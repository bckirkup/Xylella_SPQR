"""Shared command-line options for the weather-gated efficacy measurements.

Both measurement scripts (the designed-reporter margin run and the resurgence
run) need the same weather knobs, and the two must agree exactly or their
numbers are not comparable, so the flags live here rather than in either script.
"""

from __future__ import annotations

import argparse

from grain_guard.environment.spray_weather import SprayWeatherConfig


def add_spray_weather_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the weather-gate flags to a measurement script's parser."""
    parser.add_argument(
        "--spray-weather",
        action="store_true",
        help=(
            "Gate applications on the weather: wind refuses a spray and rain washes "
            "part of it off. Omit for the weather-blind tank-capacity baseline."
        ),
    )
    parser.add_argument(
        "--wind-block-speed",
        type=float,
        default=None,
        help="Wind speed (m/s) at or above which an application is refused.",
    )
    parser.add_argument(
        "--rain-washoff-full-mm",
        type=float,
        default=None,
        help="Rainfall (mm) that washes off the full washable share of a dose.",
    )
    parser.add_argument(
        "--washoff-strength",
        type=float,
        default=None,
        help="Share of a dose rain can remove, from 0.0 to 1.0.",
    )


def spray_weather_config_from_args(args: argparse.Namespace) -> SprayWeatherConfig | None:
    """Build the weather-gate config a parsed namespace asks for, or ``None``."""
    if not args.spray_weather:
        return None
    overrides = {
        "wind_block_speed_mps": args.wind_block_speed,
        "rain_washoff_full_mm": args.rain_washoff_full_mm,
        "washoff_strength": args.washoff_strength,
    }
    return SprayWeatherConfig.model_validate(
        {key: value for key, value in overrides.items() if value is not None}
    )
