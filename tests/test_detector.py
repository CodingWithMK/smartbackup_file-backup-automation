"""
Tests for the detector module.
"""

from pathlib import Path

import pytest

from smartbackup.core.detector import ChangeDetector
from smartbackup.models import FileInfo
from smartbackup.ui.logger import BackupLogger


class TestChangeDetector:
    """Tests for ChangeDetector class."""

    def test_detector_creation(self):
        """ChangeDetector should be creatable."""
        detector = ChangeDetector()
        assert detector is not None
        assert detector.use_hash is False

    def test_detector_with_hash(self):
        """ChangeDetector should accept use_hash option."""
        detector = ChangeDetector(use_hash=True)
        assert detector.use_hash is True

    def test_detect_new_files(self, source_dir: Path, backup_dir: Path):
        """Detector should identify new files."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create source file info
        source_files = {
            Path("file1.txt"): FileInfo(
                path=source_dir / "file1.txt",
                relative_path=Path("file1.txt"),
                size=11,
                mtime=1234567890.0,
            ),
        }

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 1
        assert len(modified_files) == 0
        assert len(deleted_files) == 0

    def test_detect_modified_files(self, source_dir: Path, backup_dir: Path):
        """Detector should identify modified files."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create backup file (older)
        backup_file = backup_dir / "file1.txt"
        backup_file.write_text("old content")

        # Get backup mtime
        backup_mtime = backup_file.stat().st_mtime

        # Create source file info (newer)
        source_files = {
            Path("file1.txt"): FileInfo(
                path=source_dir / "file1.txt",
                relative_path=Path("file1.txt"),
                size=11,
                mtime=backup_mtime + 100,  # Newer than backup
            ),
        }

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 0
        assert len(modified_files) == 1
        assert len(deleted_files) == 0

    def test_detect_unchanged_files(self, source_dir: Path, backup_dir: Path):
        """Detector should not flag unchanged files."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create backup file
        backup_file = backup_dir / "file1.txt"
        backup_file.write_text("Hello World")
        backup_stat = backup_file.stat()

        # Create source file info (same as backup)
        source_files = {
            Path("file1.txt"): FileInfo(
                path=source_dir / "file1.txt",
                relative_path=Path("file1.txt"),
                size=backup_stat.st_size,
                mtime=backup_stat.st_mtime,
            ),
        }

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 0
        assert len(modified_files) == 0

    def test_detect_deleted_files(self, source_dir: Path, backup_dir: Path):
        """Detector should identify files to delete from backup."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create backup file that doesn't exist in source
        orphan_file = backup_dir / "orphan.txt"
        orphan_file.write_text("orphan content")

        # Empty source
        source_files = {}

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 0
        assert len(modified_files) == 0
        assert len(deleted_files) == 1
        assert backup_dir / "orphan.txt" in deleted_files

    def test_detect_mixed_changes(self, source_dir: Path, backup_dir: Path):
        """Detector should handle mixed changes correctly."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create backup files
        (backup_dir / "existing.txt").write_text("old")
        (backup_dir / "orphan.txt").write_text("orphan")
        existing_mtime = (backup_dir / "existing.txt").stat().st_mtime

        # Create source file info
        source_files = {
            Path("new.txt"): FileInfo(
                path=source_dir / "new.txt",
                relative_path=Path("new.txt"),
                size=10,
                mtime=1234567890.0,
            ),
            Path("existing.txt"): FileInfo(
                path=source_dir / "existing.txt",
                relative_path=Path("existing.txt"),
                size=100,  # Different size = modified
                mtime=existing_mtime,
            ),
        }

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 1
        assert len(modified_files) == 1
        assert len(deleted_files) == 1

    def test_detect_with_subdirectories(self, source_dir: Path, backup_dir: Path):
        """Detector should handle subdirectories correctly."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        # Create backup structure
        subdir = backup_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        # Source has new file in subdir
        source_files = {
            Path("subdir/nested.txt"): FileInfo(
                path=source_dir / "subdir" / "nested.txt",
                relative_path=Path("subdir/nested.txt"),
                size=100,  # Different size
                mtime=9999999999.0,
            ),
            Path("subdir/new_nested.txt"): FileInfo(
                path=source_dir / "subdir" / "new_nested.txt",
                relative_path=Path("subdir/new_nested.txt"),
                size=50,
                mtime=1234567890.0,
            ),
        }

        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 1
        assert len(modified_files) == 1
