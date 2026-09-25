
from pathlib import Path

import pytest

from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine
from smartbackup.models import FileAction, FileInfo
from smartbackup.ui.logger import BackupLogger


class TestBackupCollisions:
    """Tests for file/directory collision handling in BackupEngine."""

    @pytest.fixture
    def engine(self, source_dir: Path, backup_dir: Path):
        config = BackupConfig(source_path=source_dir, backup_path=backup_dir)
        logger = BackupLogger(verbose=False)
        return BackupEngine(config, logger)

    def test_collision_file_replaces_directory(self, engine: BackupEngine, source_dir: Path, backup_dir: Path):
        """If target is a directory but should be a file, it should be deleted and replaced."""
        # Setup: Target has a directory where source has a file
        collision_path = backup_dir / "collision"
        collision_path.mkdir(parents=True)
        (collision_path / "old_file.txt").write_text("obsolete")

        source_file = source_dir / "collision"
        source_file.write_text("new content")

        file_info = FileInfo(
            path=source_file,
            relative_path=Path("collision"),
            size=len("new content"),
            mtime=1234567890.0
        )

        success, message = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "collision").is_file()
        assert (backup_dir / "collision").read_text() == "new content"
        assert not (collision_path / "old_file.txt").exists()

    def test_collision_directory_replaces_file(self, engine: BackupEngine, source_dir: Path, backup_dir: Path):
        """If parent is a file but should be a directory, it should be deleted and replaced."""
        # Setup: Target has a file where source needs a directory
        parent_collision = backup_dir / "parent_collision"
        parent_collision.write_text("I am a file")

        source_file = source_dir / "parent_collision" / "child.txt"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("child content")

        file_info = FileInfo(
            path=source_file,
            relative_path=Path("parent_collision/child.txt"),
            size=len("child content"),
            mtime=1234567890.0
        )

        success, message = engine._copy_single_file(file_info, backup_dir, FileAction.COPIED)

        assert success is True
        assert (backup_dir / "parent_collision").is_dir()
        assert (backup_dir / "parent_collision" / "child.txt").is_file()
        assert (backup_dir / "parent_collision" / "child.txt").read_text() == "child content"

    def test_sync_deletion(self, engine: BackupEngine, source_dir: Path, backup_dir: Path):
        """Files deleted on source should be deleted from backup."""
        # Setup: File exists on backup but not on source
        obsolete_file = backup_dir / "obsolete.txt"
        obsolete_file.write_text("delete me")

        assert obsolete_file.exists()

        engine._delete_files([obsolete_file])

        assert not obsolete_file.exists()
        assert engine.result.deleted_files == 1

    def test_sync_directory_deletion(self, engine: BackupEngine, source_dir: Path, backup_dir: Path):
        """Directories deleted on source should be deleted from backup recursively."""
        # Setup: Directory exists on backup but not on source
        obsolete_dir = backup_dir / "obsolete_dir"
        obsolete_dir.mkdir()
        (obsolete_dir / "file.txt").write_text("delete me")

        assert obsolete_dir.exists()

        engine._delete_files([obsolete_dir])

        assert not obsolete_dir.exists()
        assert engine.result.deleted_files == 1
