
from pathlib import Path

from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine
from smartbackup.ui.logger import BackupLogger


class TestMigrationRobustness:
    """Tests for legacy migration robustness."""

    def test_migration_skips_missing_files(self, temp_dir: Path, monkeypatch):
        """Migration should not crash if a file disappears during iteration."""
        backup_root = temp_dir / "Documents-Backup"
        backup_root.mkdir()

        # Create a file that we will simulate disappearing
        volatile_file = backup_root / "volatile.txt"
        volatile_file.write_text("I might disappear")

        # Create a manifest to trigger migration
        (backup_root / ".smartbackup_manifest.json").write_text("{}")

        config = BackupConfig(
            source_path=temp_dir / "source",
            backup_path=temp_dir,
            device_name="MacBook"
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)

        # Monkeypatch iterdir to simulate a file that disappears right before rename
        original_iterdir = Path.iterdir

        def mocked_iterdir(path_obj):
            for item in original_iterdir(path_obj):
                if item.name == "volatile.txt":
                    # Delete it right before it's yielded or processed
                    try:
                        item.unlink()
                    except FileNotFoundError:
                        pass
                yield item

        import pathlib
        monkeypatch.setattr(pathlib.Path, "iterdir", mocked_iterdir)

        # This should NOT crash now
        engine._migrate_legacy_layout(backup_root)

        assert (backup_root / "MacBook").exists()
        assert not (backup_root / "volatile.txt").exists()
