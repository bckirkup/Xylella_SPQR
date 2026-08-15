"""Pest population dynamics with co-evolutionary resistance and behavioral escape."""

from __future__ import annotations

import enum
from typing import Self

import numpy as np
from pydantic import BaseModel, Field


class PestSpecies(enum.StrEnum):
    """Pest species in the simulation."""

    APHID = "aphid"
    ROOTWORM = "rootworm"
    ARMYWORM = "armyworm"


_GENERATION_TIME: dict[PestSpecies, int] = {
    PestSpecies.APHID: 14,
    PestSpecies.ROOTWORM: 365,
    PestSpecies.ARMYWORM: 30,
}


class PestPopulation(BaseModel):
    """Per-cell pest population with resistance genetics and behavioral traits.

    Implements a simple 1-locus resistance allele model (spec §3.2).
    Behavioral escape evolves: night-feeding frequency, underside-leaf
    preference, and edge-refuge tendency.
    """

    species: PestSpecies = Field(default=PestSpecies.APHID)
    density: float = Field(default=0.0, ge=0.0, description="Pest density (individuals/m²)")
    resistance_freq: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Frequency of pesticide resistance allele",
    )
    night_feeding: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction feeding at night (harder to detect visually)",
    )
    underside_preference: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Fraction feeding on leaf undersides (hidden from aerial)",
    )
    edge_refuge: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Tendency to cluster in field margins/cover crops",
    )
    generation_counter: int = Field(default=0, ge=0)
    evolution_frozen: bool = Field(
        default=False,
        description=(
            "Freeze heritable pest traits. Random draws are still consumed so a "
            "frozen run stays aligned with an evolving run at the same seed."
        ),
    )

    @property
    def generation_time(self) -> int:
        return _GENERATION_TIME[self.species]

    @property
    def detectability(self) -> float:
        """How detectable the pest is by aerial/visual sensors [0, 1]."""
        return max(0.0, 1.0 - 0.4 * self.night_feeding - 0.4 * self.underside_preference)

    @property
    def damage_rate(self) -> float:
        """Crop damage per unit density per step."""
        base_rates: dict[PestSpecies, float] = {
            PestSpecies.APHID: 0.0003,
            PestSpecies.ROOTWORM: 0.0008,
            PestSpecies.ARMYWORM: 0.001,
        }
        return base_rates[self.species] * self.density

    def grow(self, rng: np.random.Generator, crop_health: float) -> None:
        """Logistic growth with carrying capacity proportional to crop health."""
        carrying_capacity = 100.0 * crop_health
        if self.density <= 0 or carrying_capacity <= 0:
            return
        r = 0.15 + float(rng.normal(0, 0.02))
        growth = r * self.density * (1.0 - self.density / carrying_capacity)
        self.density = max(0.0, self.density + growth)

    def apply_pesticide(self, efficacy: float, rng: np.random.Generator) -> float:
        """Apply pesticide; resistant individuals survive. Returns kill count."""
        if self.density <= 0:
            return 0.0
        susceptible_frac = 1.0 - self.resistance_freq
        kill_frac = efficacy * susceptible_frac
        killed = self.density * kill_frac
        self.density = max(0.0, self.density - killed)
        self._select_resistance(efficacy, rng)
        return killed

    def _select_resistance(self, selection_pressure: float, rng: np.random.Generator) -> None:
        """Shift resistance allele frequency under selection."""
        delta = selection_pressure * 0.02 * (1.0 - self.resistance_freq)
        noise = float(rng.normal(0, 0.005))
        if self.evolution_frozen:
            return
        self.resistance_freq = float(np.clip(self.resistance_freq + delta + noise, 0.0, 1.0))

    def evolve_behavior(self, rng: np.random.Generator, detection_pressure: float) -> None:
        """Evolve behavioral escape traits in response to detection pressure."""
        self.generation_counter += 1
        if self.generation_counter < self.generation_time:
            return
        self.generation_counter = 0
        drift = 0.01
        draws = [float(rng.normal(0, drift)) for _ in range(3)]
        if self.evolution_frozen:
            return
        self.night_feeding = float(
            np.clip(self.night_feeding + detection_pressure * 0.02 + draws[0], 0.0, 1.0)
        )
        self.underside_preference = float(
            np.clip(self.underside_preference + detection_pressure * 0.015 + draws[1], 0.0, 1.0)
        )
        self.edge_refuge = float(
            np.clip(self.edge_refuge + detection_pressure * 0.01 + draws[2], 0.0, 1.0)
        )

    def disperse(self, wind_speed: float, rng: np.random.Generator) -> float:
        """Return fraction of population that disperses to neighbors."""
        base_rate = 0.05
        wind_factor = wind_speed / 20.0
        return float(np.clip(base_rate + wind_factor + rng.normal(0, 0.01), 0.0, 0.3))

    def clone(self) -> Self:
        """Return a deep copy."""
        return type(self).model_validate(self.model_dump())
