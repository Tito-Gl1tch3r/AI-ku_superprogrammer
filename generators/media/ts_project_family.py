"""v0.8.0 media family: the TS/Remotion-style multi-file video project (expert).

The pdoom-video architecture ported to TypeScript: theme.ts owns every colour,
timeline.ts owns the schedule + MEASURED beat grid, scenes.ts are pure frame
functions, compose.ts emits a deterministic command stream, and the harness
verifies the real Node output against the generator's independent python
model (double implementation, byte-equal on probe frames).

An expert record: difficulty='expert' -> routes to hard_holdout under the
media policy (complete projects are the unseen-projects eval set).
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, Family, FileSpec, register
from .ts_video_families import (_harvest_ts, SIGNAL_HEX, _explain)
from .ts_beat_families import synthesize_track, measure_beats

SCENE_POOL = ("open", "pulse", "drift", "outro", "flash")
VIEW_W, VIEW_H, FPS = 64, 32, 24


def _model_scene(name, pn, pd, w=VIEW_W, h=VIEW_H):
    """Generator's reference model of one scene's commands (integer math)."""
    cmds = []
    m = 4
    if name == "open":
        panel_w = w - 2 * m
        cmds.append({"op": "rect", "x": m, "y": m, "w": panel_w, "h": 10,
                     "color": "bone"})
        line_w = (pn * (panel_w - 4)) // pd
        cmds.append({"op": "rect", "x": m + 2, "y": m + 12, "w": 2 + line_w,
                     "h": 2, "color": "signal"})
    elif name == "pulse":
        bar_h = 2 + (pn * 4) // pd
        cmds.append({"op": "rect", "x": m, "y": (h - 12 - bar_h), "w": w - 2 * m,
                     "h": bar_h, "color": "signal"})
    elif name == "drift":
        bw, bh = 10, 6
        x = m + (pn * (w - 2 * m - bw)) // pd
        cmds.append({"op": "rect", "x": x, "y": (h - 14) // 2, "w": bw,
                     "h": bh, "color": "bone"})
    elif name == "outro":
        bar_w = w - 2 * m - (pn * (w - 2 * m)) // pd
        cmds.append({"op": "rect", "x": m, "y": h - 10, "w": bar_w, "h": 4,
                     "color": "ash"})
    else:  # flash
        if pn == 0:
            cmds.append({"op": "rect", "x": 0, "y": 0, "w": w, "h": h,
                         "color": "signal"})
        else:
            cmds.append({"op": "rect", "x": m, "y": m, "w": w - 2 * m,
                         "h": h - 2 * m, "color": "ash"})
    return cmds


def _model_compose(frame, scenes, words, w=VIEW_W, h=VIEW_H):
    """Full reference compose: bg + scene + karaoke bar (integer math)."""
    cmds = [{"op": "rect", "x": 0, "y": 0, "w": w, "h": h, "color": "ink"}]
    for start, end, name in scenes:
        if start <= frame < end:
            cmds += _model_scene(name, frame - start, end - start, w, h)
            break
    fill = 0
    for s, e, _text in words:
        if s <= frame < e:
            fill = ((frame - s) * w) // (e - s)
            break
    if fill > 0:
        cmds.append({"op": "rect", "x": 0, "y": h - 4, "w": fill, "h": 4,
                     "color": "signal"})
    return cmds


class MediaTSProjectFamily(Family):
    """Multi-file TS composition: theme + timeline + scenes + compose."""
    NAME = "media_ts_mv_project"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("expert",)
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        pkg = rng.choice(["tealframe", "mvmotion"])
        length = rng.choice([40, 48])
        names = rng.sample(SCENE_POOL, 3)
        scenes = [(i * length, (i + 1) * length, names[i]) for i in range(3)]
        total = 3 * length
        # real audio measurement for the timeline's beat grid
        grid = None
        for _ in range(4):
            _beats, pcm, sr, nominal, _drift = synthesize_track(
                rng, sr=8000, dur=total / FPS + 1.0)
            frames, bpm = measure_beats(pcm, sr, FPS)
            if frames:
                in_view = [f for f in frames if f < total]
                if 4 <= len(in_view) <= total // 6:
                    grid = in_view
                    break
        if grid is None:
            return None
        # word windows in FRAMES (integer, end-exclusive)
        line = rng.choice(["one more epoch and I am gone",
                           "the gradient hums a lullaby",
                           "the loss curve bends for you"])
        parts = line.split(" ")
        t = 0.0
        words = []
        for wd in parts:
            dur = rng.choice([0.4, 0.5])
            s, e = round(t * FPS), round((t + dur) * FPS)
            if e > s:
                words.append([s, e, wd])
            t += dur + 0.1
        if len(words) < 3:
            return None

        theme = (
            "/** theme.ts - the single source of visual truth. */\n"
            "export const ROLES = {\n"
            f"  signal: {SIGNAL_HEX!r},  // Miku turquoise - the default accent\n"
            "  ink: '#0A0A0B',\n"
            "  bone: '#EEE9DF',\n"
            "  ash: '#9C978F',\n"
            "} as const;\n"
            "export type Role = keyof typeof ROLES;\n"
            "export const EASING_OUT_CUBIC: [number, number, number, number] = "
            "[0.215, 0.61, 0.355, 1.0];\n"
            "export const FONT_STACK = 'JetBrains Mono, monospace';\n")
        timeline = (
            "/** timeline.ts - schedule + MEASURED beat grid (real analysis). */\n"
            f"export const FPS = {FPS};\n"
            f"export const SCENES: readonly (readonly [number, number, string])[] = "
            + json.dumps(scenes) + ";\n"
            "// beats measured from the generated track's waveform (onset\n"
            "// detection) - never assumed from a nominal bpm\n"
            "export const BEAT_FRAMES: readonly number[] = "
            + json.dumps(grid) + ";\n"
            "export const WORDS: readonly (readonly [number, number, string])[] = "
            + json.dumps(words) + ";\n\n"
            "export function activeScene(frame: number):\n"
            "        readonly [number, number, string] | null {\n"
            "  for (const s of SCENES) {\n"
            "    if (frame >= s[0] && frame < s[1]) return s;\n"
            "  }\n"
            "  return null;\n"
            "}\n")
        scenes_ts = (
            "/** scenes.ts - pure frame -> element specs (integer math only). */\n"
            "import type { Role } from './theme.ts';\n\n"
            "export interface Rect { op: 'rect'; x: number; y: number;\n"
            "                        w: number; h: number; color: Role; }\n\n"
            "export function sceneCommands(name: string, pn: number, pd: number,\n"
            "                              w: number, h: number): Rect[] {\n"
            "  const m = 4;\n"
            "  if (name === 'open') {\n"
            "    const panelW = w - 2 * m;\n"
            "    const lineW = Math.trunc((pn * (panelW - 4)) / pd);\n"
            "    return [\n"
            "      { op: 'rect', x: m, y: m, w: panelW, h: 10, color: 'bone' },\n"
            "      { op: 'rect', x: m + 2, y: m + 12, w: 2 + lineW, h: 2,\n"
            "        color: 'signal' },\n"
            "    ];\n"
            "  }\n"
            "  if (name === 'pulse') {\n"
            "    const barH = 2 + Math.trunc((pn * 4) / pd);\n"
            "    return [{ op: 'rect', x: m, y: h - 12 - barH, w: w - 2 * m,\n"
            "              h: barH, color: 'signal' }];\n"
            "  }\n"
            "  if (name === 'drift') {\n"
            "    const bw = 10;\n"
            "    const x = m + Math.trunc((pn * (w - 2 * m - bw)) / pd);\n"
            "    return [{ op: 'rect', x, y: Math.trunc((h - 14) / 2), w: bw,\n"
            "              h: 6, color: 'bone' }];\n"
            "  }\n"
            "  if (name === 'outro') {\n"
            "    const barW = w - 2 * m - Math.trunc((pn * (w - 2 * m)) / pd);\n"
            "    return [{ op: 'rect', x: m, y: h - 10, w: barW, h: 4,\n"
            "              color: 'ash' }];\n"
            "  }\n"
            "  if (pn === 0) {\n"
            "    return [{ op: 'rect', x: 0, y: 0, w, h, color: 'signal' }];\n"
            "  }\n"
            "  return [{ op: 'rect', x: m, y: m, w: w - 2 * m, h: h - 2 * m,\n"
            "            color: 'ash' }];\n"
            "}\n")
        compose_ts = (
            "/** compose.ts - frame index -> deterministic command stream. */\n"
            "import { sceneCommands } from './scenes.ts';\n"
            "import type { Rect } from './scenes.ts';\n"
            "import { activeScene, WORDS } from './timeline.ts';\n\n"
            f"export const WIDTH = {VIEW_W};\n"
            f"export const HEIGHT = {VIEW_H};\n\n"
            "export function compose(frame: number): Rect[] {\n"
            "  const cmds: Rect[] = [{ op: 'rect', x: 0, y: 0, w: WIDTH,\n"
            "                          h: HEIGHT, color: 'ink' }];\n"
            "  const scene = activeScene(frame);\n"
            "  if (scene) {\n"
            "    const [s, e, name] = scene;\n"
            "    cmds.push(...sceneCommands(name, frame - s, e - s, WIDTH, HEIGHT));\n"
            "  }\n"
            "  let fill = 0;\n"
            "  for (const [s, e] of WORDS) {\n"
            "    if (frame >= s && frame < e) {\n"
            "      fill = Math.trunc(((frame - s) * WIDTH) / (e - s));\n"
            "      break;\n"
            "    }\n"
            "  }\n"
            "  if (fill > 0) {\n"
            "    cmds.push({ op: 'rect', x: 0, y: HEIGHT - 4, w: fill, h: 4,\n"
            "                color: 'signal' });\n"
            "  }\n"
            "  return cmds;\n"
            "}\n")
        solution_ts = (
            "/** solution.ts - facade for the harness. */\n"
            "export { compose, WIDTH, HEIGHT } from './compose.ts';\n"
            "export { ROLES } from './theme.ts';\n"
            "export { SCENES, BEAT_FRAMES, WORDS } from './timeline.ts';\n")
        manifest = json.dumps({
            "fps": FPS, "width": VIEW_W, "height": VIEW_H,
            "total_frames": total, "signal": SIGNAL_HEX,
            "scenes": [n for _, _, n in scenes]}, indent=1) + "\n"
        readme = (
            f"# {pkg}\n\n"
            "TS composition engine: theme owns every colour, timeline owns the\n"
            "schedule + MEASURED beat grid, scenes are pure functions, compose\n"
            "emits a deterministic command stream (offline-render friendly).\n\n"
            f"- `{pkg}/theme.ts`: palette + easing + font (signal = {SIGNAL_HEX})\n"
            f"- `{pkg}/timeline.ts`: scenes, beats (measured), word frames\n"
            f"- `{pkg}/scenes.ts`: pure per-scene specs\n"
            f"- `{pkg}/compose.ts`: frame -> command stream\n"
            "- `manifest.json`: render configuration\n")

        # ---- golden probes from the generator's python model ---------------
        probes = sorted(rng.sample(range(total), 4))
        golden = [_model_compose(f, scenes, words) for f in probes]
        # ---- tests: golden equality + determinism + theme discipline -------
        tests = _wrap_tests_project(
            f"for (const f of {json.dumps(['theme.ts', 'timeline.ts', 'scenes.ts', 'compose.ts'])}) {{\n"
            "  const src = readFileSync('./' + f, 'utf8');\n"
            "  if (f !== 'theme.ts') {\n"
            "    assert.ok(!src.includes('#'), 'raw hex outside theme in ' + f);\n"
            "  }\n"
            "}\n"
            f"const probes = {json.dumps(probes)};\n"
            f"const golden = {json.dumps(golden)};\n"
            "for (let i = 0; i < probes.length; i++) {\n"
            "  assert.deepStrictEqual(solution.compose(probes[i]), golden[i],\n"
            "                         'golden frame ' + probes[i]);\n"
            "}\n"
            "assert.deepStrictEqual(solution.compose(probes[0]),\n"
            "                       solution.compose(probes[0]), 'determinism');\n"
            "assert.strictEqual(solution.ROLES.signal, '#39C5BB');\n",
            prelude="import { readFileSync } from 'node:fs';\n\n")

        files = [FileSpec(f"{pkg}/theme.ts", theme),
                 FileSpec(f"{pkg}/timeline.ts", timeline),
                 FileSpec(f"{pkg}/scenes.ts", scenes_ts),
                 FileSpec(f"{pkg}/compose.ts", compose_ts),
                 FileSpec("solution.ts", solution_ts),
                 FileSpec("manifest.json", manifest),
                 FileSpec("README.md", readme)]
        # TS imports use './theme.ts' - flat temp dir, so re-path the facade
        flat = [("theme.ts", theme), ("timeline.ts", timeline),
                ("scenes.ts", scenes_ts), ("compose.ts", compose_ts),
                ("solution.ts", solution_ts), ("manifest.json", manifest),
                ("README.md", readme)]
        flat_files = [FileSpec(p, c) for p, c in flat]
        ok, log = _harvest_ts({p: c for p, c in flat}, tests)
        if not ok:
            return None
        expected = (f"Deterministic TS composition engine ({total} frames, "
                    f"scenes {', '.join(names)}): compose(frame) emits the "
                    "golden command stream byte-for-byte (bg + scene element + "
                    f"karaoke bar), beats MEASURED from real audio, and the "
                    f"theme discipline holds (no raw hex outside theme.ts, "
                    f"signal {SIGNAL_HEX}).")
        return Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty="expert",
            task=(f"Assemble the multi-file TS composition project described by "
                  f"README.md: theme (single source of colour truth, signal = "
                  f"Miku turquoise {SIGNAL_HEX}), timeline with end-exclusive "
                  "scene windows + the MEASURED beat grid, pure integer-math "
                  "scene functions, and compose(frame) emitting the command "
                  "stream. compose must reproduce the golden probes exactly and "
                  "re-run identically; no raw hex may appear outside theme.ts."),
            expected_behavior=expected, files=flat_files,
            entry="solution.ts", tests=tests, verify_method="executed",
            is_project=True,
            notes={"explain": {"purpose": expected,
                               "approach": ("theme + timeline/state + pure "
                                            "scenes + command-stream compose, "
                                            "verified against the generator's "
                                            "independent python model."),
                               "key_points": ["frames are pure functions",
                                              "one colour source (theme.ts)",
                                              "measured beats, never assumed"],
                               "big_o_time": "O(w*h) equivalent per frame",
                               "big_o_space": "O(commands)",
                               "edge_cases": ["scene boundary frame",
                                              "karaoke gap", "first flash frame"]}},
            tags=["media", "video_ts", "project"], variant=pkg,
            seed=rng.randrange(2**31))

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        from validators.executors.ts_exec import verify_ts
        files = {f.path: f.content for f in cand.files}
        bugs = {
            "inclusive_window": lambda fl: {
                **fl, "timeline.ts": fl["timeline.ts"].replace(
                    "if (frame >= s[0] && frame < s[1]) return s;",
                    "if (frame >= s[0] && frame <= s[1]) return s;")},
            "palette_bypass": lambda fl: {
                **fl, "compose.ts": fl["compose.ts"].replace(
                    "color: 'signal' });", "color: '#39C5BB' as any });")},
            "karaoke_no_gap": lambda fl: {
                **fl, "compose.ts": fl["compose.ts"].replace(
                    "  if (fill > 0) {", "  if (fill >= 0) {")},
        }
        kinds = sorted(bugs)
        rng.shuffle(kinds)
        for kind in kinds:
            bf = bugs[kind](dict(files))
            if bf == files:
                continue
            bfiles = [FileSpec(p, c) for p, c in bf.items()]
            bcand = Candidate(
                family=self.NAME, language="typescript", domain=cand.domain,
                difficulty=cand.difficulty, task=cand.task,
                expected_behavior=cand.expected_behavior, files=bfiles,
                entry="solution.ts", tests=cand.tests,
                verify_method="executed", is_project=True,
                notes={"bug_kind": kind, "correct_code": cand.code},
                tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                seed=cand.seed)
            r = verify_ts(bcand)
            if not r.ok:
                return (bcand, {"kind": kind, "problem": cand.variant,
                                "correct_code": cand.code,
                                "unit_notes": cand.notes.get("explain", {})})
        return None


def _wrap_tests_project(body: str, prelude: str = "") -> str:
    return (prelude
            + "/**\n * @param {typeof import('./solution.ts')} solution\n */\n"
            + "function runTests(solution) {\n" + body + "}\n")


register(globals(), MediaTSProjectFamily)
