"""
app/gridsync.py -- carbon-aware scheduling, analogous to VerdeGrid's
GridSync, but against a REAL live carbon-intensity feed instead of a
synthetic simulator. VerdeGrid's own CLAUDE.md is explicit that no real
Electricity-Maps/WattTime access existed there; this project has real
internet access from wherever it actually runs (your laptop/backend
machine), so this is the one module here that's more real than its
VerdeGrid counterpart.

Data source: the UK National Grid ESO's Carbon Intensity API
(https://carbonintensity.org.uk) -- chosen specifically because it's
free, public, and needs no signup or API key, unlike ElectricityMaps or
WattTime. It reports Great Britain's grid, not necessarily wherever these
laptops physically are -- a documented simplification for this demo, the
same way VerdeGrid documents its own simplifications rather than hiding
them. A real deployment would swap in a geolocation-keyed feed for the
laptops' actual region without changing anything below this module's
interface (fetch_current_carbon_intensity's return shape is all that
matters to callers).

The demo jobs are a small fixed set representing real deferrable
background tasks (a backup, an update check, a scan). This module only
decides whether each SHOULD run now -- nothing here actually launches
anything, matching the "show the decision, not yet the execution" scope
of this pass.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx
from pydantic import BaseModel

CARBON_INTENSITY_URL = "https://api.carbonintensity.org.uk/intensity"
# A real external API -- refreshed on a slow cadence, not every tick.
FETCH_INTERVAL_SECONDS = 300.0

CarbonIndex = Literal["very low", "low", "moderate", "high", "very high", "unknown"]

# "Clean enough to run a deferrable job" -- the same green/dirty
# threshold shape as VerdeGrid's GridSync, just against this API's own
# index categories instead of a raw gCO2/kWh cutoff.
GREEN_INDEXES = frozenset({"very low", "low"})


class CarbonSignal(BaseModel):
    intensityGCo2PerKwh: Optional[float]
    index: CarbonIndex
    fetchedAt: str
    source: str = "UK National Grid ESO Carbon Intensity API (demo stand-in for the laptops' actual local grid)"


def fetch_current_carbon_intensity(client: httpx.Client) -> CarbonSignal:
    """
    Real HTTP call. No synthetic fallback for the intensity number
    itself -- if the request fails (no internet, API down, blocked),
    the result is index="unknown" with intensityGCo2PerKwh=None, and
    callers decide what "unknown" means for scheduling (see
    DeferrableJob.decide) rather than this function fabricating a value.
    """
    try:
        resp = client.get(CARBON_INTENSITY_URL, timeout=10.0)
        resp.raise_for_status()
        intensity = resp.json()["data"][0]["intensity"]
        return CarbonSignal(
            intensityGCo2PerKwh=intensity.get("actual") or intensity.get("forecast"),
            index=intensity["index"],
            fetchedAt=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        return CarbonSignal(intensityGCo2PerKwh=None, index="unknown", fetchedAt=datetime.now(timezone.utc).isoformat())


JobStatus = Literal["waiting_for_clean_grid", "running", "force_run_deadline"]


@dataclass
class DeferrableJob:
    id: str
    name: str
    max_wait: timedelta
    submitted_at: datetime
    status: JobStatus = "waiting_for_clean_grid"
    decided_at: Optional[datetime] = None

    def decide(self, now: datetime, signal: CarbonSignal) -> JobStatus:
        """
        A job that has already started running or force-run stays there
        -- this is a one-way decision for the life of this demo job, the
        same as VerdeGrid's own scheduler never un-schedules something
        already released. Deadline force-run always wins regardless of
        the carbon signal (including "unknown"), matching the hard-
        deadline-overrides-a-dirty-grid behavior VerdeGrid's GridSync
        guarantees.
        """
        if self.status != "waiting_for_clean_grid":
            return self.status
        if (now - self.submitted_at) >= self.max_wait:
            self.status = "force_run_deadline"
        elif signal.index in GREEN_INDEXES:
            self.status = "running"
        if self.status != "waiting_for_clean_grid":
            self.decided_at = now
        return self.status


# A small set of real, plausible deferrable background tasks -- this
# module decides IF they should run, not what they actually do.
DEFAULT_DEMO_JOBS: list[tuple[str, str, timedelta]] = [
    ("backup-sync", "Backup Sync", timedelta(minutes=30)),
    ("update-check", "Software Update Check", timedelta(minutes=15)),
    ("virus-scan", "Full Virus Scan", timedelta(hours=2)),
]


class GridSyncScheduler:
    def __init__(self, *, now: Optional[datetime] = None, demo_jobs=DEFAULT_DEMO_JOBS) -> None:
        start = now or datetime.now(timezone.utc)
        self.jobs: dict[str, DeferrableJob] = {
            job_id: DeferrableJob(id=job_id, name=name, max_wait=max_wait, submitted_at=start)
            for job_id, name, max_wait in demo_jobs
        }
        self.last_signal: Optional[CarbonSignal] = None
        self._last_fetch_at: Optional[datetime] = None

    def maybe_refresh_signal(self, now: datetime, client: httpx.Client) -> CarbonSignal:
        stale = (
            self.last_signal is None
            or self._last_fetch_at is None
            or (now - self._last_fetch_at).total_seconds() >= FETCH_INTERVAL_SECONDS
        )
        if stale:
            self.last_signal = fetch_current_carbon_intensity(client)
            self._last_fetch_at = now
        return self.last_signal

    def tick(self, now: datetime, client: httpx.Client) -> CarbonSignal:
        signal = self.maybe_refresh_signal(now, client)
        for job in self.jobs.values():
            job.decide(now, signal)
        return signal
