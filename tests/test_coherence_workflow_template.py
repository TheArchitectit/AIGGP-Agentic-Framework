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
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "github-workflows" / "spec-coherence.yml"
REGISTRY = REPO / "container" / "execution-profiles.json"


def _text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _template_env() -> dict:
    """The template's UPPERCASE env values, by name (no YAML parser needed)."""
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^\s*([A-Z][A-Z0-9_]*):\s*(\S*)\s*$",
                                 _text(), re.M)}


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


def test_template_runner_label_is_overridable():
    """Runner labels are REPO-SCOPED, so one hardcoded label is wrong somewhere.

    Measured 2026-09-24 (infra-info @3e156ba): the framework registers
    `devgate`, gamerepo01 registers `devgate-game`, rad-gateway registers
    `devgate-radgateway,fleet` — the name `devgate` is not a fleet-wide label,
    it is a per-repo one. A gate copied into a repo whose runner carries a
    different label does not fail: it QUEUES FOREVER and reports nothing at
    all, which is the silent case this template exists to avoid. So the label
    must be set by the repo, with the historical default kept as the fallback.
    """
    m = re.search(r"^\s*runs-on:\s*(\S.*)$", _text(), re.M)
    assert m, "template declares no runs-on"
    target = m.group(1).strip()
    assert "vars.DEVGATE_RUNNER_LABEL" in target, (
        f"runner label is hardcoded ({target!r}) — a repo whose runner carries "
        f"a different label queues forever; read it from a repo variable")
    assert "devgate" in target, "no default label in the fallback"
    assert "queue" in _text().lower(), (
        "the setup notes must name the queue-forever failure mode")


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


