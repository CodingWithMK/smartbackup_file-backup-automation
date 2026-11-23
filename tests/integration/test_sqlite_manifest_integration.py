"""
Integration tests for the SQLite manifest backend across engine, migration,
dry-run, restore, and DriveMatcher (F10).
"""

from pathlib import Path

from smartbackup.config import BackupConfig, ConfigManager
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.core.restore import RestoreEngine
from smartbackup.manifest import (
    JsonManifestManager,
    ManifestFormat,
    SqliteManifestManager,
)
from smartbackup.platform.watcher import DriveMatcher
from smartbackup.ui.logger import BackupLogger


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

        r1 = BackupEngine(cfg, logger).run_backup()
        assert r1.errors == 0
        assert r1.copied_files == 2
        dev_dir = tgt / "Documents-Backup" / "SqlBox"
        assert (dev_dir / ".smartbackup_manifest.db").exists()
        assert not (dev_dir / ".smartbackup_manifest.json").exists()

        r2 = BackupEngine(cfg, logger).run_backup()
        assert r2.errors == 0
        assert r2.copied_files == 0
        assert r2.updated_files == 0
        assert r2.skipped_files == 2

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
        assert not (tgt / "Documents-Backup" / "DrySql" / ".smartbackup_manifest.db").exists()

    def test_format_migration_json_to_sqlite_and_back(self, tmp_path: Path):
        src = tmp_path / "source"
        tgt = tmp_path / "target"
        src.mkdir()
        tgt.mkdir()
        (src / "doc.txt").write_text("original")

        logger = BackupLogger(verbose=False)
        dev_dir = tgt / "Documents-Backup" / "MigBox"

        cfg_json = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="MigBox",
            manifest_format="json",
            log_to_file=False,
        )
        assert BackupEngine(cfg_json, logger).run_backup().copied_files == 1
        assert (dev_dir / ".smartbackup_manifest.json").exists()

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
        assert not (restore_dir / ".smartbackup_manifest.db").exists()

    def test_drive_matcher_recognizes_sqlite_manifest(self, tmp_path: Path):
        drive = tmp_path / "USB"
        dev_dir = drive / "Documents-Backup" / "WatcherSql"
        dev_dir.mkdir(parents=True)
        sm = SqliteManifestManager(dev_dir)
        sm.save(sm.create(tmp_path))

        cfg = ConfigManager()
        cfg.set_device_name("WatcherSql")
        matcher = DriveMatcher(config_manager=cfg)
        assert matcher.is_smartbackup_target(drive, "USB") is True

        legacy_drive = tmp_path / "LEGACY"
        legacy_root = legacy_drive / "Documents-Backup"
        legacy_root.mkdir(parents=True)
        sm_legacy = SqliteManifestManager(legacy_root)
        sm_legacy.save(sm_legacy.create(tmp_path))
        assert matcher.is_smartbackup_target(legacy_drive, "LEGACY") is True
