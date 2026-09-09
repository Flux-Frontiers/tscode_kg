# Release Notes — v0.5.0

> Released: 2026-09-08

A small maintenance release: the snapshot manager sheds a redundant override,
and the fleet-shared tooling floors it depends on move up to the releases
that made that override unnecessary in the first place.

## What changed

**The snapshot manager is now one class attribute.** `SnapshotManager`
previously carried an `__init__` whose entire body forwarded to `super()`
just to set one string. `kgmodule-utils` 0.20.0 reads `package_name` directly
off the class, so the constructor override is gone and `snapshots.py` drops
from 68 lines to 55. Seven of the fleet's eight KG modules carried the same
now-unnecessary override.

**The `kgmodule-utils` floor moves to `>=0.20.0`**, a hard requirement rather
than a preference: against 0.19.x the base class has no `package_name`
attribute, so every snapshot's `tool` field would silently read `"kg-utils"`
instead of `"tscode-kg"`.

**The `doc-kg` and `pycode-kg` floors move to 0.26.0 and 0.27.0**, the
releases that retired those packages' own equivalent snapshot overrides.
`poetry install --with kg` can no longer resolve a `dockg` or `pycodekg`
predating the shared extension point this repo now depends on.

## Upgrading

Reinstall with `poetry install --with dev` (or `--with kg` if you use the
snapshot tooling) to pick up the raised floors. No CLI flags or config
changed.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
