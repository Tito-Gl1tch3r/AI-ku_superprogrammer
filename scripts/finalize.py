#!/usr/bin/env python3
"""Finalize staged records into the published dataset layout.

Steps: load staging -> exact+normalised dedup -> per-family caps -> quality
gate -> grouped splits (family|variant, anti-contamination) -> hard holdout
(expert groups) -> gzip JSONL shards -> ids -> stats payloads.

Quarantined (failed) records are NEVER merged; they stay in _quarantine for
manual audit, exactly per the project policy.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from validators.dedup import DedupIndex, exact_hash, normalize  # noqa: E402
from validators.schema_check import validate  # noqa: E402
from validators.splits import coverage_fixup, holdout_hash, split_hash  # noqa: E402

SHARD_SIZE = 2000

# v0.7.0 holdout policy: every expert record of the media datasets goes to
# datasets/hard_holdout (complete mv projects are the "unseen projects"
# evaluation set). All other datasets keep the v0.6.0 rule: expert groups
# with hold-hash < 25.
MEDIA_DATASETS = ("AI-ku_superprogrammer_media",)


def _record_body(rec):
    """Full semantic body: code/files + tests + task/question + answer.

    Data lives in tests/answers for template-generated examples, so the
    dedup hashes EVERYTHING (normalized) - same template + different data
    stays, renamed cosmetic variants collapse.
    """
    parts = []
    body = rec.get("code")
    if body:
        parts.append(body)
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


def _norm_hash_record(rec):
    lang = rec.get("language", "python")
    return hashlib.sha256(normalize(_record_body(rec), lang).encode()).hexdigest()


def _exact_hash_record(rec):
    return hashlib.sha256(_record_body(rec).encode()).hexdigest()


def assign_split(rec, dataset="AI-ku_superprogrammer_write"):
    meta = rec["_split_meta"]
    group = f"{meta['family']}|{meta['variant']}"
    if meta.get("difficulty") == "expert":
        if dataset in MEDIA_DATASETS:
            return "hard_holdout"
        if holdout_hash(*group.split("|", 1)) < 25:
            return "hard_holdout"
    x = split_hash(*group.split("|", 1))
    if x < 8000:
        return "train"
    if x < 9000:
        return "validation"
    return "test"


def assign_group_splits(dataset, groups_x):
    """Group-level train/validation/test assignment with coverage guarantee."""
    return coverage_fixup(groups_x)


DATASET_DIRS = {
    "AI-ku_superprogrammer_write": "write",
    "AI-ku_superprogrammer_understand": "understand",
    "AI-ku_superprogrammer_media": "media",
    "AI-ku_superprogrammer_game_engineering": "game_engineering",
    "AI-ku_superprogrammer_reverse_engineering": "reverse_engineering",
    "AI-ku_superprogrammer_agent_ops": "agent_ops",
}


def finalize_group(dataset, kind, recs, family_cap, schema):
    """Dedup + gate + split + shard one (dataset, kind) group."""
    dedup = DedupIndex(family_cap=family_cap)
    kept, dupes, capped, bad_schema = [], 0, 0, 0
    seen_exact = set()
    for rec in recs:
        eh = _exact_hash_record(rec)
        nh = _norm_hash_record(rec)
        fam = rec["_split_meta"]["family"]
        if eh in seen_exact or nh in dedup.norm:
            dupes += 1
            continue
        if family_cap and dedup.family_counts.get(fam, 0) >= family_cap:
            capped += 1
            continue
        probe = {k: v for k, v in rec.items() if k != "id"}
        schema_noid = {k: v for k, v in schema.items() if k != "required"}
        schema_noid = dict(schema_noid)
        props = dict(schema.get("properties", {}))
        props.pop("id", None)
        schema_noid["properties"] = props
        errs = validate(probe, schema_noid)
        if errs:
            bad_schema += 1
            continue
        seen_exact.add(eh)
        dedup.norm.add(nh)
        dedup.family_counts[fam] = dedup.family_counts.get(fam, 0) + 1
        kept.append(rec)
    print(f"[{dataset}|{kind}] staged={len(recs)} kept={len(kept)} dupes={dupes} "
          f"capped={capped} schema_rejected={bad_schema}")

    buckets = defaultdict(list)
    # v0.7.0: group-level assignment with guaranteed validation/test coverage
    group_meta = {}
    holdout_records = []
    for rec in kept:
        meta = rec["_split_meta"]
        group = f"{meta['family']}|{meta['variant']}"
        if meta.get("difficulty") == "expert" and (
                dataset in MEDIA_DATASETS or holdout_hash(*group.split("|", 1)) < 25):
            buckets["hard_holdout"].append(rec)
        else:
            group_meta.setdefault(group, split_hash(*group.split("|", 1)))
            holdout_records.append(rec)
    group_assign = coverage_fixup(group_meta)
    for rec in holdout_records:
        meta = rec["_split_meta"]
        buckets[group_assign[f"{meta['family']}|{meta['variant']}"]].append(rec)

    prefix = {"AI-ku_superprogrammer_write": "write",
              "AI-ku_superprogrammer_understand": "understand",
              "AI-ku_superprogrammer_media": "media",
              "AI-ku_superprogrammer_game_engineering": "game",
              "AI-ku_superprogrammer_reverse_engineering": "re",
              "AI-ku_superprogrammer_agent_ops": "ops"}[dataset]
    counter = 0
    splits_info = {}
    base = os.path.join(ROOT, "datasets", DATASET_DIRS[dataset])
    if dataset in ("AI-ku_superprogrammer_media",
                   "AI-ku_superprogrammer_game_engineering",
                   "AI-ku_superprogrammer_reverse_engineering",
                   "AI-ku_superprogrammer_agent_ops"):
        base = os.path.join(base, kind)
    for split in ("train", "validation", "test", "hard_holdout"):
        rows = buckets.get(split, [])
        rows.sort(key=lambda r: (r["language"], r["_split_meta"]["family"],
                                 r["provenance"]["seed"]))
        for rec in rows:
            counter += 1
            rec["id"] = f"{prefix}-{counter:07d}"
        out_dir = (os.path.join(ROOT, "datasets", "hard_holdout")
                   if split == "hard_holdout" else os.path.join(base, split))
        # hard_holdout is SHARED across kinds of the same dataset: qualify the
        # shard name with the kind so one group never deletes another's shards
        shard_prefix = f"{prefix}-{kind}" if split == "hard_holdout" else prefix
        os.makedirs(out_dir, exist_ok=True)
        for old in os.listdir(out_dir):
            if old.startswith(shard_prefix) or (
                    split == "hard_holdout" and old.startswith(f"{prefix}-shard")):
                os.remove(os.path.join(out_dir, old))
        for i in range(0, len(rows), SHARD_SIZE):
            shard = rows[i:i + SHARD_SIZE]
            n = i // SHARD_SIZE
            path = os.path.join(out_dir, f"{shard_prefix}-shard-{n:05d}.jsonl.gz")
            with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f:
                for rec in shard:
                    rec.pop("_split_meta", None)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        splits_info[split] = len(rows)
    return {"dataset": dataset, "kind": kind, "staged": len(recs),
            "kept": len(kept), "dupes_removed": dupes, "family_capped": capped,
            "schema_rejected": bad_schema, "splits": splits_info}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--family-cap", type=int, default=2600)
    args = ap.parse_args()
    all_records = []
    staging = os.path.join(ROOT, "datasets", "_staging")
    if os.path.isdir(staging):
        for name in sorted(os.listdir(staging)):
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(staging, name), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            all_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
    print(f"staged records total: {len(all_records)}")
    by_group = defaultdict(list)
    for rec in all_records:
        kind = rec.get("kind") or ("understand" if "input" in rec else "write")
        rec["kind"] = kind
        by_group[(rec.get("dataset"), kind)].append(rec)
    schemas = {}
    for name in ("write", "understand"):
        with open(os.path.join(ROOT, "schemas", f"{name}.schema.json")) as f:
            schemas[name] = json.load(f)
    summary = {}
    for (dataset, kind), recs in sorted(by_group.items()):
        summary[f"{dataset}|{kind}"] = finalize_group(
            dataset, kind, recs, args.family_cap, schemas[kind])
    out = os.path.join(ROOT, "reports", "finalize_summary.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=1)
    total_kept = sum(v["kept"] for v in summary.values())
    print(f"TOTAL KEPT: {total_kept}")

if __name__ == "__main__":
    main()
