"""v0.4.0 extension: the "mind of Opus 5.5" video-engineering families.

Reverse-engineered from the p(doom) video engine (mexicat/pdoom-video, MIT)
and the ClaudeAnimationBase animation guide (MIT): the working habits that
make Opus-authored generative videos hold together are turned into verified,
ORIGINAL code tasks:

- media_mv_post_chain: the HDR post chain (exposure -> soft-knee bright pass
  -> blur -> turquoise halation -> vignette -> grain -> sRGB) and why ORDER
  is part of the look.
- media_mv_line_batch: deterministic 2D line batching with a stable
  (z, sequence) order and a scale-aware hairline floor (the 4K lesson).
- media_mv_shot_reads: shot timing planned from viewer "reads" (find ->
  understand -> hold), sequential, with a final hold.

The default signal colour stays the Miku turquoise #39C5BB - never orange.
All verification is REAL: pure-python reference implementations run in the
sandbox and golden values are asserted exactly.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register

SIGNAL_HEX = "#39C5BB"
HALATION_TINT = (0.22, 1.0, 0.92)  # turquoise-family hot tint (linear)


def _mk_explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {"purpose": purpose, "approach": approach, "key_points": key_points,
            "big_o_time": big_o_time, "big_o_space": big_o_space,
            "edge_cases": edge_cases}


def _frame_task(expected):
    return (
        "Implement a deterministic piece of a generative music-video engine in "
        f"Python (every frame is a pure function of time; the default signal "
        f"colour is the Miku turquoise {SIGNAL_HEX}, never orange). {expected}")


# ---------------------------------------------------------------- post chain
class MediaMVPostChainFamily(Family):
    """HDR post chain: order of bright-pass, blur, halation, grain."""
    NAME = "media_mv_post_chain"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["halation_order", "bright_knee", "grain_placement"])
        w, h = 6, 4
        hotspot = rng.randrange(1, w)  # top row, away from the probe corner
        seed = rng.randrange(1, 2**31)
        amp = rng.choice([0.02, 0.03, 0.04])
        knee = rng.choice([0.25, 0.3, 0.35])
        threshold = rng.choice([0.8, 0.85, 0.9])

        code = (
            f"W, H = {w}, {h}\n"
            f"EXPOSURE = 1.25\n"
            f"BLOOM_THRESHOLD = {threshold}\n"
            f"BLOOM_KNEE = {knee}\n"
            f"HALATION_TINT = {HALATION_TINT!r}  # turquoise-family hot tint\n"
            f"HALATION_GAIN = 0.5\n"
            f"GRAIN_SEED = {seed}\n"
            f"GRAIN_AMP = {amp}\n"
            f"VIGNETTE = 0.18\n\n\n"
            "def clamp01(v):\n"
            "    return max(0.0, min(1.0, v))\n\n\n"
            "def lcg(seed):\n"
            "    \"\"\"Deterministic per-pixel noise in [-0.5, 0.5).\"\"\"\n"
            "    state = seed & 0x7FFFFFFF\n"
            "    while True:\n"
            "        state = (1103515245 * state + 12345) & 0x7FFFFFFF\n"
            "        yield state / float(0x7FFFFFFF) - 0.5\n\n\n"
            "def luminance(px):\n"
            "    r, g, b = px\n"
            "    return 0.2126 * r + 0.7152 * g + 0.0722 * b\n\n\n"
            "def exposure_apply(img):\n"
            "    return [[tuple(c * EXPOSURE for c in px) for px in row]\n"
            "            for row in img]\n\n\n"
            "def bright_pass(px):\n"
            "    \"\"\"Soft-knee bright pass: 0 below the knee, full above the\n"
            "    threshold, linear ramp in between (HDR floats).\"\"\"\n"
            "    lo = BLOOM_THRESHOLD - BLOOM_KNEE\n"
            "    lum = luminance(px)\n"
            "    if lum <= lo:\n"
            "        return (0.0, 0.0, 0.0)\n"
            "    f = min(1.0, (lum - lo) / (2 * BLOOM_KNEE))\n"
            "    return (px[0] * f, px[1] * f, px[2] * f)\n\n\n"
            "def blur_once(img):\n"
            "    \"\"\"One separable box-blur pass (radius 1, edge-clamped):\n"
            "    horizontal sweep into tmp, then vertical sweep into out.\"\"\"\n"
            "    tmp = [[(0.0, 0.0, 0.0)] * W for _ in range(H)]\n"
            "    for y in range(H):\n"
            "        for x in range(W):\n"
            "            xs = [max(0, min(W - 1, x + d)) for d in (-1, 0, 1)]\n"
            "            tmp[y][x] = tuple(sum(img[y][i][k] for i in xs) / 3.0\n"
            "                              for k in range(3))\n"
            "    out = [[(0.0, 0.0, 0.0)] * W for _ in range(H)]\n"
            "    for y in range(H):\n"
            "        for x in range(W):\n"
            "            ys = [max(0, min(H - 1, y + d)) for d in (-1, 0, 1)]\n"
            "            out[y][x] = tuple(sum(tmp[i][x][k] for i in ys) / 3.0\n"
            "                              for k in range(3))\n"
            "    return out\n\n\n"
            "def halation_add(px, blurred):\n"
            "    \"\"\"Add the blurred bloom back, tinted by the hot tint.\"\"\"\n"
            "    return tuple(px[k] + blurred[k] * HALATION_TINT[k] * HALATION_GAIN\n"
            "                 for k in range(3))\n\n\n"
            "def vignette(px, x, y):\n"
            "    dx = (x + 0.5) / W - 0.5\n"
            "    dy = (y + 0.5) / H - 0.5\n"
            "    f = 1.0 - VIGNETTE * 4.0 * (dx * dx + dy * dy)\n"
            "    return (px[0] * f, px[1] * f, px[2] * f)\n\n\n"
            "def grain_add(px, noise):\n"
            "    n = noise * GRAIN_AMP\n"
            "    return tuple(px[k] + n for k in range(3))\n\n\n"
            "def to_srgb8(px):\n"
            "    return tuple(round(255.0 * clamp01(c) ** (1.0 / 2.2))\n"
            "                 for c in px)\n\n\n"
            "def render_frame(img, grain_seed=None):\n"
            "    \"\"\"Full post chain, in the order that defines the look:\n"
            "    exposure -> bright pass -> blur -> halation -> vignette ->\n"
            "    grain -> quantize to sRGB bytes. grain_seed overrides the\n"
            "    module seed (handy for A/B checks in tests).\"\"\"\n"
            "    img = exposure_apply(img)\n"
            "    bright = [[bright_pass(px) for px in row] for row in img]\n"
            "    blurred = blur_once(bright)\n"
            "    g = lcg(grain_seed if grain_seed is not None else GRAIN_SEED)\n"
            "    out = []\n"
            "    for y in range(H):\n"
            "        row = []\n"
            "        for x in range(W):\n"
            "            px = halation_add(img[y][x], blurred[y][x])\n"
            "            px = vignette(px, x, y)\n"
            "            px = grain_add(px, next(g))\n"
            "            row.append(to_srgb8(px))\n"
            "        out.append(row)\n"
            "    return out\n"
        )

        px_pool = []
        for i in range(w * h):
            if i == hotspot:
                px_pool.append((1.4, 1.2, 1.1))   # HDR hotspot: blooms
            elif i % 3 == 0:
                px_pool.append((0.06, 0.10, 0.10))  # near-ink (turquoise-dark)
            else:
                px_pool.append((0.30 + 0.01 * (i % 5), 0.34, 0.33))
        img_lit = "[" + ",".join(
            "[" + ",".join(str(px_pool[y * w + x]) for x in range(w)) + "]"
            for y in range(h)) + "]"

        if kind == "halation_order":
            expected = (
                "Halation glows only around bright pixels: the blur runs on the "
                "bright-passed image, so dark areas receive no halo. The chain "
                "order is exposure -> bright -> blur -> halation -> vignette -> "
                "grain -> quantize.")
            tests = (
                "def run_tests():\n"
                f"    IMG = {img_lit}\n"
                "    a = render_frame(IMG)\n"
                "    b = render_frame(IMG)\n"
                "    assert a == b  # pure function of the input: byte-stable\n"
                f"    hx, hy = {hotspot % w}, {hotspot // w}\n"
                "    nb = a[hy][min(W - 1, hx + 1)]\n"
                "    base = a[H - 1][0]\n"
                "    assert nb != base  # the halo reaches the hotspot's neighbour\n"
                "    # No halo may reach the far dark corner: walk the same grain\n"
                "    # stream and rebuild the pixel with a ZERO halation add.\n"
                "    py, px = H - 1, 0\n"
                "    exp_img = exposure_apply(IMG)\n"
                "    g = lcg(GRAIN_SEED)\n"
                "    for _ in range(py * W + px):\n"
                "        next(g)\n"
                "    p = grain_add(vignette(exp_img[py][px], px, py), next(g))\n"
                "    assert a[py][px] == to_srgb8(p)\n")
            explain = _mk_explain(
                "Post-chain stage order for a generative music video.",
                "Bright-pass isolates HDR hotspots; blur spreads only those; "
                "halation adds the tinted bloom back over the base image.",
                ["blur the bright pass, never the base image",
                 "the turquoise-family tint rides on the bloom only",
                 "grain and vignette come after the glow"],
                "O(W*H) per stage", "O(W*H)",
                ["hotspot at the frame edge", "all-dark frame",
                 "threshold below every pixel"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    bright = [[bright_pass(px) for px in row] for row in img]\n"
                    "    blurred = blur_once(bright)",
                    "    blurred = blur_once(img)\n"
                    "    bright = [[bright_pass(px) for px in row] for row in img]")}
            bugs = {"blur_before_bright": bug}

        elif kind == "bright_knee":
            # a pixel inside the knee zone: partial keep factor
            lo = threshold - knee
            knee_lum = lo + knee / 2.0
            # choose g so luminance = knee_lum: g dominates
            g_val = round(knee_lum / 0.7152, 4)
            knee_px = (round(g_val * 0.1, 4), g_val, round(g_val * 0.1, 4))
            img_lit2 = img_lit  # tests use both frames
            expected = (
                "The bright pass keeps sub-threshold pixels PARTIALLY inside the "
                f"knee: luminance in ({lo:.2f}, {threshold:.2f}) scales the pixel "
                "by (lum - lo) / (2*knee), so highlights fade in instead of "
                "popping.")
            tests = (
                "def run_tests():\n"
                f"    IMG = {img_lit}\n"
                "    assert bright_pass((0.1, 0.1, 0.1)) == (0.0, 0.0, 0.0)\n"
                f"    kp = bright_pass({knee_px!r})\n"
                "    assert 0.0 < kp[1] < 1.0  # partial keep inside the knee\n"
                f"    full = bright_pass((1.5, 1.5, 1.5))\n"
                "    assert full == (1.5, 1.5, 1.5)\n"
                "    a = render_frame(IMG)\n"
                "    b = render_frame(IMG)\n"
                "    assert a == b\n")
            explain = _mk_explain(
                "Soft-knee bright pass for bloom thresholds.",
                "Luminance gate with a linear ramp of width 2*knee under the "
                "threshold; partial factors keep the bloom onset smooth.",
                ["hard clips make bloom pop on beat hits",
                 "the knee width is a look parameter, not an accident",
                 "partial keep applies to the whole RGB tuple"],
                "O(1) per pixel", "O(1)",
                ["luminance exactly at lo", "luminance exactly at threshold",
                 "negative channel values"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "    f = min(1.0, (lum - lo) / (2 * BLOOM_KNEE))",
                    "    if lum < BLOOM_THRESHOLD:\n        return (0.0, 0.0, 0.0)\n"
                    "    f = min(1.0, (lum - lo) / (2 * BLOOM_KNEE))")}
            bugs = {"hard_clip_knee": bug}

        else:  # grain_placement
            expected = (
                "Film grain is applied to the HDR floats BEFORE quantization, so "
                "it survives the sRGB round and dithers banding. The grain is a "
                "seeded LCG stream consumed strictly in raster order.")
            tests = (
                "def run_tests():\n"
                f"    IMG = {img_lit}\n"
                "    a = render_frame(IMG)\n"
                "    b = render_frame(IMG)\n"
                "    assert a == b  # same seed: byte-stable\n"
                "    c = render_frame(IMG, grain_seed=GRAIN_SEED + 1)\n"
                "    assert a != c  # a different seed must reach the output bytes\n"
                "    d = render_frame(IMG, grain_seed=GRAIN_SEED)\n"
                "    assert a == d\n")
            explain = _mk_explain(
                "Grain placement in the post chain.",
                "Grain perturbs HDR floats pre-quantization; a seeded LCG walks "
                "the frame in raster order so renders are reproducible.",
                ["post-quantize grain rounds away: zero dither value",
                 "one stream, raster order: no per-channel divergence",
                 "GRAIN_AMP is a look knob tuned on stills"],
                "O(W*H)", "O(1) per pixel",
                ["GRAIN_AMP = 0", "same seed across frames",
                 "grain after vignette would stay fixed under vignette"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "            px = grain_add(px, next(g))\n"
                    "            row.append(to_srgb8(px))",
                    "            row.append(to_srgb8(px))\n"
                    "            g8 = row[-1]\n"
                    "            row[-1] = tuple(round(c + next(g) * GRAIN_AMP)\n"
                    "                         for c in g8)  # grain after quantize")}
            bugs = {"grain_after_quantize": bug}

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=_frame_task(expected),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "music_video", "post_chain", kind], variant=kind,
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


# ---------------------------------------------------------------- line batch
class MediaMVLineBatchFamily(Family):
    """Deterministic 2D line batching with a scale-aware hairline floor."""
    NAME = "media_mv_line_batch"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["stable_order", "hairline_scale"])
        n_lines = rng.randint(3, 5)
        zvals = [rng.randrange(0, 3) for _ in range(n_lines)]
        zvals[1] = zvals[0]  # lines 0 and 1 share a z: the tie is load-bearing
        lines = []
        for i in range(n_lines):
            x0 = rng.randrange(0, 40)
            y0 = rng.randrange(0, 30)
            n_pts = rng.randint(3, 4) if i == 0 else rng.randint(2, 4)
            pts = [(x0, y0)]
            for _ in range(n_pts - 1):
                px = pts[-1][0] + rng.randrange(-8, 9)
                py = pts[-1][1] + rng.randrange(-8, 9)
                pts.append((px, py))
            if i == 0 and kind == "hairline_scale":
                width0 = 0.2  # line 0 is always thin: the floor must bite
            else:
                width0 = rng.choice([0.2, 0.5, 1.0, 1.5, 2.5])
            lines.append({"z": zvals[i],
                          "points": pts,
                          "width": width0,
                          "additive": rng.random() < 0.4})
        scale = 2.0  # the 4K case: the only one where the floor bites
        lit = repr(lines)

        code = (
            f"SCALE = {scale!r}          # output scale: 1.0 (1080p) or 2.0 (4K)\n"
            "HAIRLINE_PX = 1.0     # physical-px floor so hairlines stay crisp\n"
            f"LINES = {lit}\n\n\n"
            "def batch_lines(lines=LINES):\n"
            "    \"\"\"Flatten polylines into GPU-ordered segments.\n\n"
            "    Segments are sorted by (z, line_seq, seg_idx): a STABLE order\n"
            "    that never depends on dict/set iteration. Each segment's width\n"
            "    is clamped to the logical hairline floor HAIRLINE_PX / SCALE,\n"
            "    so the floor stays 1 physical pixel at every output scale.\n"
            "    Returns the ordered segment dicts.\n"
            "    \"\"\"\n"
            "    segs = []\n"
            "    floor = HAIRLINE_PX / SCALE\n"
            "    for seq, line in enumerate(lines):\n"
            "        pts = line[\"points\"]\n"
            "        w = max(float(line[\"width\"]), floor)\n"
            "        for i in range(len(pts) - 1):\n"
            "            segs.append({\"z\": line[\"z\"], \"seq\": seq, \"seg\": i,\n"
            "                         \"a\": pts[i], \"b\": pts[i + 1],\n"
            "                         \"w\": w, \"add\": line[\"additive\"]})\n"
            "    segs.sort(key=lambda s: (s[\"z\"], s[\"seq\"], s[\"seg\"]))\n"
            "    return segs\n\n\n"
            "def manifest_hash(lines=LINES):\n"
            "    \"\"\"SHA-256 over the ordered batch: the render manifest key.\"\"\"\n"
            "    import hashlib, json\n"
            "    payload = json.dumps(batch_lines(lines), sort_keys=True,\n"
            "                         separators=(\",\", \":\"))\n"
            "    return hashlib.sha256(payload.encode()).hexdigest()\n"
        )

        if kind == "stable_order":
            expected = (
                "Segments come out in the deterministic (z, line_seq, seg_idx) "
                "order: lines sharing a z keep authoring order, and each line's "
                "segments stay consecutive. The manifest hash covers the ordered "
                "batch, so any reorder is detected.")
            tests = (
                "def run_tests():\n"
                "    segs = batch_lines()\n"
                "    keys = [(s['z'], s['seq'], s['seg']) for s in segs]\n"
                "    assert keys == sorted(keys)  # total order: z, then seq, then seg\n"
                "    assert manifest_hash() == manifest_hash()\n"
                f"    assert len(segs) == sum(len(l['points']) - 1 for l in LINES)\n"
                "    seen = []\n"
                "    for s in segs:\n"
                "        if not seen or seen[-1] != s['seq']:\n"
                "            seen.append(s['seq'])\n"
                "    assert len(seen) == len(set(seen))  # one line's segments stay together\n"
                "    seqs_in_z0 = [s['seq'] for s in segs if s['z'] == keys[0][0]]\n"
                "    assert seqs_in_z0 == sorted(seqs_in_z0)  # authoring order kept\n")
            explain = _mk_explain(
                "Stable batching for 2D line rendering.",
                "Polylines flatten to segments carrying (z, seq, seg); sorting "
                "on that triple is total, so no run-to-run or engine-version "
                "reordering is possible.",
                ["ties broken by authoring order, not by container luck",
                 "hash the ORDERED list: order is render-relevant",
                 "segments of one line stay together for batching"],
                "O(n log n)", "O(n)",
                ["two lines with equal z", "single-point polyline",
                 "empty batch"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "segs.sort(key=lambda s: (s[\"z\"], s[\"seq\"], s[\"seg\"]))",
                    "segs.sort(key=lambda s: (s[\"z\"], s[\"seg\"], s[\"seq\"]))")}
            bugs = {"seg_before_seq": bug}

        else:  # hairline_scale
            floor = 1.0 / scale
            expected = (
                f"The hairline floor lives in PHYSICAL pixels: at SCALE={scale} "
                f"a 0.2 logical-px line renders at max(0.2, {floor:.2f}) logical "
                "px, so the physical stroke never drops below one device pixel "
                "and hairlines stay crisp at 4K.")
            tests = (
                "def run_tests():\n"
                "    segs = batch_lines()\n"
                "    mine = [s for s in segs if s['seq'] == 0][0]\n"
                f"    assert abs(mine['w'] - max(LINES[0]['width'], {floor!r})) < 1e-9\n"
                "    thin = [s for s in segs if LINES[s['seq']]['width'] < HAIRLINE_PX / SCALE]\n"
                "    assert all(abs(s['w'] - HAIRLINE_PX / SCALE) < 1e-9 for s in thin)\n"
                "    thick = [s for s in segs if LINES[s['seq']]['width'] >= 1.0]\n"
                "    assert all(s['w'] == LINES[s['seq']]['width'] for s in thick)\n"
                "    assert manifest_hash() == manifest_hash()\n")
            explain = _mk_explain(
                "Scale-aware hairline floor for 4K exports.",
                "Widths are logical; the floor is physical. Dividing the 1-px "
                "floor by SCALE keeps thin strokes identical at 1x and merely "
                "sharper at 2x.",
                ["max(width, HAIRLINE_PX / SCALE), never a constant",
                 "floors below 1 physical px shimmer on export",
                 "AA feathering works in physical px too"],
                "O(n log n)", "O(n)",
                ["width exactly at the floor", "SCALE = 0.5 downscale",
                 "additive hairlines stacking to a glow"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "floor = HAIRLINE_PX / SCALE",
                    "floor = HAIRLINE_PX  # BUG: logical constant, ignores SCALE")}
            bugs = {"logical_hairline_floor": bug}

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=_frame_task(expected),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "music_video", "line_batch", kind], variant=kind,
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


# ---------------------------------------------------------------- shot reads
class MediaMVShotReadsFamily(Family):
    """Shot timing scheduled from viewer reads (find -> understand -> hold)."""
    NAME = "media_mv_shot_reads"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "trace")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["read_schedule", "anticipation"])
        fps = rng.choice([24, 30])
        reads = []
        for i in range(rng.randint(2, 3)):
            reads.append({"name": f"read{i + 1}",
                          "find": rng.randrange(4, 10),
                          "understand": rng.randrange(8, 18),
                          "anticipate": kind == "anticipation" and i == 0})
        hold = rng.choice([6, 8, 10])
        lit = repr(reads)

        code = (
            f"FPS = {fps}\n"
            f"HOLD_FRAMES = {hold}   # every read lands, then breathes\n"
            f"READS = {lit}\n\n\n"
            "def schedule_shot(reads=READS, hold=HOLD_FRAMES):\n"
            "    \"\"\"Turn viewer reads into an end-exclusive frame schedule.\n\n"
            "    Each read costs find + understand frames; a read flagged\n"
            "    'anticipate' inserts the wind-up BEFORE the find (the eye is\n"
            "    told where to look). After every understand phase the shot\n"
            "    holds HOLD_FRAMES so the meaning lands. Reads run strictly\n"
            "    one at a time: a new read never starts while the previous\n"
            "    one is still landing. Returns (phases, total) with phases as\n"
            "    (name, kind, start, end) end-exclusive tuples.\n"
            "    \"\"\"\n"
            "    phases = []\n"
            "    t = 0\n"
            "    for r in reads:\n"
            "        if r.get(\"anticipate\"):\n"
            "            phases.append((r[\"name\"], \"anticipate\", t, t + 3))\n"
            "            t += 3\n"
            "        phases.append((r[\"name\"], \"find\", t, t + r[\"find\"]))\n"
            "        t += r[\"find\"]\n"
            "        phases.append((r[\"name\"], \"understand\", t, t + r[\"understand\"]))\n"
            "        t += r[\"understand\"]\n"
            "        phases.append((r[\"name\"], \"hold\", t, t + hold))\n"
            "        t += hold\n"
            "    return phases, t\n\n\n"
            "def assert_sequential(phases):\n"
            "    \"\"\"Raises if two phases overlap or leave a gap.\"\"\"\n"
            "    for a, b in zip(phases, phases[1:]):\n"
            "        if a[3] != b[2]:\n"
            "            raise ValueError(\"phases must be contiguous\")\n"
            "    if phases and phases[-1][1] != \"hold\":\n"
            "        raise ValueError(\"shot must end on a hold\")\n"
        )

        if kind == "read_schedule":
            total = sum(3 if r["anticipate"] else 0 for r in reads) + \
                sum(r["find"] + r["understand"] for r in reads) + hold * len(reads)
            expected = (
                f"The {len(reads)} reads are scheduled strictly in sequence at "
                f"{fps} fps: each gets find + understand frames and a {hold}-frame "
                f"hold, for a total of {total} frames. No read starts before the "
                "previous one lands, and the shot ends on a hold.")
            tests = (
                "def run_tests():\n"
                f"    phases, total = schedule_shot()\n"
                f"    assert total == {total}\n"
                "    assert_sequential(phases)\n"
                "    names = [p[0] for p in phases]\n"
                f"    assert set(names) == set(r['name'] for r in READS)\n"
                "    kinds = [p[1] for p in phases]\n"
                "    assert kinds[-1] == 'hold'\n"
                f"    assert kinds.count('understand') == {len(reads)}\n"
                "    ends = [p[3] for p in phases]\n"
                "    assert ends == sorted(ends)\n")
            explain = _mk_explain(
                "Read-based shot timing for generated animation.",
                "Model the viewer: eye travel (find), comprehension "
                "(understand), and a hold to register the meaning; stack reads "
                "sequentially, never in parallel.",
                ["one read at a time: overlaps waste both",
                 "the final hold is part of the shot, not padding",
                 "end-exclusive windows compose with the scene timeline"],
                "O(reads)", "O(phases)",
                ["tiny find times for central reads", "shot with one read",
                 "read flagged anticipate twice"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        phases.append((r[\"name\"], \"hold\", t, t + hold))\n"
                    "        t += hold\n"
                    "    return phases, t",
                    "        if r is not reads[-1]:\n"
                    "            phases.append((r[\"name\"], \"hold\", t, t + hold))\n"
                    "            t += hold\n"
                    "    return phases, t")}
            bugs = {"final_hold_dropped": bug}

        else:  # anticipation
            total = 3 + sum(r["find"] + r["understand"] for r in reads) + hold * len(reads)
            expected = (
                "The first read is anticipated: a 3-frame wind-up phase runs "
                "BEFORE its find phase, telling the eye where to look. The rest "
                "of the schedule is unchanged (find -> understand -> hold per "
                f"read, {total} frames total).")
            tests = (
                "def run_tests():\n"
                f"    phases, total = schedule_shot()\n"
                f"    assert total == {total}\n"
                "    assert_sequential(phases)\n"
                "    assert phases[0][1] == 'anticipate'\n"
                "    assert phases[1][1] == 'find'\n"
                "    assert phases[0][3] == phases[1][2]\n"
                f"    assert phases[0][3] - phases[0][2] == 3\n"
                "    kinds = [p[1] for p in phases]\n"
                "    assert kinds.count('anticipate') == 1\n")
            explain = _mk_explain(
                "Anticipation before the action.",
                "A short wind-up phase precedes the find phase of the action "
                "read, so the viewer's eye is already there when it happens.",
                ["anticipation is timed, not implied",
                 "only flagged reads get the wind-up",
                 "contiguity is preserved: no gaps, no overlaps"],
                "O(reads)", "O(phases)",
                ["anticipate on the last read", "0-frame anticipation",
                 "two anticipated reads"])
            def bug(files):
                return {"solution.py": files["solution.py"].replace(
                    "        if r.get(\"anticipate\"):\n"
                    "            phases.append((r[\"name\"], \"anticipate\", t, t + 3))\n"
                    "            t += 3\n",
                    "        if r.get(\"anticipate\"):\n"
                    "            phases.append((r[\"name\"], \"anticipate\", t, t + 3))\n"
                    "            t += 3\n"
                    "            t -= 3  # BUG: overlap, the wind-up costs nothing\n")}
            bugs = {"anticipation_overlaps": bug}

        cand = Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=_frame_task(expected),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": kind, "_bug_fns": bugs},
            tags=["media", "music_video", "shot_reads", kind], variant=kind,
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


register(globals(), MediaMVPostChainFamily)
register(globals(), MediaMVLineBatchFamily)
register(globals(), MediaMVShotReadsFamily)
