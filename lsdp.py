#!/usr/bin/env python3
"""
LSDP (Lenbrook Service Discovery Protocol) implementation.
Uses UDP broadcast on port 11430 for more reliable device discovery.

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
import socket
import struct
import time
import random
import logging
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass

from constants import BLUOS_PORT
from validators import validate_ip, sanitize_ip

logger = logging.getLogger("blucommand")

# LSDP Constants
LSDP_PORT = 11430
LSDP_MAGIC = b"LSDP"
LSDP_VERSION = 1

# Class IDs (from BluOS API v1.7)
CLASS_BLUOS_PLAYER = 0x0001
CLASS_BLUOS_SERVER = 0x0002
CLASS_BLUOS_PLAYER_SECONDARY = 0x0003
CLASS_BLUOS_PLAYER_PAIR_SLAVE = 0x0006
CLASS_BLUOS_HUB = 0x0008
CLASS_ALL = 0xFFFF

# Message Types
MSG_QUERY = 0x51  # 'Q'
MSG_QUERY_UNICAST = 0x52  # 'R'
MSG_ANNOUNCE = 0x41  # 'A'
MSG_DELETE = 0x44  # 'D'


@dataclass
class LSDPDevice:
    """Represents a device discovered via LSDP."""
    node_id: str
    ip: str
    class_id: int
    txt_records: Dict[str, str]


class LSDPDiscovery:
    """LSDP discovery implementation."""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.discovered_devices: Dict[str, LSDPDevice] = {}
    
    def discover(self, class_ids: Optional[List[int]] = None) -> List[str]:
        """
        Discover devices using LSDP.
        
        Args:
            class_ids: List of class IDs to query (None = all BluOS players)
            
        Returns:
            List of discovered IP addresses
        """
        if class_ids is None:
            class_ids = [CLASS_BLUOS_PLAYER, CLASS_BLUOS_PLAYER_SECONDARY, CLASS_BLUOS_HUB]
        
        self.discovered_devices.clear()
        
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.timeout)
            
            # Send initial query packets (7 packets as per spec)
            query_packet = self._build_query_packet(class_ids)
            for i in [0, 1, 2, 3, 5, 7, 10]:
                delay = i + random.uniform(0, 0.25)
                time.sleep(delay)
                try:
                    sock.sendto(query_packet, ('<broadcast>', LSDP_PORT))
                except OSError as e:
                    logger.debug(f"LSDP query send error: {e}")
            
            # Listen for responses
            end_time = time.time() + self.timeout
            while time.time() < end_time:
                try:
                    sock.settimeout(end_time - time.time())
                    data, addr = sock.recvfrom(4096)
                    self._parse_packet(data, addr[0])
                except socket.timeout:
                    break
                except OSError as e:
                    logger.debug(f"LSDP receive error: {e}")
                    break
            
            sock.close()
            
        except Exception as e:
            logger.error(f"LSDP discovery error: {e}")
        
        # Extract and validate IPs
        valid_ips = []
        for device in self.discovered_devices.values():
            sanitized_ip = sanitize_ip(device.ip)
            if sanitized_ip:
                valid_ips.append(sanitized_ip)
        
        return sorted(list(set(valid_ips)))
    
    def _build_query_packet(self, class_ids: List[int]) -> bytes:
        """Build LSDP query packet."""
        # Packet header
        header = struct.pack('!B', 6)  # Header length
        header += LSDP_MAGIC
        header += struct.pack('!B', LSDP_VERSION)
        
        # Query message
        msg_length = 3 + (len(class_ids) * 2)  # Length + Type + Count + classes
        query = struct.pack('!B', msg_length)
        query += struct.pack('!B', MSG_QUERY)
        query += struct.pack('!B', len(class_ids))
        for class_id in class_ids:
            query += struct.pack('!H', class_id)
        
        return header + query
    
    def _parse_packet(self, data: bytes, source_ip: str) -> None:
        """Parse LSDP packet and extract device information."""
        if len(data) < 6:
            return
        
        # Check magic word
        if data[1:5] != LSDP_MAGIC:
            return
        
        # Parse version
        version = data[5]
        if version != LSDP_VERSION:
            logger.debug(f"Unsupported LSDP version: {version}")
            return
        
        # Parse messages (skip header)
        offset = data[0]  # Header length
        while offset < len(data):
            if offset + 1 > len(data):
                break
            
            msg_length = data[offset]
            if offset + msg_length > len(data):
                break
            
            msg_type = data[offset + 1]
            
            if msg_type == MSG_ANNOUNCE:
                self._parse_announce(data[offset:offset + msg_length], source_ip)
            
            offset += msg_length
    
    def _parse_announce(self, data: bytes, source_ip: str) -> None:
        """Parse LSDP announce message."""
        if len(data) < 3:
            return
        
        offset = 2  # Skip length and type
        node_id_len = data[offset]
        offset += 1
        
        if offset + node_id_len > len(data):
            return
        
        node_id = data[offset:offset + node_id_len].decode('utf-8', errors='ignore')
        offset += node_id_len
        
        if offset >= len(data):
            return
        
        addr_len = data[offset]
        offset += 1
        
        if addr_len == 4 and offset + 4 <= len(data):
            # IPv4 address
            ip_bytes = data[offset:offset + 4]
            ip = '.'.join(str(b) for b in ip_bytes)
            offset += 4
        else:
            ip = source_ip  # Fallback to source IP
            offset += addr_len
        
        if offset >= len(data):
            return
        
        count = data[offset]
        offset += 1
        
        # Parse announce records
        for _ in range(count):
            if offset + 2 > len(data):
                break
            
            class_id = struct.unpack('!H', data[offset:offset + 2])[0]
            offset += 2
            
            if offset >= len(data):
                break
            
            txt_count = data[offset]
            offset += 1
            
            txt_records = {}
            for _ in range(txt_count):
                if offset >= len(data):
                    break
                
                key_len = data[offset]
                offset += 1
                if offset + key_len > len(data):
                    break
                key = data[offset:offset + key_len].decode('utf-8', errors='ignore')
                offset += key_len
                
                if offset >= len(data):
                    break
                val_len = data[offset]
                offset += 1
                if offset + val_len > len(data):
                    break
                value = data[offset:offset + val_len].decode('utf-8', errors='ignore')
                offset += val_len
                
                txt_records[key] = value
            
            # Store device
            device_key = f"{node_id}:{class_id}"
            self.discovered_devices[device_key] = LSDPDevice(
                node_id=node_id,
                ip=ip,
                class_id=class_id,
                txt_records=txt_records
            )

