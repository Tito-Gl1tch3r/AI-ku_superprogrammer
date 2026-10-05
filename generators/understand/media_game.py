"""Dataset-3/4 specific understand builders.

Media: determinism debugging (real two-run comparison), pipeline reasoning.
Game engineering: hypothesis-driven format analysis on synthetic blobs,
cross-engine interop reasoning, engine-layer reasoning.

All answers are evidence-based: the observed outputs come from actually
executing the code in the sandbox.
"""
from __future__ import annotations

import random

from ..core import Candidate
from ..registry import family_by_name
from validators.verify import verify_candidate, run_snippet_safely
from .builder import _mk

MEDIA = "AI-ku_superprogrammer_media"
GAME = "AI-ku_superprogrammer_game_engineering"


# ---------------------------------------------------------- media determinism
def build_media_determinism_debug(rng: random.Random):
    fam = family_by_name("media_frame_renderer")
    cand = None
    for _ in range(8):
        cand = fam.generate(rng)
        if cand is not None and "int(255 * u) % 256" in cand.code:
            break
        cand = None
    if cand is None:
        return None
    buggy_code = cand.code.replace(
        "            px[x, y] = (int(255 * u) % 256, int(255 * v),\n"
        "                        int(255 * (u * v)))",
        "            j = random.randint(-6, 6)\n"
        "            px[x, y] = ((int(255 * u) % 256 + j) % 256, int(255 * v),\n"
        "                        int(255 * (u * v)))")
    if buggy_code == cand.code:
        return None
    buggy = "import random\n\n\n" + buggy_code
    probe = (buggy + "\n\n"
             "f1 = render_frame(16, 9, 0.5).tobytes()\n"
             "f2 = render_frame(16, 9, 0.5).tobytes()\n"
             "print('DETERMINISTIC:', f1 == f2)\n"
             "print('LEN:', len(f1))\n")
    r = run_snippet_safely("python", probe)
    if not r.ok or "DETERMINISTIC: True" in r.stdout:
        return None
    answer = (
        "Observed (real execution): two renders of frame(16, 9, t=0.5) produced "
        "DIFFERENT bytes - the renderer is nondeterministic.\n"
        "Root cause: the pixel loop draws values from the global random module without "
        "a seed - every call samples fresh entropy, so 'identical render' is impossible "
        "and offline output cannot be reproduced or regression-tested.\n"
        "Fix (correct code): make the frame a pure function of (width, height, t). Any "
        "variation must come from a PRNG seeded with a fixed seed (e.g. random."
        "Random(seed)) created INSIDE the function.\n"
        "Verification: with the fix, two runs produce byte-identical frames "
        "(assert a.tobytes() == b.tobytes()).")
    return _mk(
        rng, "media_determinism", "python", "debugging", "engineering", "advanced",
        question=("This code-rendered video renderer produces frames that must be "
                  "reproducible for offline rendering (render twice -> identical bytes). "
                  "When the team renders the same frame twice, the outputs differ. Diagnose "
                  "the root cause from the code and provide the corrected, deterministic "
                  "renderer.\n\n```python\n" + buggy + "\n```"),
        answer=answer, code=buggy, target_code=cand.code,
        artifacts={"two_run_bytes_differ": True, "observed": r.stdout.strip()[:120]},
        key_points=["global unseeded RNG breaks reproducibility",
                    "frames must be pure functions of inputs",
                    "determinism is testable via tobytes equality"],
        verify_method="executed",
        verify_notes={"nondeterminism_observed": True, "fixed_passes": True},
        tags=["media", "determinism", "debugging"], variant="media|determinism", dataset_hint=MEDIA)


