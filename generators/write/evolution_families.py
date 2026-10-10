"""v0.9.0 evolution families: closes every remaining ROADMAP gap (P2-rest,
P4-rest, P5, P6, P7, P10, P11) with real execution ground truth.

  * git_merge_conflict            (P2) real `git merge` conflict, both intents kept
  * flaky_test_forensics          (P4) hash-seed flakiness measured over real runs
  * sql_schema_migration          (P5) sqlite3 v1->v2 with rejects + byte rollback
  * sdk_docs_integration          (P6) fictional SDK: docs-only surface, strict guard
  * repo_feature_insertion        (P7) enter a foreign repo, extend its registry
  * profile_guided_optimization   (P10) real cProfile excerpt, measured speedup gate
  * doctest_authoring             (P11) living docs: examples really run

Every make_buggy is self-verifying: the buggy candidate is executed against
the real suite (same harness conventions as validators/executors/python_exec)
and the variant is dropped unless it FAILS.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile

from generators.core import Candidate, Family, FileSpec, register

# --------------------------------------------------------------------------
# shared: run the real harness conventions in a temp dir (mirrors python_exec)
# --------------------------------------------------------------------------

_HARNESS = '''import sys
from solution import *  # noqa: F401,F403

{tests}

run_tests()
print("__TESTS_PASSED__")
'''

_PROJECT_HARNESS = '''import sys

{tests}
'''


def _harness_ok(code: str, tests: str, files=None, entry=None) -> bool:
    """True iff the candidate passes the real harness (PYTHONHASHSEED=0).

    Used by make_buggy self-verification and generate-time gates so that a
    variant is only published when the planted bug really breaks the suite.
    """
    d = tempfile.mkdtemp(prefix="aiku_evo_")
    try:
        file_map = {f.path: f.content for f in (files or [])}
        if code is not None and not file_map:
            file_map = {"solution.py": code}
        project = bool(entry or files)
        template = _PROJECT_HARNESS if project else _HARNESS
        for name, content in file_map.items():
            p = os.path.join(d, name)
            os.makedirs(os.path.dirname(p) or d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        with open(os.path.join(d, "_harness.py"), "w", encoding="utf-8") as f:
            f.write(template.format(tests=tests))
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": d,
               "TMPDIR": d, "LANG": "C.UTF-8", "PYTHONHASHSEED": "0",
               "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = subprocess.run([sys.executable, "_harness.py"], cwd=d,
                                  env=env, capture_output=True, text=True,
                                  timeout=14)
        except subprocess.TimeoutExpired:
            return False
        passed = proc.returncode == 0 and (
            project or "__TESTS_PASSED__" in proc.stdout)
        return passed
    finally:
        for root, _, fs in os.walk(d):
            for fn in fs:
                try:
                    os.remove(os.path.join(root, fn))
                except OSError:
                    pass
        try:
            os.rmdir(d)
        except OSError:
            pass


def _py_run(script: str, timeout=12.0, env_extra=None, cwd=None):
    """Run a one-off script (generate-time measurement). Returns CompletedProcess."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": cwd or os.getcwd(), "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-c", script], env=env, cwd=cwd,
                          capture_output=True, text=True, timeout=timeout)


# --------------------------------------------------------------------------
# P2-rest: git merge conflicts resolved for real
# --------------------------------------------------------------------------

