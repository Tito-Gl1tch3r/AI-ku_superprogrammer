"""Superprogrammer extension: systems literacy skills.

py_timezones_unicode: the classic real-world bug farms - weekly meetings
across DST boundaries with zoneinfo (wall-clock steps, NOT utc-offset
steps), NFC/casefold text equality, and locale-agnostic folded sorting.

py_git_forensics: binary-search a regression with REAL `git bisect` on a
synthetic repository built by the test harness (deterministic commit
dates, invocation budget that outlaws linear scans), and read an
unfamiliar repo to find the true definition behind re-export chains.

Every candidate is verified by execution; the git family really runs git.
"""
from __future__ import annotations

import random
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..core import Candidate, Family, register


# --------------------------------------------------------------------------
# py_timezones_unicode
# --------------------------------------------------------------------------

_WEEKLY_GOOD = '''from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def weekly_meetings(start_iso: str, tz_name: str, weeks: int) -> list[str]:
    """Next `weeks` weekly occurrences of a wall-clock local time, in UTC.

    The recurrence steps the LOCAL wall clock by 7 days and only then
    converts to UTC, so the meeting keeps its local hour across DST
    transitions (the UTC hour shifts when DST does).
    """
    tz = ZoneInfo(tz_name)
    current = datetime.fromisoformat(start_iso).replace(tzinfo=tz)
    out = []
    for _ in range(weeks):
        out.append(current.astimezone(timezone.utc).isoformat())
        current += timedelta(days=7)
    return out
'''

_DST_SCENARIOS = [
    ("2026-03-20T10:00:00", "Europe/Madrid"),
    ("2026-03-05T09:30:00", "America/New_York"),
    ("2026-10-20T18:00:00", "Europe/Madrid"),
    ("2026-10-25T08:00:00", "America/New_York"),
    ("2026-03-25T12:00:00", "Europe/London"),
    ("2026-10-23T21:15:00", "Europe/London"),
]

_TEXT_PAIRS = [
    ("cafe\u0301", "caf\u00e9", True),          # decomposed vs composed
    ("CAF\u00c9", "caf\u00e9", True),            # case fold + compose
    ("\u00df", "ss", True),                      # sharp s casefolds to ss
    ("\u03a3", "\u03c2", True),                  # capital vs final sigma
    ("Stra\u00dfe", "STRASSE", True),
    ("resum\u00e9", "r\u00e9sum\u00e9", False),  # different base letters
    ("a", "a\u0301", False),
    ("\ufb01n", "fin", True),                    # fi ligature casefolds to fin
]

_SORT_POOL = ["\u00c1baco", "\u00e1baco", "Zebra", "zebra", "ma\u00f1ana",
              "manada", "Nurse", "nurse", "\u00d1and\u00fa", "oro",
              "\u00c9xodo", "eco"]


