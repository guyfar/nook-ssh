# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog.

## [Unreleased]

### Added

- Two-step server creation from an SSH address or command, with optional fields under `nk add --advanced`.
- Direct connection for an exact, unique server name and first-run guidance into the add flow.
- Isolated behavior tests for selection, authentication arguments, input validation, and existing configs.

### Fixed

- Empty passwords no longer shift picker fields or pass the `key` label as a password.
- The numbered fallback displays its choices without mixing screen output with connection data.
- Notes are searchable, picker errors are visible, and cancellation exits cleanly.
- New duplicate names, invalid ports, and malformed config fields are rejected with actionable errors.
- Removing a selected entry preserves other entries with the same name.
- The installer honors `NOOK_CONFIG_DIR`, including skipping legacy migration for an explicit directory.

### Changed

- Simplified the picker to one list, with details hidden until Tab is pressed and only usable controls in the header.
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
