# Laptop Monitor agent

Runs on a physical Windows laptop and feeds real telemetry into the
Laptop Monitor backend (`../backend`).

## What's real here vs. what needs one-time setup

| Signal | Source | Setup needed |
|---|---|---|
| CPU %, memory %, disk/network throughput | `psutil` | none |
| Idle time (seconds since last input) | Win32 `GetLastInputInfo` via `ctypes` | none |
| CPU clock speed | `psutil.cpu_freq()` | none |
| CPU package temperature | LibreHardwareMonitor's WMI provider | install + run LHM (see below) |
| Sleep prompt → real sleep | Win32 `MessageBoxW` + `SetSuspendState` | none |
| Fan speed actuation | an external command you configure | see "Fan control" below — **not implemented directly in this agent** |

## Setup

1. `pip install -r requirements.txt`.
2. Install [LibreHardwareMonitor](https://github.com/LibreHardwareMonitorTeam/LibreHardwareMonitor) (free, open source), run it, and leave it running in the background — it exposes sensor readings (including CPU package temperature) over WMI at namespace `root/LibreHardwareMonitor`. If you skip this, the agent still runs; `cpuTempC` is reported as `null` and the backend simply skips hotspot prediction for this host until it's available (fail-safe: it never fabricates a temperature).
3. Copy `config.example.json` to `config.json`, and set:
   - `hostId`: a name for this specific laptop.
   - `backendUrl`: the backend machine's LAN IP and port, e.g. `"http://192.168.1.50:8100"`.
   - `dryRun`: leave `true` for your first run on each machine — sleep prompts still show for real either way; only the *fan* actuator step is gated by `dryRun`.
4. `python agent.py` (or `python agent.py --dry-run` to force dry-run regardless of `config.json`).

## Fan control — read this before setting `fanActuatorCommands`

Real-time fan speed control on a laptop isn't exposed by any standard
Windows/psutil API — it lives behind each vendor's BIOS/EC interface, and
that interface differs per laptop model/vendor. This agent deliberately
does **not** hard-code any vendor's BIOS/EC command bytes itself, on
hardware it can't verify against. Instead, `fanActuatorCommands` in
`config.json` takes a plain external command string you supply — find and
verify the right tool for your exact laptop model first (for example,
some HP OMEN/Victus laptops can use the open-source
[OmenMon](https://github.com/OmenMon/OmenMon) project's CLI mode, which
reverse-engineers HP's own BIOS interface for those models specifically —
run its `--help`/CLI docs and confirm the max-fan on/off behavior works
correctly on the actual machine *before* wiring it in here). Other
vendors need their own equivalent tool.

Until you've verified a real command, leave `dryRun: true` — telemetry,
hotspot prediction, and the supervised approval flow in the dashboard all
still work end-to-end; the agent just logs what it would have run instead
of touching real fan hardware. If you'd rather not touch BIOS-level fan
control at all, leave `fanActuatorCommands` empty — everything up to (but
not including) physical fan actuation is still real and demonstrable; the
agent acks such commands as `"failed"` with a clear reason instead of
pretending it worked.

## Safety notes

- **Sleep never happens without a person clicking Yes** on this specific
  machine, every time — there's no auto-execute path for it.
- **Fan speed increases only after an operator approves the
  recommendation in the dashboard** — reverting the fan speed back down
  once the hotspot clears is the one thing that happens automatically,
  since that's the safe direction.
- A laptop that stops sending telemetry is simply skipped by the
  backend's next tick — never classified as idle, and never sent a stale
  command, from missing data.
