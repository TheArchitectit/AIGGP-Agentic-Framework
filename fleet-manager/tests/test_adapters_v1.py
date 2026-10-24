# spec: fleet-007-01, fleet-007-02, fleet-007-03, fleet-007-04
"""The stable adapter contract (FLEET-007, Sprint 4.1).

Every test is one failure the contract exists to prevent:

- an adapter that is missing a call, or implements one with a signature that
  cannot carry the rule (a digest, a reference, a policy, an operation key);
- a failure that arrives as an untyped exception, or carries the credential it
  failed with;
- an image pinned by a tag, or pinned by the package to a digest the fleet does
  not run;
- a warm pool that counts a used container as stock, or stock from another
  image, or stock above its own ceiling;
- a job container that keeps a work directory, outlives its job, or names the
  registration material in its argument list.

The contract checks shape, not behaviour, so the fakes here are deliberately
inert: one of them raises on every call to prove the checker never calls it.
"""
import inspect
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from fleet_manager.adapters import (  # noqa: E402
    ADAPTER_CALLS,
    MUTATING_CALLS,
    RUNNER_IMAGE_REPOSITORY,
    STANDARD_RUNNER_IMAGE_DIGEST,
    WARM_STATES,
    AdapterContract,
    AdapterContractError,
    AdapterError,
    EphemeralInstance,
    ErrorKind,
    InstanceState,
    WarmInstance,
    WarmPool,
    check_contract,
    classify,
    image_reference,
)
from fleet_manager.model import DisruptionBudget, Pool, Runtime, TrustClass  # noqa: E402

EXPECTED_TEST_COUNT = 55

DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
STANDARD_QUADLET = PKG_ROOT.parent / "templates" / "runner" / "self-hosted-runner.container"


def _credential_shaped() -> str:
    """A value that matches the package's credential shape, built at run time.

    Assembled rather than written: a literal of this shape in a public
    repository fails the secret scan, and the scan is right (see the 3.2
    record).
    """

    return "ghp_" + ("0123456789ABCDEF" * 2) + "0123"


def _pool(**overrides) -> Pool:
    fields = dict(
        pool_id="phase1-linux",
        revision=1,
        trust_class=TrustClass.PUBLIC,
        required_labels=(("pool", "phase1"),),
        runtime=Runtime.PODMAN,
        image_digest=DIGEST,
        architectures=("x86_64",),
        warm_min=1,
        warm_max=2,
        scale_ceiling=3,
        idle_timeout_seconds=300,
        job_timeout_seconds=3600,
        cleanup_timeout_seconds=120,
        network_profile="egress-proxy",
        filesystem_profile="ephemeral-root",
        secret_profile="phase1-job-secrets",
        update_channel="stable",
        rollback_image_digest=OTHER_DIGEST,
        maintenance_window="sun 02:00-04:00",
        disruption_budget=DisruptionBudget(max_parallel=1),
        owner="platform",
        escalation="platform-oncall",
        allowed_repositories=("TheArchitectit/AIGGP-Agentic-Framework",),
    )
    fields.update(overrides)
    return Pool(**fields)


class FakeAdapter:
    """A conforming adapter whose methods never run a container."""

    runtime = Runtime.PODMAN

    def discover_capabilities(self):
        return {"podman": "5"}

    def validate_host(self, host):
        return True

    def ensure_image(self, digest, *, operation_key):
        return digest

    def create_runner(self, registration_ref, *, operation_key):
        return registration_ref

    def observe_runner(self, instance_id):
        return instance_id

    def mark_drain(self, instance_id, *, operation_key):
        return instance_id

    def cancel_or_timeout(self, instance_id, policy, *, operation_key):
        return policy

    def destroy_runner(self, instance_id, *, operation_key):
        return instance_id

    def prove_cleanup(self, instance_id):
        return instance_id

    def report_receipts(self):
        return ()

    def rollback_configuration(self, revision, *, operation_key):
        return revision


