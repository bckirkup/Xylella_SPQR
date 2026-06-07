"""Factory for agricultural user profiles (spec §6)."""

from __future__ import annotations

import numpy as np
from tattletots.models.user import User


def create_ag_users(n_signal_dims: int = 10) -> list[User]:
    """Create the two agricultural user profiles.

    Agronomist (Field-Level): daily decisions, pest/weed scouting, spray timing.
    Farm Manager (Operation-Level): weekly, strategic budget and resistance management.

    Args:
        n_signal_dims: Dimensionality of the signal/priority vectors.

    Returns:
        List of two User objects.
    """
    agronomist_priority = np.zeros(n_signal_dims)
    agronomist_priority[: n_signal_dims // 2] = 1.0
    norm = float(np.linalg.norm(agronomist_priority))
    if norm > 0:
        agronomist_priority /= norm

    manager_priority = np.zeros(n_signal_dims)
    manager_priority[n_signal_dims // 2 :] = 1.0
    norm = float(np.linalg.norm(manager_priority))
    if norm > 0:
        manager_priority /= norm

    return [
        User(
            name="Agronomist",
            attention_budget=1.0,
            priority_vector=agronomist_priority,
        ),
        User(
            name="Farm Manager",
            attention_budget=0.5,
            priority_vector=manager_priority,
        ),
    ]
