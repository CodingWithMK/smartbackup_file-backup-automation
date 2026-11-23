"""
End-to-end tests for Interactive Selective Folder Backup (--select).

Covers:
1. Full backup -> selective backup lifecycle with unselected-folder immunity
   across JSON manifest, SQLite manifest (verifying dedicated selective_backups
   table), and --no-manifest (ChangeDetector).
2. Root-relative path layout and RestoreEngine compatibility.
3. Emptied selected folder deletion syncing without touching unselected folders.
4. Dedicated SELECTIVE BACKUP (--select) + SELECTIVE WORKFLOW TRACE log section.
5. --select --dry-run zero-write isolation (no dirs, files, manifest, or logs).
6. JSON <-> SQLite manifest format migration preserving selective_backups history.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from smartbackup import (
    RestoreEngine,
    SelectionMetadata,
    SmartBackup,
    get_manifest_manager,
)
from smartbackup.ui.logger import BackupLogger

DEVICE = "SelectE2EBox"


def _create_documents(root: Path) -> Path:
    src = root / "Documents"
    (src / "Projects").mkdir(parents=True)
    (src / "Finance").mkdir(parents=True)
    (src / "Photos").mkdir(parents=True)
    (src / "Projects" / "app.py").write_text("print('v1')")
    (src / "Projects" / "obsolete.py").write_text("will be deleted")
    (src / "Finance" / "budget.csv").write_text("item,cost\nrent,1000\n")
    (src / "Photos" / "trip.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    (src / "root_note.txt").write_text("root level note")
    return src


def _selection_meta(src: Path, selected: list[str]) -> SelectionMetadata:
    return SelectionMetadata(
        command_option="--select",
        source_root=str(src),
        available_folders=["Finance", "Photos", "Projects"],
        selected_folders=list(selected),
        excluded_folders_count=0,
        workflow_steps=[
            "CLI invoked with --select",
            f"Discovered 3 selectable folder(s) (0 hidden/excluded skipped) in {src}",
            f"User confirmed {len(selected)} of 3 folder(s): {', '.join(selected)}",
        ],
    )


class TestSelectiveBackupE2E:
    """Full lifecycle end-to-end tests for --select folder backups."""

    @pytest.mark.parametrize("manifest_format", ["json", "sqlite"])
    def test_full_then_selective_preserves_unselected_folders_and_audits_manifest(
        self, tmp_path: Path, manifest_format: str
    ) -> None:
        src = _create_documents(tmp_path)
        target = tmp_path / "drive"
        target.mkdir()
        backup_root = target / "Documents-Backup" / DEVICE

        # 1. Full initial backup
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                manifest_format=manifest_format,
            )
            is True
        )
        assert (backup_root / "Projects" / "app.py").exists()
        assert (backup_root / "Finance" / "budget.csv").exists()
        assert (backup_root / "Photos" / "trip.jpg").exists()
        assert (backup_root / "root_note.txt").exists()

        # 2. Mutate both selected (Projects) and unselected (Finance) folders
        (src / "Projects" / "app.py").write_text("print('v2-updated')")
        (src / "Projects" / "obsolete.py").unlink()
        (src / "Projects" / "new_module.py").write_text("NEW = True")
        # Delete Finance/budget.csv on source -> MUST stay intact on backup because Finance is unselected!
        (src / "Finance" / "budget.csv").unlink()
        (src / "root_note.txt").unlink()

        # 3. Selective backup of Projects only
        meta = _selection_meta(src, ["Projects"])
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                manifest_format=manifest_format,
                selected_folders=["Projects"],
                selection_metadata=meta,
            )
            is True
        )

        # Selected folder changes synced cleanly with root-relative paths
        assert (backup_root / "Projects" / "app.py").read_text() == "print('v2-updated')"
        assert (backup_root / "Projects" / "new_module.py").read_text() == "NEW = True"
        assert not (backup_root / "Projects" / "obsolete.py").exists()

        # Unselected folders and root files remain 100% IMMUNE
        assert (backup_root / "Finance" / "budget.csv").exists()
        assert (backup_root / "Photos" / "trip.jpg").exists()
        assert (backup_root / "root_note.txt").exists()

        # Manifest audit checks (both JSON and SQLite)
        mgr = get_manifest_manager(backup_root, manifest_format)
        manifest = mgr.load()
        assert manifest is not None
        assert manifest.last_backup_mode == "select"
        assert manifest.last_selected_folders == ["Projects"]
        assert len(manifest.selective_backups) == 1

        rec = manifest.selective_backups[0]
        assert rec.command_option == "--select"
        assert rec.scope == "folders"
        assert rec.selected_folders == ["Projects"]
        assert rec.files_copied == 1
        assert rec.files_updated == 1
        assert rec.files_deleted == 1
        assert any("Scoped scan completed" in step for step in rec.workflow_steps)
        assert any("unselected folders untouched" in step for step in rec.workflow_steps)

        # Unselected entries remain tracked in manifest
        assert manifest.has_entry(str(Path("Finance/budget.csv")))
        assert manifest.has_entry(str(Path("Photos/trip.jpg")))
        assert manifest.has_entry("root_note.txt")
        assert not manifest.has_entry(str(Path("Projects/obsolete.py")))

        # Format-specific separation verification
        if manifest_format == "json":
            raw = json.loads(mgr.manifest_path.read_text(encoding="utf-8"))
            assert raw["last_backup_mode"] == "select"
            assert raw["last_selected_folders"] == ["Projects"]
            assert len(raw["selective_backups"]) == 1
        else:
            conn = sqlite3.connect(str(mgr.manifest_path))
            try:
                rows = conn.execute(
                    "SELECT command_option, selected_folders FROM selective_backups"
                ).fetchall()
                assert len(rows) == 1
                assert rows[0][0] == "--select"
                assert json.loads(rows[0][1]) == ["Projects"]
            finally:
                conn.close()

        # Log file contains dedicated SELECTIVE BACKUP (--select) section before SUMMARY:
        logs = sorted((backup_root / "_backup_logs").glob("backup_*.log"))
        assert logs, "expected backup log file on real run"
        log_text = logs[-1].read_text(encoding="utf-8")
        assert "Mode:       Selective (--select)" in log_text
        assert "SELECTIVE BACKUP (--select)" in log_text
        assert "Command Option:    --select" in log_text
        assert "[x] Projects/" in log_text
        assert "SELECTIVE WORKFLOW TRACE:" in log_text
        assert log_text.index("SELECTIVE BACKUP (--select)") < log_text.index("SUMMARY:")

        # RestoreEngine seamlessly restores root-relative selective backup
        restore_dir = tmp_path / "restored"
        restore_result = RestoreEngine(
            backup_path=target,
            target_path=restore_dir,
            logger=BackupLogger(verbose=False),
            device_name=DEVICE,
        ).restore(patterns=["Projects/*"])
        assert restore_result.errors == 0
        assert (restore_dir / "Projects" / "app.py").read_text() == "print('v2-updated')"
        assert (restore_dir / "Projects" / "new_module.py").exists()

    def test_selective_backup_no_manifest_fallback_protects_unselected_folders(
        self, tmp_path: Path
    ) -> None:
        src = _create_documents(tmp_path)
        target = tmp_path / "drive"
        target.mkdir()
        backup_root = target / "Documents-Backup" / DEVICE

        # Full backup without manifest
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                use_manifest=False,
            )
            is True
        )

        # Delete a file in Projects AND a file in Finance
        (src / "Projects" / "obsolete.py").unlink()
        (src / "Finance" / "budget.csv").unlink()

        # Selective backup of Projects without manifest
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                use_manifest=False,
                selected_folders=["Projects"],
                selection_metadata=_selection_meta(src, ["Projects"]),
            )
            is True
        )

        assert not (backup_root / "Projects" / "obsolete.py").exists()
        assert (backup_root / "Finance" / "budget.csv").exists()

    def test_emptying_selected_folder_syncs_deletions_without_affecting_others(
        self, tmp_path: Path
    ) -> None:
        src = _create_documents(tmp_path)
        target = tmp_path / "drive"
        target.mkdir()
        backup_root = target / "Documents-Backup" / DEVICE

        assert (
            SmartBackup().run(
                custom_source=src, custom_target=target, device_name=DEVICE
            )
            is True
        )

        # Remove ALL files inside Projects
        for child in (src / "Projects").iterdir():
            child.unlink()

        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                selected_folders=["Projects"],
                selection_metadata=_selection_meta(src, ["Projects"]),
            )
            is True
        )

        assert not (backup_root / "Projects" / "app.py").exists()
        assert not (backup_root / "Projects" / "obsolete.py").exists()
        assert (backup_root / "Finance" / "budget.csv").exists()

    def test_select_dry_run_writes_nothing_to_target(self, tmp_path: Path) -> None:
        src = _create_documents(tmp_path)
        target = tmp_path / "fresh_drive"
        target.mkdir()

        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                dry_run=True,
                selected_folders=["Projects"],
                selection_metadata=_selection_meta(src, ["Projects"]),
            )
            is True
        )

        # True zero-write isolation: no directories, files, manifest, or logs
        assert list(target.rglob("*")) == []

        # Control: real selective run DOES write files, manifest, and log
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                dry_run=False,
                selected_folders=["Projects"],
                selection_metadata=_selection_meta(src, ["Projects"]),
            )
            is True
        )
        backup_root = target / "Documents-Backup" / DEVICE
        assert (backup_root / "Projects" / "app.py").exists()
        assert (backup_root / ".smartbackup_manifest.json").exists()
        assert list((backup_root / "_backup_logs").glob("backup_*.log")) != []

    def test_manifest_migration_json_to_sqlite_preserves_selective_history(
        self, tmp_path: Path
    ) -> None:
        src = _create_documents(tmp_path)
        target = tmp_path / "drive"
        target.mkdir()
        backup_root = target / "Documents-Backup" / DEVICE

        # First selective run using JSON
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                manifest_format="json",
                selected_folders=["Projects"],
                selection_metadata=_selection_meta(src, ["Projects"]),
            )
            is True
        )
        assert (backup_root / ".smartbackup_manifest.json").exists()

        # Second selective run migrating to SQLite
        assert (
            SmartBackup().run(
                custom_source=src,
                custom_target=target,
                device_name=DEVICE,
                manifest_format="sqlite",
                selected_folders=["Finance"],
                selection_metadata=_selection_meta(src, ["Finance"]),
            )
            is True
        )

        assert (backup_root / ".smartbackup_manifest.db").exists()
        assert not (backup_root / ".smartbackup_manifest.json").exists()

        loaded = get_manifest_manager(backup_root, "sqlite").load()
        assert loaded is not None
        assert len(loaded.selective_backups) == 2
        assert loaded.selective_backups[0].selected_folders == ["Projects"]
        assert loaded.selective_backups[1].selected_folders == ["Finance"]
        assert loaded.last_backup_mode == "select"
        assert loaded.last_selected_folders == ["Finance"]
