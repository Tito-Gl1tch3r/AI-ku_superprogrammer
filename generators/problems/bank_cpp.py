"""C++ implementations for the problem bank."""
from __future__ import annotations

import random

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_a import _bs_params, _bs_spec, _bs_solve, _bs_io
from .bank_py_a import _ms_params, _ms_spec, _ms_solve, _ms_io
from .bank_py_a import _ts_params, _ts_spec, _ts_solve, _ts_io
from .bank_py_b import _sp_params, _sp_spec, _sp_solve, _sp_io
from .bank_py_b import _mm_params, _mm_spec, _mm_solve, _mm_io
from .bank_py_b import _dj_params, _dj_spec, _dj_solve, _dj_io


def _py_bs(P, rng):
    v = rng.choice(["values", "data", "numbers", "items"])
    f = rng.choice(["binary_search", "find_sorted", "locate", "index_of_sorted"])
    a = ", ".join(map(str, P["arr"]))
    code = (
        f"#include <vector>\n\n"
        f"int {f}(const std::vector<int>& {v}, int target) {{\n"
        f"    int lo = 0, hi = static_cast<int>({v}.size()) - 1;\n"
        f"    while (lo <= hi) {{\n"
        f"        int mid = lo + (hi - lo) / 2;\n"
        f"        if ({v}[mid] == target) return mid;\n"
        f"        if ({v}[mid] < target) lo = mid + 1;\n"
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
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <cstdio>\n#include <vector>\n"
            f"int {f}(const std::vector<int>&, int);\n\n"
            f"int main() {{\n"
            f"    int n, target;\n"
            f"    if (scanf(\"%d %d\", &n, &target) != 2) return 1;\n"
            f"    std::vector<int> v(n);\n"
            f"    for (int i = 0; i < n; ++i) scanf(\"%d\", &v[i]);\n"
            f"    printf(\"%d\\n\", {f}(v, target));\n"
            f"    return 0;\n}}\n")}
    def bug_flip(files):
        return {k: t.replace(f"if ({v}[mid] < target)", f"if ({v}[mid] <= target)")
                for k, t in files.items()}
    def bug_bound(files):
        return {k: t.replace(f"int lo = 0, hi = static_cast<int>({v}.size()) - 1;",
                             f"int lo = 0, hi = static_cast<int>({v}.size());")
                for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"comparison_flip": bug_flip, "upper_bound_init": bug_bound},
                    notes={"purpose": "Locate a value in a sorted vector in O(log n).",
                           "approach": "Inclusive [lo, hi] window; mid = lo + (hi - lo) / 2 to avoid int overflow.",
                           "key_points": ["mid formula prevents overflow for large indices",
                                          "window halves every iteration",
                                          "-1 signals absence"],
                           "big_o_time": "O(log n)", "big_o_space": "O(1)",
                           "edge_cases": ["empty vector", "single element", "target out of range"]})


