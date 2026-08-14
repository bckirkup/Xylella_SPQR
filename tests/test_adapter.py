"""Unit tests for the GrainGuard TattleTots adapter."""

from __future__ import annotations

import numpy as np
from tattletots.models.dispatch_target import DispatchTarget
from tattletots.models.report import Report

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType


class TestGrainGuardAdapter:
    def test_get_streams(self) -> None:
        adapter = GrainGuardAdapter()
        streams = adapter.get_streams()
        assert len(streams) == 4
        for s in streams:
            assert s.dimensionality > 0

    def test_get_users(self) -> None:
        adapter = GrainGuardAdapter()
        users = adapter.get_users()
        assert len(users) == 2

    def test_step_updates_streams(self) -> None:
        adapter = GrainGuardAdapter()
        adapter.step(0)
        for s in adapter.get_streams():
            assert s.current_data.size > 0

    def test_streams_publish_static_geometry_and_statuses(self) -> None:
        adapter = GrainGuardAdapter()
        streams = adapter.get_streams()
        assert adapter.get_location_frame() == ((0, 0), (19, 19))
        assert all(stream.metadata is not None for stream in streams)
        satellite, traps, weather, soil = streams
        assert satellite.metadata is not None
        assert satellite.metadata.sensor_coordinates is not None
        assert all(coordinate is not None for coordinate in satellite.metadata.sensor_coordinates)
        assert satellite.metadata.footprints is not None
        assert all(
            footprint is not None and footprint[0] > 1.0
            for footprint in satellite.metadata.footprints
        )
        assert traps.metadata is not None
        assert traps.metadata.sensor_coordinates is not None
        assert weather.metadata is not None
        assert weather.metadata.sensor_coordinates is not None
        assert soil.metadata is not None
        assert soil.metadata.sensor_coordinates is not None

        adapter.step(0)
        assert np.all(satellite.current_status == "observed")
        adapter.step(1)
        assert np.all(satellite.current_status == "missing")
        assert all(coordinate is None for coordinate in satellite.metadata.coordinates or [])
        assert all(coordinate is not None for coordinate in satellite.metadata.sensor_coordinates)

    def test_metadata_and_statuses_ignore_pest_state(self) -> None:
        low = GrainGuardAdapter(seed=42)
        high = GrainGuardAdapter(seed=42)
        for row in range(high.field.rows):
            for col in range(high.field.cols):
                high.field.pests[row][col].density = 100.0

        for time_step in (0, 1):
            low.step(time_step)
            high.step(time_step)
            for low_stream, high_stream in zip(low.get_streams(), high.get_streams(), strict=True):
                assert low_stream.metadata == high_stream.metadata
                np.testing.assert_array_equal(
                    low_stream.current_status,
                    high_stream.current_status,
                )

    def test_ground_truth_bool(self) -> None:
        adapter = GrainGuardAdapter()
        adapter.step(0)
        result = adapter.get_ground_truth(0)
        assert isinstance(result, bool)

    def test_decoder_uses_trap_geometry(self) -> None:
        adapter = GrainGuardAdapter(seed=42)
        data = np.zeros(20)
        data[2 * 2 + 1] = 1.0
        expected = (adapter._traps[2].row, adapter._traps[2].col)
        assert adapter.infer_report_location([data], ["pheromone_traps"]) == expected

    def test_decoder_uses_satellite_zone_geometry(self) -> None:
        adapter = GrainGuardAdapter(seed=42)
        data = np.zeros(75)
        data[7 * 3 + 2] = 1.0
        zone_row, zone_col = adapter._zone_indices()[7]
        center = adapter._zone_geometry(zone_row, zone_col)[0]
        expected = (int(round(center[0])), int(round(center[1])))
        assert adapter.infer_report_location([data], ["satellite_indices"]) == expected

    def test_decoder_prioritizes_trap_geometry_over_satellite_fallback(self) -> None:
        adapter = GrainGuardAdapter(seed=42)
        satellite = np.zeros(75)
        satellite[0] = 1.0
        traps = np.zeros(20)
        traps[2 * 2] = 2.0
        expected = (adapter._traps[2].row, adapter._traps[2].col)
        assert (
            adapter.infer_report_location(
                [satellite, traps],
                ["satellite_indices", "pheromone_traps"],
            )
            == expected
        )

    def test_score_relevance(self) -> None:
        adapter = GrainGuardAdapter()
        users = adapter.get_users()
        dim = sum(s.dimensionality for s in adapter.get_streams())
        signal = np.random.default_rng(42).standard_normal(dim)
        score = adapter.score_relevance(signal, users[0])
        assert isinstance(score, float)

    def test_compute_costs(self) -> None:
        adapter = GrainGuardAdapter()
        costs = adapter.compute_costs(n_escalations=5, n_correct=3, n_false_alarms=1, n_missed=2)
        assert "surveillance_cost" in costs
        assert "response_cost" in costs
        assert "damage_cost" in costs
        assert costs["damage_cost"] > costs["surveillance_cost"]

    def test_landscape_variants(self) -> None:
        for ls in LandscapeType:
            adapter = GrainGuardAdapter(landscape=ls, grid_rows=10, grid_cols=10)
            adapter.step(0)

    def test_multi_step(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10)
        for step in range(50):
            adapter.step(step)
        assert adapter.field.mean_crop_health() > 0


