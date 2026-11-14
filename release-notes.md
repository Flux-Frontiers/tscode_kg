# Release Notes -- v0.8.2

> Released: 2026-11-14

TSCodeKG 0.8.2 fixes how calls are counted. A CALLS edge always pointed at a
function in the calling file, so anything used only from another module, and
every React component used only as JSX, had no callers and was reported as
an orphan. On a 93-module React app, orphaned declarations fall from 294 to
54.

## What changed

**Calls across files are resolved.** A call to a name bound by a relative
import (named, aliased or default) now points at the function in the file
that defines it.

**JSX elements count as calls.** `<Badge />` is a CALLS edge to `Badge`.
Lowercase intrinsic tags such as `<div>` are not.

**Extensionless imports find `.tsx` and `index` files.** `./Card` resolved
to `Card.ts` even when only `Card.tsx` exists, leaving the IMPORTS edge
pointing at nothing.

**The analysis report states the configured scope.** `tscodekg analyze`
printed "Included directories: all" regardless of `[tool.tscodekg]`. It now
reads `include` and `exclude` from pyproject.toml.

## Known limits

Calls at module top level (outside any function), such as
`root.render(<App />)`, and components passed as values, such as
`{ flame: FlameOfKnowledge }`, still produce no CALLS edge.

## Upgrading

`pip install -U tscode-kg`, then rebuild with `tscodekg build` so existing
graphs pick up the new edges. No command or tool changes.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
