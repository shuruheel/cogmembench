from __future__ import annotations

from pathlib import Path

import pytest

import cogmembench.runners.run as run_module
from cogmembench import cli


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repoint the `ROOT` name bound in `cogmembench.cli` and
    `cogmembench.runners.run` to a throwaway directory.

    CLI command handlers and `BenchmarkRunner` hardcode `ROOT / "results" / ...`
    (and similar) instead of taking an output directory argument, so tests that
    call them directly must repoint `ROOT` or they would read and write inside
    the real repository tree. `configs/` holds static fixtures that handlers
    still read by path, so it is symlinked in read-only from the real root
    rather than copied.
    """
    real_root = cli.ROOT
    for relative in (
        "scenarios/fixtures",
        "scenarios/held_out",
        "results/raw",
        "results/evaluated",
        "results/aggregated",
        "results/traces",
        "results/plots",
        "docs",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / "configs").symlink_to(real_root / "configs")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(run_module, "ROOT", tmp_path)
    return tmp_path
