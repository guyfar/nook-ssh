# Nook (`nk`)

[中文](./README.zh-CN.md)

> SSH jumpbox for humans.

Nook is a polished SSH bookmark manager for people who spend real time in the terminal. It keeps server access fast and organized without turning your workflow into a heavyweight dashboard.

You get a branded picker, recent-server pinning, grouped entries, key setup, reachability checks, diagnostics, and a clean migration path from the original `ssh-manager` layout.

中文说明见 `README.zh-CN.md`.

## Why Nook

- Clean primary command: `nk`
- Single-file Bash implementation with minimal operational overhead
- Fast interactive picker powered by `fzf`
- Server catalog with groups, notes, and recent-history pinning
- Built-in key setup, reachability checks, and diagnostics
- Automatic migration from `~/.ssh-manager` to `~/.config/nook`

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/guyfar/nook-ssh/main/install.sh | bash
nk add
nk
```

By default Nook stores data in:

```text
~/.config/nook/
```

If an existing `~/.ssh-manager/` config is present, Nook imports it automatically.

## Experience

Nook is designed to feel like a proper terminal product, not just a helper script:

- Branded TUI with preview pane and keyboard-first flow
- Recent servers stay pinned at the top of the picker
- Password and key-based authentication handled in one place
- Config stays human-readable and easy to version or back up

## Commands

| Command | Description |
|------|------|
| `nk` | Open the interactive picker |
| `nk add` | Add a server |
| `nk rm` | Remove a server |
| `nk list` | List all configured servers |
| `nk edit` | Edit the config file |
| `nk key` | Configure SSH key login |
| `nk ping` | Check server reachability |
| `nk doctor` | Show environment diagnostics |
| `nk <keyword>` | Search and connect directly |
| `nk version` | Show version |
| `nk help` | Show help |

## Configuration

Default config file:

```text
~/.config/nook/servers.conf
```

Optional override:

```bash
export NOOK_CONFIG_DIR=/path/to/custom-config-dir
```

Config format:

```conf
# Format : name | host | port | user | password(optional) | description

[production]
# prod-web-01 | 1.2.3.4 | 22   | root | yourpass  | production web node
# prod-web-02 | 1.2.3.5 | 22   | root |           | production web node 2
# prod-db-01  | 1.2.3.6 | 3306 | root | dbpass123 | primary database
```

Empty password means Nook will use SSH key login.

## SSH Key Setup

```bash
nk key
```

Nook detects an existing SSH public key automatically. If none exists, it generates an `ed25519` key and pushes it with `ssh-copy-id`.

## Dependencies

- `bash` 4.0+
- `fzf` optional, recommended
- `sshpass` optional, only needed for password-based login

```bash
# macOS
brew install fzf

# Debian / Ubuntu
sudo apt install fzf

# CentOS / RHEL
sudo yum install fzf
```

## Diagnostics

```bash
nk doctor
```

Use `nk doctor` when installation or connection reports need to be debugged. It prints version, config paths, server count, and dependency availability for `ssh`, `fzf`, and `sshpass`.

## Development

```bash
# syntax check
bash -n nk install.sh

# help
./nk help

# local install into temp directories
NOOK_INSTALL_DIR=/tmp/nook-bin XDG_CONFIG_HOME=/tmp/nook-xdg bash ./install.sh
```

Project workflow details live in `CONTRIBUTING.md`, `CHANGELOG.md`, and `RELEASE_CHECKLIST.md`.

## Uninstall

```bash
sudo rm /usr/local/bin/nk
rm -rf ~/.config/nook
rm -rf ~/.ssh-manager
```

## License

MIT
