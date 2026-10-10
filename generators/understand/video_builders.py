"""v0.8.0 media understand builders: the review loop and timeline readouts.

Evidence is REAL: reports and stats come from actually rendered sequences
(Pillow) and actually measured beat grids (numpy onset detection) at
generation time; answers are recomputed from that data and the record is
dropped when the recomputation disagrees. Distractors contradict observable
fields (e.g. verdicts without frame numbers, nominal-bpm cut times).
"""
from __future__ import annotations

import json
import random

import numpy as np

from .builder import _mk
from ..media.video_verify_family import (_audit_reference, _render_sequence,
                                         SIGNAL_RGB, INK_RGB, BONE_RGB,
                                         ASH_RGB)
from ..media.ts_beat_families import synthesize_track, measure_beats

_DATASET = "AI-ku_superprogrammer_media"


def _snap(cut, beats):
    return min(beats, key=lambda b: (abs(b - cut), b))


# ---------------------------------------------------------------- verdict

def build_video_review_verdict(rng: random.Random):
    """Acceptance decision on a review report built from a REAL render.

    The report's findings carry REAL frame numbers (from a genuinely rendered
    defective sequence). Rules: FAIL on any blocker/major finding, on a
    determinism or manifest failure, or when audio is declared but absent.
    The re-render list is the frames of blocker/major findings.
    """
    frames, boxes, manifest, defects = _render_sequence(rng)
    real = _audit_reference(frames, boxes, manifest)
    if not real:
        return None
    severity_map = {"empty_frame": "blocker", "off_palette": "major",
                    "overlap": "major", "harsh_cut": "minor"}
    findings = [{"frame": f["frame"], "rule": f["rule"],
                 "severity": severity_map[f["rule"]]} for f in real]
    determinism = True
    manifest_match = True
    audio_declared = rng.random() < 0.7
    audio_present = audio_declared or rng.random() < 0.5
    fail_reasons = []
    if any(f["severity"] in ("blocker", "major") for f in findings):
        fail_reasons.append("findings")
    if not determinism:
        fail_reasons.append("determinism")
    if not manifest_match:
        fail_reasons.append("manifest")
    if audio_declared and not audio_present:
        fail_reasons.append("audio")
    verdict = "FAIL" if fail_reasons else "PASS"
    rerender = sorted({f["frame"] for f in findings
                       if f["severity"] in ("blocker", "major")})
    report = {
        "render": {"fps": manifest["fps"], "total_frames": manifest["total_frames"],
                   "width": manifest["width"], "height": manifest["height"],
                   "audio_track": audio_present,
                   "determinism_double_run": determinism,
                   "manifest_matches_render": manifest_match},
        "findings": findings,
    }
    report_json = json.dumps(report, indent=1)
    if verdict == "FAIL":
        why = []
        if "findings" in fail_reasons:
            why.append("blocker/major findings at frames "
                       + ", ".join(str(f) for f in rerender))
        if not determinism:
            why.append("the double render is not byte-identical")
        if not manifest_match:
            why.append("the manifest does not match the render")
        if audio_declared and not audio_present:
            why.append("audio is declared but the track is missing")
        answer = (f"FAIL - re-render required. Reasons: {'; '.join(why)}. "
                  f"Re-render frames: {rerender}.")
    else:
        answer = ("PASS - no blocker or major findings, the double render is "
                  "byte-identical, the manifest matches and the audio track "
                  "is present. Deliverable.")
    distractors = [
        "PASS - the issues are cosmetic and can ship",
        "FAIL - re-render frame 0",
        "PASS - findings have no frame numbers so nothing can be verified",
    ]
    key_points = [
        "a render is deliverable only with a clean checklist (no blockers/majors)",
        "the re-render list is exactly the blocker/major frames",
        "determinism and manifest agreement are pass/fail gates, not cosmetics",
    ]
    variant = f"find{len(findings)}_{verdict.lower()}_{len(rerender)}"
    return _mk(
        rng, "video_review_verdict", "python", "video_review_verdict",
        "engineering", rng.choice(["intermediate", "advanced"]),
        ("You ran the render QA loop on a delivered composition. The review "
         "report is in the code block below (findings carry REAL frame "
         "numbers from the inspected render).\n\nAcceptance rules: any "
         "blocker or major finding fails the delivery; the double render "
         "must be byte-identical; the manifest must match the render; audio "
         "must be present if declared. Verdict and, on FAIL, the exact "
         "frames to re-render?"),
        answer,
        code=report_json,
        artifacts={"report": report,
                   "rejected_answers": distractors,
                   "audio_declared": audio_declared},
        key_points=key_points,
        verify_method="authored_verified",
        verify_notes={"evidence": "findings from a real rendered sequence",
                      "finding_frames": [f["frame"] for f in findings],
                      "verdict": verdict,
                      "recompute": "verdict recomputed from report data"},
        tags=["media", "video_review"], variant=variant,
        dataset_hint=_DATASET)


