"""Python implementations for the problem bank (part A: core algorithms)."""
from __future__ import annotations

import random

from .bank_core import CodeUnit, Problem, register_problem

NAME_POOLS = {
    "seq": ["values", "numbers", "data", "items", "elements", "samples", "entries"],
    "fn_search": ["binary_search", "find_sorted", "locate", "search_value", "index_of_sorted"],
    "fn_sort": ["merge_sort", "sort_values", "stable_sort", "merge_sort_recursive"],
    "fn_pair": ["two_sum", "find_pair", "pair_with_sum", "locate_pair"],
    "fn_paren": ["is_balanced", "valid_brackets", "check_brackets", "brackets_ok"],
    "fn_fib": ["fibonacci", "fib", "nth_fibonacci"],
}


def _pick(rng, key):
    return rng.choice(NAME_POOLS[key])


# ---------------------------------------------------------------- binary_search
def _bs_params(rng: random.Random):
    n = rng.randint(8, 900)
    arr = sorted(rng.sample(range(-10_000, 10_000), n))
    variant = rng.choice(["present", "absent_low", "absent_high", "absent_middle"])
    if variant == "present":
        idx = rng.randrange(n)
        target = arr[idx]
    elif variant == "absent_low":
        target = arr[0] - rng.randint(1, 50)
        idx = -1
    elif variant == "absent_high":
        target = arr[-1] + rng.randint(1, 50)
        idx = -1
    else:
        while True:
            t = rng.randint(arr[0], arr[-1])
            if t not in set(arr):
                target, idx = t, -1
                break
    return {"n": n, "arr": arr, "target": target, "idx": idx, "variant": variant}


def _bs_spec(P, rng):
    where = {"present": "The target IS present in the list.",
             "absent_low": "The target is smaller than every element.",
             "absent_high": "The target is larger than every element.",
             "absent_middle": "The target is missing but lies inside the value range."}[P["variant"]]
    return (f"Implement `{_pick(rng, 'fn_search')}(values, target)` that searches a sorted list of "
            f"{P['n']} integers for `target` using binary search and returns its zero-based index, "
            f"or -1 if the target is not present. The list is sorted ascending and has no duplicates. "
            f"{where} Target value: {P['target']}.")


def _bs_solve(P):
    return str(P["idx"])


def _bs_io(P):
    stdin = f"{P['n']} {P['target']}\n" + " ".join(map(str, P["arr"])) + "\n"
    return [(stdin, _bs_solve(P))]


def _py_bs(P, rng: random.Random) -> CodeUnit:
    v = _pick(rng, "seq")
    f = _pick(rng, "fn_search")
    a = ", ".join(map(str, P["arr"]))
    code = (f"def {f}({v}, target):\n"
            f"    \"\"\"Return index of target in ascending sorted {v}, else -1.\"\"\"\n"
            f"    lo, hi = 0, len({v}) - 1\n"
            f"    while lo <= hi:\n"
            f"        mid = (lo + hi) // 2\n"
            f"        if {v}[mid] == target:\n"
            f"            return mid\n"
            f"        if {v}[mid] < target:\n"
            f"            lo = mid + 1\n"
            f"        else:\n"
            f"            hi = mid - 1\n"
            f"    return -1\n")
    tests = (f"def run_tests():\n"
             f"    assert {f}([{a}], {P['target']}) == {P['idx']}\n"
             f"    assert {f}([], 7) == -1\n"
             f"    assert {f}([4], 4) == 0\n"
             f"    assert {f}([1, 3, 5], 4) == -1\n"
             f"    assert {f}([1, 3, 5], 5) == 2\n")
    cli = {"main.py":
           f"import sys\n\n\ndef {f}({v}, target):\n"
           f"    lo, hi = 0, len({v}) - 1\n"
           f"    while lo <= hi:\n"
           f"        mid = (lo + hi) // 2\n"
           f"        if {v}[mid] == target:\n"
           f"            return mid\n"
           f"        if {v}[mid] < target:\n"
           f"            lo = mid + 1\n"
           f"        else:\n"
           f"            hi = mid - 1\n"
           f"    return -1\n\n\ndef main():\n"
           f"    data = sys.stdin.read().split()\n"
           f"    n, target = int(data[0]), int(data[1])\n"
           f"    arr = [int(x) for x in data[2:2 + n]]\n"
           f"    print({f}(arr, target))\n\n\nmain()\n"}

    def bug_flip(files):
        return {k: t.replace(f"if {v}[mid] < target:", f"if {v}[mid] <= target:")
                for k, t in files.items()}

    def bug_bound(files):
        return {k: t.replace(f"lo, hi = 0, len({v}) - 1", f"lo, hi = 0, len({v})")
                for k, t in files.items()}

    def bug_ret(files):
        return {k: t.replace("    return -1\n", "    return lo\n")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"comparison_flip": bug_flip, "upper_bound_init": bug_bound,
                          "sentinel_return": bug_ret},
                    notes={"purpose": "Locate a value in a sorted list in O(log n) using binary search.",
                           "approach": "Maintain an inclusive [lo, hi] window; compare the middle element, halve the window each step.",
                           "key_points": ["invariant: if target exists, its index stays inside [lo, hi]",
                                          "mid uses (lo + hi) // 2 which cannot overflow in Python",
                                          "loop ends when the window is empty -> return -1"],
                           "big_o_time": "O(log n)", "big_o_space": "O(1)",
                           "edge_cases": ["empty list", "single element", "target below/above range",
                                          "target between elements"]})


