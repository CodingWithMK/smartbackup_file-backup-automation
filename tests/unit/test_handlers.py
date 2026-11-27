"""
Unit tests for handlers module (desktop notification dispatch & escaping).
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from smartbackup.backup import DEFAULT_MAX_RETRIES, SmartBackup
from smartbackup.handlers import FallbackHandler, _escape_applescript, _escape_powershell
from smartbackup.models import BackupResult
from smartbackup.ui.logger import BackupLogger


def _sample_result(copied: int = 3, updated: int = 1, skipped: int = 5, errors: int = 0):
    return BackupResult(
        copied_files=copied,
        updated_files=updated,
        skipped_files=skipped,
        errors=errors,
    )


class TestEscapingHelpers:
    def test_escape_applescript(self):
        assert _escape_applescript('hello "world" \\ test') == 'hello \\"world\\" \\\\ test'

    def test_escape_powershell(self):
        assert _escape_powershell("O'Brien's Drive") == "O''Brien''s Drive"


class TestDesktopNotifications:
    def test_default_does_not_invoke_desktop_notification(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        with patch("smartbackup.handlers.subprocess.run") as mock_run:
            handler.notify_completion(_sample_result(), success=True)
        mock_run.assert_not_called()

    def test_macos_osascript_dispatch(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        completed = MagicMock(returncode=0)
        with (
            patch("smartbackup.handlers.platform.system", return_value="Darwin"),
            patch("smartbackup.handlers.shutil.which", return_value="/usr/bin/osascript"),
            patch("smartbackup.handlers.subprocess.run", return_value=completed) as mock_run,
        ):
            handler.notify_completion(
                _sample_result(copied=4, updated=2, skipped=1), True, desktop=True
            )

        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "/usr/bin/osascript"
        assert cmd[1] == "-e"
        assert "SmartBackup" in cmd[2]
        assert "Copied: 4, Updated: 2, Skipped: 1" in cmd[2]

    def test_linux_notify_send_dispatch(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        completed = MagicMock(returncode=0)
        with (
            patch("smartbackup.handlers.platform.system", return_value="Linux"),
            patch("smartbackup.handlers.shutil.which", return_value="/usr/bin/notify-send"),
            patch("smartbackup.handlers.subprocess.run", return_value=completed) as mock_run,
        ):
            handler.notify_completion(_sample_result(errors=2), False, desktop=True)

        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "/usr/bin/notify-send"
        assert "Errors" in cmd[1]
        assert "Errors: 2" in cmd[2]

    def test_windows_powershell_dispatch(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        completed = MagicMock(returncode=0)
        with (
            patch("smartbackup.handlers.platform.system", return_value="Windows"),
            patch("smartbackup.handlers.shutil.which", return_value="powershell.exe"),
            patch("smartbackup.handlers.subprocess.run", return_value=completed) as mock_run,
        ):
            handler.notify_completion(_sample_result(), True, desktop=True)

        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "powershell.exe"
        assert "ShowBalloonTip" in cmd[-1]

    def test_missing_notifier_binary_is_non_fatal(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        with (
            patch("smartbackup.handlers.platform.system", return_value="Linux"),
            patch("smartbackup.handlers.shutil.which", return_value=None),
            patch("smartbackup.handlers.subprocess.run") as mock_run,
        ):
            assert handler._send_desktop_notification("Title", "Body") is False
        mock_run.assert_not_called()

    def test_subprocess_timeout_is_non_fatal(self):
        handler = FallbackHandler(BackupLogger(verbose=False))
        with (
            patch("smartbackup.handlers.platform.system", return_value="Darwin"),
            patch("smartbackup.handlers.shutil.which", return_value="/usr/bin/osascript"),
            patch(
                "smartbackup.handlers.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["osascript"], timeout=5),
            ),
        ):
            assert handler._send_desktop_notification("Title", "Body") is False


class TestFallbackHandlerNoDevice:
    """Q5 regression tests for EOFError, KeyboardInterrupt, and SmartBackup retry loop."""

    def test_handle_no_device_catches_eof_on_prompt_ask(self, tmp_path: Path) -> None:
        mock_logger = MagicMock()
        handler = FallbackHandler(mock_logger)

        with patch("smartbackup.handlers.Prompt.ask", side_effect=EOFError):
            result = handler.handle_no_device(tmp_path)

        assert result is None
        assert handler.last_cancelled is True
        mock_logger.info.assert_called_once()
        assert "non-interactive" in mock_logger.info.call_args[0][0].lower()

    def test_handle_no_device_catches_eof_on_retry_input(self, tmp_path: Path) -> None:
        mock_logger = MagicMock()
        handler = FallbackHandler(mock_logger)

        with (
            patch("smartbackup.handlers.Prompt.ask", return_value="2"),
            patch("builtins.input", side_effect=EOFError),
        ):
            result = handler.handle_no_device(tmp_path)

        assert result is None
        assert handler.last_cancelled is True
        assert "non-interactive" in mock_logger.info.call_args[0][0].lower()

    def test_handle_no_device_catches_keyboard_interrupt(self, tmp_path: Path) -> None:
        mock_logger = MagicMock()
        handler = FallbackHandler(mock_logger)

        with patch("smartbackup.handlers.Prompt.ask", side_effect=KeyboardInterrupt):
            result = handler.handle_no_device(tmp_path)

        assert result is None
        assert handler.last_cancelled is True
        assert "cancelled by user" in mock_logger.info.call_args[0][0].lower()

    def test_handle_no_device_cancel_sets_last_cancelled_true(self, tmp_path: Path) -> None:
        handler = FallbackHandler(MagicMock())

        with patch("smartbackup.handlers.Prompt.ask", return_value="3"):
            result = handler.handle_no_device(tmp_path)

        assert result is None
        assert handler.last_cancelled is True

    def test_handle_no_device_retry_sets_last_cancelled_false(self, tmp_path: Path) -> None:
        handler = FallbackHandler(MagicMock())

        with (
            patch("smartbackup.handlers.Prompt.ask", return_value="2"),
            patch("builtins.input", return_value=""),
        ):
            result = handler.handle_no_device(tmp_path)

        assert result is None
        assert handler.last_cancelled is False

    def test_handle_no_device_local_backup_and_oserror(self, tmp_path: Path) -> None:
        handler = FallbackHandler(MagicMock())

        with (
            patch("smartbackup.handlers.Path.home", return_value=tmp_path),
            patch("smartbackup.handlers.Prompt.ask", return_value="1"),
        ):
            result = handler.handle_no_device(tmp_path)

        assert result == tmp_path / ".local_backup_temp"
        assert result.is_dir()
        assert handler.last_cancelled is False

        # Unwritable home dir should fail gracefully and mark cancelled
        mock_logger = MagicMock()
        handler2 = FallbackHandler(mock_logger)
        with (
            patch("smartbackup.handlers.Path.home", return_value=tmp_path),
            patch("smartbackup.handlers.Prompt.ask", return_value="1"),
            patch("pathlib.Path.mkdir", side_effect=OSError("read-only home")),
        ):
            result2 = handler2.handle_no_device(tmp_path)

        assert result2 is None
        assert handler2.last_cancelled is True
        mock_logger.error.assert_called_once()

    def test_smartbackup_run_stops_retrying_immediately_on_eof_or_cancel(
        self, tmp_path: Path
    ) -> None:
        """Q5 fragility guard: SmartBackup.run() must NOT loop 3x on cancel or EOF."""
        src = tmp_path / "src"
        src.mkdir()

        for side_effect in (EOFError, KeyboardInterrupt):
            sb = SmartBackup()
            sb.logger = BackupLogger(verbose=False)
            sb.fallback.logger = sb.logger

            with (
                patch("smartbackup.backup.DeviceDetector.find_backup_device", return_value=None),
                patch("smartbackup.handlers.Prompt.ask", side_effect=side_effect) as mock_ask,
            ):
                ok = sb.run(custom_source=src)

            assert ok is False
            assert mock_ask.call_count == 1

        # Explicit cancel choice "3" also exits on attempt 1
        sb_cancel = SmartBackup()
        sb_cancel.logger = BackupLogger(verbose=False)
        sb_cancel.fallback.logger = sb_cancel.logger
        with (
            patch("smartbackup.backup.DeviceDetector.find_backup_device", return_value=None),
            patch("smartbackup.handlers.Prompt.ask", return_value="3") as mock_ask,
        ):
            assert sb_cancel.run(custom_source=src) is False
        assert mock_ask.call_count == 1

        # Control: explicit retry choice "2" retries DEFAULT_MAX_RETRIES times
        sb_retry = SmartBackup()
        sb_retry.logger = BackupLogger(verbose=False)
        sb_retry.fallback.logger = sb_retry.logger
        with (
            patch("smartbackup.backup.DeviceDetector.find_backup_device", return_value=None),
            patch("smartbackup.handlers.Prompt.ask", return_value="2") as mock_ask,
            patch("builtins.input", return_value=""),
        ):
            assert sb_retry.run(custom_source=src) is False
        assert mock_ask.call_count == DEFAULT_MAX_RETRIES
