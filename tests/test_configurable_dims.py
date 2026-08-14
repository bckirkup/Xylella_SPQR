"""Tests for configurable sensor dimensionalities and engine cap awareness."""

from __future__ import annotations

import warnings

import pytest

from grain_guard.adapter.grain_adapter import (
    DEFAULT_ENGINE_MAX_DIM,
    CostCoefficients,
    DimBudget,
    GrainGuardAdapter,
)
from grain_guard.sensors.yield_monitor import YieldMonitor

# ---------------------------------------------------------------------------
# Satellite zone grid configurability
# ---------------------------------------------------------------------------


class TestSatelliteZoneConfig:
    """Satellite zone_rows / zone_cols threaded through adapter."""

    def test_default_satellite_dims(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        budget = adapter.stream_budget()
        sat = budget.streams[0]
        assert sat.label == "satellite_indices"
        # default 5×5×3 = 75
        assert sat.dimensionality == 75

    def test_custom_satellite_zones(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=8,
            grid_cols=8,
            satellite_zone_rows=3,
            satellite_zone_cols=3,
            seed=1,
        )
        budget = adapter.stream_budget()
        sat = budget.streams[0]
        # 3×3×3 = 27
        assert sat.dimensionality == 27

    def test_satellite_1x1(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=8, grid_cols=8, satellite_zone_rows=1, satellite_zone_cols=1, seed=1
        )
        sat = adapter.stream_budget().streams[0]
        assert sat.dimensionality == 3

    def test_satellite_zones_fit_under_cap(self) -> None:
        """3×3 grid (27 floats) fits under default 30-dim cap."""
        adapter = GrainGuardAdapter(
            grid_rows=10,
            grid_cols=10,
            satellite_zone_rows=3,
            satellite_zone_cols=3,
            seed=1,
        )
        sat = adapter.stream_budget().streams[0]
        assert sat.dimensionality <= DEFAULT_ENGINE_MAX_DIM
        assert not sat.exceeds_engine_cap


# ---------------------------------------------------------------------------
# Yield monitor zone configurability
# ---------------------------------------------------------------------------


class TestYieldMonitorZoneConfig:
    """YieldMonitor n_zones configurable through field and adapter."""

    def test_default_n_zones(self) -> None:
        ym = YieldMonitor()
        assert ym.output_dim == 5

    def test_custom_n_zones(self) -> None:
        ym = YieldMonitor(n_zones=8)
        assert ym.output_dim == 8

    def test_single_zone(self) -> None:
        ym = YieldMonitor(n_zones=1)
        assert ym.output_dim == 1

    def test_n_zones_via_adapter(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, yield_zones=3, seed=1)
        assert adapter._yield_monitor.output_dim == 3


# ---------------------------------------------------------------------------
# Sensor fleet counts → stream dims
# ---------------------------------------------------------------------------


class TestFleetStreamDims:
    """Changing trap/station/sensor counts changes stream dimensionality."""

    def test_trap_count_affects_dim(self) -> None:
        a5 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_traps=5, seed=1)
        a20 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_traps=20, seed=1)
        dim5 = a5.stream_budget().streams[1].dimensionality
        dim20 = a20.stream_budget().streams[1].dimensionality
        assert dim5 == 10  # 5 traps × 2
        assert dim20 == 40  # 20 traps × 2

    def test_weather_count_affects_dim(self) -> None:
        a1 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_weather_stations=1, seed=1)
        a4 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_weather_stations=4, seed=1)
        assert a1.stream_budget().streams[2].dimensionality == 5  # 1 × 5
        assert a4.stream_budget().streams[2].dimensionality == 20  # 4 × 5

    def test_soil_count_affects_dim(self) -> None:
        a2 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_soil_sensors=2, seed=1)
        a8 = GrainGuardAdapter(grid_rows=8, grid_cols=8, n_soil_sensors=8, seed=1)
        assert a2.stream_budget().streams[3].dimensionality == 6  # 2 × 3
        assert a8.stream_budget().streams[3].dimensionality == 24  # 8 × 3


# ---------------------------------------------------------------------------
# Stream budget reporting
# ---------------------------------------------------------------------------


