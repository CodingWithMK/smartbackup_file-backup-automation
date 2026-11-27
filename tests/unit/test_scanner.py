"""
Unit tests for the core.scanner module (ExclusionFilter & FileScanner).
"""

import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smartbackup.config import DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.models import FileInfo
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


class TestExclusionFilterHardening:
    """Q2 & Q8 regression tests for regex metacharacters, brackets, and case sensitivity."""

    @pytest.mark.parametrize(
        "pattern,matching_name,non_matching_name",
        [
            ("Backup (1)*", "Backup (1) copy.zip", "Backup 1 copy.zip"),
            ("C++*", "C++_notes.md", "C_notes.md"),
            ("cost$100*.csv", "cost$100_q1.csv", "cost100_q1.csv"),
            ("a+b*.log", "a+b_debug.log", "aab_debug.log"),
            ("a|b*.txt", "a|b_report.txt", "apple.txt"),
            ("file{1,2}*.txt", "file{1,2}_out.txt", "file1_out.txt"),
            ("^start*.tmp", "^start_01.tmp", "start_01.tmp"),
            ("unclosed[bracket*", "unclosed[bracket_v1.txt", "unclosed_v1.txt"),
            ("img_[0-9]*.png", "img_7_final.png", "img_a_final.png"),
            ("file[!0-9]*.txt", "file_a.txt", "file5.txt"),
            ("*.tar.gz", "archive.tar.gz", "archiveXtarYgz"),
            ("temp?.txt", "temp1.txt", "temp12.txt"),
        ],
    )
    def test_metacharacter_patterns_do_not_crash_and_match_literally(
        self, pattern: str, matching_name: str, non_matching_name: str
    ) -> None:
        """Q2: glob patterns with regex metacharacters must never raise re.error or mis-match."""
        filt = ExclusionFilter({pattern}, set())

        assert filt.should_exclude(Path(f"/docs/{matching_name}"))[0] is True
        assert filt.should_exclude(Path(f"/docs/{non_matching_name}"))[0] is False

    def test_reversed_character_range_never_crashes(self) -> None:
        """Q2 fragility guard: reversed character range '[z-a]*' must never raise re.error."""
        filt = ExclusionFilter({"draft[z-a]*"}, set())
        # Must not crash regardless of Python 3.9-3.13 fnmatch.translate behavior
        assert isinstance(filt.should_exclude(Path("/docs/draft_x.txt"))[0], bool)

    def test_re_error_during_compile_logs_warning_and_falls_back_to_literal_glob(self) -> None:
        """Q2 fragility guard: if fnmatch.translate() yields an invalid regex, fall back safely."""
        mock_logger = MagicMock()
        real_compile = __import__("re").compile
        call_count = 0

        def fail_first_compile(pattern: str, flags: int = 0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise __import__("re").error("bad character range z-a")
            return real_compile(pattern, flags)

        with patch("smartbackup.core.scanner.re.compile", side_effect=fail_first_compile):
            filt = ExclusionFilter({"draft[z-a]*"}, set(), logger=mock_logger)

        mock_logger.warning.assert_called_once()
        assert "draft[z-a]*" in mock_logger.warning.call_args[0][0]
        assert filt.should_exclude(Path("/docs/draft[z-a]_v1.txt"))[0] is True
        assert filt.should_exclude(Path("/docs/draftb_v1.txt"))[0] is False

    def test_exact_folder_name_with_brackets_matches_literally(self) -> None:
        """Q2 fragility guard: bare brackets without */? stay literal exact matches."""
        filt = ExclusionFilter({"Archive [2026]"}, set())

        assert filt.should_exclude(Path("/docs/Archive [2026]"))[0] is True
        assert filt.should_exclude(Path("/docs/Archive 2"))[0] is False

    def test_case_insensitive_default_and_case_sensitive_opt_in(self) -> None:
        """Q8: default preserves cross-platform case-insensitivity; opt-in enforces exact case."""
        default_filt = ExclusionFilter({"build", "*.TMP"}, {".pyc"})
        assert default_filt.should_exclude(Path("/repo/Build"))[0] is True
        assert default_filt.should_exclude(Path("/repo/notes.tmp"))[0] is True
        assert default_filt.should_exclude(Path("/repo/MOD.PYC"))[0] is True

        cs_filt = ExclusionFilter({"build", "*.TMP"}, {".pyc"}, case_sensitive=True)
        assert cs_filt.should_exclude(Path("/repo/build"))[0] is True
        assert cs_filt.should_exclude(Path("/repo/Build"))[0] is False
        assert cs_filt.should_exclude(Path("/repo/notes.TMP"))[0] is True
        assert cs_filt.should_exclude(Path("/repo/notes.tmp"))[0] is False
        assert cs_filt.should_exclude(Path("/repo/mod.pyc"))[0] is True
        assert cs_filt.should_exclude(Path("/repo/MOD.PYC"))[0] is False


class TestFileScannerHashErrors:
    """Q1 regression tests for FileScanner._calculate_hash and hash_error propagation."""

    def test_calculate_hash_returns_none_and_logs_warning_on_read_error(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "locked.txt"
        target.write_text("data")
        mock_logger = MagicMock()
        scanner = FileScanner(ExclusionFilter(set(), set()), mock_logger, use_hash=True)

        with patch("builtins.open", side_effect=PermissionError("denied")):
            digest = scanner._calculate_hash(target)

        assert digest is None
        mock_logger.warning.assert_called_once()
        assert "Could not hash" in mock_logger.warning.call_args[0][0]

    def test_scan_sets_hash_error_only_when_hashing_attempted_and_failed(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        unreadable = src / "unreadable.txt"
        unreadable.write_text("small")
        big = src / "big.txt"
        big.write_text("A" * 100)
        ok_file = src / "ok.txt"
        ok_file.write_text("good")

        mock_logger = MagicMock()
        scanner = FileScanner(
            ExclusionFilter(set(), set()),
            mock_logger,
            use_hash=True,
            max_size_for_hash=20,
        )

        real_open = builtins.open

        def fail_unreadable(file, *args, **kwargs):
            if Path(file) == unreadable:
                raise OSError("bad sector")
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_unreadable):
            files = scanner.scan(src)

        assert files[Path("unreadable.txt")].file_hash is None
        assert files[Path("unreadable.txt")].hash_error is True

        # Skipped due to threshold: file_hash is None but hash_error MUST be False
        assert files[Path("big.txt")].file_hash is None
        assert files[Path("big.txt")].hash_error is False

        # Control: readable small file hashed cleanly
        assert files[Path("ok.txt")].file_hash is not None
        assert files[Path("ok.txt")].hash_error is False

    def test_file_info_needs_update_respects_hash_error(self) -> None:
        src = FileInfo(Path("/a"), Path("a"), size=10, mtime=100.0, file_hash=None, hash_error=True)
        bak = FileInfo(Path("/b"), Path("a"), size=10, mtime=100.0, file_hash="a" * 64)

        assert src.needs_update(bak, use_hash=True) is True
        assert src.needs_update(bak, use_hash=False) is False

        # Control: no hash_error and matching size/mtime -> False
        clean = FileInfo(Path("/a"), Path("a"), size=10, mtime=100.0, file_hash=None, hash_error=False)
        assert clean.needs_update(bak, use_hash=True) is False
