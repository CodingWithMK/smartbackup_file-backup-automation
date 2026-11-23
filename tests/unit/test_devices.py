"""
Unit tests for platform.devices.DeviceDetector.
"""

from pathlib import Path

import pytest

from smartbackup.platform.devices import DeviceDetector
from smartbackup.ui.logger import BackupLogger


class TestDeviceDetector:
    """Tests for DeviceDetector.validate_device() (F8)."""

    def test_validate_device_writable_dir(self, tmp_path: Path):
        detector = DeviceDetector(BackupLogger(verbose=False))
        assert detector.validate_device(tmp_path) is True
        assert not (tmp_path / ".write_test").exists()

    def test_validate_device_missing_dir(self, tmp_path: Path):
        detector = DeviceDetector(BackupLogger(verbose=False))
        assert detector.validate_device(tmp_path / "nonexistent") is False

    def test_validate_device_unwritable_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        def deny_write(self, *args, **kwargs):
            raise PermissionError("read-only")

        monkeypatch.setattr(Path, "write_text", deny_write)
        detector = DeviceDetector(BackupLogger(verbose=False))
        assert detector.validate_device(tmp_path) is False
