# SmartBackup — Plan for Fixing Quality, Integrity & Maintainability Issues

**Status:** in progress (Phases 0–2 complete · Phases 3–4 open) · **Target:** v0.9.0 hardening / pre-1.0.0 · **Scope:** verified
critical bugs, operational safety gaps, logging/duplication issues, and structural debt
identified in [`codebase-analysis.md`](codebase-analysis.md)

Every item below was verified against the source as of v0.9.0 (Phases 0–2 landed on `feat/selective-folder-backup` at `62da911`; 541 passing tests across 3-OS CI run `#46081876348`).
Original locations reflect `file:line` at v0.9.0 baseline. Companion documents:
[`codebase-analysis.md`](codebase-analysis.md) §5 (findings & severity matrix) and
[`ARCHITECTURE.md`](ARCHITECTURE.md) §10.3.

---

## 1. Executive summary

| ID | Issue | Severity | Type | Phase | Status |
|----|-------|----------|------|-------|--------|
| Q1 | Silent hash failure (`""`) in `_calculate_hash()` / `_hash_file()` makes `--verify` pass on unreadable/corrupt files and skips hash checks | 🔴 **Critical** | Bug (integrity) | 0 | ✅ fixed (`3c1d6a5`, `5bc1a14`) |
| Q2 | Glob-to-regex conversion in `ExclusionFilter` does not escape regex metacharacters (`+`, `(`, `)`, `[`, `$`) → crashes or mis-matches | 🔴 **Critical** | Bug (crash) | 0 | ✅ fixed (`3c1d6a5`) |
| Q3 | `ConfigManager.load()` silently returns `{}` on corrupt JSON / I/O errors → next `save()` can wipe all saved settings | 🟠 **High** | Data-safety bug | 1 | ✅ fixed (`e472227`) |
| Q4 | Legacy migration failure on final `temp_dir.rename()` can leave `.migration_temp_<ts>/` orphaned without rollback | 🟠 **High** | Recovery bug | 1 | ✅ fixed (`a2ec7f2`) |
| Q5 | `FallbackHandler.handle_no_device()` calls `input()` without catching `EOFError` on closed/piped stdin | 🟡 Low-Med | Bug (edge case) | 1 | ✅ fixed (`50d0b65`) |
| Q6 | `JsonManifestManager` and `SqliteManifestManager` print warnings directly to `sys.stderr`, bypassing `BackupLogger` and `--quiet` | 🟠 Medium | Observability | 2 | ✅ fixed (`5bc1a14`) |
| Q7 | Device-target resolution (`Documents-Backup/<device>` vs legacy root) duplicated between `cli.py` and `core/restore.py` | 🟠 Medium | Duplication | 2 | ✅ fixed (`5bc1a14`) |
| Q8 | `ExclusionFilter` lowercases path names unconditionally, diverging from case-sensitive Linux semantics | 🟡 Low-Med | Cross-platform | 2 | ✅ fixed (`3c1d6a5`) |
| Q9 | `BackupEngine.run_backup()` is ~264 lines orchestrating 10+ responsibilities in one method | 🟠 High debt | Maintainability | 3 | ⏳ open |
| Q10 | Monolithic `cli.py` (1,301 lines) combines all 7 command groups, manifest display, and interactive handlers | 🟠 High debt | Maintainability | 3 | ⏳ open |
| Q11 | 8 separate `Console()` instances across modules; only `ui/colors.py` uses `_smartbackup_theme` | 🟡 Medium debt | Consistency | 3 | ⏳ open |
| Q12 | Minor polish & CI gates (`max_retries` constant, redundant `venv_indicators[:6]` slice, monotonic durations, `test_devices.py`, `mypy`) | ⚪ Low / Polish | Housekeeping | 4 | 🟡 partial (`Q12a`, `Q12b` done) |

---

## 2. Phase 0 — Critical Integrity & Crash Hotfixes (✅ Complete)

### Q1 — Eliminate silent hash failure on unreadable files ✅ Fixed (`3c1d6a5`, `5bc1a14`)

**Where:**
- `src/smartbackup/core/scanner.py:223-232` (`FileScanner._calculate_hash`)
- `src/smartbackup/manifest/base.py:84-102` (`ManifestEntry.has_changed`)
- `src/smartbackup/manifest/base.py:508-561` (`ManifestManager._hash_file` and `verify`)

