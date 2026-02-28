"""
Tests for the compressor module.
"""

import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from smartbackup.core.compressor import SUPPORTED_FORMATS, BackupCompressor
from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine
from smartbackup.ui.logger import BackupLogger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def logger() -> BackupLogger:
    """Create a quiet logger for testing."""
    return BackupLogger(verbose=False)


@pytest.fixture
def compressor(logger: BackupLogger) -> BackupCompressor:
    """Create a BackupCompressor instance."""
    return BackupCompressor(logger)


@pytest.fixture
def sample_backup_dir(temp_dir: Path) -> Path:
    """Create a sample backup directory with files to compress."""
    backup = temp_dir / "sample_backup"
    backup.mkdir()

    # Create some files
    (backup / "file1.txt").write_text("Hello World")
    (backup / "file2.py").write_text("print('test')")

    # Create a subdirectory with files
    subdir = backup / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested file content")

    # Create a deeper nested structure
    deep = subdir / "deep"
    deep.mkdir()
    (deep / "deep_file.txt").write_text("Deep nested content")

    return backup


@pytest.fixture
def sample_backup_root(temp_dir: Path) -> Path:
    """Create a Documents-Backup/ root with a device subfolder."""
    root = temp_dir / "Documents-Backup"
    root.mkdir()

    device = root / "TestDevice"
    device.mkdir()
    (device / "file1.txt").write_text("Hello")
    (device / "file2.txt").write_text("World")

    return root


# ---------------------------------------------------------------------------
# TestBackupCompressor - Format validation
# ---------------------------------------------------------------------------


