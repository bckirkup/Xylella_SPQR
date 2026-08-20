"""Designed-reporter arms: what detection precision is reachable in this domain.

Every arm measured so far in this domain used evolved agents, so a negative
exploitable margin (best reachable precision minus the domain's own
static-prior null) could not be distinguished from "no arm measured so far was
competent". These arms replace the evolved escalation decision with a
hand-coded, evidence-only reporter, and add an oracle arm as a diagnostic
ceiling, so the two readings separate.

The pest adversary is frozen in every arm here (``freeze_pest_evolution``), so
the detector-side numbers are not confounded by the adversary adapting inside
the same runs. Pest-side gradient metrics are still reported from the same runs
as the reference shape of a working loop in this domain.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from domain_runner.types import RunContext
from tattletots.engine.config import GenePoolConfig, SimulationConfig
from tattletots.engine.dispatch_integration import init_user_cops
from tattletots.engine.relevance import align_user_priorities_to_report_space
from tattletots.engine.world import World
from tattletots.interface.reporter_policy import (
    ReporterDecision,
    ReporterPolicyContext,
    register_reporter_policy,
)
from tattletots.models.genome import Genome
from tattletots.models.location import EventLocation
from tattletots.telemetry.cost_accounting import CostAccumulator
from tattletots.telemetry.payoff_ledger import PayoffLedger

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.analysis.arms import ArmRun, ArmSpec, execute_arm
from grain_guard.analysis.detector_gradient import AgentRecord
from grain_guard.reporter_policy import (
    GRAIN_REPORTER_POLICY_NAME,
    GrainEvidenceReporterPolicy,
)

ORDINARY_ARM = "ordinary"
ALL_DESIGNED_ARM = "all_designed_seed"
INVASION_ARM = "invasion"
ORACLE_ARM = "oracle_upper_bound"
POLICY_ARMS: tuple[str, ...] = (ORDINARY_ARM, ALL_DESIGNED_ARM, INVASION_ARM, ORACLE_ARM)
EVIDENCE_ONLY_ARMS: tuple[str, ...] = (ORDINARY_ARM, ALL_DESIGNED_ARM, INVASION_ARM)
"""Arms a shipped detector could actually be; the oracle arm is diagnostic."""

ORACLE_POLICY_NAME = "grain_oracle_diagnostic_upper_bound"
INVASION_DESIGNED_FRACTION = 0.2
ESCALATION_THRESHOLD_RANGE = (0.05, 0.3)
"""Starting range of the escalation-threshold trait under the reporting levers."""

MIN_SCORED_REPORTS = 20
"""Fewer reports than this in an arm is reported as unscored, not as precision."""

CLAUSE_2_CORRELATION_THRESHOLD = 0.2
"""Parent-child reproductive correlation a seed must exceed to clear clause 2."""


@dataclass
class OracleTruthSource:
    """Harness-local holder for the active oracle ground-truth callable.

    The oracle arm is a diagnostic ceiling, not a detector: it is the only place
    in this measurement where ground truth reaches a reporting decision.
    """

    source: Callable[[], Sequence[EventLocation]] | None = None

    def locations(self) -> tuple[EventLocation, ...]:
        """Currently active event locations, or empty when unbound."""
        return tuple(self.source()) if self.source is not None else ()


_ORACLE_TRUTH = OracleTruthSource()


@dataclass
class OracleDiagnosticPolicy:
    """Report a true active location whenever one exists (diagnostic ceiling).

    Attributes:
        truth: source of currently active event locations.
        decision_steps: reporting decisions taken.
        escalation_steps: decisions that produced a report.
    """

    truth: OracleTruthSource
    decision_steps: int = 0
    escalation_steps: int = 0

    def decide(self, _context: ReporterPolicyContext) -> ReporterDecision:
        """Escalate the lowest-indexed active location, if any."""
        self.decision_steps += 1
        locations = self.truth.locations()
        if not locations:
            return ReporterDecision(escalate=False)
        self.escalation_steps += 1
        return ReporterDecision(escalate=True, location=min(locations))


def _build_oracle_policy() -> OracleDiagnosticPolicy:
    return OracleDiagnosticPolicy(truth=_ORACLE_TRUTH)


register_reporter_policy(ORACLE_POLICY_NAME, _build_oracle_policy)


def policy_assignment(
    policy_arm: str,
    population: int,
    designed_policy_name: str = GRAIN_REPORTER_POLICY_NAME,
) -> tuple[str | None, int]:
    """Reporter policy name and how many initial genomes carry it."""
    if policy_arm == ORDINARY_ARM:
        return None, 0
    if policy_arm == ALL_DESIGNED_ARM:
        return designed_policy_name, population
    if policy_arm == INVASION_ARM:
        seeded = max(1, round(population * INVASION_DESIGNED_FRACTION))
        return designed_policy_name, min(seeded, population)
    if policy_arm == ORACLE_ARM:
        return ORACLE_POLICY_NAME, population
    raise ValueError(f"unknown policy arm {policy_arm!r}")


def make_layer_setup(
    policy_arm: str,
    designed_policy_name: str = GRAIN_REPORTER_POLICY_NAME,
) -> Callable[[GrainGuardAdapter, RunContext], dict[str, Any]]:
    """Layer setup that seeds the initial genomes of one policy arm.

    The same code path builds every arm, including ``ordinary``, so arms differ
    only in which initial genomes carry a reporter policy.
    """

    def setup(adapter: GrainGuardAdapter, run: RunContext) -> dict[str, Any]:
        config = SimulationConfig(**run.simulation_config)
        world = World(
            config=config,
            gene_pool=GenePoolConfig(escalation_threshold_range=ESCALATION_THRESHOLD_RANGE),
        )
        for stream in adapter.get_streams():
            world.add_stream(stream)
        for user in adapter.get_users():
            world.add_user(user)
        world.set_location_inference(adapter.infer_report_location)
        world.set_location_frame(adapter.get_location_frame())

        genomes = [
            Genome.random_genome(
                world.rng,
                n_streams=max(len(world.streams), 1),
                input_preference_slots=config.input_preference_slots,
                n_users=max(len(world.users), 1),
                gene_pool=world.gene_pool,
            )
            for _ in range(config.initial_population)
        ]
        policy_name, seeded = policy_assignment(policy_arm, len(genomes), designed_policy_name)
        if policy_name is not None:
            for index in range(seeded):
                genomes[index] = genomes[index].model_copy(update={"reporter_policy": policy_name})
        world.seed_population(genomes=genomes)
        align_user_priorities_to_report_space(world)
        if policy_arm == ORACLE_ARM:
            _ORACLE_TRUTH.source = lambda: adapter.get_active_locations(world.time_step)
        else:
            _ORACLE_TRUTH.source = None
        return {
            "world": world,
            "sim_config": config,
            "cops": init_user_cops(world, adapter, config),
            "cost_accumulator": CostAccumulator(),
            "steps_completed": 0,
            "designed_seeded": seeded,
        }

    return setup


def designed_evidence_rates(world: World) -> dict[str, float]:
    """Evidence-arrival rates pooled over every designed policy in the run."""
    policies = [
        policy
        for policy in world.reporter_policies.values()
        if isinstance(policy, GrainEvidenceReporterPolicy)
    ]
    decisions = sum(policy.decision_steps for policy in policies)
    if decisions == 0:
        return {"n_designed_policies": float(len(policies)), "decision_steps": 0.0}
    return {
        "n_designed_policies": float(len(policies)),
        "decision_steps": float(decisions),
        "trap_evidence_rate": sum(p.trap_evidence_steps for p in policies) / decisions,
        "drone_evidence_rate": sum(p.drone_evidence_steps for p in policies) / decisions,
        "any_evidence_rate": sum(p.any_evidence_steps for p in policies) / decisions,
        "escalation_rate": sum(p.escalation_steps for p in policies) / decisions,
    }


def oracle_policy_instances(world: World) -> int:
    """Live oracle policies in a world; a ground-truth boundary check.

    Any arm other than ``oracle_upper_bound`` must report zero here: the oracle
    is the only policy in this measurement with access to ground truth.
    """
    return sum(
        1
        for policy in world.reporter_policies.values()
        if isinstance(policy, OracleDiagnosticPolicy)
    )


def _cohort_split(records: Sequence[AgentRecord]) -> dict[str, Any]:
    """Designed and ordinary cohort sizes, reports, and offspring."""
    designed = [r for r in records if r.reporter_policy is not None]
    ordinary = [r for r in records if r.reporter_policy is None]
    return {
        "n_designed_agents": len(designed),
        "n_ordinary_agents": len(ordinary),
        "designed_reports": sum(r.reports_issued for r in designed),
        "designed_correct_reports": sum(r.correct_reports for r in designed),
        "ordinary_reports": sum(r.reports_issued for r in ordinary),
        "ordinary_correct_reports": sum(r.correct_reports for r in ordinary),
        "mean_designed_offspring": fmean([float(r.offspring) for r in designed])
        if designed
        else None,
        "mean_ordinary_offspring": fmean([float(r.offspring) for r in ordinary])
        if ordinary
        else None,
    }


def measure_designed_arm(
    spec: ArmSpec,
    policy_arm: str,
    designed_policy_name: str = GRAIN_REPORTER_POLICY_NAME,
) -> dict[str, Any]:
    """Run one seed of one policy arm and return its per-seed measurements."""
    if policy_arm not in POLICY_ARMS:
        raise ValueError(f"unknown policy arm {policy_arm!r}")
    ledger = PayoffLedger()
    run: ArmRun = execute_arm(
        spec,
        setup=make_layer_setup(policy_arm, designed_policy_name),
        observe=lambda world, _step: ledger.observe(world),
    )
    ledger.finalize(run.world)
    output = run.output
    ecology = output.ecology_metrics
    domain = output.domain_metrics
    instrument = domain["instrument"]
    coupling = ledger.coupling_summary()
    detector = domain["detector_gradient"]
    pest = domain["pest_gradient"]

    return {
        "policy_arm": policy_arm,
        "seed": spec.seed,
        "steps_completed": run.steps_completed,
        "pest_evolution_frozen": run.adapter.pest_evolution_frozen,
        "total_reports": ecology.total_reports,
        "precision": ecology.precision,
        "designed_precision": ecology.designed_precision,
        "ordinary_precision": ecology.ordinary_precision,
        "designed_population_share": ecology.designed_population_share,
        "final_population": ecology.final_population,
        "static_prior_null": instrument["static_prior_null"],
        "uniform_null": instrument["uniform_null"],
        "inferability_precision": instrument["inferability_precision"],
        "decoder_precision": instrument["decoder_precision"],
        "static_prior_null_engine": domain["static_prior_null_engine"],
        "grounded_yield_share": domain["grounded_yield_share"],
        "effective_grounded_yield_share": domain["effective_grounded_yield_share"],
        "attention_solvency": domain["attention_solvency"],
        "reports_per_adult_lifetime": coupling.get("mean_reports_per_adult"),
        "n_adults": coupling.get("n_adults"),
        "silent_adult_share": coupling.get("silent_adult_share"),
        "reproduction_correctness_weight": spec.reproduction_correctness_weight,
        **_clause_measurements(coupling),
        "detector_parent_child_reproductive_correlation": detector.get(
            "parent_child_reproductive_correlation"
        ),
        "detector_function_selection_differential": domain[
            "detector_function_selection_differential"
        ],
        "pest_parent_child_reproductive_correlation": pest.get(
            "parent_child_reproductive_correlation"
        ),
        "pest_selection_differential": pest.get("selection_differential"),
        "spray_budget": run.adapter.spray_budget_metrics,
        "sprayer_fleet": run.adapter.sprayer_fleet_metrics,
        "spray_weather": run.adapter.spray_weather_metrics,
        "evidence_rates": designed_evidence_rates(run.world),
        "oracle_policy_instances": oracle_policy_instances(run.world),
        "cohorts": _cohort_split(list(run.tracker.records.values())),
    }


def _clause_measurements(coupling: dict[str, Any]) -> dict[str, Any]:
    """The two falsification clauses and the cap that rations reproduction.

    Both clauses are read off the engine's own ``PayoffLedger``: clause 1 is the
    within-run regression slope of correct-report rate over agent generations at
    fixed initial parameters, clause 2 is the parent-child correlation in
    offspring count. ``population_capped_step_share`` is reported next to them
    because a cap that rarely binds leaves a reproduction ordering with almost
    nothing to ration.
    """
    gate = coupling.get("reproduction_gate", {})
    return {
        "clause_1_precision_generation_slope": coupling.get("precision_generation_slope"),
        "generations_observed": coupling.get("generations_observed"),
        "clause_2_parent_child_offspring_correlation": coupling.get("corr_parent_child_offspring"),
        "n_parent_child_pairs": coupling.get("n_parent_child_pairs"),
        "population_capped_step_share": gate.get("population_capped_step_share"),
        "reproduction_eligible_share": gate.get("eligible_share"),
    }


def _count_where(records: Sequence[dict[str, Any]], key: str, threshold: float) -> int:
    """Seeds whose value for ``key`` is present and strictly above ``threshold``."""
    return sum(
        1
        for record in records
        if isinstance(record.get(key), (int, float)) and float(record[key]) > threshold
    )


def _mean_of(records: Sequence[dict[str, Any]], key: str) -> float | None:
    values = [
        float(record[key])
        for record in records
        if record.get(key) is not None and isinstance(record[key], (int, float))
    ]
    return fmean(values) if values else None


def _nested_mean(records: Sequence[dict[str, Any]], outer: str, key: str) -> float | None:
    values = [
        float(record[outer][key])
        for record in records
        if isinstance(record.get(outer), dict) and record[outer].get(key) is not None
    ]
    return fmean(values) if values else None


def _pooled_precision(
    records: Sequence[dict[str, Any]], reports: str, correct: str
) -> float | None:
    total = sum(int(record["cohorts"][reports]) for record in records)
    if total <= 0:
        return None
    return sum(int(record["cohorts"][correct]) for record in records) / total


def summarize_policy_arm(policy_arm: str, records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Pool one policy arm's per-seed records into a single arm summary."""
    if not records:
        raise ValueError(f"no seeds recorded for policy arm {policy_arm!r}")
    total_reports = sum(int(record["total_reports"]) for record in records)
    designed_reports = sum(int(record["cohorts"]["designed_reports"]) for record in records)
    ordinary_reports = sum(int(record["cohorts"]["ordinary_reports"]) for record in records)
    designed_precision = _pooled_precision(records, "designed_reports", "designed_correct_reports")
    ordinary_precision = _pooled_precision(records, "ordinary_reports", "ordinary_correct_reports")
    reporting_precision = (
        designed_precision
        if policy_arm != ORDINARY_ARM and designed_precision is not None
        else ordinary_precision
    )
    return {
        "policy_arm": policy_arm,
        "n_seeds": len(records),
        "total_reports": total_reports,
        "designed_reports": designed_reports,
        "ordinary_reports": ordinary_reports,
        "reporting_precision": reporting_precision,
        "designed_precision": designed_precision,
        "ordinary_precision": ordinary_precision,
        "scored": _scoring_reports(policy_arm, designed_reports, ordinary_reports)
        >= MIN_SCORED_REPORTS,
        "scoring_reports": _scoring_reports(policy_arm, designed_reports, ordinary_reports),
        "mean_static_prior_null": _mean_of(records, "static_prior_null"),
        "mean_uniform_null": _mean_of(records, "uniform_null"),
        "mean_inferability_precision": _mean_of(records, "inferability_precision"),
        "mean_decoder_precision": _mean_of(records, "decoder_precision"),
        "mean_reports_per_adult_lifetime": _mean_of(records, "reports_per_adult_lifetime"),
        "mean_silent_adult_share": _mean_of(records, "silent_adult_share"),
        "mean_population_capped_step_share": _mean_of(records, "population_capped_step_share"),
        "mean_reproduction_eligible_share": _mean_of(records, "reproduction_eligible_share"),
        "mean_clause_1_slope": _mean_of(records, "clause_1_precision_generation_slope"),
        "n_seeds_clause_1_rising": _count_where(
            records, "clause_1_precision_generation_slope", 0.0
        ),
        "mean_generations_observed": _mean_of(records, "generations_observed"),
        "mean_clause_2_correlation": _mean_of(
            records, "clause_2_parent_child_offspring_correlation"
        ),
        "n_seeds_clause_2_cleared": _count_where(
            records,
            "clause_2_parent_child_offspring_correlation",
            CLAUSE_2_CORRELATION_THRESHOLD,
        ),
        "reproduction_correctness_weights": sorted(
            {
                float(record["reproduction_correctness_weight"])
                for record in records
                if record.get("reproduction_correctness_weight") is not None
            }
        ),
        "mean_designed_population_share": _mean_of(records, "designed_population_share"),
        "mean_final_population": _mean_of(records, "final_population"),
        "n_extinct_seeds": sum(1 for record in records if int(record["final_population"]) == 0),
        "mean_grounded_yield_share": _mean_of(records, "grounded_yield_share"),
        "mean_effective_grounded_yield_share": _mean_of(records, "effective_grounded_yield_share"),
        "mean_attention_solvent_share": _nested_mean(
            records, "attention_solvency", "mean_attention_solvent_share"
        ),
        "mean_attention_capacity_per_capita": _nested_mean(
            records, "attention_solvency", "mean_attention_capacity_per_capita"
        ),
        "mean_spray_attempts": _nested_mean(records, "spray_budget", "attempts"),
        "mean_sprays_applied": _nested_mean(records, "spray_budget", "applied"),
        "mean_sprays_denied": _nested_mean(records, "spray_budget", "denied"),
        "mean_spot_granted": _nested_mean(records, "sprayer_fleet", "spot_granted"),
        "mean_spot_denied_empty": _nested_mean(records, "sprayer_fleet", "spot_denied_empty"),
        "mean_spot_denied_refilling": _nested_mean(
            records, "sprayer_fleet", "spot_denied_refilling"
        ),
        "mean_spot_denied_worked_out": _nested_mean(
            records, "sprayer_fleet", "spot_denied_worked_out"
        ),
        "mean_spot_fulfilled_share": _nested_mean(records, "sprayer_fleet", "spot_fulfilled_share"),
        "mean_tank_refills": _nested_mean(records, "sprayer_fleet", "refills"),
        "mean_liters_applied": _nested_mean(records, "sprayer_fleet", "liters_applied"),
        "mean_weather_requests": _nested_mean(records, "spray_weather", "requests"),
        "mean_weather_wind_blocked": _nested_mean(records, "spray_weather", "wind_blocked"),
        "mean_weather_rain_blocked": _nested_mean(records, "spray_weather", "rain_blocked"),
        "mean_weather_allowed": _nested_mean(records, "spray_weather", "allowed"),
        "mean_weather_washed": _nested_mean(records, "spray_weather", "washed"),
        "mean_weather_retained_efficacy": _nested_mean(
            records, "spray_weather", "mean_retained_efficacy"
        ),
        "mean_weather_allowed_share": _nested_mean(records, "spray_weather", "allowed_share"),
        "mean_any_evidence_rate": _nested_mean(records, "evidence_rates", "any_evidence_rate"),
        "mean_trap_evidence_rate": _nested_mean(records, "evidence_rates", "trap_evidence_rate"),
        "mean_drone_evidence_rate": _nested_mean(records, "evidence_rates", "drone_evidence_rate"),
        "mean_designed_escalation_rate": _nested_mean(records, "evidence_rates", "escalation_rate"),
        "mean_detector_parent_child_reproductive_correlation": _mean_of(
            records, "detector_parent_child_reproductive_correlation"
        ),
        "mean_detector_function_selection_differential": _mean_of(
            records, "detector_function_selection_differential"
        ),
        "mean_pest_parent_child_reproductive_correlation": _mean_of(
            records, "pest_parent_child_reproductive_correlation"
        ),
        "mean_pest_selection_differential": _mean_of(records, "pest_selection_differential"),
        "all_seeds_pest_frozen": all(bool(record["pest_evolution_frozen"]) for record in records),
    }


