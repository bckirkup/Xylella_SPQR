# Xylella_SPQR (GrainGuard)

**Precision pest and weed management domain simulation for [TattleTots](https://github.com/bckirkup/TattleTots).**

GrainGuard tests whether a self-organizing drone/sensor ecology (BMA) can manage crop pests and weeds more cost-effectively than centralized precision agriculture platforms, by adapting to local heterogeneity, seasonal drift, and co-evolutionary pest response faster than centralized systems.

## Quick Start

```bash
pip install -e domain-runner[dev]
pip install -e ".[dev]"
pre-commit install

grain-guard sim --layer domain_only --steps 200 --verbose
grain-guard batch --config configs/batch_example.json
```

## Architecture

```
src/grain_guard/
├── adapter/          # TattleTots DomainAdapter implementation
├── environment/      # Field, crop, pest (resistance), weed, weather
├── sensors/          # Satellite, drone imagery, traps, weather, soil, yield
├── equipment/        # Physical Tot body plans + behavioral genomes
├── users/            # Agronomist + Farm Manager profiles
├── architectures/    # Competing systems A0–A3
├── metrics/          # Spec §9 falsification metrics
├── scenarios/        # Phased deployment (3 seasons)
└── cli.py            # Command-line entry point
```

## Key Features

- **Co-evolutionary pest dynamics**: 1-locus resistance allele + behavioral escape (night-feeding, underside preference, edge refuge)
- **Three landscape variants**: Monoculture → Orchard → Intercrop (escalating complexity)
- **Five physical Tot body plans**: Scout drone, spray drone, AI tractor, trap robot, diagnostic microdrone
- **Six sensor types**: Satellite NDVI, drone imagery, pheromone traps, weather stations, soil probes, yield monitor
- **Four competing architectures**: Human IPM, AI tractor, prescription drones, centralized platform
- **Economic threshold model**: EIL = C / (V × D × I × K) — emerges from selection pressure

## Competing Architectures

| Code | Architecture | Description |
|------|-------------|-------------|
| A0 | Human IPM | Walk-the-field scouting + calendar/threshold spraying |
| A1 | AI Tractor | See & Spray-class spot treatment |
| A2 | Prescription Drone | Centralized map → autonomous flight execution |
| A3 | Centralized Platform | Full satellite/drone/IoT fusion (strongest competitor) |
| A4 | BMA / TattleTots | Self-organizing drone/tractor ecology |

## Integrated Mode (with TattleTots Agent Ecology)

Requires TattleTots:

```bash
pip install -e TattleTots[dev]
grain-guard sim --layer tattletots --config configs/tattletots_integration.json --output results.json --verbose
```

Legacy:

```bash
python scripts/run_with_tattletots.py \
    --config configs/tattletots_integration.json \
    --output results.json \
    --verbose
```

This produces unified JSON output (`tattletots.output_schema.SimulationOutput`) with consistent `ecology_metrics` and `cost_metrics` fields, enabling cross-domain comparison with the sibling repos ([Coral_Key_in_Three_Hour_Epochs](https://github.com/bckirkup/Coral_Key_in_Three_Hour_Epochs), [Scrapiron_and_the_Bear](https://github.com/bckirkup/Scrapiron_and_the_Bear)).

See [docs/COORDINATION.md](docs/COORDINATION.md) for full coordination guide, configuration reference, and comparison examples.

## Development

```bash
ruff check src/ tests/         # Lint
ruff format --check src/ tests/ # Format check
mypy src/                       # Type check (strict mode)
pytest                          # All tests
pytest -m smoke                 # Smoke tests only
```

## Falsification Test (Spec §10)

BMA must achieve equal or better yield protection with **less total pesticide input AND slower resistance evolution**, compared to the centralized precision ag platform receiving the same sensor data. If centralized beats BMA in monoculture, that's a real result — BMA's advantage should appear in orchard and intercropping where local heterogeneity is highest.

## Spec Documents

- [`grain_tots_spec_v2.md`](grain_tots_spec_v2.md) — Full domain specification
- [`domain_master_plan_v2.md`](domain_master_plan_v2.md) — Cross-domain architecture comparison plan

## License

Apache-2.0
