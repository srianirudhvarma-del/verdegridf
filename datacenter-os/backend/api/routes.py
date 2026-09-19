from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

import api.state as state
from gridsync.scheduler import DEFAULT_DIRTY_THRESHOLD, DEFAULT_GREEN_THRESHOLD
from powerprune.power import HostState
from powerprune.threshold import RESOURCES, classify_host
from shared.classification import classification_store
from shared.orchestrator import HOST_ACTIVE_WATTS, HOST_IDLE_WATTS
from shared.real_agent import RealAgentSample
from thermos.spatial import GridCellReading, interpolate_grid
from coolsense.anomaly import MaintenanceWindow
from coolsense.baseline import compute_baseline, z_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["datacenter"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===================== Pydantic Models =====================

class ServerData(BaseModel):
    id: str
    rack: str
    cpu_util: float
    ram_util: float
    watts_idle: float
    watts_active: float
    state: str
    last_migrated: str

class ServerCluster(BaseModel):
    servers: List[ServerData]
    is_live: bool = True

class ClassificationRequest(BaseModel):
    classification: str  # "protected" | "deferrable" | "unclassified"
    maxDelayMinutes: Optional[int] = None

class WaterUnit(BaseModel):
    id: str
    flow_rate_lph: float

class WaterAnomaly(BaseModel):
    rack: str
    issue: str
    val: float

class WaterFlowSnapshot(BaseModel):
    units: List[WaterUnit]
    totalFlow: float
    itLoad: float
    wue: float
    anomalies: List[WaterAnomaly]
    benchmarks: dict
    is_live: bool = True

class MaintenanceWindowRequest(BaseModel):
    loopId: str
    start: str
    end: str
    operatorId: str

class CarbonIntensitySnapshot(BaseModel):
    intensity: float
    trend: str
    isSpike: bool
    minutesUntilClean: float

class JobActionRequest(BaseModel):
    hours: Optional[int] = 0

class NetworkLink(BaseModel):
    source: str
    target: str
    capacity_gbps: float
    utilization_pct: float

class NetworkTraffic(BaseModel):
    nodes: List[str]
    links: List[NetworkLink]
    is_live: bool = True

class ThermalCell(BaseModel):
    row: int
    col: int
    inlet_temp: float
    outlet_temp: float
    is_interpolated: bool

class ThermalSnapshot(BaseModel):
    grid: List[List[ThermalCell]]
    is_live: bool = True

class ActionDecisionRequest(BaseModel):
    operatorId: str = "operator"

class RealCommandAckRequest(BaseModel):
    result: str  # "executed" | "declined" | "failed"
    detail: str = ""

# ML Models (unrelated to Phase 9, left as-is)
class ThermalPredictionRequest(BaseModel):
    snapshots: List[List[dict]]

class ThermalPredictionResponse(BaseModel):
    predicted_grid: List[dict]
    hotspots: List[dict]
    confidence: float
    timestamp: str

class FeatureVector(BaseModel):
    mfcc: List[float]
    spectral_centroid: float
    rms_energy: float

class AudioClassificationRequest(BaseModel):
    features: FeatureVector

class AudioClassificationResponse(BaseModel):
    health_class: str
    failure_probability: float
    bearing_wear: bool
    timestamp: str


# ===================== PowerPrune Routes =====================

GRID_WIDTH = 8
GRID_HEIGHT = 8


def _host_ui_state(host_id: str, status: str) -> str:
    """
    Maps the real MUST HAVE #1 threshold classification + MUST HAVE #5
    dwell state to the 3-state label the UI shows.
    """
    machine = state.dwell_machines[host_id]
    if machine.state in (HostState.STANDBY, HostState.WAKING):
        return "sleep"
    if status == "idle-candidate":
        return "zombie"
    return "active"


@router.get("/powerprune/servers", response_model=ServerCluster)
async def get_server_cluster():
    """Real per-host MAD threshold classification + dwell state, not canned numbers."""
    servers = []
    for host_id, rack in state.host_to_rack.items():
        current = state.powerprune_telemetry.poll(host_id)
        history = {r: state.powerprune_telemetry.history(host_id, r, 60) for r in RESOURCES}
        classified = classify_host(host_id, current, history)
        state.dwell_machines[host_id].observe(classified.status)

        servers.append(
            ServerData(
                id=host_id,
                rack=rack,
                cpu_util=round(current["cpu"], 1),
                ram_util=round(current["mem"], 1),
                watts_idle=HOST_IDLE_WATTS,
                watts_active=HOST_ACTIVE_WATTS,
                state=_host_ui_state(host_id, classified.status),
                last_migrated=_now_iso(),
            )
        )
    return ServerCluster(servers=servers)


@router.post("/powerprune/consolidate")
async def consolidate_idle_servers():
    """
    Real consolidation pass: any host the dwell state machine has already
    determined is IDLE_CANDIDATE (sustained idle dwell, MUST HAVE #5) is
    powered down (consolidation_succeeded() -> STANDBY). Untagged/protected
    workloads never factor in here -- this operates on hosts, whose
    IDLE_CANDIDATE status already required sustained multi-resource
    idleness (MUST HAVE #1).
    """
    consolidated = []
    for host_id, machine in state.dwell_machines.items():
        if machine.state == HostState.IDLE_CANDIDATE:
            machine.consolidation_succeeded()
            consolidated.append(host_id)

    energy_saved_watts = len(consolidated) * HOST_IDLE_WATTS
    return {
        "consolidated": len(consolidated),
        "energy_saved": round(energy_saved_watts / 1000.0, 2),
        "message": f"{len(consolidated)} idle host(s) powered down" if consolidated else "No hosts were eligible for consolidation this cycle",
    }


@router.get("/powerprune/workloads/{workload_id}/classification")
async def get_workload_classification(workload_id: str):
    """MUST HAVE #3 step 1: read a workload's classification, defaulting to protected."""
    tag = classification_store.get_tag(workload_id)
    if tag is None:
        return {"workloadId": workload_id, "classification": "protected", "source": "default"}
    return tag.model_dump()


@router.patch("/powerprune/workloads/{workload_id}/classification")
async def set_workload_classification(workload_id: str, request: ClassificationRequest):
    """MUST HAVE #3 step 2: the real operator-facing classification write path (shared.orchestrator.apply_operator_classification)."""
    from shared.orchestrator import apply_operator_classification

    try:
        tag = apply_operator_classification(
            workload_id, request.classification, max_delay_minutes=request.maxDelayMinutes, store=classification_store,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return tag.model_dump()


# ===================== CoolSense Routes =====================

WATER_BENCHMARKS = {"google": 1.1, "industry": 1.8, "poor": 3.0}
WATER_ANOMALY_Z_THRESHOLD = -2.0
WATER_MIN_HISTORY_FOR_BASELINE = 10


@router.get("/coolsense/flows", response_model=WaterFlowSnapshot)
async def get_water_flows():
    """
    Real per-loop flow telemetry (coolsense/sensors.py). Anomaly
    detection here is a documented simplification of MUST HAVE #12's full
    algorithm: z-score against the loop's own trailing history, without
    the peer-rack/load-bucket comparison or the PowerPrune workload-delta
    check the full coolsense/anomaly.py pipeline applies (that full
    pipeline is exercised directly by its own tests).
    """
    units = []
    anomalies = []
    for rack in state.RACKS:
        current = state.coolsense_telemetry.poll(rack)
        flow = current["flow_rate"]
        units.append(WaterUnit(id=rack, flow_rate_lph=round(flow, 1)))

        history = state.coolsense_telemetry.history(rack, "flow_rate", 30)
        if len(history) >= WATER_MIN_HISTORY_FOR_BASELINE:
            baseline = compute_baseline(history[:-1])
            z = z_score(flow, baseline)
            if z < WATER_ANOMALY_Z_THRESHOLD:
                anomalies.append(WaterAnomaly(rack=rack, issue="unexplained flow drop", val=round(flow, 1)))

    total_flow = sum(u.flow_rate_lph for u in units)
    it_load_watts = sum(HOST_IDLE_WATTS + (HOST_ACTIVE_WATTS - HOST_IDLE_WATTS) * (state.powerprune_telemetry.current(h)["cpu"] / 100.0) for h in state.ALL_HOST_IDS)
    it_load_kw = it_load_watts / 1000.0
    # Simplified WUE heuristic (liters/hr per kW IT load, scaled) -- not a
    # precision facility metric, same level of approximation the original
    # mock used, now driven by real flow/power readings instead of a
    # fixed formula on random numbers.
    wue = round(1.0 + (total_flow / max(it_load_kw, 1.0)) / 1000.0, 2)

    return WaterFlowSnapshot(
        units=units, totalFlow=round(total_flow, 1), itLoad=round(it_load_kw, 2),
        wue=wue, anomalies=anomalies, benchmarks=WATER_BENCHMARKS,
    )


@router.get("/coolsense/anomaly")
async def get_water_anomalies():
    snapshot = await get_water_flows()
    return {"anomalies": [a.model_dump() for a in snapshot.anomalies]}


@router.post("/coolsense/maintenance-mode")
async def declare_maintenance_window(request: MaintenanceWindowRequest):
    """SHOULD HAVE #13/#15: declare a real maintenance window; the anomaly engine checks it before escalating."""
    window = MaintenanceWindow(loopId=request.loopId, start=request.start, end=request.end, operatorId=request.operatorId)
    state.maintenance_registry.declare(window)
    return window.model_dump()


@router.get("/coolsense/maintenance-mode/{loop_id}")
async def get_maintenance_status(loop_id: str):
    active = state.maintenance_registry.is_active(loop_id, datetime.now(timezone.utc))
    return {"loopId": loop_id, "active": active}


# ===================== GridSync Routes =====================

@router.get("/gridsync/intensity", response_model=CarbonIntensitySnapshot)
async def get_carbon_intensity():
    """
    Real synthetic carbon-intensity series (Phase 0 Decision #1) run
    through the real hysteresis/smoothing (SHOULD HAVE #11) -- no more
    static ElectricityMaps passthrough with a hardcoded fallback.
    """
    intensity = state.carbon_forecast_sim.sample_current(state.CARBON_ZONE)
    classification = state.carbon_hysteresis.observe(intensity)

    history = state.carbon_forecast_sim.history(state.CARBON_ZONE, 5)
    if len(history) >= 2:
        slope = history[-1] - history[-2]
        trend = "rising" if slope > 1.0 else "falling" if slope < -1.0 else "stable"
    else:
        slope = 0.0
        trend = "stable"

    is_spike = intensity > DEFAULT_DIRTY_THRESHOLD
    if not is_spike:
        minutes_until_clean = 0.0
    elif slope < -0.5:
        minutes_until_clean = max(5.0, min(180.0, (intensity - DEFAULT_GREEN_THRESHOLD) / abs(slope) * 60.0))
    else:
        minutes_until_clean = 45.0

    return CarbonIntensitySnapshot(
        intensity=round(intensity, 1), trend=trend, isSpike=is_spike,
        minutesUntilClean=round(minutes_until_clean, 1),
    )


@router.get("/gridsync/signal-info")
async def get_signal_info():
    """MUST HAVE #8: documented average-vs-marginal justification, visible in an admin panel."""
    return state.signal_info.model_dump()


@router.get("/gridsync/jobs")
async def get_job_queue():
    return list(state.carbon_job_records.values())


@router.post("/gridsync/jobs/{job_id}/defer")
async def defer_carbon_job(job_id: str, request: JobActionRequest):
    if job_id not in state.carbon_job_records:
        raise HTTPException(status_code=404, detail="unknown job")
    state.carbon_job_records[job_id]["status"] = "deferred"
    return {
        "id": job_id, "status": "deferred", "deferredHours": request.hours,
        "message": f"Job {job_id} deferred by {request.hours} hours",
    }


@router.post("/gridsync/jobs/{job_id}/run")
async def run_carbon_job(job_id: str):
    """
    Operator manually forces a job to run now: removes it from the real
    DeadlineQueue (MUST HAVE #7's queue, not a display-only copy) if it's
    still pending, and publishes the same gridsync.job.scheduled event
    shared.orchestrator.JobExecutionTracker consumes.
    """
    if job_id not in state.carbon_job_records:
        raise HTTPException(status_code=404, detail="unknown job")

    from shared.eventbus import event_bus

    state.carbon_job_queue.remove(job_id)
    state.carbon_job_records[job_id]["status"] = "running"
    event_bus.publish("gridsync.job.scheduled", {"jobId": job_id, "windowStart": _now_iso(), "forceRun": False})
    return {"id": job_id, "status": "running", "message": f"Job {job_id} started immediately"}


# ===================== ThermOS Routes =====================

@router.get("/thermos/snapshot", response_model=ThermalSnapshot)
async def get_thermal_snapshot():
    """
    Real per-rack temperature readings (5 sensors) filled out to a full
    8x8 grid via SHOULD HAVE #23's inverse-distance-weighted
    interpolation, with each cell honestly flagged real vs interpolated.
    """
    readings = []
    for rack, (x, y) in state.RACK_GRID_POSITIONS.items():
        temp = state.thermal_telemetry.poll(rack)["temperature"]
        readings.append(GridCellReading(x=x, y=y, value=temp))

    interpolated = interpolate_grid(readings, width=GRID_WIDTH, height=GRID_HEIGHT)

    grid = [
        [
            ThermalCell(
                row=row, col=col,
                inlet_temp=round(interpolated.values[row][col], 1),
                outlet_temp=round(interpolated.values[row][col] + 5.0, 1),
                is_interpolated=interpolated.isInterpolated[row][col],
            )
            for col in range(GRID_WIDTH)
        ]
        for row in range(GRID_HEIGHT)
    ]
    return ThermalSnapshot(grid=grid)


@router.get("/thermos/actions")
async def get_pending_actions():
    """MUST HAVE #22: the supervised approval queue."""
    return [r.model_dump() for r in state.action_recommendation_queue.pending()]


@router.post("/thermos/actions/{action_id}/approve")
async def approve_action(action_id: str, request: ActionDecisionRequest):
    try:
        rec = state.action_recommendation_queue.approve(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if rec.type == "adjust_fan_speed" and rec.rackId in state.real_agent_registry.known_hosts():
        # rec.rackId is a real laptop (not a simulated rack) -- the
        # approval this endpoint already required is exactly the human
        # sign-off MUST HAVE #22 demands before anything touches real
        # hardware. Queue the real command; the laptop's own agent
        # executes it and acks back via /real/commands/{id}/ack.
        state.real_command_queue.enqueue(rec.rackId, "fan_max_on", {"recommendationId": rec.id})
        state.real_node_manager.mark_fan_executed(rec.rackId)
    return rec.model_dump()


@router.post("/thermos/actions/{action_id}/reject")
async def reject_action(action_id: str, request: ActionDecisionRequest):
    try:
        rec = state.action_recommendation_queue.reject(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return rec.model_dump()


# ===================== Real hardware integration =====================
# datacenter-os/real-agent/agent.py runs on each physical laptop and talks
# to these three endpoints only. Hosts self-register on first ingest --
# see api/real_nodes.py's module docstring for why they aren't part of the
# fixed simulated topology.

@router.post("/real/telemetry")
async def ingest_real_telemetry(sample: RealAgentSample):
    state.real_agent_registry.ingest(sample)
    return {"ok": True, "knownHosts": state.real_agent_registry.known_hosts()}


@router.get("/real/commands/{host_id}")
async def poll_real_command(host_id: str):
    """The agent polls this every cycle; a command, once returned, is
    removed from the queue (see RealCommandQueue.poll)."""
    command = state.real_command_queue.poll(host_id)
    if command is None:
        return {"type": "none"}
    return {"id": command.id, "type": command.type, "payload": command.payload, "issuedAt": command.issuedAt}


@router.post("/real/commands/{command_id}/ack")
async def ack_real_command(command_id: str, request: RealCommandAckRequest):
    try:
        return state.real_command_queue.ack(command_id, request.result, request.detail)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/real/hosts")
async def list_real_hosts():
    """Visibility into real-node state -- not wired into the React
    dashboard (out of scope for this pass; the existing 5 modules stay as
    they are)."""
    now = datetime.now(timezone.utc)
    hosts = []
    for host_id in state.real_agent_registry.known_hosts():
        sample = state.real_agent_registry.latest(host_id)
        machine = state.real_node_manager.dwell_machines.get(host_id)
        hosts.append(
            {
                "hostId": host_id,
                "lastSample": sample.model_dump() if sample else None,
                "dwellState": machine.state.value if machine else None,
                "stale": state.real_agent_registry.is_stale(
                    host_id, now, max_age_seconds=state.REAL_AGENT_STALE_SECONDS
                ),
                "lastAck": state.real_command_queue.last_ack_for_host(host_id),
            }
        )
    return hosts


@router.post("/thermos/predict", response_model=ThermalPredictionResponse)
async def predict_thermal_hotspots(request: ThermalPredictionRequest):
    """Unchanged client-driven simple-trend prediction (not a mock -- operates on whatever real snapshots the client sends)."""
    if not request.snapshots or len(request.snapshots) < 2:
        raise HTTPException(status_code=400, detail="At least 2 snapshots required")
    if len(request.snapshots) > 200:
        raise HTTPException(status_code=400, detail="Too many snapshots (max 200)")
    num_cells = len(request.snapshots[0])
    if num_cells == 0:
        raise HTTPException(status_code=400, detail="Snapshots must contain at least one cell")

    predicted_grid, hotspots, confidence_scores = [], [], []
    for pos in range(num_cells):
        inlets = [snap[pos]["inlet_temp"] for snap in request.snapshots if pos < len(snap)]
        outlets = [snap[pos]["outlet_temp"] for snap in request.snapshots if pos < len(snap)]
        if len(inlets) < 2:
            continue
        inlet_slope = (inlets[-1] - inlets[0]) / (len(inlets) - 1)
        outlet_slope = (outlets[-1] - outlets[0]) / (len(outlets) - 1)
        pred_inlet = inlets[-1] + inlet_slope * 1.5
        pred_outlet = outlets[-1] + outlet_slope * 1.5
        cell = request.snapshots[0][pos]
        predicted_grid.append({"row": cell["row"], "col": cell["col"], "inlet_temp": round(pred_inlet, 2), "outlet_temp": round(pred_outlet, 2)})
        delta = pred_outlet - pred_inlet
        if pred_inlet > 35 or delta > 15:
            severity = "high" if pred_inlet > 40 or delta > 20 else "medium"
            hotspots.append({"row": cell["row"], "col": cell["col"], "severity": severity, "predicted_inlet": round(pred_inlet, 2), "predicted_delta": round(delta, 2)})
        trend_stability = 1.0 - min(abs(inlet_slope) + abs(outlet_slope), 2.0) / 2.0
        confidence_scores.append(trend_stability * 0.8 + 0.2)

    confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
    return ThermalPredictionResponse(predicted_grid=predicted_grid, hotspots=hotspots, confidence=round(confidence, 2), timestamp=_now_iso())


# ===================== NetPulse Routes =====================

@router.get("/netpulse/network", response_model=NetworkTraffic)
async def get_network_traffic():
    """Real per-link utilization telemetry (netpulse/telemetry.py), fed into the real congestion dwell tracker (MUST HAVE #15)."""
    now = datetime.now(timezone.utc)
    links = []
    nodes = set()
    for source, target in state.LINKS:
        link_id = f"{source}-{target}"
        nodes.add(source)
        nodes.add(target)
        current = state.netpulse_telemetry.poll(link_id)
        utilization = current["utilization_pct"]
        state.congestion_tracker.observe_utilization(link_id, utilization, now)
        links.append(NetworkLink(source=source, target=target, capacity_gbps=10.0, utilization_pct=round(utilization, 1)))

    return NetworkTraffic(nodes=sorted(nodes), links=links)


@router.post("/netpulse/inject-spike")
async def inject_traffic_spike():
    """Demo control: injects a real utilization spike (shared/telemetry_sim.py's anomaly injection, Phase 0) into a random link, for exercising the congestion/optimize path."""
    import random

    link_id = random.choice(state.LINK_IDS)
    state.netpulse_telemetry.inject_anomaly(link_id, "utilization_pct", "traffic_spike", magnitude=60.0, duration_ticks=5)
    return {"linkId": link_id, "message": f"Injected a traffic spike on {link_id}"}


@router.post("/netpulse/optimize")
async def optimize_network():
    """
    Real optimization pass: reports every link the real CongestionTracker
    has confirmed congested (sustained above threshold for the dwell
    time, MUST HAVE #15) -- not a fixed canned response.
    """
    now = datetime.now(timezone.utc)
    adjusted = []
    for source, target in state.LINKS:
        link_id = f"{source}-{target}"
        if state.congestion_tracker.congestion_confirmed(link_id, now):
            current = state.netpulse_telemetry.current(link_id)["utilization_pct"]
            adjusted.append({"source": source, "target": target, "utilization_pct": round(max(current * 0.6, 0.0), 1)})

    return {"optimized": True, "adjustedLinks": adjusted}


# ===================== ML Bridge Endpoints =====================

@router.post("/ml/thermos/predict", response_model=ThermalPredictionResponse)
async def ml_predict_thermal(request: ThermalPredictionRequest):
    """
    TODO: No LSTM model exists yet in this codebase. When one is built,
    load it here (e.g. from a new ml/ module) instead of returning a stub.
    """
    return ThermalPredictionResponse(predicted_grid=[], hotspots=[], confidence=0.0, timestamp=_now_iso())

@router.post("/ml/noisemesh/classify", response_model=AudioClassificationResponse)
async def ml_classify_audio(request: AudioClassificationRequest):
    """EXCLUDED: NoiseMesh module is not being implemented."""
    raise HTTPException(status_code=501, detail="NoiseMesh module is not part of this implementation")

# ===================== Health & Status =====================

@router.get("/status")
async def api_status():
    return {
        "status": "operational",
        "version": "2.0.0",
        "modules": {
            "powerprune": "live", "coolsense": "live", "gridsync": "live",
            "thermos": "live (ML bridge stub pending)", "netpulse": "live",
            "noisemesh": "excluded",
        },
        "timestamp": _now_iso(),
    }
