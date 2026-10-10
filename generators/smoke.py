"""Smoke tool: generate + verify N samples per family (or per language).

Usage:
    python3 -m generators.smoke --languages python,sql --samples 3
    python3 -m generators.smoke --families py_bank_algorithms --samples 5
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict

from .registry import all_families
from validators.verify import verify_candidate


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default="")
    ap.add_argument("--families", default="")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    langs = set(filter(None, args.languages.split(",")))
    fams = set(filter(None, args.families.split(",")))
    stats = defaultdict(lambda: {"ok": 0, "fail": 0})
    failures = []
    for fam in all_families():
        if langs and fam.LANGUAGE not in langs:
            continue
        if fams and fam.NAME not in fams:
            continue
        for i in range(args.samples):
            # Families with honest generation gates (audio measurement
            # guarantees, harvest rejections) drop seeds; give each sample a
            # small deterministic retry budget before failing it.
            cand = None
            crash = None
            for attempt in range(6):
                rng = random.Random(args.seed * 1000 + i + attempt * 7919)
                try:
                    cand = fam.generate(rng)
                except Exception as e:
                    crash = repr(e)
                    continue
                if cand is not None:
                    break
            if crash is not None and cand is None:
                stats[fam.NAME]["fail"] += 1
                failures.append((fam.NAME, i, f"generate crashed: {crash}"))
                continue
            if cand is None:
                stats[fam.NAME]["fail"] += 1
                failures.append((fam.NAME, i, "generate returned None"))
                continue
            ok, r, ver = verify_candidate(cand)
            if ok:
                stats[fam.NAME]["ok"] += 1
            else:
                stats[fam.NAME]["fail"] += 1
                failures.append((fam.NAME, i,
                                 f"[{r.stage}] {(r.stderr or r.compile_stderr)[:2000]}"))
    print(f"{'FAMILY':38s} OK  FAIL")
    for name in sorted(stats):
        s = stats[name]
        print(f"{name:38s} {s['ok']:3d} {s['fail']:4d}")
    if failures:
        print("\nFAILURES:")
        for name, i, msg in failures[:20]:
            print(f"  {name}#{i}: {msg}")
        sys.exit(1)
    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
