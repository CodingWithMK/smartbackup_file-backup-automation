"""
Shared test fixtures for SmartBackup tests.
"""

import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def source_dir(temp_dir: Path) -> Path:
    """Create a source directory with test files."""
    source = temp_dir / "source"
    source.mkdir()

    # Create some test files
    (source / "file1.txt").write_text("Hello World")
    (source / "file2.py").write_text("print('test')")

    # Create subdirectory
    subdir = source / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("Nested file")

    return source


@pytest.fixture
def backup_dir(temp_dir: Path) -> Path:
    """Create a backup directory for testing."""
    backup = temp_dir / "backup"
    backup.mkdir()
    return backup


@pytest.fixture
def source_with_exclusions(source_dir: Path) -> Path:
    """Create a source directory with files that should be excluded."""
    # Create node_modules
    node_modules = source_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.json").write_text("{}")

    # Create __pycache__
    pycache = source_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-39.pyc").write_bytes(b"compiled")

    # Create .git
    git_dir = source_dir / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")

    # Create venv with pyvenv.cfg
    venv = source_dir / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin")

    return source_dir


@pytest.fixture
def mock_external_drive(temp_dir: Path) -> Path:
    """Create a mock external drive directory."""
    drive = temp_dir / "mock_drive"
    drive.mkdir()
    return drive
