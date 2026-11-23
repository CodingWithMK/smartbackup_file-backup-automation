"""
Integration tests for the failed-path-validation exit contract (F11)
across BackupEngine, SmartBackup.run(), and the Typer CLI.
"""

from pathlib import Path

from typer.testing import CliRunner

from smartbackup import SmartBackup
from smartbackup.cli import app
from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine
from smartbackup.ui.logger import BackupLogger

runner = CliRunner()
DEVICE = "ValidationBox"


def _engine(source: Path, target: Path, *, log_to_file: bool = False) -> BackupEngine:
    config = BackupConfig(
        source_path=source,
        backup_path=target,
        backup_folder_name="TestBackup",
        log_to_file=log_to_file,
    )
    return BackupEngine(config, BackupLogger(verbose=False))


def _source(root: Path) -> Path:
    src = root / "source"
    src.mkdir()
    (src / "file1.txt").write_text("keep me")
    return src


class TestEngineValidationFailure:
    def test_missing_target_counts_as_error(self, source_dir: Path, tmp_path: Path):
        target = tmp_path / "missing-target"
        result = _engine(source_dir, target).run_backup()

        assert result.errors == 1
        assert result.copied_files == 0
        assert result.total_files == 0
        assert result.end_time is not None

    def test_missing_source_counts_as_error(self, tmp_path: Path, backup_dir: Path):
        result = _engine(tmp_path / "missing-source", backup_dir).run_backup()

        assert result.errors == 1
        assert result.copied_files == 0

    def test_unwritable_target_counts_as_error(
        self, source_dir: Path, backup_dir: Path, monkeypatch
    ):
        original_write_text = Path.write_text

        def deny_write(self, *args, **kwargs):
            if self.name == ".write_test":
                raise PermissionError("simulated read-only medium")
            return original_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", deny_write)
        result = _engine(source_dir, backup_dir).run_backup()

        assert result.errors == 1
        assert result.copied_files == 0

    def test_missing_target_is_not_recreated_by_logging(
        self, source_dir: Path, tmp_path: Path
    ):
        target = tmp_path / "missing-target"
        result = _engine(source_dir, target, log_to_file=True).run_backup()

        assert result.errors == 1
        assert not target.exists()

    def test_valid_paths_still_succeed(self, source_dir: Path, backup_dir: Path):
        result = _engine(source_dir, backup_dir).run_backup()

        assert result.errors == 0
        assert result.copied_files > 0
        assert (backup_dir / "TestBackup" / "file1.txt").read_text() == "Hello World"


class TestSmartBackupRunResult:
    def test_missing_target_returns_false_and_creates_nothing(self, tmp_path: Path):
        src = _source(tmp_path)
        target = tmp_path / "missing-target"

        success = SmartBackup().run(
            custom_source=src,
            custom_target=target,
            device_name=DEVICE,
        )

        assert success is False
        assert not target.exists()

    def test_valid_target_returns_true(self, tmp_path: Path):
        src = _source(tmp_path)
        target = tmp_path / "target"
        target.mkdir()

        success = SmartBackup().run(
            custom_source=src,
            custom_target=target,
            device_name=DEVICE,
        )

        assert success is True
        assert (target / "Documents-Backup" / DEVICE / "file1.txt").read_text() == "keep me"


class TestCliValidationFailure:
    def test_missing_target_exits_1(self, tmp_path: Path):
        src = _source(tmp_path)
        target = tmp_path / "missing-target"

        result = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(target),
                "--device-name",
                DEVICE,
            ],
        )

        assert result.exit_code == 1
        assert "Backup medium not found" in result.output
        assert "Backup completed with errors!" in result.output
        assert "Backup completed successfully!" not in result.output
        assert not target.exists()

    def test_valid_target_still_exits_0(self, tmp_path: Path):
        src = _source(tmp_path)
        target = tmp_path / "target"
        target.mkdir()

        result = runner.invoke(
            app,
            [
                "--source",
                str(src),
                "--target",
                str(target),
                "--device-name",
                DEVICE,
            ],
        )

        assert result.exit_code == 0
        assert "Backup completed successfully!" in result.output
        assert (target / "Documents-Backup" / DEVICE / "file1.txt").read_text() == "keep me"
