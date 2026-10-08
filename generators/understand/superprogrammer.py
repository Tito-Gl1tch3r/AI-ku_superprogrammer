"""Superprogrammer understand builders: iterative repair, mastery
principles, evidence self-audit.

- iterative_repair: the agentic loop as a record. The model sees its own
  first draft failing (REAL sandbox traceback), a plausible-but-wrong fix
  attempt that still fails (REAL output), and must diagnose the true root
  cause, explain why the attempt missed it, and produce the verified fix.
  Every log line in the artifacts was actually observed by the pipeline.

- mastery_principles: distills the habits of the best programmers
  (including the Opus-authored style mined in v0.4.0) into
  name-the-defect, name-the-principle, apply-the-fix tasks. The target
  code is behavior-verified on a real run; the defect class and entry
  point come from the parameterized mastery write family.

- evidence_self_audit: generalizes the modding evidence ladder to the
  model's own claims: label what actually backs an assertion
  (creator_report < source_inspection < derived_comparison <
  synthetic_test < real_run) and pick the honest next action. Logs marked
  real were produced by the sandbox itself.
"""
from __future__ import annotations

import random

from .builder import _mk
from ..write.craft_families import MasteryRefactorFamily

UNDERSTAND = "AI-ku_superprogrammer_understand"

_EVIDENCE_LADDER = ("creator_report < source_inspection < "
                    "derived_comparison < synthetic_test < real_run")

_MASTERY_FAMILY = MasteryRefactorFamily()

_PRINCIPLES = {
    "mutable_default": ("Functions must be pure at their boundaries: never "
                        "bind a mutable object as a default argument, and "
                        "never mutate what the caller handed you. Use a "
                        "None sentinel and build a local result."),
    "bare_except": ("Catch exactly the failure modes you documented. A bare "
                    "except swallows KeyboardInterrupt and SystemExit and "
                    "turns real bugs into silent wrong behavior."),
    "string_concat_loop": ("Assemble strings in linear time: collect parts "
                           "and join once. Repeated += on a growing string "
                           "re-scans the buffer and is quadratic."),
    "god_function": ("One function, one responsibility. Parse, validate, "
                     "render and log belong in separate testable units, "
                     "with side effects injected rather than hardcoded."),
}


def _run(code: str) -> dict:
    """Run a snippet in the sandbox; return REAL observed evidence."""
    from validators.verify import run_snippet_safely
    result = run_snippet_safely("python", code, timeout=10.0)
    return {"ok": bool(result.ok), "exit_code": result.exit_code,
            "stdout": (result.stdout or "")[-500:],
            "stderr": (result.stderr or "")[-800:]}


def _parse_params(variant: str) -> dict:
    """variant = kind|entry|k=v, k=v -> the generation parameters."""
    params_part = variant.split("|", 2)[2]
    return eval("dict(" + params_part + ")",
                {"__builtins__": {}, "dict": dict}, {})


# --------------------------------------------------------------------------
# iterative_repair
# --------------------------------------------------------------------------

