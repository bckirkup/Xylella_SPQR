"""Agricultural falsification metrics aligned with spec §9."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StepMetrics(BaseModel):
    """Per-step metrics snapshot."""

    time_step: int = Field(ge=0)
    mean_crop_health: float = Field(default=1.0, ge=0.0, le=1.0)
    mean_yield_potential: float = Field(default=1.0, ge=0.0, le=1.0)
    total_pest_density: float = Field(default=0.0, ge=0.0)
    total_weed_density: float = Field(default=0.0, ge=0.0)
    mean_resistance_freq: float = Field(default=0.0, ge=0.0, le=1.0)
    n_sprays: float = Field(default=0.0, ge=0.0)
    spray_volume_L: float = Field(default=0.0, ge=0.0)
    false_sprays: float = Field(default=0.0, ge=0.0)
    missed_cells: float = Field(default=0.0, ge=0.0)
    biological_control_mean: float = Field(default=0.0, ge=0.0)
    surveillance_cost: float = Field(default=0.0, ge=0.0)
    response_cost: float = Field(default=0.0, ge=0.0)
    damage_cost: float = Field(default=0.0, ge=0.0)


class AgMetrics(BaseModel):
    """Cumulative agricultural metrics tracker (spec §9).

    Tracks:
    - Yield protected
    - Total pesticide/herbicide volume
    - False spray area
    - Missed infestation area
    - Economic net return
    - Resistance allele frequency trajectory
    - Biological control preservation
    - Detection lead time by pest/weed type
    - Cost per hectare
    """

    history: list[StepMetrics] = Field(default_factory=list)
    total_sprays: float = Field(default=0.0, ge=0.0)
    total_spray_volume: float = Field(default=0.0, ge=0.0)
    total_false_sprays: float = Field(default=0.0, ge=0.0)
    total_missed_cells: float = Field(default=0.0, ge=0.0)
    total_responses_judged_necessary: float = Field(default=0.0, ge=0.0)
    total_responses_judged_unnecessary: float = Field(default=0.0, ge=0.0)
    resistance_trajectory: list[float] = Field(default_factory=list)
    detection_latencies: list[int] = Field(default_factory=list)

    def record_step(self, metrics: StepMetrics) -> None:
        self.history.append(metrics)
        self.total_sprays += metrics.n_sprays
        self.total_spray_volume += metrics.spray_volume_L
        self.total_false_sprays += metrics.false_sprays
        self.total_missed_cells += metrics.missed_cells
        self.resistance_trajectory.append(metrics.mean_resistance_freq)

    def record_detection_latency(self, latency: int) -> None:
        self.detection_latencies.append(latency)

    def record_response_outcomes(
        self,
        *,
        dispatched: int,
        judged_necessary: int,
        judged_unnecessary: int,
    ) -> None:
        """Record post-dispatch spray judgments for the current step."""
        if self.history:
            last = self.history[-1]
            last.n_sprays = float(dispatched)
            last.spray_volume_L = float(dispatched)
            last.false_sprays = float(judged_unnecessary)
        self.total_sprays += dispatched
        self.total_spray_volume += dispatched
        self.total_false_sprays += judged_unnecessary
        self.total_responses_judged_necessary += judged_necessary
        self.total_responses_judged_unnecessary += judged_unnecessary

    @property
    def unnecessary_spray_rate(self) -> float:
        if self.total_sprays == 0:
            return 0.0
        return self.total_responses_judged_unnecessary / self.total_sprays

    @property
    def mean_detection_latency(self) -> float:
        if not self.detection_latencies:
            return float("inf")
        return sum(self.detection_latencies) / len(self.detection_latencies)

    @property
    def false_spray_rate(self) -> float:
        if self.total_sprays == 0:
            return 0.0
        return self.total_false_sprays / self.total_sprays

    @property
    def yield_protected(self) -> float:
        """Mean yield potential across all recorded steps."""
        if not self.history:
            return 0.0
        return sum(m.mean_yield_potential for m in self.history) / len(self.history)

    @property
    def final_resistance(self) -> float:
        if not self.resistance_trajectory:
            return 0.0
        return self.resistance_trajectory[-1]

    @property
    def total_cost(self) -> float:
        return sum(m.surveillance_cost + m.response_cost + m.damage_cost for m in self.history)

    def summary(self) -> dict[str, float]:
        return {
            "yield_protected": self.yield_protected,
            "total_spray_volume": self.total_spray_volume,
            "false_spray_rate": self.false_spray_rate,
            "unnecessary_spray_rate": self.unnecessary_spray_rate,
            "total_responses_judged_necessary": self.total_responses_judged_necessary,
            "total_responses_judged_unnecessary": self.total_responses_judged_unnecessary,
            "total_missed_cells": self.total_missed_cells,
            "final_resistance_freq": self.final_resistance,
            "mean_detection_latency": self.mean_detection_latency,
            "total_cost": self.total_cost,
            "biological_control_mean": (
                self.history[-1].biological_control_mean if self.history else 0.0
            ),
        }
