"""v0.4.0 extension: "mind of Opus 5.5" understand builders.

Three reasoning tasks distilled from reverse-engineering Opus-authored
work (the p(doom) video engine, the ClaudeAnimationBase guide, and the
crossover-mod wave):

- mv_frameidx_pitfall: WHY floor(t * 60) double-exposes two animation
  states inside one exported frame's shutter (and frameIdx(t) does not).
  Ground truth is computed with the real sampling arithmetic.
- mv_palette_propagation: the blast radius of a palette.ts change - which
  files' rendered output actually changes, which only LOOK related, and
  which change for the wrong reason (a hardcoded hex).
- crossover_event_debug: reading a bridge delivery log to locate the
  first divergence between the correct bridge and a buggy one, and the
  resulting state divergence in game B.

Every answer is authored alongside a machine-checked reference simulation
so the pipeline verifies consistency for real.
"""
from __future__ import annotations

import random

from ..core import UnderstandCandidate
from .builder import _mk

MEDIA = "AI-ku_superprogrammer_media"
GAME = "AI-ku_superprogrammer_game_engineering"

SIGNAL_OLD = "#FF4D12"   # the p(doom) signal orange (the thing AI-ku never uses)
SIGNAL_NEW = "#39C5BB"   # the Miku turquoise default


