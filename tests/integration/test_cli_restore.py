"""
Integration tests for the `smartbackup restore` CLI command (F3, F7).
"""

import os
import time
from pathlib import Path

from typer.testing import CliRunner

from smartbackup.cli import app
from smartbackup.manifest.json_manifest import JsonManifestManager

runner = CliRunner()


def _backup_file(tmp_path: Path, content: str = "BACKUP CONTENT") -> Path:
    backup_file = tmp_path / "backup" / "Documents-Backup" / "file1.txt"
    backup_file.parent.mkdir(parents=True)
    backup_file.write_text(content)
    return backup_file


def _target(tmp_path: Path, content: str = "LOCAL CONTENT") -> Path:
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
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_overwrite_flag_alias_still_works(self, tmp_path: Path):
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--overwrite")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "BACKUP CONTENT"

    def test_conflict_wins_over_overwrite(self, tmp_path: Path):
        _backup_file(tmp_path)
        target = _target(tmp_path)

        result = _invoke(tmp_path, "--overwrite", "--conflict", "skip")

        assert result.exit_code == 0, result.output
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"


class TestRestoreListAndManifestInfoCli:
    """CLI tests for F7: RestoreEngine.list_files() and get_manifest_info()."""

    def test_restore_list_with_pattern_filter(self, tmp_path: Path):
        backup_root = tmp_path / "backup" / "Documents-Backup"
        backup_root.mkdir(parents=True)
        (backup_root / "notes.txt").write_text("hello")
        (backup_root / "image.png").write_bytes(b"\x89PNG")

        result = runner.invoke(
            app,
            [
                "restore",
                "--source",
                str(tmp_path / "backup"),
                "--list",
                "--pattern",
                "*.txt",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "notes.txt" in result.output
        assert "image.png" not in result.output

    def test_restore_manifest_info_displays_summary(self, tmp_path: Path):
        backup_root = tmp_path / "backup" / "Documents-Backup"
        backup_root.mkdir(parents=True)
        (backup_root / "notes.txt").write_text("hello")

        mgr = JsonManifestManager(backup_root)
        manifest = mgr.load_or_create(tmp_path / "src")
        manifest.backup_count = 3
        mgr.save(manifest)

        result = runner.invoke(
            app,
            [
                "restore",
                "--source",
                str(tmp_path / "backup"),
                "--manifest-info",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "BACKUP MANIFEST INFO" in result.output
        assert "Backup Count" in result.output

    def test_restore_manifest_info_missing_manifest_exits_1(self, tmp_path: Path):
        backup_root = tmp_path / "backup" / "Documents-Backup"
        backup_root.mkdir(parents=True)

        result = runner.invoke(
            app,
            [
                "restore",
                "--source",
                str(tmp_path / "backup"),
                "--manifest-info",
            ],
        )

        assert result.exit_code == 1
        assert "No manifest found" in result.output
