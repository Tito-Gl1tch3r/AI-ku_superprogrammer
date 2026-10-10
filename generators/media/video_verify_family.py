"""v0.8.0 media family: the render QA loop (claude-remotion-skill pattern).

A render is not deliverable until it has been INSPECTED. This family renders
a REAL deterministic frame sequence with Pillow (pure function of the frame
index, seeded defects planted at generation), and the task is to implement
the auditor that finds them: empty frames, overlapping elements, off-palette
pixels, harsh cuts, and manifest mismatches (fps/total_frames/duration).

Verification is real: the auditor runs against the real rendered sequence
and must report exactly the planted defects (and nothing else).
"""
from __future__ import annotations

import json
import random

from PIL import Image

from ..core import Candidate, Family, register

SIGNAL_RGB = (57, 197, 187)   # Miku turquoise - the AI-ku signal (never orange)
INK_RGB = (10, 10, 11)
BONE_RGB = (238, 233, 223)
ASH_RGB = (156, 151, 143)
PALETTE = {"signal": SIGNAL_RGB, "ink": INK_RGB, "bone": BONE_RGB, "ash": ASH_RGB}


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {"purpose": purpose, "approach": approach, "key_points": key_points,
            "big_o_time": big_o_time, "big_o_space": big_o_space,
            "edge_cases": edge_cases}


