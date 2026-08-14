"""Yield monitor: delayed harvest-time ground truth (spec §4.6)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from grain_guard.environment.crop import CropCell, GrowthStage


class YieldMonitor(BaseModel):
    """Harvest-time yield monitor providing retrospective ground truth.

    Only produces data after crops reach MATURE or HARVESTED stage.
    """

    n_zones: int = Field(default=5, ge=1, description="Number of yield aggregation zones")

    def observe(
        self, crops: list[list[CropCell]], rng: np.random.Generator
    ) -> NDArray[np.float64] | None:
        """Return per-zone yield vector or None if not harvest time.

        Only returns data when >50% of cells are mature or harvested.
        Output dimensionality: n_zones.
        """
        rows = len(crops)
        cols = len(crops[0]) if rows > 0 else 0
        total_cells = rows * cols
        if total_cells == 0:
            return None

        mature_count = sum(
            1
            for r in range(rows)
            for c in range(cols)
            if crops[r][c].growth_stage in (GrowthStage.MATURE, GrowthStage.HARVESTED)
        )
        if mature_count < total_cells * 0.5:
            return None

        zone_yields: list[float] = []
        for z in range(self.n_zones):
            r_start = z * rows // self.n_zones
            r_end = (z + 1) * rows // self.n_zones
            zone_yield = 0.0
            zone_count = 0
            for r in range(r_start, max(r_end, r_start + 1)):
                for c in range(cols):
                    if r < rows:
                        zone_yield += crops[r][c].yield_potential
                        zone_count += 1
            avg = zone_yield / max(zone_count, 1)
            zone_yields.append(avg + float(rng.normal(0, 0.02)))
        return np.array(zone_yields, dtype=np.float64)

    @property
    def output_dim(self) -> int:
        return self.n_zones
