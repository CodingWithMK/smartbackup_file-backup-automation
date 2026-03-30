"""Tests for the manifest system."""

import hashlib
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
        assert manifest.source == str(Path("/source/path"))
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


# ---------------------------------------------------------------------------
# SHA-256 Hashing Tests
# ---------------------------------------------------------------------------


class TestSHA256Hashing:
    """Tests for SHA-256 hashing in the scanner and manifest manager."""

    def test_calculate_hash_returns_sha256(self, tmp_path: Path) -> None:
        """Hash output should be a valid SHA-256 hex digest (64 chars)."""
        test_file = tmp_path / "known.txt"
        test_file.write_bytes(b"smartbackup test content")

        expected = hashlib.sha256(b"smartbackup test content").hexdigest()

        manager = JsonManifestManager(tmp_path)
        actual = manager._hash_file(test_file)

        assert actual == expected
        assert len(actual) == 64  # SHA-256 hex length

    def test_calculate_hash_empty_file(self, tmp_path: Path) -> None:
        """Empty file should return the well-known SHA-256 of empty bytes."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        manager = JsonManifestManager(tmp_path)
        actual = manager._hash_file(test_file)

        assert actual == expected

    def test_calculate_hash_returns_empty_on_error(self, tmp_path: Path) -> None:
        """Non-existent file should return empty string, not raise."""
        manager = JsonManifestManager(tmp_path)
        result = manager._hash_file(tmp_path / "nonexistent.txt")

        assert result == ""

    def test_scanner_hashes_when_enabled(self, tmp_path: Path) -> None:
        """FileScanner with use_hash=True should compute hashes for small files."""
        from smartbackup.core.scanner import ExclusionFilter, FileScanner
        from smartbackup.ui.logger import BackupLogger

        source = tmp_path / "src"
        source.mkdir()
        (source / "small.txt").write_text("hello world")

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=True, max_size_for_hash=50 * 1024 * 1024)

        files = scanner.scan(source)
        info = files[Path("small.txt")]

        assert info.file_hash is not None
        assert len(info.file_hash) == 64

    def test_scanner_skips_hash_when_disabled(self, tmp_path: Path) -> None:
        """FileScanner with use_hash=False should leave file_hash as None."""
        from smartbackup.core.scanner import ExclusionFilter, FileScanner
        from smartbackup.ui.logger import BackupLogger

        source = tmp_path / "src"
        source.mkdir()
        (source / "small.txt").write_text("hello world")

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=False)

        files = scanner.scan(source)
        info = files[Path("small.txt")]

        assert info.file_hash is None

    def test_scanner_respects_max_size_threshold(self, tmp_path: Path) -> None:
        """Files above max_size_for_hash should not be hashed (unless hash_all)."""
        from smartbackup.core.scanner import ExclusionFilter, FileScanner
        from smartbackup.ui.logger import BackupLogger

        source = tmp_path / "src"
        source.mkdir()
        # Create a file that exceeds the threshold (threshold = 10 bytes)
        (source / "big.txt").write_text("A" * 100)

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(filt, logger, use_hash=True, max_size_for_hash=10)

        files = scanner.scan(source)
        info = files[Path("big.txt")]

        assert info.file_hash is None

    def test_scanner_hash_all_overrides_threshold(self, tmp_path: Path) -> None:
        """With hash_all=True, files above threshold should still be hashed."""
        from smartbackup.core.scanner import ExclusionFilter, FileScanner
        from smartbackup.ui.logger import BackupLogger

        source = tmp_path / "src"
        source.mkdir()
        (source / "big.txt").write_text("A" * 100)

        filt = ExclusionFilter(set(), set())
        logger = BackupLogger(verbose=False)
        scanner = FileScanner(
            filt, logger, use_hash=True, hash_all=True, max_size_for_hash=10
        )

        files = scanner.scan(source)
        info = files[Path("big.txt")]

        assert info.file_hash is not None
        assert len(info.file_hash) == 64


class TestManifestHashAlgorithm:
    """Tests for the hash_algorithm field on Manifest."""

    def test_manifest_default_hash_algorithm(self) -> None:
        """New Manifest should default to sha256."""
        manifest = Manifest()
        assert manifest.hash_algorithm == "sha256"

    def test_manifest_to_dict_includes_hash_algorithm(self) -> None:
        """Serialized dict should contain 'hash_algorithm' key."""
        manifest = Manifest()
        data = manifest.to_dict()

        assert "hash_algorithm" in data
        assert data["hash_algorithm"] == "sha256"

    def test_manifest_from_dict_backward_compat(self) -> None:
        """Loading a dict WITHOUT 'hash_algorithm' should default to 'md5'."""
        data = {
            "version": 1,
            "format": "json",
            "source": "/old/backup",
            "backup_count": 3,
            "files": {},
        }

        manifest = Manifest.from_dict(data)

        assert manifest.hash_algorithm == "md5"

    def test_manifest_from_dict_with_sha256(self) -> None:
        """Loading a dict WITH 'hash_algorithm':'sha256' should preserve it."""
        data = {
            "version": 1,
            "format": "json",
            "source": "/new/backup",
            "hash_algorithm": "sha256",
            "backup_count": 1,
            "files": {},
        }

        manifest = Manifest.from_dict(data)

        assert manifest.hash_algorithm == "sha256"


class TestHashVerification:
    """Tests for the enhanced verify() method with hash checking."""

    def test_verify_catches_hash_mismatch(self, tmp_path: Path) -> None:
        """Modified file content (same size) should be caught by hash verification."""
        manager = JsonManifestManager(tmp_path)

        # Create a file and compute its hash
        test_file = tmp_path / "data.bin"
        original_content = b"AAAA"  # 4 bytes
        test_file.write_bytes(original_content)
        original_hash = hashlib.sha256(original_content).hexdigest()

        # Create manifest with the original hash
        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="data.bin",
                file_hash=original_hash,
                size=4,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        # Modify the file content but keep the same size
        test_file.write_bytes(b"BBBB")

        errors = manager.verify(manifest, tmp_path, verify_hashes=True)

        assert len(errors) == 1
        assert "Hash mismatch" in errors[0]

    def test_verify_passes_matching_hash(self, tmp_path: Path) -> None:
        """File content matching stored hash should produce no errors."""
        manager = JsonManifestManager(tmp_path)

        test_file = tmp_path / "good.txt"
        content = b"correct content"
        test_file.write_bytes(content)
        correct_hash = hashlib.sha256(content).hexdigest()

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="good.txt",
                file_hash=correct_hash,
                size=len(content),
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path, verify_hashes=True)

        assert len(errors) == 0

    def test_verify_skips_hash_check_when_disabled(self, tmp_path: Path) -> None:
        """verify(verify_hashes=False) should NOT report hash mismatches."""
        manager = JsonManifestManager(tmp_path)

        test_file = tmp_path / "data.bin"
        test_file.write_bytes(b"AAAA")

        # Manifest stores a WRONG hash but correct size
        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="data.bin",
                file_hash="0000000000000000000000000000000000000000000000000000000000000000",
                size=4,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path, verify_hashes=False)

        assert len(errors) == 0

    def test_verify_skips_hash_when_entry_has_no_hash(self, tmp_path: Path) -> None:
        """Entry with empty file_hash should be skipped (no error, no crash)."""
        manager = JsonManifestManager(tmp_path)

        test_file = tmp_path / "nohash.txt"
        test_file.write_bytes(b"data")

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="nohash.txt",
                file_hash="",  # No hash stored
                size=4,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path, verify_hashes=True)

        assert len(errors) == 0


class TestMtimeComparison:
    """Tests for the mtime != fix in ManifestEntry.has_changed() and FileInfo.needs_update()."""

    def test_has_changed_detects_backward_mtime(self) -> None:
        """File with OLDER mtime than manifest entry should be detected as changed."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc",
            size=100,
            mtime=2000.0,
            permissions=0o644,
            backed_up_at=2000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=100,
            mtime=1000.0,  # Older than manifest
        )

        assert entry.has_changed(file_info) is True

    def test_has_changed_detects_forward_mtime(self) -> None:
        """File with NEWER mtime than manifest entry should be detected as changed."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="abc",
            size=100,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=100,
            mtime=2000.0,  # Newer than manifest
        )

        assert entry.has_changed(file_info) is True

    def test_has_changed_same_mtime_same_size(self) -> None:
        """Same mtime + same size (no hash) should be reported as unchanged."""
        entry = ManifestEntry(
            relative_path="test.txt",
            file_hash="",
            size=100,
            mtime=1000.0,
            permissions=0o644,
            backed_up_at=1000.0,
        )

        file_info = FileInfo(
            path=Path("/test.txt"),
            relative_path=Path("test.txt"),
            size=100,
            mtime=1000.0,
        )

        assert entry.has_changed(file_info) is False

    def test_needs_update_backward_mtime(self) -> None:
        """FileInfo.needs_update() should detect backward mtime changes."""
        source = FileInfo(
            path=Path("/src.txt"),
            relative_path=Path("test.txt"),
            size=100,
            mtime=1000.0,  # Older
        )
        backup = FileInfo(
            path=Path("/bak.txt"),
            relative_path=Path("test.txt"),
            size=100,
            mtime=2000.0,  # Newer
        )

        # source is OLDER than backup -- with the != fix, this should detect a change
        assert source.needs_update(backup) is True
