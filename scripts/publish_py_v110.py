#!/usr/bin/env python3
"""v1.1.0 delta publisher: merge staged batch 010 into the write dataset.

Unlike finalize.py (full rebuild from staging), this publisher APPENDS to
the existing published shards so pre-existing records keep their ids,
splits and content exactly (the audit's holdout-integrity promise stays):

  * batch 011 -> AI-ku_superprogrammer_write (3 build-craft families)

Split policy for NEW records (same rules as finalize.assign_split for the
write dataset):
  * expert groups with hold-hash < 25 -> hard_holdout
  * every other new group -> standard split-hash buckets

Ids: new records continue after the dataset's current max (one id
namespace per dataset, v0.7.0 rule). Shards are rewritten sorted by id
with gzip mtime=0; every pre-existing record keeps its id, split and
content byte-for-byte.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.dedup import DedupIndex, normalize  # noqa: E402
from validators.splits import holdout_hash, split_hash  # noqa: E402

SHARD_SIZE = 2000
STAGING = ["datasets/_staging/write_batch011.jsonl"]
BASE = os.path.join(ROOT, "datasets", "write")
PREFIX = "write"
DATASET = "AI-ku_superprogrammer_write"


def _record_body(rec):
    parts = []
    if rec.get("code"):
        parts.append(rec["code"])
    files = rec.get("files") or rec.get("input", {}).get("files")
    if files:
        parts.extend(f["content"] for f in files)
    if rec.get("tests"):
        parts.append(rec["tests"])
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


def main():
    # ---- load published state -------------------------------------------
    existing = []            # (split, rec)
    seen_exact = set()
    seen_norm = set()
    max_id = 0
    for split in ("train", "validation", "test"):
        sd = os.path.join(BASE, split)
        if not os.path.isdir(sd):
            continue
        for name in sorted(os.listdir(sd)):
            if not name.endswith(".jsonl.gz"):
                continue
            with gzip.open(os.path.join(sd, name), "rt",
                           encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    existing.append((split, rec))
                    seen_exact.add(_exact_hash(rec))
                    seen_norm.add(_norm_hash(rec))
                    try:
                        max_id = max(max_id, int(rec["id"].split("-")[1]))
                    except (ValueError, IndexError):
                        pass
    hold_dir = os.path.join(ROOT, "datasets", "hard_holdout")
    hold_names = sorted(n for n in os.listdir(hold_dir)
                        if n.startswith(f"{PREFIX}-") and
                        n.endswith(".jsonl.gz"))
    for name in hold_names:
        with gzip.open(os.path.join(hold_dir, name), "rt",
                       encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                existing.append(("hard_holdout", rec))
                seen_exact.add(_exact_hash(rec))
                seen_norm.add(_norm_hash(rec))
                try:
                    max_id = max(max_id, int(rec["id"].split("-")[1]))
                except (ValueError, IndexError):
                    pass
    print(f"published write records: {len(existing)}; max id "
          f"{PREFIX}-{max_id:07d}")

    # ---- load staged batch ----------------------------------------------
    staged = []
    for rel in STAGING:
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
                staged.append(rec)
    print(f"staged: {len(staged)}")

    # ---- dedup + assign --------------------------------------------------
    dedup = DedupIndex(family_cap=None)
    new_groups = {}
    new_recs = []
    dupes = 0
    for rec in staged:
        eh = _exact_hash(rec)
        nh = _norm_hash(rec)
        if eh in seen_exact or nh in seen_norm or nh in dedup.norm:
            dupes += 1
            continue
        seen_exact.add(eh)
        seen_norm.add(nh)
        dedup.norm.add(nh)
        new_recs.append(rec)
        meta = rec["_split_meta"]
        new_groups.setdefault(
            f"{meta['family']}|{meta['variant']}",
            split_hash(meta["family"], meta["variant"]))
    print(f"dupes removed: {dupes}; new unique: {len(new_recs)}; "
          f"new groups: {len(new_groups)}")

    counters = max_id
    added = defaultdict(int)
    holdout_added = 0
    for rec in new_recs:
        meta = rec["_split_meta"]
        group = f"{meta['family']}|{meta['variant']}"
        if meta.get("difficulty") == "expert" and \
                holdout_hash(meta["family"], meta["variant"]) < 25:
            split = "hard_holdout"
            holdout_added += 1
        else:
            x = new_groups[group]
            split = ("train" if x < 8000 else
                     "validation" if x < 9000 else "test")
        counters += 1
        rec["id"] = f"{PREFIX}-{counters:07d}"
        rec["dataset"] = DATASET
        existing.append((split, rec))
        added[split] += 1
    print(f"added: {dict(added)} (holdout {holdout_added})")

    # ---- rewrite shards (byte-preserving for untouched records) ----------
    by_split = defaultdict(list)
    for split, rec in existing:
        by_split[split].append(rec)
    for split, recs in sorted(by_split.items()):
        recs.sort(key=lambda r: r["id"])
        out_dir = (hold_dir if split == "hard_holdout"
                   else os.path.join(BASE, split))
        os.makedirs(out_dir, exist_ok=True)
        shard_prefix = (f"{PREFIX}-write" if split == "hard_holdout"
                        else PREFIX)
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
        print(f"  rewrote write/{split}: {len(recs)} records")
    print("publisher done")


if __name__ == "__main__":
    main()
