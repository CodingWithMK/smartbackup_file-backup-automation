"""
ChangeDetector - Detects changes between source and target files.
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple

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
        source_files: Dict[Path, FileInfo],
        backup_path: Path,
        logger: BackupLogger,
    ) -> Tuple[List[FileInfo], List[FileInfo], List[Path]]:
        """
        Compares source and backup files.

        Returns:
            Tuple of (new_files, modified_files, files_to_delete)
        """
        logger.section("Analyzing changes...")

        new_files: List[FileInfo] = []
        modified_files: List[FileInfo] = []
        deleted_files: List[Path] = []

        # Scan existing backup files
        existing_backup_files: Set[Path] = set()
        if backup_path.exists():
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
