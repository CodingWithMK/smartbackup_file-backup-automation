"""
Manifest Factory - Format selection and auto-detection for SmartBackup manifests.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from smartbackup.manifest.base import ManifestFormat, ManifestManager
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.manifest.sqlite_manifest import SqliteManifestManager

if TYPE_CHECKING:
    from smartbackup.ui.logger import BackupLogger

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


def resolve_device_target(
    backup_root: Path,
    device_name: Optional[str] = None,
) -> Path:
    """Resolve the backup target directory, accounting for per-device subfolders.

    Resolution order:
    1. Explicit non-empty *device_name* -> ``backup_root / device_name.strip()``.
    2. Legacy flat layout (manifest directly under *backup_root*) -> ``backup_root``.
    3. Auto-detected device directory (``backup_root / get_device_name()``) if
       it exists as a directory.
    4. Fallback -> ``backup_root``.
    """
    cleaned = device_name.strip() if device_name else ""
    if cleaned:
        return backup_root / cleaned

    # Legacy layout: manifest lives directly in backup_root
    if has_manifest(backup_root):
        return backup_root

    # New layout: use auto-detected device name if its directory exists
    from smartbackup.platform import identity

    candidate = backup_root / identity.get_device_name()
    if candidate.is_dir():
        return candidate

    return backup_root


def detect_manifest_manager(
    backup_path: Path,
    logger: Optional["BackupLogger"] = None,
) -> Optional[ManifestManager]:
    """
    Detect an existing manifest in *backup_path* and return its manager.

    If both JSON and SQLite manifests exist (e.g. an interrupted manual edit),
    the more recently modified file wins. Returns None when no manifest exists.
    """
    candidates: list[ManifestManager] = []
    for manager in (
        JsonManifestManager(backup_path, logger=logger),
        SqliteManifestManager(backup_path, logger=logger),
    ):
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
    logger: Optional["BackupLogger"] = None,
) -> ManifestManager:
    """
    Return the appropriate ManifestManager for *backup_path*.

    Args:
        backup_path: Directory holding the backup files and manifest.
        fmt: Explicit format ("json", "sqlite", or ManifestFormat). When None,
            auto-detects an existing manifest on disk and falls back to JSON.
        logger: Optional BackupLogger for routing manifest warnings.

    Raises:
        ValueError: If *fmt* is not a supported manifest format.
    """
    if fmt is None:
        return detect_manifest_manager(backup_path, logger=logger) or JsonManifestManager(
            backup_path, logger=logger
        )

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
        return SqliteManifestManager(backup_path, logger=logger)
    return JsonManifestManager(backup_path, logger=logger)
