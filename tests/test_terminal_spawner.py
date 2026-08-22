"""
Tests for TerminalSpawner.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from smartbackup.config import ConfigManager
from smartbackup.platform.terminal import TerminalSpawner


class TestTerminalSpawner:
    """Tests for TerminalSpawner."""

    def test_headless_detection_linux_no_display(self):
        """Verify is_headless returns True on Linux without DISPLAY."""
        spawner = TerminalSpawner()
        with patch("platform.system", return_value="Linux"), \
             patch.dict("os.environ", {}, clear=True):
            assert spawner.is_headless() is True

    def test_headless_detection_linux_with_display(self):
        """Verify is_headless returns False on Linux with DISPLAY."""
        spawner = TerminalSpawner()
        with patch("platform.system", return_value="Linux"), \
             patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
            assert spawner.is_headless() is False

    def test_headless_detection_ssh_session_without_display(self):
        """Verify is_headless returns True when SSH session detected on Linux without DISPLAY."""
        spawner = TerminalSpawner()
        with patch("platform.system", return_value="Linux"), \
             patch.dict("os.environ", {"SSH_CLIENT": "192.168.1.100 52341 22"}, clear=True):
            assert spawner.is_headless() is True

    def test_spawn_skips_when_headless(self):
        """Verify spawn_prompt returns False when headless."""
        spawner = TerminalSpawner()
        with patch.object(spawner, "is_headless", return_value=True):
            assert spawner.spawn_prompt(Path("/Volumes/Backup")) is False

    def test_windows_spawner_prefers_wt_exe(self):
        """Verify Windows spawns wt.exe when available."""
        spawner = TerminalSpawner()
        mount_path = Path("E:/")

        with patch("platform.system", return_value="Windows"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "C:\\Windows\\System32\\wt.exe" if "wt" in x else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python.exe")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert "wt.exe" in args[0]
            assert "--prompt" in args

    def test_windows_spawner_fallback_to_cmd(self):
        """Verify Windows falls back to cmd.exe when wt.exe is missing."""
        spawner = TerminalSpawner()
        mount_path = Path("E:/")

        with patch("platform.system", return_value="Windows"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "cmd.exe" if "cmd" in x else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python.exe")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert "cmd.exe" in str(args)

    def test_windows_spawner_fallback_to_powershell_when_cmd_fails(self):
        """Verify Windows falls back to powershell.exe when wt.exe is missing and cmd.exe fails."""
        spawner = TerminalSpawner()
        mount_path = Path("E:/")

        def _mock_popen(cmd, *args, **kwargs):
            if isinstance(cmd, str) and "cmd.exe" in cmd:
                raise OSError("CMD unavailable")
            return MagicMock()

        with patch("platform.system", return_value="Windows"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "powershell.exe" if "powershell" in x else ("cmd.exe" if "cmd" in x else None)), \
             patch("subprocess.Popen", side_effect=_mock_popen) as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python.exe")
            assert res is True
            assert mock_popen.call_count == 2
            second_call_args = mock_popen.call_args_list[1][0][0]
            assert "powershell.exe" in second_call_args

    def test_windows_spawner_all_fail_returns_false(self):
        """Verify Windows returns False gracefully when all spawners fail."""
        spawner = TerminalSpawner()
        mount_path = Path("E:/")

        with patch("platform.system", return_value="Windows"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", return_value=None), \
             patch("subprocess.Popen", side_effect=OSError("Failed")):

            res = spawner.spawn_prompt(mount_path, python_exe="python.exe")
            assert res is False

    def test_macos_spawner_uses_osascript(self):
        """Verify macOS uses AppleScript via osascript for Terminal.app."""
        spawner = TerminalSpawner()
        mount_path = Path("/Volumes/BackupDisk")

        mock_res = MagicMock()
        mock_res.returncode = 0

        with patch("platform.system", return_value="Darwin"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("subprocess.run", return_value=mock_res) as mock_run:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "osascript"
            assert any("Terminal" in a for a in args)

    def test_macos_spawner_uses_iterm2_when_configured(self):
        """Verify macOS targets iTerm2 when configured in ConfigManager."""
        config_mgr = MagicMock(spec=ConfigManager)
        config_mgr.get_preferred_terminal.return_value = "iTerm2"
        spawner = TerminalSpawner(config_manager=config_mgr)
        mount_path = Path("/Volumes/BackupDisk")

        with patch("platform.system", return_value="Darwin"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "osascript"
            assert any("iTerm" in a for a in args)

    def test_macos_spawner_fallback_on_osascript_failure_1743(self):
        """Verify macOS falls back to open -a Terminal when osascript fails with error -1743."""
        spawner = TerminalSpawner()
        mount_path = Path("/Volumes/BackupDisk")

        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "-1743: Not authorized to send Apple events"

        with patch("platform.system", return_value="Darwin"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("subprocess.run", return_value=mock_res), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "open"

    def test_linux_spawner_uses_gnome_terminal(self):
        """Verify Linux detects and spawns gnome-terminal with -- flag."""
        spawner = TerminalSpawner()
        mount_path = Path("/media/user/Backup")

        with patch("platform.system", return_value="Linux"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/gnome-terminal" if x == "gnome-terminal" else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "/usr/bin/gnome-terminal"
            assert args[1] == "--"
            assert "--prompt" in args

    def test_linux_spawner_uses_kitty(self):
        """Verify Linux detects and spawns kitty."""
        spawner = TerminalSpawner()
        mount_path = Path("/media/user/Backup")

        with patch("platform.system", return_value="Linux"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/kitty" if x == "kitty" else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "/usr/bin/kitty"
            assert "--prompt" in args

    def test_linux_spawner_uses_alacritty(self):
        """Verify Linux detects and spawns alacritty with -e flag."""
        spawner = TerminalSpawner()
        mount_path = Path("/media/user/Backup")

        with patch("platform.system", return_value="Linux"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/alacritty" if x == "alacritty" else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "/usr/bin/alacritty"
            assert args[1] == "-e"
            assert "--prompt" in args

    def test_linux_spawner_uses_konsole(self):
        """Verify Linux detects and spawns konsole with -e flag."""
        spawner = TerminalSpawner()
        mount_path = Path("/media/user/Backup")

        with patch("platform.system", return_value="Linux"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/konsole" if x == "konsole" else None), \
             patch("subprocess.Popen") as mock_popen:

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is True
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "/usr/bin/konsole"
            assert args[1] == "-e"

    def test_linux_spawner_no_emulator_returns_false(self):
        """Verify Linux logs error and returns False when no terminal emulator is found."""
        spawner = TerminalSpawner()
        mount_path = Path("/media/user/Backup")

        with patch("platform.system", return_value="Linux"), \
             patch.object(spawner, "is_headless", return_value=False), \
             patch("shutil.which", return_value=None):

            res = spawner.spawn_prompt(mount_path, python_exe="python3")
            assert res is False
