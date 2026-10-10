#!/usr/bin/env python3
"""Before/after integrity proof for the v0.9.0 append publisher.

Usage:
    python3 scripts/verify_append_v090.py snapshot /tmp/v090_before.json
    python3 scripts/verify_append_v090.py check    /tmp/v090_before.json

The snapshot maps every published write-dataset record id to the sha256 of
its canonical JSON; `check` re-derives it and asserts every pre-existing id
is byte-identical and no pre-existing id changed split.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "datasets", "write")
HOLD = os.path.join(ROOT, "datasets", "hard_holdout")


def _snapshot():
    snap = {}
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
                    snap[rec["id"]] = [split, hashlib.sha256(
                        json.dumps(rec, sort_keys=True,
                                   ensure_ascii=False).encode()).hexdigest()]
    for name in sorted(os.listdir(HOLD)):
        if not name.startswith("write-"):
            continue
        with gzip.open(os.path.join(HOLD, name), "rt",
                       encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                snap[rec["id"]] = ["hard_holdout", hashlib.sha256(
                    json.dumps(rec, sort_keys=True,
                               ensure_ascii=False).encode()).hexdigest()]
    return snap


def main():
    mode, path = sys.argv[1], sys.argv[2]
    snap = _snapshot()
    if mode == "snapshot":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snap, f)
        print(f"snapshot: {len(snap)} record ids -> {path}")
        return
    with open(path, encoding="utf-8") as f:
        before = json.load(f)
    changed = moved = missing = 0
    for rid, (split, digest) in before.items():
        now = snap.get(rid)
        if now is None:
            missing += 1
        elif now[1] != digest:
            changed += 1
        elif now[0] != split:
            moved += 1
    new_ids = len(snap) - len(before)
    print(f"pre-existing: {len(before)} | changed: {changed} | "
          f"moved: {moved} | missing: {missing} | new ids: {new_ids}")
    if changed or moved or missing:
        sys.exit(1)
    print("INTEGRITY OK: every pre-existing record byte-identical, "
          "splits stable")


if __name__ == "__main__":
    main()
