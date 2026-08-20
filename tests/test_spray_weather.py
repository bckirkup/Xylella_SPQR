"""Weather-gated efficacy: wind refuses an application, rain washes it off.

These tests pin the mechanism the phase-2 weather measurement rests on. Wind
above the label cut-off refuses the spray before any product is drawn, rain
grades down the dose that reaches the pest, and a weather refusal changes
nothing about the field or the detectors' view of it.
"""

from __future__ import annotations

import argparse

import pytest

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.analysis.arms import ArmSpec, domain_config, spray_weather_config
from grain_guard.analysis.weather_options import (
    add_spray_weather_arguments,
    spray_weather_config_from_args,
)
from grain_guard.environment.spray_weather import SprayWeatherConfig, SprayWeatherGate
from grain_guard.environment.weather import AgWeather


def _weather(*, wind_speed: float = 0.0, precipitation: float = 0.0) -> AgWeather:
    """Weather that differs from a calm dry day only where a test says so."""
    return AgWeather(wind_speed=wind_speed, precipitation=precipitation)


def _adapter(
    *,
    wind_speed: float = 0.0,
    precipitation: float = 0.0,
    gate: dict[str, object] | None = None,
    fleet: dict[str, object] | None = None,
) -> GrainGuardAdapter:
    """Adapter on a small field under weather a test fixes for itself."""
    adapter = GrainGuardAdapter(
        grid_rows=4,
        grid_cols=4,
        seed=7,
        spray_weather_config=gate if gate is not None else {},
        sprayer_fleet_config=fleet,
    )
    adapter.weather = _weather(wind_speed=wind_speed, precipitation=precipitation)
    return adapter


