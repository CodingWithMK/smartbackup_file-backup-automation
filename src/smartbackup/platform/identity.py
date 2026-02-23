"""
Identity - Device identification for multi-device backup support.

Provides functions to identify the current device using the system hostname,
enabling per-device backup separation on shared external drives.
"""

import platform
import re


def get_device_name() -> str:
    """
    Get a filesystem-safe identifier for the current device.

    Uses the system hostname via platform.node(), sanitized for safe use
    as a directory name. On macOS, the ".local" suffix appended by
    mDNS/Bonjour is stripped automatically.

    Returns:
        A sanitized hostname string (e.g., "Musabs-MacBook-Pro")
    """
    hostname = platform.node()

    # Remove domain suffix.
    # macOS appends ".local" (e.g., "Musabs-MacBook-Pro.local").
    # Corporate machines may have FQDNs (e.g., "server_01.corp.net").
    hostname = hostname.split(".")[0]

    # Replace non-alphanumeric/non-hyphen/non-underscore chars with hyphens
    sanitized = re.sub(r"[^\w\-]", "-", hostname)

    # Collapse runs of hyphens, strip leading/trailing
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")

    return sanitized or "unknown-device"
