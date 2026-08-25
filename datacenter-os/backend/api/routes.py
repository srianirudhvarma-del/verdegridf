from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["datacenter"])

# ===================== Pydantic Models =====================

class ServerData(BaseModel):
    id: str
    rack: str
    cpu_util: float
    ram_util: float
    watts_idle: float
    watts_active: float
    last_migrated: str

class WaterFlowData(BaseModel):
    rack_id: str
    cooling_unit: str
    flow_rate_l_hr: float
    it_load_kw: float
    timestamp: str

class CarbonIntensityData(BaseModel):
    carbonIntensity: int
    datetime: str
    zone: str
    status: str
    lastUpdated: str

class Job(BaseModel):
    id: str
    name: str
    type: str
    deferrable: bool
    estimatedDuration: int
    estimatedKwh: float
    status: str
    deferredHours: Optional[int] = None

class JobActionRequest(BaseModel):
    hours: Optional[int] = 0

class ThermalCell(BaseModel):
    id: str
    x: int
    y: int
    inlet_celsius: float
    outlet_celsius: float

class NetworkLink(BaseModel):
    source: str
    target: str
    capacity_gbps: float
    utilization_percent: float

class NetworkNode(BaseModel):
    id: str

class NetworkTraffic(BaseModel):
    nodes: List[NetworkNode]
    links: List[NetworkLink]

# ML Models
class ThermalPredictionRequest(BaseModel):
    snapshots: List[List[ThermalCell]]  # Last 20 snapshots

class ThermalPredictionResponse(BaseModel):
    predicted_grid: List[ThermalCell]
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

# ===================== IDLEhunter Routes =====================

@router.get("/idlehunter/servers", response_model=List[ServerData])
async def get_server_cluster():
    """Get current server cluster state from mock data"""
    servers = []
    for i in range(100):
        rack_label = f"{chr(65 + (i // 10))}{(i % 10) + 1}"
        cpu_util = round(20 + (i % 5) * 12 + (i % 3) * 3, 1)
        ram_util = round(15 + (i % 4) * 10 + (i % 2) * 5, 1)
        servers.append({
            "id": f"srv-{i+1}",
            "rack": rack_label,
            "cpu_util": cpu_util,
            "ram_util": ram_util,
            "watts_idle": 120.0,
            "watts_active": 280.0,
            "last_migrated": datetime.utcnow().isoformat(),
        })
    return servers

@router.post("/idlehunter/consolidate")
async def consolidate_idle_servers():
    """Simulate idle server consolidation and return energy savings."""
    return {
        "consolidated": 4,
        "energy_saved": 75.0,
        "message": "Idle servers consolidated successfully"
    }

# ===================== WaterWatch Routes =====================

@router.get("/waterwatch/flows", response_model=List[WaterFlowData])
async def get_water_flows():
    """Get current water flow data from mock data"""
    flows = []
    for idx in range(8):
        flows.append({
            "rack_id": f"Rack {chr(65 + idx)}",
            "cooling_unit": f"CU-{idx+1}",
            "flow_rate_l_hr": round(60 + idx * 15 + (idx % 3) * 8, 1),
            "it_load_kw": round(1.2 + idx * 0.3, 2),
            "timestamp": datetime.utcnow().isoformat(),
        })
    return flows

@router.get("/waterwatch/anomaly")
async def get_water_anomalies():
    """Return current water anomaly state"""
    anomalies = [
        {"rack_id": "Rack B2", "type": "leak", "severity": "medium"},
        {"rack_id": "Rack D4", "type": "flow_spike", "severity": "high"},
    ]
    return {"anomalies": anomalies}

# ===================== CarbonClock Routes =====================

