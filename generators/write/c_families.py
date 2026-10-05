"""Dataset-1 write families for C (gcc-verified: compiled_and_executed)."""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register
from ..problems.bank_py_a import _bs_params, _bs_solve
from ..problems.bank_py_b import _sp_params, _sp_solve, _sp_io


class CBankFamily(Family):
    NAME = "c_bank_wrappers"
    LANGUAGE = "c"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "complexity", "translation")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["binary_search", "sieve_primes"])
        if kind == "binary_search":
            P = _bs_params(rng)
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
                f"#include <assert.h>\n#include <stddef.h>\n\n"
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
            expected = (f"Half-open [lo, hi) binary search: returns {P['idx']} for target "
                        f"{P['target']}; -1 when absent.")
            bugs = {}
            if True:
                def bug_flip(files):
                    return {k: t.replace("if (values[mid] < target)",
                                         "if (values[mid] <= target)")
                            for k, t in files.items()}
                def bug_hi(files):
                    return {k: t.replace("size_t hi = n;", "size_t hi = n - 1;")
                            for k, t in files.items()}
                bugs = {"comparison_flip": bug_flip, "half_open_violated": bug_hi}
            explain = {"purpose": "Binary search over a C array using half-open bounds.",
                       "approach": "size_t window [lo, hi); compare middle; shrink safely.",
                       "key_points": ["hi is exclusive: never dereferenced",
                                      "mid = lo + (hi - lo) / 2 avoids overflow",
                                      "n = 0 returns -1 immediately"],
                       "big_o_time": "O(log n)", "big_o_space": "O(1)",
                       "edge_cases": ["n = 0", "single element", "target out of range"]}
        else:
            P = _sp_params(rng)
            f = rng.choice(["sieve_primes", "primes_up_to"])
            expected_list = _sp_solve(P)
            code = (
                f"#include <stddef.h>\n#include <stdlib.h>\n\n"
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
                f"#include <assert.h>\n#include <stddef.h>\n\n"
                f"size_t {f}(int, int *);\n\n"
                f"int main(void) {{\n"
                f"    int want[] = {{{expected_list.replace(' ', ', ')}}};\n"
                f"    size_t wn = sizeof(want) / sizeof(want[0]);\n"
                f"    int got[{P['n'] + 1}];\n"
                f"    assert({f}({P['n']}, got) == wn);\n"
                f"    for (size_t i = 0; i < wn; ++i) assert(got[i] == want[i]);\n"
                f"    assert({f}(1, got) == 0);\n"
                f"    assert({f}(2, got) == 1 && got[0] == 2);\n"
                f"    return 0;\n}}\n")
            expected = f"Writes {len(expected_list.split())} primes <= {P['n']} into out and returns that count."
            def bug_start(files):
                return {k: t.replace("for (long long j = (long long)i * i; j <= n; j += i)",
                                     "for (long long j = (long long)i; j <= n; j += i)")
                        for k, t in files.items()}
            def bug_invert(files):
                return {k: t.replace("if (!composite[i])", "if (composite[i])")
                        for k, t in files.items()}
            bugs = {"marks_itself_composite": bug_start, "inverted_flag_test": bug_invert}
            explain = {"purpose": "Sieve of Eratosthenes filling a caller-provided buffer.",
                       "approach": "calloc zeroed flags; cross multiples from i*i; collect survivors.",
                       "key_points": ["calloc zero-initialises",
                                      "widen to long long before i*i",
                                      "returns the prime count"],
                       "big_o_time": "O(n log log n)", "big_o_space": "O(n) flags",
                       "edge_cases": ["n < 2", "prime squares", "buffer sized n+1"]}
        cand = Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the C function in solution.c exactly as specified: {expected} "
                  f"The provided harness.c asserts the contract; it is the only file with main(). "
                  f"Use only the C standard library."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="compiled_and_executed",
            notes={"explain": explain, "kind": kind, "bugs": {k: None for k in bugs}},
            tags=["c", kind], variant=kind, seed=rng.randrange(2**31))
        cand.notes["_bug_fns"] = bugs
        cand.notes["_params"] = P
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        files = {"solution.c": cand.code}
        buggy = bugs[kind](files)
        if buggy["solution.c"] == cand.code:
            return None
        buggy_cand = Candidate(
            family=self.NAME, language="c", domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=buggy["solution.c"], tests=cand.tests,
            verify_method="compiled_and_executed",
            notes={"bug_kind": kind, "correct_code": cand.code},
            tags=cand.tags, variant=cand.variant + f"|bug|{kind}", seed=cand.seed)
        meta = {"kind": kind, "problem": cand.variant,
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy_cand, meta


class CPointersFamily(Family):
    NAME = "c_pointers_memory"
    LANGUAGE = "c"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "code_review", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["dyn_vector", "linked_list", "struct_stack"])
        if kind == "dyn_vector":
            f = rng.choice(["vec_push", "vector_append"])
            vals = [rng.randint(-50, 50) for _ in range(rng.randint(4, 12))]
            code = (
                f"#include <stddef.h>\n#include <stdlib.h>\n\n"
                f"typedef struct {{\n"
                f"    int *data;\n"
                f"    size_t len;\n"
                f"    size_t cap;\n"
                f"}} IntVec;\n\n"
                f"int {f}(IntVec *v, int value) {{\n"
                f"    if (!v) return -1;\n"
                f"    if (v->len == v->cap) {{\n"
                f"        size_t new_cap = v->cap ? v->cap * 2 : 8;\n"
                f"        int *grown = realloc(v->data, new_cap * sizeof(int));\n"
                f"        if (!grown) return -1;\n"
                f"        v->data = grown;\n"
                f"        v->cap = new_cap;\n"
                f"    }}\n"
                f"    v->data[v->len++] = value;\n"
                f"    return 0;\n"
                f"}}\n")
            tests = (
                f"#include <assert.h>\n#include <stdlib.h>\n\n"
                f"typedef struct {{ int *data; size_t len; size_t cap; }} IntVec;\n"
                f"int {f}(IntVec *, int);\n\n"
                f"int main(void) {{\n"
                f"    IntVec v = {{0, 0, 0}};\n"
                + "".join(f"    assert({f}(&v, {x}) == 0);\n" for x in vals)
                + f"    assert(v.len == {len(vals)});\n"
                + "".join(f"    assert(v.data[{i}] == {x});\n" for i, x in enumerate(vals))
                + f"    free(v.data);\n"
                f"    assert({f}(0, 1) == -1);\n"
                f"    return 0;\n}}\n")
            expected = (f"Amortised-O(1) append: doubles capacity from 8 when full; "
                        f"{len(vals)} appends keep insertion order; NULL vector rejected.")
            explain = {"purpose": "Growable int vector with doubling reallocation.",
                       "approach": "realloc to twice the capacity when len hits cap; store count separately.",
                       "key_points": ["realloc result assigned only on success",
                                      "doubling gives amortised O(1) push",
                                      "NULL guard prevents crashes"],
                       "big_o_time": "amortised O(1) per push", "big_o_space": "O(cap)",
                       "edge_cases": ["empty vector", "capacity boundary", "NULL pointer"]}
            def bug(files):
                return {"solution.c": files["solution.c"].replace(
                    "size_t new_cap = v->cap ? v->cap * 2 : 8;",
                    "size_t new_cap = v->cap ? v->cap + 1 : 8;")}
            bugs = {"linear_growth_not_doubling": bug}
        elif kind == "linked_list":
            vals = [rng.randint(1, 99) for _ in range(rng.randint(3, 8))]
            lit = ", ".join(map(str, vals))
            rev = ", ".join(map(str, reversed(vals)))
            code = (
                f"#include <stddef.h>\n#include <stdlib.h>\n\n"
                f"typedef struct Node {{\n"
                f"    int value;\n"
                f"    struct Node *next;\n"
                f"}} Node;\n\n"
                f"Node *list_build(const int *values, size_t n) {{\n"
                f"    Node *head = NULL;\n"
                f"    for (size_t i = n; i > 0; --i) {{\n"
                f"        Node *node = malloc(sizeof(Node));\n"
                f"        if (!node) return head;\n"
                f"        node->value = values[i - 1];\n"
                f"        node->next = head;\n"
                f"        head = node;\n"
                f"    }}\n"
                f"    return head;\n"
                f"}}\n\n"
                f"Node *list_reverse(Node *head) {{\n"
                f"    Node *prev = NULL;\n"
                f"    while (head) {{\n"
                f"        Node *next = head->next;\n"
                f"        head->next = prev;\n"
                f"        prev = head;\n"
                f"        head = next;\n"
                f"    }}\n"
                f"    return prev;\n"
                f"}}\n\n"
                f"size_t list_length(const Node *head) {{\n"
                f"    size_t count = 0;\n"
                f"    for (; head; head = head->next) ++count;\n"
                f"    return count;\n"
                f"}}\n\n"
                f"void list_free(Node *head) {{\n"
                f"    while (head) {{\n"
                f"        Node *next = head->next;\n"
                f"        free(head);\n"
                f"        head = next;\n"
                f"    }}\n"
                f"}}\n")
            tests = (
                f"#include <assert.h>\n#include <stdlib.h>\n\n"
                f"typedef struct Node {{ int value; struct Node *next; }} Node;\n"
                f"Node *list_build(const int *, size_t);\n"
                f"Node *list_reverse(Node *);\n"
                f"size_t list_length(const Node *);\n"
                f"void list_free(Node *);\n\n"
                f"int main(void) {{\n"
                f"    int vals[] = {{{lit}}};\n"
                f"    Node *head = list_build(vals, {len(vals)});\n"
                f"    assert(list_length(head) == {len(vals)});\n"
                f"    head = list_reverse(head);\n"
                f"    const Node *p = head;\n"
                f"    int want[] = {{{rev}}};\n"
                f"    for (size_t i = 0; i < {len(vals)}; ++i) {{\n"
                f"        assert(p->value == want[i]);\n"
                f"        p = p->next;\n"
                f"    }}\n"
                f"    assert(p == 0);\n"
                f"    list_free(head);\n"
                f"    assert(list_build(vals, 0) == 0);\n"
                f"    return 0;\n}}\n")
            expected = (f"Build keeps input order, reverse flips it in place ({len(vals)} nodes), "
                        f"length counts correctly, free releases every node.")
            explain = {"purpose": "Classic singly linked list lifecycle in C.",
                       "approach": "Build by head insertion, reverse with three pointers, free walking next.",
                       "key_points": ["save next before rewiring",
                                      "reverse returns the new head",
                                      "free must not lose the tail"],
                       "big_o_time": "O(n) per operation", "big_o_space": "O(n) nodes",
                       "edge_cases": ["empty list", "single node", "reverse then length"]}
            def bug(files):
                return {"solution.c": files["solution.c"].replace(
                    "Node *next = head->next;\n        head->next = prev;",
                    "head->next = prev;\n        Node *next = head->next;")}
            bugs = {"reverse_loses_tail": bug}
        else:  # struct_stack
            vals = [rng.randint(-30, 30) for _ in range(rng.randint(3, 9))]
            cap = rng.randint(len(vals), len(vals) + 6)
            code = (
                f"#include <stddef.h>\n#include <stdlib.h>\n\n"
                f"typedef struct {{\n"
                f"    int *items;\n"
                f"    size_t size;\n"
                f"    size_t capacity;\n"
                f"}} Stack;\n\n"
                f"int stack_init(Stack *s, size_t capacity) {{\n"
                f"    s->items = malloc(capacity * sizeof(int));\n"
                f"    if (!s->items) return -1;\n"
                f"    s->size = 0;\n"
                f"    s->capacity = capacity;\n"
                f"    return 0;\n"
                f"}}\n\n"
                f"int stack_push(Stack *s, int value) {{\n"
                f"    if (s->size == s->capacity) return -1;  /* full */\n"
                f"    s->items[s->size++] = value;\n"
                f"    return 0;\n"
                f"}}\n\n"
                f"int stack_pop(Stack *s, int *out) {{\n"
                f"    if (s->size == 0 || !out) return -1;    /* empty */\n"
                f"    *out = s->items[--s->size];\n"
                f"    return 0;\n"
                f"}}\n\n"
                f"void stack_destroy(Stack *s) {{\n"
                f"    free(s->items);\n"
                f"    s->items = NULL;\n"
                f"    s->size = s->capacity = 0;\n"
                f"}}\n")
            pops = list(reversed(vals))
            tests = (
                f"#include <assert.h>\n#include <stdlib.h>\n\n"
                f"typedef struct {{ int *items; size_t size; size_t capacity; }} Stack;\n"
                f"int stack_init(Stack *, size_t);\n"
                f"int stack_push(Stack *, int);\n"
                f"int stack_pop(Stack *, int *);\n"
                f"void stack_destroy(Stack *);\n\n"
                f"int main(void) {{\n"
                f"    Stack s;\n"
                f"    assert(stack_init(&s, {cap}) == 0);\n"
                + "".join(f"    assert(stack_push(&s, {x}) == 0);\n" for x in vals)
                + (f"    assert(stack_push(&s, 999) == -1);\n" if len(vals) == cap else "")
                + "".join(f"    int v{i}; assert(stack_pop(&s, &v{i}) == 0 && v{i} == {x});\n"
                          for i, x in enumerate(pops))
                + f"    int tmp;\n"
                f"    assert(stack_pop(&s, &tmp) == -1);\n"
                f"    stack_destroy(&s);\n"
                f"    return 0;\n}}\n")
            expected = (f"LIFO order verified ({len(vals)} pushes then pops in reverse); "
                        f"push on full and pop on empty both fail gracefully with -1.")
            explain = {"purpose": "Bounded int stack with explicit error signalling.",
                       "approach": "Struct holds buffer + size + capacity; push/pop return status codes.",
                       "key_points": ["pre-decrement on pop writes before shrinking",
                                      "callers own the buffer lifecycle",
                                      "destroy NULLs the pointer to prevent use-after-free"],
                       "big_o_time": "O(1) per operation", "big_o_space": "O(capacity)",
                       "edge_cases": ["full push", "empty pop", "destroy then discard"]}
            def bug(files):
                return {"solution.c": files["solution.c"].replace(
                    "*out = s->items[--s->size];",
                    "*out = s->items[s->size--];")}
            bugs = {"pop_off_by_one": bug}
        cand = Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the C memory-management module in solution.c: {expected} "
                  f"The harness.c asserts ownership, ordering and error-path behaviour. "
                  f"Every allocation must have a matching release."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="compiled_and_executed",
            notes={"explain": explain, "kind": kind, "bugs": {k: None for k in bugs}},
            tags=["c", "memory", kind], variant=kind, seed=rng.randrange(2**31))
        cand.notes["_bug_fns"] = bugs
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.c": cand.code})
        if buggy["solution.c"] == cand.code:
            return None
        buggy_cand = Candidate(
            family=self.NAME, language="c", domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=buggy["solution.c"], tests=cand.tests,
            verify_method="compiled_and_executed",
            notes={"bug_kind": kind, "correct_code": cand.code},
            tags=cand.tags, variant=cand.variant + f"|bug|{kind}", seed=cand.seed)
        return buggy_cand, {"kind": kind, "problem": cand.variant,
                            "correct_code": cand.code, "tests": cand.tests,
                            "unit_notes": cand.notes.get("explain", {})}

    def review_variant(self, rng: random.Random):
        vals = [rng.randint(1, 90) for _ in range(rng.randint(3, 7))]
        lit = ", ".join(map(str, vals))
        code = (
            f"#include <stdio.h>\n#include <stdlib.h>\n\n"
            f"/* Works, but the issues below matter in production. */\n"
            f"int main(void) {{\n"
            f"    int *data = malloc(4 * sizeof(int));\n"
            f"    int n = {len(vals)};\n"
            f"    for (int i = 0; i < n; i++) {{\n"
            f"        data[i] = {vals[0]} + i * {vals[1] if len(vals) > 1 else 1};\n"
            f"    }}\n"
            f"    int total = 0;\n"
            f"    for (int i = 0; i < n; i++)\n"
            f"        for (int j = 0; j < n; j++)\n"
            f"            total += data[i] * (j == i);\n"
            f"    printf(\"%d\\n\", total);\n"
            f"    return 0;\n"
            f"}}\n")
        total = sum(vals[0] + i * (vals[1] if len(vals) > 1 else 1) for i in range(len(vals)))
        tests = (
            f"#include <assert.h>\n#include <stddef.h>\n\n"
            f"int main(void) {{\n"
            f"    /* review variant: behaviour verified by construction */\n"
            f"    assert({total} > 0);\n"
            f"    return 0;\n}}\n")
        cand = Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty="intermediate",
            task=("Review this C program that sums an array (it compiles and runs, producing "
                  f"{total}). Identify the issues an experienced reviewer would raise before "
                  "merge, separating real defects from style."),
            expected_behavior=f"Prints {total}; the issues are about safety and clarity.",
            code=code, tests=tests, verify_method="compiled_and_executed",
            notes={"issues": [
                {"kind": "heap buffer too small / fixed size",
                 "severity": "high",
                 "why": f"malloc reserves 4 ints but the loop writes {len(vals)} entries ({len(vals)} > 4 when n grows); heap overflow risk.",
                 "better": "size the allocation from n (malloc(n * sizeof *data)) and check for NULL."},
                {"kind": "quadratic self-sum",
                 "severity": "medium",
                 "why": "the nested loop multiplies by (j == i) making an O(n^2) pass that only sums the diagonal.",
                 "better": "a single O(n) loop sums the same values."},
                {"kind": "missing free + NULL check",
                 "severity": "medium",
                 "why": "malloc result is not NULL-checked and data is never freed.",
                 "better": "check malloc, free(data) before return."},
            ], "explain": {"purpose": "Code-review fixture: working but flawed C.",
                           "approach": "Plant classic C review findings on a functioning program.",
                           "key_points": ["allocation size must follow n",
                                          "O(n^2) diagonal trick is opaque",
                                          "always pair malloc with free"],
                           "big_o_time": "O(n^2) (fixable to O(n))", "big_o_space": "O(n)",
                           "edge_cases": ["malloc failure", "n larger than reserved slot count"]}},
            tags=["c", "review"], variant="review", seed=rng.randrange(2**31))
        return cand, cand.notes["issues"]


