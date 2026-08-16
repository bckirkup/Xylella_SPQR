"""CLI entry-point for GrainGuard simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from grain_guard.runner import GrainDomainHooks, run_grain_batch, run_grain_simulation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GrainGuard: precision agriculture simulator")
    subparsers = parser.add_subparsers(dest="command", required=False)

    sim_parser = subparsers.add_parser("sim", help="Run a single simulation")
    sim_parser.add_argument("--steps", type=int, default=200)
    sim_parser.add_argument(
        "--landscape", default="monoculture", choices=["monoculture", "orchard", "intercrop"]
    )
    sim_parser.add_argument("--rows", type=int, default=20)
    sim_parser.add_argument("--cols", type=int, default=20)
    sim_parser.add_argument("--seed", type=int, default=42)
    sim_parser.add_argument("--layer", default="domain_only", choices=["domain_only", "tattletots"])
    sim_parser.add_argument("--config", type=str)
    sim_parser.add_argument("--output", type=Path)
    sim_parser.add_argument("--verbose", action="store_true")
    sim_parser.add_argument("--json", action="store_true")

    batch_parser = subparsers.add_parser("batch", help="Run batch simulations")
    batch_parser.add_argument("--config", type=str, required=True)
    batch_parser.add_argument("--output-dir", type=Path)
    batch_parser.add_argument("--parallel", action="store_true")
    batch_parser.add_argument("--workers", type=int)
    batch_parser.add_argument("--verbose", action="store_true")

    effective = argv if argv is not None else sys.argv[1:]
    if effective and effective[0] not in ("sim", "batch", "-h", "--help"):
        effective = ["sim", *effective]
    elif not effective:
        effective = ["sim"]

    args = parser.parse_args(effective)

    if args.command == "batch":
        run_grain_batch(
            Path(args.config),
            output_dir=args.output_dir,
            parallel=args.parallel,
            workers=args.workers,
            verbose=args.verbose,
        )
        return

    hooks = GrainDomainHooks()
    run = hooks.load_run_context(
        config_path=args.config,
        cli_overrides={
            "domain": {
                "steps": args.steps,
                "landscape": args.landscape,
                "grid_rows": args.rows,
                "grid_cols": args.cols,
                "seed": args.seed,
            },
            "layer": args.layer,
            "verbose": args.verbose,
            "output": str(args.output) if args.output else None,
        },
    )
    result = run_grain_simulation(run)
    if args.json and not args.output:
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
