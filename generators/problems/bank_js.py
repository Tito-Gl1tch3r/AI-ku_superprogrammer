"""JavaScript (Node.js) implementations for the problem bank."""
from __future__ import annotations

import json

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_a import _bs_params, _bs_spec, _bs_solve, _bs_io
from .bank_py_a import _ms_params, _ms_spec, _ms_solve, _ms_io
from .bank_py_a import _ts_params, _ts_spec, _ts_solve, _ts_io
from .bank_py_a import _vp_params, _vp_spec, _vp_solve, _vp_io
from .bank_py_b import _wf_params, _wf_spec, _wf_solve, _wf_io


def _js_bs(P, rng):
    v = rng.choice(["values", "data", "numbers", "items"])
    f = rng.choice(["binarySearch", "findSorted", "indexOfSorted", "locate"])
    a = json.dumps(P["arr"])
    code = (
        f"function {f}({v}, target) {{\n"
        f"  let lo = 0;\n"
        f"  let hi = {v}.length - 1;\n"
        f"  while (lo <= hi) {{\n"
        f"    const mid = (lo + hi) >> 1;\n"
        f"    if ({v}[mid] === target) return mid;\n"
        f"    if ({v}[mid] < target) lo = mid + 1;\n"
        f"    else hi = mid - 1;\n"
        f"  }}\n"
        f"  return -1;\n"
        f"}}\n\n"
        f"module.exports = {{ {f} }};\n")
    tests = (
        f"function runTests(solution) {{\n"
        f"  const {f} = solution.{f};\n"
        f"  const v1 = {a};\n"
        f"  assert.strictEqual({f}(v1, {P['target']}), {P['idx']});\n"
        f"  assert.strictEqual({f}([], 7), -1);\n"
        f"  assert.strictEqual({f}([4], 4), 0);\n"
        f"  assert.strictEqual({f}([1, 3, 5], 4), -1);\n"
        f"  assert.strictEqual({f}([1, 3, 5], 5), 2);\n"
        f"}}\n")
    cli = {
        "solution.js": code,
        "main.js": (
            f"const {{ {f} }} = require('./solution.js');\n"
            f"const lines = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
            f"const n = parseInt(lines[0], 10);\n"
            f"const target = parseInt(lines[1], 10);\n"
            f"const values = lines.slice(2, 2 + n).map(Number);\n"
            f"console.log({f}(values, target));\n")}
    def bug_flip(files):
        return {k: t.replace(f"if ({v}[mid] < target)", f"if ({v}[mid] <= target)")
                for k, t in files.items()}
    def bug_shift(files):
        return {k: t.replace("const mid = (lo + hi) >> 1;", "const mid = (lo + hi + 1) >> 1;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.js": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"comparison_flip": bug_flip, "mid_biased_right": bug_shift},
                    notes={"purpose": "Binary search in O(log n) using bitwise halving.",
                           "approach": "Inclusive [lo, hi] window; (lo + hi) >> 1 floors the midpoint.",
                           "key_points": ["bitwise shift halves without float rounding",
                                          "=== avoids coercion surprises",
                                          "-1 encodes absence"],
                           "big_o_time": "O(log n)", "big_o_space": "O(1)",
                           "edge_cases": ["empty array", "single element", "target outside range"]})


def _js_ms(P, rng):
    v = rng.choice(["values", "data", "items"])
    f = rng.choice(["mergeSort", "sortCopy", "stableMergeSort"])
    a = json.dumps(P["arr"])
    want = json.dumps(sorted(P["arr"]))
    code = (
        f"function {f}({v}) {{\n"
        f"  if ({v}.length <= 1) return {v}.slice();\n"
        f"  const mid = {v}.length >> 1;\n"
        f"  const left = {f}({v}.slice(0, mid));\n"
        f"  const right = {f}({v}.slice(mid));\n"
        f"  const merged = [];\n"
        f"  let i = 0, j = 0;\n"
        f"  while (i < left.length && j < right.length) {{\n"
        f"    if (left[i] <= right[j]) merged.push(left[i++]);\n"
        f"    else merged.push(right[j++]);\n"
        f"  }}\n"
        f"  while (i < left.length) merged.push(left[i++]);\n"
        f"  while (j < right.length) merged.push(right[j++]);\n"
        f"  return merged;\n"
        f"}}\n\n"
        f"module.exports = {{ {f} }};\n")
    tests = (
        f"function runTests(solution) {{\n"
        f"  const {f} = solution.{f};\n"
        f"  const src = {a};\n"
        f"  assert.deepStrictEqual({f}(src), {want});\n"
        f"  assert.deepStrictEqual(src, {a});  // input untouched\n"
        f"  assert.deepStrictEqual({f}([]), []);\n"
        f"  assert.deepStrictEqual({f}([2, 2, 2]), [2, 2, 2]);\n"
        f"  assert.deepStrictEqual({f}([-1, -3, -2]), [-3, -2, -1]);\n"
        f"}}\n")
    cli = {
        "solution.js": code,
        "main.js": (
            f"const {{ {f} }} = require('./solution.js');\n"
            f"const lines = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
            f"const n = parseInt(lines[0], 10);\n"
            f"const values = lines.slice(1, 1 + n).map(Number);\n"
            f"console.log({f}(values).join(' '));\n")}
    def bug_tail(files):
        return {k: t.replace("while (i < left.length) merged.push(left[i++]);",
                             "while (i + 1 < left.length) merged.push(left[i++]);")
                for k, t in files.items()}
    def bug_slice(files):
        return {k: t.replace(f"const right = {f}({v}.slice(mid));",
                             f"const right = {f}({v}.slice(mid + 1));")
                for k, t in files.items()}
    return CodeUnit(files={"solution.js": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"dropped_tail_element": bug_tail, "skipped_pivot": bug_slice},
                    notes={"purpose": "Merge sort returning a new array without mutating the input.",
                           "approach": "Slice halves, recurse, merge with two pointers.",
                           "key_points": ["slice() copies so the caller's array is untouched",
                                          "left[i] <= right[j] keeps the sort stable",
                                          "both tail loops after the main merge are required"],
                           "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty array", "all equal", "reverse sorted", "negatives"]})


