"""Dataset-1 write families for PHP 8 (STATIC verification only).

Per CONTRACT.md there is no PHP toolchain in this environment, so every
candidate carries verify_method="static_check". The static validator
(validators/executors/static_check.py::check_generic_code) enforces:
  * balanced {} and () across the whole artifact,
  * a <?php tag and at least one $variable,
  * no TODO/FIXME/placeholder/lorem tokens, minimum length 120 chars.
Families therefore emit conservative, canonical PHP 8:
declare(strict_types=1), typed signatures, PDO prepared statements,
filter_var validation and password_hash/password_verify for anything
credential-shaped (safe-by-construction, defensive only).

Determinism: every random decision flows from the rng passed to generate().
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register


def _fill(template: str, **kw) -> str:
    """Substitute {token} placeholders; literal PHP braces stay untouched."""
    out = template
    for key, value in kw.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _explain(purpose, approach, key_points, big_o_time, big_o_space, edge_cases):
    return {
        "purpose": purpose,
        "approach": approach,
        "key_points": key_points,
        "big_o_time": big_o_time,
        "big_o_space": big_o_space,
        "edge_cases": edge_cases,
    }


class PhpPdoDefensiveFamily(Family):
    """PDO prepared statements plus input validation, hash-safe logins."""
    NAME = "php_pdo_defensive"
    LANGUAGE = "php"
    DOMAIN = "security"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "code_review", "security")

    KINDS = ("fetch_by_email", "register_account", "verify_login")

    TABLES = ("accounts", "members", "subscribers")
    HASH_CONSTS = ("DUMMY_HASH", "DECOY_HASH", "SHADOW_HASH")

    # ------------------------------------------------------------------ build
    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "fetch_by_email":
            return self._build_fetch(kind, rng)
        if kind == "register_account":
            return self._build_register(kind, rng)
        return self._build_login(kind, rng)

    def _build_fetch(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["findAccountByEmail", "fetchActiveAccount",
                         "locateMemberByEmail"])
        table = rng.choice(self.TABLES)
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/**\n"
            " * Fetch one active account row by email using a prepared statement.\n"
            " * Malformed addresses never reach SQL: validation gates the query.\n"
            " */\n"
            "function {fn}(PDO $pdo, string $email): ?array\n"
            "{\n"
            "    $candidate = strtolower(trim($email));\n"
            "    if (filter_var($candidate, FILTER_VALIDATE_EMAIL) === false) {\n"
            "        return null;\n"
            "    }\n"
            "    $sql = 'SELECT id, email, display_name FROM {table}'\n"
            "         . ' WHERE email = :email AND is_active = 1';\n"
            "    $stmt = $pdo->prepare($sql);\n"
            "    $stmt->execute([':email' => $candidate]);\n"
            "    $row = $stmt->fetch(PDO::FETCH_ASSOC);\n"
            "    if ($row === false) {\n"
            "        return null;\n"
            "    }\n"
            "    return [\n"
            "        'id' => (int) $row['id'],\n"
            "        'email' => (string) $row['email'],\n"
            "        'display_name' => (string) $row['display_name'],\n"
            "    ];\n"
            "}\n",
            fn=fn, table=table)
        task = (f"Write a PHP 8 function `{fn}(PDO $pdo, string $email): ?array` "
                f"that returns the single active row of the `{table}` table whose "
                f"email matches the caller's input. Addresses must be trimmed and "
                f"lowercased first, checked with filter_var(FILTER_VALIDATE_EMAIL), "
                f"and the database lookup must use a PDO prepared statement with a "
                f"named parameter. Return null for invalid input or when no row "
                f"matches, and cast id to int in the returned array.")
        expected = (f"A valid, known email returns its id/email/display_name triple; "
                    f"a malformed address or an unknown one returns null without "
                    f"ever interpolating caller text into the SQL string.")
        explain = _explain(
            expected,
            "Normalise the address, gate it behind filter_var, then run one "
            "prepared SELECT with a bound named parameter and shape the row.",
            ["the value travels as a bound parameter, so quotes in input can "
             "never change the statement's structure",
             "filter_var rejects malformed addresses before any I/O happens",
             "fetch() returning false is mapped to null so callers get one "
             "consistent no-result shape"],
            "O(1) for the index lookup the driver performs", "O(1)",
            ["an empty or malformed email returns null without touching the DB",
             "a matching row that is deactivated (is_active = 0) is invisible",
             "trailing whitespace and uppercase letters are normalised away"])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    def _build_register(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["registerAccount", "createSignup", "openNewMember"])
        table = rng.choice(self.TABLES)
        min_len = rng.choice([10, 12, 14])
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/**\n"
            " * Create an account with server-side validation and a modern\n"
            " * password hash. Never stores or logs the plaintext password.\n"
            " */\n"
            "function {fn}(PDO $pdo, string $email, string $password): array\n"
            "{\n"
            "    $email = strtolower(trim($email));\n"
            "    $errors = [];\n"
            "    if (filter_var($email, FILTER_VALIDATE_EMAIL) === false) {\n"
            "        $errors[] = 'email address is not valid';\n"
            "    }\n"
            "    if (strlen($password) < {min_len}) {\n"
            "        $errors[] = 'password must be at least {min_len} characters';\n"
            "    }\n"
            "    if ($errors !== []) {\n"
            "        return ['ok' => false, 'errors' => $errors];\n"
            "    }\n"
            "    $hash = password_hash($password, PASSWORD_DEFAULT);\n"
            "    $sql = 'INSERT INTO {table} (email, password_hash, created_at)'\n"
            "         . \" VALUES (:email, :password_hash, NOW())\";\n"
            "    $stmt = $pdo->prepare($sql);\n"
            "    $stmt->execute([':email' => $email, ':password_hash' => $hash]);\n"
            "    return ['ok' => true, 'id' => (int) $pdo->lastInsertId()];\n"
            "}\n",
            fn=fn, table=table, min_len=min_len)
        task = (f"Implement a PHP 8 registration routine `{fn}(PDO $pdo, string "
                f"$email, string $password): array` that validates the email with "
                f"filter_var, requires passwords of at least {min_len} characters, "
                f"collects every violation into an errors array, and on success "
                f"stores password_hash($password, PASSWORD_DEFAULT) in the "
                f"`{table}` table through a PDO prepared INSERT. Return "
                f"{{ok: false, errors}} for invalid input and "
                f"{{ok: true, id}} with lastInsertId otherwise. The plaintext "
                f"password must never be stored or logged.")
        expected = (f"Invalid emails or short passwords return every violation at "
                    f"once; valid input inserts a bcrypt/argon2 hash (never the "
                    f"plaintext) and reports the new row id.")
        explain = _explain(
            expected,
            "Validate first and aggregate all errors, then hash with "
            "password_hash and insert through a prepared statement.",
            ["password_hash uses PASSWORD_DEFAULT, so the algorithm can be "
             "upgraded without touching call sites",
             "all violations are collected before returning, which keeps form "
             "round-trips cheap for users",
             "the INSERT is fully parameterised; email content cannot break out"],
            "O(1) apart from the hash cost", "O(1)",
            ["duplicate emails surface as a driver constraint failure the "
             "caller can catch and translate",
             "a password of exactly the minimum length is accepted",
             "emails with plus-addressing or unusual but legal characters pass "
             "filter_var and are stored lowercased"])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    def _build_login(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["checkCredentials", "verifyLogin", "attemptSignIn"])
        const = rng.choice(self.HASH_CONSTS)
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "const {const} = '$2y$10$usesomesillystringfore7hnbRJHxXVLeakoG8K30oukPsA.ztMG';\n\n"
            "/**\n"
            " * Constant-work credential check: a missing account still burns one\n"
            " * password_verify call, so response timing cannot enumerate users.\n"
            " */\n"
            "function {fn}(?array $account, string $password): array\n"
            "{\n"
            "    $hash = is_array($account) && isset($account['password_hash'])\n"
            "        ? (string) $account['password_hash']\n"
            "        : {const};\n"
            "    if (!password_verify($password, $hash)) {\n"
            "        return ['ok' => false, 'rehash' => false];\n"
            "    }\n"
            "    $needsRehash = password_needs_rehash($hash, PASSWORD_DEFAULT);\n"
            "    return ['ok' => true, 'rehash' => $needsRehash];\n"
            "}\n",
            fn=fn, const=const)
        task = (f"Write a PHP 8 login helper `{fn}(?array $account, string "
                f"$password): array` that verifies the password against the "
                f"account's stored hash with password_verify. When the account is "
                f"null or has no hash, verify against a fixed dummy hash instead "
                f"so timing cannot reveal which emails exist. Return "
                f"{{ok: false, rehash: false}} on mismatch and "
                f"{{ok: true, rehash: bool}} on success, where rehash reports "
                f"password_needs_rehash against PASSWORD_DEFAULT.")
        expected = ("Any wrong password fails identically whether or not the "
                    "account exists; a correct password succeeds and flags rows "
                    "hashed with an outdated algorithm for rehashing.")
        explain = _explain(
            expected,
            "Pick the real hash or a fixed decoy, run password_verify exactly "
            "once, and report whether the stored hash needs rehashing.",
            ["the dummy-hash branch equalises work between hit and miss paths, "
             "closing a user-enumeration timing side channel",
             "password_verify reads the algorithm and salt from the stored "
             "hash, so no separate salt column is needed",
             "the rehash flag lets the caller upgrade legacy hashes on the "
             "next successful login"],
            "O(1) (one hash verification)", "O(1)",
            ["an account row without a password_hash key is treated as unknown",
             "empty passwords are still passed through password_verify, which "
             "rejects them against any real hash",
             "legacy md5-era hashes verify as false and never leak errors"])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    # --------------------------------------------------------------- generate
    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="php", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], verify_method="static_check",
            notes={"kind": kind, "function_name": b["fn"],
                   "explain": b["explain"]},
            tags=["php", "pdo", "security", kind], variant=kind,
            seed=rng.randrange(2 ** 31))

    def review_variant(self, rng: random.Random):
        """Working but SQL-injectable sibling of the fetch kind."""
        b = self._build("fetch_by_email", rng)
        fn = b["fn"]
        table = rng.choice(self.TABLES)
        unsafe = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/** Looks up an account by email (review variant: builds SQL by\n"
            " * concatenation). */\n"
            "function {fn}(PDO $pdo, string $email): ?array\n"
            "{\n"
            "    $candidate = strtolower(trim($email));\n"
            "    $sql = \"SELECT id, email, display_name FROM {table}\"\n"
            "         . \" WHERE email = '\" . $candidate . \"' AND is_active = 1\";\n"
            "    $row = $pdo->query($sql)->fetch(PDO::FETCH_ASSOC);\n"
            "    return $row === false ? null : $row;\n"
            "}\n",
            fn=fn, table=table)
        cand = Candidate(
            family=self.NAME, language="php", domain=self.DOMAIN,
            difficulty="intermediate",
            task=b["task"], expected_behavior=b["expected"],
            code=unsafe, verify_method="static_check",
            notes={"kind": "fetch_by_email", "function_name": fn,
                   "explain": b["explain"], "review": "sql_concatenation"},
            tags=["php", "pdo", "security", "review"],
            variant="fetch_by_email|review", seed=rng.randrange(2 ** 31))
        issues = [
            {"kind": "security", "severity": "high",
             "why": "caller-controlled text is concatenated straight into the SQL "
                    "string, so an email like x' OR 1=1 -- rewrites the query",
             "better": "use a prepared statement with a named :email parameter "
                       "and execute([$candidate])"},
            {"kind": "validation", "severity": "medium",
             "why": "the FILTER_VALIDATE_EMAIL gate was dropped, so junk input "
                    "now reaches the database at all",
             "better": "keep the filter_var check before any query is built"},
            {"kind": "style", "severity": "low",
             "why": "query() runs on every call even though the statement shape "
                    "is constant, discarding driver-level statement reuse",
             "better": "prepare() once per request and rely on the driver's "
                       "statement cache"},
        ]
        return cand, issues


class PhpArraysStringsFamily(Family):
    """array_map/filter/reduce idioms, assoc aggregation, text pipelines."""
    NAME = "php_arrays_strings"
    LANGUAGE = "php"
    DOMAIN = "data_structures"
    DIFFICULTIES = ("beginner", "intermediate", "advanced")
    SUPPORTS = ("explanation", "testing", "code_review", "complexity")

    KINDS = ("clean_tags", "totals_by_key", "top_words")

    KIND_DOMAINS = {
        "clean_tags": "data_structures",
        "totals_by_key": "data_structures",
        "top_words": "text_processing",
    }

    # ------------------------------------------------------------------ build
    def _build(self, kind: str, rng: random.Random) -> dict:
        if kind == "clean_tags":
            return self._build_clean_tags(kind, rng)
        if kind == "totals_by_key":
            return self._build_totals(kind, rng)
        return self._build_top_words(kind, rng)

    def _build_clean_tags(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["cleanTagList", "normaliseTags", "tidyLabels"])
        separator = rng.choice([", ", " | ", "; "])
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/**\n"
            " * Clean a raw tag list: trim each entry, drop empties, dedupe\n"
            " * case-insensitively, and join the survivors for display.\n"
            " */\n"
            "function {fn}(array $tags): string\n"
            "{\n"
            "    $trimmed = array_map(\n"
            "        static fn (string $tag): string => trim($tag),\n"
            "        $tags\n"
            "    );\n"
            "    $kept = array_values(\n"
            "        array_filter($trimmed, static fn (string $tag): bool => $tag !== '')\n"
            "    );\n"
            "    $lowered = array_map('strtolower', $kept);\n"
            "    $unique = array_values(array_unique($lowered));\n"
            "    return implode('{sep}', $unique);\n"
            "}\n",
            fn=fn, sep=separator)
        task = (f"Implement a PHP 8 helper `{fn}(array $tags): string` that takes a "
                f"list of raw tag strings, trims whitespace from each entry, drops "
                f"empty ones, removes case-insensitive duplicates while keeping the "
                f"first occurrence order, lowercases what remains, and returns the "
                f"tags joined with '{separator.strip()}'. Use the array_map, "
                f"array_filter and array_unique idioms with arrow functions.")
        expected = ("Whitespace-padded and mixed-case duplicates collapse to a "
                    "single lowercase entry; ordering follows first appearance.")
        explain = _explain(
            expected,
            "Three array passes (map, filter, unique) followed by implode keep "
            "each step single-purpose and readable.",
            ["arrow functions keep the callbacks one line and scope-tight",
             "array_values re-indexes after filter/unique so the result is a "
             "clean list, not a sparse map",
             "strtolower before array_unique makes the dedupe case-insensitive "
             "without custom comparison"],
            "O(n)", "O(n)",
            ["an empty input array yields an empty string",
             "input of only whitespace entries collapses to an empty string",
             "'PHP' and 'php' keep only the position of the first sighting"])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    def _build_totals(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["totalsByCategory", "sumAmountsPerGroup",
                         "aggregateByKey"])
        key_field = rng.choice(["category", "department", "bucket"])
        amount_field = rng.choice(["amount", "cost", "minutes"])
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/**\n"
            " * Sum numeric {amount_field} values per {key_field} from rows shaped\n"
            " * like ['{key_field}' => string, '{amount_field}' => float].\n"
            " * Returns an alphabetically sorted associative array.\n"
            " */\n"
            "function {fn}(array $rows): array\n"
            "{\n"
            "    $totals = [];\n"
            "    foreach ($rows as $row) {\n"
            "        $key = (string) $row['{key_field}'];\n"
            "        $totals[$key] = ($totals[$key] ?? 0.0) + (float) $row['{amount_field}'];\n"
            "    }\n"
            "    ksort($totals);\n"
            "    return $totals;\n"
            "}\n",
            fn=fn, key_field=key_field, amount_field=amount_field)
        task = (f"Write a PHP 8 aggregator `{fn}(array $rows): array`. Each row is "
                f"an associative array with a '{key_field}' string and a "
                f"'{amount_field}' numeric value; the function returns one summed "
                f"total per distinct {key_field}, sorted alphabetically by key. "
                f"Missing keys must not warn, and numeric strings must be accepted "
                f"via casts. Use the $totals[$key] = ($totals[$key] ?? 0.0) + ... "
                f"idiom and ksort for the final ordering.")
        expected = ("Every distinct key gets exactly one entry holding the sum of "
                    "its amounts; keys emerge in alphabetical order regardless of "
                    "input order.")
        explain = _explain(
            expected,
            "One accumulating pass with the null-coalescing default, then ksort "
            "to impose the output ordering.",
            ["the ?? 0.0 default turns first sight and later additions into the "
             "same expression",
             "explicit casts make rows from JSON or CSV input safe to add",
             "ksort guarantees a deterministic, caller-friendly key order"],
            "O(n log n) dominated by the final ksort", "O(k) for k distinct keys",
            ["an empty rows array returns an empty array",
             "negative amounts simply subtract from their bucket",
             "keys are taken verbatim, so ' ops' and 'ops' stay separate "
             "buckets"])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    def _build_top_words(self, kind: str, rng: random.Random) -> dict:
        fn = rng.choice(["topWords", "mostFrequentWords", "wordLeaderboard"])
        limit = rng.choice([3, 5])
        code = _fill(
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/**\n"
            " * Return the {limit} most frequent words of a text, lowercase and\n"
            " * stripped of basic punctuation, as [word => count] with counts\n"
            " * descending.\n"
            " */\n"
            "function {fn}(string $text, int $limit = {limit}): array\n"
            "{\n"
            "    $cleaned = str_replace([',', '.', '!', '?', ';', ':'], '', $text);\n"
            "    $lower = strtolower($cleaned);\n"
            "    $words = preg_split('/\\\\s+/', trim($lower), -1, PREG_SPLIT_NO_EMPTY);\n"
            "    if ($words === false || $words === []) {\n"
            "        return [];\n"
            "    }\n"
            "    $counts = array_count_values($words);\n"
            "    arsort($counts);\n"
            "    return array_slice($counts, 0, $limit, true);\n"
            "}\n",
            fn=fn, limit=limit)
        task = (f"Implement a PHP 8 text analyser `{fn}(string $text, int $limit = "
                f"{limit}): array` that removes the punctuation characters , . ! ? "
                f"; : , lowercases the remainder, splits on whitespace runs, counts "
                f"words with array_count_values, sorts by count descending with "
                f"arsort, and returns at most $limit entries preserving word => "
                f"count keys. Empty or punctuation-only input returns an empty "
                f"array.")
        expected = ("The most frequent lowercase words surface first with exact "
                    "counts; at most {limit} entries are returned even for long "
                    "texts.".replace("{limit}", str(limit)))
        explain = _explain(
            expected,
            "Normalise, split, count, sort descending, slice - each stage is a "
            "single stdlib call.",
            ["str_replace with an array handles all punctuation in one call",
             "PREG_SPLIT_NO_EMPTY plus trim keeps whitespace-only input from "
             "producing phantom words",
             "the preserve-keys form of array_slice keeps word => count "
             "association intact"],
            "O(n log n) for the sort over distinct words", "O(n)",
            ["punctuation-only input yields an empty array",
             "words tied in frequency keep array_count_values' first-seen order",
             "the $limit defaults to {limit} but callers may raise or lower it"
             .replace("{limit}", str(limit))])
        return dict(kind=kind, fn=fn, code=code, task=task, expected=expected,
                    explain=explain)

    # --------------------------------------------------------------- generate
    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(self.KINDS)
        b = self._build(kind, rng)
        return Candidate(
            family=self.NAME, language="php", domain=self.KIND_DOMAINS[kind],
            difficulty=rng.choice(self.DIFFICULTIES),
            task=b["task"], expected_behavior=b["expected"],
            code=b["code"], verify_method="static_check",
            notes={"kind": kind, "function_name": b["fn"],
                   "explain": b["explain"]},
            tags=["php", "arrays", kind], variant=kind,
            seed=rng.randrange(2 ** 31))

    def review_variant(self, rng: random.Random):
        """Working but quadratic aggregation for review practice."""
        b = self._build("totals_by_key", rng)
        fn = b["fn"]
        naive = (
            "<?php\n\n"
            "declare(strict_types=1);\n\n"
            "/** Per-key totals (review variant: rescans the rows per key). */\n"
            "function " + fn + "(array $rows): array\n"
            "{\n"
            "    $keys = [];\n"
            "    foreach ($rows as $row) {\n"
            "        $key = (string) $row['category'];\n"
            "        if (!in_array($key, $keys, true)) {\n"
            "            $keys[] = $key;\n"
            "        }\n"
            "    }\n"
            "    $totals = [];\n"
            "    foreach ($keys as $key) {\n"
            "        $sum = 0.0;\n"
            "        foreach ($rows as $row) {\n"
            "            if ((string) $row['category'] === $key) {\n"
            "                $sum += (float) $row['amount'];\n"
            "            }\n"
            "        }\n"
            "        $totals[$key] = $sum;\n"
            "    }\n"
            "    ksort($totals);\n"
            "    return $totals;\n"
            "}\n")
        cand = Candidate(
            family=self.NAME, language="php", domain=self.DOMAIN,
            difficulty="intermediate",
            task=b["task"], expected_behavior=b["expected"],
            code=naive, verify_method="static_check",
            notes={"kind": "totals_by_key", "function_name": fn,
                   "explain": b["explain"], "review": "nested_rescan"},
            tags=["php", "arrays", "review"],
            variant="totals_by_key|review", seed=rng.randrange(2 ** 31))
        issues = [
            {"kind": "efficiency", "severity": "medium",
             "why": "the rows array is rescanned once per distinct key, making "
                    "the work O(n * k) instead of one O(n) accumulation pass",
             "better": "accumulate into $totals[$key] inside a single foreach "
                       "using the ?? 0.0 default"},
            {"kind": "repeated_computation", "severity": "low",
             "why": "the key is cast and compared repeatedly in both passes "
                    "rather than derived once per row",
             "better": "derive $key once inside one loop and use it for both "
                       "bookkeeping and accumulation"},
            {"kind": "style", "severity": "low",
             "why": "in_array with strict mode over a growing list is a manual "
                    "re-implementation of set semantics",
             "better": "let the accumulator array itself record which keys "
                       "already exist via isset"},
        ]
        return cand, issues


class PhpProjectFamily(Family):
    """Multi-file PHP project: index.php + lib/helpers.php + README.md."""
    NAME = "php_project_multifile"
    LANGUAGE = "php"
    DOMAIN = "web"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    PROJECTS = ("orders_summary", "contact_book", "quiz_scorer")

    # ------------------------------------------------------------------ build
    def _build(self, proj: str, rng: random.Random):
        if proj == "orders_summary":
            customers = rng.sample(["Alda", "Brecht", "Ceyda", "Dov", "Esme"],
                                   rng.randint(3, 4))
            items = ["notebook", "pencil set", "desk lamp", "stapler", "ink bottle"]
            rows = [{"customer": rng.choice(customers),
                     "item": rng.choice(items),
                     "qty": rng.randint(1, 4),
                     "amount": round(rng.uniform(2, 20), 2)} for _ in range(4)]
            rows_js = ",\n            ".join(
                "['customer' => '{c}', 'item' => '{i}', 'qty' => {q}, "
                "'amount' => {a}]".replace("{c}", r["customer"])
                .replace("{i}", r["item"]).replace("{q}", str(r["qty"]))
                .replace("{a}", str(r["amount"])) for r in rows)
            helpers = _fill(
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "/** In-memory sample rows consumed by the demo entry point. */\n"
                "function sampleOrders(): array\n"
                "{\n"
                "    return [\n"
                "            {rows},\n"
                "    ];\n"
                "}\n\n"
                "/** Line total for one order row: quantity times unit amount. */\n"
                "function lineTotal(array $row): float\n"
                "{\n"
                "    return (float) $row['qty'] * (float) $row['amount'];\n"
                "}\n\n"
                "/** Grand total across every order row, rounded to 2 decimals. */\n"
                "function orderTotal(array $rows): float\n"
                "{\n"
                "    $total = 0.0;\n"
                "    foreach ($rows as $row) {\n"
                "        $total += lineTotal($row);\n"
                "    }\n"
                "    return round($total, 2);\n"
                "}\n\n"
                "/** Per-customer totals, keys sorted alphabetically. */\n"
                "function totalsByCustomer(array $rows): array\n"
                "{\n"
                "    $totals = [];\n"
                "    foreach ($rows as $row) {\n"
                "        $name = (string) $row['customer'];\n"
                "        $totals[$name] = ($totals[$name] ?? 0.0) + lineTotal($row);\n"
                "    }\n"
                "    ksort($totals);\n"
                "    foreach ($totals as $name => $value) {\n"
                "        $totals[$name] = round($value, 2);\n"
                "    }\n"
                "    return $totals;\n"
                "}\n",
                rows=rows_js)
            index = (
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "require __DIR__ . '/lib/helpers.php';\n\n"
                "/** Render the demo summary as plain text lines. */\n"
                "function renderSummary(array $rows): string\n"
                "{\n"
                "    $lines = [];\n"
                "    $lines[] = 'orders: ' . count($rows);\n"
                "    $lines[] = 'total: ' . number_format(orderTotal($rows), 2);\n"
                "    foreach (totalsByCustomer($rows) as $customer => $amount) {\n"
                "        $lines[] = $customer . ': ' . number_format($amount, 2);\n"
                "    }\n"
                "    return implode(PHP_EOL, $lines) . PHP_EOL;\n"
                "}\n\n"
                "echo renderSummary(sampleOrders());\n")
            api = ("sampleOrders() for the data, orderTotal($rows) for the grand "
                   "total, and totalsByCustomer($rows) for per-customer sums")
            readme_title = "Orders Summary"
            expected = ("The entry script prints the order count, the grand total "
                        "rounded to two decimals, and one alphabetical line per "
                        "customer with their summed spend.")
        elif proj == "contact_book":
            cities = ["Utrecht", "Antwerp", "Ghent", "Leuven"]
            contacts = []
            for _ in range(rng.randint(4, 5)):
                contacts.append({"name": rng.choice(["Ada L.", "Grace H.",
                                                     "Linus T.", "Marga K.",
                                                     "Alan T."]),
                                 "email": rng.choice(["ada@example.com",
                                                      "grace@corp.dev",
                                                      "linus@mail.net",
                                                      "marga@ops.io"]),
                                 "city": rng.choice(cities)})
            rows_js = ",\n            ".join(
                "['name' => '{n}', 'email' => '{e}', 'city' => '{c}']"
                .replace("{n}", c["name"]).replace("{e}", c["email"])
                .replace("{c}", c["city"]) for c in contacts)
            helpers = _fill(
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "/** In-memory contact rows for the demo entry point. */\n"
                "function sampleContacts(): array\n"
                "{\n"
                "    return [\n"
                "            {rows},\n"
                "    ];\n"
                "}\n\n"
                "/** Normalise one contact: trimmed name, lowercased email,\n"
                " * title-cased city. */\n"
                "function normalizeContact(array $contact): array\n"
                "{\n"
                "    return [\n"
                "        'name' => trim((string) $contact['name']),\n"
                "        'email' => strtolower(trim((string) $contact['email'])),\n"
                "        'city' => ucwords(strtolower(trim((string) $contact['city']))),\n"
                "    ];\n"
                "}\n\n"
                "/** Contacts per city, keys sorted alphabetically. */\n"
                "function countContactsByCity(array $contacts): array\n"
                "{\n"
                "    $counts = [];\n"
                "    foreach ($contacts as $contact) {\n"
                "        $city = $contact['city'];\n"
                "        $counts[$city] = ($counts[$city] ?? 0) + 1;\n"
                "    }\n"
                "    ksort($counts);\n"
                "    return $counts;\n"
                "}\n\n"
                "/** True when the email looks structurally valid. */\n"
                "function isValidEmailFormat(string $email): bool\n"
                "{\n"
                "    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;\n"
                "}\n",
                rows=rows_js)
            index = (
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "require __DIR__ . '/lib/helpers.php';\n\n"
                "/** Render the contact book report as plain text. */\n"
                "function renderReport(array $contacts): string\n"
                "{\n"
                "    $normalised = array_map('normalizeContact', $contacts);\n"
                "    $lines = ['contacts: ' . count($normalised)];\n"
                "    foreach (countContactsByCity($normalised) as $city => $count) {\n"
                "        $lines[] = $city . ': ' . $count;\n"
                "    }\n"
                "    $bad = array_filter($normalised,\n"
                "        static fn (array $c): bool => !isValidEmailFormat($c['email']));\n"
                "    $lines[] = 'invalid emails: ' . count($bad);\n"
                "    return implode(PHP_EOL, $lines) . PHP_EOL;\n"
                "}\n\n"
                "echo renderReport(sampleContacts());\n")
            api = ("sampleContacts() for the data, normalizeContact($c) to clean "
                   "one row, countContactsByCity($rows) for the city histogram, "
                   "and isValidEmailFormat($email) for the structural check")
            readme_title = "Contact Book"
            expected = ("The entry script prints the contact count, one "
                        "alphabetical line per city with its contact total, and "
                        "the number of contacts whose email fails the structural "
                        "check after normalisation.")
        else:  # quiz_scorer
            letters = ["a", "b", "c", "d"]
            total = rng.randint(4, 6)
            key = [rng.choice(letters) for _ in range(total)]
            answers = [rng.choice(letters + [None]) for _ in range(total)]
            if all(a == k for a, k in zip(answers, key)):
                answers[0] = "z"  # guarantee at least one miss
            key_js = ", ".join("'{}'".format(k) for k in key)
            ans_js = ", ".join("null" if a is None else "'{}'".format(a)
                               for a in answers)
            helpers = _fill(
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "/** Canonical answer key for the demo quiz. */\n"
                "function answerKey(): array\n"
                "{\n"
                "    return [{key}];\n"
                "}\n\n"
                "/** One learner's submitted answers; null means no answer. */\n"
                "function sampleAnswers(): array\n"
                "{\n"
                "    return [{answers}];\n"
                "}\n\n"
                "/** Number of positions where the submission matches the key. */\n"
                "function scoreQuiz(array $answers, array $key): int\n"
                "{\n"
                "    $score = 0;\n"
                "    foreach ($key as $index => $expected) {\n"
                "        if (isset($answers[$index]) && $answers[$index] === $expected) {\n"
                "            $score++;\n"
                "        }\n"
                "    }\n"
                "    return $score;\n"
                "}\n\n"
                "/** Map a percentage score onto the A-F letter ladder. */\n"
                "function letterGrade(int $score, int $total): string\n"
                "{\n"
                "    if ($total === 0) {\n"
                "        return 'F';\n"
                "    }\n"
                "    $pct = (int) round($score / $total * 100);\n"
                "    if ($pct >= 90) {\n"
                "        return 'A';\n"
                "    }\n"
                "    if ($pct >= 80) {\n"
                "        return 'B';\n"
                "    }\n"
                "    if ($pct >= 70) {\n"
                "        return 'C';\n"
                "    }\n"
                "    if ($pct >= 60) {\n"
                "        return 'D';\n"
                "    }\n"
                "    return 'F';\n"
                "}\n",
                key=key_js, answers=ans_js)
            index = (
                "<?php\n\n"
                "declare(strict_types=1);\n\n"
                "require __DIR__ . '/lib/helpers.php';\n\n"
                "/** Render the quiz result line for the demo submission. */\n"
                "function renderResult(array $answers, array $key): string\n"
                "{\n"
                "    $score = scoreQuiz($answers, $key);\n"
                "    $grade = letterGrade($score, count($key));\n"
                "    return 'score: ' . $score . '/' . count($key)\n"
                "         . ' grade: ' . $grade . PHP_EOL;\n"
                "}\n\n"
                "echo renderResult(sampleAnswers(), answerKey());\n")
            api = ("answerKey() and sampleAnswers() for the data, "
                   "scoreQuiz($answers, $key) for the raw score, and "
                   "letterGrade($score, $total) for the A-F mapping")
            readme_title = "Quiz Scorer"
            expected = ("The entry script prints the score out of the key length "
                        "and the letter grade computed from the percentage, with "
                        "null answers counted as misses.")
        readme = (
            "# {title} (PHP)\n\n"
            "Small multi-file PHP 8 project showing a clean split between a\n"
            "pure helper library and the entry script that renders output.\n\n"
            "## Layout\n\n"
            "- `index.php` - entry point; wires the sample data through the API\n"
            "- `lib/helpers.php` - pure functions, no side effects, no I/O\n"
            "- `README.md` - this document\n\n"
            "## Public API\n\n"
            "{api}.\n\n"
            "## Run\n\n"
            "`php index.php` from the project root prints the demo report.\n"
            "Every helper is deterministic, so repeated runs print identical\n"
            "output.\n").replace("{title}", readme_title).replace("{api}", api)
        files = [
            FileSpec("index.php", index),
            FileSpec("lib/helpers.php", helpers),
            FileSpec("README.md", readme),
        ]
        return dict(proj=proj, files=files, expected=expected)

    # --------------------------------------------------------------- generate
    def generate(self, rng: random.Random) -> Candidate:
        proj = rng.choice(self.PROJECTS)
        b = self._build(proj, rng)
        if proj == "orders_summary":
            task = ("Build the multi-file PHP 8 project 'orders-summary' as its "
                    "README describes: lib/helpers.php must define pure helpers "
                    "sampleOrders, lineTotal, orderTotal and totalsByCustomer "
                    "(quantity times amount per row, grand total rounded to two "
                    "decimals, per-customer sums with alphabetical keys), while "
                    "index.php requires the library and echoes the rendered "
                    "summary. Use declare(strict_types=1) in both files and no "
                    "output from the helpers themselves.")
        elif proj == "contact_book":
            task = ("Create the multi-file PHP 8 project 'contact-book': "
                    "lib/helpers.php exposes sampleContacts, normalizeContact, "
                    "countContactsByCity and isValidEmailFormat (trimmed names, "
                    "lowercased emails, title-cased cities, per-city counts with "
                    "ksort, filter_var validation), and index.php requires the "
                    "library and echoes the report. Helpers stay pure; only the "
                    "entry script produces output.")
        else:
            task = ("Implement the multi-file PHP 8 project 'quiz-scorer': "
                    "lib/helpers.php defines answerKey, sampleAnswers, scoreQuiz "
                    "and letterGrade (strict comparison per position, null "
                    "answers count as misses, percentage mapped onto the A-F "
                    "ladder with round), and index.php requires the library and "
                    "echoes the result line. Both PHP files must start with "
                    "declare(strict_types=1).")
        return Candidate(
            family=self.NAME, language="php", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=b["expected"],
            files=b["files"], entry="index.php",
            verify_method="static_check", is_project=True,
            notes={"project": proj,
                   "explain": _explain(
                       b["expected"],
                       "Pure helpers live in lib/helpers.php and are pulled in "
                       "by index.php with a __DIR__-anchored require; the entry "
                       "script is the only place that echoes.",
                       ["__DIR__-based require keeps the include path stable no "
                        "matter the working directory",
                        "helpers stay pure (no echo, no I/O), so they are "
                        "unit-testable in isolation",
                        "declare(strict_types=1) makes scalar casts explicit at "
                        "every boundary"],
                       "O(n) per aggregation pass over the sample rows",
                       "O(n) for the accumulated result arrays",
                       ["an empty data set still renders a well-formed report "
                        "with zero totals",
                        "keys are output in sorted order regardless of input "
                        "order"])},
            tags=["php", "project", proj], variant=proj,
            seed=rng.randrange(2 ** 31))


register(globals(), PhpPdoDefensiveFamily)
register(globals(), PhpArraysStringsFamily)
register(globals(), PhpProjectFamily)
