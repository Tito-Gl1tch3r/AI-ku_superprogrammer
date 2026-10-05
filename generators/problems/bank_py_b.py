"""Python implementations for the problem bank (part B)."""
from __future__ import annotations

import heapq
import random

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_a import _pick


# ---------------------------------------------------------------- word_frequency
def _wf_params(rng: random.Random):
    k = rng.randint(4, 40)
    vocab = ["log", "error", "warning", "start", "stop", "user", "login", "cache",
             "disk", "network", "retry", "timeout", "config", "worker", "queue",
             "memory", "job", "task", "report", "client"]
    lines = []
    for _ in range(k):
        words = [rng.choice(vocab) for _ in range(rng.randint(2, 9))]
        lines.append(" ".join(words))
    m = rng.randint(3, 8)
    return {"lines": lines, "m": m, "k": k}


def _wf_solve(P):
    counts = {}
    for line in P["lines"]:
        for w in line.split():
            counts[w] = counts.get(w, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:P["m"]]
    return "\n".join(f"{w} {c}" for w, c in top)


def _wf_spec(P, rng):
    return (f"Given {P['k']} lines of log-style text, implement `top_words(lines, m)` that returns "
            f"the m most frequent words as a list of (word, count) tuples. Words are separated by "
            f"single spaces. Ties in count are broken by ascending alphabetical order. Return "
            f"exactly m tuples (or fewer if the text has fewer distinct words). Here m = {P['m']}.")


def _wf_io(P):
    stdin = f"{P['m']}\n" + "\n".join(P["lines"]) + "\n"
    return [(stdin, _wf_solve(P))]


def _py_wf(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["top_words", "most_frequent", "frequent_terms"])
    body = (f"def {f}(lines, m):\n"
            f"    \"\"\"Return the m most frequent words as (word, count) tuples,\n"
            f"    ties broken alphabetically.\"\"\"\n"
            f"    counts = {{}}\n"
            f"    for line in lines:\n"
            f"        for word in line.split():\n"
            f"            counts[word] = counts.get(word, 0) + 1\n"
            f"    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))\n"
            f"    return ranked[:m]\n")
    lines_lit = "[" + ", ".join(repr(l) for l in P["lines"]) + "]"
    expected = _wf_solve(P).split("\n")
    exp_lit = "[" + ", ".join(f"('{w}', {c})" for w, c in (e.split() for e in expected)) + "]"
    tests = (f"def run_tests():\n"
             f"    lines = {lines_lit}\n"
             f"    assert {f}(lines, {P['m']}) == {exp_lit}\n"
             f"    assert {f}([], 3) == []\n"
             f"    assert {f}(['a b a'], 2) == [('a', 2), ('b', 1)]\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    data = sys.stdin.read().splitlines()\n"
           "    m = int(data[0])\n    lines = data[1:]\n"
           f"    for w, c in {f}(lines, m):\n"
           "        print(w, c)\n\n\nmain()\n"}

    def bug_tie(files):
        return {k: t.replace("key=lambda kv: (-kv[1], kv[0])", "key=lambda kv: (kv[1], kv[0])")
                for k, t in files.items()}

    def bug_top(files):
        return {k: t.replace("return ranked[:m]", "return ranked[:m + 1]") for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"tie_break_reversed": bug_tie, "off_by_top_n": bug_top},
                    notes={"purpose": "Rank words by frequency with deterministic tie-breaking.",
                           "approach": "Count with a dict, then sort by (-count, word) and slice the first m.",
                           "key_points": ["-count makes the sort descending by frequency",
                                          "word as secondary key breaks ties alphabetically",
                                          "slicing beyond the list length is safe in Python"],
                           "big_o_time": "O(W + U log U) for W words, U distinct",
                           "big_o_space": "O(U)",
                           "edge_cases": ["empty input", "fewer distinct words than m",
                                          "all words equal frequency"]})


