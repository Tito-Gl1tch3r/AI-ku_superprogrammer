"""Superprogrammer extension: verification-grade engineering skills.

py_property_testing: think in INVARIANTS - write a property that exactly
characterizes a function (accepts every valid output, kills every planted
mutant deterministically) and implement delta-debugging shrinkage.

py_numeric_robustness: where naive arithmetic dies - Kahan compensated
summation against 1e16-scale cancellation, largest-remainder cent splitting
with zero loss, Welford single-pass variance against catastrophic
cancellation.

Every candidate is verified by real execution; pinned expectations are
computed with independent reference code (Fraction exact arithmetic,
statistics module) at generation time.
"""
from __future__ import annotations

import random
from fractions import Fraction

from ..core import Candidate, Family, register


# --------------------------------------------------------------------------
# py_property_testing
# --------------------------------------------------------------------------

_DEDUPE_TASK_TARGET = '''def dedupe_stable(items):
    """Keep first occurrences, preserving order."""
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out'''

_DEDUPE_INVARIANT_GOOD = '''def invariant(items, result):
    """`result` is a correct dedupe of `items` iff it has no duplicates,
    covers exactly the same set as `items`, and is ordered by the FIRST
    occurrence index of each element. Order facts make this EXACT."""
    if len(set(result)) != len(result):
        return False
    if set(result) != set(items):
        return False
    first = {}
    for index, item in enumerate(items):
        if item not in first:
            first[item] = index
    return result == sorted(result, key=lambda x: first[x])
'''

_INVARIANT_TESTS = '''def run_tests():
    cases = [[], ["a"], ["a", "a", "a"], ["b", "a", "b", "a", "c"],
             ["x", "y", "z", "y", "x"], [1, 2, 2, 1, 3, 3, 3],
             ["b", "a"], ["m", "n", "m"]]
    import random as _r
    _r.seed(20260501)
    for _ in range(12):
        cases.append([_r.choice("abcd") for _ in range(_r.randint(0, 9))])

    def ref(items):
        return [x for i, x in enumerate(items) if x not in items[:i]]

    def mutant_sorted(items):
        return sorted(set(items))

    def mutant_last_order(items):
        return list(reversed(ref(list(reversed(items)))))

    def mutant_phantom(items):
        if not items:
            return []
        return ref(items) + ["zz"]

    def mutant_dup_first(items):
        if not items:
            return []
        return [items[0]] + ref(items)

    mutants = [mutant_sorted, mutant_last_order, mutant_phantom,
               mutant_dup_first]
    killed = set()
    for items in cases:
        assert invariant(items, ref(items)), (
            "property must accept the valid output for " + repr(items))
        for mi, mutant in enumerate(mutants):
            bad = mutant(items)
            if not invariant(items, bad):
                killed.add(mi)
    missing = sorted(set(range(len(mutants))) - killed)
    assert not missing, "mutants survived the property: " + str(missing)
    print("gates-ok")
'''

_SHRINK_GOOD = '''def shrink(case, fails):
    """Delta-debug: shrink `case` while `fails(case)` stays True.

    Sweep with a chunk granularity that halves after each full sweep;
    after every successful reduction, restart from full granularity.
    The result still fails, and removing any single element from it
    makes fails() return False.
    """
    current = list(case)
    if not fails(current):
        raise ValueError("the initial case does not fail")
    granularity = len(current)
    while granularity >= 1:
        offset = 0
        while offset < len(current):
            candidate = current[:offset] + current[offset + granularity:]
            if candidate and fails(candidate):
                current = candidate
            else:
                offset += granularity
        if granularity == 1:
            break
        granularity //= 2
    return current
'''

_SHRINK_TESTS = '''def run_tests():
    import random as _r
    _r.seed(20260502)
    big = [_r.randrange(0, 50) for _ in range(40)]
    big.extend([7, 13])
    out = shrink(big, lambda c: 7 in c and 13 in c)
    assert sorted(out) == [7, 13], out
    out2 = shrink(list(range(30)), lambda c: len(c) >= 4)
    assert len(out2) == 4, out2
    assert all(len(out2[:i] + out2[i + 1:]) < 4 for i in range(len(out2)))
    out3 = shrink([5] * 20, lambda c: 5 in c)
    assert out3 == [5], out3
    try:
        shrink([1, 2], lambda c: False)
    except ValueError:
        pass
    else:
        raise AssertionError("non-failing case must raise")
    print("gates-ok")
'''


