"""
Black-box sandbox smoke tests.

Spawns the real entry point (`python main.py ...`) as a subprocess inside a
fully isolated sandbox: temporary source, temporary target, and a redirected
configuration directory (APPDATA on Windows, HOME elsewhere) so the
developer's actual SmartBackup config is never read or written.

These tests guard the Phase-0 fixes at the process boundary - exit codes,
on-disk state, and the version string printed by `--version` - exactly as a
user would experience them.

Registered marker: `sandbox`. Run only this layer with:

    pytest -m sandbox
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINT = REPO_ROOT / "main.py"
DEVICE = "SmokeBox"
TIMEOUT_SECONDS = 120

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(not ENTRY_POINT.exists(), reason="main.py entry point not found"),
]


# --------------------------------------------------------------------------- #
# Sandbox helpers
# --------------------------------------------------------------------------- #
def _sandbox_env(sandbox_root: Path) -> dict:
    """Environment with a redirected config directory and UTF-8 output."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if platform.system() == "Windows":
        env["APPDATA"] = str(sandbox_root / "appdata")
    else:
        env["HOME"] = str(sandbox_root / "home")
    return env


def _config_file(sandbox_root: Path) -> Path:
    if platform.system() == "Windows":
        return sandbox_root / "appdata" / "SmartBackup" / "config.json"
    return sandbox_root / "home" / ".config" / "smartbackup" / "config.json"


def _cli(args: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ENTRY_POINT), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
    )


def _assert_ok(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, (
        f"CLI exited with {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )


def _manifest(target: Path) -> Path:
    hits = list(target.rglob(".smartbackup_manifest.json"))
    assert hits, f"no manifest found under {target}"
    return hits[0]


def _backup_file(target: Path) -> Path:
    return target / "Documents-Backup" / DEVICE / "file1.txt"


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class TestCliSurfaceSmoke:
    def test_version_and_help_report_expected_values(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)

        version = _cli(["--version"], env)
        _assert_ok(version)
        assert "0.6.1" in version.stdout

        help_out = _cli(["--help"], env)
        _assert_ok(help_out)
        assert "--dry-run" in help_out.stdout
        assert "--exclude" in help_out.stdout


class TestDryRunLifecycleSmoke:
    def test_dry_run_then_real_lifecycle(self, tmp_path: Path):
        """The full Phase-0 F1 contract, black-box at the process boundary."""
        env = _sandbox_env(tmp_path)
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.txt").write_text("VERSION-1")
        target = tmp_path / "target"
        target.mkdir()

        def run(*extra: str) -> subprocess.CompletedProcess:
            return _cli(
                [
                    "--source",
                    str(src),
                    "--target",
                    str(target),
                    "--device-name",
                    DEVICE,
                    *extra,
                ],
                env,
            )

        # 1. Dry-run against a fresh target must not write a manifest
        _assert_ok(run("--dry-run"))
        assert not list(target.rglob(".smartbackup_manifest.json"))

        # 2. The real run after it copies everything
        _assert_ok(run())
        _manifest(target)
        assert _backup_file(target).read_text() == "VERSION-1"

        # 3. Modify the source: a dry-run must not advance the manifest
        (src / "file1.txt").write_text("VERSION-2-MODIFIED")
        manifest_before = _manifest(target).read_bytes()
        backup_before = _backup_file(target).read_text()

        _assert_ok(run("--dry-run"))
        assert _manifest(target).read_bytes() == manifest_before
        assert _backup_file(target).read_text() == backup_before

        # 4. The next real run picks the change up
        _assert_ok(run())
        assert _backup_file(target).read_text() == "VERSION-2-MODIFIED"


class TestExcludePersistenceSmoke:
    def test_exclude_flag_persists_and_applies_across_invocations(self, tmp_path: Path):
        """The full Phase-0 F2 contract: persist, apply now, apply later."""
        env = _sandbox_env(tmp_path)
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.txt").write_text("keep me")
        (src / "image.iso").write_bytes(b"iso-bytes")
        target = tmp_path / "target"
        target.mkdir()

        def run(*extra: str) -> subprocess.CompletedProcess:
            return _cli(
                [
                    "--source",
                    str(src),
                    "--target",
                    str(target),
                    "--device-name",
                    DEVICE,
                    *extra,
                ],
                env,
            )

        # 1. With the flag: applied to this run and persisted to the sandbox config
        _assert_ok(run("--exclude", "*.iso"))
        backup_root = target / "Documents-Backup" / DEVICE
        assert not (backup_root / "image.iso").exists()
        assert (backup_root / "file1.txt").exists()

        config_file = _config_file(tmp_path)
        assert config_file.exists(), "sandbox config.json was not created"
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

        # 2. Fresh medium, no flag: the stored pattern still applies
        shutil.rmtree(target)
        target.mkdir()
        _assert_ok(run())
        assert not (backup_root / "image.iso").exists()
        assert (backup_root / "file1.txt").exists()
