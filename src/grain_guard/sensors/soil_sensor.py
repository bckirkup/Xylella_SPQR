"""IoT soil moisture sensor (spec §4.5)."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from grain_guard.environment.crop import CropCell


class SoilSensor(BaseModel):
    """Fixed IoT soil moisture probe.

    Distinguishes drought stress from pest-induced stress.
    """

    row: int = Field(ge=0)
    col: int = Field(ge=0)

    def observe(self, crop: CropCell, rng: np.random.Generator) -> np.ndarray:
        """Return [moisture, temperature_proxy, conductivity_proxy].

        Output dimensionality: 3.
        """
        moisture = float(np.clip(crop.soil_moisture + rng.normal(0, 0.02), 0.0, 1.0))
        temp_proxy = 20.0 + (1.0 - crop.soil_moisture) * 10.0 + float(rng.normal(0, 1.0))
        conductivity = 0.5 * crop.soil_moisture + float(rng.normal(0, 0.05))
        return np.array([moisture, temp_proxy, max(0.0, conductivity)], dtype=np.float64)

    @property
    def output_dim(self) -> int:
        return 3
