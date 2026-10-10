"""v0.8.0 media families: Remotion-craft discipline as executable TypeScript.

Reference patterns (docs/VIDEO_RESEARCH.md): remotion-dev/skills (theme/timing
conventions), video-motion-craft (12 motion rules distilled into machine
checks), claude-remotion-skill (render->inspect->fix). Everything here is
ORIGINAL synthetic code; the AI-ku signal colour is the Miku turquoise
#39C5BB (never orange) and every family bakes it in as the DEFAULT.

Verification is REAL: candidates run under Node.js native type-stripping
(see validators/executors/ts_exec.py). Golden values are computed by the
generator's own model AND harvested from a real Node run of the candidate
code; the record is only accepted when both agree byte-for-byte.

CRITICAL TS constraints (module docstring of generators/write/typescript_families.py):
  * erasable TypeScript only; imports carry explicit .ts extensions
  * the harness `tests` snippet is plain JavaScript
"""
from __future__ import annotations

import json
import random
import subprocess
import tempfile
import os

from ..core import Candidate, Family, register

SIGNAL_HEX = "#39C5BB"   # Miku turquoise - the AI-ku default signal (never orange)
SIGNAL_RGB = (57, 197, 187)

# Real cubic-bezier control points for the easing pool.
EASING_POOL = {
    "outCubic": [0.215, 0.61, 0.355, 1.0],
    "inOutQuad": [0.455, 0.03, 0.515, 0.955],
    "outQuart": [0.165, 0.84, 0.44, 1.0],
    "outBack": [0.34, 1.56, 0.64, 1.0],
}
FONT_POOLS = (
    '"JetBrains Mono", "Fira Code", monospace',
    '"Space Grotesk", "Inter", sans-serif',
    '"IBM Plex Mono", ui-monospace, monospace',
)
ASH_TONES = ("#9C978F", "#A19C93", "#97928A")
ELEMENT_POOL = ("title", "card", "bar", "badge", "panel", "label", "chip", "banner")
ORANGE = "#FF9F45"  # the forbidden default; only ever appears as a planted bug


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {"purpose": purpose, "approach": approach, "key_points": key_points,
            "big_o_time": big_o_time, "big_o_space": big_o_space,
            "edge_cases": edge_cases}


def _harvest_ts(files: dict, tests: str):
    """Run the candidate + tests under Node type-stripping; return (ok, stdout).

    Mirrors validators/executors/ts_exec.py so generators can harvest REAL
    outputs for golden values before a record is accepted.
    """
    d = tempfile.mkdtemp(prefix="harvest_")
    try:
        for path, content in files.items():
            p = os.path.join(d, path)
            os.makedirs(os.path.dirname(p) or d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        harness = ("import assert from 'assert';\n"
                   "import * as solution from './solution.ts';\n\n"
                   f"{tests}\n\ntry {{ runTests(solution); }}\n"
                   "catch (e) { console.log('HARVEST_FAIL ' + e.message); process.exit(0); }\n"
                   "console.log('__TESTS_PASSED__');\n")
        hp = os.path.join(d, "_harvest.mjs")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(harness)
        cmd = ["node", "--experimental-strip-types", "_harvest.mjs"]
        r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=20)
        return ("__TESTS_PASSED__" in r.stdout, r.stdout + r.stderr)
    except Exception as e:  # timeout, node missing, ...
        return False, str(e)
    finally:
        for root, _, fs in os.walk(d):
            for fn in fs:
                try:
                    os.remove(os.path.join(root, fn))
                except OSError:
                    pass
        try:
            os.rmdir(d)
        except OSError:
            pass


