"""Competing management architectures A0–A3."""

from __future__ import annotations

from grain_guard.architectures.a0_human_ipm import HumanIPM
from grain_guard.architectures.a1_ai_tractor import AITractor
from grain_guard.architectures.a2_prescription_drone import PrescriptionDrone
from grain_guard.architectures.a3_centralized_platform import CentralizedPlatform
from grain_guard.architectures.base import Architecture

__all__ = [
    "AITractor",
    "Architecture",
    "CentralizedPlatform",
    "HumanIPM",
    "PrescriptionDrone",
]