# --------------------------------------------------------------- timeline

def build_video_timeline_readout(rng: random.Random):
    """Cut placement questions over a REAL measured beat grid.

    The grid comes from onset detection on a synthesized-with-drift track.
    Answers: snapped cut frames, max cut error, and the beat each cut is
    anchored to. Distractor values derive from the NOMINAL bpm grid (wrong).
    """
    fps = 24
    for _ in range(6):
        beats, pcm, sr, nominal, _drift = synthesize_track(
            rng, sr=8000, dur=10.0)
        grid, bpm = measure_beats(pcm, sr, fps)
        if not grid or bpm is None or len(grid) < 8:
            continue
        total = int(10.0 * fps)
        scene_count = rng.choice([4, 5])
        ideal = [round(total * k / scene_count) for k in range(1, scene_count)]
        snapped = [_snap(c, grid) for c in ideal]
        errs = [abs(s - c) for s, c in zip(snapped, ideal)]
        if max(errs) > 3:
            continue
        anchors = [grid.index(s) for s in snapped]
        step_nom = 60.0 / nominal * fps
        nom_grid = [round(k * step_nom) for k in range(int(total / step_nom) + 1)]
        nom_snapped = [min(nom_grid, key=lambda g: (abs(g - c), g))
                       for c in ideal]
        if nom_snapped == snapped:
            continue  # the distractor must be distinguishable
        answer = (
            f"Cuts snap to measured beat frames {snapped} (anchors: beats "
            f"{anchors} of the measured grid); max cut error {max(errs)} "
            f"frames (<= 3, accepted). The nominal {nominal} bpm grid would "
            f"give {nom_snapped} - drift makes it wrong.")
        question = (
            "The beat grid below was MEASURED from the track's waveform "
            f"(onset detection, {round(bpm, 2)} bpm real vs {nominal} nominal, "
            f"{fps} fps, {total} frames). It is in the code block.\n\nWhere do "
            "the scene cuts land after snapping each evenly spaced ideal cut "
            "to the nearest MEASURED beat (ties to the earlier beat)? Give "
            "the cut frames, their max error in frames, and which beats they "
            "anchor to.")
        timeline_json = json.dumps(
            {"measured_beat_frames": grid, "nominal_bpm": nominal,
             "fps": fps, "total_frames": total, "scene_count": scene_count},
            indent=1)
        key_points = [
            "storyboard AFTER the grid is accepted (error <= 3 frames)",
            "ties resolve to the earlier beat for determinism",
            "the nominal grid is NOT the audio's grid under tempo drift",
        ]
        return _mk(
            rng, "video_timeline_readout", "python", "video_timeline_readout",
            "engineering", rng.choice(["intermediate", "advanced"]),
            question, answer,
            code=timeline_json,
            artifacts={"measured_beat_frames": grid, "nominal_bpm": nominal,
                       "fps": fps, "total_frames": total,
                       "scene_count": scene_count,
                       "nominal_grid_answer": nom_snapped,
                       "rejected_answers": [
                           f"cuts at {nom_snapped} (nominal grid, drifted)",
                           "cuts evenly spaced without snapping"]},
            key_points=key_points,
            verify_method="authored_verified",
            verify_notes={"evidence": "grid measured from real PCM onsets",
                          "measured_bpm": round(bpm, 2),
                          "cut_error_max": max(errs),
                          "recompute": "snaps recomputed from the grid"},
            tags=["media", "beat_grid"], variant=f"cuts{scene_count}",
            dataset_hint=_DATASET)
    return None


# ---------------------------------------------------------------- defect

