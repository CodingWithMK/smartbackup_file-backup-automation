"""
Unit tests for ui.selector (interactive --select folder picker).
"""

import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from smartbackup.config import DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS
from smartbackup.core.scanner import ExclusionFilter
from smartbackup.ui.selector import (
    FolderItem,
    FolderSelector,
    KeyAction,
    _read_key_posix,
    _read_key_windows,
)


def _make_console(width: int = 100, height: int = 30) -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, width=width, height=height, force_terminal=False, highlight=False)
    return console, buf


def _scripted_keys(*actions: KeyAction):
    iterator = iter(actions)
    return lambda: next(iterator)


class TestDiscoverFolders:
    """Tests for FolderSelector.discover_folders()."""

    def test_discovers_only_top_level_non_hidden_non_excluded_dirs(self, tmp_path: Path):
        (tmp_path / "zeta").mkdir()
        (tmp_path / "Alpha").mkdir()
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "nested_dir").mkdir()
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "loose_file.txt").write_text("root file")

        filt = ExclusionFilter(DEFAULT_EXCLUSIONS, EXCLUDED_EXTENSIONS)
        console, _ = _make_console()
        selector = FolderSelector(
            tmp_path,
            exclusion_filter=filt,
            console=console,
            previously_backed_up={"Alpha"},
        )

        items, excluded_count = selector.discover_folders()

        assert [item.name for item in items] == ["Alpha", "projects", "zeta"]
        assert excluded_count == 3  # .hidden_dir, node_modules, __pycache__
        assert items[0].previously_backed_up is True
        assert items[1].previously_backed_up is False
        assert all(item.selected is False for item in items)

    def test_empty_directory_returns_none_on_select(self, tmp_path: Path):
        (tmp_path / "only_a_file.txt").write_text("hello")
        console, buf = _make_console()
        selector = FolderSelector(tmp_path, console=console)

        result = selector.select()
        assert result is None
        assert "No selectable folders found" in buf.getvalue()


class TestFolderSelectorInteraction:
    """Deterministic interaction tests using dependency-injected key_reader."""

    def test_navigate_toggle_and_confirm(self, tmp_path: Path):
        for name in ("Alpha", "Beta", "Gamma"):
            (tmp_path / name).mkdir()

        console, _ = _make_console()
        selector = FolderSelector(
            tmp_path,
            console=console,
            key_reader=_scripted_keys(
                KeyAction.DOWN,    # cursor -> Beta
                KeyAction.TOGGLE,  # select Beta
                KeyAction.DOWN,    # cursor -> Gamma
                KeyAction.TOGGLE,  # select Gamma
                KeyAction.UP,      # cursor -> Beta
                KeyAction.CONFIRM,
            ),
        )

        meta = selector.select()
        assert meta is not None
        assert meta.command_option == "--select"
        assert meta.source_root == str(tmp_path)
        assert meta.available_folders == ["Alpha", "Beta", "Gamma"]
        assert meta.selected_folders == ["Beta", "Gamma"]
        assert meta.excluded_folders_count == 0
        assert len(meta.workflow_steps) >= 3

    def test_toggle_all_selects_then_deselects(self, tmp_path: Path):
        for name in ("Docs", "Photos", "Projects"):
            (tmp_path / name).mkdir()

        console, _ = _make_console()
        selector = FolderSelector(
            tmp_path,
            console=console,
            key_reader=_scripted_keys(
                KeyAction.TOGGLE_ALL,  # select all 3
                KeyAction.TOGGLE_ALL,  # deselect all 3
                KeyAction.TOGGLE,      # select Docs
                KeyAction.CONFIRM,
            ),
        )

        meta = selector.select()
        assert meta is not None
        assert meta.selected_folders == ["Docs"]

    def test_empty_selection_guard_blocks_confirm_until_folder_selected(self, tmp_path: Path):
        (tmp_path / "Work").mkdir()
        console, buf = _make_console()
        selector = FolderSelector(
            tmp_path,
            console=console,
            key_reader=_scripted_keys(
                KeyAction.CONFIRM,  # blocked: 0 selected -> shows inline error
                KeyAction.TOGGLE,   # select Work
                KeyAction.CONFIRM,  # now succeeds
            ),
        )

        meta = selector.select()
        assert meta is not None
        assert meta.selected_folders == ["Work"]
        # Verify the inline validation message was rendered before recovery
        rendered = selector._render(
            [FolderItem(name="Work", path=tmp_path / "Work")],
            cursor=0,
            scroll_offset=0,
            visible_rows=5,
            error_msg="Please select at least one folder before pressing Enter.",
        )
        render_console, render_buf = _make_console()
        render_console.print(rendered)
        assert "Please select at least one folder" in render_buf.getvalue()

    def test_cancel_returns_none(self, tmp_path: Path):
        (tmp_path / "Work").mkdir()
        console, _ = _make_console()
        selector = FolderSelector(
            tmp_path,
            console=console,
            key_reader=_scripted_keys(KeyAction.TOGGLE, KeyAction.CANCEL),
        )

        assert selector.select() is None

    def test_viewport_scrolling_shows_above_and_below_indicators(self, tmp_path: Path):
        for i in range(25):
            (tmp_path / f"Folder_{i:02d}").mkdir()

        console, _ = _make_console()
        selector = FolderSelector(tmp_path, console=console, max_visible=5)
        items, _ = selector.discover_folders()

        # Top of list: should show "20 more below", no "more above"
        top_console, top_buf = _make_console()
        top_console.print(selector._render(items, cursor=0, scroll_offset=0, visible_rows=5))
        top_out = top_buf.getvalue()
        assert "20 more below" in top_out
        assert "more above" not in top_out

        # Middle of list: should show both "10 more above" and "10 more below"
        mid_console, mid_buf = _make_console()
        mid_console.print(selector._render(items, cursor=12, scroll_offset=10, visible_rows=5))
        mid_out = mid_buf.getvalue()
        assert "10 more above" in mid_out
        assert "10 more below" in mid_out

    def test_rich_markup_escaping_prevents_injection_and_crash(self, tmp_path: Path):
        evil_name = "[bold red]Evil[red]"
        bracket_name = "Projects [2026]"
        (tmp_path / evil_name).mkdir()
        (tmp_path / bracket_name).mkdir()

        console, _ = _make_console()
        selector = FolderSelector(
            tmp_path,
            console=console,
            key_reader=_scripted_keys(KeyAction.TOGGLE, KeyAction.CONFIRM),
        )
        items, _ = selector.discover_folders()

        # Also test a closing-tag markup string (containing '/') directly via _render
        closing_tag_item = FolderItem(
            name="[bold red]Closed[/bold red]", path=tmp_path / "placeholder"
        )
        render_console, render_buf = _make_console()
        render_console.print(
            selector._render(items + [closing_tag_item], cursor=0, scroll_offset=0, visible_rows=5)
        )
        rendered = render_buf.getvalue()
        assert "[bold red]Evil[red]/" in rendered
        assert "Projects [2026]/" in rendered
        assert "[bold red]Closed[/bold red]/" in rendered

        meta = selector.select()
        assert meta is not None
        assert meta.selected_folders == [evil_name]

    def test_ascii_fallback_on_cp1252_console(self, tmp_path: Path):
        (tmp_path / "Notes").mkdir()

        class _Cp1252Stream(io.StringIO):
            encoding = "cp1252"

        stream = _Cp1252Stream()
        console = Console(file=stream, width=100, height=25, force_terminal=False, highlight=False)
        selector = FolderSelector(tmp_path, console=console)
        items, _ = selector.discover_folders()
        items[0].selected = True

        panel = selector._render(items, cursor=0, scroll_offset=0, visible_rows=5)
        console.print(panel)
        output = stream.getvalue()
        # Must encode cleanly in cp1252 without UnicodeEncodeError
        output.encode("cp1252")
        assert "> [x] Notes/" in output


