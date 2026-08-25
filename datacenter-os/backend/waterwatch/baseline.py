"""
waterwatch/baseline.py -- MUST HAVE #12: per-rack baseline + peer-rack
comparison, cross-wired with IdleHunter's per-rack utilization signal.

1. Bucket time into "load buckets" using IdleHunter's per-rack utilization
   signal: low / medium / high (tertiles of historical utilization).
2. baseline(rack, signal, loadBucket) = {mean, std}, computed over
   trailing 7 days, only using samples from the matching load bucket.
3. z(rack, signal, t) = (value(t) - baseline.mean) / baseline.std
4. peerZ(rack, t) = z(rack,t) - average(z(peerRacksInSameLoadBucket, t))

The anomaly decision itself (combining z, peerZ, and the workload-delta
check) lives in waterwatch/anomaly.py.
"""

import statistics
from dataclasses import dataclass
from typing import Literal

LoadBucket = Literal["low", "medium", "high"]


def bucket_utilization(current_util: float, historical_utils: list[float]) -> LoadBucket:
    """
    Tertiles of historical utilization determine low/medium/high. With
    fewer than 3 historical samples there isn't enough data to compute
    tertiles -- fail safe to "medium" so this rack neither dominates nor
    is silently excluded from any bucket's peer comparison.
    """
    if len(historical_utils) < 3:
        return "medium"

    sorted_utils = sorted(historical_utils)
    low_cut = sorted_utils[len(sorted_utils) // 3]
    high_cut = sorted_utils[(2 * len(sorted_utils)) // 3]

    if current_util <= low_cut:
        return "low"
    if current_util >= high_cut:
        return "high"
    return "medium"


@dataclass
class Baseline:
    mean: float
    std: float


def compute_baseline(samples_in_load_bucket: list[float]) -> Baseline:
    """mean/std over trailing-7-day samples matching one load bucket."""
    if len(samples_in_load_bucket) < 2:
        raise ValueError("need at least 2 samples in the load bucket to compute a baseline")
    return Baseline(mean=statistics.mean(samples_in_load_bucket), std=statistics.pstdev(samples_in_load_bucket))


def z_score(value: float, baseline: Baseline) -> float:
    if baseline.std == 0:
        return 0.0 if value == baseline.mean else float("inf") * (1.0 if value > baseline.mean else -1.0)
    return (value - baseline.mean) / baseline.std


def peer_z_score(rack_z: float, peer_zs: list[float]) -> float:
    """peerZ(rack,t) = z(rack,t) - average(z(peerRacksInSameLoadBucket,t))."""
    if not peer_zs:
        return 0.0
    return rack_z - statistics.mean(peer_zs)
