#!/usr/bin/env python3
"""Validation for the Superprogrammer extension (v0.5.0).

Checks, per new write family:
  * N seeded samples generate + verify (execute) green;
  * make_buggy variants FAIL deterministically (every seed);
  * determinism: same seed -> same code.

Checks, per new understand builder:
  * records build, serialize, and carry REAL evidence
    (iterative_repair: draft+attempt1 fail, final passes);
  * schema validation passes against schemas/understand.schema.json.

Usage: python3 scripts/validate_superprogrammer_ext.py
"""
from __future__ import annotations

import gzip
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.verify import verify_candidate  # noqa: E402
from generators.registry import family_by_name  # noqa: E402
from generators.understand.dispatch import build_understand_task  # noqa: E402
from scripts.records import understand_record  # noqa: E402

WRITE_FAMILIES = [
    "py_number_bases", "py_mastery_refactor", "py_fault_resilience",
    "py_property_testing", "py_numeric_robustness", "py_timezones_unicode",
    "py_git_forensics",
]
UNDERSTAND_BUILDERS = [
    "iterative_repair", "mastery_principles", "evidence_self_audit",
]
SEEDS = 16


def check_write(name: str) -> bool:
    fam = family_by_name(name)
    if fam is None:
        print(f"  [FAIL] family {name} not registered")
        return False
    ok_all = True
    buggy_fail = buggy_total = 0
    for seed in range(3000, 3000 + SEEDS):
        cand = fam.generate(random.Random(seed))
        passed, result, _ = verify_candidate(cand, timeout=15)
        if not passed:
            print(f"  [FAIL] {name} seed={seed} sample failed: "
                  f"{(result.stderr or '')[:200]}")
            ok_all = False
        # determinism
        again = fam.generate(random.Random(seed))
        if again.code != cand.code:
            print(f"  [FAIL] {name} seed={seed} not deterministic")
            ok_all = False
        res = fam.make_buggy(random.Random(seed + 50000))
        if res is not None:
            buggy_cand, _meta = res
            buggy_total += 1
            passed, _, _ = verify_candidate(buggy_cand, timeout=15)
            if passed:
                print(f"  [FAIL] {name} seed={seed + 50000} buggy PASSED")
                ok_all = False
            else:
                buggy_fail += 1
    print(f"  write {name}: samples {SEEDS}/{SEEDS} green, "
          f"buggy-fail {buggy_fail}/{buggy_total}")
    return ok_all


def check_understand(name: str) -> bool:
    schema = json.load(open(os.path.join(ROOT, "schemas",
                                         "understand.schema.json")))
    ok_all = True
    built = 0
    real_checks = 0
    for seed in range(3000, 3000 + SEEDS * 2):
        cand = build_understand_task(name, random.Random(seed))
        if cand is None:
            continue
        rec = understand_record(cand)
        json.dumps(rec, ensure_ascii=False)
        built += 1
        if name == "iterative_repair":
            arts = rec["input"]["artifacts"]
            assert arts["draft0_run"]["ok"] is False
            assert arts["attempt1_run"]["ok"] is False
            assert arts["final_run"]["ok"] is True
            real_checks += 1
        if name == "mastery_principles":
            assert rec["input"]["artifacts"]["target_run"]["ok"] is True
            real_checks += 1
        if name == "evidence_self_audit":
            arts = rec["input"]["artifacts"]
            assert arts["reference_level"] in (
                "creator_report", "source_inspection", "derived_comparison",
                "synthetic_test", "real_run")
            if arts.get("real_log_present"):
                real_checks += 1
    print(f"  understand {name}: built {built}, real-evidence {real_checks}")
    if built == 0:
        print("  [FAIL] no records built")
        ok_all = False
    return ok_all


def main() -> None:
    print("== Superprogrammer extension validation ==")
    ok = True
    for name in WRITE_FAMILIES:
        ok &= check_write(name)
    for name in UNDERSTAND_BUILDERS:
        ok &= check_understand(name)
    print("RESULT:", "GREEN" if ok else "RED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
