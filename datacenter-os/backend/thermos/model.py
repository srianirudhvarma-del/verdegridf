"""
thermos/model.py

MUST HAVE #20 -- hybrid physics + ML core (replaces the pure trend-stub
prediction). Physics-lite RC thermal model ships alone first (needs zero
training data); a small residual regressor corrects it once enough
historical residuals exist to train on.

MUST HAVE #18 -- uncertainty bands via an MC-Dropout-style ensemble.

MUST HAVE #19 -- feature vector wiring PowerPrune's workload/power
telemetry into the thermal model, joined by rackId + nearest timestamp.
"""

import random
import statistics
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# MUST HAVE #20 -- physics-lite RC core + ML residual correction
# ---------------------------------------------------------------------------


class RCThermalModel:
    """
    T_predicted(t+dt) = T(t) + (dt/RC) * (Q_in(t) - Q_out(t))
      Q_in  ~= powerDrawWatts(t)
      Q_out ~= coolingCapacity * (T(t) - T_supply(t))
      R, C  = calibrated per-rack thermal resistance/capacitance constants

    Needs zero training data -- this alone is a valid, plausible predictor.
    """

    def __init__(self, *, thermal_resistance: float, thermal_capacitance: float, cooling_capacity: float) -> None:
        if thermal_resistance <= 0 or thermal_capacitance <= 0:
            raise ValueError("thermal_resistance and thermal_capacitance must be positive")
        self.thermal_resistance = thermal_resistance
        self.thermal_capacitance = thermal_capacitance
        self.cooling_capacity = cooling_capacity

    def predict(self, current_temp_c: float, power_draw_watts: float, supply_temp_c: float, dt_seconds: float) -> float:
        q_in = power_draw_watts
        q_out = self.cooling_capacity * (current_temp_c - supply_temp_c)
        rc = self.thermal_resistance * self.thermal_capacitance
        return current_temp_c + (dt_seconds / rc) * (q_in - q_out)


# Methodology: "add the ML correction once enough historical residuals
# exist to train on." Below this many recorded residuals, predict_residual
# falls back to 0 (physics-only) -- the fail-safe pre-change behavior.
MIN_RESIDUAL_TRAINING_SAMPLES = 10


class ResidualCorrector:
    """
    residual(t) = T_actual(t) - T_physics_predicted(t)
    Trains a small regressor (ordinary least squares trend line -- the
    "simple regressor" the methodology allows before ConvLSTM territory,
    which is SHOULD HAVE #23 and out of scope here) to predict
    residual(t+dt) from recent history.
    """

    def __init__(self, *, window: int = 30) -> None:
        if window < MIN_RESIDUAL_TRAINING_SAMPLES:
            raise ValueError(f"window must be >= {MIN_RESIDUAL_TRAINING_SAMPLES}")
        self.window = window
        self._residuals: list[float] = []

    def record_residual(self, residual: float) -> None:
        self._residuals.append(residual)
        if len(self._residuals) > self.window:
            self._residuals.pop(0)

    @property
    def has_enough_data(self) -> bool:
        return len(self._residuals) >= MIN_RESIDUAL_TRAINING_SAMPLES

    def predict_residual(self) -> float:
        if not self.has_enough_data:
            return 0.0
        x = list(range(len(self._residuals)))
        slope, intercept = _ordinary_least_squares(x, self._residuals)
        return slope * len(self._residuals) + intercept


def _ordinary_least_squares(x: list[float], y: list[float]) -> tuple[float, float]:
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denominator = sum((xi - mean_x) ** 2 for xi in x)
    if denominator == 0:
        return 0.0, mean_y
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept


# ---------------------------------------------------------------------------
# MUST HAVE #18 -- uncertainty bands (MC Dropout-style ensemble)
# ---------------------------------------------------------------------------

# Methodology default: N=5 forward passes, ~95% CI via 1.96*std.
DEFAULT_ENSEMBLE_PASSES = 5
CONFIDENCE_Z_SCORE = 1.96

# The physics+ML core has no literal dropout layers to disable at
# inference, so the ensemble stands in for MC Dropout by stochastically
# jittering the calibrated R/C constants each pass (a documented
# simplification -- see methodology's own suggested alternative of
# quantile regression as the more principled but higher-effort option).
DEFAULT_PARAM_NOISE_STD = 0.05


