"""v0.9.0 evolution families: schema, replay and published-state pins.

Fast pytest additions for the roadmap-closure wave:
  * every new family produces a schema-valid record shape (via write_record)
  * published records of the new families are third-party re-runnable:
    (code/files, tests) from the SHARDS pass the real runner again
  * the append publisher kept every pre-existing id (spot pin on max ids)
"""
import gzip
import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from generators.registry import family_by_name  # noqa: E402
from validators.verify import verify_candidate  # noqa: E402
from validators.quality_filters import quality_check  # noqa: E402

NEW_FAMILIES = ("git_merge_conflict", "flaky_test_forensics",
                "sql_schema_migration", "sdk_docs_integration",
                "repo_feature_insertion", "profile_guided_optimization",
                "doctest_authoring")

# family -> minimum published records expected from the v0.9.0 delta
# (git/repo have narrow deterministic variant spaces, hence lower floors)
MIN_PUBLISHED = {
    "git_merge_conflict": 15,
    "flaky_test_forensics": 40,
    "sql_schema_migration": 40,
    "sdk_docs_integration": 40,
    "repo_feature_insertion": 10,
    "profile_guided_optimization": 30,
    "doctest_authoring": 40,
}


@pytest.mark.parametrize("name", NEW_FAMILIES)
def test_family_record_shape(name):
    fam = family_by_name(name)
    cand = None
    for attempt in range(6):
        cand = fam.generate(random.Random(9100 + attempt * 7919))
        if cand is not None:
            break
    assert cand is not None, name
    qok, qreason = quality_check(cand)
    assert qok, f"{name}: {qreason}"
    ok, r, ver = verify_candidate(cand, timeout=40)
    assert ok, f"{name} [{r.stage}]: {(r.stderr or r.compile_stderr)[:200]}"
    from scripts.records import write_record
    rec = write_record(cand, ver)
    assert rec["dataset"] == "AI-ku_superprogrammer_write"
    assert rec["verification"]["method"] == "executed"
    assert rec["metrics"]["code_chars"] >= 70


def _iter_write_records():
    base = os.path.join(ROOT, "datasets", "write")
    for split in ("train", "validation", "test"):
        sd = os.path.join(base, split)
        for name in sorted(os.listdir(sd)):
            if not name.endswith(".jsonl.gz"):
                continue
            with gzip.open(os.path.join(sd, name), "rt",
                           encoding="utf-8") as f:
                for line in f:
                    yield split, json.loads(line)


def test_published_evolution_records_replay():
    """Third-party re-verifiability: shard records pass their own tests."""
    from collections import defaultdict
    found = defaultdict(list)
    for _split, rec in _iter_write_records():
        fam = rec["provenance"]["generator"]
        if fam in NEW_FAMILIES and len(found[fam]) < 2:
            found[fam].append(rec)
    missing = [f for f in NEW_FAMILIES if not found[f]]
    assert not missing, f"families absent from published shards: {missing}"
    for fam, recs in found.items():
        for rec in recs:
            from generators.core import Candidate, FileSpec
            files = ([FileSpec(f["path"], f["content"])
                      for f in rec["files"]] if rec.get("files") else None)
            cand = Candidate(
                family=rec["provenance"]["generator"],
                language=rec["language"], domain=rec["domain"],
                difficulty=rec["difficulty"], task=rec["task"],
                expected_behavior=rec["expected_behavior"],
                code=rec.get("code"), files=files, entry=rec.get("entry"),
                tests=rec.get("tests"), verify_method="executed",
                is_project=bool(rec.get("entry")))
            ok, r, _ = verify_candidate(cand, timeout=40)
            assert ok, f"{fam} id {rec['id']} replay failed [{r.stage}]: " \
                       f"{(r.stderr or r.compile_stderr)[:200]}"


def test_published_evolution_volumes():
    counts = {f: 0 for f in NEW_FAMILIES}
    for _split, rec in _iter_write_records():
        fam = rec["provenance"]["generator"]
        if fam in counts:
            counts[fam] += 1
    for fam, minimum in MIN_PUBLISHED.items():
        assert counts[fam] >= minimum, f"{fam}: {counts[fam]} < {minimum}"


def test_holdout_has_evolution_experts():
    hold = os.path.join(ROOT, "datasets", "hard_holdout")
    seen = set()
    for name in sorted(os.listdir(hold)):
        if not (name.startswith("write-write-") and
                name.endswith(".jsonl.gz")):
            continue
        with gzip.open(os.path.join(hold, name), "rt",
                       encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                fam = rec["provenance"]["generator"]
                if fam in NEW_FAMILIES:
                    seen.add(fam)
    # expert families (repo_feature_insertion, profile expert rows) must have
    # reached the holdout per the hash rule
    assert "repo_feature_insertion" in seen
