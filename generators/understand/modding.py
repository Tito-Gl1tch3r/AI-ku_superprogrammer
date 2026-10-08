"""Universal-modder understand builders: route selection, oracle gotchas,
evidence levels.

These teach the modding METHODOLOGY rather than a single implementation:
- mod_route_selection: from recon evidence to a safe route decision
  (refuse > loader-api > data > managed-patch > native-hook).
- mod_oracle_gotcha: symptom -> cause -> fix chains for broken oracles
  (frozen captures, t+1 frame semantics, fake-host overreach, golden
  sweeps that cannot fail, screenshots nobody opens).
- mod_evidence_levels: label claims by what actually backs them and flag
  claims that look like proof but are not.

All ground truth is authored alongside a machine-checked reference table
(route ladder re-derived; hashes recomputed; labels validated against the
closed vocabulary) so the pipeline can verify consistency.
"""
from __future__ import annotations

import hashlib
import random

from ..core import UnderstandCandidate
from .builder import _mk

GAME = "AI-ku_superprogrammer_game_engineering"

ROUTE_LADDER = ("refuse-online > loader-api > data > managed-patch > "
                "native-hook")

_ONLINE_STRINGS = ["OnlineSubsystemSteam", "EOS_SDK", "PlayFab"]


def _route_decide(engine: str, loader, anti_cheat: str, online: bool) -> str:
    """Reference route ladder (mirrors game_engine_recon's decision table)."""
    if anti_cheat != "none" and online:
        return "refuse-online"
    if loader is not None:
        return "loader-api"
    if engine in ("godot", "gamemaker", "java"):
        return "data"
    if engine in ("unity-mono", "xna-fna"):
        return "managed-patch"
    return "native-hook"


# ---------------------------------------------------------- route selection
_ROUTE_SCENARIOS = [
    ("godot", None, "none", False, "reskin the sprites and rebalance stats",
     "the .pck data formats are the whole interface; no loader is needed "
     "for content-only changes"),
    ("godot", "bepinex", "none", False, "a custom skill tree",
     "a community loader is already installed, so hook its API instead of "
     "repacking data by hand"),
    ("unity-mono", None, "eac", False, "a quality-of-life HUD tweak",
     "offline single-player with EasyAntiCheat present is fine, but with "
     "no loader the managed assemblies must be patched directly"),
    ("xna-fna", "tmodloader", "none", False, "homing weapons and a boss",
     "tModLoader exposes ModItem/ModNPC hooks, the cheapest route that "
     "reaches the idea"),
    ("gamemaker", None, "none", False, "port the sprites and room layouts",
     "data.win containers are well understood; a converter beats any "
     "code patch for asset-only work"),
    ("unity-il2cpp", None, "none", False, "a trainer for offline play",
     "IL2CPP has no managed assembly to patch; dump metadata, then hook "
     "the native methods"),
    ("unreal", "ue4ss", "none", True, "an overlay HUD",
     "UE4SS provides Lua hooks; online play is irrelevant here because "
     "the anti-cheat rule only gates anti-cheat-protected clients"),
    ("java", "fabric", "none", False, "new biomes and blocks",
     "Fabric's loader API is the community route; content packs load "
     "without touching the jar"),
    ("unity-mono", "smapi", "battleye", True, "a single-player skin swap",
     "BattlEye protects an online client: the hard rules forbid touching "
     "it even for cosmetic single-player work"),
]


