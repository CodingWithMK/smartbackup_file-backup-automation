"""
Integration tests for BackupEngine, DryRunBackupEngine, BackupCompressor, and BackupLogger.
"""

import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from rich.progress import Progress

from smartbackup.config import DEFAULT_EXCLUSIONS, BackupConfig
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.ui.logger import BackupLogger


class TestBackupEngineIntegration:
    """Integration tests for full BackupEngine.run_backup() workflows."""

    def test_run_backup_creates_folder(self, source_dir: Path, backup_dir: Path):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))
        engine.run_backup()
        assert (backup_dir / "TestBackup").exists()

    def test_run_backup_copies_files(self, source_dir: Path, backup_dir: Path):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))
        result = engine.run_backup()

        assert result.copied_files > 0
        assert (backup_dir / "TestBackup" / "file1.txt").exists()

    def test_run_backup_result(self, source_dir: Path, backup_dir: Path):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        engine = BackupEngine(config, BackupLogger(verbose=False))
        result = engine.run_backup()

        assert result.total_files > 0
        assert result.errors == 0
        assert result.end_time is not None

    def test_run_backup_incremental(self, source_dir: Path, backup_dir: Path):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=False)

        result1 = BackupEngine(config, logger).run_backup()
        copied_first = result1.copied_files

        result2 = BackupEngine(config, logger).run_backup()
        assert result2.copied_files == 0
        assert result2.skipped_files == copied_first

    def test_custom_exclusions_applied_in_run_backup(
        self, source_dir: Path, backup_dir: Path
    ):
        """Custom exclusion patterns must reach the scan (Phase 0 / F2)."""
        (source_dir / "image.iso").write_bytes(b"iso-image")

        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
            exclusions=DEFAULT_EXCLUSIONS | {"*.iso"},
        )
        BackupEngine(config, BackupLogger(verbose=False)).run_backup()

        assert not (backup_dir / "TestBackup" / "image.iso").exists()
        assert (backup_dir / "TestBackup" / "file1.txt").exists()

    def test_engine_creates_single_progress_bar_across_multiple_files(self, tmp_path: Path):
        """BackupEngine should create Progress at most once for an entire backup run."""
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        src.mkdir()
        tgt.mkdir()
        for i in range(5):
            (src / f"doc_{i}.txt").write_text(f"content-{i}")

        cfg = BackupConfig(
            source_path=src,
            backup_path=tgt,
            device_name="ProgBox",
            log_to_file=False,
        )
        logger = BackupLogger(verbose=True)

        created = []
        orig_progress = Progress

        def tracking_progress(*args, **kwargs):
            bar = orig_progress(*args, **kwargs)
            created.append(bar)
            return bar

        with patch("smartbackup.ui.logger.Progress", side_effect=tracking_progress):
            result = BackupEngine(cfg, logger).run_backup()

        assert result.errors == 0
        assert result.copied_files == 5
        assert len(created) == 1
        assert logger._progress_bar is None
        assert logger._progress_line_active is False


