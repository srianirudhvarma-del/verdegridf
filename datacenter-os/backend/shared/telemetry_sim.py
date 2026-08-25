"""
shared/telemetry_sim.py

Stateful synthetic telemetry engine (BUILD_PLAN.md Decision #1). No real
hypervisor/BMC/SNMP/Electricity-Maps access exists, so every module's real
algorithms (MAD thresholds, dwell timers, elephant-flow detection, per-rack
baselines, thermal RC models, ...) need to run against *plausible* time
series -- real variance, real trend, occasional real anomalies -- instead of
a fixed canned response or i.i.d. random noise on every call.

This is real, reusable engine code, not a stopgap: it is written behind the
`TelemetryAdapter` interface so a future real integration (an actual
hypervisor poller, a real Electricity Maps client, real BMS sensors) can be
dropped in later without any later-phase algorithm code changing.

Two layers:
  - `SyntheticSeries`: one stateful metric. Mean-reverting random walk
    (trend + noise + pull back toward a baseline), with a temporary
    "anomaly" override (leak, thermal spike, elephant flow, ...) that can be
    injected and expires after N ticks.
  - `TelemetrySimulator`: a registry of named entities (host/rack/link ids),
    each holding one or more named `SyntheticSeries` (e.g. a host has cpu,
    mem, diskIO, network). This is what `SimulatedTelemetryAdapter` polls.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Anomaly:
    kind: str
    magnitude: float
    ticks_remaining: int


class SyntheticSeries:
    """
    One stateful metric. Each call to `tick()` advances the internal state
    by one sample and returns the new value -- callers get a genuinely
    time-correlated series, not independent random draws.

    value[t+1] = value[t]
                 + trend_per_tick
                 + reversion * (baseline - value[t])   # pulls back toward baseline
                 + noise                                # Gaussian, std = noise_std
                 + anomaly_delta (if an anomaly is currently active)
    clamped to [min_value, max_value].
    """

    def __init__(
        self,
        baseline: float,
        *,
        trend_per_tick: float = 0.0,
        noise_std: float = 1.0,
        reversion: float = 0.1,
        min_value: float = 0.0,
        max_value: float = 100.0,
        seed: Optional[int] = None,
    ) -> None:
        if not 0.0 <= reversion <= 1.0:
            raise ValueError("reversion must be in [0, 1]")
        if min_value > max_value:
            raise ValueError("min_value must be <= max_value")

        self.baseline = baseline
        self.trend_per_tick = trend_per_tick
        self.noise_std = noise_std
        self.reversion = reversion
        self.min_value = min_value
        self.max_value = max_value

        self._rng = random.Random(seed)
        self.value = min(max(baseline, min_value), max_value)
        self.history: list[float] = [self.value]
        self._anomaly: Optional[Anomaly] = None

    def inject_anomaly(self, kind: str, magnitude: float, duration_ticks: int) -> None:
        """
        Temporarily add `magnitude` to every sample for the next
        `duration_ticks` calls to tick(). Replaces any anomaly already in
        progress -- only one active anomaly per series at a time.
        """
        if duration_ticks <= 0:
            raise ValueError("duration_ticks must be positive")
        self._anomaly = Anomaly(kind=kind, magnitude=magnitude, ticks_remaining=duration_ticks)

    @property
    def active_anomaly(self) -> Optional[str]:
        return self._anomaly.kind if self._anomaly else None

    def tick(self) -> float:
        noise = self._rng.gauss(0.0, self.noise_std)
        next_value = (
            self.value
            + self.trend_per_tick
            + self.reversion * (self.baseline - self.value)
            + noise
        )

        if self._anomaly is not None:
            next_value += self._anomaly.magnitude
            self._anomaly.ticks_remaining -= 1
            if self._anomaly.ticks_remaining <= 0:
                self._anomaly = None

        next_value = min(max(next_value, self.min_value), self.max_value)
        self.value = next_value
        self.history.append(next_value)
        return next_value

    def recent_history(self, n: int) -> list[float]:
        return self.history[-n:]


class TelemetryAdapter(ABC):
    """
    Adapter interface every module polls telemetry through. Algorithm code
    (MAD thresholds, elephant-flow detection, RC thermal model, ...) should
    depend only on this interface, never on `SimulatedTelemetryAdapter`
    directly, so a real hardware-backed adapter can be swapped in later
    without touching that code.
    """

    @abstractmethod
    def poll(self, entity_id: str) -> dict[str, float]:
        """Return the latest value of every registered metric for entity_id."""
        raise NotImplementedError

    @abstractmethod
    def history(self, entity_id: str, metric: str, n: int) -> list[float]:
        """Return up to the last n samples of one metric for entity_id."""
        raise NotImplementedError


@dataclass
class _Entity:
    metrics: dict[str, SyntheticSeries] = field(default_factory=dict)


class TelemetrySimulator:
    """
    Registry of simulated entities (hosts, racks, links, ...), each with one
    or more named metrics. This is the stateful engine BUILD_PLAN.md's
    Phase 0 calls for: per-host/per-rack/per-link time series with
    configurable trend + noise + injectable anomalies.
    """

    def __init__(self) -> None:
        self._entities: dict[str, _Entity] = {}

    def register_metric(
        self,
        entity_id: str,
        metric: str,
        *,
        baseline: float,
        trend_per_tick: float = 0.0,
        noise_std: float = 1.0,
        reversion: float = 0.1,
        min_value: float = 0.0,
        max_value: float = 100.0,
        seed: Optional[int] = None,
    ) -> None:
        entity = self._entities.setdefault(entity_id, _Entity())
        entity.metrics[metric] = SyntheticSeries(
            baseline,
            trend_per_tick=trend_per_tick,
            noise_std=noise_std,
            reversion=reversion,
            min_value=min_value,
            max_value=max_value,
            seed=seed,
        )

    def tick(self, entity_id: Optional[str] = None) -> None:
        """Advance one or all entities' metrics by one sample."""
        entities = [self._entities[entity_id]] if entity_id else list(self._entities.values())
        for entity in entities:
            for series in entity.metrics.values():
                series.tick()

    def sample(self, entity_id: str) -> dict[str, float]:
        """Advance every metric for entity_id by one tick and return the new values."""
        entity = self._require_entity(entity_id)
        return {name: series.tick() for name, series in entity.metrics.items()}

    def current(self, entity_id: str) -> dict[str, float]:
        """Return the current values without advancing state."""
        entity = self._require_entity(entity_id)
        return {name: series.value for name, series in entity.metrics.items()}

    def history(self, entity_id: str, metric: str, n: int) -> list[float]:
        entity = self._require_entity(entity_id)
        series = self._require_metric(entity, entity_id, metric)
        return series.recent_history(n)

    def inject_anomaly(self, entity_id: str, metric: str, kind: str, magnitude: float, duration_ticks: int) -> None:
        entity = self._require_entity(entity_id)
        series = self._require_metric(entity, entity_id, metric)
        series.inject_anomaly(kind, magnitude, duration_ticks)

    def entity_ids(self) -> list[str]:
        return list(self._entities.keys())

    def _require_entity(self, entity_id: str) -> _Entity:
        if entity_id not in self._entities:
            raise KeyError(f"Unknown entity: {entity_id!r}")
        return self._entities[entity_id]

    @staticmethod
    def _require_metric(entity: _Entity, entity_id: str, metric: str) -> SyntheticSeries:
        if metric not in entity.metrics:
            raise KeyError(f"Unknown metric {metric!r} for entity {entity_id!r}")
        return entity.metrics[metric]


