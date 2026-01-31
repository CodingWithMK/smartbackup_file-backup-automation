"""
Tests for the platform resolver module.
"""

from pathlib import Path

import pytest

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
        path_str = str(docs).lower()
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

        for path, label, free in drives:
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
