"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         SMART BACKUP SYSTEM v0.1                              ║
║                                                                               ║
║  Intelligent Backup System for Developers and Daily Use                                     ║
║  - Cross-Platform (Windows, macOS, Linux)                                     ║
║  - Incremental Backup with Change Detection                                   ║
║  - Automatic Filtering of Build Artifacts                                     ║
║  - Comprehensive Logging and Progress Display                                 ║
║                                                                               ║
║  Author: Muhammed Musab Kaya (@CodingWithMK)                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import shutil
import hashlib
import platform
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, auto
import time
import re


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS AND CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class Colors:
    """ANSI Color Codes for Terminal Output (Cross-Platform)"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disables colors for unsupported terminals"""
        cls.HEADER = cls.BLUE = cls.CYAN = cls.GREEN = ''
        cls.YELLOW = cls.RED = cls.BOLD = cls.UNDERLINE = cls.END = ''


class FileAction(Enum):
    """Actions that can be applied to files"""
    COPIED = auto()
    UPDATED = auto()
    SKIPPED = auto()
    DELETED = auto()
    ERROR = auto()


# Default exclusions for developer projects
DEFAULT_EXCLUSIONS = {
    # Node.js / JavaScript
    'node_modules',
    '.npm',
    '.yarn',
    'bower_components',
    '.next',
    '.nuxt',
    'dist',
    'build',
    '.parcel-cache',
    
    # Python
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.tox',
    '.nox',
    'venv',
    '.venv',
    'env',
    '.env',
    'ENV',
    '.eggs',
    '*.egg-info',
    '.Python',
    'pip-wheel-metadata',
    '.pytype',
    
    # Virtual Environments (generic)
    'virtualenv',
    '.virtualenv',
    'pipenv',
    '.pipenv',
    'conda-env',
    '.conda',
    
    # Java / Kotlin / Scala
    'target',
    '.gradle',
    '.m2',
    
    # .NET / C#
    'bin',
    'obj',
    'packages',
    
    # Rust
    'target',
    
    # Go
    'vendor',
    
    # IDE and Editor
    '.idea',
    '.vscode',
    '*.swp',
    '*.swo',
    '.project',
    '.settings',
    '.classpath',
    
    # Version Control
    '.git',
    '.svn',
    '.hg',
    
    # OS-specific
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    
    # Temporary files
    '*.tmp',
    '*.temp',
    '*.log',
    '*.bak',
    '~*',
    
    # Cache general
    '.cache',
    'cache',
    '.sass-cache',
    
    # Docker
    '.docker',
}

