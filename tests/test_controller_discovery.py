"""
Tests for controller discovery methods.
"""
import pytest
import subprocess
from unittest.mock import patch, MagicMock, mock_open

from blucommand.controller import BluOSController
from blucommand.constants import DISCOVERY_MDNS, DISCOVERY_LSDP, DISCOVERY_BOTH, CACHE_FILE


class TestDiscoveryMethods:
    """Test discovery method implementations."""

    @pytest.fixture(autouse=True)
    def _mock_endpoint_verify(self):
        """Avoid real LAN probes during discover() unit tests."""
        with patch(
            'blucommand.controller.Network.get',
            return_value=b'<SyncStatus name="ok"/>',
        ):
            yield

    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            ctl.ips = []
            return ctl

    def test_verify_endpoints_keeps_responders(self, controller):
        """Unreachable endpoints are dropped after discovery."""
        with patch(
            'blucommand.controller.Network.get',
            side_effect=[b'<SyncStatus name="ok"/>', None],
        ):
            result = controller._verify_endpoints(
                ['192.168.1.100:11000', '192.168.1.1:11000']
            )
        assert result == ['192.168.1.100:11000']

    def test_discover_does_not_cache_unverified(self, controller):
        """Failed SyncStatus probes must not poison the discovery cache."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'mdns',
            'DISCOVERY_TIMEOUT': '5',
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(
                controller,
                '_discover_mdns',
                return_value=['192.168.1.1:11000'],
            ):
                with patch('blucommand.controller.Network.get', return_value=None):
                    with patch('blucommand.controller.atomic_write') as mock_write:
                        controller.discover(force_refresh=True)

        assert controller.ips == []
        mock_write.assert_not_called()

    def test_discover_mdns_method(self, controller):
        """Test discovery with mDNS method."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'mdns',
            'DISCOVERY_TIMEOUT': '5'
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(
                controller,
                '_discover_mdns',
                return_value=['192.168.1.100:11000', '192.168.1.100:11010'],
            ) as mock_mdns:
                with patch.object(controller, '_discover_lsdp') as mock_lsdp:
                    controller.discover(force_refresh=True)

                    mock_mdns.assert_called_once()
                    mock_lsdp.assert_not_called()
                    assert controller.ips == [
                        '192.168.1.100:11000',
                        '192.168.1.100:11010',
                    ]

    def test_discover_lsdp_method(self, controller):
        """Test discovery with LSDP method."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'lsdp',
            'DISCOVERY_TIMEOUT': '5'
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(controller, '_discover_mdns') as mock_mdns:
                with patch.object(
                    controller,
                    '_discover_lsdp',
                    return_value=['192.168.1.100'],
                ) as mock_lsdp:
                    controller.discover(force_refresh=True)

                    mock_lsdp.assert_called_once()
                    mock_mdns.assert_not_called()
                    assert controller.ips == ['192.168.1.100:11000']

    def test_discover_both_method(self, controller):
        """Test discovery with both methods."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'both',
            'DISCOVERY_TIMEOUT': '5'
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(
                controller,
                '_discover_mdns',
                return_value=['192.168.1.100:11000'],
            ) as mock_mdns:
                with patch.object(controller, '_discover_lsdp') as mock_lsdp:
                    controller.discover(force_refresh=True)

                    mock_mdns.assert_called_once()
                    # LSDP should not be called if mDNS succeeds
                    mock_lsdp.assert_not_called()

    def test_discover_both_fallback(self, controller):
        """Test discovery with both methods, fallback to LSDP."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'both',
            'DISCOVERY_TIMEOUT': '5'
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(controller, '_discover_mdns', return_value=[]) as mock_mdns:
                with patch.object(
                    controller,
                    '_discover_lsdp',
                    return_value=['192.168.1.100'],
                ) as mock_lsdp:
                    controller.discover(force_refresh=True)

                    mock_mdns.assert_called_once()
                    mock_lsdp.assert_called_once()
                    assert controller.ips == ['192.168.1.100:11000']

    def test_discover_mdns_keeps_srv_ports(self, controller):
        """musc + musp SRV ports become distinct endpoints."""
        def fake_dns_sd(service, timeout):
            if service == '_musp._tcp':
                return "PlayerA._musp._tcp SRV 0 0 11010 speaker.local.\n"
            return "ZoneOne._musc._tcp SRV 0 0 11000 speaker.local.\n"

        with patch.object(controller, '_run_dns_sd', side_effect=fake_dns_sd):
            with patch.object(
                controller,
                '_resolve_hosts',
                return_value={'192.168.1.100'},
            ):
                result = controller._discover_mdns(5)

        assert '192.168.1.100:11000' in result
        assert '192.168.1.100:11010' in result

    @patch('blucommand.controller.subprocess.check_output')
    def test_resolve_hosts(self, mock_check, controller):
        """Test hostname resolution."""
        mock_check.return_value = "ip_address: 192.168.1.100\n"
        hosts = {'speaker.local'}
        result = controller._resolve_hosts(hosts)
        assert '192.168.1.100' in result

    @patch('blucommand.controller.subprocess.check_output')
    def test_resolve_hosts_invalid(self, mock_check, controller):
        """Test hostname resolution with invalid hostname."""
        mock_check.side_effect = subprocess.CalledProcessError(1, 'cmd')
        hosts = {'invalid-host.local'}
        result = controller._resolve_hosts(hosts)
        assert len(result) == 0

    @patch('blucommand.controller.subprocess.run')
    def test_run_dns_sd(self, mock_run, controller):
        """Test dns-sd command execution."""
        mock_run.return_value = None
        mock_file = mock_open(read_data="SRV 0 0 11000 speaker.local.\n")
        with patch('builtins.open', mock_file):
            with patch('os.path.exists', return_value=True):
                with patch('os.remove'):
                    result = controller._run_dns_sd('_musc._tcp', 5)
                    assert isinstance(result, str)

    @patch('blucommand.controller.subprocess.run')
    def test_run_dns_sd_timeout(self, mock_run, controller):
        """Test dns-sd command with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired('dns-sd', 5)
        mock_file = mock_open()
        with patch('builtins.open', mock_file):
            with patch('os.path.exists', return_value=True):
                with patch('os.remove'):
                    result = controller._run_dns_sd('_musc._tcp', 5)
                    assert result == ""

    def test_discover_rejects_loopback(self, controller):
        """Loopback endpoints from discovery are discarded."""
        controller.config.get = lambda key, default=None: {
            'DISCOVERY_METHOD': 'mdns',
            'DISCOVERY_TIMEOUT': '5'
        }.get(key, default)

        with patch.object(controller, '_load_discovery_cache', return_value=False):
            with patch.object(
                controller,
                '_discover_mdns',
                return_value=['127.0.0.1:11000', '192.168.1.100:11000'],
            ):
                controller.discover(force_refresh=True)

        assert '127.0.0.1:11000' not in controller.ips
        assert controller.ips == ['192.168.1.100:11000']
