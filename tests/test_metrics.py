"""Unit tests for agricultural metrics."""

from __future__ import annotations

from grain_guard.metrics.ag_metrics import AgMetrics, StepMetrics


class TestAgMetrics:
    def test_record_step(self) -> None:
        m = AgMetrics()
        sm = StepMetrics(
            time_step=0,
            n_sprays=5.0,
            spray_volume_L=10.0,
            false_sprays=1.0,
            missed_cells=2.0,
            mean_resistance_freq=0.05,
        )
        m.record_step(sm)
        assert m.total_sprays == 5.0
        assert m.total_spray_volume == 10.0
        assert len(m.resistance_trajectory) == 1

    def test_false_spray_rate(self) -> None:
        m = AgMetrics(total_sprays=10.0, total_false_sprays=3.0)
        assert abs(m.false_spray_rate - 0.3) < 0.01

    def test_yield_protected(self) -> None:
        m = AgMetrics()
        m.record_step(StepMetrics(time_step=0, mean_yield_potential=0.8))
        m.record_step(StepMetrics(time_step=1, mean_yield_potential=0.6))
        assert abs(m.yield_protected - 0.7) < 0.01

    def test_total_cost(self) -> None:
        m = AgMetrics()
        m.record_step(
            StepMetrics(time_step=0, surveillance_cost=1.0, response_cost=2.0, damage_cost=3.0)
        )
        assert m.total_cost == 6.0

    def test_summary_keys(self) -> None:
        m = AgMetrics()
        m.record_step(StepMetrics(time_step=0))
        s = m.summary()
        assert "yield_protected" in s
        assert "total_spray_volume" in s
        assert "false_spray_rate" in s
        assert "final_resistance_freq" in s

    def test_detection_latency(self) -> None:
        m = AgMetrics()
        m.record_detection_latency(3)
        m.record_detection_latency(5)
        assert m.mean_detection_latency == 4.0
