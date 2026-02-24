"""
Tests for the logger module.
"""

import tempfile
from pathlib import Path

import pytest

from smartbackup.models import BackupResult, FileAction
from smartbackup.ui.colors import Colors
from smartbackup.ui.logger import BackupLogger


class TestColors:
    """Tests for Colors class."""

    def test_colors_have_values(self):
        """Color codes should have values."""
        assert Colors.RED != ""
        assert Colors.GREEN != ""
        assert Colors.BLUE != ""
        assert Colors.YELLOW != ""
        assert Colors.CYAN != ""
        assert Colors.END != ""

    def test_colors_disable(self):
        """Colors should be disableable."""
        # Save original values
        original_red = Colors.RED
        original_green = Colors.GREEN

        # Disable colors
        Colors.disable()

        # All should be empty
        assert Colors.RED == ""
        assert Colors.GREEN == ""
        assert Colors.BLUE == ""
        assert Colors.END == ""

        # Restore (for other tests)
        Colors.RED = original_red
        Colors.GREEN = original_green
        Colors.HEADER = "\033[95m"
        Colors.BLUE = "\033[94m"
        Colors.CYAN = "\033[96m"
        Colors.YELLOW = "\033[93m"
        Colors.BOLD = "\033[1m"
        Colors.UNDERLINE = "\033[4m"
        Colors.END = "\033[0m"


class TestBackupLogger:
    """Tests for BackupLogger class."""

    def test_logger_creation(self):
        """Logger should be creatable."""
        logger = BackupLogger(verbose=True)
        assert logger is not None

    def test_logger_verbose_setting(self):
        """Logger should respect verbose setting."""
        logger = BackupLogger(verbose=True)
        assert logger.verbose is True

        logger2 = BackupLogger(verbose=False)
        assert logger2.verbose is False

    def test_format_size_bytes(self):
        """Size formatting should work for bytes."""
        logger = BackupLogger()
        assert "B" in logger._format_size(100)

    def test_format_size_kilobytes(self):
        """Size formatting should work for kilobytes."""
        logger = BackupLogger()
        assert "KB" in logger._format_size(1024)

    def test_format_size_megabytes(self):
        """Size formatting should work for megabytes."""
        logger = BackupLogger()
        assert "MB" in logger._format_size(1024 * 1024)

    def test_format_size_gigabytes(self):
        """Size formatting should work for gigabytes."""
        logger = BackupLogger()
        assert "GB" in logger._format_size(1024 * 1024 * 1024)

    def test_timestamp_format(self):
        """Timestamp should be properly formatted."""
        logger = BackupLogger()
        timestamp = logger._timestamp()

        # Should contain date and time separators
        assert "-" in timestamp
        assert ":" in timestamp

    def test_log_buffer(self):
        """Log buffer should accumulate messages."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = Path(f.name)

        logger = BackupLogger(log_file=log_path, verbose=False)
        logger._log_to_file("Test message 1")
        logger._log_to_file("Test message 2")

        assert len(logger._log_buffer) == 2

    def test_flush_to_file(self):
        """Flushing should write buffer to file."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = Path(f.name)

        logger = BackupLogger(log_file=log_path, verbose=False)
        logger._log_to_file("Test message")
        logger.flush_to_file()

        content = log_path.read_text()
        assert "Test message" in content

        # Cleanup
        log_path.unlink()

    def test_file_action_logging(self, capsys):
        """File action logging should work."""
        logger = BackupLogger(verbose=True)
        logger.file_action(FileAction.COPIED, Path("test.txt"), "100 KB")

        captured = capsys.readouterr()
        assert "COPIED" in captured.out
        assert "test.txt" in captured.out

    def test_summary_output(self, capsys):
        """Summary should display correctly."""
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
        assert "50" in captured.out  # copied files
        assert "10" in captured.out  # updated files

    def test_progress_bar(self, capsys):
        """Progress bar should render."""
        logger = BackupLogger(verbose=True)
        logger.progress(50, 100, "test.txt", 1024, 2048)

        # The Rich progress bar is transient, so it may not leave content
        # in captured output, but the internal state should be active
        assert logger._progress_line_active is True

        # Clean up the progress bar
        logger._stop_progress()

    def test_clear_progress_line(self, capsys):
        """Clearing progress line should work."""
        logger = BackupLogger(verbose=True)
        logger._progress_line_active = True
        logger._clear_progress_line()

        assert logger._progress_line_active is False
