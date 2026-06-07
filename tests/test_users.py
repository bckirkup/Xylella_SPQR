"""Unit tests for agricultural user profiles."""

from __future__ import annotations

import numpy as np

from grain_guard.users.ag_users import create_ag_users


class TestAgUsers:
    def test_creates_two_users(self) -> None:
        users = create_ag_users(n_signal_dims=10)
        assert len(users) == 2

    def test_user_names(self) -> None:
        users = create_ag_users(n_signal_dims=10)
        names = {u.name for u in users}
        assert "Agronomist" in names
        assert "Farm Manager" in names

    def test_priority_vectors_orthogonal(self) -> None:
        users = create_ag_users(n_signal_dims=20)
        dot = float(np.dot(users[0].priority_vector, users[1].priority_vector))
        assert abs(dot) < 0.01

    def test_priority_vectors_normalized(self) -> None:
        users = create_ag_users(n_signal_dims=20)
        for u in users:
            norm = float(np.linalg.norm(u.priority_vector))
            assert abs(norm - 1.0) < 0.01

    def test_attention_budgets(self) -> None:
        users = create_ag_users(n_signal_dims=10)
        for u in users:
            assert u.attention_budget > 0