def _py_ms(P, rng):
    v = rng.choice(["values", "data", "items", "numbers"])
    f = rng.choice(["merge_sort", "sort_values", "merge_sort_copy"])
    a = ", ".join(map(str, P["arr"]))
    code = (
        f"#include <vector>\n\n"
        f"static void merge_runs(std::vector<int>& out,\n"
        f"                       const std::vector<int>& left,\n"
        f"                       const std::vector<int>& right) {{\n"
        f"    out.clear();\n"
        f"    out.reserve(left.size() + right.size());\n"
        f"    size_t i = 0, j = 0;\n"
        f"    while (i < left.size() && j < right.size()) {{\n"
        f"        if (left[i] <= right[j]) out.push_back(left[i++]);\n"
        f"        else out.push_back(right[j++]);\n"
        f"    }}\n"
        f"    while (i < left.size()) out.push_back(left[i++]);\n"
        f"    while (j < right.size()) out.push_back(right[j++]);\n"
        f"}}\n\n"
        f"std::vector<int> {f}(std::vector<int> {v}) {{\n"
        f"    if ({v}.size() <= 1) return {v};\n"
        f"    size_t mid = {v}.size() / 2;\n"
        f"    std::vector<int> left = {f}(std::vector<int>({v}.begin(), {v}.begin() + mid));\n"
        f"    std::vector<int> right = {f}(std::vector<int>({v}.begin() + mid, {v}.end()));\n"
        f"    std::vector<int> merged;\n"
        f"    merge_runs(merged, left, right);\n"
        f"    return merged;\n"
        f"}}\n")
    tests = (
        f"#include <cassert>\n#include <vector>\n"
        f"std::vector<int> {f}(std::vector<int>);\n\n"
        f"int main() {{\n"
        f"    std::vector<int> src = {{{a}}};\n"
        f"    std::vector<int> out = {f}(src);\n"
        f"    std::vector<int> want = {{{', '.join(map(str, sorted(P['arr'])))}}};\n"
        f"    assert(out == want);\n"
        f"    assert({f}({{}}).empty());\n"
        f"    std::vector<int> dup = {{2, 2, 2}};\n"
        f"    assert({f}(dup) == dup);\n"
        f"    std::vector<int> neg = {{-1, -3, -2}};\n"
        f"    std::vector<int> neg_want = {{-3, -2, -1}};\n"
        f"    assert({f}(neg) == neg_want);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <cstdio>\n#include <vector>\n"
            f"std::vector<int> {f}(std::vector<int>);\n\n"
            f"int main() {{\n"
            f"    int n;\n    if (scanf(\"%d\", &n) != 1) return 1;\n"
            f"    std::vector<int> v(n);\n"
            f"    for (int i = 0; i < n; ++i) scanf(\"%d\", &v[i]);\n"
            f"    std::vector<int> out = {f}(v);\n"
            f"    for (size_t i = 0; i < out.size(); ++i)\n"
            f"        printf(i + 1 < out.size() ? \"%d \" : \"%d\\n\", out[i]);\n"
            f"    return 0;\n}}\n")}
    def bug_tail(files):
        return {k: t.replace("while (i < left.size()) out.push_back(left[i++]);",
                             "while (i + 1 < left.size()) out.push_back(left[i++]);")
                for k, t in files.items()}
    def bug_cmp(files):
        return {k: t.replace("if (left[i] <= right[j])", "if (left[i] - 1 <= right[j])")
                for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"dropped_tail_element": bug_tail, "shifted_merge": bug_cmp},
                    notes={"purpose": "Stable O(n log n) sorting with divide and conquer.",
                           "approach": "Recursively sort both halves, merge with two pointers into a fresh buffer.",
                           "key_points": ["taking from `left` on ties preserves stability",
                                          "both tail loops after the main merge are required",
                                          "pass-by-value keeps the caller's vector intact"],
                           "big_o_time": "O(n log n)", "big_o_space": "O(n)",
                           "edge_cases": ["empty vector", "all equal", "reverse sorted", "negatives"]})


def _py_ts(P, rng):
    v = rng.choice(["values", "data", "items"])
    f = rng.choice(["two_sum", "find_pair", "pair_with_sum"])
    a = ", ".join(map(str, P["arr"]))
    pair = P["pair"]
    pair_cpp = "std::make_pair(-1, -1)" if pair is None else f"std::make_pair({pair[0]}, {pair[1]})"
    code = (
        f"#include <unordered_map>\n#include <utility>\n#include <vector>\n\n"
        f"std::pair<int, int> {f}(const std::vector<int>& {v}, int target) {{\n"
        f"    std::unordered_map<int, int> seen;  // value -> earliest index\n"
        f"    for (int j = 0; j < static_cast<int>({v}.size()); ++j) {{\n"
        f"        int need = target - {v}[j];\n"
        f"        auto it = seen.find(need);\n"
        f"        if (it != seen.end()) return {{it->second, j}};\n"
        f"        if (!seen.count({v}[j])) seen[{v}[j]] = j;\n"
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
        f"    std::vector<int> one = {{4}};\n"
        f"    assert({f}(one, 8) == std::make_pair(-1, -1));\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <cstdio>\n#include <vector>\n"
            f"std::pair<int, int> {f}(const std::vector<int>&, int);\n\n"
            f"int main() {{\n"
            f"    int n, target;\n"
            f"    if (scanf(\"%d %d\", &n, &target) != 2) return 1;\n"
            f"    std::vector<int> v(n);\n"
            f"    for (int i = 0; i < n; ++i) scanf(\"%d\", &v[i]);\n"
            f"    auto ans = {f}(v, target);\n"
            f"    if (ans.first < 0) printf(\"-1\\n\");\n"
            f"    else printf(\"%d %d\\n\", ans.first, ans.second);\n"
            f"    return 0;\n}}\n")}
    def bug_reuse(files):
        return {k: t.replace("if (!seen.count(", "if (true || !seen.count(")
                for k, t in files.items()}
    def bug_order(files):
        return {k: t.replace("return {it->second, j};", "return {j, it->second};")
                for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"always_overwrite_seen": bug_reuse, "reversed_indices": bug_order},
                    notes={"purpose": "First complement hit with an unordered_map gives O(n) average.",
                           "approach": "Scan left to right; look up target - x before inserting x.",
                           "key_points": ["checking before inserting keeps indices increasing",
                                          "the count guard preserves the earliest duplicate index",
                                          "{-1, -1} encodes absence"],
                           "big_o_time": "O(n) average", "big_o_space": "O(n)",
                           "edge_cases": ["no pair", "duplicates", "pair of equal values"]})


