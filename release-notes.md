# Release Notes -- v0.8.1

> Released: 2026-11-02

TSCodeKG 0.8.1 is a security release. The `viz` extra capped Streamlit below
1.60, and every Streamlit before 1.66.1 caps Pillow below 13, so an install
with `viz` was held on Pillow 12.3.0 and its 41 advisories, some of them
critical. The cap now allows Streamlit 1.66, which allows Pillow 13. Nothing
else changes.

## What changed

**The `viz` extra allows Streamlit 1.66.** The range is now
`streamlit>=1.59.0,<1.67`. The floor is unchanged; only the cap moved, far
enough to reach the first Streamlit that accepts a patched Pillow. The
Streamlit app was checked under 1.66.1.

**The lock is refreshed.** Pillow 13.0.0, Streamlit 1.66.1, certifi,
filelock, setuptools and virtualenv move to patched releases, which clears
every open Dependabot alert.

## Upgrading

`pip install -U "tscode-kg[viz]"` moves Streamlit and Pillow forward. No
command, tool or index changes, so existing graphs stay valid.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
