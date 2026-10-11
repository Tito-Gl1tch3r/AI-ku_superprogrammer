"""v1.1.0 module 07: build systems & compiler diagnostics (write dataset).

Three families whose ground truth is a REAL build pipeline (make / gcc
executed inside the verification harness; verify_method = build_executed):

  * c_makefile_repair   fix a broken Makefile: build must succeed, probes
                        must pass, editing util.c must trigger a real
                        recompile, and make clean must work
  * c_warning_gate      make the build warning-clean under
                        -Wall -Wextra -Werror while preserving measured
                        behavior (the task embeds the measured warnings)
  * c_header_guards     repair the include structure (missing guards /
                        circular includes) with the measured compiler error
                        as evidence; behavior probes still pass

Every expectation is MEASURED at generate time (the builder really
compiles and runs the correct program); every planted defect (broken
input or buggy candidate) is verified to break its gate before the
variant is accepted. C sources are built with plain concatenation (no
f-strings on brace-bearing lines) so braces survive verbatim.
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
import tempfile

from generators.core import Candidate, Family, FileSpec, register

# --------------------------------------------------------------------------
# shared: direct build/run helpers (generation side; trusted own code)
# --------------------------------------------------------------------------


def _tmpdir():
    return tempfile.mkdtemp(prefix="aiku_bc_")


def _cleanup(d):
    shutil.rmtree(d, ignore_errors=True)


def _write(d, files):
    for name, content in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p) or d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def _run(cmd, d, timeout=30.0):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": d, "TMPDIR": d, "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        p = subprocess.run(cmd, cwd=d, env=env, capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, "", "timeout"


def _gcc_warn_clean(files, std="-std=c11"):
    """True iff the sources compile under -Wall -Wextra -Werror."""
    d = _tmpdir()
    try:
        _write(d, files)
        rc, _out, _err = _run(["gcc", std, "-Wall", "-Wextra", "-Werror",
                               *sorted(files), "-o", "prog", "-lm"], d)
        return rc == 0
    finally:
        _cleanup(d)


def _collect_warnings(files):
    """Return the list of gcc -Wall -Wextra warning lines (measured)."""
    d = _tmpdir()
    try:
        _write(d, files)
        rc, _out, err = _run(["gcc", "-std=c11", "-Wall", "-Wextra",
                              *sorted(files), "-o", "prog", "-lm"], d)
        if rc != 0:
            return None  # hard error, not warnings
        return [l for l in err.splitlines() if "warning:" in l]
    finally:
        _cleanup(d)


def _build_and_probe(files, build_cmd, probes):
    """Run build_cmd then every probe; return list of stdout strings or
    None when the build fails. probes: list of argv lists."""
    d = _tmpdir()
    try:
        _write(d, files)
        rc, _out, _err = _run(build_cmd, d)
        if rc != 0:
            return None
        outs = []
        for argv in probes:
            rc, out, _err = _run(["./prog", *argv], d, timeout=10.0)
            if rc != 0:
                return None
            outs.append(out)
        return outs
    finally:
        _cleanup(d)


# --------------------------------------------------------------------------
# shared: the small C programs (randomized names, deterministic behavior)
# --------------------------------------------------------------------------

def _c_program_stats(rng):
    """argv ints -> sum/max line. Returns (files, probes)."""
    f_sum = rng.choice(["util_sum", "stats_sum", "agg_sum", "total_of"])
    f_max = rng.choice(["util_max", "stats_max", "agg_max", "peak_of"])
    main_name = rng.choice(["app_main", "driver"])
    base = rng.randrange(3, 12)
    util_c = (
        '#include "util.h"\n'
        "\n"
        "int " + f_sum + "(const int *xs, int n) {\n"
        "    int acc = 0;\n"
        "    for (int i = 0; i < n; i = i + 1) {\n"
        "        acc = acc + xs[i];\n"
        "    }\n"
        "    return acc;\n"
        "}\n"
        "\n"
        "int " + f_max + "(const int *xs, int n) {\n"
        "    int best = xs[0] - " + str(base) + ";\n"
        "    for (int i = 0; i < n; i = i + 1) {\n"
        "        if (xs[i] > best) {\n"
        "            best = xs[i];\n"
        "        }\n"
        "    }\n"
        "    return best;\n"
        "}\n")
    util_h = ("#ifndef UTIL_H\n#define UTIL_H\n\n"
              "int " + f_sum + "(const int *xs, int n);\n"
              "int " + f_max + "(const int *xs, int n);\n\n#endif\n")
    main_c = (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n"
        '#include "util.h"\n'
        "\n"
        "int " + main_name + "(int argc, char **argv) {\n"
        "    int xs[16];\n"
        "    int n = argc - 1;\n"
        "    if (n < 1 || n > 16) {\n"
        "        return 1;\n"
        "    }\n"
        "    for (int i = 0; i < n; i = i + 1) {\n"
        "        xs[i] = atoi(argv[i + 1]);\n"
        "    }\n"
        '    printf("sum=%d max=%d\\n", ' + f_sum + "(xs, n), " + f_max + "(xs, n));\n"
        "    return 0;\n"
        "}\n"
        "\n"
        "int main(int argc, char **argv) { return " + main_name + "(argc, argv); }\n")
    files = {"main.c": main_c, "util.c": util_c, "util.h": util_h}
    probes = []
    for _ in range(5):
        n = rng.randrange(1, 6)
        vals = [str(rng.randrange(-20, 40)) for _ in range(n)]
        probes.append(vals)
    return files, probes


def _c_program_text(rng):
    """argv string -> count/rev line. Returns (files, probes)."""
    f_count = rng.choice(["util_count", "text_count", "count_char"])
    f_rev = rng.choice(["util_rev", "text_rev", "reverse_into"])
    mark = rng.choice("aeiouxyz")
    main_name = rng.choice(["app_main", "driver"])
    util_c = (
        '#include "util.h"\n'
        "#include <string.h>\n"
        "\n"
        "int " + f_count + "(const char *s, char c) {\n"
        "    int hits = 0;\n"
        "    for (int i = 0; s[i] != 0; i = i + 1) {\n"
        "        if (s[i] == c) {\n"
        "            hits = hits + 1;\n"
        "        }\n"
        "    }\n"
        "    return hits;\n"
        "}\n"
        "\n"
        "void " + f_rev + "(char *s) {\n"
        "    size_t n = strlen(s);\n"
        "    for (size_t i = 0; i < n / 2; i = i + 1) {\n"
        "        char tmp = s[i];\n"
        "        s[i] = s[n - 1 - i];\n"
        "        s[n - 1 - i] = tmp;\n"
        "    }\n"
        "}\n")
    util_h = ("#ifndef UTIL_H\n#define UTIL_H\n\n"
              "int " + f_count + "(const char *s, char c);\n"
              "void " + f_rev + "(char *s);\n\n#endif\n")
    main_c = (
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        '#include "util.h"\n'
        "\n"
        "int " + main_name + "(int argc, char **argv) {\n"
        "    char buf[128];\n"
        "    if (argc != 2) {\n"
        "        return 1;\n"
        "    }\n"
        "    strncpy(buf, argv[1], sizeof(buf) - 1);\n"
        "    buf[sizeof(buf) - 1] = 0;\n"
        '    printf("count=%d\\n", ' + f_count + "(buf, '" + mark + "'));\n"
        "    " + f_rev + "(buf);\n"
        '    printf("rev=%s\\n", buf);\n'
        "    return 0;\n"
        "}\n"
        "\n"
        "int main(int argc, char **argv) { return " + main_name + "(argc, argv); }\n")
    files = {"main.c": main_c, "util.c": util_c, "util.h": util_h}
    word_pool = ["listen", "racecar", "build", "systems", "arena",
                 "testing", "pipeline", "compile", "banana", "mississippi"]
    probes = [[w] for w in rng.sample(word_pool, 5)]
    return files, probes


_PROGRAMS = {"stats": _c_program_stats, "text": _c_program_text}


def _correct_makefile():
    return (
        "CC = gcc\n"
        "CFLAGS = -O2 -Wall\n"
        "\n"
        "prog: main.o util.o\n"
        "\t$(CC) $(CFLAGS) -o prog main.o util.o\n"
        "\n"
        "main.o: main.c util.h\n"
        "\t$(CC) $(CFLAGS) -c main.c\n"
        "\n"
        "util.o: util.c util.h\n"
        "\t$(CC) $(CFLAGS) -c util.c\n"
        "\n"
        "clean:\n"
        "\trm -f prog *.o\n"
        "\n"
        ".PHONY: clean\n")


def _break_makefile(kind):
    broken = _correct_makefile()
    if kind == "missing_obj":
        broken = broken.replace("-o prog main.o util.o", "-o prog main.o")
        symptom = ("make fails at LINK time with 'undefined reference' to a "
                   "util function: util.o is never linked in")
    elif kind == "missing_dash_o":
        broken = broken.replace("$(CC) $(CFLAGS) -o prog main.o util.o",
                                "$(CC) $(CFLAGS) main.o util.o")
        symptom = ("make reports success but ./prog does not exist: the "
                   "link rule forgot -o, so gcc writes a.out instead")
    elif kind == "no_util_rule":
        broken = broken.replace(
            "util.o: util.c util.h\n\t$(CC) $(CFLAGS) -c util.c\n\n", "")
        symptom = "make stops with: No rule to make target 'util.o'"
    else:
        raise ValueError(kind)
    return broken, symptom


# --------------------------------------------------------------------------
# shared harness templates (placeholders instantiated via repr())
# --------------------------------------------------------------------------

_HARNESS_MAKEFILE = r'''"""Build gate: real make, behavior probes, rebuild semantics, clean."""
import os
import subprocess

PROBES = __PROBES__


def _run(cmd, timeout=40):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    p = subprocess.run(cmd, cwd=os.getcwd(), env=env, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


rc, out, err = _run(["make"])
if rc != 0:
    print("BUILD-FAILED")
    print((err or out)[-800:])
    raise SystemExit(1)
if not os.path.isfile("prog"):
    print("NO-PROG")
    raise SystemExit(1)

for argv, expected in PROBES:
    rc, out, err = _run(["./prog", *argv], timeout=10)
    if rc != 0 or out != expected:
        print("PROBE-FAILED", argv)
        print("got:", repr(out), "want:", repr(expected))
        raise SystemExit(1)

before = os.path.getmtime("prog")
st = os.stat("util.c")
os.utime("util.c", (st.st_atime + 5, st.st_mtime + 5))
rc, out, err = _run(["make"])
if rc != 0:
    print("REBUILD-FAILED")
    raise SystemExit(1)
after = os.path.getmtime("prog")
combined = (out or "") + (err or "")
recompiled = (after > before) or ("gcc" in combined and
                                  "up to date" not in combined and
                                  "Nothing to be done" not in combined)
if not recompiled:
    print("NO-RECOMPILE-ON-UTIL-CHANGE")
    raise SystemExit(1)

rc, out, err = _run(["make", "clean"])
if rc != 0 or os.path.exists("prog"):
    print("CLEAN-FAILED")
    raise SystemExit(1)
rc, out, err = _run(["make"])
if rc != 0 or not os.path.isfile("prog"):
    print("REBUILD-AFTER-CLEAN-FAILED")
    raise SystemExit(1)
print("BUILD-GATE-OK")
'''

_HARNESS_GCC = r'''"""Gate: warning-clean build under -Wall -Wextra -Werror + probes."""
import os
import subprocess

PROBES = __PROBES__

SOURCES = __SOURCES__


def _run(cmd, timeout=40):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    p = subprocess.run(cmd, cwd=os.getcwd(), env=env, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


rc, out, err = _run(["gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                     *SOURCES, "-o", "prog", "-lm"])
if rc != 0:
    print("BUILD-FAILED")
    print((err or out)[-900:])
    raise SystemExit(1)
for argv, expected in PROBES:
    rc, out, err = _run(["./prog", *argv], timeout=10)
    if rc != 0 or out != expected:
        print("PROBE-FAILED", argv)
        print("got:", repr(out), "want:", repr(expected))
        raise SystemExit(1)
print("WARNING-GATE-OK")
'''


def _harness(template, **literals):
    out = template
    for key, value in literals.items():
        token = "__" + key.upper() + "__"
        assert token in out, f"placeholder {token} not in template"
        out = out.replace(token, repr(value))
    for key in literals:
        assert ("__" + key.upper() + "__") not in out
    return out


# --------------------------------------------------------------------------
# c_makefile_repair
# --------------------------------------------------------------------------

class MakefileRepairFamily(Family):
    """Fix a broken Makefile: real make, probes, rebuild semantics, clean."""
    NAME = "c_makefile_repair"
    LANGUAGE = "c"
    DOMAIN = "systems"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("debugging",)

    def generate(self, rng):
        prog_key = rng.choice(sorted(_PROGRAMS))
        files, probes = _PROGRAMS[prog_key](rng)
        kind = rng.choice(["missing_obj", "missing_dash_o", "no_util_rule"])
        broken, symptom = _break_makefile(kind)
        # measure: correct build probes
        good_files = dict(files)
        good_files["Makefile"] = _correct_makefile()
        outs = _build_and_probe(good_files, ["make"], probes)
        if outs is None:
            return None
        expected = [[argv, out] for argv, out in zip(probes, outs)]
        # measure: the broken Makefile really breaks (its symptom is real)
        broken_files = dict(files)
        broken_files["Makefile"] = broken
        d = _tmpdir()
        try:
            _write(d, broken_files)
            rc, _o, _e = _run(["make"], d)
            if kind == "missing_dash_o":
                ok_broken = rc == 0 and not os.path.isfile(
                    os.path.join(d, "prog"))
            else:
                ok_broken = rc != 0
        finally:
            _cleanup(d)
        if not ok_broken:
            return None  # the break must be real (measured)
        harness = _harness(_HARNESS_MAKEFILE, probes=expected)
        cand_files = dict(files)
        cand_files["Makefile"] = _correct_makefile()
        task = (
            "The build for this small C project is broken. The current "
            "Makefile (quoted below) fails like this: " + symptom + ". "
            "Fix the Makefile so that ALL of these hold, verified by real "
            "execution: (1) plain `make` builds ./prog; (2) ./prog matches "
            "the behavior probes for every tested input; (3) touching "
            "util.c and running make again RECOMPILES (dependencies must "
            "be real, no unity-build shortcuts); (4) `make clean` removes "
            "prog and the objects and a following make rebuilds. Do not "
            "modify the C sources.\n\n--- current Makefile ---\n" + broken +
            "--- end Makefile ---\nWrite the corrected Makefile.")
        return Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty="advanced", task=task,
            expected_behavior="make builds prog, probes pass, util.c edit "
                              "triggers recompile, clean works",
            files=[FileSpec(p, c) for p, c in sorted(cand_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"explain": {
                "purpose": "real build hygiene: targets, deps, phony, flags",
                "approach": "fix the broken rule set, keep deps exact",
                "key_points": ["link needs every object file",
                               "-o names the artifact explicitly",
                               "header deps belong on object rules"],
                "big_o_time": "O(1) builds",
                "big_o_space": "O(sources)",
                "edge_cases": ["stale a.out when -o is forgotten",
                               "rebuild detection through mtime"]}},
            tags=["make", "build-systems", "c"],
            variant=f"{prog_key}|{kind}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: single-recipe build WITHOUT the util.c dependency: it
        # builds and passes probes, but touching util.c does not rebuild
        # (a real anti-pattern the gate exists to catch). Measured.
        prog_key = cand.variant.split("|")[0]
        buggy_mk = ("CC = gcc\n"
                    "CFLAGS = -O2 -Wall\n"
                    "\n"
                    "prog: main.c util.h\n"
                    "\t$(CC) $(CFLAGS) -o prog main.c util.c\n"
                    "\n"
                    "clean:\n"
                    "\trm -f prog *.o\n"
                    "\n"
                    ".PHONY: clean\n")
        files = {f.path: f.content for f in cand.files}
        buggy_files = dict(files)
        buggy_files["Makefile"] = buggy_mk
        harness = cand.tests
        if _build_and_probe(buggy_files, ["make"],
                            [p[0] for p in
                             eval(harness.split("PROBES = ")[1]
                                  .split("\n")[0], {"__builtins__": {}}, {})
                             ][:1]) is None:
            return None  # the buggy build must itself build and pass probes
        rc, out, err = _run_py_gate(buggy_files, harness)
        if rc == 0:
            return None  # gate still green -> not a bug
        buggy = Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty="advanced", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec(p, c) for p, c in sorted(buggy_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"bug_kind": "stale_dependency",
                   "description": "compiles everything in one recipe "
                                  "without a util.c dependency: edits to "
                                  "util.c never trigger a rebuild",
                   "correct_code": {f.path: f.content for f in cand.files}
                                   ["Makefile"]},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "stale_dependency"}


def _run_py_gate(files, harness_src, timeout=40.0):
    """Run the standalone harness (cand.tests) over a file mapping."""
    d = _tmpdir()
    try:
        _write(d, files)
        with open(os.path.join(d, "_harness.py"), "w", encoding="utf-8") as f:
            f.write(harness_src)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": d, "TMPDIR": d, "LANG": "C.UTF-8",
               "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            p = subprocess.run([sys.executable, "_harness.py"], cwd=d,
                               env=env, capture_output=True, text=True,
                               timeout=timeout)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return -9, "", "timeout"
    finally:
        _cleanup(d)


# --------------------------------------------------------------------------
# c_warning_gate
# --------------------------------------------------------------------------

def _inject_warnings(rng, files):
    """Plant warning patterns with DEFINED, behavior-identical semantics.
    Targets are detected from the actual source (stats: acc, text: hits).
    Returns the new files dict, or None when <3 patterns apply."""
    util_c = files["util.c"]
    main_c = files["main.c"]
    counter_line = None
    for probe in ("    int acc = 0;\n", "    int hits = 0;\n"):
        if probe in util_c:
            counter_line = probe
            break
    if counter_line is None:
        return None
    patterns = ["unused_var", "unused_but_set", "unused_static"]
    if "strncpy" in main_c:
        patterns.append("sign_compare")
    chosen = rng.sample(patterns, 3)
    out_util = util_c
    out_main = main_c
    if "unused_var" in chosen:
        out_util = out_util.replace(
            counter_line,
            counter_line + "    int debug_note = " +
            str(rng.randrange(2, 9)) + ";\n", 1)
    if "unused_but_set" in chosen:
        var_name = counter_line.strip().split()[1]
        out_util = out_util.replace(
            counter_line,
            counter_line + "    int stash = 0;\n", 1)
        marker = "    return " + var_name + ";\n"
        out_util = out_util.replace(
            marker, "    stash = " + var_name + ";\n" + marker, 1)
    if "unused_static" in chosen:
        out_util = ("static int helper_pool(void) {\n"
                    "    return 42;\n"
                    "}\n\n") + out_util
    if "sign_compare" in chosen:
        out_main = out_main.replace(
            "    strncpy(buf, argv[1], sizeof(buf) - 1);\n",
            "    size_t want = strlen(argv[1]);\n"
            "    int i;\n"
            "    for (i = 0; i < want && i < 127; i = i + 1) {\n"
            "        buf[i] = argv[1][i];\n"
            "    }\n"
            "    buf[i] = 0;\n", 1)
    return {"main.c": out_main, "util.c": out_util,
            "util.h": files["util.h"]}


class WarningGateFamily(Family):
    """Make the build warning-clean under -Wall -Wextra -Werror while the
    measured behavior stays identical."""
    NAME = "c_warning_gate"
    LANGUAGE = "c"
    DOMAIN = "systems"
    DIFFICULTIES = ("advanced",)
    SUPPORTS = ("debugging",)

    def generate(self, rng):
        prog_key = rng.choice(sorted(_PROGRAMS))
        base_files, probes = _PROGRAMS[prog_key](rng)
        files = _inject_warnings(rng, base_files)
        if files is None:
            return None
        warnings = _collect_warnings(files)
        if not warnings or len(warnings) < 2:
            return None
        # measured correct behavior comes from the FIXED (base) program
        outs = _build_and_probe(base_files, ["gcc", "-std=c11", "-Wall",
                                             "-Wextra", *sorted(base_files),
                                             "-o", "prog", "-lm"], probes)
        if outs is None:
            return None
        if not _gcc_warn_clean(base_files):
            return None
        expected = [[argv, out] for argv, out in zip(probes, outs)]
        sources = ["main.c", "util.c"]
        harness = _harness(_HARNESS_GCC, probes=expected, sources=sources)
        cand_files = dict(base_files)
        task = (
            "This C project must become warning-clean WITHOUT changing "
            "behavior. The current sources (quoted below) compile, but "
            "gcc -Wall -Wextra reports REAL warnings:\n" +
            "\n".join("  " + w for w in warnings[:6]) +
            "\nFix main.c and util.c so that gcc -std=c11 -Wall -Wextra "
            "-Werror compiles clean while the program's observed behavior "
            "stays EXACTLY the same (the harness checks every probe). Fix "
            "the root cause (remove dead code, fix the comparison/type "
            "mismatch); do not just silence with casts unless that is the "
            "genuine fix.\n\n--- main.c ---\n" + files["main.c"] +
            "\n--- util.c ---\n" + files["util.c"] +
            "\n--- util.h (unchanged) ---\n" + files["util.h"])
        return Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty="advanced", task=task,
            expected_behavior="build is clean under -Wall -Wextra -Werror "
                              "and behavior probes stay identical",
            files=[FileSpec(p, c) for p, c in sorted(cand_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"explain": {
                "purpose": "treat compiler diagnostics as a contract",
                "approach": "fix root causes of each warning class",
                "key_points": ["unused code is removed, not referenced",
                               "sign-compare needs a real type fix",
                               "-Werror makes hygiene enforceable"],
                "big_o_time": "O(1) builds",
                "big_o_space": "O(sources)",
                "edge_cases": ["defined-behavior-only patterns",
                               "behavior identical before/after"]}},
            tags=["gcc", "warnings", "build-systems", "c"],
            variant=f"{prog_key}|{'|'.join(sorted(w.split(':')[0] for w in warnings))[:60]}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: one warning pattern re-introduced -> -Werror gate must fail
        files = {f.path: f.content for f in cand.files}
        buggy_files = dict(files)
        buggy_files["util.c"] = ("static int helper_pool(void) {\n"
                                 "    return 42;\n"
                                 "}\n\n" + files["util.c"])
        harness = cand.tests
        rc, _o, _e = _run_py_gate(buggy_files, harness)
        if rc == 0:
            return None  # gate still green -> not a bug
        buggy = Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty="advanced", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec(p, c) for p, c in sorted(buggy_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"bug_kind": "warning_reintroduced",
                   "description": "an unused static function sneaks back "
                                  "in; -Werror rejects the build",
                   "correct_code": files["util.c"]},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "warning_reintroduced"}


# --------------------------------------------------------------------------
# c_header_guards
# --------------------------------------------------------------------------

def _guarded_header(body, guard):
    return ("#ifndef " + guard + "\n#define " + guard + "\n\n" + body +
            "\n#endif\n")


def _point_files(spec, kind, broken):
    """Deterministic point-program builder from a name spec."""
    sname = spec["sname"]
    tname = spec["tname"]
    f_len = spec["f_len"]
    f_show = spec["f_show"]
    main_name = spec["main_name"]
    fmt = spec["fmt"]
    a_body = ("struct " + sname + " {\n    int x;\n    int y;\n};\n\n"
              "typedef struct " + sname + " " + tname + ";\n\n"
              "int " + f_len + "(" + tname + " p);")
    b_body = '#include "a.h"\n\nvoid ' + f_show + "(" + tname + " p);"
    if broken:
        a_h = a_body + "\n"
        b_h = b_body + "\n"
        if kind == "circular":
            a_h = '#include "b.h"\n\n' + a_h
    else:
        guard_a = spec["guard_a"]
        guard_b = spec["guard_b"]
        # The real-world repair for BOTH kinds: guards on every header and
        # an ACYCLIC include graph (a.h never includes b.h; b.h includes
        # a.h after its guard opens). Guards alone do not fix circularity.
        a_h = ("#ifndef " + guard_a + "\n#define " + guard_a + "\n\n" +
               a_body + "\n\n#endif\n")
        b_h = ("#ifndef " + guard_b + "\n#define " + guard_b + "\n\n" +
               b_body + "\n\n#endif\n")
    util_c = (
        '#include "a.h"\n'
        '#include "b.h"\n'
        "#include <stdio.h>\n"
        "#include <math.h>\n"
        "\n"
        "int " + f_len + "(" + tname + " p) {\n"
        "    return (int)sqrt((double)(p.x * p.x + p.y * p.y));\n"
        "}\n"
        "\n"
        "void " + f_show + "(" + tname + " p) {\n"
        '    printf("' + fmt + '\\n", p.x, p.y);\n'
        "}\n")
    main_c = (
        "#include <stdio.h>\n"
        "#include <stdlib.h>\n"
        '#include "a.h"\n'
        '#include "b.h"\n'
        "\n"
        "int " + main_name + "(int argc, char **argv) {\n"
        "    if (argc != 3) {\n"
        "        return 1;\n"
        "    }\n"
        "    " + tname + " p;\n"
        "    p.x = atoi(argv[1]);\n"
        "    p.y = atoi(argv[2]);\n"
        '    printf("len=%d ", ' + f_len + "(p));\n"
        "    " + f_show + "(p);\n"
        "    return 0;\n"
        "}\n"
        "\n"
        "int main(int argc, char **argv) { return " + main_name +
        "(argc, argv); }\n")
    files = {"main.c": main_c, "util.c": util_c, "a.h": a_h, "b.h": b_h}
    probes = spec["probes"]
    return files, probes


class HeaderGuardsFamily(Family):
    """Repair the include structure; the measured compiler error is the
    evidence, and the behavior probes must still pass."""
    NAME = "c_header_guards"
    LANGUAGE = "c"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("debugging",)

    def generate(self, rng):
        pool = [(3, 4), (0, 0), (6, 8), (5, 12), (1, 1), (9, 12), (8, 15),
                (7, 24), (20, 21), (2, 2), (11, 60), (33, 44)]
        spec = {"sname": rng.choice(["pt_rec", "coord_rec", "vec_rec"]),
                "tname": rng.choice(["point_t", "coord_t", "vec2_t"]),
                "f_len": rng.choice(["pt_len", "coord_len", "vec_len"]),
                "f_show": rng.choice(["pt_show", "coord_show", "vec_show"]),
                "main_name": rng.choice(["app_main", "driver"]),
                "guard_a": rng.choice(["A_H", "POINT_H", "GEO_A_H"]),
                "guard_b": rng.choice(["B_H", "SHOW_H", "GEO_B_H"]),
                "fmt": rng.choice(["pt=%d,%d", "loc=(%d,%d)", "xy %d:%d",
                                   "<%d|%d>"]),
                "probes": [[str(x), str(y)] for x, y in
                           rng.sample(pool, 6)]}
        kind = rng.choice(["no_guard", "circular"])
        broken_files, _p = _point_files(spec, kind, broken=True)
        fixed_files, probes = _point_files(spec, kind, broken=False)
        # measure the REAL break
        d = _tmpdir()
        try:
            _write(d, broken_files)
            rc, _o, err = _run(["gcc", "-std=c11", "-Wall", "-Wextra",
                                "main.c", "util.c", "-o", "prog", "-lm"], d)
        finally:
            _cleanup(d)
        if rc == 0 or not err.strip():
            return None
        err_excerpt = "\n".join(err.splitlines()[:4])[:400]
        # measure the fixed package: clean build + probes
        if not _gcc_warn_clean(fixed_files):
            return None
        outs = _build_and_probe(fixed_files,
                                ["gcc", "-std=c11", "-Wall", "-Wextra",
                                 "main.c", "util.c", "-o", "prog", "-lm"],
                                probes)
        if outs is None:
            return None
        expected = [[argv, out] for argv, out in zip(probes, outs)]
        harness = _harness(_HARNESS_GCC, probes=expected,
                           sources=["main.c", "util.c"])
        task = (
            "This C project does not compile. The headers a.h and b.h are "
            "quoted below; the REAL compiler says:\n" + err_excerpt +
            "\nRepair a.h and b.h (include guards / include structure) so "
            "that gcc -std=c11 -Wall -Wextra -Werror builds clean and the "
            "program behaves exactly as the probes expect. Do not change "
            "main.c or util.c; keep the SAME declarations and types (the "
            "fix is structural, not behavioral).\n\n--- a.h ---\n" +
            broken_files["a.h"] + "\n--- b.h ---\n" + broken_files["b.h"])
        difficulty = rng.choice(sorted(self.DIFFICULTIES))
        return Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty=difficulty, task=task,
            expected_behavior="headers build clean under -Werror and "
                              "behavior probes stay identical",
            files=[FileSpec(p, c) for p, c in sorted(fixed_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"explain": {
                "purpose": "include hygiene: guards and include structure",
                "approach": "structural repair, zero behavior change",
                "key_points": ["every header gets a unique guard",
                               "circular includes break without guards",
                               "the struct must be defined exactly once"],
                "big_o_time": "O(1) builds",
                "big_o_space": "O(sources)",
                "edge_cases": ["double inclusion via transitive includes",
                               "guard name collisions"]}},
            tags=["c", "headers", "build-systems"],
            variant=f"{kind}",
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        files = {f.path: f.content for f in cand.files}
        # buggy: guard macro MISMATCH between #ifndef and #define
        buggy_files = dict(files)
        a_h = files["a.h"]
        if "#ifndef" in a_h and "#define" in a_h:
            lines = a_h.splitlines()
            for i, l in enumerate(lines):
                if l.startswith("#ifndef "):
                    lines[i] = "#ifndef " + l[8:] + "_X"
                    break
            buggy_files["a.h"] = "\n".join(lines) + "\n"
        else:
            return None
        harness = cand.tests
        rc, _o, _e = _run_py_gate(buggy_files, harness)
        if rc == 0:
            return None  # gate still green -> not a bug
        buggy = Candidate(
            family=self.NAME, language="c", domain="systems",
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec(p, c) for p, c in sorted(buggy_files.items())],
            entry=None, tests=harness, verify_method="build_executed",
            is_project=True,
            notes={"bug_kind": "guard_mismatch",
                   "description": "#ifndef and #define names diverge: the "
                                  "guard never closes and the build breaks",
                   "correct_code": files["a.h"]},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy, {"kind": "guard_mismatch"}


register(globals(), MakefileRepairFamily)
register(globals(), WarningGateFamily)
register(globals(), HeaderGuardsFamily)