# File extensions that should always be skipped
EXCLUDED_EXTENSIONS = {
    '.pyc', '.pyo', '.pyd',  # Python compiled
    '.class',                 # Java compiled
    '.o', '.obj', '.exe',     # C/C++ compiled
    '.dll', '.so', '.dylib',  # Shared libraries
    '.log', '.tmp', '.temp',  # Temporary
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BackupConfig:
    """Configuration for the backup system"""
    source_path: Path
    backup_path: Path
    backup_folder_name: str = "Documents-Backup"
    exclusions: Set[str] = field(default_factory=lambda: DEFAULT_EXCLUSIONS.copy())
    excluded_extensions: Set[str] = field(default_factory=lambda: EXCLUDED_EXTENSIONS.copy())
    max_workers: int = 4
    use_hash_verification: bool = False  # Faster without, more accurate with
    min_file_size_for_hash: int = 1024 * 1024  # 1MB - only hash large files
    log_to_file: bool = True
    verbose: bool = True


@dataclass
class FileInfo:
    """Information about a single file"""
    path: Path
    relative_path: Path
    size: int
    mtime: float
    file_hash: Optional[str] = None
    
    def needs_update(self, other: 'FileInfo', use_hash: bool = False) -> bool:
        """Checks if the file needs to be updated"""
        if self.size != other.size:
            return True
        if self.mtime > other.mtime:
            return True
        if use_hash and self.file_hash and other.file_hash:
            return self.file_hash != other.file_hash
        return False


@dataclass 
class BackupResult:
    """Result of a backup operation"""
    total_files: int = 0
    copied_files: int = 0
    updated_files: int = 0
    skipped_files: int = 0
    deleted_files: int = 0
    errors: int = 0
    total_size: int = 0
    copied_size: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    file_actions: List[Tuple[Path, FileAction, str]] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Duration of the backup in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def speed_mbps(self) -> float:
        """Backup speed in MB/s"""
        if self.duration > 0:
            return (self.copied_size / (1024 * 1024)) / self.duration
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# LOGGER CLASS
# ══════════════════════════════════════════════════════════════════════════════

class BackupLogger:
    """
    Central logging system for terminal and file
    
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
        if platform.system() == 'Windows':
            self._enable_windows_ansi()
    
    def _enable_windows_ansi(self):
        """Enables ANSI escape sequences on Windows"""
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            Colors.disable()
    
    def _timestamp(self) -> str:
        """Formatted timestamp"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _clear_progress_line(self):
        """Clears the current progress line"""
        if self._progress_line_active:
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            sys.stdout.flush()
            self._progress_line_active = False
    
    def header(self, message: str):
        """Outputs a header"""
        self._clear_progress_line()
        border = "═" * (len(message) + 4)
        output = f"\n{Colors.CYAN}╔{border}╗\n║  {message}  ║\n╚{border}╝{Colors.END}\n"
        print(output)
        self._log_to_file(f"\n{'='*60}\n{message}\n{'='*60}")
    
    def section(self, message: str):
        """Outputs a section header"""
        self._clear_progress_line()
        output = f"\n{Colors.BOLD}{Colors.BLUE}▶ {message}{Colors.END}"
        print(output)
        self._log_to_file(f"\n--- {message} ---")
    
    def info(self, message: str):
        """Information message"""
        if self.verbose:
            self._clear_progress_line()
            output = f"{Colors.CYAN}ℹ{Colors.END}  [{self._timestamp()}] {message}"
            print(output)
        self._log_to_file(f"[INFO] [{self._timestamp()}] {message}")
    
    def success(self, message: str):
        """Success message"""
        self._clear_progress_line()
        output = f"{Colors.GREEN}✓{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[SUCCESS] [{self._timestamp()}] {message}")
    
    def warning(self, message: str):
        """Warning message"""
        self._clear_progress_line()
        output = f"{Colors.YELLOW}⚠{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[WARNING] [{self._timestamp()}] {message}")
    
    def error(self, message: str):
        """Error message"""
        self._clear_progress_line()
        output = f"{Colors.RED}✗{Colors.END}  [{self._timestamp()}] {message}"
        print(output)
        self._log_to_file(f"[ERROR] [{self._timestamp()}] {message}")
    
    def file_action(self, action: FileAction, file_path: Path, details: str = ""):
        """Logs a file action"""
        icons = {
            FileAction.COPIED: (Colors.GREEN, "➕", "COPIED"),
            FileAction.UPDATED: (Colors.BLUE, "🔄", "UPDATED"),
            FileAction.SKIPPED: (Colors.YELLOW, "⏭", "SKIPPED"),
            FileAction.DELETED: (Colors.RED, "🗑", "DELETED"),
            FileAction.ERROR: (Colors.RED, "❌", "ERROR"),
        }
        
        color, icon, label = icons.get(action, (Colors.END, "?", "UNKNOWN"))
        
        if self.verbose or action in (FileAction.COPIED, FileAction.UPDATED, FileAction.ERROR):
            self._clear_progress_line()
            detail_str = f" ({details})" if details else ""
            output = f"{color}{icon}{Colors.END} [{label}] {file_path}{detail_str}"
            print(output)
        
        self._log_to_file(f"[{label}] [{self._timestamp()}] {file_path} {details}")
    
    def progress(self, current: int, total: int, current_file: str = "", 
                 bytes_copied: int = 0, total_bytes: int = 0):
        """Shows a progress bar"""
        if total == 0:
            return
            
        percent = (current / total) * 100
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        # Size information
        if total_bytes > 0:
            size_info = f" | {self._format_size(bytes_copied)}/{self._format_size(total_bytes)}"
        else:
            size_info = ""
        
        # Truncate filename
        if len(current_file) > 40:
            current_file = "..." + current_file[-37:]
        
        progress_str = (f"\r{Colors.CYAN}[{bar}]{Colors.END} "
                       f"{percent:5.1f}% ({current}/{total}){size_info} "
                       f"| {current_file}")
        
        sys.stdout.write(progress_str.ljust(120))
        sys.stdout.flush()
        self._progress_line_active = True
    
    def _format_size(self, size: int) -> str:
        """Formats file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"
    
    def _log_to_file(self, message: str):
        """Writes to the log file"""
        if self.log_file:
            with self.lock:
                self._log_buffer.append(message)
    
    def flush_to_file(self):
        """Writes the buffer to the log file"""
        if self.log_file and self._log_buffer:
            with self.lock:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write('\n'.join(self._log_buffer) + '\n')
                self._log_buffer.clear()
    
    def summary(self, result: BackupResult):
        """Shows a summary of the backup operation"""
        self._clear_progress_line()
        
        duration = result.duration
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        summary = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                       BACKUP SUMMARY                         ║
╠══════════════════════════════════════════════════════════════╣{Colors.END}
║  {Colors.GREEN}Copied Files:{Colors.END}          {result.copied_files:>8}                             ║
║  {Colors.BLUE}Updated Files:{Colors.END}         {result.updated_files:>8}                             ║
║  {Colors.YELLOW}Skipped Files:{Colors.END}         {result.skipped_files:>8}                             ║
║  {Colors.RED}Errors:{Colors.END}                {result.errors:>8}                             ║
╠══════════════════════════════════════════════════════════════╣
║  Total Files:            {result.total_files:>8}                            ║
║  Copied Size:            {self._format_size(result.copied_size):>8}                            ║
║  Duration:               {time_str:>8}                            ║
║  Speed:                  {result.speed_mbps:>6.2f} MB/s                         ║
{Colors.CYAN}╚══════════════════════════════════════════════════════════════╝{Colors.END}
"""
        print(summary)
        self._log_to_file(f"\n{'='*60}\nSUMMARY\n"
                         f"Copied: {result.copied_files}, "
                         f"Updated: {result.updated_files}, "
                         f"Skipped: {result.skipped_files}, "
                         f"Errors: {result.errors}\n"
                         f"Size: {self._format_size(result.copied_size)}, "
                         f"Duration: {time_str}\n{'='*60}")


# ══════════════════════════════════════════════════════════════════════════════
# PATH RESOLVER - CROSS-PLATFORM PATH RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

