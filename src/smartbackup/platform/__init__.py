"""SmartBackup platform-specific components."""

from smartbackup.platform.devices import DeviceDetector
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.platform.scheduler import SchedulerHelper
from smartbackup.platform.terminal import TerminalSpawner
from smartbackup.platform.watcher import DebounceLock, DeviceWatcher, DriveMatcher

__all__ = [
    "PathResolver",
    "DeviceDetector",
    "SchedulerHelper",
    "get_device_name",
    "DriveMatcher",
    "DebounceLock",
    "DeviceWatcher",
    "TerminalSpawner",
]
