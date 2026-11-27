"""
Unit tests for BackupEngine and DryRunBackupEngine helper methods,
collision handling, and legacy layout migration.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.models import FileAction, FileInfo
from smartbackup.ui.logger import BackupLogger


class TestBackupEngineUnit:
    """Unit tests for BackupEngine path validation, copying, deletion, and migration."""

    @pytest.fixture
    def engine(self, source_dir: Path, backup_dir: Path) -> BackupEngine:
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        return BackupEngine(config, BackupLogger(verbose=False))

    def test_engine_creation(self, source_dir: Path, backup_dir: Path):
        """BackupEngine should be creatable."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        engine = BackupEngine(config, BackupLogger(verbose=False))

        assert engine is not None
        assert engine.config == config

    def test_validate_paths_valid(self, engine: BackupEngine):
        """Path validation should pass for valid paths."""
        assert engine._validate_paths() is True

    def test_validate_paths_missing_source(self, tmp_path: Path, backup_dir: Path):
        """Path validation should fail for missing source."""
        config = BackupConfig(
            source_path=tmp_path / "nonexistent",
            backup_path=backup_dir,
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))
        assert engine._validate_paths() is False

    def test_validate_paths_missing_backup(self, source_dir: Path, tmp_path: Path):
        """Path validation should fail for missing backup path."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=tmp_path / "nonexistent",
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))
        assert engine._validate_paths() is False

    def test_copy_single_file(
        self, engine: BackupEngine, source_dir: Path, backup_dir: Path
    ):
        """Single file copying should work."""
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

    def test_copy_file_creates_directories(
        self, engine: BackupEngine, source_dir: Path, backup_dir: Path
    ):
        """Copying should create necessary directories."""
        file_info = FileInfo(
            path=source_dir / "subdir" / "file3.txt",
            relative_path=Path("subdir/file3.txt"),
            size=11,
            mtime=1234567890.0,
        )

        success, _ = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "subdir" / "file3.txt").exists()

    def test_collision_file_replaces_directory(
        self, engine: BackupEngine, source_dir: Path, backup_dir: Path
    ):
        """If target is a directory but should be a file, it should be deleted and replaced."""
        collision_path = backup_dir / "collision"
        collision_path.mkdir(parents=True)
        (collision_path / "old_file.txt").write_text("obsolete")

        source_file = source_dir / "collision"
        source_file.write_text("new content")

        file_info = FileInfo(
            path=source_file,
            relative_path=Path("collision"),
            size=len("new content"),
            mtime=1234567890.0,
        )

        success, _ = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "collision").is_file()
        assert (backup_dir / "collision").read_text() == "new content"
        assert not (collision_path / "old_file.txt").exists()

    def test_collision_directory_replaces_file(
        self, engine: BackupEngine, source_dir: Path, backup_dir: Path
    ):
        """If parent is a file but should be a directory, it should be deleted and replaced."""
        parent_collision = backup_dir / "parent_collision"
        parent_collision.write_text("I am a file")

        source_file = source_dir / "parent_collision" / "child.txt"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("child content")

        file_info = FileInfo(
            path=source_file,
            relative_path=Path("parent_collision/child.txt"),
            size=len("child content"),
            mtime=1234567890.0,
        )

        success, _ = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "parent_collision").is_dir()
        assert (backup_dir / "parent_collision" / "child.txt").is_file()
        assert (backup_dir / "parent_collision" / "child.txt").read_text() == "child content"

    def test_sync_deletion(self, engine: BackupEngine, backup_dir: Path):
        """Files deleted on source should be deleted from backup."""
        obsolete_file = backup_dir / "obsolete.txt"
        obsolete_file.write_text("delete me")

        engine._delete_files([obsolete_file])

        assert not obsolete_file.exists()
        assert engine.result.deleted_files == 1

    def test_sync_directory_deletion(self, engine: BackupEngine, backup_dir: Path):
        """Directories deleted on source should be deleted from backup recursively."""
        obsolete_dir = backup_dir / "obsolete_dir"
        obsolete_dir.mkdir()
        (obsolete_dir / "file.txt").write_text("delete me")

        engine._delete_files([obsolete_dir])

        assert not obsolete_dir.exists()
        assert engine.result.deleted_files == 1

    def test_migration_skips_missing_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Migration should not crash if a file disappears during iteration."""
        backup_root = tmp_path / "Documents-Backup"
        backup_root.mkdir()

        volatile_file = backup_root / "volatile.txt"
        volatile_file.write_text("I might disappear")
        (backup_root / ".smartbackup_manifest.json").write_text("{}")

        config = BackupConfig(
            source_path=tmp_path / "source",
            backup_path=tmp_path,
            device_name="MacBook",
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))

        original_iterdir = Path.iterdir

        def mocked_iterdir(path_obj):
            for item in original_iterdir(path_obj):
                if item.name == "volatile.txt":
                    try:
                        item.unlink()
                    except FileNotFoundError:
                        pass
                yield item

        monkeypatch.setattr(Path, "iterdir", mocked_iterdir)

        engine._migrate_legacy_layout(backup_root)

        assert (backup_root / "MacBook").exists()
        assert not (backup_root / "volatile.txt").exists()


