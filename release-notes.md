# Release Notes -- v0.6.0

> Released: 2026-09-21

TypeScriptKG's MCP server now closes the graph database when it shuts down. No
index rebuild, no migration, no CLI change.

## What changed

**The MCP server closes the graph on shutdown.** `tscodekg-mcp` wires an
`asynccontextmanager` into `FastMCP(lifespan=...)`, so the SQLite connection is
released when the server stops rather than left to process exit. One hook
covers both the stdio and SSE transports, because both route through the same
underlying `Server.run()`.

This is the resource-cleanup pattern the fleet standardised on, verified
against a real server run rather than a stubbed `close`. It matters most for
the case TypeScriptKG is actually used in: an editor or agent that keeps the
server alive across many requests and then restarts it.

## Upgrading

Nothing to do. If you run `tscodekg-mcp` inside a long-lived process, it now
leaves no database handle behind when it stops.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