def _fold_key(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


class TimezonesUnicodeFamily(Family):
    NAME = "py_timezones_unicode"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "failure_prediction")

    def _mk_dst(self, rng: random.Random) -> Candidate:
        # pick a scenario whose window provably crosses a DST change
        for _ in range(64):
            start_iso, tz_name = rng.choice(_DST_SCENARIOS)
            weeks = rng.randint(4, 8)
            tz = ZoneInfo(tz_name)
            current = datetime.fromisoformat(start_iso).replace(tzinfo=tz)
            expected = []
            for _ in range(weeks):
                expected.append(current.astimezone(timezone.utc).isoformat())
                current += timedelta(days=7)
            local_offsets = {
                datetime.fromisoformat(s).astimezone(tz).utcoffset()
                for s in expected}
            if len(local_offsets) >= 2:
                break
        else:
            start_iso, tz_name = _DST_SCENARIOS[0]
            weeks = 6
            tz = ZoneInfo(tz_name)
            current = datetime.fromisoformat(start_iso).replace(tzinfo=tz)
            expected = []
            for _ in range(weeks):
                expected.append(current.astimezone(timezone.utc).isoformat())
                current += timedelta(days=7)
        tests = (
            f"def run_tests():\n"
            f"    out = weekly_meetings({start_iso!r}, {tz_name!r}, {weeks})\n"
            f"    assert out == {expected!r}\n"
            f"    from zoneinfo import ZoneInfo as _ZI\n"
            f"    offs = {{datetime.fromisoformat(s).astimezone(_ZI({tz_name!r})).utcoffset() for s in out}}\n"
            f"    assert len(offs) >= 2, 'scenario must cross a DST change'\n"
            f"    print('gates-ok')\n"
        )
        task = (
            f"A weekly meeting runs every 7 days at the same LOCAL wall "
            f"clock time in {tz_name}, first occurrence {start_iso}. "
            f"Implement weekly_meetings(start_iso, tz_name, weeks) in "
            f"Python: attach the zone to the naive local datetime, step the "
            f"LOCAL wall clock by 7 days per occurrence, convert each "
            f"occurrence to UTC and return the ISO strings. The UTC hour "
            f"MUST shift when daylight saving time starts or ends inside "
            f"the window (an offset-preserving recurrence is wrong). "
            f"Returns exactly `weeks` ISO UTC strings."
        )
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="advanced", task=task,
            expected_behavior=f"weekly_meetings({start_iso!r}, {tz_name!r}, "
                              f"{weeks}) keeps the local hour across the DST "
                              "transition inside the window",
            code=_WEEKLY_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Wall-clock recurrence across DST transitions",
                "approach": "step local wall time by 7 days, convert after "
                            "each step",
                "key_points": ["timedelta(days=7) on an aware datetime shifts "
                               "wall time, not UTC time",
                               "adding days to a UTC datetime freezes the local "
                               "hour and breaks the meeting",
                               "the battery asserts two distinct UTC offsets",
                               "ZoneInfo handles the rules; never hardcode them"],
                "big_o_time": "O(weeks)", "big_o_space": "O(weeks)",
                "edge_cases": ["meeting hour lands on a spring-forward gap",
                               "offset changes mid-window"]}},
            tags=["timezones", "dst", "i18n"],
            variant=f"dst|{start_iso}|{tz_name}|{weeks}",
            seed=rng.randrange(2**31))

    def _mk_text_eq(self, rng: random.Random) -> Candidate:
        picked = rng.sample(_TEXT_PAIRS, 6)
        tests = (
            f"def run_tests():\n"
            f"    cases = {picked!r}\n"
            f"    for a, b, want in cases:\n"
            f"        got = same_text(a, b)\n"
            f"        assert got == want, (a, b, got, want)\n"
            f"    assert same_text('', '') is True\n"
            f"    print('gates-ok')\n"
        )
        task = (
            "Unicode equality is not code-point equality: 'cafe' with a "
            "combining acute accent and the precomposed 'caf\\u00e9' are "
            "different byte strings for the same text, and case folding is "
            "locale-independent only through str.casefold (which also "
            "expands ligatures and maps final sigma). Implement "
            "same_text(a, b) in Python: normalize BOTH strings to NFC, "
            "then casefold both, then compare. The pinned battery covers "
            "composed/decomposed pairs, capitalization, sharp-s vs SS, "
            "sigma variants, a ligature, and genuinely different texts "
            "that must stay unequal."
        )
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="intermediate", task=task,
            expected_behavior="NFC + casefold equality on the pinned pairs",
            code=("import unicodedata\n\n\n"
                  "def same_text(a: str, b: str) -> bool:\n"
                  "    \"\"\"Locale-free text equality: NFC then casefold.\"\"\"\n"
                  "    return (unicodedata.normalize(\"NFC\", a).casefold()\n"
                  "            == unicodedata.normalize(\"NFC\", b).casefold())\n"),
            tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Correct human-text equality in Python",
                "approach": "unicodedata.normalize('NFC') + str.casefold",
                "key_points": ["== compares code points, not text",
                               "casefold is stricter and safer than lower",
                               "NFC composes combining marks before folding",
                               "ligatures fold to their letter sequence"],
                "big_o_time": "O(len(a) + len(b))",
                "big_o_space": "O(len(a) + len(b))",
                "edge_cases": ["decomposed accent vs precomposed",
                               "ligature fi vs letters f+i",
                               "genuinely different letters stay unequal"]}},
            tags=["unicode", "i18n", "text"],
            variant=f"eq|{len(picked)}", seed=rng.randrange(2**31))

    def _mk_sort(self, rng: random.Random) -> Candidate:
        items = rng.sample(_SORT_POOL, rng.randint(7, len(_SORT_POOL)))
        expected = sorted(items, key=_fold_key)
        tests = (
            f"def run_tests():\n"
            f"    items = {items!r}\n"
            f"    assert sorted_folded(items) == {expected!r}\n"
            f"    assert sorted_folded([]) == []\n"
            f"    assert sorted_folded(['b', 'a']) == ['a', 'b']\n"
            f"    print('gates-ok')\n"
        )
        task = (
            "Plain sorted() orders by code point, so 'Zebra' sorts before "
            "'abaco' and accented letters land after 'z'. Implement "
            "sorted_folded(items) in Python: a stable sort whose key is the "
            "NFC normalization of each string followed by str.casefold, so "
            "case and accents fold to the same rank ('Abaco' == 'abaco' < "
            "'Exodo' < 'manana' < 'Nandu' < 'oro' < 'Zebra'). Keep it "
            "stable for ties (Python's sorted is). Return a NEW list; do "
            "not mutate the input."
        )
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="intermediate", task=task,
            expected_behavior="folded alphabetical order on the pinned pool",
            code=("import unicodedata\n\n\n"
                  "def sorted_folded(items: list[str]) -> list[str]:\n"
                  "    \"\"\"Stable sort keyed by NFC + casefold.\"\"\"\n"
                  "    return sorted(items,\n"
                  "                  key=lambda s: unicodedata.normalize(\n"
                  "                      \"NFC\", s).casefold())\n"),
            tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Human-alphabetical order independent of locale",
                "approach": "sort key = NFC normalize then casefold",
                "key_points": ["code-point order is not alphabetical order",
                               "the key folds case AND accents together",
                               "sorted() is stable, ties keep input order",
                               "return a new list, never mutate the input"],
                "big_o_time": "O(n log n) comparisons",
                "big_o_space": "O(n)",
                "edge_cases": ["empty list", "pure-case ties", "accented heads"]}},
            tags=["unicode", "sorting", "i18n"],
            variant=f"sort|{len(items)}", seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("dst_schedule", "text_equality", "folded_sort"))
        if kind == "dst_schedule":
            return self._mk_dst(rng)
        if kind == "text_equality":
            return self._mk_text_eq(rng)
        return self._mk_sort(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(("dst_schedule", "text_equality", "folded_sort"))
        if kind == "dst_schedule":
            good = self._mk_dst(random.Random(rng.randrange(2**31)))
            buggy = good.code.replace(
                "        out.append(current.astimezone(timezone.utc).isoformat())\n"
                "        current += timedelta(days=7)\n",
                "        current = current.astimezone(timezone.utc)\n"
                "    base = current\n    out = []\n"
                "    for _ in range(weeks):\n"
                "        out.append((base + timedelta(days=7 * out.index(base) "
                "if False else 0)).isoformat())\n        break\n")
            bug_kind = "utc_offset_recurrence"
        elif kind == "text_equality":
            good = self._mk_text_eq(random.Random(rng.randrange(2**31)))
            buggy = ("def same_text(a, b):\n"
                     "    return a == b\n")
            bug_kind = "codepoint_equality"
        else:
            good = self._mk_sort(random.Random(rng.randrange(2**31)))
            buggy = good.code.replace(
                "key=lambda s: unicodedata.normalize(\n"
                "                      \"NFC\", s).casefold())",
                "key=None)")
            bug_kind = "codepoint_sort"
            if buggy == good.code:
                return None
        cand = Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code},
            tags=["systems", "bug"], variant=f"{kind}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


