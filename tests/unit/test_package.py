"""
Unit tests for package metadata, public exports, SmartBackup init, and CLI command surface.
"""

import typer.main

from smartbackup import (
    BackupConfig,
    BackupEngine,
    BackupLogger,
    BackupResult,
    ChangeDetector,
    ConfigManager,
    DebounceLock,
    DeviceDetector,
    DeviceWatcher,
    DriveMatcher,
    ExclusionFilter,
    FallbackHandler,
    FileScanner,
    PathResolver,
    SmartBackup,
    TerminalSpawner,
    __version__,
)
from smartbackup.cli import __version__ as cli_version
from smartbackup.cli import app


class TestVersion:
    """Test version information."""

    def test_version_exists_and_matches_cli(self):
        """Package and CLI versions should be defined, semver-formatted, and consistent."""
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__.split(".")) >= 2
        assert __version__ == "0.8.0"
        assert cli_version == __version__


class TestImports:
    """Test that all public exports are importable."""

    def test_public_exports_importable(self):
        """All documented package exports should be importable."""
        exports = [
            SmartBackup,
            BackupConfig,
            BackupResult,
            PathResolver,
            BackupLogger,
            FileScanner,
            ExclusionFilter,
            ChangeDetector,
            BackupEngine,
            DeviceDetector,
            ConfigManager,
            FallbackHandler,
            DriveMatcher,
            DebounceLock,
            DeviceWatcher,
            TerminalSpawner,
        ]
        assert all(obj is not None for obj in exports)


class TestSmartBackup:
    """Unit tests for SmartBackup main class initialization."""

    def test_instance_creation(self):
        """SmartBackup instance should be created with a logger."""
        backup = SmartBackup()
        assert backup is not None
        assert backup.logger is not None


class TestCompressCLISurface:
    """Unit inspection tests for the compress CLI subcommand registration."""

    def test_compress_subcommand_exists(self):
        """The 'compress' subcommand is registered in the Typer app."""
        command_names = []
        if hasattr(app, "registered_commands"):
            for cmd in app.registered_commands:
                if hasattr(cmd, "name") and cmd.name:
                    command_names.append(cmd.name)

        click_app = typer.main.get_command(app)
        if hasattr(click_app, "commands"):
            command_names.extend(click_app.commands.keys())

        assert "compress" in command_names

    def test_compress_subcommand_help(self):
        """The compress subcommand has appropriate help text."""
        click_app = typer.main.get_command(app)
        compress_cmd = click_app.commands.get("compress")
        assert compress_cmd is not None
        assert "compress" in compress_cmd.help.lower() or "archive" in compress_cmd.help.lower()
