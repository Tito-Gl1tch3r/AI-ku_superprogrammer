"""Module 05 (agent persistence) understand builders.

These records teach the reading side of objective discipline: decomposing a
compound objective into its full stage graph (and recognising the FINAL
deliverable), autopsying an agent transcript that walked away from a
long-running job, and deciding from real evidence whether a job may be
declared complete. Every instance is generated from a seeded structural
model (stage count, gates, plan counters, artifact states, transcript
shape), and the answer text is produced from that same model so question,
artifacts and answer can never disagree. The builder returns None whenever
a model invariant would be violated.
"""
from __future__ import annotations

import random

from .builder import _mk

_DATASET = "AI-ku_superprogrammer_agent_ops"


# ------------------------------------------------------------- goal decomposition

def _goal_model(rng: random.Random):
    """Seeded structural model of a compound objective (2-4 stages)."""
    key = rng.choice(("live_unit", "model_rollout", "backup_proof",
                      "schema_cutover", "release_mirror", "cache_warm",
                      "dataset_export"))
    sub = rng.choice(("", "sub", "v2", "bak", "tmp"))
    unit = {"live_unit": "live unit mounted at /media/agent/LIVE%s" % sub.upper(),
            "model_rollout": "staging model in the training queue",
            "backup_proof": "project directory on the NAS share",
            "schema_cutover": "orders table on the primary database",
            "release_mirror": "release artefacts for tag v2",
            "cache_warm": "edge cache nodes",
            "dataset_export": "export pipeline for the analytics dataset",
            }[key]
    if key == "live_unit":
        first = ("update the live unit with the new packages",
                 "the update log ends successfully and the package manifest "
                 "on the unit matches the requested set")
        finals = [("build a bootable ISO image of the whole updated unit",
                   "the ISO file exists and reads back byte-identical to the "
                   "updated tree"),
                  ("build a bootable ISO image of the whole updated unit",
                   "the ISO parses with an independent reader and every "
                   "checksummed file matches")]
        watch = "the update process itself, for errors, until it terminates"
    elif key == "model_rollout":
        first = ("run the training job on the full dataset",
                 "the job exits 0, the final checkpoint is written and the "
                 "metric summary is logged")
        finals = [("deploy the trained checkpoint behind the serving endpoint",
                   "the endpoint answers a smoke request with the new model "
                   "version"),
                  ("deploy the trained checkpoint behind the serving endpoint",
                   "the endpoint health probe passes and the served version "
                   "hash matches the checkpoint")]
        watch = "the training job, for stalls and silent deaths, until it ends"
    elif key == "backup_proof":
        first = ("back up the project directory to the NAS",
                 "the backup job exits 0 and every file hash on the NAS "
                 "matches the source manifest")
        finals = [("restore the backup into a scratch directory and diff it "
                   "against the source",
                   "the recursive diff between the restored copy and the "
                   "source is empty"),
                  ("restore the backup into a scratch directory and diff it "
                   "against the source",
                   "every restored file hash equals the source manifest")]
        watch = "the backup job, for errors, until it terminates"
    elif key == "schema_cutover":
        first = ("migrate the orders table to the new schema",
                 "the migration tool exits 0 and row counts plus checksums "
                 "match the pre-migration audit")
        finals = [("switch the service to the migrated schema",
                   "health checks pass against the new schema under real "
                   "traffic"),
                  ("switch the service to the migrated schema",
                   "the service serves real requests from the new schema "
                   "with error rates at baseline")]
        watch = "the migration job, for partial failures, until it ends"
    elif key == "release_mirror":
        first = ("build every artefact for the release tag",
                 "the build exits 0 and every expected artefact exists with "
                 "its checksum recorded")
        finals = [("publish the artefacts to the download mirror",
                   "the mirror listing shows every artefact and each "
                   "downloaded copy hash-matches the build output"),
                  ("publish the artefacts to the download mirror",
                   "a clean download of every artefact verifies against the "
                   "build checksums")]
        watch = "the build, for per-target failures, until it finishes"
    elif key == "cache_warm":
        first = ("warm the edge cache nodes with the new content set",
                 "every node reports the full content set with 200 responses "
                 "on the probe URLs")
        finals = [("flip the traffic router to the warmed nodes",
                   "the router health checks pass and the old nodes drain "
                   "with zero client errors"),
                  ("flip the traffic router to the warmed nodes",
                   "real traffic serves from the warm nodes with cache-hit "
                   "rates at the expected floor")]
        watch = "the warmup job, for per-node failures, until it completes"
    else:
        first = ("run the export pipeline on the analytics dataset",
                 "the pipeline exits 0 and the export manifest lists every "
                 "partition with matching row counts")
        finals = [("load the export into the warehouse and reconcile it",
                   "the warehouse row counts and checksums reconcile against "
                   "the export manifest"),
                  ("load the export into the warehouse and reconcile it",
                   "a sample audit query returns zero discrepancies")]
        watch = "the export pipeline, for partition failures, until it ends"

    stages = [first]
    if rng.random() < 0.55:  # optional guard stage inserted in the middle
        guard = rng.choice((
            ("snapshot the current state before touching anything",
             "the snapshot completes and its checksum is recorded"),
            ("freeze writes with a maintenance banner",
             "the banner is live and write endpoints return the maintenance "
             "notice"),
            ("record a rollback plan with the current versions",
             "the rollback plan file exists and lists every component")))
        stages.append(guard)
    stages.append(rng.choice(finals))

    caps = rng.random() < 0.5
    task = _goal_task_text(key, unit, stages[0][0], stages[-1][0], caps)
    return key, unit, stages, watch, task


