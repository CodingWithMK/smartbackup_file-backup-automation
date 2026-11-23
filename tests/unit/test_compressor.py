"""
Unit tests for core.compressor.BackupCompressor.
"""

import tarfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from smartbackup.core.compressor import SUPPORTED_FORMATS, BackupCompressor
from smartbackup.ui.logger import BackupLogger


@pytest.fixture
def logger() -> BackupLogger:
    """Create a quiet logger for testing."""
    return BackupLogger(verbose=False)


@pytest.fixture
def compressor(logger: BackupLogger) -> BackupCompressor:
    """Create a BackupCompressor instance."""
    return BackupCompressor(logger)


@pytest.fixture
def sample_backup_dir(tmp_path: Path) -> Path:
    """Create a sample backup directory with files to compress."""
    backup = tmp_path / "sample_backup"
    backup.mkdir()

    (backup / "file1.txt").write_text("Hello World")
    (backup / "file2.py").write_text("print('test')")

    subdir = backup / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested file content")

    deep = subdir / "deep"
    deep.mkdir()
    (deep / "deep_file.txt").write_text("Deep nested content")

    return backup


class TestBackupCompressorValidation:
    """Tests for format validation and error handling."""

    def test_compress_raises_on_invalid_format(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """Passing an unsupported format string raises ValueError."""
        output = tmp_path / "output.rar"
        with pytest.raises(ValueError, match="Unsupported compression format"):
            compressor.compress(sample_backup_dir, output, "rar")

    def test_compress_raises_on_nonexistent_source(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        """Compressing a non-existent source raises FileNotFoundError."""
        source = tmp_path / "nonexistent"
        output = tmp_path / "output.zip"
        with pytest.raises(FileNotFoundError):
            compressor.compress(source, output, "zip")

    def test_compress_raises_on_file_as_source(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        """Compressing a file (not directory) raises NotADirectoryError."""
        source = tmp_path / "a_file.txt"
        source.write_text("I am a file")
        output = tmp_path / "output.zip"
        with pytest.raises(NotADirectoryError):
            compressor.compress(source, output, "zip")

    def test_supported_formats_constant(self):
        """SUPPORTED_FORMATS should contain zip and tar.gz."""
        assert "zip" in SUPPORTED_FORMATS
        assert "tar.gz" in SUPPORTED_FORMATS


class TestZipCompression:
    """Tests for ZIP format compression."""

    def test_compress_zip_creates_archive(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """Compress to .zip creates a valid zip file."""
        output = tmp_path / "backup.zip"
        result = compressor.compress(sample_backup_dir, output, "zip")

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
        assert zipfile.is_zipfile(output)

    def test_compress_zip_contains_all_files(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """The zip archive contains every file from the source directory."""
        output = tmp_path / "backup.zip"
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
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """Subdirectories are preserved inside the archive."""
        output = tmp_path / "backup.zip"
        compressor.compress(sample_backup_dir, output, "zip")

        with zipfile.ZipFile(output, "r") as zf:
            assert any("subdir/" in n for n in zf.namelist())

    def test_compress_zip_content_matches(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """File contents inside the archive match the originals."""
        output = tmp_path / "backup.zip"
        compressor.compress(sample_backup_dir, output, "zip")

        with zipfile.ZipFile(output, "r") as zf:
            assert zf.read("file1.txt").decode() == "Hello World"
            assert zf.read("file2.py").decode() == "print('test')"


class TestTarGzCompression:
    """Tests for TAR.GZ format compression."""

    def test_compress_tar_gz_creates_archive(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """Compress to .tar.gz creates a valid tar.gz file."""
        output = tmp_path / "backup.tar.gz"
        result = compressor.compress(sample_backup_dir, output, "tar.gz")

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0
        with tarfile.open(output, "r:gz") as tf:
            assert len(tf.getmembers()) > 0

    def test_compress_tar_gz_contains_all_files(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """The tar.gz archive contains every file from the source directory."""
        output = tmp_path / "backup.tar.gz"
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
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """Subdirectories are preserved inside the archive."""
        output = tmp_path / "backup.tar.gz"
        compressor.compress(sample_backup_dir, output, "tar.gz")

        with tarfile.open(output, "r:gz") as tf:
            assert any("subdir" in n for n in tf.getnames())

    def test_compress_tar_gz_content_matches(
        self, compressor: BackupCompressor, sample_backup_dir: Path, tmp_path: Path
    ):
        """File contents inside the archive match the originals."""
        output = tmp_path / "backup.tar.gz"
        compressor.compress(sample_backup_dir, output, "tar.gz")

        with tarfile.open(output, "r:gz") as tf:
            f1 = tf.extractfile("file1.txt")
            assert f1 is not None
            assert f1.read().decode() == "Hello World"

            f2 = tf.extractfile("file2.py")
            assert f2 is not None
            assert f2.read().decode() == "print('test')"


class TestArchiveNaming:
    """Tests for archive name generation."""

    def test_get_archive_name_zip_format(self):
        name = BackupCompressor.get_archive_name("MyDevice", "zip")
        assert name.startswith("MyDevice_")
        assert name.endswith(".zip")

    def test_get_archive_name_tar_gz_format(self):
        name = BackupCompressor.get_archive_name("MyDevice", "tar.gz")
        assert name.startswith("MyDevice_")
        assert name.endswith(".tar.gz")

    def test_get_archive_name_includes_device_name(self):
        name = BackupCompressor.get_archive_name("WorkLaptop", "zip")
        assert "WorkLaptop" in name

    def test_get_archive_name_includes_timestamp(self):
        name = BackupCompressor.get_archive_name("Dev", "zip")
        parts = name.replace(".zip", "").split("_")
        assert len(parts) == 3
        assert parts[1].isdigit()
        assert parts[2].isdigit()


class TestAlreadyCompressed:
    """Tests for already-compressed detection."""

    def test_is_already_compressed_false_for_empty(self, tmp_path: Path):
        root = tmp_path / "empty_root"
        root.mkdir()
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_is_already_compressed_false_for_nonexistent(self, tmp_path: Path):
        root = tmp_path / "nonexistent"
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_is_already_compressed_true_when_zip_exists(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "TestDevice_20260228_120000.zip").write_bytes(b"fake zip")
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is True

    def test_is_already_compressed_true_when_tar_gz_exists(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "TestDevice_20260228_120000.tar.gz").write_bytes(b"fake tar")
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is True

    def test_is_already_compressed_false_for_different_device(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "OtherDevice_20260228_120000.zip").write_bytes(b"fake zip")
        assert BackupCompressor.is_already_compressed(root, "TestDevice") is False

    def test_find_archives_returns_matching(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "Dev_20260228_120000.zip").write_bytes(b"zip1")
        (root / "Dev_20260228_130000.tar.gz").write_bytes(b"tar1")
        (root / "Other_20260228_120000.zip").write_bytes(b"other")

        archives = BackupCompressor.find_archives(root, "Dev")
        names = [a.name for a in archives]
        assert "Dev_20260228_120000.zip" in names
        assert "Dev_20260228_130000.tar.gz" in names
        assert "Other_20260228_120000.zip" not in names

    def test_find_archives_empty_when_none(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        assert BackupCompressor.find_archives(root, "Dev") == []


class TestCompressionEdgeCases:
    """Tests for edge cases in compression."""

    def test_compress_empty_directory_zip(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output = tmp_path / "empty.zip"

        result = compressor.compress(empty_dir, output, "zip")
        assert result.exists()
        assert zipfile.is_zipfile(result)

    def test_compress_empty_directory_tar_gz(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output = tmp_path / "empty.tar.gz"

        result = compressor.compress(empty_dir, output, "tar.gz")
        assert result.exists()
        with tarfile.open(result, "r:gz") as tf:
            assert len([m for m in tf.getmembers() if m.isfile()]) == 0

    def test_compress_large_file(self, compressor: BackupCompressor, tmp_path: Path):
        source = tmp_path / "large_source"
        source.mkdir()
        large_file = source / "large.bin"
        large_file.write_bytes(b"A" * (1024 * 1024 + 512 * 1024))

        output = tmp_path / "large.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()
        assert result.stat().st_size < large_file.stat().st_size

    def test_compress_nested_directories(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        source = tmp_path / "nested_source"
        current = source
        for i in range(10):
            current = current / f"level{i}"
        current.mkdir(parents=True)
        (current / "deep.txt").write_text("very deep")

        output = tmp_path / "nested.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()

        with zipfile.ZipFile(result, "r") as zf:
            deep_files = [n for n in zf.namelist() if "deep.txt" in n]
            assert len(deep_files) == 1

    def test_compress_special_characters_in_filenames(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        source = tmp_path / "special_source"
        source.mkdir()
        (source / "file with spaces.txt").write_text("spaces")
        (source / "file-with-dashes.txt").write_text("dashes")

        output = tmp_path / "special.zip"
        result = compressor.compress(source, output, "zip")
        assert result.exists()

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "file with spaces.txt" in names
            assert "file-with-dashes.txt" in names

    def test_compress_atomic_no_partial_on_failure(
        self, compressor: BackupCompressor, tmp_path: Path
    ):
        source = tmp_path / "fail_source"
        source.mkdir()
        (source / "file.txt").write_text("test")

        output = tmp_path / "should_not_exist.zip"

        with patch("smartbackup.core.compressor.zipfile.ZipFile") as mock_zip:
            mock_zip.return_value.__enter__ = lambda s: s
            mock_zip.return_value.__exit__ = lambda s, *a: False
            mock_zip.return_value.write.side_effect = OSError("Disk full")
            mock_zip.return_value.writestr.side_effect = OSError("Disk full")

            with pytest.raises(OSError, match="Disk full"):
                compressor.compress(source, output, "zip")

        assert not output.exists()
