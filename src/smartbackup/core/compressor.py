"""
BackupCompressor - Handles compression of backup directories into archives.

Supports zip and tar.gz formats using Python stdlib (zipfile, tarfile).
"""

import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from smartbackup.ui.logger import BackupLogger

# Supported compression formats
SUPPORTED_FORMATS = ("zip", "tar.gz")


class BackupCompressor:
    """Handles compression of backup directories into archives.

    Creates a single archive from a backup directory. Supports zip and tar.gz
    formats. Uses atomic writes (temp file + rename) to prevent partial archives.
    """

    def __init__(self, logger: BackupLogger):
        self.logger = logger

    def compress(
        self,
        source_dir: Path,
        output_path: Path,
        fmt: str,
    ) -> Path:
        """Compress the source directory into an archive.

        Args:
            source_dir: The directory to compress.
            output_path: Full path for the output archive (including extension).
            fmt: Compression format ("zip" or "tar.gz").

        Returns:
            Path to the created archive file.

        Raises:
            ValueError: If format is not supported.
            FileNotFoundError: If source_dir does not exist.
            OSError: If compression fails.
        """
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported compression format: {fmt!r}. "
                f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )

        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

        if not source_dir.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

        self.logger.info(f"Compressing backup to {fmt} format...")

        # Atomic write: compress into a temp file, then rename on success
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_fd, temp_path_str = tempfile.mkstemp(
            suffix=f".{fmt}.tmp",
            dir=output_path.parent,
        )
        temp_path = Path(temp_path_str)

        try:
            # Close the file descriptor; the compression libraries open by name
            import os

            os.close(temp_fd)

            if fmt == "zip":
                self._compress_zip(source_dir, temp_path)
            else:
                self._compress_tar_gz(source_dir, temp_path)

            # Atomic rename
            temp_path.replace(output_path)

            archive_size = output_path.stat().st_size
            self.logger.success(
                f"Archive created: {output_path.name} "
                f"({archive_size / (1024 * 1024):.2f} MB)"
            )
            return output_path

        except Exception:
            # Clean up partial temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _compress_zip(self, source_dir: Path, archive_path: Path) -> None:
        """Create a .zip archive using zipfile module."""
        file_count = 0
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(source_dir.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)
                    file_count += 1
                elif file_path.is_dir():
                    # Preserve empty directories by adding a directory entry.
                    # ZipInfo trailing slash signals a directory to most tools.
                    arcname = str(file_path.relative_to(source_dir)) + "/"
                    zf.writestr(zipfile.ZipInfo(arcname), "")

        self.logger.info(f"Compressed {file_count} files into zip archive")

    def _compress_tar_gz(self, source_dir: Path, archive_path: Path) -> None:
        """Create a .tar.gz archive using tarfile module."""
        file_count = 0
        with tarfile.open(archive_path, "w:gz") as tf:
            for file_path in sorted(source_dir.rglob("*")):
                arcname = str(file_path.relative_to(source_dir))
                tf.add(file_path, arcname=arcname, recursive=False)
                if file_path.is_file():
                    file_count += 1

        self.logger.info(f"Compressed {file_count} files into tar.gz archive")

    @staticmethod
    def get_archive_name(device_name: str, fmt: str) -> str:
        """Generate an archive filename with timestamp.

        Args:
            device_name: The device identifier for the archive name.
            fmt: Compression format ("zip" or "tar.gz").

        Returns:
            Filename string like "MyDevice_20260228_093022.zip".
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = fmt  # "zip" or "tar.gz"
        return f"{device_name}_{timestamp}.{ext}"

    @staticmethod
    def is_already_compressed(backup_root: Path, device_name: str) -> bool:
        """Check if a backup has already been compressed.

        Looks for existing archive files matching the device name pattern
        in the backup root directory.

        Args:
            backup_root: The Documents-Backup/ directory.
            device_name: The device identifier to look for.

        Returns:
            True if at least one matching archive exists.
        """
        if not backup_root.exists():
            return False

        for ext in SUPPORTED_FORMATS:
            pattern = f"{device_name}_*.{ext}"
            if list(backup_root.glob(pattern)):
                return True

        return False

    @staticmethod
    def find_archives(backup_root: Path, device_name: str) -> List[Path]:
        """Find all archive files for a given device.

        Args:
            backup_root: The Documents-Backup/ directory.
            device_name: The device identifier to search for.

        Returns:
            List of archive file paths, sorted by name.
        """
        archives: List[Path] = []
        if not backup_root.exists():
            return archives

        for ext in SUPPORTED_FORMATS:
            pattern = f"{device_name}_*.{ext}"
            archives.extend(backup_root.glob(pattern))

        return sorted(archives)
