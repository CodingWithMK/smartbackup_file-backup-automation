"""
Unit tests for the config module.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smartbackup.config import (
    DEFAULT_EXCLUSIONS,
    EXCLUDED_EXTENSIONS,
    BackupConfig,
    ConfigManager,
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

    def test_default_config(self, tmp_path: Path):
        """Default config should have sensible defaults."""
        config = BackupConfig(source_path=tmp_path, backup_path=tmp_path)

        assert config.backup_folder_name == "Documents-Backup"
        assert config.device_name == ""
        assert config.max_workers >= 1
        assert config.use_hash_verification is False
        assert config.log_to_file is True
        assert config.verbose is True

    def test_custom_device_name(self, tmp_path: Path):
        """Custom device_name should be accepted."""
        config = BackupConfig(
            source_path=tmp_path,
            backup_path=tmp_path,
            device_name="Work-Laptop",
        )
        assert config.device_name == "Work-Laptop"

    def test_exclusions_are_copied(self, tmp_path: Path):
        """Default exclusions should be a copy, not the original set."""
        config = BackupConfig(source_path=tmp_path, backup_path=tmp_path)
        config.exclusions.add("test_exclusion")
        assert "test_exclusion" not in DEFAULT_EXCLUSIONS

    def test_custom_exclusions(self, tmp_path: Path):
        """Custom exclusions should be accepted."""
        custom = {"my_folder", "other_folder"}
        config = BackupConfig(
            source_path=tmp_path,
            backup_path=tmp_path,
            exclusions=custom,
        )

        assert "my_folder" in config.exclusions
        assert "other_folder" in config.exclusions
        assert "node_modules" not in config.exclusions

    def test_custom_workers(self, tmp_path: Path):
        """Custom worker count should be accepted."""
        config = BackupConfig(
            source_path=tmp_path,
            backup_path=tmp_path,
            max_workers=8,
        )
        assert config.max_workers == 8


class TestConfigManager:
    """Tests for ConfigManager class (isolated into tmp_path via conftest)."""

    def test_config_manager_creation(self):
        """ConfigManager should be creatable."""
        manager = ConfigManager()
        assert manager is not None
        assert manager.config_dir is not None
        assert manager.config_file is not None

    def test_load_empty_config(self):
        """Loading non-existent config should return empty dict."""
        manager = ConfigManager()
        assert manager.load() == {}

    def test_save_and_load_config(self):
        """Config should be saveable and loadable."""
        manager = ConfigManager()
        manager.save({"key": "value", "number": 42})

        loaded = manager.load()
        assert loaded["key"] == "value"
        assert loaded["number"] == 42

    def test_add_exclusion(self):
        """Exclusions should be addable."""
        manager = ConfigManager()
        manager.add_exclusion("my_pattern")

        config = manager.load()
        assert "my_pattern" in config.get("exclusions", [])

    def test_get_exclusions_includes_defaults(self):
        """get_exclusions should include default exclusions."""
        manager = ConfigManager()
        exclusions = manager.get_exclusions()
        assert "node_modules" in exclusions
        assert "__pycache__" in exclusions

    def test_get_exclusions_merges_custom_patterns(self):
        """get_exclusions should union persisted custom patterns with the defaults."""
        manager = ConfigManager()
        manager.add_exclusion("LargeDatasets")

        exclusions = manager.get_exclusions()
        assert "LargeDatasets" in exclusions
        assert "node_modules" in exclusions

    def test_set_and_get_preferred_target(self):
        """Preferred target should be saveable and loadable."""
        manager = ConfigManager()
        manager.set_preferred_target("MY_DRIVE")
        assert manager.get_preferred_target() == "MY_DRIVE"

    def test_get_preferred_target_none_by_default(self):
        """Preferred target should be None by default."""
        manager = ConfigManager()
        assert manager.get_preferred_target() is None

    def test_set_and_get_device_name(self):
        """Device name should be saveable and loadable."""
        manager = ConfigManager()
        manager.set_device_name("My-MacBook")
        assert manager.get_device_name() == "My-MacBook"

    def test_get_device_name_none_by_default(self):
        """Device name should be None by default."""
        manager = ConfigManager()
        assert manager.get_device_name() is None

    def test_set_and_get_auto_watch_cooldown(self):
        """Auto watch cooldown should be saveable and loadable."""
        manager = ConfigManager()
        manager.set_auto_watch_cooldown(120)
        assert manager.get_auto_watch_cooldown() == 120

    def test_get_auto_watch_cooldown_default_300(self):
        """Auto watch cooldown should default to 300."""
        manager = ConfigManager()
        assert manager.get_auto_watch_cooldown() == 300

    def test_set_and_get_preferred_terminal(self):
        """Preferred terminal should be saveable and loadable."""
        manager = ConfigManager()
        manager.set_preferred_terminal("iTerm2")
        assert manager.get_preferred_terminal() == "iTerm2"


class TestConfigManagerHardening:
    """Q3 regression tests: corrupt config warnings, backup preservation, and atomic saves."""

    def test_load_missing_config_emits_no_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_logger = MagicMock()
        manager = ConfigManager(logger=mock_logger)

        assert manager.load() == {}
        assert capsys.readouterr().err == ""
        mock_logger.warning.assert_not_called()

    def test_load_corrupt_json_emits_warning_to_stderr_and_returns_empty_dict(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        manager = ConfigManager()
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_text("{invalid-json", encoding="utf-8")

        assert manager.load() == {}
        err = capsys.readouterr().err
        assert "Failed to load configuration" in err
        assert str(manager.config_file) in err

    def test_load_corrupt_json_routes_warning_via_injected_logger(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_logger = MagicMock()
        manager = ConfigManager(logger=mock_logger)
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_text("{broken", encoding="utf-8")

        assert manager.load() == {}
        assert capsys.readouterr().err == ""
        mock_logger.warning.assert_called_once()
        assert "Failed to load configuration" in mock_logger.warning.call_args[0][0]

    @pytest.mark.parametrize("raw_bytes", [b"[]", b"42", b"null", b"\xff\xfe\x00\x01"])
    def test_load_non_dict_json_and_binary_garbage_warns_and_returns_empty(
        self, raw_bytes: bytes
    ) -> None:
        mock_logger = MagicMock()
        manager = ConfigManager(logger=mock_logger)
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_bytes(raw_bytes)

        assert manager.load() == {}
        mock_logger.warning.assert_called_once()

    def test_save_backs_up_corrupt_config_before_overwriting(self) -> None:
        mock_logger = MagicMock()
        manager = ConfigManager(logger=mock_logger)
        manager.config_dir.mkdir(parents=True, exist_ok=True)
        original_corrupt = "{broken: true, preferred_target: MY_USB"
        manager.config_file.write_text(original_corrupt, encoding="utf-8")

        manager.save({"manifest_format": "sqlite"})

        # Original corrupt content preserved in .corrupt.* sibling
        backups = list(manager.config_dir.glob("config.json.corrupt.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == original_corrupt

        # New valid config written atomically
        assert json.loads(manager.config_file.read_text(encoding="utf-8")) == {
            "manifest_format": "sqlite"
        }
        assert not list(manager.config_dir.glob("config.*.tmp"))
        assert any("Preserved corrupt configuration" in c[0][0] for c in mock_logger.warning.call_args_list)

    def test_save_multiple_corrupt_backups_in_same_second_do_not_collide(self) -> None:
        manager = ConfigManager(logger=MagicMock())
        manager.config_dir.mkdir(parents=True, exist_ok=True)

        manager.config_file.write_text("{corrupt-1", encoding="utf-8")
        manager.save({"k": 1})

        manager.config_file.write_text("{corrupt-2", encoding="utf-8")
        manager.save({"k": 2})

        backups = sorted(manager.config_dir.glob("config.json.corrupt.*"))
        assert len(backups) == 2
        contents = {b.read_text(encoding="utf-8") for b in backups}
        assert contents == {"{corrupt-1", "{corrupt-2"}

    def test_save_over_valid_config_does_not_create_corrupt_backup(self) -> None:
        """Control: normal updates must not produce .corrupt.* files."""
        manager = ConfigManager(logger=MagicMock())
        manager.save({"preferred_target": "DISK_A"})
        manager.save({"preferred_target": "DISK_B"})

        assert list(manager.config_dir.glob("config.json.corrupt.*")) == []
        assert manager.load() == {"preferred_target": "DISK_B"}

    def test_save_atomic_preserves_existing_valid_config_and_cleans_tmp_on_failure(self) -> None:
        """Fragility guard: failed json.dump must leave old config intact and remove .tmp."""
        manager = ConfigManager(logger=MagicMock())
        manager.save({"preferred_target": "SAFE_DRIVE"})

        with patch("smartbackup.config.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                manager.save({"preferred_target": "BROKEN"})

        assert manager.load() == {"preferred_target": "SAFE_DRIVE"}
        assert list(manager.config_dir.glob("config.*.tmp")) == []

    def test_exclusions_helpers_handle_non_list_corrupt_field(self) -> None:
        """Fragility guard: string/null exclusions value must not split into single chars."""
        manager = ConfigManager(logger=MagicMock())
        manager.save({"exclusions": "*.iso"})

        exclusions = manager.get_exclusions()
        assert "*" not in exclusions
        assert "i" not in exclusions

        manager.add_exclusion("*.dmg")
        assert manager.load()["exclusions"] == ["*.dmg"]
