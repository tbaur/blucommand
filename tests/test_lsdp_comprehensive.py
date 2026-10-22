"""
Comprehensive tests for LSDP discovery protocol.
"""
import pytest
import socket
import struct
from unittest.mock import Mock, patch, MagicMock

from blucommand.lsdp import (
    LSDPDiscovery,
    LSDPDevice,
    LSDP_PORT,
    CLASS_BLUOS_PLAYER,
    CLASS_BLUOS_PLAYER_SECONDARY,
    CLASS_BLUOS_HUB,
)


class TestLSDPComprehensive:
    """Comprehensive LSDP tests."""
    
    @patch("blucommand.lsdp.ipv4_broadcast_addresses", return_value=["192.0.2.255"])
    def test_lsdp_discovery_timeout(self, _mock_broadcast):
        """A short listen with no replies returns no endpoints and still queries."""
        discovery = LSDPDiscovery(timeout=0.05)

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock
            mock_sock.recvfrom.side_effect = socket.timeout()

            result = discovery.discover()
            assert result == []
            assert mock_sock.sendto.call_count == 1
            mock_sock.bind.assert_called_with(("0.0.0.0", LSDP_PORT))

    @patch("blucommand.lsdp.ipv4_broadcast_addresses", return_value=["192.0.2.255"])
    def test_lsdp_discovery_with_class_ids(self, _mock_broadcast):
        """Test LSDP discovery with specific class IDs."""
        discovery = LSDPDiscovery(timeout=0.05)

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock
            mock_sock.recvfrom.side_effect = socket.timeout()

            result = discovery.discover([CLASS_BLUOS_PLAYER, CLASS_BLUOS_HUB])
            assert result == []
    
    def test_build_query_packet_structure(self):
        """Test query packet structure."""
        discovery = LSDPDiscovery()
        packet = discovery._build_query_packet([CLASS_BLUOS_PLAYER])
        
        assert len(packet) >= 6
        assert packet[1:5] == b'LSDP'
        assert packet[5] == 1  # Version
    
    def test_parse_announce_message(self):
        """Test parsing announce message."""
        discovery = LSDPDiscovery()
        
        # Build a simple announce packet
        packet = b'\x06LSDP\x01'  # Header
        packet += b'\x15\x41'  # Announce message (length 21, type 'A')
        packet += b'\x06aa:bb:cc'  # Node ID
        packet += b'\x04\xc0\xa8\x01\x64'  # IPv4 (192.168.1.100)
        packet += b'\x01'  # Count
        packet += b'\x00\x01'  # Class ID
        packet += b'\x00'  # TXT count
        
        discovery._parse_packet(packet, "192.168.1.100")
        # Should parse without error
    
    def test_parse_packet_with_txt_records(self):
        """Test parsing packet with TXT records."""
        discovery = LSDPDiscovery()
        
        # Build packet with TXT records
        packet = b'\x06LSDP\x01'  # Header
        packet += b'\x20\x41'  # Announce message
        packet += b'\x06aa:bb:cc'  # Node ID
        packet += b'\x04\xc0\xa8\x01\x64'  # IPv4
        packet += b'\x01'  # Count
        packet += b'\x00\x01'  # Class ID
        packet += b'\x01'  # TXT count
        packet += b'\x04name'  # Key
        packet += b'\x05value'  # Value
        
        discovery._parse_packet(packet, "192.168.1.100")
        # Should parse TXT records
    
    def test_parse_packet_invalid_version(self):
        """Test parsing packet with invalid version."""
        discovery = LSDPDiscovery()
        packet = b'\x06LSDP\x02'  # Version 2 (invalid)
        
        discovery._parse_packet(packet, "192.168.1.100")
        assert len(discovery.discovered_devices) == 0
    
    def test_parse_packet_short_header(self):
        """Test parsing packet that's too short."""
        discovery = LSDPDiscovery()
        packet = b'\x05LSDP'  # Too short
        
        discovery._parse_packet(packet, "192.168.1.100")
        assert len(discovery.discovered_devices) == 0
    
    def test_parse_announce_multiple_records(self):
        """Test parsing announce with multiple service records."""
        discovery = LSDPDiscovery()
        
        # Build packet with multiple records
        packet = b'\x06LSDP\x01'
        packet += b'\x25\x41'  # Announce
        packet += b'\x06aa:bb:cc'
        packet += b'\x04\xc0\xa8\x01\x64'
        packet += b'\x02'  # 2 records
        packet += b'\x00\x01'  # Record 1
        packet += b'\x00'  # No TXT
        packet += b'\x00\x08'  # Record 2
        packet += b'\x00'  # No TXT
        
        discovery._parse_packet(packet, "192.168.1.100")
        # Should handle multiple records
    
    def test_endpoints_keep_zone_port_and_drop_unaddressable_secondary(self):
        """Secondary zones need an announced port. Loopback is not a player."""
        discovery = LSDPDiscovery()
        discovery.discovered_devices = {
            ("aa", CLASS_BLUOS_PLAYER): LSDPDevice(
                "aa", "127.0.0.1", CLASS_BLUOS_PLAYER, {}
            ),
            ("bb", CLASS_BLUOS_PLAYER): LSDPDevice(
                "bb", "192.168.1.100", CLASS_BLUOS_PLAYER, {"port": "11000"}, port=11000
            ),
            ("cc", CLASS_BLUOS_PLAYER_SECONDARY): LSDPDevice(
                "cc", "192.168.1.100", CLASS_BLUOS_PLAYER_SECONDARY, {"port": "11010"}, port=11010
            ),
            ("dd", CLASS_BLUOS_PLAYER_SECONDARY): LSDPDevice(
                "dd", "192.168.1.100", CLASS_BLUOS_PLAYER_SECONDARY, {}
            ),
        }

        assert discovery.endpoints() == ["192.168.1.100:11000", "192.168.1.100:11010"]

    def test_parse_keeps_mac_bytes_above_0x7f(self):
        """Two chassis that differ only in a high MAC byte stay distinct."""
        discovery = LSDPDiscovery()
        for mac, last in ((bytes.fromhex("0200000000a1"), 0xA1), (bytes.fromhex("0200000000b2"), 0xB2)):
            body = bytearray([0, 0x41, len(mac), *mac, 4, 192, 168, 1, 100, 1, 0, 1, 0])
            body[0] = len(body)
            packet = b"\x06LSDP\x01" + bytes(body)
            discovery._parse_packet(packet, "192.168.1.100")
            assert any(device.node_id.endswith(f"{last:02x}") for device in discovery.discovered_devices.values())
        assert len(discovery.discovered_devices) == 2

    def test_zero_length_message_does_not_loop(self):
        """A length byte of 0 must not stick the parser on the same offset."""
        discovery = LSDPDiscovery()
        discovery._parse_packet(b"\x06LSDP\x01\x00", "192.168.1.100")
        assert discovery.discovered_devices == {}