register_problem(Problem(pid="word_frequency", domain="text_processing",
                         params=_wf_params, spec=_wf_spec, io=_wf_io, solve=_wf_solve,
                         impls={"python": _py_wf}))


# ---------------------------------------------------------------- run_length_encode
def _rle_params(rng: random.Random):
    alphabet = "abcde"
    s = []
    while len(s) < rng.randint(6, 60):
        s.append(rng.choice(alphabet) * rng.randint(1, 9))
    return {"s": "".join(s)}


def _rle_solve(P):
    s = P["s"]
    out = []
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(f"{s[i]}{j - i}")
        i = j
    return "".join(out)


def _rle_spec(P, rng):
    f = rng.choice(["run_length_encode", "rle_encode", "encode_runs"])
    return (f"Implement `{f}(s)` that encodes a string by replacing each run of repeated "
            f"characters with the character followed by the run length, e.g. 'aaabb' -> 'a3b2'. "
            f"A single occurrence still shows the count 1 ('x' -> 'x1'). The input string has "
            f"length {len(P['s'])} over the alphabet {{a,b,c,d,e}} and runs shorter than 10.")


def _rle_io(P):
    return [(P["s"] + "\n", _rle_solve(P))]


def _py_rle(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["run_length_encode", "rle_encode", "encode_runs"])
    body = (f"def {f}(s):\n"
            f"    \"\"\"Encode runs: 'aaabb' -> 'a3b2' (singles keep the count).\"\"\"\n"
            f"    if not s:\n"
            f"        return ''\n"
            f"    parts = []\n"
            f"    run_char, run_len = s[0], 1\n"
            f"    for ch in s[1:]:\n"
            f"        if ch == run_char:\n"
            f"            run_len += 1\n"
            f"        else:\n"
            f"            parts.append(run_char + str(run_len))\n"
            f"            run_char, run_len = ch, 1\n"
            f"    parts.append(run_char + str(run_len))\n"
            f"    return ''.join(parts)\n")
    expected = _rle_solve(P)
    tests = (f"def run_tests():\n"
             f"    assert {f}('{P['s']}') == '{expected}'\n"
             f"    assert {f}('') == ''\n"
             f"    assert {f}('x') == 'x1'\n"
             f"    assert {f}('aabbbcc') == 'a2b3c2'\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    s = sys.stdin.readline().rstrip('\\n')\n"
           f"    print({f}(s))\n\n\nmain()\n"}

    def bug_flush(files):
        return {k: t.replace("    parts.append(run_char + str(run_len))\n    return ''.join(parts)",
                             "    return ''.join(parts)") for k, t in files.items()}

    def bug_start(files):
        return {k: t.replace("run_char, run_len = s[0], 1", "run_char, run_len = s[0], 0")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"missing_final_flush": bug_flush, "count_started_at_zero": bug_start},
                    notes={"purpose": "Compress runs of equal characters into char+count pairs.",
                           "approach": "Track the current run char and length; flush on change and once after the loop.",
                           "key_points": ["the final flush after the loop is mandatory (last run)",
                                          "singles are encoded with an explicit 1",
                                          "empty input returns the empty string"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty string", "single char", "run at end of string"]})


register_problem(Problem(pid="run_length_encode", domain="text_processing",
                         params=_rle_params, spec=_rle_spec, io=_rle_io, solve=_rle_solve,
                         impls={"python": _py_rle}))


# ---------------------------------------------------------------- sieve_primes
def _sp_params(rng: random.Random):
    return {"n": rng.randint(30, 4000)}


def _sp_solve(P):
    n = P["n"]
    is_p = [True] * (n + 1)
    if n >= 0:
        is_p[0] = False
    if n >= 1:
        is_p[1] = False
    i = 2
    while i * i <= n:
        if is_p[i]:
            for j in range(i * i, n + 1, i):
                is_p[j] = False
        i += 1
    return " ".join(str(x) for x in range(2, n + 1) if is_p[x])


def _sp_spec(P, rng):
    f = rng.choice(["sieve_primes", "primes_up_to", "all_primes"])
    return (f"Implement `{f}(n)` that returns a list of all prime numbers <= {P['n']} in ascending "
            f"order, using the Sieve of Eratosthenes.")


def _sp_io(P):
    return [(f"{P['n']}\n", _sp_solve(P))]


def _py_sp(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["sieve_primes", "primes_up_to", "all_primes"])
    body = (f"def {f}(n):\n"
            f"    \"\"\"Return all primes <= n (ascending) via the Sieve of Eratosthenes.\"\"\"\n"
            f"    if n < 2:\n"
            f"        return []\n"
            f"    is_prime = [True] * (n + 1)\n"
            f"    is_prime[0] = is_prime[1] = False\n"
            f"    i = 2\n"
            f"    while i * i <= n:\n"
            f"        if is_prime[i]:\n"
            f"            for multiple in range(i * i, n + 1, i):\n"
            f"                is_prime[multiple] = False\n"
            f"        i += 1\n"
            f"    return [x for x in range(2, n + 1) if is_prime[x]]\n")
    expected = _sp_solve(P)
    tests = (f"def run_tests():\n"
             f"    assert {f}({P['n']}) == [{expected.replace(' ', ', ')}]\n"
             f"    assert {f}(1) == []\n"
             f"    assert {f}(2) == [2]\n"
             f"    assert {f}(10) == [2, 3, 5, 7]\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           f"    n = int(sys.stdin.readline())\n    print(' '.join(map(str, {f}(n))))\n\n\nmain()\n"}

    def bug_start(files):
        return {k: t.replace("range(i * i, n + 1, i)", "range(i, n + 1, i)") for k, t in files.items()}

    def bug_bound(files):
        return {k: t.replace("while i * i <= n:", "while i * i <= n + 1:") for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"marks_itself_composite": bug_start, "overextended_bound": bug_bound},
                    notes={"purpose": "Enumerate primes up to n in near-linear time.",
                           "approach": "Boolean sieve: for each prime i, cross out multiples starting at i*i.",
                           "key_points": ["crossing out starts at i*i because smaller multiples were already crossed by smaller primes",
                                          "the outer loop stops at sqrt(n)",
                                          "0 and 1 are not prime"],
                           "big_o_time": "O(n log log n)", "big_o_space": "O(n)",
                           "edge_cases": ["n < 2", "n = 2", "perfect squares of primes"]})


register_problem(Problem(pid="sieve_primes", domain="algorithms",
                         params=_sp_params, spec=_sp_spec, io=_sp_io, solve=_sp_solve,
                         impls={"python": _py_sp}))


# ---------------------------------------------------------------- matrix_multiply
def _mm_params(rng: random.Random):
    n, m, k = (rng.randint(1, 12), rng.randint(1, 12), rng.randint(1, 12))
    A = [[rng.randint(-9, 9) for _ in range(m)] for _ in range(n)]
    B = [[rng.randint(-9, 9) for _ in range(k)] for _ in range(m)]
    return {"n": n, "m": m, "k": k, "A": A, "B": B}


def _mm_solve(P):
    C = [[sum(P["A"][i][t] * P["B"][t][j] for t in range(P["m"])) for j in range(P["k"])]
         for i in range(P["n"])]
    return "\n".join(" ".join(map(str, row)) for row in C)


def _mm_spec(P, rng):
    f = rng.choice(["matmul", "multiply_matrices", "matrix_product"])
    return (f"Implement `{f}(A, B)` that multiplies matrix A ({P['n']}x{P['m']}) by matrix B "
            f"({P['m']}x{P['k']}) with integer entries and returns the {P['n']}x{P['k']} result "
            f"as a list of row lists. Assume dimensions are compatible.")


def _mm_io(P):
    lines = [f"{P['n']} {P['m']} {P['k']}"]
    lines += [" ".join(map(str, row)) for row in P["A"]]
    lines += [" ".join(map(str, row)) for row in P["B"]]
    return [("\n".join(lines) + "\n", _mm_solve(P))]


def _py_mm(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["matmul", "multiply_matrices", "matrix_product"])
    body = (f"def {f}(A, B):\n"
            f"    \"\"\"Matrix product A x B; A is n x m, B is m x k.\"\"\"\n"
            f"    n, m, k = len(A), len(B), len(B[0])\n"
            f"    C = [[0] * k for _ in range(n)]\n"
            f"    for i in range(n):\n"
            f"        for j in range(k):\n"
            f"            total = 0\n"
            f"            for t in range(m):\n"
            f"                total += A[i][t] * B[t][j]\n"
            f"            C[i][j] = total\n"
            f"    return C\n")
    a_lit, b_lit = repr(P["A"]), repr(P["B"])
    rows = _mm_solve(P).split("\n")
    expected = "[" + ", ".join("[" + r + "]" for r in rows) + "]"
    tests = (f"def run_tests():\n"
             f"    A = {a_lit}\n    B = {b_lit}\n"
             f"    assert {f}(A, B) == {expected}\n"
             f"    assert {f}([[2]], [[3]]) == [[6]]\n"
             f"    assert {f}([[1, 0], [0, 1]], [[5, 6], [7, 8]]) == [[5, 6], [7, 8]]\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    data = sys.stdin.read().split()\n    it = iter(data)\n"
           "    n, m, k = int(next(it)), int(next(it)), int(next(it))\n"
           "    A = [[int(next(it)) for _ in range(m)] for _ in range(n)]\n"
           "    B = [[int(next(it)) for _ in range(k)] for _ in range(m)]\n"
           f"    C = {f}(A, B)\n    print('\\n'.join(' '.join(map(str, r)) for r in C))\n\n\nmain()\n"}

    def bug_index(files):
        return {k: t.replace("total += A[i][t] * B[t][j]", "total += A[i][t] * B[j][t]")
                for k, t in files.items()}

    def bug_accum(files):
        return {k: t.replace("            total = 0\n", "            total = C[i][j]\n")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"swapped_indices": bug_index, "accumulator_not_reset": bug_accum},
                    notes={"purpose": "Classic triple-loop matrix multiplication.",
                           "approach": "For each output cell (i, j) accumulate A[i][t] * B[t][j] over t.",
                           "key_points": ["B is indexed [t][j]: t walks B's rows, j its columns",
                                          "the accumulator must reset for every cell",
                                          "naive cost is O(n*m*k)"],
                           "big_o_time": "O(n*m*k)", "big_o_space": "O(n*k) for the output",
                           "edge_cases": ["1x1 matrices", "identity multiplication",
                                          "negative entries"]})


register_problem(Problem(pid="matrix_multiply", domain="algorithms",
                         params=_mm_params, spec=_mm_spec, io=_mm_io, solve=_mm_solve,
                         impls={"python": _py_mm}))


# ---------------------------------------------------------------- dijkstra
def _dj_params(rng: random.Random):
    n = rng.randint(4, 10)
    edges = []
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < 0.4:
                edges.append((u, v, rng.randint(1, 20)))
    m = len(edges)
    src = rng.randrange(n)
    return {"n": n, "m": m, "edges": edges, "src": src}


def _dj_solve(P):
    n, src = P["n"], P["src"]
    adj = [[] for _ in range(n)]
    for u, v, w in P["edges"]:
        adj[u].append((v, w))
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    heap = [(0, src)]
    done = [False] * n
    while heap:
        d, u = heapq.heappop(heap)
        if done[u]:
            continue
        done[u] = True
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return " ".join(str(x) if x != INF else "-1" for x in dist)


def _dj_spec(P, rng):
    f = rng.choice(["dijkstra", "shortest_paths", "single_source_distances"])
    return (f"Implement `{f}(n, edges, src)` that computes shortest distances from node {P['src']} "
            f"in a directed graph with {P['n']} nodes (0..{P['n'] - 1}) and {P['m']} weighted edges "
            f"(positive weights, no negative cycles). Return a list of n distances; use -1 for "
            f"unreachable nodes.")


def _dj_io(P):
    lines = [f"{P['n']} {P['m']} {P['src']}"]
    lines += [f"{u} {v} {w}" for u, v, w in P["edges"]]
    return [("\n".join(lines) + "\n", _dj_solve(P))]


def _py_dj(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["dijkstra", "shortest_paths", "single_source_distances"])
    edges_lit = repr(P["edges"])
    body = (f"import heapq\n\n\n"
            f"def {f}(n, edges, src):\n"
            f"    \"\"\"Shortest distances from src (list; -1 for unreachable).\"\"\"\n"
            f"    adj = [[] for _ in range(n)]\n"
            f"    for u, v, w in edges:\n"
            f"        adj[u].append((v, w))\n"
            f"    INF = float('inf')\n"
            f"    dist = [INF] * n\n"
            f"    dist[src] = 0\n"
            f"    heap = [(0, src)]\n"
            f"    settled = [False] * n\n"
            f"    while heap:\n"
            f"        d, u = heapq.heappop(heap)\n"
            f"        if settled[u]:\n"
            f"            continue\n"
            f"        settled[u] = True\n"
            f"        for v, w in adj[u]:\n"
            f"            nd = d + w\n"
            f"            if nd < dist[v]:\n"
            f"                dist[v] = nd\n"
            f"                heapq.heappush(heap, (nd, v))\n"
            f"    return [x if x != INF else -1 for x in dist]\n")
    expected = _dj_solve(P)
    tests = (f"def run_tests():\n"
             f"    assert {f}({P['n']}, {edges_lit}, {P['src']}) == [{expected.replace(' ', ', ')}]\n"
             f"    assert {f}(2, [(0, 1, 7)], 0) == [0, 7]\n"
             f"    assert {f}(2, [(0, 1, 7)], 1) == [-1, 0]\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    data = sys.stdin.read().split()\n    it = iter(data)\n"
           "    n, m, src = int(next(it)), int(next(it)), int(next(it))\n"
           "    edges = [(int(next(it)), int(next(it)), int(next(it))) for _ in range(m)]\n"
           f"    print(' '.join(map(str, {f}(n, edges, src))))\n\n\nmain()\n"}

    def bug_weight(files):
        return {k: t.replace("nd = d + w", "nd = d") for k, t in files.items()}

    def bug_init(files):
        return {k: t.replace("    dist[src] = 0\n", "    dist = [0] * n\n" + "    dist[src] = 0\n")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"edge_weight_ignored": bug_weight, "distances_prezeroed": bug_init},
                    notes={"purpose": "Single-source shortest paths with non-negative weights.",
                           "approach": "Min-heap of (distance, node); settle each node once and relax outgoing edges.",
                           "key_points": ["the settled flag skips stale heap entries",
                                          "relaxation only improves strictly smaller distances",
                                          "-1 marks unreachable nodes"],
                           "big_o_time": "O((V + E) log V)", "big_o_space": "O(V + E)",
                           "edge_cases": ["unreachable nodes", "source itself", "parallel better paths"]})


