"""Python verification: run candidate code against its authored test suite.

Conventions for Python families:
  * `code` (or the entry file) is importable as `solution` — no top-level
    side effects beyond imports/definitions.
  * `tests` is Python source that defines `run_tests()` using plain asserts
    over names imported from the solution (harness does `from solution import *`).
"""
from __future__ import annotations

import os
import sys

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version

HARNESS = '''import sys
from solution import *  # noqa: F401,F403

{tests}

run_tests()
print("__TESTS_PASSED__")
'''

# Project mode: the tests string is a standalone unittest script.
PROJECT_HARNESS = '''import sys

{tests}
'''


def verify_python(cand, timeout=10.0) -> ExecResult:
    d = temp_dir()
    res = ExecResult(stage="tests")
    try:
        files = {f.path: f.content for f in cand.all_files()}
        project_mode = bool(cand.is_project or cand.entry)
        if not project_mode and "solution.py" not in files:
            res.stderr = "no solution.py entry file"
            return res
        template = PROJECT_HARNESS if project_mode else HARNESS
        write_files(d, files, {"_harness.py": template.format(tests=cand.tests or "")})
        res.toolchain = probe_version([sys.executable, "--version"])
        r = run_cmd([sys.executable, "_harness.py"], d, timeout=timeout)
        res.exit_code, res.stdout, res.stderr = r.exit_code, r.stdout, r.stderr
        res.duration_ms, res.timed_out, res.toolchain = r.duration_ms, r.timed_out, r.toolchain
        res.ok = r.ok and (project_mode or "__TESTS_PASSED__" in r.stdout)
        if r.timed_out:
            res.stderr = (res.stderr + "\nTIMEOUT").strip()
    finally:
        for root, _, fs in os.walk(d):
            for fn in fs:
                try:
                    os.remove(os.path.join(root, fn))
                except OSError:
                    pass
        try:
            os.rmdir(d)
        except OSError:
            pass
    return res


def run_python_snippet(code, timeout=10.0, stdin_text=None) -> ExecResult:
    """Execute a standalone snippet (used by Dataset-2 builders)."""
    d = temp_dir()
    try:
        write_files(d, {"snippet.py": code})
        return run_cmd([sys.executable, "snippet.py"], d, timeout=timeout, stdin_text=stdin_text)
    finally:
        try:
            os.remove(os.path.join(d, "snippet.py"))
            os.rmdir(d)
        except OSError:
            pass
