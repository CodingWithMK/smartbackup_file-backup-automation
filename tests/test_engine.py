"""
Tests for the engine module.
"""

from pathlib import Path

import pytest

from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.models import FileAction, FileInfo
from smartbackup.ui.logger import BackupLogger


class TestBackupEngine:
    """Tests for BackupEngine class."""

    def test_engine_creation(self, source_dir: Path, backup_dir: Path):
        """BackupEngine should be creatable."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        assert engine is not None
        assert engine.config == config

    def test_validate_paths_valid(self, source_dir: Path, backup_dir: Path):
        """Path validation should pass for valid paths."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        assert engine._validate_paths() is True

    def test_validate_paths_missing_source(self, temp_dir: Path, backup_dir: Path):
        """Path validation should fail for missing source."""
        config = BackupConfig(
            source_path=temp_dir / "nonexistent",
            backup_path=backup_dir,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        assert engine._validate_paths() is False

    def test_validate_paths_missing_backup(self, source_dir: Path, temp_dir: Path):
        """Path validation should fail for missing backup path."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=temp_dir / "nonexistent",
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        assert engine._validate_paths() is False

    def test_copy_single_file(self, source_dir: Path, backup_dir: Path):
        """Single file copying should work."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        file_info = FileInfo(
            path=source_dir / "file1.txt",
            relative_path=Path("file1.txt"),
            size=11,
            mtime=1234567890.0,
        )

        success, message = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert message == "OK"
        assert (backup_dir / "file1.txt").exists()
        assert (backup_dir / "file1.txt").read_text() == "Hello World"

    def test_copy_file_creates_directories(self, source_dir: Path, backup_dir: Path):
        """Copying should create necessary directories."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        file_info = FileInfo(
            path=source_dir / "subdir" / "file3.txt",
            relative_path=Path("subdir/file3.txt"),
            size=11,
            mtime=1234567890.0,
        )

        success, _ = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "subdir" / "file3.txt").exists()

    def test_run_backup_creates_folder(self, source_dir: Path, backup_dir: Path):
        """Running backup should create backup folder."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        result = engine.run_backup()

        assert (backup_dir / "TestBackup").exists()

    def test_run_backup_copies_files(self, source_dir: Path, backup_dir: Path):
        """Running backup should copy files."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        result = engine.run_backup()

        assert result.copied_files > 0
        assert (backup_dir / "TestBackup" / "file1.txt").exists()

    def test_run_backup_result(self, source_dir: Path, backup_dir: Path):
        """Backup result should have correct stats."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        result = engine.run_backup()

        assert result.total_files > 0
        assert result.errors == 0
        assert result.end_time is not None

    def test_run_backup_incremental(self, source_dir: Path, backup_dir: Path):
        """Second backup should skip unchanged files."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        # First backup
        result1 = engine.run_backup()
        copied_first = result1.copied_files

        # Second backup (no changes)
        engine2 = BackupEngine(config, logger)
        result2 = engine2.run_backup()

        # Second backup should skip all files
        assert result2.copied_files == 0
        assert result2.skipped_files == copied_first


class TestDryRunBackupEngine:
    """Tests for DryRunBackupEngine class."""

    def test_dry_run_creation(self, source_dir: Path, backup_dir: Path):
        """DryRunBackupEngine should be creatable."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = DryRunBackupEngine(config, logger)

        assert engine is not None

    def test_dry_run_does_not_copy(self, source_dir: Path, backup_dir: Path):
        """Dry run should not actually copy files."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = DryRunBackupEngine(config, logger)

        file_info = FileInfo(
            path=source_dir / "file1.txt",
            relative_path=Path("file1.txt"),
            size=11,
            mtime=1234567890.0,
        )

        success, message = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert message == "DRY-RUN"
        assert not (backup_dir / "file1.txt").exists()

    def test_dry_run_delete_simulation(self, source_dir: Path, backup_dir: Path):
        """Dry run should simulate deletion without removing files."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        engine = DryRunBackupEngine(config, logger)

        # Create a file to "delete"
        test_file = backup_dir / "to_delete.txt"
        test_file.write_text("delete me")

        engine._delete_files([test_file])

        # File should still exist
        assert test_file.exists()
        assert engine.result.deleted_files == 1
