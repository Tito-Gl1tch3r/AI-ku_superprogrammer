"""Dataset-1 write families for TypeScript (Node.js native type stripping).

CRITICAL (see validators/executors/ts_exec.py + CONTRACT.md):
  * ONLY erasable TypeScript: type annotations, interfaces, type aliases,
    generics, `import type`. NO enums, namespaces, parameter properties or
    `const enum` (they need a real transform, not stripping).
  * solution.ts exports values via `export function ...`; type-only imports
    from sibling modules MUST use `import type` so they are fully erased.
  * The harness imports the solution from a temporary .mjs wrapper, so the
    `tests` snippet itself must stay plain JavaScript. The contract's typed
    signature is documented with a JSDoc annotation, which is valid in .mjs:
    `@param {typeof import('./solution.ts')} solution`.
  * Type imports reference sibling files as './types.ts' (explicit extension,
    as required by Node's type-stripping loader).
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, Family, FileSpec, register


def _fill(template: str, **kw) -> str:
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


def _tests_snippet(body: str) -> str:
    """Wrap a plain-JS test body in the harness-conventional runTests shape."""
    return (
        "/**\n"
        " * @param {typeof import('./solution.ts')} solution\n"
        " */\n"
        "function runTests(solution) {\n"
        + body
        + "}\n")


class TSTypedUtilitiesFamily(Family):
    """Generic utilities with constraints, unions, ReadonlyArray results."""
    NAME = "ts_typed_utilities"
    LANGUAGE = "typescript"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging", "complexity", "code_review")

    KINDS = ("first_or_default", "group_by", "pluck", "result_helpers")

    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "first_or_default":
            return self._build_first_or_default(kind, rng)
        if kind == "group_by":
            return self._build_group_by(kind, rng)
        if kind == "pluck":
            return self._build_pluck(kind, rng)
        return self._build_result_helpers(kind, rng)

    def _build_first_or_default(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["firstOrDefault", "firstMatching", "pickFirst"])
        n = rng.randint(5, 9)
        data = [rng.randint(1, 99) for _ in range(n)]
        threshold = data[0]  # the first element always matches -> first is the answer
        later = [x for x in data[1:] if x >= threshold]
        fallback = rng.randint(1, 99)
        code = (
            "// Return the first element matching the predicate, else the fallback.\n"
            f"export function {fn}<T>(items: ReadonlyArray<T>,\n"
            "                        predicate: (item: T) => boolean,\n"
            "                        fallback: T): T {\n"
            "  for (let i = 0; i < items.length; i++) {\n"
            "    if (predicate(items[i])) {\n"
            "      return items[i];\n"
            "    }\n"
            "  }\n"
            "  return fallback;\n"
            "}\n")
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const values = {json.dumps(data)};\n"
            f"  assert.strictEqual({fn}(values, (x) => x >= {threshold}, {fallback}),\n"
            f"                     {data[0]});\n"
            f"  assert.strictEqual({fn}([], (x) => x > 0, {fallback}), {fallback});\n"
            f"  assert.strictEqual({fn}(values, (x) => x > 500, {fallback}),\n"
            f"                     {fallback});\n")
        task = (f"Implement a generic TypeScript utility `{fn}<T>(items, predicate, "
                f"fallback)` that scans a ReadonlyArray<T> and returns the first "
                f"element satisfying the predicate, or the caller's fallback value "
                f"when nothing matches or the array is empty. Keep the signature "
                f"fully generic and annotate the parameter as ReadonlyArray.")
        expected = (f"For values {data} with predicate x >= {threshold} the answer is "
                    f"{data[0]} (the very first element); empty or fully-unmatched "
                    f"inputs return the fallback {fallback}.")
        explain = _explain(
            expected,
            "Single indexed loop with an early return; generics keep the element "
            "type flowing from the array into the predicate and result.",
            ["ReadonlyArray<T> in the signature promises not to mutate the input",
             "the fallback parameter gives callers a typed default value",
             "the loop returns on the first match, never scanning the rest"],
            "O(n)", "O(1)",
            ["empty array returns the fallback untouched",
             "a predicate matching nothing also returns the fallback",
             "the first match wins even if later elements match too"])
        bugs = {
            "skips_first_element": lambda c: c.replace(
                "for (let i = 0; i < items.length; i++) {",
                "for (let i = 1; i < items.length; i++) {"),
            "fallback_shadows_match": lambda c: c.replace(
                "      return items[i];\n", "      return fallback;\n"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain, bugs=bugs)

    def _build_group_by(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["groupBy", "bucketBy", "partitionByKey"])
        names = ["ada", "grace", "linus", "margaret", "alan", "barbara"]
        depts = rng.sample(["platform", "billing", "research", "ops"],
                           rng.randint(2, 3))
        n = rng.randint(5, 9)
        people = [{"name": rng.choice(names), "dept": rng.choice(depts)}
                  for _ in range(n)]
        groups: dict = {}
        for p in people:
            groups.setdefault(p["dept"], []).append(p)
        code = (
            "// Group items by a caller-supplied string key function.\n"
            "export function " + fn + "<T, K extends string>(\n"
            "  items: ReadonlyArray<T>,\n"
            "  keyFn: (item: T) => K,\n"
            "): Record<K, T[]> {\n"
            "  const groups: Partial<Record<K, T[]>> = {};\n"
            "  for (const item of items) {\n"
            "    const key = keyFn(item);\n"
            "    const bucket = groups[key];\n"
            "    if (bucket === undefined) {\n"
            "      groups[key] = [item];\n"
            "    } else {\n"
            "      bucket.push(item);\n"
            "    }\n"
            "  }\n"
            "  return groups as Record<K, T[]>;\n"
            "}\n")
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const people = {json.dumps(people)};\n"
            f"  assert.deepStrictEqual({fn}(people, (p) => p.dept),\n"
            f"                         {json.dumps(groups)});\n"
            f"  assert.deepStrictEqual({fn}([], (p) => p.dept), {{}});\n"
            f"  assert.deepStrictEqual({fn}([{{ name: 'solo', dept: 'ops' }}],\n"
            "                              (p) => p.dept),\n"
            "                         { ops: [{ name: 'solo', dept: 'ops' }] });\n")
        task = (f"Implement a generic TypeScript helper `{fn}<T, K extends string>"
                f"(items, keyFn)` that groups a ReadonlyArray<T> into a Record<K, "
                f"T[]> using a key function, preserving input order inside each "
                f"bucket and first-seen order across keys. Constrain K to string "
                f"and keep every annotation erasable.")
        expected = (f"Grouping {len(people)} people by department yields "
                    f"{len(groups)} buckets ({', '.join(sorted(groups))}); an empty "
                    f"array yields an empty record.")
        explain = _explain(
            expected,
            "One pass with an accumulator record; each key's bucket is created on "
            "first sight and pushed to afterwards.",
            ["K extends string keeps record keys static and autocomplete-friendly",
             "Partial<Record<K, T[]>> models the half-built accumulator honestly",
             "a single cast at the return boundary documents the invariant"],
            "O(n)", "O(n)",
            ["empty input returns an empty record",
             "a one-element input creates exactly one singleton bucket",
             "duplicate keys append in input order"])
        bugs = {
            "group_overwrite": lambda c: c.replace(
                "    if (bucket === undefined) {\n"
                "      groups[key] = [item];\n"
                "    } else {\n"
                "      bucket.push(item);\n"
                "    }\n",
                "    groups[key] = [item];\n"),
            "pushes_item_field": lambda c: c.replace(
                "      bucket.push(item);\n", "      bucket.push(item.name);\n"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain, bugs=bugs)

    def _build_pluck(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["pluck", "pickField", "columnOf"])
        rows = []
        for _ in range(rng.randint(4, 7)):
            rows.append({"id": rng.choice(["a", "b", "c", "d"])
                         + str(rng.randint(1, 9)),
                         "score": rng.randint(10, 99),
                         "active": rng.choice([True, False])})
        field = rng.choice(["score", "id"])
        expected = [r[field] for r in rows]
        code = (
            "// Extract one property from every item, typed by keyof.\n"
            "export function " + fn + "<T, K extends keyof T>(\n"
            "  items: ReadonlyArray<T>,\n"
            "  key: K,\n"
            "): T[K][] {\n"
            "  return items.map((item: T) => item[key]);\n"
            "}\n")
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const rows = {json.dumps(rows)};\n"
            f"  assert.deepStrictEqual({fn}(rows, '{field}'),\n"
            f"                         {json.dumps(expected)});\n"
            f"  assert.deepStrictEqual({fn}([], 'score'), []);\n"
            f"  assert.deepStrictEqual({fn}(rows, 'active'),\n"
            f"                         {json.dumps([r['active'] for r in rows])});\n")
        task = (f"Implement a generic TypeScript helper `{fn}<T, K extends keyof T>"
                f"(items, key)` that maps a ReadonlyArray<T> to an array of the "
                f"given property values, typed as T[K][], so the compiler ties the "
                f"allowed keys to the element type. An empty array maps to an "
                f"empty array.")
        expected = (f"Selecting the '{field}' column from {len(rows)} rows returns "
                    f"{expected}; keyof constrains callers to real field names.")
        explain = _explain(
            expected,
            "A single map over the readonly input; the keyof constraint connects "
            "the key argument to the element type at compile time.",
            ["K extends keyof T rejects typos in the property name at compile time",
             "the result element type T[K] stays precise per key",
             "map returns a fresh array, honouring the readonly input"],
            "O(n)", "O(n)",
            ["empty input maps to an empty array",
             "boolean and string fields are extracted identically"])
        bugs = {
            "returns_key_not_value": lambda c: c.replace(
                "  return items.map((item: T) => item[key]);",
                "  return items.map(() => key);"),
            "drops_first_row": lambda c: c.replace(
                "  return items.map((item: T) => item[key]);",
                "  return items.slice(1).map((item: T) => item[key]);"),
        }
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain, bugs=bugs)

    def _build_result_helpers(self, kind: str, rng: random.Random) -> dict:
        ok_name = rng.choice(["succeed", "okResult", "pass"])
        err_name = rng.choice(["fail", "errResult", "reject"])
        unwrap_name = rng.choice(["unwrapOr", "getValueOr", "resultOr"])
        value = rng.randint(1, 99)
        message = rng.choice(["not found", "bad input", "out of range"])
        code = (
            "/** Discriminated union: check `ok` to narrow the shape. */\n"
            "export type Result<T> =\n"
            "  | { ok: true; value: T }\n"
            "  | { ok: false; error: string };\n\n"
            f"export function {ok_name}<T>(value: T): Result<T> {{\n"
            "  return { ok: true, value };\n"
            "}\n\n"
            f"export function {err_name}<T>(error: string): Result<T> {{\n"
            "  return { ok: false, error };\n"
            "}\n\n"
            f"export function {unwrap_name}<T>(result: Result<T>, fallback: T): T {{\n"
            "  return result.ok ? result.value : fallback;\n"
            "}\n")
        body = (
            f"  const {{ {ok_name}, {err_name}, {unwrap_name} }} = solution;\n"
            f"  const good = {ok_name}({value});\n"
            "  assert.strictEqual(good.ok, true);\n"
            f"  assert.strictEqual(good.value, {value});\n"
            f"  const bad = {err_name}('{message}');\n"
            "  assert.strictEqual(bad.ok, false);\n"
            f"  assert.strictEqual(bad.error, '{message}');\n"
            f"  assert.strictEqual({unwrap_name}(good, 0), {value});\n"
            f"  assert.strictEqual({unwrap_name}(bad, 0), 0);\n")
        task = (f"Implement a TypeScript result toolkit: a discriminated-union type "
                f"`Result<T>` with an ok branch carrying `value` and a failed branch "
                f"carrying `error`, plus constructors `{ok_name}` and `{err_name}` "
                f"and a `{unwrap_name}(result, fallback)` combinator that returns "
                f"the wrapped value only when ok is true. All shapes must be "
                f"erasable syntax.")
        expected = (f"{ok_name}({value}) yields {{ok: true, value: {value}}}; "
                    f"{err_name}('{message}') yields the error branch; unwrapOr "
                    f"narrows via the ok discriminant and returns the fallback for "
                    f"failures.")
        explain = _explain(
            expected,
            "A tagged union with a boolean discriminant plus tiny smart constructors; "
            "unwrapOr narrows with a plain conditional on result.ok.",
            ["checking `ok` is what narrows the union to the value branch",
             "err_name is generic so the same helper serves every T",
             "the fallback branch keeps failure handling total (no throws)"],
            "O(1)", "O(1)",
            ["a failed result has no value field to read",
             "unwrapOr never throws; it routes to the fallback instead"])
        bugs = {
            "swapped_unwrap_branches": lambda c: c.replace(
                "  return result.ok ? result.value : fallback;",
                "  return result.ok ? fallback : result.value;"),
            "ok_branch_drops_value": lambda c: c.replace(
                "  return { ok: true, value };\n",
                "  return { ok: true, value: 0 };\n"),
        }
        return dict(kind=kind, fn=unwrap_name, code=code,
                    tests=_tests_snippet(body), task=task, expected=expected,
                    explain=explain, bugs=bugs)

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "explain": b["explain"]},
            tags=["typescript", "generics", kind], variant=kind,
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        bug_kind = rng.choice(sorted(b["bugs"]))
        buggy_code = b["bugs"][bug_kind](b["code"])
        if buggy_code == b["code"]:
            return None
        cand = Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty="intermediate",
            task=b["task"], expected_behavior="See question.",
            code=buggy_code, tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "bug_kind": bug_kind, "correct_code": b["code"],
                   "explain": b["explain"]},
            tags=["typescript", "generics", kind, "bug"],
            variant=f"{kind}|bug|{bug_kind}", seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "problem": self.NAME, "correct_code": b["code"],
                "tests": b["tests"], "unit_notes": b["explain"]}
        return cand, meta


class TSModelValidationFamily(Family):
    """Validation returning discriminated unions for typed domain models."""
    NAME = "ts_model_validation"
    LANGUAGE = "typescript"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "code_review", "security")

    KINDS = ("user_account", "order", "range_config")

    RESULT_TYPE = (
        "export type ValidationResult<T> =\n"
        "  | { ok: true; value: T }\n"
        "  | { ok: false; errors: string[] };\n")

    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "user_account":
            return self._build_user(kind, rng)
        if kind == "order":
            return self._build_order(kind, rng)
        return self._build_range(kind, rng)

    def _build_user(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["validateUserAccount", "validateSignup", "validateProfile"])
        min_len, max_len = rng.choice([(3, 16), (3, 20), (4, 24)])
        min_age, max_age = rng.choice([(13, 99), (16, 110), (18, 120)])
        valid = {"username": rng.choice(["harbor_ada", "quickbrownfox42", "l1nus"]),
                 "age": rng.randint(min_age, max_age),
                 "email": rng.choice(["ada@example.com", "ops+tag@corp.dev"])}
        invalid_age = min_age - 1 if min_age > 1 else 0
        bad_cases = [
            (dict(valid, username="ab"),
             ["username must be between %d and %d characters" % (min_len, max_len)]),
            (dict(valid, age=invalid_age),
             ["age must be between %d and %d" % (min_age, max_age)]),
            (dict(valid, email="missing-at-sign.com"),
             ["email must contain an @ symbol"]),
            (dict(valid, username="", age=invalid_age, email="nope"),
             ["username must be between %d and %d characters" % (min_len, max_len),
              "age must be between %d and %d" % (min_age, max_age),
              "email must contain an @ symbol"]),
        ]
        code = (
            "export interface UserAccount {\n"
            "  username: string;\n"
            "  age: number;\n"
            "  email: string;\n"
            "}\n\n" + self.RESULT_TYPE +
            f"export function {fn}(input: UserAccount): ValidationResult<UserAccount> {{\n"
            "  const errors: string[] = [];\n"
            f"  if (input.username.length < {min_len} || input.username.length > {max_len}) {{\n"
            f"    errors.push('username must be between {min_len} and {max_len} characters');\n"
            "  }\n"
            f"  if (input.age < {min_age} || input.age > {max_age}) {{\n"
            f"    errors.push('age must be between {min_age} and {max_age}');\n"
            "  }\n"
            "  if (input.email.includes('@') === false) {\n"
            "    errors.push('email must contain an @ symbol');\n"
            "  }\n"
            "  if (errors.length > 0) {\n"
            "    return { ok: false, errors };\n"
            "  }\n"
            "  return { ok: true, value: input };\n"
            "}\n")
        cases_js = []
        for bad_input, errs in bad_cases:
            cases_js.append((json.dumps(bad_input), json.dumps(errs)))
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const good = {fn}({json.dumps(valid)});\n"
            "  assert.strictEqual(good.ok, true);\n"
            "  if (good.ok) {\n"
            f"    assert.deepStrictEqual(good.value, {json.dumps(valid)});\n"
            "  }\n")
        for i, (bad_input, errs) in enumerate(cases_js):
            body += (
                f"  const bad{i} = {fn}({bad_input});\n"
                f"  assert.strictEqual(bad{i}.ok, false);\n"
                f"  if (bad{i}.ok === false) {{\n"
                f"    assert.deepStrictEqual(bad{i}.errors, {errs});\n"
                "  }\n")
        task = (f"Implement TypeScript validation for a UserAccount domain model: "
                f"`{fn}(input)` must check that username is {min_len}-{max_len} "
                f"characters, age is {min_age}-{max_age}, and email contains an @ "
                f"symbol, collecting ALL violations. Return the discriminated union "
                f"{{ok: true, value}} | {{ok: false, errors}} with deterministic "
                f"error messages, using an interface plus a type alias (erasable "
                f"syntax only).")
        expected = (f"A valid account passes through unchanged on the ok branch; "
                    f"each broken rule adds one fixed message and any combination "
                    f"reports every error in field order (username, age, email).")
        explain = _explain(
            expected,
            "Accumulate messages into an errors array, then branch on emptiness to "
            "build the matching side of the discriminated union.",
            ["collecting all errors before returning beats fail-fast for form UX",
             "the ok:true branch carries the typed value, ok:false carries errors",
             "narrowing via .ok makes the value/errors fields type-safe to read"],
            "O(1) (fixed rule set)", "O(1)",
            ["empty username fails only the length rule",
             "all three rules broken yields three messages in field order",
             "boundary values (exact min/max) are accepted"])
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain)

    def _build_order(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["validateOrder", "validateCart"])
        min_qty = rng.choice([1, 2])
        lines = [{"sku": rng.choice(["sku-aa", "sku-bb", "sku-cc", "sku-dd"]),
                  "quantity": rng.randint(min_qty, 9),
                  "unitPrice": round(rng.uniform(1, 50), 2)} for _ in range(3)]
        bad_lines = [{"sku": "sku-ee", "quantity": min_qty - 1, "unitPrice": 5},
                     {"sku": "sku-ff", "quantity": 3, "unitPrice": -0.01}]
        bad_order = {"lines": bad_lines}
        bad_errors = [f"line 0 quantity must be at least {min_qty}",
                      "line 1 unit price must not be negative"]
        empty_errors = ["order must contain at least one line"]
        code = (
            "export interface OrderLine {\n"
            "  sku: string;\n"
            "  quantity: number;\n"
            "  unitPrice: number;\n"
            "}\n\n"
            "export interface Order {\n"
            "  lines: ReadonlyArray<OrderLine>;\n"
            "}\n\n" + self.RESULT_TYPE +
            f"export function {fn}(order: Order): ValidationResult<Order> {{\n"
            "  const errors: string[] = [];\n"
            "  if (order.lines.length === 0) {\n"
            "    errors.push('order must contain at least one line');\n"
            "  }\n"
            "  order.lines.forEach((line: OrderLine, index: number) => {\n"
            f"    if (line.quantity < {min_qty}) {{\n"
            f"      errors.push('line ' + index + ' quantity must be at least {min_qty}');\n"
            "    }\n"
            "    if (line.unitPrice < 0) {\n"
            "      errors.push('line ' + index + ' unit price must not be negative');\n"
            "    }\n"
            "  });\n"
            "  if (errors.length > 0) {\n"
            "    return { ok: false, errors };\n"
            "  }\n"
            "  return { ok: true, value: order };\n"
            "}\n")
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const good = {fn}({json.dumps({'lines': lines})});\n"
            "  assert.strictEqual(good.ok, true);\n"
            f"  const broken = {fn}({json.dumps(bad_order)});\n"
            "  assert.strictEqual(broken.ok, false);\n"
            "  if (broken.ok === false) {\n"
            f"    assert.deepStrictEqual(broken.errors, {json.dumps(bad_errors)});\n"
            "  }\n"
            f"  const empty = {fn}({{ lines: [] }});\n"
            "  assert.strictEqual(empty.ok, false);\n"
            "  if (empty.ok === false) {\n"
            f"    assert.deepStrictEqual(empty.errors, {json.dumps(empty_errors)});\n"
            "  }\n")
        task = (f"Implement TypeScript validation for an Order of OrderLine rows: "
                f"`{fn}(order)` requires at least one line, every quantity >= "
                f"{min_qty}, and every unit price >= 0, reporting one message per "
                f"broken rule with the zero-based line index. Return "
                f"{{ok: true, value}} | {{ok: false, errors}} built from erasable "
                f"interfaces and a Result-style type alias.")
        expected = (f"A healthy order passes through on the ok branch; a broken "
                    f"order reports 'line i ...' messages in scan order and an "
                    f"empty cart reports exactly 'order must contain at least one "
                    f"line'.")
        explain = _explain(
            expected,
            "Guard the aggregate rule first, then forEach over lines appending "
            "indexed messages, and finally build the union branch on emptiness.",
            ["forEach's index parameter powers the 'line i' prefix",
             "ReadonlyArray<OrderLine> documents that validation never mutates",
             "multiple violations in one line each get their own message"],
            "O(n) over order lines", "O(errors)",
            ["an order with zero lines fails exactly one aggregate rule",
             "a negative price and a small quantity on the same line yield two "
             "messages",
             "boundary quantity equal to the minimum is accepted"])
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain)

    def _build_range(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["validateRangeConfig", "validateBounds"])
        lo, hi = sorted(rng.sample([10, 25, 50, 75, 100], 2))
        step = rng.choice([1, 2, 5])
        valid = {"min": lo, "max": hi, "step": step}
        bad1 = {"min": hi, "max": lo, "step": step}
        bad2 = {"min": lo, "max": hi, "step": 0}
        bad3 = {"min": hi, "max": lo, "step": 0}
        errs1 = ["min must be less than max"]
        errs2 = ["step must not be zero"]
        errs3 = ["min must be less than max", "step must not be zero"]
        code = (
            "export interface RangeConfig {\n"
            "  min: number;\n"
            "  max: number;\n"
            "  step: number;\n"
            "}\n\n" + self.RESULT_TYPE +
            f"export function {fn}(config: RangeConfig): ValidationResult<RangeConfig> {{\n"
            "  const errors: string[] = [];\n"
            "  if (config.min >= config.max) {\n"
            "    errors.push('min must be less than max');\n"
            "  }\n"
            "  if (config.step === 0) {\n"
            "    errors.push('step must not be zero');\n"
            "  }\n"
            "  if (errors.length > 0) {\n"
            "    return { ok: false, errors };\n"
            "  }\n"
            "  return { ok: true, value: config };\n"
            "}\n")
        body = (
            f"  const {{ {fn} }} = solution;\n"
            f"  const good = {fn}({json.dumps(valid)});\n"
            "  assert.strictEqual(good.ok, true);\n"
            "  if (good.ok) {\n"
            f"    assert.deepStrictEqual(good.value, {json.dumps(valid)});\n"
            "  }\n")
        for i, (bad, errs) in enumerate(((bad1, errs1), (bad2, errs2), (bad3, errs3))):
            body += (
                f"  const bad{i} = {fn}({json.dumps(bad)});\n"
                f"  assert.strictEqual(bad{i}.ok, false);\n"
                f"  if (bad{i}.ok === false) {{\n"
                f"    assert.deepStrictEqual(bad{i}.errors, {json.dumps(errs)});\n"
                "  }\n")
        task = (f"Implement TypeScript validation for a numeric RangeConfig model: "
                f"`{fn}(config)` must require min < max and a non-zero step, "
                f"returning {{ok: true, value}} | {{ok: false, errors}} with the "
                f"fixed messages 'min must be less than max' and 'step must not be "
                f"zero'. Define the domain model as an interface and the outcome as "
                f"a discriminated-union type alias.")
        expected = (f"Config {valid} passes; inverted bounds report the min/max "
                    f"message, a zero step reports the step message, and both "
                    f"broken rules report both messages in field order.")
        explain = _explain(
            expected,
            "Two independent rules append to a shared errors list; the union "
            "branch is chosen by whether anything was collected.",
            ["independent rules stay order-stable for deterministic tests",
             "the interface pins the model shape consumed by callers",
             "boundary min < max (adjacent values) remains valid"],
            "O(1)", "O(1)",
            ["min equal to max fails the ordering rule",
             "zero step fails even when bounds are fine",
             "both violations yield two messages in field order"])
        return dict(kind=kind, fn=fn, code=code, tests=_tests_snippet(body),
                    task=task, expected=expected, explain=explain)

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], tests=b["tests"], verify_method="executed",
            notes={"kind": kind, "explain": b["explain"]},
            tags=["typescript", "validation", kind], variant=kind,
            seed=rng.randrange(2 ** 31))


class TSProjectFamily(Family):
    """Multi-file TypeScript project: solution.ts + types.ts + README."""
    NAME = "ts_project_multifile"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    PROJECTS = ("taskboard", "inventory", "leaderboard")

    def _build(self, proj: str, rng: random.Random):
        if proj == "taskboard":
            priorities = ["high", "normal", "low"]
            rank = {"high": 0, "normal": 1, "low": 2}
            ids = ["t1", "t2", "t3", "t4", "t5", "t6"]
            n = rng.randint(4, 6)
            items = []
            for i in range(n):
                items.append({"id": ids[i],
                              "title": rng.choice(["wire signup flow",
                                                   "fix flaky test",
                                                   "write runbook",
                                                   "migrate cron",
                                                   "cache headers",
                                                   "audit deps"]),
                              "done": rng.random() < 0.4,
                              "priority": rng.choice(priorities)})
            if not any(it["done"] for it in items):
                items[0]["done"] = True
            open_items = [it for it in items if not it["done"]]
            sorted_items = sorted(items, key=lambda it: (rank[it["priority"]], it["id"]))
            types_ts = (
                "export type Priority = 'high' | 'normal' | 'low';\n\n"
                "export interface TaskItem {\n"
                "  id: string;\n"
                "  title: string;\n"
                "  done: boolean;\n"
                "  priority: Priority;\n"
                "}\n")
            solution_ts = (
                "import type { Priority, TaskItem } from './types.ts';\n\n"
                "const RANK: Record<Priority, number> = { high: 0, normal: 1, low: 2 };\n\n"
                "/** Every task not yet done, in input order. */\n"
                "export function openTasks(items: ReadonlyArray<TaskItem>): TaskItem[] {\n"
                "  return items.filter((task: TaskItem) => !task.done);\n"
                "}\n\n"
                "/** Priority order (high first), ties broken by ascending id. */\n"
                "export function sortByPriority(\n"
                "  items: ReadonlyArray<TaskItem>,\n"
                "): TaskItem[] {\n"
                "  return items.slice().sort((a: TaskItem, b: TaskItem) =>\n"
                "    RANK[a.priority] - RANK[b.priority] || (a.id < b.id ? -1 : 1));\n"
                "}\n")
            tests = _fill(
                "  const { openTasks, sortByPriority } = solution;\n"
                "  const board = {items};\n"
                "  assert.deepStrictEqual(openTasks(board), {open});\n"
                "  assert.deepStrictEqual(sortByPriority(board), {sorted});\n"
                "  assert.deepStrictEqual(openTasks([]), []);\n",
                items=json.dumps(items), open=json.dumps(open_items),
                sorted=json.dumps(sorted_items))
            expected = (f"openTasks keeps the {len(open_items)} unfinished of "
                        f"{len(items)} tasks in input order; sortByPriority orders "
                        f"high, then normal, then low, with id ties ascending.")
            api_import = "openTasks, sortByPriority"
        elif proj == "inventory":
            skus = rng.sample(["bolt-m8", "nut-m8", "washer-8", "brace-2m",
                               "cable-1m"], rng.randint(4, 5))
            items = [{"sku": s, "quantity": rng.randint(0, 40),
                      "reorderPoint": rng.randint(3, 12)} for s in skus]
            low = [it for it in items if it["quantity"] <= it["reorderPoint"]]
            total = sum(it["quantity"] for it in items)
            types_ts = (
                "export interface StockItem {\n"
                "  sku: string;\n"
                "  quantity: number;\n"
                "  reorderPoint: number;\n"
                "}\n\n"
                "export type ReorderReport = ReadonlyArray<StockItem>;\n")
            solution_ts = (
                "import type { ReorderReport, StockItem } from './types.ts';\n\n"
                "/** Items at or below their reorder point, in input order. */\n"
                "export function lowStock(\n"
                "  items: ReadonlyArray<StockItem>,\n"
                "): ReorderReport {\n"
                "  return items.filter((item: StockItem) =>\n"
                "    item.quantity <= item.reorderPoint);\n"
                "}\n\n"
                "/** Total units across every SKU. */\n"
                "export function totalUnits(items: ReadonlyArray<StockItem>): number {\n"
                "  return items.reduce((acc: number, item: StockItem) =>\n"
                "    acc + item.quantity, 0);\n"
                "}\n")
            tests = _fill(
                "  const { lowStock, totalUnits } = solution;\n"
                "  const stock = {items};\n"
                "  assert.deepStrictEqual(lowStock(stock), {low});\n"
                "  assert.strictEqual(totalUnits(stock), {total});\n"
                "  assert.strictEqual(totalUnits([]), 0);\n",
                items=json.dumps(items), low=json.dumps(low), total=total)
            expected = (f"lowStock flags the {len(low)} SKU(s) at or below their "
                        f"reorder point; totalUnits sums to {total} and 0 for an "
                        f"empty warehouse.")
            api_import = "lowStock, totalUnits"
        else:  # leaderboard
            names = rng.sample(["nova", "ember", "quill", "drift", "sable", "pyre"],
                               rng.randint(4, 6))
            scores = [{"name": nm, "points": rng.randint(0, 500)} for nm in names]
            top = rng.randint(2, 3)
            ranked = sorted(scores, key=lambda s: (-s["points"], s["name"]))[:top]
            avg = round(sum(s["points"] for s in scores) / len(scores), 2)
            types_ts = (
                "export interface PlayerScore {\n"
                "  name: string;\n"
                "  points: number;\n"
                "}\n\n"
                "export type LeaderBoard = ReadonlyArray<PlayerScore>;\n")
            solution_ts = (
                "import type { LeaderBoard, PlayerScore } from './types.ts';\n\n"
                "/** Top `top` players by points desc, ties broken by name asc. */\n"
                "export function leaderboard(\n"
                "  scores: LeaderBoard,\n"
                "  top: number,\n"
                "): PlayerScore[] {\n"
                "  return scores.slice()\n"
                "    .sort((a: PlayerScore, b: PlayerScore) =>\n"
                "      b.points - a.points || (a.name < b.name ? -1 : 1))\n"
                "    .slice(0, top);\n"
                "}\n\n"
                "/** Mean score rounded to 2 decimals; 0 for an empty board. */\n"
                "export function averagePoints(scores: LeaderBoard): number {\n"
                "  if (scores.length === 0) {\n"
                "    return 0;\n"
                "  }\n"
                "  const total = scores.reduce((acc: number, s: PlayerScore) =>\n"
                "    acc + s.points, 0);\n"
                "  return Math.round(total / scores.length * 100) / 100;\n"
                "}\n")
            tests = _fill(
                "  const { leaderboard, averagePoints } = solution;\n"
                "  const scores = {scores};\n"
                "  assert.deepStrictEqual(leaderboard(scores, {top}), {ranked});\n"
                "  assert.strictEqual(averagePoints(scores), {avg});\n"
                "  assert.strictEqual(averagePoints([]), 0);\n",
                scores=json.dumps(scores), top=top, ranked=json.dumps(ranked),
                avg=avg)
            expected = (f"The top-{top} leaderboard is {json.dumps(ranked)} (points "
                        f"descending, name ties ascending); averagePoints returns "
                        f"{avg} and 0 for an empty board.")
            api_import = "leaderboard, averagePoints"
        readme = (
            f"# {proj}-ts\n\n"
            "Small multi-file TypeScript project: typed domain model in a sibling "
            "module plus a small public API built on top of it.\n\n"
            "## Layout\n\n"
            "- `solution.ts` - public API (imported by tests and consumers)\n"
            "- `types.ts` - interfaces and type aliases for the domain model\n"
            "- `README.md` - this document\n\n"
            "## Notes\n\n"
            "- Types are imported with `import type`, so they are fully erased at "
            "runtime under Node's type stripping.\n"
            "- Only erasable TypeScript is used (no enums, namespaces or parameter "
            "properties).\n\n"
            "## Usage\n\n"
            "```ts\n"
            f"import {{ {api_import} }} from './solution.ts';\n"
            "```\n")
        files = [
            FileSpec("solution.ts", solution_ts),
            FileSpec("types.ts", types_ts),
            FileSpec("README.md", readme),
        ]
        # The harness inserts `tests` into a plain-JS .mjs wrapper that calls
        # `runTests(solution)` at top level, so the snippet MUST define a
        # top-level runTests. Node's type stripping does not process .mjs,
        # so the contract's typed signature
        #   function runTests(solution: typeof import('./solution.ts')): void
        # is declared via the JSDoc @param below (the repo-wide TS convention,
        # see _tests_snippet); the .mjs-safe form keeps the harness runnable.
        tests = _tests_snippet(tests)
        return dict(proj=proj, files=files, tests=tests, task=None,
                    expected=expected)

    def generate(self, rng: random.Random) -> Candidate:
        proj = rng.choice(self.PROJECTS)
        b = self._build(proj, rng)
        if proj == "taskboard":
            task = (f"Build the multi-file TypeScript project 'taskboard-ts' as its "
                    f"README describes: types.ts declares the Priority union and "
                    f"TaskItem interface, while solution.ts exports openTasks(items) "
                    f"and sortByPriority(items) operating on a ReadonlyArray of "
                    f"tasks. Behaviour: {b['expected']} The bundled test harness "
                    f"must pass.")
        elif proj == "inventory":
            task = (f"Create the multi-file TypeScript project 'inventory-ts': "
                    f"types.ts holds the StockItem interface and ReorderReport "
                    f"alias, and solution.ts exports lowStock(items) plus "
                    f"totalUnits(items) over a ReadonlyArray of stock rows. "
                    f"Behaviour: {b['expected']} The bundled test harness must "
                    f"pass.")
        else:
            task = (f"Implement the multi-file TypeScript project 'leaderboard-ts': "
                    f"types.ts declares PlayerScore and LeaderBoard, and solution.ts "
                    f"exports leaderboard(scores, top) with points-descending, "
                    f"name-ascending ordering plus averagePoints(scores) rounded to "
                    f"two decimals. Behaviour: {b['expected']} The bundled test "
                    f"harness must pass.")
        return Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=b["expected"],
            files=b["files"], entry="solution.ts", tests=b["tests"],
            verify_method="executed", is_project=True,
            notes={"project": proj,
                   "explain": _explain(
                       b["expected"],
                       "Domain types live in a sibling module imported with "
                       "`import type`; solution.ts composes runtime behaviour on "
                       "top and exports the API.",
                       ["import type keeps the sibling module erased at runtime",
                        "ReadonlyArray inputs promise callers no mutation",
                        "pure functions make the API trivially testable"],
                       "O(n log n) for the sorting variants, O(n) for the filters",
                       "O(n)",
                       ["empty inputs return empty results (or 0 for averages)",
                        "ties fall back to a deterministic secondary key"])},
            tags=["typescript", "project", proj], variant=proj,
            seed=rng.randrange(2 ** 31))


register(globals(), TSTypedUtilitiesFamily)
register(globals(), TSModelValidationFamily)
register(globals(), TSProjectFamily)
