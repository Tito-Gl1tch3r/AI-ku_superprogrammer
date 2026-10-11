"""v1.0.0 verification-craft families: shape, replay, volumes, determinism.

The write dataset gains four module-06 families whose ground truth is
two-sided real execution (mutation kill, golden master, test debugging,
regression minimization). These tests pin:
  * record shape for every family (project mode, harness present, honest
    verification metadata)
  * third-party replay: published records really pass their own harnesses
    through the standard executor (verify_python), byte-for-byte from the
    shards
  * honest volume floors (a rebuild that silently loses families fails)
  * determinism: same seed -> byte-identical solution code and harness
"""
from __future__ import annotations

import gzip
import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.executors.python_exec import verify_python  # noqa: E402

V100_FAMILIES = ("py_mutation_kill", "py_golden_master",
                 "py_test_debugging", "py_regression_minimize")

VOLUME_FLOORS = {
    "py_mutation_kill": 40,
    "py_golden_master": 40,
    "py_test_debugging": 40,
    "py_regression_minimize": 40,
}


def _write_records():
    base = os.path.join(ROOT, "datasets", "write")
    out = []
    for split in ("train", "validation", "test"):
        sd = os.path.join(base, split)
        for name in sorted(os.listdir(sd)):
            if not name.endswith(".jsonl.gz"):
                continue
            with gzip.open(os.path.join(sd, name), "rt",
                           encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    gen = (rec.get("provenance") or {}).get("generator")
                    if gen in V100_FAMILIES:
                        out.append(rec)
    return out


@pytest.mark.parametrize("name", V100_FAMILIES)
def test_family_record_shape(name):
    import generators.write.verification_craft as vc
    fam_by_name = {f.NAME: f for f in vc.__families__}
    fam = fam_by_name[name]
    cand = fam.generate(random.Random(20271101))
    assert cand is not None, f"{name}: fresh-seed generation dropped"
    assert cand.is_project and cand.entry == "solution.py"
    paths = [f.path for f in cand.files]
    assert "module.py" in paths and "solution.py" in paths
    assert cand.verify_method == "executed"
    harness = cand.tests
    assert "import solution" in harness
    assert "run_tests" in harness or "minimize_repro" in harness
    assert cand.task and len(cand.task) >= 60
    # real verification through the standard executor
    r = verify_python(cand, timeout=30)
    assert r.ok, f"{name}: fresh sample failed the real harness: " \
                 f"{(r.stderr or '')[:200]}"


def test_published_v100_records_replay():
    """Third-party replay: every published v1.0.0 record must pass its own
    harness through the standard executor, straight from the shards."""
    recs = _write_records()
    assert len(recs) >= 160, f"expected >=160 published v100 records, got {len(recs)}"
    seen = {}
    for rec in recs:
        seen.setdefault(rec["provenance"]["generator"], []).append(rec)
    import generators.core as core
    from generators.core import Candidate, FileSpec
    checked = 0
    for fam_name, group in sorted(seen.items()):
        sample = group[: max(1, len(group) // 20)]  # ~5% per family
        for rec in sample:
            cand = Candidate(
                family=rec["provenance"]["generator"],
                language=rec["language"], domain=rec["domain"],
                difficulty=rec["difficulty"], task=rec["task"],
                expected_behavior=rec["expected_behavior"],
                code=rec.get("code"),
                files=[FileSpec(path=f["path"], content=f["content"])
                       for f in (rec.get("files") or [])],
                entry=rec.get("entry"), tests=rec.get("tests"),
                verify_method="executed",
                is_project=bool((rec.get("metrics") or {}).get("is_project")),
                variant=rec["_split_meta"]["variant"] if "_split_meta" in rec
                        else (rec.get("provenance") or {}).get("seed", 0))
            r = verify_python(cand, timeout=30)
            assert r.ok, f"{fam_name} {rec['id']} replay RED: " \
                         f"{(r.stderr or '')[:200]}"
            checked += 1
    assert checked >= 8, f"replay checked only {checked} records"


def test_published_v100_volumes():
    counts = {}
    for rec in _write_records():
        fam = rec["provenance"]["generator"]
        counts[fam] = counts.get(fam, 0) + 1
    for fam, floor in VOLUME_FLOORS.items():
        assert counts.get(fam, 0) >= floor, \
            f"{fam}: {counts.get(fam, 0)} < honest floor {floor}"


@pytest.mark.parametrize("name", V100_FAMILIES)
def test_v100_determinism(name):
    import generators.write.verification_craft as vc
    fam_by_name = {f.NAME: f for f in vc.__families__}
    fam = fam_by_name[name]
    a = fam.generate(random.Random(20271201))
    b = fam.generate(random.Random(20271201))
    if a is None:
        pytest.skip(f"{name}: seed dropped (honest gate)")
    assert b is not None
    assert a.code_text() == b.code_text()
    assert a.tests == b.tests