def _repair_scenario(rng: random.Random):
    """Return (scenario dict, probe, params) with parameterized probes."""
    name = rng.choice(("sum_upto", "tag_accumulator", "average_empty",
                       "chunk_overlap"))
    if name == "sum_upto":
        n = rng.choice([5, 7, 9, 12])
        buggy = ("def sum_upto(n):\n"
                 "    total = 0\n"
                 "    for i in range(n):\n"
                 "        total += i\n"
                 "    return total\n")
        attempt1 = ("def sum_upto(n):\n"
                    "    total = 0\n"
                    "    for i in range(1, n):\n"
                    "        total += i\n"
                    "    return total\n")
        correct = ("def sum_upto(n):\n"
                   "    total = 0\n"
                   "    for i in range(1, n + 1):\n"
                   "        total += i\n"
                   "    return total\n")
        probe = (f"assert sum_upto({n}) == {n * (n + 1) // 2}\n"
                 "assert sum_upto(1) == 1\n"
                 "assert sum_upto(0) == 0\n"
                 "print('OK')\n")
        root = "range(n) stops at n-1, so the loop never adds n itself"
        why1 = ("range(1, n) only changes the START; the END is still "
                "exclusive, so n is still missing")
        return dict(name=name, buggy=buggy, attempt1=attempt1,
                    correct=correct, probe=probe, root=root, why1=why1,
                    params={"n": n})
    if name == "tag_accumulator":
        sep = ","
        words = rng.sample(["alpha", "beta", "gamma", "delta", "cache"],
                           3)
        post1 = f"{words[0]}, {words[1]} , {words[2]}"
        post2 = rng.choice(["z", "  solo  ", "last"])
        exp1 = [w.strip() for w in post1.split(sep)]
        exp2 = [post2.strip()]
        buggy = ("def collect_tags(post, tags=[]):\n"
                 "    for tag in post.split(','):\n"
                 "        tags.append(tag.strip())\n"
                 "    return tags\n")
        attempt1 = ("def collect_tags(post, tags=[]):\n"
                    "    tags = tags or []\n"
                    "    for tag in post.split(','):\n"
                    "        tags.append(tag.strip())\n"
                    "    return tags\n")
        correct = ("def collect_tags(post, tags=None):\n"
                   "    result = list(tags) if tags is not None else []\n"
                   "    for tag in post.split(','):\n"
                   "        result.append(tag.strip())\n"
                   "    return result\n")
        probe = (f"a = collect_tags({post1!r})\n"
                 f"assert a == {exp1!r}\n"
                 f"b = collect_tags({post2!r})\n"
                 f"assert b == {exp2!r}, b\n"
                 "print('OK')\n")
        root = ("the default list object is created once at definition "
                "time and shared across every call")
        why1 = ("'tags or []' keeps the SAME shared list because a "
                "non-empty default list is truthy; the state leak is "
                "untouched")
        return dict(name=name, buggy=buggy, attempt1=attempt1,
                    correct=correct, probe=probe, root=root, why1=why1,
                    params={"post1": post1})
    if name == "average_empty":
        nums = sorted(rng.sample(range(1, 99), rng.randint(3, 5)))
        avg = sum(nums) / len(nums)
        buggy = ("def average(nums):\n"
                 "    return sum(nums) / len(nums)\n")
        attempt1 = ("def average(nums):\n"
                    "    if not nums:\n"
                    "        return 0\n"
                    "    return sum(nums) / len(nums)\n")
        correct = ("def average(nums):\n"
                   "    if not nums:\n"
                   "        return None\n"
                   "    return sum(nums) / len(nums)\n")
        probe = (f"assert average({nums!r}) == {avg!r}\n"
                 "assert average([]) is None\n"
                 "print('OK')\n")
        root = ("len([]) is 0, so the division raises ZeroDivisionError "
                "before any value is produced")
        why1 = ("guarding with 'return 0' stops the crash but invents a "
                "value the spec never authorized; empty input must yield "
                "None so callers can tell 'no data' from 0.0")
        return dict(name=name, buggy=buggy, attempt1=attempt1,
                    correct=correct, probe=probe, root=root, why1=why1,
                    params={"nums": nums})
    size = rng.choice([2, 3, 4])
    items = list(range(1, 2 * size + 3))
    expected = [items[i:i + size] for i in range(0, len(items), size)]
    buggy = ("def chunk(items, size):\n"
             "    return [items[i:i + size + 1]\n"
             "            for i in range(0, len(items), size)]\n")
    attempt1 = ("def chunk(items, size):\n"
                "    return [items[i:i + size - 1]\n"
                "            for i in range(0, len(items), size)]\n")
    correct = ("def chunk(items, size):\n"
               "    return [items[i:i + size]\n"
               "            for i in range(0, len(items), size)]\n")
    probe = (f"assert chunk({items!r}, {size}) == {expected!r}\n"
             f"assert chunk([], {size}) == []\n"
             "print('OK')\n")
    root = ("the slice end is exclusive, so +1 pulls in one element of "
            "the next chunk (overlapping windows)")
    why1 = ("overcorrecting to size - 1 drops the chunk's last element; "
            "the arithmetic error is the +1, not the size")
    return dict(name=name, buggy=buggy, attempt1=attempt1, correct=correct,
                probe=probe, root=root, why1=why1,
                params={"size": size})


