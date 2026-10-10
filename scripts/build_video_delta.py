#!/usr/bin/env python3
"""Delta build for the Video End-to-End extension (v0.8.0, roadmap P3).

Batch 007 (media dataset):
  write: media_ts_theme, media_ts_motion_rules, media_ts_deterministic_render,
         media_ts_beat_grid, media_render_verify, media_ts_mv_project (expert)
  understand: video_review_verdict, video_timeline_readout, video_defect_locate
Batch 008 (reverse_engineering dataset): re_understand EXPERT delta
  (D-4 fix: re_understand gets its own expert records -> hard_holdout)

Usage:
    python3 scripts/build_video_delta.py [--workers 4]
        [--skip-write] [--skip-understand] [--skip-re-experts]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.build_dataset import worker_write, worker_understand  # noqa: E402

SEED_BASE = 20260901       # batch 007 (batch 6 = 20260801, batch 5 = 20260701)
RE_EXPERT_SEED_BASE = 20260911  # batch 008

WRITE_QUOTA = {
    "media_ts_theme": 110,
    "media_ts_motion_rules": 110,
    "media_ts_deterministic_render": 110,
    "media_ts_beat_grid": 100,
    "media_render_verify": 110,
    "media_ts_mv_project": 55,
}
UNDERSTAND_QUOTA = {
    "video_review_verdict": 90,
    "video_timeline_readout": 90,
    "video_defect_locate": 90,
}
RE_EXPERT_QUOTA = {
    "re_disasm_readout": 30,
    "re_evidence_conclusion": 25,
    "re_tool_selection": 25,
}
MAX_ATTEMPT_FACTOR = 10  # the measurement/harvest gates reject honestly


def _run_stage(stage_label, quota, worker, jobs_builder, out_path, quar_path,
               workers, seed_base=SEED_BASE):
    remaining = dict(quota)
    produced = {k: 0 for k in quota}
    attempts = 0
    max_attempts = MAX_ATTEMPT_FACTOR * sum(quota.values())
    out_f = open(out_path, "a", encoding="utf-8")
    quar_f = open(quar_path, "a", encoding="utf-8")
    total_produced = 0
    try:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = []
            max_inflight = workers * 4
            while remaining and attempts < max_attempts:
                key = min(sorted(remaining)) if attempts == 0 else \
                    sorted(remaining)[attempts % len(remaining)]
                attempts += 1
                futures.append((key, ex.submit(worker, jobs_builder(key, seed_base + attempts))))
                if len(futures) >= max_inflight:
                    key, fut = futures.pop(0)
                    try:
                        status, rec, _src = fut.result(timeout=600)
                    except Exception:
                        status, rec = "worker_error", None
                    if status == "ok":
                        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        produced[key] += 1
                        total_produced += 1
                        if key in remaining:
                            remaining[key] -= 1
                            if remaining[key] <= 0:
                                remaining.pop(key)
                    else:
                        quar_f.write(json.dumps(
                            {"status": status, "detail": rec, "stage": stage_label},
                            ensure_ascii=False) + "\n")
            for key, fut in futures:
                try:
                    status, rec, _src = fut.result(timeout=600)
                except Exception:
                    status, rec = "worker_error", None
                if status == "ok":
                    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    produced[key] += 1
                    total_produced += 1
                else:
                    quar_f.write(json.dumps(
                        {"status": status, "detail": rec, "stage": stage_label},
                        ensure_ascii=False) + "\n")
    finally:
        out_f.close()
        quar_f.close()
    print(f"[{stage_label}] attempts={attempts} produced={produced} "
          f"total={total_produced}")
    return produced, attempts


def _worker_re_expert(job):
    """Understand worker for the RE expert builders (expert=True path)."""
    import random as _random
    task_type, seed = job
    from generators.understand import re_builders
    from scripts.records import understand_record
    from validators.quality_filters import quality_check
    fn = {"re_disasm_readout": re_builders.build_re_disasm_readout,
          "re_evidence_conclusion": re_builders.build_re_evidence_conclusion,
          "re_tool_selection": re_builders.build_re_tool_selection}[task_type]
    rng = _random.Random(seed)
    cand = fn(rng, expert=True)
    if cand is None:
        return ("gen_none", None, task_type)
    body = cand.code or (cand.answer or "")
    probe = type("P", (), {"code_text": lambda s: body, "language": cand.language,
                           "domain": cand.domain, "difficulty": cand.difficulty,
                           "task": cand.question, "verify_method": cand.verify_method,
                           "is_project": False, "files": None})()
    qok, qreason = quality_check(probe)
    if not qok and "too short" not in qreason:
        return ("quality_failed", {"task_type": task_type, "reason": qreason}, None)
    rec = understand_record(cand)
    return ("ok", rec, task_type)


def _staged_counts(path):
    """Records already staged per family (resumable builds)."""
    counts = {}
    if not os.path.isfile(path):
        return counts
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            fam = (rec.get("_split_meta") or {}).get("family") or \
                (rec.get("provenance") or {}).get("generator")
            if fam:
                counts[fam] = counts.get(fam, 0) + 1
    return counts


def _remaining(quota, path):
    done = _staged_counts(path)
    out = {}
    for k, v in quota.items():
        left = v - done.get(k, 0)
        if left > 0:
            out[k] = left
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-write", action="store_true")
    ap.add_argument("--skip-understand", action="store_true")
    ap.add_argument("--skip-re-experts", action="store_true")
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="per-chunk seed offset so resumed chunks never "
                         "repeat the same seeds")
    args = ap.parse_args()
    off = args.seed_offset

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)

    if not args.skip_write:
        out_w = os.path.join(staging, "write_batch007.jsonl")
        rem = _remaining(WRITE_QUOTA, out_w)
        print(f"[write] already staged: {_staged_counts(out_w) or '{}'}; "
              f"remaining: {rem}", flush=True)
        if rem:
            _run_stage(
                "write_video_ts", rem, worker_write,
                lambda key, seed: (key, seed, 25, "AI-ku_superprogrammer_media"),
                out_w, os.path.join(quarantine, "write_batch007.jsonl"),
                args.workers, seed_base=SEED_BASE + off)
        else:
            print("[write] quota already met")

    if not args.skip_understand:
        out_u = os.path.join(staging, "understand_batch007.jsonl")
        rem = _remaining(UNDERSTAND_QUOTA, out_u)
        print(f"[understand] already staged: {_staged_counts(out_u) or '{}'}; "
              f"remaining: {rem}", flush=True)
        if rem:
            _run_stage(
                "understand_video", rem, worker_understand,
                lambda key, seed: (key, seed, "media"),
                out_u, os.path.join(quarantine, "understand_batch007.jsonl"),
                args.workers, seed_base=SEED_BASE + off)
        else:
            print("[understand] quota already met")

    if not args.skip_re_experts:
        out_r = os.path.join(staging, "understand_batch008.jsonl")
        rem = _remaining(RE_EXPERT_QUOTA, out_r)
        print(f"[re_expert] already staged: {_staged_counts(out_r) or '{}'}; "
              f"remaining: {rem}", flush=True)
        if rem:
            _run_stage(
                "understand_re_expert", rem, _worker_re_expert,
                lambda key, seed: (key, seed),
                out_r, os.path.join(quarantine, "understand_batch008.jsonl"),
                args.workers, seed_base=RE_EXPERT_SEED_BASE + off)
        else:
            print("[re_expert] quota already met")

    print("staging ready for the v0.8.0 delta publisher")


if __name__ == "__main__":
    main()
