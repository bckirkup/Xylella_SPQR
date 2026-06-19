"""Unit tests for the GrainGuard TattleTots adapter."""

from __future__ import annotations

import numpy as np

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

    def test_ground_truth_bool(self) -> None:
        adapter = GrainGuardAdapter()
        adapter.step(0)
        result = adapter.get_ground_truth(0)
        assert isinstance(result, bool)

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
        low = GrainGuardAdapter(
            grid_rows=10, grid_cols=10, seed=42, pest_intro_probability=0.0
        )
        high = GrainGuardAdapter(
            grid_rows=10, grid_cols=10, seed=42, pest_intro_probability=1.0
        )
        for step in range(5):
            low.step(step)
            high.step(step)
        assert high.field.total_pest_density() >= low.field.total_pest_density()

    def test_resistance_initial_frequency(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=5, grid_cols=5, seed=1, resistance_initial_frequency=0.5
        )
        assert adapter.field.pests[0][0].resistance_freq == 0.5
