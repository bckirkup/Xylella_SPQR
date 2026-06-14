#!/usr/bin/env python3
"""Run GrainGuard (Xylella_SPQR) simulation integrated with the TattleTots engine.

This script plugs the GrainGuard domain adapter into the full TattleTots
agent ecology — agents compress sensor streams, evolve, form trophic
hierarchies, and escalate anomalies to human users.

Usage:
    python scripts/run_with_tattletots.py --config configs/tattletots_integration.json --output results.json
    python scripts/run_with_tattletots.py --steps 200 --seed 7 --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tattletots.engine.config import SimulationConfig
from tattletots.engine.world import World
from tattletots.output_schema import (
    CostMetrics,
    EcologyMetrics,
    RunSummary,
    SimulationOutput,
    TimeSeries,
)
from tattletots.telemetry.cost_accounting import CostAccumulator

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType
from grain_guard.metrics.ag_metrics import AgMetrics, StepMetrics


def main(argv: list[str] | None = None) -> int:
    """Run integrated GrainGuard + TattleTots simulation."""
    parser = argparse.ArgumentParser(
        prog="run_with_tattletots",
        description="GrainGuard: precision agriculture integrated with TattleTots agent ecology",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON config file (contains 'simulation' and 'domain' sections)",
    )
    parser.add_argument("--steps", type=int, default=200, help="Simulation steps (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--population", type=int, default=20, help="Initial agent population")
    parser.add_argument(
        "--landscape",
        choices=["monoculture", "orchard", "intercrop"],
        default="monoculture",
        help="Landscape type",
    )
    parser.add_argument("--output", type=Path, help="Path to write unified JSON results")
    parser.add_argument("--verbose", action="store_true", help="Print step-by-step progress")
    args = parser.parse_args(argv)

    # Load configuration
    if args.config:
        with open(args.config) as f:
            raw = json.load(f)
        sim_config = SimulationConfig(**raw.get("simulation", {}))
        domain_cfg = raw.get("domain", {})
        landscape = LandscapeType(domain_cfg.get("landscape", "monoculture"))
        grid_rows = domain_cfg.get("grid_rows", 20)
        grid_cols = domain_cfg.get("grid_cols", 20)
        steps = domain_cfg.get("steps", args.steps)
        seed = domain_cfg.get("seed", args.seed)
    else:
        sim_config = SimulationConfig(
            initial_population=args.population,
            max_steps=args.steps,
            seed=args.seed,
        )
        landscape = LandscapeType(args.landscape)
        grid_rows = 20
        grid_cols = 20
        steps = args.steps
        seed = args.seed
        domain_cfg = {
            "landscape": args.landscape,
            "grid_rows": grid_rows,
            "grid_cols": grid_cols,
            "steps": steps,
            "seed": seed,
        }

    # Build domain adapter
    adapter = GrainGuardAdapter(
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        landscape=landscape,
        seed=seed,
    )

    # Build TattleTots world
    world = World(config=sim_config)
    for stream in adapter.get_streams():
        world.add_stream(stream)
    for user in adapter.get_users():
        world.add_user(user)
    world.seed_population()

    # Run simulation
    cost_accumulator = CostAccumulator()
    ag_metrics = AgMetrics()
    start_time = time.time()

    print("=== GrainGuard + TattleTots Integration ===")
    print(
        f"  Steps: {steps}, Landscape: {landscape.value}, "
        f"Population: {sim_config.initial_population}, Seed: {seed}"
    )
    print()

    for step in range(steps):
        # Advance domain
        adapter.step(step)
        world.set_ground_truth(adapter.get_ground_truth(step))

        # Advance agent ecology
        record = world.step()

        if args.verbose and step % 50 == 0:
            field = adapter.field
            print(
                f"  Step {step:4d}: pop={record.population:3d} "
                f"health={field.mean_crop_health():.3f} "
                f"pests={field.total_pest_density():.1f} "
                f"reports={record.reports_issued}"
            )

        # Cost accounting
        cost_dict = adapter.compute_costs(
            n_escalations=record.reports_issued,
            n_correct=record.correct_reports,
            n_false_alarms=record.false_alarms,
            n_missed=record.missed_events,
        )
        cost_accumulator.record_from_dict(record.time_step, cost_dict)

        # Domain metrics
        ag_metrics.record_step(
            StepMetrics(
                time_step=step,
                mean_crop_health=adapter.field.mean_crop_health(),
                mean_yield_potential=adapter.field.mean_yield_potential(),
                total_pest_density=adapter.field.total_pest_density(),
                total_weed_density=adapter.field.total_weed_density(),
            )
        )

        if record.population == 0:
            print("  ** Total extinction **")
            break

    wall_time = time.time() - start_time

    # Gather results
    summary = world.telemetry.summary()
    cost_summary = cost_accumulator.summary()

    print()
    print("=== Simulation Complete ===")
    print(f"  Final population: {summary['final_population']}")
    print(f"  Precision:        {summary['precision']:.2%}")
    print(f"  Total cost:       {cost_summary['total_cost']:.2f}")
    print(f"  Yield protected:  {ag_metrics.yield_protected:.3f}")
    print(f"  Wall time:        {wall_time:.1f}s")

    # Build unified output
    output = SimulationOutput(
        run_summary=RunSummary(
            domain="grain_guard",
            steps_completed=world.telemetry.total_steps,
            seed=seed,
            wall_time_seconds=wall_time,
        ),
        simulation_config=sim_config.model_dump(),
        domain_config=domain_cfg,
        ecology_metrics=EcologyMetrics(
            final_population=int(summary["final_population"]),
            peak_population=int(summary["peak_population"]),
            total_births=int(summary["total_births"]),
            total_deaths=int(summary["total_deaths"]),
            total_reports=int(summary["total_reports"]),
            precision=float(summary["precision"]),
            max_trophic_depth=float(summary["max_trophic_depth"]),
            reached_equilibrium=bool(summary["reached_equilibrium"]),
        ),
        cost_metrics=CostMetrics(
            total_surveillance_cost=cost_summary["total_surveillance_cost"],
            total_response_cost=cost_summary["total_response_cost"],
            total_damage_cost=cost_summary["total_damage_cost"],
            total_cost=cost_summary["total_cost"],
            mean_cost_per_step=cost_summary["mean_cost_per_step"],
        ),
        domain_metrics=ag_metrics.summary(),
        time_series=TimeSeries(
            population=world.telemetry.population_history(),
            cost_per_step=cost_accumulator.cost_history(),
        ),
    )

    if args.output:
        output.write_json(args.output)
        print(f"\n  Results written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
