"""Resurgence sanity experiment: does over-spraying cost anything ecologically?

This is a domain-only measurement, deliberately separate from the detector
measurement in :mod:`grain_guard.analysis.designed_reporter`. Spray policies
here read the field's own pest densities, so they are not detectors and their
numbers are not detection claims: the question is only whether the *domain*
now prices a spray decision at all. If an indiscriminate spray-everything
policy ends no worse than a precise, thresholded policy, then no detector
skill can pay for itself no matter how competent it is.

``ecology_enabled=False`` reproduces the pre-change (uncoupled) domain, so the
same script measures the before and after side of the comparison.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any

from grain_guard.adapter.grain_adapter import SPRAY_EFFICACY, GrainGuardAdapter
from grain_guard.equipment.sprayer_fleet import SprayerFleetConfig

NO_SPRAY = "no_spray"
INDISCRIMINATE = "indiscriminate"
PRECISE = "precise"
SPRAY_POLICIES: tuple[str, ...] = (NO_SPRAY, INDISCRIMINATE, PRECISE)

DEFAULT_SPRAY_INTERVAL = 7
DEFAULT_SPRAY_THRESHOLD = 10.0


@dataclass(frozen=True)
class ResurgenceRun:
    """One policy, one seed, one ecology setting.

    Attributes:
        policy: spray policy label.
        seed: domain seed.
        ecology_enabled: whether the coupled phase-1 ecology was active.
        steps: steps run.
        sprays: spray applications actually applied.
        denied_sprays: applications refused by the spray budget.
        final_primary_density: summed primary-pest density at the last step.
        final_secondary_density: summed secondary-pest density at the last step.
        final_total_density: summed density of every pest species.
        final_beneficial_density: summed natural-enemy density.
        primary_pest_days: mean per-step summed primary density over the run.
        secondary_pest_days: mean per-step summed secondary density over the run.
        total_pest_days: mean per-step summed density of every species.
        peak_total_density: largest per-step summed density seen.
        mean_crop_health: field-mean crop health at the last step.
        final_yield_potential: field-mean yield potential at the last step.
        sprayer_fleet: per-Tot tank metrics, or ``None`` with unlimited capacity.

    Damage in this domain is monotone (``CropCell.apply_damage`` never heals),
    so ``final_yield_potential`` is the integral of the harm a policy allowed,
    while the density fields are a last-step snapshot: a policy that kills the
    crop outright ends with few pests because carrying capacity went with it.
    Read the two together.
    """

    policy: str
    seed: int
    ecology_enabled: bool
    steps: int
    sprays: int
    denied_sprays: int
    final_primary_density: float
    final_secondary_density: float
    final_total_density: float
    final_beneficial_density: float
    primary_pest_days: float
    secondary_pest_days: float
    total_pest_days: float
    peak_total_density: float
    mean_crop_health: float
    final_yield_potential: float
    sprayer_fleet: dict[str, float | int] | None = None


def _spray_targets(
    adapter: GrainGuardAdapter,
    policy: str,
    threshold: float,
) -> list[tuple[int, int]]:
    field = adapter.field
    if policy == NO_SPRAY:
        return []
    if policy == INDISCRIMINATE:
        return [(r, c) for r in range(field.rows) for c in range(field.cols)]
    if policy == PRECISE:
        return [
            (r, c)
            for r in range(field.rows)
            for c in range(field.cols)
            if field.pests[r][c].density > threshold
        ]
    raise ValueError(f"unknown spray policy {policy!r}")


def _apply_spray_policy(
    adapter: GrainGuardAdapter,
    policy: str,
    targets: list[tuple[int, int]],
) -> tuple[int, int]:
    """Spray a policy's targets and report applications applied and refused."""
    if policy == INDISCRIMINATE:
        served = adapter.broadcast_spray(targets)
        return len(served), len(targets) - len(served)
    applied = sum(1 for row, col in targets if adapter.dispatch_spray(row, col))
    return applied, len(targets) - applied


