"""
Unit tests for manifest models and JsonManifestManager.
"""

import hashlib
from pathlib import Path

from smartbackup.manifest.base import (
    Manifest,
    ManifestDiff,
    ManifestEntry,
    ManifestFormat,
    SelectiveBackupRecord,
)
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.models import FileInfo


class TestManifestEntry:
    """Tests for ManifestEntry class."""

    def test_create_entry(self) -> None:
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
            size=2048,
            mtime=1000.0,
        )
        assert entry.has_changed(file_info) is True

    def test_has_changed_mtime_newer(self) -> None:
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
            mtime=2000.0,
        )
        assert entry.has_changed(file_info) is True

    def test_has_changed_no_change(self) -> None:
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

    def test_has_changed_detects_backward_mtime(self) -> None:
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
            mtime=1000.0,
        )
        assert entry.has_changed(file_info) is True

    def test_has_changed_detects_forward_mtime(self) -> None:
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
            mtime=2000.0,
        )
        assert entry.has_changed(file_info) is True

    def test_has_changed_same_mtime_same_size(self) -> None:
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


class TestManifest:
    """Tests for Manifest class."""

    def test_create_manifest(self) -> None:
        manifest = Manifest(source="/home/user/Documents")

        assert manifest.version == 1
        assert manifest.format == ManifestFormat.JSON
        assert manifest.source == "/home/user/Documents"
        assert manifest.total_files == 0
        assert manifest.total_size == 0

    def test_add_entry(self) -> None:
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

        assert manifest.get_entry("test.txt") == entry
        assert manifest.get_entry("nonexistent.txt") is None

    def test_to_dict_and_from_dict(self) -> None:
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

        data = manifest.to_dict()
        assert data["hostname"] == "My-Laptop"

        restored = Manifest.from_dict(data)
        assert restored.source == "/test/path"
        assert restored.hostname == "My-Laptop"
        assert restored.backup_count == 5
        assert restored.total_files == 1
        assert restored.has_entry("test.txt")

    def test_hostname_default_empty(self) -> None:
        assert Manifest().hostname == ""

    def test_hostname_from_dict_missing(self) -> None:
        data = {
            "version": 1,
            "format": "json",
            "source": "/test",
            "backup_count": 0,
            "files": {},
        }
        assert Manifest.from_dict(data).hostname == ""

    def test_manifest_default_hash_algorithm(self) -> None:
        assert Manifest().hash_algorithm == "sha256"

    def test_manifest_to_dict_includes_hash_algorithm(self) -> None:
        data = Manifest().to_dict()
        assert data["hash_algorithm"] == "sha256"

    def test_manifest_from_dict_backward_compat(self) -> None:
        data = {
            "version": 1,
            "format": "json",
            "source": "/old/backup",
            "backup_count": 3,
            "files": {},
        }
        assert Manifest.from_dict(data).hash_algorithm == "md5"

    def test_manifest_from_dict_with_sha256(self) -> None:
        data = {
            "version": 1,
            "format": "json",
            "source": "/new/backup",
            "hash_algorithm": "sha256",
            "backup_count": 1,
            "files": {},
        }
        assert Manifest.from_dict(data).hash_algorithm == "sha256"