def _js_ts(P, rng):
    v = rng.choice(["values", "data", "items"])
    f = rng.choice(["twoSum", "findPair", "pairWithSum"])
    a = json.dumps(P["arr"])
    pair = P["pair"]
    pair_js = json.dumps(list(pair)) if pair else "-1"
    code = (
        f"function {f}({v}, target) {{\n"
        f"  const seen = new Map();  // value -> earliest index\n"
        f"  for (let j = 0; j < {v}.length; j++) {{\n"
        f"    const x = {v}[j];\n"
        f"    const need = target - x;\n"
        f"    if (seen.has(need)) return [seen.get(need), j];\n"
        f"    if (!seen.has(x)) seen.set(x, j);\n"
        f"  }}\n"
        f"  return -1;\n"
        f"}}\n\n"
        f"module.exports = {{ {f} }};\n")
    tests = (
        f"function runTests(solution) {{\n"
        f"  const {f} = solution.{f};\n"
        f"  assert.deepStrictEqual({f}({a}, {P['target']}), {pair_js});\n"
        f"  assert.deepStrictEqual({f}([5, 5], 10), [0, 1]);\n"
        f"  assert.strictEqual({f}([1, 2, 3], 100), -1);\n"
        f"  assert.strictEqual({f}([4], 8), -1);\n"
        f"}}\n")
    cli = {
        "solution.js": code,
        "main.js": (
            f"const {{ {f} }} = require('./solution.js');\n"
            f"const lines = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
            f"const n = parseInt(lines[0], 10);\n"
            f"const target = parseInt(lines[1], 10);\n"
            f"const values = lines.slice(2, 2 + n).map(Number);\n"
            f"const ans = {f}(values, target);\n"
            f"console.log(ans === -1 ? '-1' : ans.join(' '));\n")}
    def bug_reuse(files):
        return {k: t.replace("    if (!seen.has(x)) seen.set(x, j);\n", "    seen.set(x, j);\n")
                for k, t in files.items()}
    def bug_order(files):
        return {k: t.replace("return [seen.get(need), j];", "return [j, seen.get(need)];")
                for k, t in files.items()}
    return CodeUnit(files={"solution.js": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"always_overwrite_seen": bug_reuse, "reversed_indices": bug_order},
                    notes={"purpose": "O(n) complement lookup with a Map.",
                           "approach": "Check the complement before inserting the current value.",
                           "key_points": ["Map preserves earliest index for duplicates via the has() guard",
                                          "returned indices are strictly increasing",
                                          "-1 encodes absence"],
                           "big_o_time": "O(n) average", "big_o_space": "O(n)",
                           "edge_cases": ["no pair", "duplicates", "single element"]})