def build_mod_route_selection(rng: random.Random):
    engine, loader, ac, online, idea, why = rng.choice(_ROUTE_SCENARIOS)
    route = _route_decide(engine, loader, ac, online)
    ac_evidence = ("no anti-cheat files in the manifest" if ac == "none"
                   else f"{ac} service files detected in the install")
    online_evidence = ("no online-subsystem strings" if not online else
                       f"online-subsystem strings present "
                       f"({rng.choice(_ONLINE_STRINGS)})")
    loader_evidence = ("no community loader installed" if loader is None
                       else f"loader detected: {loader}")
    question = (
        "You are the modder. Recon evidence for a SYNTHETIC install "
        "(pipeline-generated, no real game): engine fingerprint "
        f"'{engine}', {loader_evidence}, {ac_evidence}, {online_evidence}. "
        f"The user's idea: {idea}. Which route from the ladder "
        f"({ROUTE_LADDER}) do you take, and what do you refuse to do? "
        "Walk the decision table explicitly and name the safety rule that "
        "binds you.")
    if route == "refuse-online":
        answer = (
            f"Decision: refuse to mod this client ({route}).\n"
            f"1. Evidence: engine {engine}, loader {loader or 'none'}, "
            f"anti-cheat {ac}, online {online}.\n"
            f"2. The refuse rule fires first on the ladder: anti-cheat "
            f"AND online together means the client is protected in the "
            f"mode the user actually plays.\n"
            f"3. Offer what is allowed instead: official offline launch "
            f"options, private servers the user runs, or the game's own "
            f"tooling (workshop, creative editors).\n"
            f"4. Hard rule: never inject into an anti-cheat-protected "
            f"online client, never write cheats against other players, "
            f"never bypass the check - add the official app or use the "
            f"offline flag instead of patching it.")
    else:
        answer = (
            f"Decision: {route}.\n"
            f"1. Evidence: engine {engine}, loader {loader or 'none'}, "
            f"anti-cheat {ac}, online {online}.\n"
            f"2. Rule walk on the ladder ({ROUTE_LADDER}): the refuse rule "
            f"does not fire ({ac} anti-cheat"
            f"{'' if ac != 'none' else ''}"
            f"{' with ' if ac != 'none' else ' and '}offline-only play), "
            f"then {why}.\n"
            f"3. Before building: snapshot the saves, write the chosen "
            f"route and reason into MODLOG.md, and prove one vertical "
            f"slice in the real game with placeholder art.\n"
            f"4. Verification belongs to an oracle (round trip, log "
            f"lines, a screenshot you actually look at), not to reading "
            f"the code twice.")
    key_points = ["search the shared knowledge base before recon",
                  "the refuse rule precedes every other route",
                  "a loader always beats manual patching when present",
                  "route + reason go into MODLOG.md before any code"]
    artifacts = {"engine": engine, "loader": loader, "anti_cheat": ac,
                 "online": online, "route": route}
    return _mk(
        rng, "mod_route_selection", "python", "mod_route_selection",
        "engineering", "intermediate", question=question, answer=answer,
        artifacts=artifacts, key_points=key_points,
        verify_method="executed",
        verify_notes={"route_ladder_check": True,
                      "reference_route": _route_decide(engine, loader, ac,
                                                       online)},
        tags=["game", "modding", "recon", "safety"],
        variant=f"route|{engine}|{loader}|{ac}|{int(online)}",
        context=("Methodology: the universal-modder game-recon skill "
                 "(recon, route ladder, hard rules)."),
        dataset_hint=GAME)


# ------------------------------------------------------------ oracle gotchas
def _gotcha_frozen_capture(rng: random.Random):
    frame = bytes(rng.randrange(256) for _ in range(64))
    sha = hashlib.sha256(frame).hexdigest()
    cpu = round(rng.uniform(6.0, 9.0), 1)
    wall = 5.0
    question = (
        "Your screenshot oracle froze and kept answering. Three captures "
        f"taken minutes apart are byte-identical (SHA-256 {sha[:16]}...), "
        f"yet the process is demonstrably rendering ({cpu} s of CPU time "
        f"per {wall} s of wall clock) and the frames look plausible. The "
        "shader under test IS running. Diagnose symptom -> cause -> fix "
        "and state the protocol that would have caught this before you "
        "trusted the oracle.")
    answer = (
        "Symptom: the oracle returns confident, plausible-looking frames "
        "that have not changed; conclusions drawn from it are inverted.\n"
        "Cause: once the swapchain goes through post-processing with "
        "independent flip, the capture API stops tracking the window and "
        "replays its last composed frame - the oracle is dead, not the "
        "shader.\n"
        "Fix: capture from inside the measured thing (the game's own "
        "screenshot path writes the post-processed frame), and re-enable "
        "or bypass the capture path.\n"
        "Protocol: prove the oracle is live before trusting it - take two "
        "captures a second apart and compare hashes; if they match while "
        "the scene is animating (and the process is burning CPU, so a "
        "static scene is not the excuse), the oracle is dead.")
    artifacts = {"capture_sha_t0": sha, "capture_sha_t1": sha,
                 "captures_identical": True, "cpu_time_s": cpu,
                 "wall_time_s": wall, "oracle_frozen": True}
    return question, answer, artifacts, "frozen_capture"


def _gotcha_frame_off_by_one(rng: random.Random):
    t = rng.randrange(3, 9)
    question = (
        "A ported enemy AI is validated by replaying a recorded trace, "
        "but the replay diverges from frame "
        f"{t} on every variable at once. The port's code matches the "
        "decompiled logic line by line, and the recorder's timestamps "
        "show the game polls input after the physics update. The oracle "
        "script, however, feeds the action recorded at frame "
        f"{t} into the sim's frame {t} and reads the camera of the frame "
        "being prepared. What is wrong, and what is the fix?")
    answer = (
        "Symptom: the trace replay diverges everywhere from one frame "
        "onward despite line-by-line correct code.\n"
        "Cause: off-by-one frame semantics. The engine applies the action "
        f"observed on frame {t} during frame {t + 1} (input is polled "
        "after physics), and the oracle feeds it one frame early while "
        "reading the camera for the frame being prepared - so the oracle "
        "tests the wrong frame.\n"
        "Fix: shift the action application one frame forward in the "
        "oracle (or record input aligned with the poll point), then "
        "measure with a deliberate one-action test before trusting the "
        "replay again.\n"
        "Gotcha class: oracles that test the wrong frame; the sim and the "
        "engine can both be correct while the comparison is misaligned.")
    artifacts = {"action_frame": t, "effective_frame": t + 1,
                 "divergence_mode": "off_by_one_frame", "oracle_live": True}
    return question, answer, artifacts, "frame_off_by_one"