class TestDryRunBackupEngineIntegration:
    """Integration tests for DryRunBackupEngine.run_backup() state isolation."""

    def _make_config(self, source_dir: Path, backup_dir: Path, **kwargs) -> BackupConfig:
        return BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
            **kwargs,
        )

    def test_dry_run_does_not_create_manifest_on_fresh_target(
        self, source_dir: Path, backup_dir: Path
    ):
        config = self._make_config(source_dir, backup_dir)
        logger = BackupLogger(verbose=False)

        result = DryRunBackupEngine(config, logger).run_backup()
        manifest_path = backup_dir / "TestBackup" / ".smartbackup_manifest.json"
        assert not manifest_path.exists()
        assert result.copied_files > 0

        real_result = BackupEngine(config, logger).run_backup()
        assert real_result.copied_files > 0
        assert (backup_dir / "TestBackup" / "file1.txt").exists()

    def test_dry_run_does_not_update_manifest_then_real_run_copies_changes(
        self, source_dir: Path, backup_dir: Path
    ):
        config = self._make_config(source_dir, backup_dir)
        logger = BackupLogger(verbose=False)
        manifest_path = backup_dir / "TestBackup" / ".smartbackup_manifest.json"

        BackupEngine(config, logger).run_backup()
        before = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "file1.txt" in before["files"]

        (source_dir / "file1.txt").write_text("CHANGED CONTENT")
        DryRunBackupEngine(config, logger).run_backup()

        after = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert after["files"]["file1.txt"]["size"] == before["files"]["file1.txt"]["size"]
        assert after["files"]["file1.txt"]["mtime"] == before["files"]["file1.txt"]["mtime"]
        assert after["backup_count"] == before["backup_count"]

        result = BackupEngine(config, logger).run_backup()
        assert result.updated_files == 1
        assert (backup_dir / "TestBackup" / "file1.txt").read_text() == "CHANGED CONTENT"

    def test_dry_run_keeps_entries_for_deleted_source_files(
        self, source_dir: Path, backup_dir: Path
    ):
        config = self._make_config(source_dir, backup_dir)
        logger = BackupLogger(verbose=False)
        manifest_path = backup_dir / "TestBackup" / ".smartbackup_manifest.json"

        BackupEngine(config, logger).run_backup()
        (source_dir / "file2.py").unlink()

        DryRunBackupEngine(config, logger).run_backup()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "file2.py" in manifest["files"]
        assert (backup_dir / "TestBackup" / "file2.py").exists()

        BackupEngine(config, logger).run_backup()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "file2.py" not in manifest["files"]
        assert not (backup_dir / "TestBackup" / "file2.py").exists()

    def test_dry_run_does_not_create_archive_with_compress(
        self, source_dir: Path, backup_dir: Path
    ):
        config = self._make_config(source_dir, backup_dir, compress_format="zip")
        DryRunBackupEngine(config, BackupLogger(verbose=False)).run_backup()
        assert not list(backup_dir.rglob("*.zip"))

    def test_dry_run_does_not_migrate_legacy_layout(
        self, source_dir: Path, backup_dir: Path
    ):
        legacy_root = backup_dir / "TestBackup"
        legacy_root.mkdir()
        (legacy_root / "old.txt").write_text("legacy content")
        (legacy_root / ".smartbackup_manifest.json").write_text(
            json.dumps({"version": 1, "format": "json"}), encoding="utf-8"
        )

        config = self._make_config(source_dir, backup_dir, device_name="TestDev")
        DryRunBackupEngine(config, BackupLogger(verbose=False)).run_backup()

        assert (legacy_root / "old.txt").exists()
        assert not (legacy_root / "TestDev" / "old.txt").exists()


class TestCompressionIntegration:
    """Tests for compression integrated with BackupEngine."""

    def test_backup_without_compress_flag_no_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
            compress_format=None,
        )
        BackupEngine(config, BackupLogger(verbose=False)).run_backup()

        backup_root = backup_dir / "TestBackup"
        assert len(list(backup_root.glob("*.zip"))) == 0
        assert len(list(backup_root.glob("*.tar.gz"))) == 0

    def test_backup_with_compress_zip_creates_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="zip",
        )
        result = BackupEngine(config, BackupLogger(verbose=False)).run_backup()

        assert result.errors == 0
        zip_files = list((backup_dir / "TestBackup").glob("TestDevice_*.zip"))
        assert len(zip_files) == 1
        assert zipfile.is_zipfile(zip_files[0])

    def test_backup_with_compress_tar_gz_creates_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="tar.gz",
        )
        result = BackupEngine(config, BackupLogger(verbose=False)).run_backup()

        assert result.errors == 0
        tar_files = list((backup_dir / "TestBackup").glob("TestDevice_*.tar.gz"))
        assert len(tar_files) == 1
        with tarfile.open(tar_files[0], "r:gz") as tf:
            assert len(tf.getmembers()) > 0

    def test_backup_compress_archive_contains_backed_up_files(
        self, source_dir: Path, backup_dir: Path
    ):
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="zip",
        )
        BackupEngine(config, BackupLogger(verbose=False)).run_backup()

        zip_files = list((backup_dir / "TestBackup").glob("TestDevice_*.zip"))
        assert len(zip_files) == 1

        with zipfile.ZipFile(zip_files[0], "r") as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            assert "file1.txt" in names
            assert "file2.py" in names
