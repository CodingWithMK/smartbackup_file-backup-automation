
from pathlib import Path

from smartbackup.manifest.base import Manifest, ManifestEntry
from smartbackup.manifest.json_manifest import JsonManifestManager


def test_manifest_sync_deletes_entries():
    """Manifest should remove entries that were deleted during sync."""
    manifest = Manifest()
    manifest.add_entry(ManifestEntry(
        relative_path="keep.txt", size=10, mtime=100.0,
        file_hash="", permissions=0o644, backed_up_at=0.0
    ))
    manifest.add_entry(ManifestEntry(
        relative_path="delete.txt", size=20, mtime=200.0,
        file_hash="", permissions=0o644, backed_up_at=0.0
    ))

    assert manifest.total_files == 2

    manager = JsonManifestManager(Path("/tmp")) # path doesn't matter for logic

    # Update manifest with 0 backed up files and 1 deleted path
    updated = manager.update_from_backup(manifest, [], deleted_paths=["delete.txt"])

    assert updated.total_files == 1
    assert "keep.txt" in updated.entries
    assert "delete.txt" not in updated.entries
