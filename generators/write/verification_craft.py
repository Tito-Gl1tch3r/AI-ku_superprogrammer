"""v1.0.0 module 06: verification & testing craft (write dataset).

Four families whose ground truth is REAL two-sided execution:

  * py_mutation_kill        write tests that kill every listed mutant kind;
                            the suite is executed against behavior-different
                            mutants built by a deterministic mutator table
  * py_golden_master        characterize a quirky legacy function; the suite
                            must pass on the original and fail on a measured
                            behavior-altered refactor
  * py_test_debugging       repair a broken suite without weakening it: it
                            must pass on the correct module AND still fail on
                            planted regressions
  * py_regression_minimize  ddmin-style minimization against a real
                            reproducer predicate (subsequence, repro, cap,
                            1-minimality)

Methodology mirrors evolution_families.py: candidates are project-mode
(files: module.py + solution.py, entry solution.py, standalone harness in
`tests`), every expectation is MEASURED at generate time, and every planted
defect is self-verified to break its gate before a variant is published.
Harness templates are instantiated with repr() placeholder replacement
(never str.format) so regex backslashes survive verbatim.
"""
from __future__ import annotations

import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

from generators.core import Candidate, Family, FileSpec, register

# --------------------------------------------------------------------------
# shared: subprocess runner + project-mode harness check (PYTHONHASHSEED=0)
# --------------------------------------------------------------------------

_ENV_KEYS = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "LANG": "C.UTF-8", "PYTHONHASHSEED": "0",
             "PYTHONDONTWRITEBYTECODE": "1"}


