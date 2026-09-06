# TypeScriptKG Temporal Snapshots

**Enterprise-Grade Metrics Tracking Across Commits**

Capture, store, and compare codebase metrics over time. Track the evolution of complexity, coverage, and health signals from version to version.

---

## Overview

Snapshots are point-in-time captures of your codebase's metrics, tagged with:
- **Key** — a release tag you pass explicitly (`0.4.0`), or a UTC timestamp when
  you omit one. Never a git tree hash: that hash is read before `git add`
  stages the snapshot, so it names a tree that is never committed and cannot be
  resolved afterward.
- **Subject** — what was measured, e.g. `repo:tscode-kg`; separate from the
  version, which names the measuring tool.
- **Tree hash** — recorded as provenance, not the key; auto-detected from
  `git write-tree` when not provided.
- **Branch name** — to distinguish release vs. develop metrics
- **Version string** — semantic versioning (0.1.0, 1.0.0, etc.); auto-detected from the installed `tscode-kg` package when omitted
- **Timestamp** — ISO 8601 UTC for auditability
- **Full metrics** — nodes, edges, coverage, complexity, hotspots

Snapshots in `.tscodekg/snapshots/` are **tracked in git** — the pre-commit hook stages each snapshot file automatically so it ships with the commit that produced it.

Each snapshot includes **automatic delta computation** against the previous snapshot and a baseline snapshot, showing trends over time.

---

## Quick Start

### Capture a Snapshot
```bash
tscodekg snapshot save 0.1.0 --subject repo:tscode-kg
```

Automatically detects your current git commit and branch. Creates
`.tscodekg/snapshots/0.1.0.json`, keyed on the `VERSION` you pass. Omit
`VERSION` and the key is a UTC timestamp instead — the right answer for the
per-commit hook below, which has no release tag to give it. `--tree-hash` is
still accepted and still auto-detected, but only as provenance.

### List All Snapshots
```bash
tscodekg snapshot list
```

Shows all snapshots in reverse chronological order:
```
Key          Timestamp            Branch       Version   Nodes  Edges  Coverage
0.1.1        2026-07-07 17:25     develop      0.1.1     1240   2380   62.0%
0.1.0        2026-07-05 09:10     main         0.1.0     1240   2380   62.0%
0.1.0-dev1   2026-07-01 14:02     develop      0.1.0-dev 1180   2270   58.2%
```

### Show Snapshot Details
```bash
tscodekg snapshot show 0.1.1
```

Displays full metrics, hotspots, and deltas:
```
Key:       0.1.1
Branch:    develop
Timestamp: 2026-07-07T17:25:29Z
Version:   0.1.1

Metrics:
  Total Nodes:       1240
  Total Edges:       2380
  JSDoc Coverage:    62.0%
  Critical Issues:   0

Delta vs. Previous:
  Nodes:    +60
  Edges:    +110
  Coverage: +3.8%
  Issues:   0
```

### Compare Two Snapshots
```bash
tscodekg snapshot diff 0.1.0 0.1.1
```

Side-by-side comparison showing what changed:
```
Comparing 0.1.0 vs 0.1.1

Metric                   A             B             Δ
total_nodes              1180          1240          +60
total_edges              2270          2380          +110
docstring_coverage       58.2%         62.0%         +3.8%
critical_issues          1             0             -1
```

### Prune Old Snapshots
```bash
tscodekg snapshot prune --dry-run   # preview what would be removed
tscodekg snapshot prune             # remove them
```

---

## Architecture

### Storage Structure
```
.tscodekg/
├── graph.sqlite          # Knowledge graph database
├── vectors.sqlite        # sqlite-vec semantic embeddings
└── snapshots/
    ├── manifest.json      # Index of all snapshots
    ├── 0.1.0.json         # Snapshot keyed on the release tag
    ├── 0.1.1.json
    └── 2026-09-06T....json  # A corpus/hook capture with no tag: UTC timestamp
```

### Manifest Index
```json
{
  "format": "1.0",
  "last_update": "2026-07-07T17:25:29Z",
  "snapshots": [
    {
      "key": "0.1.1",
      "subject": "repo:tscode-kg",
      "tool": "tscode-kg",
      "tool_version": "0.4.0",
      "branch": "develop",
      "timestamp": "2026-07-07T17:25:29Z",
      "version": "0.1.1",
      "file": "0.1.1.json",
      "metrics": {
        "nodes": 1240,
        "edges": 2380,
        "coverage": 0.62,
        "critical_issues": 0
      },
      "deltas": {
        "vs_previous": {
          "nodes": 60,
          "edges": 110,
          "coverage_delta": 0.038,
          "critical_issues_delta": -1
        },
        "vs_baseline": {
          "nodes": 60,
          "edges": 110,
          "coverage_delta": 0.038,
          "critical_issues_delta": -1
        }
      }
    }
  ]
}
```