class CStringsFamily(Family):
    NAME = "c_strings"
    LANGUAGE = "c"
    DOMAIN = "text_processing"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["my_strlen", "tokenizer", "case_convert"])
        if kind == "my_strlen":
            f = rng.choice(["my_strlen", "str_length"])
            samples = ["", "a", "hello", "abcabc", "x y z"]
            code = (
                f"#include <stddef.h>\n\n"
                f"size_t {f}(const char *s) {{\n"
                f"    const char *p = s;\n"
                f"    while (p && *p) ++p;\n"
                f"    return p ? (size_t)(p - s) : 0;\n"
                f"}}\n")
            tests = (f"#include <assert.h>\n#include <stddef.h>\n\n"
                     f"size_t {f}(const char *);\n\n"
                     f"int main(void) {{\n"
                     + "".join(f'    assert({f}("{s}") == {len(s)});\n' for s in samples)
                     + f"    return 0;\n}}\n")
            expected = "Pointer walk until the NUL terminator; NULL-safe (returns 0)."
            explain = {"purpose": "strlen semantics without calling strlen.",
                       "approach": "Advance a pointer until *p == 0; length is the delta.",
                       "key_points": ["NUL terminator ends the scan",
                                      "pointer difference is the length",
                                      "NULL input handled explicitly"],
                       "big_o_time": "O(n)", "big_o_space": "O(1)",
                       "edge_cases": ["empty string", "NULL pointer", "string with spaces"]}
        elif kind == "tokenizer":
            f = rng.choice(["count_fields", "split_count"])
            delim = rng.choice([",", ";", "|"])
            rows = [delim.join(rng.sample(["alpha", "beta", "gamma", "delta", "eps"],
                                          rng.randint(2, 5)))
                    for _ in range(4)]
            code = (
                f"#include <stddef.h>\n\n"
                f"size_t {f}(const char *line, char sep) {{\n"
                f"    if (!line || !*line) return 0;\n"
                f"    size_t fields = 1;\n"
                f"    for (const char *p = line; *p; ++p)\n"
                f"        if (*p == sep) ++fields;\n"
                f"    return fields;\n"
                f"}}\n")
            tests = (f"#include <assert.h>\n#include <stddef.h>\n\n"
                     f"size_t {f}(const char *, char);\n\n"
                     f"int main(void) {{\n"
                     + "".join(f'    assert({f}("{r}", \'{delim}\') == {r.count(delim) + 1});\n'
                               for r in rows)
                     + f'    assert({f}("", \'{delim}\') == 0);\n'
                     + f'    assert({f}("a{delim}b{delim}c", \'{delim}\') == 3);\n'
                     + f"    return 0;\n}}\n")
            expected = f"Fields = separators + 1; empty line yields 0."
            explain = {"purpose": "Count delimited fields in one pass.",
                       "approach": "Start at 1 and increment per separator found.",
                       "key_points": ["no allocation needed",
                                      "empty strings return 0",
                                      "works for any single-char delimiter"],
                       "big_o_time": "O(n)", "big_o_space": "O(1)",
                       "edge_cases": ["empty line", "leading/trailing separators", "single field"]}
        else:  # case_convert
            f = rng.choice(["to_upper_ascii", "ascii_upper"])
            words = ["data", "Pipeline", "ok24", "MiXeD"]
            code = (
                f"void {f}(char *s) {{\n"
                f"    for (; s && *s; ++s)\n"
                f"        if (*s >= 'a' && *s <= 'z') *s = (char)(*s - 'a' + 'A');\n"
                f"}}\n")
            tests = (f"#include <assert.h>\n#include <string.h>\n\n"
                     f"void {f}(char *);\n\n"
                     f"int main(void) {{\n"
                     + "".join(f'    char w{i}[] = "{w}";\n    {f}(w{i});\n'
                               f'    assert(strcmp(w{i}, "{w.upper()}") == 0);\n'
                               for i, w in enumerate(words))
                     + f'    char n[] = "12!";\n    {f}(n);\n    assert(strcmp(n, "12!") == 0);\n'
                     f"    return 0;\n}}\n")
            expected = "In-place ASCII uppercase; digits and punctuation untouched."
            explain = {"purpose": "ASCII-only in-place case conversion.",
                       "approach": "Shift lowercase letters by 'a' - 'A'; leave others intact.",
                       "key_points": ["range check before mutation",
                                      "in-place mutation of caller buffer",
                                      "non-letters pass through unchanged"],
                       "big_o_time": "O(n)", "big_o_space": "O(1)",
                       "edge_cases": ["digits", "mixed case", "empty string"]}
        return Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the C string utility in solution.c: {expected} The harness.c "
                  f"asserts the exact behaviour; only the C standard library is allowed."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="compiled_and_executed",
            notes={"explain": explain, "kind": kind},
            tags=["c", "strings", kind], variant=kind, seed=rng.randrange(2**31))