class TestAdapterProperties:
    def test_field_property(self) -> None:
        adapter = GrainGuardAdapter()
        assert adapter.field is not None

    def test_weather_property(self) -> None:
        adapter = GrainGuardAdapter()
        adapter.step(0)
        assert adapter.weather is not None

    def test_pest_intro_probability(self) -> None:
        low = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42, pest_intro_probability=0.0)
        high = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42, pest_intro_probability=1.0)
        for step in range(5):
            low.step(step)
            high.step(step)
        assert high.field.total_pest_density() >= low.field.total_pest_density()

    def test_resistance_initial_frequency(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=5, grid_cols=5, seed=1, resistance_initial_frequency=0.5
        )
        assert adapter.field.pests[0][0].resistance_freq == 0.5

    def test_dispatch_and_judge_necessary_spray(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, pest_threshold=10.0)
        adapter.field.pests[3][3].density = 20.0
        users = adapter.get_users()
        report = Report(
            agent_id="agent-1",
            target_user_id=users[0].id,
            time_step=0,
            signal_vector=np.ones(10),
            confidence=0.9,
            anomaly_score=2.0,
            location=(3, 3),
            verified=True,
            correct=True,
        )
        outcomes = adapter.dispatch_and_judge_responses(
            [
                DispatchTarget(
                    location=(3, 3),
                    reports=[report],
                    responder_user_id=adapter.get_responder_user_id(),
                    cop_threat_level=2.0,
                )
            ],
            0,
        )
        assert len(outcomes) == 1
        assert outcomes[0].dispatched
        assert outcomes[0].response_necessary

    def test_dispatch_and_judge_unnecessary_below_threshold(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, pest_threshold=10.0)
        adapter.field.pests[1][1].density = 2.0
        users = adapter.get_users()
        report = Report(
            agent_id="agent-1",
            target_user_id=users[0].id,
            time_step=0,
            signal_vector=np.ones(10),
            confidence=0.9,
            anomaly_score=2.0,
            location=(1, 1),
            verified=True,
            correct=True,
        )
        outcomes = adapter.dispatch_and_judge_responses(
            [
                DispatchTarget(
                    location=(1, 1),
                    reports=[report],
                    responder_user_id=adapter.get_responder_user_id(),
                    cop_threat_level=2.0,
                )
            ],
            0,
        )
        assert len(outcomes) == 1
        assert outcomes[0].dispatched
        assert not outcomes[0].response_necessary
