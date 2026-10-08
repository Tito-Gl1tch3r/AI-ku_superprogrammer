"""Superprogrammer extension: number bases and Linux permission bits.

Teaches the base-literacy a systems programmer needs every day:
binary / octal / hexadecimal conversion with canonical padding, the
chmod symbolic <-> octal translation including setuid/setgid/sticky bits,
umask arithmetic, and flag-style bit operations on mode words.

Every candidate is verified by real execution: the reference values are
computed here with independent code (integer arithmetic / manual digit
loops) and the bundled test suite pins them exactly.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register

_DIGITS = "0123456789abcdef"

_RWX_INDEX = {"r": 4, "w": 2, "x": 1}

_SPECIAL_POS = {3: "setuid", 6: "setgid", 9: "sticky"}  # indices in 9-char sym


_EXEC_CHARS = ("x", "s", "t")


def _sym_to_mode_clean(sym: str) -> int:
    """Reference implementation (single pass, no legacy branches)."""
    if len(sym) != 9:
        raise ValueError("symbolic permission must be 9 characters")
    mode = 0
    for tri in range(3):
        chunk = sym[tri * 3:tri * 3 + 3]
        val = ((4 if chunk[0] == "r" else 0)
               + (2 if chunk[1] == "w" else 0)
               + (1 if chunk[2] in _EXEC_CHARS else 0))
        mode |= val << ((2 - tri) * 3)
    if sym[2] in ("s", "S"):
        mode |= 0o4000
    if sym[5] in ("s", "S"):
        mode |= 0o2000
    if sym[8] in ("t", "T"):
        mode |= 0o1000
    return mode


def _mode_to_sym(mode: int) -> str:
    """Reference: 0o4755 -> 'rwsr-xr-x'."""
    if not 0 <= mode <= 0o7777:
        raise ValueError("mode out of range")
    permlow = mode & 0o777
    out = []
    for shift in (6, 3, 0):
        tri = (permlow >> shift) & 7
        r = "r" if tri & 4 else "-"
        w = "w" if tri & 2 else "-"
        x = "x" if tri & 1 else "-"
        out.append(r + w + x)
    sym = "".join(out)
    chars = list(sym)
    if mode & 0o4000:
        chars[2] = "s" if permlow & 0o100 else "S"
    if mode & 0o2000:
        chars[5] = "s" if permlow & 0o10 else "S"
    if mode & 0o1000:
        chars[8] = "t" if permlow & 0o1 else "T"
    return "".join(chars)


def _to_base(value: int, base: int, width: int = 0) -> str:
    """Reference: manual digit loop for any base 2..16, zero padded."""
    if base < 2 or base > 16:
        raise ValueError("base out of range")
    if value < 0:
        raise ValueError("negative values not supported")
    if value == 0:
        digits = "0"
    else:
        chunks = []
        while value:
            chunks.append(_DIGITS[value % base])
            value //= base
        digits = "".join(reversed(chunks))
    return digits.rjust(width, "0")


_PARSE_BASE = {2: "0b", 8: "0o", 16: "0x"}


def _parse_bases(text: str, base: int) -> int:
    t = text.strip().lower()
    prefix = _PARSE_BASE.get(base)
    if prefix and t.startswith(prefix):
        t = t[len(prefix):]
    if any(c not in _DIGITS[:base] for c in t) or not t:
        raise ValueError(f"invalid base-{base} literal")
    return int(t, base)


class NumberBasesFamily(Family):
    NAME = "py_number_bases"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "trace", "debugging", "testing", "code_review")

    KINDS = ("chmod_symbolic", "umask_apply", "base_convert", "mode_bits")

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _random_symbolic(rng: random.Random, with_special: bool) -> str:
        specials = ["rwxr-xr-x", "rw-r--r--", "rwxr-x---", "rw-rw----",
                    "r--r--r--", "rwx------", "rwxrw-r-x", "r-xr-xr-x",
                    "rw-r-----", "rwxrwsr-x", "rwsrw-r--", "rwxr-sr-x",
                    "rwxrwxrwt", "rwxr-xr-t", "rwxr-sr-t", "rwSr--r--",
                    "rwxrwsrwt", "rwxr-sr-T"]
        if with_special:
            return rng.choice(specials)
        return rng.choice(specials[:10])

    def _mk_chmod(self, rng: random.Random) -> Candidate:
        with_special = rng.random() < 0.55
        sym = self._random_symbolic(rng, with_special)
        mode = _sym_to_mode_clean(sym)
        back = _mode_to_sym(mode)
        fn_a, fn_b = "sym_to_mode", "mode_to_sym"
        code = (
            "def sym_to_mode(sym: str) -> int:\n"
            "    \"\"\"Translate a 9-char chmod symbolic string to a mode int.\n\n"
            "    Handles setuid/setgid/sticky: 's'/'t' imply the exec bit on\n"
            "    their triplet, 'S'/'T' mean the special bit without exec.\n"
            "    \"\"\"\n"
            "    if len(sym) != 9:\n"
            "        raise ValueError(\"symbolic permission must be 9 chars\")\n"
            "    bits = {\"r\": 4, \"w\": 2, \"x\": 1, \"s\": 1, \"t\": 1}\n"
            "    mode = 0\n"
            "    for tri in range(3):\n"
            "        chunk = sym[tri * 3:tri * 3 + 3]\n"
            "        val = bits.get(chunk[0], 0) + bits.get(chunk[1], 0) \\\n"
            "            + bits.get(chunk[2], 0)\n"
            "        mode |= val << ((2 - tri) * 3)\n"
            "    if sym[2] in (\"s\", \"S\"):\n"
            "        mode |= 0o4000\n"
            "    if sym[5] in (\"s\", \"S\"):\n"
            "        mode |= 0o2000\n"
            "    if sym[8] in (\"t\", \"T\"):\n"
            "        mode |= 0o1000\n"
            "    return mode\n"
            "\n"
            "\n"
            "def mode_to_sym(mode: int) -> str:\n"
            "    \"\"\"Translate a mode int (<= 0o7777) to its 9-char symbolic form.\"\"\"\n"
            "    if not 0 <= mode <= 0o7777:\n"
            "        raise ValueError(\"mode out of range\")\n"
            "    parts = []\n"
            "    for shift in (6, 3, 0):\n"
            "        tri = (mode >> shift) & 7\n"
            "        parts.append((\"r\" if tri & 4 else \"-\")\n"
            "                     + (\"w\" if tri & 2 else \"-\")\n"
            "                     + (\"x\" if tri & 1 else \"-\"))\n"
            "    sym = list(\"\".join(parts))\n"
            "    if mode & 0o4000:\n"
            "        sym[2] = \"s\" if mode & 0o100 else \"S\"\n"
            "    if mode & 0o2000:\n"
            "        sym[5] = \"s\" if mode & 0o010 else \"S\"\n"
            "    if mode & 0o1000:\n"
            "        sym[8] = \"t\" if mode & 0o001 else \"T\"\n"
            "    return \"\".join(sym)\n"
        )
        extra_syms = [s for s in ("rwxrwxrwx", "r--------", "rw-rw-r--",
                                  "rwsrwsrwt", "r-xr-x--T") if s != sym]
        probe = rng.choice(extra_syms)
        probe_mode = _sym_to_mode_clean(probe)
        tests = (
            f"def run_tests():\n"
            f"    assert sym_to_mode({sym!r}) == {mode:#o}\n"
            f"    assert mode_to_sym({mode:#o}) == {back!r}\n"
            f"    assert sym_to_mode({probe!r}) == {probe_mode:#o}\n"
            f"    for m in (0o755, 0o644, 0o700, 0o4755, 0o2750, 0o1777, 0o000):\n"
            f"        assert sym_to_mode(mode_to_sym(m)) == m\n"
            f"    try:\n"
            f"        sym_to_mode('rwx')\n"
            f"    except ValueError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('bad length must raise')\n"
        )
        task = (
            "Linux stores file permissions as a 12-bit mode word: 3 bits per "
            "class (owner, group, other) plus the setuid (0o4000), setgid "
            "(0o2000) and sticky (0o1000) bits. Implement two translators in "
            "Python: sym_to_mode(sym) that parses the 9-character symbolic "
            "string (e.g. 'rwsr-xr-t') into the mode integer, and "
            "mode_to_sym(mode) that renders the mode back to the symbolic "
            "form. In a symbolic string, 's' in the owner or group exec slot "
            "means the special bit AND the exec bit for that class; 't' in "
            "the other exec slot means the sticky bit AND other-exec; 'S' "
            "and 'T' mean the special bit WITHOUT exec. Validate the input "
            "length and the mode range with ValueError."
        )
        expected = (f"sym_to_mode({sym!r}) == {mode:#o} and "
                    f"mode_to_sym({mode:#o}) == {back!r}; round-trips hold "
                    f"for every mode with or without special bits.")
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty=rng.choice(["intermediate", "advanced"]),
            task=task, expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Bidirectional chmod symbolic/mode translation "
                           "including the 3 special bits",
                "approach": "3 bits per class assembled with shifts; special "
                            "bits detected from the exec slots afterwards",
                "key_points": ["owner bits live at shift 6, group at 3, other at 0",
                               "setuid/setgid/sticky are bits 12/11/10 of the word",
                               "'s' and 't' imply exec, 'S' and 'T' do not",
                               "round-trip property catches asymmetric bugs"],
                "big_o_time": "O(1) (fixed 9 characters)",
                "big_o_space": "O(1)",
                "edge_cases": [f"{probe!r} -> {probe_mode:#o}",
                               "mode 0o000 -> '---------'",
                               "capital S/T: special bit without exec"]}},
            tags=["systems", "permissions", "chmod", "octal"],
            variant=f"chmod|{sym}", seed=rng.randrange(2**31))

    def _mk_umask(self, rng: random.Random) -> Candidate:
        umask = rng.choice(["022", "027", "077", "002", "017", "027", "007",
                            "022", "123", "077"])
        u = int(umask, 8)
        file_mode = 0o666 & ~u
        dir_mode = 0o777 & ~u
        code = (
            "def resulting_modes(umask: str) -> tuple[int, int]:\n"
            "    \"\"\"Apply a numeric umask to the process defaults.\n\n"
            "    The kernel creates files with 0o666 and directories with\n"
            "    0o777, then clears every bit set in the umask (bitwise AND\n"
            "    with the complement). Returns (file_mode, dir_mode).\n"
            "    \"\"\"\n"
            "    u = int(umask, 8)\n"
            "    if not 0 <= u <= 0o777:\n"
            "        raise ValueError(\"umask out of range\")\n"
            "    return 0o666 & ~u, 0o777 & ~u\n"
        )
        alt = rng.choice(["044", "034", "057", "070", "011"])
        alt_f, alt_d = 0o666 & ~int(alt, 8), 0o777 & ~int(alt, 8)
        tests = (
            f"def run_tests():\n"
            f"    assert resulting_modes({umask!r}) == ({file_mode:#o}, {dir_mode:#o})\n"
            f"    assert resulting_modes({alt!r}) == ({alt_f:#o}, {alt_d:#o})\n"
            f"    assert resulting_modes('000') == (0o666, 0o777)\n"
            f"    assert resulting_modes('777') == (0, 0)\n"
            f"    try:\n"
            f"        resulting_modes('1000')\n"
            f"    except ValueError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('out-of-range must raise')\n"
        )
        task = (
            "On Linux the umask shapes the permissions of every file a "
            "process creates. The kernel starts from the defaults 0o666 for "
            "files and 0o777 for directories and clears each bit that is set "
            "in the umask (a bitwise AND with the complement, never a plain "
            "subtraction). Implement resulting_modes(umask) in Python: it "
            "takes the umask as a numeric octal string such as '027', "
            "validates it fits in 9 permission bits (raise ValueError "
            "otherwise), and returns the tuple (file_mode, dir_mode) as "
            "integers."
        )
        expected = (f"resulting_modes({umask!r}) == ({file_mode:#o}, {dir_mode:#o})")
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty=rng.choice(["beginner", "intermediate"]),
            task=task, expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Predict the permissions new files and directories get",
                "approach": "mask = base & ~umask applied to 0o666 / 0o777",
                "key_points": ["umask clears bits, it never grants them",
                               "subtraction and masking differ when bits overlap",
                               "directories keep the x bits files lose by default"],
                "big_o_time": "O(1)", "big_o_space": "O(1)",
                "edge_cases": ["umask '000' keeps the full defaults",
                               "umask '777' yields mode 0 for both"]}},
            tags=["systems", "permissions", "umask", "octal"],
            variant=f"umask|{umask}", seed=rng.randrange(2**31))

    def _mk_base_convert(self, rng: random.Random) -> Candidate:
        src, dst = rng.sample([2, 8, 10, 16], 2)
        value = rng.randrange(0, 1 << rng.choice([8, 12, 16, 20]))
        width = rng.choice([0, 8, 16])
        width = max(width, len(_to_base(value, dst)) if rng.random() < 0.4 else width)
        out = _to_base(value, dst, width)
        literal = _to_base(value, src)
        code = (
            "def convert(value: str, src_base: int, dst_base: int,\n"
            "            width: int = 0) -> str:\n"
            "    \"\"\"Convert a non-negative literal between bases 2..16.\n\n"
            "    Accepts the 0b / 0o / 0x prefixes (case-insensitive) when\n"
            "    they match src_base. Output uses lowercase digits and is\n"
            "    zero-padded on the left up to `width` characters.\n"
            "    \"\"\"\n"
            "    if src_base < 2 or src_base > 16 or dst_base < 2 or dst_base > 16:\n"
            "        raise ValueError(\"bases must be within 2..16\")\n"
            "    if width < 0:\n"
            "        raise ValueError(\"width must be non-negative\")\n"
            "    text = value.strip().lower()\n"
            "    prefix = {2: \"0b\", 8: \"0o\", 16: \"0x\"}.get(src_base)\n"
            "    if prefix and text.startswith(prefix):\n"
            "        text = text[len(prefix):]\n"
            "    digits = \"0123456789abcdef\"[:src_base]\n"
            "    if not text or any(c not in digits for c in text):\n"
            "        raise ValueError(\"invalid literal for the source base\")\n"
            "    number = int(text, src_base)\n"
            "    out_digits = \"0123456789abcdef\"[:dst_base]\n"
            "    if number == 0:\n"
            "        result = \"0\"\n"
            "    else:\n"
            "        stack = []\n"
            "        while number:\n"
            "            number, rem = divmod(number, dst_base)\n"
            "            stack.append(out_digits[rem])\n"
            "        result = \"\".join(reversed(stack))\n"
            "    return result.rjust(width, \"0\")\n"
        )
        other = rng.randrange(0, 1 << 16)
        other_lit = _to_base(other, src)
        other_out = _to_base(other, dst, width)
        pref = {2: "0b", 8: "0o", 16: "0x"}.get(src)
        out_plain = _to_base(value, dst)
        prefix_case = (
            f"    assert convert({(pref + literal)!r}, {src}, {dst}) == {out_plain!r}\n"
            if pref else "")
        tests = (
            f"def run_tests():\n"
            f"    assert convert({literal!r}, {src}, {dst}, {width}) == {out!r}\n"
            f"{prefix_case}"
            f"    assert convert({other_lit!r}, {src}, {dst}, {width}) == {other_out!r}\n"
            f"    assert convert('0', {src}, {dst}) == '0'\n"
            f"    assert convert('0', {src}, {dst}, 4) == '0000'\n"
            f"    try:\n"
            f"        convert('zz', {src}, {dst})\n"
            f"    except ValueError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('invalid digit must raise')\n"
        )
        task = (
            "Implement a general integer base converter in Python. "
            "convert(value, src_base, dst_base, width=0) parses a "
            "non-negative literal written in src_base (2..16; the 0b/0o/0x "
            "prefixes are accepted case-insensitively when they match the "
            "source base), validates every digit against the source "
            "alphabet, and renders the number in dst_base using lowercase "
            "digits and a manual divmod loop (no format specifiers). The "
            "result is zero-padded on the left up to width characters when "
            "width is given. Raise ValueError for out-of-range bases, "
            "negative width or invalid digits."
        )
        expected = f"convert({literal!r}, {src}, {dst}, {width}) == {out!r}"
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty=rng.choice(["beginner", "intermediate"]),
            task=task, expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Convert integers between bases 2..16 with canonical padding",
                "approach": "parse via digit validation + int(text, base); emit via divmod loop",
                "key_points": ["prefix handling must match the declared source base",
                               "divmod emits digits least-significant first",
                               "rjust(width, '0') pads without truncating"],
                "big_o_time": "O(digits)", "big_o_space": "O(digits)",
                "edge_cases": [f"zero renders as '0' then pads to width ({width})",
                               "invalid digits raise ValueError"]}},
            tags=["systems", "bases", "binary", "hex", "octal"],
            variant=f"base|{src}|{dst}|{width}", seed=rng.randrange(2**31))

    def _mk_mode_bits(self, rng: random.Random) -> Candidate:
        start = rng.randrange(0, 1 << 12) | (1 << 3)
        n_ops = rng.randint(3, 5)
        ops = []
        for _ in range(n_ops):
            ops.append((rng.choice(["set", "clear", "toggle"]),
                        rng.randrange(0, 12)))
        ref = start
        for kind, bit in ops:
            if kind == "set":
                ref |= 1 << bit
            elif kind == "clear":
                ref &= ~(1 << bit)
            else:
                ref ^= 1 << bit
        code = (
            "def mode_ops(mode: int, ops: list[tuple[str, int]]) -> int:\n"
            "    \"\"\"Apply left-to-right flag operations on a mode word.\n\n"
            "    Each op is ('set'|'clear'|'toggle', bit_index). Bits are\n"
            "    numbered from 0 (least significant). 'toggle' flips the bit\n"
            "    whatever its current value.\n"
            "    \"\"\"\n"
            "    result = mode\n"
            "    for kind, bit in ops:\n"
            "        if not 0 <= bit < 12:\n"
            "            raise ValueError(\"bit index out of range\")\n"
            "        if kind == \"set\":\n"
            "            result |= 1 << bit\n"
            "        elif kind == \"clear\":\n"
            "            result &= ~(1 << bit)\n"
            "        elif kind == \"toggle\":\n"
            "            result ^= 1 << bit\n"
            "        else:\n"
            "            raise ValueError(f\"unknown op: {kind}\")\n"
            "    return result\n"
        )
        double = [x for x in ops if x[0] == "toggle"][:1]
        extra_ops = [("toggle", 3), ("toggle", 3), ("set", 11), ("clear", 0)]
        ref_extra = start
        for kind, bit in extra_ops:
            if kind == "set":
                ref_extra |= 1 << bit
            elif kind == "clear":
                ref_extra &= ~(1 << bit)
            else:
                ref_extra ^= 1 << bit
        tests = (
            f"def run_tests():\n"
            f"    assert mode_ops({start:#o}, {ops!r}) == {ref:#o}\n"
            f"    assert mode_ops({start:#o}, {extra_ops!r}) == {ref_extra:#o}\n"
            f"    assert mode_ops(0, [('set', 0)]) == 1\n"
            f"    assert mode_ops(0, [('set', 11), ('toggle', 11)]) == 0\n"
            f"    try:\n"
            f"        mode_ops(0, [('set', 12)])\n"
            f"    except ValueError:\n"
            f"        pass\n"
            f"    else:\n"
            f"        raise AssertionError('bit 12 must raise')\n"
        )
        task = (
            "Permission words and hardware flags are manipulated with plain "
            "bit arithmetic. Implement mode_ops(mode, ops) in Python: ops is "
            "a list of tuples processed strictly left to right, each one "
            "being ('set', bit), ('clear', bit) or ('toggle', bit) with bit "
            "in range 0..11 (bit 0 is the least significant). 'set' forces "
            "the bit to 1, 'clear' forces it to 0, 'toggle' flips it. Raise "
            "ValueError for an out-of-range bit index or an unknown op name. "
            "Return the final mode word."
        )
        expected = f"mode_ops({start:#o}, {ops!r}) == {ref:#o} (left-to-right semantics)"
        return Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty=rng.choice(["beginner", "intermediate"]),
            task=task, expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": {
                "purpose": "Practice set/clear/toggle flag arithmetic on mode words",
                "approach": "OR to set, AND-NOT to clear, XOR to toggle, in order",
                "key_points": ["order of operations matters for toggles",
                               "double toggle returns to the original bit",
                               "1 << bit addresses bit `bit` from the LSB"],
                "big_o_time": "O(len(ops))", "big_o_space": "O(1)",
                "edge_cases": ["toggle applied twice is a no-op",
                               "bit 12 is rejected (12-bit mode word)"]}},
            tags=["systems", "bits", "permissions", "octal"],
            variant=f"bits|{start}|{'-'.join(str(o) for o in ops)}",
            seed=rng.randrange(2**31))

    # --------------------------------------------------------------- hooks
    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        if kind == "chmod_symbolic":
            return self._mk_chmod(rng)
        if kind == "umask_apply":
            return self._mk_umask(rng)
        if kind == "base_convert":
            return self._mk_base_convert(rng)
        return self._mk_mode_bits(rng)

    def make_buggy(self, rng: random.Random):
        kind = rng.choice(self.KINDS)
        builder = {"chmod_symbolic": self._mk_chmod,
                   "umask_apply": self._mk_umask,
                   "base_convert": self._mk_base_convert,
                   "mode_bits": self._mk_mode_bits}[kind]
        good = builder(random.Random(rng.randrange(2**31)))
        if kind == "chmod_symbolic":
            buggy_code = good.code.replace(
                "mode |= val << ((2 - tri) * 3)",
                "mode |= val << (tri * 3)")
            bug_kind = "triplet_order"
        elif kind == "umask_apply":
            buggy_code = good.code.replace(
                "return 0o666 & ~u, 0o777 & ~u",
                "return 0o666 - u, 0o777 - u")
            bug_kind = "subtract_umask"
        elif kind == "base_convert":
            buggy_code = good.code.replace(
                'result = "".join(reversed(stack))',
                'result = "".join(stack)')
            bug_kind = "digit_order"
        else:
            buggy_code = good.code.replace(
                "result ^= 1 << bit",
                "result &= ~(1 << bit)")
            bug_kind = "toggle_as_clear"
        if buggy_code == good.code:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain="systems",
            difficulty="intermediate",
            task=good.task, expected_behavior="See question.",
            code=buggy_code, tests=good.tests, verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code,
                   "explain": good.notes["explain"]},
            tags=["systems", "bug"], variant=f"{good.variant}|bug|{bug_kind}",
            seed=rng.randrange(2**31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), NumberBasesFamily)
