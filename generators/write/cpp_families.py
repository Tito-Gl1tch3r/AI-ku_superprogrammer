"""Dataset-1 write families for C++ (g++-verified)."""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register
from ..problems.bank_py_a import _bs_params, _ts_params
from ..problems.bank_py_b import _sp_params, _sp_solve


class CppBankFamily(Family):
    NAME = "cpp_bank_wrappers"
    LANGUAGE = "cpp"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "complexity", "translation",
                "optimization")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["binary_search", "two_sum", "sieve_primes"])
        if kind == "binary_search":
            P = _bs_params(rng)
            f = rng.choice(["binarySearch", "findSorted", "indexOfSorted"])
            a = ", ".join(map(str, P["arr"]))
            code = (
                f"#include <vector>\n\n"
                f"int {f}(const std::vector<int>& values, int target) {{\n"
                f"    int lo = 0, hi = static_cast<int>(values.size()) - 1;\n"
                f"    while (lo <= hi) {{\n"
                f"        int mid = lo + (hi - lo) / 2;\n"
                f"        if (values[mid] == target) return mid;\n"
                f"        if (values[mid] < target) lo = mid + 1;\n"
                f"        else hi = mid - 1;\n"
                f"    }}\n"
                f"    return -1;\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <vector>\n"
                f"int {f}(const std::vector<int>&, int);\n\n"
                f"int main() {{\n"
                f"    std::vector<int> v1 = {{{a}}};\n"
                f"    assert({f}(v1, {P['target']}) == {P['idx']});\n"
                f"    assert({f}({{}}, 7) == -1);\n"
                f"    std::vector<int> v2 = {{4}};\n"
                f"    assert({f}(v2, 4) == 0);\n"
                f"    std::vector<int> v3 = {{1, 3, 5}};\n"
                f"    assert({f}(v3, 4) == -1);\n"
                f"    assert({f}(v3, 5) == 2);\n"
                f"    return 0;\n}}\n")
            expected = f"Returns {P['idx']} for target {P['target']}, -1 when absent."
            explain = {"purpose": "Inclusive-window binary search over std::vector.",
                       "approach": "lo/hi inclusive; mid avoids overflow; halve each step.",
                       "key_points": ["static_cast for signed size math",
                                      "empty vector -> hi = -1 -> loop skipped",
                                      "-1 encodes absence"],
                       "big_o_time": "O(log n)", "big_o_space": "O(1)",
                       "edge_cases": ["empty vector", "single element", "out-of-range target"]}
            def bug_flip(files):
                return {k: t.replace("if (values[mid] < target)",
                                     "if (values[mid] <= target)") for k, t in files.items()}
            bugs = {"comparison_flip": bug_flip}
        elif kind == "two_sum":
            P = _ts_params(rng)
            f = rng.choice(["twoSum", "findPair", "pairWithSum"])
            a = ", ".join(map(str, P["arr"]))
            pair = P["pair"]
            pair_cpp = "std::make_pair(-1, -1)" if pair is None else \
                f"std::make_pair({pair[0]}, {pair[1]})"
            code = (
                f"#include <unordered_map>\n#include <utility>\n#include <vector>\n\n"
                f"std::pair<int, int> {f}(const std::vector<int>& values, int target) {{\n"
                f"    std::unordered_map<int, int> seen;\n"
                f"    for (int j = 0; j < static_cast<int>(values.size()); ++j) {{\n"
                f"        int need = target - values[j];\n"
                f"        auto it = seen.find(need);\n"
                f"        if (it != seen.end()) return {{it->second, j}};\n"
                f"        if (!seen.count(values[j])) seen[values[j]] = j;\n"
                f"    }}\n"
                f"    return {{-1, -1}};\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <utility>\n#include <vector>\n"
                f"std::pair<int, int> {f}(const std::vector<int>&, int);\n\n"
                f"int main() {{\n"
                f"    std::vector<int> v = {{{a}}};\n"
                f"    assert({f}(v, {P['target']}) == {pair_cpp});\n"
                f"    std::vector<int> d = {{5, 5}};\n"
                f"    assert({f}(d, 10) == std::make_pair(0, 1));\n"
                f"    std::vector<int> q = {{1, 2, 3}};\n"
                f"    assert({f}(q, 100) == std::make_pair(-1, -1));\n"
                f"    return 0;\n}}\n")
            expected = ("First complement hit in an unordered_map; {-1, -1} encodes absence.")
            explain = {"purpose": "O(n) average pair lookup.",
                       "approach": "Check complement before inserting the current value.",
                       "key_points": ["count() guard keeps earliest duplicate index",
                                      "returned indices strictly increase",
                                      "pair return type documents the contract"],
                       "big_o_time": "O(n) average", "big_o_space": "O(n)",
                       "edge_cases": ["no pair", "duplicates", "equal-value pair"]}
            def bug_reuse(files):
                return {k: t.replace("if (!seen.count(", "if (true || !seen.count(")
                        for k, t in files.items()}
            bugs = {"always_overwrite_seen": bug_reuse}
        else:
            P = _sp_params(rng)
            f = rng.choice(["sievePrimes", "primesUpTo"])
            expected_list = _sp_solve(P)
            code = (
                f"#include <vector>\n\n"
                f"std::vector<int> {f}(int n) {{\n"
                f"    std::vector<int> primes;\n"
                f"    if (n < 2) return primes;\n"
                f"    std::vector<char> composite(static_cast<size_t>(n) + 1, 0);\n"
                f"    for (int i = 2; static_cast<long long>(i) * i <= n; ++i)\n"
                f"        if (!composite[i])\n"
                f"            for (long long j = static_cast<long long>(i) * i; j <= n; j += i)\n"
                f"                composite[j] = 1;\n"
                f"    for (int x = 2; x <= n; ++x)\n"
                f"        if (!composite[x]) primes.push_back(x);\n"
                f"    return primes;\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <vector>\n"
                f"std::vector<int> {f}(int);\n\n"
                f"int main() {{\n"
                f"    std::vector<int> want = {{{expected_list.replace(' ', ', ')}}};\n"
                f"    assert({f}({P['n']}) == want);\n"
                f"    assert({f}(1).empty());\n"
                f"    std::vector<int> ten = {{2, 3, 5, 7}};\n"
                f"    assert({f}(10) == ten);\n"
                f"    return 0;\n}}\n")
            expected = f"{len(expected_list.split())} primes <= {P['n']} in ascending order."
            explain = {"purpose": "Sieve with vector<char> flags.",
                       "approach": "Cross multiples from i*i; collect survivors ascending.",
                       "key_points": ["long long widening before i*i",
                                      "vector<char> is cache friendly",
                                      "n < 2 returns empty"],
                       "big_o_time": "O(n log log n)", "big_o_space": "O(n)",
                       "edge_cases": ["n < 2", "prime squares", "ascending output"]}
            def bug_start(files):
                return {k: t.replace("for (long long j = static_cast<long long>(i) * i; j <= n; j += i)",
                                     "for (long long j = static_cast<long long>(i); j <= n; j += i)")
                        for k, t in files.items()}
            bugs = {"marks_itself_composite": bug_start}
        cand = Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the C++17 function in solution.cpp: {expected} The harness.cpp "
                  f"asserts the contract (it is the only file with main). Standard library only; "
                  f"the solution must compile with -Wall -Wextra."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="compiled_and_executed",
            notes={"explain": explain, "kind": kind},
            tags=["cpp", kind], variant=kind, seed=rng.randrange(2**31))
        cand.notes["_bug_fns"] = bugs
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.cpp": cand.code})
        if buggy["solution.cpp"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="cpp", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.cpp"], tests=cand.tests,
                          verify_method="compiled_and_executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})


class CppStlFamily(Family):
    NAME = "cpp_stl_containers"
    LANGUAGE = "cpp"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "code_review", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["sort_comparator", "unique_erase", "set_ops"])
        if kind == "sort_comparator":
            f = rng.choice(["sortByLengthThenValue", "customOrder"])
            words = rng.sample(["fig", "date", "apple", "kiwi", "plum", "banana"],
                               rng.randint(3, 5))
            expected_order = sorted(words, key=lambda w: (len(w), w))
            lit = ", ".join(f'"{w}"' for w in words)
            exp_lit = ", ".join(f'"{w}"' for w in expected_order)
            code = (
                f"#include <algorithm>\n#include <string>\n#include <vector>\n\n"
                f"std::vector<std::string> {f}(std::vector<std::string> words) {{\n"
                f"    std::sort(words.begin(), words.end(),\n"
                f"              [](const std::string& a, const std::string& b) {{\n"
                f"                  if (a.size() != b.size()) return a.size() < b.size();\n"
                f"                  return a < b;\n"
                f"              }});\n"
                f"    return words;\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <string>\n#include <vector>\n"
                f"std::vector<std::string> {f}(std::vector<std::string>);\n\n"
                f"int main() {{\n"
                f"    std::vector<std::string> in = {{{lit}}};\n"
                f"    std::vector<std::string> want = {{{exp_lit}}};\n"
                f"    assert({f}(in) == want);\n"
                f"    assert({f}({{}}).empty());\n"
                f"    std::vector<std::string> one = {{\"solo\"}};\n"
                f"    assert({f}(one) == one);\n"
                f"    return 0;\n}}\n")
            expected = f"Ascending by length, ties alphabetical: {expected_order}."
            explain = {"purpose": "Two-key custom comparator with std::sort.",
                       "approach": "Lambda comparing length first, then lexicographic order.",
                       "key_points": ["strict weak ordering: primary then secondary key",
                                      "pass-by-value keeps the caller's vector intact",
                                      "stable result for equal keys"],
                       "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                       "edge_cases": ["empty input", "equal lengths", "single element"]}
            def bug(files):
                return {"solution.cpp": files["solution.cpp"].replace(
                    "return a.size() < b.size();", "return a.size() > b.size();")}
            bugs = {"reversed_primary_key": bug}
        elif kind == "unique_erase":
            vals = sorted(rng.randint(1, 9) for _ in range(rng.randint(8, 20)))
            uniq = sorted(set(vals))
            f = rng.choice(["dedupeSorted", "compactUnique"])
            code = (
                f"#include <algorithm>\n#include <vector>\n\n"
                f"std::vector<int> {f}(std::vector<int> values) {{\n"
                f"    std::sort(values.begin(), values.end());\n"
                f"    values.erase(std::unique(values.begin(), values.end()), values.end());\n"
                f"    return values;\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <vector>\n"
                f"std::vector<int> {f}(std::vector<int>);\n\n"
                f"int main() {{\n"
                f"    std::vector<int> in = {{{', '.join(map(str, vals))}}};\n"
                f"    std::vector<int> want = {{{', '.join(map(str, uniq))}}};\n"
                f"    assert({f}(in) == want);\n"
                f"    assert({f}({{}}).empty());\n"
                f"    std::vector<int> same = {{7, 7, 7}};\n"
                f"    std::vector<int> sw = {{7}};\n"
                f"    assert({f}(same) == sw);\n"
                f"    return 0;\n}}\n")
            expected = f"{len(vals)} entries collapse to {len(uniq)} unique sorted values."
            explain = {"purpose": "The erase-remove (erase-unique) idiom.",
                       "approach": "sort -> unique shifts duplicates left -> erase truncates.",
                       "key_points": ["unique only removes adjacent duplicates",
                                      "erase takes the new logical end",
                                      "size shrinks, capacity may not"],
                       "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                       "edge_cases": ["all equal", "already unique", "empty vector"]}
            def bug(files):
                return {"solution.cpp": files["solution.cpp"].replace(
                    "values.erase(std::unique(values.begin(), values.end()), values.end());",
                    "std::unique(values.begin(), values.end());")}
            bugs = {"unique_without_erase": bug}
        else:  # set_ops
            a_vals = sorted(rng.sample(range(1, 40), rng.randint(4, 8)))
            b_vals = sorted(rng.sample(range(1, 40), rng.randint(4, 8)))
            inter = sorted(set(a_vals) & set(b_vals))
            uni = sorted(set(a_vals) | set(b_vals))
            f = rng.choice(["setIntersection", "commonElements"])
            code = (
                f"#include <algorithm>\n#include <set>\n#include <vector>\n\n"
                f"std::vector<int> {f}(const std::set<int>& a, const std::set<int>& b) {{\n"
                f"    std::vector<int> out;\n"
                f"    std::set_intersection(a.begin(), a.end(), b.begin(), b.end(),\n"
                f"                          std::back_inserter(out));\n"
                f"    return out;\n"
                f"}}\n")
            tests = (
                f"#include <cassert>\n#include <set>\n#include <vector>\n"
                f"std::vector<int> {f}(const std::set<int>&, const std::set<int>&);\n\n"
                f"int main() {{\n"
                f"    std::set<int> a = {{{', '.join(map(str, a_vals))}}};\n"
                f"    std::set<int> b = {{{', '.join(map(str, b_vals))}}};\n"
                f"    std::vector<int> want = {{{', '.join(map(str, inter))}}};\n"
                f"    assert({f}(a, b) == want);\n"
                f"    std::vector<int> uni = {{{', '.join(map(str, uni))}}};\n"
                f"    assert(a.size() + b.size() >= uni.size());\n"
                f"    return 0;\n}}\n")
            expected = f"Intersection {inter} (sorted, duplicates removed by set)."
            explain = {"purpose": "Sorted-range intersection with std::set_intersection.",
                       "approach": "Both inputs sorted; linear merge writes common elements.",
                       "key_points": ["requires sorted input ranges",
                                      "back_inserter grows the output",
                                      "sets guarantee sorted iteration"],
                       "big_o_time": "O(|a| + |b|)", "big_o_space": "O(min(|a|, |b|))",
                       "edge_cases": ["disjoint sets", "identical sets", "empty set"]}
            def bug(files):
                return {"solution.cpp": files["solution.cpp"].replace(
                    "std::set_intersection(", "std::set_union(")}
            bugs = {"intersection_as_union": bug}
        cand = Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the C++17 helper in solution.cpp: {expected} The harness.cpp asserts "
                  f"the behaviour; use the appropriate <algorithm> primitives instead of manual "
                  f"loops where the task says so."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="compiled_and_executed",
            notes={"explain": explain, "kind": kind},
            tags=["cpp", "stl", kind], variant=kind, seed=rng.randrange(2**31))
        cand.notes["_bug_fns"] = bugs
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.cpp": cand.code})
        if buggy["solution.cpp"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="cpp", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.cpp"], tests=cand.tests,
                          verify_method="compiled_and_executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})

    def review_variant(self, rng: random.Random):
        n = rng.randint(4, 9)
        vals = [rng.randint(1, 50) for _ in range(n)]
        total = sum(vals)
        code = (
            f"#include <iostream>\n#include <vector>\n\n"
            f"int main() {{\n"
            f"    std::vector<int> data;\n"
            f"    int init[] = {{{', '.join(map(str, vals))}}};\n"
            f"    for (int i = 0; i < {n}; ++i) data.push_back(init[i]);\n"
            f"    int total = 0;\n"
            f"    for (size_t i = 0; i < data.size(); ++i) {{\n"
            f"        total += data[i];\n"
            f"        std::cout << data[i] << '\\n';\n"
            f"    }}\n"
            f"    std::cout << total << '\\n';\n"
            f"    return 0;\n"
            f"}}\n")
        tests = (
            f"#include <cassert>\n\n"
            f"int main() {{\n    assert({total} > 0);\n    return 0;\n}}\n")
        cand = Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty="intermediate",
            task=("Review this C++ program (it compiles and prints each value then the "
                  f"total {total}). Flag what a senior reviewer would raise; separate bugs "
                  "from style preferences."),
            expected_behavior=f"Prints {n} values then {total}.",
            code=code, tests=tests, verify_method="compiled_and_executed",
            notes={"issues": [
                {"kind": "manual loop instead of std::accumulate",
                 "severity": "low",
                 "why": "the summation re-implements std::accumulate and mixes I/O with logic.",
                 "better": "separate printing from aggregation; use std::accumulate."},
                {"kind": "signed/unsigned mixing",
                 "severity": "medium",
                 "why": "loop uses size_t while other arithmetic uses int; mixing invites subtle wrap-around bugs when refactored.",
                 "better": "use size_t consistently or a range-for."},
                {"kind": "no reserve before push_back",
                 "severity": "low",
                 "why": "the vector grows geometrically with reallocations although the size is known.",
                 "better": "data.reserve(n) or construct with the initializer list directly."},
            ], "explain": {"purpose": "Review fixture: functional but improvable C++.",
                           "approach": "Plant idiom and hygiene findings on working code.",
                           "key_points": ["I/O and logic separation",
                                          "signed/unsigned discipline",
                                          "reserve when size is known"],
                           "big_o_time": "O(n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty vector", "negative totals"]}},
            tags=["cpp", "review"], variant="review", seed=rng.randrange(2**31))
        return cand, cand.notes["issues"]