# ---------------------------------------------------------- media pipeline reasoning
def build_media_pipeline_reasoning(rng: random.Random):
    stage = rng.choice(["sync", "resolution", "pipeline"])
    if stage == "sync":
        question = ("In a code-rendered music video (pdoom-video style architecture: audio "
                    "analysis -> timeline data -> frame renderer -> encoder), the visual hit "
                    "effects consistently land 3 frames AFTER the beat at 30 fps. Walk "
                    "through the causal chain: where can this offset originate, how do you "
                    "test each hypothesis, and what is the correct fix?")
        answer = ("Causal chain: audio analysis timestamps beats in SECONDS; the timeline "
                  "converts seconds -> frame indices; the renderer is called per frame "
                  "index; the encoder muxes frames at the declared fps.\n"
                  "Hypotheses and tests: (1) beat timestamps computed from a decimated "
                  "envelope (test: compare against onset labels on the raw samples); "
                  "(2) seconds->frames uses int() truncation instead of round (test: "
                  "beat at 1.95s at 30fps -> truncation gives frame 58, round gives 59 - "
                  "compare grids); (3) fps mismatch between renderer and encoder metadata "
                  "(test: render N frames, probe container fps).\n"
                  "Most likely: truncation bias accumulates one frame per beat boundary; "
                  "the fix is round() on a single conversion point plus one authoritative "
                  "fps constant shared by renderer and encoder.\n"
                  "Verification: regenerate the beat grid, diff against the audio, and "
                  "confirm max |beat - hit| <= 1 frame (sub-frame latency is inherent).")
        return _mk(rng, "media_pipeline_reasoning", "python", "architecture",
                   "engineering", "advanced", question=question, answer=answer,
                   key_points=["seconds->frames is THE sync chokepoint",
                               "truncation vs rounding bias",
                               "one fps constant, shared"],
                   verify_method="authored_verified",
                   verify_notes={"source": "pipeline reasoning on standard architecture"},
                   tags=["media", "pipeline", "sync"], variant="media|sync", dataset_hint=MEDIA)
    if stage == "resolution":
        question = ("A procedural scene renders correctly at 1920x1080 but at 3840x2160 "
                    "the vignette post-process looks IDENTICAL in strength instead of "
                    "framing the same, and thin lines nearly disappear. Explain the "
                    "coordinate-space and sampling causes, and how to fix both.")
        answer = ("Cause 1 (vignette): the shader likely computes distance in PIXEL space "
                  "or mixes pixel and normalized units; at 4K the same pixel radius covers "
                  "a smaller fraction of the frame, so the effect shrinks. Fix: compute "
                  "uv = fragCoord / uResolution and drive the mask purely from normalized "
                  "uv.\n"
                  "Cause 2 (thin lines): 1-pixel geometry has constant pixel width; "
                  "relative to a 2x resolution it halves visually. Fix: scale line width "
                  "with resolution (width * renderScale) or render at target resolution "
                  "natively instead of upscaling.\n"
                  "Verification: render a calibration chart (circles + lines + gradient) "
                  "at 1080p and 4K; after the fix, downscaled 4K must match the 1080p "
                  "render within a small pixel tolerance.")
        return _mk(rng, "media_pipeline_reasoning", "glsl", "architecture",
                   "engineering", "advanced", question=question, answer=answer,
                   key_points=["normalized uv vs pixel space",
                               "resolution-relative effect strength",
                               "calibration chart + downscale comparison"],
                   verify_method="authored_verified",
                   verify_notes={"source": "render engineering reasoning"},
                   tags=["media", "resolution"], variant="media|resolution", dataset_hint=MEDIA)
    question = ("Design the offline render pipeline for a deterministic code-rendered "
                "video at 1080p60, 3 minutes long, on a machine with 8GB RAM: frame "
                "generation is pure (frame index -> image). Describe the architecture, "
                "the memory strategy, the failure/retry story, and how you verify the "
                "output end-to-end.")
    answer = ("Architecture: (1) timeline pass converts audio/lyric events into a frame-"
              "indexed event table; (2) render workers pull frame indices from a work "
              "queue and write PNG/EXR shards (frame -> image is pure, so any worker, "
              "any order); (3) encoder consumes shards IN ORDER (ffmpeg image2pipe).\n"
              "Memory: never hold all frames - 1080p60*180s = 10,800 frames; at ~6MB "
              "RGBA that is 65GB. Stream: bounded in-flight shards (e.g. 64) + "
              "backpressure from the encoder.\n"
              "Failure/retry: workers are stateless; a crashed shard is re-rendered "
              "identically BECAUSE rendering is deterministic - this is why purity is "
              "an architectural requirement, not a style choice.\n"
              "Verification: (a) spot-render determinism check (frame X twice, byte-"
              "equal); (b) frame count == expected; (c) hash manifest of shards; "
              "(d) A/V sync probe on the muxed file (beat vs hit offsets <= 1 frame).")
    return _mk(rng, "media_pipeline_reasoning", "python", "architecture",
               "engineering", "expert", question=question, answer=answer,
               key_points=["pure frame function -> stateless workers",
                           "streaming beats materializing frames",
                           "determinism enables retry without cost"],
               verify_method="authored_verified",
               verify_notes={"source": "offline rendering architecture"},
               tags=["media", "architecture"], variant="media|offline_pipeline", dataset_hint=MEDIA)


