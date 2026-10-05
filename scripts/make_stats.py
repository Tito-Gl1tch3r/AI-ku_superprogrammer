#!/usr/bin/env python3
"""Aggregate final statistics into reports/stats.json + markdown tables."""
from __future__ import annotations

import gzip
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIZE_BUCKETS = ((0, 300, "<300c"), (300, 1200, "300-1200c"), (1200, 3000, "1200-3000c"),
                (3000, 10 ** 9, ">3000c"))


DATASET_LAYOUT = {
    "write": ["datasets/write"],
    "understand": ["datasets/understand"],
    "media_write": ["datasets/media/write"],
    "media_understand": ["datasets/media/understand"],
    "game_write": ["datasets/game_engineering/write"],
    "game_understand": ["datasets/game_engineering/understand"],
}
HOLDOUT_PREFIX = {"write": "write", "understand": "understand", "media_write": "media",
                  "media_understand": "media", "game_write": "game",
                  "game_understand": "game"}


def load_stage(stage):
    rows = []
    for rel in DATASET_LAYOUT[stage]:
        base = os.path.join(ROOT, rel)
        for split in ("train", "validation", "test"):
            d = os.path.join(base, split)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if name.endswith(".jsonl.gz"):
                    with gzip.open(os.path.join(d, name), "rt", encoding="utf-8") as f:
                        for line in f:
                            rows.append((split, json.loads(line)))
    hd = os.path.join(ROOT, "datasets", "hard_holdout")
    prefix = HOLDOUT_PREFIX[stage]
    if os.path.isdir(hd):
        for name in sorted(os.listdir(hd)):
            if name.endswith(".jsonl.gz") and name.startswith(prefix):
                with gzip.open(os.path.join(hd, name), "rt", encoding="utf-8") as f:
                    for line in f:
                        rows.append(("hard_holdout", json.loads(line)))
    return rows


def bucket(chars):
    for lo, hi, label in SIZE_BUCKETS:
        if lo <= chars < hi:
            return label
    return ">3000c"


def pct(x, total):
    return round(100.0 * x / total, 1) if total else 0.0


def main():
    stats = {}
    for stage in ("write", "understand", "media_write", "media_understand",
                  "game_write", "game_understand"):
        rows = load_stage(stage)
        per = {
            "total": len(rows),
            "by_language": Counter(),
            "by_difficulty": Counter(),
            "by_domain": Counter(),
            "by_split": Counter(),
            "by_task_type": Counter(),
            "by_size": Counter(),
            "verified_executed": 0,
            "verified_static": 0,
            "with_tests": 0,
            "multi_file": 0,
            "synthetic": 0,
        }
        for split, rec in rows:
            per["by_split"][split] += 1
            per["by_language"][rec["language"]] += 1
            per["by_difficulty"][rec["difficulty"]] += 1
            per["by_domain"][rec["domain"]] += 1
            if stage == "understand":
                per["by_task_type"][rec["task_type"]] += 1
            m = rec.get("metrics", {})
            per["by_size"][bucket(m.get("code_chars", 0))] += 1
            if m.get("is_project"):
                per["multi_file"] += 1
            has_tests = bool(rec.get("tests") or
                             (rec.get("target") or {}).get("tests"))
            if has_tests:
                per["with_tests"] += 1
            ver = rec.get("verification", {})
            method = ver.get("method", "")
            if method in ("executed", "compiled_and_executed"):
                per["verified_executed"] += 1
            elif method == "static_check":
                per["verified_static"] += 1
            if rec.get("provenance", {}).get("source") == "synthetic":
                per["synthetic"] += 1
        per["pct_verified_executed"] = pct(per["verified_executed"], per["total"])
        per["pct_verified_static"] = pct(per["verified_static"], per["total"])
        per["pct_with_tests"] = pct(per["with_tests"], per["total"])
        per["pct_multi_file"] = pct(per["multi_file"], per["total"])
        per["pct_synthetic"] = pct(per["synthetic"], per["total"])
        stats[stage] = {
            "total": per["total"],
            "pct_verified_executed": per["pct_verified_executed"],
            "pct_verified_static": per["pct_verified_static"],
            "pct_with_tests": per["pct_with_tests"],
            "pct_multi_file": per["pct_multi_file"],
            "pct_synthetic": per["pct_synthetic"],
            "by_language": dict(per["by_language"].most_common()),
            "by_difficulty": dict(per["by_difficulty"].most_common()),
            "by_domain": dict(per["by_domain"].most_common()),
            "by_split": dict(per["by_split"]),
            "by_size": dict(per["by_size"]),
            "by_task_type": dict(per["by_task_type"].most_common()),
        }
    out = os.path.join(ROOT, "reports", "stats.json")
    with open(out, "w") as f:
        json.dump(stats, f, indent=1)

    md = ["# Dataset statistics (auto-generated)\n"]
    for stage, s in stats.items():
        md.append(f"## {stage}\n")
        md.append(f"- total: **{s['total']}**")
        md.append(f"- verified by execution: **{s['pct_verified_executed']}%** "
                  f"(static check: {s['pct_verified_static']}%)")
        md.append(f"- with tests: {s['pct_with_tests']}% | multi-file projects: "
                  f"{s['pct_multi_file']}% | synthetic: {s['pct_synthetic']}%\n")
        md.append("| language | count |")
        md.append("|---|---|")
        for k, v in s["by_language"].items():
            md.append(f"| {k} | {v} |")
        md.append("")
        md.append("| difficulty | count |")
        md.append("|---|---|")
        for k, v in s["by_difficulty"].items():
            md.append(f"| {k} | {v} |")
        if s["by_task_type"]:
            md.append("")
            md.append("| task type | count |")
            md.append("|---|---|")
            for k, v in s["by_task_type"].items():
                md.append(f"| {k} | {v} |")
        md.append("")
        md.append("| split | count |")
        md.append("|---|---|")
        for k, v in s["by_split"].items():
            md.append(f"| {k} | {v} |")
        md.append("")
        md.append("| code size | count |")
        md.append("|---|---|")
        for k, v in s["by_size"].items():
            md.append(f"| {k} | {v} |")
        md.append("")
    with open(os.path.join(ROOT, "reports", "stats.md"), "w") as f:
        f.write("\n".join(md))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in
                          ("total", "pct_verified_executed", "pct_with_tests",
                           "pct_multi_file")} for k, v in stats.items()}, indent=1))


if __name__ == "__main__":
    main()
