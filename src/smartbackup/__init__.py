"""
SmartBackup - Intelligent Backup System for Developers

A cross-platform, incremental backup solution that automatically
filters out development artifacts like node_modules, virtual environments,
and build directories.

Quick Start:
    # From command line
    $ smartbackup
    $ python -m smartbackup

    # From Python
    >>> from smartbackup import SmartBackup
    >>> backup = SmartBackup()
    >>> backup.run()
"""

__version__ = "0.4.0"
__author__ = "Muhammed Musab Kaya - @CodingWithMK"
__license__ = "MIT"

# Import from new modular structure
from smartbackup.backup import SmartBackup
from smartbackup.cli import main
from smartbackup.config import BackupConfig, ConfigManager, DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS
from smartbackup.core.detector import ChangeDetector
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.core.restore import ConflictResolution, RestoreEngine, RestoreResult
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.handlers import FallbackHandler
from smartbackup.manifest import (
    JsonManifestManager,
    Manifest,
    ManifestDiff,
    ManifestEntry,
    ManifestFormat,
    ManifestManager,
)
from smartbackup.models import BackupResult, FileAction, FileInfo
from smartbackup.platform.devices import DeviceDetector
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.platform.scheduler import SchedulerHelper
from smartbackup.ui.colors import Colors
from smartbackup.ui.logger import BackupLogger

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Main class
    "SmartBackup",
    # Config and constants
    "BackupConfig",
    "ConfigManager",
    "DEFAULT_EXCLUSIONS",
    "EXCLUDED_EXTENSIONS",
    # Models
    "BackupResult",
    "FileInfo",
    "FileAction",
    # Core components
    "BackupEngine",
    "DryRunBackupEngine",
    "FileScanner",
    "ExclusionFilter",
    "ChangeDetector",
    "RestoreEngine",
    "RestoreResult",
    "ConflictResolution",
    # Manifest
    "Manifest",
    "ManifestEntry",
    "ManifestDiff",
    "ManifestFormat",
    "ManifestManager",
    "JsonManifestManager",
    # Platform
    "PathResolver",
    "DeviceDetector",
    "SchedulerHelper",
    "get_device_name",
    # UI
    "BackupLogger",
    "Colors",
    # Handlers
    "FallbackHandler",
    # Entry point
    "main",
]
