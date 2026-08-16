# Baseline Comparisons (Without TattleTots)

Parameter scans using **only** conventional baseline architectures (A0–A3), no TattleTots agent ecology.

## Run from workspace root

```bash
cd D:\TotsFiles
uv run --no-sync --no-build python Xylella_SPQR/baselines/run_grain_guard_baselines.py --smoke-test
uv run --no-sync --no-build python Xylella_SPQR/baselines/run_grain_guard_baselines.py --workers 8
```

Parallel mode uses **ProcessPoolExecutor** (separate Python worker processes).

## Files

| File | Purpose |
|------|---------|
| `run_grain_guard_baselines.py` | Parameter scan runner |
| `grain_guard_baselines_config.json` | Factor levels, seeds, steps |
| `grain_guard_baselines_results.zip` | Pre-computed results (optional) |

## Shared utilities

Multiprocessing helpers live in `TattleTots/Large Experiments/baseline_parallel.py`.

## Prerequisites

```bash
uv sync --locked --no-build --no-binary-package grain-guard --no-binary-package domain-runner --no-binary-package tattletots --extra dev
```
