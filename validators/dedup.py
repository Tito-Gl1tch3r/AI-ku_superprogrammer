"""Deduplication: exact and normalised hashes.

Normalisation removes comments, collapses whitespace and maps user
identifiers to positional tokens. This catches the "same problem, renamed
variables" cosmetics the project explicitly bans.
"""
from __future__ import annotations

import hashlib
import re

KEYWORDS = {
    "python": {"def", "class", "return", "if", "elif", "else", "for", "while", "in", "not",
               "and", "or", "import", "from", "as", "with", "try", "except", "finally",
               "raise", "lambda", "None", "True", "False", "self", "yield", "assert",
               "pass", "break", "continue", "global", "nonlocal", "async", "await"},
    "javascript": {"function", "return", "if", "else", "for", "while", "const", "let",
                   "var", "new", "class", "extends", "this", "null", "undefined", "true",
                   "false", "typeof", "instanceof", "try", "catch", "finally", "throw",
                   "async", "await", "of", "in", "do", "switch", "case", "break",
                   "continue", "export", "import", "from", "require", "module", "default"},
    "typescript": None,  # falls back to javascript set + type keywords
    "c": {"int", "char", "float", "double", "void", "long", "short", "unsigned", "signed",
          "struct", "union", "enum", "typedef", "static", "const", "return", "if", "else",
          "for", "while", "do", "switch", "case", "break", "continue", "sizeof", "malloc",
          "free", "NULL", "include", "define"},
    "cpp": None,
    "sql": {"select", "from", "where", "group", "by", "order", "having", "join", "left",
            "right", "inner", "outer", "on", "as", "and", "or", "not", "null", "insert",
            "into", "values", "update", "set", "delete", "create", "table", "primary",
            "key", "foreign", "references", "with", "union", "all", "distinct", "limit",
            "case", "when", "then", "else", "end", "over", "partition", "row_number"},
    "bash": {"if", "then", "fi", "else", "elif", "for", "do", "done", "while", "case",
             "esac", "function", "local", "return", "echo", "exit"},
    "java": None, "go": None, "rust": None, "php": None, "powershell": None,
    "html": set(), "css": set(),
}
KEYWORDS["typescript"] = KEYWORDS["javascript"] | {"type", "interface", "implements", "readonly", "keyof"}
KEYWORDS["cpp"] = KEYWORDS["c"] | {"std", "template", "typename", "class", "public", "private",
                                   "namespace", "using", "auto", "nullptr", "new", "delete",
                                   "vector", "string", "cout", "cin", "include"}
KEYWORDS["java"] = {"public", "private", "protected", "class", "static", "void", "new", "return",
                    "if", "else", "for", "while", "int", "long", "double", "boolean", "String",
                    "var", "final", "import", "package", "extends", "implements", "interface", "null"}
KEYWORDS["go"] = {"func", "package", "import", "var", "const", "type", "struct", "interface",
                  "return", "if", "else", "for", "range", "go", "chan", "select", "defer",
                  "map", "make", "new", "nil", "string", "int", "error"}
KEYWORDS["rust"] = {"fn", "let", "mut", "pub", "struct", "enum", "impl", "trait", "match",
                    "if", "else", "for", "while", "loop", "return", "use", "mod", "self",
                    "Some", "None", "Ok", "Err", "Vec", "String", "i32", "u32", "usize", "f64"}
KEYWORDS["php"] = {"function", "return", "if", "else", "elseif", "foreach", "as", "while",
                   "class", "public", "private", "new", "use", "namespace", "echo", "array",
                   "null", "true", "false", "try", "catch", "throw", "static"}
KEYWORDS["powershell"] = {"function", "param", "return", "if", "else", "elseif", "foreach",
                          "in", "while", "try", "catch", "finally", "throw", "begin", "process", "end"}

_COMMENT = {
    "python": [r"#[^\n]*"],
    "javascript": [r"//[^\n]*", r"/\*.*?\*/"],
    "typescript": [r"//[^\n]*", r"/\*.*?\*/"],
    "c": [r"//[^\n]*", r"/\*.*?\*/"],
    "cpp": [r"//[^\n]*", r"/\*.*?\*/"],
    "java": [r"//[^\n]*", r"/\*.*?\*/"],
    "go": [r"//[^\n]*", r"/\*.*?\*/"],
    "rust": [r"//[^\n]*", r"/\*.*?\*/"],
    "php": [r"//[^\n]*", r"#[^\n]*", r"/\*.*?\*/"],
    "sql": [r"--[^\n]*", r"/\*.*?\*/"],
    "bash": [r"#[^\n]*"],
    "powershell": [r"#[^\n]*", r"<#[^\n]*#>"],
    "html": [r"<!--.*?-->"],
    "css": [r"/\*.*?\*/"],
}


def exact_hash(cand) -> str:
    body = cand.code_text()
    return hashlib.sha256(body.encode()).hexdigest()


def normalize(text: str, language: str) -> str:
    text = re.sub(r"\s+", " ", text)
    for pat in _COMMENT.get(language, []):
        text = re.sub(pat, " ", text, flags=re.S)
    text = re.sub(r"\s+", " ", text).strip()
    kws = KEYWORDS.get(language, set())
    counter = {"n": 0}
    mapping = {}

    def sub_id(m):
        tok = m.group(0)
        if tok in kws:
            return tok
        if tok not in mapping:
            counter["n"] += 1
            mapping[tok] = f"V{counter['n']}"
        return mapping[tok]

    return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", sub_id, text)


def normalized_hash(cand) -> str:
    body = cand.code_text()
    return hashlib.sha256(normalize(body, cand.language).encode()).hexdigest()


class DedupIndex:
    """Exact + normalised index with optional per-family caps."""

    def __init__(self, family_cap: int | None = None):
        self.exact = set()
        self.norm = set()
        self.family_cap = family_cap
        self.family_counts: dict = {}

    def check_and_add(self, cand) -> bool:
        """True if accepted (novel), False if duplicate or family-capped."""
        eh = exact_hash(cand)
        nh = normalized_hash(cand)
        if eh in self.exact or nh in self.norm:
            return False
        if self.family_cap is not None:
            c = self.family_counts.get(cand.family, 0)
            if c >= self.family_cap:
                return False
            self.family_counts[cand.family] = c + 1
        self.exact.add(eh)
        self.norm.add(nh)
        return True
