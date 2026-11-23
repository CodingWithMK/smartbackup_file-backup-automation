"""
Interactive Folder Selector - Zero-dependency keyboard-driven TUI for --select.

Allows users to browse top-level folders in their source directory and toggle
individual folders for backup using arrow keys, Space, Enter, 'a', and Esc/'q'.
Uses only Rich and the Python standard library (msvcrt on Windows, termios/tty/select
on POSIX).
"""

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from smartbackup.core.scanner import ExclusionFilter
from smartbackup.models import SelectionMetadata


class KeyAction(Enum):
    """Normalized keyboard actions for the interactive folder selector."""

    UP = auto()
    DOWN = auto()
    TOGGLE = auto()
    TOGGLE_ALL = auto()
    CONFIRM = auto()
    CANCEL = auto()
    OTHER = auto()


def _read_key_windows() -> KeyAction:
    """Read a single keypress on Windows using msvcrt.getwch()."""
    import msvcrt

    ch = msvcrt.getwch()
    if ch in ("\r", "\n"):
        return KeyAction.CONFIRM
    if ch == " ":
        return KeyAction.TOGGLE
    if ch in ("a", "A"):
        return KeyAction.TOGGLE_ALL
    if ch in ("q", "Q", "\x1b", "\x03"):
        return KeyAction.CANCEL
    if ch in ("k", "K"):
        return KeyAction.UP
    if ch in ("j", "J"):
        return KeyAction.DOWN
    if ch in ("\x00", "\xe0"):
        ext = msvcrt.getwch()
        if ext == "H":
            return KeyAction.UP
        if ext == "P":
            return KeyAction.DOWN
        return KeyAction.OTHER
    return KeyAction.OTHER


def _read_key_posix() -> KeyAction:
    """
    Read a single keypress on POSIX using termios/tty cbreak mode.

    Always restores terminal settings in a try...finally block and uses a
    50ms select() timeout after ESC (0x1b) to distinguish a bare Escape key
    from ANSI CSI/SS3 arrow key escape sequences.
    """
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        raw = os.read(fd, 1)
        if not raw:
            return KeyAction.CANCEL

        ch = raw.decode("utf-8", errors="ignore")
        if ch in ("\r", "\n"):
            return KeyAction.CONFIRM
        if ch == " ":
            return KeyAction.TOGGLE
        if ch in ("a", "A"):
            return KeyAction.TOGGLE_ALL
        if ch in ("q", "Q", "\x03"):
            return KeyAction.CANCEL
        if ch in ("k", "K"):
            return KeyAction.UP
        if ch in ("j", "J"):
            return KeyAction.DOWN
        if ch == "\x1b":
            # Disambiguate bare ESC from escape sequences (e.g. \x1b[A, \x1b[B)
            ready, _, _ = select.select([fd], [], [], 0.05)
            if not ready:
                return KeyAction.CANCEL

            seq1 = os.read(fd, 1).decode("utf-8", errors="ignore")
            if seq1 in ("[", "O"):
                ready2, _, _ = select.select([fd], [], [], 0.05)
                if ready2:
                    seq2 = os.read(fd, 1).decode("utf-8", errors="ignore")
                    if seq2 == "A":
                        return KeyAction.UP
                    if seq2 == "B":
                        return KeyAction.DOWN
                    # Drain any trailing CSI parameter bytes (e.g. Home/End/PgUp)
                    while select.select([fd], [], [], 0.01)[0]:
                        os.read(fd, 1)
            return KeyAction.OTHER
        return KeyAction.OTHER
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def read_key() -> KeyAction:
    """Cross-platform single-keypress reader returning a normalized KeyAction."""
    if sys.platform == "win32":
        return _read_key_windows()
    return _read_key_posix()


@dataclass
class FolderItem:
    """Represents a selectable top-level folder in the source directory."""

    name: str
    path: Path
    selected: bool = False
    previously_backed_up: bool = False


@dataclass(frozen=True)
class _GlyphSet:
    """Terminal-encoding-safe UI glyph bundle."""

    pointer: str
    check: str
    up_arrow: str
    down_arrow: str
    nav_hint: str
    bullet: str


_UNICODE_GLYPHS = _GlyphSet(
    pointer="❯",
    check="✓",
    up_arrow="▲",
    down_arrow="▼",
    nav_hint="↑/↓",
    bullet="•",
)