class CppRaiiFamily(Family):
    NAME = "cpp_raii_classes"
    LANGUAGE = "cpp"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "complexity", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        f = rng.choice(["ResourceGuard", "ScopeCounter", "HandleWrapper"])
        code = (
            f"#include <memory>\n#include <utility>\n\n"
            f"static int g_live = 0;\n\n"
            f"class {f} {{\n"
            f"public:\n"
            f"    explicit {f}(int id) : id_(id) {{ ++g_live; }}\n"
            f"    ~{f}() {{ --g_live; }}\n"
            f"    {f}(const {f}&) = delete;\n"
            f"    {f}& operator=(const {f}&) = delete;\n"
            f"    {f}({f}&& other) noexcept : id_(other.id_) {{ ++g_live; }}\n"
            f"    int id() const {{ return id_; }}\n"
            f"private:\n"
            f"    int id_;\n"
            f"}};\n\n"
            f"int live_count() {{ return g_live; }}\n\n"
            f"int probe_move(int id) {{\n"
            f"    auto a = std::make_unique<{f}>(id);\n"
            f"    auto b = std::move(a);\n"
            f"    return b->id();\n"
            f"}}\n\n"
            f"void probe_scope(int id) {{\n"
            f"    {f} local(id);\n"
            f"}}\n")
        k = rng.randint(2, 4)
        tests = (
            f"#include <cassert>\n\n"
            f"int live_count();\n"
            f"int probe_move(int);\n"
            f"void probe_scope(int);\n\n"
            f"int main() {{\n"
            f"    assert(live_count() == 0);\n"
            f"    assert(probe_move({k}) == {k});\n"
            f"    assert(live_count() == 0);\n"
            f"    probe_scope(9);\n"
            f"    assert(live_count() == 0);\n"
            f"    return 0;\n}}\n")
        return Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the RAII class {f} in solution.cpp exactly as declared: constructor "
                  f"registers the instance in a global live-counter, destructor unregisters, copy "
                  f"is deleted, move is noexcept, and id() exposes the stored identifier. The "
                  f"harness.cpp verifies that a moved unique_ptr keeps the id and that the live "
                  f"count returns to 0 after scope exit."),
            expected_behavior="Live count rises on construction, survives std::move, and returns to 0 after the scope ends.",
            code=code, tests=tests, verify_method="compiled_and_executed",
            notes={"explain": {"purpose": "Ownership tracking with RAII.",
                               "approach": "Constructor/destructor maintain a global live count; move transfers responsibility.",
                               "key_points": ["deleted copies prevent double decrement",
                                              "noexcept move enables container growth",
                                              "scope exit deterministically releases"],
                               "big_o_time": "O(1) per operation", "big_o_space": "O(1)",
                               "edge_cases": ["move then use original", "scope nesting", "destructor order"]}},
            tags=["cpp", "raii"], variant="raii_guard", seed=rng.randrange(2**31))


