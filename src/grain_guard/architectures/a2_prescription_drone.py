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
        self._baseline_ndvi: dict[tuple[int, int], float] = {}

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
                cell = self._process_cell(field, weather, r, c)
                n_sprays += cell[0]
                spray_volume += cell[1]
                false_sprays += cell[2]
                missed += cell[3]

        return {
            "n_sprays": n_sprays,
            "spray_volume_L": spray_volume,
            "false_sprays": false_sprays,
            "missed_cells": missed,
        }

    def _process_cell(
        self, field: CropField, weather: AgWeather, row: int, col: int
    ) -> tuple[float, float, float, float]:
        prescribed = self._prescription_map.get((row, col), False)
        actual_pest = field.pests[row][col].density > 10.0
        actual_weed = field.weeds[row][col].density > 5.0
        actual_problem = actual_pest or actual_weed
        n_sprays = 0.0
        spray_volume = 0.0
        false_sprays = 0.0
        missed = 0.0

        if prescribed and weather.is_spray_safe:
            n_sprays += 1.0
            spray_volume += 1.5
            if actual_pest:
                field.pests[row][col].apply_pesticide(self.spray_efficacy, self.rng)
            if actual_weed:
                field.weeds[row][col].apply_herbicide(self.spray_efficacy, self.rng)
            if not actual_problem:
                false_sprays += 1.0
        elif actual_problem:
            missed += 1.0
        return n_sprays, spray_volume, false_sprays, missed

    def _update_prescription(self, field: CropField) -> None:
        """Generate prescription map from NDVI anomaly detection.

        Instead of a raw NDVI threshold (which flags healthy seedlings),
        compare each cell's current NDVI to the field-wide median for its
        growth stage. Cells that are significantly below their peer median
        are flagged as stressed.
        """
        self._prescription_map.clear()
        # Group cells by growth stage to get stage-level NDVI medians
        stage_ndvi: dict[str, list[float]] = {}
        for r in range(field.rows):
            for c in range(field.cols):
                crop = field.crops[r][c]
                stage = crop.growth_stage.value
                stage_ndvi.setdefault(stage, []).append(crop.ndvi_proxy)
        stage_median: dict[str, float] = {}
        for stage, values in stage_ndvi.items():
            sorted_vals = sorted(values)
            mid = len(sorted_vals) // 2
            stage_median[stage] = sorted_vals[mid]

        for r in range(field.rows):
            for c in range(field.cols):
                crop = field.crops[r][c]
                stage = crop.growth_stage.value
                median = stage_median.get(stage, 0.5)
                # Flag cells whose NDVI is > 30% below their stage median
                if median > 0 and crop.ndvi_proxy < median * (1.0 - self.ndvi_stress_threshold):
                    self._prescription_map[(r, c)] = True

    def reset(self) -> None:
        self._prescription_map.clear()
        self._baseline_ndvi.clear()