### Snapshot Schema
Each snapshot captures:

**Metrics**
- `total_nodes` — Total nodes in graph (including `sym:` stubs)
- `meaningful_nodes` — Nodes excluding import stub infrastructure
- `total_edges` — Total edges in graph
- `node_counts` — Breakdown by kind (module, class, interface, type_alias, enum, namespace, function, method, symbol)
- `edge_counts` — Breakdown by relation (CALLS, CONTAINS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS)
- `docstring_coverage` — Fraction of entities with JSDoc comments (0.0–1.0)
- `critical_issues` — Count of critical issues found by the analyzer
- `complexity_median` — Median fan-in across functions

**Deltas**
- `vs_previous` — Changes from previous snapshot
- `vs_baseline` — Changes from oldest (baseline) snapshot

---

## Usage Patterns

### Release Management
Track metrics at each version release:

```bash
# After tagging v0.1.1
tscodekg snapshot save 0.1.1

# After tagging v0.1.2
tscodekg snapshot save 0.1.2

# Compare releases
tscodekg snapshot diff 0.1.1 0.1.2
```

### Feature Branch Tracking
Monitor complexity as features are added:

```bash
# On feature/add-caching
tscodekg build --repo .
tscodekg snapshot save 0.1.2-dev1

# After optimization work
tscodekg build --repo .
tscodekg snapshot save 0.1.2-dev2

# See improvement -- the key is the tag you passed, not a hash to look up
tscodekg snapshot diff 0.1.2-dev1 0.1.2-dev2
```

### Regression Detection
Identify when metrics degrade:

```bash
# Weekly health check
tscodekg build --repo .
tscodekg snapshot save 0.1.1-week5

# Compare to last week
tscodekg snapshot diff 0.1.1-week4 0.1.1-week5

# Alert if critical_issues increased or coverage dropped
```

### Automatic Capture via Git Hook (Recommended)

Install the pre-commit hook once and snapshots are captured automatically before every commit, keyed on a UTC timestamp since a commit has no release tag, and committed atomically with the changeset:

```bash
tscodekg install-hooks
```

Before each `git commit`, the hook:
1. Calls `git write-tree` to record the staged tree hash as provenance -- not
   the key, since staging the snapshot file afterward changes the index the
   hash was read from, so it names a tree that is never actually committed
2. Rebuilds the local index so it matches the staged content
3. Saves `.tscodekg/snapshots/{timestamp}.json` with full metrics (version
   auto-detected from the installed package; no `VERSION` is passed, so the
   key is a UTC timestamp)
4. Stages the snapshot file (`git add .tscodekg/snapshots/`) so it ships inside the commit
5. Runs the pre-commit framework checks (`pre-commit run`) after the snapshot is staged

If the graph isn't built yet, the snapshot step prints a warning and the hook continues. If the `tscodekg` binary can't be found at all, the hook exits cleanly without blocking the commit. Skip it for a single commit with `TSCODEKG_SKIP_SNAPSHOT=1 git commit ...`.

To overwrite an existing hook:
```bash
tscodekg install-hooks --force
```

The snapshot degrades gracefully: when the semantic extras are unavailable (e.g. a graph-only build in CI), `snapshot save` still captures a stats-only snapshot instead of failing.

### CI/CD Integration
Automate snapshot capture in your pipeline:

```bash
#!/bin/bash
# In GitHub Actions or CI workflow

# Build graph
tscodekg build --repo .

# Capture snapshot
VERSION=$(git describe --tags --always)
tscodekg snapshot save $VERSION --subject repo:tscode-kg

# Compare to previous -- the key is the tag itself, no lookup needed
PREV_TAG=$(git describe --tags --abbrev=0 HEAD~1)
tscodekg snapshot diff $PREV_TAG $VERSION > metrics_comparison.txt
```

---

## API Usage

### Python Integration

```python
from tscode_kg.snapshots import SnapshotManager

# Initialize manager (db_path enables per-module node counts)
mgr = SnapshotManager(".tscodekg/snapshots", db_path=".tscodekg/graph.sqlite")

# Capture a release snapshot: key is the tag, subject is what was measured
snapshot = mgr.capture(
    version="0.1.1",             # auto-detected from tscode-kg package if None
    branch="develop",            # auto-detected if None
    graph_stats_dict={...},      # from TypeScriptKG.stats()
    critical_issues=0,
    complexity_median=4.2,
    hotspots=[...],
    issues=[...],
    key="0.1.1",                 # release tag; omit for a UTC timestamp key
    subject="repo:tscode-kg",    # what was measured, not what measured it
    tree_hash="a1b2c3d4e5f6...", # provenance only -- auto-detected, never the key
)
mgr.save_snapshot(snapshot)

# Load and inspect by key
manifest = mgr.load_manifest()
snapshots = mgr.list_snapshots(limit=10)
loaded = mgr.load_snapshot("0.1.1")

# Compare by key
diff = mgr.diff_snapshots("0.1.0", "0.1.1")
```