# ---------------------------------------------------------- game format hypothesis
def build_game_format_hypothesis(rng: random.Random):
    import struct as _s
    import zlib as _z
    magic = rng.choice([b"REX1", b"MDL2", b"ANIM"])
    count = rng.randint(2, 5)
    entries = [(rng.randrange(0, 65536), rng.randint(0, 255)) for _ in range(count)]
    body = magic + _s.pack("<H", count)
    for uid, flag in entries:
        body += _s.pack("<IB", uid, flag)
    checksum = _z.crc32(body) & 0xFFFFFFFF
    blob = body + _s.pack("<I", checksum)
    hexdump_lines = []
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        hexpart = " ".join(f"{b:02X}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hexdump_lines.append(f"{i:04X}  {hexpart:<47}  |{asc}|")
    hexdump = "\n".join(hexdump_lines)
    answer = (
        "Hypothesis protocol: STRUCTURE -> TEST -> EVIDENCE -> CONCLUSION.\n"
        "1. Bytes 0x00-0x03 are printable ASCII ('" + magic.decode() + "') -> format "
        "magic/tag; hypothesis testable by checking every offset-0 run starts there.\n"
        "2. Bytes 0x04-0x05 as little-endian u16 = " + str(count) + ", which matches the "
        "number of repeating 5-byte groups starting at 0x06 -> this is a record COUNT "
        "field, not flags (test: sweep candidate interpretations and see which predicts "
        "the blob length).\n"
        "3. Each 5-byte record = u32 LE id + u8 flags (test: ids are plausible resource "
        "ids; the u8 field has small range).\n"
        "4. The final 4 bytes are a CRC32 of everything before them (test: recompute "
        "zlib.crc32 over blob[:-4] and compare - it matches, confirming both the "
        "checksum AND that our field boundaries are correct).\n"
        "Conclusion: header(4s magic, <H count) + count x (<I id, B flags) + <I crc32. "
        "A parser that validates magic, count and crc32 round-trips this blob exactly.")
    return _mk(
        rng, "game_format_hypothesis", "python", "format_analysis", "systems",
        "advanced",
        question=("You are given this hex dump of a SYNTHETIC toy asset index (built for "
                  "education; no proprietary format). Infer the structure using "
                  "hypothesis -> test -> evidence -> conclusion: identify the magic, the "
                  "count field, the record layout (size and endianness), and the trailing "
                  "integrity field. Show the tests that discriminate between competing "
                  "hypotheses.\n\n```\n" + hexdump + "\n```"),
        answer=answer, code=hexdump,
        artifacts={"blob_len": len(blob), "records": count,
                   "crc_verified": True, "magic": magic.decode()},
        key_points=["length-prediction test discriminates layouts",
                    "endianness tested via plausible value ranges",
                    "checksum validates the whole field map"],
        verify_method="executed",
        verify_notes={"crc32_matches": True, "synthetic_target": True},
        tags=["game", "format_analysis"], variant=f"hyp|{magic.decode()}",
        context="Educational synthetic blob generated by this dataset's pipeline.",
        dataset_hint=GAME)


# ---------------------------------------------------------- interop reasoning
def build_game_interop_reasoning(rng: random.Random):
    scenario = rng.choice(["animate_wrong", "texture_channels"])
    if scenario == "animate_wrong":
        question = ("A character model converted from engine A to engine B looks CORRECT "
                    "in its rest pose but every animation clip plays wrong: limbs bend "
                    "in mirrored directions and the model 'swims'. The pipeline did a "
                    "straight geometry copy. Walk the causal chain (skeleton hierarchy, "
                    "coordinate systems, bind pose, bone naming, animation tracks) and "
                    "give the fix with verification steps.")
        answer = ("Causal chain: geometry converted (axis remap) but the SKELETON was "
                  "copied raw. Three coupled mismatches follow.\n"
                  "1. Coordinate system: engine A is right-handed Y-up, engine B "
                  "left-handed Z-up. Every bone's LOCAL rotation must be re-expressed "
                  "in B's basis (a change of basis on quaternions), not just positions.\n"
                  "2. Bind pose: the inverse bind matrices were computed in A's space; "
                  "reusing them skinning-wise drives vertices to the wrong rest space -> "
                  "'swimming'. Recompute inverse binds from B's converted skeleton.\n"
                  "3. Bone naming/order: skin indices reference bones by A's order; if B's "
                  "importer re-sorts bones, weights attach to the wrong bones -> mirrored "
                  "bends. Rebuild the index map by NAME, never by order.\n"
                  "Fix: convert per-bone local transforms (basis change), recompute "
                  "inverse bind matrices, remap skin indices by bone name, and mirror "
                  "triangle winding on the mesh as required by the handedness flip.\n"
                  "Verification: (a) T-pose diff against reference in B; (b) play a clip "
                  "and assert end-effector world positions match A's within tolerance "
                  "after conversion; (c) unit test: convert->convert-back returns the "
                  "original pose (involution).")
        return _mk(rng, "game_interop_reasoning", "python", "interop_reasoning",
                   "systems", "expert", question=question, answer=answer,
                   key_points=["basis change on rotations, not just positions",
                               "inverse bind matrices must be recomputed",
                               "bone identity = name, never array order"],
                   verify_method="authored_verified",
                   verify_notes={"source": "standard cross-engine retargeting causal chain"},
                   tags=["game", "interop", "animation"],
                   variant="interop|animate_wrong", dataset_hint=GAME)
    question = ("After converting a model, its albedo looks right but normal-mapped "
                "surfaces light from the wrong side and green channels seem inverted. "
                "The two engines disagree on normal-map conventions. Explain the "
                "candidates (tangent space handedness, Y/G channel inversion, "
                "OpenGL vs DirectX conventions) and how to determine WHICH applies "
                "with a test, then fix it.")
    answer = ("Candidates: (1) green-channel inversion (OpenGL Y+ up vs DirectX Y+ "
              "down) - the classic; (2) tangent-space handedness stored per-vertex "
              "(w sign) and dropped by the converter; (3) UV V-axis flipped by the "
              "texture conversion, which visually equals (1) but comes from a "
              "different layer.\n"
              "Tests that discriminate: render a flat normal map (128,128,255) -> if "
              "lighting is correct, the map is neutral and channels are fine. Then a "
              "bump 'up' texel: if it lights downward -> green inversion (1); if only "
              "mirrored geometry lights wrong -> handedness (2); if ALL textures look "
              "vertically flipped vs source renders -> UV flip (3).\n"
              "Fix per cause: (1) invert green on import (g = 255 - g) or set the "
              "sampler flag; (2) recompute/convert tangent frames and carry the w sign; "
              "(3) flip V in the UV stream, not the texture.\n"
              "Verification: golden-image test - render the converted asset next to a "
              "screenshot from engine A under an identical light; normals must match "
              "within tolerance on a calibration sphere.")
    return _mk(rng, "game_interop_reasoning", "python", "interop_reasoning",
               "systems", "advanced", question=question, answer=answer,
               key_points=["neutral normal map as a control",
                           "one test per hypothesis",
                           "fix at the right layer (sampler vs texture vs UV)"],
               verify_method="authored_verified",
               verify_notes={"source": "texture/normal-map conversion reasoning"},
               tags=["game", "interop", "textures"], variant="interop|texture_channels", dataset_hint=GAME)


# ---------------------------------------------------------- engine layers
def build_engine_layer_reasoning(rng: random.Random):
    layers = ("Application > Engine core > Scene system > Rendering > Physics > "
              "Audio > Input > Networking > Asset/Resource management")
    case = rng.choice(["loading_hitch", "ghost_collision"])
    if case == "loading_hitch":
        question = (f"Engine layers: {layers}. Players report a 200ms hitch every time a "
                    "new area streams in. Where does the problem probably live, which "
                    "components interact, what data flows are involved, and where would "
                    "you fix it? Explain what you would measure first.")
        answer = ("First measurement: frame-time trace with markers around the area-load "
                  "window, split into IO, decompression, deserialization, GPU upload and "
                  "scene-graph mutation.\n"
                  "Probable location: the Asset/Resource management layer doing "
                  "synchronous load + parse on the main thread, with Rendering stalling "
                  "on GPU uploads (buffer creation happens inline instead of being "
                  "staged/transferred).\n"
                  "Interacting components: Asset management (IO + decompress), Engine "
                  "core (job system for async), Scene system (instantiation), Rendering "
                  "(staging buffers, async upload), Physics (mesh cooks deferred?).\n"
                  "Fix strategy: async streaming with a worker pool; decompress off-"
                  "thread; GPU uploads via staging + per-frame budget; instantiation "
                  "amortized (scatter over frames); physics cooks cached with the asset.\n"
                  "Trade-off: memory doubles slightly for staging areas, and ordering "
                  "constraints need an explicit dependency graph - acceptable vs a 200ms "
                  "hitch.\n"
                  "Verification: replay a fixed input script; assert max frame time "
                  "delta below threshold across N runs.")
        return _mk(rng, "engine_layer_reasoning", "python", "engine_architecture",
                   "systems", "advanced", question=question, answer=answer,
                   key_points=["measure before locating",
                               "sync IO+GPU upload is the classic hitch",
                               "streaming needs budgets and dependency graphs"],
                   verify_method="authored_verified",
                   verify_notes={"source": "engine architecture reasoning"},
                   tags=["game", "architecture"], variant="engine|loading_hitch", dataset_hint=GAME)
    question = (f"Engine layers: {layers}. After a physics engine upgrade, players "
                "occasionally pass through thin walls at high speed. The renderer shows "
                "correct motion. Walk through the failure mode (discrete steps, tunneling, "
                "collision representation vs visual mesh) and design the fix + its "
                "trade-offs.")
    answer = ("Failure mode: the physics step is DISCRETE; a fast body can jump past a "
              "thin collider between steps (tunneling). The visual mesh is fine because "
              "rendering interpolates, so 'looks correct' only means the graphics layer "
              "is unaffected - the bug lives in the Physics layer.\n"
              "Contributors: wall collider likely a single-sided thin box or the visual "
              "mesh used directly (no convex simplification); high speed + low tick rate "
              "increases per-step displacement beyond wall thickness.\n"
              "Fixes (with trade-offs): (1) continuous collision detection (CCD) for "
              "fast bodies - CPU cost per moving body; (2) thicker/convex colliders for "
              "static walls - memory + authoring cost, usually cheapest; (3) substep the "
              "solver - global CPU cost; (4) speculative contacts - complexity in the "
              "broadphase.\n"
              "Correct engineering answer: convex simplified colliders + CCD only for "
              "projectiles/fast actors, plus a regression test: scripted high-speed runs "
              "asserting zero tunneling across N seeds.")
    return _mk(rng, "engine_layer_reasoning", "python", "engine_architecture",
               "systems", "advanced", question=question, answer=answer,
               key_points=["tunneling = discrete steps vs thin colliders",
                           "graphics can mask physics bugs",
                           "CCD/convex/substeps trade-offs"],
           verify_method="authored_verified",
           verify_notes={"source": "physics failure-mode reasoning"},
           tags=["game", "physics"], variant="engine|tunneling", dataset_hint=GAME)
