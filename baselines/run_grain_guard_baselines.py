#!/usr/bin/env python3
"""Parameter Scan Runner for Grain Guard Baselines (Without TattleTots).

Run from the workspace root (parent of all repos):

    python Xylella_SPQR/baselines/run_grain_guard_baselines.py --smoke-test
    python Xylella_SPQR/baselines/run_grain_guard_baselines.py --workers 8
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from grain_guard.comparison import ComparisonConfig, run_comparison

_SCRIPT_DIR = Path(__file__).resolve().parent
for _parent in [_SCRIPT_DIR, *_SCRIPT_DIR.parents]:
    _large_experiments = _parent / "TattleTots" / "Large Experiments"
    if (_large_experiments / "baseline_parallel.py").is_file():
        sys.path.insert(0, str(_large_experiments))
        break
else:
    sys.exit(
        "[-] Error: Could not find TattleTots/Large Experiments/baseline_parallel.py.\n"
        "    Ensure all repos are cloned as siblings under a common workspace root."
    )

from baseline_parallel import resolve_worker_count, run_process_pool


def run_single_simulation(
    steps: int,
    seed: int,
    landscape: str,
    grid_rows: int,
    grid_cols: int,
    pest_intro_probability: float,
    pest_density_boost: float,
    weed_density_base: float,
    resistance_initial_frequency: float,
) -> dict[str, Any]:
    """Run a single grain guard baseline comparison (A0-A3)."""
    start_time = time.time()

    config = ComparisonConfig(
        steps=steps,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        seed=seed,
        landscape=landscape,
        pest_intro_probability=pest_intro_probability,
        pest_density_boost=pest_density_boost,
        weed_density_base=weed_density_base,
        resistance_initial_frequency=resistance_initial_frequency,
    )
    baselines = run_comparison(config)

    elapsed_time = time.time() - start_time
    baseline_results = {b.name: asdict(b) for b in baselines}

    return {
        "status": "success",
        "elapsed_seconds": elapsed_time,
        "config": {
            "steps": steps,
            "seed": seed,
            "landscape": landscape,
            "grid_rows": grid_rows,
            "grid_cols": grid_cols,
            "pest_intro_probability": pest_intro_probability,
            "pest_density_boost": pest_density_boost,
            "weed_density_base": weed_density_base,
            "resistance_initial_frequency": resistance_initial_frequency,
        },
        "baselines": baseline_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parameter Scan Runner for Grain Guard Baselines")
    parser.add_argument(
        "--config",
        type=Path,
        default=_SCRIPT_DIR / "grain_guard_baselines_config.json",
        help="Path to parameter scan config JSON file",
    )
    parser.add_argument("--smoke-test", action="store_true", help="Run a fast smoke test")
    parser.add_argument("--parallel", action="store_true", default=True)
    parser.add_argument("--no-parallel", action="store_false", dest="parallel")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel worker processes (default: min(CPU count, job count))",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"[-] Error: Config file not found at {args.config}")
        return 1

    with open(args.config) as f:
        config_data = json.load(f)

    output_dir_name = (
        "grain_guard_baselines_smoke_results"
        if args.smoke_test
        else config_data.get("output_directory", "grain_guard_baselines_results")
    )
    output_dir = Path(output_dir_name).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    steps = 5 if args.smoke_test else config_data.get("steps", 800)
    seeds = [42] if args.smoke_test else config_data.get("seeds", [42, 43, 44])
    factors = config_data.get("factors", {})
    grid_rows = config_data.get("grid_rows", 20)
    grid_cols = config_data.get("grid_cols", 20)
    pest_map = config_data.get(
        "pest_pressure_levels",
        {"medium": {"intro_probability": 0.02, "density_boost": 1.0}},
    )
    weed_map = config_data.get(
        "weed_pressure_levels",
        {"medium": {"density_base": 2.0}},
    )

    if args.smoke_test:
        factor_grid = {
            "landscape": ["monoculture"],
            "pest_pressure": ["medium"],
            "weed_pressure": ["medium"],
            "resistance_initial_frequency": [0.01],
        }
    else:
        factor_grid = {
            "landscape": factors.get("landscape", ["monoculture"]),
            "pest_pressure": factors.get("pest_pressure", ["medium"]),
            "weed_pressure": factors.get("weed_pressure", ["medium"]),
            "resistance_initial_frequency": factors.get("resistance_initial_frequency", [0.01]),
        }

    factor_names = list(factor_grid.keys())
    factor_values = [factor_grid[name] for name in factor_names]

    runs_to_execute: list[dict[str, Any]] = []
    for combo in itertools.product(*factor_values):
        combo_dict = dict(zip(factor_names, combo, strict=True))
        landscape = combo_dict["landscape"]
        pest_level = combo_dict["pest_pressure"]
        weed_level = combo_dict["weed_pressure"]
        resistance = float(combo_dict["resistance_initial_frequency"])

        pest_params = pest_map[pest_level]
        weed_params = weed_map[weed_level]
        pest_intro = float(pest_params["intro_probability"])
        pest_boost = float(pest_params["density_boost"])
        weed_base = float(weed_params["density_base"])

        res_tag = f"{resistance:.2f}".replace(".", "p")
        for seed in seeds:
            run_name = (
                f"gg_baselines_{landscape}_pest{pest_level}_weed{weed_level}"
                f"_res{res_tag}_s{seed}"
            )
            runs_to_execute.append(
                {
                    "name": run_name,
                    "steps": steps,
                    "seed": seed,
                    "landscape": landscape,
                    "grid_rows": grid_rows,
                    "grid_cols": grid_cols,
                    "pest_intro_probability": pest_intro,
                    "pest_density_boost": pest_boost,
                    "weed_density_base": weed_base,
                    "resistance_initial_frequency": resistance,
                    "metadata": {
                        "landscape": landscape,
                        "pest_pressure": pest_level,
                        "weed_pressure": weed_level,
                        "resistance_initial_frequency": resistance,
                    },
                }
            )

    n_jobs = len(runs_to_execute)
    worker_count = resolve_worker_count(args.workers, n_jobs)

    print(f"[*] Results will be saved to: {output_dir}")
    print(f"[*] Generated {n_jobs} total run configurations.")
    if args.parallel:
        print(
            f"[*] Execution mode: PARALLEL (ProcessPoolExecutor, "
            f"{worker_count} worker process{'es' if worker_count != 1 else ''}, "
            f"PID {os.getpid()} parent)"
        )
    else:
        print(f"[*] Execution mode: SEQUENTIAL (single process, PID {os.getpid()})")
    print("=" * 60)

    results_key: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "is_smoke_test": args.smoke_test,
        "output_directory": str(output_dir),
        "runs": {},
    }

    start_time = time.time()
    all_results: dict[str, Any] = {}
    logs: list[str] = []

    def _store_success(run: dict[str, Any], res: dict[str, Any]) -> None:
        name = run["name"]
        results_key["runs"][name] = {
            "status": res["status"],
            "elapsed_seconds": res["elapsed_seconds"],
            "metadata": run["metadata"],
            "baselines_summary": {
                b_name: {
                    "final_yield": b_data["final_yield"],
                    "spray_volume_L": b_data["spray_volume_L"],
                    "false_sprays": b_data["false_sprays"],
                    "total_cost": b_data["total_cost"],
                }
                for b_name, b_data in res["baselines"].items()
            },
        }
        all_results[name] = res.copy()
        logs.append(f"[+] Completed: {name} in {res['elapsed_seconds']:.2f}s")

    def _store_failure(run: dict[str, Any], exc: Exception) -> None:
        results_key["runs"][run["name"]] = {"status": "failed", "error": str(exc)}

    submit_kwargs = [
        (
            run["steps"],
            run["seed"],
            run["landscape"],
            run["grid_rows"],
            run["grid_cols"],
            run["pest_intro_probability"],
            run["pest_density_boost"],
            run["weed_density_base"],
            run["resistance_initial_frequency"],
        )
        for run in runs_to_execute
    ]

    if args.parallel:
        run_process_pool(
            run_single_simulation,
            submit_kwargs,
            runs_to_execute,
            max_workers=worker_count,
            on_success=_store_success,
            on_failure=_store_failure,
        )
    else:
        for run, kwargs in zip(runs_to_execute, submit_kwargs, strict=True):
            name = run["name"]
            try:
                _store_success(run, run_single_simulation(*kwargs))
                print(f"[+] Completed: {name}")
            except Exception as e:
                _store_failure(run, e)
                print(f"[-] Run '{name}' failed: {e}")

    total_elapsed = time.time() - start_time
    print("=" * 60)
    print(f"[+] All runs finished in {total_elapsed:.1f}s.")

    key_file_path = output_dir / "key.json"
    with open(key_file_path, "w") as f:
        json.dump(results_key, f, indent=2)
    print(f"[+] Parameter scan summary key written to: {key_file_path}")

    results_file_path = output_dir / "results.json"
    with open(results_file_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[+] Consolidated results written to: {results_file_path}")

    log_file_path = output_dir / "all_runs.log"
    with open(log_file_path, "w") as f:
        f.write("=== Grain Guard Baselines Parameter Scan Log ===\n")
        f.write(f"Timestamp: {datetime.datetime.now(datetime.UTC).isoformat()}\n")
        f.write(f"Total Runs: {len(runs_to_execute)}\n")
        f.write(f"Total Elapsed Time: {total_elapsed:.1f}s\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(logs))
    print(f"[+] Consolidated logs written to: {log_file_path}")

    print("\n=== Grain Guard Baselines Parameter Scan Summary ===")
    print(
        f"{'Run Name':<50} | {'Status':<10} | {'Time (s)':<8} | "
        f"{'A3 Yield':<10} | {'A3 Cost':<10}"
    )
    print("-" * 100)
    for name, run_res in results_key["runs"].items():
        if run_res.get("status") == "success":
            status = "success"
            elapsed = f"{run_res.get('elapsed_seconds', 0.0):.1f}"
            a3 = run_res["baselines_summary"].get("A3 Centralized Platform", {})
            yield_val = f"{a3.get('final_yield', 0.0):.3f}"
            cost = f"{a3.get('total_cost', 0.0):,.1f}"
        else:
            status = "failed"
            elapsed = "N/A"
            yield_val = "N/A"
            cost = "N/A"
        print(f"{name:<50} | {status:<10} | {elapsed:<8} | {yield_val:<10} | {cost:<10}")
    print("=" * 100)

    any_failed = any(r.get("status") == "failed" for r in results_key["runs"].values())
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
