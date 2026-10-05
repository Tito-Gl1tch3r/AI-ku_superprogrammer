#!/usr/bin/env python3
"""Main build orchestrator for both datasets.

GENERATE -> EXECUTE/COMPILE -> CHECK -> FILTER -> KEEP (staging) | QUARANTINE

Usage:
  python3 scripts/build_dataset.py --config configs/pilot.json --stage write \
      --time-budget 420 --batch 1
  python3 scripts/build_dataset.py --config configs/pilot.json --stage understand \
      --time-budget 420 --batch 1

Staging shards land in datasets/_staging/; quarantine in datasets/_quarantine/.
Finalize (dedup + splits + shards) is a separate script: scripts/finalize.py.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def worker_write(job):
    """Generate + verify one write candidate. Runs in a worker process."""
    import random as _random
    family_name, seed, verify_timeout, dataset = job
    from generators.registry import family_by_name
    from validators.verify import verify_candidate
    from validators.quality_filters import quality_check
    from scripts.records import write_record
    fam = family_by_name(family_name)
    if fam is None:
        return None
    rng = _random.Random(seed)
    try:
        cand = fam.generate(rng)
    except Exception:
        return ("crash", None, family_name)
    if cand is None:
        return ("gen_none", None, family_name)
    ok, r, ver = verify_candidate(cand, timeout=verify_timeout)
    if not ok:
        return ("verify_failed",
                {"family": family_name, "language": cand.language,
                 "stage": r.stage, "error": (r.stderr or r.compile_stderr)[:300],
                 "seed": seed}, None)
    qok, qreason = quality_check(cand)
    if not qok:
        return ("quality_failed", {"family": family_name, "reason": qreason,
                                   "seed": seed}, None)
    rec = write_record(cand, ver, dataset=dataset)
    return ("ok", rec, family_name)


def worker_understand(job):
    import random as _random
    task_type, seed, dataset = job
    from generators.understand.dispatch import build_understand_task
    from scripts.records import understand_record
    from validators.quality_filters import quality_check
    rng = _random.Random(seed)
    cand = build_understand_task(task_type, rng, dataset=dataset)
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


def weighted_choice(rng, weights):
    total = sum(weights.values())
    x = rng.random() * total
    acc = 0.0
    for k, w in weights.items():
        acc += w
        if x < acc:
            return k
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stage", choices=["write", "understand", "media", "game",
                                        "media_understand", "game_understand"],
                    required=True)
    ap.add_argument("--time-budget", type=int, default=420)
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)
    stage = args.stage
    staging_dir = os.path.join(ROOT, "datasets", "_staging")
    quarantine_dir = os.path.join(ROOT, "datasets", "_quarantine")
    os.makedirs(staging_dir, exist_ok=True)
    os.makedirs(quarantine_dir, exist_ok=True)
    state_path = os.path.join(ROOT, "reports", f"_state_{stage}.json")
    state = {"done": {}, "attempts": 0, "produced": 0}
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    out_path = os.path.join(staging_dir, f"{stage}_batch{args.batch:03d}.jsonl")
    quar_path = os.path.join(quarantine_dir, f"{stage}_batch{args.batch:03d}.jsonl")

    if stage in ("write", "media", "game"):
        target_key = {"write": "write_targets", "media": "media_targets",
                      "game": "game_targets"}[stage]
        dataset = {"write": "AI-ku_superprogrammer_write",
                   "media": "AI-ku_superprogrammer_media",
                   "game": "AI-ku_superprogrammer_game_engineering"}[stage]
        weights = dict(cfg[target_key])
        from generators.registry import all_families, dataset_for_family
        lang_fams = {}
        for fam in all_families():
            if dataset_for_family(fam.NAME) != dataset:
                continue
            lang_fams.setdefault(fam.LANGUAGE, []).append(fam.NAME)
        weights = {k: v - state["done"].get(k, 0) for k, v in weights.items()}
        weights = {k: v for k, v in weights.items() if v > 0}
        family_cap = cfg.get("family_cap", 5000)
    else:
        target_key = {"understand": "understand_targets",
                      "media_understand": "media_understand_targets",
                      "game_understand": "game_understand_targets"}[stage]
        dataset = {"understand": None, "media_understand": "media",
                   "game_understand": "game"}[stage]
        weights = dict(cfg[target_key])
        weights = {k: v - state["done"].get(k, 0) for k, v in weights.items()}
        weights = {k: v for k, v in weights.items() if v > 0}
        family_cap = None

    if not weights:
        print("targets already satisfied")
        return

    t0 = time.monotonic()
    produced = 0
    attempts = 0
    seed_base = cfg.get("seed_base", 1000) + args.batch * 1_000_000
    out_f = open(out_path, "a", encoding="utf-8")
    quar_f = open(quar_path, "a", encoding="utf-8")
    per_key = {k: 0 for k in weights}

    try:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = []
            max_inflight = args.workers * 4
            while time.monotonic() - t0 < args.time_budget and weights:
                key = weighted_choice(random.Random(seed_base + attempts), weights)
                if per_key.get(key, 0) >= weights[key]:
                    remaining = {k: v - per_key.get(k, 0) for k, v in weights.items()
                                 if v - per_key.get(k, 0) > 0}
                    if not remaining:
                        break
                    key = next(iter(remaining))
                per_key[key] = per_key.get(key, 0) + 1
                attempts += 1
                if stage in ("write", "media", "game"):
                    fams = lang_fams.get(key, [])
                    fam_name = fams[attempts % len(fams)] if fams else None
                    if fam_name is None:
                        continue
                    job = (fam_name, seed_base + attempts, cfg.get("verify_timeout", 12),
                           dataset)
                    futures.append((key, ex.submit(worker_write, job)))
                else:
                    job = (key, seed_base + attempts, dataset)
                    futures.append((key, ex.submit(worker_understand, job)))

                if len(futures) >= max_inflight:
                    key, fut = futures.pop(0)
                    try:
                        status, rec, _src = fut.result(timeout=120)
                    except Exception as e:
                        if attempts <= 3:
                            import traceback
                            print("POOL DEBUG:", type(e).__name__, repr(e)[:300], flush=True)
                        status, rec = "worker_error", None
                    if status == "ok":
                        out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        produced += 1
                        state["done"][key] = state["done"].get(key, 0) + 1
                    else:
                        quar_f.write(json.dumps({"status": status, "detail": rec},
                                                ensure_ascii=False) + "\n")

            for key, fut in futures:
                try:
                    status, rec, _src = fut.result(timeout=90)
                except Exception:
                    status, rec = "worker_error", None
                if status == "ok":
                    out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    produced += 1
                    state["done"][key] = state["done"].get(key, 0) + 1
                else:
                    quar_f.write(json.dumps({"status": status, "detail": rec},
                                            ensure_ascii=False) + "\n")
    finally:
        out_f.close()
        quar_f.close()
        state["attempts"] += attempts
        state["produced"] += produced
        state["last_batch"] = args.batch
        with open(state_path, "w") as f:
            json.dump(state, f, indent=1)

    elapsed = time.monotonic() - t0
    print(f"stage={stage} batch={args.batch} attempts={attempts} produced={produced} "
          f"elapsed={elapsed:.0f}s rate={produced / max(1, elapsed):.1f}/s")
    print(f"progress: {json.dumps(state['done'], sort_keys=True)}")


if __name__ == "__main__":
    main()
