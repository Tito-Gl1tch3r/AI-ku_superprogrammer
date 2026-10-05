"""Static verification for languages without a local toolchain, and for
HTML/CSS artifacts that cannot be rendered headlessly here.

Static checks are REAL but WEAK: they validate structure, balance, forbidden
patterns and required attributes. Records verified this way carry
verification.method = "static_check" and are never claimed as executed.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from .base import ExecResult

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"closing </{tag}> with empty stack")
        elif self.stack[-1] != tag:
            self.errors.append(f"mismatched </{tag}>, expected </{self.stack[-1]}>")
            if tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.stack.pop()
                if self.stack:
                    self.stack.pop()
        else:
            self.stack.pop()


def check_html(text: str) -> list:
    errs = []
    p = _Balance()
    try:
        p.feed(text)
        p.close()
    except Exception as e:
        errs.append(f"parse error: {e}")
        return errs
    errs += p.errors[:10]
    if p.stack:
        errs.append(f"unclosed tags: {p.stack[:8]}")
    # Security / quality gates.
    for m in re.finditer(r"<script[^>]*\ssrc\s*=\s*[\"']https?://", text, re.I):
        errs.append("external script src (must be local or omitted)")
    for m in re.finditer(r"\son[a-z]+\s*=\s*[\"']?\w", text, re.I):
        errs.append("inline event handler (use addEventListener instead)")
    for m in re.finditer(r"<img(?![^>]*\balt=)[^>]*>", text, re.I):
        errs.append("<img> missing alt attribute")
    for m in re.finditer(r"<a\s(?![^>]*\bhref=)[^>]*>", text, re.I):
        errs.append("<a> missing href attribute")
    if re.search(r"<form(?![^>]*\b(action|id)=)[^>]*>", text, re.I) and "<form" in text.lower():
        errs.append("<form> without action or id (untestable)")
    for inp in re.finditer(r"<input[^>]*>", text, re.I):
        tag = inp.group(0)
        t = re.search(r"type\s*=\s*[\"']?(\w+)", tag, re.I)
        if t and t.group(1).lower() in ("checkbox", "radio") and "id=" not in tag:
            errs.append("checkbox/radio input missing id (label association)")
    return errs


_CSS_PROP = re.compile(r"^\s*[-a-zA-Z]+\s*:\s*[^;{}]+;\s*$")


def check_css(text: str) -> list:
    errs = []
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                errs.append("unbalanced '}'")
                depth = 0
    if depth != 0:
        errs.append("unbalanced braces")
    if text.count("{") != text.count("}"):
        errs.append("brace count mismatch")
    for block in re.findall(r"\{([^{}]*)\}", text):
        for line in block.split(";")[:-1] if block.strip().endswith(";") else block.split(";"):
            if line.strip() and not _CSS_PROP.match(line + ";" if not line.rstrip().endswith(";") else line):
                if ":" not in line:
                    errs.append(f"declaration missing colon: {line.strip()[:60]!r}")
    if len(re.findall(r"!important", text)) > 3:
        errs.append("excessive !important usage")
    return errs


def check_powershell(text: str) -> list:
    errs = []
    for op, cl in (("{", "}"), ("(", ")"), ("[", "]")):
        if text.count(op) != text.count(cl):
            errs.append(f"unbalanced {op}{cl} ({text.count(op)} vs {text.count(cl)})")
    if re.search(r"Invoke-Expression\s", text):
        errs.append("Invoke-Expression usage (code injection risk)")
    if re.search(r"\$env:\w+\s*=\s*[\"'][^\"']*(secret|password|token)", text, re.I):
        errs.append("hard-coded secret in environment assignment")
    if re.search(r"ConvertTo-SecureString\s+-AsPlainText", text) and "secret" not in text.lower():
        errs.append("plaintext SecureString outside secret-handling context")
    return errs


def check_generic_code(text: str, language: str) -> list:
    """Conservative structural checks for go/rust/java/php without toolchains."""
    errs = []
    for op, cl in (("{", "}"), ("(", ")")):
        if text.count(op) != text.count(cl):
            errs.append(f"unbalanced {op}{cl}")
    if len(text) < 120:
        errs.append("too short to be meaningful")
    for bad in ("TODO", "FIXME", "placeholder", "lorem"):
        if bad in text:
            errs.append(f"forbidden token: {bad}")
    lang_rules = {
        "go": [(r"^package\s+\w+", "missing package clause"),
               (r"func\s+\w+\s*\(", "no function definitions")],
        "rust": [(r"\bfn\s+\w+", "no fn definitions"),
                 (r"(let\s+mut\s+\w+|&\s*\w+|->\s*\w+)", "missing core rust syntax")],
        "java": [(r"class\s+\w+", "missing class"),
                 (r"(public|private|protected)", "no access modifiers")],
        "php": [(r"<\?php", "missing <?php tag"),
                (r"\$\w+", "no php variables")],
    }
    for pattern, msg in lang_rules.get(language, []):
        if not re.search(pattern, text, re.M):
            errs.append(msg)
    return errs


def check_glsl(text: str) -> list:
    errs = []
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    if depth != 0:
        errs.append("unbalanced braces")
    if not text.lstrip().startswith("#version 300 es"):
        errs.append("missing #version 300 es header")
    if "void main()" not in text:
        errs.append("missing main()")
    if "fragColor" not in text:
        errs.append("missing fragColor output")
    if "texture(" not in text and "vertex" not in text:
        errs.append("no texture sampling found")
    return errs


def verify_static(cand) -> ExecResult:
    res = ExecResult(stage="static")
    res.toolchain = "static structural validator"
    text = cand.code_text()
    lang = cand.language
    if lang == "html":
        errs = check_html(text)
    elif lang == "css":
        errs = check_css(text)
    elif lang == "powershell":
        errs = check_powershell(text)
    elif lang == "glsl":
        errs = check_glsl(text)
    else:
        errs = check_generic_code(text, lang)
    if errs:
        res.stderr = " | ".join(errs[:10])
        res.exit_code = 1
    else:
        res.ok = True
        res.exit_code = 0
        res.stdout = "__STATIC_OK__"
    return res
