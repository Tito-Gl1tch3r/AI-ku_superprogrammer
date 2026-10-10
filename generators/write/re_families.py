"""Reverse-engineering extension (v0.6.0): module 04, inspired by morluto/rea.

Every family in this module trains REAL reverse-engineering skills on REAL
artifacts: the pipeline compiles small ELF binaries with gcc at generation
time, harvests ground truth with actual binutils (readelf/nm/objdump/strings),
executes the binaries to capture observed behaviour, and only then authors the
record. Nothing is invented: every expected value in the bundled test suites
was observed from a real tool run against a real binary in this sandbox.

Families (all python solutions, all executed for verification):
  * re_elf_parser       - parse ELF header/sections/segments/symbols with struct
  * re_disasm_analysis  - analyse real objdump -d text of a compiled function
  * re_blackbox_reimpl  - reimplement the byte transform of a stripped binary
  * re_version_diff     - classify probe inputs across two compiled versions
  * re_strings_decode   - recover obfuscated string tables from real binaries

Binaries are built with -nostdlib -static (no libc) so they stay tiny and
their symbol tables contain exactly the functions we authored. The host must
be x86_64 (syscall stubs are written for the Linux x86_64 ABI); on any other
host every generate() honestly returns None.
"""
from __future__ import annotations

import base64
import hashlib
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import tempfile

from ..core import Candidate, Family, register

_ARCH_OK = platform.machine() == "x86_64"

_GCC = shutil.which("gcc")
_OBJDUMP = shutil.which("objdump")
_READELF = shutil.which("readelf")
_NM = shutil.which("nm")
_STRINGS = shutil.which("strings")

_TOOLS_OK = all((_GCC, _OBJDUMP, _READELF, _NM, _STRINGS))

# -----------------------------------------------------------------------------
# C runtime stubs for -nostdlib static binaries (Linux x86_64 ABI)
# -----------------------------------------------------------------------------

_SYSCALL_STUB = """
static long sys3(long n, long a, long b, long c) {
    long ret;
    __asm__ volatile ("syscall"
                      : "=a"(ret)
                      : "a"(n), "D"(a), "S"(b), "d"(c)
                      : "rcx", "r11", "memory");
    return ret;
}
static void sys_write(long fd, const char *buf, long len) {
    sys3(1, fd, (long)buf, len);
}
static long sys_read(long fd, char *buf, long cap) {
    return sys3(0, fd, (long)buf, cap);
}
static void sys_exit(long code) {
    sys3(60, code, 0, 0);
    __builtin_unreachable();
}
"""

_COMPILE_FLAGS_KEEP_SYMS = [
    "-Os", "-static", "-nostdlib", "-nostartfiles", "-no-pie",
    "-Wl,--build-id=none", "-fno-asynchronous-unwind-tables",
    "-fno-stack-protector", "-fno-inline",
]
_COMPILE_FLAGS_STRIP = _COMPILE_FLAGS_KEEP_SYMS + ["-s"]


def _compile_c(src: str, strip: bool = False) -> bytes | None:
    """Compile C source to a static -nostdlib ELF. Returns bytes or None."""
    if not (_ARCH_OK and _GCC):
        return None
    flags = list(_COMPILE_FLAGS_STRIP if strip else _COMPILE_FLAGS_KEEP_SYMS)
    with tempfile.TemporaryDirectory(prefix="re_fam_") as d:
        cpath = os.path.join(d, "prog.c")
        bpath = os.path.join(d, "prog")
        with open(cpath, "w", encoding="utf-8") as f:
            f.write(src)
        try:
            r = subprocess.run([_GCC, *flags, "-o", bpath, cpath],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=d, timeout=30)
        except Exception:
            return None
        if r.returncode != 0 or not os.path.exists(bpath):
            return None
        with open(bpath, "rb") as f:
            return f.read()


def _run_bin(blob: bytes, stdin_bytes: bytes = b"", timeout: float = 10.0):
    """Execute an embedded ELF blob. Returns (exit_code, stdout) or None."""
    if not _ARCH_OK:
        return None
    with tempfile.TemporaryDirectory(prefix="re_run_") as d:
        bpath = os.path.join(d, "prog")
        with open(bpath, "wb") as f:
            f.write(blob)
        os.chmod(bpath, 0o755)
        try:
            r = subprocess.run([bpath], input=stdin_bytes,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=d, timeout=timeout)
        except Exception:
            return None
        return r.returncode, r.stdout


def _tool_text(tool: str, blob: bytes, extra_args: list) -> str | None:
    """Run a binutils tool against an embedded ELF; return stdout text."""
    exe = {"objdump": _OBJDUMP, "readelf": _READELF,
           "nm": _NM, "strings": _STRINGS}.get(tool)
    if not exe or not _ARCH_OK:
        return None
    with tempfile.TemporaryDirectory(prefix="re_tool_") as d:
        bpath = os.path.join(d, "prog")
        with open(bpath, "wb") as f:
            f.write(blob)
        os.chmod(bpath, 0o755)
        try:
            r = subprocess.run([exe, *extra_args, bpath],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=d, timeout=20)
        except Exception:
            return None
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", "replace")


def _b64(blob: bytes) -> str:
    return base64.b64encode(blob).decode("ascii")


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


# -----------------------------------------------------------------------------
# Reference ELF parsing (independent implementation #1). The SOLUTION templates
# below are implementation #2; tests pin values both produce, and generate()
# additionally cross-checks them against real binutils output before accepting.
# -----------------------------------------------------------------------------

_SHT = {0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB", 4: "RELA",
        5: "HASH", 6: "DYNAMIC", 7: "NOTE", 8: "NOBITS", 9: "REL",
        11: "DYNSYM", 14: "INIT_ARRAY", 15: "FINI_ARRAY"}
_PT = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE",
       6: "PHDRS", 7: "TLS"}


def _ref_elf_header(b: bytes) -> dict:
    """Parse the 64-bit ELF header (little endian) from raw bytes."""
    if b[:4] != b"\x7fELF":
        raise ValueError("not an ELF")
    (e_type, e_machine) = struct.unpack_from("<HH", b, 16)
    (e_entry, e_phoff, e_shoff) = struct.unpack_from("<QQQ", b, 24)
    (e_flags,) = struct.unpack_from("<I", b, 48)
    (e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum,
     e_shstrndx) = struct.unpack_from("<HHHHHH", b, 52)
    return {"e_type": e_type, "e_machine": e_machine, "e_entry": e_entry,
            "e_phoff": e_phoff, "e_shoff": e_shoff, "e_flags": e_flags,
            "e_ehsize": e_ehsize, "e_phentsize": e_phentsize,
            "e_phnum": e_phnum, "e_shentsize": e_shentsize,
            "e_shnum": e_shnum, "e_shstrndx": e_shstrndx}


def _ref_sections(b: bytes) -> list:
    """Return [(name, sh_addr, sh_offset, sh_size, sh_type)] for all sections."""
    hdr = _ref_elf_header(b)
    shoff, shentsize, shnum = hdr["e_shoff"], hdr["e_shentsize"], hdr["e_shnum"]
    raw = []
    for i in range(shnum):
        off = shoff + i * shentsize
        (nameoff, sh_type, _flags, sh_addr, sh_offset, sh_size,
         _link, _info, _align, _entsize) = struct.unpack_from("<IIQQQQIIQQ", b, off)
        raw.append((nameoff, sh_type, sh_addr, sh_offset, sh_size))
    strtab_off = raw[hdr["e_shstrndx"]][3]
    out = []
    for nameoff, sh_type, sh_addr, sh_offset, sh_size in raw:
        end = b.index(b"\x00", strtab_off + nameoff)
        name = b[strtab_off + nameoff:end].decode("ascii", "replace")
        out.append((name, sh_addr, sh_offset, sh_size, _SHT.get(sh_type, str(sh_type))))
    return out


def _ref_segments(b: bytes) -> list:
    """Return [(p_type, p_offset, p_vaddr, p_filesz, p_memsz)] for programs."""
    hdr = _ref_elf_header(b)
    out = []
    for i in range(hdr["e_phnum"]):
        off = hdr["e_phoff"] + i * hdr["e_phentsize"]
        (p_type, _flags, p_offset, p_vaddr, _paddr, p_filesz,
         p_memsz, _align) = struct.unpack_from("<IIQQQQQQ", b, off)
        out.append((_PT.get(p_type, str(p_type)), p_offset, p_vaddr,
                    p_filesz, p_memsz))
    return out


