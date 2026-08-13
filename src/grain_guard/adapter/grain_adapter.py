"""GrainGuard domain adapter: connects agricultural simulation to TattleTots engine.

Implements the DomainAdapter ABC so the TattleTots engine can drive a
precision agriculture simulation without any domain-specific knowledge.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from tattletots.engine.response_judgment import judge_necessity
from tattletots.interface.domain_adapter import DomainAdapter
from tattletots.models.dispatch_target import DispatchTarget
from tattletots.models.location import EventLocation
from tattletots.models.report import Report
from tattletots.models.response_outcome import ResponseOutcome
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

DEFAULT_ENGINE_MAX_DIM = 30
"""Default TattleTots engine per-agent input dimensionality cap."""

SPRAY_EFFICACY = 0.8
"""Default pesticide efficacy for spot-spray responses."""


@dataclass(frozen=True)
class CostCoefficients:
    """Domain cost model coefficients (spec §9).

    Attributes:
        surveillance: cost per escalation event (sensor/drone scouting).
        response: cost per correct intervention (spray application).
        false_alarm: cost per false-positive spray (wasted resources).
        missed: cost per missed infestation (crop damage).
    """

    surveillance: float = 0.3
    response: float = 1.5
    false_alarm: float = 3.0
    missed: float = 8.0


@dataclass(frozen=True)
class StreamDimReport:
    """Per-stream dimensionality budget report.

    Attributes:
        label: human-readable stream name.
        dimensionality: number of floats the stream produces.
        exceeds_engine_cap: True if dim > engine_max_dim.
    """

    label: str
    dimensionality: int
    exceeds_engine_cap: bool


@dataclass(frozen=True)
class DimBudget:
    """Full dimensionality budget across all streams.

    Attributes:
        streams: per-stream reports.
        total_dim: sum of all stream dimensionalities.
        engine_max_dim: TattleTots per-agent input cap.
        any_truncated: True if any single stream exceeds the cap.
    """

    streams: list[StreamDimReport] = field(default_factory=list)
    total_dim: int = 0
    engine_max_dim: int = DEFAULT_ENGINE_MAX_DIM
    any_truncated: bool = False


class GrainGuardAdapter(DomainAdapter):
    """Domain adapter bridging agricultural simulation to TattleTots.

    Manages the crop field, weather, sensors, and translates their outputs
    into abstract data streams consumable by Tot agents.

    All sensor dimensionalities and fleet sizes are configurable.  Pass
    ``engine_max_dim`` (default 30) to surface the TattleTots engine's
    per-agent input cap; a warning is emitted when any stream exceeds it.
    """

    def __init__(
        self,
        grid_rows: int = 20,
        grid_cols: int = 20,
        landscape: LandscapeType = LandscapeType.MONOCULTURE,
        *,
        n_traps: int = 10,
        n_weather_stations: int = 2,
        n_soil_sensors: int = 4,
        satellite_revisit: int = 5,
        satellite_zone_rows: int = 5,
        satellite_zone_cols: int = 5,
        yield_zones: int = 5,
        pest_threshold: float = 10.0,
        cost_coefficients: CostCoefficients | None = None,
        engine_max_dim: int = DEFAULT_ENGINE_MAX_DIM,
        pest_intro_probability: float = 0.02,
        resistance_initial_frequency: float = 0.01,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self._field = CropField(rows=grid_rows, cols=grid_cols, landscape=landscape)
        self._pest_intro_probability = pest_intro_probability
        self._apply_resistance_frequency(resistance_initial_frequency)
        self._weather = AgWeather()

        self._satellite = SatelliteSensor(
            revisit_days=satellite_revisit,
            zone_rows=satellite_zone_rows,
            zone_cols=satellite_zone_cols,
        )
        self._drone_imager = DroneImager()
        self._traps = self._place_traps(n_traps)
        self._weather_stations = self._place_weather_stations(n_weather_stations)
        self._soil_sensors = self._place_soil_sensors(n_soil_sensors)
        self._yield_monitor = YieldMonitor(n_zones=yield_zones)

        self._streams: list[Stream] = []
        self._users: list[User] = []
        self._current_step = 0
        self._pest_threshold = pest_threshold
        self._cost = cost_coefficients or CostCoefficients()
        self._engine_max_dim = engine_max_dim
        self._setup_streams()
        self._warn_on_truncation()
        self._users = create_ag_users(n_signal_dims=self._total_stream_dims())

    def _apply_resistance_frequency(self, frequency: float) -> None:
        """Set initial herbicide resistance frequency across the field."""
        if np.isclose(frequency, 0.01, rtol=0.0, atol=0.0):
            return
        for r in range(self._field.rows):
            for c in range(self._field.cols):
                self._field.pests[r][c].resistance_freq = frequency
                self._field.weeds[r][c].resistance_freq = frequency

    # ------------------------------------------------------------------
    # Sensor placement
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Stream setup & budget
    # ------------------------------------------------------------------

    def _setup_streams(self) -> None:
        """Create data streams from sensor outputs.

        Stream layout:
        - satellite_stream: zone-level NDVI/NDRE/chlorophyll
        - pest_stream: pheromone trap observations
        - weather_stream: weather station readings
        - soil_stream: soil moisture readings
        """
        sat_dim = self._satellite.output_dim
        trap_dim = len(self._traps) * PheromoneTrap(row=0, col=0).output_dim
        weather_dim = len(self._weather_stations) * AgWeatherStation(row=0, col=0).output_dim
        soil_dim = len(self._soil_sensors) * SoilSensor(row=0, col=0).output_dim

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

    def _warn_on_truncation(self) -> None:
        """Emit warnings for streams whose dimensionality exceeds the engine cap."""
        for stream in self._streams:
            if stream.dimensionality > self._engine_max_dim:
                warnings.warn(
                    f"Stream '{stream.label}' has dimensionality {stream.dimensionality} "
                    f"which exceeds the TattleTots engine cap of {self._engine_max_dim}. "
                    f"Data will be silently truncated to {self._engine_max_dim} floats. "
                    f"Consider reducing sensor counts or zone grid dimensions.",
                    stacklevel=2,
                )

    def stream_budget(self) -> DimBudget:
        """Return a dimensionality budget report for all streams.

        Useful for tuning sensor configurations to avoid engine truncation.
        """
        reports: list[StreamDimReport] = []
        total = 0
        any_truncated = False
        for stream in self._streams:
            exceeds = stream.dimensionality > self._engine_max_dim
            if exceeds:
                any_truncated = True
            reports.append(
                StreamDimReport(
                    label=stream.label,
                    dimensionality=stream.dimensionality,
                    exceeds_engine_cap=exceeds,
                )
            )
            total += stream.dimensionality
        return DimBudget(
            streams=reports,
            total_dim=total,
            engine_max_dim=self._engine_max_dim,
            any_truncated=any_truncated,
        )

    def _total_stream_dims(self) -> int:
        return sum(s.dimensionality for s in self._streams)

    # ------------------------------------------------------------------
    # DomainAdapter interface
    # ------------------------------------------------------------------

    def get_streams(self) -> list[Stream]:
        return self._streams

    def get_users(self) -> list[User]:
        return self._users

    def step(self, time_step: int) -> None:
        """Advance agricultural simulation and update all sensor streams."""
        self._current_step = time_step
        self._evolve_weather(time_step)
        self._field.stochastic_pest_introduction(self.rng, probability=self._pest_intro_probability)
        self._field.step(self._weather, self.rng)
        self._update_streams(time_step)

    def get_ground_truth(self, time_step: int) -> bool:
        """An event is active if any cells have pest density above threshold."""
        return len(self._field.cells_above_threshold(self._pest_threshold)) > 0

    def get_active_locations(self, time_step: int) -> list[EventLocation]:
        """Return field cells where pest density exceeds threshold."""
        return self._field.cells_above_threshold(self._pest_threshold)

    def infer_report_location(
        self,
        stream_data: list[NDArray[np.float64]],
        stream_labels: list[str],
    ) -> EventLocation:
        """Infer report location from pest density stream peak."""
        for data, label in zip(stream_data, stream_labels, strict=False):
            if "pest" in label and data.size > 0:
                peak_idx = int(np.argmax(data))
                cols = self._field.cols
                return (peak_idx // cols, peak_idx % cols)
        if stream_data and stream_data[0].size > 0:
            peak_idx = int(np.argmax(np.abs(stream_data[0])))
            cols = self._field.cols
            return (peak_idx // cols, peak_idx % cols)
        return (0, 0)

    def score_relevance(self, signal_vector: NDArray[np.float64], user: User) -> float:
        from tattletots.engine.relevance import score_report_relevance

        return score_report_relevance(signal_vector, user)

    def compute_costs(
        self,
        n_escalations: int,
        n_correct: int,
        n_false_alarms: int,
        n_missed: int,
    ) -> dict[str, float]:
        """Agricultural cost model using configurable coefficients."""
        return {
            "surveillance_cost": n_escalations * self._cost.surveillance,
            "response_cost": n_correct * self._cost.response
            + n_false_alarms * self._cost.false_alarm,
            "damage_cost": n_missed * self._cost.missed,
        }

    def dispatch_spray(self, row: int, col: int) -> None:
        """Apply spot-spray pesticide at a field cell."""
        if row < 0 or col < 0 or row >= self._field.rows or col >= self._field.cols:
            return
        self._field.pests[row][col].apply_pesticide(SPRAY_EFFICACY, self.rng)

    def get_responder_user_id(self) -> str:
        """Agronomist authorizes field spray dispatch."""
        for user in self._users:
            if user.name == "Agronomist":
                return user.id
        return self._users[0].id

    def dispatch_and_judge_responses(
        self,
        targets: list[DispatchTarget],
        time_step: int,
    ) -> list[ResponseOutcome]:
        """Spray COP-selected pest locations and judge responder necessity."""
        outcomes: list[ResponseOutcome] = []
        responder_id = self.get_responder_user_id()

        for target in targets:
            row, col = target.location
            before = self._pest_severity(row, col)
            self.dispatch_spray(row, col)
            after = self._pest_severity(row, col)
            dispatched = True

            problem, mitigated, necessary = judge_necessity(
                before,
                after,
                problem_threshold=self._pest_threshold,
            )
            linked_reports = target.reports or [
                Report(
                    agent_id="",
                    target_user_id=responder_id,
                    time_step=time_step,
                    signal_vector=np.array([]),
                    confidence=0.0,
                    anomaly_score=0.0,
                    location=target.location,
                    verified=True,
                )
            ]
            for report in linked_reports:
                outcome = ResponseOutcome(
                    agent_id=report.agent_id,
                    responder_user_id=responder_id,
                    time_step=time_step,
                    location=target.location,
                    response_type="spray",
                    dispatched=dispatched,
                    problem_severity_before=before,
                    problem_severity_after=after,
                    problem_present=problem,
                    mitigated=mitigated,
                    response_necessary=necessary,
                )
                report.response_outcome = outcome
                outcomes.append(outcome)

        return outcomes

    def _pest_severity(self, row: int, col: int) -> float:
        """Pest density at a field cell."""
        if row < 0 or col < 0 or row >= self._field.rows or col >= self._field.cols:
            return 0.0
        return float(self._field.pests[row][col].density)

    # ------------------------------------------------------------------
    # Internal simulation helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def field(self) -> CropField:
        """Expose field for external inspection (metrics, architectures)."""
        return self._field

    @property
    def weather(self) -> AgWeather:
        """Expose current weather state."""
        return self._weather

    @property
    def engine_max_dim(self) -> int:
        """TattleTots per-agent input dimensionality cap."""
        return self._engine_max_dim

    @property
    def pest_threshold(self) -> float:
        """Pest density threshold for ground truth events."""
        return self._pest_threshold

    @property
    def cost_coefficients(self) -> CostCoefficients:
        """Current cost model coefficients."""
        return self._cost
