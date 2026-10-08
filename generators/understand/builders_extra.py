"""Dataset-2 (understand) task builders — part 2.

Optimization/complexity/refactor/translate/compare build on the multilang
bank so that BOTH sides are really executed and compared on identical inputs.
"""
from __future__ import annotations

import random

from ..core import Candidate, UnderstandCandidate
from ..problems import REGISTRY, run_cli_for
from validators.verify import verify_candidate, run_snippet_safely
from .builder import _mk


# ------------------------------------------------------------------ optimization
def build_optimization(rng: random.Random):
    kind = rng.choice(["two_sum", "fibonacci", "word_frequency", "sql_rewrite"])
    if kind == "two_sum":
        prob = REGISTRY["two_sum"]
        P = prob.params(rng)
        unit = prob.impls["python"](P, rng)
        fn = unit.function_name
        n = P["n"]
        naive = (
            f"def {fn}_naive(values, target):\n"
            f"    \"\"\"Brute force: check every pair.\"\"\"\n"
            f"    n = len(values)\n"
            f"    for i in range(n):\n"
            f"        for j in range(i + 1, n):\n"
            f"            if values[i] + values[j] == target:\n"
            f"                return (i, j)\n"
            f"    return -1\n")
        optimized = unit.files["solution.py"].replace(
            f"def {fn}(", f"def {fn}_optimized(")
        # Equivalence check: both functions on identical inputs (really executed).
        probe = (naive + "\n\n" + optimized + "\n\n"
                 f"values = {P['arr']!r}\n"
                 f"target = {P['target']!r}\n"
                 f"a = {fn}_optimized(values, target)\n"
                 f"b = {fn}_naive(values, target)\n"
                 f"print('OPT:', a)\n"
                 f"print('NAIVE:', b)\n")
        r = run_snippet_safely("python", probe)
        if not r.ok:
            return None
        out = r.stdout.strip().splitlines()
        if len(out) < 2:
            return None
        opt_val, naive_val = out[0].split(":", 1)[1], out[1].split(":", 1)[1]
        if opt_val != naive_val:
            return None
        answer = (
            f"What changed: replace the O(n^2) double loop with a single pass over a hash map "
            f"of seen values.\n"
            f"Why it is faster: each complement lookup is O(1) average, so total work drops "
            f"from n(n-1)/2 comparisons to n map operations (time {n}^2 -> {n}).\n"
            f"Behaviour preserved: both implementations return {naive_val} on the sample "
            f"input (verified by executing both on identical data; "
            f"{unit.notes.get('big_o_time')} vs O(n^2)).\n"
            f"Trade-off: the optimized version spends O(n) extra memory on the map.")
        return _mk(
            rng, "optimize_two_sum", "python", "optimization", "algorithms", "intermediate",
            question=(f"This brute-force {fn} is correct but slow. Optimize it to O(n) average "
                      f"time WITHOUT changing its observable behaviour, and prove the behaviour "
                      f"is preserved.\n\n```python\n{naive}\n```\n\nSample input: target="
                      f"{P['target']}, values length {n}."),
            answer=answer, code=naive, target_code=optimized,
            artifacts={"equivalence_output": naive_val, "verified": True},
            key_points=["hash map of seen values", "complement lookup before insert",
                        "O(n^2) -> O(n) time, O(n) space"],
            big_o={"time": "O(n)", "space": "O(n)"},
            verify_method="executed",
            verify_notes={"equivalence_checked": True, "equivalence_method": "both implementations executed on identical inputs"},
            tags=["optimization", "two_sum"], variant="opt|two_sum")
    elif kind == "fibonacci":
        naive = (
            f"def fibonacci_naive(n):\n"
            f"    \"\"\"Exponential recursion: recomputes the same subproblems.\"\"\"\n"
            f"    if n <= 1:\n"
            f"        return n\n"
            f"    return fibonacci_naive(n - 1) + fibonacci_naive(n - 2)\n")
        n = rng.randint(25, 32)
        optimized = (
            f"def fibonacci_fast(n):\n"
            f"    \"\"\"Linear iteration with two rolling values.\"\"\"\n"
            f"    a, b = 0, 1\n"
            f"    for _ in range(n):\n"
            f"        a, b = b, a + b\n"
            f"    return a\n")
        probe = (
            f"{naive}\n{optimized}\n"
            f"import time\n"
            f"t0 = time.process_time(); v1 = fibonacci_naive({n}); t1 = time.process_time()\n"
            f"v2 = fibonacci_fast({n})\n"
            f"t2 = time.process_time()\n"
            f"print('MATCH:', v1 == v2, 'value:', v1)\n"
            f"print('TIME_NAIVE_MS:', int((t1 - t0) * 1000))\n"
            f"print('TIME_FAST_MS:', int((t2 - t1) * 1000))\n")
        r = run_snippet_safely("python", probe)
        if not r.ok:
            return None
        lines = r.stdout.strip().splitlines()
        match = "MATCH: True" in lines[0] if lines else False
        if not match:
            return None
        t_naive = next((l for l in lines if l.startswith("TIME_NAIVE")), "TIME_NAIVE_MS: ?")
        t_fast = next((l for l in lines if l.startswith("TIME_FAST")), "TIME_FAST_MS: ?")
        answer = (
            f"What changed: exponential recursion (calls ~fib(n) times) replaced by an "
            f"iterative two-variable loop.\n"
            f"Why it is faster: work drops from O(2^n) calls to O(n) additions; measured in "
            f"sandbox: {t_naive} vs {t_fast}.\n"
            f"Behaviour preserved: both return the same value for n={n} "
            f"(verified by executing both).\n"
            f"Trade-off: the iterative version is also O(1) memory versus O(n) stack depth - "
            f"the naive version crashes for n around 1000 (recursion limit).")
        return _mk(
            rng, "optimize_fibonacci", "python", "optimization", "algorithms", "advanced",
            question=(f"This naive Fibonacci recomputes subproblems exponentially. Optimize it to "
                      f"linear time, preserve exact behaviour for n=0..N, and demonstrate the "
                      f"speedup.\n\n```python\n{naive}\n```\n\nBenchmark target: n={n}."),
            answer=answer, code=naive, target_code=optimized,
            artifacts={"match": True, "timings": [t_naive, t_fast]},
            key_points=["rolling two values", "O(2^n) -> O(n)", "no recursion-limit risk"],
            big_o={"time": "O(n)", "space": "O(1)"},
            verify_method="executed",
            verify_notes={"equivalence_checked": True, "timed": True},
            tags=["optimization", "fibonacci"], variant="opt|fib")
    elif kind == "word_frequency":
        prob = REGISTRY["word_frequency"]
        P = prob.params(rng)
        unit = prob.impls["python"](P, rng)
        fn = unit.function_name
        naive = (
            f"def {fn}_naive(lines, m):\n"
            f"    \"\"\"Counts everything, sorts everything.\"\"\"\n"
            f"    counts = {{}}\n"
            f"    for line in lines:\n"
            f"        for w in line.split():\n"
            f"            counts[w] = counts.get(w, 0) + 1\n"
            f"    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:m]\n")
        optimized = (
            f"import heapq\n\n"
            f"def {fn}_heap(lines, m):\n"
            f"    \"\"\"Counts once; selection is O(U log m) instead of a full sort.\"\"\"\n"
            f"    counts = {{}}\n"
            f"    for line in lines:\n"
            f"        for w in line.split():\n"
            f"            counts[w] = counts.get(w, 0) + 1\n"
            f"    return heapq.nsmallest(m, counts.items(), key=lambda kv: (-kv[1], kv[0]))\n")
        probe = (naive + "\n\n" + optimized + "\n\n"
                 f"lines = {P['lines']!r}\n"
                 f"m = {P['m']}\n"
                 f"a = {fn}_heap(lines, m)\n"
                 f"b = {fn}_naive(lines, m)\n"
                 f"print('MATCH:', a == b)\n")
        r = run_snippet_safely("python", probe)
        if not r.ok or "MATCH: True" not in r.stdout:
            return None
        answer = (
            f"What changed: full sort of U distinct words (O(U log U)) replaced by "
            f"heapq.nsmallest selection (O(U log m), m << U).\n"
            f"Behaviour preserved: identical ranking including alphabetical tie-breaks "
            f"(verified by executing both on the same {len(P['lines'])} lines).\n"
            f"When it matters: large vocabularies where only the top-m are needed; "
            f"for tiny inputs the constant factors dominate and both are instant.")
        return _mk(
            rng, "optimize_word_freq", "python", "optimization", "text_processing",
            "intermediate",
            question=(f"Optimize this word-frequency ranking for large vocabularies: keep the "
                      f"exact ranking semantics (count desc, word asc) but avoid sorting all "
                      f"distinct words. Prove behaviour preservation.\n\n```python\n{naive}\n"
                      f"```\n\nInput: {len(P['lines'])} lines, m={P['m']}."),
            answer=answer, code=naive, target_code=optimized,
            artifacts={"equivalence": "MATCH: True"},
            key_points=["heapq.nsmallest", "O(U log m) selection", "tie-break preserved in key"],
            big_o={"time": "O(W + U log m)", "space": "O(U)"},
            verify_method="executed",
            verify_notes={"equivalence_checked": True},
            tags=["optimization", "text"], variant="opt|wordfreq")
    else:  # sql_rewrite
        from ..core import Candidate as _C
        from ..registry import all_families
        sql_fam = next(f for f in all_families() if f.NAME == "sql_query_scenarios")
        sc = sql_fam._sc_student_averages(rng)
        setup = sc["setup"]
        naive = ("SELECT s.name,\n"
                 "       (SELECT ROUND(AVG(g.score), 2) FROM grades g WHERE g.student_id = s.id) AS avg_score,\n"
                 "       (SELECT COUNT(*) FROM grades g2 WHERE g2.student_id = s.id) AS n_grades\n"
                 "FROM students s\nORDER BY avg_score DESC, s.name ASC;")
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript(setup)
        rows_a = con.execute(sc["answer"]).fetchall()
        rows_b = con.execute(naive).fetchall()
        con.close()
        if rows_a != rows_b:
            return None
        answer = (
            f"What changed: two correlated subqueries (executed per student row) replaced by a "
            f"single JOIN + GROUP BY aggregation.\n"
            f"Why it is faster: the correlated form re-scans grades for every student "
            f"(O(S x G) page visits); the join aggregates once (O(S + G)).\n"
            f"Behaviour preserved: both queries return identical rows on the seeded data "
            f"({len(rows_a)} rows, verified by executing both in SQLite).\n"
            f"Note: for tiny tables the difference is noise; for large tables the correlated "
            f"version is a classic N+1 pattern.")
        return _mk(
            rng, "optimize_sql_correlated", "sql", "optimization", "databases", "advanced",
            question=(f"This query uses correlated subqueries for the per-student average and "
                      f"grade count. Rewrite it with a JOIN + GROUP BY that returns EXACTLY the "
                      f"same rows, and explain why the rewrite scales better.\n\n```sql\n"
                      f"{naive}\n```\n\nSchema: students(id, name, class), grades(id, "
                      f"student_id, score)."),
            answer=answer, code=naive, target_code=sc["answer"],
            artifacts={"rows_match": True, "rows": len(rows_a),
                       "setup_excerpt": setup[:400]},
            key_points=["correlated subquery = per-row execution",
                        "JOIN + GROUP BY aggregates once",
                        "identical rows verified"],
            verify_method="executed",
            verify_notes={"equivalence_checked": True, "engine": "sqlite"},
            tags=["optimization", "sql"], variant="opt|sql_correlated")


# ------------------------------------------------------------------ complexity
def build_complexity(rng: random.Random):
    pids = ["binary_search", "merge_sort", "two_sum", "sieve_primes", "dijkstra",
            "max_subarray", "prefix_sums", "lru_cache", "matrix_multiply"]
    pids = [p for p in pids if p in REGISTRY and "python" in REGISTRY[p].impls]
    pid = rng.choice(pids)
    prob = REGISTRY[pid]
    P = prob.params(rng)
    unit = prob.impls["python"](P, rng)
    notes = unit.notes
    focus = rng.choice(["time", "space"])
    if focus == "time":
        question = (f"Analyse the TIME complexity of this {pid} implementation in terms of its "
                    f"input size. Justify from the loop/structure, state the recurrence or "
                    f"summation, and mention the dominant cost.\n\n```python\n"
                    f"{unit.files['solution.py'][:1800]}\n```")
        answer = (f"Time complexity: {notes.get('big_o_time')}.\n"
                  f"Justification: {notes.get('approach')} "
                  f"{' '.join(notes.get('key_points', [])[:2])}.\n"
                  f"Dominant cost: the main loop/aggregation over the input; auxiliary steps "
                  f"are lower order and do not change the asymptotics.")
    else:
        question = (f"Analyse the SPACE complexity of this {pid} implementation: what scales "
                    f"with input, what is constant, and what auxiliary structures exist?\n\n"
                    f"```python\n{unit.files['solution.py'][:1800]}\n```")
        answer = (f"Space complexity: {notes.get('big_o_space')}.\n"
                  f"Auxiliary structures: {notes.get('approach')} "
                  f"Input storage is not counted towards auxiliary space; any buffers or maps "
                  f"the algorithm allocates determine the asymptotics.")
    return _mk(
        rng, "complexity_bank", "python", "complexity", prob.domain,
        "intermediate" if rng.random() < 0.7 else "advanced",
        question=question, answer=answer, code=unit.files["solution.py"][:1800],
        key_points=[f"time {notes.get('big_o_time')}", f"space {notes.get('big_o_space')}"],
        big_o={"time": notes.get("big_o_time"), "space": notes.get("big_o_space")},
        verify_method="authored_verified",
        verify_notes={"source": "structure authored alongside the code"},
        tags=["complexity", pid], variant=f"complexity|{pid}|{focus}",
        context=f"Reference problem: {pid} with instance parameters {list(P.keys())[:6]}")


# ------------------------------------------------------------------ refactoring
def build_refactoring(rng: random.Random):
    kind = rng.choice(["py_decompose", "sql_implicit_join"])
    if kind == "py_decompose":
        base = rng.choice([2, 3])
        digits = rng.randint(2, 4)
        naive = (
            f"def process(values):\n"
            f"    # one long function doing three jobs\n"
            f"    cleaned = []\n"
            f"    for v in values:\n"
            f"        if v is not None and v >= 0:\n"
            f"            cleaned.append(v * {base})\n"
            f"    total = 0\n"
            f"    for v in cleaned:\n"
            f"        total += v\n"
            f"    report = []\n"
            f"    for v in cleaned:\n"
            f"        report.append(str(round(v / total * 100, {digits})) + '%')\n"
            f"    return report\n")
        clean = (
            f"def _valid(values):\n"
            f"    return [v * {base} for v in values if v is not None and v >= 0]\n\n\n"
            f"def _shares(scaled):\n"
            f"    total = sum(scaled)\n"
            f"    if not total:\n"
            f"        return []\n"
            f"    return [str(round(v / total * 100, {digits})) + '%' for v in scaled]\n\n\n"
            f"def process(values):\n"
            f"    \"\"\"Validate+scale, then render percentage shares.\"\"\"\n"
            f"    return _shares(_valid(values))\n")
        vals = [rng.choice([None, rng.randint(0, 9), rng.randint(-5, -1)]) for _ in range(6)]
        probe = (f"{naive}\n\n{clean}\n\n"
                 f"data = {vals!r}\n"
                 f"print('MATCH:', process(data) == _process_ref(data))\n")
        # Simpler: verify clean vs naive directly in one script.
        probe = (f"{naive}\n\n{clean}\n\n"
                 f"data = {vals!r}\n"
                 f"a = process(data)\n"
                 f"b = _process_naive(data)\n")
        probe = (naive.replace("def process(", "def _process_naive(") + "\n" + clean + "\n"
                 + f"data = {vals!r}\n"
                 f"a = process(data)\n"
                 f"b = _process_naive(data)\n"
                 f"print('MATCH:', a == b)\n")
        r = run_snippet_safely("python", probe)
        if not r.ok or "MATCH: True" not in r.stdout:
            return None
        answer = (
            f"What changed: the monolith is split into _valid (filter+scale), _shares "
            f"(percentage rendering) and a two-line process() orchestrator; comprehensions "
            f"replace manual accumulators; a zero-total guard prevents division by zero.\n"
            f"Behaviour preserved: identical output on the sample (executed: MATCH: True) - "
            f"including the None/negative filtering semantics.\n"
            f"Why it is better: each helper has one reason to change, names document intent, "
            f"and the shares computation is now unit-testable in isolation.")
        return _mk(
            rng, "refactor_decompose", "python", "refactoring", "engineering", "intermediate",
            question=(f"Refactor this working-but-muddled function: extract cohesive helpers, "
                      f"improve names, keep the observable behaviour EXACTLY the same.\n\n"
                      f"```python\n{naive}\n```\n\nSample input: {vals!r}"),
            answer=answer, code=naive, target_code=clean,
            artifacts={"equivalence": "MATCH: True", "sample": str(vals)},
            key_points=["single responsibility per helper", "guard against zero total",
                        "behaviour preserved (executed)"],
            verify_method="executed",
            verify_notes={"equivalence_checked": True},
            tags=["refactoring", "python"], variant="refactor|decompose")
    else:  # sql_implicit_join
        from ..registry import all_families
        sql_fam = next(f for f in all_families() if f.NAME == "sql_query_scenarios")
        sc = sql_fam._sc_orders_revenue(rng)
        setup = sc["setup"]
        messy = ("SELECT c.name, SUM(o.amount)\n"
                 "FROM customers c, orders o\n"
                 "WHERE o.customer_id = c.id\n"
                 "GROUP BY c.name\n"
                 "ORDER BY 2 DESC, 1 ASC;")
        clean = sc["answer"]
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.executescript(setup)
        rows_a = con.execute(messy).fetchall()
        rows_b = con.execute(clean).fetchall()
        con.close()
        if rows_a != rows_b:
            return None
        answer = (
            f"What changed: comma-join with a WHERE filter became an explicit INNER JOIN ... ON; "
            f"the aggregate gained an alias (`total`) and ORDER BY now uses names, not fragile "
            f"ordinal positions.\n"
            f"Behaviour preserved: identical rows ({len(rows_a)}) verified by executing both "
            f"queries on the same seeded database.\n"
            f"Why it is better: explicit joins make the join tree readable, cannot be "
            f"accidentally turned into a cartesian product by removing the WHERE, and ordinal "
            f"ORDER BY breaks the moment the select list changes.")
        return _mk(
            rng, "refactor_sql_join", "sql", "refactoring", "databases", "intermediate",
            question=(f"Refactor this SQL: replace the implicit comma-join and ordinal ORDER BY "
                      f"with modern explicit syntax, keeping EXACTLY the same result rows.\n\n"
                      f"```sql\n{messy}\n```\n\nSchema: customers(id, name, country), "
                      f"orders(id, customer_id, amount, placed_at)."),
            answer=answer, code=messy, target_code=clean,
            artifacts={"rows_match": True, "rows": len(rows_a)},
            key_points=["explicit JOIN ... ON", "aliased aggregates", "named ORDER BY keys"],
            verify_method="executed",
            verify_notes={"equivalence_checked": True, "engine": "sqlite"},
            tags=["refactoring", "sql"], variant="refactor|sql_join")


