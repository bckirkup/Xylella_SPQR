"""Phased deployment configuration for GrainGuard (spec §8)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from grain_guard.environment.field import LandscapeType


class DeploymentPhase(BaseModel):
    """Hardware/sensor availability for one deployment phase."""

    name: str
    n_scout_drones: int = Field(ge=0)
    n_spray_drones: int = Field(ge=0)
    n_ai_tractors: int = Field(ge=0)
    n_traps: int = Field(ge=0)
    n_weather_stations: int = Field(ge=0)
    n_soil_sensors: int = Field(ge=0)
    has_satellite: bool = True
    landscape: LandscapeType = Field(default=LandscapeType.MONOCULTURE)
    area_ha: int = Field(default=500, ge=1)
    grid_rows: int = Field(default=20, ge=1)
    grid_cols: int = Field(default=20, ge=1)


class PhasedDeployment(BaseModel):
    """Three-season deployment plan (spec §8).

    Season 1: 500 ha monoculture pilot.
    Season 2: 2,000 ha expansion + first orchard trial.
    Season 3: Full fleet + intercropping plots.
    """

    phases: list[DeploymentPhase] = Field(default_factory=list)

    def model_post_init(self, _context: object) -> None:
        if not self.phases:
            self.phases = self._default_phases()

    @staticmethod
    def _default_phases() -> list[DeploymentPhase]:
        return [
            DeploymentPhase(
                name="Season 1: Monoculture Pilot",
                n_scout_drones=3,
                n_spray_drones=1,
                n_ai_tractors=0,
                n_traps=10,
                n_weather_stations=2,
                n_soil_sensors=4,
                landscape=LandscapeType.MONOCULTURE,
                area_ha=500,
                grid_rows=20,
                grid_cols=20,
            ),
            DeploymentPhase(
                name="Season 2: Expansion + Orchard",
                n_scout_drones=10,
                n_spray_drones=3,
                n_ai_tractors=1,
                n_traps=20,
                n_weather_stations=4,
                n_soil_sensors=8,
                landscape=LandscapeType.ORCHARD,
                area_ha=2000,
                grid_rows=30,
                grid_cols=30,
            ),
            DeploymentPhase(
                name="Season 3: Full Fleet + Intercrop",
                n_scout_drones=20,
                n_spray_drones=5,
                n_ai_tractors=2,
                n_traps=30,
                n_weather_stations=6,
                n_soil_sensors=12,
                landscape=LandscapeType.INTERCROP,
                area_ha=5000,
                grid_rows=40,
                grid_cols=40,
            ),
        ]
