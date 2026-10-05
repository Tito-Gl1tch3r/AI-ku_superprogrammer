"""Dataset-1 write families for PowerShell.

pwsh is NOT installed in this environment, so every candidate is verified
with verify_method="static_check" (structural validation only: balanced
braces/parens/brackets and forbidden-pattern gates). Code is authored as
conservative, canonical PowerShell 5.1+ that would run unchanged in a real
shell: param() blocks with validated parameters, approved verbs, object
pipelines, ConvertTo-Json/ConvertFrom-Json round-trips, and never
Invoke-Expression or dynamic invocation of any kind. The learning value for
the understand-dataset is carried by the precise notes["explain"] ground
truth each family authors.
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


class PsFileAdminFamily(Family):
    """File-administration scripts: Get-ChildItem pipelines with
    Where-Object / Sort-Object / Select-Object and inventory reports,
    driven by validated param() blocks."""

    NAME = "ps_file_admin"
    LANGUAGE = "powershell"
    DOMAIN = "automation"
    DIFFICULTIES = ("beginner", "intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "testing", "debugging")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("size_report", "stale_files", "duplicate_names"))
        if kind == "size_report":
            return self._size_report(rng)
        if kind == "stale_files":
            return self._stale_files(rng)
        return self._duplicate_names(rng)

    def _size_report(self, rng: random.Random) -> Candidate:
        filt = rng.choice(("*.log", "*.txt", "*.json", "*.csv"))
        top = rng.randint(5, 20)
        code = "\n".join([
            "param(",
            "    [Parameter(Mandatory = $true)]",
            "    [ValidateScript({ Test-Path $_ -PathType Container })]",
            "    [string]$Path,",
            "",
            "    [ValidateSet('*.log', '*.txt', '*.json', '*.csv')]",
            f"    [string]$Filter = '{filt}',",
            "",
            "    [ValidateRange(1, 100)]",
            f"    [int]$Top = {top}",
            ")",
            "",
            "$largest = Get-ChildItem -Path $Path -Filter $Filter -File |",
            "    Where-Object { $_.Length -gt 0 } |",
            "    Sort-Object -Property Length -Descending |",
            "    Select-Object -First $Top",
            "",
            "$report = foreach ($file in $largest) {",
            "    [PSCustomObject]@{",
            "        Name = $file.Name",
            "        Kilobytes = [math]::Round($file.Length / 1KB, 1)",
            "        Modified = $file.LastWriteTime.ToString('yyyy-MM-dd')",
            "    }",
            "}",
            "",
            "$report | Format-Table -AutoSize",
            "Write-Output \"Listed $($report.Count) of the largest files in $Path\"",
        ])
        task = (
            "Write a PowerShell administration script with a validated param() block "
            "(-Path container, -Filter from an approved set, -Top in 1..100) that emits "
            "a largest-files inventory for extension '" + filt + "': pipeline "
            "Get-ChildItem through Where-Object, Sort-Object by descending size and "
            "Select-Object -First " + str(top) + ", project each hit into a PSCustomObject with "
            "Name, Kilobytes (one decimal) and Modified date, and finish with a "
            "Format-Table report plus a count summary line. No dynamic invocation."
        )
        expected = (
            "Running with a container path prints a sized table of up to " + str(top) +
            " non-empty '" + filt + "' files (name, KB with one decimal, yyyy-MM-dd "
            "modified) and a 'Listed N of the largest files' summary."
        )
        explain = _explain(
            purpose=("Produce a largest-files inventory report whose rows are clean "
                     "PSCustomObjects, exercising the Where/Sort/Select pipeline core of "
                     "PowerShell object flow."),
            approach=("A validated param() block feeds Get-ChildItem -File; the pipeline "
                      "filters empty files, sorts by Length descending, takes the top N, "
                      "and a foreach projection builds the report objects."),
            key_points=[
                "ValidateScript keeps bad -Path values out before any pipeline runs",
                "Where-Object { $_.Length -gt 0 } drops empty files so Kilobytes is never 0 by accident",
                "Sort-Object -Descending on Length plus Select-Object -First is the top-K idiom",
                "PSCustomObject keeps column order stable for Format-Table output",
            ],
            big_o_time="O(n log n) over n directory entries due to sorting",
            big_o_space="O(k) for the k reported rows",
            edge_cases=[
                "fewer matching files than $Top simply yields a shorter report; the count line stays truthful",
                "a scalar result still answers .Count thanks to PowerShell's intrinsic Count property",
                "subdirectories are excluded by -File, so only leaf files are measured",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "size_report", "explain": explain},
            tags=["powershell", "files", "report"], variant="size_report",
            seed=rng.randrange(2 ** 31),
        )

    def _stale_files(self, rng: random.Random) -> Candidate:
        age = rng.randint(7, 90)
        code = "\n".join([
            "param(",
            "    [Parameter(Mandatory = $true)]",
            "    [string]$Path,",
            "",
            "    [ValidateRange(1, 365)]",
            f"    [int]$AgeDays = {age}",
            ")",
            "",
            "$cutoff = (Get-Date).AddDays(-$AgeDays)",
            "$stale = Get-ChildItem -Path $Path -File -Recurse |",
            "    Where-Object { $_.LastWriteTime -lt $cutoff } |",
            "    Sort-Object -Property LastWriteTime |",
            "    Select-Object -First 25",
            "",
            "foreach ($item in $stale) {",
            "    Write-Output (\"{0}  {1}\" -f $item.LastWriteTime.ToString('yyyy-MM-dd'), $item.Name)",
            "}",
            "Write-Output \"Found $($stale.Count) files older than $AgeDays days under $Path\"",
        ])
        task = (
            "Write a PowerShell cleanup-report script with a validated param() block "
            "(-Path mandatory, -AgeDays default " + str(age) + " in 1..365) that lists stale files: "
            "compute a cutoff from Get-Date, recurse with Get-ChildItem -File, keep files "
            "whose LastWriteTime predates the cutoff via Where-Object, sort them oldest "
            "first, cap the listing at 25 rows with Select-Object, print one 'date  name' "
            "line per file, and end with a found-count summary. No dynamic invocation."
        )
        expected = (
            "Running against a tree prints at most 25 'yyyy-MM-dd  name' lines for files "
            "untouched in the last " + str(age) + " days, oldest first, then a 'Found N files "
            "older than " + str(age) + " days' summary."
        )
        explain = _explain(
            purpose=("Identify stale files for cleanup review by comparing LastWriteTime "
                     "against a computed cutoff, with an ordered, capped, human-readable "
                     "report."),
            approach=("One cutoff DateTime, one recursive Get-ChildItem -File pipeline "
                      "guarded by Where-Object, oldest-first Sort-Object, a Select-Object "
                      "cap, and a format-operator emission loop."),
            key_points=[
                "(Get-Date).AddDays(-$AgeDays) derives the cutoff instead of hard-coding a date",
                "the -lt comparison on DateTime values is culture-safe inside Where-Object",
                "Sort-Object ascending puts the oldest candidates first for cleanup triage",
                "the -f format operator renders the two-column lines without string concatenation noise",
            ],
            big_o_time="O(n log n) over n files (recursion plus sort)",
            big_o_space="O(m) for the m <= 25 stale rows",
            edge_cases=[
                "no stale files prints only the zero-count summary line",
                "exactly-at-cutoff files are kept out because the comparison is strictly older-than",
                "deeper trees cost more traversal; -Recurse is intentional and documented by the summary",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "stale_files", "explain": explain},
            tags=["powershell", "files", "maintenance"], variant="stale_files",
            seed=rng.randrange(2 ** 31),
        )

    def _duplicate_names(self, rng: random.Random) -> Candidate:
        ext = rng.choice(("log", "txt", "json", "csv"))
        code = "\n".join([
            "param(",
            "    [Parameter(Mandatory = $true)]",
            "    [string]$Path,",
            "",
            "    [ValidateSet('log', 'txt', 'json', 'csv')]",
            f"    [string]$Extension = '{ext}'",
            ")",
            "",
            "$pattern = '*.' + $Extension",
            "$duplicates = Get-ChildItem -Path $Path -Filter $pattern -File |",
            "    Group-Object -Property Name |",
            "    Where-Object { $_.Count -gt 1 } |",
            "    Sort-Object -Property Count -Descending |",
            "    Select-Object -First 10",
            "",
            "$report = foreach ($group in $duplicates) {",
            "    [PSCustomObject]@{",
            "        FileName = $group.Name",
            "        Copies = $group.Count",
            "        TotalBytes = ($group.Group | Measure-Object -Property Length -Sum).Sum",
            "    }",
            "}",
            "",
            "$report | Format-Table -AutoSize",
            "Write-Output \"Detected $($report.Count) duplicated names for extension $Extension\"",
        ])
        task = (
            "Write a PowerShell duplicate-detection script with a validated param() block "
            "(-Path mandatory, -Extension from an approved set defaulting to '" + ext +
            "'): build a wildcard pattern, pipe Get-ChildItem -File through Group-Object "
            "on file name, keep only groups with more than one copy via Where-Object, "
            "order by copy count descending, cap at 10 with Select-Object, and project "
            "each surviving group into a PSCustomObject with FileName, Copies and a "
            "Measure-Object byte total, ending in a table plus summary. No dynamic "
            "invocation."
        )
        expected = (
            "Running against a directory prints a table of at most 10 duplicated '" + ext +
            "' names with copy counts and summed bytes, then a 'Detected N duplicated "
            "names' summary."
        )
        explain = _explain(
            purpose=("Surface duplicated file names inside one extension class, ranking "
                     "them by copy count and totalling their bytes for cleanup priority."),
            approach=("Group-Object aggregates directory entries by Name; Where-Object "
                      "keeps multi-member groups; a foreach projection folds each group's "
                      "Group collection through Measure-Object -Sum."),
            key_points=[
                "Group-Object turns a flat listing into countable groups without manual dictionaries",
                "$_.Count -gt 1 is the duplicate predicate; group membership lives in $_.Group",
                "Measure-Object -Property Length -Sum aggregates file sizes per group",
                "Sort-Object on Count -Descending ranks the noisiest duplicates first",
            ],
            big_o_time="O(n) grouping plus O(g log g) over g surviving groups",
            big_o_space="O(d) for the d duplicated-name rows",
            edge_cases=[
                "a directory with no duplicates prints an empty table and a zero count",
                "same name in different subdirectories still groups together because grouping is on Name only",
                "the 10-row Select-Object cap means the summary can exceed the table length",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "duplicate_names", "explain": explain},
            tags=["powershell", "files", "duplicates"], variant="duplicate_names",
            seed=rng.randrange(2 ** 31),
        )


class PsJsonReportingFamily(Family):
    """ConvertTo-Json / ConvertFrom-Json round-trips, PSCustomObject
    construction, and computed report objects."""

    NAME = "ps_json_reporting"
    LANGUAGE = "powershell"
    DOMAIN = "automation"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "code_review", "testing", "failure_prediction")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(("round_trip", "role_aggregate", "config_audit"))
        if kind == "round_trip":
            return self._round_trip(rng)
        if kind == "role_aggregate":
            return self._role_aggregate(rng)
        return self._config_audit(rng)

    def _round_trip(self, rng: random.Random) -> Candidate:
        name1 = rng.choice(("web-01", "web-02", "edge-01"))
        name2 = rng.choice(("db-01", "db-02", "warehouse-01"))
        name3 = rng.choice(("cache-01", "queue-01", "bus-01"))
        cores = [rng.choice((2, 4, 8, 16)) for _ in range(3)]
        code = "\n".join([
            "$servers = @(",
            "    [PSCustomObject]@{ Host = '" + name1 + "'; Role = 'web'; Cores = " + str(cores[0]) + " },",
            "    [PSCustomObject]@{ Host = '" + name2 + "'; Role = 'database'; Cores = " + str(cores[1]) + " },",
            "    [PSCustomObject]@{ Host = '" + name3 + "'; Role = 'cache'; Cores = " + str(cores[2]) + " }",
            ")",
            "",
            "$json = $servers | ConvertTo-Json -Depth 4",
            "$parsed = $json | ConvertFrom-Json",
            "",
            "if (@($parsed).Count -ne $servers.Count) {",
            "    throw 'JSON round-trip lost records'",
            "}",
            "",
            "$totalCores = ($parsed | Measure-Object -Property Cores -Sum).Sum",
            "$summary = [PSCustomObject]@{",
            "    RecordCount = @($parsed).Count",
            "    TotalCores = $totalCores",
            "    AverageCores = [math]::Round($totalCores / @($parsed).Count, 2)",
            "}",
            "",
            "$summary | ConvertTo-Json -Depth 2 | Write-Output",
        ])
        task = (
            "Write a PowerShell script that proves a JSON round-trip: build an array of "
            "three PSCustomObject server rows (" + name1 + "/" + name2 + "/" + name3 + " with web, "
            "database and cache roles), serialize with ConvertTo-Json, deserialize with "
            "ConvertFrom-Json, and guard the record count with a throw. Then compute a "
            "summary PSCustomObject (RecordCount via @() wrapping, TotalCores via "
            "Measure-Object -Sum, AverageCores via [math]::Round) and emit it as JSON. "
            "No dynamic invocation."
        )
        expected = (
            "Prints a JSON summary object with RecordCount 3, TotalCores " +
            str(sum(cores)) + " and AverageCores " + str(round(sum(cores) / 3, 2)) +
            "; the throw fires if the round-trip ever loses a record."
        )
        explain = _explain(
            purpose=("Demonstrate loss-free ConvertTo-Json / ConvertFrom-Json round-trips "
                     "over PSCustomObject arrays plus computed aggregate reporting."),
            approach=("Build typed rows in memory, serialize and deserialize, verify the "
                      "record count, then fold the parsed objects through Measure-Object "
                      "into a summary object emitted as JSON again."),
            key_points=[
                "ConvertFrom-Json returns objects whose properties are directly pipeline-able",
                "@($parsed).Count normalizes single-object results so counting never breaks",
                "Measure-Object -Property Cores -Sum is the aggregate engine; .Sum reads the result",
                "a depth of 4 covers nested property graphs without silent truncation",
            ],
            big_o_time="O(n) serialization and aggregation over n rows",
            big_o_space="O(n) for the JSON text and parsed objects",
            edge_cases=[
                "a single-row array would deserialize to a scalar; @() wrapping keeps the count logic intact",
                "the throw guard converts a silent data-loss bug into a loud failure",
                "rounding AverageCores to 2 decimals keeps the JSON stable across PowerShell versions",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "round_trip", "explain": explain},
            tags=["powershell", "json", "round-trip"], variant="round_trip",
            seed=rng.randrange(2 ** 31),
        )

    def _role_aggregate(self, rng: random.Random) -> Candidate:
        web_mem = rng.choice((8, 16))
        db_mem = rng.choice((32, 64))
        code = "\n".join([
            "$servers = @(",
            "    [PSCustomObject]@{ Name = 'web-01'; Role = 'web'; MemoryGb = " + str(web_mem) + " },",
            "    [PSCustomObject]@{ Name = 'web-02'; Role = 'web'; MemoryGb = " + str(web_mem) + " },",
            "    [PSCustomObject]@{ Name = 'db-01'; Role = 'database'; MemoryGb = " + str(db_mem) + " },",
            "    [PSCustomObject]@{ Name = 'db-02'; Role = 'database'; MemoryGb = " + str(db_mem) + " }",
            ")",
            "",
            "$report = foreach ($group in ($servers | Group-Object -Property Role)) {",
            "    $members = @($group.Group)",
            "    [PSCustomObject]@{",
            "        Role = $group.Name",
            "        ServerCount = $members.Count",
            "        TotalMemoryGb = ($members | Measure-Object -Property MemoryGb -Sum).Sum",
            "    }",
            "}",
            "",
            "$sorted = $report | Sort-Object -Property Role",
            "$json = $sorted | ConvertTo-Json -Depth 3",
            "$roundTrip = $json | ConvertFrom-Json",
            "",
            "foreach ($row in $roundTrip) {",
            "    Write-Output (\"{0}: {1} servers, {2} GB\" -f $row.Role, $row.ServerCount, $row.TotalMemoryGb)",
            "}",
        ])
        task = (
            "Write a PowerShell fleet-capacity reporter: from a four-server PSCustomObject "
            "array (two web hosts with " + str(web_mem) + " GB, two database hosts with " + str(db_mem) +
            " GB), group by Role, project each group into a report row with Role, "
            "ServerCount and TotalMemoryGb (via Measure-Object -Sum), sort the rows by "
            "role name, round-trip the report through ConvertTo-Json / ConvertFrom-Json, "
            "and print one 'role: N servers, M GB' line per row using the -f operator. "
            "No dynamic invocation."
        )
        expected = (
            "Prints 'database: 2 servers, " + str(2 * db_mem) + " GB' then 'web: 2 servers, " +
            str(2 * web_mem) + " GB' in role order, computed from the JSON round-trip of "
            "the grouped report."
        )
        explain = _explain(
            purpose=("Compute per-role capacity aggregates and prove they survive a JSON "
                     "round-trip, combining Group-Object, Measure-Object and the JSON "
                     "cmdlets in one report flow."),
            approach=("Group the fleet by Role, fold each group into a PSCustomObject row, "
                      "sort rows, serialize/deserialize, and emit formatted lines from the "
                      "deserialized data."),
            key_points=[
                "$group.Group exposes member objects; @() wrapping makes .Count reliable",
                "Measure-Object -Property MemoryGb -Sum computes the per-role memory total",
                "Sort-Object on Role gives stable, comparable output across runs",
                "printing from the deserialized rows demonstrates the round-trip preserved properties",
            ],
            big_o_time="O(n) grouping and aggregation over n servers",
            big_o_space="O(r) for r report rows plus the JSON text",
            edge_cases=[
                "a role with one member still aggregates correctly thanks to @() normalization",
                "roles sort alphabetically, so 'database' precedes 'web' regardless of input order",
                "the -f operator renders Int64 sums without manual ToString calls",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "role_aggregate", "explain": explain},
            tags=["powershell", "json", "aggregation"], variant="role_aggregate",
            seed=rng.randrange(2 ** 31),
        )

    def _config_audit(self, rng: random.Random) -> Candidate:
        env = rng.choice(("staging", "production"))
        replicas = rng.choice((3, 5, 9))
        features = rng.sample(("metrics", "tracing", "alerts", "exports"), rng.randint(2, 3))
        feat_lit = ", ".join("'" + f + "'" for f in features)
        code = "\n".join([
            "$config = [PSCustomObject]@{",
            "    Environment = '" + env + "'",
            "    Replicas = " + str(replicas),
            "    Features = @(" + feat_lit + ")",
            "}",
            "",
            "$configJson = $config | ConvertTo-Json -Depth 3",
            "$parsed = $configJson | ConvertFrom-Json",
            "",
            "$required = @('Environment', 'Replicas', 'Features')",
            "$missing = @()",
            "foreach ($field in $required) {",
            "    if (-not $parsed.PSObject.Properties[$field]) {",
            "        $missing += $field",
            "    }",
            "}",
            "",
            "if ($missing.Count -gt 0) {",
            "    throw (\"missing config fields: \" + ($missing -join ', '))",
            "}",
            "",
            "$validReplicas = $parsed.Replicas -ge 1 -and $parsed.Replicas -le 50",
            "$audit = [PSCustomObject]@{",
            "    Environment = $parsed.Environment",
            "    Replicas = $parsed.Replicas",
            "    FeatureCount = @($parsed.Features).Count",
            "    SchemaValid = ($missing.Count -eq 0 -and $validReplicas)",
            "}",
            "",
            "$audit | ConvertTo-Json -Depth 2 | Write-Output",
        ])
        task = (
            "Write a PowerShell config auditor: construct a PSCustomObject with "
            "Environment '" + env + "', Replicas " + str(replicas) + " and a Features array (" +
            ", ".join(features) + "), serialize it with ConvertTo-Json and parse it back, "
            "validate the schema by checking each required field through "
            "$parsed.PSObject.Properties (collecting missing names and throwing with a "
            "joined message if any), bound-check Replicas into 1..50, and emit a final "
            "audit PSCustomObject (Environment, Replicas, FeatureCount, SchemaValid) as "
            "JSON. No dynamic invocation."
        )
        expected = (
            "Prints JSON with Environment '" + env + "', Replicas " + str(replicas) +
            ", FeatureCount " + str(len(features)) + " and SchemaValid True; any missing "
            "field throws 'missing config fields: ...' instead."
        )
        explain = _explain(
            purpose=("Validate a JSON config round-trip against a small schema: required "
                     "fields, a range check, and a computed audit object with a boolean "
                     "verdict."),
            approach=("Serialize a PSCustomObject, parse it back, probe properties via "
                      "PSObject.Properties for missing keys, accumulate failures, then "
                      "derive the audit fields and re-serialize."),
            key_points=[
                "PSObject.Properties[$field] is the reflection-safe membership probe for deserialized objects",
                "the $missing accumulator plus -join renders one precise throw message",
                "-ge/-le chain with -and expresses the replica range as a single boolean",
                "@($parsed.Features).Count tolerates a one-element array deserialized as a scalar",
            ],
            big_o_time="O(f) over f required fields; O(1) validation otherwise",
            big_o_space="O(f + a) for the missing list and audit object",
            edge_cases=[
                "Replicas 0 or 51 would fail the range check and flip SchemaValid to False",
                "a missing Features key increments $missing and prevents the audit from claiming validity",
                "an empty Features array still validates but reports FeatureCount 0",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, code=code,
            verify_method="static_check",
            notes={"kind": "config_audit", "explain": explain},
            tags=["powershell", "json", "validation"], variant="config_audit",
            seed=rng.randrange(2 ** 31),
        )


class PsModuleProjectFamily(Family):
    """Multi-file PowerShell module project: MyModule.psm1 + MyModule.psd1
    manifest + README, exporting approved-verb functions only."""

    NAME = "ps_module_project"
    LANGUAGE = "powershell"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    EXTRA_FUNCTIONS = ("Test-DiskSpace", "Write-DeployLog", "Test-PortOpen", "Set-MaintenanceFlag")

    def generate(self, rng: random.Random) -> Candidate:
        chosen = ["Get-ServerInventory"] + rng.sample(self.EXTRA_FUNCTIONS, 2)
        rng.shuffle(chosen)
        version = rng.choice(("1.0.0", "1.2.0", "2.0.1", "0.9.4"))
        guid = "-".join((
            "".join(rng.choice("0123456789abcdef") for _ in range(8)),
            "".join(rng.choice("0123456789abcdef") for _ in range(4)),
            "".join(rng.choice("0123456789abcdef") for _ in range(4)),
            "".join(rng.choice("0123456789abcdef") for _ in range(4)),
            "".join(rng.choice("0123456789abcdef") for _ in range(12)),
        ))
        bodies = {fn: self._function_body(fn) for fn in chosen}
        fn_list = ", ".join(chosen)

        psm1 = "\n".join([
            "# OpsInventory module: server inventory and health helpers.",
            "# All functions use approved verbs, validated parameters and no",
            "# dynamic invocation, so the module is safe to audit line by line.",
            ""] +
            [bodies[fn] for fn in chosen] + [
            "",
            "Export-ModuleMember -Function " + ", ".join("'" + fn + "'" for fn in chosen),
        ])
        psd1 = "\n".join([
            "@{",
            "    RootModule = 'MyModule.psm1'",
            f"    ModuleVersion = '{version}'",
            f"    GUID = '{guid}'",
            "    Author = 'Ops Engineering'",
            "    CompanyName = 'Internal Tools'",
            "    Description = 'Server inventory and health helpers for ops automation.'",
            "    PowerShellVersion = '5.1'",
            "    FunctionsToExport = @(" + ", ".join("'" + fn + "'" for fn in chosen) + ")",
            "    CmdletsToExport = @()",
            "    VariablesToExport = @()",
            "    AliasesToExport = @()",
            "    Tags = @('inventory', 'ops', 'health')",
            "    ProjectUri = 'https://git.internal/ops/OpsInventory'",
            "}",
        ])
        readme = "\n".join([
            "# OpsInventory PowerShell module",
            "",
            "Multi-file PowerShell module project.",
            "",
            "## Files",
            "",
            "- MyModule.psm1: module body with the exported functions " + fn_list,
            "- MyModule.psd1: module manifest with version, GUID and export lists",
            "- README.md: this overview",
            "",
            "## Usage",
            "",
            "- Import-Module ./MyModule.psd1 loads the manifest and its implementation",
            "- Get-Command -Module OpsInventory lists the exported functions",
            "- Get-ServerInventory -ComputerName web-01, web-02 returns one row per host",
            "",
            "## Notes",
            "",
            "Every function sticks to approved PowerShell verbs, validates its",
            "parameters, and avoids dynamic code execution, so the whole module can",
            "be reviewed with static reading alone.",
        ])
        files = [
            FileSpec("MyModule.psm1", psm1),
            FileSpec("MyModule.psd1", psd1),
            FileSpec("README.md", readme),
        ]
        task = (
            "Create the multi-file PowerShell module project 'OpsInventory' as the README "
            "describes: MyModule.psm1 implements and exports " + fn_list + " with approved "
            "verbs and validated param blocks, MyModule.psd1 is a full manifest (version " +
            version + ", RootModule, FunctionsToExport, Tags) whose export list matches the "
            "psm1, and README.md documents Import-Module usage. Every function must be "
            "deterministic, side-effect-light and free of dynamic code execution."
        )
        expected = (
            "Import-Module ./MyModule.psd1 succeeds and exposes exactly " + fn_list +
            "; Get-ServerInventory returns one PSCustomObject per -ComputerName entry and "
            "the other functions return typed status objects."
        )
        explain = _explain(
            purpose=("Author a complete PowerShell module project: implementation (.psm1) "
                     "plus manifest (.psd1) whose export lists agree, using approved verbs "
                     "and validated parameters throughout."),
            approach=("Function bodies with [CmdletBinding()] and param() validation, an "
                      "explicit Export-ModuleMember allow-list, and a manifest that "
                      "declares the identical FunctionsToExport list."),
            key_points=[
                "approved verbs (Get-, Test-, Write-, Set-) keep the module consistent with Get-Command conventions",
                "Export-ModuleMember is an allow-list: anything not listed stays private to the module",
                "the manifest FunctionsToExport must mirror the psm1 export list or Import-Module shows drift",
                "[CmdletBinding()] plus ValidateSet/ValidateRange turns bad input into clean parameter errors",
            ],
            big_o_time="O(n) over n hosts or drives per invoked function",
            big_o_space="O(n) result rows per invocation",
            edge_cases=[
                "Get-ServerInventory with an unreachable host still returns a row, with PingOk False",
                "Test-DiskSpace drives with zero used space avoid division by zero only because Used+Free stays positive",
                "an empty -ComputerName array yields an empty inventory rather than an error",
            ],
        )
        return Candidate(
            family=self.NAME, language=self.LANGUAGE, domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=task, expected_behavior=expected, files=files,
            entry="MyModule.psm1", verify_method="static_check", is_project=True,
            notes={"project": "OpsInventory", "functions": chosen,
                   "module_version": version, "explain": self._explain_for(chosen)},
            tags=["powershell", "project", "module"], variant="OpsInventory",
            seed=rng.randrange(2 ** 31),
        )

    def _explain_for(self, chosen):
        detail = {
            "Get-ServerInventory": "Test-Connection -Quiet turns reachability into a boolean column",
            "Test-DiskSpace": "free-percent math uses Used + Free as the denominator so near-empty drives stay finite",
            "Write-DeployLog": "Add-Content appends timestamped lines and returns the same entry for testability",
            "Test-PortOpen": "Test-NetConnection -Port yields TcpTestSucceeded as the open/closed verdict",
            "Set-MaintenanceFlag": "the flag writer formats one status line per call so intent is auditable",
        }
        return _explain(
            purpose=("Build a shippable PowerShell module: implementation file, manifest, "
                     "and usage README whose exported surface is exactly " + ", ".join(chosen) + "."),
            approach=("Approved-verb functions with validated param blocks, an "
                      "Export-ModuleMember allow-list mirrored by the manifest, and a "
                      "README documenting the import workflow."),
            key_points=[detail[fn] for fn in chosen] + [
                "the manifest is the contract: RootModule, ModuleVersion and FunctionsToExport must agree with the psm1",
            ],
            big_o_time="O(n) per function over its host/drive list",
            big_o_space="O(n) emitted rows per invocation",
            edge_cases=[
                "unreachable hosts degrade to False flags instead of terminating errors",
                "export lists that drift between psm1 and psd1 surface immediately on Import-Module inspection",
            ],
        )

    def _function_body(self, fn: str) -> str:
        if fn == "Get-ServerInventory":
            return "\n".join([
                "function Get-ServerInventory {",
                "    [CmdletBinding()]",
                "    param(",
                "        [Parameter(Mandatory = $true)]",
                "        [string[]]$ComputerName",
                "    )",
                "",
                "    $rows = foreach ($name in $ComputerName) {",
                "        [PSCustomObject]@{",
                "            Server = $name",
                "            PingOk = (Test-Connection -ComputerName $name -Count 1 -Quiet)",
                "            CheckedAt = (Get-Date -Format 'yyyy-MM-dd')",
                "        }",
                "    }",
                "    return $rows",
                "}",
                "",
            ])
        if fn == "Test-DiskSpace":
            return "\n".join([
                "function Test-DiskSpace {",
                "    [CmdletBinding()]",
                "    param(",
                "        [Parameter(Mandatory = $true)]",
                "        [string]$DriveLetter,",
                "",
                "        [ValidateRange(1, 99)]",
                "        [int]$MinFreePercent = 20",
                "    )",
                "",
                "    $volume = Get-PSDrive -Name $DriveLetter -ErrorAction Stop",
                "    $freePercent = [math]::Round(($volume.Free / ($volume.Used + $volume.Free)) * 100, 1)",
                "    $healthy = $freePercent -ge $MinFreePercent",
                "    return [PSCustomObject]@{",
                "        Drive = $DriveLetter",
                "        FreePercent = $freePercent",
                "        Healthy = $healthy",
                "    }",
                "}",
                "",
            ])
        if fn == "Write-DeployLog":
            return "\n".join([
                "function Write-DeployLog {",
                "    [CmdletBinding()]",
                "    param(",
                "        [Parameter(Mandatory = $true)]",
                "        [ValidateSet('start', 'success', 'failure')]",
                "        [string]$Status,",
                "",
                "        [Parameter(Mandatory = $true)]",
                "        [string]$Message,",
                "",
                "        [string]$LogPath = 'deploy.log'",
                "    )",
                "",
                "    $entry = '[{0}] {1}: {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Status.ToUpperInvariant(), $Message",
                "    Add-Content -Path $LogPath -Value $entry",
                "    return $entry",
                "}",
                "",
            ])
        if fn == "Test-PortOpen":
            return "\n".join([
                "function Test-PortOpen {",
                "    [CmdletBinding()]",
                "    param(",
                "        [Parameter(Mandatory = $true)]",
                "        [string]$ComputerName,",
                "",
                "        [ValidateRange(1, 65535)]",
                "        [int]$Port = 443",
                "    )",
                "",
                "    $result = Test-NetConnection -ComputerName $ComputerName -Port $Port -WarningAction SilentlyContinue",
                "    return [PSCustomObject]@{",
                "        Target = $ComputerName",
                "        Port = $Port",
                "        Open = $result.TcpTestSucceeded",
                "    }",
                "}",
                "",
            ])
        # Set-MaintenanceFlag
        return "\n".join([
            "function Set-MaintenanceFlag {",
            "    [CmdletBinding()]",
            "    param(",
            "        [Parameter(Mandatory = $true)]",
            "        [string]$ComputerName,",
            "",
            "        [bool]$Enabled = $true",
            "    )",
            "",
            "    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'",
            "    $entry = '{0} maintenance={1} on {2}' -f $stamp, $Enabled, $ComputerName",
            "    Write-Output $entry",
            "}",
            "",
        ])


register(globals(), PsFileAdminFamily)
register(globals(), PsJsonReportingFamily)
register(globals(), PsModuleProjectFamily)
