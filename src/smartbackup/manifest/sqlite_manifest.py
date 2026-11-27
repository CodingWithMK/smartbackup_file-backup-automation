"""
SQLite Manifest - SQLite-based manifest storage implementation.

Designed for large backups (100,000+ files) where loading and writing a single
monolithic JSON document becomes slow or memory-heavy.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from smartbackup.manifest.base import (
    Manifest,
    ManifestEntry,
    ManifestFormat,
    ManifestManager,
    SelectiveBackupRecord,
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

CREATE TABLE IF NOT EXISTS selective_backups (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                  TEXT    NOT NULL,
    timestamp               TEXT    NOT NULL,
    command_option          TEXT    NOT NULL DEFAULT '--select',
    scope                   TEXT    NOT NULL DEFAULT 'folders',
    source_root             TEXT    NOT NULL DEFAULT '',
    selected_folders        TEXT    NOT NULL DEFAULT '[]',
    available_folders_count INTEGER NOT NULL DEFAULT 0,
    files_scanned           INTEGER NOT NULL DEFAULT 0,
    files_copied            INTEGER NOT NULL DEFAULT 0,
    files_updated           INTEGER NOT NULL DEFAULT 0,
    files_deleted           INTEGER NOT NULL DEFAULT 0,
    files_skipped           INTEGER NOT NULL DEFAULT 0,
    bytes_copied            INTEGER NOT NULL DEFAULT 0,
    duration_seconds        REAL    NOT NULL DEFAULT 0.0,
    workflow_steps          TEXT    NOT NULL DEFAULT '[]'
);
"""


def _safe_json_list(raw: Optional[str]) -> list[str]:
    """Decode a JSON-encoded list of strings, falling back to an empty list."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


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
                last_backup_mode=meta.get("last_backup_mode", "full"),
                last_selected_folders=_safe_json_list(meta.get("last_selected_folders")),
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

            # Backward-compatible load of dedicated selective_backups table
            has_selective_table = (
                cursor.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'selective_backups'"
                ).fetchone()
                is not None
            )
            if has_selective_table:
                selective_rows = cursor.execute(
                    "SELECT run_id, timestamp, command_option, scope, source_root, "
                    "selected_folders, available_folders_count, files_scanned, "
                    "files_copied, files_updated, files_deleted, files_skipped, "
                    "bytes_copied, duration_seconds, workflow_steps "
                    "FROM selective_backups ORDER BY id ASC"
                ).fetchall()
                for row in selective_rows:
                    manifest.selective_backups.append(
                        SelectiveBackupRecord(
                            run_id=str(row[0]),
                            timestamp=datetime.fromisoformat(row[1]),
                            command_option=str(row[2]),
                            scope=str(row[3]),
                            source_root=str(row[4]),
                            selected_folders=_safe_json_list(row[5]),
                            available_folders_count=int(row[6]),
                            files_scanned=int(row[7]),
                            files_copied=int(row[8]),
                            files_updated=int(row[9]),
                            files_deleted=int(row[10]),
                            files_skipped=int(row[11]),
                            bytes_copied=int(row[12]),
                            duration_seconds=float(row[13]),
                            workflow_steps=_safe_json_list(row[14]),
                        )
                    )

            return manifest
        except (sqlite3.Error, OSError, ValueError, TypeError) as e:
            self._warn(f"Failed to load SQLite manifest: {e}")
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
                ("last_backup_mode", str(manifest.last_backup_mode)),
                ("last_selected_folders", json.dumps(list(manifest.last_selected_folders))),
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

            selective_rows = [
                (
                    rec.run_id,
                    rec.timestamp.isoformat(),
                    rec.command_option,
                    rec.scope,
                    rec.source_root,
                    json.dumps(list(rec.selected_folders)),
                    rec.available_folders_count,
                    rec.files_scanned,
                    rec.files_copied,
                    rec.files_updated,
                    rec.files_deleted,
                    rec.files_skipped,
                    rec.bytes_copied,
                    rec.duration_seconds,
                    json.dumps(list(rec.workflow_steps)),
                )
                for rec in manifest.selective_backups
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
                if selective_rows:
                    conn.executemany(
                        "INSERT INTO selective_backups ("
                        "run_id, timestamp, command_option, scope, source_root, "
                        "selected_folders, available_folders_count, files_scanned, "
                        "files_copied, files_updated, files_deleted, files_skipped, "
                        "bytes_copied, duration_seconds, workflow_steps"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        selective_rows,
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
            self._warn(f"Failed to save SQLite manifest: {e}")
            return False
