"""Contamination-safe splits.

Examples are grouped by (family, variant) — the conceptual template.
Groups are assigned atomically to train/validation/test, so no near-duplicate
template can straddle splits. Expert groups can additionally be routed to the
hard_holdout evaluation set, which is excluded from training splits entirely.
"""
from __future__ import annotations

import hashlib


def _h(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest()[:12], 16)


def assign_split(family: str, variant: str, hard_holdout: bool = False,
                 train=0.80, validation=0.10) -> str:
    if hard_holdout:
        # 25% of hard_holdout-flagged groups -> holdout; the rest flow normally.
        return "hard_holdout" if _h(f"hold|{family}|{variant}") % 100 < 25 else _normal(family, variant, train, validation)
    return _normal(family, variant, train, validation)


def _normal(family, variant, train, validation) -> str:
    x = _h(f"split|{family}|{variant}") % 10000
    if x < train * 10000:
        return "train"
    if x < (train + validation) * 10000:
        return "validation"
    return "test"
