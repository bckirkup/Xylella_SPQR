"""Agricultural weather station sensor (spec §4.4)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from grain_guard.environment.weather import AgWeather


class AgWeatherStation(BaseModel):
    """Fixed weather station providing local atmospheric readings.

    Drives degree-day pest phenology models and spray-window decisions.
    """

    row: int = Field(ge=0)
    col: int = Field(ge=0)

    def observe(self, weather: AgWeather, rng: np.random.Generator) -> NDArray[np.float64]:
        """Return [temp, humidity, wind_speed, wind_dir, precip] with sensor noise.

        Output dimensionality: 5.
        """
        return np.array(
            [
                weather.temperature + float(rng.normal(0, 0.5)),
                float(np.clip(weather.humidity + rng.normal(0, 0.02), 0.0, 1.0)),
                max(0.0, weather.wind_speed + float(rng.normal(0, 0.3))),
                weather.wind_direction % 360.0,
                max(0.0, weather.precipitation + float(rng.normal(0, 0.1))),
            ],
            dtype=np.float64,
        )

    @property
    def output_dim(self) -> int:
        return 5
