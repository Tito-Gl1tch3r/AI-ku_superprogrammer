"""C implementations for the problem bank."""
from __future__ import annotations

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_a import _bs_params, _bs_spec, _bs_solve, _bs_io
from .bank_py_a import _ms_params, _ms_spec, _ms_solve, _ms_io
from .bank_py_b import _sp_params, _sp_spec, _sp_solve, _sp_io
from .bank_py_b import _mm_params, _mm_spec, _mm_solve, _mm_io


def _c_bs(P, rng):
    f = rng.choice(["binary_search", "find_sorted", "index_of_sorted"])
    a = ", ".join(map(str, P["arr"]))
    code = (
        f"#include <stddef.h>\n\n"
        f"int {f}(const int *values, size_t n, int target) {{\n"
        f"    size_t lo = 0;\n"
        f"    size_t hi = n;\n"
        f"    while (lo < hi) {{\n"
        f"        size_t mid = lo + (hi - lo) / 2;\n"
        f"        if (values[mid] == target) return (int)mid;\n"
        f"        if (values[mid] < target) lo = mid + 1;\n"
        f"        else hi = mid;\n"
        f"    }}\n"
        f"    return -1;\n"
        f"}}\n")
    tests = (
        f"#include <assert.h>\n\n"
        f"int {f}(const int *, size_t, int);\n\n"
        f"int main(void) {{\n"
        f"    int v1[] = {{{a}}};\n"
        f"    assert({f}(v1, {P['n']}, {P['target']}) == {P['idx']});\n"
        f"    int v2[] = {{4}};\n"
        f"    assert({f}(v2, 1, 4) == 0);\n"
        f"    int v3[] = {{1, 3, 5}};\n"
        f"    assert({f}(v3, 3, 4) == -1);\n"
        f"    assert({f}(v3, 3, 5) == 2);\n"
        f"    assert({f}(v3, 0, 1) == -1);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.c": code,
        "main.c": (
            f"#include <stdio.h>\n#include <stdlib.h>\n"
            f"int {f}(const int *, size_t, int);\n\n"
            f"int main(void) {{\n"
            f"    int n, target;\n"
            f"    if (scanf(\"%d %d\", &n, &target) != 2) return 1;\n"
            f"    int *v = malloc((size_t)n * sizeof(int));\n"
            f"    for (int i = 0; i < n; ++i) scanf(\"%d\", &v[i]);\n"
            f"    printf(\"%d\\n\", {f}(v, (size_t)n, target));\n"
            f"    free(v);\n"
            f"    return 0;\n}}\n")}
    def bug_flip(files):
        return {k: t.replace("if (values[mid] < target)", "if (values[mid] <= target)")
                for k, t in files.items()}
    def bug_mid(files):
        return {k: t.replace("size_t mid = lo + (hi - lo) / 2;", "size_t mid = (lo + hi) / 2 + 1;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.c": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"comparison_flip": bug_flip, "mid_skips_window": bug_mid},
                    notes={"purpose": "Binary search over a C array with half-open [lo, hi) bounds.",
                           "approach": "Compare the middle element and shrink a half-open index window.",
                           "key_points": ["half-open bounds avoid the classic off-by-one",
                                          "hi is never dereferenced (exclusive)",
                                          "return -1 when the window empties"],
                           "big_o_time": "O(log n)", "big_o_space": "O(1)",
                           "edge_cases": ["n = 0", "single element", "target out of range"]})


