"""
Manifest Base - Base classes for manifest tracking.
"""

import hashlib
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from smartbackup.models import FileInfo

if TYPE_CHECKING:
    from smartbackup.ui.logger import BackupLogger


class ManifestFormat(Enum):
    """Supported manifest formats."""

    JSON = "json"
    SQLITE = "sqlite"


@dataclass
class ManifestEntry:
    """
    Represents a single file entry in the manifest.

    Stores all metadata needed for change detection and verification.
    """

    relative_path: str
    file_hash: str
    size: int
    mtime: float
    permissions: int
    backed_up_at: float

    def to_dict(self) -> dict:
        """Converts entry to dictionary for serialization."""
        return {
            "hash": self.file_hash,
            "size": self.size,
            "mtime": self.mtime,
            "permissions": self.permissions,
            "backed_up_at": self.backed_up_at,
        }

    @classmethod
    def from_dict(cls, relative_path: str, data: dict) -> "ManifestEntry":
        """Creates entry from dictionary."""
        return cls(
            relative_path=relative_path,
            file_hash=data.get("hash", ""),
            size=data.get("size", 0),
            mtime=data.get("mtime", 0.0),
            permissions=data.get("permissions", 0o644),
            backed_up_at=data.get("backed_up_at", 0.0),
        )

    @classmethod
    def from_file_info(
        cls, file_info: FileInfo, backed_up_at: Optional[float] = None
    ) -> "ManifestEntry":
        """Creates entry from FileInfo."""
        if backed_up_at is None:
            backed_up_at = datetime.now().timestamp()

        # Get permissions from file
        try:
            permissions = file_info.path.stat().st_mode
        except OSError:
            permissions = 0o644

        return cls(
            relative_path=str(file_info.relative_path),
            file_hash=file_info.file_hash or "",
            size=file_info.size,
            mtime=file_info.mtime,
            permissions=permissions,
            backed_up_at=backed_up_at,
        )

    def has_changed(self, file_info: FileInfo) -> bool:
        """
        Check if a source file has changed compared to this entry.

        Uses size and mtime for quick comparison, then hash if available.
        """
        # Size changed = definitely changed
        if file_info.size != self.size:
            return True

        # Mtime changed = likely changed
        if file_info.mtime != self.mtime:
            return True

        # Hashing was requested but failed -> cannot verify unchanged
        if file_info.hash_error:
            return True

        # If both have hashes, compare them
        if file_info.file_hash and self.file_hash:
            return file_info.file_hash != self.file_hash

        return False


