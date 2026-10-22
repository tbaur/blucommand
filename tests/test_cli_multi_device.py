"""
Tests for CLI multi-device support functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from argparse import Namespace

from blucommand.cli import BluOSCLI
from blucommand.controller import BluOSController
from blucommand.models import PlayerStatus


class TestMultiDeviceSupport:
    """Test multi-device support in CLI commands."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance with multiple devices."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            ctl.ips = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
            return ctl
    
    @pytest.fixture
    def cli(self, controller):
        """Create CLI instance."""
        return BluOSCLI(controller)
    
    @pytest.fixture
    def mock_devices(self):
        """Create mock device statuses."""
        return [
            PlayerStatus(ip="192.168.1.100", name="Zone One"),
            PlayerStatus(ip="192.168.1.101", name="Player A"),
            PlayerStatus(ip="192.168.1.102", name="Zone Two"),
        ]
    
    def test_get_matching_devices_all(self, cli, mock_devices):
        """Test getting all devices when no target specified."""
        with patch.object(cli.ctl, 'get_device_info') as mock_info:
            mock_info.side_effect = mock_devices
            devices = cli._get_matching_devices(None)
            assert len(devices) == 3
            assert all(d.name in ["Zone One", "Player A", "Zone Two"] for d in devices)
    
    def test_get_matching_devices_specific(self, cli, mock_devices):
        """Test getting specific device by exact name."""
        with patch.object(cli.ctl, 'get_device_info') as mock_info:
            mock_info.side_effect = mock_devices
            devices = cli._get_matching_devices("Zone One")
            assert len(devices) == 1
            assert devices[0].name == "Zone One"
    
    def test_get_matching_devices_pattern(self, cli, mock_devices):
        """Test getting devices by pattern match."""
        with patch.object(cli.ctl, 'get_device_info') as mock_info:
            mock_info.side_effect = mock_devices
            devices = cli._get_matching_devices("Zone")
            assert len(devices) == 2
            device_names = [d.name for d in devices]
            assert "Zone One" in device_names
            assert "Zone Two" in device_names
            assert "Player A" not in device_names
    
    def test_get_matching_devices_no_match(self, cli, mock_devices):
        """Test getting devices with no match."""
        with patch.object(cli.ctl, 'get_device_info') as mock_info:
            mock_info.side_effect = mock_devices
            devices = cli._get_matching_devices("Player C")
            assert len(devices) == 0
    
    @patch('blucommand.cli.Network')
    def test_play_all_devices(self, mock_network, cli, mock_devices):
        """Test play command on all devices."""
        mock_network.get.return_value = b"OK"
        args = Namespace(target=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'play', return_value=True) as mock_play:
                cli.play(args)
                assert mock_play.call_count == 3
    
    @patch('blucommand.cli.Network')
    def test_play_specific_device(self, mock_network, cli, mock_devices):
        """Test play command on specific device."""
        mock_network.get.return_value = b"OK"
        args = Namespace(target="Zone One")
        matching = [d for d in mock_devices if d.name == "Zone One"]
        
        with patch.object(cli, '_get_matching_devices', return_value=matching):
            with patch.object(cli.ctl, 'play', return_value=True) as mock_play:
                cli.play(args)
                assert mock_play.call_count == 1
                mock_play.assert_called_with("192.168.1.100:11000")
    
    @patch('blucommand.cli.Network')
    def test_queue_clear_all_devices(self, mock_network, cli, mock_devices):
        """Test queue clear on all devices."""
        args = Namespace(target=None, action='clear', from_index=None, to_index=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'clear_queue', return_value=True) as mock_clear:
                cli.queue(args)
                assert mock_clear.call_count == 3
    
    @patch('blucommand.cli.Network')
    def test_inputs_set_all_devices(self, mock_network, cli, mock_devices):
        """Test setting input on all devices."""
        args = Namespace(target=None, input="Bluetooth")
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'set_input', return_value=True) as mock_set:
                cli.inputs(args)
                assert mock_set.call_count == 3
                # Verify all calls were with "Bluetooth"
                for call in mock_set.call_args_list:
                    assert call[0][1] == "Bluetooth"
    
    @patch('blucommand.cli.Network')
    def test_bluetooth_set_all_devices(self, mock_network, cli, mock_devices):
        """Test setting Bluetooth mode on all devices."""
        args = Namespace(target=None, mode="auto")
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'set_bluetooth_mode', return_value=True) as mock_set:
                cli.bluetooth(args)
                assert mock_set.call_count == 3
                # Verify all calls were with mode 1 (auto)
                for call in mock_set.call_args_list:
                    assert call[0][1] == 1
    
    @patch('blucommand.cli.Network')
    def test_presets_play_all_devices(self, mock_network, cli, mock_devices):
        """Test playing preset on all devices."""
        args = Namespace(target=None, preset_id=1)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'play_preset', return_value=True) as mock_play:
                cli.presets(args)
                assert mock_play.call_count == 3
                # Verify all calls were with preset ID 1
                for call in mock_play.call_args_list:
                    assert call[0][1] == 1
    
    @patch('blucommand.cli.Network')
    def test_reboot_with_target(self, mock_network, cli, mock_devices):
        """Test reboot with device target."""
        matching = [d for d in mock_devices if d.name == "Zone One"]
        args = Namespace(target="Zone One")
        
        with patch.object(cli, '_get_matching_devices', return_value=matching):
            with patch('builtins.input', return_value='y'):
                with patch('blucommand.cli.Network.post', return_value=b"OK") as mock_post:
                    cli.reboot(args)
                    assert mock_post.call_count == 1
    
    def test_queue_show_all_devices(self, cli, mock_devices):
        """Test showing queue for all devices."""
        args = Namespace(target=None, action='show', from_index=None, to_index=None)
        
        queue_data = {
            'items': [
                {'title': 'Song 1', 'artist': 'Artist 1', 'album': 'Album 1'}
            ],
            'count': 1
        }
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'get_queue', return_value=queue_data):
                # Should not raise exception
                cli.queue(args)
    
    def test_inputs_list_all_devices(self, cli, mock_devices):
        """Test listing inputs for all devices."""
        args = Namespace(target=None, input=None)
        
        inputs_data = [
            {'name': 'Bluetooth', 'type': 'bluetooth', 'selected': True},
            {'name': 'Optical', 'type': 'optical', 'selected': False}
        ]
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'get_inputs', return_value=inputs_data):
                # Should not raise exception
                cli.inputs(args)
    
    def test_bluetooth_list_all_devices(self, cli, mock_devices):
        """Test listing Bluetooth mode for all devices."""
        args = Namespace(target=None, mode=None)
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'get_bluetooth_mode', return_value="Automatic"):
                # Should not raise exception
                cli.bluetooth(args)
    
    def test_presets_list_all_devices(self, cli, mock_devices):
        """Test listing presets for all devices."""
        args = Namespace(target=None, preset_id=None)
        
        presets_data = [
            {'id': '1', 'name': 'Preset 1', 'image': ''},
            {'id': '2', 'name': 'Preset 2', 'image': ''}
        ]
        
        with patch.object(cli, '_get_matching_devices', return_value=mock_devices):
            with patch.object(cli.ctl, 'get_presets', return_value=presets_data):
                # Should not raise exception
                cli.presets(args)

    def test_queue_move_passes_indexes_and_name(self, cli, mock_devices):
        """``queue move 3 1 "Zone One"`` is from, to, then the player name."""
        args = Namespace(action="move", parts=["3", "1", "Zone One"])
        matching = [d for d in mock_devices if d.name == "Zone One"]

        with patch.object(cli, "_get_matching_devices", return_value=matching) as match:
            with patch.object(cli.ctl, "move_queue_item", return_value=True) as move:
                cli.queue(args)

        match.assert_called_once_with("Zone One")
        move.assert_called_once()
        assert move.call_args.args[1:] == (3, 1)

    def test_queue_move_rejects_non_numeric_indexes(self, cli):
        args = Namespace(action="move", parts=["a", "1"])
        with patch.object(cli, "_get_matching_devices") as match:
            cli.queue(args)
        match.assert_not_called()

