#!/usr/bin/env python3
"""Delta build for the v1.1.0 build-craft families (module 01 write).

Builds ONLY the 4 new module-06 families and appends verified records to
datasets/_staging/write_batch011.jsonl, reusing the exact worker pipeline
from build_dataset.py (verify + quality gate + record format).

Families: c_makefile_repair, c_warning_gate, c_header_guards. Every
candidate is measured at generation (real make/gcc builds); every
make_buggy is self-verifying.

RESUMABLE: each invocation counts what is already staged per family and
only generates the deficit.

Usage:
    python3 scripts/build_v100_delta.py [--workers 4] [--max-attempts N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.build_dataset import worker_write  # noqa: E402

BATCH = 11            # write_batch011
SEED_BASE = 20261101  # distinct from batches 1-10

WRITE_QUOTA = {
    "c_makefile_repair": 150,
    "c_warning_gate": 160,
    "c_header_guards": 200,
}
MAX_ATTEMPT_FACTOR = 8  # honest generation gates need headroom


def _staged_counts(path):
    counts = Counter()
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
            fam = (rec.get("provenance") or {}).get("generator")
            if fam:
                counts[fam] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-attempts", type=int, default=0,
                    help="hard cap on attempts for this invocation "
                         "(0 = until quotas are met)")
    args = ap.parse_args()

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)
    out_path = os.path.join(staging, f"write_batch{BATCH:03d}.jsonl")
    quar_path = os.path.join(quarantine, f"write_batch{BATCH:03d}.jsonl")

    already = _staged_counts(out_path)
    quota = {k: max(0, v - already.get(k, 0))
             for k, v in WRITE_QUOTA.items()}
    quota = {k: v for k, v in quota.items() if v > 0}
    print(f"already staged: {dict(already)}")
    print(f"remaining quota: {quota}")
    if not quota:
        print("all quotas met; nothing to do")
        return

    max_attempts = args.max_attempts or (MAX_ATTEMPT_FACTOR *
                                         sum(WRITE_QUOTA.values()))
    attempts = 0
    produced = Counter()
    quarantined = 0
    out_f = open(out_path, "a", encoding="utf-8")
    quar_f = open(quar_path, "a", encoding="utf-8")
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = []
            max_inflight = args.workers * 4
            keys = sorted(quota)
            while quota and attempts < max_attempts:
                key = keys[attempts % len(keys)] if attempts else keys[0]
                attempts += 1
                seed = SEED_BASE + attempts * 1013
                futures.append((key, ex.submit(
                    worker_write, (key, seed, 25,
                                   "AI-ku_superprogrammer_write"))))
                if len(futures) >= max_inflight:
                    key, fut = futures.pop(0)
                    try:
                        status, rec, _src = fut.result(timeout=180)
                    except Exception:
                        status, rec = "worker_error", None
                    if status == "ok":
                        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        produced[key] += 1
                        if key in quota:
                            quota[key] -= 1
                            if quota[key] <= 0:
                                quota.pop(key, None)
                    else:
                        quar_f.write(json.dumps(
                            {"status": status, "detail": rec,
                             "stage": "v100_write"},
                            ensure_ascii=False) + "\n")
                        quarantined += 1
            for key, fut in futures:
                try:
                    status, rec, _src = fut.result(timeout=180)
                except Exception:
                    status, rec = "worker_error", None
                if status == "ok":
                    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    produced[key] += 1
                    if key in quota:
                        quota[key] -= 1
                        if quota[key] <= 0:
                            quota.pop(key, None)
                else:
                    quar_f.write(json.dumps(
                        {"status": status, "detail": rec,
                         "stage": "v100_write"},
                        ensure_ascii=False) + "\n")
                    quarantined += 1
    finally:
        out_f.close()
        quar_f.close()
    total_now = _staged_counts(out_path)
    print(f"this invocation: attempts={attempts} produced={dict(produced)} "
          f"quarantined={quarantined}")
    print(f"staged totals now: {dict(total_now)}")
    missing = {k: WRITE_QUOTA[k] - total_now.get(k, 0)
               for k in WRITE_QUOTA if total_now.get(k, 0) < WRITE_QUOTA[k]}
    if missing:
        print(f"STILL MISSING (re-run to resume): {missing}")
    else:
        print("ALL QUOTAS MET - staging complete")


if __name__ == "__main__":
    main()
