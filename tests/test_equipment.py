"""Unit tests for equipment body plans and genomes."""

from __future__ import annotations

import numpy as np
import pytest

from grain_guard.equipment.body_plan import BodyPlan, BodyPlanType
from grain_guard.equipment.equipment_genome import EquipmentGenome


class TestBodyPlan:
    def test_scout_drone(self) -> None:
        bp = BodyPlan.scout_drone()
        assert bp.plan_type == BodyPlanType.SCOUT_DRONE
        assert not bp.can_treat
        assert bp.sensor_count >= 3

    def test_spray_drone(self) -> None:
        bp = BodyPlan.spray_drone()
        assert bp.plan_type == BodyPlanType.SPRAY_DRONE
        assert bp.can_treat
        assert bp.tank_liters > 0

    def test_ai_tractor(self) -> None:
        bp = BodyPlan.ai_tractor()
        assert bp.plan_type == BodyPlanType.AI_TRACTOR
        assert bp.can_treat
        assert bp.tank_liters == pytest.approx(500.0, rel=0.0, abs=1e-12)

    def test_trap_robot(self) -> None:
        bp = BodyPlan.trap_robot()
        assert bp.plan_type == BodyPlanType.TRAP_ROBOT
        assert not bp.can_treat
        assert bp.has_trap_camera

    def test_diagnostic_micro(self) -> None:
        bp = BodyPlan.diagnostic_micro()
        assert bp.plan_type == BodyPlanType.DIAGNOSTIC_MICRO
        assert not bp.can_treat
        assert bp.sensor_count >= 3


class TestEquipmentGenome:
    def test_fractions_sum_to_one(self) -> None:
        g = EquipmentGenome()
        total = g.scout_fraction + g.treat_fraction + g.report_fraction
        assert abs(total - 1.0) < 0.01

    def test_mutate_preserves_body_plan(self) -> None:
        rng = np.random.default_rng(42)
        g = EquipmentGenome(body_plan=BodyPlan.spray_drone())
        m = g.mutate(rng, rate=1.0)
        assert m.body_plan.plan_type == BodyPlanType.SPRAY_DRONE
        assert m.body_plan.tank_liters == g.body_plan.tank_liters

    def test_mutate_fractions_sum_to_one(self) -> None:
        rng = np.random.default_rng(42)
        g = EquipmentGenome()
        m = g.mutate(rng, rate=1.0)
        total = m.scout_fraction + m.treat_fraction + m.report_fraction
        assert abs(total - 1.0) < 0.01

    def test_expected_role_scout(self) -> None:
        g = EquipmentGenome(
            body_plan=BodyPlan.scout_drone(),
            scout_fraction=0.6,
            treat_fraction=0.2,
            report_fraction=0.2,
        )
        assert g.expected_role == "scout"

    def test_expected_role_spray(self) -> None:
        g = EquipmentGenome(
            body_plan=BodyPlan.spray_drone(),
            scout_fraction=0.1,
            treat_fraction=0.6,
            report_fraction=0.3,
        )
        assert g.expected_role == "spray"

    def test_expected_role_trap(self) -> None:
        g = EquipmentGenome(body_plan=BodyPlan.trap_robot())
        assert g.expected_role == "trap_servicer"

    def test_expected_role_tractor(self) -> None:
        g = EquipmentGenome(body_plan=BodyPlan.ai_tractor())
        assert g.expected_role == "tractor"