class TestStreamBudget:
    """stream_budget() returns a correct DimBudget."""

    def test_budget_total(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        budget = adapter.stream_budget()
        assert budget.total_dim == sum(s.dimensionality for s in budget.streams)
        assert len(budget.streams) == 6

    def test_budget_default_engine_cap(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        assert adapter.stream_budget().engine_max_dim == 30

    def test_budget_custom_engine_cap(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, engine_max_dim=50, seed=1)
        assert adapter.stream_budget().engine_max_dim == 50

    def test_budget_flags_truncation(self) -> None:
        """Default 5×5 satellite (75 floats) exceeds 30-dim cap."""
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        budget = adapter.stream_budget()
        assert budget.any_truncated
        sat = budget.streams[0]
        assert sat.exceeds_engine_cap

    def test_budget_no_truncation_with_small_zones(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=8,
            grid_cols=8,
            satellite_zone_rows=3,
            satellite_zone_cols=3,
            n_traps=5,
            n_weather_stations=1,
            n_soil_sensors=2,
            seed=1,
        )
        budget = adapter.stream_budget()
        assert not budget.any_truncated

    def test_budget_type(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        budget = adapter.stream_budget()
        assert isinstance(budget, DimBudget)


# ---------------------------------------------------------------------------
# Truncation warnings
# ---------------------------------------------------------------------------


class TestTruncationWarning:
    """Adapter emits warnings when streams exceed engine cap."""

    def test_warning_on_default_satellite(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        truncation_warnings = [x for x in w if "truncated" in str(x.message).lower()]
        assert len(truncation_warnings) >= 1
        assert "satellite_indices" in str(truncation_warnings[0].message)

    def test_no_warning_when_within_cap(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            GrainGuardAdapter(
                grid_rows=8,
                grid_cols=8,
                satellite_zone_rows=3,
                satellite_zone_cols=3,
                n_traps=5,
                n_weather_stations=1,
                n_soil_sensors=2,
                seed=1,
            )
        truncation_warnings = [x for x in w if "truncated" in str(x.message).lower()]
        assert len(truncation_warnings) == 0

    def test_warning_with_large_trap_fleet(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            GrainGuardAdapter(
                grid_rows=8,
                grid_cols=8,
                satellite_zone_rows=1,
                satellite_zone_cols=1,
                n_traps=20,
                seed=1,
            )
        truncation_warnings = [x for x in w if "truncated" in str(x.message).lower()]
        trap_warns = [x for x in truncation_warnings if "pheromone" in str(x.message).lower()]
        assert len(trap_warns) >= 1

    def test_no_warning_with_raised_cap(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            GrainGuardAdapter(grid_rows=8, grid_cols=8, engine_max_dim=200, seed=1)
        truncation_warnings = [x for x in w if "truncated" in str(x.message).lower()]
        assert len(truncation_warnings) == 0


# ---------------------------------------------------------------------------
# Pest threshold configurability
# ---------------------------------------------------------------------------


class TestPestThreshold:
    """Pest density threshold for ground truth is configurable."""

    def test_default_threshold(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        assert adapter.pest_threshold == 10.0

    def test_custom_threshold(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, pest_threshold=5.0, seed=1)
        assert adapter.pest_threshold == 5.0

    def test_lower_threshold_more_events(self) -> None:
        """Lower threshold should trigger more ground truth events."""
        low = GrainGuardAdapter(grid_rows=10, grid_cols=10, pest_threshold=2.0, seed=42)
        high = GrainGuardAdapter(grid_rows=10, grid_cols=10, pest_threshold=50.0, seed=42)
        events_low = 0
        events_high = 0
        for t in range(100):
            low.step(t)
            high.step(t)
            if low.get_ground_truth(t):
                events_low += 1
            if high.get_ground_truth(t):
                events_high += 1
        assert events_low >= events_high


# ---------------------------------------------------------------------------
# Cost coefficients configurability
# ---------------------------------------------------------------------------


class TestCostCoefficients:
    """Cost model uses configurable coefficients."""

    def test_default_costs(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        costs = adapter.compute_costs(n_escalations=10, n_correct=5, n_false_alarms=3, n_missed=2)
        assert costs["surveillance_cost"] == pytest.approx(10 * 0.3)
        assert costs["response_cost"] == pytest.approx(5 * 1.5 + 3 * 3.0)
        assert costs["damage_cost"] == pytest.approx(2 * 8.0)

    def test_custom_costs(self) -> None:
        cc = CostCoefficients(surveillance=1.0, response=2.0, false_alarm=5.0, missed=10.0)
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, cost_coefficients=cc, seed=1)
        costs = adapter.compute_costs(n_escalations=10, n_correct=5, n_false_alarms=3, n_missed=2)
        assert costs["surveillance_cost"] == pytest.approx(10 * 1.0)
        assert costs["response_cost"] == pytest.approx(5 * 2.0 + 3 * 5.0)
        assert costs["damage_cost"] == pytest.approx(2 * 10.0)

    def test_cost_coefficients_accessor(self) -> None:
        cc = CostCoefficients(surveillance=0.5)
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, cost_coefficients=cc, seed=1)
        assert adapter.cost_coefficients.surveillance == 0.5
        assert adapter.cost_coefficients.response == 1.5  # default

    def test_zero_costs(self) -> None:
        cc = CostCoefficients(surveillance=0, response=0, false_alarm=0, missed=0)
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, cost_coefficients=cc, seed=1)
        costs = adapter.compute_costs(n_escalations=10, n_correct=5, n_false_alarms=3, n_missed=2)
        assert all(v == 0.0 for v in costs.values())


# ---------------------------------------------------------------------------
# Engine max dim property
# ---------------------------------------------------------------------------


class TestEngineMaxDim:
    """engine_max_dim is exposed and configurable."""

    def test_default(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=1)
        assert adapter.engine_max_dim == DEFAULT_ENGINE_MAX_DIM

    def test_custom(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, engine_max_dim=64, seed=1)
        assert adapter.engine_max_dim == 64


# ---------------------------------------------------------------------------
# Backward compatibility: positional args still work
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Existing code using positional args still works."""

    def test_positional_grid_and_landscape(self) -> None:
        from grain_guard.environment.field import LandscapeType

        adapter = GrainGuardAdapter(10, 10, LandscapeType.ORCHARD, seed=1)
        assert adapter.field.rows == 10
        assert adapter.field.cols == 10

    def test_old_keyword_args_still_work(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=8,
            grid_cols=8,
            n_traps=5,
            n_weather_stations=1,
            n_soil_sensors=2,
            satellite_revisit=3,
            seed=1,
        )
        assert len(adapter._traps) == 5
        assert len(adapter._weather_stations) == 1
        assert len(adapter._soil_sensors) == 2
