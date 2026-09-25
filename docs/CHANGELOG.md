# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-09-25

### Added
- **Layered test suites for the Phase-0 fixes**:
  - `tests/test_dry_run_isolation.py` — unit mutation-gate spies (manifest save, layout
    migration, compression) with real-run counterparts, plus public-API state-parity tests
    proving dry-runs are invisible in the final backup tree and manifest.
  - `tests/test_exclusion_wiring_e2e.py` — the real Typer command with the real engine:
    persist-apply-later behavior and a control test proving `*.iso` is only excluded by a
    pattern, not by the built-in sets.
  - `tests/test_sandbox_smoke.py` — black-box subprocess smoke tests running `main.py` in a
    fully isolated sandbox (redirected config dir), registered under the new
    `sandbox` pytest marker.

### Fixed
- **Dry-run no longer mutates backup state (F1)**: `--dry-run` previously updated and saved
  `.smartbackup_manifest.json` as if the simulated copies had happened, so a later real run
  reported `Skipped` and silently left the backup stale (or copied nothing at all on a fresh
  target). The dry-run engine now skips manifest persistence, legacy folder-layout migration,
  and archive creation when `--compress` is combined with `--dry-run`. Regression tests cover
  the fresh-target, modified-file, deleted-file, compress, and legacy-layout scenarios.
- **`--exclude` patterns now apply to the backup (F2)**: custom exclusion patterns were
  persisted to `config.json` but never merged into the scan — `ConfigManager.get_exclusions()`
  had no production caller. The CLI now passes the merged exclusion set (built-in defaults +
  persisted custom patterns) into `SmartBackup.run()`, so an `--exclude` pattern takes effect
  on the very run that adds it and on every subsequent run without repeating the flag.

### Changed
- **Behavior change — dry-run accounting**: dry-runs no longer increment `backup_count`,
  advance manifest entries, remove deleted entries, migrate legacy layouts, or write
  compression archives. They still create the run log so you keep a preview report.
- **Behavior change — persisted exclusions take effect**: `exclusions` entries previously
  saved in `config.json` (which were inert) are now applied to every backup run. If a config
  contains patterns you added experimentally, review them before upgrading — files matched by
  those patterns will now be excluded.

## [0.6.0] - 2026-08-22

### Added
- **USB Drive Auto-Detect & Monitoring Daemon**:
  - Automatically scans and listens for attached storage media across Windows, macOS, and Linux without native C dependencies.
  - New `smartbackup watch` command for foreground monitoring with configurable polling interval (`--interval`) and debounce cooldown (`--cooldown`).
  - **New module: `platform/watcher.py`**:
    - `DriveMatcher`: Identifies SmartBackup targets by checking `Documents-Backup/<hostname>/.smartbackup_manifest.json`, legacy flat manifests, and preferred target drive labels. Resilient to BitLocker / locked drive errors.
    - `DebounceLock`: Enforces a 300-second cooldown timer and suppresses popup bursts across multi-partition drives. Persists state to `watcher_state.json`.
    - `DeviceWatcher`: Polling loop inspecting OS mount points (`GetLogicalDrives` on Windows, `/Volumes` on macOS, `/media` and `/run/media` on Linux).
- **Cross-Platform Interactive Terminal Spawner**:
  - **New module: `platform/terminal.py`**:
    - `TerminalSpawner`: Launches native interactive terminal executing `python -m smartbackup --target <path> --prompt`.
    - Windows fallback chain: `wt.exe new-tab` -> `cmd.exe /c start` -> `powershell.exe`.
    - macOS AppleScript integration via `osascript` targeting `Terminal.app` or `iTerm2` (with fallback to `open -a Terminal`).
    - Linux terminal emulator detection (`x-terminal-emulator`, `gnome-terminal`, `kitty`, `alacritty`, `konsole`, `xfce4-terminal`, `xterm`).
    - Headless / SSH session auto-detection to prevent GUI spawn errors.
- **Interactive Prompt Mode (`--prompt`)**:
  - Formatted Rich panel rendering drive info, total capacity, free space, and device ID.
  - Interactive prompt `[Y/n/d]` (Yes / No / Dry-run).
  - 5-second automatic pause on completion before closing the terminal window.
- **OS Background Service Management (`smartbackup daemon`)**:
  - `smartbackup daemon install`: Installs and activates background service (macOS LaunchAgent plist, Windows Task Scheduler logon task, Linux systemd user service).
  - `smartbackup daemon uninstall`: Unregisters and removes the background service.
  - `smartbackup daemon status`: Queries and displays status, PID, and service file location.

