#!/usr/bin/env python3
"""Validation gate for the v0.9.0 evolution families (roadmap closures).

Write families (fresh seeds outside the build range):
  * samples pass their own tests under the real CPython runner
  * make_buggy candidates FAIL their record's tests (self-verifying)
  * determinism: two generations from the same seed agree on the code
    (task text may embed measured timings for profile_guided_optimization,
    so byte equality is asserted on the solution code, as in v0.8.0)
Understand hooks are wired via SUPPORTS/make_buggy for the generic builders
(no dedicated understand builders in this wave).
"""
from __future__ import annotations

import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SEED = 20270901  # outside every build range

WRITE_FAMILIES = ("git_merge_conflict", "flaky_test_forensics",
                  "sql_schema_migration", "sdk_docs_integration",
                  "repo_feature_insertion", "profile_guided_optimization",
                  "doctest_authoring")


def main():
    from generators.registry import family_by_name
    from validators.executors.python_exec import verify_python

    fails = []

    for name in WRITE_FAMILIES:
        fam = family_by_name(name)
        if fam is None:
            fails.append(f"{name}: family missing")
            continue
        green = buggy_fail = 0
        n = 5
        for i in range(n):
            cand = fam.generate(random.Random(SEED + i))
            if cand is None:
                continue
            r = verify_python(cand, timeout=30)
            if not r.ok:
                fails.append(f"{name} seed {i}: sample RED: "
                             f"{(r.stderr or '')[:160]}")
            else:
                green += 1
            b = fam.make_buggy(random.Random(SEED + 1000 + i))
            if b is not None:
                rb = verify_python(b[0], timeout=30)
                if rb.ok:
                    fails.append(f"{name} seed {i}: BUGGY PASSED")
                else:
                    buggy_fail += 1
        print(f"[write] {name}: green {green}/{n}, buggy-fail {buggy_fail}/{n}")
        if green == 0:
            fails.append(f"{name}: no green samples")
        if buggy_fail == 0:
            fails.append(f"{name}: no buggy-fail evidence")
        # determinism: same seed -> identical solution code/files
        c1 = fam.generate(random.Random(SEED + 31))
        c2 = fam.generate(random.Random(SEED + 31))
        if c1 is not None and c2 is not None:
            same = (c1.code or "") == (c2.code or "")
            if same and c1.files and c2.files:
                same = ([(f.path, f.content) for f in c1.files] ==
                        [(f.path, f.content) for f in c2.files])
            if not same:
                fails.append(f"{name}: determinism drift")
            else:
                print(f"[write] {name}: determinism OK")
        else:
            fails.append(f"{name}: determinism probe returned None")

    print()
    if fails:
        print("FAILURES:")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("EVOLUTION EXT VALIDATION GREEN")


if __name__ == "__main__":
    main()
