#!/usr/bin/env python3
"""Delta build for the MV (generative music-video) extension.

Builds ONLY the new families with explicit per-family quotas and appends the
verified records to datasets/_staging as batch 004 (quarantine siblings too),
reusing the exact same worker pipeline as build_dataset.py (verify + quality
gate + record format). Deterministic seeds: seed_base + batch*1e6 + attempt.

Usage:
    python3 scripts/build_mv_delta.py [--workers 2]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.build_dataset import worker_understand, worker_write  # noqa: E402

BATCH = 4
SEED_BASE = 20260101 + BATCH * 1_000_000

WRITE_QUOTA = {
    "media_mv_scene_engine": 130,
    "media_mv_karaoke": 130,
    "media_mv_project": 70,
}
UNDERSTAND_QUOTA = {
    "media_determinism_debug": 120,
    "media_pipeline_reasoning": 120,
}
MAX_ATTEMPT_FACTOR = 4  # hard stop: attempts <= factor * total quota


def _run_stage(stage_label, quota, worker, jobs_builder, out_path, quar_path, workers):
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
                futures.append((key, ex.submit(worker, jobs_builder(key, SEED_BASE + attempts))))
                if len(futures) >= max_inflight:
                    key, fut = futures.pop(0)
                    try:
                        status, rec, _src = fut.result(timeout=180)
                    except Exception:
                        status, rec = "worker_error", None
                    if status == "ok":
                        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        produced[key] += 1
                        total_produced += 1
                        if key in remaining:  # overshoot (in-flight) is kept, not fatal
                            remaining[key] -= 1
                            if remaining[key] <= 0:
                                remaining.pop(key)
                    else:
                        quar_f.write(json.dumps(
                            {"status": status, "detail": rec, "stage": stage_label},
                            ensure_ascii=False) + "\n")
            for key, fut in futures:
                try:
                    status, rec, _src = fut.result(timeout=180)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)

    out_w = os.path.join(staging, f"media_batch{BATCH:03d}.jsonl")
    quar_w = os.path.join(quarantine, f"media_batch{BATCH:03d}.jsonl")
    produced_w, attempts_w = _run_stage(
        "media_write_mv", WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 12, "AI-ku_superprogrammer_media"),
        out_w, quar_w, args.workers)

    out_u = os.path.join(staging, f"media_understand_batch{BATCH:03d}.jsonl")
    quar_u = os.path.join(quarantine, f"media_understand_batch{BATCH:03d}.jsonl")
    produced_u, attempts_u = _run_stage(
        "media_understand_mv", UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "media"),
        out_u, quar_u, args.workers)

    # keep pilot state consistent so future pilot builds do not refill these
    state_path = os.path.join(ROOT, "reports", "_state_media.json")
    with open(state_path) as f:
        state = json.load(f)
    state["done"]["python"] = state["done"].get("python", 0) + sum(produced_w.values())
    state["attempts"] += attempts_w
    state["produced"] += sum(produced_w.values())
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1)

    state_path = os.path.join(ROOT, "reports", "_state_media_understand.json")
    with open(state_path) as f:
        state = json.load(f)
    for key, n in produced_u.items():
        state["done"][key] = state["done"].get(key, 0) + n
    state["attempts"] += attempts_u
    state["produced"] += sum(produced_u.values())
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1)

    print("state files updated; staging ready for finalize.py")


if __name__ == "__main__":
    main()
