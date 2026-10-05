"""Verification dispatcher: candidate -> executor -> honest metadata."""
from __future__ import annotations

from .executors.python_exec import verify_python
from .executors.cpp_exec import verify_cpp
from .executors.c_exec import verify_c
from .executors.js_exec import verify_js
from .executors.ts_exec import verify_ts
from .executors.sql_exec import verify_sql
from .executors.bash_exec import verify_bash
from .executors.static_check import verify_static

_LANG2FN = {
    "python": verify_python,
    "cpp": verify_cpp,
    "c": verify_c,
    "javascript": verify_js,
    "typescript": verify_ts,
    "sql": verify_sql,
    "bash": verify_bash,
}


def verify_candidate(cand, timeout=None):
    """Return (ok: bool, ExecResult, verification_dict). Never raises."""
    fn = _LANG2FN.get(cand.language)
    try:
        if fn is not None and cand.verify_method in ("executed", "compiled_and_executed"):
            r = fn(cand, timeout=timeout) if timeout else fn(cand)
        else:
            r = verify_static(cand)
    except Exception as e:  # absolute: pipeline must survive any executor bug
        from .executors.base import ExecResult
        r = ExecResult(stage="internal", stderr=f"executor crashed: {e!r}")
    ver = {
        "method": ("static_check" if fn is None or cand.verify_method == "static_check"
                   else cand.verify_method),
        "compiled": r.ok if cand.language in ("c", "cpp") and r.stage in ("compile", "run") else None,
        "executed": r.ok if cand.language in _LANG2FN and cand.verify_method != "static_check" else None,
        "tests_passed": bool(r.ok) if r.stage in ("tests", "run", "static") else None,
        "duration_ms": r.duration_ms,
        "timed_out": r.timed_out,
        "toolchain": r.toolchain,
        "error_excerpt": (r.stderr or "")[:600] if not r.ok else "",
    }
    return r.ok, r, ver


def run_snippet_safely(kind, payload, **kw):
    """Helpers used by Dataset-2 builders to observe REAL behaviour."""
    from .executors.python_exec import run_python_snippet
    from .executors.js_exec import run_node_snippet
    if kind == "python":
        return run_python_snippet(payload, **kw)
    if kind == "node":
        return run_node_snippet(payload, **kw)
    raise ValueError(kind)
