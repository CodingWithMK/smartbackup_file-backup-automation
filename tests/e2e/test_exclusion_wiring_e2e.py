"""
End-to-end coverage for the exclusion wiring fix (Phase 0 / F2).

Drives the real Typer command with the real BackupEngine (no mocks)
to prove `--exclude` persistence, immediate application, and cross-run reuse.
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


class TestExcludeFlagEndToEnd:
    def test_flag_applies_to_the_current_run_and_persists(
        self, isolated_config: Path, source: Path, target: Path
    ):
        _invoke(source, target, "--exclude", "*.iso")

        assert not (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()

        config_file = isolated_config / "config.json"
        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

    def test_persisted_pattern_applies_on_later_runs_without_the_flag(
        self, source: Path, target: Path
    ):
        _invoke(source, target, "--exclude", "*.iso")

        shutil.rmtree(target)
        target.mkdir()

        _invoke(source, target)

        assert not (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()

    def test_patterns_written_before_the_run_still_apply(
        self, source: Path, target: Path
    ):
        ConfigManager().add_exclusion("*.iso")

        _invoke(source, target)
        assert not (_backup_root(target) / "image.iso").exists()

    def test_control_without_pattern_the_file_is_backed_up(
        self, source: Path, target: Path
    ):
        """Scientific control: no pattern -> no exclusion."""
        _invoke(source, target)

        assert (_backup_root(target) / "image.iso").exists()
        assert (_backup_root(target) / "file1.txt").exists()
