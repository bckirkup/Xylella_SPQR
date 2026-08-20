"""Shared command-line options for the per-Tot spray-capacity measurements.

Both measurement scripts (the designed-reporter margin run and the resurgence
run) need the same equipment knobs, and the two must agree exactly or their
numbers are not comparable, so the flags live here rather than in either script.
"""

from __future__ import annotations

import argparse

from grain_guard.equipment.sprayer_fleet import SprayerFleetConfig


def add_sprayer_fleet_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the finite-tank equipment flags to a measurement script's parser."""
    parser.add_argument(
        "--sprayer-fleet",
        action="store_true",
        help=(
            "Give the farm finite per-Tot spray tanks with refill travel and downtime. "
            "Omit for the unlimited capacity the lagged-damage baseline was measured under."
        ),
    )
    parser.add_argument(
        "--n-spot-sprayers",
        type=int,
        default=None,
        help="Spray drones owned; only used with --sprayer-fleet.",
    )
    parser.add_argument(
        "--spot-tank-liters",
        type=float,
        default=None,
        help="Tank volume per drone; defaults to the spray-drone body plan.",
    )
    parser.add_argument(
        "--liters-per-application",
        type=float,
        default=None,
        help="Product one targeted application consumes; only used with --sprayer-fleet.",
    )
    parser.add_argument(
        "--applications-per-step",
        type=int,
        default=None,
        help="Cells one loaded drone treats per step; only used with --sprayer-fleet.",
    )
    parser.add_argument(
        "--refill-duration",
        type=int,
        default=None,
        help="Steps spent refilling after arriving at the refill point.",
    )


def sprayer_fleet_config_from_args(args: argparse.Namespace) -> SprayerFleetConfig | None:
    """Build the fleet config a parsed namespace asks for, or ``None``."""
    if not args.sprayer_fleet:
        return None
    overrides = {
        "n_spot_sprayers": args.n_spot_sprayers,
        "spot_tank_liters": args.spot_tank_liters,
        "liters_per_application": args.liters_per_application,
        "applications_per_step": args.applications_per_step,
        "refill_duration_steps": args.refill_duration,
    }
    return SprayerFleetConfig.model_validate(
        {key: value for key, value in overrides.items() if value is not None}
    )