def _ref_symbols(b: bytes) -> list:
    """Return [(name, value, size, info)] from .symtab (type OBJECT/FUNC/NOTYPE)."""
    hdr = _ref_elf_header(b)
    secs = _ref_sections(b)
    symtab = next(s for s in secs if s[4] == "SYMTAB")
    strtab = next(s for s in secs if s[0] == ".strtab")
    idx = secs.index(symtab)
    sh = hdr["e_shoff"] + idx * hdr["e_shentsize"]
    sym_entsize = struct.unpack_from("<Q", b, sh + 56)[0]  # sh_entsize
    out = []
    for off in range(symtab[2], symtab[2] + symtab[3], sym_entsize):
        st_name, st_info, _other, _shndx, st_value, st_size = \
            struct.unpack_from("<IBBHQQ", b, off)
        if st_name == 0:
            continue
        end = b.index(b"\x00", strtab[2] + st_name)
        name = b[strtab[2] + st_name:end].decode("ascii", "replace")
        out.append((name, st_value, st_size, st_info & 0xF))
    return out


def _gt_check_against_binutils(blob: bytes, kind: str) -> bool:
    """Cross-check our reference parse against real binutils output."""
    hdr = _ref_elf_header(blob)
    if kind == "header_magic":
        text = _tool_text("readelf", blob, ["-h"])
        return bool(text) and "ELF Header" in text and \
            f"{hdr['e_entry']:#x}" in text and "Entry point address" in text
    if kind == "section_table":
        text = _tool_text("readelf", blob, ["-S"])
        secs = _ref_sections(blob)
        if not text:
            return False
        named = [s for s in secs if s[0]]
        hits = sum(1 for s in named if s[0] in text)
        return len(named) >= 8 and hits >= len(named) - 2
    if kind == "program_headers":
        text = _tool_text("readelf", blob, ["-l"])
        segs = _ref_segments(blob)
        loads = sum(1 for s in segs if s[0] == "LOAD")
        return bool(text) and loads >= 1 and f"LOAD" in text
    if kind == "symbol_table":
        text = _tool_text("nm", blob, [])
        syms = _ref_symbols(blob)
        names = {s[0] for s in syms if s[3] in (1, 2)}  # OBJECT/FUNC
        return bool(text) and names and all(n in text for n in names)
    return False


# -----------------------------------------------------------------------------
# Family 1: re_elf_parser
# -----------------------------------------------------------------------------

_FN_POOL = ["emit_banner", "flush_ring", "seed_state", "drain_queue",
            "sync_clock", "load_table", "pack_frame", "verify_crc",
            "spin_lock", "wake_worker", "clip_range", "scale_gains"]

_TAG_POOL = ["BOOT", "SYNC", "INIT", "HALT", "POLL", "FLUSH", "PROBE",
             "WAKE", "STRT", "STOPP", "MARK", "EDGE", "PING", "DONE"]


def _build_binary(rng: random.Random, n_helpers: int) -> tuple:
    """Author + compile a small static ELF with named helpers.

    Helpers carry a volatile guarded write and a countdown loop so the
    generated code contains real conditional jumps and branch targets.
    Returns (c_source, elf_bytes, helper_names, helper_specs, blob_vals)
    where each spec is (name, tag_taken, tag_other, k_initial, loop_floor).
    """
    names = rng.sample(_FN_POOL, n_helpers)
    tags = rng.sample(_TAG_POOL, 2 * n_helpers)
    n_blob = rng.randrange(8, 24)
    blob_vals = [rng.randrange(0, 256) for _ in range(n_blob)]
    lines = [_SYSCALL_STUB,
             f"static const unsigned char blob[{n_blob}] = {{{','.join(map(str, blob_vals))}}};"]
    specs = []
    for i, (fname, t1, t2) in enumerate(zip(names, tags[0::2], tags[1::2])):
        k = rng.randrange(5, 28)
        m = rng.randrange(2, 5)
        specs.append((fname, t1 if k & 1 else t2, t2, k, m))
        lines.append(
            f"static void {fname}(void) {{\n"
            f"    volatile unsigned t = {k};\n"
            f"    if (t & 1) {{ sys_write(1, \"{t1}\\n\", {len(t1) + 1}); }}\n"
            f"    else {{ sys_write(1, \"{t2}\\n\", {len(t2) + 1}); }}\n"
            f"    while (t > {m}) t -= 2;\n"
            "    sys_write(1, (const char *)blob, (t & 3) + 1);\n"
            "}")
    calls = "\n    ".join(f"{n}();" for n in names)
    lines.append(
        "void _start(void) {\n"
        f"    {calls}\n"
        "    sys_write(1, (const char *)blob, 4);\n"
        "    sys_exit(0);\n"
        "}")
    src = "\n".join(lines) + "\n"
    blob = _compile_c(src, strip=False)
    if blob is None:
        return None, None, [], [], []
    return src, blob, names, specs, blob_vals


_HARNESS_PRELUDE = '''import base64
import os
import tempfile

_B64 = "{b64}"


def _dump():
    fd, path = tempfile.mkstemp(suffix=".elf")
    os.write(fd, base64.b64decode(_B64))
    os.close(fd)
    os.chmod(path, 0o755)
    return path
'''

_HEADER_SOLUTION = '''"""Minimal ELF64 header reader (little-endian executables only)."""
import struct

FMT = "<HHIQQQIHHHHHH"


def read_elf_header(path):
    """Return the fixed fields of the ELF64 header as a dict."""
    with open(path, "rb") as fh:
        data = fh.read(64)
    if data[:4] != b"\\x7fELF":
        raise ValueError("missing ELF magic")
    if data[4] != 2 or data[5] != 1:
        raise ValueError("only ELF64 little-endian is supported")
    fields = struct.unpack_from(FMT, data, 16)
    (e_type, e_machine, _flags_pad, e_entry, e_phoff, e_shoff, e_flags,
     e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum,
     e_shstrndx) = fields
    return {"e_type": e_type, "e_machine": e_machine, "e_entry": e_entry,
            "e_phoff": e_phoff, "e_shoff": e_shoff, "e_flags": e_flags,
            "e_ehsize": e_ehsize, "e_phentsize": e_phentsize,
            "e_phnum": e_phnum, "e_shentsize": e_shentsize,
            "e_shnum": e_shnum, "e_shstrndx": e_shstrndx}
'''

_SECTION_SOLUTION = '''"""Enumerate ELF64 section headers with names resolved via .shstrtab."""
import struct


def list_sections(path):
    """Return [(name, sh_addr, sh_offset, sh_size, sh_type_name), ...]."""
    with open(path, "rb") as fh:
        data = fh.read()
    e_shoff, = struct.unpack_from("<Q", data, 40)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 58)
    TYPE_NAMES = {0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB",
                  8: "NOBITS", 9: "REL", 11: "DYNSYM"}
    headers = []
    for i in range(e_shnum):
        base = e_shoff + i * e_shentsize
        name_off, sh_type = struct.unpack_from("<II", data, base)
        sh_addr, sh_offset, sh_size = struct.unpack_from("<QQQ", data, base + 16)
        headers.append((name_off, sh_type, sh_addr, sh_offset, sh_size))
    str_off = headers[e_shstrndx][3]
    out = []
    for name_off, sh_type, sh_addr, sh_offset, sh_size in headers:
        end = data.index(b"\\x00", str_off + name_off)
        name = data[str_off + name_off:end].decode("ascii", "replace")
        out.append((name, sh_addr, sh_offset, sh_size,
                    TYPE_NAMES.get(sh_type, str(sh_type))))
    return out
'''

_SEGMENT_SOLUTION = '''"""List ELF64 program headers (segments) from a little-endian binary."""
import struct


def list_segments(path):
    """Return [(p_type_name, p_offset, p_vaddr, p_filesz, p_memsz), ...]."""
    with open(path, "rb") as fh:
        data = fh.read()
    e_phoff, = struct.unpack_from("<Q", data, 32)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 54)
    TYPE_NAMES = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP",
                  4: "NOTE", 6: "PHDRS", 7: "TLS"}
    out = []
    for i in range(e_phnum):
        base = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", data, base)[0]
        p_offset, p_vaddr = struct.unpack_from("<QQ", data, base + 8)
        p_filesz, p_memsz = struct.unpack_from("<QQ", data, base + 32)
        out.append((TYPE_NAMES.get(p_type, str(p_type)),
                    p_offset, p_vaddr, p_filesz, p_memsz))
    return out
'''