@router.get("/carbonclock/intensity", response_model=CarbonIntensityData)
async def get_carbon_intensity():
    """Get current carbon intensity from ElectricityMaps API (or mock)"""
    api_key = os.getenv("ELECTRICITYMAP_API_KEY") or os.getenv("VITE_ELECTRICITY_API_KEY")
    if api_key:
        try:
            url = "https://api.electricitymap.org/v3/carbon-intensity/latest?zone=IN-SO"
            req = urllib.request.Request(url, headers={"auth-token": api_key})
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode())
                intensity = payload.get("carbonIntensity") or payload.get("carbonIntensityAverage") or 250
                return {
                    "carbonIntensity": int(intensity),
                    "datetime": payload.get("datetime", datetime.utcnow().isoformat()),
                    "zone": payload.get("zone", "IN-SO"),
                    "status": payload.get("status", "live"),
                    "lastUpdated": payload.get("datetime", datetime.utcnow().isoformat()),
                }
        except urllib.error.URLError as e:
            logger.warning("ElectricityMaps request failed (network/URL error): %s", e)
        except Exception as e:
            logger.warning("ElectricityMaps request failed unexpectedly: %s", e)

    return {
        "carbonIntensity": 250,
        "datetime": datetime.utcnow().isoformat(),
        "zone": "IN-SO",
        "status": "mock",
        "lastUpdated": datetime.utcnow().isoformat(),
    }

@router.get("/carbonclock/jobs")
async def get_job_queue():
    """Get current job queue and scheduling state"""
    jobs = [
        {
            "id": "402",
            "name": "AI Training Job #402",
            "type": "training",
            "deferrable": True,
            "estimatedDuration": 4,
            "estimatedKwh": 40,
            "status": "pending",
        },
        {
            "id": "156",
            "name": "Data Processing #156",
            "type": "batch",
            "deferrable": True,
            "estimatedDuration": 2,
            "estimatedKwh": 15,
            "status": "pending",
        },
        {
            "id": "89",
            "name": "Backup Sync #89",
            "type": "backup",
            "deferrable": False,
            "estimatedDuration": 6,
            "estimatedKwh": 25,
            "status": "scheduled",
        },
    ]
    return jobs

@router.post("/carbonclock/jobs/{job_id}/defer")
async def defer_carbon_job(job_id: str, request: JobActionRequest):
    """Defer a deferrable carbon-aware job"""
    return {
        "id": job_id,
        "status": "deferred",
        "deferredHours": request.hours,
        "message": f"Job {job_id} deferred by {request.hours} hours",
    }

@router.post("/carbonclock/jobs/{job_id}/run")
async def run_carbon_job(job_id: str):
    """Trigger a carbon-aware job to run immediately"""
    return {
        "id": job_id,
        "status": "running",
        "message": f"Job {job_id} started immediately",
    }

# ===================== ThermalTrace Routes =====================

@router.get("/thermaltrace/snapshot", response_model=List[ThermalCell])
async def get_thermal_snapshot():
    """Get latest thermal grid snapshot"""
    grid = []
    for x in range(8):
        for y in range(8):
            inlet = round(25 + (x + y) * 0.9 + (x % 2) * 2, 1)
            outlet = round(inlet + 4 + (y % 3) * 1.5, 1)
            grid.append({
                "id": f"cell_{x}_{y}",
                "x": x,
                "y": y,
                "inlet_celsius": inlet,
                "outlet_celsius": outlet,
            })
    return grid

@router.post("/thermaltrace/predict", response_model=ThermalPredictionResponse)
async def predict_thermal_hotspots(request: ThermalPredictionRequest):
    """
    Predict thermal hotspots using simple trend-based model
    
    Input: Last 20 thermal snapshots (64 cells each)
    Output: Predicted grid 15 minutes in advance with hotspot detection
    """
    if not request.snapshots or len(request.snapshots) < 2:
        raise HTTPException(status_code=400, detail="At least 2 snapshots required")

    if len(request.snapshots) > 200:
        raise HTTPException(status_code=400, detail="Too many snapshots (max 200)")

    num_cells = len(request.snapshots[0])
    if num_cells == 0:
        raise HTTPException(status_code=400, detail="Snapshots must contain at least one cell")
    predicted_grid = []
    hotspots = []
    confidence_scores = []
    
    for pos in range(num_cells):
        inlets = [snap[pos].inlet_celsius for snap in request.snapshots if pos < len(snap)]
        outlets = [snap[pos].outlet_celsius for snap in request.snapshots if pos < len(snap)]
        
        if len(inlets) < 2:
            continue
        
        # Calculate simple linear trend
        inlet_slope = (inlets[-1] - inlets[0]) / (len(inlets) - 1)
        outlet_slope = (outlets[-1] - outlets[0]) / (len(outlets) - 1)
        
        # Predict 15 minutes ahead (assuming 1 snapshot ~ 1 unit time)
        pred_inlet = inlets[-1] + inlet_slope * 1.5
        pred_outlet = outlets[-1] + outlet_slope * 1.5
        
        cell_id = request.snapshots[0][pos].id
        predicted_cell = ThermalCell(
            id=cell_id,
            x=request.snapshots[0][pos].x,
            y=request.snapshots[0][pos].y,
            inlet_celsius=round(pred_inlet, 2),
            outlet_celsius=round(pred_outlet, 2),
        )
        predicted_grid.append(predicted_cell)
        
        # Detect hotspots
        delta = pred_outlet - pred_inlet
        if pred_inlet > 35 or delta > 15:
            severity = "high" if pred_inlet > 40 or delta > 20 else "medium"
            hotspots.append({
                "id": cell_id,
                "severity": severity,
                "predicted_inlet": round(pred_inlet, 2),
                "predicted_delta": round(delta, 2)
            })
        
        trend_stability = 1.0 - min(abs(inlet_slope) + abs(outlet_slope), 2.0) / 2.0
        confidence_scores.append(trend_stability * 0.8 + 0.2)
    
    confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
    
    return ThermalPredictionResponse(
        predicted_grid=predicted_grid,
        hotspots=hotspots,
        confidence=round(confidence, 2),
        timestamp=datetime.utcnow().isoformat()
    )

