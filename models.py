#!/usr/bin/env python3
"""
Data models for Blucommand.

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
from dataclasses import dataclass, field
from typing import List, Optional

from constants import BLUOS_PORT


@dataclass
class UniFiClient:
    """Immutable representation of network data from UniFi Controller."""
    mac: str = ""
    is_wired: bool = False
    uplink: str = "Unknown"
    port_info: str = ""
    down_tot: int = 0
    up_tot: int = 0
    down_rate: int = 0
    up_rate: int = 0
    uptime: int = 0
    # Where live rates came from: "wifi", "switch-port", or "client" (fallback).
    rate_source: str = ""


@dataclass
class PlayerStatus:
    """Aggregate state of a BluOS Player."""
    ip: str
    name: str = "Unknown"
    model: str = ""
    brand: str = ""
    full_model: str = ""
    status: str = "offline"
    service: str = ""
    volume: int = 0
    db: str = ""             # RSSI
    fw: str = ""
    master: str = ""         # Endpoint (ip or ip:port) of master if slave
    group: str = ""          # Combined group name when this player is primary
    slaves: List[str] = field(default_factory=list)  # Slave endpoints when primary
    battery: Optional[str] = None
    track: str = ""
    artist: str = ""
    album: str = ""
    uptime: str = "N/A"
    unifi: Optional[UniFiClient] = None
    state: str = "stop"  # Added missing state field
    port: int = BLUOS_PORT  # BluOS API port (11010+ for CI secondary zones)

    @property
    def endpoint(self) -> str:
        """Canonical ``ip:port`` used for BluOS API calls."""
        return f"{self.ip}:{self.port}"

