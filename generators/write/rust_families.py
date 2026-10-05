"""Dataset-1 write families for Rust.

rustc is NOT installed in this environment, so every candidate here is
verified with verify_method="static_check" (structural validation only).
Code is authored as conservative, canonical, stdlib-only Rust that would
compile under a real toolchain: complete programs with deterministic
assert_eq! self-checks, no exotic APIs, no stubs. The learning value for
the understand-dataset is carried by the precise notes["explain"] ground
truth each family authors alongside the code.
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


def _vec(values) -> str:
    return "vec![" + ", ".join(str(v) for v in values) + "]"


class RustOwnershipBasics(Family):
    """Single-file Rust binary: move semantics, shared vs exclusive borrows,
    and Vec/String operations, gated by deterministic assert_eq! checks."""

    NAME = "rust_ownership_basics"
    LANGUAGE = "rust"
    DOMAIN = "systems"
    DIFFICULTIES = ("beginner", "intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "trace", "code_review", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("move_vec", "borrow_slice", "string_ops"))
        if kind == "move_vec":
            return self._move_vec(rng)
        if kind == "borrow_slice":
            return self._borrow_slice(rng)
        return self._string_ops(rng)

    def _move_vec(self, rng: random.Random) -> Candidate:
        fn_name = rng.choice(("take_ownership", "consume_vector", "own_and_sum"))
        extra_fn = rng.choice(("extend_and_return", "push_and_return"))
        values = [rng.randint(1, 50) for _ in range(rng.randint(3, 6))]
        total = sum(values)
        first, second = rng.randint(2, 9), rng.randint(10, 19)
        extra = rng.randint(20, 30)
        code = "\n".join([
            "// Move semantics: passing a Vec by value transfers ownership.",
            "fn " + fn_name + "(values: Vec<i64>) -> i64 {",
            "    let total: i64 = values.iter().sum();",
            "    total",
            "}",
            "",
            "fn " + extra_fn + "(mut values: Vec<i64>, extra: i64) -> Vec<i64> {",
            "    values.push(extra);",
            "    values",
            "}",
            "",
            "fn main() {",
            "    let numbers = " + _vec(values) + ";",
            "    let total = " + fn_name + "(numbers); // numbers is moved here",
            "    assert_eq!(total, " + str(total) + ");",
            "    let grown = " + extra_fn + "(" + _vec([first, second]) + ", " + str(extra) + ");",
            "    assert_eq!(grown, " + _vec([first, second, extra]) + ");",
            '    println!("move semantics checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program that demonstrates move semantics for "
            "Vec<i64>: a function " + fn_name + " takes the vector by value and returns the "
            "folded i64 total, and a second function " + extra_fn + " takes a mutable vector "
            "plus one extra element and returns the grown vector. fn main must run "
            "deterministic assert_eq! self-checks (the sample vector folds to " + str(total) +
            ") and print a confirmation line. Use only the standard library."
        )
        expected = (
            "Compiles and runs printing 'move semantics checks passed' once the "
            "assert_eq! checks on the owned total and the extended vector pass."
        )
        explain = _explain(
            purpose=("Demonstrate Rust move semantics for Vec<i64>: a function taking the "
                     "vector by value consumes it, while a by-value mutable helper grows "
                     "a vector and returns it."),
            approach=("Two small free functions plus fn main running deterministic "
                      "assert_eq! self-checks; the total is folded with the iterator "
                      "sum() adaptor, no loops needed."),
            key_points=[
                "passing a Vec to a function by value moves ownership; using the caller binding afterwards would be error E0382",
                "a `mut` parameter binding lets the callee push without the caller seeing intermediate states",
                "values.iter().sum() reads elements through a shared borrow because i64 is Copy",
                "assert_eq! panics with both compared values, which makes the self-checks readable on failure",
            ],
            big_o_time="O(n) for the sum over n elements",
            big_o_space="O(n) for the moved and grown vectors",
            edge_cases=[
                "an empty Vec is legal: sum() of an empty iterator is 0, so assert_eq!(total, 0) would hold",
                "reading `numbers` after the move is a compile error, which is exactly the lesson of the demo",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "move_vec", "explain": explain},
            tags=["rust", "ownership", "move"], variant="move_vec",
            seed=rng.randrange(2 ** 31),
        )

    def _borrow_slice(self, rng: random.Random) -> Candidate:
        sum_fn = rng.choice(("sum_slice", "total_of", "sum_borrowed"))
        clamp_fn = rng.choice(("clamp_all", "bound_values"))
        data = [rng.randint(1, 99) for _ in range(rng.randint(4, 7))]
        low = rng.randint(10, 30)
        high = rng.randint(60, 90)
        clamped = [max(low, min(high, v)) for v in data]
        before = sum(data)
        code = "\n".join([
            "// Shared borrows read, exclusive borrows mutate; the owner stays in control.",
            "fn " + sum_fn + "(values: &[i64]) -> i64 {",
            "    values.iter().sum()",
            "}",
            "",
            "fn " + clamp_fn + "(values: &mut Vec<i64>, low: i64, high: i64) {",
            "    for value in values.iter_mut() {",
            "        if *value < low {",
            "            *value = low;",
            "        } else if *value > high {",
            "            *value = high;",
            "        }",
            "    }",
            "}",
            "",
            "fn main() {",
            "    let data = " + _vec(data) + ";",
            "    let before = " + sum_fn + "(&data);",
            "    assert_eq!(before, " + str(before) + ");",
            "    let mut work = data.clone();",
            "    " + clamp_fn + "(&mut work, " + str(low) + ", " + str(high) + ");",
            "    assert_eq!(work, " + _vec(clamped) + ");",
            "    assert_eq!(" + sum_fn + "(&data), " + str(before) + "); // data untouched",
            '    println!("borrow checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program that contrasts shared and exclusive "
            "borrowing: a read-only function " + sum_fn + " sums a slice via &[i64], and an "
            "in-place function " + clamp_fn + " bounds every element of a &mut Vec<i64> into "
            "[" + str(low) + ", " + str(high) + "]. fn main must prove with assert_eq! that the "
            "borrower sees total " + str(before) + ", the clamped copy changes exactly as "
            "expected, and the original vector is untouched. Standard library only."
        )
        expected = (
            "Runs printing 'borrow checks passed'; the shared borrow reports total " +
            str(before) + ", the exclusive borrow clamps the copy, and the original data is unchanged."
        )
        explain = _explain(
            purpose=("Show the read-only (&[i64]) versus mutating (&mut Vec<i64>) borrowing "
                     "protocol on the same owned data, proving the owner is never consumed."),
            approach=("Two borrowing functions plus a clone in fn main: the shared borrow "
                      "sums, the exclusive borrow clamps in place, and assert_eq! compares "
                      "all three observations."),
            key_points=[
                "many immutable borrows or exactly one mutable borrow: here they are sequenced so both are legal",
                "iter_mut() yields &mut i64 elements; the code dereferences with *value to read and write",
                "deref coercion turns &Vec<i64> into &[i64] at the call site, so one function serves both",
                "cloning before mutation keeps the original available for the post-check assertion",
            ],
            big_o_time="O(n) for the sum and the clamp pass",
            big_o_space="O(n) for the cloned working copy",
            edge_cases=[
                "values equal to a bound are kept as-is because the comparisons are strict",
                "generated bounds keep low < high; with low > high every value would be pinned to low",
                "an empty slice sums to 0 and an empty vector clamps to an empty vector",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "borrow_slice", "explain": explain},
            tags=["rust", "ownership", "borrowing"], variant="borrow_slice",
            seed=rng.randrange(2 ** 31),
        )

    def _string_ops(self, rng: random.Random) -> Candidate:
        shout_fn = rng.choice(("shout", "exclaim", "emphasize"))
        word_fn = rng.choice(("word_count", "count_words"))
        word = rng.choice(("deploy", "rollback", "canary", "replica"))
        phrase_words = rng.sample(("ship", "fast", "safe", "often", "daily"), rng.randint(2, 4))
        phrase = " ".join(phrase_words)
        prefix = rng.choice(("v", "rel-", "build-"))
        suffix = rng.choice(("1.4", "2.0", "9"))
        code = "\n".join([
            "// String ownership: &str borrows read-only, String owns and grows.",
            "fn " + shout_fn + "(text: &str) -> String {",
            "    let mut owned = String::from(text);",
            "    owned.push('!');",
            "    owned",
            "}",
            "",
            "fn " + word_fn + "(text: &str) -> usize {",
            "    text.split_whitespace().count()",
            "}",
            "",
            "fn main() {",
            '    let shouted = ' + shout_fn + '("' + word + '");',
            '    assert_eq!(shouted, "' + word + '!");',
            '    assert_eq!(' + word_fn + '("' + phrase + '"), ' + str(len(phrase_words)) + ');',
            '    let mut label = String::from("' + prefix + '");',
            '    label.push_str("' + suffix + '");',
            '    assert_eq!(label, "' + prefix + suffix + '");',
            '    println!("string checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program covering String versus str ownership: a "
            "builder function " + shout_fn + " borrows &str and returns a fresh owned String "
            "with an exclamation mark appended, and a counter function " + word_fn + " borrows "
            "&str and returns the whitespace-separated word count. fn main must verify the "
            "borrowed input '" + word + "', the phrase '" + phrase + "' counting " +
            str(len(phrase_words)) + " words, and incremental label growth via push_str with "
            "assert_eq! checks. Standard library only."
        )
        expected = (
            "Runs printing 'string checks passed' after verifying the owned String, the "
            "word count " + str(len(phrase_words)) + " and the grown label '" + prefix + suffix + "'."
        )
        explain = _explain(
            purpose=("Teach the &str/String split: borrowed string slices feed cheap "
                     "read-only helpers, while owned String buffers are built and grown."),
            approach=("Two functions taking &str plus fn main: one allocates a new String "
                      "via String::from and push, the other counts words with the "
                      "split_whitespace iterator."),
            key_points=[
                "String::from copies the slice data into an owned, growable buffer",
                "push_str appends without the caller ever holding two mutable borrows",
                "split_whitespace lazily yields words; count() consumes the iterator in O(n)",
                "returning String from a &str input is the standard owned-output pattern",
            ],
            big_o_time="O(n) in the input length for both helpers",
            big_o_space="O(n) for the owned String copies",
            edge_cases=[
                "an empty input string yields an empty owned String and a word count of 0",
                "leading, trailing and repeated spaces are collapsed by split_whitespace, not split(' ')",
                "push('!') appends a single char while push_str appends a whole slice",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "string_ops", "explain": explain},
            tags=["rust", "ownership", "strings"], variant="string_ops",
            seed=rng.randrange(2 ** 31),
        )


class RustErrorHandling(Family):
    """Result<T, E> with a custom error enum, the ? operator, match on
    Ok/Err, and Option combinators like map/unwrap_or."""

    NAME = "rust_error_handling"
    LANGUAGE = "rust"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "trace", "code_review", "failure_prediction")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("config_errors", "result_propagation", "option_chain"))
        if kind == "config_errors":
            return self._config_errors(rng)
        if kind == "result_propagation":
            return self._result_propagation(rng)
        return self._option_chain(rng)

    def _config_errors(self, rng: random.Random) -> Candidate:
        key = rng.choice(("host", "region", "endpoint"))
        value = rng.choice(("db.local", "eu-central-1.internal", "api-edge.corp.test"))
        port = rng.choice((5432, 6379, 8080, 9092))
        bad_port = rng.choice((0, 70000, 99999))
        missing = rng.choice(("timeout", "retries", "quota"))
        code = "\n".join([
            "use std::fmt;",
            "",
            "// Custom error type paired with the Result<T, E> protocol.",
            "#[derive(Debug, PartialEq)]",
            "enum ConfigError {",
            "    MissingKey(String),",
            "    BadPort(i64),",
            "    NotANumber,",
            "}",
            "",
            "impl fmt::Display for ConfigError {",
            "    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {",
            "        match self {",
            '            ConfigError::MissingKey(key) => write!(f, "missing config key: {}", key),',
            '            ConfigError::BadPort(port) => write!(f, "port out of range: {}", port),',
            '            ConfigError::NotANumber => write!(f, "value is not a number"),',
            "        }",
            "    }",
            "}",
            "",
            "fn lookup(table: &[(String, String)], key: &str) -> Result<String, ConfigError> {",
            "    for (name, value) in table {",
            "        if name.as_str() == key {",
            "            return Ok(value.clone());",
            "        }",
            "    }",
            "    Err(ConfigError::MissingKey(String::from(key)))",
            "}",
            "",
            "fn parse_port(raw: &str) -> Result<i64, ConfigError> {",
            "    let value: i64 = raw.parse().map_err(|_| ConfigError::NotANumber)?;",
            "    if value < 1 || value > 65535 {",
            "        return Err(ConfigError::BadPort(value));",
            "    }",
            "    Ok(value)",
            "}",
            "",
            "fn main() {",
            "    let table = vec![",
            '        (String::from("' + key + '"), String::from("' + value + '")),',
            '        (String::from("port"), String::from("' + str(port) + '")),',
            "    ];",
            '    let host = lookup(&table, "' + key + '").unwrap_or_else(|_| String::from("unset"));',
            '    assert_eq!(host, "' + value + '");',
            '    let raw = lookup(&table, "port").unwrap();',
            "    let port = parse_port(&raw).unwrap_or(8080);",
            "    assert_eq!(port, " + str(port) + ");",
            '    assert_eq!(parse_port("' + str(bad_port) + '"), Err(ConfigError::BadPort(' + str(bad_port) + ')));',
            '    assert_eq!(parse_port("abc"), Err(ConfigError::NotANumber));',
            '    match lookup(&table, "' + missing + '") {',
            '        Ok(value) => panic!("unexpected value: {}", value),',
            '        Err(err) => assert_eq!(err.to_string(), "missing config key: ' + missing + '"),',
            "    }",
            '    println!("config error checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program implementing idiomatic error handling for a "
            "config reader: define a custom error enum ConfigError with variants MissingKey, "
            "BadPort and NotANumber plus a Display impl; a lookup function returns "
            "Result<String, ConfigError> and a parse_port function converts text into a "
            "validated port using the ? operator over map_err. fn main must exercise the "
            "happy path (key '" + key + "' yields '" + value + "', port " + str(port) + "), the "
            "rejections for port " + str(bad_port) + " and non-numeric text, and a match on "
            "Ok/Err for the absent key '" + missing + "'. Standard library only."
        )
        expected = (
            "Runs printing 'config error checks passed': lookups succeed for present keys, "
            "parse_port rejects " + str(bad_port) + " and 'abc' with the right variants, and "
            "the missing key '" + missing + "' formats as 'missing config key: " + missing + "'."
        )
        explain = _explain(
            purpose=("Model recoverable failures with a custom error enum, the ? operator "
                     "for early return, and match-based handling of Ok/Err outcomes."),
            approach=("A data-carrying enum with a Display impl, two Result-returning "
                      "functions (lookup, parse_port), and fn main asserting every branch: "
                      "unwrap_or_else for defaults, ? plus map_err for conversion, and a "
                      "match for terminal handling."),
            key_points=[
                "map_err converts the ParseIntError into the domain enum so ? can propagate it",
                "the ? operator returns early from parse_port on Err and unwraps Ok values",
                "deriving PartialEq on the error enum lets assert_eq! compare Result values directly",
                "Display is implemented by hand so err.to_string() produces a stable message",
            ],
            big_o_time="O(k) lookup over k table entries; O(1) for parsing",
            big_o_space="O(k) for the config table plus cloned Strings",
            edge_cases=[
                "port 0 and values above 65535 are rejected by the range guard, not by the parser",
                "a missing key formats its message from the requested key name, so the assertion is exact",
                "unwrap_or(8080) shows the fallback path although the sample port always parses",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "config_errors", "explain": explain},
            tags=["rust", "errors", "result"], variant="config_errors",
            seed=rng.randrange(2 ** 31),
        )

    def _result_propagation(self, rng: random.Random) -> Candidate:
        pool = ("latte", "scone", "muffin", "bagel", "croissant", "toast")
        items = rng.sample(pool, 3)
        prices = {name: rng.randint(2, 9) for name in items}
        cart = rng.sample(items, 2)
        unknown = rng.choice([p for p in pool if p not in items])
        total = sum(prices[name] for name in cart)
        menu_lit = ", ".join('("' + n + '", ' + str(prices[n]) + ")" for n in items)
        cart_lit = ", ".join('"' + n + '"' for n in cart)
        code = "\n".join([
            "#[derive(Debug, PartialEq)]",
            "enum ShopError {",
            "    EmptyCart,",
            "    UnknownItem(String),",
            "}",
            "",
            "fn find_price(menu: &[(&str, i64)], item: &str) -> Result<i64, ShopError> {",
            "    for &(name, price) in menu {",
            "        if name == item {",
            "            return Ok(price);",
            "        }",
            "    }",
            "    Err(ShopError::UnknownItem(String::from(item)))",
            "}",
            "",
            "fn checkout(menu: &[(&str, i64)], cart: &[&str]) -> Result<i64, ShopError> {",
            "    if cart.is_empty() {",
            "        return Err(ShopError::EmptyCart);",
            "    }",
            "    let mut total = 0;",
            "    for &item in cart {",
            "        total += find_price(menu, item)?;",
            "    }",
            "    Ok(total)",
            "}",
            "",
            "fn main() {",
            "    let menu = vec![" + menu_lit + "];",
            "    let cart = vec![" + cart_lit + "];",
            "    match checkout(&menu, &cart) {",
            "        Ok(sum) => assert_eq!(sum, " + str(total) + "),",
            '        Err(err) => panic!("unexpected error: {:?}", err),',
            "    }",
            "    match checkout(&menu, &[]) {",
            '        Ok(_) => panic!("empty cart must fail"),',
            "        Err(err) => assert_eq!(err, ShopError::EmptyCart),",
            "    }",
            '    match checkout(&menu, &["' + cart[0] + '", "' + unknown + '"]) {',
            '        Ok(_) => panic!("unknown item must fail"),',
            "        Err(err) => assert_eq!(err, ShopError::UnknownItem(String::from(\"" + unknown + "\"))),",
            "    }",
            '    println!("result propagation checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program where errors propagate through call layers: "
            "find_price looks an item up in a menu slice and returns Result<i64, ShopError>, "
            "checkout sums a cart of items and forwards failures with the ? operator, "
            "distinguishing EmptyCart from UnknownItem(String). fn main must match on "
            "Ok/Err three times: the valid cart [" + ", ".join(cart) + "] totals " + str(total) +
            ", an empty cart fails with EmptyCart, and an unknown item '" + unknown + "' fails "
            "with UnknownItem. Standard library only."
        )
        expected = (
            "Runs printing 'result propagation checks passed': the valid cart totals " +
            str(total) + ", and both failure branches surface the exact ShopError variant."
        )
        explain = _explain(
            purpose=("Show error propagation across a two-layer call chain with ?, and "
                     "terminal handling of each error variant with match."),
            approach=("A leaf lookup returns Result, an aggregate function forwards leaf "
                      "errors with ? and adds its own guard, and fn main pattern-matches "
                      "each outcome into an assertion."),
            key_points=[
                "? inside the summing loop aborts checkout on the first unknown item",
                "the enum carries the offending item name, so Err values are self-describing",
                "for &(name, price) destructures the slice of tuple references via match ergonomics",
                "assert_eq! on the enum requires only derived PartialEq and Debug",
            ],
            big_o_time="O(len(cart) * len(menu)) linear scans",
            big_o_space="O(1) beyond the input slices and one owned String per failure",
            edge_cases=[
                "an empty cart is rejected before any lookup happens",
                "the unknown-item error embeds the exact name, asserted via String::from",
                "duplicate cart entries simply add their price twice; no dedup is applied",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "result_propagation", "explain": explain},
            tags=["rust", "errors", "propagation"], variant="result_propagation",
            seed=rng.randrange(2 ** 31),
        )

    def _option_chain(self, rng: random.Random) -> Candidate:
        probe_key = rng.choice(("retries", "max_conn", "batch_size"))
        probe_val = rng.randint(2, 9)
        timeout_val = rng.choice((1200, 1500, 2400))
        factor = rng.choice((2, 10, 100))
        fallback = rng.randint(1, 9)
        coarse = timeout_val // 100
        code = "\n".join([
            "// Option combinators turn a missing lookup into a default instead of a panic.",
            "fn setting_value(settings: &[(&str, i64)], key: &str) -> Option<i64> {",
            "    for &(name, value) in settings {",
            "        if name == key {",
            "            return Some(value);",
            "        }",
            "    }",
            "    None",
            "}",
            "",
            "fn main() {",
            "    let settings = [(\"" + probe_key + "\", " + str(probe_val) + "), (\"timeout_ms\", " + str(timeout_val) + ")];",
            '    let scaled = setting_value(&settings, "' + probe_key + '").map(|v| v * ' + str(factor) + ').unwrap_or(' + str(fallback) + ');',
            "    assert_eq!(scaled, " + str(probe_val * factor) + ");",
            '    let defaulted = setting_value(&settings, "workers").map(|v| v + 1).unwrap_or(' + str(fallback) + ');',
            "    assert_eq!(defaulted, " + str(fallback) + ");",
            '    let coarse = setting_value(&settings, "timeout_ms").map_or(0, |v| v / 100);',
            "    assert_eq!(coarse, " + str(coarse) + ");",
            "    let large: Vec<i64> = settings.iter().filter(|s| s.1 > 100).map(|s| s.1).collect();",
            "    assert_eq!(large, vec![" + str(timeout_val) + "]);",
            '    println!("option combinator checks passed");',
            "}",
        ])
        task = (
            "Write a single-file Rust program that replaces panics with Option combinators: "
            "a helper setting_value scans a slice of (name, value) tuples and returns "
            "Option<i64>, and fn main must derive values through map, map_or and unwrap_or "
            "instead of unwrap: key '" + probe_key + "' scales to " + str(probe_val * factor) +
            " (factor " + str(factor) + "), the absent key 'workers' falls back to " +
            str(fallback) + ", timeout_ms " + str(timeout_val) + " coarsens to " + str(coarse) +
            " hundred-ms units, and a filter/map/collect chain keeps only values above 100. "
            "Standard library only."
        )
        expected = (
            "Runs printing 'option combinator checks passed' with scaled=" + str(probe_val * factor) +
            ", defaulted=" + str(fallback) + ", coarse=" + str(coarse) + " and the filtered "
            "list [" + str(timeout_val) + "]."
        )
        explain = _explain(
            purpose=("Demonstrate Option as a first-class value: lookups return Option<i64> "
                     "and combinators (map, map_or, unwrap_or) express defaults without "
                     "panic-prone unwrap."),
            approach=("A linear scan returns Some/None; fn main chains combinators over the "
                      "results and asserts both the present-key and missing-key paths plus "
                      "an iterator filter/map/collect pipeline."),
            key_points=[
                "map transforms the payload inside Some and leaves None untouched",
                "unwrap_or supplies a default exactly when the lookup returns None",
                "map_or combines the default and transform into one call: map_or(0, |v| v / 100)",
                "s.1 in iterator closures reads tuple fields through nested references",
            ],
            big_o_time="O(k) per lookup over k settings; O(k) for the filter chain",
            big_o_space="O(1) per lookup, O(k) for the collected Vec",
            edge_cases=[
                "the key 'workers' is deliberately absent, exercising the unwrap_or default",
                "the threshold 100 cleanly separates the small probe value from the large timeout value",
                "map_or(0, ...) would coarsen a missing timeout to 0 instead of failing",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "option_chain", "explain": explain},
            tags=["rust", "errors", "option"], variant="option_chain",
            seed=rng.randrange(2 ** 31),
        )


class RustProjectFamily(Family):
    """Multi-file Rust binary project: main.rs + utils.rs (`mod utils;`)
    + README.md documenting the cargo mapping."""

    NAME = "rust_project_multifile"
    LANGUAGE = "rust"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    PROJECT_NAMES = ("inventory-core", "metrics-lite", "textkit")

    def generate(self, rng: random.Random) -> Candidate:
        name = rng.choice(self.PROJECT_NAMES)
        stock = [rng.randint(1, 99) for _ in range(rng.randint(5, 9) * 2 + 1)]  # odd length
        med = sorted(stock)[len(stock) // 2]
        probe = rng.randint(20, 80)
        low = rng.randint(1, 19)
        high = rng.randint(81, 99)
        under = rng.randint(0, low - 1)   # strictly below the clamp window
        over = rng.randint(high + 1, 150)  # strictly above the clamp window
        extra_kind = rng.choice(("shout", "vowels", "sum_even"))
        extra_fn, extra_utils, extra_asserts = self._extra_helpers(extra_kind, rng)

        utils = "\n".join([
            "//! Helper module for the " + name + " demo project.",
            "",
            "/// Restrict a value to the inclusive range [low, high].",
            "pub fn clamp(value: i64, low: i64, high: i64) -> i64 {",
            "    if value < low {",
            "        low",
            "    } else if value > high {",
            "        high",
            "    } else {",
            "        value",
            "    }",
            "}",
            "",
            "/// Statistical median; None for empty input. Even lengths average the",
            "/// two central values with truncating integer division.",
            "pub fn median(values: &[i64]) -> Option<i64> {",
            "    if values.is_empty() {",
            "        return None;",
            "    }",
            "    let mut sorted: Vec<i64> = values.to_vec();",
            "    sorted.sort();",
            "    let mid = sorted.len() / 2;",
            "    if sorted.len() % 2 == 1 {",
            "        Some(sorted[mid])",
            "    } else {",
            "        Some((sorted[mid - 1] + sorted[mid]) / 2)",
            "    }",
            "}",
            "",
            extra_utils,
        ])
        main_rs = "\n".join([
            "mod utils;",
            "",
            "fn main() {",
            "    let stock = " + _vec(stock) + ";",
            "    assert_eq!(utils::median(&stock), Some(" + str(med) + "));",
            "    assert_eq!(utils::median(&[]), None);",
            "    assert_eq!(utils::clamp(" + str(probe) + ", " + str(low) + ", " + str(high) + "), " + str(probe) + ");",
            "    assert_eq!(utils::clamp(" + str(under) + ", " + str(low) + ", " + str(high) + "), " + str(low) + ");",
            "    assert_eq!(utils::clamp(" + str(over) + ", " + str(low) + ", " + str(high) + "), " + str(high) + ");"
        ] + extra_asserts + [
            '    println!("project self-checks passed");',
            "}",
        ])
        fn_list = "clamp, median" + extra_fn
        readme = "\n".join([
            "# " + name + " demo project",
            "",
            "A two-file Rust binary that mirrors a cargo project layout.",
            "",
            "## Files",
            "",
            "- main.rs: binary entry point; declares `mod utils;` and runs deterministic",
            "  assert_eq! self-checks against the helper module",
            "- utils.rs: library module exposing public helpers: " + fn_list,
            "",
            "## Mapping to a cargo project",
            "",
            "1. run `cargo new " + name + "`",
            "2. copy main.rs to src/main.rs and utils.rs to src/utils.rs",
            "3. `cargo run` compiles both files and executes the self-checks",
            "4. `cargo build` succeeds with zero external crates: only std is used",
            "",
            "## Extending",
            "",
            "Keep helpers public and side-effect free in utils.rs, then add a tests",
            "module at the bottom of src/utils.rs; the self-checks in main stay as a",
            "smoke gate for `cargo run`.",
        ])
        files = [
            FileSpec("main.rs", main_rs),
            FileSpec("utils.rs", utils),
            FileSpec("README.md", readme),
        ]
        task = (
            "Build the multi-file Rust binary project '" + name + "' exactly as the README "
            "describes: main.rs declares `mod utils;` and runs deterministic assert_eq! "
            "self-checks, while utils.rs exposes the public helpers clamp, median" + extra_fn +
            " used on a stock vector of " + str(len(stock)) + " readings (median " + str(med) +
            ", clamp window [" + str(low) + ", " + str(high) + "]). The README must document "
            "how the two files map into a cargo project under src/. Standard library only."
        )
        extra_phrase = {
            "shout": " and the shout helper appends its exclamation mark",
            "vowels": " and the vowel counter matches its sample word",
            "sum_even": " and the even-sum helper folds its sample slice",
        }[extra_kind]
        expected = (
            "cargo run would print 'project self-checks passed': median of the odd-length "
            "stock vector is " + str(med) + ", empty input maps to None, clamp pins to the "
            "window bounds at both ends" + extra_phrase + "."
        )
        explain = _explain(
            purpose=("Demonstrate the canonical two-file Rust binary layout: a library "
                     "module (utils.rs) with pub helpers and a thin binary (main.rs) that "
                     "declares mod utils and smoke-tests it."),
            approach=("Binary/module split with pub fn helpers; fn main gates every helper "
                      "with assert_eq! so cargo run doubles as a smoke test; the README "
                      "documents the exact cargo mapping."),
            key_points=[
                "mod utils; pulls the sibling utils.rs into the binary crate as namespace utils",
                "pub is required on helpers, otherwise main.rs cannot reach them across the module boundary",
                "median returns Option<i64> so the empty case is encoded in the type instead of panicking",
                "assert_eq! on Option<i64> reads as a value-level specification of the helper",
            ],
            big_o_time="O(n log n) for median due to sorting; O(1) for clamp",
            big_o_space="O(n) for the sorted copy inside median",
            edge_cases=[
                "median of an empty slice returns None instead of indexing",
                "clamp pins to low/high exactly at the boundaries because comparisons are strict",
                "the stock vector length is forced odd so the tested median never uses the even-branch division",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, files=files,
            entry="main.rs", verify_method="static_check", is_project=True,
            notes={"project": name, "extra_helper": extra_kind, "explain": explain},
            tags=["rust", "project", "modules"], variant=name,
            seed=rng.randrange(2 ** 31),
        )

    def _extra_helpers(self, kind: str, rng: random.Random):
        """Return (suffix-for-prose, utils-snippet, main-assert-lines) per variant."""
        if kind == "shout":
            utils = "\n".join([
                "/// Append an exclamation mark to a borrowed slice, returning an owned String.",
                "pub fn shout(text: &str) -> String {",
                "    let mut owned = String::from(text);",
                "    owned.push('!');",
                "    owned",
                "}",
            ])
            word = rng.choice(("ready", "steady", "launch"))
            asserts = ['    assert_eq!(utils::shout("' + word + '"), "' + word + '!");']
            return ", shout", utils, asserts
        if kind == "vowels":
            utils = "\n".join([
                "/// Count ASCII vowels in a borrowed string slice.",
                "pub fn count_vowels(text: &str) -> usize {",
                '    text.chars().filter(|c| "aeiou".contains(*c)).count()',
                "}",
            ])
            word = rng.choice(("inventory", "metrics", "telemetry"))
            count = sum(1 for ch in word if ch in "aeiou")
            asserts = ["    assert_eq!(utils::count_vowels(\"" + word + "\"), " + str(count) + ");",
                       "    assert_eq!(utils::count_vowels(\"\"), 0);"]
            return ", count_vowels", utils, asserts
        utils = "\n".join([
            "/// Sum the even values of a borrowed slice.",
            "pub fn sum_even(values: &[i64]) -> i64 {",
            "    values.iter().filter(|v| *v % 2 == 0).sum()",
            "}",
        ])
        evens = [rng.randint(1, 40) * 2 for _ in range(rng.randint(2, 4))]
        odds = [rng.randint(1, 40) * 2 + 1 for _ in range(rng.randint(1, 3))]
        mixed = evens + odds
        rng.shuffle(mixed)
        asserts = ["    assert_eq!(utils::sum_even(&[" + ", ".join(str(v) for v in mixed) + "]), " + str(sum(evens)) + ");",
                   "    assert_eq!(utils::sum_even(&[]), 0);"]
        return ", sum_even", utils, asserts


register(globals(), RustOwnershipBasics)
register(globals(), RustErrorHandling)
register(globals(), RustProjectFamily)
