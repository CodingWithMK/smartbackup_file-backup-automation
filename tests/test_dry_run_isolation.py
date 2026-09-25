"""
Isolation guarantees for --dry-run (Phase 0 / F1 fix).

Two testing layers:

1. Unit - mutation gates proven by spying on the three collaborators that
   used to be mutated during a dry-run:
     * JsonManifestManager.save             (manifest persistence)
     * BackupEngine._migrate_legacy_layout  (legacy layout reorganization)
     * BackupCompressor.compress            (archive creation)
   Every gate also has a counterpart test proving real runs still call the
   collaborator, guarding against over-blocking.

2. Integration - state parity through the public API (SmartBackup.run()):
   a backup sequence interleaved with dry-runs must produce the same backup
   tree and an equivalent manifest as the same sequence without dry-runs.
   Plus direct contracts: the source is never touched, the run log is
   still written.
"""

import json
from pathlib import Path

import pytest

from smartbackup import SmartBackup
from smartbackup.core.compressor import BackupCompressor
from smartbackup.core.engine import BackupEngine
from smartbackup.manifest.json_manifest import JsonManifestManager

DEVICE = "DryRunBox"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _run(source: Path, target: Path, dry_run: bool = False, **kwargs) -> bool:
    """Invoke the public API exactly the way the CLI does."""
    return SmartBackup().run(
        custom_source=source,
        custom_target=target,
        device_name=DEVICE,
        dry_run=dry_run,
        **kwargs,
    )


def _backup_root(target: Path) -> Path:
    return target / "Documents-Backup" / DEVICE


def _manifest_path(target: Path) -> Path:
    return _backup_root(target) / ".smartbackup_manifest.json"


def _make_source(root: Path) -> Path:
    src = root / "source"
    (src / "sub").mkdir(parents=True)
    (src / "report.txt").write_text("V1")
    (src / "sub" / "child.txt").write_text("child")
    (src / "doomed.txt").write_text("will be deleted")
    return src


def _make_target(root: Path, name: str = "target") -> Path:
    """Create the backup medium.

    The engine validates that the target (the 'medium') exists before doing
    anything, so every test must mount one explicitly - just like a real
    external drive is mounted before a backup.
    """
    target = root / name
    target.mkdir()
    return target


def _snapshot(root: Path) -> dict:
    """relpath -> content bytes, excluding run logs and the manifest itself.

    Logs are timestamped by design and the manifest is compared separately
    with volatile fields normalized, so neither belongs in a byte-level
    tree comparison.
    """
    snap = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if "_backup_logs" in rel or rel.endswith(".smartbackup_manifest.json"):
            continue
        snap[rel] = path.read_bytes()
    return snap


