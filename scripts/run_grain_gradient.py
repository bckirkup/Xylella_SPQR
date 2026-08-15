"""Measure the detector-side selection gradient against the pest reference.

Detector arms hold the pest adversary frozen so a coevolving target cannot hide
or fake detector improvement. Pest reference arms use the same configuration and
seeds with pest evolution left running, and are the source of the reference
gradient numbers.

Each run writes a unified ``tattletots.output_schema.SimulationOutput`` JSON
file; an aggregate summary with per-arm means is written alongside them.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from grain_guard.analysis import ArmSpec, run_arm

DETECTOR_FRACTIONS: tuple[float, ...] = (0.0, 0.34, 0.67)
"""Grounded input fractions measured on the detector side."""

PEST_REFERENCE_FRACTIONS: tuple[float, ...] = (0.0, 0.67)
"""Fractions at which the pest reference arm (pests evolving) is run."""


def build_specs(seeds: Sequence[int], steps: int) -> list[ArmSpec]:
    """Build the frozen-pest detector arms plus the evolving pest reference arms."""
    specs: list[ArmSpec] = []
    for fraction in DETECTOR_FRACTIONS:
        for seed in seeds:
            specs.append(
                ArmSpec(
                    name=f"detector_gif{fraction:g}_s{seed}",
                    grounded_input_fraction=fraction,
                    seed=seed,
                    steps=steps,
                    freeze_pest_evolution=True,
                )
            )
    for fraction in PEST_REFERENCE_FRACTIONS:
        for seed in seeds:
            specs.append(
                ArmSpec(
                    name=f"pestref_gif{fraction:g}_s{seed}",
                    grounded_input_fraction=fraction,
                    seed=seed,
                    steps=steps,
                    freeze_pest_evolution=False,
                )
            )
    return specs


SAFE_OUTPUT_DIR = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*")
"""Relative directory names accepted for output: no dots, no other separators."""


def _safe_output_dir(raw_path: str) -> Path:
    """Resolve an output directory under the repository without traversal.

    Only names matching :data:`SAFE_OUTPUT_DIR` are accepted, so an absolute
    path, a parent reference, or any other traversal attempt is rejected before
    a path is built from it rather than checked afterwards.
    """
    if not SAFE_OUTPUT_DIR.fullmatch(raw_path):
        raise ValueError(
            "output_path must be a relative directory of letters, digits, '_', '-' and '/'"
        )
    return Path(__file__).resolve().parents[1] / raw_path


def run_and_write(spec: ArmSpec, out_dir: Path) -> dict[str, Any]:
    """Run one arm, write its SimulationOutput JSON, and return its metrics."""
    output = run_arm(spec)
    path = out_dir / f"{spec.name}.json"
    output.write_json(path)
    metrics = dict(output.domain_metrics)
    metrics["output_path"] = str(path)
    metrics["ecology"] = output.ecology_metrics.model_dump()
    return metrics


def _mean(values: Iterable[float | None]) -> float | None:
    present = [float(v) for v in values if v is not None]
    if not present:
        return None
    return statistics.fmean(present)


def _nested(records: list[dict[str, Any]], group: str, key: str) -> list[float | None]:
    return [record.get(group, {}).get(key) for record in records]


def _arm_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean of every reported metric across seeds within one arm."""
    detector_keys = (
        "selection_differential",
        "heritability",
        "parent_offspring_trait_correlation",
        "parent_child_reproductive_correlation",
        "opportunity_for_selection",
        "fitness_variance",
        "mean_fitness",
        "trait_variance",
    )
    summary: dict[str, Any] = {"n_runs": len(records)}
    for key in detector_keys:
        summary[f"detector_{key}"] = _mean(_nested(records, "detector_gradient", key))
        summary[f"pest_{key}"] = _mean(_nested(records, "pest_gradient", key))
    summary["detector_function_selection_differential"] = _mean(
        record.get("detector_function_selection_differential") for record in records
    )
    for key in (
        "first_half_correct_report_rate",
        "second_half_correct_report_rate",
        "correct_report_rate_delta",
    ):
        summary[key] = _mean(_nested(records, "correct_report_halves", key))
    for key in ("mean_attention_solvent_share", "mean_attention_capacity_per_capita"):
        summary[key] = _mean(_nested(records, "attention_solvency", key))
    for key in ("static_prior_null", "uniform_null", "inferability_precision"):
        summary[key] = _mean(_nested(records, "instrument", key))
    summary["instrument_valid_runs"] = sum(
        1 for record in records if record.get("instrument", {}).get("instrument_valid")
    )
    for key in ("report_precision", "grounded_yield_share", "effective_grounded_yield_share"):
        summary[key] = _mean(record.get(key) for record in records)
    summary["degenerate_runs"] = sum(
        1 for record in records if record.get("ecology", {}).get("initiation_is_degenerate")
    )
    summary["reproducing_fraction"] = _mean(
        _nested(records, "detector_cohort", "reproducing_fraction")
    )
    return summary


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Group run records by arm family and summarize each."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        spec = record["arm_spec"]
        family = "pestref" if not spec["freeze_pest_evolution"] else "detector"
        key = f"{family}_gif{spec['grounded_input_fraction']:g}"
        grouped.setdefault(key, []).append(record)
    return {key: _arm_summary(runs) for key, runs in sorted(grouped.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_path",
        help="output directory relative to the repository root, e.g. grain_gradient_output",
    )
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(42, 52)))
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    out_dir = _safe_output_dir(args.output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = build_specs(args.seeds, args.steps)

    records: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_and_write, spec, out_dir): spec for spec in specs}
        for future, spec in futures.items():
            records.append(future.result())
            print(f"completed {spec.name}", flush=True)

    aggregate = {
        "steps": args.steps,
        "seeds": args.seeds,
        "arms": summarize(records),
        "runs": {record["arm"]: record for record in records},
    }
    (out_dir / "gradient_summary.json").write_text(json.dumps(aggregate, indent=2, default=str))
    print(json.dumps(aggregate["arms"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
