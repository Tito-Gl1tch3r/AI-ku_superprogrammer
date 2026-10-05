"""JavaScript (Node.js) verification.

Conventions for JS families:
  * solution.js defines functions/classes and ends with `module.exports = {...}`.
  * `tests` is JS source defining `function runTests(solution){ ... }` using
    the `assert` module (provided by the harness).
"""
from __future__ import annotations

import os

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version

NODE = "node"

HARNESS = '''const assert = require('assert');
const solution = require('./solution.js');

{tests}

runTests(solution);
console.log("__TESTS_PASSED__");
'''


def verify_js(cand, timeout=10.0) -> ExecResult:
    d = temp_dir()
    res = ExecResult(stage="tests")
    try:
        files = {f.path: f.content for f in cand.all_files()}
        if "solution.js" not in files:
            res.stderr = "no solution.js entry file"
            return res
        write_files(d, files, {"_harness.js": HARNESS.format(tests=cand.tests or "")})
        res.toolchain = probe_version([NODE, "--version"])
        r = run_cmd([NODE, "_harness.js"], d, timeout=timeout)
        res.exit_code, res.stdout, res.stderr = r.exit_code, r.stdout, r.stderr
        res.duration_ms, res.timed_out = r.duration_ms, r.timed_out
        res.ok = r.ok and "__TESTS_PASSED__" in r.stdout
    finally:
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
            except OSError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass
    return res


def run_node_snippet(files, entry="snippet.js", timeout=10.0, stdin_text=None) -> ExecResult:
    d = temp_dir()
    try:
        write_files(d, files)
        return run_cmd([NODE, entry], d, timeout=timeout, stdin_text=stdin_text)
    finally:
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
            except OSError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass
