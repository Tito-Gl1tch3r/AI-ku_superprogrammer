"""Dataset-1 write families for Go.

The Go toolchain is NOT installed in this environment, so every candidate is
verified with verify_method="static_check" (structural validation only).
Code is authored as conservative, canonical, stdlib-only Go that would
compile with `go build`: complete package main programs with deterministic
self-checks, buffered channels, sync primitives, errors.Is/As wrapping and
fmt.Stringer implementations. The learning value for the understand-dataset
is carried by the precise notes["explain"] ground truth each family authors.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    """Build the notes["explain"] ground-truth dict required by the contract."""
    return {
        "purpose": purpose,
        "approach": approach,
        "key_points": list(key_points),
        "big_o_time": big_o_time,
        "big_o_space": big_o_space,
        "edge_cases": list(edge_cases),
    }


def _ints(values) -> str:
    return "[]int{" + ", ".join(str(v) for v in values) + "}"


def _strs(values) -> str:
    return "[]string{" + ", ".join('"' + v + '"' for v in values) + "}"


class GoConcurrencyPatterns(Family):
    """package main programs with goroutines, buffered channels,
    sync.WaitGroup and a mutex-guarded counter; deterministic checks only."""

    NAME = "go_concurrency_patterns"
    LANGUAGE = "go"
    DOMAIN = "concurrency"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "debugging", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("worker_pool", "pipeline", "mutex_counter"))
        if kind == "worker_pool":
            return self._worker_pool(rng)
        if kind == "pipeline":
            return self._pipeline(rng)
        return self._mutex_counter(rng)

    def _worker_pool(self, rng: random.Random) -> Candidate:
        workers = rng.randint(2, 4)
        values = [rng.randint(1, 9) for _ in range(rng.randint(3, 6))]
        if rng.random() < 0.5:
            body = "\t\tj.value = j.value * 2"
            want = [v * 2 for v in values]
            op = "doubling"
        else:
            body = "\t\tj.value = j.value * j.value"
            want = [v * v for v in values]
            op = "squaring"
        code = "\n".join([
            "package main",
            "",
            "import (",
            '\t"fmt"',
            '\t"sync"',
            ")",
            "",
            "// job carries the input position so results can be reassembled in order.",
            "type job struct {",
            "\tindex int",
            "\tvalue int",
            "}",
            "",
            "// worker consumes jobs until the channel closes, then signals the WaitGroup.",
            "func worker(jobs <-chan job, results chan<- job, wg *sync.WaitGroup) {",
            "\tdefer wg.Done()",
            "\tfor j := range jobs {",
            body,
            "\t\tresults <- j",
            "\t}",
            "}",
            "",
            "func main() {",
            "\tinput := " + _ints(values),
            "\tjobs := make(chan job, len(input))",
            "\tresults := make(chan job, len(input))",
            "\tvar wg sync.WaitGroup",
            f"\tfor w := 0; w < {workers}; w++ {{",
            "\t\twg.Add(1)",
            "\t\tgo worker(jobs, results, &wg)",
            "\t}",
            "\tfor i, v := range input {",
            "\t\tjobs <- job{index: i, value: v}",
            "\t}",
            "\tclose(jobs)",
            "\tgo func() {",
            "\t\twg.Wait()",
            "\t\tclose(results)",
            "\t}()",
            "\tout := make([]int, len(input))",
            "\tfor r := range results {",
            "\t\tout[r.index] = r.value",
            "\t}",
            "\twant := " + _ints(want),
            "\tfor i := range want {",
            "\t\tif out[i] != want[i] {",
            '\t\t\tpanic(fmt.Sprintf("mismatch at index %d: got %d want %d", i, out[i], want[i]))',
            "\t\t}",
            "\t}",
            '\tfmt.Println("worker pool checks passed")',
            "}",
        ])
        task = (
            "Write a deterministic Go worker pool in package main: " + str(workers) + " goroutine "
            "workers pull from a buffered jobs channel, " + op + " each value, and publish "
            "indexed results so main can reassemble the output in input order. Use "
            "sync.WaitGroup for shutdown and a buffered results channel closed by a "
            "closer goroutine after wg.Wait. For input " + str(values) + " the program must "
            "reconstruct " + str(want) + " and print a confirmation line only after every "
            "element matches. Standard library only."
        )
        expected = (
            "Prints 'worker pool checks passed' after reassembling " + str(want) + " from " +
            str(workers) + " concurrent workers, with per-index comparisons against the want slice."
        )
        explain = _explain(
            purpose=("Implement the classic Go worker pool with deterministic output: N "
                     "workers share a buffered job channel and results carry their input "
                     "index so order never depends on scheduling."),
            approach=("Fan-out via one buffered jobs channel read by " + str(workers) +
                      " goroutines, fan-in via an indexed result channel, and a closer "
                      "goroutine that waits on the WaitGroup before closing results."),
            key_points=[
                "buffered channels sized len(input) let senders never block even before workers start",
                "each worker defers wg.Done so shutdown is counted exactly once per goroutine",
                "embedding the input index in the job makes result placement deterministic despite racing workers",
                "closing jobs signals range loops to end; a separate goroutine closes results after wg.Wait",
            ],
            big_o_time="O(n) work spread over w workers with O(n) reassembly",
            big_o_space="O(n) for both buffered channels and the output slice",
            edge_cases=[
                "an empty input closes jobs immediately; the pool drains with zero results and want stays empty",
                "results would be nondeterministic without the index field, which is why it is asserted per element",
                "closing a channel twice would panic; only the single closer goroutine closes results",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "worker_pool", "explain": explain},
            tags=["go", "concurrency", "worker-pool"], variant="worker_pool",
            seed=rng.randrange(2 ** 31),
        )

    def _pipeline(self, rng: random.Random) -> Candidate:
        values = [rng.randint(1, 20) for _ in range(rng.randint(4, 7))]
        stage_count = rng.randint(2, 3)
        ops = []
        for _ in range(stage_count):
            if rng.random() < 0.5:
                ops.append(("add", rng.randint(1, 9)))
            else:
                ops.append(("double", 0))
        expected = list(values)
        for op, arg in ops:
            expected = [v + arg if op == "add" else v * 2 for v in expected]
        chans = ["first", "second", "third", "fourth"][:stage_count + 1]
        lines = [
            "package main",
            "",
            "import (",
            '\t"fmt"',
            '\t"sync"',
            ")",
            "",
            "// emit pushes every value then closes the channel (pipeline head).",
            "func emit(values []int, out chan<- int, wg *sync.WaitGroup) {",
            "\tdefer wg.Done()",
            "\tfor _, v := range values {",
            "\t\tout <- v",
            "\t}",
            "\tclose(out)",
            "}",
            "",
            "// addStage shifts every value by delta and closes its output.",
            "func addStage(in <-chan int, out chan<- int, delta int, wg *sync.WaitGroup) {",
            "\tdefer wg.Done()",
            "\tfor v := range in {",
            "\t\tout <- v + delta",
            "\t}",
            "\tclose(out)",
            "}",
            "",
            "// doubleStage doubles every value and closes its output.",
            "func doubleStage(in <-chan int, out chan<- int, wg *sync.WaitGroup) {",
            "\tdefer wg.Done()",
            "\tfor v := range in {",
            "\t\tout <- v * 2",
            "\t}",
            "\tclose(out)",
            "}",
            "",
            "func main() {",
            "\tvalues := " + _ints(values),
        ]
        for name in chans:
            lines.append(f"\t{name} := make(chan int, len(values))")
        lines.append("\tvar wg sync.WaitGroup")
        lines.append(f"\twg.Add({stage_count + 1})")
        lines.append(f"\tgo emit(values, {chans[0]}, &wg)")
        for i, (op, arg) in enumerate(ops):
            src, dst = chans[i], chans[i + 1]
            if op == "add":
                lines.append(f"\tgo addStage({src}, {dst}, {arg}, &wg)")
            else:
                lines.append(f"\tgo doubleStage({src}, {dst}, &wg)")
        lines += [
            "\tvar got []int",
            f"\tfor v := range {chans[-1]} {{",
            "\t\tgot = append(got, v)",
            "\t}",
            "\twg.Wait()",
            "\twant := " + _ints(expected),
            "\tif len(got) != len(want) {",
            '\t\tpanic("pipeline length mismatch")',
            "\t}",
            "\tfor i := range want {",
            "\t\tif got[i] != want[i] {",
            '\t\t\tpanic(fmt.Sprintf("pipeline mismatch at index %d", i))',
            "\t\t}",
            "\t}",
            '\tfmt.Println("pipeline checks passed")',
            "}",
        ]
        code = "\n".join(lines)
        stage_desc = ", then ".join(
            ("add " + str(arg)) if op == "add" else "doubling" for op, arg in ops
        )
        task = (
            "Write a multi-stage Go pipeline in package main: an emit goroutine feeds a "
            "buffered channel, " + str(stage_count) + " transform stages (" + stage_desc +
            ") each read one channel and write the next, every stage closes its output "
            "channel when done, and sync.WaitGroup tracks all goroutines. For input " +
            str(values) + " the collected output must equal " + str(expected) + " element by "
            "element before main prints a confirmation line. Standard library only."
        )
        expected_behavior = (
            "Prints 'pipeline checks passed' after the " + str(stage_count) + "-stage chain "
            "yields exactly " + str(expected) + " in input order."
        )
        explain = _explain(
            purpose=("Show a deterministic channel pipeline: buffered channels connect "
                     "single-producer stages whose close discipline makes the final range "
                     "loop terminate and preserve order."),
            approach=("One emit goroutine plus " + str(stage_count) + " stage goroutines; each "
                      "stage defers wg.Done and closes its own output, so main can range "
                      "over the last channel and verify the transformed slice."),
            key_points=[
                "each channel has exactly one closer: emit closes the head, every stage closes its own output",
                "buffering with len(values) keeps the pipeline fully scheduled without unbounded growth",
                "single-consumer-per-channel chains preserve element order without any locking",
                "wg.Add counts emit plus every stage; wg.Wait after draining proves clean shutdown",
            ],
            big_o_time="O(stages * n) total transformation work",
            big_o_space="O(n) per buffered channel",
            edge_cases=[
                "an empty input still flows: emit closes at once and each stage closes downstream in turn",
                "forgetting to close any intermediate channel would deadlock the final range loop",
                "the transforms commute elementwise, so the expected slice is computed by folding stages in order",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected_behavior, code=code,
            verify_method="static_check",
            notes={"kind": "pipeline", "explain": explain},
            tags=["go", "concurrency", "pipeline"], variant="pipeline",
            seed=rng.randrange(2 ** 31),
        )

    def _mutex_counter(self, rng: random.Random) -> Candidate:
        workers = rng.randint(3, 5)
        per_worker = rng.choice((100, 250, 500))
        total = workers * per_worker
        code = "\n".join([
            "package main",
            "",
            "import (",
            '\t"fmt"',
            '\t"sync"',
            ")",
            "",
            "// bump adds to the shared counter under the mutex, exactly times iterations.",
            "func bump(counter *int, mu *sync.Mutex, times int, wg *sync.WaitGroup) {",
            "\tdefer wg.Done()",
            "\tfor i := 0; i < times; i++ {",
            "\t\tmu.Lock()",
            "\t\t*counter += 1",
            "\t\tmu.Unlock()",
            "\t}",
            "}",
            "",
            "func main() {",
            "\tvar mu sync.Mutex",
            "\tvar wg sync.WaitGroup",
            "\ttotal := 0",
            f"\tworkers := {workers}",
            f"\tperWorker := {per_worker}",
            "\tfor w := 0; w < workers; w++ {",
            "\t\twg.Add(1)",
            "\t\tgo bump(&total, &mu, perWorker, &wg)",
            "\t}",
            "\twg.Wait()",
            "\texpected := workers * perWorker",
            "\tif total != expected {",
            '\t\tpanic(fmt.Sprintf("counter drift: got %d want %d", total, expected))',
            "\t}",
            '\tfmt.Println("mutex counter checks passed")',
            "}",
        ])
        task = (
            "Write a race-free shared counter in package main: " + str(workers) + " goroutines each "
            "increment a shared int " + str(per_worker) + " times through a pointer, guarded by a "
            "sync.Mutex so no update is lost, with sync.WaitGroup coordinating shutdown. "
            "func main must wait for all workers and panic with a descriptive Sprintf "
            "message if the final total is not exactly " + str(total) + ", otherwise print a "
            "confirmation line. Standard library only."
        )
        expected = (
            "Prints 'mutex counter checks passed' with the counter at exactly " + str(total) +
            " after " + str(workers) + " workers finish; any drift triggers the panic path."
        )
        explain = _explain(
            purpose=("Demonstrate that shared mutation across goroutines needs mutual "
                     "exclusion: a mutex-guarded counter reaches exactly workers * "
                     "perWorker increments."),
            approach=("Launch " + str(workers) + " goroutines that each lock, increment through a "
                      "pointer, and unlock " + str(per_worker) + " times; the WaitGroup gates the "
                      "final equality check in main."),
            key_points=[
                "counter is passed as *int so every goroutine mutates the same backing variable",
                "mu.Lock/mu.Unlock bracket the read-modify-write; deferring inside a hot loop would be needlessly slower",
                "wg.Add(1) happens before each go statement so no Done can arrive early",
                "the deterministic final value is what makes the race-free claim testable",
            ],
            big_o_time="O(workers * perWorker) increments, serialized on the mutex",
            big_o_space="O(1) beyond goroutine stacks",
            edge_cases=[
                "removing the mutex would make the total drift below " + str(total) + " nondeterministically",
                "perWorker 0 would pass trivially; the generated value is always positive",
                "wg.Wait placement matters: checking the total before Wait could read a mid-flight value",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "mutex_counter", "explain": explain},
            tags=["go", "concurrency", "mutex"], variant="mutex_counter",
            seed=rng.randrange(2 ** 31),
        )


class GoErrorsInterfaces(Family):
    """Custom error types with Error() string, errors.Is/As wrapping, and
    interface satisfaction via fmt.Stringer."""

    NAME = "go_errors_interfaces"
    LANGUAGE = "go"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "testing", "failure_prediction")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("is_as_errors", "stringer_iface", "error_chain"))
        if kind == "is_as_errors":
            return self._is_as_errors(rng)
        if kind == "stringer_iface":
            return self._stringer_iface(rng)
        return self._error_chain(rng)

    def _is_as_errors(self, rng: random.Random) -> Candidate:
        user = rng.choice(("ada", "grace", "linus", "barbara"))
        domain = rng.choice(("example.org", "corp.test", "infra.internal"))
        ghost = rng.choice(("ghost", "nobody", "mallory"))
        email = user + "@" + domain
        code = "\n".join([
            "package main",
            "",
            "import (",
            '\t"errors"',
            '\t"fmt"',
            ")",
            "",
            "// ValidationError is a structured error with pointer receivers.",
            "type ValidationError struct {",
            "\tField  string",
            "\tReason string",
            "}",
            "",
            "func (e *ValidationError) Error() string {",
            '\treturn fmt.Sprintf("validation failed on %s: %s", e.Field, e.Reason)',
            "}",
            "",
            "// ErrNotFound is the sentinel every caller can match with errors.Is.",
            "var ErrNotFound = errors.New(\"record not found\")",
            "",
            "func findUser(users map[string]string, name string) (string, error) {",
            "\tif name == \"\" {",
            '\t\treturn "", &ValidationError{Field: "name", Reason: "empty input"}',
            "\t}",
            "\temail, ok := users[name]",
            "\tif !ok {",
            '\t\treturn "", fmt.Errorf("lookup %q: %w", name, ErrNotFound)',
            "\t}",
            "\treturn email, nil",
            "}",
            "",
            "func main() {",
            "\tusers := map[string]string{\"" + user + "\": \"" + email + "\"}",
            "\tmail, err := findUser(users, \"" + user + "\")",
            "\tif err != nil {",
            "\t\tpanic(err)",
            "\t}",
            "\tif mail != \"" + email + "\" {",
            '\t\tpanic("unexpected email")',
            "\t}",
            '\t_, err = findUser(users, "' + ghost + '")',
            "\tif !errors.Is(err, ErrNotFound) {",
            '\t\tpanic("expected ErrNotFound through the wrapped chain")',
            "\t}",
            "\t_, err = findUser(users, \"\")",
            "\tvar ve *ValidationError",
            "\tif !errors.As(err, &ve) {",
            '\t\tpanic("expected a ValidationError via errors.As")',
            "\t}",
            '\tif ve.Reason != "empty input" {',
            '\t\tpanic("unexpected validation reason")',
            "\t}",
            '\tfmt.Println("errors.Is/As checks passed")',
            "}",
        ])
        task = (
            "Write a Go program in package main demonstrating typed error handling: define "
            "a ValidationError struct with Field/Reason and a pointer-receiver Error() "
            "string method, plus an ErrNotFound sentinel created with errors.New. A "
            "findUser(map, name) function must return the stored email for user '" + user +
            "', wrap ErrNotFound with fmt.Errorf percent-w for missing user '" + ghost +
            "', and return a ValidationError for the empty name. func main must verify all "
            "three paths using errors.Is and errors.As and print a confirmation line. "
            "Standard library only."
        )
        expected = (
            "Prints 'errors.Is/As checks passed': the known user resolves to '" + email +
            "', the ghost user wraps ErrNotFound, and the empty name yields a "
            "ValidationError with reason 'empty input'."
        )
        explain = _explain(
            purpose=("Contrast the two error-matching tools: errors.Is for sentinel values "
                     "(even through percent-w wrapping) and errors.As for structured error "
                     "types with fields."),
            approach=("One lookup function returns three distinct failure shapes; main "
                      "asserts the happy path, the wrapped sentinel, and the typed error "
                      "whose Reason field is then inspected."),
            key_points=[
                "Error() with a pointer receiver means only *ValidationError implements error",
                "fmt.Errorf with %w embeds ErrNotFound so errors.Is matches through the chain",
                "errors.As needs the address of a *ValidationError variable to fill",
                "the comma-ok map lookup distinguishes missing keys from empty-value entries",
            ],
            big_o_time="O(1) map lookup per call",
            big_o_space="O(n) for the user map; O(1) per error value",
            edge_cases=[
                "the empty-name branch returns a concrete *ValidationError that errors.As extracts directly",
                "a wrapped chain longer than one hop would still satisfy errors.Is thanks to Unwrap traversal",
                "matching with == instead of errors.Is would miss the wrapped sentinel",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "is_as_errors", "explain": explain},
            tags=["go", "errors", "wrapping"], variant="is_as_errors",
            seed=rng.randrange(2 ** 31),
        )

    def _stringer_iface(self, rng: random.Random) -> Candidate:
        tid = rng.randint(1, 99)
        state_idx = rng.randint(0, 2)
        states = ("draft", "active", "archived")
        label = "ticket-" + str(tid) + ":" + states[state_idx]
        code = "\n".join([
            "package main",
            "",
            'import "fmt"',
            "",
            "// State is a domain enum whose String method satisfies fmt.Stringer.",
            "type State int",
            "",
            "const (",
            "\tStateDraft State = iota",
            "\tStateActive",
            "\tStateArchived",
            ")",
            "",
            "func (s State) String() string {",
            "\tswitch s {",
            "\tcase StateDraft:",
            '\t\treturn "draft"',
            "\tcase StateActive:",
            '\t\treturn "active"',
            "\tcase StateArchived:",
            '\t\treturn "archived"',
            "\tdefault:",
            '\t\treturn "unknown"',
            "\t}",
            "}",
            "",
            "// Labeler is a tiny consumer interface; Ticket satisfies it implicitly.",
            "type Labeler interface {",
            "\tLabel() string",
            "}",
            "",
            "type Ticket struct {",
            "\tID    int",
            "\tState State",
            "}",
            "",
            "func (t Ticket) Label() string {",
            '\treturn fmt.Sprintf("ticket-%d:%s", t.ID, t.State)',
            "}",
            "",
            "func render(l Labeler) string {",
            '\treturn "label=" + l.Label()',
            "}",
            "",
            "func main() {",
            f"\tt := Ticket{{ID: {tid}, State: State({state_idx})}}",
            '\tif t.State.String() != "' + states[state_idx] + '" {',
            '\t\tpanic("Stringer output mismatch")',
            "\t}",
            '\tif render(t) != "label=' + label + '" {',
            '\t\tpanic("label mismatch")',
            "\t}",
            '\tfor i, want := range []string{"draft", "active", "archived"} {',
            "\t\tif State(i).String() != want {",
            '\t\t\tpanic(fmt.Sprintf("state %d should print as %s", i, want))',
            "\t\t}",
            "\t}",
            "\tfmt.Println(State(42))",
            '\tfmt.Println("interface checks passed")',
            "}",
        ])
        task = (
            "Write a Go program in package main exercising interface satisfaction: define "
            "a State int type with three iota constants and a String() method (so State "
            "implements fmt.Stringer), a Ticket struct with ID/State, and a Labeler "
            "interface with a Label() string method that Ticket satisfies implicitly. For "
            "ticket " + str(tid) + " in state '" + states[state_idx] + "' the rendered label must be '" +
            label + "'. func main must check every state name, the rendered label, the "
            "default 'unknown' branch via State(42), and print a confirmation line. "
            "Standard library only."
        )
        expected = (
            "Prints 'unknown' then 'interface checks passed': all three states stringify "
            "correctly, out-of-range State(42) hits the default branch, and render(t) "
            "returns 'label=" + label + "'."
        )
        explain = _explain(
            purpose=("Show implicit interface satisfaction in Go: a String method makes "
                     "State a fmt.Stringer, and a Label method makes Ticket a Labeler "
                     "without any implements declaration."),
            approach=("Small type hierarchy plus a render(l Labeler) consumer that accepts "
                      "the interface; main asserts each state name, the composed label, "
                      "and the default branch for out-of-range values."),
            key_points=[
                "String() on the value receiver lets both State values and fmt verbs use it",
                "fmt.Sprintf prints t.State through its Stringer, not as the raw int",
                "Ticket satisfies Labeler implicitly; no implements keyword exists in Go",
                "the iota const block gives stable zero-based ordering for State(i) conversions",
            ],
            big_o_time="O(1) per Stringer call",
            big_o_space="O(1); only small structs and literals",
            edge_cases=[
                "State(42) falls through the switch to the default 'unknown' branch instead of panicking",
                "the zero value StateDraft is meaningful because iota starts at zero",
                "render accepts any Labeler, so future types plug in without touching render",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "stringer_iface", "explain": explain},
            tags=["go", "interfaces", "stringer"], variant="stringer_iface",
            seed=rng.randrange(2 ** 31),
        )

    def _error_chain(self, rng: random.Random) -> Candidate:
        good = rng.choice((("2", "s", 2000), ("750", "ms", 750), ("1", "s", 1000)))
        bad_unit = rng.choice(("hours", "lightyears", "micros"))
        code = "\n".join([
            "package main",
            "",
            "import (",
            '\t"errors"',
            '\t"fmt"',
            '\t"strconv"',
            ")",
            "",
            "// ErrBadUnit is the domain sentinel for unsupported units.",
            "var ErrBadUnit = errors.New(\"unknown unit\")",
            "",
            "// ParseError wraps a lower-level failure plus its offending input.",
            "type ParseError struct {",
            "\tInput string",
            "\tErr   error",
            "}",
            "",
            "func (e *ParseError) Error() string {",
            '\treturn fmt.Sprintf("cannot parse %q", e.Input)',
            "}",
            "",
            "func (e *ParseError) Unwrap() error {",
            "\treturn e.Err",
            "}",
            "",
            "func toMillis(raw string, unit string) (int, error) {",
            "\tvalue, err := strconv.Atoi(raw)",
            "\tif err != nil {",
            '\t\treturn 0, &ParseError{Input: raw, Err: err}',
            "\t}",
            "\tswitch unit {",
            '\tcase "s":',
            "\t\treturn value * 1000, nil",
            '\tcase "ms":',
            "\t\treturn value, nil",
            "\t}",
            '\treturn 0, fmt.Errorf("unit %s: %w", unit, ErrBadUnit)',
            "}",
            "",
            "func main() {",
            '\tms, err := toMillis("' + good[0] + '", "' + good[1] + '")',
            "\tif err != nil {",
            "\t\tpanic(err)",
            "\t}",
            "\tif ms != " + str(good[2]) + " {",
            '\t\tpanic("conversion mismatch")',
            "\t}",
            '\t_, err = toMillis("abc", "s")',
            "\tvar pe *ParseError",
            "\tif !errors.As(err, &pe) {",
            '\t\tpanic("expected a ParseError")',
            "\t}",
            '\tif pe.Input != "abc" {',
            '\t\tpanic("ParseError lost the offending input")',
            "\t}",
            '\t_, err = toMillis("5", "' + bad_unit + '")',
            "\tif !errors.Is(err, ErrBadUnit) {",
            '\t\tpanic("expected ErrBadUnit through wrapping")',
            "\t}",
            '\tfmt.Println("error chain checks passed")',
            "}",
        ])
        task = (
            "Write a Go program in package main building a proper error chain: a "
            "ParseError struct wraps strconv failures (with Error() and Unwrap() methods), "
            "toMillis(raw, unit) converts durations and wraps unsupported units with "
            "fmt.Errorf percent-w around an ErrBadUnit sentinel. func main must verify the "
            "conversion " + good[0] + " " + good[1] + " equals " + str(good[2]) + " ms, recover a *ParseError "
            "from input 'abc' via errors.As and check its Input field, and detect "
            "ErrBadUnit for unit '" + bad_unit + "' via errors.Is, then print a confirmation "
            "line. Standard library only."
        )
        expected = (
            "Prints 'error chain checks passed': " + good[0] + " " + good[1] + " converts to " +
            str(good[2]) + " ms, 'abc' surfaces a *ParseError keeping its input, and the '" +
            bad_unit + "' case matches ErrBadUnit through Unwrap."
        )
        explain = _explain(
            purpose=("Teach error wrapping end to end: a custom ParseError with Unwrap "
                     "chains low-level failures, and percent-w wrapping keeps sentinel "
                     "matching alive across layers."),
            approach=("Two error types serve different roles (structural ParseError vs "
                      "sentinel ErrBadUnit); main inspects the chain with errors.As for "
                      "fields and errors.Is for identity."),
            key_points=[
                "Unwrap() error is what lets errors.Is and errors.As traverse the chain",
                "strconv.Atoi errors are preserved inside ParseError.Err for later inspection",
                "fmt.Errorf with %w attaches ErrBadUnit while adding context text",
                "the switch returns typed failures so callers branch on kind, not on strings",
            ],
            big_o_time="O(1) per conversion and per chain hop",
            big_o_space="O(1); two small error structs at most",
            edge_cases=[
                "a non-numeric input produces a ParseError whose Input field still names the bad text",
                "an unknown unit never reaches strconv; the sentinel path is independent of parsing",
                "dropping Unwrap would silently break errors.Is for the wrapped sentinel",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "error_chain", "explain": explain},
            tags=["go", "errors", "wrapping"], variant="error_chain",
            seed=rng.randrange(2 ** 31),
        )


class GoProjectFamily(Family):
    """Multi-file Go project: main.go + lib.go (same package main) + README."""

    NAME = "go_project_multifile"
    LANGUAGE = "go"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        pool = ("deploy", "cache", "index", "replica", "canary", "rollback", "artifact")
        words = rng.choices(pool, k=rng.randint(6, 9))
        counts = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1
        limit = rng.randint(2, 3)
        top = sorted(counts, key=lambda w: (-counts[w], w))[:limit]
        title_words = rng.sample(("Deploy", "Guide", "Release", "Hotfix"), 2)
        norm_src = "  " + "  ".join(title_words) + " "
        norm_want = " ".join(w.lower() for w in title_words)
        probe = top[0]

        main_go = "\n".join([
            "package main",
            "",
            'import "fmt"',
            "",
            "func main() {",
            "\twords := " + _strs(words),
            "\tcounts := WordCounts(words)",
            "\tif counts[\"" + probe + "\"] != " + str(counts[probe]) + " {",
            '\t\tpanic("word count mismatch")',
            "\t}",
            "\ttop := TopTokens(counts, " + str(limit) + ")",
            "\twant := " + _strs(top),
            "\tfor i := range want {",
            "\t\tif top[i] != want[i] {",
            '\t\t\tpanic("top token mismatch")',
            "\t\t}",
            "\t}",
            '\tif Normalize("' + norm_src + '") != "' + norm_want + '" {',
            '\t\tpanic("normalize mismatch")',
            "\t}",
            "\tif len(TopTokens(map[string]int{}, 3)) != 0 {",
            '\t\tpanic("empty map must give an empty top list")',
            "\t}",
            '\tfmt.Println("project self-checks passed")',
            "}",
        ])
        lib_go = "\n".join([
            "package main",
            "",
            "import (",
            '\t"sort"',
            '\t"strings"',
            ")",
            "",
            "// WordCounts tallies occurrences over the input slice.",
            "func WordCounts(words []string) map[string]int {",
            "\tcounts := make(map[string]int)",
            "\tfor _, w := range words {",
            "\t\tcounts[w]++",
            "\t}",
            "\treturn counts",
            "}",
            "",
            "// TopTokens returns up to limit tokens ordered by count desc,",
            "// breaking ties alphabetically so the output is deterministic.",
            "func TopTokens(counts map[string]int, limit int) []string {",
            "\tnames := make([]string, 0, len(counts))",
            "\tfor name := range counts {",
            "\t\tnames = append(names, name)",
            "\t}",
            "\tsort.Slice(names, func(i, j int) bool {",
            "\t\tif counts[names[i]] != counts[names[j]] {",
            "\t\t\treturn counts[names[i]] > counts[names[j]]",
            "\t\t}",
            "\t\treturn names[i] < names[j]",
            "\t})",
            "\tif limit > len(names) {",
            "\t\tlimit = len(names)",
            "\t}",
            "\treturn names[:limit]",
            "}",
            "",
            "// Normalize collapses whitespace runs and lowercases the text.",
            "func Normalize(text string) string {",
            "\treturn strings.ToLower(strings.Join(strings.Fields(text), \" \"))",
            "}",
        ])
        readme = "\n".join([
            "# tokenmetrics demo project",
            "",
            "A two-file Go program in package main: a tiny token-metrics core.",
            "",
            "## Files",
            "",
            "- main.go: entry point; func main runs deterministic checks against the",
            "  helpers and prints a confirmation line",
            "- lib.go: helpers WordCounts, TopTokens and Normalize in the same package",
            "",
            "## Build and run",
            "",
            "- go run . compiles both files together and executes the self-checks",
            "- go build ./... produces one binary because both files share package main",
            "- go vet ./... reports no issues; no external modules are required",
            "",
            "## Extending",
            "",
            "Add new helpers to lib.go keeping the same package clause; a future",
            "lib_test.go can hold table-driven tests without changing the binary layout.",
        ])
        files = [
            FileSpec("main.go", main_go),
            FileSpec("lib.go", lib_go),
            FileSpec("README.md", readme),
        ]
        task = (
            "Build the two-file Go project 'tokenmetrics' exactly as the README describes: "
            "lib.go provides WordCounts over a word slice, TopTokens with count-descending "
            "alphabetically-tie-broken ordering, and Normalize (whitespace collapse plus "
            "lowercasing), all in package main; main.go runs deterministic checks on the "
            "sample corpus " + str(words) + " expecting top-" + str(limit) + " " + str(top) +
            " and normalization of '" + norm_src.strip() + "' to '" + norm_want + "'. The README "
            "must document the build commands. Standard library only."
        )
        expected = (
            "go run . prints 'project self-checks passed': the corpus tallies match, top-" +
            str(limit) + " equals " + str(top) + ", normalization yields '" + norm_want +
            "', and the empty map yields an empty top list."
        )
        explain = _explain(
            purpose=("Model a minimal two-file Go project: helpers live in lib.go, the "
                     "entry point in main.go, both in package main so they compile into "
                     "one binary with deterministic self-checks."),
            approach=("Library-style helpers plus a checking main; TopTokens sorts token "
                      "names with a two-key comparator so its output is fully "
                      "deterministic despite Go's random map iteration order."),
            key_points=[
                "both files declare package main, which is what allows one `go build` binary from two files",
                "TopTokens ties break alphabetically, making the result independent of map iteration randomness",
                "strings.Fields splits on any whitespace run and Join rebuilds with single spaces",
                "the empty-map guard exercises the limit clamping branch (limit > len(names))",
            ],
            big_o_time="O(n) counting plus O(k log k) sorting over k distinct tokens",
            big_o_space="O(n + k) for the corpus copy and the counts map",
            edge_cases=[
                "an empty counts map returns an empty slice rather than panicking on names[:limit]",
                "a limit larger than the distinct-token count is clamped to len(names)",
                "Normalize on an all-space input returns the empty string",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, files=files,
            entry="main.go", verify_method="static_check", is_project=True,
            notes={"project": "tokenmetrics", "explain": explain},
            tags=["go", "project", "packages"], variant="tokenmetrics",
            seed=rng.randrange(2 ** 31),
        )


register(globals(), GoConcurrencyPatterns)
register(globals(), GoErrorsInterfaces)
register(globals(), GoProjectFamily)
