#!/usr/bin/env python3
"""
LSDP (Lenbrook Service Discovery Protocol).

Announces are broadcast to UDP 11430. macOS rejects 255.255.255.255, so queries
go to each interface's own broadcast address, and the socket must be bound to
11430 or those announces never arrive. Node IDs are raw MAC bytes. Secondary
zones are addressable only when the announce includes a port.

Copyright 2025 tbaur

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import ctypes
import ctypes.util
import logging
import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from blucommand.constants import BLUOS_PORT
from blucommand.validators import format_endpoint, sanitize_ip, validate_bluos_port

logger = logging.getLogger("blucommand")

LSDP_PORT = 11430
LSDP_MAGIC = b"LSDP"
LSDP_VERSION = 1
MSG_QUERY = 0x51
MSG_ANNOUNCE = 0x41

CLASS_BLUOS_PLAYER = 0x0001
CLASS_BLUOS_SERVER = 0x0002
CLASS_BLUOS_PLAYER_SECONDARY = 0x0003
CLASS_BLUOS_PLAYER_PAIR_SLAVE = 0x0006
CLASS_BLUOS_HUB = 0x0008
CLASS_ALL = 0xFFFF

# Pair slaves (0x0006) are not queried. The primary controls them.
QUERIED_CLASSES = (CLASS_BLUOS_PLAYER, CLASS_BLUOS_PLAYER_SECONDARY, CLASS_BLUOS_HUB)
# Repeats cover lost packets. Listening runs between sends.
_QUERY_OFFSETS = (0.0, 0.2, 0.4, 0.6, 0.9, 1.2, 1.5)
_MIN_WAIT_SECONDS = 0.01
_RECV_BUFFER_BYTES = 4096
_IFF_UP = 0x1
_IFF_BROADCAST = 0x2


@dataclass
class LSDPDevice:
    """One announced record. ``node_id`` is the MAC as hex, not decoded text."""
    node_id: str
    ip: str
    class_id: int
    txt_records: Dict[str, str] = field(default_factory=dict)
    port: Optional[int] = None


class LSDPDiscovery:
    """Broadcast LSDP queries and collect the announces that answer them."""

    def __init__(self, timeout: float = 5):
        self.timeout = timeout
        self.discovered_devices: Dict[Tuple[str, int], LSDPDevice] = {}
        self._accepted_classes = frozenset(QUERIED_CLASSES)

    def discover(self, class_ids: Optional[List[int]] = None) -> List[str]:
        """
        Listen for ``timeout`` seconds.

        Returns canonical ``ip:port`` endpoints. A secondary zone whose announce
        names no port is omitted, because it cannot be addressed.
        """
        queried = list(class_ids) if class_ids is not None else list(QUERIED_CLASSES)
        self._accepted_classes = frozenset(queried)
        self.discovered_devices.clear()
        sock: Optional[socket.socket] = None
        try:
            sock = _open_socket()
            self._exchange(sock, self._build_query_packet(queried))
        except OSError as exc:
            logger.error(f"LSDP discovery error: {exc}")
        finally:
            if sock is not None:
                sock.close()
        return self.endpoints()

    def endpoints(self) -> List[str]:
        """Addressable ``ip:port`` values from announces collected so far."""
        found: List[str] = []
        for device in self.discovered_devices.values():
            ip = sanitize_ip(device.ip)
            if not ip:
                continue
            if device.class_id == CLASS_BLUOS_PLAYER_SECONDARY and device.port is None:
                continue
            port = device.port if device.port is not None else BLUOS_PORT
            endpoint = format_endpoint(ip, port)
            if endpoint not in found:
                found.append(endpoint)
        return sorted(found)

    def _exchange(self, sock: socket.socket, packet: bytes) -> None:
        """Send staggered queries and read announces until the timeout."""
        targets = ipv4_broadcast_addresses()
        if not targets:
            logger.warning("No IPv4 broadcast addresses; LSDP query not sent")
        started = time.monotonic()
        deadline = started + self.timeout
        send_times = [started + offset for offset in _QUERY_OFFSETS if offset < self.timeout]
        while (now := time.monotonic()) < deadline:
            while send_times and send_times[0] <= now:
                send_times.pop(0)
                _send_query(sock, packet, targets)
            wake_at = min(deadline, send_times[0]) if send_times else deadline
            if not self._receive_one(sock, max(wake_at - now, _MIN_WAIT_SECONDS)):
                return

    def _receive_one(self, sock: socket.socket, wait: float) -> bool:
        """Read one datagram. Return False when the socket stops working."""
        sock.settimeout(wait)
        try:
            data, address = sock.recvfrom(_RECV_BUFFER_BYTES)
        except (TimeoutError, ConnectionRefusedError):
            # A rejected broadcast can surface as ECONNREFUSED on the next read.
            return True
        except OSError as exc:
            logger.debug(f"LSDP receive error: {exc}")
            return False
        source = address[0] if address else ""
        self._parse_packet(data, source)
        return True

    def _build_query_packet(self, class_ids: List[int]) -> bytes:
        """Build an LSDP query packet."""
        header = struct.pack("!B", 6) + LSDP_MAGIC + struct.pack("!B", LSDP_VERSION)
        query = struct.pack("!BBB", 3 + 2 * len(class_ids), MSG_QUERY, len(class_ids))
        return header + query + b"".join(struct.pack("!H", class_id) for class_id in class_ids)

    def _parse_packet(self, data: bytes, source_ip: str) -> None:
        """Parse an LSDP datagram and store accepted announces."""
        if len(data) < 6 or data[1:5] != LSDP_MAGIC or data[5] != LSDP_VERSION:
            return
        offset = data[0]
        while offset + 2 <= len(data):
            msg_length = data[offset]
            # A length below 2 never advances the cursor.
            if msg_length < 2 or offset + msg_length > len(data):
                return
            if data[offset + 1] == MSG_ANNOUNCE:
                self._parse_announce(data[offset:offset + msg_length], source_ip)
            offset += msg_length

    def _parse_announce(self, message: bytes, source_ip: str) -> None:
        """Parse one announce message."""
        reader = _Reader(message, offset=2)
        node = reader.chunk()
        address = reader.chunk()
        record_count = reader.byte()
        if node is None or address is None or record_count is None:
            return
        ip = socket.inet_ntoa(address) if len(address) == 4 else source_ip
        for _ in range(record_count):
            record = _read_record(reader)
            if record is None:
                return
            class_id, txt_records = record
            if class_id not in self._accepted_classes:
                continue
            # Players send the raw MAC. Decoding it as text drops bytes >= 0x80.
            node_id = node.hex()
            self.discovered_devices[(node_id, class_id)] = LSDPDevice(
                node_id=node_id,
                ip=ip,
                class_id=class_id,
                txt_records=txt_records,
                port=_announced_port(txt_records),
            )


class _Reader:
    """Bounds-checked cursor. Reads past the end return None."""

    def __init__(self, data: bytes, offset: int) -> None:
        self._data = data
        self._offset = offset

    def byte(self) -> Optional[int]:
        if self._offset >= len(self._data):
            return None
        value = self._data[self._offset]
        self._offset += 1
        return value

    def take(self, size: int) -> Optional[bytes]:
        end = self._offset + size
        if end > len(self._data):
            return None
        value = self._data[self._offset:end]
        self._offset = end
        return value

    def chunk(self) -> Optional[bytes]:
        """Read a field that is prefixed with its one-byte length."""
        size = self.byte()
        return None if size is None else self.take(size)


def _read_record(reader: _Reader) -> Optional[Tuple[int, Dict[str, str]]]:
    """Read one class/TXT record, or None when it is truncated."""
    raw_class = reader.take(2)
    txt_count = reader.byte()
    if raw_class is None or txt_count is None:
        return None
    txt_records: Dict[str, str] = {}
    for _ in range(txt_count):
        key = reader.chunk()
        value = reader.chunk()
        if key is None or value is None:
            return None
        txt_records[key.decode("utf-8", errors="replace")] = value.decode("utf-8", errors="replace")
    return struct.unpack("!H", raw_class)[0], txt_records


def _announced_port(txt_records: Dict[str, str]) -> Optional[int]:
    """Return the TXT ``port`` when it is a BluOS port. Do not guess a zone port."""
    raw = txt_records.get("port", "")
    if not (raw.isascii() and raw.isdigit()):
        return None
    port = int(raw)
    return port if validate_bluos_port(port) else None


def _open_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError as exc:
                logger.debug(f"LSDP SO_REUSEPORT error: {exc}")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", LSDP_PORT))
    except OSError:
        sock.close()
        raise
    return sock


def _send_query(sock: socket.socket, packet: bytes, targets: List[str]) -> None:
    for target in targets:
        try:
            sock.sendto(packet, (target, LSDP_PORT))
        except OSError as exc:
            logger.debug(f"LSDP query send error to {target}: {exc}")


class _Ifaddrs(ctypes.Structure):
    pass


_Ifaddrs._fields_ = [
    ("ifa_next", ctypes.POINTER(_Ifaddrs)),
    ("ifa_name", ctypes.c_char_p),
    ("ifa_flags", ctypes.c_uint),
    ("ifa_addr", ctypes.c_void_p),
    ("ifa_netmask", ctypes.c_void_p),
    ("ifa_dstaddr", ctypes.c_void_p),
    ("ifa_data", ctypes.c_void_p),
]


def ipv4_broadcast_addresses() -> List[str]:
    """
    Return the IPv4 broadcast address of each interface that is up.

    macOS rejects sends to 255.255.255.255. An empty list means the lookup failed.
    """
    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        return []
    try:
        return _walk_ifaddrs(ctypes.CDLL(libc_name, use_errno=True))
    except (OSError, AttributeError) as exc:
        logger.debug(f"LSDP broadcast lookup failed: {exc}")
        return []


def _walk_ifaddrs(libc: ctypes.CDLL) -> List[str]:
    libc.getifaddrs.argtypes = [ctypes.POINTER(ctypes.POINTER(_Ifaddrs))]
    libc.getifaddrs.restype = ctypes.c_int
    libc.freeifaddrs.argtypes = [ctypes.POINTER(_Ifaddrs)]
    head = ctypes.POINTER(_Ifaddrs)()
    if libc.getifaddrs(ctypes.byref(head)) != 0:
        return []
    found: List[str] = []
    try:
        node = head
        while node:
            ifa = node.contents
            is_broadcast = bool(ifa.ifa_flags & _IFF_UP and ifa.ifa_flags & _IFF_BROADCAST)
            if is_broadcast and _ipv4_at(ifa.ifa_addr):
                broadcast = _ipv4_at(ifa.ifa_dstaddr)
                if broadcast and broadcast not in found:
                    found.append(broadcast)
            node = ifa.ifa_next
    finally:
        libc.freeifaddrs(head)
    return found


def _ipv4_at(sockaddr: Optional[int]) -> Optional[str]:
    """Read a non-loopback IPv4 address from a ``struct sockaddr`` pointer."""
    if not sockaddr:
        return None
    raw = ctypes.string_at(sockaddr, 8)
    family = raw[1] if sys.platform == "darwin" else struct.unpack_from("=H", raw)[0]
    if family != socket.AF_INET:
        return None
    address = socket.inet_ntoa(raw[4:8])
    return None if address.startswith("127.") else address
