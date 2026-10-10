#!/usr/bin/env python3
"""v0.7.0 split repair: close the evaluation gaps found in the external audit.

Surgical, deterministic and group-atomic. Two repairs:

1. re_write / re_understand had no validation split (re_understand was
   100% train). Root cause: both datasets have very few (family|variant)
   groups, so the v0.6.0 hash landed every non-holdout group in train.
   Fix: recover the EXACT original groups by joining published records with
   the batch-005 staging files (provenance (generator, seed) is unique per
   record), keep hard_holdout records untouched, and re-assign the remaining
   groups among train/validation/test with the same hash plus a coverage
   fix-up guaranteeing at least one validation group and one test group.

2. media_write had 3 hard_holdout records and media_understand had zero.
   Fix: new holdout policy for the media datasets - EVERY expert-difficulty
   record moves to datasets/hard_holdout. The full media_mv_project experts
   are precisely the "complete unseen projects" evaluation set the audit
   asked for. Non-expert records keep their current split membership.

The script is idempotent and never changes record ids or record bodies.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.splits import _h  # noqa: E402

STAGING = {
    "write": os.path.join(ROOT, "datasets", "_staging_archive", "write_batch005.jsonl"),
    "understand": os.path.join(ROOT, "datasets", "_staging_archive", "understand_batch005.jsonl"),
}

DATASETS = {
    "re_write": {
        "dir": "reverse_engineering", "kind": "write", "prefix": "re",
        "join_staging": "write",
    },
    "re_understand": {
        "dir": "reverse_engineering", "kind": "understand", "prefix": "re",
        "join_staging": "understand",
    },
    "media_write": {
        "dir": "media", "kind": "write", "prefix": "media",
        "join_staging": None,
    },
    "media_understand": {
        "dir": "media", "kind": "understand", "prefix": "media",
        "join_staging": None,
    },
}


def load_staging_meta(kind):
    """{(generator, seed): {"family","variant","difficulty"}} for batch-005.

    Prefers the raw staging archive; falls back to the committed group map
    (reports/re_group_map.json) so the split repair is reproducible from a
    fresh clone without the (gitignored) staging files.
    """
    if not os.path.isfile(STAGING[kind]):
        with open(os.path.join(ROOT, "reports", "re_group_map.json")) as f:
            raw = json.load(f)
        out = {}
        for key, (family, variant, difficulty) in raw.items():
            gen, seed = key.rsplit("|", 1)
            out[(gen, int(seed))] = {"family": family, "variant": variant,
                                     "difficulty": difficulty}
        return out
    meta = {}
    with open(STAGING[kind], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            prov = r["provenance"]
            meta[(prov["generator"], prov["seed"])] = dict(r["_split_meta"])
    return meta


def load_published(ds_key):
    """All records of one dataset+kind with their current split label."""
    cfg = DATASETS[ds_key]
    rows = []  # (split, rec)
    base = os.path.join(ROOT, "datasets", cfg["dir"], cfg["kind"])
    for split in ("train", "validation", "test"):
        d = os.path.join(base, split)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".jsonl.gz"):
                continue
            with gzip.open(os.path.join(d, name), "rt", encoding="utf-8") as f:
                for line in f:
                    rows.append((split, json.loads(line)))
    hd = os.path.join(ROOT, "datasets", "hard_holdout")
    for name in sorted(os.listdir(hd)):
        if not name.endswith(".jsonl.gz"):
            continue
        if not name.startswith(f"{cfg['prefix']}-{cfg['kind']}-shard"):
            continue
        with gzip.open(os.path.join(hd, name), "rt", encoding="utf-8") as f:
            for line in f:
                rows.append(("hard_holdout", json.loads(line)))
    return rows


def coverage_fixup(group_x):
    """Assign non-holdout groups to train/validation/test.

    Start from the v0.6.0 hash buckets, then guarantee >=1 validation group
    and >=1 test group by promoting the highest-hash train groups (closest to
    the original boundaries). Deterministic; ties broken by group name.
    """
    assign = {}
    for g, x in group_x.items():
        if x < 8000:
            assign[g] = "train"
        elif x < 9000:
            assign[g] = "validation"
        else:
            assign[g] = "test"
    by_x = sorted(group_x.items(), key=lambda kv: (-kv[1], kv[0]))
    train_pool = [g for g, _ in by_x if assign[g] == "train"]
    if not any(v == "validation" for v in assign.values()):
        g = train_pool.pop(0)
        assign[g] = "validation"
    if not any(v == "test" for v in assign.values()):
        if train_pool:
            g = train_pool.pop(0)
        else:  # extreme edge: demote the smallest validation group
            g = min((gg for gg, s in assign.items() if s == "validation"),
                    key=lambda gg: (group_x[gg], gg))
            assign[g] = "test"
        assign[g] = "test"
    return assign


def resplit_re(ds_key, rows, staging_meta):
    """Repair one reverse_engineering dataset. Returns (by_split, moved_log)."""
    groups = {}
    for split, rec in rows:
        prov = rec["provenance"]
        key = (prov["generator"], prov["seed"])
        if key not in staging_meta:
            raise SystemExit(f"JOIN MISS: {ds_key} {rec.get('id')} {key} - "
                             "refusing to guess a group (honesty policy)")
        meta = staging_meta[key]
        if meta["difficulty"] != rec["difficulty"]:
            raise SystemExit(f"difficulty mismatch for {rec.get('id')}: "
                             f"{meta['difficulty']} vs {rec['difficulty']}")
        groups[rec["id"]] = f"{meta['family']}|{meta['variant']}"

    hold_groups = {groups[r["id"]] for s, r in rows if s == "hard_holdout"}
    nonhold = {}
    for split, rec in rows:
        if split == "hard_holdout":
            continue
        g = groups[rec["id"]]
        x = _h("split|" + g) % 10000
        nonhold.setdefault(g, {"x": x, "recs": []})
        nonhold[g]["recs"].append((split, rec))

    assign = coverage_fixup({g: info["x"] for g, info in nonhold.items()})

    by_split = defaultdict(list)
    for split, rec in rows:
        if split == "hard_holdout":
            by_split["hard_holdout"].append(rec)
        else:
            by_split[assign[groups[rec["id"]]]].append(rec)

    # group-atomicity assertion across train/validation/test (the eval sets)
    seen = defaultdict(set)
    for split in ("train", "validation", "test"):
        for rec in by_split[split]:
            seen[groups[rec["id"]]].add(split)
    bad = {g: s for g, s in seen.items() if len(s) > 1}
    if bad:
        raise SystemExit(f"group straddle detected: {bad}")

    log = {
        "groups_total": len(set(groups.values())),
        "holdout_groups": sorted(hold_groups),
        "assignment": {g: assign[g] for g in sorted(assign)},
        "records_moved_from_train": sum(
            1 for split, rec in rows
            if split == "train" and split != assign[groups[rec["id"]]]),
    }
    return {k: list(v) for k, v in by_split.items()}, log


def resplit_media(ds_key, rows):
    """New holdout policy: every expert record goes to hard_holdout."""
    by_split = defaultdict(list)
    moved = []
    for split, rec in rows:
        if split != "hard_holdout" and rec["difficulty"] == "expert":
            by_split["hard_holdout"].append(rec)
            moved.append(rec["id"])
        else:
            by_split[split].append(rec)
    log = {"experts_moved_to_holdout": sorted(moved),
           "holdout_total": len(by_split["hard_holdout"])}
    return {k: list(v) for k, v in by_split.items()}, log


def write_shards(ds_key, by_split):
    cfg = DATASETS[ds_key]
    base = os.path.join(ROOT, "datasets", cfg["dir"], cfg["kind"])
    for split in ("train", "validation", "test"):
        d = os.path.join(base, split)
        os.makedirs(d, exist_ok=True)
        for old in os.listdir(d):
            if old.startswith(f"{cfg['prefix']}-shard"):
                os.remove(os.path.join(d, old))
        rows = sorted(by_split.get(split, []),
                      key=lambda r: (r["language"], r["id"]))
        if rows:
            path = os.path.join(d, f"{cfg['prefix']}-shard-00000.jsonl.gz")
            with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
                for rec in rows:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # hard_holdout: shard names are qualified with the kind
    hd = os.path.join(ROOT, "datasets", "hard_holdout")
    shard_prefix = f"{cfg['prefix']}-{cfg['kind']}-shard"
    for old in os.listdir(hd):
        if old.startswith(shard_prefix):
            os.remove(os.path.join(hd, old))
    rows = sorted(by_split.get("hard_holdout", []),
                  key=lambda r: (r["language"], r["id"]))
    if rows:
        path = os.path.join(hd, f"{shard_prefix}-00000.jsonl.gz")
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
            for rec in rows:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    summary = {}
    for ds_key in ("re_write", "re_understand", "media_write", "media_understand"):
        cfg = DATASETS[ds_key]
        rows = load_published(ds_key)
        n0 = len(rows)
        if cfg["join_staging"]:
            meta = load_staging_meta(cfg["join_staging"])
            by_split, log = resplit_re(ds_key, rows, meta)
        else:
            by_split, log = resplit_media(ds_key, rows)
        n1 = sum(len(v) for v in by_split.values())
        assert n0 == n1, f"{ds_key}: record count changed {n0} -> {n1}"
        write_shards(ds_key, by_split)
        splits = {k: len(v) for k, v in sorted(by_split.items())}
        summary[ds_key] = {"total": n1, "splits": splits, **log}
        print(f"[{ds_key}] total={n1} splits={json.dumps(splits)}")
    out = os.path.join(ROOT, "reports", "resplit_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"summary -> {out}")


if __name__ == "__main__":
    main()
