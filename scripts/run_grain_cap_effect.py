"""Measure GrainGuard agent precision across stream-dimension caps."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

experiments = Path("/home/ubuntu/repos/TattleTots/Large Experiments")
sys.path.insert(0, str(experiments))
import run_batch  # noqa: E402

run_batch._WORKSPACE_ROOT = Path("/home/ubuntu/repos")
run_batch.REPOS["grain_guard"]["default_config"] = (
    "Xylella-SPQR/configs/tattletots_integration.json"
)
run_batch.REPOS["grain_guard"]["script"] = "../conformance-audit/run_grain_direct.py"
run_single_simulation = run_batch.run_single_simulation
from baseline_parallel import run_process_pool  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()

    out_root = args.output_path
    out_root.mkdir(parents=True, exist_ok=True)
    scenarios = [
        ("monoculture_baseline", "monoculture"),
        ("orchard_complexity", "orchard"),
    ]
    runs = []
    for cap in (30, 75):
        for label, landscape in scenarios:
            for seed in range(42, 47):
                runs.append(
                    {
                        "name": f"cap{cap}_{label}_s{seed}",
                        "domain": "grain_guard",
                        "config_overrides": {
                            "simulation": {
                                "initial_population": 50,
                                "max_population": 100,
                                "max_stream_dim": cap,
                                "initial_info_energy": 1.5,
                                "initial_attn_energy": 1.5,
                                "false_alarm_penalty": 0.8,
                                "trust_delta_neg": 0.3,
                                "trust_delta_pos": 0.05,
                                "trust_delta_miss": 0.15,
                                "mutation_rate": 0.1,
                                "recombination_probability": 0.3,
                                "max_steps": 800,
                                "seed": seed,
                            },
                            "domain": {
                                "steps": 800,
                                "seed": seed,
                                "landscape": landscape,
                                "grid_rows": 20,
                                "grid_cols": 20,
                                "pest_intro_probability": 0.01,
                                "resistance_initial_frequency": 0.01,
                                "engine_max_dim": cap,
                            },
                        },
                    }
                )

    results = {}

    def ok(run, result):
        results[run["name"]] = result

    def bad(run, exc):
        results[run["name"]] = {"status": "failed", "error": str(exc)}

    args = [(run["name"], run["domain"], run["config_overrides"], out_root, False) for run in runs]
    run_process_pool(
        run_single_simulation,
        args,
        runs,
        max_workers=5,
        on_success=ok,
        on_failure=bad,
    )
    (out_root / "key.json").write_text(json.dumps({"runs": results}, indent=2))
    print(json.dumps({"runs": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
