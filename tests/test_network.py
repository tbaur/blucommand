"""
Tests for network module.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from urllib.error import URLError, HTTPError

from blucommand.network import Network, _url_for_log


class TestNetwork:
    """Test Network class."""
    
    @patch('urllib.request.urlopen')
    def test_successful_get_request(self, mock_urlopen):
        """Test successful GET request."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"test response"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result == b"test response"
        mock_urlopen.assert_called_once()
    
    @patch('urllib.request.urlopen')
    def test_successful_post_request(self, mock_urlopen):
        """Test successful POST request."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"post response"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = Network.post("http://192.168.1.1/test", data={"key": "value"})
        
        assert result == b"post response"
        mock_urlopen.assert_called_once()
    
    @patch('blucommand.network.time.sleep')
    @patch('urllib.request.urlopen')
    def test_handles_timeout(self, mock_urlopen, _mock_sleep):
        """Test handling of timeout."""
        mock_urlopen.side_effect = TimeoutError()
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result is None
    
    @patch('blucommand.network.time.sleep')
    @patch('urllib.request.urlopen')
    def test_handles_connection_error(self, mock_urlopen, _mock_sleep):
        """Test handling of connection error."""
        mock_urlopen.side_effect = ConnectionError()
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result is None
    
    @patch('blucommand.network.time.sleep')
    @patch('urllib.request.urlopen')
    def test_handles_http_error(self, mock_urlopen, _mock_sleep):
        """HTTP errors must not be retried (HTTPError subclasses URLError)."""
        mock_urlopen.side_effect = HTTPError("url", 502, "Bad Gateway", {}, None)
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result is None
        assert mock_urlopen.call_count == 1
        _mock_sleep.assert_not_called()
    
    @patch('blucommand.network.time.sleep')
    @patch('urllib.request.urlopen')
    def test_handles_url_error(self, mock_urlopen, _mock_sleep):
        """Test handling of URL error."""
        mock_urlopen.side_effect = URLError("Connection refused")
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result is None

    @patch('blucommand.network.time.sleep')
    @patch('urllib.request.urlopen')
    def test_max_retries_one_fails_fast(self, mock_urlopen, _mock_sleep):
        """Device polls can disable retries so dead endpoints fail fast."""
        mock_urlopen.side_effect = URLError("timed out")

        result = Network.get("http://192.168.1.1/test", max_retries=1)

        assert result is None
        assert mock_urlopen.call_count == 1
        _mock_sleep.assert_not_called()
    
    def test_rejects_invalid_url_scheme(self):
        """Test that invalid URL schemes are rejected."""
        result = Network.get("file:///etc/passwd")
        assert result is None
        
        result = Network.get("javascript:alert(1)")
        assert result is None
    
    @patch('urllib.request.urlopen')
    def test_enforces_size_limit(self, mock_urlopen):
        """Test that size limit is enforced."""
        from blucommand.constants import MAX_XML_SIZE
        mock_response = MagicMock()
        mock_response.read.return_value = b"x" * (MAX_XML_SIZE + 1)
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = Network.get("http://192.168.1.1/test")
        
        assert result is None
    
    @patch('urllib.request.urlopen')
    def test_custom_timeout(self, mock_urlopen):
        """Test custom timeout."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"response"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        Network.get("http://192.168.1.1/test", timeout=10)
        
        call_args = mock_urlopen.call_args
        assert 'timeout' in call_args.kwargs
        assert call_args.kwargs['timeout'] == 10

    def test_url_for_log_strips_userinfo(self):
        """Credentials in URL userinfo must not appear in log-safe form."""
        assert _url_for_log("https://user:s3cret@controller.local/api") == (
            "https://controller.local/api"
        )
        assert _url_for_log("http://192.168.1.1:11000/Status") == (
            "http://192.168.1.1:11000/Status"
        )
        redacted = _url_for_log("https://token@host.example:8443/path?x=1")
        assert "token" not in redacted
        assert "host.example:8443" in redacted

    @patch('blucommand.network.logger')
    def test_invalid_scheme_log_does_not_echo_credentials(self, mock_logger):
        """Invalid-scheme rejection logs a redacted URL only."""
        Network.get("ftp://user:password@evil.example/secret")
        mock_logger.warning.assert_called()
        logged = " ".join(str(a) for a in mock_logger.warning.call_args[0])
        assert "password" not in logged
        assert "user" not in logged

