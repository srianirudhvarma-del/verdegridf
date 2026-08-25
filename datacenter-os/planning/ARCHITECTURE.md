# DatacenterOS Architecture Plan

## Overview
DatacenterOS is a unified datacenter sustainability platform designed to monitor and optimize operations across 6 key metrics: IDLEhunter (compute waste), WaterWatch (cooling water usage), CarbonClock (real-time emission tracking), ThermalTrace (heat distribution), NoiseMesh (acoustic environmental monitoring), and LightSpeed (optical interconnect efficiency).

## Core Modules
1.  **IDLEhunter**: Compute efficiency and zombie server detection.
2.  **WaterWatch**: PUE/WUE correlation and cooling loss detection.
3.  **CarbonClock**: Real-time CO2e per watt mapping based on grid intensity.
4.  **ThermalTrace**: Hot/cold aisle delta monitoring with ML-based hotspot prediction.
5.  **NoiseMesh**: Acoustic mapping of fan resonance and mechanical health.
6.  **LightSpeed**: Fiber path latency and transceiver power optimization.

## Tech Stack
- **Frontend**: React 18+ (Vite), Tailwind CSS, Framer Motion (for dynamic heatmaps), Recharts (for sparklines).
- **Backend**: Python 3.10+ (FastAPI), Pydantic (data validation).
- **Data Layer**: JSON-based simulated sensor data, stored in `data/simulated/`.
- **ML Services**: Python models as placeholders for LSTM/Anomaly detection in ThermalTrace and NoiseMesh.

## Shared Data Contracts (JSON / Pydantic)

### Common Sensor Interface
```json
{
  "timestamp": "ISO-8601",
  "value": "float",
  "unit": "string",
  "module": "string",
  "sensor_id": "string",
  "status": "string (NORMAL | ALERT | CRITICAL)"
}
```

### Module Status Response
```json
{
  "module_name": "string",
  "is_active": "boolean",
  "current_pue": "float",
  "kpi": {
    "total_savings": "float",
    "efficiency_gain": "float"
  }
}
```

## Phased Build Order
1.  **Phase 1: Project Scaffolding & Initial Planning** (COMPLETE) - Setting up the monorepo structure.
2.  **Phase 2: Data Simulation Layer** - Building scripts to generate realistic sensor streams.
3.  **Phase 3: Backend API Service** - Implementing FastAPI routes and models for all 6 modules.
4.  **Phase 4: Shared UI Components** - Building the navigation, layout, and core visualization components (Heatmaps/Sparklines).
5.  **Phase 5: Module Implementation** - Developing the 6 specialized module dashboards.
6.  **Phase 6: ML & Optimization Feed** - Integrating the ML placeholders for advanced analytics.
