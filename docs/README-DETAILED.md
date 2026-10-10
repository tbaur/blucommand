# BluOS Controller - Detailed Documentation

> **Note**: This is the detailed documentation. For a quick start guide, see the [main README.md](../README.md).

A production-ready, unified command-line controller for BluOS devices on macOS.

Current line: multi-zone discovery (`ip:port`, `_musc` + `_musp` for CI secondary zones). Released version is tagged; see [CHANGELOG.md](../CHANGELOG.md).

## Features

### Device Discovery

**Dual Discovery Protocol Support:**
- **mDNS (Bonjour)**: Default discovery method using macOS native `dns-sd`. Browses `_musc._tcp` (primary players) and `_musp._tcp` (CI secondary zones such as NAD CI S2) and keeps the SRV port.
- **LSDP (Lenbrook Service Discovery Protocol)**: Alternative discovery using UDP broadcast on port 11430. More reliable on networks with multicast issues. Discovers chassis IPs only (normalized to `ip:11000`); use mDNS for secondary zones.
- **Hybrid Mode**: Configure `DISCOVERY_METHOD=both` to try mDNS first, automatically fallback to LSDP if no devices found.

**Discovery Features:**
- Players keyed as canonical `ip:port` (primary `11000`, CI zones `11010+`)
- `/SyncStatus` verification before writing the discovery cache
- Configurable discovery timeout (default: 5 seconds)
- Intelligent caching with TTL (default: 300 seconds) to reduce network traffic
- IP/endpoint validation and sanitization (rejects loopback, multicast, reserved, and link-local addresses)
- Support for BluOS Players, Servers, Hubs, and CI multi-zone secondary endpoints

### Status Monitoring

**Comprehensive Device Information:**
- Device name, model, brand, and firmware version
- Current playback state (play, pause, stop, stream, connecting)
- Volume level and mute status
- Currently playing track (title, artist, album)
- Active service/input source
- Battery level (for portable devices)
- System uptime from device diagnostics
- Sync group information (master/slave relationships)

**Network Statistics (with UniFi Integration):**
- Wired/WiFi connection status
- Uplink information (switch/AP name, port)
- Network throughput (down/up totals and rates)
- Connection uptime
- RSSI signal strength for WiFi devices

**Output Formats:**
- Human-readable formatted output with color coding
- JSON output mode for scripting and automation
- Filterable by device name pattern

### Volume Control

**Multi-Device Support:**
- Control all devices simultaneously (default)
- Target specific devices by name
- Pattern matching for multiple devices (e.g., "Zone" matches "Zone One", "Zone Two")

**Volume Operations:**
- Set absolute volume (0-100%)
- Increment/decrement volume (+/- values)
- Mute/unmute individual or all devices
- Reset to configurable safe volume level
- Real-time volume display with status indicators

### Playback Control

**Full Playback Management:**
- Play/resume playback on all or selected devices
- Pause playback (individual or all devices)
- Stop playback completely
- Skip to next track
- Go to previous track
- Toggle play/pause state (intelligently switches based on current state)

**Multi-Device Operations:**
- All commands support operating on all devices, specific devices, or pattern-matched devices
- Concurrent execution using thread pools for fast multi-device control
- Status feedback for each device operation

### Queue Management

**Queue Operations:**
- View current playback queue with track information (title, artist, album, service)
- Clear queue on all or selected devices
- Reorder tracks by moving items within queue
- Queue information includes track count and metadata

### Input Source Selection

**Audio Input Control:**
- List all available audio inputs for devices
- Switch between inputs (Bluetooth, Optical, USB, Network, etc.)
- Display currently selected input with visual indicators
- Support for all devices or specific device targeting

### Bluetooth Mode Control

**Bluetooth Configuration:**
- Get current Bluetooth mode for devices
- Set Bluetooth mode:
  - **Manual**: Requires manual pairing
  - **Automatic**: Auto-connects to paired devices
  - **Guest**: Allows guest device connections
  - **Disabled**: Completely disables Bluetooth
- Multi-device support for bulk configuration

### Preset Management

