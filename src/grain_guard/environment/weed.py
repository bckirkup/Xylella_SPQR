"""Weed population dynamics with herbicide resistance evolution."""

from __future__ import annotations

import enum

import numpy as np
from pydantic import BaseModel, Field


class WeedSpecies(enum.StrEnum):
    """Weed species in the simulation."""

    PIGWEED = "pigweed"
    FOXTAIL = "foxtail"
    WATERHEMP = "waterhemp"


class WeedPopulation(BaseModel):
    """Per-cell weed population with herbicide resistance genetics.

    Weeds compete with crops for light and nutrients. Resistance evolves
    under herbicide selection pressure (1-locus model, spec §3.2).
    """

    species: WeedSpecies = Field(default=WeedSpecies.PIGWEED)
    density: float = Field(default=0.0, ge=0.0, description="Weed density (plants/m²)")
    resistance_freq: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Frequency of herbicide resistance allele",
    )
    canopy_height: float = Field(default=0.0, ge=0.0, description="Average weed canopy height (cm)")
    seed_bank: float = Field(default=50.0, ge=0.0, description="Soil seed bank density (seeds/m²)")

    @property
    def competition_factor(self) -> float:
        """Crop yield reduction from weed competition [0, 1]."""
        return float(np.clip(self.density * 0.001, 0.0, 0.3))

    @property
    def detectability(self) -> float:
        """How visible weeds are to aerial/tractor cameras [0, 1]."""
        if self.density <= 0:
            return 0.0
        height_signal = min(self.canopy_height / 30.0, 1.0)
        density_signal = min(self.density / 20.0, 1.0)
        return float(np.clip(0.5 * height_signal + 0.5 * density_signal, 0.0, 1.0))

    def grow(self, rng: np.random.Generator, soil_moisture: float) -> None:
        """Logistic growth modulated by soil moisture."""
        carrying_capacity = 50.0 * soil_moisture
        if self.density <= 0:
            self._germinate(rng, soil_moisture)
            return
        r = 0.1 + float(rng.normal(0, 0.02))
        growth = r * self.density * (1.0 - self.density / max(carrying_capacity, 1.0))
        self.density = max(0.0, self.density + growth)
        self.canopy_height = min(80.0, self.canopy_height + max(0.0, growth) * 2.0)

    def _germinate(self, rng: np.random.Generator, soil_moisture: float) -> None:
        """Recruit from seed bank."""
        if self.seed_bank <= 0:
            return
        germination_rate = 0.02 * soil_moisture
        recruits = self.seed_bank * germination_rate * float(rng.uniform(0.5, 1.5))
        self.density = max(0.0, recruits)
        self.seed_bank = max(0.0, self.seed_bank - recruits)

    def apply_herbicide(self, efficacy: float, rng: np.random.Generator) -> float:
        """Apply herbicide; resistant individuals survive. Returns kill count."""
        if self.density <= 0:
            return 0.0
        susceptible_frac = 1.0 - self.resistance_freq
        kill_frac = efficacy * susceptible_frac
        killed = self.density * kill_frac
        self.density = max(0.0, self.density - killed)
        self.canopy_height *= max(0.0, 1.0 - kill_frac)
        self._select_resistance(efficacy, rng)
        return killed

    def _select_resistance(self, selection_pressure: float, rng: np.random.Generator) -> None:
        """Shift resistance allele frequency under herbicide selection."""
        delta = selection_pressure * 0.03 * (1.0 - self.resistance_freq)
        self.resistance_freq = float(
            np.clip(self.resistance_freq + delta + rng.normal(0, 0.005), 0.0, 1.0)
        )

    def set_seed(self, rng: np.random.Generator) -> None:
        """Replenish seed bank from mature weeds (end of season)."""
        if self.density > 0 and self.canopy_height > 20.0:
            new_seeds = self.density * float(rng.uniform(5.0, 15.0))
            self.seed_bank += new_seeds
