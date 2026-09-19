# VerdeGrid real-hardware agent

Runs on a physical Windows laptop and feeds real telemetry into the
DatacenterOS backend (`../backend`), replacing the synthetic simulator for
that one machine. Built for two specific machines: an HP OMEN Transcend 16
and an HP Victus 15, both Windows -- but the telemetry/idle-detection path
here is generic to any Windows laptop; only the fan actuation step (below)
is model-specific.

Two laptops run this agent; a third machine runs the backend
(`../backend`, `uvicorn main:app --host 0.0.0.0 --port 8000`) that all of
them can reach over the LAN.

## What's real here vs. what needs one-time setup

| Signal | Source | Setup needed |
|---|---|---|
| CPU %, memory %, disk/network throughput | `psutil` | none |
| Idle time (seconds since last input) | Win32 `GetLastInputInfo` via `ctypes` | none |
| CPU clock speed | `psutil.cpu_freq()` | none |
| CPU package temperature | LibreHardwareMonitor's WMI provider | install + run LHM (see below) |
| Sleep prompt -> real sleep | Win32 `MessageBoxW` + `SetSuspendState` | none |
| Fan speed actuation | an external command you configure | see "Fan control" below -- **not implemented directly in this agent** |

## Setup

1. `pip install -r requirements.txt` (add `wmi` is already conditional on Windows in requirements.txt).
2. Install [LibreHardwareMonitor](https://github.com/LibreHardwareMonitorTeam/LibreHardwareMonitor) (free, open source), run it, and leave it running in the background -- it exposes sensor readings (including CPU package temperature) over WMI at namespace `root/LibreHardwareMonitor`, which `agent.py`'s `get_cpu_temp_c()` reads. If you skip this, the agent still runs fine; `cpuTempC` is just reported as `null` and the backend simply won't run ThermOS hotspot prediction for this host until it's available (fail-safe: it never fabricates a temperature).
3. Copy `config.example.json` to `config.json`, and set:
   - `hostId`: a name for this specific laptop (e.g. `"omen-transcend-16"` or `"victus-15"`). Whatever you put here is what shows up in the backend's `/api/real/hosts` and in ThermOS's action recommendations.
   - `backendUrl`: the backend machine's LAN IP and port, e.g. `"http://192.168.1.50:8000"`.
   - `dryRun`: leave `true` for your first run on each machine -- the agent will still detect idle/hotspot conditions and log what it *would* do, but won't actually run a fan command (sleep prompts still show for real either way, since the prompt itself is always a real, low-risk confirmation dialog -- only the *fan* actuator is gated by `dryRun`). Flip to `false` once you've verified `fanActuatorCommands` are correct on this exact machine.
4. `python agent.py` (or `python agent.py --dry-run` to force dry-run regardless of `config.json`).

## Fan control -- read this before setting `fanActuatorCommands`

Real-time fan speed control on a laptop isn't exposed by any standard
Windows/psutil API -- it lives behind each vendor's BIOS/EC (embedded
controller) interface. On HP OMEN/Victus laptops specifically, that
interface is the same one HP's own Omen Gaming Hub uses, and it has been
reverse-engineered by the open-source **[OmenMon](https://github.com/OmenMon/OmenMon)**
project, which ships a command-line mode for exactly this
("Max Fan Mode" on/off, reading fan RPM, etc.).

This agent deliberately does **not** hard-code OmenMon's (or any) exact
BIOS/EC command bytes itself. Two reasons:

1. This code was written in a sandboxed environment with no access to
   your actual OMEN Transcend 16 / Victus 15 hardware to test against, and
   this session's network egress to OmenMon's own CLI documentation site
   was blocked, so its exact current flag syntax couldn't be verified
   here. Shipping a guessed command against real BIOS-level hardware
   control isn't a place to guess.
2. Keeping the exact fan command in your own `config.json` (as a plain
   external command string) means you can verify it works correctly
   *outside* this agent first -- run `OmenMon.com --help` (or check its
   CLI docs at the URL above) on the actual laptop, confirm the max-fan
   on/off commands do what you expect, and only then put them in
   `fanActuatorCommands`.

Until you've done that, leave `dryRun: true` -- the backend's hotspot
prediction, the supervised approval step in the ThermOS dashboard, and the
command round-trip all still work end-to-end; the agent just logs what it
would have run instead of touching real fan hardware.

If you'd rather not touch BIOS-level fan control at all, that's a
perfectly reasonable choice for a demo: leave `fanActuatorCommands` empty.
Hotspot detection, the real recommendation appearing in the ThermOS
approval queue, and the operator-approval flow are all still real and
demonstrable -- only the very last "and now the fan physically spins up"
step is skipped (the agent acks such commands as `"failed"` with a clear
reason, which the dashboard will show honestly rather than pretending it
worked).

## Safety notes

- **Sleep never happens without a person clicking Yes** on this specific
  machine, every time -- there is no auto-execute path for it, matching
  the rest of this codebase's "every classification defaults to the
  safest state" rule.
- **Fan speed increases only after an operator approves the recommendation
  in the ThermOS dashboard** (the existing supervised `ActionRecommendationQueue`,
  MUST HAVE #22) -- reverting the fan speed back down once the hotspot
  clears is the one thing that happens automatically, since that's the
  safe direction.
- A laptop that stops sending telemetry (agent closed, network down) is
  simply skipped by the backend's next tick -- it is never classified as
  idle, and never sent a stale command, from missing data.
