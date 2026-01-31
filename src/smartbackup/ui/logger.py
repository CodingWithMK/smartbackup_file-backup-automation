"""
BackupLogger - Central logging system for terminal and file output.
"""

import platform
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from smartbackup.models import BackupResult, FileAction
from smartbackup.ui.colors import Colors


class BackupLogger:
    """
    Central logging system for terminal and file.

    Features:
    - Colored terminal output
    - Progress bar
    - Log file on backup medium
    - Timestamps for all entries
    """

    def __init__(self, log_file: Optional[Path] = None, verbose: bool = True):
        self.log_file = log_file
        self.verbose = verbose
        self.lock = threading.Lock()
        self._log_buffer: List[str] = []
        self._progress_line_active = False

        # Windows compatibility for ANSI colors
        if platform.system() == "Windows":
            self._enable_windows_ansi()

    def _enable_windows_ansi(self) -> None:
        """Enables ANSI escape sequences on Windows."""
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            Colors.disable()

    def _timestamp(self) -> str:
        """Formatted timestamp."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _clear_progress_line(self) -> None:
        """Clears the current progress line."""
        if self._progress_line_active:
            sys.stdout.write("\r" + " " * 100 + "\r")
            sys.stdout.flush()
            self._progress_line_active = False

    def header(self, message: str) -> None:
        """Outputs a header."""
        self._clear_progress_line()
        border = "=" * (len(message) + 4)
        output = f"\n{Colors.CYAN}+{border}+\n|  {message}  |\n+{border}+{Colors.END}\n"
        print(output)
        self._log_to_file(f"\n{'=' * 60}\n{message}\n{'=' * 60}")

    def section(self, message: str) -> None:
        """Outputs a section header."""
        self._clear_progress_line()
        output = f"\n{Colors.BOLD}{Colors.BLUE}> {message}{Colors.END}"
        print(output)
        self._log_to_file(f"\n--- {message} ---")

    def info(self, message: str) -> None:
        """Information message."""
        if self.verbose:
            self._clear_progress_line()
            output = f"{Colors.CYAN}i{Colors.END}  [{self._timestamp()}] {message}"
            print(output)
        self._log_to_file(f"[INFO] [{self._timestamp()}] {message}")

    def success(self, message: str) -> None:
        """Success message."""
        self._clear_progress_line()
        output = f"{Colors.GREEN}+{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[SUCCESS] [{self._timestamp()}] {message}")

    def warning(self, message: str) -> None:
        """Warning message."""
        self._clear_progress_line()
        output = f"{Colors.YELLOW}!{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[WARNING] [{self._timestamp()}] {message}")

    def error(self, message: str) -> None:
        """Error message."""
        self._clear_progress_line()
        output = f"{Colors.RED}x{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[ERROR] [{self._timestamp()}] {message}")

    def file_action(self, action: FileAction, file_path: Path, details: str = "") -> None:
        """Logs a file action."""
        icons = {
            FileAction.COPIED: (Colors.GREEN, "+", "COPIED"),
            FileAction.UPDATED: (Colors.BLUE, "~", "UPDATED"),
            FileAction.SKIPPED: (Colors.YELLOW, "-", "SKIPPED"),
            FileAction.DELETED: (Colors.RED, "x", "DELETED"),
            FileAction.ERROR: (Colors.RED, "!", "ERROR"),
        }

        color, icon, label = icons.get(action, (Colors.END, "?", "UNKNOWN"))

        if self.verbose or action in (FileAction.COPIED, FileAction.UPDATED, FileAction.ERROR):
            self._clear_progress_line()
            detail_str = f" ({details})" if details else ""
            output = f"{color}{icon}{Colors.END} [{label}] {file_path}{detail_str}"
            print(output)

        self._log_to_file(f"[{label}] [{self._timestamp()}] {file_path} {details}")

    def progress(
        self,
        current: int,
        total: int,
        current_file: str = "",
        bytes_copied: int = 0,
        total_bytes: int = 0,
    ) -> None:
        """Shows a progress bar."""
        if total == 0:
            return

        percent = (current / total) * 100
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = "#" * filled + "-" * (bar_length - filled)

        # Size information
        if total_bytes > 0:
            size_info = f" | {self._format_size(bytes_copied)}/{self._format_size(total_bytes)}"
        else:
            size_info = ""

        # Truncate filename
        if len(current_file) > 40:
            current_file = "..." + current_file[-37:]

        progress_str = (
            f"\r{Colors.CYAN}[{bar}]{Colors.END} "
            f"{percent:5.1f}% ({current}/{total}){size_info} "
            f"| {current_file}"
        )

        sys.stdout.write(progress_str.ljust(120))
        sys.stdout.flush()
        self._progress_line_active = True

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
        """Shows a summary of the backup operation."""
        self._clear_progress_line()

        duration = result.duration
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        summary = f"""
{Colors.CYAN}+==============================================================+
|                       BACKUP SUMMARY                         |
+==============================================================+{Colors.END}
|  {Colors.GREEN}Copied Files:{Colors.END}          {result.copied_files:>8}                             |
|  {Colors.BLUE}Updated Files:{Colors.END}         {result.updated_files:>8}                             |
|  {Colors.YELLOW}Skipped Files:{Colors.END}         {result.skipped_files:>8}                             |
|  {Colors.RED}Errors:{Colors.END}                {result.errors:>8}                             |
+==============================================================+
|  Total Files:            {result.total_files:>8}                            |
|  Copied Size:            {self._format_size(result.copied_size):>8}                            |
|  Duration:               {time_str:>8}                            |
|  Speed:                  {result.speed_mbps:>6.2f} MB/s                         |
{Colors.CYAN}+==============================================================+{Colors.END}
"""
        print(summary)
        self._log_to_file(
            f"\n{'=' * 60}\nSUMMARY\n"
            f"Copied: {result.copied_files}, "
            f"Updated: {result.updated_files}, "
            f"Skipped: {result.skipped_files}, "
            f"Errors: {result.errors}\n"
            f"Size: {self._format_size(result.copied_size)}, "
            f"Duration: {time_str}\n{'=' * 60}"
        )
