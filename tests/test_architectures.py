"""Unit tests for competing management architectures."""

from __future__ import annotations

import numpy as np
import pytest

from grain_guard.architectures.a0_human_ipm import HumanIPM
from grain_guard.architectures.a1_ai_tractor import AITractor
from grain_guard.architectures.a2_prescription_drone import PrescriptionDrone
from grain_guard.architectures.a3_centralized_platform import CentralizedPlatform
from grain_guard.environment.field import CropField
from grain_guard.environment.weather import AgWeather


@pytest.fixture()
def field_with_pests() -> CropField:
    rng = np.random.default_rng(42)
    f = CropField(rows=10, cols=10)
    f.stochastic_pest_introduction(rng, probability=1.0)
    for _ in range(5):
        f.step(AgWeather(temperature=25.0), rng)
    return f


@pytest.fixture()
def weather() -> AgWeather:
    return AgWeather(temperature=25.0, wind_speed=3.0, precipitation=0.0)


class TestHumanIPM:
    def test_step_returns_keys(self, field_with_pests: CropField, weather: AgWeather) -> None:
        arch = HumanIPM(scout_interval=1)
        result = arch.step(field_with_pests, weather, time_step=7)
        assert "n_sprays" in result
        assert "spray_volume_L" in result
        assert "false_sprays" in result
        assert "missed_cells" in result

    def test_no_spray_off_interval(self, field_with_pests: CropField, weather: AgWeather) -> None:
        arch = HumanIPM(scout_interval=7)
        result = arch.step(field_with_pests, weather, time_step=3)
        assert result["n_sprays"] == 0.0

    def test_reset(self) -> None:
        arch = HumanIPM()
        arch.reset()


class TestAITractor:
    def test_step_returns_keys(self, field_with_pests: CropField, weather: AgWeather) -> None:
        arch = AITractor(pass_interval=1)
        result = arch.step(field_with_pests, weather, time_step=3)
        assert "n_sprays" in result

    def test_reset(self) -> None:
        arch = AITractor()
        arch.reset()


class TestPrescriptionDrone:
    def test_step_returns_keys(self, field_with_pests: CropField, weather: AgWeather) -> None:
        arch = PrescriptionDrone(map_update_interval=1)
        result = arch.step(field_with_pests, weather, time_step=5)
        assert "n_sprays" in result

    def test_reset(self) -> None:
        arch = PrescriptionDrone()
        arch.reset()


class TestCentralizedPlatform:
    def test_step_returns_keys(self, field_with_pests: CropField, weather: AgWeather) -> None:
        arch = CentralizedPlatform()
        result = arch.step(field_with_pests, weather, time_step=0)
        assert "n_sprays" in result

    def test_reset(self) -> None:
        arch = CentralizedPlatform()
        arch.reset()
