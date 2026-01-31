"""
Handlers - Fallback and error handling.
"""

from pathlib import Path
from typing import Optional

from smartbackup.models import BackupResult
from smartbackup.ui.colors import Colors
from smartbackup.ui.logger import BackupLogger


class FallbackHandler:
    """
    Handles fallback scenarios when backup is not possible.

    Options:
    - Local temporary backup
    - User notification
    - Automatic retry
    """

    def __init__(self, logger: BackupLogger):
        self.logger = logger

    def handle_no_device(self, source_path: Path) -> Optional[Path]:
        """
        Handles the case when no external medium is available.

        Returns:
            Alternative backup path or None
        """
        self.logger.warning(
            """
+================================================================+
|  !  EXTERNAL STORAGE MEDIUM NOT FOUND                          |
+================================================================+
|                                                                |
|  Please make sure that:                                        |
|  - The external medium is connected                            |
|  - The medium is recognized by the system                      |
|  - You have write permissions on the medium                    |
|                                                                |
+================================================================+
"""
        )

        # Option 1: Offer local backup
        local_backup = Path.home() / ".local_backup_temp"

        print(f"\n{Colors.YELLOW}Options:{Colors.END}")
        print(f"  [1] Create local temporary backup ({local_backup})")
        print("  [2] Wait and try again")
        print("  [3] Cancel")

        try:
            choice = input(f"\n{Colors.CYAN}Your choice (1-3): {Colors.END}").strip()

            if choice == "1":
                local_backup.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Local backup directory created: {local_backup}")
                return local_backup

            elif choice == "2":
                print("\nPlease connect the external medium and press Enter...")
                input()
                return None  # Will retry

            else:
                self.logger.info("Backup cancelled.")
                return None

        except KeyboardInterrupt:
            print("\n")
            self.logger.info("Backup cancelled by user.")
            return None

    def notify_completion(self, result: BackupResult, success: bool) -> None:
        """Notifies about completion (can be extended for desktop notifications)."""
        if success:
            self.logger.success("Backup completed successfully!")
        else:
            self.logger.error("Backup completed with errors!")
