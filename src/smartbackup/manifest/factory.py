"""
Manifest Factory - Format selection and auto-detection for SmartBackup manifests.
"""

from pathlib import Path
from typing import Optional, Union

from smartbackup.manifest.base import ManifestFormat, ManifestManager
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.manifest.sqlite_manifest import SqliteManifestManager

SUPPORTED_MANIFEST_FORMATS: tuple[str, ...] = (
    ManifestFormat.JSON.value,
    ManifestFormat.SQLITE.value,
)


def has_manifest(backup_dir: Path) -> bool:
    """Return True if *backup_dir* contains a JSON or SQLite SmartBackup manifest."""
    return (
        JsonManifestManager(backup_dir).exists()
        or SqliteManifestManager(backup_dir).exists()
    )


def detect_manifest_manager(backup_path: Path) -> Optional[ManifestManager]:
    """
    Detect an existing manifest in *backup_path* and return its manager.

    If both JSON and SQLite manifests exist (e.g. an interrupted manual edit),
    the more recently modified file wins. Returns None when no manifest exists.
    """
    candidates: list[ManifestManager] = []
    for manager in (JsonManifestManager(backup_path), SqliteManifestManager(backup_path)):
        if manager.exists():
            candidates.append(manager)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    def _safe_mtime(mgr: ManifestManager) -> float:
        try:
            return mgr.manifest_path.stat().st_mtime
        except OSError:
            return 0.0

    return max(candidates, key=_safe_mtime)


def get_manifest_manager(
    backup_path: Path,
    fmt: Optional[Union[str, ManifestFormat]] = None,
) -> ManifestManager:
    """
    Return the appropriate ManifestManager for *backup_path*.

    Args:
        backup_path: Directory holding the backup files and manifest.
        fmt: Explicit format ("json", "sqlite", or ManifestFormat). When None,
            auto-detects an existing manifest on disk and falls back to JSON.

    Raises:
        ValueError: If *fmt* is not a supported manifest format.
    """
    if fmt is None:
        return detect_manifest_manager(backup_path) or JsonManifestManager(backup_path)

    if isinstance(fmt, ManifestFormat):
        resolved = fmt
    else:
        normalized = fmt.strip().lower()
        try:
            resolved = ManifestFormat(normalized)
        except ValueError as exc:
            valid = ", ".join(SUPPORTED_MANIFEST_FORMATS)
            raise ValueError(
                f"Unsupported manifest format: {fmt!r}. Choose from: {valid}"
            ) from exc

    if resolved == ManifestFormat.SQLITE:
        return SqliteManifestManager(backup_path)
    return JsonManifestManager(backup_path)
