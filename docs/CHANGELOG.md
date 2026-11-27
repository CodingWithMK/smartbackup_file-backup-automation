# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-11-28

### Added
- **Interactive Selective Folder Backup (`--select`)**:
  - Added zero-dependency keyboard-driven TUI (`smartbackup.ui.selector.FolderSelector`) using
    `rich` + Python stdlib (`msvcrt` on Windows; `termios` + `tty` + `select` on POSIX with
    50ms Escape disambiguation and guaranteed `try...finally` terminal restoration).
  - Supports `↑`/`↓` (and `k`/`j`) navigation, `Space` toggle, `a` select/deselect all,
    `Enter` confirm (with inline validation when 0 folders are checked), `Esc`/`q` cancel,
    viewport scrolling for large directories, `rich.markup.escape()` markup safety, and
    automatic ASCII glyph fallback on legacy Windows `cp1252` consoles.
  - Preserves root-relative paths (`FileScanner.scan(..., include_folders=...)`) for full
    compatibility with standard backups and `RestoreEngine`.
  - Guarantees **unselected-folder and loose-root-file immunity** across `ManifestManager.diff()`,
    `ChangeDetector.detect_changes()`, and emptied-selected-folder deletion syncing.
  - Added dedicated audit tracking:
    - `SelectionMetadata` model and `SelectiveBackupRecord` manifest history.
    - JSON manifest (`last_backup_mode`, `last_selected_folders`, `selective_backups`) and a
      dedicated normalized **`selective_backups` SQLite table** separating selective backup
      history from `files`/`metadata` (100% backward compatible with legacy manifests and
      preserved across JSON ↔ SQLite format migrations).
    - Dedicated `SELECTIVE BACKUP (--select)` and `SELECTIVE WORKFLOW TRACE` sections written
      before `SUMMARY:` in per-run backup log files.
    - `Backup Mode` / `Selected Folders` rows in `BackupLogger.summary()` and a
      `Selective Backup History (--select)` Rich table in `--show-manifest`.
  - Enforces fail-fast exit code `1` when `--select` is invoked in a non-TTY environment.

### Changed
- **Global zero-write `--dry-run` isolation**:
  - Neither full `--dry-run` nor `--select --dry-run` creates target directories or writes
    `.log` files on the backup medium, ensuring complete zero-write dry-run simulation.
- **Shared device-target resolution (`Q7`)**:
  - Extracted `resolve_device_target()` in `smartbackup.manifest.factory` (checking
    `candidate.is_dir()` to avoid regular-file name collisions) and reused it across
    `cli.py` and `RestoreEngine`.
- **Optional case-sensitive `ExclusionFilter` mode (`Q8`)**:
  - Added opt-in `case_sensitive: bool = False` parameter to `ExclusionFilter` while
    preserving the cross-platform case-insensitive default across Windows, macOS, and Linux.

### Fixed
- **Eliminated silent hash failures during `--verify` and `--hash` (`Q1`)**:
  - `ManifestManager._hash_file()` and `FileScanner._calculate_hash()` now return `None`
    on read/`OSError` failures (with warning logged in `FileScanner`) instead of `""`.
  - `ManifestManager.verify(..., verify_hashes=True)` now reports an explicit hashing
    error and exits `1` when a file's metadata is readable (`stat()`) but its body cannot
    be read during hashing.
  - Added `FileInfo.hash_error` so unreadable files scanned under `--hash` are never
    silently skipped as unchanged, while non-hash runs continue fast-path size+mtime checks.
- **Crash-proof exclusion glob matching (`Q2`)**:
  - Replaced naive `.replace()` glob-to-regex conversion in `ExclusionFilter` with
    `fnmatch.translate()` plus a literal-glob fallback on `re.error`, fixing crashes and
    mis-matches on patterns containing regex metacharacters (`Backup (1)*`, `C++*`, `$`, `|`, `{}`).
- **Corrupt `config.json` protection and atomic saves (`Q3`)**:
  - `ConfigManager.load()` now differentiates `FileNotFoundError` from corrupt JSON,
    non-UTF-8 bytes, non-dict JSON, and `OSError`, emitting a visible warning instead of
    silently resetting settings.
  - `ConfigManager.save()` now preserves any corrupt existing `config.json` to a
    collision-safe `config.json.corrupt.<timestamp>` backup before atomically swapping via
    a temporary file in the same directory.
- **Legacy layout migration rollback & error reporting (`Q4`)**:
  - `BackupEngine._migrate_legacy_layout()` now uses collision-safe temporary folder
    naming, performs best-effort rollback when the final `rename()` fails (preserving any
    unmovable items and logging the exact recovery directory), and returns `bool` so
    `run_backup()` increments `result.errors` and aborts instead of proceeding into a
    half-migrated layout.
