"""
End-to-End (E2E) Virtualized Integration Tests for SmartBackup v0.6.1.
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
    """End-to-End integration test suite."""

    def test_e2e_mount_detection_and_interactive_backup(self, tmp_path: Path):
        """
        E2E Scenario 1:
        1. User creates source files in Documents folder.
        2. Removable drive mounts with previous backup structure.
        3. DeviceWatcher detects drive and invokes TerminalSpawner.
        4. TerminalSpawner launches interactive --prompt session.
        5. User confirms backup ('y') -> incremental backup executes successfully.
        6. Target backup contains copied files and updated manifest.
        """
        # Step 1: Create source directory and sample files
        source_dir = tmp_path / "Documents"
        source_dir.mkdir()
        (source_dir / "resume.pdf").write_text("Resume Content")
        (source_dir / "projects").mkdir()
        (source_dir / "projects" / "app.py").write_text("print('hello world')")

        # Step 2: Create virtual USB target drive
        usb_drive = tmp_path / "Virtual_USB_Drive"
        usb_backup_root = usb_drive / "Documents-Backup" / "Test-Laptop"
        usb_backup_root.mkdir(parents=True)
        (usb_backup_root / ".smartbackup_manifest.json").write_text("{}")

        # State tracking file for debounce lock
        state_file = tmp_path / "state.json"

        with patch("smartbackup.cli.get_device_name", return_value="Test-Laptop"), \
             patch("smartbackup.backup.get_device_name", return_value="Test-Laptop"), \
             patch("smartbackup.platform.identity.get_device_name", return_value="Test-Laptop"), \
             patch("smartbackup.platform.watcher.get_device_name", return_value="Test-Laptop"), \
             patch("smartbackup.platform.resolver.PathResolver.get_documents_path", return_value=source_dir):

            # Step 3: Initialize DeviceWatcher and TerminalSpawner
            spawner_calls = []

            def _mock_spawn(target, *args, **kwargs):
                spawner_calls.append(target)
            watcher = DeviceWatcher(
                interval=0.1,
                cooldown=300,
                on_drive_detected=_mock_spawn,
                state_file=state_file,
            )

            # Polling cycle discovers newly mounted drive
            watcher._previous_drives = set()
            with patch.object(watcher, "_get_current_drives", return_value={usb_drive}):
                triggered = watcher.run_once()

            assert triggered == [usb_drive]
            assert len(spawner_calls) == 1
            assert spawner_calls[0] == usb_drive

            # Step 4 & 5: Simulate interactive --prompt CLI invocation
            with patch("rich.prompt.Prompt.ask", return_value="y"), \
                 patch("time.sleep"):  # skip 5s completion pause

                result = runner.invoke(
                    app,
                    ["--source", str(source_dir), "--target", str(usb_drive), "--prompt"],
                )

                assert result.exit_code == 0
                assert "Backup completed successfully!" in result.output

            # Step 6: Verify backup destination files and manifest
            assert (usb_backup_root / "resume.pdf").exists()
            assert (usb_backup_root / "resume.pdf").read_text() == "Resume Content"
            assert (usb_backup_root / "projects" / "app.py").exists()
            assert (usb_backup_root / ".smartbackup_manifest.json").exists()

    def test_e2e_multi_partition_drive_suppression(self, tmp_path: Path):
        """
        E2E Scenario 2:
        Simulates a multi-partition external drive (e.g. Partition 1 + Partition 2 + EFI)
        mounting simultaneously. DebounceLock must allow exactly 1 prompt and suppress
        burst popups for all other partitions.
        """
        partition1 = tmp_path / "Partition_Data"
        (partition1 / "Documents-Backup" / "Work-PC").mkdir(parents=True)
        (partition1 / "Documents-Backup" / "Work-PC" / ".smartbackup_manifest.json").write_text("{}")

        partition2 = tmp_path / "Partition_Recovery"
        (partition2 / "Documents-Backup" / "Work-PC").mkdir(parents=True)
        (partition2 / "Documents-Backup" / "Work-PC" / ".smartbackup_manifest.json").write_text("{}")

        state_file = tmp_path / "debounce_state.json"
        prompt_targets = []

        with patch("smartbackup.cli.get_device_name", return_value="Work-PC"), \
             patch("smartbackup.backup.get_device_name", return_value="Work-PC"), \
             patch("smartbackup.platform.identity.get_device_name", return_value="Work-PC"), \
             patch("smartbackup.platform.watcher.get_device_name", return_value="Work-PC"):
            watcher = DeviceWatcher(
                interval=0.1,
                cooldown=300,
                on_drive_detected=lambda target: prompt_targets.append(target),
                state_file=state_file,
            )

            watcher._previous_drives = set()

            # Both partitions appear in the same scan cycle
            with patch.object(watcher, "_get_current_drives", return_value={partition1, partition2}):
                triggered = watcher.run_once()

            # Only ONE prompt should be triggered due to global burst debounce lock
            assert len(triggered) == 1
            assert len(prompt_targets) == 1

    def test_e2e_drive_letter_reassignment_and_incremental_sync(self, tmp_path: Path):
        """
        E2E Scenario 3:
        1. Drive is initially mounted at path A (simulating D:).
        2. Backup is performed.
        3. Drive is re-mounted at path B (simulating E:).
        4. Watcher identifies drive by hostname folder / manifest.
        5. Incremental backup runs and only copies newly added files.
        """
        source_dir = tmp_path / "Documents"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("Version 1")

        # Initial mount point D:
        mount_d = tmp_path / "Drive_D"
        backup_d = mount_d / "Documents-Backup" / "Dev-Machine"
        backup_d.mkdir(parents=True)

        with patch("smartbackup.cli.get_device_name", return_value="Dev-Machine"), \
             patch("smartbackup.backup.get_device_name", return_value="Dev-Machine"), \
             patch("smartbackup.platform.identity.get_device_name", return_value="Dev-Machine"), \
             patch("smartbackup.platform.watcher.get_device_name", return_value="Dev-Machine"):
            # Run initial backup to Mount D
            result = runner.invoke(
                app,
                ["--source", str(source_dir), "--target", str(mount_d)],
            )
            assert result.exit_code == 0
            assert (backup_d / "file1.txt").exists()
            assert (backup_d / ".smartbackup_manifest.json").exists()

            # Add new file to source
            (source_dir / "file2.txt").write_text("New File 2")

            # Simulate drive letter change: move backup directory to Mount E
            mount_e = tmp_path / "Drive_E"
            mount_d.rename(mount_e)
            backup_e = mount_e / "Documents-Backup" / "Dev-Machine"

            # Check that DriveMatcher identifies Mount E
            matcher = DriveMatcher()
            assert matcher.is_smartbackup_target(mount_e) is True

            # Run incremental backup targeting Mount E
            result2 = runner.invoke(
                app,
                ["--source", str(source_dir), "--target", str(mount_e)],
            )
            assert result2.exit_code == 0
            assert (backup_e / "file1.txt").exists()
            assert (backup_e / "file2.txt").exists()

    def test_e2e_daemon_service_lifecycle(self, tmp_path: Path):
        """
        E2E Scenario 4:
        Tests full daemon CLI lifecycle (install -> status -> uninstall) across platforms.
        """
        # Test Install
        with patch("smartbackup.platform.scheduler.SchedulerHelper.install_daemon_service", return_value=(True, "Installed ok")):
            res_install = runner.invoke(app, ["daemon", "install"])
            assert res_install.exit_code == 0
            assert "Installed ok" in res_install.output

        # Test Status
        status_payload = {
            "installed": True,
            "running": True,
            "pid": 8888,
            "service_path": "/fake/path/service",
            "details": "Active",
        }
        with patch("smartbackup.platform.scheduler.SchedulerHelper.get_daemon_status", return_value=status_payload):
            res_status = runner.invoke(app, ["daemon", "status"])
            assert res_status.exit_code == 0
            assert "8888" in res_status.output
            assert "Active" in res_status.output

        # Test Uninstall
        with patch("smartbackup.platform.scheduler.SchedulerHelper.uninstall_daemon_service", return_value=(True, "Uninstalled ok")):
            res_uninstall = runner.invoke(app, ["daemon", "uninstall"])
            assert res_uninstall.exit_code == 0
            assert "Uninstalled ok" in res_uninstall.output
