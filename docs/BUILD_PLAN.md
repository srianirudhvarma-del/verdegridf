# VerdeGrid Build Plan
### Translating the 64-item Consolidated Change List + Implementation Methodology into concrete steps against the actual codebase

Source docs: `VerdeGrid-Implementation-Methodology.md`, `VerdeGrid-Consolidated-Change-List.docx`, plus the four per-module deep-research reports.

---

## 0. Where we actually are vs. what the docs assume

The methodology is written as if telemetry is already flowing and modules already talk to each other. The real state of this repo, after the earlier cleanup pass:

- **Backend** (`datacenter-os/backend/api/routes.py`): 15 endpoints, every one either a fixed canned response or a stateless loop generating random-looking numbers on each request. No history, no memory, no cross-module calls.
- **Frontend**: never calls that backend at all. Every dashboard module runs its own local mock generator (`src/data/mock/*.js`), fully disconnected.
- **None of the 22 MUST HAVE items exist yet**, not even as stubs — no shared contracts, no classification system, no adaptive thresholds, no event bus.

So this is a from-scratch build using the methodology as spec, not a wire-up job. Two decisions already made:

1. **Telemetry source**: build a stateful synthetic telemetry simulator per module — realistic time series with actual variance, trends, and occasional anomalies — so the real algorithms (MAD thresholds, dwell timers, elephant-flow detection, etc.) operate on genuinely plausible data instead of static randoms. This is a real, reusable engine, not a stopgap.
2. **Sequencing**: build the entire backend (all modules, all MUST HAVE + SHOULD HAVE items) first. Wire the frontend to the real backend in one dedicated pass at the end, replacing `src/data/mock/*` calls with real HTTP requests module by module.

## 1. Stack translation from the methodology's assumptions to our real stack

