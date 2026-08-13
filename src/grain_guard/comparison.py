"""Head-to-head comparison harness for baseline architectures (A0-A3).

Runs all non-TattleTots management architectures on the *same* field
scenario (same seed, same landscape) and produces summary metrics for
parameter scan analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from grain_guard.adapter.grain_adapter import CostCoefficients
from grain_guard.architectures.a0_human_ipm import HumanIPM
from grain_guard.architectures.a1_ai_tractor import AITractor
from grain_guard.architectures.a2_prescription_drone import PrescriptionDrone
from grain_guard.architectures.a3_centralized_platform import CentralizedPlatform
from grain_guard.architectures.base import Architecture
from grain_guard.environment.field import CropField, LandscapeType
from grain_guard.environment.weather import AgWeather


@dataclass
class ComparisonResult:
    """Summary for a single architecture's run."""

    name: str
    n_sprays: float = 0.0
    spray_volume_L: float = 0.0
    false_sprays: float = 0.0
    missed_cells: float = 0.0
    final_health: float = 0.0
    final_yield: float = 0.0
    total_pest_density: float = 0.0
    total_weed_density: float = 0.0
    total_cost: float = 0.0


@dataclass
class ComparisonConfig:
    """Configuration for a head-to-head comparison run."""

    steps: int = 365
    grid_rows: int = 20
    grid_cols: int = 20
    seed: int = 42
    landscape: str = "monoculture"
    pest_intro_probability: float = 0.02
    pest_density_boost: float = 1.0
    weed_density_base: float = 0.0
    resistance_initial_frequency: float = 0.01
    cost_coefficients: CostCoefficients | None = None


def _build_fresh_field(config: ComparisonConfig, rng: np.random.Generator) -> CropField:
    """Create and seed a field with deterministic pest introduction."""
    field = CropField(
        rows=config.grid_rows,
        cols=config.grid_cols,
        landscape=LandscapeType(config.landscape),
    )
    field.stochastic_pest_introduction(rng, probability=config.pest_intro_probability)

    if not np.isclose(config.pest_density_boost, 1.0, rtol=0.0, atol=0.0):
        for r in range(field.rows):
            for c in range(field.cols):
                field.pests[r][c].density *= config.pest_density_boost

    if config.weed_density_base > 0.0:
        for r in range(field.rows):
            for c in range(field.cols):
                field.weeds[r][c].density += config.weed_density_base

    if not np.isclose(config.resistance_initial_frequency, 0.01, rtol=0.0, atol=0.0):
        for r in range(field.rows):
            for c in range(field.cols):
                field.pests[r][c].resistance_freq = config.resistance_initial_frequency
                field.weeds[r][c].resistance_freq = config.resistance_initial_frequency

    return field


def _evolve_weather(time_step: int, rng: np.random.Generator) -> AgWeather:
    """Seasonal weather evolution (same as GrainGuardAdapter)."""
    phase = 2.0 * np.pi * time_step / 365.0
    return AgWeather(
        temperature=20.0 + 12.0 * np.sin(phase) + float(rng.normal(0, 2)),
        humidity=float(np.clip(0.5 + 0.2 * np.cos(phase) + rng.normal(0, 0.05), 0, 1)),
        wind_speed=max(0.0, 4.0 + 2.0 * np.sin(phase * 0.5) + float(rng.normal(0, 1))),
        wind_direction=float((180.0 + 90.0 * np.sin(phase * 0.3)) % 360),
        precipitation=max(0.0, float(rng.exponential(2.0) if rng.random() < 0.2 else 0.0)),
        solar_radiation=max(0.0, 15.0 + 8.0 * np.sin(phase) + float(rng.normal(0, 1))),
    )


def _make_architectures(seed: int) -> list[tuple[str, Architecture]]:
    """Instantiate baseline architectures A0 through A3."""
    return [
        ("A0 Human IPM", HumanIPM(seed=seed)),
        ("A1 AI Tractor", AITractor(seed=seed)),
        ("A2 Prescription Drone", PrescriptionDrone(seed=seed)),
        ("A3 Centralized Platform", CentralizedPlatform(seed=seed)),
    ]


def _compute_total_cost(
    totals: dict[str, float],
    cost: CostCoefficients,
) -> float:
    """Compute agricultural cost from accumulated step metrics."""
    return (
        totals["n_sprays"] * cost.response
        + totals["false_sprays"] * cost.false_alarm
        + totals["missed_cells"] * cost.missed
    )


def run_comparison(config: ComparisonConfig | None = None) -> list[ComparisonResult]:
    """Execute head-to-head comparison, returning per-architecture summaries."""
    if config is None:
        config = ComparisonConfig()

    cost = config.cost_coefficients or CostCoefficients()
    archs = _make_architectures(config.seed)
    results: list[ComparisonResult] = []

    for name, arch in archs:
        rng = np.random.default_rng(config.seed)
        weather_rng = np.random.default_rng(config.seed + 1)
        field = _build_fresh_field(config, rng)

        totals = {
            "n_sprays": 0.0,
            "spray_volume_L": 0.0,
            "false_sprays": 0.0,
            "missed_cells": 0.0,
        }

        for step in range(config.steps):
            weather = _evolve_weather(step, weather_rng)
            field.stochastic_pest_introduction(rng, probability=config.pest_intro_probability)
            field.step(weather, rng)

            step_result = arch.step(field, weather, step)
            for key in totals:
                totals[key] += float(step_result[key])

        arch.reset()

        results.append(
            ComparisonResult(
                name=name,
                n_sprays=round(totals["n_sprays"], 1),
                spray_volume_L=round(totals["spray_volume_L"], 1),
                false_sprays=round(totals["false_sprays"], 1),
                missed_cells=round(totals["missed_cells"], 1),
                final_health=round(field.mean_crop_health(), 4),
                final_yield=round(field.mean_yield_potential(), 4),
                total_pest_density=round(field.total_pest_density(), 1),
                total_weed_density=round(field.total_weed_density(), 1),
                total_cost=round(_compute_total_cost(totals, cost), 1),
            )
        )

    return results


def format_comparison_table(results: list[ComparisonResult]) -> str:
    """Format comparison results as an aligned text table."""
    header = (
        f"{'Architecture':<24} {'Sprays':>8} {'Volume L':>10} "
        f"{'False':>8} {'Missed':>8} {'Health':>8} {'Yield':>8} {'Cost':>10}"
    )
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(
            f"{r.name:<24} {r.n_sprays:>8,.0f} {r.spray_volume_L:>10,.1f} "
            f"{r.false_sprays:>8,.0f} {r.missed_cells:>8,.0f} "
            f"{r.final_health:>8.3f} {r.final_yield:>8.3f} {r.total_cost:>10,.1f}"
        )
    return "\n".join(lines)


def format_comparison_json(results: list[ComparisonResult]) -> str:
    """Format comparison results as JSON."""
    data = []
    for r in results:
        data.append(
            {
                "architecture": r.name,
                "n_sprays": r.n_sprays,
                "spray_volume_L": r.spray_volume_L,
                "false_sprays": r.false_sprays,
                "missed_cells": r.missed_cells,
                "final_health": r.final_health,
                "final_yield": r.final_yield,
                "total_pest_density": r.total_pest_density,
                "total_weed_density": r.total_weed_density,
                "total_cost": r.total_cost,
            }
        )
    return json.dumps(data, indent=2)