def run_resurgence_arm(
    policy: str,
    seed: int,
    *,
    steps: int = 400,
    ecology_enabled: bool = True,
    spray_interval: int = DEFAULT_SPRAY_INTERVAL,
    spray_threshold: float = DEFAULT_SPRAY_THRESHOLD,
    grid_rows: int = 20,
    grid_cols: int = 20,
    pest_intro_probability: float = 0.02,
    pest_damage_visibility_lag_steps: int | None = None,
    spray_budget_capacity: int | None = None,
    spray_budget_interval_steps: int = 7,
    sprayer_fleet_config: SprayerFleetConfig | None = None,
) -> ResurgenceRun:
    """Run one spray policy against the domain and report its end state.

    With a fleet configured, the indiscriminate policy sprays through the boom
    sprayer, because that is the equipment a whole-field pass actually uses;
    thresholded spraying goes cell by cell through the drone fleet and is the
    policy that finite tanks make scarce.
    """
    if policy not in SPRAY_POLICIES:
        raise ValueError(f"unknown spray policy {policy!r}")
    ecology_config: dict[str, Any] = {"enabled": ecology_enabled}
    if pest_damage_visibility_lag_steps is not None:
        ecology_config["pest_damage_visibility_lag_steps"] = pest_damage_visibility_lag_steps
    spray_budget_config: dict[str, Any] | None = None
    if spray_budget_capacity is not None:
        spray_budget_config = {
            "capacity": spray_budget_capacity,
            "interval_steps": spray_budget_interval_steps,
        }
    adapter = GrainGuardAdapter(
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        seed=seed,
        pest_intro_probability=pest_intro_probability,
        ecology_config=ecology_config,
        spray_budget_config=spray_budget_config,
        sprayer_fleet_config=sprayer_fleet_config,
    )
    sprays = 0
    denied = 0
    primary_trace: list[float] = []
    secondary_trace: list[float] = []
    for step in range(steps):
        adapter.step(step)
        primary_trace.append(adapter.field.total_primary_pest_density())
        secondary_trace.append(adapter.field.total_secondary_pest_density())
        if step % spray_interval != 0:
            continue
        targets = _spray_targets(adapter, policy, spray_threshold)
        applied, refused = _apply_spray_policy(adapter, policy, targets)
        sprays += applied
        denied += refused
    field = adapter.field
    totals = [
        primary + secondary
        for primary, secondary in zip(primary_trace, secondary_trace, strict=True)
    ]
    return ResurgenceRun(
        policy=policy,
        seed=seed,
        ecology_enabled=ecology_enabled,
        steps=steps,
        sprays=sprays,
        denied_sprays=denied,
        final_primary_density=field.total_primary_pest_density(),
        final_secondary_density=field.total_secondary_pest_density(),
        final_total_density=field.total_primary_pest_density()
        + field.total_secondary_pest_density(),
        final_beneficial_density=float(field.biological_control.sum()),
        primary_pest_days=fmean(primary_trace),
        secondary_pest_days=fmean(secondary_trace),
        total_pest_days=fmean(totals),
        peak_total_density=max(totals),
        mean_crop_health=field.mean_crop_health(),
        final_yield_potential=field.mean_yield_potential(),
        sprayer_fleet=adapter.sprayer_fleet_metrics,
    )


def summarize_policy(policy: str, runs: Sequence[ResurgenceRun]) -> dict[str, Any]:
    """Pool one policy's seeds into means."""
    if not runs:
        raise ValueError(f"no seeds recorded for policy {policy!r}")
    return {
        "policy": policy,
        "n_seeds": len(runs),
        "ecology_enabled": runs[0].ecology_enabled,
        "mean_sprays": fmean([float(run.sprays) for run in runs]),
        "mean_denied_sprays": fmean([float(run.denied_sprays) for run in runs]),
        "mean_primary_density": fmean([run.final_primary_density for run in runs]),
        "mean_secondary_density": fmean([run.final_secondary_density for run in runs]),
        "mean_total_density": fmean([run.final_total_density for run in runs]),
        "mean_beneficial_density": fmean([run.final_beneficial_density for run in runs]),
        "mean_primary_pest_days": fmean([run.primary_pest_days for run in runs]),
        "mean_secondary_pest_days": fmean([run.secondary_pest_days for run in runs]),
        "mean_total_pest_days": fmean([run.total_pest_days for run in runs]),
        "mean_peak_total_density": fmean([run.peak_total_density for run in runs]),
        "mean_crop_health": fmean([run.mean_crop_health for run in runs]),
        "mean_yield_potential": fmean([run.final_yield_potential for run in runs]),
        "mean_refills": _fleet_mean(runs, "refills"),
        "mean_spot_granted": _fleet_mean(runs, "spot_granted"),
        "mean_spot_denied_empty": _fleet_mean(runs, "spot_denied_empty"),
        "mean_spot_denied_refilling": _fleet_mean(runs, "spot_denied_refilling"),
        "mean_spot_denied_worked_out": _fleet_mean(runs, "spot_denied_worked_out"),
        "mean_spot_fulfilled_share": _fleet_mean(runs, "spot_fulfilled_share"),
        "mean_liters_applied": _fleet_mean(runs, "liters_applied"),
    }