def _ts_candidate(family: Family, rng: random.Random, *, code: str, tests: str,
                  expected: str, explain: dict, bugs: dict, files=None,
                  variant: str, tags_extra=(), difficulty=None, is_project=False,
                  task_extra="", notes_extra=None) -> Candidate:
    """Shared Candidate assembly for TS media families.

    Harvest gate: the REAL Node run of the candidate must pass its own tests
    before the candidate is accepted (evidence, not claims).
    """
    entry_files = files if files is not None else {}
    payload = dict(entry_files)
    if "solution.ts" not in payload:
        payload["solution.ts"] = code
    ok, log = _harvest_ts(payload, tests)
    if not ok:
        return None
    return Candidate(
        family=family.NAME, language="typescript", domain=family.DOMAIN,
        difficulty=difficulty or rng.choice(family.DIFFICULTIES),
        task=(f"Implement the piece of a deterministic Remotion-style video "
              f"composition in TypeScript (erasable TS only, explicit .ts "
              f"imports). {expected}{task_extra} The theme's signal colour is "
              f"the Miku turquoise {SIGNAL_HEX} - AI-ku's default accent, "
              f"never orange. Code runs under Node type-stripping; the tests "
              f"execute for real."),
        expected_behavior=expected, code=code, files=files, tests=tests,
        verify_method="executed", is_project=is_project,
        notes={"explain": explain, "variant": variant, "_bug_fns": bugs,
               **(notes_extra or {})},
        tags=["media", "video_ts", *tags_extra], variant=variant,
        seed=rng.randrange(2**31))


def make_buggy_ts(family: Family, cand: Candidate, rng: random.Random):
    """Shared make_buggy for TS media families (bug fns edit solution.ts).

    Self-verifying: the buggy candidate is accepted only when it REALLY fails
    the record's tests under the real Node runner - bugs that are no-ops for
    this instance are skipped, kinds are tried in rng order. If the family
    stored a bug-for-violation map it is tried first.
    """
    from validators.executors.ts_exec import verify_ts
    bugs = cand.notes.get("_bug_fns") or {}
    if not bugs:
        return None
    viol = cand.notes.get("viol")
    mapping = cand.notes.get("bug_for_viol") or {}
    kinds = sorted(bugs)
    if viol and viol in mapping and mapping[viol] in bugs:
        kinds = [mapping[viol]] + [k for k in kinds if k != mapping[viol]]
    if cand.files:
        files = {f.path: f.content for f in cand.files}
    else:
        files = {"solution.ts": cand.code}
    for kind in kinds:
        buggy_files = bugs[kind](dict(files))
        if buggy_files == files:
            continue
        buggy_code = buggy_files["solution.ts"]
        buggy = Candidate(
            family=family.NAME, language="typescript", domain=cand.domain,
            difficulty=cand.difficulty, task=cand.task,
            expected_behavior=cand.expected_behavior, code=buggy_code,
            files=([type(cand.files[0])(p, c) for p, c in buggy_files.items()]
                   if cand.files else None),
            tests=cand.tests, verify_method="executed",
            notes={"bug_kind": kind, "correct_code": cand.code},
            tags=cand.tags, variant=cand.variant + f"|bug|{kind}", seed=cand.seed)
        r = verify_ts(buggy)
        if not r.ok:
            return (buggy, {"kind": kind, "problem": cand.variant,
                            "correct_code": cand.code,
                            "unit_notes": cand.notes.get("explain", {})})
    return None


