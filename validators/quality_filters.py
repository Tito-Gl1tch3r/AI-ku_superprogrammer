"""Quality gates applied before an example is kept.

These filters encode the project's anti-garbage rules: no trivial echoes,
no placeholder text, no meaningless one-liners, coherent metadata.
"""
from __future__ import annotations

MIN_CODE_CHARS = {"python": 70, "cpp": 90, "c": 90, "javascript": 70,
                  "typescript": 80, "sql": 90, "bash": 70, "html": 180,
                  "css": 120, "powershell": 110, "go": 90, "rust": 90,
                  "java": 90, "php": 90}
MAX_CODE_CHARS = 9000
MIN_TASK_CHARS = 60
BANNED = ("TODO", "FIXME", "XXX", "lorem", "lorem ipsum", "# placeholder",
          "// placeholder", "not implemented", "as an ai", "for brevity")
DOMAINS = {"algorithms", "data_structures", "systems", "web", "databases",
           "automation", "science_math", "engineering", "security", "networking",
           "concurrency", "text_processing"}
DIFFS = {"beginner", "intermediate", "advanced", "expert"}


def quality_check(cand) -> tuple:
    """Return (ok, reason)."""
    body = cand.code_text()
    if len(body) < MIN_CODE_CHARS.get(cand.language, 90):
        return False, "code too short / trivial"
    if len(body) > MAX_CODE_CHARS:
        return False, "code too long"
    if len(cand.task or "") < MIN_TASK_CHARS:
        return False, "task description too short"
    low = body.lower()
    for b in BANNED:
        if b in low:
            return False, f"banned token: {b}"
    if cand.domain not in DOMAINS:
        return False, f"bad domain: {cand.domain}"
    if cand.difficulty not in DIFFS:
        return False, f"bad difficulty: {cand.difficulty}"
    if cand.language == "html" and "<html" not in low and "<!doctype" not in low and "<div" not in low and "<form" not in low and "<table" not in low:
        return False, "html fragment without meaningful structure"
    if cand.verify_method not in ("executed", "compiled_and_executed", "static_check", "authored_verified", "build_executed"):
        return False, f"bad verify_method: {cand.verify_method}"
    return True, ""
