"""
SQLite Manifest - SQLite-based manifest storage implementation.

Designed for large backups (100,000+ files) where loading and writing a single
monolithic JSON document becomes slow or memory-heavy.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from smartbackup.manifest.base import (
    Manifest,
    ManifestEntry,
    ManifestFormat,
    ManifestManager,
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    relative_path TEXT PRIMARY KEY,
    file_hash     TEXT NOT NULL,
    size          INTEGER NOT NULL,
    mtime         REAL NOT NULL,
    permissions   INTEGER NOT NULL,
    backed_up_at  REAL NOT NULL
);
"""


class SqliteManifestManager(ManifestManager):
    """
    SQLite-based manifest manager.

    Stores manifest metadata and file entries in a single `.smartbackup_manifest.db`
    SQLite database using atomic temp-file replacement on save.
    """

    FORMAT = ManifestFormat.SQLITE

    @property
    def manifest_path(self) -> Path:
        """Path to the SQLite manifest database."""
        return self.backup_path / f"{self.MANIFEST_FILENAME}.db"

    def exists(self) -> bool:
        """Check if manifest database exists."""
        return self.manifest_path.exists()

    def load(self) -> Optional[Manifest]:
        """
        Load manifest from SQLite database.

        Returns:
            Manifest if database exists and is valid, None otherwise
        """
        if not self.exists():
            return None

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(str(self.manifest_path))
            cursor = conn.cursor()

            meta_rows = cursor.execute("SELECT key, value FROM metadata").fetchall()
            meta = dict(meta_rows)

            now_iso = datetime.now().isoformat()
            manifest = Manifest(
                version=int(meta.get("version", "1")),
                format=ManifestFormat(meta.get("format", ManifestFormat.SQLITE.value)),
                created=datetime.fromisoformat(meta.get("created", now_iso)),
                updated=datetime.fromisoformat(meta.get("updated", now_iso)),
                source=meta.get("source", ""),
                hostname=meta.get("hostname", ""),
                hash_algorithm=meta.get("hash_algorithm", "sha256"),
                backup_count=int(meta.get("backup_count", "0")),
            )

            file_rows = cursor.execute(
                "SELECT relative_path, file_hash, size, mtime, permissions, backed_up_at "
                "FROM files"
            ).fetchall()
            for rel_path, file_hash, size, mtime, permissions, backed_up_at in file_rows:
                manifest.entries[rel_path] = ManifestEntry(
                    relative_path=rel_path,
                    file_hash=file_hash,
                    size=int(size),
                    mtime=float(mtime),
                    permissions=int(permissions),
                    backed_up_at=float(backed_up_at),
                )

            return manifest
        except (sqlite3.Error, OSError, ValueError) as e:
            print(f"Warning: Failed to load SQLite manifest: {e}", file=sys.stderr)
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def save(self, manifest: Manifest) -> bool:
        """
        Save manifest to SQLite database using an atomic temp-file swap.

        Args:
            manifest: The manifest to save

        Returns:
            True if successful, False otherwise
        """
        temp_path = self.manifest_path.with_suffix(".db.tmp")
        conn: Optional[sqlite3.Connection] = None

        try:
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.unlink(missing_ok=True)

            conn = sqlite3.connect(str(temp_path))
            conn.executescript(_SCHEMA_SQL)

            meta_rows = [
                ("version", str(manifest.version)),
                ("format", ManifestFormat.SQLITE.value),
                ("created", manifest.created.isoformat()),
                ("updated", manifest.updated.isoformat()),
                ("source", str(manifest.source)),
                ("hostname", str(manifest.hostname)),
                ("hash_algorithm", str(manifest.hash_algorithm)),
                ("backup_count", str(manifest.backup_count)),
            ]

            entry_rows = [
                (
                    entry.relative_path,
                    entry.file_hash,
                    entry.size,
                    entry.mtime,
                    entry.permissions,
                    entry.backed_up_at,
                )
                for entry in manifest.entries.values()
            ]

            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    meta_rows,
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO files "
                    "(relative_path, file_hash, size, mtime, permissions, backed_up_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    entry_rows,
                )

            conn.close()
            conn = None

            manifest.format = ManifestFormat.SQLITE
            temp_path.replace(self.manifest_path)
            return True

        except (sqlite3.Error, OSError) as e:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            print(f"Warning: Failed to save SQLite manifest: {e}", file=sys.stderr)
            return False
