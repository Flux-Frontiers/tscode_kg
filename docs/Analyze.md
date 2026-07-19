# TypeScriptKG Thorough Analysis

**Comprehensive Codebase Health & Complexity Assessment**

Analyze your TypeScript/JavaScript codebase for complexity hotspots, code quality metrics, architectural issues, and health signals. Produces detailed reports suitable for decision-making and team communication.

---

## Overview

The `tscodekg analyze` command runs the 14-phase `TSCodeKGAnalyzer` over the knowledge graph and emits a **Markdown report** — a human-readable summary for team communication:

- Complexity hotspots (high fan-in/fan-out functions)
- Global CodeRank (weighted PageRank) and SIR structural centrality
- JSDoc coverage and documentation status
- Module coupling (IMPORTS + cross-module CALLS)
- Orphaned (dead code) declarations
- Class/interface hierarchy (INHERITS + IMPLEMENTS + EXTENDS)
- Public API surface (exported declarations)
- Critical call chains
- Snapshot history for temporal comparison
- Known architectural issues and identified strengths

### The 14 phases

1. Baseline metrics
2. CodeRank (global PageRank over CALLS + IMPORTS + INHERITS)
3. Fan-in analysis (most-called functions/methods)
4. Fan-out analysis (orchestrators)
5. Orphan detection (zero-callers excluding framework entry points)
6. Pattern detection
7. Module coupling (IMPORTS + cross-module CALLS)
8. Critical call chains
9. Public API surface (exported declarations)
10. JSDoc coverage
11. Class/interface hierarchy (INHERITS + IMPLEMENTS + EXTENDS)
12. Generate insights and recommendations
13. Snapshot history
14. Structural centrality (SIR PageRank)

---

## Quick Start

### 1. Build the Knowledge Graph
```bash
tscodekg build --repo .
```

### 2. Run Thorough Analysis
```bash
tscodekg analyze . --report analysis.md
```

### 3. View the Results
```bash
cat analysis.md
```

Omit `--report` to print the Markdown report to stdout.

---

## Command Reference

```bash
tscodekg analyze [OPTIONS] [REPO_ROOT]
```

### Options

| Option | Description |
|--------|-------------|
| `--db PATH` | SQLite knowledge graph path (default: `<repo>/.tscodekg/graph.sqlite`) |
| `--vectors PATH` | sqlite-vec vector store path (default: `<repo>/.tscodekg/vectors.sqlite`) |
| `--report FILE`, `-o FILE` | Markdown report output path (omit to print to stdout) |
| `--write-centrality` | Persist SIR centrality scores to the `centrality_scores` table in the SQLite graph |

---

## What Gets Analyzed

### Complexity Hotspots

**High Fan-In Functions** (heavily called)
- Core functions that many other functions depend on
- Changes have broad impact
- Critical for stability
- Risk: Breaking changes affect many dependents

**High Fan-Out Functions** (many calls)
- Orchestration functions that call many others
- Complex coordination logic
- Testing burden
- Risk: Hard to understand and maintain

### JSDoc Coverage

Measures documentation completeness across all node kinds — modules, classes, interfaces, functions, and methods.

- **Excellent:** >90%
- **Good:** 70-90%
- **Fair:** 50-70%
- **Poor:** <50%

### Circular Dependencies

Identifies import cycles between modules that can cause issues.

**Impact:** Can cause:
- Import-time side effects
- Hard-to-debug failures
- Module ordering dependencies
- Refactoring difficulty

### Orphaned Declarations

Functions and methods with no callers (dead code candidates).

**Note:** Some false positives are normal:
- Entry points (CLI mains, `index.ts` exports)
- Framework callbacks (React lifecycle methods, event handlers, route handlers)
- Indirect callers (dynamic dispatch, string-keyed registries, reflection)

### Module Coupling

Analyzes interdependencies using `IMPORTS` edges plus cross-module `CALLS` — which modules depend on which, and where the coupling is heaviest.

### Class/Interface Hierarchy

Maps the type system's structure through `INHERITS` (class extends class), `IMPLEMENTS` (class implements interface), and `EXTENDS` (interface extends interface) edges.

### Issues & Strengths

High-level assessment compiled from the earlier phases, for example:

```markdown
### Issues Identified
- High fan-out in pipeline orchestrator (18 calls)
- 2 circular import cycles detected
- JSDoc coverage below 80% in utils module

### Strengths
- Well-structured layering (CLI → Store → Graph)
- No god objects (max fan-in: 12)
- Good separation of concerns
```

---

## Output Example

### Markdown Report Section