def build_iterative_repair(rng: random.Random) -> UnderstandCandidate:
    scenario = _repair_scenario(rng)
    run0 = _run(scenario["buggy"] + "\n\n" + scenario["probe"])
    run1 = _run(scenario["attempt1"] + "\n\n" + scenario["probe"])
    run2 = _run(scenario["correct"] + "\n\n" + scenario["probe"])
    if not (not run0["ok"] and not run1["ok"] and run2["ok"]):
        return None
    opener = rng.choice((
        "You are repairing your own code through a real execution loop.",
        "Agentic repair loop: every log below was really observed in the "
        "sandbox.",
    ))
    question = (
        f"{opener} Task: implement `{scenario['name']}` so the probe "
        f"battery passes. Draft 0 failed (log A below). You shipped fix "
        f"attempt 1 and it STILL fails (log B below). Diagnose the true "
        f"root cause, explain precisely why attempt 1 did not address it, "
        f"and return the corrected implementation in target.code.\n\n"
        f"--- draft 0 ---\n{scenario['buggy']}\n"
        f"log A (real): exit {run0['exit_code']}, stderr tail: "
        f"{run0['stderr'][-200:]}\n\n"
        f"--- fix attempt 1 ---\n{scenario['attempt1']}\n"
        f"log B (real): exit {run1['exit_code']}, stderr tail: "
        f"{run1['stderr'][-200:]}"
    )
    answer = (
        f"Root cause: {scenario['root']}.\n"
        f"Why attempt 1 failed: {scenario['why1']}.\n"
        f"Correct fix: change the actual off-by-spec element (see "
        f"target.code); the probe battery then passes on the real sandbox "
        f"run (exit {run2['exit_code']})."
    )
    key_points = [
        "read the REAL traceback before touching the code",
        "a fix that does not change the failing mechanism changes nothing",
        "re-run the same probe battery after every attempt",
        "state the root cause in one sentence before patching",
    ]
    return _mk(
        rng, "iterative_repair", "python", "iterative_repair",
        "engineering", "advanced", question=question, answer=answer,
        code=scenario["buggy"], target_code=scenario["correct"],
        artifacts={"draft0_run": run0, "attempt1_code": scenario["attempt1"],
                   "attempt1_run": run1, "final_run": run2,
                   "params": scenario["params"]},
        target_tests=scenario["probe"], key_points=key_points,
        verify_method="executed",
        verify_notes={"draft0": run0, "attempt1": run1, "final": run2,
                      "all_real": True},
        tags=["agentic", "self-repair", "loop", scenario["name"]],
        variant=f"repair|{scenario['name']}|{scenario['params']}",
        context="Multi-turn self-repair trajectory with real sandbox logs.",
        dataset_hint=UNDERSTAND)


# --------------------------------------------------------------------------
# mastery_principles
# --------------------------------------------------------------------------

def _mastery_probe(kind: str, entry: str, params: dict) -> str:
    """Behavior battery for the corrected code (parameterized)."""
    if kind == "mutable_default":
        raw, sep = params["raw"], params["sep"]
        expected = [w.strip() for w in raw.split(sep)]
        return (f"assert {entry}({raw!r}) == {expected!r}\n"
                f"first = {entry}('p{sep}q')\n"
                f"second = {entry}('z')\n"
                f"assert second == ['z'], second\n"
                f"print('OK')\n")
    if kind == "bare_except":
        key, fallback = params["key"], params["fallback"]
        return (f"assert {entry}({{{key!r}: '{fallback}'}}) == {fallback}\n"
                f"assert {entry}({{}}) == {fallback}\n"
                f"assert {entry}({{{key!r}: None}}) == {fallback}\n"
                f"print('OK')\n")
    if kind == "string_concat_loop":
        rows, delim = params["rows"], params["delim"]
        expected = "".join(delim.join(map(str, row)) + "\n" for row in rows)
        return (f"assert {entry}({rows!r}) == {expected!r}\n"
                f"assert {entry}([]) == ''\n"
                f"print('OK')\n")
    domain, body, sep = params["domain"], params["body"], params["sep"]
    fn = f"handle_{domain}"
    parts = body.split(sep)
    name = parts[0].strip().lower()
    email = parts[1].strip().lower() if len(parts) > 1 else ""
    ok = len(name) > 0 and "@" in email and "." in email
    card = f"name={name};email={email};valid={'true' if ok else 'false'}"
    return (f"log = []\n"
            f"assert {fn}({body!r}, sink=log) is {ok}\n"
            f"assert log == [{card!r}]\n"
            f"print('OK')\n")


