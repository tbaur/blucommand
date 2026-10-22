"""
Comprehensive tests for LSDP discovery protocol.
"""
import ctypes
import socket
import struct
from unittest.mock import MagicMock, patch

import pytest

from blucommand.lsdp import (
    LSDPDiscovery,
    LSDPDevice,
    LSDP_PORT,
    CLASS_BLUOS_PLAYER,
    CLASS_BLUOS_PLAYER_SECONDARY,
    CLASS_BLUOS_HUB,
    _Reader,
    _announced_port,
    _ipv4_at,
    _open_socket,
    _read_record,
    _send_query,
    _walk_ifaddrs,
    ipv4_broadcast_addresses,
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


def _announce(node, address, class_id, txt=()):
    """Build one datagram whose only message is an announce."""
    body = bytearray([len(node), *node, len(address), *address, 1])
    body += struct.pack("!H", class_id)
    body.append(len(txt))
    for key, value in txt:
        key_bytes = key.encode()
        value_bytes = value.encode()
        body += bytes([len(key_bytes), *key_bytes, len(value_bytes), *value_bytes])
    message = bytearray([0, 0x41]) + body
    message[0] = len(message)
    return b"\x06LSDP\x01" + bytes(message)


def _sockaddr(address, family=socket.AF_INET):
    raw = bytearray(16)
    raw[1] = family & 0xFF
    if family == socket.AF_INET:
        raw[4:8] = socket.inet_aton(address)
    return ctypes.create_string_buffer(bytes(raw))


class TestLSDPEdges:
    """Parser, socket, and interface-lookup branches."""

    def test_discover_logs_and_returns_empty_when_the_socket_fails(self):
        discovery = LSDPDiscovery(timeout=0.05)
        with patch("blucommand.lsdp._open_socket", side_effect=OSError("down")):
            assert discovery.discover() == []

    def test_exchange_warns_when_no_broadcast_address_exists(self):
        discovery = LSDPDiscovery(timeout=0.05)
        sock = MagicMock()
        sock.recvfrom.side_effect = TimeoutError()
        with patch("blucommand.lsdp.ipv4_broadcast_addresses", return_value=[]):
            discovery._exchange(sock, b"query")
        sock.sendto.assert_not_called()

    def test_exchange_stops_when_the_socket_fails(self):
        discovery = LSDPDiscovery(timeout=0.05)
        sock = MagicMock()
        sock.recvfrom.side_effect = OSError("closed")
        with patch("blucommand.lsdp.ipv4_broadcast_addresses", return_value=["192.0.2.255"]):
            discovery._exchange(sock, b"query")

    def test_truncated_txt_record_is_dropped(self):
        discovery = LSDPDiscovery()
        message = bytearray([0, 0x41, 1, 0xAA, 4, 192, 0, 2, 10, 1])
        message[0] = len(message)
        discovery._parse_announce(bytes(message), "192.0.2.10")
        assert discovery.discovered_devices == {}

        reader = _Reader(b"\x00\x01\x01", offset=0)
        assert _read_record(reader) is None
        reader = _Reader(b"\x00\x01\x01\x04name\x05value", offset=0)
        assert _read_record(reader) == (1, {"name": "value"})

    def test_receive_treats_refused_and_empty_address_as_continue(self):
        discovery = LSDPDiscovery()
        sock = MagicMock()
        sock.recvfrom.side_effect = ConnectionRefusedError()
        assert discovery._receive_one(sock, 0.01) is True

        sock.recvfrom.side_effect = None
        sock.recvfrom.return_value = (b"", None)
        assert discovery._receive_one(sock, 0.01) is True

        sock.recvfrom.side_effect = OSError("closed")
        assert discovery._receive_one(sock, 0.01) is False

    def test_parse_skips_non_announce_and_drops_unknown_class(self):
        discovery = LSDPDiscovery()
        discovery._parse_packet(b"\x06LSDP\x01\x02\x51", "192.0.2.10")
        discovery._parse_packet(b"\x06LSDP\x01\x50\x41", "192.0.2.10")
        assert discovery.discovered_devices == {}

        packet = _announce(b"\x02", b"\x01\x02", 0x0002)
        discovery._parse_packet(packet, "192.0.2.10")
        assert discovery.discovered_devices == {}

    def test_parse_uses_source_ip_when_the_address_is_not_ipv4(self):
        discovery = LSDPDiscovery()
        packet = _announce(b"\xaa", b"\x01\x02", CLASS_BLUOS_PLAYER)
        discovery._parse_packet(packet, "192.0.2.10")
        device = next(iter(discovery.discovered_devices.values()))
        assert device.ip == "192.0.2.10"

    def test_truncated_announce_and_record_store_nothing(self):
        discovery = LSDPDiscovery()
        discovery._parse_announce(b"\x02\x41", "192.0.2.10")
        assert discovery.discovered_devices == {}

        reader = _Reader(b"\x00\x01", offset=0)
        assert _read_record(reader) is None
        assert _Reader(b"", offset=0).byte() is None
        assert _Reader(b"\x05", offset=0).chunk() is None
        assert _Reader(b"\x01\xff", offset=0).take(4) is None

    def test_announced_port_rejects_text_and_out_of_range(self):
        assert _announced_port({}) is None
        assert _announced_port({"port": "nope"}) is None
        assert _announced_port({"port": "80"}) is None
        assert _announced_port({"port": "11000"}) == 11000

    def test_open_socket_survives_reuseport_and_closes_on_bind_failure(self):
        sock = MagicMock()

        def setsockopt(_level, option, _value):
            if option == socket.SO_REUSEPORT:
                raise OSError("unsupported")

        sock.setsockopt.side_effect = setsockopt
        with patch("socket.socket", return_value=sock):
            assert _open_socket() is sock
        sock.bind.assert_called_with(("0.0.0.0", LSDP_PORT))

        failed = MagicMock()
        failed.bind.side_effect = OSError("busy")
        with patch("socket.socket", return_value=failed):
            with pytest.raises(OSError):
                _open_socket()
        failed.close.assert_called_once()

    def test_send_query_logs_and_continues(self):
        sock = MagicMock()
        sock.sendto.side_effect = OSError("unreachable")
        _send_query(sock, b"query", ["192.0.2.255"])
        sock.sendto.assert_called_once()

    def test_broadcast_lookup_returns_empty_when_libc_is_unavailable(self):
        with patch("blucommand.lsdp.ctypes.util.find_library", return_value=None):
            assert ipv4_broadcast_addresses() == []
        with patch("blucommand.lsdp.ctypes.util.find_library", return_value="c"):
            with patch("blucommand.lsdp.ctypes.CDLL", side_effect=OSError("no libc")):
                assert ipv4_broadcast_addresses() == []

    def test_walk_ifaddrs_keeps_one_broadcast_and_skips_the_rest(self):
        good_addr = _sockaddr("192.0.2.10")
        good_broadcast = _sockaddr("192.0.2.255")
        second_addr = _sockaddr("192.0.2.11")
        same_broadcast = _sockaddr("192.0.2.255")
        loopback = _sockaddr("127.0.0.1")
        from blucommand import lsdp

        nodes = (lsdp._Ifaddrs * 3)()
        nodes[0].ifa_flags = lsdp._IFF_UP | lsdp._IFF_BROADCAST
        nodes[0].ifa_addr = ctypes.cast(good_addr, ctypes.c_void_p)
        nodes[0].ifa_dstaddr = ctypes.cast(good_broadcast, ctypes.c_void_p)
        nodes[0].ifa_next = ctypes.pointer(nodes[1])
        nodes[1].ifa_flags = lsdp._IFF_UP | lsdp._IFF_BROADCAST
        nodes[1].ifa_addr = ctypes.cast(second_addr, ctypes.c_void_p)
        nodes[1].ifa_dstaddr = ctypes.cast(same_broadcast, ctypes.c_void_p)
        nodes[1].ifa_next = ctypes.pointer(nodes[2])
        nodes[2].ifa_flags = lsdp._IFF_UP | lsdp._IFF_BROADCAST
        nodes[2].ifa_addr = ctypes.cast(loopback, ctypes.c_void_p)
        nodes[2].ifa_dstaddr = ctypes.cast(good_broadcast, ctypes.c_void_p)
        nodes[2].ifa_next = ctypes.POINTER(lsdp._Ifaddrs)()

        libc = MagicMock()

        def getifaddrs(head_ptr):
            head_ptr._obj.contents = ctypes.pointer(nodes[0])
            return 0

        libc.getifaddrs.side_effect = getifaddrs
        assert _walk_ifaddrs(libc) == ["192.0.2.255"]

        failed = MagicMock()
        failed.getifaddrs.return_value = -1
        assert _walk_ifaddrs(failed) == []

    def test_ipv4_at_rejects_null_loopback_and_other_families(self):
        assert _ipv4_at(None) is None
        assert _ipv4_at(0) is None
        assert _ipv4_at(ctypes.addressof(_sockaddr("127.0.0.1"))) is None
        assert _ipv4_at(ctypes.addressof(_sockaddr("192.0.2.10", family=1))) is None
        assert _ipv4_at(ctypes.addressof(_sockaddr("192.0.2.10"))) == "192.0.2.10"

    def test_endpoints_drop_a_repeated_address(self):
        discovery = LSDPDiscovery()
        first = LSDPDevice("aa", "192.0.2.10", CLASS_BLUOS_PLAYER, {}, port=11000)
        second = LSDPDevice("bb", "192.0.2.10", CLASS_BLUOS_PLAYER, {}, port=11000)
        discovery.discovered_devices = {("aa", 1): first, ("bb", 1): second}
        assert discovery.endpoints() == ["192.0.2.10:11000"]

