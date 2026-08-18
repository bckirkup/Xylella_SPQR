"""Grid-based crop field: the spatial substrate for the agricultural simulation."""

from __future__ import annotations

import enum

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from grain_guard.environment.crop import CropCell, CropType
from grain_guard.environment.pest import PestPopulation, PestSpecies
from grain_guard.environment.weather import AgWeather
from grain_guard.environment.weed import WeedPopulation, WeedSpecies


class LandscapeType(enum.StrEnum):
    """Cropping system variant (spec §3.1)."""

    MONOCULTURE = "monoculture"
    ORCHARD = "orchard"
    INTERCROP = "intercrop"


class EcologyConfig(BaseModel):
    """Tunable ecological coupling that makes spray selectivity consequential."""

    enabled: bool = Field(default=True)
    beneficial_spray_mortality: float = Field(default=0.95, ge=0.0, le=1.0)
    primary_predation_rate: float = Field(default=0.12, ge=0.0)
    secondary_predation_rate: float = Field(default=0.24, ge=0.0)
    beneficial_response_rate: float = Field(default=0.025, ge=0.0, le=1.0)
    beneficial_recolonization_rate: float = Field(default=0.08, ge=0.0, le=1.0)
    beneficial_noise: float = Field(default=0.1, ge=0.0)
    drought_threshold: float = Field(default=0.42, gt=0.0, le=1.0)
    abiotic_vigor_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Reversible suppression of crop vigor at full drought stress. Drought "
            "never writes permanent damage, so a rewetted cell recovers."
        ),
    )
    secondary_intro_fraction: float = Field(default=0.2, ge=0.0)
    secondary_growth_multiplier: float = Field(default=2.0, ge=0.0)
    introduction_patch_radius: int = Field(default=1, ge=0, le=3)


