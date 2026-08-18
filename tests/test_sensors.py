"""Unit tests for sensor models."""

from __future__ import annotations

import numpy as np

from grain_guard.environment.crop import CropCell
from grain_guard.environment.pest import PestPopulation
from grain_guard.environment.weather import AgWeather
from grain_guard.environment.weed import WeedPopulation
from grain_guard.sensors.drone_imagery import DroneImager
from grain_guard.sensors.pheromone_trap import PheromoneTrap
from grain_guard.sensors.satellite import SatelliteSensor
from grain_guard.sensors.soil_sensor import SoilSensor
from grain_guard.sensors.weather_station import AgWeatherStation
from grain_guard.sensors.yield_monitor import YieldMonitor


class TestSatelliteSensor:
    def test_returns_none_off_cadence(self) -> None:
        s = SatelliteSensor(revisit_days=5)
        rng = np.random.default_rng(42)
        crops = [[CropCell() for _ in range(5)] for _ in range(5)]
        assert s.observe(crops, time_step=1, rng=rng) is None

    def test_returns_data_on_cadence(self) -> None:
        s = SatelliteSensor(revisit_days=5)
        rng = np.random.default_rng(42)
        crops = [[CropCell() for _ in range(5)] for _ in range(5)]
        obs = s.observe(crops, time_step=5, rng=rng)
        assert obs is not None
        assert obs.shape == (s.output_dim,)

    def test_output_dim(self) -> None:
        s = SatelliteSensor(zone_rows=3, zone_cols=4)
        assert s.output_dim == 36


class TestDroneImager:
    def test_observe_shape(self) -> None:
        d = DroneImager()
        rng = np.random.default_rng(42)
        obs = d.observe(CropCell(), PestPopulation(density=10.0), WeedPopulation(), rng)
        assert obs.shape == (4,)

    def test_observe_nonneg(self) -> None:
        d = DroneImager()
        rng = np.random.default_rng(42)
        obs = d.observe(CropCell(), PestPopulation(), WeedPopulation(), rng)
        assert all(v >= 0 for v in obs)


class TestPheromoneTrap:
    def test_observe_shape(self) -> None:
        t = PheromoneTrap(row=0, col=0)
        rng = np.random.default_rng(42)
        obs = t.observe(PestPopulation(density=20.0), time_step=0, rng=rng)
        assert obs.shape == (2,)

    def test_catch_proportional(self) -> None:
        t = PheromoneTrap(row=0, col=0, catch_efficiency=0.5)
        rng = np.random.default_rng(42)
        obs_low = t.observe(PestPopulation(density=5.0), time_step=0, rng=rng)
        obs_high = t.observe(PestPopulation(density=50.0), time_step=0, rng=rng)
        assert obs_high[0] > obs_low[0]


class TestAgWeatherStation:
    def test_observe_shape(self) -> None:
        ws = AgWeatherStation(row=0, col=0)
        rng = np.random.default_rng(42)
        obs = ws.observe(AgWeather(), rng)
        assert obs.shape == (5,)


class TestSoilSensor:
    def test_observe_shape(self) -> None:
        ss = SoilSensor(row=0, col=0)
        rng = np.random.default_rng(42)
        obs = ss.observe(CropCell(), rng)
        assert obs.shape == (3,)

    def test_conductivity_separates_abiotic_stress_at_equal_health(self) -> None:
        """Drought damage and pest damage look alike in health; soil tells them apart.

        Both cells carry the same reduced health, so a health- or NDVI-only
        reading cannot separate them. Conductivity has to fall with abiotic
        stress for the discrimination to exist at all, and it has to stay
        graded rather than switch on a single boundary.
        """
        sensor = SoilSensor(row=0, col=0)
        readings = []
        for stress in (0.0, 0.5, 1.0):
            cell = CropCell(health=0.6, soil_moisture=0.7, abiotic_stress=stress)
            samples = [sensor.observe(cell, np.random.default_rng(seed))[2] for seed in range(40)]
            readings.append(float(np.mean(samples)))
        assert readings[0] > readings[1] > readings[2]
        assert readings[0] - readings[2] > 0.1


class TestYieldMonitor:
    def test_returns_none_early_season(self) -> None:
        ym = YieldMonitor()
        rng = np.random.default_rng(42)
        crops = [[CropCell() for _ in range(5)] for _ in range(5)]
        assert ym.observe(crops, rng) is None

    def test_returns_data_at_harvest(self) -> None:
        from grain_guard.environment.crop import GrowthStage

        ym = YieldMonitor()
        rng = np.random.default_rng(42)
        crops = [[CropCell(growth_stage=GrowthStage.MATURE) for _ in range(5)] for _ in range(5)]
        obs = ym.observe(crops, rng)
        assert obs is not None
        assert obs.shape == (5,)
