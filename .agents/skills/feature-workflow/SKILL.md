---
name: Feature & Bugfix Workflow
description: Use when building a new feature, fixing a bug, or implementing a planned change in this repo - covers the full loop from plan first, to exhaustive layered tests, version bump, tests/ruff verification, and semantic commits.
---

# Feature & Bugfix Workflow

The proven workflow for adding features and fixing bugs in SmartBackup.
Follow every phase in order; do not skip the plan, the tests, or the verification.

## Phase 1 — Plan before code

1. **Research the actual source first.** Read the relevant modules
   (`src/smartbackup/cli.py`, `config.py`, `backup.py`, `core/engine.py`,
   `core/restore.py`, `platform/watcher.py`, `platform/scheduler.py`) before
   proposing anything.
2. **Never hallucinate CLI commands, flags, or defaults.** Every claim in the
   plan or docs must be grounded in the real source. If the code and the docs
   disagree, the code wins — document actual behavior.
3. Write the plan as a doc when the change is non-trivial
   (e.g. `docs/PLAN_*.md`): inventory each finding/fix with an ID, status
   checkbox, and the file/line it lives in.
4. Present the plan for approval before implementing.

## Phase 2 — Branch

- Name it in the current branch's style: `type/v<version>-<semantic-description>`,
  e.g. `fix/v0.6.1-dryrun-manifest-exclusions`.
- The version in the branch name is the version this branch ships.

## Phase 3 — Implement + tests to the limits

Write the fix, then push the test coverage as far as it reasonably goes:

- **Unit tests** — spies/mocks proving the gate fires, plus real-run
  counterparts so a broken gate cannot hide behind a stub.
- **Integration tests** — real CLI/engine wiring (not mocked), with an
  isolated config so the user's real config is never touched.
- **E2E tests** — invoke the actual command path end to end.
- **Sandbox/smoke tests** — subprocess runs with `APPDATA`/`HOME` redirected
  (register a marker in `pyproject.toml` if you add one).
- **Non-vacuity guards** — assert the test actually did work
  (e.g. `backup_count == 2`, expected file count), so a silently-skipped
  operation cannot pass.
- **Control tests** — a negative/control case proving the test setup itself
  would catch a regression.

Test file naming: one focused file per concern, e.g.
`tests/test_<feature>_<aspect>.py`.

## Phase 4 — Version bump (if the branch ships a release)

Bump **everywhere** in the branch, not just one file:

- `pyproject.toml`, `src/smartbackup/__init__.py`, `src/smartbackup/cli.py`
  (`__version__` + banner), version tests (rename `..._is_0_6_0` → current),
  `README.md`, `docs/USER_GUIDE.md`, `docs/CHANGELOG.md` (new section with
  date), and any plan doc referencing the branch.

## Phase 5 — Verify before every commit

```powershell
$env:PYTHONUTF8="1"; python -m pytest tests/ -q     # all green
$env:PYTHONUTF8="1"; python -m ruff check .          # zero errors
```

- `PYTHONUTF8=1` is required on this machine (cp1252 console breaks the Rich
  banner otherwise).
- Ruff baseline must stay at zero new errors — fix new violations in the same
  change that introduces them.
- If a lint fix touches tests, re-run the suite: autofixers can remove an
  assignment whose right-hand side had side effects.

## Phase 6 — Semantic commits, never one bulk dump

Split work into commits by meaning, each with a good one-line subject and a
body explaining *why*:

- `fix(scope): ...` — behavior fixes
- `test(...)` / `fix(test): ...` — test additions and test corrections
- `docs(...): ...` — documentation
- `style: ...` / `chore(lint): ...` — lint and formatting
- `refactor(cli): ...` — structural changes with no behavior change
- release/version bumps as their own commit

Never `git add -A` everything into one commit. Stage file by file
(`git add <path>`) and commit each semantic unit separately. Write the commit
body: what changed and why it is safe (e.g. "no control-flow or exit-code
changes", "full suite re-run: N passed").
