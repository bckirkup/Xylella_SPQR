"""Run one GrainGuard simulation through the TattleTots layer."""

from __future__ import annotations

import argparse

from grain_guard.runner import GrainDomainHooks, run_grain_simulation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    hooks = GrainDomainHooks()
    run = hooks.load_run_context(
        config_path=args.config,
        cli_overrides={"layer": "tattletots", "output": args.output},
    )
    run_grain_simulation(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
