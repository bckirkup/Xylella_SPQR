"""Crop model: per-cell growth stage, health, and yield potential."""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class CropType(enum.StrEnum):
    """Crop species planted in the field."""

    WHEAT = "wheat"
    CORN = "corn"
    SOY = "soy"
    APPLE = "apple"
    MIXED = "mixed"


class GrowthStage(enum.StrEnum):
    """Phenological growth stages (simplified BBCH)."""

    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    GRAIN_FILL = "grain_fill"
    MATURE = "mature"
    HARVESTED = "harvested"


_STAGE_ORDER: list[GrowthStage] = [
    GrowthStage.SEEDLING,
    GrowthStage.VEGETATIVE,
    GrowthStage.FLOWERING,
    GrowthStage.GRAIN_FILL,
    GrowthStage.MATURE,
    GrowthStage.HARVESTED,
]

_GDD_THRESHOLDS: dict[GrowthStage, float] = {
    GrowthStage.SEEDLING: 0.0,
    GrowthStage.VEGETATIVE: 150.0,
    GrowthStage.FLOWERING: 500.0,
    GrowthStage.GRAIN_FILL: 900.0,
    GrowthStage.MATURE: 1400.0,
    GrowthStage.HARVESTED: 1800.0,
}


class CropCell(BaseModel):
    """Per-cell crop state.

    Tracks phenology via accumulated growing-degree-days, health from
    pest/weed pressure, and potential yield.
    """

    crop_type: CropType = Field(default=CropType.WHEAT)
    growth_stage: GrowthStage = Field(default=GrowthStage.SEEDLING)
    accumulated_gdd: float = Field(default=0.0, ge=0.0, description="Cumulative GDD")
    health: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Crop health index [0=dead, 1=perfect]"
    )
    yield_potential: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Fraction of max yield achievable"
    )
    soil_moisture: float = Field(default=0.5, ge=0.0, le=1.0, description="Soil moisture fraction")
    abiotic_stress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Drought or nutrient stress independent of pest damage",
    )
    is_cover_crop: bool = Field(
        default=False, description="Whether this cell is a cover crop alley (beneficial habitat)"
    )

    def advance_phenology(self, gdd_increment: float) -> None:
        """Advance growth stage based on accumulated GDD."""
        self.accumulated_gdd += gdd_increment
        idx = _STAGE_ORDER.index(self.growth_stage)
        for next_idx in range(idx + 1, len(_STAGE_ORDER)):
            stage = _STAGE_ORDER[next_idx]
            if self.accumulated_gdd >= _GDD_THRESHOLDS[stage]:
                self.growth_stage = stage
            else:
                break

    def apply_damage(self, damage: float) -> None:
        """Reduce health and yield potential from pest/weed pressure."""
        self.health = max(0.0, self.health - damage)
        self.yield_potential = max(0.0, self.yield_potential - damage * 0.8)

    @property
    def ndvi_proxy(self) -> float:
        """Simulated NDVI signal: healthy vegetation → high, stressed → low."""
        base = {
            GrowthStage.SEEDLING: 0.2,
            GrowthStage.VEGETATIVE: 0.6,
            GrowthStage.FLOWERING: 0.8,
            GrowthStage.GRAIN_FILL: 0.7,
            GrowthStage.MATURE: 0.4,
            GrowthStage.HARVESTED: 0.15,
        }
        return base[self.growth_stage] * self.health
