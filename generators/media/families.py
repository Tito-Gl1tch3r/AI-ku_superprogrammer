"""Dataset-3 families: AI-ku_superprogrammer_media.

Code-rendered media: deterministic frame rendering, timelines, easing,
audio->data->visual pipelines, color pipelines. Verification is REAL:
frames render via Pillow (verified sandbox dependency) and are compared
byte-for-byte; numeric pipelines are asserted; TS runs on Node.
"""
from __future__ import annotations

import json
import random

from ..core import Candidate, Family, FileSpec, register


class MediaTimelineFamily(Family):
    NAME = "media_timeline_easing"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["easing", "keyframes", "timeline_sample"])
        if kind == "easing":
            code = (
                "import math\n\n\n"
                "def ease_linear(t):\n"
                "    \"\"\"Identity easing on t in [0, 1].\"\"\"\n"
                "    return t\n\n\n"
                "def ease_in_quad(t):\n"
                "    return t * t\n\n\n"
                "def ease_out_quad(t):\n"
                "    return 1.0 - (1.0 - t) * (1.0 - t)\n\n\n"
                "def ease_in_out_sine(t):\n"
                "    return 0.5 - 0.5 * math.cos(math.pi * t)\n")
            tests = (
                "def run_tests():\n"
                "    assert abs(ease_linear(0.5) - 0.5) < 1e-9\n"
                "    assert abs(ease_in_quad(0.5) - 0.25) < 1e-9\n"
                "    assert abs(ease_out_quad(0.5) - 0.75) < 1e-9\n"
                "    assert abs(ease_in_out_sine(0.0)) < 1e-9\n"
                "    assert abs(ease_in_out_sine(1.0) - 1.0) < 1e-9\n"
                "    assert abs(ease_in_out_sine(0.5) - 0.5) < 1e-9\n")
            expected = ("Easing curves map [0,1] -> [0,1]; out mirrors in; the sine "
                        "variant is symmetric around t=0.5.")
            explain = {"purpose": "Animation easing functions as pure time-warping maps.",
                       "approach": "Each curve maps normalized time to normalized progress deterministically.",
                       "key_points": ["same t -> same value (render determinism)",
                                      "ease-out mirrors ease-in",
                                      "easing is the vocabulary of motion polish"],
                       "big_o_time": "O(1)", "big_o_space": "O(1)",
                       "edge_cases": ["t=0", "t=1", "midpoint symmetry"]}
            bugs = {}
        elif kind == "keyframes":
            k0 = round(rng.uniform(0.5, 2.0), 3)
            k1 = round(k0 + rng.uniform(1.0, 3.0), 3)
            v0, v1, v2 = (round(rng.uniform(-10, 10), 3) for _ in range(3))
            keys = [(0.0, v0), (k0, v1), (k1, v2)]
            fn = rng.choice(["sample_channel", "value_at", "interpolate_keys"])
            code = (
                f"KEYS = {keys!r}\n\n\n"
                f"def {fn}(keys, t):\n"
                f"    \"\"\"Linear keyframe interpolation; clamps outside the key range.\"\"\"\n"
                f"    if t <= keys[0][0]:\n"
                f"        return keys[0][1]\n"
                f"    if t >= keys[-1][0]:\n"
                f"        return keys[-1][1]\n"
                f"    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):\n"
                f"        if t0 <= t <= t1:\n"
                f"            alpha = (t - t0) / (t1 - t0)\n"
                f"            return v0 + (v1 - v0) * alpha\n"
                f"    raise AssertionError('unreachable')\n")
            probe_t = round((k0 + k1) / 2, 4)
            exp_mid = round(v1 + (v2 - v1) * (probe_t - k0) / (k1 - k0), 6)
            tests = (
                f"def run_tests():\n"
                f"    keys = {keys!r}\n"
                f"    assert {fn}(keys, -1.0) == {v0!r}\n"
                f"    assert {fn}(keys, 999.0) == {v2!r}\n"
                f"    assert abs({fn}(keys, {probe_t}) - {exp_mid!r}) < 1e-6\n"
                f"    assert abs({fn}(keys, {k0!r}) - {v1!r}) < 1e-9\n")
            expected = (f"Clamped linear interpolation across 3 keys; at t={probe_t} the "
                        f"value is {exp_mid}.")
            explain = {"purpose": "Deterministic keyframe channels for timelines.",
                       "approach": "Locate the bracketing key pair; lerp with normalized alpha; clamp at the ends.",
                       "key_points": ["clamp-first avoids extrapolation surprises",
                                      "alpha renormalizes local time between keys",
                                      "sorted keys are the contract"],
                       "big_o_time": "O(n) scan (O(log n) possible)", "big_o_space": "O(1)",
                       "edge_cases": ["t before first key", "t after last key", "exact key hit"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "alpha = (t - t0) / (t1 - t0)", "alpha = (t1 - t0) / (t - t0)")}
            bugs = {"alpha_inverted": bug}
        else:  # timeline_sample
            fps = rng.choice([24, 30, 60])
            dur = rng.choice([2.0, 2.5, 4.0])
            total = int(fps * dur)
            bpm = rng.choice([90, 120, 140])
            step = 60.0 / bpm * fps
            beats = [round(k * step) for k in range(int(total / step) + 1)]
            code = (
                f"FPS = {fps}\n"
                f"BPM = {bpm}\n\n\n"
                f"def frame_times(total_frames, fps=FPS):\n"
                f"    \"\"\"Deterministic frame -> seconds mapping.\"\"\"\n"
                f"    return [i / fps for i in range(total_frames)]\n\n\n"
                f"def beat_grid(bpm, total_frames, fps=FPS):\n"
                f"    \"\"\"Frame indices closest to each musical beat.\"\"\"\n"
                f"    step = 60.0 / bpm * fps\n"
                f"    return [round(k * step) for k in range(int(total_frames / step) + 1)]\n")
            tests = (
                f"def run_tests():\n"
                f"    times = frame_times({total})\n"
                f"    assert len(times) == {total}\n"
                f"    assert abs(times[{total - 1}] - {total - 1} / {fps}) < 1e-9\n"
                f"    assert beat_grid(BPM, {total}) == {beats!r}\n"
                f"    assert frame_times({total}) == frame_times({total})  # determinism\n")
            expected = (f"{total} frames at {fps} fps; beats (BPM {bpm}) land on frames "
                        f"{beats[:4]}...")
            explain = {"purpose": "Deterministic frame timing and beat synchronization.",
                       "approach": "frame->seconds is i/fps; beat step is 60/bpm*fps rounded to frames.",
                       "key_points": ["integer frame indices keep rendering deterministic",
                                      "beat grid derives from BPM without float drift",
                                      "same call -> same timeline"],
                       "big_o_time": "O(frames)", "big_o_space": "O(frames)",
                       "edge_cases": ["beat beyond last frame", "fps rounding", "empty range"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    step = 60.0 / bpm * fps", "    step = bpm / 60.0 * fps")}
            bugs = {"bpm_inverted": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement a deterministic media-timeline utility in Python. {expected} "
                  f"Rendering pipelines call these per frame, so they must be pure and "
                  f"reproducible."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", kind], variant=kind, seed=rng.randrange(2**31))
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


class MediaFramesFamily(Family):
    """Renders REAL Pillow frames and verifies determinism + behaviour."""
    NAME = "media_frame_renderer"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "testing", "code_review")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["gradient", "bouncer", "compositor"])
        w, h = rng.choice([(16, 9), (24, 18), (32, 18)])
        fn = rng.choice(["render_frame", "draw_frame"])
        if kind == "gradient":
            code = (
                "from PIL import Image\n\n\n"
                f"def {fn}(width, height, t):\n"
                "    \"\"\"Deterministic two-axis gradient at time t in [0, 1].\"\"\"\n"
                "    img = Image.new('RGB', (width, height))\n"
                "    px = img.load()\n"
                "    for y in range(height):\n"
                "        for x in range(width):\n"
                "            u = (x + t * width) / max(1, width - 1)\n"
                "            v = y / max(1, height - 1)\n"
                "            px[x, y] = (int(255 * u) % 256, int(255 * v),\n"
                "                        int(255 * (u * v)))\n"
                "    return img\n")
            tests = (
                "def run_tests():\n"
                f"    a = {fn}({w}, {h}, 0.0)\n"
                f"    b = {fn}({w}, {h}, 0.0)\n"
                "    assert a.tobytes() == b.tobytes()  # deterministic\n"
                f"    c = {fn}({w}, {h}, 1.0)\n"
                "    assert a.tobytes() != c.tobytes()  # time moves the gradient\n"
                f"    assert a.size == ({w}, {h})\n"
                "    assert a.load()[0, 0][1] == 0  # v=0 on the top row\n")
            expected = (f"Byte-identical frames for identical arguments; the gradient "
                        f"advances with t ({w}x{h} RGB).")
            explain = {"purpose": "Procedural frame rendering with pixel-level control.",
                       "approach": "Pure function of (width, height, t): per-pixel normalized coordinates drive color.",
                       "key_points": ["no hidden state, no clock -> reproducible renders",
                                      "normalized coordinates survive resolution changes",
                                      "Pillow Image is the render target"],
                       "big_o_time": "O(w*h) per frame", "big_o_space": "O(w*h)",
                       "edge_cases": ["t=0 vs t=1", "1-pixel dimensions", "byte equality"]}
            def bug(files):
                return {"solution.py": ("import random\n\n\n" + files["solution.py"]).replace(
                    "            px[x, y] = (int(255 * u) % 256, int(255 * v),\n"
                    "                        int(255 * (u * v)))",
                    "            j = random.randint(-10, 10)\n"
                    "            px[x, y] = (int(255 * u) % 256 + j, int(255 * v),\n"
                    "                        int(255 * (u * v)))")}
            bugs = {"nondeterministic_jitter": bug}
        elif kind == "bouncer":
            speed = rng.choice([0.5, 0.75])
            radius = max(2, min(w, h) // 6)
            code = (
                "from PIL import Image, ImageDraw\n\n"
                "BG = (12, 16, 24)\n"
                "FG = (240, 96, 64)\n\n\n"
                f"def {fn}(width, height, frame, total_frames):\n"
                "    \"\"\"Ball bouncing horizontally; deterministic per frame index.\"\"\"\n"
                "    t = frame / max(1, total_frames - 1)\n"
                f"    cycle = abs((t * {speed} * 2.0) % 2.0 - 1.0)\n"
                f"    x = int(cycle * (width - 2 * {radius})) + {radius}\n"
                "    y = height // 2\n"
                "    img = Image.new('RGB', (width, height), BG)\n"
                f"    ImageDraw.Draw(img).ellipse([x - {radius}, y - {radius},\n"
                f"                                 x + {radius}, y + {radius}], fill=FG)\n"
                "    return img\n")
            tests = (
                "def run_tests():\n"
                f"    f0 = {fn}({w}, {h}, 0, 10)\n"
                f"    assert f0.tobytes() == {fn}({w}, {h}, 0, 10).tobytes()\n"
                f"    assert {fn}({w}, {h}, 0, 10).tobytes() != {fn}({w}, {h}, 5, 10).tobytes()\n"
                f"    assert {fn}({w}, {h}, 5, 10).size == ({w}, {h})\n")
            expected = (f"Deterministic bouncing ball ({speed} cycles): identical frame "
                        f"index -> identical bytes; different frames differ.")
            explain = {"purpose": "Frame-accurate procedural animation.",
                       "approach": "Map frame index to a ping-pong cycle; draw into a fresh image per call.",
                       "key_points": ["stateless render: everything derives from (frame, total)",
                                      "ping-pong via abs(x % 2 - 1)",
                                      "fresh render target avoids ghosting"],
                       "big_o_time": "O(w*h)", "big_o_space": "O(w*h)",
                       "edge_cases": ["first/last frame", "cycle wrap", "determinism"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    t = frame / max(1, total_frames - 1)",
                    "    t = total_frames / max(1, frame + 1)")}
            bugs = {"time_mapping_inverted": bug}
        else:  # compositor
            alpha = rng.choice([0.3, 0.5, 0.7])
            code = (
                "from PIL import Image\n\n\n"
                f"def {fn}(base, overlay, alpha={alpha}):\n"
                "    \"\"\"Source-over composite of two equal-size RGB images.\"\"\"\n"
                "    out = base.copy()\n"
                "    bp, op, outp = base.load(), overlay.load(), out.load()\n"
                "    for y in range(base.height):\n"
                "        for x in range(base.width):\n"
                "            b, o = bp[x, y], op[x, y]\n"
                "            outp[x, y] = tuple(\n"
                "                int(o[c] * alpha + b[c] * (1 - alpha)) for c in range(3))\n"
                "    return out\n")
            tests = (
                "def run_tests():\n"
                "    from PIL import Image\n"
                "    base = Image.new('RGB', (4, 4), (0, 0, 0))\n"
                "    over = Image.new('RGB', (4, 4), (200, 100, 50))\n"
                f"    out = {fn}(base, over)\n"
                f"    assert out.load()[0, 0] == (int(200 * {alpha}), int(100 * {alpha}), int(50 * {alpha}))\n"
                f"    assert out.tobytes() == {fn}(base, over).tobytes()\n")
            expected = (f"Source-over at alpha={alpha}: overlay dominates; result is "
                        f"byte-stable across runs.")
            explain = {"purpose": "Alpha compositing: the basis of transitions and overlays.",
                       "approach": "Per-channel linear mix overlay*alpha + base*(1-alpha).",
                       "key_points": ["alpha=1 -> overlay, alpha=0 -> base",
                                      "int conversion clamps to gamut",
                                      "pure function -> reproducible frames"],
                       "big_o_time": "O(w*h)", "big_o_space": "O(w*h)",
                       "edge_cases": ["alpha extremes", "identical images", "determinism"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "int(o[c] * alpha + b[c] * (1 - alpha)) for c in range(3))",
                    "int(b[c] * alpha + o[c] * (1 - alpha)) for c in range(3))")}
            bugs = {"alpha_order_swapped": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement a deterministic procedural frame renderer in Python (Pillow is "
                  f"available). {expected} The renderer must be a pure function of its inputs: "
                  f"identical arguments produce byte-identical frames - this is what makes "
                  f"offline rendering reproducible."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "render", kind], variant=kind, seed=rng.randrange(2**31))
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


class MediaAudioPipelineFamily(Family):
    NAME = "media_audio_analysis"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        import math
        kind = rng.choice(["envelope", "onsets", "bpm_grid"])
        if kind == "envelope":
            n = rng.randint(30, 60)
            samples = [round(rng.uniform(-1, 1), 4) for _ in range(n)]
            win = rng.choice([3, 4, 5])
            code = (
                "def envelope_abs(samples):\n"
                "    \"\"\"Rectified amplitude envelope.\"\"\"\n"
                "    return [abs(s) for s in samples]\n\n\n"
                "def envelope_smoothed(samples, win):\n"
                "    \"\"\"Moving-average smoothed envelope (running sum, O(n)).\"\"\"\n"
                "    if win <= 0:\n"
                "        raise ValueError('win must be positive')\n"
                "    out, acc = [], 0.0\n"
                "    for i, s in enumerate(samples):\n"
                "        acc += abs(s)\n"
                "        if i >= win:\n"
                "            acc -= abs(samples[i - win])\n"
                "        out.append(acc / min(i + 1, win))\n"
                "    return out\n")
            tests = (
                f"def run_tests():\n"
                f"    data = {samples[:16]!r}\n"
                f"    env = envelope_smoothed(data, {win})\n"
                f"    assert len(env) == len(data)\n"
                f"    assert env[0] == abs(data[0])\n"
                f"    assert all(v >= 0.0 for v in env)\n"
                f"    assert envelope_smoothed([], {win}) == []\n"
                f"    try:\n"
                f"        envelope_smoothed(data, 0)\n"
                f"        assert False\n"
                f"    except ValueError:\n"
                f"        pass\n")
            expected = ("Rectified + moving-average envelope; O(n) via running sum; "
                        "win<=0 raises.")
            explain = {"purpose": "Amplitude envelope extraction for audio-reactive animation.",
                       "approach": "Rectify, then smooth with a sliding window using a running sum.",
                       "key_points": ["the envelope drives visual intensity",
                                      "running sum keeps it O(n)",
                                      "window length trades responsiveness vs smoothness"],
                       "big_o_time": "O(n)", "big_o_space": "O(n)",
                       "edge_cases": ["empty input", "win > len", "win <= 0 raises"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "            acc -= abs(samples[i - win])",
                    "            acc -= abs(samples[i - win]) * 0.5")}
            bugs = {"leaky_running_sum": bug}
        elif kind == "onsets":
            n = rng.randint(30, 60)
            peak = rng.randrange(6, n - 6)
            samples = [0.05] * n
            for k in range(peak, min(n, peak + 6)):
                samples[k] = 0.9
            code = (
                "THRESHOLD = 0.5\n\n\n"
                "def detect_onsets(samples, threshold=THRESHOLD):\n"
                "    \"\"\"Indices where energy rises above threshold (edge-triggered).\"\"\"\n"
                "    onsets = []\n"
                "    above = False\n"
                "    for i, s in enumerate(samples):\n"
                "        if s >= threshold and not above:\n"
                "            onsets.append(i)\n"
                "            above = True\n"
                "        elif s < threshold:\n"
                "            above = False\n"
                "    return onsets\n")
            tests = (
                f"def run_tests():\n"
                f"    data = {samples!r}\n"
                f"    assert detect_onsets(data) == {[peak]!r}\n"
                f"    assert detect_onsets([]) == []\n"
                f"    assert detect_onsets([0.9, 0.9, 0.1, 0.9]) == [0, 3]\n")
            expected = (f"Edge-triggered detection: the burst at index {peak} yields "
                        f"exactly one onset.")
            explain = {"purpose": "Onset detection for beat-synced visual hits.",
                       "approach": "Edge-triggered threshold crossing: one event per burst.",
                       "key_points": ["edge-triggering debounces sustained energy",
                                      "threshold trades sensitivity vs noise",
                                      "onsets become timeline events"],
                       "big_o_time": "O(n)", "big_o_space": "O(1)",
                       "edge_cases": ["no onsets", "sustained burst", "empty input"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        if s >= threshold and not above:",
                    "        if s >= threshold:")}
            bugs = {"missing_edge_trigger": bug}
        else:  # bpm_grid
            bpm = rng.choice([100, 120, 150])
            fps = rng.choice([24, 30, 60])
            total = rng.choice([90, 120, 180])
            step = 60.0 / bpm * fps
            beats = [round(k * step) for k in range(int(total / step) + 1)]
            code = (
                "def beat_frames(bpm, total_frames, fps):\n"
                "    \"\"\"Frame indices for every beat (BPM -> frames conversion).\"\"\"\n"
                "    if bpm <= 0 or fps <= 0:\n"
                "        raise ValueError('bpm and fps must be positive')\n"
                "    step = 60.0 / bpm * fps\n"
                "    return [round(k * step) for k in range(int(total_frames / step) + 1)]\n\n\n"
                "def bar_frames(bpm, total_frames, fps, beats_per_bar=4):\n"
                "    \"\"\"Downbeat (bar-start) frames only.\"\"\"\n"
                "    return beat_frames(bpm, total_frames, fps)[::beats_per_bar]\n")
            tests = (
                f"def run_tests():\n"
                f"    assert beat_frames({bpm}, {total}, {fps}) == {beats!r}\n"
                f"    assert beat_frames({bpm}, {total}, {fps}) == beat_frames({bpm}, {total}, {fps})\n"
                f"    assert bar_frames({bpm}, {total}, {fps}) == {beats[::4]!r}\n"
                f"    try:\n"
                f"        beat_frames(0, 10, 30)\n"
                f"        assert False\n"
                f"    except ValueError:\n"
                f"        pass\n")
            expected = (f"BPM {bpm} at {fps} fps -> step {step:.4f} frames; {len(beats)} "
                        f"beats, bars every 4th beat.")
            explain = {"purpose": "Convert musical time (BPM) into frame indices.",
                       "approach": "60/bpm seconds per beat * fps -> frame step, rounded to the frame grid.",
                       "key_points": ["one conversion point keeps A/V in sync",
                                      "rounding to frames makes it renderable",
                                      "bars give stronger accents"],
                       "big_o_time": "O(beats)", "big_o_space": "O(beats)",
                       "edge_cases": ["bpm/fps <= 0", "beat beyond last frame", "deterministic grid"]}
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    return [round(k * step) for k in range(int(total_frames / step) + 1)]",
                    "    return [round(k * step + 0.5) for k in range(int(total_frames / step) + 1)]")}
            bugs = {"beat_grid_biased": bug}
        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Build the audio-analysis step of an audio->data->visual pipeline in "
                  f"Python. {expected} The output feeds the animation timeline, so it must "
                  f"be deterministic and unit-tested."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "audio", kind], variant=kind, seed=rng.randrange(2**31))
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


