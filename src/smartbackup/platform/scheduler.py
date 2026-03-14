"""
SchedulerHelper - Helps set up automatic backups.
"""

import platform
import sys
from pathlib import Path

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