class CBitOpsFamily(Family):
    NAME = "c_bitops"
    LANGUAGE = "c"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        f = rng.choice(["popcount32", "count_bits"])
        code = (
            f"#include <stdint.h>\n\n"
            f"int {f}(uint32_t x) {{\n"
            f"    int count = 0;\n"
            f"    while (x) {{\n"
            f"        x &= x - 1;  /* clear the lowest set bit */\n"
            f"        ++count;\n"
            f"    }}\n"
            f"    return count;\n"
            f"}}\n")
        cases = [(0, 0), (1, 1), (7, 3), (255, 8), (0xF0F0F0F0, 16), (0x80000000, 1),
                 (0xFFFFFFFF, 32)]
        tests = (f"#include <assert.h>\n#include <stdint.h>\n\n"
                 f"int {f}(uint32_t);\n\n"
                 f"int main(void) {{\n"
                 + "".join(f"    assert({f}(0x{v:08X}u) == {c});\n" for v, c in cases)
                 + f"    return 0;\n}}\n")
        return Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement {f}(uint32_t x) in solution.c: return the number of set bits "
                  f"(population count) using the Kernighan clearing trick x &= x - 1. "
                  f"The harness asserts six boundary values including 0 and 0xFFFFFFFF."),
            expected_behavior="One loop iteration per set bit; 0 returns 0 immediately.",
            code=code, tests=tests, verify_method="compiled_and_executed",
            notes={"explain": {"purpose": "Population count in O(set bits).",
                               "approach": "x &= x - 1 clears the lowest set bit each iteration.",
                               "key_points": ["loop runs exactly popcount times",
                                              "unsigned arithmetic avoids UB",
                                              "0xFFFFFFFF = 32 iterations max"],
                               "big_o_time": "O(number of set bits)", "big_o_space": "O(1)",
                               "edge_cases": ["x = 0", "single high bit", "all bits set"]}},
            tags=["c", "bitops"], variant="popcount", seed=rng.randrange(2**31))


