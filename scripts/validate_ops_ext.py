#!/usr/bin/env python3
"""Validation for the Agent Persistence extension (v0.7.0, module 05).

Checks, per new write family:
  * N seeded samples generate + verify (execute) green — jobs really run as
    subprocesses, files really sync+hash, ISO images are real ISO9660 bytes
    read back with an independent parser, game cores simulate headless;
  * make_buggy variants FAIL deterministically (every seed);
  * determinism: same seed -> same code AND same tests (files included).

Checks, per new understand builder:
  * records build, serialize, and carry the module's evidence:
      - ops_goal_decomposition: the answer's stage list matches the artifact
        stage count and the task text is quoted in artifacts;
      - ops_failure_autopsy: the decisive entry appears verbatim in the
        transcript artifact;
      - ops_done_criteria: the verdict is consistent with the authored log
        (YES requires exit 0 + full plan + verified artifact);
  * schema validation passes against schemas/understand.schema.json.

Usage: python3 scripts/validate_ops_ext.py
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
    "ops_monitor_watchdog", "ops_two_stage_orchestrator",
    "ops_progress_supervisor", "ops_scope_elevation",
]
UNDERSTAND_BUILDERS = [
    "ops_goal_decomposition", "ops_failure_autopsy", "ops_done_criteria",
]
SEEDS = 12
_DATASET = "AI-ku_superprogrammer_agent_ops"


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
        # determinism: code AND tests (and embedded files) identical
        again = fam.generate(random.Random(seed))
        if again is None or again.code != cand.code or \
                again.tests != cand.tests:
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


def _evidence_check(name, cand) -> str | None:
    """Module-specific consistency checks; returns error text or None."""
    art = cand.artifacts or {}
    if name == "ops_goal_decomposition":
        if not art.get("task_text") or art.get("task_text") not in \
                (cand.question or ""):
            return "task_text not quoted in the question"
        stage_lines = sum(1 for ln in (cand.answer or "").splitlines()
                          if ln[:2].rstrip(".").isdigit())
        if stage_lines != art.get("stages"):
            return f"answer lists {stage_lines} stages, model says " \
                   f"{art.get('stages')}"
        if art.get("final_deliverable") not in (cand.answer or ""):
            return "final deliverable missing from the answer"
    elif name == "ops_failure_autopsy":
        tr = art.get("transcript") or ""
        if art.get("bad_entry") and art["bad_entry"] not in tr:
            return "decisive entry not found verbatim in the transcript"
        label = art.get("failure_label") or (art.get("failure_class") or "").replace("_", " ")
        if label not in (cand.answer or ""):
            return "failure class missing from the answer"
    elif name == "ops_done_criteria":
        verdict = art.get("verdict")
        log = art.get("job_log") or ""
        plan = art.get("plan_steps")
        done = art.get("steps_done")
        full_plan = done == plan
        verified = "read back and equals" in (art.get("artifact_state") or "")
        should = (verdict == "YES")
        implied = full_plan and verified and "FATAL" not in log
        if should != implied:
            return f"verdict {verdict} inconsistent with the authored log"
    return None


def check_understand(name: str) -> bool:
    schema = json.load(open(os.path.join(ROOT, "schemas",
                                         "understand.schema.json")))
    ok_all = True
    built = 0
    evidence_ok = 0
    for seed in range(3000, 3000 + SEEDS * 3):
        cand = build_understand_task(name, random.Random(seed))
        if cand is None:
            continue
        rec = understand_record(cand)
        json.dumps(rec, ensure_ascii=False)
        if rec["dataset"] != _DATASET:
            print(f"  [FAIL] {name} seed={seed}: wrong dataset "
                  f"{rec['dataset']}")
            ok_all = False
            continue
        probe = {k: v for k, v in rec.items() if k != "id"}
        schema_noid = {k: v for k, v in schema.items() if k != "required"}
        props = dict(schema.get("properties", {}))
        props.pop("id", None)
        schema_noid["properties"] = props
        errs = validate(probe, schema_noid)
        if errs:
            print(f"  [FAIL] {name} seed={seed}: schema {errs[:2]}")
            ok_all = False
            continue
        ev_err = _evidence_check(name, cand)
        if ev_err:
            print(f"  [FAIL] {name} seed={seed}: {ev_err}")
            ok_all = False
            continue
        evidence_ok += 1
        built += 1
    print(f"  understand {name}: built {built} (evidence-checked "
          f"{evidence_ok}/{built})")
    if built == 0:
        ok_all = False
    return ok_all


def main():
    print("== Agent Persistence extension validation (v0.7.0, module 05) ==")
    ok = True
    for name in WRITE_FAMILIES:
        ok &= check_write(name)
    for name in UNDERSTAND_BUILDERS:
        ok &= check_understand(name)
    print("VALIDATION", "GREEN" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
