# Contributing to SmartBackup

Thanks for your interest in contributing! 🎉

## Quick Start

1. Fork and clone the repo
2. Create a virtual environment: `python -m venv .venv`
3. Activate it: `.venv/bin/activate` (or `.venv\Scripts\activate` on Windows)
4. Install dev dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest`

## Making Changes

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `pytest`
4. Run linter: `ruff check .`
5. Commit with a clear message
6. Push and create a Pull Request

## Code Style

- Follow PEP 8
- Use type hints
- Keep it simple and readable

## Translating Documentation

`README.md` at the repository root is always the canonical English version. Localized READMEs
live under `docs/i18n/` using ISO 639-1 language codes (for example, `docs/i18n/README.tr.md`
and `docs/i18n/README.de.md`).

When updating or adding a translation:

1. Keep CLI commands, flags, file names, and URLs verbatim; translate prose and inline `#` comments.
2. Update the language switcher bar in `README.md` and every `docs/i18n/README.*.md` file using
   native language names (e.g., `English`, `Türkçe`, `Deutsch`), bolding the active language.
3. Update the invisible HTML sync header (`<!-- Source: README.md | Version: ... -->`) at the top
   of the translated file.
4. Run `pytest tests/unit/test_docs_i18n.py` to verify all cross-language links, relative paths,
   internal heading anchors, version parity, and CLI command coverage.

## Questions?

Open an issue - we're happy to help!