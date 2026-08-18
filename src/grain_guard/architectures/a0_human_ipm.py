"""A0: Human scouting + calendar/threshold IPM (spec §7, A0)."""

from __future__ import annotations

import numpy as np

from grain_guard.architectures.base import Architecture
from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


class HumanIPM(Architecture):
    """Walk-the-field, count pests, spray on calendar or when count exceeds ET.

    Lowest technology. Still dominant globally. Uses fixed economic
    threshold and periodic scouting.
    """

    def __init__(
        self,
        economic_threshold: float = 10.0,
        scout_interval: int = 7,
        spray_efficacy: float = 0.8,
        seed: int = 42,
    ) -> None:
        self.economic_threshold = economic_threshold
        self.scout_interval = scout_interval
        self.spray_efficacy = spray_efficacy
        self.rng = np.random.default_rng(seed)
        self._last_scout: dict[tuple[int, int], float] = {}

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

        if time_step % self.scout_interval != 0:
            return {
                "n_sprays": 0.0,
                "spray_volume_L": 0.0,
                "false_sprays": 0.0,
                "missed_cells": 0.0,
            }

        for r in range(field.rows):
            for c in range(field.cols):
                observed = field.pests[r][c].density * float(self.rng.uniform(0.6, 1.4))
                self._last_scout[(r, c)] = observed

                actual_above = field.pests[r][c].density > self.economic_threshold
                observed_above = observed > self.economic_threshold

                if observed_above and weather.is_spray_safe:
                    n_sprays += 1.0
                    spray_volume += 2.0
                    field.apply_pesticide(r, c, self.spray_efficacy, self.rng)
                    if not actual_above:
                        false_sprays += 1.0
                elif actual_above:
                    missed += 1.0

        return {
            "n_sprays": n_sprays,
            "spray_volume_L": spray_volume,
            "false_sprays": false_sprays,
            "missed_cells": missed,
        }

    def reset(self) -> None:
        self._last_scout.clear()
