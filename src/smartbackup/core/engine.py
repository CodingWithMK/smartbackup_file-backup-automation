"""
BackupEngine - Core backup engine implementation.
"""

import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from smartbackup.config import BackupConfig
from smartbackup.core.detector import ChangeDetector
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.manifest.base import Manifest, ManifestManager
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.models import BackupResult, FileAction, FileInfo
from smartbackup.ui.logger import BackupLogger


class BackupEngine:
    """
    Main engine for the backup system.

    Features:
    - Multithreaded copying
    - Progress monitoring
    - Error handling and retry
    - Atomic operations
    - Manifest-based incremental backups
    """

    def __init__(self, config: BackupConfig, logger: BackupLogger):
        self.config = config
        self.logger = logger
        self.result = BackupResult()
        self._lock = threading.Lock()
        self._bytes_copied = 0
        self._files_processed = 0
        self._total_bytes = 0
        self._total_files = 0
        self._manifest_manager: Optional[ManifestManager] = None
        self._manifest: Optional[Manifest] = None
        self._backed_up_files: List[FileInfo] = []
        self._backup_target: Optional[Path] = None

    def run_backup(self) -> BackupResult:
        """Performs the complete backup."""
        self.result = BackupResult(start_time=datetime.now())
        self._backed_up_files = []

        try:
            # 1. Validate paths
            if not self._validate_paths():
                return self.result

            # 2. Initialize components
            exclusion_filter = ExclusionFilter(
                self.config.exclusions, self.config.excluded_extensions
            )

            scanner = FileScanner(
                exclusion_filter,
                self.logger,
                self.config.use_hash_verification,
                self.config.min_file_size_for_hash,
            )

            # 3. Create backup directory (with per-device subfolder)
            backup_root = self.config.backup_path / self.config.backup_folder_name
            if self.config.device_name:
                # Migrate legacy layout if needed
                self._migrate_legacy_layout(backup_root)
                backup_target = backup_root / self.config.device_name
            else:
                backup_target = backup_root
            backup_target.mkdir(parents=True, exist_ok=True)
            self._backup_target = backup_target

            # 4. Initialize manifest if enabled
            if self.config.use_manifest:
                self._manifest_manager = JsonManifestManager(backup_target)
                self._manifest = self._manifest_manager.load_or_create(self.config.source_path)
                # Embed device hostname in manifest metadata
                if self.config.device_name:
                    self._manifest.hostname = self.config.device_name
                self.logger.info(f"Manifest: {self._manifest.total_files} files tracked")

            # 5. Scan source files
            source_files = scanner.scan(self.config.source_path)

            if not source_files:
                self.logger.warning("No files found for backup!")
                return self.result

            # 6. Detect changes - use manifest if available for faster detection
            if self.config.use_manifest and self._manifest_manager and self._manifest:
                diff = self._manifest_manager.diff(source_files, self._manifest)
                new_files = diff.new_files
                modified_files = diff.modified_files
                deleted_paths = diff.deleted_paths
                self.logger.info(f"Manifest diff: {diff.summary}")
            else:
                # Fall back to traditional change detection
                change_detector = ChangeDetector(self.config.use_hash_verification)
                new_files, modified_files, deleted_files = change_detector.detect_changes(
                    source_files, backup_target, self.logger
                )
                deleted_paths = [str(p) for p in deleted_files] if deleted_files else []

            # 7. Calculate total sizes
            self._total_files = len(new_files) + len(modified_files)
            self._total_bytes = sum(f.size for f in new_files + modified_files)
            self.result.total_files = len(source_files)
            self.result.total_size = sum(f.size for f in source_files.values())

            # 8. Perform backup
            self.logger.section("Starting backup operation...")

            # Copy new files
            if new_files:
                self._copy_files(new_files, backup_target, FileAction.COPIED)

            # Update modified files
            if modified_files:
                self._copy_files(modified_files, backup_target, FileAction.UPDATED)

            # Optional: Delete old files
            # (Commented out for safety - can be enabled)
            # if deleted_paths:
            #     self._delete_files_by_path(deleted_paths, backup_target)

            # Count skipped
            self.result.skipped_files = len(source_files) - len(new_files) - len(modified_files)

            # 9. Update manifest with backed up files
            if self.config.use_manifest and self._manifest_manager and self._manifest:
                self._manifest = self._manifest_manager.update_from_backup(
                    self._manifest, self._backed_up_files, deleted_paths=None
                )
                if self._manifest_manager.save(self._manifest):
                    self.logger.success(
                        f"Manifest updated: {self._manifest.total_files} files tracked"
                    )
                else:
                    self.logger.warning("Failed to save manifest")

        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            self.result.errors += 1

        finally:
            self.result.end_time = datetime.now()

            # Write log file
            if self.config.log_to_file:
                self._write_log_file()

        return self.result

    def _migrate_legacy_layout(self, backup_root: Path) -> None:
        """Migrate legacy flat layout to per-device subfolder structure.

        If Documents-Backup/ contains files directly (legacy layout), move them
        into a device-named subfolder so multiple devices can coexist.
        """
        if not backup_root.exists():
            return  # Fresh backup, no migration needed

        # Check for legacy indicators at the root level
        legacy_manifest = backup_root / ".smartbackup_manifest.json"
        legacy_logs = backup_root / "_backup_logs"
        has_root_files = any(item.is_file() for item in backup_root.iterdir())

        if not (legacy_manifest.exists() or legacy_logs.exists() or has_root_files):
            return  # Already using new layout or empty

        device_name = self.config.device_name
        device_folder = backup_root / device_name

        # If device folder already exists, skip migration
        if device_folder.exists():
            return

        self.logger.info("Detected legacy backup layout. Migrating to per-device structure...")
        self.logger.info(f"Moving existing backup into: {device_name}/")

        # Create a temporary directory for the move
        temp_name = f".migration_temp_{int(time.time())}"
        temp_dir = backup_root / temp_name
        temp_dir.mkdir()

        # Move all items (except the temp dir itself) into the temp dir
        for item in backup_root.iterdir():
            if item.name == temp_name:
                continue
            item.rename(temp_dir / item.name)

        # Rename temp dir to device folder
        temp_dir.rename(device_folder)

        self.logger.success("Migration complete!")

    def _validate_paths(self) -> bool:
        """Validates source and target paths."""
        if not self.config.source_path.exists():
            self.logger.error(f"Source directory does not exist: {self.config.source_path}")
            return False

        if not self.config.backup_path.exists():
            self.logger.error(f"Backup medium not found: {self.config.backup_path}")
            return False

        # Check write permissions
        try:
            test_file = self.config.backup_path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            self.logger.error(f"No write permissions on backup medium: {e}")
            return False

        return True

    def _copy_files(self, files: List[FileInfo], backup_target: Path, action: FileAction) -> None:
        """Copies files with multithreading."""
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._copy_single_file, f, backup_target, action): f for f in files
            }

            for future in as_completed(futures):
                file_info = futures[future]
                try:
                    success, message = future.result()

                    with self._lock:
                        self._files_processed += 1

                        if success:
                            self._bytes_copied += file_info.size
                            self._backed_up_files.append(file_info)  # Track for manifest

                            if action == FileAction.COPIED:
                                self.result.copied_files += 1
                            else:
                                self.result.updated_files += 1

                            self.result.copied_size += file_info.size
                            self.result.file_actions.append(
                                (file_info.relative_path, action, message)
                            )

                            self.logger.file_action(
                                action,
                                file_info.relative_path,
                                f"{file_info.size / 1024:.1f} KB",
                            )
                        else:
                            self.result.errors += 1
                            self.result.file_actions.append(
                                (file_info.relative_path, FileAction.ERROR, message)
                            )
                            self.logger.file_action(
                                FileAction.ERROR, file_info.relative_path, message
                            )

                        # Update progress
                        self.logger.progress(
                            self._files_processed,
                            self._total_files,
                            str(file_info.relative_path.name),
                            self._bytes_copied,
                            self._total_bytes,
                        )

                except Exception as e:
                    with self._lock:
                        self.result.errors += 1
                    self.logger.error(f"Error at {file_info.path}: {e}")

    def _copy_single_file(
        self, file_info: FileInfo, backup_target: Path, action: FileAction
    ) -> Tuple[bool, str]:
        """Copies a single file."""
        try:
            dest_path = backup_target / file_info.relative_path

            # Create target directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file with metadata
            shutil.copy2(file_info.path, dest_path)

            return True, "OK"

        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, f"OS error: {e.errno}"
        except Exception as e:
            return False, str(e)

    def _delete_files(self, files: List[Path]) -> None:
        """Deletes files that no longer exist in source."""
        for path in files:
            try:
                if path.is_file():
                    path.unlink()
                    self.result.deleted_files += 1
                    self.logger.file_action(FileAction.DELETED, path)
            except Exception as e:
                self.logger.error(f"Delete failed: {path} - {e}")

    def _write_log_file(self) -> None:
        """Writes detailed log to the backup medium."""
        if self._backup_target is None:
            log_dir = self.config.backup_path / self.config.backup_folder_name / "_backup_logs"
        else:
            log_dir = self._backup_target / "_backup_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"backup_{timestamp}.log"

        self.logger.log_file = log_file

        # Write header
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(
                f"""
{"=" * 70}
                    BACKUP LOG - {timestamp}
{"=" * 70}

CONFIGURATION:
  Source:     {self.config.source_path}
  Target:     {self._backup_target or (self.config.backup_path / self.config.backup_folder_name)}
  Timestamp:  {self.result.start_time.strftime("%Y-%m-%d %H:%M:%S")}

SUMMARY:
  Total Files:            {self.result.total_files}
  Copied Files:           {self.result.copied_files}
  Updated Files:          {self.result.updated_files}
  Skipped Files:          {self.result.skipped_files}
  Errors:                 {self.result.errors}

  Total Size:            {self.result.total_size / (1024 * 1024):.2f} MB
  Copied Size:           {self.result.copied_size / (1024 * 1024):.2f} MB
  Duration:              {self.result.duration:.1f} seconds
  Speed:                 {self.result.speed_mbps:.2f} MB/s

{"=" * 70}
                         FILE ACTIONS
{"=" * 70}

"""
            )

            # Write actions
            for path, action, message in self.result.file_actions:
                action_str = {
                    FileAction.COPIED: "[COPIED]     ",
                    FileAction.UPDATED: "[UPDATED]    ",
                    FileAction.SKIPPED: "[SKIPPED]    ",
                    FileAction.DELETED: "[DELETED]    ",
                    FileAction.ERROR: "[ERROR]      ",
                }.get(action, "[?]")

                f.write(f"{action_str} {path}")
                if message and message != "OK":
                    f.write(f" ({message})")
                f.write("\n")

        self.logger.flush_to_file()
        self.logger.success(f"Log file saved: {log_file}")


class DryRunBackupEngine(BackupEngine):
    """
    Backup engine for simulation mode.
    Performs all analyses but does not copy files.
    """

    def _copy_single_file(
        self, file_info: FileInfo, backup_target: Path, action: FileAction
    ) -> Tuple[bool, str]:
        """Simulates copying without actual file operation."""
        # Short pause for simulation
        time.sleep(0.001)
        return True, "DRY-RUN"

    def _delete_files(self, files: List[Path]) -> None:
        """Simulates deletion."""
        for path in files:
            self.result.deleted_files += 1
            self.logger.file_action(FileAction.DELETED, path, "DRY-RUN")
