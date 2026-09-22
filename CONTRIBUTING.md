# Contributing

Thanks for contributing to Nook.

## Development Principles

- Keep the project lightweight and dependency-minimal.
- Prefer portable Bash over shell tricks that only work on one platform.
- Treat `nk` as the primary user-facing command.

## Local Checks

Run these before opening a PR:

```bash
bash -n nk install.sh
python3 -m unittest discover -s tests -v
./nk help
./nk version
NOOK_INSTALL_DIR=/tmp/nook-bin NOOK_CONFIG_DIR=/tmp/nook-config bash ./install.sh
```

Tests use temporary catalogs and fake SSH commands, with real fzf filtering when
fzf is installed. They do not connect to real servers. Python 3 is only a test dependency.

## Style Notes

- Use ASCII unless a file already relies on Unicode.
- Keep output concise and readable in narrow terminals.
- Prefer explicit, predictable shell code over clever one-liners.

## Pull Requests

- Explain the user-facing change.
- Mention any compatibility impact.
- Include manual verification steps if behavior changed.
