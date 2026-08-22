"""
SchedulerHelper - Helps set up automatic backups.
"""

import platform
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


class SchedulerHelper:
    """
    Helps set up automatic backups.

    Supports:
    - Windows Task Scheduler
    - macOS launchd
    - Linux cron/systemd
    """

    @staticmethod
    def setup_scheduled_backup(interval_hours: int = 24) -> None:
        """Sets up a scheduled backup."""
        system = platform.system()
        script_path = Path(__file__).resolve()

        if system == "Windows":
            SchedulerHelper._setup_windows_task(script_path, interval_hours)
        elif system == "Darwin":
            SchedulerHelper._setup_macos_launchd(script_path, interval_hours)
        else:
            SchedulerHelper._setup_linux_cron(script_path, interval_hours)

    @staticmethod
    def _setup_windows_task(script_path: Path, interval_hours: int) -> None:
        """Creates Windows Scheduled Task."""
        console = Console(highlight=False)
        task_name = "SmartBackup"
        python_path = sys.executable

        instructions = (
            f"[bold]To set up automatic backup on Windows:[/bold]\n\n"
            f"1. Open Task Scheduler (taskschd.msc)\n"
            f"2. Create a new task with the following settings:\n"
            f"   - Name: [cyan]{task_name}[/cyan]\n"
            f"   - Trigger: Daily / Every {interval_hours} hours\n"
            f"   - Action: Start a program\n"
            f"     - Program: [cyan]{python_path}[/cyan]\n"
            f'     - Arguments: [cyan]"{script_path}"[/cyan]\n\n'
            f"Or run the following command as Administrator:"
        )

        cmd = (
            f'schtasks /create /tn "{task_name}" '
            f'/tr "\\"{python_path}\\" \\"{script_path}\\"" '
            f"/sc hourly /mo {interval_hours}"
        )

        console.print()
        console.print(Panel(instructions, title="Windows Setup", style="cyan", expand=False))
        console.print(Syntax(cmd, "powershell", theme="monokai", padding=1))
        console.print()

    @staticmethod
    def _setup_macos_launchd(script_path: Path, interval_hours: int) -> None:
        """Creates macOS LaunchAgent."""
        console = Console(highlight=False)
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.smartbackup.plist"
        interval_seconds = interval_hours * 3600

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartbackup</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""

        instructions = (
            f"[bold]To set up automatic backup on macOS:[/bold]\n\n"
            f"1. Create the file: [cyan]{plist_path}[/cyan]\n"
            f"2. Add the content shown below\n"
            f"3. Load the agent:\n"
            f"   [cyan]launchctl load {plist_path}[/cyan]"
        )

        console.print()
        console.print(Panel(instructions, title="macOS Setup", style="cyan", expand=False))
        console.print(Syntax(plist_content, "xml", theme="monokai", padding=1))
        console.print()

    @staticmethod
    def _setup_linux_cron(script_path: Path, interval_hours: int) -> None:
        """Shows cron setup for Linux."""
        console = Console(highlight=False)
        cron_schedule = f"0 */{interval_hours} * * *" if interval_hours < 24 else "0 9 * * *"

        service_content = f"""[Unit]
Description=Smart Backup Service

[Service]
Type=oneshot
ExecStart={sys.executable} {script_path}"""

        timer_content = f"""[Unit]
Description=Run Smart Backup every {interval_hours} hours

[Timer]
OnBootSec=15min
OnUnitActiveSec={interval_hours}h

[Install]
WantedBy=timers.target"""

        instructions = (
            f"[bold]To set up automatic backup on Linux:[/bold]\n\n"
            f"[bold]Option 1 - Cron:[/bold]\n"
            f"  1. Open crontab: [cyan]crontab -e[/cyan]\n"
            f"  2. Add the following line:\n"
            f"     [cyan]{cron_schedule} {sys.executable} {script_path}[/cyan]\n\n"
            f"[bold]Option 2 - Systemd:[/bold]\n"
            f"  Create the service and timer files shown below,\n"
            f"  then enable with:\n"
            f"  [cyan]systemctl --user enable --now smartbackup.timer[/cyan]"
        )

        console.print()
        console.print(Panel(instructions, title="Linux Setup", style="cyan", expand=False))
        console.print()
        console.print("[bold]~/.config/systemd/user/smartbackup.service:[/bold]")
        console.print(Syntax(service_content, "ini", theme="monokai", padding=1))
        console.print()
        console.print("[bold]~/.config/systemd/user/smartbackup.timer:[/bold]")
        console.print(Syntax(timer_content, "ini", theme="monokai", padding=1))
        console.print()

    # ---------------------------------------------------------------------------
    # Daemon Service Helpers (Auto-Detect Watcher Daemon)
    # ---------------------------------------------------------------------------

    @staticmethod
    def install_daemon_service(
        python_exe: Optional[str] = None,
        interval: float = 2.5,
        cooldown: int = 300,
    ) -> tuple[bool, str]:
        """
        Installs and registers the background auto-detect watcher daemon service.

        Returns:
            Tuple of (success: bool, message: str)
        """
        system = platform.system()
        py_exe = python_exe or sys.executable

        if system == "Darwin":
            return SchedulerHelper._install_macos_daemon(py_exe)
        elif system == "Windows":
            return SchedulerHelper._install_windows_daemon(py_exe)
        else:
            return SchedulerHelper._install_linux_daemon(py_exe)

    @staticmethod
    def uninstall_daemon_service() -> tuple[bool, str]:
        """
        Unregisters and stops the background auto-detect watcher daemon service.

        Returns:
            Tuple of (success: bool, message: str)
        """
        system = platform.system()

        if system == "Darwin":
            return SchedulerHelper._uninstall_macos_daemon()
        elif system == "Windows":
            return SchedulerHelper._uninstall_windows_daemon()
        else:
            return SchedulerHelper._uninstall_linux_daemon()

    @staticmethod
    def get_daemon_status() -> dict:
        """
        Queries the current status of the background watcher daemon service.

        Returns:
            Dictionary containing installed, running, pid, service_path, and details.
        """
        system = platform.system()

        if system == "Darwin":
            return SchedulerHelper._get_macos_daemon_status()
        elif system == "Windows":
            return SchedulerHelper._get_windows_daemon_status()
        else:
            return SchedulerHelper._get_linux_daemon_status()

    # --- macOS Daemon Implementation ---

    @staticmethod
    def _get_macos_plist_path() -> Path:
        return Path.home() / "Library" / "LaunchAgents" / "com.smartbackup.watcher.plist"

    @staticmethod
    def _install_macos_daemon(py_exe: str) -> tuple[bool, str]:
        import subprocess

        plist_path = SchedulerHelper._get_macos_plist_path()
        log_dir = Path.home() / ".config" / "smartbackup" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smartbackup.watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exe}</string>
        <string>-m</string>
        <string>smartbackup</string>
        <string>watch</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir / "watcher.log"}</string>
    <key>StandardErrorPath</key>
    <string>{log_dir / "watcher.err.log"}</string>
