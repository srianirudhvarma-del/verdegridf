import pytest

from thermaltrace.maintenance import check_maintenance_due
from thermaltrace.spatial import GridCellReading, SpatialResidualCorrector, interpolate_grid
from thermaltrace.zoning import (
    ZoneSetpointRegistry,
    build_setpoint_recommendation,
    cluster_racks_into_zones,
    temperature_delta_correlation,
)


# ---------------------------------------------------------------------------
# SHOULD HAVE #23 -- grid-shaped spatial modeling + sensor-vs-interpolated flagging
# ---------------------------------------------------------------------------


def test_real_sensor_cells_are_never_flagged_as_interpolated():
    readings = [GridCellReading(x=0, y=0, value=30.0), GridCellReading(x=1, y=0, value=32.0)]
    grid = interpolate_grid(readings, width=2, height=1)

    assert grid.isInterpolated[0][0] is False
    assert grid.isInterpolated[0][1] is False
    assert grid.values[0][0] == 30.0
    assert grid.values[0][1] == 32.0


def test_missing_cells_are_flagged_interpolated_and_filled():
    readings = [
        GridCellReading(x=0, y=0, value=30.0),
        GridCellReading(x=2, y=0, value=40.0),
        GridCellReading(x=1, y=0, value=None),  # missing
    ]
    grid = interpolate_grid(readings, width=3, height=1)

    assert grid.isInterpolated[0][1] is True
    assert 30.0 < grid.values[0][1] < 40.0  # between its two neighbors


def test_interpolation_requires_at_least_one_real_reading():
    with pytest.raises(ValueError):
        interpolate_grid([GridCellReading(x=0, y=0, value=None)], width=1, height=1)


def test_spatial_corrector_blends_own_history_with_neighbors():
    corrector = SpatialResidualCorrector(width=3, height=1)
    corrector.record_residual(0, 0, 2.0)
    corrector.record_residual(1, 0, 4.0)
    corrector.record_residual(2, 0, 6.0)

    grid = corrector.predict_residual_grid()

    # cell (1,0)'s own history is 4.0; its neighbors (0,0)=2.0 and (2,0)=6.0
    # average to 4.0 too, so the blended result should equal 4.0.
    assert grid[0][1] == pytest.approx(4.0)


def test_spatial_corrector_falls_back_to_own_value_with_no_neighbor_data():
    corrector = SpatialResidualCorrector(width=1, height=1)
    corrector.record_residual(0, 0, 3.0)

    grid = corrector.predict_residual_grid()
    assert grid[0][0] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# SHOULD HAVE #24 -- thermal zoning and adaptive setpoints
# ---------------------------------------------------------------------------


def test_correlation_is_high_for_racks_that_move_together():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [2.0, 4.0, 6.0, 8.0, 10.0]  # perfectly correlated (scaled)
    assert temperature_delta_correlation(a, b) == pytest.approx(1.0)


def test_correlation_is_near_zero_for_unrelated_racks():
    a = [1.0, 2.0, 1.0, 2.0, 1.0]
    b = [5.0, 5.0, 5.0, 5.0, 5.0]  # no variance -- uncorrelated by definition
    assert temperature_delta_correlation(a, b) == 0.0


def test_racks_cluster_together_when_correlated():
    deltas = {
        "rack-1": [1.0, 2.0, 3.0, 4.0],
        "rack-2": [1.1, 2.1, 3.1, 4.1],  # tracks rack-1 closely
        "rack-3": [5.0, 1.0, 8.0, 2.0],  # unrelated pattern
    }
    zones = cluster_racks_into_zones(["rack-1", "rack-2", "rack-3"], deltas)

    zone_members = list(zones.values())
    assert any({"rack-1", "rack-2"}.issubset(set(members)) for members in zone_members)
    assert not any("rack-3" in members and "rack-1" in members for members in zone_members)


def test_zone_setpoint_falls_back_to_facility_default():
    registry = ZoneSetpointRegistry(default_setpoint_celsius=22.0)
    assert registry.get_setpoint("zone-unset") == 22.0

    registry.set_zone_setpoint("zone-1", 19.5)
    assert registry.get_setpoint("zone-1") == 19.5
    assert registry.get_setpoint("zone-2") == 22.0


def test_setpoint_recommendation_feeds_the_action_queue():
    rec = build_setpoint_recommendation("rec-1", "zone-1", "rack-5", 22.0, 20.0)
    assert rec.type == "adjust_setpoint"
    assert rec.status == "pending"
    assert rec.magnitude == -2.0


# ---------------------------------------------------------------------------
# SHOULD HAVE #25 -- predictive maintenance for cooling equipment
# ---------------------------------------------------------------------------


def test_flags_maintenance_due_when_run_hours_exceed_rated_interval():
    flag = check_maintenance_due("fan-1", run_hours=9000.0, rated_service_interval_hours=8760.0,
                                  current_draw_baseline=None, current_draw_latest=None)
    assert flag is not None
    assert "runHours" in flag.reason


def test_flags_maintenance_due_on_current_draw_deviation():
    flag = check_maintenance_due("pump-1", run_hours=100.0, rated_service_interval_hours=8760.0,
                                  current_draw_baseline=10.0, current_draw_latest=13.0)  # 30% deviation
    assert flag is not None
    assert "current-draw" in flag.reason


def test_no_flag_for_healthy_equipment():
    flag = check_maintenance_due("fan-2", run_hours=100.0, rated_service_interval_hours=8760.0,
                                  current_draw_baseline=10.0, current_draw_latest=10.3)
    assert flag is None
