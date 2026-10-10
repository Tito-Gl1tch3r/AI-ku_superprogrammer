"""v0.8.0 regression tests: third-party re-verifiability of bash/sql records.

Audit finding D-3: bash/sql verification fixtures were never persisted, so
the published payload could not be re-verified by third parties. The v0.8.0
migration attaches verification.fixtures to every bash/sql write record
(recaptured from real executions of the published code). These tests pin
that guarantee: the payload alone must be enough to re-verify.
"""
from __future__ import annotations

import gzip
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _bash_sql_records():
    from scripts.fix_fixtures_v080 import load_bash_sql_records
    return load_bash_sql_records()


def _replay(rec):
    """Re-verify a published record from its payload alone."""
    from types import SimpleNamespace
    from validators.executors.bash_exec import verify_bash
    from validators.executors.sql_exec import verify_sql
    if rec.get("code"):
        entry = rec.get("entry") or "script.sh"
        files = [SimpleNamespace(path=entry, content=rec["code"])]
    else:
        files = [SimpleNamespace(path=f["path"], content=f["content"])
                 for f in (rec.get("files") or [])]

    class _C:
        pass

    c = _C()
    c.code = rec.get("code")
    c.files = files
    c.entry = rec.get("entry")
    c.all_files = lambda: files
    c.notes = rec["verification"]["fixtures"]
    if rec["language"] == "sql":
        return verify_sql(c)
    return verify_bash(c)


def test_every_bash_sql_record_has_fixtures():
    recs = _bash_sql_records()
    assert len(recs) == 90, f"expected 90 bash/sql records, got {len(recs)}"
    for _path, _split, rec in recs:
        fx = rec["verification"].get("fixtures")
        assert fx, f"{rec['id']} has no verification.fixtures"
        assert fx.get("cases"), f"{rec['id']} fixtures have no cases"
        if rec["language"] == "sql":
            assert fx.get("setup"), f"{rec['id']} sql fixtures have no setup"
        origin = rec["verification"].get("fixtures_origin")
        assert origin in ("original_recovered", "recaptured_v080"), \
            f"{rec['id']} unknown fixtures_origin {origin}"


def test_sampled_records_replay_from_payload():
    """A deterministic sample re-verifies end-to-end from the published payload."""
    recs = _bash_sql_records()
    sample = [recs[i] for i in range(0, len(recs), 8)]  # ~12 records, all families
    assert len(sample) >= 10
    for _path, _split, rec in sample:
        r = _replay(rec)
        assert r.ok, f"{rec['id']} replay failed: {(r.stderr or '')[:300]}"


def test_sql_fixtures_carry_setup_and_valid_cases():
    for _path, _split, rec in _bash_sql_records():
        if rec["language"] != "sql":
            continue
        fx = rec["verification"]["fixtures"]
        for case in fx["cases"]:
            assert case.get("sql") or case.get("use_answer") or \
                case.get("run_answer_first"), \
                f"{rec['id']} case without executable content"
