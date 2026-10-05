"""Dataset-1 write families for Python."""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register
from ..problems import REGISTRY
from ..problems.bank_core import CodeUnit


class PythonBankFamily(Family):
    """spec -> implementation for every bank problem available in Python."""
    NAME = "py_bank_algorithms"
    LANGUAGE = "python"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "trace", "debugging", "testing", "failure_prediction",
                "complexity", "translation", "comparison", "optimization", "code_review")

    def generate(self, rng: random.Random) -> Candidate | None:
        pids = sorted(p for p, prob in REGISTRY.items() if "python" in prob.impls)
        pid = rng.choice(pids)
        prob = REGISTRY[pid]
        P = prob.params(rng)
        unit: CodeUnit = prob.impls["python"](P, rng)
        diff = rng.choice(self.DIFFICULTIES)
        return Candidate(
            family=self.NAME, language="python", domain=prob.domain,
            difficulty=diff,
            task=prob.spec(P, rng),
            expected_behavior=unit.notes.get("purpose", "") + " Behavior is verified by the bundled test suite.",
            code=unit.files["solution.py"], tests=unit.tests,
            verify_method="executed",
            notes={"problem": pid, "params": P, "unit_notes": unit.notes,
                   "big_o": {"time": unit.notes.get("big_o_time"),
                             "space": unit.notes.get("big_o_space")},
                   "explain": unit.notes, "cli": unit.cli, "io": prob.io(P),
                   "function_name": unit.function_name},
            tags=["algorithm", pid], variant=pid, seed=rng.randrange(2**31),
        )

    def make_buggy(self, rng: random.Random):
        pids = sorted(p for p, prob in REGISTRY.items() if "python" in prob.impls)
        pid = rng.choice(pids)
        prob = REGISTRY[pid]
        P = prob.params(rng)
        unit = prob.impls["python"](P, rng)
        if not unit.bugs:
            return None
        kind = rng.choice(sorted(unit.bugs))
        buggy_files = unit.bugs[kind](unit.files)
        buggy_code = buggy_files["solution.py"]
        if buggy_code == unit.files["solution.py"]:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain=prob.domain,
            difficulty="intermediate",
            task=prob.spec(P, rng),
            expected_behavior="See question.", code=buggy_code, tests=unit.tests,
            verify_method="executed",
            notes={"problem": pid, "params": P, "bug_kind": kind,
                   "correct_code": unit.files["solution.py"], "unit_notes": unit.notes},
            tags=["algorithm", pid, "bug"], variant=f"{pid}|bug|{kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": kind, "problem": pid, "unit": unit, "params": P,
                "correct_code": unit.files["solution.py"], "tests": unit.tests}
        return cand, meta


