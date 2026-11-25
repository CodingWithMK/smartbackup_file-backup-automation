"""
TerminalSpawner - Cross-platform interactive terminal window spawner.
"""

import logging
import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from smartbackup.config import ConfigManager
from smartbackup.platform.runtime import build_cli_command

logger = logging.getLogger(__name__)


class TerminalSpawner:
    """
    Spawns an interactive native terminal session executing SmartBackup
    with ``--target <mount_path> --prompt`` (directly when running as a
    frozen standalone binary, or via ``python -m smartbackup`` otherwise).
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self.config_manager = config_manager or ConfigManager()

    def is_headless(self) -> bool:
        """Check if current environment is headless (e.g., SSH session without GUI)."""
        system = platform.system()
        if system == "Linux":
            # Check for display server
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                return True
        # Check SSH indicators
        if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
            if system == "Linux" and not os.environ.get("DISPLAY"):
                return True
        return False

    def spawn_prompt(self, target_path: Path, python_exe: Optional[str] = None) -> bool:
        """
        Spawn an interactive native terminal window for the given target drive.

        Args:
            target_path: Path to the detected backup medium
            python_exe: Optional path to Python interpreter (default: sys.executable)

        Returns:
            True if terminal was spawned successfully, False otherwise.
        """
        if self.is_headless():
            logger.info(f"Headless environment detected; skipping GUI terminal spawn for {target_path}")
            return False

        system = platform.system()

        try:
            if system == "Windows":
                return self._spawn_windows(target_path, python_exe)
            elif system == "Darwin":
                return self._spawn_macos(target_path, python_exe)
            else:
                return self._spawn_linux(target_path, python_exe)
        except Exception as e:
            logger.error(f"Failed to spawn interactive terminal: {e}")
            return False

    def _spawn_windows(self, target_path: Path, python_exe: Optional[str]) -> bool:
        """Spawn terminal on Windows (wt.exe -> cmd.exe -> powershell.exe)."""
        title = "SmartBackup - Auto-Detect Backup"
        target_str = str(target_path)
        cli_cmd = build_cli_command("--target", target_str, "--prompt", python_exe=python_exe)
        exe = cli_cmd[0]
        extra_args = cli_cmd[1:-3]  # ["-m", "smartbackup"] or [] when frozen
        extra_str = f" {' '.join(extra_args)}" if extra_args else ""

        # 1. Try Windows Terminal (wt.exe)
        wt_path = shutil.which("wt.exe") or shutil.which("wt")
        if wt_path:
            try:
                cmd = [wt_path, "--title", title, *cli_cmd]
                subprocess.Popen(cmd)
                return True
            except Exception as e:
                logger.warning(f"Failed to launch wt.exe, falling back to cmd.exe: {e}")

        # 2. Fallback to cmd.exe
        cmd_path = shutil.which("cmd.exe") or "cmd.exe"
        try:
            full_cmd = (
                f'start "{title}" "{exe}"{extra_str} --target "{target_str}" --prompt'
            )
            subprocess.Popen(f"{cmd_path} /c {full_cmd}", shell=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to launch cmd.exe, falling back to powershell: {e}")

        # 3. Fallback to powershell.exe
        ps_path = shutil.which("powershell.exe") or "powershell.exe"
        try:
            ps_cmd = [
                ps_path,
                "-NoExit",
                "-Command",
                f"& '{exe}'{extra_str} --target '{target_str}' --prompt",
            ]
            subprocess.Popen(ps_cmd)
            return True
        except Exception as e:
            logger.error(f"All Windows terminal spawners failed: {e}")
            return False

    def _spawn_macos(self, target_path: Path, python_exe: Optional[str]) -> bool:
        """Spawn terminal on macOS via AppleScript / Terminal.app / iTerm2."""
        target_str = str(target_path)
        cli_cmd = build_cli_command("--target", target_str, "--prompt", python_exe=python_exe)
        exe = cli_cmd[0]
        extra_args = cli_cmd[1:-3]
        extra_str = f" {' '.join(extra_args)}" if extra_args else ""
        shell_cmd = f'{exe}{extra_str} --target "{target_str}" --prompt'
        # Escape quotes for AppleScript
        escaped_shell_cmd = shell_cmd.replace('\\', '\\\\').replace('"', '\\"')

        preferred = self.config_manager.get_preferred_terminal()

        # 1. If iTerm2 preferred and available
        if preferred and preferred.lower() in ("iterm", "iterm2"):
            try:
                osa_cmd = [
                    "osascript",
                    "-e",
                    'tell application "iTerm"',
                    "-e",
                    f'create window with default profile command "{escaped_shell_cmd}"',
                    "-e",
                    "activate",
                    "-e",
                    "end tell",
                ]
                subprocess.Popen(osa_cmd)
                return True
            except Exception as e:
                logger.warning(f"Failed to launch iTerm2, falling back to Terminal.app: {e}")

        # 2. Default: Terminal.app via osascript
        try:
            osa_cmd = [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script "{escaped_shell_cmd}"',
                "-e",
                'tell application "Terminal" to activate',
            ]
            res = subprocess.run(osa_cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return True
            logger.warning(f"osascript returned code {res.returncode}: {res.stderr}. Trying open fallback.")
        except Exception as e:
            logger.warning(f"osascript execution failed: {e}. Trying open fallback.")

        # 3. Fallback: Create temporary launcher command file and use `open`
        try:
            open_cmd = [
                "open",
                "-a",
                "Terminal.app",
            ]
            subprocess.Popen(open_cmd)
            return True
        except Exception as e:
            logger.error(f"macOS terminal spawner failed: {e}")
            return False

    def _spawn_linux(self, target_path: Path, python_exe: Optional[str]) -> bool:
        """Spawn terminal on Linux across supported terminal emulators."""
        target_str = str(target_path)
        prompt_args = build_cli_command("--target", target_str, "--prompt", python_exe=python_exe)
        prompt_cmd_str = " ".join(shlex.quote(arg) for arg in prompt_args)

        # Check configured preferred terminal first
        preferred = self.config_manager.get_preferred_terminal()
        emulators_to_try: list[str] = []
        if preferred:
            emulators_to_try.append(preferred)

        emulators_to_try.extend([
            "x-terminal-emulator",
            "gnome-terminal",
            "kitty",
            "alacritty",
            "konsole",
            "xfce4-terminal",
            "xterm",
        ])

        for emulator in emulators_to_try:
            emu_path = shutil.which(emulator)
            if not emu_path:
                continue

            try:
                base_name = Path(emu_path).name.lower()
                if "gnome-terminal" in base_name:
                    cmd = [emu_path, "--"] + prompt_args
                elif "kitty" in base_name:
                    cmd = [emu_path] + prompt_args
                elif "alacritty" in base_name:
                    cmd = [emu_path, "-e"] + prompt_args
                elif "konsole" in base_name:
                    cmd = [emu_path, "-e"] + prompt_args
                elif "xfce4-terminal" in base_name:
                    cmd = [emu_path, "-e", prompt_cmd_str]
                elif "xterm" in base_name:
                    cmd = [emu_path, "-e"] + prompt_args
                else:  # x-terminal-emulator and generic
                    cmd = [emu_path, "-e", prompt_cmd_str]

                subprocess.Popen(cmd)
                return True
            except Exception as e:
                logger.warning(f"Failed to spawn {emulator}: {e}")
                continue

        logger.error("No supported terminal emulator found on Linux.")
        return False