def _c_ms(P, rng):
    f = rng.choice(["merge_sort_into", "merge_sort_range", "sort_copy_merge"])
    want = ", ".join(map(str, sorted(P["arr"])))
    src = ", ".join(map(str, P["arr"]))
    code = (
        f"#include <stdlib.h>\n#include <string.h>\n\n"
        f"static void merge_halves(const int *src, int *tmp,\n"
        f"                          size_t lo, size_t mid, size_t hi) {{\n"
        f"    size_t i = lo, j = mid, k = lo;\n"
        f"    while (i < mid && j < hi)\n"
        f"        tmp[k++] = (src[i] <= src[j]) ? src[i++] : src[j++];\n"
        f"    while (i < mid) tmp[k++] = src[i++];\n"
        f"    while (j < hi) tmp[k++] = src[j++];\n"
        f"    memcpy(src + lo, tmp + lo, (hi - lo) * sizeof(int));\n"
        f"}}\n\n"
        f"static void msort_rec(int *data, int *tmp, size_t lo, size_t hi) {{\n"
        f"    if (hi - lo < 2) return;\n"
        f"    size_t mid = lo + (hi - lo) / 2;\n"
        f"    msort_rec(data, tmp, lo, mid);\n"
        f"    msort_rec(data, tmp, mid, hi);\n"
        f"    merge_halves(data, tmp, lo, mid, hi);\n"
        f"}}\n\n"
        f"void {f}(int *data, size_t n) {{\n"
        f"    if (n < 2) return;\n"
        f"    int *tmp = malloc(n * sizeof(int));\n"
        f"    if (!tmp) return;  /* allocation failure: leave data untouched */\n"
        f"    msort_rec(data, tmp, 0, n);\n"
        f"    free(tmp);\n"
        f"}}\n")
    tests = (
        f"#include <assert.h>\n#include <string.h>\n\n"
        f"void {f}(int *, size_t);\n\n"
        f"int main(void) {{\n"
        f"    int data[] = {{{src}}};\n"
        f"    int want[] = {{{want}}};\n"
        f"    {f}(data, {P['n']});\n"
        f"    assert(memcmp(data, want, sizeof(data)) == 0);\n"
        f"    int single[] = {{7}};\n"
        f"    {f}(single, 1);\n"
        f"    assert(single[0] == 7);\n"
        f"    int dup[] = {{2, 2, 1, 2}};\n"
        f"    int dup_want[] = {{1, 2, 2, 2}};\n"
        f"    {f}(dup, 4);\n"
        f"    assert(memcmp(dup, dup_want, sizeof(dup)) == 0);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.c": code,
        "main.c": (
            f"#include <stdio.h>\n#include <stdlib.h>\n"
            f"void {f}(int *, size_t);\n\n"
            f"int main(void) {{\n"
            f"    int n;\n    if (scanf(\"%d\", &n) != 1) return 1;\n"
            f"    int *v = malloc((size_t)n * sizeof(int));\n"
            f"    for (int i = 0; i < n; ++i) scanf(\"%d\", &v[i]);\n"
            f"    {f}(v, (size_t)n);\n"
            f"    for (int i = 0; i < n; ++i)\n"
            f"        printf(i + 1 < n ? \"%d \" : \"%d\\n\", v[i]);\n"
            f"    free(v);\n"
            f"    return 0;\n}}\n")}
    def bug_tail(files):
        return {k: t.replace("while (i < mid) tmp[k++] = src[i++];",
                             "while (i + 1 < mid) tmp[k++] = src[i++];")
                for k, t in files.items()}
    def bug_cmp(files):
        return {k: t.replace("(src[i] <= src[j])", "(src[i] - 1 <= src[j])")
                for k, t in files.items()}
    return CodeUnit(files={"solution.c": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"dropped_tail_element": bug_tail, "shifted_merge": bug_cmp},
                    notes={"purpose": "Bottom-up recursion merge sort over raw C arrays with a scratch buffer.",
                           "approach": "Split [lo, hi) at mid, sort halves, merge with two pointers into tmp, copy back.",
                           "key_points": ["half-open ranges [lo, hi) everywhere",
                                          "one malloc'ed scratch buffer reused by all levels",
                                          "memcpy copies the merged run back into the input"],
                           "big_o_time": "O(n log n)", "big_o_space": "O(n) scratch",
                           "edge_cases": ["n < 2", "duplicates", "malloc failure guard"]})


