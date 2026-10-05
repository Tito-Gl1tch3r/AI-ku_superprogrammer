"""TypeScript implementations for the problem bank.

CRITICAL: only *erasable* TypeScript is used (annotations, interfaces, type
aliases, generics). Node's native type stripping cannot transform enums,
namespaces or parameter properties — those would break verification.
"""
from __future__ import annotations

import json

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_a import _bs_params, _bs_spec, _bs_solve, _bs_io
from .bank_py_a import _ts_params, _ts_spec, _ts_solve, _ts_io
from .bank_py_a import _vp_params, _vp_spec, _vp_solve, _vp_io


def _ts_bs(P, rng):
    f = rng.choice(["binarySearch", "findSorted", "indexOfSorted"])
    a = json.dumps(P["arr"])
    code = (
        f"interface SearchInput {{\n"
        f"  values: number[];\n"
        f"  target: number;\n"
        f"}}\n\n"
        f"export function {f}(input: SearchInput): number {{\n"
        f"  const {{ values, target }} = input;\n"
        f"  let lo = 0;\n"
        f"  let hi = values.length - 1;\n"
        f"  while (lo <= hi) {{\n"
        f"    const mid = Math.floor((lo + hi) / 2);\n"
        f"    const probe: number = values[mid];\n"
        f"    if (probe === target) return mid;\n"
        f"    if (probe < target) lo = mid + 1;\n"
        f"    else hi = mid - 1;\n"
        f"  }}\n"
        f"  return -1;\n"
        f"}}\n")
    tests = (
        f"function runTests(solution: typeof import('./solution.ts')): void {{\n"
        f"  const {{ {f} }} = solution;\n"
        f"  assert.strictEqual({f}({{ values: {a}, target: {P['target']} }}), {P['idx']});\n"
        f"  assert.strictEqual({f}({{ values: [], target: 7 }}), -1);\n"
        f"  assert.strictEqual({f}({{ values: [1, 3, 5], target: 4 }}), -1);\n"
        f"  assert.strictEqual({f}({{ values: [1, 3, 5], target: 5 }}), 2);\n"
        f"}}\n")
    cli = {
        "solution.ts": code,
        "main.ts": (
            f"import {{ {f} }} from './solution.ts';\n"
            f"import {{ readFileSync }} from 'fs';\n"
            f"const lines: string[] = readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
            f"const n: number = parseInt(lines[0], 10);\n"
            f"const target: number = parseInt(lines[1], 10);\n"
            f"const values: number[] = lines.slice(2, 2 + n).map(Number);\n"
            f"console.log({f}({{ values, target }}));\n")}
    def bug_flip(files):
        return {k: t.replace("if (probe < target)", "if (probe <= target)")
                for k, t in files.items()}
    def bug_floor(files):
        return {k: t.replace("Math.floor((lo + hi) / 2)", "Math.ceil((lo + hi) / 2)")
                for k, t in files.items()}
    return CodeUnit(files={"solution.ts": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"comparison_flip": bug_flip, "mid_ceiling": bug_floor},
                    notes={"purpose": "Typed binary search: the interface documents the contract.",
                           "approach": "Destructure the input object; inclusive window; Math.floor midpoint.",
                           "key_points": ["the interface makes the parameter shape explicit",
                                          "annotated probe variable documents element type",
                                          "Math.ceil on mid biases right and can skip targets"],
                           "big_o_time": "O(log n)", "big_o_space": "O(1)",
                           "edge_cases": ["empty array", "single element", "target outside range"]})


