"""Tests for the restore engine."""

import tempfile
from pathlib import Path

import pytest

from smartbackup.core.restore import (
    ConflictResolution,
    RestoreEngine,
    RestoreResult,
)
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.models import FileAction


class TestRestoreResult:
    """Tests for RestoreResult class."""

    def test_create_result(self) -> None:
        """Test creating a restore result."""
        result = RestoreResult()

        assert result.total_files == 0
        assert result.restored_files == 0
        assert result.skipped_files == 0
        assert result.errors == 0

    def test_duration(self) -> None:
        """Test duration calculation."""
        from datetime import datetime, timedelta

        result = RestoreResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.end_time = datetime.now()

        assert result.duration >= 9.9  # Account for minor timing differences

    def test_speed_mbps(self) -> None:
        """Test speed calculation."""
        from datetime import datetime, timedelta

        result = RestoreResult()
        result.start_time = datetime.now() - timedelta(seconds=10)
        result.end_time = datetime.now()
        result.restored_size = 10 * 1024 * 1024  # 10 MB

        assert result.speed_mbps >= 0.99  # ~1 MB/s


class TestRestoreEngine:
    """Tests for RestoreEngine class."""

    @pytest.fixture
    def backup_structure(self, tmp_path: Path) -> tuple:
        """Create a backup directory structure for testing."""
        # Create backup location
        backup_base = tmp_path / "backup"
        backup_folder = backup_base / "Documents-Backup"
        backup_folder.mkdir(parents=True)

        # Create some backup files
        (backup_folder / "file1.txt").write_text("Content 1")
        (backup_folder / "file2.txt").write_text("Content 2")

        sub_dir = backup_folder / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file3.txt").write_text("Content 3")

        # Create internal files that should be skipped
        logs_dir = backup_folder / "_backup_logs"
        logs_dir.mkdir()
        (logs_dir / "backup.log").write_text("Log content")

        # Create target location
        target = tmp_path / "restored"
        target.mkdir()

        return backup_base, target

    def test_restore_all_files(self, backup_structure: tuple) -> None:
        """Test restoring all files."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore()

        assert result.errors == 0
        assert result.restored_files == 3
        assert (target / "file1.txt").exists()
        assert (target / "file2.txt").exists()
        assert (target / "subdir" / "file3.txt").exists()
        # Log files should not be restored
        assert not (target / "_backup_logs").exists()

    def test_restore_dry_run(self, backup_structure: tuple) -> None:
        """Test dry run mode."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore(dry_run=True)

        assert result.errors == 0
        assert result.restored_files == 3
        # Files should NOT actually be created
        assert not (target / "file1.txt").exists()
        assert not (target / "file2.txt").exists()

    def test_restore_with_pattern(self, backup_structure: tuple) -> None:
        """Test restoring with pattern filter."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore(patterns=["file1*"])

        assert result.errors == 0
        assert result.restored_files == 1
        assert (target / "file1.txt").exists()
        assert not (target / "file2.txt").exists()

    def test_restore_skip_existing(self, backup_structure: tuple) -> None:
        """Test skipping existing files."""
        backup_base, target = backup_structure

        # Create an existing file
        (target / "file1.txt").write_text("Original content")

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore(overwrite=False)

        assert result.errors == 0
        assert result.restored_files == 2  # file2 and file3
        assert result.skipped_files == 1  # file1
        # Existing file should keep original content
        assert (target / "file1.txt").read_text() == "Original content"

    def test_restore_overwrite_existing(self, backup_structure: tuple) -> None:
        """Test overwriting existing files."""
        backup_base, target = backup_structure

        # Create an existing file with different content
        (target / "file1.txt").write_text("Original content")

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore(overwrite=True)

        assert result.errors == 0
        assert result.restored_files == 2  # file2 and file3 (new)
        assert result.overwritten_files == 1  # file1 (overwritten)
        # File should be overwritten with backup content
        assert (target / "file1.txt").read_text() == "Content 1"

    def test_restore_creates_directories(self, backup_structure: tuple) -> None:
        """Test that restore creates necessary directories."""
        backup_base, target = backup_structure

        # Add a deeply nested file
        backup_folder = backup_base / "Documents-Backup"
        deep_dir = backup_folder / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.txt").write_text("Deep content")

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        result = engine.restore()

        assert result.errors == 0
        assert (target / "a" / "b" / "c" / "deep.txt").exists()
        assert (target / "a" / "b" / "c" / "deep.txt").read_text() == "Deep content"

    def test_list_files(self, backup_structure: tuple) -> None:
        """Test listing files in backup."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        files = engine.list_files()

        assert len(files) == 3
        paths = [str(f[0]) for f in files]
        assert "file1.txt" in paths
        assert "file2.txt" in paths

    def test_list_files_with_pattern(self, backup_structure: tuple) -> None:
        """Test listing files with pattern filter."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        files = engine.list_files(patterns=["*.txt"])

        # All 3 txt files match
        assert len(files) == 3

    def test_restore_nonexistent_backup(self, tmp_path: Path) -> None:
        """Test restore from nonexistent backup directory."""
        engine = RestoreEngine(
            backup_path=tmp_path / "nonexistent",
            target_path=tmp_path / "target",
        )

        result = engine.restore()

        assert result.errors >= 1

    def test_get_manifest_info(self, backup_structure: tuple) -> None:
        """Test getting manifest info."""
        backup_base, target = backup_structure
        backup_folder = backup_base / "Documents-Backup"

        # Create a manifest
        manager = JsonManifestManager(backup_folder)
        from smartbackup.manifest.base import Manifest

        manifest = Manifest(source="/original/source", backup_count=5)
        manager.save(manifest)

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        info = engine.get_manifest_info()

        assert info is not None
        assert info["source"] == "/original/source"
        assert info["backup_count"] == 5

    def test_get_manifest_info_no_manifest(self, backup_structure: tuple) -> None:
        """Test getting manifest info when no manifest exists."""
        backup_base, target = backup_structure

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=target,
        )

        info = engine.get_manifest_info()

        assert info is None

    def test_restore_uses_manifest_source(self, backup_structure: tuple) -> None:
        """Test that restore can use manifest source as target."""
        backup_base, _ = backup_structure
        backup_folder = backup_base / "Documents-Backup"

        # Create target from manifest
        original_source = backup_base.parent / "original_source"
        original_source.mkdir()

        # Create manifest with original source
        manager = JsonManifestManager(backup_folder)
        from smartbackup.manifest.base import Manifest

        manifest = Manifest(source=str(original_source))
        manager.save(manifest)

        engine = RestoreEngine(
            backup_path=backup_base,
            target_path=None,  # No target specified
        )

        result = engine.restore()

        assert result.errors == 0
        # Files should be restored to original source location
        assert (original_source / "file1.txt").exists()


class TestConflictResolution:
    """Tests for ConflictResolution enum."""

    def test_conflict_resolution_values(self) -> None:
        """Test conflict resolution enum values."""
        assert ConflictResolution.SKIP.value == 1
        assert ConflictResolution.OVERWRITE.value == 2
        assert ConflictResolution.RENAME.value == 3
        assert ConflictResolution.NEWER.value == 4