class TestReadKeyPlatform:
    """Tests for low-level POSIX termios restoration & escape disambiguation and Windows msvcrt."""

    def test_posix_termios_always_restored_even_on_exception(self, monkeypatch):
        fake_termios = types.SimpleNamespace(
            TCSADRAIN=1,
            tcgetattr=MagicMock(return_value=["SAVED_ATTRS"]),
            tcsetattr=MagicMock(),
        )
        fake_tty = types.SimpleNamespace(setcbreak=MagicMock())
        fake_select = types.SimpleNamespace(select=MagicMock(return_value=([], [], [])))

        monkeypatch.setitem(sys.modules, "termios", fake_termios)
        monkeypatch.setitem(sys.modules, "tty", fake_tty)
        monkeypatch.setitem(sys.modules, "select", fake_select)
        monkeypatch.setattr(sys, "stdin", MagicMock(fileno=MagicMock(return_value=7)))

        with patch("os.read", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                _read_key_posix()

        fake_tty.setcbreak.assert_called_once_with(7)
        fake_termios.tcsetattr.assert_called_once_with(7, 1, ["SAVED_ATTRS"])

    def test_posix_escape_disambiguation_bare_esc_vs_arrows(self, monkeypatch):
        fake_termios = types.SimpleNamespace(
            TCSADRAIN=1,
            tcgetattr=MagicMock(return_value=["OLD"]),
            tcsetattr=MagicMock(),
        )
        fake_tty = types.SimpleNamespace(setcbreak=MagicMock())
        monkeypatch.setitem(sys.modules, "termios", fake_termios)
        monkeypatch.setitem(sys.modules, "tty", fake_tty)
        monkeypatch.setattr(sys, "stdin", MagicMock(fileno=MagicMock(return_value=0)))

        # Bare ESC: select returns empty list after 50ms -> CANCEL
        monkeypatch.setitem(
            sys.modules, "select", types.SimpleNamespace(select=MagicMock(return_value=([], [], [])))
        )
        with patch("os.read", side_effect=[b"\x1b"]):
            assert _read_key_posix() == KeyAction.CANCEL

        # Up arrow (\x1b[A) -> UP
        monkeypatch.setitem(
            sys.modules,
            "select",
            types.SimpleNamespace(select=MagicMock(side_effect=[([0], [], []), ([0], [], [])])),
        )
        with patch("os.read", side_effect=[b"\x1b", b"[", b"A"]):
            assert _read_key_posix() == KeyAction.UP

        # Down arrow (\x1b[B) -> DOWN
        monkeypatch.setitem(
            sys.modules,
            "select",
            types.SimpleNamespace(select=MagicMock(side_effect=[([0], [], []), ([0], [], [])])),
        )
        with patch("os.read", side_effect=[b"\x1b", b"[", b"B"]):
            assert _read_key_posix() == KeyAction.DOWN

    def test_windows_msvcrt_key_mapping(self, monkeypatch):
        keys = iter(["\xe0", "H", "\xe0", "P", " ", "a", "\r", "\x1b", "q"])
        fake_msvcrt = types.SimpleNamespace(getwch=lambda: next(keys))
        monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)

        assert _read_key_windows() == KeyAction.UP
        assert _read_key_windows() == KeyAction.DOWN
        assert _read_key_windows() == KeyAction.TOGGLE
        assert _read_key_windows() == KeyAction.TOGGLE_ALL
        assert _read_key_windows() == KeyAction.CONFIRM
        assert _read_key_windows() == KeyAction.CANCEL
        assert _read_key_windows() == KeyAction.CANCEL
