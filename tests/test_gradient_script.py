"""Output-directory validation for the gradient measurement script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> ModuleType:
    """Import the measurement script, which lives outside the package."""
    path = REPO_ROOT / "scripts" / "run_grain_gradient.py"
    spec = importlib.util.spec_from_file_location("run_grain_gradient", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


class TestSafeOutputDir:
    @pytest.mark.parametrize(
        "raw",
        ["grain_gradient_output", "docs/grain_detector_gradient", "a/b/c", "out-2"],
    )
    def test_accepts_relative_names_under_the_repo(self, raw: str) -> None:
        resolved = SCRIPT._safe_output_dir(raw)
        assert resolved == REPO_ROOT / raw
        assert resolved.is_relative_to(REPO_ROOT)

    @pytest.mark.parametrize(
        "raw",
        ["/tmp/x", "../x", "./x", "a/../b", "", "a//b", "~/x", "a b", "out.json"],
    )
    def test_rejects_absolute_and_traversing_names(self, raw: str) -> None:
        with pytest.raises(ValueError, match="relative directory"):
            SCRIPT._safe_output_dir(raw)
