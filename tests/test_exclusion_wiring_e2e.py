"""
End-to-end coverage for the exclusion wiring fix (Phase 0 / F2).

These tests drive the actual Typer command with the real BackupEngine -
nothing about the run is mocked - so they prove the full contract:

  1. `--exclude` patterns are persisted to config.json, AND
  2. the persisted patterns reach the current run's scan, AND
  3. patterns saved by earlier runs apply to later runs without the flag.

The user's real configuration is isolated by redirecting
`ConfigManager._get_config_dir` into pytest's tmp_path, so the developer's
actual config.json is never read or written.

A control test proves that `image.iso` is only excluded when a pattern says
so (it is not part of the built-in DEFAULT_EXCLUSIONS or
EXCLUDED_EXTENSIONS sets).
"""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smartbackup.cli import app
from smartbackup.config import ConfigManager

runner = CliRunner()
DEVICE = "ExclusionBox"


# --------------------------------------------------------------------------- #
# Fixtures & helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch) -> Path:
    """Redirect the persistent config into tmp_path; returns the config dir."""
    config_dir = tmp_path / "cfg"
    monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: config_dir)
    return config_dir


@pytest.fixture
def source(tmp_path: Path) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    (src / "file1.txt").write_text("keep me")
    (src / "image.iso").write_bytes(b"iso-bytes")
    return src


@pytest.fixture
def target(tmp_path: Path) -> Path:
    tgt = tmp_path / "target"
    tgt.mkdir()
    return tgt


def _invoke(source: Path, target: Path, *extra: str):
    """Run a real backup through the CLI; fails the test with CLI output."""
    result = runner.invoke(
        app,
        [
            "--source",
            str(source),
            "--target",
            str(target),
            "--device-name",
            DEVICE,
            *extra,
        ],
    )
    assert result.exit_code == 0, f"CLI failed (exit {result.exit_code}):\n{result.output}"
    return result


def _backup_root(target: Path) -> Path:
    return target / "Documents-Backup" / DEVICE


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class TestExcludeFlagEndToEnd:
    def test_flag_applies_to_the_current_run_and_persists(
        self, isolated_config: Path, source: Path, target: Path
    ):
        _invoke(source, target, "--exclude", "*.iso")

        # Applied immediately: excluded file absent, normal file present
        assert not (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()

        # Persisted: config.json now records the pattern
        config_file = isolated_config / "config.json"
        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

    def test_persisted_pattern_applies_on_later_runs_without_the_flag(
        self, isolated_config: Path, source: Path, target: Path
    ):
        # Run 1 persists the pattern
        _invoke(source, target, "--exclude", "*.iso")

        # Fresh backup medium (as if plugging in an empty drive)
        shutil.rmtree(target)
        target.mkdir()

        # Run 2 without the flag: the stored pattern still excludes
        _invoke(source, target)

        assert not (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()

    def test_patterns_written_before_the_run_still_apply(
        self, isolated_config: Path, source: Path, target: Path
    ):
        # A config.json written by an older version or edited by hand
        manager = ConfigManager()
        manager.add_exclusion("*.iso")

        _invoke(source, target)

        assert not (_backup_root(target) / "image.iso").exists()

    def test_control_without_pattern_the_file_is_backed_up(
        self, isolated_config: Path, source: Path, target: Path
    ):
        """Scientific control: no pattern -> no exclusion.

        Proves the other tests fail only because of the pattern, not
        because *.iso happens to be filtered by the built-in sets.
        """
        _invoke(source, target)

        assert (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()