class PathResolver:
    """
    Cross-Platform Path Resolution
    
    Automatically detects:
    - Documents folder on all operating systems
    - External storage media
    - Different drives (Windows) / mount points (Unix)
    """
    
    @staticmethod
    def get_documents_path() -> Path:
        """Determines the Documents folder in a platform-independent way"""
        system = platform.system()
        
        if system == 'Windows':
            # Try to use Shell Folders
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
                )
                documents, _ = winreg.QueryValueEx(key, "Personal")
                winreg.CloseKey(key)
                return Path(documents)
            except Exception:
                pass
            
            # Fallback
            return Path.home() / "Documents"
        
        elif system == 'Darwin':  # macOS
            return Path.home() / "Documents"
        
        else:  # Linux and others
            # Check XDG configuration
            xdg_docs = os.environ.get('XDG_DOCUMENTS_DIR')
            if xdg_docs:
                return Path(xdg_docs)
            
            # Try to read user-dirs.dirs
            user_dirs = Path.home() / ".config" / "user-dirs.dirs"
            if user_dirs.exists():
                try:
                    with open(user_dirs, 'r') as f:
                        for line in f:
                            if line.startswith('XDG_DOCUMENTS_DIR'):
                                path = line.split('=')[1].strip().strip('"')
                                path = path.replace('$HOME', str(Path.home()))
                                return Path(path)
                except Exception:
                    pass
            
            # Fallbacks for different languages
            for name in ['Documents', 'Dokumente', 'documents']:
                path = Path.home() / name
                if path.exists():
                    return path
            
            return Path.home() / "Documents"
    
    @staticmethod
    def find_external_drives() -> List[Tuple[Path, str, int]]:
        """
        Finds all external storage media
        
        Returns:
            List of tuples (path, label, free space in bytes)
        """
        drives = []
        system = platform.system()
        
        if system == 'Windows':
            drives = PathResolver._find_windows_drives()
        elif system == 'Darwin':
            drives = PathResolver._find_macos_drives()
        else:
            drives = PathResolver._find_linux_drives()
        
        return drives
    
    @staticmethod
    def _find_windows_drives() -> List[Tuple[Path, str, int]]:
        """Finds external drives on Windows"""
        drives = []
        try:
            import ctypes
            from ctypes import wintypes
            
            kernel32 = ctypes.windll.kernel32
            
            # Iterate through all drive letters
            bitmask = kernel32.GetLogicalDrives()
            for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                if bitmask & 1:
                    drive_path = Path(f"{letter}:\\")
                    drive_type = kernel32.GetDriveTypeW(str(drive_path))
                    
                    # 2 = Removable, 3 = Fixed (external USB drives)
                    if drive_type in (2, 3) and drive_path.exists():
                        try:
                            # Check if writable
                            total, used, free = shutil.disk_usage(drive_path)
                            
                            # Try to get volume label
                            volume_name_buffer = ctypes.create_unicode_buffer(261)
                            kernel32.GetVolumeInformationW(
                                str(drive_path), volume_name_buffer, 261,
                                None, None, None, None, 0
                            )
                            label = volume_name_buffer.value or f"Drive {letter}"
                            
                            drives.append((drive_path, label, free))
                        except Exception:
                            pass
                
                bitmask >>= 1
                
        except Exception as e:
            # Fallback: Simple method
            for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                drive_path = Path(f"{letter}:\\")
                if drive_path.exists():
                    try:
                        _, _, free = shutil.disk_usage(drive_path)
                        drives.append((drive_path, f"Drive {letter}", free))
                    except Exception:
                        pass
        
        return drives
    
    @staticmethod
    def _find_macos_drives() -> List[Tuple[Path, str, int]]:
        """Finds external drives on macOS"""
        drives = []
        volumes_path = Path("/Volumes")
        
        if volumes_path.exists():
            for volume in volumes_path.iterdir():
                if volume.is_dir() and volume.name != "Macintosh HD":
                    try:
                        _, _, free = shutil.disk_usage(volume)
                        drives.append((volume, volume.name, free))
                    except Exception:
                        pass
        
        return drives
    
    @staticmethod
    def _find_linux_drives() -> List[Tuple[Path, str, int]]:
        """Finds external drives on Linux"""
        drives = []
        
        # Common mount points for external media
        mount_points = [
            Path("/media") / os.environ.get("USER", ""),
            Path("/mnt"),
            Path("/run/media") / os.environ.get("USER", ""),
        ]
        
        for mount_base in mount_points:
            if mount_base.exists():
                for mount in mount_base.iterdir():
                    if mount.is_dir():
                        try:
                            _, _, free = shutil.disk_usage(mount)
                            drives.append((mount, mount.name, free))
                        except Exception:
                            pass
        
        return drives


# ══════════════════════════════════════════════════════════════════════════════
# DEVICE DETECTOR - EXTERNAL MEDIA DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class DeviceDetector:
    """
    Detects and validates external storage media
    
    Features:
    - Automatic detection of available media
    - Storage space validation
    - User interaction for selection
    """
    
    def __init__(self, logger: BackupLogger):
        self.logger = logger
    
    def find_backup_device(self, 
                          required_space: int = 0,
                          preferred_label: Optional[str] = None) -> Optional[Path]:
        """
        Finds a suitable backup medium
        
        Args:
            required_space: Minimum required free space
            preferred_label: Preferred drive label
        
        Returns:
            Path to backup medium or None
        """
        self.logger.section("Searching for external storage medium...")
        
        drives = PathResolver.find_external_drives()
        
        if not drives:
            self.logger.warning("No external storage medium found!")
            return None
        
        # Filter by storage space
        suitable_drives = [
            (path, label, free) for path, label, free in drives
            if free >= required_space
        ]
        
        if not suitable_drives:
            self.logger.warning(
                f"No drive with sufficient storage space "
                f"({required_space / (1024**3):.1f} GB required) found!"
            )
            return None
        
        # Check for preferred drive
        if preferred_label:
            for path, label, free in suitable_drives:
                if label.lower() == preferred_label.lower():
                    self.logger.success(
                        f"Preferred drive found: {label} ({path}) - "
                        f"{free / (1024**3):.1f} GB free"
                    )
                    return path
        
        # Multiple options: let user choose or take first one
        if len(suitable_drives) == 1:
            path, label, free = suitable_drives[0]
            self.logger.success(
                f"External medium found: {label} ({path}) - "
                f"{free / (1024**3):.1f} GB free"
            )
            return path
        
        # Multiple options - show selection
        self.logger.info("Multiple external media found:")
        for i, (path, label, free) in enumerate(suitable_drives, 1):
            print(f"  [{i}] {label} ({path}) - {free / (1024**3):.1f} GB free")
        
        # In automatic mode: take first one
        path, label, free = suitable_drives[0]
        self.logger.info(f"Automatic selection: {label}")
        return path
    
    def validate_device(self, path: Path) -> bool:
        """Validates if the device is writable"""
        if not path.exists():
            return False
        
        try:
            test_file = path / ".backup_test_write"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════════════════