def _gotcha_fake_host(rng: random.Random):
    question = (
        "A game-inside-game bridge is fully green against your fake host: "
        "known geometry renders, poses arrive, collision feeds back. The "
        "moment it runs inside the real host game, overlays disappear "
        "whenever the pause menu opens and the guest camera drifts during "
        "idle cinematics. The README says 'verified'. Which evidence "
        "level did you actually earn, and what is the fix?")
    answer = (
        "Symptom: green fake-host results, broken real-game behaviour "
        "(pause menus, idle cameras, window focus - things the fake "
        "cannot model).\n"
        "Cause: 'works in the fake host' is a synthetic test, not a real "
        "run; the evidence level earned so far is synthetic_test, and "
        "calling it verified in the README overstates it.\n"
        "Fix: keep the fake host for fast iteration, but gate the claim "
        "on a scripted real-game run (launch -> menus -> scene -> check) "
        "with the log and a screenshot you actually looked at; label the "
        "README claim with the exact evidence level and what it does not "
        "cover.\n"
        "Rule: only a real run on the real build supports 'working'.")
    artifacts = {"fake_host_pass": True, "real_run_done": False,
                 "claimed_level": "synthetic_test",
                 "required_level": "real_run"}
    return question, answer, artifacts, "fake_host_overreach"


def _gotcha_golden_sweep(rng: random.Random):
    skipped = rng.randrange(4, 12)
    question = (
        "Your mod's CI sweep is green on every run, but a user reports "
        f"the addon never loads. Inspection finds {skipped} addon tests "
        "skipped with 'owned files missing' and counted as passed, plus "
        "one save-verification task that once passed with no game data "
        "present. What is the failure mode and the fix?")
    answer = (
        "Symptom: a golden sweep that cannot fail - green on every run "
        "while the shipped feature is broken.\n"
        "Cause: skipped tests counted as passes (the denominator promised "
        "coverage the checks never delivered), and a conditional test "
        "that silently skips its meaningful assertion when the owned "
        "files it needs are absent.\n"
        "Fix: make skipped tests fail loudly unless the skip is declared "
        "and reported separately; assert on evidence artifacts per run "
        "(hashes, log lines) instead of exit codes alone; have a human "
        "run the real build in the real setup before calling it done.\n"
        "Rule: a test whose name promises more than it checks is a lie "
        "the pipeline will keep telling.")
    artifacts = {"skipped_tests": skipped, "counted_as": "passed",
                 "sweep_can_fail": False}
    return question, answer, artifacts, "golden_sweep"


def _gotcha_unread_screenshots(rng: random.Random):
    n = rng.randrange(3, 9)
    question = (
        f"The mod spawns a new unit; {n} screenshots were saved during "
        "development and the build was called done. A reviewer's first "
        "clip shows the unit facing left instead of right. Nobody "
        "noticed because the screenshots were never opened. What broke, "
        "and what is the cheapest fix that catches this class?")
    answer = (
        "Symptom: visual state ('does it show up at all, facing the "
        "right way, correct pivot') was never actually checked despite "
        "artifacts existing.\n"
        "Cause: screenshots nobody looks at - saving an artifact is not "
        "an oracle; the check never happened.\n"
        f"Fix: after every visual change, open a scaled copy of the "
        f"capture (a downscaled view is cheap and catches facing, "
        f"pivot and layering); make the spawn scene repeatable (a chat "
        f"command or scenario) so the same check reruns after each "
        f"change.\n"
        "Rule: an oracle only counts when someone (or something) actually "
        "reads the evidence.")
    artifacts = {"screenshots_saved": n, "screenshots_viewed": 0,
                 "defect_class": "visual_orientation"}
    return question, answer, artifacts, "unread_screenshots"


_GOTCHAS = [_gotcha_frozen_capture, _gotcha_frame_off_by_one,
            _gotcha_fake_host, _gotcha_golden_sweep,
            _gotcha_unread_screenshots]


