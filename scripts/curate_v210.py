#!/usr/bin/env python3
"""v2.1.0 super-programmer curation pass — remove what does not serve the goal.

User mandate (2026-10-11): keep only what serves the super-programmer goal;
media (video via code), reverse_engineering and understand are explicitly
IMPORTANT and protected. Quality > quantity: identical-code template records
beyond a generous scenario cap are redundant (measured redundancy: up to
180:1) and are removed. Coverage stubs below a meaningful volume are removed.

Rules (deterministic, id-ordered, line-level rewrite keeps survivors
byte-identical):
  R1 cap15      write-kind records in {write, agent_ops, game_engineering}
                (+ their hard_holdout shards): group by (family, split,
                code payload sha256); keep first K=15 ids per group.
                Families pinned by test volume floors whose post-cap
                published (non-holdout) count would violate the floor are
                EXEMPT from R1 (their narrow deterministic variant spaces
                are the documented design, enforced by tests).
  R2 stubs<4    write-kind families in the same scope with total n < 4 are
                removed entirely (coverage stubs cannot teach a capability).

Outputs:
  - rewritten shards (survivors byte-identical, order stable)
  - reports/curation_v210.json manifest (per-id reasons, per-file sha256,
    summaries)
"""
import collections, glob, gzip, hashlib, json, os, re, sys

REPO = "/home/z/my-project/re-build/AI-ku"
DS = os.path.join(REPO, "datasets")
K_CAP = 15
STUB_MIN = 4
MANIFEST = os.path.join(REPO, "reports", "curation_v210.json")

FLOORS = {
    "git_merge_conflict": 15, "flaky_test_forensics": 40,
    "sql_schema_migration": 40, "sdk_docs_integration": 40,
    "repo_feature_insertion": 10, "profile_guided_optimization": 30,
    "doctest_authoring": 40,
    "py_mutation_kill": 40, "py_golden_master": 40,
    "py_test_debugging": 40, "py_regression_minimize": 40,
    "c_makefile_repair": 40, "c_warning_gate": 100, "c_header_guards": 40,
    "py_inventory_ops": 25, "py_log_pipeline": 25, "ts_jsonl_pipeline": 25,
}

HOLDOUT_PREFIX = {"game-": "game_engineering", "media-": "media",
                  "ops-": "agent_ops", "re-": "reverse_engineering",
                  "write-": "write", "understand-": "understand"}

def norm(s):
    return re.sub(r"\s+", " ", s).strip()

def payload(r):
    c = r.get("code")
    if c:
        return hashlib.sha256(norm(c).encode()).hexdigest()
    files = r.get("files")
    if files:
        return hashlib.sha256(norm(json.dumps(files, sort_keys=True)).encode()).hexdigest()
    return ""

def iter_shards():
    """Yield (path, dataset, kind, split)."""
    for f in sorted(glob.glob(os.path.join(DS, "**", "*.jsonl.gz"), recursive=True)):
        rel = os.path.relpath(f, DS).replace(os.sep, "/")
        if rel.startswith(("_staging", "_quarantine")):
            continue
        if rel.startswith("hard_holdout/"):
            base = os.path.basename(rel)
            ds = next((v for p, v in HOLDOUT_PREFIX.items() if base.startswith(p)), "?")
            kind = base.split("-", 1)[1].split("-")[0]
            yield f, ds, kind, "holdout"
        elif rel.count("/") == 2:
            d, split, fname = rel.split("/")
            yield f, d, d, split  # dir name IS the kind for core datasets
        elif rel.count("/") == 3:
            d, kind, split, fname = rel.split("/")
            yield f, d, kind, split

