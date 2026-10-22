#!/bin/bash
#
# Blucommand Installation Script
# Sets up the controller in ~/.config/blucommand
#
# Copyright 2025 tbaur
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.config/blucommand"
BIN_DIR="$HOME/local/bin"
BIN_NAME="blucommand"

echo -e "${BOLD}${BLUE}Blucommand Installation${RESET}"
echo -e "${BLUE}=======================================${RESET}"
echo ""

# Check if this is an update or new install
CONFIG_FILE="$HOME/.config/blucommand/config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${CYAN}Update mode: Existing installation detected${RESET}"
    echo -e "${DIM}Configuration will be preserved.${RESET}"
    echo ""
else
    echo -e "${CYAN}New installation mode${RESET}"
    echo ""
fi

# Check if Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is required but not found.${RESET}"
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo -e "${RED}Error: Python 3.10 or newer is required.${RESET}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${CYAN}Found Python ${PYTHON_VERSION}${RESET}"
echo ""

# Create installation directory
echo -e "${CYAN}Creating installation directory...${RESET}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/cache"
mkdir -p "$BIN_DIR"

# Secure cache directory (owner only access)
chmod 700 "$INSTALL_DIR/cache" 2>/dev/null || true

# Install the package where Python can import it, next to the config.
echo -e "${CYAN}Installing package...${RESET}"
rm -rf "$INSTALL_DIR/blucommand"
cp -R "$SCRIPT_DIR/src/blucommand" "$INSTALL_DIR/blucommand"
cat > "$INSTALL_DIR/blucommand-run" << EOF
#!/bin/bash
export PYTHONPATH="$INSTALL_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m blucommand "\$@"
EOF
chmod +x "$INSTALL_DIR/blucommand-run"

# Determine if this is a new install or update
CONFIG_FILE="$INSTALL_DIR/config.json"
IS_UPDATE=false

if [ -f "$CONFIG_FILE" ]; then
    IS_UPDATE=true
    echo -e "${CYAN}Preserving existing configuration...${RESET}"
    echo ""
else
    echo -e "${CYAN}Setting up configuration...${RESET}"
    echo ""
fi

# Only create config if it doesn't exist (new install)
if [ "$IS_UPDATE" = false ]; then
    # Prompt for basic settings
    echo ""
    echo -e "${BOLD}Basic Configuration:${RESET}"
    
    echo "Discovery method:"
    echo "  1) mDNS (default, recommended)"
    echo "  2) LSDP (more reliable on some networks)"
    echo "  3) Both (try mDNS first, fallback to LSDP)"
    read -p "Choose [1]: " DISCOVERY_CHOICE
    DISCOVERY_CHOICE=${DISCOVERY_CHOICE:-1}
    case $DISCOVERY_CHOICE in
        2) DISCOVERY_METHOD="lsdp" ;;
        3) DISCOVERY_METHOD="both" ;;
        *) DISCOVERY_METHOD="mdns" ;;
    esac
    
    read -p "Discovery timeout (seconds) [5]: " DISCOVERY_TIMEOUT
    DISCOVERY_TIMEOUT=${DISCOVERY_TIMEOUT:-5}
    
    read -p "Cache TTL (seconds) [300]: " CACHE_TTL
    CACHE_TTL=${CACHE_TTL:-300}
    
    read -p "Default safe volume [14]: " DEFAULT_SAFE_VOL
    DEFAULT_SAFE_VOL=${DEFAULT_SAFE_VOL:-14}
    
    # Prompt for UniFi integration
    echo ""
    echo -e "${BOLD}UniFi Integration (optional):${RESET}"
    read -p "Enable UniFi integration? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        UNIFI_ENABLED="true"
        
        read -p "UniFi Controller address (e.g., unifi.local or 192.168.1.1): " UNIFI_CONTROLLER
        while [ -z "$UNIFI_CONTROLLER" ]; do
            echo -e "${RED}UniFi Controller address is required.${RESET}"
            read -p "UniFi Controller address: " UNIFI_CONTROLLER
        done
        
        read -p "UniFi API Key: " UNIFI_API_KEY
        while [ -z "$UNIFI_API_KEY" ]; do
            echo -e "${RED}UniFi API Key is required.${RESET}"
            read -p "UniFi API Key: " UNIFI_API_KEY
        done
        
        # Ask if user wants to store in Keychain (macOS only)
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo ""
            read -p "Store API key in macOS Keychain? (Y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                # Store in Keychain
                echo -e "${CYAN}Storing API key in Keychain...${RESET}"
                security add-generic-password -s "blucommand" -a "unifi-api-key" -w "$UNIFI_API_KEY" -U 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}✓ API key stored in Keychain${RESET}"
                    # Don't store in config.json if stored in Keychain
                    UNIFI_API_KEY=""
                else
                    echo -e "${YELLOW}⚠ Failed to store in Keychain, will store in config.json instead${RESET}"
                fi
            fi
        fi
        
        read -p "UniFi Site [default]: " UNIFI_SITE
        UNIFI_SITE=${UNIFI_SITE:-default}
    else
        UNIFI_ENABLED="false"
        UNIFI_CONTROLLER=""
        UNIFI_API_KEY=""
        UNIFI_SITE="default"
    fi
    
    # Create config.json
    cat > "$CONFIG_FILE" <<EOF
{
  "BLUOS_SERVICE": "_musc._tcp",
  "DISCOVERY_METHOD": "${DISCOVERY_METHOD}",
  "DISCOVERY_TIMEOUT": "${DISCOVERY_TIMEOUT}",
  "CACHE_TTL": "${CACHE_TTL}",
  "DEFAULT_SAFE_VOL": "${DEFAULT_SAFE_VOL}",
  "UNIFI_ENABLED": "${UNIFI_ENABLED}",
  "UNIFI_CONTROLLER": "${UNIFI_CONTROLLER}",
  "UNIFI_API_KEY": "${UNIFI_API_KEY}",
  "UNIFI_SITE": "${UNIFI_SITE}"
}
EOF
    
    # Secure the config file (owner read/write only, no group/other access)
    chmod 600 "$CONFIG_FILE"
    
    echo -e "${GREEN}Configuration saved to ${CONFIG_FILE}${RESET}"
    echo -e "${CYAN}Permissions set to 600 (owner read/write only)${RESET}"
