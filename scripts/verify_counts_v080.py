#!/usr/bin/env python3
"""v0.8.0 independent recount from published shards (audit-style).

Counts every published record from the gzip shards, cross-checks against
reports/stats.json, verifies id uniqueness per dataset namespace and that
hard_holdout stays id-disjoint from train/validation/test.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASETS = {
    "write": "datasets/write",
    "understand": "datasets/understand",
    "media": "datasets/media",
    "game_engineering": "datasets/game_engineering",
    "reverse_engineering": "datasets/reverse_engineering",
    "agent_ops": "datasets/agent_ops",
}
HOLDOUT = "datasets/hard_holdout"
HOLDOUT_PREFIX = {"write": "write-", "understand": "understand-",
                  "media": "media-", "game_engineering": "game-",
                  "reverse_engineering": "re-", "agent_ops": "ops-"}


def count_dir(pattern):
    n, ids = 0, []
    for p in sorted(glob.glob(os.path.join(ROOT, pattern))):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                n += 1
                ids.append(rec["id"])
    return n, ids


def main():
    grand = Counter()
    all_ids = defaultdict(list)
    for ds, base in DATASETS.items():
        if ds in ("write", "understand"):
            # module-01 datasets have no kind subdirectory
            n, ids = count_dir(os.path.join(base, "*", "*.jsonl.gz"))
            if n:
                grand[ds] = n
                all_ids[ds].extend(ids)
            continue
        for kind in ("write", "understand"):
            n, ids = count_dir(os.path.join(base, kind, "*", "*.jsonl.gz"))
            if n:
                grand[f"{ds}_{kind}"] = n
                all_ids[ds].extend(ids)
    holdout = Counter()
    for ds, prefix in HOLDOUT_PREFIX.items():
        if ds in ("write", "understand"):
            n, ids = count_dir(os.path.join(HOLDOUT, f"{prefix}*.jsonl.gz"))
            if n:
                holdout[ds] = n
                all_ids[ds].extend(ids)
                grand[f"{ds}_holdout"] = n
            continue
        for kind in ("write", "understand"):
            n, ids = count_dir(os.path.join(
                HOLDOUT, f"{prefix}{kind}-*.jsonl.gz"))
            if n:
                holdout[f"{ds}_{kind}"] = n
                all_ids[ds].extend(ids)
                grand[f"{ds}_{kind}_holdout"] = n

    dup_total = 0
    for ds, ids in all_ids.items():
        c = Counter(ids)
        dupes = {k: v for k, v in c.items() if v > 1}
        dup_total += sum(v - 1 for v in dupes.values())
        if dupes:
            print(f"  DUPLICATE ids in {ds}: {list(dupes.items())[:5]}")

    hold_ids = set()
    norm_ids = set()
    for ds, ids in all_ids.items():
        pass
    # id-disjoint check: holdout ids must not appear in normal splits
    for ds, base in DATASETS.items():
        normal = set()
        for kind in ("write", "understand"):
            for p in glob.glob(os.path.join(ROOT, base, kind, "*", "*.jsonl.gz")):
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            normal.add(json.loads(line)["id"])
        hp = []
        for p in glob.glob(os.path.join(ROOT, HOLDOUT, f"{HOLDOUT_PREFIX[ds]}*.jsonl.gz")):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        hp.append(json.loads(line)["id"])
        overlap = normal & set(hp)
        if overlap:
            print(f"  HOLDOUT OVERLAP in {ds}: {len(overlap)} ids")
        norm_ids |= normal
        hold_ids |= set(hp)

    published = sum(v for k, v in grand.items() if not k.endswith("holdout"))
    held = sum(holdout.values())
    print(f"published: {published}")
    print(f"hard_holdout: {held}")
    print(f"grand total: {published + held}")
    print(f"per stage: {dict(grand)}")
    print(f"duplicate ids: {dup_total}")
    print(f"holdout/normal overlap: {len(norm_ids & hold_ids)}")
    # cross-check vs stats.json (totals INCLUDE the dataset's holdout)
    stats = json.load(open(os.path.join(ROOT, "reports", "stats.json")))
    ok = True
    stage_map = {}
    for ds, base in DATASETS.items():
        if ds in ("write", "understand"):
            stage_map[ds] = grand[ds] + holdout[ds]
        else:
            for kind in ("write", "understand"):
                k = f"{ds}_{kind}"
                if k in grand:
                    stage_map[k] = grand[k] + holdout[k]
    for key, n in stage_map.items():
        stage = stats.get(key)
        if stage is None:
            continue
        st = stage.get("total") if isinstance(stage, dict) else None
        if st is not None and st != n:
            print(f"  STATS MISMATCH {key}: shards+holdout {n} vs stats {st}")
            ok = False
    print("RESULT:", "OK" if (dup_total == 0 and ok and
                              len(norm_ids & hold_ids) == 0) else "FAIL")


if __name__ == "__main__":
    main()