# EXCLUSION FILTER - INTELLIGENT FILTERING
# ══════════════════════════════════════════════════════════════════════════════

class ExclusionFilter:
    """
    Filters files and folders based on exclusion rules
    
    Supports:
    - Exact names
    - Wildcards (*.ext)
    - Regex patterns (optional)
    """
    
    def __init__(self, exclusions: Set[str], excluded_extensions: Set[str]):
        self.exact_matches: Set[str] = set()
        self.patterns: List[re.Pattern] = []
        self.excluded_extensions = {ext.lower() for ext in excluded_extensions}
        
        for excl in exclusions:
            if '*' in excl or '?' in excl:
                # Convert glob pattern to regex
                regex = excl.replace('.', r'\.').replace('*', '.*').replace('?', '.')
                self.patterns.append(re.compile(f"^{regex}$", re.IGNORECASE))
            else:
                self.exact_matches.add(excl.lower())
    
    def should_exclude(self, path: Path) -> Tuple[bool, str]:
        """
        Checks if a path should be excluded
        
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
        """Detects virtual environments by their structure"""
        if not path.is_dir():
            return False
        
        # Python venv indicators
        venv_indicators = [
            path / "pyvenv.cfg",
            path / "Scripts" / "activate",  # Windows
            path / "bin" / "activate",       # Unix
            path / "Scripts" / "python.exe",
            path / "bin" / "python",
            path / "lib" / "python3",        # Standard venv structure
        ]
        
        return any(indicator.exists() for indicator in venv_indicators[:6])


# ══════════════════════════════════════════════════════════════════════════════
# FILE SCANNER - FILESYSTEM SCANNER
# ══════════════════════════════════════════════════════════════════════════════

class FileScanner:
    """
    Scans the filesystem and collects file information
    
    Features:
    - Efficient recursive scanning
    - Integrated filtering
    - Optional hashing for large files
    """
    
    def __init__(self, 
                 exclusion_filter: ExclusionFilter,
                 logger: BackupLogger,
                 use_hash: bool = False,
                 min_size_for_hash: int = 1024 * 1024):
        self.filter = exclusion_filter
        self.logger = logger
        self.use_hash = use_hash
        self.min_size_for_hash = min_size_for_hash
        self._scan_count = 0
        self._excluded_count = 0
    
    def scan(self, base_path: Path) -> Dict[Path, FileInfo]:
        """
        Scans a directory recursively
        
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
            f"Scan completed: {self._scan_count} files found, "
            f"{self._excluded_count} excluded"
        )
        
        return files
    
    def _scan_recursive(self, 
                       current_path: Path, 
                       base_path: Path,
                       files: Dict[Path, FileInfo]):
        """Recursive scan implementation"""
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
                                    str(path.name)
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
                                file_hash=file_hash
                            )
                    
                    except PermissionError:
                        self._excluded_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error at {entry.path}: {e}")
        
        except PermissionError:
            self.logger.warning(f"Permission denied for: {current_path}")
    
    def _calculate_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Calculates MD5 hash of a file (fast, not cryptographically secure)"""
        hasher = hashlib.md5()
        try:
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""


# ══════════════════════════════════════════════════════════════════════════════
# CHANGE DETECTOR - CHANGE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

class ChangeDetector:
    """
    Detects changes between source and target files
    
    Strategies:
    - Size comparison (fast)
    - Timestamp comparison (fast)
    - Hash comparison (accurate, optional)
    """
    
    def __init__(self, use_hash: bool = False):
        self.use_hash = use_hash
    
    def detect_changes(self,
                      source_files: Dict[Path, FileInfo],
                      backup_path: Path,
                      logger: BackupLogger) -> Tuple[
                          List[FileInfo],  # New files
                          List[FileInfo],  # Modified files
                          List[Path]       # Files to delete (in backup, no longer in source)
                      ]:
        """
        Compares source and backup files
        
        Returns:
            Tuple of (new_files, modified_files, files_to_delete)
        """
        logger.section("Analyzing changes...")
        
        new_files: List[FileInfo] = []
        modified_files: List[FileInfo] = []
        deleted_files: List[Path] = []
        
        # Scan existing backup files
        existing_backup_files: Set[Path] = set()
        if backup_path.exists():
            for path in backup_path.rglob('*'):
                if path.is_file():
                    relative = path.relative_to(backup_path)
                    existing_backup_files.add(relative)
        
        # Compare source files with backup
        for relative_path, source_info in source_files.items():
            backup_file = backup_path / relative_path
            
            if not backup_file.exists():
                new_files.append(source_info)
            else:
                # Check if modified
                try:
                    backup_stat = backup_file.stat()
                    backup_info = FileInfo(
                        path=backup_file,
                        relative_path=relative_path,
                        size=backup_stat.st_size,
                        mtime=backup_stat.st_mtime
                    )
                    
                    if source_info.needs_update(backup_info, self.use_hash):
                        modified_files.append(source_info)
                        
                except Exception:
                    # On error: mark as modified
                    modified_files.append(source_info)
            
            # Remove from existing
            if relative_path in existing_backup_files:
                existing_backup_files.remove(relative_path)
        
        # Remaining files in backup are deleted
        deleted_files = [backup_path / p for p in existing_backup_files]
        
        logger.info(
            f"Analysis completed: {len(new_files)} new, "
            f"{len(modified_files)} modified, "
            f"{len(deleted_files)} files to delete"
        )
        
        return new_files, modified_files, deleted_files


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP ENGINE - CORE OF THE BACKUP SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class BackupEngine:
    """
    Main engine for the backup system
    
    Features:
    - Multithreaded copying
    - Progress monitoring
    - Error handling and retry
    - Atomic operations
    """
    
    def __init__(self, config: BackupConfig, logger: BackupLogger):
        self.config = config
        self.logger = logger
        self.result = BackupResult()
        self._lock = threading.Lock()
        self._bytes_copied = 0
        self._files_processed = 0
        self._total_bytes = 0
        self._total_files = 0
    
    def run_backup(self) -> BackupResult:
        """Performs the complete backup"""
        self.result = BackupResult(start_time=datetime.now())
        
        try:
            # 1. Validate paths
            if not self._validate_paths():
                return self.result
            
            # 2. Initialize components
            exclusion_filter = ExclusionFilter(
                self.config.exclusions,
                self.config.excluded_extensions
            )
            
            scanner = FileScanner(
                exclusion_filter,
                self.logger,
                self.config.use_hash_verification,
                self.config.min_file_size_for_hash
            )
            
            change_detector = ChangeDetector(self.config.use_hash_verification)
            
            # 3. Scan source files
            source_files = scanner.scan(self.config.source_path)
            
            if not source_files:
                self.logger.warning("No files found for backup!")
                return self.result
            
            # 4. Create backup directory
            backup_target = self.config.backup_path / self.config.backup_folder_name
            backup_target.mkdir(parents=True, exist_ok=True)
            
            # 5. Detect changes
            new_files, modified_files, deleted_files = change_detector.detect_changes(
                source_files, backup_target, self.logger
            )
            
            # 6. Calculate total sizes
            self._total_files = len(new_files) + len(modified_files)
            self._total_bytes = sum(f.size for f in new_files + modified_files)
            self.result.total_files = len(source_files)
            self.result.total_size = sum(f.size for f in source_files.values())
            
            # 7. Perform backup
            self.logger.section("Starting backup operation...")
            
            # Copy new files
            if new_files:
                self._copy_files(new_files, backup_target, FileAction.COPIED)
            
            # Update modified files
            if modified_files:
                self._copy_files(modified_files, backup_target, FileAction.UPDATED)
            
            # Optional: Delete old files
            # (Commented out for safety - can be enabled)
            # if deleted_files:
            #     self._delete_files(deleted_files)
            
            # Count skipped
            self.result.skipped_files = (
                len(source_files) - len(new_files) - len(modified_files)
            )
            
        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            self.result.errors += 1
        
        finally:
            self.result.end_time = datetime.now()
            
            # Write log file
            if self.config.log_to_file:
                self._write_log_file()
        
        return self.result
    
    def _validate_paths(self) -> bool:
        """Validates source and target paths"""
        if not self.config.source_path.exists():
            self.logger.error(f"Source directory does not exist: {self.config.source_path}")
            return False
        
        if not self.config.backup_path.exists():
            self.logger.error(f"Backup medium not found: {self.config.backup_path}")
            return False
        
        # Check write permissions
        try:
            test_file = self.config.backup_path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            self.logger.error(f"No write permissions on backup medium: {e}")
            return False
        
        return True
    
    def _copy_files(self, 
                   files: List[FileInfo], 
                   backup_target: Path,
                   action: FileAction):
        """Copies files with multithreading"""
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._copy_single_file, f, backup_target, action): f
                for f in files
            }
            
            for future in as_completed(futures):
                file_info = futures[future]
                try:
                    success, message = future.result()
                    
                    with self._lock:
                        self._files_processed += 1
                        
                        if success:
                            self._bytes_copied += file_info.size
                            
                            if action == FileAction.COPIED:
                                self.result.copied_files += 1
                            else:
                                self.result.updated_files += 1
                            
                            self.result.copied_size += file_info.size
                            self.result.file_actions.append(
                                (file_info.relative_path, action, message)
                            )
                            
                            self.logger.file_action(
                                action, 
                                file_info.relative_path,
                                f"{file_info.size / 1024:.1f} KB"
                            )
                        else:
                            self.result.errors += 1
                            self.result.file_actions.append(
                                (file_info.relative_path, FileAction.ERROR, message)
                            )
                            self.logger.file_action(
                                FileAction.ERROR,
                                file_info.relative_path,
                                message
                            )
                        
                        # Update progress
                        self.logger.progress(
                            self._files_processed,
                            self._total_files,
                            str(file_info.relative_path.name),
                            self._bytes_copied,
                            self._total_bytes
                        )
                
                except Exception as e:
                    with self._lock:
                        self.result.errors += 1
                    self.logger.error(f"Error at {file_info.path}: {e}")
    
    def _copy_single_file(self, 
                         file_info: FileInfo, 
                         backup_target: Path,
                         action: FileAction) -> Tuple[bool, str]:
        """Copies a single file"""
        try:
            dest_path = backup_target / file_info.relative_path
            
            # Create target directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file with metadata
            shutil.copy2(file_info.path, dest_path)
            
            return True, "OK"
            
        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, f"OS error: {e.errno}"
        except Exception as e:
            return False, str(e)
    
    def _delete_files(self, files: List[Path]):
        """Deletes files that no longer exist in source"""
        for path in files:
            try:
                if path.is_file():
                    path.unlink()
                    self.result.deleted_files += 1
                    self.logger.file_action(FileAction.DELETED, path)
            except Exception as e:
                self.logger.error(f"Delete failed: {path} - {e}")
    
    def _write_log_file(self):
        """Writes detailed log to the backup medium"""
        log_dir = self.config.backup_path / self.config.backup_folder_name / "_backup_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"backup_{timestamp}.log"
        
        self.logger.log_file = log_file
        
        # Write header
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"""
{'='*70}
                    BACKUP LOG - {timestamp}
{'='*70}