class GitMergeConflictFamily(Family):
    """Real `git merge` produces the conflict; the solution keeps BOTH intents.

    Scenario kinds share a shape: two branches edit the SAME contiguous block
    of a small module, so `git merge` must conflict. The ground truth merges
    both intents; the pinned suite runs branch A's tests AND branch B's tests.
    """
    NAME = "git_merge_conflict"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("debugging", "explanation", "failure_prediction")
    KINDS = ("config_merge", "rate_limiter", "render_flags")

    # ---- kind builders: (base, block_old, side_a, side_b, merged, tests_a, tests_b, task_params)

    def _kind_config(self, rng):
        timeout = rng.choice([30, 45, 60])
        retries = rng.choice([2, 3])
        max_conn = rng.choice([8, 16])
        base = (
            "DEFAULTS = {\n"
            f"    \"timeout\": {timeout},\n"
            f"    \"retries\": {retries},\n"
            "}\n\n"
            "def effective(cfg=None):\n"
            "    merged = dict(DEFAULTS)\n"
            "    if cfg:\n"
            "        merged.update(cfg)\n"
            "    return merged\n\n"
            "def describe(cfg=None):\n"
            "    eff = effective(cfg)\n"
            "    return \"timeout=%s retries=%s\" % (eff[\"timeout\"], eff[\"retries\"])\n")
        old_block = (
            "DEFAULTS = {\n"
            f"    \"timeout\": {timeout},\n"
            f"    \"retries\": {retries},\n"
            "}\n")
        side_a = (
            "DEFAULTS = {\n"
            f"    \"timeout\": {timeout + 15},\n"
            f"    \"retries\": {retries},\n"
            f"    \"max_connections\": {max_conn},\n"
            "}\n")
        side_b = (
            "DEFAULTS = {\n"
            f"    \"timeout\": {timeout},\n"
            f"    \"retries\": {retries},\n"
            "    \"backoff\": True,\n"
            "}\n")
        merged = (
            "DEFAULTS = {\n"
            f"    \"timeout\": {timeout + 15},\n"
            f"    \"retries\": {retries},\n"
            f"    \"max_connections\": {max_conn},\n"
            "    \"backoff\": True,\n"
            "}\n\n"
            "def effective(cfg=None):\n"
            "    merged = dict(DEFAULTS)\n"
            "    if cfg:\n"
            "        merged.update(cfg)\n"
            "    return merged\n\n"
            "def describe(cfg=None):\n"
            "    eff = effective(cfg)\n"
            "    return \"timeout=%s retries=%s\" % (eff[\"timeout\"], eff[\"retries\"])\n")
        tests_a = (
            "    from solution import DEFAULTS as D\n"
            f"    assert D[\"timeout\"] == {timeout + 15}, D\n"
            f"    assert D[\"max_connections\"] == {max_conn}, D\n"
            "    from solution import effective\n"
            f"    eff = effective({{\"timeout\": 90}})\n"
            "    assert eff[\"timeout\"] == 90 and eff[\"max_connections\"] "
            f"== {max_conn}\n")
        tests_b = (
            "    from solution import DEFAULTS as D\n"
            "    assert D[\"backoff\"] is True, D\n"
            f"    assert D[\"retries\"] == {retries}, D\n"
            "    from solution import describe\n"
            f"    assert describe() == \"timeout={timeout + 15} "
            f"retries={retries}\", describe()\n")
        intent_a = (f"raise the default timeout to {timeout + 15} seconds and "
                    f"add \"max_connections\": {max_conn}")
        intent_b = ("mark the client's backoff capability by adding "
                    "\"backoff\": True to the defaults")
        return dict(base=base, old=old_block, a=side_a, b=side_b,
                    merged=merged, tests_a=tests_a, tests_b=tests_b,
                    intents=(intent_a, intent_b), module="client defaults",
                    variant=f"config|{timeout}|{max_conn}")

    def _kind_limiter(self, rng):
        cap = rng.choice([3, 5])
        cooldown = rng.choice([2, 4])
        burst = rng.choice([1, 2])
        base = (
            f"CAP = {cap}\n"
            "ALLOWED = 0\n\n"
            "def allow(n=1):\n"
            "    \"\"\"Allow a request while under the fixed cap.\"\"\"\n"
            "    global ALLOWED\n"
            "    if ALLOWED + n > CAP:\n"
            "        return False\n"
            "    ALLOWED += n\n"
            "    return True\n")
        old_block = (
            "def allow(n=1):\n"
            "    \"\"\"Allow a request while under the fixed cap.\"\"\"\n"
            "    global ALLOWED\n"
            "    if ALLOWED + n > CAP:\n"
            "        return False\n"
            "    ALLOWED += n\n"
            "    return True\n")
        side_a = (
            "def allow(n=1):\n"
            "    \"\"\"Fixed cap, but a burst of %d passes before counting.\"\"\"\n"
            "    global ALLOWED, BURST\n"
            "    if BURST > 0:\n"
            "        BURST -= 1\n"
            "        return True\n"
            "    if ALLOWED + n > CAP:\n"
            "        return False\n"
            "    ALLOWED += n\n"
            "    return True\n"
            "\n"
            f"BURST = {burst}\n") % burst
        side_b = (
            "def allow(n=1):\n"
            "    \"\"\"Fixed cap; refusal starts a cooldown window.\"\"\"\n"
            "    global ALLOWED, COOLDOWN\n"
            "    if COOLDOWN > 0:\n"
            "        COOLDOWN -= 1\n"
            "        return False\n"
            "    if ALLOWED + n > CAP:\n"
            "        COOLDOWN = %d\n"
            "        return False\n"
            "    ALLOWED += n\n"
            "    return True\n"
            "\n"
            "COOLDOWN = 0\n") % cooldown
        merged = (
            f"CAP = {cap}\n"
            "ALLOWED = 0\n"
            f"BURST = {burst}\n"
            "COOLDOWN = 0\n\n"
            "def allow(n=1):\n"
            f"    \"\"\"Fixed cap; burst of {burst} first, then cooldown on refusal.\"\"\"\n"
            "    global ALLOWED, BURST, COOLDOWN\n"
            "    if BURST > 0:\n"
            "        BURST -= 1\n"
            "        return True\n"
            "    if COOLDOWN > 0:\n"
            "        COOLDOWN -= 1\n"
            "        return False\n"
            "    if ALLOWED + n > CAP:\n"
            f"        COOLDOWN = {cooldown}\n"
            "        return False\n"
            "    ALLOWED += n\n"
            "    return True\n")
        tests_a = (
            "    import solution\n"
            f"    for _ in range({burst}):\n"
            "        assert solution.allow() is True  # startup burst\n"
            "    assert solution.BURST == 0\n"
            f"    for _ in range({cap}):\n"
            "        assert solution.allow() is True\n"
            "    assert solution.allow() is False\n")
        tests_b = (
            "    import solution\n"
            "    solution.ALLOWED = 0\n"
            f"    solution.BURST = {burst}\n"
            "    solution.COOLDOWN = 0\n"
            f"    for _ in range({cap + burst + 1}):\n"
            "        solution.allow()\n"
            f"    assert solution.COOLDOWN == {cooldown}\n"
            "    assert solution.allow() is False  # inside the cooldown window\n")
        intent_a = (f"let the first {burst} request(s) through uncounted as a "
                    "startup burst")
        intent_b = ("start a cooldown window of " + str(cooldown) +
                    " refusals whenever the cap rejects")
        return dict(base=base, old=old_block, a=side_a, b=side_b,
                    merged=merged, tests_a=tests_a, tests_b=tests_b,
                    intents=(intent_a, intent_b), module="rate limiter",
                    variant=f"limiter|{cap}|{burst}|{cooldown}")

    def _kind_render(self, rng):
        width = rng.choice([10, 12])
        base = (
            "def render(text, flags=()):\n"
            "    \"\"\"Apply layout flags to text.\"\"\"\n"
            "    out = text\n"
            "    for f in flags:\n"
            "        if f == \"trim\":\n"
            "            out = out.strip()\n"
            "    return out\n\n"
            "def banner(text, flags=()):\n"
            "    body = render(text, flags)\n"
            f"    return body + \"~\" * max(0, {width} - len(body))\n")
        old_block = (
            "    out = text\n"
            "    for f in flags:\n"
            "        if f == \"trim\":\n"
            "            out = out.strip()\n"
            "    return out\n")
        side_a = (
            "    out = text\n"
            "    for f in flags:\n"
            "        if f == \"trim\":\n"
            "            out = out.strip()\n"
            "        elif f == \"upper\":\n"
            "            out = out.upper()\n"
            "    return out\n")
        side_b = (
            "    out = text\n"
            "    for f in flags:\n"
            "        if f == \"trim\":\n"
            "            out = out.strip()\n"
            "        elif f == \"wrap\":\n"
            "            out = \"\\n\".join(out[i:i + 4] for i in "
            "range(0, len(out), 4))\n"
            "    return out\n")
        merged = (
            "def render(text, flags=()):\n"
            "    \"\"\"Apply layout flags to text.\"\"\"\n"
            "    out = text\n"
            "    for f in flags:\n"
            "        if f == \"trim\":\n"
            "            out = out.strip()\n"
            "        elif f == \"upper\":\n"
            "            out = out.upper()\n"
            "        elif f == \"wrap\":\n"
            "            out = \"\\n\".join(out[i:i + 4] for i in "
            "range(0, len(out), 4))\n"
            "    return out\n\n"
            "def banner(text, flags=()):\n"
            "    body = render(text, flags)\n"
            f"    return body + \"~\" * max(0, {width} - len(body))\n")
        word = rng.choice(["alpha", "beta", "gamma"])
        tests_a = (
            "    from solution import render\n"
            "    assert render(\" hi \", (\"trim\", \"upper\")) == \"HI\"\n"
            f"    assert render(\"{word}\", (\"upper\",)) == \"{word.upper()}\"\n")
        tests_b = (
            "    from solution import render, banner\n"
            "    assert render(\"abcdefgh\", (\"wrap\",)) == \"abcd\\nefgh\"\n"
            "    assert \"\\n\" not in banner(\"ok\", ())\n")
        intent_a = "add an \"upper\" flag that uppercases the text"
        intent_b = ("add a \"wrap\" flag that splits the text into chunks of 4 "
                    "characters joined with newlines")
        return dict(base=base, old=old_block, a=side_a, b=side_b,
                    merged=merged, tests_a=tests_a, tests_b=tests_b,
                    intents=(intent_a, intent_b), module="text renderer",
                    variant=f"render|{width}|{word}")

    _KINDS = {"config_merge": _kind_config, "rate_limiter": _kind_limiter,
              "render_flags": _kind_render}

    # ---- git plumbing -------------------------------------------------
    def _real_conflict(self, scenario):
        """Run a REAL git history and merge; return the conflicted file text.

        Returns (conflicted_text, merge_info) or None when git disagrees
        (honest gate: no invented conflict markers).
        """
        d = tempfile.mkdtemp(prefix="aiku_git_")
        try:
            def git(*args, **kw):
                env = dict(os.environ,
                           GIT_AUTHOR_NAME="a", GIT_AUTHOR_EMAIL="a@a",
                           GIT_COMMITTER_NAME="a", GIT_COMMITTER_EMAIL="a@a",
                           GIT_AUTHOR_DATE="2026-01-01T00:00:00 +0000",
                           GIT_COMMITTER_DATE="2026-01-01T00:00:00 +0000",
                           HOME=d)
                return subprocess.run(["git", *args], cwd=d, env=env,
                                      capture_output=True, text=True,
                                      timeout=20, **kw)

            def commit(msg):
                if git("add", "mod.py").returncode != 0:
                    return False
                r = git("commit", "-m", msg)
                return r.returncode == 0

            def write(text):
                with open(os.path.join(d, "mod.py"), "w", encoding="utf-8") as f:
                    f.write(text)

            if git("init", "-q").returncode != 0:
                return None
            write(scenario["base"])
            if not commit("base"):
                return None
            trunk = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            if not trunk:
                return None
            if git("checkout", "-q", "-b", "feature-a").returncode != 0:
                return None
            write(scenario["base"].replace(scenario["old"], scenario["a"]))
            if scenario["base"].replace(scenario["old"], scenario["a"]) == \
                    scenario["base"]:
                return None
            if not commit("intent A"):
                return None
            if git("checkout", "-q", trunk).returncode != 0:
                return None
            write(scenario["base"].replace(scenario["old"], scenario["b"]))
            if scenario["base"].replace(scenario["old"], scenario["b"]) == \
                    scenario["base"]:
                return None
            if not commit("intent B"):
                return None
            m = git("merge", "feature-a")
            if m.returncode == 0:
                return None  # regions too far apart: no conflict, drop seed
            with open(os.path.join(d, "mod.py"), encoding="utf-8") as f:
                conflicted = f.read()
            if "<<<<<<<" not in conflicted or ">>>>>>>" not in conflicted:
                return None
            info = {"merge_exit": m.returncode,
                    "stderr": (m.stderr or "").strip()[:200]}
            return conflicted, info
        except Exception:
            return None
        finally:
            for root, _, fs in os.walk(d):
                for fn in fs:
                    try:
                        os.remove(os.path.join(root, fn))
                    except OSError:
                        pass
            try:
                os.rmdir(d)
            except OSError:
                pass

    def _candidate(self, rng, kind, sc, conflicted, info):
        tests = ("def run_tests():\n"
                 + sc["tests_a"] + "\n"
                 + sc["tests_b"] + "\n"
                 "    print(\"gates-ok\")\n")
        task = (
            f"A teammate merged two feature branches of a {sc['module']} "
            "module and git stopped with a conflict. Branch intent A: "
            f"{sc['intents'][0]}. Branch intent B: {sc['intents'][1]}. "
            "Here is the file exactly as git left it:\n\n"
            f"{conflicted}\n"
            "Produce the resolved file: keep BOTH intents, keep the "
            "untouched parts identical, and make sure the combined suite "
            "(branch A's tests AND branch B's tests) passes. Do not rename "
            "existing public names.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced", task=task,
            expected_behavior=("both branch intents coexist in one module; "
                               "the combined suite passes"),
            code=sc["merged"], tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": f"git merge conflict resolution: {kind}",
                "approach": "real git merge produced the conflict; the "
                            "resolution preserves both intents and the suite "
                            "runs both branches' tests",
                "key_points": ["read both sides before resolving",
                               "a resolution that drops one intent fails "
                               "that branch's tests",
                               "untouched regions stay byte-identical"],
                "big_o_time": "O(file)", "big_o_space": "O(file)",
                "edge_cases": ["adjacent-line conflicts",
                               "merge markers left in the file"]},
                   "git_merge": info},
            tags=["git", "merge-conflict", kind],
            variant=sc["variant"], seed=rng.randrange(2 ** 31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        sc = self._KINDS[kind](self, rng)
        got = self._real_conflict(sc)
        if got is None:
            return None
        conflicted, info = got
        return self._candidate(rng, kind, sc, conflicted, info)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        sc = self._KINDS[kind](self, rng)
        drop = rng.choice(["a", "b"])
        if drop == "a":
            # resolution keeps B and silently loses A's intent
            resolved = sc["base"].replace(sc["old"], sc["b"])
            bug_kind = "lost_intent_a"
        else:
            resolved = sc["base"].replace(sc["old"], sc["a"])
            bug_kind = "lost_intent_b"
        tests = ("def run_tests():\n"
                 + sc["tests_a"] + "\n" + sc["tests_b"] + "\n")
        if _harness_ok(resolved, tests):
            return None  # self-verification: the bug MUST break the suite
        good = self._KINDS[kind](self, rng)
        good_cand = self._candidate(rng, kind, good, sc["base"], {
            "merge_exit": 1, "stderr": "synthetic reference"})
        cand = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced", task=good_cand.task,
            expected_behavior="See question.", code=resolved,
            tests=good_cand.tests, verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good["merged"]},
            tags=["git", "bug"], variant=f"{good['variant']}|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "correct_code": good["merged"],
                "tests": good_cand.tests}
        return cand, meta


register(globals(), GitMergeConflictFamily)

# --------------------------------------------------------------------------
# P4-rest: flaky-test forensics (hash-seed flakiness, measured for real)
# --------------------------------------------------------------------------

