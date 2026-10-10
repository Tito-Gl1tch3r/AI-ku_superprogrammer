"""v0.8.0 media family: beat-sync with the grid accepted BEFORE the storyboard.

video-motion-craft's flow: the beat grid is MEASURED from the real audio
(with error <= 3 frames), accepted, and only then cuts are placed. Here the
generator synthesizes a real PCM track with tempo drift (numpy), measures
onsets from the actual waveform (energy peaks + median interval), and bakes
the MEASURED grid into the task. A cut placed on the NOMINAL bpm grid drifts
out of tolerance - the planted bug that teaches why measured grids matter.

The TypeScript side places cuts / checks drift under Node type-stripping.
"""
from __future__ import annotations

import json
import random

import numpy as np

from ..core import Candidate, Family, register
from .ts_video_families import (_harvest_ts, _ts_candidate, make_buggy_ts,
                                SIGNAL_HEX, _explain, _wrap_tests)


def synthesize_track(rng: random.Random, sr: int = 8000, dur: float = 10.0):
    """Deterministic kick/hat track with a slight tempo drift (acceleration).

    Returns (beat_times, pcm, sr). The tempo curve is nominal + linear drift,
    so the TRUE grid is not the nominal grid - exactly like real recordings.
    """
    nominal = float(rng.choice([110, 120, 128]))
    drift = rng.uniform(3.0, 6.0) * rng.choice([-1.0, 1.0])  # bpm gained over the track
    beats = []
    t = 0.0
    while t < dur - 0.25:
        beats.append(t)
        bpm_now = nominal + drift * (t / dur)
        t += 60.0 / bpm_now
    n = int(sr * dur)
    pcm = np.zeros(n, dtype=np.float64)
    # kick: 55 Hz sine with exp decay at every beat
    kick_len = int(0.11 * sr)
    tt = np.arange(kick_len) / sr
    kick = np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 30)
    for bt in beats:
        i0 = int(bt * sr)
        if i0 + kick_len < n:
            pcm[i0:i0 + kick_len] += kick * 0.9
    # hat: quiet noise clicks on the off-beat (kept well below the onset
    # threshold so only KICKS are measured - the hat is texture, not grid)
    rng_state = np.random.RandomState(20261011)
    click_len = int(0.03 * sr)
    for bt in beats:
        i0 = int((bt + 60.0 / (nominal + drift * (bt / dur)) / 2) * sr)
        if i0 + click_len < n:
            pcm[i0:i0 + click_len] += rng_state.randn(click_len) * np.exp(
                -np.arange(click_len) / sr * 90) * 0.06
    return beats, pcm, sr, nominal, drift


def measure_beats(pcm: np.ndarray, sr: int, fps: int):
    """Onset detection on the real waveform -> (beat_frames, measured_bpm).

    Energy envelope (abs -> smooth -> positive diff) peak-picked with a
    refractory gap; interval median gives the measured bpm.
    """
    env = np.abs(pcm)
    k = int(sr * 0.01)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    d = np.maximum(np.diff(env), 0.0)
    thr = d.max() * 0.45
    refractory = int(sr * 0.20)
    onsets = []
    last = -refractory
    for i in range(1, len(d)):
        if d[i] > thr and i - last >= refractory:
            # local maximum check within +-3 samples
            lo, hi = max(0, i - 3), min(len(d), i + 4)
            if d[i] >= d[lo:hi].max():
                onsets.append(i / sr)
                last = i
    if len(onsets) < 6:
        return None, None
    intervals = np.diff(onsets)
    med = float(np.median(intervals))
    # drop intervals wildly off the median (missed/extra onsets) and re-time
    times = [onsets[0]] + [t for t, iv in zip(onsets[1:], intervals)
                           if 0.75 * med < iv < 1.33 * med]
    if len(times) < 6:
        return None, None
    iv2 = np.diff(times)
    bpm = 60.0 / float(np.median(iv2))
    frames = sorted({int(round(t * fps)) for t in times})
    return frames, bpm


