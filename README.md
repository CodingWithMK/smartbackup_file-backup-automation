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
[📖 User Guide](docs/USER_GUIDE.md) •
[Contributing](#-contributing)

</div>

---

> # 📖 **Full documentation: [SmartBackup User Guide](docs/USER_GUIDE.md)**
> Installation (pip / uv / dev), **every CLI command and flag**, incremental manifests,
> auto-detect watcher & background daemon, restore & recovery, configuration, and
> cross-platform troubleshooting — all in one place.

---

## 🤔 Why SmartBackup?

Ever tried to backup your Documents folder only to wait hours because of massive `node_modules`
folders or Python virtual environments?

**SmartBackup solves this.** It automatically detects and skips development artifacts, making
your backups:

- ⚡ **10x faster** — skip gigabytes of dependencies
- 💾 **10x smaller** — only back up what matters
- 🧠 **Smart** — incremental, manifest-based backups copy only changed files
- 💻 **Multi-device** — several machines share one drive safely (per-hostname folders)
- 🔌 **Zero config** — works out of the box on Windows, macOS, and Linux

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **Cross-Platform** | Works on Windows, macOS, and Linux |
| 🔍 **Smart Filtering** | Auto-skips `node_modules`, `venv`, `.git`, `__pycache__`, build outputs, caches |
| 📊 **Incremental Backup** | JSON or SQLite manifest (`--manifest-format json\|sqlite`) with auto-detection & seamless migration |
| 🔐 **SHA-256 Hashing** | Optional tiered hashing (`--hash` ≤ 50 MB, `--hash-all` for everything) |
| 🔄 **Restore Support** | Conflict strategies (`skip`, `overwrite`, `newer`, `rename`), pattern filtering, `--manifest-info`, dry-run preview |
| 💻 **Multi-Device** | Per-device backup folders — multiple machines share one drive |
| 📦 **Compression** | `zip` / `tar.gz` — during backup or afterwards via `compress` |
| 🔌 **Auto-Detection** | Finds external drives; optional watcher daemon prompts on plug-in |
| ⚙️ **Config CLI** | Manage persistent settings & exclusions via `smartbackup config` (no manual JSON edits) |
| 🔔 **Desktop Notifications** | Opt-in completion alerts (`--notify`) via `osascript`, `notify-send`, or PowerShell |
| 🗓️ **Scheduling Helper** | Print OS-specific `schtasks`, `launchd`, `cron`, and `systemd` recipes via `smartbackup schedule` |
| 📝 **Detailed Logging** | Persistent single-bar Rich progress display + per-run log file on the backup drive |
| 🎯 **Minimal Dependencies** | Only `rich` + `typer` — everything else is stdlib |

---

## 🚀 Quick Start

### Option 1 — One-Line Standalone Install (No Python Required)

Install the standalone prebuilt binary directly from [GitHub Releases](https://github.com/CodingWithMK/smartbackup_file-backup-automation/releases) on a fresh machine — no Python, `pip`, or `uv` needed:

**macOS & Linux (`curl`):**
```bash
curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

<details>
<summary>Pin a specific release version</summary>

```bash
# macOS / Linux
SMARTBACKUP_VERSION=v0.8.0 curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
```

```powershell
# Windows (PowerShell)
$env:SMARTBACKUP_VERSION = "v0.8.0"; irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
```

</details>

---

### Option 2 — Run from Source / Python (Developers)

**Requirements:** Python 3.9+ · Windows / macOS / Linux

#### Run directly (no installation)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # backs up Documents → auto-detected external drive
```

#### Install with pip

```bash
pip install .
smartbackup
```

#### Install with uv (recommended for developers)

```bash
uv venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"
smartbackup
```

**That's it!** Connect a drive and run — SmartBackup finds it, skips build artifacts, and
copies only what changed since the last run. If no drive is found, you'll be offered a local
temporary backup instead.

```bash
smartbackup --version     # verify: smartbackup 0.8.0
smartbackup --help        # all commands and options
```

---

## 💡 Common Commands

```bash
smartbackup                                   # backup Documents to the auto-detected drive
smartbackup --source ~/Projects               # back up a custom folder
smartbackup --target /media/USB_DRIVE         # back up to an explicit path
smartbackup --dry-run                         # simulate a backup (no copies, no manifest writes)
smartbackup --manifest-format sqlite          # store manifest in SQLite (.smartbackup_manifest.db)
smartbackup --notify                          # send an OS desktop notification when done
smartbackup --list-drives                     # show available drives
smartbackup --hash                            # SHA-256 change detection (files ≤ 50 MB)
smartbackup --target /media/USB --verify      # verify backup integrity against the manifest
smartbackup --compress zip                    # backup, then archive as zip

smartbackup restore --source /media/USB_DRIVE --list                  # inspect a backup
smartbackup restore --source /media/USB_DRIVE --manifest-info         # show manifest summary
smartbackup restore --source /media/USB_DRIVE --conflict rename       # keep both on conflict

smartbackup config list                       # inspect persistent configuration
smartbackup config set manifest_format sqlite # persist SQLite as default manifest format

smartbackup watch                             # foreground drive watcher
smartbackup daemon install                    # background watcher service (status/uninstall/clear-state)
smartbackup schedule --hours 24               # print OS-specific scheduled backup instructions
```

Full explanations, options, and recipes: **[User Guide →](docs/USER_GUIDE.md)**

<details>
<summary><b>What gets excluded by default?</b></summary>

`node_modules`, `venv`/`.venv`/`.env`, `__pycache__`, `.git`/`.svn`/`.hg`, `dist`/`build`,
`target`, `bin`/`obj`, `.idea`/`.vscode`, `.next`/`.nuxt`, `.gradle`/`.m2`, caches
(`.cache`, `.pytest_cache`, `.mypy_cache`, `.sass-cache`), temp files (`*.tmp`, `*.log`,
`*.bak`, `~*`), binaries (`*.pyc`, `*.exe`, `*.dll`, `*.so`, `*.dylib`, …), OS junk
(`.DS_Store`, `Thumbs.db`, `desktop.ini`) — plus anything that *looks like* a Python
virtual environment.

Full list: [User Guide → Appendix B](docs/USER_GUIDE.md#b-default-exclusions)

</details>

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest` · Lint: `ruff check .`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for details and [CHANGELOG.md](docs/CHANGELOG.md) for release history.

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