# ===================== LightSpeed Routes =====================

@router.get("/lightspeed/network", response_model=NetworkTraffic)
async def get_network_traffic():
    """Get current network topology and link utilization"""
    return {
        "nodes": [
            {"id": "A1"},
            {"id": "A2"},
            {"id": "B1"},
            {"id": "B2"},
            {"id": "C1"},
        ],
        "links": [
            {"source": "A1", "target": "A2", "capacity_gbps": 10, "utilization_percent": 45},
            {"source": "A1", "target": "B1", "capacity_gbps": 10, "utilization_percent": 67},
            {"source": "A2", "target": "B2", "capacity_gbps": 10, "utilization_percent": 23},
            {"source": "B1", "target": "B2", "capacity_gbps": 10, "utilization_percent": 89},
            {"source": "C1", "target": "A1", "capacity_gbps": 10, "utilization_percent": 34},
            {"source": "C1", "target": "A2", "capacity_gbps": 10, "utilization_percent": 56},
            {"source": "C1", "target": "B1", "capacity_gbps": 10, "utilization_percent": 78},
            {"source": "C1", "target": "B2", "capacity_gbps": 10, "utilization_percent": 12},
        ],
    }

@router.post("/lightspeed/optimize")
async def optimize_network():
    """Simulate a network optimization pass after a traffic spike."""
    return {
        "optimized": True,
        "adjustedLinks": [
            {"source": "B1", "target": "B2", "utilization_percent": 60},
            {"source": "C1", "target": "B1", "utilization_percent": 72},
        ],
    }

# ===================== ML Bridge Endpoints =====================

@router.post("/ml/thermaltrace/predict", response_model=ThermalPredictionResponse)
async def ml_predict_thermal(request: ThermalPredictionRequest):
    """
    ML Bridge: Thermal prediction
    
    The frontend will call this after collecting 20 thermal snapshots.
    This endpoint should call a trained PyTorch LSTM model.

    TODO: No LSTM model exists yet in this codebase. When one is built,
    load it here (e.g. from a new ml/ module) instead of returning a stub.
    """
    # Stub implementation
    return ThermalPredictionResponse(
        predicted_grid=[],
        hotspots=[],
        confidence=0.0,
        timestamp=datetime.utcnow().isoformat()
    )

@router.post("/ml/noisemesh/classify", response_model=AudioClassificationResponse)
async def ml_classify_audio(request: AudioClassificationRequest):
    """
    EXCLUDED: NoiseMesh module is not being implemented
    This endpoint is kept as a stub for future reference only.
    """
    raise HTTPException(status_code=501, detail="NoiseMesh module is not part of this implementation")

# ===================== Health & Status =====================

@router.get("/status")
async def api_status():
    """Overall API status"""
    return {
        "status": "operational",
        "version": "1.0.0",
        "modules": {
            "idlehunter": "mock",
            "waterwatch": "mock",
            "carbonclock": "mock",
            "thermaltrace": "mock (ML stub pending)",
            "lightspeed": "mock",
            "noisemesh": "excluded"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
