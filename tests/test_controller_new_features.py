"""
Tests for new controller features (playback, queue, inputs, etc.).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from blucommand.controller import BluOSController
from blucommand.models import PlayerStatus
from blucommand.constants import BLUOS_PORT


class TestPlaybackControls:
    """Test playback control methods."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            ctl.ips = ["192.168.1.100"]
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_play(self, mock_network, controller):
        """Test play command."""
        mock_network.get.return_value = b"OK"
        result = controller.play("192.168.1.100")
        assert result is True
        mock_network.get.assert_called_once()
        call_url = mock_network.get.call_args[0][0]
        assert f"http://192.168.1.100:{BLUOS_PORT}/Play" in call_url
    
    @patch('blucommand.controller.Network')
    def test_pause_device(self, mock_network, controller):
        """Test pause command."""
        mock_network.get.return_value = b"OK"
        result = controller.pause_device("192.168.1.100")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "/Pause" in call_url
    
    @patch('blucommand.controller.Network')
    def test_stop(self, mock_network, controller):
        """Test stop command."""
        mock_network.get.return_value = b"OK"
        result = controller.stop("192.168.1.100")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "/Stop" in call_url
    
    @patch('blucommand.controller.Network')
    def test_skip(self, mock_network, controller):
        """Test skip command."""
        mock_network.get.return_value = b"OK"
        result = controller.skip("192.168.1.100")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "/Skip" in call_url
    
    @patch('blucommand.controller.Network')
    def test_previous(self, mock_network, controller):
        """Test previous command."""
        mock_network.get.return_value = b"OK"
        result = controller.previous("192.168.1.100")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "/Back" in call_url
    
    def test_play_invalid_ip(self, controller):
        """Test play with invalid IP."""
        result = controller.play("invalid")
        assert result is False


class TestQueueManagement:
    """Test queue management methods."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_get_queue(self, mock_network, controller):
        """Test getting queue via v1.7 /Playlist."""
        xml_content = b"""<?xml version="1.0"?>
        <playlist length="1" id="2">
            <song id="0">
                <title>Test Song</title>
                <art>Test Artist</art>
                <alb>Test Album</alb>
                <service>Library</service>
            </song>
        </playlist>"""
        mock_network.get.return_value = xml_content

        result = controller.get_queue("192.168.1.100")
        assert result is not None
        assert result["count"] == 1
        assert result["items"][0]["title"] == "Test Song"
        assert result["items"][0]["artist"] == "Test Artist"
        call_url = mock_network.get.call_args[0][0]
        assert "/Playlist?" in call_url
    
    @patch('blucommand.controller.Network')
    def test_clear_queue(self, mock_network, controller):
        """Test clearing queue via /Clear."""
        mock_network.get.return_value = b"OK"
        result = controller.clear_queue("192.168.1.100")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert call_url.endswith("/Clear")
    
    @patch('blucommand.controller.Network')
    def test_move_queue_item(self, mock_network, controller):
        """Test moving queue item via /Move."""
        mock_network.get.return_value = b"<moved>moved</moved>"
        result = controller.move_queue_item("192.168.1.100", 3, 1)
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "/Move?" in call_url
        assert "old=3" in call_url
        assert "new=1" in call_url


class TestInputManagement:
    """Test input management methods."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_get_inputs(self, mock_network, controller):
        """Test getting inputs from capture settings."""
        xml_content = b"""<?xml version="1.0"?>
        <settings pageId="capture" schemaVersion="32">
          <menuGroup id="capture" displayName="Customize sources">
            <setting id="bluetoothAutoplay" name="bluetoothAutoplay" value="3"></setting>
            <menuGroup id="capture-input0" displayName="Analog Input" icon="/images/capture/ic_analoginput.png"></menuGroup>
            <menuGroup id="capture-input1" displayName="Optical Input" icon="/images/capture/ic_opticalinput.png"></menuGroup>
          </menuGroup>
        </settings>"""
        mock_network.get.return_value = xml_content

        result = controller.get_inputs("192.168.1.100")
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "Analog Input"
        assert result[0]["id"] == "analog-1"
        assert result[1]["id"] == "spdif-1"
        call_urls = [call.args[0] for call in mock_network.get.call_args_list]
        assert any("Settings?id=capture" in url for url in call_urls)
    
    @patch('blucommand.controller.Network')
    def test_set_input(self, mock_network, controller):
        """Test setting input via inputTypeIndex."""
        capture_xml = b"""<?xml version="1.0"?>
        <settings pageId="capture" schemaVersion="32">
          <menuGroup id="capture">
            <menuGroup id="capture-input0" displayName="Analog Input" icon="/images/capture/ic_analoginput.png"></menuGroup>
          </menuGroup>
        </settings>"""
        mock_network.get.side_effect = [
            capture_xml,
            b"<status><service>Library</service></status>",
            b"<state>stream</state>",
        ]
        result = controller.set_input("192.168.1.100", "Analog Input")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "Play?inputType=analog&index=1" in call_url