register_problem(Problem(pid="dijkstra", domain="algorithms",
                         params=_dj_params, spec=_dj_spec, io=_dj_io, solve=_dj_solve,
                         impls={"python": _py_dj}))


# ---------------------------------------------------------------- lru_cache
def _lru_params(rng: random.Random):
    cap = rng.randint(2, 5)
    ops, expected = [], []
    od = {}  # key -> value, insertion order = recency
    keys = [f"k{i}" for i in range(cap + 3)]
    for _ in range(rng.randint(8, 22)):
        k = rng.choice(keys)
        if rng.random() < 0.55:
            v = rng.randint(0, 99)
            ops.append(("put", k, v))
            if k in od:
                del od[k]
            od[k] = v
            if len(od) > cap:
                oldest = next(iter(od))
                del od[oldest]
        else:
            ops.append(("get", k))
            if k in od:  # a get refreshes recency exactly like the real cache
                val = od.pop(k)
                od[k] = val
            expected.append(str(od[k]) if k in od else "MISS")
    return {"cap": cap, "ops": ops, "expected": expected}


def _lru_solve(P):
    return " ".join(P["expected"]) if P["expected"] else "(no gets)"


def _lru_spec(P, rng):
    f = rng.choice(["LRUCache", "LruCache", "RecencyCache"])
    return (f"Design an LRU cache class `{f}` with capacity {P['cap']}: `{f}(capacity)` constructor, "
            f"`get(key)` returning the value or None when absent, and `put(key, value)`. Both "
            f"operations count as key usage; when capacity is exceeded the least recently used "
            f"entry is evicted. Operations run in O(1) average time.")


