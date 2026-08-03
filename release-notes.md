# Release Notes — v0.3.0

> Released: 2026-08-03

Nothing under `src/` changed. What changed is what this package *claims* about
its sibling knowledge graphs — and it had the two halves exactly backwards.

## The dependency it has was undeclared; the one it doesn't have was published

`.git/hooks/pre-commit` runs `pycodekg build` against this repo on every commit.
`pycode-kg` was declared nowhere. In its place, `pyproject.toml` carried a
standing workaround:

```bash
poetry run pip install pycode-kg     # the old advice
```

Meanwhile a published `kgdeps` extra declared `doc-kg` — which TypeScriptKG
never imports and never invokes. The only trace of DocKG anywhere in the repo
is the literal string `".dockg"` in an exclusion list.

So consumers of `tscode-kg[kgdeps]` were installing a package this project has
no relationship with, while contributors had to know an undocumented manual step
to make the commit hook work.

## Why the workaround existed, and why it's gone

The manual-install advice was not arbitrary. Declaring `pycode-kg` used to force
Poetry to reconcile its `transformers` pin against this project's own, and the
constraints genuinely deadlocked: `kgmodule-utils>=0.9.0` needs
`transformers>=5.5.0,<6`, while pycode-kg 0.20.0 capped `transformers<4.57`. The
old `pycode-kg>=0.20.0,<0.21` ceiling had been quietly holding this repo on the
**pre-CVE `transformers` line**.

That constraint no longer exists. pycode-kg 0.21.4 doesn't pin `transformers` at
all — it inherits `kgmodule-utils[semantic]>=0.10.0`, the same source this
project already uses. This was verified rather than assumed: locking with the
new group resolves cleanly and leaves `transformers` at **5.14.1, unchanged**.

## What replaces both

A Poetry group. Groups are locked and installable, but are never written into
wheel metadata — so contributors get the CLIs and consumers get nothing extra:

```bash
poetry install --with kg      # dockg + pycodekg CLIs into .venv/bin
poetry install                # default — group is optional, skipped
```

`doc-kg` rides along so that `poetry install --with kg` means the same thing in
every repo across the KG fleet. TypeScriptKG has no DocKG index today, so the
CLI is simply available rather than required — and it lives in the group, not an
extra, precisely because nothing depends on it at runtime.

## Upgrading

If you install `tscode-kg`, `tscode-kg[kg]`, `tscode-kg[viz]` or
`tscode-kg[viz3d]`, nothing changes.

If you were installing **`tscode-kg[kgdeps]`**, that extra no longer exists. You
almost certainly wanted the contributor setup: clone the repo and run
`poetry install --with kg`. Nothing in the fleet referenced it.

If you are a contributor who followed the old `poetry run pip install pycode-kg`
advice, you can stop — `poetry install --with kg` now does it, and pins a
version.

See [CHANGELOG.md](CHANGELOG.md) for the itemised list.
