"""Hand-designed, evidence-only reporter policy for the GrainGuard domain.

The policy reads only what the adapter publishes to any agent attached to the
raw streams: pheromone-trap catch counts and drone pest-detection signals, with
their declared coordinates, modality labels and observation status. It never
reads field state, ground truth, or adapter internals.

Both readings are converted to an estimated pest density in the same units as
the published actionable threshold, using the sensors' own published
calibration (trap catch efficiency; drone detection at full detectability). The
drone conversion is deliberately conservative: pest behavioural escape lowers
detectability, so ``pest_signal`` underestimates density and the policy reports
less often than a policy that assumed the true detectability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from tattletots.interface.reporter_policy import (
    ReporterDecision,
    ReporterPolicyContext,
    ReporterStream,
    register_reporter_policy,
)
from tattletots.models.location import EventLocation

GRAIN_REPORTER_POLICY_NAME = "grain_trap_drone_evidence"
"""Registered name of the designed GrainGuard reporter policy."""

TRAP_STREAM_LABEL = "pheromone_traps"
DRONE_STREAM_LABEL = "drone_imagery"
TRAP_CATCH_MODALITY = "catch_count"
DRONE_PEST_MODALITY = "pest_detection"
OBSERVED_STATUS = "observed"

DEFAULT_THRESHOLD_DENSITY = 10.0
"""Published actionable pest density a report has to be supported by."""

DEFAULT_TRAP_CATCH_EFFICIENCY = 0.3
"""Published fraction of local adults a pheromone trap catches."""

DEFAULT_DRONE_DETECTABILITY = 1.0
"""Assumed drone detectability; 1.0 is the conservative end of the range."""


@dataclass(frozen=True)
class _Evidence:
    """One coordinate-bearing density estimate read from a public stream."""

    density: float
    location: EventLocation


@dataclass
class GrainEvidenceReporterPolicy:
    """Report a field cell only when public evidence puts it above threshold.

    Attributes:
        threshold_density: estimated density a report has to clear.
        trap_catch_efficiency: published trap catch efficiency used to invert
            a catch count into a density estimate.
        drone_detectability: assumed drone detectability used to invert a
            pest-detection signal into a density estimate.
        decision_steps: reporting decisions taken (adult steps of a designed
            agent whose escalation was evaluated).
        trap_evidence_steps: decisions with usable trap evidence.
        drone_evidence_steps: decisions with usable drone evidence.
        any_evidence_steps: decisions with usable evidence of either kind.
        escalation_steps: decisions that produced a report.
    """

    threshold_density: float = DEFAULT_THRESHOLD_DENSITY
    trap_catch_efficiency: float = DEFAULT_TRAP_CATCH_EFFICIENCY
    drone_detectability: float = DEFAULT_DRONE_DETECTABILITY
    decision_steps: int = 0
    trap_evidence_steps: int = 0
    drone_evidence_steps: int = 0
    any_evidence_steps: int = 0
    escalation_steps: int = 0
    _stream_labels: set[str] = field(default_factory=set)

    def decide(self, context: ReporterPolicyContext) -> ReporterDecision:
        """Report the strongest above-threshold cell in the current snapshot."""
        self.decision_steps += 1
        self._stream_labels.update(stream.label for stream in context.streams)
        trap = self._best_trap_evidence(context)
        drone = self._best_drone_evidence(context)
        self._record_evidence(trap is not None, drone is not None)

        supported = [
            item
            for item in (trap, drone)
            if item is not None
            and item.density >= self.threshold_density
            and self._in_frame(item.location, context)
        ]
        if not supported:
            return ReporterDecision(escalate=False)
        best = max(supported, key=lambda item: item.density)
        self.escalation_steps += 1
        return ReporterDecision(escalate=True, location=best.location)

    @property
    def stream_labels(self) -> tuple[str, ...]:
        """Raw stream labels this policy has been offered, sorted."""
        return tuple(sorted(self._stream_labels))

    def evidence_rates(self) -> dict[str, float]:
        """Evidence-arrival and escalation rates over this policy's decisions."""
        denominator = max(self.decision_steps, 1)
        return {
            "decision_steps": float(self.decision_steps),
            "trap_evidence_rate": self.trap_evidence_steps / denominator,
            "drone_evidence_rate": self.drone_evidence_steps / denominator,
            "any_evidence_rate": self.any_evidence_steps / denominator,
            "escalation_rate": self.escalation_steps / denominator,
        }

    def _record_evidence(self, trap: bool, drone: bool) -> None:
        if trap:
            self.trap_evidence_steps += 1
        if drone:
            self.drone_evidence_steps += 1
        if trap or drone:
            self.any_evidence_steps += 1

    def _best_trap_evidence(self, context: ReporterPolicyContext) -> _Evidence | None:
        stream = self._find_stream(context.streams, TRAP_STREAM_LABEL)
        if stream is None or self.trap_catch_efficiency <= 0.0:
            return None
        return self._best_reading(stream, TRAP_CATCH_MODALITY, 1.0 / self.trap_catch_efficiency)

    def _best_drone_evidence(self, context: ReporterPolicyContext) -> _Evidence | None:
        stream = self._find_stream(context.streams, DRONE_STREAM_LABEL)
        if stream is None or self.drone_detectability <= 0.0:
            return None
        return self._best_reading(stream, DRONE_PEST_MODALITY, 1.0 / self.drone_detectability)

    def _best_reading(
        self,
        stream: ReporterStream,
        modality: str,
        scale: float,
    ) -> _Evidence | None:
        """Strongest observed reading of one modality, as a density estimate."""
        modalities = stream.metadata.modality
        coordinates = stream.metadata.coordinates
        if modalities is None or coordinates is None:
            return None
        best: _Evidence | None = None
        for index, value in enumerate(stream.data):
            location = self._reading_location(stream, modalities, coordinates, index, modality)
            if location is None or not np.isfinite(value):
                continue
            density = float(value) * scale
            if best is None or density > best.density:
                best = _Evidence(density=density, location=location)
        return best

    @staticmethod
    def _reading_location(
        stream: ReporterStream,
        modalities: tuple[str | None, ...],
        coordinates: tuple[tuple[float, ...] | None, ...],
        index: int,
        modality: str,
    ) -> EventLocation | None:
        """Published coordinate of one reading, if it is the wanted modality."""
        if index >= len(modalities) or index >= len(coordinates):
            return None
        if (modalities[index] or "") != modality:
            return None
        if index >= len(stream.observation_status):
            return None
        if stream.observation_status[index] != OBSERVED_STATUS:
            return None
        coordinate = coordinates[index]
        if coordinate is None or len(coordinate) < 2:
            return None
        return (int(round(coordinate[0])), int(round(coordinate[1])))

    @staticmethod
    def _find_stream(
        streams: tuple[ReporterStream, ...],
        label: str,
    ) -> ReporterStream | None:
        return next((stream for stream in streams if stream.label == label), None)

    @staticmethod
    def _in_frame(location: EventLocation, context: ReporterPolicyContext) -> bool:
        if context.location_frame is None:
            return True
        minimum, maximum = context.location_frame
        return minimum[0] <= location[0] <= maximum[0] and minimum[1] <= location[1] <= maximum[1]


register_reporter_policy(GRAIN_REPORTER_POLICY_NAME, GrainEvidenceReporterPolicy)