def _bs_problem():
    return Problem(pid="binary_search", domain="algorithms",
                   params=_bs_params, spec=_bs_spec, io=_bs_io, solve=_bs_solve,
                   impls={"python": _py_bs})


register_problem(_bs_problem())


# ---------------------------------------------------------------- merge_sort
def _ms_params(rng: random.Random):
    n = rng.randint(6, 400)
    arr = [rng.randint(-999, 999) for _ in range(n)]
    return {"n": n, "arr": arr}


def _ms_spec(P, rng):
    f = _pick(rng, "fn_sort")
    return (f"Implement `{f}(values)` that sorts a list of {P['n']} integers (duplicates and "
            f"negatives allowed) in ascending order using the merge sort algorithm. The function "
            f"must return a new sorted list and must not mutate the input.")


def _ms_solve(P):
    return " ".join(map(str, sorted(P["arr"])))


def _ms_io(P):
    stdin = f"{P['n']}\n" + " ".join(map(str, P["arr"])) + "\n"
    return [(stdin, _ms_solve(P))]


def _py_ms(P, rng: random.Random) -> CodeUnit:
    v = _pick(rng, "seq")
    f = _pick(rng, "fn_sort")
    a = ", ".join(map(str, P["arr"]))
    body = (f"def {f}({v}):\n"
            f"    \"\"\"Return a new ascending-sorted list using merge sort.\"\"\"\n"
            f"    if len({v}) <= 1:\n"
            f"        return list({v})\n"
            f"    mid = len({v}) // 2\n"
            f"    left = {f}({v}[:mid])\n"
            f"    right = {f}({v}[mid:])\n"
            f"    merged = []\n"
            f"    i = j = 0\n"
            f"    while i < len(left) and j < len(right):\n"
            f"        if left[i] <= right[j]:\n"
            f"            merged.append(left[i])\n"
            f"            i += 1\n"
            f"        else:\n"
            f"            merged.append(right[j])\n"
            f"            j += 1\n"
            f"    merged.extend(left[i:])\n"
            f"    merged.extend(right[j:])\n"
            f"    return merged\n")
    tests = (f"def run_tests():\n"
             f"    src = [{a}]\n"
             f"    out = {f}(src)\n"
             f"    assert out == sorted(src)\n"
             f"    assert src == [{a}]  # input must not be mutated\n"
             f"    assert {f}([]) == []\n"
             f"    assert {f}([2, 2, 2]) == [2, 2, 2]\n"
             f"    assert {f}([-1, -3, -2]) == [-3, -2, -1]\n")
    cli = {"main.py": body + "\n\ndef main():\n    data = sys.stdin.read().split()\n"
           f"    n = int(data[0])\n    arr = [int(x) for x in data[1:1 + n]]\n"
           f"    print(' '.join(map(str, {f}(arr))))\n\n\nimport sys\n\nmain()\n"}

    def bug_ext(files):
        return {k: t.replace("    merged.extend(left[i:])", "    merged.extend(left[i + 1:])")
                for k, t in files.items()}

    def bug_cmp(files):
        return {k: t.replace("if left[i] <= right[j]:", "if left[i] - 1 <= right[j]:")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"drop_tail_run": bug_ext, "shifted_merge": bug_cmp},
                    notes={"purpose": "Sort a list in O(n log n) with a stable divide-and-conquer algorithm.",
                           "approach": "Split in half, recursively sort both halves, then merge two sorted runs with two pointers.",
                           "key_points": ["stability comes from taking from `left` on ties (<=)",
                                          "recursion depth is O(log n); each level does O(n) merge work",
                                          "input list is never mutated"],
                           "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty list", "all equal elements", "reverse sorted",
                                          "single element"]})