def _goal_task_text(key, unit, first_desc, final_desc, caps):
    """Full objective text: intro + stage 1 + transition + FINAL action."""
    final_clause = {
        "build a bootable ISO image of the whole updated unit":
            ("MAKE AN ISO OF THE WHOLE UNIT",
             "build an ISO image of the whole updated unit"),
        "deploy the trained checkpoint behind the serving endpoint":
            ("DEPLOY IT BEHIND THE SERVING ENDPOINT",
             "deploy it behind the serving endpoint"),
        "restore the backup into a scratch directory and diff it "
        "against the source":
            ("PROVE THE BACKUP WORKS: RESTORE IT TO A SCRATCH DIR AND DIFF",
             "prove it works by restoring to a scratch dir and diffing"),
        "switch the service to the migrated schema":
            ("SWITCH THE SERVICE TO THE NEW SCHEMA",
             "switch the service to the new schema"),
        "publish the artefacts to the download mirror":
            ("PUBLISH THEM TO THE DOWNLOAD MIRROR",
             "publish them to the download mirror"),
        "flip the traffic router to the warmed nodes":
            ("FLIP THE ROUTER TO THE WARM NODES",
             "flip traffic over to the warm nodes"),
        "load the export into the warehouse and reconcile it":
            ("LOAD IT INTO THE WAREHOUSE AND RECONCILE",
             "load it into the warehouse and reconcile"),
    }[final_desc]
    watch = ("WATCH THE WHOLE THING IN CASE SOMETHING FAILS",
             "keep an eye on it the whole time, last run failed silently")
    if caps:
        intro = {
            "live_unit": "UPDATE %s WITH THE NEW PACKAGES, AND AS SOON AS "
                         "IT FINISHES" % unit.upper(),
            "model_rollout": "RUN THE TRAINING JOB ON %s, AND WHEN IT IS "
                             "DONE" % unit.upper(),
            "backup_proof": "BACK UP %s AND THEN" % unit.upper(),
            "schema_cutover": "MIGRATE %s TONIGHT; ONCE THE MIGRATION "
                              "FINISHES" % unit.upper(),
            "release_mirror": "BUILD %s AND THEN" % unit.upper(),
            "cache_warm": "WARM %s WITH THE NEW CONTENT SET, THEN" % unit.upper(),
            "dataset_export": "RUN THE EXPORT FOR %s, AND ONCE IT "
                              "FINISHES" % unit.upper(),
        }[key]
        return "%s %s. %s." % (intro, final_clause[0], watch[0])
    intro = {
        "live_unit": "update %s with the new packages, and as soon as it "
                     "finishes" % unit,
        "model_rollout": "run the training job on %s, and when it is done" % unit,
        "backup_proof": "please back up %s and then" % unit,
        "schema_cutover": "migrate %s tonight; once the migration finishes" % unit,
        "release_mirror": "build %s and then" % unit,
        "cache_warm": "warm %s with the new content set, then" % unit,
        "dataset_export": "run the export for %s, and once it finishes" % unit,
    }[key]
    return "%s %s. %s." % (intro, final_clause[1], watch[1])