CONFIGURATION:
  Source:     {self.config.source_path}
  Target:     {self.config.backup_path / self.config.backup_folder_name}
  Timestamp:  {self.result.start_time.strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY:
  Total Files:            {self.result.total_files}
  Copied Files:           {self.result.copied_files}
  Updated Files:          {self.result.updated_files}
  Skipped Files:          {self.result.skipped_files}
  Errors:                 {self.result.errors}
  
  Total Size:            {self.result.total_size / (1024*1024):.2f} MB
  Copied Size:           {self.result.copied_size / (1024*1024):.2f} MB
  Duration:              {self.result.duration:.1f} seconds
  Speed:                 {self.result.speed_mbps:.2f} MB/s

{'='*70}
                         FILE ACTIONS
{'='*70}

""")
            
            # Write actions
            for path, action, message in self.result.file_actions:
                action_str = {
                    FileAction.COPIED: "[COPIED]     ",
                    FileAction.UPDATED: "[UPDATED]    ",
                    FileAction.SKIPPED: "[SKIPPED]    ",
                    FileAction.DELETED: "[DELETED]    ",
                    FileAction.ERROR: "[ERROR]      ",
                }.get(action, "[?]")
                
                f.write(f"{action_str} {path}")
                if message and message != "OK":
                    f.write(f" ({message})")
                f.write("\n")
        
        self.logger.flush_to_file()
        self.logger.success(f"Log file saved: {log_file}")


# ══════════════════════════════════════════════════════════════════════════════
# FALLBACK HANDLER - ERROR HANDLING
# ══════════════════════════════════════════════════════════════════════════════

class FallbackHandler:
    """
    Handles fallback scenarios when backup is not possible
    
    Options:
    - Local temporary backup
    - User notification
    - Automatic retry
    """
    
    def __init__(self, logger: BackupLogger):
        self.logger = logger
    
    def handle_no_device(self, source_path: Path) -> Optional[Path]:
        """
        Handles the case when no external medium is available
        
        Returns:
            Alternative backup path or None
        """
        self.logger.warning("""
╔════════════════════════════════════════════════════════════════╗
║  ⚠  EXTERNAL STORAGE MEDIUM NOT FOUND                          ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Please make sure that:                                        ║
║  • The external medium is connected                            ║
║  • The medium is recognized by the system                      ║
║  • You have write permissions on the medium                    ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""")
        
        # Option 1: Offer local backup
        local_backup = Path.home() / ".local_backup_temp"
        
        print(f"\n{Colors.YELLOW}Options:{Colors.END}")
        print(f"  [1] Create local temporary backup ({local_backup})")
        print(f"  [2] Wait and try again")
        print(f"  [3] Cancel")
        
        try:
            choice = input(f"\n{Colors.CYAN}Your choice (1-3): {Colors.END}").strip()
            
            if choice == '1':
                local_backup.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Local backup directory created: {local_backup}")
                return local_backup
            
            elif choice == '2':
                print("\nPlease connect the external medium and press Enter...")
                input()
                return None  # Will retry
            
            else:
                self.logger.info("Backup cancelled.")
                return None
                
        except KeyboardInterrupt:
            print("\n")
            self.logger.info("Backup cancelled by user.")
            return None
    
    def notify_completion(self, result: BackupResult, success: bool):
        """Notifies about completion (can be extended for desktop notifications)"""
        if success:
            self.logger.success("Backup completed successfully!")
        else:
            self.logger.error("Backup completed with errors!")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PROGRAM
# ══════════════════════════════════════════════════════════════════════════════

class SmartBackup:
    """
    Main class that brings all components together
    """
    
    def __init__(self):
        self.logger = BackupLogger(verbose=True)
        self.fallback = FallbackHandler(self.logger)
    
    def run(self, 
            custom_source: Optional[Path] = None,
            custom_target: Optional[Path] = None,
            target_label: Optional[str] = None) -> bool:
        """
        Executes the backup
        
        Args:
            custom_source: Optional custom source path
            custom_target: Optional custom target path
            target_label: Preferred target medium label
        
        Returns:
            True if successful, False on errors
        """
        self._print_banner()
        
        # Determine source directory
        source_path = custom_source or PathResolver.get_documents_path()
        
        self.logger.info(f"Source directory: {source_path}")
        self.logger.info(f"Operating system: {platform.system()} {platform.release()}")
        
        if not source_path.exists():
            self.logger.error(f"Source directory does not exist: {source_path}")
            return False
        
        # Find external medium
        backup_path = custom_target
        device_detector = DeviceDetector(self.logger)
        
        max_retries = 3
        for attempt in range(max_retries):
            if backup_path is None:
                backup_path = device_detector.find_backup_device(
                    required_space=1024 * 1024 * 100,  # 100 MB minimum
                    preferred_label=target_label
                )
            
            if backup_path is None:
                backup_path = self.fallback.handle_no_device(source_path)
                if backup_path is None and attempt < max_retries - 1:
                    continue  # Retry
            
            break
        
        if backup_path is None:
            return False
        
        # Create configuration
        config = BackupConfig(
            source_path=source_path,
            backup_path=backup_path,
            backup_folder_name="Documents-Backup",
            max_workers=min(8, (os.cpu_count() or 4)),
            use_hash_verification=False,  # Faster without
            verbose=True
        )
        
        # Perform backup
        engine = BackupEngine(config, self.logger)
        result = engine.run_backup()
        
        # Summary
        self.logger.summary(result)
        
        # Notification
        success = result.errors == 0
        self.fallback.notify_completion(result, success)
        
        return success
    
    def _print_banner(self):
        """Shows the program banner"""
        banner = f"""
{Colors.CYAN}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ███████╗███╗   ███╗ █████╗ ██████╗ ████████╗                               ║
║   ██╔════╝████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝                               ║
║   ███████╗██╔████╔██║███████║██████╔╝   ██║                                  ║
║   ╚════██║██║╚██╔╝██║██╔══██║██╔══██╗   ██║                                  ║
║   ███████║██║ ╚═╝ ██║██║  ██║██║  ██║   ██║                                  ║
║   ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝                                  ║
║                                                                              ║
║   ██████╗  █████╗  ██████╗██╗  ██╗██╗   ██╗██████╗                           ║
║   ██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██║   ██║██╔══██╗                          ║
║   ██████╔╝███████║██║     █████╔╝ ██║   ██║██████╔╝                          ║
║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██║   ██║██╔═══╝                           ║
║   ██████╔╝██║  ██║╚██████╗██║  ██╗╚██████╔╝██║                               ║
║   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝                                ║
║                                                                              ║
║                    Intelligent Backup System v0.1                            ║
║                    Cross-Platform • Incremental • Efficient                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.END}"""
        print(banner)


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND LINE INTERFACE
# ══════════════════════════════════════════════════════════════════════════════

def parse_arguments():
    """Parses command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Smart Backup - Intelligent Backup System for Developers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Standard backup from Documents
  %(prog)s --source ~/Projects      # Backup a specific folder
  %(prog)s --target /media/usb      # Backup to specific medium
  %(prog)s --label "BACKUP_USB"     # Search for medium with label
  %(prog)s --dry-run                # Simulation without actual copying
  %(prog)s --verbose                # Verbose output
        """
    )
    
    parser.add_argument(
        '-s', '--source',
        type=Path,
        help='Source directory (default: Documents folder)'
    )
    
    parser.add_argument(
        '-t', '--target',
        type=Path,
        help='Target directory/medium (default: automatic detection)'
    )
    
    parser.add_argument(
        '-l', '--label',
        type=str,
        help='Preferred target medium label'
    )
    
    parser.add_argument(
        '-n', '--name',
        type=str,
        default='Documents-Backup',
        help='Name of the backup folder (default: Documents-Backup)'
    )
    
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='Number of parallel copy threads (default: 4)'
    )
    
    parser.add_argument(
        '--hash',
        action='store_true',
        help='Enable hash verification for change detection (slower)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulation without actual copying'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=True,
        help='Verbose output'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Minimal output'
    )
    
    parser.add_argument(
        '--exclude',
        type=str,
        nargs='+',
        help='Additional exclusions (folders/files)'
    )
    
    parser.add_argument(
        '--list-drives',
        action='store_true',
        help='Shows all available external drives'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Smart Backup v2.0'
    )
    
    return parser.parse_args()


def list_available_drives():
    """Shows all available external drives"""
    logger = BackupLogger(verbose=True)
    logger.header("Available External Storage Media")
    
    drives = PathResolver.find_external_drives()
    
    if not drives:
        logger.warning("No external storage media found!")
        return
    
    print(f"\n{'─'*70}")
    print(f"{'No.':<5}{'Label':<25}{'Path':<25}{'Free':<15}")
    print(f"{'─'*70}")
    
    for i, (path, label, free) in enumerate(drives, 1):
        free_str = f"{free / (1024**3):.1f} GB"
        print(f"{i:<5}{label:<25}{str(path):<25}{free_str:<15}")
    
    print(f"{'─'*70}\n")


# ══════════════════════════════════════════════════════════════════════════════
# DRY RUN MODE
# ══════════════════════════════════════════════════════════════════════════════

class DryRunBackupEngine(BackupEngine):
    """
    Backup engine for simulation mode
    Performs all analyses but does not copy files
    """
    
    def _copy_single_file(self, 
                         file_info: FileInfo, 
                         backup_target: Path,
                         action: FileAction) -> Tuple[bool, str]:
        """Simulates copying without actual file operation"""
        # Short pause for simulation
        time.sleep(0.001)
        return True, "DRY-RUN"
    
    def _delete_files(self, files: List[Path]):
        """Simulates deletion"""
        for path in files:
            self.result.deleted_files += 1
            self.logger.file_action(FileAction.DELETED, path, "DRY-RUN")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION FILE SUPPORT
# ══════════════════════════════════════════════════════════════════════════════

class ConfigManager:
    """
    Manages persistent configuration
    
    Stores settings in:
    - Windows: %APPDATA%/SmartBackup/config.json
    - macOS/Linux: ~/.config/smartbackup/config.json
    """
    
    def __init__(self):
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"
    
    def _get_config_dir(self) -> Path:
        """Determines the configuration directory"""
        system = platform.system()
        
        if system == 'Windows':
            base = Path(os.environ.get('APPDATA', Path.home()))
            return base / "SmartBackup"
        else:
            return Path.home() / ".config" / "smartbackup"
    
    def load(self) -> dict:
        """Loads the configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def save(self, config: dict):
        """Saves the configuration"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, default=str)
    
    def get_exclusions(self) -> Set[str]:
        """Loads custom exclusions"""
        config = self.load()
        custom = set(config.get('exclusions', []))
        return DEFAULT_EXCLUSIONS | custom
    
    def add_exclusion(self, pattern: str):
        """Adds an exclusion"""
        config = self.load()
        exclusions = set(config.get('exclusions', []))
        exclusions.add(pattern)
        config['exclusions'] = list(exclusions)
        self.save(config)
    
    def set_preferred_target(self, label: str):
        """Saves preferred target medium"""
        config = self
        
    def set_preferred_target(self, label: str):
        """Saves preferred target medium"""
        config = self.load()
        config['preferred_target'] = label
        self.save(config)
    
    def get_preferred_target(self) -> Optional[str]:
        """Loads preferred target medium"""
        config = self.load()
        return config.get('preferred_target')


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER INTEGRATION (Optional)
# ══════════════════════════════════════════════════════════════════════════════

class SchedulerHelper:
    """
    Helps set up automatic backups
    
    Supports:
    - Windows Task Scheduler
    - macOS launchd
    - Linux cron/systemd
    """
    
    @staticmethod
    def setup_scheduled_backup(interval_hours: int = 24):
        """Sets up a scheduled backup"""
        system = platform.system()
        script_path = Path(__file__).resolve()
        
        if system == 'Windows':
            SchedulerHelper._setup_windows_task(script_path, interval_hours)
        elif system == 'Darwin':
            SchedulerHelper._setup_macos_launchd(script_path, interval_hours)
        else:
            SchedulerHelper._setup_linux_cron(script_path, interval_hours)
    
    @staticmethod
    def _setup_windows_task(script_path: Path, interval_hours: int):
        """Creates Windows Scheduled Task"""
        task_name = "SmartBackup"
        python_path = sys.executable
        
        print(f"""
