"""v2.0.0 module 08: capstone integration projects (expert tier, write).

Three families whose ground truth is a COMPOUND gate over a real
multi-file system: unit probes through the public seam, byte-exact CLI
behavior via real subprocesses, and structural checks (AST) that reject
shortcut implementations. All records are expert difficulty and follow
the expert routing policy (expert-hash holdout):

  * py_inventory_ops      implement ops.py (checkout/restock with
                          atomicity semantics) against a given Store;
                          the CLI is really executed per probe
  * py_log_pipeline       implement pipeline.py (classify/aggregate) and
                          answer the report CLI byte-exactly
  * ts_jsonl_pipeline     implement a TypeScript JSONL transformer
                          (filter/map/aggregate) executed under Node
                          type-stripping; determinism is checked by
                          running the CLI twice

Every expectation is MEASURED at generate time from the golden
implementation; every make_buggy is self-verifying (it must FAIL the
compound gate before publication).
"""
from __future__ import annotations

import ast as pyast
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

from generators.core import Candidate, Family, FileSpec, register

# --------------------------------------------------------------------------
# shared: generation-side runner (trusted own code)
# --------------------------------------------------------------------------


def _tmpdir():
    return tempfile.mkdtemp(prefix="aiku_cap_")


def _cleanup(d):
    shutil.rmtree(d, ignore_errors=True)


def _write(d, files):
    for name, content in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p) or d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def _run(cmd, d, timeout=20.0, stdin_text=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": d, "TMPDIR": d, "LANG": "C.UTF-8",
           "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        p = subprocess.run(cmd, cwd=d, env=env, capture_output=True,
                           text=True, timeout=timeout,
                           input=stdin_text if stdin_text is not None else None)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, "", "timeout"


def _run_gate(files, harness_src, timeout=40.0):
    """Run a standalone python harness over a file mapping."""
    d = _tmpdir()
    try:
        _write(d, files)
        with open(os.path.join(d, "_harness.py"), "w", encoding="utf-8") as f:
            f.write(harness_src)
        return _run([sys.executable, "_harness.py"], d, timeout=timeout)
    finally:
        _cleanup(d)


def _has_docstrings(src, fn_names):
    """AST check: every listed function carries a non-empty docstring."""
    try:
        tree = pyast.parse(src)
    except SyntaxError:
        return False
    found = {}
    for node in pyast.walk(tree):
        if isinstance(node, pyast.FunctionDef) and node.name in fn_names:
            doc = pyast.get_docstring(node)
            found[node.name] = bool(doc and doc.strip())
    return all(found.get(n, False) for n in fn_names)


def _harness(template, **literals):
    """Instantiate a harness template with repr()-escaped placeholders."""
    out = template
    for key, value in literals.items():
        token = "__" + key.upper() + "__"
        assert token in out, f"placeholder {token} not in template"
        out = out.replace(token, repr(value))
    for key in literals:
        assert ("__" + key.upper() + "__") not in out, \
            f"placeholder {key} left unreplaced"
    return out


def _imports_of(src):
    try:
        tree = pyast.parse(src)
    except SyntaxError:
        return set()
    mods = set()
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, pyast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


# --------------------------------------------------------------------------
# scenario A: inventory ops (given store + CLI; candidate writes ops.py)
# --------------------------------------------------------------------------

_GIVEN_STORE_PY = '''"""JSON-backed store with atomic saves (given infrastructure)."""
import json
import os


class Store:
    def __init__(self, path):
        self.path = path
        self.items = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                self.items = json.load(fh)

    def get(self, sku):
        if sku in self.items:
            return dict(self.items[sku])
        return None

    def set_qty(self, sku, qty):
        self.items[sku]["qty"] = qty

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.items, fh, sort_keys=True)
        os.replace(tmp, self.path)
'''