def _scoring_reports(policy_arm: str, designed_reports: int, ordinary_reports: int) -> int:
    """Reports the arm's headline precision is computed from."""
    if policy_arm == ORDINARY_ARM:
        return ordinary_reports
    return designed_reports


def exploitable_margin(summaries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Best reachable precision minus the domain's own static-prior null.

    Only scored, evidence-only arms can set the reachable precision; the oracle
    arm is reported separately as a diagnostic ceiling.
    """
    nulls = [
        float(summary["mean_static_prior_null"])
        for summary in summaries
        if summary["mean_static_prior_null"] is not None
    ]
    static_prior_null = fmean(nulls) if nulls else None
    eligible = [
        summary
        for summary in summaries
        if summary["policy_arm"] in EVIDENCE_ONLY_ARMS
        and summary["scored"]
        and summary["reporting_precision"] is not None
    ]
    best = max(eligible, key=lambda s: float(s["reporting_precision"])) if eligible else None
    oracle = next(
        (
            summary
            for summary in summaries
            if summary["policy_arm"] == ORACLE_ARM
            and summary["scored"]
            and summary["reporting_precision"] is not None
        ),
        None,
    )
    ordinary = next(
        (summary for summary in summaries if summary["policy_arm"] == ORDINARY_ARM), None
    )
    best_precision = float(best["reporting_precision"]) if best is not None else None
    oracle_precision = float(oracle["reporting_precision"]) if oracle is not None else None
    ordinary_precision = (
        float(ordinary["reporting_precision"])
        if ordinary is not None
        and ordinary["scored"]
        and ordinary["reporting_precision"] is not None
        else None
    )
    return {
        "static_prior_null": static_prior_null,
        "best_arm": best["policy_arm"] if best is not None else None,
        "best_reachable_precision": best_precision,
        "exploitable_margin_pp": _margin_pp(best_precision, static_prior_null),
        "exploitable_margin_positive": _is_positive(_margin_pp(best_precision, static_prior_null)),
        "oracle_precision": oracle_precision,
        "oracle_margin_pp": _margin_pp(oracle_precision, static_prior_null),
        "ordinary_precision": ordinary_precision,
        "ordinary_margin_pp": _margin_pp(ordinary_precision, static_prior_null),
        "unscored_arms": [summary["policy_arm"] for summary in summaries if not summary["scored"]],
    }


def _margin_pp(precision: float | None, null: float | None) -> float | None:
    if precision is None or null is None:
        return None
    return (precision - null) * 100.0


def _is_positive(margin_pp: float | None) -> bool | None:
    return None if margin_pp is None else margin_pp > 0.0
