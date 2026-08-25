# GreenCore — Consolidated Cross-Module Engineering Change List

All five modules — IdleHunter, CarbonClock, WaterWatch, LightSpeed, ThermalTrace — ranked by the same priority tiers used in each individual deep-research report.

Prepared for: Team AGASTA, Vellore Institute of Technology
Scope: Evidence-based technical review of architecture, competitive positioning, real limitations, candidate improvements, and a final V2 design recommendation.

## How to read this document

Each of GreenCore's five module reports independently ranked its own proposed changes using the same tiering:
- **MUST HAVE** — build before pitching to judges
- **SHOULD HAVE** — meaningfully strengthens the pitch
- **MODIFY** — positioning/terminology, not a technical build item
- **FUTURE** — deliberately postponed, revisit once a stated condition is met
- **DO NOT BUILD / NOT NOW** — explicit anti-scope, avoided on purpose, not forgotten

Numbering restarts within each tier. Cost/Cx: L = Low, M = Medium, H = High.

## Dashboard: items per module per tier

| Module | Must Have | Should Have | Modify | Future | Do Not Build / Not Now | Total |
|---|---|---|---|---|---|---|
| IdleHunter | 5 | 3 | 0 | 2 | 3 | 13 |
| CarbonClock | 4 | 3 | 0 | 2 | 2 | 11 |
| WaterWatch | 4 | 3 | 0 | 2 | 3 | 12 |
| LightSpeed | 4 | 4 | 0 | 2 | 3 | 13 |
| ThermalTrace | 5 | 3 | 2 | 3 | 2 | 15 |
| **TOTAL** | **22** | **16** | **2** | **11** | **13** | **64** |

---

## 1. MUST HAVE — Build Before Pitching to Judges

22 items closing a Critical gap each module's own report identified. None require new hardware categories beyond a small named sensor addition (WaterWatch, ThermalTrace); everything else is software/policy-layer over data the module already collects or can reach via an existing API.

| # | Module | Change | Rationale | Cost/Cx |
|---|---|---|---|---|
| 1 | IdleHunter | Replace the fixed 15% CPU-only threshold with an adaptive, multi-resource threshold | Static single-resource thresholds are documented as unsuitable for dynamic environments; adaptive statistics (MAD-style) are the accepted successor | L-M |
| 2 | IdleHunter | Add a migration-cost check before triggering any VM move | Live migration has a real, quantifiable energy/downtime cost; ignoring it can make a "consolidation" a net energy loss | L |
| 3 | IdleHunter | Add workload classification (protected/latency-sensitive vs. deferrable) | Without this, automated consolidation can silently touch a workload it should never have moved | L |
| 4 | IdleHunter | Add redundancy-aware placement constraints | Consolidation must never silently remove an operator's failover headroom | L-M |
| 5 | IdleHunter | Asymmetric dwell-time policy (slow to power down, fast to wake) | Matches VMware DPM's own default philosophy | L |
| 6 | CarbonClock | Define explicit workload-classification criteria with a safe (protected) default | Every credible source treats correct classification as the central design problem | L |
| 7 | CarbonClock | Add a hard maximum-delay deadline per deferrable job | Without this, a "deferred" job can be delayed indefinitely if the grid stays dirty | L |
| 8 | CarbonClock | Explicitly justify the average-vs-marginal carbon-signal choice | A peer-reviewed 65-grid study found the two signals disagree in direction for most regions | L |
| 9 | CarbonClock | Cross-wire with IdleHunter's capacity state before scheduling | Prevents scheduling into a window where the needed servers have been powered down | L-M |
| 10 | WaterWatch | Add differential-pressure sensing to the detection pipeline | Pressure is a leading indicator that appears before a leak becomes visible — the single biggest, cheapest gap | L-M |
| 11 | WaterWatch | Add humidity sensing | Recent leak-forecasting research identifies humidity as one of the three strongest predictive signals | L |
| 12 | WaterWatch | Add per-rack baseline + peer-rack comparison, cross-wired with IdleHunter's workload data | Without this, normal workload-driven flow variation is indistinguishable from a genuine anomaly | L |
| 13 | WaterWatch | Add explicit maintenance-mode suppression | Scheduled maintenance produces signatures identical to a fault | L |
| 14 | LightSpeed | Add flow-level ("elephant-flow") detection alongside link-utilization monitoring | Closes the documented ECMP-collision blind spot | L-M |
| 15 | LightSpeed | Add dwell-time/hysteresis before triggering any reroute | Undamped local rerouting can push congestion to neighboring links and trigger oscillation | L |
| 16 | LightSpeed | Add an explicit fail-safe-open controller/optimizer failure story | A centralized optimization layer is a documented single point of failure | L-M |
| 17 | LightSpeed | Scope automatic rerouting to the narrow, pre-validated elephant-flow-collision case | Matches exactly how Hedera/Mahout scope automatic action | L |
| 18 | ThermalTrace | Add uncertainty bands to thermal predictions | Point estimates erode operator trust after any false alarm | L-M |
| 19 | ThermalTrace | Wire IT load/power telemetry (from IdleHunter) into the thermal model | Load-aware models show double-digit accuracy improvements in published comparisons | L |
| 20 | ThermalTrace | Move from pure ML to a hybrid physics+ML core | Pure ML risks physically implausible predictions off-distribution | M |
| 21 | ThermalTrace | Add basic airflow sensing (differential-pressure/anemometer points per aisle) | Temperature alone cannot separate an overloaded rack from a recirculation/bypass problem | L-M |
| 22 | ThermalTrace | Add supervised (human-approved) closed-loop control | Hyperscale operators keep a human in the loop even at their scale | M |