def _py_sp(P, rng):
    f = rng.choice(["sieve_primes", "primes_up_to", "all_primes"])
    expected = _sp_solve(P)
    code = (
        f"#include <vector>\n\n"
        f"std::vector<int> {f}(int n) {{\n"
        f"    std::vector<int> primes;\n"
        f"    if (n < 2) return primes;\n"
        f"    std::vector<char> composite(n + 1, 0);\n"
        f"    for (int i = 2; i * i <= n; ++i) {{\n"
        f"        if (!composite[i]) {{\n"
        f"            for (long long j = 1LL * i * i; j <= n; j += i) composite[j] = 1;\n"
        f"        }}\n"
        f"    }}\n"
        f"    for (int x = 2; x <= n; ++x)\n"
        f"        if (!composite[x]) primes.push_back(x);\n"
        f"    return primes;\n"
        f"}}\n")
    tests = (
        f"#include <cassert>\n#include <vector>\n"
        f"std::vector<int> {f}(int);\n\n"
        f"int main() {{\n"
        f"    std::vector<int> want = {{{expected.replace(' ', ', ')}}};\n"
        f"    assert({f}({P['n']}) == want);\n"
        f"    assert({f}(1).empty());\n"
        f"    std::vector<int> two = {{2}};\n"
        f"    assert({f}(2) == two);\n"
        f"    std::vector<int> ten = {{2, 3, 5, 7}};\n"
        f"    assert({f}(10) == ten);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <cstdio>\n#include <vector>\n"
            f"std::vector<int> {f}(int);\n\n"
            f"int main() {{\n    int n;\n"
            f"    if (scanf(\"%d\", &n) != 1) return 1;\n"
            f"    std::vector<int> p = {f}(n);\n"
            f"    for (size_t i = 0; i < p.size(); ++i)\n"
            f"        printf(i + 1 < p.size() ? \"%d \" : \"%d\\n\", p[i]);\n"
            f"    return 0;\n}}\n")}
    def bug_start(files):
        return {k: t.replace("for (long long j = 1LL * i * i; j <= n; j += i)",
                             "for (long long j = 1LL * i; j <= n; j += i)")
                for k, t in files.items()}
    def bug_cast(files):
        return {k: t.replace("1LL * i * i", "i * i") for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"marks_itself_composite": bug_start, "int_overflow_cast": bug_cast},
                    notes={"purpose": "Sieve of Eratosthenes in O(n log log n).",
                           "approach": "Byte array of composites; cross out multiples from i*i upward.",
                           "key_points": ["1LL * i * i widens before multiplying to avoid int overflow",
                                          "crossing out starts at i*i (smaller multiples already crossed)",
                                          "outer loop stops at sqrt(n)"],
                           "big_o_time": "O(n log log n)", "big_o_space": "O(n)",
                           "edge_cases": ["n < 2", "n = 2", "prime squares"]})


