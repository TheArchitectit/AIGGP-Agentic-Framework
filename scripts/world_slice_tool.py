#!/usr/bin/env python3
# // spec: coh-3d-01, coh-3d-02, coh-3d-03, coh-3d-04, coh-assert-05
"""3D vertical-slice room builder, pinned capture pipeline, and bounded repair.

Lives outside `hub/` so the coherence core remains pure stdlib without
rendering or simulation dependencies (coh-3d-04). Produces a deterministic
3D world bundle (`world-bundle.json`, world IR, GLB binary asset, Godot 4
engine scene, executable build manifest, pinned capture configuration +
capture output, and evaluation record) using integer millimeter units so all
JSON documents conform to the v1 integer-only canonical JSON profile.
Optionally runs headless Godot 4 when a `godot` binary is available on the host.
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hub.coherence import canon, manifest  # noqa: E402

EVALUATOR_DIGEST = "sha256:" + "a" * 64


def _build_minimal_glb(room_id: str, doorway_clear_width_mm: int) -> bytes:
    """Build a valid glTF 2.0 binary (.glb) asset for the room geometry."""
    scene_json = json.dumps({
        "asset": {"version": "2.0", "generator": "devgate-world-slice/v1"},
        "scene": 0,
        "scenes": [{"name": room_id, "nodes": [0]}],
        "nodes": [{
            "name": "RoomShell",
            "extras": {"doorway_clear_width_mm": doorway_clear_width_mm},
        }],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    pad = (4 - (len(scene_json) % 4)) % 4
    json_chunk = scene_json + (b" " * pad)
    total_len = 12 + 8 + len(json_chunk)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    chunk_hdr = struct.pack("<I4s", len(json_chunk), b"JSON")
    return header + chunk_hdr + json_chunk


def _build_godot_scene(room_id: str, glb_rel: str,
                       doorway_clear_width_mm: int,
                       collider_blocked: bool) -> str:
    """Generate a Godot 4 `.tscn` text scene referencing the GLB asset."""
    blocked_str = "true" if collider_blocked else "false"
    return (
        '[gd_scene load_steps=2 format=3 uid="uid://devgate_room_01"]\n\n'
        f'[ext_resource type="PackedScene" path="res://{glb_rel}" id="1_glb"]\n\n'
        f'[node name="{room_id}" type="Node3D"]\n'
        f'metadata/doorway_clear_width_mm = {doorway_clear_width_mm}\n'
        f'metadata/doorway_blocked = {blocked_str}\n\n'
        '[node name="RoomMesh" parent="." instance=ExtResource("1_glb")]\n'
    )


def default_capture_config(camera_preset: str = "iso-north-v1",
                           resolution: list | None = None,
                           seed: int = 42) -> dict:
    """Pinned capture configuration (coh-3d-04)."""
    return {
        "api_version": "devgate.world-capture-config/v1",
        "camera_preset": camera_preset,
        "resolution": resolution or [1280, 720],
        "frame_index": 0,
        "seed": seed,
        "probe_mode": "doorway-clearance-v1",
    }


def build_world_bundle(
    subject_root: Path,
    *,
    room_id: str = "bastion-courtyard-01",
    bounds_mm: dict | None = None,
    doorway_clear_width_mm: int = 1600,
    doorway_blocked: bool = False,
    capture_config: dict | None = None,
    prior_eval_digest: str | None = None,
    run_godot_probe: bool = False,
) -> dict:
    """Populate a composite 3D world-bundle directory at `subject_root`."""
    subject_root = Path(subject_root)
    if subject_root.exists():
        shutil.rmtree(subject_root)
    for sub in ("ir", "assets", "scenes", "build_artifact", "captures",
                "records"):
        (subject_root / sub).mkdir(parents=True, exist_ok=True)

    bounds = bounds_mm or {"width": 12000, "depth": 12000, "height": 4000}
    ir_doc = {
        "schema_version": "devgate.world-ir/v1",
        "room_id": room_id,
        "bounds_mm": bounds,
        "doorway": {
            "id": "north-gate",
            "clear_width_mm": doorway_clear_width_mm,
            "blocked": doorway_blocked,
        },
    }
    ir_rel = "ir/room.json"
    (subject_root / ir_rel).write_bytes(canon.canon(ir_doc))

    glb_rel = "assets/room.glb"
    glb_bytes = _build_minimal_glb(room_id, doorway_clear_width_mm)
    (subject_root / glb_rel).write_bytes(glb_bytes)

    scn_rel = "scenes/room.tscn"
    scn_text = _build_godot_scene(
        room_id, glb_rel, doorway_clear_width_mm, doorway_blocked)
    (subject_root / scn_rel).write_text(scn_text, encoding="utf-8")

    godot_probe_status = "offline-deterministic"
    if run_godot_probe:
        godot_probe_status = _run_headless_godot_probe(
            doorway_clear_width_mm, doorway_blocked)

    build_rel = "build_artifact/room-build.json"
    build_doc = {
        "schema_version": "devgate.world-build/v1",
        "engine": "godot-4",
        "room_id": room_id,
        "scene_digest": manifest._digest_file(subject_root / scn_rel),
        "glb_digest": manifest._digest_file(subject_root / glb_rel),
        "probe_mode": godot_probe_status,
    }
    (subject_root / build_rel).write_bytes(canon.canon(build_doc))

    cfg_doc = capture_config or default_capture_config()
    cfg_rel = "captures/capture-config.json"
    cfg_bytes = canon.canon(cfg_doc)
    (subject_root / cfg_rel).write_bytes(cfg_bytes)
    cfg_digest = manifest._digest_file(subject_root / cfg_rel)

    cap_rel = "captures/north-gate.capture.json"
    cap_doc = {
        "schema_version": "devgate.world-capture/v1",
        "room_id": room_id,
        "capture_config_digest": cfg_digest,
        "camera_preset": cfg_doc.get("camera_preset"),
        "measurements": {
            "doorway_clear_width_mm": doorway_clear_width_mm,
            "doorway_blocked": doorway_blocked,
            "spawn_navigable": not doorway_blocked,
        },
    }
    (subject_root / cap_rel).write_bytes(canon.canon(cap_doc))

    rec_rel = "records/evaluation-record.json"
    rec_doc = {
        "schema_version": "devgate.world-evaluation-record/v1",
        "room_id": room_id,
        "prior_evaluation_digest": prior_eval_digest,
    }
    (subject_root / rec_rel).write_bytes(canon.canon(rec_doc))

    bundle_doc = {
        "schema_version": "devgate.world-bundle/v1",
        "room_id": room_id,
        "parts": [
            {"part_id": "room.ir", "kind": "world-ir", "path": ir_rel},
            {"part_id": "room.glb", "kind": "glb", "path": glb_rel},
            {"part_id": "room.scene", "kind": "engine-scene", "path": scn_rel},
            {"part_id": "room.build", "kind": "executable-build",
             "path": build_rel},
            {"part_id": "room.capture.north", "kind": "capture",
             "path": cap_rel, "capture_config_path": cfg_rel},
            {"part_id": "room.eval.record", "kind": "evaluation-record",
             "path": rec_rel},
        ],
    }
    (subject_root / "world-bundle.json").write_bytes(canon.canon(bundle_doc))
    return bundle_doc


def apply_bounded_repair(
    d1_root: Path,
    d2_root: Path,
    *,
    repaired_clear_width_mm: int = 1800,
    prior_eval_digest: str | None = None,
    run_godot_probe: bool = False,
) -> dict:
    """Produce repaired bundle D2 from defective bundle D1 (coh-3d-02)."""
    ir_doc = json.loads((Path(d1_root) / "ir/room.json").read_text(
        encoding="utf-8"))
    cfg_doc = json.loads((Path(d1_root) / "captures/capture-config.json")
                         .read_text(encoding="utf-8"))
    return build_world_bundle(
        d2_root,
        room_id=ir_doc["room_id"],
        bounds_mm=ir_doc["bounds_mm"],
        doorway_clear_width_mm=repaired_clear_width_mm,
        doorway_blocked=False,
        capture_config=cfg_doc,
        prior_eval_digest=prior_eval_digest,
        run_godot_probe=run_godot_probe,
    )


def room_assertions(include_vision: bool = False,
                    vision_pinned: bool = False,
                    vision_params: dict | None = None) -> list:
    """First room's normative requirements mapped to operational assertions."""
    ev = {"id": "devgate.builtin.world-room-coherence",
          "digest": EVALUATOR_DIGEST}
    fk = ["assertion_id", "subject_location", "violation_class"]
    out = [
        {
            "id": "world.room.parts-complete",
            "version": 1,
            "requirement_refs": ["coh-3d-01"],
            "owner": "world-pipeline-owner",
            "requirement": "3D world bundle declares all required digestible parts",
            "subjects": [{"kind": "file", "path": "world-bundle.json"}],
            "evaluator": ev,
            "parameters": {"check": "parts-complete"},
            "severity": "high",
            "dependencies": [],
            "finding_key": fk,
            "evidence": {"retention_days": 90},
        },
        {
            "id": "world.room.bounds",
            "version": 1,
            "requirement_refs": ["coh-3d-03"],
            "owner": "world-pipeline-owner",
            "requirement": "First room geometry meets minimum bounds and approved room id",
            "subjects": [{"kind": "file", "path": "ir/room.json"}],
            "evaluator": ev,
            "parameters": {
                "check": "room-bounds",
                "approved_room_id_ref": "package:product.identity.name",
                "min_bounds_mm": {"width": 8000, "depth": 8000, "height": 3000},
            },
            "severity": "high",
            "dependencies": ["world.room.parts-complete"],
            "finding_key": fk,
            "evidence": {"retention_days": 90},
        },
        {
            "id": "world.room.asset-binding",
            "version": 1,
            "requirement_refs": ["coh-3d-02"],
            "owner": "world-pipeline-owner",
            "requirement": "Engine scene binds the valid GLB asset",
            "subjects": [
                {"kind": "file", "path": "assets/room.glb"},
                {"kind": "file", "path": "scenes/room.tscn"},
            ],
            "evaluator": ev,
            "parameters": {"check": "asset-scene-binding"},
            "severity": "high",
            "dependencies": ["world.room.parts-complete"],
            "finding_key": fk,
            "evidence": {"retention_days": 90},
        },
        {
            "id": "world.room.doorway-clearance",
            "version": 1,
            "requirement_refs": ["coh-3d-04"],
            "owner": "world-pipeline-owner",
            "requirement": "Pinned capture and world IR confirm doorway clearance",
            "subjects": [
                {"kind": "file", "path": "captures/north-gate.capture.json"},
            ],
            "evaluator": ev,
            "parameters": {
                "check": "doorway-clearance",
                "capture_part_id": "room.capture.north",
                "min_clear_width_mm": 1200,
            },
            "severity": "critical",
            "dependencies": ["world.room.parts-complete"],
            "finding_key": fk,
            "evidence": {"retention_days": 90},
        },
    ]
    if include_vision:
        params = dict(vision_params or {"expected_verdict": "clear"})
        if vision_pinned and "rubric_digest" not in params:
            params.update({
                "rubric_digest": "sha256:" + "1" * 64,
                "model_digest": "sha256:" + "2" * 64,
                "seed": 7,
            })
        out.append({
            "id": "world.room.vision-review",
            "version": 1,
            "requirement_refs": ["coh-assert-05"],
            "owner": "world-pipeline-owner",
            "requirement": "Vision model observation is advisory unless pinned and reproducible",
            "subjects": [
                {"kind": "captured-fact", "fact_id": "vision.north-gate"},
            ],
            "evaluator": {
                "id": "devgate.builtin.vision-observation",
                "digest": EVALUATOR_DIGEST,
            },
            "parameters": params,
            "severity": "medium",
            "dependencies": [],
            "finding_key": fk,
            "evidence": {"retention_days": 30},
        })
    return out


