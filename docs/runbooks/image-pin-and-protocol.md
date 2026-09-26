# Runbook: Pinned-Image Drift and Protocol Mismatch

**Scope:** the two evaluator-side behaviors the coherence gate refuses on
without ever touching policy or evidence — a pinned image the host cannot
honor, and a request whose contract version this build cannot judge.
Companion to [hub-outage.md](./hub-outage.md) (the hub-side failure
classes) and [evidence-and-attestation.md](./evidence-and-attestation.md)
(the sealed-output classes).

## What you will see

A gate workflow using the shipped template
(`templates/github-workflows/spec-coherence.yml`) ends in one of:

| Signal | Where it appears |
|---|---|
| step `note "…" "SKIPPED (pinned digest … is not the registry's …)"`, workflow continues then exits nonzero | the Actions log for the gate job |
| a hub `coherence_skipped` alert naming that reason | the hub's alert stream, via the monitor |
| `result.json` with `decision: "ERROR"`, `error.class: "protocol"`, process exit 40 | the run's outputs directory |

## Root causes

- **Image drift.** What is pinned is the image **digest**, not the tag.
  The template reads the expected digest from this repo's
  `container/execution-profiles.json` for the active `COHERENCE_PROFILE`
  and compares it to the workflow's `COHERENCE_IMAGE_MANIFEST_DIGEST`.
  They disagree, or the profile is absent, when: the host's podman image
  was removed or rebuilt, the registry record moved under a stale pin, or
  the pin and the profile were edited apart (template comment: "Moving
  the pin and the digest is one operation").
- **Protocol mismatch.** The request's `api_version` is not the build's
  `SUPPORTED_API` (`hub/coherence/__main__.py` — currently
  `devgate.spec-coherence/v1`). A foreign `api_version` MUST NOT be
  judged by this version's schema (coh-dec-04): the guard returns before
  deep validation, so an old hub talking to a new evaluator fails closed
  with `protocol`, never with a wrong PASS.

## Triage — image drift

```bash
# On the spoke that ran the gate:
podman images --format '{{.ID}} {{.Repository}}@{{.Digest}}' | grep devgate
python3 - <<'PY'
import json
reg = json.load(open("container/execution-profiles.json"))
for p in reg.get("profiles", []):
    print(p.get("label"), p.get("image_ref"), p.get("image_manifest_digest"))
PY
```

Decide from the comparison:

| Host has the pinned digest? | Registry record vs pin | Meaning / action |
|---|---|---|
| yes | agree | transient — re-run; a pull race or image-cache eviction |
| yes | disagree | the pin is stale: re-pin from the registry (below) |
| no | — | the image was removed/rebuilt: restore it from the registry, do NOT relax the pin |

A missing image is **never** a pull-and-continue here: the template
notes "SKIPPED (image … not present)" and the hub alerts — an absent
gate reads as *absent*, not as healthy (coh-int-05, adapter default-
deny).

## Triage — protocol

Exit 40 is configuration, not code: a hub and evaluator built for
different contract versions. Compare the requester's `api_version`
(visible in the request it wrote) against this build's `SUPPORTED_API`;
upgrade whichever side is behind. Do not "fix" 40 by editing the schema
to accept the foreign version — the refusal is the contract.

## Re-pinning (the write side of drift)

Pin, registry record, and workflow constant move together (the template's
`DEVGATE_PIN` block refuses to finish otherwise — fail closed on pin
disagreement):

```bash
# from a clean checkout of the pinned ref:
python3 -c "import json; print(json.load(
  open('container/execution-profiles.json'))['profiles'])"
# update COHERENCE_IMAGE_MANIFEST_DIGEST + DEVGATE_PIN in the workflow
# to the registry-served manifest digest for the new ref, then re-run
# the gate; the digest step must go quiet for the drift to be closed.
```

## Pinned by

`tests/test_hub_coherence_exitcodes.py::ExitCodeMatrixTest.test_40_protocol`
(exit 40, `decision: "ERROR"`, `error.class: "protocol"`, guard before
any resolver); the template's structural tests in
`tests/test_hub_coherence_container.py`; the hub-side skip-class
transport in `tests/test_hub_monitor_default_deny.py`
(`test_skipped_keeps_its_own_coherence_class` — a deliberate skip stays
distinct from a failed gate).