def _ts_pair(P, rng):
    f = rng.choice(["twoSum", "findPair", "pairWithSum"])
    a = json.dumps(P["arr"])
    pair = P["pair"]
    pair_js = json.dumps(list(pair)) if pair else "-1"
    code = (
        f"type PairResult = [number, number] | -1;\n\n"
        f"export function {f}(values: number[], target: number): PairResult {{\n"
        f"  const seen = new Map<number, number>();\n"
        f"  for (let j = 0; j < values.length; j++) {{\n"
        f"    const x: number = values[j];\n"
        f"    const need: number = target - x;\n"
        f"    if (seen.has(need)) return [seen.get(need) as number, j];\n"
        f"    if (!seen.has(x)) seen.set(x, j);\n"
        f"  }}\n"
        f"  return -1;\n"
        f"}}\n")
    tests = (
        f"function runTests(solution: typeof import('./solution.ts')): void {{\n"
        f"  const {{ {f} }} = solution;\n"
        f"  assert.deepStrictEqual({f}({a}, {P['target']}), {pair_js});\n"
        f"  assert.deepStrictEqual({f}([5, 5], 10), [0, 1]);\n"
        f"  assert.strictEqual({f}([1, 2, 3], 100), -1);\n"
        f"  assert.strictEqual({f}([4], 8), -1);\n"
        f"}}\n")
    cli = {
        "solution.ts": code,
        "main.ts": (
            f"import {{ {f} }} from './solution.ts';\n"
            f"import {{ readFileSync }} from 'fs';\n"
            f"const lines: string[] = readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean);\n"
            f"const n: number = parseInt(lines[0], 10);\n"
            f"const target: number = parseInt(lines[1], 10);\n"
            f"const values: number[] = lines.slice(2, 2 + n).map(Number);\n"
            f"const ans = {f}(values, target);\n"
            f"console.log(ans === -1 ? '-1' : ans.join(' '));\n")}
    def bug_reuse(files):
        return {k: t.replace("    if (!seen.has(x)) seen.set(x, j);\n", "    seen.set(x, j);\n")
                for k, t in files.items()}
    def bug_widen(files):
        return {k: t.replace("type PairResult = [number, number] | -1;",
                             "type PairResult = number;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.ts": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"always_overwrite_seen": bug_reuse, "widened_result_type": bug_widen},
                    notes={"purpose": "Discriminated result type makes absence explicit in the signature.",
                           "approach": "Union type [number, number] | -1; Map complement scan.",
                           "key_points": ["the PairResult union encodes the failure mode",
                                          "as number narrows the Map.get undefined case",
                                          "checking before inserting keeps indices increasing"],
                           "big_o_time": "O(n) average", "big_o_space": "O(n)",
                           "edge_cases": ["no pair", "duplicates", "single element"]})


def _ts_vp(P, rng):
    f = rng.choice(["isBalanced", "validBrackets", "bracketsOk"])
    s = P["s"].replace("\\", "\\\\").replace("'", "\\'")
    body = (
        f"type Bracket = '(' | '[' | '{{';\n\n"
        f"const MATCH: Record<string, string> = {{ ')': '(', ']': '[', '}}': '{{' }};\n\n"
        f"function isOpen(ch: string): ch is Bracket {{\n"
        f"  return ch === '(' || ch === '[' || ch === '{{';\n"
        f"}}\n\n"
        f"export function {f}(s: string): boolean {{\n"
        f"  const stack: Bracket[] = [];\n"
        f"  for (const ch of s) {{\n"
        f"    if (isOpen(ch)) stack.push(ch);\n"
        f"    else if (ch in MATCH) {{\n"
        f"      const top = stack.pop();\n"
        f"      if (top === undefined || top !== MATCH[ch]) return false;\n"
        f"    }}\n"
        f"  }}\n"
        f"  return stack.length === 0;\n"
        f"}}\n")
    tests = (
        f"function runTests(solution: typeof import('./solution.ts')): void {{\n"
        f"  const {{ {f} }} = solution;\n"
        f"  assert.strictEqual({f}('{s}'), {str(P['balanced']).lower()});\n"
        f"  assert.strictEqual({f}(''), true);\n"
        f"  assert.strictEqual({f}(')'), false);\n"
        f"  assert.strictEqual({f}('([)]'), false);\n"
        f"  assert.strictEqual({f}('{{[()]}}'), true);\n"
        f"}}\n")
    cli = {
        "solution.ts": body,
        "main.ts": (
            f"import {{ {f} }} from './solution.ts';\n"
            f"import {{ readFileSync }} from 'fs';\n"
            f"const line: string = readFileSync(0, 'utf8').replace(/\\r?\\n$/, '');\n"
            f"console.log({f}(line) ? 'true' : 'false');\n")}
    def bug_map(files):
        return {k: t.replace("']': '[', '}", "']': '(', '}") for k, t in files.items()}
    def bug_undef(files):
        return {k: t.replace("if (top === undefined || top !== MATCH[ch]) return false;",
                             "if (top !== MATCH[ch]) return false;")
                for k, t in files.items()}
    def bug_end(files):
        return {k: t.replace("  return stack.length === 0;", "  return true;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.ts": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"wrong_match_table": bug_map, "undefined_top_compare": bug_undef,
                          "skip_empty_check": bug_end},
                    notes={"purpose": "Type-guard based bracket validation.",
                           "approach": "A user-defined type guard narrows openers; pop returns undefined on empty stack which must fail.",
                           "key_points": ["`ch is Bracket` narrows inside the branch",
                                          "undefined top (empty stack) must return false",
                                          "final length check catches unclosed openers"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty string", "lone closer", "unclosed openers"]})


def _problem(pid, domain, params, spec, io, solve, impl):
    register_problem(Problem(pid=pid, domain=domain, params=params, spec=spec,
                             io=io, solve=solve, impls={"typescript": impl}))


_problem("binary_search", "algorithms", _bs_params, _bs_spec, _bs_io, _bs_solve, _ts_bs)
_problem("two_sum", "algorithms", _ts_params, _ts_spec, _ts_io, _ts_solve, _ts_pair)
_problem("valid_parentheses", "algorithms", _vp_params, _vp_spec, _vp_io, _vp_solve, _ts_vp)
