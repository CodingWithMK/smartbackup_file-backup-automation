"""
Unit tests for BackupEngine and DryRunBackupEngine helper methods,
collision handling, and legacy layout migration.
"""

from pathlib import Path

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
