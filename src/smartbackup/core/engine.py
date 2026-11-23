"""
BackupEngine - Core backup engine implementation.
"""

import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

from smartbackup.config import BackupConfig
from smartbackup.core.detector import ChangeDetector
from smartbackup.core.scanner import ExclusionFilter, FileScanner
from smartbackup.manifest.base import Manifest, ManifestManager, SelectiveBackupRecord
from smartbackup.manifest.factory import (
    detect_manifest_manager,
    get_manifest_manager,
    has_manifest,
)
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

    # When True, the engine must not persist any state (manifest save, legacy
    # layout migration, archive creation). Overridden by DryRunBackupEngine.
    is_dry_run = False

    def __init__(self, config: BackupConfig, logger: BackupLogger):
        self.config = config
        self.logger = logger
        self.result = BackupResult(
            backup_mode=config.backup_mode,
            selected_folders=list(config.selected_folders or []),
            selection_metadata=config.selection_metadata,
        )
        self._lock = threading.Lock()
        self._bytes_copied = 0
        self._files_processed = 0
        self._total_bytes = 0
        self._total_files = 0
        self._manifest_manager: Optional[ManifestManager] = None
        self._manifest: Optional[Manifest] = None
        self._migrated_from_manifest_path: Optional[Path] = None
        self._backed_up_files: list[FileInfo] = []
        self._backup_target: Optional[Path] = None

    def run_backup(self) -> BackupResult:
        """Performs the complete backup."""
        self.result = BackupResult(
            start_time=datetime.now(),
            backup_mode=self.config.backup_mode,
            selected_folders=list(self.config.selected_folders or []),
            selection_metadata=self.config.selection_metadata,
        )
        self._backed_up_files = []

        try:
            # 1. Validate paths
            if not self._validate_paths():
                # A failed validation is a real error. Without this, errors
                # stays 0, SmartBackup.run() returns True, the CLI exits 0 and
                # the completion handler reports success although nothing was
                # copied (F11).
                self.result.errors += 1
                return self.result

            # 2. Initialize components
            exclusion_filter = ExclusionFilter(
                self.config.exclusions, self.config.excluded_extensions
            )

            scanner = FileScanner(
                exclusion_filter,
                self.logger,
                use_hash=self.config.use_hash_verification,
                hash_all=self.config.hash_all_files,
                max_size_for_hash=self.config.max_file_size_for_hash,
            )

            # 3. Create backup directory (with per-device subfolder)
            backup_root = self.config.backup_path / self.config.backup_folder_name
            if self.config.device_name:
                # Migrate legacy layout if needed. Never during dry-run: a
                # simulation must not reorganize files on the backup medium.
                if not self.is_dry_run:
                    self._migrate_legacy_layout(backup_root)
                backup_target = backup_root / self.config.device_name
            else:
                backup_target = backup_root
            if not self.is_dry_run:
                backup_target.mkdir(parents=True, exist_ok=True)
            self._backup_target = backup_target

            # 4. Initialize manifest if enabled
            self._migrated_from_manifest_path = None
            if self.config.use_manifest:
                self._manifest_manager = get_manifest_manager(
                    backup_target, self.config.manifest_format
                )
                if self._manifest_manager.exists():
                    self._manifest = self._manifest_manager.load_or_create(
                        self.config.source_path
                    )
                else:
                    existing_other = detect_manifest_manager(backup_target)
                    loaded_other = existing_other.load() if existing_other else None
                    if existing_other and loaded_other is not None:
                        self._manifest = loaded_other
                        self._manifest.format = self._manifest_manager.FORMAT
                        self._migrated_from_manifest_path = existing_other.manifest_path
                        self.logger.info(
                            f"Migrating manifest format from "
                            f"{existing_other.FORMAT.value} to "
                            f"{self._manifest_manager.FORMAT.value}"
                        )
                    else:
                        self._manifest = self._manifest_manager.create(
                            self.config.source_path
                        )
                # Embed device hostname in manifest metadata
                if self.config.device_name:
                    self._manifest.hostname = self.config.device_name
                self.logger.info(
                    f"Manifest ({self._manifest_manager.FORMAT.value}): "
                    f"{self._manifest.total_files} files tracked"
                )

            # 5. Scan source files
            scoped_folders: Optional[list[str]] = (
                list(self.config.selected_folders)
                if self.config.backup_mode == "select" and self.config.selected_folders is not None
                else None
            )
            source_files = scanner.scan(
                self.config.source_path, include_folders=scoped_folders
            )
            if scoped_folders is not None:
                self._record_workflow_step(
                    f"Scoped scan completed across {len(scoped_folders)} selected "
                    f"folder(s): {len(source_files)} file(s) found"
                )

            if not source_files and not self._has_existing_scoped_entries(
                backup_target, scoped_folders
            ):
                self.logger.warning("No files found for backup!")
                return self.result

            # 6. Detect changes - use manifest if available for faster detection
            if self.config.use_manifest and self._manifest_manager and self._manifest:
                diff = self._manifest_manager.diff(
                    source_files, self._manifest, scoped_folders=scoped_folders
                )
                new_files = diff.new_files
                modified_files = diff.modified_files
                deleted_paths = diff.deleted_paths
                self.logger.info(f"Manifest diff: {diff.summary}")
            else:
                # Fall back to traditional change detection
                change_detector = ChangeDetector(self.config.use_hash_verification)
                new_files, modified_files, deleted_files = change_detector.detect_changes(
                    source_files,
                    backup_target,
                    self.logger,
                    scoped_folders=scoped_folders,
                )
                deleted_paths = [str(p) for p in deleted_files] if deleted_files else []

            if scoped_folders is not None:
                self._record_workflow_step(
                    f"Scoped diff completed: +{len(new_files)} new, "
                    f"~{len(modified_files)} modified, -{len(deleted_paths)} deleted "
                    "(unselected folders untouched)"
                )

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

            # Stop the copy progress bar cleanly before post-copy phases
            self.logger.stop_progress()

            # Delete old files
            if deleted_paths:
                self.logger.info(f"Removing {len(deleted_paths)} obsolete files/folders...")
                self._delete_files([backup_target / p for p in deleted_paths])

            # Count skipped
            self.result.skipped_files = len(source_files) - len(new_files) - len(modified_files)

            if scoped_folders is not None:
                phase_label = "Dry-run simulation" if self.is_dry_run else "Backup execution"
                self._record_workflow_step(
                    f"{phase_label} finished: {self.result.copied_files} copied, "
                    f"{self.result.updated_files} updated, {self.result.deleted_files} deleted, "
                    f"{self.result.skipped_files} skipped"
                )

            # 9. Update manifest with backed up files. Skipped during dry-run:
            #    simulated copies/deletes must never advance manifest state,
            #    otherwise a later real run would wrongly skip those files.
            if self.is_dry_run:
                if self.config.use_manifest:
                    self.logger.info("Dry-run: manifest left unchanged")
            elif self.config.use_manifest and self._manifest_manager and self._manifest:
                self._manifest = self._manifest_manager.update_from_backup(
                    self._manifest, self._backed_up_files, deleted_paths=deleted_paths
                )
                if self.config.backup_mode == "select" and scoped_folders is not None:
                    now = datetime.now()
                    run_id = f"{now:%Y%m%d_%H%M%S}_#{self._manifest.backup_count}"
                    meta = self.config.selection_metadata
                    self._record_workflow_step(
                        f"Manifest ({self._manifest_manager.FORMAT.value}) updated "
                        f"with SelectiveBackupRecord {run_id}"
                    )
                    record = SelectiveBackupRecord(
                        run_id=run_id,
                        timestamp=now,
                        command_option=meta.command_option if meta else "--select",
                        scope="folders",
                        source_root=(
                            meta.source_root if meta and meta.source_root else str(self.config.source_path)
                        ),
                        selected_folders=list(scoped_folders),
                        available_folders_count=(
                            len(meta.available_folders) if meta else len(scoped_folders)
                        ),
                        files_scanned=self.result.total_files,
                        files_copied=self.result.copied_files,
                        files_updated=self.result.updated_files,
                        files_deleted=self.result.deleted_files,
                        files_skipped=self.result.skipped_files,
                        bytes_copied=self.result.copied_size,
                        duration_seconds=round(self.result.duration, 2),
                        workflow_steps=list(meta.workflow_steps) if meta else [],
                    )
                    self._manifest.add_selective_backup(record)
                else:
                    self._manifest.last_backup_mode = "full"
                    self._manifest.last_selected_folders = []

                if self._manifest_manager.save(self._manifest):
                    if (
                        self._migrated_from_manifest_path is not None
                        and self._migrated_from_manifest_path
                        != self._manifest_manager.manifest_path
                    ):
                        try:
                            self._migrated_from_manifest_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        self._migrated_from_manifest_path = None
                    self.logger.success(
                        f"Manifest updated: {self._manifest.total_files} files tracked"
                    )
                else:
                    self.logger.warning("Failed to save manifest")

            # 10. Compress backup if requested
            if self.config.compress_format:
                if self.is_dry_run:
                    self.logger.info(
                        f"Dry-run: skipping {self.config.compress_format} archive creation"
                    )
                else:
                    from smartbackup.core.compressor import BackupCompressor

                    compressor = BackupCompressor(self.logger)
                    archive_name = compressor.get_archive_name(
                        self.config.device_name or "backup",
                        self.config.compress_format,
                    )
                    archive_path = backup_root / archive_name
                    compressor.compress(
                        backup_target, archive_path, self.config.compress_format
                    )

        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            self.result.errors += 1

        finally:
            self.logger.stop_progress()
            self.result.end_time = datetime.now()

            # Write log file (skipped during dry-run to guarantee zero target writes).
            # Logging is best-effort: a vanished or unwritable medium must not turn
            # a handled failure into an uncaught exception, nor recreate a target
            # directory that failed validation.
            if self.config.log_to_file and not self.is_dry_run:
                try:
                    self._write_log_file()
                except OSError as e:
                    self.logger.warning(f"Could not write log file: {e}")

        return self.result

    def _record_workflow_step(self, step: str) -> None:
        """Append a workflow step to selection_metadata when tracing --select runs."""
        if self.config.selection_metadata is not None:
            self.config.selection_metadata.workflow_steps.append(step)

    def _has_existing_scoped_entries(
        self,
        backup_target: Path,
        scoped_folders: Optional[list[str]],
    ) -> bool:
        """Check whether any previously backed-up files exist within selected folders."""
        if not scoped_folders:
            return False

        scoped_set = set(scoped_folders)
        if self.config.use_manifest and self._manifest is not None:
            for rel_path in self._manifest.entries:
                parts = Path(rel_path.replace("\\", "/")).parts
                if len(parts) >= 2 and parts[0] in scoped_set:
                    return True
            return False

        if backup_target.exists():
            for folder_name in scoped_folders:
                folder_backup = backup_target / folder_name
                if folder_backup.exists() and folder_backup.is_dir():
                    if any(p.is_file() for p in folder_backup.rglob("*")):
                        return True
        return False

    def _migrate_legacy_layout(self, backup_root: Path) -> None:
        """Migrate legacy flat layout to per-device subfolder structure.

        If Documents-Backup/ contains files directly (legacy layout), move them
        into a device-named subfolder so multiple devices can coexist.
        """
        if not backup_root.exists():
            return  # Fresh backup, no migration needed

        # Check for legacy indicators at the root level
        legacy_logs = backup_root / "_backup_logs"
        has_root_files = any(item.is_file() for item in backup_root.iterdir())

        if not (has_manifest(backup_root) or legacy_logs.exists() or has_root_files):
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

            try:
                item.rename(temp_dir / item.name)
            except (FileNotFoundError, OSError) as e:
                self.logger.warning(f"Could not migrate {item.name}: {e}")

        # Rename temp dir to device folder
        try:
            temp_dir.rename(device_folder)
        except OSError as e:
            self.logger.error(f"Failed to finalize migration to {device_name}: {e}")
            # Try to roll back some files from temp_dir if possible,
            # but usually this is a fatal collision or permission issue.
            return

        self.logger.success("Migration complete!")

    def _validate_paths(self) -> bool:
        """Validates source and target paths."""
        if not self.config.source_path.exists():
            self.logger.error(f"Source directory does not exist: {self.config.source_path}")
            return False

        if not self.config.backup_path.exists():
            self.logger.error(f"Backup medium not found: {self.config.backup_path}")
            return False

        # Check write permissions via DeviceDetector (unified writability probe)
        from smartbackup.platform.devices import DeviceDetector

        if not DeviceDetector(self.logger).validate_device(self.config.backup_path):
            self.logger.error(f"No write permissions on backup medium: {self.config.backup_path}")
            return False

        return True

    def _copy_files(self, files: list[FileInfo], backup_target: Path, action: FileAction) -> None:
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
    ) -> tuple[bool, str]:
        """Copies a single file, handling type collisions."""
        try:
            dest_path = backup_target / file_info.relative_path

            # Collision Handling 1: Parent is a file, but needs to be a directory
            if dest_path.parent.exists() and not dest_path.parent.is_dir():
                self.logger.warning(f"Collision: {dest_path.parent} is a file, but should be a directory. Deleting...")
                dest_path.parent.unlink()

            # Create target directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Collision Handling 2: Target is a directory, but needs to be a file
            if dest_path.exists() and dest_path.is_dir():
                self.logger.warning(f"Collision: {dest_path} is a directory, but should be a file. Deleting...")
                shutil.rmtree(dest_path)

            # Copy file with metadata, with fallback for file systems that don't support all attributes
            try:
                shutil.copy2(file_info.path, dest_path)
            except (OSError, PermissionError) as e:
                # Fallback: basic copy + manual mtime preservation if copy2 fails (common on ExFAT/FAT32)
                self.logger.warning(f"Full metadata copy failed for {file_info.relative_path}: {e}. Falling back to basic copy.")
                shutil.copy(file_info.path, dest_path)

                # Try to preserve at least the modification time
                try:
                    import os
                    os.utime(dest_path, (file_info.mtime, file_info.mtime))
                except Exception as ut_e:
                    self.logger.warning(f"Could not preserve timestamp for {file_info.relative_path}: {ut_e}")

            return True, "OK"

        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, f"OS error: {e.errno}"
        except Exception as e:
            return False, str(e)

    def _delete_files(self, files: list[Path]) -> None:
        """Deletes files/directories that no longer exist in source."""
        for path in files:
            if not path.exists():
                continue
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                    self.result.deleted_files += 1
                    self.logger.file_action(FileAction.DELETED, path)
                elif path.is_dir():
                    shutil.rmtree(path)
                    self.result.deleted_files += 1
                    self.logger.file_action(FileAction.DELETED, path)
            except Exception as e:
                self.logger.error(f"Delete failed: {path} - {e}")

    def _write_log_file(self) -> None:
        """Writes detailed log to the backup medium."""
        if not self.config.backup_path.exists():
            # Never create the medium: if it is missing, path validation has
            # already failed and there is nowhere legitimate to write.
            self.logger.warning(
                f"Log file skipped: backup medium not available ({self.config.backup_path})"
            )
            return

        if self._backup_target is None:
            log_dir = self.config.backup_path / self.config.backup_folder_name / "_backup_logs"
        else:
            log_dir = self._backup_target / "_backup_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"backup_{timestamp}.log"

        self.logger.log_file = log_file

        mode_label = (
            "Selective (--select)" if self.config.backup_mode == "select" else "Full"
        )

        selective_section = ""
        if self.config.backup_mode == "select":
            meta = self.config.selection_metadata
            selected_list = list(self.config.selected_folders or [])
            available_count = (
                len(meta.available_folders) if meta else len(selected_list)
            )
            excluded_count = meta.excluded_folders_count if meta else 0
            source_root = (
                meta.source_root if meta and meta.source_root else str(self.config.source_path)
            )
            selected_at_str = (
                meta.selected_at.strftime("%Y-%m-%d %H:%M:%S")
                if meta
                else self.result.start_time.strftime("%Y-%m-%d %H:%M:%S")
            )
            command_opt = meta.command_option if meta else "--select"
            workflow_steps = list(meta.workflow_steps) if meta else []

            folder_lines = "\n".join(f"    [x] {name}/" for name in selected_list) or "    (none)"
            if workflow_steps:
                trace_lines = "\n".join(
                    f"    {idx}. {step}" for idx, step in enumerate(workflow_steps, start=1)
                )
            else:
                trace_lines = "    1. Selective backup executed"

            selective_section = (
                f"\n{'=' * 70}\n"
                f"                SELECTIVE BACKUP ({command_opt})\n"
                f"{'=' * 70}\n"
                f"  Command Option:    {command_opt}\n"
                f"  Scope:             folders (top-level only)\n"
                f"  Source Root:       {source_root}\n"
                f"  Available Folders: {available_count}\n"
                f"  Selected Folders:  {len(selected_list)} of {available_count}\n"
                f"  Excluded Folders:  {excluded_count}\n"
                f"  Selected At:       {selected_at_str}\n\n"
                f"  Selected Folder List:\n"
                f"{folder_lines}\n\n"
                f"  SELECTIVE WORKFLOW TRACE:\n"
                f"{trace_lines}\n"
                f"{'=' * 70}\n"
            )

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
  Mode:       {mode_label}
  Timestamp:  {self.result.start_time.strftime("%Y-%m-%d %H:%M:%S")}
{selective_section}
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
    Performs all analyses without writing anything to the target drive
    (no directories created, no files copied/deleted, no manifest writes,
    no layout migration, no archives, and no log files).
    """

    is_dry_run = True

    def _copy_single_file(
        self, file_info: FileInfo, backup_target: Path, action: FileAction
    ) -> tuple[bool, str]:
        """Simulates copying without actual file operation."""
        # Short pause for simulation
        time.sleep(0.001)
        return True, "DRY-RUN"

    def _delete_files(self, files: list[Path]) -> None:
        """Simulates deletion."""
        for path in files:
            self.result.deleted_files += 1
            self.logger.file_action(FileAction.DELETED, path, "DRY-RUN")
