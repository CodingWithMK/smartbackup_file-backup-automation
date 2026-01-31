"""
DeviceDetector - External media detection and validation.
"""

from pathlib import Path
from typing import Optional

from smartbackup.platform.resolver import PathResolver
from smartbackup.ui.logger import BackupLogger


class DeviceDetector:
    """
    Detects and validates external storage media.

    Features:
    - Automatic detection of available media
    - Storage space validation
    - User interaction for selection
    """

    def __init__(self, logger: BackupLogger):
        self.logger = logger

    def find_backup_device(
        self, required_space: int = 0, preferred_label: Optional[str] = None
    ) -> Optional[Path]:
        """
        Finds a suitable backup medium.

        Args:
            required_space: Minimum required free space
            preferred_label: Preferred drive label

        Returns:
            Path to backup medium or None
        """
        self.logger.section("Searching for external storage medium...")

        drives = PathResolver.find_external_drives()

        if not drives:
            self.logger.warning("No external storage medium found!")
            return None

        # Filter by storage space
        suitable_drives = [
            (path, label, free) for path, label, free in drives if free >= required_space
        ]

        if not suitable_drives:
            self.logger.warning(
                f"No drive with sufficient storage space "
                f"({required_space / (1024**3):.1f} GB required) found!"
            )
            return None

        # Check for preferred drive
        if preferred_label:
            for path, label, free in suitable_drives:
                if label.lower() == preferred_label.lower():
                    self.logger.success(
                        f"Preferred drive found: {label} ({path}) - {free / (1024**3):.1f} GB free"
                    )
                    return path

        # Multiple options: let user choose or take first one
        if len(suitable_drives) == 1:
            path, label, free = suitable_drives[0]
            self.logger.success(
                f"External medium found: {label} ({path}) - {free / (1024**3):.1f} GB free"
            )
            return path

        # Multiple options - show selection
        self.logger.info("Multiple external media found:")
        for i, (path, label, free) in enumerate(suitable_drives, 1):
            print(f"  [{i}] {label} ({path}) - {free / (1024**3):.1f} GB free")

        # In automatic mode: take first one
        path, label, free = suitable_drives[0]
        self.logger.info(f"Automatic selection: {label}")
        return path

    def validate_device(self, path: Path) -> bool:
        """Validates if the device is writable."""
        if not path.exists():
            return False

        try:
            test_file = path / ".backup_test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False