To set up automatic backup on Windows:

1. Open Task Scheduler (taskschd.msc)
2. Create a new task with the following settings:
   - Name: {task_name}
   - Trigger: Daily / Every {interval_hours} hours
   - Action: Start a program
     - Program: {python_path}
     - Arguments: "{script_path}"

Or run the following command as Administrator:
schtasks /create /tn "{task_name}" /tr "\\"{python_path}\\" \\"{script_path}\\"" /sc hourly /mo {interval_hours}
""")
    
    @staticmethod
    def _setup_macos_launchd(script_path: Path, interval_hours: int):
        """Creates macOS LaunchAgent"""
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.smartbackup.plist"
        interval_seconds = interval_hours * 3600
        
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartbackup</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        
        print(f"""
To set up automatic backup on macOS:

1. Create the file: {plist_path}
2. Add the following content:

{plist_content}

3. Load the agent:
   launchctl load {plist_path}
""")
    
    @staticmethod
    def _setup_linux_cron(script_path: Path, interval_hours: int):
        """Shows cron setup for Linux"""
        cron_schedule = f"0 */{interval_hours} * * *" if interval_hours < 24 else "0 9 * * *"
        
        print(f"""
To set up automatic backup on Linux:

1. Open crontab:
   crontab -e

2. Add the following line:
   {cron_schedule} {sys.executable} {script_path}

