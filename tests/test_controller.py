"""
Tests for controller module.
"""
import pytest
import json
import os
import time
from unittest.mock import patch, MagicMock, Mock, mock_open
import xml.etree.ElementTree as ET

from controller import BluOSController
from models import PlayerStatus, UniFiClient
from constants import CACHE_FILE, UNIFI_CACHE_FILE


class TestBluOSController:
    """Test BluOSController class."""
    
    @pytest.fixture
    def controller(self, temp_config_dir):
        """Create a controller instance for testing."""
        with patch('controller.CACHE_FILE', os.path.join(temp_config_dir, "cache.json")), \
             patch('controller.UNIFI_CACHE_FILE', os.path.join(temp_config_dir, "unifi.json")):
            return BluOSController()
    
    def test_loads_discovery_cache(self, controller, temp_config_dir):
        """Test loading discovery cache."""
        cache_file = os.path.join(temp_config_dir, "cache.json")
        cache_data = {
            'ts': time.time(),
            'ips': ['192.168.1.1', '192.168.1.2']
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        with patch('controller.CACHE_FILE', cache_file):
            result = controller._load_discovery_cache()
            assert result is True
            assert len(controller.ips) == 2
    
    def test_cache_expired(self, controller, temp_config_dir):
        """Test that expired cache is not used."""
        cache_file = os.path.join(temp_config_dir, "cache.json")
        cache_data = {
            'ts': time.time() - 1000,  # Old timestamp
            'ips': ['192.168.1.1']
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        with patch('controller.CACHE_FILE', cache_file):
            controller.config.data['CACHE_TTL'] = '300'
            result = controller._load_discovery_cache()
            assert result is False
    
    def test_validates_cached_ips(self, controller, temp_config_dir):
        """Test that cached IPs are validated."""
        cache_file = os.path.join(temp_config_dir, "cache.json")
        cache_data = {
            'ts': time.time(),
            'ips': ['127.0.0.1', '192.168.1.1', 'invalid']  # Mix of valid/invalid
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        with patch('controller.CACHE_FILE', cache_file):
            result = controller._load_discovery_cache()
            # Bare IPs normalize to ip:11000; loopback rejected
            assert '192.168.1.1:11000' in controller.ips
            assert '127.0.0.1' not in controller.ips
            assert '127.0.0.1:11000' not in controller.ips
    
    @patch('subprocess.check_output')
    def test_resolves_hosts(self, mock_subprocess, controller):
        """Test hostname resolution."""
        mock_subprocess.return_value = "ip_address: 192.168.1.1\n"
        
        hosts = {'speaker.local'}
        result = controller._resolve_hosts(hosts)
        
        assert '192.168.1.1' in result
        mock_subprocess.assert_called()
    
    def test_validates_resolved_ips(self, controller):
        """Test that resolved IPs are validated."""
        with patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.return_value = "ip_address: 127.0.0.1\n"
            
            hosts = {'speaker.local'}
            result = controller._resolve_hosts(hosts)
            
            # Loopback should be rejected
            assert '127.0.0.1' not in result
    
    @patch('controller.Network.get')
    def test_get_device_info(self, mock_network, controller):
        """Test getting device information (no /diagnostics by default)."""
        sync_xml = b'<sync name="Test Speaker" modelName="Node" brand="BluOS" version="1.0"/>'
        status_xml = b'<status><volume>50</volume><state>play</state><service>Library</service></status>'
        
        mock_network.side_effect = [sync_xml, status_xml]
        
        status = controller.get_device_info("192.168.1.1")
        
        assert status.name == "Test Speaker"
        assert status.volume == 50
        assert status.state == "play"
        assert mock_network.call_count == 2
        assert all('/diagnostics' not in str(c) for c in mock_network.call_args_list)

    @patch('controller.Network.get')
    def test_get_device_info_include_uptime(self, mock_network, controller):
        """Status path may request /diagnostics for uptime."""
        sync_xml = b'<sync name="Test Speaker" modelName="Node" brand="BluOS" version="1.0"/>'
        status_xml = b'<status><volume>50</volume><state>play</state></status>'
        html = b'<html>Uptime: 1 day</html>'
        mock_network.side_effect = [sync_xml, status_xml, html]

        status = controller.get_device_info("192.168.1.1", include_uptime=True)

        assert status.name == "Test Speaker"
        assert mock_network.call_count == 3
    
    def test_get_device_info_invalid_ip(self, controller):
        """Test that invalid IPs are handled."""
        status = controller.get_device_info("127.0.0.1")
        
        assert status.status == "invalid"
    
    @patch('controller.Network.get')
    def test_safe_xml_parsing(self, mock_network, controller):
        """Test safe XML parsing."""
        # Test with valid XML
        valid_xml = b'<sync name="Test"/>'
        root = controller._safe_parse_xml(valid_xml, "192.168.1.1")
        assert root is not None
        assert root.attrib['name'] == "Test"
    
    def test_safe_xml_parsing_rejects_large_xml(self, controller):
        """Test that large XML is rejected."""
        from constants import MAX_XML_SIZE
        large_xml = b'<sync>' + b'x' * (MAX_XML_SIZE + 1) + b'</sync>'
        
        root = controller._safe_parse_xml(large_xml, "192.168.1.1")
        assert root is None
    
    def test_safe_xml_parsing_rejects_deep_xml(self, controller):
        """Test that deeply nested XML is rejected."""
        from constants import MAX_XML_DEPTH
        # Create deeply nested XML
        deep_xml = b'<root>' + b'<nested>' * (MAX_XML_DEPTH + 5) + b'</nested>' * (MAX_XML_DEPTH + 5) + b'</root>'
        
        root = controller._safe_parse_xml(deep_xml, "192.168.1.1")
        assert root is None
    
    @patch('controller.Network.get')
    @patch('os.path.exists')
    @patch('config.get_api_key', return_value=None)
    def test_sync_unifi_success(self, mock_keychain, mock_exists, mock_network, controller):
        """Test successful UniFi sync for Wi‑Fi (STA rates, no device fetch)."""
        # Ensure cache doesn't exist so we test fresh fetch
        mock_exists.return_value = False
        
        controller.ips = ['192.168.1.1']
        controller.config.data = {
            'UNIFI_ENABLED': 'true',
            'UNIFI_CONTROLLER': 'controller.local',
            'UNIFI_API_KEY': 'test-key',
            'UNIFI_SITE': 'default',
            'CACHE_TTL': '300'
        }
        
        unifi_response = {
            'data': [{
                'ip': '192.168.1.1',
                'is_wired': False,
                'ap_name': 'Test AP',
                'essid': 'TestNetwork',
                'mac': 'aa:bb:cc:dd:ee:ff',
                'tx_bytes': 1000,
                'rx_bytes': 2000,
                'tx_bytes-r': 100,
                'rx_bytes-r': 200,
                'uptime': 3600
            }]
        }
        
        mock_network.return_value = json.dumps(unifi_response).encode()
        
        result = controller.sync_unifi()
        
        assert result.startswith("SUCCESS:")
        assert '192.168.1.1' in controller.unifi_map
        wifi = controller.unifi_map['192.168.1.1']
        assert wifi.rate_source == "wifi"
        assert wifi.down_rate == 100
        assert wifi.up_rate == 200
        assert mock_network.call_count == 1

    @patch('controller.Network.get')
    @patch('os.path.exists')
    @patch('config.get_api_key', return_value=None)
    def test_sync_unifi_wired_uses_switch_port_rates(
        self, mock_keychain, mock_exists, mock_network, controller
    ):
        """Wired clients prefer switch port_table rates over broken STA rates."""
        mock_exists.return_value = False
        controller.ips = ['192.168.1.35']
        controller.config.data = {
            'UNIFI_ENABLED': 'true',
            'UNIFI_CONTROLLER': 'controller.local',
            'UNIFI_API_KEY': 'test-key',
            'UNIFI_SITE': 'default',
            'CACHE_TTL': '300',
        }

        sta_response = {
            'data': [{
                'ip': '192.168.1.35',
                'is_wired': True,
                'last_uplink_name': 'sw3-01',
                'sw_mac': '11:22:33:44:55:66',
                'sw_port': 9,
                'mac': 'aa:bb:cc:dd:ee:01',
                'wired-tx_bytes': 1_000_000,
                'wired-rx_bytes': 2_000_000,
                'wired-tx_bytes-r': 0,
                'wired-rx_bytes-r': 0,
                'uptime': 3600,
            }]
        }
        device_response = {
            'data': [{
                'mac': '11:22:33:44:55:66',
                'type': 'usw',
                'name': 'sw3-01',
                'port_table': [
                    {
                        'port_idx': 9,
                        'tx_bytes-r': 500_000,  # to client ≈ download
                        'rx_bytes-r': 12_000,   # from client ≈ upload
                    }
                ],
            }]
        }
        mock_network.side_effect = [
            json.dumps(sta_response).encode(),
            json.dumps(device_response).encode(),
        ]

        result = controller.sync_unifi()

        assert result == "SUCCESS:1"
        wired = controller.unifi_map['192.168.1.35']
        assert wired.is_wired is True
        assert wired.rate_source == "switch-port"
        assert wired.down_rate == 500_000
        assert wired.up_rate == 12_000
        assert wired.down_tot == 1_000_000
        assert wired.uplink == "sw3-01"
        assert wired.port_info == "9"
        assert mock_network.call_count == 2

    @patch('controller.Network.get')
    @patch('os.path.exists')
    @patch('config.get_api_key', return_value=None)
    def test_sync_unifi_wired_falls_back_to_client_rates(
        self, mock_keychain, mock_exists, mock_network, controller
    ):
        """If switch stats are missing, keep wired STA rates as fallback."""
        mock_exists.return_value = False
        controller.ips = ['192.168.1.35']
        controller.config.data = {
            'UNIFI_ENABLED': 'true',
            'UNIFI_CONTROLLER': 'controller.local',
            'UNIFI_API_KEY': 'test-key',
            'UNIFI_SITE': 'default',
            'CACHE_TTL': '300',
        }
        sta_response = {
            'data': [{
                'ip': '192.168.1.35',
                'is_wired': True,
                'last_uplink_name': 'sw3-01',
                'sw_mac': '11:22:33:44:55:66',
                'sw_port': 9,
                'mac': 'aa:bb:cc:dd:ee:01',
                'wired-tx_bytes': 100,
                'wired-rx_bytes': 200,
                'wired-tx_bytes-r': 50,
                'wired-rx_bytes-r': 25,
                'uptime': 10,
            }]
        }
        mock_network.side_effect = [
            json.dumps(sta_response).encode(),
            None,  # stat/device failed
        ]

        result = controller.sync_unifi()

        assert result == "SUCCESS:1"
        wired = controller.unifi_map['192.168.1.35']
        assert wired.rate_source == "client"
        assert wired.down_rate == 50
        assert wired.up_rate == 25
    
    def test_sync_unifi_skipped_when_disabled(self, controller):
        """Test that UniFi sync is skipped when disabled."""
        controller.config.data['UNIFI_ENABLED'] = 'false'
        
        result = controller.sync_unifi()
        
        assert result == "SKIPPED"
    
    @patch('config.get_api_key', return_value=None)
    def test_sync_unifi_missing_config(self, mock_keychain, controller):
        """Test UniFi sync with missing config."""
        controller.ips = ['192.168.1.1']
        controller.config.data = {
            'UNIFI_ENABLED': 'true',
            'UNIFI_CONTROLLER': '',
            'UNIFI_API_KEY': ''
        }
        
        result = controller.sync_unifi()
        
        assert result == "MISSING_CONFIG"
    
    @patch('controller.Network.get')
    @patch('os.path.exists')
    @patch('config.get_api_key', return_value='keychain-api-key')
    def test_sync_unifi_uses_keychain(self, mock_keychain, mock_exists, mock_network, controller):
        """Test that UniFi sync uses API key from Keychain when available."""
        # Ensure cache doesn't exist so we test fresh fetch
        mock_exists.return_value = False
        
        controller.ips = ['192.168.1.1']
        controller.config.data = {
            'UNIFI_ENABLED': 'true',
            'UNIFI_CONTROLLER': 'controller.local',
            'UNIFI_API_KEY': '',  # Empty in config, should use Keychain
            'UNIFI_SITE': 'default',
            'CACHE_TTL': '300'
        }
        
        unifi_response = {
            'data': [{
                'ip': '192.168.1.1',
                'is_wired': False,
                'ap_name': 'Test AP',
                'essid': 'TestNetwork',
                'mac': 'aa:bb:cc:dd:ee:ff',
                'tx_bytes': 1000,
                'rx_bytes': 2000,
                'tx_bytes-r': 100,
                'rx_bytes-r': 200,
                'uptime': 3600
            }]
        }
        
        mock_network.return_value = json.dumps(unifi_response).encode()
        
        result = controller.sync_unifi()
        
        # Should succeed using Keychain API key
        assert result.startswith("SUCCESS:"), f"Expected SUCCESS but got: {result}"
        assert '192.168.1.1' in controller.unifi_map
        # Verify the API key from Keychain was used (check Network.get was called with correct headers)
        assert mock_network.called
        # Verify the mock was called with the Keychain API key
        mock_keychain.assert_called()

    def test_switch_port_rate_index(self, controller):
        """Port index maps switch MAC + port to TX/RX rates."""
        devices = [{
            'mac': 'AA:BB:CC:DD:EE:FF',
            'port_table': [
                {'port_idx': 3, 'tx_bytes-r': 1000, 'rx_bytes-r': 200},
                {'port_idx': 'bad', 'tx_bytes-r': 1, 'rx_bytes-r': 1},
            ],
        }]
        index = controller._switch_port_rate_index(devices)
        assert index[('aa:bb:cc:dd:ee:ff', 3)] == (1000.0, 200.0)
        assert ('aa:bb:cc:dd:ee:ff', 'bad') not in index
    
    @patch('controller.Network.get')
    def test_get_sys_uptime(self, mock_network, controller):
        """Test getting system uptime."""
        mock_network.return_value = b'<html><div>Uptime:</div><div>2 days</div></html>'
        
        result = controller.get_sys_uptime("192.168.1.1")
        
        assert result == "2 days"
    
    def test_get_sys_uptime_invalid_ip(self, controller):
        """Test getting uptime with invalid IP."""
        result = controller.get_sys_uptime("127.0.0.1")
        
        assert result == "N/A"