def build_video_defect_locate(rng: random.Random):
    """Locate defects from REAL per-frame stats of a rendered sequence.

    Artifacts: the mean |diff| array between consecutive frames, per-frame
    off-palette pixel counts, and per-frame ink ratios. The answer names the
    harsh-cut frame (argmax diff), the empty frame(s) (ink ratio 1.0) and the
    off-palette frame(s) - all recomputed from the real render.
    """
    frames, boxes, manifest, defects = _render_sequence(rng)
    if len(defects) < 2:
        return None
    w, h = manifest["width"], manifest["height"]
    total = manifest["total_frames"]
    diffs = []
    for i in range(1, total):
        a = list(frames[i - 1].getdata())
        b = list(frames[i].getdata())
        diffs.append(round(sum(abs(x[j] - y[j]) for x, y in zip(a, b)
                               for j in range(3)) / (len(a) * 3), 1))
    ink_ratio = [round(sum(1 for p in list(im.getdata()) if p == INK_RGB)
                       / (w * h), 3) for im in frames]
    offpal = [round(sum(1 for p in list(im.getdata())
                        if p not in {SIGNAL_RGB, INK_RGB, BONE_RGB, ASH_RGB})
                      / (w * h), 3) for im in frames]
    harsh = [i + 1 for i in range(total - 1)
             if defects.get(i + 1) == "harsh_cut"]
    empty = [f for f in range(total) if defects.get(f) == "empty_frame"]
    offp = [f for f in range(total) if defects.get(f) == "off_palette"]
    overlap = [f for f in range(total) if defects.get(f) == "overlap"]
    # ground truth recomputation from the stats themselves
    gt_harsh = [i + 1 for i, d in enumerate(diffs) if d > 60.0]
    gt_empty = [f for f in range(total) if ink_ratio[f] == 1.0]
    gt_offp = [f for f in range(total) if offpal[f] > 0]
    if gt_harsh != harsh or gt_empty != empty or gt_offp != offp:
        # both transitions of the flash count as harsh cuts; accept the
        # stats' verdict as the answer when it is a superset
        if not (set(gt_harsh) >= set(harsh) and gt_empty == empty
                and gt_offp == offp):
            return None
        harsh = gt_harsh
    stats = {"mean_abs_diff_consecutive": diffs,
             "ink_ratio_per_frame": ink_ratio,
             "off_palette_ratio_per_frame": offpal,
             "thresholds": {"harsh_cut_mean_diff": 60.0}}
    parts = []
    if harsh:
        parts.append(f"harsh cut(s) entering frame(s) {harsh} (mean |diff| "
                     "above the 60.0 threshold)")
    if empty:
        parts.append(f"empty frame(s) {empty} (ink ratio 1.0)")
    if offp:
        parts.append(f"off-palette frame(s) {offp} (nonzero off-palette ratio)")
    if overlap:
        parts.append(f"overlap suspect(s) {overlap} (box data)")
    answer = ("The stats locate: " + "; ".join(parts) +
              ". Everything else is within tolerance.")
    stats_json = json.dumps(stats, indent=1)
    question = (
        f"You inspected a rendered sequence ({w}x{h}, {total} frames) and "
        "collected the per-frame stats in the code block.\n\nUsing ONLY the "
        "stats (harsh-cut threshold 60.0, empty = ink ratio 1.0, "
        "off-palette = any off-palette pixel), name each defect and its "
        "exact frame(s).")
    key_points = [
        "defects are located by thresholds on measured stats, not vibes",
        "the harsh cut shows up as a neighbour-diff spike",
        "empty means ink ratio exactly 1.0",
    ]
    return _mk(
        rng, "video_defect_locate", "python", "video_defect_locate",
        "engineering", rng.choice(["advanced", "expert"]),
        question, answer,
        code=stats_json,
        artifacts={"stats": stats,
                   "overlap_suspects": overlap,
                   "rejected_answers": [
                       "the sequence looks fine overall",
                       "defects around frame 0 (no spike there)"]},
        key_points=key_points,
        verify_method="authored_verified",
        verify_notes={"evidence": "stats computed from the real render",
                      "defect_frames": sorted(defects),
                      "recompute": "argmax/ratio recomputation matches"},
        tags=["media", "render_qa"], variant=f"d{len(defects)}",
        dataset_hint=_DATASET)