def _raise_on_every_call(cls):
    """The same signatures, none of the bodies: calling is a test failure.

    Built by wrapping rather than by hand so the shapes stay exactly right — a
    fake whose signatures drifted would prove nothing about the checker.
    """

    class Raising(cls):
        pass

    for name in ADAPTER_CALLS:
        original = getattr(cls, name)

        def refuse(*args, __original=original, **kwargs):
            raise RuntimeError("the checker called a method")

        refuse.__signature__ = inspect.signature(original)
        setattr(Raising, name, refuse)

    return Raising


class ContractTests(unittest.TestCase):
    def test_the_contract_is_the_eleven_calls_the_program_names(self) -> None:
        self.assertEqual(
            (
                "discover_capabilities",
                "validate_host",
                "ensure_image",
                "create_runner",
                "observe_runner",
                "mark_drain",
                "cancel_or_timeout",
                "destroy_runner",
                "prove_cleanup",
                "report_receipts",
                "rollback_configuration",
            ),
            ADAPTER_CALLS,
        )
        self.assertEqual(len(set(ADAPTER_CALLS)), len(ADAPTER_CALLS))

    def test_the_mutating_calls_are_the_six_that_change_a_host(self) -> None:
        self.assertEqual(
            {
                "ensure_image",
                "create_runner",
                "mark_drain",
                "cancel_or_timeout",
                "destroy_runner",
                "rollback_configuration",
            },
            set(MUTATING_CALLS),
        )
        self.assertTrue(MUTATING_CALLS <= set(ADAPTER_CALLS))

    def test_a_complete_adapter_conforms(self) -> None:
        contract = check_contract(FakeAdapter(), runtime=Runtime.PODMAN)
        self.assertIsInstance(contract, AdapterContract)
        self.assertIs(Runtime.PODMAN, contract.runtime)
        self.assertEqual(ADAPTER_CALLS, contract.calls)

    def test_a_missing_call_is_named(self) -> None:
        class MissingOne(FakeAdapter):
            prove_cleanup = None

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(MissingOne(), runtime=Runtime.PODMAN)
        self.assertIn("missing: prove_cleanup", str(caught.exception))

    def test_every_missing_call_is_reported_at_once(self) -> None:
        class MissingThreeProperly(FakeAdapter):
            prove_cleanup = None
            destroy_runner = None
            report_receipts = None

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(MissingThreeProperly(), runtime=Runtime.PODMAN)
        message = str(caught.exception)
        for name in ("prove_cleanup", "destroy_runner", "report_receipts"):
            self.assertIn(name, message)

    def test_a_member_that_is_not_callable_is_refused(self) -> None:
        class NotCallableAdapter(FakeAdapter):
            observe_runner = 7

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(NotCallableAdapter(), runtime=Runtime.PODMAN)
        self.assertIn("not callable: observe_runner", str(caught.exception))

    def test_ensure_image_needs_a_digest_parameter(self) -> None:
        class TagAdapter(FakeAdapter):
            def ensure_image(self, image, *, operation_key):
                return image

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(TagAdapter(), runtime=Runtime.PODMAN)
        self.assertIn("ensure_image: no parameter named 'digest'", str(caught.exception))

    def test_every_mutating_call_needs_an_operation_key(self) -> None:
        for name in sorted(MUTATING_CALLS):
            with self.subTest(call=name):
                adapter = FakeAdapter()
                original = getattr(adapter, name)

                def unkeyed(*args, _original=original, **kwargs):
                    return _original(*args, **kwargs)

                # Rebuild the signature without the keyword-only key, so the
                # check sees exactly the defect and nothing else.
                unkeyed.__signature__ = _signature_without(original, "operation_key")
                setattr(adapter, name, unkeyed)
                with self.assertRaises(AdapterContractError) as caught:
                    check_contract(adapter, runtime=Runtime.PODMAN)
                self.assertIn(f"{name}: no parameter named 'operation_key'", str(caught.exception))

    def test_cancel_or_timeout_needs_a_policy(self) -> None:
        class UnpoliciedAdapter(FakeAdapter):
            def cancel_or_timeout(self, instance_id, *, operation_key):
                return instance_id

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(UnpoliciedAdapter(), runtime=Runtime.PODMAN)
        self.assertIn(
            "cancel_or_timeout: no parameter named 'policy'", str(caught.exception)
        )

    def test_prove_cleanup_needs_an_instance_id(self) -> None:
        class AnonymousCleanup(FakeAdapter):
            def prove_cleanup(self):
                return True

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(AnonymousCleanup(), runtime=Runtime.PODMAN)
        self.assertIn(
            "prove_cleanup: no parameter named 'instance_id'", str(caught.exception)
        )

    def test_create_runner_asks_for_a_reference_not_the_material(self) -> None:
        class MaterialAdapter(FakeAdapter):
            def create_runner(self, registration_token, *, operation_key):
                return registration_token

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(MaterialAdapter(), runtime=Runtime.PODMAN)
        message = str(caught.exception)
        self.assertIn("create_runner: parameter 'registration_token'", message)
        self.assertIn("registration_ref", message)

    def test_a_catch_all_signature_does_not_satisfy_a_required_name(self) -> None:
        class CatchAll(FakeAdapter):
            def ensure_image(self, **kwargs):
                return kwargs

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(CatchAll(), runtime=Runtime.PODMAN)
        self.assertIn("ensure_image: no parameter named 'digest'", str(caught.exception))

    def test_the_wrong_runtime_is_refused(self) -> None:
        class DockerAdapter(FakeAdapter):
            runtime = Runtime.DOCKER

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(DockerAdapter(), runtime=Runtime.PODMAN)
        message = str(caught.exception)
        self.assertIn("docker", message)
        self.assertIn("podman", message)

    def test_an_adapter_that_declares_no_runtime_is_refused(self) -> None:
        class RuntimeLess(FakeAdapter):
            runtime = "podman"

        with self.assertRaises(AdapterContractError) as caught:
            check_contract(RuntimeLess(), runtime=Runtime.PODMAN)
        self.assertIn("adapter.runtime", str(caught.exception))

    def test_the_pool_runtime_must_be_a_runtime(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            check_contract(FakeAdapter(), runtime="podman")
        self.assertIn("adapter.runtime", str(caught.exception))

    def test_checking_does_not_call_the_adapter(self) -> None:
        contract = check_contract(
            _raise_on_every_call(FakeAdapter)(), runtime=Runtime.PODMAN
        )
        self.assertEqual(ADAPTER_CALLS, contract.calls)

    def test_the_contract_value_cannot_be_re_written(self) -> None:
        with self.assertRaises(AdapterContractError):
            AdapterContract(runtime=Runtime.PODMAN, calls=ADAPTER_CALLS[:-1])
        with self.assertRaises(AdapterContractError):
            AdapterContract(runtime="podman")


class ErrorTests(unittest.TestCase):
    def test_the_eight_kinds_are_exactly_the_programs(self) -> None:
        self.assertEqual(
            {
                "invalid_desired_state",
                "unavailable_host",
                "registration_failure",
                "runtime_failure",
                "cleanup_failure",
                "capacity_exhaustion",
                "policy_denial",
                "unknown_state",
            },
            {kind.value for kind in ErrorKind},
        )

    def test_an_unknown_kind_is_refused(self) -> None:
        for bad in ("runtime_failure", None, 3, "boom"):
            with self.subTest(kind=bad):
                with self.assertRaises(AdapterContractError) as caught:
                    AdapterError(bad)
                self.assertIn("adapter_error.kind", str(caught.exception))

    def test_a_kind_is_required(self) -> None:
        with self.assertRaises(TypeError):
            AdapterError()  # type: ignore[call-arg]

    def test_the_kind_is_an_enum_not_a_spelling(self) -> None:
        error = AdapterError(ErrorKind.POLICY_DENIAL)
        self.assertEqual("policy_denial", str(error))
        self.assertIs(ErrorKind.POLICY_DENIAL, error.kind)

    def test_a_detail_that_looks_like_a_credential_is_withheld(self) -> None:
        value = _credential_shaped()
        with self.assertRaises(AdapterContractError) as caught:
            AdapterError(ErrorKind.REGISTRATION_FAILURE, f"was given {value}")
        self.assertNotIn(value, str(caught.exception))
        self.assertIn("withheld", str(caught.exception))

    def test_a_long_detail_is_refused(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            AdapterError(ErrorKind.RUNTIME_FAILURE, "x" * 513)
        self.assertIn("512", str(caught.exception))

    def test_a_detail_must_be_a_string(self) -> None:
        with self.assertRaises(AdapterContractError):
            AdapterError(ErrorKind.RUNTIME_FAILURE, 3)

    def test_an_unexpected_exception_is_classified_by_type_only(self) -> None:
        value = _credential_shaped()
        failure = RuntimeError(f"docker login failed with {value}")
        classified = classify(failure)
        self.assertIsInstance(classified, AdapterError)
        self.assertIs(ErrorKind.RUNTIME_FAILURE, classified.kind)
        self.assertIn("RuntimeError", str(classified))
        self.assertNotIn(value, str(classified))
        self.assertNotIn("docker login failed", str(classified))

    def test_classify_passes_an_adapter_error_through(self) -> None:
        original = AdapterError(ErrorKind.UNAVAILABLE_HOST, "host-a")
        self.assertIs(original, classify(original))


class ImageTests(unittest.TestCase):
    def test_the_standard_digest_is_a_digest(self) -> None:
        self.assertTrue(STANDARD_RUNNER_IMAGE_DIGEST.startswith("sha256:"))
        self.assertEqual(71, len(STANDARD_RUNNER_IMAGE_DIGEST))

    def test_the_image_reference_is_repository_plus_digest(self) -> None:
        self.assertEqual(
            f"{RUNNER_IMAGE_REPOSITORY}@{DIGEST}", image_reference(DIGEST)
        )

    def test_a_tag_is_refused(self) -> None:
        for tag in (
            "ghcr.io/actions/actions-runner:2.337.0",
            "2.337.0",
            "latest",
        ):
            with self.subTest(tag=tag):
                with self.assertRaises(AdapterContractError) as caught:
                    image_reference(tag)
                self.assertIn("mutable", str(caught.exception))

    def test_a_reference_is_not_a_digest(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            image_reference(f"{RUNNER_IMAGE_REPOSITORY}@{DIGEST}")
        self.assertIn("not a reference", str(caught.exception))

    def test_a_digest_must_be_lowercase_hex_of_the_right_length(self) -> None:
        for bad in (
            "sha256:" + "A" * 64,
            "sha256:" + "a" * 63,
            "sha256:" + "a" * 65,
            "sha256:" + "g" * 64,
            "sha512:" + "a" * 64,
            "",
        ):
            with self.subTest(digest=bad):
                with self.assertRaises(AdapterContractError):
                    image_reference(bad)

    @unittest.skipUnless(
        STANDARD_QUADLET.exists(),
        "the extraction rehearsal copies only fleet-manager/, so the fleet "
        "standard is absent there; a changed standard still fails",
    )
    def test_the_standard_digest_is_the_digests_the_fleet_runs(self) -> None:
        image_lines = [
            line.strip()
            for line in STANDARD_QUADLET.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("Image=")
        ]
        self.assertTrue(image_lines, "the quadlet records no Image= pin")
        expected = f"Image={RUNNER_IMAGE_REPOSITORY}@{STANDARD_RUNNER_IMAGE_DIGEST}"
        self.assertEqual([expected], image_lines)


class WarmPoolTests(unittest.TestCase):
    def test_only_two_states_are_warm(self) -> None:
        self.assertEqual(
            {InstanceState.PREPULLED, InstanceState.STOPPED_CLEAN}, WARM_STATES
        )
        for state in InstanceState:
            with self.subTest(state=state.value):
                instance = WarmInstance(
                    instance_id="w-1",
                    pool_id="phase1-linux",
                    image_digest=DIGEST,
                    state=state,
                )
                self.assertEqual(state in WARM_STATES, instance.is_warm)

    def test_a_warm_pool_refuses_used_stock(self) -> None:
        used = WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.USED)
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=_pool(), instances=(used,))
        self.assertIn("not warm stock", str(caught.exception))
        self.assertIn("RUN-001", str(caught.exception))

    def test_warm_stock_above_the_ceiling_is_refused(self) -> None:
        pool = _pool(warm_min=1, warm_max=1)
        instances = (
            WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.PREPULLED),
            WarmInstance("w-2", "phase1-linux", DIGEST, InstanceState.STOPPED_CLEAN),
        )
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=pool, instances=instances)
        self.assertIn("capacity exhaustion", str(caught.exception))

    def test_warm_stock_from_another_image_is_refused(self) -> None:
        stale = WarmInstance("w-1", "phase1-linux", OTHER_DIGEST, InstanceState.PREPULLED)
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=_pool(), instances=(stale,))
        message = str(caught.exception)
        self.assertIn(OTHER_DIGEST, message)
        self.assertIn(DIGEST, message)

    def test_warm_stock_from_another_pool_is_refused(self) -> None:
        foreign = WarmInstance("w-1", "other-pool", DIGEST, InstanceState.PREPULLED)
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=_pool(), instances=(foreign,))
        self.assertIn("other-pool", str(caught.exception))

    def test_duplicate_instance_ids_are_refused(self) -> None:
        one = WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.PREPULLED)
        two = WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.STOPPED_CLEAN)
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=_pool(), instances=(one, two))
        self.assertIn("duplicate", str(caught.exception))

    def test_admitting_past_the_ceiling_is_capacity_exhaustion(self) -> None:
        pool = _pool(warm_min=1, warm_max=2)
        stock = WarmPool(
            pool=pool,
            instances=(
                WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.PREPULLED),
                WarmInstance("w-2", "phase1-linux", DIGEST, InstanceState.STOPPED_CLEAN),
            ),
        )
        extra = WarmInstance("w-3", "phase1-linux", DIGEST, InstanceState.PREPULLED)
        with self.assertRaises(AdapterContractError) as caught:
            stock.admit(extra)
        self.assertIn("capacity exhaustion", str(caught.exception))

    def test_shortfall_and_floor(self) -> None:
        pool = _pool(warm_min=2, warm_max=3)
        empty = WarmPool(pool=pool)
        self.assertEqual(2, empty.shortfall)
        self.assertFalse(empty.at_floor)
        one = empty.admit(
            WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.PREPULLED)
        )
        self.assertEqual(1, one.shortfall)
        self.assertFalse(one.at_floor)
        two = one.admit(
            WarmInstance("w-2", "phase1-linux", DIGEST, InstanceState.STOPPED_CLEAN)
        )
        self.assertEqual(0, two.shortfall)
        self.assertTrue(two.at_floor)
        self.assertEqual(0, empty.warm_count, "admit must not mutate the pool it is called on")

    def test_retiring_an_unknown_instance_is_refused(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            WarmPool(pool=_pool()).retire("w-9")
        self.assertIn("w-9", str(caught.exception))

    def test_retiring_an_instance_leaves_the_rest(self) -> None:
        stock = WarmPool(
            pool=_pool(warm_min=1, warm_max=3),
            instances=(
                WarmInstance("w-1", "phase1-linux", DIGEST, InstanceState.PREPULLED),
                WarmInstance("w-2", "phase1-linux", DIGEST, InstanceState.STOPPED_CLEAN),
            ),
        )
        after = stock.retire("w-1")
        self.assertEqual(("w-2",), tuple(instance.instance_id for instance in after.instances))

    def test_a_warm_pool_needs_a_pool_and_a_tuple(self) -> None:
        with self.assertRaises(AdapterContractError):
            WarmPool(pool=None)  # type: ignore[arg-type]
        with self.assertRaises(AdapterContractError):
            WarmPool(pool=_pool(), instances=[])  # type: ignore[arg-type]

    def test_a_warm_instance_is_identified(self) -> None:
        for bad_field, value in (
            ("instance_id", "W 1"),
            ("pool_id", ""),
            ("image_digest", "latest"),
            ("state", "prepulled"),
        ):
            with self.subTest(field=bad_field):
                arguments = dict(
                    instance_id="w-1",
                    pool_id="phase1-linux",
                    image_digest=DIGEST,
                    state=InstanceState.PREPULLED,
                )
                arguments[bad_field] = value
                with self.assertRaises(AdapterContractError):
                    WarmInstance(**arguments)


class EphemeralInstanceTests(unittest.TestCase):
    def _instance(self, **overrides) -> EphemeralInstance:
        fields = dict(
            instance_id="job-1",
            pool_id="phase1-linux",
            image_digest=DIGEST,
            registration_env_file="/run/devgate/phase1-linux.secrets.env",
            runtime=Runtime.PODMAN,
        )
        fields.update(overrides)
        return EphemeralInstance(**fields)

    def test_a_job_instance_has_no_work_directory(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            self._instance(work_dir="/srv/work")
        self.assertIn("anonymous", str(caught.exception))

    def test_a_job_instance_is_removed_on_exit(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            self._instance(remove_on_exit=False)
        self.assertIn("RUN-001", str(caught.exception))

    def test_the_command_mounts_no_durable_volume(self) -> None:
        command = self._instance().command()
        for flag in ("-v", "--volume", "--mount"):
            self.assertNotIn(flag, command)
        self.assertNotIn("/_work", " ".join(command))

    def test_the_command_never_names_the_registration_material(self) -> None:
        command = self._instance().command()
        joined = " ".join(command)
        self.assertNotIn("RUNNER_TOKEN=", joined)
        for part in command:
            self.assertFalse(
                any(character in part for character in ("RUNNER_TOKEN", "=ref:")),
                f"argument names registration material: {part!r}",
            )
        self.assertIn("--env-file", command)
        self.assertIn("/run/devgate/phase1-linux.secrets.env", command)

    def test_the_command_is_ephemeral_and_named(self) -> None:
        command = self._instance().command()
        self.assertEqual("podman", command[0])
        self.assertEqual("run", command[1])
        self.assertIn("--rm", command)
        self.assertEqual("job-1", command[command.index("--name") + 1])
        self.assertEqual("EPHEMERAL=true", command[command.index("--env") + 1])

    def test_the_command_uses_the_pools_runtime_binary(self) -> None:
        docker = self._instance(runtime=Runtime.DOCKER).command()
        self.assertEqual("docker", docker[0])

    def test_the_command_runs_the_pinned_image(self) -> None:
        command = self._instance().command()
        self.assertEqual(f"{RUNNER_IMAGE_REPOSITORY}@{DIGEST}", command[-1])
        self.assertIn("devgate.pool=phase1-linux", command)

    def test_a_credential_shaped_env_path_is_refused(self) -> None:
        value = _credential_shaped()
        with self.assertRaises(AdapterContractError) as caught:
            self._instance(registration_env_file=f"/run/{value}.env")
        self.assertNotIn(value, str(caught.exception))

    def test_an_env_file_that_is_an_assignment_is_refused(self) -> None:
        with self.assertRaises(AdapterContractError) as caught:
            self._instance(registration_env_file="RUNNER_TOKEN=abc")
        self.assertIn("assignment", str(caught.exception))

    def test_an_instance_names_its_pool_and_validates_its_fields(self) -> None:
        with self.assertRaises(AdapterContractError):
            self._instance(runtime="podman")
        with self.assertRaises(AdapterContractError):
            self._instance(image_digest="latest")
        with self.assertRaises(AdapterContractError):
            self._instance(instance_id="Job 1")


def _signature_without(member, name):
    signature = inspect.signature(member)
    parameters = [
        parameter
        for key, parameter in signature.parameters.items()
        if key != name
    ]
    return signature.replace(parameters=parameters)


class TestSuiteFloor(unittest.TestCase):
    def test_this_suite_runs_all_of_its_tests(self) -> None:
        discovered = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        self.assertEqual(EXPECTED_TEST_COUNT, discovered.countTestCases())


if __name__ == "__main__":
    unittest.main()
