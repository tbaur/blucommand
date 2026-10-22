# Blucommand

[![Tests](https://github.com/tbaur/blucommand/actions/workflows/test.yml/badge.svg)](https://github.com/tbaur/blucommand/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![macOS](https://img.shields.io/badge/macOS-10.15%2B-lightgrey.svg)](https://www.apple.com/macos/)

Command-line controller for BluOS devices on macOS. Pure Python standard library.

## Quick Start

```bash
# from the cloned repo
./install.sh
```

This installs to `~/.config/blucommand` and creates a symlink at `~/local/bin/blucommand`.

```bash
blucommand discover          # Find devices (mDNS + CI zones)
blucommand status            # Show all device status
blucommand status --scan     # Force rediscovery, then status
blucommand volume 25         # Set volume
blucommand play "Player A"    # Play on specific device
blucommand --help            # Full command reference
```

## Features

- **Discovery** — mDNS (`_musc` + `_musp` for CI secondary zones) and/or LSDP; players keyed as `ip:port`; SyncStatus verified before caching
- **Playback** — play, pause, stop, skip, previous, toggle
- **Volume** — absolute, relative (+/-), mute/unmute, reset to safe level
- **Queue** — view, clear, reorder
- **Inputs** — list and switch audio sources
- **Bluetooth** — get/set mode (manual, auto, guest, disable)
- **Presets** — list and play
- **Sync Groups** — create, break, list multi-room groups (including orphan ungroup when primary is offline)
- **Diagnostics** — device info, uptime, network stats
- **UniFi Integration** — optional network statistics from UniFi Controller
- **Keychain** — store API keys securely in macOS Keychain

All device commands load discovery (cache by default). `status` and `sync` accept `--scan` to force a rescan; other commands auto-rescan once if every cached endpoint is dead. Target all devices (default), a name, or a pattern.

NAD multi-zone players (e.g. NAD CI S2 or CI 580 V2) advertise secondary zones on `_musp._tcp` with non-default ports (`11010+`). Those zones appear as separate `ip:port` endpoints alongside the primary on `11000`.

## Configuration

Stored in `~/.config/blucommand/config.json`:

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

Discovery methods: `mdns` (default), `lsdp`, or `both` (mDNS first, LSDP fallback).

mDNS always browses `_musc._tcp` (primary players) and `_musp._tcp` (CI secondary zones). LSDP discovers chassis IPs only (normalized to `ip:11000`).

### API Key Storage

Store your API key in macOS Keychain instead of plaintext config:

```bash
blucommand keychain set      # Store key
blucommand keychain get      # Check status
blucommand keychain delete   # Remove key
```

Keychain values take precedence over `config.json`.

## Requirements

- Python 3.10+ (standard library only)
- macOS 10.15+ (uses `dns-sd` and `dscacheutil` for discovery)

## Uninstall

```bash
rm -rf ~/.config/blucommand
rm ~/local/bin/blucommand
```

## Documentation

The command and the BluOS client live in `src/blucommand`. Tests are in `tests/`. Longer guides are in `docs/`.

- [CHANGELOG](CHANGELOG.md) — version history
- [CONTRIBUTING](CONTRIBUTING.md) — contribution guidelines
- [SECURITY](SECURITY.md) — security policy

## License

Copyright 2026 tbaur.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
