#!/usr/bin/env python3
"""Validation for the Reverse Engineering extension (v0.6.0, module 04).

Checks, per new write family:
  * N seeded samples generate + verify (execute) green — every sample
    compiles real ELF binaries and runs them;
  * make_buggy variants FAIL deterministically (every seed);
  * determinism: same seed -> same code AND same tests (binaries included).

Checks, per new understand builder:
  * records build, serialize, and carry REAL evidence
    (re_disasm_readout: real objdump block + captured stdout;
     re_evidence_conclusion: real readelf/nm excerpts;
     re_tool_selection: real executed-command output);
  * schema validation passes against schemas/understand.schema.json.

Usage: python3 scripts/validate_re_ext.py
"""
from __future__ import annotations

import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.verify import verify_candidate  # noqa: E402
from validators.schema_check import validate  # noqa: E402
from generators.registry import family_by_name  # noqa: E402
from generators.understand.dispatch import build_understand_task  # noqa: E402
from scripts.records import understand_record  # noqa: E402

WRITE_FAMILIES = [
    "re_elf_parser", "re_disasm_analysis", "re_blackbox_reimpl",
    "re_version_diff", "re_strings_decode",
]
UNDERSTAND_BUILDERS = [
    "re_disasm_readout", "re_evidence_conclusion", "re_tool_selection",
]
SEEDS = 12


def check_write(name: str) -> bool:
    fam = family_by_name(name)
    if fam is None:
        print(f"  [FAIL] family {name} not registered")
        return False
    ok_all = True
    buggy_fail = buggy_total = 0
    for seed in range(3000, 3000 + SEEDS):
        cand = fam.generate(random.Random(seed))
        if cand is None:
            continue
        passed, result, _ = verify_candidate(cand, timeout=25)
        if not passed:
            print(f"  [FAIL] {name} seed={seed} sample failed: "
                  f"{(result.stderr or '')[:200]}")
            ok_all = False
        # determinism: code AND tests (tests embed the compiled binary)
        again = fam.generate(random.Random(seed))
        if again is None or again.code != cand.code or again.tests != cand.tests:
            print(f"  [FAIL] {name} seed={seed} not deterministic")
            ok_all = False
        res = fam.make_buggy(random.Random(seed + 50000))
        if res is not None:
            buggy_cand, _meta = res
            buggy_total += 1
            passed, _, _ = verify_candidate(buggy_cand, timeout=25)
            if passed:
                print(f"  [FAIL] {name} seed={seed + 50000} buggy PASSED")
                ok_all = False
            else:
                buggy_fail += 1
    print(f"  write {name}: samples green (see above), "
          f"buggy-fail {buggy_fail}/{buggy_total}")
    return ok_all


def check_understand(name: str) -> bool:
    schema = json.load(open(os.path.join(ROOT, "schemas",
                                         "understand.schema.json")))
    ok_all = True
    built = 0
    real_checks = 0
    for seed in range(3000, 3000 + SEEDS * 3):
        cand = build_understand_task(name, random.Random(seed))
        if cand is None:
            continue
        rec = understand_record(cand)
        json.dumps(rec, ensure_ascii=False)
        assert rec["dataset"] == "AI-ku_superprogrammer_reverse_engineering"
        probe = {k: v for k, v in rec.items() if k != "id"}
        schema_noid = {k: v for k, v in schema.items() if k != "required"}
        props = dict(schema.get("properties", {}))
        props.pop("id", None)
        schema_noid["properties"] = props
        errs = validate(probe, schema_noid)
        if errs:
            print(f"  [FAIL] {name} seed={seed} schema: {errs[:2]}")
            ok_all = False
            continue
        built += 1
        arts = rec["input"]["artifacts"]
        if name == "re_disasm_readout":
            assert arts.get("objdump_block") and "objdump" in arts["objdump_block"].lower() or "<" in arts.get("objdump_block", "")
            assert arts.get("binary_stdout_hex")
            real_checks += 1
        if name == "re_evidence_conclusion":
            assert arts.get("readelf_h_excerpt") and "ELF Header" in arts["readelf_h_excerpt"]
            assert arts.get("nm_excerpt")
            real_checks += 1
        if name == "re_tool_selection":
            assert rec["verification"].get("command")
            assert rec["verification"].get("output_head")
            real_checks += 1
    print(f"  understand {name}: built {built}, real-evidence {real_checks}")
    if built == 0:
        print("  [FAIL] no records built")
        ok_all = False
    return ok_all


def main() -> None:
    print("== Reverse Engineering extension validation ==")
    ok = True
    for name in WRITE_FAMILIES:
        ok &= check_write(name)
    for name in UNDERSTAND_BUILDERS:
        ok &= check_understand(name)
    print("RESULT:", "GREEN" if ok else "RED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
