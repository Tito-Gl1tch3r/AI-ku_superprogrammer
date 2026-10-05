"""C verification: gcc compile + run harness with asserts.

Conventions for C families:
  * candidate files define functions/types; exactly the harness has main().
  * `tests` is the full content of harness.c (includes assert.h, returns 0).
"""
from __future__ import annotations

import os

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version

GCC = "gcc"


def compile_and_run_c(sources, out_name, timeout=15.0, std="-std=c11",
                      extra_flags=("-O1", "-Wall", "-Wextra"), libs=("-lm",),
                      all_sources=None) -> ExecResult:
    d = temp_dir()
    res = ExecResult(stage="compile")
    try:
        write_files(d, all_sources if all_sources is not None else sources)
        res.toolchain = probe_version([GCC, "--version"])
        cmd = [GCC, std, *extra_flags, *sources.keys(), "-o", out_name, *libs]
        c = run_cmd(cmd, d, timeout=25.0)
        res.compile_stderr = c.stderr
        res.duration_ms = c.duration_ms
        if not c.ok:
            res.stderr = c.stderr or "compilation failed"
            res.exit_code = c.exit_code
            return res
        res.stage = "run"
        r = run_cmd([f"./{out_name}"], d, timeout=timeout)
        res.exit_code, res.stdout, res.stderr = r.exit_code, r.stdout, r.stderr
        res.duration_ms += r.duration_ms
        res.timed_out = r.timed_out
        res.ok = r.ok
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


def verify_c(cand, timeout=10.0) -> ExecResult:
    sources = {f.path: f.content for f in cand.all_files()}
    if cand.tests:
        sources["harness.c"] = cand.tests
    c_files = {k: v for k, v in sources.items() if k.endswith(".c")}
    if "solution.c" not in sources or "harness.c" not in c_files:
        return ExecResult(stage="compile", stderr="missing solution.c or harness.c")
    return compile_and_run_c(c_files, "prog_c", timeout=timeout, all_sources=sources)
