"""Dataset-4 families: AI-ku_superprogrammer_game_engineering.

Authorized reverse-engineering / modding / interoperability taught on
SYNTHETIC toy formats and open architectures only: binary pack/parse
round-trips, save serialization, sprite atlases, coordinate-system
conversion, a toy bytecode VM, plugin/event systems. Everything is
verified by executing pack->parse->compare round-trips in the sandbox.
No proprietary formats, no DRM, no online-game content.
"""
from __future__ import annotations

import random
import struct
import zlib

from ..core import Candidate, Family, FileSpec, register


def _blob_records(rng, count):
    return [(rng.randrange(1, 2 ** 16), rng.randint(-100, 100),
             round(rng.uniform(-9.5, 9.5), 3)) for _ in range(count)]


class GameFormatFamily(Family):
    NAME = "game_binary_formats"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["header_table", "tlv_save"])
        if kind == "header_table":
            magic = rng.choice([b"TOY1", b"GMBX", b"SPAK"])
            count = rng.randint(3, 8)
            records = _blob_records(rng, count)
            # f32 quantization: the file stores f32, so ground truth must be f32-rounded.
            records = [(uid, num, struct.unpack("<f", struct.pack("<f", real))[0])
                       for uid, num, real in records]
            blob = magic + struct.pack("<H", count)
            for uid, number, real in records:
                blob += struct.pack("<Hi f", uid, number, real)
            fn = rng.choice(["parse_container", "read_records"])
            code = (
                f"import struct\n\n"
                f"MAGIC = {magic!r}\n"
                f"HEADER = struct.Struct('<4sH')      # magic, record count\n"
                f"RECORD = struct.Struct('<Hi f')     # u16 id, i32 num, f32 real\n\n\n"
                f"def {fn}(blob):\n"
                f"    \"\"\"Parse the toy container: header + fixed-size records.\"\"\"\n"
                f"    magic, count = HEADER.unpack_from(blob, 0)\n"
                f"    if magic != MAGIC:\n"
                f"        raise ValueError('bad magic: ' + repr(magic))\n"
                f"    out = []\n"
                f"    offset = HEADER.size\n"
                f"    for _ in range(count):\n"
                f"        out.append(RECORD.unpack_from(blob, offset))\n"
                f"        offset += RECORD.size\n"
                f"    return out\n")
            tests = (
                f"import struct\n\n"
                f"def run_tests():\n"
                f"    blob = {blob!r}\n"
                f"    recs = {fn}(blob)\n"
                f"    assert len(recs) == {count}\n"
                f"    assert recs[0] == {records[0]!r}\n"
                f"    assert recs[-1][0] == {records[-1][0]}\n"
                f"    try:\n"
                f"        {fn}(b'NOPE' + blob[4:])\n"
                f"        assert False\n"
                f"    except ValueError:\n"
                f"        pass\n")
            expected = (f"Header (magic {magic.decode()} + u16 count) then {count} "
                        f"fixed-size records; little-endian; bad magic rejected.")
            explain = {"purpose": "Reconstruct a binary container format from its layout.",
                       "approach": "struct.Struct with explicit little-endian codes; walk offsets by record size.",
                       "key_points": ["endianness is part of the format (< = little)",
                                      "unpack_from avoids slicing copies",
                                      "magic validation is the first sanity gate"],
                       "big_o_time": "O(n) records", "big_o_space": "O(n)",
                       "edge_cases": ["bad magic", "truncated blob", "count mismatch"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "HEADER = struct.Struct('<4sH')", "HEADER = struct.Struct('>4sH')")}
            bugs = {"endianness_flipped": bug}
        else:  # tlv_save
            fields = [("hp", rng.randint(1, 99)), ("gold", rng.randint(0, 9999)),
                      ("x", round(rng.uniform(-50, 50), 2))]
            name = rng.choice(["player", "hero", "save01"])
            payload = name.encode() + b"\x00" + struct.pack("<H f", fields[0][1],
                                                            fields[1][1] / 100.0
                                                            if False else fields[2][1])
            body = b"SAVE" + struct.pack("<H", len(payload)) + payload
            checksum = zlib.crc32(body) & 0xFFFFFFFF
            blob = body + struct.pack("<I", checksum)
            code = (
                f"import struct\nimport zlib\n\n\n"
                f"def parse_save(blob):\n"
                f"    \"\"\"TLV-ish save: 'SAVE' + u16 length + payload + crc32 tail.\"\"\"\n"
                f"    if blob[:4] != b'SAVE':\n"
                f"        raise ValueError('not a save file')\n"
                f"    (length,) = struct.unpack_from('<H', blob, 4)\n"
                f"    payload = blob[6:6 + length]\n"
                f"    (stored,) = struct.unpack_from('<I', blob, 6 + length)\n"
                f"    if zlib.crc32(blob[:6 + length]) & 0xFFFFFFFF != stored:\n"
                f"        raise ValueError('checksum mismatch')\n"
                f"    name = payload.split(b'\\x00', 1)[0].decode()\n"
                f"    hp, x = struct.unpack_from('<H f', payload, len(name) + 1)\n"
                f"    return {{'name': name, 'hp': hp, 'x': round(x, 3)}}\n")
            tests = (
                f"def run_tests():\n"
                f"    blob = {blob!r}\n"
                f"    data = parse_save(blob)\n"
                f"    assert data['name'] == {name!r}\n"
                f"    assert data['hp'] == {fields[0][1]}\n"
                f"    corrupt = bytearray(blob)\n"
                f"    corrupt[8] ^= 0xFF\n"
                f"    try:\n"
                f"        parse_save(bytes(corrupt))\n"
                f"        assert False, 'checksum must fail'\n"
                f"    except ValueError:\n"
                f"        pass\n")
            expected = (f"Save blob parsed (name={name}, hp={fields[0][1]}, x="
                        f"{fields[2][1]}); corruption is caught by crc32.")
            explain = {"purpose": "Save-file serialization with integrity checking.",
                       "approach": "Length-prefixed payload + trailing crc32 over the prefix.",
                       "key_points": ["length prefix delimits variable payload",
                                      "crc32 catches bit flips",
                                      "checksum covers header+payload, not itself"],
                       "big_o_time": "O(n)", "big_o_space": "O(n)",
                       "edge_cases": ["bad tag", "corrupted payload", "short blob"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    if zlib.crc32(blob[:6 + length]) & 0xFFFFFFFF != stored:",
                    "    if False:\n        pass\n    if zlib.crc32(blob[:6 + length]) & 0xFFFFFFFF != stored and False:")}
            bugs = {"checksum_bypassed": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Reconstruct this SYNTHETIC toy format (educational reverse-engineering "
                  f"on data we generated ourselves - no proprietary formats). {expected} "
                  f"Implement the parser in Python; the tests round-trip the exact bytes."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["game", "formats", kind], variant=kind, seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
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


class GameCoordinatesFamily(Family):
    NAME = "game_coord_conversion"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["handedness", "quaternion"])
        x, y, z = (round(rng.uniform(-5, 5), 3) for _ in range(3))
        if kind == "handedness":
            code = (
                f"def rhs_to_lhs(pos):\n"
                f"    \"\"\"Right-handed Y-up -> left-handed Z-up: swap Y/Z, keep X.\"\"\"\n"
                f"    px, py, pz = pos\n"
                f"    return (px, pz, py)\n\n\n"
                f"def triangle_windings(rhs_indices):\n"
                f"    \"\"\"Handedness flip inverts face winding on every triangle.\"\"\"\n"
                f"    return [(a, c, b) for (a, b, c) in rhs_indices]\n")
            tests = (
                f"def run_tests():\n"
                f"    p = ({x}, {y}, {z})\n"
                f"    assert rhs_to_lhs(p) == ({x}, {z}, {y})\n"
                f"    assert rhs_to_lhs(rhs_to_lhs(p)) == p  # involution\n"
                f"    assert triangle_windings([(0, 1, 2)]) == [(0, 2, 1)]\n"
                f"    assert triangle_windings([]) == []\n")
            expected = (f"Axis remap Y-up->Z-up swaps Y/Z ({x},{y},{z} -> {x},{z},{y}); "
                        f"triangle winding flips; the map is an involution.")
            explain = {"purpose": "Coordinate-system conversion between engine conventions.",
                       "approach": "Swap the up/forward axes; flip triangle winding because handedness inverts orientation.",
                       "key_points": ["positions and winding must flip together",
                                      "the conversion is its own inverse (involution)",
                                      "forgetting winding turns models inside out"],
                       "big_o_time": "O(n) vertices", "big_o_space": "O(n)",
                       "edge_cases": ["zero vectors", "degenerate triangles", "double conversion"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    return [(a, c, b) for (a, b, c) in rhs_indices]",
                    "    return [(a, b, c) for (a, b, c) in rhs_indices]")}
            bugs = {"winding_not_flipped": bug}
        else:  # quaternion
            import math
            angle = round(rng.uniform(0.3, 2.0), 3)
            code = (
                f"import math\n\n\n"
                f"def quat_to_mat(q):\n"
                f"    \"\"\"Unit quaternion (w, x, y, z) -> 3x3 rotation matrix (row-major).\"\"\"\n"
                f"    w, x, y, z = q\n"
                f"    return [\n"
                f"        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],\n"
                f"        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],\n"
                f"        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],\n"
                f"    ]\n\n\n"
                f"def quat_about_axis(angle, axis):\n"
                f"    \"\"\"Unit quaternion for a rotation of `angle` radians about axis.\"\"\"\n"
                f"    n = math.sqrt(sum(a * a for a in axis))\n"
                f"    ax, ay, az = (a / n for a in axis)\n"
                f"    h = angle / 2.0\n"
                f"    return (math.cos(h), ax * math.sin(h), ay * math.sin(h), az * math.sin(h))\n")
            import math as _m
            h = angle / 2.0
            q = (_m.cos(h), 0.0, 0.0, _m.sin(h))
            tests = (
                f"def run_tests():\n"
                f"    import math\n"
                f"    q = quat_about_axis({angle}, (0, 0, 1))\n"
                f"    m = quat_to_mat(q)\n"
                f"    cos_a = math.cos({angle})\n"
                f"    assert abs(m[0][0] - cos_a) < 1e-6\n"
                f"    assert abs(m[0][1] + math.sin({angle})) < 1e-6\n"
                f"    assert abs(m[2][2] - 1.0) < 1e-6\n"
                f"    identity = quat_to_mat((1, 0, 0, 0))\n"
                f"    assert identity[0] == [1.0, 0.0, 0.0]\n")
            expected = (f"Unit quaternion about Z by {angle} rad maps to the standard "
                        f"rotation matrix; identity quaternion maps to I.")
            explain = {"purpose": "Quaternion->matrix conversion for animation pose math.",
                       "approach": "The standard closed form; build quats from axis+angle for tests.",
                       "key_points": ["quaternions avoid gimbal lock",
                                      "row-major vs column-major is a convention trap",
                                      "identity (1,0,0,0) must map to identity matrix"],
                       "big_o_time": "O(1)", "big_o_space": "O(1)",
                       "edge_cases": ["identity quat", "non-normalized axis normalized", "angle wrap"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        [2 * (x * y - z * w), 2 * (x * y + z * w), 2 * (x * z + y * w)],"
                    if False else
                    "        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],",
                    "        [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z + y * w)],")}
            bugs = {"matrix_transpose_error": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the coordinate/rotation math that cross-engine asset "
                  f"converters need (verified against synthetic data). {expected} Pure "
                  f"Python math; the tests check invariants like involution and identity."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["game", "math", kind], variant=kind, seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
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


class GameSpriteAtlasFamily(Family):
    NAME = "game_sprite_atlas"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing")

    def generate(self, rng: random.Random) -> Candidate:
        sw = rng.choice([2, 3, 4])
        count = rng.randint(2, 4)
        sprites = []
        for i in range(count):
            base = (i + 1) * 30
            sprites.append(tuple((base + j) % 256 for j in range(sw * sw)))
        atlas_w = sw * count
        code = (
            f"SPRITE_SIZE = {sw}\n\n\n"
            f"def pack_atlas(sprites):\n"
            f"    \"\"\"Shelf-pack 1xN: sprites side by side into one flat row.\"\"\"\n"
            f"    if not sprites:\n"
            f"        return []\n"
            f"    size = len(sprites[0])\n"
            f"    assert all(len(s) == size for s in sprites), 'uniform sprites only'\n"
            f"    atlas = []\n"
            f"    for s in sprites:\n"
            f"        atlas.extend(s)\n"
            f"    return atlas\n\n\n"
            f"def extract_sprite(atlas, index, sprite_size=SPRITE_SIZE):\n"
            f"    \"\"\"Slice one sprite back out of the packed row.\"\"\"\n"
            f"    start = index * sprite_size * sprite_size\n"
            f"    return atlas[start:start + sprite_size * sprite_size]\n")
        tests = (
            f"def run_tests():\n"
            f"    sprites = {list(sprites)!r}\n"
            f"    atlas = pack_atlas(sprites)\n"
            f"    assert len(atlas) == {atlas_w * sw}\n"
            f"    for i, s in enumerate(sprites):\n"
            f"        assert extract_sprite(atlas, i) == list(s)\n"
            f"    assert pack_atlas([]) == []\n")
        expected = (f"{count} sprites of {sw}x{sw} shelf-pack into one row of "
                    f"{atlas_w}x{sw}; extraction restores each sprite exactly.")
        explain = {"purpose": "Texture atlas packing and slicing (sprite-batch fundamentals).",
                  "approach": "Shelf packing in one row; index-based slicing back out.",
                  "key_points": ["atlas reduces draw calls (one texture bind)",
                                 "extraction must mirror packing arithmetic",
                                 "uniform sprite sizes simplify offsets"],
                  "big_o_time": "O(total pixels)", "big_o_space": "O(total pixels)",
                  "edge_cases": ["empty list", "index out of range", "non-uniform sizes rejected"]}
        def bug(files):
            return {"solution.py": files["solution.py"].replace(
                "    start = index * sprite_size * sprite_size",
                "    start = index * sprite_size")}
        bugs = {"stride_off_by_one": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement sprite-atlas packing/extraction over synthetic pixel data "
                  f"(legally ours; mirrors how real engines batch sprites). {expected} "
                  f"The tests verify the pack->extract round-trip pixel-exactly."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": "atlas", "_bug_fns": bugs},
            tags=["game", "assets", "atlas"], variant="atlas", seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
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


class GameBytecodeFamily(Family):
    """Toy ISA: assembler + interpreter + disassembler, all verified."""
    NAME = "game_script_vm"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        a = rng.randint(2, 9)
        b = rng.randint(2, 9)
        code = (
            "# Toy stack VM: LOAD n | ADD | MUL | DUP | SWAP | PRINT | HALT\n"
            "LOAD, ADD, MUL, DUP, SWAP, PRINT, HALT = 0x10, 0x20, 0x21, 0x22, 0x23, 0x30, 0xFF\n\n\n"
            "def asm(*ops):\n"
            "    \"\"\"Assemble (opcode, [arg]) tuples into a bytes program.\"\"\"\n"
            "    out = bytearray()\n"
            "    for op in ops:\n"
            "        opcode = op[0]\n"
            "        out.append(opcode)\n"
            "        if opcode == LOAD:\n"
            "            out += struct_pack_i32(op[1])\n"
            "    return bytes(out)\n\n\n"
            "def struct_pack_i32(v):\n"
            "    import struct\n"
            "    return struct.pack('<i', v)\n\n\n"
            "def run(program, trace=False):\n"
            "    \"\"\"Execute the toy VM; PRINT appends to output list.\"\"\"\n"
            "    stack, out, pc = [], [], 0\n"
            "    while pc < len(program):\n"
            "        op = program[pc]\n"
            "        if op == LOAD:\n"
            "            import struct\n"
            "            stack.append(struct.unpack_from('<i', program, pc + 1)[0])\n"
            "            pc += 5\n"
            "        elif op == ADD:\n"
            "            b, a2 = stack.pop(), stack.pop()\n"
            "            stack.append(a2 + b)\n"
            "            pc += 1\n"
            "        elif op == MUL:\n"
            "            b, a2 = stack.pop(), stack.pop()\n"
            "            stack.append(a2 * b)\n"
            "            pc += 1\n"
            "        elif op == DUP:\n"
            "            stack.append(stack[-1])\n"
            "            pc += 1\n"
            "        elif op == SWAP:\n"
            "            stack[-1], stack[-2] = stack[-2], stack[-1]\n"
            "            pc += 1\n"
            "        elif op == PRINT:\n"
            "            out.append(stack[-1])\n"
            "            pc += 1\n"
            "        elif op == HALT:\n"
            "            break\n"
            "        else:\n"
            "            raise ValueError(f'bad opcode 0x{op:02X} at {pc}')\n"
            "    return out\n")
        tests = (
            f"def run_tests():\n"
            f"    prog = asm((LOAD, {a}), (LOAD, {b}), (MUL,), (PRINT,), (HALT,))\n"
            f"    assert run(prog) == [{a * b}]\n"
            f"    prog2 = asm((LOAD, {a}), (LOAD, {b}), (ADD,), (PRINT,), (HALT,))\n"
            f"    assert run(prog2) == [{a + b}]\n"
            f"    try:\n"
            f"        run(b'\\x77')\n"
            f"        assert False, 'bad opcode must raise'\n"
            f"    except ValueError:\n"
            f"        pass\n")
        expected = (f"Program (LOAD {a}; LOAD {b}; MUL; PRINT) outputs [{a * b}]; "
                    f"unknown opcodes raise with the faulting pc.")
        explain = {"purpose": "Scripting-system fundamentals: bytecode assembler + interpreter.",
                   "approach": "Fixed-width opcodes with inline i32 operands; dispatch loop with pc.",
                   "key_points": ["operand width drives pc advancement",
                                  "stack discipline for arithmetic",
                                  "unknown opcode = controlled error, not UB"],
                   "big_o_time": "O(instructions)", "big_o_space": "O(stack)",
                   "edge_cases": ["unknown opcode", "stack underflow guard", "HALT early"]}
        def bug(files):
            return {"solution.py": files["solution.py"].replace(
                "            pc += 5", "            pc += 4")}
        bugs = {"operand_stride_wrong": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the toy scripting VM used by the (fictional, synthetic) engine "
                  f"'ToyEngine': an assembler for the opcode set and the dispatch interpreter. "
                  f"{expected} This is educational binary/executable reasoning on our own ISA - "
                  f"no real game binaries involved."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": "vm", "_bug_fns": bugs},
            tags=["game", "vm", "bytecode"], variant="vm", seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
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


class GamePluginFamily(Family):
    NAME = "game_mod_plugin_system"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        mods = rng.sample(["core-fix", "hd-ui", "weather+", "auto-save"], rng.randint(2, 3))
        code = (
            "class EventBus:\n"
            "    \"\"\"Minimal plugin event bus with ordered handlers (modding API).\"\"\"\n\n"
            "    def __init__(self):\n"
            "        self._handlers = {}\n\n"
            "    def on(self, event, handler, priority=0):\n"
            "        self._handlers.setdefault(event, []).append((priority, handler))\n"
            "        self._handlers[event].sort(key=lambda t: -t[0])\n\n"
            "    def emit(self, event, payload):\n"
            "        for _prio, handler in self._handlers.get(event, []):\n"
            "            payload = handler(payload) or payload\n"
            "        return payload\n\n\n"
            "def semver_ok(requires, provides):\n"
            "    \"\"\"Compatibility gate: major must match, provides minor >= requires.\"\"\"\n"
            "    r_maj, r_min, _ = requires\n"
            "    p_maj, p_min, _ = provides\n"
            "    return r_maj == p_maj and p_min >= r_min\n")
        tests = (
            "def run_tests():\n"
            "    bus = EventBus()\n"
            "    order = []\n"
            "    bus.on('frame', lambda p: (order.append('high'), p + 1)[1], priority=10)\n"
            "    bus.on('frame', lambda p: (order.append('low'), p * 2)[1], priority=1)\n"
            "    assert bus.emit('frame', 3) == 8\n"
            "    assert order == ['high', 'low']\n"
            "    assert semver_ok((2, 1, 0), (2, 3, 0))\n"
            "    assert not semver_ok((2, 1, 0), (2, 0, 0))\n"
            "    assert not semver_ok((3, 0, 0), (2, 9, 9))\n")
        expected = (f"Handlers run in priority order with payload chaining; semver gate "
                    f"accepts major-match and minor >= required ({mods} as plugin names).")
        explain = {"purpose": "Plugin/mod architecture primitives: event bus + compat gate.",
                   "approach": "Priority-sorted handler lists; payload flows through the chain; semver-lite for deps.",
                   "key_points": ["mods extend via events, not forks",
                                  "priority ordering must be deterministic",
                                  "version gates prevent incompatible loads"],
                   "big_o_time": "O(h log h) per registration", "big_o_space": "O(h)",
                   "edge_cases": ["no handlers", "handler returning None keeps payload", "major mismatch"]}
        def bug(files):
            return {"solution.py": files["solution.py"].replace(
                "        self._handlers[event].sort(key=lambda t: -t[0])",
                "        self._handlers[event].sort(key=lambda t: t[0])")}
        bugs = {"priority_order_reversed": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement the modding/plugin primitives for an open, officially-extensible "
                  f"engine style: an ordered event bus and a semantic-version compatibility "
                  f"gate. {expected} This models SUPPORTED modding surfaces (no bypassing, "
                  f"no anti-cheat, no online play)."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": "plugins", "_bug_fns": bugs},
            tags=["game", "modding", "plugins"], variant="plugins",
            seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
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


class GameInteropProjectFamily(Family):
    """Cross-engine converter project: SOURCE format -> TARGET format."""
    NAME = "game_interop_project"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation", "debugging")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        pkgname = rng.choice(["meshbridge", "animporter", "scenelink"])
        verts = [(round(rng.uniform(-5, 5), 3), round(rng.uniform(-5, 5), 3),
                  round(rng.uniform(-5, 5), 3)) for _ in range(rng.randint(3, 6))]
        lib = (
            '"""Source format: right-handed Y-up triangles (engine A)."""\n\n'
            f'VERTS = {verts!r}\n'
            'TRIS = [(0, 1, 2)]\n')
        conv = (
            '"""Convert source -> target: left-handed Z-up, cm units, recentered."""\n\n'
            f'from {pkgname}.source import VERTS, TRIS\n\n'
            'SCALE_CM = 100.0\n\n\n'
            'def convert_vertex(v):\n'
            '    x, y, z = v\n'
            '    return (x * SCALE_CM, z * SCALE_CM, y * SCALE_CM)\n\n\n'
            'def convert_mesh():\n'
            '    return [convert_vertex(v) for v in VERTS], TRIS\n')
        initc = f'from .source import VERTS, TRIS\nfrom .convert import convert_mesh, convert_vertex\n\n__all__ = ["VERTS", "TRIS", "convert_mesh", "convert_vertex"]\n'
        readme = (f"# {pkgname}\n\nCross-engine mesh conversion project (synthetic "
                  f"formats, educational).\n\n"
                  f"- `source.py`: engine A data (RH, Y-up, meters)\n"
                  f"- `convert.py`: transform to engine B (LH, Z-up, centimeters)\n"
                  f"- `tests/`: round-trip + invariant checks\n\n"
                  f"Run: `python -m unittest discover -s tests`\n")
        tests = (
            "import sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
            f"from {pkgname}.source import VERTS\n"
            f"from {pkgname}.convert import convert_vertex, convert_mesh\n\n\n"
            "class TestInterop(unittest.TestCase):\n"
            "    def test_axis_remap(self):\n"
            f"        v0 = VERTS[0]\n"
            f"        self.assertEqual(convert_vertex(v0),\n"
            f"                         (v0[0] * 100.0, v0[2] * 100.0, v0[1] * 100.0))\n\n"
            "    def test_units_scaled(self):\n"
            "        out, _tris = convert_mesh()\n"
            "        self.assertTrue(all(abs(c) <= 500.0 + 1e-6 for v in out for c in v))\n\n"
            "    def test_topology_preserved(self):\n"
            "        _out, tris = convert_mesh()\n"
            "        self.assertEqual(tris, [(0, 1, 2)])\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n")
        files = [FileSpec(f"{pkgname}/__init__.py", initc),
                 FileSpec(f"{pkgname}/source.py", lib),
                 FileSpec(f"{pkgname}/convert.py", conv),
                 FileSpec("README.md", readme),
                 FileSpec("tests/test_convert.py", tests)]
        expected = (f"Vertices remap (x, y, z) -> (x, z, y) * 100 cm and topology is "
                    f"preserved ({len(verts)} verts, 1 triangle).")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Build the multi-file cross-engine converter project in README.md: read "
                  f"engine-A synthetic mesh data and emit engine-B format with correct axis "
                  f"remap, unit scaling and preserved topology. {expected} The unittest suite "
                  f"must pass. This teaches the general reconstruction pipeline (inspect -> "
                  f"extract -> transform -> verify) on data we own."),
            expected_behavior=expected, files=files, entry=f"{pkgname}/__init__.py",
            tests=tests, verify_method="executed", is_project=True,
            notes={"explain": {"purpose": expected,
                               "approach": "Layered converter: source module, transform module, invariant tests.",
                               "key_points": ["axis remap + winding are a pair",
                                              "unit scaling (m->cm) multiplies every coordinate",
                                              "topology (indices) must survive untouched"],
                               "big_o_time": "O(V)", "big_o_space": "O(V)",
                               "edge_cases": ["negative coordinates", "scale factor errors", "topology drift"]}},
            tags=["game", "interop", "project"], variant="mesh_convert",
            seed=rng.randrange(2**31))


register(globals(), GameFormatFamily)
register(globals(), GameCoordinatesFamily)
register(globals(), GameSpriteAtlasFamily)
register(globals(), GameBytecodeFamily)
register(globals(), GamePluginFamily)
register(globals(), GameInteropProjectFamily)


def _game_plugin_review_variant(self, rng: random.Random):
    code = (
        "class EventBus:\n"
        "    def __init__(self):\n"
        "        self._handlers = {}\n\n"
        "    def on(self, event, handler, priority=0, log=[]):\n"
        "        log.append((event, handler.__name__))\n"
        "        self._handlers.setdefault(event, []).append((priority, handler))\n\n"
        "    def emit(self, event, payload):\n"
        "        try:\n"
        "            for _prio, handler in self._handlers.get(event, []):\n"
        "                payload = handler(payload) or payload\n"
        "        except Exception:\n"
        "            pass\n"
        "        return payload\n")
    cand = Candidate(
        family=self.NAME, language="python", domain=self.DOMAIN,
        difficulty="intermediate",
        task=("Review this mod-loader event bus (it currently 'works' for the happy path). "
              "Identify the defects an experienced reviewer would block, and the ones they "
              "would merely flag. This models an officially-supported modding surface."),
        expected_behavior="Happy path works; planted issues affect robustness and debuggability.",
        code=code,
        tests=("def run_tests():\n"
               "    bus = EventBus()\n"
               "    bus.on('hit', lambda p: p + 1)\n"
               "    assert bus.emit('hit', 1) == 2\n"
               "    assert bus.emit('missing', 7) == 7\n"),
        verify_method="executed",
        notes={"issues": [
            {"kind": "mutable default argument (log=[])",
             "severity": "high",
             "why": "the default list is shared across ALL calls, so registration history silently leaks between bus instances.",
             "better": "default None and create a fresh list inside."},
            {"kind": "bare except: pass around emit",
             "severity": "high",
             "why": "a crashing mod handler is swallowed silently - exactly how mod conflicts become undebuggable.",
             "better": "catch, log the failing handler + event, and decide an isolation policy (skip vs fail-fast)."},
            {"kind": "no handler priority sort",
             "severity": "medium",
             "why": "emit order follows insertion; mods cannot declare load order and results become registration-order dependent.",
             "better": "sort by priority (stable) at registration time."},
            {"kind": "handler returning None ambiguous",
             "severity": "low",
             "why": "`handler(payload) or payload` conflates 'no change' with 'falsy new payload' (e.g. 0).",
             "better": "document the contract or use a sentinel/return-tuple protocol."},
        ], "explain": {"purpose": "Review fixture: plugin bus with classic Python traps.",
                       "approach": "Plant mutable-default, silent-except, ordering and contract issues.",
                       "key_points": ["mutable defaults are shared state",
                                      "silent exception swallowing kills mod debuggability",
                                      "ordering must be explicit"],
                       "big_o_time": "O(h) per emit", "big_o_space": "O(h)",
                       "edge_cases": ["handler crash", "falsy payloads", "duplicate registration"]}},
        tags=["game", "review"], variant="review", seed=rng.randrange(2**31))
    return cand, cand.notes["issues"]


GamePluginFamily.review_variant = _game_plugin_review_variant
