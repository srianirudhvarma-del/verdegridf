# GreenCore — Project Context for Claude Code

## What this repo is

GreenCore is a datacenter sustainability platform: 5 modules (IdleHunter, CarbonClock, WaterWatch, LightSpeed, ThermalTrace) covering server consolidation, carbon-aware job scheduling, water/cooling monitoring, network optimization, and thermal prediction. Two parts:

- `datacenter-os/backend/` — Python/FastAPI. All real logic lives here.
- `datacenter-os/frontend/` — React 18 + Vite dashboard. Currently runs on local mock data (`src/data/mock/*.js`), fully disconnected from the backend. **Do not touch the frontend until told to** — see "Current phase" below.
- `core/`, `plugins/`, `index.js` at repo root — a small, unrelated Node plugin-loader experiment. Not part of GreenCore proper; leave alone unless explicitly asked.

## Required reading before starting any phase

Read these, in this order, before writing code:

1. `docs/BUILD_PLAN.md` — the phased build plan, translated to our actual stack. **This is the plan of record.**
2. `docs/GreenCore-Implementation-Methodology.md` — exact algorithms, schemas, pseudocode, and acceptance tests per item.
3. `docs/GreenCore-Consolidated-Change-List.md` — the full 64-item change list with rationale, if you need the "why" behind an item.
4. The relevant per-module `docs/*-Deep-Research-Architecture-Optimization.docx` — only if you need more background than the methodology doc already distilled. Usually you won't need these.

## Key decisions already made (do not re-litigate these)

- **Telemetry source**: no real hypervisor/BMC/SNMP/Electricity-Maps hardware access exists. Build a stateful synthetic telemetry simulator (`shared/telemetry_sim.py`, Phase 0) with realistic time series — real variance, trends, injectable anomalies — so the actual algorithms (MAD thresholds, dwell timers, elephant-flow detection, etc.) run on genuinely plausible data. This is real, reusable engine code, not a stopgap to throw away later. Write real client adapters behind an interface so a future real integration can swap in without touching algorithm code.
- **Sequencing**: build the entire backend first (all phases through Phase 8). Frontend wiring is Phase 9, done in one dedicated pass at the end — don't wire any dashboard module to the real backend before then, even if it would be easy to.
- **Stack translation**: the methodology doc's TypeScript interfaces translate directly to Pydantic `BaseModel`s with the same field names/shapes. Its "event bus" becomes an in-process pub/sub (`shared/eventbus.py`) — no need for a real message broker. No WebSockets — REST polling at 3–5s (the frontend's existing cadence) satisfies the methodology's 30–60s telemetry cadence with room to spare.
- **`api/routes.py` stays a single file** (not split per-module) — but its endpoint bodies should become thin wrappers delegating to the real module packages (`idlehunter/`, `carbonclock/`, etc.), not contain logic inline.
- **Fail-safe-open default, everywhere**: every classification defaults to the safest state (`protected` not `deferrable`, `normal` not `idle-candidate`) until explicitly overridden by data or an operator. Every MUST HAVE item needs an automatic fallback to current (pre-change) behavior if its new dependency is unavailable.

## Current phase

<!-- Update this line as we progress. Example: -->
<!-- Currently on: Phase 0 — shared infrastructure (contracts, event bus, classification, telemetry simulator) -->
Phases 0-4 complete. Phase 0: `shared/contracts.py`, `shared/eventbus.py`, `shared/classification.py`, `shared/telemetry_sim.py`. Phase 1: `idlehunter/threshold.py` (#1 MAD threshold), `idlehunter/consolidation.py` (#2 migration-cost check, #3 classification hard filter, #4 redundancy-aware placement), `idlehunter/power.py` (#5 dwell/wake state machine), `idlehunter/telemetry.py` (simulator-backed adapter). Phase 2: `thermaltrace/sensors.py` (#21 airflow/pressure sensing — `PressureReading` defined here for WaterWatch's Phase 4 MUST HAVE #10 to reuse, since ThermalTrace needs it first), `thermaltrace/model.py` (#20 physics-lite RC core + ML residual corrector, #18 MC-Dropout-style uncertainty bands, #19 IdleHunter telemetry join into the feature vector). Phase 3: `carbonclock/jobs.py` (#6 classification reused from `shared/classification.py` keyed by jobId, #7 deadline priority queue), `carbonclock/grid.py` (#8 signal-info config + synthetic 48h forecast), `carbonclock/scheduler.py` (core capacity-curve algorithm + #9 IdleHunter capacity cross-wire, emits `carbonclock.prewake.requested` — added to `shared/contracts.py`'s Topic set, which Section 2 documents as a minimal starting list). Phase 4: `waterwatch/sensors.py` (#10 pressure sensing, importing `PressureReading` from `thermaltrace/sensors.py` rather than redefining it; #11 zone-level humidity), `waterwatch/baseline.py` (#12's load-bucket/baseline/z-score/peer-z machinery), `waterwatch/anomaly.py` (#12's anomaly decision — flow z < -2.5 AND peer z divergence AND workload delta doesn't explain it; #13 maintenance-mode suppression that still logs the raw anomaly for audit). All tested, full suite passing (152 tests). Next up: Phase 5 — LightSpeed MUST HAVE #14–#17.

## Working rhythm — follow this strictly

1. Implement **one phase at a time**, not the whole plan in one shot. Within a phase, one numbered MUST HAVE item at a time is even better if the phase is large.
2. After implementing an item: **write and run a test proving the specific acceptance criterion** from the methodology doc / Section 10 checklist — not just "it runs," but the actual documented behavior (e.g. "adaptive threshold widens with variance," "untagged VM never in candidate list").
3. Run the existing test suite (`npm test` at repo root for the JS plugin tests, `python3 -m pytest` in `datacenter-os/backend/` for the Python suite) to confirm nothing already-working broke.
4. Commit after each item or phase passes its tests. Small commits, not one giant diff.
5. Update the "Current phase" line above before ending a session, so the next session picks up correctly.
6. If a phase's acceptance test can't pass yet because an earlier phase's dependency isn't built — stop and say so, don't fake it with a stub that silently returns fixed data.

## Do not build

The methodology's Section 5 / change-list's Table 5 lists 13 explicitly out-of-scope items (fleet-scale custom scheduler, full SDN fabric replacement, CFD simulation, autonomous non-supervised control anywhere, etc.). Don't implement these even if a later phase seems to gesture toward them — check the anti-scope table first if something feels like it's drifting that direction.
