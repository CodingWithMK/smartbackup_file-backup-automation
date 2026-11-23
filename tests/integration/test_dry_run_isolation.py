"""
Integration tests for --dry-run isolation guarantees (Phase 0 / F1).

Covers:
1. Mutation gates proven by spying on JsonManifestManager.save,
   BackupEngine._migrate_legacy_layout, and BackupCompressor.compress,
   paired with real-run counterpart tests.
2. End-state parity through SmartBackup.run().
"""

import json
from pathlib import Path

import pytest

from smartbackup import SmartBackup
from smartbackup.core.compressor import BackupCompressor
from smartbackup.core.engine import BackupEngine
from smartbackup.manifest.json_manifest import JsonManifestManager

DEVICE = "DryRunBox"


def _run(source: Path, target: Path, dry_run: bool = False, **kwargs) -> bool:
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
    target = root / name
    target.mkdir()
    return target


def _snapshot(root: Path) -> dict:
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
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("created", None)
    data.pop("updated", None)
    data["files"] = {
        name: {k: v for k, v in meta.items() if k != "backed_up_at"}
        for name, meta in data.get("files", {}).items()
    }
    return data


def _source_state(root: Path, *, exclude_logs: bool = False) -> dict:
    state = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if exclude_logs and "_backup_logs" in rel:
            continue
        state[rel] = (path.stat().st_size, path.stat().st_mtime_ns)
    return state


@pytest.fixture
def manifest_saves(monkeypatch):
    calls = []
    original = JsonManifestManager.save

    def spy(self, manifest):
        calls.append(self)
        return original(self, manifest)

    monkeypatch.setattr(JsonManifestManager, "save", spy)
    return calls


@pytest.fixture
def migration_calls(monkeypatch):
    calls = []
    original = BackupEngine._migrate_legacy_layout

    def spy(self, backup_root):
        calls.append(Path(backup_root))
        return original(self, backup_root)

    monkeypatch.setattr(BackupEngine, "_migrate_legacy_layout", spy)
    return calls


@pytest.fixture
def compress_calls(monkeypatch):
    calls = []
    original = BackupCompressor.compress

    def spy(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BackupCompressor, "compress", spy)
    return calls


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

        assert _run(src, target) is True
        assert len(manifest_saves) == 1
        manifest_saves.clear()

        (src / "report.txt").write_text("V2")
        assert _run(src, target, dry_run=True) is True
        assert manifest_saves == []

    def test_real_run_still_saves_manifest(self, tmp_path, manifest_saves):
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
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, compress_format="zip") is True

        assert len(compress_calls) == 1
        assert list(target.rglob("*.zip"))


class TestDryRunStateParity:
    """Through SmartBackup.run(): dry-runs must be invisible in the end state."""

    @staticmethod
    def _mutate_source(src: Path) -> None:
        (src / "report.txt").write_text("V2")
        (src / "new.txt").write_text("added later")
        (src / "doomed.txt").unlink()

    def test_dry_run_interleaved_sequence_matches_pure_real_sequence(self, tmp_path):
        src = _make_source(tmp_path)
        target_a = _make_target(tmp_path, "target_with_dry_runs")
        target_b = _make_target(tmp_path, "target_without_dry_runs")

        assert _run(src, target_a) is True
        self._mutate_source(src)
        assert _run(src, target_a, dry_run=True) is True
        assert _run(src, target_a, dry_run=True) is True
        assert _run(src, target_a) is True

        assert _run(src, target_b) is True
        assert _run(src, target_b) is True

        snap_a = _snapshot(_backup_root(target_a))
        snap_b = _snapshot(_backup_root(target_b))
        assert snap_a, "backup tree A is empty - parity would pass vacuously"
        assert len(snap_a) == 3, f"expected 3 backed-up files, got {sorted(snap_a)}"
        assert snap_a.keys() == snap_b.keys()
        for name in snap_a:
            assert snap_a[name] == snap_b[name], f"content mismatch in {name}"

        norm_a = _normalized_manifest(_manifest_path(target_a))
        norm_b = _normalized_manifest(_manifest_path(target_b))
        assert norm_a["backup_count"] == 2
        assert len(norm_a["files"]) == 3
        assert norm_a == norm_b

    def test_dry_run_leaves_source_tree_untouched(self, tmp_path):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)
        before = _source_state(src)

        assert _run(src, target, dry_run=True) is True
        assert _source_state(src) == before

    def test_dry_run_never_writes_log_or_creates_target_dir(self, tmp_path):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=True) is True
        assert list(target.rglob("*.log")) == []
        assert list(target.rglob("*")) == []

    def test_real_run_writes_log_report(self, tmp_path):
        src = _make_source(tmp_path)
        target = _make_target(tmp_path)

        assert _run(src, target, dry_run=False) is True
        assert list(target.rglob("*.log")) != []

    def test_repeated_dry_runs_are_idempotent(self, tmp_path):
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
