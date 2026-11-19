"""
CLI front door for the persistent config (F4).

`ConfigManager` has carried setters for `preferred_target`, `device_name`,
`auto_watch_cooldown` and `preferred_terminal` since before 0.7, but nothing in
production called them — users had to hand-edit `config.json`. These tests
drive the new `smartbackup config` group end to end with the config directory
redirected into pytest's tmp_path, so the developer's real config is never
read or written.

Covered:
  * list / get / set / unset roundtrip for every supported key
  * device-name sanitization and cooldown validation
  * unknown keys and the `exclusions` pseudo-key are rejected with exit 1
  * exclude / unexclude wrap ConfigManager.add_exclusion/remove_exclusion
  * invalid input never mutates the config file (control)
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smartbackup.cli import app
from smartbackup.config import ConfigManager

runner = CliRunner()


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch) -> Path:
    """Redirect every ConfigManager instance into tmp_path."""
    directory = tmp_path / "cfg"
    monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: directory)
    return directory


def _invoke(*args: str):
    return runner.invoke(app, ["config", *args])


def _stored(config_dir: Path) -> dict:
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text(encoding="utf-8"))


class TestConfigListAndGet:
    def test_list_shows_all_supported_keys(self, config_dir: Path):
        result = _invoke("list")

        assert result.exit_code == 0, result.output
        for key in (
            "preferred_target",
            "device_name",
            "auto_watch_cooldown",
            "preferred_terminal",
            "exclusions",
        ):
            assert key in result.output
        assert "Config file:" in result.output
        assert "config.json" in result.output

    def test_get_unset_key_reports_not_set(self, config_dir: Path):
        result = _invoke("get", "preferred_target")

        assert result.exit_code == 0, result.output
        assert "(not set)" in result.output

    def test_get_unknown_key_exits_1(self, config_dir: Path):
        result = _invoke("get", "bogus")

        assert result.exit_code == 1
        assert "Unknown config key" in result.output
        for key in ("preferred_target", "device_name", "auto_watch_cooldown"):
            assert key in result.output


class TestConfigSetAndUnset:
    def test_set_get_unset_roundtrip(self, config_dir: Path):
        set_result = _invoke("set", "auto_watch_cooldown", "42")
        assert set_result.exit_code == 0, set_result.output
        assert _stored(config_dir)["auto_watch_cooldown"] == 42

        get_result = _invoke("get", "auto_watch_cooldown")
        assert get_result.exit_code == 0
        assert "42" in get_result.output

        unset_result = _invoke("unset", "auto_watch_cooldown")
        assert unset_result.exit_code == 0, unset_result.output
        assert "auto_watch_cooldown" not in _stored(config_dir)

        assert "(not set)" in _invoke("get", "auto_watch_cooldown").output

    def test_set_device_name_is_sanitized(self, config_dir: Path):
        result = _invoke("set", "device_name", "My Laptop!!")

        assert result.exit_code == 0, result.output
        assert _stored(config_dir)["device_name"] == "My-Laptop"

    def test_set_preferred_terminal_and_target(self, config_dir: Path):
        assert _invoke("set", "preferred_terminal", "iterm").exit_code == 0
        assert _invoke("set", "preferred_target", "MY_DISK").exit_code == 0

        stored = _stored(config_dir)
        assert stored["preferred_terminal"] == "iterm"
        assert stored["preferred_target"] == "MY_DISK"

    def test_invalid_cooldown_exits_1_and_does_not_write(self, config_dir: Path):
        assert _invoke("set", "auto_watch_cooldown", "30").exit_code == 0
        before = (config_dir / "config.json").read_bytes()

        result = _invoke("set", "auto_watch_cooldown", "not-a-number")

        assert result.exit_code == 1
        assert "Invalid value" in result.output
        assert (config_dir / "config.json").read_bytes() == before

    def test_unknown_key_exits_1_and_does_not_write(self, config_dir: Path):
        result = _invoke("set", "bogus", "value")

        assert result.exit_code == 1
        assert "Unknown config key" in result.output
        assert not (config_dir / "config.json").exists()

    def test_exclusions_pseudo_key_is_rejected(self, config_dir: Path):
        result = _invoke("set", "exclusions", "*.iso")

        assert result.exit_code == 1
        assert "exclude" in result.output
        assert not (config_dir / "config.json").exists()


class TestConfigExclusions:
    def test_exclude_then_unexclude_roundtrip(self, config_dir: Path):
        assert _invoke("exclude", "*.iso", "*.dmg").exit_code == 0
        stored = set(_stored(config_dir)["exclusions"])
        assert stored == {"*.iso", "*.dmg"}

        assert _invoke("unexclude", "*.iso").exit_code == 0
        stored = set(_stored(config_dir)["exclusions"])
        assert stored == {"*.dmg"}

    def test_unexclude_unknown_pattern_is_harmless(self, config_dir: Path):
        assert _invoke("exclude", "*.iso").exit_code == 0

        result = _invoke("unexclude", "*.never-added")

        assert result.exit_code == 0, result.output
        assert set(_stored(config_dir)["exclusions"]) == {"*.iso"}

    def test_get_exclusions_prints_patterns(self, config_dir: Path):
        _invoke("exclude", "*.iso")

        result = _invoke("get", "exclusions")

        assert result.exit_code == 0
        assert "*.iso" in result.output
