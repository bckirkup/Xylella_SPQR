"""Weather gating of pesticide applications: wind blocks, rain washes off.

A spray decision is not free of the sky it is made under. Wind above the label
cut-off makes an application illegal and physically useless because the product
drifts off target, and rain during the application washes product off the leaf
before it can act. Both are properties of the weather at the moment of
application, not of the target, so a detector cannot earn its way out of them --
they price the *timing* of a response rather than its accuracy.

Only the instantaneous application is modelled. The field carries no pesticide
residue state, so post-application wash-off of a residue that is still working
several steps later is out of scope rather than approximated.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from grain_guard.environment.weather import AgWeather

DEFAULT_WIND_BLOCK_SPEED_MPS = 6.0
"""Wind at or above which an application is refused (about 13 mph)."""

DEFAULT_RAIN_WASHOFF_FULL_MM = 4.0
"""Rainfall at which wash-off removes the full washable share of the dose."""

DEFAULT_WASHOFF_STRENGTH = 1.0
"""Share of the dose rain can wash off at ``rain_washoff_full_mm``."""


class SprayWeatherConfig(BaseModel):
    """Weather conditions under which an application is refused or degraded.

    Attributes:
        wind_block_speed_mps: wind speed at or above which an application is
            refused outright, because drift puts the product off target.
        rain_washoff_full_mm: rainfall during the application at which the full
            washable share of the dose is lost; wash-off scales linearly up to
            this depth.
        washoff_strength: share of the dose that rain can remove. ``1.0`` lets
            heavy enough rain waste an application entirely, which is also the
            only way rain alone refuses one.
    """

    wind_block_speed_mps: float = Field(default=DEFAULT_WIND_BLOCK_SPEED_MPS, gt=0.0)
    rain_washoff_full_mm: float = Field(default=DEFAULT_RAIN_WASHOFF_FULL_MM, gt=0.0)
    washoff_strength: float = Field(default=DEFAULT_WASHOFF_STRENGTH, ge=0.0, le=1.0)


@dataclass
class SprayWeatherCounters:
    """Application decisions the weather gate has taken.

    Attributes:
        requests: application decisions the gate was asked to rule on.
        wind_blocked: decisions refused because the wind was too strong.
        rain_blocked: decisions refused because rain would waste the whole dose.
        allowed: decisions the gate let through.
        washed: allowed decisions that lost part of their dose to rain.
        retained_efficacy_sum: retained-efficacy fractions of allowed decisions.
    """

    requests: int = 0
    wind_blocked: int = 0
    rain_blocked: int = 0
    allowed: int = 0
    washed: int = 0
    retained_efficacy_sum: float = 0.0


class SprayWeatherGate:
    """Rules on each application against the weather it would be made in.

    One gate decision covers one application decision: a spot request is one
    decision, and a boom pass is one decision for the whole pass, because the
    whole pass happens under the same weather.
    """

    def __init__(self, config: SprayWeatherConfig | None = None) -> None:
        self.config = config or SprayWeatherConfig()
        self.counters = SprayWeatherCounters()

    def wind_blocks(self, weather: AgWeather) -> bool:
        """Whether the wind is strong enough to put the product off target."""
        return weather.wind_speed >= self.config.wind_block_speed_mps

    def retained_fraction(self, weather: AgWeather) -> float:
        """Share of the dose that survives the rain falling on it."""
        washable = min(1.0, weather.precipitation / self.config.rain_washoff_full_mm)
        return max(0.0, 1.0 - self.config.washoff_strength * washable)

    def effective_efficacy(self, base_efficacy: float, weather: AgWeather) -> float | None:
        """Efficacy this application would achieve, or ``None`` if refused."""
        self.counters.requests += 1
        if self.wind_blocks(weather):
            self.counters.wind_blocked += 1
            return None
        retained = self.retained_fraction(weather)
        if retained <= 0.0:
            self.counters.rain_blocked += 1
            return None
        self.counters.allowed += 1
        self.counters.retained_efficacy_sum += retained
        if retained < 1.0:
            self.counters.washed += 1
        return base_efficacy * retained

    def metrics(self) -> dict[str, float | int]:
        """Weather-gate settings and the decisions taken under them."""
        allowed = self.counters.allowed
        return {
            "wind_block_speed_mps": self.config.wind_block_speed_mps,
            "rain_washoff_full_mm": self.config.rain_washoff_full_mm,
            "washoff_strength": self.config.washoff_strength,
            "requests": self.counters.requests,
            "wind_blocked": self.counters.wind_blocked,
            "rain_blocked": self.counters.rain_blocked,
            "allowed": allowed,
            "washed": self.counters.washed,
            "mean_retained_efficacy": (
                self.counters.retained_efficacy_sum / allowed if allowed else 0.0
            ),
            "allowed_share": (allowed / self.counters.requests if self.counters.requests else 0.0),
        }
