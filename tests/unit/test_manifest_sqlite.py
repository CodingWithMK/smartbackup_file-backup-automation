"""
Unit tests for SqliteManifestManager and the manifest factory / auto-detection.
"""

import builtins
import hashlib
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smartbackup.manifest import (
    JsonManifestManager,
    ManifestEntry,
    ManifestFormat,
    SelectiveBackupRecord,
    SqliteManifestManager,
    detect_manifest_manager,
    get_manifest_manager,
    has_manifest,
    resolve_device_target,
)
from smartbackup.models import FileInfo


class TestSqliteManifestManager:
    def test_manifest_path_and_exists(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        assert mgr.manifest_path == tmp_path / ".smartbackup_manifest.db"
        assert mgr.exists() is False
        assert mgr.load() is None

    def test_create_save_and_load_roundtrip(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        source_path = Path("/source/docs")
        manifest = mgr.create(source_path)
        manifest.hostname = "DevLaptop"
        manifest.backup_count = 3
        manifest.hash_algorithm = "sha256"
        manifest.add_entry(
            ManifestEntry(
                relative_path="notes/todo.md",
                file_hash="deadbeef" * 8,
                size=512,
                mtime=1700000000.5,
                permissions=0o100644,
                backed_up_at=1700000100.25,
            )
        )
        manifest.add_entry(
            ManifestEntry(
                relative_path="unicode/ümlaut-日本語.txt",
                file_hash="cafebabe" * 8,
                size=42,
                mtime=1700000001.0,
                permissions=0o100600,
                backed_up_at=1700000100.25,
            )
        )

        assert mgr.save(manifest) is True
        assert mgr.exists() is True
        assert not mgr.manifest_path.with_suffix(".db.tmp").exists()

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.version == manifest.version
        assert loaded.format == ManifestFormat.SQLITE
        assert loaded.source == str(source_path)
        assert loaded.hostname == "DevLaptop"
        assert loaded.hash_algorithm == "sha256"
        assert loaded.backup_count == 3
        assert loaded.total_files == 2
        assert loaded.total_size == 554
        assert isinstance(loaded.created, datetime)
        assert isinstance(loaded.updated, datetime)

        entry = loaded.get_entry("notes/todo.md")
        assert entry is not None
        assert entry.file_hash == "deadbeef" * 8
        assert entry.size == 512
        assert entry.mtime == pytest.approx(1700000000.5)
        assert entry.permissions == 0o100644
        assert loaded.get_entry("unicode/ümlaut-日本語.txt") is not None

    def test_load_or_create_reuses_existing(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        initial_source = Path("/src")
        created = mgr.load_or_create(initial_source)
        assert created.format == ManifestFormat.SQLITE
        assert created.backup_count == 0

        created.backup_count = 7
        assert mgr.save(created) is True

        reloaded = mgr.load_or_create(Path("/other"))
        assert reloaded.backup_count == 7
        assert reloaded.source == str(initial_source)

    def test_corrupted_sqlite_returns_none(self, tmp_path: Path, capsys):
        mgr = SqliteManifestManager(tmp_path)
        mgr.manifest_path.write_bytes(b"this is definitely not a sqlite database")

        assert mgr.exists() is True
        assert mgr.load() is None
        captured = capsys.readouterr()
        assert "Failed to load SQLite manifest" in captured.err

    def test_missing_tables_sqlite_returns_none(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        conn = sqlite3.connect(str(mgr.manifest_path))
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.close()

        assert mgr.load() is None

    def test_diff_update_and_verify(self, tmp_path: Path):
        src = tmp_path / "src"
        bak = tmp_path / "bak"
        src.mkdir()
        bak.mkdir()

        f1 = src / "a.txt"
        f1.write_text("hello")
        (bak / "a.txt").write_text("hello")

        mgr = SqliteManifestManager(bak)
        manifest = mgr.create(src)
        fi1 = FileInfo(
            path=f1,
            relative_path=Path("a.txt"),
            size=f1.stat().st_size,
            mtime=f1.stat().st_mtime,
            file_hash=mgr._hash_file(f1),
        )
        mgr.update_from_backup(manifest, [fi1])
        assert mgr.save(manifest) is True

        loaded = mgr.load()
        assert loaded is not None
        assert mgr.verify(loaded, bak, verify_hashes=True) == []

        (bak / "a.txt").write_text("tampered!")
        errors = mgr.verify(loaded, bak, verify_hashes=True)
        assert len(errors) == 1
        assert "Size mismatch" in errors[0] or "Hash mismatch" in errors[0]


class TestManifestFactory:
    def test_has_manifest_detects_both_formats(self, tmp_path: Path):
        assert has_manifest(tmp_path) is False

        json_dir = tmp_path / "j"
        json_dir.mkdir()
        JsonManifestManager(json_dir).save(JsonManifestManager(json_dir).create(tmp_path))
        assert has_manifest(json_dir) is True

        sql_dir = tmp_path / "s"
        sql_dir.mkdir()
        SqliteManifestManager(sql_dir).save(SqliteManifestManager(sql_dir).create(tmp_path))
        assert has_manifest(sql_dir) is True

    def test_detect_manifest_manager_prefers_newer_when_both_exist(self, tmp_path: Path):
        jm = JsonManifestManager(tmp_path)
        sm = SqliteManifestManager(tmp_path)
        jm.save(jm.create(tmp_path))
        sm.save(sm.create(tmp_path))

        now = time.time()
        os.utime(jm.manifest_path, (now - 100, now - 100))
        os.utime(sm.manifest_path, (now, now))
        assert isinstance(detect_manifest_manager(tmp_path), SqliteManifestManager)

        os.utime(jm.manifest_path, (now + 100, now + 100))
        assert isinstance(detect_manifest_manager(tmp_path), JsonManifestManager)

    def test_get_manifest_manager_explicit_and_invalid(self, tmp_path: Path):
        assert isinstance(get_manifest_manager(tmp_path, "json"), JsonManifestManager)
        assert isinstance(get_manifest_manager(tmp_path, "SQLITE"), SqliteManifestManager)
        assert isinstance(
            get_manifest_manager(tmp_path, ManifestFormat.SQLITE), SqliteManifestManager
        )
        assert isinstance(get_manifest_manager(tmp_path), JsonManifestManager)

        with pytest.raises(ValueError, match="Unsupported manifest format"):
            get_manifest_manager(tmp_path, "yaml")


class TestSqliteSelectiveManifest:
    """Tests for dedicated SQLite selective_backups table separation & backward compat."""

    def test_selective_backups_stored_in_dedicated_table_and_roundtrips(
        self, tmp_path: Path
    ) -> None:
        mgr = SqliteManifestManager(tmp_path)
        manifest = mgr.create(Path("/docs"))
        manifest.add_entry(
            ManifestEntry(
                relative_path="Projects/main.py",
                file_hash="a" * 64,
                size=128,
                mtime=1700000000.0,
                permissions=0o644,
                backed_up_at=1700000100.0,
            )
        )
        manifest.add_selective_backup(
            SelectiveBackupRecord(
                run_id="20261124_010000_#1",
                source_root="/docs",
                selected_folders=["Projects"],
                available_folders_count=4,
                files_scanned=1,
                files_copied=1,
                files_updated=0,
                files_deleted=0,
                files_skipped=0,
                bytes_copied=128,
                duration_seconds=0.42,
                workflow_steps=["CLI invoked with --select", "Scoped scan completed"],
            )
        )

        assert mgr.save(manifest) is True

        # Verify dedicated SQLite table separation directly via sqlite3
        conn = sqlite3.connect(str(mgr.manifest_path))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {"metadata", "files", "selective_backups"}.issubset(tables)
            sel_count = conn.execute("SELECT COUNT(*) FROM selective_backups").fetchone()[0]
            file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            assert sel_count == 1
            assert file_count == 1
        finally:
            conn.close()

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.last_backup_mode == "select"
        assert loaded.last_selected_folders == ["Projects"]
        assert len(loaded.selective_backups) == 1
        rec = loaded.selective_backups[0]
        assert rec.run_id == "20261124_010000_#1"
        assert rec.selected_folders == ["Projects"]
        assert rec.available_folders_count == 4
        assert rec.files_copied == 1
        assert rec.bytes_copied == 128
        assert rec.workflow_steps == ["CLI invoked with --select", "Scoped scan completed"]

    def test_legacy_sqlite_db_without_selective_backups_table_loads_cleanly(
        self, tmp_path: Path
    ) -> None:
        mgr = SqliteManifestManager(tmp_path)
        conn = sqlite3.connect(str(mgr.manifest_path))
        try:
            conn.executescript(
                """
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE files (
                    relative_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    permissions INTEGER NOT NULL,
                    backed_up_at REAL NOT NULL
                );
                """
            )
            conn.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                [
                    ("version", "1"),
                    ("format", "sqlite"),
                    ("created", "2026-01-01T00:00:00"),
                    ("updated", "2026-01-01T00:00:00"),
                    ("source", "/legacy"),
                    ("hostname", "LegacyBox"),
                    ("hash_algorithm", "sha256"),
                    ("backup_count", "2"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.backup_count == 2
        assert loaded.last_backup_mode == "full"
        assert loaded.last_selected_folders == []
        assert loaded.selective_backups == []


class TestSqliteHardeningAndDeviceResolution:
    """Q1, Q6, and Q7 regression tests for SQLite manifest & resolve_device_target()."""

    def test_verify_reports_error_when_file_unreadable_during_hashing(
        self, tmp_path: Path
    ) -> None:
        bak = tmp_path / "bak"
        bak.mkdir()
        target = bak / "data.bin"
        content = b"sqlite-verified-bytes"
        target.write_bytes(content)

        mgr = SqliteManifestManager(bak)
        manifest = mgr.create(tmp_path / "src")
        manifest.add_entry(
            ManifestEntry(
                relative_path="data.bin",
                file_hash=hashlib.sha256(content).hexdigest(),
                size=len(content),
                mtime=1000.0,
                permissions=0o644,
                backed_up_at=1000.0,
            )
        )
        assert mgr.save(manifest) is True
        loaded = mgr.load()
        assert loaded is not None

        # Control: readable passes
        assert mgr.verify(loaded, bak, verify_hashes=True) == []

        real_open = builtins.open

        def fail_open(file, *args, **kwargs):
            if Path(file) == target:
                raise PermissionError("locked file")
            return real_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=fail_open):
            errors = mgr.verify(loaded, bak, verify_hashes=True)

        assert len(errors) == 1
        assert "Error hashing" in errors[0]

    def test_corrupt_sqlite_manifest_logs_warning_via_injected_logger_not_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_logger = MagicMock()
        mgr = get_manifest_manager(tmp_path, "sqlite", logger=mock_logger)
        mgr.manifest_path.write_bytes(b"corrupt sqlite header")

        assert mgr.load() is None
        assert capsys.readouterr().err == ""
        mock_logger.warning.assert_called_once()
        assert "Failed to load SQLite manifest" in mock_logger.warning.call_args[0][0]

    def test_sqlite_manifest_save_failure_routes_warning_to_logger(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_logger = MagicMock()
        mgr = SqliteManifestManager(tmp_path, logger=mock_logger)
        manifest = mgr.create(tmp_path / "src")

        with patch("smartbackup.manifest.sqlite_manifest.sqlite3.connect", side_effect=sqlite3.OperationalError("readonly")):
            ok = mgr.save(manifest)

        assert ok is False
        assert capsys.readouterr().err == ""
        mock_logger.warning.assert_called_once()
        assert "Failed to save SQLite manifest" in mock_logger.warning.call_args[0][0]

    def test_resolve_device_target_explicit_and_whitespace(self, tmp_path: Path) -> None:
        root = tmp_path / "Documents-Backup"
        root.mkdir()
        assert resolve_device_target(root, "My-PC") == root / "My-PC"
        assert resolve_device_target(root, "  My-PC  ") == root / "My-PC"
        # Whitespace-only falls back to auto-detection / root
        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(root, "   ") == root

    def test_resolve_device_target_legacy_json_and_sqlite_roots(self, tmp_path: Path) -> None:
        json_root = tmp_path / "legacy_json"
        json_root.mkdir()
        jm = JsonManifestManager(json_root)
        jm.save(jm.create(tmp_path))
        (json_root / "AutoBox").mkdir()

        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(json_root) == json_root

        sql_root = tmp_path / "legacy_sql"
        sql_root.mkdir()
        sm = SqliteManifestManager(sql_root)
        sm.save(sm.create(tmp_path))
        (sql_root / "AutoBox").mkdir()

        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(sql_root) == sql_root

    def test_resolve_device_target_auto_detects_dir_and_ignores_file_collision(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "Documents-Backup"
        root.mkdir()
        (root / "AutoBox").mkdir()

        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(root) == root / "AutoBox"

        # Fragility guard: a regular file named after the hostname must NOT be treated as target dir
        file_root = tmp_path / "file_collision"
        file_root.mkdir()
        (file_root / "AutoBox").write_text("regular file, not a dir")

        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(file_root) == file_root

    def test_resolve_device_target_missing_root_fallback(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        with patch("smartbackup.platform.identity.get_device_name", return_value="AutoBox"):
            assert resolve_device_target(missing) == missing
            assert resolve_device_target(missing, "ExplicitDev") == missing / "ExplicitDev"
