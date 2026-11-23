"""
Unit tests for SqliteManifestManager and the manifest factory / auto-detection.
"""

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytest

from smartbackup.manifest import (
    JsonManifestManager,
    ManifestEntry,
    ManifestFormat,
    SqliteManifestManager,
    detect_manifest_manager,
    get_manifest_manager,
    has_manifest,
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
