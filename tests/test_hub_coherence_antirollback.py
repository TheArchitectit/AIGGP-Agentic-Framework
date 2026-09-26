# // spec: coh-pol-01, coh-pol-02
"""S6 Cycle B — the anti-rollback binding (design.md, round-15).

The signed context is the control-plane trust root: it binds the current
central bundle's digest, the epoch floor, and recorded grandfather windows.
At policy resolution the run path enforces BOTH checks — the pinned bundle
must match the bound digest AND meet the bound floor — unless a grandfather
record covers exactly that content within its window (the one exception to
both). A context with no binding is a substitution attempt (coh-pol-02's
scenario, literally: "no control-plane binding → resolution fails").

Rejections are exit 31 with machine-parsable `anti-rollback:` /
`policy-substitution:` reason prefixes so fleet reporting can alert on them;
the envelope's error.class stays policy-resolution (no exit-matrix change).

All fixtures synthetic (R9); dual-runnable.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, issue, policy, result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
DECOY = "sha256:" + "b" * 64
FUTURE = "2027-01-01T00:00:00Z"
PAST = "2026-01-01T00:00:00Z"
NOW = fx.FIXED_TIME


def _run(req):
    return subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(req)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
        env={**os.environ, **fx.cli_env()})


def _binding_error(out):
    env = json.loads((out / "result.json").read_text(encoding="utf-8"))
    return env, env["error"]


class TestSubstitutionAttempt(unittest.TestCase):
    def test_bindingless_context_is_rejected_by_the_contract(self):
        # evaluation-context.schema.json requires policy_binding (round-15):
        # a context that predates the field is rejected at load, never
        # grandfathered by silence.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f", binding=False)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY, p.stderr)
            self.assertNotIn("Traceback", p.stderr)
            env, err = _binding_error(out)
            self.assertEqual(env["decision"], "ERROR")
            self.assertEqual(err["class"], "policy-resolution")
            self.assertIn("policy_binding", err["reason"])

    def test_resolver_refuses_to_run_without_a_binding(self):
        # Defense in depth: resolve called without a binding fails closed
        # even if a schema check were bypassed — the default is refusal,
        # not "identity-only" (the pre-slice behavior).
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            root.mkdir()
            bundle = {"api_version": "devgate.spec-coherence.policy/v1",
                      "policy_version": "1", "bundle_epoch": 1,
                      "required_assertions": [], "approved_evaluators": [],
                      "approved_signers": [],
                      "stages": {"max_advisory_age_days": 30}}
            (root / "policy.json").write_text(json.dumps(bundle), encoding="utf-8")
            dig = canon.digest_obj("policy/v1", bundle)
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig)
            self.assertIn("policy-substitution", str(c.exception))


class TestRollbackRejection(unittest.TestCase):
    def test_foreign_bundle_digest_is_rejected_with_prefix(self):
        # The context binds a different central bundle than the one the repo
        # pinned: substitution of content, rejected even though the request's
        # own identity digest matches the pinned content.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f",
                                     binding_expected_digest=DECOY)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY,
                             f"pinned {DECOY[:16]} must not evaluate: {p.stderr}")
            env, err = _binding_error(out)
            self.assertEqual(err["class"], "policy-resolution")
            self.assertTrue(err["reason"].startswith("anti-rollback:"),
                            err["reason"])

    def test_epoch_below_bound_floor_is_rejected_even_when_digest_matches(self):
        # Ratified round-15: BOTH checks run. The digest matches the bound
        # current bundle, but the bundle's ordinal is below the bound floor —
        # an issuer that binds a floor above its own bundle is caught here
        # instead of silently evaluating.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f", bundle_epoch=0,
                                     min_bundle_epoch=5)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY, p.stderr)
            env, err = _binding_error(out)
            self.assertTrue(err["reason"].startswith("anti-rollback:"),
                            err["reason"])
            self.assertIn("epoch", err["reason"])

    def test_bundle_without_a_declared_epoch_fails_closed(self):
        # A bundle that does not declare its ordinal cannot be checked
        # against the floor; silence would be a bypass.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "p"
            root.mkdir()
            bundle = {"api_version": "devgate.spec-coherence.policy/v1",
                      "policy_version": "1",
                      "required_assertions": [], "approved_evaluators": [],
                      "approved_signers": [],
                      "stages": {"max_advisory_age_days": 30}}
            (root / "policy.json").write_text(json.dumps(bundle), encoding="utf-8")
            dig = canon.digest_obj("policy/v1", bundle)
            binding = {"expected_digest": dig, "min_bundle_epoch": 0,
                       "grandfathers": []}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time=NOW)
            self.assertIn("bundle_epoch", str(c.exception))


class TestGrandfatherWindow(unittest.TestCase):
    def test_grandfathered_older_bundle_runs_within_its_window(self):
        # The repo pins an older, genuinely signed bundle (the written one);
        # the context binds a newer current digest but records a window that
        # covers the pinned content: the run proceeds.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f",
                                     binding_expected_digest=DECOY,
                                     grandfather_self_until=FUTURE)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_PASS, p.stderr)

    def test_expired_grandfather_window_rejects_with_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f",
                                     binding_expected_digest=DECOY,
                                     grandfather_self_until=PAST)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY, p.stderr)
            env, err = _binding_error(out)
            self.assertTrue(err["reason"].startswith("anti-rollback:"),
                            err["reason"])
            self.assertIn("grandfather", err["reason"])

    def test_grandfather_exempts_the_epoch_floor_too(self):
        # The recorded window is the exception to BOTH checks: a
        # grandfathered bundle below the floor still runs inside its window
        # (coh-pol-01: "rejected unless explicitly grandfathered").
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f", bundle_epoch=0,
                                     min_bundle_epoch=5,
                                     binding_expected_digest=DECOY,
                                     grandfather_self_until=FUTURE)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_PASS, p.stderr)

    def test_window_expiry_is_measured_against_evaluation_time_not_host(self):
        # Time doctrine: the window is judged by the context's trusted
        # evaluation_time. The host clock is 2026-09-19, AFTER the window's
        # end — a host-clock check would reject; the context says the run is
        # happening inside the window, and the context wins.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(
                Path(td) / "f", binding_expected_digest=DECOY,
                grandfather_self_until="2026-09-18T00:00:00Z",
                evaluation_time="2026-09-17T12:00:00Z")
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_PASS, p.stderr)


class TestMalformedBindings(unittest.TestCase):
    """The binding is control-plane material; every malformed shape fails
    closed even though the context schema already rejects most of these —
    resolve is the load-bearing guard for direct callers (round-15)."""

    def _bundle_root(self, td: Path, **extra) -> tuple:
        root = Path(td) / "p"
        root.mkdir(parents=True, exist_ok=True)
        bundle = {"api_version": "devgate.spec-coherence.policy/v1",
                  "policy_version": "1", "bundle_epoch": 1,
                  "required_assertions": [], "approved_evaluators": [],
                  "approved_signers": [],
                  "stages": {"max_advisory_age_days": 30}}
        bundle.update(extra)
        (root / "policy.json").write_text(json.dumps(bundle), encoding="utf-8")
        return root, canon.digest_obj("policy/v1", bundle)

    def test_binding_without_expected_digest_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig,
                               binding={"min_bundle_epoch": 0,
                                        "grandfathers": []},
                               evaluation_time=NOW)
            self.assertIn("expected_digest", str(c.exception))

    def test_malformed_grandfather_record_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            binding = {"expected_digest": DECOY, "min_bundle_epoch": 0,
                       "grandfathers": [{"bundle_digest": dig}]}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time=NOW)
            self.assertIn("malformed grandfather", str(c.exception))

    def test_grandfather_with_unparseable_valid_until_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            binding = {"expected_digest": DECOY, "min_bundle_epoch": 0,
                       "grandfathers": [{"bundle_digest": dig,
                                         "valid_until": "not-a-time",
                                         "reason": "r"}]}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time=NOW)
            self.assertIn("unparseable", str(c.exception))

    def test_unparseable_evaluation_time_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            binding = {"expected_digest": DECOY, "min_bundle_epoch": 0,
                       "grandfathers": [{"bundle_digest": dig,
                                         "valid_until": FUTURE,
                                         "reason": "r"}]}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time="junk")
            self.assertIn("unparseable", str(c.exception))

    def test_grandfather_window_requires_an_evaluation_time(self):
        # Without the context's trusted time there is no honest way to judge
        # the window; guessing (host clock) is the one thing the service may
        # never do.
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            binding = {"expected_digest": DECOY, "min_bundle_epoch": 0,
                       "grandfathers": [{"bundle_digest": dig,
                                         "valid_until": FUTURE,
                                         "reason": "r"}]}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time=None)
            self.assertIn("evaluation_time", str(c.exception))

    def test_malformed_bound_floor_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root, dig = self._bundle_root(Path(td))
            binding = {"expected_digest": dig, "min_bundle_epoch": "5",
                       "grandfathers": []}
            with self.assertRaises(policy.PolicyError) as c:
                policy.resolve(str(root), dig, binding=binding,
                               evaluation_time=NOW)
            self.assertIn("min_bundle_epoch", str(c.exception))


class TestIssuanceWritesTheBinding(unittest.TestCase):
    def _registry(self, td) -> Path:
        td = Path(td)
        rp = td / "reg.json"
        rp.write_text(json.dumps(
            {"com.test.widget": {"stage": 2, "owner": "o"}}), encoding="utf-8")
        return rp

    def test_issued_context_binds_the_current_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            pol = Path(td) / "p"
            pol.mkdir()
            bundle = {"api_version": "devgate.spec-coherence.policy/v1",
                      "policy_version": "1", "bundle_epoch": 7,
                      "min_bundle_epoch": 3,
                      "required_assertions": [], "approved_evaluators": [],
                      "approved_signers": [],
                      "stages": {"max_advisory_age_days": 30}}
            (pol / "policy.json").write_text(json.dumps(bundle), encoding="utf-8")
            out = issue.issue_context(
                str(Path(td) / "c"), str(pol), repo="com.test.widget",
                registry_path=str(self._registry(td)),
                evaluation_time=NOW)
            ctx = json.loads((Path(td) / "c" / "context.json").read_text(encoding="utf-8"))
            b = ctx["policy_binding"]
            self.assertEqual(b["expected_digest"],
                             canon.digest_obj("policy/v1", bundle))
            self.assertEqual(b["min_bundle_epoch"], 3,
                             "floor resolved from the current bundle")
            self.assertEqual(b["grandfathers"], [])

    def test_issuance_without_a_central_bundle_is_refused(self):
        # The issuer cannot bind what does not exist: refusing here is the
        # earliest fail-closed point — an issued-but-unbound context would
        # only die later at the CLI.
        with tempfile.TemporaryDirectory() as td:
            pol = Path(td) / "p"
            pol.mkdir()
            with self.assertRaises(ValueError) as c:
                issue.issue_context(
                    str(Path(td) / "c"), str(pol), repo="com.test.widget",
                    registry_path=str(self._registry(td)),
                    evaluation_time=NOW)
            # "cannot bind" is the refusal's own phrase — a downstream
            # read-failure message ("cannot read policy bundle") must not
            # satisfy this pin.
            self.assertIn("cannot bind", str(c.exception))


if __name__ == "__main__":
    unittest.main()