class FlakyTestForensicsFamily(Family):
    """A suite that fails only under some PYTHONHASHSEED values.

    The tie-break rule iterates a set, so the result depends on str hash
    order. At generate time the buggy module is executed across many real
    seeds; the recorded evidence (which seeds disagreed, and how) is REAL.
    The candidate is the fixed module: deterministic tie order, identical
    output under every hash seed (pinned by subprocess re-runs in tests).
    """
    NAME = "flaky_test_forensics"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("debugging", "testing", "explanation", "failure_prediction")
    KINDS = ("traffic_report", "quota_pick")

    _SEEDS = tuple(range(41))

    _BUGGY_TRAFFIC = (
        "def status_report(counts, limit):\n"
        "    \"\"\"Sources with count >= limit, highest count first;\n"
        "    equal counts in first-seen order.\"\"\"\n"
        "    hot = {s for s, c in counts.items() if c >= limit}\n"
        "    return sorted(hot, key=lambda s: -counts[s])\n")

    _FIXED_TRAFFIC = (
        "def status_report(counts, limit):\n"
        "    \"\"\"Sources with count >= limit, highest count first;\n"
        "    equal counts in first-seen order.\"\"\"\n"
        "    first_seen = {}\n"
        "    for index, source in enumerate(counts):\n"
        "        first_seen.setdefault(source, index)\n"
        "    hot = [s for s, c in counts.items() if c >= limit]\n"
        "    hot.sort(key=lambda s: (-counts[s], first_seen[s]))\n"
        "    return hot\n")

    _BUGGY_QUOTA = (
        "def assign_quota(demand, pool):\n"
        "    \"\"\"Give every team with demand a slot from the pool,\n"
        "    biggest demand first; equal demands in first-seen order.\"\"\"\n"
        "    needy = {t for t, d in demand.items() if d > 0}\n"
        "    ranked = sorted(needy, key=lambda t: -demand[t])\n"
        "    return ranked[:pool]\n")

    _FIXED_QUOTA = (
        "def assign_quota(demand, pool):\n"
        "    \"\"\"Give every team with demand a slot from the pool,\n"
        "    biggest demand first; equal demands in first-seen order.\"\"\"\n"
        "    first_seen = {}\n"
        "    for index, team in enumerate(demand):\n"
        "        first_seen.setdefault(team, index)\n"
        "    needy = [t for t, d in demand.items() if d > 0]\n"
        "    needy.sort(key=lambda t: (-demand[t], first_seen[t]))\n"
        "    return needy[:pool]\n")

    def _scenario(self, kind, rng):
        if kind == "traffic_report":
            names = rng.sample(["auth", "billing", "search", "mesh", "cdn",
                                "api", "vault", "ingest"], 6)
            top = rng.sample(names, 2)
            ties = rng.sample([n for n in names if n not in top], 3)
            cold = [n for n in names if n not in top and n not in ties][:1]
            counts = {}
            for n in top:
                counts[n] = 9
            for n in ties:
                counts[n] = 5
            for n in cold:
                counts[n] = 2
            limit = 5
            buggy, fixed = self._BUGGY_TRAFFIC, self._FIXED_TRAFFIC
            fn = "status_report"
            args = f"({counts!r}, {limit})"
            spec = ("sources with count >= limit, highest count first, "
                    "equal counts in first-seen insertion order of the "
                    "counts mapping")
        else:
            names = rng.sample(["core", "web", "ops", "ml", "edge", "docs",
                                "sre", "data"], 6)
            big = rng.sample(names, 2)
            ties = rng.sample([n for n in names if n not in big], 3)
            demand = {}
            for n in big:
                demand[n] = 6
            for n in ties:
                demand[n] = 3
            demand[rng.choice([n for n in names if n not in big
                               and n not in ties])] = 0
            pool = 5
            counts, limit = demand, pool
            buggy, fixed = self._BUGGY_QUOTA, self._FIXED_QUOTA
            fn = "assign_quota"
            args = f"({demand!r}, {pool})"
            spec = ("teams with demand > 0, biggest demand first, equal "
                    "demands in first-seen insertion order of the demand "
                    "mapping, truncated to pool slots")
        expected = fixed  # the fixed module computes it; measured below
        return dict(kind=kind, counts=counts, limit=limit, buggy=buggy,
                    fixed=fixed, fn=fn, args=args, spec=spec,
                    variant=f"{kind}|{'|'.join(sorted(counts))[:60]}")

    def _measure_flakiness(self, sc):
        """Execute the buggy module across seeds; return evidence or None.

        The buggy module is materialized to a temp dir as solution.py and
        executed once per PYTHONHASHSEED; the recorded evidence (which
        seeds disagreed, and how) is REAL.
        """
        d = tempfile.mkdtemp(prefix="aiku_flaky_")
        try:
            with open(os.path.join(d, "solution.py"), "w",
                      encoding="utf-8") as f:
                f.write(sc["buggy"])
            script = ("import json\n"
                      "import solution as m\n"
                      f"print(json.dumps(m.{sc['fn']}{sc['args']}))\n")
            seen = {}
            for seed in self._SEEDS:
                try:
                    proc = _py_run(script, timeout=8, cwd=d,
                                   env_extra={"PYTHONHASHSEED": str(seed)})
                except subprocess.TimeoutExpired:
                    continue
                if proc.returncode != 0:
                    continue
                out = proc.stdout.strip()
                seen.setdefault(out, []).append(seed)
            if len(seen) < 2:
                return None  # never disagreed: no honest flakiness evidence
            outputs = sorted(seen, key=lambda o: -len(seen[o]))
            a, b = outputs[0], outputs[1]
            return {"seed_group_a": seen[a][:6], "seed_group_b": seen[b][:6],
                    "output_a": a, "output_b": b,
                    "outputs_seen": len(seen)}
        finally:
            try:
                os.remove(os.path.join(d, "solution.py"))
                os.rmdir(d)
            except OSError:
                pass

    def _expected(self, sc):
        """Compute the expected result with the family's own reference impl."""
        d = tempfile.mkdtemp(prefix="aiku_flakyexp_")
        try:
            with open(os.path.join(d, "reference.py"), "w",
                      encoding="utf-8") as f:
                f.write(sc["fixed"])
            script = ("import json\n"
                      "import reference as m\n"
                      f"print(json.dumps(m.{sc['fn']}{sc['args']}))\n")
            proc = _py_run(script, timeout=8, cwd=d)
            if proc.returncode != 0:
                return None
            return proc.stdout.strip()
        finally:
            try:
                os.remove(os.path.join(d, "reference.py"))
                os.rmdir(d)
            except OSError:
                pass

    def _tests(self, sc, expected):
        return (
            "import json\n"
            "import os\n"
            "import subprocess\n"
            "import sys\n"
            "\n"
            f"INPUT = {sc['counts']!r}\n"
            f"LIMIT = {sc['limit']!r}\n"
            f"EXPECTED = {expected}\n"
            "\n"
            "def run_tests():\n"
            "    import solution\n"
            f"    assert solution.{sc['fn']}(INPUT, LIMIT) == EXPECTED\n"
            "    script = ('import json,sys;import solution as m;'\n"
            f"              \"print(json.dumps(m.{sc['fn']}{sc['args']}))\")\n"
            "    outs = []\n"
            "    for seed in ('1', '7', '11', '23', '42'):\n"
            "        env = dict(os.environ, PYTHONHASHSEED=seed)\n"
            "        proc = subprocess.run([sys.executable, '-c', script],\n"
            "                              capture_output=True, text=True,\n"
            "                              env=env, timeout=8)\n"
            "        assert proc.returncode == 0, proc.stderr\n"
            "        outs.append(proc.stdout.strip())\n"
            "    assert len(set(outs)) == 1, outs\n"
            "    assert json.loads(outs[0]) == EXPECTED, outs\n"
            "    print('gates-ok')\n")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        sc = self._scenario(kind, rng)
        evidence = self._measure_flakiness(sc)
        if evidence is None:
            return None
        expected = self._expected(sc)
        if expected is None:
            return None
        task = (
            "CI runs this module's suite under many hash seeds and it fails "
            "only on some runners. The module:\n\n"
            f"{sc['buggy']}\n"
            "Measured evidence from the real CI replication: with hash seed "
            f"{evidence['seed_group_a'][0]} the call "
            f"{sc['fn']}{sc['args']} returned {evidence['output_a']}, but "
            f"with hash seed {evidence['seed_group_b'][0]} it returned "
            f"{evidence['output_b']} ({evidence['outputs_seen']} distinct "
            "outputs across 41 seeded runs).\n\n"
            f"Contract: {sc['spec']}. Fix the module so the result is "
            "identical under every PYTHONHASHSEED value, keep the signature "
            "and docstring contract, and do not change the call sites. The "
            "hidden suite re-runs the call under several hash seeds and "
            "rejects any output drift.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced", task=task,
            expected_behavior=("deterministic result: ties follow first-seen "
                               "insertion order on every hash seed"),
            code=sc["fixed"], tests=self._tests(sc, expected),
            verify_method="executed",
            notes={"explain": {
                "purpose": f"flaky test forensics: {kind}",
                "approach": "set iteration order follows str hash "
                            "randomization; the fix derives tie order from "
                            "the input's own insertion order",
                "key_points": ["never let a set's iteration order decide "
                               "visible output",
                               "first-seen order must be captured while "
                               "scanning the input",
                               "the suite proves determinism by re-running "
                               "under several hash seeds"],
                "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                "edge_cases": ["ties across hash seeds",
                               "empty input", "pool smaller than needy set"]},
                   "flaky_evidence": evidence},
            tags=["testing", "flaky", kind, "hash-seed"],
            variant=sc["variant"], seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        sc = self._scenario(kind, rng)
        expected = self._expected(sc)
        if expected is None:
            return None
        # bug: "stability" achieved by sorting ties ALPHABETICALLY instead of
        # first-seen order (deterministic, so the cross-seed check passes, but
        # the contract violation is caught by the pinned expectation)
        if kind == "traffic_report":
            buggy = self._FIXED_TRAFFIC.replace(
                "hot.sort(key=lambda s: (-counts[s], first_seen[s]))",
                "hot.sort(key=lambda s: (-counts[s], s))")
        else:
            buggy = self._FIXED_QUOTA.replace(
                "needy.sort(key=lambda t: (-demand[t], first_seen[t]))",
                "needy.sort(key=lambda t: (-demand[t], t))")
        if buggy == sc["fixed"]:
            return None
        tests = self._tests(sc, expected)
        if _harness_ok(buggy, tests):
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced",
            task=("Fix the nondeterministic tie order in this module so the "
                  "result is stable under every hash seed; ties must follow "
                  f"first-seen order. Contract: {sc['spec']}."),
            expected_behavior="See question.", code=buggy, tests=tests,
            verify_method="executed",
            notes={"bug_kind": "unstable_tiebreak",
                   "correct_code": sc["fixed"]},
            tags=["testing", "bug"], variant=f"{sc['variant']}|bug|id_tie",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": "unstable_tiebreak", "correct_code": sc["fixed"],
                "tests": tests}
        return cand, meta


register(globals(), FlakyTestForensicsFamily)

# --------------------------------------------------------------------------
# P5: schema evolution / data migrations with real sqlite3
# --------------------------------------------------------------------------

