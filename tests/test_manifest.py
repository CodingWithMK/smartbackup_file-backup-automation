"""Tests for the manifest system."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from smartbackup.manifest.base import (
    Manifest,
    ManifestDiff,
    ManifestEntry,
    ManifestFormat,
)
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.models import FileInfo


class TestManifestEntry:
    """Tests for ManifestEntry class."""

    def test_create_entry(self) -> None:
        """Test creating a manifest entry."""
        entry = ManifestEntry(
            relative_path="test/file.txt",
            file_hash="abc123",
            size=1024,
            mtime=1706691600.0,
            permissions=0o644,
            backed_up_at=1706695200.0,
        )

        assert entry.relative_path == "test/file.txt"
        assert entry.file_hash == "abc123"
        assert entry.size == 1024
        assert entry.mtime == 1706691600.0
        assert entry.permissions == 0o644
        assert entry.backed_up_at == 1706695200.0

    def test_to_dict(self) -> None:
        """Test converting entry to dictionary."""
        entry = ManifestEntry(
            relative_path="test/file.txt",
            file_hash="abc123",
            size=1024,
            mtime=1706691600.0,
            permissions=0o644,
            backed_up_at=1706695200.0,
        )

        data = entry.to_dict()

        assert data["hash"] == "abc123"
        assert data["size"] == 1024
        assert data["mtime"] == 1706691600.0
        assert data["permissions"] == 0o644
        assert data["backed_up_at"] == 1706695200.0

    def test_from_dict(self) -> None:
        """Test creating entry from dictionary."""
        data = {
            "hash": "abc123",
            "size": 1024,
            "mtime": 1706691600.0,
            "permissions": 0o644,
            "backed_up_at": 1706695200.0,
        }

        entry = ManifestEntry.from_dict("test/file.txt", data)

        assert entry.relative_path == "test/file.txt"
        assert entry.file_hash == "abc123"
        assert entry.size == 1024

    def test_from_file_info(self, tmp_path: Path) -> None:
        """Test creating entry from FileInfo."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        file_info = FileInfo(
            path=test_file,
            relative_path=Path("test.txt"),
            size=13,
            mtime=test_file.stat().st_mtime,
            file_hash="somehash",
        )

        entry = ManifestEntry.from_file_info(file_info)

        assert entry.relative_path == "test.txt"
        assert entry.file_hash == "somehash"
        assert entry.size == 13

    def test_has_changed_size_different(self) -> None:
        """Test change detection when size differs."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=2048,  # Different size
            mtime=1000.0,
        )

        assert entry.has_changed(file_info) is True

    def test_has_changed_mtime_newer(self) -> None:
        """Test change detection when mtime is newer."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=1024,
            mtime=2000.0,  # Newer mtime
        )

        assert entry.has_changed(file_info) is True

    def test_has_changed_no_change(self) -> None:
        """Test change detection when nothing changed."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=1024,
            mtime=1000.0,
        )

        assert entry.has_changed(file_info) is False


class TestManifest:
    """Tests for Manifest class."""

    def test_create_manifest(self) -> None:
        """Test creating a manifest."""
        manifest = Manifest(
            source="/home/user/Documents",
        )

        assert manifest.version == 1
        assert manifest.format == ManifestFormat.JSON
        assert manifest.source == "/home/user/Documents"
        assert manifest.total_files == 0
        assert manifest.total_size == 0

    def test_add_entry(self) -> None:
        """Test adding an entry."""
        manifest = Manifest()

        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        manifest.add_entry(entry)

        assert manifest.total_files == 1
        assert manifest.total_size == 1024
        assert manifest.has_entry("test.txt")

    def test_remove_entry(self) -> None:
        """Test removing an entry."""
        manifest = Manifest()

        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        manifest.add_entry(entry)
        removed = manifest.remove_entry("test.txt")

        assert removed == entry
        assert manifest.total_files == 0
        assert not manifest.has_entry("test.txt")

    def test_get_entry(self) -> None:
        """Test getting an entry."""
        manifest = Manifest()

        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        manifest.add_entry(entry)
        retrieved = manifest.get_entry("test.txt")

        assert retrieved == entry
        assert manifest.get_entry("nonexistent.txt") is None

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization roundtrip."""
        manifest = Manifest(source="/test/path", hostname="My-Laptop")

        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )
        manifest.add_entry(entry)
        manifest.backup_count = 5

        # Serialize
        data = manifest.to_dict()

        assert data["hostname"] == "My-Laptop"

        # Deserialize
        restored = Manifest.from_dict(data)

        assert restored.source == "/test/path"
        assert restored.hostname == "My-Laptop"
        assert restored.backup_count == 5
        assert restored.total_files == 1
        assert restored.has_entry("test.txt")

    def test_hostname_default_empty(self) -> None:
        """Test that hostname defaults to empty string."""
        manifest = Manifest()
        assert manifest.hostname == ""

    def test_hostname_from_dict_missing(self) -> None:
        """Test that from_dict handles missing hostname gracefully."""
        data = {
            "version": 1,
            "format": "json",
            "source": "/test",
            "backup_count": 0,
            "files": {},
        }
        manifest = Manifest.from_dict(data)
        assert manifest.hostname == ""


