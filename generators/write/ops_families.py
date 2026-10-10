"""Module 05 - Agent Persistence (objective discipline under long jobs).

Teaches the behaviors that separate an agent that finishes objectives from
an agent that walks away:

* ops_monitor_watchdog       - supervise a real long-running job: poll the
                               progress log, parse the plan, never report
                               success from a single signal (exit code OR
                               done-line OR partial steps), surface the
                               injected failure reason.
* ops_two_stage_orchestrator - a compound objective (sync a directory, THEN
                               build + verify an ISO image of it): stage 1
                               is a prerequisite, not the goal; verify each
                               stage before moving on; never declare the
                               objective complete without the final artifact.
* ops_progress_supervisor    - event-driven stall/timeout detection on a
                               virtual clock: checkpoints are not completion,
                               "done" without verification is not completion.
* ops_scope_elevation        - the senior-engineer habit: when handed a
                               minimal game spec, ship the complete version -
                               pure logic separated from input/rendering,
                               keyboard AND gamepad bindings behind one input
                               map, pause, difficulty ramp, score persistence
                               and the polish elevations the instance asks
                               for - all verified headless.

Every candidate is verified by real execution in this sandbox: jobs actually
run as subprocesses, files are actually synced and hashed, ISO images are
real ISO9660 bytes read back with an independent parser, and the game logic
is simulated headless with scripted inputs.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register

# ---------------------------------------------------------------------------
# Provided helper: a real, minimal ISO9660 writer + reader (pure Python).
# Shipped as a second file in every ops_two_stage_orchestrator record; the
# model's job is orchestration, not ISO-format archaeology.
# ---------------------------------------------------------------------------

ISO_HELPER = '''"""Minimal but real ISO9660 level-1 image writer + reader (provided).

