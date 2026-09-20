# // spec: coh-id-04
"""Execution-profile registry: coh-id-04 identity records for the built
service image (platform manifest digests per profile; index digest when a
multi-platform manifest list exists). Shape-checked on load. The launcher
pins the image by digest and cross-checks the declared profile's recorded
platform manifest digest before assertions run.
"""
import json
import re
from pathlib import Path

_SHA = re.compile(r"sha256:[0-9a-f]{64}")
_PLATFORM = re.compile(r"^linux/(amd64|arm64)$")


class ProfileRegistryError(ValueError):
    """Invalid or unresolvable execution-profile registry (exit-30 class)."""


def validate_registry(obj) -> dict:
    if not isinstance(obj, dict):
        raise ProfileRegistryError("registry-not-object")
    if obj.get("schema") != "execution-profiles":
        raise ProfileRegistryError("bad-schema-tag")
    if not isinstance(obj.get("image"), str) or not obj["image"]:
        raise ProfileRegistryError("bad-image")
    idx = obj.get("image_index_digest")
    if idx is not None and (not isinstance(idx, str) or not _SHA.fullmatch(idx)):
        raise ProfileRegistryError("bad-image-index-digest")
    profiles = obj.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ProfileRegistryError("bad-profiles")
    labels = set()
    for p in profiles:
        if not isinstance(p, dict):
            raise ProfileRegistryError("bad-profile")
        label, plat = p.get("label"), p.get("platform")
        dig, base = p.get("image_manifest_digest"), p.get("base_image")
        if not isinstance(label, str) or not label:
            raise ProfileRegistryError("bad-profile-label")
        if label in labels:
            raise ProfileRegistryError(f"duplicate-profile-label:{label}")
        labels.add(label)
        if not isinstance(plat, str) or not _PLATFORM.fullmatch(plat):
            raise ProfileRegistryError(f"bad-platform:{plat!r}")
        if not isinstance(dig, str) or not _SHA.fullmatch(dig):
            raise ProfileRegistryError(f"bad-manifest-digest:{label}")
        if not isinstance(base, str) or "@" not in base \
                or not _SHA.fullmatch(base.rsplit("@", 1)[1]):
            raise ProfileRegistryError(f"bad-base-image:{label}")
        if not isinstance(p.get("semantic_equivalence_group"), str) \
                or not p["semantic_equivalence_group"]:
            raise ProfileRegistryError(f"bad-equivalence-group:{label}")
    return obj


def load_registry(path) -> dict:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProfileRegistryError(f"registry-unreadable:{path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileRegistryError(f"registry-invalid-json:{path}") from exc
    return validate_registry(obj)


def resolve_profile(reg: dict, label: str) -> dict:
    for p in reg["profiles"]:
        if p["label"] == label:
            return p
    raise ProfileRegistryError(f"undeclared-profile:{label}")


def check_launch_digest(reg: dict, label: str, manifest_digest: str) -> None:
    """A launch claiming a profile must reference the manifest digest the
    registry recorded for it (coh-id-04: identity stable within the
    equivalence class the launch acceptance promises)."""
    recorded = resolve_profile(reg, label)["image_manifest_digest"]
    if manifest_digest != recorded:
        raise ProfileRegistryError(
            f"profile-digest-mismatch:{label}"
        )


# Execution-identity self-check (coh-id-04, S4/S6): the HOST launcher knows
# the digest-pinned ref it executed and injects it into the container. The
# runtime reads it, shape-validates it, and records its own identity instead
# of a null. Absence stays null — an unknown identity is never fabricated.
EXECUTION_IDENTITY_ENV = "DEVGATE_IMAGE_DIGEST"
_DIGEST_RE = None


def execution_identity(environ=None) -> str:
    """The running evaluator's image manifest digest, or None when unknown.

    A malformed value is an identity ERROR, not a silent null: a digest
    that fails shape validation means someone injected nonsense into the
    execution environment.
    """
    import os as _os
    import re as _re
    global _DIGEST_RE
    if _DIGEST_RE is None:
        _DIGEST_RE = _re.compile(r"sha256:[0-9a-f]{64}")
    env = _os.environ if environ is None else environ
    raw = env.get(EXECUTION_IDENTITY_ENV, "").strip()
    if not raw:
        return None
    if not _DIGEST_RE.fullmatch(raw):
        raise ProfileRegistryError(
            f"execution-identity-malformed:{raw[:64]!r}")
    return raw