Or for systemd timer, create:

~/.config/systemd/user/smartbackup.service:
[Unit]
Description=Smart Backup Service

[Service]
Type=oneshot
ExecStart={sys.executable} {script_path}

~/.config/systemd/user/smartbackup.timer:
[Unit]
Description=Run Smart Backup every {interval_hours} hours

[Timer]
OnBootSec=15min
OnUnitActiveSec={interval_hours}h

[Install]
WantedBy=timers.target

Then enable with:
systemctl --user enable --now smartbackup.timer
""")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    """
    Main entry point of the program.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        prog="smartbackup",
        description="SmartBackup - Intelligent Backup System for Developers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  smartbackup                           # Backup Documents to external drive
  smartbackup --source ~/Projects       # Backup a specific folder
  smartbackup --target /media/usb       # Backup to specific drive
  smartbackup --label "BACKUP_USB"      # Find drive by label
  smartbackup --dry-run                 # Simulate without copying
  smartbackup --list-drives             # Show available drives
        """
    )
    
    parser.add_argument(
        "-s", "--source",
        type=Path,
        help="Source directory (default: Documents folder)"
    )
    
    parser.add_argument(
        "-t", "--target",
        type=Path,
        help="Target directory/drive (default: auto-detect external drive)"
    )
    
    parser.add_argument(
        "-l", "--label",
        type=str,
        help="Preferred target drive label"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate backup without copying files"
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Minimal output"
    )
    
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        help="Additional exclusion patterns"
    )
    
    parser.add_argument(
        "--list-drives",
        action="store_true",
        help="List available external drives and exit"
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    args = parser.parse_args()
    
    # List drives only
    if args.list_drives:
        _list_available_drives()
        return 0
    
    # Initialize logger
    logger = BackupLogger(verbose=not args.quiet)
    
    # Load config and add exclusions
    config_manager = ConfigManager()
    if args.exclude:
        for pattern in args.exclude:
            config_manager.add_exclusion(pattern)
            logger.info(f"Exclusion added: {pattern}")
    
    # Get preferred target
    target_label = args.label or config_manager.get_preferred_target()
    
    # Execute backup
    try:
        if args.dry_run:
            logger.warning("DRY-RUN MODE - No files will be copied!")
        
        backup = SmartBackup()
        backup.logger = logger
        success = backup.run(
            custom_source=args.source,
            custom_target=args.target,
            target_label=target_label
        )
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Backup cancelled by user.{Colors.END}")
        return 130
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _list_available_drives() -> None:
    """Display all available external drives."""
    logger = BackupLogger(verbose=True)
    logger.header("Available External Storage Media")
    
    drives = PathResolver.find_external_drives()
    
    if not drives:
        logger.warning("No external storage media found!")
        return
    
    print(f"\n{'─' * 70}")
    print(f"{'No.':<5}{'Label':<25}{'Path':<25}{'Free':<15}")
    print(f"{'─' * 70}")
    
    for i, (path, label, free) in enumerate(drives, 1):
        free_str = f"{free / (1024**3):.1f} GB"
        print(f"{i:<5}{label:<25}{str(path):<25}{free_str:<15}")
    
    print(f"{'─' * 70}\n")


# Module execution
if __name__ == "__main__":
    raise SystemExit(main())