# ------------------------------------------------------------------- theme
class MediaTSThemeFamily(Family):
    """theme.ts discipline: one file owns every colour/easing/font decision.

    A raw hex inside a component is a defect; the default accent is the Miku
    turquoise #39C5BB and the accent list holds exactly ONE colour.
    """
    NAME = "media_ts_theme"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["theme_module", "accent_sweep"])
        if kind == "theme_module":
            cand = self._theme_module(rng)
        else:
            cand = self._accent_sweep(rng)
        return cand

    # -- kind 1: the theme module itself -----------------------------------
    def _theme_module(self, rng: random.Random) -> Candidate:
        ease_keys = sorted(rng.sample(sorted(EASING_POOL), rng.randint(2, 3)))
        easing = {k: EASING_POOL[k] for k in ease_keys}
        font = rng.choice(FONT_POOLS)
        ash = rng.choice(ASH_TONES)
        code = (
            "/**\n"
            " * theme.ts - the single source of visual truth for the composition.\n"
            " * Every colour, easing curve and font decision lives HERE; a raw hex\n"
            " * inside a component is a review-blocking defect.\n"
            " */\n\n"
            "export interface Palette {\n"
            "  signal: string;\n"
            "  ink: string;\n"
            "  bone: string;\n"
            "  ash: string;\n"
            "}\n\n"
            "/** Cubic-bezier control points [x1, y1, x2, y2]; x must be monotone. */\n"
            "export type Easing = readonly [number, number, number, number];\n\n"
            f"export const PALETTE: Palette = {{\n"
            f"  signal: {SIGNAL_HEX!r},  // Miku turquoise - the default signal\n"
            "  ink: '#0A0A0B',\n"
            "  bone: '#EEE9DF',\n"
            f"  ash: {ash!r},\n"
            "};\n\n"
            "/** The accent list: exactly ONE colour, the signal teal. */\n"
            f"export const ACCENTS: readonly string[] = [{SIGNAL_HEX!r}];\n\n"
            "export const EASING: Readonly<Record<string, Easing>> = "
            + json.dumps(easing).replace("[", "[").replace("]", "]") + ";\n\n"
            f"export const FONT_STACK: string = {font!r};\n")
        tests = _wrap_tests(
            "assert.deepStrictEqual(solution.PALETTE.signal, '#39C5BB');\n"
            "assert.deepStrictEqual(solution.PALETTE.ink, '#0A0A0B');\n"
            "assert.deepStrictEqual(solution.PALETTE.bone, '#EEE9DF');\n"
            "assert.deepStrictEqual(solution.ACCENTS, ['#39C5BB']);\n"
            "assert.strictEqual(solution.ACCENTS.length, 1, 'one accent per frame');\n"
            "assert.strictEqual(typeof solution.FONT_STACK, 'string');\n"
            f"assert.ok(solution.FONT_STACK.length > 0);\n"
            "const keys = " + json.dumps(ease_keys) + ";\n"
            "for (const k of keys) {\n"
            "  const e = solution.EASING[k];\n"
            "  assert.ok(Array.isArray(e) && e.length === 4, 'easing ' + k);\n"
            "  assert.ok(e[0] < e[2], 'easing ' + k + ' x must be monotone');\n"
            "}\n")
        expected = (f"Theme module exporting PALETTE (signal {SIGNAL_HEX}, ink, "
                    f"bone, ash {ash}), exactly one accent ({SIGNAL_HEX}), the "
                    f"{', '.join(ease_keys)} easing curve(s) with monotone x "
                    "control points, and a font stack.")
        explain = _explain(
            "Theme discipline for TS video compositions.",
            "One module owns every visual constant; components import names, "
            "never raw hex values.",
            ["a single SIGNAL constant is the whole brand",
             "easing x control points stay monotone or the curve folds",
             "ACCENTS holds one colour: one accent per frame"],
            "O(1)", "O(1)",
            ["raw hex in a component", "second accent colour", "folded easing"])
        bugs = {
            "orange_signal": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    f"signal: {SIGNAL_HEX!r}", f"signal: {ORANGE!r}")},
            "easing_folded": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    json.dumps(easing[ease_keys[0]]),
                    json.dumps([easing[ease_keys[0]][2], easing[ease_keys[0]][3],
                                easing[ease_keys[0]][0], easing[ease_keys[0]][1]]))},
            "dual_accent": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    f"= [{SIGNAL_HEX!r}]", f"= [{SIGNAL_HEX!r}, {ORANGE!r}]")},
        }
        cand = _ts_candidate(
            self, rng, code=code, tests=tests, expected=expected, explain=explain,
            bugs=bugs, variant="theme_module", tags_extra=["theme"],
            task_extra=(" Enforce theme.ts discipline: every colour/easing/font "
                        "decision is exported from this one module."))
        if cand is not None and rng.random() < 0.5:
            cand.difficulty = "advanced"
        return cand

    # -- kind 2: one-accent-per-frame sweep --------------------------------
    def _accent_sweep(self, rng: random.Random) -> Candidate:
        n_frames = rng.randint(18, 30)
        els = rng.sample(ELEMENT_POOL, rng.randint(3, 5))
        frames = []
        # guaranteed violations: on these frames elements 0 AND 1 are forced
        # visible and both wear the accent -> exactly two accents
        viol_frames = sorted(rng.sample(range(2, n_frames), rng.randint(2, 3)))
        for f in range(n_frames):
            row = []
            for i, el in enumerate(els):
                visible = ((f + i) % 4 != 0)
                if f in viol_frames and i in (0, 1):
                    visible = True
                accent = (i == 0) or (f in viol_frames and i == 1)
                row.append({"el": el, "visible": visible,
                            "color": "signal" if accent else "bone"})
            frames.append(row)
        code = (
            "/** Frame element specs as data; 'signal' marks the accent colour. */\n"
            "export interface FrameSpec { el: string; visible: boolean; color: string; }\n"
            "export const FRAMES: readonly (readonly FrameSpec[])[] = "
            + json.dumps([[e for e in row] for row in frames]) + ";\n\n"
            "/**\n"
            " * Return the frame indices where MORE THAN ONE visible element wears\n"
            " * the accent colour (the 'one accent per frame' rule). Hidden elements\n"
            " * never count.\n"
            " */\n"
            "export function accentViolations(frames) {\n"
            "  const out = [];\n"
            "  for (let f = 0; f < frames.length; f++) {\n"
            "    let n = 0;\n"
            "    for (const spec of frames[f]) {\n"
            "      if (spec.visible && spec.color === 'signal') n++;\n"
            "    }\n"
            "    if (n > 1) out.push(f);\n"
            "  }\n"
            "  return out;\n"
            "}\n")
        sol_viol = [f for f in range(n_frames)
                    if sum(1 for e in frames[f] if e["visible"] and e["color"] == "signal") > 1]
        tests = _wrap_tests(
            "assert.deepStrictEqual(solution.accentViolations(solution.FRAMES), "
            + json.dumps(sol_viol) + ");\n"
            "const single = solution.FRAMES.map((row) => row.map((s) =>\n"
            "  ({ ...s, color: s.color === 'signal' && s.el !== "
            + json.dumps(els[0]) + " ? 'bone' : s.color })));\n"
            "assert.deepStrictEqual(solution.accentViolations(single), []);\n")
        expected = (f"accentViolations flags exactly frames {sol_viol} where two "
                    f"visible elements wear the {SIGNAL_HEX} accent; a cleaned "
                    "single-accent version returns no violations.")
        explain = _explain(
            "The 'one accent per frame' rule as a mechanical sweep.",
            "Count visible accent-coloured elements per frame; flag frames with "
            "more than one.",
            ["hidden elements never violate the rule",
             "the sweep is data-driven: frames are values, not side effects",
             "an empty violations list is the acceptance gate"],
            "O(frames * elements)", "O(frames)",
            ["two accents on one frame", "accent on a hidden element", "no accents"])
        bugs = {
            "allows_two": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (n > 1) out.push(f);", "if (n > 2) out.push(f);")},
            "first_only": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "return out;", "return out.slice(0, 1);")},
            "visibility_inverted": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (spec.visible && spec.color === 'signal') n++;",
                    "if (!spec.visible && spec.color === 'signal') n++;")},
        }
        return _ts_candidate(
            self, rng, code=code, tests=tests, expected=expected, explain=explain,
            bugs=bugs, variant="accent_sweep", tags_extra=["accent_sweep"])

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        return make_buggy_ts(self, cand, rng)