| Methodology assumes | We actually have | Translation |
|---|---|---|
| Node/TypeScript backend | Python/FastAPI | TS `interface` → Pydantic `BaseModel`, same field names/shapes |
| Shared event bus (pub/sub) | Single FastAPI process | In-process pub/sub (simple `EventEmitter`-style class) now; swappable for a real bus later without touching module logic |
| WebSocket dashboard | REST polling (3–5s refresh, already the frontend's pattern) | Keep REST; no need to introduce WebSockets to hit the methodology's 30–60s telemetry cadence |
| Hypervisor/BMC/SNMP/Electricity-Maps live integrations | No real hardware access | Synthetic telemetry simulator per module (Decision #1 above), with the real client code written behind an adapter interface so a real integration can be dropped in later without touching the algorithm layer |

## 2. Target repo layout (Python packages mirroring the methodology's Section 1)

```
datacenter-os/backend/
  shared/
    contracts.py          # Pydantic: WorkloadTag, CapacityForecast, ThermalHeadroom
    eventbus.py            # in-process pub/sub
    classification.py       # shared workload-classification logic
    telemetry_sim.py         # the stateful synthetic telemetry engine (Decision #1)
  powerprune/
    telemetry.py              # adapter interface + simulator-backed implementation
    threshold.py                # MAD adaptive threshold engine
    consolidation.py             # bin-packing optimizer + migration-cost model
    power.py                      # dwell-timer state machine
  gridsync/
    grid.py                        # Electricity Maps client (already exists) + forecast
    scheduler.py                    # capacity-curve engine + hysteresis
    jobs.py                          # job classification + deadline enforcement
  coolsense/
    sensors.py                       # pressure + humidity ingestion
    baseline.py                       # per-rack rolling baseline + peer comparison
    anomaly.py                         # multi-signal Z-score + maintenance suppression
  netpulse/
    telemetry.py                       # flow telemetry + SNMP fallback
    flow.py                             # elephant-flow detector
    congestion.py                        # dwell-time congestion confirmation
    routing.py                            # fail-safe-open path control
  thermos/
    sensors.py                             # temp grid + airflow
    model.py                                # physics-lite RC core + ML residual
    control.py                               # supervised action-recommendation queue
  api/routes.py             # stays as the single HTTP surface; delegates to the packages above
```

`api/routes.py` keeps its role as the one place FastAPI routes live (per our earlier "leave it as one file" decision) — but its endpoint bodies become thin wrappers calling into the real module packages, instead of containing the logic inline as they do today.

---

## 3. Phase-by-phase plan

Phases 1–6 mirror the methodology's Section 9 build order exactly, because the dependency reasoning there is sound: PowerPrune's classification + capacity signal is the one three other modules need before their own cross-wiring items make sense.

### Phase 0 — Shared infrastructure
- `shared/contracts.py`: `WorkloadTag`, `CapacityForecast`, `ThermalHeadroom` (Pydantic, from methodology Section 2)
- `shared/eventbus.py`: minimal in-process pub/sub covering the 5 topics in the methodology's `Topic` type
- `shared/classification.py`: the protected/deferrable logic reused by PowerPrune, GridSync, NetPulse
- `shared/telemetry_sim.py`: the synthetic telemetry engine — per-host/per-rack/per-link time series with configurable trend + noise + injectable anomalies (leaks, thermal spikes, elephant flows), so every later phase has something real to compute over

### Phase 1 — PowerPrune MUST HAVE #1–#5
1. Adaptive multi-resource MAD threshold (replacing the fixed 15% CPU-only check)
2. Migration-cost check before any consolidation move
3. Workload classification (protected/deferrable), with the hard filter excluding untagged VMs from candidates
4. Redundancy-aware placement (`minRedundancy`, anti-affinity groups)
5. Asymmetric dwell-time/wake state machine

*Everything downstream depends on this phase's capacity + classification signal.*

### Phase 2 — ThermOS MUST HAVE #18, #19, #20, #21
18. Uncertainty bands (MC Dropout ensemble) on predictions
19. Wire PowerPrune's load/power telemetry into the thermal feature vector
20. Hybrid physics (RC thermal model) + ML residual core, replacing the current pure-stub prediction
21. Basic airflow sensing (shares the pressure-sensor pipeline built for CoolSense)

*CoolSense's SHOULD HAVE #9 and PowerPrune's SHOULD HAVE #2 depend on this phase's headroom/temperature feed.*

### Phase 3 — GridSync MUST HAVE #6–#9
6. Workload classification reusing the shared contract, keyed by `jobId`
7. Hard max-delay deadline per deferrable job (priority queue, force-run past deadline)
8. Documented average-vs-marginal signal justification (config object, not a hidden default)
9. Cross-wire with PowerPrune's capacity forecast before scheduling into a window

*Depends on Phase 1's capacity-forecast API.*

### Phase 4 — CoolSense MUST HAVE #10–#13
10. Differential-pressure sensing added to the detection pipeline
11. Humidity sensing (facility/zone-level)
12. Per-rack baseline + peer-rack comparison, cross-wired with PowerPrune's utilization signal
13. Explicit maintenance-mode suppression

*MUST HAVE #12 depends on Phase 1's per-rack utilization signal.*

### Phase 5 — NetPulse MUST HAVE #14–#17
14. Elephant-flow detection alongside link-utilization
15. Dwell-time/hysteresis before any reroute + reroute cooldown
16. Explicit fail-safe-open story (optimizer only biases existing ECMP/BGP; watchdog reverts to default on optimizer failure)
17. Auto-reroute scoped narrowly (elephant + non-latency-sensitive + confirmed congestion + a viable alt path only)

*MUST HAVE #17's non-latency-sensitive check depends on Phase 1's classification.*

### Phase 6 — ThermOS MUST HAVE #22
22. Supervised (human-approved) closed-loop control — `ActionRecommendation` queue with a trust-ladder toggle, never silently auto-enabled

*Depends on Phase 2's physics+ML core already being in place.*

### Phase 7 — All 16 SHOULD HAVE items (any order, each is cross-wiring on top of an already-working MUST HAVE base)
- PowerPrune: failure-during-consolidation handling; thermal-headroom cross-wiring; K8s telemetry adapter
- GridSync: 48h forecast ingestion; hysteresis/smoothing on carbon state; electricity-price signal
- CoolSense: point-sensor backstop; sensor-fault/drift checks; ThermOS cross-wire for cooling-performance estimate
- NetPulse: packet-loss/queue-depth telemetry; LLDP auto-topology; SNMP fallback path; latency-sensitivity tagging cross-wire
- ThermOS: ConvLSTM upgrade + explicit sensor-vs-interpolated flagging; thermal zoning/adaptive setpoints; predictive maintenance for cooling equipment

### Phase 8 — MODIFY documentation changes
- Global find-and-replace: "horizontal integration" → "cross-layer, hierarchical co-optimization"
- ThermOS positioning: "a prediction model with a dashboard" → "a Physics + Data + Control system" (sequenced *after* Phases 2 and 6 so it's literally true when written)

### Phase 9 — Frontend integration (our added phase, per the backend-first decision)
- Replace each module's `src/data/mock/*` calls with real requests to the now-real backend, one module at a time
- Re-introduce `services/api.js` (removed earlier as dead code) as the real integration layer
- Re-add the Vite dev proxy removed earlier, now pointed at a backend worth proxying to
- UI additions the new backend logic actually needs: the `ActionRecommendation` approval queue (Phase 6), the maintenance-mode toggle (Phase 4), the workload-classification override UI (Phase 1)

### Phase 10 — FUTURE items: explicitly out of scope
Not implemented without a separate go-ahead — each has a stated precondition (e.g. "once sufficient historical data exists to train on"). Listed in the change list's Table 4; revisit individually, not as a batch.

### Explicitly not building (for the record, matches the change list's anti-scope table)
Fleet-scale custom scheduler, full SDN fabric replacement, CFD simulation, dense liquid-cooling sensor arrays, autonomous (non-supervised) control anywhere, spatial multi-region load shifting, and a few others — 13 items total, each with a stated reason in the change list. These stay out unless a stated precondition changes.

---

## 4. Acceptance tests per phase (reused directly from the methodology, Section 10)

Each phase ships with its own test file (extending the pytest suite already in `backend/tests/`) proving the specific behaviors the methodology calls out, e.g.:
- PowerPrune: adaptive threshold actually widens with variance (not fixed at 15%); memory-bound-but-CPU-idle host never flagged idle; poor cost/benefit migration blocked; untagged VM never in candidate list; power-down never breaches `minRedundancy`
- GridSync: untagged job never delayed; deferrable job force-runs at deadline even on a dirty grid; scheduling into insufficient-capacity window triggers pre-wake or reschedule
- CoolSense: workload-explained flow drop does not alert; unexplained flow drop does; maintenance window suppresses; flatlined sensor raises `sensor_fault`, not false-clear
- NetPulse: single congested sample doesn't reroute; confirmed elephant-flow collision on non-latency traffic can; latency-tagged flow never auto-rerouted; optimizer-down still routes via default ECMP
- ThermOS: every prediction ships a confidence band; physics-only core produces a plausible prediction with zero training data; `ActionRecommendation` always requires approval until the trust ladder is explicitly enabled

---

## 5. Suggested working rhythm

Per the methodology's own instruction: implement one numbered item (or one phase) at a time — build, test, commit, move to the next. Given the size of this (22 MUST HAVE + 16 SHOULD HAVE + frontend wiring), I'd suggest we tackle it phase by phase in separate working sessions rather than attempting large chunks in one pass, checking in after each phase before moving to the next.