class CppParsingFamily(Family):
    NAME = "cpp_parsing"
    LANGUAGE = "cpp"
    DOMAIN = "text_processing"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging")

    def generate(self, rng: random.Random) -> Candidate:
        f = rng.choice(["sumTokens", "parseNumbers"])
        rows = []
        for _ in range(rng.randint(3, 6)):
            n = rng.randint(2, 6)
            rows.append(", ".join(str(rng.randint(-40, 40)) for _ in range(n)))
        text = " | ".join(rows)
        expected = sum(int(x) for r in rows for x in r.split(","))
        code = (
            f"#include <sstream>\n#include <string>\n\n"
            f"long {f}(const std::string& blob) {{\n"
            f"    long total = 0;\n"
            f"    std::istringstream in(blob);\n"
            f"    std::string token;\n"
            f"    while (std::getline(in, token, '|')) {{\n"
            f"        std::istringstream cell(token);\n"
            f"        std::string value;\n"
            f"        while (std::getline(cell, value, ',')) {{\n"
            f"            total += std::stoi(value);\n"
            f"        }}\n"
            f"    }}\n"
            f"    return total;\n"
            f"}}\n")
        tests = (
            f"#include <cassert>\n#include <string>\n"
            f"long {f}(const std::string&);\n\n"
            f"int main() {{\n"
            f'    assert({f}("{text}") == {expected});\n'
            f'    assert({f}("") == 0);\n'
            f'    assert({f}("5") == 5);\n'
            f'    assert({f}("-3,4|10") == 11);\n'
            f"    return 0;\n}}\n")
        def bug(files):
            return {"solution.cpp": files["solution.cpp"].replace(
                "total += std::stoi(value);", "total = std::stoi(value);")}
        return Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement {f} in solution.cpp: parse a 'a,b,c | d,e' style string with nested "
                  f"getline splitting ('|' for rows, ',' for cells), summing every integer token. "
                  f"{expected} The harness asserts the sample plus edge cases (empty string, single "
                  f"number, negatives)."),
            expected_behavior=f"Nested tokenization sums to {expected} for the sample.",
            code=code, tests=tests, verify_method="compiled_and_executed",
            notes={"explain": {"purpose": "Nested string tokenization with istringstream.",
                               "approach": "Outer getline on '|' yields rows; inner getline on ',' yields cells; std::stoi converts.",
                               "key_points": ["getline with custom delimiter",
                                              "stoi throws on non-numeric garbage",
                                              "accumulator must persist across rows"],
                               "big_o_time": "O(n)", "big_o_space": "O(1) beyond input",
                               "edge_cases": ["empty blob", "single token", "negative numbers"]},
                   "kind": "sum_tokens", "_bug_fns": {"accumulator_overwritten": bug}},
            tags=["cpp", "parsing"], variant="sum_tokens", seed=rng.randrange(2**31))

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.cpp": cand.code})
        if buggy["solution.cpp"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="cpp", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.cpp"], tests=cand.tests,
                          verify_method="compiled_and_executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})


class CppProjectFamily(Family):
    NAME = "cpp_project_multifile"
    LANGUAGE = "cpp"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        shapes = rng.sample(["square", "rect", "tri"], 3)
        header = (
            "#pragma once\n#include <vector>\n\n"
            "struct Shape { virtual ~Shape() = default; virtual double area() const = 0; };\n"
            "class Square : public Shape { public: explicit Square(double s); double area() const override; private: double s_; };\n"
            "class Rect : public Shape { public: Rect(double w, double h); double area() const override; private: double w_, h_; };\n"
            "class Tri : public Shape { public: Tri(double b, double h); double area() const override; private: double b_, h_; };\n"
            "double total_area(const std::vector<Shape*>& shapes);\n")
        impl = (
            '#include "geometry.h"\n\n'
            "Square::Square(double s) : s_(s) {}\ndouble Square::area() const { return s_ * s_; }\n"
            "Rect::Rect(double w, double h) : w_(w), h_(h) {}\n"
            "double Rect::area() const { return w_ * h_; }\n"
            "Tri::Tri(double b, double h) : b_(b), h_(h) {}\n"
            "double Tri::area() const { return b_ * h_ / 2.0; }\n"
            "double total_area(const std::vector<Shape*>& shapes) {\n"
            "    double t = 0.0;\n"
            "    for (const Shape* s : shapes) t += s->area();\n"
            "    return t;\n}\n")
        a, b, c, d = (rng.randint(2, 9) for _ in range(4))
        solution = (
            f'#include "geometry.h"\n\n'
            f"double report() {{\n"
            f"    Square sq({a}); Rect r({b}, {c}); Tri t({d}, {a});\n"
            f"    std::vector<Shape*> shapes = {{&sq, &r, &t}};\n"
            f"    return total_area(shapes);\n"
            f"}}\n")
        expected_total = a * a + b * c + d * a / 2.0
        readme = ("# geometry-kit\n\nPolymorphic shape library.\n\n"
                  "- `geometry.h`/`geometry.cpp`: Shape hierarchy + total_area\n"
                  "- `solution.cpp`: report() composing shapes\n\n"
                  "Build: `g++ -std=c++17 solution.cpp geometry.cpp harness.cpp -pthread`\n")
        tests = (
            '#include <cassert>\n#include <vector>\n'
            '#include "geometry.h"\n'
            'double report();\n\n'
            f'int main() {{\n'
            f'    Square s({a});\n    assert(s.area() == {a * a}.0);\n'
            f'    Rect r({b}, {c});\n    assert(r.area() == {b * c}.0);\n'
            f'    Tri t({d}, {a});\n    assert(t.area() == {d * a / 2.0});\n'
            f'    double total = report();\n'
            f'    assert(total > 0);\n'
            f'    return 0;\n}}\n')
        files = [FileSpec("solution.cpp", solution), FileSpec("geometry.h", header),
                 FileSpec("geometry.cpp", impl), FileSpec("README.md", readme)]
        return Candidate(
            family=self.NAME, language="cpp", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Build the multi-file C++17 project described by README.md: a polymorphic Shape "
                  f"hierarchy (Square/Rect/Tri) in geometry.h + geometry.cpp with total_area(), and "
                  f"solution.cpp implementing report() that composes Square({a}), Rect({b},{c}), "
                  f"Tri({d},{a}). The harness links all translation units and asserts each area "
                  f"(total {expected_total})."),
            expected_behavior=f"Virtual area() dispatch yields total {expected_total} for the composed shapes.",
            files=files, entry="solution.cpp", tests=tests,
            verify_method="compiled_and_executed", is_project=True,
            notes={"explain": {"purpose": "Runtime polymorphism across translation units.",
                               "approach": "Abstract base + overrides; total_area iterates Shape*.",
                               "key_points": ["virtual destructor in the base",
                                              "override keyword catches signature drift",
                                              "separate compilation links geometry.cpp"],
                               "big_o_time": "O(n) over shapes", "big_o_space": "O(n)",
                               "edge_cases": ["empty shape list", "half-integer triangle areas"]}},
            tags=["cpp", "project"], variant="geometry", seed=rng.randrange(2**31))


register(globals(), CppBankFamily)
register(globals(), CppStlFamily)
register(globals(), CppRaiiFamily)
register(globals(), CppParsingFamily)
register(globals(), CppProjectFamily)
