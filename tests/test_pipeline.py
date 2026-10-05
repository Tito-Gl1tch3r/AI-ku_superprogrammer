"""Pipeline self-tests: executors, dedup, splits, generators, bugs, schemas."""
import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from generators.registry import all_families, family_by_name  # noqa: E402
from validators.verify import verify_candidate  # noqa: E402
from validators.dedup import DedupIndex  # noqa: E402
from validators.splits import assign_split  # noqa: E402
from validators.quality_filters import quality_check  # noqa: E402
from validators.schema_check import validate  # noqa: E402
from evaluators.mutation import mutation_score  # noqa: E402

HAS_GCC = os.system("command -v gcc > /dev/null 2>&1") == 0
HAS_GXX = os.system("command -v g++ > /dev/null 2>&1") == 0


# ---------------------------------------------------------------- executors
def test_python_executor_pass_and_fail():
    from generators.core import Candidate
    good = Candidate(family="t", language="python", domain="algorithms",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code="def add(a, b):\n    return a + b\n",
                     tests="def run_tests():\n    assert add(2, 3) == 5\n",
                     verify_method="executed")
    ok, r, _ = verify_candidate(good)
    assert ok and r.ok
    bad = Candidate(family="t", language="python", domain="algorithms",
                    difficulty="beginner", task="x" * 60, expected_behavior="y",
                    code="def add(a, b):\n    return a - b\n",
                    tests="def run_tests():\n    assert add(2, 3) == 5\n",
                    verify_method="executed")
    ok2, r2, _ = verify_candidate(bad)
    assert not ok2


def test_python_executor_timeout():
    from generators.core import Candidate
    loop = Candidate(family="t", language="python", domain="algorithms",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code="def spin():\n    while True:\n        pass\n",
                     tests="def run_tests():\n    spin()\n",
                     verify_method="executed")
    ok, r, ver = verify_candidate(loop, timeout=4)
    assert not ok and (r.timed_out or ver["timed_out"])


def test_sql_executor():
    from generators.core import Candidate
    cand = Candidate(family="t", language="sql", domain="databases",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code="SELECT a FROM t ORDER BY a;",
                     verify_method="executed",
                     notes={"setup": "CREATE TABLE t (a INTEGER);\nINSERT INTO t VALUES (2);"
                                     "\nINSERT INTO t VALUES (1);",
                            "cases": [{"name": "main", "use_answer": True,
                                       "expected": [[1], [2]]}]})
    ok, r, _ = verify_candidate(cand)
    assert ok


def test_bash_executor():
    from generators.core import Candidate
    cand = Candidate(family="t", language="bash", domain="automation",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code='#!/usr/bin/env bash\necho "hello $1"\n',
                     verify_method="executed",
                     notes={"cases": [{"args": ["world"], "expected_stdout": "hello world\n",
                                       "expected_exit": 0, "stdout_mode": "exact"}]})
    ok, r, _ = verify_candidate(cand)
    assert ok


@pytest.mark.skipif(not HAS_GCC, reason="gcc missing")
def test_c_executor():
    from generators.core import Candidate
    cand = Candidate(family="t", language="c", domain="algorithms",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code="int twice(int x) { return x * 2; }\n",
                     tests="#include <assert.h>\nint twice(int);\n"
                           "int main(void) { assert(twice(2) == 4); return 0; }\n",
                     verify_method="compiled_and_executed")
    ok, r, _ = verify_candidate(cand)
    assert ok


@pytest.mark.skipif(not HAS_GXX, reason="g++ missing")
def test_cpp_executor():
    from generators.core import Candidate
    cand = Candidate(family="t", language="cpp", domain="algorithms",
                     difficulty="beginner", task="x" * 60, expected_behavior="y",
                     code="#include <vector>\nint sum(const std::vector<int>& v) "
                          "{ int s = 0; for (int x : v) s += x; return s; }\n",
                     tests="#include <cassert>\n#include <vector>\n"
                           "int sum(const std::vector<int>&);\n"
                           "int main() { assert(sum({1, 2, 3}) == 6); return 0; }\n",
                     verify_method="compiled_and_executed")
    ok, r, _ = verify_candidate(cand)
    assert ok


def test_static_html_rejects_bad():
    from generators.core import Candidate
    bad = Candidate(family="t", language="html", domain="web", difficulty="beginner",
                    task="x" * 60, expected_behavior="y",
                    code="<html><body><p>unclosed</body></html>",
                    verify_method="static_check")
    ok, r, _ = verify_candidate(bad)
    assert not ok