class MediaTsLogicFamily(Family):
    NAME = "media_ts_logic"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["timeline_ts", "color_ts"])
        if kind == "timeline_ts":
            fps = rng.choice([24, 30, 60])
            code = (
                "interface Keyframe {\n"
                "  time: number;\n"
                "  value: number;\n"
                "}\n\n"
                "export interface SampleOptions {\n"
                "  fps: number;\n"
                "  clamp?: boolean;\n"
                "}\n\n"
                "export function sampleChannel(keys: Keyframe[], time: number,\n"
                "                              opts: SampleOptions): number {\n"
                "  const clamp: boolean = opts.clamp ?? true;\n"
                "  if (keys.length === 0) return 0;\n"
                "  if (clamp && time <= keys[0].time) return keys[0].value;\n"
                "  if (clamp && time >= keys[keys.length - 1].time) {\n"
                "    return keys[keys.length - 1].value;\n"
                "  }\n"
                "  for (let i = 0; i < keys.length - 1; i++) {\n"
                "    const a: Keyframe = keys[i];\n"
                "    const b: Keyframe = keys[i + 1];\n"
                "    if (time >= a.time && time <= b.time) {\n"
                "      const alpha: number = (time - a.time) / (b.time - a.time);\n"
                "      return a.value + (b.value - a.value) * alpha;\n"
                "    }\n"
                "  }\n"
                "  return keys[keys.length - 1].value;\n"
                "}\n\n"
                "export function frameTime(frame: number, fps: number): number {\n"
                "  return frame / fps;\n"
                "}\n")
            tests = (
                "/** @param {typeof import('./solution.ts')} solution */\n"
                "function runTests(solution) {\n"
                "  const keys = [{ time: 0, value: 10 }, { time: 1, value: 20 },"
                " { time: 2, value: 0 }];\n"
                f"  const o = {{ fps: {fps} }};\n"
                "  assert.strictEqual(solution.sampleChannel(keys, -1, o), 10);\n"
                "  assert.strictEqual(solution.sampleChannel(keys, 99, o), 0);\n"
                "  assert.strictEqual(solution.sampleChannel(keys, 0.5, o), 15);\n"
                f"  assert.strictEqual(solution.frameTime({fps}, {fps}), 1);\n"
                "}\n")
            expected = "Typed keyframe channel with clamping; frame->time is frame/fps."
            explain = {"purpose": "Type-safe timeline sampling for code-rendered video.",
                       "approach": "Interface-documented keyframes; lerp between brackets; optional clamping.",
                       "key_points": ["interfaces document the data contract",
                                      "clamp option controls extrapolation",
                                      "frame/time conversions centralized"],
                       "big_o_time": "O(n) scan", "big_o_space": "O(1)",
                       "edge_cases": ["empty keys", "time outside range", "mid-segment alpha"]}
            def bug(files):
                return {"solution.ts": files["solution.ts"].replace(
                    "      return a.value + (b.value - a.value) * alpha;",
                    "      return b.value + (a.value - b.value) * alpha;")}
            bugs = {"lerp_direction_flipped": bug}
        else:  # color_ts
            code = (
                "export type RGB = readonly [number, number, number];\n\n"
                "export function luma(c: RGB): number {\n"
                "  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];\n"
                "}\n\n"
                "export function mix(a: RGB, b: RGB, t: number): RGB {\n"
                "  const clamped = Math.min(1, Math.max(0, t));\n"
                "  return [\n"
                "    Math.round(a[0] + (b[0] - a[0]) * clamped),\n"
                "    Math.round(a[1] + (b[1] - a[1]) * clamped),\n"
                "    Math.round(a[2] + (b[2] - a[2]) * clamped),\n"
                "  ] as RGB;\n"
                "}\n\n"
                "export function fade(c: RGB, t: number): RGB {\n"
                "  return mix(c, [0, 0, 0], t);\n"
                "}\n")
            tests = (
                "/** @param {typeof import('./solution.ts')} solution */\n"
                "function runTests(solution) {\n"
                "  assert.strictEqual(solution.luma([0, 0, 0]), 0);\n"
                "  assert.ok(Math.abs(solution.luma([255, 255, 255]) - 255) < 1e-6);\n"
                "  assert.deepStrictEqual(solution.mix([0, 0, 0], [200, 100, 50], 0.5),"
                " [100, 50, 25]);\n"
                "  assert.deepStrictEqual(solution.fade([100, 200, 50], 1.0), [0, 0, 0]);\n"
                "  assert.deepStrictEqual(solution.mix([10, 10, 10], [20, 20, 20], 5.0),"
                " [20, 20, 20]);\n"
                "}\n")
            expected = "Rec.709 luma, clamped RGB mixing, fade-to-black helper."
            explain = {"purpose": "Color math for compositing and post-processing.",
                       "approach": "Rec.709 weights for perceptual luma; clamped per-channel mix.",
                       "key_points": ["luma weights encode perception",
                                      "t clamping keeps results in gamut",
                                      "fade is mix toward black"],
                       "big_o_time": "O(1)", "big_o_space": "O(1)",
                       "edge_cases": ["t out of range", "extreme channels", "rounding"]}
            def bug(files):
                return {"solution.ts": files["solution.ts"].replace(
                    "  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];",
                    "  return (c[0] + c[1] + c[2]) / 3;")}
            bugs = {"luma_weights_averaged": bug}
        cand = Candidate(
            family=self.NAME, language="typescript", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Implement typed media-logic helpers in erasable TypeScript (Node 24 "
                  f"runs this natively). {expected} These utilities belong to the "
                  f"timeline/color layer of a code-rendered video pipeline."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "typescript", kind], variant=kind, seed=rng.randrange(2**31))
        return cand

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kind = rng.choice(sorted(bugs))
        buggy = bugs[kind]({"solution.ts": cand.code})
        if buggy["solution.ts"] == cand.code:
            return None
        return (Candidate(family=self.NAME, language="typescript", domain=cand.domain,
                          difficulty=cand.difficulty, task=cand.task,
                          expected_behavior=cand.expected_behavior,
                          code=buggy["solution.ts"], tests=cand.tests,
                          verify_method="executed",
                          notes={"bug_kind": kind, "correct_code": cand.code},
                          tags=cand.tags, variant=cand.variant + f"|bug|{kind}",
                          seed=cand.seed),
                {"kind": kind, "problem": cand.variant, "correct_code": cand.code,
                 "tests": cand.tests, "unit_notes": cand.notes.get("explain", {})})


