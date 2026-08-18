"""Unit tests for environment models: crop, pest, weed, weather, field."""

from __future__ import annotations

import numpy as np
import pytest

from grain_guard.environment.crop import CropCell, CropType, GrowthStage
from grain_guard.environment.field import CropField, EcologyConfig, LandscapeType
from grain_guard.environment.pest import PestPopulation
from grain_guard.environment.weather import AgWeather
from grain_guard.environment.weed import WeedPopulation


class TestAgWeather:
    def test_gdd_positive(self) -> None:
        w = AgWeather(temperature=25.0)
        assert w.growing_degree_days == pytest.approx(15.0, rel=0.0, abs=1e-12)

    def test_gdd_zero_below_base(self) -> None:
        w = AgWeather(temperature=5.0)
        assert w.growing_degree_days == pytest.approx(0.0, rel=0.0, abs=1e-12)

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
        assert c.health == pytest.approx(1.0, rel=0.0, abs=1e-12)
        assert c.yield_potential == pytest.approx(1.0, rel=0.0, abs=1e-12)

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
        assert p.density == pytest.approx(0.0, rel=0.0, abs=1e-12)

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
        assert w.density == pytest.approx(0.0, rel=0.0, abs=1e-12)

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

    def test_orchard_pest_species_diversity(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.ORCHARD)
        species = {f.pests[r][c].species for r in range(10) for c in range(10)}
        assert len(species) >= 2

    def test_intercrop_pest_species_diversity(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.INTERCROP)
        species = {f.pests[r][c].species for r in range(10) for c in range(10)}
        assert len(species) >= 3

    def test_intercrop_weed_species_diversity(self) -> None:
        f = CropField(rows=10, cols=10, landscape=LandscapeType.INTERCROP)
        species = {f.weeds[r][c].species for r in range(10) for c in range(10)}
        assert len(species) >= 3

    def test_landscape_modifiers_differ(self) -> None:
        mono = CropField(rows=5, cols=5, landscape=LandscapeType.MONOCULTURE)
        orch = CropField(rows=5, cols=5, landscape=LandscapeType.ORCHARD)
        inter = CropField(rows=5, cols=5, landscape=LandscapeType.INTERCROP)
        assert mono._landscape_pest_growth_modifier != orch._landscape_pest_growth_modifier
        assert mono._landscape_weed_growth_modifier != inter._landscape_weed_growth_modifier
        assert orch._landscape_biocontrol_boost > mono._landscape_biocontrol_boost

    def test_landscape_differentiation_after_steps(self) -> None:
        """Different landscapes must produce different pest/crop dynamics."""
        rng_m = np.random.default_rng(42)
        rng_o = np.random.default_rng(42)
        rng_i = np.random.default_rng(42)
        w = AgWeather(temperature=25.0, precipitation=1.0)

        mono = CropField(rows=10, cols=10, landscape=LandscapeType.MONOCULTURE)
        orch = CropField(rows=10, cols=10, landscape=LandscapeType.ORCHARD)
        inter = CropField(rows=10, cols=10, landscape=LandscapeType.INTERCROP)

        for f, rng in [(mono, rng_m), (orch, rng_o), (inter, rng_i)]:
            f.stochastic_pest_introduction(rng, probability=1.0)
            for _ in range(50):
                f.step(w, rng)

        # Pest dynamics should differ across landscapes
        pest_densities = [
            mono.total_pest_density(),
            orch.total_pest_density(),
            inter.total_pest_density(),
        ]
        # Not all identical
        assert len(set(round(d, 2) for d in pest_densities)) > 1

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