def _run_py(files_map: dict, runner_src: str, timeout: float = 12.0):
    """Write files + runner, run it, return (returncode, stdout, stderr)."""
    d = tempfile.mkdtemp(prefix="aiku_vc_")
    try:
        for name, content in files_map.items():
            p = os.path.join(d, name)
            os.makedirs(os.path.dirname(p) or d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        rp = os.path.join(d, "_runner.py")
        with open(rp, "w", encoding="utf-8") as f:
            f.write(runner_src)
        env = dict(_ENV_KEYS)
        env["HOME"] = d
        env["TMPDIR"] = d
        try:
            proc = subprocess.run([sys.executable, "_runner.py"], cwd=d,
                                  env=env, capture_output=True, text=True,
                                  timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -9, "", "timeout"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _project_ok(files: dict, harness_src: str, timeout: float = 12.0) -> bool:
    """True iff module.py + solution.py + harness pass as a project record."""
    rc, _out, _err = _run_py(files, harness_src, timeout=timeout)
    return rc == 0


# --------------------------------------------------------------------------
# shared: deterministic mutator table (behavior-different mutant selection)
# --------------------------------------------------------------------------

MUTATOR_TABLE = {
    "lt_to_le": (r"(?<![<>=!])<(?!=)", "<="),
    "le_to_lt": (r"(?<![<>=!])<=(?!=)", "<"),
    "gt_to_ge": (r"(?<![<>=!])>(?!=)", ">="),
    "ge_to_gt": (r"(?<![<>=!])>=(?!=)", ">"),
    "plus_to_minus": (r"(?<![+\-*/=])\+(?![+=])", "-"),
    "minus_to_plus": (r"(?<![+\-*/=])-(?![=>])", "+"),
    "and_to_or": (r"\band\b", "or"),
    "or_to_and": (r"\bor\b", "and"),
    "zero_to_one": (r"\b0\b", "1"),
    "one_to_two": (r"\b1\b", "2"),
}


def _mutate_first(src: str, kind: str):
    """Return src with the FIRST line the kind's regex changes, else None."""
    pat, repl = MUTATOR_TABLE[kind]
    for line in src.splitlines():
        new_line = re.sub(pat, repl, line)
        if new_line != line:
            return src.replace(line, new_line, 1)
    return None


def _behavior_differs(orig_src: str, mutated_src: str, battery, fn_name):
    """True iff the mutated module gives a different answer on the battery."""
    probe = ("import importlib.util, sys\n"
             "def load(path, name):\n"
             "    spec = importlib.util.spec_from_file_location(name, path)\n"
             "    m = importlib.util.module_from_spec(spec)\n"
             "    spec.loader.exec_module(m)\n"
             "    return m\n"
             "a = load('orig.py', 'orig')\n"
             "b = load('mut.py', 'mut')\n"
             "inputs = __BATTERY__\n"
             "for args in inputs:\n"
             "    try:\n"
             "        ra = getattr(a, __FN__)(*args)\n"
             "    except Exception as e:\n"
             "        ra = ('exc', type(e).__name__)\n"
             "    try:\n"
             "        rb = getattr(b, __FN__)(*args)\n"
             "    except Exception as e:\n"
             "        rb = ('exc', type(e).__name__)\n"
             "    if ra != rb:\n"
             "        print('__DIFF__')\n"
             "        break\n"
             "else:\n"
             "    print('__SAME__')\n")
    probe = probe.replace("__BATTERY__", repr(battery)).replace("__FN__", repr(fn_name))
    rc, out, _err = _run_py({"orig.py": orig_src, "mut.py": mutated_src},
                            probe, timeout=10.0)
    return rc == 0 and "__DIFF__" in out


def _pick_mutant(orig_src: str, kind: str, battery, fn_name):
    """Deterministic: first behavior-different mutation for this kind."""
    mutated = _mutate_first(orig_src, kind)
    if mutated is None:
        return None
    if not _behavior_differs(orig_src, mutated, battery, fn_name):
        return None
    return mutated


# --------------------------------------------------------------------------
# shared: module shapes for logic functions (mutation_kill, test_debugging)
# --------------------------------------------------------------------------

_FN_NAME_POOLS = {
    "tiered_fee": ["tiered_fee", "delivery_cost", "parcel_price", "freight_for"],
    "window_score": ["window_score", "in_range_flag", "zone_check", "span_flag"],
    "shard": ["shard_count", "chunk_total", "bucket_count", "partition_no"],
}


def _shape_tiered_fee(rng):
    w2 = rng.randrange(3, 7)
    w10 = w2 + rng.randrange(4, 9)
    w20 = w10 + rng.randrange(6, 12)
    return ("tiered_fee", w2, w10, w20)


def _shape_window_score(rng):
    lo = rng.randrange(-8, 9)
    hi = lo + rng.randrange(6, 20)
    return ("window_score", lo, hi)


def _shape_shard(rng):
    min_shards = rng.randrange(1, 5)
    return ("shard", min_shards)


_SHAPES = {"tiered_fee": _shape_tiered_fee,
           "window_score": _shape_window_score,
           "shard": _shape_shard}


def _logic_module_src(shape_key, fn, params):
    """Real module source per shape: deliberately mixes comparisons,
    arithmetic, and/or, and 0/1 literals so several mutant kinds are
    behavior-different on the battery."""
    if shape_key == "tiered_fee":
        w2, w10, w20 = params
        return (
            f"def {fn}(weight, express, insured):\n"
            "    if weight <= 0:\n"
            "        raise ValueError('bad weight')\n"
            "    cost = 5\n"
            "    if weight > " + str(w10) + ":\n"
            "        cost = 12\n"
            "    elif weight > " + str(w2) + ":\n"
            "        cost = 8\n"
            "    rebate = 0\n"
            "    if weight > " + str(w20) + ":\n"
            "        rebate = 1\n"
            "    cost = cost - rebate\n"
            "    if express and insured:\n"
            "        cost = cost + 6\n"
            "    elif express or insured:\n"
            "        cost = cost + 3\n"
            "    return cost\n")
    if shape_key == "window_score":
        lo, hi = params
        return (
            f"def {fn}(v, lo=" + str(lo) + ", hi=" + str(hi) + ", strict=False):\n"
            "    if lo >= hi:\n"
            "        return -1\n"
            "    if strict:\n"
            "        if v > lo and v < hi:\n"
            "            return 1\n"
            "        return 0\n"
            "    if v >= lo and v <= hi:\n"
            "        return 1\n"
            "    return 0\n")
    if shape_key == "shard":
        min_shards = params[0]
        return (
            f"def {fn}(total, size, min_shards=" + str(min_shards) + "):\n"
            "    if size <= 0:\n"
            "        raise ValueError('bad size')\n"
            "    if total < 0:\n"
            "        raise ValueError('bad total')\n"
            "    q, r = divmod(total, size)\n"
            "    if r > 0:\n"
            "        q = q + 1\n"
            "    if q < min_shards:\n"
            "        q = min_shards\n"
            "    return q\n")
    raise ValueError(shape_key)


def _logic_battery(shape_key, params, rng):
    """Boundary grid: every cut value +/- 1, exception triggers, both
    boolean branches, and values where 0/1 and +- matter."""
    if shape_key == "tiered_fee":
        w2, w10, w20 = params
        weights = sorted({0, 1, 2, w2 - 1, w2, w2 + 1, w10 - 1, w10,
                          w10 + 1, w20 - 1, w20, w20 + 1})
        flags = [(False, False), (True, False), (False, True), (True, True)]
        return [(w, e, i) for w in weights for e, i in flags]
    if shape_key == "window_score":
        lo, hi = params
        vals = sorted({lo - 1, lo, lo + 1, hi - 1, hi, hi + 1,
                       (lo + hi) // 2, 0, 1})
        pairs = [(lo, hi, False), (lo, hi, True),
                 (hi, lo, False), (lo, lo, False), (lo, lo, True)]
        return [(v, a, b, s) for v in vals for a, b, s in pairs]
    if shape_key == "shard":
        min_shards = params[0]
        totals = (0, 1, 7, 30, 100)
        sizes = (0, 1, 3, 4, 10)
        minss = (min_shards - 1, min_shards, min_shards + 2, 0, 1)
        return [(t, s, m) for t in totals for s in sizes for m in sorted(set(minss))]
    raise ValueError(shape_key)


# --------------------------------------------------------------------------
# shared: mutant selection = FIRST behavior-different line mutation
# (the generator and every harness re-derive it identically: deterministic)
# --------------------------------------------------------------------------

def _pick_behavior_mutant(src: str, kind: str, battery, fn_name):
    """First line-mutation of `kind` that changes behavior on the battery."""
    pat, repl = MUTATOR_TABLE[kind]
    for line in src.splitlines():
        new_line = re.sub(pat, repl, line)
        if new_line == line:
            continue
        mutated = src.replace(line, new_line, 1)
        if _behavior_differs(src, mutated, battery, fn_name):
            return mutated
    return None


# --------------------------------------------------------------------------
# shared harness building blocks (standalone scripts, placeholders via repr)
# --------------------------------------------------------------------------

_SUITE_RUNNER = '''import shutil
import subprocess
import sys
import tempfile
import os


def _suite_passes_on(mod_src):
    """Run the candidate's own suite against an alternative module source."""
    d = tempfile.mkdtemp(prefix="vcsub_")
    try:
        with open(os.path.join(d, "module.py"), "w", encoding="utf-8") as f:
            f.write(mod_src)
        with open(os.path.join(d, "solution.py"), "w", encoding="utf-8") as f:
            f.write(open("solution.py", encoding="utf-8").read())
        with open(os.path.join(d, "_t.py"), "w", encoding="utf-8") as f:
            f.write("import solution\\n"
                    "solution.run_tests()\\n"
                    "print('__SUITES_OK__')\\n")
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "_t.py"], cwd=d, env=env,
                           capture_output=True, text=True, timeout=6)
        return p.returncode == 0 and "__SUITES_OK__" in p.stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)
'''

_HARNESS_MUTKILL = r'''"""Two-sided gate: candidate suite must pass on the original module and
kill every required mutant kind. Mutant selection is deterministic: the
first line-mutation of the kind that changes behavior on the battery."""
import re
import shutil
import subprocess
import sys
import tempfile
import os

REQUIRED_KINDS = __KINDS__

MUTATORS = __MUTATORS__

BATTERY = __BATTERY__

FN = __FN__


def _first_behavior_mutant(src, kind):
    pat, repl = MUTATORS[kind]
    for line in src.splitlines():
        new_line = re.sub(pat, repl, line)
        if new_line == line:
            continue
        mutated = src.replace(line, new_line, 1)
        if _differs(src, mutated):
            return mutated
    return None


def _differs(orig_src, mutated_src):
    import importlib.util

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    a = load("module.py", "vc_orig")
    d = tempfile.mkdtemp(prefix="vcmut_")
    try:
        mp = os.path.join(d, "mut.py")
        with open(mp, "w", encoding="utf-8") as f:
            f.write(mutated_src)
        b = load(mp, "vc_mut")
        for args in BATTERY:
            try:
                ra = getattr(a, FN)(*args)
            except Exception as e:
                ra = ("exc", type(e).__name__)
            try:
                rb = getattr(b, FN)(*args)
            except Exception as e:
                rb = ("exc", type(e).__name__)
            if ra != rb:
                return True
        return False
    finally:
        shutil.rmtree(d, ignore_errors=True)

__SUITE_RUNNER__

import solution  # noqa: E402

solution.run_tests()

survivors = []
for kind in REQUIRED_KINDS:
    mutated = _first_behavior_mutant(open("module.py", encoding="utf-8").read(),
                                     kind)
    if mutated is None:
        print("KIND-UNUSABLE: " + kind)
        raise SystemExit(1)
    if _suite_passes_on(mutated):
        survivors.append(kind)
if survivors:
    print("SURVIVORS: " + ", ".join(survivors))
    raise SystemExit(1)
print("ALL_MUTANTS_KILLED")
'''

_HARNESS_GOLDEN = r'''"""Two-sided gate: candidate suite must pass on the original legacy
module and fail on the measured behavior-altered refactor."""
import os
import sys

REFACTOR_SRC = __REFACTOR__

__SUITE_RUNNER__

import solution  # noqa: E402

solution.run_tests()

if _suite_passes_on(REFACTOR_SRC):
    print("REFACTOR_UNDETECTED")
    raise SystemExit(1)
print("REFACTOR_CAUGHT")
'''

_HARNESS_TESTFIX = r'''"""Two-sided gate: repaired suite must pass on the correct module and
still fail on each planted regression variant."""
import os
import sys

BAD_VARIANTS = __BAD_VARIANTS__

__SUITE_RUNNER__

import solution  # noqa: E402

solution.run_tests()

for i, bad_src in enumerate(BAD_VARIANTS):
    if _suite_passes_on(bad_src):
        print("REGRESSION_UNDETECTED: %d" % i)
        raise SystemExit(1)
print("SUITE_FIXED_AND_STRONG")
'''

_HARNESS_MINIMIZE = r'''"""Property gate for regression minimization against a real reproducer:
subsequence, reproduction, length cap and 1-minimality are all checked by
calling the module's own predicate."""
from module import is_repro  # noqa: E402

import solution  # noqa: E402

STEPS = __STEPS__

CAP = __CAP__


def _is_subsequence(needle, haystack):
    it = iter(haystack)
    return all(x in it for x in needle)


result = solution.minimize_repro(list(STEPS))
if not isinstance(result, list) or not all(isinstance(s, str) for s in result):
    print("BAD-TYPE")
    raise SystemExit(1)
if not _is_subsequence(result, STEPS):
    print("NOT-SUBSEQUENCE")
    raise SystemExit(1)
if not is_repro(result):
    print("NOT-REPRODUCIBLE")
    raise SystemExit(1)
if len(result) > CAP:
    print("TOO-LONG: %d > %d" % (len(result), CAP))
    raise SystemExit(1)
for i in range(len(result)):
    reduced = result[:i] + result[i + 1:]
    if is_repro(reduced):
        print("NOT-1-MINIMAL at %d" % i)
        raise SystemExit(1)
print("MINIMAL-REPRO-OK")
'''


def _harness(template: str, suite_runner_block: bool, **literals) -> str:
    """Instantiate a harness template with repr()-escaped placeholders."""
    out = template
    if suite_runner_block:
        out = out.replace("__SUITE_RUNNER__", _SUITE_RUNNER)
    for key, value in literals.items():
        token = "__" + key.upper() + "__"
        assert token in out, f"placeholder {token} not in template"
        out = out.replace(token, repr(value))
    for key in literals:
        assert ("__" + key.upper() + "__") not in out, \
            f"placeholder {key} left unreplaced"
    assert "__SUITE_RUNNER__" not in out, "suite runner block not injected"
    return out


def _run_module_fn(src: str, fn_name: str, battery):
    """Measure fn(*args) for each battery args tuple; returns list of results
    where each result is either the value or ('exc', ExcName)."""
    probe = ("import importlib.util\n"
             "spec = importlib.util.spec_from_file_location('m', 'module.py')\n"
             "m = importlib.util.module_from_spec(spec)\n"
             "spec.loader.exec_module(m)\n"
             "battery = __BATTERY__\n"
             "for args in battery:\n"
             "    try:\n"
             "        r = getattr(m, __FN__)(*args)\n"
             "    except Exception as e:\n"
             "        r = ('exc', type(e).__name__)\n"
             "    print(repr(r))\n")
    probe = probe.replace("__BATTERY__", repr(battery)).replace("__FN__", repr(fn_name))
    rc, out, _err = _run_py({"module.py": src}, probe, timeout=10.0)
    if rc != 0:
        return None
    results = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(eval(line, {"__builtins__": {}}, {}))
        except Exception:
            return None
    return results if len(results) == len(battery) else None


def _golden_asserts(fn_name, battery, results):
    """Build run_tests() source with exact measured asserts.

    Returns (source, blocks) where blocks is a list of complete case blocks
    (each a list of lines) so defects can be planted/removed without ever
    breaking the suite's syntax.
    """
    header = ["def run_tests():",
              f"    from module import {fn_name}",
              ""]
    blocks = []
    for args, res in zip(battery, results):
        call = f"{fn_name}({', '.join(repr(a) for a in args)})"
        if isinstance(res, tuple) and len(res) == 2 and res[0] == "exc":
            blocks.append([f"    try:",
                           f"        {call}",
                           f"        raise AssertionError('no exception')",
                           f"    except {res[1]}:",
                           f"        pass"])
        else:
            blocks.append([f"    assert {call} == {res!r}"])
    body = []
    for b in blocks:
        body.extend(b)
    return "\n".join(header + body) + "\n", blocks


def _parse_assert(line):
    """Parse `    assert fn(args) == expected` -> (fn_name, args, expected)."""
    s = line.strip()
    if not s.startswith("assert "):
        return None
    body = s[len("assert "):]
    call, sep, expected = body.rpartition(" == ")
    if not sep:
        return None
    try:
        open_idx = call.index("(")
        close_idx = call.rindex(")")
    except ValueError:
        return None
    fn_name = call[:open_idx].strip()
    args_src = call[open_idx + 1:close_idx].strip()
    try:
        args = eval("(" + args_src + ",)", {"__builtins__": {}}, {}) \
            if args_src else ()
        exp = eval(expected, {"__builtins__": {}}, {})
    except Exception:
        return None
    return fn_name, args, exp


def _blind_case_weak(golden_src, module_src, alt_srcs):
    """Build a weakened suite that keeps ONE measured-blind assert: the case
    where the original and EVERY alternative source agree. The weak suite
    still passes the original module but cannot detect the alternatives.
    Returns the weak source or None when no blind case exists."""
    lines = golden_src.splitlines()
    for i, line in enumerate(lines):
        parsed = _parse_assert(line)
        if parsed is None:
            continue
        fn_name, args, exp = parsed
        orig = _run_module_fn(module_src, fn_name, [args])
        if orig != [exp]:
            continue
        blind = True
        for alt in alt_srcs:
            res = _run_module_fn(alt, fn_name, [args])
            if res is None or res[0] != exp:
                blind = False
                break
        if not blind:
            continue
        weak = "\n".join(
            l for j, l in enumerate(lines)
            if j == i or not l.strip().startswith("assert ")) + "\n"
        return weak
    return None


def _harness_literal(harness_src, var_name):
    """Extract an embedded repr() literal from a harness source."""
    for line in harness_src.splitlines():
        if line.startswith(var_name + " = "):
            try:
                return eval(line[len(var_name) + 3:], {"__builtins__": {}}, {})
            except Exception:
                return None
    return None


# --------------------------------------------------------------------------
# py_mutation_kill
# --------------------------------------------------------------------------

class MutationKillFamily(Family):
    """Write a suite that kills every listed mutant kind (real gate)."""
    NAME = "py_mutation_kill"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("testing",)

    def generate(self, rng):
        shape_key = rng.choice(sorted(_SHAPES))
        fn = rng.choice(_FN_NAME_POOLS[shape_key])
        shape = _SHAPES[shape_key](rng)
        params = shape[1:]
        src = _logic_module_src(shape_key, fn, params)
        battery = _logic_battery(shape_key, params, rng)
        kinds = [k for k in rng.sample(sorted(MUTATOR_TABLE), 5)
                 if _pick_behavior_mutant(src, k, battery, fn) is not None]
        if len(kinds) < 3:
            return None
        kinds = sorted(kinds)
        results = _run_module_fn(src, fn, battery)
        if results is None:
            return None
        golden, _blocks = _golden_asserts(fn, battery, results)
        harness = _harness(_HARNESS_MUTKILL, True,
                           kinds=kinds, mutators=MUTATOR_TABLE,
                           battery=battery, fn=fn)
        files = {"module.py": src, "solution.py": golden}
        if not _project_ok(files, harness):
            return None  # golden must kill every kind (measured gate)
        task = (
            f"module.py (shown in the files) implements `{fn}`. Write "
            f"solution.py defining run_tests() that pins down its behavior "
            f"with plain asserts so that EVERY mutant from these kinds dies: "
            f"{', '.join(kinds)}. A kind dies when at least one of your "
            f"assertions fails against the mutated module. Mutants change "
            f"one operator/constant per line (comparisons, +-, and/or, 0/1). "
            f"Cover the boundaries: comparisons at the exact cut points, "
            f"arithmetic-sensitive values, both boolean branches. Your "
            f"run_tests() must import from module and pass unchanged on the "
            f"original code.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced", task=task,
            expected_behavior="run_tests() passes on the original module and "
                              "fails on each required mutant kind",
            files=[FileSpec("module.py", src), FileSpec("solution.py", golden)],
            entry="solution.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "mutation-aware test authoring under a real gate",
                "approach": "boundary grid asserts measured from the module",
                "key_points": ["< vs <= dies exactly at the cut value",
                               "0->1 and +->- need arithmetic-sensitive cases",
                               "and/or mutants need both branch outcomes"],
                "big_o_time": "O(k) mutant runs for k kinds",
                "big_o_space": "O(battery)",
                "edge_cases": ["mutant that only changes an exception path",
                               "kind with no behavior-different mutant "
                               "cannot be required"]}},
            tags=["testing", "mutation", "verification"],
            variant=f"{shape_key}|{fn}|{'|'.join(kinds)}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        files = {f.path: f.content for f in cand.files}
        harness = cand.tests
        src_fn = files["module.py"]
        battery = None
        # rebuild the measured battery from the harness literal
        for line in harness.splitlines():
            if line.startswith("BATTERY = "):
                battery = eval(line[len("BATTERY = "):], {"__builtins__": {}}, {})
        if battery is None:
            return None
        results = _run_module_fn(src_fn, cand.variant.split("|")[1], battery)
        if results is None:
            return None
        _src, blocks = _golden_asserts(cand.variant.split("|")[1], battery,
                                       results)
        if len(blocks) < 6:
            return None
        header = files["solution.py"].split("def run_tests():")[0]
        for frac in (2, 3):
            kept = [b for i, b in enumerate(blocks) if i % frac != 0]
            weak_src = header + "def run_tests():\n" + "\n".join(
                "\n".join(b) for b in kept) + "\n"
            weak_files = {"module.py": src_fn, "solution.py": weak_src}
            if not _project_ok(weak_files, harness):
                buggy = Candidate(
                    family=self.NAME, language="python", domain="engineering",
                    difficulty="advanced", task=cand.task,
                    expected_behavior=cand.expected_behavior,
                    files=[FileSpec("module.py", src_fn),
                           FileSpec("solution.py", weak_src)],
                    entry="solution.py", tests=harness,
                    verify_method="executed", is_project=True,
                    notes={"bug_kind": "weak_suite",
                           "description": "thinned suite lets a mutant survive",
                           "correct_code": files["solution.py"]},
                    tags=cand.tags, variant=cand.variant + "|weak",
                    seed=rng.randrange(2 ** 31))
                return buggy, {"kind": "weak_suite"}
        return None


# --------------------------------------------------------------------------
# legacy-function templates for py_golden_master (parameterized rules so the
# refactor variant is a real behavior flip, never a textual trick)
# --------------------------------------------------------------------------

def _legacy_norm(rng):
    fn = rng.choice(["normalize_ref", "canonical_key", "clean_token",
                     "tidy_code"])
    max_len = rng.randrange(16, 33, 2)
    swap = rng.choice([True, False])
    sep = rng.choice(["drop", "underscore"])
    case = rng.choice(["upper", "lower", "keep"])

    def build(max_len, swap, sep, case):
        lines = [f"def {fn}(s):", "    s = s.strip()"]
        if sep == "drop":
            lines.append('    s = s.replace(" ", "")')
        else:
            lines.append('    s = s.replace(" ", "_")')
        if swap:
            lines.append('    if s[:2].lower() == "0x":')
            lines.append('        s = "0X" + s[2:]')
        if case == "upper":
            lines.append("    s = s.upper()")
        elif case == "lower":
            lines.append("    s = s.lower()")
        lines += [f"    if len(s) > {max_len}:",
                  f"        s = s[:{max_len - 1}] + '~'",
                  "    return s"]
        return "\n".join(lines) + "\n"

    src = build(max_len, swap, sep, case)
    refactor = build(max_len + rng.choice([2, 3, 4]), swap,
                     "underscore" if sep == "drop" else "drop", case)
    battery = [("ab cd",), ("  X  Y  ",), ("0xbeef",), ("0XCAFE",),
               ("a" * 30 + " z",), ("MiXeD Case 42",), ("trailing   ",),
               ("0x" + "f" * 40,), ("plain",), ("UPPER lower",),
               ("0x fast ride",), ("tab\tsep",), ("  ",), ("x" * 18,)]
    return {"fn": fn, "src": src, "refactor": refactor, "battery": battery,
            "name": "identifier normalizer", "flip": "whitespace rule and "
            "truncation length"}


def _legacy_duration(rng):
    fn = rng.choice(["format_duration", "render_span", "elapsed_text",
                     "human_time"])
    sep = rng.choice(["", "-", ":"])
    always = rng.choice([True, False])

    def build(sep, always):
        joiner = 'sep = "' + sep + '"'
        if always:
            body = [
                "def " + fn + "(secs):",
                "    " + joiner,
                "    d, rem = divmod(secs, 86400)",
                "    h, rem = divmod(rem, 3600)",
                "    m, s = divmod(rem, 60)",
                '    return sep.join([str(d) + "d", str(h) + "h",',
                '                      str(m) + "m", str(s) + "s"])',
            ]
        else:
            body = [
                "def " + fn + "(secs):",
                "    " + joiner,
                "    d, rem = divmod(secs, 86400)",
                "    h, rem = divmod(rem, 3600)",
                "    m, s = divmod(rem, 60)",
                "    parts = []",
                "    if d:",
                '        parts.append(str(d) + "d")',
                "    if h:",
                '        parts.append(str(h) + "h")',
                "    if m:",
                '        parts.append(str(m) + "m")',
                "    if s or not parts:",
                '        parts.append(str(s) + "s")',
                "    return sep.join(parts)",
            ]
        return "\n".join(body) + "\n"

    src = build(sep, always)
    refactor = build(":" if sep != ":" else "-", not always)
    battery = [(v,) for v in (0, 1, 45, 59, 60, 61, 3599, 3600, 3661, 7200,
                              86399, 86400, 90061, 172800)]
    return {"fn": fn, "src": src, "refactor": refactor, "battery": battery,
            "name": "duration formatter", "flip": "unit omission rule and "
            "separator"}


def _legacy_refid(rng):
    fn = rng.choice(["ref_id", "build_ref", "ticket_code", "order_ref"])
    w = rng.randrange(3, 6)
    m = rng.choice([10, 26, 97])
    sep = rng.choice(["-", "/"])
    c = rng.choice([1, 2])

    def build(w, m):
        return (
            "def " + fn + "(code, seq):\n"
            "    base = code + \"-\" + str(seq).zfill(" + str(w) + ")\n"
            "    acc = 0\n"
            "    for i, ch in enumerate(base):\n"
            "        acc = (acc * 3 + ord(ch)) % " + str(m) + "\n"
            "    return base + \"" + sep + "\" + str(acc).zfill(" + str(c) + ")\n")

    m2 = rng.choice([x for x in (10, 26, 97) if x != m])
    src = build(w, m)
    refactor = build(w + 1, m2)
    battery = [(code, seq) for code in ("AUX", "WEB7", "zz") for seq in
               (0, 1, 7, 42, 123, 999)]
    return {"fn": fn, "src": src, "refactor": refactor, "battery": battery,
            "name": "reference-id builder", "flip": "padding width and "
            "checksum modulus"}


def _legacy_slug(rng):
    fn = rng.choice(["slugify", "to_slug", "url_slug", "slug_for"])
    sep = rng.choice(["-", "_"])
    lim = rng.randrange(18, 41, 2)
    stops = rng.choice([
        ("the", "a", "of", "and"),
        ("the", "a", "of", "and", "to", "in"),
        ("de", "la", "y", "el"),
    ])

    def build(stops, lim):
        stops_lit = "{" + ", ".join(repr(s) for s in stops) + "}"
        return (
            "def " + fn + "(title):\n"
            "    stop = frozenset(" + stops_lit + ")\n"
            "    keep = []\n"
            "    for w in title.lower().split():\n"
            "        if w in stop:\n"
            "            continue\n"
            "        keep.append(w)\n"
            "    out = \"" + sep + "\".join(keep)\n"
            "    if len(out) > " + str(lim) + ":\n"
            "        out = out[: lim]\n"
            "        while out.endswith(\"" + sep + "\"):\n"
            "            out = out[: -1]\n"
            "    return out\n")

    src = build(stops, lim)
    stops2 = tuple(w for w in ("the", "a", "of", "and", "to", "in")
                   if w not in stops) or ("the",)
    refactor = build(stops2, lim + rng.choice([4, 6, 8]))
    battery = [(t,) for t in ("The Quick Brown Fox", "a tale of two cities",
                              "ride the lightning", "TO INFINITY AND BEYOND",
                              "de la y el camino", "x", "the   matrix  ",
                              "A" * 12 + " " + "b" * 12 + " " + "c" * 12,
                              "one Two three", "")]
    return {"fn": fn, "src": src, "refactor": refactor, "battery": battery,
            "name": "title slugifier", "flip": "stopword list and "
            "length limit"}


_LEGACY = {"norm": _legacy_norm, "duration": _legacy_duration,
           "refid": _legacy_refid, "slug": _legacy_slug}


class GoldenMasterFamily(Family):
    """Characterize a legacy function: pass on the original, fail on the
    behavior-altered refactor (both sides really executed)."""
    NAME = "py_golden_master"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("testing",)

    def generate(self, rng):
        key = rng.choice(sorted(_LEGACY))
        spec = _LEGACY[key](rng)
        fn, src, refactor = spec["fn"], spec["src"], spec["refactor"]
        battery = spec["battery"]
        orig_res = _run_module_fn(src, fn, battery)
        ref_res = _run_module_fn(refactor, fn, battery)
        if orig_res is None or ref_res is None:
            return None
        diffs = sum(1 for a, b in zip(orig_res, ref_res) if a != b)
        if diffs < 2:
            return None  # the planted refactor must be observable (measured)
        golden, _blocks = _golden_asserts(fn, battery, orig_res)
        harness = _harness(_HARNESS_GOLDEN, True, refactor=refactor)
        files = {"module.py": src, "solution.py": golden}
        if not _project_ok(files, harness):
            return None
        difficulty = rng.choice(sorted(self.DIFFICULTIES))
        task = (
            f"module.py (in the files) holds the current `{fn}` "
            f"({spec['name']}). Its behavior is frozen: a refactor is about "
            f"to be diffed against this module and it changes "
            f"{spec['flip']}. Write solution.py with run_tests() that pins "
            f"the CURRENT observable behavior with plain asserts (derive "
            f"expected values by exercising the function, including its "
            f"edge inputs) so the suite passes on module.py and FAILS on "
            f"any build where {spec['flip']} drift. Do not modify "
            f"module.py; your asserts must stay meaningful (no tautologies).")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty=difficulty, task=task,
            expected_behavior="suite passes on the original module and fails "
                              "on the altered refactor build",
            files=[FileSpec("module.py", src), FileSpec("solution.py", golden)],
            entry="solution.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "golden-master characterization before a risky change",
                "approach": "pin measured outputs across the input grid",
                "key_points": ["expected values come from observation, not intent",
                               "edge inputs (empty, boundaries, long strings) catch rule flips",
                               "tautological asserts detect nothing"],
                "big_o_time": "O(battery)",
                "big_o_space": "O(battery)",
                "edge_cases": ["empty input", "truncation boundary",
                               "rule interaction (case x separator)"]}},
            tags=["testing", "golden-master", "verification"],
            variant=f"{key}|{fn}|{spec['flip']}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        files = {f.path: f.content for f in cand.files}
        harness = cand.tests
        # Weakened characterization: keep ONE measured-blind assert (a case
        # where the original and the refactor agree), so the weak suite
        # passes the original but cannot detect the refactor (measured).
        refactor = _harness_literal(harness, "REFACTOR_SRC")
        if refactor is None:
            return None
        weak = _blind_case_weak(files["solution.py"], files["module.py"],
                                [refactor])
        if weak is None:
            return None
        weak_files = {"module.py": files["module.py"],
                      "solution.py": weak}
        if _project_ok(weak_files, harness):
            return None  # gate still green with the weak suite -> not a bug
        buggy = Candidate(
            family=self.NAME, language="python",
            domain="engineering", difficulty=cand.difficulty,
            task=cand.task, expected_behavior=cand.expected_behavior,
            files=[FileSpec("module.py", files["module.py"]),
                   FileSpec("solution.py", weak)],
            entry="solution.py", tests=harness,
            verify_method="executed", is_project=True,
            notes={"bug_kind": "weak_characterization",
                   "description": "suite reduced to a refactor-blind case: "
                                  "the drift goes undetected",
                   "correct_code": files["solution.py"]},
            tags=cand.tags, variant=cand.variant + "|weak",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "weak_characterization"}


# --------------------------------------------------------------------------
# py_test_debugging: repair a broken suite without weakening it
# --------------------------------------------------------------------------

_TEST_BUG_KINDS = ("wrong_operator", "wrong_expected", "swapped_args")


def _plant_test_bug(rng, lines, block_ranges):
    """Plant one test bug into one assert block; returns new lines or None.

    wrong_operator: == -> != (always fails against the correct module)
    wrong_expected: bump an integer literal expectation by one
    swapped_args:   swap the two last call arguments
    """
    kind = rng.choice(sorted(_TEST_BUG_KINDS))
    candidates = [r[0] for r in block_ranges if len(r) == 1]  # simple asserts
    if not candidates:
        return None
    start = rng.choice(candidates)
    line = lines[start]
    if kind == "wrong_operator" and " == " in line:
        return start, kind, [line.replace(" == ", " != ", 1)]
    if kind == "wrong_expected" and " == " in line:
        head, _, tail = line.rstrip().rpartition(" == ")
        try:
            bumped = int(tail) + 1
        except ValueError:
            return None
        return start, kind, [f"{head} == {bumped}"]
    if kind == "swapped_args" and line.count(",") >= 1:
        # swap the last two top-level args inside the call parentheses
        open_idx = line.index("(")
        close_idx = line.rindex(")")
        inner = line[open_idx + 1:close_idx]
        parts = inner.rsplit(",", 2)
        if len(parts) == 3:
            fixed = line[:open_idx + 1] + parts[0] + "," + parts[2] + \
                "," + parts[1] + line[close_idx:]
            return start, kind, [fixed]
    return None


class TestDebuggingFamily(Family):
    """The module is correct; the suite is broken. Fix the TESTS so they
    pass on the module AND still catch the planted regression kinds."""
    NAME = "py_test_debugging"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate",)
    SUPPORTS = ("testing",)

    def generate(self, rng):
        shape_key = rng.choice(sorted(_SHAPES))
        fn = rng.choice(_FN_NAME_POOLS[shape_key])
        shape = _SHAPES[shape_key](rng)
        params = shape[1:]
        src = _logic_module_src(shape_key, fn, params)
        battery = _logic_battery(shape_key, params, rng)
        results = _run_module_fn(src, fn, battery)
        if results is None:
            return None
        golden, blocks = _golden_asserts(fn, battery, results)
        # two regression variants the FIXED suite must still catch
        kinds = []
        bad_variants = []
        for k in rng.sample(sorted(MUTATOR_TABLE), 6):
            if len(kinds) >= 2:
                break
            mutated = _pick_behavior_mutant(src, k, battery, fn)
            if mutated is None:
                continue
            kinds.append(k)
            bad_variants.append(mutated)
        if len(kinds) < 2:
            return None
        # plant 2-3 test bugs (suite must then FAIL on the good module)
        lines = golden.splitlines()
        total_block_lines = sum(len(b) for b in blocks)
        idx = len(lines) - total_block_lines
        block_ranges = []
        for b in blocks:
            block_ranges.append(list(range(idx, idx + len(b))))
            idx += len(b)
        planted = 0
        tries = 0
        while planted < 2 and tries < 8:
            tries += 1
            hit = _plant_test_bug(rng, lines, block_ranges)
            if hit is None:
                continue
            start, kind, replacement = hit
            if kind == "swapped_args" and any(
                    r[0] <= start < r[-1] + 1 and len(r) > 1
                    for r in block_ranges):
                continue  # do not corrupt multi-line blocks
            lines = lines[:start] + replacement + lines[start + 1:]
            planted += 1
        if planted < 2:
            return None
        broken = "\n".join(lines) + "\n"
        # measured: broken suite must FAIL on the correct module
        rc, _out, _err = _run_py(
            {"module.py": src, "solution.py": broken},
            "import solution\nsolution.run_tests()\n", timeout=10.0)
        if rc == 0:
            return None
        harness = _harness(_HARNESS_TESTFIX, True, bad_variants=bad_variants)
        files = {"module.py": src, "broken_suite.py": broken,
                 "solution.py": golden}
        if not _project_ok(files, harness):
            return None
        task = (
            f"module.py (in the files) is CORRECT and frozen; the test "
            f"suite in broken_suite.py is NOT: at least two of its tests "
            f"fail against the correct module because the TESTS are wrong "
            f"(wrong expected values, wrong operators or wrong arguments). "
            f"Write solution.py with the repaired run_tests(): every test "
            f"passes on module.py, no assertion is weakened or deleted "
            f"(same cases, corrected expectations), and the suite still "
            f"catches regressions of these kinds: {', '.join(kinds)}.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="intermediate", task=task,
            expected_behavior="repaired suite passes on the correct module "
                              "and fails on each regression variant",
            files=[FileSpec("module.py", src),
                   FileSpec("broken_suite.py", broken),
                   FileSpec("solution.py", golden)],
            entry="solution.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "separate test bugs from code bugs, keep strength",
                "approach": "measure the module, correct expectations, keep every case",
                "key_points": ["a failing test against correct code is a test bug",
                               "fixing must never mean weakening",
                               "regression kinds stay covered after repair"],
                "big_o_time": "O(battery)",
                "big_o_space": "O(battery)",
                "edge_cases": ["swapped arguments that still type-check",
                               "boundary expectations off by one"]}},
            tags=["testing", "debugging", "verification"],
            variant=f"{shape_key}|{fn}|{'|'.join(kinds)}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        files = {f.path: f.content for f in cand.files}
        harness = cand.tests
        golden = files["solution.py"]
        # Weakened repair: keep ONE measured-blind assert (a case where the
        # correct module and the FIRST regression variant agree). It passes
        # the good module but that variant survives -> gate fails (both
        # measured, never assumed).
        bad_variants = _harness_literal(harness, "BAD_VARIANTS")
        if not bad_variants:
            return None
        weak = _blind_case_weak(golden, files["module.py"],
                                [bad_variants[0]])
        if weak is None:
            return None
        weak_files = {"module.py": files["module.py"],
                      "solution.py": weak}
        rc, _out, _err = _run_py(dict(weak_files),
                                 "import solution\nsolution.run_tests()\n",
                                 timeout=10.0)
        if rc != 0:
            return None  # the weak suite must still pass the good module
        if _project_ok(weak_files, harness):
            return None  # gate still green -> not a bug
        buggy = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="intermediate", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec("module.py", files["module.py"]),
                   FileSpec("broken_suite.py", files["broken_suite.py"]),
                   FileSpec("solution.py", weak)],
            entry="solution.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"bug_kind": "weakened_repair",
                   "description": "repair by deletion leaves a regression "
                                  "variant uncovered",
                   "correct_code": golden},
            tags=cand.tags, variant=cand.variant + "|weak",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "weakened_repair"}


