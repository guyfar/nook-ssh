#!/usr/bin/env bash
# ============================================
# Nook - installer
# Supports local install and remote bootstrap
# ============================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

REPO="${NOOK_REPO:-guyfar/nook-ssh}"
BRANCH="${NOOK_BRANCH:-main}"
RAW_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
INSTALL_DIR="${NOOK_INSTALL_DIR:-/usr/local/bin}"
PRIMARY_BIN="nk"
XDG_CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_DIR="${NOOK_CONFIG_DIR:-$XDG_CONFIG_ROOT/nook}"
CONFIG_FILE="$CONFIG_DIR/servers.conf"
LEGACY_CONFIG_DIR="$HOME/.ssh-manager"
# Apple Silicon Mac 优先用 /opt/homebrew/bin
if [[ -z "${NOOK_INSTALL_DIR:-}" && -d "/opt/homebrew/bin" ]]; then
    INSTALL_DIR="/opt/homebrew/bin"
fi

print_logo() {
    echo -e "${CYAN}${BOLD}"
    cat <<'EOF'
    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|
EOF
    echo -e "${NC}${DIM}  SSH jumpbox for humans${NC}"
}

write_default_config() {
    cat > "$CONFIG_FILE" <<'CONF'
# ============================================
# Nook - server catalog
# ============================================
# Format : name | host | port | user | password(optional) | description
# Group  : lines like [group-name]
# Notes  : password empty uses standard SSH authentication
# ============================================

[default]
# prod-web-01 | 1.2.3.4 | 22 | root | yourpass | production web node
CONF
}

install_file() {
    local src="$1" dest="$2"
    if [[ -w "$INSTALL_DIR" ]]; then
        cp "$src" "$dest"
        chmod +x "$dest"
    else
        sudo cp "$src" "$dest"
        sudo chmod +x "$dest"
    fi
}

ensure_install_dir() {
    if [[ -d "$INSTALL_DIR" ]]; then
        return 0
    fi

    if mkdir -p "$INSTALL_DIR" 2>/dev/null; then
        return 0
    fi

    sudo mkdir -p "$INSTALL_DIR"
}

print_logo
echo ""

# --- 判断是本地安装还是远程安装 ---
SCRIPT_DIR=""
if [[ -f "$(dirname "$0")/nk" ]] 2>/dev/null; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

# --- Step 1: install primary binary ---
echo -e "${DIM}[1/4] install ${PRIMARY_BIN} into ${INSTALL_DIR}/${PRIMARY_BIN} ...${NC}"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

ensure_install_dir

if [[ -n "$SCRIPT_DIR" ]]; then
    cp "${SCRIPT_DIR}/nk" "$TMP_DIR/nk"
else
    echo -e "${DIM}  download from GitHub...${NC}"
    curl -fsSL "${RAW_URL}/nk" -o "$TMP_DIR/nk"
fi

chmod +x "$TMP_DIR/nk"
install_file "$TMP_DIR/nk" "${INSTALL_DIR}/nk"
echo -e "${GREEN}  [ok] primary command installed: ${PRIMARY_BIN}${NC}"

# --- Step 2: 检查 fzf 和 sshpass ---
echo -e "${DIM}[2/4] check fzf ...${NC}"
if command -v fzf &>/dev/null; then
    echo -e "${GREEN}  [ok] fzf is installed${NC}"
else
    echo -e "${YELLOW}  [warn] fzf is not installed${NC}"
    if command -v brew &>/dev/null; then
        read -r -p "  Install fzf now? [Y/n]: " install_fzf
        if [[ ! "$install_fzf" =~ ^[nN] ]]; then
            brew install fzf
            echo -e "${GREEN}  [ok] fzf installed${NC}"
        fi
    else
        echo -e "${DIM}  install manually: brew install fzf${NC}"
        echo -e "${DIM}  Nook works without it, but the picker is better with fzf${NC}"
    fi
fi

# --- Step 3: 检查 sshpass ---
echo -e "${DIM}[3/4] check sshpass ...${NC}"
if command -v sshpass &>/dev/null; then
    echo -e "${GREEN}  [ok] sshpass is installed${NC}"
else
    echo -e "${YELLOW}  [warn] sshpass is not installed (only needed for password login)${NC}"
    if command -v brew &>/dev/null; then
        read -r -p "  Install sshpass now? [Y/n]: " install_sshpass
        if [[ ! "$install_sshpass" =~ ^[nN] ]]; then
            brew install hudochenkov/sshpass/sshpass 2>/dev/null || \
            brew install esolitos/ipa/sshpass 2>/dev/null || \
            echo -e "${YELLOW}  automatic install failed, please install it manually${NC}"
        fi
    fi
fi

# --- Step 4: 初始化配置 ---
echo -e "${DIM}[4/4] initialize config ...${NC}"
mkdir -p "$CONFIG_DIR"
if [[ -z "${NOOK_CONFIG_DIR:-}" && -f "${LEGACY_CONFIG_DIR}/servers.conf" && ! -f "$CONFIG_FILE" ]]; then
    cp "${LEGACY_CONFIG_DIR}/servers.conf" "$CONFIG_FILE"
    [[ -f "${LEGACY_CONFIG_DIR}/.history" ]] && cp "${LEGACY_CONFIG_DIR}/.history" "${CONFIG_DIR}/.history"
    echo -e "${GREEN}  [ok] migrated existing config from ${LEGACY_CONFIG_DIR}${NC}"
elif [[ ! -f "$CONFIG_FILE" ]]; then
    write_default_config
    echo -e "${GREEN}  [ok] created config: ${CONFIG_FILE}${NC}"
else
    echo -e "${GREEN}  [ok] config already exists: ${CONFIG_FILE}${NC}"
fi
chmod 600 "$CONFIG_FILE"

echo ""
echo -e "${GREEN}${BOLD}[ok] install complete${NC}"
echo ""
echo -e "${BOLD}Quick start${NC}"
echo -e "  1. Add a server:       ${CYAN}${PRIMARY_BIN} add${NC}"
echo -e "  2. Pick and connect:   ${CYAN}${PRIMARY_BIN}${NC}"
echo -e "  3. Configure SSH key:  ${CYAN}${PRIMARY_BIN} key${NC}"
echo -e "  4. Run diagnostics:    ${CYAN}${PRIMARY_BIN} doctor${NC}"
echo -e "  5. Help:               ${CYAN}${PRIMARY_BIN} help${NC}"
echo ""
echo -e "${DIM}Config path: ${CONFIG_FILE}${NC}"
