"""
Tests for utils module.
"""
import pytest
import os
import json
from unittest.mock import patch, mock_open

from blucommand.utils import format_bytes, format_rate, format_uptime, atomic_write, setup_logging


class TestFormatBytes:
    """Byte formatting tests."""
    
    def test_format_bytes_zero(self):
        result = format_bytes(0)
        assert result == "0.00 B"
    
    def test_format_bytes_small(self):
        assert format_bytes(512) == "512.00 B"
        assert format_bytes(1023) == "1023.00 B"
    
    def test_format_bytes_kilobytes(self):
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"
    
    def test_format_bytes_megabytes(self):
        assert format_bytes(1048576) == "1.00 MB"
        assert format_bytes(int(2.5 * 1024 * 1024)) == "2.50 MB"
    
    def test_format_bytes_gigabytes(self):
        assert format_bytes(1073741824) == "1.00 GB"
    
    def test_format_bytes_terabytes(self):
        assert format_bytes(1024 ** 4) == "1.00 TB"
    
    def test_format_bytes_negative(self):
        result = format_bytes(-1)
        assert "-1.00 B" in result
    
    def test_format_bytes_very_large(self):
        result = format_bytes(999999999999)
        assert "GB" in result

    def test_format_bytes_petabytes(self):
        assert format_bytes(1024 ** 5) == "1.00 PB"


class TestFormatRate:
    """Rate formatting tests."""
    
    def test_format_rate_zero(self):
        assert format_rate(0) == "0 bps"
    
    def test_format_rate_bps(self):
        assert format_rate(100) == "800 bps"
    
    def test_format_rate_kbps(self):
        assert format_rate(1000) == "8 Kbps"
        assert format_rate(1250) == "10 Kbps"
    
    def test_format_rate_mbps(self):
        assert format_rate(125000) == "1.00 Mbps"
        assert format_rate(250000) == "2.00 Mbps"
        assert format_rate(1000000) == "8.00 Mbps"
    
    def test_format_rate_negative(self):
        assert format_rate(-1) == "-8 bps"
    
    def test_format_rate_very_large(self):
        result = format_rate(999999999)
        assert "Mbps" in result


class TestFormatUptime:
    """Uptime formatting tests."""
    
    def test_format_uptime_zero(self):
        assert format_uptime(0) == "0m"
    
    def test_format_uptime_minutes(self):
        assert format_uptime(30) == "0m"
        assert format_uptime(60) == "1m"
        assert format_uptime(90) == "1m"
    
    def test_format_uptime_hours(self):
        assert format_uptime(3600) == "1h 0m"
        assert format_uptime(3660) == "1h 1m"
        assert format_uptime(7200) == "2h 0m"
    
    def test_format_uptime_days(self):
        assert format_uptime(86400) == "1d 0h"
        assert format_uptime(90000) == "1d 1h"
        assert format_uptime(172800) == "2d 0h"
        assert format_uptime(2592000) == "30d 0h"
    
    def test_format_uptime_negative(self):
        assert format_uptime(-1) == "0m"
    
    def test_format_uptime_invalid_type(self):
        assert format_uptime("invalid") == "N/A"
        assert format_uptime(None) == "N/A"


class TestAtomicWrite:
    """Atomic write tests."""
    
    def test_atomic_write_creates_file(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        data = {"key": "value", "number": 42}
        
        atomic_write(filepath, data)
        
        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            result = json.load(f)
        assert result == data
    
    def test_atomic_write_no_temp_file_left(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        atomic_write(filepath, {"key": "value"})
        
        assert not os.path.exists(f"{filepath}.tmp")
        assert os.path.exists(filepath)
    
    def test_atomic_write_overwrite(self, tmp_path):
        filepath = str(tmp_path / "test.json")
        
        atomic_write(filepath, {"old": "data"})
        atomic_write(filepath, {"new": "data"})
        
        with open(filepath, 'r') as f:
            result = json.load(f)
        assert result == {"new": "data"}
    
    def test_atomic_write_nonexistent_directory(self, tmp_path):
        """Write to non-existent directory fails gracefully."""
        invalid_file = str(tmp_path / "nonexistent" / "test.json")
        atomic_write(invalid_file, {"key": "value"})
        assert not os.path.exists(invalid_file)
    
    @patch('builtins.open')
    @patch('os.replace')
    def test_atomic_write_handles_oserror(self, mock_replace, mock_open):
        mock_open.side_effect = OSError("Permission denied")
        atomic_write("/tmp/test.json", {"test": "value"})
    
    @patch('builtins.open')
    @patch('os.replace')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_atomic_write_cleanup_on_error(self, mock_remove, mock_exists, mock_replace, mock_open):
        mock_open.return_value.__enter__.side_effect = OSError("Write failed")
        mock_exists.return_value = True
        
        atomic_write("/tmp/test.json", {"test": "value"})
        mock_remove.assert_called()

    @patch('os.remove', side_effect=OSError("busy"))
    @patch('os.path.exists', return_value=True)
    @patch('os.replace', side_effect=OSError("replace failed"))
    @patch('builtins.open')
    def test_atomic_write_ignores_cleanup_failure(self, _mock_open, _mock_replace, _mock_exists, _mock_remove):
        atomic_write("/tmp/test.json", {"test": "value"})


class TestSetupLogging:
    """Test logging setup."""
    
    def test_setup_logging_debug(self):
        """Test logging setup with debug enabled."""
        logger = setup_logging(debug=True)
        assert logger.level == 10  # DEBUG
    
    def test_setup_logging_normal(self):
        """Test logging setup without debug."""
        logger = setup_logging(debug=False)
        assert logger.level == 30  # WARNING
    
    def test_setup_logging_handlers(self):
        """Test logging setup creates handlers."""
        logger = setup_logging(debug=False)
        assert len(logger.handlers) >= 1

    def test_setup_logging_structured(self):
        logger = setup_logging(structured=True)
        assert logger.handlers