register_problem(Problem(pid="merge_sort", domain="algorithms",
                         params=_ms_params, spec=_ms_spec, io=_ms_io, solve=_ms_solve,
                         impls={"python": _py_ms}))


# ---------------------------------------------------------------- two_sum
def _ts_params(rng: random.Random):
    n = rng.randint(6, 300)
    arr = [rng.randint(-500, 500) for _ in range(n)]
    variant = rng.choice(["pair", "none"])
    if variant == "pair":
        i, j = rng.sample(range(n), 2)
        target = arr[i] + arr[j]
        # Ground truth = the FIRST pair the hash-scan reference finds.
        pair = None
        seen = {}
        for jj, x in enumerate(arr):
            need = target - x
            if need in seen:
                pair = (seen[need], jj)
                break
            if x not in seen:
                seen[x] = jj
        if pair is None:
            variant, pair = "none", None
    else:
        target = -3000 - rng.randint(0, 500)  # below any possible sum of two
        pair = None
    return {"n": n, "arr": arr, "target": target, "pair": pair, "variant": variant}


def _ts_spec(P, rng):
    f = _pick(rng, "fn_pair")
    if P["variant"] == "pair":
        outcome = (f"A valid pair exists (e.g. indices {P['pair'][0]} and {P['pair'][1]}). "
                   "Any single valid pair with i < j is acceptable, but the reference solution "
                   "returns the first pair found by a left-to-right scan with a hash map.")
    else:
        outcome = "No pair sums to the target; the function must return -1."
    return (f"Implement `{f}(values, target)` that finds two distinct indices i < j such that "
            f"values[i] + values[j] == target and returns them as a tuple (i, j); return -1 when "
            f"no such pair exists. The list holds {P['n']} integers. {outcome}")


def _ts_solve(P):
    if P["pair"] is None:
        return "-1"
    return f"{P['pair'][0]} {P['pair'][1]}"


def _ts_io(P):
    stdin = f"{P['n']} {P['target']}\n" + " ".join(map(str, P["arr"])) + "\n"
    return [(stdin, _ts_solve(P))]


def _py_ts(P, rng: random.Random) -> CodeUnit:
    v = _pick(rng, "seq")
    f = _pick(rng, "fn_pair")
    a = ", ".join(map(str, P["arr"]))
    body = (f"def {f}({v}, target):\n"
            f"    \"\"\"Return (i, j) with i < j and {v}[i] + {v}[j] == target, else -1.\"\"\"\n"
            f"    seen = {{}}  # value -> earliest index\n"
            f"    for j, x in enumerate({v}):\n"
            f"        need = target - x\n"
            f"        if need in seen:\n"
            f"            return (seen[need], j)\n"
            f"        if x not in seen:\n"
            f"            seen[x] = j\n"
            f"    return -1\n")
    tests = (f"def run_tests():\n"
             f"    assert {f}([{a}], {P['target']}) == {P['pair'] if P['pair'] else -1}\n"
             f"    assert {f}([5, 5], 10) == (0, 1)\n"
             f"    assert {f}([1, 2, 3], 100) == -1\n"
             f"    assert {f}([4], 8) == -1  # cannot reuse the same element twice\n")
    cli = {"main.py": body + "\n\ndef main():\n    data = sys.stdin.read().split()\n"
           "    n, target = int(data[0]), int(data[1])\n"
           "    arr = [int(x) for x in data[2:2 + n]]\n"
           f"    ans = {f}(arr, target)\n"
           "    print('-1' if ans == -1 else f'{ans[0]} {ans[1]}')\n\n\nmain()\n"}

    def bug_reuse(files):
        return {k: t.replace("        if x not in seen:\n            seen[x] = j\n",
                             "        seen[x] = j\n") for k, t in files.items()}

    def bug_pair_order(files):
        return {k: t.replace("return (seen[need], j)", "return (j, seen[need])")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"overwrite_seen": bug_reuse, "reversed_indices": bug_pair_order},
                    notes={"purpose": "Find the first pair of indices whose values sum to target in O(n).",
                           "approach": "Single pass with a hash map from value to its earliest index; check complement before inserting.",
                           "key_points": ["checking `need` before inserting keeps indices strictly increasing",
                                          "guard `x not in seen` preserves the earliest index for duplicates",
                                          "returns -1 when no pair exists"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["no pair", "duplicate values", "pair with equal values",
                                          "single element list"]})