def _py_mm(P, rng):
    f = rng.choice(["matmul", "multiply_matrices", "matrix_product"])
    rows = _mm_solve(P).split("\n")
    expected = "{" + ", ".join("{" + r + "}" for r in rows) + "}"
    a_flat = ", ".join(str(x) for row in P["A"] for x in row)
    b_flat = ", ".join(str(x) for row in P["B"] for x in row)
    a_rows = "{" + ", ".join("{" + ", ".join(map(str, row)) + "}" for row in P["A"]) + "}"
    b_rows = "{" + ", ".join("{" + ", ".join(map(str, row)) + "}" for row in P["B"]) + "}"
    code = (
        f"#include <cstddef>\n#include <vector>\n\n"
        f"std::vector<std::vector<long long>> {f}(const std::vector<std::vector<int>>& A,\n"
        f"                                        const std::vector<std::vector<int>>& B) {{\n"
        f"    size_t n = A.size(), m = B.size(), k = B[0].size();\n"
        f"    std::vector<std::vector<long long>> C(n, std::vector<long long>(k, 0));\n"
        f"    for (size_t i = 0; i < n; ++i)\n"
        f"        for (size_t t = 0; t < m; ++t)\n"
        f"            for (size_t j = 0; j < k; ++j)\n"
        f"                C[i][j] += static_cast<long long>(A[i][t]) * B[t][j];\n"
        f"    return C;\n"
        f"}}\n")
    tests = (
        f"#include <cassert>\n#include <vector>\n"
        f"std::vector<std::vector<long long>> {f}(const std::vector<std::vector<int>>&, "
        f"const std::vector<std::vector<int>>&);\n\n"
        f"int main() {{\n"
        f"    std::vector<std::vector<int>> A = {a_rows};\n"
        f"    std::vector<std::vector<int>> B = {b_rows};\n"
        f"    std::vector<std::vector<long long>> want = {expected};\n"
        f"    assert({f}(A, B) == want);\n"
        f"    std::vector<std::vector<int>> I = {{{{1, 0}}, {{0, 1}}}};\n"
        f"    std::vector<std::vector<int>> X = {{{{5, 6}}, {{7, 8}}}};\n"
        f"    std::vector<std::vector<long long>> Xw = {{{{5LL, 6LL}}, {{7LL, 8LL}}}};\n"
        f"    assert({f}(I, X) == Xw);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <cstdio>\n#include <vector>\n"
            f"std::vector<std::vector<long long>> {f}(const std::vector<std::vector<int>>&, const std::vector<std::vector<int>>&);\n\n"
            f"int main() {{\n"
            f"    int n, m, k;\n"
            f"    if (scanf(\"%d %d %d\", &n, &m, &k) != 3) return 1;\n"
            f"    std::vector<std::vector<int>> A(n, std::vector<int>(m)), B(m, std::vector<int>(k));\n"
            f"    for (int i = 0; i < n; ++i) for (int t = 0; t < m; ++t) scanf(\"%d\", &A[i][t]);\n"
            f"    for (int t = 0; t < m; ++t) for (int j = 0; j < k; ++j) scanf(\"%d\", &B[t][j]);\n"
            f"    auto C = {f}(A, B);\n"
            f"    for (int i = 0; i < n; ++i) {{\n"
            f"        for (int j = 0; j < k; ++j)\n"
            f"            printf(j + 1 < k ? \"%lld \" : \"%lld\", C[i][j]);\n"
            f"        printf(\"\\n\");\n"
            f"    }}\n"
            f"    return 0;\n}}\n")}
    def bug_swap(files):
        return {k: t.replace("A[i][t]) * B[t][j]", "A[i][t]) * B[j][t]")
                for k, t in files.items()}
    def bug_ikj(files):
        return {k: t.replace("C[i][j] += static_cast<long long>(A[i][t]) * B[t][j];",
                             "C[i][j] = static_cast<long long>(A[i][t]) * B[t][j];")
                for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"swapped_indices": bug_swap, "accumulator_overwritten": bug_ikj},
                    notes={"purpose": "Cache-friendlier i-t-j loop order for matrix multiplication.",
                           "approach": "Accumulate into C[i][j] while t is the middle loop (better memory locality than i-j-t).",
                           "key_points": ["cast to long long before multiplying prevents overflow",
                                          "i-t-j ordering walks B rows contiguously",
                                          "C starts zeroed and only accumulates"],
                           "big_o_time": "O(n*m*k)", "big_o_space": "O(n*k)",
                           "edge_cases": ["1x1 matrices", "identity", "negative entries"]})


