"""
End-to-End (E2E) virtualized workflow tests for auto-detection and incremental sync.
Simulates real-world drive mount lifecycles, prompt interactions, and backup execution
with zero external hardware dependencies.
"""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from smartbackup.cli import app
from smartbackup.platform.watcher import DeviceWatcher, DriveMatcher

runner = CliRunner()


class TestAutoDetectE2E:
    """End-to-End virtualized mount and backup scenarios."""

    def test_e2e_mount_detection_and_interactive_backup(self, tmp_path: Path):
        """
        1. User creates source files in Documents folder.
        2. Removable drive mounts with previous backup structure.
        3. DeviceWatcher detects drive and triggers prompt callback.
        4. User confirms backup ('y') via interactive --prompt CLI -> backup executes.
        5. Target backup contains copied files and updated manifest.
        """
        source_dir = tmp_path / "Documents"
        source_dir.mkdir()
        (source_dir / "resume.pdf").write_text("Resume Content")
        (source_dir / "projects").mkdir()
        (source_dir / "projects" / "app.py").write_text("print('hello world')")

        usb_drive = tmp_path / "Virtual_USB_Drive"
        usb_backup_root = usb_drive / "Documents-Backup" / "Test-Laptop"
        usb_backup_root.mkdir(parents=True)
        (usb_backup_root / ".smartbackup_manifest.json").write_text("{}")

        state_file = tmp_path / "state.json"

        with (
            patch("smartbackup.cli.get_device_name", return_value="Test-Laptop"),
            patch("smartbackup.backup.get_device_name", return_value="Test-Laptop"),
            patch("smartbackup.platform.identity.get_device_name", return_value="Test-Laptop"),
            patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Laptop"),
            patch(
                "smartbackup.platform.resolver.PathResolver.get_documents_path",
                return_value=source_dir,
            ),
        ):
            spawner_calls = []
            watcher = DeviceWatcher(
                interval=0.1,
                cooldown=300,
                on_drive_detected=lambda target, *a, **kw: spawner_calls.append(target),
                state_file=state_file,
            )

            watcher._previous_drives = set()
            with patch.object(watcher, "_get_current_drives", return_value={usb_drive}):
                triggered = watcher.run_once()

            assert triggered == [usb_drive]
            assert spawner_calls == [usb_drive]

            with (
                patch("rich.prompt.Prompt.ask", return_value="y"),
                patch("time.sleep"),
            ):
                result = runner.invoke(
                    app,
                    ["--source", str(source_dir), "--target", str(usb_drive), "--prompt"],
                )

                assert result.exit_code == 0
                assert "Backup completed successfully!" in result.output

            assert (usb_backup_root / "resume.pdf").exists()
            assert (usb_backup_root / "resume.pdf").read_text() == "Resume Content"
            assert (usb_backup_root / "projects" / "app.py").exists()
            assert (usb_backup_root / ".smartbackup_manifest.json").exists()

    def test_e2e_multi_partition_drive_suppression(self, tmp_path: Path):
        """Multi-partition mounts in one scan allow exactly 1 prompt."""
        partition1 = tmp_path / "Partition_Data"
        (partition1 / "Documents-Backup" / "Work-PC").mkdir(parents=True)
        (partition1 / "Documents-Backup" / "Work-PC" / ".smartbackup_manifest.json").write_text("{}")

        partition2 = tmp_path / "Partition_Recovery"
        (partition2 / "Documents-Backup" / "Work-PC").mkdir(parents=True)
        (partition2 / "Documents-Backup" / "Work-PC" / ".smartbackup_manifest.json").write_text("{}")

        state_file = tmp_path / "debounce_state.json"
        prompt_targets = []

        with (
            patch("smartbackup.cli.get_device_name", return_value="Work-PC"),
            patch("smartbackup.backup.get_device_name", return_value="Work-PC"),
            patch("smartbackup.platform.identity.get_device_name", return_value="Work-PC"),
            patch("smartbackup.platform.watcher.get_device_name", return_value="Work-PC"),
        ):
            watcher = DeviceWatcher(
                interval=0.1,
                cooldown=300,
                on_drive_detected=lambda target: prompt_targets.append(target),
                state_file=state_file,
            )
            watcher._previous_drives = set()

            with patch.object(
                watcher, "_get_current_drives", return_value={partition1, partition2}
            ):
                triggered = watcher.run_once()

            assert len(triggered) == 1
            assert len(prompt_targets) == 1

    def test_e2e_drive_letter_reassignment_and_incremental_sync(self, tmp_path: Path):
        """Drive re-mounted at a new path is matched and incrementally synced."""
        source_dir = tmp_path / "Documents"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("Version 1")

        mount_d = tmp_path / "Drive_D"
        backup_d = mount_d / "Documents-Backup" / "Dev-Machine"
        backup_d.mkdir(parents=True)

        with (
            patch("smartbackup.cli.get_device_name", return_value="Dev-Machine"),
            patch("smartbackup.backup.get_device_name", return_value="Dev-Machine"),
            patch("smartbackup.platform.identity.get_device_name", return_value="Dev-Machine"),
            patch("smartbackup.platform.watcher.get_device_name", return_value="Dev-Machine"),
        ):
            result = runner.invoke(
                app,
                ["--source", str(source_dir), "--target", str(mount_d)],
            )
            assert result.exit_code == 0
            assert (backup_d / "file1.txt").exists()
            assert (backup_d / ".smartbackup_manifest.json").exists()

            (source_dir / "file2.txt").write_text("New File 2")

            mount_e = tmp_path / "Drive_E"
            mount_d.rename(mount_e)
            backup_e = mount_e / "Documents-Backup" / "Dev-Machine"

            assert DriveMatcher().is_smartbackup_target(mount_e) is True

            result2 = runner.invoke(
                app,
                ["--source", str(source_dir), "--target", str(mount_e)],
            )
            assert result2.exit_code == 0
            assert (backup_e / "file1.txt").exists()
            assert (backup_e / "file2.txt").exists()