**Mechanism:**
1. Both `_calculate_hash()` and `_hash_file()` catch `Exception` and return `""`.
2. In `ManifestManager.verify()` (`:550-557`), when `verify_hashes=True` and `entry.file_hash` is set:
   ```python
   actual_hash = self._hash_file(file_path)
   if actual_hash and actual_hash != entry.file_hash:
       errors.append(...)
   ```
   If `file_path.stat()` succeeds (metadata intact) but reading the file body fails (bad USB sector, I/O error, permission revoked), `_hash_file()` returns `""`, `if actual_hash ...` evaluates to `False`, and **`--verify` silently reports 0 errors**.
3. During `--hash` / `--hash-all` scans, an unreadable file gets `file_hash=""`, silently skipping hash comparison in `ManifestEntry.has_changed()` without warning.

**Fix (minimal, backward compatible):**

1. Change `ManifestManager._hash_file(path)` to return `Optional[str]` (`None` on `OSError` / read failure) or propagate `OSError` inside `verify()`.
2. In `ManifestManager.verify()`:
   - When `actual_hash is None`, append `f"Error hashing {entry.relative_path}: unable to read file"` to `errors` so `--verify` exits `1`.
3. Change `FileScanner._calculate_hash(path)` to return `Optional[str]`, logging `self.logger.warning(f"Could not hash {path}: {e}")` when hashing fails instead of swallowing silently.
4. In `ManifestEntry.has_changed(file_info)`:
   - Keep `size` and `mtime` fast-path checks; when hashes are requested and `file_info.file_hash is None` while `self.file_hash` is set, treat as unverifiable/changed (or fall back safely with a warning logged at scan time) rather than silently equating `"" == ""`.

**Tests:**
- `tests/unit/test_manifest_json.py` & `tests/unit/test_manifest_sqlite.py`:
  - `test_verify_reports_error_when_file_unreadable_during_hashing` (mock `open` raising `OSError` while `stat()` succeeds → `verify(..., verify_hashes=True)` returns non-empty error list)
- `tests/unit/test_scanner.py`:
  - `test_calculate_hash_returns_none_and_logs_warning_on_read_error`

**Docs:** update `CHANGELOG.md` and mark `CRIT-2` resolved in `codebase-analysis.md`.

**Effort:** S (≈ 2–3 hours incl. tests) · **Risk:** low — makes integrity verification strictly more honest.

---

### Q2 — Use `fnmatch.translate()` in `ExclusionFilter` ✅ Fixed (`3c1d6a5`)

**Where:** `src/smartbackup/core/scanner.py:30-35`

```python
for excl in exclusions:
    if "*" in excl or "?" in excl:
        # Convert glob pattern to regex
        regex = excl.replace(".", r"\.").replace("*", ".*").replace("?", ".")
        self.patterns.append(re.compile(f"^{regex}$", re.IGNORECASE))
```

