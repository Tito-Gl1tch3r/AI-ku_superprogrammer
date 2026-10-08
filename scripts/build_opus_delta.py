#!/usr/bin/env python3
"""Delta build for the v0.4.0 opus-mind extension.

Builds ONLY the new families with explicit per-family quotas and appends
verified records to datasets/_staging:
  - media_batch005.jsonl          (media write:  post_chain / line_batch / shot_reads)
  - game_batch004.jsonl           (game write:   crossover_bridge / state_scan)
  - media_understand_batch005.jsonl (mv_frameidx_pitfall / mv_palette_propagation)
  - game_understand_batch003.jsonl  (crossover_event_debug)
reusing the exact worker pipeline from build_dataset.py (verify + quality
gate + record format).

Usage:
    python3 scripts/build_opus_delta.py [--workers 4]
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

BATCH_MEDIA_WRITE = 5
BATCH_GAME_WRITE = 4
BATCH_MEDIA_UNDERSTAND = 5
BATCH_GAME_UNDERSTAND = 3
SEED_BASE = 20260301   # distinct from batches 1-5 (20260101) and modding (20260201)

MEDIA_WRITE_QUOTA = {
    "media_mv_post_chain": 70,
    "media_mv_line_batch": 70,
    "media_mv_shot_reads": 60,
}
GAME_WRITE_QUOTA = {
    "game_crossover_bridge": 80,
    "game_state_scan": 70,
}
MEDIA_UNDERSTAND_QUOTA = {
    "mv_frameidx_pitfall": 55,
    "mv_palette_propagation": 55,
}
GAME_UNDERSTAND_QUOTA = {
    "crossover_event_debug": 60,
}
MAX_ATTEMPT_FACTOR = 8  # None-drops (scan uniqueness) burn attempts; headroom


def _run_stage(stage_label, quota, worker, jobs_builder, out_path, quar_path,
               workers):
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
                futures.append((key, ex.submit(worker,
                                               jobs_builder(key,
                                                            SEED_BASE +
                                                            attempts))))
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
                        if key in remaining:
                            remaining[key] -= 1
                            if remaining[key] <= 0:
                                remaining.pop(key)
                    else:
                        quar_f.write(json.dumps(
                            {"status": status, "detail": rec,
                             "stage": stage_label},
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
                        {"status": status, "detail": rec,
                         "stage": stage_label},
                        ensure_ascii=False) + "\n")
    finally:
        out_f.close()
        quar_f.close()
    print(f"[{stage_label}] attempts={attempts} produced={produced} "
          f"total={total_produced}")
    return produced, attempts


def _bump_state(state_name, produced, attempts, batch_no, lang_key=None):
    path = os.path.join(ROOT, "reports", state_name)
    with open(path) as f:
        state = json.load(f)
    if lang_key is not None:
        state["done"][lang_key] = state["done"].get(lang_key, 0) + \
            sum(produced.values())
    else:
        for key, n in produced.items():
            state["done"][key] = state["done"].get(key, 0) + n
    state["attempts"] += attempts
    state["produced"] += sum(produced.values())
    state["last_batch"] = batch_no
    with open(path, "w") as f:
        json.dump(state, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)

    out_w = os.path.join(staging, f"media_batch{BATCH_MEDIA_WRITE:03d}.jsonl")
    quar_w = os.path.join(quarantine,
                          f"media_batch{BATCH_MEDIA_WRITE:03d}.jsonl")
    produced_mw, attempts_mw = _run_stage(
        "media_write_opus", MEDIA_WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 12, "AI-ku_superprogrammer_media"),
        out_w, quar_w, args.workers)

    out_g = os.path.join(staging, f"game_batch{BATCH_GAME_WRITE:03d}.jsonl")
    quar_g = os.path.join(quarantine,
                          f"game_batch{BATCH_GAME_WRITE:03d}.jsonl")
    produced_gw, attempts_gw = _run_stage(
        "game_write_opus", GAME_WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 12,
                           "AI-ku_superprogrammer_game_engineering"),
        out_g, quar_g, args.workers)

    out_mu = os.path.join(
        staging, f"media_understand_batch{BATCH_MEDIA_UNDERSTAND:03d}.jsonl")
    quar_mu = os.path.join(
        quarantine, f"media_understand_batch{BATCH_MEDIA_UNDERSTAND:03d}.jsonl")
    produced_mu, attempts_mu = _run_stage(
        "media_understand_opus", MEDIA_UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "media"),
        out_mu, quar_mu, args.workers)

    out_gu = os.path.join(
        staging, f"game_understand_batch{BATCH_GAME_UNDERSTAND:03d}.jsonl")
    quar_gu = os.path.join(
        quarantine, f"game_understand_batch{BATCH_GAME_UNDERSTAND:03d}.jsonl")
    produced_gu, attempts_gu = _run_stage(
        "game_understand_opus", GAME_UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "game"),
        out_gu, quar_gu, args.workers)

    _bump_state("_state_media.json", produced_mw, attempts_mw,
                BATCH_MEDIA_WRITE, lang_key="python")
    _bump_state("_state_game.json", produced_gw, attempts_gw,
                BATCH_GAME_WRITE, lang_key="python")
    _bump_state("_state_media_understand.json", produced_mu, attempts_mu,
                BATCH_MEDIA_UNDERSTAND)
    _bump_state("_state_game_understand.json", produced_gu, attempts_gu,
                BATCH_GAME_UNDERSTAND)

    total = sum(produced_mw.values()) + sum(produced_gw.values()) + \
        sum(produced_mu.values()) + sum(produced_gu.values())
    print(f"state files updated; staging ready for finalize.py "
          f"(staged total={total})")


if __name__ == "__main__":
    main()
