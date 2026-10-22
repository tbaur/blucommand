"""
Additional main.py tests for coverage.
"""
import pytest
import sys
from unittest.mock import patch, MagicMock

import blucommand.main as main


class TestMainCoverage:
    """Additional main.py tests for better coverage."""
    
    def test_main_pause(self):
        """Test main with pause command."""
        with patch('sys.argv', ['main.py', 'pause']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'pause'
                    args.target = None
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.pause.assert_called_once()
    
    def test_main_stop(self):
        """Test main with stop command."""
        with patch('sys.argv', ['main.py', 'stop']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'stop'
                    args.target = None
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.stop.assert_called_once()
    
    def test_main_skip(self):
        """Test main with skip command."""
        with patch('sys.argv', ['main.py', 'skip']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'skip'
                    args.target = None
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.skip.assert_called_once()
    
    def test_main_previous(self):
        """Test main with previous command."""
        with patch('sys.argv', ['main.py', 'previous']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'previous'
                    args.target = None
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.previous.assert_called_once()
    
    def test_main_toggle(self):
        """Test main with toggle command."""
        with patch('sys.argv', ['main.py', 'toggle']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'toggle'
                    args.target = None
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.toggle.assert_called_once()
    
    def test_main_queue(self):
        """Test main with queue command."""
        with patch('sys.argv', ['main.py', 'queue']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'queue'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.queue.assert_called_once()
    
    def test_main_inputs(self):
        """Test main with inputs command."""
        with patch('sys.argv', ['main.py', 'inputs']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'inputs'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.inputs.assert_called_once()
    
    def test_main_bluetooth(self):
        """Test main with bluetooth command."""
        with patch('sys.argv', ['main.py', 'bluetooth']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'bluetooth'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.bluetooth.assert_called_once()
    
    def test_main_presets(self):
        """Test main with presets command."""
        with patch('sys.argv', ['main.py', 'presets']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'presets'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.presets.assert_called_once()
    
    def test_main_sync(self):
        """Test main with sync command."""
        with patch('sys.argv', ['main.py', 'sync', 'list']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'sync'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.sync.assert_called_once()
    
    def test_main_reboot_hard(self):
        """Test main with hard reboot command."""
        with patch('sys.argv', ['main.py', 'reboot']):
            with patch('blucommand.main.BluOSController') as mock_controller_class:
                with patch('blucommand.main.BluOSCLI') as mock_cli_class:
                    mock_controller = MagicMock()
                    mock_controller.ips = ['192.168.1.100']
                    mock_controller.discover.return_value = None
                    mock_controller_class.return_value = mock_controller
                    
                    mock_cli = MagicMock()
                    mock_cli_class.return_value = mock_cli
                    
                    args = MagicMock()
                    args.command = 'reboot'
                    args.scan = False
                    
                    with patch('blucommand.main.argparse.ArgumentParser') as mock_parser:
                        mock_parser_instance = MagicMock()
                        mock_parser.return_value = mock_parser_instance
                        mock_parser_instance.parse_args.return_value = args
                        
                        main.main()
                        mock_cli.reboot.assert_called_once()

