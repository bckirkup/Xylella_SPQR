"""A3: Centralized precision ag platform — strongest conventional competitor (spec §7, A3)."""

from __future__ import annotations

import numpy as np

from grain_guard.architectures.base import Architecture
from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


class CentralizedPlatform(Architecture):
    """Climate Corp / Farmers Edge / Taranis class.

    Satellite + drone + IoT + weather fusion into a single decision engine.
    Global optimization of spray timing, rate, location. Full strength
    conventional competitor — receives ALL sensor data.
    """

    def __init__(
        self,
        pest_threshold: float = 8.0,
        weed_threshold: float = 3.0,
        spray_efficacy: float = 0.9,
        biocontrol_weight: float = 0.3,
        seed: int = 42,
    ) -> None:
        self.pest_threshold = pest_threshold
        self.weed_threshold = weed_threshold
        self.spray_efficacy = spray_efficacy
        self.biocontrol_weight = biocontrol_weight
        self.rng = np.random.default_rng(seed)

    def step(
        self,
        field: CropField,
        weather: AgWeather,
        time_step: int,
    ) -> dict[str, float]:
        n_sprays = 0.0
        spray_volume = 0.0
        false_sprays = 0.0
        missed = 0.0

        for r in range(field.rows):
            for c in range(field.cols):
                pest = field.pests[r][c]
                weed = field.weeds[r][c]
                crop = field.crops[r][c]
                bio_density = field.biological_control[r * field.cols + c]

                eil = self._compute_eil(crop, pest, bio_density)
                economic_threshold = 0.75 * eil

                treat_pest = pest.density > economic_threshold
                treat_weed = weed.density > self.weed_threshold

                actual_pest_problem = pest.density > economic_threshold
                actual_weed_problem = weed.density > self.weed_threshold

                if treat_pest and weather.is_spray_safe:
                    reduced_efficacy = self.spray_efficacy * (
                        1.0 - self.biocontrol_weight * min(bio_density / 20.0, 1.0)
                    )
                    n_sprays += 1.0
                    spray_volume += 1.0
                    pest.apply_pesticide(max(0.1, reduced_efficacy), self.rng)
                    if not actual_pest_problem:
                        false_sprays += 1.0

                if treat_weed and weather.is_spray_safe:
                    n_sprays += 1.0
                    spray_volume += 0.5
                    weed.apply_herbicide(self.spray_efficacy, self.rng)
                    if not actual_weed_problem:
                        false_sprays += 1.0

                if actual_pest_problem and not treat_pest:
                    missed += 1.0
                if actual_weed_problem and not treat_weed:
                    missed += 1.0

        return {
            "n_sprays": n_sprays,
            "spray_volume_L": spray_volume,
            "false_sprays": false_sprays,
            "missed_cells": missed,
        }

    def _compute_eil(self, crop: object, pest: object, bio_density: float) -> float:
        """Compute EIL = C / (V * D * I * K) (spec §3.3)."""
        c = 2.0
        v = 5.0
        d = 0.1
        i = 0.05
        k = max(0.1, 1.0 - bio_density * 0.02)
        denominator = v * d * i * k
        if denominator <= 0:
            return float("inf")
        return c / denominator

    def reset(self) -> None:
        pass
