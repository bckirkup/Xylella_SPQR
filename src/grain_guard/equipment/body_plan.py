"""Farm Tot body plans: fixed hardware templates for agricultural drones/robots (spec §5)."""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class BodyPlanType(enum.StrEnum):
    """Farm Tot body plan archetypes.

    SCOUT_DRONE: high endurance, multispectral sensing, no treatment payload.
    SPRAY_DRONE: treatment payload, moderate sensing.
    AI_TRACTOR: boom sprayer, row-crop specialist, high payload.
    TRAP_ROBOT: ground robot servicing pheromone traps.
    DIAGNOSTIC_MICRO: small drone for close-up leaf-level diagnosis.
    """

    SCOUT_DRONE = "scout_drone"
    SPRAY_DRONE = "spray_drone"
    AI_TRACTOR = "ai_tractor"
    TRAP_ROBOT = "trap_robot"
    DIAGNOSTIC_MICRO = "diagnostic_micro"


class BodyPlan(BaseModel):
    """Physical hardware template for a farm Tot.

    Body plans are FIXED — they define the hardware constraints within
    which the evolvable genome operates.
    """

    plan_type: BodyPlanType = Field(default=BodyPlanType.SCOUT_DRONE)
    tank_liters: float = Field(
        default=0.0, ge=0.0, le=500.0, description="Treatment tank capacity in liters"
    )
    battery_capacity: float = Field(
        default=1.0, gt=0.0, description="Battery capacity (normalized)"
    )
    max_speed: float = Field(default=1.0, gt=0.0, description="Max speed in grid cells per step")
    endurance: int = Field(
        default=50, ge=1, description="Max operating time in steps before recharge"
    )
    has_rgb: bool = Field(default=True, description="RGB camera")
    has_multispectral: bool = Field(default=False, description="Multispectral sensor")
    has_thermal: bool = Field(default=False, description="Thermal imaging")
    has_trap_camera: bool = Field(default=False, description="Trap counting camera")
    has_soil_probe: bool = Field(default=False, description="Soil moisture probe")
    treatment_type: str = Field(
        default="none", description="pesticide, herbicide, biocontrol, or none"
    )

    @property
    def sensor_count(self) -> int:
        return sum(
            [
                self.has_rgb,
                self.has_multispectral,
                self.has_thermal,
                self.has_trap_camera,
                self.has_soil_probe,
            ]
        )

    @property
    def can_treat(self) -> bool:
        return self.tank_liters > 0.0

    @classmethod
    def scout_drone(cls) -> BodyPlan:
        """High endurance, rich sensing, no treatment."""
        return cls(
            plan_type=BodyPlanType.SCOUT_DRONE,
            tank_liters=0.0,
            battery_capacity=1.2,
            max_speed=2.0,
            endurance=80,
            has_rgb=True,
            has_multispectral=True,
            has_thermal=True,
            treatment_type="none",
        )

    @classmethod
    def spray_drone(cls) -> BodyPlan:
        """Targeted spray drone with moderate sensing."""
        return cls(
            plan_type=BodyPlanType.SPRAY_DRONE,
            tank_liters=20.0,
            battery_capacity=1.0,
            max_speed=1.0,
            endurance=40,
            has_rgb=True,
            has_thermal=True,
            treatment_type="pesticide",
        )

    @classmethod
    def ai_tractor(cls) -> BodyPlan:
        """AI tractor with boom sprayer for row crops."""
        return cls(
            plan_type=BodyPlanType.AI_TRACTOR,
            tank_liters=500.0,
            battery_capacity=3.0,
            max_speed=0.5,
            endurance=200,
            has_rgb=True,
            has_multispectral=True,
            treatment_type="herbicide",
        )

    @classmethod
    def trap_robot(cls) -> BodyPlan:
        """Ground robot for trap servicing and ground-truth counts."""
        return cls(
            plan_type=BodyPlanType.TRAP_ROBOT,
            tank_liters=0.0,
            battery_capacity=0.8,
            max_speed=0.3,
            endurance=100,
            has_rgb=True,
            has_trap_camera=True,
            has_soil_probe=True,
            treatment_type="none",
        )

    @classmethod
    def diagnostic_micro(cls) -> BodyPlan:
        """Micro drone for leaf-level pest identification."""
        return cls(
            plan_type=BodyPlanType.DIAGNOSTIC_MICRO,
            tank_liters=0.0,
            battery_capacity=0.5,
            max_speed=1.5,
            endurance=25,
            has_rgb=True,
            has_multispectral=True,
            has_thermal=True,
            treatment_type="none",
        )
