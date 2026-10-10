"""
Tests for XML parsing and device info in controller.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from controller import BluOSController
from models import PlayerStatus
from constants import MAX_XML_SIZE, MAX_XML_DEPTH, MAX_XML_ELEMENTS, MAX_XML_ATTRIBUTES


class TestXMLParsing:
    """Test XML parsing methods."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('controller.Config'):
            ctl = BluOSController()
            return ctl
    
    def test_safe_parse_xml_valid(self, controller):
        """Test safe XML parsing with valid XML."""
        xml_data = b'<sync name="Test" modelName="Node"/>'
        root = controller._safe_parse_xml(xml_data, "192.168.1.1")
        assert root is not None
        assert root.attrib['name'] == "Test"
    
    def test_safe_parse_xml_empty(self, controller):
        """Test safe XML parsing with empty data."""
        result = controller._safe_parse_xml(b'', "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_none(self, controller):
        """Test safe XML parsing with None."""
        result = controller._safe_parse_xml(None, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_too_large(self, controller):
        """Test safe XML parsing rejects large XML."""
        large_xml = b'<sync>' + b'x' * (MAX_XML_SIZE + 1) + b'</sync>'
        result = controller._safe_parse_xml(large_xml, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_too_deep(self, controller):
        """Test safe XML parsing rejects deep nesting."""
        deep_xml = b'<root>' + b'<nested>' * (MAX_XML_DEPTH + 5) + b'</nested>' * (MAX_XML_DEPTH + 5) + b'</root>'
        result = controller._safe_parse_xml(deep_xml, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_invalid(self, controller):
        """Test safe XML parsing with invalid XML."""
        invalid_xml = b'<unclosed>'
        result = controller._safe_parse_xml(invalid_xml, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_whitespace_only(self, controller):
        """Test safe XML parsing rejects whitespace-only XML."""
        result = controller._safe_parse_xml(b'   \n\t  ', "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_too_many_elements(self, controller):
        """Test safe XML parsing rejects XML with too many elements."""
        # Create XML with more than MAX_XML_ELEMENTS elements
        many_elements = b'<root>' + b'<item/>' * (MAX_XML_ELEMENTS + 100) + b'</root>'
        result = controller._safe_parse_xml(many_elements, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_too_many_attributes(self, controller):
        """Test safe XML parsing rejects elements with too many attributes."""
        # Create XML with element having more than MAX_XML_ATTRIBUTES * 2 attributes
        # (root element gets 2x limit, so we need more than that)
        attrs = ' '.join([f'a{i}="value{i}"' for i in range(MAX_XML_ATTRIBUTES * 2 + 10)])
        many_attrs_xml = f'<root {attrs}/>'.encode()
        result = controller._safe_parse_xml(many_attrs_xml, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_large_text_node(self, controller):
        """Test safe XML parsing rejects elements with excessively large text nodes."""
        # Create XML with text node larger than 10% of MAX_XML_SIZE
        large_text = b'x' * (MAX_XML_SIZE // 10 + 1000)
        large_text_xml = f'<root>{large_text.decode("latin-1")}</root>'.encode('latin-1')
        result = controller._safe_parse_xml(large_text_xml, "192.168.1.1")
        assert result is None
    
    def test_safe_parse_xml_recursion_error_handling(self, controller):
        """Test that recursion errors are handled gracefully."""
        # Create deeply nested XML that would cause recursion error
        very_deep_xml = b'<root>' + b'<nested>' * (MAX_XML_DEPTH * 2) + b'</nested>' * (MAX_XML_DEPTH * 2) + b'</root>'
        result = controller._safe_parse_xml(very_deep_xml, "192.168.1.1")
        assert result is None


class TestDeviceInfo:
    """Test device info retrieval."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('controller.Network.get')
    def test_get_device_info_full(self, mock_network, controller):
        """Test getting full device info."""
        sync_xml = b'<sync name="Speaker" modelName="Node" brand="BluOS" version="1.0" db="192.168.1.100" master=""/>'
        status_xml = b'<status><volume>50</volume><state>play</state><service>Library</service><title1>Song</title1><artist>Artist</artist><album>Album</album></status>'
        html = b'<html>Uptime: 1 day</html>'
        
        mock_network.side_effect = [sync_xml, status_xml, html]
        
        status = controller.get_device_info("192.168.1.100")
        
        assert status.name == "Speaker"
        assert status.volume == 50
        assert status.state == "play"
        assert status.track == "Song"
    
    @patch('controller.Network.get')
    def test_get_device_info_no_sync(self, mock_network, controller):
        """Test getting device info without sync XML."""
        status_xml = b'<status><volume>50</volume></status>'
        html = b'<html>Uptime: 1 day</html>'
        
        mock_network.side_effect = [None, status_xml, html]
        
        status = controller.get_device_info("192.168.1.100")
        assert status.name == "Unknown"
        assert status.volume == 50
    
    @patch('controller.Network.get')
    def test_get_device_info_xml_error(self, mock_network, controller):
        """Test device info with XML parse error."""
        mock_network.return_value = b'<invalid>'
        
        status = controller.get_device_info("192.168.1.100")
        assert status.status in ["xml_error", "parse_error", "error"]
    
    @patch('controller.Network.get')
    def test_get_device_info_with_battery(self, mock_network, controller):
        """Test device info with battery information."""
        sync_xml = b'<sync name="Portable"><battery level="75"/></sync>'
        status_xml = b'<status><volume>50</volume></status>'
        
        mock_network.side_effect = [sync_xml, status_xml, None]
        
        status = controller.get_device_info("192.168.1.100")
        assert status.battery == "75"
    
    @patch('controller.Network.get')
    def test_get_device_info_with_master(self, mock_network, controller):
        """Test device info with sync master child element."""
        sync_xml = b'<SyncStatus name="Slave"><master>192.168.1.100</master></SyncStatus>'
        status_xml = b'<status><volume>50</volume></status>'
        
        mock_network.side_effect = [sync_xml, status_xml, None]
        
        status = controller.get_device_info("192.168.1.101")
        assert status.master == "192.168.1.100:11000"

    @patch('controller.Network.get')
    def test_synced_slave_prefers_syncstatus_volume(self, mock_network, controller):
        """Synced /Status volume is group level — prefer SyncStatus attribute."""
        sync_xml = (
            b'<SyncStatus name="Player A" volume="64" db="-8.7">'
            b'<master port="11000">192.168.1.174</master>'
            b'</SyncStatus>'
        )
        status_xml = (
            b'<status><volume>15</volume><groupVolume>15</groupVolume>'
            b'<state>stream</state><title1>Track</title1></status>'
        )
        mock_network.side_effect = [sync_xml, status_xml, None]

        status = controller.get_device_info("192.168.1.88")
        assert status.volume == 64
        assert status.state == "stream"
        assert status.track == "Track"
    
    @patch('controller.Network.get')
    def test_get_device_info_roon_service(self, mock_network, controller):
        """Test device info with Roon service."""
        sync_xml = b'<sync name="Speaker"/>'
        status_xml = b'<status><service>Raat</service></status>'
        
        mock_network.side_effect = [sync_xml, status_xml, None]
        
        status = controller.get_device_info("192.168.1.100")
        assert status.service == "Roon"