- **Non-interactive `EOFError` and cancel retry-loop fix (`Q5`)**:
  - `FallbackHandler.handle_no_device()` now catches `EOFError` alongside
    `KeyboardInterrupt`, and `SmartBackup.run()` stops immediately on cancel/`Ctrl+C`/`EOF`
    instead of re-prompting `DEFAULT_MAX_RETRIES` (3) times.
- **Unified manifest warning logging (`Q6`)**:
  - `ManifestManager`, `JsonManifestManager`, `SqliteManifestManager`, and
    `manifest/factory.py` now accept an optional `BackupLogger` so corrupt-load and save
    warnings route cleanly through `BackupLogger.warning()` instead of leaking raw
    `sys.stderr` output; hardened JSON/SQLite corrupt-schema loading.

## [0.8.0] - 2026-11-23

### Added
- **SQLite manifest backend (`ManifestFormat.SQLITE`, F10)**:
  - Implemented `SqliteManifestManager` (`.smartbackup_manifest.db`) using Python's
    standard-library `sqlite3` with atomic temp-file replacement for large backups.
  - Added manifest factory and auto-detection helpers (`get_manifest_manager`,
    `detect_manifest_manager`, `has_manifest`) wired across `BackupEngine`,
    `RestoreEngine`, `DriveMatcher`, and all CLI inspection commands (`--show-manifest`,
    `--verify`, `--list-devices`, `restore --list`, `restore --manifest-info`).
  - Seamless format migration when switching between `json` and `sqlite` (preserving
    history and removing the superseded manifest file after a successful non-dry-run save).
  - Wired `manifest_format` through `--manifest-format [json|sqlite]`,
    `ConfigManager.get/set_manifest_format()`, and `smartbackup config set|get|unset manifest_format`.
- **Cross-platform desktop notifications (`--notify`, F10)**:
  - Implemented best-effort OS desktop notifications in `FallbackHandler.notify_completion()`
    (`osascript` on macOS, `notify-send` on Linux, PowerShell on Windows) behind the
    opt-in `--notify` flag, with safe escaping, 5-second timeout, and non-fatal fallback.

## [0.7.2] - 2026-11-20

### Added
- **`smartbackup schedule [--hours N]` (F6)**: exposes `SchedulerHelper.setup_scheduled_backup()`
  via the CLI and updates the OS scheduler recipes (Windows `schtasks`, macOS `launchd`,
  Linux `cron` / `systemd`) to emit runnable `-m smartbackup` invocations.
- **`smartbackup restore --manifest-info` (F7)**: surfaces `RestoreEngine.get_manifest_info()`
  as a formatted summary table.
- **`smartbackup daemon clear-state` (F9)**: exposes `DebounceLock.clear()` so users can
  clear `watcher_state.json` without deleting it by hand.

### Changed
- **`smartbackup restore --list` (F7)**: now delegates to `RestoreEngine.list_files(patterns=...)`
  instead of duplicating manifest/directory traversal in the CLI, and honors `-p/--pattern`.
- **Unified target writability probe (F8)**: `BackupEngine._validate_paths()` now delegates to
  `DeviceDetector.validate_device()`, removing duplicate write-test code.

## [0.7.1] - 2026-11-19

### Added
- **`smartbackup config` command group (F4)**: `ConfigManager` already had
  setters for `preferred_target`, `device_name`, `auto_watch_cooldown` and
  `preferred_terminal`, but nothing in production called them, so the keys
  could only be changed by hand-editing `config.json`. The new group provides
  `config list`, `get <key>`, `set <key> <value>`, `unset <key>`,
  `exclude <pattern>...` and `unexclude <pattern>...`.
  - `auto_watch_cooldown` is validated as an integer ≥ 0.
  - `device_name` is sanitized to a filesystem-safe folder name.
  - `exclusions` is managed only through `exclude`/`unexclude`.
  - Unknown keys exit `1` and list the valid keys; invalid values never write.
- **`ConfigManager.remove_exclusion()`**: removes a persisted pattern (no-op
  when absent), powering `config unexclude`.
- **`sanitize_device_name()`** in `platform/identity.py`, reused by
  `get_device_name()` so CLI writes follow the same rules as hostname detection.

### Fixed
- **`watch --cooldown` now honors `auto_watch_cooldown` (F5)**: the flag
  defaulted to a hard-coded `300` and the config key was never read. Resolution
  is now `--cooldown` flag → `auto_watch_cooldown` config → `300`. A corrupt
  config value falls back to `300` instead of crashing the watcher.

