"""
ChangeDetector - Detects changes between source and target files.
"""

from pathlib import Path
from typing import Optional

from smartbackup.models import FileInfo
from smartbackup.ui.logger import BackupLogger


class ChangeDetector:
    """
    Detects changes between source and target files.

    Strategies:
    - Size comparison (fast)
    - Timestamp comparison (fast)
    - Hash comparison (accurate, optional)
    """

    def __init__(self, use_hash: bool = False):
        self.use_hash = use_hash

    def detect_changes(
        self,
        source_files: dict[Path, FileInfo],
        backup_path: Path,
        logger: BackupLogger,
        scoped_folders: Optional[list[str]] = None,
    ) -> tuple[list[FileInfo], list[FileInfo], list[Path]]:
        """
        Compares source and backup files.

        Args:
            source_files: Mapping of root-relative paths to source FileInfo.
            backup_path: Target backup root directory.
            logger: Logger for progress/info messages.
            scoped_folders: Optional list of top-level folder names to scope
                deletion detection to (used by ``--select``). Backup files
                outside these folders are never marked for deletion.

        Returns:
            Tuple of (new_files, modified_files, files_to_delete)
        """
        logger.section("Analyzing changes...")

        new_files: list[FileInfo] = []
        modified_files: list[FileInfo] = []
        deleted_files: list[Path] = []

        # Scan existing backup files (scoped to selected folders if provided)
        existing_backup_files: set[Path] = set()
        if backup_path.exists():
            if scoped_folders is not None:
                for folder_name in scoped_folders:
                    folder_backup_path = backup_path / folder_name
                    if folder_backup_path.exists() and folder_backup_path.is_dir():
                        for path in folder_backup_path.rglob("*"):
                            if path.is_file():
                                relative = path.relative_to(backup_path)
                                existing_backup_files.add(relative)
            else:
                for path in backup_path.rglob("*"):
                    if path.is_file():
                        relative = path.relative_to(backup_path)
                        existing_backup_files.add(relative)

        # Compare source files with backup
        for relative_path, source_info in source_files.items():
            backup_file = backup_path / relative_path

            if not backup_file.exists():
                new_files.append(source_info)
            else:
                # Check if modified
                try:
                    backup_stat = backup_file.stat()
                    backup_info = FileInfo(
                        path=backup_file,
                        relative_path=relative_path,
                        size=backup_stat.st_size,
                        mtime=backup_stat.st_mtime,
                    )

                    if source_info.needs_update(backup_info, self.use_hash):
                        modified_files.append(source_info)

                except Exception:
                    # On error: mark as modified
                    modified_files.append(source_info)

            # Remove from existing
            if relative_path in existing_backup_files:
                existing_backup_files.remove(relative_path)

        # Remaining files in backup are deleted
        deleted_files = [backup_path / p for p in existing_backup_files]

        logger.info(
            f"Analysis completed: {len(new_files)} new, "
            f"{len(modified_files)} modified, "
            f"{len(deleted_files)} files to delete"
        )

        return new_files, modified_files, deleted_files
