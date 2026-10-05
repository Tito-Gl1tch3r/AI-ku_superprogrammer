"""TypeScript verification via Node.js native type stripping.

Node >= 23.6 runs .ts files directly by erasing type annotations. Families
MUST use only *erasable* TypeScript (type annotations, interfaces, type
aliases, generics, `import type`). Enums, namespaces, parameter properties
and `const enum` are FORBIDDEN (they require a real transform, not stripping).

Conventions:
  * solution.ts exports via `export { ... }` of values (ESM) — the harness
    uses a temporary .mjs wrapper importing from ./solution.ts.
"""
from __future__ import annotations

import os

from .base import ExecResult, run_cmd, temp_dir, write_files, probe_version

NODE = "node"

HARNESS_MJS = '''import assert from 'assert';
import * as solution from './solution.ts';

{tests}

runTests(solution);
console.log("__TESTS_PASSED__");
'''


def verify_ts(cand, timeout=12.0) -> ExecResult:
    d = temp_dir()
    res = ExecResult(stage="tests")
    try:
        files = {f.path: f.content for f in cand.all_files()}
        if "solution.ts" not in files:
            res.stderr = "no solution.ts entry file"
            return res
        write_files(d, files, {"_harness.mjs": HARNESS_MJS.format(tests=cand.tests or "")})
        res.toolchain = probe_version([NODE, "--version"]) + " (type-stripping)"
        r = run_cmd([NODE, "--experimental-strip-types", "_harness.mjs"], d, timeout=timeout)
        if r.exit_code != 0 and "bad option" in (r.stderr or "").lower():
            # Older/newer Node: try without the explicit flag.
            r = run_cmd([NODE, "_harness.mjs"], d, timeout=timeout)
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
