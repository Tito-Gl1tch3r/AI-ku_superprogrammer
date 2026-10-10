#!/usr/bin/env python3
"""Delta build for the Reverse Engineering extension (v0.6.0, module 04).

Builds ONLY the new families with explicit per-family quotas and appends
verified records to datasets/_staging as write_batch005.jsonl and
understand_batch005.jsonl, reusing the exact worker pipeline from
build_dataset.py (verify + quality gate + record format).

Families (write): re_elf_parser, re_disasm_analysis, re_blackbox_reimpl,
re_version_diff, re_strings_decode. Every candidate compiles real ELF
binaries with gcc and harvests ground truth with real binutils.
Understand: re_disasm_readout, re_evidence_conclusion, re_tool_selection.

Usage:
    python3 scripts/build_re_delta.py [--workers 4]
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

BATCH = 5             # write_batch005 / understand_batch005
SEED_BASE = 20260701  # distinct from batches 1-5 (batch 4 = 20260601)

WRITE_QUOTA = {
    "re_elf_parser": 190,
    "re_disasm_analysis": 160,
    "re_blackbox_reimpl": 140,
    "re_version_diff": 120,
    "re_strings_decode": 120,
}
UNDERSTAND_QUOTA = {
    "re_disasm_readout": 160,
    "re_evidence_conclusion": 140,
    "re_tool_selection": 140,
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
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    staging = os.path.join(ROOT, "datasets", "_staging")
    quarantine = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging, exist_ok=True)
    os.makedirs(quarantine, exist_ok=True)

    out_w = os.path.join(staging, f"write_batch{BATCH:03d}.jsonl")
    quar_w = os.path.join(quarantine, f"write_batch{BATCH:03d}.jsonl")
    produced_w, attempts_w = _run_stage(
        "write_reverse_engineering", WRITE_QUOTA, worker_write,
        lambda key, seed: (key, seed, 25, "AI-ku_superprogrammer_reverse_engineering"),
        out_w, quar_w, args.workers)

    out_u = os.path.join(staging, f"understand_batch{BATCH:03d}.jsonl")
    quar_u = os.path.join(quarantine, f"understand_batch{BATCH:03d}.jsonl")
    produced_u, attempts_u = _run_stage(
        "understand_reverse_engineering", UNDERSTAND_QUOTA, worker_understand,
        lambda key, seed: (key, seed, "understand"),
        out_u, quar_u, args.workers)

    print("staging ready for finalize.py "
          f"(write {sum(produced_w.values())}, "
          f"understand {sum(produced_u.values())})")


if __name__ == "__main__":
    main()
