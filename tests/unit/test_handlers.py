"""
Unit tests for handlers module (desktop notification dispatch & escaping).
"""

import subprocess
from unittest.mock import MagicMock, patch

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
