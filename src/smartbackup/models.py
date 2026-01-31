"""
Models - Data classes for SmartBackup.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple


class FileAction(Enum):
    """Actions that can be applied to files."""

    COPIED = auto()
    UPDATED = auto()
    SKIPPED = auto()
    DELETED = auto()
    ERROR = auto()


@dataclass
class FileInfo:
    """Information about a single file."""

    path: Path
    relative_path: Path
    size: int
    mtime: float
    file_hash: Optional[str] = None

    def needs_update(self, other: "FileInfo", use_hash: bool = False) -> bool:
        """Checks if the file needs to be updated."""
        if self.size != other.size:
            return True
        if self.mtime > other.mtime:
            return True
        if use_hash and self.file_hash and other.file_hash:
            return self.file_hash != other.file_hash
        return False


@dataclass
class BackupResult:
    """Result of a backup operation."""

    total_files: int = 0
    copied_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    deleted_files: int = 0
    errors: int = 0
    total_size: int = 0
    copied_size: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    file_actions: List[Tuple[Path, FileAction, str]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Duration of the backup in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def speed_mbps(self) -> float:
        """Backup speed in MB/s."""
        if self.duration > 0:
            return (self.copied_size / (1024 * 1024)) / self.duration
        return 0.0
