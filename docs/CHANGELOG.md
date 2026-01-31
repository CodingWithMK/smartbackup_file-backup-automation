# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### v0.3.0 (Planned)
- [ ] Compression support (zip/tar.gz)
- [ ] SQLite manifest for large directories (100K+ files)
- [ ] Better progress display with ETA
- [ ] Quick hash comparison (xxhash/blake3)

### v0.4.0 (Planned)
- [ ] Encryption support for sensitive files
- [ ] Backup profiles
- [ ] Resume interrupted backups
