#!/usr/bin/env python3
"""Delta build for the universal-modder extension (game modding methodology).

Builds ONLY the new modding families with explicit per-family quotas and
appends verified records to datasets/_staging as batch 005 (game write)
and batch 002 (game understand), reusing the exact worker pipeline from
build_dataset.py (verify + quality gate + record format).

Families (write): game_engine_recon, game_save_backup, game_publish_lint,
game_oracle_replay. Understand: mod_route_selection, mod_oracle_gotcha,
mod_evidence_levels.

Usage:
    python3 scripts/build_modding_delta.py [--workers 4]
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

BATCH_WRITE = 3        # game_batch003
BATCH_UNDERSTAND = 2   # game_understand_batch002
SEED_BASE = 20260201   # distinct from batches 1-4

WRITE_QUOTA = {
    "game_engine_recon": 100,
    "game_save_backup": 80,
    "game_publish_lint": 80,
    "game_oracle_replay": 80,
}
UNDERSTAND_QUOTA = {
    "mod_route_selection": 90,
    "mod_oracle_gotcha": 90,
    "mod_evidence_levels": 80,
}
MAX_ATTEMPT_FACTOR = 6  # bugs/retries burn attempts; allow more headroom


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)

    out_w = os.path.join(staging, f"game_batch{BATCH_WRITE:03d}.jsonl")
    quar_w = os.path.join(quarantine, f"game_batch{BATCH_WRITE:03d}.jsonl")
    produced_w, attempts_w = _run_stage(
        "game_write_modding", WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 12,
                           "AI-ku_superprogrammer_game_engineering"),
        out_w, quar_w, args.workers)

    out_u = os.path.join(staging,
                         f"game_understand_batch{BATCH_UNDERSTAND:03d}.jsonl")
    quar_u = os.path.join(quarantine,
                          f"game_understand_batch{BATCH_UNDERSTAND:03d}.jsonl")
    produced_u, attempts_u = _run_stage(
        "game_understand_modding", UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "game"),
        out_u, quar_u, args.workers)

    # keep pilot state consistent so future pilot builds do not refill these
    state_path = os.path.join(ROOT, "reports", "_state_game.json")
    with open(state_path) as f:
        state = json.load(f)
    state["done"]["python"] = state["done"].get("python", 0) + \
        sum(produced_w.values())
    state["attempts"] += attempts_w
    state["produced"] += sum(produced_w.values())
    state["last_batch"] = BATCH_WRITE
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1)

    state_path = os.path.join(ROOT, "reports", "_state_game_understand.json")
    with open(state_path) as f:
        state = json.load(f)
    for key, n in produced_u.items():
        state["done"][key] = state["done"].get(key, 0) + n
    state["attempts"] += attempts_u
    state["produced"] += sum(produced_u.values())
    state["last_batch"] = BATCH_UNDERSTAND
    with open(state_path, "w") as f:
        json.dump(state, f, indent=1)

    print("state files updated; staging ready for finalize.py")


if __name__ == "__main__":
    main()