class SimulatedTelemetryAdapter(TelemetryAdapter):
    """TelemetryAdapter implementation backed by a TelemetrySimulator."""

    def __init__(self, simulator: TelemetrySimulator) -> None:
        self._simulator = simulator

    def poll(self, entity_id: str) -> dict[str, float]:
        return self._simulator.sample(entity_id)

    def history(self, entity_id: str, metric: str, n: int) -> list[float]:
        return self._simulator.history(entity_id, metric, n)


def make_host_simulator(host_ids: list[str], *, seed: Optional[int] = None) -> TelemetrySimulator:
    """
    Convenience factory: a TelemetrySimulator pre-registered with the 4
    host-level resources the methodology's MAD threshold (MUST HAVE #1)
    needs -- cpu, mem, diskIO, network -- at plausible idle-cluster
    baselines with mild noise and mean reversion.
    """
    sim = TelemetrySimulator()
    rng = random.Random(seed)
    metric_defaults = {
        "cpu": dict(baseline=30.0, noise_std=4.0, reversion=0.15, min_value=0.0, max_value=100.0),
        "mem": dict(baseline=40.0, noise_std=3.0, reversion=0.1, min_value=0.0, max_value=100.0),
        "diskIO": dict(baseline=15.0, noise_std=5.0, reversion=0.2, min_value=0.0, max_value=100.0),
        "network": dict(baseline=20.0, noise_std=6.0, reversion=0.2, min_value=0.0, max_value=100.0),
    }
    for host_id in host_ids:
        for metric, params in metric_defaults.items():
            sim.register_metric(host_id, metric, seed=rng.randint(0, 2**31 - 1), **params)
    return sim
