"""Tests for grain_guard.runner (domain-runner integration)."""

from __future__ import annotations

import pytest
from domain_runner.layer import DomainOnlyLayer
from domain_runner.single import run_simulation
from domain_runner.types import RunContext

from grain_guard.runner import GrainDomainHooks, run_grain_simulation


@pytest.mark.integration
class TestGrainRunner:
    def test_domain_only_simulation(self) -> None:
        run = RunContext(
            steps=5,
            seed=42,
            domain_config={"grid_rows": 8, "grid_cols": 8, "landscape": "monoculture"},
            layer="domain_only",
        )
        result = run_simulation(GrainDomainHooks(), DomainOnlyLayer(), run)
        assert result.steps_completed == 5
        assert "final_health" in result.domain_metrics

    @pytest.mark.smoke
    def test_run_grain_simulation_entry(self) -> None:
        hooks = GrainDomainHooks()
        run = hooks.load_run_context(
            cli_overrides={
                "domain": {"steps": 10, "grid_rows": 8, "grid_cols": 8},
                "layer": "domain_only",
            }
        )
        result = run_grain_simulation(run)
        assert result.domain == "grain_guard"