def _lru_io(P):
    lines = [str(P["cap"])]
    for op in P["ops"]:
        lines.append(" ".join(str(x) for x in op))
    return [("\n".join(lines) + "\n", _lru_solve(P))]


def _py_lru(P, rng: random.Random) -> CodeUnit:
    cls = rng.choice(["LRUCache", "LruCache", "RecencyCache"])
    ops_lit = repr(P["ops"])
    body = (f"from collections import OrderedDict\n\n\n"
            f"class {cls}:\n"
            f"    \"\"\"LRU cache: O(1) get/put backed by an OrderedDict.\"\"\"\n\n"
            f"    def __init__(self, capacity):\n"
            f"        if capacity <= 0:\n"
            f"            raise ValueError('capacity must be positive')\n"
            f"        self.capacity = capacity\n"
            f"        self._data = OrderedDict()\n\n"
            f"    def get(self, key):\n"
            f"        if key not in self._data:\n"
            f"            return None\n"
            f"        self._data.move_to_end(key)\n"
            f"        return self._data[key]\n\n"
            f"    def put(self, key, value):\n"
            f"        if key in self._data:\n"
            f"            self._data.move_to_end(key)\n"
            f"        self._data[key] = value\n"
            f"        if len(self._data) > self.capacity:\n"
            f"            self._data.popitem(last=False)\n")
    driver = (f"def run_tests():\n"
              f"    c = {cls}({P['cap']})\n"
              f"    ops = {ops_lit}\n"
              f"    expected = {P['expected']!r}\n"
              f"    outs = []\n"
              f"    for op in ops:\n"
              f"        if op[0] == 'put':\n"
              f"            c.put(op[1], op[2])\n"
              f"        else:\n"
              f"            v = c.get(op[1])\n"
              f"            outs.append(str(v) if v is not None else 'MISS')\n"
              f"    assert outs == list(expected)\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    lines = sys.stdin.read().splitlines()\n"
           f"    c = {cls}(int(lines[0]))\n"
           "    out = []\n"
           "    for line in lines[1:]:\n"
           "        parts = line.split()\n"
           "        if parts[0] == 'put':\n"
           "            c.put(parts[1], int(parts[2]))\n"
           "        else:\n"
           "            v = c.get(parts[1])\n"
           "            out.append(str(v) if v is not None else 'MISS')\n"
           "    print(' '.join(out))\n\n\nmain()\n"}

    def bug_no_touch(files):
        return {k: t.replace("        self._data.move_to_end(key)\n        return self._data[key]",
                             "        return self._data[key]") for k, t in files.items()}

    def bug_evict(files):
        return {k: t.replace("self._data.popitem(last=False)", "self._data.popitem()")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=driver, cli=cli, function_name=cls,
                    bugs={"get_breaks_recency": bug_no_touch, "evicts_newest": bug_evict},
                    notes={"purpose": "Constant-time LRU cache using OrderedDict recency tracking.",
                           "approach": "OrderedDict keeps insertion order; move_to_end on access; popitem(last=False) evicts the LRU entry.",
                           "key_points": ["both get and put must refresh recency",
                                          "put of an existing key updates without growing",
                                          "popitem(last=False) removes the least recently used entry"],
                           "big_o_time": "O(1) average per operation", "big_o_space": "O(capacity)",
                           "edge_cases": ["capacity 1", "get missing key", "overwrite existing key"]})


