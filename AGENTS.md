# AGENTS.md — AI Agent Guidelines for Xylella_SPQR

## Repository Purpose
GrainGuard domain simulation — a testbed for TattleTots. Grid-based precision
agriculture model with physical drone/tractor Tots, co-evolutionary pest/weed
dynamics, competing architectures (A0-A3), and phased deployment scenarios.

## Setup
```bash
pip install -e ".[dev]"
pre-commit install
```

## Validation Commands
Run these before committing:
```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest
```

## Architecture Rules
- **Domain-specific code only** — never modify TattleTots engine or its models
- **Implement `DomainAdapter` ABC** — the adapter bridges ag sim → TattleTots
- **All architectures get the same sensors** — no strawmen
- **Pests/weeds co-evolve** — resistance and behavioral escape under management pressure
- **Equipment are physical Tots** — they have body plans (hardware) and genomes (behavior)
- **Body plans don't mutate** — hardware is fixed; behavioral traits evolve
- **Never modify tests to make them pass** — fix the implementation

## Key Files
| File | Purpose |
|------|---------|
| `src/grain_guard/adapter/grain_adapter.py` | TattleTots DomainAdapter implementation |
| `src/grain_guard/environment/field.py` | Grid-based crop field simulation |
| `src/grain_guard/environment/pest.py` | Pest dynamics + resistance evolution |
| `src/grain_guard/environment/weed.py` | Weed dynamics + herbicide resistance |
| `src/grain_guard/equipment/equipment_genome.py` | Heritable equipment behavioral traits |
| `src/grain_guard/architectures/a3_centralized_platform.py` | Strongest conventional competitor |
| `src/grain_guard/scenarios/phased_deployment.py` | 3-season hardware rollout |
| `src/grain_guard/metrics/ag_metrics.py` | Spec §9 falsification metrics |

## Module Dependency Order
```
environment → sensors → equipment → users → architectures → adapter → metrics → scenarios → cli
```

## Spec Documents
- `grain_tots_spec_v2.md` — Domain specification with all requirements
- `domain_master_plan_v2.md` — Cross-domain architecture comparison plan

## PR Requirements
- All ruff checks pass
- mypy strict passes on src/
- All tests pass (including smoke tests)
- New features include tests
- Update README if adding new scenarios or architectures