### Changed
- Version bumped to 0.6.0 across all package manifests and source files.
- `BackupConfig` and `ConfigManager` updated with `auto_watch_cooldown` and `preferred_terminal` settings.
- `SmartBackup.run()` now accepts `dry_run: bool = False` and seamlessly switches to `DryRunBackupEngine`.

## [0.5.1] - 2026-06-03

### Fixed
- **Robust Backup Migration**: Fixed crashes during legacy flat-layout to per-device migration by adding error handling for disappearing files (e.g., `.DS_Store`).
- **Hard Sync (True Synchronization)**: Enabled synchronization of deletions. Files deleted on the source are now automatically removed from the backup and the manifest.
- **Data Collision Resolution**: Implemented aggressive handling for file-to-directory (and vice versa) type changes, preventing `FileNotFoundError` and `FileExistsError`.
- **ExFAT/FAT32 Support**: Fixed "OS error 22 (Invalid argument)" on non-native file systems by adding a fallback mechanism from `shutil.copy2` to `shutil.copy` with manual timestamp preservation.

## [0.5.0] - 2026-03-14

### Added
- **Compression Support**: Create compressed archives of backups in `zip` or `tar.gz` format
  - New `--compress FORMAT` option on the backup command (e.g., `smartbackup --compress zip`)
  - New `smartbackup compress` subcommand to compress existing uncompressed backups after the fact
  - Options: `--target`, `--format`, `--device-name`, `--remove-source`
  - Archives are named `<device-name>_<YYYYMMDD_HHMMSS>.<ext>` and placed alongside device folders
  - Atomic writes via temp files to prevent partial archives on failure
- **New module: `core/compressor.py`** — `BackupCompressor` class with full zip/tar.gz support
- **SHA-256 Hashing**: Optional integrity-based change detection
  - `--hash` flag enables SHA-256 hashing for files up to 50MB
  - `--hash-all` flag hashes all files regardless of size (implies `--hash`)
  - Hash algorithm recorded in manifest (`hash_algorithm` field) for forward compatibility
- **Hash Verification**: `--verify` now checks file content integrity via SHA-256
  - Re-hashes backup files and compares against stored manifest hashes
  - Reports hash mismatches (corrupted files) alongside size mismatches

### Changed
- Version updated to 0.5.0 across all files
- Hash algorithm upgraded from MD5 to SHA-256 (collision-resistant)
- Hash chunk size increased from 8KB to 64KB for better I/O throughput
- `min_file_size_for_hash` replaced with `max_file_size_for_hash` (50MB default)
  - Old behavior: hash files ABOVE 1MB (hashed large files, skipped small ones)
  - New behavior: hash files UP TO 50MB (hashes small/medium files, skips huge ones)
- `mtime` comparison changed from `>` to `!=` in both `ManifestEntry.has_changed()` and `FileInfo.needs_update()` to catch backward clock adjustments

### Fixed
- `ManifestEntry.has_changed()` now detects files with older mtime (clock skew, timezone changes)
- `FileInfo.needs_update()` now detects backward mtime changes
- `--verify` now actually verifies file content hashes, not just existence and size
- `use_hash_verification` config field is no longer hardcoded to `False` in `backup.py`

## [0.4.0] - 2026-02-24

### Changed
- **Modernized CLI with Typer**: Replaced `argparse` with `typer` for polished CLI experience with auto-generated help panels
- **Modernized terminal output with Rich**: Replaced raw ANSI escape codes and manual `print()` formatting with `rich` (Console, Panel, Table, Progress)
  - Headers displayed as styled Rich Panels
  - Backup summary rendered as a Rich Table
  - Progress bars powered by Rich Progress with spinner, ETA, and transfer speed
  - File actions, prompts, and scheduler instructions all use Rich markup
- **Added `rich>=13.0.0` and `typer>=0.9.0`** as runtime dependencies
- Version updated to 0.4.0 across all files

### Fixed
- Fixed `_stop_progress()` not resetting `_progress_line_active` flag when no progress bar was active

## [0.3.0] - 2026-02-23

### Added
- **Device-Aware Backups**: Multiple devices can now safely back up to the same external drive
  - Each device gets its own subfolder under `Documents-Backup/` based on system hostname
  - New `--device-name` flag to set a custom device identifier
  - New `--list-devices` flag to show all devices with backups on a drive
  - Automatic detection and sanitization of hostname via `platform.node()`
  - macOS `.local` suffix (from mDNS/Bonjour) is stripped automatically
- **New module: `platform/identity.py`** — `get_device_name()` function for device identification
- **Manifest hostname field** — `hostname` recorded in manifest metadata for device traceability
- **Legacy layout migration** — Existing flat `Documents-Backup/` layouts are automatically migrated into a per-device subfolder on first run

