# SmartBackup — Plan for Fixing & Wiring Defined-but-Unused Functions

**Status:** proposed · **Target:** post-0.6.0 · **Scope:** features that exist in the codebase
but are unreachable, not applied, or misleading to users

Every item below was verified against the source (grep for call sites + execution where
noted). Locations are `file:line` as of v0.6.0. Companion document:
[`USER_GUIDE.md`](USER_GUIDE.md) §8.5 lists the user-visible symptoms this plan removes.

---

## 1. Executive summary

| ID | Issue | Severity | Type | Phase | Status |
|----|-------|----------|------|-------|--------|
| F1 | `--dry-run` writes/updates the manifest without copying → later real backups silently skip changes | 🔴 **Critical** | Bug (proven) | 0 | ✅ fixed (0.6.1) |
| F2 | `ConfigManager.get_exclusions()` never called → `--exclude` / `config.json` exclusions are inert | 🔴 **High** | Missing wiring | 0 | ✅ fixed (0.6.1) |
| F3 | Restore strategies `NEWER` (implemented) and `RENAME` (stub) not selectable via CLI | 🟠 Medium | Missing wiring | 1 | ⬜ pending |
| F4 | `set_preferred_target()`, `set_device_name()`, `set_preferred_terminal()`, `set/get_auto_watch_cooldown()` have no CLI path | 🟠 Medium | Missing wiring | 2 | ⬜ pending |
| F5 | `watch --cooldown` ignores `auto_watch_cooldown` config (hard-coded default 300) | 🟡 Low-Med | Missing wiring | 2 | ⬜ pending |
| F6 | `SchedulerHelper.setup_scheduled_backup()` (+3 OS helpers) unreachable — no `schedule` command | 🟡 Low | Missing command | 3 | ⬜ pending |
| F7 | `RestoreEngine.list_files()` / `get_manifest_info()` unused — CLI reimplements listing | 🟡 Low | Duplication | 3 | ⬜ pending |
| F8 | `DeviceDetector.validate_device()` unused — duplicates the engine's write test | 🟡 Low | Duplication | 3 | ⬜ pending |
| F9 | `DebounceLock.clear()` unreachable — users must hand-delete `watcher_state.json` | 🟡 Low | Missing wiring | 3 | ⬜ pending |
| F10 | `ManifestFormat.SQLITE`, `FallbackHandler.notify_completion()` desktop notifications | ⚪ Backlog | Roadmap | 4 | ⬜ pending |

---

## 2. Phase 0 — Hotfixes (do first; small diffs, large impact)

> **✅ Status: IMPLEMENTED** on branch `fix/v0.6.0-dryrun-manifest-exclusions` (targets 0.6.1).
> F1: `BackupEngine.is_dry_run` class flag gates legacy-layout migration, manifest
> update+save, and archive creation; `DryRunBackupEngine` sets `is_dry_run = True`.
> F2: `SmartBackup.run(..., exclusions=...)` receives `ConfigManager.get_exclusions()`
> from `cli.py`. Regression tests added in `tests/test_engine.py` and `tests/test_cli.py`;
> all three §9 baselines verified passing.

### F1 — Dry-run must not mutate the manifest 🔴 ✅ fixed

**Where:** `core/engine.py:435-453` (`DryRunBackupEngine`) inherits `run_backup()`
(`core/engine.py:48-175`), whose step 9 (`:139-148`) updates and **saves** the manifest.

**Mechanism:** `_copy_files()` appends simulated successes to `_backed_up_files`
(`:268`), so dry-run feeds phantom entries into `update_from_backup()`, bumps
`backup_count`, and persists — while `deleted_paths` entries are removed from the
manifest even though their files remain on disk.

**Proven impact (executed during doc authoring):**

- Fresh target + dry-run → manifest claims files exist; real run reports `Skipped: 1`
  and copies **nothing**.
- Existing backup, modify file → dry-run → real run: backup remains at the **old**
  content forever (manifest says current).

**Fix (recommended, minimal surface):**

1. In `BackupEngine.run_backup()`, gate steps 8–9 manifest bookkeeping behind
   `if not self._dry_run:` — implement by adding a class attribute
   `_writes_manifest = True` on `BackupEngine`, overridden to `False` on
   `DryRunBackupEngine` (template-method style, consistent with the existing design).