register_problem(Problem(pid="two_sum", domain="algorithms",
                         params=_ts_params, spec=_ts_spec, io=_ts_io, solve=_ts_solve,
                         impls={"python": _py_ts}))


# ---------------------------------------------------------------- valid_parentheses
def _vp_params(rng: random.Random):
    n = rng.randint(0, 120)
    pairs = {"(": ")", "[": "]", "{": "}"}
    opens, closes = list(pairs), list(pairs.values())
    stack, s = [], []
    balanced = rng.random() < 0.5
    for _ in range(n):
        if stack and (rng.random() < 0.45 or not balanced):
            s.append(pairs[stack.pop()])
        else:
            c = rng.choice(opens)
            stack.append(c)
            s.append(c)
    while stack and balanced:
        s.append(pairs[stack.pop()])
    if not balanced and stack:
        pass  # intentionally unbalanced (unclosed opens)
    elif not balanced:
        s.append(rng.choice(closes))  # extra closer
    return {"s": "".join(s), "balanced": not stack and balanced or (balanced and not stack)}


def _vp_spec(P, rng):
    f = _pick(rng, "fn_paren")
    return (f"Implement `{f}(s)` that decides whether the string s (length {len(P['s'])}, built from "
            f"the brackets ( ) [ ] {{ }}) is balanced: every opening bracket must be closed by the "
            f"same type in correct LIFO order. Return True or False. An empty string is balanced.")


def _vp_solve(P):
    return "true" if _vp_reference(P["s"]) else "false"


def _vp_reference(s: str) -> bool:
    match = {")": "(", "]": "[", "}": "{"}
    st = []
    for ch in s:
        if ch in "([{":
            st.append(ch)
        elif ch in match:
            if not st or st.pop() != match[ch]:
                return False
    return not st


def _vp_io(P):
    return [(P["s"] + "\n", _vp_solve(P))]


def _py_vp(P, rng: random.Random) -> CodeUnit:
    f = _pick(rng, "fn_paren")
    body = (f"MATCH = {{')': '(', ']': '[', '}}': '{{'}}\n\n\n"
            f"def {f}(s):\n"
            f"    \"\"\"True when brackets in s nest correctly (LIFO order).\"\"\"\n"
            f"    stack = []\n"
            f"    for ch in s:\n"
            f"        if ch in '([{{':\n"
            f"            stack.append(ch)\n"
            f"        elif ch in MATCH:\n"
            f"            if not stack or stack.pop() != MATCH[ch]:\n"
            f"                return False\n"
            f"    return not stack\n")
    s = P["s"]
    esc = s.replace("'", "\\'")
    tests = (f"def run_tests():\n"
             f"    assert {f}('{esc}') is {P['balanced']}\n"
             f"    assert {f}('') is True\n"
             f"    assert {f}(')') is False\n"
             f"    assert {f}('([)]') is False\n"
             f"    assert {f}('{{[()]}}') is True\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n    line = sys.stdin.readline().rstrip('\\n')\n"
           f"    print('true' if {f}(line) else 'false')\n\n\nmain()\n"}

    def bug_map(files):
        return {k: t.replace("']': '[', '}", "']': '(', '}") for k, t in files.items()}

    def bug_final(files):
        return {k: t.replace("    return not stack", "    return True") for k, t in files.items()}

    def bug_guard(files):
        return {k: t.replace("if not stack or stack.pop() != MATCH[ch]:", "if stack.pop() != MATCH[ch]:")
                for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"wrong_match_table": bug_map, "skip_empty_check": bug_final,
                          "unchecked_pop": bug_guard},
                    notes={"purpose": "Validate bracket nesting with a LIFO stack.",
                           "approach": "Push openers; on a closer, the stack top must be its matching opener; string is balanced iff the stack ends empty.",
                           "key_points": ["the empty-stack guard prevents popping from an empty list",
                                          "final `not stack` catches unclosed openers",
                                          "works for any of the three bracket types interleaved"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty string", "lone closer", "interleaved types",
                                          "unclosed openers"]})