register_problem(Problem(pid="lru_cache", domain="data_structures",
                         params=_lru_params, spec=_lru_spec, io=_lru_io, solve=_lru_solve,
                         impls={"python": _py_lru}))


# ---------------------------------------------------------------- max_subarray (Kadane)
def _msa_params(rng: random.Random):
    n = rng.randint(5, 300)
    arr = [rng.randint(-50, 50) for _ in range(n)]
    return {"n": n, "arr": arr}


def _msa_solve(P):
    best = cur = P["arr"][0]
    for x in P["arr"][1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return str(best)


def _msa_spec(P, rng):
    f = rng.choice(["max_subarray_sum", "kadane_max", "best_contiguous_sum"])
    return (f"Implement `{f}(values)` that returns the maximum sum over all non-empty contiguous "
            f"subarrays of a list of {P['n']} integers (negatives included). Target linear time.")


def _msa_io(P):
    stdin = f"{P['n']}\n" + " ".join(map(str, P["arr"])) + "\n"
    return [(stdin, _msa_solve(P))]


def _py_msa(P, rng: random.Random) -> CodeUnit:
    f = rng.choice(["max_subarray_sum", "kadane_max", "best_contiguous_sum"])
    a = ", ".join(map(str, P["arr"]))
    body = (f"def {f}(values):\n"
            f"    \"\"\"Maximum contiguous subarray sum (Kadane's algorithm).\"\"\"\n"
            f"    best = cur = values[0]\n"
            f"    for x in values[1:]:\n"
            f"        cur = max(x, cur + x)\n"
            f"        best = max(best, cur)\n"
            f"    return best\n")
    tests = (f"def run_tests():\n"
             f"    assert {f}([{a}]) == {_msa_solve(P)}\n"
             f"    assert {f}([-3, -1, -7]) == -1\n"
             f"    assert {f}([5]) == 5\n"
             f"    assert {f}([1, -2, 3, 4]) == 7\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    data = sys.stdin.read().split()\n"
           "    n = int(data[0])\n    arr = [int(x) for x in data[1:1 + n]]\n"
           f"    print({f}(arr))\n\n\nmain()\n"}

    def bug_extend(files):
        return {k: t.replace("cur = max(x, cur + x)", "cur = cur + x") for k, t in files.items()}

    def bug_init(files):
        return {k: t.replace("best = cur = values[0]", "best, cur = 0, 0") for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"never_restart_run": bug_extend, "zero_floor_init": bug_init},
                    notes={"purpose": "Maximum subarray sum in O(n) with Kadane's algorithm.",
                           "approach": "Either extend the current run or restart at x, whichever is larger; track the best seen.",
                           "key_points": ["max(x, cur + x) lets the run restart when the prefix is harmful",
                                          "initialising best to values[0] handles all-negative arrays",
                                          "the subarray must be non-empty"],
                           "big_o_time": "O(n)", "big_o_space": "O(1)",
                           "edge_cases": ["all negative", "single element", "all positive"]})


register_problem(Problem(pid="max_subarray", domain="algorithms",
                         params=_msa_params, spec=_msa_spec, io=_msa_io, solve=_msa_solve,
                         impls={"python": _py_msa}))


# ---------------------------------------------------------------- prefix_sums
def _ps_params(rng: random.Random):
    n = rng.randint(5, 400)
    q = rng.randint(3, 10)
    arr = [rng.randint(-100, 100) for _ in range(n)]
    queries = []
    for _ in range(q):
        l = rng.randrange(n)
        r = rng.randrange(l, n)
        queries.append((l, r))
    return {"n": n, "q": q, "arr": arr, "queries": queries}


def _ps_solve(P):
    pre = [0]
    for x in P["arr"]:
        pre.append(pre[-1] + x)
    return " ".join(str(pre[r + 1] - pre[l]) for l, r in P["queries"])


def _ps_spec(P, rng):
    f = rng.choice(["PrefixSums", "RangeSummer"])
    return (f"Implement a class `{f}` built from a list of {P['n']} integers that answers range-sum "
            f"queries `sum_range(l, r)` (inclusive both ends) in O(1) after O(n) preprocessing. "
            f"There are {P['q']} sample queries in the tests.")


def _ps_io(P):
    lines = [f"{P['n']} {P['q']}", " ".join(map(str, P["arr"]))]
    lines += [f"{l} {r}" for l, r in P["queries"]]
    return [("\n".join(lines) + "\n", _ps_solve(P))]


