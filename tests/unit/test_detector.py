"""
Unit tests for core.detector.ChangeDetector.
"""

from pathlib import Path

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

        backup_file = backup_dir / "file1.txt"
        backup_file.write_text("old content")
        backup_mtime = backup_file.stat().st_mtime

        source_files = {
            Path("file1.txt"): FileInfo(
                path=source_dir / "file1.txt",
                relative_path=Path("file1.txt"),
                size=11,
                mtime=backup_mtime + 100,
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

        backup_file = backup_dir / "file1.txt"
        backup_file.write_text("Hello World")
        backup_stat = backup_file.stat()

        source_files = {
            Path("file1.txt"): FileInfo(
                path=source_dir / "file1.txt",
                relative_path=Path("file1.txt"),
                size=backup_stat.st_size,
                mtime=backup_stat.st_mtime,
            ),
        }

        new_files, modified_files, _ = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 0
        assert len(modified_files) == 0

    def test_detect_deleted_files(self, source_dir: Path, backup_dir: Path):
        """Detector should identify files to delete from backup."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        orphan_file = backup_dir / "orphan.txt"
        orphan_file.write_text("orphan content")

        new_files, modified_files, deleted_files = detector.detect_changes(
            {}, backup_dir, logger
        )

        assert len(new_files) == 0
        assert len(modified_files) == 0
        assert len(deleted_files) == 1
        assert backup_dir / "orphan.txt" in deleted_files

    def test_detect_mixed_changes(self, source_dir: Path, backup_dir: Path):
        """Detector should handle mixed changes correctly."""
        detector = ChangeDetector()
        logger = BackupLogger(verbose=False)

        (backup_dir / "existing.txt").write_text("old")
        (backup_dir / "orphan.txt").write_text("orphan")
        existing_mtime = (backup_dir / "existing.txt").stat().st_mtime

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
                size=100,
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

        subdir = backup_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        source_files = {
            Path("subdir/nested.txt"): FileInfo(
                path=source_dir / "subdir" / "nested.txt",
                relative_path=Path("subdir/nested.txt"),
                size=100,
                mtime=9999999999.0,
            ),
            Path("subdir/new_nested.txt"): FileInfo(
                path=source_dir / "subdir" / "new_nested.txt",
                relative_path=Path("subdir/new_nested.txt"),
                size=50,
                mtime=1234567890.0,
            ),
        }

        new_files, modified_files, _ = detector.detect_changes(
            source_files, backup_dir, logger
        )

        assert len(new_files) == 1
        assert len(modified_files) == 1


class TestScopedChangeDetector:
    """Tests for ChangeDetector.detect_changes(..., scoped_folders=...) immunity."""

    def test_scoped_detect_changes_only_deletes_within_selected_folders(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        bak = tmp_path / "bak"
        (src / "Projects").mkdir(parents=True)
        (bak / "Projects").mkdir(parents=True)
        (bak / "Finance").mkdir(parents=True)
        (bak / "_backup_logs").mkdir(parents=True)

        # Keep one file in Projects, remove one from Projects
        keep_src = src / "Projects" / "keep.py"
        keep_src.write_text("keep")
        keep_bak = bak / "Projects" / "keep.py"
        keep_bak.write_text("keep")
        keep_stat = keep_bak.stat()

        obsolete_bak = bak / "Projects" / "deleted_in_scope.py"
        obsolete_bak.write_text("old")

        # Unselected folder, root file, and logs must be immune
        unselected_bak = bak / "Finance" / "budget.xlsx"
        unselected_bak.write_text("safe")
        root_bak = bak / "notes.txt"
        root_bak.write_text("root safe")
        log_bak = bak / "_backup_logs" / "backup.log"
        log_bak.write_text("log safe")

        source_files = {
            Path("Projects/keep.py"): FileInfo(
                path=keep_src,
                relative_path=Path("Projects/keep.py"),
                size=keep_stat.st_size,
                mtime=keep_stat.st_mtime,
            )
        }

        detector = ChangeDetector()
        new_files, modified_files, deleted_files = detector.detect_changes(
            source_files, bak, BackupLogger(verbose=False), scoped_folders=["Projects"]
        )

        assert new_files == []
        assert modified_files == []
        assert deleted_files == [obsolete_bak]
        assert unselected_bak not in deleted_files
        assert root_bak not in deleted_files
        assert log_bak not in deleted_files