### Changed
- `BackupConfig` dataclass gains `device_name` field
- `BackupEngine` builds backup path as `Documents-Backup/<device-name>/`
- `RestoreEngine` accepts `device_name` parameter with auto-detection fallback
- `ConfigManager` gains `set_device_name()` / `get_device_name()` for persistence
- CLI functions (`_show_manifest`, `_verify_manifest`, `_handle_restore`) are now device-aware
- Version updated to 0.3.0 across all files
- Test count increased to 194

## [0.2.2] - 2026-02-17

### Changed
- **Development Python version upgraded from 3.10 to 3.12**
  - Enables `Path.walk()`, improved f-strings, and faster hashlib
  - 10-15% overall performance improvement
  - Updated `.python-version` to 3.12
  - Minimum supported version for users remains `>=3.9`

## [0.2.1] - 2026-02-04

### Fixed
- **macOS External Drive Detection**: Fixed issue where Time Machine `.timemachine` snapshots appeared as external drives
  - Added comprehensive filtering for system directories (`.timemachine`, hidden directories starting with `.`)
  - Excluded internal system volumes: "Macintosh HD", "Macintosh HD - Data", "MacBook", "Macbook - Data"
  - Changed from single exclusion (`!= "Macintosh HD"`) to comprehensive filtering using `excluded_names` set
  - Location: `src/smartbackup/platform/resolver.py` in `_find_macos_drives()` method

### Changed
- Version updated to 0.2.1 across all files

## [0.2.0] - 2026-02-01

### Added
- **Manifest System**: JSON-based manifest tracking for 10x faster incremental backups
  - `ManifestEntry`, `Manifest`, `ManifestDiff` classes for file tracking
  - `JsonManifestManager` for atomic JSON manifest storage
  - Automatic manifest creation and updates during backup
  - Manifest verification command (`--verify`)
  - Manifest display command (`--show-manifest`)
- **Restore Functionality**: Full restore support from backup
  - `RestoreEngine` with multithreaded file restoration
  - Pattern-based file filtering (`--pattern`)
  - Conflict resolution (skip/overwrite existing files)
  - Dry-run mode for restore preview
  - List files in backup (`--list`)
  - Restore to original location or custom target
- **New CLI Commands**:
  - `smartbackup restore` - Restore files from backup
  - `--no-manifest` - Disable manifest tracking
  - `--show-manifest` - Display manifest contents
  - `--verify` - Verify backup integrity against manifest

### Changed
- **Major Refactoring**: Split monolithic 1949-line `smart_backup.py` into clean modular structure
  - `core/` - Engine, scanner, detector, restore modules
  - `manifest/` - Manifest tracking system
  - `platform/` - Cross-platform path resolution, device detection
  - `ui/` - Colors, logging modules
  - `cli.py` - Command-line interface
  - `config.py` - Configuration management
  - `models.py` - Data classes
  - `handlers.py` - Fallback handlers
  - `backup.py` - Main SmartBackup class
- Version updated to 0.2.0 across all files
- Improved test coverage: 175 tests (up from ~20)

### Fixed
- Removed `pytest` from main dependencies (was breaking "zero dependencies" claim)
- Fixed duplicate `set_preferred_target()` method
- Fixed version string mismatch (was showing "v2.0" instead of version)
- Fixed incomplete `__all__` exports in `__init__.py`

### Removed
- Deleted monolithic `smart_backup.py` (replaced by modular structure)

---

## [0.1.0] - 2025-10-21

### Added
- Initial release
- Cross-platform support (Windows, macOS, Linux)
- Incremental backup with change detection (size + timestamp)
- Automatic external drive detection
- Smart filtering of development artifacts:
  - Node.js: `node_modules`, `.npm`, `.yarn`, `dist`, `build`
  - Python: `venv`, `.venv`, `__pycache__`, `.pytest_cache`
  - Version Control: `.git`, `.svn`, `.hg`
  - IDEs: `.idea`, `.vscode`
  - And many more...
- Progress bar with colored terminal output
- Detailed logging saved to backup drive
- Fallback options when no external drive found
- Command-line interface with multiple options
- Zero external dependencies (Python stdlib only) *Note: As of v0.4.0 'rich' and 'typer' were added as runtime dependencies for CLI*
- Multi-threaded file copying for speed

### Known Limitations
- No encryption support (planned for future)
- No cloud backup support (planned for future)
- No scheduled backup built-in (use OS scheduler)

---

## Roadmap

### v0.5.0
- [x] Compression support (zip/tar.gz)
- [x] SHA-256 tiered hashing with `--hash` / `--hash-all` CLI flags
- [x] Hash-based verification in `--verify`
- [ ] SQLite manifest for large directories (100K+ files)

### v0.6.0 (Planned)
- [ ] Encryption support for sensitive files
- [ ] Backup profiles
- [ ] Resume interrupted backups