class PythonTextProcessingFamily(Family):
    NAME = "py_text_processing"
    LANGUAGE = "python"
    DOMAIN = "text_processing"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging", "complexity")

    TASKS = ("slugify", "csv_parser", "template_fill", "diff_words", "initials",
             "word_wrap", "title_case", "mask_words")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.TASKS)
        names = rng.sample(["text", "payload", "document", "content", "raw"], 1)
        n = rng.choice([n for n in ("text",)])
        if kind == "slugify":
            words = rng.sample(["Deploy Guide", "API  Rate  Limits", "Hola  Mundo", "My 3rd Post",
                                "User Auth & Sessions", "Caching: Basics"], rng.randint(2, 4))
            sep = rng.choice(["-", "_"])
            text = rng.choice(words)
            fn = rng.choice(["slugify", "to_slug", "make_slug"])
            code = (f"import re\n\n\ndef {fn}({n}: str, sep: str = \"{sep}\") -> str:\n"
                    f"    \"\"\"Lowercase, strip accents-free non-alphanumerics, join with {sep}.\"\"\"\n"
                    f"    cleaned = re.sub(r\"[^a-z0-9]+\", sep, {n}.lower()).strip(sep)\n"
                    f"    return cleaned\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({text!r}) == {fn}_ref({text!r})\n"
                     f"    assert {fn}('') == ''\n"
                     f"    assert {fn}('  A  B  ') == 'a{sep}b'\n"
                     f"    assert {fn}('X--Y!!Z') == 'x{sep}y{sep}z'\n")
            import re as _re
            ref = _re.sub(r"[^a-z0-9]+", sep, text.lower()).strip(sep)
            tests += f"\ndef {fn}_ref(s):\n    import re\n    return re.sub(r\"[^a-z0-9]+\", \"{sep}\", s.lower()).strip(\"{sep}\")\n"
            expected = f"Returns {ref!r} for the sample input."
        elif kind == "csv_parser":
            fn = rng.choice(["parse_csv_line", "split_csv", "csv_fields"])
            fields = [rng.choice(["alpha", "beta, inc", "gamma", '"delta, llc"', "eps"]) for _ in range(rng.randint(3, 5))]
            line = ",".join('"' + f.replace('"', '""') + '"' if ("," in f or '"' in f) else f for f in fields)
            code = (f"def {fn}({n}: str) -> list[str]:\n"
                    f"    \"\"\"Parse one RFC-4180-ish CSV line: quoted fields may contain commas\n"
                    f"    and escaped double quotes.\"\"\"\n"
                    f"    fields, cur, in_quotes = [], [], False\n"
                    f"    i = 0\n"
                    f"    while i < len({n}):\n"
                    f"        ch = {n}[i]\n"
                    f"        if ch == '\"':\n"
                    f"            if in_quotes and i + 1 < len({n}) and {n}[i + 1] == '\"':\n"
                    f"                cur.append('\"')\n"
                    f"                i += 1\n"
                    f"            else:\n"
                    f"                in_quotes = not in_quotes\n"
                    f"        elif ch == ',' and not in_quotes:\n"
                    f"            fields.append(''.join(cur))\n"
                    f"            cur = []\n"
                    f"        else:\n"
                    f"            cur.append(ch)\n"
                    f"        i += 1\n"
                    f"    fields.append(''.join(cur))\n"
                    f"    return fields\n")
            import csv as _csv, io as _io
            expected_fields = next(_csv.reader(_io.StringIO(line)))
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({line!r}) == {expected_fields!r}\n"
                     f"    assert {fn}('') == ['']\n"
                     f"    assert {fn}('a,b,c') == ['a', 'b', 'c']\n"
                     f"    assert {fn}('\"x\"\"y\",z') == ['x\"y', 'z']\n")
            expected = "Quoted commas stay inside a field; doubled quotes decode to a single quote."
        elif kind == "template_fill":
            fn = rng.choice(["render_template", "fill_template"])
            keys = rng.sample(["name", "city", "role", "year", "team"], rng.randint(2, 3))
            template = "Hello " + " and ".join("{" + k + "}" for k in keys[:2]) + "!"
            vals = {k: rng.choice(["Ada", "Lima", "dev", "2049", "core"]) for k in keys[:2]}
            code = (f"import string\n\n\ndef {fn}(template: str, **values) -> str:\n"
                    f"    \"\"\"Replace {{key}} placeholders; missing keys raise KeyError.\"\"\"\n"
                    f"    result = template\n"
                    f"    for key, value in values.items():\n"
                    f"        result = result.replace(\"{{\" + key + \"}}\", str(value))\n"
                    f"    return result\n")
            out = template
            for k, v in vals.items():
                out = out.replace("{" + k + "}", str(v))
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({template!r}, **{vals!r}) == {out!r}\n"
                     f"    assert {fn}('no keys') == 'no keys'\n"
                     f"    assert {fn}('{{a}}{{a}}', a='x') == 'xx'\n")
            expected = f"Renders {out!r}; unknown placeholders stay untouched."
        elif kind == "diff_words":
            fn = rng.choice(["added_words", "new_terms"])
            old = rng.sample(["alpha", "beta", "gamma", "delta", "cache", "index"], 4)
            new = rng.sample(["alpha", "beta", "gamma", "delta", "cache", "index", "queue", "log"], 4)
            code = (f"def {fn}(old: str, new: str) -> list[str]:\n"
                    f"    \"\"\"Words present in `new` but not in `old`, first-seen order.\"\"\"\n"
                    f"    before = set(old.split())\n"
                    f"    seen, result = set(), []\n"
                    f"    for word in new.split():\n"
                    f"        if word not in before and word not in seen:\n"
                    f"            seen.add(word)\n"
                    f"            result.append(word)\n"
                    f"    return result\n")
            exp = []
            seen = set()
            for w in new:
                if w not in set(old) and w not in seen:
                    seen.add(w)
                    exp.append(w)
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({' '.join(old)!r}, {' '.join(new)!r}) == {exp!r}\n"
                     f"    assert {fn}('', '') == []\n"
                     f"    assert {fn}('a', 'a a a') == []\n"
                     f"    assert {fn}('a', 'b b c') == ['b', 'c']\n")
            expected = f"Returns {exp!r} preserving first-seen order."
        elif kind == "initials":
            fn = rng.choice(["initials", "monogram", "name_initials"])
            full = rng.choice(["Ada Lovelace", "Grace Brewster Hopper", "Alan M. Turing",
                               "Linus Torvalds", "Margaret Hamilton"])
            parts = [p for p in full.replace(".", "").split() if p]
            exp = ".".join(p[0].upper() for p in parts) + "."
            code = (f"def {fn}(full_name: str) -> str:\n"
                    f"    \"\"\"Uppercase initials separated by dots, trailing dot included.\"\"\"\n"
                    f"    words = [w for w in full_name.replace('.', ' ').split() if w]\n"
                    f"    return '.'.join(w[0].upper() for w in words) + '.'\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({full!r}) == {exp!r}\n"
                     f"    assert {fn}('a b') == 'A.B.'\n"
                     f"    assert {fn}('  single  ') == 'S.'\n")
            expected = f"Produces {exp!r}."
        elif kind == "word_wrap":
            fn = rng.choice(["wrap_text", "word_wrap"])
            width = rng.randint(10, 24)
            words = rng.sample(["deploy", "rollback", "healthcheck", "replica", "latency",
                                "throughput", "failover", "canary"], rng.randint(4, 7))
            text = " ".join(words)
            exp_lines = []
            cur = ""
            for w in words:
                if not cur:
                    cur = w
                elif len(cur) + 1 + len(w) <= width:
                    cur += " " + w
                else:
                    exp_lines.append(cur)
                    cur = w
            if cur:
                exp_lines.append(cur)
            exp = "\n".join(exp_lines)
            code = (f"def {fn}(text: str, width: int) -> str:\n"
                    f"    \"\"\"Greedy word wrap: never split words, single spaces, max `width` cols.\"\"\"\n"
                    f"    lines, cur = [], \"\"\n"
                    f"    for word in text.split():\n"
                    f"        if not cur:\n"
                    f"            cur = word\n"
                    f"        elif len(cur) + 1 + len(word) <= width:\n"
                    f"            cur += \" \" + word\n"
                    f"        else:\n"
                    f"            lines.append(cur)\n"
                    f"            cur = word\n"
                    f"    if cur:\n"
                    f"        lines.append(cur)\n"
                    f"    return \"\\n\".join(lines)\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({text!r}, {width}) == {exp!r}\n"
                     f"    assert {fn}('', 10) == ''\n"
                     f"    assert {fn}('toolongword', 5) == 'toolongword'\n")
            expected = "Words longer than width stay on their own line."
        elif kind == "title_case":
            fn = rng.choice(["title_case", "capitalize_title"])
            minor = {"a", "an", "the", "and", "or", "but", "of", "in", "on", "to", "for"}
            words = rng.sample(["the", "art", "of", "unix", "programming", "a", "design",
                                "for", "networks"], rng.randint(4, 6))
            title = " ".join(words)
            exp = " ".join(w if (w in minor and i != 0) else w.capitalize()
                           for i, w in enumerate(words))
            code = (f"MINOR_WORDS = {{{', '.join(repr(m) for m in sorted(minor))}}}\n\n\n"
                    f"def {fn}(title: str) -> str:\n"
                    f"    \"\"\"Capitalize every word except minor words (unless first).\"\"\"\n"
                    f"    words = title.split()\n"
                    f"    out = []\n"
                    f"    for i, w in enumerate(words):\n"
                    f"        if i != 0 and w.lower() in MINOR_WORDS:\n"
                    f"            out.append(w.lower())\n"
                    f"        else:\n"
                    f"            out.append(w.capitalize())\n"
                    f"    return ' '.join(out)\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({title!r}) == {exp!r}\n"
                     f"    assert {fn}('the end') == 'The End'\n"
                     f"    assert {fn}('') == ''\n")
            expected = f"Produces {exp!r}."
        else:  # mask_words
            fn = rng.choice(["mask_words", "redact_terms"])
            secret = rng.choice(["hunter2", "s3cr3t", "topsecret", "pa55word"])
            text = f"login with {secret} then rotate {secret} nightly"
            keep = rng.randint(1, 2)
            exp = text.replace(secret, "*" * len(secret))
            code = (f"def {fn}(text: str, secret: str, visible: int = {keep}) -> str:\n"
                    f"    \"\"\"Replace every occurrence of secret with asterisks,\n"
                    f"    leaving at most `visible` leading characters readable.\"\"\"\n"
                    f"    if not secret:\n"
                    f"        return text\n"
                    f"    shown = secret[:visible]\n"
                    f"    masked = shown + '*' * (len(secret) - visible)\n"
                    f"    return text.replace(secret, masked)\n")
            masked = secret[:keep] + "*" * (len(secret) - keep)
            exp = text.replace(secret, masked)
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({text!r}, {secret!r}) == {exp!r}\n"
                     f"    assert {fn}('x', '') == 'x'\n"
                     f"    assert {fn}('abc', 'abc', visible=3) == 'abc'\n")
            expected = f"Sample output: {exp!r}."
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write a Python utility function for log/report preprocessing. {expected} "
                  f"Include type hints and a docstring; handle the empty-input edge case."),
            expected_behavior=expected,
            code=code, tests=tests, verify_method="executed",
            notes={"kind": kind, "explain": {"purpose": expected,
                                             "approach": "Single pass with the appropriate stdlib tool.",
                                             "key_points": ["stdlib-only", "edge case: empty input"],
                                             "big_o_time": "O(n)", "big_o_space": "O(n)"}},
            tags=["text", kind], variant=kind, seed=rng.randrange(2**31))


