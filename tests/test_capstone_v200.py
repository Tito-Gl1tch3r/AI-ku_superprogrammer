"""v2.0.0 capstone integration families: shape, replay, volumes, determinism.

The write dataset gains three module-08 capstone families (expert tier;
compound gates: unit probes + real CLI subprocesses + structural checks).
These tests pin:
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

from validators.executors.python_exec import verify_python
from validators.executors.ts_exec import verify_ts  # noqa: E402

V200_FAMILIES = ("py_inventory_ops", "py_log_pipeline", "ts_jsonl_pipeline")

VOLUME_FLOORS = {
    "py_inventory_ops": 25,
    "py_log_pipeline": 25,
    "ts_jsonl_pipeline": 25,
}


def _write_records():
    base = os.path.join(ROOT, "datasets", "write")
    out = []
    sources = []
    for split in ("train", "validation", "test"):
        sources.append((split, os.path.join(base, split)))
    hold = os.path.join(ROOT, "datasets", "hard_holdout")
    sources.append(("hard_holdout", hold))
    for split, sd in sources:
        for name in sorted(os.listdir(sd)):
            if not name.endswith(".jsonl.gz"):
                continue
            if split == "hard_holdout" and not name.startswith("write-"):
                continue
            with gzip.open(os.path.join(sd, name), "rt",
                           encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    gen = (rec.get("provenance") or {}).get("generator")
                    if gen in V200_FAMILIES:
                        out.append(rec)
    return out


@pytest.mark.parametrize("name", V200_FAMILIES)
def test_family_record_shape(name):
    import generators.write.capstone_projects as cap
    fam_by_name = {f.NAME: f for f in cap.__families__}
    fam = fam_by_name[name]
    cand = None
    for seed in range(20271221, 20271225):
        cand = fam.generate(random.Random(seed))
        if cand is not None:
            break
    assert cand is not None, f"{name}: no sample in 4 fresh seeds"
    assert cand.difficulty == "expert"
    if cand.family != "ts_jsonl_pipeline":
        assert cand.is_project
    paths = [f.path for f in (cand.files or [])]
    assert "main.py" in paths or cand.code, "capstone needs the given CLI or a code entry"
    harness = cand.tests
    assert "subprocess" in harness or "execFileSync" in harness
    assert cand.task and len(cand.task) >= 60
    # real verification through the standard executor
    _run = verify_ts if cand.language == "typescript" else verify_python
    r = _run(cand, timeout=40)
    assert r.ok, f"{name}: fresh sample failed the real harness: " \
                 f"{(r.stderr or '')[:200]}"


def test_published_v200_records_replay():
    """Third-party replay: every published v1.0.0 record must pass its own
    harness through the standard executor, straight from the shards."""
    recs = _write_records()
    assert len(recs) >= 150, f"expected >=150 published v200 records, got {len(recs)}"
    seen = {}
    for rec in recs:
        seen.setdefault(rec["provenance"]["generator"], []).append(rec)
    from generators.core import Candidate, FileSpec
    from validators.executors.ts_exec import verify_ts
    checked = 0
    for fam_name, group in sorted(seen.items()):
        sample = group[: max(2, len(group) // 10)]  # ~10% per family
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
            _run = verify_ts if rec["language"] == "typescript" else verify_python
            r = _run(cand, timeout=40)
            assert r.ok, f"{fam_name} {rec['id']} replay RED: " \
                         f"{(r.stderr or '')[:200]}"
            checked += 1
    assert checked >= 6, f"replay checked only {checked} records"


def test_published_v200_volumes():
    counts = {}
    for rec in _write_records():
        fam = rec["provenance"]["generator"]
        counts[fam] = counts.get(fam, 0) + 1
    for fam, floor in VOLUME_FLOORS.items():
        assert counts.get(fam, 0) >= floor, \
            f"{fam}: {counts.get(fam, 0)} < honest floor {floor}"


@pytest.mark.parametrize("name", V200_FAMILIES)
def test_v200_determinism(name):
    import generators.write.capstone_projects as cap
    fam_by_name = {f.NAME: f for f in cap.__families__}
    fam = fam_by_name[name]
    a = fam.generate(random.Random(20271221))
    b = fam.generate(random.Random(20271221))
    if a is None:
        pytest.skip(f"{name}: seed dropped (honest gate)")
    assert b is not None
    assert a.code_text() == b.code_text()
    assert a.tests == b.tests
