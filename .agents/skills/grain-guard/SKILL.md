---
name: grain-guard
description: Guide for developing and testing the GrainGuard domain simulation for TattleTots.
---

# GrainGuard Development Skill

## Setup

```bash
cd /home/ubuntu/repos/Xylella_SPQR
pip install -e ".[dev]"
pre-commit install
```

## Run Simulation

```bash
grain-guard --steps 200 --verbose
grain-guard --landscape orchard --steps 100 --json
grain-guard --landscape intercrop --steps 100 --verbose
```

## Validation

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest
pytest -m smoke
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

## Integrated Mode (TattleTots Agent Ecology)

```bash
python scripts/run_with_tattletots.py \
    --config configs/tattletots_integration.json \
    --output results.json --verbose
```

Output conforms to `tattletots.output_schema.SimulationOutput` (unified JSON).
See `docs/COORDINATION.md` for coordination with sibling repos.

## GPU Acceleration

```bash
pip install -e ".[gpu]"  # installs cupy-cuda12x
```

Set `"use_gpu": true` in the `"simulation"` section of the integration config.
Falls back silently to NumPy if CuPy or CUDA is unavailable.

## Parameter Scans

Generate config variants and run in parallel for large sweeps:

```bash
python scripts/run_with_tattletots.py --config <variant>.json --output results/<name>.json
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
