# TypeScriptKG Temporal Snapshots

**Enterprise-Grade Metrics Tracking Across Commits**

Capture, store, and compare codebase metrics over time. Track the evolution of complexity, coverage, and health signals from version to version.

---

## Overview

Snapshots are point-in-time captures of your codebase's metrics, tagged with:
- **Tree hash** — the git tree hash of the staged changeset (pre-commit mode) or commit hash (CI/manual)
- **Commit hash** — HEAD at capture time; recorded as metadata even in pre-commit mode
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
tscodekg snapshot save 0.1.0
```

Automatically detects your current git commit and branch. Creates `.tscodekg/snapshots/{tree_hash}.json` with full metrics. Use `--tree-hash $(git write-tree)` in pre-commit context to key by staged tree.

### List All Snapshots
```bash
tscodekg snapshot list
```

Shows all snapshots in reverse chronological order:
```
Commit     Branch       Version    Nodes  Edges  Coverage
3487ed5    develop      0.1.1      1240   2380   62.0%
660e4f0    main         0.1.0      1240   2380   62.0%
9f7918d    develop      0.1.0-dev  1180   2270   58.2%
```

### Show Snapshot Details
```bash
tscodekg snapshot show 3487ed5
```

Displays full metrics, hotspots, and deltas:
```
Commit:    3487ed5
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
tscodekg snapshot diff 660e4f0 3487ed5
```

Side-by-side comparison showing what changed:
```
Comparing 660e4f0 vs 3487ed5

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
    ├── manifest.json     # Index of all snapshots
    ├── 3487ed5.json      # Snapshot keyed by tree hash
    ├── 660e4f0.json
    └── 9f7918d.json
```

### Manifest Index
```json
{
  "format": "1.0",
  "last_update": "2026-07-07T17:25:29Z",
  "snapshots": [
    {
      "key": "a1b2c3d4e5f6...",
      "commit": "3487ed5",
      "tree_hash": "a1b2c3d4e5f6...",
      "branch": "develop",
      "timestamp": "2026-07-07T17:25:29Z",
      "version": "0.1.1",
      "file": "a1b2c3d4e5f6....json",
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
tscodekg snapshot diff <v0.1.1-key> <v0.1.2-key>
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

# See improvement
tscodekg snapshot diff <dev1-key> <dev2-key>
```

### Regression Detection
Identify when metrics degrade:

```bash
# Weekly health check
tscodekg build --repo .
tscodekg snapshot save 0.1.1-week5

# Compare to last week
tscodekg snapshot diff <prev-week-key> <current-week-key>

# Alert if critical_issues increased or coverage dropped
```

### Automatic Capture via Git Hook (Recommended)

Install the pre-commit hook once and snapshots are captured automatically before every commit — keyed by the staged tree hash and committed atomically with the changeset:

```bash
tscodekg install-hooks
```

Before each `git commit`, the hook:
1. Calls `git write-tree` to get the stable tree hash of the staged changeset
2. Rebuilds the local index so it matches the staged content
3. Saves `.tscodekg/snapshots/{tree_hash}.json` with full metrics (version auto-detected from the installed package)
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
tscodekg snapshot save $VERSION

# Compare to previous
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

# Capture snapshot (pre-commit mode: pass tree_hash from `git write-tree`)
snapshot = mgr.capture(
    version="0.1.1",             # auto-detected from tscode-kg package if None
    branch="develop",            # auto-detected if None
    graph_stats_dict={...},      # from TypeScriptKG.stats()
    critical_issues=0,
    complexity_median=4.2,
    hotspots=[...],
    issues=[...],
    tree_hash="a1b2c3d4e5f6...", # optional; used as file key when set
)
mgr.save_snapshot(snapshot)

# Load and inspect (pass tree_hash or commit hash as key)
manifest = mgr.load_manifest()
snapshots = mgr.list_snapshots(limit=10)
loaded = mgr.load_snapshot("a1b2c3d4e5f6...")

# Compare (pass tree hashes or commit hashes)
diff = mgr.diff_snapshots("660e4f0tree...", "a1b2c3d4e5f6...")
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
   - Snapshots are captured before every commit, keyed by tree hash, and staged atomically
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
   - Use branch names to distinguish develop/main
   - Tag with what changed if committing snapshots
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

**Q: How do I integrate with dashboards?**
A: Use `--json` output (`snapshot list --json`, `snapshot diff --json`) and feed to Grafana, Datadog, or custom tools. The structure is designed for programmatic ingestion.

**Q: Can I delete or modify snapshots?**
A: Snapshots are write-once by design. Create new ones instead. Use `tscodekg snapshot prune` (preview with `--dry-run`) to clean up stale snapshots and keep the manifest consistent.

---

## See Also

- [Analyze.md](Analyze.md) — Thorough repository analysis
- [CHEATSHEET.md](CHEATSHEET.md) — TypeScriptKG query reference
- [README.md](../README.md) — Project overview