class TestManifestDiff:
    """Tests for ManifestDiff class."""

    def test_empty_diff(self) -> None:
        diff = ManifestDiff()
        assert not diff.has_changes
        assert diff.files_to_backup == []
        assert "New: 0" in diff.summary

    def test_diff_with_changes(self) -> None:
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
        manager = JsonManifestManager(tmp_path)
        assert manager.manifest_path == tmp_path / ".smartbackup_manifest.json"

    def test_exists_false(self, tmp_path: Path) -> None:
        assert not JsonManifestManager(tmp_path).exists()

    def test_save_and_load(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        manifest = Manifest(source="/test/path")
        manifest.add_entry(
            ManifestEntry(
                relative_path="test.txt",
                file_hash="abc123",
                size=1024,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        assert manager.save(manifest) is True
        assert manager.exists()

        loaded = manager.load()
        assert loaded is not None
        assert loaded.source == "/test/path"
        assert loaded.total_files == 1
        assert loaded.has_entry("test.txt")

    def test_load_or_create_new(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        manifest = manager.load_or_create(Path("/source/path"))

        assert manifest is not None
        assert manifest.source == str(Path("/source/path"))
        assert manifest.total_files == 0

    def test_load_or_create_existing(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        manager.save(Manifest(source="/existing/path", backup_count=5))

        manifest = manager.load_or_create(Path("/new/path"))
        assert manifest.source == "/existing/path"
        assert manifest.backup_count == 5

    def test_diff_no_manifest(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        source_files = {
            Path("file1.txt"): FileInfo(Path("/src/file1.txt"), Path("file1.txt"), 100, 1000.0),
            Path("file2.txt"): FileInfo(Path("/src/file2.txt"), Path("file2.txt"), 200, 2000.0),
        }

        diff = manager.diff(source_files)
        assert len(diff.new_files) == 2
        assert len(diff.modified_files) == 0
        assert len(diff.deleted_paths) == 0

    def test_diff_with_manifest(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
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

        source_files = {
            Path("existing.txt"): FileInfo(
                Path("/src/existing.txt"), Path("existing.txt"), 100, 1000.0
            ),
            Path("new.txt"): FileInfo(Path("/src/new.txt"), Path("new.txt"), 200, 2000.0),
        }

        diff = manager.diff(source_files)
        assert len(diff.new_files) == 1
        assert diff.new_files[0].relative_path == Path("new.txt")
        assert len(diff.unchanged_files) == 1
        assert len(diff.deleted_paths) == 1
        assert diff.deleted_paths[0] == "to_delete.txt"

    def test_update_from_backup(self, tmp_path: Path) -> None:
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

    def test_update_from_backup_sync_deletes_entries(self, tmp_path: Path) -> None:
        """Manifest should remove entries that were deleted during sync."""
        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="keep.txt",
                size=10,
                mtime=100.0,
                file_hash="",
                permissions=0o644,
                backed_up_at=0.0,
            )
        )
        manifest.add_entry(
            ManifestEntry(
                relative_path="delete.txt",
                size=20,
                mtime=200.0,
                file_hash="",
                permissions=0o644,
                backed_up_at=0.0,
            )
        )

        manager = JsonManifestManager(tmp_path)
        updated = manager.update_from_backup(manifest, [], deleted_paths=["delete.txt"])

        assert updated.total_files == 1
        assert "keep.txt" in updated.entries
        assert "delete.txt" not in updated.entries

    def test_verify_success(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        (tmp_path / "test.txt").write_text("Hello, World!")

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

        assert len(manager.verify(manifest, tmp_path)) == 0

    def test_verify_missing_file(self, tmp_path: Path) -> None:
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
        manager = JsonManifestManager(tmp_path)
        (tmp_path / "test.txt").write_text("Hello")

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="test.txt",
                file_hash="abc",
                size=1000,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        errors = manager.verify(manifest, tmp_path)
        assert len(errors) == 1
        assert "Size mismatch" in errors[0]

    def test_atomic_save(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        manager.save(Manifest(source="/test"))

        temp_file = manager.manifest_path.with_suffix(".json.tmp")
        assert not temp_file.exists()
        assert manager.manifest_path.exists()

    def test_load_corrupted_manifest(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        manager.manifest_path.write_text("{ invalid json }")
        assert manager.load() is None


class TestManifestHashingAndVerification:
    """Tests for SHA-256 hashing and verify(verify_hashes=...) checks."""

    def test_calculate_hash_returns_sha256(self, tmp_path: Path) -> None:
        test_file = tmp_path / "known.txt"
        test_file.write_bytes(b"smartbackup test content")
        expected = hashlib.sha256(b"smartbackup test content").hexdigest()

        actual = JsonManifestManager(tmp_path)._hash_file(test_file)
        assert actual == expected
        assert len(actual) == 64

    def test_calculate_hash_empty_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        assert JsonManifestManager(tmp_path)._hash_file(test_file) == expected

    def test_calculate_hash_returns_empty_on_error(self, tmp_path: Path) -> None:
        assert JsonManifestManager(tmp_path)._hash_file(tmp_path / "nonexistent.txt") == ""

    def test_verify_catches_hash_mismatch(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        test_file = tmp_path / "data.bin"
        test_file.write_bytes(b"AAAA")
        original_hash = hashlib.sha256(b"AAAA").hexdigest()

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

        test_file.write_bytes(b"BBBB")
        errors = manager.verify(manifest, tmp_path, verify_hashes=True)
        assert len(errors) == 1
        assert "Hash mismatch" in errors[0]

    def test_verify_passes_matching_hash(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        test_file = tmp_path / "good.txt"
        content = b"correct content"
        test_file.write_bytes(content)

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="good.txt",
                file_hash=hashlib.sha256(content).hexdigest(),
                size=len(content),
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        assert len(manager.verify(manifest, tmp_path, verify_hashes=True)) == 0

    def test_verify_skips_hash_check_when_disabled(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        (tmp_path / "data.bin").write_bytes(b"AAAA")

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="data.bin",
                file_hash="0" * 64,
                size=4,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        assert len(manager.verify(manifest, tmp_path, verify_hashes=False)) == 0

    def test_verify_skips_hash_when_entry_has_no_hash(self, tmp_path: Path) -> None:
        manager = JsonManifestManager(tmp_path)
        (tmp_path / "nohash.txt").write_bytes(b"data")

        manifest = Manifest()
        manifest.add_entry(
            ManifestEntry(
                relative_path="nohash.txt",
                file_hash="",
                size=4,
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )

        assert len(manager.verify(manifest, tmp_path, verify_hashes=True)) == 0


class TestSelectiveManifestJson:
    """Tests for SelectiveBackupRecord, legacy JSON load, and scoped diff() immunity."""

    def test_selective_backup_record_roundtrip(self) -> None:
        rec = SelectiveBackupRecord(
            run_id="20261124_010000_#2",
            source_root="/home/user/Documents",
            selected_folders=["Projects", "Work"],
            available_folders_count=5,
            files_scanned=12,
            files_copied=3,
            files_updated=1,
            files_deleted=2,
            files_skipped=8,
            bytes_copied=4096,
            duration_seconds=1.25,
            workflow_steps=["CLI invoked with --select", "Scoped scan completed"],
        )

        restored = SelectiveBackupRecord.from_dict(rec.to_dict())
        assert restored.run_id == rec.run_id
        assert restored.command_option == "--select"
        assert restored.scope == "folders"
        assert restored.selected_folders == ["Projects", "Work"]
        assert restored.available_folders_count == 5
        assert restored.files_copied == 3
        assert restored.files_deleted == 2
        assert restored.bytes_copied == 4096
        assert restored.workflow_steps == rec.workflow_steps

    def test_legacy_json_manifest_without_selective_fields_loads_cleanly(self) -> None:
        legacy_data = {
            "version": 1,
            "format": "json",
            "source": "/legacy/docs",
            "hostname": "OldPC",
            "hash_algorithm": "sha256",
            "backup_count": 4,
            "files": {},
        }

        manifest = Manifest.from_dict(legacy_data)
        assert manifest.last_backup_mode == "full"
        assert manifest.last_selected_folders == []
        assert manifest.selective_backups == []

    def test_add_selective_backup_and_full_backup_preserves_history(self, tmp_path: Path) -> None:
        mgr = JsonManifestManager(tmp_path)
        manifest = mgr.create(Path("/docs"))
        record = SelectiveBackupRecord(
            run_id="20261124_010000_#1",
            source_root="/docs",
            selected_folders=["Projects"],
            available_folders_count=3,
            files_copied=2,
        )
        manifest.add_selective_backup(record)
        assert manifest.last_backup_mode == "select"
        assert manifest.last_selected_folders == ["Projects"]
        assert len(manifest.selective_backups) == 1

        assert mgr.save(manifest) is True
        loaded = mgr.load()
        assert loaded is not None
        assert loaded.last_backup_mode == "select"
        assert loaded.last_selected_folders == ["Projects"]
        assert len(loaded.selective_backups) == 1
        assert loaded.selective_backups[0].run_id == "20261124_010000_#1"

        # Subsequent full run flips mode back to full while preserving selective history
        loaded.last_backup_mode = "full"
        loaded.last_selected_folders = []
        assert mgr.save(loaded) is True
        reloaded = mgr.load()
        assert reloaded is not None
        assert reloaded.last_backup_mode == "full"
        assert reloaded.last_selected_folders == []
        assert len(reloaded.selective_backups) == 1

    def test_scoped_diff_protects_unselected_folders_and_root_files(self, tmp_path: Path) -> None:
        mgr = JsonManifestManager(tmp_path)
        manifest = Manifest(source="/docs")
        for rel in (
            "Projects/keep.py",
            "Projects/removed.py",
            "Finance/budget.xlsx",
            "Projects",  # loose root file sharing name with selected folder!
            "readme.txt",
        ):
            manifest.add_entry(
                ManifestEntry(
                    relative_path=rel,
                    file_hash="abc",
                    size=10,
                    mtime=100.0,
                    permissions=0o644,
                    backed_up_at=100.0,
                )
            )

        # Source scan only contains Projects/keep.py (Projects/removed.py deleted)
        source_files = {
            Path("Projects/keep.py"): FileInfo(
                path=Path("/docs/Projects/keep.py"),
                relative_path=Path("Projects/keep.py"),
                size=10,
                mtime=100.0,
            )
        }
        # Normalize entry key to match OS path representation used by ManifestManager.diff
        manifest.entries = {
            str(Path(k)): ManifestEntry(
                relative_path=str(Path(k)),
                file_hash=v.file_hash,
                size=v.size,
                mtime=v.mtime,
                permissions=v.permissions,
                backed_up_at=v.backed_up_at,
            )
            for k, v in manifest.entries.items()
        }

        diff = mgr.diff(source_files, manifest, scoped_folders=["Projects"])
        assert diff.deleted_paths == [str(Path("Projects/removed.py"))]
        assert str(Path("Finance/budget.xlsx")) not in diff.deleted_paths
        assert "Projects" not in diff.deleted_paths
        assert "readme.txt" not in diff.deleted_paths
