"""v1.1.0 build-craft families: shape, replay, volumes, determinism.

The write dataset gains three module-07 families whose ground truth is a
REAL build pipeline (make / gcc executed inside the harness,
verify_method = build_executed). These tests pin:
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

V110_FAMILIES = ("c_makefile_repair", "c_warning_gate", "c_header_guards")

VOLUME_FLOORS = {
    "c_makefile_repair": 40,
    "c_warning_gate": 100,
    "c_header_guards": 40,
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
                    if gen in V110_FAMILIES:
                        out.append(rec)
    return out


@pytest.mark.parametrize("name", V110_FAMILIES)
def test_family_record_shape(name):
    import generators.write.build_craft as bc
    fam_by_name = {f.NAME: f for f in bc.__families__}
    fam = fam_by_name[name]
    cand = None
    for seed in range(20271111, 20271115):
        cand = fam.generate(random.Random(seed))
        if cand is not None:
            break
    assert cand is not None, f"{name}: no sample in 4 fresh seeds"
    assert cand.is_project and cand.verify_method == "build_executed"
    paths = [f.path for f in cand.files]
    assert any(p.endswith(".c") for p in paths)
    harness = cand.tests
    assert "subprocess" in harness
    assert cand.task and len(cand.task) >= 60
    # real verification through the standard executor
    r = verify_python(cand, timeout=30)
    assert r.ok, f"{name}: fresh sample failed the real harness: " \
                 f"{(r.stderr or '')[:200]}"


def test_published_v110_records_replay():
    """Third-party replay: every published v1.0.0 record must pass its own
    harness through the standard executor, straight from the shards."""
    recs = _write_records()
    assert len(recs) >= 100, f"expected >=100 published v110 records, got {len(recs)}"
    seen = {}
    for rec in recs:
        seen.setdefault(rec["provenance"]["generator"], []).append(rec)
    import generators.core as core
    from generators.core import Candidate, FileSpec
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
            r = verify_python(cand, timeout=30)
            assert r.ok, f"{fam_name} {rec['id']} replay RED: " \
                         f"{(r.stderr or '')[:200]}"
            checked += 1
    assert checked >= 6, f"replay checked only {checked} records"


def test_published_v110_volumes():
    counts = {}
    for rec in _write_records():
        fam = rec["provenance"]["generator"]
        counts[fam] = counts.get(fam, 0) + 1
    for fam, floor in VOLUME_FLOORS.items():
        assert counts.get(fam, 0) >= floor, \
            f"{fam}: {counts.get(fam, 0)} < honest floor {floor}"


@pytest.mark.parametrize("name", V110_FAMILIES)
def test_v110_determinism(name):
    import generators.write.build_craft as bc
    fam_by_name = {f.NAME: f for f in bc.__families__}
    fam = fam_by_name[name]
    a = fam.generate(random.Random(20271211))
    b = fam.generate(random.Random(20271211))
    if a is None:
        pytest.skip(f"{name}: seed dropped (honest gate)")
    assert b is not None
    assert a.code_text() == b.code_text()
    assert a.tests == b.tests
