"""
Unit tests for the core.scanner module (ExclusionFilter & FileScanner).
"""

from pathlib import Path

from smartbackup.config import DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.ui.logger import BackupLogger


class TestExclusionFilter:
    """Tests for ExclusionFilter class."""

    def test_exact_match_exclusion(self):
        """Exact names should be excluded."""
        filt = ExclusionFilter({"node_modules", "__pycache__"}, set())

        excluded, reason = filt.should_exclude(Path("/project/node_modules"))
        assert excluded is True
        assert "Exact match" in reason

    def test_case_insensitive_exclusion(self):
        """Exclusions should be case insensitive."""
        filt = ExclusionFilter({"node_modules"}, set())

        excluded, _ = filt.should_exclude(Path("/project/NODE_MODULES"))
        assert excluded is True

    def test_extension_exclusion(self):
        """File extensions should be excluded."""
        filt = ExclusionFilter(set(), {".pyc", ".log"})

        excluded, reason = filt.should_exclude(Path("/project/module.pyc"))
        assert excluded is True
        assert "extension" in reason.lower()

    def test_pattern_exclusion_wildcard(self):
        """Wildcard patterns should work."""
        filt = ExclusionFilter({"*.tmp", "*.log"}, set())

        excluded, reason = filt.should_exclude(Path("/project/cache.tmp"))
        assert excluded is True
        assert "Pattern match" in reason

    def test_not_excluded_file(self):
        """Regular files should not be excluded."""
        filt = ExclusionFilter({"node_modules"}, {".pyc"})

        excluded, reason = filt.should_exclude(Path("/project/main.py"))
        assert excluded is False
        assert reason == ""

    def test_venv_detection(self, tmp_path: Path):
        """Virtual environments should be detected."""
        filt = ExclusionFilter(set(), set())

        venv_dir = tmp_path / "my_venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin")

        excluded, reason = filt.should_exclude(venv_dir)
        assert excluded is True
        assert "Virtual environment" in reason

    def test_non_venv_directory(self, tmp_path: Path):
        """Regular directories should not be detected as venv."""
        filt = ExclusionFilter(set(), set())

        regular_dir = tmp_path / "regular"
        regular_dir.mkdir()

        excluded, _ = filt.should_exclude(regular_dir)
        assert excluded is False

    def test_default_exclusions(self):
        """Default exclusions should exclude common dev artifacts."""
        filt = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)

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
            excluded, _ = filt.should_exclude(path)
            assert excluded == should_exclude, f"Failed for {path}"