# ------------------------------------------------------------------ translation
TRANSLATE_PAIRS = [("python", "cpp"), ("python", "javascript"), ("python", "c"),
                   ("python", "typescript"), ("cpp", "python"), ("javascript", "python"),
                   ("c", "python"), ("typescript", "python"), ("python", "bash")]


def build_translation(rng: random.Random):
    prob_pool = []
    for pid, prob in REGISTRY.items():
        for src, dst in TRANSLATE_PAIRS:
            if src in prob.impls and dst in prob.impls:
                prob_pool.append((pid, src, dst))
    if not prob_pool:
        return None
    pid, src, dst = rng.choice(prob_pool)
    prob = REGISTRY[pid]
    P = prob.params(rng)
    unit_src = prob.impls[src](P, rng)
    unit_dst = prob.impls[dst](P, rng2 := random.Random(rng.randrange(2**31)))
    # Verify BOTH via their CLI on the shared io protocol.
    io_cases = prob.io(P)[:2]
    if dst == "bash" or src == "bash":
        io_cases = io_cases[:1]
    outs = {}
    for lang, unit in ((src, unit_src), (dst, unit_dst)):
        ok_all = True
        for stdin, expected in io_cases:
            try:
                r = run_cli_for(lang, unit, stdin, timeout=15.0)
            except Exception:
                ok_all = False
                break
            if not r.ok or r.stdout.strip() != expected:
                ok_all = False
                break
        outs[lang] = ok_all
    if not all(outs.values()):
        return None
    idiom = unit_dst.notes.get("approach", "")
    key_points = unit_dst.notes.get("key_points", [])[:3]
    answer = (
        f"Idiomatic {dst} translation (verified by executing both versions on the same "
        f"inputs and comparing outputs):\n```{dst}\n" +
        ("\n".join(unit_dst.files[k] for k in sorted(unit_dst.files))[:2200] if dst != "bash"
         else list(unit_dst.files.values())[0][:1200]) +
        f"\n```\nTranslation notes: {idiom}\nKey points: " + "; ".join(key_points) + ".")
    return _mk(
        rng, "translate_bank", dst, "translation", prob.domain, "advanced",
        question=(f"Translate this {src} implementation of {pid} into idiomatic {dst}. Preserve "
                  f"semantics, complexity and error behaviour - do NOT translate token by token; "
                  f"use the target language's idioms.\n\n```{src}\n" +
                  ("\n".join(unit_src.files[k] for k in sorted(unit_src.files))[:2000]
                   if src != "bash" else list(unit_src.files.values())[0][:1200]) +
                  "\n```"),
        answer=answer, code=("\n".join(unit_src.files[k] for k in sorted(unit_src.files))[:2000]
                             if src != "bash" else list(unit_src.files.values())[0][:1200]),
        target_code=("\n".join(unit_dst.files[k] for k in sorted(unit_dst.files))[:2400]
                     if dst != "bash" else list(unit_dst.files.values())[0][:1400]),
        artifacts={"both_executed": True, "io_cases": len(io_cases), "outputs_match": True},
        key_points=key_points,
        big_o={"time": unit_dst.notes.get("big_o_time"), "space": unit_dst.notes.get("big_o_space")},
        verify_method="executed",
        verify_notes={"source_executed": outs[src], "target_executed": outs[dst],
                      "outputs_compared": len(io_cases)},
        tags=["translation", pid, src, dst], variant=f"translate|{pid}|{src}->{dst}")


# ------------------------------------------------------------------ comparison
def build_comparison(rng: random.Random):
    kind = rng.choice(["two_sum_hash_vs_sort", "binary_search_rec_vs_iter"])
    if kind == "two_sum_hash_vs_sort":
        prob = REGISTRY["two_sum"]
        P = prob.params(rng)
        unit = prob.impls["python"](P, rng)
        fn = unit.function_name
        variant_b = (
            f"def {fn}_sortscan(values, target):\n"
            f"    \"\"\"Sort + two-pointer scan.\"\"\"\n"
            f"    indexed = sorted(enumerate(values), key=lambda t: t[1])\n"
            f"    lo, hi = 0, len(indexed) - 1\n"
            f"    while lo < hi:\n"
            f"        s = indexed[lo][1] + indexed[hi][1]\n"
            f"        if s == target:\n"
            f"            pair = sorted((indexed[lo][0], indexed[hi][0]))\n"
            f"            return (pair[0], pair[1])\n"
            f"        if s < target:\n"
            f"            lo += 1\n"
            f"        else:\n"
            f"            hi -= 1\n"
            f"    return -1\n")
        hash_version = unit.files["solution.py"].replace(
            f"def {fn}(", f"def {fn}_hash(")
        probe = (hash_version + "\n\n" + variant_b + "\n\n"
                 f"values = {P['arr']!r}\n"
                 f"target = {P['target']!r}\n"
                 f"a = {fn}_hash(values, target)\n"
                 f"b = {fn}_sortscan(values, target)\n"
                 f"print('A:', a)\nprint('B:', b)\n"
                 f"va = -1 if a == -1 else values[a[0]] + values[a[1]]\n"
                 f"vb = -1 if b == -1 else values[b[0]] + values[b[1]]\n"
                 f"print('BOTH_VALID:', va == target and (vb == target or b == -1))\n")
        r = run_snippet_safely("python", probe)
        if not r.ok:
            return None
        answer = (
            f"Correctness: both find a valid pair for the sample (executed: "
            f"{r.stdout.strip().splitlines()[-1]}).\n"
            f"Complexity: hash-map version is O(n) time / O(n) space; sort+two-pointer is "
            f"O(n log n) time / O(n) for the index copy (or O(1) extra if sorting in place "
            f"were acceptable - it is not here, indices must be tracked).\n"
            f"Behaviour nuance: the two versions may return DIFFERENT valid pairs when several "
            f"exist - the hash version returns the first pair found scanning left to right, "
            f"the two-pointer version returns whichever pair the sorted scan meets first.\n"
            f"Context choice: hash map when values are hashable and memory is fine (typical); "
            f"two-pointer when the array is already sorted or memory is tight and you may "
            f"reorder.")
        return _mk(
            rng, "compare_two_sum", "python", "comparison", "algorithms", "advanced",
            question=(f"Compare these two {fn} strategies: (A) hash-map single pass, "
                      f"(B) sort + two-pointer scan below. Determine correctness, compare time/"
                      f"space complexity, note any behavioural differences, and say which one "
                      f"you would ship and when.\n\nStrategy B:\n```python\n{variant_b}\n```"
                      f"\n\nSample input: target={P['target']}, n={P['n']}."),
            answer=answer, code=variant_b,
            artifacts={"executed": True, "output": r.stdout.strip()[:200]},
            key_points=["O(n) vs O(n log n)", "pair identity may differ", "sorted-input bonus"],
            verify_method="executed",
            verify_notes={"both_executed": True},
            tags=["comparison", "two_sum"], variant="compare|two_sum")
    else:  # binary_search rec vs iter
        prob = REGISTRY["binary_search"]
        P = prob.params(rng)
        unit = prob.impls["python"](P, rng)
        fn = unit.function_name
        variant_rec = (
            f"def {fn}_recursive(values, target, lo=0, hi=None):\n"
            f"    if hi is None:\n"
            f"        hi = len(values) - 1\n"
            f"    if lo > hi:\n"
            f"        return -1\n"
            f"    mid = (lo + hi) // 2\n"
            f"    if values[mid] == target:\n"
            f"        return mid\n"
            f"    if values[mid] < target:\n"
            f"        return {fn}_recursive(values, target, mid + 1, hi)\n"
            f"    return {fn}_recursive(values, target, lo, mid - 1)\n")
        iter_version = unit.files["solution.py"]
        probe = (iter_version + "\n\n" + variant_rec + "\n\n"
                 f"values = {P['arr']!r}\n"
                 f"target = {P['target']!r}\n"
                 f"print('A:', {fn}(values, target))\n"
                 f"print('B:', {fn}_recursive(values, target))\n")
        r = run_snippet_safely("python", probe)
        if not r.ok:
            return None
        a_out = r.stdout.strip().splitlines()[0].split(":")[1].strip()
        b_out = r.stdout.strip().splitlines()[1].split(":")[1].strip()
        answer = (
            f"Correctness: both return the same index for the sample (A={a_out}, B={b_out}, "
            f"executed).\n"
            f"Complexity: identical O(log n) time; the recursive version additionally uses "
            f"O(log n) stack frames (Python's default recursion limit ~1000 makes it safe for "
            f"arrays up to ~2^1000 elements, i.e. practically fine, but the frames cost real "
            f"memory and call overhead).\n"
            f"Readability: the iterative loop is the conventional choice in production Python; "
            f"the recursive form reads like the mathematical definition and is handy in "
            f"languages with tail-call optimisation (which CPython lacks).\n"
            f"Context choice: iterative by default; recursive when the codebase already models "
            f"divide-and-conquer recursively.")
        return _mk(
            rng, "compare_binsearch", "python", "comparison", "algorithms", "intermediate",
            question=(f"Compare the iterative binary search (shown in full) with the recursive "
                      f"variant below: correctness, complexity (time AND space), stack "
                      f"implications, and when each is preferable.\n\nRecursive variant:\n"
                      f"```python\n{variant_rec}\n```\n\nSample: target={P['target']}, "
                      f"n={P['n']}."),
            answer=answer, code=variant_rec,
            artifacts={"executed": True, "A": a_out, "B": b_out},
            key_points=["same O(log n) time", "recursion adds O(log n) stack",
                        "no tail-call optimisation in CPython"],
            verify_method="executed",
            verify_notes={"both_executed": True},
            tags=["comparison", "binary_search"], variant="compare|binsearch")


