"""
VerdeGrid real-hardware agent -- runs on a physical Windows laptop and
feeds real telemetry into the DatacenterOS backend's PowerPrune/ThermOS
pipeline (see backend/shared/real_agent.py and backend/api/real_nodes.py),
in place of the synthetic simulator, for that one machine.

What it does, every poll cycle:
  1. Reads real CPU load, memory, disk/network throughput, CPU clock
     speed, idle time, and (if available) CPU package temperature.
  2. POSTs that sample to the backend's /api/real/telemetry endpoint.
  3. Polls /api/real/commands/{host_id} for anything the backend wants
     this machine to do, and acts on it:
       - "sleep_prompt": shows a real Yes/No prompt on this machine
         ("this laptop has been idle for N minutes -- sleep now?"). Only
         a Yes actually suspends the machine. Nothing here ever sleeps
         the laptop without that explicit click.
       - "fan_max_on" / "fan_max_off": runs an operator-configured
         external command (see config.example.json's fanActuatorCommands)
         -- this agent does not hard-code any BIOS/EC command bytes
         itself. See README.md for why, and for the exact HP OMEN/Victus
         setup this needs.
  4. Acks back what actually happened via /api/real/commands/{id}/ack,
     so the dashboard reflects reality, not just what was requested.

Only depends on the standard library + psutil + requests, so it runs on
a bare "python -m pip install -r requirements.txt" with no build step.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import psutil
import requests

logger = logging.getLogger("verdegrid.agent")

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")

# 0x24 = MB_YESNO | MB_ICONQUESTION
MB_YESNO_ICONQUESTION = 0x24
IDYES = 6


class Config:
    def __init__(self, data: dict) -> None:
        self.host_id: str = data["hostId"]
        self.backend_url: str = data["backendUrl"].rstrip("/")
        self.poll_interval_seconds: float = float(data.get("pollIntervalSeconds", 5.0))
        self.critical_temp_c: float = float(data.get("criticalTempC", 92.0))
        self.disk_max_bytes_per_sec: float = float(data.get("diskMaxBytesPerSec", 200 * 1024 * 1024))
        self.network_max_bytes_per_sec: float = float(data.get("networkMaxBytesPerSec", 50 * 1024 * 1024))
        self.dry_run: bool = bool(data.get("dryRun", True))
        fan_cmds = data.get("fanActuatorCommands", {})
        self.fan_max_on_cmd: Optional[str] = fan_cmds.get("fanMaxOn")
        self.fan_max_off_cmd: Optional[str] = fan_cmds.get("fanMaxOff")

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            raise SystemExit(
                f"Config file not found: {path}\n"
                f"Copy config.example.json to config.json and fill in hostId/backendUrl first."
            )
        return cls(json.loads(path.read_text()))


# --------------------------------------------------------------------------
# Real metric collection
# --------------------------------------------------------------------------


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input, via the standard
    Win32 GetLastInputInfo idle-detection pattern. ctypes-only -- no
    pywin32 dependency needed for this one."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
    return max(0.0, millis / 1000.0)


def get_cpu_temp_c() -> Optional[float]:
    """
    Windows has no built-in cross-vendor way to read CPU package
    temperature. This queries LibreHardwareMonitor's WMI provider
    (namespace root/LibreHardwareMonitor, class Sensor), which is the
    standard free way to get this on a Windows laptop -- see README.md
    for the one-time setup (install + run LibreHardwareMonitor with "Run
    In Background" so its WMI server stays up). Returns None (not a
    fabricated value) if that provider isn't reachable, e.g. LHM isn't
    running -- the backend's fail-safe-open handling already treats a
    missing cpuTempC as "no thermal prediction possible right now"
    rather than guessing.
    """
    try:
        import wmi  # local import: optional dependency, only needed for this

        conn = wmi.WMI(namespace="root/LibreHardwareMonitor")
        for sensor in conn.Sensor():
            if sensor.SensorType == "Temperature" and "CPU Package" in sensor.Name:
                return float(sensor.Value)
        # Fall back to any CPU temperature sensor if "CPU Package" isn't named that on this board.
        for sensor in conn.Sensor():
            if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                return float(sensor.Value)
    except Exception:
        logger.debug("CPU temperature unavailable (LibreHardwareMonitor WMI not reachable)", exc_info=True)
    return None


class ThroughputMeter:
    """Turns cumulative byte counters into a 0-100 percent normalized
    against a configured max throughput -- the same shape as the
    simulator's diskIO/network resources, so threshold.py's MAD
    classifier doesn't need to know real hardware is behind it."""

    def __init__(self, max_bytes_per_sec: float) -> None:
        self._max_bytes_per_sec = max_bytes_per_sec
        self._last_bytes: Optional[int] = None
        self._last_time: Optional[float] = None

    def sample(self, total_bytes: int) -> float:
        now = time.monotonic()
        if self._last_bytes is None:
            self._last_bytes, self._last_time = total_bytes, now
            return 0.0
        elapsed = max(1e-6, now - self._last_time)
        rate = max(0.0, (total_bytes - self._last_bytes) / elapsed)
        self._last_bytes, self._last_time = total_bytes, now
        return min(100.0, 100.0 * rate / self._max_bytes_per_sec) if self._max_bytes_per_sec > 0 else 0.0


