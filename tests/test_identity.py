"""
Tests for the platform identity module.
"""

from unittest.mock import patch

from smartbackup.platform.identity import get_device_name


class TestGetDeviceName:
    """Tests for get_device_name() function."""

    def test_returns_string(self):
        """Should return a non-empty string."""
        result = get_device_name()
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("smartbackup.platform.identity.platform")
    def test_strips_local_suffix(self, mock_platform):
        """Should strip the .local suffix added by macOS mDNS/Bonjour."""
        mock_platform.node.return_value = "Musabs-MacBook-Pro.local"
        assert get_device_name() == "Musabs-MacBook-Pro"

    @patch("smartbackup.platform.identity.platform")
    def test_strips_domain_suffix(self, mock_platform):
        """Should strip full domain suffixes (e.g., corporate FQDNs)."""
        mock_platform.node.return_value = "server_01.corp.net"
        assert get_device_name() == "server_01"

    @patch("smartbackup.platform.identity.platform")
    def test_windows_hostname(self, mock_platform):
        """Should handle typical Windows hostnames."""
        mock_platform.node.return_value = "DESKTOP-A1B2C3D"
        assert get_device_name() == "DESKTOP-A1B2C3D"

    @patch("smartbackup.platform.identity.platform")
    def test_replaces_spaces(self, mock_platform):
        """Should replace spaces with hyphens."""
        mock_platform.node.return_value = "my laptop"
        assert get_device_name() == "my-laptop"

    @patch("smartbackup.platform.identity.platform")
    def test_replaces_special_chars(self, mock_platform):
        """Should replace non-alphanumeric/non-hyphen/non-underscore chars."""
        mock_platform.node.return_value = "host@name!here"
        assert get_device_name() == "host-name-here"

    @patch("smartbackup.platform.identity.platform")
    def test_collapses_multiple_hyphens(self, mock_platform):
        """Should collapse multiple consecutive hyphens into one."""
        mock_platform.node.return_value = "host--name---here"
        assert get_device_name() == "host-name-here"

    @patch("smartbackup.platform.identity.platform")
    def test_strips_leading_trailing_hyphens(self, mock_platform):
        """Should strip leading and trailing hyphens."""
        mock_platform.node.return_value = "-hostname-"
        assert get_device_name() == "hostname"

    @patch("smartbackup.platform.identity.platform")
    def test_fallback_for_empty_hostname(self, mock_platform):
        """Should return 'unknown-device' if hostname is empty."""
        mock_platform.node.return_value = ""
        assert get_device_name() == "unknown-device"

    @patch("smartbackup.platform.identity.platform")
    def test_fallback_for_dot_only(self, mock_platform):
        """Should return 'unknown-device' if hostname is just a dot."""
        mock_platform.node.return_value = "."
        assert get_device_name() == "unknown-device"

    @patch("smartbackup.platform.identity.platform")
    def test_fallback_for_all_special_chars(self, mock_platform):
        """Should return 'unknown-device' if hostname is all special chars."""
        mock_platform.node.return_value = "!!!.local"
        assert get_device_name() == "unknown-device"

    @patch("smartbackup.platform.identity.platform")
    def test_underscores_preserved(self, mock_platform):
        """Should preserve underscores in hostname."""
        mock_platform.node.return_value = "my_server_01"
        assert get_device_name() == "my_server_01"

    @patch("smartbackup.platform.identity.platform")
    def test_simple_hostname(self, mock_platform):
        """Should handle a simple hostname without suffix."""
        mock_platform.node.return_value = "Office-Desktop"
        assert get_device_name() == "Office-Desktop"