def test_the_pinned_commit_carries_the_pinned_identity():
    """coh-id-04 + coh-int-01: the pin names a tree that agrees with the pins.

    The gate checks DEVGATE_PIN out into .devgate and reads
    container/execution-profiles.json FROM THAT TREE, then SKIPs with FAIL=1
    when its digest is not COHERENCE_IMAGE_MANIFEST_DIGEST. So a pin that
    predates a re-pin is not a stale-but-harmless value: every consumer's
    coherence gate lands at SKIPPED. That makes the pinned tree part of the
    identity — this performs the digest step's own resolution, against the
    registry at the pin, so a pin that does not carry the identity fails here
    instead of in every consumer's summary.
    """
    m = re.search(r"^\s*DEVGATE_PIN:\s*([0-9a-f]{40})\s*$", _text(), re.M)
    assert m, "template declares no 40-hex DEVGATE_PIN"
    shown = subprocess.run(["git", "-C", str(REPO), "show",
                            f"{m.group(1)}:container/execution-profiles.json"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert shown.returncode == 0, (
        f"the pinned commit {m.group(1)} does not carry "
        f"container/execution-profiles.json — either it is not in this clone "
        f"(the tests job checks out with fetch-depth 0 precisely so it is), or "
        f"the pin predates the identity registry. Re-pin to a commit whose tree "
        f"carries it: {shown.stderr.strip()[:160]}")
    env, pinned = _template_env(), json.loads(shown.stdout)
    assert env.get("COHERENCE_IMAGE") == pinned["image"], (
        f"the pin's tree records image {pinned['image']!r}, the template pins "
        f"{env.get('COHERENCE_IMAGE')!r}")
    prof = next((p for p in pinned["profiles"]
                 if p.get("label") == env.get("COHERENCE_PROFILE")), None)
    assert prof, (f"the pin's tree has no profile {env.get('COHERENCE_PROFILE')!r}")
    assert env.get("COHERENCE_IMAGE_MANIFEST_DIGEST") == prof["image_manifest_digest"], (
        f"the pin's tree records digest {prof['image_manifest_digest']}, the "
        f"template pins {env.get('COHERENCE_IMAGE_MANIFEST_DIGEST')}")


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

    A gate that ran a candidate-local `hub/` would execute the candidate's own
    idea of the service — the exact substitution the pinned runtime exists to
    prevent. The invocation must be `python3 -m hub.coherence` (the image's own
    ENTRYPOINT form) launched from inside `.devgate`, so the module resolves to
    the pinned clone. It MUST NOT be `python3 .../__main__.py`: that form is an
    ImportError (relative imports need a package context), and this test once
    pinned it verbatim — the suite certifying the defect it should have caught
    (round-18 D3).
    """
    body = "\n".join(_run_blocks())
    assert re.search(r"python3 \.devgate/hub/coherence/__main__\.py", body) is None, \
        "gate invokes __main__.py directly — an ImportError; use -m hub.coherence"
    assert re.search(r"cd \.devgate\b[^\n]*python3 -m hub\.coherence\b", body), \
        "gate does not run `python3 -m hub.coherence` from the pinned clone"


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


def test_container_phase_delegates_launch_config_to_the_builder():
    """coh-rt-01/05: the template must NOT hand-write the launch config.

    This requirement used to be tested by grepping the shell for
    `"network": "none"` etc. — which only proved the TEMPLATE embedded the
    right isolation values, and did nothing to stop the template's heredoc from
    simultaneously shipping ONE mount while the contract needs four (round-18
    D1). The isolation property belongs to `hub.coherence.invoke.build_launch`
    and to `launcher.validate_launch`, which enforces it regardless of what
    any config claims (the container never self-certifies, coh-rt-02); both are
    pinned in tests/test_hub_coherence_invoke.py. What this template test can
    honestly hold is the DELEGATION: the shell runs the builder and passes its
    output to the driver, so no launch JSON is assembled in bash.
    """
    body = "\n".join(_run_blocks())
    # The shell must not write a launch.json object itself...
    assert 'cat >' not in body and 'EOF' not in body, \
        "template assembles a payload in shell — a second implementation (D1)"
    # ...but must call the builder that produces it, and feed the driver.
    assert re.search(r"python3 -m hub\.coherence\.invoke\b", body), \
        "template does not delegate request/launch construction to the builder"
    # The driver invocation is what enforces isolation at launch.
    assert "--launch-config" in body, "no containerized driver invocation"


def test_template_identity_agrees_with_the_repo_registry():
    """coh-id-04: the template's literals ARE this repo's registry record.

    The byte-equivalence suite cannot see this drift: its `_run_template_command`
    substitutes the registry's values FOR these literals (`$COHERENCE_IMAGE` ->
    reg["image"], `$DIGEST` -> the profile digest), so it proves the command's
    SHAPE and is blind to the identity the command addresses — measured
    2026-09-23, when both sides agreed on a build-time config digest no
    registry could serve. This is the missing comparison: what a consumer's
    gate launches is what this repo's registry records, and what the driver
    checks the launch against.
    """
    env = _template_env()
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    label = env.get("COHERENCE_PROFILE")
    assert label, "template declares no COHERENCE_PROFILE"
    prof = next((p for p in reg["profiles"] if p.get("label") == label), None)
    assert prof, f"template profile {label!r} is not in the pinned registry"
    assert env.get("COHERENCE_IMAGE") == reg["image"], (
        f"template COHERENCE_IMAGE {env.get('COHERENCE_IMAGE')!r} != registry "
        f"image {reg['image']!r}")
    assert re.fullmatch(r"sha256:[0-9a-f]{64}",
                        env.get("COHERENCE_IMAGE_MANIFEST_DIGEST") or ""), \
        "template pins no manifest digest"
    assert env.get("COHERENCE_IMAGE_MANIFEST_DIGEST") == \
        prof["image_manifest_digest"], (
        f"template digest {env.get('COHERENCE_IMAGE_MANIFEST_DIGEST')!r} != "
        f"registry digest {prof['image_manifest_digest']!r} for {label}")


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
