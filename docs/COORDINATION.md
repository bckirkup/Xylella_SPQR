# Cross-Repository Coordination Guide

This document explains how Xylella_SPQR (GrainGuard) integrates with TattleTots and the sibling domain repos.

## Repository Ecosystem

| Repository | Role | Package |
|------------|------|---------|
| **TattleTots** | Agent ecology engine (domain-agnostic) | `tattletots` |
| **Coral_Key_in_Three_Hour_Epochs** | ReefWatch fishery domain adapter | `coral-key` |
| **Xylella_SPQR** (this repo) | GrainGuard agriculture domain adapter | `grain-guard` |
| **Scrapiron_and_the_Bear** | FireEcology wildfire domain adapter | `fire-ecology` |

## How GrainGuard Connects to TattleTots

GrainGuard implements the `DomainAdapter` ABC from TattleTots:

```python
from tattletots.interface.domain_adapter import DomainAdapter

class GrainGuardAdapter(DomainAdapter):
    def get_streams(self) -> list[Stream]: ...      # Satellite, traps, weather, soil
    def get_users(self) -> list[User]: ...          # Farm Manager, Agronomist
    def step(self, time_step: int) -> None: ...     # Advance field + pests + weather
    def get_ground_truth(self, time_step: int) -> bool: ...  # Infestation above EIL?
    def compute_costs(self, ...) -> dict[str, float]: ...    # Spray + damage costs
```

## Installation for Coordinated Use

```bash
# Install TattleTots first (engine dependency)
pip install -e /path/to/TattleTots[dev]

# Install this repo
pip install -e ".[dev]"

# Optionally install sibling domains for cross-comparison
pip install -e /path/to/Coral_Key_in_Three_Hour_Epochs[dev]
pip install -e /path/to/Scrapiron_and_the_Bear[dev]
```

## Running Modes

### Standalone (domain-only, no agent ecology)

```bash
grain-guard --steps 200 --landscape monoculture --verbose --json
```

Exercises the agricultural simulation (crop growth, pest dynamics, sensor observations) without TattleTots agents.

### Integrated (domain + TattleTots agent ecology)

```bash
python scripts/run_with_tattletots.py \
    --config configs/tattletots_integration.json \
    --output integrated_results.json \
    --verbose
```

Runs the full loop: domain generates sensor streams → Tot agents compress/escalate → trust/evolution dynamics → cost accounting.

## Configuration

The integrated config (`configs/tattletots_integration.json`) has two sections:

- **`simulation`**: TattleTots engine params (population size, mutation rate, trust dynamics)
- **`domain`**: GrainGuard params (landscape type, grid size, sensor placement, pest threshold)

### Key Parameters to Tune

| Parameter | Section | Effect |
|-----------|---------|--------|
| `initial_population` | simulation | Number of starting Tot agents |
| `max_stream_dim` | simulation | Per-agent input cap (keep ≤30 for performance) |
| `landscape` | domain | Field structure (monoculture/orchard/intercrop) |
| `grid_rows`/`grid_cols` | domain | Field resolution |
| `pest_threshold` | domain | Economic injury level for ground truth |
| `n_traps` | domain | Pheromone trap network density |

## Output Format

Integrated runs produce unified JSON (see TattleTots `docs/COORDINATION.md` for full schema).

Domain-specific metrics in `domain_metrics`:

```json
{
  "yield_protected": 0.87,
  "total_spray_volume": 145.5,
  "false_spray_rate": 0.08,
  "total_missed_cells": 12.0,
  "final_resistance_freq": 0.15,
  "mean_detection_latency": 4.2,
  "total_cost": 3200.0,
  "biological_control_mean": 0.45
}
```

## Cross-Domain Comparison

All domain repos produce the same top-level structure. Compare across domains:

```python
from tattletots.output_schema import SimulationOutput

coral = SimulationOutput.read_json("coral_results.json")
fire = SimulationOutput.read_json("fire_results.json")
grain = SimulationOutput.read_json("grain_results.json")

# Same metrics available for each
for r in [coral, fire, grain]:
    print(f"{r.run_summary.domain}: cost={r.cost_metrics.total_cost:.0f} "
          f"precision={r.ecology_metrics.precision:.2%}")
```

## Relationship to Sibling Repos

Each domain repo is structurally parallel:
- `src/<package>/adapter/` — DomainAdapter implementation
- `scripts/run_with_tattletots.py` — Integrated runner
- `configs/tattletots_integration.json` — Default integrated config
- `docs/COORDINATION.md` — This file

The domains share no code with each other — only with TattleTots via the `DomainAdapter` interface. This ensures each domain can evolve independently while maintaining compatible outputs.
