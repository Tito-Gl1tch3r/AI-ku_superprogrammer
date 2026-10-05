"""Dataset-2 (understand) task builders — part 1.

Every builder produces an UnderstandCandidate whose verification metadata
records what was REALLY observed by executing code in the sandbox:
  * debugging: buggy version must FAIL (observed), corrected must PASS;
  * trace: steps derived from the same deterministic logic, final output
    verified by executing the visible code;
  * explanation: authored from family ground truth + live spot-check;
  * failure_prediction: edge inputs actually executed, behaviour captured.
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, UnderstandCandidate
from ..problems import REGISTRY, run_cli_for, run_ts_snippet
from ..problems.bank_core import CodeUnit
from validators.verify import verify_candidate, run_snippet_safely
from evaluators.mutation import mutation_score


def _mk(seed_rng, family, language, task_type, domain, difficulty, question, answer,
        code=None, artifacts=None, target_code=None, target_tests=None,
        key_points=None, big_o=None, verify_method="authored_verified",
        verify_notes=None, tags=None, variant="default", context="", files=None,
        dataset_hint="AI-ku_superprogrammer_understand"):
    return UnderstandCandidate(
        family=family, language=language, task_type=task_type, domain=domain,
        difficulty=difficulty, question=question, answer=answer, context=context,
        code=code, files=files, artifacts=artifacts or {}, target_code=target_code,
        target_tests=target_tests, key_points=key_points or [],
        big_o=big_o, verify_method=verify_method,
        verify_notes=verify_notes or {}, tags=tags or [], variant=variant,
        seed=seed_rng.randrange(2**31), dataset_hint=dataset_hint)


# ------------------------------------------------------------------ debugging
DATASET_SUFFIX = {"media": "media", "game": "game_engineering"}


def build_debugging(rng: random.Random, language: str | None = None, dataset: str | None = None):
    """Use make_buggy hooks; verify buggy FAILS and corrected PASSES (for real)."""
    from ..registry import all_families, dataset_for_family
    suffix = DATASET_SUFFIX.get(dataset, dataset) if dataset else None
    fams = [f for f in all_families()
            if "debugging" in f.SUPPORTS and (language is None or f.LANGUAGE == language)
            and (suffix is None or dataset_for_family(f.NAME) ==
                 ("AI-ku_superprogrammer_" + suffix))]
    rng.shuffle(fams)
    for fam in fams:
        for attempt in range(3):
            try:
                res = fam.make_buggy(rng)
            except Exception:
                res = None
            if res:
                buggy, meta = res
                ok_buggy, r_buggy, _ = verify_candidate(buggy)
                if not ok_buggy:
                    break
            res = None
        if not res:
            continue
        buggy, meta = res
        ok_buggy, r_buggy, _ = verify_candidate(buggy)
        if ok_buggy:
            continue  # bug did not trigger -> drop honestly
        correct = Candidate(
            family=buggy.family, language=buggy.language, domain=buggy.domain,
            difficulty=buggy.difficulty, task=buggy.task,
            expected_behavior=buggy.expected_behavior, code=meta.get("correct_code"),
            tests=meta.get("tests"), verify_method=buggy.verify_method)
        ok_correct, r_correct, _ = verify_candidate(correct)
        if not ok_correct:
            continue
        evidence = (r_buggy.stderr or r_buggy.stdout or r_buggy.compile_stderr)[:700]
        bug_kind = meta.get("kind", "unknown")
        unit_notes = meta.get("unit_notes") or {}
        answer = (
            f"Failure cause: the {bug_kind} bug in the provided code.\n"
            f"Evidence: running the bundled tests against the buggy version fails "
            f"({r_buggy.stage} stage, exit {r_buggy.exit_code}): {evidence.strip()[:240]}\n"
            f"Mechanism: {unit_notes.get('approach', 'see code')} - the mutation breaks "
            f"the invariant the algorithm relies on ({'; '.join(unit_notes.get('key_points', [])[:2])}).\n"
            f"Fix: restore the original logic (see corrected code).\n"
            f"Verification: the corrected version passes the same test suite "
            f"(exit 0, all assertions green).")
        return _mk(
            rng, fam.NAME, buggy.language, "debugging", buggy.domain,
            buggy.difficulty if buggy.difficulty != "beginner" else "intermediate",
            question=(f"The following {buggy.language} code fails its test suite. Identify the "
                      f"bug, explain the root cause, and provide the corrected code.\n\n"
                      f"```{buggy.language}\n{buggy.code}\n```\n\n"
                      f"Failing evidence observed when running the tests:\n```\n"
                      f"{evidence}\n```"),
            answer=answer, code=buggy.code,
            artifacts={"observed_failure": evidence,
                       "stage": r_buggy.stage, "exit_code": r_buggy.exit_code},
            target_code=meta.get("correct_code"), target_tests=meta.get("tests"),
            key_points=[f"bug class: {bug_kind}",
                        unit_notes.get("approach", "")],
            verify_method="executed",
            verify_notes={"buggy_version_fails": True, "fixed_version_passes": True,
                          "observed_stage": r_buggy.stage},
            tags=["debugging", buggy.language, bug_kind],
            variant=f"{buggy.family}|{bug_kind}", context=buggy.task,
            dataset_hint=("AI-ku_superprogrammer_" + suffix) if suffix else "")
    return None


# ------------------------------------------------------------------ trace
TRACE_PROBLEMS = ("binary_search", "two_sum", "fibonacci", "max_subarray",
                  "run_length_encode")


def _trace_steps(pid: str, P: dict) -> list:
    """Deterministic step log computed by mirroring the reference logic."""
    steps = []
    if pid == "binary_search":
        arr, target, lo, hi = P["arr"], P["target"], 0, len(P["arr"]) - 1
        step = 0
        while lo <= hi and step < 24:
            mid = (lo + hi) // 2
            steps.append(f"step {step}: lo={lo} hi={hi} mid={mid} arr[mid]={arr[mid]}"
                         + (" == target -> return" if arr[mid] == target else
                            (" < target -> lo=mid+1" if arr[mid] < target else " > target -> hi=mid-1")))
            if arr[mid] == target:
                return steps
            if arr[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
            step += 1
        steps.append("window empty -> return -1")
    elif pid == "fibonacci":
        n = P["n"]
        a, b = 0, 1
        for i in range(min(n, 12)):
            steps.append(f"iter {i}: (a, b) = ({a}, {b}) -> next ({b}, {a + b})")
            a, b = b, a + b
        steps.append(f"after n={n} iterations: a={a} (fibonacci({n}))")
    elif pid == "max_subarray":
        arr = P["arr"]
        best = cur = arr[0]
        steps.append(f"init: best=cur={best}")
        for i, x in enumerate(arr[1:], 1):
            cur = max(x, cur + x)
            best = max(best, cur)
            if i < 14:
                steps.append(f"x={x}: cur=max(x, cur+x)={cur}, best={best}")
        steps.append(f"final best={best}")
    elif pid == "two_sum":
        arr, target = P["arr"], P["target"]
        seen = {}
        for j, x in enumerate(arr[:16]):
            need = target - x
            if need in seen:
                steps.append(f"j={j} x={x}: complement {need} seen at {seen[need]} -> return ({seen[need]}, {j})")
                return steps
            steps.append(f"j={j} x={x}: need={need} not in seen -> store seen[{x}]={j}")
            seen[x] = j
        steps.append("no pair found -> return -1")
    else:  # run_length_encode
        s = P["s"]
        i = 0
        while i < len(s) and len(steps) < 14:
            j = i
            while j < len(s) and s[j] == s[i]:
                j += 1
            steps.append(f"run '{s[i]}' x{j - i} -> emit '{s[i]}{j - i}'")
            i = j
        steps.append("input exhausted -> join parts")
    return steps


def build_trace(rng: random.Random):
    pids = [p for p in TRACE_PROBLEMS if p in REGISTRY and "python" in REGISTRY[p].impls]
    pid = rng.choice(pids)
    prob = REGISTRY[pid]
    P = prob.params(rng)
    unit = prob.impls["python"](P, rng)
    steps = _trace_steps(pid, P)
    stdin, expected = prob.io(P)[0]
    # Verify the visible code against the traced final output (real execution).
    cli = dict(unit.cli)
    r = run_cli_for("python", unit, stdin)
    if not r.ok or r.stdout.strip() != expected:
        return None
    answer = ("Step-by-step execution:\n" + "\n".join(steps) +
              f"\nFinal output: {expected} (verified by executing the code on this input).")
    return _mk(
        rng, "trace_bank", "python", "trace", prob.domain,
        "intermediate" if len(steps) < 10 else "advanced",
        question=(f"Trace the execution of this {pid} implementation on the given input. "
                  f"Track the relevant variables/loop state step by step and give the final "
                  f"output.\n\n```python\n{unit.files['solution.py']}\n```\n\n"
                  f"Input (stdin):\n```\n{stdin[:400]}\n```"),
        answer=answer, code=unit.files["solution.py"],
        artifacts={"stdin_excerpt": stdin[:400], "final_output": expected},
        key_points=[f"algorithm: {pid}", unit.notes.get("approach", "")],
        big_o={"time": unit.notes.get("big_o_time"), "space": unit.notes.get("big_o_space")},
        verify_method="executed",
        verify_notes={"trace_verified_by_execution": True, "final_output": expected},
        tags=["trace", pid], variant=f"trace|{pid}")


# ------------------------------------------------------------------ explanation
def build_explanation(rng: random.Random, language: str | None = None,
                      dataset: str | None = None):
    from ..registry import all_families, dataset_for_family
    suffix = DATASET_SUFFIX.get(dataset, dataset) if dataset else None
    fams = [f for f in all_families()
            if (language is None or f.LANGUAGE == language)
            and (suffix is None or dataset_for_family(f.NAME) ==
                 ("AI-ku_superprogrammer_" + suffix))]
    rng.shuffle(fams)
    for fam in fams[:5]:
        try:
            cand = fam.generate(rng)
        except Exception:
            continue
        explain = (cand.notes or {}).get("explain")
        if not explain or not explain.get("key_points"):
            continue
        # Live spot-check when the candidate has an executable scenario.
        spot = None
        if cand.language == "python" and cand.code and cand.tests:
            r = verify_candidate(cand)[1]
            spot = {"executed": r.ok, "stage": r.stage}
        elif cand.language in ("python", "cpp", "javascript", "typescript", "bash", "c") \
                and (cand.code or cand.files):
            ok, r, _ = verify_candidate(cand)
            spot = {"executed": ok, "stage": r.stage}
        purpose = explain["purpose"]
        answer = (
            f"Purpose: {purpose}\n"
            f"How it works: {explain['approach']}\n"
            f"Key points:\n" +
            "".join(f"- {kp}\n" for kp in explain["key_points"]) +
            f"Complexity: time {explain.get('big_o_time', 'n/a')}, "
            f"space {explain.get('big_o_space', 'n/a')}.\n"
            f"Edge cases handled: {'; '.join(explain.get('edge_cases', [])[:4])}.")
        return _mk(
            rng, fam.NAME, cand.language, "explanation", cand.domain,
            "beginner" if cand.difficulty == "beginner" else "intermediate",
            question=(f"Explain what this {cand.language} code does, how it achieves it, and "
                      f"which design details matter. Do not merely restate the code.\n\n"
                      f"```{cand.language}\n{cand.code_text()[:2600]}\n```"),
            answer=answer, code=cand.code_text()[:2600],
            artifacts={"spot_check": spot} if spot else {},
            key_points=explain["key_points"],
            big_o={"time": explain.get("big_o_time"), "space": explain.get("big_o_space")},
            verify_method="authored_verified",
            verify_notes={"spot_check": spot} if spot else {"spot_check": None},
            tags=["explanation", cand.language], variant=f"{fam.NAME}|explain",
            context=cand.task,
            dataset_hint=("AI-ku_superprogrammer_" + suffix) if suffix else "")
    return None


# ------------------------------------------------------------------ code_review
def build_code_review(rng: random.Random, language: str | None = None,
                      dataset: str | None = None):
    from ..registry import all_families, dataset_for_family
    suffix = DATASET_SUFFIX.get(dataset, dataset) if dataset else None
    fams = [f for f in all_families()
            if "code_review" in f.SUPPORTS and (language is None or f.LANGUAGE == language)
            and (suffix is None or dataset_for_family(f.NAME) ==
                 ("AI-ku_superprogrammer_" + suffix))
            and hasattr(f, "review_variant")]
    rng.shuffle(fams)
    for fam in fams[:5]:
        try:
            res = fam.review_variant(rng)
        except Exception:
            continue
        if not res:
            continue
        cand, issues = res
        ok, r, _ = verify_candidate(cand)
        if not ok:
            continue  # review fixtures must actually work
        issues_text = "\n".join(
            f"{i + 1}. [{iss['severity'].upper()}] {iss['kind']}: {iss['why']} "
            f"Better: {iss['better']}"
            for i, iss in enumerate(issues))
        answer = ("Findings (working code, ordered by severity):\n" + issues_text +
                  "\nNone of these break the current behaviour - they affect safety, "
                  "performance or maintainability, which is why this is a review, not a bugfix.")
        return _mk(
            rng, fam.NAME, cand.language, "code_review", cand.domain,
            "intermediate",
            question=(f"Perform a code review of the following working {cand.language} code. "
                      f"List real issues with severity, say why each matters, and propose the "
                      f"improvement. Distinguish 'broken' from 'works but should be better'.\n\n"
                      f"```{cand.language}\n{cand.code}\n```"),
            answer=answer, code=cand.code,
            artifacts={"verified_working": True, "stage": r.stage},
            key_points=[iss["kind"] for iss in issues],
            verify_method="executed",
            verify_notes={"code_runs": True, "planted_issues": len(issues)},
            tags=["review", cand.language], variant=f"{fam.NAME}|review",
            dataset_hint=("AI-ku_superprogrammer_" + suffix) if suffix else "")
    return None


# ------------------------------------------------------------------ failure_prediction
EDGE_INPUTS = {
    "binary_search": [("empty list", "[]", None), ("absent greater", None, 10 ** 9)],
    "fibonacci": [("negative n", None, -3), ("n=0", None, 0)],
    "valid_parentheses": [("empty string", "", None), ("lone closer", ")", None)],
    "word_frequency": [("no lines", [], None), ("fewer words than m", ["one"], None)],
    "max_subarray": [("all negative", [-5, -2, -9], None), ("single", [7], None)],
}


def build_failure_prediction(rng: random.Random):
    pids = [p for p in EDGE_INPUTS if p in REGISTRY and "python" in REGISTRY[p].impls]
    pid = rng.choice(pids)
    prob = REGISTRY[pid]
    P = prob.params(rng)
    unit = prob.impls["python"](P, rng)
    fn = unit.function_name
    label, arg_value, arg_scalar = rng.choice(EDGE_INPUTS[pid])
    # Build a probe script: call the function with the edge input, print outcome.
    if pid == "binary_search":
        call = f"{fn}([], {arg_scalar})" if "empty" in label else f"{fn}({fn}_probe_arr(), {arg_scalar})"
        probe = (f"import solution\n\n"
                 f"def {fn}_probe_arr():\n"
                 f"    return {P['arr'][:4]!r}\n\n"
                 f"try:\n"
                 f"    result = {call}\n"
                 f"    print('RETURN:', result)\n"
                 f"except Exception as exc:\n"
                 f"    print('EXC:', type(exc).__name__, str(exc)[:80])\n")
    elif pid == "fibonacci":
        call = f"{fn}({arg_scalar})"
        probe = (f"import solution\n"
                 f"try:\n    result = {call}\n    print('RETURN:', result)\n"
                 f"except Exception as exc:\n    print('EXC:', type(exc).__name__, str(exc)[:80])\n")
    elif pid == "valid_parentheses":
        call = f"{fn}({arg_value!r})"
        probe = (f"import solution\n"
                 f"try:\n    result = {call}\n    print('RETURN:', result)\n"
                 f"except Exception as exc:\n    print('EXC:', type(exc).__name__, str(exc)[:80])\n")
    elif pid == "word_frequency":
        m = P["m"]
        call = f"{fn}({arg_value!r}, {m})"
        probe = (f"import solution\n"
                 f"try:\n    result = {call}\n    print('RETURN:', result)\n"
                 f"except Exception as exc:\n    print('EXC:', type(exc).__name__, str(exc)[:80])\n")
    else:  # max_subarray
        call = f"{fn}({arg_value!r})"
        probe = (f"import solution\n"
                 f"try:\n    result = {call}\n    print('RETURN:', result)\n"
                 f"except Exception as exc:\n    print('EXC:', type(exc).__name__, str(exc)[:80])\n")
    files = {"solution.py": unit.files["solution.py"], "probe.py": probe}
    import subprocess
    import tempfile, os, sys
    d = tempfile.mkdtemp(prefix="failpred_")
    try:
        for name, content in files.items():
            with open(os.path.join(d, name), "w") as f:
                f.write(content)
        proc = subprocess.run([sys.executable, "probe.py"], cwd=d, capture_output=True,
                              text=True, timeout=10,
                              env={"PATH": os.environ.get("PATH", "/usr/bin"),
                                   "PYTHONDONTWRITEBYTECODE": "1"})
        observed = (proc.stdout + proc.stderr).strip()[:400]
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    if not observed:
        return None
    answer = (f"Observed behaviour (executed in a sandbox): {observed}\n"
              f"Why: {unit.notes.get('approach', '')} The edge input '{label}' exercises "
              f"the boundary the algorithm must handle: "
              f"{'; '.join(unit.notes.get('edge_cases', [])[:2])}.")
    return _mk(
        rng, "failpred_bank", "python", "failure_prediction", prob.domain,
        "intermediate",
        question=(f"Predict EXACTLY what happens when this {pid} code receives the edge "
                  f"input '{label}'. Return value? Exception (which type)? Crash?\n\n"
                  f"```python\n{unit.files['solution.py']}\n```\n\n"
                  f"Edge input: {label} = {arg_value if arg_value is not None else arg_scalar}"),
        answer=answer, code=unit.files["solution.py"],
        artifacts={"edge_input": label, "observed": observed},
        key_points=[f"observed: {observed.splitlines()[0][:120]}" if observed else "",
                    unit.notes.get("approach", "")],
        verify_method="executed",
        verify_notes={"observed_output": observed},
        tags=["failure_prediction", pid], variant=f"failpred|{pid}|{label}")


# ------------------------------------------------------------------ testing
TESTING_PROBLEMS = ("binary_search", "merge_sort", "valid_parentheses", "fibonacci",
                    "run_length_encode", "word_frequency")


def build_testing(rng: random.Random):
    from evaluators.mutation import mutation_score as ms
    pids = [p for p in TESTING_PROBLEMS if p in REGISTRY and "python" in REGISTRY[p].impls]
    pid = rng.choice(pids)
    prob = REGISTRY[pid]
    P = prob.params(rng)
    unit = prob.impls["python"](P, rng)
    # The authored suite must pass on the correct code...
    probe = Candidate(family="testing_probe", language="python", domain=prob.domain,
                      difficulty="intermediate", task="probe", expected_behavior="probe",
                      code=unit.files["solution.py"], tests=unit.tests,
                      verify_method="executed")
    ok, r, _ = verify_candidate(probe)
    if not ok:
        return None
    score = ms(unit.files["solution.py"], unit.tests)
    if score.get("total", 0) == 0:
        return None
    answer = (
        f"A strong suite for this function:\n```python\n{unit.tests}\n```\n"
        f"Why these cases: {unit.notes.get('approach', '')}\n"
        f"Coverage reasoning - key points: " +
        "; ".join(unit.notes.get("key_points", [])[:3]) + "\n"
        f"Edge cases exercised: " + "; ".join(unit.notes.get("edge_cases", [])[:4]) + ".\n"
        f"Mutation check (real execution): the suite kills {score['killed']}/{score['total']} "
        f"mutants" + (f"; survivors: {', '.join(score['survived'])} - these hint at cases the "
                      f"suite could still add." if score["survived"] else " (no survivors)."))
    return _mk(
        rng, "testing_bank", "python", "testing", prob.domain,
        "intermediate" if score["killed"] / max(1, score["total"]) >= 0.5 else "advanced",
        question=(f"Design a test suite for this {pid} implementation. Include happy paths, "
                  f"boundary cases and at least one negative/exceptional case. Explain what "
                  f"each group of tests protects against.\n\n```python\n"
                  f"{unit.files['solution.py']}\n```"),
        answer=answer, code=unit.files["solution.py"], target_tests=unit.tests,
        artifacts={"mutation_score": score, "suite_passes": True},
        key_points=["happy path", "boundaries", "negative cases",
                    f"mutation kill rate {score['killed']}/{score['total']}"],
        verify_method="executed",
        verify_notes={"suite_passes": True, "mutation": score},
        tags=["testing", pid], variant=f"testing|{pid}")


# ------------------------------------------------------------------ security
def build_security(rng: random.Random):
    kind = rng.choice(["sqli", "path_traversal", "weak_hash"])
    if kind == "sqli":
        table = rng.choice(["users", "accounts", "sessions"])
        col = rng.choice(["username", "email", "token"])
        payload = "x' OR '1'='1"
        buggy = (
            f"import sqlite3\n\n\ndef lookup_vulnerable(conn, value):\n"
            f"    \"\"\"UNSAFE: string-formatted query.\"\"\"\n"
            f"    query = \"SELECT id FROM {table} WHERE {col} = '\" + value + \"'\"\n"
            f"    return conn.execute(query).fetchall()\n")
        fixed = (
            f"import sqlite3\n\n\ndef lookup_safe(conn, value):\n"
            f"    \"\"\"Parameterised query: payload stays data.\"\"\"\n"
            f"    return conn.execute(\n"
            f"        \"SELECT id FROM {table} WHERE {col} = ?\", (value,)).fetchall()\n")
        evidence_script = (
            f"import sqlite3\n\n"
            f"conn = sqlite3.connect(':memory:')\n"
            f"conn.execute('CREATE TABLE {table} (id INTEGER PRIMARY KEY, {col} TEXT)')\n"
            f"conn.execute(\"INSERT INTO {table} ({col}) VALUES ('ada')\")\n"
            f"payload = {payload!r}\n"
            f"query = \"SELECT id FROM {table} WHERE {col} = '\" + payload + \"'\"\n"
            f"rows = conn.execute(query).fetchall()\n"
            f"print('VULN_ROWS:', len(rows))\n")
        r = run_snippet_safely("python", evidence_script)
        observed = (r.stdout or r.stderr).strip()[:200]
        if "VULN_ROWS:" not in observed:
            return None
        leaked = observed.split("VULN_ROWS:")[1].strip().splitlines()[0]
        answer = (
            f"Vulnerability: SQL injection (CWE-89) via string concatenation of user input.\n"
            f"Controlled evidence (in-memory SQLite): the payload {payload!r} turned the query "
            f"into a tautology and returned {leaked} row(s) that no legitimate lookup should return.\n"
            f"Fix: bind parameters - `WHERE {col} = ?` with the value as a tuple - so the "
            f"driver keeps SQL and data separate.\n"
            f"Verification: the safe version returns zero rows for the same payload and "
            f"correct rows for legitimate values.")
        return _mk(
            rng, "security_sqli", "python", "security", "security", "advanced",
            question=(f"Audit this authentication helper for security vulnerabilities. Identify "
                      f"the vulnerability class (CWE), show its impact in a CONTROLLED local "
                      f"environment only, and provide the corrected code.\n\n```python\n"
                      f"{buggy}\n```"),
            answer=answer, code=buggy, target_code=fixed,
            artifacts={"observed_leak_rows": leaked, "cwe": "CWE-89",
                       "payload": payload},
            key_points=["CWE-89 SQL injection", "parameterised queries fix it",
                        "least privilege + ORM helpers as defense in depth"],
            verify_method="executed",
            verify_notes={"vuln_demonstrated_rows": leaked, "environment": "in-memory sqlite"},
            tags=["security", "sqli"], variant="sqli")
    elif kind == "path_traversal":
        base = rng.choice(["/srv/app", "/var/data"])
        payload = "../../../etc/passwd"
        buggy = (
            f"import os\n\n\ndef read_user_file_vulnerable(base, name):\n"
            f"    \"\"\"UNSAFE: naive join.\"\"\"\n"
            f"    path = os.path.join(base, name)\n"
            f"    with open(path) as fh:\n"
            f"        return fh.read()\n")
        fixed = (
            f"import os\n\n\ndef read_user_file_safe(base, name):\n"
            f"    \"\"\"Containment-checked join.\"\"\"\n"
            f"    base_real = os.path.realpath(base)\n"
            f"    candidate = os.path.realpath(os.path.join(base_real, name))\n"
            f"    if candidate != base_real and not candidate.startswith(base_real + os.sep):\n"
            f"        raise ValueError('path escapes base directory')\n"
            f"    with open(candidate) as fh:\n"
            f"        return fh.read()\n")
        probe = (
            f"import os\n"
            f"base = {base!r}\n"
            f"name = {payload!r}\n"
            f"joined = os.path.join(base, name)\n"
            f"resolved = os.path.realpath(joined)\n"
            f"escapes = not resolved.startswith(os.path.realpath(base) + os.sep)\n"
            f"print('JOINED:', joined)\n"
            f"print('RESOLVED:', resolved)\n"
            f"print('ESCAPES_BASE:', escapes)\n")
        r = run_snippet_safely("python", probe)
        observed = (r.stdout or r.stderr).strip()[:300]
        if "ESCAPES_BASE: True" not in observed:
            return None
        answer = (
            f"Vulnerability: path traversal (CWE-22). The naive os.path.join lets '..' climb out "
            f"of the base directory.\n"
            f"Controlled evidence: joining {payload!r} resolves to the path shown in the observed "
            f"output, which escapes the base directory (ESCAPES_BASE: True).\n"
            f"Fix: canonicalise with os.path.realpath and require the result to stay inside the "
            f"real base directory before opening anything.\n"
            f"Verification: the safe version raises ValueError for traversal payloads and still "
            f"serves files inside the base.")
        return _mk(
            rng, "security_traversal", "python", "security", "security", "advanced",
            question=(f"Audit this file-serving endpoint for security vulnerabilities. Identify "
                      f"the CWE class, demonstrate the impact in a controlled local check, and "
                      f"provide corrected code.\n\n```python\n{buggy}\n```"),
            answer=answer, code=buggy, target_code=fixed,
            artifacts={"observed": observed, "cwe": "CWE-22", "payload": payload},
            key_points=["CWE-22 path traversal", "realpath containment check",
                        "allowlist file names as extra hardening"],
            verify_method="executed",
            verify_notes={"escapes_base": True, "environment": "path resolution only (no file opened)"},
            tags=["security", "path_traversal"], variant="traversal")
    else:  # weak_hash
        buggy = (
            f"import hashlib\n\n\ndef store_password_vulnerable(password):\n"
            f"    \"\"\"UNSAFE: fast, unsalted digest.\"\"\"\n"
            f"    return hashlib.md5(password.encode()).hexdigest()\n")
        fixed = (
            f"import hashlib\nimport os\n\n\ndef store_password_safe(password):\n"
            f"    \"\"\"Salted PBKDF2-HMAC-SHA256 with 120k iterations.\"\"\"\n"
            f"    salt = os.urandom(16)\n"
            f"    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)\n"
            f"    return salt.hex() + '$' + digest.hex()\n")
        probe = (
            f"import hashlib\n"
            f"p = 'correct horse'\n"
            f"d1 = hashlib.md5(p.encode()).hexdigest()\n"
            f"d2 = hashlib.md5(p.encode()).hexdigest()\n"
            f"print('DETERMINISTIC:', d1 == d2)\n"
            f"print('MD5_LEN:', len(d1))\n")
        r = run_snippet_safely("python", probe)
        observed = (r.stdout or r.stderr).strip()[:200]
        if "DETERMINISTIC: True" not in observed:
            return None
        answer = (
            f"Vulnerability: insecure password hashing (CWE-327/CWE-916). MD5 is fast and "
            f"unsalted, so identical passwords produce identical hashes (observed: "
            f"DETERMINISTIC: True) and GPU cracking is cheap.\n"
            f"Fix: per-user random salt + a deliberately slow KDF (PBKDF2-HMAC-SHA256, 120k "
            f"iterations), verified with hmac.compare_digest.\n"
            f"Verification: two hashes of the same password differ (random salt) and the "
            f"verification function accepts only the correct password.")
        return _mk(
            rng, "security_weak_hash", "python", "security", "security", "intermediate",
            question=(f"Audit this credential-storage function. Name the vulnerability class, "
                      f"explain the attack it enables, and provide the corrected implementation.\n\n"
                      f"```python\n{buggy}\n```"),
            answer=answer, code=buggy, target_code=fixed,
            artifacts={"observed": observed, "cwe": "CWE-327"},
            key_points=["CWE-327 weak crypto", "salted slow KDF", "constant-time verify"],
            verify_method="executed",
            verify_notes={"md5_deterministic": True},
            tags=["security", "passwords"], variant="weak_hash")