class MediaShaderFamily(Family):
    """GLSL examples: static structural verification (no GL context here)."""
    NAME = "media_glsl_shaders"
    LANGUAGE = "glsl"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation",)

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["grayscale", "posterize", "vignette", "chroma_shift"])
        if kind == "grayscale":
            body = ("float luma = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));\n"
                    "    fragColor = vec4(vec3(luma), color.a);")
        elif kind == "posterize":
            levels = rng.choice([4, 5, 8])
            body = (f"vec3 quantized = floor(color.rgb * {levels}.0) / {levels}.0;\n"
                    f"    fragColor = vec4(quantized, color.a);")
        elif kind == "vignette":
            strength = rng.choice([0.4, 0.6, 0.8])
            body = (f"vec2 uv = gl_FragCoord.xy / uResolution.xy;\n"
                    f"    float d = distance(uv, vec2(0.5));\n"
                    f"    float vig = smoothstep(0.8, 0.2, d * {strength});\n"
                    f"    fragColor = vec4(color.rgb * vig, color.a);")
        else:
            offset = rng.choice([0.002, 0.004, 0.008])
            body = (f"float r = texture(uTexture, vUv + vec2({offset}, 0.0)).r;\n"
                    f"    float b = texture(uTexture, vUv - vec2({offset}, 0.0)).b;\n"
                    f"    vec4 center = texture(uTexture, vUv);\n"
                    f"    fragColor = vec4(r, center.g, b, center.a);")
        code = (
            f"#version 300 es\n"
            f"precision highp float;\n\n"
            f"in vec2 vUv;\n"
            f"out vec4 fragColor;\n\n"
            f"uniform sampler2D uTexture;\n"
            f"uniform vec4 uResolution;\n\n"
            f"void main() {{\n"
            f"    vec4 color = texture(uTexture, vUv);\n"
            f"    {body}\n"
            f"}}\n")
        expected = (f"GLSL ES 3.0 fragment shader implementing the '{kind}' post-process "
                    f"over a sampled texture.")
        return Candidate(
            family=self.NAME, language="glsl", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write the fragment shader for a code-rendered video pipeline's "
                  f"post-processing pass. {expected} Inputs: vUv (texture coordinate), "
                  f"uTexture (source), uResolution. Output: fragColor. GLSL ES 3.0."),
            expected_behavior=expected, code=code, verify_method="static_check",
            notes={"explain": {"purpose": expected,
                               "approach": "Sample the source texture, transform per-pixel, write fragColor.",
                               "key_points": ["fragColor is the render target output",
                                              "uv space is normalized [0,1]",
                                              "post-passes chain via render-to-texture"],
                               "big_o_time": "O(pixels) on GPU", "big_o_space": "O(1) per pixel",
                               "edge_cases": ["uv borders", "highp precision requirement"]}},
            tags=["media", "glsl", kind], variant=kind, seed=rng.randrange(2**31))