def build_mod_oracle_gotcha(rng: random.Random):
    question, answer, artifacts, kind = rng.choice(_GOTCHAS)(rng)
    return _mk(
        rng, "mod_oracle_gotcha", "python", "mod_oracle_gotcha",
        "engineering", "advanced", question=question, answer=answer,
        artifacts=artifacts,
        key_points=["the running game is the oracle, your reading of the "
                    "code is not",
                    "prove the oracle is live before trusting it",
                    "circuit breaker: after 3 identical failures, change "
                    "approach",
                    "write down what the oracle did NOT cover"],
        verify_method="executed",
        verify_notes={"gotcha_table_check": True, "kind": kind,
                      **({"captures_identical": True} if kind ==
                         "frozen_capture" else {})},
        tags=["game", "modding", "oracles", "debugging"],
        variant=f"gotcha|{kind}",
        context=("Methodology: the universal-modder oracles knowledge note "
                 "(round trip, trace replay, scripted scenes, evidence "
                 "levels, circuit breaker)."),
        dataset_hint=GAME)


# ------------------------------------------------------------ evidence levels
_EVIDENCE_LEVELS = ("creator_report", "design", "source_inspection",
                    "derived_comparison", "synthetic_test", "real_run")

_EVIDENCE_POOL = [
    ("The mod's release post states it works on build 1.4.4.9.",
     "creator_report",
     "someone reports it works; nothing was run by the reporter's own "
     "hand", False),
    ("The design doc plans in-frame Vulkan compositing for v0.2.",
     "design",
     "planned work; the current build ships an overlay window instead",
     True),
    ("We read the decompiled damage routine and located the defense "
     "subtraction at the documented offset.", "source_inspection",
     "code was read; nothing was executed", False),
    ("Compared with upstream, the camera fix landed in commit 4f2e1.",
     "derived_comparison",
     "a version/fork diff, not a run", False),
    ("The bridge passes both ends against a fake host in CI.",
     "synthetic_test",
     "a test with stand-ins ran; both real games did not", True),
    ("We played three full rounds with the mod loaded on 1.21.1 and "
     "watched the log each round.", "real_run",
     "the real game ran this build and a human looked", False),
    ("The progress badge reports 80% of declared system functions "
     "implemented.", "creator_report",
     "the denominator grows as more functions are found; it is not game "
     "compatibility", True),
    ("The shipped test suite is green.", "synthetic_test",
     "a passing suite can assert almost nothing; green is not coverage",
     True),
    ("It installs cleanly on my machine.", "creator_report",
     "one tested machine is not a second machine; hardware/driver "
     "coverage is unknown", True),
    ("The headless sim bench runs 885 tests green in seconds with just "
     "the compiler.", "synthetic_test",
     "a real harness ran, but entirely outside the host game", False),
]


def build_mod_evidence_levels(rng: random.Random):
    picked = rng.sample(_EVIDENCE_POOL, 5)
    lines_q = []
    lines_a = []
    traps = 0
    for i, (claim, level, why, trap) in enumerate(picked, 1):
        lines_q.append(f"{i}. \"{claim}\"")
        label = level + (" -- LOOKS LIKE PROOF BUT ISN'T" if trap else "")
        lines_a.append(f"{i}. {label}: {why}.")
        traps += int(trap)
    assert all(lvl in _EVIDENCE_LEVELS for _, lvl, _, _ in picked)
    question = (
        "A field note (and your report to the user) must keep evidence "
        "levels apart. Label each claim below with exactly one level from "
        + ", ".join(_EVIDENCE_LEVELS) +
        " - and flag any claim that looks like proof but is not.\n"
        + "\n".join(lines_q))
    answer = (
        "Levels, claim by claim:\n" + "\n".join(lines_a) +
        f"\nOnly real_run claims support 'working' from your own work, and "
        f"only for the scenarios actually played; {traps} of the "
        f"{len(picked)} claims above are proof-shaped but do not carry "
        f"their weight.")
    artifacts = {"claims": len(picked), "trap_claims": traps,
                 "levels": sorted({lvl for _, lvl, _, _ in picked})}
    return _mk(
        rng, "mod_evidence_levels", "python", "mod_evidence_levels",
        "engineering", "intermediate", question=question, answer=answer,
        artifacts=artifacts,
        key_points=["creator report < source inspection < synthetic test "
                    "< real run",
                    "a design document is not a feature",
                    "a green test that checks little is not coverage",
                    "say what the evidence does NOT cover"],
        verify_method="executed",
        verify_notes={"evidence_level_table_check": True,
                      "vocabulary": list(_EVIDENCE_LEVELS)},
        tags=["game", "modding", "evidence", "honesty"],
        variant="evidence|" + "|".join(sorted(
            f"{lvl}{int(trap)}" for _, lvl, _, trap in picked)),
        context=("Methodology: the universal-modder evidence-levels note "
                 "(reports, source reading, proposals and real runs)."),
        dataset_hint=GAME)
