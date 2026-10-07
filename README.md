# Nook (`nk`)

[中文](./README.zh-CN.md)

Save SSH servers, search, and press Enter to connect. A single-file Bash tool with groups, notes, and recent-server ordering.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/guyfar/nook-ssh/main/install.sh | bash
nk add
nk
```

Adding a server takes two inputs: its address and a name. Enter `ubuntu@example.com` or paste `ssh ubuntu@example.com -p 2222`. The default port is `22`; an omitted username keeps the existing `root` default.

You can also pass an address and then confirm its name:

```bash
nk add ubuntu@example.com
nk add 'ssh ubuntu@example.com -p 2222'
```

Supported input: `[user@]host`, IPv6, and the `-p` and `-l` options. Other SSH options and remote commands are rejected explicitly. Pasted input is never evaluated as a shell command.

In a terminal, an invalid address, port, or name prompts you to correct that field while keeping the other inputs. Piped input fails immediately on errors rather than consuming later values as corrections.

## Everyday use

- `nk`: search names, hosts, usernames, groups, or notes. Recently used servers appear first.
- `nk <name>`: connect immediately when the name matches exactly one entry; otherwise open the picker.
- In the picker, actions run on the highlighted server: **Enter** connect, **alt-e** edit, **alt-d** remove, **alt-k** configure key login, **alt-p** check reachability, **alt-c** copy the SSH command, **alt-r** refresh status, **Tab** toggle details, **Esc** close details or cancel.
- Actions keep you in the picker and use `alt-` keys so fzf's own navigation (`ctrl-j`/`ctrl-k`, `ctrl-n`/`ctrl-p`, `ctrl-y`) keeps working. The action bar adapts to the terminal width.
- Columns show the name, group, full `user@host:port`, note, how long ago it was last used, and reachability. Details add login method, status, and a manual SSH command; use **Alt+Up/Down** to scroll.
- Status comes from the last `nk ping` and is never checked on startup, so the picker stays fast. A trailing `*` means the reading is over an hour old. Press **ctrl-r** in the picker, or run `nk ping`, to refresh it.
- When a connection fails in a terminal, Nook offers a small menu (`p` ping, `k` key login, `e` edit, `c` copy command) instead of exiting silently.
- Without `fzf`, choose a numbered entry or press Enter to cancel.
- Running `nk` in a terminal with an empty catalog starts the add flow.

SSH handles keys, ssh-agent, or password prompts by default. No saved password is required.

For a group, note, or saved password, use:

```bash
nk add --advanced
```

Saved passwords are stored as plain text in the local config, with file permissions set to `600`. Automatically filling a saved password requires `sshpass`; without it, Nook uses normal SSH login.

## Other commands

| Command | Description |
|---------|-------------|
| `nk list` | List servers with last used and status |
| `nk rm` | Choose and confirm removal of a server |
| `nk edit` | Edit the config with `$EDITOR`, defaulting to Vim |
| `nk key` | Choose a server and configure SSH key login |
| `nk ping` | Check server port reachability |
| `nk doctor` | Show environment diagnostics |
| `nk version` | Show version |
| `nk help` | Show help |

`nk ping` checks direct TCP reachability from this machine to the configured addresses and ports. It does not verify SSH login or use SSH jump hosts or proxies. Missing `nc` is reported explicitly, and any unreachable port results in a nonzero exit status. Results are cached and shown in the picker and `nk list` until the next check.

When `nk key` fails, Nook preserves the original SSH error and exit status and shows a command for checking login.

## Configuration

The default file is `~/.config/nook/servers.conf`. `XDG_CONFIG_HOME` is supported, or set an explicit directory:

```bash
export NOOK_CONFIG_DIR=/path/to/custom-config-dir
```

The existing config format is unchanged:

```conf
# name | host | port | user | password(optional) | description
[production]
web-prod | 192.0.2.10 | 22 | ubuntu | | production web server
```

New names must be unique. Ports must be `1–65535`; fields cannot contain `|`, tabs, or line breaks. Invalid manually edited entries report their file location instead of being skipped silently. Existing duplicate names always require selection rather than connecting directly.

An existing `~/.ssh-manager/` catalog is migrated automatically unless `NOOK_CONFIG_DIR` is set.

## Dependencies and development

- Bash 3.2+, OpenSSH, and common Unix utilities.
- `fzf`: optional, for interactive search.
- `column`: optional, for aligned columns including CJK names. Selection and connection still work without it.
- `sshpass`: optional, for automatically filling saved passwords.
- `ssh-copy-id`: only for key setup; `nc`: only for reachability checks.

```bash
bash -n nk install.sh
python3 -m unittest discover -s tests -v
./nk help
./nk doctor
```

Tests use temporary catalogs and fake SSH commands; they never connect to real servers. Python is needed only for tests, not for using Nook.

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) for the project workflow.

## License

MIT