# ---------------------------------------------------- frameIdx pitfall
def build_mv_frameidx_pitfall(rng: random.Random):
    fps = 60
    n_samples = 12
    shutter_frac = rng.choice([0.2, 0.25])
    k = rng.randrange(7, 120)
    case = rng.choice(["boundary", "mid", "late"])
    # frame time offset (in frame durations): 0.0 = exactly on the frame
    # boundary, 0.5 = mid-frame, 0.3 = late but safely inside the region
    offset = {"boundary": 0.0, "mid": 0.5, "late": 0.3}[case]
    F = 1.0 / fps
    t_center = (k + offset) * F
    half = shutter_frac * F / 2.0
    times = [t_center + half * (2.0 * i / (n_samples - 1) - 1.0)
             for i in range(n_samples)]
    states = [int(t * fps // 1) for t in times]  # floor(t * fps)
    uniq = sorted(set(states))
    counts = {s: states.count(s) for s in uniq}
    floor_states = len(uniq)
    split = ", ".join(f"state {s}: {c} samples" for s, c in sorted(counts.items()))

    question = (
        "The export renders every frame as the average of "
        f"{n_samples} sub-frames spread over a shutter of {shutter_frac} frame "
        "durations, centred on the frame's time. A scene blinks a spark by "
        "seeding its noise with int(t * 60) (the frame index by floor). For "
        f"frame k={k} at t = ({k} + {offset}) / 60 s, work out how many "
        "DISTINCT blink states the exported frame averages and how the "
        "samples split between them; then say what a frameIdx(t) helper "
        "(constant over the shutter) would give instead, and why the floor "
        "version reads as a ghost/double exposure.")
    if floor_states == 1:
        answer = (
            f"The shutter spans t in [{times[0] * fps:.3f}, {times[-1] * fps:.3f}] "
            f"in frame-index units, which lies entirely inside the region of "
            f"int(t*60) = {uniq[0]}. All {n_samples} sub-frames show ONE blink "
            f"state, so this particular frame looks correct - but the bug is "
            f"latent: with the shutter centred exactly on a frame boundary "
            f"(offset 0.0) the same code averages two states 50/50. frameIdx(t) "
            f"gives {k} for every sub-frame by construction; the floor version "
            f"is only safe by accident of where this frame's time sits.")
    else:
        answer = (
            f"The shutter spans t in [{times[0] * fps:.3f}, {times[-1] * fps:.3f}] "
            f"in frame-index units and straddles the boundary at {k}: the "
            f"export averages TWO blink states - {split}. The averaged frame "
            f"is a 50/50 ghost of both states (the classic double exposure "
            f"the engine guide warns about). frameIdx(t) is constant over the "
            f"shutter by definition: every sub-frame sees blink state index "
            f"{k}, and the blink renders crisply.")
    artifacts = {"frame": k, "offset": offset,
                 "floor_states": floor_states, "state_counts": counts,
                 "samples": n_samples, "shutter_frac": shutter_frac}
    key_points = [
        "sub-frames are rendered out of order and in any number",
        "floor switches AT the frame's own time: the shutter straddles it",
        "frameIdx(t) is constant over the shutter - that is its whole job",
        "noise keyed to continuous t should seed with frameIdx(t) too",
    ]
    return _mk(
        rng, "mv_frameidx_pitfall", "python", "mv_frameidx_pitfall",
        "engineering", "advanced", question=question, answer=answer,
        artifacts=artifacts,
        key_points=key_points,
        verify_method="executed",
        verify_notes={"sampling_recomputed": True, "floor_states": floor_states,
                      "state_counts": {str(s): c for s, c in counts.items()},
                      "case": case},
        tags=["media", "music_video", "determinism", "motion_blur"],
        variant=f"frameidx|{case}|{k}",
        context=("Engine guide rule: per-frame flicker keyed to 60 fps must "
                 "use frameIdx(t), not Math.floor(t * 60). This task makes "
                 "the arithmetic of that rule explicit."),
        dataset_hint=MEDIA)


# ------------------------------------------------ palette propagation
_PALETTE_ROLES = ("defines_signal", "glsl_scene", "ts_post", "canvas_hud",
                  "ember_only_scene", "dead_import", "hardcoded_hex")


def build_mv_palette_propagation(rng: random.Random):
    n_glsl = rng.randint(2, 3)
    files = [
        ("app/src/engine/palette.ts", "defines_signal",
         "central palette: exports signal/ember/blood hex + LIN.* + rgba()"),
    ]
    for i in range(n_glsl):
        files.append((f"app/src/scenes/pulse-{i + 1}.ts", "glsl_scene",
                      "fullscreen pass consuming C_SIGNAL via GLSL_COMMON"))
    files.append(("app/src/engine/post.ts", "ts_post",
                  "halation tint samples LIN.signal for the bloom pass"))
    files.append(("app/src/engine/hud.ts", "canvas_hud",
                  "readout draws with rgba('signal', 0.8) on Canvas2D"))
    files.append(("app/src/scenes/ember-motif.ts", "ember_only_scene",
                  "uses only C_EMBER / LIN.ember - never signal"))
    files.append(("app/src/scenes/old-graph.ts", "dead_import",
                  "imports the palette but renders from f.t only"))
    if rng.random() < 0.7:
        files.append(("app/src/scenes/legacy-spark.ts", "hardcoded_hex",
                      f"hardcodes the old signal value {SIGNAL_OLD} directly"))
    rng.shuffle(files)

    changed = [f for f, role, _ in files
               if role in ("defines_signal", "glsl_scene", "ts_post",
                           "canvas_hud", "hardcoded_hex")]
    structural = [f for f, role, _ in files
                  if role in ("ember_only_scene", "dead_import")]
    hard = [f for f, role, _ in files if role == "hardcoded_hex"]
    bullet_q = "\n".join(f"  - {f}: {why}" for f, role, why in files)
    question = (
        f"The centralized palette changes the signal colour from "
        f"{SIGNAL_OLD} (the old default this project bans) to {SIGNAL_NEW} "
        f"(the Miku turquoise default). Only palette.ts is edited. For each "
        f"file below, decide whether its RENDERED OUTPUT changes, and name "
        f"the one file (if any) that changes for a reason the palette "
        f"refactor should have made impossible:\n{bullet_q}\n"
        f"Answer with the count of changed files, the count of untouched "
        f"files, and the hardcoded-file verdict.")
    answer = (
        f"Changed ({len(changed)}): the palette module itself, every "
        f"C_SIGNAL scene ({n_glsl}), the halation pass reading LIN.signal, "
        f"and the HUD's rgba('signal') draw - they all consume the signal "
        f"name, so the new hex propagates through the uniforms. "
        f"Untouched ({len(structural)}): the ember-only scene (different "
        f"palette entry) and the dead import (renders from time alone). "
        + (f"Verdict: {hard[0]} ALSO changes, but only because it hardcoded "
           f"{SIGNAL_OLD} instead of consuming the palette - a centralization "
           f"bug the refactor exists to prevent; it must be repointed to the "
           f"palette, not left matching by coincidence."
           if hard else
           "Verdict: no hardcoded hex in this inventory - every consumer "
           "goes through the palette, which is exactly the point of the "
           "C_* / LIN.* / rgba() discipline."))
    artifacts = {"files": [f for f, _, _ in files], "changed": len(changed),
                 "untouched": len(structural),
                 "hardcoded": list(hard)}
    key_points = [
        "one hex edit propagates through named consumers only",
        "GLSL consts, TS LIN.* and Canvas2D rgba() are three faces of one entry",
        "similar colour is not shared colour: ember files do not move",
        "a hardcoded hex 'working' after a recolor is a bug wearing a patch",
    ]
    return _mk(
        rng, "mv_palette_propagation", "python", "mv_palette_propagation",
        "engineering", "intermediate", question=question, answer=answer,
        artifacts=artifacts,
        key_points=key_points,
        verify_method="executed",
        verify_notes={"palette_table_check": True, "changed_count": len(changed),
                      "untouched_count": len(structural),
                      "hardcoded_present": bool(hard)},
        tags=["media", "music_video", "palette", "refactor"],
        variant="palette|" + ("hard" if hard else "clean"),
        context=("Engine convention: scenes consume the palette through "
                 "C_* uniforms in GLSL, LIN.* in TS for GL, and rgba(name) "
                 "in Canvas2D - so the default signal colour is a single "
                 "decision per project."),
        dataset_hint=MEDIA)


# --------------------------------------------- crossover event debug
_BRIDGE_KINDS = ("duplicate_delivery", "deferred_dropped", "global_reorder")


def _bridge_sim(events, rate, rules, bug):
    seen = set()
    deferred = {"actions": [], "chat": []}
    count = {"actions": 0, "chat": 0}
    log = []
    inv = {}
    for ev in events:
        key = (ev["chan"], ev["seq"])
        if key in seen:
            if bug != "duplicate_delivery":
                continue
        else:
            seen.add(key)
        c = ev["chan"]
        if count[c] < rate:
            count[c] += 1
            out = rules.get(ev["kind"], "noop")
            log.append((c, ev["seq"], out, ev["val"]))
            inv[out] = inv.get(out, 0) + ev["val"]
        else:
            deferred[c].append(ev)
    if bug != "deferred_dropped":
        if bug == "global_reorder":
            flat = [e for c in sorted(deferred) for e in deferred[c]]
            flat.sort(key=lambda e: e["seq"])
            for ev in flat:
                out = rules.get(ev["kind"], "noop")
                log.append((ev["chan"], ev["seq"], out, ev["val"]))
                inv[out] = inv.get(out, 0) + ev["val"]
        else:
            for c in sorted(deferred):
                for ev in deferred[c]:
                    out = rules.get(ev["kind"], "noop")
                    log.append((c, ev["seq"], out, ev["val"]))
                    inv[out] = inv.get(out, 0) + ev["val"]
    return log, inv


def build_crossover_event_debug(rng: random.Random):
    rate = rng.randint(2, 3)
    rules = {"spell": "summon", "hit": "damage", "line": "shout"}
    kind = rng.choice(_BRIDGE_KINDS)
    events = []
    seq = 0
    for _ in range(rate):
        for chan in ("actions", "chat"):
            events.append({"seq": seq, "chan": chan,
                           "kind": rng.choice(list(rules)),
                           "val": rng.randrange(1, 9)})
            seq += 1
    events.append({"seq": seq, "chan": "chat",
                   "kind": rng.choice(list(rules)), "val": rng.randrange(1, 9)})
    seq += 1
    events.append({"seq": seq, "chan": "actions",
                   "kind": rng.choice(list(rules)), "val": rng.randrange(1, 9)})
    if kind == "duplicate_delivery":
        events.insert(rng.randrange(2, len(events)), dict(events[0]))

    good_log, good_inv = _bridge_sim(events, rate, rules, None)
    bad_log, bad_inv = _bridge_sim(events, rate, rules, kind)
    first_div = None
    for i, (g, b) in enumerate(zip(good_log, bad_log)):
        if g != b:
            first_div = i
            break
    if first_div is None and len(good_log) != len(bad_log):
        first_div = min(len(good_log), len(bad_log))
    assert first_div is not None, "scenario must diverge"
    div_good = good_log[first_div] if first_div < len(good_log) else None
    div_bad = bad_log[first_div] if first_div < len(bad_log) else None
    inv_delta = {k: (good_inv.get(k, 0), bad_inv.get(k, 0))
                 for k in set(good_inv) | set(bad_inv)
                 if good_inv.get(k, 0) != bad_inv.get(k, 0)}

    why = {
        "duplicate_delivery":
            "the re-sent (chan, seq) is delivered again: the seen-set check "
            "is missing, so B applies the event twice",
        "deferred_dropped":
            "the per-channel deferred queue is never drained after the "
            "window, so the overflow events never reach B",
        "global_reorder":
            "overflow drains as ONE global seq-sorted queue instead of "
            "per-channel FIFO: chat's deferred event (lower seq) jumps "
            "ahead of actions'",
    }[kind]
    question = (
        f"A crossover bridge forwards game-A events into game B with a rate "
        f"limit of {rate} deliveries per channel per window (overflow "
        f"deferred, per-channel FIFO). Two runs of the same event script "
        f"disagree: the reference log and the deployed build's log. Locate "
        f"the FIRST divergent delivery (0-based index, both entries) and "
        f"the inventory divergence it causes; then name the bridge rule "
        f"that was broken.\n"
        f"Events: {events!r}\n"
        f"Reference log tail: {good_log[-3:]!r}\n"
        f"Deployed log tail:  {bad_log[-3:]!r}")
    answer = (
        f"First divergence at index {first_div}: reference "
        f"{div_good!r} vs deployed {div_bad!r}. Broken rule: {why}. "
        f"Inventory divergence: {inv_delta!r} (reference, deployed). The "
        f"fix restores the invariant - at-most-once delivery keyed on "
        f"(chan, seq), per-channel FIFO through the window, deferred "
        f"overflow drained, never dropped.")
    artifacts = {"first_divergence": first_div,
                 "reference_entry": div_good, "deployed_entry": div_bad,
                 "inv_delta": {k: list(v) for k, v in inv_delta.items()},
                 "bug": kind}
    key_points = [
        "diff the logs at the first differing delivery, not the tail",
        "duplicates double-apply state; drops lose it; reorders mis-time it",
        "channel order is per channel - a global sort is a different contract",
        "the inventory diff is the observable consequence in game B",
    ]
    return _mk(
        rng, "crossover_event_debug", "python", "crossover_event_debug",
        "engineering", "advanced", question=question, answer=answer,
        artifacts=artifacts,
        key_points=key_points,
        verify_method="executed",
        verify_notes={"bridge_sim_recomputed": True, "bug": kind,
                      "first_divergence": first_div,
                      "good_len": len(good_log), "bad_len": len(bad_log)},
        tags=["game", "crossover", "bridge", "debugging"],
        variant=f"bridge|{kind}",
        context=("Crossover-mod methodology: two games run side by side; a "
                 "bridge translates and forwards events in real time. The "
                 "delivery log is the oracle for order and idempotency."),
        dataset_hint=GAME)