@dataclass
class SelectiveBackupRecord:
    """Audit record for a single --select folder backup run."""

    run_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    command_option: str = "--select"
    scope: str = "folders"
    source_root: str = ""
    selected_folders: list[str] = field(default_factory=list)
    available_folders_count: int = 0
    files_scanned: int = 0
    files_copied: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    files_skipped: int = 0
    bytes_copied: int = 0
    duration_seconds: float = 0.0
    workflow_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert selective backup record to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "command_option": self.command_option,
            "scope": self.scope,
            "source_root": self.source_root,
            "selected_folders": list(self.selected_folders),
            "available_folders_count": self.available_folders_count,
            "files_scanned": self.files_scanned,
            "files_copied": self.files_copied,
            "files_updated": self.files_updated,
            "files_deleted": self.files_deleted,
            "files_skipped": self.files_skipped,
            "bytes_copied": self.bytes_copied,
            "duration_seconds": self.duration_seconds,
            "workflow_steps": list(self.workflow_steps),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SelectiveBackupRecord":
        """Create selective backup record from dictionary with backward-safe defaults."""
        raw_ts = data.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(raw_ts) if raw_ts else datetime.now()
        except (TypeError, ValueError):
            timestamp = datetime.now()

        return cls(
            run_id=str(data.get("run_id", "")),
            timestamp=timestamp,
            command_option=str(data.get("command_option", "--select")),
            scope=str(data.get("scope", "folders")),
            source_root=str(data.get("source_root", "")),
            selected_folders=list(data.get("selected_folders", [])),
            available_folders_count=int(data.get("available_folders_count", 0)),
            files_scanned=int(data.get("files_scanned", 0)),
            files_copied=int(data.get("files_copied", 0)),
            files_updated=int(data.get("files_updated", 0)),
            files_deleted=int(data.get("files_deleted", 0)),
            files_skipped=int(data.get("files_skipped", 0)),
            bytes_copied=int(data.get("bytes_copied", 0)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            workflow_steps=list(data.get("workflow_steps", [])),
        )


@dataclass
class Manifest:
    """
    Represents a complete backup manifest.

    Contains metadata about the backup, all file entries, and a clearly
    separated audit trail of selective (--select) folder backup runs.
    """

    version: int = 1
    format: ManifestFormat = ManifestFormat.JSON
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    source: str = ""
    hostname: str = ""  # Device hostname for identification
    hash_algorithm: str = "sha256"  # Hash algorithm used for file hashes
    backup_count: int = 0
    entries: dict[str, ManifestEntry] = field(default_factory=dict)
    last_backup_mode: str = "full"  # "full" or "select"
    last_selected_folders: list[str] = field(default_factory=list)
    selective_backups: list[SelectiveBackupRecord] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        """Total number of files in manifest."""
        return len(self.entries)

    @property
    def total_size(self) -> int:
        """Total size of all files in manifest."""
        return sum(e.size for e in self.entries.values())

    def add_entry(self, entry: ManifestEntry) -> None:
        """Add or update an entry in the manifest."""
        self.entries[entry.relative_path] = entry
        self.updated = datetime.now()

    def add_selective_backup(self, record: SelectiveBackupRecord) -> None:
        """Record a selective (--select) backup run in the manifest."""
        self.last_backup_mode = "select"
        self.last_selected_folders = list(record.selected_folders)
        self.selective_backups.append(record)
        self.updated = datetime.now()

    def remove_entry(self, relative_path: str) -> Optional[ManifestEntry]:
        """Remove an entry from the manifest."""
        entry = self.entries.pop(relative_path, None)
        if entry:
            self.updated = datetime.now()
        return entry

    def get_entry(self, relative_path: str) -> Optional[ManifestEntry]:
        """Get an entry by relative path."""
        return self.entries.get(relative_path)

    def has_entry(self, relative_path: str) -> bool:
        """Check if an entry exists."""
        return relative_path in self.entries

    def iter_entries(self) -> Iterator[ManifestEntry]:
        """Iterate over all entries."""
        yield from self.entries.values()

    def to_dict(self) -> dict:
        """Convert manifest to dictionary for serialization."""
        return {
            "version": self.version,
            "format": self.format.value,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "source": self.source,
            "hostname": self.hostname,
            "hash_algorithm": self.hash_algorithm,
            "backup_count": self.backup_count,
            "last_backup_mode": self.last_backup_mode,
            "last_selected_folders": list(self.last_selected_folders),
            "total_files": self.total_files,
            "total_size": self.total_size,
            "selective_backups": [r.to_dict() for r in self.selective_backups],
            "files": {path: entry.to_dict() for path, entry in self.entries.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        """Create manifest from dictionary with backward-compatible defaults."""
        raw_selective = data.get("selective_backups", [])
        selective_records = [
            SelectiveBackupRecord.from_dict(item)
            for item in raw_selective
            if isinstance(item, dict)
        ]

        manifest = cls(
            version=data.get("version", 1),
            format=ManifestFormat(data.get("format", "json")),
            created=datetime.fromisoformat(data.get("created", datetime.now().isoformat())),
            updated=datetime.fromisoformat(data.get("updated", datetime.now().isoformat())),
            source=data.get("source", ""),
            hostname=data.get("hostname", ""),
            hash_algorithm=data.get("hash_algorithm", "md5"),  # old manifests used MD5
            backup_count=data.get("backup_count", 0),
            last_backup_mode=str(data.get("last_backup_mode", "full")),
            last_selected_folders=list(data.get("last_selected_folders", [])),
            selective_backups=selective_records,
        )

        # Load file entries
        files_data = data.get("files", {})
        for relative_path, entry_data in files_data.items():
            manifest.entries[relative_path] = ManifestEntry.from_dict(relative_path, entry_data)

        return manifest


@dataclass
class ManifestDiff:
    """
    Result of comparing source files against a manifest.

    Used to determine what needs to be backed up.
    """

    new_files: list[FileInfo] = field(default_factory=list)
    modified_files: list[FileInfo] = field(default_factory=list)
    deleted_paths: list[str] = field(default_factory=list)
    unchanged_files: list[FileInfo] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.new_files or self.modified_files or self.deleted_paths)

    @property
    def files_to_backup(self) -> list[FileInfo]:
        """Get all files that need to be backed up."""
        return self.new_files + self.modified_files

    @property
    def summary(self) -> str:
        """Get a summary of changes."""
        return (
            f"New: {len(self.new_files)}, "
            f"Modified: {len(self.modified_files)}, "
            f"Deleted: {len(self.deleted_paths)}, "
            f"Unchanged: {len(self.unchanged_files)}"
        )


class ManifestManager(ABC):
    """
    Abstract base class for manifest management.

    Provides interface for loading, saving, and updating manifests.
    Different storage backends (JSON, SQLite) implement this interface.
    """

    MANIFEST_FILENAME = ".smartbackup_manifest"
    FORMAT: ManifestFormat = ManifestFormat.JSON

    def __init__(self, backup_path: Path, logger: Optional["BackupLogger"] = None):
        """
        Initialize manifest manager.

        Args:
            backup_path: Path to the backup directory
            logger: Optional BackupLogger for routing warnings instead of raw stderr
        """
        self.backup_path = backup_path
        self.logger = logger

    def _warn(self, message: str) -> None:
        """Emit a warning through the injected logger, or stderr as fallback."""
        if self.logger is not None:
            self.logger.warning(message)
        else:
            print(f"Warning: {message}", file=sys.stderr)

    @property
    @abstractmethod
    def manifest_path(self) -> Path:
        """Path to the manifest file."""
        pass

    @abstractmethod
    def load(self) -> Optional[Manifest]:
        """
        Load manifest from storage.

        Returns:
            Manifest if exists, None otherwise
        """
        pass

    @abstractmethod
    def save(self, manifest: Manifest) -> bool:
        """
        Save manifest to storage.

        Args:
            manifest: The manifest to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def exists(self) -> bool:
        """Check if manifest exists."""
        pass

    def create(self, source_path: Path) -> Manifest:
        """
        Create a new empty manifest.

        Args:
            source_path: The source directory being backed up

        Returns:
            New empty manifest
        """
        return Manifest(
            format=self.FORMAT,
            source=str(source_path),
            backup_count=0,
        )

    def load_or_create(self, source_path: Path) -> Manifest:
        """
        Load existing manifest or create a new one.

        Args:
            source_path: The source directory being backed up

        Returns:
            Existing or new manifest
        """
        manifest = self.load()
        if manifest is None:
            manifest = self.create(source_path)
        return manifest

    def diff(
        self,
        source_files: dict[Path, FileInfo],
        manifest: Optional[Manifest] = None,
        scoped_folders: Optional[list[str]] = None,
    ) -> ManifestDiff:
        """
        Compare source files against manifest to find changes.

        Args:
            source_files: Dictionary of source files (path -> FileInfo)
            manifest: Existing manifest (loads from storage if None)
            scoped_folders: Optional list of top-level folder names to restrict
                deletion detection to (used by ``--select``). Manifest entries
                outside these folders (including loose root-level files) are
                immune and will never be reported in ``deleted_paths``.

        Returns:
            ManifestDiff with new, modified, and deleted files
        """
        if manifest is None:
            manifest = self.load()

        result = ManifestDiff()

        if manifest is None:
            # No manifest = all files are new
            result.new_files = list(source_files.values())
            return result

        # Track which manifest entries we've seen
        seen_paths: set[str] = set()

        for file_info in source_files.values():
            relative_path = str(file_info.relative_path)
            seen_paths.add(relative_path)

            entry = manifest.get_entry(relative_path)

            if entry is None:
                # New file
                result.new_files.append(file_info)
            elif entry.has_changed(file_info):
                # Modified file
                result.modified_files.append(file_info)
            else:
                # Unchanged
                result.unchanged_files.append(file_info)

        scoped_set: Optional[set[str]] = (
            set(scoped_folders) if scoped_folders is not None else None
        )

        # Find deleted files (in manifest but not in source)
        for relative_path in manifest.entries:
            if relative_path not in seen_paths:
                if scoped_set is not None:
                    parts = Path(relative_path.replace("\\", "/")).parts
                    # Only entries inside a selected top-level folder are in scope;
                    # loose root-level files (len(parts) < 2) and unselected folders are immune.
                    if len(parts) < 2 or parts[0] not in scoped_set:
                        continue
                result.deleted_paths.append(relative_path)

        return result

    def update_from_backup(
        self,
        manifest: Manifest,
        backed_up_files: list[FileInfo],
        deleted_paths: Optional[list[str]] = None,
    ) -> Manifest:
        """
        Update manifest after a backup operation.

        Args:
            manifest: The manifest to update
            backed_up_files: Files that were backed up
            deleted_paths: Paths that were deleted from backup

        Returns:
            Updated manifest
        """
        backup_time = datetime.now().timestamp()

        # Add/update entries for backed up files
        for file_info in backed_up_files:
            entry = ManifestEntry.from_file_info(file_info, backed_up_at=backup_time)
            manifest.add_entry(entry)

        # Remove entries for deleted files
        if deleted_paths:
            for path in deleted_paths:
                manifest.remove_entry(path)

        # Update metadata
        manifest.backup_count += 1
        manifest.updated = datetime.now()

        return manifest

    @staticmethod
    def _hash_file(path: Path, chunk_size: int = 65536) -> Optional[str]:
        """Calculate SHA-256 hash of a file for verification.

        Returns ``None`` if the file cannot be read.
        """
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError:
            return None

    def verify(
        self, manifest: Manifest, backup_target: Path, verify_hashes: bool = False
    ) -> list[str]:
        """
        Verify backup files against manifest.

        Args:
            manifest: The manifest to verify against
            backup_target: Path to the backup directory
            verify_hashes: If True, re-hash files and compare against stored hashes

        Returns:
            List of verification errors (empty if all files match)
        """
        errors = []

        for entry in manifest.iter_entries():
            file_path = backup_target / entry.relative_path

            if not file_path.exists():
                errors.append(f"Missing: {entry.relative_path}")
                continue

            try:
                stat = file_path.stat()

                if stat.st_size != entry.size:
                    errors.append(
                        f"Size mismatch: {entry.relative_path} "
                        f"(expected {entry.size}, got {stat.st_size})"
                    )
                elif verify_hashes and entry.file_hash:
                    actual_hash = self._hash_file(file_path)
                    if actual_hash is None:
                        errors.append(
                            f"Error hashing {entry.relative_path}: unable to read file"
                        )
                    elif actual_hash != entry.file_hash:
                        errors.append(
                            f"Hash mismatch: {entry.relative_path} "
                            f"(expected {entry.file_hash[:16]}..., "
                            f"got {actual_hash[:16]}...)"
                        )

            except OSError as e:
                errors.append(f"Error reading {entry.relative_path}: {e}")

        return errors