2. Keep `_backed_up_files` collection only when `_writes_manifest` is true (avoids
   misleading summaries too).
3. Optionally skip `backup_target.mkdir()` in dry-run for pristine targets; keep the
   log file write (users want the dry-run report).
4. Summary should label dry-run results (e.g. `Skipped: 0 (dry-run)`) to avoid the
   confusing "Copied: 1" for uncopied files.

**Tests:** `tests/test_engine.py`
- `test_dry_run_does_not_create_manifest`
- `test_dry_run_does_not_update_existing_manifest`
- `test_real_backup_after_dry_run_copies_pending_changes` (regression for the proven scenario)
- `test_dry_run_keeps_deleted_files_in_manifest` (source deletion + dry-run → entry retained)

**Docs:** remove the ⚠️ callouts in `USER_GUIDE.md` §3.1, §4.1, §8.4, §8.5 (item 1);
note the fix in `CHANGELOG.md`.

**Effort:** S (≈ half day incl. tests) · **Risk:** low — behavior becomes *more* conservative.

---

### F2 — Apply custom exclusions (`get_exclusions()` is dead) 🔴

**Where:** `config.py:171-175` defines `get_exclusions()` (only referenced by
`tests/test_config.py`). `cli.py:788-793` persists every `--exclude` value via
`add_exclusion()`, but `backup.py:98-109` constructs `BackupConfig(...)` **without**
`exclusions=`, so the field falls back to `DEFAULT_EXCLUSIONS.copy()`
(`config.py:115`). Result: stored patterns never reach `ExclusionFilter`
(`core/engine.py:59-61`).

**Fix:**

1. `SmartBackup.run()` (`backup.py:30-41`): add parameter
   `exclusions: Optional[Set[str]] = None`; pass to `BackupConfig(exclusions=...)`
   merged as `DEFAULT_EXCLUSIONS | custom` (or call `ConfigManager.get_exclusions()`
   directly inside `run()` — preferred: single source of truth, keeps `cli.py` thin).
2. Keep `--exclude`'s persistence behavior (it is documented as "persists"), but make
   the **current run** apply it immediately (read config *after* the `add_exclusion`
   writes, which the current ordering already allows).