class TestBluetoothControl:
    """Test Bluetooth mode control."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_get_bluetooth_mode(self, mock_network, controller):
        """Test getting Bluetooth mode from capture settings."""
        xml_content = b"""<?xml version="1.0"?>
        <settings pageId="capture" schemaVersion="32">
          <menuGroup id="capture">
            <setting id="bluetoothAutoplay" name="bluetoothAutoplay" value="1" description="Automatic"></setting>
          </menuGroup>
        </settings>"""
        mock_network.get.return_value = xml_content

        result = controller.get_bluetooth_mode("192.168.1.100")
        assert result == "Automatic"
        call_url = mock_network.get.call_args[0][0]
        assert "Settings?id=capture" in call_url
    
    @patch('blucommand.controller.Network')
    def test_set_bluetooth_mode(self, mock_network, controller):
        """Test setting Bluetooth mode."""
        mock_network.get.return_value = b"OK"
        result = controller.set_bluetooth_mode("192.168.1.100", 1)
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "bluetoothAutoplay=1" in call_url
    
    def test_set_bluetooth_mode_invalid(self, controller):
        """Test setting invalid Bluetooth mode."""
        result = controller.set_bluetooth_mode("192.168.1.100", 99)
        assert result is False


class TestPresetManagement:
    """Test preset management."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_get_presets(self, mock_network, controller):
        """Test getting presets."""
        xml_content = b"""<?xml version="1.0"?>
        <presets>
            <preset id="1">
                <name>Preset 1</name>
            </preset>
        </presets>"""
        mock_network.get.return_value = xml_content
        
        with patch.object(controller, '_safe_parse_xml') as mock_parse:
            mock_root = MagicMock()
            mock_preset = MagicMock()
            mock_preset.get.return_value = '1'
            mock_preset.findtext.return_value = 'Preset 1'
            mock_root.findall.return_value = [mock_preset]
            mock_parse.return_value = mock_root
            
            result = controller.get_presets("192.168.1.100")
            assert result is not None
            assert len(result) == 1
    
    @patch('blucommand.controller.Network')
    def test_play_preset(self, mock_network, controller):
        """Test playing preset."""
        mock_network.get.return_value = b"OK"
        result = controller.play_preset("192.168.1.100", 1)
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "Preset?id=1" in call_url


