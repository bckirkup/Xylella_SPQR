"""Tests for the GrainGuard command-line entry point."""

from __future__ import annotations

from pathlib import Path

import pytest

from grain_guard.cli import main


def test_console_script_uses_sys_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "results.json"
    monkeypatch.setattr(
        "sys.argv",
        ["grain-guard", "sim", "--steps", "3", "--output", str(output)],
    )

    main()

    assert "Steps:   3" in capsys.readouterr().out
    assert output.exists()
