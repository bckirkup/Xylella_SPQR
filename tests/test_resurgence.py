"""Tests for the domain-side resurgence sanity experiment."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from grain_guard.analysis.resurgence import (
    INDISCRIMINATE,
    NO_SPRAY,
    PRECISE,
    resurgence_verdict,
    run_resurgence_arm,
    run_resurgence_experiment,
    summarize_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> ModuleType:
    """Import the measurement script, which lives outside the package."""
    path = REPO_ROOT / "scripts" / "run_resurgence_experiment.py"
    spec = importlib.util.spec_from_file_location("run_resurgence_experiment", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()

# Short windows: these tests check the instrument, not the production numbers.
SHORT_STEPS = 60
SMALL_GRID = 8


def _short_run(policy: str, seed: int = 1000, *, ecology_enabled: bool = True) -> Any:
    return run_resurgence_arm(
        policy,
        seed,
        steps=SHORT_STEPS,
        ecology_enabled=ecology_enabled,
        grid_rows=SMALL_GRID,
        grid_cols=SMALL_GRID,
        pest_intro_probability=0.1,
    )


def _summary(policy: str, **overrides: float) -> dict[str, Any]:
    base: dict[str, Any] = {
        "policy": policy,
        "n_seeds": 3,
        "ecology_enabled": True,
        "mean_sprays": 100.0,
        "mean_primary_density": 100.0,
        "mean_secondary_density": 10.0,
        "mean_total_density": 110.0,
        "mean_beneficial_density": 50.0,
        "mean_primary_pest_days": 100.0,
        "mean_secondary_pest_days": 10.0,
        "mean_total_pest_days": 110.0,
        "mean_peak_total_density": 200.0,
        "mean_crop_health": 0.5,
        "mean_yield_potential": 0.5,
    }
    base.update(overrides)
    return base


class TestSprayPolicies:
    def test_spray_counts_are_ordered_by_policy_selectivity(self) -> None:
        counts = [_short_run(policy, 1000).sprays for policy in (NO_SPRAY, PRECISE, INDISCRIMINATE)]
        assert counts[0] == 0
        assert counts[0] < counts[1] < counts[2]
        assert counts[2] == SMALL_GRID * SMALL_GRID * (1 + (SHORT_STEPS - 1) // 7)

    def test_unknown_policy_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown spray policy"):
            run_resurgence_arm("mystery", 1000, steps=2)

    def test_runs_are_rerunnable_under_a_fixed_seed(self) -> None:
        first = _short_run(PRECISE, 1001)
        second = _short_run(PRECISE, 1001)
        assert first == second

    def test_different_seeds_move_the_numbers(self) -> None:
        yields = {_short_run(PRECISE, seed).final_yield_potential for seed in (1000, 1001, 1002)}
        assert len(yields) > 1


class TestRunInvariants:
    @pytest.mark.parametrize("policy", [NO_SPRAY, PRECISE, INDISCRIMINATE])
    def test_reported_quantities_stay_in_range(self, policy: str) -> None:
        run = _short_run(policy)
        assert run.steps == SHORT_STEPS
        assert run.final_primary_density >= 0.0
        assert run.final_secondary_density >= 0.0
        assert run.final_total_density == pytest.approx(
            run.final_primary_density + run.final_secondary_density
        )
        assert run.total_pest_days == pytest.approx(run.primary_pest_days + run.secondary_pest_days)
        assert run.peak_total_density >= run.total_pest_days
        assert 0.0 <= run.mean_crop_health <= 1.0
        assert 0.0 <= run.final_yield_potential <= 1.0
        assert run.final_beneficial_density >= 0.0

    def test_coupled_spraying_keeps_natural_enemies_depleted_despite_enemy_release(self) -> None:
        """Broad-spectrum mortality remains visible after the secondary pest erupts.

        The untreated secondary pest can support more beneficial recovery than
        the legacy prey-tracking loop, so a ratio to each mode's no-spray arm is
        not comparable. The coupled sprayed arm must still end enemy-depleted in
        absolute terms and relative to its own unsprayed control.
        """
        legacy_sprayed = _short_run(INDISCRIMINATE, ecology_enabled=False)
        coupled_unsprayed = _short_run(NO_SPRAY, ecology_enabled=True)
        coupled_sprayed = _short_run(INDISCRIMINATE, ecology_enabled=True)
        assert coupled_sprayed.final_beneficial_density < legacy_sprayed.final_beneficial_density
        assert (
            coupled_sprayed.final_beneficial_density
            < 0.25 * coupled_unsprayed.final_beneficial_density
        )

    def test_secondary_pest_exists_only_when_coupled(self) -> None:
        assert _short_run(INDISCRIMINATE).final_secondary_density > 0.0
        assert _short_run(
            INDISCRIMINATE, ecology_enabled=False
        ).final_secondary_density == pytest.approx(0.0)


class TestVerdict:
    def test_resurgence_needs_both_a_precise_and_a_no_spray_comparison(self) -> None:
        verdict = resurgence_verdict(
            [
                _summary(NO_SPRAY, mean_yield_potential=0.4, mean_total_density=100.0),
                _summary(INDISCRIMINATE, mean_yield_potential=0.2, mean_total_density=200.0),
                _summary(PRECISE, mean_yield_potential=0.7, mean_total_density=150.0),
            ]
        )
        assert verdict["resurgence"] is True
        assert verdict["indiscriminate_minus_precise_yield"] == pytest.approx(-0.5)
        assert verdict["indiscriminate_minus_no_spray_yield"] == pytest.approx(-0.2)

    def test_beating_no_spray_is_not_resurgence_even_if_precise_wins(self) -> None:
        verdict = resurgence_verdict(
            [
                _summary(NO_SPRAY, mean_yield_potential=0.1),
                _summary(INDISCRIMINATE, mean_yield_potential=0.5),
                _summary(PRECISE, mean_yield_potential=0.7),
            ]
        )
        assert verdict["resurgence"] is False

    def test_crop_collapse_without_a_density_rebound_is_not_resurgence(self) -> None:
        """A collapsed crop suppresses pests, so low yield alone is insufficient."""
        verdict = resurgence_verdict(
            [
                _summary(NO_SPRAY, mean_yield_potential=0.4, mean_total_density=6000.0),
                _summary(INDISCRIMINATE, mean_yield_potential=0.05, mean_total_density=100.0),
                _summary(PRECISE, mean_yield_potential=0.6, mean_total_density=3000.0),
            ]
        )
        assert verdict["indiscriminate_minus_precise_density"] < 0.0
        assert verdict["resurgence"] is False

    def test_missing_policies_are_an_error_not_a_silent_pass(self) -> None:
        with pytest.raises(ValueError, match="indiscriminate and precise"):
            resurgence_verdict([_summary(NO_SPRAY)])

    def test_summarizing_no_seeds_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="no seeds recorded"):
            summarize_policy(PRECISE, [])


class TestExperimentAndScript:
    def test_experiment_records_configuration_and_every_cell(self) -> None:
        results = run_resurgence_experiment(
            [1000, 1001],
            steps=20,
            policies=(NO_SPRAY, INDISCRIMINATE, PRECISE),
        )
        assert results["configuration"]["seeds"] == [1000, 1001]
        assert len(results["per_seed"]) == 6
        assert {summary["policy"] for summary in results["policies"]} == {
            NO_SPRAY,
            INDISCRIMINATE,
            PRECISE,
        }
        assert isinstance(results["verdict"]["resurgence"], bool)

    @pytest.mark.parametrize("raw", ["docs", "artifacts/scratch"])
    def test_output_dir_accepts_relative_names(self, raw: str) -> None:
        assert SCRIPT.safe_output_dir(raw) == REPO_ROOT / raw

    @pytest.mark.parametrize("raw", ["/tmp/x", "../x", "./x", "", "a b", "out.json"])
    def test_output_dir_rejects_absolute_and_traversing_names(self, raw: str) -> None:
        with pytest.raises(ValueError, match="relative directory"):
            SCRIPT.safe_output_dir(raw)

    def test_legacy_flag_selects_the_uncoupled_domain(self) -> None:
        assert SCRIPT._parse_args([]).legacy_ecology is False
        assert SCRIPT._parse_args(["--legacy-ecology"]).legacy_ecology is True

    def test_report_states_the_verdict_and_every_policy_column(self) -> None:
        results = run_resurgence_experiment([1000], steps=20)
        report = SCRIPT.markdown_report(results)
        assert "# Resurgence sanity experiment" in report
        assert "Resurgence:" in report
        for policy in (NO_SPRAY, INDISCRIMINATE, PRECISE):
            assert f"`{policy}`" in report

    def test_artifacts_round_trip_to_the_requested_directory(self, tmp_path: Path) -> None:
        results = run_resurgence_experiment([1000], steps=20)
        json_path, report_path = SCRIPT.write_artifacts(results, tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["configuration"]["steps"] == 20
        assert report_path.read_text(encoding="utf-8").startswith("# Resurgence sanity experiment")
