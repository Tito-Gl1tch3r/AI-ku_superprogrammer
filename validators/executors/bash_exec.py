"""Bash verification: run script.sh with fixtures in a sandbox cwd.

Conventions for Bash families:
  * code is the full content of script.sh; scripts only touch files inside
    the current working directory (never absolute paths, never /tmp directly).
  * notes["cases"]: list of {"args": [...], "stdin": str|None, "fixtures":
    {name: content}, "expected_exit": int, "expected_stdout": str,
    "stdout_mode": "exact"|"contains"|"regex"}
"""
from __future__ import annotations

import os
import re

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version

BASH = "bash"


def verify_bash(cand, timeout=10.0) -> ExecResult:
    res = ExecResult(stage="tests")
    res.toolchain = probe_version([BASH, "--version"])
    cases = (cand.notes or {}).get("cases")
    if not cases:
        res.stderr = "missing bash cases"
        return res
    d = temp_dir()
    script_name = (cand.entry
                   or next((f.path for f in cand.all_files() if f.path.endswith(".sh")),
                           "script.sh"))
    try:
        write_files(d, {f.path: f.content for f in cand.all_files()})
        failures = []
        r = None
        for i, case in enumerate(cases):
            write_files(d, case.get("fixtures") or {})
            r = run_cmd([BASH, script_name, *(case.get("args") or [])], d,
                        timeout=timeout, stdin_text=case.get("stdin"))
            mode = case.get("stdout_mode", "exact")
            exp_out = case.get("expected_stdout", "")
            exp_exit = case.get("expected_exit", 0)
            if r.exit_code != exp_exit:
                failures.append(f"case {i}: exit {r.exit_code} != {exp_exit}; stderr: {r.stderr[:200]}")
            elif mode == "exact" and r.stdout != exp_out:
                failures.append(f"case {i}: stdout mismatch\n got: {r.stdout[:200]!r}\nwant: {exp_out[:200]!r}")
            elif mode == "contains" and exp_out not in r.stdout:
                failures.append(f"case {i}: stdout missing {exp_out[:120]!r}")
            elif mode == "regex" and not re.search(exp_out, r.stdout):
                failures.append(f"case {i}: stdout !~ {exp_out[:120]!r}")
        res.stdout = "stdout of last case: " + r.stdout[:600] if cases else ""
        if failures:
            res.stderr = " | ".join(failures)[:1500]
            res.exit_code = 1
            return res
        res.ok = True
        res.exit_code = 0
        res.stdout = "__BASH_OK__ " + res.stdout
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
