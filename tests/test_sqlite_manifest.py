"""
Comprehensive tests for the SQLite manifest backend, factory auto-detection,
format migration, engine/restore/watcher/CLI integration (F10).
"""

import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from smartbackup.cli import app, main
from smartbackup.config import BackupConfig, ConfigManager
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.core.restore import RestoreEngine
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
from smartbackup.platform.watcher import DriveMatcher
from smartbackup.ui.logger import BackupLogger

runner = CliRunner()


# ---------------------------------------------------------------------------
# Unit tests — SqliteManifestManager
# ---------------------------------------------------------------------------


class TestSqliteManifestManager:
    def test_manifest_path_and_exists(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        assert mgr.manifest_path == tmp_path / ".smartbackup_manifest.db"
        assert mgr.exists() is False
        assert mgr.load() is None

    def test_create_save_and_load_roundtrip(self, tmp_path: Path):
        mgr = SqliteManifestManager(tmp_path)
        manifest = mgr.create(Path("/source/docs"))
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
        # Atomic swap: no leftover temp file
        assert not mgr.manifest_path.with_suffix(".db.tmp").exists()

        loaded = mgr.load()
        assert loaded is not None
        assert loaded.version == manifest.version
        assert loaded.format == ManifestFormat.SQLITE
        assert loaded.source == "/source/docs"
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
        created = mgr.load_or_create(Path("/src"))
        assert created.format == ManifestFormat.SQLITE
        assert created.backup_count == 0

        created.backup_count = 7
        assert mgr.save(created) is True

        reloaded = mgr.load_or_create(Path("/other"))
        assert reloaded.backup_count == 7
        assert reloaded.source == "/src"

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

        # Corrupt backup file -> verify catches it
        (bak / "a.txt").write_text("tampered!")
        errors = mgr.verify(loaded, bak, verify_hashes=True)
        assert len(errors) == 1
        assert "Size mismatch" in errors[0] or "Hash mismatch" in errors[0]


# ---------------------------------------------------------------------------
# Unit tests — Manifest Factory & Auto-Detection
# ---------------------------------------------------------------------------


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

        # Make SQLite explicitly newer
        now = time.time()
        os.utime(jm.manifest_path, (now - 100, now - 100))
        os.utime(sm.manifest_path, (now, now))
        assert isinstance(detect_manifest_manager(tmp_path), SqliteManifestManager)

        # Make JSON explicitly newer
        os.utime(jm.manifest_path, (now + 100, now + 100))
        assert isinstance(detect_manifest_manager(tmp_path), JsonManifestManager)

    def test_get_manifest_manager_explicit_and_invalid(self, tmp_path: Path):
        assert isinstance(get_manifest_manager(tmp_path, "json"), JsonManifestManager)
        assert isinstance(get_manifest_manager(tmp_path, "SQLITE"), SqliteManifestManager)
        assert isinstance(
            get_manifest_manager(tmp_path, ManifestFormat.SQLITE), SqliteManifestManager
        )
        # Auto-detect on empty dir defaults to JSON
        assert isinstance(get_manifest_manager(tmp_path), JsonManifestManager)

        with pytest.raises(ValueError, match="Unsupported manifest format"):
            get_manifest_manager(tmp_path, "yaml")


# ---------------------------------------------------------------------------
# Integration tests — Engine, Migration, Dry-Run, Restore, Watcher
# ---------------------------------------------------------------------------


class TestSqliteEngineIntegration:
    def test_incremental_backup_with_sqlite_manifest(self, tmp_path: Path):
        src = tmp_path / "source"
        tgt = tmp_path / "target"
        src.mkdir()
        tgt.mkdir()
        (src / "one.txt").write_text("v1")
        (src / "two.txt").write_text("v1")

        cfg = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="SqlBox",
            manifest_format="sqlite",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)

        # 1. Initial backup creates .smartbackup_manifest.db (NOT .json)
        r1 = BackupEngine(cfg, logger).run_backup()
        assert r1.errors == 0
        assert r1.copied_files == 2
        dev_dir = tgt / "Documents-Backup" / "SqlBox"
        assert (dev_dir / ".smartbackup_manifest.db").exists()
        assert not (dev_dir / ".smartbackup_manifest.json").exists()

        # 2. Second run with no changes skips both
        r2 = BackupEngine(cfg, logger).run_backup()
        assert r2.errors == 0
        assert r2.copied_files == 0
        assert r2.updated_files == 0
        assert r2.skipped_files == 2

        # 3. Modify one, delete the other
        (src / "one.txt").write_text("v2-updated")
        (src / "two.txt").unlink()
        r3 = BackupEngine(cfg, logger).run_backup()
        assert r3.errors == 0
        assert r3.updated_files == 1
        assert (dev_dir / "one.txt").read_text() == "v2-updated"
        assert not (dev_dir / "two.txt").exists()

        loaded = SqliteManifestManager(dev_dir).load()
        assert loaded is not None
        assert loaded.backup_count == 3
        assert loaded.total_files == 1
        assert loaded.has_entry("one.txt")
        assert not loaded.has_entry("two.txt")

    def test_dry_run_with_sqlite_does_not_create_db(self, tmp_path: Path):
        src = tmp_path / "source"
        tgt = tmp_path / "target"
        src.mkdir()
        tgt.mkdir()
        (src / "a.txt").write_text("hello")

        cfg = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="DrySql",
            manifest_format="sqlite",
            log_to_file=False,
        )
        r = DryRunBackupEngine(cfg, BackupLogger(verbose=False)).run_backup()
        assert r.errors == 0
        dev_dir = tgt / "Documents-Backup" / "DrySql"
        assert not (dev_dir / ".smartbackup_manifest.db").exists()

    def test_format_migration_json_to_sqlite_and_back(self, tmp_path: Path):
        src = tmp_path / "source"
        tgt = tmp_path / "target"
        src.mkdir()
        tgt.mkdir()
        (src / "doc.txt").write_text("original")

        logger = BackupLogger(verbose=False)
        dev_dir = tgt / "Documents-Backup" / "MigBox"

        # 1. Start with JSON
        cfg_json = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="MigBox",
            manifest_format="json",
            log_to_file=False,
        )
        assert BackupEngine(cfg_json, logger).run_backup().copied_files == 1
        assert (dev_dir / ".smartbackup_manifest.json").exists()

        # 2. Dry-run with SQLite must NOT migrate or remove JSON
        cfg_sql = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="MigBox",
            manifest_format="sqlite",
            log_to_file=False,
        )
        assert DryRunBackupEngine(cfg_sql, logger).run_backup().errors == 0
        assert (dev_dir / ".smartbackup_manifest.json").exists()
        assert not (dev_dir / ".smartbackup_manifest.db").exists()

        # 3. Real run with SQLite migrates and cleans up JSON (unchanged file is skipped!)
        r_mig = BackupEngine(cfg_sql, logger).run_backup()
        assert r_mig.errors == 0
        assert r_mig.skipped_files == 1
        assert r_mig.copied_files == 0
        assert (dev_dir / ".smartbackup_manifest.db").exists()
        assert not (dev_dir / ".smartbackup_manifest.json").exists()

        loaded_sql = SqliteManifestManager(dev_dir).load()
        assert loaded_sql is not None
        assert loaded_sql.backup_count == 2
        assert loaded_sql.format == ManifestFormat.SQLITE

        # 4. Migrate back to JSON
        r_back = BackupEngine(cfg_json, logger).run_backup()
        assert r_back.errors == 0
        assert r_back.skipped_files == 1
        assert (dev_dir / ".smartbackup_manifest.json").exists()
        assert not (dev_dir / ".smartbackup_manifest.db").exists()

        loaded_json = JsonManifestManager(dev_dir).load()
        assert loaded_json is not None
        assert loaded_json.backup_count == 3
        assert loaded_json.format == ManifestFormat.JSON

    def test_restore_engine_reads_sqlite_manifest(self, tmp_path: Path):
        src = tmp_path / "source"
        tgt = tmp_path / "target"
        restore_dir = tmp_path / "restored"
        src.mkdir()
        tgt.mkdir()
        (src / "report.txt").write_text("quarterly numbers")

        cfg = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="RestoreSql",
            manifest_format="sqlite",
            log_to_file=False,
        )
        assert BackupEngine(cfg, BackupLogger(verbose=False)).run_backup().errors == 0

        engine = RestoreEngine(
            backup_path=tgt,
            target_path=restore_dir,
            logger=BackupLogger(verbose=False),
            device_name="RestoreSql",
        )
        info = engine.get_manifest_info()
        assert info is not None
        assert info["total_files"] == 1
        assert info["backup_count"] == 1

        listed = engine.list_files()
        assert len(listed) == 1
        assert listed[0][0] == Path("report.txt")

        res = engine.restore()
        assert res.errors == 0
        assert res.restored_files == 1
        assert (restore_dir / "report.txt").read_text() == "quarterly numbers"
        # Internal .smartbackup_manifest.db must never be restored
        assert not (restore_dir / ".smartbackup_manifest.db").exists()

    def test_drive_matcher_recognizes_sqlite_manifest(self, tmp_path: Path, monkeypatch):
        drive = tmp_path / "USB"
        dev_dir = drive / "Documents-Backup" / "WatcherSql"
        dev_dir.mkdir(parents=True)
        sm = SqliteManifestManager(dev_dir)
        sm.save(sm.create(tmp_path))

        monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg")
        cfg = ConfigManager()
        cfg.set_device_name("WatcherSql")
        matcher = DriveMatcher(config_manager=cfg)
        assert matcher.is_smartbackup_target(drive, "USB") is True

        # Legacy flat SQLite manifest also recognized
        legacy_drive = tmp_path / "LEGACY"
        legacy_root = legacy_drive / "Documents-Backup"
        legacy_root.mkdir(parents=True)
        sm_legacy = SqliteManifestManager(legacy_root)
        sm_legacy.save(sm_legacy.create(tmp_path))
        assert matcher.is_smartbackup_target(legacy_drive, "LEGACY") is True


