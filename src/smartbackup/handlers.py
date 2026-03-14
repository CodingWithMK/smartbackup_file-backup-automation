"""
Handlers - Fallback and error handling.
"""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from smartbackup.models import BackupResult
from smartbackup.ui.logger import BackupLogger

console = Console(highlight=False)


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
        warning_msg = (
            "[bold]EXTERNAL STORAGE MEDIUM NOT FOUND[/bold]\n\n"
            "Please make sure that:\n"
            "  - The external medium is connected\n"
            "  - The medium is recognized by the system\n"
            "  - You have write permissions on the medium"
        )

        console.print()
        console.print(
            Panel(warning_msg, title="Warning", style="yellow", expand=False, padding=(1, 2))
        )

        # Option 1: Offer local backup
        local_backup = Path.home() / ".local_backup_temp"

        console.print()
        console.print("[yellow]Options:[/yellow]")
        console.print(f"  [bold]\\[1][/bold] Create local temporary backup ({local_backup})")
        console.print("  [bold]\\[2][/bold] Wait and try again")
        console.print("  [bold]\\[3][/bold] Cancel")

        try:
            choice = Prompt.ask("\n[cyan]Your choice[/cyan]", choices=["1", "2", "3"], default="3")

            if choice == "1":
                local_backup.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Local backup directory created: {local_backup}")
                return local_backup

            elif choice == "2":
                console.print("\nPlease connect the external medium and press Enter...")
                input()
                return None  # Will retry

            else:
                self.logger.info("Backup cancelled.")
                return None

        except KeyboardInterrupt:
            console.print()
            self.logger.info("Backup cancelled by user.")
            return None

    def notify_completion(self, result: BackupResult, success: bool) -> None:
        """Notifies about completion (can be extended for desktop notifications)."""
        if success:
            self.logger.success("Backup completed successfully!")
        else:
            self.logger.error("Backup completed with errors!")