</dict>
</plist>"""

        try:
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)

            # Unload any previous instance
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            # Load new plist
            res = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"macOS LaunchAgent registered and started at {plist_path}"
            return False, f"LaunchAgent written to {plist_path} but launchctl load returned error: {res.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to install macOS LaunchAgent: {e}"

    @staticmethod
    def _uninstall_macos_daemon() -> tuple[bool, str]:
        import subprocess

        plist_path = SchedulerHelper._get_macos_plist_path()
        if not plist_path.exists():
            return True, "No LaunchAgent plist found; service is not installed."

        try:
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            plist_path.unlink()
            return True, "macOS LaunchAgent unloaded and removed successfully."
        except Exception as e:
            return False, f"Failed to remove macOS LaunchAgent: {e}"

    @staticmethod
    def _get_macos_daemon_status() -> dict:
        import subprocess

        plist_path = SchedulerHelper._get_macos_plist_path()
        installed = plist_path.exists()
        running = False
        pid = None
        details = "Not installed"

        if installed:
            details = "Installed"
            try:
                res = subprocess.run(
                    ["launchctl", "list", "com.smartbackup.watcher"],
                    capture_output=True,
                    text=True,
                )
                if res.returncode == 0:
                    # Try to extract PID
                    for line in res.stdout.splitlines():
                        if '"PID"' in line or "PID" in line:
                            parts = line.strip().replace(";", "").split("=")
                            if len(parts) == 2 and parts[1].strip().isdigit():
                                pid = int(parts[1].strip())
                                break
                    if pid is not None:
                        running = True
                        details = "Running"
                    else:
                        running = False
                        details = "Loaded (Idle/Stopped)"
                else:
                    details = "Installed (Stopped)"
            except Exception as e:
                details = f"Installed (Status check failed: {e})"

        return {
            "installed": installed,
            "running": running,
            "pid": pid,
            "service_path": str(plist_path) if installed else None,
            "details": details,
        }

    # --- Windows Daemon Implementation ---

    @staticmethod
    def _install_windows_daemon(py_exe: str) -> tuple[bool, str]:
        import subprocess

        task_name = "SmartBackupWatcher"
        cmd = (
            f'schtasks /create /tn "{task_name}" '
            f'/tr "\\"{py_exe}\\" -m smartbackup watch" '
            f'/sc onlogon /rl highest /f'
        )
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                # Attempt to run immediately
                subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True)
                return True, f"Windows Scheduled Task '{task_name}' created and started."
            return False, f"schtasks failed with error: {res.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to register Windows scheduled task: {e}"

    @staticmethod
    def _uninstall_windows_daemon() -> tuple[bool, str]:
        import subprocess

        task_name = "SmartBackupWatcher"
        cmd = f'schtasks /delete /tn "{task_name}" /f'
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                return True, f"Windows Scheduled Task '{task_name}' removed."
            return False, f"schtasks delete error: {res.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to delete Windows scheduled task: {e}"

    @staticmethod
    def _get_windows_daemon_status() -> dict:
        import subprocess

        task_name = "SmartBackupWatcher"
        cmd = f'schtasks /query /tn "{task_name}" /fo LIST'
        installed = False
        running = False
        pid = None
        details = "Not installed"

        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                installed = True
                details = "Installed"
                if "Running" in res.stdout:
                    running = True
                    details = "Running"
                elif "Ready" in res.stdout:
                    details = "Ready (Stopped)"
            else:
                details = "Not installed"
        except Exception as e:
            details = f"Status check failed: {e}"

        return {
            "installed": installed,
            "running": running,
            "pid": pid,
            "service_path": f"Task: {task_name}" if installed else None,
            "details": details,
        }

    # --- Linux Daemon Implementation ---

    @staticmethod
    def _get_linux_service_path() -> Path:
        return Path.home() / ".config" / "systemd" / "user" / "smartbackup-watcher.service"

    @staticmethod
    def _install_linux_daemon(py_exe: str) -> tuple[bool, str]:
        import subprocess

        service_path = SchedulerHelper._get_linux_service_path()
        service_path.parent.mkdir(parents=True, exist_ok=True)

        service_content = f"""[Unit]
