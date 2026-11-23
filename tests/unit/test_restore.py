"""
Unit tests for core.restore (RestoreEngine, RestoreResult, ConflictResolution).
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from smartbackup.core.restore import (
    ConflictResolution,
    RestoreEngine,
    RestoreResult,
)
from smartbackup.manifest.base import Manifest
from smartbackup.manifest.json_manifest import JsonManifestManager


class TestRestoreResult:
    """Tests for RestoreResult class."""

    def test_create_result(self) -> None:
        result = RestoreResult()

        assert result.total_files == 0
        assert result.restored_files == 0
        assert result.skipped_files == 0
        assert result.errors == 0

    def test_duration(self) -> None:
        result = RestoreResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.end_time = datetime.now()

        assert result.duration >= 9.9

    def test_speed_mbps(self) -> None:
        result = RestoreResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.end_time = datetime.now()
        result.restored_size = 10 * 1024 * 1024

        assert result.speed_mbps >= 0.99


class TestRestoreEngine:
    """Tests for RestoreEngine class."""

    @pytest.fixture
    def backup_structure(self, tmp_path: Path) -> tuple:
        backup_base = tmp_path / "backup"
        backup_folder = backup_base / "Documents-Backup"
        backup_folder.mkdir(parents=True)

        (backup_folder / "file1.txt").write_text("Content 1")
        (backup_folder / "file2.txt").write_text("Content 2")

        sub_dir = backup_folder / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file3.txt").write_text("Content 3")

        logs_dir = backup_folder / "_backup_logs"
        logs_dir.mkdir()
        (logs_dir / "backup.log").write_text("Log content")

        target = tmp_path / "restored"
        target.mkdir()

        return backup_base, target

    def test_restore_all_files(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        result = engine.restore()

        assert result.errors == 0
        assert result.restored_files == 3
        assert (target / "file1.txt").exists()
        assert (target / "file2.txt").exists()
        assert (target / "subdir" / "file3.txt").exists()
        assert not (target / "_backup_logs").exists()

    def test_restore_dry_run(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        result = engine.restore(dry_run=True)

        assert result.errors == 0
        assert result.restored_files == 3
        assert not (target / "file1.txt").exists()
        assert not (target / "file2.txt").exists()

    def test_restore_with_pattern(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        result = engine.restore(patterns=["file1*"])

        assert result.errors == 0
        assert result.restored_files == 1
        assert (target / "file1.txt").exists()
        assert not (target / "file2.txt").exists()

    def test_restore_skip_existing(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        (target / "file1.txt").write_text("Original content")

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(overwrite=False)

        assert result.errors == 0
        assert result.restored_files == 2
        assert result.skipped_files == 1
        assert (target / "file1.txt").read_text() == "Original content"

    def test_restore_overwrite_existing(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        (target / "file1.txt").write_text("Original content")

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(overwrite=True)

        assert result.errors == 0
        assert result.restored_files == 2
        assert result.overwritten_files == 1
        assert (target / "file1.txt").read_text() == "Content 1"

    def test_restore_creates_directories(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        backup_folder = backup_base / "Documents-Backup"
        deep_dir = backup_folder / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.txt").write_text("Deep content")

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore()

        assert result.errors == 0
        assert (target / "a" / "b" / "c" / "deep.txt").exists()
        assert (target / "a" / "b" / "c" / "deep.txt").read_text() == "Deep content"

    def test_list_files(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        files = engine.list_files()
        assert len(files) == 3
        paths = [str(f[0]) for f in files]
        assert "file1.txt" in paths
        assert "file2.txt" in paths

    def test_list_files_with_pattern(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        files = engine.list_files(patterns=["*.txt"])
        assert len(files) == 3

    def test_restore_nonexistent_backup(self, tmp_path: Path) -> None:
        engine = RestoreEngine(
            backup_path=tmp_path / "nonexistent",
            target_path=tmp_path / "target",
        )

        result = engine.restore()
        assert result.errors >= 1

    def test_get_manifest_info(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        backup_folder = backup_base / "Documents-Backup"

        manager = JsonManifestManager(backup_folder)
        manager.save(Manifest(source="/original/source", backup_count=5))

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        info = engine.get_manifest_info()

        assert info is not None
        assert info["source"] == "/original/source"
        assert info["backup_count"] == 5

    def test_get_manifest_info_no_manifest(self, backup_structure: tuple) -> None:
        backup_base, target = backup_structure
        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        assert engine.get_manifest_info() is None

    def test_restore_uses_manifest_source(self, backup_structure: tuple) -> None:
        backup_base, _ = backup_structure
        backup_folder = backup_base / "Documents-Backup"

        original_source = backup_base.parent / "original_source"
        original_source.mkdir()

        manager = JsonManifestManager(backup_folder)
        manager.save(Manifest(source=str(original_source)))

        engine = RestoreEngine(backup_path=backup_base, target_path=None)
        result = engine.restore()

        assert result.errors == 0
        assert (original_source / "file1.txt").exists()


class TestConflictResolution:
    """Tests for ConflictResolution enum."""

    def test_conflict_resolution_values(self) -> None:
        assert ConflictResolution.SKIP.value == 1
        assert ConflictResolution.OVERWRITE.value == 2
        assert ConflictResolution.RENAME.value == 3
        assert ConflictResolution.NEWER.value == 4


class TestConflictStrategies:
    """Tests for F3 conflict resolution strategies."""

    @pytest.fixture
    def conflict_setup(self, tmp_path: Path) -> tuple:
        backup_base = tmp_path / "backup"
        backup_folder = backup_base / "Documents-Backup"
        backup_folder.mkdir(parents=True)
        (backup_folder / "file1.txt").write_text("BACKUP CONTENT")

        target = tmp_path / "restored"
        target.mkdir()
        (target / "file1.txt").write_text("LOCAL CONTENT")

        return backup_base, target

    def test_conflict_newer_skips_when_target_is_newer(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup
        old = time.time() - 3600
        os.utime(backup_base / "Documents-Backup" / "file1.txt", (old, old))

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(conflict=ConflictResolution.NEWER)

        assert result.errors == 0
        assert result.skipped_files == 1
        assert result.overwritten_files == 0
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_conflict_newer_overwrites_when_backup_is_newer(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup
        old = time.time() - 3600
        os.utime(target / "file1.txt", (old, old))

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(conflict=ConflictResolution.NEWER)

        assert result.errors == 0
        assert result.overwritten_files == 1
        assert (target / "file1.txt").read_text() == "BACKUP CONTENT"

    def test_conflict_rename_keeps_both_files(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(conflict=ConflictResolution.RENAME)

        assert result.errors == 0
        assert result.restored_files == 1
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

        renamed = list(target.glob("file1.restored-*.txt"))
        assert len(renamed) == 1, f"expected one renamed copy, got {renamed}"
        assert renamed[0].read_text() == "BACKUP CONTENT"
        assert any("Renamed" in message for _, _, message in result.file_actions)

    def test_conflict_rename_is_collision_safe(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup
        engine = RestoreEngine(backup_path=backup_base, target_path=target)

        engine.restore(conflict=ConflictResolution.RENAME)
        engine.restore(conflict=ConflictResolution.RENAME)

        renamed = sorted(target.glob("file1.restored-*.txt"))
        assert len(renamed) == 2, f"expected two renamed copies, got {renamed}"
        assert all(p.read_text() == "BACKUP CONTENT" for p in renamed)
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_conflict_rename_dry_run_writes_nothing(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(conflict=ConflictResolution.RENAME, dry_run=True)

        assert result.errors == 0
        assert result.restored_files == 1
        assert not list(target.glob("file1.restored-*"))
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_default_skip_is_unchanged(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore()

        assert result.errors == 0
        assert result.skipped_files == 1
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"

    def test_overwrite_flag_is_unchanged(self, conflict_setup: tuple) -> None:
        backup_base, target = conflict_setup

        engine = RestoreEngine(backup_path=backup_base, target_path=target)
        result = engine.restore(overwrite=True)

        assert result.errors == 0
        assert result.overwritten_files == 1
        assert (target / "file1.txt").read_text() == "BACKUP CONTENT"
