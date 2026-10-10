#!/usr/bin/env python3
"""v0.7.0 record-id migration: one id namespace per dataset, not per kind.

Usage: python3 scripts/fix_ids_v070.py

Defect found during the v0.7.0 audit: finalize_group numbered ids per
(dataset, kind) group, so media/game/re/ops ids collide ACROSS kinds with
different content (e.g. game-0000714 exists in both write/train and
understand/test). Ambiguous ids since v0.1.0.

Fix: reassign ids with ONE counter per dataset (prefix kept), ordering all
records of the dataset - both kinds, all splits, hard_holdout included -
by (kind, language, family, seed). Deterministic; module-01 datasets
(write/understand) are single-kind and keep their ids untouched.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASETS = {
    "AI-ku_superprogrammer_media": ("media", "datasets/media"),
    "AI-ku_superprogrammer_game_engineering": ("game", "datasets/game_engineering"),
    "AI-ku_superprogrammer_reverse_engineering": ("re", "datasets/reverse_engineering"),
    "AI-ku_superprogrammer_agent_ops": ("ops", "datasets/agent_ops"),
}


def shard_paths(base):
    out = []
    for kind in ("write", "understand"):
        kdir = os.path.join(ROOT, base, kind)
        if not os.path.isdir(kdir):
            continue
        for split in ("train", "validation", "test"):
            d = os.path.join(kdir, split)
            if os.path.isdir(d):
                for name in sorted(os.listdir(d)):
                    if name.endswith(".jsonl.gz"):
                        out.append(os.path.join(d, name))
    return out


def holdout_paths(prefix):
    hd = os.path.join(ROOT, "datasets", "hard_holdout")
    out = []
    for name in sorted(os.listdir(hd)):
        if name.endswith(".jsonl.gz") and name.startswith(f"{prefix}-"):
            out.append(os.path.join(hd, name))
    return out


def rewrite(path, id_map):
    tmp = path + ".tmp"
    with gzip.open(path, "rt", encoding="utf-8") as f, \
            gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as out:
        for line in f:
            rec = json.loads(line)
            rec["id"] = id_map[(rec["kind"], rec["provenance"]["generator"],
                                rec["provenance"]["seed"], rec["language"])]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def main():
    for ds_name, (prefix, base) in DATASETS.items():
        paths = shard_paths(base) + holdout_paths(prefix)
        recs = []
        for p in paths:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                for line in f:
                    recs.append((p, json.loads(line)))
        # deterministic global order across kinds and splits
        recs.sort(key=lambda pr: (pr[1]["kind"], pr[1]["language"],
                                  pr[1]["provenance"]["generator"],
                                  pr[1]["provenance"]["seed"]))
        id_map = {}
        for i, (_p, r) in enumerate(recs, 1):
            new_id = f"{prefix}-{i:07d}"
            key = (r["kind"], r["provenance"]["generator"],
                   r["provenance"]["seed"], r["language"])
            if key in id_map:
                raise SystemExit(f"collision on model key {key} in {ds_name}")
            id_map[key] = new_id
        for p in paths:
            rewrite(p, id_map)
        print(f"{ds_name}: {len(recs)} records -> {prefix}-0000001.."
              f"{prefix}-{len(recs):07d} (ids unique across kinds)")


if __name__ == "__main__":
    main()
