# // spec: coh-int-01, coh-int-06
"""Conformance tests for the pinned CI invocation template (coh-int-01, coh-int-06).

The workflow is configuration, and configuration is where this contract is
easiest to lose quietly: a template can drift into reimplementing gate logic,
into exiting 0 having evaluated nothing, or into invoking a runtime that is not
the pinned one — and every one of those looks like a green check downstream.

These tests read the template as text (no PyYAML dependency — the repo is
stdlib-only) and pin the properties a reviewer would otherwise have to
re-verify by eye. They are deliberately structural: they assert the SHAPE a
correct template must have, not the prose of this particular one.

Dual-runnable: pytest collects test_*; `python3 <this file>` runs them too.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402

TEMPLATE = (Path(__file__).resolve().parent.parent
            / "templates" / "github-workflows" / "spec-coherence.yml")


def _text() -> str:
    return TEMPLATE.read_text()


def _run_blocks() -> list[str]:
    """Every `run: |` block in the file, de-indented.

    Extracted by indentation rather than parsed so the test needs no YAML
    library, and so a block that is malformed enough to break a parser still
    gets inspected.
    """
    lines = _text().split("\n")
    blocks, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)run: \|$", lines[i])
        if m:
            ind = len(m.group(1))
            body, j = [], i + 1
            while j < len(lines) and (not lines[j].strip()
                                      or len(lines[j]) - len(lines[j].lstrip()) > ind):
                body.append(lines[j][ind + 2:] if len(lines[j]) > ind + 2 else "")
                j += 1
            blocks.append("\n".join(body))
            i = j
        else:
            i += 1
    return blocks


def test_template_name_matches_the_hub_matcher():
    """coh-int-02/coh-int-07: the hub finds this workflow BY NAME.

    The hub's default matcher is a case-insensitive substring test. A template
    named anything that does not contain it is a workflow the hub never sees —
    the gate would exist and the fleet would report nothing, which is the
    failure mode the fifth check class was added to prevent.
    """
    m = re.search(r"^name:\s*(.+)$", _text(), re.M)
    assert m, "template declares no name:"
    assert Config().coherence_workflow_match.lower() in m.group(1).lower(), \
        f"workflow name {m.group(1)!r} does not match the hub's matcher"


def test_template_pins_a_full_commit():
    """coh-int-01: the runtime is addressed by content, not by a moving ref.

    A branch or tag name in the pin is not a pin — the same template would run
    different bytes tomorrow. 40 hex characters, the same shape drift-scan.yml
    uses.
    """
    m = re.search(r"^\s*DEVGATE_PIN:\s*(\S+)$", _text(), re.M)
    assert m, "template declares no DEVGATE_PIN"
    assert re.fullmatch(r"[0-9a-f]{40}", m.group(1)), \
        f"pin {m.group(1)!r} is not a full commit sha"


def test_template_does_not_declare_floating_versions():
    """coh-int-01: nothing in the invocation resolves at run time.

    `actions/checkout@v4` is a moving tag; drift-scan.yml already moved to the
    sha-pinned form for exactly this reason. Any `@vN` in an action reference
    is a floating version and fails here.
    """
    for line in _text().split("\n"):
        if "uses:" in line:
            ref = line.split("uses:", 1)[1].strip()
            assert not re.search(r"@v\d+(\.\d+)*\s*(#.*)?$", ref), \
                f"floating action version: {line.strip()}"


def test_every_skip_path_is_non_green():
    """coh-int-06: SKIPPED is a non-passing condition, never absence-as-pass.

    Each `SKIPPED (` the template reports must sit in a branch that ends the
    step non-zero. There are two legitimate shapes and both count: setting the
    aggregated `FAIL=1` that the gate exits on, or exiting non-zero directly —
    the early steps have no aggregate to contribute to, and forcing them to
    invent one would be ceremony around a single verdict.

    What must never happen is a skip recorded and then forgotten while the job
    exits 0. The window ends at the next skip-or-fail branch, so a skip cannot
    be vouched for by a later one's flag.
    """
    body = "\n".join(_run_blocks())
    skips = [m.start() for m in re.finditer(r"SKIPPED \(", body)]
    assert skips, "template reports no SKIPPED path at all (coh-int-06 unmet)"
    for pos in skips:
        # Bounded by the enclosing `fi` as well as the next branch: everything
        # from the skip to where its branch ends is in scope, and nothing
        # after it is. A fixed-size window silently truncates and would let a
        # skip path go green whenever the verdict sat past the cutoff.
        window = body[pos:pos + 600]
        boundaries = [window.find(t, 1)
                      for t in ("note ", "elif ", "else\n", "\nfi\n", "\n          fi\n")]
        nxt = min([b for b in boundaries if b != -1], default=-1)
        segment = window if nxt == -1 else window[:nxt]
        assert re.search(r"FAIL=1|\bexit\s+[1-9]", segment), \
            f"a SKIPPED path neither sets FAIL=1 nor exits non-zero: " \
            f"{body[pos:pos + 200]!r}"


def test_gate_exits_on_the_failure_flag():
    """coh-int-06: the aggregated flag actually decides the job's conclusion.

    Recording a skip in the summary and exiting 0 anyway would satisfy the
    letter of "reports an explicit SKIPPED" while making the whole contract
    inert — the run would be green and the hub would never alert.
    """
    body = "\n".join(_run_blocks())
    assert re.search(r"^\s*exit \$FAIL\s*$", body, re.M), \
        "the gate does not exit on $FAIL"


def test_gate_invokes_the_service_from_the_pinned_clone():
    """coh-int-01: the invocation targets the PINNED clone, not a local copy.

    A gate that called a repo-local `python3 hub/coherence/__main__.py` would
    run the candidate's own idea of the service — the exact substitution the
    pinned runtime exists to prevent.
    """
    body = "\n".join(_run_blocks())
    assert re.search(r"python3 \.devgate/hub/coherence/__main__\.py", body), \
        "gate does not invoke the service CLI from the pinned clone"


def test_gate_uses_the_containerized_driver():
    """coh-rt-01/05: the evaluation runs in the pinned image, not on the host.

    Invoking the service without `--launch-config` runs it directly on the
    runner: no isolation, no registry-checked image identity, and an evaluator
    identity the promotion cannot audit. Separate claim from the pinned-clone
    one above — a template can get the path right and still skip containment.
    """
    body = "\n".join(_run_blocks())
    assert "--launch-config" in body, \
        "gate does not use the containerized driver"


def test_adapter_does_not_reimplement_evaluators():
    """coh-int-01: adapters transport decisions, they do not compute them.

    The third way to lose this requirement, after the wrong path and the
    missing driver: recomputing an assertion in shell. A second implementation
    of the contract is free to disagree with the first, and the disagreement
    would show up as a gate that passes where the service fails.
    """
    body = "\n".join(_run_blocks())
    for name in ("identity_consistency", "traceability_completeness",
                 "release_claim_consistency"):
        assert name not in body, \
            f"adapter reimplements evaluator {name!r} instead of invoking it"


def test_pinned_digest_is_checked_against_the_registry():
    """coh-id-04/coh-rt-01: the declared digest must agree with the registry.

    The driver refuses a ref/digest disagreement, but a template that never
    compares the two can ship a stale digest and only discover it at launch
    time in production. The comparison is in the template so the summary can
    name which of the two drifted.
    """
    body = "\n".join(_run_blocks())
    assert "execution-profiles.json" in body, \
        "template never reads the pinned execution-profile registry"
    assert re.search(r'"\$DIGEST" != "\$COHERENCE_IMAGE_MANIFEST_DIGEST"', body), \
        "template does not compare the registry digest with the configured pin"


def test_container_phase_fails_closed_on_isolation_settings():
    """coh-rt-01/05: the launch config this template ships must be the
    restrictive one.

    These are the settings the launcher refuses to relax, so a template that
    ships a permissive config is a template that never runs — and worse, one
    whose failure a future reader might be tempted to "fix" by editing the
    launcher rather than the config.
    """
    body = "\n".join(_run_blocks())
    for required in ('"network": "none"', '"read_only_rootfs": true',
                     '"cap_drop": ["ALL"]', '"cap_add": []'):
        assert required in body, f"launch config missing {required}"
    # A writable rootfs or host networking would each be a silent weakening.
    assert re.search(r'"read_only_rootfs":\s*false', body) is None
    assert re.search(r'"network":\s*"host"', body) is None


def test_doctor_phase_never_pulls_the_image():
    """coh-rt-01: the executed bytes must not depend on the network.

    A pull would mean the run's evaluator identity is determined at run time
    by a registry the promotion cannot audit. The doctor phase reports an
    absent image as a reason; it must not fetch one.
    """
    body = "\n".join(_run_blocks())
    assert "podman image exists" in body, \
        "doctor phase does not check for the pinned image"
    for forbidden in ("podman pull", "podman run --pull", "docker pull"):
        assert forbidden not in body, \
            f"template fetches the image at run time: {forbidden!r}"


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