def build_ops_goal_decomposition(rng: random.Random):
    """Extract the FULL stage graph of a compound objective - final step included."""
    key, unit, stages, watch, task = _goal_model(rng)
    n = len(stages)
    stage_lines = []
    for i, (desc, gate) in enumerate(stages, 1):
        stage_lines.append("%d. %s. Gate: %s." % (i, desc, gate))
    final_desc, final_gate = stages[-1]
    answer = (
        "The final deliverable is: %s - everything before it is a "
        "prerequisite. Full stage graph:\n%s\n"
        "Stage discipline: start a stage only when the previous gate holds, "
        "and keep supervising %s. The objective may be reported complete "
        "only after the last gate: %s. Stopping after stage 1 (\"%s\") "
        "would finish a prerequisite, not the task the user asked for."
        % (final_desc, "\n".join(stage_lines), watch, final_gate,
           stages[0][0]))
    question = (
        "A user hands you this compound objective:\n\n    %s\n\n"
        "Questions: (1) What is the FINAL deliverable (the thing 'done' "
        "actually means)? (2) List every stage in order with its completion "
        "gate. (3) What must you keep supervising while it runs, and what is "
        "the exact condition to report completion?" % task)
    return _mk(rng, "ops_goal_decomposition", "python",
               "ops_goal_decomposition", "automation",
               rng.choice(("intermediate", "advanced", "expert")),
               question, answer,
               context="compound-objective comprehension",
               artifacts={"task_text": task, "scenario": key,
                          "stages": n, "final_deliverable": final_desc,
                          "note": "stage graph authored from the task text; "
                                  "every gate cross-checked against it"},
               key_points=["stage 1 is a prerequisite, not the objective",
                           "the final deliverable is: " + final_desc,
                           "every stage needs its own verification gate",
                           "supervise " + watch],
               verify_method="authored_verified",
               verify_notes={"evidence": "stage graph, gates and final "
                                         "deliverable cross-checked against "
                                         "the authored task text",
                             "stages": n, "scenario": key},
               tags=["agent_ops", "objectives", "planning"],
               variant="%s|s%d" % (key, n), dataset_hint=_DATASET)


# ------------------------------------------------------------- failure autopsy

_FAILURE_CLASSES = (
    {
        "key": "monitoring_abandonment",
        "label": "monitoring abandonment",
        "desc": ("it launched a long-running job and then stopped watching "
                 "it: no polling, no progress checks, no error detection - "
                 "it simply moved on while the job could have been failing"),
        "next": ("keep supervising the job until it reaches a terminal, "
                 "verified state: poll its progress, react to failures, and "
                 "only then continue the objective"),
    },
    {
        "key": "lost_final_objective",
        "label": "loss of the complete objective",
        "desc": ("it completed the FIRST stage and reported the task done, "
                 "treating a prerequisite as the goal - the final deliverable "
                 "the user asked for was never produced"),
        "next": ("recognise stage 1 as a prerequisite and continue to the "
                 "remaining stages until the final deliverable exists and "
                 "verifies"),
    },
    {
        "key": "premature_completion",
        "label": "premature completion",
        "desc": ("it declared success from a single success signal (exit "
                 "code 0) without verifying the plan completed or the final "
                 "artifact exists and checks out"),
        "next": ("verify before reporting: plan complete, artifact present, "
                 "read back and compared; only then declare completion"),
    },
)

_JOBS = ("unit_sync.sh", "pkg_update.sh", "train_job.py", "backup_job",
         "build_all.sh", "mirror_sync", "warm_cache", "export_run")
_FINALS = ("unit.iso", "release.iso", "deploy_report.md", "restore_diff.txt",
           "mirror_manifest.json", "reconcile_report.txt")
_FILLERS = (
    "action: skim the project README while waiting",
    "action: tidy the workspace temp files",
    "note: the sandbox clock drifted 0.4s; ignoring",
    "action: re-read the second stage of the objective",
)


