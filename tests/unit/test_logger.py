"""
Unit tests for ui.colors and ui.logger.
"""

from pathlib import Path

import pytest

from smartbackup.models import BackupResult, FileAction
from smartbackup.ui.colors import Colors
from smartbackup.ui.logger import BackupLogger


class TestColors:
    """Tests for Colors class."""

    def test_colors_have_values(self):
        assert Colors.RED != ""
        assert Colors.GREEN != ""
        assert Colors.BLUE != ""
        assert Colors.YELLOW != ""
        assert Colors.CYAN != ""
        assert Colors.END != ""

    def test_colors_disable(self, monkeypatch: pytest.MonkeyPatch):
        color_attrs = (
            "HEADER",
            "BLUE",
            "CYAN",
            "GREEN",
            "YELLOW",
            "RED",
            "BOLD",
            "UNDERLINE",
            "END",
        )
        for attr in color_attrs:
            monkeypatch.setattr(Colors, attr, getattr(Colors, attr))

        Colors.disable()

        assert Colors.RED == ""
        assert Colors.GREEN == ""
        assert Colors.BLUE == ""
        assert Colors.END == ""


class TestBackupLogger:
    """Tests for BackupLogger class."""

    def test_logger_creation(self):
        logger = BackupLogger(verbose=True)
        assert logger is not None

    def test_logger_verbose_setting(self):
        assert BackupLogger(verbose=True).verbose is True
        assert BackupLogger(verbose=False).verbose is False

    def test_format_size_bytes(self):
        assert "B" in BackupLogger()._format_size(100)

    def test_format_size_kilobytes(self):
        assert "KB" in BackupLogger()._format_size(1024)

    def test_format_size_megabytes(self):
        assert "MB" in BackupLogger()._format_size(1024 * 1024)

    def test_format_size_gigabytes(self):
        assert "GB" in BackupLogger()._format_size(1024 * 1024 * 1024)

    def test_timestamp_format(self):
        timestamp = BackupLogger()._timestamp()
        assert "-" in timestamp
        assert ":" in timestamp

    def test_log_buffer(self, tmp_path: Path):
        log_path = tmp_path / "test.log"
        logger = BackupLogger(log_file=log_path, verbose=False)
        logger._log_to_file("Test message 1")
        logger._log_to_file("Test message 2")
        assert len(logger._log_buffer) == 2

    def test_flush_to_file(self, tmp_path: Path):
        log_path = tmp_path / "test.log"
        logger = BackupLogger(log_file=log_path, verbose=False)
        logger._log_to_file("Test message")
        logger.flush_to_file()

        assert "Test message" in log_path.read_text()

    def test_file_action_logging(self, capsys):
        logger = BackupLogger(verbose=True)
        logger.file_action(FileAction.COPIED, Path("test.txt"), "100 KB")

        captured = capsys.readouterr()
        assert "COPIED" in captured.out
        assert "test.txt" in captured.out

    def test_summary_output(self, capsys):
        logger = BackupLogger(verbose=True)
        result = BackupResult(
            total_files=100,
            copied_files=50,
            updated_files=10,
            skipped_files=38,
            errors=2,
            copied_size=1024 * 1024 * 10,
        )
        result.end_time = result.start_time

        logger.summary(result)

        captured = capsys.readouterr()
        assert "SUMMARY" in captured.out
        assert "50" in captured.out
        assert "10" in captured.out

    def test_progress_bar(self, capsys):
        logger = BackupLogger(verbose=True)
        logger.progress(50, 100, "test.txt", 1024, 2048)
        assert logger._progress_line_active is True
        logger._stop_progress()

    def test_clear_progress_line(self, capsys):
        logger = BackupLogger(verbose=True)
        logger._progress_line_active = True
        logger._clear_progress_line()
        assert logger._progress_line_active is False

    def test_file_action_does_not_recreate_progress_bar(self, capsys):
        """Logging file actions/warnings during backup must reuse one Progress instance."""
        logger = BackupLogger(verbose=True)
        try:
            logger.progress(1, 5, "file1.txt", 100, 500)
            bar_instance = logger._progress_bar
            assert bar_instance is not None
            assert logger._progress_line_active is True

            logger.file_action(FileAction.COPIED, Path("file1.txt"), "0.1 KB")
            logger.warning("transient warning")
            logger.info("mid-copy info")
            logger.error("single file error")

            assert logger._progress_bar is bar_instance
            assert logger._progress_line_active is True

            logger.progress(2, 5, "file2.txt", 200, 500)
            assert logger._progress_bar is bar_instance
        finally:
            logger.stop_progress()

        assert logger._progress_bar is None
        assert logger._progress_line_active is False

        captured = capsys.readouterr()
        assert "COPIED" in captured.out
        assert "file1.txt" in captured.out