def build_mastery_principles(rng: random.Random) -> UnderstandCandidate:
    cand = _MASTERY_FAMILY.generate(rng)
    kind = cand.variant.split("|")[0]
    entry = cand.variant.split("|")[1]
    params = _parse_params(cand.variant)
    principle = _PRINCIPLES[kind]
    legacy_start = cand.task.index("```python\n") + len("```python\n")
    legacy_end = cand.task.index("\n```", legacy_start)
    legacy = cand.task[legacy_start:legacy_end]
    probe = _mastery_probe(kind, entry, params)
    run_good = _run(cand.code + "\n\n" + probe)
    if not run_good["ok"]:
        return None
    question = (
        "You are reviewing your own draft like a senior engineer. Here is "
        f"working-but-poor code:\n```python\n{legacy}\n```\n"
        "1) Name the defect class, 2) state the craft principle it "
        f"violates, and 3) return a production-quality rewrite in "
        f"target.code that preserves the observable behavior of "
        f"`{entry}` (the bundled behavior battery must pass) while "
        "removing the defect mechanism itself. Justify every structural "
        "change in one line each."
    )
    answer = (
        f"Defect class: {kind}. Principle: {principle}\n"
        f"The rewrite keeps the public entry point `{entry}` stable, "
        f"removes the defect structurally (not cosmetically), and passes "
        f"the behavior battery on a real run (exit "
        f"{run_good['exit_code']}). Structural changes: type hints and a "
        f"docstring state the contract; the defect mechanism is gone, not "
        f"hidden; side effects are injectable where the battery needs it."
    )
    key_points = [
        "behavior preservation is verified by execution, not by reading",
        f"the principle: {principle.split(':')[0].lower()}",
        "cosmetic patches that keep the mechanism are rejected",
        "public call sites stay stable across the refactor",
    ]
    return _mk(
        rng, "mastery_principles", "python", "mastery_principles",
        "engineering", "advanced", question=question, answer=answer,
        code=legacy, target_code=cand.code,
        artifacts={"behavior_probe": probe, "target_run": run_good,
                   "params": params},
        key_points=key_points,
        verify_method="executed",
        verify_notes={"target_run": run_good, "real": True},
        tags=["craft", "mastery", kind],
        variant=cand.variant,
        context="Senior-level self-review distilled from master authors "
                "and the Opus-style guide (docs/OPUS_STYLE.md).",
        dataset_hint=UNDERSTAND)


# --------------------------------------------------------------------------
# evidence_self_audit
# --------------------------------------------------------------------------