class ThermalPrediction(BaseModel):
    rackId: str
    timestamp: str
    mean: float
    lower: float
    upper: float
    physicsOnly: bool  # True while the ML residual correction has no training data yet


def predict_with_uncertainty(
    model: RCThermalModel,
    corrector: ResidualCorrector,
    *,
    rack_id: str,
    current_temp_c: float,
    power_draw_watts: float,
    supply_temp_c: float,
    dt_seconds: float,
    n_passes: int = DEFAULT_ENSEMBLE_PASSES,
    param_noise_std: float = DEFAULT_PARAM_NOISE_STD,
    seed: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> ThermalPrediction:
    if n_passes < 1:
        raise ValueError("n_passes must be >= 1")

    rng = random.Random(seed)
    samples = []
    for _ in range(n_passes):
        jittered_model = RCThermalModel(
            thermal_resistance=max(model.thermal_resistance * (1 + rng.gauss(0, param_noise_std)), 1e-9),
            thermal_capacitance=max(model.thermal_capacitance * (1 + rng.gauss(0, param_noise_std)), 1e-9),
            cooling_capacity=model.cooling_capacity,
        )
        physics_pred = jittered_model.predict(current_temp_c, power_draw_watts, supply_temp_c, dt_seconds)
        samples.append(physics_pred + corrector.predict_residual())

    mean = statistics.mean(samples)
    std = statistics.pstdev(samples) if n_passes > 1 else 0.0

    return ThermalPrediction(
        rackId=rack_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        mean=mean,
        lower=mean - CONFIDENCE_Z_SCORE * std,
        upper=mean + CONFIDENCE_Z_SCORE * std,
        physicsOnly=not corrector.has_enough_data,
    )


# ---------------------------------------------------------------------------
# MUST HAVE #19 -- wire PowerPrune's workload/power telemetry into the
# thermal feature vector, joined by rackId + nearest timestamp
# ---------------------------------------------------------------------------


class PowerPruneRackReading(BaseModel):
    """One rack-aggregated utilization/power sample, as PowerPrune would publish it."""

    rackId: str
    timestamp: str
    workloadUtil: float
    powerDrawWatts: float


class ThermalFeatureVector(BaseModel):
    rackId: str
    timestamp: str
    tempGrid: list[list[float]]
    humidity: float
    workloadUtil: Optional[float] = None
    powerDrawWatts: Optional[float] = None


# Methodology: "tolerate up to 1 sampling-interval staleness." PowerPrune
# samples at 30-60s cadence; use the upper end as the default tolerance.
DEFAULT_MAX_STALENESS_SECONDS = 60.0


def join_workload_telemetry(
    rack_id: str,
    thermal_timestamp: str,
    powerprune_readings: list[PowerPruneRackReading],
    *,
    max_staleness_seconds: float = DEFAULT_MAX_STALENESS_SECONDS,
) -> tuple[Optional[float], Optional[float]]:
    """
    Most recent PowerPrune reading for rack_id at or before
    thermal_timestamp, within max_staleness_seconds. Fail-safe: no
    matching reading returns (None, None) rather than fabricating a value
    -- the same as "no telemetry available," the pre-change behavior.
    """
    target = datetime.fromisoformat(thermal_timestamp)
    best: Optional[PowerPruneRackReading] = None
    best_delta: Optional[float] = None

    for reading in powerprune_readings:
        if reading.rackId != rack_id:
            continue
        reading_time = datetime.fromisoformat(reading.timestamp)
        if reading_time > target:
            continue
        delta = (target - reading_time).total_seconds()
        if delta > max_staleness_seconds:
            continue
        if best_delta is None or delta < best_delta:
            best, best_delta = reading, delta

    if best is None:
        return None, None
    return best.workloadUtil, best.powerDrawWatts


def build_feature_vector(
    rack_id: str,
    timestamp: str,
    temp_grid: list[list[float]],
    humidity: float,
    powerprune_readings: list[PowerPruneRackReading],
    *,
    max_staleness_seconds: float = DEFAULT_MAX_STALENESS_SECONDS,
) -> ThermalFeatureVector:
    workload_util, power_draw_watts = join_workload_telemetry(
        rack_id, timestamp, powerprune_readings, max_staleness_seconds=max_staleness_seconds
    )
    return ThermalFeatureVector(
        rackId=rack_id,
        timestamp=timestamp,
        tempGrid=temp_grid,
        humidity=humidity,
        workloadUtil=workload_util,
        powerDrawWatts=power_draw_watts,
    )
