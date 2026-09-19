# Laptop Monitor

A standalone real-hardware demo: physical laptops report real telemetry
(CPU load, memory, disk/network throughput, clock speed, CPU temperature,
idle time) to a backend that runs 5 module analogs against that real
data — the same 5 modules as VerdeGrid (`../datacenter-os/`), reimagined
for laptops instead of a datacenter, and mostly against genuinely real
data instead of VerdeGrid's synthetic simulator.

1. **PowerPrune — idle → sleep prompt.** An adaptive per-resource
   threshold (the same MAD/"adaptive utilization threshold" pattern used
   in production VM-consolidation research) classifies a host idle only
   when CPU, memory, disk, and network are *all* below their own adaptive
   floor, sustained for a dwell period — not a single low reading. Once
   that holds, the laptop shows a real Yes/No prompt; only clicking Yes
   actually suspends it.
2. **ThermOS — temperature + clock speed → fan-speed recommendation.** A
   linear trend fit on recent CPU package temperature projects forward
   and, cross-checked against clock speed (to avoid mistaking sensor
   noise on an idle chip for a real hotspot), produces a recommendation
   that a human operator must approve in the dashboard before anything
   touches real fan hardware.
3. **CoolSense — cooling-baseline anomaly detection.** Fits each laptop's
   own temperature-vs-CPU-load relationship from its real history, then
   flags when the current reading is a statistical outlier against that
   baseline — i.e. running hotter than *its own* established pattern
   predicts for this load, the kind of thing a clogged fan or dried
   thermal paste causes. A different question from ThermOS's predictive
   warning above, which only looks at the recent trend.
4. **NetPulse — elephant-flow detection.** Flags sustained high network
   throughput (several consecutive samples above a threshold, not one
   momentary spike) on a laptop, the same "sustained not momentary" shape
   as VerdeGrid's own per-link check.
5. **GridSync — real carbon-aware scheduling.** VerdeGrid's own docs are
   explicit that no real Electricity-Maps/WattTime access exists there,
   so its GridSync runs on a synthetic carbon simulator. This one calls a
   real, free, no-signup public API (the UK National Grid ESO's Carbon
   Intensity API) and schedules a few demo deferrable jobs (a backup, an
   update check, a scan) to run only when that real signal is clean — with
   a hard per-job deadline that force-runs it regardless, the same
   guarantee VerdeGrid's own GridSync makes. This is the one module here
   that's more real than its VerdeGrid counterpart (see the honest caveat
   in `backend/app/gridsync.py` about it being UK grid data specifically,
   not necessarily wherever the laptops physically are).

**Current scope:** every module's *decision* is real and visible on the
dashboard — PowerPrune and ThermOS's decisions are also fully wired to
real actuation (sleep, fan) behind explicit opt-in flags, gated off by
default (see "What's real vs. what needs your input" below). CoolSense,
NetPulse, and GridSync are decision/detection only for now — nothing
physically acts on their findings yet; that's a deliberate next step, not
a limitation of the detection logic itself.

## Layout

- `backend/` — Python/FastAPI. All the real logic (adaptive threshold,
  dwell tracking, hotspot prediction, cooling-baseline regression,
  elephant-flow tracking, the real carbon-intensity scheduler, and the
  supervised approval queue) lives here. `python3 -m pytest` runs its
  test suite (44 tests). Key endpoints: `POST /api/telemetry` (agent
  ingest), `GET /api/hosts` (per-host status across all 5 modules),
  `GET /api/actions` + `/approve` + `/reject` (ThermOS's supervised
  queue), `GET /api/gridsync` (the real carbon signal + demo job
  statuses).
- `agent/` — the Windows-only script that runs on each physical laptop,
  reads real metrics, and talks to the backend. See `agent/README.md`.
- `frontend/` — a small React + Vite dashboard showing live host status
  (including CoolSense/NetPulse signals per host), GridSync's real carbon
  signal + job statuses, and pending ThermOS fan-speed approvals.

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
