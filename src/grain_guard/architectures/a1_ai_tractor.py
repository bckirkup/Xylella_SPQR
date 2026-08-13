"""A1: AI-enabled tractor / See & Spray class (spec §7, A1)."""

from __future__ import annotations

import numpy as np

from grain_guard.architectures.base import Architecture, SprayMetrics, apply_treatment
from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


class AITractor(Architecture):
    """Camera-on-boom, real-time weed/pest classification, spot-spray.

    Strong for weeds in row crops; limited for canopy pests or 3D orchards.
    Centralized model trained offline, deployed on-device.
    """

    def __init__(
        self,
        weed_threshold: float = 0.3,
        pest_threshold: float = 15.0,
        spray_efficacy: float = 0.85,
        pass_interval: int = 3,
        seed: int = 42,
    ) -> None:
        self.weed_threshold = weed_threshold
        self.pest_threshold = pest_threshold
        self.spray_efficacy = spray_efficacy
        self.pass_interval = pass_interval
        self.rng = np.random.default_rng(seed)

    def step(
        self,
        field: CropField,
        weather: AgWeather,
        time_step: int,
    ) -> dict[str, float]:
        if time_step % self.pass_interval != 0:
            return {
                "n_sprays": 0.0,
                "spray_volume_L": 0.0,
                "false_sprays": 0.0,
                "missed_cells": 0.0,
            }

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
        weed = field.weeds[row][col]
        pest = field.pests[row][col]

        weed_detected = weed.detectability > self.weed_threshold
        pest_detected = pest.density * pest.detectability > self.pest_threshold

        actual_weed = weed.density > 5.0
        actual_pest = pest.density > self.pest_threshold
        missed = 0.0

        weed_metrics = apply_treatment(
            should_treat=weed_detected and weather.is_spray_safe,
            volume=0.5,
            actual_problem=actual_weed,
            application=lambda: weed.apply_herbicide(self.spray_efficacy, self.rng),
        )
        pest_metrics = apply_treatment(
            should_treat=pest_detected and weather.is_spray_safe,
            volume=1.0,
            actual_problem=actual_pest,
            application=lambda: pest.apply_pesticide(self.spray_efficacy, self.rng),
        )

        if actual_pest and not pest_detected:
            missed += 1.0
        if actual_weed and not weed_detected:
            missed += 1.0
        return SprayMetrics(
            weed_metrics.sprays + pest_metrics.sprays,
            weed_metrics.volume + pest_metrics.volume,
            weed_metrics.false_sprays + pest_metrics.false_sprays,
            missed,
        )

    def reset(self) -> None:
        pass  # Stateless architecture; reset is required by the shared interface.
