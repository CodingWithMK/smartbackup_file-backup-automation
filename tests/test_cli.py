"""
Tests for the CLI module.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from smartbackup.cli import main, _list_available_drives, __version__


class TestCLIVersion:
    """Tests for CLI version."""

    def test_version_is_0_6_0(self):
        """Version should be 0.6.0."""
        assert __version__ == "0.6.0"


class TestListDrives:
    """Tests for drive listing function."""

    def test_list_drives_runs_without_error(self, capsys):
        """Listing drives should not raise errors."""
        # This just tests it runs without crashing
        _list_available_drives()
        captured = capsys.readouterr()
        # Should output something (header at minimum)
        assert len(captured.out) > 0


class TestMainFunction:
    """Tests for main() function."""

    def test_main_with_list_drives(self):
        """--list-drives should return 0."""
        with patch.object(sys, "argv", ["smartbackup", "--list-drives"]):
            result = main()
            assert result == 0

    def test_main_with_version(self):
        """--version should exit with 0."""
        with patch.object(sys, "argv", ["smartbackup", "--version"]):
            result = main()
            assert result == 0

    def test_main_with_nonexistent_source(self):
        """Non-existent source should return error."""
        with patch.object(sys, "argv", ["smartbackup", "--source", "/nonexistent/path/12345"]):
            result = main()
            # Should fail because source doesn't exist
            assert result != 0

    def test_main_keyboard_interrupt(self):
        """Keyboard interrupt should return 130."""
        with patch.object(sys, "argv", ["smartbackup"]):
            with patch("smartbackup.cli.SmartBackup.run", side_effect=KeyboardInterrupt):
                result = main()
                assert result == 130


class TestExcludeFlag:
    """Tests for --exclude persistence and immediate application (Phase 0 / F2)."""

    def test_exclude_flag_persists_and_passes_merged_exclusions(
        self, tmp_path: Path, monkeypatch
    ):
        """--exclude must save to config AND reach the current run's scan."""
        from smartbackup.config import ConfigManager

        # Isolate the config file from the developer's real config
        monkeypatch.setattr(
            ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg"
        )

        argv = ["smartbackup", "--exclude", "*.iso", "--target", str(tmp_path)]
        with patch.object(sys, "argv", argv):
            with patch(
                "smartbackup.cli.SmartBackup.run", return_value=True
            ) as mock_run:
                result = main()

        assert result == 0

        # 1. Pattern persisted to config.json
        config_file = tmp_path / "cfg" / "config.json"
        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

        # 2. Pattern passed to the run, merged with built-in defaults
        exclusions = mock_run.call_args[1]["exclusions"]
        assert "*.iso" in exclusions
        assert "node_modules" in exclusions
        assert "__pycache__" in exclusions

    def test_run_receives_persisted_exclusions_without_exclude_flag(
        self, tmp_path: Path, monkeypatch
    ):
        """Patterns saved by earlier runs are applied on later runs too."""
        from smartbackup.config import ConfigManager

        monkeypatch.setattr(
            ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg"
        )
        manager = ConfigManager()
        manager.add_exclusion("LargeDatasets")

        argv = ["smartbackup", "--target", str(tmp_path)]
        with patch.object(sys, "argv", argv):
            with patch(
                "smartbackup.cli.SmartBackup.run", return_value=True
            ) as mock_run:
                result = main()

        assert result == 0
        exclusions = mock_run.call_args[1]["exclusions"]
        assert "LargeDatasets" in exclusions
