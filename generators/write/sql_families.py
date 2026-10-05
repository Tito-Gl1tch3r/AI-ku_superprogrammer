"""Dataset-1 write families for SQL (SQLite dialect, independently verified).

Every scenario builds its data model in Python first; expected rows are
computed from that model in Python (never by running the answer query).
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, register


def _names(rng, n):
    pool = ["ada", "linus", "grace", "alan", "edger", "barbara", "ken", "dennis",
            "radia", "james", "margaret", "vint"]
    if n <= len(pool):
        return rng.sample(pool, n)
    return [pool[i % len(pool)] + str(i) for i in range(n)]


def _mk_table(table, cols, rows):
    types = {"i": "INTEGER", "t": "TEXT", "r": "REAL"}
    lines = [f"CREATE TABLE {table} (" +
             ", ".join(f"{c} {types[t]}" for c, t in cols) + ");"]
    for row in rows:
        vals = []
        for (c, t), v in zip(cols, row):
            if v is None:
                vals.append("NULL")
            elif t == "t":
                vals.append("'" + str(v).replace("'", "''") + "'")
            else:
                vals.append(str(v))
        lines.append(f"INSERT INTO {table} VALUES ({', '.join(vals)});")
    return "\n".join(lines)


class SQLQueryFamily(Family):
    NAME = "sql_query_scenarios"
    LANGUAGE = "sql"
    DOMAIN = "databases"
    DIFFICULTIES = ("beginner", "intermediate", "advanced", "expert")
    SUPPORTS = ("explanation", "debugging", "code_review", "optimization",
                "testing", "complexity")

    SCENARIOS = ("orders_revenue", "dept_avg_salary", "library_top", "low_stock",
                 "student_averages", "monthly_totals", "last_login", "cheapest_route",
                 "upsert_catalog", "index_speedup")

    def generate(self, rng: random.Random) -> Candidate | None:
        kind = rng.choice(self.SCENARIOS)
        builder = getattr(self, "_sc_" + kind)
        sc = builder(rng)
        setup = sc["setup"]
        answer = sc["answer"]
        expected = sc["expected"]
        cases = []
        if not sc.get("no_answer_case"):
            cases.append({"name": "answer", "use_answer": True, "expected": expected})
        for extra in sc.get("extras", []):
            cases.append(extra)
        notes = {"setup": setup, "cases": cases, "scenario": kind,
                 "explain": sc["explain"], "tables": sc.get("tables", {})}
        return Candidate(
            family=self.NAME, language="sql", domain=self.DOMAIN,
            difficulty=sc.get("difficulty", rng.choice(self.DIFFICULTIES)),
            task=sc["task"], expected_behavior=sc["explain"]["purpose"],
            code=answer, tests=None, verify_method="executed",
            notes=notes, tags=["sql", kind], variant=kind,
            seed=rng.randrange(2**31))

    # ------------------------------------------------------------ scenarios
    def _sc_orders_revenue(self, rng):
        names = _names(rng, rng.randint(3, 6))
        countries = ["ES", "DE", "FR", "US", "MX"]
        cust_rows = [(i, names[i], rng.choice(countries)) for i in range(len(names))]
        n_ord = rng.randint(8, 24)
        ord_rows = [(i, rng.randrange(len(names)), rng.randint(10, 900),
                     f"2026-0{rng.randint(1, 9)}-{rng.randint(10, 28):02d}")
                    for i in range(n_ord)]
        top = rng.choice(["all"]) if rng.random() < 0.5 else str(rng.randint(2, 3))
        answer = ("SELECT c.name, SUM(o.amount) AS total\n"
                  "FROM orders o JOIN customers c ON c.id = o.customer_id\n"
                  "GROUP BY c.name\n"
                  "ORDER BY total DESC, c.name ASC"
                  + (f"\nLIMIT {top};" if top != "all" else ";"))
        totals = {}
        for _, cid, amt, _d in ord_rows:
            totals[cid] = totals.get(cid, 0) + amt
        expected = [[names[cid], tot] for cid, tot in totals.items()]
        expected.sort(key=lambda r: (-r[1], r[0]))
        if top != "all":
            expected = expected[:int(top)]
        setup = (_mk_table("customers", [("id", "i"), ("name", "t"), ("country", "t")], cust_rows)
                 + "\n" + _mk_table("orders", [("id", "i"), ("customer_id", "i"),
                                               ("amount", "i"), ("placed_at", "t")], ord_rows))
        return {"setup": setup, "answer": answer.rstrip(";"),
                "expected": expected,
                "task": (f"Write ONE SQLite query over the customers/orders schema that returns each "
                         f"customer's name and the summed `amount` of their orders, sorted by total "
                         f"descending with ties broken by name ascending"
                         + (f", limited to the top {top}" if top != "all" else "")
                         + ". Column aliases: name, total."),
                "explain": {"purpose": "Revenue per customer via JOIN + GROUP BY + ordered sort.",
                            "approach": "Inner join on customer_id, aggregate with SUM, order by the aggregate alias.",
                            "key_points": ["aliases can be referenced in ORDER BY",
                                           "ties need a deterministic secondary key"],
                            "big_o_time": "O(n log n) with the sort", "big_o_space": "O(u)"},
                "tables": {"customers": 2, "orders": 4}}

    def _sc_dept_avg_salary(self, rng):
        depts = rng.sample(["core", "web", "data", "infra", "sec"], rng.randint(2, 4))
        names = _names(rng, rng.randint(8, 16))
        emp_rows = [(i, names[i % len(names)] + str(i), rng.choice(depts),
                     rng.randint(30, 120) * 1000) for i in range(len(names))]
        # Force an exact integer average for every dept (sum divisible by count).
        by_dept = {}
        for _, _, d, s in emp_rows:
            by_dept.setdefault(d, []).append(s)
        fixed = []
        for i, (_, name, d, s) in enumerate(emp_rows):
            rows_d = [r for r in fixed if r[2] == d]
            fixed.append((i, name, d, s))
        # Adjust the last employee of each dept so the sum divides evenly.
        for d in depts:
            idxs = [k for k, r in enumerate(fixed) if r[2] == d]
            vals = [fixed[k][3] for k in idxs]
            c = len(vals)
            target = sum(vals)
            k = idxs[-1]
            remainder = target % c
            old = fixed[k]
            fixed[k] = (old[0], old[1], old[2], old[3] - remainder)
        answer = ("SELECT department, AVG(salary) AS avg_salary, COUNT(*) AS headcount\n"
                  "FROM employees\nGROUP BY department\n"
                  "HAVING COUNT(*) >= 2\nORDER BY avg_salary DESC, department ASC;")
        by_dept = {}
        for _, _, d, s in fixed:
            by_dept.setdefault(d, []).append(s)
        expected = [[d, sum(v) / len(v), len(v)] for d, v in sorted(by_dept.items()) if len(v) >= 2]
        expected.sort(key=lambda r: (-r[1], r[0]))
        setup = _mk_table("employees", [("id", "i"), ("name", "t"),
                                        ("department", "t"), ("salary", "i")], fixed)
        return {"setup": setup, "answer": answer.rstrip(";"),
                "expected": expected,
                "task": ("Write ONE SQLite query over employees(id, name, department, salary) that "
                         "returns department, average salary (alias avg_salary) and headcount for "
                         "departments with at least two employees, ordered by average salary "
                         "descending then department name ascending."),
                "explain": {"purpose": "Group-level statistics filtered with HAVING.",
                            "approach": "GROUP BY department; HAVING filters groups (WHERE filters rows).",
                            "key_points": ["HAVING applies after aggregation",
                                           "AVG over salaries that divide evenly keeps integer-ish results"],
                            "big_o_time": "O(n log n)", "big_o_space": "O(g)"},
                "tables": {"employees": 4}}

    def _sc_library_top(self, rng):
        titles = rng.sample(["Dune", "Neuromancer", "Snow Crash", "Cryptonomicon",
                             "Hyperion", "Ilium", "Anathem"], rng.randint(4, 6))
        book_rows = [(i, titles[i], rng.choice(["scifi", "fantasy", "tech"]))
                     for i in range(len(titles))]
        loans = []
        for _ in range(rng.randint(6, 20)):
            loans.append((len(loans), rng.randrange(len(titles)),
                          f"2026-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}"))
        top = rng.randint(2, 3)
        answer = (f"SELECT b.title, COUNT(l.id) AS loans\n"
                  f"FROM books b LEFT JOIN loans l ON l.book_id = b.id\n"
                  f"GROUP BY b.title\nORDER BY loans DESC, b.title ASC\nLIMIT {top};")
        counts = {i: 0 for i in range(len(titles))}
        for _, bid, _d in loans:
            counts[bid] += 1
        expected = [[titles[i], c] for i, c in counts.items()]
        expected.sort(key=lambda r: (-r[1], r[0]))
        expected = expected[:top]
        setup = (_mk_table("books", [("id", "i"), ("title", "t"), ("genre", "t")], book_rows)
                 + "\n" + _mk_table("loans", [("id", "i"), ("book_id", "i"),
                                              ("borrowed_on", "t")], loans))
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": (f"Write ONE SQLite query that returns the top {top} book titles by number "
                         f"of loans (alias loans), including books with zero loans, ties broken by "
                         f"title ascending."),
                "explain": {"purpose": "LEFT JOIN preserves zero-loan books.",
                            "approach": "LEFT JOIN + COUNT(l.id) counts only existing loans.",
                            "key_points": ["COUNT(column) skips NULLs; COUNT(*) would not",
                                           "LIMIT after ORDER BY"],
                            "big_o_time": "O(n log n)", "big_o_space": "O(b)"},
                "tables": {"books": 3, "loans": 3}}

    def _sc_low_stock(self, rng):
        prods = rng.sample(["bolt", "nut", "washer", "screw", "rivet", "clamp"], 6)
        rows = [(i, prods[i], rng.randint(0, 40), rng.choice(["A1", "B2", "C3"]))
                for i in range(6)]
        thr = rng.randint(5, 15)
        answer = (f"SELECT sku, name, stock, location\nFROM parts\nWHERE stock <= {thr}\n"
                  f"ORDER BY stock ASC, name ASC;")
        expected = [[i, n, s, l] for i, n, s, l in rows if s <= thr]
        expected.sort(key=lambda r: (r[2], r[1]))
        setup = _mk_table("parts", [("sku", "i"), ("name", "t"), ("stock", "i"),
                                    ("location", "t")], rows)
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": (f"Write ONE SQLite query returning sku, name, stock, location for parts "
                         f"with stock at or below {thr}, ordered by stock ascending then name."),
                "explain": {"purpose": "Threshold filter with deterministic ordering.",
                            "approach": "WHERE with <= covers the boundary; ORDER BY two keys.",
                            "key_points": ["at-or-below means <=", "full row projection"],
                            "big_o_time": "O(n log n)", "big_o_space": "O(k)"},
                "tables": {"parts": 4}, "difficulty": "beginner"}

    def _sc_student_averages(self, rng):
        students = _names(rng, rng.randint(4, 6))
        st_rows = [(i, students[i], rng.choice(["9A", "9B"])) for i in range(len(students))]
        gr_rows = []
        gid = 0
        for sid in range(len(students)):
            for _ in range(rng.randint(2, 4)):
                gr_rows.append((gid, sid, rng.randint(4, 10)))
                gid += 1
        # Exact averages: adjust last grade of each student.
        by_s = {}
        for _, s, g in gr_rows:
            by_s.setdefault(s, []).append(g)
        for s, vals in list(by_s.items()):
            c = len(vals)
            rem = sum(vals) % c
            if rem:
                idx = max(k for k, r in enumerate(gr_rows) if r[1] == s)
                gr_rows[idx] = (gr_rows[idx][0], s, gr_rows[idx][2] - rem)
        answer = ("SELECT s.name, ROUND(AVG(g.score), 2) AS avg_score, COUNT(*) AS n_grades\n"
                  "FROM students s JOIN grades g ON g.student_id = s.id\n"
                  "GROUP BY s.name\nORDER BY avg_score DESC, s.name ASC;")
        by_s = {}
        for _, s, g in gr_rows:
            by_s.setdefault(s, []).append(g)
        expected = [[students[s], sum(v) / len(v), len(v)] for s, v in sorted(by_s.items())]
        expected = [[n, round(a, 2), c] for n, a, c in expected]
        expected.sort(key=lambda r: (-r[1], r[0]))
        setup = (_mk_table("students", [("id", "i"), ("name", "t"), ("class", "t")], st_rows)
                 + "\n" + _mk_table("grades", [("id", "i"), ("student_id", "i"),
                                               ("score", "i")], gr_rows))
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": ("Write ONE SQLite query joining students and grades returning name, average "
                         "score rounded to 2 decimals (alias avg_score) and number of grades, ordered "
                         "by avg_score descending then name ascending."),
                "explain": {"purpose": "Join + aggregate with explicit rounding.",
                            "approach": "ROUND(AVG(...), 2) inside the select list.",
                            "key_points": ["ROUND is applied per group after aggregation",
                                           "COUNT(*) counts grade rows"],
                            "big_o_time": "O(n log n)", "big_o_space": "O(s)"}}

    def _sc_monthly_totals(self, rng):
        names = _names(rng, 4)
        pay_rows = []
        for i in range(rng.randint(10, 24)):
            month = rng.randint(1, 6)
            pay_rows.append((i, names[rng.randrange(4)],
                             rng.randint(100, 2000),
                             f"2026-{month:02d}-{rng.randint(10, 28):02d}"))
        answer = ("SELECT strftime('%Y-%m', paid_at) AS month, SUM(amount) AS total, COUNT(*) AS n\n"
                  "FROM payments\nGROUP BY month\nORDER BY month ASC;")
        agg = {}
        for _, _n, amt, date in pay_rows:
            m = date[:7]
            a, c = agg.get(m, (0, 0))
            agg[m] = (a + amt, c + 1)
        expected = [[m, t, c] for m, (t, c) in sorted(agg.items())]
        setup = _mk_table("payments", [("id", "i"), ("payer", "t"), ("amount", "i"),
                                       ("paid_at", "t")], pay_rows)
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": ("Write ONE SQLite query grouping payments by month (use "
                         "strftime('%Y-%m', paid_at), alias month) returning month, SUM(amount) as "
                         "total and COUNT(*) as n, ordered by month ascending."),
                "explain": {"purpose": "Date truncation to month buckets.",
                            "approach": "strftime extracts 'YYYY-MM'; group by the expression alias.",
                            "key_points": ["GROUP BY can reference select aliases in SQLite",
                                           "ISO dates sort lexicographically"],
                            "big_o_time": "O(n log m)", "big_o_space": "O(m)"}}

    def _sc_last_login(self, rng):
        users = _names(rng, rng.randint(4, 6))
        events = []
        eid = 0
        for u in users:
            for _ in range(rng.randint(1, 4)):
                events.append((eid, u, f"2026-05-{rng.randint(10, 28):02d}"))
                eid += 1
        rng.shuffle(events)
        answer = ("SELECT username, MAX(login_day) AS last_day\nFROM logins\n"
                  "GROUP BY username\nORDER BY username ASC;")
        agg = {}
        for _, u, d in events:
            if u not in agg or d > agg[u]:
                agg[u] = d
        expected = [[u, d] for u, d in sorted(agg.items())]
        setup = _mk_table("logins", [("id", "i"), ("username", "t"), ("login_day", "t")], events)
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": ("Write ONE SQLite query returning each username and its latest login_day "
                         "(alias last_day), sorted by username ascending."),
                "explain": {"purpose": "Greatest-per-group with MAX.",
                            "approach": "MAX over ISO dates uses lexicographic order = chronological.",
                            "key_points": ["ISO-8601 dates compare correctly as text",
                                           "GROUP BY yields one row per user"],
                            "big_o_time": "O(n)", "big_o_space": "O(u)"},
                "difficulty": "intermediate"}

    def _sc_cheapest_route(self, rng):
        cities = rng.sample(["MAD", "BCN", "LIS", "CDG", "FRA", "AMS"], 4)
        legs = []
        for i in range(rng.randint(6, 14)):
            a, b = rng.sample(cities, 2)
            legs.append((i, a, b, rng.randint(40, 400)))
        answer = ("SELECT origin, destination, MIN(price) AS best\nFROM flights\n"
                  "GROUP BY origin, destination\nORDER BY origin ASC, destination ASC;")
        agg = {}
        for _, a, b, p in legs:
            k = (a, b)
            if k not in agg or p < agg[k]:
                agg[k] = p
        expected = [[a, b, p] for (a, b), p in sorted(agg.items())]
        setup = _mk_table("flights", [("id", "i"), ("origin", "t"),
                                      ("destination", "t"), ("price", "i")], legs)
        return {"setup": setup, "answer": answer.rstrip(";"), "expected": expected,
                "task": ("Write ONE SQLite query returning origin, destination and the cheapest "
                         "price (alias best) for every route, ordered by origin then destination."),
                "explain": {"purpose": "Cheapest-per-group via MIN with compound grouping.",
                            "approach": "GROUP BY both endpoints; MIN aggregates across duplicates.",
                            "key_points": ["compound group keys",
                                           "ORDER BY two keys keeps output deterministic"],
                            "big_o_time": "O(n log r)", "big_o_space": "O(r)"},
                "difficulty": "intermediate"}

    def _sc_upsert_catalog(self, rng):
        skus = [f"P{i}" for i in range(4)]
        cat_rows = [(skus[i], rng.randint(1, 9), rng.randint(5, 90)) for i in range(4)]
        rows = {s: (q, p) for s, q, p in cat_rows}
        upd_sku = skus[rng.randrange(4)]
        upd = (upd_sku, rng.randint(1, 9), rng.randint(5, 90))
        final = dict(rows)
        final[upd_sku] = (upd[1], upd[2])
        final["P9"] = (3, 42)
        answer = ("INSERT INTO catalog (sku, qty, price) VALUES (?, ?, ?)\n"
                  "ON CONFLICT(sku) DO UPDATE SET qty = excluded.qty, price = excluded.price;")
        cases = [
            {"name": "concrete_upsert_then_select",
             "prelude": (f"INSERT INTO catalog (sku, qty, price) VALUES ('{upd[0]}', {upd[1]}, {upd[2]})\n"
                         "ON CONFLICT(sku) DO UPDATE SET qty = excluded.qty, price = excluded.price;\n"
                         "INSERT INTO catalog (sku, qty, price) VALUES ('P9', 3, 42)\n"
                         "ON CONFLICT(sku) DO UPDATE SET qty = excluded.qty, price = excluded.price;\n"),
             "sql": "SELECT sku, qty, price FROM catalog ORDER BY sku ASC;",
             "expected": [[s, q, p] for s, (q, p) in sorted(final.items())]},
        ]
        setup = ("CREATE TABLE catalog (sku TEXT PRIMARY KEY, qty INTEGER, price INTEGER);\n"
                 + "\n".join(f"INSERT INTO catalog VALUES ('{s}', {q}, {p});" for s, (q, p) in rows.items()))
        return {"setup": setup, "answer": answer.rstrip(";"),
                "expected": [],
                "task": ("Write ONE SQLite upsert statement: INSERT INTO catalog (sku, qty, price) "
                         "VALUES (?, ?, ?) that updates qty and price from the excluded row when the "
                         "sku already exists (ON CONFLICT)."),
                "explain": {"purpose": "Idempotent insert-or-update with ON CONFLICT.",
                            "approach": "excluded.* references the row that failed to insert.",
                            "key_points": ["excluded.qty is the proposed value",
                                           "the conflict target must match a unique constraint"],
                            "big_o_time": "O(log n) with the PK index", "big_o_space": "O(1)"},
                "extras": cases, "no_answer_case": True}

    def _sc_index_speedup(self, rng):
        cols = rng.sample(["alpha", "beta", "gamma", "delta", "epsilon"], 5)
        rows = [(i, cols[i % 5], rng.randint(1, 100)) for i in range(20)]
        idx_name = f"idx_events_{rng.choice(['label', 'kind', 'tag'])}"
        answer = (f"-- Accelerates equality lookups and range scans on the label column\n"
                  f"CREATE INDEX {idx_name} ON events (label);")
        cases = [
            {"name": "index_exists", "run_answer_first": True,
             "sql": ("SELECT name FROM sqlite_master WHERE type = 'index' AND name = "
                     f"'{idx_name}';"),
             "expected": [[idx_name]]},
            {"name": "query_still_correct",
             "sql": (f"SELECT COUNT(*) FROM events WHERE label = '{cols[0]}';"),
             "expected": [[sum(1 for _, l, _ in rows if l == cols[0])]]},
        ]
        setup = _mk_table("events", [("id", "i"), ("label", "t"), ("value", "i")], rows)
        return {"setup": setup, "answer": answer,
                "expected": [],
                "task": (f"Write ONE SQLite statement that creates an index named {idx_name} on the "
                         f"label column of the events table."),
                "explain": {"purpose": "Index creation to accelerate equality lookups.",
                            "approach": "CREATE INDEX builds a B-tree over (label).",
                            "key_points": ["indexes speed reads, slow writes",
                                           "sqlite_master reflects new indexes"],
                            "big_o_time": "O(n log n) build", "big_o_space": "O(n)"},
                "extras": cases, "difficulty": "intermediate"}


register(globals(), SQLQueryFamily)
