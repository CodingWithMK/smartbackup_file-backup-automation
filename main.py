#!/usr/bin/env python3
"""
SmartBackup - Quick Entry Point

Run this file directly to start a backup with default settings.
For more options, use: python main.py --help

Examples:
    python main.py                          # Backup Documents to external drive
    python main.py --source ~/Projects      # Backup specific folder
    python main.py --target /media/usb      # Backup to specific drive
    python main.py --list-drives            # Show available drives
    python main.py --dry-run                # Simulate without copying
"""

import sys
from pathlib import Path

# Ensure the package can be imported when running from repo root
src_path = Path(__file__).parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from smartbackup import main as run_backup

if __name__ == "__main__":
    sys.exit(run_backup())