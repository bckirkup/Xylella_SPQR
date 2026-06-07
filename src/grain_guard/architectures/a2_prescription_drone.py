"""A2: Prescription drone service with centralized map generation (spec §7, A2)."""

from __future__ import annotations

import numpy as np

from grain_guard.architectures.base import Architecture
from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


class PrescriptionDrone(Architecture):
    """Autonomous spray drones with pre-planned flight paths.

    Prescription maps from satellite imagery + agronomist interpretation.
    Centralized planning, distributed execution. No real-time
    within-flight adaptation.
    """

    def __init__(
        self,
        ndvi_stress_threshold: float = 0.5,
        spray_efficacy: float = 0.8,
        map_update_interval: int = 5,
        seed: int = 42,
    ) -> None:
        self.ndvi_stress_threshold = ndvi_stress_threshold
        self.spray_efficacy = spray_efficacy
        self.map_update_interval = map_update_interval
        self.rng = np.random.default_rng(seed)
        self._prescription_map: dict[tuple[int, int], bool] = {}

    def step(
        self,
        field: CropField,
        weather: AgWeather,
        time_step: int,
    ) -> dict[str, float]:
        if time_step % self.map_update_interval == 0:
            self._update_prescription(field)

        n_sprays = 0.0
        spray_volume = 0.0
        false_sprays = 0.0
        missed = 0.0

        for r in range(field.rows):
            for c in range(field.cols):
                prescribed = self._prescription_map.get((r, c), False)
                actual_pest = field.pests[r][c].density > 10.0
                actual_weed = field.weeds[r][c].density > 5.0
                actual_problem = actual_pest or actual_weed

                if prescribed and weather.is_spray_safe:
                    n_sprays += 1.0
                    spray_volume += 1.5
                    if actual_pest:
                        field.pests[r][c].apply_pesticide(self.spray_efficacy, self.rng)
                    if actual_weed:
                        field.weeds[r][c].apply_herbicide(self.spray_efficacy, self.rng)
                    if not actual_problem:
                        false_sprays += 1.0
                elif actual_problem:
                    missed += 1.0

        return {
            "n_sprays": n_sprays,
            "spray_volume_L": spray_volume,
            "false_sprays": false_sprays,
            "missed_cells": missed,
        }

    def _update_prescription(self, field: CropField) -> None:
        """Generate prescription map from NDVI stress signals."""
        self._prescription_map.clear()
        for r in range(field.rows):
            for c in range(field.cols):
                ndvi = field.crops[r][c].ndvi_proxy
                if ndvi < self.ndvi_stress_threshold:
                    self._prescription_map[(r, c)] = True

    def reset(self) -> None:
        self._prescription_map.clear()