class PropertyTestingFamily(Family):
    NAME = "py_property_testing"
    LANGUAGE = "python"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("testing", "explanation", "debugging")

    def _mk_invariant(self, rng: random.Random) -> Candidate:
        task = (
            "Test-first thinking: given the reference function "
            "dedupe_stable(items) shown below, write a single property "
            "invariant(items, result) -> bool that EXACTLY characterizes a "
            "correct dedupe. It must accept every valid output AND reject "
            "every plausible broken variant: sorted-set output, "
            "last-occurrence order, phantom extra elements, and duplicated "
            "first element. Use only directly checkable facts (result has "
            "no duplicates, set(result) == set(items), and result is "
            "ordered by the FIRST occurrence index of each element in "
            "items) - do NOT reimplement the dedupe algorithm and compare "
            "against it.\n\nReference function:\n```python\n"
            f"{_DEDUPE_TASK_TARGET}\n```"
        )
        return Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced",
            task=task,
            expected_behavior=("accepts every correct dedupe output and "
                               "kills all four planted mutants on the "
                               "seeded case battery"),
            code=_DEDUPE_INVARIANT_GOOD, tests=_INVARIANT_TESTS,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Write an exact-checkable property for dedupe",
                "approach": "uniqueness + set equality + subsequence scan",
                "key_points": ["a property must accept valid AND reject invalid",
                               "tautologies survive mutants, so they are useless",
                               "subsequence scan avoids reimplementing the algorithm",
                               "the battery covers empty, single and heavy-dup inputs"],
                "big_o_time": "O(len(items) + len(result)) per call",
                "big_o_space": "O(len(items))",
                "edge_cases": ["empty items -> empty result accepted",
                               "phantom element breaks set equality",
                               "duplicated element breaks uniqueness"]}},
            tags=["testing", "properties", "mutants"],
            variant="invariant", seed=rng.randrange(2**31))

    def _mk_shrink(self, rng: random.Random) -> Candidate:
        task = (
            "Implement delta-debugging shrinkage: shrink(case, fails) takes "
            "a list of integers and a predicate fails(case) -> bool (True "
            "means the case still reproduces the failure). Return a minimal "
            "still-failing case: it must itself fail, and removing ANY "
            "single element from it must make fails() return False. Use the "
            "classic ddmin loop - try removing chunks at a granularity that "
            "halves after each full sweep, and restart each sweep at the "
            "current granularity. Raise ValueError if the initial case does "
            "not fail at all."
        )
        return Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced",
            task=task,
            expected_behavior=("the shrunk case still fails and every "
                               "single-element removal passes"),
            code=_SHRINK_GOOD, tests=_SHRINK_TESTS,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Minimize failing inputs automatically (ddmin)",
                "approach": "chunk removal sweeps with halving granularity",
                "key_points": ["the result must still fail",
                               "minimality: every element is necessary",
                               "chunk removal keeps order (subsequence)",
                               "granularity 1 ends the search"],
                "big_o_time": "O(n^2) predicate calls in the worst case",
                "big_o_space": "O(n)",
                "edge_cases": ["initial case does not fail -> ValueError",
                               "single-element minimal cases"]}},
            tags=["testing", "shrinking", "ddmin"],
            variant="shrink", seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("invariant_design", "shrink_minimal"))
        if kind == "invariant_design":
            return self._mk_invariant(rng)
        return self._mk_shrink(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(("invariant_design", "shrink_minimal"))
        if kind == "invariant_design":
            good = self._mk_invariant(random.Random(rng.randrange(2**31)))
            buggy = ("def invariant(items, result):\n"
                     "    return set(result) == set(items)\n")
            bug_kind = "tautological_property"
        else:
            good = self._mk_shrink(random.Random(rng.randrange(2**31)))
            buggy = good.code.replace(
                "        granularity //= 2", "        break")
            bug_kind = "no_termination_guard"
            if buggy == good.code:
                return None
        cand = Candidate(
            family=self.NAME, language="python", domain="algorithms",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code},
            tags=["testing", "bug"], variant=f"{kind}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


# --------------------------------------------------------------------------
# py_numeric_robustness
# --------------------------------------------------------------------------

_KAHAN_GOOD = '''def kahan_sum(values):
    """Compensated summation: recover the bits naive += throws away."""
    total = 0.0
    compensation = 0.0
    for value in values:
        y = value - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total
'''

_SPLIT_GOOD = '''def split_cents(amount: int, n: int) -> list[int]:
    """Largest-remainder split with zero loss: sum(parts) == amount.

    Deterministic: every part gets amount // n; the first
    amount % n parts (in order) get one extra cent.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if amount < 0:
        raise ValueError("amount must be non-negative")
    base = amount // n
    remainder = amount % n
    return [base + 1 if i < remainder else base for i in range(n)]
'''

_WELFORD_GOOD = '''def welford(values):
    """Single-pass mean and population variance (Welford's algorithm)."""
    count = 0
    mean = 0.0
    m2 = 0.0
    for value in values:
        count += 1
        delta = value - mean
        mean += delta / count
        m2 += delta * (value - mean)
    if count == 0:
        return 0.0, 0.0
    return mean, m2 / count
'''


class NumericRobustnessFamily(Family):
    NAME = "py_numeric_robustness"
    LANGUAGE = "python"
    DOMAIN = "science_math"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "optimization", "failure_prediction")

    def _mk_kahan(self, rng: random.Random) -> Candidate:
        # pinned random all-positive battery: exact via Fraction arithmetic
        pinned = []
        for _ in range(3):
            n = rng.randint(30, 80)
            vals = [round(rng.uniform(0.0, 1e6), 4) for _ in range(n - 3)]
            vals += [1e-8, 1e-8, 1e-8]
            exact = float(sum((Fraction(v) for v in vals), Fraction(0)))
            pinned.append((vals, exact))
        pinned_repr = "".join(
            f"    _vals, _exact = {vals!r}, {exact!r}\n"
            f"    _tol = 1e-9 + 1e-12 * sum(abs(v) for v in _vals)\n"
            f"    assert abs(kahan_sum(_vals) - _exact) <= _tol\n"
            for vals, exact in pinned)
        tests = (
            "def run_tests():\n"
            "    seq = [1e16] + [1.0] * 10000 + [-1e16]\n"
            "    assert abs(kahan_sum(seq) - 10000.0) < 1e-6, kahan_sum(seq)\n"
            "    naive = 0.0\n"
            "    for v in seq:\n"
            "        naive += v\n"
            "    assert abs(naive - 10000.0) > 9000.0, (\n"
            "        'battery lost its discrimination power')\n"
            f"{pinned_repr}"
            "    assert kahan_sum([]) == 0.0\n"
            "    assert kahan_sum([2.5]) == 2.5\n"
            "    print('gates-ok')\n"
        )
        task = (
            "Floating-point addition is not associative: summing "
            "[1e16, 1.0, 1.0, ..., -1e16] with naive += loses every 1.0 to "
            "round-off (the running total never changes). Implement "
            "kahan_sum(values) in Python using Kahan compensated summation: "
            "keep a running compensation equal to the round-off error of "
            "each addition (compensation = (t - total) - y with y = value - "
            "compensation) so the lost low-order bits are reinjected. The "
            "classic battery must return 10000.0 (naive sum returns 0.0), "
            "and several all-positive mixed-magnitude batteries must match "
            "the exact Fraction-arithmetic result within a tight tolerance."
        )
        return Candidate(
            family=self.NAME, language="python", domain="science_math",
            difficulty="advanced",
            task=task,
            expected_behavior="kahan_sum([1e16] + [1.0]*10000 + [-1e16]) "
                              "== 10000.0; pinned mixed-magnitude batteries "
                              "match exact arithmetic",
            code=_KAHAN_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Compensated summation against catastrophic loss",
                "approach": "Kahan: track round-off per addition, reinject it",
                "key_points": ["naive += on 1e16 + 1.0 is a no-op in float64",
                               "compensation = (t - total) - y is the exact error",
                               "Fraction arithmetic provides the exact ground truth",
                               "empty input returns 0.0"],
                "big_o_time": "O(n) with 4 float ops per element",
                "big_o_space": "O(1)",
                "edge_cases": ["empty list", "single element",
                               "cancellation battery ends at exactly 10000.0"]}},
            tags=["numerics", "float", "kahan"],
            variant=f"kahan|{rng.randrange(2**20)}", seed=rng.randrange(2**31))

    def _mk_split(self, rng: random.Random) -> Candidate:
        amount = rng.randrange(1, 1_000_000)
        n = rng.randint(3, 9)
        while amount % n == 0:
            amount = rng.randrange(1, 1_000_000)
        parts = [amount // n + (1 if i < amount % n else 0) for i in range(n)]
        other_a, other_n = rng.randrange(1, 999), rng.randint(2, 7)
        while other_a % other_n == 0:
            other_a = rng.randrange(1, 999)
        other_parts = [other_a // other_n + (1 if i < other_a % other_n else 0)
                       for i in range(other_n)]
        tests = (
            f"def run_tests():\n"
            f"    assert split_cents({amount}, {n}) == {parts!r}\n"
            f"    assert split_cents({other_a}, {other_n}) == {other_parts!r}\n"
            f"    assert split_cents(100, 3) == [34, 33, 33]\n"
            f"    assert split_cents(7, 7) == [1] * 7\n"
            f"    assert split_cents(0, 4) == [0, 0, 0, 0]\n"
            f"    assert split_cents(2, 5) == [1, 1, 0, 0, 0]\n"
            f"    out = split_cents({amount}, {n})\n"
            f"    assert sum(out) == {amount}, 'zero loss required'\n"
            f"    assert max(out) - min(out) <= 1\n"
            f"    assert out == sorted(out, reverse=True)\n"
            f"    try:\n"
            f"        split_cents(10, 0)\n"
            f"    except ValueError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('n=0 must raise')\n"
            f"    print('gates-ok')\n"
        )
        task = (
            "Splitting money must never lose a cent. Implement "
            "split_cents(amount, n) in Python with the largest-remainder "
            "method over integer cents: every part starts at amount // n, "
            "and the first amount % n parts (in order) receive one extra "
            "cent. Guarantees: sum(parts) == amount exactly, max - min <= 1, "
            "the list is non-increasing (extra cents go to the earliest "
            "parts), and it raises ValueError for n <= 0 or negative amount."
        )
        return Candidate(
            family=self.NAME, language="python", domain="science_math",
            difficulty=rng.choice(["intermediate", "advanced"]),
            task=task,
            expected_behavior=f"split_cents({amount}, {n}) == {parts!r}; "
                              "zero loss, max-min <= 1, non-increasing",
            code=_SPLIT_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Lossless integer money splitting",
                "approach": "floor division + distribute the remainder by index",
                "key_points": ["floats must never touch money",
                               "sum(parts) == amount is the hard invariant",
                               "deterministic tie order: earliest parts win",
                               "n <= 0 rejected explicitly"],
                "big_o_time": "O(n)", "big_o_space": "O(n)",
                "edge_cases": ["amount < n yields zeros",
                               "amount == 0", "n == 0 raises"]}},
            tags=["numerics", "money", "determinism"],
            variant=f"split|{amount}|{n}", seed=rng.randrange(2**31))

    def _mk_welford(self, rng: random.Random) -> Candidate:
        # The discrimination battery must actually discriminate: mirror the
        # test's naive float loop here until the scenario provably separates
        # Welford from the naive formula (deterministic given the rng).
        while True:
            base = rng.choice([1e8, 5e8, 1e9])
            spread = rng.choice([0.25, 0.5])
            count = rng.choice([200, 500, 800])
            values = [base + i * spread for i in range(count)]
            import statistics as _st
            mean_ref = _st.fmean(values)
            var_ref = _st.pvariance(values)
            acc_sq = 0.0
            acc_lin = 0.0
            for v in values:
                acc_sq += v * v
                acc_lin += v
            naive_v = acc_sq / len(values) - (acc_lin / len(values)) ** 2
            if abs(naive_v - var_ref) > 1e-3 * var_ref:
                break
        small_ref = _st.pvariance([2, 4, 4, 4, 5, 5, 7, 9])
        tests = (
            f"def run_tests():\n"
            f"    import statistics as _st\n"
            f"    values = {values!r}\n"
            f"    mean, var = welford(values)\n"
            f"    assert abs(mean - {mean_ref!r}) <= 1e-6 * max(1.0, abs({mean_ref!r}))\n"
            f"    assert abs(var - {var_ref!r}) <= 1e-3 * {var_ref!r}, var\n"
            f"    acc_sq = 0.0\n"
            f"    acc_lin = 0.0\n"
            f"    for v in values:\n"
            f"        acc_sq += v * v\n"
            f"        acc_lin += v\n"
            f"    naive_v = acc_sq / len(values) - (acc_lin / len(values)) ** 2\n"
            f"    assert abs(naive_v - {var_ref!r}) > 1e-3 * {var_ref!r}, (\n"
            f"        'battery lost its discrimination power')\n"
            f"    assert abs(welford([2, 4, 4, 4, 5, 5, 7, 9])[1] - {small_ref!r}) < 1e-9\n"
            f"    assert welford([]) == (0.0, 0.0)\n"
            f"    print('gates-ok')\n"
        )
        task = (
            "Computing variance as E[x^2] - mean^2 in one naive pass "
            "suffers catastrophic cancellation when the mean is huge and "
            "the spread is small: for values like 1e9 + k*0.25 the naive "
            "result can be hundreds off the true variance of ~5. Implement "
            "welford(values) in Python with Welford's single-pass algorithm: "
            "maintain count, running mean (mean += delta / count) and M2 "
            "(m2 += delta * (value - mean)), returning the tuple "
            "(mean, m2 / count) as population statistics. An empty input "
            "returns (0.0, 0.0). The result must match the two-pass "
            "statistics module within 0.1% while the naive formula on the "
            "same data must NOT."
        )
        return Candidate(
            family=self.NAME, language="python", domain="science_math",
            difficulty="advanced",
            task=task,
            expected_behavior="single-pass result matches two-pass statistics "
                              "within 0.1% on the 1e9-scale battery",
            code=_WELFORD_GOOD, tests=tests, verify_method="executed",
            notes={"explain": {
                "purpose": "Single-pass variance without cancellation",
                "approach": "Welford: update mean and M2 incrementally",
                "key_points": ["E[x^2] - mean^2 subtracts two huge numbers",
                               "delta * (value - mean) uses the UPDATED mean",
                               "population variance divides by count",
                               "empty input is defined, not an error"],
                "big_o_time": "O(n) single pass", "big_o_space": "O(1)",
                "edge_cases": ["empty input", "single value -> variance 0",
                               "1e9-scale data with 0.25 spread"]}},
            tags=["numerics", "statistics", "welford"],
            variant=f"welford|{base}|{spread}", seed=rng.randrange(2**31))

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("kahan_sum", "split_cents", "welford_variance"))
        if kind == "kahan_sum":
            return self._mk_kahan(rng)
        if kind == "split_cents":
            return self._mk_split(rng)
        return self._mk_welford(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(("kahan_sum", "split_cents", "welford_variance"))
        if kind == "kahan_sum":
            good = self._mk_kahan(random.Random(rng.randrange(2**31)))
            buggy = ("def kahan_sum(values):\n"
                     "    total = 0.0\n"
                     "    for value in values:\n"
                     "        total += value\n"
                     "    return total\n")
            bug_kind = "naive_summation"
        elif kind == "split_cents":
            good = self._mk_split(random.Random(rng.randrange(2**31)))
            buggy = good.code.replace(
                "    return [base + 1 if i < remainder else base for i in range(n)]",
                "    return [base for _ in range(n)]")
            bug_kind = "floor_only_loss"
            if buggy == good.code:
                return None
        else:
            good = self._mk_welford(random.Random(rng.randrange(2**31)))
            buggy = ("def welford(values):\n"
                     "    if not values:\n"
                     "        return 0.0, 0.0\n"
                     "    n = len(values)\n"
                     "    acc = 0.0\n"
                     "    acc2 = 0.0\n"
                     "    for v in values:\n"
                     "        acc += v\n"
                     "        acc2 += v * v\n"
                     "    mean = acc / n\n"
                     "    var = acc2 / n - mean * mean\n"
                     "    return mean, var\n")
            bug_kind = "catastrophic_cancellation"
        cand = Candidate(
            family=self.NAME, language="python", domain="science_math",
            difficulty="advanced", task=good.task,
            expected_behavior="See question.", code=buggy, tests=good.tests,
            verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code},
            tags=["numerics", "bug"], variant=f"{kind}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), PropertyTestingFamily)
register(globals(), NumericRobustnessFamily)
