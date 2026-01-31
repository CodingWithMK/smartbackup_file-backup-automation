"""
Tests for the scanner module.
"""

from pathlib import Path

import pytest

from smartbackup.config import DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.ui.logger import BackupLogger


class TestExclusionFilter:
    """Tests for ExclusionFilter class."""

    def test_exact_match_exclusion(self):
        """Exact names should be excluded."""
        filter = ExclusionFilter({"node_modules", "__pycache__"}, set())

        excluded, reason = filter.should_exclude(Path("/project/node_modules"))
        assert excluded is True
        assert "Exact match" in reason

    def test_case_insensitive_exclusion(self):
        """Exclusions should be case insensitive."""
        filter = ExclusionFilter({"node_modules"}, set())

        excluded, _ = filter.should_exclude(Path("/project/NODE_MODULES"))
        assert excluded is True

    def test_extension_exclusion(self):
        """File extensions should be excluded."""
        filter = ExclusionFilter(set(), {".pyc", ".log"})

        excluded, reason = filter.should_exclude(Path("/project/module.pyc"))
        assert excluded is True
        assert "extension" in reason.lower()

    def test_pattern_exclusion_wildcard(self):
        """Wildcard patterns should work."""
        filter = ExclusionFilter({"*.tmp", "*.log"}, set())

        excluded, reason = filter.should_exclude(Path("/project/cache.tmp"))
        assert excluded is True
        assert "Pattern match" in reason

    def test_not_excluded_file(self):
        """Regular files should not be excluded."""
        filter = ExclusionFilter({"node_modules"}, {".pyc"})

        excluded, reason = filter.should_exclude(Path("/project/main.py"))
        assert excluded is False
        assert reason == ""

    def test_venv_detection(self, temp_dir: Path):
        """Virtual environments should be detected."""
        filter = ExclusionFilter(set(), set())

        # Create a venv-like structure
        venv_dir = temp_dir / "my_venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin")

        excluded, reason = filter.should_exclude(venv_dir)
        assert excluded is True
        assert "Virtual environment" in reason

    def test_non_venv_directory(self, temp_dir: Path):
        """Regular directories should not be detected as venv."""
        filter = ExclusionFilter(set(), set())

        regular_dir = temp_dir / "regular"
        regular_dir.mkdir()

        excluded, _ = filter.should_exclude(regular_dir)
        assert excluded is False

    def test_default_exclusions(self):
        """Default exclusions should exclude common dev artifacts."""
        filter = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)

        # Test various common exclusions
        test_cases = [
            (Path("/project/node_modules"), True),
            (Path("/project/__pycache__"), True),
            (Path("/project/.git"), True),
            (Path("/project/dist"), True),
            (Path("/project/build"), True),
            (Path("/project/.vscode"), True),
            (Path("/project/src"), False),
            (Path("/project/main.py"), False),
        ]

        for path, should_exclude in test_cases:
            excluded, _ = filter.should_exclude(path)
            assert excluded == should_exclude, f"Failed for {path}"


class TestFileScanner:
    """Tests for FileScanner class."""

    def test_scanner_creation(self):
        """FileScanner should be creatable."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        assert scanner is not None

    def test_scan_empty_directory(self, temp_dir: Path):
        """Scanning empty directory should return empty dict."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        files = scanner.scan(empty_dir)
        assert files == {}

    def test_scan_finds_files(self, source_dir: Path):
        """Scanner should find files in directory."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        files = scanner.scan(source_dir)

        assert len(files) >= 2  # At least file1.txt and file2.py
        assert Path("file1.txt") in files
        assert Path("file2.py") in files

    def test_scan_finds_nested_files(self, source_dir: Path):
        """Scanner should find files in subdirectories."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        files = scanner.scan(source_dir)

        assert Path("subdir/file3.txt") in files

    def test_scan_excludes_patterns(self, source_with_exclusions: Path):
        """Scanner should exclude matching patterns."""
        filter = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        files = scanner.scan(source_with_exclusions)

        # Check that excluded directories are not in results
        for rel_path in files.keys():
            path_str = str(rel_path)
            assert "node_modules" not in path_str
            assert "__pycache__" not in path_str
            assert ".git" not in path_str
            assert "venv" not in path_str

    def test_scan_file_info_populated(self, source_dir: Path):
        """FileInfo should have correct attributes."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        files = scanner.scan(source_dir)

        file_info = files[Path("file1.txt")]
        assert file_info.path.exists()
        assert file_info.relative_path == Path("file1.txt")
        assert file_info.size > 0
        assert file_info.mtime > 0

    def test_scan_with_hash(self, source_dir: Path):
        """Scanner should calculate hash when enabled."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger, use_hash=True, min_size_for_hash=0)

        files = scanner.scan(source_dir)

        file_info = files[Path("file1.txt")]
        assert file_info.file_hash is not None
        assert len(file_info.file_hash) == 32  # MD5 hex length

    def test_scan_without_hash(self, source_dir: Path):
        """Scanner should not calculate hash when disabled."""
        filter = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger, use_hash=False)

        files = scanner.scan(source_dir)

        file_info = files[Path("file1.txt")]
        assert file_info.file_hash is None

    def test_scan_counts(self, source_with_exclusions: Path):
        """Scanner should track scan and exclusion counts."""
        filter = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filter, logger)

        files = scanner.scan(source_with_exclusions)

        # Should have found some files and excluded some
        assert scanner._scan_count > 0
        assert scanner._excluded_count > 0
