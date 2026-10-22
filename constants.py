#!/usr/bin/env python3
"""
Shared constants for Blucommand.

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
import os

__version__ = "1.4.3"  # x-release-please-version

# --- PATHS ---
BASE_DIR = os.path.expanduser("~/.config/blucommand")
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
CONFIG_FILE_JSON = os.path.join(BASE_DIR, "config.json")
CACHE_FILE = os.path.join(BASE_DIR, "cache", "discovery.json")
UNIFI_CACHE_FILE = os.path.join(BASE_DIR, "cache", "unifi.json")
LOG_FILE = os.path.join(BASE_DIR, "blucommand.log")

# Ensure cache directory exists with secure permissions
cache_dir = os.path.join(BASE_DIR, "cache")
os.makedirs(cache_dir, exist_ok=True)
# Secure cache directory (owner only access)
try:
    os.chmod(cache_dir, 0o700)
except OSError:
    pass  # Ignore if we can't set permissions

# --- OPERATIONAL CONSTANTS ---
BLUOS_PORT = 11000
# BluOS mDNS: primary players (_musc) + CI secondary zones (_musp)
BLUOS_MDNS_SERVICES = ("_musc._tcp", "_musp._tcp")
DEFAULT_TIMEOUT = 2
MAX_XML_SIZE = 1_048_576  # 1MB Limit
MAX_XML_DEPTH = 20  # Maximum XML nesting depth to prevent bombs
MAX_XML_ELEMENTS = 10_000  # Maximum total XML elements to prevent DoS
MAX_XML_ATTRIBUTES = 100  # Maximum attributes per element
MAX_HOSTNAME_LENGTH = 253  # RFC 1035 max hostname length
MAX_WORKERS_DISCOVERY = 10  # Max workers for discovery operations
MAX_WORKERS_STATUS = 20  # Max workers for status operations
SUBPROCESS_TIMEOUT = 5  # Timeout for subprocess calls
MIN_VOLUME = 0
MAX_VOLUME = 100
MIN_TIMEOUT = 1
MAX_TIMEOUT = 60
MIN_CACHE_TTL = 0
MAX_CACHE_TTL = 3600

# --- RETRY & RATE LIMITING ---
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay in seconds for exponential backoff
MAX_RETRY_DELAY = 10.0  # Maximum delay between retries
RATE_LIMIT_DELAY = 0.1  # Minimum delay between device operations (seconds)
MAX_CONCURRENT_OPERATIONS = 5  # Max concurrent operations per device

# --- ANSI COLOR CODES ---
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
RESET = "\033[0m"
DIM = "\033[2m"

# --- DISCOVERY METHODS ---
DISCOVERY_MDNS = "mdns"
DISCOVERY_LSDP = "lsdp"
DISCOVERY_BOTH = "both"  # Try both, prefer mDNS

# --- DEFAULT CONFIGURATION ---
DEFAULT_CONFIG_CONTENT = """# Blucommand Configuration
BLUOS_SERVICE="_musc._tcp"
DISCOVERY_METHOD=mdns
DISCOVERY_TIMEOUT=5
CACHE_TTL=300
DEFAULT_SAFE_VOL=14
# UniFi Integration
UNIFI_ENABLED=true
UNIFI_CONTROLLER=""
UNIFI_API_KEY=""
UNIFI_SITE="default"
"""