**Preset Operations:**
- List all available presets for devices
- Play presets by ID on all or selected devices
- Preset information includes name and image metadata

### Sync Group Management

**Multi-Room Synchronization (runtime groups):**
- Create sync groups with a primary player and one or more slaves
- Uses BluOS `AddSlave` / `RemoveSlave` on the primary (not legacy `/Sync`)
- Break sync groups by removing slaves from the primary
- List groups with primary/slave relationships and combined group names
- Parses `/SyncStatus` for `group`, `<master>`, and `<slave>` elements
- Devices in sync groups automatically follow primary playback

**Example output (`sync list`):**

```text
Group: Zone One + 1 slave
  Primary: Zone One (192.168.1.32)
  Slave:   Player A (192.168.1.20)

Standalone:
  Player B (192.168.1.23)
```

**Example output (`status`, grouped primary with 7 slaves):**

```text
[1] Zone One
    Status: ★ PRIMARY  |  Vol: 10%  |  Source: Tidal
    Sync:   6 slaves
    ♫ Track:  Hayling
```

### Device Diagnostics

**Comprehensive Diagnostics:**
- IP address and MAC address (via ARP)
- System uptime from device
- UniFi network database lookup (if enabled)
- Raw XML endpoint responses for troubleshooting
- Connection status and network information

### Reboot Control

**Device Reboot Options:**
- Hard reboot (full device restart)
- Soft reboot (less disruptive, preserves some state)
- Support for all devices or specific device targeting
- Safety confirmation prompts

### Security Features

**Input Validation & Sanitization:**
- IP address validation using `ipaddress` module
- Rejects invalid, loopback, multicast, reserved, and link-local addresses
- Hostname validation before subprocess calls
- Volume and timeout value range validation
- Configuration value validation on load

**XML Security:**
- Safe XML parsing with size limits (1MB default)
- Depth limit protection (20 levels) to prevent XML bombs
- Entity expansion protection
- Proper error handling for malformed XML

**URL Security:**
- URL scheme validation (only http/https allowed)
- IP sanitization before use in URLs
- Size limit enforcement for responses

**File Security:**
- Secure file permissions (600 for config, 700 for cache)
- Atomic file writes to prevent corruption
- Input validation before file operations

### Reliability Features

**Error Handling:**
- Specific exception types for different error conditions
- Graceful degradation on network failures
- Timeout protection for all network operations (configurable)
- Subprocess timeout protection (5 seconds default)
- Cache validation and expiration handling

**Performance:**
- Thread pool execution for concurrent operations
- Configurable worker limits (10 for discovery, 20 for status)
- Intelligent caching to reduce network traffic
- Efficient device filtering and pattern matching

### UniFi Integration

**Network Statistics (Optional):**
- Integration with UniFi Controller API
- Automatic client lookup by IP address
- Network topology information (switch, AP, port)
- Throughput statistics (wired and wireless)
- Connection uptime tracking
- Cached results to reduce API calls

**Configuration:**
- Enable/disable via configuration
- Supports custom UniFi sites
- API key authentication
- Configurable cache TTL

### Multi-Device Support

**Universal Device Targeting:**
- All commands support operating on all devices (default behavior)
- Target specific devices by exact or partial name match
- Pattern matching for bulk operations (e.g., "Zone" matches multiple devices)
- Case-insensitive device name matching
- Clear feedback showing which devices are being controlled

**Concurrent Execution:**
- Parallel operations using ThreadPoolExecutor
- Fast multi-device control with status feedback
- Independent error handling per device
- No cascading failures between devices

## Installation

### Quick Install

Run the installation script from the repository:

```bash
# from the cloned repo
./install.sh
```

The script will:
- Copy files to `~/.config/bluos-controller`
- Prompt for configuration settings (UniFi integration, etc.)
- Create `config.json` with your settings
- Create a symlink `~/local/bin/bluos-controller` (add to PATH if needed)

### Manual Installation

1. Clone or copy this repository to `~/.config/bluos-controller`
2. Ensure Python 3.10+ is installed
3. Make `main.py` executable: `chmod +x main.py`
4. Create `config.json` (see Configuration section)

## Configuration

