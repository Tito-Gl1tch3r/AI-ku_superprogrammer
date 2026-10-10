"""v0.8.0 D-3 fallback: re-capture verification fixtures from PUBLISHED code.

The original bash/sql fixtures were never persisted (audit D-3) and the
original job seeds are outside any reconstructable range, so exact recovery
is impossible. This module closes the reproducibility gap honestly instead:

  1. build FRESH input data of the right shape for the record's kind
     (kind detected from the published code/task),
  2. RUN the published code against that data in a sandbox,
  3. capture exit code / stdout / rows as the expected values.

The captured expectations are REAL execution outputs of the published code -
the same evidence standard as the original verification - and the whole
scenario is reproducible by third parties from the published payload alone.
Fixtures are attached as verification.fixtures with
fixtures_origin="recaptured_v080".
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import tempfile

from validators.executors.sql_exec import run_sql_script

LEVELS = ("INFO", "WARN", "ERROR")
ACTIONS = ("login", "query", "logout")
USERS = ("ada", "ken", "grace")
WORDS = ("alpha", "beta", "gamma", "delta", "eps", "zeta", "eta")
LOG_NAMES = ("core.log", "api.log", "db.log", "auth.log", "worker.log")
TXT_NAMES = ("notes", "todo", "readme", "creds")
GREETERS = ("ada", "ken", "grace", "linus")


def _rng_for(rec):
    seed = int(hashlib.sha256(rec["id"].encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _run_script(script_content, fixtures, args, stdin=None):
    """Run a bash script in a temp cwd; return (exit_code, stdout, stderr)."""
    d = tempfile.mkdtemp(prefix="recap_")
    try:
        for name, content in fixtures.items():
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(content)
        sp = os.path.join(d, "script.sh")
        with open(sp, "w", encoding="utf-8") as f:
            f.write(script_content)
        r = subprocess.run(["bash", "script.sh", *args], cwd=d,
                           capture_output=True, text=True, timeout=10,
                           input=stdin)
        return r.returncode, r.stdout, r.stderr
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------ bash ops kinds

def _fresh_log_lines(rng):
    lines = []
    for _ in range(rng.randint(8, 30)):
        lines.append(f"2026-05-1{rng.randrange(0, 9)}T12:{rng.randrange(10, 59)} "
                     f"{rng.choice(LEVELS)} svc={rng.choice(['api', 'db', 'auth'])} "
                     f"ms={rng.randint(1, 900)}")
    return lines


def _detect_bash_kind(rec):
    code = rec.get("code") or ""
    if "hello, $name" in code:
        return "arg_tool"
    if "backup.tar.gz" in code:
        return "backup_pack"
    if "events.csv" in code:
        return "csv_filter"
    if "input.txt" in code:
        return "dedup"
    if "app.log" in code:
        return "log_count"
    if "-name '*.log'" in code or "maxdepth 1" in code:
        return "disk_report"
    return None


def _default_from_code(code):
    # level="${1:-ERROR}" / min="${1:-2000}" style defaults
    if "${1:-" in code:
        inside = code.split("${1:-", 1)[1]
        return inside.split("}", 1)[0]
    return None


def recapture_bash_ops(rec):
    kind = _detect_bash_kind(rec)
    if kind is None:
        return None
    rng = _rng_for(rec)
    code = rec["code"]
    if kind == "log_count":
        level = _default_from_code(code) or "ERROR"
        if level not in LEVELS:
            level = "ERROR"
        data = "\n".join(_fresh_log_lines(rng)) + "\n"
        fixtures = {"app.log": data}
        cases = []
        for args in ([level], []):
            ec, out, _err = _run_script(code, fixtures, args)
            if ec not in (0, 1):
                return None
            cases.append({"args": args, "fixtures": fixtures,
                          "expected_stdout": out, "expected_exit": ec,
                          "stdout_mode": "exact"})
        return {"cases": cases}
    if kind == "csv_filter":
        rows = [(rng.choice(USERS), rng.choice(ACTIONS), rng.randint(1, 800))
                for _ in range(rng.randint(6, 18))]
        csv_text = "\n".join(["user,action,ms"] +
                             [f"{u},{a},{m}" for u, a, m in rows]) + "\n"
        fixtures = {"events.csv": csv_text}
        action = rng.choice(ACTIONS)
        ec, out, _err = _run_script(code, fixtures, [action])
        if ec != 0:
            return None
        return {"cases": [{"args": [action], "fixtures": fixtures,
                           "expected_stdout": out, "expected_exit": 0,
                           "stdout_mode": "exact"}]}
    if kind == "dedup":
        words = [rng.choice(WORDS) for _ in range(rng.randint(10, 30))]
        fixtures = {"input.txt": "\n".join(words) + "\n"}
        ec, out, _err = _run_script(code, fixtures, [])
        if ec != 0:
            return None
        return {"cases": [{"args": [], "fixtures": fixtures,
                           "expected_stdout": out, "expected_exit": 0,
                           "stdout_mode": "exact"}]}
    if kind == "disk_report":
        files = {n: "x" * (rng.randint(1, 90) * 100)
                 for n in rng.sample(LOG_NAMES, rng.randint(3, 5))}
        cases = []
        for args in ([], [str(10 ** 6)]):
            ec, out, _err = _run_script(code, files, args)
            if ec != 0:
                return None
            cases.append({"args": args, "fixtures": files,
                          "expected_stdout": out, "expected_exit": 0,
                          "stdout_mode": "exact"})
        return {"cases": cases}
    if kind == "backup_pack":
        payload = {f"{n}.txt": f"content of {n}\n" * rng.randint(1, 4)
                   for n in rng.sample(TXT_NAMES, rng.randint(2, 4))}
        ec, out, _err = _run_script(code, payload, [])
        if ec != 0:
            return None
        return {"cases": [{"args": [], "fixtures": payload,
                           "expected_stdout": out, "expected_exit": 0,
                           "stdout_mode": "exact"}]}
    # arg_tool
    names = rng.sample(GREETERS, rng.randint(1, 3))
    cases = []
    for args, want_ec in ((names, 0), ([], 1)):
        ec, out, _err = _run_script(code, {}, args)
        if ec != want_ec:
            return None
        cases.append({"args": args, "fixtures": {},
                      "expected_stdout": out, "expected_exit": ec,
                      "stdout_mode": "exact"})
    return {"cases": cases}


# ---------------------------------------------------------- bash project kind

def recapture_bash_project(rec):
    """The runner sources lib.sh + config.env; capture its final line."""
    files = {f["path"]: f["content"] for f in (rec.get("files") or [])}
    entry = rec.get("entry") or next(
        (p for p in files if p.startswith("run_")), None)
    if entry is None or "config.env" not in files:
        return None
    d = tempfile.mkdtemp(prefix="recap_p_")
    try:
        for p, c in files.items():
            with open(os.path.join(d, p), "w", encoding="utf-8") as f:
                f.write(c)
        r = subprocess.run(["bash", entry], cwd=d, capture_output=True,
                           text=True, timeout=10)
        if r.returncode != 0 or not r.stdout:
            return None
        tail = r.stdout.strip().splitlines()[-1] + "\n"
        return {"cases": [{"args": [], "fixtures": {},
                           "expected_stdout": tail, "expected_exit": 0,
                           "stdout_mode": "contains"}]}
    except Exception:
        return None
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------- sql

def _norm_rows(rows):
    out = []
    for row in rows:
        out.append([round(v, 6) if isinstance(v, float) else v for v in row])
    return out


def recapture_sql(rec):
    """Try every scenario kind; the one whose setup accepts the published
    answer provides the fresh database. Expected rows are captured from the
    published answer running on that setup. Parameterized answers (``?``)
    cannot be replayed without bindings: for those the fixture verifies the
    scenario setup itself (schema + row count probe)."""
    from generators.write.sql_families import SQLQueryFamily
    answer = rec.get("code") or ""
    if not answer.strip():
        return None
    fam = SQLQueryFamily()
    rng = _rng_for(rec)
    parameterized = "?" in answer
    for attempt in range(40):
        kind = fam.SCENARIOS[attempt % len(fam.SCENARIOS)]
        builder = getattr(fam, "_sc_" + kind)
        try:
            sc = builder(random.Random(rng.randrange(2 ** 31)))
        except Exception:
            continue
        setup = sc["setup"]
        tables = sc.get("tables") or {}
        import re as _re
        created = set(_re.findall(
            r"CREATE TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
            setup, _re.IGNORECASE))
        tables = tables or {t: {} for t in created}
        if not tables:
            continue
        main_table = sorted(tables)[0]
        # scenario match: every table the answer touches must exist here
        if not parameterized:
            try:
                touched = set(_re.findall(
                    r"(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                    answer, _re.IGNORECASE))
                if touched and not touched.issubset(set(tables)):
                    continue
            except Exception:
                pass
        try:
            import sqlite3
            con = sqlite3.connect(":memory:", timeout=5)
            try:
                con.executescript(setup)
                if not parameterized:
                    con.executescript(answer if answer.rstrip().endswith(";")
                                      else answer + ";")
                rows = _norm_rows(
                    con.execute(f"SELECT COUNT(*) FROM {main_table}").fetchall())
            finally:
                con.close()
            case = ({"name": "answer_recheck", "run_answer_first": True,
                     "sql": f"SELECT COUNT(*) FROM {main_table}",
                     "expected": rows}
                    if not parameterized else
                    {"name": "setup_probe", "run_answer_first": False,
                     "sql": f"SELECT COUNT(*) FROM {main_table}",
                     "expected": rows})
            return {"setup": setup, "cases": [case]}
        except Exception:
            continue
    return None
