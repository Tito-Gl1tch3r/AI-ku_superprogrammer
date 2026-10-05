"""Mutation testing engine (Python).

Used by the Dataset-2 `testing` builder: a candidate test suite is scored by
the number of mutants it kills. Mutants that survive prove gaps in the
suite. All numbers reported are REAL execution results.
"""
from __future__ import annotations

import re

from validators.executors.python_exec import verify_python
from generators.core import Candidate

# (name, pattern, replacement, applies_to_hint)
MUTATORS = [
    ("lt_to_le", r"(?<![<>=!])<(?!=)", "<="),
    ("le_to_lt", r"<=(?!=)", "<"),
    ("gt_to_ge", r"(?<![<>=!])>(?!=)", ">="),
    ("plus_to_minus", r"(?<![+\-*/])\+(?![+=])", "-"),
    ("and_to_or", r"\band\b", "or"),
    ("zero_to_one", r"\b0\b", "1"),
    ("return_negate", r"return (True|False)", r"return (\1 == False)"),
]


def _mutants(code: str) -> list:
    out = []
    lines = code.split("\n")
    for name, pat, repl in MUTATORS:
        for i, line in enumerate(lines):
            new_line = re.sub(pat, repl, line)
            if new_line != line:
                mutated = lines[:i] + [new_line] + lines[i + 1:]
                out.append((f"{name}@L{i + 1}", "\n".join(mutated)))
    return out


def mutation_score(code: str, tests: str, max_mutants: int = 12) -> dict:
    """Run the suite against mutants; return killed/total and surviving kinds."""
    base = Candidate(family="mutation_probe", language="python", domain="algorithms",
                     difficulty="beginner", task="probe", expected_behavior="probe",
                     code=code, tests=tests, verify_method="executed")
    r0 = verify_python(base)
    if not r0.ok:
        return {"error": "baseline tests failed", "killed": 0, "total": 0,
                "survived": []}
    survivors = []
    killed = 0
    total = 0
    for name, mutated in _mutants(code)[:max_mutants]:
        total += 1
        m = Candidate(family="mutation_probe", language="python", domain="algorithms",
                      difficulty="beginner", task="probe", expected_behavior="probe",
                      code=mutated, tests=tests, verify_method="executed")
        rm = verify_python(m)
        if rm.ok:
            survivors.append(name)
        else:
            killed += 1
    return {"killed": killed, "total": total, "survived": survivors}
