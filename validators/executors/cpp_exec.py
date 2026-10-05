"""C++ verification: g++ compile + run harness with asserts.

Conventions for C++ families:
  * candidate files define functions/classes; only harness.cpp has main().
  * `tests` is the full content of harness.cpp (includes <cassert>, returns 0).
"""
from __future__ import annotations

import os

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version
from .c_exec import compile_and_run_c

GXX = "g++"


def verify_cpp(cand, timeout=12.0) -> ExecResult:
    sources = {f.path: f.content for f in cand.all_files()}
    if cand.tests:
        sources["harness.cpp"] = cand.tests
    cpp_files = {k: v for k, v in sources.items() if k.endswith(".cpp")}
    if "harness.cpp" not in cpp_files:
        return ExecResult(stage="compile", stderr="missing harness.cpp")
    d = temp_dir()
    res = ExecResult(stage="compile")
    try:
        write_files(d, sources)
        res.toolchain = probe_version([GXX, "--version"])
        cmd = [GXX, "-std=c++17", "-O1", "-Wall", "-Wextra",
               *cpp_files.keys(), "-o", "prog_cpp", "-pthread"]
        c = run_cmd(cmd, d, timeout=30.0)
        res.compile_stderr = c.stderr
        res.duration_ms = c.duration_ms
        if not c.ok:
            res.stderr = c.stderr or "compilation failed"
            res.exit_code = c.exit_code
            return res
        res.stage = "run"
        r = run_cmd(["./prog_cpp"], d, timeout=timeout)
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
