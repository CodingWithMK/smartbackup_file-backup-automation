"""
CLI - Command line interface for SmartBackup.

Modernised with Typer and Rich for a polished developer experience.
"""

import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from smartbackup.backup import SmartBackup
from smartbackup.config import EXCLUDED_EXTENSIONS, ConfigManager
from smartbackup.core.scanner import ExclusionFilter
from smartbackup.manifest.factory import (
    SUPPORTED_MANIFEST_FORMATS,
    get_manifest_manager,
    has_manifest,
)
from smartbackup.models import SelectionMetadata
from smartbackup.platform.identity import get_device_name, sanitize_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.platform.scheduler import SchedulerHelper
from smartbackup.platform.terminal import TerminalSpawner
from smartbackup.platform.watcher import DeviceWatcher
from smartbackup.ui.logger import BackupLogger
from smartbackup.ui.selector import FolderSelector

__version__ = "0.8.0"

console = Console(highlight=False)


def _is_interactive_tty() -> bool:
    """Return True when both stdin and stdout are attached to an interactive TTY."""
    return bool(sys.stdin.isatty() and sys.stdout.isatty())

app = typer.Typer(
    name="smartbackup",
    help="SmartBackup - Intelligent Backup System for Developers",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)

daemon_app = typer.Typer(
    name="daemon",
    help="Manage OS background watcher daemon service",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(daemon_app, name="daemon")

config_app = typer.Typer(
    name="config",
    help="Inspect and update the persistent SmartBackup configuration",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# Helpers (unchanged logic)
# ---------------------------------------------------------------------------


def _resolve_device_target(root: Path, device: Optional[str] = None) -> Path:
    """Resolve the backup target directory, accounting for device subfolders.

    If a device name is given, use that subfolder. Otherwise, check for a
    legacy flat layout (manifest at root) or fall back to the auto-detected
    device name.
    """
    if device:
        return root / device

    # Legacy layout: manifest lives directly in root
    if has_manifest(root):
        return root

    # New layout: use auto-detected device name
    device_name = get_device_name()
    candidate = root / device_name
    if candidate.exists():
        return candidate

    # If nothing matches, fall back to root (will likely show "not found")
    return root


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"smartbackup {__version__}")
        raise typer.Exit()


def _list_devices(backup_path: Path, backup_folder: str = "Documents-Backup") -> None:
    """List all device backup folders on the drive."""
    logger = BackupLogger(verbose=True)
    root = backup_path / backup_folder

    if not root.exists():
        logger.warning("No backup directory found!")
        return

    logger.header("Devices with Backups")

    table = Table(show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Device", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Last Backup")

    devices_found = False
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith(("_", ".")):
            if has_manifest(item):
                manager = get_manifest_manager(item)
                manifest = manager.load()
                if manifest:
                    table.add_row(
                        item.name,
                        f"{manifest.total_files:,}",
                        f"{manifest.total_size / (1024**2):.1f} MB",
                        manifest.updated.strftime("%Y-%m-%d %H:%M"),
                    )
                    devices_found = True

    if devices_found:
        console.print(table)
    else:
        logger.warning("No device backups found")


def _list_available_drives() -> None:
    """Display all available external drives."""
    logger = BackupLogger(verbose=True)
    logger.header("Available External Storage Media")

    drives = PathResolver.find_external_drives()

    if not drives:
        logger.warning("No external storage media found!")
        return

    table = Table(show_header=True, header_style="bold cyan", expand=False)
    table.add_column("No.", justify="right", style="dim")
    table.add_column("Label", style="bold")
    table.add_column("Path")
    table.add_column("Free", justify="right", style="green")

    for i, (path, label, free) in enumerate(drives, 1):
        free_str = f"{free / (1024**3):.1f} GB"
        table.add_row(str(i), label, str(path), free_str)

    console.print()
    console.print(table)
    console.print()


def _show_manifest(
    backup_path: Path,
    backup_folder: str = "Documents-Backup",
    device: Optional[str] = None,
) -> None:
    """Display manifest contents."""
    logger = BackupLogger(verbose=True)
    logger.header("Backup Manifest")

    root = backup_path / backup_folder
    if not root.exists():
        logger.error(f"Backup directory not found: {root}")
        return

    # Determine target: device subfolder or legacy layout
    target = _resolve_device_target(root, device)

    manager = get_manifest_manager(target)
    if not manager.exists():
        logger.warning("No manifest found in backup directory")
        return

    manifest = manager.load()
    if manifest is None:
        logger.error("Failed to load manifest")
        return

    table = Table(
        title="MANIFEST INFORMATION",
        title_style="bold cyan",
        show_header=False,
        expand=False,
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Version", str(manifest.version))
    table.add_row("Format", manifest.format.value)
    table.add_row("Source", str(manifest.source))
    if hasattr(manifest, "hostname") and manifest.hostname:
        table.add_row("Hostname", manifest.hostname)
    table.add_row("Created", manifest.created.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Updated", manifest.updated.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Backup Count", str(manifest.backup_count))
    mode_label = (
        "[bold cyan]Selective (--select)[/bold cyan]"
        if manifest.last_backup_mode == "select"
        else "Full"
    )
    table.add_row("Last Backup Mode", mode_label)
    if manifest.last_backup_mode == "select" and manifest.last_selected_folders:
        table.add_row(
            "Last Selected Folders",
            escape(", ".join(manifest.last_selected_folders)),
        )
    table.add_row("Total Files", f"{manifest.total_files:,}")
    table.add_row("Total Size", f"{manifest.total_size / (1024 * 1024):.2f} MB")

    console.print()
    console.print(table)

    if manifest.selective_backups:
        sel_table = Table(
            title="Selective Backup History (--select)",
            title_style="bold cyan",
            border_style="cyan",
            show_header=True,
            expand=False,
            padding=(0, 1),
        )
        sel_table.add_column("Run ID", style="bold")
        sel_table.add_column("Timestamp")
        sel_table.add_column("Folders")
        sel_table.add_column("Copied", justify="right", style="green")
        sel_table.add_column("Updated", justify="right", style="blue")
        sel_table.add_column("Deleted", justify="right", style="yellow")
        sel_table.add_column("Duration", justify="right")

        for rec in manifest.selective_backups:
            sel_table.add_row(
                escape(rec.run_id),
                rec.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                escape(", ".join(rec.selected_folders)),
                str(rec.files_copied),
                str(rec.files_updated),
                str(rec.files_deleted),
                f"{rec.duration_seconds:.1f}s",
            )

        console.print()
        console.print(sel_table)

    console.print()


def _verify_manifest(
    backup_path: Path,
    backup_folder: str = "Documents-Backup",
    device: Optional[str] = None,
) -> int:
    """Verify backup files against manifest."""
    logger = BackupLogger(verbose=True)
    logger.header("Verifying Backup Against Manifest")

    root = backup_path / backup_folder
    if not root.exists():
        logger.error(f"Backup directory not found: {root}")
        return 1

    target = _resolve_device_target(root, device)

    manager = get_manifest_manager(target)
    manifest = manager.load()
    if manifest is None:
        logger.error("No manifest found or failed to load")
        return 1

    logger.info(f"Verifying {manifest.total_files} files...")
    errors = manager.verify(manifest, target, verify_hashes=True)

    if not errors:
        logger.success("All files verified successfully!")
        return 0
    else:
        logger.error(f"Found {len(errors)} verification errors:")
        for error in errors[:20]:  # Show first 20 errors
            console.print(f"  [red]-[/red] {error}")
        if len(errors) > 20:
            console.print(f"  ... and {len(errors) - 20} more errors")
        return 1


# ---------------------------------------------------------------------------
# Restore sub-command
# ---------------------------------------------------------------------------


@app.command("restore", help="Restore files from backup")
def restore_cmd(
    source: Path = typer.Option(..., "-s", "--source", help="Backup source directory"),
    target: Optional[Path] = typer.Option(
        None, "-t", "--target", help="Target directory to restore to"
    ),
    pattern: Optional[list[str]] = typer.Option(
        None, "-p", "--pattern", help="Glob patterns to filter files"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing files"),
    conflict: Optional[str] = typer.Option(
        None,
        "--conflict",
        help="Conflict resolution: skip, overwrite, newer, rename",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview restore without copying"),
    list_files: bool = typer.Option(False, "--list", help="List files in backup"),
    manifest_info: bool = typer.Option(
        False, "--manifest-info", help="Show backup manifest summary"
    ),
    device_name: Optional[str] = typer.Option(
        None,
        "--device-name",
        help="Device name to restore from (default: auto-detected hostname)",
    ),
) -> None:
    """Handle the restore subcommand."""
    _handle_restore(
        source=source,
        target=target,
        pattern=pattern,
        overwrite=overwrite,
        conflict=conflict,
        dry_run=dry_run,
        list_files=list_files,
        manifest_info=manifest_info,
        device_name=device_name,
    )


def _handle_restore(
    source: Path,
    target: Optional[Path],
    pattern: Optional[list[str]],
    overwrite: bool,
    conflict: Optional[str],
    dry_run: bool,
    list_files: bool,
    device_name: Optional[str],
    manifest_info: bool = False,
) -> int:
    """Handle the restore subcommand (core logic)."""
    logger = BackupLogger(verbose=True)

    try:
        from smartbackup.core.restore import ConflictResolution, RestoreEngine
    except ImportError:
        logger.error("Restore functionality not yet available")
        logger.info("This feature will be implemented in the next version")
        raise typer.Exit(code=1) from None

    conflict_map = {
        "skip": ConflictResolution.SKIP,
        "overwrite": ConflictResolution.OVERWRITE,
        "newer": ConflictResolution.NEWER,
        "rename": ConflictResolution.RENAME,
    }
    conflict_resolution = None
    if conflict is not None:
        key = conflict.strip().lower()
        if key not in conflict_map:
            logger.error(
                f"Invalid --conflict value: {conflict}. "
                "Choose from: skip, overwrite, newer, rename"
            )
            raise typer.Exit(code=1)
        conflict_resolution = conflict_map[key]

    resolved_device = device_name or ""
    restore_engine = RestoreEngine(
        backup_path=source,
        target_path=target,
        logger=logger,
        device_name=resolved_device,
    )

    if manifest_info:
        if not restore_engine.backup_target.exists():
            logger.error(f"Backup directory not found: {restore_engine.backup_target}")
            raise typer.Exit(code=1)
        info = restore_engine.get_manifest_info()
        if info is None:
            logger.warning("No manifest found in backup.")
            raise typer.Exit(code=1)
        table = Table(
            title="BACKUP MANIFEST INFO",
            title_style="bold cyan",
            border_style="cyan",
            show_header=False,
            expand=False,
        )
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Source", str(info["source"]))
        table.add_row("Created", str(info["created"]))
        table.add_row("Updated", str(info["updated"]))
        table.add_row("Backup Count", str(info["backup_count"]))
        table.add_row("Total Files", f"{info['total_files']:,}")
        table.add_row("Total Size", f"{info['total_size']:,} bytes")
        console.print()
        console.print(table)
        console.print()
        raise typer.Exit(code=0)

    if list_files:
        logger.header("Files in Backup")
        if not restore_engine.backup_target.exists():
            logger.error(f"Backup directory not found: {restore_engine.backup_target}")
            raise typer.Exit(code=1)
        files = restore_engine.list_files(patterns=pattern)
        if not files:
            logger.warning("No matching files found in backup.")
        else:
            for rel_path, size in files:
                console.print(f"  {rel_path} ({size:,} bytes)")
        raise typer.Exit(code=0)

    # Perform restore
    try:
        if dry_run:
            logger.warning("DRY-RUN MODE - No files will be restored!")

        result = restore_engine.restore(
            patterns=pattern,
            overwrite=overwrite,
            dry_run=dry_run,
            conflict=conflict_resolution,
        )

        code = 0 if result.errors == 0 else 1
        raise typer.Exit(code=code)

    except typer.Exit:
        raise
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(code=1) from e


# ---------------------------------------------------------------------------
# Compress sub-command
# ---------------------------------------------------------------------------


@app.command("compress", help="Compress an existing backup into an archive")
def compress_cmd(
    target: Path = typer.Option(
        ...,
        "-t",
        "--target",
        help="Path to backup drive/directory containing Documents-Backup/",
    ),
    fmt: str = typer.Option(
        "zip",
        "-f",
        "--format",
        help="Compression format: zip or tar.gz",
    ),
    device_name: Optional[str] = typer.Option(
        None,
        "--device-name",
        help="Device name to compress (default: auto-detected hostname)",
    ),
    remove_source: bool = typer.Option(
        False,
        "--remove-source",
        help="Remove uncompressed backup directory after successful compression",
    ),
    backup_folder: str = typer.Option(
        "Documents-Backup",
        "--backup-folder",
        help="Backup folder name",
        hidden=True,
    ),
) -> None:
    """Compress an existing uncompressed backup into a zip or tar.gz archive."""
    _handle_compress(
        target=target,
        fmt=fmt,
        device_name=device_name,
        remove_source=remove_source,
        backup_folder=backup_folder,
    )


def _handle_compress(
    target: Path,
    fmt: str,
    device_name: Optional[str],
    remove_source: bool,
    backup_folder: str = "Documents-Backup",
) -> None:
    """Core logic for the compress subcommand."""
    import shutil

    from smartbackup.core.compressor import SUPPORTED_FORMATS, BackupCompressor

    logger = BackupLogger(verbose=True)
    logger.header("Compress Existing Backup")

    # Validate format
    if fmt not in SUPPORTED_FORMATS:
        logger.error(
            f"Unsupported compression format: {fmt!r}. "
            f"Use one of: {', '.join(SUPPORTED_FORMATS)}"
        )
        raise typer.Exit(code=1)

    # Resolve backup root
    root = target / backup_folder
    if not root.exists():
        logger.error(f"Backup directory not found: {root}")
        raise typer.Exit(code=1)

    # Resolve device target
    device_target = _resolve_device_target(root, device_name)
    resolved_device = device_target.name

    if not device_target.exists():
        logger.error(f"Device backup directory not found: {device_target}")
        raise typer.Exit(code=1)

    # Check if already compressed
    compressor = BackupCompressor(logger)
    if compressor.is_already_compressed(root, resolved_device):
        logger.warning(f"Archives already exist for device '{resolved_device}'")
        existing = compressor.find_archives(root, resolved_device)
        for archive in existing:
            logger.info(f"  Existing archive: {archive.name}")
        logger.info("Proceeding with new archive anyway...")

    # Create the archive
    archive_name = compressor.get_archive_name(resolved_device, fmt)
    archive_path = root / archive_name

    try:
        compressor.compress(device_target, archive_path, fmt)
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        raise typer.Exit(code=1) from e

    # Optionally remove the source directory
    if remove_source:
        logger.info(f"Removing uncompressed directory: {device_target}")
        try:
            shutil.rmtree(device_target)
            logger.success("Uncompressed backup directory removed")
        except Exception as e:
            logger.error(f"Failed to remove source directory: {e}")
            logger.warning("Archive was created successfully, but source was not removed")
            raise typer.Exit(code=1) from e

    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Watch & Daemon sub-commands
# ---------------------------------------------------------------------------


@app.command("watch", help="Watch for external backup storage media and trigger prompts")
def watch_cmd(
    interval: float = typer.Option(2.5, "-i", "--interval", help="Polling interval in seconds"),
    cooldown: Optional[int] = typer.Option(
        None,
        "-c",
        "--cooldown",
        help="Cooldown in seconds between drive prompts "
        "(default: auto_watch_cooldown config, else 300)",
    ),
) -> None:
    """Run foreground drive watcher daemon."""
    _handle_watch(interval=interval, cooldown=cooldown)


def _handle_watch(interval: float = 2.5, cooldown: Optional[int] = None) -> None:
    """Foreground drive watcher logic."""
    if cooldown is None:
        try:
            cooldown = ConfigManager().get_auto_watch_cooldown()
        except (TypeError, ValueError):
            # Hand-edited config: fall back to the historical default.
            cooldown = 300

    console.print(
        Panel(
            f"[bold green]SmartBackup Drive Watcher Active[/bold green]\n\n"
            f"[dim]Polling interval:[/dim] {interval}s\n"
            f"[dim]Debounce cooldown:[/dim] {cooldown}s\n\n"
            f"Listening for attached external backup storage media...\n"
            f"[dim]Press Ctrl+C to stop.[/dim]",
            title="[bold cyan]SmartBackup Watcher[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    spawner = TerminalSpawner()
    watcher = DeviceWatcher(
        interval=interval,
        cooldown=cooldown,
        on_drive_detected=spawner.spawn_prompt,
    )
    try:
        watcher.start(blocking=True)
    except KeyboardInterrupt:
        watcher.stop()
        console.print("\n[yellow]Watcher stopped by user.[/yellow]")
        raise typer.Exit(code=0) from None


@daemon_app.command("install", help="Install and start the background watcher service")
def daemon_install_cmd() -> None:
    """Install the background auto-detect watcher daemon service."""
    success, message = SchedulerHelper.install_daemon_service()
    if success:
        console.print(
            Panel(
                f"[bold green]Success:[/bold green] {message}",
                title="[bold cyan]Daemon Installation[/bold cyan]",
                border_style="green",
                expand=False,
            )
        )
        raise typer.Exit(code=0)
    else:
        console.print(
            Panel(
                f"[bold red]Error:[/bold red] {message}",
                title="[bold red]Daemon Installation Failed[/bold red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


@daemon_app.command("uninstall", help="Uninstall and stop the background watcher service")
def daemon_uninstall_cmd() -> None:
    """Uninstall the background auto-detect watcher daemon service."""
    success, message = SchedulerHelper.uninstall_daemon_service()
    if success:
        console.print(
            Panel(
                f"[bold green]Success:[/bold green] {message}",
                title="[bold cyan]Daemon Removal[/bold cyan]",
                border_style="green",
                expand=False,
            )
        )
        raise typer.Exit(code=0)
    else:
        console.print(
            Panel(
                f"[bold red]Error:[/bold red] {message}",
                title="[bold red]Daemon Removal Failed[/bold red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code=1)


@daemon_app.command("status", help="Check the status of the background watcher service")
def daemon_status_cmd() -> None:
    """Query background watcher daemon service status."""
    status = SchedulerHelper.get_daemon_status()
    table = Table(
        title="DAEMON SERVICE STATUS",
        title_style="bold cyan",
        border_style="cyan",
        show_header=False,
        expand=False,
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    installed_str = "[green]Installed[/green]" if status["installed"] else "[red]Not Installed[/red]"
    table.add_row("Installed", installed_str)

    if status["running"]:
        running_str = (
            f"[bold green]Running[/bold green] (PID: {status['pid']})"
            if status.get("pid")
            else "[bold green]Running[/bold green]"
        )
    else:
        running_str = "[yellow]Stopped[/yellow]"
    table.add_row("Status", running_str)

    if status.get("service_path"):
        table.add_row("Service Path", status["service_path"])
    table.add_row("Details", status.get("details", ""))

    console.print()
    console.print(table)
    console.print()
    raise typer.Exit(code=0)


@daemon_app.command("clear-state", help="Clear watcher debounce state (watcher_state.json)")
def daemon_clear_state_cmd() -> None:
    """Reset the watcher debounce lock so drives can prompt immediately."""
    from smartbackup.platform.watcher import DebounceLock

    lock = DebounceLock()
    lock.clear()
    console.print(
        Panel(
            f"[bold green]Success:[/bold green] Cleared watcher debounce state ({lock.state_file}).",
            title="[bold cyan]Daemon State Cleared[/bold cyan]",
            border_style="green",
            expand=False,
        )
    )
    raise typer.Exit(code=0)


@app.command("schedule", help="Show instructions to schedule periodic backups")
def schedule_cmd(
    hours: int = typer.Option(
        24, "--hours", "-H", min=1, help="Backup interval in hours"
    ),
) -> None:
    """Display OS-specific instructions for scheduling periodic backups."""
    SchedulerHelper.setup_scheduled_backup(interval_hours=hours)
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Main (default) command -- backup
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def backup_cmd(
    ctx: typer.Context,
    source: Optional[Path] = typer.Option(
        None, "-s", "--source", help="Source directory (default: Documents folder)"
    ),
    target: Optional[Path] = typer.Option(
        None,
        "-t",
        "--target",
        help="Target directory/drive (default: auto-detect external drive)",
    ),
    label: Optional[str] = typer.Option(None, "-l", "--label", help="Preferred target drive label"),
    prompt: bool = typer.Option(
        False, "--prompt", help="Run interactive prompt mode for detected drive"
    ),
    select: bool = typer.Option(
        False,
        "--select",
        help="Interactively select specific top-level folders from source to back up",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate backup without copying files"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Minimal output"),
    exclude: Optional[list[str]] = typer.Option(
        None, "--exclude", help="Additional exclusion patterns"
    ),
    list_drives: bool = typer.Option(
        False, "--list-drives", help="List available external drives and exit"
    ),
    device_name: Optional[str] = typer.Option(
        None,
        "--device-name",
        help="Custom device name for backup subfolder (default: auto-detected hostname)",
    ),
    list_devices: bool = typer.Option(
        False,
        "--list-devices",
        help="List devices with backups on the target drive and exit",
    ),
    no_manifest: bool = typer.Option(False, "--no-manifest", help="Disable manifest tracking"),
    manifest_format: Optional[str] = typer.Option(
        None,
        "--manifest-format",
        help="Manifest storage backend: json or sqlite (default: config manifest_format, else json)",
        metavar="FORMAT",
    ),
    show_manifest: bool = typer.Option(
        False, "--show-manifest", help="Display manifest contents and exit"
    ),
    verify: bool = typer.Option(False, "--verify", help="Verify backup against manifest and exit"),
    notify: bool = typer.Option(
        False,
        "--notify",
        help="Send a desktop notification when the backup finishes",
    ),
    compress: Optional[str] = typer.Option(
        None,
        "--compress",
        help="Compress backup into archive after copying (zip or tar.gz)",
        metavar="FORMAT",
    ),
    use_hash: bool = typer.Option(
        False,
        "--hash",
        help="Enable SHA-256 hashing for more accurate change detection (files up to 50MB)",
    ),
    hash_all: bool = typer.Option(
        False,
        "--hash-all",
        help="Hash all files regardless of size (implies --hash, slower for large files)",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "-v",
        "--version",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """SmartBackup - Intelligent Backup System for Developers."""
    # If a subcommand was invoked, do nothing here
    if ctx.invoked_subcommand is not None:
        return

    # --- flag-only actions (exit early) ---

    if list_drives:
        _list_available_drives()
        raise typer.Exit(code=0)

    if list_devices:
        if not target:
            logger = BackupLogger(verbose=True)
            logger.error("Please specify backup directory with --target")
            raise typer.Exit(code=1)
        _list_devices(target)
        raise typer.Exit(code=0)

    # Initialize logger
    logger = BackupLogger(verbose=not quiet)

    if show_manifest:
        if not target:
            logger.error("Please specify backup directory with --target")
            raise typer.Exit(code=1)
        _show_manifest(target, device=device_name)
        raise typer.Exit(code=0)

    if verify:
        if not target:
            logger.error("Please specify backup directory with --target")
            raise typer.Exit(code=1)
        code = _verify_manifest(target, device=device_name)
        raise typer.Exit(code=code)

    # --- Interactive Prompt Flow (--prompt) ---
    if prompt:
        # Determine drive info
        drive_path = target
        if drive_path is None:
            from smartbackup.platform.devices import DeviceDetector

            detector = DeviceDetector(logger)
            drive_path = detector.find_backup_device(required_space=100 * 1024 * 1024)

        if drive_path is None:
            logger.error("No backup medium found for prompt mode.")
            time.sleep(3)
            raise typer.Exit(code=1)

        # Retrieve disk capacity info
        try:
            total, used, free = shutil.disk_usage(drive_path)
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            space_info = f"{free_gb:.1f} GB free of {total_gb:.1f} GB"
        except Exception:
            space_info = "Available"

        source_display = source or PathResolver.get_documents_path()
        dev_name = device_name or get_device_name()

        banner_text = (
            f"[bold cyan]Detected External Backup Drive[/bold cyan]\n\n"
            f"[bold]Drive Path:[/bold]  [green]{drive_path}[/green]\n"
            f"[bold]Capacity:[/bold]    {space_info}\n"
            f"[bold]Source:[/bold]      {source_display}\n"
            f"[bold]Device ID:[/bold]   [yellow]{dev_name}[/yellow]"
        )

        console.print()
        console.print(
            Panel(
                banner_text,
                title="[bold green]SmartBackup Auto-Detect[/bold green]",
                border_style="green",
                expand=False,
            )
        )
        console.print()

        try:
            choice = Prompt.ask(
                "[bold]Start backup now?[/bold] ([bold green]Y[/bold green]es / [bold red]n[/bold red]o / [bold yellow]d[/bold yellow]ry-run)",
                default="y",
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Backup cancelled by user.[/yellow]")
            raise typer.Exit(code=0) from None

        if choice in ("n", "no"):
            console.print("[dim]Backup skipped by user.[/dim]")
            raise typer.Exit(code=0)
        elif choice in ("d", "dry-run", "dryrun"):
            dry_run = True
            logger.info("Executing backup in dry-run simulation mode...")
        elif choice in ("y", "yes", ""):
            dry_run = False
        else:
            console.print(f"[yellow]Unrecognized option '{choice}', proceeding with standard backup.[/yellow]")

    # --- Normal backup flow ---

    # Validate compression format if provided
    if compress:
        from smartbackup.core.compressor import SUPPORTED_FORMATS

        if compress not in SUPPORTED_FORMATS:
            logger.error(
                f"Unsupported compression format: {compress!r}. "
                f"Use one of: {', '.join(SUPPORTED_FORMATS)}"
            )
            raise typer.Exit(code=1)
        logger.info(f"Compression enabled: {compress}")

    # Log hash mode
    if hash_all:
        logger.info("SHA-256 hashing enabled for ALL files (--hash-all)")
    elif use_hash:
        logger.info("SHA-256 hashing enabled for files up to 50MB (--hash)")

    # Load config and add exclusions
    config_manager = ConfigManager()
    if exclude:
        for pat in exclude:
            config_manager.add_exclusion(pat)
            logger.info(f"Exclusion added: {pat}")

    # Effective exclusion set for this run: built-in defaults + persisted
    # custom patterns (get_exclusions() re-reads config, so patterns added
    # above are included immediately)
    merged_exclusions = config_manager.get_exclusions()
    logger.info(f"Exclusion patterns in effect: {len(merged_exclusions)}")

    # Get preferred target
    target_label = label or config_manager.get_preferred_target()

    # Resolve and validate manifest format (flag > config > "json")
    raw_manifest_format = (
        manifest_format if manifest_format is not None else config_manager.get_manifest_format()
    )
    resolved_manifest_format = raw_manifest_format.strip().lower()
    if resolved_manifest_format not in SUPPORTED_MANIFEST_FORMATS:
        logger.error(
            f"Unsupported manifest format: {raw_manifest_format!r}. "
            f"Choose from: {', '.join(SUPPORTED_MANIFEST_FORMATS)}"
        )
        raise typer.Exit(code=1)

    # --- Interactive Selective Folder Backup (--select) ---
    selected_folders: Optional[list[str]] = None
    selection_metadata: Optional[SelectionMetadata] = None
    if select:
        if not _is_interactive_tty():
            logger.error(
                "The --select option requires an interactive terminal (TTY). "
                "Run SmartBackup in an interactive shell or omit --select."
            )
            raise typer.Exit(code=1)

        resolved_source = source if source is not None else PathResolver.get_documents_path()
        if not resolved_source.exists() or not resolved_source.is_dir():
            logger.error(
                f"Source directory does not exist or is not a directory: {resolved_source}"
            )
            raise typer.Exit(code=1)

        # Best-effort lookup of previously backed-up top-level folders for UI badges
        previously_backed_up: set[str] = set()
        if target is not None:
            try:
                backup_root = target / "Documents-Backup"
                resolved_dev = device_name or get_device_name()
                candidate_dir = backup_root / resolved_dev
                if candidate_dir.exists():
                    existing_mgr = get_manifest_manager(candidate_dir)
                    existing_manifest = existing_mgr.load() if existing_mgr.exists() else None
                    if existing_manifest is not None:
                        for rel_path in existing_manifest.entries:
                            parts = Path(rel_path.replace("\\", "/")).parts
                            if len(parts) >= 2:
                                previously_backed_up.add(parts[0])
            except Exception:
                pass

        selector = FolderSelector(
            source_path=resolved_source,
            exclusion_filter=ExclusionFilter(merged_exclusions, EXCLUDED_EXTENSIONS),
            console=console,
            previously_backed_up=previously_backed_up,
        )
        selection_metadata = selector.select()
        if selection_metadata is None:
            console.print("[yellow]Selective backup cancelled.[/yellow]")
            raise typer.Exit(code=0)

        selected_folders = list(selection_metadata.selected_folders)
        logger.info(
            f"Selective mode (--select): {len(selected_folders)} folder(s) selected "
            f"({', '.join(selected_folders)})"
        )

    # Execute backup
    try:
        if dry_run:
            logger.warning("DRY-RUN MODE - No files will be copied!")

        backup = SmartBackup()
        backup.logger = logger

        if no_manifest:
            logger.info("Manifest tracking disabled")

        success = backup.run(
            custom_source=source,
            custom_target=target,
            target_label=target_label,
            use_manifest=not no_manifest,
            device_name=device_name,
            compress_format=compress,
            use_hash=use_hash or hash_all,
            hash_all=hash_all,
            dry_run=dry_run,
            exclusions=merged_exclusions,
            manifest_format=resolved_manifest_format,
            notify=notify,
            selected_folders=selected_folders,
            selection_metadata=selection_metadata,
        )

        if prompt:
            console.print("\n[dim]Window will close automatically in 5 seconds...[/dim]")
            time.sleep(5)

        raise typer.Exit(code=0 if success else 1)

    except typer.Exit:
        raise

    except (FileNotFoundError, OSError) as e:
        logger.error(f"Storage medium error (drive may have been disconnected): {e}")
        if prompt:
            time.sleep(3)
        raise typer.Exit(code=1) from e

    except KeyboardInterrupt:
        console.print("\n[yellow]Backup cancelled by user.[/yellow]")
        raise typer.Exit(code=130) from None

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        if prompt:
            time.sleep(5)
        raise typer.Exit(code=1) from e


# ---------------------------------------------------------------------------
# Config sub-command group
# ---------------------------------------------------------------------------

_CONFIG_KEYS = (
    "preferred_target",
    "device_name",
    "auto_watch_cooldown",
    "preferred_terminal",
    "manifest_format",
    "exclusions",
)


def _reject_unknown_config_key(key: str) -> None:
    console.print(
        f"[red]Unknown config key:[/red] {key}\n"
        f"[dim]Valid keys:[/dim] {', '.join(_CONFIG_KEYS)}"
    )
    raise typer.Exit(code=1)


@config_app.command("list")
def config_list_cmd() -> None:
    """Show the effective persistent configuration."""
    manager = ConfigManager()
    config = manager.load()

    table = Table(
        title="SMARTBACKUP CONFIGURATION",
        title_style="bold cyan",
        show_header=True,
        expand=False,
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key in _CONFIG_KEYS[:-1]:
        value = config.get(key)
        table.add_row(key, "(not set)" if value is None else str(value))

    exclusions = config.get("exclusions", [])
    table.add_row("exclusions", ", ".join(sorted(exclusions)) if exclusions else "(none)")

    console.print()
    console.print(table)
    console.print(f"[dim]Config file:[/dim] {manager.config_file}")
    raise typer.Exit(code=0)


@config_app.command("get")
def config_get_cmd(
    key: str = typer.Argument(..., help="Configuration key"),
) -> None:
    """Print one configuration value."""
    if key not in _CONFIG_KEYS:
        _reject_unknown_config_key(key)

    config = ConfigManager().load()

    if key == "exclusions":
        patterns = sorted(config.get("exclusions", []))
        console.print(", ".join(patterns) if patterns else "(none)")
        raise typer.Exit(code=0)

    value = config.get(key)
    console.print("(not set)" if value is None else str(value))
    raise typer.Exit(code=0)


@config_app.command("set")
def config_set_cmd(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="New value"),
) -> None:
    """Validate and persist one configuration value."""
    if key not in _CONFIG_KEYS:
        _reject_unknown_config_key(key)

    if key == "exclusions":
        console.print(
            "[red]Use `smartbackup config exclude|unexclude <pattern>` "
            "to manage exclusions.[/red]"
        )
        raise typer.Exit(code=1)

    manager = ConfigManager()

    if key == "auto_watch_cooldown":
        try:
            seconds = int(value)
        except ValueError:
            seconds = -1
        if seconds < 0:
            console.print(
                f"[red]Invalid value:[/red] {value!r} (expected an integer >= 0)"
            )
            raise typer.Exit(code=1)
        manager.set_auto_watch_cooldown(seconds)
        stored = str(seconds)
    elif key == "device_name":
        sanitized = sanitize_device_name(value)
        if sanitized == "unknown-device":
            console.print(
                "[red]Invalid value:[/red] device_name must contain at least "
                "one letter or digit"
            )
            raise typer.Exit(code=1)
        manager.set_device_name(sanitized)
        stored = sanitized
    elif key == "manifest_format":
        cleaned_fmt = value.strip().lower()
        if cleaned_fmt not in SUPPORTED_MANIFEST_FORMATS:
            console.print(
                f"[red]Invalid value:[/red] {value!r} "
                f"(choose from: {', '.join(SUPPORTED_MANIFEST_FORMATS)})"
            )
            raise typer.Exit(code=1)
        manager.set_manifest_format(cleaned_fmt)
        stored = cleaned_fmt
    else:  # preferred_target / preferred_terminal
        cleaned = value.strip()
        if not cleaned:
            console.print(f"[red]Invalid value:[/red] {key} must not be empty")
            raise typer.Exit(code=1)
        if key == "preferred_target":
            manager.set_preferred_target(cleaned)
        else:
            manager.set_preferred_terminal(cleaned)
        stored = cleaned

    console.print(f"[green]Set[/green] {key} = {stored}")
    console.print(f"[dim]Config file:[/dim] {manager.config_file}")
    raise typer.Exit(code=0)


@config_app.command("unset")
def config_unset_cmd(
    key: str = typer.Argument(..., help="Configuration key"),
) -> None:
    """Remove a configuration key so its default applies again."""
    if key not in _CONFIG_KEYS:
        _reject_unknown_config_key(key)

    manager = ConfigManager()
    manager.unset(key)
    console.print(f"[green]Unset[/green] {key}")
    raise typer.Exit(code=0)


@config_app.command("exclude")
def config_exclude_cmd(
    patterns: list[str] = typer.Argument(..., help="Glob patterns to add"),
) -> None:
    """Add one or more custom exclusion patterns."""
    manager = ConfigManager()
    for pattern in patterns:
        manager.add_exclusion(pattern)
    console.print(f"[green]Added {len(patterns)} exclusion(s).[/green]")
    raise typer.Exit(code=0)


@config_app.command("unexclude")
def config_unexclude_cmd(
    patterns: list[str] = typer.Argument(..., help="Glob patterns to remove"),
) -> None:
    """Remove one or more custom exclusion patterns."""
    manager = ConfigManager()
    for pattern in patterns:
        manager.remove_exclusion(pattern)
    console.print(f"[green]Removed {len(patterns)} exclusion(s).[/green]")
    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Main entry point of the program.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        result = app(standalone_mode=False)
        # typer.Exit(code=N) with standalone_mode=False returns N
        if isinstance(result, int):
            return result
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 1
    except KeyboardInterrupt:
        return 130
    except Exception:
        return 1
