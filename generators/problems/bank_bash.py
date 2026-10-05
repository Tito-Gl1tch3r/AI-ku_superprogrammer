"""Bash implementations for the problem bank (POSIX-ish text pipelines)."""
from __future__ import annotations

from .bank_core import CodeUnit, Problem, register_problem
from .bank_py_b import _wf_params, _wf_spec, _wf_solve, _wf_io


def _bash_wf(P, rng):
    f = rng.choice(["top_words", "word_top", "frequent_words"])
    m = P["m"]
    script = (
        f"#!/usr/bin/env bash\n"
        f"# {f}: read m on the first line, then log lines; print the m most\n"
        f"# frequent words as 'word count', ties broken alphabetically.\n"
        f"set -u\n\n"
        f"read -r top\n\n"
        f"awk '{{ for (i = 1; i <= NF; i++) count[$i]++ }}\n"
        f"END {{ for (w in count) print count[w], w }}'\n"
        f"  | sort -k1,1nr -k2,2\n"
        f"  | head -n \"$top\"\n"
        f"  | awk '{{ print $2, $1 }}'\n")
    expected_lines = _wf_solve(P).split("\n")
    cases = [{"args": [], "stdin": f"{m}\n" + "\n".join(P["lines"]) + "\n",
              "expected_stdout": _wf_solve(P) + "\n", "expected_exit": 0,
              "stdout_mode": "exact"}]
    tests = ""
    cli = {"script.sh": script}
    def bug_tie(files):
        return {k: t.replace("sort -k1,1nr -k2,2", "sort -k1,1n -k2,2r")
                for k, t in files.items()}
    def bug_head(files):
        return {k: t.replace('head -n "$top"', 'head -n "$((top + 1))"')
                for k, t in files.items()}
    def bug_field(files):
        return {k: t.replace("print $2, $1", "print $1, $2")
                for k, t in files.items()}
    return CodeUnit(files={"script.sh": script}, tests=tests, cli=cli, function_name=f,
                    bugs={"tie_break_reversed": bug_tie, "off_by_top_n": bug_head,
                          "swapped_output_columns": bug_field},
                    notes={"purpose": "Shell pipeline ranking words by frequency.",
                           "approach": "awk counts, sort orders by count desc then word asc, head trims, awk swaps columns for output.",
                           "key_points": ["sort -k1,1nr sorts numerically descending on the count",
                                          "-k2,2 breaks ties alphabetically ascending",
                                          "set -euo pipefail fails fast on any pipeline stage"],
                           "big_o_time": "O(W log U)", "big_o_space": "O(U)",
                           "edge_cases": ["empty lines", "fewer words than m", "ties"]})


register_problem(Problem(pid="word_frequency", domain="text_processing",
                         params=_wf_params, spec=_wf_spec, io=_wf_io,
                         solve=_wf_solve, impls={"bash": _bash_wf}))