# ------------------------------------------------------------ motion rules
class MediaTSMotionRulesFamily(Family):
    """video-motion-craft's non-negotiables as executable invariants.

    Rules checked on tween PROGRAMS (data, not pixels): entrances carry a real
    easing curve, an entrance animates more than opacity alone, every tween
    stays inside the composition, and a linear ease on a non-entrance is fine.
    """
    NAME = "media_ts_motion_rules"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging")

    def _program(self, rng: random.Random):
        """Build a tween program with known violations; return (tweens, total, expected)."""
        total = rng.choice([60, 72, 90])
        els = rng.sample(ELEMENT_POOL, rng.randint(3, 5))
        tweens = []
        expected = []
        start = 0
        for i, el in enumerate(els):
            ease = rng.choice([k for k in EASING_POOL if k != "outBack"])
            # entrance: opacity + one transform (legal)
            tweens.append({"el": el, "prop": "opacity", "from": 0, "to": 1,
                           "start": start, "dur": rng.choice([8, 10, 12]),
                           "ease": ease})
            tweens.append({"el": el, "prop": rng.choice(["x", "y", "scale"]),
                           "from": rng.choice([-24, -12, 88]), "to": 0,
                           "start": start, "dur": rng.choice([8, 10, 12]),
                           "ease": ease})
            start += rng.choice([4, 5, 6])
        # a LEGAL linear ease on a non-entrance tween (drift) - the audit must
        # NOT flag it: linear is banned on entrances only
        drift_el = els[0]
        tweens.append({"el": drift_el, "prop": "driftx", "from": 0, "to": 6,
                       "start": start, "dur": rng.choice([12, 16]),
                       "ease": "linear"})
        # planted violations
        viol = rng.choice(["linear_entrance", "opacity_only", "unclamped",
                           "linear_and_opacity"])
        v_el = rng.choice(els)
        if viol == "linear_entrance":
            tweens.append({"el": v_el + "2", "prop": "opacity", "from": 0, "to": 1,
                           "start": start, "dur": 10, "ease": "linear"})
            tweens.append({"el": v_el + "2", "prop": "x", "from": -20, "to": 0,
                           "start": start, "dur": 10, "ease": "outCubic"})
            expected.append(f"linear_entrance:{v_el}2")
        elif viol == "opacity_only":
            tweens.append({"el": v_el + "2", "prop": "opacity", "from": 0, "to": 1,
                           "start": start, "dur": 10, "ease": "outCubic"})
            expected.append(f"opacity_only:{v_el}2")
        elif viol == "unclamped":
            tweens.append({"el": v_el + "2", "prop": "x", "from": 0, "to": 40,
                           "start": total - 3, "dur": 8, "ease": "outCubic"})
            expected.append(f"unclamped:{v_el}2")
        else:  # linear_and_opacity
            tweens.append({"el": v_el + "2", "prop": "opacity", "from": 0, "to": 1,
                           "start": start, "dur": 10, "ease": "linear"})
            expected.append(f"linear_entrance:{v_el}2")
            expected.append(f"opacity_only:{v_el}2")
        # a legal end-exactly-at-total tween (boundary: NOT a violation)
        tweens.append({"el": "endcap", "prop": "x", "from": 0, "to": 10,
                       "start": total - 10, "dur": 10, "ease": "outCubic"})
        return tweens, total, sorted(expected), viol

    def generate(self, rng: random.Random) -> Candidate:
        tweens, total, expected, viol = self._program(rng)
        code = (
            "/** Tween program as data: pure input for the motion audit. */\n"
            "export const TOTAL_FRAMES = " + str(total) + ";\n"
            "export const TWEENS = " + json.dumps(tweens) + ";\n\n"
            "/**\n"
            " * Motion-craft audit. An ENTRANCE is a tween with prop 'opacity',\n"
            " * from 0 (a fade-in). Rules:\n"
            " *   linear_entrance:<el>  an entrance with ease 'linear'\n"
            " *   opacity_only:<el>    an element whose ONLY tween is its entrance\n"
            " *   unclamped:<el>       a tween with start < 0 or start + dur > TOTAL\n"
            " * A tween ending exactly at TOTAL_FRAMES is legal.\n"
            " * Violations are unique, in first-encounter order, formatted\n"
            " * '<rule>:<el>'.\n"
            " */\n"
            "export function auditMotion(tweens, totalFrames) {\n"
            "  const out = [];\n"
            "  const seen = new Set();\n"
            "  const push = (rule, el) => {\n"
            "    const k = rule + ':' + el;\n"
            "    if (!seen.has(k)) { seen.add(k); out.push(k); }\n"
            "  };\n"
            "  const byEl = new Map();\n"
            "  for (const t of tweens) {\n"
            "    if (!byEl.has(t.el)) byEl.set(t.el, []);\n"
            "    byEl.get(t.el).push(t);\n"
            "  }\n"
            "  for (const t of tweens) {\n"
            "    if (t.start < 0 || t.start + t.dur > totalFrames)\n"
            "      push('unclamped', t.el);\n"
            "  }\n"
            "  for (const [el, ts] of byEl) {\n"
            "    const entrance = ts.find((t) => t.prop === 'opacity' && t.from === 0);\n"
            "    if (entrance && entrance.ease === 'linear') push('linear_entrance', el);\n"
            "    if (entrance && ts.length === 1) push('opacity_only', el);\n"
            "  }\n"
            "  return out;\n"
            "}\n")
        tests = _wrap_tests(
            "assert.deepStrictEqual(solution.auditMotion(solution.TWEENS, solution.TOTAL_FRAMES), "
            + json.dumps(expected) + ");\n"
            "assert.deepStrictEqual(solution.auditMotion([], 60), []);\n"
            "// a tween ending exactly at total is legal (no unclamped)\n"
            "const cap = [{ el: 'cap', prop: 'x', from: 0, to: 1, start: "
            + str(total - 10) + ", dur: 10, ease: 'outCubic' }];\n"
            "assert.deepStrictEqual(solution.auditMotion(cap, " + str(total) + "), []);\n")
        expected = (f"auditMotion reports exactly {expected} for the seeded "
                    f"{total}-frame program: entrances carry real easings, an "
                    "entrance never travels alone, and every tween stays inside "
                    "the composition (ending exactly at the last frame is legal).")
        explain = _explain(
            "The motion-craft non-negotiables as data checks.",
            "Tweens are values; the audit walks them once, dedupes violations "
            "and emits stable rule:element strings.",
            ["linear ease is banned on entrances only, not everywhere",
             "an entrance must move a second property (no lonely fades)",
             "boundary: end == total is legal, end > total is not"],
            "O(tweens)", "O(tweens)",
            ["tween ending at the last frame", "duplicate violations",
             "element with only an opacity fade"])
        bugs = {
            "skips_opacity_only": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "    if (entrance && ts.length === 1) push('opacity_only', el);\n",
                    "")},
            "skips_linear": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (entrance && entrance.ease === 'linear') push('linear_entrance', el);\n",
                    "")},
            "boundary_off_by_one": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (t.start < 0 || t.start + t.dur > totalFrames)",
                    "if (t.start < 0 || t.start + t.dur >= totalFrames)")},
            "linear_everywhere": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (entrance && entrance.ease === 'linear') push('linear_entrance', el);",
                    "if (ts.some((t) => t.ease === 'linear')) push('linear_entrance', el);")},
        }
        return _ts_candidate(
            self, rng, code=code, tests=tests, expected=expected, explain=explain,
            bugs=bugs, variant="tween_audit", tags_extra=["motion_rules"],
            notes_extra={"viol": viol,
                         "bug_for_viol": {"linear_entrance": "skips_linear",
                                          "linear_and_opacity": "skips_opacity_only",
                                          "opacity_only": "skips_opacity_only",
                                          "unclamped": "boundary_off_by_one"}})

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        return make_buggy_ts(self, cand, rng)


