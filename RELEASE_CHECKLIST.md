# Release Checklist

Use this before publishing a new Nook release.

## Branding

- Confirm the project name is consistently `Nook`.
- Confirm `nk` is the documented primary command.
- Capture at least one fresh terminal screenshot or demo GIF.

## Repository

- Confirm the GitHub repository name is `nook-ssh`.
- Confirm these files point to `guyfar/nook-ssh`:
  - `README.md`
  - `README.zh-CN.md`
  - `install.sh`
  - `.github/ISSUE_TEMPLATE/config.yml`
- Verify the repository description and topics match the new brand.
- Add a short project description on GitHub: `SSH jumpbox for humans`.

## Quality

- Run `bash -n nk install.sh`
- Run `python3 -m unittest discover -s tests -v`
- Run `./nk help`
- Run `./nk doctor`
- Test install flow with:

```bash
NOOK_INSTALL_DIR=/tmp/nook-bin NOOK_CONFIG_DIR=/tmp/nook-config bash ./install.sh
```

- Test both:
  - first-run empty config
  - migration from an existing `~/.ssh-manager`

## Release Notes

- Update `CHANGELOG.md`
- Tag a version
- Draft concise release notes with:
  - what changed
  - migration notes
  - any command or config path changes