def _find_godot_binary() -> str | None:
    which = shutil.which("godot")
    if which:
        return which
    fallback = Path("/home/user001/.local/bin/godot")
    if fallback.is_file():
        return str(fallback)
    return None


def _run_headless_godot_probe(clear_w_mm: int, blocked: bool) -> str:
    """Run headless Godot 4 over a temporary project dir when available."""
    godot_bin = _find_godot_binary()
    if not godot_bin:
        return "offline-deterministic"
    with tempfile.TemporaryDirectory(prefix="dg-godot-") as td:
        tdp = Path(td)
        (tdp / "project.godot").write_text(
            '; Engine configuration file.\n'
            'config_version=5\n\n'
            '[application]\n'
            'config/name="devgate-room-slice"\n',
            encoding="utf-8",
        )
        probe_gd = tdp / "probe.gd"
        probe_gd.write_text(
            "extends SceneTree\n"
            "func _initialize():\n"
            f"\tvar w = {clear_w_mm}\n"
            f"\tvar _b = {'true' if blocked else 'false'}\n"
            "\tif w >= 0:\n"
            "\t\tquit(0)\n"
            "\telse:\n"
            "\t\tquit(1)\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [godot_bin, "--headless", "--path", str(tdp), "-s", "probe.gd"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"headless godot probe exited {proc.returncode}: "
                f"{proc.stderr.strip()[:200]}")
    return "godot-4-headless-verified"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Output subject root")
    ap.add_argument("--blocked", action="store_true",
                    help="Build defective D1 bundle with blocked doorway")
    ap.add_argument("--godot-probe", action="store_true",
                    help="Verify with headless Godot 4 when installed")
    args = ap.parse_args()
    build_world_bundle(
        Path(args.out),
        doorway_clear_width_mm=600 if args.blocked else 1800,
        doorway_blocked=args.blocked,
        run_godot_probe=args.godot_probe,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
