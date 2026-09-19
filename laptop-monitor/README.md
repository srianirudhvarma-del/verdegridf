# Laptop Monitor

A standalone real-hardware demo: two physical laptops report real telemetry
(CPU load, memory, disk/network throughput, clock speed, CPU temperature,
idle time) to a backend that decides two things from that real data:

1. **Idle for too long → prompt to sleep.** An adaptive per-resource
   threshold (the same MAD/"adaptive utilization threshold" pattern used
   in production VM-consolidation research) classifies a host idle only
   when CPU, memory, disk, and network are *all* below their own adaptive
   floor, sustained for a dwell period — not a single low reading. Once
   that holds, the laptop shows a real Yes/No prompt; only clicking Yes
   actually suspends it.
2. **Rising temperature + high clock speed → recommend more cooling.** A
   linear trend fit on recent CPU package temperature projects forward
   and, cross-checked against clock speed (to avoid mistaking sensor
   noise on an idle chip for a real hotspot), produces a recommendation
   that a human operator must approve in the dashboard before anything
   touches real fan hardware.

This is separate from and unrelated to VerdeGrid (`../datacenter-os/`),
which is a datacenter-sustainability platform running on synthetic
telemetry by design. This project exists specifically to demonstrate the
same class of idea against *real* hardware data instead.

## Layout

- `backend/` — Python/FastAPI. All the real logic (adaptive threshold,
  dwell tracking, hotspot prediction, the supervised approval queue)
  lives here. `python3 -m pytest` runs its test suite (24 tests).
- `agent/` — the Windows-only script that runs on each physical laptop,
  reads real metrics, and talks to the backend. See `agent/README.md`.
- `frontend/` — a small React + Vite dashboard showing live host status
  and pending fan-speed approvals.

## Running it for real (3 machines on one LAN)

1. Pick one machine (a laptop, a desktop, whatever) to run the backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8100
   ```
2. On each of the two laptops being monitored:
   ```bash
   cd agent
   pip install -r requirements.txt
   cp config.example.json config.json   # set hostId + backendUrl (the backend machine's LAN IP:8100)
   python agent.py                      # actionsEnabled defaults to false: measures/reports only
   ```
   The shipped config has `"actionsEnabled": false` — the agent measures
   and reports real telemetry, but any sleep-prompt or fan command coming
   back from the backend is logged and skipped, not acted on. Watch the
   dashboard fill with real numbers first; only flip `actionsEnabled` to
   `true` in `config.json` (and read `agent/README.md`'s fan-control
   section before also disabling `dryRun`) once you're ready to see the
   real sleep prompt and real fan actuation.
3. Run the dashboard (can be on any of the three machines, or your own):
   ```bash
   cd frontend
   npm install
   VITE_API_BASE_URL=http://<backend-machine-ip>:8100 npm run build && npm run preview
   # or for local dev with the proxy: npm run dev
   ```

## What's real vs. what needs your input

Everything except one thing is real end-to-end: real telemetry in, real
adaptive classification, a real sleep confirmation dialog, a real
supervised-approval queue. The one piece that needs your input before
it's "real" all the way through is the actual fan-speed command — see
`agent/README.md`'s "Fan control" section for why this project doesn't
guess a BIOS-level command on your specific hardware, and how to supply
the right one yourself.
