"""Smoke tests: end-to-end GrainGuard adapter simulation (spec §10)."""

from __future__ import annotations

import pytest

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType


@pytest.mark.smoke
class TestSmokeSimulation:
    """End-to-end simulation smoke tests.

    These validate that the full pipeline runs without errors and
    produces reasonable outputs for each landscape variant.
    """

    def test_monoculture_200_steps(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=15, grid_cols=15, landscape=LandscapeType.MONOCULTURE, seed=42
        )
        for step in range(200):
            adapter.step(step)
        assert adapter.field.mean_crop_health() > 0.0
        assert adapter.field.mean_yield_potential() > 0.0

    def test_orchard_100_steps(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=10, grid_cols=10, landscape=LandscapeType.ORCHARD, seed=42
        )
        for step in range(100):
            adapter.step(step)
        assert adapter.field.mean_crop_health() > 0.0

    def test_intercrop_100_steps(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=10, grid_cols=10, landscape=LandscapeType.INTERCROP, seed=42
        )
        for step in range(100):
            adapter.step(step)
        assert adapter.field.mean_crop_health() > 0.0

    def test_streams_populated(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        for step in range(20):
            adapter.step(step)
        for s in adapter.get_streams():
            assert s.current_data.size > 0

    def test_ground_truth_triggers(self) -> None:
        """Over enough steps, pests should accumulate and trigger events."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        events = 0
        for step in range(300):
            adapter.step(step)
            if adapter.get_ground_truth(step):
                events += 1
        assert events > 0
