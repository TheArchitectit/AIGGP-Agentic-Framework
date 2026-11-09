#!/usr/bin/env python3
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


# spec: art-bytes-01
def check_bytes(cfg: dict, rows: list, out: list) -> None:
    """art-bytes-01: replication recorded and the restore path exercised."""
    rep = cfg.get("replication")
    if not isinstance(rep, dict):
        rep = {}
    # Trust the declared boolean, not a truthy stand-in. `"false"` is a
    # non-empty string and `1` is truthy, so both recorded a second copy that
    # the manifest did not declare; only `True` is a declaration. A restore
    # timestamp is a non-blank string - whitespace records no exercise.
    if rep.get("present") is not True:
        out.append(Finding("art-bytes-01",
                           "no second copy of the art bytes is recorded",
                           "replication.present must be declared true"))
    restored = rep.get("restore_exercised_at")
    if not isinstance(restored, str) or not restored.strip():
        out.append(Finding("art-bytes-01",
                           "the restore path has never been exercised",
                           "restore_exercised_at must be a non-blank timestamp"))
    for r in rows:
        # A deletion reason is contract-required ("a recorded deletion with a
        # reason"). `not r.get(...)` accepted "   " as a reason; strip first.
        if r.get("deleted"):
            reason = r.get("deletion_reason")
            if not isinstance(reason, str) or not reason.strip():
                out.append(Finding("art-bytes-01",
                                   f"{r.get('id', '?')}: deletion with no recorded reason"))


# spec: art-accept-01, art-accept-02, art-done-01
def check_acceptance(cfg: dict, rows: list, stage_enum: list, out: list) -> None:
    """art-accept-01 / art-accept-02 / art-done-01: a verdict naming a rule; measurements never gate."""
    shape_rules = cfg.get("shape_rules")
    if not isinstance(shape_rules, dict):
        shape_rules = {}
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
                # Strip, the same way check_brief builds its class set: one
                # meaning of "class" across both files. An unstripped
                # 'furniture ' looked up no rule and skipped the compare.
                cls = str(r.get("class", "")).strip()
                want = shape_rules.get(cls)
                # Fail closed. The old `if want and rule != want` skipped the
                # compare whenever the declared rule was absent, null or
                # blank, so an accept verdict naming any rule passed with no
                # rule declared at all. A rule that is not a non-blank string
                # is not a declared rule, so it can never satisfy the check.
                if not isinstance(want, str) or not want.strip() or rule != want:
                    out.append(Finding("art-accept-01",
                                       f"{rid}: verdict rule '{rule}' is not the "
                                       f"declared rule for class '{cls}'"))
        # A measurement that is absent, empty or carries no meaning is not a
        # recorded measurement. `{}` and `null` are falsy, so the old `if meas:`
        # short-circuit skipped both; `{"threshold": 0.9}` with no name or value
        # passed too - a pass point for a quantity nobody named. Meaning is a
        # name plus a value at minimum (design.md, Data shape).
        meas = r.get("measurement")
        if not isinstance(meas, dict) or not meas:
            out.append(Finding("art-accept-02",
                               f"{rid}: no measurement recorded",
                               "a retention measure must be recorded beside the verdict"))
        else:
            name = meas.get("name")
            if not isinstance(name, str) or not name.strip():
                out.append(Finding("art-accept-02",
                                   f"{rid}: measurement carries no name",
                                   "meaning is a name and a value at minimum"))
            if "value" not in meas or meas.get("value") is None:
                out.append(Finding("art-accept-02",
                                   f"{rid}: measurement carries no value",
                                   "meaning is a name and a value at minimum"))
            if "threshold" not in meas:
                out.append(Finding("art-accept-02",
                                   f"{rid}: measurement carries no threshold field",
                                   "null means it cannot gate"))
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


# spec: art-draw-01
def check_draw(cfg: dict, out: list) -> None:
    """art-draw-01: a frame per shipped target from the title's own renderer."""
    targets = cfg.get("targets")
    if not isinstance(targets, list) or not targets:
        out.append(Finding("art-draw-01", "no shipped targets declared"))
        return
    # A non-object `captures` is malformed, not a mapping; `.get` on it was a
    # traceback. Report the missing capture instead.
    caps = cfg.get("captures")
    if not isinstance(caps, dict):
        caps = {}
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
        # The design says the scanner trusts the manifest's declared boolean.
        # A non-boolean is not a boolean: `"false"` is truthy and `1` is not
        # `True`, and both used to satisfy `not cap.get(...)`.
        if cap.get("contains_game_geometry") is not True:
            out.append(Finding("art-draw-01",
                               f"target '{t}': capture contains no game geometry",
                               "contains_game_geometry must be declared true"))
        # A digest is a non-blank string. Whitespace is not a digest, the same
        # way whitespace is not a rights classification or a class.
        sha = cap.get("frame_sha256")
        if not isinstance(sha, str) or not sha.strip():
            out.append(Finding("art-draw-01",
                               f"target '{t}': capture is not digested",
                               "frame_sha256 must be a non-blank digest"))


# spec: art-qty-01
def check_quantity(rows: list, out: list) -> None:
    """art-qty-01: floor shortfall and fidelity failure are separate failures.

    Each is computed and reported on its own: a declared floor that is not met
    fails even when every fidelity verdict is green, and a red verdict fails
    even when the floor is met. Collapsing them into one string (the old
    `SHORTFALL-AND-FIDELITY` line) let a genuine shortfall hide behind a floor
    comparison that was never performed at all.
    """
    # The floor is a title-level number carried on a ledger row in this format.
    # First row that carries the key wins; that is the field's contract, not an
    # accident of the loop.
    floor = None
    for r in rows:
        if "library_floor" in r:
            raw = r["library_floor"]
            # bool is a subclass of int in Python (True == 1), and 1.0 == 1 has
            # the same shape as the published-count bug in art_checks.py. A
            # floor that is not a real integer is its own finding, never a
            # silent skip - a floor nobody can count is not a floor.
            if isinstance(raw, bool) or not isinstance(raw, int):
                out.append(Finding("art-qty-01",
                                   "library_floor is not an integer "
                                   f"(type {type(raw).__name__})",
                                   "a floor must be countable; this one is not"))
            # A negative floor is satisfied by any count, including zero, and
            # was accepted silently. It is not a floor and never lowers one.
            elif raw < 0:
                out.append(Finding("art-qty-01",
                                   f"library_floor is negative ({raw})",
                                   "a floor below zero is not a floor"))
            else:
                floor = raw
            break
    failing = [str(r.get("id", "?")) for r in rows
               if not isinstance(r.get("fidelity"), dict)
               or r["fidelity"].get("verdict") != VERDICT_ACCEPT]
    counted = len(rows)
    if floor is not None:
        shortfall = max(0, floor - counted)
        if shortfall:
            out.append(Finding("art-qty-01",
                               f"floor={floor} counted={counted} shortfall={shortfall}",
                               "a declared floor is a floor: shortfall fails even "
                               "with every fidelity verdict green"))
    if failing:
        # Both conditions are printed (spec.md art-qty-01, "both conditions are
        # printed"). The fidelity branch used to omit the floor, so a reader
        # could not see the floor was met while fidelity failed.
        out.append(Finding("art-qty-01",
                           f"floor={floor if floor is not None else 'none'} "
                           f"counted={counted} fidelity-fail={len(failing)}",
                           ", ".join(failing[:6])))