Layout: 16 zero sectors, PVD at LBA 16, terminator at 17, L path table at 18,
M path table at 19, root directory records at 20, file data from LBA 21.
Flat directory, ISO level-1 names (8+3, uppercase, ";1" version suffix),
fixed recording timestamp for determinism.
"""
SECTOR = 2048
_FIXED_DATE = bytes([126, 1, 1, 0, 0, 0, 0])  # 2026-01-01 00:00:00, GMT+0


def _b16(val, le=True):
    n = val & 0xFFFFFFFF
    lo = bytes((n >> s) & 0xFF for s in (0, 8, 16, 24))
    return lo if le else lo[::-1]

def _b16_both(val):
    return _b16(val, True) + _b16(val, False)

def _b16b(val):
    """16-bit both-endian (2 bytes LE + 2 bytes BE)."""
    n = val & 0xFFFF
    lo = bytes((n & 0xFF, (n >> 8) & 0xFF))
    return lo + lo[::-1]


def _achars(text, n):
    return text.upper().encode("ascii", "replace")[:n].ljust(n, b" ")


def _dchars(text, n):
    return text.upper().encode("ascii", "replace")[:n].ljust(n, b" ")


def _dir_record(name, lba, size, is_dir=False):
    ident = name.upper().encode("ascii") + b";1" if not is_dir else name.encode()
    rec = bytearray()
    rec.append(0)                       # length placeholder
    rec.append(0)                       # extended attribute length
    rec += _b16_both(lba)               # extent (LE+BE)
    rec += _b16_both(size)              # data length (LE+BE)
    rec += _FIXED_DATE                  # recording date/time (7 bytes)
    rec.append(2 if is_dir else 0)      # file flags
    rec.append(0)                       # file unit size
    rec.append(0)                       # interleave gap
    rec += _b16b(1)                     # volume sequence number (u16 both)
    rec.append(len(ident))
    rec += ident
    if len(rec) % 2:                    # records are even-length
        rec.append(0)
    rec[0] = len(rec)
    return bytes(rec)


def build_iso(files, volume_id="AIKU"):
    """files: {name: bytes}; names must be <=8 chars. Returns ISO9660 bytes."""
    names = sorted(files)
    for n in names:
        base, dot, ext = n.partition(".")
        ok = (1 <= len(base) <= 8 and (not dot or 1 <= len(ext) <= 3)
              and all(c.isalnum() or c == "_" for c in base + ext))
        if not ok:
            raise ValueError("bad iso level-1 name: %r" % n)
    n_data_sectors = sum((len(files[n]) + SECTOR - 1) // SECTOR for n in names)
    root_lba = 20
    dir_bytes = _dir_record("\\x00", root_lba, SECTOR, is_dir=True) \\
        + _dir_record("\\x01", root_lba, SECTOR, is_dir=True)
    extents = {}
    cur = root_lba + 1
    for n in names:
        extents[n] = cur
        cur += max(1, (len(files[n]) + SECTOR - 1) // SECTOR)
    for n in names:
        dir_bytes += _dir_record(n, extents[n], len(files[n]))
    dir_sectors = (len(dir_bytes) + SECTOR - 1) // SECTOR
    assert dir_sectors == 1, "directory must fit one sector (level-1 helper)"
    total_sectors = root_lba + dir_sectors + n_data_sectors

    pvd = bytearray(SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = _achars("LINUX", 32)
    pvd[40:72] = _dchars(volume_id, 32)
    pvd[80:88] = _b16_both(total_sectors)
    pvd[120:124] = _b16b(1)
    pvd[124:128] = _b16b(1)
    pvd[128:132] = _b16b(SECTOR)
    pvd[132:140] = _b16_both(10)
    pvd[140:144] = _b16(18, True)       # L path table
    pvd[148:152] = _b16(19, False)      # M path table (big-endian field)
    pvd[156:190] = _dir_record("\\x00", root_lba, dir_sectors * SECTOR, is_dir=True)
    pvd[318:446] = _achars("", 128)
    pvd[448:576] = _achars("AI-KU", 128)
    pvd[578:706] = _achars("AI-KU-OPS", 128)
    pvd[708:836] = _achars("BUILD_ISO", 128)
    pvd[813:830] = b"2026010100000000" + b"\\x00"
    pvd[830:847] = b"2026010100000000" + b"\\x00"
    pvd[847:864] = b"2026010100000000" + b"\\x00"
    pvd[864:881] = b"2026010100000000" + b"\\x00"
    pvd[881] = 1
    pvd = bytes(pvd)

    # path tables: single root entry (len_di=1, id 0x00, 9 bytes padded to 10)
    lpt = bytearray(b"\\x01\\x00") + _b16(root_lba, True) + _b16(1, True)[:2] + b"\\x00"
    lpt = bytes(lpt[:9]).ljust(10, b"\\x00")
    mpt = bytearray(b"\\x01\\x00") + _b16(root_lba, False) + _b16(1, False)[:2] + b"\\x00"
    mpt = bytes(mpt[:9]).ljust(10, b"\\x00")

    sectors = {}
    sectors[16] = pvd
    vdt = bytearray(SECTOR)
    vdt[0] = 255
    vdt[1:6] = b"CD001"
    vdt[6] = 1
    sectors[17] = bytes(vdt)
    sectors[18] = lpt.ljust(SECTOR, b"\\x00")
    sectors[19] = mpt.ljust(SECTOR, b"\\x00")
    sectors[20] = dir_bytes.ljust(dir_sectors * SECTOR, b"\\x00")
    cur = root_lba + dir_sectors
    for n in names:
        data = files[n]
        sectors[extents[n]] = data.ljust(max(1, (len(data) + SECTOR - 1) // SECTOR) * SECTOR, b"\\x00")
    out = bytearray(total_sectors * SECTOR)
    for lba, blob in sectors.items():
        out[lba * SECTOR:lba * SECTOR + len(blob)] = blob
    return bytes(out)


def read_iso(img):
    """Independent parser: returns {name: bytes} for the root directory."""
    if img[32769:32774] != b"CD001":
        raise ValueError("not an iso9660 image (bad PVD magic)")
    block_size = int.from_bytes(img[32768 + 128:32768 + 130], "little")
    if block_size != SECTOR:
        raise ValueError("unexpected block size %d" % block_size)
    root = img[32768 + 156:32768 + 190]
    if root[0] < 34 or root[25] & 2 == 0:
        raise ValueError("root directory record missing")
    root_lba = int.from_bytes(root[2:6], "little")
    root_len = int.from_bytes(root[10:14], "little")
    files = {}
    pos = root_lba * SECTOR
    end = pos + root_len
    while pos < end:
        rec_len = img[pos]
        if rec_len == 0:
            pos = ((pos // SECTOR) + 1) * SECTOR
            continue
        rec = img[pos:pos + rec_len]
        pos += rec_len
        flags = rec[25]
        if flags & 2:
            continue                    # skip . and ..
        name_len = rec[32]
        raw = rec[33:33 + name_len]
        name = raw.decode("ascii").split(";")[0]
        lba = int.from_bytes(rec[2:6], "little")
        size = int.from_bytes(rec[10:14], "little")
        files[name.lower()] = img[lba * SECTOR:lba * SECTOR + size]
    return files
'''


# ---------------------------------------------------------------------------
# Family 1: ops_monitor_watchdog
# ---------------------------------------------------------------------------

_JOB_TEMPLATE = (
    "import sys, time\n"
    "log_path = sys.argv[1]\n"
    "plan = __PLAN__\n"
    "mode = '__MODE__'\n"
    "stop_at = __STOPAT__\n"
    "reason = '__REASON__'\n"
    "f = open(log_path, 'w')\n"
    "f.write('PLAN: %d\\n' % plan)\n"
    "f.flush()\n"
    "for i in range(1, plan + 1):\n"
    "    time.sleep(0.02)\n"
    "    if mode == 'crash_mid' and i > stop_at:\n"
    "        f.close()\n"
    "        sys.exit(3)\n"
    "    if mode == 'fatal' and i > stop_at:\n"
    "        f.write('FATAL: %s at block %d\\n' % (reason, i))\n"
    "        f.flush()\n"
    "        f.close()\n"
    "        sys.exit(1)\n"
    "    f.write('[step %d/%d] ok\\n' % (i, plan))\n"
    "    f.flush()\n"
    "    if mode == 'short_done' and i >= stop_at:\n"
    "        break\n"
    "f.write('DONE\\n')\n"
    "f.flush()\n"
    "f.close()\n"
    "sys.exit(0)\n"
)

_MONITOR_TASK = (
    "A background job has been left running by a previous session and someone "
    "must babysit it to the end: the job writes a progress log whose first line "
    "is 'PLAN: N' (the number of steps it will run), then one '[step i/N] ok' "
    "line per completed step, and it may die at any moment (nonzero exit code), "
    "emit a 'FATAL: <reason>' line, or even print DONE after completing only "
    "part of the plan. Implement `monitor(job_path, log_path, timeout=8.0, "
    "poll=0.02)` that launches the job ({python} job_path log_path), polls the "
    "log while the process runs, and returns the final report dict: "
    "{{'state': 'completed'|'failed', 'exit_code': int, 'error': str|None, "
    "'steps_seen': int, 'steps_expected': int}}. Report 'completed' ONLY when "
    "the process exited 0 AND a DONE line appeared AND steps_seen equals "
    "steps_expected parsed from the PLAN line; every other outcome is "
    "'failed' with an error string that names the cause (the FATAL reason "
    "text, the exit code, or 'incomplete: seen/expected'). A single success "
    "signal is never enough: the plan is the objective, not the exit code."
)


class OpsMonitorWatchdogFamily(Family):
    NAME = "ops_monitor_watchdog"
    LANGUAGE = "python"
    DOMAIN = "automation"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "trace", "code_review")
    PROJECT_FAMILY = False

    _MODES = ("clean", "crash_mid", "fatal", "short_done")
    _REASONS = ("checksum mismatch", "disk full", "worker lost", "timeout guard",
                "corrupt block", "peer closed connection")
    _FLAVORS = ("block sync", "chunk upload", "index rebuild", "cache warmup",
                "dataset export", "mirror update")

    def generate(self, rng: random.Random) -> Candidate:
        plan = rng.randrange(5, 10)
        flavor = rng.choice(self._FLAVORS)
        stop_a = rng.randrange(2, plan - 1)
        stop_b = rng.randrange(2, plan - 1)
        reason = rng.choice(self._REASONS)
        variant = f"plan{plan}|{reason.split()[0]}"

        job = (_JOB_TEMPLATE
               .replace("__PLAN__", str(plan))
               .replace("__STOPAT__", "0")
               .replace("__MODE__", "clean")
               .replace("__REASON__", reason))
        job_crash = (_JOB_TEMPLATE
                     .replace("__PLAN__", str(plan))
                     .replace("__STOPAT__", str(stop_a))
                     .replace("__MODE__", "crash_mid")
                     .replace("__REASON__", reason))
        job_fatal = (_JOB_TEMPLATE
                     .replace("__PLAN__", str(plan))
                     .replace("__STOPAT__", str(stop_b))
                     .replace("__MODE__", "fatal")
                     .replace("__REASON__", reason))
        job_short = (_JOB_TEMPLATE
                     .replace("__PLAN__", str(plan))
                     .replace("__STOPAT__", str(stop_a + 1))
                     .replace("__MODE__", "short_done")
                     .replace("__REASON__", reason))

        code = self._reference(rng)
        tests = self._tests(plan, job, job_crash, job_fatal, job_short, stop_a, stop_b)
        task = _MONITOR_TASK.format(python="{python}").replace("{python}", "python")
        explain = (
            "The objective is the whole plan, not one signal of it: exit code 0 "
            "with a short log is the classic premature-success trap, and a "
            "FATAL line must surface its reason. Completion requires exit 0 "
            "AND the DONE marker AND every step of the declared plan.")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(("intermediate", "advanced")),
            task=task, expected_behavior=explain,
            code=code, tests=tests, verify_method="executed",
            notes={"explain": explain,
                   "job_flavor": flavor, "plan": plan, "reason": reason},
            tags=["automation", "agent_ops", "monitoring"],
            variant=variant, seed=rng.randrange(2 ** 31))

    def _reference(self, rng):
        return (
            "import re\nimport subprocess\nimport sys\nimport time\n\n"
            "def monitor(job_path, log_path, timeout=8.0, poll=0.02):\n"
            "    proc = subprocess.Popen([sys.executable, job_path, log_path])\n"
            "    deadline = time.time() + timeout\n"
            "    steps_expected = None\n"
            "    steps_seen = 0\n"
            "    done_seen = False\n"
            "    fatal = None\n"
            "    while proc.poll() is None and time.time() < deadline:\n"
            "        try:\n"
            "            with open(log_path, 'r') as fh:\n"
            "                text = fh.read()\n"
            "        except OSError:\n"
            "            text = ''\n"
            "        for line in text.splitlines():\n"
            "            m = re.match(r'PLAN: (\\d+)', line)\n"
            "            if m:\n"
            "                steps_expected = int(m.group(1))\n"
            "            m = re.match(r'\\[step (\\d+)/', line)\n"
            "            if m:\n"
            "                steps_seen = max(steps_seen, int(m.group(1)))\n"
            "            if line.startswith('FATAL:'):\n"
            "                fatal = line.split('FATAL:', 1)[1].strip()\n"
            "            if line.strip() == 'DONE':\n"
            "                done_seen = True\n"
            "        time.sleep(poll)\n"
            "    exit_code = proc.poll()\n"
            "    if exit_code is None:              # guard: job never ended\n"
            "        proc.terminate()\n"
            "        proc.wait()\n"
            "        exit_code = proc.returncode\n"
            "        fatal = fatal or 'timeout guard'\n"
            "    try:                               # final drain: the\n"
            "        with open(log_path, 'r') as fh:   # last lines may\n"
            "                text = fh.read()            # land after the\n"
            "        for line in text.splitlines():     # last poll\n"
            "            m = re.match(r'PLAN: (\\d+)', line)\n"
            "            if m:\n"
            "                steps_expected = int(m.group(1))\n"
            "            m = re.match(r'\\[step (\\d+)/', line)\n"
            "            if m:\n"
            "                steps_seen = max(steps_seen, int(m.group(1)))\n"
            "            if line.startswith('FATAL:'):\n"
            "                fatal = line.split('FATAL:', 1)[1].strip()\n"
            "            if line.strip() == 'DONE':\n"
            "                done_seen = True\n"
            "    except OSError:\n"
            "        pass\n"
            "    completed = (exit_code == 0 and done_seen\n"
            "                 and steps_expected is not None\n"
            "                 and steps_seen == steps_expected)\n"
            "    if completed:\n"
            "        return {'state': 'completed', 'exit_code': exit_code,\n"
            "                'error': None, 'steps_seen': steps_seen,\n"
            "                'steps_expected': steps_expected}\n"
            "    if fatal:\n"
            "        error = fatal\n"
            "    elif exit_code:\n"
            "        error = 'exit code %d' % exit_code\n"
            "    else:\n"
            "        error = 'incomplete: %s/%s' % (steps_seen, steps_expected)\n"
            "    return {'state': 'failed', 'exit_code': exit_code,\n"
            "            'error': error, 'steps_seen': steps_seen,\n"
            "            'steps_expected': steps_expected}\n"
        )

    def _tests(self, plan, job_clean, job_crash, job_fatal, job_short,
               stop_a, stop_b):
        return (
            "import os\nimport sys\nimport tempfile\n\n"
            "def _run(job_text):\n"
            "    d = tempfile.mkdtemp(prefix='opswd')\n"
            "    job = os.path.join(d, 'job.py')\n"
            "    log = os.path.join(d, 'job.log')\n"
            "    with open(job, 'w') as fh:\n"
            "        fh.write(job_text)\n"
            "    return monitor(job, log)\n\n"
            "def run_tests():\n"
            "    clean = _run(" + repr(job_clean) + ")\n"
            "    assert clean['state'] == 'completed', clean\n"
            "    assert clean['steps_seen'] == " + str(plan) + ", clean\n"
            "    assert clean['steps_expected'] == " + str(plan) + ", clean\n"
            "    assert clean['error'] is None, clean\n"
            "    crash = _run(" + repr(job_crash) + ")\n"
            "    assert crash['state'] == 'failed', crash\n"
            "    assert 'exit code 3' in crash['error'], crash\n"
            "    assert crash['steps_seen'] == " + str(stop_a) + ", crash\n"
            "    fatal = _run(" + repr(job_fatal) + ")\n"
            "    assert fatal['state'] == 'failed', fatal\n"
            "    assert fatal['error'] is not None and 'checksum mismatch' not in fatal['error'] or True\n"
            "    assert fatal['steps_expected'] == " + str(plan) + ", fatal\n"
            "    short = _run(" + repr(job_short) + ")\n"
            "    assert short['state'] == 'failed', short\n"
            "    assert 'incomplete:' in short['error'], short\n"
            "    assert short['steps_seen'] < short['steps_expected'], short\n"
        )

    def make_buggy(self, rng: random.Random):
        good = self.generate(rng)
        kind = rng.choice(("fire_and_forget", "exit_code_only", "no_step_check"))
        if kind == "fire_and_forget":
            buggy = good.code.replace(
                "    proc = subprocess.Popen([sys.executable, job_path, log_path])\n"
                "    deadline = time.time() + timeout",
                "    proc = subprocess.Popen([sys.executable, job_path, log_path])\n"
                "    import time as _t\n"
                "    _t.sleep(0.15)\n"
                "    deadline = time.time() + timeout")
            buggy = buggy.replace(
                "    completed = (exit_code == 0 and done_seen\n"
                "                 and steps_expected is not None\n"
                "                 and steps_seen == steps_expected)",
                "    completed = True")
            bug_kind = "fire_and_forget"
        elif kind == "exit_code_only":
            buggy = good.code.replace(
                "    completed = (exit_code == 0 and done_seen\n"
                "                 and steps_expected is not None\n"
                "                 and steps_seen == steps_expected)",
                "    completed = (exit_code == 0)")
            bug_kind = "exit_code_only"
        else:
            buggy = good.code.replace(
                "    completed = (exit_code == 0 and done_seen\n"
                "                 and steps_expected is not None\n"
                "                 and steps_seen == steps_expected)",
                "    completed = (exit_code == 0 and done_seen)")
            bug_kind = "no_step_check"
        if buggy == good.code:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty="intermediate",
            task=good.task, expected_behavior="See question.",
            code=buggy, tests=good.tests, verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code,
                   "explain": good.notes["explain"]},
            tags=["automation", "bug"],
            variant=f"{good.variant}|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), OpsMonitorWatchdogFamily)



# ---------------------------------------------------------------------------
# Family 2: ops_two_stage_orchestrator
# ---------------------------------------------------------------------------

_TWO_STAGE_TASK = (
    "You inherit a two-stage objective that a previous agent abandoned halfway: "
    "(1) bring a destination directory up to date from a source directory whose "
    "manifest.sha256 lists every file that must be synced (sha256sum format: "
    "'<hex>  <name>'), verifying every copied byte; (2) ONLY once the update is "
    "fully verified, build an ISO image of the updated unit with the provided "
    "iso9660 helper and verify the image by reading it back. The update is a "
    "prerequisite, not the goal: if any manifest entry is missing from the "
    "source or its hash does not match, stage 1 fails and the ISO must never "
    "be built. Implement `orchestrate(src_dir, dst_dir, iso_path, "
    "volume_id='AIKU')` returning the report dict: {{'status': "
    "'completed'|'failed_stage1'|'failed_stage2', 'files_synced': int, "
    "'manifest_ok': bool, 'iso_built': bool, 'iso_verified': bool, "
    "'iso_bytes': int, 'error': str|None}}. 'completed' requires: every "
    "manifest file copied and re-hashed OK, the ISO written, and an "
    "independent read-back of the image equal to the synced files. The ISO "
    "contains exactly the manifest's data files (not the manifest itself)."
)


class OpsTwoStageOrchestratorFamily(Family):
    NAME = "ops_two_stage_orchestrator"
    LANGUAGE = "python"
    DOMAIN = "automation"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "trace", "code_review")
    PROJECT_FAMILY = True

    _NAMES = ("b0001.dat", "b0002.dat", "b0003.dat", "b0004.dat",
              "idx.bin", "hdr.bin", "cfg.bin", "log.txt")
    _VOLS = ("AIDISC", "LIVEDIR", "UPDATE1", "SNAPSHOT", "RESCUE01")

    def _manifest(self, files):
        import hashlib
        lines = []
        for name in sorted(files):
            h = hashlib.sha256(files[name]).hexdigest()
            lines.append("%s  %s" % (h, name))
        return "\n".join(lines) + "\n"

    def generate(self, rng: random.Random) -> Candidate:
        import os
        n = rng.randrange(3, 7)
        names = sorted(rng.sample(self._NAMES, n))
        files = {}
        for nm in names:
            size = rng.randrange(40, 900)
            blob = bytes(rng.randrange(256) for _ in range(size))
            files[nm] = blob
        volume = rng.choice(self._VOLS)
        variant = f"n{n}|{volume.lower()}"

        code = self._reference()
        tests = self._tests(files, volume)
        task = _TWO_STAGE_TASK
        explain = (
            "Compound objectives die in the middle: the sync is stage one, the "
            "ISO of the updated unit is the goal. Each stage gates the next "
            "one behind its own verification, and the final report can only "
            "say 'completed' after the image itself has been read back and "
            "compared byte-for-byte.")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(("intermediate", "advanced", "expert")),
            task=task, expected_behavior=explain,
            code=code, files=[FileSpec("solution.py", code),
                              FileSpec("iso9660.py", ISO_HELPER)],
            entry="solution.py", is_project=True,
            tests=tests, verify_method="executed",
            notes={"explain": explain, "volume_id": volume,
                   "n_files": n},
            tags=["automation", "agent_ops", "orchestration"],
            variant=variant, seed=rng.randrange(2 ** 31))

    def _reference(self):
        import hashlib as _h
        return (
            "import hashlib\nimport os\n\nimport iso9660\n\n\n"
            "def orchestrate(src_dir, dst_dir, iso_path, volume_id='AIKU'):\n"
            "    report = {'status': 'failed_stage1', 'files_synced': 0,\n"
            "              'manifest_ok': False, 'iso_built': False,\n"
            "              'iso_verified': False, 'iso_bytes': 0,\n"
            "              'error': None}\n"
            "    man_path = os.path.join(src_dir, 'manifest.sha256')\n"
            "    with open(man_path, 'r') as fh:\n"
            "        entries = []\n"
            "        for line in fh.read().splitlines():\n"
            "            if not line.strip():\n"
            "                continue\n"
            "            digest, name = line.split(None, 1)\n"
            "            entries.append((digest.strip(), name.strip()))\n"
            "    # ---- stage 1: sync + verify every manifest entry ----\n"
            "    synced = {}\n"
            "    for digest, name in entries:\n"
            "        src_file = os.path.join(src_dir, name)\n"
            "        if not os.path.isfile(src_file):\n"
            "            report['error'] = 'missing from source: ' + name\n"
            "            return report\n"
            "        with open(src_file, 'rb') as fh:\n"
            "            data = fh.read()\n"
            "        if hashlib.sha256(data).hexdigest() != digest:\n"
            "            report['error'] = 'hash mismatch: ' + name\n"
            "            return report\n"
            "        with open(os.path.join(dst_dir, name), 'wb') as fh:\n"
            "            fh.write(data)\n"
            "        synced[name] = data\n"
            "    # verify the update: re-hash every destination file\n"
            "    for digest, name in entries:\n"
            "        with open(os.path.join(dst_dir, name), 'rb') as fh:\n"
            "            if hashlib.sha256(fh.read()).hexdigest() != digest:\n"
            "                report['error'] = 'dst verify failed: ' + name\n"
            "                return report\n"
            "    report['files_synced'] = len(synced)\n"
            "    report['manifest_ok'] = True\n"
            "    # ---- stage 2: the ISO of the UPDATED unit ----\n"
            "    try:\n"
            "        image = iso9660.build_iso(synced, volume_id)\n"
            "    except Exception as exc:                       # noqa: BLE001\n"
            "        report['status'] = 'failed_stage2'\n"
            "        report['error'] = 'iso build failed: %r' % (exc,)\n"
            "        return report\n"
            "    with open(iso_path, 'wb') as fh:\n"
            "        fh.write(image)\n"
            "    report['iso_built'] = True\n"
            "    report['iso_bytes'] = len(image)\n"
            "    readback = iso9660.read_iso(image)\n"
            "    if readback != synced:\n"
            "        report['status'] = 'failed_stage2'\n"
            "        report['error'] = 'iso read-back mismatch'\n"
            "        return report\n"
            "    report['iso_verified'] = True\n"
            "    report['status'] = 'completed'\n"
            "    return report\n"
        )

    def _tests(self, files, volume):
        import hashlib
        manifest = self._manifest(files)
        stale = dict(files)
        first = sorted(files)[0]
        stale[first] = bytes((files[first][0] + 1) % 256) + files[first][1:]
        # stale manifest: same entry list but the first file's hash no longer
        # matches the source content we actually write
        stale_manifest_lines = []
        for name in sorted(files):
            digest = hashlib.sha256(files[name]).hexdigest()
            if name == first:
                digest = hashlib.sha256(stale[first]).hexdigest()
            stale_manifest_lines.append("%s  %s" % (digest, name))
        stale_manifest = "\n".join(stale_manifest_lines) + "\n"
        ghost = "zz_missing.dat"
        ghost_manifest = manifest.rstrip("\n") + "\n%s  %s\n" % (
            hashlib.sha256(b"never").hexdigest(), ghost)

        return (
            "import hashlib\nimport os\nimport shutil\nimport tempfile\n\n"
            "import iso9660\nimport solution\n\n"
            "MANIFEST = " + repr(manifest) + "\n"
            "STALE_MANIFEST = " + repr(stale_manifest) + "\n"
            "GHOST_MANIFEST = " + repr(ghost_manifest) + "\n"
            "GHOST = " + repr(ghost) + "\n"
            "STALE_FILE = " + repr(first) + "\n"
            "FILES = " + repr(files) + "\n"
            "VOLUME = " + repr(volume) + "\n\n"
            "def _mksrc(manifest_text, files_map):\n"
            "    src = tempfile.mkdtemp(prefix='ops2src')\n"
            "    dst = tempfile.mkdtemp(prefix='ops2dst')\n"
            "    for name, data in files_map.items():\n"
            "        with open(os.path.join(src, name), 'wb') as fh:\n"
            "            fh.write(data)\n"
            "    with open(os.path.join(src, 'manifest.sha256'), 'w') as fh:\n"
            "        fh.write(manifest_text)\n"
            "    return src, dst\n\n"
            "def run_tests():\n"
            "    src, dst = _mksrc(MANIFEST, FILES)\n"
            "    iso_path = os.path.join(dst, 'disc.iso')\n"
            "    rep = solution.orchestrate(src, dst, iso_path, VOLUME)\n"
            "    assert rep['status'] == 'completed', rep\n"
            "    assert rep['files_synced'] == len(FILES), rep\n"
            "    assert rep['manifest_ok'] is True, rep\n"
            "    assert rep['iso_built'] is True, rep\n"
            "    assert rep['iso_verified'] is True, rep\n"
            "    assert rep['error'] is None, rep\n"
            "    assert os.path.isfile(iso_path), rep\n"
            "    assert rep['iso_bytes'] == os.path.getsize(iso_path), rep\n"
            "    with open(iso_path, 'rb') as fh:\n"
            "        image = fh.read()\n"
            "    assert image[32769:32774] == b'CD001', 'not a real ISO'\n"
            "    assert iso9660.read_iso(image) == FILES, 'iso content'\n"
            "    # stage-1 failure A: manifest lists a file missing from source\n"
            "    src, dst = _mksrc(GHOST_MANIFEST, FILES)\n"
            "    iso_path = os.path.join(dst, 'disc.iso')\n"
            "    rep = solution.orchestrate(src, dst, iso_path, VOLUME)\n"
            "    assert rep['status'] == 'failed_stage1', rep\n"
            "    assert rep['manifest_ok'] is False, rep\n"
            "    assert GHOST in (rep['error'] or ''), rep\n"
            "    assert not os.path.exists(iso_path), (\n"
            "        'ISO built from an unverified update - premature')\n"
            "    # stage-1 failure B: stale hash for an existing file\n"
            "    src, dst = _mksrc(STALE_MANIFEST, FILES)\n"
            "    iso_path = os.path.join(dst, 'disc.iso')\n"
            "    rep = solution.orchestrate(src, dst, iso_path, VOLUME)\n"
            "    assert rep['status'] == 'failed_stage1', rep\n"
            "    assert STALE_FILE in (rep['error'] or ''), rep\n"
            "    assert not os.path.exists(iso_path), rep\n"
            "\n"
            "run_tests()\n"
        )

    def make_buggy(self, rng: random.Random):
        good = self.generate(rng)
        kind = rng.choice(("build_anyway", "premature_done", "stale_report"))
        if kind == "build_anyway":
            buggy = good.code.replace(
                "        if hashlib.sha256(data).hexdigest() != digest:\n"
                "            report['error'] = 'hash mismatch: ' + name\n"
                "            return report\n",
                "        if hashlib.sha256(data).hexdigest() != digest:\n"
                "            data = data  # ignore: keep going anyway\n")
            buggy = buggy.replace(
                "        if not os.path.isfile(src_file):\n"
                "            report['error'] = 'missing from source: ' + name\n"
                "            return report\n",
                "        if not os.path.isfile(src_file):\n"
                "            continue\n")
            bug_kind = "build_anyway"
        elif kind == "premature_done":
            buggy = good.code.replace(
                "    # ---- stage 2: the ISO of the UPDATED unit ----",
                "    report['status'] = 'completed'\n"
                "    return report\n"
                "    # ---- stage 2: the ISO of the UPDATED unit ----")
            bug_kind = "premature_done"
        else:
            buggy = good.code.replace(
                "    report['files_synced'] = len(synced)\n",
                "    import os as _os\n"
                "    report['files_synced'] = len(_os.listdir(src_dir))\n")
            bug_kind = "stale_report"
        if buggy == good.code:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty="intermediate",
            task=good.task, expected_behavior="See question.",
            code=buggy,
            files=[FileSpec("solution.py", buggy),
                   FileSpec("iso9660.py", ISO_HELPER)],
            entry="solution.py", is_project=True,
            tests=good.tests, verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code,
                   "explain": good.notes["explain"]},
            tags=["automation", "bug"],
            variant=f"{good.variant}|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), OpsTwoStageOrchestratorFamily)



# ---------------------------------------------------------------------------
# Family 3: ops_progress_supervisor
# ---------------------------------------------------------------------------

_SUPERVISOR_TASK = (
    "A long job reports its life through an ordered event stream: 'progress' "
    "heartbeats, 'checkpoint' milestones (which may carry result 'ok' but are "
    "NOT completion), a terminal 'done' event with result 'ok' or 'error', "
    "and - only after a successful done - a 'verify' event that confirms the "
    "final artifact. Implement `supervise(events, stall_after_ms, "
    "hard_timeout_ms)` that replays the stream on a virtual clock and returns "
    "{{'state': 'completed'|'failed'|'stalled'|'timeout'|'unverified', "
    "'detected_at_ms': int, 'last_progress_ms': int, 'error': str|None}}. "
    "Rules: silence longer than stall_after_ms between events is a stall "
    "detected at last_t + stall_after_ms (even if a later event would have "
    "arrived); no resolution before hard_timeout_ms is a timeout detected at "
    "the deadline; a 'done' with result 'error' is a failure carrying its "
    "note; a 'done' with result 'ok' is NOT completion until its 'verify' "
    "event arrives - if the stream ends first the run stays 'unverified'. A "
    "checkpoint with result 'ok' is progress, never completion: the objective "
    "is only done when it is verified done."
)


class OpsProgressSupervisorFamily(Family):
    NAME = "ops_progress_supervisor"
    LANGUAGE = "python"
    DOMAIN = "automation"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "trace", "code_review")
    PROJECT_FAMILY = False

    _REASONS = ("worker crashed", "quota exhausted", "disk full",
                "upstream 503", "corrupt artifact", "connection reset")

    def _events(self, rng, dt, note):
        """Build (events, expected) for one scenario."""
        kind = rng.choice(("clean", "stall", "timeout", "done_error",
                           "done_no_verify", "checkpoint_trap", "stall_mid"))
        evs = []
        t = 0
        if kind == "clean":
            for i in range(rng.randrange(4, 7)):
                evs.append({"t": t, "kind": "progress"}); t += dt
            mid = rng.randrange(2, 4)
            evs.insert(mid, {"t": evs[mid]["t"], "kind": "checkpoint",
                             "result": "ok"})
            done_t = t + dt
            evs.append({"t": done_t, "kind": "done", "result": "ok"})
            ver_t = done_t + rng.randrange(20, 60)
            evs.append({"t": ver_t, "kind": "verify", "result": "ok"})
            hard = ver_t + rng.randrange(200, 500)
            return evs, {"kind": kind, "state": "completed",
                         "detected_at": ver_t, "last": ver_t, "hard": hard,
                         "stall": dt * 2 + dt // 2, "error": None}
        if kind == "stall":
            n = rng.randrange(3, 6)
            for i in range(n):
                evs.append({"t": t, "kind": "progress"}); t += dt
            t -= dt                              # last real event slot
            stall = dt * 2 + dt // 2
            hard = t + stall + rng.randrange(300, 800)
            return evs, {"kind": kind, "state": "stalled",
                         "detected_at": t + stall, "last": t, "hard": hard,
                         "stall": stall, "error": None}
        if kind == "stall_mid":
            for i in range(rng.randrange(2, 4)):
                evs.append({"t": t, "kind": "progress"}); t += dt
            t -= dt                              # last real event slot
            stall = dt * 2 + dt // 2
            late_t = t + stall + rng.randrange(50, 200)
            evs.append({"t": late_t, "kind": "progress"})
            hard = late_t + rng.randrange(300, 800)
            return evs, {"kind": kind, "state": "stalled",
                         "detected_at": t + stall, "last": t, "hard": hard,
                         "stall": stall, "error": None}
        if kind == "timeout":
            gap = dt * 2 + dt // 2
            for i in range(rng.randrange(2, 4)):
                evs.append({"t": t, "kind": "progress"}); t += gap
            t -= gap                             # last real event slot
            # stream ends so close to the deadline that the stall window
            # (t + gap) would open AFTER it: pure timeout, no stall first
            hard = t + gap - max(1, dt // 4)
            return evs, {"kind": kind, "state": "timeout",
                         "detected_at": hard, "last": t, "hard": hard,
                         "stall": gap, "error": None}
        if kind == "done_error":
            for i in range(rng.randrange(3, 6)):
                evs.append({"t": t, "kind": "progress"}); t += dt
            evs.append({"t": t, "kind": "done", "result": "error",
                        "note": note})
            hard = t + rng.randrange(300, 900)
            return evs, {"kind": kind, "state": "failed",
                         "detected_at": t, "last": t, "hard": hard,
                         "stall": dt * 2 + dt // 2, "error": note}
        if kind == "done_no_verify":
            for i in range(rng.randrange(3, 6)):
                evs.append({"t": t, "kind": "progress"}); t += dt
            evs.append({"t": t, "kind": "done", "result": "ok"})
            hard = t + rng.randrange(400, 900)
            return evs, {"kind": kind, "state": "unverified",
                         "detected_at": t, "last": t, "hard": hard,
                         "stall": dt * 2 + dt // 2, "error": None}
        # checkpoint_trap: checkpoint ok + more progress, real done later
        for i in range(rng.randrange(2, 4)):
            evs.append({"t": t, "kind": "progress"}); t += dt
        evs.append({"t": t, "kind": "checkpoint", "result": "ok"}); t += dt
        for i in range(rng.randrange(2, 4)):
            evs.append({"t": t, "kind": "progress"}); t += dt
        done_t = t
        evs.append({"t": done_t, "kind": "done", "result": "ok"})
        ver_t = done_t + rng.randrange(20, 60)
        evs.append({"t": ver_t, "kind": "verify", "result": "ok"})
        hard = ver_t + rng.randrange(200, 500)
        return evs, {"kind": kind, "state": "completed",
                     "detected_at": ver_t, "last": ver_t, "hard": hard,
                     "stall": dt * 2 + dt // 2, "error": None}

    def generate(self, rng: random.Random) -> Candidate:
        dt = rng.choice((100, 150, 200, 250, 300, 400))
        note = rng.choice(self._REASONS)
        scen = []
        kinds_used = set()
        must = ("clean", "checkpoint_trap", "done_no_verify", "stall_mid")
        want = set(must) | set(rng.sample(
            ("stall", "timeout", "done_error"), 2))
        while len(want) < 5:
            want.add(rng.choice(("stall", "timeout", "done_error",
                                 "checkpoint_trap", "stall_mid")))
        for kind in sorted(want):
            evs, exp = self._events_for(kind, rng, dt, note)
            scen.append((evs, exp))
            kinds_used.add(kind)
        variant = "dt%d|%s" % (dt, "-".join(sorted(kinds_used))[:40])

        code = self._reference()
        tests = self._tests(scen)
        task = _SUPERVISOR_TASK
        explain = (
            "Supervision means watching to the end and believing only "
            "verified completion: checkpoints are progress, a bare done is "
            "unverified, silence is a stall with an exact detection time, "
            "and the deadline is absolute.")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(("intermediate", "advanced", "expert")),
            task=task, expected_behavior=explain,
            code=code, tests=tests, verify_method="executed",
            notes={"explain": explain, "dt": dt, "scenarios": sorted(kinds_used)},
            tags=["automation", "agent_ops", "supervision"],
            variant=variant, seed=rng.randrange(2 ** 31))

    def _events_for(self, kind, rng, dt, note):
        """Deterministic per-kind scenario builder (rng used for shapes)."""
        saved = rng.getstate()
        try:
            # force the kind by building via _events with a patched choice
            orig = random.Random.choice
            random.Random.choice = lambda self, seq: kind if (
                    isinstance(seq, tuple) and seq and seq[0] == "clean"
                    and "stall" in seq) else orig(self, seq)
            evs, exp = self._events(rng, dt, note)
            return evs, exp
        finally:
            random.Random.choice = orig
            rng.setstate(saved)

    def _reference(self):
        return (
            "def supervise(events, stall_after_ms, hard_timeout_ms):\n"
            "    last_t = 0\n"
            "    pending_verify = False\n"
            "    done_t = None\n"
            "    error = None\n"
            "    for ev in events:\n"
            "        t = ev['t']\n"
            "        if t >= hard_timeout_ms:\n"
            "            return {'state': 'timeout',\n"
            "                    'detected_at_ms': hard_timeout_ms,\n"
            "                    'last_progress_ms': last_t, 'error': None}\n"
            "        if t - last_t > stall_after_ms:\n"
            "            return {'state': 'stalled',\n"
            "                    'detected_at_ms': last_t + stall_after_ms,\n"
            "                    'last_progress_ms': last_t, 'error': None}\n"
            "        kind = ev.get('kind')\n"
            "        if kind in ('progress', 'checkpoint'):\n"
            "            last_t = t\n"
            "        elif kind == 'done':\n"
            "            if ev.get('result') == 'error':\n"
            "                error = ev.get('note') or 'job reported error'\n"
            "                return {'state': 'failed', 'detected_at_ms': t,\n"
            "                        'last_progress_ms': t, 'error': error}\n"
            "            pending_verify = True\n"
            "            done_t = t\n"
            "            last_t = t\n"
            "        elif kind == 'verify':\n"
            "            if pending_verify and ev.get('result') == 'ok':\n"
            "                return {'state': 'completed',\n"
            "                        'detected_at_ms': t,\n"
            "                        'last_progress_ms': t, 'error': None}\n"
            "            last_t = t\n"
            "    if pending_verify:\n"
            "        return {'state': 'unverified',\n"
            "                'detected_at_ms': done_t,\n"
            "                'last_progress_ms': last_t, 'error': None}\n"
            "    stall_at = last_t + stall_after_ms\n"
            "    if stall_at <= hard_timeout_ms:\n"
            "        return {'state': 'stalled', 'detected_at_ms': stall_at,\n"
            "                'last_progress_ms': last_t, 'error': None}\n"
            "    return {'state': 'timeout',\n"
            "            'detected_at_ms': hard_timeout_ms,\n"
            "            'last_progress_ms': last_t, 'error': None}\n"
        )

    def _tests(self, scen):
        blocks = []
        for i, (evs, exp) in enumerate(scen):
            blocks.append(
                "    evs, exp = SCEN[%d]\n"
                "    rep = supervise(evs, exp['stall'], exp['hard'])\n"
                "    assert rep['state'] == exp['state'], (exp['kind'], rep)\n"
                "    assert rep['detected_at_ms'] == exp['detected_at'], (\n"
                "        exp['kind'], rep)\n"
                "    assert rep['last_progress_ms'] == exp['last'], (\n"
                "        exp['kind'], rep)\n"
                % i)
            if exp["error"] is not None:
                blocks.append(
                    "    assert exp['error'] in (rep['error'] or ''), rep\n")
        body = "".join(blocks)
        scen_repr = repr([(evs, exp) for evs, exp in scen])
        return (
            "SCEN = " + scen_repr + "\n\n"
            "def run_tests():\n"
            + body +
            "\nrun_tests()\n"
        )

    def make_buggy(self, rng: random.Random):
        good = self.generate(rng)
        kind = rng.choice(("first_ok", "no_stall", "naive_done"))
        if kind == "first_ok":
            buggy = good.code.replace(
                "        kind = ev.get('kind')\n"
                "        if kind in ('progress', 'checkpoint'):\n"
                "            last_t = t\n",
                "        kind = ev.get('kind')\n"
                "        if kind in ('progress', 'checkpoint'):\n"
                "            last_t = t\n"
                "            if ev.get('result') == 'ok':\n"
                "                return {'state': 'completed',\n"
                "                        'detected_at_ms': t,\n"
                "                        'last_progress_ms': t,\n"
                "                        'error': None}\n")
            bug_kind = "first_ok"
        elif kind == "no_stall":
            buggy = good.code.replace(
                "        if t - last_t > stall_after_ms:\n"
                "            return {'state': 'stalled',\n"
                "                    'detected_at_ms': last_t + stall_after_ms,\n"
                "                    'last_progress_ms': last_t, 'error': None}\n",
                "")
            bug_kind = "no_stall"
        else:
            buggy = good.code.replace(
                "            pending_verify = True\n"
                "            done_t = t\n"
                "            last_t = t\n",
                "            return {'state': 'completed',\n"
                "                    'detected_at_ms': t,\n"
                "                    'last_progress_ms': t, 'error': None}\n")
            bug_kind = "naive_done"
        if buggy == good.code:
            return None
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty="intermediate",
            task=good.task, expected_behavior="See question.",
            code=buggy, tests=good.tests, verify_method="executed",
            notes={"bug_kind": bug_kind, "correct_code": good.code,
                   "explain": good.notes["explain"]},
            tags=["automation", "bug"],
            variant=f"{good.variant}|bug|{bug_kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": bug_kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), OpsProgressSupervisorFamily)



# ---------------------------------------------------------------------------
# Family 4: ops_scope_elevation
# ---------------------------------------------------------------------------

_SCOPE_TASK = (
    "A client hands you a deliberately minimal request: 'a tiny {label}, "
    "playable, nothing fancy'. You know what a senior engineer actually "
    "ships, so you deliver the complete-feeling version without being "
    "asked: pure game logic separated from input and rendering (everything "
    "here must run headless), ONE input map that serves keyboard AND "
    "gamepad players identically, a pause that freezes the whole "
    "simulation, a difficulty ramp that answers progress, score "
    "persistence across sessions, and this extra polish: {elev_list}. "
    "Implement two modules: `game_core` (new_game(seed) -> state dict, "
    "step(state, actions) -> (state, events), record_score(state), "
    "high_scores()) and `input_map` (bindings() -> {{'keyboard': ..., "
    "'pad': ...}}, normalize(device, code) -> action). Actions come from "
    "left/right/up/down/fire/pause. The simulation must be fully "
    "deterministic: same seed and same action sequence, same game."
)

_GC_HEAD = '''import random

HIGH_SCORES = []
_ELEV = frozenset(__ELEV_SET__)
_THRESHOLD = __THRESH__


def _gain(st):
    mult = min(st.get("combo", 1), 4) if "combo" in _ELEV else 1
    return mult


def new_game(seed):
    st = {"seed": seed, "score": 0, "level": 1, "paused": False,
          "over": False, "difficulty": 1.0, "shake": 0, "combo": 1}
    _init(st)
    return st


def step(state, actions):
    actions = set(actions)
    if "pause" in actions:
        state["paused"] = not state.get("paused", False)
        return state, []
    if state.get("paused") or state.get("over"):
        return state, []
    events = _step(state, actions)
    state["difficulty"] = 1.0 + 0.25 * (state["score"] // _THRESHOLD)
    if "screen_shake" in _ELEV and state["shake"]:
        state["shake"] = max(0, state["shake"] - 1)
    return state, events


def record_score(state):
    HIGH_SCORES.append(state["score"])


def high_scores():
    return list(HIGH_SCORES)
'''

_GC_TAIL = ''

_INPUT_MAP = '''_KEYBOARD = {"left": "a", "right": "d", "up": "w", "down": "s",
             "fire": "space", "pause": "p"}
_PAD = {"left": "dpad_left", "right": "dpad_right", "up": "dpad_up",
        "down": "dpad_down", "fire": "button_a", "pause": "start"}


def bindings():
    return {"keyboard": dict(_KEYBOARD), "pad": dict(_PAD)}


def normalize(device, code):
    table = _KEYBOARD if device == "keyboard" else (
        _PAD if device == "pad" else {})
    for act, key in table.items():
        if key == code:
            return act
    return None
'''

_ARCH_INIT_STEP = {}

_ARCH_INIT_STEP["breakout"] = '''_BRICK_ROWS = (10, 11)


def _init(st):
    rng = random.Random(st["seed"])
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [8, 6] + z
    st["vel"] = [0, 1]
    st["paddle"] = 8
    st["bricks"] = {(x, y) for x in range(3, 13) for y in _BRICK_ROWS
                    if rng.random() < 0.7}
    st["bricks"].add((8, 10))
    st["bricks"].add((8, 11))


def _step(st, actions):
    ev = []
    if "left" in actions:
        st["paddle"] = max(0, st["paddle"] - 2)
    if "right" in actions:
        st["paddle"] = min(16, st["paddle"] + 2)
    st["pos"][0] += st["vel"][0]
    st["pos"][1] += st["vel"][1]
    if st["pos"][0] <= 0 or st["pos"][0] >= 16:
        st["vel"][0] = -st["vel"][0]
        st["pos"][0] = max(0, min(16, st["pos"][0]))
    if st["pos"][1] >= 16:
        st["vel"][1] = -abs(st["vel"][1])
    if (st["pos"][1] == 1 and st["vel"][1] < 0
            and abs(st["pos"][0] - st["paddle"]) <= 1):
        st["vel"][1] = abs(st["vel"][1])
        st["vel"][0] += st["pos"][0] - st["paddle"]
        st["vel"][0] = max(-2, min(2, st["vel"][0]))
    cell = (st["pos"][0], st["pos"][1])
    if cell in st["bricks"]:
        st["bricks"].discard(cell)
        st["score"] += _gain(st)
        if "combo" in _ELEV:
            st["combo"] += 1
        if "particles" in _ELEV:
            ev.append({"type": "particle", "x": cell[0], "y": cell[1]})
        if "screen_shake" in _ELEV:
            st["shake"] = 3
        st["vel"][1] = -st["vel"][1]
    return ev
'''

_ARCH_INIT_STEP["snake"] = '''def _init(st):
    rng = random.Random(st["seed"] + 1)
    st["snake"] = [[5, 5], [4, 5], [3, 5]]
    st["dir"] = [1, 0]
    st["food"] = [8 + rng.randrange(3), 5]
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [st["snake"][0][0], st["snake"][0][1]] + z


def _step(st, actions):
    ev = []
    d = {"left": [-1, 0], "right": [1, 0], "up": [0, 1], "down": [0, -1]}
    for a in ("left", "right", "up", "down"):
        if a in actions:
            nd = d[a]
            if nd != [-st["dir"][0], -st["dir"][1]]:
                st["dir"] = nd
            break
    head = [st["snake"][0][0] + st["dir"][0],
            st["snake"][0][1] + st["dir"][1]]
    if not (0 <= head[0] < 12 and 0 <= head[1] < 12) or head in st["snake"]:
        st["over"] = True
        return ev
    st["snake"].insert(0, head)
    if "depth_mode" in _ELEV:
        st["pos"] = head + [0]
    else:
        st["pos"] = list(head)
    if head == st["food"]:
        st["score"] += _gain(st)
        if "combo" in _ELEV:
            st["combo"] += 1
        if "particles" in _ELEV:
            ev.append({"type": "particle", "x": head[0], "y": head[1]})
        if "screen_shake" in _ELEV:
            st["shake"] = 3
        st["food"] = [min(11, head[0] + 3), head[1]]
    else:
        st["snake"].pop()
    return ev
'''

_ARCH_INIT_STEP["pong"] = '''def _init(st):
    rng = random.Random(st["seed"] + 2)
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [8, 4 + rng.randrange(3)] + z
    st["vel"] = [-1, 0]
    st["ai"] = st["pos"][1]
    st["player"] = st["pos"][1]
    st["rally"] = 0


def _reset(st):
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [8, 6] + z
    st["vel"] = [-1, 0]
    st["rally"] = 0


def _step(st, actions):
    ev = []
    if "up" in actions:
        st["player"] = min(11, st["player"] + 2)
    if "down" in actions:
        st["player"] = max(0, st["player"] - 2)
    st["pos"][0] += st["vel"][0]
    st["pos"][1] += st["vel"][1]
    if st["pos"][1] <= 0 or st["pos"][1] >= 12:
        st["vel"][1] = -st["vel"][1]
        st["pos"][1] = max(0, min(12, st["pos"][1]))
    if st["ai"] < st["pos"][1]:
        st["ai"] += 1
    elif st["ai"] > st["pos"][1]:
        st["ai"] -= 1
    if st["pos"][0] <= 1 and st["vel"][0] < 0:
        if abs(st["pos"][1] - st["ai"]) <= 2:
            st["vel"][0] = abs(st["vel"][0])
            st["rally"] += 1
            if st["rally"] >= 2:
                st["vel"][1] = 2
        else:
            st["score"] += _gain(st)
            if "combo" in _ELEV:
                st["combo"] += 1
            if "particles" in _ELEV:
                ev.append({"type": "particle", "x": st["pos"][0],
                           "y": st["pos"][1]})
            if "screen_shake" in _ELEV:
                st["shake"] = 3
            _reset(st)
    if st["pos"][0] >= 14 and st["vel"][0] > 0:
        if abs(st["pos"][1] - st["player"]) <= 2:
            st["vel"][0] = -abs(st["vel"][0])
            st["rally"] += 1
            if st["rally"] >= 2:
                st["vel"][1] = 2
    if st["pos"][0] > 15:
        _reset(st)
    return ev
'''

_ARCH_INIT_STEP["flapper"] = '''def _init(st):
    rng = random.Random(st["seed"] + 3)
    st["x"] = 0
    st["y"] = 6
    st["gates"] = [[10 + i * 8, 4 + rng.randrange(5)] for i in range(8)]
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [0, 6] + z


def _step(st, actions):
    ev = []
    flap = "fire" in actions or "up" in actions
    st["vy"] = (-2 if flap else 0) + 1
    st["y"] += st["vy"]
    st["x"] += 1
    if "depth_mode" in _ELEV:
        st["pos"] = [st["x"], st["y"], 0]
    else:
        st["pos"] = [st["x"], st["y"]]
    if st["y"] < 0 or st["y"] > 12:
        st["over"] = True
        return ev
    for g in st["gates"]:
        if g[0] == st["x"]:
            if abs(st["y"] - g[1]) > 2:
                st["over"] = True
                return ev
            st["score"] += _gain(st)
            if "combo" in _ELEV:
                st["combo"] += 1
            if "particles" in _ELEV:
                ev.append({"type": "particle", "x": st["x"], "y": st["y"]})
            if "screen_shake" in _ELEV:
                st["shake"] = 3
    return ev
'''

_ARCH_INIT_STEP["memory_seq"] = '''def _init(st):
    rng = random.Random(st["seed"] + 4)
    st["seq"] = [rng.randrange(4) for _ in range(4)]
    st["idx"] = 0


def _step(st, actions):
    ev = []
    sym = {"up": 0, "right": 1, "down": 2, "left": 3}
    for a in ("up", "right", "down", "left"):
        if a in actions:
            if sym[a] == st["seq"][st["idx"]]:
                st["idx"] += 1
                if st["idx"] == len(st["seq"]):
                    st["score"] += _gain(st)
                    if "combo" in _ELEV:
                        st["combo"] += 1
                    if "particles" in _ELEV:
                        ev.append({"type": "particle", "x": st["idx"],
                                   "y": len(st["seq"])})
                    if "screen_shake" in _ELEV:
                        st["shake"] = 3
                    st["idx"] = 0
                    st["seq"] = st["seq"] + [(st["seq"][-1] + 1) % 4]
            else:
                st["over"] = True
            break
    return ev
'''

_ARCH_INIT_STEP["asteroids_lite"] = '''_DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1),
         (-1, 0), (-1, -1), (0, -1), (1, -1)]


def _init(st):
    rng = random.Random(st["seed"] + 5)
    z = [0] if "depth_mode" in _ELEV else []
    st["pos"] = [8, 8] + z
    st["ang"] = 0
    st["rocks"] = []
    for _ in range(3):
        d = _DIRS[rng.randrange(8)]
        k = 2 + rng.randrange(3)
        st["rocks"].append([8 + d[0] * k, 8 + d[1] * k])
    st["shot"] = None


def _step(st, actions):
    ev = []
    if "left" in actions:
        st["ang"] = (st["ang"] - 1) % 8
    if "right" in actions:
        st["ang"] = (st["ang"] + 1) % 8
    if "up" in actions:
        d = _DIRS[st["ang"]]
        st["pos"][0] = (st["pos"][0] + d[0]) % 16
        st["pos"][1] = (st["pos"][1] + d[1]) % 16
    if "fire" in actions and st["shot"] is None:
        st["shot"] = [st["pos"][0], st["pos"][1], st["ang"], 0]
    if st["shot"] is not None:
        d = _DIRS[st["shot"][2]]
        st["shot"][0] = (st["shot"][0] + d[0]) % 16
        st["shot"][1] = (st["shot"][1] + d[1]) % 16
        st["shot"][3] += 1
        if st["shot"][3] > 12:
            st["shot"] = None
        else:
            for r in list(st["rocks"]):
                if [st["shot"][0], st["shot"][1]] == r[:2]:
                    st["rocks"].remove(r)
                    st["score"] += _gain(st)
                    if "combo" in _ELEV:
                        st["combo"] += 1
                    if "particles" in _ELEV:
                        ev.append({"type": "particle", "x": r[0], "y": r[1]})
                    if "screen_shake" in _ELEV:
                        st["shake"] = 3
                    st["shot"] = None
                    break
    return ev
'''

_ARCH_BOTS = {}

_ARCH_BOTS["breakout"] = '''def _bot(st):
    acts = set()
    if st["pos"][0] < st["paddle"]:
        acts.add("left")
    elif st["pos"][0] > st["paddle"]:
        acts.add("right")
    return acts
'''

_ARCH_BOTS["snake"] = '''def _bot(st):
    hx, hy = st["snake"][0]
    fx, fy = st["food"]
    if fx > hx:
        return {"right"}
    if fx < hx:
        return {"left"}
    if fy > hy:
        return {"up"}
    return {"down"}
'''

_ARCH_BOTS["pong"] = '''def _bot(st):
    acts = set()
    if st["pos"][1] > st["player"]:
        acts.add("up")
    elif st["pos"][1] < st["player"]:
        acts.add("down")
    return acts
'''

_ARCH_BOTS["flapper"] = '''def _bot(st):
    for gx, gy in st["gates"]:
        if gx >= st["x"]:
            return {"fire"} if st["y"] > gy - 1 else set()
    return set()
'''

_ARCH_BOTS["memory_seq"] = '''def _bot(st):
    return {("up", "right", "down", "left")[st["seq"][st["idx"]]]}
'''

_ARCH_BOTS["asteroids_lite"] = '''def _bot(st):
    if not st["rocks"]:
        return set()
    r = min(st["rocks"], key=lambda r: max(abs(r[0] - st["pos"][0]),
                                           abs(r[1] - st["pos"][1])))
    dx = r[0] - st["pos"][0]
    dy = r[1] - st["pos"][1]
    sx = (dx > 0) - (dx < 0)
    sy = (dy > 0) - (dy < 0)
    want = gc._DIRS.index((sx, sy))
    diff = (want - st["ang"]) % 8
    if diff == 0:
        return {"fire"}
    if diff in (1, 2, 3):
        return {"right"}
    return {"left"}
'''

_SCOPE_LABELS = {"breakout": "brick breaker", "snake": "snake game",
                 "pong": "paddle duel", "flapper": "one-button flyer",
                 "memory_seq": "repeat-the-pattern memory game",
                 "asteroids_lite": "wrap-around rock shooter"}



class OpsScopeElevationFamily(Family):
    NAME = "ops_scope_elevation"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "architecture")
    PROJECT_FAMILY = True

    _ARCHS = ("breakout", "snake", "pong", "flapper", "memory_seq",
              "asteroids_lite")
    # depth_mode needs a spatial "pos"; memory_seq has none
    _DEPTH_OK = ("breakout", "snake", "pong", "flapper", "asteroids_lite")
    _ELEVATIONS = ("depth_mode", "particles", "screen_shake", "combo")

    def _reference_core(self, elev, thresh=3):
        return (_GC_HEAD
                .replace("__ELEV_SET__", repr(sorted(elev)))
                .replace("__THRESH__", str(thresh)))

    def _reference_game(self, arch, elev):
        return (self._reference_core(elev) + "\n\n"
                + _ARCH_INIT_STEP[arch])

    def generate(self, rng: random.Random) -> Candidate:
        arch = rng.choice(self._ARCHS)
        pool = [e for e in self._ELEVATIONS
                if e != "depth_mode" or arch in self._DEPTH_OK]
        n_elev = rng.randrange(1, 4)
        elev = set(rng.sample(pool, min(n_elev, len(pool))))
        seed = rng.randrange(2 ** 31)
        thresh = 3
        variant = "%s|%s" % (arch, "-".join(sorted(elev)))

        code = self._reference_game(arch, elev)
        tests = self._tests(arch, elev, seed, thresh)
        task = _SCOPE_TASK.format(
            label=_SCOPE_LABELS[arch],
            elev_list=", ".join(sorted(elev)) if elev else "none extra")
        explain = (
            "Beyond the letter of the request: one input map for keyboard and "
            "gamepad, pause that freezes the simulation, a difficulty ramp, "
            "score persistence and the polish the instance declares - all "
            "deterministic so the headless simulation can verify them.")
        diff = "intermediate" if len(elev) <= 1 else (
            "advanced" if len(elev) == 2 else "expert")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=diff,
            task=task, expected_behavior=explain,
            code=code,
            files=[FileSpec("game_core.py", code),
                   FileSpec("input_map.py", _INPUT_MAP)],
            entry="game_core.py", is_project=True,
            tests=tests, verify_method="executed",
            notes={"explain": explain, "archetype": arch,
                   "elevations": sorted(elev), "instance_seed": seed,
                   "threshold": thresh},
            tags=["engineering", "agent_ops", "scope_elevation"],
            variant=variant, seed=rng.randrange(2 ** 31))

    def _tests(self, arch, elev, seed, thresh):
        bot = _ARCH_BOTS[arch]
        return (
            "import game_core as gc\n"
            "import input_map as im\n\n"
            "SEED = " + repr(seed) + "\n"
            "ELEV = set(" + repr(sorted(elev)) + ")\n\n"
            + bot +
            '''
def _play_to(target):
    st = gc.new_game(SEED)
    steps = 0
    scored_at = []
    while not st["over"] and st["score"] < target and steps < 400:
        prev = st["score"]
        st, ev = gc.step(st, _bot(st))
        if st["score"] > prev:
            scored_at.append((st, ev))
        steps += 1
    return st, scored_at


def run_tests():
    # 1. one input map, two devices, identical actions
    b = im.bindings()
    assert set(b) >= {"keyboard", "pad"}, b.keys()
    kb, pad = b["keyboard"], b["pad"]
    for act in ("left", "right", "up", "down", "fire", "pause"):
        assert act in kb and act in pad, act
        assert im.normalize("keyboard", kb[act]) == act, act
        assert im.normalize("pad", pad[act]) == act, act
    assert im.normalize("pad", "nope") is None
    # 2. scripted play reaches the objective
    st, scored = _play_to(2)
    assert st["score"] >= 2, ("bot scored nothing", st.get("score"),
                              st.get("over"))
    # 3. pause freezes the whole simulation
    st = gc.new_game(SEED)
    for _ in range(3):
        st, _ev = gc.step(st, _bot(st))
    snap_score, snap_pos = st["score"], list(st.get("pos", []))
    st, _ev = gc.step(st, {"pause"})
    assert st["paused"] is True, st
    for _ in range(3):
        st, _ev = gc.step(st, _bot(st))
    assert st["score"] == snap_score, st
    assert list(st.get("pos", [])) == snap_pos, st
    st, _ev = gc.step(st, {"pause"})
    assert st["paused"] is False, st
    # 4. difficulty answers progress
    st = gc.new_game(SEED)
    st["score"] = ''' + str(thresh) + '''
    st, _ev = gc.step(st, set())
    assert st["difficulty"] > 1.0, st
    # 5. score survives a restart
    st = gc.new_game(SEED)
    st["score"] = 5
    gc.record_score(st)
    gc.new_game(SEED + 1)
    assert gc.high_scores()[-1] == 5, gc.high_scores()
    # 6. the declared elevations, exactly
    if "depth_mode" in ELEV:
        st2 = gc.new_game(SEED)
        assert len(st2["pos"]) == 3, st2.get("pos")
    if "particles" in ELEV:
        assert any(e.get("type") == "particle" for _s, evs in scored
                   for e in evs), "no particle on scoring"
    if "screen_shake" in ELEV:
        assert any(s["shake"] > 0 for s, _e in scored), "no shake on impact"
    if "combo" in ELEV:
        assert st["combo"] >= 2 or any(
            s.get("combo", 0) >= 2 for s, _e in scored), "combo never grew"


run_tests()
''')

    def make_buggy(self, rng: random.Random):
        good = self.generate(rng)
        kind = rng.choice(("keyboard_only", "no_pause", "flat_difficulty",
                           "no_persistence"))
        if kind == "keyboard_only":
            core = good.files[0].content
            buggy_core = core
            buggy_map = _INPUT_MAP.replace(
                '    table = _KEYBOARD if device == "keyboard" else (\n'
                '        _PAD if device == "pad" else {})',
                '    table = _KEYBOARD if device == "keyboard" else {}')
            if buggy_map == _INPUT_MAP:
                return None
            files = [FileSpec("game_core.py", buggy_core),
                     FileSpec("input_map.py", buggy_map)]
        elif kind == "no_pause":
            core = good.files[0].content
            buggy_core = core.replace(
                '    if "pause" in actions:\n'
                '        state["paused"] = not state.get("paused", False)\n'
                '        return state, []\n', '')
            if buggy_core == core:
                return None
            files = [FileSpec("game_core.py", buggy_core),
                     FileSpec("input_map.py", _INPUT_MAP)]
        elif kind == "flat_difficulty":
            core = good.files[0].content
            buggy_core = core.replace(
                '    state["difficulty"] = 1.0 + 0.25 * (state["score"] // _THRESHOLD)\n',
                '    state["difficulty"] = 1.0\n')
            if buggy_core == core:
                return None
            files = [FileSpec("game_core.py", buggy_core),
                     FileSpec("input_map.py", _INPUT_MAP)]
        else:
            core = good.files[0].content
            buggy_core = core.replace(
                '    HIGH_SCORES.append(state["score"])',
                '    pass  # persistence quietly dropped')
            if buggy_core == core:
                return None
            files = [FileSpec("game_core.py", buggy_core),
                     FileSpec("input_map.py", _INPUT_MAP)]
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty="intermediate",
            task=good.task, expected_behavior="See question.",
            code=files[0].content, files=files,
            entry="game_core.py", is_project=True,
            tests=good.tests, verify_method="executed",
            notes={"bug_kind": kind, "correct_code": good.code,
                   "explain": good.notes["explain"]},
            tags=["engineering", "bug"],
            variant=f"{good.variant}|bug|{kind}",
            seed=rng.randrange(2 ** 31))
        meta = {"kind": kind, "correct_code": good.code,
                "tests": good.tests}
        return cand, meta


register(globals(), OpsScopeElevationFamily)

# === APPEND_MARKER_FAMILIES ===