Configuration is stored in `~/.config/bluos-controller/config.json` (JSON format is preferred, but INI format is also supported for backward compatibility).

### Basic Configuration

```json
{
  "DISCOVERY_METHOD": "mdns",
  "DISCOVERY_TIMEOUT": "5",
  "CACHE_TTL": "300",
  "DEFAULT_SAFE_VOL": "14",
  "UNIFI_ENABLED": "false",
  "UNIFI_CONTROLLER": "",
  "UNIFI_API_KEY": "",
  "UNIFI_SITE": "default"
}
```

**Discovery Methods:**
- `mdns` - mDNS/Bonjour discovery (default, recommended); always browses `_musc._tcp` and `_musp._tcp`
- `lsdp` - LSDP (Lenbrook Service Discovery Protocol) - more reliable on networks with multicast issues; primary port only
- `both` - Try mDNS first, fallback to LSDP if no devices found

`BLUOS_SERVICE` may still appear in older configs; discovery ignores it and uses the built-in dual-service browse list.

### UniFi Integration (Optional)

To enable UniFi integration for network statistics, set:

```json
{
  "UNIFI_ENABLED": "true",
  "UNIFI_CONTROLLER": "your-controller.local",
  "UNIFI_API_KEY": "your-api-key",
  "UNIFI_SITE": "default"
}
```

#### Secure API Key Storage (macOS Keychain)

**Recommended**: Store your UniFi API key securely in macOS Keychain instead of plaintext in `config.json`:

```bash
# Store API key in Keychain
bluos-controller keychain set

# Check if API key is stored
bluos-controller keychain get

# Remove API key from Keychain
bluos-controller keychain delete
```

**How it works:**
- The `keychain set` command prompts for your API key and stores it securely in macOS Keychain
- When the controller needs the API key, it checks Keychain first, then falls back to `config.json`
- Keychain values take precedence over `config.json` entries
- If you store the key in Keychain, you can leave `UNIFI_API_KEY` empty in `config.json`

**Security Benefits:**
- ✅ API key stored in macOS Keychain (encrypted, system-managed)
- ✅ No plaintext API keys in config files
- ✅ Keychain access requires user authentication
- ✅ Backward compatible: existing `config.json` entries still work

**Note**: Keychain storage is only available on macOS. On other platforms, use `config.json`.

## Usage

After installation, use the `bluos-controller` command:

**Note**: Most commands support controlling all devices (default) or specific devices by name. Device names can be:
- Exact match: `"Zone One"`
- Partial match: `"Zone"` matches "Zone One", "Zone Two", etc.
- Case-insensitive matching

### Discover Devices

```bash
bluos-controller discover
```

### Status Report

```bash
# All devices
bluos-controller status

# Filter by name
bluos-controller status "Zone One"

# Force fresh scan
bluos-controller status --scan

# JSON output
bluos-controller status --json
```

### Volume Control

```bash
# List current volumes
bluos-controller volume

# Set absolute volume
bluos-controller volume 20

# Adjust volume
bluos-controller volume +5
bluos-controller volume -10

# Mute/Unmute
bluos-controller volume mute
bluos-controller volume unmute

# Reset to safe volume
bluos-controller volume reset

# Target specific device
bluos-controller volume 25 "Zone One"
```

### Playback Control

All playback commands support controlling all devices (default) or specific devices by name/pattern:

```bash
# All devices (default)
bluos-controller play
bluos-controller pause
bluos-controller stop
bluos-controller skip
bluos-controller previous
bluos-controller toggle

# Specific device
bluos-controller play "Zone One"
bluos-controller pause "Player A"

# Pattern matching (multiple devices)
bluos-controller play "Zone"  # Matches "Zone One", "Zone Two", etc.
```

### Queue Management

Queue commands support all devices or specific devices:

```bash
# Show queue for all devices
bluos-controller queue

# Show queue for specific device
bluos-controller queue "Zone One"

# Clear queue on all devices
bluos-controller queue clear

# Clear queue on specific device
bluos-controller queue clear "Player A"

# Move track in queue (all or specific)
bluos-controller queue move 3 1          # All devices
bluos-controller queue move 3 1 "Zone One"  # Specific device
```