_GIVEN_MAIN_PY = '''"""CLI over the store; behavior is frozen (given infrastructure)."""
import sys

from store import Store
import ops


def main(argv):
    if argv and argv[0] == "report":
        store = Store("store.json")
        for sku in sorted(store.items):
            print(sku + "," + str(store.items[sku]["qty"]))
        return 0
    if len(argv) != 3 or argv[0] not in ("checkout", "restock"):
        print("ERR usage")
        return 2
    cmd, sku, n = argv[0], argv[1], int(argv[2])
    store = Store("store.json")
    if cmd == "checkout":
        r = ops.checkout(store, sku, n)
    else:
        r = ops.restock(store, sku, n)
    if r >= 0:
        print("OK " + str(r))
    else:
        print("ERR " + str(r))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

_GOLDEN_OPS = '''"""Inventory operations with refusal codes and atomic saves."""


def checkout(store, sku, n):
    """Take n units of sku out of the store.

    Returns the remaining quantity on success. Refuses WITHOUT touching
    the store: -2 when n <= 0, -3 when the sku is unknown, -1 when the
    stock is insufficient.
    """
    if n <= 0:
        return -2
    item = store.get(sku)
    if item is None:
        return -3
    if item["qty"] < n:
        return -1
    new_qty = item["qty"] - n
    store.set_qty(sku, new_qty)
    store.save()
    return new_qty


def restock(store, sku, n):
    """Add n units of sku. Same refusal codes; returns the new quantity."""
    if n <= 0:
        return -2
    item = store.get(sku)
    if item is None:
        return -3
    new_qty = item["qty"] + n
    store.set_qty(sku, new_qty)
    store.save()
    return new_qty
'''

_HARNESS_INVENTORY = r'''"""Compound gate: unit probes + real CLI + structural checks."""
import ast as _ast
import json
import os
import subprocess
import sys

INIT = __INIT__

UNIT_PROBES = __UNIT_PROBES__

CLI_PROBES = __CLI_PROBES__


def _store_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_store(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, sort_keys=True)


def _run_cli(argv):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    p = subprocess.run([sys.executable, "main.py", *argv], cwd=os.getcwd(),
                       env=env, capture_output=True, text=True, timeout=15)
    return p.returncode, p.stdout


# --- structural checks ----------------------------------------------------
src = open("ops.py", encoding="utf-8").read()
tree = _ast.parse(src)
docs = {}
for node in _ast.walk(tree):
    if isinstance(node, _ast.FunctionDef) and node.name in ("checkout",
                                                            "restock"):
        docs[node.name] = bool(_ast.get_docstring(node))
if not (docs.get("checkout") and docs.get("restock")):
    print("STRUCTURAL: docstrings missing")
    raise SystemExit(1)
imports = set()
for node in _ast.walk(tree):
    if isinstance(node, _ast.Import):
        imports.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, _ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])
forbidden = {"os", "sys", "subprocess", "main", "shutil", "pathlib"}
if imports & forbidden:
    print("STRUCTURAL: forbidden imports " + ",".join(sorted(imports & forbidden)))
    raise SystemExit(1)

# --- unit probes (real Store, real file) ----------------------------------
from store import Store  # noqa: E402
import ops  # noqa: E402

for fn_name, sku, n, want_ret, want_qty in UNIT_PROBES:
    _write_store("unit.json", INIT)
    store = Store("unit.json")
    ret = getattr(ops, fn_name)(store, sku, n)
    if ret != want_ret:
        print("UNIT-FAILED", fn_name, sku, n, "ret", ret, "want", want_ret)
        raise SystemExit(1)
    after = _store_file("unit.json")
    if after != want_qty:
        print("UNIT-STATE-FAILED", fn_name, sku, n, after, "want", want_qty)
        raise SystemExit(1)

# --- CLI probes (byte-exact stdout + store state after) -------------------
for argv, want_out, want_store in CLI_PROBES:
    _write_store("store.json", INIT)
    rc, out = _run_cli(argv)
    if rc != 0 or out != want_out:
        print("CLI-FAILED", argv)
        print("got:", repr(out), "want:", repr(want_out))
        raise SystemExit(1)
    after = _store_file("store.json")
    if after != want_store:
        print("CLI-STATE-FAILED", argv, after, "want", want_store)
        raise SystemExit(1)
