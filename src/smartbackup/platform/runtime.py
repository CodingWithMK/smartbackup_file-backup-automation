"""
Runtime helpers for standalone (PyInstaller frozen) vs Python-interpreter execution
and cross-platform UTF-8 console output.
"""

import sys
from typing import Optional


def is_frozen_binary() -> bool:
    """Return True when running from a frozen standalone executable (e.g., PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def build_cli_command(*args: str, python_exe: Optional[str] = None) -> list[str]:
    """
    Build an argv list to invoke SmartBackup.

    When running as a frozen standalone binary (and no explicit ``python_exe``
    override is supplied), invokes the executable directly without ``-m smartbackup``.
    Otherwise invokes ``<python_exe> -m smartbackup ...``.
    """
    if python_exe is None and is_frozen_binary():
        return [sys.executable, *args]
    exe = python_exe or sys.executable
    return [exe, "-m", "smartbackup", *args]


def ensure_utf8_console() -> None:
    """
    Reconfigure stdout/stderr to UTF-8 on non-UTF-8 terminals (e.g., Windows cp1252).

    Safe no-op when streams do not support ``reconfigure`` (such as test buffers).
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        if encoding and encoding.lower().replace("-", "") != "utf8":
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass
