"""Dataset-1 write families for JavaScript (Node.js).

Harness conventions (CONTRACT.md + validators/executors/js_exec.py):
  * solution.js defines functions and ends with `module.exports = {...};`
  * `tests` is JS source defining `function runTests(solution){ ... }` using the
    global `assert` module (the harness provides it and calls runTests).
  * The async family defines `async function runTests(solution) { ... await ... }`.
    The harness fires runTests without awaiting, but a rejected test promise is
    an unhandled rejection -> non-zero exit -> verification fails, while a full
    pass exits 0, so the executed check stays sound. All fake delays are
    setTimeout-based and small; a candidate's whole suite stays well under 2s.

Determinism: every random decision flows from the rng passed to generate().
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, Family, FileSpec, register
from ..problems import REGISTRY


def _fill(template: str, **kw) -> str:
    """Substitute {token} placeholders; literal JS braces are left untouched."""
    out = template
    for key, value in kw.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {
        "purpose": purpose,
        "approach": approach,
        "key_points": key_points,
        "big_o_time": big_o_time,
        "big_o_space": big_o_space,
        "edge_cases": edge_cases,
    }


def _jsify_spec(text: str) -> str:
    """Nudge shared bank specs toward JS vocabulary (arrays, booleans)."""
    for old, new in (
        ("sorted list", "sorted array"),
        ("a list of", "an array of"),
        ("as a tuple (i, j)", "as a two-element array [i, j]"),
        ("Return True or False", "Return true or false"),
        ("(word, count) tuples", "[word, count] pairs"),
        ("a new sorted list", "a new sorted array"),
    ):
        text = text.replace(old, new)
    return text


class JavaScriptBankFamily(Family):
    """spec -> implementation for every bank problem available in JavaScript."""
    NAME = "js_bank_wrappers"
    LANGUAGE = "javascript"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "trace", "debugging", "testing", "failure_prediction",
                "complexity", "translation", "comparison", "optimization", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        pids = sorted(p for p, prob in REGISTRY.items() if "javascript" in prob.impls)
        pid = rng.choice(pids)
        prob = REGISTRY[pid]
        P = prob.params(rng)
        unit = prob.impls["javascript"](P, rng)
        return Candidate(
            family=self.NAME, language="javascript", domain=prob.domain,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=_jsify_spec(prob.spec(P, rng)),
            expected_behavior=unit.notes.get("purpose", "")
            + " Behavior is verified by the bundled Node.js test suite.",
            code=unit.files["solution.js"], tests=unit.tests,
            verify_method="executed",
            notes={"problem": pid, "params": P, "unit_notes": unit.notes,
                   "big_o": {"time": unit.notes.get("big_o_time"),
                             "space": unit.notes.get("big_o_space")},
                   "explain": unit.notes, "function_name": unit.function_name},
            tags=["javascript", pid], variant=pid, seed=rng.randrange(2 ** 31),
        )

    def make_buggy(self, rng: random.Random):
        pids = sorted(p for p, prob in REGISTRY.items() if "javascript" in prob.impls)
        pid = rng.choice(pids)
        prob = REGISTRY[pid]
        P = prob.params(rng)
        unit = prob.impls["javascript"](P, rng)
        if not unit.bugs:
            return None
        kind = rng.choice(sorted(unit.bugs))
        buggy_files = unit.bugs[kind](unit.files)
        buggy_code = buggy_files["solution.js"]
        if buggy_code == unit.files["solution.js"]:
            return None
        cand = Candidate(
            family=self.NAME, language="javascript", domain=prob.domain,
            difficulty="intermediate",
            task=_jsify_spec(prob.spec(P, rng)),
            expected_behavior="See question.", code=buggy_code, tests=unit.tests,
            verify_method="executed",
            notes={"problem": pid, "params": P, "bug_kind": kind,
                   "correct_code": unit.files["solution.js"],
                   "unit_notes": unit.notes, "explain": unit.notes},
            tags=["javascript", pid, "bug"], variant=f"{pid}|bug|{kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": kind, "problem": pid,
                "correct_code": unit.files["solution.js"], "tests": unit.tests,
                "unit_notes": unit.notes}
        return cand, meta


class JavaScriptArrayTransformsFamily(Family):
    """map/filter/reduce pipelines, chunking, dedupe, grouping by key."""
    NAME = "js_array_transforms"
    LANGUAGE = "javascript"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging", "complexity", "code_review")

    KINDS = ("pipeline", "chunk", "dedupe", "group_by")

    # ------------------------------------------------------------------ build
    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "pipeline":
            return self._build_pipeline(kind, rng)
        if kind == "chunk":
            return self._build_chunk(kind, rng)
        if kind == "dedupe":
            return self._build_dedupe(kind, rng)
        return self._build_group_by(kind, rng)

    def _build_pipeline(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["processReadings", "analyzeScores", "summarizeSamples",
                         "computeAggregate"])
        n = rng.randint(6, 12)
        data = [rng.randint(1, 99) for _ in range(n)]
        m = rng.choice([3, 5, 9])  # odd multiplier keeps parity meaningful
        parity = rng.choice(["even", "odd"])
        cmp = "===" if parity == "even" else "!=="
        keep = 0 if parity == "even" else 1
        total = sum(x * m for x in data if (x * m) % 2 == keep)
        drop_case = "[1, 3, 5]" if parity == "even" else "[2, 4, 6]"
        code = _fill(
            "// Scale, filter, then reduce a batch of readings to one number.\n"
            "function {fn}(readings) {\n"
            "  const scaled = readings.map((x) => x * {m});\n"
            "  const picked = scaled.filter((x) => x % 2 {cmp} 0);\n"
            "  const total = picked.reduce((acc, x) => acc + x, 0);\n"
            "  return total;\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn, m=m, cmp=cmp)
        tests = _fill(
            "function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  assert.strictEqual({fn}({data}), {total});\n"
            "  assert.strictEqual({fn}([]), 0);\n"
            "  assert.strictEqual({fn}({drop_case}), 0);\n"
            "}\n",
            fn=fn, data=json.dumps(data), total=total, drop_case=drop_case)
        task = (f"Implement `{fn}(readings)` in Node.js JavaScript: multiply every "
                f"number by {m}, keep only the products that are {parity}, and reduce "
                f"the survivors to their sum with reduce(). An empty input returns 0. "
                f"Export the function with module.exports.")
        expected = (f"reduce() accumulates the {parity} scaled values from left to "
                    f"right starting at 0; for the sample input it returns {total}.")
        explain = _explain(
            expected,
            "Three-stage pipeline: map scales, filter keeps the wanted parity, "
            "reduce folds with an explicit 0 seed.",
            ["the reduce seed 0 makes the empty-array case return 0",
             "x % 2 with === / !== avoids truthy/falsy coercion surprises",
             "map and filter return new arrays, so the input is never mutated"],
            "O(n)", "O(n)",
            ["empty array yields 0 via the reduce seed",
             "input where every value is filtered out also yields 0"])
        bugs = {
            "accumulator_seed_off_by_one": lambda c: c.replace(
                ".reduce((acc, x) => acc + x, 0);", ".reduce((acc, x) => acc + x, 1);"),
            "accumulator_op_flip": lambda c: c.replace(
                ".reduce((acc, x) => acc + x, 0);", ".reduce((acc, x) => acc * x, 0);"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected, explain=explain, bugs=bugs)

    def _build_chunk(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["chunkArray", "paginateItems", "splitIntoBatches"])
        size = rng.randint(2, 4)
        n = rng.randint(7, 12)
        if n % size == 0:
            n += 1  # force a short tail chunk
        data = [rng.randint(1, 99) for _ in range(n)]
        expected = [data[i:i + size] for i in range(0, n, size)]
        code = _fill(
            "// Split a list into consecutive fixed-size windows.\n"
            "function {fn}(items, size) {\n"
            "  const chunks = [];\n"
            "  for (let i = 0; i < items.length; i += size) {\n"
            "    chunks.push(items.slice(i, i + size));\n"
            "  }\n"
            "  return chunks;\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn)
        tests = _fill(
            "function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  assert.deepStrictEqual({fn}({data}, {size}), {expected});\n"
            "  assert.deepStrictEqual({fn}([], {size}), []);\n"
            "  assert.deepStrictEqual({fn}([1, 2, 3], 5), [[1, 2, 3]]);\n"
            "}\n",
            fn=fn, data=json.dumps(data), size=size, expected=json.dumps(expected))
        task = (f"Implement `{fn}(items, size)` in JavaScript: split the array into "
                f"consecutive chunks of at most `size` elements while preserving "
                f"order; the final chunk may be shorter and an empty array yields "
                f"an empty result. Export the function with module.exports.")
        expected_txt = (f"For the sample array of {n} numbers with size {size} the "
                        f"function returns {len(expected)} chunks, the last one "
                        f"holding {len(expected[-1])} element(s).")
        explain = _explain(
            expected_txt,
            "Single forward loop stepping by `size`; slice() copies each window so "
            "the source array is never mutated.",
            ["slice clamps out-of-range ends, so the tail window can be shorter",
             "stepping by size keeps windows disjoint and ordered",
             "an empty array skips the loop body and returns []"],
            "O(n)", "O(n)",
            ["length not divisible by size leaves a short tail chunk",
             "size larger than the array length yields one chunk with everything"])
        bugs = {
            "trailing_empty_chunk": lambda c: c.replace(
                "for (let i = 0; i < items.length; i += size) {",
                "for (let i = 0; i <= items.length; i += size) {"),
            "short_windows": lambda c: c.replace(
                "chunks.push(items.slice(i, i + size));",
                "chunks.push(items.slice(i, i + size - 1));"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected_txt, explain=explain, bugs=bugs)

    def _build_dedupe(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["uniqueValues", "dedupe", "distinctInOrder"])
        words = ["cache", "queue", "worker", "retry", "login", "report", "config",
                 "budget", "task", "email"]
        n = rng.randint(6, 12)
        seq = [rng.choice(words) for _ in range(n)]
        seq[-1] = seq[0]  # guarantee at least one duplicate
        seen, out = set(), []
        for w in seq:
            if w not in seen:
                seen.add(w)
                out.append(w)
        code = _fill(
            "// Keep the first occurrence of every value, preserving order.\n"
            "function {fn}(items) {\n"
            "  const seen = new Set();\n"
            "  const out = [];\n"
            "  for (const item of items) {\n"
            "    if (!seen.has(item)) {\n"
            "      seen.add(item);\n"
            "      out.push(item);\n"
            "    }\n"
            "  }\n"
            "  return out;\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn)
        tests = _fill(
            "function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  assert.deepStrictEqual({fn}({seq}), {expected});\n"
            "  assert.deepStrictEqual({fn}([]), []);\n"
            "  assert.deepStrictEqual({fn}(['x', 'x', 'x']), ['x']);\n"
            "}\n",
            fn=fn, seq=json.dumps(seq), expected=json.dumps(out))
        task = (f"Write `{fn}(items)` in JavaScript that removes duplicate values "
                f"from an array while preserving the first-occurrence order of every "
                f"element; an empty input returns an empty array. Export the "
                f"function via module.exports.")
        expected_txt = (f"The sample sequence of {n} tokens collapses to {len(out)} "
                        f"unique values, e.g. it starts with {out[0]!r} exactly once.")
        explain = _explain(
            expected_txt,
            "A Set tracks values already emitted; only unseen values are appended.",
            ["Set.has is O(1) on average, keeping the whole pass linear",
             "order is preserved because output grows by append only",
             "the guard runs before pushing, so duplicates never enter the output"],
            "O(n)", "O(n)",
            ["empty array returns an empty array",
             "an array of identical values collapses to a single element"])
        bugs = {
            "skips_seen_guard": lambda c: c.replace(
                "    if (!seen.has(item)) {\n      seen.add(item);\n"
                "      out.push(item);\n    }\n",
                "    out.push(item);\n"),
            "only_duplicates_kept": lambda c: c.replace(
                "if (!seen.has(item)) {", "if (seen.has(item)) {"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected_txt, explain=explain, bugs=bugs)

    def _build_group_by(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["groupByDept", "indexByTeam", "collectByChannel"])
        names = ["ada", "grace", "linus", "margaret", "alan", "barbara",
                 "katherine", "dennis"]
        depts = rng.sample(["platform", "billing", "support", "research", "ops"],
                           rng.randint(2, 3))
        n = rng.randint(5, 9)
        people = [{"name": rng.choice(names), "dept": rng.choice(depts)}
                  for _ in range(n)]
        groups: dict = {}
        for p in people:
            groups.setdefault(p["dept"], []).append(p)
        code = _fill(
            "// Bucket people by department, preserving input order in each bucket.\n"
            "function {fn}(people) {\n"
            "  const groups = {};\n"
            "  for (const person of people) {\n"
            "    const key = person.dept;\n"
            "    if (groups[key] === undefined) {\n"
            "      groups[key] = [];\n"
            "    }\n"
            "    groups[key].push(person);\n"
            "  }\n"
            "  return groups;\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn)
        tests = _fill(
            "function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  assert.deepStrictEqual({fn}({people}), {expected});\n"
            "  assert.deepStrictEqual({fn}([]), {empty});\n"
            "  assert.deepStrictEqual(\n"
            "    {fn}([{ name: 'solo', dept: '{dept0}' }]),\n"
            "    { {dept0}: [{ name: 'solo', dept: '{dept0}' }] });\n"
            "}\n",
            fn=fn, people=json.dumps(people), expected=json.dumps(groups),
            empty="{}", dept0=depts[0])
        task = (f"Implement `{fn}(people)` in JavaScript: group the given person "
                f"objects (each with name and dept fields) by their `dept` property "
                f"into a plain object that maps every department to the array of its "
                f"members, keeping input order inside each bucket and first-seen "
                f"order across keys. Export the function with module.exports.")
        expected_txt = (f"The sample roster splits into {len(groups)} departments "
                        f"({', '.join(sorted(groups))}); members appear in the order "
                        f"they occur in the input array.")
        explain = _explain(
            expected_txt,
            "One pass over the roster; each person is appended to the bucket keyed "
            "by their department, creating the bucket on first sight.",
            ["plain-object buckets keep first-seen key order in modern engines",
             "appending (push) preserves the relative input order of members",
             "the undefined check creates each bucket exactly once"],
            "O(n)", "O(n)",
            ["empty roster returns an empty object",
             "a department with a single member still gets its own bucket"])
        bugs = {
            "accumulator_reset": lambda c: c.replace(
                "    if (groups[key] === undefined) {\n      groups[key] = [];\n    }\n",
                "    groups[key] = [];\n"),
            "pushes_name_field": lambda c: c.replace(
                "groups[key].push(person);", "groups[key].push(person.name);"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected_txt, explain=explain, bugs=bugs)

    # --------------------------------------------------------------- generate
    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "function_name": b["fn"], "explain": b["explain"]},
            tags=["javascript", "arrays", kind], variant=kind,
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        bug_kind = rng.choice(sorted(b["bugs"]))
        buggy_code = b["bugs"][bug_kind](b["code"])
        if buggy_code == b["code"]:
            return None
        cand = Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty="intermediate",
            task=b["task"], expected_behavior="See question.",
            code=buggy_code, tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "bug_kind": bug_kind, "correct_code": b["code"],
                   "explain": b["explain"]},
            tags=["javascript", "arrays", kind, "bug"],
            variant=f"{kind}|bug|{bug_kind}", seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "problem": self.NAME, "correct_code": b["code"],
                "tests": b["tests"], "unit_notes": b["explain"]}
        return cand, meta

    def review_variant(self, rng: random.Random):
        """Working but flawed groupBy: nested loops + repeated key scanning."""
        b = self._build("group_by", rng)
        fn = b["fn"]
        naive = _fill(
            "// Grouping via a full re-scan per distinct key (review variant).\n"
            "function {fn}(people) {\n"
            "  const keys = [];\n"
            "  for (const person of people) {\n"
            "    if (!keys.includes(person.dept)) {\n"
            "      keys.push(person.dept);\n"
            "    }\n"
            "  }\n"
            "  const groups = {};\n"
            "  for (const key of keys) {\n"
            "    groups[key] = [];\n"
            "    for (const person of people) {\n"
            "      if (person.dept === key) {\n"
            "        groups[key].push(person);\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  return groups;\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn)
        cand = Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty="intermediate",
            task=b["task"], expected_behavior=b["expected"],
            code=naive, tests=b["tests"], verify_method="executed",
            notes={"kind": "group_by", "function_name": fn,
                   "explain": b["explain"], "review": "naive_nested_loops"},
            tags=["javascript", "arrays", "group_by", "review"],
            variant="group_by|review", seed=rng.randrange(2 ** 31))
        issues = [
            {"kind": "efficiency", "severity": "medium",
             "why": "the nested loops re-scan the whole input once per distinct key, "
                    "so the work is O(n * k) instead of a single O(n) pass",
             "better": "make one pass and append each item into a bucket keyed by "
                       "its group (Map or plain object)"},
            {"kind": "repeated_computation", "severity": "low",
             "why": "person.dept is re-read and re-compared for every distinct key "
                    "rather than computed once per element",
             "better": "compute the key once per element and keep a Set of keys "
                       "already seen"},
            {"kind": "style", "severity": "low",
             "why": "the key-collection pass and the grouping pass duplicate logic "
                    "that a single accumulator handles",
             "better": "fold both concerns into one loop that creates buckets on "
                       "demand"},
        ]
        return cand, issues


class JavaScriptAsyncPatternsFamily(Family):
    """Promise.all fan-out, async/await sequencing, bounded retry helper."""
    NAME = "js_async_patterns"
    LANGUAGE = "javascript"
    DOMAIN = "concurrency"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "trace", "complexity")

    KINDS = ("promise_all", "sequence", "retry")

    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "promise_all":
            return self._build_promise_all(kind, rng)
        if kind == "sequence":
            return self._build_sequence(kind, rng)
        return self._build_retry(kind, rng)

    def _build_promise_all(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["runAll", "gatherAll", "finishJobs"])
        labels = ["alpha", "beta", "gamma"][:3]
        delays = sorted(rng.sample([2, 3, 5, 7, 11, 16], 3), reverse=True)
        jobs = [{"label": lbl, "ms": d} for lbl, d in zip(labels, delays)]
        jobs_js = json.dumps(jobs)
        labels_js = json.dumps(labels)
        code = _fill(
            "// Deterministic fake I/O: a setTimeout-based delay promise.\n"
            "function sleep(ms) {\n"
            "  return new Promise((resolve) => setTimeout(resolve, ms));\n"
            "}\n\n"
            "// Start every job concurrently; resolve labels in INPUT order.\n"
            "async function {fn}(jobs) {\n"
            "  const running = jobs.map((job) => sleep(job.ms).then(() => job.label));\n"
            "  return Promise.all(running);\n"
            "}\n\n"
            "module.exports = { sleep, {fn} };\n",
            fn=fn)
        tests = _fill(
            "async function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  const jobs = {jobs};\n"
            "  assert.deepStrictEqual(await {fn}(jobs), {labels});\n"
            "  assert.deepStrictEqual(await {fn}([]), []);\n"
            "  assert.deepStrictEqual(await {fn}([{ label: 'solo', ms: 1 }]),\n"
            "                         ['solo']);\n"
            "}\n",
            fn=fn, jobs=jobs_js, labels=labels_js)
        task = (f"Implement two exports for Node.js: `sleep(ms)` (a Promise resolved "
                f"via setTimeout) and `{fn}(jobs)`, which starts every job "
                f"concurrently with Promise.all and resolves to the job labels in "
                f"INPUT order, never completion order. Each job is an object with "
                f"`label` and `ms` fields; an empty job list resolves to [].")
        expected = (f"With delays {delays} ms the jobs settle in the order "
                    f"{list(reversed(labels))}, yet Promise.all still resolves to "
                    f"{labels} because it preserves input positions.")
        explain = _explain(
            expected,
            "Map each job to a delay promise, hand the array to Promise.all, and "
            "await it; positional order is guaranteed by the spec.",
            ["Promise.all preserves the input order regardless of settle order",
             "one rejected element rejects the whole aggregation",
             "sleep wraps setTimeout so fake latency stays short and deterministic"],
            "O(n) promises, bounded by the longest delay", "O(n)",
            ["empty input resolves to [] without touching timers",
             "a slower first job must not reorder the resolved array"])
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected, explain=explain)

    def _build_sequence(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["runSequence", "processSteps", "awaitEach"])
        names = ["resize-images", "purge-cache", "send-digest", "rotate-keys",
                 "prune-logs"]
        chosen = rng.sample(names, 3)
        delays = sorted(rng.sample([2, 3, 5, 8, 13, 18], 3), reverse=True)
        steps = [{"name": nm, "ms": d} for nm, d in zip(chosen, delays)]
        steps_js = json.dumps(steps)
        names_js = json.dumps(chosen)
        code = _fill(
            "// Deterministic fake I/O: a setTimeout-based delay promise.\n"
            "function sleep(ms) {\n"
            "  return new Promise((resolve) => setTimeout(resolve, ms));\n"
            "}\n\n"
            "// Run steps strictly one after another, awaiting each fake delay.\n"
            "async function {fn}(steps) {\n"
            "  const completed = [];\n"
            "  for (const step of steps) {\n"
            "    await sleep(step.ms);\n"
            "    completed.push(step.name);\n"
            "  }\n"
            "  return completed;\n"
            "}\n\n"
            "module.exports = { sleep, {fn} };\n",
            fn=fn)
        tests = _fill(
            "async function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  const steps = {steps};\n"
            "  assert.deepStrictEqual(await {fn}(steps), {names});\n"
            "  assert.deepStrictEqual(await {fn}([]), []);\n"
            "  const single = await {fn}([{ name: 'only', ms: 1 }]);\n"
            "  assert.deepStrictEqual(single, ['only']);\n"
            "}\n",
            fn=fn, steps=steps_js, names=names_js)
        task = (f"Implement two exports for Node.js: `sleep(ms)` (setTimeout-based) "
                f"and `{fn}(steps)`, which awaits each step's fake delay one after "
                f"another and returns the step names strictly in input order. Each "
                f"step is an object with `name` and `ms` fields; the sequence must "
                f"not start a later step before the earlier one settles.")
        expected = (f"Steps {chosen} run back to back: even though their delays "
                    f"{delays} ms would complete in reverse order if parallelised, "
                    f"the awaited loop reports {chosen}.")
        explain = _explain(
            expected,
            "A for..of loop with await inside the body serialises the steps; the "
            "completed log is appended only after each await settles.",
            ["await inside the loop body is what enforces sequencing",
             "results append in loop order, so input order == output order",
             "an empty step list returns [] and never schedules a timer"],
            "O(n) steps plus the sum of all delays", "O(n)",
            ["empty input returns [] without any timer",
             "a slow first step delays every later step (by design)"])
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected, explain=explain)

    def _build_retry(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["withRetry", "attemptUntil", "retryTask"])
        attempts = rng.randint(3, 5)
        fails = rng.randint(1, attempts - 1)
        attempts2 = rng.randint(2, 4)
        code = _fill(
            "// Deterministic fake I/O: a setTimeout-based delay promise.\n"
            "function sleep(ms) {\n"
            "  return new Promise((resolve) => setTimeout(resolve, ms));\n"
            "}\n\n"
            "// Await task(attemptNo); retry after 1ms on rejection, at most\n"
            "// `attempts` total attempts, then rethrow the last error.\n"
            "async function {fn}(task, attempts) {\n"
            "  let lastError = null;\n"
            "  for (let attempt = 1; attempt <= attempts; attempt++) {\n"
            "    try {\n"
            "      return await task(attempt);\n"
            "    } catch (err) {\n"
            "      lastError = err;\n"
            "      if (attempt < attempts) {\n"
            "        await sleep(1);\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  throw lastError;\n"
            "}\n\n"
            "module.exports = { sleep, {fn} };\n",
            fn=fn)
        tests = _fill(
            "async function runTests(solution) {\n"
            "  const { {fn} } = solution;\n"
            "  let calls = 0;\n"
            "  const flaky = async () => {\n"
            "    calls += 1;\n"
            "    if (calls <= {fails}) {\n"
            "      throw new Error('transient-' + calls);\n"
            "    }\n"
            "    return 'ok';\n"
            "  };\n"
            "  assert.strictEqual(await {fn}(flaky, {attempts}), 'ok');\n"
            "  assert.strictEqual(calls, {needed});\n"
            "  let always = 0;\n"
            "  const doomed = async () => {\n"
            "    always += 1;\n"
            "    throw new Error('permanent');\n"
            "  };\n"
            "  let caught = '';\n"
            "  try {\n"
            "    await {fn}(doomed, {attempts2});\n"
            "  } catch (err) {\n"
            "    caught = err.message;\n"
            "  }\n"
            "  assert.strictEqual(caught, 'permanent');\n"
            "  assert.strictEqual(always, {attempts2});\n"
            "}\n",
            fn=fn, fails=fails, attempts=attempts, needed=fails + 1,
            attempts2=attempts2)
        task = (f"Implement two exports for Node.js: `sleep(ms)` (setTimeout-based) "
                f"and `{fn}(task, attempts)`, a retry helper that awaits "
                f"`task(attemptNo)`, waits 1 ms between tries, and gives up after "
                f"`attempts` total attempts by rethrowing the last error. The first "
                f"successful attempt must return its value immediately.")
        expected = (f"A task failing {fails} time(s) then succeeding resolves to "
                    f"'ok' after {fails + 1} calls; a permanently failing task is "
                    f"called exactly `attempts` times and its error propagates.")
        explain = _explain(
            expected,
            "Counting loop with try/catch around `await task(attempt)`; the loop "
            "index doubles as the attempt number passed to the task.",
            ["return await propagates the resolved value out of the try block",
             "the 1 ms sleep between attempts keeps backoff deterministic",
             "throwing lastError after the loop surfaces the real failure cause"],
            "O(attempts) task invocations", "O(1)",
            ["task succeeding on attempt 1 never sleeps",
             "exhausted attempts rethrow the most recent error unchanged"])
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected, explain=explain)

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "function_name": b["fn"], "explain": b["explain"]},
            tags=["javascript", "async", kind], variant=kind,
            seed=rng.randrange(2 ** 31))


class JavaScriptWebHttpFamily(Family):
    """Pure Node http request handlers exercised with fake req/res objects."""
    NAME = "js_web_http"
    LANGUAGE = "javascript"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "code_review", "comparison")

    KINDS = ("minimal", "method_aware", "validating")

    def _build(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["handle", "handleRequest", "route"])
        a = rng.randint(-20, 60)
        b = rng.randint(-20, 60)
        total = a + b
        method_guard = ""
        if kind == "method_aware":
            method_guard = (
                "  if (req.method !== 'GET') {\n"
                "    res.statusCode = 405;\n"
                "    res.setHeader('Allow', 'GET');\n"
                "    res.end('method not allowed');\n"
                "    return;\n"
                "  }\n")
        sum_guard = ""
        if kind == "validating":
            sum_guard = (
                "    if (!url.searchParams.has('a') || !url.searchParams.has('b') ||\n"
                "        Number.isNaN(a) || Number.isNaN(b)) {\n"
                "      res.statusCode = 400;\n"
                "      res.setHeader('Content-Type', 'text/plain; charset=utf-8');\n"
                "      res.end('bad request');\n"
                "      return;\n"
                "    }\n")
        code = _fill(
            "// Pure request handler: no sockets, no server — req in, res out.\n"
            "// Compatible with http.createServer(handler) but tests drive it\n"
            "// directly with plain objects.\n"
            "function {fn}(req, res) {\n"
            "  const url = new URL(req.url, 'http://localhost');\n"
            "{method_guard}"
            "  if (url.pathname === '/ping') {\n"
            "    res.statusCode = 200;\n"
            "    res.setHeader('Content-Type', 'text/plain; charset=utf-8');\n"
            "    res.end('pong');\n"
            "    return;\n"
            "  }\n"
            "  if (url.pathname === '/sum') {\n"
            "    const a = Number(url.searchParams.get('a'));\n"
            "    const b = Number(url.searchParams.get('b'));\n"
            "{sum_guard}"
            "    res.statusCode = 200;\n"
            "    res.setHeader('Content-Type', 'text/plain; charset=utf-8');\n"
            "    res.end(String(a + b));\n"
            "    return;\n"
            "  }\n"
            "  res.statusCode = 404;\n"
            "  res.setHeader('Content-Type', 'text/plain; charset=utf-8');\n"
            "  res.end('not found');\n"
            "}\n\n"
            "module.exports = { {fn} };\n",
            fn=fn, method_guard=method_guard, sum_guard=sum_guard)

        common = (
            "function runTests(solution) {\n"
            "  const { " + fn + " } = solution;\n"
            "  function fakeRes() {\n"
            "    return {\n"
            "      statusCode: 0,\n"
            "      headers: {},\n"
            "      body: '',\n"
            "      setHeader(name, value) { this.headers[name] = value; },\n"
            "      end(chunk) { this.body = chunk === undefined ? '' : String(chunk); },\n"
            "    };\n"
            "  }\n")
        tests = common + _fill(
            "  let res = fakeRes();\n"
            "  {fn}({ method: 'GET', url: '/ping' }, res);\n"
            "  assert.strictEqual(res.statusCode, 200);\n"
            "  assert.strictEqual(res.body, 'pong');\n"
            "  assert.strictEqual(res.headers['Content-Type'],\n"
            "                     'text/plain; charset=utf-8');\n"
            "  res = fakeRes();\n"
            "  {fn}({ method: 'GET', url: '/sum?a={a}&b={b}' }, res);\n"
            "  assert.strictEqual(res.statusCode, 200);\n"
            "  assert.strictEqual(res.body, '{total}');\n"
            "  res = fakeRes();\n"
            "  {fn}({ method: 'GET', url: '/nope' }, res);\n"
            "  assert.strictEqual(res.statusCode, 404);\n",
            fn=fn, a=a, b=b, total=total)
        if kind == "method_aware":
            tests += _fill(
                "  res = fakeRes();\n"
                "  {fn}({ method: 'POST', url: '/ping' }, res);\n"
                "  assert.strictEqual(res.statusCode, 405);\n"
                "  assert.strictEqual(res.headers['Allow'], 'GET');\n",
                fn=fn)
        if kind == "validating":
            tests += _fill(
                "  res = fakeRes();\n"
                "  {fn}({ method: 'GET', url: '/sum?a=x&b=1' }, res);\n"
                "  assert.strictEqual(res.statusCode, 400);\n"
                "  res = fakeRes();\n"
                "  {fn}({ method: 'GET', url: '/sum' }, res);\n"
                "  assert.strictEqual(res.statusCode, 400);\n",
                fn=fn)
        tests += "}\n"

        extras = {
            "minimal": "unknown paths fall through to 404.",
            "method_aware": "non-GET requests are rejected with 405 plus an Allow header, and unknown paths fall through to 404.",
            "validating": "missing or non-numeric query parameters answer 400 before any arithmetic, and unknown paths fall through to 404.",
        }
        task = (f"Implement a pure Node.js request-handler function `{fn}(req, res)` "
                f"shaped for http.createServer but verified without sockets: route "
                f"GET /ping to a 200 'pong' text response and GET /sum?a=&b= to a "
                f"200 response containing a + b; {extras[kind]} Parse the target "
                f"with the URL global and drive responses via res.statusCode, "
                f"res.setHeader and res.end.")
        expected = (f"GET /ping answers 200 'pong'; GET /sum?a={a}&b={b} answers "
                    f"200 '{total}'; the handler never touches net code, so tests "
                    f"use plain fake req/res objects. {extras[kind][0].upper()}"
                    f"{extras[kind][1:]}")
        explain = _explain(
            expected,
            "Parse req.url with the URL global, dispatch on pathname, set status "
            "plus headers, then res.end the payload and return early.",
            ["the handler is pure: it only reads req and writes via the res API",
             "new URL(req.url, base) separates pathname from searchParams safely",
             "early returns after res.end keep one response per request"],
            "O(1) per request", "O(1)",
            ["unknown pathname must yield 404 rather than crash",
             "query values arrive as strings and must be converted with Number()",
             *(["non-GET methods get 405 with an Allow header"]
               if kind == "method_aware" else []),
             *(["absent or NaN query params get 400 instead of NaN output"]
               if kind == "validating" else [])])
        return dict(kind=kind, fn=fn, code=code, tests=tests, task=task,
                    expected=expected, explain=explain)

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "function_name": b["fn"], "explain": b["explain"]},
            tags=["javascript", "web", "http", kind], variant=kind,
            seed=rng.randrange(2 ** 31))


class JavaScriptProjectFamily(Family):
    """Multi-file Node project: solution.js + lib/mathx.js + test + README."""
    NAME = "js_project_multifile"
    LANGUAGE = "javascript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    PROJECTS = ("stats", "fractions", "grades")

    def _mathx_stats(self) -> str:
        return (
            "'use strict';\n\n"
            "// Small numeric helpers shared by the public API.\n\n"
            "function round2(x) {\n"
            "  return Math.round(x * 100) / 100;\n"
            "}\n\n"
            "function mean(values) {\n"
            "  if (values.length === 0) {\n"
            "    throw new RangeError('mean of empty array');\n"
            "  }\n"
            "  return round2(values.reduce((acc, x) => acc + x, 0) / values.length);\n"
            "}\n\n"
            "function median(values) {\n"
            "  if (values.length === 0) {\n"
            "    throw new RangeError('median of empty array');\n"
            "  }\n"
            "  const ordered = values.slice().sort((a, b) => a - b);\n"
            "  const mid = ordered.length >> 1;\n"
            "  return ordered.length % 2 === 1\n"
            "    ? ordered[mid]\n"
            "    : round2((ordered[mid - 1] + ordered[mid]) / 2);\n"
            "}\n\n"
            "function spread(values) {\n"
            "  if (values.length === 0) {\n"
            "    throw new RangeError('spread of empty array');\n"
            "  }\n"
            "  return round2(Math.max.apply(null, values) - Math.min.apply(null, values));\n"
            "}\n\n"
            "module.exports = { round2, mean, median, spread };\n")

    def _mathx_fractions(self) -> str:
        return (
            "'use strict';\n\n"
            "// Integer helpers for ratio arithmetic.\n\n"
            "function gcd(a, b) {\n"
            "  let x = Math.abs(a);\n"
            "  let y = Math.abs(b);\n"
            "  while (y !== 0) {\n"
            "    const r = x % y;\n"
            "    x = y;\n"
            "    y = r;\n"
            "  }\n"
            "  return x;\n"
            "}\n\n"
            "function lcm(a, b) {\n"
            "  if (a === 0 || b === 0) {\n"
            "    return 0;\n"
            "  }\n"
            "  return Math.abs(a) / gcd(a, b) * Math.abs(b);\n"
            "}\n\n"
            "module.exports = { gcd, lcm };\n")

    def _mathx_grades(self) -> str:
        return (
            "'use strict';\n\n"
            "// Grading scale helpers.\n\n"
            "function mean(values) {\n"
            "  if (values.length === 0) {\n"
            "    throw new RangeError('mean of empty array');\n"
            "  }\n"
            "  return Math.round(values.reduce((acc, x) => acc + x, 0)\n"
            "    / values.length * 100) / 100;\n"
            "}\n\n"
            "function letterFor(score) {\n"
            "  if (score >= 90) return 'A';\n"
            "  if (score >= 80) return 'B';\n"
            "  if (score >= 70) return 'C';\n"
            "  if (score >= 60) return 'D';\n"
            "  return 'F';\n"
            "}\n\n"
            "module.exports = { mean, letterFor };\n")

    def _build(self, proj: str, rng: random.Random):
        readme_title = {"stats": "sample-stats", "fractions": "ratio-toolkit",
                        "grades": "grade-reporter"}[proj]
        if proj == "stats":
            count = rng.choice([2, 4, 5, 10])  # keeps means at exact 2 decimals
            values = sorted(rng.randint(1, 99) for _ in range(count))
            values[0] = rng.randint(1, 9)  # decorrelate order from value
            s = sum(values)
            mean_v = round(s * 100 / count) / 100
            ordered = sorted(values)
            mid = len(ordered) // 2
            med = (ordered[mid] if count % 2
                   else round((ordered[mid - 1] + ordered[mid]) * 50) / 100)
            spr = ordered[-1] - ordered[0]
            summary = {"count": count, "mean": mean_v, "median": med, "spread": spr}
            solution = (
                "'use strict';\n\n"
                "const { mean, median, spread } = require('./lib/mathx.js');\n\n"
                "// Public API: one-call summary over a batch of numeric samples.\n"
                "function summarize(values) {\n"
                "  return {\n"
                "    count: values.length,\n"
                "    mean: mean(values),\n"
                "    median: median(values),\n"
                "    spread: spread(values),\n"
                "  };\n"
                "}\n\n"
                "module.exports = { summarize, mean, median, spread };\n")
            tests = (
                "function runTests(solution) {\n"
                f"  const {{ summarize }} = solution;\n"
                f"  assert.deepStrictEqual(summarize({json.dumps(values)}),\n"
                f"                         {json.dumps(summary)});\n"
                "  assert.deepStrictEqual(summarize([7, 9]),\n"
                "                         { count: 2, mean: 8, median: 8, spread: 2 });\n"
                "  assert.throws(() => summarize([]), RangeError);\n"
                "}\n")
            standalone = (
                "const assert = require('assert');\n"
                "const { summarize } = require('../solution.js');\n\n"
                f"assert.deepStrictEqual(summarize({json.dumps(values)}),\n"
                f"                       {json.dumps(summary)});\n"
                "assert.throws(() => summarize([]), RangeError);\n"
                "console.log('test/solution.test.js: all checks passed');\n")
            expected = (f"summarize({values}) returns {json.dumps(summary)}; the "
                        f"empty array throws RangeError.")
            task = (f"Build the multi-file Node.js project '{readme_title}' exactly "
                    f"as the README describes: lib/mathx.js provides round2, mean, "
                    f"median and spread helpers, and solution.js re-exports them "
                    f"behind a summarize(values) function that returns an object "
                    f"with count, mean, median and spread fields. Behaviour: "
                    f"{expected} The bundled test harness must pass.")
        elif proj == "fractions":
            num, den = rng.choice([(6, 8), (10, 15), (9, 12), (14, 21), (8, 20)])
            g = 1
            x, y = num, den
            while y:
                x, y = y, x % y
            g = x
            ratio = f"{num // g}/{den // g}"
            solution = (
                "'use strict';\n\n"
                "const { gcd, lcm } = require('./lib/mathx.js');\n\n"
                "// Public API: reduce a ratio to lowest terms as 'numerator/denominator'.\n"
                "function ratioText(a, b) {\n"
                "  if (b === 0) {\n"
                "    throw new RangeError('denominator must not be zero');\n"
                "  }\n"
                "  const d = gcd(a, b);\n"
                "  return (a / d) + '/' + (b / d);\n"
                "}\n\n"
                "module.exports = { ratioText, gcd, lcm };\n")
            tests = (
                "function runTests(solution) {\n"
                "  const { ratioText, gcd, lcm } = solution;\n"
                f"  assert.strictEqual(ratioText({num}, {den}), '{ratio}');\n"
                f"  assert.strictEqual(gcd({num}, {den}), {g});\n"
                "  assert.strictEqual(gcd(0, 5), 5);\n"
                "  assert.strictEqual(lcm(4, 6), 12);\n"
                "  assert.strictEqual(ratioText(7, 13), '7/13');\n"
                "  assert.throws(() => ratioText(3, 0), RangeError);\n"
                "}\n")
            standalone = (
                "const assert = require('assert');\n"
                "const { ratioText, gcd } = require('../solution.js');\n\n"
                f"assert.strictEqual(ratioText({num}, {den}), '{ratio}');\n"
                f"assert.strictEqual(gcd({num}, {den}), {g});\n"
                "assert.strictEqual(ratioText(7, 13), '7/13');\n"
                "console.log('test/solution.test.js: all checks passed');\n")
            expected = (f"ratioText({num}, {den}) returns '{ratio}' because "
                        f"gcd({num}, {den}) = {g}; a zero denominator throws "
                        f"RangeError.")
            task = (f"Create the multi-file Node.js project '{readme_title}' from "
                    f"its README: lib/mathx.js implements gcd and lcm, and "
                    f"solution.js exposes ratioText(a, b) that reduces a ratio to "
                    f"lowest terms and returns it as a 'numerator/denominator' "
                    f"string, re-exporting the helpers. Behaviour: {expected} The "
                    f"bundled test harness must pass.")
        else:  # grades
            count = rng.choice([2, 4, 5, 10])
            scores = [rng.randint(55, 99) for _ in range(count)]
            avg = round(sum(scores) * 100 / count) / 100
            letter = ("A" if avg >= 90 else "B" if avg >= 80
                      else "C" if avg >= 70 else "D" if avg >= 60 else "F")
            report = {"count": count, "average": avg, "letter": letter}
            solution = (
                "'use strict';\n\n"
                "const { mean, letterFor } = require('./lib/mathx.js');\n\n"
                "// Public API: aggregate a batch of scores into one report object.\n"
                "function gradeReport(scores) {\n"
                "  const average = mean(scores);\n"
                "  return {\n"
                "    count: scores.length,\n"
                "    average: average,\n"
                "    letter: letterFor(average),\n"
                "  };\n"
                "}\n\n"
                "module.exports = { gradeReport, letterFor };\n")
            tests = (
                "function runTests(solution) {\n"
                "  const { gradeReport, letterFor } = solution;\n"
                f"  assert.deepStrictEqual(gradeReport({json.dumps(scores)}),\n"
                f"                         {json.dumps(report)});\n"
                "  assert.strictEqual(letterFor(90), 'A');\n"
                "  assert.strictEqual(letterFor(89.9), 'B');\n"
                "  assert.strictEqual(letterFor(59.5), 'F');\n"
                "  assert.throws(() => gradeReport([]), RangeError);\n"
                "}\n")
            standalone = (
                "const assert = require('assert');\n"
                "const { gradeReport, letterFor } = require('../solution.js');\n\n"
                f"assert.deepStrictEqual(gradeReport({json.dumps(scores)}),\n"
                f"                       {json.dumps(report)});\n"
                "assert.strictEqual(letterFor(85), 'B');\n"
                "console.log('test/solution.test.js: all checks passed');\n")
            expected = (f"gradeReport({scores}) returns {json.dumps(report)} using "
                        f"the fixed A-F thresholds (90/80/70/60); an empty batch "
                        f"throws RangeError.")
            task = (f"Implement the multi-file Node.js project '{readme_title}': "
                    f"lib/mathx.js carries the mean and letterFor helpers (fixed "
                    f"thresholds 90/80/70/60 for A/B/C/D), while solution.js "
                    f"publishes gradeReport(scores) returning count, rounded "
                    f"average and letter grade. Behaviour: {expected} The bundled "
                    f"test harness must pass.")
        readme = (
            f"# {readme_title}\n\n"
            f"Tiny Node.js (CommonJS) project demonstrating a library + public API "
            f"split.\n\n"
            "## Layout\n\n"
            "- `solution.js` - public entry point; re-exports the API built on the lib\n"
            "- `lib/mathx.js` - focused helpers, no knowledge of the public API\n"
            "- `test/solution.test.js` - standalone assert-based checks\n\n"
            "## Usage\n\n"
            "```js\n"
            f"const api = require('./solution.js');\n"
            "```\n\n"
            "## Verify\n\n"
            "Run `node test/solution.test.js`; the pipeline harness drives the same "
            "checks through `runTests(solution)`.\n")
        files = [
            FileSpec("solution.js", solution),
            FileSpec("lib/mathx.js", self._mathx_stats() if proj == "stats"
                     else self._mathx_fractions() if proj == "fractions"
                     else self._mathx_grades()),
            FileSpec("test/solution.test.js", standalone),
            FileSpec("README.md", readme),
        ]
        return dict(proj=proj, files=files, solution=solution, tests=tests,
                    task=task, expected=expected)

    def generate(self, rng: random.Random) -> Candidate:
        proj = rng.choice(self.PROJECTS)
        b = self._build(proj, rng)
        return Candidate(
            family=self.NAME, language="javascript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            files=b["files"], entry="solution.js", tests=b["tests"],
            verify_method="executed", is_project=True,
            notes={"project": proj,
                   "explain": _explain(
                       b["expected"],
                       "Layered layout: lib helpers stay dumb and pure, solution.js "
                       "composes them into the public API, tests pin behaviour.",
                       ["module.exports exposes only the public surface",
                        "the lib module has no dependency on the entry file",
                        "tests assert both happy paths and thrown RangeErrors"],
                       "O(n) over the input batch", "O(n)",
                       ["empty input throws RangeError instead of returning NaN",
                        "median handles even and odd batch lengths"])},
            tags=["javascript", "project", proj], variant=proj,
            seed=rng.randrange(2 ** 31))


register(globals(), JavaScriptBankFamily)
register(globals(), JavaScriptArrayTransformsFamily)
register(globals(), JavaScriptAsyncPatternsFamily)
register(globals(), JavaScriptWebHttpFamily)
register(globals(), JavaScriptProjectFamily)
