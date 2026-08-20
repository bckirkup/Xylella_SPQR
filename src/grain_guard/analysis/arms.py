"""Run one measurement arm and emit a unified ``SimulationOutput``.

An arm is a (grounded input fraction, seed) pair at otherwise identical
configuration. The pest adversary is frozen for detector-side arms so a moving
target cannot hide or fake detector improvement; the pest reference arm is the
same configuration with the pest loop left evolving.

An arm may also be run with a caller-supplied layer setup, which is how the
designed-reporter measurement seeds genomes carrying a reporter policy without
duplicating the arm loop or its metrics.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from domain_runner.types import RunContext
from tattletots.engine.world import World
from tattletots.integration.tattletots_layer import TattleTotsLayer
from tattletots.interface.instrument import validate_instrument
from tattletots.output_schema import SimulationOutput

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.analysis.detector_gradient import LineageTracker
from grain_guard.analysis.gradient import GradientEstimates
from grain_guard.analysis.pest_reference import PestTrajectory
from grain_guard.runner import GrainDomainHooks

LayerSetup = Callable[[GrainGuardAdapter, RunContext], dict[str, Any]]
"""Builds engine layer state for one arm from its adapter and run context."""


@dataclass(frozen=True)
class ArmSpec:
    """One measurement arm.

    Attributes:
        name: arm label used for output filenames.
        grounded_input_fraction: engine knob under test.
        grounded_attractiveness_multiplier: engine knob under test.
        seed: seed shared by the domain and the engine.
        steps: number of simulation steps.
        freeze_pest_evolution: hold the pest adversary fixed.
        landscape: field landscape name.
        pest_generation_steps: steps per recorded pest generation.
        reporting_levers: enable the engine's measured reporting-opportunity
            settings (levers 1-4) instead of the engine defaults.
        reproduction_correctness_weight: weight of rank in verified correctness,
            rather than rank in reserve sufficiency, in the reproductive merit
            the population cap rations by (the engine's lever 5 response gate).
            Applies only under ``reporting_levers``; ``0.0`` is the
            reserves-only ordering measured so far.
        pest_intro_probability: per-edge-cell pest introduction probability;
            ``0.0`` gives a pest-free field, which is how a no-event control
            window is built.
        ecology_enabled: enable the phase-1 coupled ecology; false reproduces
            the legacy uncoupled domain for before/after measurement.
        pest_damage_visibility_lag_steps: steps between pest injury being
            committed and becoming visible. ``None`` keeps the domain default;
            ``0`` reproduces the immediately-visible damage measured in phase 1.
        spray_budget_capacity: maximum applications in one budget interval.
            ``None`` preserves the unlimited lagged-damage baseline, and is the
            default because the global cap destroyed the resurgence criterion.
        spray_budget_interval_steps: length of the budget interval in steps.
        sprayer_fleet_enabled: give the farm finite per-Tot spray tanks, so an
            application spent on a false positive is unavailable nearby.
            ``False`` preserves the unlimited lagged-damage baseline.
        n_spot_sprayers: spray drones owned; ``None`` uses the fleet default.
        spot_tank_liters: tank volume per drone; ``None`` uses the body plan.
        liters_per_application: product one application consumes; ``None`` uses
            the fleet default.
        applications_per_step: cells one loaded drone treats per step; ``None``
            uses the fleet default.
        refill_duration_steps: steps spent refilling on arrival; ``None`` uses
            the fleet default.
        spray_weather_enabled: gate applications on the weather they are made
            in, so wind refuses a spray and rain washes part of it off.
            ``False`` preserves the tank-capacity baseline, in which weather
            never touches efficacy.
        wind_block_speed_mps: wind at or above which an application is refused;
            ``None`` uses the weather-gate default.
        rain_washoff_full_mm: rainfall that washes off the full washable share
            of a dose; ``None`` uses the weather-gate default.
        washoff_strength: share of a dose rain can remove; ``None`` uses the
            weather-gate default.
    """

    name: str
    grounded_input_fraction: float
    seed: int
    steps: int = 400
    grounded_attractiveness_multiplier: float = 1.0
    freeze_pest_evolution: bool = True
    landscape: str = "monoculture"
    pest_generation_steps: int = 14
    reporting_levers: bool = False
    reproduction_correctness_weight: float = 0.0
    pest_intro_probability: float | None = None
    ecology_enabled: bool = True
    pest_damage_visibility_lag_steps: int | None = None
    spray_budget_capacity: int | None = None
    spray_budget_interval_steps: int = 7
    sprayer_fleet_enabled: bool = False
    n_spot_sprayers: int | None = None
    spot_tank_liters: float | None = None
    liters_per_application: float | None = None
    applications_per_step: int | None = None
    refill_duration_steps: int | None = None
    spray_weather_enabled: bool = False
    wind_block_speed_mps: float | None = None
    rain_washoff_full_mm: float | None = None
    washoff_strength: float | None = None


@dataclass
class ArmRun:
    """Everything one executed arm exposes for measurement.

    Attributes:
        output: engine and domain metrics for the arm.
        adapter: the domain adapter the arm ran against.
        world: the engine world after the final step.
        tracker: detector-side lineage bookkeeping.
        pest: pest-side generation snapshots.
        steps_completed: steps actually run before any early stop.
    """

    output: SimulationOutput
    adapter: GrainGuardAdapter
    world: World
    tracker: LineageTracker
    pest: PestTrajectory
    steps_completed: int


def _reporting_lever_config() -> dict[str, Any]:
    """The engine's measured reporting-opportunity settings (levers 1-4)."""
    return {
        "correct_report_attention_value": 8.0,
        "false_alarm_break_even_precision": 0.2,
        "reproduction_merit_ordering": True,
        "escalation_calibration_in_score_units": True,
    }


def simulation_config(spec: ArmSpec) -> dict[str, Any]:
    """Engine configuration for one arm."""
    config: dict[str, Any] = {
        "initial_population": 30,
        "max_population": 80,
        "max_steps": spec.steps,
        "seed": spec.seed,
        "mutation_rate": 0.1,
        "recombination_probability": 0.3,
        "false_alarm_penalty": 0.4,
        "trust_delta_neg": 0.2,
        "trust_delta_pos": 0.05,
        "trust_delta_miss": 0.15,
        "max_stream_dim": 75,
        "grounded_input_fraction": spec.grounded_input_fraction,
        "grounded_attractiveness_multiplier": spec.grounded_attractiveness_multiplier,
    }
    if spec.reporting_levers:
        config.update(_reporting_lever_config())
        config["reproduction_correctness_weight"] = spec.reproduction_correctness_weight
    return config


def ecology_config(spec: ArmSpec) -> dict[str, Any]:
    """Domain ecology settings for one arm."""
    config: dict[str, Any] = {"enabled": spec.ecology_enabled}
    if spec.pest_damage_visibility_lag_steps is not None:
        config["pest_damage_visibility_lag_steps"] = spec.pest_damage_visibility_lag_steps
    return config


def domain_config(spec: ArmSpec) -> dict[str, Any]:
    """Domain configuration for one arm."""
    config: dict[str, Any] = {
        "grid_rows": 20,
        "grid_cols": 20,
        "landscape": spec.landscape,
        "seed": spec.seed,
        "n_traps": 10,
        "n_weather_stations": 2,
        "n_soil_sensors": 4,
        "satellite_revisit": 5,
        "pest_threshold": 10.0,
        "engine_max_dim": 75,
        "freeze_pest_evolution": spec.freeze_pest_evolution,
        "ecology_config": ecology_config(spec),
    }
    if spec.spray_budget_capacity is not None:
        config["spray_budget_config"] = {
            "capacity": spec.spray_budget_capacity,
            "interval_steps": spec.spray_budget_interval_steps,
        }
    if spec.sprayer_fleet_enabled:
        config["sprayer_fleet_config"] = sprayer_fleet_config(spec)
    if spec.spray_weather_enabled:
        config["spray_weather_config"] = spray_weather_config(spec)
    if spec.pest_intro_probability is not None:
        config["pest_intro_probability"] = spec.pest_intro_probability
    return config


def sprayer_fleet_config(spec: ArmSpec) -> dict[str, Any]:
    """Per-Tot tank settings for one arm, omitting unset overrides."""
    overrides: dict[str, Any] = {
        "n_spot_sprayers": spec.n_spot_sprayers,
        "spot_tank_liters": spec.spot_tank_liters,
        "liters_per_application": spec.liters_per_application,
        "applications_per_step": spec.applications_per_step,
        "refill_duration_steps": spec.refill_duration_steps,
    }
    return {key: value for key, value in overrides.items() if value is not None}


def spray_weather_config(spec: ArmSpec) -> dict[str, Any]:
    """Weather-gate settings for one arm, omitting unset overrides."""
    overrides: dict[str, Any] = {
        "wind_block_speed_mps": spec.wind_block_speed_mps,
        "rain_washoff_full_mm": spec.rain_washoff_full_mm,
        "washoff_strength": spec.washoff_strength,
    }
    return {key: value for key, value in overrides.items() if value is not None}


def run_context(spec: ArmSpec) -> RunContext:
    """Domain-runner run context for one arm."""
    return RunContext(
        steps=spec.steps,
        seed=spec.seed,
        domain_config=domain_config(spec),
        layer="tattletots",
        simulation_config=simulation_config(spec),
        verbose=False,
        output_path=None,
    )


def _halves(reports: list[int], correct: list[int]) -> dict[str, float]:
    """Correct-report rate in the first and second half of the run."""
    n = min(len(reports), len(correct))
    if n < 2:
        return {}
    mid = n // 2
    first_reports = sum(reports[:mid])
    second_reports = sum(reports[mid:n])
    first_correct = sum(correct[:mid])
    second_correct = sum(correct[mid:n])
    first_rate = first_correct / first_reports if first_reports else 0.0
    second_rate = second_correct / second_reports if second_reports else 0.0
    return {
        "first_half_reports": float(first_reports),
        "second_half_reports": float(second_reports),
        "first_half_correct_report_rate": first_rate,
        "second_half_correct_report_rate": second_rate,
        "correct_report_rate_delta": second_rate - first_rate,
        "first_half_correct_reports_per_step": first_correct / mid,
        "second_half_correct_reports_per_step": second_correct / (n - mid),
    }


def _per_capita_solvency(
    solvent: list[int], population: list[int], capacity: list[float]
) -> dict[str, float]:
    """Per-capita attention solvency over steps with a living population."""
    n = min(len(solvent), len(population), len(capacity))
    live = [i for i in range(n) if population[i] > 0]
    if not live:
        return {}
    solvent_share = [solvent[i] / population[i] for i in live]
    capacity_per_capita = [capacity[i] / population[i] for i in live]
    return {
        "mean_attention_solvent_share": sum(solvent_share) / len(live),
        "mean_attention_capacity_per_capita": sum(capacity_per_capita) / len(live),
        "final_attention_solvent_share": solvent_share[-1],
    }


def _estimates_dict(estimates: GradientEstimates | None) -> dict[str, Any]:
    return asdict(estimates) if estimates is not None else {}


def instrument_nulls(spec: ArmSpec) -> dict[str, Any]:
    """Instrument-level nulls, measured on a fresh adapter of the same config."""
    hooks = GrainDomainHooks()
    adapter = hooks.build_adapter(domain_config(spec))
    report = validate_instrument(adapter, spec.steps)
    return {
        "static_prior_null": report.static_prior_baseline,
        "uniform_null": report.chance_baseline,
        "inferability_precision": report.inferability_precision,
        "decoder_precision": report.decoder_precision,
        "distinct_event_locations": report.distinct_event_locations,
        "event_steps": report.event_steps,
        "instrument_valid": report.valid,
        "instrument_findings": {f.check.value: f.passed for f in report.findings},
    }


def execute_arm(
    spec: ArmSpec,
    *,
    setup: LayerSetup | None = None,
    observe: Callable[[World, int], None] | None = None,
) -> ArmRun:
    """Run one arm and return its output alongside the objects it ran on."""
    hooks = GrainDomainHooks()
    run = run_context(spec)
    adapter = hooks.build_adapter(run.domain_config)
    layer = TattleTotsLayer()
    state = setup(adapter, run) if setup is not None else layer.setup(adapter, run)
    tracker = LineageTracker()
    pest = PestTrajectory(generation_steps=spec.pest_generation_steps)
    started = time.time()

    steps_completed = 0
    for step in range(spec.steps):
        events = layer.step(adapter, step, state)
        tracker.observe(state["world"], step)
        if observe is not None:
            observe(state["world"], step)
        pest.record(adapter.field, step)
        steps_completed = step + 1
        if events.get("stop"):
            break

    metrics = layer.finalize(adapter, state, run)
    output: SimulationOutput = metrics["simulation_output"]
    output.run_summary.wall_time_seconds = time.time() - started
    series = output.time_series
    ecology = output.ecology_metrics
    output.domain_metrics = {
        "arm": spec.name,
        "arm_spec": asdict(spec),
        "steps_completed": steps_completed,
        "pest_evolution_frozen": adapter.pest_evolution_frozen,
        "detector_gradient": _estimates_dict(tracker.estimates()),
        "detector_function_selection_differential": tracker.function_selection_differential(),
        "detector_cohort": tracker.summary(),
        "pest_gradient": _estimates_dict(pest.estimates()),
        "pest_traits": pest.trait_summary(),
        "pest_generations_recorded": pest.n_generations,
        "correct_report_halves": _halves(series.reports_issued, series.correct_reports),
        "attention_solvency": _per_capita_solvency(
            series.n_attention_solvent_agents,
            series.population,
            series.attention_carrying_capacity,
        ),
        "grounded_yield_share": ecology.grounded_yield_share,
        "effective_grounded_yield_share": ecology.effective_grounded_yield_share,
        "report_precision": ecology.precision,
        "static_prior_null_engine": ecology.static_prior_precision,
        "uniform_null_engine": ecology.chance_precision,
        "instrument": instrument_nulls(spec),
    }
    return ArmRun(
        output=output,
        adapter=adapter,
        world=state["world"],
        tracker=tracker,
        pest=pest,
        steps_completed=steps_completed,
    )


def run_arm(spec: ArmSpec) -> SimulationOutput:
    """Run one arm and return its ``SimulationOutput`` with gradient metrics."""
    return execute_arm(spec).output