print("INVENTORY-GATE-OK")
'''


def _inventory_data(rng):
    names = ["widget", "bolt", "cable", "sensor", "pump", "valve", "gear"]
    rng.shuffle(names)
    skus = ["SKU-" + n[:3].upper() + "-" + str(rng.randrange(10, 99))
            for n in names[:3]]
    init = {sku: {"name": n, "qty": rng.randrange(5, 30)}
            for sku, n in zip(skus, names[:3])}
    return init, skus


class InventoryOpsFamily(Family):
    """Implement ops.py against the given Store + frozen CLI."""
    NAME = "py_inventory_ops"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("expert",)
    SUPPORTS = ("architecture",)

    def generate(self, rng):
        init, skus = _inventory_data(rng)
        skus.sort()
        unit_probes = []
        cli_probes = []
        # measured from the golden implementation on fresh stores
        for sku in skus:
            q0 = init[sku]["qty"]
            take = rng.randrange(1, q0 + 1)
            unit_probes.append(["checkout", sku, take, q0 - take,
                                dict(init, **{sku: dict(init[sku],
                                                        qty=q0 - take)})])
            unit_probes.append(["checkout", sku, q0 + 5, -1, dict(init)])
            unit_probes.append(["checkout", sku, 0, -2, dict(init)])
            unit_probes.append(["restock", sku, rng.randrange(1, 10),
                                None, None])  # filled below
            unit_probes[-1][3] = init[sku]["qty"] + unit_probes[-1][2]
            unit_probes[-1][4] = dict(init, **{sku: dict(
                init[sku], qty=unit_probes[-1][3])})
            unit_probes.append(["restock", "SKU-NOPE-01", 3, -3, dict(init)])
        for cmd, sku, n in (("checkout", skus[0],
                             rng.randrange(1, init[skus[0]]["qty"])),
                            ("restock", skus[1], rng.randrange(1, 9)),
                            ("checkout", "SKU-NOPE-01", 2),
                            ("report", None, None)):
            if cmd == "report":
                want_out = "".join(
                    s + "," + str(init[s]["qty"]) + "\n" for s in skus)
                cli_probes.append([["report"], want_out, dict(init)])
                continue
            base = dict(init)
            if sku not in init:
                want_out = "ERR -3\n"  # unknown sku: state untouched
            elif cmd == "checkout":
                newq = init[sku]["qty"] - n
                if newq >= 0:
                    base[sku] = dict(init[sku], qty=newq)
                    want_out = "OK " + str(newq) + "\n"
                else:
                    want_out = "ERR -1\n"
            else:
                newq = init[sku]["qty"] + n
                base[sku] = dict(init[sku], qty=newq)
                want_out = "OK " + str(newq) + "\n"
            cli_probes.append([[cmd, sku, str(n)], want_out, base])
        harness = _harness(_HARNESS_INVENTORY, init=init,
                           unit_probes=unit_probes, cli_probes=cli_probes)
        files = {"store.py": _GIVEN_STORE_PY, "main.py": _GIVEN_MAIN_PY,
                 "ops.py": _GOLDEN_OPS, "store.json": ""}
        gate_files = {k: v for k, v in files.items() if k != "store.json"}
        rc, out, err = _run_gate(gate_files, harness)
        if rc != 0:
            return None
        task = (
            "You are handed a working system: store.py (JSON-backed store "
            "with atomic saves), main.py (frozen CLI) and store.json as the "
            "database. Implement ops.py with EXACTLY these semantics:\n"
            "- checkout(store, sku, n): return the remaining quantity and "
            "persist it; refuse WITHOUT changing any state: -2 when n <= 0, "
            "-3 when the sku is unknown, -1 when the stock is insufficient.\n"
            "- restock(store, sku, n): return the new quantity and persist "
            "it; same refusal codes.\n"
            "The harness runs unit probes against a REAL Store (it checks "
            "the JSON on disk after every call: a refused checkout must "
            "leave the file byte-identical), then drives main.py as a real "
            "subprocess and checks stdout byte-exactly plus the store state "
            "after each command. Both functions need real docstrings. Do "
            "not modify store.py or main.py; do not import os/sys/"
            "subprocess/main from ops.py.")
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="expert", task=task,
            expected_behavior="ops.py passes unit + CLI + structural gates "
                              "with atomicity respected",
            files=[FileSpec(p, c) for p, c in sorted(files.items())],
            entry="ops.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "enter a working system through its seams",
                "approach": "refusal codes before mutation; persist once",
                "key_points": ["validate-then-mutate keeps atomicity",
                               "the CLI is frozen: ops.py is the only seam",
                               "state on disk is part of the contract"],
                "big_o_time": "O(1) per operation",
                "big_o_space": "O(items)",
                "edge_cases": ["insufficient stock leaves the file untouched",
                               "unknown sku vs bad argument codes"]}},
            tags=["integration", "cli", "atomicity"],
            variant="inventory|" + "|".join(skus),
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: mutate-then-check (breaks atomicity: a refused checkout
        # still persists) — the unit state probe must catch it. Measured.
        buggy = _GOLDEN_OPS.replace(
            '''    item = store.get(sku)
    if item is None:
        return -3
    if item["qty"] < n:
        return -1
    new_qty = item["qty"] - n''',
            '''    item = store.get(sku)
    if item is None:
        return -3
    new_qty = item["qty"] - n
    if item["qty"] < n:
        store.set_qty(sku, new_qty)
        store.save()
        return -1''')
        if buggy == _GOLDEN_OPS:
            return None
        files = {f.path: f.content for f in cand.files}
        rc, _o, _e = _run_gate({**files, "ops.py": buggy}, cand.tests)
        if rc == 0:
            return None  # gate still green -> not a bug
        buggy_cand = Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="expert", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec(p, buggy if p == "ops.py" else c)
                   for p, c in sorted(files.items())],
            entry="ops.py", tests=cand.tests, verify_method="executed",
            is_project=True,
            notes={"bug_kind": "broken_atomicity",
                   "description": "mutate-then-check persists on refusals",
                   "correct_code": _GOLDEN_OPS},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy_cand, {"kind": "broken_atomicity"}


# --------------------------------------------------------------------------
# scenario B: log pipeline (candidate writes pipeline.py)
# --------------------------------------------------------------------------

_GIVEN_LOG_MAIN = '''"""CLI over the pipeline; behavior is frozen (given infrastructure)."""
import sys

