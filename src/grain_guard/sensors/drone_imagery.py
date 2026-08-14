"""On-demand drone imagery sensor: high-res RGB + multispectral + thermal (spec §4.2)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from grain_guard.environment.crop import CropCell
from grain_guard.environment.pest import PestPopulation
from grain_guard.environment.weed import WeedPopulation


class DroneImager(BaseModel):
    """High-resolution on-demand drone sensor.

    Provides cell-level pest and weed detection with cost per flight.
    Can discriminate pest damage at leaf level.
    """

    cost_per_flight: float = Field(default=0.5, ge=0.0, description="Energy cost per flight")
    detection_noise: float = Field(
        default=0.05, ge=0.0, description="Noise σ for detection observations"
    )

    def observe(
        self,
        crop: CropCell,
        pest: PestPopulation,
        weed: WeedPopulation,
        rng: np.random.Generator,
    ) -> NDArray[np.float64]:
        """Return [pest_signal, weed_signal, stress_signal, thermal_anomaly] for one cell.

        Output dimensionality: 4.
        """
        pest_signal = pest.density * pest.detectability + float(rng.normal(0, self.detection_noise))
        weed_signal = weed.detectability + float(rng.normal(0, self.detection_noise))
        stress_signal = 1.0 - crop.health + float(rng.normal(0, self.detection_noise))
        thermal = (1.0 - crop.soil_moisture) * 0.5 + float(rng.normal(0, self.detection_noise))
        return np.array(
            [
                max(0.0, pest_signal),
                max(0.0, weed_signal),
                max(0.0, stress_signal),
                max(0.0, thermal),
            ],
            dtype=np.float64,
        )

    @property
    def output_dim(self) -> int:
        return 4
