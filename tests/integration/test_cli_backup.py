"""
Integration tests for primary CLI flags and commands (main, --list-drives,
--exclude, --notify, --manifest-format, --show-manifest, --verify, schedule).
"""

import builtins
import json
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from smartbackup.cli import _list_available_drives, app, main
from smartbackup.config import ConfigManager
from smartbackup.models import SelectionMetadata
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


class TestSelectCLIFlag:
    """Integration tests for --select CLI flag, TTY guard, cancellation, and --show-manifest."""

    def test_select_fails_fast_in_non_tty_environment(self, tmp_path: Path):
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "Projects").mkdir()

        with patch("smartbackup.cli._is_interactive_tty", return_value=False):
            res = runner.invoke(
                app, ["--select", "--source", str(src), "--target", str(tgt)]
            )

        assert res.exit_code == 1
        assert "TTY" in res.output or "interactive terminal" in res.output

    def test_select_cancelled_exits_0_without_running_backup(self, tmp_path: Path):
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "Projects").mkdir()

        with (
            patch("smartbackup.cli._is_interactive_tty", return_value=True),
            patch("smartbackup.cli.FolderSelector.select", return_value=None),
            patch("smartbackup.cli.SmartBackup.run") as mock_run,
        ):
            res = runner.invoke(
                app, ["--select", "--source", str(src), "--target", str(tgt)]
            )

        assert res.exit_code == 0, res.output
        mock_run.assert_not_called()

    def test_select_forwards_selected_folders_and_metadata_to_smartbackup(
        self, tmp_path: Path
    ):
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "Projects").mkdir()
        (src / "Finance").mkdir()

        meta = SelectionMetadata(
            command_option="--select",
            source_root=str(src),
            available_folders=["Finance", "Projects"],
            selected_folders=["Projects"],
            excluded_folders_count=0,
            workflow_steps=["CLI invoked with --select"],
        )

        with (
            patch("smartbackup.cli._is_interactive_tty", return_value=True),
            patch("smartbackup.cli.FolderSelector.select", return_value=meta),
            patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run,
        ):
            res = runner.invoke(
                app, ["--select", "--source", str(src), "--target", str(tgt)]
            )

        assert res.exit_code == 0, res.output
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["selected_folders"] == ["Projects"]
        assert mock_run.call_args.kwargs["selection_metadata"] is meta

    def test_show_manifest_displays_selective_history_for_json_and_sqlite(
        self, tmp_path: Path
    ):
        for fmt in ("json", "sqlite"):
            src = tmp_path / f"src_{fmt}"
            tgt = tmp_path / f"tgt_{fmt}"
            (src / "Projects").mkdir(parents=True)
            (src / "Projects" / "code.py").write_text("print('ok')")
            tgt.mkdir()

            meta = SelectionMetadata(
                command_option="--select",
                source_root=str(src),
                available_folders=["Projects"],
                selected_folders=["Projects"],
                workflow_steps=["CLI invoked with --select"],
            )

            with (
                patch("smartbackup.cli._is_interactive_tty", return_value=True),
                patch("smartbackup.cli.FolderSelector.select", return_value=meta),
            ):
                run_res = runner.invoke(
                    app,
                    [
                        "--select",
                        "--source",
                        str(src),
                        "--target",
                        str(tgt),
                        "--device-name",
                        f"Dev_{fmt}",
                        "--manifest-format",
                        fmt,
                    ],
                )
            assert run_res.exit_code == 0, run_res.output

            show_res = runner.invoke(
                app,
                ["--show-manifest", "--target", str(tgt), "--device-name", f"Dev_{fmt}"],
            )
            assert show_res.exit_code == 0, show_res.output
            assert "Selective (--select)" in show_res.output
            assert "Selective Backup History (--select)" in show_res.output
            assert "Projects" in show_res.output


class TestQualityHardeningCLI:
    """Integration tests for Q1 (--verify unreadable), Q2 (regex metacharacters), Q6 (manifest logging)."""

    def test_cli_verify_exits_1_when_backup_file_unreadable_during_hashing(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "secret.txt").write_text("integrity-checked")

        # 1. Perform real hashed backup
        res = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(tgt),
                "--device-name",
                "VerifyBox",
                "--hash",
            ],
        )
        assert res.exit_code == 0, res.output
        backed_up = tgt / "Documents-Backup" / "VerifyBox" / "secret.txt"
        assert backed_up.exists()

        # 2. Control: readable --verify exits 0
        ok_verify = runner.invoke(
            app, ["--verify", "--target", str(tgt), "--device-name", "VerifyBox"]
        )
        assert ok_verify.exit_code == 0, ok_verify.output

        # 3. Unreadable during hashing while stat() succeeds -> must exit 1!
        real_open = builtins.open

        def fail_backed_up(file, *args, **kwargs):
            if Path(file) == backed_up:
                raise PermissionError("simulated unreadable sector")
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_backed_up):
            bad_verify = runner.invoke(
                app, ["--verify", "--target", str(tgt), "--device-name", "VerifyBox"]
            )

        assert bad_verify.exit_code == 1
        assert "Error hashing" in bad_verify.output

    def test_cli_exclude_with_regex_metacharacters_works_and_persists(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "keep.txt").write_text("keep")
        (src / "Backup (1) copy.zip").write_bytes(b"skip-me")
        (src / "C++_notes.md").write_text("skip-cpp")
        (src / "draft[1_old.txt").write_text("skip-unclosed")
        (src / "img_3.png").write_bytes(b"skip-digit")

        res = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(tgt),
                "--device-name",
                "MetaBox",
                "--exclude",
                "Backup (1)*",
                "--exclude",
                "C++*",
                "--exclude",
                "draft[1*",
                "--exclude",
                "img_[0-9]*.png",
            ],
        )
        assert res.exit_code == 0, res.output
        out_dir = tgt / "Documents-Backup" / "MetaBox"
        assert (out_dir / "keep.txt").exists()
        assert not (out_dir / "Backup (1) copy.zip").exists()
        assert not (out_dir / "C++_notes.md").exists()
        assert not (out_dir / "draft[1_old.txt").exists()
        assert not (out_dir / "img_3.png").exists()

        # Subsequent run using persisted metacharacter patterns also succeeds cleanly
        res2 = runner.invoke(
            app,
            ["--source", str(src), "--target", str(tgt), "--device-name", "MetaBox"],
        )
        assert res2.exit_code == 0, res2.output

    def test_cli_corrupt_manifest_warning_routed_via_logger_not_raw_stderr(
        self, tmp_path: Path, capsys
    ) -> None:
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        (src / "doc.txt").write_text("hello")
        dev_dir = tgt / "Documents-Backup" / "LogBox"
        dev_dir.mkdir(parents=True)
        (dev_dir / ".smartbackup_manifest.json").write_text("{corrupt", encoding="utf-8")

        res = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(tgt),
                "--device-name",
                "LogBox",
                "--quiet",
            ],
        )
        assert res.exit_code == 0, res.output
        assert capsys.readouterr().err == ""
        assert "Failed to load manifest" in res.output
        assert (dev_dir / "doc.txt").exists()
