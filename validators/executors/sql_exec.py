"""SQL verification via in-memory SQLite (python sqlite3 module).

Conventions for SQL families:
  * notes["setup"]           : DDL + INSERT seed script (deterministic).
  * notes["cases"]           : list of {"name", "sql", "expected": [[row], ...]}
  * `code`                   : the answer SQL (what the model must produce).
  * expected rows are computed INDEPENDENTLY in the generator (from the
    seeded data model), never by running the answer on itself.
"""
from __future__ import annotations

import sqlite3

from .base import ExecResult


def _norm(v):
    if isinstance(v, float):
        return round(v, 6)
    return v


def verify_sql(cand, timeout=10.0) -> ExecResult:
    res = ExecResult(stage="tests")
    res.toolchain = "sqlite (python sqlite3)"
    notes = cand.notes or {}
    setup = notes.get("setup")
    cases = notes.get("cases") or []
    if not setup or not cases:
        res.stderr = "missing sql verification scenario"
        return res
    try:
        con = sqlite3.connect(":memory:", timeout=5)
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(setup)
        failures = []
        for i, case in enumerate(cases):
            # Optionally run the candidate answer first (DDL / write scenarios).
            if case.get("run_answer_first") and cand.code:
                try:
                    con.executescript(cand.code if cand.code.rstrip().endswith(";")
                                      else cand.code + ";")
                except sqlite3.Error as e:
                    failures.append(f"case {case.get('name', i)}: answer error: {e}")
                    continue
            if case.get("prelude"):
                try:
                    con.executescript(case["prelude"])
                except sqlite3.Error as e:
                    failures.append(f"case {case.get('name', i)}: prelude error: {e}")
                    continue
            sql = case.get("sql")
            if case.get("use_answer") and cand.code:
                sql = cand.code
            if not sql:
                failures.append(f"case {case.get('name', i)}: no SQL to run")
                continue
            try:
                rows = [[_norm(v) for v in row] for row in con.execute(sql).fetchall()]
            except sqlite3.Error as e:
                failures.append(f"case {case.get('name', i)}: SQL error: {e}")
                continue
            exp = [[_norm(v) for v in row] for row in case["expected"]]
            if rows != exp:
                failures.append(f"case {case.get('name', i)}: rows mismatch "
                                f"(got {rows[:3]}..., want {exp[:3]}...)")
        con.close()
        if failures:
            res.stderr = " | ".join(failures)[:MAXMSG]
            res.exit_code = 1
            return res
        res.ok = True
        res.exit_code = 0
        res.stdout = f"__SQL_OK__ cases={len(cases)}"
    except sqlite3.Error as e:
        res.stderr = f"scenario error: {e}"
        res.exit_code = 2
    return res


MAXMSG = 1500


def run_sql_script(script: str) -> tuple:
    """Run an arbitrary SQL script in-memory; return (ok, fetched_last, error)."""
    try:
        con = sqlite3.connect(":memory:", timeout=5)
        con.executescript(script)
        con.close()
        return True, None, ""
    except sqlite3.Error as e:
        return False, None, str(e)