def _c_sp(P, rng):
    f = rng.choice(["sieve_primes", "primes_up_to"])
    expected = _sp_solve(P)
    code = (
        f"#include <stddef.h>\n#include <stdlib.h>\n#include <string.h>\n\n"
        f"size_t {f}(int n, int *out) {{\n"
        f"    if (n < 2) return 0;\n"
        f"    unsigned char *composite = calloc((size_t)n + 1, 1);\n"
        f"    if (!composite) return 0;\n"
        f"    size_t count = 0;\n"
        f"    for (int i = 2; (long long)i * i <= n; ++i)\n"
        f"        if (!composite[i])\n"
        f"            for (long long j = (long long)i * i; j <= n; j += i)\n"
        f"                composite[j] = 1;\n"
        f"    for (int x = 2; x <= n; ++x)\n"
        f"        if (!composite[x]) out[count++] = x;\n"
        f"    free(composite);\n"
        f"    return count;\n"
        f"}}\n")
    tests = (
        f"#include <assert.h>\n\n"
        f"size_t {f}(int, int *);\n\n"
        f"int main(void) {{\n"
        f"    int want[] = {{{expected.replace(' ', ', ')}}};\n"
        f"    size_t wn = sizeof(want) / sizeof(want[0]);\n"
        f"    int got[{P['n'] + 1}];\n"
        f"    assert({f}({P['n']}, got) == wn);\n"
        f"    for (size_t i = 0; i < wn; ++i) assert(got[i] == want[i]);\n"
        f"    assert({f}(1, got) == 0);\n"
        f"    assert({f}(2, got) == 1 && got[0] == 2);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.c": code,
        "main.c": (
            f"#include <stdio.h>\n#include <stdlib.h>\n"
            f"size_t {f}(int, int *);\n\n"
            f"int main(void) {{\n"
            f"    int n;\n    if (scanf(\"%d\", &n) != 1) return 1;\n"
            f"    int *out = malloc(((size_t)n + 1) * sizeof(int));\n"
            f"    size_t c = {f}(n, out);\n"
            f"    for (size_t i = 0; i < c; ++i)\n"
            f"        printf(i + 1 < c ? \"%d \" : \"%d\\n\", out[i]);\n"
            f"    if (c == 0) printf(\"\\n\");\n"
            f"    free(out);\n"
            f"    return 0;\n}}\n")}
    def bug_start(files):
        return {k: t.replace("for (long long j = (long long)i * i; j <= n; j += i)",
                             "for (long long j = (long long)i; j <= n; j += i)")
                for k, t in files.items()}
    def bug_bound(files):
        return {k: t.replace("for (int i = 2; (long long)i * i <= n; ++i)",
                             "for (int i = 2; (long long)i * i <= n + 1; ++i)")
                for k, t in files.items()}
    return CodeUnit(files={"solution.c": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"marks_itself_composite": bug_start, "overextended_bound": bug_bound},
                    notes={"purpose": "Sieve of Eratosthenes writing primes into a caller buffer.",
                           "approach": "calloc'ed composite flags; cross multiples from i*i; collect survivors.",
                           "key_points": ["calloc zero-initialises the flag array",
                                          "the loop bound is widened to long long before squaring",
                                          "returns the number of primes written"],
                           "big_o_time": "O(n log log n)", "big_o_space": "O(n) flags",
                           "edge_cases": ["n < 2", "buffer sized n+1", "cast before i*i"]})


