"""
Config - Configuration classes and constants for SmartBackup.
"""

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set

# Default exclusions for developer projects
DEFAULT_EXCLUSIONS: Set[str] = {
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
EXCLUDED_EXTENSIONS: Set[str] = {
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
    exclusions: Set[str] = field(default_factory=lambda: DEFAULT_EXCLUSIONS.copy())
    excluded_extensions: Set[str] = field(default_factory=lambda: EXCLUDED_EXTENSIONS.copy())
    max_workers: int = 4
    use_hash_verification: bool = False  # Faster without, more accurate with
    min_file_size_for_hash: int = 1024 * 1024  # 1MB - only hash large files
    log_to_file: bool = True
    verbose: bool = True
    # Manifest options
    use_manifest: bool = True  # Use manifest for faster incremental backups
    manifest_format: str = "json"  # "json" or "sqlite" (future)


class ConfigManager:
    """
    Manages persistent configuration.

    Stores settings in:
    - Windows: %APPDATA%/SmartBackup/config.json
    - macOS/Linux: ~/.config/smartbackup/config.json
    """

    def __init__(self) -> None:
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"

    def _get_config_dir(self) -> Path:
        """Determines the configuration directory."""
        system = platform.system()

        if system == "Windows":
            base = Path(os.environ.get("APPDATA", str(Path.home())))
            return base / "SmartBackup"
        else:
            return Path.home() / ".config" / "smartbackup"

    def load(self) -> dict:
        """Loads the configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save(self, config: dict) -> None:
        """Saves the configuration."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, default=str)

    def get_exclusions(self) -> Set[str]:
        """Loads custom exclusions."""
        config = self.load()
        custom = set(config.get("exclusions", []))
        return DEFAULT_EXCLUSIONS | custom

    def add_exclusion(self, pattern: str) -> None:
        """Adds an exclusion."""
        config = self.load()
        exclusions = set(config.get("exclusions", []))
        exclusions.add(pattern)
        config["exclusions"] = list(exclusions)
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
