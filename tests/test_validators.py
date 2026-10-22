"""
Tests for validators module.
"""
import pytest
from blucommand.validators import (
    validate_ip, validate_hostname, sanitize_ip,
    validate_volume, validate_timeout, validate_config_value,
    parse_endpoint, format_endpoint, sanitize_endpoint,
)


class TestValidateIP:
    """Test IP address validation."""
    
    def test_valid_ipv4(self):
        """Test valid IPv4 addresses."""
        assert validate_ip("192.168.1.1") is True
        assert validate_ip("10.0.0.1") is True
        assert validate_ip("172.16.0.1") is True
        assert validate_ip("8.8.8.8") is True
    
    def test_invalid_ipv4(self):
        """Test invalid IPv4 addresses."""
        assert validate_ip("256.1.1.1") is False
        assert validate_ip("192.168.1") is False
        assert validate_ip("not.an.ip.address") is False
        assert validate_ip("") is False
        assert validate_ip("192.168.1.1.1") is False
    
    def test_rejects_loopback(self):
        """Test that loopback addresses are rejected."""
        assert validate_ip("127.0.0.1") is False
        assert validate_ip("127.1.1.1") is False
    
    def test_rejects_multicast(self):
        """Test that multicast addresses are rejected."""
        assert validate_ip("224.0.0.1") is False
        assert validate_ip("239.255.255.255") is False
    
    def test_rejects_reserved(self):
        """Test that reserved addresses are rejected."""
        assert validate_ip("0.0.0.0") is False
        assert validate_ip("169.254.1.1") is False  # Link-local
    
    def test_rejects_null_bytes(self):
        """Test that IPs with null bytes are rejected."""
        assert validate_ip("192.168.1.1\x00") is False
        assert validate_ip("\x00192.168.1.1") is False
    
    def test_rejects_newlines(self):
        """Test that IPs with newlines are rejected."""
        assert validate_ip("192.168.1.1\n") is False
        assert validate_ip("192.168.1.1\r") is False
    
    def test_rejects_too_long(self):
        """Test that IPs that are too long are rejected."""
        assert validate_ip("192.168.1.1.1") is False
        assert validate_ip("a" * 100) is False
    
    def test_rejects_non_string(self):
        """Test that non-string inputs are rejected."""
        assert validate_ip(None) is False
        assert validate_ip(123) is False
        assert validate_ip([]) is False


class TestValidateHostname:
    """Test hostname validation."""
    
    def test_valid_hostnames(self):
        """Test valid hostnames."""
        assert validate_hostname("example.com") is True
        assert validate_hostname("speaker.local") is True
        assert validate_hostname("device-1.example.com") is True
        assert validate_hostname("a") is True
        assert validate_hostname("a" * 63) is True  # Max label length
    
    def test_invalid_hostnames(self):
        """Test invalid hostnames."""
        assert validate_hostname("") is False
        assert validate_hostname("-invalid.com") is False
        assert validate_hostname("invalid-.com") is False
        assert validate_hostname(".invalid.com") is False
        assert validate_hostname("invalid..com") is False
        assert validate_hostname("a" * 254) is False  # Too long
    
    def test_rejects_shell_metacharacters(self):
        """Test that hostnames with shell metacharacters are rejected."""
        assert validate_hostname("host;rm -rf") is False
        assert validate_hostname("host&evil") is False
        assert validate_hostname("host|command") is False
        assert validate_hostname("host`command`") is False
        assert validate_hostname("host$(command)") is False
        assert validate_hostname("host (evil)") is False
        assert validate_hostname("host<evil>") is False
        assert validate_hostname("host with spaces") is False
    
    def test_rejects_null_bytes_and_newlines(self):
        """Test that hostnames with null bytes or newlines are rejected."""
        assert validate_hostname("host\x00name") is False
        assert validate_hostname("host\nname") is False
        assert validate_hostname("host\rname") is False
    
    def test_rejects_non_string(self):
        """Test that non-string inputs are rejected."""
        assert validate_hostname(None) is False
        assert validate_hostname(123) is False
        assert validate_hostname([]) is False


class TestSanitizeIP:
    """Test IP sanitization."""
    
    def test_valid_ip_sanitization(self):
        """Test sanitization of valid IPs."""
        assert sanitize_ip("192.168.1.1") == "192.168.1.1"
        assert sanitize_ip("  192.168.1.1  ") == "192.168.1.1"
        assert sanitize_ip("10.0.0.1") == "10.0.0.1"
    
    def test_invalid_ip_sanitization(self):
        """Test sanitization of invalid IPs."""
        assert sanitize_ip("127.0.0.1") is None
        assert sanitize_ip("invalid") is None
        assert sanitize_ip("") is None
        assert sanitize_ip("256.1.1.1") is None


