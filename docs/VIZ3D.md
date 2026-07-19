# TypeScriptKG 3D Visualizer

`viz3d` renders your TypeScript/JavaScript codebase as an interactive 3-D
knowledge graph — every module, class, interface, function, and method becomes a
solid object in space, and every relationship between them becomes a coloured
edge.  You can orbit, zoom, and pick any node to read its JSDoc.

Requires the `viz3d` extra:

```bash
pip install "tscode-kg[viz3d]"
```

---

## What the graph represents

The knowledge graph is built from your repo's tree-sitter AST and stores six
structural relationships:

| Edge type | Meaning |
|-----------|---------|
| **CONTAINS** | A module contains a class, interface, or function; a class contains its methods |
| **CALLS** | One function or method calls another |
| **IMPORTS** | A module imports another module or symbol |
| **INHERITS** | A class extends another class |
| **IMPLEMENTS** | A class implements an interface |
| **EXTENDS** | An interface extends another interface |

Every node is one of:

| Node kind | Shape (high detail) | Colour |
|-----------|--------------------|--------|
| Module | Cube | Blue `#4A90D9` |
| Class | Icosahedron / Octahedron | Green `#27AE60` |
| Interface | Icosahedron / Octahedron | Teal `#1ABC9C` |
| Type alias | Icosahedron | Purple `#9B59B6` |
| Enum | Icosahedron | Orange `#E67E22` |
| Namespace | Icosahedron | Slate `#34495E` |
| Function | Cylinder | Red `#E74C3C` |
| Private function (`_…`) | Cylinder | Yellow `#F1C40F` |
| Method | Sphere | Sky blue `#3498DB` |
| Symbol stub | Small sphere | Grey `#95A5A6` |

Node geometry is automatically simplified for large repos (Level-of-Detail tiers
at 800 and 1 500 visible nodes) so rendering stays interactive at scale.

---

## Layout styles

### Allium

Each module is drawn as a **Giant Allium flower**:

- The **module node** (cube) sits in a flat Fibonacci-annulus ring in the XY plane
  at Z = 0.  Modules are spaced outward from the centre so the ring grows with
  the number of modules.
- The **stem apex** rises vertically above each module cube.
- **Classes, interfaces, and top-level functions** are scattered on a Fibonacci
  sphere ("the flower head") centred at the stem apex.  The head radius grows
  with the square root of the child count.
- **Methods** orbit their parent class on a smaller Fibonacci sphere just
  above the head.

The result is a botanical landscape — you can visually identify large modules
(tall, bushy alliums), densely connected classes (compact heads), and lightly
populated modules (sparse heads) at a glance.

> Best for: exploring intra-module structure, spotting size imbalances,
> comparing module complexity.

### Funnel

Nodes are **stratified by kind** across horizontal Z layers:

| Layer | Node kind | Z height |
|-------|-----------|----------|
| 0 | Modules | 0 |
| 1 | Classes, interfaces, enums, type aliases, namespaces | `layer_gap` (default 20) |
| 2 | Functions & Methods | `2 × layer_gap` |
| 3 | Symbol stubs | `3 × layer_gap` |

Within each layer, XY positions are placed on a golden-angle disc spiral.
The disc radius is derived algorithmically — `r = spacing × node_size × √n` —
so the layout scales correctly for repos of any size without hand-tuning.

Cross-cutting edges (CALLS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS) arc between
layers, making structural coupling immediately visible from any angle.  The
overall silhouette typically narrows at the top (fewer modules, many functions),
giving the layout its name.

> Best for: understanding cross-layer coupling, import architecture,
> call graph shape at a glance.

---

## Camera and navigation

| Action | Result |
|--------|--------|
| Left-drag | Orbit (terrain-constrained — Z stays up) |
| Right-drag / scroll | Zoom |
| Middle-drag | Pan |
| **Reset View** button | Returns to the default front-elevated perspective |

The default view looks along +Y with a slight upward tilt so the full vertical
extent of the graph (ground modules → top functions) is visible on launch.

The **XYZ orientation widget** in the top-right corner always shows the current
camera orientation.

---

## Picking nodes

**Right-click** any node to:

- Highlight it in pink
- Open a floating JSDoc popup (rendered as Markdown; both `:param:` and
  `@param` styles are recognized)
- Zoom the camera toward it

Click **Show JSDoc** in the button row to re-open the popup for the last
picked node.  Close the popup or click another node to clear the highlight.

---

## User interface

### Control panel (left)

| Section | Controls |
|---------|---------|
| **Input Parameters** | Database path (`.tscodekg/graph.sqlite`), layout selector (Allium / Funnel), save path stem, save format (HTML / PNG / JPG) |
| **Module Filter** | Single-select list — choose one module to render only that subtree; leave empty to show the whole repo |
| **Render Options** | Checkboxes: Methods, Symbols, CONTAINS edges |
| **Edge Types** | Checkboxes: CALLS, IMPORTS, INHERITS, IMPLEMENTS, EXTENDS |
| **Funnel Spacing** | Slider (0.5 – 10.0) — controls the XY spread of each funnel layer; only active when Funnel layout is selected |
| **Graph Statistics** | Live node/edge counts (including interfaces) updated after each render |

### Viewport buttons (below the 3-D view)

| Button | Action |
|--------|--------|
| **Render Graph** | (Re-)build the full 3-D scene with current settings |
| **Show JSDoc** | Re-open the JSDoc popup for the last picked node |
| **Save View** | Export the current viewport to the configured path and format |
| **Reset View** | Restore the default camera angle and zoom |
| **Reset Settings** | Return all controls to their defaults and re-render |

### Window title bar

The title shows the repo name, version, and live node counts:

```
TypeScriptKG 3D v0.1.0 | my-ts-app | Modules: 42  Classes: 31  Interfaces: 28  Methods: 187  Functions: 96  Faces: 6412
```

---

## Performance notes

- **Edge cap** — edges are rendered up to a hard limit of 8 000.  When the limit
  is hit, structural `CONTAINS` edges are preserved first; `CALLS` edges are the
  first to be dropped.
- **Arc edges** — for graphs with ≤ 2 000 edges, edges are drawn as quadratic
  Bézier arcs for visual clarity.  Above that threshold straight lines are used
  for performance.
- **LOD tiers** — node geometry is automatically simplified above 800 and 1 500
  visible nodes.

---

## Launching

```bash
# Default (Allium layout, current repo)
tscodekg viz3d

# Funnel layout, custom DB
tscodekg viz3d --layout funnel --db /path/to/.tscodekg/graph.sqlite

# Larger window
tscodekg viz3d --width 1920 --height 1080
```

The database must exist before launching — run `tscodekg build` first if needed.
