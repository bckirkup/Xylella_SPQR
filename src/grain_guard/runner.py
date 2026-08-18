"""GrainGuard simulation runner — layer-agnostic single/batch entry points."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

from domain_runner.batch import run_batch as execute_batch
from domain_runner.config import deep_merge, load_json
from domain_runner.layer import DomainOnlyLayer, SimulationLayer
from domain_runner.single import print_result_summary, run_simulation_timed
from domain_runner.types import RunContext, SimulationResult

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType

_DEFAULT_DOMAIN: dict[str, Any] = {
    "grid_rows": 20,
    "grid_cols": 20,
    "landscape": "monoculture",
    "seed": 42,
    "steps": 200,
}

_INT_ADAPTER_KEYS: tuple[str, ...] = (
    "n_traps",
    "n_weather_stations",
    "n_soil_sensors",
    "satellite_revisit",
    "satellite_zone_rows",
    "satellite_zone_cols",
    "yield_zones",
    "engine_max_dim",
)
_FLOAT_ADAPTER_KEYS: tuple[str, ...] = (
    "pest_threshold",
    "pest_intro_probability",
    "resistance_initial_frequency",
)
_BOOL_ADAPTER_KEYS: tuple[str, ...] = ("freeze_pest_evolution",)
_OBJECT_ADAPTER_KEYS: tuple[str, ...] = ("ecology_config",)


def adapter_kwargs_from_config(domain_config: dict[str, Any]) -> dict[str, Any]:
    """Extract adapter keyword arguments a domain config may override.

    Grid geometry, landscape, and seed are passed separately by the caller.
    Keys absent from the config keep the adapter's own defaults, so a config
    that names a sensor count or the pest-evolution freeze is no longer
    silently dropped.
    """
    kwargs: dict[str, Any] = {}
    for key in _INT_ADAPTER_KEYS:
        if key in domain_config:
            kwargs[key] = int(domain_config[key])
    for key in _FLOAT_ADAPTER_KEYS:
        if key in domain_config:
            kwargs[key] = float(domain_config[key])
    for key in _BOOL_ADAPTER_KEYS:
        if key in domain_config:
            kwargs[key] = bool(domain_config[key])
    for key in _OBJECT_ADAPTER_KEYS:
        if key in domain_config:
            kwargs[key] = domain_config[key]
    return kwargs


class GrainDomainHooks:
    domain_name = "grain_guard"
    default_config_path = "configs/domain_default.json"

    def load_run_context(
        self,
        *,
        config_path: str | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> RunContext:
        raw: dict[str, Any] = {"domain": dict(_DEFAULT_DOMAIN), "layer": "domain_only"}
        if config_path:
            raw = deep_merge(raw, load_json(config_path))
        if cli_overrides:
            if "domain" in cli_overrides:
                raw["domain"] = deep_merge(raw.get("domain", {}), cli_overrides["domain"])
            for key in ("layer", "simulation", "output", "verbose"):
                if key in cli_overrides:
                    raw[key] = cli_overrides[key]

        domain_cfg = dict(raw.get("domain", {}))
        steps = int(domain_cfg.pop("steps", _DEFAULT_DOMAIN["steps"]))
        return RunContext(
            steps=steps,
            seed=int(domain_cfg.get("seed", 42)),
            domain_config=domain_cfg,
            layer=str(raw.get("layer", "domain_only")),
            simulation_config=dict(raw.get("simulation", {})),
            verbose=bool(raw.get("verbose", False)),
            output_path=Path(raw["output"]) if raw.get("output") else None,
        )

    def build_adapter(self, domain_config: dict[str, Any]) -> GrainGuardAdapter:
        landscape = LandscapeType(domain_config.get("landscape", "monoculture"))
        return GrainGuardAdapter(
            grid_rows=int(domain_config.get("grid_rows", 20)),
            grid_cols=int(domain_config.get("grid_cols", 20)),
            landscape=landscape,
            seed=int(domain_config.get("seed", 42)),
            **adapter_kwargs_from_config(domain_config),
        )

    def print_header(self, _adapter: GrainGuardAdapter, run: RunContext) -> None:
        print(f"=== GrainGuard ({run.layer}) ===")
        print(
            f"  Steps: {run.steps}, Landscape: {run.domain_config.get('landscape')}, Seed: {run.seed}"
        )
        print()

    def on_step(
        self,
        _adapter: GrainGuardAdapter,
        _step: int,
        _layer_events: dict[str, Any],
    ) -> None:
        return

    def should_stop(
        self, _adapter: GrainGuardAdapter, _step: int, layer_events: dict[str, Any]
    ) -> bool:
        return bool(layer_events.get("stop"))

    def print_step(
        self,
        adapter: GrainGuardAdapter,
        step: int,
        _layer_events: dict[str, Any],
        *,
        verbose: bool,
    ) -> None:
        if verbose and step % 50 == 0:
            field = adapter.field
            print(
                f"  Step {step:4d}: health={field.mean_crop_health():.3f} "
                f"pests={field.total_pest_density():.1f}"
            )

    def summarize(
        self, adapter: GrainGuardAdapter, layer_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        field = adapter.field
        summary = {
            "final_health": field.mean_crop_health(),
            "final_yield": field.mean_yield_potential(),
            "total_pests": field.total_pest_density(),
            "primary_pests": field.total_primary_pest_density(),
            "secondary_pests": field.total_secondary_pest_density(),
            "total_weeds": field.total_weed_density(),
        }
        if "telemetry_summary" in layer_metrics:
            summary["ecology"] = layer_metrics["telemetry_summary"]
        return summary

    def write_output(self, result: SimulationResult, path: str) -> None:
        if "simulation_output" in result.layer_metrics:
            output = result.layer_metrics["simulation_output"]
            output.run_summary.wall_time_seconds = result.wall_time_seconds
            output.domain_metrics = result.domain_metrics
            output.write_json(path)
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)


def resolve_layer(name: str) -> SimulationLayer:
    if name in ("domain_only", "domain", "none"):
        return DomainOnlyLayer()
    if name in ("tattletots", "tots"):
        from tattletots.integration.tattletots_layer import TattleTotsLayer

        return TattleTotsLayer()
    raise ValueError(f"Unknown layer {name!r}")


def run_grain_simulation(run: RunContext) -> SimulationResult:
    hooks = GrainDomainHooks()
    result = run_simulation_timed(hooks, resolve_layer(run.layer), run)
    print_result_summary(result)
    return result


def run_grain_batch_entry(
    name: str, run_config: dict[str, Any], output_dir: Path, verbose: bool
) -> dict[str, Any]:
    layer_name = str(run_config.pop("_layer", "domain_only"))
    simulation_config = dict(run_config.pop("simulation", {}))
    steps = int(run_config.pop("steps", _DEFAULT_DOMAIN["steps"]))
    run = RunContext(
        steps=steps,
        seed=int(run_config.get("seed", 42)),
        domain_config=run_config,
        layer=layer_name,
        simulation_config=simulation_config,
        verbose=verbose,
        output_path=output_dir / f"{name}_results.json",
    )
    start = time.time()
    try:
        result = run_grain_simulation(run)
        return {
            "status": "success",
            "layer": layer_name,
            "elapsed_seconds": time.time() - start,
            "metrics": result.domain_metrics,
        }
    except Exception as exc:
        return {"status": "failed", "layer": layer_name, "error": str(exc)}


def run_grain_batch(batch_config_path: Path, **kwargs: Any) -> dict[str, Any]:
    batch = load_json(batch_config_path)
    out = Path(kwargs.get("output_dir") or batch.get("output_directory", "batch_results"))
    return cast(
        dict[str, Any],
        execute_batch(
            batch,
            run_grain_batch_entry,
            output_dir=out,
            default_config={"domain": dict(_DEFAULT_DOMAIN)},
            parallel=bool(kwargs.get("parallel")),
            workers=kwargs.get("workers"),
            verbose=bool(kwargs.get("verbose")),
        ),
    )
