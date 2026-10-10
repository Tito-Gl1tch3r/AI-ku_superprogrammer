#!/usr/bin/env python3
"""Validation gate for the v0.8.0 video end-to-end extension.

Write families (fresh seeds outside the build range):
  * samples compile + pass their own tests under the real runner
    (Node type-stripping for TS, CPython for python)
  * make_buggy candidates FAIL their record's tests (self-verifying)
  * determinism: two generations from the same seed agree byte-for-byte
Understand builders: fresh builds carry real evidence (frame numbers from
real renders, measured beat grids, recomputation-consistent answers).
"""
from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SEED = 20270401  # outside every build range

WRITE_FAMILIES = ("media_ts_theme", "media_ts_motion_rules",
                  "media_ts_deterministic_render", "media_ts_beat_grid",
                  "media_render_verify", "media_ts_mv_project")
BUILDERS = ("video_review_verdict", "video_timeline_readout",
            "video_defect_locate")


def main():
    from generators.registry import family_by_name
    from generators.understand.dispatch import build_understand_task
    from validators.executors.ts_exec import verify_ts
    from validators.executors.python_exec import verify_python
    from validators.quality_filters import quality_check

    fails = []

    for name in WRITE_FAMILIES:
        fam = family_by_name(name)
        if fam is None:
            fails.append(f"{name}: family missing")
            continue
        verifier = verify_ts if fam.LANGUAGE == "typescript" else verify_python
        green = buggy_fail = 0
        n = 6
        for i in range(n):
            cand = fam.generate(random.Random(SEED + i))
            if cand is None:
                continue
            r = verifier(cand)
            if not r.ok:
                fails.append(f"{name} seed {i}: sample RED: "
                             f"{(r.stderr or '')[:160]}")
            else:
                green += 1
            b = fam.make_buggy(random.Random(SEED + 1000 + i))
            if b is not None:
                rb = verifier(b[0])
                if rb.ok:
                    fails.append(f"{name} seed {i}: BUGGY PASSED")
                else:
                    buggy_fail += 1
        print(f"[write] {name}: green {green}/{n}, buggy-fail {buggy_fail}/{n}")
        if green == 0:
            fails.append(f"{name}: no green samples")
        if buggy_fail == 0:
            fails.append(f"{name}: no buggy-fail evidence")
        # determinism: same seed -> identical candidate
        c1 = fam.generate(random.Random(SEED + 31))
        c2 = fam.generate(random.Random(SEED + 31))
        if c1 is not None and c2 is not None:
            if (c1.code or "") != (c2.code or ""):
                fails.append(f"{name}: determinism drift")
            else:
                print(f"[write] {name}: determinism OK")

    for tt in BUILDERS:
        ok = evidence = 0
        n = 8
        for i in range(n):
            cand = build_understand_task(tt, random.Random(SEED + i))
            if cand is None:
                continue
            body = cand.code or (cand.answer or "")
            probe = type("P", (), {
                "code_text": lambda s: body, "language": cand.language,
                "domain": cand.domain, "difficulty": cand.difficulty,
                "task": cand.question,
                "verify_method": cand.verify_method})()
            qok, qreason = quality_check(probe)
            if not qok:
                fails.append(f"{tt} seed {i}: quality {qreason}")
                continue
            ok += 1
            notes = cand.verify_notes or {}
            if notes.get("evidence") or notes.get("recompute"):
                evidence += 1
            else:
                fails.append(f"{tt} seed {i}: no evidence notes")
        print(f"[understand] {tt}: quality-ok {ok}/{n}, evidence {evidence}")
        if ok == 0:
            fails.append(f"{tt}: no valid builds")

    print()
    if fails:
        print("FAILURES:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("VIDEO EXT VALIDATION GREEN")


if __name__ == "__main__":
    main()
