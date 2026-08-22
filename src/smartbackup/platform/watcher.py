"""
Watcher - Target matcher, debounce lock, and drive watcher daemon.
"""

import json
import logging
import os
import platform
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from smartbackup.config import ConfigManager
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver

logger = logging.getLogger(__name__)

# Exclusion names for macOS /Volumes scanning
MACOS_EXCLUDED_VOLUMES = {
    "Macintosh HD",
    "Macintosh HD - Data",
    "Macbook",
    "Macbook - Data",
    ".timemachine",
}


class DriveMatcher:
    """
    Validates whether a detected mount point is a SmartBackup target.

    Checks for:
    1. Per-device layout: Documents-Backup/<hostname>/.smartbackup_manifest.json
    2. Legacy flat layout: Documents-Backup/.smartbackup_manifest.json
    3. Configured preferred target label match.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self.config_manager = config_manager or ConfigManager()

    def is_smartbackup_target(
        self, drive_path: Path, preferred_label: Optional[str] = None
    ) -> bool:
        """
        Check if the given drive path contains a SmartBackup backup or matches preferred target.

        Args:
            drive_path: Path to the drive / mount point
            preferred_label: Optional explicit label to match against

        Returns:
            True if the drive qualifies as a backup target, False otherwise.
        """
        try:
            if not drive_path.exists():
                return False
        except (PermissionError, OSError):
            return False

        # 1. Check preferred target label
        target_label = preferred_label or self.config_manager.get_preferred_target()
        if target_label:
            # Check drive path name or volume label
            if drive_path.name.lower() == target_label.lower():
                return True
            # On Windows, check drive letter like "E:"
            if str(drive_path).rstrip(":\\/").lower() == target_label.rstrip(":\\/").lower():
                return True

        backup_root = drive_path / "Documents-Backup"
        try:
            if not backup_root.exists() or not backup_root.is_dir():
                return False
        except (PermissionError, OSError):
            return False

        # 2. Check per-device layout: Documents-Backup/<hostname>/.smartbackup_manifest.json
        device_name = self.config_manager.get_device_name() or get_device_name()
        per_device_manifest = backup_root / device_name / ".smartbackup_manifest.json"
        try:
            if per_device_manifest.exists():
                return True
        except (PermissionError, OSError):
            pass

        # Also check if the device folder itself exists
        try:
            device_folder = backup_root / device_name
            if device_folder.exists() and device_folder.is_dir():
                return True
        except (PermissionError, OSError):
            pass

        # 3. Check legacy flat layout: Documents-Backup/.smartbackup_manifest.json
        legacy_manifest = backup_root / ".smartbackup_manifest.json"
        try:
            if legacy_manifest.exists():
                return True
        except (PermissionError, OSError):
            pass

        return False

    def find_matching_targets(
        self, drives: Optional[list[tuple[Path, str, int]]] = None
    ) -> list[Path]:
        """
        Find all external drives that qualify as SmartBackup targets.

        Args:
            drives: Optional list of (path, label, free_bytes). If None, calls PathResolver.

        Returns:
            List of Path objects for qualifying backup targets.
        """
        if drives is None:
            drives = PathResolver.find_external_drives()

        matches: list[Path] = []
        for path, label, _ in drives:
            if self.is_smartbackup_target(path, preferred_label=label):
                matches.append(path)
        return matches


class DebounceLock:
    """
    Prevents repeated terminal prompt spawns for the same drive within a cooldown window.
    Also prevents prompt storms when multi-partition drives mount simultaneously.

    State is maintained in-memory and persisted to disk.
    """

    def __init__(
        self,
        cooldown_seconds: int = 300,
        state_file: Optional[Path] = None,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        if state_file is None:
            config_mgr = ConfigManager()
            self.state_file = config_mgr.config_dir / "watcher_state.json"
        else:
            self.state_file = Path(state_file)
        self._lock = threading.Lock()
        self._memory_cache: dict[str, float] = {}
        self._load_state()

    def _normalize_drive_key(self, drive_path: Path) -> str:
        """Get a normalized string key representing the drive."""
        try:
            return str(drive_path.resolve()).rstrip("\\/")
        except Exception:
            return str(drive_path).rstrip("\\/")

    def _load_state(self) -> dict[str, float]:
        """Load state from disk into memory cache."""
        state: dict[str, float] = {}
        if self.state_file.exists():
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        state = {str(k): float(v) for k, v in data.items() if isinstance(v, (int, float))}
            except Exception:
                state = {}
        self._memory_cache = state
        return state

    def _save_state(self) -> None:
        """Persist state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2)
        except Exception:
            pass

    def should_prompt(
        self,
        drive_path: Path,
        cooldown_seconds: Optional[int] = None,
    ) -> bool:
        """
        Check if a prompt is allowed for the specified drive.

        Args:
            drive_path: Path to the mounted drive
            cooldown_seconds: Optional cooldown override (default: self.cooldown_seconds)

        Returns:
            True if prompt should be spawned, False if suppressed by cooldown.
        """
        cooldown = cooldown_seconds if cooldown_seconds is not None else self.cooldown_seconds
        drive_key = self._normalize_drive_key(drive_path)
        now = time.time()

        with self._lock:
            self._load_state()

            # Multi-partition burst suppression: if any prompt occurred within 3 seconds, suppress
            last_global = self._memory_cache.get("__last_global_prompt__", 0.0)
            if now - last_global < 3.0:
                return False

            # Cooldown per drive
            last_prompt = self._memory_cache.get(drive_key, 0.0)
            if now - last_prompt < cooldown:
                return False

            return True

    def record_prompt(self, drive_path: Path) -> None:
        """
        Record that a prompt was spawned for the given drive.

        Args:
            drive_path: Path to the mounted drive
        """
        drive_key = self._normalize_drive_key(drive_path)
        now = time.time()

        with self._lock:
            self._memory_cache[drive_key] = now
            self._memory_cache["__last_global_prompt__"] = now

            # Prune entries older than 2x cooldown
            max_age = max(self.cooldown_seconds * 2, 600)
            self._memory_cache = {
                k: v for k, v in self._memory_cache.items()
                if (now - v) < max_age or k == "__last_global_prompt__"
            }

            self._save_state()

    def clear(self) -> None:
        """Clear all debounce state."""
        with self._lock:
            self._memory_cache.clear()
            if self.state_file.exists():
                try:
                    self.state_file.unlink()
                except Exception:
                    pass


