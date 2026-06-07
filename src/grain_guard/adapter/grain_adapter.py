"""GrainGuard domain adapter: connects agricultural simulation to TattleTots engine.

Implements the DomainAdapter ABC so the TattleTots engine can drive a
precision agriculture simulation without any domain-specific knowledge.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from tattletots.interface.domain_adapter import DomainAdapter
from tattletots.models.stream import Stream, StreamType
from tattletots.models.user import User

from grain_guard.environment.field import CropField, LandscapeType
from grain_guard.environment.weather import AgWeather
from grain_guard.sensors.drone_imagery import DroneImager
from grain_guard.sensors.pheromone_trap import PheromoneTrap
from grain_guard.sensors.satellite import SatelliteSensor
from grain_guard.sensors.soil_sensor import SoilSensor
from grain_guard.sensors.weather_station import AgWeatherStation
from grain_guard.sensors.yield_monitor import YieldMonitor
from grain_guard.users.ag_users import create_ag_users


class GrainGuardAdapter(DomainAdapter):
    """Domain adapter bridging agricultural simulation to TattleTots.

    Manages the crop field, weather, sensors, and translates their outputs
    into abstract data streams consumable by Tot agents.
    """

    def __init__(
        self,
        grid_rows: int = 20,
        grid_cols: int = 20,
        landscape: LandscapeType = LandscapeType.MONOCULTURE,
        n_traps: int = 10,
        n_weather_stations: int = 2,
        n_soil_sensors: int = 4,
        satellite_revisit: int = 5,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self._field = CropField(rows=grid_rows, cols=grid_cols, landscape=landscape)
        self._weather = AgWeather()

        self._satellite = SatelliteSensor(revisit_days=satellite_revisit)
        self._drone_imager = DroneImager()
        self._traps = self._place_traps(n_traps)
        self._weather_stations = self._place_weather_stations(n_weather_stations)
        self._soil_sensors = self._place_soil_sensors(n_soil_sensors)
        self._yield_monitor = YieldMonitor()

        self._streams: list[Stream] = []
        self._users: list[User] = []
        self._current_step = 0
        self._pest_threshold = 10.0
        self._setup_streams()
        self._users = create_ag_users(n_signal_dims=self._total_stream_dims())

    def _place_traps(self, n: int) -> list[PheromoneTrap]:
        traps: list[PheromoneTrap] = []
        for i in range(n):
            r = int((i + 1) * self._field.rows / (n + 1))
            c = int(self.rng.integers(0, self._field.cols))
            traps.append(PheromoneTrap(row=r, col=c))
        return traps

    def _place_weather_stations(self, n: int) -> list[AgWeatherStation]:
        stations: list[AgWeatherStation] = []
        for _ in range(n):
            r = int(self.rng.integers(0, self._field.rows))
            c = int(self.rng.integers(0, self._field.cols))
            stations.append(AgWeatherStation(row=r, col=c))
        return stations

    def _place_soil_sensors(self, n: int) -> list[SoilSensor]:
        sensors: list[SoilSensor] = []
        for _ in range(n):
            r = int(self.rng.integers(0, self._field.rows))
            c = int(self.rng.integers(0, self._field.cols))
            sensors.append(SoilSensor(row=r, col=c))
        return sensors

    def _setup_streams(self) -> None:
        """Create data streams from sensor outputs.

        Stream layout:
        - satellite_stream: zone-level NDVI/NDRE/chlorophyll
        - pest_stream: pheromone trap observations
        - weather_stream: weather station readings
        - soil_stream: soil moisture readings
        """
        sat_dim = self._satellite.output_dim
        trap_dim = len(self._traps) * 2
        weather_dim = len(self._weather_stations) * 5
        soil_dim = len(self._soil_sensors) * 3

        self._streams = [
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=sat_dim,
                label="satellite_indices",
                current_data=np.zeros(sat_dim),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=trap_dim,
                label="pheromone_traps",
                current_data=np.zeros(trap_dim),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=weather_dim,
                label="weather_observations",
                current_data=np.zeros(weather_dim),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=soil_dim,
                label="soil_moisture",
                current_data=np.zeros(soil_dim),
            ),
        ]

    def _total_stream_dims(self) -> int:
        return sum(s.dimensionality for s in self._streams)

    def get_streams(self) -> list[Stream]:
        return self._streams

    def get_users(self) -> list[User]:
        return self._users

    def step(self, time_step: int) -> None:
        """Advance agricultural simulation and update all sensor streams."""
        self._current_step = time_step
        self._evolve_weather(time_step)
        self._field.stochastic_pest_introduction(self.rng)
        self._field.step(self._weather, self.rng)
        self._update_streams(time_step)

    def get_ground_truth(self, time_step: int) -> bool:
        """An event is active if any cells have pest density above threshold."""
        return len(self._field.cells_above_threshold(self._pest_threshold)) > 0

    def score_relevance(self, signal_vector: NDArray[np.float64], user: User) -> float:
        return float(user.compute_relevance(signal_vector))

    def compute_costs(
        self,
        n_escalations: int,
        n_correct: int,
        n_false_alarms: int,
        n_missed: int,
    ) -> dict[str, float]:
        """Agricultural cost model.

        - Surveillance: sensor/drone scouting costs.
        - Response: spray application costs (false alarms expensive).
        - Damage: crop loss from unmanaged infestations.
        """
        return {
            "surveillance_cost": n_escalations * 0.3,
            "response_cost": n_correct * 1.5 + n_false_alarms * 3.0,
            "damage_cost": n_missed * 8.0,
        }

    def _evolve_weather(self, time_step: int) -> None:
        """Seasonal weather with sinusoidal temperature and stochastic rain."""
        phase = 2.0 * np.pi * time_step / 365.0
        self._weather = AgWeather(
            temperature=20.0 + 12.0 * np.sin(phase) + float(self.rng.normal(0, 2)),
            humidity=float(np.clip(0.5 + 0.2 * np.cos(phase) + self.rng.normal(0, 0.05), 0, 1)),
            wind_speed=max(0.0, 4.0 + 2.0 * np.sin(phase * 0.5) + float(self.rng.normal(0, 1))),
            wind_direction=float((180.0 + 90.0 * np.sin(phase * 0.3)) % 360),
            precipitation=max(
                0.0, float(self.rng.exponential(2.0) if self.rng.random() < 0.2 else 0.0)
            ),
            solar_radiation=max(0.0, 15.0 + 8.0 * np.sin(phase) + float(self.rng.normal(0, 1))),
        )

    def _update_streams(self, time_step: int) -> None:
        """Populate stream data from sensor outputs."""
        sat_obs = self._satellite.observe(self._field.crops, time_step, self.rng)
        if sat_obs is not None:
            self._streams[0].update(sat_obs)

        trap_parts = [
            trap.observe(self._field.pests[trap.row][trap.col], time_step, self.rng)
            for trap in self._traps
        ]
        self._streams[1].update(np.concatenate(trap_parts))

        weather_parts = [ws.observe(self._weather, self.rng) for ws in self._weather_stations]
        self._streams[2].update(np.concatenate(weather_parts))

        soil_parts = [
            ss.observe(self._field.crops[ss.row][ss.col], self.rng) for ss in self._soil_sensors
        ]
        self._streams[3].update(np.concatenate(soil_parts))

    @property
    def field(self) -> CropField:
        """Expose field for external inspection (metrics, architectures)."""
        return self._field

    @property
    def weather(self) -> AgWeather:
        """Expose current weather state."""
        return self._weather
