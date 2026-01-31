"""
RestoreEngine - Core restore engine implementation.
"""

import fnmatch
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple

from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.models import FileAction
from smartbackup.ui.logger import BackupLogger


class ConflictResolution(Enum):
    """How to handle file conflicts during restore."""

    SKIP = auto()  # Skip existing files
    OVERWRITE = auto()  # Overwrite existing files
    RENAME = auto()  # Rename restored files
    NEWER = auto()  # Only overwrite if backup is newer


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    total_files: int = 0
    restored_files: int = 0
    skipped_files: int = 0
    overwritten_files: int = 0
    errors: int = 0
    total_size: int = 0
    restored_size: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    file_actions: List[Tuple[Path, FileAction, str]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Duration of the restore in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def speed_mbps(self) -> float:
        """Restore speed in MB/s."""
        if self.duration > 0:
            return (self.restored_size / (1024 * 1024)) / self.duration
        return 0.0


class RestoreEngine:
    """
    Engine for restoring files from backup.

    Features:
    - Restore full backup or filtered files
    - Conflict resolution (skip, overwrite, rename)
    - Dry-run mode for preview
    - Manifest-aware restore
    """

    def __init__(
        self,
        backup_path: Path,
        target_path: Optional[Path] = None,
        logger: Optional[BackupLogger] = None,
        backup_folder: str = "Documents-Backup",
    ):
        """
        Initialize restore engine.

        Args:
            backup_path: Path to the backup location (parent of backup folder)
            target_path: Where to restore files (default: original source location)
            logger: Logger for output
            backup_folder: Name of the backup folder
        """
        self.backup_path = backup_path
        self.backup_folder = backup_folder
        self.backup_target = backup_path / backup_folder
        self.target_path = target_path
        self.logger = logger or BackupLogger(verbose=True)
        self.result = RestoreResult()
        self._lock = threading.Lock()
        self._manifest_manager = JsonManifestManager(self.backup_target)

    def restore(
        self,
        patterns: Optional[List[str]] = None,
        overwrite: bool = False,
        dry_run: bool = False,
        max_workers: int = 4,
    ) -> RestoreResult:
        """
        Perform the restore operation.

        Args:
            patterns: Optional glob patterns to filter files
            overwrite: Whether to overwrite existing files
            dry_run: Preview without actual restore

        Returns:
            RestoreResult with statistics
        """
        self.result = RestoreResult(start_time=datetime.now())

        try:
            # 1. Validate backup directory
            if not self.backup_target.exists():
                self.logger.error(f"Backup directory not found: {self.backup_target}")
                self.result.errors = 1
                return self.result

            # 2. Determine target path
            if self.target_path is None:
                # Try to get original source from manifest
                manifest = self._manifest_manager.load()
                if manifest and manifest.source:
                    self.target_path = Path(manifest.source)
                    self.logger.info(f"Restoring to original source: {self.target_path}")
                else:
                    self.logger.error("No target path specified and no manifest source found")
                    self.result.errors = 1
                    return self.result

            # 3. Collect files to restore
            files_to_restore = self._collect_files(patterns)

            if not files_to_restore:
                self.logger.warning("No files to restore!")
                return self.result

            self.result.total_files = len(files_to_restore)
            self.result.total_size = sum(f.stat().st_size for f in files_to_restore)

            self.logger.info(f"Found {len(files_to_restore)} files to restore")
            self.logger.info(f"Total size: {self.result.total_size / (1024 * 1024):.2f} MB")

            # 4. Perform restore
            self.logger.section("Starting restore operation...")

            conflict_resolution = (
                ConflictResolution.OVERWRITE if overwrite else ConflictResolution.SKIP
            )

            self._restore_files(files_to_restore, conflict_resolution, dry_run, max_workers)

        except Exception as e:
            self.logger.error(f"Restore error: {e}")
            self.result.errors += 1

        finally:
            self.result.end_time = datetime.now()
            self._print_summary()

        return self.result

    def _collect_files(self, patterns: Optional[List[str]] = None) -> List[Path]:
        """
        Collect files to restore based on patterns.

        Args:
            patterns: Optional glob patterns to filter files

        Returns:
            List of file paths to restore
        """
        files = []

        for path in self.backup_target.rglob("*"):
            if path.is_file():
                # Skip internal files
                relative = path.relative_to(self.backup_target)
                if str(relative).startswith("_backup_logs") or str(relative).startswith(
                    ".smartbackup"
                ):
                    continue

                # Apply pattern filter if specified
                if patterns:
                    match = False
                    for pattern in patterns:
                        if fnmatch.fnmatch(str(relative), pattern):
                            match = True
                            break
                    if not match:
                        continue

                files.append(path)

        return files

    def _restore_files(
        self,
        files: List[Path],
        conflict_resolution: ConflictResolution,
        dry_run: bool,
        max_workers: int,
    ) -> None:
        """Restore files with multithreading."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._restore_single_file, f, conflict_resolution, dry_run): f
                for f in files
            }

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    success, action, message = future.result()
                    relative = file_path.relative_to(self.backup_target)

                    with self._lock:
                        if success:
                            if action == FileAction.COPIED:
                                self.result.restored_files += 1
                                self.result.restored_size += file_path.stat().st_size
                            elif action == FileAction.UPDATED:
                                self.result.overwritten_files += 1
                                self.result.restored_size += file_path.stat().st_size
                            elif action == FileAction.SKIPPED:
                                self.result.skipped_files += 1
                        else:
                            self.result.errors += 1

                        self.result.file_actions.append((relative, action, message))
                        self.logger.file_action(action, relative, message)

                except Exception as e:
                    with self._lock:
                        self.result.errors += 1
                    self.logger.error(f"Error restoring {file_path}: {e}")

    def _restore_single_file(
        self,
        source_path: Path,
        conflict_resolution: ConflictResolution,
        dry_run: bool,
    ) -> Tuple[bool, FileAction, str]:
        """
        Restore a single file.

        Args:
            source_path: Path to the backup file
            conflict_resolution: How to handle conflicts
            dry_run: Preview without actual restore

        Returns:
            Tuple of (success, action, message)
        """
        try:
            relative = source_path.relative_to(self.backup_target)
            target_path = self.target_path
            if target_path is None:
                return False, FileAction.ERROR, "No target path set"
            target = target_path / relative

            # Check for existing file
            if target.exists():
                if conflict_resolution == ConflictResolution.SKIP:
                    return True, FileAction.SKIPPED, "File exists"
                elif conflict_resolution == ConflictResolution.NEWER:
                    source_mtime = source_path.stat().st_mtime
                    target_mtime = target.stat().st_mtime
                    if source_mtime <= target_mtime:
                        return True, FileAction.SKIPPED, "Target is newer"

            if dry_run:
                if target.exists():
                    return True, FileAction.UPDATED, "DRY-RUN"
                return True, FileAction.COPIED, "DRY-RUN"

            # Create target directory
            target.parent.mkdir(parents=True, exist_ok=True)

            # Determine action
            action = FileAction.UPDATED if target.exists() else FileAction.COPIED

            # Copy file with metadata (atomic pattern)
            temp_path = target.with_suffix(target.suffix + ".tmp")
            try:
                shutil.copy2(source_path, temp_path)
                temp_path.replace(target)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise

            return True, action, "OK"

        except PermissionError:
            return False, FileAction.ERROR, "Permission denied"
        except OSError as e:
            return False, FileAction.ERROR, f"OS error: {e.errno}"
        except Exception as e:
            return False, FileAction.ERROR, str(e)

    def _print_summary(self) -> None:
        """Print restore summary."""
        print("\n" + "=" * 70)
        print("RESTORE SUMMARY")
        print("=" * 70)
        print(f"  Total Files:      {self.result.total_files:,}")
        print(f"  Restored:         {self.result.restored_files:,}")
        print(f"  Overwritten:      {self.result.overwritten_files:,}")
        print(f"  Skipped:          {self.result.skipped_files:,}")
        print(f"  Errors:           {self.result.errors:,}")
        print(f"  Restored Size:    {self.result.restored_size / (1024 * 1024):.2f} MB")
        print(f"  Duration:         {self.result.duration:.1f} seconds")
        print(f"  Speed:            {self.result.speed_mbps:.2f} MB/s")
        print("=" * 70 + "\n")

        if self.result.errors == 0:
            self.logger.success("Restore completed successfully!")
        else:
            self.logger.warning(f"Restore completed with {self.result.errors} errors")

    def list_files(self, patterns: Optional[List[str]] = None) -> List[Tuple[Path, int]]:
        """
        List files available in backup.

        Args:
            patterns: Optional glob patterns to filter files

        Returns:
            List of (relative_path, size) tuples
        """
        files = self._collect_files(patterns)
        return [(f.relative_to(self.backup_target), f.stat().st_size) for f in files]

    def get_manifest_info(self) -> Optional[dict]:
        """
        Get information from manifest.

        Returns:
            Dictionary with manifest info or None
        """
        manifest = self._manifest_manager.load()
        if manifest is None:
            return None

        return {
            "source": manifest.source,
            "created": manifest.created.isoformat(),
            "updated": manifest.updated.isoformat(),
            "backup_count": manifest.backup_count,
            "total_files": manifest.total_files,
            "total_size": manifest.total_size,
        }