### Input Source Selection

Input commands support all devices or specific devices:

```bash
# List inputs for all devices
bluos-controller inputs

# List inputs for specific device
bluos-controller inputs "Zone One"

# Set input on all devices
bluos-controller inputs "" "Bluetooth"

# Set input on specific device
bluos-controller inputs "Zone One" "Bluetooth"
bluos-controller inputs "Player A" "Optical 1"
```

### Bluetooth Mode Control

Bluetooth commands support all devices or specific devices:

```bash
# Show Bluetooth mode for all devices
bluos-controller bluetooth

# Show mode for specific device
bluos-controller bluetooth "Zone One"

# Set mode on all devices
bluos-controller bluetooth "" auto

# Set mode on specific device
bluos-controller bluetooth "Zone One" manual
bluos-controller bluetooth "Player A" auto
bluos-controller bluetooth "Zone Two" guest
bluos-controller bluetooth "Player C" disable
```

### Preset Management

Preset commands support all devices or specific devices:

```bash
# List presets for all devices
bluos-controller presets

# List presets for specific device
bluos-controller presets "Zone One"

# Play preset on all devices
bluos-controller presets "" 1

# Play preset on specific device
bluos-controller presets "Zone One" 1
```

### Sync Group Management

Runtime BluOS groups use the **primary** player to attach or detach slaves.

```bash
# Create sync group (Zone One primary, Player A + Zone Two slaves)
bluos-controller sync create "Zone One" "Player A,Zone Two"

# Break all runtime groups
bluos-controller sync break

# Refresh discovery, then list groups
bluos-controller sync list --scan

# Break groups involving a specific player (primary or slave)
bluos-controller sync break "Player A"

# List sync groups and standalone players
bluos-controller sync list
```

`sync list` reads `/SyncStatus` from each player and shows:

- Combined `group` name on the primary (same name Tidal Connect may advertise)
- Primary and slave IPs/names
- Standalone players not currently grouped

Ungrouping always sends `RemoveSlave` to the **primary**, matching BluOS runtime group behavior.

### Device Diagnostics

```bash
bluos-controller diagnose "Device Name"
```

### Keychain Management (macOS)

Manage UniFi API key storage in macOS Keychain:

```bash
# Store API key in Keychain (prompts for password)
bluos-controller keychain set

# Check API key status
bluos-controller keychain get

# Remove API key from Keychain
bluos-controller keychain delete
```

**Note**: Keychain operations are macOS-only and don't require network discovery, making them fast and efficient.

### Reboot Devices

Reboot commands support all devices or specific devices:

```bash
# Hard reboot all devices
bluos-controller reboot

# Hard reboot specific device
bluos-controller reboot "Zone One"

# Soft reboot all devices
bluos-controller reboot --soft

# Soft reboot specific device
bluos-controller reboot --soft "Player A"
```

## Debug Mode & Logging

### Debug Logging

Enable debug logging by setting the environment variable:

```bash
export BLUOS_DEBUG=1
bluos-controller status
```

Debug logs are written to `~/.config/bluos-controller/bluos-controller.log`

### Structured Logging (JSON Format)

Enable JSON-formatted structured logging for better log parsing and analysis:

```bash
export BLUOS_STRUCTURED_LOG=1
bluos-controller status
```

Structured logs include:
- Timestamp (ISO 8601 format)
- Log level (DEBUG, INFO, WARNING, ERROR)
- Logger name and module information
- Function name and line number
- Custom fields (device IP, operation, etc.)
- Exception information (when applicable)

This format is ideal for log aggregation systems, monitoring tools, and automated analysis.

## Requirements

- **Python**: 3.10+ (uses only standard library - no external dependencies)
- **Operating System**: macOS (uses `dns-sd` and `dscacheutil` for mDNS discovery)
- **Network**: Access to BluOS devices on local network
- **Optional**: UniFi Controller (for network statistics integration)

## Project Structure