else
    echo -e "${GREEN}Using existing configuration: ${CONFIG_FILE}${RESET}"
fi

# Create symlink in ~/local/bin
echo ""
echo -e "${CYAN}Creating symlink...${RESET}"

SYMLINK_TARGET="$BIN_DIR/$BIN_NAME"

# Remove existing symlink if it exists
if [ -L "$SYMLINK_TARGET" ]; then
    rm "$SYMLINK_TARGET"
    echo -e "${DIM}Removed existing symlink.${RESET}"
fi

# Create/update symlink
ln -sf "$INSTALL_DIR/blucommand-run" "$SYMLINK_TARGET"
echo -e "${GREEN}Symlink created: ${SYMLINK_TARGET}${RESET}"

# Check if ~/local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo -e "${YELLOW}Warning: ${BIN_DIR} is not in your PATH.${RESET}"
    echo -e "${CYAN}Add this to your ~/.zshrc or ~/.bashrc:${RESET}"
    echo -e "${BOLD}export PATH=\"\$HOME/local/bin:\$PATH\"${RESET}"
    echo ""
fi

# Summary
echo ""
if [ "$IS_UPDATE" = true ]; then
    echo -e "${GREEN}${BOLD}Update complete!${RESET}"
    echo -e "${DIM}Files updated, existing configuration preserved.${RESET}"
else
    echo -e "${GREEN}${BOLD}Installation complete!${RESET}"
fi
echo ""
echo -e "${CYAN}Installation directory:${RESET} ${INSTALL_DIR}"
echo -e "${CYAN}Configuration file:${RESET} ${CONFIG_FILE}"
if [ "$IS_UPDATE" = true ]; then
    echo -e "${DIM}  (existing configuration preserved)${RESET}"
fi
echo -e "${CYAN}Binary symlink:${RESET} ${SYMLINK_TARGET}"
echo ""
echo -e "${BOLD}Usage:${RESET}"
echo "  $BIN_NAME discover"
echo "  $BIN_NAME status"
echo "  $BIN_NAME status --scan"
echo "  $BIN_NAME volume 20"
echo ""
echo -e "${CYAN}For more commands, run:${RESET} $BIN_NAME --help"
echo ""
echo -e "${CYAN}Note:${RESET} Make sure ~/local/bin is in your PATH:"
echo -e "${BOLD}export PATH=\"\$HOME/local/bin:\$PATH\"${RESET}"
echo ""

