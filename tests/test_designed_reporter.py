"""Tests for the designed (evidence-only) reporter and its measurement."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from tattletots.interface.reporter_policy import (
    ReporterMetadata,
    ReporterPolicyContext,
    ReporterStream,
    create_reporter_policy,
    register_reporter_policy,
)

import grain_guard.reporter_policy
from grain_guard.analysis.arms import ArmSpec, domain_config, simulation_config
from grain_guard.analysis.designed_reporter import (
    ALL_DESIGNED_ARM,
    CLAUSE_2_CORRELATION_THRESHOLD,
    INVASION_ARM,
    MIN_SCORED_REPORTS,
    ORACLE_ARM,
    ORACLE_POLICY_NAME,
    ORDINARY_ARM,
    OracleDiagnosticPolicy,
    OracleTruthSource,
    exploitable_margin,
    measure_designed_arm,
    policy_assignment,
    summarize_policy_arm,
)
from grain_guard.reporter_policy import (
    DRONE_STREAM_LABEL,
    GRAIN_REPORTER_POLICY_NAME,
    TRAP_STREAM_LABEL,
    GrainEvidenceReporterPolicy,
)

TRAP_COORDINATES = ((2.0, 3.0), (2.0, 3.0), (7.0, 11.0), (7.0, 11.0))
TRAP_MODALITY = ("catch_count", "resistance_proxy", "catch_count", "resistance_proxy")


def _trap_stream(
    catches: tuple[float, float],
    *,
    status: str = "observed",
) -> ReporterStream:
    data = np.array([catches[0], 0.4, catches[1], 0.4], dtype=np.float64)
    return ReporterStream(
        label=TRAP_STREAM_LABEL,
        data=data,
        observation_status=(status,) * 4,
        metadata=ReporterMetadata(coordinates=TRAP_COORDINATES, modality=TRAP_MODALITY),
    )


def _drone_stream(
    pest_signal: float,
    coordinate: tuple[float, float] | None = (5.0, 5.0),
) -> ReporterStream:
    return ReporterStream(
        label=DRONE_STREAM_LABEL,
        data=np.array([pest_signal, 0.1, 0.2, 0.3], dtype=np.float64),
        observation_status=("observed",) * 4,
        metadata=ReporterMetadata(
            coordinates=(coordinate, None, None, None),
            modality=("pest_detection", "weed_detection", "crop_stress", "thermal_detection"),
        ),
    )


def _weather_stream() -> ReporterStream:
    return ReporterStream(
        label="weather_stations",
        data=np.array([25.0, 0.6], dtype=np.float64),
        observation_status=("observed", "observed"),
        metadata=ReporterMetadata(
            coordinates=((1.0, 1.0), (1.0, 1.0)), modality=("temperature", "humidity")
        ),
    )


def _context(*streams: ReporterStream, step: int = 0) -> ReporterPolicyContext:
    observation = np.concatenate([stream.data for stream in streams]) if streams else np.zeros(1)
    return ReporterPolicyContext(
        observation=observation,
        signal_vector=observation,
        anomaly_score=0.5,
        escalation_threshold=0.2,
        time_step=step,
        location_frame=((0, 0), (19, 19)),
        streams=streams,
    )


def _catch_ladder() -> tuple[float, ...]:
    """Trap catch counts spanning below to well above any tested threshold."""
    return (0.0, 0.6, 1.5, 3.0, 6.0, 12.0, 30.0)


class TestDesignedReporterSensitivity:
    @pytest.mark.parametrize("threshold", [1.0, 5.0, 10.0, 20.0, 60.0])
    def test_escalations_are_bounded_by_decisions(self, threshold: float) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=threshold)
        for catch in _catch_ladder():
            policy.decide(_context(_trap_stream((catch, 0.0))))
        assert policy.decision_steps == len(_catch_ladder())
        assert 0 <= policy.escalation_steps <= policy.decision_steps

    def test_raising_the_threshold_never_adds_reports(self) -> None:
        counts = []
        for threshold in (1.0, 5.0, 10.0, 20.0, 60.0):
            policy = GrainEvidenceReporterPolicy(threshold_density=threshold)
            for catch in _catch_ladder():
                policy.decide(_context(_trap_stream((catch, 0.0))))
            counts.append(policy.escalation_steps)
        assert counts == sorted(counts, reverse=True)
        assert counts[0] > counts[-1]

    def test_stronger_evidence_reports_at_least_as_often(self) -> None:
        counts = []
        for catch in (0.0, 1.0, 3.0, 9.0, 27.0):
            policy = GrainEvidenceReporterPolicy(threshold_density=10.0)
            for _ in range(4):
                policy.decide(_context(_trap_stream((catch, 0.0))))
            counts.append(policy.escalation_steps)
        assert counts == sorted(counts)
        assert counts[0] == 0
        assert counts[-1] == 4

    def test_reports_the_coordinate_of_the_strongest_reading(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=10.0)
        weak_then_strong = policy.decide(_context(_trap_stream((4.0, 40.0))))
        strong_then_weak = policy.decide(_context(_trap_stream((40.0, 4.0))))
        assert weak_then_strong.escalate
        assert weak_then_strong.location == (7, 11)
        assert strong_then_weak.location == (2, 3)

    def test_drone_and_trap_evidence_are_counted_separately(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=10.0)
        policy.decide(_context(_trap_stream((30.0, 0.0)), _drone_stream(12.0)))
        rates = policy.evidence_rates()
        assert rates["trap_evidence_rate"] == pytest.approx(1.0)
        assert rates["drone_evidence_rate"] == pytest.approx(1.0)
        assert all(0.0 <= rates[key] <= 1.0 for key in rates if key.endswith("rate"))
        assert all(math.isfinite(value) for value in rates.values())


class TestDesignedReporterNegativeControls:
    def test_no_evidence_streams_never_reports(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=0.0)
        for step in range(5):
            assert not policy.decide(_context(_weather_stream(), step=step)).escalate
        assert policy.decision_steps == 5
        assert policy.any_evidence_steps == 0
        assert policy.evidence_rates()["any_evidence_rate"] == pytest.approx(0.0)

    def test_unobserved_readings_are_not_evidence(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=1.0)
        decision = policy.decide(_context(_trap_stream((99.0, 99.0), status="stale")))
        assert not decision.escalate
        assert policy.any_evidence_steps == 0

    def test_non_finite_readings_are_ignored(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=1.0)
        stream = _trap_stream((float("nan"), float("inf")))
        assert not policy.decide(_context(stream)).escalate

    def test_missing_coordinates_block_reporting(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=1.0)
        assert not policy.decide(_context(_drone_stream(50.0, coordinate=None))).escalate

    def test_locations_outside_the_frame_are_not_reported(self) -> None:
        policy = GrainEvidenceReporterPolicy(threshold_density=1.0)
        stream = _trap_stream((50.0, 0.0))
        out_of_frame = ReporterPolicyContext(
            observation=stream.data,
            signal_vector=stream.data,
            anomaly_score=0.5,
            escalation_threshold=0.2,
            time_step=0,
            location_frame=((0, 0), (1, 1)),
            streams=(stream,),
        )
        assert not policy.decide(out_of_frame).escalate

    def test_registered_factory_builds_the_designed_policy(self) -> None:
        policy = create_reporter_policy(GRAIN_REPORTER_POLICY_NAME)
        assert isinstance(policy, GrainEvidenceReporterPolicy)


class TestOracleArm:
    def test_oracle_reports_only_when_truth_is_active(self) -> None:
        truth = OracleTruthSource()
        policy = OracleDiagnosticPolicy(truth=truth)
        assert not policy.decide(_context(_weather_stream())).escalate
        truth.source = lambda: [(4, 9), (1, 2)]
        decision = policy.decide(_context(_weather_stream()))
        assert decision.escalate
        assert decision.location == (1, 2)
        assert policy.escalation_steps == 1
        assert policy.decision_steps == 2

    def test_registered_oracle_factory_is_a_diagnostic_policy(self) -> None:
        assert isinstance(create_reporter_policy(ORACLE_POLICY_NAME), OracleDiagnosticPolicy)


class TestPolicyAssignment:
    def test_arms_seed_the_expected_number_of_designed_genomes(self) -> None:
        assert policy_assignment(ORDINARY_ARM, 30) == (None, 0)
        assert policy_assignment(ALL_DESIGNED_ARM, 30) == (GRAIN_REPORTER_POLICY_NAME, 30)
        assert policy_assignment(ORACLE_ARM, 30) == (ORACLE_POLICY_NAME, 30)
        name, seeded = policy_assignment(INVASION_ARM, 30)
        assert name == GRAIN_REPORTER_POLICY_NAME
        assert 0 < seeded < 30

    @pytest.mark.parametrize("population", [2, 5, 30, 80])
    def test_invasion_stays_a_minority_at_every_population(self, population: int) -> None:
        _, seeded = policy_assignment(INVASION_ARM, population)
        assert 1 <= seeded <= population // 2

    def test_unknown_arm_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown policy arm"):
            policy_assignment("subsidised", 10)


def _record(
    policy_arm: str,
    *,
    seed: int,
    designed_reports: int,
    designed_correct: int,
    ordinary_reports: int = 100,
    ordinary_correct: int = 50,
    static_prior_null: float = 0.5,
    clause_1_slope: float = 0.001,
    clause_2_correlation: float = 0.05,
) -> dict[str, Any]:
    return {
        "policy_arm": policy_arm,
        "seed": seed,
        "reproduction_correctness_weight": 1.0,
        "silent_adult_share": 0.1,
        "clause_1_precision_generation_slope": clause_1_slope,
        "generations_observed": 6,
        "clause_2_parent_child_offspring_correlation": clause_2_correlation,
        "n_parent_child_pairs": 120,
        "population_capped_step_share": 0.8,
        "reproduction_eligible_share": 0.7,
        "total_reports": designed_reports + ordinary_reports,
        "precision": 0.5,
        "designed_precision": 0.0,
        "ordinary_precision": 0.0,
        "designed_population_share": 0.5,
        "final_population": 40,
        "static_prior_null": static_prior_null,
        "uniform_null": 0.0025,
        "inferability_precision": 0.8,
        "decoder_precision": 0.6,
        "grounded_yield_share": 1.0,
        "effective_grounded_yield_share": 1.0,
        "attention_solvency": {"mean_attention_solvent_share": 0.5},
        "reports_per_adult_lifetime": 4.0,
        "detector_parent_child_reproductive_correlation": 0.05,
        "detector_function_selection_differential": 0.01,
        "pest_parent_child_reproductive_correlation": 0.21,
        "pest_selection_differential": 0.02,
        "pest_evolution_frozen": True,
        "evidence_rates": {"any_evidence_rate": 0.93, "escalation_rate": 0.5},
        "cohorts": {
            "designed_reports": designed_reports,
            "designed_correct_reports": designed_correct,
            "ordinary_reports": ordinary_reports,
            "ordinary_correct_reports": ordinary_correct,
        },
    }


class TestSummaries:
    def test_pooled_precision_follows_the_seeded_correct_share(self) -> None:
        precisions = []
        for correct_share in (0.1, 0.3, 0.6, 0.9):
            records = [
                _record(
                    ALL_DESIGNED_ARM,
                    seed=seed,
                    designed_reports=100,
                    designed_correct=int(100 * correct_share),
                )
                for seed in range(3)
            ]
            summary = summarize_policy_arm(ALL_DESIGNED_ARM, records)
            precisions.append(summary["reporting_precision"])
            assert 0.0 <= summary["reporting_precision"] <= 1.0
        assert precisions == sorted(precisions)
        assert precisions[-1] > precisions[0]

    def test_ordinary_arm_is_scored_on_ordinary_reports(self) -> None:
        records = [
            _record(
                ORDINARY_ARM,
                seed=seed,
                designed_reports=0,
                designed_correct=0,
                ordinary_reports=50,
                ordinary_correct=10,
            )
            for seed in range(4)
        ]
        summary = summarize_policy_arm(ORDINARY_ARM, records)
        assert summary["reporting_precision"] == pytest.approx(0.2)
        assert summary["scoring_reports"] == 200
        assert summary["scored"]

    def test_too_few_reports_is_unscored_rather_than_low_precision(self) -> None:
        records = [
            _record(
                ALL_DESIGNED_ARM,
                seed=0,
                designed_reports=MIN_SCORED_REPORTS - 1,
                designed_correct=0,
            )
        ]
        summary = summarize_policy_arm(ALL_DESIGNED_ARM, records)
        assert not summary["scored"]

    def test_summary_requires_at_least_one_seed(self) -> None:
        with pytest.raises(ValueError, match="no seeds recorded"):
            summarize_policy_arm(ALL_DESIGNED_ARM, [])


class TestDamageLagConfigPlumbing:
    def _spec(self, lag_steps: int | None) -> ArmSpec:
        return ArmSpec(
            name="damage_lag",
            grounded_input_fraction=0.67,
            seed=5,
            pest_damage_visibility_lag_steps=lag_steps,
        )

    def test_omitted_lag_keeps_the_domain_default(self) -> None:
        ecology = domain_config(self._spec(None))["ecology_config"]
        assert ecology == {"enabled": True}

    @pytest.mark.parametrize("lag_steps", [0, 1, 3, 10])
    def test_lag_reaches_the_domain_config_unchanged(self, lag_steps: int) -> None:
        ecology = domain_config(self._spec(lag_steps))["ecology_config"]
        assert ecology["pest_damage_visibility_lag_steps"] == lag_steps

    def test_lag_is_the_only_difference_between_measurement_arms(self) -> None:
        control = domain_config(self._spec(0))
        treatment = domain_config(self._spec(3))
        changed = {key for key in control if control[key] != treatment[key]}
        assert changed == {"ecology_config"}
        control_ecology = control["ecology_config"]
        treatment_ecology = treatment["ecology_config"]
        ecology_changed = {
            key
            for key in control_ecology | treatment_ecology
            if control_ecology.get(key) != treatment_ecology.get(key)
        }
        assert ecology_changed == {"pest_damage_visibility_lag_steps"}


class TestResponseGateConfig:
    """The response gate is config-gated, default off, and nothing else moves."""

    def _spec(self, **kwargs: Any) -> ArmSpec:
        return ArmSpec(name="gate", grounded_input_fraction=0.67, seed=5, steps=25, **kwargs)

    def test_default_arm_leaves_the_gate_closed(self) -> None:
        assert self._spec().reproduction_correctness_weight == pytest.approx(0.0)
        levered = simulation_config(self._spec(reporting_levers=True))
        assert levered["reproduction_correctness_weight"] == pytest.approx(0.0)
        assert levered["reproduction_merit_ordering"] is True

    @pytest.mark.parametrize("weight", [0.0, 0.25, 0.5, 1.0])
    def test_weight_reaches_the_engine_config_unchanged(self, weight: float) -> None:
        config = simulation_config(
            self._spec(reporting_levers=True, reproduction_correctness_weight=weight)
        )
        assert config["reproduction_correctness_weight"] == pytest.approx(weight)

    def test_the_weight_is_the_only_difference_between_arms(self) -> None:
        control = simulation_config(self._spec(reporting_levers=True))
        treatment = simulation_config(
            self._spec(reporting_levers=True, reproduction_correctness_weight=1.0)
        )
        differing = {key for key in control | treatment if control.get(key) != treatment.get(key)}
        assert differing == {"reproduction_correctness_weight"}

    def test_without_the_levers_the_engine_keeps_its_own_default(self) -> None:
        config = simulation_config(self._spec(reproduction_correctness_weight=1.0))
        assert "reproduction_correctness_weight" not in config
        assert "reproduction_merit_ordering" not in config


class TestClauseSummaries:
    """Rising-seed and cleared-seed counts follow the per-seed values."""

    def _summary(self, slopes: list[float], correlations: list[float]) -> dict[str, Any]:
        records = [
            _record(
                ORDINARY_ARM,
                seed=seed,
                designed_reports=0,
                designed_correct=0,
                clause_1_slope=slope,
                clause_2_correlation=correlation,
            )
            for seed, (slope, correlation) in enumerate(zip(slopes, correlations, strict=True))
        ]
        return summarize_policy_arm(ORDINARY_ARM, records)

    @pytest.mark.parametrize(
        ("slopes", "expected_rising"),
        [
            ([-0.01, -0.02, -0.03, -0.04], 0),
            ([-0.01, 0.0, 0.002, 0.004], 2),
            ([0.001, 0.002, 0.003, 0.004], 4),
        ],
    )
    def test_rising_seed_count_tracks_the_slopes(
        self, slopes: list[float], expected_rising: int
    ) -> None:
        summary = self._summary(slopes, [0.0] * len(slopes))
        assert summary["n_seeds_clause_1_rising"] == expected_rising
        assert summary["mean_clause_1_slope"] == pytest.approx(sum(slopes) / len(slopes))

    @pytest.mark.parametrize(
        ("correlations", "expected_cleared"),
        [
            ([0.0, 0.1, 0.19, -0.3], 0),
            ([0.0, 0.21, 0.4, 0.19], 2),
            ([0.25, 0.3, 0.35, 0.4], 4),
        ],
    )
    def test_cleared_seed_count_tracks_the_threshold(
        self, correlations: list[float], expected_cleared: int
    ) -> None:
        summary = self._summary([0.0] * len(correlations), correlations)
        assert summary["n_seeds_clause_2_cleared"] == expected_cleared
        assert summary["mean_clause_2_correlation"] == pytest.approx(
            sum(correlations) / len(correlations)
        )

    def test_a_seed_exactly_at_the_threshold_does_not_clear_it(self) -> None:
        summary = self._summary([0.0], [CLAUSE_2_CORRELATION_THRESHOLD])
        assert summary["n_seeds_clause_2_cleared"] == 0

    def test_swept_weights_are_recorded_on_the_arm(self) -> None:
        summary = self._summary([0.0, 0.0], [0.0, 0.0])
        assert summary["reproduction_correctness_weights"] == [1.0]


class TestExploitableMargin:
    def _summaries(self, designed_correct: int) -> list[dict[str, Any]]:
        return [
            summarize_policy_arm(
                ORDINARY_ARM,
                [
                    _record(
                        ORDINARY_ARM,
                        seed=0,
                        designed_reports=0,
                        designed_correct=0,
                        ordinary_reports=100,
                        ordinary_correct=40,
                    )
                ],
            ),
            summarize_policy_arm(
                ALL_DESIGNED_ARM,
                [
                    _record(
                        ALL_DESIGNED_ARM,
                        seed=0,
                        designed_reports=100,
                        designed_correct=designed_correct,
                    )
                ],
            ),
            summarize_policy_arm(
                ORACLE_ARM,
                [_record(ORACLE_ARM, seed=0, designed_reports=100, designed_correct=100)],
            ),
        ]

    @pytest.mark.parametrize("designed_correct", [20, 50, 70, 95])
    def test_margin_is_finite_and_tracks_precision(self, designed_correct: int) -> None:
        margin = exploitable_margin(self._summaries(designed_correct))
        assert margin["static_prior_null"] == pytest.approx(0.5)
        assert math.isfinite(float(margin["exploitable_margin_pp"]))
        assert -100.0 <= float(margin["exploitable_margin_pp"]) <= 100.0

    def test_margin_sign_and_ordering_follow_the_null(self) -> None:
        margins = [
            float(exploitable_margin(self._summaries(correct))["exploitable_margin_pp"])
            for correct in (20, 50, 70, 95)
        ]
        assert margins == sorted(margins)
        assert margins[0] < 0.0 < margins[-1]

    def test_best_arm_excludes_the_oracle_and_reports_it_separately(self) -> None:
        margin = exploitable_margin(self._summaries(70))
        assert margin["best_arm"] == ALL_DESIGNED_ARM
        assert margin["best_reachable_precision"] == pytest.approx(0.7)
        assert margin["oracle_precision"] == pytest.approx(1.0)
        assert margin["oracle_margin_pp"] == pytest.approx(50.0)
        assert margin["ordinary_precision"] == pytest.approx(0.4)
        assert margin["ordinary_margin_pp"] == pytest.approx(-10.0)

    def test_unscored_arms_cannot_set_the_reachable_precision(self) -> None:
        summaries = self._summaries(95)
        summaries[1]["scored"] = False
        margin = exploitable_margin(summaries)
        assert margin["best_arm"] == ORDINARY_ARM
        assert ALL_DESIGNED_ARM in margin["unscored_arms"]


class TestMeasuredArms:
    """Short end-to-end runs: the arms wire up and stay inside their bounds."""

    def _spec(self, seed: int = 7) -> ArmSpec:
        return ArmSpec(
            name="designed_test",
            grounded_input_fraction=0.67,
            seed=seed,
            steps=25,
            freeze_pest_evolution=True,
            reporting_levers=True,
        )

    def test_designed_arm_reads_evidence_and_stays_in_bounds(self) -> None:
        record = measure_designed_arm(self._spec(), ALL_DESIGNED_ARM)
        assert record["pest_evolution_frozen"]
        assert record["cohorts"]["designed_reports"] > 0
        assert record["cohorts"]["ordinary_reports"] == 0
        rates = record["evidence_rates"]
        assert rates["decision_steps"] > 0
        assert 0.0 < rates["any_evidence_rate"] <= 1.0
        assert 0.0 <= record["designed_precision"] <= 1.0
        assert 0.0 <= record["static_prior_null"] <= 1.0
        assert math.isfinite(float(record["reports_per_adult_lifetime"]))

    def test_ordinary_arm_seeds_no_designed_agents(self) -> None:
        record = measure_designed_arm(self._spec(), ORDINARY_ARM)
        assert record["cohorts"]["designed_reports"] == 0
        assert record["cohorts"]["n_designed_agents"] == 0
        assert record["evidence_rates"]["decision_steps"] == pytest.approx(0.0)
        assert 0.0 <= record["ordinary_precision"] <= 1.0

    @pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
    def test_clause_metrics_stay_inside_their_bounds(self, weight: float) -> None:
        spec = ArmSpec(
            name="designed_test",
            grounded_input_fraction=0.67,
            seed=7,
            steps=25,
            reporting_levers=True,
            reproduction_correctness_weight=weight,
        )
        record = measure_designed_arm(spec, ORDINARY_ARM)
        assert record["reproduction_correctness_weight"] == pytest.approx(weight)
        assert math.isfinite(float(record["clause_1_precision_generation_slope"]))
        assert -1.0 <= float(record["clause_2_parent_child_offspring_correlation"]) <= 1.0
        assert 0.0 <= float(record["population_capped_step_share"]) <= 1.0
        assert 0.0 <= float(record["reproduction_eligible_share"]) <= 1.0
        assert 0.0 <= float(record["silent_adult_share"]) <= 1.0
        assert int(record["generations_observed"]) >= 1
        assert int(record["n_parent_child_pairs"]) >= 0

    def test_invasion_arm_seeds_a_designed_minority(self) -> None:
        record = measure_designed_arm(self._spec(), INVASION_ARM)
        cohorts = record["cohorts"]
        assert cohorts["n_designed_agents"] > 0
        assert cohorts["n_ordinary_agents"] > cohorts["n_designed_agents"]
        assert 0.0 <= record["designed_population_share"] <= 1.0

    def test_unknown_arm_is_rejected_before_running(self) -> None:
        with pytest.raises(ValueError, match="unknown policy arm"):
            measure_designed_arm(self._spec(), "population_floor")

    def test_only_the_oracle_arm_holds_a_ground_truth_policy(self) -> None:
        for arm in (ORDINARY_ARM, ALL_DESIGNED_ARM, INVASION_ARM):
            assert measure_designed_arm(self._spec(), arm)["oracle_policy_instances"] == 0
        assert measure_designed_arm(self._spec(), ORACLE_ARM)["oracle_policy_instances"] > 0


ZERO_THRESHOLD_POLICY_NAME = "grain_zero_threshold_tamper_control"
register_reporter_policy(
    ZERO_THRESHOLD_POLICY_NAME, lambda: GrainEvidenceReporterPolicy(threshold_density=0.0)
)


class TestNoEventWindow:
    """With no pest anywhere, the evidence threshold is what stops reporting.

    With real infestations present the strongest true detection dominates the
    policy's maximum, so the threshold looks inert; a pest-free field is what
    shows it is load-bearing.
    """

    def _pest_free_spec(self) -> ArmSpec:
        return ArmSpec(
            name="designed_no_event",
            grounded_input_fraction=0.67,
            seed=11,
            steps=25,
            freeze_pest_evolution=True,
            reporting_levers=True,
            pest_intro_probability=0.0,
        )

    def test_threshold_on_produces_no_designed_reports(self) -> None:
        record = measure_designed_arm(self._pest_free_spec(), ALL_DESIGNED_ARM)
        assert record["evidence_rates"]["decision_steps"] > 0
        assert record["cohorts"]["designed_reports"] == 0

    def test_threshold_zero_produces_reports_and_none_are_correct(self) -> None:
        record = measure_designed_arm(
            self._pest_free_spec(), ALL_DESIGNED_ARM, ZERO_THRESHOLD_POLICY_NAME
        )
        assert record["cohorts"]["designed_reports"] > 0
        assert record["cohorts"]["designed_correct_reports"] == 0


class TestGroundTruthBoundary:
    def test_the_designed_policy_module_never_names_a_truth_accessor(self) -> None:
        source = Path(grain_guard.reporter_policy.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "get_ground_truth",
            "get_active_locations",
            "cells_above_threshold",
            "PestPopulation",
            "CropField",
            "grain_guard.adapter",
            "grain_guard.environment",
        ):
            assert forbidden not in source

    def test_the_best_arm_is_none_when_no_feasible_arm_scores(self) -> None:
        summaries = [
            summarize_policy_arm(
                arm,
                [
                    _record(
                        arm,
                        seed=0,
                        designed_reports=1,
                        designed_correct=0,
                        ordinary_reports=1,
                        ordinary_correct=0,
                    )
                ],
            )
            for arm in (ORDINARY_ARM, ALL_DESIGNED_ARM, INVASION_ARM)
        ]
        summaries.append(
            summarize_policy_arm(
                ORACLE_ARM,
                [_record(ORACLE_ARM, seed=0, designed_reports=500, designed_correct=500)],
            )
        )
        margin = exploitable_margin(summaries)
        assert margin["best_arm"] is None
        assert margin["best_reachable_precision"] is None
        assert margin["exploitable_margin_pp"] is None
        assert margin["oracle_precision"] == pytest.approx(1.0)
