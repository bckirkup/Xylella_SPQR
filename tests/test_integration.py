"""Integration tests: GrainGuard adapter running through the TattleTots World engine."""

from __future__ import annotations

import pytest
from tattletots.engine.config import SimulationConfig
from tattletots.engine.world import World

from grain_guard.adapter.grain_adapter import GrainGuardAdapter
from grain_guard.environment.field import LandscapeType


def _make_world(
    adapter: GrainGuardAdapter,
    *,
    initial_pop: int = 10,
    max_pop: int = 50,
    seed: int = 42,
) -> World:
    """Wire a GrainGuard adapter into a TattleTots World."""
    config = SimulationConfig(
        initial_population=initial_pop,
        max_population=max_pop,
        seed=seed,
    )
    world = World(config=config)
    for stream in adapter.get_streams():
        world.add_stream(stream)
    for user in adapter.get_users():
        world.add_user(user)
    world.seed_population()
    return world


def _run_integrated(adapter: GrainGuardAdapter, world: World, steps: int) -> list[object]:
    """Run the adapter + world loop for *steps*, return step records."""
    records = []
    for t in range(steps):
        adapter.step(t)
        world.set_event_state(adapter.get_active_locations(t))
        records.append(world.step())
    return records


@pytest.mark.integration
class TestWorldIntegration:
    """Verify that the GrainGuard adapter produces a valid TattleTots simulation."""

    def test_streams_registered(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=42)
        world = _make_world(adapter)
        # 4 raw streams + 10 residual streams from agents
        assert len([s for s in world.streams.values() if s.stream_type.value == "raw"]) == 4

    def test_users_registered(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=42)
        world = _make_world(adapter)
        assert len(world.users) == 2

    def test_agents_seeded(self) -> None:
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=42)
        world = _make_world(adapter, initial_pop=15)
        assert world.living_population == 15

    @pytest.mark.parametrize(
        "landscape",
        [LandscapeType.MONOCULTURE, LandscapeType.ORCHARD, LandscapeType.INTERCROP],
    )
    def test_50_step_simulation(self, landscape: LandscapeType) -> None:
        """Run 50 integrated steps; agents should survive and crops remain viable."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, landscape=landscape, seed=42)
        world = _make_world(adapter)
        _run_integrated(adapter, world, 50)
        assert world.living_population > 0
        assert adapter.field.mean_crop_health() > 0.0

    def test_ground_truth_events_propagate(self) -> None:
        """Ground truth events should trigger during the integrated run."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        world = _make_world(adapter)
        events = 0
        for t in range(200):
            adapter.step(t)
            locations = adapter.get_active_locations(t)
            world.set_event_state(locations)
            if locations:
                events += 1
            world.step()
        assert events > 0

    def test_trophic_levels_form(self) -> None:
        """After enough steps, trophic hierarchy should emerge."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        world = _make_world(adapter)
        _run_integrated(adapter, world, 30)
        levels = world.trophic_levels
        assert len(levels) > 0
        # At minimum, basal agents at level 1.0 should exist
        assert any(v >= 1.0 for v in levels.values())

    def test_trust_updates_occur(self) -> None:
        """Users' trust states should change from the default after integrated run."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        world = _make_world(adapter)
        _run_integrated(adapter, world, 100)
        # At least one user should have non-default trust for some agent
        any_trust_change = False
        for user in world.users.values():
            if any(v != 0.5 for v in user.trust.values()):
                any_trust_change = True
                break
        assert any_trust_change

    def test_agent_reproduction(self) -> None:
        """Agents should reproduce during an integrated run."""
        adapter = GrainGuardAdapter(grid_rows=10, grid_cols=10, seed=42)
        world = _make_world(adapter, initial_pop=10, max_pop=50)
        _run_integrated(adapter, world, 100)
        # Population should have grown from reproduction
        assert world.living_population > 10 or len(world.agents) > 10

    def test_runner_tattletots_layer(self) -> None:
        """Full loop via domain-runner + TattleTots layer (COP dispatch included)."""
        from grain_guard.runner import GrainDomainHooks, run_grain_simulation

        hooks = GrainDomainHooks()
        run = hooks.load_run_context(
            cli_overrides={
                "domain": {"steps": 8, "grid_rows": 8, "grid_cols": 8},
                "layer": "tattletots",
                "simulation": {"initial_population": 8, "max_steps": 8, "seed": 42},
            }
        )
        result = run_grain_simulation(run)
        assert result.layer == "tattletots"
        assert result.steps_completed == 8
        ecology = result.domain_metrics["ecology"]
        assert ecology["initiation_is_degenerate"] is True
        assert ecology["initiation_degeneracy_reasons"]
        assert ecology["event_prevalence"] == 0.0

    def test_cost_computation(self) -> None:
        """Adapter cost model should return valid dict."""
        adapter = GrainGuardAdapter(grid_rows=8, grid_cols=8, seed=42)
        costs = adapter.compute_costs(n_escalations=10, n_correct=5, n_false_alarms=3, n_missed=2)
        assert "surveillance_cost" in costs
        assert "response_cost" in costs
        assert "damage_cost" in costs
        assert all(v >= 0 for v in costs.values())

    @pytest.mark.smoke
    def test_full_season_monoculture(self) -> None:
        """Full-season integration: 200 steps, monoculture landscape."""
        adapter = GrainGuardAdapter(
            grid_rows=15, grid_cols=15, landscape=LandscapeType.MONOCULTURE, seed=42
        )
        world = _make_world(adapter, initial_pop=15, max_pop=80)
        _run_integrated(adapter, world, 200)
        assert world.living_population > 0
        assert adapter.field.mean_crop_health() > 0.0
        assert adapter.field.mean_yield_potential() > 0.0