def _render_sequence(rng: random.Random, w=48, h=24, total=36, fps=24):
    """Render a REAL deterministic sequence; plant 2-3 seeded defects.

    Layout: a bone panel + a signal bar. Defects (frame-disjoint):
      empty_frame  - the renderer lost the scene: all-ink frame
      overlap      - a duplicate ash box shares area with the bone panel
      off_palette  - one stray forbidden-orange pixel
      harsh_cut    - one frame flashes a bone background (brightness spike)
    Returns (frames, boxes_per_frame, manifest, defects, layout_fn).
    """
    el_w = rng.randint(8, 12)
    el_h = rng.randint(4, 6)
    margin = rng.randint(2, 4)

    def layout(f):
        bar_x = margin + (f * 2) % (w - 2 * margin - el_w)
        return [{"x": margin, "y": margin, "w": el_w, "h": el_h,
                 "color": list(BONE_RGB)},
                {"x": bar_x, "y": h - margin - 4, "w": el_w, "h": 4,
                 "color": list(SIGNAL_RGB)}]

    chosen = rng.sample(["empty_frame", "overlap", "off_palette", "harsh_cut"],
                        rng.randint(2, 3))

    def pick(exclude=()):
        f = rng.randint(4, total - 4)
        while f in exclude:
            f = rng.randint(4, total - 4)
        return f

    empty_f = pick() if "empty_frame" in chosen else None
    overlap_f = pick([empty_f]) if "overlap" in chosen else None
    offpal_f = pick([empty_f, overlap_f]) if "off_palette" in chosen else None
    harsh_f = pick([empty_f, overlap_f, offpal_f]) if "harsh_cut" in chosen else None

    boxes_per_frame = []
    for f in range(total):
        row = layout(f)
        if f == overlap_f:
            b0 = row[0]
            row = row + [{"x": b0["x"] + 2, "y": b0["y"] + 1, "w": b0["w"],
                          "h": b0["h"], "color": list(ASH_RGB)}]
        boxes_per_frame.append(row)

    frames = []
    for f in range(total):
        bg = BONE_RGB if f == harsh_f else INK_RGB
        img = Image.new("RGB", (w, h), bg)
        px = img.load()
        if f != empty_f:
            for b in boxes_per_frame[f]:
                for yy in range(b["y"], min(h, b["y"] + b["h"])):
                    for xx in range(b["x"], min(w, b["x"] + b["w"])):
                        px[xx, yy] = tuple(b["color"])
        if f == offpal_f:
            px[(w // 2 + f) % w, h // 2] = (255, 159, 69)  # forbidden orange
        frames.append(img)

    defects = {}
    if empty_f is not None:
        defects[empty_f] = "empty_frame"
    if overlap_f is not None:
        defects[overlap_f] = "overlap"
    if offpal_f is not None:
        defects[offpal_f] = "off_palette"
    if harsh_f is not None:
        defects[harsh_f] = "harsh_cut"
    manifest = {"fps": fps, "width": w, "height": h, "total_frames": total,
                "palette": [list(c) for c in (SIGNAL_RGB, INK_RGB, BONE_RGB,
                                              ASH_RGB)]}
    return frames, boxes_per_frame, manifest, defects


def _audit_reference(frames, boxes_per_frame, manifest):
    """Independent ground-truth audit (the semantics the candidate must match).

    One finding per frame max, priority: empty_frame > off_palette >
    harsh_cut > overlap. harsh_cut is judged on the |diff| INTO the frame.
    """
    findings = []
    pal = {SIGNAL_RGB, INK_RGB, BONE_RGB, ASH_RGB}
    thr = 60.0
    for i, img in enumerate(frames):
        rule = None
        px = list(img.getdata())
        if all(p == INK_RGB for p in px):
            rule = "empty_frame"
        elif any(p not in pal for p in px):
            rule = "off_palette"
        elif i > 0:
            prev = list(frames[i - 1].getdata())
            diff = sum(abs(a[j] - b[j]) for a, b in zip(prev, px)
                       for j in range(3)) / (len(prev) * 3)
            if diff > thr:
                rule = "harsh_cut"
        if rule is None and i < len(boxes_per_frame):
            row = boxes_per_frame[i]
            for a_i in range(len(row)):
                for b_i in range(a_i + 1, len(row)):
                    ax0, ay0, ax1, ay1 = (row[a_i]["x"], row[a_i]["y"],
                                          row[a_i]["x"] + row[a_i]["w"],
                                          row[a_i]["y"] + row[a_i]["h"])
                    bx0, by0, bx1, by1 = (row[b_i]["x"], row[b_i]["y"],
                                          row[b_i]["x"] + row[b_i]["w"],
                                          row[b_i]["y"] + row[b_i]["h"])
                    if min(ax1, bx1) - max(ax0, bx0) > 0 and \
                            min(ay1, by1) - max(ay0, by0) > 0:
                        rule = "overlap"
        if rule:
            findings.append({"frame": i, "rule": rule})
    return findings


def _manifest_problems(manifest, rendered_count):
    problems = []
    if manifest["total_frames"] != rendered_count:
        problems.append("total_frames_mismatch")
    duration = manifest["total_frames"] / manifest["fps"]
    if not (1.0 <= duration <= 60.0):
        problems.append("duration_out_of_range")
    if manifest["fps"] not in (12, 24, 25, 30, 60):
        problems.append("fps_out_of_range")
    return sorted(problems)


AUDIT_CODE = (
    "\n\ndef audit_frames(frames, boxes, manifest):\n"
    "    \"\"\"QA a rendered sequence. One finding per frame, sorted by frame.\n\n"
    "    Priority: empty_frame > off_palette > harsh_cut > overlap.\n"
    "      empty_frame  - every pixel equals the ink background\n"
    "      off_palette  - a pixel outside the manifest palette\n"
    "      harsh_cut    - mean |diff| into the frame > 60.0\n"
    "      overlap      - two layout boxes share non-zero area\n"
    "    \"\"\"\n"
    "    findings = []\n"
    "    pal = {tuple(c) for c in manifest['palette']}\n"
    "    thr = 60.0\n"
    "    for i, img in enumerate(frames):\n"
    "        rule = None\n"
    "        px = list(img.getdata())\n"
    "        if all(p == tuple(INK) for p in px):\n"
    "            rule = 'empty_frame'\n"
    "        elif any(p not in pal for p in px):\n"
    "            rule = 'off_palette'\n"
    "        elif i > 0:\n"
    "            prev = list(frames[i - 1].getdata())\n"
    "            diff = sum(abs(a[j] - b[j]) for a, b in zip(prev, px)\n"
    "                       for j in range(3)) / (len(prev) * 3)\n"
    "            if diff > thr:\n"
    "                rule = 'harsh_cut'\n"
    "        if rule is None:\n"
    "            row = boxes[i]\n"
    "            for a_i in range(len(row)):\n"
    "                for b_i in range(a_i + 1, len(row)):\n"
    "                    A, B = row[a_i], row[b_i]\n"
    "                    ox = min(A['x'] + A['w'], B['x'] + B['w']) - max(A['x'], B['x'])\n"
    "                    oy = min(A['y'] + A['h'], B['y'] + B['h']) - max(A['y'], B['y'])\n"
    "                    if ox > 0 and oy > 0:\n"
    "                        rule = 'overlap'\n"
    "        if rule:\n"
    "            findings.append({'frame': i, 'rule': rule})\n"
    "    return findings\n")


class MediaRenderVerifyFamily(Family):
    """render -> inspect -> fix: the review loop as an executable skill."""
    NAME = "media_render_verify"
    LANGUAGE = "python"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("explanation", "testing", "debugging")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["defect_audit", "manifest_audit"])
        if kind == "defect_audit":
            return self._defect_audit(rng)
        return self._manifest_audit(rng)

    # -- kind 1: full frame audit ------------------------------------------
    def _defect_audit(self, rng: random.Random):
        frames, boxes, manifest, defects = _render_sequence(rng)
        w, h, total = manifest["width"], manifest["height"], manifest["total_frames"]
        expected = _audit_reference(frames, boxes, manifest)
        if [f["rule"] for f in expected] != [defects.get(f["frame"])
                                             for f in expected]:
            return None  # planted defects must be exactly what the audit finds
        if not expected:
            return None

        # baked defect params so the candidate's re-render reproduces the
        # SAME defective sequence the reference audit inspected
        empty_f = [f for f, r in defects.items() if r == "empty_frame"]
        offpal_f = [f for f, r in defects.items() if r == "off_palette"]
        harsh_f = [f for f, r in defects.items() if r == "harsh_cut"]
        header = (
            f"WIDTH, HEIGHT, TOTAL = {w}, {h}, {total}\n"
            f"MANIFEST = {json.dumps(manifest)}\n"
            f"BOXES = {json.dumps(boxes)}\n"
            f"INK = {list(INK_RGB)}\n"
            f"ORANGE = [255, 159, 69]\n"
            f"BONE = {list(BONE_RGB)}\n"
            f"EMPTY_FRAMES = {json.dumps(empty_f)}\n"
            f"OFFPAL_FRAMES = {json.dumps(offpal_f)}\n"
            f"HARSH_FRAMES = {json.dumps(harsh_f)}\n\n\n"
            "def render_frame(f):\n"
            "    \"\"\"Deterministic re-render: layout + the baked defects.\"\"\"\n"
            "    from PIL import Image\n"
            "    bg = tuple(BONE) if f in HARSH_FRAMES else tuple(INK)\n"
            "    img = Image.new('RGB', (WIDTH, HEIGHT), bg)\n"
            "    px = img.load()\n"
            "    if f not in EMPTY_FRAMES:\n"
            "        for b in BOXES[f]:\n"
            "            for yy in range(b['y'], min(HEIGHT, b['y'] + b['h'])):\n"
            "                for xx in range(b['x'], min(WIDTH, b['x'] + b['w'])):\n"
            "                    px[xx, yy] = tuple(b['color'])\n"
            "    if f in OFFPAL_FRAMES:\n"
            "        px[(WIDTH // 2 + f) % WIDTH, HEIGHT // 2] = tuple(ORANGE)\n"
            "    return img\n\n\n"
            "def rebuilt_frames():\n"
            f"    return [render_frame(f) for f in range({total})]\n")
        code = header + AUDIT_CODE
        tests = (
            "from PIL import Image\n\n\n"
            "def run_tests():\n"
            "    frames = rebuilt_frames()\n"
            "    findings = audit_frames(frames, BOXES, MANIFEST)\n"
            f"    assert findings == {json.dumps(expected)}, findings\n"
            "    assert audit_frames(rebuilt_frames(), BOXES, MANIFEST) == findings"
            "  # deterministic\n")
        exp_text = (f"audit_frames reports exactly {expected} on the real "
                    "rendered sequence: every planted defect once, at its "
                    "frame, nothing else.")
        explain = _explain(
            "The render QA loop: a render is not deliverable unreviewed.",
            "Walk the real frames once; check emptiness, palette, neighbour "
            "diff and box overlap; report one finding per frame, sorted.",
            ["empty means EVERY pixel equals ink",
             "overlap = bounding boxes with non-zero shared area",
             "harsh cut = neighbour mean |diff| above threshold"],
            "O(frames * w * h)", "O(w * h)",
            ["defect on the last frame", "two rules on one frame",
             "all-ink sequence"])
        bugs = {
            "misses_empty": lambda src: src.replace(
                "if all(p == tuple(INK) for p in px):",
                "if all(p == tuple(INK) for p in px) and False:"),
            "loose_threshold": lambda src: src.replace(
                "thr = 60.0", "thr = 240.0"),
            "overlap_ignored": lambda src: src.replace(
                "                        rule = 'overlap'\n", ""),
            "off_palette_ignored": lambda src: src.replace(
                "        elif any(p not in pal for p in px):\n"
                "            rule = 'off_palette'\n", ""),
        }
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=("Implement the QA auditor `audit_frames(frames, boxes, "
                  f"manifest)` for a rendered video sequence ({w}x{h}, {total} "
                  f"frames at {manifest['fps']}fps). The sequence renders "
                  "deterministically from the baked BOXES layout; the auditor "
                  f"must report exactly: {expected}. One finding per frame "
                  "max, priority empty_frame > off_palette > harsh_cut > "
                  "overlap; harsh_cut is judged on the mean |diff| INTO the "
                  "frame with threshold 60.0. The forbidden stray colour (an "
                  "orange pixel) must be caught as off_palette. The signal "
                  f"colour is the Miku turquoise {SIGNAL_RGB} by default, "
                  "never orange."),
            expected_behavior=exp_text, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": "defect_audit",
                   "_bug_fns": bugs, "defects": defects},
            tags=["media", "render_qa", "defect_audit"],
            variant="defect_audit", seed=rng.randrange(2**31))

    # -- kind 2: manifest cross-check ---------------------------------------
    def _manifest_audit(self, rng: random.Random):
        total = rng.choice([36, 48, 72])
        fps = rng.choice([24, 30])
        manifest = {"fps": fps, "width": 48, "height": 24,
                    "total_frames": total}
        tampered = dict(manifest)
        tampered["total_frames"] = total + rng.choice([-4, 4])
        tampered["fps"] = fps + rng.choice([-6, 6])
        problems = _manifest_problems(tampered, total)
        if not problems:
            return None
        code = (
            f"MANIFEST = {json.dumps(tampered)}\n"
            f"RENDERED_COUNT = {total}\n\n\n"
            "def audit_manifest(manifest, rendered_count):\n"
            "    \"\"\"Cross-check the render manifest against the real sequence.\n\n"
            "    Returns a sorted list of problems:\n"
            "      'total_frames_mismatch' - declared != len(frames)\n"
            "      'duration_out_of_range' - duration (frames/fps) outside 1..60s\n"
            "      'fps_out_of_range'      - fps not in {12, 24, 25, 30, 60}\n"
            "    \"\"\"\n"
            "    problems = []\n"
            "    if manifest['total_frames'] != rendered_count:\n"
            "        problems.append('total_frames_mismatch')\n"
            "    duration = manifest['total_frames'] / manifest['fps']\n"
            "    if not (1.0 <= duration <= 60.0):\n"
            "        problems.append('duration_out_of_range')\n"
            "    if manifest['fps'] not in (12, 24, 25, 30, 60):\n"
            "        problems.append('fps_out_of_range')\n"
            "    return sorted(problems)\n")
        tests = (
            "def run_tests():\n"
            f"    assert audit_manifest(MANIFEST, RENDERED_COUNT) == "
            f"{json.dumps(problems)}, audit_manifest(MANIFEST, RENDERED_COUNT)\n"
            f"    clean = {json.dumps(manifest)}\n"
            f"    assert audit_manifest(clean, {total}) == [], "
            "'clean manifest passes'\n")
        expected = (f"audit_manifest flags {problems} on the tampered manifest "
                    f"({tampered['total_frames']} frames @ {tampered['fps']}fps "
                    f"declared vs {total} rendered @ {fps}fps) and passes the "
                    "clean one.")
        explain = _explain(
            "Delivery gate: the manifest must describe the real render.",
            "Compare declared totals with the rendered count, recompute the "
            "duration and validate fps against the standard set.",
            ["total_frames is checkable without touching pixels",
             "duration = frames / fps must land in the 1..60s band",
             "fps belongs to the standard set (12/24/25/30/60)"],
            "O(1)", "O(1)",
            ["both fields tampered", "clean manifest", "fps 25 vs 24"])
        bugs = {
            "skips_duration": lambda src: src.replace(
                "        problems.append('duration_out_of_range')",
                "        pass"),
            "total_swap": lambda src: src.replace(
                "if manifest['total_frames'] != rendered_count:",
                "if manifest['total_frames'] < rendered_count:"),
            "fps_any": lambda src: src.replace(
                "if manifest['fps'] not in (12, 24, 25, 30, 60):",
                "if manifest['fps'] not in (12, 24, 25, 30, 60, 18):"),
        }
        # guarantee the chosen bug breaks THIS instance
        safe = {}
        for k, fn in bugs.items():
            mutated = fn(code)
            if mutated != code:
                safe[k] = fn
        if not safe:
            return None
        return Candidate(
            family=self.NAME, language="python", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=("Implement the manifest auditor `audit_manifest(manifest, "
                  f"rendered_count)` for a rendered video: the declared "
                  f"manifest says {tampered['total_frames']} frames at "
                  f"{tampered['fps']}fps but the real render produced {total} "
                  f"frames at {fps}fps. Report the problems sorted: "
                  "total_frames_mismatch, duration_out_of_range, "
                  "fps_out_of_range. A clean manifest must produce no "
                  "problems."),
            expected_behavior=expected, code=code, tests=tests,
            verify_method="executed",
            notes={"explain": explain, "kind": "manifest_audit",
                   "_bug_fns": safe},
            tags=["media", "render_qa", "manifest_audit"],
            variant="manifest_audit", seed=rng.randrange(2**31))

    def make_buggy(self, rng: random.Random):
        """Self-verifying: the buggy candidate is accepted only when it REALLY
        fails the record's tests under the real python runner."""
        from validators.executors.python_exec import verify_python
        cand = self.generate(rng)
        if cand is None:
            return None
        bugs = cand.notes.get("_bug_fns") or {}
        if not bugs:
            return None
        kinds = sorted(bugs)
        rng.shuffle(kinds)
        for kind in kinds:
            buggy = bugs[kind](cand.code)
            if buggy == cand.code:
                continue
            bcand = Candidate(family=self.NAME, language="python",
                              domain=cand.domain, difficulty=cand.difficulty,
                              task=cand.task,
                              expected_behavior=cand.expected_behavior,
                              code=buggy, tests=cand.tests,
                              verify_method="executed",
                              notes={"bug_kind": kind,
                                     "correct_code": cand.code},
                              tags=cand.tags,
                              variant=cand.variant + f"|bug|{kind}",
                              seed=cand.seed)
            r = verify_python(bcand)
            if not r.ok:
                return (bcand, {"kind": kind, "problem": cand.variant,
                                "correct_code": cand.code,
                                "unit_notes": cand.notes.get("explain", {})})
        return None


register(globals(), MediaRenderVerifyFamily)