## 2. SHOULD HAVE — Strengthens the Pitch

16 Important (not Critical) items — the module is defensible to a judge without them on day one, but several are explicit cross-module wiring, the concrete evidence GreenCore is a coordinated platform.

| # | Module | Change | Rationale | Cost/Cx |
|---|---|---|---|---|
| 1 | IdleHunter | Failure-during-consolidation handling (detect + re-place) | Standard practice in HA-integrated schedulers | M |
| 2 | IdleHunter | Thermal-headroom cross-wiring with ThermalTrace | Prevents IdleHunter from creating a hotspot it cannot see | L |
| 3 | IdleHunter | Container/Kubernetes telemetry support alongside VM support | Containers are increasingly the more practical consolidation unit | M |
| 4 | CarbonClock | Ingest forecast (not just real-time) carbon-intensity data | Purely reactive scheduling cannot pre-position deferred work | L |
| 5 | CarbonClock | Hysteresis/smoothing on the carbon-state signal | Forecast noise increases scheduling volatility | L |
| 6 | CarbonClock | Electricity-price signal alongside carbon | Adds a second, tangible cost-savings metric | L-M |
| 7 | WaterWatch | Physical leak-detection cable/point sensors as a backstop | Catches slow, small leaks a statistical system might miss | L |
| 8 | WaterWatch | Sensor-failure/drift plausibility checks | Prevents false confidence from a silently broken sensor | L |
| 9 | WaterWatch | Cross-wiring with ThermalTrace for a combined cooling-performance estimate | Adds a cooling-efficiency metric at zero new hardware cost | L |
| 10 | LightSpeed | Packet-loss and queue-depth telemetry alongside utilization | Queue occupancy rises before loss occurs | L |
| 11 | LightSpeed | Automatic LLDP-based topology discovery | Manually maintained topology is error-prone and drifts | L |
| 12 | LightSpeed | Explicit SNMP-fallback telemetry path | Streaming telemetry requires switch support not universal across fleets | L-M |
| 13 | LightSpeed | Latency-sensitivity tagging, cross-wired with IdleHunter's workload classification | Ensures rerouting never touches a latency-sensitive flow | L |
| 14 | ThermalTrace | Upgrade plain LSTM to ConvLSTM; flag sensor-vs-interpolated cells clearly | A flat LSTM discards the spatial structure the 8x8 grid was built to show | L-M |
| 15 | ThermalTrace | Thermal zoning and adaptive setpoints | Cheap, high-leverage once airflow+power data exists | L-M |
| 16 | ThermalTrace | Predictive maintenance for cooling equipment (fans, pumps) | Extends component life, avoids incidents | M |

## 3. MODIFY — Positioning & Terminology

| # | Module | Change | Rationale |
|---|---|---|---|
| 1 | ThermalTrace | Reposition from "a prediction model with a dashboard" to "a Physics + Data + Control system" | Matches where the literature says the value actually is |
| 2 | ThermalTrace | Replace "horizontal integration" with "cross-layer, hierarchical co-optimization" | "Horizontal integration" is a business-strategy term, reads as weak technical vocabulary |

## 4. FUTURE — Deliberately Postponed

| # | Module | Change | Precondition to revisit |
|---|---|---|---|
| 1 | IdleHunter | ML-based load-spike forecasting | Valuable once sufficient historical telemetry exists |
| 2 | IdleHunter | DVFS/P-state tuning inside IdleHunter | Lower priority; hypervisor/CPU already handle much of this |
| 3 | CarbonClock | Multi-provider carbon-signal cross-validation (Electricity Maps + WattTime) | Strengthens robustness once core product is proven |
| 4 | CarbonClock | Demand Shaping application-level integration | Valuable once the core time-shifting mechanism is proven |
| 5 | WaterWatch | LSTM/Random-Forest predictive leak forecasting | ~87% forecasting accuracy possible once sufficient historical multi-signal data exists |
| 6 | WaterWatch | Autonomous valve/pump control | Only after a track record of accurate, trusted, alert-only detection |
| 7 | LightSpeed | Seasonal/predictive congestion forecasting (ML-based) | Needs historical flow-pattern data volume this deployment won't have at launch |
| 8 | LightSpeed | Broader SDN-controller adoption | Only after a track record of reliable, damped, flow-targeted rerouting |
| 9 | ThermalTrace | Liquid-cooling telemetry support | Only relevant if target customers adopt higher-density racks |
| 10 | ThermalTrace | Economizer/free-cooling control integration | A facility HVAC-design decision more than a software feature |
| 11 | ThermalTrace | Autonomous (non-supervised) control | Only after a track record of safe, supervised MPC-driven action exists |

