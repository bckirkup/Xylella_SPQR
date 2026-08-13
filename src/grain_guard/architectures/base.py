"""Base class for competing management architectures."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


class SprayMetrics(NamedTuple):
    """Per-cell management metrics accumulated by an architecture step."""

    sprays: float
    volume: float
    false_sprays: float
    missed: float


class Architecture(ABC):
    """Abstract base for a pest/weed management architecture.

    All architectures receive identical sensor access and operate
    on the same field. No strawmen.
    """

    @abstractmethod
    def step(
        self,
        field: CropField,
        weather: AgWeather,
        time_step: int,
    ) -> dict[str, float]:
        """Execute one management step.

        Returns dict with keys: n_sprays, spray_volume_L, false_sprays, missed_cells.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state for a new simulation run."""
