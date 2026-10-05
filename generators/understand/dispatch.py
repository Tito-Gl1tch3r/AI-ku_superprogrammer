"""Dataset-2 dispatcher: maps (task_type, language) to builder functions."""
from __future__ import annotations

import random

from .builder import (build_debugging, build_trace, build_explanation,
                      build_code_review, build_failure_prediction, build_testing,
                      build_security)
from .builders_extra import (build_optimization, build_complexity, build_refactoring,
                             build_translation, build_comparison, build_architecture,
                             build_language_selection)
from .media_game import (build_media_determinism_debug, build_media_pipeline_reasoning,
                         build_game_format_hypothesis, build_game_interop_reasoning,
                         build_engine_layer_reasoning)

BUILDERS = {
    "debugging": build_debugging,
    "trace": build_trace,
    "explanation": build_explanation,
    "code_review": build_code_review,
    "failure_prediction": build_failure_prediction,
    "testing": build_testing,
    "security": build_security,
    "optimization": build_optimization,
    "complexity": build_complexity,
    "refactoring": build_refactoring,
    "translation": build_translation,
    "comparison": build_comparison,
    "architecture": build_architecture,
    "language_selection": build_language_selection,
    "media_determinism_debug": build_media_determinism_debug,
    "media_pipeline_reasoning": build_media_pipeline_reasoning,
    "game_format_hypothesis": build_game_format_hypothesis,
    "game_interop_reasoning": build_game_interop_reasoning,
    "engine_layer_reasoning": build_engine_layer_reasoning,
}


def build_understand_task(task_type: str, rng: random.Random, language=None,
                          dataset=None):
    """Return UnderstandCandidate | None (None = attempt dropped honestly)."""
    builder = BUILDERS.get(task_type)
    if builder is None:
        return None
    try:
        if task_type in ("debugging", "explanation", "code_review"):
            return builder(rng, language, dataset=dataset)
        return builder(rng)
    except Exception:
        return None
