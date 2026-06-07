"""Agricultural weather model: temperature, humidity, wind, precipitation, degree-days."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class AgWeather(BaseModel):
    """Weather state for a single time step.

    Drives pest phenology (growing degree-days), crop growth, and
    spray-drift calculations.
    """

    temperature: float = Field(default=20.0, description="Air temperature in °C")
    humidity: float = Field(default=0.6, ge=0.0, le=1.0, description="Relative humidity [0, 1]")
    wind_speed: float = Field(default=3.0, ge=0.0, description="Wind speed in m/s")
    wind_direction: float = Field(
        default=180.0, ge=0.0, lt=360.0, description="Wind direction in degrees from north"
    )
    precipitation: float = Field(default=0.0, ge=0.0, description="Precipitation in mm")
    solar_radiation: float = Field(default=15.0, ge=0.0, description="Solar radiation in MJ/m²/day")

    @property
    def growing_degree_days(self) -> float:
        """Daily GDD contribution using base 10 °C."""
        return max(0.0, self.temperature - 10.0)

    @property
    def spray_drift_risk(self) -> float:
        """Risk of spray drift [0, 1] based on wind speed."""
        return float(np.clip(self.wind_speed / 15.0, 0.0, 1.0))

    @property
    def is_spray_safe(self) -> bool:
        """Whether conditions allow safe spraying (low wind, no rain)."""
        return self.wind_speed < 10.0 and self.precipitation < 1.0

    def evapotranspiration_rate(self) -> float:
        """Simplified Hargreaves-style ET estimate (mm/day)."""
        return float(
            0.0023
            * (self.temperature + 17.8)
            * max(self.solar_radiation, 0.1) ** 0.5
            * max(self.temperature, 0.0)
        )
