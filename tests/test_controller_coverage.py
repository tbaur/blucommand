"""
Additional controller tests for coverage.
"""
import pytest
import os
import json
import time
from unittest.mock import patch, MagicMock, mock_open

from blucommand.controller import BluOSController
from blucommand.constants import CACHE_FILE, DISCOVERY_MDNS, DISCOVERY_LSDP, DISCOVERY_BOTH


class TestControllerCoverage:
    """Additional controller tests for better coverage."""

    @pytest.fixture(autouse=True)
    def _mock_endpoint_verify(self):
        """Avoid real LAN probes during discover() unit tests."""
        with patch(
            'blucommand.controller.Network.get',
            return_value=b'<SyncStatus name="ok"/>',
        ):
            yield
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        return BluOSController()
    
    def test_discover_no_valid_devices(self, controller):
        """Test discover when no valid devices found."""
        with patch.object(controller, '_discover_mdns', return_value=[]):
            with patch.object(controller, '_discover_lsdp', return_value=[]):
                with patch.object(controller.config, 'get', side_effect=lambda k, d=None: {
                    'DISCOVERY_METHOD': DISCOVERY_MDNS,
                    'DISCOVERY_TIMEOUT': 5
                }.get(k, d)):
                    controller.discover(force_refresh=True)
                    assert controller.ips == []
    
    def test_discover_lsdp_error(self, controller):
        """Test discover when LSDP raises exception."""
        with patch.object(controller, '_discover_mdns', return_value=[]):
            with patch('blucommand.controller.LSDPDiscovery') as mock_lsdp_class:
                mock_lsdp_class.side_effect = Exception("LSDP error")
                with patch.object(controller.config, 'get', side_effect=lambda k, d=None: {
                    'DISCOVERY_METHOD': DISCOVERY_LSDP,
                    'DISCOVERY_TIMEOUT': 5
                }.get(k, d)):
                    controller.discover(force_refresh=True)
                    assert controller.ips == []
    
    def test_discover_both_methods(self, controller):
        """Test discover with both methods."""
        with patch.object(controller, '_discover_mdns', return_value=['192.168.1.100']):
            with patch.object(controller, '_discover_lsdp', return_value=['192.168.1.101']):
                with patch.object(controller.config, 'get', side_effect=lambda k, d=None: {
                    'DISCOVERY_METHOD': DISCOVERY_BOTH,
                    'DISCOVERY_TIMEOUT': 5
                }.get(k, d)):
                    with patch('blucommand.controller.validate_ip', side_effect=lambda x: True):
                        controller.discover(force_refresh=True)
                        # Both methods should be called, but only unique IPs kept
                        assert len(controller.ips) >= 1
    
    def test_discover_both_fallback_to_lsdp(self, controller):
        """Test discover with both methods, mDNS fails, falls back to LSDP."""
        with patch.object(controller, '_discover_mdns', return_value=[]):
            with patch.object(controller, '_discover_lsdp', return_value=['192.168.1.100']):
                with patch.object(controller.config, 'get', side_effect=lambda k, d=None: {
                    'DISCOVERY_METHOD': DISCOVERY_BOTH,
                    'DISCOVERY_TIMEOUT': 5
                }.get(k, d)):
                    with patch('blucommand.controller.validate_ip', side_effect=lambda x: True):
                        controller.discover(force_refresh=True)
                        assert len(controller.ips) == 1
    
    def test_discover_mdns_no_output(self, controller):
        """Test _discover_mdns with no output."""
        with patch.object(controller, '_run_dns_sd', return_value=""):
            result = controller._discover_mdns(5)
            assert result == []
    
    def test_discover_mdns_no_hosts(self, controller):
        """Test _discover_mdns with no hosts found."""
        with patch.object(controller, '_run_dns_sd', return_value="some output without SRV"):
            result = controller._discover_mdns(5)
            assert result == []
    
    def test_discover_mdns_no_srv_match(self, controller):
        """Test _discover_mdns with output but no SRV match."""
        with patch.object(controller, '_run_dns_sd', return_value="TXT some data"):
            result = controller._discover_mdns(5)
            assert result == []
    
    def test_discover_lsdp_exception(self, controller):
        """Test _discover_lsdp with exception."""
        with patch('blucommand.controller.LSDPDiscovery') as mock_lsdp_class:
            mock_lsdp_class.side_effect = Exception("Error")
            result = controller._discover_lsdp(5)
            assert result == []
    
    def test_discover_lsdp_calls_discover(self, controller):
        """Test _discover_lsdp calls discover."""
        with patch('blucommand.controller.LSDPDiscovery') as mock_lsdp_class:
            mock_lsdp = MagicMock()
            mock_lsdp.discover.return_value = ['192.168.1.100']
            mock_lsdp_class.return_value = mock_lsdp
            result = controller._discover_lsdp(5)
            assert result == ['192.168.1.100']
            mock_lsdp.discover.assert_called_once()
    
    def test_load_discovery_cache_invalid_json(self, controller):
        """Test loading cache with invalid JSON."""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data="invalid json")):
                result = controller._load_discovery_cache()
                assert result is False
    
    def test_load_discovery_cache_missing_ts(self, controller):
        """Test loading cache with missing timestamp."""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"ips": ["192.168.1.100"]}')):
                result = controller._load_discovery_cache()
                assert result is False
    
    def test_load_discovery_cache_no_ips(self, controller):
        """Test loading cache with no IPs."""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='{"ts": 1000}')):
                result = controller._load_discovery_cache()
                assert result is False

