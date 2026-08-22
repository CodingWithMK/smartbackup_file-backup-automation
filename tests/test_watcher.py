"""
Tests for DriveMatcher, DebounceLock, and DeviceWatcher.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from smartbackup.config import ConfigManager
from smartbackup.platform.watcher import (
    DebounceLock,
    DeviceWatcher,
    DriveMatcher,
)


class TestDriveMatcher:
    """Tests for DriveMatcher."""

    def test_drive_matcher_identifies_per_device_manifest(self, tmp_path: Path):
        """Ensure DriveMatcher recognizes drives with current hostname backup manifest."""
        drive = tmp_path / "usb_drive"
        manifest_dir = drive / "Documents-Backup" / "Test-Host"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / ".smartbackup_manifest.json").write_text("{}")

        with patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Host"):
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(drive) is True

    def test_drive_matcher_identifies_per_device_folder(self, tmp_path: Path):
        """Ensure DriveMatcher recognizes drives with current hostname subfolder."""
        drive = tmp_path / "usb_drive"
        device_dir = drive / "Documents-Backup" / "Test-Host"
        device_dir.mkdir(parents=True)

        with patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Host"):
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(drive) is True

    def test_drive_matcher_identifies_legacy_layout(self, tmp_path: Path):
        """Ensure DriveMatcher recognizes legacy flat Documents-Backup manifest."""
        drive = tmp_path / "legacy_drive"
        manifest_dir = drive / "Documents-Backup"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / ".smartbackup_manifest.json").write_text("{}")

        matcher = DriveMatcher()
        assert matcher.is_smartbackup_target(drive) is True

    def test_drive_matcher_matches_preferred_target_by_label(self, tmp_path: Path):
        """Ensure DriveMatcher matches drive when label equals preferred target."""
        drive = tmp_path / "MyBackupDrive"
        drive.mkdir()

        config_mgr = MagicMock(spec=ConfigManager)
        config_mgr.get_preferred_target.return_value = "MyBackupDrive"
        config_mgr.get_device_name.return_value = "Test-Host"

        matcher = DriveMatcher(config_manager=config_mgr)
        assert matcher.is_smartbackup_target(drive) is True

    def test_drive_matcher_matches_custom_device_name(self, tmp_path: Path):
        """Ensure DriveMatcher respects custom device_name configured in ConfigManager."""
        drive = tmp_path / "usb_drive"
        manifest_dir = drive / "Documents-Backup" / "Custom-Device-Name"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / ".smartbackup_manifest.json").write_text("{}")

        config_mgr = MagicMock(spec=ConfigManager)
        config_mgr.get_preferred_target.return_value = None
        config_mgr.get_device_name.return_value = "Custom-Device-Name"

        with patch("smartbackup.platform.watcher.get_device_name", return_value="Default-Host"):
            matcher = DriveMatcher(config_manager=config_mgr)
            assert matcher.is_smartbackup_target(drive) is True

    def test_drive_matcher_drive_letter_cycling(self, tmp_path: Path):
        """Ensure DriveMatcher identifies target even if Windows drive letter changes (D: -> E:)."""
        drive_d = tmp_path / "drive_D"
        (drive_d / "Documents-Backup" / "My-PC").mkdir(parents=True)
        (drive_d / "Documents-Backup" / "My-PC" / ".smartbackup_manifest.json").write_text("{}")

        drive_e = tmp_path / "drive_E"
        (drive_e / "Documents-Backup" / "My-PC").mkdir(parents=True)
        (drive_e / "Documents-Backup" / "My-PC" / ".smartbackup_manifest.json").write_text("{}")

        with patch("smartbackup.platform.watcher.get_device_name", return_value="My-PC"):
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(drive_d) is True
            assert matcher.is_smartbackup_target(drive_e) is True

    def test_drive_matcher_ignores_unrelated_or_blank_drive(self, tmp_path: Path):
        """Ensure DriveMatcher returns False for blank or non-backup drives without preferred target."""
        drive = tmp_path / "random_usb"
        drive.mkdir()
        (drive / "photos").mkdir()

        config_mgr = MagicMock(spec=ConfigManager)
        config_mgr.get_preferred_target.return_value = None
        config_mgr.get_device_name.return_value = "Test-Host"

        matcher = DriveMatcher(config_manager=config_mgr)
        assert matcher.is_smartbackup_target(drive) is False

    def test_drive_matcher_handles_locked_bitlocker_volume(self, tmp_path: Path):
        """Ensure DriveMatcher catches PermissionError / OSError on locked BitLocker volume."""
        drive = tmp_path / "locked_drive"
        drive.mkdir()

        with patch.object(Path, "exists", side_effect=PermissionError("Access denied (BitLocker locked)")):
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(drive) is False

        with patch.object(Path, "exists", side_effect=OSError("[WinError 21] The device is not ready")):
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(drive) is False

    def test_drive_matcher_handles_nonexistent_path(self, tmp_path: Path):
        """Ensure DriveMatcher handles nonexistent paths gracefully."""
        nonexistent = tmp_path / "does_not_exist"
        matcher = DriveMatcher()
        assert matcher.is_smartbackup_target(nonexistent) is False

    def test_find_matching_targets(self, tmp_path: Path):
        """Ensure find_matching_targets filters correctly."""
        drive1 = tmp_path / "drive1"
        (drive1 / "Documents-Backup" / "Test-Host").mkdir(parents=True)
        (drive1 / "Documents-Backup" / "Test-Host" / ".smartbackup_manifest.json").write_text("{}")

        drive2 = tmp_path / "drive2"
        drive2.mkdir()

        with patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Host"):
            matcher = DriveMatcher()
            drives = [
                (drive1, "BackupDrive", 1000000),
                (drive2, "OtherDrive", 1000000),
            ]
            matches = matcher.find_matching_targets(drives)
            assert matches == [drive1]


class TestDebounceLock:
    """Tests for DebounceLock."""

    def test_debounce_cooldown_prevents_retrigger(self, tmp_path: Path):
        """Ensure DebounceLock blocks repeated triggers within cooldown window."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=300, state_file=state_file)
        drive = tmp_path / "usb_drive"

        # First mount -> Allowed
        assert debounce.should_prompt(drive) is True
        debounce.record_prompt(drive)

        # Immediate second mount -> Blocked
        assert debounce.should_prompt(drive) is False

    def test_debounce_allows_prompt_after_cooldown(self, tmp_path: Path):
        """Ensure DebounceLock allows prompt once cooldown expires."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=1, state_file=state_file)
        drive = tmp_path / "usb_drive"

        assert debounce.should_prompt(drive) is True
        debounce.record_prompt(drive)

        assert debounce.should_prompt(drive) is False

        # Wait for cooldown to expire (1.1s)
        time.sleep(1.1)
        # Also wait past global burst suppression (3.0s)
        time.sleep(2.0)

        assert debounce.should_prompt(drive) is True

    def test_multi_partition_burst_suppression(self, tmp_path: Path):
        """Ensure simultaneous multi-partition mounts suppress duplicate popups."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=300, state_file=state_file)
        partition1 = tmp_path / "partition1"
        partition2 = tmp_path / "partition2"

        # First partition triggers prompt
        assert debounce.should_prompt(partition1) is True
        debounce.record_prompt(partition1)

        # Second partition mounts immediately -> suppressed by global burst lock
        assert debounce.should_prompt(partition2) is False

    def test_wake_from_sleep_stampede_suppression(self, tmp_path: Path):
        """Simulate waking laptop with 3 already-connected drives; all duplicates are suppressed."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=300, state_file=state_file)
        drive1 = tmp_path / "drive1"
        drive2 = tmp_path / "drive2"
        drive3 = tmp_path / "drive3"

        # Record pre-sleep mounts
        debounce.record_prompt(drive1)
        debounce.record_prompt(drive2)
        debounce.record_prompt(drive3)

        # Wake event scans all three drives immediately
        assert debounce.should_prompt(drive1) is False
        assert debounce.should_prompt(drive2) is False
        assert debounce.should_prompt(drive3) is False

    def test_debounce_multithread_concurrency_safety(self, tmp_path: Path):
        """Ensure concurrent access from multiple threads does not corrupt state."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=300, state_file=state_file)

        def _worker(i: int):
            d = tmp_path / f"drive_{i}"
            debounce.should_prompt(d)
            debounce.record_prompt(d)
            return True

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(_worker, range(20)))

        assert all(results)
        assert state_file.exists()

    def test_debounce_persistence_and_clear(self, tmp_path: Path):
        """Ensure state file persistence and clear function."""
        state_file = tmp_path / "state.json"
        debounce = DebounceLock(cooldown_seconds=300, state_file=state_file)
        drive = tmp_path / "usb_drive"

        debounce.record_prompt(drive)
        assert state_file.exists()

        # Reinstantiate DebounceLock using same state file
        debounce2 = DebounceLock(cooldown_seconds=300, state_file=state_file)
        assert debounce2.should_prompt(drive) is False

        # Clear state
        debounce2.clear()
        assert debounce2.should_prompt(drive) is True


