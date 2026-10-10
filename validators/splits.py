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


def split_hash(family: str, variant: str) -> int:
    """The v0.6.0 split-bucket hash for a group (0..9999)."""
    return _h(f"split|{family}|{variant}") % 10000


def holdout_hash(family: str, variant: str) -> int:
    """The v0.6.0 hard-holdout gate hash for a group (0..99)."""
    return _h(f"hold|{family}|{variant}") % 100


def coverage_fixup(group_x: dict) -> dict:
    """Assign non-holdout groups to train/validation/test.

    Start from the hash buckets, then guarantee at least one validation
    group and one test group by promoting the highest-hash train groups
    (the ones closest to the original boundaries). Deterministic; ties
    broken by group name. Used by finalize.py (v0.7.0+) and by the
    resplit_v070 repair script.
    """
    assign = {}
    for g, x in group_x.items():
        if x < 8000:
            assign[g] = "train"
        elif x < 9000:
            assign[g] = "validation"
        else:
            assign[g] = "test"
    by_x = sorted(group_x.items(), key=lambda kv: (-kv[1], kv[0]))
    train_pool = [g for g, _ in by_x if assign[g] == "train"]
    if not any(v == "validation" for v in assign.values()):
        if train_pool:
            assign[train_pool.pop(0)] = "validation"
    if not any(v == "test" for v in assign.values()):
        if train_pool:
            assign[train_pool.pop(0)] = "test"
        else:  # extreme edge: demote the lowest-hash validation group
            g = min((gg for gg, s in assign.items() if s == "validation"),
                    key=lambda gg: (group_x[gg], gg))
            assign[g] = "test"
    return assign
