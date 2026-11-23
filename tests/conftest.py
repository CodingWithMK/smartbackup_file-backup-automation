"""
Shared test fixtures and automatic layer marking for SmartBackup tests.
"""

from pathlib import Path

import pytest

from smartbackup.config import ConfigManager

_LAYER_MARKERS = {
    "unit": pytest.mark.unit,
    "integration": pytest.mark.integration,
    "e2e": pytest.mark.e2e,
    "smoke": pytest.mark.smoke,
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply unit/integration/e2e/smoke markers based on test directory."""
    tests_root = Path(__file__).parent
    for item in items:
        try:
            rel_parts = Path(item.fspath).relative_to(tests_root).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in _LAYER_MARKERS:
            item.add_marker(_LAYER_MARKERS[rel_parts[0]])


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ConfigManager into tmp_path so no test touches real user config."""
    config_dir = tmp_path / "cfg"
    monkeypatch.setattr(ConfigManager, "_get_config_dir", lambda self: config_dir)
    return config_dir


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for testing (alias for pytest's tmp_path)."""
    return tmp_path


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory with test files."""
    source = tmp_path / "source"
    source.mkdir()

    (source / "file1.txt").write_text("Hello World")
    (source / "file2.py").write_text("print('test')")

    subdir = source / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("Nested file")

    return source


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """Create a backup directory for testing."""
    backup = tmp_path / "backup"
    backup.mkdir()
    return backup


@pytest.fixture
def source_with_exclusions(source_dir: Path) -> Path:
    """Create a source directory with files that should be excluded."""
    node_modules = source_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.json").write_text("{}")

    pycache = source_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-39.pyc").write_bytes(b"compiled")

    git_dir = source_dir / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")

    venv = source_dir / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin")

    return source_dir


@pytest.fixture
def mock_external_drive(tmp_path: Path) -> Path:
    """Create a mock external drive directory."""
    drive = tmp_path / "mock_drive"
    drive.mkdir()
    return drive
