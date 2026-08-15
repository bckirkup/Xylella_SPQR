"""Selection-gradient measurement for the pest and detector sides."""

from __future__ import annotations

from grain_guard.analysis.arms import ArmSpec, run_arm
from grain_guard.analysis.detector_gradient import AgentRecord, LineageTracker
from grain_guard.analysis.gradient import (
    GradientEstimates,
    LineagePairs,
    Regression,
    estimate_gradient,
    opportunity_for_selection,
    parent_offspring_regression,
    regress,
    selection_differential,
)
from grain_guard.analysis.pest_reference import PestCellSnapshot, PestTrajectory

__all__ = [
    "AgentRecord",
    "ArmSpec",
    "GradientEstimates",
    "LineagePairs",
    "LineageTracker",
    "PestCellSnapshot",
    "PestTrajectory",
    "Regression",
    "estimate_gradient",
    "opportunity_for_selection",
    "parent_offspring_regression",
    "regress",
    "run_arm",
    "selection_differential",
]
