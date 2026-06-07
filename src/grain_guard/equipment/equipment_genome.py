"""Farm Tot behavioral genome: evolvable traits layered on body plan hardware."""

from __future__ import annotations

from typing import Self

import numpy as np
from pydantic import BaseModel, Field

from grain_guard.equipment.body_plan import BodyPlan, BodyPlanType


class EquipmentGenome(BaseModel):
    """Heritable behavioral traits for a farm Tot.

    The body plan is fixed hardware; these traits evolve within
    hardware constraints. Behavioral fractions must sum to 1.0.
    """

    model_config = {"arbitrary_types_allowed": True}

    body_plan: BodyPlan = Field(default_factory=BodyPlan)

    scout_fraction: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Fraction of energy allocated to scouting/patrol",
    )
    treat_fraction: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Fraction of energy allocated to treatment (spray/biocontrol)",
    )
    report_fraction: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Fraction of energy allocated to reporting",
    )
    crop_niche_preference: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Preferred niche (0=healthy zones, 1=stressed zones)",
    )
    pest_threshold_sensitivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sensitivity to economic threshold (0=spray early, 1=wait for high density)",
    )
    escalation_to_user: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Anomaly threshold for escalating to human user",
    )
    spatial_range: float = Field(
        default=5.0,
        ge=1.0,
        le=50.0,
        description="Operating range in grid cells from base",
    )
    biocontrol_affinity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Preference for biological control preservation (avoids spraying near beneficials)",
    )

    @property
    def expected_role(self) -> str:
        """Infer emergent role from genome and body plan."""
        if self.body_plan.plan_type == BodyPlanType.TRAP_ROBOT:
            return "trap_servicer"
        if self.body_plan.plan_type == BodyPlanType.AI_TRACTOR:
            return "tractor"
        if self.body_plan.can_treat and self.treat_fraction > 0.4:
            return "spray"
        if self.body_plan.sensor_count >= 3 and self.scout_fraction > 0.4:
            return "scout"
        if self.report_fraction > 0.5:
            return "diagnostic"
        return "generalist"

    def mutate(self, rng: np.random.Generator, rate: float = 0.1) -> Self:
        """Return a mutated copy. Body plan is NOT mutated (hardware is fixed)."""
        data = self.model_dump()
        float_traits = [
            "scout_fraction",
            "treat_fraction",
            "report_fraction",
            "crop_niche_preference",
            "pest_threshold_sensitivity",
            "escalation_to_user",
            "spatial_range",
            "biocontrol_affinity",
        ]
        for trait in float_traits:
            if rng.random() < rate:
                if trait == "spatial_range":
                    data[trait] = float(np.clip(data[trait] + rng.normal(0, 1.0), 1.0, 50.0))
                else:
                    data[trait] = float(np.clip(data[trait] + rng.normal(0, 0.05), 0.0, 1.0))

        total = data["scout_fraction"] + data["treat_fraction"] + data["report_fraction"]
        if total > 0:
            data["scout_fraction"] /= total
            data["treat_fraction"] /= total
            data["report_fraction"] /= total

        return type(self).model_validate(data)
