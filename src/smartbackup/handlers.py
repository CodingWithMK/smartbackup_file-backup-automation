"""
Handlers - Fallback and error handling.
"""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from smartbackup.models import BackupResult
from smartbackup.ui.logger import BackupLogger

console = Console(highlight=False)

_NOTIFICATION_TIMEOUT_SECONDS = 5


def _escape_applescript(text: str) -> str:
    """Escape backslashes and double quotes for an AppleScript string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _escape_powershell(text: str) -> str:
    """Escape single quotes for a single-quoted PowerShell string literal."""
    return text.replace("'", "''")


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

    def notify_completion(
        self,
        result: BackupResult,
        success: bool,
        desktop: bool = False,
    ) -> None:
        """
        Notify the user about backup completion.

        Always logs the console summary message. When *desktop* is True, also
        attempts a best-effort OS desktop notification (macOS ``osascript``,
        Linux ``notify-send``, or Windows PowerShell) without ever failing the
        backup if notifications are unavailable.
        """
        if success:
            self.logger.success("Backup completed successfully!")
        else:
            self.logger.error("Backup completed with errors!")

        if not desktop:
            return

        title = "SmartBackup — Completed" if success else "SmartBackup — Completed with Errors"
        parts = [
            f"Copied: {result.copied_files}",
            f"Updated: {result.updated_files}",
            f"Skipped: {result.skipped_files}",
        ]
        if result.errors:
            parts.append(f"Errors: {result.errors}")
        message = ", ".join(parts)

        self._send_desktop_notification(title, message)

    def _send_desktop_notification(self, title: str, message: str) -> bool:
        """Send a best-effort OS desktop notification. Returns True on success."""
        system = platform.system()
        cmd: Optional[list[str]] = None

        if system == "Darwin":
            osascript = shutil.which("osascript")
            if osascript:
                script = (
                    f'display notification "{_escape_applescript(message)}" '
                    f'with title "{_escape_applescript(title)}"'
                )
                cmd = [osascript, "-e", script]
        elif system == "Linux":
            notify_send = shutil.which("notify-send")
            if notify_send:
                cmd = [notify_send, title, message]
        elif system == "Windows":
            shell = shutil.which("powershell") or shutil.which("pwsh")
            if shell:
                ps_script = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$n = New-Object System.Windows.Forms.NotifyIcon; "
                    "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                    "$n.Visible = $true; "
                    f"$n.ShowBalloonTip(5000, '{_escape_powershell(title)}', "
                    f"'{_escape_powershell(message)}', "
                    "[System.Windows.Forms.ToolTipIcon]::Info); "
                    "Start-Sleep -Milliseconds 500; $n.Dispose()"
                )
                cmd = [shell, "-NoProfile", "-NonInteractive", "-Command", ps_script]

        if not cmd:
            self.logger.warning(
                f"Desktop notifications are not available on this system ({system})."
            )
            return False

        try:
            kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "timeout": _NOTIFICATION_TIMEOUT_SECONDS,
                "check": False,
            }
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if system == "Windows" and create_no_window:
                kwargs["creationflags"] = create_no_window

            proc = subprocess.run(cmd, **kwargs)
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            self.logger.warning(f"Could not send desktop notification: {e}")
            return False