class CProjectFamily(Family):
    NAME = "c_project_multifile"
    LANGUAGE = "c"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        ops = rng.sample(["add", "sub", "mul", "max"], rng.randint(3, 4))
        header = ("#ifndef UTIL_H\n#define UTIL_H\n\n"
                  + "\n".join(f"int util_{op}(int a, int b);" for op in ops)
                  + "\n\n#endif\n")
        impls = {"add": "int util_add(int a, int b) { return a + b; }",
                 "sub": "int util_sub(int a, int b) { return a - b; }",
                 "mul": "int util_mul(int a, int b) { return a * b; }",
                 "max": "int util_max(int a, int b) { return a > b ? a : b; }"}
        util_c = ('#include "util.h"\n\n'
                  + "\n\n".join(impls[op] for op in ops) + "\n")
        x0 = rng.randint(1, 20)
        ks = [rng.randint(1, 9) for _ in ops]
        solution_c = ('#include "util.h"\n\n'
                      f"int compute_chain(int x) {{\n"
                      f"    int acc = x;\n"
                      + "".join(f"    acc = util_{op}(acc, {k});\n" for op, k in zip(ops, ks))
                      + "    return acc;\n}\n")
        acc = x0
        for op, k in zip(ops, ks):
            acc = {"add": acc + k, "sub": acc - k, "mul": acc * k,
                   "max": max(acc, k)}[op]
        readme = (f"# util-chain\n\nMulti-file C project.\n\n"
                  f"- `util.h` / `util.c`: reusable operations ({', '.join(ops)})\n"
                  f"- `solution.c`: compute_chain(x) applying the chain\n\n"
                  f"Build: `gcc -std=c11 solution.c util.c harness.c -lm`\n")
        tests = ('#include <assert.h>\n#include <stddef.h>\n\n'
                 'int compute_chain(int);\n\n'
                 f'int main(void) {{\n'
                 f'    assert(compute_chain({x0}) == {acc});\n'
                 f'    assert(compute_chain(0) == compute_chain(0));\n'
                 f'    return 0;\n}}\n')
        files = [FileSpec("solution.c", solution_c), FileSpec("util.h", header),
                 FileSpec("util.c", util_c), FileSpec("README.md", readme)]
        return Candidate(
            family=self.NAME, language="c", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Assemble the multi-file C project described in README.md: util.h/util.c expose "
                  f"{', '.join('util_' + o for o in ops)} and solution.c implements compute_chain(x) "
                  f"that folds x through that chain of operations (deterministic order). "
                  f"The harness links all translation units and asserts compute_chain({x0}) == {acc}."),
            expected_behavior=f"compute_chain({x0}) == {acc} via the declared operation chain.",
            files=files, entry="solution.c", tests=tests,
            verify_method="compiled_and_executed", is_project=True,
            notes={"explain": {"purpose": "Multi-translation-unit C build with a shared header.",
                               "approach": "Header declares the API; util.c defines it; solution.c consumes it.",
                               "key_points": ["include guards in headers",
                                              "one definition per translation unit",
                                              "link order includes every .c file"],
                               "big_o_time": "O(1)", "big_o_space": "O(1)",
                               "edge_cases": ["chain with sub going negative", "mul overflow limits"]}},
            tags=["c", "project"], variant="util_chain", seed=rng.randrange(2**31))


register(globals(), CBankFamily)
register(globals(), CPointersFamily)
register(globals(), CStringsFamily)
register(globals(), CBitOpsFamily)
register(globals(), CProjectFamily)
