"""Tests for the shared selection-gradient estimators.

The estimators are the measuring instrument for both the pest reference loop
and the detector side, so they are tested for graded sensitivity (ordered
responses to ordered inputs), bounds/invariants, and explicit ``None`` on
degenerate samples rather than a misleading zero.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from grain_guard.analysis.detector_gradient import AgentRecord, LineageTracker
from grain_guard.analysis.gradient import (
    LineagePairs,
    estimate_gradient,
    opportunity_for_selection,
    parent_offspring_regression,
    regress,
    selection_differential,
)
from grain_guard.analysis.pest_reference import PestCellSnapshot, PestTrajectory


def _pairs(
    parent_trait: list[float],
    offspring_trait: list[float],
    parent_fitness: list[float] | None = None,
    offspring_fitness: list[float] | None = None,
) -> LineagePairs:
    return LineagePairs(
        parent_trait=parent_trait,
        offspring_trait=offspring_trait,
        parent_fitness=parent_fitness if parent_fitness is not None else list(parent_trait),
        offspring_fitness=(
            offspring_fitness if offspring_fitness is not None else list(offspring_trait)
        ),
    )


class TestOpportunityForSelection:
    def test_graded_in_fitness_spread(self) -> None:
        """Wider relative-fitness spread at equal mean must score higher."""
        arms = [
            [2.0, 2.0, 2.0, 2.0],
            [1.0, 2.0, 2.0, 3.0],
            [0.0, 1.0, 3.0, 4.0],
        ]
        scores = [opportunity_for_selection(arm) for arm in arms]
        assert all(s is not None for s in scores)
        assert scores[0] < scores[1] < scores[2]  # type: ignore[operator]

    def test_zero_when_no_variance(self) -> None:
        assert opportunity_for_selection([3.0] * 5) == pytest.approx(0.0)

    def test_none_when_nobody_reproduces(self) -> None:
        assert opportunity_for_selection([0.0, 0.0, 0.0]) is None

    def test_none_for_single_unit(self) -> None:
        assert opportunity_for_selection([1.0]) is None

    def test_scale_invariant(self) -> None:
        base = [1.0, 2.0, 5.0, 8.0]
        scaled = [10.0 * v for v in base]
        assert opportunity_for_selection(base) == pytest.approx(opportunity_for_selection(scaled))


class TestSelectionDifferential:
    def test_sign_and_magnitude_track_trait_fitness_coupling(self) -> None:
        traits = [0.0, 1.0, 2.0, 3.0]
        aligned = selection_differential(traits, [1.0, 2.0, 3.0, 4.0])
        flat = selection_differential(traits, [2.5, 2.5, 2.5, 2.5])
        opposed = selection_differential(traits, [4.0, 3.0, 2.0, 1.0])
        assert flat == pytest.approx(0.0)
        assert opposed is not None
        assert aligned is not None
        assert opposed < 0.0
        assert aligned > 0.0

    def test_graded_across_coupling_strengths(self) -> None:
        traits = [0.0, 1.0, 2.0, 3.0]
        weak = selection_differential(traits, [2.0, 2.2, 2.4, 2.6])
        strong = selection_differential(traits, [1.0, 2.0, 3.0, 4.0])
        assert weak is not None
        assert strong is not None
        assert weak > 0.0
        assert weak < strong

    def test_none_when_mean_fitness_is_zero(self) -> None:
        assert selection_differential([0.0, 1.0], [0.0, 0.0]) is None

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            selection_differential([1.0, 2.0], [1.0])


class TestRegression:
    def test_recovers_known_slope(self) -> None:
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        fit = regress(x, [0.5 * v + 3.0 for v in x])
        assert fit.slope == pytest.approx(0.5)
        assert fit.correlation == pytest.approx(1.0)
        assert fit.n == len(x)

    def test_correlation_stays_in_bounds_on_noisy_data(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.normal(size=200)
        y = 0.4 * x + rng.normal(size=200)
        fit = regress(x.tolist(), y.tolist())
        assert fit.correlation is not None
        assert -1.0 <= fit.correlation <= 1.0
        assert math.isfinite(fit.slope or math.nan)

    def test_graded_heritability(self) -> None:
        """Stronger parent-offspring transmission must yield a larger slope."""
        parents = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        slopes = []
        for transmission in (0.0, 0.5, 1.0):
            offspring = [0.35 + transmission * (p - 0.35) for p in parents]
            fit = parent_offspring_regression(parents, offspring)
            slopes.append(0.0 if fit.slope is None else fit.slope)
        assert slopes[0] < slopes[1] < slopes[2]
        assert slopes[2] == pytest.approx(1.0)

    def test_none_when_parent_trait_has_no_variance(self) -> None:
        fit = parent_offspring_regression([0.3] * 5, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert fit.slope is None
        assert fit.correlation is None

    def test_float_noise_on_a_frozen_trait_is_not_variance(self) -> None:
        """A trait that differs only in its last bits must not look heritable."""
        parents = [0.1, 0.1 + 7e-17, 0.1, 0.1 + 7e-17, 0.1]
        fit = parent_offspring_regression(parents, parents)
        assert fit.slope is None
        assert fit.correlation is None
        assert selection_differential(parents, [0.0, 1.0, 2.0, 1.0, 0.0]) == pytest.approx(0.0)

    def test_none_below_minimum_pairs(self) -> None:
        fit = regress([1.0, 2.0], [1.0, 2.0])
        assert fit.slope is None
        assert fit.n == 2


class TestEstimateGradient:
    def test_reports_every_component_with_finite_values(self) -> None:
        traits = [0.1, 0.2, 0.3, 0.4, 0.5]
        fitness = [0.0, 1.0, 1.0, 2.0, 3.0]
        est = estimate_gradient(
            traits, fitness, _pairs(traits[:-1], traits[1:], fitness[:-1], fitness[1:])
        )
        assert est.n_units == len(traits)
        assert est.mean_fitness == pytest.approx(np.mean(fitness))
        assert est.fitness_variance >= 0.0
        assert est.trait_variance >= 0.0
        assert est.n_lineage_pairs == len(traits) - 1
        assert est.parent_offspring_trait_correlation is not None
        assert -1.0 <= est.parent_offspring_trait_correlation <= 1.0
        assert est.parent_child_reproductive_correlation is not None
        assert -1.0 <= est.parent_child_reproductive_correlation <= 1.0

    def test_frozen_trait_yields_null_not_zero_heritability(self) -> None:
        traits = [0.3] * 6
        fitness = [0.0, 1.0, 2.0, 0.0, 1.0, 2.0]
        est = estimate_gradient(traits, fitness, _pairs(traits, traits, fitness, fitness))
        assert est.trait_variance == pytest.approx(0.0)
        assert est.heritability is None
        assert est.selection_differential == pytest.approx(0.0)


class TestPestTrajectory:
    def test_records_only_generation_boundaries(self) -> None:
        traj = PestTrajectory(generation_steps=5)
        from grain_guard.environment.field import CropField

        crop_field = CropField(rows=2, cols=2)
        for step in range(11):
            traj.record(crop_field, step)
        assert traj.steps_recorded == 11
        assert traj.n_generations == 3

    def test_no_estimates_before_two_generations(self) -> None:
        traj = PestTrajectory(generation_steps=5)
        traj.snapshots.append([PestCellSnapshot(1.0, 0.1, 0.01)])
        assert traj.estimates() is None

    def test_growing_cells_score_higher_fitness_than_shrinking(self) -> None:
        traj = PestTrajectory(generation_steps=1)
        for scale in (1.0, 1.0, 1.0):
            traj.snapshots.append(
                [
                    PestCellSnapshot(density=scale * 10.0, night_feeding=0.1, resistance_freq=0.01),
                    PestCellSnapshot(density=scale * 10.0, night_feeding=0.5, resistance_freq=0.01),
                ]
            )
        # Second cell (high night_feeding) grows, first shrinks.
        traj.snapshots[1][0] = PestCellSnapshot(5.0, 0.1, 0.01)
        traj.snapshots[1][1] = PestCellSnapshot(20.0, 0.5, 0.01)
        traj.snapshots[2][0] = PestCellSnapshot(2.5, 0.1, 0.01)
        traj.snapshots[2][1] = PestCellSnapshot(40.0, 0.5, 0.01)
        est = traj.estimates()
        assert est is not None
        assert est.selection_differential is not None
        assert est.selection_differential > 0.0

    def test_trait_summary_is_empty_without_snapshots(self) -> None:
        assert PestTrajectory().trait_summary() == {}


class TestLineageTracker:
    def _tracker(self) -> LineageTracker:
        tracker = LineageTracker(last_step=100)
        # Parent thresholds 0.1..0.5, offspring inherit exactly, fitness tracks trait.
        for index, threshold in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
            parent = AgentRecord(
                agent_id=f"p{index}",
                parent_id=None,
                first_seen_step=0,
                escalation_threshold=threshold,
                offspring=index,
                reports_issued=10,
                correct_reports=index * 2,
            )
            child = AgentRecord(
                agent_id=f"c{index}",
                parent_id=f"p{index}",
                first_seen_step=10,
                escalation_threshold=threshold,
                offspring=index,
                reports_issued=10,
                correct_reports=index * 2,
            )
            tracker.records[parent.agent_id] = parent
            tracker.records[child.agent_id] = child
        return tracker

    def test_maturity_cutoff_excludes_late_arrivals(self) -> None:
        tracker = self._tracker()
        tracker.records["late"] = AgentRecord("late", None, 99, 0.3)
        scored = tracker.scored_records()
        assert all(r.first_seen_step <= 75 for r in scored)
        assert "late" not in {r.agent_id for r in scored}

    def test_estimates_recover_perfect_transmission(self) -> None:
        est = self._tracker().estimates()
        assert est is not None
        assert est.heritability == pytest.approx(1.0)
        assert est.parent_child_reproductive_correlation == pytest.approx(1.0)

    def test_function_selection_differential_positive_when_accuracy_pays(self) -> None:
        diff = self._tracker().function_selection_differential()
        assert diff is not None
        assert diff > 0.0

    def test_summary_fractions_stay_in_bounds(self) -> None:
        summary = self._tracker().summary()
        assert 0.0 <= summary["reproducing_fraction"] <= 1.0
        assert 0.0 <= summary["scored_report_precision"] <= 1.0
        assert summary["n_agents_scored"] <= summary["n_agents_observed"]

    def test_report_precision_zero_without_reports(self) -> None:
        assert AgentRecord("a", None, 0, 0.3).report_precision == pytest.approx(0.0)

    def test_estimates_none_for_tiny_cohort(self) -> None:
        tracker = LineageTracker(last_step=10)
        tracker.records["a"] = AgentRecord("a", None, 0, 0.3)
        assert tracker.estimates() is None
