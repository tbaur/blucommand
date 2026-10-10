"""
Tests for CLI command implementations.
"""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from argparse import Namespace

from cli import BluOSCLI
from controller import BluOSController
from models import PlayerStatus


class TestCLICommands:
    """Test CLI command implementations."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('controller.Config'):
            ctl = BluOSController()
            ctl.ips = ["192.168.1.100", "192.168.1.101"]
            return ctl
    
    @pytest.fixture
    def cli(self, controller):
        """Create CLI instance."""
        return BluOSCLI(controller)
    
    @pytest.fixture
    def mock_devices(self):
        """Create mock device statuses."""
        return [
            PlayerStatus(ip="192.168.1.100", name="Zone One", volume=50, state="play"),
            PlayerStatus(ip="192.168.1.101", name="Player A", volume=30, state="pause"),
        ]
    
    def test_discover(self, cli):
        """Test discover command."""
        cli.ctl.ips = ['192.168.1.100']
        mock_future = MagicMock()
        mock_future.result.return_value = PlayerStatus(ip="192.168.1.100", name="Test Speaker")
        
        # Mock as_completed to return the future immediately
        from concurrent.futures import as_completed
        with patch('cli.as_completed', return_value=[mock_future]):
            with patch('cli.ThreadPoolExecutor') as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor.__enter__ = MagicMock(return_value=mock_executor)
                mock_executor.__exit__ = MagicMock(return_value=False)
                mock_executor.submit.return_value = mock_future
                mock_executor_class.return_value = mock_executor
                
                with patch('builtins.print'):
                    cli.discover()
    
    def test_status_all(self, cli, mock_devices):
        """Test status command for all devices."""
        from concurrent.futures import as_completed
        cli.ctl.ips = ['192.168.1.100', '192.168.1.101']
        mock_future1 = MagicMock()
        mock_future1.result.return_value = mock_devices[0]
        mock_future2 = MagicMock()
        mock_future2.result.return_value = mock_devices[1]
        
        with patch('cli.as_completed', return_value=[mock_future1, mock_future2]):
            with patch('cli.ThreadPoolExecutor') as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor.__enter__ = MagicMock(return_value=mock_executor)
                mock_executor.__exit__ = MagicMock(return_value=False)
                mock_executor.submit.side_effect = [mock_future1, mock_future2]
                mock_executor_class.return_value = mock_executor
                
                with patch.object(cli.ctl, 'sync_unifi', return_value="SUCCESS:2"):
                    with patch('builtins.print'):
                        cli.status(pattern=None, json_mode=False)
    
    def test_status_json(self, cli, mock_devices):
        """Test status command with JSON output."""
        from concurrent.futures import as_completed
        cli.ctl.ips = ['192.168.1.100']
        mock_future = MagicMock()
        mock_future.result.return_value = mock_devices[0]
        
        with patch('cli.as_completed', return_value=[mock_future]):
            with patch('cli.ThreadPoolExecutor') as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor.__enter__ = MagicMock(return_value=mock_executor)
                mock_executor.__exit__ = MagicMock(return_value=False)
                mock_executor.submit.return_value = mock_future
                mock_executor_class.return_value = mock_executor
                
                with patch.object(cli.ctl, 'sync_unifi', return_value="SUCCESS:1"):
                    with patch('builtins.print'):
                        cli.status(pattern=None, json_mode=True)
    
    def test_status_pattern(self, cli, mock_devices):
        """Test status command with pattern filter."""
        from concurrent.futures import as_completed
        cli.ctl.ips = ['192.168.1.100', '192.168.1.101']
        mock_future1 = MagicMock()
        mock_future1.result.return_value = mock_devices[0]
        mock_future2 = MagicMock()
        mock_future2.result.return_value = mock_devices[1]
        
        with patch('cli.as_completed', return_value=[mock_future1, mock_future2]):
            with patch('cli.ThreadPoolExecutor') as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor.__enter__ = MagicMock(return_value=mock_executor)
                mock_executor.__exit__ = MagicMock(return_value=False)
                mock_executor.submit.side_effect = [mock_future1, mock_future2]
                mock_executor_class.return_value = mock_executor
                
                with patch.object(cli.ctl, 'sync_unifi', return_value="SUCCESS:2"):
                    with patch('builtins.print'):
                        cli.status(pattern="One", json_mode=False)
    
    def test_volume_list(self, cli, mock_devices):
        """Test volume command listing volumes."""
        args = Namespace(cmd=None, target='all')
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('builtins.print'):
                cli.volume(args)
    
    def test_volume_set(self, cli, mock_devices):
        """Test volume command setting volume."""
        args = Namespace(cmd='25', target='all')
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('cli.Network.get', return_value=b"OK"):
                with patch('builtins.print'):
                    cli.volume(args)
    
    def test_volume_increment(self, cli, mock_devices):
        """Test volume command incrementing."""
        args = Namespace(cmd='+5', target='all')
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('cli.Network.get', return_value=b"OK"):
                with patch('builtins.print'):
                    cli.volume(args)
    
    def test_volume_mute(self, cli, mock_devices):
        """Test volume command muting."""
        args = Namespace(cmd='mute', target='all')
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('cli.Network.get', return_value=b"OK"):
                with patch('builtins.print'):
                    cli.volume(args)
    
    def test_pause(self, cli, mock_devices):
        """Test pause command."""
        args = Namespace(target=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('cli.Network.get', return_value=b"OK"):
                with patch('builtins.print'):
                    cli.pause(args)
    
    @patch('builtins.input', return_value='y')
    def test_reboot_all(self, mock_input, cli, mock_devices):
        """Test reboot command."""
        args = Namespace(target=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch('cli.Network.post', return_value=b"OK"):
                with patch('builtins.print'):
                    cli.reboot(args)
    
    @patch('builtins.input', return_value='n')
    def test_reboot_cancelled(self, mock_input, cli, mock_devices):
        """Test reboot command cancellation."""
        args = Namespace(target=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            cli.reboot(args)
            # Should not call Network.post if cancelled
    
    @patch('builtins.input', return_value='y')
    def test_soft_reboot(self, mock_input, cli, mock_devices):
        """Test soft reboot command."""
        args = Namespace(target=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'soft_reboot', return_value=True):
                with patch('builtins.print'):
                    cli.soft_reboot(args)
    
    @patch('cli.subprocess.check_output')
    def test_diagnose(self, mock_arp, cli, mock_devices):
        """Test diagnose command."""
        mock_arp.return_value = "192.168.1.100 aa:bb:cc:dd:ee:ff"
        target = "Zone One"
        
        with patch.object(cli.ctl, 'get_device_info') as mock_info:
            mock_info.return_value = mock_devices[0]
            with patch.object(cli.ctl, 'get_sys_uptime', return_value="1 day"):
                with patch.object(cli.ctl, 'sync_unifi'):
                    with patch.object(cli.ctl, 'unifi_map', {}):
                        with patch('cli.Network.get', return_value=b"<sync/>"):
                            with patch('builtins.print'):
                                cli.diagnose(target)
    
    def test_print_help(self, cli):
        """Test help command."""
        with patch('builtins.print'):
            cli.print_help()
    
    def test_print_status_header(self, cli):
        """Test status header printing."""
        with patch('builtins.print'):
            cli._print_status_header(None, "SUCCESS:5")
            cli._print_status_header("Zone", "SUCCESS:5")
    
    def test_format_connection_string(self, cli):
        """Test connection string formatting."""
        device = PlayerStatus(ip="192.168.1.100", name="Test")
        device.unifi = None
        
        result = cli._format_connection_string(device)
        assert isinstance(result, str)
        
        # Test with UniFi data
        from models import UniFiClient
        device.unifi = UniFiClient(
            mac="aa:bb:cc:dd:ee:ff",
            is_wired=True,
            uplink="Switch1",
            port_info="1",
            down_tot=1000,
            up_tot=2000,
            down_rate=100,
            up_rate=200,
            uptime=3600
        )
        result = cli._format_connection_string(device)
        assert "Switch1" in result or "Ethernet" in result

