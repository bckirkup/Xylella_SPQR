#!/usr/bin/env python3
"""Measure the grain domain's exploitable margin with a designed reporter arm.

Earlier cross-domain work measured this domain at a negative exploitable margin
(best reachable precision minus its own static-prior null) using evolved agent
arms only. This script adds the missing arm: a hand-coded, evidence-only
reporter that reads the domain's published trap and drone streams, plus an
oracle arm as a diagnostic ceiling, over many seeds at a fixed step count with
the pest adversary frozen.

Outputs `docs/designed-reporter-measurement.json` and
`docs/designed-reporter-measurement.md`.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from grain_guard.analysis.arms import ArmSpec
from grain_guard.analysis.designed_reporter import (
    CLAUSE_2_CORRELATION_THRESHOLD,
    ESCALATION_THRESHOLD_RANGE,
    INVASION_DESIGNED_FRACTION,
    MIN_SCORED_REPORTS,
    POLICY_ARMS,
    exploitable_margin,
    measure_designed_arm,
    summarize_policy_arm,
)
from grain_guard.reporter_policy import (
    DEFAULT_THRESHOLD_DENSITY,
    DEFAULT_TRAP_CATCH_EFFICIENCY,
    GRAIN_REPORTER_POLICY_NAME,
)

DEFAULT_SEEDS = tuple(range(1000, 1021))
DEFAULT_STEPS = 400
DEFAULT_GROUNDED_FRACTION = 0.67
DEFAULT_CORRECTNESS_WEIGHT = 0.0
"""Response gate off: the population cap rations reproduction by reserves only."""
JSON_ARTIFACT_NAME = "designed_reporter_measurement.json"
REPORT_ARTIFACT_NAME = "designed_reporter_measurement.md"
DEFAULT_OUT_DIR = "docs"

SAFE_OUTPUT_DIR = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
"""Relative directory names accepted for output: no dots, no other separators."""


def safe_output_dir(raw_path: str) -> Path:
    """Resolve an output directory under the repository without traversal.

    Only names matching :data:`SAFE_OUTPUT_DIR` are accepted, so an absolute
    path, a parent reference, or any other traversal attempt is rejected before
    a path is built from it rather than checked afterwards.
    """
    if not SAFE_OUTPUT_DIR.fullmatch(raw_path):
        raise ValueError(
            "out_dir must be a relative directory of letters, digits, '_', '-' and '/'"
        )
    return Path(__file__).resolve().parents[1] / raw_path


def arm_spec(policy_arm: str, seed: int, args: argparse.Namespace) -> ArmSpec:
    """Arm specification for one seed of one policy arm."""
    return ArmSpec(
        name=f"designed_{policy_arm}",
        grounded_input_fraction=args.grounded_fraction,
        grounded_attractiveness_multiplier=args.grounded_multiplier,
        seed=seed,
        steps=args.steps,
        freeze_pest_evolution=True,
        reporting_levers=args.payoff_levers,
        reproduction_correctness_weight=args.correctness_weight,
    )


def _run_cell(cell: tuple[ArmSpec, str]) -> dict[str, Any]:
    spec, policy_arm = cell
    return measure_designed_arm(spec, policy_arm)


def run_measurement(args: argparse.Namespace) -> dict[str, Any]:
    """Run every policy arm over every seed and pool the results."""
    policy_arms = tuple(args.policy_arms)
    cells = [
        (arm_spec(policy_arm, seed, args), policy_arm)
        for policy_arm in policy_arms
        for seed in args.seeds
    ]
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            per_seed = list(pool.map(_run_cell, cells))
    else:
        per_seed = [_run_cell(cell) for cell in cells]
    summaries: list[dict[str, Any]] = []
    for policy_arm in policy_arms:
        arm_records = [record for record in per_seed if record["policy_arm"] == policy_arm]
        summaries.append(summarize_policy_arm(policy_arm, arm_records))
    return {
        "configuration": {
            "seeds": list(args.seeds),
            "steps": args.steps,
            "grounded_input_fraction": args.grounded_fraction,
            "grounded_attractiveness_multiplier": args.grounded_multiplier,
            "pest_evolution_frozen": True,
            "policy_arms": list(policy_arms),
            "payoff_levers": args.payoff_levers,
            "reproduction_correctness_weight": args.correctness_weight,
            "clause_2_correlation_threshold": CLAUSE_2_CORRELATION_THRESHOLD,
            "reporter_policy": GRAIN_REPORTER_POLICY_NAME,
            "reporter_threshold_density": DEFAULT_THRESHOLD_DENSITY,
            "reporter_trap_catch_efficiency": DEFAULT_TRAP_CATCH_EFFICIENCY,
            "invasion_designed_fraction": INVASION_DESIGNED_FRACTION,
            "escalation_threshold_range": list(ESCALATION_THRESHOLD_RANGE),
            "min_scored_reports": MIN_SCORED_REPORTS,
        },
        "margin": exploitable_margin(summaries),
        "arms": summaries,
        "per_seed": per_seed,
    }


def _fmt(value: object, spec: str = "{:.4f}") -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return spec.format(value)
    return str(value)


_PRECISION_KEYS = frozenset({"reporting_precision", "designed_precision", "ordinary_precision"})
"""Rows whose value is meaningless for an arm with too few reports to score."""

_ARM_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Headline precision", "reporting_precision", "{:.4f}"),
    ("Designed reports", "designed_reports", "{:.0f}"),
    ("Ordinary reports", "ordinary_reports", "{:.0f}"),
    ("Reports scored", "scoring_reports", "{:.0f}"),
    ("Scored", "scored", "{}"),
    ("Static-prior null", "mean_static_prior_null", "{:.4f}"),
    ("Uniform null", "mean_uniform_null", "{:.4f}"),
    ("Reports per adult lifetime", "mean_reports_per_adult_lifetime", "{:.2f}"),
    ("Evidence rate (designed adult steps)", "mean_any_evidence_rate", "{:.4f}"),
    ("Designed escalation rate", "mean_designed_escalation_rate", "{:.4f}"),
    ("Attention solvent share", "mean_attention_solvent_share", "{:.4f}"),
    ("Attention capacity per capita", "mean_attention_capacity_per_capita", "{:.3f}"),
    ("Grounded-yield share", "mean_grounded_yield_share", "{:.4f}"),
    ("Effective grounded-yield share", "mean_effective_grounded_yield_share", "{:.4f}"),
    ("Designed population share", "mean_designed_population_share", "{:.4f}"),
    ("Final population", "mean_final_population", "{:.1f}"),
    ("Extinct seeds", "n_extinct_seeds", "{:.0f}"),
    (
        "Detector parent-child repro corr",
        "mean_detector_parent_child_reproductive_correlation",
        "{:.4f}",
    ),
    ("Pest parent-child repro corr", "mean_pest_parent_child_reproductive_correlation", "{:.4f}"),
    ("Silent-adult share", "mean_silent_adult_share", "{:.4f}"),
    ("Population-cap binding step share", "mean_population_capped_step_share", "{:.4f}"),
    ("Reproduction-eligible agent-step share", "mean_reproduction_eligible_share", "{:.4f}"),
    ("Clause 1: correct-report rate slope per generation", "mean_clause_1_slope", "{:+.5f}"),
    ("Clause 1: seeds rising", "n_seeds_clause_1_rising", "{:.0f}"),
    ("Generations observed", "mean_generations_observed", "{:.1f}"),
    ("Clause 2: parent-child offspring corr", "mean_clause_2_correlation", "{:+.4f}"),
    ("Clause 2: seeds above threshold", "n_seeds_clause_2_cleared", "{:.0f}"),
)


def _arm_cell(arm: dict[str, Any], key: str, spec: str) -> str:
    """One table cell, kept from printing a precision an arm cannot support."""
    if key in _PRECISION_KEYS and not arm["scored"]:
        return "unscored"
    return _fmt(arm.get(key), spec)


def _verdict_lines(margin: dict[str, Any]) -> list[str]:
    """Plain-language answer to the exploitable-margin question."""
    positive = margin["exploitable_margin_positive"]
    if positive is None:
        headline = (
            "No evidence-only arm produced enough scored reports, so the margin is unmeasured."
        )
    elif positive:
        headline = (
            "The grain domain has a positive exploitable margin: a hand-designed,"
            " evidence-only reporter beats the domain's own static-prior null, so the domain"
            " is not unselectable by construction."
        )
    else:
        headline = (
            "The grain domain has no positive exploitable margin at this configuration: the"
            " best evidence-only reporter measured here does not beat the domain's own"
            " static-prior null."
        )
    ordinary_margin = margin["ordinary_margin_pp"]
    if ordinary_margin is None:
        evolved = "The evolved (ordinary) arm produced too few scored reports to place."
    elif ordinary_margin > 0.0:
        evolved = "The evolved (ordinary) arm sits above the static-prior null."
    else:
        evolved = "The evolved (ordinary) arm stays below the static-prior null."
    return ["## Answer", "", headline, "", evolved, ""]


def _method_lines(config: dict[str, Any]) -> list[str]:
    """How the adversary was frozen and what the designed reporter may read."""
    return [
        "## Method notes",
        "",
        "- The pest adversary is held fixed in every arm: the runs build the adapter with",
        "  `freeze_pest_evolution=True`, so the heritable resistance and behavioural-escape",
        "  update in `environment/pest.py` does not run and the detector-side numbers are not",
        "  confounded by the adversary adapting inside the same runs. Pest-side gradient",
        "  metrics are still reported from those runs as the reference shape of this domain's",
        "  one known-good evolutionary loop.",
        f"- The designed reporter (`{config['reporter_policy']}`) reads only published grain",
        "  streams — `pheromone_traps` catch counts and `drone_imagery` pest detections, with",
        "  their declared coordinates — and reports a location only when that public evidence",
        f"  implies at least `{config['reporter_threshold_density']}` pests per cell. It never",
        "  reads ground truth, active locations, or adapter internals.",
        "- The `oracle_upper_bound` arm is the only place ground truth reaches a reporting",
        "  decision. It is a diagnostic ceiling, not a shippable policy, and is excluded from",
        "  the best-reachable-precision selection.",
        "- No subsidies, grace periods, juvenile discounts, or population floors were added,",
        "  and no domain parameter was tuned for this measurement.",
        "- `docs/response_gate_measurement.md` reports the same instrument under the engine's",
        "  payoff levers and the correctness-keyed response gate, against both falsification",
        "  clauses.",
        "",
    ]


def markdown_report(results: dict[str, Any]) -> str:
    """Render the measurement as a Markdown table of arms against metrics."""
    config = results["configuration"]
    margin = results["margin"]
    arms = results["arms"]
    lines = [
        "# Designed-reporter measurement: grain domain exploitable margin",
        "",
        "Generated by `scripts/run_designed_reporter_experiment.py`.",
        "",
        f"- Seeds: `{len(config['seeds'])}` (`{min(config['seeds'])}`-`{max(config['seeds'])}`)",
        f"- Steps per run: `{config['steps']}`",
        f"- `grounded_input_fraction`: `{config['grounded_input_fraction']}`",
        f"- Pest evolution frozen: `{config['pest_evolution_frozen']}`",
        f"- Designed reporter: `{config['reporter_policy']}`",
        f"- Payoff levers 1-4 enabled: `{config['payoff_levers']}`",
        f"- `reproduction_correctness_weight`: `{config['reproduction_correctness_weight']}`",
        f"- Policy arms: `{', '.join(config['policy_arms'])}`",
        "",
        "## Exploitable margin",
        "",
        f"- Static-prior null: `{_fmt(margin['static_prior_null'])}`",
        f"- Best reachable precision: `{_fmt(margin['best_reachable_precision'])}`"
        f" (arm `{margin['best_arm']}`)",
        f"- **Exploitable margin: `{_fmt(margin['exploitable_margin_pp'], '{:+.2f}')}` pp**"
        f" (positive: `{_fmt(margin['exploitable_margin_positive'])}`)",
        f"- Ordinary (evolved) arm precision: `{_fmt(margin['ordinary_precision'])}`,"
        f" margin `{_fmt(margin['ordinary_margin_pp'], '{:+.2f}')}` pp",
        f"- Oracle diagnostic ceiling: `{_fmt(margin['oracle_precision'])}`,"
        f" margin `{_fmt(margin['oracle_margin_pp'], '{:+.2f}')}` pp",
        f"- Unscored arms (fewer than `{config['min_scored_reports']}` reports):"
        f" `{margin['unscored_arms']}`",
        "",
    ]
    lines.extend(_verdict_lines(margin))
    lines.extend(["## Arms", ""])
    header = "| Metric | " + " | ".join(f"`{arm['policy_arm']}`" for arm in arms) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(arms) + 1))
    for label, key, spec in _ARM_ROWS:
        cells = " | ".join(f"`{_arm_cell(arm, key, spec)}`" for arm in arms)
        lines.append(f"| {label} | {cells} |")
    lines.append("")
    lines.extend(_method_lines(config))
    return "\n".join(lines)


def write_artifacts(results: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    """Write the JSON and Markdown artifacts into ``out_dir``."""
    json_path = out_dir / JSON_ARTIFACT_NAME
    report_path = out_dir / REPORT_ARTIFACT_NAME
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(markdown_report(results), encoding="utf-8")
    return json_path, report_path


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="*", default=list(DEFAULT_SEEDS))
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--grounded-fraction", type=float, default=DEFAULT_GROUNDED_FRACTION)
    parser.add_argument("--grounded-multiplier", type=float, default=1.0)
    parser.add_argument(
        "--payoff-levers",
        action="store_true",
        help=(
            "Enable the engine's measured reporting-payoff levers 1-4: verified-correctness"
            " attention income, merit-ordered reproduction at the population cap, false-alarm"
            " pricing at reachable precision, and escalation thresholds in score units. Off by"
            " default, so the committed designed-reporter numbers are unchanged."
        ),
    )
    parser.add_argument(
        "--correctness-weight",
        type=float,
        default=DEFAULT_CORRECTNESS_WEIGHT,
        help=(
            "Weight of rank in verified correctness in the reproductive merit the"
            " population cap rations by (engine lever 5). 0 keeps the reserves-only"
            " ordering the committed numbers were measured under."
        ),
    )
    parser.add_argument(
        "--policy-arms",
        nargs="+",
        choices=POLICY_ARMS,
        default=list(POLICY_ARMS),
        help="Policy arms to run; restrict to spend a seed budget on one arm.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Processes used to run (arm, seed) cells; 1 runs them in-process.",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help="Output directory relative to the repository root, e.g. docs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the measurement and write both artifacts."""
    args = _parse_args(argv)
    out_dir = safe_output_dir(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = run_measurement(args)
    json_path, report_path = write_artifacts(results, out_dir)
    margin = results["margin"]
    print(f"static-prior null: {_fmt(margin['static_prior_null'])}")
    print(
        f"best reachable precision: {_fmt(margin['best_reachable_precision'])}"
        f" ({margin['best_arm']})"
    )
    print(f"exploitable margin: {_fmt(margin['exploitable_margin_pp'], '{:+.2f}')} pp")
    print(f"wrote {json_path} and {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
