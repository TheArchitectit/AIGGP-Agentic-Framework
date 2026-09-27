#!/usr/bin/env python3
"""Zig + OpenGL engine manifest reader for the DevGate game gates.

Reads game-manifest.json and provides engine-specific configuration.
"""

import json
from pathlib import Path


def load_manifest(root: Path) -> dict:
    """Load and parse game-manifest.json."""
    manifest_path = root / "game-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("game-manifest.json not found")
    return json.loads(manifest_path.read_text())


def get_engine(root: Path) -> str:
    """Get engine name from manifest."""
    manifest = load_manifest(root)
    return manifest.get("engine", "unknown")


def get_phase(root: Path) -> str:
    """Get current development phase from manifest."""
    manifest = load_manifest(root)
    return manifest.get("phase", "Prototype")


def is_zig_project(root: Path) -> bool:
    """Check if project uses Zig + OpenGL engine."""
    return get_engine(root) == "Zig + OpenGL"


def get_platforms(root: Path) -> list[str]:
    """Get target platforms from manifest."""
    manifest = load_manifest(root)
    return manifest.get("platforms", ["windows"])


def get_registries(root: Path) -> dict:
    """Get registry configuration from manifest."""
    manifest = load_manifest(root)
    return manifest.get("registries", {})


def validate_manifest(root: Path) -> list[str]:
    """Validate game-manifest.json has required fields.

    Returns list of validation errors (empty if valid).
    """
    errors = []
    manifest = load_manifest(root)

    required_fields = ["game", "version", "engine", "phase", "platforms"]
    for field in required_fields:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    if manifest.get("engine") == "Zig + OpenGL":
        zig_required = ["rendering", "windowing", "audio", "build_system", "web_target"]
        for field in zig_required:
            if field not in manifest:
                errors.append(f"Missing Zig-specific field: {field}")

    return errors
