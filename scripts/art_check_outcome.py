#!/usr/bin/env python3
# spec: art-bytes-01, art-accept-01, art-accept-02, art-done-01, art-draw-01
# spec: art-qty-01
"""art_check_outcome.py - did the work survive, get accepted, and reach a player.

Declaration checks (brief, stages, ledger, rights) live in `art_checks.py`.
These four ask the question the contract exists to ask: are the bytes
replicated and restore-tested, did a human accept the fidelity against a named
rule, does every shipped target draw the asset from its own renderer, and is
the quantity floor being reported honestly while fidelity is red.

Every function appends Finding objects to an out-list; none of them prints or
exits. Split at the source soft limit, the way the limit is meant to be used.
"""
from __future__ import annotations

from art_checks import VERDICT_ACCEPT, VERDICT_REJECT, Finding


def check_bytes(cfg: dict, rows: list, out: list) -> None:
    """art-bytes-01: replication recorded and the restore path exercised."""
    rep = cfg.get("replication") or {}
    if not rep.get("present"):
        out.append(Finding("art-bytes-01",
                           "no second copy of the art bytes is recorded"))
    if not rep.get("restore_exercised_at"):
        out.append(Finding("art-bytes-01",
                           "the restore path has never been exercised"))
    for r in rows:
        if r.get("deleted") and not r.get("deletion_reason"):
            out.append(Finding("art-bytes-01",
                               f"{r.get('id', '?')}: deletion with no recorded reason"))


def check_acceptance(cfg: dict, rows: list, stage_enum: list, out: list) -> None:
    """art-accept-01 / art-accept-02 / art-done-01: a verdict naming a rule; measurements never gate."""
    shape_rules = cfg.get("shape_rules") or {}
    for r in rows:
        rid = str(r.get("id", "?"))
        fid = r.get("fidelity") if isinstance(r.get("fidelity"), dict) else {}
        verdict = fid.get("verdict")
        if verdict not in (VERDICT_ACCEPT, VERDICT_REJECT):
            out.append(Finding("art-accept-01",
                               f"{rid}: no fidelity verdict (needs accept|reject)"))
        rule = str(fid.get("rule", ""))
        if verdict == VERDICT_ACCEPT:
            if not rule:
                out.append(Finding("art-accept-01",
                                   f"{rid}: accept verdict names no class rule"))
            else:
                cls = str(r.get("class", ""))
                want = shape_rules.get(cls)
                if want and rule != want:
                    out.append(Finding("art-accept-01",
                                       f"{rid}: verdict rule '{rule}' is not the "
                                       f"declared rule for class '{cls}'"))
        meas = r.get("measurement") if isinstance(r.get("measurement"), dict) else {}
        if meas:
            if "threshold" not in meas:
                out.append(Finding("art-accept-02",
                                   f"{rid}: measurement carries no threshold field",
                                   "null means it cannot gate"))
            elif meas.get("threshold") is None:
                pass  # correctly labelled as non-gating
        stage = str(r.get("stage") or "")
        # A named stage outside the enum is an accept-01 problem; a blank stage
        # is a ledger problem (raised there) and must not be laundered into a
        # non-finding by a falsy short-circuit here.
        if stage and stage_enum and stage not in stage_enum:
            out.append(Finding("art-accept-01",
                               f"{rid}: stage '{stage}' is not a declared pipeline stage"))
        # Fail closed: no `and stage` guard. An accepted row that is not at the
        # terminal stage is not done, and a blank stage is not the terminal one.
        if verdict == VERDICT_ACCEPT and stage_enum and stage != stage_enum[-1]:
            out.append(Finding("art-done-01",
                               f"{rid}: accepted but not at the terminal stage "
                               f"'{stage_enum[-1]}' - done means visible in a shipped build"))


def check_draw(cfg: dict, out: list) -> None:
    """art-draw-01: a frame per shipped target from the title's own renderer."""
    targets = cfg.get("targets") or []
    if not targets:
        out.append(Finding("art-draw-01", "no shipped targets declared"))
        return
    caps = cfg.get("captures") or {}
    for t in targets:
        cap = caps.get(t)
        if not cap:
            out.append(Finding("art-draw-01",
                               f"target '{t}' has no rendered-frame capture",
                               "a target that draws nothing is a failing target"))
            continue
        # Allowlist, not a blacklist. A blacklist of one magic string
        # ('dcc-preview') made every other label - 'blender', 'blender-preview',
        # 'dcc', or a capture with no renderer field at all - a green run. The
        # contract says "from the title's own renderer"; only that value is
        # evidence, and anything else is a DCC preview wearing a name.
        renderer = cap.get("renderer")
        if renderer != "title-own":
            shown = "absent" if renderer in (None, "") else repr(str(renderer))
            out.append(Finding("art-draw-01",
                               f"target '{t}': capture is not from the title's own "
                               f"renderer (renderer={shown}, need 'title-own')",
                               "a DCC preview offered as evidence is rejected"))
        if not cap.get("contains_game_geometry"):
            out.append(Finding("art-draw-01",
                               f"target '{t}': capture contains no game geometry"))
        if not cap.get("frame_sha256"):
            out.append(Finding("art-draw-01",
                               f"target '{t}': capture is not digested"))


def check_quantity(rows: list, out: list) -> None:
    """art-qty-01: the floor cannot be green while fidelity is red."""
    floor = None
    for r in rows:
        if isinstance(r.get("library_floor"), int):
            floor = r["library_floor"]
            break
    failing = [str(r.get("id", "?")) for r in rows
               if (r.get("fidelity") or {}).get("verdict") != VERDICT_ACCEPT]
    if floor is not None and len(rows) >= floor and failing:
        out.append(Finding("art-qty-01",
                           f"floor {floor} met with {len(failing)} asset(s) failing fidelity",
                           "shortfall and fidelity failure are separate quantities"))
    if failing:
        out.append(Finding("art-qty-01",
                           f"SHORTFALL-AND-FIDELITY: counted={len(rows)} "
                           f"fidelity-fail={len(failing)}",
                           ", ".join(failing[:6])))
