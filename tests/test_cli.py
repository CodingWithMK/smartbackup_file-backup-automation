"""
Tests for the CLI module.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from smartbackup.cli import main, _list_available_drives, __version__


class TestCLIVersion:
    """Tests for CLI version."""

    def test_version_is_0_2_1(self):
        """Version should be 0.2.1."""
        assert __version__ == "0.2.1"


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
        """--version should exit with SystemExit."""
        with patch.object(sys, "argv", ["smartbackup", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse exits with 0 for --version
            assert exc_info.value.code == 0

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
