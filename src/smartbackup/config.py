"""
Config - Configuration classes and constants for SmartBackup.
"""

import json
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from smartbackup.models import SelectionMetadata

if TYPE_CHECKING:
    from smartbackup.ui.logger import BackupLogger

# Default exclusions for developer projects
DEFAULT_EXCLUSIONS: set[str] = {
    # Node.js / JavaScript
    "node_modules",
    ".npm",
    ".yarn",
    "bower_components",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".parcel-cache",
    # Python
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    "venv",
    ".venv",
    "env",
    ".env",
    "ENV",
    ".eggs",
    "*.egg-info",
    ".Python",
    "pip-wheel-metadata",
    ".pytype",
    # Virtual Environments (generic)
    "virtualenv",
    ".virtualenv",
    "pipenv",
    ".pipenv",
    "conda-env",
    ".conda",
    # Java / Kotlin / Scala
    "target",
    ".gradle",
    ".m2",
    # .NET / C#
    "bin",
    "obj",
    "packages",
    # Rust
    # "target",  # Already listed above
    # Go
    "vendor",
    # IDE and Editor
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    ".project",
    ".settings",
    ".classpath",
    # Version Control
    ".git",
    ".svn",
    ".hg",
    # OS-specific
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    # Temporary files
    "*.tmp",
    "*.temp",
    "*.log",
    "*.bak",
    "~*",
    # Cache general
    ".cache",
    "cache",
    ".sass-cache",
    # Docker
    ".docker",
}

# File extensions that should always be skipped
EXCLUDED_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",  # Python compiled
    ".class",  # Java compiled
    ".o",
    ".obj",
    ".exe",  # C/C++ compiled
    ".dll",
    ".so",
    ".dylib",  # Shared libraries
    ".log",
    ".tmp",
    ".temp",  # Temporary
}


@dataclass
class BackupConfig:
    """Configuration for the backup system."""

    source_path: Path
    backup_path: Path
    backup_folder_name: str = "Documents-Backup"
    device_name: str = ""  # Device identifier for per-device subfolder
    exclusions: set[str] = field(default_factory=lambda: DEFAULT_EXCLUSIONS.copy())
    excluded_extensions: set[str] = field(default_factory=lambda: EXCLUDED_EXTENSIONS.copy())
    max_workers: int = 4
    use_hash_verification: bool = False  # Enable SHA-256 hashing for change detection
    hash_all_files: bool = False  # Hash all files regardless of size (requires use_hash_verification)
    max_file_size_for_hash: int = 50 * 1024 * 1024  # 50MB - only hash files up to this size
    log_to_file: bool = True
    verbose: bool = True
    # Manifest options
    use_manifest: bool = True  # Use manifest for faster incremental backups
    manifest_format: str = "json"  # "json" or "sqlite"
    # Compression options
    compress_format: Optional[str] = None  # None (no compression), "zip", or "tar.gz"
    # Watcher options
    auto_watch_cooldown: int = 300  # Default debounce cooldown in seconds (5 minutes)
    # Selective folder backup options (--select)
    backup_mode: str = "full"  # "full" or "select"
    selected_folders: Optional[list[str]] = None
    selection_metadata: Optional[SelectionMetadata] = None

    def __post_init__(self) -> None:
        """Normalize backup_mode when selected_folders are explicitly supplied."""
        if self.selected_folders is not None and self.backup_mode == "full":
            self.backup_mode = "select"


