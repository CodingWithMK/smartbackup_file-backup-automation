"""
CLI - Command line interface for SmartBackup.

Modernised with Typer and Rich for a polished developer experience.
"""

import shutil
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from smartbackup.backup import SmartBackup
from smartbackup.config import ConfigManager
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.platform.scheduler import SchedulerHelper
from smartbackup.platform.terminal import TerminalSpawner
from smartbackup.platform.watcher import DeviceWatcher
from smartbackup.ui.logger import BackupLogger

__version__ = "0.6.0"

console = Console(highlight=False)

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
    if (root / ".smartbackup_manifest.json").exists():
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
            manifest_path = item / ".smartbackup_manifest.json"
            if manifest_path.exists():
                manager = JsonManifestManager(item)
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

    manager = JsonManifestManager(target)
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
    table.add_row("Total Files", f"{manifest.total_files:,}")
    table.add_row("Total Size", f"{manifest.total_size / (1024 * 1024):.2f} MB")

    console.print()
    console.print(table)
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

    manager = JsonManifestManager(target)
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview restore without copying"),
    list_files: bool = typer.Option(False, "--list", help="List files in backup"),
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
        dry_run=dry_run,
        list_files=list_files,
        device_name=device_name,
    )


def _handle_restore(
    source: Path,
    target: Optional[Path],
    pattern: Optional[list[str]],
    overwrite: bool,
    dry_run: bool,
    list_files: bool,
    device_name: Optional[str],
) -> int:
    """Handle the restore subcommand (core logic)."""
    logger = BackupLogger(verbose=True)

    try:
        from smartbackup.core.restore import RestoreEngine
    except ImportError:
        logger.error("Restore functionality not yet available")
        logger.info("This feature will be implemented in the next version")
        raise typer.Exit(code=1)

    if list_files:
        # List files in backup
        logger.header("Files in Backup")
        root = source / "Documents-Backup"
        if not root.exists():
            logger.error(f"Backup directory not found: {root}")
            raise typer.Exit(code=1)

        resolved_target = _resolve_device_target(root, device_name)

        manager = JsonManifestManager(resolved_target)
        manifest = manager.load()
        if manifest is None:
            logger.warning("No manifest found, scanning directory...")
            for path in resolved_target.rglob("*"):
                if path.is_file():
                    console.print(f"  {path.relative_to(resolved_target)}")
        else:
            for entry in manifest.iter_entries():
                console.print(f"  {entry.relative_path} ({entry.size:,} bytes)")
        raise typer.Exit(code=0)

    # Perform restore
    resolved_device = device_name or ""
    try:
        restore_engine = RestoreEngine(
            backup_path=source,
            target_path=target,
            logger=logger,
            device_name=resolved_device,
        )

        if dry_run:
            logger.warning("DRY-RUN MODE - No files will be restored!")

        result = restore_engine.restore(
            patterns=pattern,
            overwrite=overwrite,
            dry_run=dry_run,
        )

        code = 0 if result.errors == 0 else 1
        raise typer.Exit(code=code)

    except typer.Exit:
        raise
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(code=1)


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
        raise typer.Exit(code=1)

    # Optionally remove the source directory
    if remove_source:
        logger.info(f"Removing uncompressed directory: {device_target}")
        try:
            shutil.rmtree(device_target)
            logger.success("Uncompressed backup directory removed")
        except Exception as e:
            logger.error(f"Failed to remove source directory: {e}")
            logger.warning("Archive was created successfully, but source was not removed")
            raise typer.Exit(code=1)

    raise typer.Exit(code=0)


# ---------------------------------------------------------------------------
# Watch & Daemon sub-commands
# ---------------------------------------------------------------------------


@app.command("watch", help="Watch for external backup storage media and trigger prompts")
def watch_cmd(
    interval: float = typer.Option(2.5, "-i", "--interval", help="Polling interval in seconds"),
    cooldown: int = typer.Option(300, "-c", "--cooldown", help="Cooldown in seconds between drive prompts"),
) -> None:
    """Run foreground drive watcher daemon."""
    _handle_watch(interval=interval, cooldown=cooldown)


def _handle_watch(interval: float = 2.5, cooldown: int = 300) -> None:
    """Foreground drive watcher logic."""
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
        raise typer.Exit(code=0)


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
    show_manifest: bool = typer.Option(
        False, "--show-manifest", help="Display manifest contents and exit"
    ),
    verify: bool = typer.Option(False, "--verify", help="Verify backup against manifest and exit"),
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
            raise typer.Exit(code=0)

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
        raise typer.Exit(code=1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Backup cancelled by user.[/yellow]")
        raise typer.Exit(code=130)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        if prompt:
            time.sleep(5)
        raise typer.Exit(code=1)


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