class TestCoupledEcology:
    def test_beneficial_spray_mortality_is_graded_and_exceeds_pest_kill(self) -> None:
        remaining: list[float] = []
        for mortality in (0.2, 0.6, 0.95):
            field = CropField(
                rows=1,
                cols=1,
                ecology=EcologyConfig(beneficial_spray_mortality=mortality),
            )
            field.pests[0][0].density = 100.0
            field.pests[0][0].resistance_freq = 0.0
            field.biological_control[0] = 10.0
            field.apply_pesticide(0, 0, 0.8, np.random.default_rng(4))
            remaining.append(float(field.biological_control[0]))
        assert remaining[0] > remaining[1] > remaining[2]
        assert remaining[-1] < 10.0 * (1.0 - 0.8)

    def test_predation_operates_in_monoculture_with_graded_strength(self) -> None:
        densities: list[float] = []
        for rate in (0.0, 0.1, 0.2):
            field = CropField(
                rows=1,
                cols=1,
                landscape=LandscapeType.MONOCULTURE,
                ecology=EcologyConfig(primary_predation_rate=rate),
            )
            field.pests[0][0].density = 40.0
            field.biological_control[0] = 20.0
            field._advance_pests(np.random.default_rng(8))
            densities.append(field.pests[0][0].density)
        assert densities[0] > densities[1] > densities[2]
        assert densities[0] - densities[2] > 3.0

    def test_neighbor_recolonization_is_slow_and_graded(self) -> None:
        center_after_one_step: list[float] = []
        for rate in (0.02, 0.08, 0.2):
            field = CropField(
                rows=3,
                cols=3,
                ecology=EcologyConfig(
                    beneficial_response_rate=0.0,
                    beneficial_recolonization_rate=rate,
                    beneficial_noise=0.0,
                ),
            )
            field.biological_control[:] = 10.0
            field.biological_control[4] = 0.0
            field._update_biological_control(np.random.default_rng(3))
            center_after_one_step.append(float(field.biological_control[4]))
        assert center_after_one_step[0] < center_after_one_step[1] < center_after_one_step[2]
        assert center_after_one_step[1] < 2.0

    def test_spraying_releases_untreated_secondary_pest(self) -> None:
        ecology = EcologyConfig(beneficial_noise=0.0)
        sprayed = CropField(rows=3, cols=3, ecology=ecology)
        unsprayed = CropField(rows=3, cols=3, ecology=ecology)
        for field in (sprayed, unsprayed):
            field.secondary_pests[1][1].density = 20.0
            field.biological_control[:] = 10.0
        sprayed.apply_pesticide(1, 1, 0.8, np.random.default_rng(2))
        weather = AgWeather(temperature=25.0, wind_speed=0.0, precipitation=0.0)
        for _ in range(5):
            sprayed.step(weather, np.random.default_rng(17))
            unsprayed.step(weather, np.random.default_rng(17))
        assert sprayed.total_secondary_pest_density() > unsprayed.total_secondary_pest_density()
        assert (
            sprayed.total_secondary_pest_density() - unsprayed.total_secondary_pest_density() > 1.0
        )

    def test_abiotic_stress_is_bounded_and_increases_as_soil_dries(self) -> None:
        field = CropField(rows=1, cols=1)
        stresses = [field._abiotic_stress(0, 0, moisture) for moisture in (0.5, 0.2, 0.0)]
        assert 0.0 <= stresses[0] < stresses[1] < stresses[2] <= 1.0

    def test_introductions_are_patches_not_field_wide(self) -> None:
        field = CropField(rows=10, cols=10)
        field.stochastic_pest_introduction(np.random.default_rng(42), probability=1.0)
        occupied = {
            (row, col)
            for row in range(field.rows)
            for col in range(field.cols)
            if field.cell_pest_density(row, col) > 0.0
        }
        interior = [(row, col) for row, col in occupied if 0 < row < 9]
        assert [cell for cell in interior if 0 < cell[1] < 9]
        assert len(occupied) < field.rows * field.cols
        assert field.total_secondary_pest_density() > 0.0

    def test_population_and_stress_invariants_hold_over_steps(self) -> None:
        field = CropField(rows=5, cols=5)
        rng = np.random.default_rng(19)
        field.stochastic_pest_introduction(rng, probability=1.0)
        for _ in range(40):
            field.step(AgWeather(), rng)
        densities = [
            field.cell_pest_density(row, col)
            for row in range(field.rows)
            for col in range(field.cols)
        ]
        stress = [cell.abiotic_stress for row in field.crops for cell in row]
        assert all(np.isfinite(value) for value in densities)
        assert all(value >= 0.0 for value in densities)
        assert all(np.isfinite(value) for value in stress)
        assert all(0.0 <= value <= 1.0 for value in stress)
        assert np.all(np.isfinite(field.biological_control))
        assert np.all(field.biological_control >= 0.0)


