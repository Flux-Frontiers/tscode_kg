# Release Notes — v0.4.0

> Released: 2026-09-06

Snapshots saved by this package were never actually retrievable. This release
fixes the root cause, adds two new build commands that bring the CLI in line
with the rest of the fleet, and removes a flag whose default direction was
backwards.

## What changed

**Snapshots were keyed on a hash that never matched anything committed.**
`snapshot save VERSION` accepted a version tag but silently threw it away:
`Snapshot.key` fell back to the git tree hash, and that hash was read before
`git add` staged the snapshot file, so it named a tree that was never actually
committed. A snapshot saved this way could not be looked up again by tag, by
timestamp, or by any value a caller could reasonably guess. `snapshot save`
now passes the version through as the key and takes a new `--subject` option
naming what was measured (for example `repo:tscode-kg`), separate from the
tool that measured it. The pre-commit hook needed no changes: it has never
passed a version, so its automatic captures now key correctly on a UTC
timestamp instead of an unresolvable hash. Snapshots saved under the old
scheme stay readable under the key they were stored with. `docs/SNAPSHOTS.md`,
`docs/CHEATSHEET.md`, `docs/MCP.md`, and this repo's `README.md` described the
broken scheme as the intended design and are corrected to match.

**`tscodekg build` now always wipes**, matching `pycodekg build`, `dockg
build`, and `memorykg build` elsewhere in the fleet. The old default was an
incremental upsert, the one CLI in the fleet where a plain `build` left stale
data behind instead of starting clean. The opt-in `--wipe` flag this replaces
is gone; a new `tscodekg update` command carries the incremental behavior for
anyone who relied on it, and `build-sqlite` / `build-index` expose the two
build stages as named commands for anyone who was using `build --graph-only`
or `build --index-only`.

**Dependency floors moved up to the packages this project is tested
against**: `kgmodule-utils` to `0.19.1`, `doc-kg` to `0.24.1`, and `pycode-kg`
to `0.26.0`. The `kgmodule-utils` floor had sat at `0.18.0` since this
project's first release, several versions behind the shared snapshot fix
above required to land.

**Dev tooling moved from a `dev` extra to an optional Poetry group.** It no
longer ships in the wheel and can no longer be installed with `pip`. Use
`poetry install --with dev` instead.

A separate documentation pass corrected 24 sites referencing the removed
`--wipe` flag and fixed `docs/INSTALLATION.md`, which listed `kg` and `dev` as
installable extras (`kg` is a Poetry group; `dev` no longer exists as either)
and recommended a PyVista Jupyter extra this project deliberately avoids.

## Upgrading

Scripts that pass `tscodekg build --wipe` should drop the flag; `build` wipes
by default now. Scripts that relied on the old incremental default should
call `tscodekg update` instead. Bump the `kgmodule-utils`, `doc-kg`, and
`pycode-kg` floors in any environment that pins them below the versions
above, and reinstall dev tooling with `poetry install --with dev` if it was
installed via the old extra.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
