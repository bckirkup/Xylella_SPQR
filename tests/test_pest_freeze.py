"""Tests for the pest-evolution freeze used in detector-side measurements."""

from __future__ import annotations

import numpy as np
import pytest

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import CropField, LandscapeType
from grain_guard.environment.pest import PestPopulation
from grain_guard.runner import adapter_kwargs_from_config

PESTICIDE_APPLICATIONS = 20
DETECTION_PRESSURE = 0.8


def _pest(*, frozen: bool) -> PestPopulation:
    return PestPopulation(density=10.0, evolution_frozen=frozen)


class TestPestFreeze:
    def test_resistance_frozen_stays_exactly_constant(self) -> None:
        pest = _pest(frozen=True)
        rng = np.random.default_rng(7)
        start = pest.resistance_freq
        for _ in range(PESTICIDE_APPLICATIONS):
            pest.apply_pesticide(0.9, rng)
        assert pest.resistance_freq == pytest.approx(start, abs=0.0)

    def test_resistance_unfrozen_moves_under_pressure(self) -> None:
        pest = _pest(frozen=False)
        rng = np.random.default_rng(7)
        start = pest.resistance_freq
        for _ in range(PESTICIDE_APPLICATIONS):
            pest.apply_pesticide(0.9, rng)
        assert pest.resistance_freq > start

    def test_behavior_frozen_stays_exactly_constant(self) -> None:
        pest = _pest(frozen=True)
        rng = np.random.default_rng(11)
        before = (pest.night_feeding, pest.underside_preference, pest.edge_refuge)
        for _ in range(pest.generation_time * 3):
            pest.evolve_behavior(rng, DETECTION_PRESSURE)
        after = (pest.night_feeding, pest.underside_preference, pest.edge_refuge)
        assert after == before

    def test_behavior_unfrozen_responds_to_detection_pressure(self) -> None:
        pest = _pest(frozen=False)
        rng = np.random.default_rng(11)
        before = pest.night_feeding
        for _ in range(pest.generation_time * 3):
            pest.evolve_behavior(rng, DETECTION_PRESSURE)
        assert pest.night_feeding > before

    def test_freeze_consumes_the_same_random_draws(self) -> None:
        """A frozen pest must not desynchronize the shared RNG stream."""
        results: list[float] = []
        for frozen in (True, False):
            pest = _pest(frozen=frozen)
            rng = np.random.default_rng(3)
            for _ in range(pest.generation_time * 2):
                pest.evolve_behavior(rng, DETECTION_PRESSURE)
            pest.apply_pesticide(0.5, rng)
            results.append(float(rng.normal(0, 1)))
        assert results[0] == pytest.approx(results[1], abs=0.0)

    def test_density_still_responds_when_frozen(self) -> None:
        """Freezing heritable traits must not freeze ecology."""
        pest = _pest(frozen=True)
        rng = np.random.default_rng(5)
        start = pest.density
        for _ in range(10):
            pest.grow(rng, crop_health=1.0)
        assert pest.density > start


class TestFieldFreezePropagation:
    def test_field_flag_reaches_every_cell(self) -> None:
        field = CropField(rows=4, cols=4, freeze_pest_evolution=True)
        assert all(pest.evolution_frozen for row in field.pests for pest in row)

    def test_default_field_is_not_frozen(self) -> None:
        field = CropField(rows=4, cols=4)
        assert not field.freeze_pest_evolution
        assert not any(pest.evolution_frozen for row in field.pests for pest in row)

    def test_apply_freeze_toggles_cells(self) -> None:
        field = CropField(rows=3, cols=3)
        field.apply_pest_evolution_freeze(True)
        assert all(pest.evolution_frozen for row in field.pests for pest in row)
        field.apply_pest_evolution_freeze(False)
        assert not any(pest.evolution_frozen for row in field.pests for pest in row)


class TestAdapterFreeze:
    def test_adapter_exposes_and_applies_freeze(self) -> None:
        adapter = GrainGuardAdapter(
            grid_rows=6,
            grid_cols=6,
            landscape=LandscapeType.MONOCULTURE,
            seed=42,
            freeze_pest_evolution=True,
        )
        assert adapter.pest_evolution_frozen
        assert all(pest.evolution_frozen for row in adapter.field.pests for pest in row)

    def test_adapter_default_evolves(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=6, grid_cols=6, seed=42)
        assert not adapter.pest_evolution_frozen

    def test_frozen_traits_hold_across_a_simulated_season(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=42, freeze_pest_evolution=True)
        before = [
            (pest.night_feeding, pest.underside_preference, pest.resistance_freq)
            for row in adapter.field.pests
            for pest in row
        ]
        for step in range(120):
            adapter.step(step)
        after = [
            (pest.night_feeding, pest.underside_preference, pest.resistance_freq)
            for row in adapter.field.pests
            for pest in row
        ]
        assert after == before


class TestRunnerConfigPlumbing:
    def test_freeze_flag_is_read_from_domain_config(self) -> None:
        kwargs = adapter_kwargs_from_config({"freeze_pest_evolution": True})
        assert kwargs == {"freeze_pest_evolution": True}

    def test_absent_keys_keep_adapter_defaults(self) -> None:
        assert adapter_kwargs_from_config({}) == {}

    def test_typed_keys_are_coerced(self) -> None:
        kwargs = adapter_kwargs_from_config(
            {"n_traps": "12", "pest_threshold": "10", "freeze_pest_evolution": 0}
        )
        assert kwargs["n_traps"] == 12
        assert kwargs["pest_threshold"] == pytest.approx(10.0)
        assert kwargs["freeze_pest_evolution"] is False