class PythonDataStatsFamily(Family):
    NAME = "py_data_statistics"
    LANGUAGE = "python"
    DOMAIN = "science_math"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "complexity", "failure_prediction")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["mean_median", "variance", "linear_regression", "percentile",
                           "histogram"])
        n = rng.randint(8, 60)
        data = [round(rng.uniform(-100, 100), 2) for _ in range(n)]
        d_lit = repr(data)
        if kind == "mean_median":
            fn = rng.choice(["summary_stats", "mean_and_median"])
            s = sorted(data)
            mean = sum(s) / len(s)
            med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
            code = (f"def {fn}(values):\n"
                    f"    \"\"\"Return (mean, median) rounded to 4 decimals.\"\"\"\n"
                    f"    if not values:\n"
                    f"        raise ValueError('empty data')\n"
                    f"    ordered = sorted(values)\n"
                    f"    count = len(ordered)\n"
                    f"    mean = sum(ordered) / count\n"
                    f"    mid = count // 2\n"
                    f"    median = ordered[mid] if count % 2 else (ordered[mid - 1] + ordered[mid]) / 2\n"
                    f"    return round(mean, 4), round(median, 4)\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({d_lit}) == {round(mean, 4), round(med, 4)!r}\n"
                     f"    assert {fn}([5]) == (5.0, 5.0)\n"
                     f"    assert {fn}([1, 2]) == (1.5, 1.5)\n"
                     f"    try:\n"
                     f"        {fn}([])\n"
                     f"        assert False\n"
                     f"    except ValueError:\n"
                     f"        pass\n")
            expected = f"Mean {round(mean, 4)}, median {round(med, 4)} (both rounded to 4 decimals)."
        elif kind == "variance":
            fn = rng.choice(["population_variance", "variance_pop"])
            mean = sum(data) / len(data)
            var = sum((x - mean) ** 2 for x in data) / len(data)
            code = (f"def {fn}(values):\n"
                    f"    \"\"\"Population variance: mean of squared deviations.\"\"\"\n"
                    f"    if len(values) < 2:\n"
                    f"        raise ValueError('need at least two values')\n"
                    f"    mu = sum(values) / len(values)\n"
                    f"    return round(sum((x - mu) ** 2 for x in values) / len(values), 4)\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({d_lit}) == {round(var, 4)}\n"
                     f"    assert {fn}([3, 3, 3]) == 0.0\n"
                     f"    assert {fn}([0, 10]) == 25.0\n")
            expected = f"Population variance = {round(var, 4)}."
        elif kind == "linear_regression":
            fn = rng.choice(["simple_linear_fit", "ols_fit"])
            slope = round(rng.uniform(-3, 3), 3)
            inter = round(rng.uniform(-50, 50), 3)
            xs = [i + rng.uniform(-0.4, 0.4) for i in range(5, 5 + n)]
            ys = [round(slope * x + inter + rng.uniform(-3, 3), 3) for x in xs]
            mx, my = sum(xs) / n, sum(ys) / n
            sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            sxx = sum((x - mx) ** 2 for x in xs)
            b = sxy / sxx
            a = my - b * mx
            code = (f"def {fn}(xs, ys):\n"
                    f"    \"\"\"Ordinary least squares; returns (slope, intercept).\"\"\"\n"
                    f"    count = len(xs)\n"
                    f"    if count < 2 or count != len(ys):\n"
                    f"        raise ValueError('need matching lists of length >= 2')\n"
                    f"    mean_x = sum(xs) / count\n"
                    f"    mean_y = sum(ys) / count\n"
                    f"    s_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))\n"
                    f"    s_xx = sum((x - mean_x) ** 2 for x in xs)\n"
                    f"    slope = s_xy / s_xx\n"
                    f"    return round(slope, 4), round(mean_y - slope * mean_x, 4)\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({xs!r}, {ys!r}) == ({round(b, 4)}, {round(a, 4)})\n"
                     f"    assert {fn}([0, 1, 2], [1, 3, 5]) == (2.0, 1.0)\n"
                     f"    try:\n"
                     f"        {fn}([1], [1])\n"
                     f"        assert False\n"
                     f"    except ValueError:\n"
                     f"        pass\n")
            expected = f"Slope {round(b, 4)}, intercept {round(a, 4)}."
        elif kind == "percentile":
            fn = rng.choice(["nearest_rank_percentile", "percentile_rank"])
            p = rng.choice([25, 50, 75, 90])
            s = sorted(data)
            import math
            rank = max(1, math.ceil(p / 100 * len(s)))
            exp = s[rank - 1]
            code = (f"import math\n\n\ndef {fn}(values, p):\n"
                    f"    \"\"\"Nearest-rank percentile: smallest value with rank >= ceil(p/100*n).\"\"\"\n"
                    f"    if not 1 <= p <= 100:\n"
                    f"        raise ValueError('p must be in [1, 100]')\n"
                    f"    ordered = sorted(values)\n"
                    f"    rank = max(1, math.ceil(p / 100 * len(ordered)))\n"
                    f"    return ordered[rank - 1]\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({d_lit}, {p}) == {exp}\n"
                     f"    assert {fn}([1, 2, 3, 4], 100) == 4\n"
                     f"    assert {fn}([1, 2, 3, 4], 25) == 1\n")
            expected = f"p{p} (nearest rank) = {exp}."
        else:  # histogram
            fn = rng.choice(["histogram_bins", "bucket_counts"])
            edges = [-100, -50, 0, 50, 101]
            counts = [0] * (len(edges) - 1)
            for x in data:
                for i in range(len(edges) - 1):
                    if edges[i] <= x < edges[i + 1]:
                        counts[i] += 1
                        break
            labels = [f"[{edges[i]},{edges[i+1]})" for i in range(len(edges) - 1)]
            code = (f"def {fn}(values, edges={edges!r}):\n"
                    f"    \"\"\"Count values in [edge_i, edge_i+1) buckets (last bucket closed).\"\"\"\n"
                    f"    counts = [0] * (len(edges) - 1)\n"
                    f"    for x in values:\n"
                    f"        for i in range(len(edges) - 2, -1, -1):\n"
                    f"            if x >= edges[i]:\n"
                    f"                if i == len(edges) - 2 or x < edges[i + 1]:\n"
                    f"                    counts[i] += 1\n"
                    f"                break\n"
                    f"    labels = [\"[\" + str(edges[i]) + \",\" + str(edges[i + 1]) + \")\"\n"
                    f"              for i in range(len(edges) - 1)]\n"
                    f"    return dict(zip(labels, counts))\n")
            exp = dict(zip(labels, counts))
            d0 = "{'[0,1)': 0, '[1,2)': 0}"
            d1 = "{'[0,1)': 0, '[1,2)': 1}"
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({d_lit}) == {exp!r}\n"
                     f"    assert {fn}([], [0, 1, 2]) == {d0}\n"
                     f"    assert {fn}([2], [0, 1, 2]) == {d1}\n")
            expected = f"Bucket counts: {exp}."
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement a small statistics helper in pure Python (no external packages). "
                  f"{expected} Include input validation and a docstring."),
            expected_behavior=expected, code=code, tests=tests, verify_method="executed",
            notes={"kind": kind,
                   "explain": {"purpose": expected,
                               "approach": "Closed-form statistics computed in one or two passes.",
                               "key_points": ["pure stdlib", "validates input length/ranges"],
                               "big_o_time": "O(n)", "big_o_space": "O(1) or O(n) when sorting"}},
            tags=["statistics", kind], variant=kind, seed=rng.randrange(2**31))