class TestFileScanner:
    """Tests for FileScanner class."""

    def test_scanner_creation(self):
        """FileScanner should be creatable."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)
        assert scanner is not None

    def test_scan_empty_directory(self, tmp_path: Path):
        """Scanning empty directory should return empty dict."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        assert scanner.scan(empty_dir) == {}

    def test_scan_finds_files(self, source_dir: Path):
        """Scanner should find files in directory."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        files = scanner.scan(source_dir)
        assert len(files) >= 2
        assert Path("file1.txt") in files
        assert Path("file2.py") in files

    def test_scan_finds_nested_files(self, source_dir: Path):
        """Scanner should find files in subdirectories."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        files = scanner.scan(source_dir)
        assert Path("subdir/file3.txt") in files

    def test_scan_excludes_patterns(self, source_with_exclusions: Path):
        """Scanner should exclude matching patterns."""
        filt = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        files = scanner.scan(source_with_exclusions)
        for rel_path in files:
            path_str = str(rel_path)
            assert "node_modules" not in path_str
            assert "__pycache__" not in path_str
            assert ".git" not in path_str
            assert "venv" not in path_str

    def test_scan_file_info_populated(self, source_dir: Path):
        """FileInfo should have correct attributes."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        files = scanner.scan(source_dir)
        file_info = files[Path("file1.txt")]
        assert file_info.path.exists()
        assert file_info.relative_path == Path("file1.txt")
        assert file_info.size > 0
        assert file_info.mtime > 0

    def test_scan_with_hash(self, source_dir: Path):
        """Scanner should calculate hash when enabled."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=True, max_size_for_hash=50 * 1024 * 1024)

        files = scanner.scan(source_dir)
        file_info = files[Path("file1.txt")]
        assert file_info.file_hash is not None
        assert len(file_info.file_hash) == 64

    def test_scan_without_hash(self, source_dir: Path):
        """Scanner should not calculate hash when disabled."""
        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=False)

        files = scanner.scan(source_dir)
        file_info = files[Path("file1.txt")]
        assert file_info.file_hash is None

    def test_scan_counts(self, source_with_exclusions: Path):
        """Scanner should track scan and exclusion counts."""
        filt = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger)

        scanner.scan(source_with_exclusions)
        assert scanner._scan_count > 0
        assert scanner._excluded_count > 0

    def test_scanner_hashes_when_enabled(self, tmp_path: Path) -> None:
        """FileScanner with use_hash=True should compute hashes for small files."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "small.txt").write_text("hello world")

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=True, max_size_for_hash=50 * 1024 * 1024)

        files = scanner.scan(source)
        info = files[Path("small.txt")]
        assert info.file_hash is not None
        assert len(info.file_hash) == 64

    def test_scanner_skips_hash_when_disabled(self, tmp_path: Path) -> None:
        """FileScanner with use_hash=False should leave file_hash as None."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "small.txt").write_text("hello world")

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=False)

        files = scanner.scan(source)
        assert files[Path("small.txt")].file_hash is None

    def test_scanner_respects_max_size_threshold(self, tmp_path: Path) -> None:
        """Files above max_size_for_hash should not be hashed (unless hash_all)."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "big.txt").write_text("A" * 100)

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=True, max_size_for_hash=10)

        files = scanner.scan(source)
        assert files[Path("big.txt")].file_hash is None

    def test_scanner_hash_all_overrides_threshold(self, tmp_path: Path) -> None:
        """With hash_all=True, files above threshold should still be hashed."""
        source = tmp_path / "src"
        source.mkdir()
        (source / "big.txt").write_text("A" * 100)

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(
            filt, logger, use_hash=True, hash_all=True, max_size_for_hash=10
        )

        files = scanner.scan(source)
        info = files[Path("big.txt")]
        assert info.file_hash is not None
        assert len(info.file_hash) == 64


class TestScopedFileScanner:
    """Tests for FileScanner.scan(..., include_folders=...) selective scanning."""

    def test_scan_include_folders_returns_only_selected_with_root_relative_paths(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "root.txt").write_text("root loose file")
        (tmp_path / "Projects").mkdir()
        (tmp_path / "Projects" / "app.py").write_text("print(1)")
        (tmp_path / "Projects" / "sub").mkdir()
        (tmp_path / "Projects" / "sub" / "mod.py").write_text("x = 1")
        (tmp_path / "Finance").mkdir()
        (tmp_path / "Finance" / "budget.csv").write_text("a,b")

        scanner = FileScanner(ExclusionFilter(set(), set()), BackupLogger(verbose=False))
        files = scanner.scan(tmp_path, include_folders=["Projects"])

        assert set(files.keys()) == {
            Path("Projects/app.py"),
            Path("Projects/sub/mod.py"),
        }
        assert files[Path("Projects/app.py")].relative_path == Path("Projects/app.py")

    def test_scan_include_folders_applies_exclusions_inside_selected_folder(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "Projects").mkdir()
        (tmp_path / "Projects" / "main.py").write_text("ok")
        (tmp_path / "Projects" / "node_modules").mkdir()
        (tmp_path / "Projects" / "node_modules" / "pkg.js").write_text("skip")

        scanner = FileScanner(
            ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS),
            BackupLogger(verbose=False),
        )
        files = scanner.scan(tmp_path, include_folders=["Projects"])

        assert set(files.keys()) == {Path("Projects/main.py")}

    def test_scan_include_folders_skips_missing_folder_gracefully(self, tmp_path: Path) -> None:
        (tmp_path / "Projects").mkdir()
        (tmp_path / "Projects" / "a.txt").write_text("a")

        scanner = FileScanner(ExclusionFilter(set(), set()), BackupLogger(verbose=False))
        files = scanner.scan(tmp_path, include_folders=["Projects", "DoesNotExist"])

        assert set(files.keys()) == {Path("Projects/a.txt")}
