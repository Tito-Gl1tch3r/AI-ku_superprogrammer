#!/usr/bin/env python3
"""D-5 closure: freeze the honest per-batch generation-attempt history.

The v0.7.0 audit flagged that the global "~N generated" figure stopped being
aggregated (hueco D-5). This script recomputes it from the primary sources
(datasets/_staging/*.jsonl + datasets/_quarantine/*.jsonl line counts, the
only places the pipeline ever wrote attempts) and freezes the result into
reports/attempts_history.json. Re-runnable: the numbers are re-derived, the
file is a snapshot of the pipeline's actual attempt ledger.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(ROOT, "datasets", "_staging")
QUARANTINE = os.path.join(ROOT, "datasets", "_quarantine")


def _count(path):
    n = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n += 1
    except OSError:
        pass
    return n


def main():
    batches = defaultdict(lambda: {"staged_kept": 0, "quarantined": 0,
                                   "datasets": set()})
    for directory, key in ((STAGING, "staged_kept"),
                           (QUARANTINE, "quarantined")):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".jsonl"):
                continue
            n = _count(os.path.join(directory, name))
            batch = name.rsplit(".", 1)[0]          # e.g. write_batch001
            batches[batch][key] += n
            batches[batch]["datasets"].add(
                "write" if name.startswith("write_") else
                name.split("_batch")[0])
    rows = []
    total_attempts = 0
    total_kept = 0
    for batch in sorted(batches):
        info = batches[batch]
        kept = info["staged_kept"]
        quar = info["quarantined"]
        attempts = kept + quar
        total_attempts += attempts
        total_kept += kept
        rows.append({"batch": batch,
                     "datasets": sorted(info["datasets"]),
                     "attempts": attempts,
                     "kept_staged": kept,
                     "quarantined_or_duplicates_dropped": quar,
                     "note": "staged = kept by the gates; quarantine = "
                             "failed verification/quality/duplicates at "
                             "build time"})
    out = {
        "purpose": "D-5 closure (v0.9.0): the generation-attempt ledger, "
                   "recomputed from the pipeline's own staging and "
                   "quarantine ledgers. Published records are a SUBSET of "
                   "staged (finalize/publish dedup and caps removed more); "
                   "the exact published-vs-staged deltas live in "
                   "reports/finalize_summary.json and the publisher output "
                   "of each release.",
        "computed_with": "scripts/build_attempts_history.py",
        "batches": rows,
        "totals": {"attempts_recorded_in_ledgers": total_attempts,
                   "kept_staged": total_kept},
        "historical_estimates": [
            {"source": "README TL;DR up to v0.8.0",
             "figure": "~45,000 generated cumulative (all releases)",
             "nature": "estimate quoted in the README; the surviving "
                       "ledger files only cover the batches that were not "
                       "cleaned after finalize, so the ledger totals are a "
                       "FLOOR, not the full history"},
            {"source": "CHANGELOG 0.1.0-0.4.1 era (full-rebuild finalize)",
             "figure": "thousands of quarantined attempts per batch, ledgers "
                       "rotated by later rebuilds",
             "nature": "explanation of why the surviving ledger is a floor"},
        ],
        "honesty_note": "attempts that crashed before reaching a ledger "
                        "(worker crashes, quarantine-write failures, ledger "
                        "rotation on full rebuilds) cannot be reconstructed "
                        "and are NOT counted; the ledger figure is a FLOOR, "
                        "never an overestimate. Future batches accumulate "
                        "in the same ledgers, so re-running this script "
                        "grows the picture monotonically from v0.9.0 on.",
    }
    dest = os.path.join(ROOT, "reports", "attempts_history.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"batches: {len(rows)}; attempts(ledger floor)={total_attempts}; "
          f"kept_staged={total_kept}")
    print(f"written: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