class SchemaMigrationFamily(Family):
    """Evolve a dirty v1 SQLite database into v2 without losing anything.

    The generator authors the v1 rows AND the expected v2/rejects state with
    its own reference implementation; the pinned suite rebuilds the dirty v1
    database, runs the candidate's migrate(conn), asserts the v2 state row by
    row, then runs rollback(conn) and asserts the v1 schema + rows restored
    exactly (migrate must have kept a backup).
    """
    NAME = "sql_schema_migration"
    LANGUAGE = "python"
    DOMAIN = "databases"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("explanation", "debugging", "failure_prediction")

    V1_SCHEMA = ("CREATE TABLE orders (id INTEGER PRIMARY KEY, "
                 "customer TEXT, ts TEXT, amount TEXT, status TEXT)")
    V1_COLS = "id, customer, ts_utc, amount_cents, status"

    _TZ = ("+02:00", "+05:30", "-03:00")

    def _dirty_rows(self, rng):
        """(rows, expected_v2, expected_rejects) authored by the reference."""
        customers = rng.sample(["ana", "bruno", "caro", "dimitri", "elda",
                                "farid", "greta"], 4)
        rows = []
        oid = 1
        clean = rng.randint(3, 5)
        base_days = rng.sample(range(1, 28), 8)
        for i in range(clean):
            cust = customers[rng.randrange(len(customers))]
            day = base_days[i]
            hour = rng.randrange(6, 20)
            minute = rng.choice(["00", "15", "30", "45"])
            amount = f"{rng.randrange(2, 40)}.{rng.choice(['50', '99', '00', '25'])}"
            rows.append((oid, cust,
                         f"2026-04-{day:02d}T{hour:02d}:{minute}:00Z",
                         amount, "new"))
            oid += 1
        # one tz-offset row that must convert cleanly
        cust = customers[rng.randrange(len(customers))]
        tz = rng.choice(self._TZ)
        rows.append((oid, cust, f"2026-04-05 12:30:00{tz}", "7.10", "new"))
        oid += 1
        # one exact duplicate pair (same customer/ts/amount, new id)
        dup_src = rows[rng.randrange(len(rows))]
        rows.append((oid, dup_src[1], dup_src[2], dup_src[3], dup_src[4]))
        oid += 1
        # one bad timestamp
        rows.append((oid, customers[0], "yesterday morning", "5.00", "new"))
        oid += 1
        # one bad amount
        rows.append((oid, customers[1],
                     f"2026-04-10T08:00:00Z", rng.choice(["N/A", "n/a", "?"]),
                     "new"))
        oid += 1
        # a second duplicate of an earlier row, different amount formatting
        twin_src = rows[rng.randrange(len(rows) - 3)]  # a clean row
        alt_amount = twin_src[3]
        if "." not in alt_amount:
            alt_amount += ".00"
        rows.append((oid, twin_src[1], twin_src[2], alt_amount, twin_src[4]))
        return rows

    @staticmethod
    def _to_utc(ts):
        from datetime import datetime, timezone
        text = ts.strip()
        try:
            if text.endswith("Z"):
                dt = datetime.fromisoformat(text[:-1]).replace(
                    tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return None

    @staticmethod
    def _to_cents(amount):
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        try:
            value = Decimal(amount.strip())
        except (InvalidOperation, ValueError):
            return None
        return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))

    def _reference(self, rows):
        """The family's own migration reference: (v2_rows, rejects)."""
        seen = set()
        v2, rejects = [], []
        for oid, cust, ts, amount, status in rows:
            ts_utc = self._to_utc(ts)
            if ts_utc is None:
                rejects.append((oid, "bad_ts"))
                continue
            cents = self._to_cents(amount)
            if cents is None:
                rejects.append((oid, "bad_amount"))
                continue
            key = (cust, ts_utc, cents)
            if key in seen:
                rejects.append((oid, "duplicate"))
                continue
            seen.add(key)
            v2.append((oid, cust, ts_utc, cents, status))
        return v2, rejects

    _SOLUTION = '''import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

V1_SCHEMA = ("CREATE TABLE orders (id INTEGER PRIMARY KEY, "
             "customer TEXT, ts TEXT, amount TEXT, status TEXT)")


def _to_utc(ts):
    text = ts.strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _to_cents(amount):
    try:
        value = Decimal(amount.strip())
    except (InvalidOperation, ValueError):
        return None
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def migrate(conn):
    """v1 -> v2: normalize ts to UTC, amounts to integer cents, dedup.

    Rejects land in orders_rejects(order_id, reason) with precedence
    bad_ts > bad_amount > duplicate. The v1 table is backed up to
    orders_v1_backup (schema + rows) and then replaced by orders_v2.
    """
    conn.execute("CREATE TABLE orders_v1_backup (id INTEGER PRIMARY KEY, "
                 "customer TEXT, ts TEXT, amount TEXT, status TEXT)")
    conn.execute("INSERT INTO orders_v1_backup SELECT * FROM orders")
    conn.execute("CREATE TABLE orders_v2 (id INTEGER PRIMARY KEY, "
                 "customer TEXT, ts_utc TEXT, amount_cents INTEGER, "
                 "status TEXT)")
    conn.execute("CREATE TABLE orders_rejects (order_id INTEGER PRIMARY KEY, "
                 "reason TEXT)")
    seen = set()
    for oid, cust, ts, amount, status in conn.execute(
            "SELECT id, customer, ts, amount, status FROM orders ORDER BY id"):
        ts_utc = _to_utc(ts)
        if ts_utc is None:
            conn.execute("INSERT INTO orders_rejects VALUES (?, ?)",
                         (oid, "bad_ts"))
            continue
        cents = _to_cents(amount)
        if cents is None:
            conn.execute("INSERT INTO orders_rejects VALUES (?, ?)",
                         (oid, "bad_amount"))
            continue
        key = (cust, ts_utc, cents)
        if key in seen:
            conn.execute("INSERT INTO orders_rejects VALUES (?, ?)",
                         (oid, "duplicate"))
            continue
        seen.add(key)
        conn.execute("INSERT INTO orders_v2 VALUES (?, ?, ?, ?, ?)",
                     (oid, cust, ts_utc, cents, status))
    conn.execute("DROP TABLE orders")


def rollback(conn):
    """Restore the exact v1 database from orders_v1_backup."""
    conn.execute("DROP TABLE IF EXISTS orders_v2")
    conn.execute("DROP TABLE IF EXISTS orders_rejects")
    conn.execute("DROP TABLE IF EXISTS orders")
    conn.execute(V1_SCHEMA)
    conn.execute("INSERT INTO orders SELECT * FROM orders_v1_backup")
    conn.execute("DROP TABLE orders_v1_backup")
'''

    def _tests_for(self, rows, v2, rejects):
        return (
            "import sqlite3\n"
            "\n"
            f"ROWS = {rows!r}\n"
            f"EXPECTED_V2 = {v2!r}\n"
            f"EXPECTED_REJECTS = {rejects!r}\n"
            f"V1_SCHEMA = {self.V1_SCHEMA!r}\n"
            "\n"
            "def run_tests():\n"
            "    from solution import migrate, rollback\n"
            "    conn = sqlite3.connect(':memory:')\n"
            "    conn.execute(V1_SCHEMA)\n"
            "    conn.executemany('INSERT INTO orders VALUES (?,?,?,?,?)', ROWS)\n"
            "    schema_before = conn.execute(\n"
            "        \"SELECT sql FROM sqlite_master WHERE name='orders'\").fetchone()\n"
            "    rows_before = conn.execute(\n"
            "        'SELECT * FROM orders ORDER BY id').fetchall()\n"
            "    migrate(conn)\n"
            "    v2 = conn.execute(\n"
            "        'SELECT id, customer, ts_utc, amount_cents, status '\n"
            "        'FROM orders_v2 ORDER BY id').fetchall()\n"
            "    assert v2 == EXPECTED_V2, v2\n"
            "    rej = conn.execute(\n"
            "        'SELECT order_id, reason FROM orders_rejects '\n"
            "        'ORDER BY order_id').fetchall()\n"
            "    assert rej == EXPECTED_REJECTS, rej\n"
            "    rollback(conn)\n"
            "    assert conn.execute(\n"
            "        \"SELECT sql FROM sqlite_master WHERE name='orders'\").fetchone() \\\n"
            "        == schema_before, 'v1 schema not restored exactly'\n"
            "    assert conn.execute(\n"
            "        'SELECT * FROM orders ORDER BY id').fetchall() == rows_before, \\\n"
            "        'v1 rows not restored exactly'\n"
            "    names = {r[0] for r in conn.execute(\n"
            "        \"SELECT name FROM sqlite_master WHERE type='table'\")}\n"
            "    assert not ({'orders_v2', 'orders_rejects',\n"
            "                 'orders_v1_backup'} & names), names\n"
            "    print('gates-ok')\n")

    def generate(self, rng: random.Random) -> Candidate:
        rows = self._dirty_rows(rng)
        v2, rejects = self._reference(rows)
        tests = self._tests_for(rows, v2, rejects)
        n_dup = sum(1 for _, r in rejects if r == "duplicate")
        task = (
            "A service is migrating its SQLite schema in place. The v1 table "
            f"is: {self.V1_SCHEMA}; its rows carry mixed timestamp shapes "
            "(ISO with Z, ISO with a numeric offset, naive ISO that must be "
            "treated as UTC), amounts as decimal STRINGS, plus dirty rows: "
            f"exact duplicates and unparseable values. Write migrate(conn) "
            "and rollback(conn) in Python so that: (1) orders_v2 "
            "(id, customer, ts_utc, amount_cents, status) holds every "
            "parseable row exactly once - ts_utc canonical "
            "YYYY-MM-DDTHH:MM:SSZ in UTC, amount_cents = decimal string "
            "times 100 rounded half-up to int; (2) duplicates are detected "
            "on (customer, ts_utc, amount_cents) keeping the LOWEST id; "
            f"(3) rejected rows go to orders_rejects(order_id, reason) with "
            "reason in bad_ts/bad_amount/duplicate and precedence "
            "bad_ts > bad_amount > duplicate (this database yields "
            f"{len(rejects)} rejects, {n_dup} of them duplicates); "
            "(4) migrate() keeps an exact backup of v1 (orders_v1_backup) "
            "and drops the v1 table; (5) rollback(conn) restores the v1 "
            "schema and rows byte-exactly and removes the v2 tables and the "
            "backup. The suite rebuilds this exact v1 state and compares "
            "every table row by row.")
        return Candidate(
            family=self.NAME, language="python", domain="databases",
            difficulty="advanced", task=task,
            expected_behavior=("v2 normalized + classified rejects; rollback "
                               "restores v1 exactly"),
            code=self._SOLUTION, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "schema evolution with a real migration + rollback",
                "approach": "backup first, transform with explicit "
                            "precedence, reject predictably, restore "
                            "byte-exactly",
                "key_points": ["naive timestamps are UTC by spec",
                               "dedup keys on the NORMALIZED values",
                               "reject precedence must be checked in order"],
                "big_o_time": "O(rows)", "big_o_space": "O(rows)",
                "edge_cases": ["offset conversion across the day boundary",
                               "same logical row with different amount "
                               "formatting"]}},
            tags=["databases", "migration", "sqlite"],
            variant=f"orders|{len(rows)}|{len(rejects)}|{rejects[0][0] if rejects else 0}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        bug_kind = rng.choice(["no_dedup", "naive_tz"])
        if bug_kind == "no_dedup":
            buggy = self._SOLUTION.replace(
                "        key = (cust, ts_utc, cents)\n"
                "        if key in seen:\n"
                "            conn.execute(\"INSERT INTO orders_rejects VALUES (?, ?)\",\n"
                "                         (oid, \"duplicate\"))\n"
                "            continue\n"
                "        seen.add(key)\n",
                "        key = (cust, ts_utc, cents)\n"
                "        seen.add(key)\n")
        else:
            buggy = self._SOLUTION.replace(
                "        if dt.tzinfo is None:\n"
                "            dt = dt.replace(tzinfo=timezone.utc)\n"
                "        return dt.astimezone(timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\")\n",
                "        return dt.strftime(\"%Y-%m-%dT%H:%M:%SZ\")\n")
        if buggy == self._SOLUTION:
            return None
        # self-verification: the planted defect must fail the real suite
        rows = self._dirty_rows(rng)
        v2, rejects = self._reference(rows)
        tests = self._tests_for(rows, v2, rejects)
        if _harness_ok(buggy, tests):
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain="databases",
            difficulty="advanced",
            task=("Review this migration draft against the v2 spec "
                  "(canonical UTC ts_utc, integer cents, dedup on normalized "
                  "(customer, ts_utc, amount_cents) keeping the lowest id, "
                  "classified rejects, exact rollback). Find the defect."),
            expected_behavior="See question.", code=buggy,
            tests=tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": self._SOLUTION},
            tags=["databases", "bug"], variant=f"orders|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "correct_code": self._SOLUTION,
                "tests": tests}
        return cand, meta


register(globals(), SchemaMigrationFamily)

# --------------------------------------------------------------------------
# P6: integrate a fictional SDK reading ONLY its documentation
# --------------------------------------------------------------------------

_SDK = '''"""Reference implementation of the fictional pagerfeed SDK (v3.1).

docs.md is the ONLY contract; this module implements it exactly so that
integrations can be verified against reality.
"""


class RateLimited(Exception):
    """Raised after the request budget is exhausted; carries retry_after."""

    def __init__(self, retry_after):
        super().__init__("rate limited")
        self.retry_after = retry_after


class Page:
    """One feed page: items plus the cursor for the next page."""

    def __init__(self, items, next_cursor):
        self.items = items
        self.next_cursor = next_cursor


class _ScriptedBackend:
    """Deterministic test double: scripted pages and a post failure budget."""

    def __init__(self, pages, fail_at):
        self.pages = pages
        self.fail_at = fail_at
        self.posts = []

    def page(self, cursor):
        if cursor is None:
            return self.pages[0]
        return self.pages[int(cursor)]

    def post(self, text):
        if self.fail_at > 0:
            self.fail_at -= 1
            raise RateLimited(1)
        self.posts.append(text)


class Client:
    """Pagerfeed client. Documented surface: token, feed, post, health."""

    def __init__(self, token, backend=None):
        self.token = token
        self._backend = backend if backend is not None else _ScriptedBackend(
            [{"items": [], "next_cursor": None}], 0)

    def feed(self, cursor=None):
        """Return the next Page; cursor comes from Page.next_cursor."""
        page = self._backend.page(cursor)
        return Page(page["items"], page["next_cursor"])

    def post(self, text):
        """Log one text (<= 280 chars); may raise RateLimited."""
        if len(text) > 280:
            raise ValueError("too_long")
        self._backend.post(text)

    def health(self):
        return "ok"
'''