class DeviceWatcher:
    """
    Cross-platform device watcher that detects newly mounted storage media
    and triggers prompt sessions for matching SmartBackup targets.
    """

    def __init__(
        self,
        interval: float = 2.5,
        cooldown: int = 300,
        on_drive_detected: Optional[Callable[[Path], None]] = None,
        config_manager: Optional[ConfigManager] = None,
        state_file: Optional[Path] = None,
    ) -> None:
        self.interval = interval
        self.cooldown = cooldown
        self.config_manager = config_manager or ConfigManager()
        self.matcher = DriveMatcher(self.config_manager)
        self.debounce = DebounceLock(cooldown_seconds=cooldown, state_file=state_file)
        self.on_drive_detected = on_drive_detected
        self._stop_event = threading.Event()
        self._previous_drives: set[Path] = set()

    def _get_current_drives(self) -> set[Path]:
        """Scan system for currently mounted storage drives."""
        system = platform.system()
        drives: set[Path] = set()

        if system == "Windows":
            drives = self._get_windows_drives()
        elif system == "Darwin":
            drives = self._get_macos_drives()
        else:
            drives = self._get_linux_drives()

        return drives

    def _get_windows_drives(self) -> set[Path]:
        """Detect Windows logical drives via Win32 API."""
        drives: set[Path] = set()
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            bitmask = kernel32.GetLogicalDrives()
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                if bitmask & 1:
                    drive_path = Path(f"{letter}:\\")
                    try:
                        drive_type = kernel32.GetDriveTypeW(str(drive_path))
                        # 2 = DRIVE_REMOVABLE, 3 = DRIVE_FIXED
                        if drive_type in (2, 3) and drive_path.exists():
                            drives.add(drive_path)
                    except Exception:
                        pass
                bitmask >>= 1
        except Exception:
            # Fallback
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive_path = Path(f"{letter}:\\")
                try:
                    if drive_path.exists():
                        drives.add(drive_path)
                except Exception:
                    pass
        return drives

    def _get_macos_drives(self) -> set[Path]:
        """Detect macOS mounted volumes under /Volumes."""
        drives: set[Path] = set()
        volumes_path = Path("/Volumes")
        if volumes_path.exists():
            try:
                for volume in volumes_path.iterdir():
                    try:
                        if (
                            volume.is_dir()
                            and volume.name not in MACOS_EXCLUDED_VOLUMES
                            and not volume.name.startswith(".")
                        ):
                            drives.add(volume)
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass
        return drives

    def _get_linux_drives(self) -> set[Path]:
        """Detect Linux mounted media."""
        drives: set[Path] = set()
        mount_points = [
            Path("/media") / os.environ.get("USER", ""),
            Path("/run/media") / os.environ.get("USER", ""),
            Path("/mnt"),
        ]
        for mount_base in mount_points:
            if mount_base.exists():
                try:
                    for mount in mount_base.iterdir():
                        try:
                            if mount.is_dir() and not mount.name.startswith("."):
                                drives.add(mount)
                        except (PermissionError, OSError):
                            pass
                except (PermissionError, OSError):
                    pass
        return drives

    def run_once(self) -> list[Path]:
        """
        Execute a single polling check for newly attached drives.

        Returns:
            List of newly attached qualifying drives triggered.
        """
        current_drives = self._get_current_drives()
        new_drives = current_drives - self._previous_drives
        self._previous_drives = current_drives

        triggered: list[Path] = []
        for drive in new_drives:
            try:
                if self.matcher.is_smartbackup_target(drive):
                    if self.debounce.should_prompt(drive):
                        self.debounce.record_prompt(drive)
                        triggered.append(drive)
                        if self.on_drive_detected:
                            try:
                                self.on_drive_detected(drive)
                            except Exception as e:
                                logger.error(f"Error in on_drive_detected callback: {e}")
            except Exception as e:
                logger.error(f"Error checking drive {drive}: {e}")

        return triggered

    def start(self, blocking: bool = True) -> None:
        """
        Start the drive watcher polling loop.

        Args:
            blocking: If True, blocks until stopped or KeyboardInterrupt.
        """
        self._stop_event.clear()
        # Initialize baseline of currently connected drives
        self._previous_drives = self._get_current_drives()

        def _loop() -> None:
            while not self._stop_event.is_set():
                self.run_once()
                self._stop_event.wait(self.interval)

        if blocking:
            try:
                _loop()
            except KeyboardInterrupt:
                self.stop()
        else:
            thread = threading.Thread(target=_loop, daemon=True, name="SmartBackup-DeviceWatcher")
            thread.start()

    def stop(self) -> None:
        """Stop the drive watcher loop."""
        self._stop_event.set()