### Added
- **Regression coverage for the config front door**:
  - `tests/test_config_cli.py` — isolated-config roundtrips for list/get/set/
    unset/exclude/unexclude, sanitization, validation and no-write-on-error
    controls.
  - `tests/test_daemon_cli.py` — watcher cooldown resolution (config, flag
    precedence, default and corrupt-config fallback).
  - `tests/test_sandbox_smoke.py` — subprocess config set/get/unset and
    exclude/unexclude roundtrips.

## [0.7.0] - 2026-11-19

### Added
- **Restore conflict strategies are now selectable and complete (F3)**:
  - `smartbackup restore --conflict [skip|overwrite|newer|rename]` exposes the
    engine's `ConflictResolution` enum. `skip` remains the default.
  - `NEWER` was implemented in the engine but unreachable from the CLI; it now
    overwrites only when the backed-up copy's mtime is newer than the local file.
  - `RENAME` was declared but unimplemented (it silently overwrote the local
    file). It now keeps both files, writing the restored copy as
    `<name>.restored-<YYYYmmdd-HHMMSS>.<ext>` with collision-safe `-1`, `-2`, …
    suffixes.
  - `--overwrite` is retained as a legacy alias for `--conflict overwrite`;
    when both are given, `--conflict` wins. An unknown value exits `1` with the
    valid strategy list.
  - Dry-run `RENAME` reports the intended name without writing anything.

### Added
- **Regression coverage for restore conflicts**:
  - `tests/test_restore.py` — engine-level `NEWER` skip/overwrite, `RENAME`
    keep-both and collision safety, dry-run, plus controls for the legacy
    `SKIP`/`OVERWRITE` paths.
  - `tests/test_restore_cli.py` — real Typer command coverage for the new flag,
    invalid values, the `--overwrite` alias and flag precedence.
  - `tests/test_sandbox_smoke.py` — black-box subprocess coverage for
    `--conflict rename` and invalid values.

## [0.6.3] - 2026-11-19

### Fixed
- **Failed path validation no longer reports success (F11)**: when the backup medium
  (target) was missing or unwritable, `BackupEngine.run_backup()` returned a result with
  `errors == 0`. `SmartBackup.run()` therefore returned `True`, the CLI exited `0`, and the
  completion handler printed "Backup completed successfully!" even though nothing was
  copied — contradicting the documented exit-code contract (§4.8 of the User Guide).
  Validation failures are now counted as an error, so the summary reports `Errors: 1`, the
  CLI exits `1`, and the completion message is "Backup completed with errors!".
  The run log is also skipped when the medium is absent, instead of recreating the missing
  target directory, and a log write failure can no longer escape as an uncaught exception.

### Added
- **Validation-failure regression coverage**:
  - `tests/test_validation_failure_exit.py` — engine, public-API and real-CLI coverage for
    missing source/target and unwritable-medium validation, plus controls proving healthy
    runs still succeed.
  - `tests/test_sandbox_smoke.py` — black-box subprocess coverage (normal and `--dry-run`)
    asserting exit `1`, the error completion message, and that the missing target is not
    created.

## [0.6.2] - 2026-11-11

### Fixed
- **Windows external drive detection parity with macOS**:
  - Fixed bitmask decoding offset bug where `kernel32.GetLogicalDrives()` was shifted sequentially from letter `D`, mapping drive letters to incorrect bits and preventing external drives from ever being detected on Windows.
  - Implemented dynamic system and user home drive exclusion (`SystemDrive` and `Path.home().drive`), preventing backup targets on the host operating system partition.
  - Added native Win32 volume label resolution via `kernel32.GetVolumeInformationW` in `DriveMatcher` and `PathResolver` to properly match configured target names (`preferred_target`), resolving the issue where Windows root drives (e.g. `E:\`) have an empty `Path.name`.
  - Added resilient fallback logic in `PathResolver._find_windows_drives()` to scan drive letters `D-Z` when Win32 ctypes calls fail or return no drives.

### Added
- **Unit and regression tests for Windows external drive detection**:
  - `test_find_windows_drives_bitmask_mapping`: Verifies Win32 bitmask decoding and system drive exclusion.
  - `test_windows_system_drive_dynamic_exclusion`: Verifies dynamic exclusion of custom system drives (e.g. `D:`).
  - `test_find_windows_drives_fallback_on_exception`: Verifies graceful fallback to filesystem inspection upon Win32 exceptions.
  - `test_drive_matcher_windows_volume_label_matching`: Verifies volume label matching for Windows root drive paths against `preferred_target`.
  - `test_drive_matcher_windows_volume_label_mismatch_returns_false`: Verifies non-matching volume labels without backup manifests evaluate to `False`.
  - `test_drive_matcher_get_volume_label_helper`: Verifies cross-platform behavior of `_get_volume_label`.

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