```
bluos-controller/
├── main.py              # Entry point
├── constants.py         # Constants and configuration
├── models.py            # Data models
├── validators.py        # Input validation and sanitization
├── config.py            # Configuration management
├── network.py           # Network I/O operations
├── utils.py             # Utility functions
├── controller.py        # Core controller logic
├── cli.py               # CLI interface
├── install.sh           # Installation script
├── config.json          # Configuration file (generated)
├── cache/               # Cache directory (generated)
└── tests/               # Comprehensive test suite (263 tests, 82% coverage)
    ├── test_cli_commands.py          # CLI command tests
    ├── test_cli_coverage.py          # CLI edge cases and error paths
    ├── test_cli_multi_device.py     # Multi-device support tests
    ├── test_config.py               # Configuration management tests
    ├── test_controller.py           # Core controller logic tests
    ├── test_controller_coverage.py   # Controller edge cases
    ├── test_controller_discovery.py # Discovery method tests
    ├── test_controller_new_features.py # New feature tests
    ├── test_controller_xml.py       # XML parsing and security tests
    ├── test_integration.py           # End-to-end integration tests
    ├── test_lsdp.py                 # LSDP discovery basic tests
    ├── test_lsdp_comprehensive.py   # LSDP comprehensive tests
    ├── test_main.py                 # Main entry point tests
    ├── test_main_coverage.py        # Main command routing tests
    ├── test_network.py              # Network operation tests
    ├── test_utils.py                # Utility function tests
    ├── test_utils_comprehensive.py  # Comprehensive utility tests
    ├── test_utils_retry.py          # Retry logic and rate limiting tests
    └── test_validators.py           # Input validation tests
```

## Development

### Running Tests

**Easy Method (Recommended):**
```bash
bluos-controller --run-code-tests
```
This command will:
- Run all tests with coverage
- Automatically update README.md and docs/README-DETAILED.md with latest test statistics
- Works from any location (finds repository root automatically)
- Creates virtual environment if needed (handles externally-managed Python environments)

**Manual Method:**
Install test dependencies:
```bash
pip install -r requirements-test.txt
```

