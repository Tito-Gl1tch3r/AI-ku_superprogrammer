"""Record builders: Candidate/UnderstandCandidate -> final JSON dicts."""
from __future__ import annotations

import datetime
import os

PIPELINE_VERSION = "0.1.0"
GENERATOR_VERSION = "0.1.0"

DATASET_NAMES = ("AI-ku_superprogrammer_write", "AI-ku_superprogrammer_understand",
                 "AI-ku_superprogrammer_media", "AI-ku_superprogrammer_game_engineering")
ID_PREFIX = {"AI-ku_superprogrammer_write": "write",
             "AI-ku_superprogrammer_understand": "understand",
             "AI-ku_superprogrammer_media": "media",
             "AI-ku_superprogrammer_game_engineering": "game"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _provenance(cand):
    return {
        "source": "synthetic",
        "generator": cand.family,
        "generator_version": GENERATOR_VERSION,
        "seed": cand.seed,
        "created_utc": _now(),
        "pipeline_version": PIPELINE_VERSION,
        "method": "template_synthesis + execution verification",
    }


def _metrics(cand):
    body = cand.code_text()
    lines = body.count("\n") + 1
    return {"code_chars": len(body), "code_lines": lines,
            "is_project": bool(cand.is_project),
            "n_files": len(cand.files) if cand.files else 1}


def write_record(cand, verification, dataset="AI-ku_superprogrammer_write"):
    return {
        "id": None,  # assigned at finalize
        "dataset": dataset,
        "kind": "write",
        "language": cand.language,
        "domain": cand.domain,
        "task": cand.task,
        "code": cand.code,
        "files": ([{"path": f.path, "content": f.content} for f in cand.files]
                  if cand.files else None),
        "entry": cand.entry,
        "tests": cand.tests,
        "expected_behavior": cand.expected_behavior,
        "difficulty": cand.difficulty,
        "tags": cand.tags,
        "verification": verification,
        "provenance": _provenance(cand),
        "license": "MIT",
        "metrics": _metrics(cand),
        "_split_meta": {"family": cand.family, "variant": cand.variant,
                        "difficulty": cand.difficulty},
    }


def understand_record(cand: dict):
    """cand is an UnderstandCandidate."""
    from generators.registry import dataset_for_family
    ds = cand.dataset_hint or dataset_for_family(cand.family)
    if ds == "AI-ku_superprogrammer_write":
        ds = "AI-ku_superprogrammer_understand"
    return {
        "id": None,
        "dataset": ds,
        "kind": "understand",
        "language": cand.language,
        "task_type": cand.task_type,
        "domain": cand.domain,
        "difficulty": cand.difficulty,
        "input": {
            "context": cand.context,
            "code": cand.code,
            "files": ([{"path": f.path, "content": f.content} for f in cand.files]
                      if cand.files else None),
            "question": cand.question,
            "artifacts": cand.artifacts,
        },
        "target": {
            "answer": cand.answer,
            "code": cand.target_code,
            "tests": cand.target_tests,
            "key_points": cand.key_points,
            "big_o": cand.big_o,
        },
        "verification": {
            "method": cand.verify_method,
            **cand.verify_notes,
        },
        "provenance": {
            "source": "synthetic",
            "generator": cand.family,
            "generator_version": GENERATOR_VERSION,
            "seed": cand.seed,
            "created_utc": _now(),
            "pipeline_version": PIPELINE_VERSION,
            "method": "authored ground truth + execution evidence",
        },
        "license": "MIT",
        "metrics": {**_metrics(cand), "task_type": cand.task_type},
        "_split_meta": {"family": cand.family, "variant": cand.variant,
                        "difficulty": cand.difficulty, "task_type": cand.task_type},
    }