def _fleet_mean(runs: Sequence[ResurgenceRun], key: str) -> float | None:
    """Mean of one fleet metric, or ``None`` when capacity was unlimited."""
    values = [float(run.sprayer_fleet[key]) for run in runs if run.sprayer_fleet is not None]
    return fmean(values) if values else None


def resurgence_verdict(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Whether spray-everything now ends worse than precise spraying.

    ``resurgence`` is true when indiscriminate spraying leaves strictly lower
    yield than precise spraying *and* strictly more final pests than no spray.
    Requiring both prevents crop collapse from masquerading as pest control:
    damage here is monotone, while the last-step density can fall merely because
    the carrying capacity died. The secondary-pest-day gap is reported beside
    the verdict as the release mechanism.
    """
    by_policy = {summary["policy"]: summary for summary in summaries}
    indiscriminate = by_policy.get(INDISCRIMINATE)
    precise = by_policy.get(PRECISE)
    if indiscriminate is None or precise is None:
        raise ValueError("resurgence verdict needs both the indiscriminate and precise policies")
    density_gap = indiscriminate["mean_total_density"] - precise["mean_total_density"]
    pest_day_gap = indiscriminate["mean_total_pest_days"] - precise["mean_total_pest_days"]
    secondary_gap = indiscriminate["mean_secondary_pest_days"] - precise["mean_secondary_pest_days"]
    yield_gap = indiscriminate["mean_yield_potential"] - precise["mean_yield_potential"]
    baseline = by_policy.get(NO_SPRAY)
    no_spray_yield_gap = (
        indiscriminate["mean_yield_potential"] - baseline["mean_yield_potential"]
        if baseline is not None
        else None
    )
    no_spray_density_gap = (
        indiscriminate["mean_total_density"] - baseline["mean_total_density"]
        if baseline is not None
        else None
    )
    worse_than_no_spray = no_spray_density_gap is not None and no_spray_density_gap > 0.0
    return {
        "indiscriminate_minus_precise_density": density_gap,
        "indiscriminate_minus_precise_pest_days": pest_day_gap,
        "indiscriminate_minus_precise_secondary_pest_days": secondary_gap,
        "indiscriminate_minus_precise_yield": yield_gap,
        "indiscriminate_minus_no_spray_yield": no_spray_yield_gap,
        "indiscriminate_minus_no_spray_density": no_spray_density_gap,
        "resurgence": bool(yield_gap < 0.0 and worse_than_no_spray),
    }


def run_resurgence_experiment(
    seeds: Sequence[int],
    *,
    steps: int = 400,
    ecology_enabled: bool = True,
    spray_interval: int = DEFAULT_SPRAY_INTERVAL,
    spray_threshold: float = DEFAULT_SPRAY_THRESHOLD,
    policies: Sequence[str] = SPRAY_POLICIES,
    pest_damage_visibility_lag_steps: int | None = None,
    spray_budget_capacity: int | None = None,
    spray_budget_interval_steps: int = 7,
    sprayer_fleet_config: SprayerFleetConfig | None = None,
) -> dict[str, Any]:
    """Run every policy over every seed and pool the comparison."""
    runs = [
        run_resurgence_arm(
            policy,
            seed,
            steps=steps,
            ecology_enabled=ecology_enabled,
            spray_interval=spray_interval,
            spray_threshold=spray_threshold,
            pest_damage_visibility_lag_steps=pest_damage_visibility_lag_steps,
            spray_budget_capacity=spray_budget_capacity,
            spray_budget_interval_steps=spray_budget_interval_steps,
            sprayer_fleet_config=sprayer_fleet_config,
        )
        for policy in policies
        for seed in seeds
    ]
    summaries = [
        summarize_policy(policy, [run for run in runs if run.policy == policy])
        for policy in policies
    ]
    return {
        "configuration": {
            "seeds": list(seeds),
            "steps": steps,
            "ecology_enabled": ecology_enabled,
            "pest_damage_visibility_lag_steps": pest_damage_visibility_lag_steps,
            "spray_budget_capacity": spray_budget_capacity,
            "spray_budget_interval_steps": spray_budget_interval_steps,
            "sprayer_fleet": (
                sprayer_fleet_config.model_dump() if sprayer_fleet_config is not None else None
            ),
            "spray_interval": spray_interval,
            "spray_threshold": spray_threshold,
            "spray_efficacy": SPRAY_EFFICACY,
            "policies": list(policies),
        },
        "verdict": resurgence_verdict(summaries),
        "policies": summaries,
        "per_seed": [asdict(run) for run in runs],
    }