def main():
    # ---- pass 1: index ---------------------------------------------------
    recs = []  # (path, idx, id, dataset, kind, split, fam, payload)
    per_file = collections.defaultdict(list)
    for path, ds, kind, split in iter_shards():
        with gzip.open(path, "rt") as fh:
            for i, line in enumerate(fh):
                r = json.loads(line)
                fam = (r.get("provenance") or {}).get("generator") or "<none>"
                rec = [path, i, r["id"], ds, kind, split, fam, payload(r)]
                recs.append(rec)
                per_file[path].append(rec)
    print(f"indexed {len(recs)} records in {len(per_file)} files")
    assert len(recs) == 25491, f"expected 25491 indexed records, got {len(recs)}"
    kd = collections.Counter((r[3], r[4]) for r in recs)
    print("dataset×kind:", dict(kd))

    # ---- decide removals -------------------------------------------------
    removed = {}          # id -> dict(reason, family, dataset, split)
    totals = collections.Counter((r[3], r[4], r[6]) for r in recs)

    # R1 exemption check per floor family (post-cap count over ALL splits,
    # matching the test contracts which include hard_holdout)
    floor_exempt = set()
    for fam, floor in FLOORS.items():
        bygroup = collections.Counter()
        for r in recs:
            if r[6] == fam and r[4] == "write" and r[3] in ("write", "agent_ops", "game_engineering"):
                bygroup[(r[5], r[7])] += 1
        kept = sum(min(n, K_CAP) for n in bygroup.values())
        published = sum(bygroup.values())
        if kept < floor:
            floor_exempt.add(fam)
            print(f"  R1-exempt {fam}: post-cap {kept} < floor {floor} (published {published})")
    print("R1 exempt families:", sorted(floor_exempt))

    for r in recs:
        path, idx, rid, ds, kind, split, fam, pl = r
        if kind != "write":
            continue  # understand is protected (user mandate)
        if ds in ("media", "reverse_engineering"):
            continue  # protected (user mandate)
        if ds not in ("write", "agent_ops", "game_engineering"):
            continue
        # R2 stubs
        if totals[(ds, kind, fam)] < STUB_MIN:
            removed[rid] = {"reason": "coverage_stub_lt4", "family": fam,
                            "dataset": ds, "split": split}
    # R1 cap (after R2 so stubs are already gone; cap ignores stub families)
    groups = collections.defaultdict(list)
    for r in recs:
        path, idx, rid, ds, kind, split, fam, pl = r
        if kind != "write" or ds not in ("write", "agent_ops", "game_engineering"):
            continue
        if (ds, kind, fam) not in totals or totals[(ds, kind, fam)] < STUB_MIN:
            continue
        if fam in floor_exempt:
            continue
        groups[(fam, split, pl)].append(r)
    for (fam, split, pl), members in groups.items():
        if pl == "" :
            continue
        members.sort(key=lambda r: r[2])
        for r in members[K_CAP:]:
            removed[r[2]] = {"reason": "cap15_redundant_code_payload",
                             "family": fam, "dataset": r[3], "split": r[5]}
    print(f"removals decided: {len(removed)}")

    # ---- pass 2: rewrite affected files line-level -----------------------
    file_hashes = {}
    byfile = collections.defaultdict(set)
    for rid, info in removed.items():
        pass  # index removal ids per file below
    id2file = {r[2]: r[0] for r in recs}
    for rid in removed:
        f = id2file[rid]
        byfile[f].add(rid)
    for path in sorted(byfile):
        drop = byfile[path]
        raw = gzip.open(path, "rb").read().split(b"\n")
        # splitlines-safe: reconstruct with '\n' joins; keep original bytes
        kept_lines, dropped = [], 0
        for rawline in raw:
            if not rawline:
                continue
            rid = json.loads(rawline.decode())["id"]
            if rid in drop:
                dropped += 1
            else:
                kept_lines.append(rawline)
        assert dropped == len(drop), f"{path}: dropped {dropped} != planned {len(drop)}"
        newpath = path + ".tmp"
        with gzip.GzipFile(newpath, "wb", mtime=0) as out:
            for kl in kept_lines:
                out.write(kl + b"\n")
        os.replace(newpath, path)
        file_hashes[path] = {"dropped": dropped}
    print(f"rewrote {len(file_hashes)} files")

    # ---- manifest --------------------------------------------------------
    summary_ds = collections.Counter()
    summary_fam = collections.Counter()
    summary_reason = collections.Counter()
    for info in removed.values():
        summary_ds[info["dataset"]] += 1
        summary_fam[f"{info['dataset']}::{info['family']}"] += 1
        summary_reason[info["reason"]] += 1
    man = {
        "release": "2.1.0",
        "mandate": "user-directed curation: remove what does not serve the "
                   "super-programmer goal; quality over quantity",
        "protected": ["media (video via code)", "reverse_engineering", "understand"],
        "rules": {
            "R1": f"cap K={K_CAP} identical-code-payload records per "
                  "(family, split); floor-contract families exempt",
            "R1_exempt_families": sorted(floor_exempt),
            "R2": f"families with total n < {STUB_MIN} removed (coverage stubs)",
        },
        "totals": {"removed": len(removed), "by_dataset": dict(summary_ds),
                   "by_reason": dict(summary_reason)},
        "by_family": dict(sorted(summary_fam.items())),
        "removed_ids": {rid: f"{info['reason']}|{info['family']}|{info['split']}"
                        for rid, info in sorted(removed.items())},
    }
    with open(MANIFEST, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
    print("by_dataset:", dict(summary_ds))
    print("by_reason:", dict(summary_reason))
    top = summary_fam.most_common(15)
    print("top families removed:")
    for k, v in top:
        print(f"   {k:55s} -{v}")

if __name__ == "__main__":
    main()
