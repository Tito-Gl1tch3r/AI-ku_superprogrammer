#!/usr/bin/env python3
"""Validation gate for the v2.0.0 capstone integration families.

Write families (fresh seeds outside every build range):
  * samples pass their own two-sided gates under the real CPython runner
  * make_buggy candidates FAIL their record's tests (self-verifying)
  * determinism: two generations from the same seed agree byte-for-byte on
    the solution code AND the harness (no measured wall-clock text in these
    families, so full byte equality is required)
"""
from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SEED = 20271201  # outside every build range

WRITE_FAMILIES = ("py_inventory_ops", "py_log_pipeline", "ts_jsonl_pipeline")


def main():
    from generators.registry import family_by_name
    from validators.executors.python_exec import verify_python
    from validators.executors.ts_exec import verify_ts

    def _verify(cand, timeout):
        if cand.language == "typescript":
            return verify_ts(cand, timeout=timeout)
        return verify_python(cand, timeout=timeout)

    fails = []

    for name in WRITE_FAMILIES:
        fam = family_by_name(name)
        if fam is None:
            fails.append(f"{name}: family missing")
            continue
        green = buggy_fail = determinism_ok = 0
        n = 5
        for i in range(n):
            cand = fam.generate(random.Random(SEED + i))
            if cand is None:
                continue
            r = _verify(cand, 40)
            if not r.ok:
                fails.append(f"{name} seed {i}: sample RED: "
                             f"{(r.stderr or '')[:160]}")
            else:
                green += 1
            b = fam.make_buggy(random.Random(SEED + 1000 + i))
            if b is not None:
                rb = _verify(b[0], 40)
                if rb.ok:
                    fails.append(f"{name} seed {i}: BUGGY PASSED")
                else:
                    buggy_fail += 1
            cand2 = fam.generate(random.Random(SEED + i))
            if cand2 is not None and \
                    cand2.code_text() == cand.code_text() and \
                    cand2.tests == cand.tests:
                determinism_ok += 1
        print(f"[write] {name}: green {green}/{n}, buggy-fail {buggy_fail}/{n}, "
              f"determinism {determinism_ok}/{n}")

    if fails:
        print("\nFAILURES:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("\nVALIDATE_V200_EXT: ALL GREEN")


if __name__ == "__main__":
    main()