3. Add the inverse operation while here: `ConfigManager.remove_exclusion(pattern)` +
   a CLI path (see F4's `config` subcommand), since today patterns can only be removed
   by hand-editing JSON.

**Tests:** `tests/test_cli.py` / `tests/test_scanner.py`
- `test_exclude_flag_applies_to_current_run` (source with `*.iso` file → excluded)
- `test_custom_exclusions_merge_with_defaults`
- `test_remove_exclusion_roundtrip`

**Docs:** replace the ⚠️ callout in `USER_GUIDE.md` §7.3, §8.4, §8.5 (item 2);
update the `config.json` key table ("settable from CLI: ✅ `--exclude`").

**Effort:** S · **Risk:** low, but **behavior change**: users who saved patterns expecting
them to be inert will now have files excluded — call out in `CHANGELOG.md`.

---

## 3. Phase 1 — Restore conflict strategies

### F3 — Expose `NEWER`, implement `RENAME` 🟠

**Where:** `core/restore.py:23-30` enum; `NEWER` logic exists in
`_restore_single_file()` (`:288-292`) but `restore()` hard-maps the boolean
(`:168-170`): `overwrite → OVERWRITE`, else `SKIP`. `RENAME` has no handler at all
(known dead code — `docs/codebase-analysis.md`).

**Fix:**

1. `RestoreEngine.restore()` → add parameter
   `conflict: Optional[ConflictResolution] = None`; when `None`, keep today's
   `overwrite`-flag mapping (**backward compatible**).
2. Implement `RENAME` in `_restore_single_file()` (`:260-321`): on conflict, write to
   `target.with_stem(f"{target.stem}.restored-{YYYYmmdd-HHMMSS}{target.suffix}")`
   (deterministic, collision-safe loop appending `-1`, `-2`…). Return
   `FileAction.COPIED` with a `Renamed → …` detail so it shows in the summary.
3. CLI (`cli.py:247-274`): add
   `--conflict [skip|overwrite|newer|rename]` (default: `skip`), keep `--overwrite`
   as a hidden alias that sets `conflict=OVERWRITE`; error with exit 1 on unknown value.
   Validate precedence: if both `--conflict` and `--overwrite` are given, `--conflict` wins
   (document it).

**Tests:** `tests/test_restore.py`
- `test_conflict_newer_skips_older_backup`, `test_conflict_newer_overwrites_older`
- `test_conflict_rename_keeps_both_files`
- `test_overwrite_flag_alias_still_works` (regression)

**Docs:** `USER_GUIDE.md` §4.3 (new flag), §6.4 (availability column → ✅), §8.5 (item 3).

**Effort:** M (≈ 1–2 days) · **Risk:** low — additive flags; default behavior unchanged.

---

## 4. Phase 2 — Config setters need a front door

### F4 — `config` subcommand group 🟠

**Dead surface (verified):** `set_preferred_target()` (`config.py:185-189`),
`set_device_name()` (`:196-200`), `set_auto_watch_cooldown()` (`:207-211`),
`set_preferred_terminal()` (`:218-222`) — only tests call them. Their **getters** are
live (`get_preferred_target` → `cli.py:796`; `get_device_name` → `watcher.py:80`;
`get_preferred_terminal` → `terminal.py:129,187`), so users can benefit from keys they
have no supported way to write. `USER_GUIDE.md` §7.2 currently says "❌ edit JSON manually"
for four keys.

**Fix:** new Typer group mirroring the existing `daemon` group (`cli.py:40-47`):

```text
smartbackup config list                       # pretty table of effective config
smartbackup config get <key>                  # one value
smartbackup config set <key> <value>          # validated write
smartbackup config unset <key>                # remove key
smartbackup config exclude <pattern>...       # add exclusion (wraps add_exclusion)
smartbackup config unexclude <pattern>...     # new: wraps F2's remove_exclusion
```

Allowed keys with validation: `preferred_target` (str), `device_name` (str, sanitized via
`platform.identity` rules), `auto_watch_cooldown` (int ≥ 0), `preferred_terminal` (str;
hint values `iterm`/`iterm2` on macOS), `exclusions` (list — via `exclude`/`unexclude`).
Unknown key → exit 1 with the valid-key list.

### F5 — `watch` should honor `auto_watch_cooldown` 🟡

**Where:** `cli.py:73-74` defaults `--cooldown` to `300`; `watcher.py:263` takes it as a
constructor arg; nothing reads `get_auto_watch_cooldown()` (`config.py:213-216`).

**Fix:** default `--cooldown` to `None`; in `_handle_watch()`, resolve
`cooldown = cooldown if cooldown is not None else ConfigManager().get_auto_watch_cooldown()`.
CLI flag keeps precedence over config, config over hard-coded 300.

**Tests:** `tests/test_daemon_cli.py` — `test_watch_uses_configured_cooldown`,
`test_watch_flag_overrides_configured_cooldown`.

**Docs:** `USER_GUIDE.md` §4.5 (default column → "config `auto_watch_cooldown`, else 300"),
§7.2 (flip the ❌ cells for all four keys), §8.5 (item 4).

**Effort:** M (group + validation ≈ 1–2 days) · **Risk:** low.

---

## 5. Phase 3 — Housekeeping (reachability & duplication)

### F6 — Expose `setup_scheduled_backup()` as `smartbackup schedule` 🟡

`scheduler.py:26-36` dispatches to three recipe printers (`:39-149`) that are only reachable
from tests. **Fix:** add `smartbackup schedule [--hours N]` that prints the OS-specific
instructions (Windows `schtasks` panel, macOS launchd plist, Linux cron + systemd user timer)
— i.e. surface the existing code, optionally improved to emit
`python -m smartbackup` instead of the current `scheduler.py` path (which isn't a runnable
entry point — see `scheduler.py:29,32`).
Tests: reuse `tests/test_scheduler.py` dispatch assertions + a CLI invoke test.
Docs: `USER_GUIDE.md` §5.5 gains the command (keep the manual recipes as fallback).

### F7 — Stop duplicating restore listing 🟡

`RestoreEngine.list_files()` (`restore.py:356-367`) and `get_manifest_info()`
(`:369-387`) are unused; `cli.py:296-316` hand-rolls manifest iteration/rglob.
**Fix:** `_handle_restore --list` → construct `RestoreEngine` and call
`list_files(patterns)`; optionally surface `get_manifest_info()` as
`smartbackup restore --manifest-info` or fold into `--show-manifest`.
Preserves filtering behavior — update `tests/test_cli.py` expectations.

### F8 — Unify the writability check 🟡

`DeviceDetector.validate_device()` (`devices.py:85-97`) writes `.backup_test_write`;
`BackupEngine._validate_paths()` (`engine.py:240-247`) writes `.write_test` — two
implementations, one unreachable (flagged in `codebase-analysis.md:542`).
**Fix:** engine calls `DeviceDetector(logger).validate_device(path)` (inject the logger),
delete the inline block; or delete `validate_device()` if the engine's richer error
messages are preferred. Choose one — don't keep both.

### F9 — Debounce reset command 🟡

`DebounceLock.clear()` (`watcher.py:238-247`) is unreachable; the User Guide tells users to
delete `watcher_state.json` by hand. **Fix (pick one):**
- `smartbackup watch --reset-debounce` (clear state, then start), or
- `smartbackup daemon clear-state` / `watcher clear`.

Recommendation: a standalone `smartbackup daemon clear-state` so it works while the daemon
is *stopped* and doesn't imply "reset then watch". Tests: state file removed, next
`should_prompt()` returns True.

### F10 — Minor cleanups 🟡

- `FallbackHandler.notify_completion()` (`handlers.py:82-87`) — either implement desktop
  notifications (Windows toast / `osascript` / `notify-send`) behind a `--notify` flag, or
  document as a stub and stop advertising it.
- `DeviceWatcher.start(blocking=False)` (`watcher.py:385-408`) — prod code always blocks;
  keep (tested) but it's fine as-is.
- Remove/repair stale links if `docs/codebase-analysis.md` findings are resolved.

---

## 6. Phase 4 — Backlog (explicitly out of scope for wiring)

| Item | Notes |
|------|-------|
| `ManifestFormat.SQLITE` backend | Enum only (`manifest/base.py:21`); needs a `SqliteManifestManager(ManifestManager)` + format switch in `JsonManifestManager.load` detection. Target: >100k files. |
| Desktop notifications (F10) | Per-OS APIs; nice-to-have. |
| `BackupConfig.manifest_format` | Wire to config once SQLite exists. |
| Restore from archives directly | Today `restore` reads directories only (`USER_GUIDE.md` §6.5). Consider `restore --from-archive` using `BackupCompressor`'s inverse. |

---

## 7. Sequencing, effort & risk

```text
Phase 0 (F1, F2)      S     🔴 critical correctness — ship in next patch release (0.6.1)
Phase 1 (F3)          M     🟠 user-facing feature gap
Phase 2 (F4, F5)      M     🟠 completes the config story
Phase 3 (F6–F9)       S–M   🟡 cleanup / reachability
Phase 4 (F10+)        —     ⚪ backlog
```

**Suggested milestones:** `0.6.1` = Phase 0 · `0.7.0` = Phases 1–2 · `0.7.x` = Phase 3.

## 8. Definition of done (per item)

1. Function has a production call path (CLI or pipeline), not just tests.
2. Unit + regression tests (Phase 0 items require the exact scenarios proven above).
3. `pytest` green · `ruff check .` clean · no new warnings.
4. `USER_GUIDE.md` updated: remove/adjust the ⚠️ callouts and the ❌ cells in §7.2,
   add new flags/commands to §4 and Appendix A.
5. `CHANGELOG.md` entry, flagging behavior changes (F1 dry-run no longer writes state;
   F2 exclusions now apply).
6. `smartbackup --help` output re-captured so docs match reality.

## 9. Verification checklist (pre-implementation baselines)

Recorded while authoring the docs, to re-run after each fix:

```bash
# F1 (WAS FAILING — now PASSING, verified after Phase 0)
python main.py --source SRC --target TGT --dry-run
test ! -f TGT/Documents-Backup/DEV/.smartbackup_manifest.json   # fresh target
# then a real run must copy the files  ✅ verified

# F2 (WAS FAILING — now PASSING, verified after Phase 0)
python main.py --source SRC --target TGT --exclude "*.iso"
# a *.iso file in SRC must NOT appear in TGT  ✅ verified
# (and the pattern persists: later runs exclude *.iso without the flag)

# F3 (currently unavailable — Phase 1)
smartbackup restore --source TGT --conflict newer    # must be accepted
smartbackup restore --source TGT --conflict rename    # must keep both files
```