def _js_vp(P, rng):
    f = rng.choice(["isBalanced", "validBrackets", "bracketsOk"])
    s = P["s"].replace("\\", "\\\\").replace("'", "\\'")
    body = (
        f"function {f}(s) {{\n"
        f"  const match = {{ ')': '(', ']': '[', '}}': '{{' }};\n"
        f"  const stack = [];\n"
        f"  for (const ch of s) {{\n"
        f"    if (ch === '(' || ch === '[' || ch === '{{') {{\n"
        f"      stack.push(ch);\n"
        f"    }} else if (ch in match) {{\n"
        f"      if (stack.length === 0 || stack.pop() !== match[ch]) return false;\n"
        f"    }}\n"
        f"  }}\n"
        f"  return stack.length === 0;\n"
        f"}}\n\n"
        f"module.exports = {{ {f} }};\n")
    tests = (
        f"function runTests(solution) {{\n"
        f"  const {f} = solution.{f};\n"
        f"  assert.strictEqual({f}('{s}'), {str(P['balanced']).lower()});\n"
        f"  assert.strictEqual({f}(''), true);\n"
        f"  assert.strictEqual({f}(')'), false);\n"
        f"  assert.strictEqual({f}('([)]'), false);\n"
        f"  assert.strictEqual({f}('{'{'}[()]{'}'}'), true);\n"
        f"}}\n")
    cli = {
        "solution.js": body,
        "main.js": (
            f"const {{ {f} }} = require('./solution.js');\n"
            f"const line = require('fs').readFileSync(0, 'utf8').replace(/\\r?\\n$/, '');\n"
            f"console.log({f}(line) ? 'true' : 'false');\n")}
    def bug_map(files):
        return {k: t.replace("']': '[', '}", "']': '(', '}") for k, t in files.items()}
    def bug_end(files):
        return {k: t.replace("  return stack.length === 0;", "  return true;")
                for k, t in files.items()}
    def bug_guard(files):
        return {k: t.replace("if (stack.length === 0 || stack.pop() !== match[ch]) return false;",
                             "if (stack.pop() !== match[ch]) return false;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.js": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"wrong_match_table": bug_map, "skip_empty_check": bug_end,
                          "unchecked_pop": bug_guard},
                    notes={"purpose": "LIFO stack validation of bracket nesting.",
                           "approach": "Push openers, pop-and-match closers, require an empty stack at the end.",
                           "key_points": ["the empty-stack guard throws no error but must return false",
                                          "unclosed openers are caught by the final length check",
                                          "`ch in match` ignores non-bracket characters"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty string", "lone closer", "interleaved types", "unclosed opens"]})


def _js_wf(P, rng):
    f = rng.choice(["topWords", "mostFrequent", "frequentTerms"])
    lines_js = json.dumps(P["lines"])
    expected = [[w, int(c)] for w, c in (e.split() for e in _wf_solve(P).split("\n"))]
    body = (
        f"function {f}(lines, m) {{\n"
        f"  const counts = new Map();\n"
        f"  for (const line of lines) {{\n"
        f"    for (const word of line.split(' ')) {{\n"
        f"      if (word === '') continue;\n"
        f"      counts.set(word, (counts.get(word) || 0) + 1);\n"
        f"    }}\n"
        f"  }}\n"
        f"  const ranked = [...counts.entries()].sort((a, b) =>\n"
        f"    b[1] - a[1] || (a[0] < b[0] ? -1 : 1)\n"
        f"  );\n"
        f"  return ranked.slice(0, m);\n"
        f"}}\n\n"
        f"module.exports = {{ {f} }};\n")
    tests = (
        f"function runTests(solution) {{\n"
        f"  const {f} = solution.{f};\n"
        f"  assert.deepStrictEqual({f}({lines_js}, {P['m']}), {json.dumps(expected)});\n"
        f"  assert.deepStrictEqual({f}([], 3), []);\n"
        f"  assert.deepStrictEqual({f}(['a b a'], 2), [['a', 2], ['b', 1]]);\n"
        f"}}\n")
    cli = {
        "solution.js": body,
        "main.js": (
            f"const {{ {f} }} = require('./solution.js');\n"
            f"const data = require('fs').readFileSync(0, 'utf8').split('\\n');\n"
            f"const m = parseInt(data[0].trim(), 10);\n"
            f"const lines = data.slice(1).filter((l, i, arr) => !(i === arr.length - 1 && l === ''));\n"
            f"for (const [w, c] of {f}(lines, m)) console.log(w, c);\n")}
    def bug_tie(files):
        return {k: t.replace("b[1] - a[1] || (a[0] < b[0] ? -1 : 1)",
                             "a[1] - b[1] || (a[0] < b[0] ? -1 : 1)")
                for k, t in files.items()}
    def bug_top(files):
        return {k: t.replace("return ranked.slice(0, m);", "return ranked.slice(0, m + 1);")
                for k, t in files.items()}
    return CodeUnit(files={"solution.js": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"tie_break_reversed": bug_tie, "off_by_top_n": bug_top},
                    notes={"purpose": "Word-frequency ranking with deterministic tie-breaking.",
                           "approach": "Count into a Map, sort by count desc then word asc, slice m.",
                           "key_points": ["comparator returns 0 on equal counts so the secondary key decides",
                                          "empty tokens from double spaces are skipped",
                                          "slice beyond length is safe"],
                           "big_o_time": "O(W + U log U)", "big_o_space": "O(U)",
                           "edge_cases": ["empty input", "fewer distinct words than m", "ties"]})


def _problem(pid, domain, params, spec, io, solve, impl):
    register_problem(Problem(pid=pid, domain=domain, params=params, spec=spec,
                             io=io, solve=solve, impls={"javascript": impl}))


_problem("binary_search", "algorithms", _bs_params, _bs_spec, _bs_io, _bs_solve, _js_bs)
_problem("merge_sort", "algorithms", _ms_params, _ms_spec, _ms_io, _ms_solve, _js_ms)
_problem("two_sum", "algorithms", _ts_params, _ts_spec, _ts_io, _ts_solve, _js_ts)
_problem("valid_parentheses", "algorithms", _vp_params, _vp_spec, _vp_io, _vp_solve, _js_vp)
_problem("word_frequency", "text_processing", _wf_params, _wf_spec, _wf_io, _wf_solve, _js_wf)