_ASCII_GLYPHS = _GlyphSet(
    pointer=">",
    check="x",
    up_arrow="^",
    down_arrow="v",
    nav_hint="Up/Down",
    bullet="*",
)


def _resolve_glyphs(console: Console) -> _GlyphSet:
    """Choose Unicode glyphs when the console encoding supports them, else ASCII."""
    encoding = getattr(console, "encoding", None) or getattr(sys.stdout, "encoding", None) or "utf-8"
    sample = (
        _UNICODE_GLYPHS.pointer
        + _UNICODE_GLYPHS.check
        + _UNICODE_GLYPHS.up_arrow
        + _UNICODE_GLYPHS.down_arrow
        + _UNICODE_GLYPHS.nav_hint
        + _UNICODE_GLYPHS.bullet
    )
    try:
        sample.encode(encoding)
        return _UNICODE_GLYPHS
    except (UnicodeEncodeError, LookupError):
        return _ASCII_GLYPHS


class FolderSelector:
    """
    Interactive terminal folder selector for ``smartbackup --select``.

    Discovers top-level subdirectories of ``source_path``, renders a live
    checkbox list with viewport scrolling, and returns a ``SelectionMetadata``
    object on confirmation or ``None`` on cancellation / empty directory.
    """

    def __init__(
        self,
        source_path: Path,
        exclusion_filter: Optional[ExclusionFilter] = None,
        console: Optional[Console] = None,
        key_reader: Optional[Callable[[], KeyAction]] = None,
        previously_backed_up: Optional[set[str]] = None,
        max_visible: Optional[int] = None,
    ) -> None:
        self.source_path = source_path
        self.exclusion_filter = exclusion_filter
        self.console = console or Console(highlight=False)
        self._key_reader: Callable[[], KeyAction] = key_reader or read_key
        self._previously_backed_up: set[str] = set(previously_backed_up or set())
        self._max_visible = max_visible
        self._glyphs = _resolve_glyphs(self.console)

    def discover_folders(self) -> tuple[list[FolderItem], int]:
        """
        Discover selectable top-level folders in ``self.source_path``.

        Only top-level directories are returned (loose files are ignored).
        Hidden directories starting with ``'.'`` and directories matched by
        ``self.exclusion_filter`` are skipped and counted in ``excluded_count``.

        Returns:
            Tuple of ``(sorted_folder_items, excluded_folders_count)``.
        """
        items: list[FolderItem] = []
        excluded_count = 0

        with os.scandir(self.source_path) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue

                name = entry.name
                entry_path = Path(entry.path)

                if name.startswith("."):
                    excluded_count += 1
                    continue

                if self.exclusion_filter is not None:
                    should_exclude, _ = self.exclusion_filter.should_exclude(entry_path)
                    if should_exclude:
                        excluded_count += 1
                        continue

                items.append(
                    FolderItem(
                        name=name,
                        path=entry_path,
                        selected=False,
                        previously_backed_up=name in self._previously_backed_up,
                    )
                )

        items.sort(key=lambda item: item.name.lower())
        return items, excluded_count

    def _compute_visible_rows(self) -> int:
        """Compute how many folder rows fit comfortably in the terminal viewport."""
        if self._max_visible is not None:
            return max(1, self._max_visible)
        try:
            term_height = self.console.size.height
        except Exception:
            term_height = 24
        # Reserve ~10 lines for panel border, header, scroll indicators, and footer
        return max(5, term_height - 10)

    def _render(
        self,
        items: list[FolderItem],
        cursor: int,
        scroll_offset: int,
        visible_rows: int,
        error_msg: str = "",
    ) -> Panel:
        """Render the interactive selector UI as a Rich Panel."""
        g = self._glyphs
        selected_count = sum(1 for item in items if item.selected)
        total_count = len(items)

        lines: list[str] = [
            f"[dim]Source:[/dim] [bold]{escape(str(self.source_path))}[/bold]",
            f"[dim]Selected:[/dim] [bold green]{selected_count}[/bold green] / {total_count} folder(s)",
            "",
        ]

        if scroll_offset > 0:
            lines.append(f"  [dim]{g.up_arrow} {scroll_offset} more above[/dim]")

        end_idx = min(total_count, scroll_offset + visible_rows)
        for idx in range(scroll_offset, end_idx):
            item = items[idx]
            is_current = idx == cursor
            pointer = f"[bold cyan]{g.pointer}[/bold cyan]" if is_current else " "
            checkbox = (
                f"[bold green]\\[{g.check}][/bold green]"
                if item.selected
                else "[dim]\\[ ][/dim]"
            )
            safe_name = escape(item.name)
            if is_current:
                name_display = f"[bold cyan]{safe_name}/[/bold cyan]"
            elif item.selected:
                name_display = f"[green]{safe_name}/[/green]"
            else:
                name_display = f"{safe_name}/"

            badge = " [dim](backed up)[/dim]" if item.previously_backed_up else ""
            lines.append(f" {pointer} {checkbox} {name_display}{badge}")

        remaining_below = total_count - end_idx
        if remaining_below > 0:
            lines.append(f"  [dim]{g.down_arrow} {remaining_below} more below[/dim]")

        if error_msg:
            lines.append("")
            lines.append(f"[bold yellow]{escape(error_msg)}[/bold yellow]")

        lines.append("")
        lines.append(
            f"[dim]{g.nav_hint} Navigate  {g.bullet}  Space Toggle  {g.bullet}  "
            f"a All/None  {g.bullet}  Enter Confirm  {g.bullet}  Esc/q Cancel[/dim]"
        )

        body = Text.from_markup("\n".join(lines))
        return Panel(
            body,
            title="[bold cyan]Select Folders to Back Up (--select)[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
            expand=False,
        )

    def select(self) -> Optional[SelectionMetadata]:
        """
        Launch the interactive folder selector loop.

        Returns:
            ``SelectionMetadata`` when the user confirms >= 1 selected folder,
            or ``None`` if no selectable folders exist or the user cancels.
        """
        items, excluded_count = self.discover_folders()

        if not items:
            self.console.print(
                f"[yellow]No selectable folders found in {escape(str(self.source_path))}[/yellow]"
            )
            return None

        cursor = 0
        scroll_offset = 0
        visible_rows = self._compute_visible_rows()
        error_msg = ""

        try:
            with Live(
                self._render(items, cursor, scroll_offset, visible_rows, error_msg),
                console=self.console,
                auto_refresh=False,
                transient=True,
            ) as live:
                while True:
                    action = self._key_reader()

                    if action == KeyAction.UP:
                        error_msg = ""
                        if cursor > 0:
                            cursor -= 1
                            if cursor < scroll_offset:
                                scroll_offset = cursor

                    elif action == KeyAction.DOWN:
                        error_msg = ""
                        if cursor < len(items) - 1:
                            cursor += 1
                            if cursor >= scroll_offset + visible_rows:
                                scroll_offset = cursor - visible_rows + 1

                    elif action == KeyAction.TOGGLE:
                        error_msg = ""
                        items[cursor].selected = not items[cursor].selected

                    elif action == KeyAction.TOGGLE_ALL:
                        error_msg = ""
                        all_selected = all(item.selected for item in items)
                        for item in items:
                            item.selected = not all_selected

                    elif action == KeyAction.CONFIRM:
                        chosen = [item.name for item in items if item.selected]
                        if not chosen:
                            error_msg = "Please select at least one folder before pressing Enter."
                        else:
                            now = datetime.now()
                            available_names = [item.name for item in items]
                            workflow_steps = [
                                "CLI invoked with --select",
                                (
                                    f"Discovered {len(available_names)} selectable folder(s) "
                                    f"({excluded_count} hidden/excluded skipped) in {self.source_path}"
                                ),
                                (
                                    f"User confirmed {len(chosen)} of {len(available_names)} "
                                    f"folder(s): {', '.join(chosen)}"
                                ),
                            ]
                            return SelectionMetadata(
                                command_option="--select",
                                source_root=str(self.source_path),
                                available_folders=available_names,
                                selected_folders=chosen,
                                excluded_folders_count=excluded_count,
                                selected_at=now,
                                workflow_steps=workflow_steps,
                            )

                    elif action == KeyAction.CANCEL:
                        return None

                    live.update(
                        self._render(items, cursor, scroll_offset, visible_rows, error_msg),
                        refresh=True,
                    )
        except KeyboardInterrupt:
            return None
