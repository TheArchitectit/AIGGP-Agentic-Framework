"""DevGate game gates — Zig + OpenGL engine support.

This module adds quality gates for Zig + OpenGL game projects.
Part of the in-tree game gates (merged from devgate-game-framework 2026-09-26).

Modules:
- scanner.py: Discover .zig files, extract entity/handler definitions
- manifest.py: Read game-manifest.json for engine detection
- patterns.json: Zig-specific regression patterns (Z001-Z010)

Usage:
    from engines.zig_opengl.scanner import scan_project
    from engines.zig_opengl.manifest import load_manifest

Example:
    results = scan_project(Path("/path/to/project"))
    print(results["passed"])
"""

__version__ = "1.0.0"
__engine__ = "Zig + OpenGL"