class PythonFileOpsFamily(Family):
    NAME = "py_files_logs"
    LANGUAGE = "python"
    DOMAIN = "automation"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["log_parse", "dedup_lines", "csv_sum", "env_report"])
        if kind == "log_parse":
            fn = rng.choice(["parse_log_lines", "extract_log_fields"])
            levels = ["INFO", "WARN", "ERROR"]
            rows = []
            for _ in range(rng.randint(5, 14)):
                rows.append((rng.choice(levels), rng.choice(["auth", "db", "api", "worker"]),
                             rng.randint(1, 999)))
            log = "\n".join(f"2026-05-1{rng.randrange(0,9)}T10:{rng.randrange(10,59)}:00 {lv} [{svc}] code={c}"
                            for lv, svc, c in rows)
            import re
            pat = re.compile(r"(\S+) (\w+) \[(\w+)\] code=(\d+)")
            parsed = [(m.group(2), m.group(3), int(m.group(4))) for m in pat.finditer(log)]
            errors = [p for p in parsed if p[2] >= 400 or p[0] == "ERROR"]
            code = (f"import re\n\n"
                    f"LOG_RE = re.compile(r\"(?P<ts>\\S+) (?P<level>\\w+) \\[(?P<svc>\\w+)\\] code=(?P<code>\\d+)\")\n\n\n"
                    f"def {fn}(log_text):\n"
                    f"    \"\"\"Return (level, service, code) tuples for every well-formed line.\"\"\"\n"
                    f"    out = []\n"
                    f"    for line in log_text.splitlines():\n"
                    f"        m = LOG_RE.match(line)\n"
                    f"        if m:\n"
                    f"            out.append((m['level'], m['svc'], int(m['code'])))\n"
                    f"    return out\n")
            tests = (f"def run_tests():\n"
                     f"    log = {log!r}\n"
                     f"    assert {fn}(log) == {parsed!r}\n"
                     f"    assert {fn}('') == []\n"
                     f"    assert {fn}('garbage line') == []\n")
            expected = f"Parses {len(parsed)} records; malformed lines are skipped silently."
        elif kind == "dedup_lines":
            fn = rng.choice(["dedup_keep_first", "unique_lines"])
            base = [rng.choice(["alpha", "beta", "gamma", "delta", "eps", "zeta"]) for _ in range(rng.randint(8, 20))]
            exp = []
            seen = set()
            for w in base:
                if w not in seen:
                    seen.add(w)
                    exp.append(w)
            code = (f"def {fn}(lines):\n"
                    f"    \"\"\"Keep the first occurrence of every line, preserving order.\"\"\"\n"
                    f"    seen = set()\n"
                    f"    out = []\n"
                    f"    for line in lines:\n"
                    f"        if line not in seen:\n"
                    f"            seen.add(line)\n"
                    f"            out.append(line)\n"
                    f"    return out\n")
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({base!r}) == {exp!r}\n"
                     f"    assert {fn}([]) == []\n"
                     f"    assert {fn}(['x', 'x']) == ['x']\n")
            expected = f"Collapses {len(base)} lines to {len(exp)} unique-first entries."
        elif kind == "csv_sum":
            fn = rng.choice(["sum_column", "column_total"])
            n_rows = rng.randint(4, 10)
            names = [rng.choice(["alpha", "beta", "gamma", "delta"]) for _ in range(n_rows)]
            nums = [rng.randint(1, 500) for _ in range(n_rows)]
            csv_text = "name,amount\n" + "\n".join(f"{a},{b}" for a, b in zip(names, nums))
            target = rng.choice(names)
            exp = sum(b for a, b in zip(names, nums) if a == target)
            code = (f"import csv\nimport io\n\n\ndef {fn}(csv_text, column_name, target_name):\n"
                    f"    \"\"\"Sum the `amount` column for rows whose `name` matches.\"\"\"\n"
                    f"    reader = csv.DictReader(io.StringIO(csv_text))\n"
                    f"    total = 0\n"
                    f"    for row in reader:\n"
                    f"        if row[\"name\"] == target_name:\n"
                    f"            total += int(row[\"amount\"])\n"
                    f"    return total\n")
            tests = (f"def run_tests():\n"
                     f"    data = {csv_text!r}\n"
                     f"    assert {fn}(data, 'amount', {target!r}) == {exp}\n"
                     f"    assert {fn}('name,amount', 'amount', 'x') == 0\n")
            expected = f"Total for {target!r} = {exp}."
        else:  # env_report
            fn = rng.choice(["build_env_report", "env_snapshot"])
            keys = rng.sample(["PATH", "HOME", "USER", "SHELL", "LANG", "TERM"], 4)
            env = {k: rng.choice(["/usr/bin", "/root", "svc", "/bin/bash", "C.UTF-8", "xterm"]) for k in keys}
            code = (f"def {fn}(env, keys):\n"
                    f"    \"\"\"Selected environment snapshot; missing keys show '<unset>'.\"\"\"\n"
                    f"    return {{k: env.get(k, '<unset>') for k in sorted(keys)}}\n")
            exp = {k: env.get(k, "<unset>") for k in sorted(keys)}
            tests = (f"def run_tests():\n"
                     f"    assert {fn}({env!r}, {keys!r}) == {exp!r}\n"
                     f"    assert {fn}({{}}, ['A']) == {{'A': '<unset>'}}\n")
            expected = "Snapshot sorted by key with '<unset>' placeholders."
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write a Python function for a small ops-automation toolkit. {expected} "
                  f"Use only the standard library, add a docstring, and make the function "
                  f"total (never raise on the tested inputs)."),
            expected_behavior=expected, code=code, tests=tests, verify_method="executed",
            notes={"kind": kind,
                   "explain": {"purpose": expected,
                               "approach": "Standard library only; regex/csv/set based processing.",
                               "key_points": ["stdlib only", "defensive against malformed input"],
                               "big_o_time": "O(n)", "big_o_space": "O(n)"}},
            tags=["files", kind], variant=kind, seed=rng.randrange(2**31))