class MediaTSBeatGridFamily(Family):
    """Cuts anchored to the MEASURED beat grid with error <= 3 frames."""
    NAME = "media_ts_beat_grid"
    LANGUAGE = "typescript"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "debugging")

    def _measure(self, rng: random.Random, fps: int = 24):
        for _ in range(6):
            beats, pcm, sr, nominal, drift = synthesize_track(rng)
            frames, bpm = measure_beats(pcm, sr, fps)
            if not frames or bpm is None:
                continue
            total = int(10.0 * fps)
            if frames[-1] > total - 10 or frames[0] < 4:
                continue
            # drift guarantee: nominal grid must leave tolerance by the end
            step_nom = 60.0 / nominal * fps
            nom = [round(k * step_nom) for k in range(int(total / step_nom) + 1)]
            drift_max = max(min(abs(b - g) for g in nom) for b in frames)
            if drift_max < 4:
                continue  # not enough tempo drift to punish the nominal-grid bug
            if abs(bpm - nominal) < 1.0:
                continue
            return frames, bpm, nominal, total, drift_max
        return None

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["cut_placement", "grid_check"])
        measured = self._measure(rng)
        if measured is None:
            return None
        beat_frames, bpm, nominal, total, drift_max = measured
        if kind == "cut_placement":
            scene_count = rng.choice([4, 5])
            ideal = [round(total * k / scene_count)
                     for k in range(1, scene_count)]
            snapped = [min(beat_frames, key=lambda b: (abs(b - c), b))
                       for c in ideal]
            errs = [abs(s - c) for s, c in zip(snapped, ideal)]
            if max(errs) > 3:
                return None  # the measured grid must ACCEPT the storyboard
            code = (
                "/**\n"
                " * Beat-sync: the grid below was MEASURED from the real audio\n"
                " * (onset detection on the waveform), not assumed from the\n"
                " * nominal bpm. Cuts are snapped to the measured beats with a\n"
                " * hard acceptance error of 3 frames.\n"
                " */\n"
                f"export const FPS = {24};\n"
                f"export const NOMINAL_BPM = {nominal};\n"
                f"export const MEASURED_BPM = {round(bpm, 2)};\n"
                f"export const TOTAL_FRAMES = {total};\n"
                f"export const BEAT_FRAMES: readonly number[] = "
                + json.dumps(beat_frames) + ";\n\n"
                "/** Nearest measured beat; ties resolve to the EARLIER beat. */\n"
                "export function snapToBeat(frame: number, beats: readonly number[]): number {\n"
                "  let best = beats[0];\n"
                "  for (const b of beats) {\n"
                "    if (Math.abs(b - frame) < Math.abs(best - frame)) best = b;\n"
                "  }\n"
                "  return best;\n"
                "}\n\n"
                "/**\n"
                " * Ideal cuts are evenly spaced; each is snapped to the measured\n"
                " * grid. Monotonic, first cut > 0, error <= 3 frames.\n"
                " */\n"
                "export function placeCuts(sceneCount: number, totalFrames: number,\n"
                "                          beats: readonly number[]): number[] {\n"
                "  const cuts: number[] = [];\n"
                "  for (let k = 1; k < sceneCount; k++) {\n"
                "    const ideal = Math.round((totalFrames * k) / sceneCount);\n"
                "    cuts.push(snapToBeat(ideal, beats));\n"
                "  }\n"
                "  return cuts;\n"
                "}\n")
            tests = _wrap_tests(
                "assert.deepStrictEqual(solution.placeCuts(" + str(scene_count)
                + ", solution.TOTAL_FRAMES, solution.BEAT_FRAMES), "
                + json.dumps(snapped) + ");\n"
                "assert.strictEqual(solution.snapToBeat(50, [40, 60]), 40, 'tie -> earlier');\n"
                "const cuts = solution.placeCuts(" + str(scene_count)
                + ", solution.TOTAL_FRAMES, solution.BEAT_FRAMES);\n"
                "for (let i = 1; i < cuts.length; i++)\n"
                "  assert.ok(cuts[i] > cuts[i - 1], 'monotonic');\n"
                "const ideal = [1, 2, 3].map((k) => Math.round((solution.TOTAL_FRAMES * k) / "
                + str(scene_count) + "));\n"
                "for (let i = 0; i < cuts.length; i++)\n"
                "  assert.ok(Math.abs(cuts[i] - ideal[i]) <= 3, 'error <= 3 frames');\n")
            expected = (f"Cuts {snapped} snapped from ideal {ideal} onto the "
                        f"MEASURED grid ({round(bpm, 2)} bpm real vs {nominal} "
                        f"nominal; max grid drift {drift_max} frames), every cut "
                        "within the 3-frame acceptance window, ties to the "
                        "earlier beat.")
            explain = _explain(
                "Storyboard AFTER the grid is accepted (motion-craft flow).",
                "Ideal evenly spaced cuts snap to the measured onsets; the "
                "nominal bpm grid is NOT the audio's grid (tempo drift).",
                ["measure first, storyboard second",
                 "tie -> earlier beat keeps cuts deterministic",
                 "error budget: 3 frames is the acceptance gate"],
                "O(cuts * beats)", "O(beats)",
                ["cut exactly between beats", "tempo drift vs nominal grid",
                 "cut beyond the last beat"])
            bugs = {
                "nominal_grid": lambda fl: {
                    **fl, "solution.ts": fl["solution.ts"].replace(
                        "cuts.push(snapToBeat(ideal, beats));",
                        "const step = Math.round((60 / NOMINAL_BPM) * FPS);\n"
                        "        cuts.push(step * Math.round(ideal / step));")},
                "tie_flip": lambda fl: {
                    **fl, "solution.ts": fl["solution.ts"].replace(
                        "if (Math.abs(b - frame) < Math.abs(best - frame)) best = b;",
                        "if (Math.abs(b - frame) <= Math.abs(best - frame)) best = b;")},
            }
            # guarantee the exact-value test distinguishes correct vs nominal grid
            step_nom0 = 60.0 / nominal * 24
            nom_grid0 = [round(k * step_nom0) for k in range(int(total / step_nom0) + 1)]
            nominal_snapped = [min(nom_grid0, key=lambda g: (abs(g - c), g))
                               for c in ideal]
            if nominal_snapped == snapped:
                return None
            return _ts_candidate(
                self, rng, code=code, tests=tests, expected=expected,
                explain=explain, bugs=bugs, variant=kind,
                tags_extra=["beat_grid"],
                notes_extra={"bug_for_viol": {"nominal_grid": "nominal_grid"}})

        # grid_check
        step_nom = 60.0 / nominal * 24
        nom = [round(k * step_nom) for k in range(int(total / step_nom) + 1)]
        drifts = sorted(abs(min(nom, key=lambda g: abs(g - b)) - b)
                        for b in beat_frames)
        max_drift = drifts[-1]
        half = len(beat_frames) // 2
        early = max(abs(min(nom, key=lambda g: abs(g - b)) - b)
                    for b in beat_frames[:half])
        late = max(abs(min(nom, key=lambda g: abs(g - b)) - b)
                   for b in beat_frames[half:])
        if not (late > early):
            return None
        code = (
            "/**\n"
            " * Drift audit: how far does the NOMINAL bpm grid wander from the\n"
            " * MEASURED beat frames? Justifies measuring the grid before the\n"
            " * storyboard. Returns the max |measured - nominal| in frames.\n"
            " */\n"
            f"export const NOMINAL_BPM = {nominal};\n"
            "export const FPS = 24;\n"
            f"export const BEAT_FRAMES: readonly number[] = "
            + json.dumps(beat_frames) + ";\n\n"
            "export function nominalGrid(totalFrames: number, bpm: number,\n"
            "                            fps: number): number[] {\n"
            "  const step = (60 / bpm) * fps;\n"
            "  const out: number[] = [];\n"
            "  for (let k = 0; k * step <= totalFrames; k++) out.push(Math.round(k * step));\n"
            "  return out;\n"
            "}\n\n"
            "export function gridDrift(beats: readonly number[], totalFrames: number,\n"
            "                          bpm: number, fps: number): number {\n"
            "  const grid = nominalGrid(totalFrames, bpm, fps);\n"
            "  let worst = 0;\n"
            "  for (const b of beats) {\n"
            "    let best = Infinity;\n"
            "    for (const g of grid) {\n"
            "      const d = Math.abs(g - b);\n"
            "      if (d < best) best = d;\n"
            "    }\n"
            "    if (best > worst) worst = best;\n"
            "  }\n"
            "  return worst;\n"
            "}\n\n"
            "export function withinAcceptance(drift: number, k = 3): boolean {\n"
            "  return drift <= k;\n"
            "}\n")
            # note: withinAcceptance(>3) must be FALSE for this track
        tests = _wrap_tests(
            f"assert.strictEqual(solution.gridDrift(solution.BEAT_FRAMES, "
            f"{total}, solution.NOMINAL_BPM, 24), {max_drift});\n"
            f"assert.strictEqual(solution.withinAcceptance({max_drift}), false, "
            f"'drift {max_drift} > 3: the nominal grid is NOT acceptable');\n"
            "assert.strictEqual(solution.withinAcceptance(3), true, 'boundary: 3 is acceptable');\n"
            "assert.strictEqual(solution.withinAcceptance(2), true);\n"
            f"assert.strictEqual(solution.nominalGrid({total}, {nominal}, 24).length > 5, true);\n")
        expected = (f"gridDrift reports {max_drift} frames max deviation between "
                    f"the measured grid ({round(bpm, 2)} bpm) and the nominal "
                    f"{nominal} bpm grid - outside the 3-frame acceptance, and "
                    f"the drift grows over time (early half {early}, late half "
                    f"{late}).")
        explain = _explain(
            "Why the grid is measured: nominal bpm drifts in real audio.",
            "Nearest nominal tick per measured beat; the max deviation decides "
            "acceptance (<= 3 frames).",
            ["drift grows with time - early frames hide it",
             "acceptance is a hard gate, not an average",
             "the measured grid is the single source of truth"],
            "O(beats * grid)", "O(grid)",
            ["drift exactly at tolerance", "monotone grids (no drift)",
             "beat beyond the nominal grid"])
        bugs = {
            "no_abs": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "const d = Math.abs(g - b);", "const d = g - b;")},
            "prefix_cap": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "for (const b of beats) {\n    let best = Infinity;",
                    "for (const b of beats.slice(0, 8)) {\n    let best = Infinity;")},
            "acceptance_flip": lambda fl: {
                **fl, "solution.ts": fl["solution.ts"].replace(
                    "return drift <= k;", "return drift < k;")},
        }
        return _ts_candidate(
            self, rng, code=code, tests=tests, expected=expected,
            explain=explain, bugs=bugs, variant=kind,
            tags_extra=["beat_grid"])

    def make_buggy(self, rng: random.Random):
        cand = self.generate(rng)
        if cand is None:
            return None
        return make_buggy_ts(self, cand, rng)


register(globals(), MediaTSBeatGridFamily)
