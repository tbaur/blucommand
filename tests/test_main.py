"""
Tests for main.py entry point.
"""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

import blucommand.main as main


class TestMain:
    """Test main entry point."""
    
    def test_main_help(self):
        """Test main with help flag."""
        with patch('sys.argv', ['main.py', '--help']):
            with patch('sys.exit') as mock_exit:
                with patch('blucommand.main.BluOSCLI') as mock_cli:
                    mock_cli.return_value.print_help.return_value = None
                    try:
                        main.main()
                    except SystemExit:
                        pass
                    # Help may exit with 0 or 2 depending on argparse
                    assert mock_exit.called
    
    def test_main_no_args(self):
        """Test main with no arguments."""
        with patch('sys.argv', ['main.py']):
            with patch('sys.exit') as mock_exit:
                with patch('blucommand.main.BluOSCLI') as mock_cli:
                    mock_cli.return_value.print_help.return_value = None
                    try:
                        main.main()
                    except SystemExit:
                        pass
                    # Should exit after showing help
                    assert mock_exit.called
    
    @patch('blucommand.main.BluOSController')
    @patch('blucommand.main.BluOSCLI')
    def test_main_discover(self, mock_cli_class, mock_ctl_class):
        """Test main with discover command."""
        mock_ctl = MagicMock()
        mock_ctl_class.return_value = mock_ctl
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        
        args = MagicMock()
        args.command = 'discover'
        args.scan = False
        
        with patch('sys.argv', ['main.py', 'discover']):
            with patch('blucommand.main.argparse.ArgumentParser.parse_args', return_value=args):
                main.main()
                mock_ctl.discover.assert_called_once()
                mock_cli.discover.assert_called_once()
    
    @patch('blucommand.main.BluOSController')
    @patch('blucommand.main.BluOSCLI')
    def test_main_status(self, mock_cli_class, mock_ctl_class):
        """Test main with status command."""
        mock_ctl = MagicMock()
        mock_ctl_class.return_value = mock_ctl
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        
        args = MagicMock()
        args.command = 'status'
        args.pattern = None
        args.json = False
        args.scan = False
        
        with patch('sys.argv', ['main.py', 'status']):
            with patch('blucommand.main.argparse.ArgumentParser.parse_args', return_value=args):
                main.main()
                mock_cli.status.assert_called_once_with(
                    pattern=None, json_mode=False, force_refresh=False
                )
    
    @patch('blucommand.main.BluOSController')
    @patch('blucommand.main.BluOSCLI')
    def test_main_status_with_scan(self, mock_cli_class, mock_ctl_class):
        """Test main with status --scan."""
        mock_ctl = MagicMock()
        mock_ctl_class.return_value = mock_ctl
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        
        args = MagicMock()
        args.command = 'status'
        args.pattern = None
        args.json = False
        args.scan = True
        
        with patch('sys.argv', ['main.py', 'status', '--scan']):
            with patch('blucommand.main.argparse.ArgumentParser.parse_args', return_value=args):
                main.main()
                mock_ctl.discover.assert_called_once_with(force_refresh=True)
                mock_cli.status.assert_called_once_with(
                    pattern=None, json_mode=False, force_refresh=True
                )
    
    @patch('blucommand.main.BluOSController')
    @patch('blucommand.main.BluOSCLI')
    def test_main_volume(self, mock_cli_class, mock_ctl_class):
        """Test main with volume command."""
        mock_ctl = MagicMock()
        mock_ctl_class.return_value = mock_ctl
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        
        args = MagicMock()
        args.command = 'volume'
        args.cmd = '25'
        args.target = 'all'
        args.scan = False
        
        with patch('sys.argv', ['main.py', 'volume', '25']):
            with patch('blucommand.main.argparse.ArgumentParser.parse_args', return_value=args):
                main.main()
                mock_cli.volume.assert_called_once()
    
    @patch('blucommand.main.BluOSController')
    @patch('blucommand.main.BluOSCLI')
    def test_main_play(self, mock_cli_class, mock_ctl_class):
        """Test main with play command."""
        mock_ctl = MagicMock()
        mock_ctl_class.return_value = mock_ctl
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        
        args = MagicMock()
        args.command = 'play'
        args.target = None
        args.scan = False
        
        with patch('sys.argv', ['main.py', 'play']):
            with patch('blucommand.main.argparse.ArgumentParser.parse_args', return_value=args):
                main.main()
                mock_cli.play.assert_called_once()