class PythonConcurrencyFamily(Family):
    NAME = "py_concurrency"
    LANGUAGE = "python"
    DOMAIN = "concurrency"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "debugging", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["pool_map", "queue_pipeline", "lock_counter"])
        if kind == "pool_map":
            fn = rng.choice(["parallel_square_sum", "pool_transform"])
            n = rng.randint(50, 300)
            data = [rng.randint(1, 100) for _ in range(n)]
            code = (f"from concurrent.futures import ThreadPoolExecutor\n\n\n"
                    f"def {fn}(values, workers=4):\n"
                    f"    \"\"\"Square every value on a thread pool; order follows the input.\"\"\"\n"
                    f"    with ThreadPoolExecutor(max_workers=workers) as pool:\n"
                    f"        return list(pool.map(lambda x: x * x, values))\n")
            tests = (f"def run_tests():\n"
                     f"    data = {data!r}\n"
                     f"    assert {fn}(data) == [x * x for x in data]\n"
                     f"    assert {fn}([], 2) == []\n"
                     f"    assert {fn}([3], 1) == [9]\n")
            expected = "Output order matches input order regardless of worker scheduling."
        elif kind == "queue_pipeline":
            code = ('import queue\nimport threading\n\n\ndef pipeline(values, stages=3):\n'
                    '    """Push values through `stages` queues (one thread each);\n'
                    '    returns the final transformed list in order."""\n'
                    '    q_in = queue.Queue()\n'
                    '    for v in values:\n'
                    '        q_in.put(v)\n'
                    '    q_in.put(None)\n'
                    '    out = []\n'
                    '    q_prev = q_in\n'
                    '    for stage in range(stages):\n'
                    '        q_next = queue.Queue()\n'
                    '        def worker(src=q_prev, dst=q_next, step=stage):\n'
                    '            while True:\n'
                    '                item = src.get()\n'
                    '                if item is None:\n'
                    '                    dst.put(None)\n'
                    '                    break\n'
                    '                dst.put(item + step)\n'
                    '        t = threading.Thread(target=worker)\n'
                    '        t.start()\n'
                    '        q_prev = q_next\n'
                    '    while True:\n'
                    '        item = q_prev.get()\n'
                    '        if item is None:\n'
                    '            break\n'
                    '        out.append(item)\n'
                    '    return out\n')
            data = [rng.randint(0, 20) for _ in range(rng.randint(5, 30))]
            stages = rng.randint(2, 4)
            total_shift = stages * (stages - 1) // 2
            tests = (f"def run_tests():\n"
                     f"    data = {data!r}\n"
                     f"    assert pipeline(data, stages={stages}) == [x + {total_shift} for x in data]\n"
                     f"    assert pipeline([], stages=2) == []\n")
            expected = f"With {stages} stages every value gains {total_shift} (0+1+...+{stages - 1}); order preserved."
        else:  # lock_counter
            code = ('import threading\n\n\nclass SafeCounter:\n'
                    '    """Counter whose increments are atomic across threads."""\n\n'
                    '    def __init__(self):\n'
                    '        self._value = 0\n'
                    '        self._lock = threading.Lock()\n\n'
                    '    def increment(self, amount=1):\n'
                    '        with self._lock:\n'
                    '            self._value += amount\n\n'
                    '    @property\n'
                    '    def value(self):\n'
                    '        with self._lock:\n'
                    '            return self._value\n')
            tests = ('def run_tests():\n'
                     '    import threading\n'
                     '    c = SafeCounter()\n'
                     '    def bump():\n'
                     '        for _ in range(2000):\n'
                     '            c.increment()\n'
                     '    threads = [threading.Thread(target=bump) for _ in range(4)]\n'
                     '    for t in threads: t.start()\n'
                     '    for t in threads: t.join()\n'
                     '    assert c.value == 8000\n')
            expected = "4 threads x 2000 increments end at exactly 8000 thanks to the lock."
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement concurrent Python code with correct synchronisation. {expected} "
                  f"Use only threading/queue/concurrent.futures from the standard library."),
            expected_behavior=expected, code=code, tests=tests, verify_method="executed",
            notes={"kind": kind,
                   "explain": {"purpose": expected,
                               "approach": "Thread pool / Queue / Lock patterns from the stdlib.",
                               "key_points": ["shared mutation needs a lock", "sentinel None stops workers",
                                              "map() preserves input order"],
                               "big_o_time": "O(n)", "big_o_space": "O(n)"}},
            tags=["concurrency", kind], variant=kind, seed=rng.randrange(2**31))