class TestRecoverableAbioticStress:
    """Drought suppresses the standing crop reversibly instead of ratcheting it down."""

    def test_vigor_weight_grades_observable_suppression(self) -> None:
        weights = (0.0, 0.3, 0.6, 0.9)
        observed = [
            CropCell(
                health=1.0,
                abiotic_stress=0.8,
                abiotic_vigor_weight=weight,
                growth_stage=GrowthStage.FLOWERING,
            )
            for weight in weights
        ]
        health = [cell.effective_health for cell in observed]
        ndvi = [cell.ndvi_proxy for cell in observed]
        assert health == sorted(health, reverse=True)
        assert ndvi == sorted(ndvi, reverse=True)
        assert health[0] - health[-1] > 0.2
        assert all(0.0 <= value <= 1.0 for value in health)

    def test_drought_suppression_reverses_when_the_soil_rewets(self) -> None:
        """The point of the fix: the same cell recovers once moisture returns.

        A one-way damage ratchet would leave both the underlying health and the
        observable vigor permanently lower after the dry spell.
        """
        dry = AgWeather(temperature=30.0, solar_radiation=25.0, precipitation=0.0)
        wet = AgWeather(temperature=30.0, solar_radiation=25.0, precipitation=50.0)
        field = CropField(rows=4, cols=4)
        rng = np.random.default_rng(11)
        for _ in range(30):
            field.step(dry, rng)
        drought_vigor = field.mean_crop_health()
        for _ in range(30):
            field.step(wet, rng)
        recovered_vigor = field.mean_crop_health()
        underlying = [cell.health for row in field.crops for cell in row]
        assert drought_vigor < 0.7
        assert recovered_vigor > 0.95
        assert min(underlying) > 0.99

    def test_pest_free_field_keeps_its_health_over_a_long_dry_run(self) -> None:
        dry = AgWeather(temperature=30.0, solar_radiation=25.0, precipitation=0.0)
        field = CropField(rows=4, cols=4)
        rng = np.random.default_rng(5)
        for _ in range(200):
            field.step(dry, rng)
        underlying = [cell.health for row in field.crops for cell in row]
        yields = [cell.yield_potential for row in field.crops for cell in row]
        assert min(underlying) > 0.99
        assert min(yields) > 0.99

    def test_secondary_damage_multiplier_grades_crop_survival(self) -> None:
        health: list[float] = []
        for multiplier in (0.0, 0.2, 1.0):
            field = CropField(
                rows=1,
                cols=1,
                ecology=EcologyConfig(secondary_crop_damage_multiplier=multiplier),
            )
            field.secondary_pests[0][0].density = 100.0
            field._advance_crops(AgWeather())
            health.append(field.crops[0][0].health)
        assert health[0] > health[1] > health[2]
        assert health[0] - health[2] > 0.05

    def test_drought_lowers_pest_carrying_capacity_without_damaging_the_crop(self) -> None:
        densities: list[float] = []
        for stress in (0.0, 0.5, 1.0):
            field = CropField(rows=1, cols=1, ecology=EcologyConfig(primary_predation_rate=0.0))
            field.crops[0][0].abiotic_stress = stress
            field.pests[0][0].density = 20.0
            field.biological_control[0] = 0.0
            field._advance_pests(np.random.default_rng(6))
            densities.append(field.pests[0][0].density)
        assert densities[0] > densities[1] > densities[2]
        assert densities[0] - densities[2] > 0.5

    def test_effective_state_stays_bounded_and_finite(self) -> None:
        field = CropField(rows=5, cols=5)
        rng = np.random.default_rng(23)
        field.stochastic_pest_introduction(rng, probability=1.0)
        for _ in range(40):
            field.step(AgWeather(temperature=28.0, precipitation=0.0), rng)
        cells = [cell for row in field.crops for cell in row]
        vigor = [cell.effective_health for cell in cells]
        realized = [cell.effective_yield_potential for cell in cells]
        assert all(np.isfinite(value) for value in vigor)
        assert all(0.0 <= value <= 1.0 for value in vigor)
        assert all(np.isfinite(value) for value in realized)
        assert all(0.0 <= value <= 1.0 for value in realized)
        assert all(value <= cell.health for value, cell in zip(vigor, cells, strict=True))


class TestLegacyEcologyControl:
    """Negative controls: with the coupling off, none of the new costs apply."""

    def test_spray_leaves_beneficials_untouched(self) -> None:
        field = CropField(rows=1, cols=1, ecology=EcologyConfig(enabled=False))
        field.pests[0][0].density = 50.0
        field.biological_control[0] = 10.0
        field.apply_pesticide(0, 0, 0.8, np.random.default_rng(4))
        assert field.biological_control[0] == pytest.approx(10.0)

    def test_monoculture_predation_absent(self) -> None:
        field = CropField(rows=1, cols=1, ecology=EcologyConfig(enabled=False))
        field.pests[0][0].density = 20.0
        field.biological_control[0] = 5.0
        field._advance_pests(np.random.default_rng(8))
        assert field.pests[0][0].density > 20.0

    def test_no_secondary_pest_or_abiotic_stress(self) -> None:
        field = CropField(rows=5, cols=5, ecology=EcologyConfig(enabled=False))
        rng = np.random.default_rng(19)
        field.stochastic_pest_introduction(rng, probability=1.0)
        for _ in range(20):
            field.step(AgWeather(), rng)
        assert field.total_secondary_pest_density() == pytest.approx(0.0)
        assert field.total_pest_density() == pytest.approx(field.total_primary_pest_density())
        stress = [cell.abiotic_stress for row in field.crops for cell in row]
        assert stress == pytest.approx([0.0] * len(stress))

    def test_observable_vigor_equals_raw_health(self) -> None:
        field = CropField(rows=3, cols=3, ecology=EcologyConfig(enabled=False))
        rng = np.random.default_rng(31)
        field.stochastic_pest_introduction(rng, probability=1.0)
        for _ in range(20):
            field.step(AgWeather(temperature=30.0, precipitation=0.0), rng)
        cells = [cell for row in field.crops for cell in row]
        assert all(cell.abiotic_vigor_weight == pytest.approx(0.0) for cell in cells)
        assert field.mean_crop_health() == pytest.approx(
            sum(cell.health for cell in cells) / len(cells)
        )
