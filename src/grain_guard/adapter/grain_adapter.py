"""GrainGuard domain adapter: connects agricultural simulation to TattleTots engine.

Implements the DomainAdapter ABC so the TattleTots engine can drive a
precision agriculture simulation without any domain-specific knowledge.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field
from tattletots.engine.response_judgment import judge_necessity
from tattletots.interface.domain_adapter import DomainAdapter
from tattletots.models.dispatch_target import DispatchTarget
from tattletots.models.location import EventLocation
from tattletots.models.observation import ObservationStatus, StreamMetadata
from tattletots.models.report import Report
from tattletots.models.response_outcome import ResponseOutcome
from tattletots.models.stream import Stream, StreamType
from tattletots.models.user import User

from grain_guard.environment.field import CropField, EcologyConfig, LandscapeType
from grain_guard.environment.pest import PestPopulation
from grain_guard.environment.weather import AgWeather
from grain_guard.equipment.sprayer_fleet import SprayerFleet, SprayerFleetConfig
from grain_guard.sensors.drone_imagery import DroneImager
from grain_guard.sensors.pheromone_trap import PheromoneTrap
from grain_guard.sensors.satellite import SatelliteSensor
from grain_guard.sensors.soil_sensor import SoilSensor
from grain_guard.sensors.weather_station import AgWeatherStation
from grain_guard.sensors.yield_monitor import YieldMonitor
from grain_guard.users.ag_users import create_ag_users

DEFAULT_ENGINE_MAX_DIM = 75
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


class SprayBudgetConfig(BaseModel):
    """Hard cap on pesticide applications within a regulatory interval.

    Superseded by :class:`~grain_guard.equipment.sprayer_fleet.SprayerFleetConfig`
    and off by default: measurement showed that capping field-wide pesticide
    volume also caps the collateral kill of natural enemies, which destroys the
    resurgence criterion. See ``docs/phase2_spray_budget_measurement.md``.
    """

    capacity: int = Field(default=60, ge=1)
    interval_steps: int = Field(default=7, ge=1)


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
    ``engine_max_dim`` (default 75) to surface the TattleTots engine's
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
        freeze_pest_evolution: bool = False,
        ecology_config: EcologyConfig | dict[str, object] | None = None,
        spray_budget_config: SprayBudgetConfig | dict[str, object] | None = None,
        sprayer_fleet_config: SprayerFleetConfig | dict[str, object] | None = None,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self._field = CropField(
            rows=grid_rows,
            cols=grid_cols,
            landscape=landscape,
            ecology=EcologyConfig.model_validate(ecology_config or {}),
            freeze_pest_evolution=freeze_pest_evolution,
        )
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
        self._spray_budget = (
            SprayBudgetConfig.model_validate(spray_budget_config)
            if spray_budget_config is not None
            else None
        )
        self._spray_budget_window = -1
        self._spray_budget_remaining = 0
        self._sprayer_fleet = self._build_sprayer_fleet(sprayer_fleet_config)
        self._spray_attempts = 0
        self._sprays_applied = 0
        self._sprays_denied = 0
        self._pest_threshold = pest_threshold
        self._cost = cost_coefficients or CostCoefficients()
        self._engine_max_dim = engine_max_dim
        self._setup_streams()
        self._warn_on_truncation()
        self._users = create_ag_users(n_signal_dims=self._total_stream_dims())

    @property
    def pest_evolution_frozen(self) -> bool:
        """Whether the pest adversary is held fixed for this run."""
        return self._field.freeze_pest_evolution

    @property
    def spray_budget_metrics(self) -> dict[str, int | None]:
        """Operational spray demand, fulfillment, and remaining capacity."""
        return {
            "capacity": self._spray_budget.capacity if self._spray_budget else None,
            "interval_steps": (self._spray_budget.interval_steps if self._spray_budget else None),
            "attempts": self._spray_attempts,
            "applied": self._sprays_applied,
            "denied": self._sprays_denied,
            "remaining": self._spray_budget_remaining_value(),
        }

    @property
    def sprayer_fleet_metrics(self) -> dict[str, float | int] | None:
        """Per-Tot tank fulfillment, refill trips, and travel; ``None`` if unlimited."""
        if self._sprayer_fleet is None:
            return None
        return self._sprayer_fleet.metrics()

    def _build_sprayer_fleet(
        self, config: SprayerFleetConfig | dict[str, object] | None
    ) -> SprayerFleet | None:
        """Equip the farm with finite tanks, or leave spray capacity unlimited."""
        if config is None:
            return None
        return SprayerFleet(
            config=SprayerFleetConfig.model_validate(config),
            rows=self._field.rows,
            cols=self._field.cols,
        )

    def _apply_resistance_frequency(self, frequency: float) -> None:
        """Set initial herbicide resistance frequency across the field."""
        if np.isclose(frequency, 0.01, rtol=0.0, atol=0.0):
            return
        for r in range(self._field.rows):
            for c in range(self._field.cols):
                self._field.pests[r][c].resistance_freq = frequency
                self._field.secondary_pests[r][c].resistance_freq = frequency
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
        - drone_stream: scheduled mobile drone imagery
        - yield_stream: harvest-time yield observations
        """
        sat_dim = self._satellite.output_dim
        trap_dim = len(self._traps) * PheromoneTrap(row=0, col=0).output_dim
        weather_dim = len(self._weather_stations) * AgWeatherStation(row=0, col=0).output_dim
        soil_dim = len(self._soil_sensors) * SoilSensor(row=0, col=0).output_dim
        drone_dim = self._drone_imager.output_dim
        yield_dim = self._yield_monitor.output_dim

        self._streams = [
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=sat_dim,
                label="satellite_indices",
                current_data=np.zeros(sat_dim),
                metadata=self._satellite_metadata(),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=trap_dim,
                label="pheromone_traps",
                current_data=np.zeros(trap_dim),
                metadata=self._trap_metadata(),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=weather_dim,
                label="weather_observations",
                current_data=np.zeros(weather_dim),
                metadata=self._weather_metadata(),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=soil_dim,
                label="soil_moisture",
                current_data=np.zeros(soil_dim),
                metadata=self._soil_metadata(),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=drone_dim,
                label="drone_imagery",
                current_data=np.zeros(drone_dim),
                metadata=self._drone_metadata(),
            ),
            Stream(
                stream_type=StreamType.RAW,
                dimensionality=yield_dim,
                label="yield_monitor",
                current_data=np.zeros(yield_dim),
                metadata=self._yield_metadata(),
            ),
        ]

    def _satellite_metadata(self) -> StreamMetadata:
        """Declare static zone geometry and dynamic revisit coordinates."""
        coordinates: list[tuple[float, ...] | None] = []
        footprints: list[tuple[float, ...] | None] = []
        resolutions: list[float | None] = []
        for zone_row, zone_col in self._zone_indices():
            (row, col), footprint = self._zone_geometry(zone_row, zone_col)
            for _ in range(3):
                coordinates.append((row, col))
                footprints.append(footprint)
                resolutions.append(float(max(footprint)))
        return StreamMetadata(
            coordinates=coordinates,
            sensor_coordinates=list(coordinates),
            modality=["ndvi", "ndre", "chlorophyll"] * (len(coordinates) // 3),
            identity=[None] * len(coordinates),
            footprints=footprints,
            resolution=resolutions,
        )

    def _trap_metadata(self) -> StreamMetadata:
        """Declare fixed point geometry for each trap feature block."""
        coordinates = [
            (float(trap.row), float(trap.col))
            for trap in self._traps
            for _ in range(trap.output_dim)
        ]
        return StreamMetadata(
            coordinates=list(coordinates),
            sensor_coordinates=list(coordinates),
            modality=["catch_count", "resistance_proxy"] * len(self._traps),
            identity=[None] * len(coordinates),
            footprints=[(0.0, 0.0)] * len(coordinates),
            resolution=[0.0] * len(coordinates),
        )

    def _weather_metadata(self) -> StreamMetadata:
        """Declare fixed point geometry for each weather feature block."""
        coordinates = [
            (float(station.row), float(station.col))
            for station in self._weather_stations
            for _ in range(station.output_dim)
        ]
        modalities: list[str | None] = [
            "temperature",
            "humidity",
            "wind_speed",
            "wind_direction",
            "precipitation",
        ]
        return StreamMetadata(
            coordinates=list(coordinates),
            sensor_coordinates=list(coordinates),
            modality=modalities * len(self._weather_stations),
            identity=[None] * len(coordinates),
            footprints=[(0.0, 0.0)] * len(coordinates),
            resolution=[0.0] * len(coordinates),
        )

    def _soil_metadata(self) -> StreamMetadata:
        """Declare fixed point geometry for each soil feature block."""
        coordinates = [
            (float(sensor.row), float(sensor.col))
            for sensor in self._soil_sensors
            for _ in range(sensor.output_dim)
        ]
        return StreamMetadata(
            coordinates=list(coordinates),
            sensor_coordinates=list(coordinates),
            modality=["moisture", "temperature_proxy", "conductivity_proxy"]
            * len(self._soil_sensors),
            identity=[None] * len(coordinates),
            footprints=[(0.0, 0.0)] * len(coordinates),
            resolution=[0.0] * len(coordinates),
        )

    def _drone_metadata(self) -> StreamMetadata:
        """Declare the mobile drone's dynamic location and instrument contract."""
        return StreamMetadata(
            coordinates=[None] * self._drone_imager.output_dim,
            sensor_coordinates=None,
            modality=["pest_detection", "weed_detection", "crop_stress", "thermal_detection"],
            identity=["drone_imager"] * self._drone_imager.output_dim,
            footprints=[(1.0, 1.0)] * self._drone_imager.output_dim,
            resolution=[1.0] * self._drone_imager.output_dim,
        )

    def _yield_metadata(self) -> StreamMetadata:
        """Declare fixed yield-zone geometry and retrospective context."""
        coordinates: list[tuple[float, ...] | None] = []
        footprints: list[tuple[float, ...] | None] = []
        resolutions: list[float | None] = []
        for zone in range(self._yield_monitor.n_zones):
            row_start = zone * self._field.rows // self._yield_monitor.n_zones
            row_end = (zone + 1) * self._field.rows // self._yield_monitor.n_zones
            height = max(row_end - row_start, 1)
            coordinates.append(
                (float(row_start + (height - 1) / 2.0), float(self._field.cols - 1) / 2.0)
            )
            footprints.append((float(height), float(self._field.cols)))
            resolutions.append(float(max(height, self._field.cols)))
        return StreamMetadata(
            coordinates=coordinates,
            sensor_coordinates=list(coordinates),
            modality=["yield_context"] * self._yield_monitor.n_zones,
            identity=[f"yield_zone_{zone}" for zone in range(self._yield_monitor.n_zones)],
            footprints=footprints,
            resolution=resolutions,
        )

    def _zone_indices(self) -> list[tuple[int, int]]:
        return [
            (zone_row, zone_col)
            for zone_row in range(self._satellite.zone_rows)
            for zone_col in range(self._satellite.zone_cols)
        ]

    def _zone_geometry(
        self, zone_row: int, zone_col: int
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        row_start = zone_row * self._field.rows // self._satellite.zone_rows
        row_end = (zone_row + 1) * self._field.rows // self._satellite.zone_rows
        col_start = zone_col * self._field.cols // self._satellite.zone_cols
        col_end = (zone_col + 1) * self._field.cols // self._satellite.zone_cols
        height = max(row_end - row_start, 1)
        width = max(col_end - col_start, 1)
        return (
            (
                float(row_start + (height - 1) / 2.0),
                float(col_start + (width - 1) / 2.0),
            ),
            (float(height), float(width)),
        )

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

    def get_location_frame(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Return the inclusive CropField coordinate frame."""
        return ((0, 0), (self._field.rows - 1, self._field.cols - 1))

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
    ) -> EventLocation | None:
        """Infer location from tiered, normalized evidence and declared geometry."""
        streams_by_label = {stream.label: stream for stream in self._streams}
        candidates: list[tuple[int, float, int, EventLocation]] = []
        for data, label in zip(stream_data, stream_labels, strict=False):
            stream = streams_by_label.get(label)
            if stream is None or data.size == 0 or stream.metadata is None:
                continue
            coordinates = stream.metadata.sensor_coordinates or stream.metadata.coordinates
            if coordinates is None:
                continue
            magnitudes = np.abs(data).astype(np.float64, copy=True)
            finite = np.isfinite(magnitudes)
            magnitudes[~finite] = 0.0
            if not np.any(finite):
                continue
            scale = float(np.sqrt(np.mean(magnitudes**2)))
            if scale <= 0.0:
                continue
            peak_idx = int(np.argmax(magnitudes))
            if peak_idx >= len(coordinates) or coordinates[peak_idx] is None:
                continue
            coordinate = coordinates[peak_idx]
            assert coordinate is not None
            modalities = stream.metadata.modality or []
            detection = any(
                any(
                    term in (modality or "").lower()
                    for term in ("pest_detection", "catch_count", "trap")
                )
                for modality in modalities
            )
            tier = 0 if detection else 1
            candidates.append(
                (
                    tier,
                    float(magnitudes[peak_idx] / scale),
                    peak_idx,
                    (int(round(coordinate[0])), int(round(coordinate[1]))),
                )
            )
        if not candidates:
            return None
        return min(candidates, key=lambda candidate: (candidate[0], -candidate[1]))[3]

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

    def _spray_budget_remaining_value(self) -> int | None:
        if self._spray_budget is None:
            return None
        if self._spray_budget_window < 0:
            return self._spray_budget.capacity
        return self._spray_budget_remaining

    def _refresh_spray_budget(self) -> None:
        """Refill spray capacity at the first request in each interval."""
        if self._spray_budget is None:
            return
        window = self._current_step // self._spray_budget.interval_steps
        if window != self._spray_budget_window:
            self._spray_budget_window = window
            self._spray_budget_remaining = self._spray_budget.capacity

    def dispatch_spray(self, row: int, col: int) -> bool:
        """Spot-spray one cell if permission and physical capacity both allow it.

        Regulatory permission is checked before equipment so a request refused
        by a quota does not consume product from a tank.
        """
        if row < 0 or col < 0 or row >= self._field.rows or col >= self._field.cols:
            return False
        self._spray_attempts += 1
        self._refresh_spray_budget()
        if self._spray_budget is not None and self._spray_budget_remaining == 0:
            self._sprays_denied += 1
            return False
        if self._sprayer_fleet is not None and not self._sprayer_fleet.request_spot_application(
            row, col, self._current_step
        ):
            self._sprays_denied += 1
            return False
        self._field.apply_pesticide(row, col, SPRAY_EFFICACY, self.rng)
        if self._spray_budget is not None:
            self._spray_budget_remaining -= 1
        self._sprays_applied += 1
        return True

    def broadcast_spray(self, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Treat many cells in one boom pass and return the cells treated.

        Broadcast volume lives on the boom sprayer, not on the drones, so a
        whole-field pass stays available even when spot capacity is exhausted:
        finite tanks make targeting scarce without capping pesticide load.
        Without a fleet configured this is one unlimited spot spray per cell.
        """
        in_bounds = [
            (row, col)
            for row, col in cells
            if 0 <= row < self._field.rows and 0 <= col < self._field.cols
        ]
        if self._sprayer_fleet is None:
            return [(row, col) for row, col in in_bounds if self.dispatch_spray(row, col)]
        self._spray_attempts += len(in_bounds)
        served = self._sprayer_fleet.request_broadcast_pass(in_bounds, self._current_step)
        for row, col in served:
            self._field.apply_pesticide(row, col, SPRAY_EFFICACY, self.rng)
        self._sprays_applied += len(served)
        self._sprays_denied += len(in_bounds) - len(served)
        return served

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

        ordered_targets = targets
        if self._spray_budget is not None or self._sprayer_fleet is not None:
            ordered_targets = sorted(
                targets,
                key=lambda target: target.cop_threat_level,
                reverse=True,
            )
        for target in ordered_targets:
            row, col = target.location
            before = self._pest_severity(row, col)
            dispatched = self.dispatch_spray(row, col)
            after = self._pest_severity(row, col)

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
        return self._field.cell_pest_density(row, col)

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
        satellite_stream = self._streams[0]
        satellite_metadata = satellite_stream.metadata
        if satellite_metadata is None or satellite_metadata.sensor_coordinates is None:
            raise RuntimeError("satellite metadata must declare static sensor coordinates")
        if sat_obs is not None:
            satellite_stream.metadata = satellite_metadata.model_copy(
                update={"coordinates": list(satellite_metadata.sensor_coordinates)}
            )
            satellite_stream.update(
                sat_obs,
                np.full(
                    satellite_stream.dimensionality,
                    ObservationStatus.OBSERVED.value,
                    dtype="<U8",
                ),
            )
        else:
            satellite_stream.metadata = satellite_metadata.model_copy(
                update={"coordinates": [None] * satellite_stream.dimensionality}
            )
            satellite_stream.update(
                satellite_stream.current_data.copy(),
                np.full(
                    satellite_stream.dimensionality,
                    ObservationStatus.MISSING.value,
                    dtype="<U8",
                ),
            )

        trap_parts = [
            trap.observe(self._field.pests[trap.row][trap.col], time_step, self.rng)
            for trap in self._traps
        ]
        self._streams[1].update(
            np.concatenate(trap_parts),
            np.full(
                self._streams[1].dimensionality,
                ObservationStatus.OBSERVED.value,
                dtype="<U8",
            ),
        )

        weather_parts = [ws.observe(self._weather, self.rng) for ws in self._weather_stations]
        self._streams[2].update(
            np.concatenate(weather_parts),
            np.full(
                self._streams[2].dimensionality,
                ObservationStatus.OBSERVED.value,
                dtype="<U8",
            ),
        )

        soil_parts = [
            ss.observe(self._field.crops[ss.row][ss.col], self.rng) for ss in self._soil_sensors
        ]
        self._streams[3].update(
            np.concatenate(soil_parts),
            np.full(
                self._streams[3].dimensionality,
                ObservationStatus.OBSERVED.value,
                dtype="<U8",
            ),
        )

        drone_row, drone_col = self._drone_location(time_step)
        drone_observation = self._drone_imager.observe(
            self._field.crops[drone_row][drone_col],
            self._observable_pest(drone_row, drone_col),
            self._field.weeds[drone_row][drone_col],
            self.rng,
        )
        drone_stream = self._streams[4]
        if drone_stream.metadata is not None:
            drone_stream.metadata = drone_stream.metadata.model_copy(
                update={
                    "coordinates": [(float(drone_row), float(drone_col))]
                    * drone_stream.dimensionality
                }
            )
        drone_stream.update(
            drone_observation,
            np.full(
                drone_stream.dimensionality,
                ObservationStatus.OBSERVED.value,
                dtype="<U8",
            ),
        )

        yield_stream = self._streams[5]
        yield_observation = self._yield_monitor.observe(self._field.crops, self.rng)
        if yield_observation is None:
            if yield_stream.metadata is not None:
                yield_stream.metadata = yield_stream.metadata.model_copy(
                    update={
                        "coordinates": [None] * yield_stream.dimensionality,
                        "identity": [None] * yield_stream.dimensionality,
                    }
                )
            yield_stream.update(
                np.zeros(yield_stream.dimensionality),
                np.full(
                    yield_stream.dimensionality,
                    ObservationStatus.MISSING.value,
                    dtype="<U8",
                ),
            )
        else:
            if yield_stream.metadata is not None:
                yield_stream.metadata = yield_stream.metadata.model_copy(
                    update={
                        "coordinates": list(
                            yield_stream.metadata.sensor_coordinates
                            or [None] * yield_stream.dimensionality
                        ),
                        "identity": [
                            f"yield_zone_{zone}" for zone in range(yield_stream.dimensionality)
                        ],
                    }
                )
            yield_stream.update(
                yield_observation,
                np.full(
                    yield_stream.dimensionality,
                    ObservationStatus.OBSERVED.value,
                    dtype="<U8",
                ),
            )

    def _observable_pest(self, row: int, col: int) -> PestPopulation:
        """Pest signal visible to imagery, including the secondary species."""
        primary = self._field.pests[row][col]
        if not self._field.ecology.enabled:
            return primary
        observable = primary.clone()
        observable.density = self._field.cell_pest_density(row, col)
        return observable

    def _drone_location(self, time_step: int) -> tuple[int, int]:
        """Return a deterministic geography-only flight-plan location."""
        flat_index = time_step % (self._field.rows * self._field.cols)
        return divmod(flat_index, self._field.cols)

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
