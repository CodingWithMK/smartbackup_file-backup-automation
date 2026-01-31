"""
Scanner - File scanning and exclusion filtering.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from smartbackup.models import FileInfo
from smartbackup.ui.logger import BackupLogger


class ExclusionFilter:
    """
    Filters files and folders based on exclusion rules.

    Supports:
    - Exact names
    - Wildcards (*.ext)
    - Regex patterns (optional)
    """

    def __init__(self, exclusions: Set[str], excluded_extensions: Set[str]):
        self.exact_matches: Set[str] = set()
        self.patterns: List[re.Pattern[str]] = []
        self.excluded_extensions = {ext.lower() for ext in excluded_extensions}

        for excl in exclusions:
            if "*" in excl or "?" in excl:
                # Convert glob pattern to regex
                regex = excl.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                self.patterns.append(re.compile(f"^{regex}$", re.IGNORECASE))
            else:
                self.exact_matches.add(excl.lower())

    def should_exclude(self, path: Path) -> Tuple[bool, str]:
        """
        Checks if a path should be excluded.

        Returns:
            Tuple (should_be_excluded, reason)
        """
        name = path.name.lower()

        # Exact match
        if name in self.exact_matches:
            return True, f"Exact match: {name}"

        # Check file extension
        if path.suffix.lower() in self.excluded_extensions:
            return True, f"Excluded extension: {path.suffix}"

        # Pattern match
        for pattern in self.patterns:
            if pattern.match(name):
                return True, f"Pattern match: {pattern.pattern}"

        # Special check for virtual environments
        if self._is_virtual_env(path):
            return True, "Virtual environment detected"

        return False, ""

    def _is_virtual_env(self, path: Path) -> bool:
        """Detects virtual environments by their structure."""
        if not path.is_dir():
            return False

        # Python venv indicators
        venv_indicators = [
            path / "pyvenv.cfg",
            path / "Scripts" / "activate",  # Windows
            path / "bin" / "activate",  # Unix
            path / "Scripts" / "python.exe",
            path / "bin" / "python",
            path / "lib" / "python3",  # Standard venv structure
        ]

        return any(indicator.exists() for indicator in venv_indicators[:6])


class FileScanner:
    """
    Scans the filesystem and collects file information.

    Features:
    - Efficient recursive scanning
    - Integrated filtering
    - Optional hashing for large files
    """

    def __init__(
        self,
        exclusion_filter: ExclusionFilter,
        logger: BackupLogger,
        use_hash: bool = False,
        min_size_for_hash: int = 1024 * 1024,
    ):
        self.filter = exclusion_filter
        self.logger = logger
        self.use_hash = use_hash
        self.min_size_for_hash = min_size_for_hash
        self._scan_count = 0
        self._excluded_count = 0

    def scan(self, base_path: Path) -> Dict[Path, FileInfo]:
        """
        Scans a directory recursively.

        Args:
            base_path: Base directory to scan

        Returns:
            Dictionary with relative paths as keys and FileInfo as values
        """
        self.logger.section(f"Scanning source directory: {base_path}")
        self._scan_count = 0
        self._excluded_count = 0

        files: Dict[Path, FileInfo] = {}

        try:
            self._scan_recursive(base_path, base_path, files)
        except PermissionError as e:
            self.logger.error(f"Permission denied: {e}")
        except Exception as e:
            self.logger.error(f"Scan error: {e}")

        self.logger.info(
            f"Scan completed: {self._scan_count} files found, {self._excluded_count} excluded"
        )

        return files

    def _scan_recursive(
        self, current_path: Path, base_path: Path, files: Dict[Path, FileInfo]
    ) -> None:
        """Recursive scan implementation."""
        try:
            with os.scandir(current_path) as entries:
                for entry in entries:
                    try:
                        path = Path(entry.path)

                        # Check exclusion
                        should_exclude, reason = self.filter.should_exclude(path)
                        if should_exclude:
                            self._excluded_count += 1
                            if entry.is_dir():
                                # Skip entire folder
                                continue
                            else:
                                continue

                        if entry.is_dir(follow_symlinks=False):
                            # Recursively enter subdirectory
                            self._scan_recursive(path, base_path, files)

                        elif entry.is_file(follow_symlinks=False):
                            self._scan_count += 1

                            # Show progress
                            if self._scan_count % 100 == 0:
                                self.logger.progress(
                                    self._scan_count,
                                    self._scan_count,  # Unknown total
                                    str(path.name),
                                )

                            stat = entry.stat()
                            relative_path = path.relative_to(base_path)

                            # Optional: Calculate hash
                            file_hash = None
                            if self.use_hash and stat.st_size >= self.min_size_for_hash:
                                file_hash = self._calculate_hash(path)

                            files[relative_path] = FileInfo(
                                path=path,
                                relative_path=relative_path,
                                size=stat.st_size,
                                mtime=stat.st_mtime,
                                file_hash=file_hash,
                            )

                    except PermissionError:
                        self._excluded_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error at {entry.path}: {e}")

        except PermissionError:
            self.logger.warning(f"Permission denied for: {current_path}")

    def _calculate_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Calculates MD5 hash of a file (fast, not cryptographically secure)."""
        hasher = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
