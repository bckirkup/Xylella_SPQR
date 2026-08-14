#!/usr/bin/env python3
"""Run GrainGuard with TattleTots layer (thin wrapper — prefer `grain-guard sim --layer tattletots`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from grain_guard.runner import GrainDomainHooks, run_grain_simulation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GrainGuard + TattleTots integration")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    hooks = GrainDomainHooks()
    run = hooks.load_run_context(
        config_path=str(args.config) if args.config else None,
        cli_overrides={
            "layer": "tattletots",
            "verbose": args.verbose,
            "domain": {"steps": args.steps, "seed": args.seed},
            "simulation": {
                "initial_population": args.population,
                "max_steps": args.steps,
                "seed": args.seed,
            },
            "output": str(args.output) if args.output else None,
        },
    )
    run_grain_simulation(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
