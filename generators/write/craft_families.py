"""Superprogrammer extension: master-level code craft.

py_mastery_refactor: take working-but-poor code and rebuild it the way
the best programmers (and Opus-style authors) do - no mutable default
arguments, no bare except, linear-time string assembly, single
responsibility per function. Behavior must survive AND the style gates
must pass: the bundled tests inspect the real solution source with ast.
Fully parameterized (names, separators, fallback values, domains) so the
dedup keeps genuinely distinct records.

py_fault_resilience: code that fails WELL under a hostile environment -
exponential backoff with a configurable factor, idempotent effect
application exactly once, and a circuit breaker with closed/open/half-open
states. A deterministic fault schedule (seeded at generation time) makes
every classic mistake observable: double effects, flat backoff, breakers
that never trip.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register


# --------------------------------------------------------------------------
# py_mastery_refactor (parameterized)
# --------------------------------------------------------------------------

_AST_GATE_PROLOGUE = '''def run_tests():
    import ast, inspect, solution as _mod
    src = inspect.getsource(_mod)
    tree = ast.parse(src)
'''


class MasteryRefactorFamily(Family):
    NAME = "py_mastery_refactor"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("code_review", "refactoring", "explanation", "debugging")

    KINDS = ("mutable_default", "bare_except", "string_concat_loop",
             "god_function")

    def _mk_mutable_default(self, rng: random.Random) -> Candidate:
        fn = rng.choice(["collect_tags", "parse_labels", "split_items"])
        sep = rng.choice([",", ";", "|"])
        pool = ["alpha", "beta", "gamma", "delta", "cache", "index",
                "queue", "graph"]
        words = rng.sample(pool, rng.randint(3, 5))
        raw = f"  {sep} ".join([words[0], words[1], words[2]])
        legacy = (
            f"def {fn}(post, tags=[]):\n"
            f"    for tag in post.split('{sep}'):\n"
            f"        tags.append(tag.strip())\n"
            f"    return tags\n")
        good = (
            f"def {fn}(post: str, tags: list[str] | None = None) -> list[str]:\n"
            f"    \"\"\"Split on '{sep}'; never mutate the caller's list.\"\"\"\n"
            f"    result = list(tags) if tags is not None else []\n"
            f"    for tag in post.split('{sep}'):\n"
            f"        result.append(tag.strip())\n"
            f"    return result\n")
        expected_first = [w.strip() for w in raw.split(sep)]
        tests = (
            f"def run_tests():\n"
            f"    import ast, inspect, solution as _mod\n"
            f"    assert {fn}({raw!r}) == {expected_first!r}\n"
            f"    first = {fn}('p{sep}q')\n"
            f"    second = {fn}('z')\n"
            f"    assert second == ['z'], 'calls must not share state'\n"
            f"    assert {fn}('m', ['seed']) == ['seed', 'm']\n"
            f"    src = inspect.getsource(_mod)\n"
            f"    tree = ast.parse(src)\n"
            f"    for node in ast.walk(tree):\n"
            f"        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
            f"            for default in node.args.defaults:\n"
            f"                if isinstance(default, (ast.List, ast.Dict, ast.Set, ast.Call)):\n"
            f"                    raise AssertionError('mutable default forbidden')\n"
            f"    print('gates-ok')\n"
        )
        return self._candidate(rng, "mutable_default", legacy, good, tests, fn,
                               raw=raw, sep=sep)

    def _mk_bare_except(self, rng: random.Random) -> Candidate:
        fn = rng.choice(["read_port", "read_setting", "read_limit"])
        key = rng.choice(["port", "timeout", "workers", "retries"])
        fallback = {"port": [8080, 8000, 9090], "timeout": [30, 60, 120],
                    "workers": [4, 8, 16], "retries": [3, 5, 10]}[key]
        fallback = rng.choice(fallback)
        legacy = (
            f"def {fn}(config):\n"
            f"    try:\n"
            f"        return int(config['{key}'])\n"
            f"    except:\n"
            f"        return {fallback}\n")
        good = (
            f"def {fn}(config: dict) -> int:\n"
            f"    \"\"\"Read '{key}'; only documented failure modes fall back.\"\"\"\n"
            f"    try:\n"
            f"        return int(config['{key}'])\n"
            f"    except (KeyError, TypeError, ValueError):\n"
            f"        return {fallback}\n")
        tests = (
            f"def run_tests():\n"
            f"    import ast, inspect, solution as _mod\n"
            f"    assert {fn}({{'{key}': '{fallback}'}}) == {fallback}\n"
            f"    assert {fn}({{}}) == {fallback}\n"
            f"    assert {fn}({{'{key}': None}}) == {fallback}\n"
            f"    assert {fn}({{'{key}': 'abc'}}) == {fallback}\n"
            f"    src = inspect.getsource(_mod)\n"
            f"    tree = ast.parse(src)\n"
            f"    allowed = {{'KeyError', 'TypeError', 'ValueError'}}\n"
            f"    for node in ast.walk(tree):\n"
            f"        if isinstance(node, ast.ExceptHandler):\n"
            f"            if node.type is None:\n"
            f"                raise AssertionError('bare except forbidden')\n"
            f"            items = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]\n"
            f"            names = {{getattr(i, 'id', getattr(i, 'attr', '')) for i in items}}\n"
            f"            if not names or not names.issubset(allowed):\n"
            f"                raise AssertionError('catch only documented modes')\n"
            f"    print('gates-ok')\n"
        )
        return self._candidate(rng, "bare_except", legacy, good, tests, fn,
                               key=key, fallback=fallback)

    def _mk_string_concat(self, rng: random.Random) -> Candidate:
        fn = rng.choice(["render_csv", "render_table", "serialize_rows"])
        delim = rng.choice([",", ";", "|"])
        n_rows = rng.randint(2, 5)
        rows = [[rng.randrange(10, 99) for _ in range(rng.randint(2, 3))]
                for _ in range(n_rows)]
        legacy = (
            f"def {fn}(rows):\n"
            f"    out = \"\"\n"
            f"    for row in rows:\n"
            f"        out += '{delim}'.join(str(cell) for cell in row) + \"\\n\"\n"
            f"    return out\n")
        good = (
            f"def {fn}(rows) -> str:\n"
            f"    \"\"\"Linear-time rendering: join once, never re-scan.\"\"\"\n"
            f"    lines = ['{delim}'.join(str(cell) for cell in row) for row in rows]\n"
            f"    return \"\\n\".join(lines) + \"\\n\" if lines else \"\"\n")
        expected = "".join(f"{delim}".join(map(str, row)) + "\n" for row in rows)
        tests = (
            f"def run_tests():\n"
            f"    import ast, inspect, solution as _mod\n"
            f"    assert {fn}({rows!r}) == {expected!r}\n"
            f"    assert {fn}([]) == ''\n"
            f"    assert {fn}([['a'], []]) == 'a\\n\\n'\n"
            f"    src = inspect.getsource(_mod)\n"
            f"    tree = ast.parse(src)\n"
            f"    for node in ast.walk(tree):\n"
            f"        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):\n"
            f"            raise AssertionError('use join, not repeated +=')\n"
            f"    print('gates-ok')\n"
        )
        return self._candidate(rng, "string_concat_loop", legacy, good, tests,
                               fn, rows=rows, delim=delim)

    def _mk_god_function(self, rng: random.Random) -> Candidate:
        domain = rng.choice(["signup", "order", "booking", "enrollment"])
        fn = f"handle_{domain}"
        sep = rng.choice(["|", "::"])
        name = rng.choice(["ana", "bo", "cy", "dee"])
        email = f"{name}@{rng.choice(['x.io', 'mail.dev', 'test.org'])}"
        body = f" {name.title()} {sep}{email} "
        legacy = (
            f"def {fn}(body):\n"
            f"    name = body.strip().lower()\n"
            f"    email = body.split('{sep}')[1].strip().lower() if '{sep}' in body else \"\"\n"
            f"    ok = len(name) > 0 and '@' in email and '.' in email\n"
            f"    card = f\"name={{name}};email={{email}};valid={{str(ok).lower()}}\"\n"
            f"    with open(\"{domain}.log\", \"a\") as fh:\n"
            f"        fh.write(card + \"\\n\")\n"
            f"    return ok\n")
        good = (
            f"def _parse_{domain}(body: str) -> tuple[str, str]:\n"
            f"    parts = body.split('{sep}')\n"
            f"    name = parts[0].strip().lower()\n"
            f"    email = parts[1].strip().lower() if len(parts) > 1 else \"\"\n"
            f"    return name, email\n"
            f"\n"
            f"\n"
            f"def _is_valid(name: str, email: str) -> bool:\n"
            f"    return len(name) > 0 and '@' in email and '.' in email\n"
            f"\n"
            f"\n"
            f"def _render_card(name: str, email: str, ok: bool) -> str:\n"
            f"    return f\"name={{name}};email={{email}};valid={{str(ok).lower()}}\"\n"
            f"\n"
            f"\n"
            f"def {fn}(body: str, sink=None) -> bool:\n"
            f"    \"\"\"Orchestrate parse -> validate -> render; sink injectable.\"\"\"\n"
            f"    name, email = _parse_{domain}(body)\n"
            f"    ok = _is_valid(name, email)\n"
            f"    card = _render_card(name, email, ok)\n"
            f"    (sink.append if sink is not None else _default_sink)(card)\n"
            f"    return ok\n"
            f"\n"
            f"\n"
            f"def _default_sink(card: str) -> None:\n"
            f"    pass\n")
        card_ok = f"name={name};email={email};valid=true"
        card_bad = f"name={name};email=;valid=false"
        tests = (
            f"def run_tests():\n"
            f"    import ast, inspect, solution as _mod\n"
            f"    assert {fn}({body!r}) is True\n"
            f"    assert {fn}('{sep}bad') is False\n"
            f"    assert {fn}('solo') is False\n"
            f"    log = []\n"
            f"    assert {fn}({body!r}, sink=log) is True\n"
            f"    assert log == [{card_ok!r}]\n"
            f"    log2 = []\n"
            f"    {fn}('{sep}bad', sink=log2)\n"
            f"    assert log2 == ['name=;email=bad;valid=false']\n"
            f"    src = inspect.getsource(_mod)\n"
            f"    tree = ast.parse(src)\n"
            f"    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]\n"
            f"    if len(defs) < 4:\n"
            f"        raise AssertionError('split parse / validate / render / orchestrate')\n"
            f"    print('gates-ok')\n"
        )
        return self._candidate(rng, "god_function", legacy, good, tests, fn,
                               domain=domain, body=body, sep=sep)

    def _candidate(self, rng: random.Random, kind: str, legacy: str,
                   good: str, tests: str, entry: str, **kw) -> Candidate:
        why = {
            "mutable_default": "a shared default list accumulates across "
                               "calls; use a None sentinel and never mutate "
                               "the caller's data",
            "bare_except": "a bare except swallows KeyboardInterrupt and "
                           "SystemExit and hides real bugs; catch exactly "
                           "the documented modes",
            "string_concat_loop": "repeated += re-scans the growing buffer, "
                                  "quadratic cost; collect parts and join once",
            "god_function": "one function that parses, validates, renders "
                            "and logs cannot be tested or reused; split "
                            "responsibilities and inject the side effect",
        }[kind]
        params = ", ".join(f"{k}={v!r}" for k, v in kw.items()) or "defaults"
        task = (
            "The function below works today, but a senior reviewer would "
            "bounce it. Rewrite it to production quality in Python. Defect "
            f"class: {kind} ({why}). Requirements: preserve the observable "
            "behavior exactly, add type hints and a docstring, remove the "
            "smell so an AST-based review passes (no mutable default "
            "arguments, no bare except, no repeated string += in loops, "
            "single responsibility per function), and keep the same public "
            f"entry point (`{entry}`).\n\nLegacy code:\n```python\n"
            f"{legacy}\n```\n(Scenario parameters: {params})")
        return Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty=rng.choice(["advanced", "expert"]),
            task=task,
            expected_behavior=(f"Same observable behavior as the legacy "
                               f"`{entry}`, with the {kind} smell removed "
                               "(enforced by AST gates in the test suite)."),
            code=good, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": f"Refactor {kind} into master-level Python",
                "approach": "preserve behavior, remove the mechanism, pass "
                            "the AST review gates",
                "key_points": ["behavior preservation is executed, not assumed",
                               "style gates parse the real solution with ast",
                               "side effects become injectable where needed",
                               "the public entry point stays stable"],
                "big_o_time": "same asymptotic class as legacy or better",
                "big_o_space": "same as legacy or better",
                "edge_cases": ["empty/degenerate input matches legacy",
                               "the defect mechanism is structurally gone"]}},
            tags=["craft", "refactoring", "mastery", kind],
            variant=f"{kind}|{entry}|{params}",
            seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        builder = {"mutable_default": self._mk_mutable_default,
                   "bare_except": self._mk_bare_except,
                   "string_concat_loop": self._mk_string_concat,
                   "god_function": self._mk_god_function}[kind]
        return builder(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        good = self.generate(random.Random(rng.randrange(2**31)))
        legacy_start = good.task.index("```python\n") + len("```python\n")
        legacy_end = good.task.index("\n```", legacy_start)
        buggy = good.task[legacy_start:legacy_end] + "\n"
        cand = Candidate(
            family=self.NAME, language="python", domain="engineering",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": f"smell_survives_{kind}",
                   "correct_code": good.code},
            tags=["craft", "bug"], variant=f"{good.variant}|bug",
            seed=rng.randrange(2**31))
        meta = {"kind": f"smell_survives_{kind}", "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


# --------------------------------------------------------------------------
# py_fault_resilience (parameterized)
# --------------------------------------------------------------------------

class FaultResilienceFamily(Family):
    NAME = "py_fault_resilience"
    LANGUAGE = "python"
    DOMAIN = "networking"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "failure_prediction")

    KINDS = ("retry_backoff", "idempotent_apply", "circuit_breaker")

    def _mk_retry(self, rng: random.Random) -> Candidate:
        factor = rng.choice([2, 3])
        max_attempts = rng.choice([3, 4, 5])
        base_delay = rng.choice([0.25, 0.5, 1.0])
        fails_first = rng.randint(1, max_attempts - 1)
        sleeps = [round(base_delay * factor ** i, 4)
                  for i in range(fails_first)]
        broken_sleeps = [round(base_delay * factor ** i, 4)
                         for i in range(max_attempts - 1)]
        final = f"payload{rng.randrange(10, 99)}"
        plan = ["RuntimeError"] * fails_first + [final]
        code = (
            "def with_retry(op, *, max_attempts, base_delay, sleep, jitter):\n"
            f"    \"\"\"Call op until success; delay = base * {factor} ** attempt.\"\"\"\n"
            "    last_error = None\n"
            "    for attempt in range(max_attempts):\n"
            "        try:\n"
            "            return op()\n"
            "        except Exception as error:\n"
            "            last_error = error\n"
            "            if attempt + 1 < max_attempts:\n"
            f"                sleep(jitter(base_delay * ({factor} ** attempt)))\n"
            "    raise last_error\n")
        tests = (
            f"def run_tests():\n"
            f"    sleeps = []\n"
            f"    plan = iter([{', '.join('RuntimeError()' if p == 'RuntimeError' else repr(p) for p in plan)}])\n"
            f"    def op():\n"
            f"        step = next(plan)\n"
            f"        if isinstance(step, Exception):\n"
            f"            raise step\n"
            f"        return step\n"
            f"    out = with_retry(op, max_attempts={max_attempts}, base_delay={base_delay},\n"
            f"                     sleep=sleeps.append, jitter=lambda d: d)\n"
            f"    assert out == {final!r}\n"
            f"    assert sleeps == {sleeps!r}, sleeps\n"
            f"    def broken():\n"
            f"        raise RuntimeError('down')\n"
            f"    try:\n"
            f"        with_retry(broken, max_attempts={max_attempts}, base_delay={base_delay},\n"
            f"                   sleep=sleeps.append, jitter=lambda d: d)\n"
            f"    except RuntimeError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('exhaustion must re-raise')\n"
            f"    assert sleeps[{len(sleeps)}:] == {broken_sleeps!r}, 'flat backoff rejected'\n"
            f"    calls = {{'n': 0}}\n"
            f"    def once():\n"
            f"        calls['n'] += 1\n"
            f"        return 7\n"
            f"    assert with_retry(once, max_attempts={max_attempts + 1}, base_delay={base_delay},\n"
            f"                      sleep=lambda s: None, jitter=lambda d: d) == 7\n"
            f"    assert calls['n'] == 1 and sleeps[{len(sleeps)}:] == {broken_sleeps!r}, 'no sleep after success'\n"
            f"    print('gates-ok')\n"
        )
        task = (
            f"Implement with_retry(op, *, max_attempts, base_delay, sleep, "
            f"jitter) in Python for calling a flaky remote operation. Call "
            f"op() up to max_attempts times. Whenever op() raises, sleep for "
            f"base_delay * {factor} ** attempt_index seconds, passed first "
            f"through jitter(...) and then to sleep(...) - exponential "
            f"backoff with factor {factor}. If the last attempt also fails, "
            f"re-raise the original exception. Never sleep after a "
            f"successful call. The harness pins the exact delay sequence "
            f"and rejects flat backoff."
        )
        return self._candidate(rng, "retry_backoff", code, tests, task,
                               expected=("success value returned; delays "
                                         f"{sleeps!r}; exhaustion re-raises; "
                                         "no sleep after success"),
                               variant=f"retry|{factor}|{max_attempts}|{base_delay}")

    def _mk_idempotent(self, rng: random.Random) -> Candidate:
        prefix = rng.choice(["pay", "ship", "sync", "export"])
        keys = [f"{prefix}-{i}" for i in rng.sample(range(10, 99), 4)]
        fail_key = rng.choice(keys)
        events = [(keys[0], 1), (keys[1], 2), (keys[0], 1), (keys[2], 3),
                  (keys[1], 2), (keys[3], 4)]
        expected = {k: f"done:{k}" for k in dict.fromkeys(k for k, _ in events)}
        raw_counts = {k: 1 for k in expected}
        raw_counts[fail_key] = 2
        code = (
            "def apply_events(events, store):\n"
            "    \"\"\"Exactly-once application; one retry for transient errors.\"\"\"\n"
            "    results = {}\n"
            "    for key, payload in events:\n"
            "        if key in results:\n"
            "            continue\n"
            "        try:\n"
            "            results[key] = store.apply(key, payload)\n"
            "        except RuntimeError:\n"
            "            results[key] = store.apply(key, payload)\n"
            "    return results\n")
        tests = (
            f"def run_tests():\n"
            f"    class FlakyStore:\n"
            f"        def __init__(self, fail_once):\n"
            f"            self.fail_once = set(fail_once)\n"
            f"            self.applied = []\n"
            f"            self.results = {{}}\n"
            f"        def apply(self, key, payload):\n"
            f"            self.applied.append(key)\n"
            f"            if key in self.fail_once:\n"
            f"                self.fail_once.discard(key)\n"
            f"                raise RuntimeError('transient')\n"
            f"            self.results[key] = f'done:{{key}}'\n"
            f"            return self.results[key]\n"
            f"    events = {events!r}\n"
            f"    store = FlakyStore([{fail_key!r}])\n"
            f"    out = apply_events(events, store)\n"
            f"    assert out == {expected!r}\n"
            f"    from collections import Counter\n"
            f"    assert Counter(store.applied) == {raw_counts!r}, store.applied\n"
            f"    store2 = FlakyStore([])\n"
            f"    out2 = apply_events(events, store2)\n"
            f"    assert out2 == {expected!r}\n"
            f"    assert len(store2.applied) == {len(expected)}, 'no duplicate effects'\n"
            f"    print('gates-ok')\n"
        )
        task = (
            "Implement apply_events(events, store) in Python with "
            "exactly-once semantics. events is a list of (key, payload) "
            "tuples where keys may repeat; store exposes apply(key, payload) "
            "that records an effect and returns a result string, but may "
            "raise RuntimeError (transient) the first time it sees a key. "
            "Rules: each unique key must be applied successfully exactly "
            "once; a transient RuntimeError on a key's first apply is "
            "retried once for that same key; after a key succeeds, later "
            "duplicate events must return the cached result WITHOUT "
            "touching the store again. Return a dict key -> result."
        )
        return self._candidate(rng, "idempotent_apply", code, tests, task,
                               expected=("every unique key applied exactly "
                                         "once; one retry for transient "
                                         "failures; duplicates served from "
                                         "the cache"),
                               variant=f"idem|{prefix}|{fail_key}")

    def _mk_breaker(self, rng: random.Random) -> Candidate:
        threshold = rng.choice([2, 3, 4])
        cooldown = rng.choice([1, 2, 3])
        code = (
            "class CircuitBreaker:\n"
            "    \"\"\"closed -> open after N consecutive failures -> half-open.\"\"\"\n"
            "\n"
            "    def __init__(self, fail_threshold: int, cooldown: int):\n"
            "        if fail_threshold < 1 or cooldown < 1:\n"
            "            raise ValueError(\"threshold and cooldown must be positive\")\n"
            "        self.fail_threshold = fail_threshold\n"
            "        self.cooldown = cooldown\n"
            "        self.state = \"closed\"\n"
            "        self._failures = 0\n"
            "        self._ticks = 0\n"
            "        self._open_at = 0\n"
            "\n"
            "    def tick(self) -> None:\n"
            "        self._ticks += 1\n"
            "\n"
            "    def _ticks_since_open(self) -> int:\n"
            "        return self._ticks - self._open_at\n"
            "\n"
            "    def call(self, fn):\n"
            "        if self.state == \"open\":\n"
            "            if self._ticks_since_open() < self.cooldown:\n"
            "                raise RuntimeError(\"open\")\n"
            "            self.state = \"half-open\"\n"
            "        if self.state == \"half-open\":\n"
            "            try:\n"
            "                result = fn()\n"
            "            except Exception:\n"
            "                self.state = \"open\"\n"
            "                self._open_at = self._ticks\n"
            "                raise\n"
            "            self.state = \"closed\"\n"
            "            self._failures = 0\n"
            "            return result\n"
            "        try:\n"
            "            result = fn()\n"
            "        except Exception:\n"
            "            self._failures += 1\n"
            "            if self._failures >= self.fail_threshold:\n"
            "                self.state = \"open\"\n"
            "                self._open_at = self._ticks\n"
            "            raise\n"
            "        self._failures = 0\n"
            "        return result\n")
        tests = (
            f"def run_tests():\n"
            f"    calls = []\n"
            f"    def flaky():\n"
            f"        calls.append(1)\n"
            f"        raise RuntimeError('down')\n"
            f"    br = CircuitBreaker({threshold}, {cooldown})\n"
            f"    for _ in range({threshold}):\n"
            f"        try:\n"
            f"            br.call(flaky)\n"
            f"        except RuntimeError:\n"
            f"            pass\n"
            f"    assert br.state == 'open', 'consecutive failures must open'\n"
            f"    n = len(calls)\n"
            f"    try:\n"
            f"        br.call(flaky)\n"
            f"    except RuntimeError as e:\n"
            f"        assert 'open' in str(e)\n"
            f"    else:\n"
            f"        raise AssertionError('open breaker must refuse')\n"
            f"    assert len(calls) == n, 'open breaker must not invoke the dependency'\n"
            f"    for _ in range({cooldown}):\n"
            f"        br.tick()\n"
            f"    try:\n"
            f"        br.call(flaky)\n"
            f"    except RuntimeError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('probe inherits the failure')\n"
            f"    assert br.state == 'open', 'failed probe reopens'\n"
            f"    for _ in range({cooldown}):\n"
            f"        br.tick()\n"
            f"    assert br.call(lambda: 'ok') == 'ok', 'good probe closes'\n"
            f"    assert br.state == 'closed'\n"
            f"    br2 = CircuitBreaker({threshold}, {cooldown})\n"
            f"    try:\n"
            f"        br2.call(flaky)\n"
            f"    except RuntimeError:\n"
            f"        pass\n"
            f"    assert br2.call(lambda: 'ok') == 'ok', 'success resets the streak'\n"
            f"    assert br2.state == 'closed'\n"
            f"    try:\n"
            f"        br2.call(flaky)\n"
            f"    except RuntimeError:\n"
            f"        pass\n"
            f"    assert br2.state == 'closed', 'streak was reset; one failure is not enough'\n"
            f"    print('gates-ok')\n"
        )
        task = (
            f"Implement a CircuitBreaker class in Python with "
            f"closed/open/half-open semantics. CircuitBreaker({threshold}, "
            f"{cooldown}): while closed, call(fn) invokes fn(); after "
            f"{threshold} CONSECUTIVE failures the breaker opens and "
            "call(fn) raises RuntimeError('open') WITHOUT invoking fn. Each "
            "tick() advances time one unit; after cooldown ticks the "
            "breaker becomes half-open and lets exactly one probe through: "
            "probe success closes it (failure streak reset), probe failure "
            "reopens it. One success while closed resets the streak (a "
            "single failure after a success must NOT open it)."
        )
        return self._candidate(rng, "circuit_breaker", code, tests, task,
                               expected=("open breaker refuses without "
                                         "invoking the dependency; half-open "
                                         "probes once; success resets the "
                                         "streak"),
                               variant=f"breaker|{threshold}|{cooldown}")

    def _candidate(self, rng: random.Random, kind: str, code: str,
                   tests: str, task: str, expected: str,
                   variant: str) -> Candidate:
        return Candidate(
            family=self.NAME, language="python", domain="networking",
            difficulty="advanced", task=task, expected_behavior=expected,
            code=code, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": f"Resilience pattern: {kind}",
                "approach": "deterministic fault schedule makes every "
                            "classic mistake observable",
                "key_points": ["exactly-once needs a results cache keyed by id",
                               "backoff grows geometrically, jitter shapes it",
                               "an open breaker must not touch the dependency",
                               "success resets consecutive-failure counters"],
                "big_o_time": "O(attempts) or O(events)",
                "big_o_space": "O(unique keys) for the cache",
                "edge_cases": ["duplicated event keys",
                               "failure on the very last attempt",
                               "probe failure while half-open"]}},
            tags=["resilience", kind, "fault-injection"],
            variant=variant, seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        builder = {"retry_backoff": self._mk_retry,
                   "idempotent_apply": self._mk_idempotent,
                   "circuit_breaker": self._mk_breaker}[kind]
        return builder(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        builder = {"retry_backoff": self._mk_retry,
                   "idempotent_apply": self._mk_idempotent,
                   "circuit_breaker": self._mk_breaker}[kind]
        good = builder(random.Random(rng.randrange(2**31)))
        if kind == "retry_backoff":
            factor = good.variant.split("|")[1]
            buggy = good.code.replace(
                f"sleep(jitter(base_delay * ({factor} ** attempt)))",
                "sleep(jitter(base_delay))")
            bug_kind = "flat_backoff"
        elif kind == "idempotent_apply":
            buggy = good.code.replace(
                "        if key in results:\n            continue\n", "")
            bug_kind = "no_dedupe"
        else:
            buggy = good.code.replace(
                "if self._failures >= self.fail_threshold:",
                "if self._failures > self.fail_threshold + 3:")
            bug_kind = "never_opens"
        if buggy == good.code:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain="networking",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code},
            tags=["resilience", "bug"], variant=f"{good.variant}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code, "tests": good.tests}
        return cand, meta


register(globals(), MasteryRefactorFamily)
register(globals(), FaultResilienceFamily)
