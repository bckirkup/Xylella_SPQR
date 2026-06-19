"""Tests for head-to-head architecture comparison harness."""

from __future__ import annotations

from grain_guard.comparison import (
    ComparisonConfig,
    format_comparison_json,
    format_comparison_table,
    run_comparison,
)


class TestComparison:
    def test_run_baselines_only(self) -> None:
        config = ComparisonConfig(
            steps=10,
            grid_rows=5,
            grid_cols=5,
            seed=42,
            landscape="monoculture",
        )
        results = run_comparison(config)
        assert len(results) == 4
        names = [r.name for r in results]
        assert "A0 Human IPM" in names
        assert "A3 Centralized Platform" in names

    def test_deterministic(self) -> None:
        config = ComparisonConfig(
            steps=15,
            grid_rows=5,
            grid_cols=5,
            seed=99,
            landscape="orchard",
        )
        r1 = run_comparison(config)
        r2 = run_comparison(config)
        for a, b in zip(r1, r2, strict=True):
            assert a.n_sprays == b.n_sprays
            assert a.final_yield == b.final_yield
            assert a.total_cost == b.total_cost

    def test_format_table(self) -> None:
        config = ComparisonConfig(steps=5, grid_rows=5, grid_cols=5, seed=42)
        results = run_comparison(config)
        table = format_comparison_table(results)
        assert "Architecture" in table
        assert "A0 Human IPM" in table

    def test_pressure_and_resistance_params(self) -> None:
        config = ComparisonConfig(
            steps=10,
            grid_rows=5,
            grid_cols=5,
            seed=42,
            landscape="orchard",
            pest_intro_probability=0.05,
            pest_density_boost=2.0,
            weed_density_base=5.0,
            resistance_initial_frequency=0.20,
        )
        results = run_comparison(config)
        assert len(results) == 4
        assert all(r.final_yield >= 0.0 for r in results)

    def test_format_json(self) -> None:
        config = ComparisonConfig(steps=5, grid_rows=5, grid_cols=5, seed=42)
        results = run_comparison(config)
        j = format_comparison_json(results)
        assert '"architecture"' in j
        assert '"final_yield"' in j

    def test_landscape_variants(self) -> None:
        for landscape in ("monoculture", "orchard", "intercrop"):
            config = ComparisonConfig(
                steps=10,
                grid_rows=5,
                grid_cols=5,
                seed=42,
                landscape=landscape,
            )
            results = run_comparison(config)
            assert len(results) == 4
