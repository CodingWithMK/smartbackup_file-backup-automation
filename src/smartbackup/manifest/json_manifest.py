"""
JSON Manifest - JSON-based manifest storage implementation.
"""

import json
from pathlib import Path
from typing import Optional

from smartbackup.manifest.base import Manifest, ManifestManager


class JsonManifestManager(ManifestManager):
    """
    JSON-based manifest manager.

    Stores manifest as a human-readable JSON file.
    Best for smaller backups (< 100,000 files).
    """

    @property
    def manifest_path(self) -> Path:
        """Path to the JSON manifest file."""
        return self.backup_path / f"{self.MANIFEST_FILENAME}.json"

    def exists(self) -> bool:
        """Check if manifest file exists."""
        return self.manifest_path.exists()

    def load(self) -> Optional[Manifest]:
        """
        Load manifest from JSON file.

        Returns:
            Manifest if file exists and is valid, None otherwise
        """
        if not self.exists():
            return None

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Manifest.from_dict(data)
        except (json.JSONDecodeError, IOError, OSError) as e:
            # Log error but don't crash - treat as no manifest
            # This allows recovery from corrupted manifests
            import sys

            print(f"Warning: Failed to load manifest: {e}", file=sys.stderr)
            return None

    def save(self, manifest: Manifest) -> bool:
        """
        Save manifest to JSON file.

        Uses atomic write pattern: write to temp file, then rename.

        Args:
            manifest: The manifest to save

        Returns:
            True if successful, False otherwise
        """
        temp_path = self.manifest_path.with_suffix(".json.tmp")

        try:
            # Ensure directory exists
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file
            data = manifest.to_dict()
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_path.replace(self.manifest_path)
            return True

        except (IOError, OSError) as e:
            # Clean up temp file on failure
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            import sys

            print(f"Warning: Failed to save manifest: {e}", file=sys.stderr)
            return False

    def load_or_create(self, source_path: Path) -> Manifest:
        """
        Load existing manifest or create a new one.

        Args:
            source_path: The source directory being backed up

        Returns:
            Existing or new manifest
        """
        manifest = self.load()
        if manifest is None:
            manifest = self.create(source_path)
        return manifest
