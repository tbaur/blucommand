#!/usr/bin/env python3
"""
Blucommand - Main entry point.

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
import argparse
import subprocess
import re
from pathlib import Path

# Setup logging before other imports
debug_mode = os.environ.get("BLUCOMMAND_DEBUG") == "1"
structured_logging = os.environ.get("BLUCOMMAND_STRUCTURED_LOG") == "1"
from utils import setup_logging
logger = setup_logging(debug=debug_mode, structured=structured_logging)

from controller import BluOSController
from cli import BluOSCLI


def run_tests_and_update_docs() -> None:
    """Run test suite and update documentation with results."""
    print("🧪 Running test suite...\n")
    
    # Find repository root by looking for requirements-test.txt
    # Resolve symlinks to get actual script location
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent
    
    # If we're in a symlinked location (e.g., ~/local/bin), find the actual repo
    # Look for requirements-test.txt in parent directories
    max_depth = 10
    for _ in range(max_depth):
        if (repo_root / "requirements-test.txt").exists():
            break
        parent = repo_root.parent
        if parent == repo_root:  # Reached filesystem root
            break
        repo_root = parent
    else:
        # If not found, try common locations
        possible_roots = [
            Path.home() / "github" / "blucommand",
            Path.home() / ".config" / "blucommand",
            Path(__file__).parent,
        ]
        for root in possible_roots:
            if (root / "requirements-test.txt").exists():
                repo_root = root
                break
    
    if not (repo_root / "requirements-test.txt").exists():
        print(f"❌ Error: Could not find repository root (requirements-test.txt not found)")
        print(f"   Searched from: {script_path}")
        print(f"   Current directory: {Path.cwd()}")
        sys.exit(1)
    
    venv_dir = repo_root / ".venv"
    pytest_cmd = None
    
    # Check if pytest is available in current environment
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10,  # Security: Add timeout
            check=True,
            shell=False  # Security: Explicitly disable shell
        )
        pytest_cmd = ["python3", "-m", "pytest"]
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # Try using venv if it exists
        venv_pytest = venv_dir / "bin" / "pytest"
        if venv_pytest.exists():
            pytest_cmd = [str(venv_pytest)]
        else:
            # Try to create venv and install dependencies
            print("📦 Creating virtual environment for tests...")
            try:
                # Security: Validate venv_dir path and add timeout
                if not venv_dir or not isinstance(venv_dir, Path):
                    raise ValueError("Invalid venv directory")
                
                subprocess.run(
                    ["python3", "-m", "venv", str(venv_dir)],
                    check=True,
                    capture_output=True,
                    timeout=60,  # Security: Add timeout for venv creation
                    shell=False  # Security: Explicitly disable shell
                )
                # Install test dependencies in venv
                pip_path = venv_dir / "bin" / "pip"
                if not pip_path.exists():
                    raise FileNotFoundError(f"pip not found at {pip_path}")
                
                subprocess.run(
                    [str(pip_path), "install", "-q", "-r", str(repo_root / "requirements-test.txt")],
                    check=True,
                    capture_output=True,
                    timeout=300,  # Security: Add timeout for pip install (5 minutes)
                    shell=False  # Security: Explicitly disable shell
                )
                pytest_cmd = [str(venv_pytest)]
                print("✅ Virtual environment created and dependencies installed\n")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to create virtual environment: {e}")
                print("\n💡 Try installing test dependencies manually:")
                print("   python3 -m venv .venv")
                print("   source .venv/bin/activate")
                print("   pip install -r requirements-test.txt")
                sys.exit(1)
    
    if not pytest_cmd:
        print("❌ Error: Could not find or install pytest")
        sys.exit(1)
    
    # Run tests with coverage
    # Security: Validate pytest_cmd and add timeout
    if not pytest_cmd or not isinstance(pytest_cmd, list):
        print("❌ Error: Invalid pytest command")
        sys.exit(1)
    
    # Security: Validate command arguments don't contain shell metacharacters
    for arg in pytest_cmd:
        if isinstance(arg, str) and any(char in arg for char in [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']):
            print("❌ Error: Unsafe characters in pytest command")
            sys.exit(1)
    
    test_result = subprocess.run(
        pytest_cmd + ["tests/", "--cov=.", "--cov-report=term", "-v"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=600,  # Security: Add timeout for test execution (10 minutes)
        shell=False  # Security: Explicitly disable shell
    )
    
    # Print test output
    print(test_result.stdout)
    if test_result.stderr:
        print(test_result.stderr, file=sys.stderr)
    
    # Parse test count and coverage
    test_count = 0
    coverage_percent = 0.0
    
    # Extract test count from output
    test_match = re.search(r'(\d+)\s+passed', test_result.stdout)
    if test_match:
        test_count = int(test_match.group(1))
    
    # Extract coverage percentage
    coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', test_result.stdout)
    if coverage_match:
        coverage_percent = int(coverage_match.group(1))
    else:
        # Try alternative format
        coverage_match = re.search(r'(\d+)%\s+coverage', test_result.stdout, re.IGNORECASE)
        if coverage_match:
            coverage_percent = int(coverage_match.group(1))
    
    # Update README.md
    readme_path = repo_root / "README.md"
    if readme_path.exists():
        readme_content = readme_path.read_text()
        
        # Update test statistics line
        old_pattern = r'- \*\*(\d+) tests\*\* with \*\*(\d+)% code coverage\*\*'
        new_line = f'- **{test_count} tests** with **{coverage_percent}% code coverage**'
        
        if re.search(old_pattern, readme_content):
            readme_content = re.sub(old_pattern, new_line, readme_content)
            readme_path.write_text(readme_content)
            print(f"\n✅ Updated README.md: {test_count} tests, {coverage_percent}% coverage")
        else:
            # Try to find and update any test/coverage mention
            readme_content = re.sub(
                r'(\d+)\s+tests.*?(\d+)%',
                f'{test_count} tests with {coverage_percent}%',
                readme_content
            )
            readme_path.write_text(readme_content)
            print(f"\n✅ Updated README.md with test statistics")
    
    # Update docs/README-DETAILED.md if it exists
    detailed_readme = repo_root / "docs" / "README-DETAILED.md"
    if detailed_readme.exists():
        detailed_content = detailed_readme.read_text()
        
        # Update test statistics
        detailed_content = re.sub(
            r'- \*\*(\d+) test methods\*\* across \d+ test files',
            f'- **{test_count} test methods** across 21 test files',
            detailed_content
        )
        detailed_content = re.sub(
            r'- \*\*(\d+)% code coverage\*\* across all modules',
            f'- **{coverage_percent}% code coverage** across all modules',
            detailed_content
        )
        detailed_readme.write_text(detailed_content)
        print(f"✅ Updated docs/README-DETAILED.md")
    
    # Exit with test result code
    if test_result.returncode != 0:
        print(f"\n❌ Tests failed with exit code {test_result.returncode}")
        sys.exit(test_result.returncode)
    else:
        print(f"\n✅ All tests passed! ({test_count} tests, {coverage_percent}% coverage)")


def main() -> None:
    """Main entry point."""
    # Check for --run-code-tests flag first
    if '--run-code-tests' in sys.argv:
        run_tests_and_update_docs()
        return
    
    if len(sys.argv) == 1 or sys.argv[1] in ['-h', '--help']:
        BluOSCLI(None).print_help()  # type: ignore
        sys.exit(0)
    
    p = argparse.ArgumentParser(add_help=False)
    sub = p.add_subparsers(dest="command")
    
    sub.add_parser("discover")
    
    r = sub.add_parser("status")
    r.add_argument("pattern", nargs="?", default=None, help="Filter by name")
    r.add_argument("--json", action="store_true")
    r.add_argument("--scan", action="store_true")
    
    d = sub.add_parser("diagnose")
    d.add_argument("target")
    
    v = sub.add_parser("volume")
    v.add_argument("cmd", nargs="?")
    v.add_argument("target", nargs="?", default="all")
    
    # Playback controls
    play_cmd = sub.add_parser("play")
    play_cmd.add_argument("target", nargs="?", default=None)
    
    pas = sub.add_parser("pause")
    pas.add_argument("target", nargs="?", default=None)
    
    stop_cmd = sub.add_parser("stop")
    stop_cmd.add_argument("target", nargs="?", default=None)
    
    skip_cmd = sub.add_parser("skip")
    skip_cmd.add_argument("target", nargs="?", default=None)
    
    prev_cmd = sub.add_parser("previous")
    prev_cmd.add_argument("target", nargs="?", default=None)
    
    toggle_cmd = sub.add_parser("toggle")
    toggle_cmd.add_argument("target", nargs="?", default=None)
    
    # Queue management
    queue_cmd = sub.add_parser("queue")
    queue_cmd.add_argument("action", nargs="?", default="show")
    queue_cmd.add_argument("target", nargs="?", default=None)
    queue_cmd.add_argument("from_index", nargs="?", default=None, help="From index (for move)")
    queue_cmd.add_argument("to_index", nargs="?", default=None, help="To index (for move)")
    
    # Input management
    inputs_cmd = sub.add_parser("inputs")
    inputs_cmd.add_argument("target", nargs="?", default=None)
    inputs_cmd.add_argument("input", nargs="?", default=None, help="Input name to set")
    
    # Bluetooth
    bt_cmd = sub.add_parser("bluetooth")
    bt_cmd.add_argument("target", nargs="?", default=None)
    bt_cmd.add_argument("mode", nargs="?", default=None, help="Mode: manual, auto, guest, disable")
    
    # Presets
    presets_cmd = sub.add_parser("presets")
    presets_cmd.add_argument("target", nargs="?", default=None)
    presets_cmd.add_argument("preset_id", nargs="?", default=None, type=int, help="Preset ID to play")
    
    # Sync groups
    sync_cmd = sub.add_parser("sync")
    sync_cmd.add_argument(
        "action",
        choices=["enable", "create", "break", "list"],
        help="enable: group all others under primary; create/break/list as before",
    )
    sync_cmd.add_argument(
        "master",
        nargs="?",
        default=None,
        help="Primary/master device name (enable, create) or break target",
    )
    sync_cmd.add_argument("slaves", nargs="?", default=None, help="Slave devices, comma-separated (for create)")
    sync_cmd.add_argument("target", nargs="?", default=None, help="Target device (for break)")
    sync_cmd.add_argument("--scan", action="store_true", help="Force network rescan before command")
    
    # Reboot
    reboot_cmd = sub.add_parser("reboot")
    reboot_cmd.add_argument("--soft", action="store_true", help="Soft reboot")
    reboot_cmd.add_argument("target", nargs="?", default=None, help="Target device name (optional)")
    
    # Keychain management
    keychain_cmd = sub.add_parser("keychain")
    keychain_cmd.add_argument("action", choices=["set", "get", "delete"], help="Action: set, get, or delete API key")
    
    args = p.parse_args()
    
    ctl = BluOSController()
    cli = BluOSCLI(ctl)
    
    # Skip network discovery for commands that don't need it
    if args.command == "keychain":
        pass
    elif args.command == "discover":
        ctl.discover(force_refresh=True)
    else:
        force = getattr(args, 'scan', False)
        ctl.discover(force_refresh=force)
    
    if args.command == "discover":
        cli.discover()
    elif args.command == "status":
        cli.status(
            pattern=args.pattern,
            json_mode=args.json,
            force_refresh=getattr(args, 'scan', False),
        )
    elif args.command == "volume":
        cli.volume(args)
    elif args.command == "play":
        cli.play(args)
    elif args.command == "pause":
        cli.pause(args)
    elif args.command == "stop":
        cli.stop(args)
    elif args.command == "skip":
        cli.skip(args)
    elif args.command == "previous":
        cli.previous(args)
    elif args.command == "toggle":
        cli.toggle(args)
    elif args.command == "queue":
        cli.queue(args)
    elif args.command == "inputs":
        cli.inputs(args)
    elif args.command == "bluetooth":
        cli.bluetooth(args)
    elif args.command == "presets":
        cli.presets(args)
    elif args.command == "sync":
        cli.sync(args)
    elif args.command == "reboot":
        if getattr(args, 'soft', False):
            cli.soft_reboot(args)
        else:
            cli.reboot(args)
    elif args.command == "diagnose":
        cli.diagnose(args.target)
    elif args.command == "keychain":
        cli.keychain(args)


if __name__ == "__main__":
    main()

