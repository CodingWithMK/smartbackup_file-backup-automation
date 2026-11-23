"""
Integration tests for primary CLI flags and commands (main, --list-drives,
--exclude, --notify, --manifest-format, --show-manifest, --verify, schedule).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from smartbackup.cli import _list_available_drives, app, main
from smartbackup.config import ConfigManager
from smartbackup.platform.scheduler import SchedulerHelper

runner = CliRunner()


class TestListDrives:
    """Tests for drive listing function."""

    def test_list_drives_runs_without_error(self, capsys):
        _list_available_drives()
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestMainFunction:
    """Tests for main() entry-point wiring."""

    def test_main_with_list_drives(self):
        with patch.object(sys, "argv", ["smartbackup", "--list-drives"]):
            assert main() == 0

    def test_main_with_version(self):
        with patch.object(sys, "argv", ["smartbackup", "--version"]):
            assert main() == 0

    def test_main_with_nonexistent_source(self):
        with patch.object(sys, "argv", ["smartbackup", "--source", "/nonexistent/path/12345"]):
            assert main() != 0

    def test_main_keyboard_interrupt(self):
        with (
            patch.object(sys, "argv", ["smartbackup"]),
            patch("smartbackup.cli.SmartBackup.run", side_effect=KeyboardInterrupt),
        ):
            assert main() == 130


class TestExcludeFlag:
    """Tests for --exclude persistence and immediate application (Phase 0 / F2)."""

    def test_exclude_flag_persists_and_passes_merged_exclusions(
        self, isolated_config: Path, tmp_path: Path
    ):
        argv = ["smartbackup", "--exclude", "*.iso", "--target", str(tmp_path)]
        with (
            patch.object(sys, "argv", argv),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            result = main()

        assert result == 0

        config_file = isolated_config / "config.json"
        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

        exclusions = mock_run.call_args[1]["exclusions"]
        assert "*.iso" in exclusions
        assert "node_modules" in exclusions
        assert "__pycache__" in exclusions

    def test_run_receives_persisted_exclusions_without_exclude_flag(self, tmp_path: Path):
        ConfigManager().add_exclusion("LargeDatasets")

        argv = ["smartbackup", "--target", str(tmp_path)]
        with (
            patch.object(sys, "argv", argv),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            result = main()

        assert result == 0
        assert "LargeDatasets" in mock_run.call_args[1]["exclusions"]


class TestNotifyCLIFlag:
    """Tests for --notify CLI flag wiring (F10)."""

    def test_notify_flag_wired_to_smartbackup_run(self, tmp_path: Path):
        with (
            patch.object(sys, "argv", ["smartbackup", "--target", str(tmp_path)]),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            assert main() == 0
        assert mock_run.call_args.kwargs["notify"] is False

        with (
            patch.object(sys, "argv", ["smartbackup", "--target", str(tmp_path), "--notify"]),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            assert main() == 0
        assert mock_run.call_args.kwargs["notify"] is True


class TestScheduleCLI:
    """Tests for 'smartbackup schedule' CLI command."""

    def test_schedule_cli_command_default_and_custom_hours(self):
        res_default = runner.invoke(app, ["schedule"])
        assert res_default.exit_code == 0, res_default.output
        assert "-m" in res_default.output
        assert "smartbackup" in res_default.output
        assert "scheduler.py" not in res_default.output

        with patch.object(SchedulerHelper, "setup_scheduled_backup") as mock_setup:
            res_custom = runner.invoke(app, ["schedule", "--hours", "6"])
            assert res_custom.exit_code == 0, res_custom.output
            mock_setup.assert_called_once_with(interval_hours=6)


class TestSqliteManifestCLI:
    """CLI wiring tests for --manifest-format, --show-manifest, --verify, --list-devices."""

    def test_cli_sqlite_backup_inspect_verify_and_list_devices(self, tmp_path: Path):
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "app.py").write_text("print('hi')")

        res = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(tgt),
                "--device-name",
                "CliSql",
                "--manifest-format",
                "sqlite",
            ],
        )
        assert res.exit_code == 0, res.output
        assert (tgt / "Documents-Backup" / "CliSql" / ".smartbackup_manifest.db").exists()

        show = runner.invoke(
            app, ["--show-manifest", "--target", str(tgt), "--device-name", "CliSql"]
        )
        assert show.exit_code == 0, show.output
        assert "sqlite" in show.output.lower()

        verify = runner.invoke(
            app, ["--verify", "--target", str(tgt), "--device-name", "CliSql"]
        )
        assert verify.exit_code == 0, verify.output

        devices = runner.invoke(app, ["--list-devices", "--target", str(tgt)])
        assert devices.exit_code == 0, devices.output
        assert "CliSql" in devices.output

    def test_cli_invalid_manifest_format_exits_1(self, tmp_path: Path):
        res = runner.invoke(
            app, ["--target", str(tmp_path), "--manifest-format", "bogus"]
        )
        assert res.exit_code == 1
        assert "Unsupported manifest format" in res.output

    def test_cli_uses_configured_manifest_format_and_flag_overrides(self, tmp_path: Path):
        ConfigManager().set_manifest_format("sqlite")

        with (
            patch.object(sys, "argv", ["smartbackup", "--target", str(tmp_path)]),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            assert main() == 0
        assert mock_run.call_args.kwargs["manifest_format"] == "sqlite"

        with (
            patch.object(
                sys,
                "argv",
                ["smartbackup", "--target", str(tmp_path), "--manifest-format", "json"],
            ),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            assert main() == 0
        assert mock_run.call_args.kwargs["manifest_format"] == "json"
