"""Dataset-1 write families for Bash (verified with fixtures in a sandbox cwd)."""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register


class BashOpsFamily(Family):
    NAME = "bash_ops_scripts"
    LANGUAGE = "bash"
    DOMAIN = "automation"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "debugging", "testing", "code_review")

    KINDS = ("log_count", "csv_filter", "dedup", "disk_report", "backup_pack", "arg_tool")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        if kind == "log_count":
            levels = ["INFO", "WARN", "ERROR"]
            target = rng.choice(levels)
            lines = []
            for _ in range(rng.randint(8, 30)):
                lv = rng.choice(levels)
                lines.append(f"2026-05-1{rng.randrange(0, 9)}T12:{rng.randrange(10, 59)} {lv} svc={rng.choice(['api', 'db', 'auth'])} ms={rng.randint(1, 900)}")
            n_target = sum(1 for l in lines if target in l)
            script = (f"#!/usr/bin/env bash\n"
                      f"# Count log lines whose level equals $1 (default {target}).\n"
                      f"set -u\n"
                      f"level=\"${{1:-{target}}}\"\n"
                      f"grep -c \" $level \" app.log\n")
            cases = [{"args": [target], "fixtures": {"app.log": "\n".join(lines) + "\n"},
                      "expected_stdout": f"{n_target}\n", "expected_exit": 0,
                      "stdout_mode": "exact"},
                     {"args": [], "fixtures": {"app.log": "\n".join(lines) + "\n"},
                      "expected_stdout": f"{n_target}\n", "expected_exit": 0,
                      "stdout_mode": "exact"}]
            task = (f"Write a Bash script (read from app.log in the current directory) that prints "
                    f"ONLY the number of lines whose log level equals the first argument (default "
                    f"'{target}' when omitted). A level appears as a standalone word like ' {target} '. "
                    f"With zero matches grep -c prints 0 and exits 1 — the script must still exit 0 "
                    f"and print the count.")
            script = script.replace("grep -c \" $level \" app.log\n",
                                    "count=$(grep -c \" $level \" app.log || true)\necho \"$count\"\n")
            expected = f"Prints {n_target} for the sample log; level names are matched as whole words."
        elif kind == "csv_filter":
            header = "user,action,ms"
            rows = []
            for _ in range(rng.randint(6, 18)):
                rows.append((rng.choice(["ada", "ken", "grace"]),
                             rng.choice(["login", "query", "logout"]),
                             rng.randint(1, 800)))
            want_action = rng.choice(["login", "query", "logout"])
            matched = [r for r in rows if r[1] == want_action]
            csv_text = "\n".join([header] + [f"{u},{a},{m}" for u, a, m in rows]) + "\n"
            script = (f"#!/usr/bin/env bash\n"
                      f"# Print user,ms of rows whose action (column 2) equals $1, skipping the header.\n"
                      f"set -eu\n"
                      f"action=\"$1\"\n"
                      f"awk -F, -v a=\"$action\" 'NR > 1 && $2 == a {{ print $1 \",\" $3 }}' events.csv\n")
            exp_out = "".join(f"{u},{m}\n" for u, _a, m in matched)
            cases = [{"args": [want_action], "fixtures": {"events.csv": csv_text},
                      "expected_stdout": exp_out, "expected_exit": 0, "stdout_mode": "exact"}]
            task = (f"Write a Bash script that filters events.csv (columns: user,action,ms, with a "
                    f"header) and prints 'user,ms' for every row whose action equals the first "
                    f"argument, preserving file order. Use awk; do not print the header.")
            expected = f"{len(matched)} rows match action '{want_action}'."
        elif kind == "dedup":
            words = [rng.choice(["alpha", "beta", "gamma", "delta", "eps", "zeta", "eta"])
                     for _ in range(rng.randint(10, 30))]
            unique_sorted = sorted(set(words))
            script = (f"#!/usr/bin/env bash\n"
                      f"# Print the unique lines of input.txt sorted ascending.\n"
                      f"set -eu\n"
                      f"sort -u input.txt\n")
            exp_out = "\n".join(unique_sorted) + "\n"
            cases = [{"args": [], "fixtures": {"input.txt": "\n".join(words) + "\n"},
                      "expected_stdout": exp_out, "expected_exit": 0, "stdout_mode": "exact"}]
            task = ("Write a Bash script that reads input.txt in the current directory and prints "
                    "its unique lines sorted ascending (one per line).")
            expected = f"{len(words)} lines collapse to {len(unique_sorted)} unique entries."
        elif kind == "disk_report":
            files = {}
            for name in rng.sample(["core.log", "api.log", "db.log", "auth.log", "worker.log"],
                                   rng.randint(3, 5)):
                files[name] = "x" * (rng.randint(1, 90) * 100)
            big = rng.randint(20, 70) * 100
            selected = sorted(n for n, c in files.items() if len(c) >= big)
            script = (f"#!/usr/bin/env bash\n"
                      f"# List *.log files of at least $1 bytes (default {big}), sorted by name.\n"
                      f"set -eu\n"
                      f"min=\"${{1:-{big}}}\"\n"
                      f"find . -maxdepth 1 -type f -name '*.log' -size +\"$min\"c -printf '%f\\n' | sort\n")
            exp_out = "".join(f"{n}\n" for n in selected)
            cases = [{"args": [], "fixtures": files, "expected_stdout": exp_out,
                      "expected_exit": 0, "stdout_mode": "exact"},
                     {"args": [str(10 ** 6)], "fixtures": files, "expected_stdout": "",
                      "expected_exit": 0, "stdout_mode": "exact"}]
            task = (f"Write a Bash script that lists the names (no ./ prefix) of *.log files in the "
                    f"current directory whose size is at least the first argument in bytes (default "
                    f"{big}), one per line, sorted ascending. Files with exactly the threshold size "
                    f"are included when strictly larger is false — here use strictly greater than or "
                    f"equal via -size +N-1c semantics handled by find; simplest correct approach: "
                    f"-size +$((min-1))c.")
            script = script.replace('-size +"$min"c', '-size +"$((min - 1))"c')
            expected = f"{len(selected)} files meet the {big}-byte threshold."
        elif kind == "backup_pack":
            payload = {f"{n}.txt": f"content of {n}\n" * rng.randint(1, 4)
                       for n in rng.sample(["notes", "todo", "readme", "creds"], rng.randint(2, 4))}
            names = sorted(payload)
            script = (f"#!/usr/bin/env bash\n"
                      f"# Pack every .txt file into backup.tar.gz, then print the archive listing.\n"
                      f"set -eu\n"
                      f"tar -czf backup.tar.gz *.txt\n"
                      f"tar -tzf backup.tar.gz | sort\n")
            exp_out = "".join(f"{n}\n" for n in names)
            cases = [{"args": [], "fixtures": payload, "expected_stdout": exp_out,
                      "expected_exit": 0, "stdout_mode": "exact"}]
            task = ("Write a Bash script that packs all *.txt files of the current directory into "
                    "backup.tar.gz and then prints the archive's file list sorted ascending (names "
                    "only, as tar lists them).")
            expected = f"Archive contains {len(names)} files: {', '.join(names)}."
        else:  # arg_tool
            script = ('#!/usr/bin/env bash\n'
                      '# Greet each argument; print usage and exit 1 with no arguments.\n'
                      'set -u\n'
                      'if [ "$#" -eq 0 ]; then\n'
                      '    echo "usage: $0 name..." >&2\n'
                      '    exit 1\n'
                      'fi\n'
                      'for name in "$@"; do\n'
                      '    echo "hello, $name"\n'
                      'done\n')
            names = rng.sample(["ada", "ken", "grace", "linus"], rng.randint(1, 3))
            exp_out = "".join(f"hello, {n}\n" for n in names)
            cases = [{"args": names, "fixtures": {}, "expected_stdout": exp_out,
                      "expected_exit": 0, "stdout_mode": "exact"},
                     {"args": [], "fixtures": {}, "expected_stdout": "",
                      "expected_exit": 1, "stdout_mode": "exact"}]
            task = ("Write a Bash script that prints 'hello, NAME' for each argument; with zero "
                    "arguments it prints 'usage: $0 name...' to stderr and exits with status 1.")
            expected = "One greeting per argument; usage error exits 1 without stdout output."
        return Candidate(
            family=self.NAME, language="bash", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=script,
            verify_method="executed",
            notes={"cases": cases, "kind": kind,
                   "explain": {"purpose": expected,
                               "approach": "POSIX tools composed in a pipeline with strict mode.",
                               "key_points": ["quote every expansion",
                                              "set -u catches unset variables",
                                              "check exit codes of greps that may find nothing"],
                               "big_o_time": "O(n)", "big_o_space": "O(n)"}},
            tags=["bash", kind], variant=kind, seed=rng.randrange(2**31))