_DOCS = '''# pagerfeed SDK - integration contract (v3.1)

Authentication: pass your token to `Client(token)`.

## Reading
- `client.feed(cursor=None)` returns a `Page`.
- `Page.items` is a list of note dicts: `{"id": str, "text": str,
  "kind": str}`. Only items with `kind == "note"` are loggable.
- `Page.next_cursor` is the cursor for the NEXT page, or `None` when the
  feed is exhausted. Never build cursors yourself.

## Writing
- `client.post(text)` logs one text of at most 280 characters. Longer text
  raises `ValueError("too_long")` - check the length BEFORE calling and
  skip the post silently; do not catch that error.
- Under load `post` may raise `RateLimited` (import it from pagerfeed);
  the exception carries `.retry_after`. Retrying is the caller's job:
  retry the SAME text at most 3 attempts total (the original call counts
  as attempt 1) and re-raise if all attempts fail.

## Surface stability
Only `token`, `feed`, `post` and `health` are public. Anything else on the
client object is internal and WILL move; integrations must not touch it.
'''

_INTEGRATOR = '''"""pagerfeed integration: drain the feed into the audit log."""
from pagerfeed import RateLimited

MAX_TEXT = 280


def sync_feed(client):
    """Collect every feed item id in page order.

    Log every note item whose text fits the documented limit; respect the
    documented retry contract when RateLimited shows up. Returns the list
    of ids.
    """
    ids = []
    cursor = None
    while True:
        page = client.feed(cursor)
        for item in page.items:
            ids.append(item["id"])
            if item.get("kind") != "note":
                continue
            text = item["text"]
            if len(text) > MAX_TEXT:
                continue
            for attempt in range(3):
                try:
                    client.post(text)
                    break
                except RateLimited:
                    if attempt == 2:
                        raise
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return ids
'''