def _c_mm(P, rng):
    f = rng.choice(["matmul_flat", "multiply_matrices"])
    rows = _mm_solve(P).split("\n")
    want = "{" + ", ".join("{" + r + "}" for r in rows) + "}"
    a_flat = ", ".join(str(x) for row in P["A"] for x in row)
    b_flat = ", ".join(str(x) for row in P["B"] for x in row)
    code = (
        f"void {f}(const int *A, const int *B, long long *C,\n"
        f"         int n, int m, int k) {{\n"
        f"    for (int i = 0; i < n; ++i)\n"
        f"        for (int j = 0; j < k; ++j)\n"
        f"            C[(long long)i * k + j] = 0;\n"
        f"    for (int i = 0; i < n; ++i)\n"
        f"        for (int t = 0; t < m; ++t) {{\n"
        f"            long long a = A[(long long)i * m + t];\n"
        f"            if (a == 0) continue;\n"
        f"            for (int j = 0; j < k; ++j)\n"
        f"                C[(long long)i * k + j] += a * (long long)B[(long long)t * k + j];\n"
        f"        }}\n"
        f"}}\n")
    tests = (
        f"#include <assert.h>\n\n"
        f"void {f}(const int *, const int *, long long *, int, int, int);\n\n"
        f"int main(void) {{\n"
        f"    int A[] = {{{a_flat}}};\n"
        f"    int B[] = {{{b_flat}}};\n"
        f"    long long C[{P['n']} * {P['k']}];\n"
        f"    long long want[{P['n']} * {P['k']}] = {want};\n"
        f"    {f}(A, B, C, {P['n']}, {P['m']}, {P['k']});\n"
        f"    for (int i = 0; i < {P['n']} * {P['k']}; ++i) assert(C[i] == want[i]);\n"
        f"    return 0;\n}}\n")
    cli = {
        "solution.c": code,
        "main.c": (
            f"#include <stdio.h>\n#include <stdlib.h>\n"
            f"void {f}(const int *, const int *, long long *, int, int, int);\n\n"
            f"int main(void) {{\n"
            f"    int n, m, k;\n"
            f"    if (scanf(\"%d %d %d\", &n, &m, &k) != 3) return 1;\n"
            f"    int *A = malloc((size_t)n * m * sizeof(int));\n"
            f"    int *B = malloc((size_t)m * k * sizeof(int));\n"
            f"    long long *C = malloc((size_t)n * k * sizeof(long long));\n"
            f"    for (int i = 0; i < n * m; ++i) scanf(\"%d\", &A[i]);\n"
            f"    for (int i = 0; i < m * k; ++i) scanf(\"%d\", &B[i]);\n"
            f"    {f}(A, B, C, n, m, k);\n"
            f"    for (int i = 0; i < n; ++i) {{\n"
            f"        for (int j = 0; j < k; ++j)\n"
            f"            printf(j + 1 < k ? \"%lld \" : \"%lld\\n\", C[(long long)i * k + j]);\n"
            f"    }}\n"
            f"    free(A); free(B); free(C);\n"
            f"    return 0;\n}}\n")}
    def bug_swap(files):
        return {k: t.replace("B[(long long)t * k + j]", "B[(long long)j * k + t]")
                for k, t in files.items()}
    def bug_zero(files):
        return {k: t.replace("C[(long long)i * k + j] = 0;",
                             "C[(long long)i * k + j] = 1;")
                for k, t in files.items()}
    return CodeUnit(files={"solution.c": code}, tests=tests, cli=cli, function_name=f,
                    bugs={"swapped_indices": bug_swap, "wrong_identity_init": bug_zero},
                    notes={"purpose": "Row-major flat-array matrix multiply with a zero-skip micro-optimisation.",
                           "approach": "Explicit zeroing pass, then i-t-j accumulation; index arithmetic is (row * cols + col).",
                           "key_points": ["flat indexing: A[i*m + t], B[t*k + j], C[i*k + j]",
                                          "the zero pass is required because C only accumulates",
                                          "skipping zero rows of A saves multiplications"],
                           "big_o_time": "O(n*m*k)", "big_o_space": "O(1) beyond output",
                           "edge_cases": ["1x1 matrices", "zero entries", "flat index arithmetic"]})


def _problem(pid, domain, params, spec, io, solve, impl):
    register_problem(Problem(pid=pid, domain=domain, params=params, spec=spec,
                             io=io, solve=solve, impls={"c": impl}))


_problem("binary_search", "algorithms", _bs_params, _bs_spec, _bs_io, _bs_solve, _c_bs)
_problem("merge_sort", "algorithms", _ms_params, _ms_spec, _ms_io, _ms_solve, _c_ms)
_problem("sieve_primes", "algorithms", _sp_params, _sp_spec, _sp_io, _sp_solve, _c_sp)
_problem("matrix_multiply", "algorithms", _mm_params, _mm_spec, _mm_io, _mm_solve, _c_mm)
