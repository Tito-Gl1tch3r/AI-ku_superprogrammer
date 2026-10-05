"""Problem bank: import side-effect registers every problem and language impl."""
from .bank_core import REGISTRY, CodeUnit, Problem, register_problem  # noqa: F401
from . import bank_py_a      # noqa: F401
from . import bank_py_b      # noqa: F401
from . import bank_cpp       # noqa: F401
from . import bank_c         # noqa: F401
from . import bank_js        # noqa: F401
from . import bank_ts        # noqa: F401
from . import bank_bash      # noqa: F401

# Extra executor hook for TS snippets (used by Dataset-2 builders).
from validators.executors.base import ExecResult, run_cmd, temp_dir, write_files  # noqa: F401


def run_ts_snippet(files, entry="main.ts", timeout=12.0, stdin_text=None) -> ExecResult:
    import subprocess
    d = temp_dir()
    try:
        write_files(d, files)
        return run_cmd(["node", "--experimental-strip-types", entry], d,
                       timeout=timeout, stdin_text=stdin_text)
    finally:
        import os
        for fn in os.listdir(d):
            try:
                os.remove(os.path.join(d, fn))
            except OSError:
                pass
        try:
            os.rmdir(d)
        except OSError:
            pass


def run_cli_for(language: str, code_unit, stdin_text: str, timeout=10.0) -> ExecResult:
    """Run a bank CodeUnit's CLI files with stdin; return raw ExecResult."""
    if not code_unit.cli:
        raise ValueError(f"problem has no CLI for this language")
    d = temp_dir()
    try:
        write_files(d, code_unit.cli)
        if language == "python":
            cmd = ["python3", "main.py"]
        elif language in ("javascript", "typescript"):
            flag = ["--experimental-strip-types"] if language == "typescript" else []
            cmd = ["node", *flag, "main.ts" if language == "typescript" else "main.js"]
        elif language == "cpp":
            c = run_cmd(["g++", "-std=c++17", "-O1", "solution.cpp", "main.cpp",
                         "-o", "prog", "-pthread"], d, timeout=30)
            if not c.ok:
                r = ExecResult(stage="compile", stderr=c.stderr or "compile failed")
                return r
            cmd = ["./prog"]
        elif language == "c":
            c = run_cmd(["gcc", "-std=c11", "-O1", "solution.c", "main.c",
                         "-o", "prog", "-lm"], d, timeout=30)
            if not c.ok:
                r = ExecResult(stage="compile", stderr=c.stderr or "compile failed")
                return r
            cmd = ["./prog"]
        elif language == "bash":
            cmd = ["bash", "script.sh"]
        else:
            raise ValueError(f"no CLI runner for {language}")
        return run_cmd(cmd, d, timeout=timeout, stdin_text=stdin_text)
    finally:
        import os
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
