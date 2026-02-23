"""
CLI - Command line interface for SmartBackup.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from smartbackup.backup import SmartBackup
from smartbackup.config import ConfigManager
from smartbackup.manifest.json_manifest import JsonManifestManager
from smartbackup.platform.identity import get_device_name
from smartbackup.platform.resolver import PathResolver
from smartbackup.ui.colors import Colors
from smartbackup.ui.logger import BackupLogger

__version__ = "0.3.0"


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


def _list_devices(backup_path: Path, backup_folder: str = "Documents-Backup") -> None:
    """List all device backup folders on the drive."""
    logger = BackupLogger(verbose=True)
    root = backup_path / backup_folder

    if not root.exists():
        logger.warning("No backup directory found!")
        return

    logger.header("Devices with Backups")

    devices_found = False
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith(("_", ".")):
            manifest_path = item / ".smartbackup_manifest.json"
            if manifest_path.exists():
                manager = JsonManifestManager(item)
                manifest = manager.load()
                if manifest:
                    print(f"  {item.name}")
                    print(f"    Files: {manifest.total_files:,}")
                    print(f"    Size:  {manifest.total_size / (1024**2):.1f} MB")
                    print(f"    Last:  {manifest.updated.strftime('%Y-%m-%d %H:%M')}")
                    print()
                    devices_found = True

    if not devices_found:
        logger.warning("No device backups found")


def _list_available_drives() -> None:
    """Display all available external drives."""
    logger = BackupLogger(verbose=True)
    logger.header("Available External Storage Media")

    drives = PathResolver.find_external_drives()

    if not drives:
        logger.warning("No external storage media found!")
        return

    print(f"\n{'-' * 70}")
    print(f"{'No.':<5}{'Label':<25}{'Path':<25}{'Free':<15}")
    print(f"{'-' * 70}")

    for i, (path, label, free) in enumerate(drives, 1):
        free_str = f"{free / (1024**3):.1f} GB"
        print(f"{i:<5}{label:<25}{str(path):<25}{free_str:<15}")

    print(f"{'-' * 70}\n")


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

    print(f"\n{'=' * 70}")
    print(f"MANIFEST INFORMATION")
    print(f"{'=' * 70}")
    print(f"  Version:       {manifest.version}")
    print(f"  Format:        {manifest.format.value}")
    print(f"  Source:        {manifest.source}")
    if hasattr(manifest, "hostname") and manifest.hostname:
        print(f"  Hostname:      {manifest.hostname}")
    print(f"  Created:       {manifest.created.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Updated:       {manifest.updated.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Backup Count:  {manifest.backup_count}")
    print(f"  Total Files:   {manifest.total_files:,}")
    print(f"  Total Size:    {manifest.total_size / (1024 * 1024):.2f} MB")
    print(f"{'=' * 70}\n")


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
    errors = manager.verify(manifest, target)

    if not errors:
        logger.success("All files verified successfully!")
        return 0
    else:
        logger.error(f"Found {len(errors)} verification errors:")
        for error in errors[:20]:  # Show first 20 errors
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        return 1


def main() -> int:
    """
    Main entry point of the program.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        prog="smartbackup",
        description="SmartBackup - Intelligent Backup System for Developers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  smartbackup                           # Backup Documents to external drive
  smartbackup --source ~/Projects       # Backup a specific folder
  smartbackup --target /media/usb       # Backup to specific drive
  smartbackup --label "BACKUP_USB"      # Find drive by label
  smartbackup --device-name "Work-PC"   # Use a custom device name
  smartbackup --list-devices -t /mnt    # List devices with backups
  smartbackup --dry-run                 # Simulate without copying
  smartbackup --list-drives             # Show available drives
  smartbackup --show-manifest           # Display manifest contents
  smartbackup --verify                  # Verify backup against manifest
  smartbackup restore --source /backup  # Restore from backup
        """,
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Restore subcommand
    restore_parser = subparsers.add_parser("restore", help="Restore files from backup")
    restore_parser.add_argument(
        "-s", "--source", type=Path, required=True, help="Backup source directory"
    )
    restore_parser.add_argument("-t", "--target", type=Path, help="Target directory to restore to")
    restore_parser.add_argument(
        "-p", "--pattern", type=str, nargs="+", help="Glob patterns to filter files"
    )
    restore_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    restore_parser.add_argument(
        "--dry-run", action="store_true", help="Preview restore without copying"
    )
    restore_parser.add_argument(
        "--list", action="store_true", dest="list_files", help="List files in backup"
    )
    restore_parser.add_argument(
        "--device-name",
        type=str,
        help="Device name to restore from (default: auto-detected hostname)",
    )

    # Main backup arguments
    parser.add_argument(
        "-s", "--source", type=Path, help="Source directory (default: Documents folder)"
    )

    parser.add_argument(
        "-t",
        "--target",
        type=Path,
        help="Target directory/drive (default: auto-detect external drive)",
    )

    parser.add_argument("-l", "--label", type=str, help="Preferred target drive label")

    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate backup without copying files"
    )

    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")

    parser.add_argument("--exclude", type=str, nargs="+", help="Additional exclusion patterns")

    parser.add_argument(
        "--list-drives", action="store_true", help="List available external drives and exit"
    )

    # Device options
    parser.add_argument(
        "--device-name",
        type=str,
        help="Custom device name for backup subfolder (default: auto-detected hostname)",
    )

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List devices with backups on the target drive and exit",
    )

    # Manifest options
    parser.add_argument("--no-manifest", action="store_true", help="Disable manifest tracking")

    parser.add_argument(
        "--show-manifest", action="store_true", help="Display manifest contents and exit"
    )

    parser.add_argument(
        "--verify", action="store_true", help="Verify backup against manifest and exit"
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # Handle restore command
    if args.command == "restore":
        return _handle_restore(args)

    # List drives only
    if args.list_drives:
        _list_available_drives()
        return 0

    # List devices on target
    if args.list_devices:
        if not args.target:
            logger = BackupLogger(verbose=True)
            logger.error("Please specify backup directory with --target")
            return 1
        _list_devices(args.target)
        return 0

    # Initialize logger
    logger = BackupLogger(verbose=not args.quiet)

    # Show manifest
    if args.show_manifest:
        if not args.target:
            logger.error("Please specify backup directory with --target")
            return 1
        _show_manifest(args.target, device=args.device_name)
        return 0

    # Verify manifest
    if args.verify:
        if not args.target:
            logger.error("Please specify backup directory with --target")
            return 1
        return _verify_manifest(args.target, device=args.device_name)

    # Load config and add exclusions
    config_manager = ConfigManager()
    if args.exclude:
        for pattern in args.exclude:
            config_manager.add_exclusion(pattern)
            logger.info(f"Exclusion added: {pattern}")

    # Get preferred target
    target_label = args.label or config_manager.get_preferred_target()

    # Execute backup
    try:
        if args.dry_run:
            logger.warning("DRY-RUN MODE - No files will be copied!")

        backup = SmartBackup()
        backup.logger = logger

        # Set manifest option
        if args.no_manifest:
            logger.info("Manifest tracking disabled")

        success = backup.run(
            custom_source=args.source,
            custom_target=args.target,
            target_label=target_label,
            use_manifest=not args.no_manifest,
            device_name=args.device_name,
        )

        return 0 if success else 1

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Backup cancelled by user.{Colors.END}")
        return 130

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _handle_restore(args: argparse.Namespace) -> int:
    """Handle the restore subcommand."""
    logger = BackupLogger(verbose=True)

    # Import here to avoid circular imports
    try:
        from smartbackup.core.restore import RestoreEngine
    except ImportError:
        logger.error("Restore functionality not yet available")
        logger.info("This feature will be implemented in the next version")
        return 1

    if args.list_files:
        # List files in backup
        logger.header("Files in Backup")
        root = args.source / "Documents-Backup"
        if not root.exists():
            logger.error(f"Backup directory not found: {root}")
            return 1

        device = getattr(args, "device_name", None)
        target = _resolve_device_target(root, device)

        manager = JsonManifestManager(target)
        manifest = manager.load()
        if manifest is None:
            logger.warning("No manifest found, scanning directory...")
            # Fall back to directory scan
            for path in target.rglob("*"):
                if path.is_file():
                    print(f"  {path.relative_to(target)}")
        else:
            for entry in manifest.iter_entries():
                print(f"  {entry.relative_path} ({entry.size:,} bytes)")
        return 0

    # Perform restore
    device_name = getattr(args, "device_name", None) or ""
    try:
        restore_engine = RestoreEngine(
            backup_path=args.source,
            target_path=args.target,
            logger=logger,
            device_name=device_name,
        )

        if args.dry_run:
            logger.warning("DRY-RUN MODE - No files will be restored!")

        result = restore_engine.restore(
            patterns=args.pattern,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )

        return 0 if result.errors == 0 else 1

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
