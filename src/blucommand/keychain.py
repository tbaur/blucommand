#!/usr/bin/env python3
"""
macOS Keychain integration for secure API key storage.

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
import subprocess
import sys
import logging
from typing import Optional

logger = logging.getLogger("blucommand")

# Keychain service and account names
KEYCHAIN_SERVICE = "blucommand"
KEYCHAIN_ACCOUNT = "unifi-api-key"

# Characters that are unsafe in subprocess arguments
_UNSAFE_CHARS = frozenset(';&|`$()<>\n\r ')


def is_macos() -> bool:
    """Check if running on macOS."""
    return sys.platform == "darwin"


def _validate_keychain_params() -> bool:
    """Validate keychain service/account names are safe for subprocess use."""
    for name, label in [(KEYCHAIN_SERVICE, "service"), (KEYCHAIN_ACCOUNT, "account")]:
        if not name or not isinstance(name, str):
            logger.warning(f"Invalid Keychain {label} name")
            return False
        if any(char in name for char in _UNSAFE_CHARS):
            logger.warning(f"Keychain {label} name contains unsafe characters")
            return False
    return True


def get_api_key() -> Optional[str]:
    """
    Retrieve UniFi API key from macOS Keychain.
    
    Returns:
        API key string if found, None otherwise
    """
    if not is_macos():
        logger.debug("Keychain access only available on macOS")
        return None
    
    try:
        if not _validate_keychain_params():
            return None
        
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT,
                "-w"  # Write password to stdout
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            # Security: Explicitly disable shell
            shell=False
        )
        
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        else:
            logger.debug("API key not found in Keychain")
            return None
    except subprocess.TimeoutExpired:
        logger.warning("Keychain access timed out")
        return None
    except FileNotFoundError:
        logger.debug("security command not found (not on macOS?)")
        return None
    except Exception as e:
        logger.debug(f"Keychain access error: {e}")
        return None


def set_api_key(api_key: str) -> bool:
    """
    Store UniFi API key in macOS Keychain.
    
    Args:
        api_key: API key to store
        
    Returns:
        True if successful, False otherwise
    """
    if not is_macos():
        logger.error("Keychain access only available on macOS")
        return False
    
    if not api_key:
        logger.error("Cannot store empty API key")
        return False
    
    try:
        if not _validate_keychain_params():
            return False
        
        # Validate API key doesn't contain null bytes
        if '\x00' in api_key:
            logger.error("API key contains null bytes")
            return False
        
        # First, try to delete existing entry (ignore errors)
        subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            # Security: Explicitly disable shell
            shell=False
        )
        
        # Add new entry
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT,
                "-w", api_key,
                "-U"  # Update if exists
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
            # Security: Explicitly disable shell
            shell=False
        )
        
        if result.returncode == 0:
            logger.info("API key stored in Keychain successfully")
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
            logger.error(f"Failed to store API key in Keychain: {error_msg}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Keychain access timed out")
        return False
    except FileNotFoundError:
        logger.error("security command not found (not on macOS?)")
        return False
    except Exception as e:
        logger.error(f"Keychain storage error: {e}")
        return False


def delete_api_key() -> bool:
    """
    Delete UniFi API key from macOS Keychain.
    
    Returns:
        True if successful or key doesn't exist, False on error
    """
    if not is_macos():
        logger.error("Keychain access only available on macOS")
        return False
    
    try:
        if not _validate_keychain_params():
            return False
        
        result = subprocess.run(
            [
                "security",
                "delete-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
            # Security: Explicitly disable shell
            shell=False
        )
        
        # Return code 44 means item not found, which is fine
        if result.returncode == 0 or result.returncode == 44:
            logger.info("API key removed from Keychain")
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
            logger.error(f"Failed to delete API key from Keychain: {error_msg}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Keychain access timed out")
        return False
    except FileNotFoundError:
        logger.error("security command not found (not on macOS?)")
        return False
    except Exception as e:
        logger.error(f"Keychain deletion error: {e}")
        return False


def has_api_key() -> bool:
    """
    Check if API key exists in Keychain.
    
    Returns:
        True if key exists, False otherwise
    """
    if not is_macos():
        return False
    
    try:
        if not _validate_keychain_params():
            return False
        
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s", KEYCHAIN_SERVICE,
                "-a", KEYCHAIN_ACCOUNT
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            # Security: Explicitly disable shell
            shell=False
        )
        return result.returncode == 0
    except Exception:
        return False

