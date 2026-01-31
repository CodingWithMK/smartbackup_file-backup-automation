"""
Tests for the models module.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from smartbackup.models import BackupResult, FileAction, FileInfo


class TestFileAction:
    """Tests for FileAction enum."""

    def test_all_actions_exist(self):
        """All expected file actions should exist."""
        assert FileAction.COPIED
        assert FileAction.UPDATED
        assert FileAction.SKIPPED
        assert FileAction.DELETED
        assert FileAction.ERROR


class TestFileInfo:
    """Tests for FileInfo dataclass."""

    def test_file_info_creation(self, temp_dir: Path):
        """FileInfo should be creatable with required fields."""
        path = temp_dir / "test.txt"
        info = FileInfo(
            path=path,
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
        )

        assert info.path == path
        assert info.relative_path == Path("test.txt")
        assert info.size == 100
        assert info.mtime == 1234567890.0
        assert info.file_hash is None

    def test_file_info_with_hash(self, temp_dir: Path):
        """FileInfo should accept optional hash."""
        info = FileInfo(
            path=temp_dir / "test.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
            file_hash="abc123",
        )

        assert info.file_hash == "abc123"

    def test_needs_update_different_size(self, temp_dir: Path):
        """File needs update if size differs."""
        source = FileInfo(
            path=temp_dir / "src.txt",
            relative_path=Path("test.txt"),
            size=200,
            mtime=1234567890.0,
        )
        backup = FileInfo(
            path=temp_dir / "bak.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
        )

        assert source.needs_update(backup) is True

    def test_needs_update_newer_mtime(self, temp_dir: Path):
        """File needs update if source is newer."""
        source = FileInfo(
            path=temp_dir / "src.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567900.0,  # Newer
        )
        backup = FileInfo(
            path=temp_dir / "bak.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
        )

        assert source.needs_update(backup) is True

    def test_needs_update_same_file(self, temp_dir: Path):
        """File does not need update if same size and mtime."""
        source = FileInfo(
            path=temp_dir / "src.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
        )
        backup = FileInfo(
            path=temp_dir / "bak.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
        )

        assert source.needs_update(backup) is False

    def test_needs_update_different_hash(self, temp_dir: Path):
        """File needs update if hash differs (when using hash)."""
        source = FileInfo(
            path=temp_dir / "src.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
            file_hash="abc123",
        )
        backup = FileInfo(
            path=temp_dir / "bak.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
            file_hash="def456",
        )

        assert source.needs_update(backup, use_hash=True) is True

    def test_needs_update_same_hash(self, temp_dir: Path):
        """File does not need update if hash is same."""
        source = FileInfo(
            path=temp_dir / "src.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
            file_hash="abc123",
        )
        backup = FileInfo(
            path=temp_dir / "bak.txt",
            relative_path=Path("test.txt"),
            size=100,
            mtime=1234567890.0,
            file_hash="abc123",
        )

        assert source.needs_update(backup, use_hash=True) is False


class TestBackupResult:
    """Tests for BackupResult dataclass."""

    def test_default_result(self):
        """Default result should have zero counts."""
        result = BackupResult()

        assert result.total_files == 0
        assert result.copied_files == 0
        assert result.updated_files == 0
        assert result.skipped_files == 0
        assert result.deleted_files == 0
        assert result.errors == 0
        assert result.total_size == 0
        assert result.copied_size == 0

    def test_result_with_values(self):
        """Result should accept initial values."""
        result = BackupResult(
            total_files=100,
            copied_files=50,
            updated_files=10,
            errors=2,
        )

        assert result.total_files == 100
        assert result.copied_files == 50
        assert result.updated_files == 10
        assert result.errors == 2

    def test_duration_without_end_time(self):
        """Duration should work without end_time set."""
        result = BackupResult()

        # Duration should be positive (time since creation)
        assert result.duration >= 0

    def test_duration_with_end_time(self):
        """Duration should calculate correctly with end_time."""
        start = datetime.now()
        end = start + timedelta(seconds=10)

        result = BackupResult(start_time=start, end_time=end)

        assert result.duration == 10.0

    def test_speed_mbps_zero_duration(self):
        """Speed should be 0 when duration is 0."""
        start = datetime.now()
        result = BackupResult(
            start_time=start,
            end_time=start,  # Same time = 0 duration
            copied_size=1024 * 1024,
        )

        assert result.speed_mbps == 0.0

    def test_speed_mbps_calculation(self):
        """Speed should calculate correctly."""
        start = datetime.now()
        end = start + timedelta(seconds=2)

        result = BackupResult(
            start_time=start,
            end_time=end,
            copied_size=2 * 1024 * 1024,  # 2 MB
        )

        # 2 MB in 2 seconds = 1 MB/s
        assert result.speed_mbps == 1.0

    def test_file_actions_list(self):
        """File actions should be trackable."""
        result = BackupResult()

        result.file_actions.append((Path("test.txt"), FileAction.COPIED, "OK"))
        result.file_actions.append((Path("other.txt"), FileAction.ERROR, "Failed"))

        assert len(result.file_actions) == 2
        assert result.file_actions[0][1] == FileAction.COPIED
        assert result.file_actions[1][1] == FileAction.ERROR
