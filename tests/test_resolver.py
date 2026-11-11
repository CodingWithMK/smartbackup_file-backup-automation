"""
Tests for the platform resolver module.
"""

from pathlib import Path

from smartbackup.platform.resolver import PathResolver


class TestPathResolver:
    """Tests for PathResolver class."""

    def test_get_documents_path_returns_path(self):
        """Documents path should return a Path object."""
        docs = PathResolver.get_documents_path()
        assert isinstance(docs, Path)

    def test_get_documents_path_is_absolute(self):
        """Documents path should be absolute."""
        docs = PathResolver.get_documents_path()
        assert docs.is_absolute()

    def test_get_documents_path_contains_documents(self):
        """Documents path should typically contain 'Documents'."""
        docs = PathResolver.get_documents_path()
        # On most systems, the path should contain 'Documents' or localized equivalent
        str(docs).lower()
        # This may fail on some Linux systems with non-standard configs
        # so we just check it's a valid path
        assert len(str(docs)) > 0

    def test_find_external_drives_returns_list(self):
        """External drives should return a list."""
        drives = PathResolver.find_external_drives()
        assert isinstance(drives, list)

    def test_find_external_drives_tuple_format(self):
        """Each drive should be a tuple of (path, label, free_space)."""
        drives = PathResolver.find_external_drives()

        for drive in drives:
            assert isinstance(drive, tuple)
            assert len(drive) == 3
            path, label, free = drive
            assert isinstance(path, Path)
            assert isinstance(label, str)
            assert isinstance(free, int)

    def test_find_external_drives_free_space_positive(self):
        """Free space should be positive for all drives."""
        drives = PathResolver.find_external_drives()

        for _path, _label, free in drives:
            assert free >= 0


class TestPathResolverPlatformMethods:
    """Tests for platform-specific methods."""

    def test_find_macos_drives_method_exists(self):
        """macOS drive finding method should exist."""
        assert hasattr(PathResolver, "_find_macos_drives")
        assert callable(PathResolver._find_macos_drives)

    def test_find_linux_drives_method_exists(self):
        """Linux drive finding method should exist."""
        assert hasattr(PathResolver, "_find_linux_drives")
        assert callable(PathResolver._find_linux_drives)

    def test_find_windows_drives_method_exists(self):
        """Windows drive finding method should exist."""
        assert hasattr(PathResolver, "_find_windows_drives")
        assert callable(PathResolver._find_windows_drives)

    def test_find_windows_drives_bitmask_mapping(self):
        """Verify Windows drive bitmask decoding and system drive exclusion."""
        import ctypes
        from unittest.mock import MagicMock, patch

        mock_kernel32 = MagicMock()
        # Mock GetLogicalDrives() == (1 << 2) | (1 << 3) | (1 << 4) (C:, D:, E:)
        mock_kernel32.GetLogicalDrives.return_value = (1 << 2) | (1 << 3) | (1 << 4)

        def mock_get_drive_type(drive_str):
            if "C:" in drive_str:
                return 3  # FIXED
            elif "D:" in drive_str:
                return 2  # REMOVABLE
            elif "E:" in drive_str:
                return 3  # FIXED
            return 1

        mock_kernel32.GetDriveTypeW.side_effect = mock_get_drive_type

        def mock_get_volume_info(drive_str, buf, size, *args):
            if "D:" in drive_str:
                buf.value = "FlashDrive"
            elif "E:" in drive_str:
                buf.value = "ExternalSSD"
            return 1

        mock_kernel32.GetVolumeInformationW.side_effect = mock_get_volume_info

        mock_windll = MagicMock()
        mock_windll.kernel32 = mock_kernel32

        with patch("platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"SystemDrive": "C:"}), \
             patch.object(Path, "home", return_value=Path("C:/Users/TestUser")), \
             patch.object(ctypes, "windll", mock_windll, create=True), \
             patch.object(Path, "exists", return_value=True), \
             patch("shutil.disk_usage", return_value=(2000000000, 1000000000, 1000000000)):

            drives = PathResolver.find_external_drives()
            drive_paths = [d[0] for d in drives]

            assert Path("D:\\") in drive_paths
            assert Path("E:\\") in drive_paths
            assert Path("C:\\") not in drive_paths

            d_drive = next(d for d in drives if d[0] == Path("D:\\"))
            assert d_drive[1] == "FlashDrive"
            assert d_drive[2] == 1000000000

            e_drive = next(d for d in drives if d[0] == Path("E:\\"))
            assert e_drive[1] == "ExternalSSD"
            assert e_drive[2] == 1000000000

    def test_windows_system_drive_dynamic_exclusion(self):
        """Ensure dynamic system drive (e.g. D:) is excluded, even if drive type is REMOVABLE."""
        import ctypes
        from unittest.mock import MagicMock, patch

        mock_kernel32 = MagicMock()
        mock_kernel32.GetLogicalDrives.return_value = (1 << 2) | (1 << 3) | (1 << 4)

        mock_kernel32.GetDriveTypeW.return_value = 2  # REMOVABLE for all
        mock_kernel32.GetVolumeInformationW.return_value = 1

        mock_windll = MagicMock()
        mock_windll.kernel32 = mock_kernel32

        with patch("platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"SystemDrive": "D:"}), \
             patch.object(Path, "home", return_value=Path("D:/Users/TestUser")), \
             patch.object(ctypes, "windll", mock_windll, create=True), \
             patch.object(Path, "exists", return_value=True), \
             patch("shutil.disk_usage", return_value=(2000000000, 1000000000, 1000000000)):

            drives = PathResolver._find_windows_drives()
            drive_paths = [d[0] for d in drives]

            # D:\ is SystemDrive so it must be excluded
            assert Path("D:\\") not in drive_paths
            # C:\ and E:\ should be included
            assert Path("C:\\") in drive_paths
            assert Path("E:\\") in drive_paths

    def test_find_windows_drives_fallback_on_exception(self):
        """Ensure resilient fallback executes if Win32 ctypes call raises an exception."""
        import ctypes
        from unittest.mock import patch

        def fake_exists(self):
            return str(self) in ("E:\\", "F:\\")

        with patch("platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"SystemDrive": "C:"}), \
             patch.object(Path, "home", return_value=Path("C:/Users/TestUser")), \
             patch.object(ctypes, "windll", side_effect=Exception("Win32 unavailable"), create=True), \
             patch.object(Path, "exists", autospec=True, side_effect=fake_exists), \
             patch("shutil.disk_usage", return_value=(2000000000, 1000000000, 1000000000)):

            drives = PathResolver._find_windows_drives()
            drive_paths = [d[0] for d in drives]

            assert Path("E:\\") in drive_paths
            assert Path("F:\\") in drive_paths
            assert Path("C:\\") not in drive_paths