# ---------------------------------------------------------------------------
# CLI wiring tests — --manifest-format, --show-manifest, --verify, --list-devices
# ---------------------------------------------------------------------------


class TestSqliteManifestCLI:
    def test_cli_sqlite_backup_inspect_verify_and_list_devices(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg")
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        (src / "app.py").write_text("print('hi')")

        # Run backup with --manifest-format sqlite
        res = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(tgt),
                "--device-name",
                "CliSql",
                "--manifest-format",
                "sqlite",
            ],
        )
        assert res.exit_code == 0, res.output
        assert (tgt / "Documents-Backup" / "CliSql" / ".smartbackup_manifest.db").exists()

        # --show-manifest reads SQLite and displays format "sqlite"
        show = runner.invoke(
            app, ["--show-manifest", "--target", str(tgt), "--device-name", "CliSql"]
        )
        assert show.exit_code == 0, show.output
        assert "sqlite" in show.output.lower()

        # --verify succeeds on SQLite manifest
        verify = runner.invoke(
            app, ["--verify", "--target", str(tgt), "--device-name", "CliSql"]
        )
        assert verify.exit_code == 0, verify.output

        # --list-devices lists the SQLite-backed device
        devices = runner.invoke(app, ["--list-devices", "--target", str(tgt)])
        assert devices.exit_code == 0, devices.output
        assert "CliSql" in devices.output

    def test_cli_invalid_manifest_format_exits_1(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg")
        res = runner.invoke(
            app, ["--target", str(tmp_path), "--manifest-format", "bogus"]
        )
        assert res.exit_code == 1
        assert "Unsupported manifest format" in res.output

    def test_cli_uses_configured_manifest_format_and_flag_overrides(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: tmp_path / "cfg")
        ConfigManager().set_manifest_format("sqlite")

        # Without flag -> config wins ("sqlite")
        with patch.object(sys, "argv", ["smartbackup", "--target", str(tmp_path)]):
            with patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run:
                assert main() == 0
        assert mock_run.call_args.kwargs["manifest_format"] == "sqlite"

        # With explicit flag -> flag wins ("json")
        with patch.object(
            sys,
            "argv",
            ["smartbackup", "--target", str(tmp_path), "--manifest-format", "json"],
        ):
            with patch("smartbackup.cli.SmartBackup.run", return_value=True) as mock_run:
                assert main() == 0
        assert mock_run.call_args.kwargs["manifest_format"] == "json"