```markdown
## Complexity & Architecture Health

### High Fan-Out Functions (Orchestrators)
These functions coordinate many other functions. Candidates for refactoring.

1. **buildGraph** (Fan-in: 2, Fan-out: 14)
   - Complex coordination logic
   - Calls: extractNodes, buildEdges, indexSemantics, ...
   - Risk: HIGH

### JSDoc Coverage: 87.5%
Well documented. Good for onboarding.

- Modules: 100% (15/15)
- Classes: 98% (32/33)
- Interfaces: 91% (58/64)
- Functions: 86% (152/177)
- Methods: 84% (110/131)

### Issues Identified
- ⚠️ 2 circular import cycles in graph building
- ⚠️ 1 orphaned declaration (legacyHandler)

### Strengths
- ✓ No god objects detected
- ✓ Clear layering across modules
- ✓ Consistent error handling patterns
```

---

## Workflows

### Generate & Use Analysis

```bash
# Run analysis and write a report
tscodekg analyze . --report analysis.md

# View report
cat analysis.md

# Persist SIR centrality scores for downstream tooling
tscodekg analyze . --write-centrality
```

### CI/CD Integration

```bash
# In GitHub Actions or CI workflow
tscodekg build --repo .
tscodekg analyze . --report analysis.md

# Archive the report as a build artifact, or diff it against
# the previous release's report during review.
```

For machine-readable metrics gates in CI, combine the analyzer with snapshots — `tscodekg snapshot save` captures issue counts and hotspots from the same analysis, and `tscodekg snapshot list --json` / `snapshot diff --json` produce structured output. See [SNAPSHOTS.md](SNAPSHOTS.md).

### Combine with Snapshots

For the richest insights:

```bash
# 1. Run thorough analysis
tscodekg analyze . --report analysis.md

# 2. Capture the metrics as a temporal snapshot
tscodekg snapshot save

# 3. Compare against the previous snapshot
tscodekg snapshot diff <prev-key> <current-key>
```

---

## Best Practices

1. **Run regularly** — After major refactoring, at releases, during design reviews
2. **Track over time** — Use snapshots to monitor trends in complexity and coverage
3. **Share reports** — Team communication: "We're above 85% documentation"
4. **Set thresholds** — Define minimum acceptable coverage (80-90% is common)
5. **Act on hotspots** — Use for refactoring prioritization
6. **Verify fixes** — Re-run after major changes to confirm improvements

---

## Interpreting Results

### JSDoc Coverage

| Coverage | Interpretation | Action |
|----------|----------------|--------|
| >95% | Excellent | Maintain standards |
| 85-95% | Good | Review gaps, target improvements |
| 70-85% | Fair | Schedule documentation sprints |
| <70% | Poor | High onboarding friction, priority work |

### Fan-Out Risk

| Fan-Out | Risk | Recommendation |
|---------|------|-----------------|
| <5 | Low | Normal, no action |
| 5-12 | Medium | Monitor, consider refactoring |
| 12-20 | High | Plan refactoring |
| >20 | Critical | Immediate refactoring needed |

### Circular Dependencies

| Count | Action |
|-------|--------|
| 0 | Perfect |
| 1-2 | Low risk, document carefully |
| >2 | Plan refactoring cycles |

---

## API Usage

### Python Integration

```python
from pathlib import Path

from tscode_kg.analysis import TSCodeKGAnalyzer
from tscode_kg.kg import TypeScriptKG

kg = TypeScriptKG(repo_root=Path("."))
analyzer = TSCodeKGAnalyzer(kg)

# Run the 14-phase analysis (optionally writing a report and
# persisting SIR centrality scores)
results = analyzer.run_analysis(
    report_path="analysis.md",
    persist_centrality=True,
)

# Access metrics
issues = results["issues"]
function_metrics = results["function_metrics"]   # fan-in / fan-out per function

# Render the full Markdown report
markdown = analyzer.to_markdown()
```

---

## FAQ

**Q: How often should I analyze?**
A: After major refactoring, at release milestones, and monthly during normal development.

**Q: What's a good JSDoc coverage target?**
A: 85% is a good baseline; 90%+ is excellent. Use snapshots to track trends.

**Q: Are orphaned declarations always dead code?**
A: No, there are false positives: entry points, framework callbacks (React lifecycle, event handlers), dynamic dispatch. Review before deleting.

**Q: How do I fix high fan-out functions?**
A: Break into smaller helpers, extract decision logic, use composition. Reduce coordination burden.

**Q: What about circular dependencies?**
A: Usually fixable by moving shared code to a new module or restructuring imports. Plan refactoring.

---

## See Also

- [SNAPSHOTS.md](SNAPSHOTS.md) — Track metrics over time
- [CHEATSHEET.md](CHEATSHEET.md) — TypeScriptKG query reference
- [README.md](../README.md) — Project overview