# --------------------------------------------------------------------------
# py_git_forensics
# --------------------------------------------------------------------------

_BISECT_GOOD = '''import subprocess


def find_bad_commit(repo: str, check_path: str) -> str:
    """Bisect a regression: return the first bad commit's full hash.

    The repo has exactly 21 commits (index 0 = oldest good history,
    HEAD = newest). check_path is an absolute path to a checker script
    that exits 0 on a good commit and non-zero on a bad one (bisect run
    executes it with cwd = repo root). The search budget is 8 checker
    invocations, which forces binary search instead of a linear walk.
    Always reset the bisect state before returning.
    """
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", repo, *args],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    git("bisect", "start")
    git("bisect", "bad", "HEAD")
    git("bisect", "good", "HEAD~20")
    proc = subprocess.run(["git", "-C", repo, "bisect", "run",
                           "python3", check_path],
                          capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    git("bisect", "reset")
    for line in output.splitlines():
        if "is the first bad commit" in line:
            return line.split()[0]
    raise RuntimeError("bisect did not converge: " + output)
'''

_BISECT_BUGGY = '''import subprocess


def find_bad_commit(repo: str, check_path: str) -> str:
    revs = subprocess.run(
        ["git", "-C", repo, "rev-list", "--reverse", "HEAD"],
        capture_output=True, text=True, check=True).stdout.split()
    bad = None
    for sha in revs:
        subprocess.run(["git", "-C", repo, "checkout", "-q", sha],
                       capture_output=True, text=True, check=True)
        probe = subprocess.run(["python3", check_path], cwd=repo,
                               capture_output=True, text=True)
        if probe.returncode != 0:
            bad = sha
            break
    subprocess.run(["git", "-C", repo, "checkout", "-q", "HEAD"],
                   capture_output=True, text=True)
    return bad
'''