Run all tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=. --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_validators.py -v
```

### Smoke Tests

Quick validation that all commands execute without crashing (uses mocked devices):

```bash
python3 smoke_test.py
```

The smoke test verifies all 33 CLI commands work correctly without requiring actual hardware. It's useful for:
- Quick validation after code changes
- CI/CD pipeline integration
- Ensuring no regressions in command execution

### Test Coverage

The test suite includes:
- **263 test methods** across 21 test files
- **82% code coverage** across all modules
- Input validation tests (IPs, hostnames, volumes, timeouts)
- Configuration management tests
- Network operation tests with retry logic
- Controller logic tests (discovery, device info, operations)
- CLI command tests (all commands, multi-device support)
- Rate limiting and retry logic tests
- Structured logging tests
- Integration tests
- XML parsing and security tests
- LSDP discovery comprehensive tests
- Security feature validation

See `tests/README.md` for detailed test documentation.

### Code Structure

The codebase is organized into modular components:

- **models.py**: Immutable data classes using `@dataclass` for `UniFiClient` and `PlayerStatus`
- **validators.py**: Comprehensive input validation and sanitization
  - IP address validation (rejects invalid, loopback, multicast, reserved, link-local)
  - Hostname validation before subprocess calls
  - Volume and timeout range validation
  - Configuration value validation on load
- **config.py**: Configuration file management
  - Supports JSON (preferred) and INI (backward compatibility)
  - Automatic default config creation
  - Value validation on load
  - Secure file permissions (600)
- **network.py**: HTTP requests and network operations
  - GET and POST requests with timeout support
  - SSL context management (disabled for local IoT)
  - Size limit enforcement
  - Comprehensive error handling
- **utils.py**: Utility functions
  - Byte and rate formatting (human-readable)
  - Uptime formatting
  - Atomic file writes (prevents corruption)
  - Logging setup
- **controller.py**: Core device management logic
  - Dual discovery (mDNS and LSDP)
  - Device information retrieval
  - UniFi integration
  - XML parsing with security protections
  - All BluOS API endpoint implementations
- **cli.py**: Command-line interface
  - Multi-device support with pattern matching
  - Color-coded output formatting
  - Comprehensive help documentation
  - Thread pool execution for concurrent operations
- **lsdp.py**: LSDP discovery protocol
  - UDP broadcast implementation
  - Binary packet parsing (Query, Announce, Delete)
  - Class ID support (Players, Servers, Hubs)
  - TXT record parsing

### Production-Ready Features

- **Retry Logic**: Automatic retry with exponential backoff for transient network failures
- **Rate Limiting**: Per-device rate limiting to prevent overwhelming devices
- **Structured Logging**: JSON-formatted logs for better parsing and analysis
- **Error Recovery**: Graceful degradation when optional services (e.g., UniFi) fail
- **Circuit Breaker Pattern**: Prevents cascading failures from repeated retries
- **Operation Throttling**: Configurable delays between device operations

### Security Features

- **Input Validation**: All IP addresses, hostnames, and config values are validated
- **XML Protection**: Safe XML parsing with size and depth limits to prevent XML bombs
- **URL Security**: URL scheme validation and IP sanitization
- **Subprocess Security**: Input validation and timeout protection for subprocess calls
- **File Security**: Secure file permissions (600 for config, 700 for cache)

### Code Quality

- Comprehensive test suite (263 tests, 82% coverage)
- Type hints throughout
- Error handling with specific exception types
- Constants extracted (no magic numbers)
- Documentation and docstrings
- Pinned dependency versions for reproducible builds

## Environment Variables

- `BLUOS_DEBUG=1`: Enable debug logging
- `BLUOS_STRUCTURED_LOG=1`: Enable JSON structured logging format

## Troubleshooting

### Devices Not Found

1. **Check Network Connectivity**: Ensure devices are on the same network
2. **Try Different Discovery Method**: 
   ```bash
   # Edit ~/.config/bluos-controller/config.json
   # Change "DISCOVERY_METHOD" to "lsdp" or "both"
   ```
3. **Force Fresh Discovery**: Use `--scan` flag
   ```bash
   bluos-controller status --scan
   ```
4. **Check Firewall**: Ensure UDP port 11430 (LSDP) and mDNS are not blocked

### Network Errors

- **Timeout Errors**: Increase `DISCOVERY_TIMEOUT` in config (default: 5 seconds)
- **Connection Refused**: Verify device IP addresses are correct
- **Retry Logic**: Network operations automatically retry up to 3 times with exponential backoff

### UniFi Integration Issues

- **No Network Stats**: UniFi integration is optional - the controller continues without it
- **Check Config**: Verify `UNIFI_ENABLED=true` and API credentials are correct
- **Cache**: UniFi data is cached - use `--scan` to force refresh

### Performance Issues

- **Rate Limiting**: Operations are automatically rate-limited per device (0.1s minimum delay)
- **Concurrent Operations**: Discovery and status operations use thread pools for efficiency
- **Caching**: Discovery results are cached (default: 5 minutes) to reduce network traffic

### Logging

- **Debug Mode**: Set `BLUOS_DEBUG=1` for detailed logging
- **Structured Logs**: Set `BLUOS_STRUCTURED_LOG=1` for JSON-formatted logs
- **Log Location**: `~/.config/bluos-controller/bluos-controller.log`

## Version

See [CHANGELOG.md](../CHANGELOG.md) for the current released version and history. Unreleased work on `main` may include multi-zone CI discovery ahead of the next Release PR merge.

## Additional Documentation

- **[CHANGELOG.md](../CHANGELOG.md)**: Version history
- **[SECURITY.md](../SECURITY.md)**: Security policy and vulnerability reporting
- **[CONTRIBUTING.md](../CONTRIBUTING.md)**: Contribution guidelines
- **[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)**: Architecture and security overview
- **[API_VERIFICATION.md](API_VERIFICATION.md)**: BluOS API compatibility notes

## Statistics

- **Lines of Code**: ~4,200 (excluding tests)
- **Test Code**: ~3,400 lines across 20 test files
- **Test Coverage**: 80%+ (258 tests)
- **Modules**: 10 core modules
- **Commands**: 16 CLI commands

## License

Copyright 2026 tbaur

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the LICENSE file for the full text of the License.

