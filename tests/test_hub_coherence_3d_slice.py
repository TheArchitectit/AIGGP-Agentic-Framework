# // spec: coh-3d-01, coh-3d-02, coh-3d-03, coh-3d-04, coh-assert-05
"""3D vertical-slice conformance and unit suite (add-3d-vertical-slice).

Covers:
  - coh-3d-01: composite 3D world-bundle manifest with individually digestible
    parts (world-ir, glb, engine-scene, executable-build, capture,
    evaluation-record), schema validation, and 1-byte mutation sensitivity.
  - coh-3d-02 (Acceptance Fixture G): bounded repair produces digest D2;
    pre-repair attestation for D1 is refused against D2; only the D2-bound
    PASS attestation promotes D2.
  - coh-3d-03: 3D world-bundle evaluation runs through the exact same
    `python -m hub.coherence --request` CLI, exit codes, and `result.schema.json`
    contract as code subjects without pipeline-specific branching.
  - coh-3d-04: captures enter evaluation under pinned capture configurations
    (`capture_config_digest`); regenerating under a different config changes
    capture identity and recorded findings; evaluators never invoke rendering
    or simulation.
  - coh-assert-05: unpinned/stochastic vision model observations remain
    advisory-only (`ADVISORY`) even at Stage 3/4 and never silently produce or
    block an enforced PASS; fully pinned reproducible observations participate
    deterministically under the normal contract.

Dual-runnable via pytest and `python3 tests/test_hub_coherence_3d_slice.py`.
All fixtures synthetic (R9).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from hub.coherence import (  # noqa: E402
    attest,
    canon,
    evaluators,
    manifest,
    package,
    result,
    schemacheck,
)
from scripts import world_slice_tool as wst  # noqa: E402
from tests.fixtures.coherence import fixtures as fx  # noqa: E402


def _build_world_request(
    root: Path,
    subject_dir: Path,
    *,
    assertions: list | None = None,
    stage: int = 2,
    semantics: str = "fresh-promotion",
    captured_facts: dict | None = None,
    room_id: str = "bastion-courtyard-01",
) -> tuple[Path, Path, dict]:
    """Assemble OpenSpec package, policy, context, and request for a 3D bundle."""
    root.mkdir(parents=True, exist_ok=True)
    pkg = root / "openspec"
    (pkg / "specs").mkdir(parents=True)
    assertion_list = assertions if assertions is not None else wst.room_assertions()
    for a in assertion_list:
        (pkg / "specs" / f"{a['id']}.json").write_text(
            json.dumps(a), encoding="utf-8")
    inv = [
        {
            "path": str(f.relative_to(pkg)),
            "kind": "normative",
            "digest": canon.digest_bytes("file/v1", f.read_bytes()),
        }
        for f in sorted((pkg / "specs").glob("*.json"))
    ]
    (pkg / "package.json").write_text(json.dumps({
        "schema_version": "devgate.openspec.package/v1",
        "package_id": "com.test.world-slice",
        "package_version": "2026.11.01",
        "product": {"identity": {"name": room_id}},
        "normative_inventory": inv,
        "imports": [],
    }), encoding="utf-8")

    pol = root / "policy"
    pol.mkdir()
    bundle = {
        "api_version": "devgate.spec-coherence.policy/v1",
        "policy_version": "1",
        "bundle_epoch": 1,
        "required_assertions": [a["id"] for a in assertion_list],
        "approved_evaluators": [],
        "approved_signers": [],
        "stages": {"max_advisory_age_days": 30},
        "advisory_escalation": {
            "on_expiry": "block",
            "renewal": {"requires": "central-approval",
                        "max_extension_days": 30},
        },
    }
    (pol / "policy.json").write_text(json.dumps(bundle), encoding="utf-8")
    pol_digest = canon.digest_obj("policy/v1", bundle)

    ctx = root / "ctx"
    (ctx / "facts").mkdir(parents=True)
    fact_records = []
    for fid, payload_obj in sorted((captured_facts or {}).items()):
        raw = canon.canon(payload_obj)
        (ctx / "facts" / fid).write_bytes(raw)
        fact_records.append({
            "fact_id": fid,
            "digest": canon.digest_bytes("file/v1", raw),
            "captured_at": fx.FIXED_TIME,
            "source": "vision-capture-pipeline",
        })
    ctx_doc = {
        "api_version": "devgate.spec-coherence.context/v1",
        "context_id": "world-slice-ctx",
        "evaluation_time": fx.FIXED_TIME,
        "stage": stage,
        "semantics": semantics,
        "policy_binding": {
            "expected_digest": pol_digest,
            "min_bundle_epoch": 0,
            "grandfathers": [],
        },
        "baseline_set_digest": None,
        "exception_set_digest": None,
        "signer_set_digest": None,
        "capability_grants": [],
        "captured_facts": fact_records,
        "execution_profile": "linux-amd64-v1",
        "supported_runners": ["linux-amd64-v1"],
        "issuance": {"issued_at": fx.FIXED_ISSUED,
                     "issuer": "fixture-control-plane"},
    }
    (ctx / "context.json").write_text(json.dumps(ctx_doc), encoding="utf-8")

    subj_manifest = manifest.build(str(subject_dir), "world-bundle")
    pkg_resolved = package.resolve(str(pkg))
    ctx_digest = canon.digest_obj("context/v1", ctx_doc)

    out_dir = root / "out"
    req_doc = {
        "api_version": "devgate.spec-coherence/v1",
        "request_id": "world-slice-req",
        "subject": {
            "kind": "world-bundle",
            "root": str(subject_dir),
            "expected_digest": subj_manifest["subject_digest"],
        },
        "openspec": {
            "root": str(pkg),
            "expected_digest": pkg_resolved["package_digest"],
        },
        "policy": {
            "root": str(pol),
            "expected_digest": pol_digest,
        },
        "context": {
            "root": str(ctx),
            "expected_digest": ctx_digest,
        },
        "semantics": semantics,
        "outputs": str(out_dir),
    }
    req_path = root / "request.json"
    req_path.write_text(json.dumps(req_doc), encoding="utf-8")
    return req_path, out_dir, subj_manifest


def _run_cli(req_path: Path, out_dir: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO), env={**os.environ, **fx.cli_env()}, timeout=120,
    )
    res_doc = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    return proc.returncode, res_doc


class TestWorldBundleManifest(unittest.TestCase):
    """coh-3d-01: composite 3D world-bundle manifest and 1-byte sensitivity."""

    def test_composite_manifest_validates_schema_and_binds_all_parts(self):
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "world"
            wst.build_world_bundle(subj)
            m = manifest.build(str(subj), "world-bundle")
            schema = schemacheck.load("subject-manifest.schema.json")
            self.assertEqual(schemacheck.validate(m, schema), [])
            self.assertEqual(m["subject_kind"], "world-bundle")
            kinds = {p["kind"] for p in m["parts"]}
            self.assertEqual(kinds, {
                "world-ir", "glb", "engine-scene",
                "executable-build", "capture", "evaluation-record",
            })
            cap_part = next(p for p in m["parts"] if p["kind"] == "capture")
            self.assertRegex(cap_part["capture_config_digest"],
                             r"^sha256:[0-9a-f]{64}$")

    def test_one_byte_change_in_any_part_changes_composite_digest(self):
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "world"
            wst.build_world_bundle(subj)
            base = manifest.build(str(subj), "world-bundle")
            base_digest = base["subject_digest"]
            part_files = [
                "ir/room.json",
                "assets/room.glb",
                "scenes/room.tscn",
                "build_artifact/room-build.json",
                "captures/north-gate.capture.json",
                "captures/capture-config.json",
                "records/evaluation-record.json",
            ]
            for rel in part_files:
                fp = subj / rel
                orig = fp.read_bytes()
                try:
                    fp.write_bytes(orig + b"\n")
                    mutated = manifest.build(str(subj), "world-bundle")
                    self.assertNotEqual(
                        mutated["subject_digest"], base_digest,
                        f"1-byte change in {rel} must change subject_digest")
                    self.assertEqual(manifest.first_mutation(base, str(subj)),
                                     rel)
                finally:
                    fp.write_bytes(orig)
            restored = manifest.build(str(subj), "world-bundle")
            self.assertEqual(restored["subject_digest"], base_digest)

    def test_world_bundle_rejects_missing_descriptor_or_missing_capture_cfg(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty"
            empty.mkdir()
            (empty / "README.md").write_text("hi\n", encoding="utf-8")
            with self.assertRaises(manifest.SubjectError):
                manifest.build(str(empty), "world-bundle")

            subj = Path(td) / "world"
            doc = wst.build_world_bundle(subj)
            for p in doc["parts"]:
                p.pop("capture_config_path", None)
            (subj / "world-bundle.json").write_bytes(canon.canon(doc))
            with self.assertRaises(manifest.SubjectError) as cm:
                manifest.build(str(subj), "world-bundle")
            self.assertIn("capture_config_path", str(cm.exception))


class TestBoundedRepairAndCommonContract(unittest.TestCase):
    """coh-3d-02 (Fixture G), coh-3d-03, coh-3d-04: gated build + repair."""

    def test_fixture_g_defective_build_fails_repair_creates_d2_and_old_attestation_refused(self):
        signer_doc = fx.signer_set("a" * 64)
        result_schema = schemacheck.load("result.schema.json")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            # 1. Defective bundle D1 (blocked doorway) fails at Stage 2.
            d1_subj = tdp / "d1_subject"
            wst.build_world_bundle(d1_subj, doorway_clear_width_mm=550,
                                   doorway_blocked=True)
            d1_req, d1_out, d1_manifest = _build_world_request(
                tdp / "d1_run", d1_subj, stage=2)
            d1_code, d1_res = _run_cli(d1_req, d1_out)
            self.assertEqual(d1_code, result.EXIT_FAIL)
            self.assertEqual(d1_res["decision"], "FAIL")
            self.assertEqual(schemacheck.validate(d1_res, result_schema), [])

            # Also evaluate a pre-repair PASS attestation for an earlier
            # candidate D1b to prove even a valid PASS attestation for an
            # earlier digest cannot promote D2.
            d1_pass_subj = tdp / "d1_prior_pass_subject"
            wst.build_world_bundle(d1_pass_subj, doorway_clear_width_mm=1500,
                                   doorway_blocked=False)
            d1p_req, d1p_out, d1p_manifest = _build_world_request(
                tdp / "d1_prior_pass_run", d1_pass_subj, stage=2)
            d1p_code, d1p_res = _run_cli(d1p_req, d1p_out)
            self.assertEqual(d1p_code, result.EXIT_PASS)
            self.assertEqual(d1p_res["decision"], "PASS")

            # 2. Bounded repair on D1 -> D2 (clears doorway, links D1 digest).
            d2_subj = tdp / "d2_subject"
            wst.apply_bounded_repair(
                d1_subj, d2_subj,
                repaired_clear_width_mm=1800,
                prior_eval_digest=d1_manifest["subject_digest"],
                run_godot_probe=True,
            )
            d2_req, d2_out, d2_manifest = _build_world_request(
                tdp / "d2_run", d2_subj, stage=2)
            self.assertNotEqual(d1_manifest["subject_digest"],
                                d2_manifest["subject_digest"])
            self.assertNotEqual(d1p_manifest["subject_digest"],
                                d2_manifest["subject_digest"])

            d2_code, d2_res = _run_cli(d2_req, d2_out)
            self.assertEqual(d2_code, result.EXIT_PASS)
            self.assertEqual(d2_res["decision"], "PASS")
            self.assertEqual(schemacheck.validate(d2_res, result_schema), [])

            # 3. Promotion consumer checks (coh-3d-02 Scenario):
            # Presenting D1's run or D1-prior's PASS attestation for D2 MUST
            # fail with candidate-digest-mismatch.
            ok_d1_for_d2, reason_d1 = attest.verify_promotion(
                str(d1_out), signer_doc, d2_manifest["subject_digest"])
            self.assertFalse(ok_d1_for_d2)
            self.assertEqual(reason_d1, "candidate-digest-mismatch")

            ok_prior_for_d2, reason_prior = attest.verify_promotion(
                str(d1p_out), signer_doc, d2_manifest["subject_digest"])
            self.assertFalse(ok_prior_for_d2)
            self.assertEqual(reason_prior, "candidate-digest-mismatch")

            # Only the D2-bound PASS attestation promotes D2.
            ok_d2, reason_d2 = attest.verify_promotion(
                str(d2_out), signer_doc, d2_manifest["subject_digest"])
            self.assertTrue(ok_d2, reason_d2)
            self.assertEqual(reason_d2, "ok")

    def test_common_contract_handles_code_and_3d_identically(self):
        """coh-3d-03 Scenario 2: one schema and one decision path handle both."""
        result_schema = schemacheck.load("result.schema.json")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            code_req, code_out = fx.build_root(tdp / "code", stage=2)
            c_code, c_res = _run_cli(code_req, code_out)

            world_subj = tdp / "world_subj"
            wst.build_world_bundle(world_subj)
            w_req, w_out, _ = _build_world_request(
                tdp / "world", world_subj, stage=2)
            w_code, w_res = _run_cli(w_req, w_out)

            self.assertEqual(c_code, result.EXIT_PASS)
            self.assertEqual(w_code, result.EXIT_PASS)
            self.assertEqual(set(c_res.keys()), set(w_res.keys()))
            self.assertEqual(schemacheck.validate(c_res, result_schema), [])
            self.assertEqual(schemacheck.validate(w_res, result_schema), [])


class TestDeclaredCapturesNoEvaluatorRender(unittest.TestCase):
    """coh-3d-04: captures carry config digest; evaluators never render."""

    def test_regenerated_capture_under_different_config_changes_identity(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            s_a = tdp / "cap_a"
            s_b = tdp / "cap_b"
            cfg_a = wst.default_capture_config(camera_preset="iso-north-v1",
                                               resolution=[1280, 720], seed=1)
            cfg_b = wst.default_capture_config(camera_preset="top-ortho-v2",
                                               resolution=[1920, 1080], seed=2)
            wst.build_world_bundle(s_a, doorway_clear_width_mm=500,
                                   doorway_blocked=True, capture_config=cfg_a)
            wst.build_world_bundle(s_b, doorway_clear_width_mm=500,
                                   doorway_blocked=True, capture_config=cfg_b)
            m_a = manifest.build(str(s_a), "world-bundle")
            m_b = manifest.build(str(s_b), "world-bundle")
            cap_a = next(p for p in m_a["parts"] if p["kind"] == "capture")
            cap_b = next(p for p in m_b["parts"] if p["kind"] == "capture")
            self.assertNotEqual(cap_a["capture_config_digest"],
                                cap_b["capture_config_digest"])
            self.assertNotEqual(m_a["subject_digest"], m_b["subject_digest"])

            req_a, out_a, _ = _build_world_request(tdp / "run_a", s_a, stage=2)
            req_b, out_b, _ = _build_world_request(tdp / "run_b", s_b, stage=2)
            _, res_a = _run_cli(req_a, out_a)
            _, res_b = _run_cli(req_b, out_b)
            obs_a = res_a["findings"][0]["observed"]
            obs_b = res_b["findings"][0]["observed"]
            self.assertIn(cap_a["capture_config_digest"], obs_a)
            self.assertIn(cap_b["capture_config_digest"], obs_b)

    def test_evaluator_never_invokes_subprocess_or_rendering(self):
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "world"
            wst.build_world_bundle(subj)
            pkg = {"product": {"identity": {"name": "bastion-courtyard-01"}}}
            with mock.patch("subprocess.run",
                            side_effect=AssertionError("evaluator spawned process")):
                for a in wst.room_assertions():
                    fn = evaluators.BUILTINS[a["evaluator"]["id"]]
                    self.assertEqual(fn(a, pkg, str(subj), {}), [])


class TestVisionObservationPosture(unittest.TestCase):
    """coh-assert-05: unpinned model advice is advisory; pinned rubric replays."""

    def test_unpinned_vision_observation_is_advisory_even_at_stage_4(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subj = tdp / "world"
            wst.build_world_bundle(subj)
            assertions = wst.room_assertions(include_vision=True,
                                             vision_pinned=False)
            facts = {
                "vision.north-gate": {
                    "verdict": "blocked-looking-shadow",
                    "observation": "stochastic VLM flagged shadow near arch",
                    "reproducible": False,
                }
            }
            req, out, _ = _build_world_request(
                tdp / "run", subj, assertions=assertions, stage=4,
                captured_facts=facts)
            code, res = _run_cli(req, out)
            # Cannot block a PASS into FAIL, and cannot silently emit PASS:
            # emits ADVISORY (exit 10) with ADVISORY enforcement on the finding.
            self.assertEqual(code, result.EXIT_ADVISORY)
            self.assertEqual(res["decision"], "ADVISORY")
            self.assertEqual(len(res["findings"]), 1)
            f = res["findings"][0]
            self.assertEqual(f["violation_class"], "unpinned-model-advice")
            self.assertEqual(f["enforcement"], "ADVISORY")

    @staticmethod
    def _write_real_artifacts(subj: Path) -> dict:
        """Real rubric/model artifacts inside the subject tree, really hashed."""
        ev = subj / "eval"
        ev.mkdir(exist_ok=True)
        rubric = ev / "rubric.md"
        rubric.write_text(
            "# north-gate vision rubric\n\nVerdicts: clear, obstructed.\n",
            encoding="utf-8")
        model = ev / "model.bin"
        model.write_bytes(b"synthetic-model-artifact-v1\n")
        return {
            "expected_verdict": "clear",
            "rubric_path": "eval/rubric.md",
            "model_path": "eval/model.bin",
            "rubric_digest": manifest._digest_file(rubric),
            "model_digest": manifest._digest_file(model),
            "seed": 11,
        }

    @staticmethod
    def _echo_fact(art: dict, subj: Path, verdict: str = "clear") -> dict:
        cap = subj / "captures" / "north-gate.capture.json"
        return {
            "vision.north-gate": {
                "verdict": verdict,
                "rubric_digest": art["rubric_digest"],
                "model_digest": art["model_digest"],
                "input_digest": manifest._digest_file(cap),
                "input_path": "captures/north-gate.capture.json",
                "seed": art["seed"],
                "reproducible": True,
            }
        }

    def test_pinned_reproducible_vision_rubric_participates_and_replays_identically(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subj = tdp / "world"
            wst.build_world_bundle(subj)
            art = self._write_real_artifacts(subj)
            assertions = wst.room_assertions(
                include_vision=True,
                vision_pinned=True,
                vision_params=art,
                vision_artifact_root=subj)
            good_fact = self._echo_fact(art, subj)
            req1, out1, _ = _build_world_request(
                tdp / "run_pass_1", subj, assertions=assertions, stage=3,
                captured_facts=good_fact)
            code1, res1 = _run_cli(req1, out1)
            self.assertEqual(code1, result.EXIT_PASS)
            self.assertEqual(res1["decision"], "PASS")
            bytes1 = (out1 / "result.json").read_bytes()

            req2, out2, _ = _build_world_request(
                tdp / "run_pass_2", subj, assertions=assertions, stage=3,
                captured_facts=good_fact)
            code2, _ = _run_cli(req2, out2)
            self.assertEqual(code2, result.EXIT_PASS)
            self.assertEqual((out2 / "result.json").read_bytes(), bytes1)

            # When the pinned rubric observes a defect, it blocks normally at Stage 3.
            bad_fact = self._echo_fact(art, subj, verdict="obstructed")
            req_fail, out_fail, _ = _build_world_request(
                tdp / "run_fail", subj, assertions=assertions, stage=3,
                captured_facts=bad_fact)
            code_f, res_f = _run_cli(req_fail, out_fail)
            self.assertEqual(code_f, result.EXIT_FAIL)
            self.assertEqual(res_f["decision"], "FAIL")
            self.assertEqual(res_f["findings"][0]["enforcement"], "BLOCK")

    def test_pin_digest_must_match_the_real_artifact_bytes(self):
        """Value check, not shape check: a claimed digest that disagrees with
        the artifact bytes is unpinned advice even when the fact echoes the
        claim consistently (a lying pin cannot enforce)."""
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subj = tdp / "world"
            wst.build_world_bundle(subj)
            art = self._write_real_artifacts(subj)
            assertions = wst.room_assertions(
                include_vision=True,
                vision_pinned=True,
                vision_params=art,
                vision_artifact_root=subj)
            lie = dict(art)
            lie["rubric_digest"] = "sha256:" + "1" * 64
            for a in assertions:
                if a["id"] == "world.room.vision-review":
                    a["parameters"]["rubric_digest"] = lie["rubric_digest"]
            fact = self._echo_fact(lie, subj)
            req, out, _ = _build_world_request(
                tdp / "run", subj, assertions=assertions, stage=3,
                captured_facts=fact)
            code, res = _run_cli(req, out)
            self.assertEqual(code, result.EXIT_ADVISORY)
            self.assertEqual(res["findings"][0]["violation_class"],
                             "unpinned-model-advice")
            self.assertEqual(res["findings"][0]["enforcement"], "ADVISORY")

    def test_fabricated_evaluator_digest_cannot_pin(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subj = tdp / "world"
            wst.build_world_bundle(subj)
            art = self._write_real_artifacts(subj)
            assertions = wst.room_assertions(
                include_vision=True,
                vision_pinned=True,
                vision_params=art,
                vision_artifact_root=subj)
            for a in assertions:
                if a["id"] == "world.room.vision-review":
                    a["evaluator"]["digest"] = "sha256:" + "a" * 64
            fact = self._echo_fact(art, subj)
            req, out, _ = _build_world_request(
                tdp / "run", subj, assertions=assertions, stage=3,
                captured_facts=fact)
            code, res = _run_cli(req, out)
            self.assertEqual(code, result.EXIT_ADVISORY)
            self.assertEqual(res["findings"][0]["enforcement"], "ADVISORY")

    def test_pinned_vision_without_artifacts_fails_loudly(self):
        with self.assertRaises(ValueError) as ctx:
            wst.room_assertions(include_vision=True, vision_pinned=True,
                                vision_params={"seed": 11})
        self.assertIn("rubric_path", str(ctx.exception))
        self.assertIn("model_path", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            wst.room_assertions(
                include_vision=True, vision_pinned=True,
                vision_params={"rubric_path": "eval/absent.md",
                               "model_path": "eval/model.bin", "seed": 11},
                vision_artifact_root=Path(tempfile.gettempdir()))
        self.assertIn("artifact absent", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
