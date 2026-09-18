"""
gridsync/grid.py

MUST HAVE #8 -- documented average-vs-marginal carbon-signal justification.
Hardcoded as a config object, not a hidden default -- visible in an
admin/about panel (api/routes.py, when this module is wired up) and here in
comments. `signalType` stays a config flag even though only "average" is
implemented, so a future multi-provider item has a clean extension point.

Also owns GridSync's carbon-intensity forecast source. api/routes.py
already has a real-time ElectricityMaps client; no real 48h *forecast* API
access exists, so -- per Phase 0 Decision #1 -- a synthetic 48h hourly
forecast is generated with the shared telemetry simulator, giving the
capacity-curve scheduler (scheduler.py) genuinely time-varying data to
bucket and rank instead of a fixed canned response.

SHOULD HAVE #10 -- ForecastCache refreshes on a 1-4h cycle instead of
regenerating the forecast on every call.

SHOULD HAVE #11 -- HysteresisState smooths the carbon-state signal and
requires a sustained band-margin crossing before flipping green/dirty.
"""

import statistics
from datetime import datetime, timedelta
from typing import Literal, Optional

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

    def sample_current(self, zone: str) -> float:
        """Advances and returns the zone's current carbon-intensity reading, for live polling (as opposed to forecast_48h's batch of 48 hourly buckets)."""
        return self._simulator.sample(zone)["carbon_intensity"]

    def history(self, zone: str, n: int) -> list[float]:
        return self._simulator.history(zone, "carbon_intensity", n)


# ---------------------------------------------------------------------------
# SHOULD HAVE #10 -- ingest forecast on a refresh cycle, not every call
# ---------------------------------------------------------------------------

# Methodology: "1-4 hour refresh cycle." Mirrors, within that range.
DEFAULT_FORECAST_REFRESH_INTERVAL_SECONDS = 2 * 3600.0


class ForecastCache:
    """
    Wraps a CarbonForecastSimulator so the 48h forecast is only
    regenerated once per refresh_interval_seconds per zone, instead of on
    every scheduling call -- matching how a real Electricity Maps forecast
    endpoint would actually be polled.
    """

    def __init__(
        self,
        simulator: CarbonForecastSimulator,
        *,
        refresh_interval_seconds: float = DEFAULT_FORECAST_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self._simulator = simulator
        self.refresh_interval_seconds = refresh_interval_seconds
        self._cached: dict[str, list[HourlyForecast]] = {}
        self._last_refreshed: dict[str, datetime] = {}

    def get_forecast(self, zone: str, *, now: datetime) -> list[HourlyForecast]:
        last = self._last_refreshed.get(zone)
        if last is None or (now - last).total_seconds() >= self.refresh_interval_seconds:
            self._cached[zone] = self._simulator.forecast_48h(zone, start=now)
            self._last_refreshed[zone] = now
        return self._cached[zone]

    def last_refreshed(self, zone: str) -> Optional[datetime]:
        return self._last_refreshed.get(zone)


# ---------------------------------------------------------------------------
# SHOULD HAVE #11 -- hysteresis/smoothing on the carbon-state signal
# ---------------------------------------------------------------------------

# Mirrors gridsync/scheduler.py's DEFAULT_GREEN_THRESHOLD/DIRTY_THRESHOLD.
# Duplicated (not imported) to avoid a circular import -- scheduler.py
# already imports HourlyForecast from this module.
DEFAULT_GREEN_THRESHOLD = 150.0
DEFAULT_DIRTY_THRESHOLD = 400.0

DEFAULT_SMOOTHING_WINDOW = 3
DEFAULT_BAND_MARGIN_PERCENT = 10.0
DEFAULT_CONFIRM_SAMPLES = 2

CarbonState = Literal["green", "dirty", "normal"]


class HysteresisState:
    """
    smoothedIntensity = movingAverage(last N samples)
    onlyChangeGreenDirtyClassification if smoothedIntensity crosses the
    threshold band by more than bandMarginPercent for >= confirmSamples
    consecutive samples.
    """

    def __init__(
        self,
        *,
        green_threshold: float = DEFAULT_GREEN_THRESHOLD,
        dirty_threshold: float = DEFAULT_DIRTY_THRESHOLD,
        band_margin_percent: float = DEFAULT_BAND_MARGIN_PERCENT,
        confirm_samples: int = DEFAULT_CONFIRM_SAMPLES,
        window: int = DEFAULT_SMOOTHING_WINDOW,
    ) -> None:
        self.green_threshold = green_threshold
        self.dirty_threshold = dirty_threshold
        # bandMarginPercent applied as a percentage of the threshold value itself.
        self.green_margin = green_threshold * band_margin_percent / 100.0
        self.dirty_margin = dirty_threshold * band_margin_percent / 100.0
        self.confirm_samples = confirm_samples
        self.window = window

        self._samples: list[float] = []
        self.classification: CarbonState = "normal"
        self._candidate: Optional[CarbonState] = None
        self._candidate_streak = 0

    def observe(self, intensity: float) -> CarbonState:
        self._samples.append(intensity)
        if len(self._samples) > self.window:
            self._samples.pop(0)
        smoothed = statistics.mean(self._samples)

        if smoothed < self.green_threshold - self.green_margin:
            candidate: CarbonState = "green"
        elif smoothed > self.dirty_threshold + self.dirty_margin:
            candidate = "dirty"
        else:
            candidate = "normal"

        if candidate == self.classification:
            self._candidate_streak = 0
            return self.classification

        if candidate == self._candidate:
            self._candidate_streak += 1
        else:
            self._candidate = candidate
            self._candidate_streak = 1

        if self._candidate_streak >= self.confirm_samples:
            self.classification = candidate
            self._candidate_streak = 0

        return self.classification