class MediaProjectFamily(Family):
    NAME = "media_project_multifile"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        pkgname = rng.choice(["miniav", "framekit", "vidlab"])
        fps = rng.choice([24, 30])
        w, h = 12, 8
        scenes = rng.sample(["intro", "wave", "flash", "outro"], rng.randint(2, 3))
        total = 8 * len(scenes)
        timeline = (
            '"""Deterministic scene schedule: (start, end, name) with end exclusive."""\n\n'
            f'SCENES = {[(i * 8, (i + 1) * 8, s) for i, s in enumerate(scenes)]!r}\n\n\n'
            'def active_scene(frame):\n'
            '    """Return (scene_name, local_progress) for a frame index."""\n'
            '    for start, end, name in SCENES:\n'
            '        if start <= frame < end:\n'
            '            return name, (frame - start) / (end - start)\n'
            '    return None, 0.0\n')
        renderer = (
            '"""Pure frame renderer: frame index -> PIL Image."""\n'
            'from PIL import Image\n\n'
            f'from {pkgname}.timeline import active_scene\n\n'
            f'WIDTH, HEIGHT = {w}, {h}\n\n\n'
            'def render(frame):\n'
            '    name, local_t = active_scene(frame)\n'
            '    img = Image.new("RGB", (WIDTH, HEIGHT), (8, 10, 14))\n'
            '    px = img.load()\n'
            '    for y in range(HEIGHT):\n'
            '        for x in range(WIDTH):\n'
            '            base = (x * 7 + y * 13 + int(local_t * 255)) % 256\n'
            '            px[x, y] = (base, base // 2, 96 + base // 4)\n'
            '    return img\n')
        manifest = json.dumps({"fps": fps, "width": w, "height": h,
                               "scenes": scenes, "seed": 7,
                               "total_frames": total}, indent=1) + "\n"
        readme = (f"# {pkgname}\n\nCode-rendered video skeleton (see concepts: "
                  f"deterministic rendering, timeline, scene system).\n\n"
                  f"- `{pkgname}/timeline.py`: scene schedule\n"
                  f"- `{pkgname}/renderer.py`: pure frame renderer\n"
                  f"- `manifest.json`: render configuration\n"
                  f"- `tests/`: unittest suite (determinism + scene coverage)\n\n"
                  f"Run tests: `python -m unittest discover -s tests`\n")
        tests = (
            "import sys\nimport unittest\n\nsys.path.insert(0, '..')\n\n"
            f"from {pkgname}.timeline import active_scene\n"
            f"from {pkgname}.renderer import render\n\n\n"
            "class TestPipeline(unittest.TestCase):\n"
            "    def test_determinism(self):\n"
            "        self.assertEqual(render(3).tobytes(), render(3).tobytes())\n\n"
            "    def test_frames_differ(self):\n"
            f"        self.assertNotEqual(render(0).tobytes(), render({total - 1}).tobytes())\n\n"
            "    def test_scene_coverage(self):\n"
            f"        names = [active_scene(f)[0] for f in range({total})]\n"
            f"        self.assertTrue(all(n in {scenes!r} for n in names))\n\n"
            "    def test_manifest(self):\n"
            "        import json\n"
            "        m = json.load(open('manifest.json'))\n"
            f"        self.assertEqual(m['fps'], {fps})\n"
            f"        self.assertEqual(m['total_frames'], {total})\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n")
        files = [FileSpec(f"{pkgname}/__init__.py", f'"""{pkgname}: code-rendered video skeleton."""\n'),
                 FileSpec(f"{pkgname}/timeline.py", timeline),
                 FileSpec(f"{pkgname}/renderer.py", renderer),
                 FileSpec("manifest.json", manifest),
                 FileSpec("README.md", readme),
                 FileSpec("tests/test_pipeline.py", tests)]
        expected = (f"render(frame) is deterministic and delegates every frame to the "
                    f"scheduled scene ({', '.join(scenes)} @ {fps}fps, {total} frames).")
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Assemble the multi-file code-rendered video project described by "
                  f"README.md: a deterministic scene timeline, a pure frame renderer "
                  f"({w}x{h} @ {fps}fps, {total} frames configured via manifest.json), and a "
                  f"unittest suite proving render determinism plus scene coverage. "
                  f"{expected}"),
            expected_behavior=expected, files=files, entry=f"{pkgname}/__init__.py",
            tests=tests, verify_method="executed", is_project=True,
            notes={"explain": {"purpose": expected,
                               "approach": "Timeline/scheduler + pure renderer + manifest config + tests.",
                               "key_points": ["determinism is testable via tobytes equality",
                                              "manifest decouples config from code",
                                              "scenes partition the timeline"],
                               "big_o_time": "O(w*h) per frame", "big_o_space": "O(w*h)",
                               "edge_cases": ["frame outside schedule", "manifest/code drift"]}},
            tags=["media", "project"], variant="miniav", seed=rng.randrange(2**31))


