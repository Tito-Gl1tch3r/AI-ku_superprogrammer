#!/usr/bin/env python3
"""Delta build for the Superprogrammer extension (v0.5.0).

Builds ONLY the new families with explicit per-family quotas and appends
verified records to datasets/_staging as write_batch004.jsonl and
understand_batch004.jsonl, reusing the exact worker pipeline from
build_dataset.py (verify + quality gate + record format).

Families (write): py_number_bases, py_mastery_refactor, py_fault_resilience,
py_property_testing, py_numeric_robustness, py_timezones_unicode,
py_git_forensics.
Understand: iterative_repair, mastery_principles, evidence_self_audit.

Usage:
    python3 scripts/build_superprogrammer_delta.py [--workers 4]
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

BATCH = 4             # write_batch004 / understand_batch004
SEED_BASE = 20260601  # distinct from batches 1-5

WRITE_QUOTA = {
    "py_number_bases": 110,
    "py_mastery_refactor": 100,
    "py_fault_resilience": 90,
    "py_property_testing": 90,
    "py_numeric_robustness": 90,
    "py_timezones_unicode": 90,
    "py_git_forensics": 70,
}
UNDERSTAND_QUOTA = {
    "iterative_repair": 60,
    "mastery_principles": 60,
    "evidence_self_audit": 60,
}
MAX_ATTEMPT_FACTOR = 8  # honest Nones / dedup-heavy kinds need headroom


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
                futures.append((key, ex.submit(worker, jobs_builder(key, SEED_BASE + attempts))))
                if len(futures) >= max_inflight:
                    key, fut = futures.pop(0)
                    try:
                        status, rec, _src = fut.result(timeout=300)
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
                    status, rec, _src = fut.result(timeout=300)
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

    out_w = os.path.join(staging, f"write_batch{BATCH:03d}.jsonl")
    quar_w = os.path.join(quarantine, f"write_batch{BATCH:03d}.jsonl")
    produced_w, attempts_w = _run_stage(
        "write_superprogrammer", WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 20, "AI-ku_superprogrammer_write"),
        out_w, quar_w, args.workers)

    out_u = os.path.join(staging, f"understand_batch{BATCH:03d}.jsonl")
    quar_u = os.path.join(quarantine, f"understand_batch{BATCH:03d}.jsonl")
    produced_u, attempts_u = _run_stage(
        "understand_superprogrammer", UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "understand"),
        out_u, quar_u, args.workers)

    print("staging ready for finalize.py "
          f"(write {sum(produced_w.values())}, "
          f"understand {sum(produced_u.values())})")


if __name__ == "__main__":
    main()
