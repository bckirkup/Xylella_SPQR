"""Per-Tot spray tank capacity: physical scarcity, refills, and its boundary.

These tests pin the mechanism the phase-2 tank measurement rests on: targeted
applications are limited by what a drone carries, a drone that runs dry pays a
refill trip in travel and downtime, and none of that reaches the detectors as
ground truth. Broadcast passes stay available on purpose, because capping
field-wide pesticide load is what the superseded global quota did wrong.
"""

from __future__ import annotations

import argparse

import pytest

from grain_guard.adapter.grain_adapter import DispatchTarget, GrainGuardAdapter
from grain_guard.analysis.arms import ArmSpec, domain_config, sprayer_fleet_config
from grain_guard.analysis.fleet_options import (
    add_sprayer_fleet_arguments,
    sprayer_fleet_config_from_args,
)
from grain_guard.equipment.sprayer_fleet import SprayerFleet, SprayerFleetConfig


def _adapter(**fleet: object) -> GrainGuardAdapter:
    """Adapter on a small field whose drones carry exactly what a test needs."""
    return GrainGuardAdapter(grid_rows=4, grid_cols=4, seed=7, sprayer_fleet_config=fleet)


class TestTankConfig:
    @pytest.mark.parametrize(
        "config",
        [
            {"n_spot_sprayers": 0},
            {"applications_per_step": 0},
            {"liters_per_application": 0.0},
            {"spot_tank_liters": 0.0},
            {"refill_duration_steps": -1},
        ],
    )
    def test_rejects_unphysical_equipment(self, config: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            SprayerFleetConfig.model_validate(config)

    def test_rejects_a_dose_larger_than_the_tank(self) -> None:
        with pytest.raises(ValueError):
            SprayerFleetConfig(spot_tank_liters=1.0, liters_per_application=2.0)

    def test_tank_volumes_default_to_the_body_plans(self) -> None:
        config = SprayerFleetConfig()
        assert config.resolved_spot_tank_liters > config.liters_per_application
        assert config.resolved_broadcast_tank_liters > config.resolved_spot_tank_liters

    def test_refill_point_defaults_to_mid_field(self) -> None:
        fleet = SprayerFleet(config=SprayerFleetConfig(), rows=20, cols=20)
        boom = fleet.boom_sprayer
        assert boom is not None
        assert (boom.row, boom.col) == (10, 10)


class TestTankScarcity:
    def test_tank_volume_grades_applications_served(self) -> None:
        served: list[int] = []
        for tank_liters in (2.0, 4.0, 6.0):
            adapter = _adapter(
                n_spot_sprayers=1,
                spot_tank_liters=tank_liters,
                liters_per_application=2.0,
                applications_per_step=4,
            )
            served.append(sum(adapter.dispatch_spray(0, col) for col in range(4)))
        assert served == [1, 2, 3]

    def test_a_spent_application_is_unavailable_to_the_next_cell(self) -> None:
        adapter = _adapter(
            n_spot_sprayers=1,
            spot_tank_liters=2.0,
            liters_per_application=2.0,
            applications_per_step=4,
        )
        assert adapter.dispatch_spray(0, 0)
        pest_before = adapter.field.pests[0][1].density
        beneficial_before = adapter.field.biological_control[1]
        assert not adapter.dispatch_spray(0, 1)
        assert adapter.field.pests[0][1].density == pytest.approx(pest_before)
        assert adapter.field.biological_control[1] == pytest.approx(beneficial_before)

    def test_the_working_beat_limits_applications_within_one_step(self) -> None:
        adapter = _adapter(n_spot_sprayers=1, applications_per_step=2)
        results = [adapter.dispatch_spray(0, col) for col in range(4)]
        assert results == [True, True, False, False]
        metrics = adapter.sprayer_fleet_metrics
        assert metrics is not None
        assert metrics["spot_denied_worked_out"] == 2
        assert metrics["spot_denied_empty"] == 0

    def test_a_new_step_restores_the_working_beat(self) -> None:
        adapter = _adapter(n_spot_sprayers=1, applications_per_step=1)
        assert adapter.dispatch_spray(0, 0)
        assert not adapter.dispatch_spray(0, 1)
        adapter.step(1)
        assert adapter.dispatch_spray(0, 1)


class TestRefills:
    def test_an_empty_drone_leaves_for_a_refill_and_returns_loaded(self) -> None:
        adapter = _adapter(
            n_spot_sprayers=1,
            spot_tank_liters=2.0,
            liters_per_application=2.0,
            refill_duration_steps=2,
            refill_row=0,
            refill_col=0,
        )
        assert adapter.dispatch_spray(0, 0)
        assert not adapter.dispatch_spray(1, 1)
        adapter.step(1)
        assert not adapter.dispatch_spray(1, 1)
        adapter.step(2)
        assert adapter.dispatch_spray(1, 1)
        metrics = adapter.sprayer_fleet_metrics
        assert metrics is not None
        assert metrics["refills"] == 1
        assert metrics["spot_denied_empty"] == 1
        assert metrics["spot_denied_refilling"] == 1
        assert metrics["final_mean_tank_share"] == pytest.approx(0.0)

    def test_refill_travel_lengthens_the_downtime(self) -> None:
        downtimes: list[int] = []
        for refill_col in (0, 3):
            adapter = GrainGuardAdapter(
                grid_rows=4,
                grid_cols=4,
                seed=7,
                sprayer_fleet_config={
                    "n_spot_sprayers": 1,
                    "spot_tank_liters": 2.0,
                    "liters_per_application": 2.0,
                    "refill_duration_steps": 0,
                    "refill_row": 0,
                    "refill_col": refill_col,
                },
            )
            assert adapter.dispatch_spray(0, 0)
            assert not adapter.dispatch_spray(0, 0)
            downtime = 0
            for step in range(1, 12):
                adapter.step(step)
                if adapter.dispatch_spray(0, 0):
                    break
                downtime += 1
            downtimes.append(downtime)
        assert downtimes[1] > downtimes[0]

    def test_travel_is_accounted_in_distance_flown(self) -> None:
        adapter = _adapter(n_spot_sprayers=1, applications_per_step=4)
        assert adapter.dispatch_spray(0, 0)
        assert adapter.dispatch_spray(3, 3)
        metrics = adapter.sprayer_fleet_metrics
        assert metrics is not None
        assert metrics["cells_travelled"] > 0.0


class TestBroadcastIsNotCapped:
    def test_a_boom_pass_survives_drones_that_are_dry(self) -> None:
        adapter = _adapter(
            n_spot_sprayers=1,
            spot_tank_liters=2.0,
            liters_per_application=2.0,
        )
        assert adapter.dispatch_spray(0, 0)
        assert not adapter.dispatch_spray(0, 1)
        cells = [(row, col) for row in range(4) for col in range(4)]
        assert adapter.broadcast_spray(cells) == cells

    def test_the_boom_tops_up_at_the_headland_rather_than_refusing_cells(self) -> None:
        adapter = _adapter(broadcast_tank_liters=1.0, liters_per_broadcast_cell=0.5)
        cells = [(row, col) for row in range(4) for col in range(4)]
        assert adapter.broadcast_spray(cells) == cells
        metrics = adapter.sprayer_fleet_metrics
        assert metrics is not None
        assert metrics["broadcast_cells_denied"] == 0
        assert metrics["refills"] >= 1

    def test_headland_refill_off_makes_broadcast_volume_bind(self) -> None:
        adapter = _adapter(
            broadcast_tank_liters=1.0,
            liters_per_broadcast_cell=0.5,
            broadcast_headland_refill=False,
        )
        cells = [(row, col) for row in range(4) for col in range(4)]
        assert len(adapter.broadcast_spray(cells)) == 2


class TestScarcityMakesDetectionOrdinal:
    def test_the_last_application_goes_to_the_higher_published_threat(self) -> None:
        adapter = _adapter(
            n_spot_sprayers=1,
            spot_tank_liters=2.0,
            liters_per_application=2.0,
        )
        responder = adapter.get_responder_user_id()
        targets = [
            DispatchTarget(
                location=(0, 0),
                reports=[],
                responder_user_id=responder,
                cop_threat_level=0.2,
            ),
            DispatchTarget(
                location=(3, 3),
                reports=[],
                responder_user_id=responder,
                cop_threat_level=0.9,
            ),
        ]
        outcomes = adapter.dispatch_and_judge_responses(targets, time_step=0)
        assert [(outcome.location, outcome.dispatched) for outcome in outcomes] == [
            ((3, 3), True),
            ((0, 0), False),
        ]


class TestGroundTruthBoundary:
    def test_fleet_metrics_carry_no_pest_state(self) -> None:
        adapter = _adapter(n_spot_sprayers=2)
        adapter.dispatch_spray(0, 0)
        metrics = adapter.sprayer_fleet_metrics
        assert metrics is not None
        assert all(isinstance(value, (int, float)) for value in metrics.values())
        forbidden = ("pest", "density", "resistance", "beneficial", "truth", "health")
        assert not [key for key in metrics if any(word in key for word in forbidden)]

    def test_fleet_state_is_absent_from_detector_signals(self) -> None:
        adapter = _adapter(n_spot_sprayers=2)
        labels = " ".join(stream.label for stream in adapter.get_streams()).lower()
        assert "tank" not in labels
        assert "refill" not in labels
        assert "sprayer" not in labels


class TestFleetPlumbing:
    def test_unconfigured_fleet_leaves_dispatch_unlimited(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=1, grid_cols=2, seed=7)
        assert all(adapter.dispatch_spray(0, index % 2) for index in range(20))
        assert adapter.sprayer_fleet_metrics is None

    def test_arm_spec_omits_fleet_config_until_enabled(self) -> None:
        spec = ArmSpec(name="a", grounded_input_fraction=0.5, seed=1, steps=2)
        assert "sprayer_fleet_config" not in domain_config(spec)

    def test_arm_spec_forwards_only_the_overrides_it_sets(self) -> None:
        spec = ArmSpec(
            name="a",
            grounded_input_fraction=0.5,
            seed=1,
            steps=2,
            sprayer_fleet_enabled=True,
            spot_tank_liters=12.0,
            applications_per_step=3,
        )
        assert sprayer_fleet_config(spec) == {
            "spot_tank_liters": 12.0,
            "applications_per_step": 3,
        }
        assert domain_config(spec)["sprayer_fleet_config"] == sprayer_fleet_config(spec)

    def test_command_line_flags_build_the_same_config(self) -> None:
        parser = argparse.ArgumentParser()
        add_sprayer_fleet_arguments(parser)
        assert sprayer_fleet_config_from_args(parser.parse_args([])) is None
        config = sprayer_fleet_config_from_args(
            parser.parse_args(["--sprayer-fleet", "--applications-per-step", "3"])
        )
        assert config == SprayerFleetConfig(applications_per_step=3)
