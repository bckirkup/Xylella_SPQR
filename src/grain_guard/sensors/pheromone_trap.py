"""Pheromone trap sensor: species-specific adult pest counts (spec §4.3)."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from grain_guard.environment.pest import PestPopulation


class PheromoneTrap(BaseModel):
    """Fixed pheromone trap providing direct pest counts.

    Species-specific but spatially sparse. Provides ground-truth
    calibration for aerial scouts.
    """

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    catch_efficiency: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Fraction of local adults caught"
    )

    def observe(self, pest: PestPopulation, time_step: int, rng: np.random.Generator) -> np.ndarray:
        """Return [catch_count, resistance_proxy] for this trap location.

        Output dimensionality: 2.
        """
        catch = pest.density * self.catch_efficiency * float(rng.uniform(0.7, 1.3))
        resistance_proxy = pest.resistance_freq + float(rng.normal(0, 0.05))
        return np.array(
            [max(0.0, catch), float(np.clip(resistance_proxy, 0.0, 1.0))],
            dtype=np.float64,
        )

    @property
    def output_dim(self) -> int:
        return 2