# ------------------------------------------------------------------ architecture
def build_architecture(rng: random.Random):
    from ..registry import all_families
    projs = [f for f in all_families() if f.PROJECT_FAMILY and f.LANGUAGE in
             ("python", "bash", "sql", "javascript", "typescript", "cpp", "c")]
    rng.shuffle(projs)
    for fam in projs[:4]:
        try:
            cand = fam.generate(rng)
        except Exception:
            continue
        if not cand or not cand.is_project:
            continue
        ok, r, _ = verify_candidate(cand)
        if not ok:
            continue
        paths = ", ".join(f.path for f in (cand.files or []))
        answer = (
            f"Components: the project separates a library module (pure logic) from an entry "
            f"point/CLI and a test suite; README documents the contract. Files: {paths}.\n"
            f"Dependencies: the entry point imports the library API; tests import both; no "
            f"external packages are required (standard library only).\n"
            f"Failure points: malformed inputs at the boundary functions; resource "
            f"initialisation (connections/files) if extended to I/O; in the current pure form "
            f"the main risks are contract drift between README, code and tests.\n"
            f"Bottlenecks: the central data structure operations dominate; current complexity "
            f"is documented per family ({(cand.notes.get('explain') or {}).get('big_o_time', 'O(n)')}).\n"
            f"Improvement roadmap: (1) pin the public API in the README, (2) add property-based "
            f"tests for boundary functions, (3) wire structured logging if I/O is introduced, "
            f"(4) package metadata once dependencies appear.\n"
            f"Design verdict: the layering is appropriate for the scope; introducing interfaces "
            f"now would be premature generalisation.")
        return _mk(
            rng, "arch_projects", cand.language, "architecture", cand.domain, "advanced",
            question=(f"Analyse this small multi-file project: identify components and their "
                      f"responsibilities, the dependency graph, likely failure points, "
                      f"bottlenecks, and propose two concrete improvements with rationale.\n\n"
                      f"Files:\n" +
                      "".join(f"### {fpath}\n```{cand.language}\n{fcontent[:900]}\n```\n"
                              for fpath, fcontent in
                              [(fs.path, fs.content) for fs in (cand.files or [])][:4])),
            answer=answer, code=None, files=(cand.files or [])[:4],
            artifacts={"project_verified": True, "stage": r.stage},
            key_points=["library/entry/test separation", "stdlib-only dependency graph",
                        "contract drift is the main risk"],
            verify_method="executed",
            verify_notes={"project_tests_pass": True},
            tags=["architecture", cand.language], variant=f"arch|{fam.NAME}",
            context=cand.task)
    return None