# ---------------------------------------------------------------- generators
def test_every_family_generates_and_validates():
    """One sample per family; executable languages must verify, static must pass checks."""
    for fam in all_families():
        base = sum(ord(c) for c in fam.NAME)  # deterministic across processes
        rng = random.Random(base % 10_000)
        cand = fam.generate(rng)
        assert cand is not None, fam.NAME
        qok, qreason = quality_check(cand)
        assert qok, f"{fam.NAME}: {qreason}"
        ok, r, _ = verify_candidate(cand, timeout=15)
        assert ok, f"{fam.NAME} [{cand.language}] failed at {r.stage}: " \
                   f"{(r.stderr or r.compile_stderr)[:200]}"


def test_no_family_cap_breach():
    fams = {f.NAME for f in all_families()}
    assert len(fams) >= 40


# ---------------------------------------------------------------- dedup/splits
def test_dedup_catches_renamed_duplicates():
    from generators.core import Candidate

    def mk(name_value):
        return Candidate(family="f", language="python", domain="algorithms",
                         difficulty="beginner", task="x" * 60, expected_behavior="y",
                         code=f"def calc(values):\n    total = 0\n"
                              f"    for {name_value} in values:\n"
                              f"        total += {name_value}\n    return total\n",
                         verify_method="executed")
    idx = DedupIndex()
    assert idx.check_and_add(mk("x"))
    assert not idx.check_and_add(mk("y"))  # same structure, renamed -> duplicate


def test_splits_are_group_atomic():
    groups = [(f"fam{i}", "variantA") for i in range(50)]
    seen = {}
    for fam, var in groups:
        s = assign_split(fam, var)
        seen[(fam, var)] = s
    # same group always maps to the same split
    for (fam, var), s in seen.items():
        assert assign_split(fam, var) == s
    # expert holdout is deterministic
    assert assign_split("fam0", "variantA", hard_holdout=True) == \
        assign_split("fam0", "variantA", hard_holdout=True)


# ---------------------------------------------------------------- mutation
def test_mutation_engine_kills_strong_suite():
    code = ("def clamp(x, lo, hi):\n"
            "    if x < lo:\n"
            "        return lo\n"
            "    if x > hi:\n"
            "        return hi\n"
            "    return x\n")
    tests = ("def run_tests():\n"
             "    assert clamp(0, 1, 5) == 1\n"
             "    assert clamp(9, 1, 5) == 5\n"
             "    assert clamp(3, 1, 5) == 3\n"
             "    assert clamp(1, 1, 5) == 1\n")
    score = mutation_score(code, tests, max_mutants=8)
    assert score["total"] > 0
    assert score["killed"] >= score["total"] - 2  # strong suite kills most


# ---------------------------------------------------------------- schemas
def test_final_records_validate_against_schemas():
    with open(os.path.join(ROOT, "schemas", "write.schema.json")) as f:
        wschema = json.load(f)
    with open(os.path.join(ROOT, "schemas", "understand.schema.json")) as f:
        uschema = json.load(f)
    from scripts.records import write_record
    from generators.core import Candidate
    cand = Candidate(family="t", language="python", domain="algorithms",
                     difficulty="beginner", task="x" * 70, expected_behavior="y" * 10,
                     code="def f():\n    return 1\n",
                     tests="def run_tests():\n    assert f() == 1\n",
                     verify_method="executed")
    ok, r, ver = verify_candidate(cand)
    assert ok
    rec = write_record(cand, ver)
    rec["id"] = "write-0000001"
    errs = validate(rec, wschema)
    assert not errs, errs[:3]
    # understand record minimal shape
    urec = {"id": "understand-0000001", "dataset": "AI-ku_superprogrammer_understand",
            "language": "python", "task_type": "debugging", "domain": "algorithms",
            "difficulty": "advanced",
            "input": {"context": "", "code": "x", "files": None,
                      "question": "q" * 50, "artifacts": {}},
            "target": {"answer": "a" * 50, "code": None, "tests": None,
                       "key_points": [], "big_o": None},
            "verification": {"method": "executed"},
            "provenance": {"source": "synthetic", "generator": "test", "seed": 1,
                           "created_utc": "2026-01-01T00:00:00+00:00",
                           "pipeline_version": "0.1.0"},
            "license": "MIT", "metrics": {}}
    errs2 = validate(urec, uschema)
    assert not errs2, errs2[:3]
