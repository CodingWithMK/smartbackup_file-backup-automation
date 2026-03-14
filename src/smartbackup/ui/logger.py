"""
BackupLogger - Central logging system for terminal and file output.

Modernised with Rich for styled terminal output, progress bars, panels,
and tables while keeping the same public API.
"""

import platform
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

from smartbackup.models import BackupResult, FileAction


class BackupLogger:
    """
    Central logging system for terminal and file.

    Features:
    - Rich styled terminal output
    - Progress bar via Rich Progress
    - Log file on backup medium
    - Timestamps for all entries
    """

    def __init__(self, log_file: Optional[Path] = None, verbose: bool = True):
        self.log_file = log_file
        self.verbose = verbose
        self.lock = threading.Lock()
        self._log_buffer: List[str] = []
        self._progress_line_active = False
        self.console = Console(highlight=False)

        # Rich progress bar (lazily initialised)
        self._progress_bar: Optional[Progress] = None
        self._progress_task_id: Optional[int] = None
        self._progress_total: int = 0

    def _timestamp(self) -> str:
        """Formatted timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _stop_progress(self) -> None:
        """Stop the Rich progress bar if it is running."""
        if self._progress_bar is not None:
            try:
                self._progress_bar.stop()
            except Exception:
                pass
            self._progress_bar = None
            self._progress_task_id = None
        self._progress_line_active = False

    def _clear_progress_line(self) -> None:
        """Clears the current progress line (stops Rich progress)."""
        if self._progress_line_active:
            self._stop_progress()

    def header(self, message: str) -> None:
        """Outputs a header."""
        self._clear_progress_line()
        panel = Panel(
            Text(message, style="bold white", justify="center"),
            style="cyan",
            expand=False,
            padding=(0, 2),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()
        self._log_to_file(f"\n{'=' * 60}\n{message}\n{'=' * 60}")

    def section(self, message: str) -> None:
        """Outputs a section header."""
        self._clear_progress_line()
        self.console.print()
        self.console.print(f"[bold blue]> {message}[/bold blue]")
        self._log_to_file(f"\n--- {message} ---")

    def info(self, message: str) -> None:
        """Information message."""
        if self.verbose:
            self._clear_progress_line()
            self.console.print(f"[cyan]i[/cyan]  \\[{self._timestamp()}] {message}")
        self._log_to_file(f"[INFO] [{self._timestamp()}] {message}")

    def success(self, message: str) -> None:
        """Success message."""
        self._clear_progress_line()
        self.console.print(f"[green]+[/green]  \\[{self._timestamp()}] {message}")
        self._log_to_file(f"[SUCCESS] [{self._timestamp()}] {message}")

    def warning(self, message: str) -> None:
        """Warning message."""
        self._clear_progress_line()
        self.console.print(f"[yellow]![/yellow]  \\[{self._timestamp()}] {message}")
        self._log_to_file(f"[WARNING] [{self._timestamp()}] {message}")

    def error(self, message: str) -> None:
        """Error message."""
        self._clear_progress_line()
        self.console.print(f"[red]x[/red]  \\[{self._timestamp()}] {message}")
        self._log_to_file(f"[ERROR] [{self._timestamp()}] {message}")

    def file_action(self, action: FileAction, file_path: Path, details: str = "") -> None:
        """Logs a file action."""
        icons = {
            FileAction.COPIED: ("green", "+", "COPIED"),
            FileAction.UPDATED: ("blue", "~", "UPDATED"),
            FileAction.SKIPPED: ("yellow", "-", "SKIPPED"),
            FileAction.DELETED: ("red", "x", "DELETED"),
            FileAction.ERROR: ("red", "!", "ERROR"),
        }

        style, icon, label = icons.get(action, ("", "?", "UNKNOWN"))

        if self.verbose or action in (FileAction.COPIED, FileAction.UPDATED, FileAction.ERROR):
            self._clear_progress_line()
            detail_str = f" ({details})" if details else ""
            self.console.print(f"[{style}]{icon}[/{style}] \\[{label}] {file_path}{detail_str}")

        self._log_to_file(f"[{label}] [{self._timestamp()}] {file_path} {details}")

    def progress(
        self,
        current: int,
        total: int,
        current_file: str = "",
        bytes_copied: int = 0,
        total_bytes: int = 0,
    ) -> None:
        """Shows a progress bar using Rich Progress."""
        if total == 0:
            return

        # Truncate filename
        if len(current_file) > 40:
            current_file = "..." + current_file[-37:]

        # Lazily create and start the Rich progress bar
        if self._progress_bar is None:
            columns = [
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
                MofNCompleteColumn(),
            ]
            if total_bytes > 0:
                columns.append(TransferSpeedColumn())
            columns.append(TimeRemainingColumn())

            self._progress_bar = Progress(
                *columns,
                console=self.console,
                transient=True,
            )
            self._progress_total = total
            self._progress_task_id = self._progress_bar.add_task(
                current_file or "Backing up...",
                total=total,
            )
            self._progress_bar.start()
            self._progress_line_active = True

        # Update progress
        if self._progress_task_id is not None:
            self._progress_bar.update(
                self._progress_task_id,
                completed=current,
                description=current_file or "Backing up...",
            )

    def _format_size(self, size: int) -> str:
        """Formats file size in human-readable format."""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_float < 1024:
                return f"{size_float:.1f}{unit}"
            size_float /= 1024
        return f"{size_float:.1f}PB"

    def _log_to_file(self, message: str) -> None:
        """Writes to the log file."""
        if self.log_file:
            with self.lock:
                self._log_buffer.append(message)

    def flush_to_file(self) -> None:
        """Writes the buffer to the log file."""
        if self.log_file and self._log_buffer:
            with self.lock:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(self._log_buffer) + "\n")
                self._log_buffer.clear()

    def summary(self, result: BackupResult) -> None:
        """Shows a summary of the backup operation using a Rich table."""
        self._clear_progress_line()

        duration = result.duration
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        table = Table(
            title="BACKUP SUMMARY",
            title_style="bold cyan",
            show_header=False,
            expand=False,
            border_style="cyan",
            padding=(0, 2),
        )
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        table.add_row("[green]Copied Files[/green]", str(result.copied_files))
        table.add_row("[blue]Updated Files[/blue]", str(result.updated_files))
        table.add_row("[yellow]Skipped Files[/yellow]", str(result.skipped_files))
        table.add_row("[red]Errors[/red]", str(result.errors))
        table.add_row("", "")
        table.add_row("Total Files", str(result.total_files))
        table.add_row("Copied Size", self._format_size(result.copied_size))
        table.add_row("Duration", time_str)
        table.add_row("Speed", f"{result.speed_mbps:.2f} MB/s")

        self.console.print()
        self.console.print(table)
        self.console.print()

        self._log_to_file(
            f"\n{'=' * 60}\nSUMMARY\n"
            f"Copied: {result.copied_files}, "
            f"Updated: {result.updated_files}, "
            f"Skipped: {result.skipped_files}, "
            f"Errors: {result.errors}\n"
            f"Size: {self._format_size(result.copied_size)}, "
            f"Duration: {time_str}\n{'=' * 60}"
        )
