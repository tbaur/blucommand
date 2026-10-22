#!/usr/bin/env python3
"""
Input validation and sanitization utilities.

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
import re
import ipaddress
import logging
from typing import Optional

logger = logging.getLogger("blucommand")


def validate_ip(ip: str) -> bool:
    """
    Validate IPv4 address format and range with comprehensive security checks.
    
    Args:
        ip: IP address string to validate
        
    Returns:
        True if valid IPv4 address, False otherwise
        
    Security Features:
    - Type checking (prevents injection)
    - Format validation (prevents malformed input)
    - Range validation (rejects private/reserved addresses)
    - Length limits (prevents buffer overflow attempts)
    """
    # Type and basic format validation
    if not ip or not isinstance(ip, str):
        return False
    
    # Length check (IPv4 addresses are max 15 characters: "255.255.255.255")
    if len(ip) > 15 or len(ip.strip()) == 0:
        return False
    
    # Reject strings with null bytes or other dangerous characters
    if '\x00' in ip or '\n' in ip or '\r' in ip:
        return False
    
    try:
        addr = ipaddress.IPv4Address(ip)
        # Reject 0.0.0.0 (unspecified), loopback, multicast, reserved, and link-local addresses
        if ip == "0.0.0.0":
            return False
        # Reject loopback, multicast, reserved, and link-local addresses for device discovery
        if addr.is_loopback or addr.is_multicast or addr.is_reserved or addr.is_link_local:
            return False
        return True
    except (ValueError, ipaddress.AddressValueError):
        return False
    except Exception:
        # Catch any other unexpected errors
        return False


def validate_hostname(hostname: str) -> bool:
    """
    Validate hostname format with comprehensive security checks.
    
    Args:
        hostname: Hostname string to validate
        
    Returns:
        True if valid hostname format, False otherwise
        
    Security Features:
    - Type checking (prevents injection)
    - Length validation (RFC 1035 compliant)
    - Format validation (prevents shell injection)
    - Character validation (rejects dangerous characters)
    """
    from constants import MAX_HOSTNAME_LENGTH
    
    # Type and basic validation
    if not hostname or not isinstance(hostname, str):
        return False
    
    # Length check (RFC 1035: max 253 characters)
    if len(hostname) > MAX_HOSTNAME_LENGTH or len(hostname.strip()) == 0:
        return False
    
    # Reject strings with null bytes, newlines, or other dangerous characters
    if '\x00' in hostname or '\n' in hostname or '\r' in hostname:
        return False
    
    # Reject shell metacharacters that could be used for injection
    shell_metachars = [';', '&', '|', '`', '$', '(', ')', '<', '>', ' ', '\t']
    if any(char in hostname for char in shell_metachars):
        return False
    
    # RFC 1035 compliant hostname validation (alphanumeric, dots, hyphens)
    # Each label: 1-63 chars, alphanumeric or hyphen, can't start/end with hyphen
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, hostname))


def sanitize_ip(ip: str) -> Optional[str]:
    """
    Sanitize and validate IP address.
    
    Args:
        ip: IP address string to sanitize
        
    Returns:
        Validated IP address string or None if invalid
    """
    if not ip:
        return None
    ip = ip.strip()
    if validate_ip(ip):
        return ip
    return None


def validate_bluos_port(port: int) -> bool:
    """Return True if port is a plausible BluOS API port."""
    return isinstance(port, int) and 1024 <= port <= 65535


def parse_endpoint(value: str, default_port: Optional[int] = None) -> tuple[Optional[str], int]:
    """
    Parse ``ip`` or ``ip:port`` into ``(ip, port)``.

    Returns ``(None, default_port)`` when the IP is invalid.
    """
    from constants import BLUOS_PORT

    if default_port is None:
        default_port = BLUOS_PORT

    if not value or not isinstance(value, str):
        return None, default_port

    value = value.strip()
    if not value:
        return None, default_port

    # IPv4 endpoint: address[:port]
    if value.count(":") == 1:
        host, port_str = value.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return None, default_port
        sanitized = sanitize_ip(host)
        if not sanitized or not validate_bluos_port(port):
            return None, default_port
        return sanitized, port

    sanitized = sanitize_ip(value)
    if not sanitized:
        return None, default_port
    return sanitized, default_port


def format_endpoint(ip: str, port: Optional[int] = None) -> str:
    """Return canonical ``ip:port`` endpoint string."""
    from constants import BLUOS_PORT

    if port is None:
        port = BLUOS_PORT
    return f"{ip}:{port}"


def sanitize_endpoint(value: str, default_port: Optional[int] = None) -> Optional[str]:
    """
    Sanitize an endpoint to canonical ``ip:port`` form.

    Accepts bare IP (assumes default BluOS port) or ``ip:port``.
    """
    ip, port = parse_endpoint(value, default_port=default_port)
    if not ip:
        return None
    return format_endpoint(ip, port)


def validate_volume(volume: int) -> int:
    """
    Validate and clamp volume to valid range with type checking.
    
    Args:
        volume: Volume level to validate (int or convertible to int)
        
    Returns:
        Volume clamped to valid range (0-100)
        
    Security Features:
    - Type validation (prevents type confusion attacks)
    - Range validation (prevents out-of-bounds values)
    - Safe conversion (handles edge cases)
    """
    from constants import MIN_VOLUME, MAX_VOLUME
    
    # Type checking
    if not isinstance(volume, (int, float, str)):
        logger.warning(f"Invalid volume type: {type(volume)}")
        return MIN_VOLUME
    
    try:
        # Safe conversion with bounds checking
        vol_int = int(float(volume))  # Handle float strings like "25.5"
        
        # Clamp to valid range
        return max(MIN_VOLUME, min(MAX_VOLUME, vol_int))
    except (ValueError, TypeError, OverflowError):
        logger.warning(f"Invalid volume value: {volume}")
        return MIN_VOLUME


def validate_timeout(timeout: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """
    Validate and clamp timeout to valid range.
    
    Args:
        timeout: Timeout value in seconds
        min_val: Minimum allowed timeout (uses constant if None)
        max_val: Maximum allowed timeout (uses constant if None)
        
    Returns:
        Timeout clamped to valid range
    """
    from constants import MIN_TIMEOUT, MAX_TIMEOUT
    min_val = min_val if min_val is not None else MIN_TIMEOUT
    max_val = max_val if max_val is not None else MAX_TIMEOUT
    return max(min_val, min(max_val, int(timeout)))


def validate_config_value(key: str, value: str) -> Optional[str]:
    """
    Validate configuration value based on key.
    
    Args:
        key: Configuration key
        value: Configuration value to validate
        
    Returns:
        Validated value or None if invalid
    """
    key_upper = key.upper()
    
    if key_upper == 'DISCOVERY_TIMEOUT':
        try:
            timeout_val = int(value)
            if timeout_val < 1:
                return None  # Reject values less than 1
            timeout = validate_timeout(timeout_val, min_val=1, max_val=60)
            return str(timeout)
        except (ValueError, TypeError):
            logger.warning(f"Invalid DISCOVERY_TIMEOUT: {value}, using default")
            return None
    
    elif key_upper == 'CACHE_TTL':
        try:
            from constants import MIN_CACHE_TTL, MAX_CACHE_TTL
            ttl = max(MIN_CACHE_TTL, min(MAX_CACHE_TTL, int(value)))
            return str(ttl)
        except (ValueError, TypeError):
            logger.warning(f"Invalid CACHE_TTL: {value}, using default")
            return None
    
    elif key_upper == 'DEFAULT_SAFE_VOL':
        try:
            vol = validate_volume(int(value))
            return str(vol)
        except (ValueError, TypeError):
            logger.warning(f"Invalid DEFAULT_SAFE_VOL: {value}, using default")
            return None
    
    elif key_upper == 'UNIFI_ENABLED':
        if value.lower() in ('true', 'false', '1', '0', 'yes', 'no'):
            return 'true' if value.lower() in ('true', '1', 'yes') else 'false'
        return None
    
    elif key_upper == 'DISCOVERY_METHOD':
        if value.lower() in ('mdns', 'lsdp', 'both'):
            return value.lower()
        logger.warning(f"Invalid DISCOVERY_METHOD: {value}, using 'mdns'")
        return 'mdns'
    
    return value  # Pass through other values