class TestWeatherGateConfig:
    @pytest.mark.parametrize(
        "config",
        [
            {"wind_block_speed_mps": 0.0},
            {"wind_block_speed_mps": -1.0},
            {"rain_washoff_full_mm": 0.0},
            {"washoff_strength": -0.1},
            {"washoff_strength": 1.1},
        ],
    )
    def test_rejects_unphysical_settings(self, config: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            SprayWeatherConfig.model_validate(config)

    def test_defaults_allow_a_calm_dry_day_at_full_strength(self) -> None:
        gate = SprayWeatherGate()
        assert gate.effective_efficacy(0.8, _weather()) == pytest.approx(0.8)


class TestWindBlocksApplication:
    @pytest.mark.parametrize(
        ("wind_speed", "allowed"),
        [(0.0, True), (5.9, True), (6.0, False), (12.0, False)],
    )
    def test_wind_at_or_above_the_cut_off_refuses_the_spray(
        self, wind_speed: float, allowed: bool
    ) -> None:
        gate = SprayWeatherGate(SprayWeatherConfig(wind_block_speed_mps=6.0))
        assert (
            gate.effective_efficacy(0.8, _weather(wind_speed=wind_speed)) is not None
        ) is allowed

    def test_the_cut_off_moves_with_its_setting(self) -> None:
        wind = _weather(wind_speed=5.0)
        strict = SprayWeatherGate(SprayWeatherConfig(wind_block_speed_mps=4.0))
        lenient = SprayWeatherGate(SprayWeatherConfig(wind_block_speed_mps=9.0))
        assert strict.effective_efficacy(0.8, wind) is None
        assert lenient.effective_efficacy(0.8, wind) == pytest.approx(0.8)

    def test_a_wind_refusal_leaves_the_field_untouched(self) -> None:
        adapter = _adapter(wind_speed=9.0)
        pest_before = adapter.field.pests[0][0].density
        beneficial_before = adapter.field.biological_control[0]
        assert not adapter.dispatch_spray(0, 0)
        assert adapter.field.pests[0][0].density == pytest.approx(pest_before)
        assert adapter.field.biological_control[0] == pytest.approx(beneficial_before)

    def test_a_wind_refusal_does_not_draw_product_from_the_tank(self) -> None:
        adapter = _adapter(wind_speed=9.0, fleet={"n_spot_sprayers": 1})
        assert not adapter.dispatch_spray(0, 0)
        fleet_metrics = adapter.sprayer_fleet_metrics
        assert fleet_metrics is not None
        assert fleet_metrics["spot_granted"] == 0
        assert fleet_metrics["liters_applied"] == pytest.approx(0.0)

    def test_wind_refuses_a_whole_boom_pass_at_once(self) -> None:
        adapter = _adapter(wind_speed=9.0, fleet={"n_spot_sprayers": 1})
        cells = [(row, col) for row in range(4) for col in range(4)]
        assert adapter.broadcast_spray(cells) == []
        budget = adapter.spray_budget_metrics
        assert budget["denied"] == len(cells)
        weather_metrics = adapter.spray_weather_metrics
        assert weather_metrics is not None
        assert weather_metrics["requests"] == 1
        assert weather_metrics["wind_blocked"] == 1


class TestRainWashesOffTheDose:
    @pytest.mark.parametrize(
        ("precipitation", "retained"),
        [(0.0, 1.0), (1.0, 0.75), (2.0, 0.5), (3.0, 0.25)],
    )
    def test_rain_grades_the_dose_that_survives(
        self, precipitation: float, retained: float
    ) -> None:
        gate = SprayWeatherGate(SprayWeatherConfig(rain_washoff_full_mm=4.0))
        assert gate.retained_fraction(_weather(precipitation=precipitation)) == pytest.approx(
            retained
        )

    def test_rain_heavy_enough_to_waste_the_whole_dose_refuses_the_spray(self) -> None:
        gate = SprayWeatherGate(SprayWeatherConfig(rain_washoff_full_mm=4.0))
        assert gate.effective_efficacy(0.8, _weather(precipitation=4.0)) is None
        assert gate.counters.rain_blocked == 1

    def test_a_weaker_wash_off_leaves_a_floor_no_rain_can_pass(self) -> None:
        gate = SprayWeatherGate(SprayWeatherConfig(rain_washoff_full_mm=4.0, washoff_strength=0.5))
        assert gate.effective_efficacy(0.8, _weather(precipitation=99.0)) == pytest.approx(0.4)

    def test_wash_off_strength_grades_the_efficacy_applied(self) -> None:
        weather = _weather(precipitation=2.0)
        applied = [
            SprayWeatherGate(
                SprayWeatherConfig(rain_washoff_full_mm=4.0, washoff_strength=strength)
            ).effective_efficacy(0.8, weather)
            for strength in (0.0, 0.5, 1.0)
        ]
        assert applied == [pytest.approx(0.8), pytest.approx(0.6), pytest.approx(0.4)]

    def test_rain_leaves_more_pests_alive_than_a_dry_application(self) -> None:
        survivors: list[float] = []
        for precipitation in (0.0, 2.0):
            adapter = _adapter(precipitation=precipitation)
            adapter.field.pests[0][0].density = 200.0
            assert adapter.dispatch_spray(0, 0)
            survivors.append(adapter.field.pests[0][0].density)
        assert survivors[1] > survivors[0]


class TestWeatherGateBookkeeping:
    def test_counters_split_refusals_by_cause_and_track_retention(self) -> None:
        gate = SprayWeatherGate(
            SprayWeatherConfig(wind_block_speed_mps=6.0, rain_washoff_full_mm=4.0)
        )
        gate.effective_efficacy(0.8, _weather())
        gate.effective_efficacy(0.8, _weather(precipitation=2.0))
        gate.effective_efficacy(0.8, _weather(wind_speed=7.0))
        gate.effective_efficacy(0.8, _weather(precipitation=5.0))
        metrics = gate.metrics()
        assert metrics["requests"] == 4
        assert metrics["wind_blocked"] == 1
        assert metrics["rain_blocked"] == 1
        assert metrics["allowed"] == 2
        assert metrics["washed"] == 1
        assert metrics["allowed_share"] == pytest.approx(0.5)
        assert metrics["mean_retained_efficacy"] == pytest.approx(0.75)

    def test_an_unused_gate_reports_no_retention_rather_than_a_division(self) -> None:
        metrics = SprayWeatherGate().metrics()
        assert metrics["requests"] == 0
        assert metrics["mean_retained_efficacy"] == pytest.approx(0.0)
        assert metrics["allowed_share"] == pytest.approx(0.0)


class TestGroundTruthBoundary:
    def test_weather_gate_metrics_carry_no_field_state(self) -> None:
        adapter = _adapter()
        adapter.dispatch_spray(0, 0)
        metrics = adapter.spray_weather_metrics
        assert metrics is not None
        assert all(isinstance(value, (int, float)) for value in metrics.values())
        forbidden = ("pest", "density", "resistance", "beneficial", "truth", "health")
        assert not [key for key in metrics if any(word in key for word in forbidden)]

    def test_gate_state_is_absent_from_detector_signals(self) -> None:
        adapter = _adapter()
        adapter.dispatch_spray(0, 0)
        labels = " ".join(stream.label for stream in adapter.get_streams()).lower()
        assert "washoff" not in labels
        assert "blocked" not in labels
        assert "refused" not in labels


class TestWeatherPlumbing:
    def test_an_unconfigured_gate_leaves_weather_irrelevant(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=4, grid_cols=4, seed=7)
        adapter.weather = _weather(wind_speed=30.0, precipitation=50.0)
        assert adapter.dispatch_spray(0, 0)
        assert adapter.spray_weather_metrics is None

    def test_arm_spec_omits_weather_config_until_enabled(self) -> None:
        spec = ArmSpec(name="a", grounded_input_fraction=0.5, seed=1, steps=2)
        assert "spray_weather_config" not in domain_config(spec)

    def test_arm_spec_forwards_only_the_overrides_it_sets(self) -> None:
        spec = ArmSpec(
            name="a",
            grounded_input_fraction=0.5,
            seed=1,
            steps=2,
            spray_weather_enabled=True,
            wind_block_speed_mps=5.0,
        )
        assert spray_weather_config(spec) == {"wind_block_speed_mps": 5.0}
        assert domain_config(spec)["spray_weather_config"] == spray_weather_config(spec)

    def test_command_line_flags_build_the_same_config(self) -> None:
        parser = argparse.ArgumentParser()
        add_spray_weather_arguments(parser)
        assert spray_weather_config_from_args(parser.parse_args([])) is None
        config = spray_weather_config_from_args(
            parser.parse_args(["--spray-weather", "--wind-block-speed", "5"])
        )
        assert config is not None
        assert config.wind_block_speed_mps == pytest.approx(5.0)
        assert config.rain_washoff_full_mm == pytest.approx(
            SprayWeatherConfig().rain_washoff_full_mm
        )