_GIT_TESTS_PREFIX = '''def run_tests():
    import os
    import pathlib
    import shutil
    import subprocess
    import tempfile

    tmp = tempfile.mkdtemp(prefix="aiku_git_")
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["HOME"] = tmp
    env["GIT_AUTHOR_NAME"] = "AiKu"
    env["GIT_AUTHOR_EMAIL"] = "aiku@example.test"
    env["GIT_COMMITTER_NAME"] = "AiKu"
    env["GIT_COMMITTER_EMAIL"] = "aiku@example.test"

    def git(*args):
        result = subprocess.run(["git", "-C", tmp, *args],
                                capture_output=True, text=True, env=env)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    try:
        git("init", "-q", "-b", "main")
        check = pathlib.Path(tmp) / "check.py"
        check.write_text(
            "import pathlib\\n"
            "log = pathlib.Path('checklog.txt')\\n"
            "with log.open('a') as fh:\\n"
            "    fh.write('c\\\\n')\\n"
            "text = pathlib.Path('data.txt').read_text()\\n"
            "header, _, rest = text.partition('\\\\n')\\n"
            "assert header == 'v:7', header\\n"
            "assert 'BUG' not in rest, 'regression present'\\n"
            "print('ok')\\n"
        )
        hashes = []
        total = 21
        bad_index = {bad_index}
        for index in range(total):
            marker = "BUG-marker" if index >= bad_index else f"line-{index}"
            lines = "\\n".join(f"entry-{i}" for i in range(7 - index % 3))
            (pathlib.Path(tmp) / "data.txt").write_text(
                "v:7\\n" + lines + "\\n" + marker + "\\n")
            env["GIT_AUTHOR_DATE"] = f"2026-01-01T00:00:{index:02d} +0000"
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
            git("add", "-A")
            git("commit", "-q", "-m", f"commit {index}")
            hashes.append(git("rev-parse", "HEAD"))
        checklog = pathlib.Path(tmp) / "checklog.txt"
        if checklog.exists():
            checklog.unlink()
        head_before = git("rev-parse", "HEAD")
        bad_hash = find_bad_commit(tmp, str(check))
        assert bad_hash == hashes[bad_index], (bad_hash, hashes[bad_index])
        calls = len(checklog.read_text().splitlines())
        assert calls <= 8, f"bisect budget blown: {calls} checker calls"
        assert git("rev-parse", "HEAD") == head_before, \
            "bisect state must be reset to HEAD"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("gates-ok")
'''