class TestManifestDiff:
    """Tests for ManifestDiff class."""

    def test_empty_diff(self) -> None:
        """Test empty diff."""
        diff = ManifestDiff()

        assert not diff.has_changes
        assert diff.files_to_backup == []
        assert "New: 0" in diff.summary

    def test_diff_with_changes(self) -> None:
        """Test diff with changes."""
        diff = ManifestDiff()

        diff.new_files.append(FileInfo(Path("/new.txt"), Path("new.txt"), 100, 1000.0))
        diff.modified_files.append(FileInfo(Path("/mod.txt"), Path("mod.txt"), 200, 2000.0))
        diff.deleted_paths.append("deleted.txt")

        assert diff.has_changes
        assert len(diff.files_to_backup) == 2
        assert "New: 1" in diff.summary
        assert "Modified: 1" in diff.summary
        assert "Deleted: 1" in diff.summary


class TestJsonManifestManager:
    """Tests for JsonManifestManager class."""

    def test_manifest_path(self, tmp_path: Path) -> None:
        """Test manifest path property."""
        manager = JsonManifestManager(tmp_path)

        assert manager.manifest_path == tmp_path / ".smartbackup_manifest.json"

    def test_exists_false(self, tmp_path: Path) -> None:
        """Test exists returns False when no manifest."""
        manager = JsonManifestManager(tmp_path)

        assert not manager.exists()

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading manifest."""
        manager = JsonManifestManager(tmp_path)

        manifest = Manifest(source="/test/path")
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc123",
            size=1024,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )
        manifest.add_entry(entry)

        # Save
        result = manager.save(manifest)
        assert result is True
        assert manager.exists()

        # Load
        loaded = manager.load()
        assert loaded is not None
        assert loaded.source == "/test/path"
        assert loaded.total_files == 1
        assert loaded.has_entry("test.txt")

    def test_load_or_create_new(self, tmp_path: Path) -> None:
        """Test load_or_create creates new manifest."""
        manager = JsonManifestManager(tmp_path)

        manifest = manager.load_or_create(Path("/source/path"))

        assert manifest is not None
        assert manifest.source == "/source/path"
        assert manifest.total_files == 0

    def test_load_or_create_existing(self, tmp_path: Path) -> None:
        """Test load_or_create loads existing manifest."""
        manager = JsonManifestManager(tmp_path)

        # First, save a manifest
        existing = Manifest(source="/existing/path", backup_count=5)
        manager.save(existing)

        # Load or create
        manifest = manager.load_or_create(Path("/new/path"))

        # Should return existing
        assert manifest.source == "/existing/path"
        assert manifest.backup_count == 5

    def test_diff_no_manifest(self, tmp_path: Path) -> None:
        """Test diff when no manifest exists."""
        manager = JsonManifestManager(tmp_path)

        source_files = {
            Path("file1.txt"): FileInfo(Path("/src/file1.txt"), Path("file1.txt"), 100, 1000.0),
            Path("file2.txt"): FileInfo(Path("/src/file2.txt"), Path("file2.txt"), 200, 2000.0),
        }

        diff = manager.diff(source_files)

        # All files should be new
        assert len(diff.new_files) == 2
        assert len(diff.modified_files) == 0
        assert len(diff.deleted_paths) == 0

    def test_diff_with_manifest(self, tmp_path: Path) -> None:
        """Test diff with existing manifest."""
        manager = JsonManifestManager(tmp_path)

        # Create manifest with one file
        manifest = Manifest(source="/test")
        manifest.add_entry(
            ManifestEntry(
                relative_path="existing.txt",
                file_hash="abc",
                size=100,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )
        manifest.add_entry(
            ManifestEntry(
                relative_path="to_delete.txt",
                file_hash="def",
                size=50,
                mtime=500.0,
                permissions=0o644,
                backed_up_at=500.0,
            )
        )
        manager.save(manifest)

        # Source files
        source_files = {
            Path("existing.txt"): FileInfo(
                Path("/src/existing.txt"), Path("existing.txt"), 100, 1000.0
            ),  # Unchanged
            Path("new.txt"): FileInfo(Path("/src/new.txt"), Path("new.txt"), 200, 2000.0),  # New
        }

        diff = manager.diff(source_files)

        # Check diff results
        assert len(diff.new_files) == 1
        assert diff.new_files[0].relative_path == Path("new.txt")

        assert len(diff.unchanged_files) == 1

        assert len(diff.deleted_paths) == 1
        assert diff.deleted_paths[0] == "to_delete.txt"

    def test_update_from_backup(self, tmp_path: Path) -> None:
        """Test updating manifest after backup."""
        manager = JsonManifestManager(tmp_path)

        manifest = Manifest(source="/test")
        backed_up_files = [
            FileInfo(Path("/src/file1.txt"), Path("file1.txt"), 100, 1000.0, "hash1"),
            FileInfo(Path("/src/file2.txt"), Path("file2.txt"), 200, 2000.0, "hash2"),
        ]

        updated = manager.update_from_backup(manifest, backed_up_files)

        assert updated.total_files == 2
        assert updated.backup_count == 1
        assert updated.has_entry("file1.txt")
        assert updated.has_entry("file2.txt")

    def test_verify_success(self, tmp_path: Path) -> None:
        """Test successful verification."""
        manager = JsonManifestManager(tmp_path)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # Create manifest matching the file
        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="test.txt",
                file_hash="abc",
                size=13,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path)

        assert len(errors) == 0

    def test_verify_missing_file(self, tmp_path: Path) -> None:
        """Test verification with missing file."""
        manager = JsonManifestManager(tmp_path)

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="missing.txt",
                file_hash="abc",
                size=100,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path)

        assert len(errors) == 1
        assert "Missing" in errors[0]

    def test_verify_size_mismatch(self, tmp_path: Path) -> None:
        """Test verification with size mismatch."""
        manager = JsonManifestManager(tmp_path)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello")

        # Create manifest with wrong size
        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="test.txt",
                file_hash="abc",
                size=1000,  # Wrong size
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path)

        assert len(errors) == 1
        assert "Size mismatch" in errors[0]

    def test_atomic_save(self, tmp_path: Path) -> None:
        """Test that save is atomic (uses temp file)."""
        manager = JsonManifestManager(tmp_path)

        manifest = Manifest(source="/test")

        # Save
        manager.save(manifest)

        # Check that no temp file remains
        temp_file = manager.manifest_path.with_suffix(".json.tmp")
        assert not temp_file.exists()

        # Check that manifest file exists
        assert manager.manifest_path.exists()

    def test_load_corrupted_manifest(self, tmp_path: Path) -> None:
        """Test loading a corrupted manifest returns None."""
        manager = JsonManifestManager(tmp_path)

        # Write corrupted JSON
        manager.manifest_path.write_text("{ invalid json }")

        manifest = manager.load()

        assert manifest is None