import pipeline


def main(argv):
    if len(argv) == 2 and argv[0] == "report":
        with open(argv[1], "r", encoding="utf-8") as fh:
            counts = pipeline.aggregate(fh.read().splitlines())
        for level in sorted(counts):
            print(level + "=" + str(counts[level]))
        return 0
    if len(argv) == 3 and argv[0] == "filter":
        with open(argv[1], "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for line in pipeline.filter_lines(lines, argv[2]):
            print(line)
        return 0
    print("ERR usage")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

_GOLDEN_PIPELINE = '''"""Log line classification and aggregation."""


def classify(line):
    """Classify one log line by its leading tag.

    "[OK] ...", "[WARN] ..." and "[ERR] ..." map to OK / WARN / ERR
    (the tag is case-sensitive and must be the FIRST thing in the line,
    followed by one space). Anything else is ERR.
    """
    for tag in ("[OK] ", "[WARN] ", "[ERR] "):
        if line.startswith(tag):
            return tag[1:-2]
    return "ERR"


def aggregate(lines):
    """Count lines per level; the dict covers OK, WARN and ERR keys even
    at zero (all three, always)."""
    counts = {"OK": 0, "WARN": 0, "ERR": 0}
    for line in lines:
        counts[classify(line)] += 1
    return counts


def filter_lines(lines, level):
    """Return the lines classified as `level`, preserving order."""
    return [l for l in lines if classify(l) == level]
'''

_HARNESS_PIPELINE = r'''"""Compound gate: unit probes + real CLI byte-exact + structural."""
import ast as _ast
import os
import subprocess
import sys

UNIT_PROBES = __UNIT_PROBES__

CLI_PROBES = __CLI_PROBES__


def _run_cli(argv):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    p = subprocess.run([sys.executable, "main.py", *argv], cwd=os.getcwd(),
                       env=env, capture_output=True, text=True, timeout=15)
    return p.returncode, p.stdout


src = open("pipeline.py", encoding="utf-8").read()
tree = _ast.parse(src)
docs = {}
for node in _ast.walk(tree):
    if isinstance(node, _ast.FunctionDef) and node.name in ("classify",
                                                            "aggregate",
                                                            "filter_lines"):
        docs[node.name] = bool(_ast.get_docstring(node))
if not all(docs.get(n, False) for n in ("classify", "aggregate",
                                        "filter_lines")):
    print("STRUCTURAL: docstrings missing")
    raise SystemExit(1)
imports = set()
for node in _ast.walk(tree):
    if isinstance(node, _ast.Import):
        imports.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, _ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])
if imports - {"json"}:
    print("STRUCTURAL: unexpected imports " + ",".join(sorted(imports - {"json"})))
    raise SystemExit(1)

import pipeline  # noqa: E402

for line, want in UNIT_PROBES:
    got = pipeline.classify(line)
    if got != want:
        print("UNIT-FAILED", repr(line), got, "want", want)
        raise SystemExit(1)

for argv, want_out in CLI_PROBES:
    rc, out = _run_cli(argv)
    if rc != 0 or out != want_out:
        print("CLI-FAILED", argv)
        print("got:", repr(out), "want:", repr(want_out))
        raise SystemExit(1)
print("PIPELINE-GATE-OK")
'''


def _log_data(rng):
    msgs = ["boot ok", "reconnect", "disk near capacity", "auth failed",
            "cache warm", "retry 2/5", "socket closed", "job done",
            "timeout waiting", "checksum mismatch"]
    lines = []
    for _ in range(rng.randrange(12, 20)):
        tag = rng.choice(["[OK] ", "[WARN] ", "[ERR] ", "plain line", "",
                          "[ok] lowercase"])
        lines.append(tag + rng.choice(msgs))
    return lines


class LogPipelineFamily(Family):
    """Implement pipeline.py behind the frozen report/filter CLI."""
    NAME = "py_log_pipeline"
    LANGUAGE = "python"
    DOMAIN = "automation"
    DIFFICULTIES = ("expert",)
    SUPPORTS = ("architecture",)

    def generate(self, rng):
        lines = _log_data(rng)
        golden = _GOLDEN_PIPELINE
        # measure classify on every line via the golden module
        probe1 = ("import pipeline\n"
                  "lines = __LINES__\n"
                  "for l in lines:\n"
                  "    print(repr(pipeline.classify(l)))\n").replace(
                      "__LINES__", repr(lines))
        d = _tmpdir()
        try:
            _write(d, {"pipeline.py": golden, "_probe.py": probe1})
            rc, out, _e = _run([sys.executable, "_probe.py"], d)
        finally:
            _cleanup(d)
        if rc != 0 or len(out.splitlines()) != len(lines):
            return None
        unit_probes = []
        for line, got_repr in zip(lines, out.splitlines()):
            unit_probes.append([line, eval(got_repr.strip(),
                                           {"__builtins__": {}}, {})])
        # measure aggregate + filter outputs via the golden module
        probe2 = ("import pipeline, json\n"
                  "lines = __LINES__\n"
                  "print(json.dumps(pipeline.aggregate(lines)))\n"
                  "for lv in ('OK', 'WARN', 'ERR'):\n"
                  "    print(json.dumps(pipeline.filter_lines(lines, lv)))\n"
                  ).replace("__LINES__", repr(lines))
        d2 = _tmpdir()
        try:
            _write(d2, {"pipeline.py": golden, "_probe.py": probe2})
            rc, out2, _e = _run([sys.executable, "_probe.py"], d2)
        finally:
            _cleanup(d2)
        if rc != 0 or len(out2.splitlines()) != 4:
            return None
        agg = json.loads(out2.splitlines()[0])
        want_report = "".join(lv + "=" + str(agg[lv]) + "\n"
                              for lv in sorted(agg))
        cli_probes = [[["report", "input.log"], want_report]]
        for i, lv in enumerate(("OK", "WARN", "ERR")):
            filtered = json.loads(out2.splitlines()[1 + i])
            want = "".join(l + "\n" for l in filtered)
            cli_probes.append([["filter", "input.log", lv], want])
        harness = _harness(_HARNESS_PIPELINE, unit_probes=unit_probes,
                           cli_probes=cli_probes)
        log_text = "\n".join(lines) + "\n"
        files = {"main.py": _GIVEN_LOG_MAIN, "pipeline.py": golden,
                 "input.log": log_text}
        rc, _o, _e = _run_gate(files, harness)
        if rc != 0:
            return None
        task = (
            "You are handed main.py (frozen CLI with `report <path>` and "
            "`filter <path> <level>` commands) and input.log. Implement "
            "pipeline.py with EXACTLY this contract:\n"
            "- classify(line): '[OK] ', '[WARN] ' or '[ERR] ' as the FIRST "
            "thing in the line (case-sensitive, one trailing space) maps "
            "to OK / WARN / ERR; anything else (including '[ok] ' and "
            "empty lines) is ERR.\n"
            "- aggregate(lines): counts per level; the dict ALWAYS covers "
            "all three keys OK, WARN, ERR (zero included).\n"
            "- filter_lines(lines, level): matching lines in order.\n"
            "The harness checks classify against real measured lines, then "
            "runs main.py as a real subprocess over input.log and checks "
            "stdout byte-exactly. All three functions need real docstrings. "
            "No imports beyond json; do not modify main.py or input.log.")
        return Candidate(
            family=self.NAME, language="python", domain="automation",
            difficulty="expert", task=task,
            expected_behavior="pipeline.py passes unit + CLI + structural "
                              "gates byte-exactly",
            files=[FileSpec(p, c) for p, c in sorted(files.items())],
            entry="pipeline.py", tests=harness, verify_method="executed",
            is_project=True,
            notes={"explain": {
                "purpose": "seam-first thinking behind a frozen CLI",
                "approach": "single classifier, aggregation on top",
                "key_points": ["the zero-keys invariant in aggregate",
                               "byte-exact stdout is part of the contract",
                               "case-sensitive tags; default is ERR"],
                "big_o_time": "O(n) over lines",
                "big_o_space": "O(n)",
                "edge_cases": ["lowercase tags are ERR",
                               "missing file paths are main.py's business"]}},
            tags=["integration", "cli", "logs"],
            variant="logs|" + str(len(lines)),
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: aggregate drops zero-count keys (breaks the invariant the
        # CLI prints); the report probe must catch it. Measured.
        buggy = _GOLDEN_PIPELINE.replace(
            '    counts = {"OK": 0, "WARN": 0, "ERR": 0}\n',
            '    counts = {}\n')
        files = {f.path: f.content for f in cand.files}
        rc, _o, _e = _run_gate({**files, "pipeline.py": buggy}, cand.tests)
        if rc == 0:
            return None
        buggy_cand = Candidate(
            family=self.NAME, language="python", domain="automation",
            difficulty="expert", task=cand.task,
            expected_behavior=cand.expected_behavior,
            files=[FileSpec(p, buggy if p == "pipeline.py" else c)
                   for p, c in sorted(files.items())],
            entry="pipeline.py", tests=cand.tests, verify_method="executed",
            is_project=True,
            notes={"bug_kind": "missing_zero_keys",
                   "description": "aggregate omits zero-count levels so "
                                  "the report shape drifts",
                   "correct_code": _GOLDEN_PIPELINE},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy_cand, {"kind": "missing_zero_keys"}


# --------------------------------------------------------------------------
# ts_jsonl_pipeline (TypeScript under Node type-stripping)
# --------------------------------------------------------------------------

_GOLDEN_TS = '''export interface Row {
  id: number;
  kind: string;
  val: number;
}

export interface Summary {
  counts: Record<string, number>;
  total: number;
}

/** Aggregate JSONL rows: per-kind counts (sorted keys) + total of vals. */
export function aggregate(rows: Row[]): Summary {
  const counts: Record<string, number> = {};
  let total = 0;
  for (const r of rows) {
    counts[r.kind] = (counts[r.kind] ?? 0) + 1;
    total = total + r.val;
  }
  const sorted: Record<string, number> = {};
  for (const k of Object.keys(counts).sort()) {
    sorted[k] = counts[k];
  }
  return { counts: sorted, total: total };
}

function main(): void {
  const data: string = fs.readFileSync(0, "utf8");
  const rows: Row[] = data
    .split("\\n")
    .filter((l) => l.trim() !== "")
    .map((l) => JSON.parse(l) as Row);
  process.stdout.write(JSON.stringify(aggregate(rows)) + "\\n");
}

import fs from "node:fs";
import { pathToFileURL } from "node:url";

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
'''

_HARNESS_TS = '''import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

export function runTests(solution) {
  const UNIT = __UNIT__;
  const CLI = __CLI__;
  // unit probes: aggregate on measured rows
  for (const [rows, want] of UNIT) {
    const got = JSON.stringify(solution.aggregate(rows));
    if (got !== JSON.stringify(want)) {
      throw new Error("UNIT-FAILED " + got + " want " + JSON.stringify(want));
    }
  }
  // CLI probes: byte-exact over the shipped solution.ts, twice (determinism)
  for (const [input, want] of CLI) {
    const a = execFileSync("node", ["--experimental-strip-types",
                                    "solution.ts"],
                           { input: input, encoding: "utf8", timeout: 20000 });
    const b = execFileSync("node", ["--experimental-strip-types",
                                    "solution.ts"],
                           { input: input, encoding: "utf8", timeout: 20000 });
    if (a !== want || b !== want || a !== b) {
      throw new Error("CLI-FAILED got " + JSON.stringify(a) + " want " +
                      JSON.stringify(want));
    }
  }
  // structural: no any, no nondeterminism, doc comment present
  const src = readFileSync("solution.ts", "utf8");
  if (/\\bany\\b/.test(src)) throw new Error("STRUCTURAL: any used");
  if (/Date\\.now|Math\\.random/.test(src)) {
    throw new Error("STRUCTURAL: nondeterminism");
  }
  if (!src.includes("/**")) throw new Error("STRUCTURAL: doc comment missing");
  console.log("__TESTS_PASSED__");
}
'''


def _ts_data(rng):
    kinds = ["web", "db", "api", "job"]
    rows = [{"id": i, "kind": rng.choice(kinds),
             "val": rng.randrange(-20, 50)}
            for i in range(rng.randrange(6, 12))]
    return rows, kinds


class TsJsonlPipelineFamily(Family):
    """TypeScript JSONL transformer: module + CLI under Node stripping."""
    NAME = "ts_jsonl_pipeline"
    LANGUAGE = "typescript"
    DOMAIN = "automation"
    DIFFICULTIES = ("expert",)
    SUPPORTS = ("architecture",)

    def generate(self, rng):
        rows, _kinds = _ts_data(rng)
        # measure golden outputs
        d = _tmpdir()
        try:
            _write(d, {"solution.ts": _GOLDEN_TS})
            cli_input = "\n".join(json.dumps(r) for r in rows) + "\n"
            rc, out, err = _run(["node", "--experimental-strip-types",
                                 "solution.ts"], d, stdin_text=cli_input)
        finally:
            _cleanup(d)
        if rc != 0:
            return None
        want_cli = out
        # unit: aggregate over the rows and a couple of subsets
        probe_js = ("import { aggregate } from './solution.ts';\n"
                    "const rows = __ROWS__;\n"
                    "console.log(JSON.stringify(aggregate(rows)));\n"
                    "console.log(JSON.stringify(aggregate(rows.slice(0, 3))));\n")
        probe_js = probe_js.replace("__ROWS__", json.dumps(rows))
        d2 = _tmpdir()
        try:
            _write(d2, {"solution.ts": _GOLDEN_TS, "_probe.mjs": probe_js})
            rc, out2, _e = _run(["node", "--experimental-strip-types",
                                 "_probe.mjs"], d2)
        finally:
            _cleanup(d2)
        if rc != 0 or len(out2.splitlines()) < 2:
            return None
        want_full = json.loads(out2.splitlines()[0])
        want_head = json.loads(out2.splitlines()[1])
        harness = _HARNESS_TS.replace(
            "__UNIT__", repr([[rows, want_full], [rows[:3], want_head]])).\
            replace("__CLI__", repr([[cli_input, want_cli]]))
        files = {"solution.ts": _GOLDEN_TS}
        # real gate through the standard TS executor conventions
        from validators.executors.ts_exec import verify_ts
        from generators.core import Candidate as _C
        probe_cand = _C(family=self.NAME, language="typescript",
                        domain="automation", difficulty="expert",
                        task="probe", expected_behavior="probe",
                        code=_GOLDEN_TS, tests=harness,
                        verify_method="executed")
        r = verify_ts(probe_cand, timeout=40)
        if not r.ok:
            return None
        task = (
            "Implement solution.ts: a JSONL transformer with a dual "
            "contract. AS A MODULE it exports aggregate(rows: Row[]): "
            "Summary where Row is {id: number, kind: string, val: number} "
            "and Summary is {counts: Record<string, number>, total: "
            "number}; counts must carry every observed kind with keys "
            "INSERTED IN SORTED ORDER (byte-exact JSON output depends on "
            "it) and total is the sum of vals. AS A CLI (node "
            "--experimental-strip-types solution.ts < input.jsonl) it "
            "reads all of stdin, aggregates the rows and writes exactly "
            "one JSON line. TypeScript must be erasable-only (no enums/"
            "namespaces), no any, no Date.now/Math.random, and aggregate "
            "carries a real doc comment. The harness runs unit probes, "
            "then the real CLI twice checking byte-exact output and "
            "determinism.")
        return Candidate(
            family=self.NAME, language="typescript", domain="automation",
            difficulty="expert", task=task,
            expected_behavior="unit probes + real CLI byte-exact and "
                              "deterministic under Node type-stripping",
            code=_GOLDEN_TS, tests=harness, verify_method="executed",
            notes={"explain": {
                "purpose": "dual module/CLI contract in one file",
                "approach": "insertion-ordered counts; fs.readFileSync(0)",
                "key_points": ["sorted key insertion = byte-exact JSON",
                               "import.meta.url vs argv[1] CLI detection",
                               "erasable TS only under type-stripping"],
                "big_o_time": "O(n) over rows",
                "big_o_space": "O(kinds)",
                "edge_cases": ["empty stdin yields empty counts + total 0",
                               "negative vals sum correctly"]}},
            tags=["typescript", "cli", "jsonl"],
            variant="jsonl|" + str(len(rows)),
            seed=rng.randrange(2 ** 31))

    def make_buggy(self, rng):
        cand = self.generate(rng)
        if cand is None:
            return None
        # buggy: counts keys in INSERTION order (not sorted) -> byte-exact
        # JSON unit probes must fail. Measured.
        buggy = _GOLDEN_TS.replace(
            "  for (const k of Object.keys(counts).sort()) {",
            "  for (const k of Object.keys(counts)) {")
        if buggy == _GOLDEN_TS:
            return None
        from validators.executors.ts_exec import verify_ts
        from generators.core import Candidate as _C
        probe_cand = _C(family=self.NAME, language="typescript",
                        domain="automation", difficulty="expert",
                        task=cand.task, expected_behavior=cand.expected_behavior,
                        code=buggy, tests=cand.tests,
                        verify_method="executed")
        r = verify_ts(probe_cand, timeout=40)
        if r.ok:
            return None
        buggy_cand = Candidate(
            family=self.NAME, language="typescript", domain="automation",
            difficulty="expert", task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=buggy, tests=cand.tests, verify_method="executed",
            notes={"bug_kind": "unsorted_keys",
                   "description": "counts in insertion order: the byte-"
                                  "exact JSON contract breaks",
                   "correct_code": _GOLDEN_TS},
            tags=cand.tags, variant=cand.variant + "|buggy",
            seed=rng.randrange(2 ** 31))
        return buggy_cand, {"kind": "unsorted_keys"}


register(globals(), InventoryOpsFamily)
register(globals(), LogPipelineFamily)
register(globals(), TsJsonlPipelineFamily)
