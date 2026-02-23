"""
Manifest Base - Base classes for manifest tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from smartbackup.models import FileInfo


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
        except (OSError, IOError):
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
        if file_info.mtime > self.mtime:
            return True

        # If both have hashes, compare them
        if file_info.file_hash and self.file_hash:
            return file_info.file_hash != self.file_hash

        return False


@dataclass
class Manifest:
    """
    Represents a complete backup manifest.

    Contains metadata about the backup and all file entries.
    """

    version: int = 1
    format: ManifestFormat = ManifestFormat.JSON
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)
    source: str = ""
    hostname: str = ""  # Device hostname for identification
    backup_count: int = 0
    entries: Dict[str, ManifestEntry] = field(default_factory=dict)

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
            "backup_count": self.backup_count,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "files": {path: entry.to_dict() for path, entry in self.entries.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        """Create manifest from dictionary."""
        manifest = cls(
            version=data.get("version", 1),
            format=ManifestFormat(data.get("format", "json")),
            created=datetime.fromisoformat(data.get("created", datetime.now().isoformat())),
            updated=datetime.fromisoformat(data.get("updated", datetime.now().isoformat())),
            source=data.get("source", ""),
            hostname=data.get("hostname", ""),
            backup_count=data.get("backup_count", 0),
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

    new_files: List[FileInfo] = field(default_factory=list)
    modified_files: List[FileInfo] = field(default_factory=list)
    deleted_paths: List[str] = field(default_factory=list)
    unchanged_files: List[FileInfo] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.new_files or self.modified_files or self.deleted_paths)

    @property
    def files_to_backup(self) -> List[FileInfo]:
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

    def __init__(self, backup_path: Path):
        """
        Initialize manifest manager.

        Args:
            backup_path: Path to the backup directory
        """
        self.backup_path = backup_path

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
            source=str(source_path),
            backup_count=0,
        )

    def diff(
        self, source_files: Dict[Path, FileInfo], manifest: Optional[Manifest] = None
    ) -> ManifestDiff:
        """
        Compare source files against manifest to find changes.

        Args:
            source_files: Dictionary of source files (path -> FileInfo)
            manifest: Existing manifest (loads from storage if None)

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
        seen_paths: set = set()

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

        # Find deleted files (in manifest but not in source)
        for relative_path in manifest.entries:
            if relative_path not in seen_paths:
                result.deleted_paths.append(relative_path)

        return result

    def update_from_backup(
        self,
        manifest: Manifest,
        backed_up_files: List[FileInfo],
        deleted_paths: Optional[List[str]] = None,
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

    def verify(self, manifest: Manifest, backup_target: Path) -> List[str]:
        """
        Verify backup files against manifest.

        Args:
            manifest: The manifest to verify against
            backup_target: Path to the backup directory

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

            except OSError as e:
                errors.append(f"Error reading {entry.relative_path}: {e}")

        return errors
