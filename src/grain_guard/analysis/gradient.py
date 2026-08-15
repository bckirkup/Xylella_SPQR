"""Quantitative-genetic estimators for a selection gradient.

The same estimators are applied to the pest adversary and to the agent
(detector) side so the two can be compared with one set of definitions:

- ``selection_differential``: covariance of a trait with relative fitness
  (Robertson / Price form), in trait units.
- ``parent_offspring_regression``: slope of offspring trait on parent trait
  (a heritability estimate for clonal / asexual lineages) and the matching
  correlation.
- ``opportunity_for_selection``: variance of relative fitness,
  ``var(w) / mean(w)**2``.

Every estimator returns ``None`` when its sample is too small or degenerate
(zero variance, zero mean fitness) rather than a misleading zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MIN_PAIRS = 3
"""Smallest sample a regression or correlation is reported for."""

VARIANCE_EPSILON = 1e-9
"""Relative spread below which a sample counts as having no variance.

A frozen trait can still differ in its last floating-point bits after values
are mixed and rewritten (dispersal averages densities and traits), which would
otherwise make a regression on a constant trait return a spurious slope of
exactly 1.0 instead of ``None``.
"""


def _has_variance(values: np.ndarray) -> bool:
    """Whether a sample's spread is larger than floating-point noise."""
    scale = 1.0 + abs(float(values.mean()))
    return float(np.sqrt(values.var())) > VARIANCE_EPSILON * scale


@dataclass(frozen=True)
class Regression:
    """Least-squares fit of ``y`` on ``x``.

    Attributes:
        slope: fitted slope, ``None`` when undefined.
        correlation: Pearson correlation, ``None`` when undefined.
        n: number of paired observations.
    """

    slope: float | None
    correlation: float | None
    n: int


@dataclass(frozen=True)
class GradientEstimates:
    """One side's selection gradient, measured over completed lineages.

    Attributes:
        n_units: number of reproducing units scored for fitness.
        mean_fitness: mean per-unit reproductive output.
        fitness_variance: variance of per-unit reproductive output.
        opportunity_for_selection: variance of relative fitness.
        selection_differential: covariance of the focal trait with relative
            fitness, in trait units.
        trait_variance: variance of the focal trait across units.
        heritability: parent-offspring regression slope for the focal trait.
        parent_offspring_trait_correlation: correlation of the same pairs.
        parent_child_reproductive_correlation: correlation between a parent's
            reproductive output and its offspring's reproductive output.
        n_lineage_pairs: number of parent-offspring pairs available.
    """

    n_units: int
    mean_fitness: float
    fitness_variance: float
    opportunity_for_selection: float | None
    selection_differential: float | None
    trait_variance: float
    heritability: float | None
    parent_offspring_trait_correlation: float | None
    parent_child_reproductive_correlation: float | None
    n_lineage_pairs: int


def _as_array(values: Sequence[float]) -> np.ndarray:
    return np.asarray(list(values), dtype=np.float64)


def opportunity_for_selection(fitness: Sequence[float]) -> float | None:
    """Return ``var(w) / mean(w)**2``, or ``None`` when mean fitness is zero."""
    w = _as_array(fitness)
    if w.size < 2:
        return None
    mean = float(w.mean())
    if mean <= 0.0:
        return None
    return float(w.var() / (mean * mean))


def selection_differential(traits: Sequence[float], fitness: Sequence[float]) -> float | None:
    """Return ``cov(trait, fitness) / mean(fitness)`` in trait units."""
    z = _as_array(traits)
    w = _as_array(fitness)
    if z.size != w.size:
        raise ValueError("traits and fitness must have equal length")
    if z.size < 2:
        return None
    mean_w = float(w.mean())
    if mean_w <= 0.0:
        return None
    if not _has_variance(z):
        return 0.0
    covariance = float(((z - z.mean()) * (w - mean_w)).mean())
    return covariance / mean_w


def regress(x: Sequence[float], y: Sequence[float]) -> Regression:
    """Least-squares regression of ``y`` on ``x`` with its correlation."""
    xs = _as_array(x)
    ys = _as_array(y)
    if xs.size != ys.size:
        raise ValueError("x and y must have equal length")
    if xs.size < MIN_PAIRS:
        return Regression(slope=None, correlation=None, n=int(xs.size))
    if not _has_variance(xs):
        return Regression(slope=None, correlation=None, n=int(xs.size))
    x_var = float(xs.var())
    y_var = float(ys.var())
    covariance = float(((xs - xs.mean()) * (ys - ys.mean())).mean())
    slope = covariance / x_var
    correlation = None if not _has_variance(ys) else covariance / float(np.sqrt(x_var * y_var))
    return Regression(slope=slope, correlation=correlation, n=int(xs.size))


def parent_offspring_regression(
    parent_traits: Sequence[float], offspring_traits: Sequence[float]
) -> Regression:
    """Heritability estimate for clonal lineages: offspring trait on parent trait."""
    return regress(parent_traits, offspring_traits)


@dataclass(frozen=True)
class LineagePairs:
    """Paired parent and offspring measurements.

    Attributes:
        parent_trait: focal trait of each parent.
        offspring_trait: focal trait of the matched offspring.
        parent_fitness: reproductive output of each parent.
        offspring_fitness: reproductive output of the matched offspring.
    """

    parent_trait: list[float]
    offspring_trait: list[float]
    parent_fitness: list[float]
    offspring_fitness: list[float]

    def __len__(self) -> int:
        return len(self.parent_trait)


def estimate_gradient(
    traits: Sequence[float],
    fitness: Sequence[float],
    pairs: LineagePairs,
) -> GradientEstimates:
    """Combine within-generation selection with across-generation transmission."""
    z = list(traits)
    w = list(fitness)
    trait_fit = parent_offspring_regression(pairs.parent_trait, pairs.offspring_trait)
    fitness_fit = regress(pairs.parent_fitness, pairs.offspring_fitness)
    w_array = _as_array(w)
    z_array = _as_array(z)
    return GradientEstimates(
        n_units=len(z),
        mean_fitness=float(w_array.mean()) if w else 0.0,
        fitness_variance=float(w_array.var()) if w else 0.0,
        opportunity_for_selection=opportunity_for_selection(w),
        selection_differential=selection_differential(z, w),
        trait_variance=float(z_array.var()) if z else 0.0,
        heritability=trait_fit.slope,
        parent_offspring_trait_correlation=trait_fit.correlation,
        parent_child_reproductive_correlation=fitness_fit.correlation,
        n_lineage_pairs=len(pairs),
    )
