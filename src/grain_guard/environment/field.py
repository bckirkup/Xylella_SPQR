"""Grid-based crop field: the spatial substrate for the agricultural simulation."""

from __future__ import annotations

import enum

import numpy as np
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


class CropField(BaseModel):
    """Grid-based crop field simulation.

    Each cell holds crop state, pest populations, and weed populations.
    The field manages spatial dynamics (pest dispersal, edge effects)
    and supports three landscape variants.
    """

    model_config = {"arbitrary_types_allowed": True}

    rows: int = Field(default=20, ge=1)
    cols: int = Field(default=20, ge=1)
    landscape: LandscapeType = Field(default=LandscapeType.MONOCULTURE)

    crops: list[list[CropCell]] = Field(default_factory=list)
    pests: list[list[PestPopulation]] = Field(default_factory=list)
    weeds: list[list[WeedPopulation]] = Field(default_factory=list)

    biological_control: np.ndarray = Field(
        default_factory=lambda: np.array([], dtype=np.float64),
        description="Beneficial insect density per cell (flattened)",
    )

    def model_post_init(self, _context: object) -> None:
        """Initialize grids if empty."""
        if not self.crops:
            self._initialize_crops()
        if not self.pests:
            self._initialize_pests()
        if not self.weeds:
            self._initialize_weeds()
        if self.biological_control.size == 0:
            self.biological_control = np.full(self.rows * self.cols, 5.0)

    def _initialize_crops(self) -> None:
        """Create crop grid based on landscape type."""
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
                ct = default_type
                if self.landscape == LandscapeType.INTERCROP:
                    ct = [CropType.WHEAT, CropType.SOY, CropType.CORN][(r + c) % 3]
                row.append(CropCell(crop_type=ct, is_cover_crop=is_cover))
            self.crops.append(row)

    def _initialize_pests(self) -> None:
        """Initialize pests with landscape-appropriate species diversity."""
        self.pests = []
        for r in range(self.rows):
            row: list[PestPopulation] = []
            for c in range(self.cols):
                if self.landscape == LandscapeType.MONOCULTURE:
                    sp = PestSpecies.APHID
                elif self.landscape == LandscapeType.ORCHARD:
                    sp = [PestSpecies.APHID, PestSpecies.ARMYWORM][(r + c) % 2]
                else:
                    sp = [PestSpecies.APHID, PestSpecies.ROOTWORM, PestSpecies.ARMYWORM][
                        (r + c) % 3
                    ]
                row.append(PestPopulation(species=sp))
            self.pests.append(row)

    def _initialize_weeds(self) -> None:
        """Initialize weeds with landscape-appropriate species diversity."""
        self.weeds = []
        for r in range(self.rows):
            row: list[WeedPopulation] = []
            for c in range(self.cols):
                if self.landscape == LandscapeType.MONOCULTURE:
                    sp = WeedSpecies.PIGWEED
                elif self.landscape == LandscapeType.ORCHARD:
                    sp = [WeedSpecies.PIGWEED, WeedSpecies.FOXTAIL][(r + c) % 2]
                else:
                    sp = [WeedSpecies.PIGWEED, WeedSpecies.FOXTAIL, WeedSpecies.WATERHEMP][
                        (r + c) % 3
                    ]
                row.append(WeedPopulation(species=sp))
            self.weeds.append(row)

    @property
    def _landscape_pest_growth_modifier(self) -> float:
        """Pest growth multiplier: monoculture=1.0 (easy), orchard=1.3, intercrop=0.8.

        Orchards provide more microhabitat for pests (3D canopy).
        Intercropping disrupts pest host-finding (trap-crop effect).
        """
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 1.3,
            LandscapeType.INTERCROP: 0.8,
        }[self.landscape]

    @property
    def _landscape_weed_growth_modifier(self) -> float:
        """Weed growth multiplier: monoculture=1.0, orchard=0.7 (shade), intercrop=0.6.

        Orchards partially shade ground (moderate weed suppression).
        Intercrop living mulch strongly suppresses weeds.
        """
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 0.7,
            LandscapeType.INTERCROP: 0.6,
        }[self.landscape]

    @property
    def _landscape_dispersal_modifier(self) -> float:
        """Pest dispersal multiplier: open monoculture spreads easily, orchard/intercrop barriers slow it."""
        return {
            LandscapeType.MONOCULTURE: 1.0,
            LandscapeType.ORCHARD: 0.6,
            LandscapeType.INTERCROP: 0.5,
        }[self.landscape]

    @property
    def _landscape_detection_penalty(self) -> float:
        """Detection difficulty: monoculture=0 (easy), orchard=0.3 (3D canopy), intercrop=0.2 (mixed spectra)."""
        return {
            LandscapeType.MONOCULTURE: 0.0,
            LandscapeType.ORCHARD: 0.3,
            LandscapeType.INTERCROP: 0.2,
        }[self.landscape]

    @property
    def _landscape_biocontrol_boost(self) -> float:
        """Beneficial insect carrying capacity multiplier: polycultures support more."""
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
        self._pest_dispersal(weather, rng)
        self._update_biological_control(rng)

    def _advance_crops(self, weather: AgWeather) -> None:
        et = weather.evapotranspiration_rate()
        for r in range(self.rows):
            for c in range(self.cols):
                crop = self.crops[r][c]
                crop.advance_phenology(weather.growing_degree_days)
                crop.soil_moisture = float(
                    np.clip(
                        crop.soil_moisture + weather.precipitation * 0.01 - et * 0.005,
                        0.0,
                        1.0,
                    )
                )
                pest_damage = self.pests[r][c].damage_rate
                weed_damage = self.weeds[r][c].competition_factor * 0.01
                crop.apply_damage(pest_damage + weed_damage)

    def _advance_pests(self, rng: np.random.Generator) -> None:
        growth_mod = self._landscape_pest_growth_modifier
        detection_penalty = self._landscape_detection_penalty
        bio_boost = self._landscape_biocontrol_boost
        for r in range(self.rows):
            for c in range(self.cols):
                pest = self.pests[r][c]
                # Landscape modifies effective carrying capacity
                pest.grow(rng, self.crops[r][c].health * growth_mod)
                # Cover crops boost beneficial insects → suppress pests
                if self.crops[r][c].is_cover_crop:
                    bio_idx = r * self.cols + c
                    bio = self.biological_control[bio_idx] * bio_boost
                    pest.density = max(0.0, pest.density - bio * 0.01)
                # Detection pressure reduced in complex canopies
                detection_pressure = max(0.0, (1.0 - pest.night_feeding * 0.5) - detection_penalty)
                pest.evolve_behavior(rng, detection_pressure)

    def _advance_weeds(self, rng: np.random.Generator) -> None:
        weed_mod = self._landscape_weed_growth_modifier
        for r in range(self.rows):
            for c in range(self.cols):
                # Cover crop alleys suppress weeds
                moisture = self.crops[r][c].soil_moisture
                if self.crops[r][c].is_cover_crop:
                    moisture *= 0.5  # Cover crop competes for moisture
                self.weeds[r][c].grow(rng, moisture * weed_mod)

    def _pest_dispersal(self, weather: AgWeather, rng: np.random.Generator) -> None:
        """Diffuse pest populations to neighboring cells."""
        dispersal_mod = self._landscape_dispersal_modifier
        new_densities = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                dispersal_frac = self.pests[r][c].disperse(weather.wind_speed, rng) * dispersal_mod
                emigrants = self.pests[r][c].density * dispersal_frac
                self.pests[r][c].density -= emigrants
                neighbors = self._neighbors(r, c)
                if neighbors:
                    share = emigrants / len(neighbors)
                    for nr, nc in neighbors:
                        new_densities[nr, nc] += share
        for r in range(self.rows):
            for c in range(self.cols):
                self.pests[r][c].density += new_densities[r, c]

    def _update_biological_control(self, rng: np.random.Generator) -> None:
        """Beneficial insect populations track pest density with lag.

        Polyculture landscapes support higher beneficial insect populations
        (more habitat, prey diversity). Cover crop cells get an extra boost.
        """
        boost = self._landscape_biocontrol_boost
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                pest_density = self.pests[r][c].density
                target = pest_density * 0.3 * boost
                # Cover crops attract beneficials
                if self.crops[r][c].is_cover_crop:
                    target *= 1.5
                current = self.biological_control[idx]
                self.biological_control[idx] = float(
                    np.clip(
                        current + 0.1 * (target - current) + rng.normal(0, 0.5),
                        0.0,
                        50.0 * boost,
                    )
                )

    def _neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                result.append((nr, nc))
        return result

    def total_pest_density(self) -> float:
        return sum(self.pests[r][c].density for r in range(self.rows) for c in range(self.cols))

    def total_weed_density(self) -> float:
        return sum(self.weeds[r][c].density for r in range(self.rows) for c in range(self.cols))

    def mean_crop_health(self) -> float:
        total = sum(self.crops[r][c].health for r in range(self.rows) for c in range(self.cols))
        return total / (self.rows * self.cols)

    def mean_yield_potential(self) -> float:
        total = sum(
            self.crops[r][c].yield_potential for r in range(self.rows) for c in range(self.cols)
        )
        return total / (self.rows * self.cols)

    def cells_above_threshold(self, threshold: float) -> list[tuple[int, int]]:
        """Return cells where pest density exceeds the economic threshold."""
        result: list[tuple[int, int]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.pests[r][c].density > threshold:
                    result.append((r, c))
        return result

    def stochastic_pest_introduction(
        self, rng: np.random.Generator, probability: float = 0.02
    ) -> None:
        """Randomly introduce pests at field edges."""
        for r in range(self.rows):
            for c in range(self.cols):
                if (r == 0 or r == self.rows - 1 or c == 0 or c == self.cols - 1) and (
                    rng.random() < probability
                ):
                    self.pests[r][c].density += float(rng.uniform(1.0, 10.0))