**Mechanism:** Regex metacharacters (`+`, `(`, `)`, `[`, `]`, `{`, `}`, `^`, `$`, `|`, `\`) are not escaped. Valid filenames like `Backup (1)*`, `C++*`, or `draft[v1]*` raise `re.error` at `ExclusionFilter.__init__` time. Because `--exclude` persists patterns into `config.json`, a single pattern with unescaped metacharacters breaks **every subsequent backup** until removed via `config unexclude`.

**Fix:**
1. Replace line 33–34 with Python's standard library `fnmatch.translate`:
   ```python
   import fnmatch
   ...
   if any(ch in excl for ch in ("*", "?", "[")):
       self.patterns.append(re.compile(fnmatch.translate(excl), re.IGNORECASE))
   ```
   *(Careful with `[` — verify whether users pass literal `[draft]*` vs glob character classes `[0-9]*`. If literal brackets are desired unless `*`/`?` is present, keep `if "*" in excl or "?" in excl:` and escape unbalanced brackets gracefully or use `fnmatch.translate(excl)`.)*
2. Add a guard around `re.compile()` so an invalid pattern logs a clear warning instead of crashing an entire backup run.

**Tests:** `tests/unit/test_scanner.py`
- `test_exclusion_pattern_with_regex_metacharacters_does_not_crash` (`"Backup (1)*"`, `"C++*"`, `"data$*"`, `"a+b*.log"`, `"report[draft]*"`)
- `test_exclusion_pattern_matches_exact_glob_semantics` (verify existing `*.pyc`, `*.egg-info`, `temp?.txt` patterns unchanged)

**Docs:** update `CHANGELOG.md` and mark `CRIT-1` resolved in `codebase-analysis.md`.

**Effort:** XS (≈ 1 hour incl. tests) · **Risk:** very low — stdlib drop-in replacement.

---

## 3. Phase 1 — Operational Safety & Data-Loss Prevention (✅ Complete)

### Q3 — Stop `ConfigManager.load()` from silently swallowing corrupt config errors ✅ Fixed (`e472227`)

**Where:** `src/smartbackup/config.py:166-181`

```python
def load(self) -> dict:
    if self.config_file.exists():
        try:
            with open(self.config_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}
```

**Mechanism:** If `config.json` has a JSON syntax error or transient read failure, `load()` returns `{}` silently. A subsequent `config set <key> <val>` or `--exclude` calls `load()` → mutates `{}` → `save()`, **permanently overwriting and wiping** the user's previous exclusions, `preferred_target`, `device_name`, and `manifest_format`.

**Fix:**
1. Differentiate `FileNotFoundError` (normal first-run → `{}`) from `json.JSONDecodeError` / `OSError`:
   - Emit a visible warning (`sys.stderr` or optional logger) identifying the exact path and parse error.
   - Before overwriting a corrupt `config.json` inside `save()`, preserve a backup copy (`config.json.corrupt.<timestamp>`) so the user never loses their original settings.
   - Validate that `json.load()` returns a `dict` (not a list/scalar).
2. Make `save()` atomic (write to `config.json.tmp` then `replace()`), matching the atomic write pattern already used by manifests and archives.

**Tests:** `tests/unit/test_config.py`, `tests/integration/test_cli_config.py`
- `test_load_corrupt_json_emits_warning_and_returns_empty_dict`
- `test_save_backs_up_corrupt_config_before_overwriting`
- `test_save_uses_atomic_temp_file_replacement`

**Effort:** S (≈ half day) · **Risk:** low — additive safety only.

---

### Q4 — Add best-effort rollback to `_migrate_legacy_layout()` ✅ Fixed (`a2ec7f2`)

**Where:** `src/smartbackup/core/engine.py:356-407`

**Mechanism:** During legacy flat-layout → per-device migration, items are moved into `.migration_temp_<ts>/` (`:388-395`) and then `temp_dir.rename(device_folder)` (`:399`) runs. If that final rename fails (e.g., locked handle on Windows or name collision), line `:404` logs an error and returns while all existing backups remain stranded inside `.migration_temp_<ts>/`.

**Fix:**
1. On `OSError` in `temp_dir.rename(device_folder)`:
   - Attempt a best-effort rollback moving each entry inside `temp_dir` back to `backup_root / item.name`.
   - If `temp_dir` is empty after rollback, remove it cleanly; otherwise log an explicit recovery message naming the exact `.migration_temp_<ts>` directory so the user knows where their files are.
2. Increment `self.result.errors` if migration fails unrecoverably so the backup does not proceed into a half-migrated state and report exit `0`.

**Tests:** `tests/unit/test_engine_unit.py`
- `test_legacy_migration_rolls_back_items_when_final_rename_fails`
- `test_legacy_migration_failure_logs_recovery_path_and_counts_error`

**Effort:** S (≈ half day) · **Risk:** low — only triggers on legacy pre-v0.3.0 layouts when rename fails.

---

### Q5 — Guard `input()` against `EOFError` in `FallbackHandler` ✅ Fixed (`50d0b65`)

**Where:** `src/smartbackup/handlers.py:75-96`

**Mechanism:** `handle_no_device()` catches `KeyboardInterrupt` (`:92`), but line `:85` calls `input()` (and `:76` calls `Prompt.ask()`). When stdin is closed or piped (e.g., cron, CI, redirected input), `EOFError` propagates uncaught.

**Fix:**
1. Change `except KeyboardInterrupt:` (`:92`) to `except (KeyboardInterrupt, EOFError):`.
2. Return `None` with a clean log message (`"Backup cancelled (non-interactive input)."`).

**Tests:** `tests/unit/test_handlers.py`
- `test_handle_no_device_catches_eof_error_gracefully`

**Effort:** XS (≈ 30 min) · **Risk:** none.

---

## 4. Phase 2 — Logging Consistency, Deduplication & Cross-Platform Semantics (✅ Complete)

### Q6 — Route manifest warnings through `BackupLogger` instead of raw `sys.stderr` ✅ Fixed (`5bc1a14`)

**Where:**
- `src/smartbackup/manifest/json_manifest.py:48-51, 86-89`
- `src/smartbackup/manifest/sqlite_manifest.py:175-177, 289-291`
- `src/smartbackup/manifest/factory.py:30-84`

**Mechanism:** Both `JsonManifestManager` and `SqliteManifestManager` call `print(f"Warning: ...", file=sys.stderr)` directly. These messages bypass `BackupLogger`, so they:
- leak to stderr even in `--quiet` mode, and
- never appear in `_backup_logs/backup_*.log`.

**Fix:**
1. Accept an optional `logger: Optional[BackupLogger] = None` on `ManifestManager.__init__`, `JsonManifestManager`, `SqliteManifestManager`, and `manifest/factory.py` helpers (`get_manifest_manager`, `detect_manifest_manager`) — default `None` for 100% backward compatibility.
2. Add a small `_warn(self, message: str)` helper on `ManifestManager`: if `self.logger` is set, call `self.logger.warning(message)`; otherwise fall back to `print(f"Warning: {message}", file=sys.stderr)`.
3. Pass `self.logger` from `BackupEngine`, `RestoreEngine`, and `cli.py`.

**Tests:** `tests/unit/test_manifest_json.py`, `tests/unit/test_manifest_sqlite.py`
- `test_corrupt_manifest_logs_warning_via_injected_logger_not_stderr`

**Effort:** S (≈ half day) · **Risk:** low — optional parameter with backward-compatible fallback.

---

### Q7 — Extract shared `resolve_device_target()` utility ✅ Fixed (`5bc1a14`)

**Where:**
- `src/smartbackup/cli.py:78-98` (`_resolve_device_target`)
- `src/smartbackup/core/restore.py:94-106` (`RestoreEngine.__init__`)

**Mechanism:** Both locations implement nearly identical logic to choose between `root / device_name`, legacy flat `root` (when `has_manifest(root)` is True), or auto-detected `root / get_device_name()`. Any future layout rule change must be kept in sync in two places.

**Fix:**
1. Add `PathResolver.resolve_device_target(backup_root: Path, device_name: Optional[str] = None) -> Path` in `src/smartbackup/platform/resolver.py` (or a small helper in `manifest/factory.py` / `platform/identity.py` to avoid circular imports with `manifest`).
   - *Dependency note:* `platform/resolver.py` is currently stdlib-only. To preserve its zero-internal-dependency leaf status, place `resolve_device_target()` in `manifest/factory.py` (which already imports `has_manifest`) or pass a `has_manifest_fn` predicate. Putting it in `manifest/factory.py` keeps the dependency DAG strictly acyclic!
2. Call it from both `cli.py` and `core/restore.py`.

**Tests:** `tests/unit/test_restore.py`, `tests/integration/test_cli_backup.py`
- Unit tests covering explicit `device_name`, legacy root manifest, auto-detected device subfolder, and missing directory fallback.

**Effort:** S (≈ 2–3 hours) · **Risk:** low.

---

### Q8 — Clarify / align `ExclusionFilter` case-sensitivity across platforms ✅ Fixed (`3c1d6a5`)

**Where:** `src/smartbackup/core/scanner.py:25-65`

**Mechanism:** `ExclusionFilter` unconditionally lowercases all filenames and uses `re.IGNORECASE`. On Windows and macOS (default APFS case-insensitive), this matches OS semantics. On Linux (`ext4`/`xfs`/`btrfs`), `Build/` and `build/` are distinct directories, so excluding `build` also excludes `Build`.

**Fix (choose conservative option):**
1. Add an optional `case_sensitive: Optional[bool] = None` parameter to `ExclusionFilter.__init__`:
   - Default `False` (current cross-platform developer-friendly behavior preserved so no existing user workflows break silently!).
   - Allow callers/config to opt in to `case_sensitive=True` if needed, AND explicitly document case-insensitive matching in `ExclusionFilter` docstring and `USER_GUIDE.md` §7.3.

**Tests:** `tests/unit/test_scanner.py`
- `test_exclusion_filter_case_insensitive_default_and_case_sensitive_opt_in`

**Effort:** XS (≈ 1–2 hours) · **Risk:** very low — preserves existing default behavior.

---

## 5. Phase 3 — Maintainability & Architectural Decomposition (Pre-v1.0 Readiness)

> These items do not fix active bugs; execute them on dedicated refactor branches with zero behavior changes verified by the full 456-test suite.

### Q9 — Decompose `BackupEngine.run_backup()` 🟠

**Where:** `src/smartbackup/core/engine.py:61-325` (~264 lines)

**Fix:** Extract cohesive private phase helpers on `BackupEngine` without altering any public API or `DryRunBackupEngine` override hooks:
- `_prepare_backup_target() -> Optional[Path]` (validation + legacy migration + mkdir)
- `_initialize_manifest(backup_target: Path) -> None` (auto-detect + format migration prep)
- `_compute_changes(source_files, backup_target, scoped_folders) -> tuple[list, list, list]`
- `_finalize_manifest(deleted_paths, backup_target) -> None` (update entries, append `SelectiveBackupRecord`, save, remove superseded manifest on format switch)
- `_maybe_compress(backup_root: Path, backup_target: Path) -> None`

**Verification:** All unit, integration (`test_backup_engine.py`, `test_dry_run_isolation.py`, `test_sqlite_manifest_integration.py`), e2e (`test_select_backup_e2e.py`), and smoke tests pass with zero test rewrites.

**Effort:** M (≈ 1 day) · **Risk:** low-medium (must preserve exact dry-run gating & selective workflow step ordering).

---

### Q10 — Split monolithic `cli.py` into a `cli/` subpackage 🟠

**Where:** `src/smartbackup/cli.py` (1,301 lines)

**Fix:** Convert `src/smartbackup/cli.py` into `src/smartbackup/cli/`:
```text
src/smartbackup/cli/
├── __init__.py       # Re-exports app, main, __version__, _is_interactive_tty (100% backward compat)
├── app.py            # Typer app, daemon_app, config_app, main()
├── backup.py         # Default backup callback, --select, --prompt, --show-manifest, --verify
├── restore.py        # `restore` subcommand
├── compress.py       # `compress` subcommand
├── daemon.py         # `watch`, `schedule`, `daemon` subcommands
└── config.py         # `config` subcommand group
```

**Compatibility invariant:** Preserve all existing import paths (`from smartbackup.cli import app, main, __version__, _is_interactive_tty, SmartBackup, FolderSelector`) and verify PyInstaller (`--collect-submodules smartbackup`) still bundles cleanly.

**Effort:** M–L (≈ 1–2 days) · **Risk:** medium (many tests patch `smartbackup.cli.*` attributes — re-exports or targeted test patch updates needed).

---

### Q11 — Consolidate fragmented `Console()` instances 🟡

**Where:** `ui/colors.py:25`, `ui/logger.py:48`, `ui/selector.py:211`, `cli.py:39`, `handlers.py:18`, `backup.py:166`, `core/restore.py:349`, `platform/scheduler.py:42,77,117`

**Fix:**
1. Import the themed `console` singleton from `smartbackup.ui.colors` in `cli.py`, `handlers.py`, `backup.py`, `core/restore.py`, and `platform/scheduler.py`.
2. In `BackupLogger` and `FolderSelector`, default `self.console = console or shared_console` (retaining constructor DI for unit tests that inject `Console(file=io.StringIO())`).

**Effort:** S (≈ 2–3 hours) · **Risk:** low (verify `tests/unit/test_logger.py` and `tests/unit/test_selector.py` still pass unchanged).

---

## 6. Phase 4 — Minor Polish, Test Coverage & CI Type-Checking

### Q12 — Pre-1.0 Polish & Quality Gates ⚪

Small, independent improvements that can be batched or landed opportunistically:

| Sub-item | Location | Change | Status |
|---|---|---|---|
| **Q12a** | `src/smartbackup/backup.py:25` | Extract `DEFAULT_MAX_RETRIES = 3` module constant | ✅ fixed (`50d0b65`) |
| **Q12b** | `src/smartbackup/core/scanner.py:124` | Remove redundant `[:6]` slice (`any(ind.exists() for ind in venv_indicators)`) | ✅ fixed (`3c1d6a5`) |
| **Q12c** | `src/smartbackup/models.py` | Track `duration_seconds` via `time.monotonic()` (immune to DST / clock jumps) while keeping `start_time`/`end_time` datetimes for display | ⏳ open |
| **Q12d** | `tests/unit/test_devices.py` | Expand coverage (currently 33 lines) to test `find_backup_device()` space filtering, preferred label matching, multi-drive prompting, and `validate_device()` write failures | ⏳ open |
| **Q12e** | `pyproject.toml`, `.github/workflows/ci.yml` | Add `mypy` to `[project.optional-dependencies].dev` and add a non-strict-then-strict `mypy src/smartbackup/` check to `ci.yml` | ⏳ open |

**Effort:** S–M · **Risk:** low.

---

## 7. Sequencing, effort & risk

```text
Phase 0 (Q1, Q2)        S     🔴 critical correctness & integrity — ship in patch release (0.9.1)
Phase 1 (Q3, Q4, Q5)    S–M   🟠 config safety, migration recovery, non-TTY resilience (0.9.2)
Phase 2 (Q6, Q7, Q8)    S–M   🟠 unified logging, deduplication, cross-platform clarity (0.9.3)
Phase 3 (Q9, Q10, Q11)  M–L   🟠 architectural decomposition before profiles/encryption (0.10.0)
Phase 4 (Q12a–Q12e)     S–M   ⚪ polish, DeviceDetector tests, mypy in CI (1.0.0-rc.1)
```

**Suggested milestones:** `0.9.1` = Phase 0 · `0.9.2` = Phase 1 · `0.9.3` = Phase 2 · `0.10.0` / `1.0.0-rc.1` = Phases 3–4.

---

## 8. Definition of done (per item)

1. Root cause fixed with minimal, focused diff on an isolated feature/fix branch (`fix/...` or `refactor/...`).
2. Unit + regression tests added proving the failure mode before the fix and verifying the fix afterward.
3. Local checks green: `ruff check src/ tests/`, full `pytest -v`, and non-`PYTHONUTF8` CLI smoke (`python main.py --version` / `--help`).
4. GitHub Actions CI green across all three evergreen runners (`ubuntu-latest`, `macos-latest`, `windows-latest`).
5. Zero new runtime dependencies in `pyproject.toml` (strictly `rich` + `typer`).
6. `docs/CHANGELOG.md` updated for user-visible fixes, and [`docs/codebase-analysis.md`](codebase-analysis.md) + this plan updated to mark the item ✅ fixed.

---

## 9. Verification checklist (pre-implementation baselines)

Re-run each check after its phase lands:

```bash
# Q1 — Hash read failure must NOT pass --verify silently
# Corrupt/unreadable file with intact stat() -> verify(..., verify_hashes=True) must return an error
pytest tests/unit/test_manifest_json.py tests/unit/test_manifest_sqlite.py -k "unreadable"

# Q2 — Regex metacharacters in --exclude must not crash
smartbackup --source SRC --target TGT --dry-run --exclude "Backup (1)*" --exclude "C++*"
# must exit 0 and exclude matching files without re.error

# Q3 — Corrupt config.json must warn and preserve backup before overwrite
printf "{invalid-json" > "$CONFIG_FILE"
smartbackup config set manifest_format sqlite
# must print warning AND create config.json.corrupt.* backup instead of silent wipe

# Q4 — Failed legacy migration rename must roll back items out of .migration_temp_*
pytest tests/unit/test_engine_unit.py -k "migration"

# Q5 — Closed stdin on no-device prompt must exit cleanly without EOFError traceback
smartbackup --source SRC < /dev/null

# Q6 — Corrupt manifest warning must respect --quiet and appear in backup log
smartbackup --source SRC --target TGT --quiet   # no raw stderr leak from manifest manager

# Q7–Q12 — Full regression + lint + type check
ruff check src/ tests/
PYTHONUTF8=1 pytest -v
python main.py --version && python main.py --help
```