def build_evidence_self_audit(rng: random.Random) -> UnderstandCandidate:
    """Label the evidence behind a claim; degrade it when it is not real."""
    scenarios = []

    # real_run: actually run a snippet right now; the log is genuine.
    probe_kind = rng.choice(("add", "dedupe", "clamp"))
    if probe_kind == "add":
        code = ("def add(a, b):\n    return a + b\n\n"
                "assert add(2, 3) == 5\nassert add(-1, 1) == 0\n"
                "print('2/2 asserts passed')\n")
        claim = "add(a, b) passes its assertion battery"
    elif probe_kind == "dedupe":
        code = ("def dedupe(xs):\n    out = []\n"
                "    for x in xs:\n        if x not in out:\n"
                "            out.append(x)\n    return out\n\n"
                "assert dedupe([1, 1, 2]) == [1, 2]\n"
                "assert dedupe([]) == []\n"
                "print('2/2 asserts passed')\n")
        claim = "dedupe(xs) keeps first occurrences and drops duplicates"
    else:
        code = ("def clamp(v, lo, hi):\n    return max(lo, min(hi, v))\n\n"
                "assert clamp(15, 0, 10) == 10\n"
                "assert clamp(-5, 0, 10) == 0\n"
                "print('2/2 asserts passed')\n")
        claim = "clamp(v, lo, hi) never returns values outside [lo, hi]"
    real = _run(code)
    if real["ok"]:
        scenarios.append({
            "claim": claim,
            "log": (f"sandbox run: exit {real['exit_code']}, stdout: "
                    f"{real['stdout'].strip()!r}"),
            "level": "real_run",
            "action": "claim stands; record the run id and inputs in the "
                      "field note",
        })
    big_rows = rng.choice(["1M", "5M", "250k"])
    pct = rng.choice([30, 40, 60])
    scenarios.append({
        "claim": f"the exporter handles {big_rows}-row files without "
                 "memory blowups",
        "log": ("the author says 'I tried it on my machine once and it "
                "was fine'; no command, no log, no dataset in the note"),
        "level": "creator_report",
        "action": "do not trust it; schedule a synthetic_test with a "
                  f"generated {big_rows}-row fixture and a memory cap",
    })
    scenarios.append({
        "claim": "parse_config rejects unknown keys",
        "log": ("code review: the function body contains `if key not in "
                "ALLOWED: raise ValueError(...)` on the hot path"),
        "level": "source_inspection",
        "action": ("promote to synthetic_test: call parse_config with an "
                   "unknown key and observe the raise"),
    })
    scenarios.append({
        "claim": f"the cache improves latency by {pct}%",
        "log": ("two benchmark tables derived from the same theory model, "
                "no measurement ran; numbers come from a formula in the "
                "PR description"),
        "level": "derived_comparison",
        "action": ("treat as hypothesis; measure with a real workload "
                   "before quoting the number"),
    })
    scenarios.append({
        "claim": "migration preserves every row",
        "log": ("test suite: row-count equality asserted for three "
                "fixture datasets inside CI (green)"),
        "level": "synthetic_test",
        "action": ("good for CI; before touching production data, run a "
                   "checksummed dry-run on a real snapshot (real_run)"),
    })
    scenarios.append({
        "claim": "the crash cannot happen because the guard is upstream",
        "log": ("reading the call graph: the guard sits in every entry "
                "point found by grep; no dynamic dispatch found"),
        "level": "source_inspection",
        "action": ("keep the defensive check; write the "
                   "failure-prediction test that would catch a future "
                   "bypass"),
    })
    scenarios.append({
        "claim": "mod works on the target build",
        "log": ("field note shows a video of the feature working; build "
                "hash of the target not recorded"),
        "level": "creator_report",
        "action": ("re-run against the pinned build hash and log it; "
                   "otherwise the note cannot be trusted"),
    })
    scenario = rng.choice(scenarios)
    question = (
        "You made the following claim about your own work and must audit "
        f"it honestly. Claim: {scenario['claim']!r}. Evidence actually on "
        f"record: {scenario['log']!r}. Evidence ladder (weakest to "
        f"strongest): {_EVIDENCE_LADDER}. 1) Label the claim's current "
        "evidence level. 2) Decide the next action that would make the "
        "claim trustworthy, or state that it already stands. Never "
        "inflate: a claim backed only by a story is a creator_report."
    )
    answer = (
        f"Level: {scenario['level']}.\n"
        f"Next action: {scenario['action']}.\n"
        "Rule: label what EXISTS in the record, not what you remember "
        "doing; upgrade only by adding stronger evidence, never by "
        "re-describing the same evidence."
    )
    key_points = [
        f"ladder: {_EVIDENCE_LADDER}",
        "labels attach to recorded evidence, not to memory",
        "the upgrade path is new evidence, not new words",
        "real_run beats everything; without a run, say so",
    ]
    return _mk(
        rng, "evidence_self_audit", "python", "evidence_self_audit",
        "engineering", rng.choice(["intermediate", "advanced"]),
        question=question, answer=answer,
        artifacts={"claim": scenario["claim"], "log": scenario["log"],
                   "reference_level": scenario["level"],
                   "real_log_present": scenario["level"] == "real_run"},
        key_points=key_points,
        verify_method="authored_verified",
        verify_notes={"labels_validated_against_ladder": True,
                      "scenario_level": scenario["level"],
                      "real_run_log": real if real["ok"] else None},
        tags=["honesty", "evidence", "self-audit"],
        variant=f"audit|{scenario['level']}|{scenario['claim'][:40]}",
        context="Generalizes mod_evidence_levels to the model's own claims.",
        dataset_hint=UNDERSTAND)
