"""Sandboxed process execution primitives for verification.

All generated code is run in a fresh temp dir, in a child process with
resource limits (wall-clock timeout, CPU seconds, address space, file
size). Nothing generated is ever trusted.
"""
from __future__ import annotations

import os
import resource
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field

MAX_CAPTURE = 8000  # chars kept from stdout/stderr tails


@dataclass
class ExecResult:
    ok: bool = False
    stage: str = "none"             # compile|run|tests|static
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    compile_stderr: str = ""        # compiler warnings/errors when applicable
    toolchain: str = ""
    details: dict = field(default_factory=dict)

    def tail(self, s: str) -> str:
        return s[-MAX_CAPTURE:] if s else ""


def _limits(mem_mb: int = 1536, cpu_s: int = 12, fsize_mb: int = 48):
    def apply():
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 2))
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            os.setsid()
        except Exception:
            pass
    return apply


def run_cmd(cmd, cwd, timeout=10.0, stdin_text=None, env=None, mem_mb=1536):
    """Run cmd in cwd with resource limits; kill the whole group on timeout."""
    t0 = time.monotonic()
    res = ExecResult()
    full_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": cwd, "TMPDIR": cwd, "LANG": "C.UTF-8",
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
    if env:
        full_env.update(env)
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=full_env,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, preexec_fn=_limits(mem_mb=mem_mb),
        )
        try:
            out, err = proc.communicate(stdin_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()
            out, err = proc.communicate()
            res.timed_out = True
        res.exit_code = proc.returncode
        res.stdout = res.tail(out or "")
        res.stderr = res.tail(err or "")
        res.duration_ms = int((time.monotonic() - t0) * 1000)
        res.ok = (proc.returncode == 0) and not res.timed_out
    except FileNotFoundError as e:
        res.stderr = f"toolchain missing: {e}"
        res.stage = "toolchain"
    except Exception as e:  # defensive: sandbox errors must not crash the pipeline
        res.stderr = f"sandbox error: {e!r}"
    return res


def temp_dir(prefix="aiku_"):
    return tempfile.mkdtemp(prefix=prefix)


def _amaro_wasm_oom(stderr: str | None) -> bool:
    """True when Node's TS type-stripper (amaro) failed to init its WASM.

    Signature of the toolchain hitting the sandbox address-space cap at
    startup -- the reservation happens before any generated code runs.
    """
    s = stderr or ""
    return "WebAssembly.Instance" in s and "Out of memory" in s


def run_node_ts(cmd, cwd, timeout=10.0, stdin_text=None, env=None, mem_mb=1536):
    """run_cmd for Node type-stripping runs, resilient to amaro WASM OOM.

    Some Node builds bundle an amaro whose WASM memory reservation exceeds
    the sandbox default address-space cap. On that failure signature, retry
    once with a raised RLIMIT_AS so the toolchain's own reservation fits.
    Tests, CPU/FSIZE limits, pass criteria and timeout are unchanged; the
    retry is recorded in details for full transparency.
    """
    r = run_cmd(cmd, cwd, timeout=timeout, stdin_text=stdin_text, env=env, mem_mb=mem_mb)
    if r.exit_code != 0 and _amaro_wasm_oom(r.stderr):
        r = run_cmd(cmd, cwd, timeout=timeout, stdin_text=stdin_text, env=env, mem_mb=4096)
        r.details["amaro_mem_retry"] = True
    return r


def write_files(d, files, extra=None):
    """Write {relpath: content} (creating subdirs) plus extra {name: content}."""
    for name, content in {**(files or {}), **(extra or {})}.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p) or d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def probe_version(cmd) -> str:
    """Cache toolchain version strings; empty string if unavailable."""
    global _VER_CACHE
    if cmd[0] in _VER_CACHE:
        return _VER_CACHE[cmd[0]]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        ver = (out.stdout or out.stderr).strip().splitlines()[0][:80]
    except Exception:
        ver = ""
    _VER_CACHE[cmd[0]] = ver
    return ver


_VER_CACHE: dict = {}