# --------------------------------------------------------------------------
# py_regression_minimize: ddmin-style minimization against a real predicate
# --------------------------------------------------------------------------

_MIN_VOCAB = ("boot", "login", "logout", "set", "inc", "flush", "rollback",
              "commit", "export", "report")


def _minimize_module_src(k: int) -> str:
    return (
        "def is_repro(steps):\n"
        "    \"\"\"Deterministic failure predicate: the pipeline reports the\n"
        "    corruption only after login+set arms it, at least K increments\n"
        "    land while armed, and a commit then happens.\"\"\"\n"
        "    K = " + str(k) + "\n"
        "    logged = False\n"
        "    armed = False\n"
        "    incs = 0\n"
        "    for s in steps:\n"
        "        if s == \"login\":\n"
        "            logged = True\n"
        "        elif s == \"logout\":\n"
        "            logged = False\n"
        "        elif s == \"set\":\n"
        "            armed = logged\n"
        "        elif s == \"inc\":\n"
        "            if armed and logged:\n"
        "                incs = incs + 1\n"
        "        elif s == \"flush\":\n"
        "            incs = 0\n"
        "        elif s == \"rollback\":\n"
        "            armed = False\n"
        "        elif s == \"commit\":\n"
        "            if armed and logged and incs >= K:\n"
        "                return True\n"
        "    return False\n")