def _transcript(rng, cls_key, job, final, plan_n, done_k, t_base):
    """Author a truncated agent transcript exhibiting the failure class."""
    t1 = t_base
    t2 = t_base + rng.randrange(2, 9)
    t3 = t2 + rng.randrange(2, 9)
    head = [
        "[t+%02d:00] plan: 1) run %s to completion (%d planned steps)  "
        "2) produce %s" % (t_base, job, plan_n, final),
        "[t+%02d:0%d] action: launch %s (long-running)" % (t1, rng.randrange(9), job),
        "[t+%02d:%02d] action: read first progress lines of %s" % (
            t2, rng.randrange(10, 59), job),
    ]
    if rng.random() < 0.5:
        head.insert(2, "[t+%02d:%02d] %s" % (t3, rng.randrange(10, 59),
                                             rng.choice(_FILLERS)))
    if cls_key == "monitoring_abandonment":
        tail = [
            "[t+%02d:00] agent: the job is running; I'll stop here." % (t3 + 1),
            "[no further monitoring of %s occurs; final deliverable %s "
            "never checked]" % (job, final),
        ]
        bad_line = tail[0]
    elif cls_key == "lost_final_objective":
        tail = [
            "[t+12:%02d] observe: %s exited 0, all %d planned steps present"
            % (rng.randrange(10, 59), job, plan_n),
            "[t+12:%02d] agent: stage one is finished, so the task is "
            "complete. (%s was never built)" % (rng.randrange(10, 59), final),
        ]
        bad_line = tail[1]
    else:  # premature_completion
        tail = [
            "[t+%02d:%02d] observe: %s printed exit code 0 early, log shows "
            "%d of %d planned steps" % (t_base + rng.randrange(3, 6),
                                        rng.randrange(10, 59), job, done_k,
                                        plan_n),
            "[t+%02d:%02d] agent: exit code 0, everything worked. Task "
            "complete without checking %s." % (t_base + rng.randrange(6, 9),
                                               rng.randrange(10, 59), final),
        ]
        bad_line = tail[1]
    return head + tail, bad_line


def build_ops_failure_autopsy(rng: random.Random):
    """Diagnose WHY an agent transcript walked away from the objective."""
    cls = rng.choice(_FAILURE_CLASSES)
    job = rng.choice(_JOBS)
    final = rng.choice(_FINALS)
    plan_n = rng.randrange(5, 10)
    done_k = rng.randrange(2, plan_n - 1)
    t_base = rng.randrange(0, 4)
    lines, bad_line = _transcript(rng, cls["key"], job, final, plan_n,
                                  done_k, t_base)
    transcript = "\n".join(lines)
    answer = (
        "Failure class: %s. What went wrong: %s. The decisive moment is the "
        "entry \"%s\". What the agent should have done next: %s. Of the "
        "objective, stage 1 (%s, %d planned steps) was started but its "
        "verified completion is unknown from this transcript, and the final "
        "deliverable (%s) is still outstanding - the task is NOT done."
        % (cls["label"], cls["desc"], bad_line, cls["next"], job, plan_n,
           final))
    question = (
        "This is the transcript of an agent that was given a two-stage "
        "objective and stopped early. Diagnose it:\n\n%s\n\n"
        "Questions: (1) Which failure class is this: monitoring abandonment, "
        "loss of the complete objective, or premature completion? (2) Quote "
        "the transcript entry where it goes wrong. (3) What should the agent "
        "have done next, and what part of the objective is still outstanding?"
        % transcript)
    return _mk(rng, "ops_failure_autopsy", "python",
               "ops_failure_autopsy", "automation",
               rng.choice(("intermediate", "advanced", "expert")),
               question, answer,
               context="agent-transcript forensics",
               artifacts={"transcript": transcript,
                          "failure_class": cls["key"],
                          "failure_label": cls["label"],
                          "bad_entry": bad_line,
                          "job": job, "final_deliverable": final,
                          "plan_steps": plan_n, "steps_done": done_k,
                          "note": "transcript authored from the failure "
                                  "model; class and bad entry cross-checked"},
               key_points=["failure class: " + cls["label"],
                           "decisive entry: " + bad_line,
                           "the objective is not done: " + final +
                           " is still missing"],
               verify_method="authored_verified",
               verify_notes={"evidence": "failure class, decisive entry and "
                                         "outstanding deliverable verified "
                                         "against the authored transcript",
                             "class": cls["key"]},
               tags=["agent_ops", "forensics", "objectives"],
               variant="%s|p%d" % (cls["key"], plan_n),
               dataset_hint=_DATASET)


# ------------------------------------------------------------- done criteria

_FATALS = ("checksum mismatch at block", "disk full while writing",
           "worker lost connection", "upstream returned 503",
           "corrupt artifact detected", "watchdog killed the worker")
_HEX = "0123456789abcdef"