class CropField(BaseModel):
    """Grid-based crop field simulation with coupled pests and natural enemies."""

    model_config = {"arbitrary_types_allowed": True}

    rows: int = Field(default=20, ge=1)
    cols: int = Field(default=20, ge=1)
    landscape: LandscapeType = Field(default=LandscapeType.MONOCULTURE)
    ecology: EcologyConfig = Field(default_factory=EcologyConfig)
    freeze_pest_evolution: bool = Field(
        default=False,
        description=(
            "Hold the pest adversary fixed: resistance and behavioral escape traits "
            "stop changing, while their random draws are still consumed so a frozen "
            "run stays seed-aligned with an evolving run."
        ),
    )

    crops: list[list[CropCell]] = Field(default_factory=list)
    pests: list[list[PestPopulation]] = Field(default_factory=list)
    secondary_pests: list[list[PestPopulation]] = Field(default_factory=list)
    weeds: list[list[WeedPopulation]] = Field(default_factory=list)
    biological_control: NDArray[np.float64] = Field(
        default_factory=lambda: np.array([], dtype=np.float64),
        description="Beneficial insect density per cell (flattened)",
    )
    abiotic_susceptibility: NDArray[np.float64] = Field(
        default_factory=lambda: np.array([], dtype=np.float64),
        description="Spatially smooth susceptibility to drought stress (flattened)",
    )

    def model_post_init(self, _context: object) -> None:
        """Initialize grids if empty."""
        if not self.crops:
            self._initialize_crops()
        if not self.pests:
            self._initialize_pests()
        if not self.secondary_pests:
            self._initialize_secondary_pests()
        if not self.weeds:
            self._initialize_weeds()
        if self.biological_control.size == 0:
            self.biological_control = np.full(self.rows * self.cols, 5.0)
        if self.abiotic_susceptibility.size == 0:
            self.abiotic_susceptibility = self._initial_abiotic_susceptibility()
        self._apply_abiotic_vigor_weight()
        self.apply_pest_evolution_freeze(self.freeze_pest_evolution)

    def _apply_abiotic_vigor_weight(self) -> None:
        weight = self.ecology.abiotic_vigor_weight if self.ecology.enabled else 0.0
        for row in self.crops:
            for crop in row:
                crop.abiotic_vigor_weight = weight

    def apply_pest_evolution_freeze(self, frozen: bool) -> None:
        """Freeze or unfreeze heritable pest traits across every cell."""
        self.freeze_pest_evolution = frozen
        for grid in (self.pests, self.secondary_pests):
            for row in grid:
                for pest in row:
                    pest.evolution_frozen = frozen

    def _initialize_crops(self) -> None:
        crop_map: dict[LandscapeType, CropType] = {
            LandscapeType.MONOCULTURE: CropType.WHEAT,
            LandscapeType.ORCHARD: CropType.APPLE,
            LandscapeType.INTERCROP: CropType.MIXED,
        }
        default_type = crop_map[self.landscape]
        self.crops = []
        for r in range(self.rows):
            row: list[CropCell] = []
            for c in range(self.cols):
                is_cover = self.landscape == LandscapeType.ORCHARD and c % 3 == 0
                crop_type = default_type
                if self.landscape == LandscapeType.INTERCROP:
                    crop_type = [CropType.WHEAT, CropType.SOY, CropType.CORN][(r + c) % 3]
                row.append(CropCell(crop_type=crop_type, is_cover_crop=is_cover))
            self.crops.append(row)

    def _initialize_pests(self) -> None:
        self.pests = []
        for r in range(self.rows):
            row: list[PestPopulation] = []
            for c in range(self.cols):
                if self.landscape == LandscapeType.MONOCULTURE:
                    species = PestSpecies.APHID
                elif self.landscape == LandscapeType.ORCHARD:
                    species = [PestSpecies.APHID, PestSpecies.ARMYWORM][(r + c) % 2]
                else:
                    species = [PestSpecies.APHID, PestSpecies.ROOTWORM, PestSpecies.ARMYWORM][
                        (r + c) % 3
                    ]
                row.append(PestPopulation(species=species))
            self.pests.append(row)

    def _initialize_secondary_pests(self) -> None:
        self.secondary_pests = [
            [PestPopulation(species=PestSpecies.ARMYWORM) for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

    def _initialize_weeds(self) -> None:
        self.weeds = []
        for r in range(self.rows):
            row: list[WeedPopulation] = []
            for c in range(self.cols):
                if self.landscape == LandscapeType.MONOCULTURE:
                    species = WeedSpecies.PIGWEED
                elif self.landscape == LandscapeType.ORCHARD:
                    species = [WeedSpecies.PIGWEED, WeedSpecies.FOXTAIL][(r + c) % 2]
                else:
                    species = [WeedSpecies.PIGWEED, WeedSpecies.FOXTAIL, WeedSpecies.WATERHEMP][
                        (r + c) % 3
                    ]
                row.append(WeedPopulation(species=species))
            self.weeds.append(row)

    def _initial_abiotic_susceptibility(self) -> NDArray[np.float64]:
        values = np.empty((self.rows, self.cols), dtype=np.float64)
        row_scale = max(self.rows - 1, 1)
        col_scale = max(self.cols - 1, 1)
        for r in range(self.rows):
            for c in range(self.cols):
                wave = np.sin(np.pi * r / row_scale) * np.cos(np.pi * c / col_scale)
                values[r, c] = 0.75 + 0.25 * wave
        return values.ravel()

    @property
    def _landscape_pest_growth_modifier(self) -> float:
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 1.3,
            LandscapeType.INTERCROP: 0.8,
        }[self.landscape]

    @property
    def _landscape_weed_growth_modifier(self) -> float:
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 0.7,
            LandscapeType.INTERCROP: 0.6,
        }[self.landscape]

    @property
    def _landscape_dispersal_modifier(self) -> float:
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 0.6,
            LandscapeType.INTERCROP: 0.5,
        }[self.landscape]

    @property
    def _landscape_detection_penalty(self) -> float:
        return {
            LandscapeType.MONOCULTURE: 0.0,
            LandscapeType.ORCHARD: 0.3,
            LandscapeType.INTERCROP: 0.2,
        }[self.landscape]

    @property
    def _landscape_biocontrol_boost(self) -> float:
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 1.8,
            LandscapeType.INTERCROP: 2.0,
        }[self.landscape]

    def step(self, weather: AgWeather, rng: np.random.Generator) -> None:
        """Advance the field one time step."""
        self._advance_crops(weather)
        self._advance_pests(rng)
        self._advance_weeds(rng)
        self._pest_dispersal(weather, rng, self.pests)
        if self.ecology.enabled:
            self._pest_dispersal(weather, rng, self.secondary_pests)
        self._update_biological_control(rng)

    def _advance_crops(self, weather: AgWeather) -> None:
        evapotranspiration = weather.evapotranspiration_rate()
        for r in range(self.rows):
            for c in range(self.cols):
                crop = self.crops[r][c]
                crop.advance_phenology(weather.growing_degree_days)
                crop.soil_moisture = float(
                    np.clip(
                        crop.soil_moisture
                        + weather.precipitation * 0.01
                        - evapotranspiration * 0.005,
                        0.0,
                        1.0,
                    )
                )
                crop.abiotic_stress = self._abiotic_stress(r, c, crop.soil_moisture)
                pest_damage = self.pests[r][c].damage_rate
                if self.ecology.enabled:
                    pest_damage += self.secondary_pests[r][c].damage_rate
                weed_damage = self.weeds[r][c].competition_factor * 0.01
                crop.apply_damage(pest_damage + weed_damage)

    def _abiotic_stress(self, r: int, c: int, moisture: float) -> float:
        if not self.ecology.enabled:
            return 0.0
        shortage = max(0.0, self.ecology.drought_threshold - moisture)
        normalized = shortage / self.ecology.drought_threshold
        susceptibility = self.abiotic_susceptibility[r * self.cols + c]
        return float(np.clip(normalized * susceptibility, 0.0, 1.0))

    def _advance_pests(self, rng: np.random.Generator) -> None:
        growth_modifier = self._landscape_pest_growth_modifier
        detection_penalty = self._landscape_detection_penalty
        for r in range(self.rows):
            for c in range(self.cols):
                primary = self.pests[r][c]
                crop_health = self.crops[r][c].effective_health
                primary.grow(rng, crop_health * growth_modifier)
                if self.ecology.enabled:
                    secondary = self.secondary_pests[r][c]
                    secondary.grow(
                        rng,
                        crop_health * growth_modifier * self.ecology.secondary_growth_multiplier,
                    )
                    beneficials = self.biological_control[r * self.cols + c]
                    self._apply_predation(primary, beneficials, self.ecology.primary_predation_rate)
                    self._apply_predation(
                        secondary, beneficials, self.ecology.secondary_predation_rate
                    )
                elif self.crops[r][c].is_cover_crop:
                    beneficials = self.biological_control[r * self.cols + c]
                    primary.density = max(
                        0.0,
                        primary.density - beneficials * self._landscape_biocontrol_boost * 0.01,
                    )
                detection_pressure = max(
                    0.0,
                    (1.0 - primary.night_feeding * 0.5) - detection_penalty,
                )
                primary.evolve_behavior(rng, detection_pressure)
                if self.ecology.enabled:
                    self.secondary_pests[r][c].evolve_behavior(rng, detection_pressure)

    @staticmethod
    def _apply_predation(pest: PestPopulation, beneficials: float, rate: float) -> None:
        pest.density = max(0.0, pest.density - beneficials * rate)

    def _advance_weeds(self, rng: np.random.Generator) -> None:
        weed_modifier = self._landscape_weed_growth_modifier
        for r in range(self.rows):
            for c in range(self.cols):
                moisture = self.crops[r][c].soil_moisture
                if self.crops[r][c].is_cover_crop:
                    moisture *= 0.5
                self.weeds[r][c].grow(rng, moisture * weed_modifier)

    def _pest_dispersal(
        self,
        weather: AgWeather,
        rng: np.random.Generator,
        populations: list[list[PestPopulation]],
    ) -> None:
        dispersal_modifier = self._landscape_dispersal_modifier
        additions = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                pest = populations[r][c]
                dispersal_fraction = pest.disperse(weather.wind_speed, rng) * dispersal_modifier
                emigrants = pest.density * dispersal_fraction
                pest.density -= emigrants
                neighbors = self._neighbors(r, c)
                if neighbors:
                    share = emigrants / len(neighbors)
                    for neighbor_r, neighbor_c in neighbors:
                        additions[neighbor_r, neighbor_c] += share
        for r in range(self.rows):
            for c in range(self.cols):
                populations[r][c].density += additions[r, c]

    def _update_biological_control(self, rng: np.random.Generator) -> None:
        if not self.ecology.enabled:
            self._update_legacy_biological_control(rng)
            return
        boost = self._landscape_biocontrol_boost
        previous = self.biological_control.reshape(self.rows, self.cols).copy()
        updated = previous.copy()
        for r in range(self.rows):
            for c in range(self.cols):
                prey = self.pests[r][c].density + self.secondary_pests[r][c].density
                target = prey * 0.3 * boost
                if self.crops[r][c].is_cover_crop:
                    target *= 1.5
                neighbors = self._neighbors(r, c)
                neighbor_mean = (
                    float(np.mean([previous[nr, nc] for nr, nc in neighbors]))
                    if neighbors
                    else previous[r, c]
                )
                response = self.ecology.beneficial_response_rate * (target - previous[r, c])
                recolonization = self.ecology.beneficial_recolonization_rate * (
                    neighbor_mean - previous[r, c]
                )
                updated[r, c] = np.clip(
                    previous[r, c]
                    + response
                    + recolonization
                    + rng.normal(0, self.ecology.beneficial_noise),
                    0.0,
                    50.0 * boost,
                )
        self.biological_control = updated.ravel()

    def _update_legacy_biological_control(self, rng: np.random.Generator) -> None:
        boost = self._landscape_biocontrol_boost
        for r in range(self.rows):
            for c in range(self.cols):
                index = r * self.cols + c
                target = self.pests[r][c].density * 0.3 * boost
                if self.crops[r][c].is_cover_crop:
                    target *= 1.5
                current = self.biological_control[index]
                self.biological_control[index] = float(
                    np.clip(
                        current + 0.1 * (target - current) + rng.normal(0, 0.5),
                        0.0,
                        50.0 * boost,
                    )
                )

    def apply_pesticide(
        self,
        row: int,
        col: int,
        efficacy: float,
        rng: np.random.Generator,
    ) -> float:
        """Treat the primary pest and, under coupled ecology, kill natural enemies."""
        killed = self.pests[row][col].apply_pesticide(efficacy, rng)
        if self.ecology.enabled:
            index = row * self.cols + col
            survival = 1.0 - self.ecology.beneficial_spray_mortality
            self.biological_control[index] *= survival
        return killed

    def _neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for row_offset, col_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_r, neighbor_c = r + row_offset, c + col_offset
            if 0 <= neighbor_r < self.rows and 0 <= neighbor_c < self.cols:
                result.append((neighbor_r, neighbor_c))
        return result

    def total_pest_density(self) -> float:
        primary = sum(self.pests[r][c].density for r in range(self.rows) for c in range(self.cols))
        if not self.ecology.enabled:
            return primary
        secondary = sum(
            self.secondary_pests[r][c].density for r in range(self.rows) for c in range(self.cols)
        )
        return primary + secondary

    def total_primary_pest_density(self) -> float:
        return sum(self.pests[r][c].density for r in range(self.rows) for c in range(self.cols))

    def total_secondary_pest_density(self) -> float:
        return sum(
            self.secondary_pests[r][c].density for r in range(self.rows) for c in range(self.cols)
        )

    def total_weed_density(self) -> float:
        return sum(self.weeds[r][c].density for r in range(self.rows) for c in range(self.cols))

    def mean_crop_health(self) -> float:
        total = sum(
            self.crops[r][c].effective_health for r in range(self.rows) for c in range(self.cols)
        )
        return total / (self.rows * self.cols)

    def mean_yield_potential(self) -> float:
        total = sum(
            self.crops[r][c].effective_yield_potential
            for r in range(self.rows)
            for c in range(self.cols)
        )
        return total / (self.rows * self.cols)

    def cell_pest_density(self, row: int, col: int) -> float:
        density = self.pests[row][col].density
        if self.ecology.enabled:
            density += self.secondary_pests[row][col].density
        return density

    def cells_above_threshold(self, threshold: float) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.cell_pest_density(r, c) > threshold
        ]

    def stochastic_pest_introduction(
        self,
        rng: np.random.Generator,
        probability: float = 0.02,
    ) -> None:
        """Introduce edge pests, spatially clumped when coupled ecology is enabled."""
        if not self.ecology.enabled:
            self._legacy_pest_introduction(rng, probability)
            return
        edges = self._edge_cells()
        introductions = sum(1 for _ in edges if rng.random() < probability)
        for _ in range(introductions):
            row, col = edges[int(rng.integers(0, len(edges)))]
            dose = float(rng.uniform(1.0, 10.0))
            patch = self._patch_cells(row, col, self.ecology.introduction_patch_radius)
            for patch_r, patch_c, distance in patch:
                local_dose = dose / (1.0 + distance)
                self.pests[patch_r][patch_c].density += local_dose
                self.secondary_pests[patch_r][patch_c].density += (
                    local_dose * self.ecology.secondary_intro_fraction
                )

    def _legacy_pest_introduction(self, rng: np.random.Generator, probability: float) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if (r == 0 or r == self.rows - 1 or c == 0 or c == self.cols - 1) and (
                    rng.random() < probability
                ):
                    self.pests[r][c].density += float(rng.uniform(1.0, 10.0))

    def _edge_cells(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if r in (0, self.rows - 1) or c in (0, self.cols - 1)
        ]

    def _patch_cells(self, row: int, col: int, radius: int) -> list[tuple[int, int, int]]:
        return [
            (r, c, abs(r - row) + abs(c - col))
            for r in range(max(0, row - radius), min(self.rows, row + radius + 1))
            for c in range(max(0, col - radius), min(self.cols, col + radius + 1))
            if abs(r - row) + abs(c - col) <= radius
        ]
