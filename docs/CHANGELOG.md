# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-21-10

### Added
- 🎉 Initial release
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
- No encryption support (planned for v0.2)
- No cloud backup support (planned for future)
- No scheduled backup built-in (use OS scheduler)

---

## Roadmap

### v0.2.0 (Planned)
- [ ] Encryption support for sensitive files
- [ ] Compression option
- [ ] Restore functionality

### v0.3.0 (Planned)
- [ ] Configuration file support
- [ ] Backup profiles