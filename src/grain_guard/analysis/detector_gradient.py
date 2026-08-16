"""Detector-side (agent) selection-gradient measurement.

An agent's realized fitness is its offspring count; its focal heritable trait is
the genome escalation threshold, and its realized function is its correct-report
rate. Agents born too late in a run have not had a chance to reproduce, so they
are excluded from fitness scoring to keep the estimate from being censored
downward.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field

from tattletots.engine.world import World

from grain_guard.analysis.gradient import (
    GradientEstimates,
    LineagePairs,
    estimate_gradient,
    selection_differential,
)

DEFAULT_MATURITY_FRACTION = 0.75
"""Agents first seen after this fraction of the run are not fitness-scored."""


@dataclass
class AgentRecord:
    """One agent's lineage bookkeeping.

    Attributes:
        agent_id: engine agent identifier.
        parent_id: first parent identifier, or ``None`` for founders.
        first_seen_step: step index at which the agent was first observed.
        escalation_threshold: heritable focal trait, read when first seen.
        offspring: number of offspring observed for this agent.
        reports_issued: reports issued over the observed lifetime.
        correct_reports: correct reports over the observed lifetime.
        reporter_policy: name of the agent's non-genomic reporter policy, or
            ``None`` for an ordinary agent using evolved escalation.
    """

    agent_id: str
    parent_id: str | None
    first_seen_step: int
    escalation_threshold: float
    offspring: int = 0
    reports_issued: int = 0
    correct_reports: int = 0
    reporter_policy: str | None = None

    @property
    def report_precision(self) -> float:
        """Fraction of this agent's reports that were correct."""
        if self.reports_issued <= 0:
            return 0.0
        return self.correct_reports / self.reports_issued


@dataclass
class LineageTracker:
    """Observe an engine world each step and accumulate lineage statistics.

    Attributes:
        records: per-agent records keyed by agent id.
        last_step: most recent step index observed.
    """

    records: dict[str, AgentRecord] = dataclass_field(default_factory=dict)
    last_step: int = 0

    def observe(self, world: World, step: int) -> None:
        """Record newly seen agents and refresh lifetime report counters."""
        self.last_step = step
        for agent_id, agent in world.agents.items():
            record = self.records.get(agent_id)
            if record is None:
                parents = list(agent.state.parent_ids)
                record = AgentRecord(
                    agent_id=agent_id,
                    parent_id=parents[0] if parents else None,
                    first_seen_step=step,
                    escalation_threshold=float(agent.genome.escalation_threshold),
                    reporter_policy=agent.genome.reporter_policy,
                )
                self.records[agent_id] = record
                parent = self.records.get(record.parent_id or "")
                if parent is not None:
                    parent.offspring += 1
            record.reports_issued = int(agent.state.reports_issued)
            record.correct_reports = int(agent.state.correct_reports)

    def scored_records(
        self, *, maturity_fraction: float = DEFAULT_MATURITY_FRACTION
    ) -> list[AgentRecord]:
        """Records old enough that a zero offspring count is informative."""
        cutoff = self.last_step * maturity_fraction
        return [r for r in self.records.values() if r.first_seen_step <= cutoff]

    def estimates(
        self, *, maturity_fraction: float = DEFAULT_MATURITY_FRACTION
    ) -> GradientEstimates | None:
        """Estimate the detector-side gradient over fitness-scored agents."""
        scored = self.scored_records(maturity_fraction=maturity_fraction)
        if len(scored) < 2:
            return None
        traits = [r.escalation_threshold for r in scored]
        fitness = [float(r.offspring) for r in scored]
        return estimate_gradient(traits, fitness, self._lineage_pairs(scored))

    def function_selection_differential(
        self, *, maturity_fraction: float = DEFAULT_MATURITY_FRACTION
    ) -> float | None:
        """Selection differential on realized function (correct-report rate).

        This is selection measured on performance rather than on a heritable
        trait: it answers whether reporting correctly paid in offspring.
        """
        scored = self.scored_records(maturity_fraction=maturity_fraction)
        if len(scored) < 2:
            return None
        return selection_differential(
            [r.report_precision for r in scored], [float(r.offspring) for r in scored]
        )

    def _lineage_pairs(self, scored: list[AgentRecord]) -> LineagePairs:
        pairs = LineagePairs([], [], [], [])
        by_id = {r.agent_id: r for r in scored}
        for record in scored:
            parent = by_id.get(record.parent_id or "")
            if parent is None:
                continue
            pairs.parent_trait.append(parent.escalation_threshold)
            pairs.offspring_trait.append(record.escalation_threshold)
            pairs.parent_fitness.append(float(parent.offspring))
            pairs.offspring_fitness.append(float(record.offspring))
        return pairs

    def summary(
        self, *, maturity_fraction: float = DEFAULT_MATURITY_FRACTION
    ) -> dict[str, float | int]:
        """Descriptive counts for the fitness-scored cohort."""
        scored = self.scored_records(maturity_fraction=maturity_fraction)
        reports = sum(r.reports_issued for r in scored)
        correct = sum(r.correct_reports for r in scored)
        reproducers = sum(1 for r in scored if r.offspring > 0)
        return {
            "n_agents_observed": len(self.records),
            "n_agents_scored": len(scored),
            "n_reproducing_agents": reproducers,
            "reproducing_fraction": (reproducers / len(scored)) if scored else 0.0,
            "scored_reports_issued": reports,
            "scored_correct_reports": correct,
            "scored_report_precision": (correct / reports) if reports else 0.0,
        }
