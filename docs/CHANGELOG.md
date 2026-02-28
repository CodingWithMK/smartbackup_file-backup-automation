# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-03-01

### Added
- **Compression Support**: Create compressed archives of backups in `zip` or `tar.gz` format
  - New `--compress FORMAT` option on the backup command (e.g., `smartbackup --compress zip`)
  - New `smartbackup compress` subcommand to compress existing uncompressed backups after the fact
  - Options: `--target`, `--format`, `--device-name`, `--remove-source`
  - Archives are named `<device-name>_<YYYYMMDD_HHMMSS>.<ext>` and placed alongside device folders
  - Atomic writes via temp files to prevent partial archives on failure
- **New module: `core/compressor.py`** — `BackupCompressor` class with full zip/tar.gz support

### Changed
- Version updated to 0.5.0 across all files

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
- Zero external dependencies (Python stdlib only)
- Multi-threaded file copying for speed

### Known Limitations
- No encryption support (planned for future)
- No cloud backup support (planned for future)
- No scheduled backup built-in (use OS scheduler)

---

## Roadmap

### v0.5.0
- [x] Compression support (zip/tar.gz)
- [ ] SQLite manifest for large directories (100K+ files)
- [ ] Quick hash comparison (xxhash/blake3)

### v0.6.0 (Planned)
- [ ] Encryption support for sensitive files
- [ ] Backup profiles
- [ ] Resume interrupted backups
