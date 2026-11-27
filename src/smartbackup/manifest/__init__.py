"""
Manifest - Backup manifest tracking for SmartBackup.

Provides incremental backup tracking through manifest files
that store file metadata (hash, size, mtime) for efficient
change detection without rescanning the backup directory.
"""

from smartbackup.manifest.base import (
    Manifest,
    ManifestDiff,
    ManifestEntry,
    ManifestFormat,
    ManifestManager,
    SelectiveBackupRecord,
)
from smartbackup.manifest.factory import (
    SUPPORTED_MANIFEST_FORMATS,
    detect_manifest_manager,
    get_manifest_manager,
    has_manifest,
    resolve_device_target,
)
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.manifest.sqlite_manifest import SqliteManifestManager

__all__ = [
    "Manifest",
    "ManifestDiff",
    "ManifestEntry",
    "ManifestFormat",
    "ManifestManager",
    "SelectiveBackupRecord",
    "JsonManifestManager",
    "SqliteManifestManager",
    "SUPPORTED_MANIFEST_FORMATS",
    "get_manifest_manager",
    "detect_manifest_manager",
    "has_manifest",
    "resolve_device_target",
]
