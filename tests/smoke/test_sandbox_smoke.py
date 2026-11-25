"""
Black-box sandbox smoke tests.

Spawns the real entry point (`python main.py ...`) as a subprocess inside a
fully isolated sandbox: temporary source, temporary target, and a redirected
configuration directory (APPDATA on Windows, HOME elsewhere).

Registered markers: `sandbox`, `smoke`. Run only this layer with:

    pytest -m sandbox
    pytest -m smoke
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINT = REPO_ROOT / "main.py"
BINARY_OVERRIDE = os.environ.get("SMARTBACKUP_BINARY")
DEVICE = "SmokeBox"
TIMEOUT_SECONDS = 120

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BINARY_OVERRIDE and not ENTRY_POINT.exists(),
        reason="main.py entry point not found and SMARTBACKUP_BINARY not set",
    ),
]


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI SGR/CSI color codes from captured CLI output."""
    return _ANSI_ESCAPE_RE.sub("", text)


def _sandbox_env(sandbox_root: Path) -> dict:
    """Environment with a redirected config directory and UTF-8 output."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    env.pop("FORCE_COLOR", None)
    env.pop("PY_COLORS", None)
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
    cmd = [BINARY_OVERRIDE, *args] if BINARY_OVERRIDE else [sys.executable, str(ENTRY_POINT), *args]
    return subprocess.run(
        cmd,
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


class TestCliSurfaceSmoke:
    def test_version_and_help_report_expected_values(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)

        version = _cli(["--version"], env)
        _assert_ok(version)
        assert "0.9.0" in version.stdout

        help_out = _cli(["--help"], env)
        _assert_ok(help_out)
        clean_help = _strip_ansi(help_out.stdout)
        assert "--dry-run" in clean_help
        assert "--select" in clean_help
        assert "--exclude" in clean_help
        assert "--manifest-format" in clean_help
        assert "--notify" in clean_help


class TestDryRunLifecycleSmoke:
    def test_dry_run_then_real_lifecycle(self, tmp_path: Path):
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

        _assert_ok(run("--dry-run"))
        assert not list(target.rglob(".smartbackup_manifest.json"))

        _assert_ok(run())
        _manifest(target)
        assert _backup_file(target).read_text() == "VERSION-1"

        (src / "file1.txt").write_text("VERSION-2-MODIFIED")
        manifest_before = _manifest(target).read_bytes()
        backup_before = _backup_file(target).read_text()

        _assert_ok(run("--dry-run"))
        assert _manifest(target).read_bytes() == manifest_before
        assert _backup_file(target).read_text() == backup_before

        _assert_ok(run())
        assert _backup_file(target).read_text() == "VERSION-2-MODIFIED"


class TestExcludePersistenceSmoke:
    def test_exclude_flag_persists_and_applies_across_invocations(self, tmp_path: Path):
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

        _assert_ok(run("--exclude", "*.iso"))
        backup_root = target / "Documents-Backup" / DEVICE
        assert not (backup_root / "image.iso").exists()
        assert (backup_root / "file1.txt").exists()

        config_file = _config_file(tmp_path)
        assert config_file.exists(), "sandbox config.json was not created"
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert "*.iso" in saved.get("exclusions", [])

        shutil.rmtree(target)
        target.mkdir()
        _assert_ok(run())
        assert not (backup_root / "image.iso").exists()
        assert (backup_root / "file1.txt").exists()


class TestValidationFailureSmoke:
    """F11: failed path validation must never look like a successful backup."""

    @pytest.mark.parametrize("extra", [[], ["--dry-run"]])
    def test_missing_target_exits_nonzero_and_creates_nothing(
        self, tmp_path: Path, extra: list
    ):
        env = _sandbox_env(tmp_path)
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.txt").write_text("keep me")
        target = tmp_path / "missing-target"

        proc = _cli(
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

        assert proc.returncode == 1, (
            f"expected exit 1, got {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
        assert "Backup medium not found" in proc.stdout
        assert "Backup completed with errors!" in proc.stdout
        assert "Backup completed successfully!" not in proc.stdout
        assert not target.exists(), "failed validation recreated the missing target"

    def test_valid_target_still_exits_zero(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.txt").write_text("keep me")
        target = tmp_path / "target"
        target.mkdir()

        proc = _cli(
            [
                "--source",
                str(src),
                "--target",
                str(target),
                "--device-name",
                DEVICE,
            ],
            env,
        )

        _assert_ok(proc)
        assert "Backup completed successfully!" in proc.stdout
        assert (target / "Documents-Backup" / DEVICE / "file1.txt").read_text() == "keep me"


class TestRestoreConflictSmoke:
    """F3: the --conflict flag works at the process boundary."""

    def test_conflict_rename_keeps_both_files(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        backup_folder = tmp_path / "backup" / "Documents-Backup"
        backup_folder.mkdir(parents=True)
        (backup_folder / "file1.txt").write_text("BACKUP CONTENT")

        target = tmp_path / "restored"
        target.mkdir()
        (target / "file1.txt").write_text("LOCAL CONTENT")

        proc = _cli(
            [
                "restore",
                "--source",
                str(tmp_path / "backup"),
                "--target",
                str(target),
                "--conflict",
                "rename",
            ],
            env,
        )

        _assert_ok(proc)
        assert (target / "file1.txt").read_text() == "LOCAL CONTENT"
        renamed = list(target.glob("file1.restored-*.txt"))
        assert len(renamed) == 1, f"expected one renamed copy, got {renamed}"
        assert renamed[0].read_text() == "BACKUP CONTENT"

    def test_unknown_conflict_value_exits_nonzero(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        backup_folder = tmp_path / "backup" / "Documents-Backup"
        backup_folder.mkdir(parents=True)
        (backup_folder / "file1.txt").write_text("BACKUP CONTENT")

        target = tmp_path / "restored"
        target.mkdir()

        proc = _cli(
            [
                "restore",
                "--source",
                str(tmp_path / "backup"),
                "--target",
                str(target),
                "--conflict",
                "bogus",
            ],
            env,
        )

        assert proc.returncode == 1, (
            f"expected exit 1, got {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
        assert "Invalid --conflict value" in proc.stdout


class TestConfigCliSmoke:
    """F4: the config group works at the process boundary with a sandbox HOME."""

    def test_set_get_unset_roundtrip(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        config_file = _config_file(tmp_path)

        _assert_ok(_cli(["config", "set", "auto_watch_cooldown", "42"], env))
        assert json.loads(config_file.read_text(encoding="utf-8"))["auto_watch_cooldown"] == 42

        got = _cli(["config", "get", "auto_watch_cooldown"], env)
        _assert_ok(got)
        assert "42" in got.stdout

        _assert_ok(_cli(["config", "unset", "auto_watch_cooldown"], env))
        assert "auto_watch_cooldown" not in json.loads(
            config_file.read_text(encoding="utf-8")
        )

    def test_invalid_value_exits_nonzero(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)

        proc = _cli(["config", "set", "auto_watch_cooldown", "nope"], env)

        assert proc.returncode == 1, (
            f"expected exit 1, got {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
        assert "Invalid value" in proc.stdout

    def test_exclude_and_unexclude_roundtrip(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        config_file = _config_file(tmp_path)

        _assert_ok(_cli(["config", "exclude", "*.iso"], env))
        assert "*.iso" in json.loads(config_file.read_text(encoding="utf-8"))["exclusions"]

        _assert_ok(_cli(["config", "unexclude", "*.iso"], env))
        assert "*.iso" not in json.loads(config_file.read_text(encoding="utf-8"))["exclusions"]


class TestSqliteManifestSmoke:
    """F10: SQLite manifest end-to-end at the process boundary."""

    def test_sqlite_backup_show_verify_and_restore(self, tmp_path: Path):
        env = _sandbox_env(tmp_path)
        src = tmp_path / "src"
        tgt = tmp_path / "tgt"
        restored = tmp_path / "restored"
        src.mkdir()
        tgt.mkdir()
        (src / "hello.txt").write_text("sqlite-backed")

        _assert_ok(
            _cli(
                [
                    "--source",
                    str(src),
                    "--target",
                    str(tgt),
                    "--device-name",
                    DEVICE,
                    "--manifest-format",
                    "sqlite",
                ],
                env,
            )
        )
        db = tgt / "Documents-Backup" / DEVICE / ".smartbackup_manifest.db"
        assert db.exists()
        assert not (tgt / "Documents-Backup" / DEVICE / ".smartbackup_manifest.json").exists()

        show = _cli(["--show-manifest", "--target", str(tgt), "--device-name", DEVICE], env)
        _assert_ok(show)
        assert "sqlite" in show.stdout.lower()

        _assert_ok(_cli(["--verify", "--target", str(tgt), "--device-name", DEVICE], env))

        _assert_ok(
            _cli(
                [
                    "restore",
                    "--source",
                    str(tgt),
                    "--target",
                    str(restored),
                    "--device-name",
                    DEVICE,
                ],
                env,
            )
        )
        assert (restored / "hello.txt").read_text() == "sqlite-backed"
