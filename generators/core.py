"""Core data model for the AI-ku_superprogrammer generation pipeline.

Every generated example flows through the pipeline:

    GENERATE -> EXECUTE/COMPILE -> CHECK -> FILTER -> KEEP

A `Candidate` is produced by a `Family` (a parameterised problem generator).
It is then verified by the executor for its language. Only verified
candidates become dataset records; failures go to quarantine.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Callable, Optional

# Canonical difficulty ladder.
DIFFICULTIES = ("beginner", "intermediate", "advanced", "expert")

# Domains (closed vocabulary used across both datasets).
DOMAINS = (
    "algorithms", "data_structures", "systems", "web", "databases",
    "automation", "science_math", "engineering", "security", "networking",
    "concurrency", "text_processing",
)

# Verification methods (honest metadata: what was REALLY done).
VERIFY_EXECUTE = "executed"            # ran code + tests, observed results
VERIFY_COMPILE_RUN = "compiled_and_executed"  # compiled binary then ran tests
VERIFY_STATIC = "static_check"         # structural validation only (no toolchain)
VERIFY_AUTHORING = "authored_verified"  # ground truth authored alongside code,
                                        # cross-checked by execution where stated


@dataclass
class FileSpec:
    """A single file of a multi-file project example."""
    path: str
    content: str


@dataclass
class Candidate:
    """A generated Dataset-1 (write) example pending verification."""
    family: str
    language: str
    domain: str
    difficulty: str
    task: str                       # English spec shown to the model
    expected_behavior: str          # English description of correct behaviour
    code: Optional[str] = None      # single-file code (mutually exclusive-ish with files)
    files: Optional[list] = None    # list[FileSpec] for multi-file projects
    entry: Optional[str] = None     # entry file for verification when files is used
    tests: Optional[str] = None     # language-specific test snippet (harness conventions)
    verify_method: str = VERIFY_EXECUTE
    notes: dict = field(default_factory=dict)   # family ground-truth for Dataset 2
    tags: list = field(default_factory=list)
    variant: str = "default"        # split-grouping key component
    seed: int = 0
    is_project: bool = False        # multi-file project flag

    def all_files(self) -> list:
        """Return FileSpec list regardless of single/multi file form."""
        if self.files:
            return list(self.files)
        entry_name = {"python": "solution.py", "javascript": "solution.js",
                      "typescript": "solution.ts", "c": "solution.c",
                      "cpp": "solution.cpp", "java": "Main.java",
                      "rust": "main.rs", "go": "main.go", "php": "solution.php",
                      "bash": "script.sh", "powershell": "script.ps1"}.get(self.language, "solution.txt")
        return [FileSpec(entry_name, self.code or "")]

    def code_text(self) -> str:
        if self.code:
            return self.code
        return "\n\n".join(f.content for f in (self.files or []))


@dataclass
class UnderstandCandidate:
    """A generated Dataset-2 (understand) example pending verification."""
    family: str
    language: str
    task_type: str                  # debugging|trace|explanation|code_review|optimization|
                                    # complexity|refactoring|translation|comparison|
                                    # failure_prediction|testing|security|architecture|
                                    # language_selection
    domain: str
    difficulty: str
    question: str                   # English instruction
    answer: str                     # structured, RESUMED reasoning (English)
    context: str = ""               # optional textual context
    code: Optional[str] = None      # code shown to the model (single file)
    files: Optional[list] = None    # multi-file input
    artifacts: dict = field(default_factory=dict)  # REAL observed outputs/errors
    target_code: Optional[str] = None   # corrected/optimized/translated code
    target_files: Optional[list] = None
    target_tests: Optional[str] = None
    key_points: list = field(default_factory=list)
    big_o: Optional[dict] = None    # {"time": "...", "space": "..."}
    verify_method: str = VERIFY_AUTHORING
    verify_notes: dict = field(default_factory=dict)  # real verification evidence
    tags: list = field(default_factory=list)
    variant: str = "default"
    seed: int = 0
    is_project: bool = False
    dataset_hint: str = ""  # empty -> derive from family registry

    def all_files(self) -> list:
        if self.files:
            return list(self.files)
        if self.code:
            return [FileSpec("input.txt", self.code)]
        return []

    def code_text(self) -> str:
        if self.code:
            return self.code
        return "\n\n".join(f.content for f in (self.files or []))


class Family:
    """Base class for parameterised problem families.

    Subclasses MUST:
      * be deterministic given the rng passed to generate();
      * only use real, existing stdlib APIs (no invented APIs);
      * author ground truth (notes) alongside the code;
      * produce English dataset-facing text.
    """
    NAME: str = "family_base"
    LANGUAGE: str = "python"
    DOMAIN: str = "algorithms"
    DIFFICULTIES: tuple = DIFFICULTIES
    # Understand task types this family can feed (used by Dataset 2 builder).
    SUPPORTS: tuple = ("explanation",)
    PROJECT_FAMILY: bool = False

    def generate(self, rng) -> Optional[Candidate]:
        raise NotImplementedError

    # Optional hooks used by Dataset 2 builders when SUPPORTS declares them.
    def make_buggy(self, rng):
        """Yield (Candidate-buggy, bug_meta) or None. bug_meta:
        {"kind","cwe","description","evidence_hint"}"""
        return None

    def review_variant(self, rng):
        """Return (Candidate-working-but-flawed, issues list) or None."""
        return None

    def perf_pair(self, rng):
        """Return (naive Candidate, optimized Candidate, meta) or None."""
        return None

    def trace_case(self, rng):
        """Return dict(input, steps=[...], output) or None (verified externally)."""
        return None


def register(module_globals, cls):
    """Helper: instantiate a family class and expose it for registry scans."""
    instance = cls()
    module_globals.setdefault("__families__", []).append(instance)
    return cls
