"""
Basic tests for SmartBackup.

Run with: pytest
"""

import tempfile
from pathlib import Path

import pytest

from smartbackup import (
    SmartBackup,
    BackupConfig,
    BackupResult,
    PathResolver,
    BackupLogger,
)
from smartbackup import __version__


class TestVersion:
    """Test version information."""
    
    def test_version_exists(self):
        """Version should be defined."""
        assert __version__ is not None
        assert isinstance(__version__, str)
    
    def test_version_format(self):
        """Version should follow semver format."""
        parts = __version__.split(".")
        assert len(parts) >= 2


class TestPathResolver:
    """Tests for PathResolver class."""
    
    def test_get_documents_path_returns_path(self):
        """Documents path should return a Path object."""
        docs = PathResolver.get_documents_path()
        assert isinstance(docs, Path)
    
    def test_get_documents_path_is_absolute(self):
        """Documents path should be absolute."""
        docs = PathResolver.get_documents_path()
        assert docs.is_absolute()
    
    def test_find_external_drives_returns_list(self):
        """External drives should return a list."""
        drives = PathResolver.find_external_drives()
        assert isinstance(drives, list)


class TestBackupConfig:
    """Tests for BackupConfig class."""
    
    def test_default_config(self):
        """Default config should have sensible defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir)
            )
            assert config.backup_folder_name == "Documents-Backup"
            assert config.max_workers >= 1
            assert "node_modules" in config.exclusions
            assert "__pycache__" in config.exclusions
    
    def test_custom_exclusions(self):
        """Custom exclusions should be accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom = {"my_folder", "other_folder"}
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir),
                exclusions=custom
            )
            assert "my_folder" in config.exclusions


class TestBackupResult:
    """Tests for BackupResult class."""
    
    def test_default_result(self):
        """Default result should have zero counts."""
        result = BackupResult()
        assert result.copied_files == 0
        assert result.updated_files == 0
        assert result.errors == 0
    
    def test_duration_calculation(self):
        """Duration should be calculable."""
        result = BackupResult()
        assert result.duration >= 0


class TestSmartBackup:
    """Tests for SmartBackup main class."""
    
    def test_instance_creation(self):
        """SmartBackup instance should be created."""
        backup = SmartBackup()
        assert backup is not None
        assert backup.logger is not None


class TestExclusionDefaults:
    """Tests for default exclusion patterns."""
    
    def test_node_modules_excluded(self):
        """node_modules should be in default exclusions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir)
            )
            assert "node_modules" in config.exclusions
    
    def test_venv_excluded(self):
        """Virtual environments should be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir)
            )
            assert "venv" in config.exclusions
            assert ".venv" in config.exclusions
    
    def test_pycache_excluded(self):
        """__pycache__ should be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir)
            )
            assert "__pycache__" in config.exclusions
    
    def test_git_excluded(self):
        """.git should be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(
                source_path=Path(tmpdir),
                backup_path=Path(tmpdir)
            )
            assert ".git" in config.exclusions


class TestBackupLogger:
    """Tests for BackupLogger class."""
    
    def test_logger_creation(self):
        """Logger should be creatable."""
        logger = BackupLogger(verbose=True)
        assert logger is not None
    
    def test_format_size(self):
        """Size formatting should work."""
        logger = BackupLogger()
        assert "KB" in logger._format_size(1024)
        assert "MB" in logger._format_size(1024 * 1024)
        assert "GB" in logger._format_size(1024 * 1024 * 1024)