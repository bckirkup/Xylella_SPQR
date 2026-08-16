"""Selection-gradient measurement for the pest and detector sides."""

from __future__ import annotations

from grain_guard.analysis.arms import ArmRun, ArmSpec, execute_arm, run_arm
from grain_guard.analysis.designed_reporter import (
    POLICY_ARMS,
    OracleDiagnosticPolicy,
    exploitable_margin,
    measure_designed_arm,
    summarize_policy_arm,
)
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
    "POLICY_ARMS",
    "AgentRecord",
    "ArmRun",
    "ArmSpec",
    "GradientEstimates",
    "LineagePairs",
    "LineageTracker",
    "OracleDiagnosticPolicy",
    "PestCellSnapshot",
    "PestTrajectory",
    "Regression",
    "estimate_gradient",
    "execute_arm",
    "exploitable_margin",
    "measure_designed_arm",
    "summarize_policy_arm",
    "opportunity_for_selection",
    "parent_offspring_regression",
    "regress",
    "run_arm",
    "selection_differential",
]