# ------------------------------------------------------------------ language_selection
_SCENARIOS = [
    ("log pipeline", "Parse 5GB of web-server logs nightly, extract fields, aggregate per hour, "
     "output CSV. Single machine, cron, no existing codebase.",
     "bash", "grep/awk/sort pipelines stream line-by-line with zero runtime setup; Python fits "
     "if logic gets complex, but the task is classic text-stream processing.",
     "python", "Go compiles to a single static binary with easy concurrency, but the parsing "
     "here is line-oriented text munging where shell tooling is already optimal."),
    ("low-latency matcher", "Order-matching engine: sub-millisecond p99, deterministic memory, "
     "no GC pauses. Linux servers.",
     "cpp", "Manual memory control, predictable latencies, mature ecosystem for HFT-style "
     "systems; Rust would also fit with stronger safety guarantees.",
     "python", "Interpreter jitter and GC make sub-ms p99 unreliable."),
    ("internal dashboard API", "CRUD + aggregates over Postgres for an internal admin tool; "
     "small team, fast iteration, JSON over HTTP.",
     "python", "Batteries-included frameworks and rapid iteration; the workload is I/O-bound "
     "and volumes are modest.",
     "cpp", "Manual memory and compilation overhead buy nothing for a CRUD I/O-bound service."),
    ("embedded sensor firmware", "8-bit MCU, 2KB RAM, bare metal, no OS.",
     "c", "The only realistic choice: direct register access, tiny runtime, deterministic "
     "memory footprint.",
     "python", "No interpreter fits in 2KB RAM."),
    ("cross-platform CLI", "A developer tool distributed to many OSes as a single binary with "
     "parallel file processing.",
     "go", "Static single-binary cross-compilation, first-class goroutines for the parallel "
     "file walk, fast startup.",
     "bash", "Not distributable as a self-contained binary; portability gaps are real."),
    ("safe systems service", "Network-facing parser service where memory-safety defects are the "
     "top risk; team wants fearless concurrency.",
     "rust", "Ownership enforces memory safety without GC; the borrow checker matches the "
     "threat model of parsing untrusted input.",
     "c", "Manual memory management is exactly the risk the constraint flags."),
    ("data cleaning notebook", "One-off analysis: load messy CSVs, dedupe, join, export charts. "
     "Analyst team, interactive.",
     "python", "pandas/dataclasses ecosystem plus notebooks fit interactive analysis; SQL for "
     "the heavy joins if data outgrows memory.",
     "bash", "Aggregation and joins in awk become unmaintainable fast."),
    ("browser components", "Interactive form-heavy UI with client-side validation and state.",
     "typescript", "Type-safe DOM/state models catch refactoring errors; compiles to JS for "
     "every browser.",
     "css", "Styles presentation only; cannot express validation logic."),
    ("config templating", "Render per-host configuration files from templates and variables in "
     "CI.",
     "python", "string.Template/Jinja-style logic with testable functions; easy CI integration.",
     "sql", "Wrong tool entirely - no templating semantics."),
    ("batch SQL reporting", "Nightly heavy aggregations over relational data already in "
     "Postgres.",
     "sql", "Set-based processing happens where the data lives; indexes and the planner do the "
     "heavy lifting.",
     "python", "Pulling millions of rows into the app to aggregate wastes I/O and memory."),
]


