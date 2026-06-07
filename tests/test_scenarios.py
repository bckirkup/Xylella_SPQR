"""Unit tests for deployment scenarios."""

from __future__ import annotations

from grain_guard.environment.field import LandscapeType
from grain_guard.scenarios.phased_deployment import DeploymentPhase, PhasedDeployment


class TestPhasedDeployment:
    def test_default_phases(self) -> None:
        pd = PhasedDeployment()
        assert len(pd.phases) == 3

    def test_phase_names(self) -> None:
        pd = PhasedDeployment()
        assert "Season 1" in pd.phases[0].name
        assert "Season 2" in pd.phases[1].name
        assert "Season 3" in pd.phases[2].name

    def test_escalating_fleet(self) -> None:
        pd = PhasedDeployment()
        for i in range(len(pd.phases) - 1):
            assert pd.phases[i + 1].n_scout_drones >= pd.phases[i].n_scout_drones

    def test_landscape_progression(self) -> None:
        pd = PhasedDeployment()
        assert pd.phases[0].landscape == LandscapeType.MONOCULTURE
        assert pd.phases[1].landscape == LandscapeType.ORCHARD
        assert pd.phases[2].landscape == LandscapeType.INTERCROP

    def test_custom_phase(self) -> None:
        phase = DeploymentPhase(
            name="Custom",
            n_scout_drones=5,
            n_spray_drones=2,
            n_ai_tractors=1,
            n_traps=15,
            n_weather_stations=3,
            n_soil_sensors=6,
        )
        assert phase.n_scout_drones == 5