class TestDeviceWatcher:
    """Tests for DeviceWatcher."""

    def test_watcher_run_once_triggers_new_backup_drive(self, tmp_path: Path):
        """Ensure run_once triggers callback on newly detected target drive."""
        drive = tmp_path / "usb_drive"
        (drive / "Documents-Backup" / "Test-Host").mkdir(parents=True)
        (drive / "Documents-Backup" / "Test-Host" / ".smartbackup_manifest.json").write_text("{}")

        callback = MagicMock()
        state_file = tmp_path / "watcher_state.json"

        with patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Host"):
            watcher = DeviceWatcher(
                interval=0.1,
                cooldown=300,
                on_drive_detected=callback,
                state_file=state_file,
            )

            # Initially empty drives
            watcher._previous_drives = set()

            # Mock _get_current_drives returning the new drive
            with patch.object(watcher, "_get_current_drives", return_value={drive}):
                triggered = watcher.run_once()

                assert triggered == [drive]
                callback.assert_called_once_with(drive)

    def test_watcher_ignores_non_backup_drive(self, tmp_path: Path):
        """Ensure run_once ignores drives without SmartBackup target."""
        drive = tmp_path / "unrelated_drive"
        drive.mkdir()

        callback = MagicMock()
        state_file = tmp_path / "watcher_state.json"

        watcher = DeviceWatcher(
            interval=0.1,
            cooldown=300,
            on_drive_detected=callback,
            state_file=state_file,
        )
        watcher._previous_drives = set()

        with patch.object(watcher, "_get_current_drives", return_value={drive}):
            triggered = watcher.run_once()
            assert triggered == []
            callback.assert_not_called()

    def test_watcher_macos_polling_filters_system_volumes(self, tmp_path: Path):
        """Verify macOS polling filters internal system containers and APFS snapshots."""
        volumes_dir = tmp_path / "Volumes"
        volumes_dir.mkdir()

        # System volumes to be filtered
        (volumes_dir / "Macintosh HD").mkdir()
        (volumes_dir / "Macintosh HD - Data").mkdir()
        (volumes_dir / "Macbook").mkdir()
        (volumes_dir / ".timemachine").mkdir()
        (volumes_dir / ".Spotlight-V100").mkdir()
        (volumes_dir / ".fseventsd").mkdir()

        # Legitimate external backup volume
        valid_usb = volumes_dir / "External_Backup_USB"
        valid_usb.mkdir()

        watcher = DeviceWatcher()

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.iterdir", return_value=[
                 volumes_dir / "Macintosh HD",
                 volumes_dir / "Macintosh HD - Data",
                 volumes_dir / "Macbook",
                 volumes_dir / ".timemachine",
                 volumes_dir / ".Spotlight-V100",
                 volumes_dir / ".fseventsd",
                 valid_usb,
             ]):

            drives = watcher._get_macos_drives()
            assert valid_usb in drives
            assert (volumes_dir / "Macintosh HD") not in drives
            assert (volumes_dir / "Macintosh HD - Data") not in drives
            assert (volumes_dir / ".timemachine") not in drives

    def test_watcher_windows_polling_filters_drive_types(self):
        """Verify Windows polling only includes DRIVE_REMOVABLE (2) and DRIVE_FIXED (3)."""
        import ctypes

        watcher = DeviceWatcher()

        mock_kernel32 = MagicMock()
        mock_kernel32.GetLogicalDrives.return_value = 0b111100

        # C: FIXED (3), D: REMOVABLE (2), E: REMOTE (4), F: CDROM (5)
        def _mock_get_drive_type(drive_str):
            if "C:" in drive_str:
                return 3  # FIXED
            elif "D:" in drive_str:
                return 2  # REMOVABLE
            elif "E:" in drive_str:
                return 4  # REMOTE / NETWORK
            elif "F:" in drive_str:
                return 5  # CDROM
            return 1

        mock_kernel32.GetDriveTypeW.side_effect = _mock_get_drive_type

        mock_windll = MagicMock()
        mock_windll.kernel32 = mock_kernel32

        with patch.object(ctypes, "windll", mock_windll, create=True), \
             patch.object(Path, "exists", return_value=True):

            drives = watcher._get_windows_drives()
            drive_strs = [str(d) for d in drives]
            assert any("C:" in d for d in drive_strs)
            assert any("D:" in d for d in drive_strs)
            assert not any("E:" in d for d in drive_strs)
            assert not any("F:" in d for d in drive_strs)

    def test_watcher_linux_polling_discovers_media(self, tmp_path: Path):
        """Verify Linux polling searches /media/$USER, /run/media/$USER, and /mnt."""
        media_user = tmp_path / "media" / "testuser"
        media_user.mkdir(parents=True)
        usb1 = media_user / "usb_drive_1"
        usb1.mkdir()

        mnt = tmp_path / "mnt"
        mnt.mkdir()
        usb2 = mnt / "external_ssd"
        usb2.mkdir()

        watcher = DeviceWatcher()

        def _mock_iterdir(path_obj):
            path_str = str(path_obj)
            if "media" in path_str and "testuser" in path_str:
                return [usb1]
            elif "mnt" in path_str:
                return [usb2]
            return []

        with patch.dict("os.environ", {"USER": "testuser"}), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "iterdir", _mock_iterdir):

            drives = watcher._get_linux_drives()
            assert usb1 in drives or usb2 in drives

    def test_watcher_handles_inaccessible_drive_during_polling(self, tmp_path: Path):
        """Ensure DeviceWatcher continues gracefully when a drive throws PermissionError during scan."""
        locked_drive = tmp_path / "locked_drive"
        locked_drive.mkdir()

        state_file = tmp_path / "watcher_state.json"
        watcher = DeviceWatcher(state_file=state_file)
        watcher._previous_drives = set()

        with patch.object(watcher, "_get_current_drives", return_value={locked_drive}), \
             patch.object(watcher.matcher, "is_smartbackup_target", side_effect=PermissionError("Locked")):

            triggered = watcher.run_once()
            assert triggered == []

    def test_watcher_start_and_stop_lifecycle(self, tmp_path: Path):
        """Ensure start (non-blocking) and stop work properly."""
        state_file = tmp_path / "watcher_state.json"
        watcher = DeviceWatcher(
            interval=0.05,
            cooldown=300,
            state_file=state_file,
        )

        with patch.object(watcher, "_get_current_drives", return_value=set()):
            watcher.start(blocking=False)
            assert not watcher._stop_event.is_set()

            watcher.stop()
            assert watcher._stop_event.is_set()
