"""
tscode_kg: Knowledge graph for TypeScript/JavaScript codebases.

Pure tree-sitter AST extraction → SQLite (authoritative) → sqlite-vec (semantic index).

Primary entry point::

    from tscode_kg import TypeScriptKG

    kg = TypeScriptKG(repo_root="/path/to/ts-repo")
    stats = kg.build(wipe=True)
    result = kg.query("authentication middleware")
    pack = kg.pack("error handling utilities")
    pack.save("context.md")

KGExtractor SDK::

    from tscode_kg import TSCodeExtractor
"""

__version__ = "0.3.0"
__author__ = "Eric G. Suchanek, PhD"

from tscode_kg.extractor import TSCodeExtractor

__all__ = [
    "TSCodeExtractor",
]

try:
    from tscode_kg.analysis import TSCodeKGAnalyzer
    from tscode_kg.kg import BuildStats, QueryResult, SnippetPack, TypeScriptKG

    __all__ += [
        "TypeScriptKG",
        "TSCodeKGAnalyzer",
        "BuildStats",
        "QueryResult",
        "SnippetPack",
    ]
except ImportError:
    pass  # kgmodule-utils[semantic] not installed; extractor still works standalone
