#!/usr/bin/env python3
"""
Configuration management for Blucommand.

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
import json
import configparser
import logging
from typing import Any, Optional

from constants import CONFIG_FILE, CONFIG_FILE_JSON, DEFAULT_CONFIG_CONTENT
from validators import validate_config_value
from keychain import get_api_key

logger = logging.getLogger("blucommand")

# Secret config keys must not be returned by Config.get(); use dedicated accessors.
_SECRET_CONFIG_KEYS = frozenset({"UNIFI_API_KEY"})


class Config:
    """Manages configuration loading and access."""
    
    def __init__(self):
        self.data: dict[str, str] = {}
        self._load()
    
    def _load(self) -> None:
        """
        Loads configuration from JSON (preferred) or INI format.
        """
        # Try JSON first, then fall back to INI
        config_file = CONFIG_FILE_JSON if os.path.exists(CONFIG_FILE_JSON) else CONFIG_FILE
        
        if not os.path.exists(config_file):
            try:
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                # Create default JSON config
                default_config = {
                    "BLUOS_SERVICE": "_musc._tcp",
                    "DISCOVERY_METHOD": "mdns",
                    "DISCOVERY_TIMEOUT": "5",
                    "CACHE_TTL": "300",
                    "DEFAULT_SAFE_VOL": "14",
                    "UNIFI_ENABLED": "false",
                    "UNIFI_CONTROLLER": "",
                    "UNIFI_API_KEY": "",
                    "UNIFI_SITE": "default"
                }
                with open(CONFIG_FILE_JSON, "w") as f:
                    json.dump(default_config, f, indent=2)
                # Secure the config file (owner read/write only, no group/other access)
                os.chmod(CONFIG_FILE_JSON, 0o600)
                config_file = CONFIG_FILE_JSON
            except OSError as e:
                logger.error(f"Failed to create default config: {e}")
                return
        
        # Load JSON config
        if config_file.endswith('.json'):
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)
                # Validate config values
                validated_data = {}
                for k, v in config_data.items():
                    validated = validate_config_value(k, str(v))
                    if validated is not None:
                        validated_data[k.upper()] = validated
                    else:
                        logger.warning(f"Invalid config value for {k}: {v}, using default")
                self.data = validated_data
                return
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"JSON Configuration Parse Error: {e}")
                return
        
        # Fall back to INI format
        parser = configparser.ConfigParser()
        try:
            with open(config_file, "r") as f:
                file_content = f.read()
            # Inject dummy section for parsing dotfiles
            parser.read_string(f"[root]\n{file_content}")
            
            if "root" in parser:
                self.data = {
                    k.upper(): v.strip('"').strip("'") 
                    for k, v in parser["root"].items()
                }
        except (configparser.Error, OSError) as e:
            logger.error(f"Configuration Parse Error: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a non-secret configuration value by key.

        Secrets such as UNIFI_API_KEY are never returned here — use
        get_unifi_api_key() instead. Keeping secrets out of this method
        prevents them from being taint-tracked into ordinary log/print sinks.
        """
        key_upper = key.upper()
        if key_upper in _SECRET_CONFIG_KEYS:
            return default
        return self.data.get(key_upper, default)

    def get_unifi_api_key(self) -> Optional[str]:
        """
        Return the UniFi API key from macOS Keychain, falling back to config.

        Callers must not log or print the returned value.
        """
        keychain_key = get_api_key()
        if keychain_key:
            return keychain_key
        file_key = self.data.get("UNIFI_API_KEY")
        if file_key:
            return file_key
        return None