class PythonSecurityFamily(Family):
    NAME = "py_security_defensive"
    LANGUAGE = "python"
    DOMAIN = "security"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "security", "testing", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["param_query", "safe_path", "password_hash", "token_compare"])
        if kind == "param_query":
            code = ('import sqlite3\n\n\ndef create_user(conn, username, email):\n'
                    '    """Insert a user using bound parameters (SQL-injection safe)."""\n'
                    '    conn.execute(\n'
                    '        "INSERT INTO users (username, email) VALUES (?, ?)",\n'
                    '        (username, email),\n'
                    '    )\n'
                    '    conn.commit()\n\n\ndef find_user(conn, username):\n'
                    '    """Fetch one user row by exact username match."""\n'
                    '    cur = conn.execute(\n'
                    '        "SELECT id, username, email FROM users WHERE username = ?",\n'
                    '        (username,),\n'
                    '    )\n'
                    '    return cur.fetchone()\n')
            user = rng.choice(["ada", "linus", "grace", "mallory"])
            evil = f"{user}' OR '1'='1"
            tests = (f"def run_tests():\n"
                     f"    import sqlite3\n"
                     f"    conn = sqlite3.connect(':memory:')\n"
                     f"    conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT)')\n"
                     f"    create_user(conn, {user!r}, '{user}@example.test')\n"
                     f"    assert find_user(conn, {user!r}) is not None\n"
                     f"    assert find_user(conn, {evil!r}) is None  # injection is inert\n"
                     f"    assert find_user(conn, 'nobody') is None\n")
            expected = ("Bound ?-parameters keep the payload data: an OR-tautology username "
                        "matches nothing.")
        elif kind == "safe_path":
            base = rng.choice(["/srv/app", "/var/www", "/data/uploads"])
            fn = rng.choice(["resolve_under_base", "safe_join"])
            evil = "../../etc/passwd"
            code = (f"import os\n\n\ndef {fn}(base, user_path):\n"
                    f"    \"\"\"Join user_path under base; raise ValueError on traversal.\"\"\"\n"
                    f"    base_real = os.path.realpath(base)\n"
                    f"    candidate = os.path.realpath(os.path.join(base_real, user_path))\n"
                    f"    if candidate != base_real and not candidate.startswith(base_real + os.sep):\n"
                    f"        raise ValueError('path escapes base directory')\n"
                    f"    return candidate\n")
            tests = (f"def run_tests():\n"
                     f"    base = {base!r}\n"
                     f"    assert {fn}(base, 'docs/readme.txt').startswith(base)\n"
                     f"    assert {fn}(base, '.') == {base!r}\n"
                     f"    try:\n"
                     f"        {fn}(base, {evil!r})\n"
                     f"        assert False, 'expected ValueError'\n"
                     f"    except ValueError:\n"
                     f"        pass\n")
            expected = "realpath containment check rejects ../ traversal attempts."
        elif kind == "password_hash":
            code = ('import hashlib\nimport hmac\nimport os\n\n\ndef hash_password(password):\n'
                    '    """Return salt$pbkdf2_hex using 120k iterations of PBKDF2-HMAC-SHA256."""\n'
                    '    salt = os.urandom(16)\n'
                    '    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)\n'
                    '    return salt.hex() + "$" + digest.hex()\n\n\ndef verify_password(password, stored):\n'
                    '    """Constant-time verification against a stored hash."""\n'
                    '    salt_hex, digest_hex = stored.split("$", 1)\n'
                    '    digest = hashlib.pbkdf2_hmac("sha256", password.encode(),\n'
                    '                                 bytes.fromhex(salt_hex), 120_000)\n'
                    '    return hmac.compare_digest(digest.hex(), digest_hex)\n')
            pwd = rng.choice(["correct horse", "tr0ub4dor&3", "rainbow-6"])
            tests = (f"def run_tests():\n"
                     f"    stored = hash_password({pwd!r})\n"
                     f"    assert verify_password({pwd!r}, stored)\n"
                     f"    assert not verify_password('wrong', stored)\n"
                     f"    assert stored != hash_password({pwd!r})  # random salt\n")
            expected = "Random 16-byte salt + PBKDF2(120k) + constant-time compare."
        else:  # token_compare
            code = ('import hmac\nimport secrets\n\n\ndef issue_token():\n'
                    '    """256-bit URL-safe session token."""\n'
                    '    return secrets.token_urlsafe(32)\n\n\ndef tokens_match(a, b):\n'
                    '    """Constant-time equality check for token comparison."""\n'
                    '    return hmac.compare_digest(a, b)\n')
            tok = "T" * 43
            tests = (f"def run_tests():\n"
                     f"    t = issue_token()\n"
                     f"    assert len(t) >= 40\n"
                     f"    assert tokens_match(t, t)\n"
                     f"    assert not tokens_match(t, 'x' * len(t))\n"
                     f"    assert not tokens_match({tok!r}, {tok!r} + 'x')\n")
            expected = "secrets.token_urlsafe(32) entropy; comparison via hmac.compare_digest."
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write DEFENSIVE security code (safe by construction, no offensive content). "
                  f"{expected} Standard library only; include docstrings explaining the threat "
                  f"mitigated."),
            expected_behavior=expected, code=code, tests=tests, verify_method="executed",
            notes={"kind": kind,
                   "explain": {"purpose": expected,
                               "approach": "Secure-by-construction stdlib primitives.",
                               "key_points": ["parameter binding", "containment checks",
                                              "constant-time comparison", "salted KDF"],
                               "big_o_time": "O(n) or KDF-dominated", "big_o_space": "O(1)"}},
            tags=["security", kind], variant=kind, seed=rng.randrange(2**31))


