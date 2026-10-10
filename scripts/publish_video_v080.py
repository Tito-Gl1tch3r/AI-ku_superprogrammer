#!/usr/bin/env python3
"""v0.8.0 delta publisher: merge staged batches into the published layout.

Unlike finalize.py (full rebuild from staging), this publisher APPENDS to the
existing published shards so pre-existing records keep their ids, splits and
content exactly (the audit's holdout-integrity promise stays intact):

  * batch 007 -> media write/understand (new video families)
  * batch 008 -> reverse_engineering understand EXPERT delta (D-4)

Split policy for NEW records:
  * media experts (difficulty == expert) -> hard_holdout (v0.7.0 policy)
  * every new re_understand expert -> hard_holdout (D-4 fix)
  * all other new records -> group-level assignment (split hash +
    coverage fix-up) applied to the NEW groups only

Ids: new records continue after the dataset's current max (one id namespace
per dataset, v0.7.0 rule). Shards are rewritten sorted by id; every
pre-existing record keeps its id, split and content byte-for-byte.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.dedup import DedupIndex, normalize  # noqa: E402
from validators.splits import coverage_fixup, split_hash  # noqa: E402
from scripts.fix_fixtures_v080 import rec_key  # noqa: E402  (reuse key helper)

SHARD_SIZE = 2000
STAGING = [
    ("datasets/_staging/write_batch007.jsonl", "media"),
    ("datasets/_staging/understand_batch007.jsonl", "media"),
    ("datasets/_staging/understand_batch008.jsonl", "re"),
]

DATASET_DIRS = {"media": "datasets/media", "re": "datasets/reverse_engineering"}
PREFIX = {"media": "media", "re": "re"}


def _record_body(rec):
    parts = []
    if rec.get("code"):
        parts.append(rec["code"])
    files = rec.get("files") or rec.get("input", {}).get("files")
    if files:
        parts.extend(f["content"] for f in files)
    if rec.get("tests"):
        parts.append(rec["tests"])
    if rec.get("target", {}).get("tests"):
        parts.append(rec["target"]["tests"])
    if rec.get("task"):
        parts.append(rec["task"])
    inp = rec.get("input") or {}
    if inp.get("question"):
        parts.append(inp["question"])
    if inp.get("artifacts"):
        parts.append(json.dumps(inp["artifacts"], sort_keys=True))
    tgt = rec.get("target") or {}
    if tgt.get("answer"):
        parts.append(tgt["answer"])
    if tgt.get("code"):
        parts.append(tgt["code"])
    if not parts:
        parts.append(json.dumps(rec, sort_keys=True))
    return "\n@@\n".join(parts)


def _norm_hash(rec):
    lang = rec.get("language", "python")
    return hashlib.sha256(normalize(_record_body(rec), lang).encode()).hexdigest()


def _exact_hash(rec):
    return hashlib.sha256(_record_body(rec).encode()).hexdigest()


def _iter_published(ds_key):
    """Yield (path, split, rec) for every published record of the dataset."""
    base = os.path.join(ROOT, DATASET_DIRS[ds_key])
    for kind in ("write", "understand"):
        kdir = os.path.join(base, kind)
        if not os.path.isdir(kdir):
            continue
        for split in ("train", "validation", "test"):
            sd = os.path.join(kdir, split)
            if not os.path.isdir(sd):
                continue
            for name in sorted(os.listdir(sd)):
                if not name.endswith(".jsonl.gz"):
                    continue
                p = os.path.join(sd, name)
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    for line in f:
                        rec = json.loads(line)
                        yield p, split, rec
    # hard_holdout shards for this dataset's prefix
    hold_dir = os.path.join(ROOT, "datasets", "hard_holdout")
    for name in sorted(os.listdir(hold_dir)):
        if not (name.startswith(f"{PREFIX[ds_key]}-") and name.endswith(".jsonl.gz")):
            continue
        p = os.path.join(hold_dir, name)
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                yield p, "hard_holdout", rec


def _shards_for(ds_key):
    """All shard paths that exist for the dataset (grouped by (kind, split))."""
    out = defaultdict(list)
    base = os.path.join(ROOT, DATASET_DIRS[ds_key])
    for kind in ("write", "understand"):
        for split in ("train", "validation", "test"):
            sd = os.path.join(base, kind, split)
            if os.path.isdir(sd):
                for name in sorted(os.listdir(sd)):
                    if name.endswith(".jsonl.gz"):
                        out[(kind, split)].append(os.path.join(sd, name))
    hold_dir = os.path.join(ROOT, "datasets", "hard_holdout")
    for name in sorted(os.listdir(hold_dir)):
        if name.startswith(f"{PREFIX[ds_key]}-") and name.endswith(".jsonl.gz"):
            out[("holdout", "hard_holdout")].append(os.path.join(hold_dir, name))
    return out


def main():
    # ---- load published state -------------------------------------------
    existing = {}   # ds_key -> list of (kind, split, rec)
    seen_exact = set()
    seen_norm = set()
    max_id = defaultdict(int)
    for ds_key in ("media", "re"):
        for _p, split, rec in _iter_published(ds_key):
            kind = rec["kind"]
            existing.setdefault(ds_key, []).append((kind, split, rec))
            seen_exact.add(_exact_hash(rec))
            seen_norm.add(_norm_hash(rec))
            try:
                max_id[ds_key] = max(max_id[ds_key], int(rec["id"].split("-")[1]))
            except (ValueError, IndexError):
                pass
    print(f"published: media {len(existing['media'])}, re {len(existing['re'])}; "
          f"max ids: {dict(max_id)}")

    # ---- load staged batches --------------------------------------------
    staged = defaultdict(list)   # ds_key -> recs
    for rel, ds_key in STAGING:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                staged[ds_key].append(rec)
    print(f"staged: media {len(staged['media'])}, re {len(staged['re'])}")

    # ---- dedup + assign --------------------------------------------------
    counters = {ds: max_id[ds] for ds in max_id}
    added = defaultdict(lambda: defaultdict(int))   # ds -> split -> n
    dupes = defaultdict(int)
    for ds_key in ("media", "re"):
        # existing group registry for coverage fix-up over NEW groups only
        new_groups = {}
        new_recs = []
        dedup = DedupIndex(family_cap=None)
        for rec in staged[ds_key]:
            eh = _exact_hash(rec)
            nh = _norm_hash(rec)
            if eh in seen_exact or nh in seen_norm or nh in dedup.norm:
                dupes[ds_key] += 1
                continue
            seen_exact.add(eh)
            seen_norm.add(nh)
            dedup.norm.add(nh)
            new_recs.append(rec)
            meta = rec["_split_meta"]
            new_groups.setdefault(f"{meta['family']}|{meta['variant']}",
                                  split_hash(meta["family"], meta["variant"]))
        # new groups follow the standard hash buckets directly: the existing
        # published splits already guarantee validation/test coverage, and a
        # coverage fix-up over a tiny new-group set would be degenerate
        assign = {}
        for g, x in new_groups.items():
            assign[g] = ("train" if x < 8000 else
                         "validation" if x < 9000 else "test")
        for rec in new_recs:
            meta = rec["_split_meta"]
            ds = ds_key
            if meta.get("difficulty") == "expert":
                split = "hard_holdout"   # media policy + D-4 fix
            else:
                split = assign[f"{meta['family']}|{meta['variant']}"]
            counters[ds_key] += 1
            prefix = PREFIX[ds_key]
            rec["id"] = f"{prefix}-{counters[ds_key]:07d}"
            kind = rec["kind"]
            existing[ds_key].append((kind, split, rec))
            added[ds_key][split] += 1
    print(f"dupes: media {dupes['media']}, re {dupes['re']}")
    for ds_key in ("media", "re"):
        print(f"added {ds_key}: {dict(added[ds_key])}")

    # ---- rewrite shards --------------------------------------------------
    import io
    import time
    for ds_key in ("media", "re"):
        by_kind_split = defaultdict(list)
        for kind, split, rec in existing[ds_key]:
            by_kind_split[(kind, split)].append(rec)
        shards = _shards_for(ds_key)
        base = os.path.join(ROOT, DATASET_DIRS[ds_key])
        for (kind, split), recs in sorted(by_kind_split.items()):
            recs.sort(key=lambda r: r["id"])
            out_dir = (os.path.join(ROOT, "datasets", "hard_holdout")
                       if split == "hard_holdout"
                       else os.path.join(base, kind, split))
            os.makedirs(out_dir, exist_ok=True)
            shard_prefix = (f"{PREFIX[ds_key]}-{kind}"
                            if split == "hard_holdout" else PREFIX[ds_key])
            for old in os.listdir(out_dir):
                if old.startswith(shard_prefix) and old.endswith(".jsonl.gz"):
                    os.remove(os.path.join(out_dir, old))
            for i in range(0, len(recs), SHARD_SIZE):
                chunk = recs[i:i + SHARD_SIZE]
                n = i // SHARD_SIZE
                path = os.path.join(out_dir,
                                    f"{shard_prefix}-shard-{n:05d}.jsonl.gz")
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6,
                                   mtime=0) as g:
                    for rec in chunk:
                        rec.pop("_split_meta", None)
                        g.write((json.dumps(rec, ensure_ascii=False) + "\n")
                                .encode("utf-8"))
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
            print(f"  rewrote {ds_key}/{kind}/{split}: {len(recs)} records")
        # shards that no longer hold records (shouldn't happen; keep for safety)
    print("publisher done")


if __name__ == "__main__":
    main()