register_problem(Problem(pid="valid_parentheses", domain="algorithms",
                         params=_vp_params, spec=_vp_spec, io=_vp_io, solve=_vp_solve,
                         impls={"python": _py_vp}))


# ---------------------------------------------------------------- fibonacci
def _fib_params(rng: random.Random):
    return {"n": rng.randint(5, 90)}


def _fib_spec(P, rng):
    return (f"Implement `fibonacci(n)` that returns the n-th Fibonacci number with "
            f"fibonacci(0) == 0 and fibonacci(1) == 1. It must handle n up to {P['n']} "
            f"efficiently (no exponential blow-up) using arbitrary-precision integers.")


def _fib_solve(P):
    a, b = 0, 1
    for _ in range(P["n"]):
        a, b = b, a + b
    return str(a)


def _fib_io(P):
    return [(f"{P['n']}\n", _fib_solve(P))]


def _py_fib(P, rng: random.Random) -> CodeUnit:
    f = _pick(rng, "fn_fib")
    body = (f"def {f}(n):\n"
            f"    \"\"\"Return the n-th Fibonacci number (fibonacci(0) == 0), iterative.\"\"\"\n"
            f"    if n < 0:\n"
            f"        raise ValueError('n must be non-negative')\n"
            f"    a, b = 0, 1\n"
            f"    for _ in range(n):\n"
            f"        a, b = b, a + b\n"
            f"    return a\n")
    tests = (f"def run_tests():\n"
             f"    assert {f}(0) == 0\n"
             f"    assert {f}(1) == 1\n"
             f"    assert {f}({P['n']}) == {int(_fib_solve(P))}\n"
             f"    assert {f}(10) == 55\n"
             f"    try:\n"
             f"        {f}(-1)\n"
             f"        assert False, 'expected ValueError'\n"
             f"    except ValueError:\n"
             f"        pass\n")
    cli = {"main.py": body + "\n\ndef main():\n    import sys\n    n = int(sys.stdin.readline())\n"
           f"    print({f}(n))\n\n\nmain()\n"}

    def bug_shift(files):
        return {k: t.replace("a, b = b, a + b", "a, b = b, b") for k, t in files.items()}

    def bug_base(files):
        return {k: t.replace("if n < 0:", "if n <= 0:") for k, t in files.items()}

    return CodeUnit(files={"solution.py": body}, tests=tests, cli=cli, function_name=f,
                    bugs={"stalled_shift": bug_shift, "dropped_base_case": bug_base},
                    notes={"purpose": "Compute Fibonacci numbers in linear time without recursion.",
                           "approach": "Keep the last two values (a, b) and slide the pair forward n times.",
                           "key_points": ["iterative: O(n) time, O(1) space, no recursion limit issues",
                                          "Python ints are arbitrary precision so no overflow",
                                          "negative input is rejected with ValueError"],
                           "big_o_time": "O(n)", "big_o_space": "O(1)",
                           "edge_cases": ["n = 0", "n = 1", "large n", "negative n raises"]})


register_problem(Problem(pid="fibonacci", domain="algorithms",
                         params=_fib_params, spec=_fib_spec, io=_fib_io, solve=_fib_solve,
                         impls={"python": _py_fib}))
