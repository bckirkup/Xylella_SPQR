"""A3: Centralized precision ag platform — strongest conventional competitor (spec §7, A3)."""

from __future__ import annotations

import numpy as np

from grain_guard.architectures.base import Architecture, SprayMetrics, apply_treatment
from grain_guard.environment.crop import CropCell
from grain_guard.environment.field import CropField
from grain_guard.environment.pest import PestPopulation
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
                cell = self._process_cell(field, weather, r, c)
                n_sprays += cell.sprays
                spray_volume += cell.volume
                false_sprays += cell.false_sprays
                missed += cell.missed

        return {
            "n_sprays": n_sprays,
            "spray_volume_L": spray_volume,
            "false_sprays": false_sprays,
            "missed_cells": missed,
        }

    def _process_cell(
        self, field: CropField, weather: AgWeather, row: int, col: int
    ) -> SprayMetrics:
        pest = field.pests[row][col]
        weed = field.weeds[row][col]
        crop = field.crops[row][col]
        bio_density = field.biological_control[row * field.cols + col]

        eil = self._compute_eil(crop, pest, bio_density)
        economic_threshold = 0.75 * eil
        treat_pest = pest.density > economic_threshold
        treat_weed = weed.density > self.weed_threshold
        actual_pest_problem = pest.density > economic_threshold
        actual_weed_problem = weed.density > self.weed_threshold
        missed = 0.0

        pest_metrics = apply_treatment(
            should_treat=treat_pest and weather.is_spray_safe,
            volume=1.0,
            actual_problem=actual_pest_problem,
            application=lambda: field.apply_pesticide(
                row,
                col,
                max(
                    0.1,
                    self.spray_efficacy
                    * (1.0 - self.biocontrol_weight * min(bio_density / 20.0, 1.0)),
                ),
                self.rng,
            ),
        )
        weed_metrics = apply_treatment(
            should_treat=treat_weed and weather.is_spray_safe,
            volume=0.5,
            actual_problem=actual_weed_problem,
            application=lambda: weed.apply_herbicide(self.spray_efficacy, self.rng),
        )

        if actual_pest_problem and not treat_pest:
            missed += 1.0
        if actual_weed_problem and not treat_weed:
            missed += 1.0
        return SprayMetrics(
            pest_metrics.sprays + weed_metrics.sprays,
            pest_metrics.volume + weed_metrics.volume,
            pest_metrics.false_sprays + weed_metrics.false_sprays,
            missed,
        )

    def _compute_eil(self, crop: CropCell, _pest: PestPopulation, bio_density: float) -> float:
        """Compute Economic Injury Level (spec §3.3).

        Uses a practical formulation: base threshold scaled by crop value
        at risk and biological control suppression. Higher biocontrol density
        → higher threshold (let beneficials work before spraying).

        EIL = base_threshold * (1 + biocontrol_suppression) / vulnerability
        """
        vulnerability = max(0.2, crop.health)  # healthier crops = more at stake
        bio_suppression = self.biocontrol_weight * min(bio_density / 10.0, 2.0)
        return self.pest_threshold * (1.0 + bio_suppression) / vulnerability

    def reset(self) -> None:
        pass  # Stateless architecture; reset is required by the shared interface.
