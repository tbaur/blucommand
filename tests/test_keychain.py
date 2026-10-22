"""
Tests for keychain module.
"""
import pytest
import subprocess
import sys
from unittest.mock import patch, MagicMock

from blucommand.keychain import (
    get_api_key, set_api_key, delete_api_key, has_api_key, is_macos
)


class TestKeychain:
    """Test Keychain functions."""
    
    def test_is_macos(self):
        """Test macOS detection."""
        if sys.platform == "darwin":
            assert is_macos() is True
        else:
            assert is_macos() is False
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_get_api_key_success(self):
        """Test retrieving API key from Keychain."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "test-api-key-12345\n"
        
        with patch('subprocess.run', return_value=mock_result):
            key = get_api_key()
            assert key == "test-api-key-12345"
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_get_api_key_not_found(self):
        """Test retrieving API key when not in Keychain."""
        mock_result = MagicMock()
        mock_result.returncode = 44  # Item not found
        mock_result.stdout = ""
        
        with patch('subprocess.run', return_value=mock_result):
            key = get_api_key()
            assert key is None
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_set_api_key_success(self):
        """Test storing API key in Keychain."""
        # Mock delete (returns 0 or 44)
        mock_delete = MagicMock()
        mock_delete.returncode = 0
        
        # Mock add (returns 0 for success)
        mock_add = MagicMock()
        mock_add.returncode = 0
        mock_add.stderr = None
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [mock_delete, mock_add]
            result = set_api_key("test-api-key-12345")
            assert result is True
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_set_api_key_empty(self):
        """Test that empty API key is rejected."""
        result = set_api_key("")
        assert result is False
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_delete_api_key_success(self):
        """Test deleting API key from Keychain."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = None
        
        with patch('subprocess.run', return_value=mock_result):
            result = delete_api_key()
            assert result is True
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_delete_api_key_not_found(self):
        """Test deleting API key when not in Keychain."""
        mock_result = MagicMock()
        mock_result.returncode = 44  # Item not found
        mock_result.stderr = None
        
        with patch('subprocess.run', return_value=mock_result):
            result = delete_api_key()
            assert result is True  # Should return True even if not found
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_has_api_key_true(self):
        """Test checking if API key exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result):
            result = has_api_key()
            assert result is True
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_has_api_key_false(self):
        """Test checking if API key doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 44  # Item not found
        
        with patch('subprocess.run', return_value=mock_result):
            result = has_api_key()
            assert result is False
    
    def test_get_api_key_non_macos(self):
        """Test that Keychain functions return None on non-macOS."""
        with patch('blucommand.keychain.is_macos', return_value=False):
            assert get_api_key() is None
            assert set_api_key("test") is False
            assert delete_api_key() is False
            assert has_api_key() is False
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_get_api_key_timeout(self):
        """Test handling of Keychain timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("security", 5)):
            key = get_api_key()
            assert key is None
    
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_get_api_key_command_not_found(self):
        """Test handling when security command is not found."""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            key = get_api_key()
            assert key is None

