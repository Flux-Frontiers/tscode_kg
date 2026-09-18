# Release Notes -- v0.5.1

> Released: 2026-09-17

`tscodekg analyze` now produces a report for a graph that has no vector index.
Before this release, running `analyze` after `build-sqlite` -- a supported
combination, since `build-sqlite` deliberately skips the index -- printed an
internal database error naming a table the user had never heard of, and wrote
no report at all.

## What changed

**One failing phase no longer costs the whole report.** The analysis runs
fourteen phases. Only one of them, fan-out, needs the semantic index; the
other thirteen read the SQLite graph directly. Each phase now runs on its own
terms: a failure is recorded and the run continues, so the same command that
used to produce nothing now produces a complete report minus one section.

**A degraded report says it is degraded.** Both the printed output and the
`--report` file carry an *Incomplete Analysis* section naming each phase that
could not run, the reason, and the command that fixes it. When the missing
piece is the semantic index, it says so and points at `tscodekg build`. An
empty section with no explanation would read as a finding about your code
rather than as a build step you skipped.

**That hint survives the new SDK.** `kgmodule-utils` 0.22.0 reports a missing
vector store with a clearer, typed error than the raw database message it
replaced. The notice was matching the old text, so with the new SDK it would
have stopped appearing. It now recognises both.

**Current dependencies.** `kgmodule-utils` is now required at `>=0.22.0`, the
fleet's current release.

## Upgrading

Nothing to do beyond upgrading the package. Existing graphs, vector indexes
and snapshots are read as before. If an analysis report now lists an
incomplete phase, run `tscodekg build` to create the semantic index and
re-run `tscodekg analyze`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