def _py_dj(P, rng):
    f = rng.choice(["dijkstra", "shortest_paths", "single_source_distances"])
    expected = _dj_solve(P)
    edges_lit = ", ".join("{" + f"{u}, {v}, {w}" + "}" for u, v, w in P["edges"])
    code = (
        f"#include <array>\n#include <cstdint>\n#include <limits>\n#include <queue>\n#include <utility>\n#include <vector>\n\n"
        f"std::vector<long long> {f}(int n,\n"
        f"                                  const std::vector<std::array<int, 3>>& edges,\n"
        f"                                  int src) {{\n"
        f"    std::vector<std::vector<std::pair<int, int>>> adj(n);\n"
        f"    for (const auto& e : edges) adj[e[0]].push_back({{e[1], e[2]}});\n"
        f"    const long long INF = std::numeric_limits<long long>::max() / 4;\n"
        f"    std::vector<long long> dist(n, INF);\n"
        f"    std::vector<char> settled(n, 0);\n"
        f"    using Item = std::pair<long long, int>;\n"
        f"    std::priority_queue<Item, std::vector<Item>, std::greater<Item>> pq;\n"
        f"    dist[src] = 0;\n"
        f"    pq.push({{0LL, src}});\n"
        f"    while (!pq.empty()) {{\n"
        f"        auto [d, u] = pq.top();\n"
        f"        pq.pop();\n"
        f"        if (settled[u]) continue;\n"
        f"        settled[u] = 1;\n"
        f"        for (auto [v, w] : adj[u]) {{\n"
        f"            long long nd = d + w;\n"
        f"            if (nd < dist[v]) {{\n"
        f"                dist[v] = nd;\n"
        f"                pq.push({{nd, v}});\n"
        f"            }}\n"
        f"        }}\n"
        f"    }}\n"
        f"    for (int i = 0; i < n; ++i)\n"
        f"        if (dist[i] >= INF) dist[i] = -1;\n"
        f"    return dist;\n"
        f"}}\n")
    tests = (
        f"#include <cassert>\n#include <array>\n#include <vector>\n"
        f"std::vector<long long> {f}(int, const std::vector<std::array<int, 3>>&, int);\n\n"
        f"int main() {{\n"
        f"    std::vector<std::array<int, 3>> edges = {{{edges_lit}}};\n"
        f"    std::vector<long long> want = {{{expected.replace(' ', ', ').replace('-', ' -')}}};\n"
        f"    assert({f}({P['n']}, edges, {P['src']}) == want);\n"
        f"    std::vector<std::array<int, 3>> e2 = {{{{0, 1, 7}}}};\n"
        f"    std::vector<long long> w2 = {{0LL, 7LL}};\n"
        f"    assert({f}(2, e2, 0) == w2);\n"
        f"    std::vector<long long> w3 = {{-1LL, 0LL}};\n"
        f"    assert({f}(2, e2, 1) == w3);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.cpp": code,
        "main.cpp": (
            f"#include <array>\n#include <cstdio>\n#include <vector>\n"
            f"std::vector<long long> {f}(int, const std::vector<std::array<int, 3>>&, int);\n\n"
            f"int main() {{\n"
            f"    int n, m, src;\n"
            f"    if (scanf(\"%d %d %d\", &n, &m, &src) != 3) return 1;\n"
            f"    std::vector<std::array<int, 3>> edges(m);\n"
            f"    for (int i = 0; i < m; ++i)\n"
            f"        scanf(\"%d %d %d\", &edges[i][0], &edges[i][1], &edges[i][2]);\n"
            f"    auto d = {f}(n, edges, src);\n"
            f"    for (int i = 0; i < n; ++i)\n"
            f"        printf(i + 1 < n ? \"%lld \" : \"%lld\\n\", d[i]);\n"
            f"    return 0;\n}}\n")}
    def bug_weight(files):
        return {k: t.replace("long long nd = d + w;", "long long nd = d;")
                for k, t in files.items()}
    def bug_struct(files):
        return {k: t.replace("auto [d, u] = pq.top();", "auto [d, u] = pq.top(); (void)d;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.cpp": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"edge_weight_ignored": bug_weight, "distance_shadowed": bug_struct},
                    notes={"purpose": "Dijkstra with a binary heap for sparse graphs.",
                           "approach": "Min-heap of (dist, node); settle nodes once, relax edges lazily.",
                           "key_points": ["structured bindings unpack heap items",
                                          "settled flags skip stale duplicate entries",
                                          "INF/4 headroom prevents overflow on additions"],
                           "big_o_time": "O((V + E) log V)", "big_o_space": "O(V + E)",
                           "edge_cases": ["unreachable nodes", "source distance 0", "lazy deletion"]})


def _problem(pid, domain, params, spec, io, solve, impl):
    register_problem(Problem(pid=pid, domain=domain, params=params, spec=spec,
                             io=io, solve=solve, impls={"cpp": impl}))


_problem("binary_search", "algorithms", _bs_params, _bs_spec, _bs_io, _bs_solve, _py_bs)
_problem("merge_sort", "algorithms", _ms_params, _ms_spec, _ms_io, _ms_solve, _py_ms)
_problem("two_sum", "algorithms", _ts_params, _ts_spec, _ts_io, _ts_solve, _py_ts)
_problem("sieve_primes", "algorithms", _sp_params, _sp_spec, _sp_io, _sp_solve, _py_sp)
_problem("matrix_multiply", "algorithms", _mm_params, _mm_spec, _mm_io, _mm_solve, _py_mm)
_problem("dijkstra", "algorithms", _dj_params, _dj_spec, _dj_io, _dj_solve, _py_dj)