class TestSyncGroups:
    """Test sync group management."""
    
    @pytest.fixture
    def controller(self):
        """Create controller instance."""
        with patch('blucommand.controller.Config'):
            ctl = BluOSController()
            return ctl
    
    @patch('blucommand.controller.Network')
    def test_add_sync_slave(self, mock_network, controller):
        """Test adding sync slave."""
        mock_network.get.return_value = (
            b'<addSlave><slave id="192.168.1.101" port="11000"/></addSlave>'
        )
        result = controller.add_sync_slave("192.168.1.100", "192.168.1.101")
        assert result is True
        call_url = mock_network.get.call_args[0][0]
        assert "AddSlave?slave=" in call_url
        assert "port=11000" in call_url
    
    @patch('blucommand.controller.Network')
    def test_remove_sync_slave(self, mock_network, controller):
        """Test removing sync slave."""
        # RemoveSlave response + SyncStatus verify (no master)
        mock_network.get.side_effect = [
            b"<SyncStatus id='192.168.1.100:11000'/>",
            b"<SyncStatus id='192.168.1.101:11000'/>",
        ]
        result = controller.remove_sync_slave("192.168.1.100", "192.168.1.101")
        assert result is True
        call_url = mock_network.get.call_args_list[0].args[0]
        assert "RemoveSlave?slave=" in call_url
        assert "port=11000" in call_url

    @patch('blucommand.controller.Network')
    def test_remove_sync_slave_rejects_error_xml(self, mock_network, controller):
        """BluOS <error> bodies must not count as a successful break."""
        err = b"<error>no slave available as new master</error>"
        # master remove+legacy fail; slave remove returns error twice; no donors
        mock_network.get.side_effect = [None, None, err, err]
        controller.ips = []
        result = controller.remove_sync_slave(
            "192.168.1.32:11000", "192.168.1.31:11000"
        )
        assert result is False

    @patch('blucommand.controller.Network')
    def test_remove_sync_slave_reparents_orphan(self, mock_network, controller):
        """Orphaned reconnecting slave is cleared via a live donor primary."""
        controller.ips = ["192.168.1.30:11000", "192.168.1.31:11000"]
        add_ok = b'<addSlave><slave id="192.168.1.31" port="11000"/></addSlave>'
        remove_ok = b"<SyncStatus id='192.168.1.30:11000'/>"
        standalone = b"<SyncStatus id='192.168.1.31:11000' name='Player D'/>"
        mock_network.get.side_effect = [
            None,  # RemoveSlave on dead master
            None,  # legacy on master
            b"<error>no slave available as new master</error>",  # slave self
            None,  # legacy on slave
            add_ok,  # AddSlave to donor
            remove_ok,  # RemoveSlave on donor
            standalone,  # verify ungrouped
        ]
        result = controller.remove_sync_slave(
            "192.168.1.32:11000", "192.168.1.31:11000"
        )
        assert result is True
        urls = [c.args[0] for c in mock_network.get.call_args_list]
        assert any("192.168.1.30:11000/AddSlave" in u for u in urls)
        assert any("192.168.1.30:11000/RemoveSlave" in u for u in urls)

    @patch('blucommand.controller.Network')
    def test_player_is_ungrouped_states(self, mock_network, controller):
        """Ungrouped check distinguishes standalone, grouped, and unreachable."""
        mock_network.get.return_value = b"<SyncStatus name='x'/>"
        assert controller._player_is_ungrouped("192.168.1.31:11000") is True

        mock_network.get.return_value = (
            b"<SyncStatus><master>192.168.1.32</master></SyncStatus>"
        )
        assert controller._player_is_ungrouped("192.168.1.31:11000") is False

        mock_network.get.return_value = None
        assert controller._player_is_ungrouped("192.168.1.31:11000") is None

    @patch('blucommand.controller.Network')
    def test_remove_sync_slave_unreachable_not_success(self, mock_network, controller):
        """RemoveSlave HTTP body is not enough if the slave cannot be verified."""
        controller.ips = []
        # Master RemoveSlave returns XML, but every SyncStatus verify is down.
        mock_network.get.side_effect = [
            b"<SyncStatus id='master'/>",
            *[None] * 8,  # verify polls + legacy/slave attempts
        ]
        with patch.object(controller, '_wait_until_ungrouped', return_value=False):
            with patch.object(controller, '_ungroup_via_reparent', return_value=False):
                result = controller.remove_sync_slave(
                    "192.168.1.32:11000", "192.168.1.31:11000"
                )
        assert result is False

