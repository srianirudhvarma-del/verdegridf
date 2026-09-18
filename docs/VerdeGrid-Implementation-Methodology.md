# VerdeGrid Implementation Methodology
### A build spec for implementing all 64 reviewed changes across PowerPrune, GridSync, CoolSense, NetPulse, and ThermOS

This document translates the consolidated change list into exact, buildable methodology: data schemas, algorithms/formulas, pseudocode, APIs, and acceptance tests, per item. It assumes VerdeGrid is a Node/TypeScript backend with a React + WebSocket dashboard (per the existing VerdeGrid architecture), but every algorithm below is stack-agnostic and can be adapted to whatever the actual codebase uses.

**How to use this with Claude Code:** feed this whole document as context, then ask it to implement one numbered item (or one module's MUST HAVE block) at a time, in the sequencing order given in Section 9. Each item is self-contained: data it needs, exact algorithm, schema, and a test to prove it works. Do not ask for the whole thing in one shot — implement, test, commit, move to the next item.

---

## 0. Conventions Used Throughout

- **Sampling cadence**: unless stated otherwise, telemetry polling is 30–60s. This is not a millisecond control system anywhere in VerdeGrid.
- **Fail-safe-open default**: every classification defaults to the safest state (`protected`, not `deferrable`; `normal`, not `idle-candidate`) until explicitly overridden by data or an operator.
- **Cross-module communication**: modules publish to and subscribe from a shared internal event bus / REST API (Section 2). No module should reach directly into another module's database — always go through the published contract.
- **Every MUST HAVE item ships with an automatic fallback to current (pre-change) behavior if its new dependency is unavailable** — e.g., if PowerPrune's capacity API is down, GridSync schedules as if no capacity data exists (conservative), rather than failing entirely.

---

## 1. Repo / Module Structure (suggested)

```
verdegrid/
  shared/
    contracts/           <- shared TypeScript types & JSON schemas (Section 2)
    eventbus/             <- pub/sub client (or REST client if no bus yet)
    classification/       <- shared workload-classification logic (reused by PowerPrune, GridSync, NetPulse)
  powerprune/
    telemetry/             <- hypervisor/BMC polling
    threshold/             <- adaptive MAD threshold engine
    consolidation/          <- bin-packing optimizer, migration-cost model
    power/                  <- dwell-timer state machine, BMC wake/sleep
  gridsync/
    grid/                   <- Electricity Maps client (current + forecast)
    scheduler/              <- capacity-curve engine, hysteresis
    jobs/                    <- job classification, deadline enforcement
  coolsense/
    sensors/                <- flow, pressure, humidity ingestion
    baseline/                <- per-rack rolling baseline + peer comparison
    anomaly/                  <- multi-signal Z-score + maintenance suppression
  netpulse/
    telemetry/               <- streaming telemetry + SNMP fallback + LLDP
    flow/                     <- elephant-flow detector
    congestion/               <- dwell-time congestion confirmation
    routing/                   <- fail-safe-open path control
  thermos/
    sensors/                   <- temp grid + airflow (shares coolsense/sensors pressure code)
    model/                      <- physics-lite RC core + ML residual correction
    control/                     <- supervised action-recommendation queue
```

---

## 2. Shared Cross-Module Data Contracts

Implement these first — four of the five modules depend on at least one of them.

```typescript
// shared/contracts/workload.ts
type WorkloadClassification = "protected" | "deferrable" | "unclassified";

interface WorkloadTag {
  workloadId: string;         // VM id, job id, or flow's owning VM id
  classification: WorkloadClassification; // default on read: "protected" if unset
  maxDelayMinutes?: number;    // required if classification === "deferrable"
  source: "operator" | "inferred" | "default";
  updatedAt: string;           // ISO timestamp
}
// RULE: any consumer treats a missing/unclassified tag as "protected". Never assume deferrable.
```

```typescript
// shared/contracts/capacity.ts
interface CapacityForecast {
  timestampRangeStart: string;
  timestampRangeEnd: string;
  poweredOnHostCount: number;
  availableCpuCapacity: number;   // aggregate, same unit as telemetry
  availableMemCapacity: number;
  standbyHostCount: number;        // powered down but wakeable
  estimatedWakeLatencySeconds: number;
}
// Published by PowerPrune, consumed by GridSync, CoolSense (for baseline correlation), NetPulse
```

```typescript
// shared/contracts/thermal.ts
interface ThermalHeadroom {
  rackId: string;
  timestamp: string;
  headroomCelsius: number;    // distance to ASHRAE envelope ceiling
  status: "ok" | "constrained" | "critical";
}
// Published by ThermOS, consumed by PowerPrune (avoid consolidating into constrained racks)
```

```typescript
// shared/contracts/events.ts
// Minimal pub/sub topics every module must support, even if backed by simple REST polling initially:
type Topic =
  | "powerprune.capacity.updated"
  | "powerprune.workload.classified"
  | "thermos.headroom.updated"
  | "gridsync.job.scheduled"
  | "netpulse.flow.classified";
```

---

## 3. PowerPrune — Implementation Methodology

### MUST HAVE #1 — Adaptive multi-resource threshold (replace fixed 15% CPU-only)

**Data needed per host, per resource** (`cpu`, `mem`, `diskIO`, `network`), sampled every 30–60s, rolling window of last `N=60` samples (~30–60 min).

**Algorithm — Median Absolute Deviation (MAD) adaptive threshold** (Beloglazov & Buyya pattern):

```
for each resource r in {cpu, mem, diskIO, network}:
    median_r = median(history_r)
    MAD_r    = median(abs(x_i - median_r) for x_i in history_r)
    lower_r  = max(0, median_r - s * MAD_r)      // idle-candidate floor
    upper_r  = median_r + s * MAD_r              // overload ceiling
    // s = sensitivity constant, default 2.5; expose as config
    // COLD START: if history length < N, use static defaults
    //   (cpu lower=15%, mem lower=20%, diskIO lower=10%, network lower=10%)
    //   until enough history accumulates (documented, not hidden)
```

**Host status decision**:
```
status = "overloaded"      if ANY resource current_r > upper_r
status = "idle-candidate"  if ALL resources current_r < lower_r
status = "normal"          otherwise
```

**Schema**:
```typescript
interface HostUtilizationState {
  hostId: string;
  timestamp: string;
  resources: { cpu: number; mem: number; diskIO: number; network: number };
  thresholds: { cpu: {lower:number,upper:number}; mem: {...}; diskIO: {...}; network: {...} };
  status: "normal" | "idle-candidate" | "overloaded";
}
```

**Acceptance test**: feed synthetic time series with rising variance; assert threshold widens (adaptive), not fixed at 15%. Feed a CPU-idle-but-memory-bound host; assert status is NOT `idle-candidate` (multi-resource check working).

---

### MUST HAVE #2 — Migration-cost check before triggering a move

**Data needed**: VM memory size (`vmMemMB`, from hypervisor API), available migration-network bandwidth (`bandwidthMbps`), memory dirty rate (`dirtyRateMBps` — start with a conservative constant e.g. `0.10 * vmMemMB` per second if the hypervisor doesn't expose real dirty-rate stats yet).

**Downtime estimate** (closed-form, from the migration-cost literature):
```
n = ceil( log(dirtyRateMBps / bandwidthMbps) / log(dirtyThresholdMB / vmMemMB) )
downtimeSeconds = (vmMemMB * dirtyRateMBps^n) / bandwidthMbps^(n+1) + resumeTimeSeconds
```
(If this is too complex to implement immediately, use the simpler bound: `migrationDurationSeconds ≈ vmMemMB / effectiveBandwidthMBps`, and treat `downtimeSeconds` as a fixed conservative fraction, e.g. 5%, of that duration — flag this simplification in code comments.)

**Cost/benefit decision**:
```
migrationEnergyCost = (P_source_elevated - P_source_idle) * migrationDurationSeconds
                     + (P_dest_elevated  - P_dest_idle)   * migrationDurationSeconds
projectedSavings     = P_host_baseline_draw * expectedDwellHours * 3600
proceed = projectedSavings > migrationEnergyCost * SAFETY_MARGIN   // SAFETY_MARGIN default = 3
```

**Schema**:
```typescript
interface MigrationDecision {
  vmId: string; sourceHost: string; targetHost: string;
  estimatedCostJoules: number; estimatedSavingsJoules: number;
  proceed: boolean; reason: string;
}
```

**Acceptance test**: a VM with large memory + low expected dwell time → `proceed=false`. A VM with small memory + long expected dwell (e.g., overnight) → `proceed=true`.

---

### MUST HAVE #3 — Workload classification (protected vs. deferrable)

Use the shared `WorkloadTag` contract (Section 2). Implementation steps:

1. `GET /api/powerprune/workloads/:vmId/classification` → returns tag, defaulting to `{classification:"protected", source:"default"}` if none exists.
2. `PATCH /api/powerprune/workloads/:vmId/classification` (operator-only) → sets `classification`, requires `maxDelayMinutes` if `deferrable`.
3. Optional inference helper: suggest `deferrable` for VM names/tags matching `/batch|backup|etl|report|training/i` — **never auto-apply**; surface as a one-click confirm in the UI.
4. Consolidation optimizer (`consolidation/optimizer.ts`) must hard-filter: any VM without `classification === "deferrable"` is excluded from the migration candidate list entirely.

**Acceptance test**: an untagged VM is never present in the optimizer's candidate output, even if it's CPU-idle.

---

### MUST HAVE #4 — Redundancy-aware placement constraints

**Config**: `minRedundancy` per host-group (e.g., `N+1` → 1 extra host's worth of capacity must stay powered on).

**Algorithm**:
```
requiredCapacity = sum(runningVmResourceRequirements) + minRedundancy * avgHostCapacity
candidatePlan = optimizer.proposeConsolidation(...)
poweredOnCapacityAfterPlan = totalCapacity - sum(candidatePlan.hostsToPowerDown.capacity)
if poweredOnCapacityAfterPlan < requiredCapacity:
    trim candidatePlan.hostsToPowerDown until constraint satisfied (remove lowest-savings hosts first)
```
Additionally: maintain an `antiAffinityGroups` map (VMs tagged as replicas of each other); reject any single-host placement that would co-locate two members of the same group.

**Acceptance test**: with `minRedundancy=1` and only exactly N+1 hosts running, the optimizer must refuse to power down any host that would drop below N.

---

### MUST HAVE #5 — Asymmetric dwell-time / wake policy

**State machine per host**:
```
NORMAL --(idle-candidate for >= dwellTimeDownSamples)--> IDLE_CANDIDATE
IDLE_CANDIDATE --(migration+consolidation succeeds)--> STANDBY
STANDBY --(cluster capacity crosses high-water mark, OR any single sample of "overloaded" elsewhere)--> WAKING
WAKING --(BMC wake confirmed + host rejoins hypervisor pool)--> NORMAL
```
Defaults: `dwellTimeDownSamples` = 20–40 samples of continuous idle-candidate status at 30–60s cadence (≈15–20 min); wake trigger = **single sample**, no dwell required (asymmetric — matches VMware DPM's own default philosophy).

**Acceptance test**: a host must NOT be powered down after a single idle sample; a host must be woken within one polling cycle of a high-water-mark breach.

---

### SHOULD HAVE #6 — Failure-during-consolidation handling
Subscribe to hypervisor HA/failure events during any active migration/consolidation window. On host failure: immediately re-run the placement optimizer excluding the failed host, treat all VMs that were on it as top-priority (not subject to the normal dwell/threshold gating), and log the incident.

### SHOULD HAVE #7 — Thermal-headroom cross-wiring
Before finalizing any consolidation plan, call `GET /api/thermos/headroom/:rackId`. If `status !== "ok"` for the target rack, exclude that rack's hosts from the candidate target list for this cycle.

### SHOULD HAVE #8 — Container/Kubernetes telemetry support
Add a second telemetry adapter (`telemetry/k8sAdapter.ts`) polling the Kubernetes metrics-server (`/apis/metrics.k8s.io/v1beta1/nodes`) and normalize into the same `HostUtilizationState` schema as the hypervisor adapter, so the rest of the pipeline (threshold engine, optimizer) is adapter-agnostic.

---

## 4. GridSync — Implementation Methodology

### MUST HAVE #6 — Explicit workload-classification criteria with safe default
Reuse the shared `WorkloadTag` contract exactly as PowerPrune does, keyed by `jobId` instead of `vmId`. Same default: unclassified = `protected`.

### MUST HAVE #7 — Hard maximum-delay deadline per deferrable job

```typescript
interface DeferrableJob {
  jobId: string;
  submittedAt: string;
  maxDelayMinutes: number;
  deadline: string; // = submittedAt + maxDelayMinutes
}
```
**Rule**: scheduler must force-run any job where `now >= deadline`, regardless of current carbon state. Implement as a priority queue sorted by `deadline ascending`; a cron/interval check (every 1–5 min) force-releases anything past its deadline.

### MUST HAVE #8 — Documented average-vs-marginal carbon-signal justification

```typescript
// GET /api/gridsync/signal-info
{ type: "average", provider: "electricitymaps", methodology: "flow-traced",
  rationale: "Matches Google CICS's own data source; average/flow-traced is the accounting standard; marginal signals disagree in direction across many grids per peer-reviewed comparison." }
```
Implementation: hardcode this as a config object, not a hidden default — it should be visible in an admin/about panel and in code comments at the top of `grid/client.ts`. Leave a `signalType` config flag (`"average" | "marginal"`) even though only `"average"` is implemented now, so the future multi-provider item (Section 8) has a clean extension point.

### MUST HAVE #9 — Cross-wire with PowerPrune's capacity state

```
before scheduling deferrableJob into window W:
    forecast = GET /api/powerprune/capacity-forecast?start=W.start&end=W.end
    if forecast.availableCpuCapacity < job.requiredCapacity:
        if forecast.standbyHostCount > 0 and W.start - now > forecast.estimatedWakeLatencySeconds:
            emit "gridsync.prewake.requested" { targetTime: W.start - forecast.estimatedWakeLatencySeconds }
            proceed with W
        else:
            pick next-best window from the ranked carbon-intensity list, repeat check
    else:
        proceed with W
```

### Core scheduling algorithm (Google CICS "capacity-curve" pattern — implements the base mechanism all the above build on)

```
1. fetch 48h carbon-intensity forecast from Electricity Maps
2. bucket into hourly windows; rank ascending by intensity
3. for each hour, compute flexibleCapacityCap:
     if intensity < greenThreshold: cap = 100%
     elif intensity > dirtyThreshold: cap = floorCapPercent (e.g. 50%)
     else: cap = linear interpolation between floorCapPercent and 100%
   NOTE: protected/non-deferrable workloads are NEVER subject to this cap
4. deferrable jobs consume from the flexible-capacity pool for their assigned hour;
   if a hour's pool is full, push job to next-best remaining hour within its deadline
5. if no hour before deadline has room -> force-run at deadline (see MUST HAVE #7)
```

### SHOULD HAVE #10 — Ingest forecast (not just real-time)
Add `grid/forecastClient.ts` calling Electricity Maps' forecast endpoint on a 1–4 hour refresh cycle; feed into the capacity-curve algorithm above instead of only real-time intensity.

### SHOULD HAVE #11 — Hysteresis/smoothing on carbon-state signal
```
smoothedIntensity = movingAverage(last 3 samples)
onlyChangeGreenDirtyClassification if smoothedIntensity crosses threshold band
    by more than bandMarginPercent (e.g. 10%) for >= 2 consecutive samples
```

### SHOULD HAVE #12 — Electricity-price signal alongside carbon
```
score(hour) = w_carbon * carbonRank(hour) + w_price * priceRank(hour)   // w_carbon=0.7, w_price=0.3 default
```
Rank hours by this combined score instead of carbon alone when a price feed is available; fall back to carbon-only ranking if the price API is unreachable.

---

## 5. CoolSense — Implementation Methodology

### MUST HAVE #10 — Add differential-pressure sensing

```typescript
interface PressureReading { loopId: string; timestamp: string; differentialKPa: number; absoluteKPa: number; }
```
Ingest on the same pipeline/cadence as existing flow sensors (1–5 min sampling). Feed into the same baseline/Z-score engine described below as an additional signal channel.

### MUST HAVE #11 — Add humidity sensing
```typescript
interface HumidityReading { zoneId: string; timestamp: string; relativeHumidityPct: number; }
```
Facility/zone-level granularity is sufficient — does not need per-rack resolution.

### MUST HAVE #12 — Per-rack baseline + peer-rack comparison, cross-wired with PowerPrune

```
1. Bucket time into "load buckets" using PowerPrune's per-rack utilization signal:
     low / medium / high (tertiles of historical utilization)
2. baseline(rack, signal, loadBucket) = { mean, std } computed over trailing 7 days,
     only using samples from matching loadBucket
3. z(rack, signal, t) = (value(t) - baseline.mean) / baseline.std
4. peerZ(rack, t) = z(rack,t) - average(z(peerRacksInSameLoadBucket, t))
5. anomaly flagged if:
     z(flow) < -2.5  AND  |peerZ(flow)| > 2.0   AND  PowerPrune utilization delta for this rack
        is within its own normal range (i.e., NOT explained by a workload change)
```
This directly implements "distinguish a leak from normal workload-driven variation" — the flow drop must be unexplained by workload before it counts as a leak signal.

### MUST HAVE #13 — Explicit maintenance-mode suppression
```typescript
interface MaintenanceWindow { loopId: string; start: string; end: string; operatorId: string; }
// POST /api/coolsense/maintenance-mode
```
Anomaly engine checks active windows before raising an alert (still logs the raw anomaly for audit, but suppresses the notification/escalation).

### SHOULD HAVE #14 — Physical leak-detection cable/point sensors as backstop
```typescript
interface PointSensorReading { sensorId: string; loopId: string; timestamp: string; wet: boolean; }
```
Any `wet: true` reading bypasses the statistical pipeline entirely and raises a Critical alert immediately — this is a hard trip-wire, not a Z-score input.

### SHOULD HAVE #15 — Sensor-failure/drift plausibility checks
```
flag sensor_fault if:
    reading is flatlined (variance == 0) for > 2 hours, OR
    reading outside physically valid bounds (e.g., flow < 0, flow > ratedMaxFlow), OR
    reading missing for > 3 consecutive expected samples
```
A `sensor_fault` flag suppresses that signal from the anomaly engine (does not count as "no anomaly" — surfaces a separate "sensor needs attention" alert instead).

### SHOULD HAVE #16 — Cross-wiring with ThermOS for combined cooling-performance estimate
```
coolingPerformance(rack, t) = flow(rack,t) * specificHeatConstant * (T_return(rack,t) - T_supply(rack,t))
```
Pull `T_return`/`T_supply` from ThermOS's existing per-rack temperature feed rather than adding new sensors.

---

## 6. NetPulse — Implementation Methodology

### MUST HAVE #14 — Flow-level ("elephant flow") detection

**Data collection**: poll edge-switch flow tables every 5–10s via sFlow/NetFlow/IPFIX (or SNMP flow-stats extension where that's all the switch supports).

```typescript
interface Flow {
  srcIp: string; dstIp: string; srcPort: number; dstPort: number; proto: string;
  bytesLastInterval: number; firstSeen: string; lastSeen: string; isElephant: boolean;
}
```
```
isElephant = bytesLastInterval > elephantThresholdBytes   // default ~10MB/interval, tune per fabric
             AND (now - firstSeen) > minDurationSeconds     // default 10s
```

### MUST HAVE #15 — Dwell-time/hysteresis before any reroute
```
congestionConfirmed(link) =
    utilization(link) > congestionThresholdPct (default 80%)
    for >= dwellTimeSeconds consecutively (default 30-60s)
onRerouteExecuted(link, flow):
    startCooldown(link, flow, cooldownSeconds = 300)   // no repeat reroute of same flow/link for 5 min
```

### MUST HAVE #16 — Explicit fail-safe-open controller/optimizer failure story

Architectural rule, not just code: NetPulse's optimizer only ever **adds a preference weight on top of** the existing loop-free routing (BGP/ECMP) — it never replaces or removes the default path.
```
watchdog: if optimizerService.lastHeartbeat > healthCheckTimeoutSeconds ago:
    switch-side agent reverts any active path-preference overrides to default ECMP automatically
```

### MUST HAVE #17 — Scope automatic rerouting to the narrow, pre-validated case
```
autoReroute(flow) allowed only if ALL true:
    flow.isElephant == true
    flow.latencySensitive == false        // from NetPulse <- PowerPrune cross-wire, SHOULD HAVE #21
    congestionConfirmed(flow.currentLink) == true
    exists altPath with utilization < altPathThresholdPct (default 60%)
else: recommend only, require operator approval via UI action
```

### SHOULD HAVE #18 — Packet-loss and queue-depth telemetry
Add these as additional fields on the existing link-utilization telemetry record; use as an OR condition alongside utilization in `congestionConfirmed()` — i.e., sustained high queue depth can also confirm congestion even if raw utilization looks borderline.

### SHOULD HAVE #19 — Automatic LLDP-based topology discovery
Poll LLDP neighbor tables per switch on a slower interval (e.g., every 5 min — topology doesn't change often); build/update the network graph automatically instead of a manually maintained config file.

### SHOULD HAVE #20 — Explicit SNMP-fallback telemetry path
```
telemetryClient.connect(switch):
    try streamingTelemetry.subscribe(switch)   // gNMI/gRPC
    catch (unsupported): fallback to snmpPoller.poll(switch, intervalSeconds=15)
```

### SHOULD HAVE #21 — Latency-sensitivity tagging cross-wired with PowerPrune
Map each flow's source/destination IP to its owning VM (via a simple IP→VM lookup table synced from the hypervisor), then call PowerPrune's `WorkloadTag` API for that VM to populate `flow.latencySensitive = (classification !== "deferrable")`.

---

## 7. ThermOS — Implementation Methodology

### MUST HAVE #18 — Add uncertainty bands to predictions

**Simplest implementable approach — MC Dropout ensemble**:
```
run N=5 forward passes of the existing prediction model with dropout active at inference
mean_prediction = average(N outputs)
std_prediction  = stddev(N outputs)
confidenceBand  = [mean - 1.96*std, mean + 1.96*std]   // ~95% CI
```
(Alternative if the model architecture doesn't support dropout-at-inference easily: switch the output layer to quantile regression, predicting p10/p50/p90 directly — more work, more principled; use MC Dropout first to ship quickly.)

### MUST HAVE #19 — Wire IT load/power telemetry (from PowerPrune) into the thermal model
```typescript
interface ThermalFeatureVector {
  rackId: string; timestamp: string;
  tempGrid: number[][];         // existing 8x8 heatmap
  humidity: number;
  workloadUtil: number;         // <- from PowerPrune, joined by rackId + nearest timestamp
  powerDrawWatts: number;       // <- from PowerPrune
}
```
Add a join step in the feature-preparation pipeline: for every thermal sample timestamp, look up PowerPrune's most recent utilization/power reading for the same rack (tolerate up to 1 sampling-interval staleness).

### MUST HAVE #20 — Move from pure ML to a hybrid physics+ML core

**Physics-lite backbone (RC thermal model)**:
```
T_predicted(t+dt) = T(t) + (dt/RC) * (Q_in(t) - Q_out(t))
   Q_in  ≈ powerDrawWatts(t)                       // heat generated
   Q_out ≈ coolingCapacity * (T(t) - T_supply(t))  // heat removed, depends on airflow/cooling
   R, C  = calibrated per-rack thermal resistance/capacitance constants (fit from historical data)
```
**ML residual correction**:
```
residual(t) = T_actual(t) - T_physics_predicted(t)
train small model (ConvLSTM or simple regressor) to predict residual(t+dt) from recent history
final_prediction(t+dt) = T_physics_predicted(t+dt) + ML_residual_predicted(t+dt)
```
This is the standard physics-informed ML (PIML) pattern — ship the physics core alone first (it needs no training data), add the ML correction once enough historical residuals exist to train on.

### MUST HAVE #21 — Add basic airflow sensing
Shares the exact `PressureReading` schema and ingestion pipeline built for CoolSense (Section 5, MUST HAVE #10) — one differential-pressure sensor type, two consumers. Airflow estimate from pressure:
```
airflowEstimate = calibrationConstant * sqrt(differentialKPa)   // fan-law derived relationship
```

### MUST HAVE #22 — Add supervised (human-approved) closed-loop control
```typescript
interface ActionRecommendation {
  id: string; type: "adjust_setpoint" | "adjust_fan_speed" | "defer_job";
  rackId: string; magnitude: number; predictedBenefit: string;
  status: "pending" | "approved" | "rejected" | "auto_executed";
}
```
UI: an approval queue. **Trust ladder**: after `M` consecutive operator approvals of the same `type` with no overrides/reversals, surface a toggle offering "auto-execute this action type going forward" — never auto-enable it silently.

### SHOULD HAVE #23 — Upgrade plain LSTM to ConvLSTM
Replace the flat-vector LSTM input with a proper `(batch, time, height, width, channels)` tensor over the 8x8 grid, using ConvLSTM2D layers so spatial neighbor relationships are learned, not discarded. Also: in the UI/data model, explicitly flag which grid cells are real sensor readings vs. spatially interpolated (Kriging) values — don't let them look identical.

### SHOULD HAVE #24 — Thermal zoning and adaptive setpoints
Cluster racks into zones based on measured airflow/thermal coupling (e.g., correlation of temperature deltas between racks); allow a per-zone setpoint rather than one facility-wide setpoint, feeding into the same `ActionRecommendation` queue above.

### SHOULD HAVE #25 — Predictive maintenance for cooling equipment
```
track fan/pump runHours and (if available) current-draw signature over time
flag maintenance_due if runHours > ratedServiceInterval
   OR current-draw trend deviates from its own historical baseline by > X% (simple trend/Z-score, same pattern as CoolSense's sensor-drift check)
```

---

## 8. MODIFY Items (ThermOS) — Documentation-Only Changes

These require no code — only copy/documentation edits, but should be done in the same PR pass as the MUST HAVE items so the pitch deck and code comments stay consistent:

1. Find-and-replace `"horizontal integration"` → `"cross-layer, hierarchical co-optimization"` across README, pitch deck, and code comments.
2. Update ThermOS's product description from `"a prediction model with a dashboard"` → `"a Physics + Data + Control system"` — this should be literally true once MUST HAVE #20 and #22 ship (physics core + ML correction + supervised control loop), so sequence this copy change after those two are done, not before.

---

## 9. Build Sequencing (Claude Code should implement in this order)

```
Phase 0 — Shared infrastructure
  - shared/contracts/* (Section 2)
  - shared/classification/* (reused by PowerPrune, GridSync, NetPulse)

Phase 1 — PowerPrune MUST HAVE #1-#5
  (Everything else depends on PowerPrune's workload classification + capacity signal)

Phase 2 — ThermOS MUST HAVE #18, #19, #20, #21
  (CoolSense's SHOULD HAVE #16 and PowerPrune's SHOULD HAVE #7 depend on ThermOS's headroom/temp feed)

Phase 3 — GridSync MUST HAVE #6-#9
  (Depends on PowerPrune's capacity-forecast API from Phase 1)

Phase 4 — CoolSense MUST HAVE #10-#13
  (MUST HAVE #12 depends on PowerPrune's per-rack utilization signal from Phase 1)

Phase 5 — NetPulse MUST HAVE #14-#17
  (MUST HAVE #17's non-latency-sensitive check depends on PowerPrune classification from Phase 1)

Phase 6 — ThermOS MUST HAVE #22
  (Depends on the physics+ML core from Phase 2 being in place)

Phase 7 — All SHOULD HAVE items, in any order
  (Sections 3-7's SHOULD HAVE items are all cross-wiring on top of an already-working MUST HAVE base)

Phase 8 — MODIFY documentation changes (Section 8)

Phase 9 — FUTURE items (out of current build scope; do not implement without an explicit go-ahead —
  each has a stated precondition, e.g. "once sufficient historical data exists")
```

**Note on Phase 1 priority**: PowerPrune is the critical-path module. Three other modules' MUST HAVE items (GridSync #9, CoolSense #12, NetPulse #17) directly depend on PowerPrune's Phase 1 output. Do not start Phases 3–5 in parallel with Phase 1 unless you're willing to stub PowerPrune's API with fixed test data first.

---

## 10. Acceptance Test Checklist (run before considering a module "done")

**PowerPrune**
- [ ] Adaptive threshold changes when synthetic variance changes (not fixed at 15%)
- [ ] A memory-bound-but-CPU-idle host is never flagged idle-candidate
- [ ] A migration with poor cost/benefit ratio is blocked (`proceed=false`)
- [ ] An untagged VM never appears in the consolidation candidate list
- [ ] Powering down never drops capacity below `minRedundancy`
- [ ] Host power-down requires sustained dwell; wake is near-immediate

**GridSync**
- [ ] An untagged job defaults to protected and is never delayed
- [ ] A deferrable job force-runs at its deadline even if the grid is still dirty
- [ ] The signal-type endpoint returns `"average"` with a stated rationale
- [ ] Scheduling into a window with insufficient PowerPrune-reported capacity either triggers a pre-wake request or reschedules

**CoolSense**
- [ ] A flow drop that coincides with a documented workload drop does NOT raise an alert
- [ ] A flow drop with no corresponding workload change DOES raise an alert
- [ ] Alerts are suppressed during an active, operator-declared maintenance window
- [ ] A flatlined sensor raises a `sensor_fault`, not a false "all clear"

**NetPulse**
- [ ] A single congested sample does not trigger a reroute (dwell-time enforced)
- [ ] A confirmed elephant-flow collision on non-latency-sensitive traffic can auto-reroute
- [ ] A latency-tagged flow is never auto-rerouted
- [ ] If the optimizer service is down, traffic still flows via default ECMP/BGP (fail-safe-open)

**ThermOS**
- [ ] Every prediction ships with a confidence band, not a bare point estimate
- [ ] The physics-lite core alone (no ML) produces a plausible prediction with zero training data
- [ ] An `ActionRecommendation` requires explicit approval before execution, every time, until the trust-ladder toggle is explicitly enabled by an operator

---

## Appendix — Quick Reference: All 22 MUST HAVE Items by File Location

| # | Module | Item | Primary file(s) |
|---|--------|------|------------------|
| 1 | PowerPrune | Adaptive multi-resource threshold | `powerprune/threshold/mad.ts` |
| 2 | PowerPrune | Migration-cost check | `powerprune/consolidation/migrationCost.ts` |
| 3 | PowerPrune | Workload classification | `shared/classification/*`, `powerprune/consolidation/optimizer.ts` |
| 4 | PowerPrune | Redundancy-aware placement | `powerprune/consolidation/optimizer.ts` |
| 5 | PowerPrune | Asymmetric dwell-time/wake | `powerprune/power/dwellStateMachine.ts` |
| 6 | GridSync | Workload classification | `shared/classification/*`, `gridsync/jobs/classify.ts` |
| 7 | GridSync | Max-delay deadline | `gridsync/jobs/deadline.ts` |
| 8 | GridSync | Signal-type justification | `gridsync/grid/client.ts` |
| 9 | GridSync | Cross-wire PowerPrune capacity | `gridsync/scheduler/capacityCheck.ts` |
| 10 | CoolSense | Differential-pressure sensing | `coolsense/sensors/pressure.ts` |
| 11 | CoolSense | Humidity sensing | `coolsense/sensors/humidity.ts` |
| 12 | CoolSense | Per-rack baseline + peer comparison | `coolsense/baseline/*` |
| 13 | CoolSense | Maintenance-mode suppression | `coolsense/anomaly/maintenanceMode.ts` |
| 14 | NetPulse | Elephant-flow detection | `netpulse/flow/detector.ts` |
| 15 | NetPulse | Dwell-time/hysteresis | `netpulse/congestion/dwell.ts` |
| 16 | NetPulse | Fail-safe-open story | `netpulse/routing/watchdog.ts` |
| 17 | NetPulse | Narrow auto-reroute scope | `netpulse/routing/autoReroute.ts` |
| 18 | ThermOS | Uncertainty bands | `thermos/model/uncertainty.ts` |
| 19 | ThermOS | Wire PowerPrune telemetry | `thermos/model/featurePipeline.ts` |
| 20 | ThermOS | Hybrid physics+ML core | `thermos/model/physicsCore.ts`, `mlResidual.ts` |
| 21 | ThermOS | Basic airflow sensing | `thermos/sensors/airflow.ts` (shares `coolsense/sensors/pressure.ts`) |
| 22 | ThermOS | Supervised closed-loop control | `thermos/control/actionQueue.ts` |