def _normalized_manifest(path: Path) -> dict:
    """Manifest with wall-clock fields removed; everything else must match."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("created", None)
    data.pop("updated", None)
    data["files"] = {
        name: {k: v for k, v in meta.items() if k != "backed_up_at"}
        for name, meta in data.get("files", {}).items()
    }
    return data


def _source_state(root: Path, *, exclude_logs: bool = False) -> dict:
    """relpath -> (size, mtime_ns). `exclude_logs` skips the timestamped
    run logs, which legitimately differ between invocations."""
    state = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if exclude_logs and "_backup_logs" in rel:
            continue
        state[rel] = (path.stat().st_size, path.stat().st_mtime_ns)
    return state


# --------------------------------------------------------------------------- #
# Spies (unit layer)
# --------------------------------------------------------------------------- #
@pytest.fixture
def manifest_saves(monkeypatch):
    """Records every manifest persistence while still performing the real save."""
    calls = []
    original = JsonManifestManager.save

    def spy(self, manifest):
        calls.append(self)
        return original(self, manifest)

    monkeypatch.setattr(JsonManifestManager, "save", spy)
    return calls


@pytest.fixture
def migration_calls(monkeypatch):
    """Records legacy-layout migrations while still performing them."""
    calls = []
    original = BackupEngine._migrate_legacy_layout

    def spy(self, backup_root):
        calls.append(Path(backup_root))
        return original(self, backup_root)

    monkeypatch.setattr(BackupEngine, "_migrate_legacy_layout", spy)
    return calls


@pytest.fixture
def compress_calls(monkeypatch):
    """Records archive creations while still performing them."""
    calls = []
    original = BackupCompressor.compress

    def spy(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BackupCompressor, "compress", spy)
    return calls


# --------------------------------------------------------------------------- #
# Unit: mutation gates
# --------------------------------------------------------------------------- #
class TestDryRunMutationGates:
    """Dry-run must never call the three state-mutating collaborators."""

    def test_dry_run_fresh_target_never_saves_manifest(self, tmp_path, manifest_saves):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=True) is True

        assert manifest_saves == []

    def test_dry_run_existing_backup_never_saves_manifest(self, tmp_path, manifest_saves):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target) is True  # baseline real run persists once
        assert len(manifest_saves) == 1
        manifest_saves.clear()

        (src / "report.txt").write_text("V2")  # pending change
        assert _run(src, target, dry_run=True) is True

        assert manifest_saves == []  # the gate held with work pending

    def test_real_run_still_saves_manifest(self, tmp_path, manifest_saves):
        """Counterpart: the gate must not over-block real runs."""
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target) is True

        assert len(manifest_saves) == 1

    @staticmethod
    def _make_legacy_layout(target: Path) -> Path:
        legacy_root = target / "Documents-Backup"
        legacy_root.mkdir(parents=True)
        (legacy_root / "old.txt").write_text("legacy content")
        (legacy_root / ".smartbackup_manifest.json").write_text(
            json.dumps({"version": 1, "format": "json"}), encoding="utf-8"
        )
        return legacy_root

    def test_dry_run_never_migrates_legacy_layout(self, tmp_path, migration_calls):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)
        legacy_root = self._make_legacy_layout(target)

        assert _run(src, target, dry_run=True) is True

        assert migration_calls == []
        assert (legacy_root / "old.txt").exists()
        assert not (legacy_root / DEVICE / "old.txt").exists()

    def test_real_run_migrates_legacy_layout(self, tmp_path, migration_calls):
        """Counterpart: a real run must still reorganize a legacy layout."""
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)
        legacy_root = self._make_legacy_layout(target)

        assert _run(src, target) is True

        assert len(migration_calls) == 1
        assert (legacy_root / DEVICE / "old.txt").exists()
        assert not (legacy_root / "old.txt").exists()

    @pytest.mark.parametrize("fmt, ext", [("zip", "*.zip"), ("tar.gz", "*.tar.gz")])
    def test_dry_run_never_compresses(self, tmp_path, compress_calls, fmt, ext):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=True, compress_format=fmt) is True

        assert compress_calls == []
        assert list(target.rglob(ext)) == []

    def test_real_run_compresses(self, tmp_path, compress_calls):
        """Counterpart: a real run must still create the requested archive."""
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, compress_format="zip") is True

        assert len(compress_calls) == 1
        assert list(target.rglob("*.zip"))


# --------------------------------------------------------------------------- #
# Integration: end-state parity and direct contracts
# --------------------------------------------------------------------------- #
class TestDryRunStateParity:
    """Through SmartBackup.run(): dry-runs must be invisible in the end state."""

    @staticmethod
    def _mutate_source(src: Path) -> None:
        (src / "report.txt").write_text("V2")
        (src / "new.txt").write_text("added later")
        (src / "doomed.txt").unlink()

    def test_dry_run_interleaved_sequence_matches_pure_real_sequence(self, tmp_path):
        """The core invariant: interleaving dry-runs changes nothing at the end.

        Path A: baseline -> mutate -> dry-run x2 -> final real run.
        Path B: same source (already mutated) -> baseline -> final real run.
        The two backup trees and manifests must be indistinguishable.
        """
        src = _make_source(tmp_path)
        target_a = _make_target(tmp_path, "target_with_dry_runs")
        target_b = _make_target(tmp_path, "target_without_dry_runs")

        # Path A: dry-runs interleaved
        assert _run(src, target_a) is True
        self._mutate_source(src)
        assert _run(src, target_a, dry_run=True) is True
        assert _run(src, target_a, dry_run=True) is True
        assert _run(src, target_a) is True

        # Path B: identical source, no dry-runs anywhere
        assert _run(src, target_b) is True
        assert _run(src, target_b) is True

        snap_a = _snapshot(_backup_root(target_a))
        snap_b = _snapshot(_backup_root(target_b))
        # Non-vacuity guards: if setup ever breaks, fail loudly instead of
        # comparing two empty states.
        assert snap_a, "backup tree A is empty - parity would pass vacuously"
        assert len(snap_a) == 3, f"expected 3 backed-up files, got {sorted(snap_a)}"
        assert snap_a.keys() == snap_b.keys()
        for name in snap_a:
            assert snap_a[name] == snap_b[name], f"content mismatch in {name}"

        norm_a = _normalized_manifest(_manifest_path(target_a))
        norm_b = _normalized_manifest(_manifest_path(target_b))
        assert norm_a["backup_count"] == 2  # exactly two real runs per path
        assert len(norm_a["files"]) == 3  # final source state: 3 files
        assert norm_a == norm_b

    def test_dry_run_leaves_source_tree_untouched(self, tmp_path):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)
        before = _source_state(src)

        assert _run(src, target, dry_run=True) is True

        assert _source_state(src) == before

    def test_dry_run_still_writes_the_run_log_report(self, tmp_path):
        """Dry-run keeps its preview report even though it persists no state."""
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=True) is True

        assert list(target.rglob("*.log")) != []

    def test_repeated_dry_runs_are_idempotent(self, tmp_path):
        """A second dry-run observes exactly the same state as the first."""
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=True) is True
        state_after_first = _source_state(target, exclude_logs=True)
        manifest_bytes_after_first = (
            _manifest_path(target).read_bytes() if _manifest_path(target).exists() else None
        )

        assert _run(src, target, dry_run=True) is True

        assert _source_state(target, exclude_logs=True) == state_after_first
        manifest_bytes_after_second = (
            _manifest_path(target).read_bytes() if _manifest_path(target).exists() else None
        )
        assert manifest_bytes_after_second == manifest_bytes_after_first
