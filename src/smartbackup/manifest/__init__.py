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
)
from smartbackup.manifest.json_manifest import JsonManifestManager

__all__ = [
    "Manifest",
    "ManifestDiff",
    "ManifestEntry",
    "ManifestFormat",
    "ManifestManager",
    "JsonManifestManager",
]
