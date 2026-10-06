# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog.

## [Unreleased]

### Added

- Aligned name, group, and full connection-target columns, plus a scrollable preview with the equivalent manual SSH command.
- A semantic, truecolor picker theme (Tokyo Night) with per-column colour, a rounded frame, a `DETAILS` side pane on wide terminals that collapses to a bottom pane on narrow ones, and colour-free fallback output for pipes or `NO_COLOR`.
- `nk list` shares the same aligned, colour-coded table as the picker.
- Relative "last used" times from timestamped history, plus a cached reachability column. `nk ping` writes the cache and picker `ctrl-r` refreshes it in place; stale readings are marked with `*`.
- A picker action bar that keeps you in the picker: `ctrl-e` shows details in the preview pane, `ctrl-p` pings one server, `ctrl-y` copies the SSH command, `ctrl-k` installs key login, and `ctrl-d` removes after a confirmation, all acting on the highlighted server. The list refreshes in place and the hint line adapts to the terminal width.
- Interactive correction of individual add fields without discarding valid inputs; piped input continues to fail immediately on invalid data.
- Two-step server creation from an SSH address or command, with optional fields under `nk add --advanced`.
- Direct connection for an exact, unique server name and first-run guidance into the add flow.
- Isolated behavior tests for selection, authentication arguments, input validation, and existing configs.

### Fixed

- Key setup preserves underlying errors and failure exit codes, with a command for checking login.
- Port checks report direct TCP reachability rather than server online/offline status, including missing dependencies and failure exit codes.
- Saved-password prompts disable terminal echo before appearing and restore it after input or cancellation.
- Empty passwords no longer shift picker fields or pass the `key` label as a password.
- The numbered fallback displays its choices without mixing screen output with connection data.
- Notes are searchable, picker errors are visible, and cancellation exits cleanly.
- New duplicate names, invalid ports, and malformed config fields are rejected with actionable errors.
- Removing a selected entry preserves other entries with the same name.
- The installer honors `NOOK_CONFIG_DIR`, including skipping legacy migration for an explicit directory.

### Changed

- Simplified the picker to one list, with details hidden until Tab is pressed and only usable controls in the header.
- The picker degrades gracefully: fzf capabilities are probed individually, and CJK columns stay aligned because cells are width-aligned before colour is applied.
- The history file now stores `name<TAB>epoch`; legacy name-only history is still read and upgraded on the next connection.
- Removed repeated logos from everyday commands and shortened both READMEs around common tasks.
- Kept credentials out of picker input; selection resolves a record ID against the loaded catalog.
- Documented and tested compatibility with macOS Bash 3.2.

## [1.1.0] - 2026-03-22

### Added

- Introduced the `Nook` brand and the new primary command `nk`.
- Added a branded ASCII logo, help output, and TUI framing.
- Added automatic migration from `~/.ssh-manager` to `~/.config/nook`.
- Added `nk doctor` for environment diagnostics.
- Added OSS project metadata files: `LICENSE`, `CONTRIBUTING.md`, and `RELEASE_CHECKLIST.md`.

### Changed

- Replaced the old one-letter entrypoint with `nk` as the only supported command.
- Updated installer and README to reflect the new brand and config layout.
- Reworked config editing logic to avoid the previous macOS-only `sed -i ''` approach.