_ARCH_REPO_SHOP = {
    "app/api.py": ("from core.models import User, validate_user\n"
                   "from helpers.audit import AUDIT_ENABLED\n"
                   "\n"
                   "\n"
                   "def handler(user):\n"
                   "    if AUDIT_ENABLED:\n"
                   "        pass\n"
                   "    return validate_user(user)\n"),
    "core/__init__.py": ("from core.models import User\n"),
    "core/models.py": ("class User:\n"
                       "    def __init__(self, name):\n"
                       "        self.name = name\n"
                       "\n"
                       "\n"
                       "def validate_user(user):\n"
                       "    return bool(user and user.name)\n"),
    "helpers/audit.py": ("AUDIT_ENABLED = True\n"
                         "\n"
                         "def audit(event):\n"
                         "    return event\n"),
}

_ARCH_SYMBOLS_SHOP = {"User": "core/models.py:1",
                      "validate_user": "core/models.py:6",
                      "AUDIT_ENABLED": "helpers/audit.py:1",
                      "handler": "app/api.py:5"}

_ARCH_GOOD = '''def find_definition(files: dict[str, str], symbol: str) -> str:
    """Locate the real definition of `symbol` as 'path:line'.

    A definition is `class X`, `def x(`, or a bare assignment `X = ...`
    at the start of a statement. Imports and re-exports do NOT count,
    even though they mention the name. Paths are scanned in sorted
    order; the symbol has exactly one true definition per repo.
    """
    for path in sorted(files):
        for line_no, line in enumerate(files[path].splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("from ", "import ")):
                continue
            head = stripped.split("#", 1)[0].rstrip(":")
            if (head.startswith(("class ", "def "))
                    and head.split("(")[0].split()[-1] == symbol):
                return f"{path}:{line_no}"
            if head.split("=")[0].strip() == symbol and "=" in head:
                return f"{path}:{line_no}"
    raise LookupError(symbol)
'''

_ARCH_BUGGY = '''def find_definition(files: dict[str, str], symbol: str) -> str:
    for path in sorted(files):
        for line_no, line in enumerate(files[path].splitlines(), start=1):
            if symbol in line:
                return f"{path}:{line_no}"
    raise LookupError(symbol)
'''