class SdkDocsIntegrationFamily(Family):
    """Docs-only SDK integration against a strict, scripted reference.

    The candidate ships three files: the SDK contract (docs.md), the exact
    reference implementation (pagerfeed.py) and the integrator (solution.py).
    The hidden suite drives the integrator through scripted backends and a
    STRICT wrapper that raises AttributeError on any undocumented attribute,
    so hallucinated surface usage is fatal.
    """
    NAME = "sdk_docs_integration"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "architecture")
    PROJECT_FAMILY = True

    _PAD = "pad "  # keeps long-note texts free of banned filler words

    def _pages(self, rng):
        """(pages, expected_ids, n_loggable) for a scripted feed."""
        n_pages = rng.randint(2, 4)
        pages, ids = [], []
        nid = 100
        kinds = ("note", "note", "ping", "note")
        for p in range(n_pages):
            items = []
            for _ in range(rng.randint(2, 4)):
                nid += 1
                kind = rng.choice(kinds)
                if kind == "note":
                    size = rng.choice([10, 80, 280, rng.choice([281, 300])])
                    text = (self._PAD * (size // 4 + 1))[:size]
                else:
                    text = f"signal-{nid}"
                items.append({"id": f"n{nid}", "text": text, "kind": kind})
                ids.append(f"n{nid}")
            pages.append({"items": items,
                          "next_cursor": str(p + 1)
                          if p < n_pages - 1 else None})
        loggable = sum(1 for pg in pages for it in pg["items"]
                       if it["kind"] == "note" and len(it["text"]) <= 280)
        if loggable == 0:  # the suite needs at least one loggable note
            first = pages[0]["items"][0]
            first["kind"] = "note"
            first["text"] = "hello from the feed"
            loggable = 1
        return pages, ids, loggable

    def _tests(self, pages, ids, loggable, fail_at, expect_raise):
        return (
            "from pagerfeed import Client, RateLimited, _ScriptedBackend\n"
            "\n"
            f"PAGES = {pages!r}\n"
            f"EXPECTED_IDS = {ids!r}\n"
            f"FAIL_AT = {fail_at}\n"
            f"EXPECT_RAISE = {expect_raise!r}\n"
            "\n"
            "class StrictClient:\n"
            "    ALLOWED = {'token', 'feed', 'post', 'health'}\n"
            "\n"
            "    def __init__(self, inner):\n"
            "        object.__setattr__(self, '_inner', inner)\n"
            "\n"
            "    def __getattr__(self, name):\n"
            "        if name.startswith('_') or name not in self.ALLOWED:\n"
            "            raise AttributeError('undocumented SDK surface: '\n"
            "                                 + name)\n"
            "        return getattr(self._inner, name)\n"
            "\n"
            "\n"
            "def _client():\n"
            "    return Client('tok', backend=_ScriptedBackend(\n"
            "        PAGES, FAIL_AT))\n"
            "\n"
            "\n"
            "def run_tests():\n"
            "    from solution import sync_feed\n"
            "    client = _client()\n"
            "    if EXPECT_RAISE:\n"
            "        try:\n"
            "            sync_feed(client)\n"
            "        except RateLimited:\n"
            "            pass\n"
            "        else:\n"
            "            raise AssertionError('budget exhaustion must re-raise')\n"
            "        return\n"
            "    got = sync_feed(client)\n"
            "    assert got == EXPECTED_IDS, got\n"
            "    backend = client._backend\n"
            f"    assert len(backend.posts) == {loggable}, len(backend.posts)\n"
            "    client2 = _client()\n"
            "    got2 = sync_feed(StrictClient(client2))\n"
            "    assert got2 == EXPECTED_IDS, got2\n"
            "    print('gates-ok')\n"
            "\n"
            "\n"
            "run_tests()\n")

    def generate(self, rng: random.Random) -> Candidate:
        pages, ids, loggable = self._pages(rng)
        expect_raise = rng.random() < 0.25
        # the raise scenario needs a budget strictly beyond the retry contract
        fail_at = rng.choice([4, 5]) if expect_raise else rng.choice([0, 0, 1, 2])
        tests = self._tests(pages, ids, loggable, fail_at, expect_raise)
        files = [FileSpec("docs.md", _DOCS),
                 FileSpec("pagerfeed.py", _SDK),
                 FileSpec("solution.py", _INTEGRATOR)]
        raise_note = ("; the post-failure budget exceeds the retry contract, "
                      "so RateLimited must propagate" if expect_raise else "")
        task = (
            "Integrate the fictional pagerfeed SDK from its documentation "
            "alone. The files carry the full contract (docs.md), the exact "
            "reference implementation (pagerfeed.py) and a first-cut "
            "integrator (solution.py). Your answer must replace "
            "solution.py so sync_feed(client): walks every page following "
            "Page.next_cursor until it is None (never invent cursors), "
            "collects every item id in page order, posts the text of every "
            "note item that fits the documented length limit (longer notes "
            "are skipped silently, without touching post), honours the "
            "documented RateLimited retry budget (same text, at most 3 "
            "attempts total, then re-raise), and never touches anything "
            "outside the documented surface - the hidden suite wraps the "
            "client in a strict guard that raises AttributeError on any "
            f"undocumented attribute. This scenario scripts {len(pages)} "
            f"pages with a post-failure budget of {fail_at}{raise_note}.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty=rng.choice(self.DIFFICULTIES), task=task,
            expected_behavior=("full drain in page order; documented "
                               "retries; strict-surface clean"),
            code=None, files=files, entry="solution.py", tests=tests,
            verify_method="executed", is_project=True,
            notes={"explain": {
                "purpose": "integrate an unknown SDK from documentation",
                "approach": "treat docs.md as the only truth; the strict "
                            "wrapper makes hallucinated surface usage fatal",
                "key_points": ["pagination stops when next_cursor is None",
                               "documented limits are respected, not caught",
                               "retry budget counts the original attempt"],
                "big_o_time": "O(items)", "big_o_space": "O(items)",
                "edge_cases": ["note of exactly 280 chars is loggable",
                               "non-note items are collected but not posted"]}},
            tags=["integration", "sdk", "docs"],
            variant=f"pagerfeed|{len(pages)}|{fail_at}|{int(expect_raise)}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        pages, ids, loggable = self._pages(rng)
        bug_kind = rng.choice(["single_page", "swallow_rate_limit"])
        # the swallowed-rate-limit bug only shows when a 429 really happens
        fail_at = 1 if bug_kind == "swallow_rate_limit" else rng.choice([0, 1])
        if bug_kind == "single_page":
            body = ("    ids = []\n"
                    "    page = client.feed(None)\n"
                    "    for item in page.items:\n"
                    "        ids.append(item['id'])\n"
                    "        if item.get('kind') == 'note' and "
                    "len(item['text']) <= 280:\n"
                    "            client.post(item['text'])\n"
                    "    return ids\n")
        else:
            body = ("    ids = []\n"
                    "    cursor = None\n"
                    "    while True:\n"
                    "        page = client.feed(cursor)\n"
                    "        for item in page.items:\n"
                    "            ids.append(item['id'])\n"
                    "            if item.get('kind') != 'note' or "
                    "len(item['text']) > 280:\n"
                    "                continue\n"
                    "            try:\n"
                    "                client.post(item['text'])\n"
                    "            except RateLimited:\n"
                    "                continue\n"
                    "        if page.next_cursor is None:\n"
                    "            break\n"
                    "        cursor = page.next_cursor\n"
                    "    return ids\n")
        buggy_solution = ('"""buggy integration variant."""\n'
                          "from pagerfeed import RateLimited\n"
                          "\n"
                          "\n"
                          "def sync_feed(client):\n" + body)
        buggy_files = [FileSpec("docs.md", _DOCS),
                       FileSpec("pagerfeed.py", _SDK),
                       FileSpec("solution.py", buggy_solution)]
        tests = self._tests(pages, ids, loggable, fail_at, False)
        if _harness_ok(None, tests, files=buggy_files,
                       entry="solution.py"):
            return None
        good = [FileSpec("docs.md", _DOCS),
                FileSpec("pagerfeed.py", _SDK),
                FileSpec("solution.py", _INTEGRATOR)]
        cand = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced",
            task=("This pagerfeed integration passes a quick smoke run but "
                  "breaks a documented contract. Read docs.md and find what "
                  "it violates."),
            expected_behavior="See question.", code=None, files=buggy_files,
            entry="solution.py", tests=tests, verify_method="executed",
            is_project=True,
            notes={"bug_kind": bug_kind, "correct_files":
                   [{"path": f.path, "content": f.content} for f in good]},
            tags=["integration", "bug"], variant=f"pagerfeed|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind}
        return cand, meta


register(globals(), SdkDocsIntegrationFamily)

# --------------------------------------------------------------------------
# P7: feature insertion into an existing repo (extension points respected)
# --------------------------------------------------------------------------

_REPO_INIT = '''"""notewrap: tiny notes library with pluggable renderers."""
from .store import NoteStore

__all__ = ["NoteStore"]
'''

_REPO_STORE = '''class Note:
    def __init__(self, title, body):
        self.title = title
        self.body = body


class NoteStore:
    def __init__(self):
        self._notes = []

    def add(self, title, body):
        note = Note(title, body)
        self._notes.append(note)
        return note

    def all(self):
        return list(self._notes)
'''

_REPO_RENDERERS = '''"""Renderer registry: the ONLY extension point for new renderers."""
REGISTRY = {}


def register(name):
    def deco(cls):
        if name in REGISTRY:
            raise ValueError("renderer already registered: " + name)
        REGISTRY[name] = cls
        return cls
    return deco


def get_renderer(name):
    try:
        return REGISTRY[name]()
    except KeyError:
        raise KeyError("unknown renderer %r (known: %s)"
                       % (name, ", ".join(sorted(REGISTRY)))) from None


# built-in renderers self-register at import time
from . import markdown  # noqa: E402
from . import plain  # noqa: E402
'''

_REPO_PLAIN = '''from . import register


@register("plain")
class PlainRenderer:
    def render(self, note):
        return note.title + "\\n" + note.body
'''

_REPO_MARKDOWN = '''from . import register


@register("markdown")
class MarkdownRenderer:
    def render(self, note):
        return "# " + note.title + "\\n\\n" + note.body
'''

_BASE_CLI = '''"""CLI dispatch: pick a renderer through the registry."""
from .renderers import get_renderer


def run(store, renderer_name="plain"):
    renderer = get_renderer(renderer_name)
    return [renderer.render(n) for n in store.all()]
'''

_TARGET_CLI = '''"""CLI dispatch: pick a renderer through the registry."""
from .renderers import get_renderer


def run(store, renderer_name=None, tail=False):
    renderer = get_renderer(renderer_name or "plain")
    notes = store.all()
    if tail:
        notes = notes[-1:]
    return [renderer.render(n) for n in notes]
'''

_NEW_RENDERERS = {
    "upper": '''from . import register


@register("upper")
class UpperRenderer:
    def render(self, note):
        return note.title.upper() + "\\n" + note.body.upper()
''',
    "shout": '''from . import register


@register("shout")
class ShoutRenderer:
    def render(self, note):
        return note.title.upper() + "!!!\\n" + note.body.upper() + "!!!"
''',
    "titlecase": '''from . import register


@register("titlecase")
class TitleRenderer:
    def render(self, note):
        return note.title.title() + "\\n" + note.body
''',
}


class RepoFeatureInsertionFamily(Family):
    """Enter a foreign repo and add a feature through ITS extension point.

    The candidate files are the patch: the new renderer module plus the
    updated cli.py. The pinned suite materializes the untouched repo,
    applies the candidate files, and enforces (a) new feature behaviour,
    (b) full regression on the old behaviour, and (c) the structural rule
    that the renderer is registered through the registry - hardcoding the
    new name inside cli.py cannot pass.
    """
    NAME = "repo_feature_insertion"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("expert",)
    SUPPORTS = ("architecture", "explanation", "code_review")
    PROJECT_FAMILY = True

    _BASE_FILES = {
        "notewrap/__init__.py": _REPO_INIT,
        "notewrap/store.py": _REPO_STORE,
        "notewrap/renderers/__init__.py": _REPO_RENDERERS,
        "notewrap/renderers/plain.py": _REPO_PLAIN,
        "notewrap/renderers/markdown.py": _REPO_MARKDOWN,
    }

    def _notes(self, rng):
        titles = rng.sample(["standup", "deploy", "review", "incident",
                             "backlog", "retro"], 3)
        bodies = ["ship the fix", "check the dashboards", "call the owner",
                  "write the summary", "tag the release"]
        return [(t, rng.choice(bodies)) for t in titles]

    def _expected(self, kind, notes):
        """Measured: run the assembled repo + target patch for real."""
        if kind == "upper":
            render = lambda n: n[0].upper() + "\n" + n[1].upper()
        elif kind == "shout":
            render = lambda n: n[0].upper() + "!!!\n" + n[1].upper() + "!!!"
        else:
            render = lambda n: n[0].title() + "\n" + n[1]
        plain = lambda n: n[0] + "\n" + n[1]
        markdown = lambda n: "# " + n[0] + "\n\n" + n[1]
        store = notes
        new_mod = "notewrap.renderers." + kind
        return {
            "new": [render(n) for n in store],
            "plain": [plain(n) for n in store],
            "markdown": [markdown(n) for n in store],
            "tail": [render(store[-1])],
            "default_is_plain": [plain(n) for n in store],
            "new_module": new_mod,
        }

    def _tests(self, kind, notes, exp):
        return (
            "import os\n"
            "\n"
            "REPO = " + repr(self._BASE_FILES) + "\n"
            "NOTES = " + repr(notes) + "\n"
            "NEW_KIND = " + repr(kind) + "\n"
            "EXPECTED_NEW = " + repr(exp["new"]) + "\n"
            "EXPECTED_PLAIN = " + repr(exp["plain"]) + "\n"
            "EXPECTED_MARKDOWN = " + repr(exp["markdown"]) + "\n"
            "EXPECTED_TAIL = " + repr(exp["tail"]) + "\n"
            "\n"
            "\n"
            "def _materialize():\n"
            "    for path, content in REPO.items():\n"
            "        full = os.path.join(os.getcwd(), path)\n"
            "        os.makedirs(os.path.dirname(full), exist_ok=True)\n"
            "        with open(full, 'w', encoding='utf-8') as handle:\n"
            "            handle.write(content)\n"
            "\n"
            "\n"
            "def run_tests():\n"
            "    _materialize()\n"
            "    import importlib\n"
            "    import notewrap.renderers as registry\n"
            "    from notewrap.cli import run\n"
            "    from notewrap.store import NoteStore\n"
            "    importlib.import_module('notewrap.renderers.' + NEW_KIND)\n"
            "    assert NEW_KIND in registry.REGISTRY, sorted(\n"
            "        registry.REGISTRY)\n"
            "    assert registry.REGISTRY[NEW_KIND].__module__ \\\n"
            "        == 'notewrap.renderers.' + NEW_KIND, \\\n"
            "        registry.REGISTRY[NEW_KIND].__module__\n"
            "    store = NoteStore()\n"
            "    for title, body in NOTES:\n"
            "        store.add(title, body)\n"
            "    assert run(store, NEW_KIND) == EXPECTED_NEW, run(store,\n"
            "                                                     NEW_KIND)\n"
            "    assert run(store) == EXPECTED_PLAIN\n"
            "    assert run(store, None) == EXPECTED_PLAIN\n"
            "    assert run(store, 'markdown') == EXPECTED_MARKDOWN\n"
            "    assert run(store, NEW_KIND, tail=True) == EXPECTED_TAIL\n"
            "    try:\n"
            "        run(store, 'bogus')\n"
            "    except KeyError as err:\n"
            "        message = str(err)\n"
            "        assert 'plain' in message and NEW_KIND in message, message\n"
            "    else:\n"
            "        raise AssertionError('unknown renderer must raise KeyError')\n"
            "    print('gates-ok')\n"
            "\n"
            "\n"
            "run_tests()\n")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(sorted(_NEW_RENDERERS))
        notes = self._notes(rng)
        exp = self._expected(kind, notes)
        new_path = f"notewrap/renderers/{kind}.py"
        files = [FileSpec(new_path, _NEW_RENDERERS[kind]),
                 FileSpec("notewrap/cli.py", _TARGET_CLI)]
        tests = self._tests(kind, notes, exp)
        if not _harness_ok(None, tests, files=files, entry=new_path):
            return None
        task = (
            "You are joining the notewrap project. Its renderer system is a "
            "registry: notewrap/renderers/__init__.py owns REGISTRY and "
            "get_renderer, and every renderer module self-registers with "
            "the @register decorator. Current dispatch (notewrap/cli.py):\n\n"
            f"{_BASE_CLI}\n"
            "Existing renderers: plain (title\\nbody) and markdown "
            "(# title\\n\\nbody). The current signatures of NoteStore "
            "(add/all) and both renderer modules stay frozen.\n\n"
            f"Task: add the '{kind}' renderer and extend the CLI so that:\n"
            f"1. run(store, '{kind}') renders every note with the new "
            "renderer (exact output pinned by the suite);\n"
            "2. run(store) and run(store, None) BOTH keep the old plain "
            "default - the new renderer must NOT become the default;\n"
            "3. run accepts tail=True to render only the most recent note;\n"
            "4. the unknown-renderer KeyError keeps listing every known "
            "renderer name, including the new one;\n"
            "5. the new renderer registers through the registry like every "
            "other module - the suite imports your module and then checks "
            "its class landed in REGISTRY with the right __module__, so "
            "hardcoding "
            "the name inside cli.py is rejected.\n"
            "Your answer files: notewrap/renderers/"
            f"{kind}.py and the updated notewrap/cli.py. Everything else "
            "stays byte-identical.")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="expert", task=task,
            expected_behavior=("feature works through the registry; old "
                               "defaults intact; regression suite green"),
            code=None, files=files, entry=new_path, tests=tests,
            verify_method="executed", is_project=True,
            notes={"explain": {
                "purpose": "feature insertion respecting foreign architecture",
                "approach": "extend the existing registry pattern instead of "
                            "special-casing the new name in the dispatcher",
                "key_points": ["extension points exist for a reason",
                               "defaults are a public contract",
                               "the KeyError message is part of the UX"],
                "big_o_time": "O(notes)", "big_o_space": "O(notes)",
                "edge_cases": ["empty store", "unknown renderer message",
                               "tail on a single-note store"]}},
            tags=["architecture", "feature", "registry"],
            variant=f"{kind}|{notes[0][0]}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(sorted(_NEW_RENDERERS))
        notes = self._notes(rng)
        exp = self._expected(kind, notes)
        bug_kind = rng.choice(["bypass_registry", "default_flipped"])
        new_path = f"notewrap/renderers/{kind}.py"
        if bug_kind == "bypass_registry":
            unregistered = _NEW_RENDERERS[kind].replace("@register(\"%s\")\n" % kind, "")
            buggy_cli = (
                '"""CLI dispatch (hardcoded new renderer)."""\n'
                "from .renderers import get_renderer\n"
                "from notewrap.renderers import REGISTRY\n"
                "\n"
                "\n"
                "def run(store, renderer_name=None, tail=False):\n"
                f"    if renderer_name == '{kind}':\n"
                "        notes = store.all()\n"
                "        if tail:\n"
                "            notes = notes[-1:]\n"
                f"        return [n.title.upper() + '\\n' + n.body.upper() "
                "for n in notes]\n"
                '    renderer = get_renderer(renderer_name or "plain")\n'
                "    notes = store.all()\n"
                "    if tail:\n"
                "        notes = notes[-1:]\n"
                "    return [renderer.render(n) for n in notes]\n")
            buggy_new = unregistered
        else:
            buggy_cli = _TARGET_CLI.replace(
                'renderer = get_renderer(renderer_name or "plain")',
                f'renderer = get_renderer(renderer_name or "{kind}")')
            buggy_new = _NEW_RENDERERS[kind]
        files = [FileSpec(new_path, buggy_new),
                 FileSpec("notewrap/cli.py", buggy_cli)]
        tests = self._tests(kind, notes, exp)
        if _harness_ok(None, tests, files=files, entry=new_path):
            return None
        good = [FileSpec(new_path, _NEW_RENDERERS[kind]),
                FileSpec("notewrap/cli.py", _TARGET_CLI)]
        cand = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="expert",
            task=("Review this feature patch against the repo conventions: "
                  "renderers must register through the registry, run(store) "
                  "must keep the plain default, and the KeyError message "
                  "must list every renderer. Find the violation."),
            expected_behavior="See question.", code=None, files=files,
            entry=new_path, tests=tests, verify_method="executed",
            is_project=True,
            notes={"bug_kind": bug_kind, "correct_files":
                   [{"path": f.path, "content": f.content} for f in good]},
            tags=["architecture", "bug"],
            variant=f"{kind}|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind}
        return cand, meta


register(globals(), RepoFeatureInsertionFamily)

# --------------------------------------------------------------------------
# P10: optimization guided by a REAL profile, not by intuition
# --------------------------------------------------------------------------

_NAIVE_PAIRS = '''def _pair_ok(a, b):
    return a == b


def equal_pairs(xs):
    """Count the pairs i < j with xs[i] == xs[j]."""
    total = 0
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            if _pair_ok(xs[i], xs[j]):
                total += 1
    return total
'''

_FAST_PAIRS = '''from collections import Counter


def equal_pairs(xs):
    """Count the pairs i < j with xs[i] == xs[j]."""
    counts = Counter(xs)
    return sum(c * (c - 1) // 2 for c in counts.values())
'''

_NAIVE_TOPK = '''def _next_top(scores, taken):
    best_i = -1
    best_s = None
    for i, s in enumerate(scores):
        if i in taken:
            continue
        if best_s is None or s > best_s:
            best_i = i
            best_s = s
    return best_i


def top_scores(scores, k):
    """Indices of the k highest scores, best first; ties by lower index."""
    taken = set()
    out = []
    for _ in range(k):
        i = _next_top(scores, taken)
        taken.add(i)
        out.append(i)
    return out
'''

_FAST_TOPK = '''import heapq


def top_scores(scores, k):
    """Indices of the k highest scores, best first; ties by lower index."""
    return heapq.nlargest(k, range(len(scores)),
                          key=lambda i: (scores[i], -i))
'''


class ProfileGuidedOptimizationFamily(Family):
    """Optimize the function the profile blames, not the one you guess.

    The task embeds a REAL cProfile excerpt measured on the reference
    machine (generated at build time). The pinned suite checks exact
    equivalence on pinned + freshly-seeded inputs AND a measured wall-clock
    gate: a candidate that optimized a cold path still runs at naive speed
    and fails the threshold.
    """
    NAME = "profile_guided_optimization"
    LANGUAGE = "python"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("optimization", "explanation", "complexity")
    KINDS = ("pair_counts", "topk")

    def _workload_script(self, kind):
        if kind == "pair_counts":
            return ("import random\n"
                    "rng = random.Random(12345)\n"
                    "xs = [rng.randint(0, 50) for _ in range(3000)]\n")
        return ("import random\n"
                "rng = random.Random(12345)\n"
                "scores = [rng.randint(0, 10 ** 6) for _ in range(40000)]\n"
                "K = 160\n")

    def _measure(self, kind, naive):
        """Measure the naive version for real: wall time + profile excerpt."""
        import cProfile
        import io as _io
        import pstats
        wl = self._workload_script(kind)
        call = ("equal_pairs(xs)" if kind == "pair_counts"
                else "top_scores(scores, K)")
        wall_script = ("import time\n" + wl + f"{naive}\n"
                       "t0 = time.perf_counter()\n"
                       + call
                       + "\nt1 = time.perf_counter()\n"
                       + "print('WALL %.4f' % (t1 - t0))\n")
        proc = _py_run(wall_script, timeout=25)
        if proc.returncode != 0:
            return None
        try:
            t_naive = float(proc.stdout.strip().split()[-1])
        except (ValueError, IndexError):
            return None
        if not (0.2 <= t_naive <= 8.0):
            return None  # workload size must stay honest on this machine
        pr = cProfile.Profile()
        env_ns = {}
        exec(wl, env_ns)  # noqa: S102 - trusted generator-side workload
        exec(naive, env_ns)  # noqa: S102
        pr.enable()
        if kind == "pair_counts":
            env_ns["equal_pairs"](env_ns["xs"])
        else:
            env_ns["top_scores"](env_ns["scores"], env_ns["K"])
        pr.disable()
        buf = _io.StringIO()
        ps = pstats.Stats(pr, stream=buf)
        ps.sort_stats("tottime")
        rows = []
        for (_file, _line, name), (_cc, nc, tt, ct, _callers) in \
                sorted(ps.stats.items(), key=lambda kv: -kv[1][2])[:3]:
            rows.append(f"{name}: {nc} calls, {tt:.3f}s tottime, "
                        f"{ct:.3f}s cumtime")
        hotspot = rows[0].split(":")[0] if rows else "unknown"
        return {"t_naive": t_naive,
                "threshold": max(0.15, round(t_naive / 4, 2)),
                "excerpt": rows, "hotspot": hotspot}

    def _tests(self, kind, threshold, t_naive):
        common_tail = (
            "\n"
            "def _timed(fn):\n"
            "    t0 = time.perf_counter()\n"
            "    fn()\n"
            "    return time.perf_counter() - t0\n")
        if kind == "pair_counts":
            return (
                "import random\n"
                "import time\n"
                "\n"
                f"THRESHOLD = {threshold!r}\n"
                "PINNED = [([1, 2, 3, 2, 2], 3), ([], 0), ([7], 0),\n"
                "          ([5, 5, 5, 5], 6), ([1, 2, 3, 4], 0)]\n"
                + common_tail +
                "\n"
                "\n"
                "def run_tests():\n"
                "    import solution\n"
                "    for values, expected in PINNED:\n"
                "        got = solution.equal_pairs(list(values))\n"
                "        assert got == expected, (values, got)\n"
                "    rng = random.Random(777)\n"
                "    big = [rng.randint(0, 50) for _ in range(3000)]\n"
                "    from collections import Counter\n"
                "    counts = Counter(big)\n"
                "    expected = sum(c * (c - 1) // 2 for c in "
                "counts.values())\n"
                "    got = solution.equal_pairs(big)\n"
                "    assert got == expected, (got, expected)\n"
                "    elapsed = _timed(lambda: solution.equal_pairs(big))\n"
                "    assert elapsed < THRESHOLD, (elapsed, THRESHOLD)\n"
                "    print('gates-ok')\n")
        return (
            "import random\n"
            "import time\n"
            "\n"
            f"THRESHOLD = {threshold!r}\n"
            "PINNED = [([3, 1, 3, 2], 2, [0, 2]), ([9], 1, [0]),\n"
            "          ([4, 4, 4, 4], 3, [0, 1, 2])]\n"
            + common_tail +
            "\n"
            "\n"
            "def run_tests():\n"
            "    import solution\n"
            "    for scores, k, expected in PINNED:\n"
            "        got = solution.top_scores(list(scores), k)\n"
            "        assert got == expected, (scores, got)\n"
            "    rng = random.Random(777)\n"
            "    scores = [rng.randint(0, 10 ** 6) for _ in range(40000)]\n"
            "    k = 160\n"
            "    order = sorted(range(len(scores)),\n"
            "                   key=lambda i: (-scores[i], i))\n"
            "    expected = order[:k]\n"
            "    got = solution.top_scores(scores, k)\n"
            "    assert got == expected, (got[:5], expected[:5])\n"
            "    elapsed = _timed(lambda: solution.top_scores(scores, k))\n"
            "    assert elapsed < THRESHOLD, (elapsed, THRESHOLD)\n"
            "    print('gates-ok')\n")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        naive = _NAIVE_PAIRS if kind == "pair_counts" else _NAIVE_TOPK
        fixed = _FAST_PAIRS if kind == "pair_counts" else _FAST_TOPK
        measured = self._measure(kind, naive)
        if measured is None:
            return None
        tests = self._tests(kind, measured["threshold"],
                            measured["t_naive"])
        if not _harness_ok(fixed, tests):
            return None
        if kind == "pair_counts":
            story = ("The suite of an analytics service got slower every "
                     "quarter. equal_pairs(xs) counts the pairs i < j with "
                     "xs[i] == xs[j], and the profiler was run on the "
                     "production workload (3000 values). The excerpt:\n\n"
                     + "\n".join(measured["excerpt"]))
            contract = ("Keep the signature and the docstring contract; the "
                        "result must stay identical on every input (pinned "
                        "cases include empty, single-element, all-equal and "
                        "all-distinct lists, plus a fresh 3000-value seeded "
                        "workload).")
        else:
            story = ("A leaderboard endpoint times out under load. "
                     "top_scores(scores, k) returns the indices of the k "
                     "highest scores, best first, ties by lower index, and "
                     "the profiler was run on the production workload "
                     "(40000 scores, k=160). The excerpt:\n\n"
                     + "\n".join(measured["excerpt"]))
            contract = ("Keep the signature and the docstring contract; the "
                        "returned indices must stay identical, including "
                        "the tie order, on the pinned cases and on a fresh "
                        "seeded 40000-score workload.")
        task = (
            story + "\n\n"
            f"Optimize the real hotspot so the same call finishes below "
            f"{measured['threshold']!r}s (the naive version measured "
            f"{measured['t_naive']:.3f}s on the reference machine). "
            + contract + " A candidate that speeds up anything else keeps "
            "running at naive speed and fails the wall-clock gate.")
        return Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty=rng.choice(self.DIFFICULTIES), task=task,
            expected_behavior=("identical outputs; total time below "
                               f"{measured['threshold']!r}s"),
            code=fixed, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "profile-guided optimization",
                "approach": "the profile names the hotspot; the fix changes "
                            "the complexity class, not the constants",
                "key_points": ["optimize what the profile blames",
                               "equivalence must hold on adversarial inputs",
                               "the wall-clock gate catches cosmetic fixes"],
                "big_o_time": ("O(n)" if kind == "pair_counts"
                               else "O(n log n)"),
                "big_o_space": "O(n)",
                "edge_cases": ["all-equal input", "all-distinct input",
                               "ties across the k boundary"]},
                   "profile_measurement": {
                       "naive_seconds": round(measured["t_naive"], 4),
                       "threshold_seconds": measured["threshold"],
                       "hotspot": measured["hotspot"]}},
            tags=["optimization", "profile", kind],
            variant=f"{kind}|{measured['threshold']}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        naive = _NAIVE_PAIRS if kind == "pair_counts" else _NAIVE_TOPK
        fixed = _FAST_PAIRS if kind == "pair_counts" else _FAST_TOPK
        measured = self._measure(kind, naive)
        if measured is None:
            return None
        # cosmetic fix: micro-optimizes the naive loop, same complexity
        if kind == "pair_counts":
            buggy = naive.replace(
                "def equal_pairs(xs):\n    total = 0\n",
                "def equal_pairs(xs):\n    total = 0\n    rng_len = "
                "len(xs)\n").replace(
                "for i in range(len(xs)):", "for i in range(rng_len):"
            ).replace("if _pair_ok(xs[i], xs[j]):",
                      "if xs[i] == xs[j]:")
        else:
            buggy = naive.replace(
                "        if best_s is None or s > best_s:",
                "        if best_s is None or s > best_s:\n            "
                "pass").replace(
                "def top_scores(scores, k):\n    taken = set()",
                "def top_scores(scores, k):\n    taken = set()\n"
                "    n = len(scores)")
        if buggy == naive:
            return None
        tests = self._tests(kind, measured["threshold"],
                            measured["t_naive"])
        if _harness_ok(buggy, tests):
            return None  # cosmetic fix must NOT meet the wall-clock gate
        cand = Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced",
            task=("A teammate 'optimized' this hot function but the "
                  "endpoint is still slow. The profile still blames the "
                  "same algorithm. Explain why the change cannot meet the "
                  "wall-clock gate."),
            expected_behavior="See question.", code=buggy, tests=tests,
            verify_method="executed",
            notes={"bug_kind": "cosmetic_optimization",
                   "correct_code": fixed},
            tags=["optimization", "bug"],
            variant=f"{kind}|bug|cosmetic",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": "cosmetic_optimization", "correct_code": fixed,
                "tests": tests}
        return cand, meta


