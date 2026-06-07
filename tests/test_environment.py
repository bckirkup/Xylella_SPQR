"""Unit tests for environment models: crop, pest, weed, weather, field."""

from __future__ import annotations

import numpy as np
import pytest

from grain_guard.environment.crop import CropCell, CropType, GrowthStage
from grain_guard.environment.field import CropField, LandscapeType
from grain_guard.environment.pest import PestPopulation
from grain_guard.environment.weather import AgWeather
from grain_guard.environment.weed import WeedPopulation


class TestAgWeather:
    def test_gdd_positive(self) -> None:
        w = AgWeather(temperature=25.0)
        assert w.growing_degree_days == 15.0

    def test_gdd_zero_below_base(self) -> None:
        w = AgWeather(temperature=5.0)
        assert w.growing_degree_days == 0.0

    def test_spray_safe(self) -> None:
        w = AgWeather(wind_speed=3.0, precipitation=0.0)
        assert w.is_spray_safe

    def test_spray_unsafe_wind(self) -> None:
        w = AgWeather(wind_speed=12.0, precipitation=0.0)
        assert not w.is_spray_safe

    def test_spray_unsafe_rain(self) -> None:
        w = AgWeather(wind_speed=3.0, precipitation=5.0)
        assert not w.is_spray_safe

    def test_spray_drift_risk(self) -> None:
        w = AgWeather(wind_speed=7.5)
        assert 0.0 <= w.spray_drift_risk <= 1.0
        assert w.spray_drift_risk == pytest.approx(0.5, abs=0.01)

    def test_evapotranspiration_nonneg(self) -> None:
        w = AgWeather(temperature=25.0, solar_radiation=20.0)
        assert w.evapotranspiration_rate() >= 0.0


class TestCropCell:
    def test_initial_state(self) -> None:
        c = CropCell()
        assert c.growth_stage == GrowthStage.SEEDLING
        assert c.health == 1.0
        assert c.yield_potential == 1.0

    def test_phenology_advance(self) -> None:
        c = CropCell()
        c.advance_phenology(200.0)
        assert c.growth_stage == GrowthStage.VEGETATIVE

    def test_phenology_to_flowering(self) -> None:
        c = CropCell()
        c.advance_phenology(600.0)
        assert c.growth_stage == GrowthStage.FLOWERING

    def test_damage_reduces_health(self) -> None:
        c = CropCell()
        c.apply_damage(0.3)
        assert c.health == pytest.approx(0.7, abs=0.01)
        assert c.yield_potential < 1.0

    def test_ndvi_proxy_ranges(self) -> None:
        for stage in GrowthStage:
            c = CropCell(growth_stage=stage)
            assert 0.0 <= c.ndvi_proxy <= 1.0


class TestPestPopulation:
    def test_initial_density(self) -> None:
        p = PestPopulation()
        assert p.density == 0.0

    def test_growth(self) -> None:
        rng = np.random.default_rng(42)
        p = PestPopulation(density=5.0)
        p.grow(rng, crop_health=1.0)
        assert p.density > 5.0

    def test_pesticide_kills(self) -> None:
        rng = np.random.default_rng(42)
        p = PestPopulation(density=50.0, resistance_freq=0.0)
        killed = p.apply_pesticide(0.8, rng)
        assert killed > 0
        assert p.density < 50.0

    def test_resistance_increases_under_pressure(self) -> None:
        rng = np.random.default_rng(42)
        p = PestPopulation(density=50.0, resistance_freq=0.1)
        initial_r = p.resistance_freq
        p.apply_pesticide(0.9, rng)
        assert p.resistance_freq >= initial_r

    def test_detectability_range(self) -> None:
        p = PestPopulation(night_feeding=0.5, underside_preference=0.5)
        assert 0.0 <= p.detectability <= 1.0

    def test_disperse_bounded(self) -> None:
        rng = np.random.default_rng(42)
        p = PestPopulation(density=30.0)
        frac = p.disperse(5.0, rng)
        assert 0.0 <= frac <= 0.3


class TestWeedPopulation:
    def test_initial_density(self) -> None:
        w = WeedPopulation()
        assert w.density == 0.0

    def test_germination(self) -> None:
        rng = np.random.default_rng(42)
        w = WeedPopulation(seed_bank=100.0)
        w.grow(rng, soil_moisture=0.6)
        assert w.density > 0.0

    def test_herbicide_kills(self) -> None:
        rng = np.random.default_rng(42)
        w = WeedPopulation(density=30.0, resistance_freq=0.0)
        killed = w.apply_herbicide(0.8, rng)
        assert killed > 0
        assert w.density < 30.0

    def test_competition_factor_bounded(self) -> None:
        w = WeedPopulation(density=200.0)
        assert 0.0 <= w.competition_factor <= 0.3


class TestCropField:
    def test_initialization_monoculture(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.MONOCULTURE)
        assert len(f.crops) == 10
        assert len(f.crops[0]) == 10
        assert f.crops[0][0].crop_type == CropType.WHEAT

    def test_initialization_orchard(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.ORCHARD)
        assert f.crops[0][0].crop_type == CropType.APPLE
        cover_count = sum(1 for r in f.crops for c in r if c.is_cover_crop)
        assert cover_count > 0

    def test_initialization_intercrop(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.INTERCROP)
        types = {f.crops[r][c].crop_type for r in range(10) for c in range(10)}
        assert len(types) > 1

    def test_step_runs(self) -> None:
        rng = np.random.default_rng(42)
        f = CropField(rows=5, cols=5)
        w = AgWeather(temperature=25.0, precipitation=1.0)
        f.step(w, rng)

    def test_pest_introduction(self) -> None:
        rng = np.random.default_rng(42)
        f = CropField(rows=10, cols=10)
        f.stochastic_pest_introduction(rng, probability=1.0)
        edge_pests = sum(
            f.pests[r][c].density
            for r in range(10)
            for c in range(10)
            if r == 0 or r == 9 or c == 0 or c == 9
        )
        assert edge_pests > 0

    def test_mean_crop_health_initial(self) -> None:
        f = CropField(rows=5, cols=5)
        assert f.mean_crop_health() == pytest.approx(1.0)

    def test_mean_yield_potential_initial(self) -> None:
        f = CropField(rows=5, cols=5)
        assert f.mean_yield_potential() == pytest.approx(1.0)
