# CONTRACT: How to write a Family module for this repo

READ THIS FULLY BEFORE WRITING CODE. Your module will be auto-verified by the
pipeline; anything violating this contract FAILS and will be rejected.

## 1. Data model (generators/core.py)

```python
from ..core import Candidate, Family, FileSpec, register
```

* `Candidate` fields: family, language, domain, difficulty, task,
  expected_behavior, code (single-file str) OR files (list[FileSpec]) +
  entry, tests, verify_method, notes (dict), tags, variant, seed,
  is_project.
* `Family` subclass attributes: `NAME` (unique, prefix with language:
  `py_`, `c_`, `cpp_`, `java_`, `js_`, `ts_`, `php_`, `html_`, `css_`,
  `rust_`, `go_`, `ps_`), `LANGUAGE`, `DOMAIN` (one of: algorithms,
  data_structures, systems, web, databases, automation, science_math,
  engineering, security, networking, concurrency, text_processing),
  `DIFFICULTIES` (subset of beginner/intermediate/advanced/expert),
  `SUPPORTS` (understand task types you can feed),
  `PROJECT_FAMILY` (True for multi-file projects).
* Register at module bottom: `register(globals(), MyFamily)` (one line per class).
* Determinism: use ONLY the `rng: random.Random` passed to generate().
  Never call random.* module functions or time-based values.

## 2. Harness conventions per language (verification contract)

### C (executable; verify_method="compiled_and_executed")
* files: `solution.c` (+ optional extra .c/.h files). NO main() in solution.
* `tests` = FULL content of `harness.c`: its own #includes, a prototype of
  every solution function, `int main(void)` using assert.h, returns 0.
* Executor compiles: gcc -std=c11 -O1 -Wall -Wextra solution.c harness.c -lm
* Use only libc; no external deps.

### C++ (executable; verify_method="compiled_and_executed")
* files: `solution.cpp` (+ extras). NO main() in solution.
* `tests` = FULL content of `harness.cpp` (includes, prototypes, main with
  <cassert>, returns 0). Executor: g++ -std=c++17 -O1 -Wall -Wextra -pthread.
* std only.

### JavaScript (executable; verify_method="executed")
* `code` = `solution.js` ending with `module.exports = { fnName };`
* `tests` = JS source defining `function runTests(solution){ ... }` using
  the global `assert` (harness provides `const assert = require('assert')`).

### TypeScript (executable; verify_method="executed")
* ERASABLE SYNTAX ONLY: annotations, interfaces, type aliases, generics,
  `import type`. NO enums, namespaces, parameter properties, const enum.
* `code` = `solution.ts` with `export function ...`.
* `tests` = TS source defining
  `function runTests(solution: typeof import('./solution.ts')): void { ... }`
  (harness imports solution and provides assert).
* Node 24 runs it with native type-stripping.

### Java / Rust / Go / PHP / PowerShell (STATIC-ONLY in this environment)
* verify_method="static_check" (the executor runs structural checks only).
* Write conservative, canonical stdlib code that would obviously compile:
  no exotic APIs, no generated placeholders, complete working programs.
* Single file via `code`, or `files` + `entry` for projects.

## 3. notes contract (feeds Dataset 2 — understand)

Every Candidate MUST include `notes["explain"]`:
```python
notes={"explain": {"purpose": "...", "approach": "...",
                   "key_points": ["...", "..."],
                   "big_o_time": "O(...)", "big_o_space": "O(...)",
                   "edge_cases": ["..."]}, ...}
```
For executable-language families, ideally ALSO implement optional hooks:
* `make_buggy(self, rng)` -> (Candidate-buggy, meta) or None. The buggy
  Candidate must carry `tests` and the same verify_method as the original;
  meta = {"kind", "problem", "correct_code", "tests", "unit_notes"}.
  Only bugs that deterministically make tests FAIL are useful (pipeline
  verifies this and drops non-failing bugs).
* `review_variant(self, rng)` -> (Candidate-working, issues list) where
  issues = [{"kind", "severity" ("high"|"medium"|"low"), "why", "better"}].
  The code MUST still pass its tests (issues are design/perf/style).
* `perf_pair(self, rng)` -> (naive Candidate, optimized Candidate, meta)
  with meta = {"what_changed": [...], "equivalence_inputs": [...]}.

## 4. Content rules (QUALITY IS ABSOLUTE)

* ALL dataset-facing text (task, expected_behavior, explain, key_points,
  issue descriptions) in ENGLISH, professional tone.
* tasks >= 60 chars; code >= 90 chars; realistic, meaningful examples.
* Diversity: parameterize sizes, values, identifier names (realistic name
  pools), edge cases. Do NOT pad volume with renamed duplicates.
* Only REAL stdlib APIs (no invented functions).
* Include at least one PROJECT family (multi-file: files + entry +
  is_project=True) per language.
* Security content = defensive only (safe-by-construction patterns).

## 5. Self-test before reporting (MANDATORY)

```bash
cd /home/z/my-project/download/AI-ku_superprogrammer
python3 -m generators.smoke --families <name1>,<name2> --samples 5
```
ALL your families must show OK >= 5, FAIL 0. Iterate until green.
For static languages, the static validator must also pass:
`python3 -m generators.smoke --languages <lang> --samples 5`

## 6. Deliverables & reporting

* Only write YOUR assigned file(s). Do not modify shared files
  (core.py, executors, registry.py, bank_*).
* Append your work record to /home/z/my-project/worklog.md (Task ID given
  in your assignment) with the template: `---` line, Task ID, Agent, Task,
  Work Log bullets, Stage Summary.
* Report back: families implemented, smoke results, hooks implemented
  (make_buggy/review_variant/perf_pair), any caveats.
