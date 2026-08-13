"""Satellite multispectral sensor: NDVI, NDRE, chlorophyll indices per zone (spec §4.1)."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from grain_guard.environment.crop import CropCell


class SatelliteSensor(BaseModel):
    """Sentinel-2 / PlanetScope-like satellite imagery.

    Provides zone-level vegetation indices at coarse resolution with
    fixed revisit cadence. Detects crop stress but NOT pest-specific.
    """

    resolution_m: float = Field(default=10.0, ge=1.0, description="Spatial resolution in meters")
    revisit_days: int = Field(default=5, ge=1, description="Revisit interval in time steps")
    zone_rows: int = Field(default=5, ge=1, description="Zone aggregation rows")
    zone_cols: int = Field(default=5, ge=1, description="Zone aggregation cols")

    def observe(
        self,
        crops: list[list[CropCell]],
        time_step: int,
        rng: np.random.Generator,
    ) -> np.ndarray | None:
        """Return zone-level [NDVI, NDRE, chlorophyll] or None if not revisit step.

        Output dimensionality: zone_rows * zone_cols * 3.
        """
        if time_step % self.revisit_days != 0:
            return None
        field_rows = len(crops)
        field_cols = len(crops[0]) if field_rows > 0 else 0
        result: list[float] = []
        for zr in range(self.zone_rows):
            for zc in range(self.zone_cols):
                result.extend(self._observe_zone(crops, zr, zc, field_rows, field_cols, rng))
        return np.array(result, dtype=np.float64)

    def _observe_zone(
        self,
        crops: list[list[CropCell]],
        zone_row: int,
        zone_col: int,
        field_rows: int,
        field_cols: int,
        rng: np.random.Generator,
    ) -> list[float]:
        r_start = zone_row * field_rows // self.zone_rows
        r_end = (zone_row + 1) * field_rows // self.zone_rows
        c_start = zone_col * field_cols // self.zone_cols
        c_end = (zone_col + 1) * field_cols // self.zone_cols
        ndvi_sum = 0.0
        count = 0
        for r in range(r_start, max(r_end, r_start + 1)):
            for c in range(c_start, max(c_end, c_start + 1)):
                if r < field_rows and c < field_cols:
                    ndvi_sum += crops[r][c].ndvi_proxy
                    count += 1
        ndvi = ndvi_sum / max(count, 1)
        ndre = ndvi * 0.8 + float(rng.normal(0, 0.02))
        chlorophyll = ndvi * 1.2 + float(rng.normal(0, 0.03))
        return [ndvi + float(rng.normal(0, 0.01)), ndre, chlorophyll]

    @property
    def output_dim(self) -> int:
        return self.zone_rows * self.zone_cols * 3
