"""Measure GrainGuard precision across caps using a sibling TattleTots checkout.

This harness borrows ``run_batch`` and ``baseline_parallel`` from the sibling
TattleTots repository. By default it expects that checkout at ``../TattleTots``
relative to this repository's parent workspace. Override the workspace with
``GRAIN_WORKSPACE_ROOT`` or the TattleTots checkout with
``GRAIN_TATTLETS_ROOT``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = Path(os.environ.get("GRAIN_WORKSPACE_ROOT", str(_REPO_ROOT.parent))).resolve()
_TATTLETS_ROOT = Path(
    os.environ.get("GRAIN_TATTLETS_ROOT", str(_WORKSPACE_ROOT / "TattleTots"))
).resolve()
experiments = _TATTLETS_ROOT / "Large Experiments"
sys.path.insert(0, str(experiments))
import run_batch  # noqa: E402

run_batch._WORKSPACE_ROOT = _WORKSPACE_ROOT
_repo_name = _REPO_ROOT.name
run_batch.REPOS["grain_guard"]["default_config"] = (
    f"{_repo_name}/configs/tattletots_integration.json"
)
run_batch.REPOS["grain_guard"]["script"] = f"{_repo_name}/scripts/run_grain_direct.py"
run_single_simulation = run_batch.run_single_simulation
from baseline_parallel import run_process_pool  # noqa: E402


def _safe_output_dir(raw_path: Path) -> Path:
    """Resolve an output directory without allowing path traversal."""
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ValueError("output_path must be a relative path without '..'")
    output_path = (_WORKSPACE_ROOT / raw_path).resolve()
    if not output_path.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError("output_path must remain under the workspace root")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()

    out_root = _safe_output_dir(args.output_path)
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
