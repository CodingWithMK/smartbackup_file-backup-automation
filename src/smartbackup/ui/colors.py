"""
Colors - ANSI color codes for terminal output.

Provides backward-compatible color constants alongside a shared Rich console
instance used by the modernised UI layer.
"""

from rich.console import Console
from rich.theme import Theme

# Shared Rich theme matching the legacy colour names
_smartbackup_theme = Theme(
    {
        "header": "magenta",
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "accent": "cyan",
        "muted": "dim",
    }
)

# Module-level Rich console singleton
console = Console(theme=_smartbackup_theme, highlight=False)


class Colors:
    """ANSI Color Codes for Terminal Output (Cross-Platform).

    Retained for backward compatibility.  New code should prefer the module-level
    ``console`` (a ``rich.console.Console`` instance) instead.
    """

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        """Disables colors for unsupported terminals."""
        cls.HEADER = cls.BLUE = cls.CYAN = cls.GREEN = ""
        cls.YELLOW = cls.RED = cls.BOLD = cls.UNDERLINE = cls.END = ""
