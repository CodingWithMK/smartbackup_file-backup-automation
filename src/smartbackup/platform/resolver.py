"""
PathResolver - Cross-platform path resolution.
"""

import os
import platform
import shutil
from pathlib import Path
from typing import List, Tuple


class PathResolver:
    """
    Cross-Platform Path Resolution.

    Automatically detects:
    - Documents folder on all operating systems
    - External storage media
    - Different drives (Windows) / mount points (Unix)
    """

    @staticmethod
    def get_documents_path() -> Path:
        """Determines the Documents folder in a platform-independent way."""
        system = platform.system()

        if system == "Windows":
            # Try to use Shell Folders
            try:
                import winreg

                key = winreg.OpenKey(  # type: ignore[attr-defined]
                    winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
                )
                documents, _ = winreg.QueryValueEx(key, "Personal")  # type: ignore[attr-defined]
                winreg.CloseKey(key)  # type: ignore[attr-defined]
                return Path(documents)
            except Exception:
                pass

            # Fallback
            return Path.home() / "Documents"

        elif system == "Darwin":  # macOS
            return Path.home() / "Documents"

        else:  # Linux and others
            # Check XDG configuration
            xdg_docs = os.environ.get("XDG_DOCUMENTS_DIR")
            if xdg_docs:
                return Path(xdg_docs)

            # Try to read user-dirs.dirs
            user_dirs = Path.home() / ".config" / "user-dirs.dirs"
            if user_dirs.exists():
                try:
                    with open(user_dirs, "r") as f:
                        for line in f:
                            if line.startswith("XDG_DOCUMENTS_DIR"):
                                path = line.split("=")[1].strip().strip('"')
                                path = path.replace("$HOME", str(Path.home()))
                                return Path(path)
                except Exception:
                    pass

            # Fallbacks for different languages
            for name in ["Documents", "Dokumente", "documents"]:
                path = Path.home() / name
                if path.exists():
                    return path

            return Path.home() / "Documents"

    @staticmethod
    def find_external_drives() -> List[Tuple[Path, str, int]]:
        """
        Finds all external storage media.

        Returns:
            List of tuples (path, label, free space in bytes)
        """
        drives: List[Tuple[Path, str, int]] = []
        system = platform.system()

        if system == "Windows":
            drives = PathResolver._find_windows_drives()
        elif system == "Darwin":
            drives = PathResolver._find_macos_drives()
        else:
            drives = PathResolver._find_linux_drives()

        return drives

    @staticmethod
    def _find_windows_drives() -> List[Tuple[Path, str, int]]:
        """Finds external drives on Windows."""
        drives: List[Tuple[Path, str, int]] = []
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            # Iterate through all drive letters
            bitmask = kernel32.GetLogicalDrives()
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
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
                                str(drive_path),
                                volume_name_buffer,
                                261,
                                None,
                                None,
                                None,
                                None,
                                0,
                            )
                            label = volume_name_buffer.value or f"Drive {letter}"

                            drives.append((drive_path, label, free))
                        except Exception:
                            pass

                bitmask >>= 1

        except Exception:
            # Fallback: Simple method
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
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
        """Finds external drives on macOS."""
        drives: List[Tuple[Path, str, int]] = []
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
        """Finds external drives on Linux."""
        drives: List[Tuple[Path, str, int]] = []

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