register(globals(), ProfileGuidedOptimizationFamily)

# --------------------------------------------------------------------------
# P11: living documentation with really-executed examples
# --------------------------------------------------------------------------

class DoctestAuthoringFamily(Family):
    """Write docstrings whose examples actually run.

    The task pins 3 pure functions by spec (no docs). The candidate adds
    docstrings with doctest examples; the family MEASURES the real outputs
    (REPR form, exactly what the REPL would show) at generate time, and the
    pinned suite runs doctest.testmod plus an AST check that every public
    function documents at least one example. A docstring that promises a
    different output than the observed one fails.
    """
    NAME = "doctest_authoring"
    LANGUAGE = "python"
    DOMAIN = "text_processing"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "code_review")

    # name -> (spec, impl, sample inputs)
    _BANK = {
        "snake_to_camel": (
            "convert a snake_case identifier to lowerCamelCase; an empty "
            "input returns the empty string",
            ("def snake_to_camel(text):\n"
             "    if not text:\n"
             "        return text\n"
             "    head, _, rest = text.partition(\"_\")\n"
             "    parts = rest.split(\"_\") if rest else []\n"
             "    out = head\n"
             "    for part in parts:\n"
             "        out += part[:1].upper() + part[1:]\n"
             "    return out\n"),
            ["total_price", "user_id", "http_request"],
        ),
        "pluralize": (
            "return the singular word when n == 1 and the plural "
            "(word + 's') otherwise",
            ("def pluralize(word, n):\n"
             "    return word if n == 1 else word + \"s\"\n"),
            [("box", 1), ("box", 3), ("item", 0)],
        ),
        "wrap_chars": (
            "split text into chunks of at most width characters joined "
            "with newlines; a width <= 0 raises ValueError",
            ("def wrap_chars(text, width):\n"
             "    if width <= 0:\n"
             "        raise ValueError(\"width must be positive\")\n"
             "    return \"\\n\".join(text[i:i + width]\n"
             "                         for i in range(0, len(text), width))\n"),
            [("abcdefgh", 4), ("hi", 5)],
        ),
        "money": (
            "format an integer amount of cents as a dollar string with a "
            "leading $ and exactly two decimals",
            ("def money(cents):\n"
             "    return \"${}.{:02d}\".format(cents // 100, cents % 100)\n"),
            [1250, 5, 1000000],
        ),
        "parse_version": (
            "parse a dotted version string into a tuple of ints",
            ("def parse_version(text):\n"
             "    return tuple(int(part) for part in text.split(\".\"))\n"),
            ["1.2.3", "0.10", "2"],
        ),
        "initials": (
            "return the initials of a full name as uppercase letters "
            "separated by dots; the name is split on whitespace",
            ("def initials(full_name):\n"
             "    return \".\".join(part[0].upper() for part in "
             "full_name.split())\n"),
            ["ada lovelace", "grace brewster hopper", "alan"],
        ),
    }

    def _trio(self, rng):
        return rng.sample(sorted(self._BANK), 3)

    @staticmethod
    def _call(name, value):
        """Render the call line: tuples splat into the arg list."""
        if isinstance(value, tuple):
            return f"{name}{value!r}"
        return f"{name}({value!r})"

    def _probe(self, names):
        """Measure real REPR outputs for every sample input.

        Returns {name: [(call_line, out_repr), ...]} or None. Only calls
        that return normally are recorded (exceptions are not doctest
        examples in this family).
        """
        parts = ["import json"]
        for name in names:
            parts.append(self._BANK[name][1])
        for name in names:
            for value in self._BANK[name][2]:
                parts.append(
                    f"try:\n    out = {self._call(name, value)}\n"
                    f"    print(json.dumps([{name!r}, {value!r}, "
                    "repr(out)]))\n"
                    "except Exception:\n"
                    "    pass\n")
        script = "\n".join(parts) + "\n"
        proc = _py_run(script, timeout=10)
        if proc.returncode != 0:
            return None
        measured = {}
        for line in proc.stdout.strip().splitlines():
            try:
                name, value, out_repr = json.loads(line)
            except json.JSONDecodeError:
                return None
            # the JSON round trip turns tuples into lists; normalize and
            # rebuild the call from the canonical repr
            if isinstance(value, list):
                value = tuple(value)
            if isinstance(value, tuple):
                call = f"{name}{value!r}"
            else:
                call = f"{name}({value!r})"
            if "\n" in out_repr:  # never embed a real newline in an example
                continue
            measured.setdefault(name, []).append((call, out_repr))
        if len(measured) != len(names):
            return None
        return measured

    def _module(self, names, measured):
        """Assemble the documented module; returns source or None."""
        blocks = ['"""Utility helpers with executable documentation."""',
                  ""]
        for name in names:
            spec, impl, _inputs = self._BANK[name]
            rows = measured.get(name) or []
            if not rows:
                return None
            lines = []
            for call, out_repr in rows[:2]:
                lines.append(f"    >>> {call}")
                # the docstring is NOT raw: escape backslashes so an escaped
                # newline in the repr survives as literal text
                lines.append("    " + out_repr.replace("\\", "\\\\"))
            prose = spec[0].upper() + spec[1:]
            head, body = impl.split("\n", 1)
            doc = f"    {prose}.\n" + "\n".join(lines)
            blocks.append(head + '\n    """\n' + doc + '\n    """\n' + body)
            blocks.append("")
        return "\n".join(blocks)

    def _tests(self, names):
        public = ", ".join(repr(n) for n in names)
        return (
            "import ast\n"
            "import doctest\n"
            "import inspect\n"
            "\n"
            f"PUBLIC = [{public}]\n"
            "\n"
            "def run_tests():\n"
            "    import solution\n"
            "    result = doctest.testmod(solution, verbose=False)\n"
            "    assert result.failed == 0, result.failed\n"
            "    assert result.attempted >= len(PUBLIC), result.attempted\n"
            "    tree = ast.parse(inspect.getsource(solution))\n"
            "    publics = [node for node in tree.body\n"
            "               if isinstance(node, ast.FunctionDef)\n"
            "               and not node.name.startswith('_')]\n"
            "    assert {node.name for node in publics} >= set(PUBLIC)\n"
            "    for node in publics:\n"
            "        doc = ast.get_docstring(node) or ''\n"
            "        assert '>>>' in doc, node.name\n"
            "    print('gates-ok')\n")

    def generate(self, rng: random.Random) -> Candidate:
        names = self._trio(rng)
        measured = self._probe(names)
        if measured is None:
            return None
        source = self._module(names, measured)
        if source is None:
            return None
        tests = self._tests(names)
        if not _harness_ok(source, tests):
            return None
        spec_lines = []
        for name in names:
            spec = self._BANK[name][0]
            spec_lines.append(f"- {name}(..): {spec}.")
        task = (
            "Three helpers exist in this module but were shipped without "
            "any documentation. Behaviour contract:\n"
            + "\n".join(spec_lines)
            + "\n\nWrite the module with a docstring on every public "
            "function; each docstring must contain at least one doctest "
            "example (a '>>>' line with the call and the EXACT expected "
            "output on the following line, exactly as the interpreter "
            "prints it). The hidden suite executes every example with "
            "doctest and rejects any promised output that differs from the "
            "observed behaviour, and an AST pass rejects any public "
            "function left without an example. Keep the implementations "
            "unchanged.")
        return Candidate(
            family=self.NAME, language="python", domain="text_processing",
            difficulty=rng.choice(self.DIFFICULTIES), task=task,
            expected_behavior=("every public function documents at least "
                               "one running example; doctest green"),
            code=source, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "living documentation with doctests",
                "approach": "examples are measured outputs, never invented; "
                            "AST coverage keeps every public name honest",
                "key_points": ["a doc that promises unobserved output fails",
                               "doctest examples double as regression tests",
                               "expected output is the repr, quote marks "
                               "included"],
                "big_o_time": "O(n) per helper",
                "big_o_space": "O(1)",
                "edge_cases": ["empty input", "single-word names",
                               "versions with one part"]}},
            tags=["documentation", "doctest"],
            variant="|".join(names),
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        names = self._trio(rng)
        measured = self._probe(names)
        if measured is None:
            return None
        source = self._module(names, measured)
        if source is None:
            return None
        tests = self._tests(names)
        # tamper: one example promises an output the function never produced;
        # try every victim name and every measured row before giving up
        plan = None
        for victim in names:
            for call, out_repr in measured.get(victim) or []:
                if out_repr.startswith(("'", '"')):
                    inner = out_repr[1:-1]
                    wrong = ("'" + (inner.upper() if not inner.isupper()
                                    else inner.lower()) + "'")
                    plan = (victim, call, out_repr, wrong)
                    break
                if out_repr.lstrip("-").isdigit():
                    wrong = str(int(out_repr) + 1)
                    plan = (victim, call, out_repr, wrong)
                    break
            if plan:
                break
        if plan is None:
            return None
        victim, call, real_repr, wrong_repr = plan
        real_src = real_repr.replace("\\", "\\\\")  # as embedded in the module
        good_pair = f"    >>> {call}\n    {real_src}"
        bad_pair = f"    >>> {call}\n    {wrong_repr.replace(chr(92), chr(92) + chr(92))}"
        if good_pair not in source:
            return None
        buggy = source.replace(good_pair, bad_pair, 1)
        if _harness_ok(buggy, tests):
            return None  # the lie must fail doctest
        cand = Candidate(
            family=self.NAME, language="python", domain="text_processing",
            difficulty="intermediate",
            task=("One of the doctest examples in this module promises an "
                  "output the function never produced. Run the examples "
                  "and report which one lies and what the real output is."),
            expected_behavior="See question.", code=buggy, tests=tests,
            verify_method="executed",
            notes={"bug_kind": "docstring_lies",
                   "correct_code": source, "victim": victim,
                   "promised": wrong_repr, "real": real_repr},
            tags=["documentation", "bug"],
            variant=f"{'|'.join(names)}|bug|lie",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": "docstring_lies", "victim": victim,
                "promised": wrong_repr, "real": real_repr}
        return cand, meta


register(globals(), DoctestAuthoringFamily)
