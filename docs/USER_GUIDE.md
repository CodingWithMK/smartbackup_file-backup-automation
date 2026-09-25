# SmartBackup User Guide

**Version tested against: `smartbackup 0.6.1`** · Platforms: Windows · macOS · Linux · Python 3.9+

This guide is the single source of truth for using SmartBackup. Every command, flag, default
value, file path, and behavior documented here was taken from (or verified against) the
project source code.

---

## Table of Contents

1. [Overview & Philosophy](#1-overview--philosophy)
2. [Installation & Prerequisites](#2-installation--prerequisites)
3. [Core Concepts](#3-core-concepts)
4. [CLI Command Reference & Everyday Recipes](#4-cli-command-reference--everyday-recipes)
5. [Auto-Detect Daemon & Watcher Guide](#5-auto-detect-daemon--watcher-guide)
6. [Data Recovery & Restore Guide](#6-data-recovery--restore-guide)
7. [Configuration & Custom Exclusions](#7-configuration--custom-exclusions)
8. [Platform Nuances & Troubleshooting](#8-platform-nuances--troubleshooting)
9. [Appendix](#9-appendix)

---

## 1. Overview & Philosophy

**SmartBackup** backs up developer working data (by default, your `Documents` folder) to an
external drive while automatically skipping development artifacts such as `node_modules`,
virtual environments, build outputs, version-control metadata, and caches.

### Core highlights

| Highlight | What it means in practice |
|---|---|
| **Smart filtering** | A four-tier exclusion engine (exact names, file extensions, glob patterns, virtual-env structure detection) skips gigabytes of regenerable artifacts before they are ever copied. |
| **Zero/minimal dependencies** | The runtime requires only [`rich`](https://github.com/Textualize/rich) and [`typer`](https://github.com/tiangolo/typer). Compression, hashing, manifests, and restore all use the Python standard library — no external binaries. |
| **Manifest change detection** | A JSON manifest (`.smartbackup_manifest.json`) stored *on the backup drive* records every file's size, mtime, and optional SHA-256 hash, so later runs copy only new/changed files and remove files you deleted from the source. |
| **Hostname device isolation** | Each machine backs up into `Documents-Backup/<hostname>/`, so several computers can safely share one external drive without overwriting each other. |
| **Cross-platform, zero-config** | Windows, macOS, and Linux are all supported with automatic Documents-folder resolution, external-drive detection, and native terminal/OS integration. |

### What SmartBackup is *not*

- **Not an archive/versioning system.** Deletions in your source **propagate to the backup**
  (it mirrors the source). It keeps no old versions of changed files.
- **Not encrypted.** There is no encryption support today (it is on the roadmap).
- **Not a deduplicating/remote backup tool.** No SSH, no cloud backends, no block-level
  dedup, no retention policies.

Use SmartBackup for fast, local, "copy my working files to a USB stick" backups. Use
something else (or add SmartBackup alongside it) for point-in-time disaster recovery.

### Requirements

- Python **3.9 or newer** (`requires-python = ">=3.9"`)
- A writable destination: external drive, USB stick, or any directory you choose
- ~100 MB free space on the target (minimum enforced by the auto-detector)

---

## 2. Installation & Prerequisites

All examples in this guide use the `smartbackup` command. If you don't install the package,
every example also works verbatim via `python main.py` (from the repo root) or
`python -m smartbackup`.

### Option 1 — Run directly (no installation)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

python main.py            # backups work with no install step at all
```

`main.py` adds `src/` to `sys.path` automatically, so no installation is required.

### Option 2 — Install with pip

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

pip install .             # regular install → provides the `smartbackup` command
```

Editable (development) install:

```bash
pip install -e ".[dev]"   # -e = live-editable, [dev] adds pytest, pytest-cov, ruff
```

### Option 3 — Install with uv (recommended for developers)

```bash
git clone https://github.com/CodingWithMK/smartbackup_file-backup-automation.git
cd smartbackup_file-backup-automation

uv venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
                                   # Windows (CMD):        .venv\Scripts\activate.bat
uv pip install -e ".[dev]"
```

### Verify the installation

```bash
smartbackup --version
# smartbackup 0.6.1

smartbackup --help          # full option list (shown for every command/subcommand too)
```

### Uninstall / upgrade

```bash
pip uninstall smartbackup
pip install . --upgrade      # from a fresh clone, to upgrade
```

### Entry points summary

| Entry point | Needs install? | Notes |
|---|---|---|
| `smartbackup` | Yes (`pip install .`) | Console script defined as `smartbackup = smartbackup:main` |
| `python -m smartbackup` | Yes (package importable) | Same code path as the console script |
| `python main.py` | No | Repo-root convenience runner; adds `src/` to `sys.path` |

---

## 3. Core Concepts

### 3.1 Incremental Manifest Tracking

After every backup run, SmartBackup writes a manifest to the backup drive:

```
<backup>/Documents-Backup/<Device>/.smartbackup_manifest.json
```

The manifest records, per file: `hash` (SHA-256, optional), `size`, `mtime`,
`permissions`, `backed_up_at` — plus header metadata: `source` (original path),
`hostname`, `hash_algorithm`, `backup_count`, `total_files`, `total_size`,
`created`, `updated`.

**How a run decides what to copy:**

1. Scan the source tree, applying exclusions (see [3.5](#35-what-gets-excluded)).
2. Compare each source file against its manifest entry, in order:
   - **size** differs → modified
   - **mtime** differs → modified
   - both sides have a **hash** and they differ → modified
   - not in the manifest → new
   - manifest entry with no source counterpart → **deleted** (removed from the backup)
3. Copy new files, update modified files, delete obsolete files (multithreaded, up to
   `min(8, CPU count)` workers).
4. Rewrite the manifest atomically (temp file + rename, so a power cut can't corrupt it).

**Key implications:**

- **Deletions mirror to the backup.** Deleting a file locally means the next backup deletes
  it from the drive too. This is by design — SmartBackup mirrors your working set.
- **The manifest lives on the target**, so incremental state survives reinstalling SmartBackup.
- **`--no-manifest`** disables manifest tracking and falls back to a traditional
  source-vs-backup comparison (`ChangeDetector`: size + mtime, plus hash when `--hash` is on).
- **Corrupt/missing manifest** is non-fatal: a warning is printed and the run rebuilds it
  (a rebuilt manifest treats every file as new, so the next run re-copies everything — safe,
  just slower).

**Dry-run is read-only with respect to backup state.** `--dry-run` simulates the scan and
diff, prints what *would* happen, and writes the run log — but it never creates or updates
`.smartbackup_manifest.json`, never migrates a legacy folder layout, and never creates a
compression archive. You can safely run a dry-run immediately before a real backup: the
real run still sees every pending change and copies it.

### 3.2 Automatic External Drive Detection

When you don't pass `--target`, SmartBackup enumerates candidate drives per platform:

| OS | Method | What is enumerated |
|---|---|---|
| **Windows** | Win32 `GetLogicalDrives` + `GetDriveTypeW` | Drive letters **D:**–**Z:** of type *Removable* or *Fixed* that exist (fallback: plain letter probing) |
| **macOS** | `/Volumes` scan | Every mounted volume except `Macintosh HD`, `Macintosh HD - Data`, `Macbook`, `Macbook - Data`, hidden `.…` volumes (incl. `.timemachine`) |
| **Linux** | Mount-point scan | `/media/$USER`, `/run/media/$USER`, `/mnt` subdirectories |

Selection rules (`DeviceDetector.find_backup_device`):

1. Drives with **less than 100 MB free** are discarded.
2. If `--label` (or `preferred_target` in config) matches a drive label — case-insensitive —
   that drive wins immediately.
3. If exactly one candidate remains, it is used.
4. If several remain, they are listed and the **first one is picked automatically**.
   Use `--label` or `--target` to pin a specific drive.

> **Caution:** on Windows and Linux, *Fixed* disks (secondary internal disks) are eligible.
> If more than one drive is connected, always pin the destination with `--target PATH`
> or `--label NAME` (or set `preferred_target` in your config).

**When no drive is found**, SmartBackup offers:

```
Options:
  [1] Create local temporary backup   → writes to ~/.local_backup_temp
  [2] Wait and try again              → press Enter after connecting the drive (retries up to 3 times)
  [3] Cancel                          → exit without backup
```

List what's currently available:

```bash
smartbackup --list-drives
# table: No. | Label | Path | Free
```

### 3.3 Multi-Device Support (Hostname Isolation)

The device folder name is derived from `platform.node()`:

1. Strip any domain suffix (`.local` from macOS mDNS, corporate FQDNs).
2. Replace anything that isn't alphanumeric/`-`/`_` with `-`, collapse repeats, trim ends.
3. Fall back to `unknown-device` if nothing remains.

Example: `Musabs-MacBook-Pro.local` → `Musabs-MacBook-Pro`.

```
YOUR_EXTERNAL_DRIVE/
└── Documents-Backup/
    ├── Musabs-MacBook-Pro/          ← this machine (hostname-based)
    │   ├── .smartbackup_manifest.json
    │   ├── _backup_logs/
    │   │   └── backup_20260924_093022.log
    │   └── ... your files ...
    ├── Office-Desktop/              ← another machine sharing the same drive
    │   └── ...
    └── Musabs-MacBook-Pro_20260228_093022.zip   ← archives live here (see §4)
```

- **Override the name** for a run with `--device-name "Work-Laptop"`.
- **Legacy flat layouts** (files sitting directly in `Documents-Backup/`) are migrated
  automatically into `Documents-Backup/<hostname>/` on the next backup run.
- **See what's on a drive:** `smartbackup --list-devices --target /path/to/drive`
  (table: Device | Files | Size | Last Backup).

### 3.4 Backup On-Disk Layout

```
<target>/
└── Documents-Backup/                     # fixed folder name (internal option --backup-folder)
    ├── <Device>/                         # one folder per machine
    │   ├── .smartbackup_manifest.json    # incremental state (atomic writes)
    │   ├── _backup_logs/                 # one log per run
    │   │   └── backup_YYYYMMDD_HHMMSS.log
    │   └── <mirrored source tree>
    ├── <Device>_YYYYMMDD_HHMMSS.zip      # optional archives (created by --compress / `compress`)
    └── <Device>_YYYYMMDD_HHMMSS.tar.gz
```

Every run writes a log file containing the configuration, a summary (files/size/duration/
speed), and a per-file action list (`[COPIED]`, `[UPDATED]`, `[SKIPPED]`, `[DELETED]`,
`[ERROR]`).

### 3.5 What Gets Excluded

Four tiers are checked for every scanned entry (first match wins), matched against the
**file/folder name** (case-insensitive):

1. **Exact name match** — e.g. `node_modules`, `.git`, `venv`, `__pycache__`, `dist`, …
2. **Excluded extension** — `.pyc .pyo .pyd .class .o .obj .exe .dll .so .dylib .log .tmp .temp`
3. **Glob pattern** — entries containing `*`/`?` are converted to regexes:
   `*.egg-info`, `*.swp`, `*.swo`, `*.tmp`, `*.temp`, `*.log`, `*.bak`, `~*`
4. **Virtual-environment structure detection** — a directory containing `pyvenv.cfg`,
   `Scripts/activate`, `bin/activate`, `Scripts/python.exe`, `bin/python`, or
   `lib/python3` is skipped as a venv regardless of its name.

The full built-in list is in [Appendix B](#b-default-exclusions). Custom rules are covered
in [§7](#7-configuration--custom-exclusions).

---

## 4. CLI Command Reference & Everyday Recipes

### Command tree

```
smartbackup [OPTIONS]                    # default action = run a backup
├── restore [OPTIONS]                    # restore files from a backup
├── compress [OPTIONS]                   # archive an existing backup
├── watch [OPTIONS]                      # foreground drive watcher
└── daemon                              # background watcher service
    ├── install
    ├── status
    └── uninstall
```

Every command supports `--help` (`smartbackup restore --help`, …).

### 4.1 Root command (`smartbackup`) options

| Option | Short | Argument | Default | Description |
|---|---|---|---|---|
| `--source` | `-s` | PATH | Documents folder | Source directory to back up |
| `--target` | `-t` | PATH | auto-detect external drive | Target directory/drive |
| `--label` | `-l` | TEXT | — | Preferred target drive label (matched case-insensitively at detection time) |
| `--prompt` | | | off | Run the interactive `[Y/n/d]` prompt for a detected drive (used by the auto-detect spawner) |
| `--dry-run` | | | off | Simulate the backup: reports what would change without copying, deleting, or writing state (see [§3.1](#31-incremental-manifest-tracking)) |
| `--quiet` | `-q` | | off | Minimal output (banner + summary still shown; per-file logging suppressed) |
| `--exclude` | | TEXT (repeatable) | — | Add exclusion pattern(s). **Persists to `config.json` and applies to this run** — see [§7.3](#73-adding-custom-exclusions) |
| `--list-drives` | | | — | List available external drives and exit |
| `--device-name` | | TEXT | auto-detected hostname | Device name for the backup subfolder |
| `--list-devices` | | | — | List devices with backups on the target drive and exit (requires `--target`) |
| `--no-manifest` | | | off | Disable manifest tracking (traditional size/mtime comparison against the drive) |
| `--show-manifest` | | | — | Display manifest contents and exit (requires `--target`) |
| `--verify` | | | — | Verify the backup against the manifest (re-hashes files when hashes were recorded) and exit (requires `--target`) |
| `--compress` | | FORMAT | — | Compress the backup after copying: `zip` or `tar.gz` |
| `--hash` | | | off | SHA-256 change detection for files **up to 50 MB** |
| `--hash-all` | | | off | SHA-256 for **all** files regardless of size (implies `--hash`; slower) |
| `--version` | `-v` | | — | Print `smartbackup 0.6.1` and exit |
| `--help` | `-h` | | — | Show help and exit |

### 4.2 Everyday recipes

**Basic backups**

```bash
smartbackup                                   # Documents → auto-detected external drive
python main.py                                # same thing, no installation needed

smartbackup --source ~/Projects               # back up a custom folder
smartbackup --target /media/USB_DRIVE         # back up to an explicit path
smartbackup --target E:\                      # Windows example
smartbackup --label "MY_BACKUP_DISK"          # find the drive by its volume label
smartbackup --device-name "Work-Laptop"       # custom device subfolder name
smartbackup --quiet                           # minimal output (scripts/CI)
```

**Preview before you run**

```bash
smartbackup --dry-run                         # simulate a backup: no copies, no manifest writes
smartbackup --list-drives                     # what drives are visible?
smartbackup --target /media/USB --list-devices      # which machines have backups here?
smartbackup --target /media/USB --show-manifest     # manifest header stats
```

**Integrity verification (tiered hashing)**

```bash
smartbackup --hash                            # record SHA-256 for files ≤ 50 MB during backup
smartbackup --hash-all                        # record SHA-256 for every file (slow but thorough)
smartbackup --target /media/USB --verify      # re-check existence + size + recorded hashes
```

How the tiers work:

- **Default (no flag):** change detection uses size + mtime only.
- **`--hash`:** files ≤ 50 MB are hashed (64 KB chunks) and the hash is stored in the
  manifest; on later runs a hash mismatch flags the file as modified even if size/mtime
  look unchanged. Larger files fall back to size/mtime.
- **`--hash-all`:** every file is hashed regardless of size. Use when content integrity
  matters more than speed (bit-rot detection, network drives that don't update mtime).
- **`--verify`:** independently re-reads the backup and reports `Missing:`, `Size mismatch:`,
  and `Hash mismatch:` entries. Exit code `0` = clean, `1` = problems found.
  Hash checks only run for files whose hashes were recorded (i.e. you backed up with
  `--hash`/`--hash-all` at some point).

**Compression**

```bash
smartbackup --compress zip                    # backup, then archive as zip
smartbackup --compress tar.gz                 # backup, then archive as tar.gz

# Archive an existing, already-completed backup:
smartbackup compress --target /media/USB --format zip
smartbackup compress --target /media/USB --format tar.gz --device-name "Office-Desktop"
smartbackup compress --target /media/USB --format zip --remove-source   # delete the folder after success
```

- Archives are written into `Documents-Backup/` as `<Device>_<YYYYMMDD_HHMMSS>.zip|tar.gz`.
- Compression uses only the standard library (`zipfile`/`tarfile`) with atomic
  temp-file-then-rename writes; a failed run leaves no half-written archive.
- `zip` uses DEFLATE and preserves empty directories; `tar.gz` preserves everything tar
  captures.
- The `compress` subcommand warns if archives already exist for that device but proceeds.
- `--compress` (root) does **not** delete the uncompressed folder — only
  `compress --remove-source` does.

**Manifest bookkeeping**

```bash
smartbackup --target /media/USB --show-manifest    # version, format, source, hostname,
                                                   # created/updated, backup count, totals
smartbackup --target /media/USB --verify           # with hash verification
smartbackup --no-manifest                          # opt out of manifest tracking
```

### 4.3 `smartbackup restore` options

| Option | Short | Argument | Description |
|---|---|---|---|
| `--source` | `-s` | PATH | **Required.** The drive/directory that *contains* `Documents-Backup/` |
| `--target` | `-t` | PATH | Restore destination (default: the original source path recorded in the manifest) |
| `--pattern` | `-p` | TEXT (repeatable) | Glob filter(s), matched against the relative path (`fnmatch`), e.g. `"*.py"` |
| `--overwrite` | | | Overwrite existing files (conflict strategy `OVERWRITE`; default is `SKIP`) |
| `--dry-run` | | | Preview the restore without copying anything |
| `--list` | | | List files in the backup and exit |
| `--device-name` | | TEXT | Device subfolder to restore from (default: auto-detected hostname, then legacy layout) |

### 4.4 `smartbackup compress` options

| Option | Short | Argument | Default | Description |
|---|---|---|---|---|
| `--target` | `-t` | PATH | *required* | Backup drive/directory containing `Documents-Backup/` |
| `--format` | `-f` | TEXT | `zip` | `zip` or `tar.gz` (anything else → error, exit 1) |
| `--device-name` | | TEXT | auto hostname | Which device folder to compress |
| `--remove-source` | | | off | Delete the uncompressed folder after the archive is created |
| `--backup-folder` | | TEXT | `Documents-Backup` | *Hidden/internal* backup folder name |

### 4.5 `smartbackup watch` options

| Option | Short | Argument | Default | Description |
|---|---|---|---|---|
| `--interval` | `-i` | FLOAT | `2.5` | Polling interval in seconds |
| `--cooldown` | `-c` | INTEGER | `300` | Cooldown (seconds) between prompts for the same drive |

### 4.6 `smartbackup daemon` subcommands

| Command | Description |
|---|---|
| `smartbackup daemon install` | Register **and start** the OS background watcher service |
| `smartbackup daemon status` | Show Installed / Status (with PID) / Service Path / Details |
| `smartbackup daemon uninstall` | Stop and remove the background service |

No options; details in [§5](#5-auto-detect-daemon--watcher-guide).

### 4.7 Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (also: dry-run/list/manifest actions, prompt skipped by user, watcher stopped with Ctrl+C) |
| `1` | Failure: backup errors, verification errors, unsupported `--compress` format, missing directories, missing required `--target`/`--source` |
| `130` | Interrupted with Ctrl+C during a backup |

---

## 5. Auto-Detect Daemon & Watcher Guide

SmartBackup can run as a *drive watcher*: it polls for newly attached drives and, when a
known backup drive appears, opens a native terminal window asking whether to back up now.

### 5.1 How a drive becomes a "SmartBackup target"

A drive triggers the watcher only if **any** of these match (`DriveMatcher`):

1. Its label matches `preferred_target` from your config (or the passed label), or
2. `Documents-Backup/<hostname>/.smartbackup_manifest.json` exists, or
3. the folder `Documents-Backup/<hostname>/` exists, or
4. legacy layout: `Documents-Backup/.smartbackup_manifest.json` exists.

> **Important:** a brand-new, empty drive never matches (there is no manifest yet). Seed it
> once manually — `smartbackup --target /path/to/drive` — and the watcher will recognize it
> from then on.

Locked/ unreadable volumes (e.g. BitLocker-locked disks on Windows) are handled safely:
permission and OS errors are caught, the drive is treated as a non-target, and the watcher
keeps running.

### 5.2 Foreground testing: `smartbackup watch`

```bash
smartbackup watch                          # interval 2.5 s, cooldown 300 s
smartbackup watch --interval 1.0           # poll every second
smartbackup watch --cooldown 60            # only one prompt per drive per minute
```

You'll see a status panel (`SmartBackup Drive Watcher Active` with the polling interval and
cooldown). Stop with **Ctrl+C** (exit code `0`).

The watcher takes a **baseline snapshot** of attached drives when it starts, so drives that
are already plugged in never trigger a prompt — only *newly appearing* ones do.

### 5.3 The interactive prompt `[Y/n/d]`

When a matching drive is detected, SmartBackup opens a new native terminal window running:

```
python -m smartbackup --target <drive-path> --prompt
```

It prints a panel (drive path, free/total capacity, source folder, device ID) and asks:

```
Start backup now? (Y/n/d) [y]:
```

| Input | Accepted forms | Result |
|---|---|---|
| **Yes** | `y`, `yes`, *(Enter)* | Normal backup runs |
| **No** | `n`, `no` | "Backup skipped by user." — exits `0` |
| **Dry-run** | `d`, `dry-run`, `dryrun` | Runs in dry-run simulation mode (no files copied, manifest untouched) |
| Anything else | — | Warning printed, proceeds with a **standard backup** |
| Ctrl+C | — | "Backup cancelled by user." — exits `0` |

After the run completes, prompt-mode windows display
`Window will close automatically in 5 seconds...`.

**Prompts are debounced** so you aren't spammed:

- **3-second global suppression** — multi-partition drives that mount simultaneously
  produce a single prompt.
- **Per-drive cooldown** (default `300` s, i.e. 5 minutes) — re-plugging the same drive
  won't re-prompt until the cooldown expires.
- State is persisted in `<config dir>/watcher_state.json`.
  *To force an immediate re-prompt*, close the watcher/daemon and delete that file
  (there is no CLI command for this yet — see [`docs/PLAN_WIRING_FIXES.md`](PLAN_WIRING_FIXES.md)).

**Terminal used for the prompt window:**

| OS | Order of attempts |
|---|---|
| Windows | Windows Terminal (`wt.exe --title …`) → `cmd.exe` `start` → PowerShell `-NoExit` |
| macOS | iTerm2 (if `preferred_terminal` = `iterm`/`iterm2`) → Terminal.app via AppleScript → `open -a Terminal.app` fallback |
| Linux | `preferred_terminal` from config → `x-terminal-emulator` → `gnome-terminal` → `kitty` → `alacritty` → `konsole` → `xfce4-terminal` → `xterm` |

**Headless environments** (Linux without `DISPLAY`/`WAYLAND_DISPLAY`, or an SSH session) do
**not** spawn a window; the watcher stays silent. Run the prompt manually instead:

```bash
smartbackup --target /path/to/drive --prompt
```

### 5.4 Background service: `smartbackup daemon`

```bash
smartbackup daemon install      # register + start the watcher service
smartbackup daemon status       # Installed? Running (PID)? Where is the service?
smartbackup daemon uninstall    # stop + remove
```

What each platform gets:

| OS | Artifact | Details |
|---|---|---|
| **Windows** | Scheduled Task `SmartBackupWatcher` | Trigger: *at logon* (`/sc onlogon /rl highest`); runs `"<python>" -m smartbackup watch`; started immediately on install |
| **macOS** | LaunchAgent `~/Library/LaunchAgents/com.smartbackup.watcher.plist` | `RunAtLoad` + `KeepAlive` (auto-restarts); stdout → `~/.config/smartbackup/logs/watcher.log`, stderr → `watcher.err.log` |
| **Linux** | systemd **user** unit `~/.config/systemd/user/smartbackup-watcher.service` | `Type=simple`, `Restart=always`, `RestartSec=5s`; runs `<python> -m smartbackup watch` |

`daemon status` prints a table: **Installed**, **Status** (`Running (PID: …)` / `Stopped`),
**Service Path**, **Details**.

Notes:

- The Python interpreter used is the one that ran the install command — install from the
  same environment you run SmartBackup from (a venv you delete later will break the service).
- **Windows:** the background task runs without a visible window; prompt windows are spawned
  separately when a drive is detected. If prompts stop appearing, check
  `daemon status`, then check that the drive matches §5.1.
- **Linux:** systemd *user* units only start at login; enable lingering if you want the
  watcher at boot before login: `loginctl enable-linger $USER`.
- Uninstalling is idempotent: if the service file/task/plist is missing, the command
  succeeds with "not installed" messages.

### 5.5 Scheduling periodic backups with your OS

The codebase ships recipe printing for OS-level scheduling
(`SchedulerHelper.setup_scheduled_backup()`), but **it is not exposed as a CLI command yet**.
Until it is (see the fix plan), set up scheduling yourself using your OS tooling and the
`smartbackup` entry point:

**Windows (Task Scheduler, run in an *Administrator* prompt):**

```powershell
schtasks /create /tn "SmartBackup" /tr "smartbackup" /sc daily /st 09:00
```

Or graphically: `taskschd.msc` → Create Task → Trigger: daily → Action: start program
`smartbackup` (or `python` with arguments `-m smartbackup`).

**macOS (`~/Library/LaunchAgents/com.smartbackup.plist`), then
`launchctl load ~/Library/LaunchAgents/com.smartbackup.plist`:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.smartbackup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/python</string><string>-m</string><string>smartbackup</string>
    </array>
    <key>StartInterval</key><integer>86400</integer>
    <key>RunAtLoad</key><true/>
</dict>
</plist>
```

**Linux (cron):**

```cron
0 9 * * * /path/to/python -m smartbackup
```

**Linux (systemd user timer):** `~/.config/systemd/user/smartbackup.service` +
`~/.config/systemd/user/smartbackup.timer`, then
`systemctl --user enable --now smartbackup.timer`.

> Scheduling a *backup* is different from the *watcher daemon* (§5.4). The daemon only
> detects drive connections; it does not run backups on a timer.

---

## 6. Data Recovery & Restore Guide

### 6.1 Mental model

For `restore`, `--source` is the **drive (or directory) that contains `Documents-Backup/`** —
the same path you would pass to `--target` for a backup — *not* the device folder itself:

```
smartbackup restore --source /media/USB_DRIVE        # ✅  drive root
smartbackup restore --source /media/USB_DRIVE/My-Laptop   # ❌  wrong: it appends Documents-Backup/ itself
```

Device resolution order inside `--source/Documents-Backup/`:

1. `--device-name` (if given), else
2. legacy layout (manifest directly in `Documents-Backup/`), else
3. `Documents-Backup/<current-hostname>/` if it exists, else
4. the root folder itself.

**Destination:** `--target` if provided; otherwise the **original source path recorded in
the manifest** (e.g. `/home/you/Documents`). If neither is available, the restore fails with
`No target path specified and no manifest source found`.

### 6.2 Step 1 — Inspect before you restore

```bash
# List contents (from the manifest, or a directory scan if no manifest)
smartbackup restore --source /media/USB_DRIVE --list
# path/to/file.txt (1,234 bytes)

# Manifest summary: source path, hostname, dates, totals
smartbackup --target /media/USB_DRIVE --show-manifest

# Integrity check: existence + size + hashes (where recorded)
smartbackup --target /media/USB_DRIVE --verify
# ✅ All files verified successfully!   (exit 0)
# ❌ Found N verification errors: Missing: … / Size mismatch: … / Hash mismatch: …  (exit 1)

# Per-run audit trail
cat /media/USB_DRIVE/Documents-Backup/<Device>/_backup_logs/backup_*.log
```

### 6.3 Step 2 — Restore

```bash
# Full restore to the original location (read from manifest.source)
smartbackup restore --source /media/USB_DRIVE

# Restore to a custom directory (great for testing / new machine layout)
smartbackup restore --source /media/USB_DRIVE --target ~/Restored

# From a specific machine's backup on a shared drive
smartbackup restore --source /media/USB_DRIVE --device-name "Office-Desktop"

# Filter with globs (matched against the relative path; repeatable)
smartbackup restore --source /media/USB_DRIVE --pattern "*.py" --pattern "*.md"

# Preview — nothing is copied
smartbackup restore --source /media/USB_DRIVE --dry-run

# Replace files that already exist locally
smartbackup restore --source /media/USB_DRIVE --overwrite
```

Internals worth knowing:

- Files are copied with metadata (`copy2`) using an **atomic temp-file + rename** pattern,
  so an interrupted restore won't leave half-written files.
- Restore runs multithreaded (4 workers).
- Internal bookkeeping is never restored: anything under `_backup_logs/` or matching
  `.smartbackup*` is skipped.
- On completion you get a `RESTORE SUMMARY` table (Total / Restored / Overwritten / Skipped /
  Errors / size / duration / speed). Exit `0` if `errors == 0`, else `1`.

### 6.4 Conflict resolution strategies

When the destination file already exists:

| Strategy | Behavior | Availability |
|---|---|---|
| **SKIP** | Keep the existing local file; count it as `Skipped ("File exists")` | ✅ **Default** (no flag) |
| **OVERWRITE** | Replace the local file with the backed-up version | ✅ `--overwrite` |
| **NEWER** | Overwrite only if the backup copy's mtime is newer than the local file | ⚠️ Implemented in the restore engine but **not selectable from the CLI** (no flag maps to it yet) |
| **RENAME** | Keep both, renaming the restored file | ⚠️ Declared in the engine's `ConflictResolution` enum but **not implemented** (falls back to overwrite semantics if ever selected) |

> Until the wiring fix lands (see [`docs/PLAN_WIRING_FIXES.md`](PLAN_WIRING_FIXES.md)), your
> only CLI-selectable strategies are **SKIP** (default) and **OVERWRITE** (`--overwrite`).
> Emulate NEWER manually: restore to a scratch `--target`, then copy only the files you want.

### 6.5 Restoring from a compressed archive

`restore` reads **directories**, not `.zip`/`.tar.gz` files. To restore an archived backup,
extract it back into the expected layout first:

```bash
# 1. Extract into the device folder
mkdir -p /media/USB_DRIVE/Documents-Backup/<Device>
unzip <Device>_<timestamp>.zip -d /media/USB_DRIVE/Documents-Backup/<Device>     # zip
tar -xzf <Device>_<timestamp>.tar.gz -C /media/USB_DRIVE/Documents-Backup/<Device>   # tar.gz

# 2. Restore normally
smartbackup restore --source /media/USB_DRIVE --device-name "<Device>"
```

(If you extracted somewhere else entirely, just point the restore at the directory that
*contains* `Documents-Backup/`.)

### 6.6 Restoring on a different machine

Device folders are hostname-based, so another machine won't auto-find your folder. Either:

```bash
smartbackup restore --source /media/USB_DRIVE --device-name "Old-Machine-Name"
```

…or use `--target` to restore into an explicit directory. `--list` first to confirm what's
inside.

### 6.7 Common restore errors

| Message | Cause | Fix |
|---|---|---|
| `Backup directory not found: …` | `--source` points inside `Documents-Backup/` or at the device folder | Pass the **drive root** |
| `No manifest found` + everything listed by scan | Wrong device folder / legacy layout | Use `--device-name`, or run `--list` to see what's there |
| `No target path specified and no manifest source found` | No `--target` and manifest has no `source` | Pass `--target <dir>` |
| Nothing restored, `No files to restore!` | Pattern too narrow, or only internal files exist | Relax `--pattern`, verify with `--list` |
| `Permission denied` per file | OS permissions/controlled folders | Restore to a directory you own (`--target ~/Restored`) |

---

## 7. Configuration & Custom Exclusions

### 7.1 Where the config lives

| OS | Path |
|---|---|
| **Windows** | `%APPDATA%\SmartBackup\config.json` (typically `C:\Users\<you>\AppData\Roaming\SmartBackup\config.json`) |
| **macOS** | `~/.config/smartbackup/config.json` |
| **Linux** | `~/.config/smartbackup/config.json` |

The file is created on first write. The config directory also holds `watcher_state.json`
(debounce state) and, on macOS, the daemon logs (`logs/watcher.log`, `logs/watcher.err.log`).

### 7.2 Config keys

| Key | Type | Default | Effect | Settable from CLI? |
|---|---|---|---|---|
| `exclusions` | list of strings | `[]` (merged with built-ins) | Custom exclusion patterns | ✅ `--exclude` appends here and applies (see below) |
| `preferred_target` | string | none | Drive label used to pick the target and to match watcher prompts (case-insensitive) | ❌ edit JSON manually |
| `device_name` | string | none (use hostname) | Overrides the auto-detected device name (used by the watcher matcher) | ❌ edit JSON manually (`--device-name` is per-run only) |
| `auto_watch_cooldown` | int (seconds) | `300` | Watcher debounce cooldown | ❌ edit JSON manually (`watch --cooldown` is per-run only) |
| `preferred_terminal` | string | none | Terminal emulator for spawned prompt windows: `iterm`/`iterm2` on macOS, any emulator binary name on Linux | ❌ edit JSON manually |

Example `config.json`:

```json
{
  "exclusions": ["*.iso", "Downloads", "LargeDatasets"],
  "preferred_target": "MY_BACKUP_DISK",
  "device_name": "Work-Laptop",
  "auto_watch_cooldown": 300,
  "preferred_terminal": "iTerm2"
}
```

> The `❌ edit JSON manually` entries are functional (the code reads them) but have **no CLI
> setter** yet — planned in [`docs/PLAN_WIRING_FIXES.md`](PLAN_WIRING_FIXES.md). Keep the
> JSON valid (commas between entries); SmartBackup tolerates a corrupt file by treating it
> as empty.

### 7.3 Adding custom exclusions

**Via the CLI:**

```bash
smartbackup --exclude "*.iso" "Downloads" "LargeDatasets"
```

Each `--exclude` value is **persisted permanently** to `config.json` (they accumulate across
runs — the flag does not create a one-shot exclusion).

> ### Note: persisted exclusions are applied
>
> `--exclude` saves the pattern to `config.json` **and** applies it immediately: the backup
> run receives the merged set (`ConfigManager.get_exclusions()` = built-in defaults +
> your custom patterns). Patterns saved by earlier runs are picked up automatically by
> later runs, even without repeating the flag.
>
> **What excludes files:** `DEFAULT_EXCLUSIONS` + `EXCLUDED_EXTENSIONS` + your persisted
> patterns + venv-structure detection ([Appendix B](#b-default-exclusions)).

**By editing the file:** add patterns to the `exclusions` array in `config.json` (same
syntax: exact names like `Downloads`, globs like `*.iso`). Matching rules: see §3.5.

**Removing a persisted pattern:** edit `config.json` and delete it from the `exclusions`
array (there is no `--include`/remove flag).

### 7.4 Defining a preferred backup volume (`preferred_target`)

The preferred volume is how you say "*this* drive, always" without typing `--target` every
time — it also decides whether the watcher prompts for a drive.

1. Get the label: `smartbackup --list-drives` (the **Label** column).
2. Edit `config.json` and add:

```json
{ "preferred_target": "MY_BACKUP_DISK" }
```

3. Matching is case-insensitive and understands Windows drive letters (`E:` / `E:\` style)
   as well as volume/folder names on macOS/Linux.

Equivalents: `smartbackup --label "MY_BACKUP_DISK"` for a single run (not persisted).

---

## 8. Platform Nuances & Troubleshooting

### 8.1 Windows

**BitLocker-locked drives.** A locked volume throws `PermissionError`/`OSError` when probed.
SmartBackup's `DriveMatcher` catches these and treats the drive as a non-target (there's
even a regression test for it), so the watcher won't crash — but it also means **no prompt
until you unlock the drive**. Unlock first (`explorer.exe` → right-click the drive →
*Unlock BitLocker*, or `manage-bde -unlock D: -password`), then replug or wait for the poll.

**Terminal fallback chain.** Prompt windows try Windows Terminal (`wt.exe`) first, then
`cmd.exe`'s `start`, then PowerShell with `-NoExit`. If nothing opens, run the prompt
manually in any terminal:

```powershell
python -m smartbackup --target E:\ --prompt
```

**Drive letters.** Detection probes **D:**–**Z:** (the watcher scans A:–Z: for removable/fixed
drives). Your system disk (C:) is never a backup *target*, but pinned `--target E:\` always
works regardless of enumeration quirks.

**Legacy-console encoding errors.** On old console hosts you may see
`UnicodeEncodeError: 'charmap' codec can't encode characters` from the ASCII-art banner.
Fix: use Windows Terminal, or set UTF-8 mode first:

```powershell
$env:PYTHONUTF8="1"; smartbackup
```

### 8.2 macOS

**Terminal emulation.** Prompt windows open **Terminal.app** by default via AppleScript. To
use **iTerm2**, set `"preferred_terminal": "iterm"` (or `iterm2`) in
`~/.config/smartbackup/config.json`. If AppleScript fails, the fallback only opens an empty
Terminal window — run the command yourself in that case:

```bash
python -m smartbackup --target /Volumes/MY_BACKUP_DISK --prompt
```

**System/Time Machine exclusions.** `/Volumes` scanning skips `Macintosh HD`,
`Macintosh HD - Data`, `Macbook`, `Macbook - Data`, hidden volumes, and `.timemachine`
(Time Machine snapshot mounts) — so the watcher never mistakes a snapshot or the system
volume for your backup drive.

**Permissions.** macOS may block access to `Documents`, `Desktop`, etc. (TCC). If scanning
reports `Permission denied`, add your terminal (Terminal.app/iTerm) under
*System Settings → Privacy & Security → Full Disk Access*, then restart the terminal.

**Automation prompts.** The first osascript spawn may trigger a macOS automation consent
dialog ("Terminal wants to control …").

### 8.3 Linux

**Mount points.** External media are discovered under `/media/$USER`, `/run/media/$USER`,
and `/mnt`. If your distribution mounts elsewhere, pass `--target /your/mount` explicitly.
The `$USER` variable must be set (it is in normal shells; systemd services get it from the
unit environment).

**systemd user units.** `daemon install` writes
`~/.config/systemd/user/smartbackup-watcher.service` and runs
`systemctl --user daemon-reload` + `enable --now`. If `systemctl --user` fails
(`Failed to connect to bus`), you're in a session without a user bus — use
`smartbackup watch` in a terminal instead.

**Headless / SSH.** With no `DISPLAY`/`WAYLAND_DISPLAY`, the watcher detects a headless
session and skips GUI window spawning (by design). Use `smartbackup watch` + a manual
`smartbackup --target <path> --prompt`, or run `daemon install` on a machine with a desktop.

**Terminal emulators.** The spawn order is `preferred_terminal` → `x-terminal-emulator` →
`gnome-terminal` → `kitty` → `alacritty` → `konsole` → `xfce4-terminal` → `xterm`.
Install at least one, or set `preferred_terminal` to its binary name.

**Permissions.** The engine performs a write test (`.write_test`) on the target before
starting; a `No write permissions on backup medium` error means the mount is read-only or
owned by root — `chown`/`mount` it read-write or pick another target.

### 8.4 Troubleshooting matrix

| Symptom | Likely cause | Fix |
|---|---|---|
| `EXTERNAL STORAGE MEDIUM NOT FOUND` | No eligible drive ≥ 100 MB free / not mounted / wrong filesystem | `--list-drives`; check the mount; or use `--target`; or pick option `[1]` for a local temp backup |
| Backup went to an unexpected disk | Multiple candidate drives, auto-pick took the first | Pin with `--target` or `--label` / `preferred_target` |
| `Please specify backup directory with --target` | `--list-devices`, `--show-manifest`, or `--verify` without `--target` | Add `--target <drive root>` |
| Watcher runs but **never prompts** | Drive doesn't match §5.1 (brand-new drive), or cooldown active, or headless | Seed the drive once manually; delete `watcher_state.json`; check `daemon status` |
| Prompt appears but backups to nothing | — | Check the panel's Device ID matches the folder you expect (`--device-name`) |
| Second backup re-copies *everything* | Manifest missing/corrupt (warning was printed) or `--no-manifest` used | Normal recovery — manifest rebuilds; investigate the drive's health if recurring |
| Backup **skips changes** after a dry-run | A SmartBackup **≤ 0.6.0** dry-run wrote the manifest (fixed in 0.6.1) | Delete `.smartbackup_manifest.json`, run a real backup |
| `--exclude` has no visible effect | Pattern syntax doesn't match anything (glob vs exact name) | Check the matching rules in [§3.5](#35-what-gets-excluded) |
| `Collision: … is a file, but should be a directory` | A file/folder type changed in the source tree | Auto-resolved (the conflicting entry is removed); informational |
| `Full metadata copy failed … Falling back to basic copy` | ExFAT/FAT32 can't store full POSIX metadata | Expected; mtime is preserved manually, ownership/permissions aren't |
| `No files found for backup!` | Source empty, wrong `--source`, or everything excluded | Check `--source`; check exclusions (§3.5) |
| `UnicodeEncodeError … charmap` (Windows) | Legacy console host can't render the banner | Windows Terminal or `PYTHONUTF8=1` (§8.1) |
| `Permission denied` while scanning | OS privacy controls (macOS TCC / Windows controlled folders) | Grant access (§8.2) or run from another location |
| `Storage medium error (drive may have been disconnected)` | Drive unplugged mid-run | Reconnect and re-run; already-copied files are tracked in the manifest |
| Restore finds nothing | `--source` points at the device folder instead of the drive root | Use the drive root (§6.1) |
| Restore targets the wrong machine's folder | Hostname differs from folder name | `--device-name <folder>` |
| Daemon works but stopped after reinstalling Python/venv | Service registered with the old interpreter path | Re-run `smartbackup daemon uninstall` then `install` from the active environment |

### 8.5 Known limitations (current release)

1. Restore strategies `NEWER`/`RENAME` exist in the engine but aren't CLI-selectable ([§6.4](#64-conflict-resolution-strategies)).
2. No CLI setters for `preferred_target`, `device_name`, `auto_watch_cooldown`,
   `preferred_terminal` (edit `config.json`, §7.2).
3. No built-in scheduler command (use OS tooling, §5.5).
4. `restore` handles directories only — extract archives first (§6.5).
5. No encryption, deduplication, versioning, or remote targets (§1).

Fixes for item 1 are planned in [`docs/PLAN_WIRING_FIXES.md`](PLAN_WIRING_FIXES.md).

---

## 9. Appendix

### A. Quick flag card

```text
smartbackup [OPTIONS]
  -s, --source PATH        Source directory (default: Documents)
  -t, --target PATH        Target drive/directory (default: auto-detect)
  -l, --label TEXT         Preferred target drive label
      --prompt             Interactive [Y/n/d] prompt mode
      --dry-run            Simulate (no copies, no manifest writes)
  -q, --quiet              Minimal output
      --exclude TEXT       Persist extra exclusion pattern(s) to config
      --list-drives        Show drives and exit
      --list-devices       Show devices on --target and exit
      --device-name TEXT   Device subfolder (default: hostname)
      --show-manifest      Show manifest stats for --target and exit
      --verify             Verify backup against manifest and exit
      --no-manifest        Disable manifest tracking
      --compress FORMAT    zip | tar.gz, after copying
      --hash               SHA-256 for files ≤ 50 MB
      --hash-all           SHA-256 for all files
  -v, --version            Print version and exit

smartbackup restore  -s PATH [-t PATH] [-p GLOB]... [--overwrite] [--dry-run] [--list] [--device-name TEXT]
smartbackup compress -t PATH [-f zip|tar.gz] [--device-name TEXT] [--remove-source]
smartbackup watch    [-i SECONDS] [-c SECONDS]
smartbackup daemon   install | status | uninstall
```

### B. Default exclusions

**Folder/file names** (case-insensitive exact match):

<details>
<summary><code>DEFAULT_EXCLUSIONS</code> (click to expand)</summary>

- **Node.js / JavaScript:** `node_modules`, `.npm`, `.yarn`, `bower_components`, `.next`,
  `.nuxt`, `dist`, `build`, `.parcel-cache`
- **Python:** `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.tox`, `.nox`, `venv`,
  `.venv`, `env`, `.env`, `ENV`, `.eggs`, `.Python`, `pip-wheel-metadata`, `.pytype`
- **Python packaging/venvs:** `*.egg-info`, `virtualenv`, `.virtualenv`, `pipenv`,
  `.pipenv`, `conda-env`, `.conda`
- **JVM:** `target`, `.gradle`, `.m2`
- **.NET:** `bin`, `obj`, `packages`
- **Go:** `vendor`
- **IDE/editor:** `.idea`, `.vscode`, `*.swp`, `*.swo`, `.project`, `.settings`, `.classpath`
- **Version control:** `.git`, `.svn`, `.hg`
- **OS junk:** `.DS_Store`, `Thumbs.db`, `desktop.ini`
- **Temp files:** `*.tmp`, `*.temp`, `*.log`, `*.bak`, `~*`
- **Caches:** `.cache`, `cache`, `.sass-cache`
- **Docker:** `.docker`

</details>

**Excluded extensions** (always skipped):
`.pyc` `.pyo` `.pyd` `.class` `.o` `.obj` `.exe` `.dll` `.so` `.dylib` `.log` `.tmp` `.temp`

**Plus:** any directory that *looks like* a Python virtual environment (§3.5, tier 4).

### C. Key file paths

| What | Path |
|---|---|
| Config (Windows) | `%APPDATA%\SmartBackup\config.json` |
| Config (macOS/Linux) | `~/.config/smartbackup/config.json` |
| Watcher debounce state | `<config dir>/watcher_state.json` |
| Watcher daemon logs (macOS) | `~/.config/smartbackup/logs/watcher.log`, `watcher.err.log` |
| Backup manifest | `<target>/Documents-Backup/<Device>/.smartbackup_manifest.json` |
| Backup logs | `<target>/Documents-Backup/<Device>/_backup_logs/backup_YYYYMMDD_HHMMSS.log` |
| Archives | `<target>/Documents-Backup/<Device>_<YYYYMMDD_HHMMSS>.zip\|tar.gz` |
| Local temp fallback | `~/.local_backup_temp` |
| Windows watcher task | Scheduled Task `SmartBackupWatcher` |
| macOS watcher agent | `~/Library/LaunchAgents/com.smartbackup.watcher.plist` |
| Linux watcher unit | `~/.config/systemd/user/smartbackup-watcher.service` |

### D. Further reading

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — internals, pipelines, data flows
- [`docs/PLAN_WIRING_FIXES.md`](PLAN_WIRING_FIXES.md) — known limitations and the fix plan
- [`docs/CONTRIBUTING.md`](CONTRIBUTING.md) — development setup, tests, linting
- [`docs/CHANGELOG.md`](CHANGELOG.md) — release history
- [`README.md`](../README.md) — overview and quick start
