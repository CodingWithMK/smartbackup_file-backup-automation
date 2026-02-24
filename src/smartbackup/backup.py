"""
SmartBackup - Main backup class.
"""

import os
import platform
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from smartbackup.config import BackupConfig
from smartbackup.core.engine import BackupEngine
from smartbackup.handlers import FallbackHandler
from smartbackup.platform.devices import DeviceDetector
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.ui.logger import BackupLogger


class SmartBackup:
    """Main class that brings all components together."""

    def __init__(self) -> None:
        self.logger = BackupLogger(verbose=True)
        self.fallback = FallbackHandler(self.logger)

    def run(
        self,
        custom_source: Optional[Path] = None,
        custom_target: Optional[Path] = None,
        target_label: Optional[str] = None,
        use_manifest: bool = True,
        device_name: Optional[str] = None,
    ) -> bool:
        """
        Executes the backup.

        Args:
            custom_source: Optional custom source path
            custom_target: Optional custom target path
            target_label: Preferred target medium label
            use_manifest: Whether to use manifest for incremental backups
            device_name: Custom device name (default: auto-detected hostname)

        Returns:
            True if successful, False on errors
        """
        self._print_banner()

        # Determine source directory
        source_path = custom_source or PathResolver.get_documents_path()

        # Determine device name
        resolved_device_name = device_name or get_device_name()

        self.logger.info(f"Source directory: {source_path}")
        self.logger.info(f"Device identifier: {resolved_device_name}")
        self.logger.info(f"Operating system: {platform.system()} {platform.release()}")

        if not source_path.exists():
            self.logger.error(f"Source directory does not exist: {source_path}")
            return False

        # Find external medium
        backup_path = custom_target
        device_detector = DeviceDetector(self.logger)

        max_retries = 3
        for attempt in range(max_retries):
            if backup_path is None:
                backup_path = device_detector.find_backup_device(
                    required_space=1024 * 1024 * 100,  # 100 MB minimum
                    preferred_label=target_label,
                )

            if backup_path is None:
                backup_path = self.fallback.handle_no_device(source_path)
                if backup_path is None and attempt < max_retries - 1:
                    continue  # Retry

            break

        if backup_path is None:
            return False

        # Create configuration
        config = BackupConfig(
            source_path=source_path,
            backup_path=backup_path,
            backup_folder_name="Documents-Backup",
            device_name=resolved_device_name,
            max_workers=min(8, (os.cpu_count() or 4)),
            use_hash_verification=False,  # Faster without
            verbose=True,
            use_manifest=use_manifest,
        )

        # Perform backup
        engine = BackupEngine(config, self.logger)
        result = engine.run_backup()

        # Summary
        self.logger.summary(result)

        # Notification
        success = result.errors == 0
        self.fallback.notify_completion(result, success)

        return success

    def _print_banner(self) -> None:
        """Shows the program banner using Rich."""
        banner_text = Text(justify="center")
        banner_text.append(
            "███████╗███╗   ███╗ █████╗ ██████╗ ████████╗\n"
            "██╔════╝████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝\n"
            "███████╗██╔████╔██║███████║██████╔╝   ██║   \n"
            "╚════██║██║╚██╔╝██║██╔══██║██╔══██╗   ██║   \n"
            "███████║██║ ╚═╝ ██║██║  ██║██║  ██║   ██║   \n"
            "╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   \n",
            style="bold cyan",
        )
        banner_text.append(
            "██████╗  █████╗  ██████╗██╗  ██╗██╗   ██╗██████╗ \n"
            "██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██║   ██║██╔══██╗\n"
            "██████╔╝███████║██║     █████╔╝ ██║   ██║██████╔╝\n"
            "██╔══██╗██╔══██║██║     ██╔═██╗ ██║   ██║██╔═══╝ \n"
            "██████╔╝██║  ██║╚██████╗██║  ██╗╚██████╔╝██║     \n"
            "╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝╚═╝     \n",
            style="bold cyan",
        )
        banner_text.append("\n", style="")
        banner_text.append("Intelligent Backup System v0.4.0\n", style="bold white")
        banner_text.append("Cross-Platform  •  Incremental  •  Efficient", style="dim")

        _console = Console(highlight=False)
        _console.print()
        _console.print(
            Panel(
                banner_text,
                style="cyan",
                padding=(1, 4),
            )
        )
        _console.print()
