"""
CLI wiring for restore conflict strategies (F3).

The restore engine has always carried a `ConflictResolution` enum, but the
command only exposed `--overwrite`, so NEWER was unreachable and RENAME was
never selected. These tests drive the real Typer command end to end:

  * `--conflict rename` keeps both files (local + renamed restored copy)
  * `--conflict newer` skips an older backup and overwrites a newer one
  * an unknown value exits 1 with a helpful message
  * `--overwrite` remains a working alias
  * `--conflict` wins when both flags are supplied
"""

import os
import time
from pathlib import Path

from typer.testing import CliRunner

from smartbackup.cli import app

runner = CliRunner()


def _backup_file(tmp_path: Path, content: str = "BACKUP CONTENT") -> Path:
    """Create a minimal backup tree and return the backed-up file."""
    backup_file = tmp_path / "backup" / "Documents-Backup" / "file1.txt"
    backup_file.parent.mkdir(parents=True)
    backup_file.write_text(content)
    return backup_file


def _target(tmp_path: Path, content: str = "LOCAL CONTENT") -> Path:
    """Create the restore destination with a conflicting local file."""
    target = tmp_path / "restored"
    target.mkdir()
    (target / "file1.txt").write_text(content)
    return target


def _invoke(tmp_path: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "restore",
            "--source",
            str(tmp_path / "backup"),
            "--target",
            str(tmp_path / "restored"),
            *extra,
        ],
    )


class TestRestoreConflictCli:
    def test_conflict_rename_keeps_both_files(self, tmp_path: Path):
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--conflict", "rename")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"
        renamed = list(target.glob("file1.restored-*.txt"))
        assert len(renamed) == 1, f"expected one renamed copy, got {renamed}"
        assert renamed[0].read_text() == "BACKUP CONTENT"

    def test_conflict_newer_skips_older_backup(self, tmp_path: Path):
        backup_file = _backup_file(tmp_path)
        target = _target(tmp_path)
        old = time.time() - 3600
        os.utime(backup_file, (old, old))

        result = _invoke(tmp_path, "--conflict", "newer")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_conflict_newer_overwrites_older_local_file(self, tmp_path: Path):
        _backup_file(tmp_path)
        target = _target(tmp_path)
        old = time.time() - 3600
        os.utime(target / "file1.txt", (old, old))

        result = _invoke(tmp_path, "--conflict", "newer")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "BACKUP CONTENT"

    def test_unknown_conflict_value_exits_1(self, tmp_path: Path):
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--conflict", "bogus")

        assert result.exit_code == 1
        assert "Invalid --conflict value" in result.output
        for valid in ("skip", "overwrite", "newer", "rename"):
            assert valid in result.output
        # The invalid value must not mutate the destination
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_overwrite_flag_alias_still_works(self, tmp_path: Path):
        """Regression: the pre-0.7 flag keeps its behavior."""
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--overwrite")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "BACKUP CONTENT"

    def test_conflict_wins_over_overwrite(self, tmp_path: Path):
        """When both are given, the explicit --conflict strategy takes precedence."""
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--overwrite", "--conflict", "skip")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"
