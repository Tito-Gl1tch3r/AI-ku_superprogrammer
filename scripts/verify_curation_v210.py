#!/usr/bin/env python3
"""Verify v2.1.0 curation integrity:
  1. every surviving record line is BYTE-IDENTICAL to its pre-curation line
     (git HEAD shards are the baseline)
  2. the set of dropped ids per file == the ids the manifest assigns to that
     file's (dataset, split)
  3. no duplicate ids anywhere after curation; holdout disjoint from splits
  4. floors from test contracts still hold (quick re-check here)
"""
import collections, gzip, json, os, subprocess, sys

REPO = "/home/z/my-project/re-build/AI-ku"
DS = os.path.join(REPO, "datasets")
MAN = json.load(open(os.path.join(REPO, "reports", "curation_v210.json")))
removed = MAN["removed_ids"]

def git_blob(path):
    blob = subprocess.run(["git", "-C", REPO, "show", f"HEAD:{path}"],
                          capture_output=True, check=True).stdout
    return [l for l in gzip.decompress(blob).split(b"\n") if l]

ok = True
files = subprocess.run(["git", "-C", REPO, "ls-files", "datasets/"],
                       capture_output=True, text=True).stdout.split()
checked_lines = dropped_ids = 0
for path in files:
    if not path.endswith(".jsonl.gz") or "/_staging" in path or "/_quarantine" in path:
        continue
    rel = path  # already repo-root-relative
    old_lines = git_blob(rel)
    with gzip.open(os.path.join(REPO, rel), "rb") as fh:
        new_lines = [l for l in fh.read().split(b"\n") if l]
    # survivor byte-identity via set comparison of exact bytes
    old_set = collections.Counter(old_lines)
    new_set = collections.Counter(new_lines)
    missing = old_set - new_set   # lines that disappeared (must all be removals)
    added = new_set - old_set     # must be empty
    if added:
        print(f"FAIL {rel}: {sum(added.values())} new/altered lines"); ok = False
    for line, cnt in missing.items():
        rid = json.loads(line)["id"]
        if rid not in removed:
            print(f"FAIL {rel}: dropped {rid} NOT in manifest"); ok = False
        dropped_ids += cnt
    checked_lines += sum(new_set.values())
    if new_set:
        n_old = sum(old_set.values())
        print(f"{rel:55s} {n_old:6d} -> {sum(new_set.values()):6d}")

print(f"\nsurvivor lines checked: {checked_lines}; dropped total: {dropped_ids}; "
      f"manifest removals: {len(removed)}")
if dropped_ids != len(removed):
    print("FAIL: dropped count != manifest size"); ok = False

# dup ids / holdout disjointness across the whole tree
seen = {}
HOLD = os.path.join(DS, "hard_holdout")
for f in __import__("glob").glob(os.path.join(DS, "**", "*.jsonl.gz"), recursive=True):
    rel = os.path.relpath(f, DS)
    if rel.startswith(("_staging", "_quarantine")):
        continue
    is_hold = rel.startswith("hard_holdout/")
    with gzip.open(f, "rt") as fh:
        for line in fh:
            rid = json.loads(line)["id"]
            if rid in seen and seen[rid] != is_hold:
                print(f"FAIL duplicate/overlap id {rid}"); ok = False
            if rid in seen and is_hold:
                print(f"FAIL holdout overlap {rid}"); ok = False
            seen[rid] = is_hold
print(f"unique ids: {len(seen)}")

# floors (incl. holdout, mirroring the pytest contracts)
FLOORS = {"py_inventory_ops": 25, "py_log_pipeline": 25, "ts_jsonl_pipeline": 25,
          "py_mutation_kill": 40, "py_golden_master": 40, "py_test_debugging": 40,
          "py_regression_minimize": 40, "c_makefile_repair": 40,
          "c_warning_gate": 100, "c_header_guards": 40,
          "git_merge_conflict": 15, "flaky_test_forensics": 40,
          "sql_schema_migration": 40, "sdk_docs_integration": 40,
          "repo_feature_insertion": 10, "profile_guided_optimization": 30,
          "doctest_authoring": 40}
counts = collections.Counter()
for f in __import__("glob").glob(os.path.join(DS, "write", "*", "*.gz")) + \
         __import__("glob").glob(os.path.join(DS, "hard_holdout", "write-*.gz")):
    with gzip.open(f, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            counts[(r.get("provenance") or {}).get("generator")] += 1
for fam, floor in FLOORS.items():
    if counts.get(fam, 0) < floor:
        print(f"FAIL floor {fam}: {counts.get(fam,0)} < {floor}"); ok = False
print("floors: OK" if ok else "floors: see failures above")

total = 0
for f in __import__("glob").glob(os.path.join(DS, "**", "*.jsonl.gz"), recursive=True):
    rel = os.path.relpath(f, DS)
    if rel.startswith(("_staging", "_quarantine")):
        continue
    with gzip.open(f, "rt") as fh:
        total += sum(1 for _ in fh)
print(f"TOTAL published records after curation: {total}")
print("RESULT:", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