class ConfigManager:
    """
    Manages persistent configuration.

    Stores settings in:
    - Windows: %APPDATA%/SmartBackup/config.json
    - macOS/Linux: ~/.config/smartbackup/config.json
    """

    def __init__(self, logger: Optional["BackupLogger"] = None) -> None:
        self.logger = logger
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"

    def _warn(self, message: str) -> None:
        """Emit a warning via the injected logger, or stderr as fallback."""
        if self.logger is not None:
            self.logger.warning(message)
        else:
            print(f"Warning: {message}", file=sys.stderr)

    def _get_config_dir(self) -> Path:
        """Determines the configuration directory."""
        system = platform.system()

        if system == "Windows":
            base = Path(os.environ.get("APPDATA", str(Path.home())))
            return base / "SmartBackup"
        else:
            return Path.home() / ".config" / "smartbackup"

    def _is_corrupt_config_file(self) -> bool:
        """Return True if config_file exists on disk but is not a valid JSON object."""
        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = json.load(f)
            return not isinstance(data, dict)
        except FileNotFoundError:
            return False
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return True

    def _backup_corrupt_config(self) -> Optional[Path]:
        """Preserve a corrupt config.json before overwriting it."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_dir / f"{self.config_file.name}.corrupt.{timestamp}"
        counter = 1
        while backup_path.exists():
            backup_path = (
                self.config_dir / f"{self.config_file.name}.corrupt.{timestamp}.{counter}"
            )
            counter += 1

        try:
            shutil.copy2(self.config_file, backup_path)
            self._warn(f"Preserved corrupt configuration backup at: {backup_path}")
            return backup_path
        except OSError as e:
            self._warn(f"Could not back up corrupt configuration {self.config_file}: {e}")
            return None

    def load(self) -> dict:
        """Loads the configuration, warning visibly on corrupt or unreadable files."""
        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            self._warn(f"Failed to load configuration from {self.config_file}: {e}")
            return {}

        if not isinstance(data, dict):
            self._warn(
                f"Invalid configuration in {self.config_file}: "
                f"expected JSON object, got {type(data).__name__}"
            )
            return {}

        return data

    def save(self, config: dict) -> None:
        """Atomically saves the configuration, preserving any corrupt existing file first."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self._is_corrupt_config_file():
            self._backup_corrupt_config()

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.config_dir,
                prefix="config.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = Path(f.name)
                json.dump(config, f, indent=2, default=str)
                f.flush()
            temp_path.replace(self.config_file)
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    @staticmethod
    def _extract_exclusions(config: dict) -> set[str]:
        """Safely extract custom exclusions list from loaded config."""
        raw = config.get("exclusions")
        if isinstance(raw, list):
            return {str(item) for item in raw}
        return set()

    def get_exclusions(self) -> set[str]:
        """Loads custom exclusions."""
        config = self.load()
        custom = self._extract_exclusions(config)
        return DEFAULT_EXCLUSIONS | custom

    def add_exclusion(self, pattern: str) -> None:
        """Adds an exclusion."""
        config = self.load()
        exclusions = self._extract_exclusions(config)
        exclusions.add(pattern)
        config["exclusions"] = list(exclusions)
        self.save(config)

    def remove_exclusion(self, pattern: str) -> None:
        """Removes an exclusion pattern (no-op when it is absent)."""
        config = self.load()
        exclusions = self._extract_exclusions(config)
        exclusions.discard(pattern)
        config["exclusions"] = list(exclusions)
        self.save(config)

    def unset(self, key: str) -> None:
        """Removes a configuration key so its default applies again."""
        config = self.load()
        config.pop(key, None)
        self.save(config)

    def set_preferred_target(self, label: str) -> None:
        """Saves preferred target medium."""
        config = self.load()
        config["preferred_target"] = label
        self.save(config)

    def get_preferred_target(self) -> Optional[str]:
        """Loads preferred target medium."""
        config = self.load()
        return config.get("preferred_target")

    def set_device_name(self, name: str) -> None:
        """Save a custom device name override."""
        config = self.load()
        config["device_name"] = name
        self.save(config)

    def get_device_name(self) -> Optional[str]:
        """Load custom device name (None = use auto-detected hostname)."""
        config = self.load()
        return config.get("device_name")

    def set_auto_watch_cooldown(self, seconds: int) -> None:
        """Save auto-watch debounce cooldown in seconds."""
        config = self.load()
        config["auto_watch_cooldown"] = seconds
        self.save(config)

    def get_auto_watch_cooldown(self) -> int:
        """Load auto-watch debounce cooldown in seconds (default 300)."""
        config = self.load()
        return int(config.get("auto_watch_cooldown", 300))

    def set_preferred_terminal(self, terminal: str) -> None:
        """Save preferred terminal emulator application."""
        config = self.load()
        config["preferred_terminal"] = terminal
        self.save(config)

    def get_preferred_terminal(self) -> Optional[str]:
        """Load preferred terminal emulator application."""
        config = self.load()
        return config.get("preferred_terminal")

    def set_manifest_format(self, fmt: str) -> None:
        """Save preferred manifest storage format ('json' or 'sqlite')."""
        config = self.load()
        config["manifest_format"] = fmt
        self.save(config)

    def get_manifest_format(self) -> str:
        """Load preferred manifest storage format (default 'json')."""
        config = self.load()
        value = config.get("manifest_format", "json")
        return str(value) if value else "json"