class TestBackupCompressorValidation:
    """Tests for format validation and error handling."""

    def test_compress_raises_on_invalid_format(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """Passing an unsupported format string raises ValueError."""
        output = temp_dir / "output.rar"
        with pytest.raises(ValueError, match="Unsupported compression format"):
            compressor.compress(sample_backup_dir, output, "rar")

    def test_compress_raises_on_nonexistent_source(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Compressing a non-existent source raises FileNotFoundError."""
        source = temp_dir / "nonexistent"
        output = temp_dir / "output.zip"
        with pytest.raises(FileNotFoundError):
            compressor.compress(source, output, "zip")

    def test_compress_raises_on_file_as_source(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Compressing a file (not directory) raises NotADirectoryError."""
        source = temp_dir / "a_file.txt"
        source.write_text("I am a file")
        output = temp_dir / "output.zip"
        with pytest.raises(NotADirectoryError):
            compressor.compress(source, output, "zip")

    def test_supported_formats_constant(self):
        """SUPPORTED_FORMATS should contain zip and tar.gz."""
        assert "zip" in SUPPORTED_FORMATS
        assert "tar.gz" in SUPPORTED_FORMATS


# ---------------------------------------------------------------------------
# TestBackupCompressor - ZIP compression
# ---------------------------------------------------------------------------


class TestZipCompression:
    """Tests for ZIP format compression."""

    def test_compress_zip_creates_archive(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """Compress to .zip creates a valid zip file."""
        output = temp_dir / "backup.zip"
        result = compressor.compress(sample_backup_dir, output, "zip")

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
        assert zipfile.is_zipfile(output)

    def test_compress_zip_contains_all_files(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """The zip archive contains every file from the source directory."""
        output = temp_dir / "backup.zip"
        compressor.compress(sample_backup_dir, output, "zip")

        with zipfile.ZipFile(output, "r") as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            assert "file1.txt" in names
            assert "file2.py" in names
            assert str(Path("subdir/nested.txt")) in names or "subdir/nested.txt" in names
            assert (
                str(Path("subdir/deep/deep_file.txt")) in names
                or "subdir/deep/deep_file.txt" in names
            )

    def test_compress_zip_preserves_directory_structure(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """Subdirectories are preserved inside the archive."""
        output = temp_dir / "backup.zip"
        compressor.compress(sample_backup_dir, output, "zip")

        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            # Check for directory entries or files within subdirectories
            has_subdir = any("subdir/" in n for n in names)
            assert has_subdir

    def test_compress_zip_content_matches(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """File contents inside the archive match the originals."""
        output = temp_dir / "backup.zip"
        compressor.compress(sample_backup_dir, output, "zip")

        with zipfile.ZipFile(output, "r") as zf:
            assert zf.read("file1.txt").decode() == "Hello World"
            assert zf.read("file2.py").decode() == "print('test')"


# ---------------------------------------------------------------------------
# TestBackupCompressor - TAR.GZ compression
# ---------------------------------------------------------------------------


class TestTarGzCompression:
    """Tests for TAR.GZ format compression."""

    def test_compress_tar_gz_creates_archive(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """Compress to .tar.gz creates a valid tar.gz file."""
        output = temp_dir / "backup.tar.gz"
        result = compressor.compress(sample_backup_dir, output, "tar.gz")

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
        # Validate it's a valid tar.gz
        with tarfile.open(output, "r:gz") as tf:
            assert len(tf.getmembers()) > 0

    def test_compress_tar_gz_contains_all_files(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """The tar.gz archive contains every file from the source directory."""
        output = temp_dir / "backup.tar.gz"
        compressor.compress(sample_backup_dir, output, "tar.gz")

        with tarfile.open(output, "r:gz") as tf:
            names = tf.getnames()
            file_names = [n for n in names if not tf.getmember(n).isdir()]
            assert "file1.txt" in file_names
            assert "file2.py" in file_names
            assert (
                str(Path("subdir/nested.txt")) in file_names
                or "subdir/nested.txt" in file_names
            )

    def test_compress_tar_gz_preserves_directory_structure(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """Subdirectories are preserved inside the archive."""
        output = temp_dir / "backup.tar.gz"
        compressor.compress(sample_backup_dir, output, "tar.gz")

        with tarfile.open(output, "r:gz") as tf:
            names = tf.getnames()
            has_subdir = any("subdir" in n for n in names)
            assert has_subdir

    def test_compress_tar_gz_content_matches(
        self, compressor: BackupCompressor, sample_backup_dir: Path, temp_dir: Path
    ):
        """File contents inside the archive match the originals."""
        output = temp_dir / "backup.tar.gz"
        compressor.compress(sample_backup_dir, output, "tar.gz")

        with tarfile.open(output, "r:gz") as tf:
            f1 = tf.extractfile("file1.txt")
            assert f1 is not None
            assert f1.read().decode() == "Hello World"

            f2 = tf.extractfile("file2.py")
            assert f2 is not None
            assert f2.read().decode() == "print('test')"


# ---------------------------------------------------------------------------
# TestBackupCompressor - Archive naming
# ---------------------------------------------------------------------------


class TestArchiveNaming:
    """Tests for archive name generation."""

    def test_get_archive_name_zip_format(self):
        """Returns correct filename pattern for zip."""
        name = BackupCompressor.get_archive_name("MyDevice", "zip")
        assert name.startswith("MyDevice_")
        assert name.endswith(".zip")

    def test_get_archive_name_tar_gz_format(self):
        """Returns correct filename pattern for tar.gz."""
        name = BackupCompressor.get_archive_name("MyDevice", "tar.gz")
        assert name.startswith("MyDevice_")
        assert name.endswith(".tar.gz")

    def test_get_archive_name_includes_device_name(self):
        """Device name appears in the archive filename."""
        name = BackupCompressor.get_archive_name("WorkLaptop", "zip")
        assert "WorkLaptop" in name

    def test_get_archive_name_includes_timestamp(self):
        """Archive name includes a timestamp component."""
        name = BackupCompressor.get_archive_name("Dev", "zip")
        # Format: Dev_YYYYMMDD_HHMMSS.zip - should have underscores and digits
        parts = name.replace(".zip", "").split("_")
        assert len(parts) == 3  # Dev, YYYYMMDD, HHMMSS
        assert parts[1].isdigit()
        assert parts[2].isdigit()


# ---------------------------------------------------------------------------
# TestBackupCompressor - Already compressed detection
# ---------------------------------------------------------------------------


class TestAlreadyCompressed:
    """Tests for already-compressed detection."""

    def test_is_already_compressed_false_for_empty(self, temp_dir: Path):
        """Returns False when no archives exist."""
        root = temp_dir / "empty_root"
        root.mkdir()
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_is_already_compressed_false_for_nonexistent(self, temp_dir: Path):
        """Returns False when root doesn't exist."""
        root = temp_dir / "nonexistent"
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_is_already_compressed_true_when_zip_exists(self, temp_dir: Path):
        """Returns True when a matching .zip archive exists."""
        root = temp_dir / "root"
        root.mkdir()
        (root / "TestDevice_20260228_120000.zip").write_bytes(b"fake zip")

        assert BackupCompressor.is_already_compressed(root, "TestDevice") is True

    def test_is_already_compressed_true_when_tar_gz_exists(self, temp_dir: Path):
        """Returns True when a matching .tar.gz archive exists."""
        root = temp_dir / "root"
        root.mkdir()
        (root / "TestDevice_20260228_120000.tar.gz").write_bytes(b"fake tar")

        assert BackupCompressor.is_already_compressed(root, "TestDevice") is True

    def test_is_already_compressed_false_for_different_device(self, temp_dir: Path):
        """Returns False when archive is for a different device."""
        root = temp_dir / "root"
        root.mkdir()
        (root / "OtherDevice_20260228_120000.zip").write_bytes(b"fake zip")

        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_find_archives_returns_matching(self, temp_dir: Path):
        """find_archives returns all matching archive files."""
        root = temp_dir / "root"
        root.mkdir()
        (root / "Dev_20260228_120000.zip").write_bytes(b"zip1")
        (root / "Dev_20260228_130000.tar.gz").write_bytes(b"tar1")
        (root / "Other_20260228_120000.zip").write_bytes(b"other")

        archives = BackupCompressor.find_archives(root, "Dev")
        names = [a.name for a in archives]
        assert "Dev_20260228_120000.zip" in names
        assert "Dev_20260228_130000.tar.gz" in names
        assert "Other_20260228_120000.zip" not in names

    def test_find_archives_empty_when_none(self, temp_dir: Path):
        """find_archives returns empty list when no archives match."""
        root = temp_dir / "root"
        root.mkdir()
        assert BackupCompressor.find_archives(root, "Dev") == []


# ---------------------------------------------------------------------------
# TestBackupCompressor - Edge cases
# ---------------------------------------------------------------------------


class TestCompressionEdgeCases:
    """Tests for edge cases in compression."""

    def test_compress_empty_directory_zip(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Compressing an empty directory produces a valid zip archive."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        output = temp_dir / "empty.zip"

        result = compressor.compress(empty_dir, output, "zip")
        assert result.exists()
        assert zipfile.is_zipfile(result)

    def test_compress_empty_directory_tar_gz(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Compressing an empty directory produces a valid tar.gz archive."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        output = temp_dir / "empty.tar.gz"

        result = compressor.compress(empty_dir, output, "tar.gz")
        assert result.exists()
        with tarfile.open(result, "r:gz") as tf:
            # Empty dir should have zero or very few members
            assert len([m for m in tf.getmembers() if m.isfile()]) == 0

    def test_compress_large_file(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """A single large file (>1MB) compresses successfully."""
        source = temp_dir / "large_source"
        source.mkdir()
        large_file = source / "large.bin"
        # Write 1.5 MB of data
        large_file.write_bytes(b"A" * (1024 * 1024 + 512 * 1024))

        output = temp_dir / "large.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()
        # Compressed size should be smaller for repetitive data
        assert result.stat().st_size < large_file.stat().st_size

    def test_compress_nested_directories(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Deeply nested directory structures are handled correctly."""
        source = temp_dir / "nested_source"
        current = source
        for i in range(10):
            current = current / f"level{i}"
        current.mkdir(parents=True)
        (current / "deep.txt").write_text("very deep")

        output = temp_dir / "nested.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            deep_files = [n for n in names if "deep.txt" in n]
            assert len(deep_files) == 1

    def test_compress_special_characters_in_filenames(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """Files with spaces in names compress correctly."""
        source = temp_dir / "special_source"
        source.mkdir()
        (source / "file with spaces.txt").write_text("spaces")
        (source / "file-with-dashes.txt").write_text("dashes")

        output = temp_dir / "special.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "file with spaces.txt" in names
            assert "file-with-dashes.txt" in names

    def test_compress_atomic_no_partial_on_failure(
        self, compressor: BackupCompressor, temp_dir: Path
    ):
        """If compression fails midway, no partial archive file is left behind."""
        source = temp_dir / "fail_source"
        source.mkdir()
        (source / "file.txt").write_text("test")

        output = temp_dir / "should_not_exist.zip"

        # Patch zipfile.ZipFile to raise an error during write
        with patch("smartbackup.core.compressor.zipfile.ZipFile") as mock_zip:
            mock_zip.return_value.__enter__ = lambda s: s
            mock_zip.return_value.__exit__ = lambda s, *a: False
            mock_zip.return_value.write.side_effect = OSError("Disk full")
            mock_zip.return_value.writestr.side_effect = OSError("Disk full")

            with pytest.raises(OSError, match="Disk full"):
                compressor.compress(source, output, "zip")

        # The output file should NOT exist (atomic cleanup)
        assert not output.exists()


# ---------------------------------------------------------------------------
# TestCompressionIntegration - Engine integration
# ---------------------------------------------------------------------------


class TestCompressionIntegration:
    """Tests for compression integrated with BackupEngine."""

    def test_backup_without_compress_flag_no_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        """Running backup without compress_format produces no archive."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            log_to_file=False,
            compress_format=None,
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)
        engine.run_backup()

        # No archive files should exist
        backup_root = backup_dir / "TestBackup"
        zip_files = list(backup_root.glob("*.zip"))
        tar_files = list(backup_root.glob("*.tar.gz"))
        assert len(zip_files) == 0
        assert len(tar_files) == 0

    def test_backup_with_compress_zip_creates_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        """Running backup with compress_format='zip' produces a zip archive."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="zip",
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)
        result = engine.run_backup()

        assert result.errors == 0

        # Archive should exist in the backup root
        backup_root = backup_dir / "TestBackup"
        zip_files = list(backup_root.glob("TestDevice_*.zip"))
        assert len(zip_files) == 1
        assert zipfile.is_zipfile(zip_files[0])

    def test_backup_with_compress_tar_gz_creates_archive(
        self, source_dir: Path, backup_dir: Path
    ):
        """Running backup with compress_format='tar.gz' produces a tar.gz archive."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="tar.gz",
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)
        result = engine.run_backup()

        assert result.errors == 0

        # Archive should exist in the backup root
        backup_root = backup_dir / "TestBackup"
        tar_files = list(backup_root.glob("TestDevice_*.tar.gz"))
        assert len(tar_files) == 1
        with tarfile.open(tar_files[0], "r:gz") as tf:
            assert len(tf.getmembers()) > 0

    def test_backup_compress_archive_contains_backed_up_files(
        self, source_dir: Path, backup_dir: Path
    ):
        """Compressed archive from backup contains the expected files."""
        config = BackupConfig(
            source_path=source_dir,
            backup_path=backup_dir,
            backup_folder_name="TestBackup",
            device_name="TestDevice",
            log_to_file=False,
            compress_format="zip",
        )
        logger = BackupLogger(verbose=False)
        engine = BackupEngine(config, logger)
        engine.run_backup()

        backup_root = backup_dir / "TestBackup"
        zip_files = list(backup_root.glob("TestDevice_*.zip"))
        assert len(zip_files) == 1

        with zipfile.ZipFile(zip_files[0], "r") as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            assert "file1.txt" in names
            assert "file2.py" in names


# ---------------------------------------------------------------------------
# TestCompressCLI - CLI subcommand
# ---------------------------------------------------------------------------


class TestCompressCLI:
    """Tests for the compress CLI subcommand."""

    def test_compress_subcommand_exists(self):
        """The 'compress' subcommand is registered in the Typer app."""
        from smartbackup.cli import app

        # Typer registers commands as info objects
        command_names = []
        if hasattr(app, "registered_commands"):
            for cmd in app.registered_commands:
                if hasattr(cmd, "name") and cmd.name:
                    command_names.append(cmd.name)

        # Also check the click group directly
        import click

        try:
            click_app = typer.main.get_command(app)
            if hasattr(click_app, "commands"):
                command_names.extend(click_app.commands.keys())
        except Exception:
            pass

        assert "compress" in command_names, (
            f"'compress' not found in registered commands: {command_names}"
        )

    def test_compress_subcommand_help(self):
        """The compress subcommand has appropriate help text."""
        import typer.main

        from smartbackup.cli import app

        click_app = typer.main.get_command(app)
        compress_cmd = click_app.commands.get("compress")
        assert compress_cmd is not None
        assert "compress" in compress_cmd.help.lower() or "archive" in compress_cmd.help.lower()