class TestDryRunBackupEngineUnit:
    """Unit tests for DryRunBackupEngine low-level file operations."""

    def test_dry_run_creation(self, source_dir: Path, backup_dir: Path):
        """DryRunBackupEngine should be creatable."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        engine = DryRunBackupEngine(config, BackupLogger(verbose=False))
        assert engine is not None

    def test_dry_run_does_not_copy(self, source_dir: Path, backup_dir: Path):
        """Dry run should not actually copy files."""
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        engine = DryRunBackupEngine(config, BackupLogger(verbose=False))

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
        engine = DryRunBackupEngine(config, BackupLogger(verbose=False))

        test_file = backup_dir / "to_delete.txt"
        test_file.write_text("delete me")

        engine._delete_files([test_file])

        assert test_file.exists()
        assert engine.result.deleted_files == 1


class TestLegacyMigrationRollback:
    """Q4 regression tests for legacy layout migration rollback and error propagation."""

    def test_legacy_migration_rolls_back_items_when_final_rename_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backup_root = tmp_path / "Documents-Backup"
        backup_root.mkdir()
        (backup_root / "notes.txt").write_text("important")
        sub = backup_root / "Projects"
        sub.mkdir()
        (sub / "main.py").write_text("print(1)")
        (backup_root / ".smartbackup_manifest.json").write_text("{}")

        config = BackupConfig(
            source_path=tmp_path / "source",
            backup_path=tmp_path,
            device_name="WorkLaptop",
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))

        real_rename = Path.rename

        def fail_final_rename(self_path: Path, target: Path):
            if target.name == "WorkLaptop" and self_path.name.startswith(".migration_temp_"):
                raise OSError("device busy")
            return real_rename(self_path, target)

        monkeypatch.setattr(Path, "rename", fail_final_rename)

        ok = engine._migrate_legacy_layout(backup_root)

        assert ok is False
        assert not (backup_root / "WorkLaptop").exists()
        # Every original item must be rolled back to backup_root
        assert (backup_root / "notes.txt").read_text() == "important"
        assert (backup_root / "Projects" / "main.py").read_text() == "print(1)"
        assert (backup_root / ".smartbackup_manifest.json").exists()
        # No orphaned .migration_temp_* left behind
        assert not list(backup_root.glob(".migration_temp_*"))

    def test_legacy_migration_partial_rollback_preserves_files_and_logs_recovery_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backup_root = tmp_path / "Documents-Backup"
        backup_root.mkdir()
        (backup_root / "good.txt").write_text("ok")
        (backup_root / "locked.txt").write_text("stuck")
        (backup_root / ".smartbackup_manifest.json").write_text("{}")

        mock_logger = MagicMock()
        config = BackupConfig(
            source_path=tmp_path / "source",
            backup_path=tmp_path,
            device_name="WorkLaptop",
        )
        engine = BackupEngine(config, mock_logger)

        real_rename = Path.rename

        def fail_final_and_locked_rollback(self_path: Path, target: Path):
            if target.name == "WorkLaptop" and self_path.name.startswith(".migration_temp_"):
                raise OSError("rename blocked")
            if self_path.name == "locked.txt" and self_path.parent.name.startswith(".migration_temp_"):
                raise OSError("file handle locked")
            return real_rename(self_path, target)

        monkeypatch.setattr(Path, "rename", fail_final_and_locked_rollback)

        ok = engine._migrate_legacy_layout(backup_root)

        assert ok is False
        # Unlocked file was restored cleanly
        assert (backup_root / "good.txt").read_text() == "ok"
        # Locked file remains safely inside .migration_temp_* (never deleted!)
        temp_dirs = list(backup_root.glob(".migration_temp_*"))
        assert len(temp_dirs) == 1
        assert (temp_dirs[0] / "locked.txt").read_text() == "stuck"
        # Explicit recovery path logged as error
        error_msgs = [call.args[0] for call in mock_logger.error.call_args_list]
        assert any(str(temp_dirs[0]) in msg for msg in error_msgs)

    def test_legacy_migration_failure_aborts_run_backup_and_increments_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "fresh.txt").write_text("should not be copied into half-migrated dir")

        backup_path = tmp_path / "drive"
        backup_root = backup_path / "Documents-Backup"
        backup_root.mkdir(parents=True)
        (backup_root / "old.txt").write_text("legacy")
        (backup_root / ".smartbackup_manifest.json").write_text("{}")

        config = BackupConfig(
            source_path=source,
            backup_path=backup_path,
            device_name="WorkLaptop",
            log_to_file=False,
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))

        real_rename = Path.rename

        def fail_final_rename(self_path: Path, target: Path):
            if target.name == "WorkLaptop" and self_path.name.startswith(".migration_temp_"):
                raise OSError("permission denied")
            return real_rename(self_path, target)

        monkeypatch.setattr(Path, "rename", fail_final_rename)

        result = engine.run_backup()

        assert result.errors == 1
        assert result.copied_files == 0
        assert not (backup_root / "WorkLaptop").exists()
        assert (backup_root / "old.txt").read_text() == "legacy"

    def test_legacy_migration_collision_safe_temp_dir_and_mkdir_oserror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        backup_root = tmp_path / "Documents-Backup"
        backup_root.mkdir()
        (backup_root / "legacy.txt").write_text("data")
        # Pre-create same-second temp dir to verify collision avoidance
        monkeypatch.setattr("smartbackup.core.engine.time.time", lambda: 1700000000)
        (backup_root / ".migration_temp_1700000000").mkdir()

        config = BackupConfig(
            source_path=tmp_path / "source",
            backup_path=tmp_path,
            device_name="LaptopA",
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))

        assert engine._migrate_legacy_layout(backup_root) is True
        assert (backup_root / "LaptopA" / "legacy.txt").read_text() == "data"

        # Now verify mkdir OSError returns False cleanly instead of crashing
        backup_root2 = tmp_path / "Documents-Backup-2"
        backup_root2.mkdir()
        (backup_root2 / "legacy.txt").write_text("data")
        engine2 = BackupEngine(config, BackupLogger(verbose=False))

        real_mkdir = Path.mkdir

        def fail_temp_mkdir(self_path: Path, *args, **kwargs):
            if self_path.name.startswith(".migration_temp_"):
                raise OSError("read-only filesystem")
            return real_mkdir(self_path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", fail_temp_mkdir)
        assert engine2._migrate_legacy_layout(backup_root2) is False
        assert (backup_root2 / "legacy.txt").read_text() == "data"