register(globals(), MediaTimelineFamily)
register(globals(), MediaFramesFamily)
register(globals(), MediaAudioPipelineFamily)
register(globals(), MediaTsLogicFamily)
register(globals(), MediaShaderFamily)
register(globals(), MediaProjectFamily)


def _extra_hooks(cls):
    return cls


# review_variant hook for MediaFramesFamily (attached post-hoc for clarity)
def _media_frames_review_variant(self, rng: random.Random):
    alpha = rng.choice([0.4, 0.6])
    code = (
        "from PIL import Image\n\n\n"
        "def composite(base, overlay, alpha=0.6):\n"
        "    out = base.copy()\n"
        "    bp, op, outp = base.load(), overlay.load(), out.load()\n"
        "    for y in range(base.height):\n"
        "        for x in range(base.width):\n"
        "            b, o = bp[x, y], op[x, y]\n"
        "            outp[x, y] = tuple(\n"
        "                int(o[c] * alpha + b[c] * (1 - alpha)) for c in range(3))\n"
        "    return out\n")
    cand = Candidate(
        family=self.NAME, language="python", domain=self.DOMAIN,
        difficulty="intermediate",
        task=("Review this compositing helper used by the render pipeline (it runs and "
              "produces correct output at the configured alpha). List the issues a senior "
              "graphics engineer would raise, separating correctness risks from "
              "performance/style."),
        expected_behavior="Output is correct for equal-size RGB inputs; issues are robustness and performance.",
        code=code,
        tests=("from PIL import Image\n"
               "def run_tests():\n"
               "    base = Image.new('RGB', (4, 4), (0, 0, 0))\n"
               "    over = Image.new('RGB', (4, 4), (200, 100, 50))\n"
               "    out = composite(base, over, alpha=0.6)\n"
               "    assert out.size == (4, 4)\n"
               "    assert out.load()[0, 0] == (int(200 * 0.6), int(100 * 0.6), int(50 * 0.6))\n"),
        verify_method="executed",
        notes={"issues": [
            {"kind": "no input validation (size/mode mismatch)",
             "severity": "high",
             "why": "base and overlay with different sizes or modes (RGBA vs RGB) raise deep inside the loop or silently blend wrong channels.",
             "better": "assert base.size == overlay.size and both RGB; convert modes explicitly."},
            {"kind": "per-pixel Python loop",
             "severity": "medium",
             "why": "pure-Python blending is ~100x slower than Image.blend / numpy vectorization at 1080p.",
             "better": "use Image.blend(base, overlay, alpha) or a numpy fused expression."},
            {"kind": "alpha not validated",
             "severity": "low",
             "why": "alpha outside [0, 1] silently clips or overflows int conversion.",
             "better": "clamp/validate alpha at the boundary."},
            {"kind": "int() truncation instead of rounding",
             "severity": "low",
             "why": "int() floors toward zero, so blended values are biased one LSB dark; negligible visually but it makes golden-image tests brittle.",
             "better": "document the rounding policy or use round() consistently."},
        ], "explain": {"purpose": "Review fixture: working compositor with planted findings.",
                       "approach": "Real review categories: contracts, performance, validation.",
                       "key_points": ["validate render-target contracts early",
                                      "prefer vectorized blending",
                                      "clamp alpha at boundaries"],
                       "big_o_time": "O(w*h) (vectorizable)", "big_o_space": "O(w*h)",
                       "edge_cases": ["size mismatch", "mode mismatch", "alpha extremes"]}},
        tags=["media", "review"], variant="review", seed=rng.randrange(2**31))
    return cand, cand.notes["issues"]


MediaFramesFamily.review_variant = _media_frames_review_variant