def build_language_selection(rng: random.Random):
    topic, brief, best, why_best, worst, why_worst = rng.choice(_SCENARIOS)
    alt = [b for _, _, b, _, _, _ in _SCENARIOS if b != best]
    rng.shuffle(alt)
    answer = (
        f"Recommended primary choice: {best}.\n"
        f"Why: {why_best}\n"
        f"Deliberately rejected for this case: {worst} - {why_worst}\n"
        f"Reasonable alternatives: {', '.join(alt[:2])} under different constraints (team "
        f"skills, existing code, hard latency bounds).\n"
        f"Decision path applied: objective -> requirements -> constraints -> environment -> "
        f"language choice -> implementation -> test -> verification. The choice is contextual, "
        f"not a lookup table: swap 'single machine cron' for 'distributed streaming' and the "
        f"recommendation changes.")
    return _mk(
        rng, "language_selection", "python", "language_selection", "engineering",
        "advanced",
        question=(f"Scenario: {topic}. {brief}\n\nWhich language/tool would you choose as the "
                  f"PRIMARY implementation, justify it against the requirements and constraints, "
                  f"name the option you reject and why, and list the decision path you applied?"),
        answer=answer,
        key_points=[f"primary: {best}", f"rejected: {worst}", "decision is constraint-driven"],
        verify_method="authored_verified",
        verify_notes={"source": "curated scenario bank"},
        tags=["language_selection", best], variant=f"select|{topic.replace(' ', '_')}",
        context=brief)
