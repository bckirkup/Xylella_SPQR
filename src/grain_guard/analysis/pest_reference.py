"""Pest-side reference measurement: the shape of a working selection gradient.

The pest adversary is the reference loop in this domain. Each grid cell holds a
clonal pest line, so a cell is the reproducing unit: its per-capita density
change over one pest generation is its realized fitness, and its behavioral
escape trait is transmitted to the next generation of the same cell.

The same estimators from :mod:`grain_guard.analysis.gradient` are then applied
to the agent side, so pest and detector numbers are directly comparable.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from grain_guard.analysis.gradient import (
    GradientEstimates,
    LineagePairs,
    estimate_gradient,
)
from grain_guard.environment.field import CropField

MIN_DENSITY = 1e-6
"""Density below which a cell is treated as unoccupied and not scored."""


@dataclass(frozen=True)
class PestCellSnapshot:
    """One cell's pest state at a generation boundary.

    Attributes:
        density: pest density in the cell.
        night_feeding: focal behavioral escape trait.
        resistance_freq: pesticide resistance allele frequency.
    """

    density: float
    night_feeding: float
    resistance_freq: float


@dataclass
class PestTrajectory:
    """Per-generation snapshots of the pest population.

    Attributes:
        generation_steps: number of simulation steps per recorded generation.
        snapshots: recorded generation boundaries, each a flat list of cells.
        steps_recorded: number of ``record`` calls made.
    """

    generation_steps: int = 14
    snapshots: list[list[PestCellSnapshot]] = dataclass_field(default_factory=list)
    steps_recorded: int = 0

    def record(self, crop_field: CropField, step: int) -> None:
        """Record a generation boundary if ``step`` lands on one."""
        self.steps_recorded += 1
        if step % self.generation_steps != 0:
            return
        cells = [
            PestCellSnapshot(
                density=pest.density,
                night_feeding=pest.night_feeding,
                resistance_freq=pest.resistance_freq,
            )
            for row in crop_field.pests
            for pest in row
        ]
        self.snapshots.append(cells)

    @property
    def n_generations(self) -> int:
        """Number of recorded generation boundaries."""
        return len(self.snapshots)

    def _window_fitness(self, index: int) -> dict[int, float]:
        """Per-capita density change of each occupied cell over one generation."""
        start = self.snapshots[index]
        end = self.snapshots[index + 1]
        return {
            i: end[i].density / start[i].density
            for i in range(len(start))
            if start[i].density > MIN_DENSITY
        }

    def estimates(self) -> GradientEstimates | None:
        """Estimate the pest-side gradient, or ``None`` without two generations."""
        if self.n_generations < 2:
            return None
        last = self.n_generations - 2
        fitness_by_cell = self._window_fitness(last)
        traits = [self.snapshots[last][i].night_feeding for i in fitness_by_cell]
        fitness = list(fitness_by_cell.values())
        return estimate_gradient(traits, fitness, self._lineage_pairs())

    def _lineage_pairs(self) -> LineagePairs:
        """Pair each cell's generation with the next generation of the same cell."""
        pairs = LineagePairs([], [], [], [])
        for index in range(self.n_generations - 2):
            parent_fitness = self._window_fitness(index)
            child_fitness = self._window_fitness(index + 1)
            for cell in parent_fitness:
                if cell not in child_fitness:
                    continue
                pairs.parent_trait.append(self.snapshots[index][cell].night_feeding)
                pairs.offspring_trait.append(self.snapshots[index + 1][cell].night_feeding)
                pairs.parent_fitness.append(parent_fitness[cell])
                pairs.offspring_fitness.append(child_fitness[cell])
        return pairs

    def trait_summary(self) -> dict[str, float]:
        """Mean focal traits at the first and last recorded generation."""
        if not self.snapshots:
            return {}
        first = self.snapshots[0]
        last = self.snapshots[-1]
        return {
            "night_feeding_first": sum(c.night_feeding for c in first) / len(first),
            "night_feeding_last": sum(c.night_feeding for c in last) / len(last),
            "resistance_freq_first": sum(c.resistance_freq for c in first) / len(first),
            "resistance_freq_last": sum(c.resistance_freq for c in last) / len(last),
            "mean_density_last": sum(c.density for c in last) / len(last),
        }
