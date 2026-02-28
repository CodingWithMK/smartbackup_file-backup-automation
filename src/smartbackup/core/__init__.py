"""SmartBackup core components."""

from smartbackup.core.compressor import BackupCompressor
from smartbackup.core.scanner import FileScanner, ExclusionFilter
from smartbackup.core.detector import ChangeDetector
from smartbackup.core.engine import BackupEngine, DryRunBackupEngine
from smartbackup.core.restore import RestoreEngine, RestoreResult, ConflictResolution

__all__ = [
    "BackupCompressor",
    "FileScanner",
    "ExclusionFilter",
    "ChangeDetector",
    "BackupEngine",
    "DryRunBackupEngine",
    "RestoreEngine",
    "RestoreResult",
    "ConflictResolution",
]