class TestEndpointHelpers:
    """Test BluOS ip:port endpoint helpers."""

    def test_parse_endpoint_bare_ip(self):
        assert parse_endpoint("192.168.1.1") == ("192.168.1.1", 11000)

    def test_parse_endpoint_with_port(self):
        assert parse_endpoint("192.168.1.1:11010") == ("192.168.1.1", 11010)

    def test_parse_endpoint_invalid(self):
        ip, port = parse_endpoint("127.0.0.1:11000")
        assert ip is None
        assert port == 11000

    def test_format_and_sanitize_endpoint(self):
        assert format_endpoint("192.168.1.1", 11010) == "192.168.1.1:11010"
        assert sanitize_endpoint("192.168.1.1") == "192.168.1.1:11000"
        assert sanitize_endpoint("192.168.1.1:11010") == "192.168.1.1:11010"
        assert sanitize_endpoint("invalid") is None

    def test_parse_endpoint_rejects_blank_and_bad_port(self):
        assert parse_endpoint("") == (None, 11000)
        assert parse_endpoint("   ") == (None, 11000)
        ip, port = parse_endpoint("192.0.2.10:nope")
        assert ip is None
        assert port == 11000
        assert format_endpoint("192.0.2.10") == "192.0.2.10:11000"

    def test_unknown_discovery_method_falls_back(self):
        assert validate_config_value("DISCOVERY_METHOD", "nope") == "mdns"


class TestValidateVolume:
    """Test volume validation."""
    
    def test_valid_volumes(self):
        """Test valid volume values."""
        assert validate_volume(0) == 0
        assert validate_volume(50) == 50
        assert validate_volume(100) == 100
    
    def test_clamps_out_of_range(self):
        """Test that out-of-range volumes are clamped."""
        assert validate_volume(-10) == 0
        assert validate_volume(150) == 100
        assert validate_volume(200) == 100
    
    def test_handles_strings(self):
        """Test that string volumes are converted."""
        assert validate_volume("50") == 50
        assert validate_volume("0") == 0
        assert validate_volume("25.5") == 25  # Float strings are converted
    
    def test_handles_invalid_types(self):
        """Test that invalid volume types are handled."""
        assert validate_volume(None) == 0  # Returns MIN_VOLUME
        assert validate_volume([]) == 0
        assert validate_volume({}) == 0
        assert validate_volume("invalid") == 0


class TestValidateTimeout:
    """Test timeout validation."""
    
    def test_valid_timeouts(self):
        """Test valid timeout values."""
        assert validate_timeout(1) == 1
        assert validate_timeout(5) == 5
        assert validate_timeout(60) == 60
    
    def test_clamps_out_of_range(self):
        """Test that out-of-range timeouts are clamped."""
        assert validate_timeout(0) == 1  # MIN_TIMEOUT
        assert validate_timeout(100) == 60  # MAX_TIMEOUT
        assert validate_timeout(-5) == 1
    
    def test_custom_range(self):
        """Test custom timeout ranges."""
        assert validate_timeout(5, min_val=10, max_val=20) == 10
        assert validate_timeout(15, min_val=10, max_val=20) == 15
        assert validate_timeout(25, min_val=10, max_val=20) == 20


class TestValidateConfigValue:
    """Test configuration value validation."""
    
    def test_discovery_timeout_validation(self):
        """Test DISCOVERY_TIMEOUT validation."""
        assert validate_config_value("DISCOVERY_TIMEOUT", "5") == "5"
        assert validate_config_value("DISCOVERY_TIMEOUT", "1") == "1"
        assert validate_config_value("DISCOVERY_TIMEOUT", "60") == "60"
        assert validate_config_value("DISCOVERY_TIMEOUT", "0") is None
        assert validate_config_value("DISCOVERY_TIMEOUT", "invalid") is None
    
    def test_cache_ttl_validation(self):
        """Test CACHE_TTL validation."""
        assert validate_config_value("CACHE_TTL", "300") == "300"
        assert validate_config_value("CACHE_TTL", "0") == "0"
        assert validate_config_value("CACHE_TTL", "3600") == "3600"
        assert validate_config_value("CACHE_TTL", "invalid") is None
    
    def test_default_safe_vol_validation(self):
        """Test DEFAULT_SAFE_VOL validation."""
        assert validate_config_value("DEFAULT_SAFE_VOL", "14") == "14"
        assert validate_config_value("DEFAULT_SAFE_VOL", "0") == "0"
        assert validate_config_value("DEFAULT_SAFE_VOL", "100") == "100"
        assert validate_config_value("DEFAULT_SAFE_VOL", "invalid") is None
    
    def test_unifi_enabled_validation(self):
        """Test UNIFI_ENABLED validation."""
        assert validate_config_value("UNIFI_ENABLED", "true") == "true"
        assert validate_config_value("UNIFI_ENABLED", "false") == "false"
        assert validate_config_value("UNIFI_ENABLED", "1") == "true"
        assert validate_config_value("UNIFI_ENABLED", "0") == "false"
        assert validate_config_value("UNIFI_ENABLED", "yes") == "true"
        assert validate_config_value("UNIFI_ENABLED", "no") == "false"
        assert validate_config_value("UNIFI_ENABLED", "invalid") is None
    
    def test_other_values_pass_through(self):
        """Test that other config values pass through."""
        assert validate_config_value("BLUOS_SERVICE", "_musc._tcp") == "_musc._tcp"
        assert validate_config_value("UNIFI_CONTROLLER", "controller.local") == "controller.local"

