"""
Unit tests for standalone-binary runtime helpers, frozen-mode command generation,
Windows UTF-8 console reconfiguration, installer scripts, and release workflows.
"""

import io
import platform
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from smartbackup.platform.runtime import (
    build_cli_command,
    ensure_utf8_console,
    is_frozen_binary,
)
from smartbackup.platform.scheduler import SchedulerHelper
from smartbackup.platform.terminal import TerminalSpawner

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestRuntimeHelpers:
    """Tests for frozen-binary detection, CLI argv construction, and UTF-8 console."""

    def test_is_frozen_binary_default_false(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert is_frozen_binary() is False

    def test_is_frozen_binary_true_when_frozen(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert is_frozen_binary() is True

    def test_build_cli_command_under_python_interpreter(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delattr(sys, "frozen", raising=False)
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")

        assert build_cli_command("watch") == ["/usr/bin/python3", "-m", "smartbackup", "watch"]
        assert build_cli_command() == ["/usr/bin/python3", "-m", "smartbackup"]

    def test_build_cli_command_under_frozen_binary(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/home/user/.local/bin/smartbackup")

        assert build_cli_command("watch") == ["/home/user/.local/bin/smartbackup", "watch"]
        assert build_cli_command() == ["/home/user/.local/bin/smartbackup"]

    def test_build_cli_command_explicit_python_exe_overrides_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert build_cli_command("watch", python_exe="python3") == [
            "python3",
            "-m",
            "smartbackup",
            "watch",
        ]

    def test_ensure_utf8_console_reconfigures_non_utf8_streams(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeStream:
            encoding = "cp1252"

            def __init__(self) -> None:
                self.reconfigured: list[tuple[str, str]] = []

            def reconfigure(self, *, encoding: str, errors: str) -> None:
                self.reconfigured.append((encoding, errors))

        fake_out = FakeStream()
        fake_err = FakeStream()
        monkeypatch.setattr(sys, "stdout", fake_out)
        monkeypatch.setattr(sys, "stderr", fake_err)

        ensure_utf8_console()

        assert fake_out.reconfigured == [("utf-8", "replace")]
        assert fake_err.reconfigured == [("utf-8", "replace")]

    def test_ensure_utf8_console_noop_on_utf8_or_stringio(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.setattr(sys, "stderr", io.StringIO())
        ensure_utf8_console()  # Must not raise


class TestFrozenBinaryIntegration:
    """Ensure TerminalSpawner and SchedulerHelper omit `-m smartbackup` when frozen."""

    def test_terminal_spawner_frozen_windows_omits_dash_m(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\Apps\smartbackup.exe")
        spawner = TerminalSpawner()

        with (
            patch("platform.system", return_value="Windows"),
            patch.object(spawner, "is_headless", return_value=False),
            patch("shutil.which", side_effect=lambda x: r"C:\Windows\wt.exe" if "wt" in x else None),
            patch("subprocess.Popen") as mock_popen,
        ):
            assert spawner.spawn_prompt(Path("E:/")) is True
            cmd = mock_popen.call_args[0][0]
            assert r"C:\Apps\smartbackup.exe" in cmd
            assert "-m" not in cmd
            assert "--prompt" in cmd

    def test_scheduler_daemon_install_frozen_linux_omits_dash_m(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/home/alice/.local/bin/smartbackup")
        fake_service = tmp_path / "smartbackup-watcher.service"
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(SchedulerHelper, "_get_linux_service_path", return_value=fake_service),
            patch("subprocess.run", return_value=mock_res),
        ):
            success, _ = SchedulerHelper.install_daemon_service()
            assert success is True
            content = fake_service.read_text(encoding="utf-8")
            assert "ExecStart=/home/alice/.local/bin/smartbackup watch" in content
            assert "-m smartbackup" not in content

    def test_scheduler_daemon_install_frozen_macos_omits_dash_m(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", "/Users/alice/.local/bin/smartbackup")
        fake_plist = tmp_path / "com.smartbackup.watcher.plist"
        mock_res = MagicMock(returncode=0)

        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(SchedulerHelper, "_get_macos_plist_path", return_value=fake_plist),
            patch("subprocess.run", return_value=mock_res),
        ):
            success, _ = SchedulerHelper.install_daemon_service()
            assert success is True
            content = fake_plist.read_text(encoding="utf-8")
            assert "<string>/Users/alice/.local/bin/smartbackup</string>" in content
            assert "<string>watch</string>" in content
            assert "<string>-m</string>" not in content


class TestReleaseArtifactsAndInstallers:
    """Contract and syntax checks for CI workflows and blank-machine installer scripts."""

    def test_workflows_exist_and_target_all_three_evergreen_runners(self):
        ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        release_yml = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        for content in (ci_yml, release_yml):
            assert "ubuntu-latest" in content
            assert "macos-latest" in content
            assert "windows-latest" in content

        assert "PyInstaller" in release_yml
        assert "SHA256SUMS.txt" in release_yml
        assert "workflow_dispatch" in release_yml
        assert "scripts/install.sh" in release_yml
        assert "scripts/install.ps1" in release_yml

    def test_install_sh_contract(self):
        script = REPO_ROOT / "scripts" / "install.sh"
        content = script.read_text(encoding="utf-8")

        assert content.startswith("#!/bin/sh\n")
        assert "CodingWithMK/smartbackup_file-backup-automation" in content
        assert "SMARTBACKUP_VERSION" in content
        assert ".local/bin" in content
        assert "SHA256SUMS.txt" in content

    def test_install_ps1_contract_and_syntax(self):
        script = REPO_ROOT / "scripts" / "install.ps1"
        content = script.read_text(encoding="utf-8")

        assert '$ErrorActionPreference = "Stop"' in content
        assert "CodingWithMK/smartbackup_file-backup-automation" in content
        assert "smartbackup-windows-x86_64.exe" in content
        assert "SMARTBACKUP_VERSION" in content
        assert "SHA256SUMS.txt" in content

        if platform.system() == "Windows":
            ps_check = (
                "$errors = $null; "
                f"[void][System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$errors); "
                "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_check],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert proc.returncode == 0, proc.stderr
