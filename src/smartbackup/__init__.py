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

__version__ = "0.1.0"
__author__ = "Muhammed Musab Kaya - @CodingWithMK"
__license__ = "MIT"

from smartbackup.smart_backup import (
    SmartBackup,
    BackupConfig,
    BackupResult,
    BackupLogger,
    PathResolver,
    main,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Main class
    "SmartBackup",
    # Config and result
    "BackupConfig",
    "BackupResult",
    # Utilities
    "BackupLogger",
    "PathResolver",
    "DeviceDetector",
    "ConfigManager",
    # Core components
    "BackupEngine",
    "FileScanner",
    "ChangeDetector",
    "ExclusionFilter",
    # Entry point
    "main",
]