class BashProjectFamily(Family):
    """Multi-file bash project: script + lib + config + README."""
    NAME = "bash_project_multifile"
    LANGUAGE = "bash"
    DOMAIN = "automation"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        topic = rng.choice(["deploy", "rotate", "watch"])
        lib_fn = rng.choice(["log_line", "emit", "stamp"])
        config = {"LOG_LEVEL": rng.choice(["info", "debug", "warn"]),
                  "TARGET": rng.choice(["staging", "prod", "canary"]),
                  "RETRIES": str(rng.randint(1, 5))}
        lib = (f"#!/usr/bin/env bash\n"
               f"# lib.sh: shared logging helpers (sourced by main scripts).\n"
               f"{lib_fn}() {{\n"
               f"    local level=\"$1\"; shift\n"
               f"    printf '[%s] %s: %s\\n' \"$(date -u +%H:%M:%S)\" \"$level\" \"$*\"\n"
               f"}}\n"
               f"info() {{ {lib_fn} info \"$@\"; }}\n"
               f"warn() {{ {lib_fn} warn \"$@\"; }}\n")
        main = (f"#!/usr/bin/env bash\n"
                f"# run_{topic}.sh — {topic} runner driven by config.env\n"
                f"set -eu\n"
                f"SCRIPT_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
                f"# shellcheck source=/dev/null\n"
                f"source \"$SCRIPT_DIR/lib.sh\"\n"
                f"source \"$SCRIPT_DIR/config.env\"\n"
                f"info \"starting {topic} for $TARGET (level=$LOG_LEVEL, retries=$RETRIES)\"\n"
                f"printf '%s\\n' \"$TARGET:$RETRIES\"\n")
        conf = "\n".join(f"{k}={v}" for k, v in config.items()) + "\n"
        readme = (f"# {topic}-toolkit\n\n"
                  f"- `lib.sh`: logging helpers\n"
                  f"- `run_{topic}.sh`: entry point sourcing lib + config\n"
                  f"- `config.env`: environment knobs\n")
        # Deterministic date: override date via PATH? Simpler: test the CONFIG plumbing only.
        tests_note = "config plumbing verified by executing the runner"
        target = config["TARGET"]
        retries = config["RETRIES"]
        level = config["LOG_LEVEL"]
        exp_tail = f"{target}:{retries}\n"
        cases = [{"args": [], "fixtures": {},
                  "expected_stdout": exp_tail, "expected_exit": 0,
                  "stdout_mode": "contains"}]
        files = [FileSpec("lib.sh", lib), FileSpec(f"run_{topic}.sh", main),
                 FileSpec("config.env", conf), FileSpec("README.md", readme)]
        expected = (f"The runner sources lib.sh + config.env, logs one line, then prints "
                    f"{exp_tail.strip()}.")
        task = (f"Assemble a multi-file Bash toolkit ({topic}): a lib.sh with a {lib_fn}() helper "
                f"plus info/warn wrappers, config.env (LOG_LEVEL={level}, TARGET={target}, "
                f"RETRIES={retries}), and run_{topic}.sh that sources both, logs 'starting {topic} "
                f"for $TARGET (...)' and prints '$TARGET:$RETRIES' as its final line. "
                f"{tests_note}.")
        return Candidate(
            family=self.NAME, language="bash", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected,
            files=files, entry=f"run_{topic}.sh", verify_method="executed",
            is_project=True,
            notes={"cases": cases, "kind": topic,
                   "explain": {"purpose": expected,
                               "approach": "Script composition: sourced library, dotenv-style config, strict mode.",
                               "key_points": ["source relative to SCRIPT_DIR",
                                              "config as key=value pairs",
                                              "log helper keeps a single format"],
                               "big_o_time": "O(1)", "big_o_space": "O(1)"}},
            tags=["bash", "project", topic], variant=topic, seed=rng.randrange(2**31))


register(globals(), BashOpsFamily)
register(globals(), BashProjectFamily)
