"""Pytest configuration and fixtures."""
import pytest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch

from blucommand.constants import BASE_DIR


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    
    # Create cache subdirectory
    cache_dir = os.path.join(temp_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    # Patch BASE_DIR for tests
    with patch('blucommand.constants.BASE_DIR', temp_dir):
        yield temp_dir
    
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.get = Mock(return_value="default_value")
    config.data = {
        'BLUOS_SERVICE': '_musc._tcp',
        'DISCOVERY_TIMEOUT': '5',
        'CACHE_TTL': '300',
        'DEFAULT_SAFE_VOL': '14',
        'UNIFI_ENABLED': 'false'
    }
    return config


@pytest.fixture
def sample_config_file(temp_config_dir):
    """Create a sample config file."""
    config_file = os.path.join(temp_config_dir, "config.json")
    config_data = {
        "BLUOS_SERVICE": "_musc._tcp",
        "DISCOVERY_TIMEOUT": "5",
        "CACHE_TTL": "300",
        "DEFAULT_SAFE_VOL": "14",
        "UNIFI_ENABLED": "false",
        "UNIFI_CONTROLLER": "",
        "UNIFI_API_KEY": "",
        "UNIFI_SITE": "default"
    }
    
    with open(config_file, 'w') as f:
        json.dump(config_data, f)
    
    return config_file


@pytest.fixture
def sample_cache_file(temp_config_dir):
    """Create a sample cache file."""
    cache_file = os.path.join(temp_config_dir, "cache", "discovery.json")
    cache_data = {
        'ts': 1000000.0,
        'ips': ['192.168.1.1', '192.168.1.2']
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)
    
    return cache_file

