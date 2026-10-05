"""Dataset-3 extension: generative music-video engine families (MV).

Teaches the pdoom-video-style architecture with ORIGINAL code only (frames as a
pure function of time, scene timeline, word-synced karaoke typography, offline
render with hash manifests). AI-ku's default signal colour is the Miku
turquoise #39C5BB - every family bakes it in as the DEFAULT, never orange.

Verification is REAL: renderers execute via Pillow and determinism is proven
with byte-identical frames / hash-stable render_all() output.
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, Family, FileSpec, register

# AI-ku's default signal colour (Miku turquoise). Deliberately NOT orange.
SIGNAL_HEX = "#39C5BB"
SIGNAL_RGB = (57, 197, 187)

SCENE_POOL = ("open", "pulse", "flash", "drift", "outro")
LINE_POOL = (
    "ChatGPT, please don't eat me alive",
    "the gradient hums a lullaby",
    "I'm upping my p(doom) tonight",
    "one more epoch and I'm gone",
    "the loss curve bends for you",
)


def _mk_explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {"purpose": purpose, "approach": approach, "key_points": key_points,
            "big_o_time": big_o_time, "big_o_space": big_o_space,
            "edge_cases": edge_cases}


# --------------------------------------------------------------- scene engine
class MediaMVSceneEngineFamily(Family):
    """Timeline dispatch, beat snapping and the signal heat ramp."""
    NAME = "media_mv_scene_engine"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["scene_dispatch", "beat_snap", "heat_ramp"])
        if kind == "scene_dispatch":
            n = rng.randint(2, 3)
            names = rng.sample(SCENE_POOL, n)
            fps = rng.choice([24, 30])
            length = rng.choice([48, 72, 96])
            scenes = [(i * length, (i + 1) * length, names[i]) for i in range(n)]
            total = n * length
            code = (
                f"FPS = {fps}\n"
                f"SCENES = {scenes!r}\n\n\n"
                "def active_scene(frame):\n"
                "    \"\"\"Return (name, local_progress) for a frame index.\n\n"
                "    Windows are end-exclusive: the first frame of scene k+1 is\n"
                "    frame SCENES[k][1]. Outside the schedule returns (None, 0.0).\n"
                "    \"\"\"\n"
                "    for start, end, name in SCENES:\n"
                "        if start <= frame < end:\n"
                "            return name, (frame - start) / (end - start)\n"
                "    return None, 0.0\n")
            first_end = length
            tests = (
                "def run_tests():\n"
                f"    assert active_scene(0) == ({names[0]!r}, 0.0)\n"
                f"    assert active_scene({first_end}) == ({names[1]!r}, 0.0)\n"
                f"    assert active_scene({first_end - 1})[0] == {names[0]!r}\n"
                f"    assert abs(active_scene({first_end // 2})[1] - 0.5) < 1e-9\n"
                f"    assert active_scene({total}) == (None, 0.0)\n"
                "    names = [active_scene(f)[0] for f in range("
                f"{total})]\n"
                f"    assert set(names) == set({sorted(set(names))!r})\n")
            expected = (f"{n} end-exclusive scene windows of {length} frames "
                        f"({', '.join(names)}) at {fps} fps; frame boundaries hand "
                        "over exactly at window ends.")
            explain = _mk_explain(
                "Scene schedule for a code-rendered music video.",
                "Linear scan over (start, end, name) windows with end-exclusive "
                "membership; progress is normalized local time.",
                ["end-exclusive windows avoid double ownership at cuts",
                 "local progress drives per-scene animation",
                 "outside the schedule is a defined state, not an error"],
                "O(scenes) per probe", "O(1)",
                ["frame at a window boundary", "frame past the last scene",
                 "single-scene schedule"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "if start <= frame < end:", "if start <= frame <= end:")}
            bugs = {"end_inclusive_window": bug}
        elif kind == "beat_snap":
            fps = rng.choice([24, 30])
            bpm = rng.choice([100, 120, 132, 140])
            total = rng.choice([240, 360, 480])
            step = 60.0 / bpm * fps
            beats = [round(k * step) for k in range(int(total / step) + 1)]
            code = (
                f"FPS = {fps}\n"
                f"BPM = {bpm}\n\n\n"
                "def beat_frames(total_frames, bpm=BPM, fps=FPS):\n"
                "    \"\"\"Frame indices of every beat, snapped to the nearest frame.\"\"\"\n"
                "    step = 60.0 / bpm * fps\n"
                "    return [round(k * step) for k in range(int(total_frames / step) + 1)]\n\n\n"
                "def snap_to_beat(frame, beats):\n"
                "    \"\"\"Nearest beat frame; ties resolve to the earlier beat.\"\"\"\n"
                "    best = beats[0]\n"
                "    for b in beats:\n"
                "        if abs(b - frame) < abs(best - frame):\n"
                "            best = b\n"
                "    return best\n")
            tests = (
                "def run_tests():\n"
                f"    beats = beat_frames({total})\n"
                f"    assert beats == {beats!r}\n"
                f"    assert snap_to_beat({beats[1] + 1}, beats) == {beats[1]}\n"
                f"    assert snap_to_beat({beats[2] - 1}, beats) == {beats[2]}\n"
                f"    tie = ({beats[1]} + {beats[2]}) / 2\n"
                f"    assert snap_to_beat(tie, beats) == {beats[1]}  # tie -> earlier\n"
                "    assert snap_to_beat(beats[0], beats) == beats[0]\n")
            expected = (f"Beat grid at {bpm} BPM / {fps} fps (step {step:.3f} frames) "
                        f"with nearest-beat snapping and earlier-beat tie-breaks.")
            explain = _mk_explain(
                "Beat synchronization for music-video timelines.",
                "Beat period converts to frames via 60/bpm*fps and rounds; snapping "
                "is a linear nearest-neighbour scan with a deterministic tie-break.",
                ["one conversion point: seconds -> frames with round()",
                 "ties must resolve deterministically (earlier beat)",
                 "the grid is pure data - renderers index it, never recompute"],
                "O(beats + log) linear scan", "O(beats)",
                ["tie exactly between beats", "frame before first beat",
                 "beat beyond total_frames"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        if abs(b - frame) < abs(best - frame):",
                    "        if abs(b - frame) <= abs(best - frame):")}
            bugs = {"tie_break_flipped": bug}
        else:  # heat_ramp
            mid = rng.choice([0.4, 0.45, 0.5, 0.55, 0.6])
            ember = rng.choice(["#8DF6E9", "#7DEEDC", "#A5FFF0"])
            code = (
                f"SIGNAL = {SIGNAL_HEX!r}  # Miku turquoise - the AI-ku default signal colour\n"
                f"EMBER = {ember!r}  # hot turquoise core tone\n"
                "INK = (10, 10, 11)\n"
                "BONE = (238, 233, 223)\n"
                f"MID = {mid!r}\n\n\n"
                "def hex_to_rgb(hex_color):\n"
                "    h = hex_color.lstrip('#')\n"
                "    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))\n\n\n"
                "SIGNAL_RGB = hex_to_rgb(SIGNAL)\n"
                "EMBER_RGB = hex_to_rgb(EMBER)\n\n\n"
                "def mix(c0, c1, a):\n"
                "    \"\"\"Linear mix of two RGB tuples; a is clamped to [0, 1].\"\"\"\n"
                "    a = max(0.0, min(1.0, a))\n"
                "    return tuple(round(c0[i] + (c1[i] - c0[i]) * a) for i in range(3))\n\n\n"
                "def heat(x):\n"
                f"    \"\"\"0.0 = ink, MID = signal (Miku turquoise), 1.0 = white-hot bone.\"\"\"\n"
                "    x = max(0.0, min(1.0, x))\n"
                "    if x < MID:\n"
                "        return mix(INK, SIGNAL_RGB, x / MID)\n"
                "    return mix(SIGNAL_RGB, BONE, (x - MID) / (1 - MID))\n")
            tests = (
                "def run_tests():\n"
                f"    assert hex_to_rgb({SIGNAL_HEX!r}) == {SIGNAL_RGB!r}\n"
                "    assert heat(0.0) == INK\n"
                "    assert heat(MID) == SIGNAL_RGB\n"
                "    assert heat(1.0) == BONE\n"
                "    assert heat(-1.0) == INK and heat(2.0) == BONE\n"
                "    g = [heat(i / 10)[1] for i in range(11)]\n"
                "    assert g == sorted(g)  # green channel rises monotonically\n"
                "    assert EMBER_RGB != SIGNAL_RGB\n")
            expected = (f"Signal heat ramp anchored on the Miku turquoise {SIGNAL_HEX}: "
                        f"ink at 0.0, pure signal at MID={mid}, white-hot bone at 1.0, "
                        "with a hot turquoise core tone for highlights.")
            explain = _mk_explain(
                "The one-signal-colour heat ramp used across AI-ku video scenes.",
                "Two-segment lerp: ink->signal then signal->bone; hex parsed to "
                "integer RGB once at import.",
                ["a single SIGNAL constant is the whole brand",
                 "clamped interpolation keeps every pixel in gamut",
                 "monotone channels make the ramp safe for bloom"],
                "O(1) per pixel", "O(1)",
                ["x outside [0, 1]", "x exactly at MID", "midpoint purity"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))",
                    "    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))")}
            bugs = {"hex_channels_swapped": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement a deterministic piece of a generative music-video engine "
                  f"in Python (frames are a pure function of time). {expected} The "
                  f"default signal colour is the Miku turquoise {SIGNAL_HEX}, never "
                  f"orange, because this engine renders AI-ku-branded videos."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "music_video", kind], variant=kind,
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


# -------------------------------------------------------------------- karaoke
class MediaMVKaraokeFamily(Family):
    """Word-synced karaoke typography with the turquoise signal highlight."""
    NAME = "media_mv_karaoke"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def _words(self, rng):
        line = rng.choice(LINE_POOL)
        parts = line.split(" ")
        t = 0.0
        words = []
        for w in parts:
            dur = rng.choice([0.3, 0.4, 0.5, 0.6])
            words.append((round(t, 2), round(t + dur, 2), w))
            t += dur + rng.choice([0.05, 0.1])
        return words

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["word_state", "caption_render"])
        words = self._words(rng)
        header = f"WORDS = {words!r}\n\n\n"
        if kind == "word_state":
            code = (
                header +
                "def active_word(t):\n"
                "    \"\"\"Return (index, progress) of the word sung at time t.\n\n"
                "    Word windows are end-exclusive; in a gap between words returns\n"
                "    (None, 0.0). Progress is the normalized time inside the word.\n"
                "    \"\"\"\n"
                "    for i, (start, end, _text) in enumerate(WORDS):\n"
                "        if start <= t < end:\n"
                "            return i, (t - start) / (end - start)\n"
                "    return None, 0.0\n")
            gap = round(words[0][1] + 0.02, 2)
            mid_t = round((words[1][0] + words[1][1]) / 2, 4)
            tests = (
                "def run_tests():\n"
                f"    assert active_word({words[0][0]!r}) == (0, 0.0)\n"
                f"    assert active_word({words[1][0]!r}) == (1, 0.0)\n"
                f"    assert active_word({words[0][1]!r}) == (None, 0.0)  # gap instant\n"
                f"    assert active_word({gap!r}) == (None, 0.0)\n"
                f"    assert abs(active_word({mid_t!r})[1] - 0.5) < 1e-6\n"
                "    assert active_word(-1.0) == (None, 0.0)\n")
            expected = (f"Word windows are end-exclusive: t={words[0][1]} (word 0's end, "
                        f"in a gap) returns (None, 0.0), and t={words[1][0]} lands "
                        "exactly on word 1 with progress 0.0.")
            explain = _mk_explain(
                "Word-level karaoke sync state for caption typography.",
                "Linear scan over (start, end, text) windows, end-exclusive, with "
                "normalized in-word progress.",
                ["end-exclusive handover: t=end belongs to the NEXT word",
                 "gaps are explicit (None, 0.0) states, not errors",
                 "progress lets the renderer sweep a fill or glow"],
                "O(words) per probe", "O(1)",
                ["t exactly at a word boundary", "t in a gap", "t before the first word"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        if start <= t < end:", "        if start <= t <= end:")}
            bugs = {"boundary_inclusive": bug}
        else:  # caption_render
            slot = 10
            margin = 4
            width = 2 * margin + sum(len(w[2]) + 1 for w in words) * slot
            code = (
                "from PIL import Image\n\n"
                f"SIGNAL_RGB = {SIGNAL_RGB!r}  # Miku turquoise - the AI-ku default signal\n"
                "BONE_RGB = (238, 233, 223)\n"
                "INK_RGB = (10, 10, 11)\n"
                f"SLOT = {slot}  # pixels per character\n"
                f"MARGIN = {margin}\n"
                f"WORDS = {words!r}\n\n\n"
                "def word_x(i):\n"
                "    \"\"\"Left pixel column of word i's first character.\"\"\"\n"
                "    return MARGIN + sum((len(w[2]) + 1) for w in WORDS[:i]) * SLOT\n\n\n"
                "def active_word(t):\n"
                "    for i, (start, end, _text) in enumerate(WORDS):\n"
                "        if start <= t < end:\n"
                "            return i, (t - start) / (end - start)\n"
                "    return None, 0.0\n\n\n"
                "def render_caption(t, width, height):\n"
                "    \"\"\"Karaoke caption: ONLY the active word is signal turquoise.\"\"\"\n"
                "    img = Image.new('RGB', (width, height), INK_RGB)\n"
                "    px = img.load()\n"
                "    idx, _progress = active_word(t)\n"
                "    for i, (start, end, text) in enumerate(WORDS):\n"
                "        color = SIGNAL_RGB if i == idx else BONE_RGB\n"
                "        x0 = word_x(i)\n"
                "        for j in range(len(text)):\n"
                "            for dy in range(6, 10):\n"
                "                for dx in range(SLOT - 2):\n"
                "                    px[x0 + j * SLOT + dx, dy] = color\n"
                "    return img\n")
            w0_mid = round((words[0][0] + words[0][1]) / 2, 4)
            gap_t = round(words[0][1] + 0.02, 2)
            later_col = margin + (len(words[0][2]) + 1) * slot + 1
            tests = (
                "from PIL import Image\n\n\n"
                "def run_tests():\n"
                f"    img = render_caption({w0_mid!r}, {width}, 16)\n"
                "    assert img.tobytes() == render_caption("
                f"{w0_mid!r}, {width}, 16).tobytes()  # determinism\n"
                "    assert img.load()[word_x(0) + 1, 7] == SIGNAL_RGB\n"
                f"    assert img.load()[{later_col}, 7] == BONE_RGB  # later word stays bone\n"
                f"    gap = render_caption({gap_t!r}, {width}, 16)\n"
                "    assert gap.load()[word_x(0) + 1, 7] == BONE_RGB\n")
            expected = ("Only the word sung at time t renders in the Miku turquoise "
                        "signal; every other word (and gap frames) renders in bone.")
            explain = _mk_explain(
                "Word-synced karaoke typography for code-rendered videos.",
                "Per-word fixed slots; the active word index decides the colour; "
                "everything else is bone on ink.",
                ["colour is a pure function of t (render determinism)",
                 "single signal colour: only the active word lights up",
                 "fixed slot layout keeps pixel math exact and testable"],
                "O(total characters) per frame", "O(width*height)",
                ["t in a gap", "t at a boundary", "deterministic double render"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        color = SIGNAL_RGB if i == idx else BONE_RGB",
                    "        color = SIGNAL_RGB if idx is None or i <= idx else BONE_RGB")}
            bugs = {"cumulative_highlight": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement word-synced karaoke typography for a code-rendered music "
                  f"video in Python. {expected} The highlight colour is the Miku "
                  f"turquoise {SIGNAL_RGB!r} ({SIGNAL_HEX}) by default - AI-ku's signal "
                  f"colour, never orange. Rendering must be a pure function of t."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "music_video", kind], variant=kind,
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


# ------------------------------------------------------------------- project
class MediaMVProjectFamily(Family):
    """Multi-file mini music-video engine: palette + timeline + karaoke +
    pure renderer + offline render_all with hash manifest."""
    NAME = "media_mv_project"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        pkg = rng.choice(["mvmotion", "tealframe"])
        fps = 24
        length = rng.choice([48, 64])
        names = rng.sample(SCENE_POOL, 3)
        scenes = [(i * length, (i + 1) * length, names[i]) for i in range(3)]
        total = 3 * length
        line = rng.choice(LINE_POOL)
        parts = line.split(" ")
        t = 0.0
        words = []
        for w in parts:
            dur = rng.choice([0.4, 0.5])
            words.append((round(t, 2), round(t + dur, 2), w))
            t += dur + 0.1
        palette = (
            '"""Palette: AI-ku\'s default signal colour is the Miku turquoise."""\n\n'
            f'SIGNAL = {SIGNAL_HEX!r}  # Miku turquoise - default signal colour (never orange)\n'
            'INK = "#0A0A0B"\n'
            'BONE = "#EEE9DF"\n'
            'ASH = "#9C978F"\n\n\n'
            'def hex_to_rgb(hex_color):\n'
            '    h = hex_color.lstrip("#")\n'
            '    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))\n\n\n'
            'SIGNAL_RGB = hex_to_rgb(SIGNAL)\n'
            'INK_RGB = hex_to_rgb(INK)\n'
            'BONE_RGB = hex_to_rgb(BONE)\n')
        timeline = (
            '"""Deterministic scene schedule and beat grid."""\n\n'
            f'SCENES = {scenes!r}\n'
            f'BPM = {rng.choice([100, 120, 132])}\n'
            f'FPS = {fps}\n\n\n'
            'def active_scene(frame):\n'
            '    """(name, local_progress) for a frame; end-exclusive windows."""\n'
            '    for start, end, name in SCENES:\n'
            '        if start <= frame < end:\n'
            '            return name, (frame - start) / (end - start)\n'
            '    return None, 0.0\n\n\n'
            'def beat_grid(total_frames, bpm=BPM, fps=FPS):\n'
            '    step = 60.0 / bpm * fps\n'
            '    return [round(k * step) for k in range(int(total_frames / step) + 1)]\n')
        karaoke = (
            '"""Word-synced karaoke state."""\n\n'
            f'WORDS = {words!r}\n\n\n'
            'def active_word(t):\n'
            '    """(index, progress) of the word at t, or (None, 0.0) in gaps."""\n'
            '    for i, (start, end, _text) in enumerate(WORDS):\n'
            '        if start <= t < end:\n'
            '            return i, (t - start) / (end - start)\n'
            '    return None, 0.0\n')
        renderer = (
            '"""Pure frame renderer: frame index -> PIL Image (deterministic)."""\n'
            'from PIL import Image\n\n'
            f'from {pkg}.palette import INK_RGB, SIGNAL_RGB\n'
            f'from {pkg}.timeline import active_scene\n'
            f'from {pkg}.karaoke import active_word\n\n'
            f'WIDTH, HEIGHT = 64, 32\n'
            'BAR_Y0, BAR_Y1 = 24, 28\n\n\n'
            'def render(frame, fps=24):\n'
            '    _name, local_t = active_scene(frame)\n'
            '    t = frame / fps\n'
            '    _idx, progress = active_word(t)\n'
            '    img = Image.new("RGB", (WIDTH, HEIGHT), INK_RGB)\n'
            '    px = img.load()\n'
            '    for y in range(HEIGHT):\n'
            '        for x in range(WIDTH):\n'
            '            shade = (x * 3 + y * 5 + int(local_t * 48)) % 40\n'
            '            px[x, y] = (10 + shade, 11 + shade // 2, 12 + shade // 4)\n'
            '    fill = int(WIDTH * progress)\n'
            '    for y in range(BAR_Y0, BAR_Y1):\n'
            '        for x in range(fill):\n'
            '            px[x, y] = SIGNAL_RGB  # Miku turquoise progress bar\n'
            '    return img\n')
        render_all = (
            '"""Offline render loop: every frame in order, with a hash manifest."""\n'
            'import hashlib\n\n'
            f'from {pkg}.renderer import render\n'
            f'from {pkg}.timeline import SCENES\n\n\n'
            'def render_all():\n'
            '    """Return the sha256 hex digest of every rendered frame, in order."""\n'
            '    total = SCENES[-1][1]\n'
            '    return [hashlib.sha256(render(frame).tobytes()).hexdigest()\n'
            '            for frame in range(total)]\n')
        manifest = json.dumps({"fps": fps, "width": 64, "height": 32,
                               "scenes": [n for _, _, n in scenes],
                               "total_frames": total, "signal": SIGNAL_HEX},
                              indent=1) + "\n"
        readme = (
            f"# {pkg}\n\n"
            "Mini generative music-video engine (frames are a pure function of the "
            "frame index, so preview and offline render agree byte-for-byte).\n\n"
            f"- `{pkg}/palette.py`: colours - the default signal colour is the Miku "
            f"turquoise {SIGNAL_HEX} (AI-ku identity). Never orange.\n"
            f"- `{pkg}/timeline.py`: scene schedule + beat grid\n"
            f"- `{pkg}/karaoke.py`: word-level sync\n"
            f"- `{pkg}/renderer.py`: pure `render(frame)`\n"
            f"- `{pkg}/render_all.py`: offline loop + sha256 frame manifest\n"
            f"- `manifest.json`: render configuration (signal included)\n\n"
            "Run tests: `python -m unittest discover -s tests`\n")
        tests = (
            "import json\nimport sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
            f"from {pkg}.palette import SIGNAL, SIGNAL_RGB\n"
            f"from {pkg}.timeline import active_scene, SCENES\n"
            f"from {pkg}.karaoke import active_word, WORDS\n"
            f"from {pkg}.renderer import render, WIDTH, BAR_Y0\n"
            f"from {pkg}.render_all import render_all\n\n\n"
            "class TestEngine(unittest.TestCase):\n"
            "    def test_default_signal_is_miku_turquoise(self):\n"
            f"        self.assertEqual(SIGNAL, {SIGNAL_HEX!r})\n"
            f"        self.assertEqual(SIGNAL_RGB, {SIGNAL_RGB!r})\n\n"
            "    def test_render_determinism(self):\n"
            "        self.assertEqual(render(7).tobytes(), render(7).tobytes())\n\n"
            "    def test_render_all_hash_stable(self):\n"
            "        self.assertEqual(render_all(), render_all())\n\n"
            "    def test_scene_coverage(self):\n"
            "        names = [active_scene(f)[0] for f in range(" 
            f"{total})]\n"
            "        self.assertEqual(set(names), "
            f"set({sorted(set(names))!r}))\n\n"
            "    def test_karaoke_bar_fill(self):\n"
            "        first_end = WORDS[0][1]\n"
            "        frame = int((WORDS[0][0] + first_end) / 2 * 24)\n"
            "        img = render(frame)\n"
            "        self.assertEqual(img.load()[0, BAR_Y0], SIGNAL_RGB)\n"
            "        self.assertNotEqual(img.load()[63, BAR_Y0], SIGNAL_RGB)\n\n"
            "    def test_manifest(self):\n"
            "        m = json.load(open('manifest.json'))\n"
            f"        self.assertEqual(m['total_frames'], {total})\n"
            f"        self.assertEqual(m['signal'], {SIGNAL_HEX!r})\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n")
        files = [FileSpec(f"{pkg}/__init__.py", f'"""{pkg}: mini generative music-video engine."""\n'),
                 FileSpec(f"{pkg}/palette.py", palette),
                 FileSpec(f"{pkg}/timeline.py", timeline),
                 FileSpec(f"{pkg}/karaoke.py", karaoke),
                 FileSpec(f"{pkg}/renderer.py", renderer),
                 FileSpec(f"{pkg}/render_all.py", render_all),
                 FileSpec("manifest.json", manifest),
                 FileSpec("README.md", readme),
                 FileSpec("tests/test_pipeline.py", tests)]
        expected = (f"A deterministic {fps}fps mini music-video engine ({total} frames, "
                    f"scenes {', '.join(names)}): pure render(frame), karaoke progress "
                    f"bar in the default Miku turquoise {SIGNAL_HEX}, and a hash-stable "
                    "offline render_all().")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Assemble the multi-file generative music-video project described by "
                  f"README.md: palette (default signal = Miku turquoise {SIGNAL_HEX}), "
                  f"scene timeline + beat grid, word-synced karaoke, a pure frame "
                  f"renderer and an offline render_all() with a sha256 manifest. "
                  f"{expected} Determinism is proven by byte-identical renders and "
                  f"hash-stable double passes."),
            expected_behavior=expected, files=files, entry=f"{pkg}/__init__.py",
            tests=tests, verify_method="executed", is_project=True,
            notes={"explain": {"purpose": expected,
                               "approach": ("palette + timeline/karaoke state + pure "
                                            "renderer + offline loop with hash manifest."),
                               "key_points": ["frames are pure functions of the frame index",
                                              "the signal colour is ONE constant (#39C5BB)",
                                              "hash manifests make offline renders auditable"],
                               "big_o_time": "O(w*h) per frame", "big_o_space": "O(w*h)",
                               "edge_cases": ["frame outside schedule", "karaoke gap",
                                              "manifest/code drift"]}},
            tags=["media", "music_video", "project"], variant=pkg,
            seed=rng.randrange(2**31))


register(globals(), MediaMVSceneEngineFamily)
register(globals(), MediaMVKaraokeFamily)
register(globals(), MediaMVProjectFamily)
