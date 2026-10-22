#!/usr/bin/env python3
"""
Smoke Test for Blucommand
====================================
Quick validation that all commands execute without crashing.
Uses mocked devices to avoid requiring actual hardware.

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
import sys
import os
from unittest.mock import patch, MagicMock, Mock
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controller import BluOSController
from cli import BluOSCLI
from models import PlayerStatus


class SmokeTest:
    """Smoke test runner for all Blucommand commands."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test(self, name: str, func) -> None:
        """Run a test and track results."""
        try:
            func()
            self.passed += 1
            print(f"✅ {name}")
        except Exception as e:
            self.failed += 1
            self.errors.append((name, str(e)))
            print(f"❌ {name}: {e}")
    
    def setup_mock_controller(self) -> BluOSController:
        """Create a controller with mocked devices."""
        controller = BluOSController()
        controller.ips = ['192.168.1.100', '192.168.1.101']
        
        # Mock device info
        mock_status1 = PlayerStatus(
            ip='192.168.1.100',
            name='Zone One',
            model='Node',
            brand='BluOS',
            status='online',
            state='play',
            volume=50,
            service='Spotify',
            track='Test Track',
            artist='Test Artist',
            album='Test Album'
        )
        
        mock_status2 = PlayerStatus(
            ip='192.168.1.101',
            name='Zone Two',
            model='Pulse',
            brand='BluOS',
            status='online',
            state='pause',
            volume=30,
            service='Library',
            track='Another Track',
            artist='Another Artist',
            album='Another Album'
        )
        
        controller.get_device_info = MagicMock(side_effect=[mock_status1, mock_status2])
        controller.play = MagicMock(return_value=True)
        controller.pause_device = MagicMock(return_value=True)
        controller.stop = MagicMock(return_value=True)
        controller.skip = MagicMock(return_value=True)
        controller.previous = MagicMock(return_value=True)
        controller.get_queue = MagicMock(return_value={'items': [], 'count': 0})
        controller.clear_queue = MagicMock(return_value=True)
        controller.move_queue_item = MagicMock(return_value=True)
        controller.get_inputs = MagicMock(return_value=[{'name': 'Bluetooth', 'type': 'bluetooth', 'selected': True}])
        controller.set_input = MagicMock(return_value=True)
        controller.get_bluetooth_mode = MagicMock(return_value='Automatic')
        controller.set_bluetooth_mode = MagicMock(return_value=True)
        controller.get_presets = MagicMock(return_value=[{'id': '1', 'name': 'Preset 1', 'image': ''}])
        controller.play_preset = MagicMock(return_value=True)
        controller.add_sync_slave = MagicMock(return_value=True)
        controller.remove_sync_slave = MagicMock(return_value=True)
        controller.soft_reboot = MagicMock(return_value=True)
        controller.sync_unifi = MagicMock(return_value='SUCCESS:2')
        
        return controller
    
    def test_discover(self) -> None:
        """Test discover command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        # Capture output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.discover()
            output = fake_out.getvalue()
            assert 'Discovered Devices' in output or len(output) > 0
    
    def test_status_all(self) -> None:
        """Test status command (all devices)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.status(pattern=None, json_mode=False)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_status_filtered(self) -> None:
        """Test status command (filtered)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.status(pattern='One', json_mode=False)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_status_json(self) -> None:
        """Test status command (JSON mode)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.status(pattern=None, json_mode=True)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_list(self) -> None:
        """Test volume command (list volumes)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = None
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_set(self) -> None:
        """Test volume command (set volume)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = '50'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_increment(self) -> None:
        """Test volume command (increment)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = '+10'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_decrement(self) -> None:
        """Test volume command (decrement)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = '-5'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_mute(self) -> None:
        """Test volume command (mute)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = 'mute'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_unmute(self) -> None:
        """Test volume command (unmute)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = 'unmute'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_volume_reset(self) -> None:
        """Test volume command (reset)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.cmd = 'reset'
        args.target = 'all'  # Use 'all' instead of None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.volume(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_play(self) -> None:
        """Test play command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.play(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_pause(self) -> None:
        """Test pause command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.pause(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_stop(self) -> None:
        """Test stop command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.stop(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_skip(self) -> None:
        """Test skip command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.skip(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_previous(self) -> None:
        """Test previous command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.previous(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_toggle(self) -> None:
        """Test toggle command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.toggle(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_queue_show(self) -> None:
        """Test queue command (show)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'show'
        args.target = None
        args.from_index = None
        args.to_index = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.queue(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_queue_clear(self) -> None:
        """Test queue command (clear)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'clear'
        args.target = None
        args.from_index = None
        args.to_index = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.queue(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_queue_move(self) -> None:
        """Test queue command (move)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'move'
        args.target = None
        args.from_index = '1'
        args.to_index = '0'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.queue(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_inputs_list(self) -> None:
        """Test inputs command (list)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.input = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.inputs(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_inputs_set(self) -> None:
        """Test inputs command (set input)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.input = 'Bluetooth'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.inputs(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_bluetooth_get(self) -> None:
        """Test bluetooth command (get mode)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.mode = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.bluetooth(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_bluetooth_set(self) -> None:
        """Test bluetooth command (set mode)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.mode = 'auto'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.bluetooth(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_presets_list(self) -> None:
        """Test presets command (list)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.preset_id = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.presets(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_presets_play(self) -> None:
        """Test presets command (play preset)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        args.preset_id = 1
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.presets(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_sync_create(self) -> None:
        """Test sync command (create)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'create'
        args.master = 'Zone One'
        args.slaves = 'Zone Two'
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.sync(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_sync_break(self) -> None:
        """Test sync command (break)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'break'
        args.master = None
        args.slaves = None
        args.target = 'Zone One'
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.sync(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_sync_list(self) -> None:
        """Test sync command (list)."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.action = 'list'
        args.master = None
        args.slaves = None
        args.target = None
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.sync(args)
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_reboot(self) -> None:
        """Test reboot command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()), \
             patch('builtins.input', return_value='n'):  # Don't actually reboot
            cli.reboot(args)
    
    def test_soft_reboot(self) -> None:
        """Test soft reboot command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        args = Mock()
        args.target = None
        
        with patch('sys.stdout', new=StringIO()), \
             patch('builtins.input', return_value='n'):  # Don't actually reboot
            cli.soft_reboot(args)
    
    def test_diagnose(self) -> None:
        """Test diagnose command."""
        controller = self.setup_mock_controller()
        cli = BluOSCLI(controller)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.diagnose('Zone One')
            output = fake_out.getvalue()
            assert len(output) > 0
    
    def test_help(self) -> None:
        """Test help command."""
        cli = BluOSCLI(None)  # type: ignore
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            cli.print_help()
            output = fake_out.getvalue()
            assert 'Blucommand' in output
            assert 'COMMANDS' in output
    
    def run_all(self) -> None:
        """Run all smoke tests."""
        print("🔥 Running Smoke Tests for Blucommand\n")
        print("=" * 60)
        
        # Discovery and Status
        self.test("discover", self.test_discover)
        self.test("status (all)", self.test_status_all)
        self.test("status (filtered)", self.test_status_filtered)
        self.test("status (JSON)", self.test_status_json)
        
        # Volume Control
        self.test("volume (list)", self.test_volume_list)
        self.test("volume (set)", self.test_volume_set)
        self.test("volume (increment)", self.test_volume_increment)
        self.test("volume (decrement)", self.test_volume_decrement)
        self.test("volume (mute)", self.test_volume_mute)
        self.test("volume (unmute)", self.test_volume_unmute)
        self.test("volume (reset)", self.test_volume_reset)
        
        # Playback Control
        self.test("play", self.test_play)
        self.test("pause", self.test_pause)
        self.test("stop", self.test_stop)
        self.test("skip", self.test_skip)
        self.test("previous", self.test_previous)
        self.test("toggle", self.test_toggle)
        
        # Queue Management
        self.test("queue (show)", self.test_queue_show)
        self.test("queue (clear)", self.test_queue_clear)
        self.test("queue (move)", self.test_queue_move)
        
        # Input Management
        self.test("inputs (list)", self.test_inputs_list)
        self.test("inputs (set)", self.test_inputs_set)
        
        # Bluetooth
        self.test("bluetooth (get)", self.test_bluetooth_get)
        self.test("bluetooth (set)", self.test_bluetooth_set)
        
        # Presets
        self.test("presets (list)", self.test_presets_list)
        self.test("presets (play)", self.test_presets_play)
        
        # Sync Groups
        self.test("sync (create)", self.test_sync_create)
        self.test("sync (break)", self.test_sync_break)
        self.test("sync (list)", self.test_sync_list)
        
        # System
        self.test("reboot", self.test_reboot)
        self.test("soft_reboot", self.test_soft_reboot)
        self.test("diagnose", self.test_diagnose)
        
        # Help
        self.test("help", self.test_help)
        
        # Summary
        print("\n" + "=" * 60)
        print(f"\n✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.errors:
            print("\nErrors:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        
        return self.failed == 0


def main() -> None:
    """Main entry point."""
    tester = SmokeTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

