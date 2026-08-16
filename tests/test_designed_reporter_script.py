"""Output-path validation and rendering for the designed-reporter script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> ModuleType:
    """Import the measurement script, which lives outside the package."""
    path = REPO_ROOT / "scripts" / "run_designed_reporter_experiment.py"
    spec = importlib.util.spec_from_file_location("run_designed_reporter_experiment", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


class TestSafeOutputDir:
    @pytest.mark.parametrize("raw", ["docs", "docs/designed", "a/b/c", "out-2"])
    def test_accepts_relative_names_under_the_repo(self, raw: str) -> None:
        resolved = SCRIPT.safe_output_dir(raw)
        assert resolved == REPO_ROOT / raw
        assert resolved.is_relative_to(REPO_ROOT)

    @pytest.mark.parametrize(
        "raw", ["/tmp/x", "../x", "./x", "a/../b", "", "a//b", "~/x", "a b", "out.json"]
    )
    def test_rejects_absolute_and_traversing_names(self, raw: str) -> None:
        with pytest.raises(ValueError, match="relative directory"):
            SCRIPT.safe_output_dir(raw)


def _arm(policy_arm: str, precision: float | None, *, scored: bool = True) -> dict[str, Any]:
    return {
        "policy_arm": policy_arm,
        "n_seeds": 21,
        "reporting_precision": precision,
        "scoring_reports": 500 if scored else 3,
        "scored": scored,
        "mean_static_prior_null": 0.5,
        "mean_uniform_null": 0.0025,
        "mean_reports_per_adult_lifetime": 4.0,
        "mean_any_evidence_rate": 0.93,
        "mean_detector_parent_child_reproductive_correlation": 0.04,
        "mean_pest_parent_child_reproductive_correlation": 0.21,
        "n_extinct_seeds": 0,
    }


def _results(best_precision: float, ordinary_precision: float) -> dict[str, Any]:
    margin = {
        "static_prior_null": 0.5,
        "best_arm": "all_designed_seed",
        "best_reachable_precision": best_precision,
        "exploitable_margin_pp": (best_precision - 0.5) * 100.0,
        "exploitable_margin_positive": best_precision > 0.5,
        "oracle_precision": 1.0,
        "oracle_margin_pp": 50.0,
        "ordinary_precision": ordinary_precision,
        "ordinary_margin_pp": (ordinary_precision - 0.5) * 100.0,
        "unscored_arms": [],
    }
    return {
        "configuration": {
            "seeds": list(range(1000, 1021)),
            "steps": 400,
            "grounded_input_fraction": 0.67,
            "pest_evolution_frozen": True,
            "reporter_policy": "grain_trap_drone_evidence",
            "reporter_threshold_density": 10.0,
            "min_scored_reports": 20,
        },
        "margin": margin,
        "arms": [_arm("ordinary", ordinary_precision), _arm("all_designed_seed", best_precision)],
    }


class TestMarkdownReport:
    def test_report_states_the_margin_and_the_frozen_pest(self) -> None:
        report = SCRIPT.markdown_report(_results(0.72, 0.40))
        assert "## Answer" in report
        assert "+22.00" in report
        assert "freeze_pest_evolution=True" in report
        assert "diagnostic ceiling" in report
        assert "`ordinary`" in report
        assert "`all_designed_seed`" in report

    @pytest.mark.parametrize(
        ("best", "expected"),
        [(0.2, "no positive exploitable margin"), (0.9, "positive exploitable margin")],
    )
    def test_verdict_follows_the_sign_of_the_margin(self, best: float, expected: str) -> None:
        assert expected in SCRIPT.markdown_report(_results(best, 0.4))

    @pytest.mark.parametrize(
        ("ordinary", "expected"),
        [(0.4, "stays below the static-prior null"), (0.8, "sits above the static-prior null")],
    )
    def test_evolved_arm_placement_follows_its_own_margin(
        self, ordinary: float, expected: str
    ) -> None:
        assert expected in SCRIPT.markdown_report(_results(0.9, ordinary))

    def test_unmeasured_margin_is_reported_as_unmeasured(self) -> None:
        results = _results(0.9, 0.4)
        results["margin"]["exploitable_margin_positive"] = None
        results["margin"]["exploitable_margin_pp"] = None
        results["margin"]["ordinary_margin_pp"] = None
        report = SCRIPT.markdown_report(results)
        assert "unmeasured" in report
        assert "too few scored reports" in report

    def test_unscored_arms_print_unscored_rather_than_a_precision(self) -> None:
        results = _results(0.72, 0.40)
        results["arms"].append(_arm("invasion", 0.0, scored=False))
        report = SCRIPT.markdown_report(results)
        table = [line for line in report.splitlines() if line.startswith("| Headline precision")]
        assert table == ["| Headline precision | `0.4000` | `0.7200` | `unscored` |"]

    def test_artifacts_round_trip_to_the_requested_directory(self, tmp_path: Path) -> None:
        results = _results(0.72, 0.40)
        json_path, report_path = SCRIPT.write_artifacts(results, tmp_path)
        assert json.loads(json_path.read_text(encoding="utf-8"))["margin"]["best_arm"] == (
            "all_designed_seed"
        )
        assert report_path.read_text(encoding="utf-8").startswith("# Designed-reporter measurement")