def _done_model(rng: random.Random):
    """Seeded job-log + artifact model; the verdict derives from its fields."""
    plan_n = rng.randrange(4, 10)
    exit_code = rng.choice((0, 0, 0, 1, 2, 3))
    done_written = rng.random() < 0.7
    if exit_code == 0:
        steps_done = plan_n if rng.random() < 0.6 else rng.randrange(2, plan_n)
    else:
        steps_done = rng.randrange(1, plan_n)
    reason = rng.choice(_FATALS)
    art_present = rng.random() < (0.9 if (exit_code == 0 and
                                          steps_done == plan_n) else 0.1)
    art_verified = art_present and rng.random() < 0.6
    size = rng.randrange(500, 2000) * 1024
    sha = "".join(rng.choice(_HEX) for _ in range(8)) + "..." + \
        "".join(rng.choice(_HEX) for _ in range(4))
    # verdict state machine (single source of truth)
    if exit_code != 0:
        verdict = "NO"
        why = ("the job failed with exit code %d (log: FATAL: %s ... after "
               "%d of %d planned steps) - the objective is failed and must "
               "be reported with the reason; no artifact can be trusted yet"
               % (exit_code, reason, steps_done, plan_n))
    elif steps_done < plan_n:
        verdict = "NO"
        why = ("exit 0 is not completion: the log declares %d planned steps "
               "but only %d ran%s - the plan is incomplete, the classic "
               "premature-success trap"
               % (plan_n, steps_done,
                  " and a DONE marker was printed anyway" if done_written
                  else ""))
    elif not art_present:
        verdict = "NO"
        why = ("the plan completed but the final artifact was never "
               "produced - the objective ends in a verified artifact, not "
               "in a green exit code")
    elif not art_verified:
        verdict = "NO"
        why = ("the plan completed and an artifact exists, but it was never "
               "read back and compared - an image that exists is not an "
               "image that works; verify before reporting")
    else:
        verdict = "YES"
        why = ("the process exited 0, all %d planned steps ran, the DONE "
               "marker appeared and the final artifact was read back and "
               "verified - every completion condition holds"
               % plan_n)
    log_lines = ["PLAN: %d" % plan_n]
    for i in range(1, steps_done + 1):
        log_lines.append("[step %d/%d] ok" % (i, plan_n))
    if exit_code != 0:
        log_lines.append("FATAL: %s %d" % (reason, steps_done + 1))
    elif done_written:
        log_lines.append("DONE")
    log = "\n".join(log_lines) + "\n"
    if art_present:
        artifact = ("unit.iso (%d bytes, sha256 %s)%s"
                    % (size, sha,
                       "; read back and equals the synced tree"
                       if art_verified else
                       "; exists but was never read back or compared"))
    else:
        artifact = "no final artifact produced yet"
    return {
        "plan_n": plan_n, "exit_code": exit_code, "steps_done": steps_done,
        "done_written": done_written, "reason": reason,
        "artifact": artifact, "verdict": verdict, "why": why,
        "log": log,
    }


def build_ops_done_criteria(rng: random.Random):
    """Decide, from real signals, whether the objective may be declared done."""
    sit = _done_model(rng)
    exit_text = "exit code %d" % sit["exit_code"]
    answer = (
        "%s. %s Completion checklist for this objective: process terminal "
        "state, every planned step in the log, and the final artifact "
        "verified (exists, read back, compared). A single success signal "
        "never satisfies it." % (sit["verdict"], sit["why"]))
    question = (
        "You are supervising a job whose objective ends in a verified "
        "artifact. May you declare the objective complete right now?\n\n"
        "Job result: %s\nJob log:\n%s\nArtifacts: %s\n\n"
        "Answer YES or NO and justify it against the completion checklist."
        % (exit_text, sit["log"], sit["artifact"]))
    return _mk(rng, "ops_done_criteria", "python", "ops_done_criteria",
               "automation", rng.choice(("intermediate", "advanced")),
               question, answer,
               context="completion-criteria reasoning",
               artifacts={"job_exit": exit_text, "job_log": sit["log"],
                          "artifact_state": sit["artifact"],
                          "verdict": sit["verdict"],
                          "plan_steps": sit["plan_n"],
                          "steps_done": sit["steps_done"],
                          "note": "log, exit and artifact state authored "
                                  "together; the checklist verdict derives "
                                  "from the same model"},
               key_points=["verdict: " + sit["verdict"],
                           "single signals are not completion",
                           "verify the artifact before reporting done"],
               verify_method="authored_verified",
               verify_notes={"evidence": "verdict derived from the authored "
                                         "log/exit/artifact model and "
                                         "cross-checked against the "
                                         "checklist",
                             "situation": sit["verdict"].lower()},
               tags=["agent_ops", "verification", "objectives"],
               variant="v%s|p%d" % (sit["verdict"].lower(), sit["plan_n"]),
               dataset_hint=_DATASET)
