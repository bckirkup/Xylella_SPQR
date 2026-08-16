---
name: grain-guard
description: Guide for developing and testing the GrainGuard domain simulation for TattleTots.
---

# GrainGuard Development Skill

## Setup

```bash
uv sync --locked --no-build --no-binary-package grain-guard --no-binary-package domain-runner --no-binary-package tattletots --extra dev
uv run --no-sync --no-build pre-commit install
```

## Run Simulation

```bash
uv run --no-sync --no-build grain-guard sim --layer domain_only --steps 200 --verbose
uv run --no-sync --no-build grain-guard sim --layer tattletots --config configs/tattletots_integration.json
uv run --no-sync --no-build grain-guard batch --config configs/batch_example.json

# Legacy
uv run --no-sync --no-build grain-guard --steps 200 --verbose
uv run --no-sync --no-build grain-guard --landscape orchard --steps 100 --json
```

## Validation

```bash
uv run --no-sync --no-build ruff check src/ tests/
uv run --no-sync --no-build ruff format --check src/ tests/
uv run --no-sync --no-build mypy src/
uv run --no-sync --no-build pytest
uv run --no-sync --no-build pytest -m smoke
```

## Module Dependency Order

```
environment → sensors → equipment → users → architectures → adapter → metrics → scenarios → cli
```

## Key Patterns

- All data models use Pydantic v2 with `from __future__ import annotations`
- Sensors return `np.ndarray` or `None` (when off-cadence like satellite)
- Adapter streams are capped at 30 dimensions each
- Body plans are fixed; genomes mutate with `mutate(rng, rate)` → Self
- Behavioral fractions (scout/treat/report) are normalized to sum to 1.0
- Pest evolution tracks resistance allele frequency [0, 1] and behavioral escape traits

## TattleTots Integration

The adapter (`adapter/grain_adapter.py`) implements `DomainAdapter`:
- `get_streams()` → pest, satellite, pheromone, soil sensor streams
- `get_users()` → 2 ag-domain user profiles
- `step(time_step)` → advances pest/crop/weather sim, updates streams
- `get_ground_truth(time_step)` → True if pest density exceeds threshold
- `get_active_locations(time_step)` → returns `(row, col)` of cells above pest threshold
- `infer_report_location(stream_data, stream_labels)` → finds peak in pest stream → maps to field `(row, col)`
- `score_relevance(signal, user)` → band-aligned role relevance via `tattletots.engine.relevance`
- `compute_costs(...)` → scouting + treatment + damage costs
- `get_responder_user_id()` → user authorized for COP dispatch
- `dispatch_and_judge_responses(targets, time_step)` → treatment outcomes

**Note:** The integration loop uses `world.set_event_state(adapter.get_active_locations(step))` (not `set_ground_truth`). Agents must not read `User.trust`.

### Running Integrated Mode

```bash
uv run --no-sync --no-build grain-guard sim --layer tattletots --config configs/tattletots_integration.json --output results.json --verbose
```

Output conforms to `tattletots.output_schema.SimulationOutput` (unified JSON).
See `docs/COORDINATION.md` for coordination with sibling repos.

### Baselines

Standalone baseline comparison files live in `baselines/`:
- `run_grain_guard_baselines.py` — Parameter scan runner for A0-A3 architectures
- `grain_guard_baselines_config.json` — Scan configuration
- `grain_guard_baselines_results.zip` — Pre-computed results

## GPU Acceleration

```bash
uv sync --locked --no-build --no-binary-package grain-guard --no-binary-package domain-runner --no-binary-package tattletots --extra dev --extra gpu
```

Set `"use_gpu": true` in the `"simulation"` section of the integration config.
Falls back silently to NumPy if CuPy or CUDA is unavailable.

## Parameter Scans

Generate config variants and run in parallel for large sweeps:

```bash
uv run --no-sync --no-build python scripts/run_with_tattletots.py --config <variant>.json --output results/<name>.json
```

Key domain parameters to sweep: `landscape` (monoculture/orchard/intercrop),
`pest_initial_density`, `resistance_frequency`, `steps`, `seed`.

Load results:
```python
from tattletots.output_schema import SimulationOutput
result = SimulationOutput.model_validate_json(path.read_text())
```

## Testing Accounts

No external services required. All simulation is self-contained.

## Common Tasks

### Add a new pest species
1. Add to `PestSpecies` enum in `environment/pest.py`
2. Add generation time to `_GENERATION_TIME` dict
3. Add base damage rate in `damage_rate` property
4. Add tests in `tests/test_environment.py`

### Add a new sensor
1. Create model in `sensors/` with `observe()` → `np.ndarray` and `output_dim` property
2. Wire into `adapter/grain_adapter.py` (add stream, update `_setup_streams`)
3. Update `sensors/__init__.py`
4. Add tests in `tests/test_sensors.py`

### Add a new architecture
1. Subclass `Architecture` from `architectures/base.py`
2. Implement `step(field, weather, time_step)` → dict and `reset()`
3. Update `architectures/__init__.py`
4. Add tests in `tests/test_architectures.py`