_GOLDEN_MINIMIZE = '''def minimize_repro(steps):
    """Return a minimal subsequence of `steps` that still reproduces.

    Fixed-point backward elimination: remove elements while a single
    removal keeps the reproduction; repeat passes until nothing can go.
    """
    from module import is_repro
    cur = list(steps)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(cur):
            reduced = cur[:i] + cur[i + 1:]
            if is_repro(reduced):
                cur = reduced
                changed = True
            else:
                i += 1
    return cur
'''


class MinimizeFamily(Family):
    """Minimize a failing input against a real reproducer predicate."""
    NAME = "py_regression_minimize"
    LANGUAGE = "python"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("testing",)

    def _build_steps(self, rng, k):
        trigger = ["login", "set"] + ["inc"] * k + ["commit"]
        noise = [_MIN_VOCAB[rng.randrange(len(_MIN_VOCAB))]
                 for _ in range(rng.randrange(6, 13))]
        steps = []
        ni = 0
        for t in trigger:
            burst = rng.randrange(0, 3)
            steps.extend(noise[ni:ni + burst])
            ni += burst
            steps.append(t)
        steps.extend(noise[ni:])
        return steps

    def generate(self, rng):
        k = rng.randrange(2, 5)
        src = _minimize_module_src(k)
        steps = None
        for _ in range(6):
            cand_steps = self._build_steps(rng, k)
            res = _run_module_fn(src, "is_repro", [(cand_steps,)])
            if res == [True]:
                steps = cand_steps
                break
        if steps is None:
            return None
        golden = _GOLDEN_MINIMIZE
        harness_stub = None
        # measure the golden minimal length to size the cap honestly
        rc, _out, _err = _run_py({"module.py": src, "solution.py": golden},
                                 "import solution\nr = "
                                 "solution.minimize_repro(__STEPS__)\n"
                                 "print(len(r))\n".replace("__STEPS__",
                                                          repr(steps)),
                                 timeout=10.0)
        if rc != 0:
            return None
        golden_len = int(_out.strip().splitlines()[-1])
        cap = golden_len + 2
        harness = _harness(_HARNESS_MINIMIZE, False, steps=steps, cap=cap)
        files = {"module.py": src, "solution.py": golden}
        if not _project_ok(files, harness):
            return None
        task = (
            f"module.py defines is_repro(steps), the exact predicate that "
            f"reproduces a corruption report. The input list (shown in the "
            f"harness literal) reproduces but is full of noise. Implement "
            f"minimize_repro(steps) in solution.py: return a SUBSEQUENCE of "
            f"the original list (same relative order) that still satisfies "
            f"is_repro, has at most {cap} elements, and is 1-minimal: "
            f"removing ANY single element breaks the reproduction. Plain "
            f"stdlib; deterministic; do not modify module.py.")
        return Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced", task=task,
            expected_behavior="returns a 1-minimal reproducing subsequence "
                              "within the length cap",
            files=[FileSpec("module.py", src), FileSpec("solution.py", golden)],
            entry="solution.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "automated regression minimization (ddmin spirit)",
                "approach": "fixed-point backward elimination over the predicate",
                "key_points": ["single-pass deletion is not 1-minimal",
                               "the predicate, not the developer, decides",
                               "subsequence semantics preserve order"],
                "big_o_time": "O(n^2) predicate calls for n steps",
                "big_o_space": "O(n)",
                "edge_cases": ["noise that re-arms the state",
                               "commit before arming is inert"]}},
            tags=["testing", "ddmin", "algorithms"],
            variant=f"k{k}|n{len(steps)}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: appends an element from the original input to the minimal
        # result -> either not a subsequence anymore or not 1-minimal; the
        # gate must fail either way (measured below).
        module_src = {f.path: f.content for f in cand.files}["module.py"]
        steps_line = [l for l in cand.tests.splitlines()
                      if l.startswith("STEPS = ")][0]
        steps = eval(steps_line[len("STEPS = "):], {"__builtins__": {}}, {})
        buggy_src = _GOLDEN_MINIMIZE.replace(
            "    return cur\n",
            "    cur.append(" + repr(steps[0]) + ")\n    return cur\n", 1)
        files = {"module.py": module_src, "solution.py": buggy_src}
        if _project_ok(files, cand.tests):
            return None  # gate still green with the buggy -> not a bug
        buggy = Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec("module.py", files["module.py"]),
                   FileSpec("solution.py", buggy_src)],
            entry="solution.py", tests=cand.tests, verify_method="executed",
            is_project=True,
            notes={"bug_kind": "non_minimal_result",
                   "description": "appends an input element: the list no "
                                  "longer satisfies 1-minimality (or is not "
                                  "even a subsequence)",
                   "correct_code": _GOLDEN_MINIMIZE},
            tags=cand.tags, variant=cand.variant + "|weak",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "non_minimal_result"}


register(globals(), MutationKillFamily)
register(globals(), GoldenMasterFamily)
register(globals(), TestDebuggingFamily)
register(globals(), MinimizeFamily)