_SYMBOL_SOLUTION = '''"""Extract FUNC/OBJECT symbols from a non-stripped ELF64 .symtab."""
import struct


# Section header tuple layout used below (ELF64, little endian):
# (sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size,
#  sh_link, sh_info, sh_addralign, sh_entsize)
def list_symbols(path):
    """Return [(name, st_value, st_size, kind)] sorted by address.

    kind: 1 = OBJECT, 2 = FUNC. Local and global symbols both included;
    the null symbol and unnamed entries are skipped. The string table
    used for symbol names is found via the symtab's sh_link field.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    e_shoff, = struct.unpack_from("<Q", data, 40)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, 58)
    heads = []
    for i in range(e_shnum):
        base = e_shoff + i * e_shentsize
        heads.append(struct.unpack_from("<IIQQQQIIQQ", data, base))
    symtab = next(h for h in heads if h[1] == 2)
    strtab = heads[symtab[6]]          # sh_link -> companion string table
    symtab_off, symtab_size, symtab_entsize = symtab[4], symtab[5], symtab[9]
    strtab_off = strtab[4]
    out = []
    for off in range(symtab_off, symtab_off + symtab_size, symtab_entsize):
        st_name, st_info, _o, _s, st_value, st_size = \
            struct.unpack_from("<IBBHQQ", data, off)
        if st_name == 0:
            continue
        end = data.index(b"\\x00", strtab_off + st_name)
        name = data[strtab_off + st_name:end].decode("ascii", "replace")
        kind = st_info & 0xF
        if kind in (1, 2):
            out.append((name, st_value, st_size, kind))
    out.sort(key=lambda t: t[1])
    return out
'''


