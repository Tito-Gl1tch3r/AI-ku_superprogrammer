"""v0.4.0 extension: crossover-mod engineering families (game dataset).

The 2026 crossover-mod wave (two games running at once, bridged in real
time) rests on two verifiable core skills, taught here with ORIGINAL code:

- game_crossover_bridge: a deterministic event bridge between two toy
  games - idempotent delivery keyed on (channel, seq), per-channel FIFO
  order, and a rate limit that DEFERS overflow instead of dropping it.
- game_state_scan: the recon step every crossover starts with - narrowing
  a state value to one address by intersecting candidate sets across
  snapshots, then freezing it.

Verification is REAL: the bridge runs against recorded event logs and the
scanner runs against a synthetic RAM image inside the sandbox.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register


def _mk_explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {"purpose": purpose, "approach": approach, "key_points": key_points,
            "big_o_time": big_o_time, "big_o_space": big_o_space,
            "edge_cases": edge_cases}


# ------------------------------------------------------------------- bridge
class GameCrossoverBridgeFamily(Family):
    """Deterministic event bridge between two toy games (crossover mods)."""
    NAME = "game_crossover_bridge"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    CHANS = ("actions", "chat")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["idempotency", "rate_defer", "channel_order"])
        rate = rng.randint(2, 3)
        rules = {"spell": "summon", "hit": "damage", "line": "shout", "move": "step"}
        kinds = list(rules)
        events = []
        if kind == "channel_order":
            # Deterministic interleave that FORCES the bug to diverge:
            # both channels overflow; chat's deferred seq is LOWER than
            # actions', so a global seq sort reorders what per-channel
            # draining keeps in channel order.
            seq = 0
            for _ in range(rate):
                for chan in ("actions", "chat"):
                    events.append({"seq": seq, "chan": chan,
                                   "kind": rng.choice(kinds),
                                   "val": rng.randrange(1, 9)})
                    seq += 1
            events.append({"seq": seq, "chan": "chat",
                           "kind": rng.choice(kinds), "val": rng.randrange(1, 9)})
            seq += 1
            events.append({"seq": seq, "chan": "actions",
                           "kind": rng.choice(kinds), "val": rng.randrange(1, 9)})
        else:
            seq = 0
            inserted_dupe = False
            per_chan = {"actions": 0, "chat": 0}
            for _ in range(rng.randint(6, 9)):
                chan = rng.choice(self.CHANS)
                events.append({"seq": seq, "chan": chan,
                               "kind": rng.choice(kinds),
                               "val": rng.randrange(1, 9)})
                per_chan[chan] += 1
                seq += 1
                if kind == "idempotency" and not inserted_dupe and rng.random() < 0.35:
                    events.append(dict(events[-1]))  # same (chan, seq) re-sent
                    inserted_dupe = True
            if kind == "idempotency" and not inserted_dupe:
                events.append(dict(events[rng.randrange(len(events))]))
            if kind == "rate_defer":
                # guarantee at least one channel overflows the window
                full = max(per_chan, key=lambda c: (per_chan[c], c))
                while per_chan[full] <= rate:
                    events.append({"seq": seq, "chan": full,
                                   "kind": rng.choice(kinds),
                                   "val": rng.randrange(1, 9)})
                    per_chan[full] += 1
                    seq += 1
        lit = repr(events)

        code = (
            f"RATE = {rate}          # max deliveries per channel per sync window\n"
            f"RULES = {rules!r}   # game-A kind -> game-B kind\n"
            f"EVENTS = {lit}\n\n\n"
            "def run_bridge(events=EVENTS):\n"
            "    \"\"\"Bridge game-A events into game B, deterministically.\n\n"
            "    - Idempotency: an event is delivered at most once, keyed on\n"
            "      (chan, seq); re-sent duplicates are swallowed.\n"
            "    - Order: each channel is FIFO by seq; channels are otherwise\n"
            "      independent (no global reordering).\n"
            "    - Rate limit: at most RATE deliveries per channel pass in the\n"
            "      window; the overflow is DEFERRED to a per-channel queue that\n"
            "      drains (still FIFO) after the main pass - never dropped.\n"
            "    Returns (b_state, log) where log holds every delivery as\n"
            "    (chan, seq, out_kind, val) in delivery order.\n"
            "    \"\"\"\n"
            "    seen = set()\n"
            "    deferred = {c: [] for c in (\"actions\", \"chat\")}\n"
            "    count = {c: 0 for c in (\"actions\", \"chat\")}\n"
            "    log = []\n"
            "    b_state = {\"inventory\": {}}\n"
            "\n"
            "    def deliver(ev):\n"
            "        out = RULES.get(ev[\"kind\"], \"noop\")\n"
            "        log.append((ev[\"chan\"], ev[\"seq\"], out, ev[\"val\"]))\n"
            "        b_state[\"inventory\"][out] = \\\n"
            "            b_state[\"inventory\"].get(out, 0) + ev[\"val\"]\n"
            "\n"
            "    for ev in events:\n"
            "        key = (ev[\"chan\"], ev[\"seq\"])\n"
            "        if key in seen:\n"
            "            continue\n"
            "        seen.add(key)\n"
            "        c = ev[\"chan\"]\n"
            "        if count[c] < RATE:\n"
            "            count[c] += 1\n"
            "            deliver(ev)\n"
            "        else:\n"
            "            deferred[c].append(ev)\n"
            "    for c in sorted(deferred):\n"
            "        for ev in deferred[c]:\n"
            "            deliver(ev)\n"
            "    return b_state, log\n"
        )

        # golden values computed here (the generator IS the reference impl)
        seen = set()
        deferred = {c: [] for c in self.CHANS}
        count = {c: 0 for c in self.CHANS}
        log = []
        b_state = {"inventory": {}}
        for ev in events:
            key = (ev["chan"], ev["seq"])
            if key in seen:
                continue
            seen.add(key)
            c = ev["chan"]
            if count[c] < rate:
                count[c] += 1
                out = rules.get(ev["kind"], "noop")
                log.append((c, ev["seq"], out, ev["val"]))
                b_state["inventory"][out] = b_state["inventory"].get(out, 0) + ev["val"]
            else:
                deferred[c].append(ev)
        for c in sorted(deferred):
            for ev in deferred[c]:
                out = rules.get(ev["kind"], "noop")
                log.append((c, ev["seq"], out, ev["val"]))
                b_state["inventory"][out] = b_state["inventory"].get(out, 0) + ev["val"]
        uniq = len(seen)
        dupes = len(events) - uniq
        deferred_total = sum(len(v) for v in deferred.values())
        inv_lit = repr(dict(sorted(b_state["inventory"].items())))
        log_lit = repr(log)
        counts_log = {}
        for c, _s, _k, _v in log:
            counts_log[c] = counts_log.get(c, 0) + 1

        if kind == "idempotency":
            expected = (
                f"Every event is delivered at most once: the {len(events)} incoming "
                f"events contain {dupes} duplicate re-sends, and only {uniq} unique "
                "(chan, seq) keys are delivered. B's inventory ends at "
                f"{inv_lit}.")
            tests = (
                "def run_tests():\n"
                "    b, log = run_bridge()\n"
                f"    assert len(log) == {uniq}\n"
                "    keys = [(c, s) for c, s, _k, _v in log]\n"
                "    assert len(keys) == len(set(keys))  # no duplicate delivery\n"
                f"    assert b['inventory'] == {inv_lit}\n"
                "    seqs = [s for _c, s, _k, _v in log]\n"
                "    assert sorted(seqs) == sorted(set(seqs))\n")
            explain = _mk_explain(
                "Idempotent event bridging between two game processes.",
                "Delivery is keyed on (channel, seq); a seen-set swallows "
                "re-sends so retries can never double-apply.",
                ["the key is the pair, not seq alone",
                 "swallowing happens before rate limiting",
                 "B's state must match the unique-key count"],
                "O(events)", "O(events)",
                ["duplicate after its channel filled the window",
                 "same seq on different channels (both delivered)",
                 "empty event list"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        if key in seen:\n            continue\n        seen.add(key)",
                    "        pass  # idempotency check removed")}
            bugs = {"no_idempotency": bug}

        elif kind == "rate_defer":
            expected = (
                f"The rate limit allows {rate} deliveries per channel in the "
                f"window; the {deferred_total} overflow events are deferred to a "
                "per-channel queue that drains FIFO after the main pass - "
                f"nothing is dropped and all {uniq} unique events land.")
            tests = (
                "def run_tests():\n"
                "    b, log = run_bridge()\n"
                f"    assert len(log) == {uniq}\n"
                "    counts = {}\n"
                "    for c, _s, _k, _v in log:\n"
                "        counts[c] = counts.get(c, 0) + 1\n"
                f"    assert counts == {repr(dict(sorted(counts_log.items())))}\n"
                f"    assert b['inventory'] == {inv_lit}\n"
                "    keys = [(c, s) for c, s, _k, _v in log]\n"
                "    assert len(keys) == len(set(keys))\n")
            explain = _mk_explain(
                "Rate-limited delivery with deferral, not drops.",
                "A per-channel counter gates the window; overflow waits in a "
                "FIFO queue drained after the main pass, preserving both "
                "delivery and order guarantees.",
                ["deferred is not lost: the window drains",
                 "per-channel queues keep channel order",
                 "counters are per channel, not global"],
                "O(events)", "O(deferred)",
                ["overflow on both channels", "rate larger than the input",
                 "deferred drain re-hitting the limit (it must not)"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    for c in sorted(deferred):\n"
                    "        for ev in deferred[c]:\n"
                    "            deliver(ev)",
                    "    pass  # deferred queue never drained (drops overflow)")}
            bugs = {"deferred_dropped": bug}

        else:  # channel_order
            expected = (
                "Deferred overflow drains per channel: each channel's own FIFO "
                f"order survives the window boundary. Of {uniq} unique events, "
                f"{deferred_total} were deferred; the log interleaves channels "
                "only where their queues actually interleave.")
            tests = (
                "def run_tests():\n"
                "    b, log = run_bridge()\n"
                f"    assert log == {log_lit}\n"
                "    for chan in ('actions', 'chat'):\n"
                "        seqs = [s for c, s, _k, _v in log if c == chan]\n"
                "        assert seqs == sorted(seqs)  # per-channel FIFO\n"
                f"    assert len(log) == {uniq}\n")
            explain = _mk_explain(
                "Per-channel FIFO through a rate-limited window.",
                "Channels own their queues; draining one channel never "
                "reorders another, and the golden log pins the exact "
                "interleaving.",
                ["sorted(deferred) gives a deterministic drain order",
                 "channel seq order is the invariant to test",
                 "the whole log is golden: any reorder fails"],
                "O(events)", "O(deferred)",
                ["single deferred channel", "interleaved overflow",
                 "channel with exactly RATE events"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    for c in sorted(deferred):\n"
                    "        for ev in deferred[c]:\n"
                    "            deliver(ev)",
                    "    flat = [ev for c in sorted(deferred) for ev in deferred[c]]\n"
                    "    flat.sort(key=lambda e: e[\"seq\"])\n"
                    "    for ev in flat:\n"
                    "        deliver(ev)")}
            bugs = {"global_seq_reorder": bug}

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(
                "Two toy games run side by side and a bridge forwards game-A "
                "events into game B in real time (the crossover-mod pattern). "
                f"Implement run_bridge() in Python: idempotent delivery keyed "
                f"on (chan, seq), per-channel FIFO order, and a rate limit of "
                f"{rate} deliveries per channel per window whose overflow is "
                "DEFERRED (never dropped). Deliveries translate kinds via "
                "RULES and accumulate into B's inventory; return (b_state, "
                "log) with the log in delivery order."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["game", "crossover", "bridge", kind], variant=kind,
            seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.py": cand.code})
        if buggy["solution.py"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="python", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.py"], tests=cand.tests,
                          verify_method="executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})


# -------------------------------------------------------------- state scan
class GameStateScanFamily(Family):
    """Two-snapshot delta scan narrows a state value to one address."""
    NAME = "game_state_scan"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["delta_scan", "freeze_patch"])
        size = 96
        addr = rng.randrange(8, size - 8)
        hp0 = rng.choice([100, 128, 200])
        hp1 = hp0 - rng.choice([15, 25, 35])
        freeze = 999
        # build two RAM snapshots; other bytes evolve too but avoid HP values
        def mk_ram(hp):
            ram = bytearray(rng.randrange(1, 250) for _ in range(size))
            for i in range(4):
                ram[addr + i] = 0  # write below, keep neighbours clean-ish
            ram[addr:addr + 4] = hp.to_bytes(4, "little")
            # sprinkle 1-2 decoy static occurrences of hp elsewhere
            for _ in range(rng.randint(1, 2)):
                off = rng.randrange(0, size - 4)
                if abs(off - addr) > 4:
                    ram[off:off + 4] = hp.to_bytes(4, "little")
            return ram

        ram0 = mk_ram(hp0)
        ram1 = mk_ram(hp1)
        lit0 = repr(bytes(ram0))
        lit1 = repr(bytes(ram1))

        code = (
            f"RAM0 = {lit0}\n"
            f"RAM1 = {lit1}\n"
            f"HP0 = {hp0}\n"
            f"HP1 = {hp1}\n\n\n"
            "def scan(ram, value):\n"
            "    \"\"\"Little-endian 4-byte scan: offsets where the dword == value.\"\"\"\n"
            "    hits = []\n"
            "    target = value.to_bytes(4, \"little\")\n"
            "    for i in range(len(ram) - 3):\n"
            "        if bytes(ram[i:i + 4]) == target:\n"
            "            hits.append(i)\n"
            "    return hits\n\n\n"
            "def narrow(ram0, ram1, v0, v1):\n"
            "    \"\"\"Intersect scan(ram0, v0) with scan(ram1, v1): the addresses\n"
            "    that held v0 AND now hold v1. This is how a live value is\n"
            "    separated from static decoys in two snapshots.\"\"\"\n"
            "    first = set(scan(ram0, v0))\n"
            "    return sorted(o for o in scan(ram1, v1) if o in first)\n\n\n"
            "def freeze(ram, off, value):\n"
            "    \"\"\"Patch the dword at off (the trainer-style write).\"\"\"\n"
            "    ram[off:off + 4] = value.to_bytes(4, \"little\")\n"
            "    return ram\n"
        )

        first0 = sorted(set(i for i in range(size - 3)
                            if bytes(ram0[i:i + 4]) == hp0.to_bytes(4, "little")))
        final = sorted(o for o in range(size - 3)
                       if bytes(ram1[o:o + 4]) == hp1.to_bytes(4, "little")
                       and o in set(first0))
        # guarantee a unique resolution: regenerate the scenario if not unique
        if len(final) != 1 or len(first0) < 2:
            return None
        addr = final[0]
        patched = bytearray(ram1)
        patched[addr:addr + 4] = freeze.to_bytes(4, "little")
        patch_hash = __import__("hashlib").sha256(bytes(patched)).hexdigest()
        first_lit = repr(first0)

        if kind == "delta_scan":
            expected = (
                f"Snapshot 0 has {len(first0)} candidates for HP={hp0} at {first_lit}; "
                f"intersecting with snapshot 1 (HP={hp1}) leaves exactly one "
                f"address: {addr}. The static decoys holding the same value in "
                "both snapshots are eliminated by the change, not by luck.")
            tests = (
                "def run_tests():\n"
                f"    assert scan(RAM0, HP0) == {first_lit}\n"
                f"    assert narrow(RAM0, RAM1, HP0, HP1) == [{addr}]\n"
                f"    assert scan(RAM1, HP1).count({addr}) >= 1\n"
                "    r = narrow(RAM0, RAM0, HP0, HP0)  # same snapshot: nothing narrows\n"
                "    assert len(r) >= 2  # the decoys survive without a change\n")
            explain = _mk_explain(
                "Narrowing a live value by intersecting two snapshot scans.",
                "scan() finds dword candidates; narrow() keeps only addresses "
                "that matched BOTH snapshots, so values that did not change "
                "between them (static decoys) drop out.",
                ["intersect candidate sets, never union them",
                 "little-endian dwords are the game's unit of state",
                 "a value that changed between snapshots is the live one"],
                "O(size) per scan", "O(candidates)",
                ["value did not change between snapshots",
                 "two live addresses changing identically",
                 "dword crossing the end of the buffer"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    first = set(scan(ram0, v0))\n"
                    "    return sorted(o for o in scan(ram1, v1) if o in first)",
                    "    first = set(scan(ram0, v0))\n"
                    "    return sorted(first | set(scan(ram1, v1)))  # union: wrong")}
            bugs = {"union_not_intersect": bug}

        else:  # freeze_patch
            expected = (
                f"narrow() resolves HP to the single address {addr}; freeze() "
                f"writes {freeze} there little-endian. The patched RAM image "
                f"hashes to {patch_hash[:16]}... and reading back the dword "
                f"returns {freeze}.")
            tests = (
                "def run_tests():\n"
                f"    off = narrow(RAM0, RAM1, HP0, HP1)[0]\n"
                f"    assert off == {addr}\n"
                "    ram = freeze(bytearray(RAM1), off, 999)\n"
                f"    assert int.from_bytes(ram[off:off + 4], 'little') == 999\n"
                "    import hashlib\n"
                f"    assert hashlib.sha256(bytes(ram)).hexdigest() == {patch_hash!r}\n"
                "    assert bytes(RAM1[off:off + 4]) == HP1.to_bytes(4, 'little')\n")
            explain = _mk_explain(
                "Trainer-style freeze after a confirmed narrow.",
                "Resolve the address by intersection, then patch the dword; "
                "the hash pins the entire patched image so no stray byte "
                "moves.",
                ["never write before the address is unique",
                 "little-endian write mirrors the scan",
                 "RAM1 must stay untouched (work on a copy)"],
                "O(size)", "O(1) extra",
                ["freezing an ambiguous address corrupts decoys",
                 "in-place patch of the snapshot (side effects)",
                 "value larger than 4 bytes"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "def freeze(ram, off, value):\n"
                    "    \"\"\"Patch the dword at off (the trainer-style write).\"\"\"\n"
                    "    ram[off:off + 4] = value.to_bytes(4, \"little\")\n"
                    "    return ram",
                    "def freeze(ram, off, value):\n"
                    "    \"\"\"Patch the dword at off (the trainer-style write).\"\"\"\n"
                    "    ram[off:off + 4] = value.to_bytes(4, \"big\")  # wrong endianness\n"
                    "    return ram")}
            bugs = {"big_endian_write": bug}

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(
                "A crossover mod must find the enemy HP inside a game's memory "
                "before bridging it (the recon step every real-time mod starts "
                "with). Implement scan(), narrow() and freeze() in Python over "
                f"the two little-endian snapshots RAM0/RAM1: two-snapshot "
                f"intersection must resolve HP ({hp0} -> {hp1}) to a single "
                "address, and freeze() patches that dword in place on a copy. "
                "Return the resolved offsets sorted."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["game", "crossover", "state_scan", kind], variant=kind,
            seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.py": cand.code})
        if buggy["solution.py"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="python", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.py"], tests=cand.tests,
                          verify_method="executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})


register(globals(), GameCrossoverBridgeFamily)
register(globals(), GameStateScanFamily)