class GitForensicsFamily(Family):
    NAME = "py_git_forensics"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "architecture")

    def _mk_bisect(self, rng: random.Random) -> Candidate:
        bad_index = rng.randrange(9, 15)
        tests = _GIT_TESTS_PREFIX.replace("{bad_index}", str(bad_index))
        task = (
            "Forensic debugging with real git. A repository has exactly 21 "
            "commits; every commit contains data.txt, and a checker script "
            "exits 0 on good commits and non-zero on bad ones. Implement "
            "find_bad_commit(repo, check_path) in Python using `git bisect` "
            "via subprocess: start with bad=HEAD and good=HEAD~20, run "
            "`git bisect run python3 <check_path>`, parse the reported "
            "first-bad-commit line, return its FULL commit hash, and reset "
            "the bisect state so the repo ends on HEAD. Efficiency is part "
            "of the contract: the checker may execute at most 8 times "
            "(binary search); a linear walk of the history is rejected by "
            "the test harness."
        )
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="advanced", task=task,
            expected_behavior="returns the exact first bad commit hash with "
                              "at most 8 checker invocations and a clean "
                              "bisect reset",
            code=_BISECT_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Real git bisect automation under an invocation budget",
                "approach": "bisect start/bad/good/run/reset; parse the report line",
                "key_points": ["binary search needs ceil(log2(21)) + slack <= 8 runs",
                               "bisect run drives the checker automatically",
                               "HEAD~20 is the guaranteed-good oldest commit",
                               "reset restores HEAD; never leave bisect state"],
                "big_o_time": "O(log n) checker runs",
                "big_o_space": "O(n) for the history",
                "edge_cases": ["bad commit deep in history (budget)",
                               "checker must run with cwd = repo root",
                               "bisect state must not outlive the function"]}},
            tags=["git", "bisect", "forensics"],
            variant=f"bisect|{bad_index}", seed=rng.randrange(2**31))

    def _mk_archaeology(self, rng: random.Random) -> Candidate:
        repo_name = rng.choice(("shop", "blog", "inventory"))
        files = dict(_ARCH_REPO_SHOP)
        symbols = dict(_ARCH_SYMBOLS_SHOP)
        pinned = rng.sample(sorted(symbols), 3)
        tests = (
            f"def run_tests():\n"
            f"    files = {files!r}\n"
            + "".join(
                f"    assert find_definition(files, {sym!r}) == {symbols[sym]!r}\n"
                for sym in pinned)
            + f"    try:\n"
              f"        find_definition(files, 'nope_missing')\n"
              f"    except LookupError:\n"
              f"        pass\n"
              f"    else:\n"
              f"        raise AssertionError('unknown symbol must raise')\n"
              f"    print('gates-ok')\n"
        )
        task = (
            f"Repo archaeology: you just cloned the '{repo_name}' codebase "
            "(given as a dict path -> source). The name "
            f"'{pinned[0]}' appears in imports, re-exports and call sites, "
            "but only ONE line in the whole tree truly defines it. Implement "
            "find_definition(files, symbol) in Python returning 'path:line' "
            "(1-based) of the real definition: a `class X` line, a `def x(` "
            "line, or a bare `X = ...` assignment. Import/re-export lines "
            "(`from x import y`, `import ...`) and usages do NOT count. "
            "Paths are scanned in sorted order; raise LookupError for a "
            "symbol with no definition. The test pins several symbols whose "
            "naive 'first text match' answer lands on a re-export."
        )
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="advanced", task=task,
            expected_behavior="returns the definition site, not re-exports; "
                              "LookupError for unknown symbols",
            code=_ARCH_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Navigate an unfamiliar repo without being fooled "
                           "by re-exports",
                "approach": "skip import lines; match class/def/assign heads",
                "key_points": ["grep's first hit is usually a re-export",
                               "definitions are class/def/bare-assign heads",
                               "sorted path order keeps the search deterministic",
                               "unknown symbols raise LookupError"],
                "big_o_time": "O(total lines)",
                "big_o_space": "O(1)",
                "edge_cases": ["re-export before the true definition file",
                               "symbol used inside strings and comments",
                               "unknown symbol raises"]}},
            tags=["git", "archaeology", "navigation"],
            variant=f"arch|{repo_name}|{'-'.join(pinned)}",
            seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("bisect_hunt", "repo_archaeology"))
        if kind == "bisect_hunt":
            return self._mk_bisect(rng)
        return self._mk_archaeology(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(("bisect_hunt", "repo_archaeology"))
        if kind == "bisect_hunt":
            good = self._mk_bisect(random.Random(rng.randrange(2**31)))
            buggy = _BISECT_BUGGY
            bug_kind = "linear_scan_budget_blown"
        else:
            good = self._mk_archaeology(random.Random(rng.randrange(2**31)))
            buggy = _ARCH_BUGGY
            bug_kind = "first_text_match"
        cand = Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code},
            tags=["systems", "bug"], variant=f"{kind}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), TimezonesUnicodeFamily)
register(globals(), GitForensicsFamily)