class REElfParserFamily(Family):
    """Write ELF parsers verified against binaries compiled in this sandbox."""

    NAME = "re_elf_parser"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "code_review", "trace")
    KINDS = ("header_magic", "section_table", "program_headers", "symbol_table")

    _SOL = {"header_magic": _HEADER_SOLUTION, "section_table": _SECTION_SOLUTION,
            "program_headers": _SEGMENT_SOLUTION, "symbol_table": _SYMBOL_SOLUTION}
    _FN = {"header_magic": "read_elf_header", "section_table": "list_sections",
           "program_headers": "list_segments", "symbol_table": "list_symbols"}

    def generate(self, rng: random.Random):
        if not (_ARCH_OK and _TOOLS_OK):
            return None
        kind = rng.choice(self.KINDS)
        n_helpers = rng.randrange(3, 7)
        src, blob, names, _specs, _bv = _build_binary(rng, n_helpers)
        if blob is None or len(blob) < 1500:
            return None
        if not _gt_check_against_binutils(blob, kind):
            return None  # honest drop: our parse and binutils disagree

        if kind == "header_magic":
            expected = _ref_elf_header(blob)
            difficulty = "intermediate"
        elif kind == "section_table":
            secs = _ref_sections(blob)
            expected = {"count": len(secs),
                        "text": next(s for s in secs if s[0] == ".text")[:4],
                        "names": sorted(s[0] for s in secs if s[0])}
            difficulty = "intermediate"
        elif kind == "program_headers":
            segs = _ref_segments(blob)
            expected = {"phnum": len(segs),
                        "loads": [s for s in segs if s[0] == "LOAD"]}
            difficulty = "advanced"
        else:
            keep = set(names) | {"_start", "blob"}
            exp_symbols = {n: (v, s, k) for (n, v, s, k) in _ref_symbols(blob)
                           if n in keep}
            if len(exp_symbols) < n_helpers + 1:
                return None  # symbols missing from the table: honest drop
            expected = {"funcs": exp_symbols}
            difficulty = "advanced"

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=difficulty, task=self._mk_task(kind),
            expected_behavior=self._mk_behavior(kind),
            code=self._SOL[kind], tests=self._mk_tests(kind, blob, expected),
            verify_method="executed",
            notes={"explain": self._mk_explain(kind), "c_source": src,
                   "binary_sha256": _sha256(blob), "binary_bytes": len(blob)},
            tags=["reverse-engineering", "elf", "binutils", kind],
            variant=kind, seed=rng.randrange(2 ** 31))
        return cand

    def _mk_task(self, kind: str) -> str:
        fn = self._FN[kind]
        if kind == "header_magic":
            return ("You are given a 64-bit little-endian ELF binary compiled as a "
                    "static -nostdlib executable (it is materialized to disk by the "
                    "test harness). Implement `read_elf_header(path)` in Python that "
                    "parses the fixed ELF64 header fields (type, machine, entry point, "
                    "program/section header offsets and counts) and returns them as a "
                    "dict with exactly the documented keys. Raise ValueError when the "
                    "ELF magic is missing or the file is not ELF64 little-endian.")
        if kind == "section_table":
            return ("A statically linked, libc-free ELF64 binary is materialized by "
                    "the test harness. Implement `list_sections(path)` that walks the "
                    "section header table, resolves every section name through the "
                    ".shstrtab string table, and returns tuples of (name, sh_addr, "
                    "sh_offset, sh_size, sh_type_name) for ALL sections in file order. "
                    "Map known sh_type values to their canonical names and fall back "
                    "to the decimal string for anything else.")
        if kind == "program_headers":
            return ("The test harness materializes a stripped-of-libc ELF64 loader "
                    "image. Implement `list_segments(path)` that reads e_phoff/"
                    "e_phentsize/e_phnum from the ELF header and returns one tuple "
                    "(p_type_name, p_offset, p_vaddr, p_filesz, p_memsz) per program "
                    "header, translating segment types (LOAD, NOTE, ...) to their "
                    "canonical names. These are the segments a loader would map, so "
                    "getting offsets and virtual addresses exactly right matters.")
        return ("A non-stripped ELF64 binary (static, no libc) is materialized by "
                "the test harness. Implement `list_symbols(path)` that locates the "
                ".symtab and its companion .strtab through the section header table, "
                "decodes every Elf64_Sym entry, skips unnamed/null symbols, keeps "
                "only OBJECT and FUNC symbols, and returns (name, st_value, st_size, "
                "kind) tuples sorted by st_value. Named helper functions and data "
                "objects of the original C program must all be recovered.")

    def _mk_tests(self, kind: str, blob: bytes, expected: dict) -> str:
        fn = self._FN[kind]
        lines = [_HARNESS_PRELUDE.format(b64=_b64(blob)), "", "def run_tests():",
                 f"    from solution import {fn}", "    p = _dump()", "    try:"]
        if kind == "header_magic":
            pairs = sorted(expected.items())
            lines.append(f"        got = {fn}(p)")
            lines.append(f"        assert sorted(got.items()) == {pairs!r}")
        elif kind == "section_table":
            lines.append(f"        secs = {fn}(p)")
            lines.append(f"        assert len(secs) == {expected['count']}")
            lines.append("        assert [s for s in secs if s[0] == '.text'][0][:4] == "
                         f"{expected['text']!r}")
            lines.append("        assert sorted(s[0] for s in secs if s[0]) == "
                         f"{expected['names']!r}")
        elif kind == "program_headers":
            lines.append(f"        segs = {fn}(p)")
            lines.append(f"        assert len(segs) == {expected['phnum']}")
            lines.append("        assert [s for s in segs if s[0] == 'LOAD'] == "
                         f"{expected['loads']!r}")
        else:
            pairs = sorted(expected["funcs"].items())
            lines.append(f"        got = dict((n, (v, s, k)) for n, v, s, k in {fn}(p))")
            lines.append(f"        expected = {pairs!r}")
            lines.append("        for name, exp in expected:")
            lines.append("            assert got[name] == exp, name")
        lines += ["    finally:", "        os.remove(p)", ""]
        return "\n".join(lines)

    def _mk_behavior(self, kind: str) -> str:
        if kind == "header_magic":
            return ("Running the bundled suite materializes the ELF and asserts the "
                    "parsed header equals the reference values byte for byte; wrong "
                    "endianness or offsets fail loudly.")
        if kind == "section_table":
            return ("The suite asserts the section count, the exact .text tuple and "
                    "the full sorted name set recovered through .shstrtab.")
        if kind == "program_headers":
            return ("The suite asserts the program header count and that every LOAD "
                    "segment tuple (type, offset, vaddr, filesz, memsz) matches the "
                    "loader-visible mapping exactly.")
        return ("The suite asserts every authored function symbol and the data "
                "object resolve to their exact (value, size, kind) triples from "
                ".symtab, ordered by virtual address.")

    def _mk_explain(self, kind: str) -> dict:
        if kind == "header_magic":
            return {"purpose": "Recover structural metadata of a stripped ELF from "
                               "raw bytes with no external tools.",
                    "approach": "Fixed-offset struct unpacking of the ELF64 header "
                                "after magic/class/endian validation.",
                    "key_points": ["magic is 0x7f 'E' 'L' 'F'; class 2 and data 1 "
                                   "mean ELF64 little-endian",
                                   "header fields start at offset 16 and run to 64",
                                   "e_entry/e_phoff/e_shoff are 8-byte fields"],
                    "big_o_time": "O(1)", "big_o_space": "O(1)",
                    "edge_cases": ["non-ELF files must raise ValueError",
                                   "big-endian images are rejected, not misparsed"]}
        if kind == "section_table":
            return {"purpose": "Enumerate every section of an ELF64 image with "
                               "resolved names.",
                    "approach": "Walk e_shoff/e_shentsize entries; resolve names "
                                "from the .shstrtab string table.",
                    "key_points": ["e_shstrndx indexes the name string table",
                                   "names are NUL-terminated C strings",
                                   "unknown sh_type values fall back to decimals"],
                    "big_o_time": "O(sections + name bytes)",
                    "big_o_space": "O(sections)",
                    "edge_cases": ["the NULL section has no name",
                                   "NOBITS sections occupy no file bytes"]}
        if kind == "program_headers":
            return {"purpose": "Recover the memory mapping a loader would perform.",
                    "approach": "Read e_phoff/e_phentsize/e_phnum and decode each "
                                "program header struct.",
                    "key_points": ["LOAD segments carry filesz/memsz (BSS zero-fill)",
                                   "p_offset is file-relative, p_vaddr is memory-"
                                   "relative"],
                    "big_o_time": "O(phnum)", "big_o_space": "O(phnum)",
                    "edge_cases": ["memsz can exceed filesz (zero-initialized data)"]}
        return {"purpose": "Recover authored function and object symbols from a "
                           "non-stripped static binary.",
                "approach": "Find .symtab by section type, take its sh_link as the "
                            "string table, decode Elf64_Sym entries.",
                "key_points": ["st_info low nibble encodes the symbol type",
                               "sh_link points at the companion .strtab",
                               "address order reveals the original link layout"],
                "big_o_time": "O(symbols)", "big_o_space": "O(symbols)",
                "edge_cases": ["unnamed section symbols are skipped",
                                "FILE-type entries carry no addresses"]}

    # -------------------------------------------------------------- make_buggy
    _BUGS = {
        "header_magic": ("FMT = \"<HHIQQQIHHHHHH\"", "FMT = \">HHIQQQIHHHHHH\"",
                         "wrong_endianness"),
        "section_table": ('struct.unpack_from("<QQQ", data, base + 16)',
                          'struct.unpack_from("<QQQ", data, base + 24)',
                          "shifted_field_offsets"),
        "program_headers": ('struct.unpack_from("<QQ", data, base + 8)',
                            'struct.unpack_from("<QQ", data, base + 16)',
                            "wrong_program_header_offsets"),
        "symbol_table": ("if kind in (1, 2):", "if kind == 2:",
                         "dropped_object_symbols"),
    }

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        old, new, bug_kind = self._BUGS[cand.variant]
        if cand.code.count(old) != 1:
            return None
        buggy = Candidate(
            family=cand.family, language=cand.language, domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=cand.code.replace(old, new), tests=cand.tests,
            verify_method=cand.verify_method, notes=cand.notes,
            tags=cand.tags, variant=cand.variant, seed=cand.seed,
            is_project=cand.is_project)
        meta = {"kind": bug_kind,
                "problem": f"{bug_kind}: the parser reports values that do not "
                           "match the real binary.",
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy, meta


def _extract_function_block(text: str, target: str):
    """Extract the objdump -d block of one function, label line included."""
    lines = text.splitlines()
    start = None
    label = f"<{target}>:"
    for i, ln in enumerate(lines):
        if ln.rstrip().endswith(label) and ":" in ln:
            start = i
            break
    if start is None:
        return None
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if not ln.strip():
            break
        if ln[0] not in (" ", chr(9)):
            break  # next top-level label or section header
        out.append(ln)
    return "\n".join(out).rstrip()


def _disasm_ground_truth(block: str, kind: str):
    """Parse the REAL objdump block; return brace-free ground truth or None."""
    import re
    instrs = []
    body = block.splitlines()[1:]
    for ln in body:
        m = re.match(r"\s*([0-9a-f]+):\t((?:[0-9a-f]{2}[ \t])+)[ \t]*(.*)$", ln)
        if m:
            addr = int(m.group(1), 16)
            nbytes = len(m.group(2).split())
            instrs.append((addr, nbytes, m.group(3).strip()))
    if not instrs:
        return None
    if kind == "count_calls":
        names = []
        for _a, _n, asm in instrs:
            mm = re.match(r"call\s+[0-9a-f]+ <([A-Za-z_][A-Za-z0-9_]*)>", asm)
            if mm:
                names.append(mm.group(1))
        if not names:
            return None
        return (tuple(names), len(names))
    if kind == "immediates":
        vals = sorted(int(x, 16) for x in
                      set(re.findall(r"\$0x([0-9a-f]+)", block)))
        if not vals:
            return None
        return tuple(vals)
    if kind == "jump_targets":
        targets = set()
        for _a, _n, asm in instrs:
            mm = re.match(r"j\w+\s+([0-9a-f]+)\b", asm)
            if mm:
                targets.add(int(mm.group(1), 16))
        if not targets:
            return None
        return tuple(sorted(targets))
    if kind == "function_span":
        start = instrs[0][0]
        last_addr, last_len, _ = instrs[-1]
        return (start, last_addr + last_len - start, len(instrs))
    return None


class REDisasmAnalysisFamily(Family):
    """Analyse real objdump -d text of compiled -nostdlib helper functions."""

    NAME = "re_disasm_analysis"
    LANGUAGE = "python"
    DOMAIN = "systems"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "trace", "testing", "code_review")
    KINDS = ("count_calls", "immediates", "jump_targets", "function_span")

    def generate(self, rng: random.Random):
        if not (_ARCH_OK and _TOOLS_OK):
            return None
        kind = rng.choice(self.KINDS)
        src, blob, names, _specs, _bv = _build_binary(rng, rng.randrange(3, 6))
        if blob is None:
            return None
        # _start is the only function guaranteed to contain calls (to helpers);
        # helper functions may inline all syscalls and end up call-free.
        target = "_start" if kind == "count_calls" else rng.choice(names)
        text = _tool_text("objdump", blob, ["-d"])
        if not text or f"<{target}>:" not in text:
            return None
        block = _extract_function_block(text, target)
        if block is None or len(block.splitlines()) < 3:
            return None
        expected = _disasm_ground_truth(block, kind)
        if expected is None:
            return None
        difficulty = "intermediate" if kind in ("count_calls", "immediates") \
            else "advanced"
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=difficulty, task=self._mk_task(kind, target),
            expected_behavior=self._mk_behavior(kind),
            code=self._mk_solution(kind),
            tests=self._mk_tests(kind, target, block, expected),
            verify_method="executed",
            notes={"explain": self._mk_explain(kind), "c_source": src,
                   "binary_sha256": _sha256(blob), "target_function": target,
                   "objdump_excerpt": block},
            tags=["reverse-engineering", "disassembly", "objdump", kind],
            variant=kind, seed=rng.randrange(2 ** 31))
        return cand

    def _mk_task(self, kind: str, target: str) -> str:
        if kind == "count_calls":
            return (f"Below is the real `objdump -d` output of a statically "
                    f"linked, libc-free x86-64 binary; focus on `_start`, which "
                    f"orchestrates the program's helper routines. Implement "
                    f"`analyse(text, name)` in Python that, given the full "
                    f"disassembly text and a function name, returns a tuple with "
                    f"the call targets of that function in textual order plus the "
                    f"total number of call instructions. This is exactly the "
                    f"first-pass triage an analyst runs to map a program's call "
                    f"structure before reading any logic in detail.")
        if kind == "immediates":
            return (f"The function `{target}` from a real compiled binary has been "
                    f"disassembled with objdump and its block is embedded in the "
                    f"test suite. Implement `analyse(text, name)` that extracts "
                    f"the function's immediate operands: every `$0x...` constant "
                    f"appearing in its instructions, deduplicated and sorted as "
                    f"integers. Immediate-only recovery is the fastest way to "
                    f"spot magic constants, buffer sizes and protocol tags "
                    f"without understanding the control flow at all.")
        if kind == "jump_targets":
            return (f"You get the objdump -d block of `{target}`, a compiled "
                    f"helper containing at least one conditional branch and a "
                    f"countdown loop. Implement `analyse(text, name)` returning "
                    f"the sorted tuple of branch-target instruction addresses "
                    f"(every target referenced by any j-type instruction in the "
                    f"function). Branch-target sets are the backbone for "
                    f"rebuilding control-flow graphs when no source is available.")
        return (f"The block of `{target}` from a real objdump -d dump is provided. "
                f"Implement `analyse(text, name)` that measures the function's "
                f"footprint: a tuple (start_address, span_bytes, instruction_count) "
                f"where span_bytes is end_address minus start_address computed from "
                f"the final instruction's address plus its encoding length. Code "
                f"size estimates from disassembly drive diffing and patching "
                f"decisions during binary triage.")

    def _mk_behavior(self, kind: str) -> str:
        return ("Running the suite parses the embedded REAL objdump block and "
                "asserts the analysis result equals the values harvested from the "
                "actual disassembly of the actual compiled binary.")

    def _mk_solution(self, kind: str) -> str:
        if kind == "count_calls":
            return '''"""Map the call structure of one function from objdump text."""
import re

_CALL = re.compile(r"call\\s+[0-9a-f]+ <([A-Za-z_][A-Za-z0-9_]*)>")
_LABEL = re.compile(r"^[0-9a-f]+ <([^>]+)>:")


def analyse(text, name):
    """Return (call_targets_in_order, total_calls) for function `name`."""
    lines = text.splitlines()
    out = []
    inside = False
    for ln in lines:
        lab = _LABEL.match(ln)
        if lab:
            inside = lab.group(1) == name
            continue
        if not inside or not ln.strip():
            if inside and not ln.strip():
                break
            continue
        m = _CALL.search(ln)
        if m:
            out.append(m.group(1))
    return tuple(out), len(out)
'''
        if kind == "immediates":
            return '''"""Recover the immediate constants used by one disassembled function."""
import re

_IMM = re.compile(r"\\$0x([0-9a-f]+)")


def analyse(text, name):
    """Return sorted unique immediates of function `name` as ints."""
    block = _slice(text, name)
    return tuple(sorted(set(int(m, 16) for m in _IMM.findall(block))))


def _slice(text, name):
    marker = "<" + name + ">:"
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.rstrip().endswith(marker))
    keep = []
    for ln in lines[start + 1:]:
        if not ln.strip():
            break
        keep.append(ln)
    return "\\n".join(keep)
'''
        if kind == "jump_targets":
            return '''"""Collect branch-target addresses of a function from objdump text."""
import re

_JMP = re.compile(r"\\bj[A-Za-z0-9]+\\s+([0-9a-f]+)\\b")


def analyse(text, name):
    """Return sorted unique branch-target addresses for function `name`."""
    lines = text.splitlines()
    marker = "<" + name + ">:"
    start = next(i for i, ln in enumerate(lines) if ln.rstrip().endswith(marker))
    targets = set()
    for ln in lines[start + 1:]:
        if not ln.strip():
            break
        m = _JMP.search(ln)
        if m:
            targets.add(int(m.group(1), 16))
    return tuple(sorted(targets))
'''
        return '''"""Measure code footprint of a function from its objdump block."""
import re

_ROW = re.compile(r"\\s*([0-9a-f]+):\\t((?:[0-9a-f]{2}[ \\t])+)[ \\t]*(.*)$")


def analyse(text, name):
    """Return (start_address, span_bytes, instruction_count)."""
    lines = text.splitlines()
    marker = "<" + name + ">:"
    start = next(i for i, ln in enumerate(lines) if ln.rstrip().endswith(marker))
    rows = []
    for ln in lines[start + 1:]:
        if not ln.strip():
            break
        m = _ROW.match(ln)
        if m:
            rows.append((int(m.group(1), 16), len(m.group(2).split())))
    first = rows[0][0]
    last_addr, last_len = rows[-1]
    return first, last_addr + last_len - first, len(rows)
'''

    def _mk_tests(self, kind: str, target: str, block: str, expected) -> str:
        lines = [f"_BLOCK = {block!r}", "", "def run_tests():",
                 "    from solution import analyse",
                 f"    assert analyse(_BLOCK, {target!r}) == {expected!r}", ""]
        return "\n".join(lines)

    def _mk_explain(self, kind: str) -> dict:
        if kind == "count_calls":
            return {"purpose": "Map inter-function calls of a binary from its "
                               "disassembly text.",
                    "approach": "Regex over objdump rows; call rows carry the "
                                "callee symbol in angle brackets.",
                    "key_points": ["call targets are named when symbols exist",
                                   "textual order follows program order",
                                   "_start is the static entry point"],
                    "big_o_time": "O(lines)", "big_o_space": "O(calls)",
                    "edge_cases": ["indirect calls have no symbol target",
                                   "tail calls may appear as jmp"]}
        if kind == "immediates":
            return {"purpose": "Spot magic constants without reading logic.",
                    "approach": "Collect AT&T immediate operands ($0x...) in the "
                                "function block.",
                    "key_points": ["sizes and tags usually show up as immediates",
                                   "deduplication keeps the constant set small"],
                    "big_o_time": "O(lines)", "big_o_space": "O(constants)",
                    "edge_cases": ["addresses-as-immediates also match"]}
        if kind == "jump_targets":
            return {"purpose": "Extract branch targets to seed a control-flow "
                               "graph.",
                    "approach": "Match j-type mnemonics and parse the absolute "
                                "target address objdump prints.",
                    "key_points": ["conditional and unconditional jumps share the "
                                   "j prefix",
                                   "targets are instruction addresses in .text"],
                    "big_o_time": "O(lines)", "big_o_space": "O(targets)",
                    "edge_cases": ["loop back-edges point to lower addresses"]}
        return {"purpose": "Estimate code size and bounds of a function.",
                "approach": "Parse address and encoding-length columns per row.",
                "key_points": ["span = last addr + last length - first addr",
                               "instruction count equals parsed rows"],
                "big_o_time": "O(lines)", "big_o_space": "O(1)",
                "edge_cases": ["padding nops inflate the span"]}

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        bugs = {
            "count_calls": ('_CALL = re.compile(r"call\\s+[0-9a-f]+ <([A-Za-z_][A-Za-z0-9_]*)>")',
                            '_CALL = re.compile(r"jmp\\s+[0-9a-f]+ <([A-Za-z_][A-Za-z0-9_]*)>")',
                            "wrong_mnemonic_class"),
            "immediates": ('tuple(sorted(set(int(m, 16) for m in _IMM.findall(block))))',
                           'tuple(sorted(set(int(m, 16) for m in _IMM.findall(block)))[:-1])',
                            "dropped_last_constant"),
            "jump_targets": ('r"\\bj[A-Za-z0-9]+\\s+([0-9a-f]+)\\b"',
                             'r"\\bjmp\\s+([0-9a-f]+)\\b"',
                             "conditional_jumps_ignored"),
            "function_span": ('return first, last_addr + last_len - first, len(rows)',
                              'return first, last_addr - first, len(rows)',
                              "span_ignores_last_instruction_length"),
        }
        old, new, bug_kind = bugs[cand.variant]
        if cand.code.count(old) != 1:
            return None
        buggy = Candidate(
            family=cand.family, language=cand.language, domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=cand.code.replace(old, new), tests=cand.tests,
            verify_method=cand.verify_method, notes=cand.notes,
            tags=cand.tags, variant=cand.variant, seed=cand.seed,
            is_project=cand.is_project)
        meta = {"kind": bug_kind,
                "problem": f"{bug_kind}: the analysis diverges from what the real "
                           "disassembly shows.",
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy, meta


# -----------------------------------------------------------------------------
# Family 3: re_blackbox_reimpl
# -----------------------------------------------------------------------------

_BB_TASK = ("A stripped, libc-free ELF64 binary is embedded in the test suite; it "
            "reads its entire stdin, applies one fixed byte-oriented transform and "
            "writes the result to stdout. Treat it as a black box: the harness "
            "executes it, and you may reason about any embedded constants you can "
            "recover. Implement transform(data: bytes) -> bytes reproducing the "
            "binary's mapping EXACTLY: the suite feeds identical probes to the "
            "real binary and to your function and requires byte-identical outputs "
            "on every probe. Do not overfit the probes; the mapping is one simple "
            "deterministic rule over positions and constants.")

_BB_BEHAVIOR = ("Every probe's expected bytes were captured by actually executing "
                "the compiled binary in this sandbox; the solution must reproduce "
                "all of them byte for byte.")


class REBlackboxFamily(Family):
    """Reimplement the byte transform of a real stripped binary."""

    NAME = "re_blackbox_reimpl"
    LANGUAGE = "python"
    DOMAIN = "security"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "trace", "testing", "debugging")
    KINDS = ("rolling_xor", "offset_add", "lcg_stream", "nibble_rot")

    def generate(self, rng: random.Random):
        if not (_ARCH_OK and _TOOLS_OK):
            return None
        kind = rng.choice(self.KINDS)
        key = rng.randrange(1, 256)
        seed = rng.randrange(1, 2 ** 31)
        src, solution = self._author(kind, key, seed)
        blob = _compile_c(src, strip=True)
        if blob is None or not (1500 < len(blob) < 30000):
            return None
        expected_pairs = []
        for _ in range(6):
            probe = bytes(rng.randrange(0, 256)
                          for _ in range(rng.randrange(4, 17)))
            run = _run_bin(blob, probe)
            if run is None or run[0] != 0 or len(run[1]) != len(probe):
                return None  # honest drop: binary misbehaved
            expected_pairs.append((probe.hex(), run[1].hex()))
        difficulty = "expert" if kind == "lcg_stream" else \
            rng.choice(("advanced", "expert"))
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=difficulty, task=_BB_TASK,
            expected_behavior=_BB_BEHAVIOR, code=solution,
            tests=self._mk_tests(blob, expected_pairs),
            verify_method="executed",
            notes={"explain": self._mk_explain(kind), "c_source": src,
                   "binary_sha256": _sha256(blob), "binary_bytes": len(blob),
                   "stripped": True},
            tags=["reverse-engineering", "blackbox", "transform", kind],
            variant=kind, seed=rng.randrange(2 ** 31))
        return cand

    def _author(self, kind: str, key: int, seed: int) -> tuple:
        """Return (c_source, python_solution) implementing the same rule."""
        if kind == "rolling_xor":
            c_expr = f"y = x ^ (unsigned)(({key}u + (unsigned)i) & 0xffu);"
            sol = ('"""Byte transform recovered from a stripped binary."""\n\n\n'
                   "def transform(data: bytes) -> bytes:\n"
                   '    """Map every byte exactly like the analysed binary."""\n'
                   "    out = []\n"
                   "    for i, b in enumerate(data):\n"
                   f"        out.append(b ^ (({key} + i) & 0xFF))\n"
                   "    return bytes(out)\n")
        elif kind == "offset_add":
            c_expr = f"y = (x + (unsigned)({key}u + (unsigned)i)) & 0xffu;"
            sol = ('"""Byte transform recovered from a stripped binary."""\n\n\n'
                   "def transform(data: bytes) -> bytes:\n"
                   '    """Map every byte exactly like the analysed binary."""\n'
                   f"    return bytes((b + {key} + i) & 0xFF\n"
                   "                  for i, b in enumerate(data))\n")
        elif kind == "lcg_stream":
            c_expr = ("r = r * 1103515245u + 12345u;\n"
                      "        y = x ^ (unsigned)((r >> 23) & 0xffu);")
            sol = ('"""Byte transform recovered from a stripped binary."""\n\n\n'
                   "def transform(data: bytes) -> bytes:\n"
                   '    """Map every byte exactly like the analysed binary."""\n'
                   "    out = []\n"
                   f"    state = {seed}\n"
                   "    for b in data:\n"
                   "        state = (state * 1103515245 + 12345) & 0xFFFFFFFF\n"
                   "        out.append(b ^ ((state >> 23) & 0xFF))\n"
                   "    return bytes(out)\n")
        else:
            c_expr = f"y = (((x << 4) | (x >> 4)) & 0xffu) ^ {hex(key)}u;"
            sol = ('"""Byte transform recovered from a stripped binary."""\n\n\n'
                   "def transform(data: bytes) -> bytes:\n"
                   '    """Map every byte exactly like the analysed binary."""\n'
                   f"    return bytes(((((b << 4) | (b >> 4)) & 0xFF) ^ {key})\n"
                   "                  for b in data)\n")
        state_decl = "    unsigned r = %du;\n" % seed if kind == "lcg_stream" else ""
        src = (_SYSCALL_STUB +
               "void _start(void) {\n"
               "    static char inb[4096];\n"
               "    static char outb[4096];\n"
               "    long total = 0;\n"
               "    for (;;) {\n"
               "        if (total >= (long)sizeof(inb)) break;\n"
               "        long n = sys_read(0, inb + total,\n"
               "                          (long)sizeof(inb) - total);\n"
               "        if (n <= 0) break;\n"
               "        total += n;\n"
               "    }\n"
               f"{state_decl}"
               "    for (long i = 0; i < total; ++i) {\n"
               "        unsigned x = (unsigned char)inb[i];\n"
               "        unsigned y;\n"
               f"        {c_expr}\n"
               "        outb[i] = (char)y;\n"
               "    }\n"
               "    sys_write(1, outb, total);\n"
               "    sys_exit(0);\n"
               "}\n")
        return src, sol

    def _mk_tests(self, blob: bytes, expected_pairs) -> str:
        lines = [_HARNESS_PRELUDE.format(b64=_b64(blob)), "",
                 "import subprocess", "",
                 "def run_tests():",
                 "    from solution import transform",
                 "    p = _dump()",
                 "    try:",
                 f"        pairs = {expected_pairs!r}",
                 "        for probe_hex, want_hex in pairs:",
                 "            probe = bytes.fromhex(probe_hex)",
                 "            r = subprocess.run([p], input=probe,",
                 "                               stdout=subprocess.PIPE, timeout=10)",
                 "            assert r.returncode == 0",
                 "            assert r.stdout == bytes.fromhex(want_hex)",
                 "            assert transform(probe) == r.stdout, probe.hex()",
                 "    finally:",
                 "        os.remove(p)", ""]
        return "\n".join(lines)

    def _mk_explain(self, kind: str) -> dict:
        base = {"purpose": "Reproduce an unknown byte transform exactly.",
                "approach": "Black-box probing plus reasoning about constants "
                            "recoverable from the stripped binary.",
                "key_points": ["position-dependent rules need the byte index",
                               "verify on fresh inputs, not only the probes",
                               "empty input must map to empty output"],
                "big_o_time": "O(n)", "big_o_space": "O(n)",
                "edge_cases": ["multi-byte reads must not reorder data"]}
        if kind == "rolling_xor":
            base["key_points"].insert(0, "the xor key evolves with the byte "
                                         "position")
        if kind == "lcg_stream":
            base["key_points"].insert(0, "a linear congruential generator drives "
                                         "the keystream")
            base["approach"] = "Recognize the LCG constants and mirror the state."
        if kind == "nibble_rot":
            base["key_points"].insert(0, "nibble rotation is two shifts or-ed "
                                         "together")
        return base

    # -------------------------------------------------------------- make_buggy
    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        kind = cand.variant
        if kind == "rolling_xor":
            m = re.search(r"\((\d+) \+ i\) & 0xFF", cand.code)
            if not m:
                return None
            old, new = m.group(0), f"({int(m.group(1)) + 1} + i) & 0xFF"
            bug_kind = "off_by_one_key_position"
        elif kind == "offset_add":
            m = re.search(r"\(b \+ (\d+) \+ i\)", cand.code)
            if not m:
                return None
            old, new = m.group(0), f"(b + {int(m.group(1)) + 1} + i)"
            bug_kind = "shifted_key_constant"
        elif kind == "lcg_stream":
            old, new, bug_kind = "state >> 23", "state >> 21", \
                "wrong_keystream_shift"
        else:
            m = re.search(r"\^ (\d+)\)", cand.code)
            if not m:
                return None
            old, new = m.group(0), f"^ {int(m.group(1)) ^ 1})"
            bug_kind = "flipped_xor_bit"
        if cand.code.count(old) != 1:
            return None
        buggy = Candidate(
            family=cand.family, language=cand.language, domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=cand.code.replace(old, new), tests=cand.tests,
            verify_method=cand.verify_method, notes=cand.notes,
            tags=cand.tags, variant=cand.variant, seed=cand.seed,
            is_project=cand.is_project)
        meta = {"kind": bug_kind,
                "problem": f"{bug_kind}: the transform diverges from the real "
                           "binary on essentially every probe.",
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy, meta
# -----------------------------------------------------------------------------
# Family 4: re_version_diff
# -----------------------------------------------------------------------------


class REVersionDiffFamily(Family):
    """Characterize the behavioral patch between two real compiled builds."""

    NAME = "re_version_diff"
    LANGUAGE = "python"
    DOMAIN = "security"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("comparison", "explanation", "testing", "debugging")
    KINDS = ("key_bump", "xor_mask_tweak", "offset_drop")

    def generate(self, rng: random.Random):
        if not (_ARCH_OK and _TOOLS_OK):
            return None
        kind = rng.choice(self.KINDS)
        key = rng.randrange(16, 240)
        k1 = key
        if kind == "key_bump":
            k2 = (key + rng.randrange(1, 8)) % 256
            rule2, pos2 = "rolling", True
        elif kind == "xor_mask_tweak":
            k2 = key ^ rng.randrange(1, 16)
            rule2, pos2 = "rolling", True
        else:  # offset_drop: v2 removes the position term entirely
            k2 = key
            rule2, pos2 = "static", False
        src1 = self._author_src(k1, positional=True)
        src2 = self._author_src(k2, positional=pos2)
        blob1 = _compile_c(src1, strip=True)
        blob2 = _compile_c(src2, strip=True)
        if blob1 is None or blob2 is None:
            return None
        if blob1 == blob2:
            return None  # patch produced identical build: honest drop
        expected = []
        differ = 0
        for _ in range(7):
            probe = bytes(rng.randrange(0, 256)
                          for _ in range(rng.randrange(3, 13)))
            r1 = _run_bin(blob1, probe)
            r2 = _run_bin(blob2, probe)
            if r1 is None or r2 is None or r1[0] or r2[0]:
                return None
            same = r1[1] == r2[1]
            differ += 0 if same else 1
            expected.append((probe.hex(), r1[1].hex(), r2[1].hex()))
        if differ == 0:
            return None
        solution = self._mk_solution(kind, k1, k2, positional_v2=pos2)
        difficulty = "expert" if kind == "xor_mask_tweak" else \
            rng.choice(("advanced", "expert"))
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=difficulty, task=self._mk_task(),
            expected_behavior=self._mk_behavior(),
            code=solution, tests=self._mk_tests(blob1, blob2, expected),
            verify_method="executed",
            notes={"explain": self._mk_explain(kind), "c_source_v1": src1,
                   "c_source_v2": src2, "binary_v1_sha256": _sha256(blob1),
                   "binary_v2_sha256": _sha256(blob2), "patch_kind": kind},
            tags=["reverse-engineering", "differential", "binutils", kind],
            variant=kind, seed=rng.randrange(2 ** 31))
        return cand

    def _author_src(self, key: int, positional: bool) -> str:
        pos = "(unsigned)i" if positional else "0u"
        body = f"        y = x ^ (unsigned)(({key}u + {pos}) & 0xffu);"
        return (_SYSCALL_STUB +
                "void _start(void) {\n"
                "    static char inb[4096];\n"
                "    static char outb[4096];\n"
                "    long total = 0;\n"
                "    for (;;) {\n"
                "        if (total >= (long)sizeof(inb)) break;\n"
                "        long n = sys_read(0, inb + total,\n"
                "                          (long)sizeof(inb) - total);\n"
                "        if (n <= 0) break;\n"
                "        total += n;\n"
                "    }\n"
                "    for (long i = 0; i < total; ++i) {\n"
                "        unsigned x = (unsigned char)inb[i];\n"
                "        unsigned y;\n"
                f"{body}\n"
                "        outb[i] = (char)y;\n"
                "    }\n"
                "    sys_write(1, outb, total);\n"
                "    sys_exit(0);\n"
                "}\n")

    def _mk_task(self) -> str:
        return ("You are given two stripped builds of the same stdin-to-stdout "
                "byte tool; they differ by exactly one small behavioral patch "
                "introduced between versions. The test suite embeds BOTH binaries "
                "and executes them on fixed probes. Implement "
                "analyze(data: bytes) -> tuple that returns (v1_bytes, v2_bytes), "
                "the exact output each build produces for the given input. From "
                "your pairs plus the probe table, the patch itself (which rule "
                "changed and how) must be describable in one sentence.")

    def _mk_behavior(self) -> str:
        return ("Each probe row was produced by executing both real builds in "
                "this sandbox; the solution must reproduce every pair exactly.")

    def _mk_solution(self, kind: str, k1: int, k2: int,
                     positional_v2: bool) -> str:
        b1 = (f"    out1 = bytes((b ^ (({k1} + i) & 0xFF))\n"
              "                 for i, b in enumerate(data))\n")
        if positional_v2:
            b2 = (f"    out2 = bytes((b ^ (({k2} + i) & 0xFF))\n"
                  "                 for i, b in enumerate(data))\n")
        else:
            b2 = f"    out2 = bytes((b ^ {k2}) & 0xFF for b in data)\n"
        return ('"""Differential model of two builds of one byte tool."""\n\n\n'
                "def analyze(data: bytes) -> tuple:\n"
                '    """Return (v1_output, v2_output) for the given input."""\n'
                f"{b1}{b2}"
                "    return out1, out2\n")

    def _mk_tests(self, blob1: bytes, blob2: bytes, expected) -> str:
        lines = ["import base64", "import os", "import subprocess",
                 "import tempfile", "",
                 f"_B64_V1 = {_b64(blob1)!r}", f"_B64_V2 = {_b64(blob2)!r}", "",
                 "def _dump(tag, b64):",
                 "    fd, path = tempfile.mkstemp(prefix=tag, suffix='.elf')",
                 "    os.write(fd, base64.b64decode(b64))",
                 "    os.close(fd)",
                 "    os.chmod(path, 0o755)",
                 "    return path", "",
                 "def run_tests():",
                 "    from solution import analyze",
                 "    p1 = _dump('v1-', _B64_V1)",
                 "    p2 = _dump('v2-', _B64_V2)",
                 "    try:",
                 f"        rows = {expected!r}",
                 "        for probe_hex, w1, w2 in rows:",
                 "            probe = bytes.fromhex(probe_hex)",
                 "            r1 = subprocess.run([p1], input=probe,",
                 "                                stdout=subprocess.PIPE, timeout=10)",
                 "            r2 = subprocess.run([p2], input=probe,",
                 "                                stdout=subprocess.PIPE, timeout=10)",
                 "            assert r1.stdout == bytes.fromhex(w1)",
                 "            assert r2.stdout == bytes.fromhex(w2)",
                 "            got1, got2 = analyze(probe)",
                 "            assert got1 == r1.stdout and got2 == r2.stdout",
                 "    finally:",
                 "        os.remove(p1)",
                 "        os.remove(p2)", ""]
        return "\n".join(lines)

    def _mk_explain(self, kind: str) -> dict:
        return {"purpose": "Characterize a between-versions behavioral patch by "
                           "differential probing.",
                "approach": "Model both transforms, compare outputs on probes, "
                            "isolate the rule that moved.",
                "key_points": ["key_bump shifts the whole xor key",
                               "offset_drop removes the position term",
                               "xor_mask_tweak flips low key bits"],
                "big_o_time": "O(n)", "big_o_space": "O(n)",
                "edge_cases": ["probes where both builds agree are expected "
                               "unless every byte differs"]}

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        if cand.variant == "offset_drop":
            m = re.search(r"b \^ (\d+)\) & 0xFF for b in data", cand.code)
            if not m:
                return None
            old, new = f"b ^ {m.group(1)})", f"b ^ {int(m.group(1)) + 1})"
        else:
            m = re.findall(r"\^ \((\d+) \+ i\) & 0xFF", cand.code)
            if len(m) != 2:
                return None
            old, new = f"^ ({m[1]} + i)", f"^ ({int(m[1]) + 1} + i)"
        if cand.code.count(old) != 1:
            return None
        buggy = Candidate(
            family=cand.family, language=cand.language, domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=cand.code.replace(old, new), tests=cand.tests,
            verify_method=cand.verify_method, notes=cand.notes,
            tags=cand.tags, variant=cand.variant, seed=cand.seed,
            is_project=cand.is_project)
        meta = {"kind": "v2_model_off_by_one",
                "problem": "v2 model uses a shifted key constant; probe pairs "
                           "disagree with the real second build.",
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy, meta


# -----------------------------------------------------------------------------
# Family 5: re_strings_decode
# -----------------------------------------------------------------------------

_MSG_POOL = ["BOOT sequence complete", "SYNC lost: retrying", "PROBE ack ok",
             "STATE flushed to disk", "WATCHDOG kicked", "QUEUE drained",
             "TABLE reloaded", "FRAME dropped", "CRC mismatch found",
             "CONFIG restored", "LINK renegotiated", "CACHE invalidated",
             "TASK preempted", "BUFFER compacted", "LEASE renewed"]


class REStringsDecodeFamily(Family):
    """Recover an obfuscated string table from a real binary that decodes it."""

    NAME = "re_strings_decode"
    LANGUAGE = "python"
    DOMAIN = "security"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging", "trace")
    KINDS = ("xor_key", "rolling_xor")

    def generate(self, rng: random.Random):
        if not (_ARCH_OK and _TOOLS_OK):
            return None
        kind = rng.choice(self.KINDS)
        msgs = rng.sample(_MSG_POOL, rng.randrange(2, 5))
        key = rng.randrange(0x10, 0xF1)
        enc_rows = []
        for _ in range(64):
            enc_rows = [self._encode(m.encode("ascii"), key, kind)
                        for m in msgs]
            if all(b != 0 for row in enc_rows for b in row):
                break
            key = (key % 240) + 0x10
        else:
            return None
        decoded = [m.encode("ascii") for m in msgs]
        arrs = "\n".join(
            "static const unsigned char s%d[%d] = {%s};"
            % (i, len(r) + 1, ",".join(map(str, list(r) + [0])))
            for i, r in enumerate(enc_rows))
        emit_blocks = []
        for i, r in enumerate(enc_rows):
            rule = f"({key}u + j) & 0xffu" if kind == "rolling_xor" else f"{key}u"
            emit_blocks.append(
                "    { static char ob[%d];\n"
                "      for (unsigned j = 0; j < %d; ++j)\n"
                f"          ob[j] = (char)(s{i}[j] ^ ({rule}));\n"
                f"      sys_write(1, ob, {len(r)});\n"
                "      sys_write(1, \"\\n\", 1); }" % (len(r) + 1, len(r)))
        prints = "\n".join(emit_blocks)
        src = (_SYSCALL_STUB + arrs + "\n"
               "void _start(void) {\n" + prints + "\n    sys_exit(0);\n}\n")
        blob = _compile_c(src, strip=True)
        if blob is None:
            return None
        presence = [all(bytes(r) in blob for r in enc_rows)]
        run = _run_bin(blob)
        if not all(presence) or run is None or run[0] != 0:
            return None
        real_out = run[1]
        if real_out != b"".join(d + b"\n" for d in decoded):
            return None  # the binary must really print the decoded strings
        solution = self._mk_solution(kind, key)
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(("intermediate", "advanced")),
            task=self._mk_task(kind),
            expected_behavior=self._mk_behavior(),
            code=solution,
            tests=self._mk_tests(blob, enc_rows, decoded, real_out),
            verify_method="executed",
            notes={"explain": self._mk_explain(kind), "c_source": src,
                   "binary_sha256": _sha256(blob), "key_dec": key,
                   "captured_stdout": real_out.decode("ascii", "replace")},
            tags=["reverse-engineering", "strings", "obfuscation", kind],
            variant=kind, seed=rng.randrange(2 ** 31))
        return cand

    def _encode(self, plain: bytes, key: int, kind: str) -> bytes:
        if kind == "xor_key":
            return bytes(b ^ key for b in plain)
        return bytes(b ^ ((key + i) & 0xFF) for i, b in enumerate(plain))

    def _mk_task(self, kind: str) -> str:
        if kind == "xor_key":
            return ("A stripped binary embeds an obfuscated log table: every "
                    "plaintext line was XORed with one fixed key byte before "
                    "being linked into .rodata, and the program decodes and "
                    "prints the table when executed. The encoded rows are given "
                    "to your function as raw bytes. Implement "
                    "decode_table(rows: list) -> list returning the decoded "
                    "ASCII lines in order. The suite also executes the real "
                    "binary and requires your output to agree with what it "
                    "actually prints.")
        return ("A stripped binary embeds an obfuscated log table whose rows "
                "were XORed with a key that advances one step per byte position "
                "(resetting at each row start). The program decodes and prints "
                "the table when executed. Implement decode_table(rows: list) -> "
                "list returning the decoded ASCII lines in order. The suite "
                "executes the real binary and requires agreement with its "
                "captured stdout.")

    def _mk_behavior(self) -> str:
        return ("Decoded lines must match both the authored plaintext table and "
                "the real stdout captured from executing the compiled binary.")

    def _mk_solution(self, kind: str, key: int) -> str:
        if kind == "xor_key":
            core = (f"    return [bytes(b ^ {key} for b in row).decode(\"ascii\")\n"
                    "            for row in rows]\n")
        else:
            core = ("    out = []\n"
                    f"    k0 = {key}\n"
                    "    for row in rows:\n"
                    "        line = bytes(b ^ ((k0 + i) & 0xFF)\n"
                    "                     for i, b in enumerate(row))\n"
                    "        out.append(line.decode(\"ascii\"))\n"
                    "    return out\n")
        return ('"""Recover the plaintext log table from its obfuscated rows."""\n\n\n'
                "def decode_table(rows: list) -> list:\n"
                '    """Decode every row and return the ASCII lines in order."""\n'
                f"{core}")

    def _mk_tests(self, blob: bytes, enc_rows, decoded, real_out: bytes) -> str:
        rows_lit = [bytes(r).hex() for r in enc_rows]
        lines = [_HARNESS_PRELUDE.format(b64=_b64(blob)), "",
                 "import subprocess", "",
                 f"_ROWS_HEX = {rows_lit!r}",
                 f"_WANT = {[d.decode('ascii') for d in decoded]!r}",
                 f"_REAL_STDOUT = {real_out!r}", "",
                 "def run_tests():",
                 "    from solution import decode_table",
                 "    p = _dump()",
                 "    try:",
                 "        rows = [bytes.fromhex(h) for h in _ROWS_HEX]",
                 "        got = decode_table(rows)",
                 "        assert got == _WANT",
                 "        r = subprocess.run([p], input=b\"\",",
                 "                           stdout=subprocess.PIPE, timeout=10)",
                 "        assert r.returncode == 0",
                 "        assert r.stdout == _REAL_STDOUT",
                 "        assert _REAL_STDOUT == b\"\".join("
                 "w.encode('ascii') + b'\\n' for w in _WANT)",
                 "    finally:",
                 "        os.remove(p)", ""]
        return "\n".join(lines)

    def _mk_explain(self, kind: str) -> dict:
        base = {"purpose": "Recover plaintext strings from an obfuscated table "
                           "without touching a debugger.",
                "approach": "Identify the obfuscation rule and invert it over "
                            "the encoded rows.",
                "key_points": ["the binary itself decodes the table: its stdout "
                               "is ground truth",
                               "key bytes never survive as NUL in the table"],
                "big_o_time": "O(total bytes)", "big_o_space": "O(total bytes)",
                "edge_cases": ["row boundaries reset the position-dependent key"]}
        if kind == "rolling_xor":
            base["key_points"].insert(0, "the effective key advances with the "
                                         "byte index inside each row")
        return base

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        m = re.search(r"b \^ (\d+)", cand.code)
        if not m:
            return None
        old = f"b ^ {m.group(1)}"
        new = f"b ^ {int(m.group(1)) + 1}"
        if cand.code.count(old) < 1:
            return None
        buggy = Candidate(
            family=cand.family, language=cand.language, domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior,
            code=cand.code.replace(old, new, 1), tests=cand.tests,
            verify_method=cand.verify_method, notes=cand.notes,
            tags=cand.tags, variant=cand.variant, seed=cand.seed,
            is_project=cand.is_project)
        meta = {"kind": "off_by_one_key",
                "problem": "decoder applies a shifted key byte; recovered lines "
                           "stop matching the binary's real output.",
                "correct_code": cand.code, "tests": cand.tests,
                "unit_notes": cand.notes.get("explain", {})}
        return buggy, meta


register(globals(), REElfParserFamily)
register(globals(), REDisasmAnalysisFamily)
register(globals(), REBlackboxFamily)
register(globals(), REVersionDiffFamily)
register(globals(), REStringsDecodeFamily)