def _py_ps(P, rng: random.Random) -> CodeUnit:
    cls = rng.choice(["PrefixSums", "RangeSummer"])
    a = ", ".join(map(str, P["arr"]))
    qs = P["queries"]
    body = (f"class {cls}:\n"
            f"    \"\"\"O(1) range sums via a prefix array of length n + 1.\"\"\"\n\n"
            f"    def __init__(self, values):\n"
            f"        self.pre = [0]\n"
            f"        for x in values:\n"
            f"            self.pre.append(self.pre[-1] + x)\n\n"
            f"    def sum_range(self, l, r):\n"
            f"        if l < 0 or r >= len(self.pre) - 1 or l > r:\n"
            f"            raise IndexError('bad range')\n"
            f"        return self.pre[r + 1] - self.pre[l]\n")
    expected = _ps_solve(P)
    tests = (f"def run_tests():\n"
             f"    ps = {cls}([{a}])\n"
             f"    assert [ps.sum_range(l, r) for (l, r) in {qs!r}] == [{expected.replace(' ', ', ')}]\n"
             f"    try:\n"
             f"        ps.sum_range(2, 1)\n"
             f"        assert False, 'expected IndexError'\n"
             f"    except IndexError:\n"
             f"        pass\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n"
           "    data = sys.stdin.read().split()\n"
           "    n, q = int(data[0]), int(data[1])\n"
           "    arr = [int(x) for x in data[2:2 + n]]\n"
           "    rest = [int(x) for x in data[2 + n:2 + n + 2 * q]]\n"
           f"    ps = {cls}(arr)\n"
           "    print(' '.join(str(ps.sum_range(rest[i], rest[i + 1])) for i in range(0, 2 * q, 2)))\n\n\nmain()\n"}

    def bug_off(files):
        return {k: t.replace("return self.pre[r + 1] - self.pre[l]", "return self.pre[r] - self.pre[l]")
                for k, t in files.items()}

    def bug_build(files):
        return {k: t.replace("for x in values:\n            self.pre.append(self.pre[-1] + x)",
                             "for i, x in enumerate(values):\n            self.pre.append(pre_get(self.pre, i) + x)")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=cls,
                    bugs={"right_endpoint_excluded": bug_off},
                    notes={"purpose": "Constant-time range sums with prefix accumulation.",
                           "approach": "pre[i+1] = sum of values[0..i]; sum(l, r) = pre[r+1] - pre[l].",
                           "key_points": ["the prefix array has one extra leading zero",
                                          "inclusive r requires pre[r+1], not pre[r]",
                                          "out-of-order or out-of-bounds ranges raise IndexError"],
                           "big_o_time": "O(n) build, O(1) per query", "big_o_space": "O(n)",
                           "edge_cases": ["single-element range", "full-range query", "invalid ranges raise"]})


register_problem(Problem(pid="prefix_sums", domain="algorithms",
                         params=_ps_params, spec=_ps_spec, io=_ps_io, solve=_ps_solve,
                         impls={"python": _py_ps}))