class PythonProjectFamily(Family):
    """Multi-file Python package: module + tests + README + config."""
    NAME = "py_project_multifile"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    PROJECTS = ("inventory", "bookmarks", "taskqueue")

    def generate(self, rng: random.Random) -> Candidate:
        proj = rng.choice(self.PROJECTS)
        name = rng.choice(["toolkit", "manager", "service", "store"])
        pkg = f"{proj}_{name}"
        if proj == "inventory":
            items = rng.sample(["widget", "gizmo", "doohickey", "thingum", "contraption"],
                               rng.randint(3, 5))
            stock = {w: rng.randint(0, 40) for w in items}
            lib = (f'"""In-memory inventory with a low-stock report."""\n\n\n'
                   f'class Inventory:\n'
                   f'    def __init__(self, threshold=5):\n'
                   f'        self._stock = {{}}\n'
                   f'        self.threshold = threshold\n\n'
                   f'    def add(self, sku, qty=1):\n'
                   f'        if qty < 0:\n'
                   f'            raise ValueError("qty must be >= 0")\n'
                   f'        self._stock[sku] = self._stock.get(sku, 0) + qty\n\n'
                   f'    def take(self, sku, qty=1):\n'
                   f'        if self._stock.get(sku, 0) < qty:\n'
                   f'            raise ValueError("insufficient stock")\n'
                   f'        self._stock[sku] -= qty\n\n'
                   f'    def low_stock(self):\n'
                   f'        return sorted(s for s, q in self._stock.items() if q <= self.threshold)\n')
            main = (f'"""CLI entry: add/take/report commands."""\n'
                    f'from {pkg}.inventory import Inventory\n\n\n'
                    f'def run_commands(inventory, commands):\n'
                    f'    """Apply ("add"|"take", sku, qty) tuples; return low-stock after each."""\n'
                    f'    report = []\n'
                    f'    for cmd, sku, qty in commands:\n'
                    f'        getattr(inventory, cmd)(sku, qty)\n'
                    f'        report.append(inventory.low_stock())\n'
                    f'    return report\n')
            initc = f'"""{pkg} package."""\n\nfrom .inventory import Inventory\n\n__all__ = ["Inventory"]\n'
            readme = (f"# {pkg}\n\nTiny inventory CLI.\n\n"
                      f"- `inventory.py`: Inventory class (add/take/low_stock)\n"
                      f"- `__main__.py`: command runner\n\n"
                      f"## Run tests\n\n`python -m unittest discover -s tests`\n")
            cmds = []
            inv = {}
            exp_reports = []
            for _ in range(rng.randint(4, 8)):
                sku = rng.choice(items)
                if rng.random() < 0.5 or inv.get(sku, 0) == 0:
                    qty = rng.randint(1, 10)
                    inv[sku] = inv.get(sku, 0) + qty
                    cmds.append(("add", sku, qty))
                else:
                    qty = rng.randint(1, inv.get(sku, 0))
                    inv[sku] -= qty
                    cmds.append(("take", sku, qty))
                exp_reports.append(sorted(s for s, q in inv.items() if q <= 5))
            tests = (f"import sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
                     f"from {pkg}.inventory import Inventory\n"
                     f"from {pkg}.__main__ import run_commands\n\n\n"
                     f"class TestInventory(unittest.TestCase):\n"
                     f"    def test_flow(self):\n"
                     f"        inv = Inventory(threshold=5)\n"
                     f"        self.assertEqual(run_commands(inv, {cmds!r}), {exp_reports!r})\n\n"
                     f"    def test_take_guard(self):\n"
                     f"        inv = Inventory()\n"
                     f"        with self.assertRaises(ValueError):\n"
                     f"            inv.take('ghost', 2)\n\n\n"
                     f"if __name__ == '__main__':\n"
                     f"    unittest.main()\n")
            files = [FileSpec(f"{pkg}/__init__.py", initc),
                     FileSpec(f"{pkg}/inventory.py", lib),
                     FileSpec(f"{pkg}/__main__.py", main),
                     FileSpec("README.md", readme),
                     FileSpec("tests/test_inventory.py", tests)]
            expected = "add/take commands update stock; low_stock lists SKUs at/below threshold sorted."
            task = (f"Build the small multi-file Python package '{pkg}' described by the README: "
                    f"an Inventory class (add/take/low_stock with threshold) plus a command runner. "
                    f"Behaviour: {expected} The unittest suite must pass.")
        elif proj == "bookmarks":
            tags = rng.sample(["python", "rust", "web", "db", "devops"], 3)
            lib = (f'"""Tagged bookmark store with fuzzy-free exact search."""\n'
                   f'from dataclasses import dataclass, field\n\n\n'
                   f'@dataclass\nclass Bookmark:\n'
                   f'    title: str\n'
                   f'    url: str\n'
                   f'    tags: list = field(default_factory=list)\n\n\n'
                   f'class BookmarkStore:\n'
                   f'    def __init__(self):\n'
                   f'        self._items = []\n\n'
                   f'    def add(self, title, url, tags=()):\n'
                   f'        self._items.append(Bookmark(title, url, list(tags)))\n\n'
                   f'    def find_by_tag(self, tag):\n'
                   f'        return [b for b in self._items if tag in b.tags]\n\n'
                   f'    def popular_tags(self, top=3):\n'
                   f'        counts = {{}}\n'
                   f'        for b in self._items:\n'
                   f'            for t in b.tags:\n'
                   f'                counts[t] = counts.get(t, 0) + 1\n'
                   f'        return sorted(counts, key=lambda t: (-counts[t], t))[:top]\n')
            main = (f'from {pkg}.bookmarks import BookmarkStore\n\n\ndef bulk_add(store, rows):\n'
                    f'    """rows: iterable of (title, url, tags)."""\n'
                    f'    for title, url, tags in rows:\n'
                    f'        store.add(title, url, tags)\n')
            initc = f'from .bookmarks import BookmarkStore, Bookmark\n\n__all__ = ["BookmarkStore", "Bookmark"]\n'
            readme = f"# {pkg}\n\nTagged bookmarks with exact tag search and popularity ranking.\n"
            rows, exp_pop = [], {}
            for i in range(rng.randint(4, 8)):
                t = rng.choice(tags)
                t2 = rng.choice(tags)
                rows.append((f"site{i}", f"https://site{i}.example", [t, t2]))
                exp_pop[t] = exp_pop.get(t, 0) + 1
                exp_pop[t2] = exp_pop.get(t2, 0) + 1
            top = sorted(exp_pop, key=lambda t: (-exp_pop[t], t))[:2]
            tests = (f"import sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
                     f"from {pkg}.bookmarks import BookmarkStore\n"
                     f"from {pkg}.__main__ import bulk_add\n\n\n"
                     f"class TestBookmarks(unittest.TestCase):\n"
                     f"    def test_popularity(self):\n"
                     f"        store = BookmarkStore()\n"
                     f"        bulk_add(store, {rows!r})\n"
                     f"        self.assertEqual(store.popular_tags(top=2), {top!r})\n"
                     f"        self.assertTrue(all({tags[0]!r} in b.tags for b in store.find_by_tag({tags[0]!r})))\n\n\n"
                     f"if __name__ == '__main__':\n    unittest.main()\n")
            files = [FileSpec(f"{pkg}/__init__.py", initc),
                     FileSpec(f"{pkg}/bookmarks.py", lib),
                     FileSpec(f"{pkg}/__main__.py", main),
                     FileSpec("README.md", readme),
                     FileSpec("tests/test_bookmarks.py", tests)]
            expected = f"popular_tags ranks by count desc then name asc; top-2 = {top}."
            task = (f"Create the multi-file package '{pkg}' (Bookmark dataclass + BookmarkStore with "
                    f"add/find_by_tag/popular_tags + bulk_add runner) exactly as the README "
                    f"describes. Behaviour: {expected} unittest suite must pass.")
        else:  # taskqueue
            lib = (f'"""FIFO task queue with retries."""\n\n\nclass TaskQueue:\n'
                   f'    def __init__(self, max_retries=2):\n'
                   f'        self._pending = []\n'
                   f'        self.max_retries = max_retries\n\n'
                   f'    def push(self, task_id, payload):\n'
                   f'        self._pending.append({{"id": task_id, "payload": payload, "tries": 0}})\n\n'
                   f'    def pop(self):\n'
                   f'        if not self._pending:\n'
                   f'            return None\n'
                   f'        return self._pending.pop(0)\n\n'
                   f'    def retry(self, task):\n'
                   f'        task["tries"] += 1\n'
                   f'        if task["tries"] <= self.max_retries:\n'
                   f'            self._pending.append(task)\n'
                   f'            return True\n'
                   f'        return False\n')
            main = (f'from {pkg}.queue import TaskQueue\n\n\ndef drain(queue, handler, fail_ids=()):\n'
                    f'    """Pop until empty; handler returning False marks failure."""\n'
                    f'    delivered, dead = [], []\n'
                    f'    while True:\n'
                    f'        task = queue.pop()\n'
                    f'        if task is None:\n'
                    f'            break\n'
                    f'        if task["id"] in fail_ids and handler(task) is False:\n'
                    f'            if not queue.retry(task):\n'
                    f'                dead.append(task["id"])\n'
                    f'        else:\n'
                    f'            delivered.append(task["id"])\n'
                    f'    return delivered, dead\n')
            initc = f'from .queue import TaskQueue\n\n__all__ = ["TaskQueue"]\n'
            readme = f"# {pkg}\n\nFIFO queue with bounded retries and a drain runner.\n"
            max_retries = rng.randint(1, 3)
            ids = [f"t{i}" for i in range(rng.randint(3, 6))]
            fail_id = rng.choice(ids)
            tests = (f"import sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
                     f"from {pkg}.queue import TaskQueue\n"
                     f"from {pkg}.__main__ import drain\n\n\nclass TestQueue(unittest.TestCase):\n"
                     f"    def test_retries(self):\n"
                     f"        q = TaskQueue(max_retries={max_retries})\n"
                     f"        for tid in {ids!r}:\n"
                     f"            q.push(tid, {{}})\n"
                     f"        calls = []\n"
                     f"        def handler(task):\n"
                     f"            calls.append(task['id'])\n"
                     f"            return task['id'] not in {fail_id!r}\n"
                     f"        delivered, dead = drain(q, handler, fail_ids={fail_id!r})\n"
                     f"        self.assertNotIn({fail_id!r}, delivered)\n"
                     f"        self.assertEqual(dead, [{fail_id!r}])\n"
                     f"        self.assertEqual(calls.count({fail_id!r}), {max_retries + 1})\n\n\n"
                     f"if __name__ == '__main__':\n    unittest.main()\n")
            files = [FileSpec(f"{pkg}/__init__.py", initc),
                     FileSpec(f"{pkg}/queue.py", lib),
                     FileSpec(f"{pkg}/__main__.py", main),
                     FileSpec("README.md", readme),
                     FileSpec("tests/test_queue.py", tests)]
            expected = (f"Failing task is retried up to {max_retries} extra times then declared "
                        f"dead exactly once.")
            task = (f"Implement the multi-file package '{pkg}': TaskQueue (FIFO with max_retries="
                    f"{max_retries}) and drain() that retries failed tasks. Behaviour: {expected} "
                    f"The unittest suite must pass.")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, files=files,
            entry=f"{pkg}/__init__.py", tests=tests, verify_method="executed",
            is_project=True,
            notes={"project": proj,
                   "explain": {"purpose": expected,
                               "approach": "Package layout: library module + runner + unittest suite + README.",
                               "key_points": ["package-relative imports", "unittest discovery",
                                              "README documents the contract"],
                               "big_o_time": "O(n) per operation", "big_o_space": "O(n)"}},
            tags=["project", proj], variant=proj, seed=rng.randrange(2**31))


register(globals(), PythonBankFamily)
register(globals(), PythonTextProcessingFamily)
register(globals(), PythonDataStatsFamily)
register(globals(), PythonFileOpsFamily)
register(globals(), PythonConcurrencyFamily)
register(globals(), PythonSecurityFamily)
register(globals(), PythonProjectFamily)
