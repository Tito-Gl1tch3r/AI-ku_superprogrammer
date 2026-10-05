"""Multilanguage problem bank.

Each problem defines:
  * params(rng)  -> instance parameters (deterministic per rng);
  * spec(P, rng) -> English task statement;
  * io(P)        -> [(stdin, expected_stdout)] shared across languages — the
                    cross-language equivalence protocol (CLI shim per impl);
  * impls        -> {language: impl_fn(P, rng) -> CodeUnit}.

CodeUnit carries library-style files + harness tests + CLI files + notes
(explanation ground truth, Big-O, idioms) + bug transforms (string-level,
verified by execution: a buggy version is only kept if tests actually fail).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CodeUnit:
    files: dict = field(default_factory=dict)      # name -> content (no main/CLI)
    tests: str = ""                                # harness snippet (language conventions)
    cli: dict = field(default_factory=dict)        # extra CLI files for stdin/stdout runs
    notes: dict = field(default_factory=dict)
    bugs: dict = field(default_factory=dict)       # kind -> fn(files_dict) -> buggy_files_dict
    function_name: str = ""

    def library_files(self) -> dict:
        return dict(self.files)


@dataclass
class Problem:
    pid: str
    domain: str
    params: Callable = None
    spec: Callable = None
    io: Callable = None
    solve: Callable = None           # pure-python reference -> expected stdout
    impls: dict = field(default_factory=dict)

    def impl_languages(self):
        return sorted(self.impls.keys())


REGISTRY: dict = {}


def register_problem(problem: Problem):
    """Register a problem; repeated registrations for the same pid merge impls."""
    existing = REGISTRY.get(problem.pid)
    if existing is None:
        REGISTRY[problem.pid] = problem
        return
    for lang, fn in problem.impls.items():
        existing.impls[lang] = fn
    # First-registered metadata (params/spec/io) wins; impls accumulate.