def _wrap_tests(body: str) -> str:
    return ("/**\n * @param {typeof import('./solution.ts')} solution\n */\n"
            "function runTests(solution) {\n" + body + "}\n")


# ------------------------------------------------------ deterministic render
def _mulberry32_stream(seed: int):
    """Exact python mirror of the mulberry32 PRNG the TS code must implement."""
    M = 0xFFFFFFFF
    state = seed & M

    def nxt():
        nonlocal state
        state = (state + 0x6D2B79F5) & M
        t = ((state ^ (state >> 15)) * (1 | state)) & M
        t = ((((t ^ (t >> 7)) * (61 | t)) & M) + t) & M ^ t
        t = (t ^ (t >> 14)) & M
        return t / 4294967296.0

    return nxt


class MediaTSDeterministicRenderFamily(Family):
    """Seeded PRNG (mulberry32) + pure frame state; no Date.now, no Math.random.

    Golden positions are computed by the generator's model AND harvested from
    a real Node run; the record is dropped if the two ever disagree.
    """
    NAME = "media_ts_deterministic_render"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging")

    def _model(self, seed: int, t: int, w: int, h: int, n: int):
        r = _mulberry32_stream(seed + t)
        out = []
        for i in range(n):
            ew = 6 + int(r() * 5)
            eh = 4 + int(r() * 3)
            x = int(r() * (w - ew))
            y = int(r() * (h - eh))
            out.append({"el": f"e{i}", "x": x, "y": y, "w": ew, "h": eh})
        return out

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["seeded_frame", "render_compare"])
        seed = rng.randint(1000, 99999)
        w, h = 64, 32
        n = rng.randint(3, 5)
        probes = sorted(rng.sample(range(0, 48), 2))
        if kind == "seeded_frame":
            golden = [self._model(seed, t, w, h, n) for t in probes]
            code = (
                "/**\n"
                " * Deterministic frame state for a video composition.\n"
                " * frames are a PURE function of (t, seed): mulberry32 re-seeded\n"
                " * per frame; no Date.now(), no Math.random().\n"
                " */\n"
                "export function mulberry32(seed: number): () => number {\n"
                "  let a = seed >>> 0;\n"
                "  return () => {\n"
                "    a = (a + 0x6D2B79F5) | 0;\n"
                "    let t = Math.imul(a ^ (a >>> 15), 1 | a);\n"
                "    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;\n"
                "    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;\n"
                "  };\n"
                "}\n\n"
                "export interface Box { el: string; x: number; y: number; w: number; h: number; }\n\n"
                "/** Layout for frame t: n boxes, positions from the seeded stream. */\n"
                "export function frameAt(t: number, seed: number, w: number, h: number): Box[] {\n"
                "  const rand = mulberry32(seed + t);\n"
                f"  const n = {n};\n"
                "  const out: Box[] = [];\n"
                "  for (let i = 0; i < n; i++) {\n"
                "    const bw = 6 + Math.floor(rand() * 5);\n"
                "    const bh = 4 + Math.floor(rand() * 3);\n"
                "    const x = Math.floor(rand() * (w - bw));\n"
                "    const y = Math.floor(rand() * (h - bh));\n"
                "    out.push({ el: 'e' + i, x, y, w: bw, h: bh });\n"
                "  }\n"
                "  return out;\n"
                "}\n")
            tests = _wrap_tests(
                f"const golden = {json.dumps(golden)};\n"
                f"assert.deepStrictEqual(solution.frameAt({probes[0]}, {seed}, {w}, {h}), golden[0]);\n"
                f"assert.deepStrictEqual(solution.frameAt({probes[1]}, {seed}, {w}, {h}), golden[1]);\n"
                f"assert.deepStrictEqual(solution.frameAt({probes[0]}, {seed}, {w}, {h}), "
                f"solution.frameAt({probes[0]}, {seed}, {w}, {h}), 'determinism');\n"
                f"assert.notDeepStrictEqual(solution.frameAt(1, {seed}, {w}, {h}), "
                f"solution.frameAt(2, {seed}, {w}, {h}), 'frames differ');\n"
                f"for (const b of solution.frameAt({probes[0]}, {seed}, {w}, {h})) {{\n"
                "  assert.ok(b.x >= 0 && b.x + b.w <= " + str(w) + ", 'x in bounds');\n"
                "  assert.ok(b.y >= 0 && b.y + b.h <= " + str(h) + ", 'y in bounds');\n}\n")
            expected = (f"frameAt re-seeds mulberry32 with seed + t and lays out "
                        f"{n} boxes; frame {probes[0]} and {probes[1]} reproduce "
                        "the golden layout exactly, consecutive frames differ, "
                        "and every box stays inside the 64x32 viewport.")
            explain = _explain(
                "Deterministic rendering starts with a seeded PRNG.",
                "mulberry32 (32-bit integer mixing) re-seeded per frame makes "
                "every frame a pure function; renders become byte-reproducible.",
                ["seed + t re-seeding: frames never share a stream position",
                 "Math.imul keeps the mixing in 32-bit space",
                 "no Date.now() / Math.random(): same inputs, same pixels"],
                "O(elements) per frame", "O(elements)",
                ["shared stream across frames", "Math.random leak",
                 "box partially outside the viewport"])
            bugs = {
                "math_random": lambda fl: {
                    **fl, "solution.ts": fl["solution.ts"].replace(
                        "const rand = mulberry32(seed + t);",
                        "const rand = Math.random;")},
                "span_off_by_one": lambda fl: {
                    **fl, "solution.ts": fl["solution.ts"].replace(
                        "Math.floor(rand() * (w - bw));",
                        "Math.floor(rand() * (w - bw + 1));")},
                "static_seed": lambda fl: {
                    **fl, "solution.ts": fl["solution.ts"].replace(
                        "const rand = mulberry32(seed + t);",
                        "const rand = mulberry32(seed);")},
            }
            return _ts_candidate(
                self, rng, code=code, tests=tests, expected=expected,
                explain=explain, bugs=bugs, variant=kind,
                tags_extra=["determinism"])

        # render_compare
        golden0 = self._model(seed, 3, w, h, n)
        golden1 = self._model(seed, 4, w, h, n)
        mut = [dict(b) for b in golden1]
        mut_idx = rng.randrange(len(mut))
        mut[mut_idx]["x"] = mut[mut_idx]["x"] + 1
        code = (
            "/** Two independent renders of the same seeded composition. */\n"
            "export function frameAt(t: number, seed: number, w: number, h: number) {\n"
            "  let a = (seed + t) >>> 0;\n"
            "  const rand = () => {\n"
            "    a = (a + 0x6D2B79F5) | 0;\n"
            "    let x = Math.imul(a ^ (a >>> 15), 1 | a);\n"
            "    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;\n"
            "    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;\n"
            "  };\n"
            f"  const n = {n};\n"
            "  const out = [];\n"
            "  for (let i = 0; i < n; i++) {\n"
            "    const bw = 6 + Math.floor(rand() * 5);\n"
            "    const bh = 4 + Math.floor(rand() * 3);\n"
            "    out.push({ el: 'e' + i, x: Math.floor(rand() * (w - bw)),\n"
            "               y: Math.floor(rand() * (h - bh)), w: bw, h: bh });\n"
            "  }\n"
            "  return out;\n"
            "}\n\n"
            "export function renderFrames(count: number, seed: number, w: number, h: number) {\n"
            "  const out = [];\n"
            "  for (let t = 3; t < 3 + count; t++) out.push(frameAt(t, seed, w, h));\n"
            "  return out;\n"
            "}\n\n"
            "/** First index where the frame arrays differ, or -1. */\n"
            "export function compareFrames(a, b) {\n"
            "  if (a.length !== b.length) return -2;\n"
            "  for (let i = 0; i < a.length; i++) {\n"
            "    const fa = a[i], fb = b[i];\n"
            "    if (fa.length !== fb.length) return i;\n"
            "    for (let j = 0; j < fa.length; j++) {\n"
            "      for (const k of ['el', 'x', 'y', 'w', 'h']) {\n"
            "        if (fa[j][k] !== fb[j][k]) return i;\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "  return -1;\n"
            "}\n")
            # compare returns FRAME index (a[i] is a frame = array of boxes)
        frames_json = json.dumps(json.dumps([golden0, golden1]))
        tests = _wrap_tests(
            f"const a = solution.renderFrames(2, {seed}, {w}, {h});\n"
            f"const b = solution.renderFrames(2, {seed}, {w}, {h});\n"
            "assert.deepStrictEqual(a, b, 'double render is byte-identical');\n"
            f"const ref = JSON.parse({frames_json});\n"
            "assert.deepStrictEqual(a, ref, 'golden frames reproduce');\n"
            "assert.strictEqual(solution.compareFrames(a, a), -1);\n"
            f"const mut = JSON.parse({frames_json});\n"
            f"mut[1][{mut_idx}].x = mut[1][{mut_idx}].x + 1;\n"
            "assert.strictEqual(solution.compareFrames(a, mut), 1, 'mutation at frame 1');\n"
            "assert.strictEqual(solution.compareFrames(a, []), -2, 'length mismatch');\n")
        expected = ("renderFrames is byte-identical across runs; compareFrames "
                    "returns -1 for equal sequences, -2 for length mismatches "
                    f"and the exact frame index (here 1) where a mutation lives.")
        explain = _explain(
            "Render verification: compare two independent renders.",
            "Deterministic frames make renders comparable frame-by-frame; the "
            "comparator reports the first differing frame index.",
            ["double-render equality is the determinism gate",
             "report the FIRST differing frame, not a boolean",
             "length mismatch is its own signal (-2)"],
            "O(frames * elements)", "O(1)",
            ["mutation in the last frame", "empty sequence", "element reordering"])
        bugs = {
            "skips_last_frame": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "for (let i = 0; i < a.length; i++) {",
                    "for (let i = 0; i + 1 < a.length; i++) {")},
            "shallow_compare": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "if (fa[j][k] !== fb[j][k]) return i;", "")},
        }
        return _ts_candidate(
            self, rng, code=code, tests=tests, expected=expected,
            explain=explain, bugs=bugs, variant=kind,
            tags_extra=["determinism"])

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        return make_buggy_ts(self, cand, rng)


register(globals(), MediaTSThemeFamily)
register(globals(), MediaTSMotionRulesFamily)
register(globals(), MediaTSDeterministicRenderFamily)
