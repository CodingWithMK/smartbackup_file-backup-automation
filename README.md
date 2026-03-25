<div align="center">

# 🔄 SmartBackup

**Intelligent Backup System for Developers**

Automatically backup your important files while skipping `node_modules`, virtual environments, and other build artifacts.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/CodingWithMK/smartbackup_file-backup-automation/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](/)

[Features](#-features) •
[Quick Start](#-quick-start) •
[Installation](#-installation) •
[Usage](#-usage) •
[Configuration](#%EF%B8%8F-configuration) •
[Contributing](#-contributing)

</div>

---

## 🤔 Why SmartBackup?

Ever tried to backup your Documents folder only to wait hours because of massive `node_modules` folders or Python virtual environments?

**SmartBackup solves this.** It automatically detects and skips development artifacts, making your backups:

- ⚡ **10x faster** - Skip gigabytes of dependencies
- 💾 **10x smaller** - Only backup what matters
- 🧠 **Smart** - Incremental backups copy only changed files
- 🔌 **Zero config** - Works out of the box

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **Cross-Platform** | Works on Windows, macOS, and Linux |
| 🔍 **Smart Filtering** | Auto-skips `node_modules`, `venv`, `.git`, `__pycache__`, etc. |
| 📊 **Incremental Backup** | Only copies new or modified files |
| 📋 **Manifest Tracking** | JSON manifest for 10x faster incremental backups |
| 🔄 **Restore Support** | Full restore functionality with pattern filtering |
| 💻 **Multi-Device** | Per-device backup folders — multiple machines share one drive safely |
| 🔌 **Auto-Detection** | Automatically finds external drives |
| 📝 **Detailed Logging** | Progress bar + log file on backup drive |
| 🎯 **Minimal Dependencies** | Only requires few dependencies for CLI |
| ⚙️ **Configurable** | Add custom exclusions as needed |

---

## 🚀 Quick Start

### For Regular Users (No Installation)

**Just download and run!**

1. **Download** the latest release or clone this repository
2. **Connect** your external drive
3. **Run** the backup:

```bash
python main.py
```

That's it! Your Documents folder will be backed up to the external drive.

---

## 📦 Installation

### Option 1: Direct Download (Easiest)

```bash
# Clone the repository
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

# Run directly
python main.py
```

### Option 2: Install with pip

```bash
# Clone and install
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

pip install .

# Now you can run from anywhere
smartbackup
```

### Option 3: Install with uv (Recommended for Developers)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Run
python main.py
# or
smartbackup
```

---

## 📖 Usage

### Basic Usage

```bash
# Backup Documents folder to auto-detected external drive
python main.py

# Or if installed
smartbackup
```

### Common Options

```bash
# Backup a specific folder
python main.py --source ~/Projects

# Backup to a specific drive
python main.py --target /media/USB_DRIVE

# Find drive by name
python main.py --label "My Backup Drive"

# Use a custom device name (default: auto-detected hostname)
python main.py --device-name "Work Laptop"

# List devices with backups on the target drive
python main.py --list-devices --target /media/USB_DRIVE

# See what would be backed up (without copying)
python main.py --dry-run

# List available drives
python main.py --list-drives

# Quiet mode (less output)
python main.py --quiet

# Add extra folders to skip
python main.py --exclude "downloads" "*.iso"
```

### All Options

```
usage: smartbackup [-h] [-s SOURCE] [-t TARGET] [-l LABEL] [--dry-run]
                   [-q] [--exclude PATTERN [PATTERN ...]] [--list-drives]
                   [--no-manifest] [--show-manifest] [--verify]
                   [--device-name NAME] [--list-devices] [-v]
                   {restore} ...

Options:
  -h, --help            Show this help message
  -s, --source PATH     Source directory (default: Documents)
  -t, --target PATH     Target drive/directory
  -l, --label NAME      Find drive by label name
  --dry-run             Simulate without copying
  -q, --quiet           Minimal output
  --exclude PATTERN     Additional exclusion patterns
  --list-drives         Show available drives
  --no-manifest         Disable manifest tracking
  --show-manifest       Display manifest contents
  --verify              Verify backup against manifest
  --device-name NAME    Custom device name (default: auto-detected hostname)
  --list-devices        List devices with backups on the target drive
  -v, --version         Show version

Commands:
  restore               Restore files from backup
```

### Restore Files from Backup

```bash
# Restore all files to original location
smartbackup restore --source /path/to/backup

# Restore to a specific directory
smartbackup restore --source /path/to/backup --target ~/Restored

# Restore from a specific device's backup
smartbackup restore --source /path/to/backup --device-name "Office-Desktop"

# Restore only specific files (pattern matching)
smartbackup restore --source /path/to/backup --pattern "*.py" "*.md"

# Preview what would be restored (dry-run)
smartbackup restore --source /path/to/backup --dry-run

# List files in backup
smartbackup restore --source /path/to/backup --list

# Overwrite existing files
smartbackup restore --source /path/to/backup --overwrite
```

### Manifest Commands

```bash
# Show manifest information
smartbackup --target /path/to/backup --show-manifest

# Verify backup integrity against manifest
smartbackup --target /path/to/backup --verify

# Disable manifest tracking (use traditional change detection)
smartbackup --no-manifest
```

---

## 📋 Example Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    Intelligent Backup System v0.4.0                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

ℹ  [2024-01-15 09:30:22] Source directory: /Users/dev/Documents
ℹ  [2024-01-15 09:30:22] Operating system: Darwin 23.1.0
ℹ  [2024-01-15 09:30:22] Device identifier: Musabs-MacBook-Pro

▶ Searching for external storage medium...
✓  [2024-01-15 09:30:22] External medium found: BACKUP_USB (/Volumes/BACKUP_USB) - 234.5 GB free

▶ Scanning source directory: /Users/dev/Documents
ℹ  [2024-01-15 09:30:45] Scan completed: 1,523 files found, 8,492 excluded

▶ Analyzing changes...
ℹ  [2024-01-15 09:30:47] Analysis completed: 12 new, 34 modified, 0 to delete

▶ Starting backup operation...
➕ [COPIED] Projects/app/main.py (2.3 KB)
🔄 [UPDATED] Documents/report.docx (156.2 KB)
[██████████████████████████████] 100.0% (46/46) | 12.4MB/12.4MB

╔══════════════════════════════════════════════════════════════════════════════╗
║                           BACKUP SUMMARY                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ✓ Copied Files:              12                                              ║
║  ✓ Updated Files:             34                                              ║
║  ○ Skipped Files:          1,477                                              ║
║  ✗ Errors:                     0                                              ║
║                                                                               ║
║  Duration:               00:00:23                                             ║
║  Speed:                  0.54 MB/s                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

✓  Backup completed successfully!
```

---

## 🚫 What Gets Excluded

SmartBackup automatically skips these folders and files:

<details>
<summary><b>Click to see full exclusion list</b></summary>

### JavaScript / Node.js
- `node_modules`
- `.npm`, `.yarn`
- `dist`, `build`
- `.next`, `.nuxt`

### Python
- `venv`, `.venv`, `env`
- `__pycache__`
- `.pytest_cache`, `.mypy_cache`
- `*.pyc`, `*.pyo`

### Version Control
- `.git`
- `.svn`
- `.hg`

### IDEs & Editors
- `.idea` (JetBrains)
- `.vscode`
- `*.swp`, `*.swo` (Vim)

### Build Artifacts
- `target` (Java/Rust)
- `bin`, `obj` (.NET)
- `.gradle`

### Operating System
- `.DS_Store` (macOS)
- `Thumbs.db` (Windows)
- `desktop.ini`

### Temporary Files
- `*.tmp`, `*.temp`
- `*.log`
- `*.bak`
- `cache`, `.cache`

</details>

---

## ⚙️ Configuration

### Add Custom Exclusions

**Command line:**
```bash
python main.py --exclude "my_folder" "*.iso" "downloads"
```

**Permanent exclusions** are saved in:
- Windows: `%APPDATA%\SmartBackup\config.json`
- macOS/Linux: `~/.config/smartbackup/config.json`

### Backup Location

Files are backed up to a per-device subfolder based on your system hostname:
```
YOUR_EXTERNAL_DRIVE/
└── Documents-Backup/
    ├── Musabs-MacBook-Pro/              # Auto-detected from hostname
    │   ├── .smartbackup_manifest.json
    │   ├── _backup_logs/
    │   │   └── backup_20240115_093022.log
    │   ├── Your files and folders...
    │   └── ...
    │
    └── Office-Desktop/                  # Another device's backup
        ├── .smartbackup_manifest.json
        ├── _backup_logs/
        │   └── backup_20240114_180500.log
        └── ...
```

Multiple devices can back up to the same drive without conflicts. Each device's backup is isolated in its own subfolder.

If you have an existing backup from a previous version (files directly in `Documents-Backup/`), SmartBackup will automatically migrate it into a device subfolder on the next run.

---

## 🛡️ No External Drive?

If no external drive is found, SmartBackup offers options:

```
╔════════════════════════════════════════════════════════════════╗
║  ⚠  EXTERNAL STORAGE MEDIUM NOT FOUND                         ║
╠════════════════════════════════════════════════════════════════╣
║  Please make sure that:                                        ║
║  • The external medium is connected                            ║
║  • The medium is recognized by the system                      ║
╚════════════════════════════════════════════════════════════════╝

Options:
  [1] Create local temporary backup
  [2] Wait and try again
  [3] Cancel
```

---

## 🧪 For Developers

### Setup Development Environment

```bash
# Clone
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .
```

### Project Structure

```
smartbackup_file-backup-automation/
├── src/
│   └── smartbackup/
│       ├── __init__.py       # Package exports
│       ├── __main__.py       # python -m smartbackup
│       ├── backup.py         # SmartBackup main class
│       ├── cli.py            # CLI argument parsing
│       ├── config.py         # Configuration management
│       ├── handlers.py       # Fallback handlers
│       ├── models.py         # Data classes
│       ├── core/
│       │   ├── engine.py     # Backup engine
│       │   ├── scanner.py    # File scanner
│       │   ├── detector.py   # Change detection
│       │   └── restore.py    # Restore engine
│       ├── manifest/
│       │   ├── base.py       # Manifest classes
│       │   └── json_manifest.py  # JSON implementation
│       ├── platform/
│       │   ├── resolver.py   # Path resolution
│       │   ├── devices.py    # Device detection
│       │   ├── identity.py   # Device identification (hostname)
│       │   └── scheduler.py  # OS scheduler helpers
│       └── ui/
│           ├── colors.py     # Terminal colors
│           └── logger.py     # Logging
├── tests/                    # 194 tests
├── main.py                   # Quick entry point
├── pyproject.toml
└── README.md
```

### Run from Source

```bash
# These all work:
python main.py
python -m smartbackup
smartbackup  # if installed
```

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with ❤️ for developers who are tired of backing up `node_modules`
- Inspired by the frustration of slow backups

---

<div align="center">

**If this tool saved you time, consider giving it a ⭐**

[Report Bug](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues) •
[Request Feature](https://github.com/CodingWithMK/smartbackup_file-backup-automation/issues)

</div>
```