## 5. DO NOT BUILD / NOT NOW — Explicit Anti-Scope

| # | Module | Capability declined | Why it's out of scope | Status |
|---|---|---|---|---|
| 1 | IdleHunter | Fleet-scale custom scheduler modeled on Google Borg/Autopilot | Requires homogeneous fleet scale and dedicated scheduling-research engineering | Do not build |
| 2 | IdleHunter | ML-based load forecasting for the initial release | Adaptive statistical thresholds already outperform static thresholds without ML | Not now |
| 3 | IdleHunter | Fully autonomous execution with no human-approval stage at launch | Even VMware's mature DPM defaults to conservative, configurable automation | Not now |
| 4 | CarbonClock | Spatial (multi-region) load shifting | Requires a multi-datacenter footprint a single low-to-mid operator does not have | Do not build (now) |
| 5 | CarbonClock | Real-time per-job AI-based scheduling optimizer | Google's own production system uses a simpler capacity-curve mechanism | Not now |
| 6 | WaterWatch | Dense in-rack liquid-cooling sensor arrays / CDU-integrated instrumentation | Assumes a liquid-cooled, high-density deployment most operators don't have | Do not build (now) |
| 7 | WaterWatch | Autonomous pump/valve/chiller control | Requires actuator integration and trust inappropriate for an alert-only V1 | Not now |
| 8 | WaterWatch | Continuous infrared-camera thermal-imaging monitoring | Documented as a periodic-inspection tool, not continuous-monitoring | Not now |
| 9 | LightSpeed | Full SDN fabric replacement (OpenFlow/Cisco ACI/VMware NSX-class) | Requires significant capital investment and a multi-month deployment project | Do not build (now) |
| 10 | LightSpeed | In-band Network Telemetry (P4-programmable switches) | Requires programmable-data-plane switch hardware most fleets don't have | Not now |
| 11 | LightSpeed | Blanket automatic rerouting triggered by aggregate utilization alone | Contradicts the literature's explicit warning about oscillation | Not now |
| 12 | ThermalTrace | Real-time/full CFD as a running product feature | Requires expert configuration and hours-to-days of compute even for a small room | Do not build |
| 13 | ThermalTrace | Autonomous reinforcement-learning control | Even Google, with a decade of data, keeps a human able to intervene | Not now |

## 6. Cross-Module Dependency Map

| Dependency | Data shared | Why it matters |
|---|---|---|
| IdleHunter → ThermalTrace | Per-server/rack IT load and power utilization | Lets ThermalTrace react to workload changes instead of only a lagging temperature symptom (ThermalTrace MUST HAVE #19) |
| ThermalTrace → IdleHunter | Per-rack/zone thermal headroom | Stops IdleHunter from consolidating into an already-constrained rack (IdleHunter SHOULD HAVE #2) |
| IdleHunter → CarbonClock | Current/planned server capacity state | Stops CarbonClock scheduling into a window where needed servers are powered down (CarbonClock MUST HAVE #9) |
| CarbonClock → IdleHunter | Upcoming deferred-job queue / scheduled execution time | Lets IdleHunter proactively wake standby capacity ahead of a scheduled batch |
| IdleHunter → WaterWatch | Per-rack workload/utilization signal | Lets WaterWatch distinguish workload-driven flow increase from a genuine leak (WaterWatch MUST HAVE #12) |
| ThermalTrace → WaterWatch | Per-rack temperature data | Enables a combined cooling-performance estimate without duplicating sensing (WaterWatch SHOULD HAVE #9) |
| IdleHunter → LightSpeed | Workload classification (latency-sensitive vs. deferrable/batch) | Ensures automatic rerouting never touches latency-sensitive traffic (LightSpeed SHOULD HAVE #13) |

**Recommended build sequencing implication**: IdleHunter's classification + multi-resource telemetry work should land early (MUST HAVE #1, #3), since four other modules depend on its workload/capacity signal. ThermalTrace's airflow/power sensing (MUST HAVE #21, #19) should land before WaterWatch's cross-wired cooling-performance estimate. None of the cross-module dependencies block a module's own MUST HAVE items — every module's Critical fixes are self-contained; only SHOULD HAVE cross-wiring items have a real ordering dependency.

## Summary

22 Critical (MUST HAVE) fixes, 16 Important (SHOULD HAVE) improvements, 2 no-cost positioning/terminology corrections (MODIFY), 11 well-justified deferred items (FUTURE), and 13 explicitly declined capabilities (DO NOT BUILD / NOT NOW) — 64 reviewed items in total. Every MUST HAVE item is a software, policy, or small-sensor-addition change over data the platform already collects or can reach cheaply — none requires hyperscale-grade infrastructure.
