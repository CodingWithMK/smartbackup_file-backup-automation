"""
Tests for the config module.
"""

import tempfile
from pathlib import Path

import pytest

from smartbackup.config import (
    BackupConfig,
    ConfigManager,
    DEFAULT_EXCLUSIONS,
    EXCLUDED_EXTENSIONS,
)


class TestDefaultExclusions:
    """Tests for default exclusion patterns."""

    def test_node_modules_in_defaults(self):
        """node_modules should be in default exclusions."""
        assert "node_modules" in DEFAULT_EXCLUSIONS

    def test_pycache_in_defaults(self):
        """__pycache__ should be in default exclusions."""
        assert "__pycache__" in DEFAULT_EXCLUSIONS

    def test_venv_in_defaults(self):
        """Virtual environment directories should be excluded."""
        assert "venv" in DEFAULT_EXCLUSIONS
        assert ".venv" in DEFAULT_EXCLUSIONS

    def test_git_in_defaults(self):
        """.git should be in default exclusions."""
        assert ".git" in DEFAULT_EXCLUSIONS

    def test_ide_directories_in_defaults(self):
        """IDE directories should be excluded."""
        assert ".idea" in DEFAULT_EXCLUSIONS
        assert ".vscode" in DEFAULT_EXCLUSIONS


class TestExcludedExtensions:
    """Tests for excluded file extensions."""

    def test_python_compiled_excluded(self):
        """Python compiled files should be excluded."""
        assert ".pyc" in EXCLUDED_EXTENSIONS
        assert ".pyo" in EXCLUDED_EXTENSIONS

    def test_temp_files_excluded(self):
        """Temporary files should be excluded."""
        assert ".tmp" in EXCLUDED_EXTENSIONS
        assert ".log" in EXCLUDED_EXTENSIONS


class TestBackupConfig:
    """Tests for BackupConfig dataclass."""

    def test_default_config(self, temp_dir: Path):
        """Default config should have sensible defaults."""
        config = BackupConfig(source_path=temp_dir, backup_path=temp_dir)

        assert config.backup_folder_name == "Documents-Backup"
        assert config.device_name == ""
        assert config.max_workers >= 1
        assert config.use_hash_verification is False
        assert config.log_to_file is True
        assert config.verbose is True

    def test_custom_device_name(self, temp_dir: Path):
        """Custom device_name should be accepted."""
        config = BackupConfig(
            source_path=temp_dir,
            backup_path=temp_dir,
            device_name="Work-Laptop",
        )
        assert config.device_name == "Work-Laptop"

    def test_exclusions_are_copied(self, temp_dir: Path):
        """Default exclusions should be a copy, not the original set."""
        config = BackupConfig(source_path=temp_dir, backup_path=temp_dir)

        # Modify config exclusions
        config.exclusions.add("test_exclusion")

        # Original should not be modified
        assert "test_exclusion" not in DEFAULT_EXCLUSIONS

    def test_custom_exclusions(self, temp_dir: Path):
        """Custom exclusions should be accepted."""
        custom = {"my_folder", "other_folder"}
        config = BackupConfig(
            source_path=temp_dir,
            backup_path=temp_dir,
            exclusions=custom,
        )

        assert "my_folder" in config.exclusions
        assert "other_folder" in config.exclusions
        assert "node_modules" not in config.exclusions

    def test_custom_workers(self, temp_dir: Path):
        """Custom worker count should be accepted."""
        config = BackupConfig(
            source_path=temp_dir,
            backup_path=temp_dir,
            max_workers=8,
        )

        assert config.max_workers == 8


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_config_manager_creation(self):
        """ConfigManager should be creatable."""
        manager = ConfigManager()
        assert manager is not None
        assert manager.config_dir is not None
        assert manager.config_file is not None

    def test_load_empty_config(self):
        """Loading non-existent config should return empty dict."""
        manager = ConfigManager()
        # Use a non-existent path
        manager.config_file = Path("/tmp/nonexistent_smartbackup_config.json")
        config = manager.load()
        assert config == {}

    def test_save_and_load_config(self):
        """Config should be saveable and loadable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager()
            manager.config_dir = Path(tmpdir)
            manager.config_file = Path(tmpdir) / "config.json"

            # Save config
            test_config = {"key": "value", "number": 42}
            manager.save(test_config)

            # Load config
            loaded = manager.load()
            assert loaded["key"] == "value"
            assert loaded["number"] == 42

    def test_add_exclusion(self):
        """Exclusions should be addable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager()
            manager.config_dir = Path(tmpdir)
            manager.config_file = Path(tmpdir) / "config.json"

            manager.add_exclusion("my_pattern")

            config = manager.load()
            assert "my_pattern" in config.get("exclusions", [])

    def test_get_exclusions_includes_defaults(self):
        """get_exclusions should include default exclusions."""
        manager = ConfigManager()
        manager.config_file = Path("/tmp/nonexistent_config.json")

        exclusions = manager.get_exclusions()
        assert "node_modules" in exclusions
        assert "__pycache__" in exclusions

    def test_set_and_get_preferred_target(self):
        """Preferred target should be saveable and loadable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager()
            manager.config_dir = Path(tmpdir)
            manager.config_file = Path(tmpdir) / "config.json"

            manager.set_preferred_target("MY_DRIVE")

            target = manager.get_preferred_target()
            assert target == "MY_DRIVE"

    def test_get_preferred_target_none_by_default(self):
        """Preferred target should be None by default."""
        manager = ConfigManager()
        manager.config_file = Path("/tmp/nonexistent_config.json")

        target = manager.get_preferred_target()
        assert target is None

    def test_set_and_get_device_name(self):
        """Device name should be saveable and loadable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ConfigManager()
            manager.config_dir = Path(tmpdir)
            manager.config_file = Path(tmpdir) / "config.json"

            manager.set_device_name("My-MacBook")

            name = manager.get_device_name()
            assert name == "My-MacBook"

    def test_get_device_name_none_by_default(self):
        """Device name should be None by default."""
        manager = ConfigManager()
        manager.config_file = Path("/tmp/nonexistent_config.json")

        name = manager.get_device_name()
        assert name is None
