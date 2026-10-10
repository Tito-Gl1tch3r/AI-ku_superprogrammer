# ---------------------------------------------------------------- v0.7.0 audit regression tests
# These close the fault-injection gaps found in the v0.7.0 audit:
# planted faults F1/F2/F5/F7 were NOT caught by the original suite.
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_split_coverage_guarantee():
    """Every dataset stage must have at least one group in validation and test."""
    from validators.splits import coverage_fixup, split_hash
    # a stage whose groups all hash into train must still get val/test coverage
    groups = {f"fam{i}|v" for i in range(6)}
    gx = {g: split_hash(*g.split("|", 1)) for g in groups}
    # force the pathological case: all hashes land in train bucket
    gx = {g: 100 for g in groups}
    assign = coverage_fixup(gx)
    assert set(assign.values()) >= {"train", "validation", "test"}, assign
    vals = [g for g, s in assign.items() if s == "validation"]
    tests = [g for g, s in assign.items() if s == "test"]
    assert len(vals) >= 1 and len(tests) >= 1


def test_media_holdout_policy():
    """ALL expert records of the media dataset go to hard_holdout (v0.7.0)."""
    from scripts.finalize import assign_split, MEDIA_DATASETS
    assert "AI-ku_superprogrammer_media" in MEDIA_DATASETS
    rec = {"_split_meta": {"family": "media_mv_project", "variant": "x",
                           "difficulty": "expert"}}
    assert assign_split(rec, "AI-ku_superprogrammer_media") == "hard_holdout"
    # non-expert media records flow normally
    rec2 = {"_split_meta": {"family": "media_mv_project", "variant": "x",
                            "difficulty": "advanced"}}
    assert assign_split(rec2, "AI-ku_superprogrammer_media") != "hard_holdout"
    # other datasets keep the hash rule: expert groups are NOT auto-holdout
    rec3 = {"_split_meta": {"family": "re_elf_parser", "variant": "header_magic",
                            "difficulty": "expert"}}
    assert assign_split(rec3, "AI-ku_superprogrammer_reverse_engineering") in         ("train", "validation", "test", "hard_holdout")


def test_schema_check_rejects_invalid():
    """A neutered schema checker (always []) must be detectable."""
    from validators.schema_check import validate
    schema = json.load(open(os.path.join(ROOT, "schemas", "write.schema.json")))
    bad = {"id": "x", "dataset": "AI-ku_superprogrammer_write", "kind": "write",
           "language": "klingon", "domain": "nope", "difficulty": "chaotic",
           "task": "", "code": "", "tests": None, "expected_behavior": "",
           "verification": {"method": "vibes", "tests_passed": None},
           "provenance": {}, "license": "MIT",
           "metrics": {"code_chars": 0, "is_project": False}}
    errs = validate(bad, schema)
    assert errs, "schema checker accepted a garbage record - checker neutered?"
    assert any("language" in str(e) or "difficulty" in str(e) or "method" in str(e)
               for e in errs), errs[:3]


def test_make_stats_executed_counting():
    """make_stats must only count executed/compiled as verified-by-execution."""
    import importlib
    import scripts.make_stats as ms
    importlib.reload(ms)
    src = open(ms.__file__, encoding="utf-8").read()
    # the executed gate must reference the honest method enum, not True
    assert 'if method in ("executed", "compiled_and_executed"):' in src, \
        "make_stats executed-count gate was neutered"
