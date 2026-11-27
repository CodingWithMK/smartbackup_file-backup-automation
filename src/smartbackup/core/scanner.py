"""
Scanner - File scanning and exclusion filtering.
"""

import fnmatch
import hashlib
import os
import re
from pathlib import Path
from typing import Optional

from smartbackup.models import FileInfo
from smartbackup.ui.logger import BackupLogger


def _compile_literal_glob(pattern: str, flags: int) -> re.Pattern[str]:
    """Compile a glob pattern treating ``*`` and ``?`` as wildcards and all other chars literally.

    Used as a crash-proof fallback when ``fnmatch.translate()`` produces an invalid
    regex character range (for example ``report[z-a]*``).
    """
    parts: list[str] = []
    for ch in pattern:
        if ch == "*":
            parts.append(".*")
        elif ch == "?":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    return re.compile(rf"(?s:{''.join(parts)})\Z", flags)


class ExclusionFilter:
    """
    Filters files and folders based on exclusion rules.

    Matching is case-insensitive by default for cross-platform developer
    convenience (Windows, macOS, and Linux). Pass ``case_sensitive=True`` to
    enforce case-sensitive matching on case-sensitive filesystems.

    Supports:
    - Exact names (matched literally, even when containing brackets like ``Archive [2026]``)
    - File extensions
    - Glob wildcards (``*``, ``?``, and valid ``[...]`` character classes via ``fnmatch``)
    - Automatic Python virtual environment detection
    """

    def __init__(
        self,
        exclusions: set[str],
        excluded_extensions: set[str],
        case_sensitive: bool = False,
        logger: Optional[BackupLogger] = None,
    ):
        self.case_sensitive = case_sensitive
        self.logger = logger
        self.exact_matches: set[str] = set()
        self.patterns: list[re.Pattern[str]] = []
        self.excluded_extensions = (
            set(excluded_extensions)
            if case_sensitive
            else {ext.lower() for ext in excluded_extensions}
        )

        flags = 0 if case_sensitive else re.IGNORECASE

        for excl in exclusions:
            if "*" in excl or "?" in excl:
                try:
                    self.patterns.append(re.compile(fnmatch.translate(excl), flags))
                except re.error as e:
                    if self.logger is not None:
                        self.logger.warning(
                            f"Exclusion pattern '{excl}' has invalid character class ({e}); "
                            "treating brackets literally."
                        )
                    self.patterns.append(_compile_literal_glob(excl, flags))
            else:
                self.exact_matches.add(excl if case_sensitive else excl.lower())

    def should_exclude(self, path: Path) -> tuple[bool, str]:
        """
        Checks if a path should be excluded.

        Returns:
            Tuple (should_be_excluded, reason)
        """
        raw_name = path.name
        name = raw_name if self.case_sensitive else raw_name.lower()

        # Exact match
        if name in self.exact_matches:
            return True, f"Exact match: {name}"

        # Check file extension
        suffix = path.suffix if self.case_sensitive else path.suffix.lower()
        if suffix in self.excluded_extensions:
            return True, f"Excluded extension: {path.suffix}"

        # Pattern match
        for pattern in self.patterns:
            if pattern.match(raw_name):
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

        return any(indicator.exists() for indicator in venv_indicators)


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
        hash_all: bool = False,
        max_size_for_hash: int = 50 * 1024 * 1024,  # 50MB
    ):
        self.filter = exclusion_filter
        self.logger = logger
        self.use_hash = use_hash
        self.hash_all = hash_all
        self.max_size_for_hash = max_size_for_hash
        self._scan_count = 0
        self._excluded_count = 0

    def scan(
        self,
        base_path: Path,
        include_folders: Optional[list[str]] = None,
    ) -> dict[Path, FileInfo]:
        """
        Scans a directory recursively.

        Args:
            base_path: Base directory to scan
            include_folders: Optional list of top-level folder names under
                ``base_path`` to restrict scanning to (used by ``--select``).
                All collected ``FileInfo.relative_path`` values remain relative
                to ``base_path``.

        Returns:
            Dictionary with relative paths as keys and FileInfo as values
        """
        self._scan_count = 0
        self._excluded_count = 0

        files: dict[Path, FileInfo] = {}

        if include_folders is not None:
            self.logger.section(
                f"Scanning selected folders ({len(include_folders)}) in: {base_path}"
            )
            for folder_name in include_folders:
                folder_path = base_path / folder_name
                if not folder_path.exists() or not folder_path.is_dir():
                    self.logger.warning(f"Selected folder not found, skipping: {folder_name}")
                    continue
                try:
                    self._scan_recursive(folder_path, base_path, files)
                except PermissionError as e:
                    self.logger.error(f"Permission denied: {e}")
                except Exception as e:
                    self.logger.error(f"Scan error in '{folder_name}': {e}")
        else:
            self.logger.section(f"Scanning source directory: {base_path}")
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
        self, current_path: Path, base_path: Path, files: dict[Path, FileInfo]
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
                            file_hash: Optional[str] = None
                            hash_error = False
                            if self.use_hash:
                                if self.hash_all or stat.st_size <= self.max_size_for_hash:
                                    file_hash = self._calculate_hash(path)
                                    if file_hash is None:
                                        hash_error = True

                            files[relative_path] = FileInfo(
                                path=path,
                                relative_path=relative_path,
                                size=stat.st_size,
                                mtime=stat.st_mtime,
                                file_hash=file_hash,
                                hash_error=hash_error,
                            )

                    except PermissionError:
                        self._excluded_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error at {entry.path}: {e}")

        except PermissionError:
            self.logger.warning(f"Permission denied for: {current_path}")

    def _calculate_hash(self, path: Path, chunk_size: int = 65536) -> Optional[str]:
        """Calculate SHA-256 hash of a file for integrity verification.

        Returns ``None`` and logs a warning if the file cannot be read.
        """
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as e:
            self.logger.warning(f"Could not hash {path}: {e}")
            return None
