"""
SchedulerHelper - Helps set up automatic backups.
"""

import platform
import sys
from pathlib import Path


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
        task_name = "SmartBackup"
        python_path = sys.executable

        print(
            f"""
To set up automatic backup on Windows:

1. Open Task Scheduler (taskschd.msc)
2. Create a new task with the following settings:
   - Name: {task_name}
   - Trigger: Daily / Every {interval_hours} hours
   - Action: Start a program
     - Program: {python_path}
     - Arguments: "{script_path}"

Or run the following command as Administrator:
schtasks /create /tn "{task_name}" /tr "\\"{python_path}\\" \\"{script_path}\\"" /sc hourly /mo {interval_hours}
"""
        )

    @staticmethod
    def _setup_macos_launchd(script_path: Path, interval_hours: int) -> None:
        """Creates macOS LaunchAgent."""
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

        print(
            f"""
To set up automatic backup on macOS:

1. Create the file: {plist_path}
2. Add the following content:

{plist_content}

3. Load the agent:
   launchctl load {plist_path}
"""
        )

    @staticmethod
    def _setup_linux_cron(script_path: Path, interval_hours: int) -> None:
        """Shows cron setup for Linux."""
        cron_schedule = f"0 */{interval_hours} * * *" if interval_hours < 24 else "0 9 * * *"

        print(
            f"""
To set up automatic backup on Linux:

1. Open crontab:
   crontab -e

2. Add the following line:
   {cron_schedule} {sys.executable} {script_path}

Or for systemd timer, create:

~/.config/systemd/user/smartbackup.service:
[Unit]
Description=Smart Backup Service

[Service]
Type=oneshot
ExecStart={sys.executable} {script_path}

~/.config/systemd/user/smartbackup.timer:
[Unit]
Description=Run Smart Backup every {interval_hours} hours

[Timer]
OnBootSec=15min
OnUnitActiveSec={interval_hours}h

[Install]
WantedBy=timers.target

Then enable with:
systemctl --user enable --now smartbackup.timer
"""
        )
