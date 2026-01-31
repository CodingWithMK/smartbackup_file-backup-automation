"""
Colors - ANSI color codes for terminal output.
"""


class Colors:
    """ANSI Color Codes for Terminal Output (Cross-Platform)."""

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
