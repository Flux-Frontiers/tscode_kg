# Release Notes -- v0.7.0

> Released: 2026-09-26

A snapshot saved without a VERSION now records the version of the repo it
measured, not the version of `tscode-kg`.

## What changed

**Snapshots name the subject's version.** `tscodekg snapshot save` with no
VERSION reads the repo's version from its root `package.json`, then from
`CITATION.cff`, and falls back to the installed package only when neither
declares one. Before, a snapshot of `knowledge_press` 1.23.0 recorded 0.6.0.
The measuring tool's version stays in `tool_version`, and the key is still a
UTC timestamp; only an explicit VERSION becomes the key.

## Upgrading

Nothing to rebuild. Existing snapshots are unchanged. Release snapshots should
still pass the version explicitly, as before.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