### JSON Output

`snapshot list` and `snapshot diff` support `--json` for machine consumption:

```bash
tscodekg snapshot list --json > snapshots.json
tscodekg snapshot diff a b --json > comparison.json
```

---

## Metrics Explained

### Node/Edge Counts
- **Nodes** — Total entities in the knowledge graph
- **Meaningful Nodes** — Real code entities (excludes `sym:` import stubs)
- **Edges** — Relationships between nodes

Increasing nodes/edges indicates code growth. Decreasing suggests refactoring or cleanup.

### JSDoc Coverage
Fraction of documented functions, classes, interfaces, and methods.

- **97%+** — Excellent (most entities have JSDoc)
- **90-97%** — Good (well documented)
- **80-90%** — Fair (gaps in documentation)
- **<80%** — Poor (incomplete documentation)

### Critical Issues
Count of high-risk patterns found during analysis:
- High complexity functions (fan-out > 10)
- Circular dependencies
- Orphaned code
- Dead functions

Lower is better. Trends indicate code health improvements or regressions.

### Complexity Median
Median fan-in (number of callers) across all functions.

- **2-4** — Healthy (good separation of concerns)
- **5-8** — Moderate (some coordination functions)
- **>8** — High (risk of coupling)

---

## Deltas and Trends

Snapshots automatically compute deltas:

**vs_previous**
- Change from the immediately previous snapshot
- Useful for detecting what changed in the last commit/PR
- Example: "Coverage improved 0.5%, added 12 nodes"

**vs_baseline**
- Change from the oldest snapshot
- Shows overall trajectory since project start
- Example: "Growth of +500 nodes, coverage improved 5% since the baseline"

Monitor trends to detect:
- ✅ Improving coverage over time
- ✅ Stable complexity
- ⚠️ Growing critical issues
- ⚠️ Increasing fan-out (coupling)

---

## Best Practices

1. **Install the git hook**
   - Run `tscodekg install-hooks` once per repo
   - Snapshots are captured before every commit, keyed on a UTC timestamp, and staged atomically
   - `.tscodekg/snapshots/` is tracked in git — snapshots ship with the commit that produced them

2. **Capture at milestones**
   - Tag releases with versions
   - Snapshot after major refactoring
   - Weekly health checks for long-running projects

3. **Use semantic versioning**
   - `0.1.1` for releases
   - `0.1.2-dev` for development snapshots
   - Easier to track release impact

4. **Include context**
   - Pass `--subject` to name what was measured, e.g. `repo:tscode-kg`
   - Use branch names to distinguish develop/main
   - Link to issues/PRs for traceability

5. **Automate in CI**
   - Capture snapshot after every release
   - Set up alerts for regressions
   - Archive artifacts for historical analysis

6. **Analyze trends**
   - Regular review of metric trajectories
   - Celebrate improvements (coverage up 2%)
   - Address regressions quickly

---

## Common Questions

**Q: How often should I capture snapshots?**
A: At version releases (mandatory), weekly for long projects, after major changes (optional). More frequent = better granularity, but storage is minimal.

**Q: Are snapshots committed to git?**
A: Yes — `.tscodekg/snapshots/` is tracked in git (only the SQLite artifacts are ignored). The pre-commit hook stages the snapshot file automatically, so it ships inside the commit that produced it. No manual `git add` needed.

**Q: What if I miss a snapshot?**
A: You can manually create one anytime with `tscodekg snapshot save`. Delta comparison still works as long as timestamps are preserved.

**Q: My existing snapshots are keyed by a tree hash from before this scheme changed -- are they still readable?**
A: Yes. `load_snapshot` and the manifest loader both dual-read the legacy shape, so old tree-hash-keyed files stay addressable by the key they were stored under. New captures use the tag/timestamp scheme going forward; nothing rewrites history.

**Q: How do I integrate with dashboards?**
A: Use `--json` output (`snapshot list --json`, `snapshot diff --json`) and feed to Grafana, Datadog, or custom tools. The structure is designed for programmatic ingestion.

**Q: Can I delete or modify snapshots?**
A: Snapshots are write-once by design. Create new ones instead. Use `tscodekg snapshot prune` (preview with `--dry-run`) to clean up stale snapshots and keep the manifest consistent.

---

## See Also

- [Analyze.md](Analyze.md) — Thorough repository analysis
- [CHEATSHEET.md](CHEATSHEET.md) — TypeScriptKG query reference
- [README.md](../README.md) — Project overview
