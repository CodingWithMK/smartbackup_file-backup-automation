"""
Unit tests for platform.scheduler.SchedulerHelper.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from smartbackup.platform.scheduler import SchedulerHelper


class TestSchedulerHelper:
    """Tests for SchedulerHelper scheduled backups and daemon management."""

    def test_setup_scheduled_backup_calls_platform_method(self):
        """Verify setup_scheduled_backup dispatches by OS."""
        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_setup_macos_launchd") as mock_mac,
        ):
            SchedulerHelper.setup_scheduled_backup(12)
            mock_mac.assert_called_once()

        with (
            patch("platform.system", return_value="Windows"),
            patch.object(SchedulerHelper, "_setup_windows_task") as mock_win,
        ):
            SchedulerHelper.setup_scheduled_backup(12)
            mock_win.assert_called_once()

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_setup_linux_cron") as mock_lin,
        ):
            SchedulerHelper.setup_scheduled_backup(12)
            mock_lin.assert_called_once()

    def test_install_daemon_service_macos(self, tmp_path: Path):
        fake_plist = tmp_path / "com.smartbackup.watcher.plist"
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_get_macos_plist_path", return_value=fake_plist),
            patch("subprocess.run", return_value=mock_res) as mock_run,
        ):
            success, _ = SchedulerHelper.install_daemon_service(python_exe="python3")
            assert success is True
            assert fake_plist.exists()
            content = fake_plist.read_text()
            assert "com.smartbackup.watcher" in content
            assert "smartbackup" in content
            assert "watch" in content
            assert mock_run.call_count >= 2

    def test_uninstall_daemon_service_macos(self, tmp_path: Path):
        fake_plist = tmp_path / "com.smartbackup.watcher.plist"
        fake_plist.parent.mkdir(parents=True, exist_ok=True)
        fake_plist.write_text("<plist></plist>")
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_get_macos_plist_path", return_value=fake_plist),
            patch("subprocess.run", return_value=mock_res),
        ):
            success, _ = SchedulerHelper.uninstall_daemon_service()
            assert success is True
            assert not fake_plist.exists()

    def test_get_daemon_status_macos_running(self, tmp_path: Path):
        fake_plist = tmp_path / "com.smartbackup.watcher.plist"
        fake_plist.write_text("<plist></plist>")
        mock_res = MagicMock(
            returncode=0,
            stdout='"PID" = 12345;\n"Label" = "com.smartbackup.watcher";',
        )

        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_get_macos_plist_path", return_value=fake_plist),
            patch("subprocess.run", return_value=mock_res),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is True
            assert status["running"] is True
            assert status["pid"] == 12345

    def test_get_daemon_status_macos_stopped(self, tmp_path: Path):
        fake_plist = tmp_path / "com.smartbackup.watcher.plist"
        fake_plist.write_text("<plist></plist>")
        mock_res = MagicMock(
            returncode=0,
            stdout='"Label" = "com.smartbackup.watcher";\n"LastExitStatus" = 0;',
        )

        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_get_macos_plist_path", return_value=fake_plist),
            patch("subprocess.run", return_value=mock_res),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is True
            assert status["running"] is False
            assert status["pid"] is None

    def test_install_daemon_service_windows(self):
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run", return_value=mock_res) as mock_run,
        ):
            success, _ = SchedulerHelper.install_daemon_service(python_exe="python.exe")
            assert success is True
            assert mock_run.call_count >= 1
            cmd_called = mock_run.call_args_list[0][0][0]
            assert "schtasks" in cmd_called
            assert "SmartBackupWatcher" in cmd_called

    def test_uninstall_daemon_service_windows(self):
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run", return_value=mock_res) as mock_run,
        ):
            success, _ = SchedulerHelper.uninstall_daemon_service()
            assert success is True
            mock_run.assert_called_once()
            cmd_called = mock_run.call_args[0][0]
            assert "schtasks" in cmd_called
            assert "/delete" in cmd_called
            assert "SmartBackupWatcher" in cmd_called

    def test_get_daemon_status_windows_running(self):
        mock_res = MagicMock(
            returncode=0,
            stdout="TaskName: SmartBackupWatcher\nStatus: Running",
        )

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run", return_value=mock_res),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is True
            assert status["running"] is True

    def test_get_daemon_status_windows_ready(self):
        mock_res = MagicMock(
            returncode=0,
            stdout="TaskName: SmartBackupWatcher\nStatus: Ready",
        )

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run", return_value=mock_res),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is True
            assert status["running"] is False

    def test_get_daemon_status_windows_not_installed(self):
        mock_res = MagicMock(
            returncode=1,
            stdout="ERROR: The system cannot find the file specified.",
        )

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run", return_value=mock_res),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is False
            assert status["running"] is False

    def test_install_daemon_service_linux(self, tmp_path: Path):
        fake_service = tmp_path / "smartbackup-watcher.service"
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_get_linux_service_path", return_value=fake_service),
            patch("subprocess.run", return_value=mock_res) as mock_run,
        ):
            success, _ = SchedulerHelper.install_daemon_service(python_exe="python3")
            assert success is True
            assert fake_service.exists()
            content = fake_service.read_text()
            assert "SmartBackup USB Auto-Detect Daemon" in content
            assert "smartbackup watch" in content
            assert mock_run.call_count >= 2

    def test_uninstall_daemon_service_linux(self, tmp_path: Path):
        fake_service = tmp_path / "smartbackup-watcher.service"
        fake_service.parent.mkdir(parents=True, exist_ok=True)
        fake_service.write_text("[Unit]")
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_get_linux_service_path", return_value=fake_service),
            patch("subprocess.run", return_value=mock_res) as mock_run,
        ):
            success, _ = SchedulerHelper.uninstall_daemon_service()
            assert success is True
            assert not fake_service.exists()
            assert mock_run.call_count >= 2

    def test_get_daemon_status_linux_running(self, tmp_path: Path):
        fake_service = tmp_path / "smartbackup-watcher.service"
        fake_service.write_text("[Unit]")

        def _mock_run(cmd, *args, **kwargs):
            res = MagicMock(returncode=0)
            if "is-active" in cmd:
                res.stdout = "active\n"
            elif "show" in cmd:
                res.stdout = "MainPID=67890\n"
            else:
                res.stdout = ""
            return res

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_get_linux_service_path", return_value=fake_service),
            patch("subprocess.run", side_effect=_mock_run),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is True
            assert status["running"] is True
            assert status["pid"] == 67890

    def test_get_daemon_status_linux_not_installed(self, tmp_path: Path):
        fake_service = tmp_path / "nonexistent.service"

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_get_linux_service_path", return_value=fake_service),
        ):
            status = SchedulerHelper.get_daemon_status()
            assert status["installed"] is False
            assert status["running"] is False