Description=SmartBackup USB Auto-Detect Daemon
After=default.target

[Service]
Type=simple
ExecStart={py_exe} -m smartbackup watch
Restart=always
RestartSec=5s

[Install]
WantedBy=default.target
"""
        try:
            with open(service_path, "w", encoding="utf-8") as f:
                f.write(service_content)

            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            res = subprocess.run(
                ["systemctl", "--user", "enable", "--now", "smartbackup-watcher.service"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return True, f"Linux systemd user service enabled and started at {service_path}"
            return False, f"Failed to enable systemd service: {res.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to install systemd user service: {e}"

    @staticmethod
    def _uninstall_linux_daemon() -> tuple[bool, str]:
        import subprocess

        service_path = SchedulerHelper._get_linux_service_path()
        if not service_path.exists():
            return True, "No systemd service file found; service is not installed."

        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "smartbackup-watcher.service"],
                capture_output=True,
            )
            service_path.unlink()
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            return True, "Linux systemd user service disabled and removed."
        except Exception as e:
            return False, f"Failed to remove Linux systemd service: {e}"

    @staticmethod
    def _get_linux_daemon_status() -> dict:
        import subprocess

        service_path = SchedulerHelper._get_linux_service_path()
        installed = service_path.exists()
        running = False
        pid = None
        details = "Not installed"

        if installed:
            details = "Installed"
            try:
                res = subprocess.run(
                    ["systemctl", "--user", "is-active", "smartbackup-watcher.service"],
                    capture_output=True,
                    text=True,
                )
                status_text = res.stdout.strip()
                if status_text == "active":
                    running = True
                    details = "Running"
                    # Try to get MainPID
                    show_res = subprocess.run(
                        ["systemctl", "--user", "show", "smartbackup-watcher.service", "--property=MainPID"],
                        capture_output=True,
                        text=True,
                    )
                    if "=" in show_res.stdout:
                        pid_val = show_res.stdout.split("=")[1].strip()
                        if pid_val.isdigit() and int(pid_val) > 0:
                            pid = int(pid_val)
                else:
                    details = f"Installed ({status_text})"
            except Exception as e:
                details = f"Installed (Status check failed: {e})"

        return {
            "installed": installed,
            "running": running,
            "pid": pid,
            "service_path": str(service_path) if installed else None,
            "details": details,
        }