def collect_sample(config: Config, disk_meter: ThroughputMeter, net_meter: ThroughputMeter) -> dict:
    cpu_freq = psutil.cpu_freq()
    disk_counters = psutil.disk_io_counters()
    net_counters = psutil.net_io_counters()
    battery = psutil.sensors_battery()

    return {
        "hostId": config.host_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cpuPercent": psutil.cpu_percent(interval=None),
        "memPercent": psutil.virtual_memory().percent,
        "diskIoPercent": disk_meter.sample(disk_counters.read_bytes + disk_counters.write_bytes),
        "networkPercent": net_meter.sample(net_counters.bytes_sent + net_counters.bytes_recv),
        "cpuFreqMhz": cpu_freq.current if cpu_freq else 0.0,
        "cpuFreqMaxMhz": (cpu_freq.max or cpu_freq.current) if cpu_freq else 0.0,
        "cpuTempC": get_cpu_temp_c(),
        "idleSeconds": get_idle_seconds(),
        "batteryPercent": battery.percent if battery else None,
    }


# --------------------------------------------------------------------------
# Real actuation -- always asks first for sleep, and never hard-codes a
# BIOS/EC fan command itself (see README.md).
# --------------------------------------------------------------------------


def handle_sleep_prompt(config: Config, command: dict, session: requests.Session) -> None:
    idle_minutes = command.get("payload", {}).get("idleMinutes", "several")
    message = (
        f"VerdeGrid PowerPrune: this laptop has been idle for ~{idle_minutes} minutes.\n\n"
        f"Put it to sleep now?"
    )
    answer = ctypes.windll.user32.MessageBoxW(None, message, "VerdeGrid PowerPrune", MB_YESNO_ICONQUESTION)
    if answer != IDYES:
        ack(session, config, command["id"], "declined")
        return
    ack(session, config, command["id"], "executed", "user confirmed sleep")
    # SetSuspendState blocks until the machine resumes; the ack above is
    # sent first so the dashboard reflects the decision immediately
    # rather than only after the laptop wakes back up.
    ctypes.windll.powrprof.SetSuspendState(False, True, False)


def handle_fan_command(config: Config, command: dict, session: requests.Session) -> None:
    cmd = config.fan_max_on_cmd if command["type"] == "fan_max_on" else config.fan_max_off_cmd
    if not cmd:
        ack(session, config, command["id"], "failed", f"no {command['type']} command configured")
        return
    if config.dry_run:
        logger.info("[dry-run] would run: %s", cmd)
        ack(session, config, command["id"], "executed", f"dry-run: {cmd}")
        return
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True, timeout=15)
        ack(session, config, command["id"], "executed", cmd)
    except Exception as exc:
        logger.exception("fan actuator command failed")
        ack(session, config, command["id"], "failed", str(exc))


def ack(session: requests.Session, config: Config, command_id: str, result: str, detail: str = "") -> None:
    try:
        session.post(
            f"{config.backend_url}/api/real/commands/{command_id}/ack",
            json={"result": result, "detail": detail},
            timeout=10,
        )
    except requests.RequestException:
        logger.exception("failed to ack command %s", command_id)


def handle_command(config: Config, command: dict, session: requests.Session) -> None:
    if command["type"] == "sleep_prompt":
        handle_sleep_prompt(config, command, session)
    elif command["type"] in ("fan_max_on", "fan_max_off"):
        handle_fan_command(config, command, session)
    else:
        logger.warning("unknown command type: %s", command["type"])


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------


def run(config: Config) -> None:
    session = requests.Session()
    disk_meter = ThroughputMeter(config.disk_max_bytes_per_sec)
    net_meter = ThroughputMeter(config.network_max_bytes_per_sec)
    psutil.cpu_percent(interval=None)  # prime the first (meaningless) reading

    logger.info("VerdeGrid real-agent starting: host=%s backend=%s dry_run=%s", config.host_id, config.backend_url, config.dry_run)

    while True:
        try:
            sample = collect_sample(config, disk_meter, net_meter)
            session.post(f"{config.backend_url}/api/real/telemetry", json=sample, timeout=10)

            resp = session.get(f"{config.backend_url}/api/real/commands/{config.host_id}", timeout=10)
            command = resp.json()
            if command.get("type") != "none":
                # Run in a thread so a blocking sleep-prompt dialog doesn't
                # stall the next poll cycle's telemetry post indefinitely.
                threading.Thread(target=handle_command, args=(config, command, session), daemon=True).start()
        except requests.RequestException:
            logger.exception("backend request failed; will retry next cycle")
        except Exception:
            logger.exception("unexpected error in agent loop")

        time.sleep(config.poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="VerdeGrid real-hardware telemetry agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="force dry-run regardless of config.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if sys.platform != "win32":
        logger.warning("This agent targets Windows (sleep/fan actuation are Win32-specific). Telemetry-only paths may still work elsewhere.")

    config = Config.load(args.config)
    if args.dry_run:
        config.dry_run = True

    run(config)


if __name__ == "__main__":
    main()
