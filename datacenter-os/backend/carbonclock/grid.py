"""
carbonclock/grid.py

MUST HAVE #8 -- documented average-vs-marginal carbon-signal justification.
Hardcoded as a config object, not a hidden default -- visible in an
admin/about panel (api/routes.py, when this module is wired up) and here in
comments. `signalType` stays a config flag even though only "average" is
implemented, so a future multi-provider item has a clean extension point.

Also owns CarbonClock's carbon-intensity forecast source. api/routes.py
already has a real-time ElectricityMaps client; no real 48h *forecast* API
access exists, so -- per Phase 0 Decision #1 -- a synthetic 48h hourly
forecast is generated with the shared telemetry simulator, giving the
capacity-curve scheduler (scheduler.py) genuinely time-varying data to
bucket and rank instead of a fixed canned response.
"""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from shared.telemetry_sim import TelemetrySimulator

SignalType = Literal["average", "marginal"]

# Only "average" is implemented today. The flag is kept even though
# "marginal" isn't -- selecting it is a documented no-op, not silently
# ignored -- so a future multi-provider item has a clean extension point.
SUPPORTED_SIGNAL_TYPES: tuple[SignalType, ...] = ("average", "marginal")
IMPLEMENTED_SIGNAL_TYPES: tuple[SignalType, ...] = ("average",)


class SignalInfo(BaseModel):
    type: SignalType
    provider: str
    methodology: str
    rationale: str


DEFAULT_SIGNAL_INFO = SignalInfo(
    type="average",
    provider="electricitymaps",
    methodology="flow-traced",
    rationale=(
        "Matches Google CICS's own data source; average/flow-traced is the "
        "accounting standard; marginal signals disagree in direction across "
        "many grids per peer-reviewed comparison."
    ),
)


class HourlyForecast(BaseModel):
    windowStart: str
    windowEnd: str
    carbonIntensity: float


class CarbonForecastSimulator:
    """Synthetic 48h hourly carbon-intensity forecast, per grid zone."""

    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_zone(
        self,
        zone: str,
        *,
        baseline: float = 250.0,
        noise_std: float = 30.0,
        reversion: float = 0.3,
        min_value: float = 0.0,
        max_value: float = 900.0,
        seed: int | None = None,
    ) -> None:
        self._simulator.register_metric(
            zone,
            "carbon_intensity",
            baseline=baseline,
            noise_std=noise_std,
            reversion=reversion,
            min_value=min_value,
            max_value=max_value,
            seed=seed,
        )

    def forecast_48h(self, zone: str, *, start: datetime) -> list[HourlyForecast]:
        """Advances the zone's series by 48 ticks (1 tick == 1 hour of forecast)."""
        buckets = []
        for hour_offset in range(48):
            intensity = self._simulator.sample(zone)["carbon_intensity"]
            window_start = start + timedelta(hours=hour_offset)
            window_end = window_start + timedelta(hours=1)
            buckets.append(
                HourlyForecast(
                    windowStart=window_start.isoformat(),
                    windowEnd=window_end.isoformat(),
                    carbonIntensity=intensity,
                )
            )
        return buckets
