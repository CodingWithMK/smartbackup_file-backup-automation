"""
Tests for CLI daemon and watch commands, and interactive --prompt option.
"""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from smartbackup.cli import app

runner = CliRunner()


class TestDaemonCLI:
    """Tests for daemon subcommands."""

    def test_watch_command_invokes_device_watcher(self):
        """Ensure 'smartbackup watch' starts DeviceWatcher loop."""
        with patch("smartbackup.platform.watcher.DeviceWatcher.start") as mock_start:
            result = runner.invoke(app, ["watch", "--interval", "1.0", "--cooldown", "60"])
            assert result.exit_code == 0
            mock_start.assert_called_once()

    def test_watch_command_keyboard_interrupt(self):
        """Ensure 'smartbackup watch' handles KeyboardInterrupt cleanly."""
        with patch("smartbackup.platform.watcher.DeviceWatcher.start", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["watch"])
            assert result.exit_code == 0
            assert "Watcher stopped by user" in result.output

    def test_daemon_install_command_success(self):
        """Ensure 'smartbackup daemon install' registers the service and reports success."""
        with patch(
            "smartbackup.platform.scheduler.SchedulerHelper.install_daemon_service",
            return_value=(True, "Service installed successfully"),
        ) as mock_install:
            result = runner.invoke(app, ["daemon", "install"])
            assert result.exit_code == 0
            assert "Service installed successfully" in result.output
            mock_install.assert_called_once()

    def test_daemon_install_command_failure(self):
        """Ensure 'smartbackup daemon install' handles failures."""
        with patch(
            "smartbackup.platform.scheduler.SchedulerHelper.install_daemon_service",
            return_value=(False, "Permission denied"),
        ) as mock_install:
            result = runner.invoke(app, ["daemon", "install"])
            assert result.exit_code == 1
            assert "Permission denied" in result.output
            mock_install.assert_called_once()

    def test_daemon_uninstall_command_success(self):
        """Ensure 'smartbackup daemon uninstall' removes the service."""
        with patch(
            "smartbackup.platform.scheduler.SchedulerHelper.uninstall_daemon_service",
            return_value=(True, "Service removed"),
        ) as mock_uninstall:
            result = runner.invoke(app, ["daemon", "uninstall"])
            assert result.exit_code == 0
            assert "Service removed" in result.output
            mock_uninstall.assert_called_once()

    def test_daemon_uninstall_command_failure(self):
        """Ensure 'smartbackup daemon uninstall' handles failure."""
        with patch(
            "smartbackup.platform.scheduler.SchedulerHelper.uninstall_daemon_service",
            return_value=(False, "Removal error"),
        ) as mock_uninstall:
            result = runner.invoke(app, ["daemon", "uninstall"])
            assert result.exit_code == 1
            assert "Removal error" in result.output
            mock_uninstall.assert_called_once()

    def test_daemon_status_command(self):
        """Ensure 'smartbackup daemon status' outputs status table."""
        status_info = {
            "installed": True,
            "running": True,
            "pid": 54321,
            "service_path": "/Library/LaunchAgents/com.smartbackup.watcher.plist",
            "details": "Running",
        }
        with patch(
            "smartbackup.platform.scheduler.SchedulerHelper.get_daemon_status",
            return_value=status_info,
        ):
            result = runner.invoke(app, ["daemon", "status"])
            assert result.exit_code == 0
            assert "DAEMON SERVICE STATUS" in result.output
            assert "54321" in result.output


class TestInteractivePromptCLI:
    """Tests for --prompt interactive mode."""

    def test_prompt_user_cancels(self, tmp_path: Path):
        """User responds 'n' to prompt -> exits 0 without backup."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", return_value="n"), \
             patch("smartbackup.backup.SmartBackup.run") as mock_run:

            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 0
            assert "Backup skipped" in result.output
            mock_run.assert_not_called()

    def test_prompt_user_accepts(self, tmp_path: Path):
        """User responds 'y' to prompt -> runs backup and pauses."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", return_value="y"), \
             patch("smartbackup.backup.SmartBackup.run", return_value=True) as mock_run, \
             patch("time.sleep") as mock_sleep:

            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["dry_run"] is False
            # Check 5 second pause was called
            mock_sleep.assert_called_with(5)

    def test_prompt_user_dry_run(self, tmp_path: Path):
        """User responds 'd' to prompt -> runs dry-run simulation."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", return_value="d"), \
             patch("smartbackup.backup.SmartBackup.run", return_value=True) as mock_run, \
             patch("time.sleep"):

            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            assert mock_run.call_args[1]["dry_run"] is True

    def test_prompt_user_keyboard_interrupt(self, tmp_path: Path):
        """User hits Ctrl+C during prompt -> exits cleanly with code 0."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 0
            assert "Backup cancelled by user" in result.output

    def test_prompt_invalid_choice_falls_back_to_backup(self, tmp_path: Path):
        """User enters unrecognized choice -> displays warning and proceeds with backup."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", return_value="foobar"), \
             patch("smartbackup.backup.SmartBackup.run", return_value=True) as mock_run, \
             patch("time.sleep"):

            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 0
            assert "Unrecognized option 'foobar'" in result.output
            mock_run.assert_called_once()

    def test_prompt_no_drive_found_exits_1(self):
        """When prompt mode cannot find any drive -> exits code 1."""
        with patch("smartbackup.platform.devices.DeviceDetector.find_backup_device", return_value=None), \
             patch("time.sleep"):

            result = runner.invoke(app, ["--prompt"])
            assert result.exit_code == 1
            assert "No backup medium found" in result.output

    def test_prompt_drive_disconnected_mid_backup(self, tmp_path: Path):
        """Simulate drive disconnection mid-backup raising FileNotFoundError -> handles cleanly."""
        drive = tmp_path / "backup_drive"
        drive.mkdir()

        with patch("rich.prompt.Prompt.ask", return_value="y"), \
             patch("smartbackup.backup.SmartBackup.run", side_effect=FileNotFoundError("Drive disconnected")), \
             patch("time.sleep"):

            result = runner.invoke(app, ["--target", str(drive), "--prompt"])
            assert result.exit_code == 1
            assert "Storage medium error" in result.output
