import pytest
from pydantic import ValidationError

from shared.contracts import (
    TOPICS,
    CapacityForecast,
    ThermalHeadroom,
    WorkloadTag,
)


def test_unclassified_tag_reads_as_protected():
    """Fail-safe-open: an 'unclassified' tag must never be treated as deferrable."""
    tag = WorkloadTag(
        workloadId="vm-1",
        classification="unclassified",
        source="default",
        updatedAt="2026-08-25T00:00:00Z",
    )
    assert tag.effective_classification == "protected"


def test_protected_tag_reads_as_protected():
    tag = WorkloadTag(
        workloadId="vm-2",
        classification="protected",
        source="operator",
        updatedAt="2026-08-25T00:00:00Z",
    )
    assert tag.effective_classification == "protected"


def test_deferrable_tag_requires_max_delay_minutes():
    with pytest.raises(ValidationError):
        WorkloadTag(
            workloadId="vm-3",
            classification="deferrable",
            source="operator",
            updatedAt="2026-08-25T00:00:00Z",
        )


def test_deferrable_tag_with_max_delay_reads_as_deferrable():
    tag = WorkloadTag(
        workloadId="vm-4",
        classification="deferrable",
        maxDelayMinutes=120,
        source="operator",
        updatedAt="2026-08-25T00:00:00Z",
    )
    assert tag.effective_classification == "deferrable"


def test_capacity_forecast_roundtrip():
    forecast = CapacityForecast(
        timestampRangeStart="2026-08-25T00:00:00Z",
        timestampRangeEnd="2026-08-25T00:05:00Z",
        poweredOnHostCount=40,
        availableCpuCapacity=120.5,
        availableMemCapacity=512.0,
        standbyHostCount=6,
        estimatedWakeLatencySeconds=45.0,
    )
    assert forecast.poweredOnHostCount == 40
    assert forecast.standbyHostCount == 6


def test_thermal_headroom_status_is_constrained_to_known_values():
    with pytest.raises(ValidationError):
        ThermalHeadroom(
            rackId="rack-1",
            timestamp="2026-08-25T00:00:00Z",
            headroomCelsius=3.2,
            status="fine",  # not a valid status
        )

    headroom = ThermalHeadroom(
        rackId="rack-1",
        timestamp="2026-08-25T00:00:00Z",
        headroomCelsius=3.2,
        status="constrained",
    )
    assert headroom.status == "constrained"


def test_topics_cover_the_five_methodology_topics():
    assert TOPICS == {
        "idlehunter.capacity.updated",
        "idlehunter.workload.classified",
        "thermaltrace.headroom.updated",
        "carbonclock.job.scheduled",
        "lightspeed.flow.classified",
    }
