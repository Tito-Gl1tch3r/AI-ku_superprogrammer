"""Dataset-1 write families for Java (static-verified: no JDK in this sandbox).

Java has no javac here, so verification is structural (static_check). The
templates are conservative canonical Java 17 that would compile on a real
toolchain; records carry verification.method = "static_check" honestly.
"""
from __future__ import annotations

import random

from ..core import Candidate, Family, FileSpec, register


class JavaOopFamily(Family):
    NAME = "java_oop"
    LANGUAGE = "java"
    DOMAIN = "engineering"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "code_review", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["shape_iface", "employee_record"])
        if kind == "shape_iface":
            w, h = rng.randint(2, 12), rng.randint(2, 12)
            s = rng.randint(2, 9)
            code = (
                f"public class Main {{\n\n"
                f"    interface Shape {{\n"
                f"        double area();\n"
                f"    }}\n\n"
                f"    static class Rect implements Shape {{\n"
                f"        private final double w, h;\n"
                f"        Rect(double w, double h) {{ this.w = w; this.h = h; }}\n"
                f"        @Override public double area() {{ return w * h; }}\n"
                f"        @Override public String toString() {{ return \"Rect(\" + w + \"x\" + h + \")\"; }}\n"
                f"    }}\n\n"
                f"    static class Sq implements Shape {{\n"
                f"        private final double side;\n"
                f"        Sq(double side) {{ this.side = side; }}\n"
                f"        @Override public double area() {{ return side * side; }}\n"
                f"    }}\n\n"
                f"    public static void main(String[] args) {{\n"
                f"        Shape r = new Rect({w}, {h});\n"
                f"        Shape s = new Sq({s});\n"
                f"        double total = r.area() + s.area();\n"
                f"        System.out.println(r + \" -> \" + r.area());\n"
                f"        System.out.println(\"total=\" + total);\n"
                f"    }}\n"
                f"}}\n")
            expected = f"Rect({w}x{h}) area {w * h}; total {w * h + s * s} via polymorphic dispatch."
        else:  # employee_record
            code = (
                "public class Main {\n\n"
                "    static class Employee {\n"
                "        private final String name;\n"
                "        private final int level;\n"
                "        Employee(String name, int level) {\n"
                "            if (name == null || name.isBlank())\n"
                "                throw new IllegalArgumentException(\"name required\");\n"
                "            this.name = name;\n"
                "            this.level = level;\n"
                "        }\n"
                "        String name() { return name; }\n"
                "        int level() { return level; }\n"
                "        @Override public String toString() {\n"
                "            return name + \"(L\" + level + \")\";\n"
                "        }\n"
                "    }\n\n"
                "    public static void main(String[] args) {\n"
                "        Employee e = new Employee(\"ada\", 4);\n"
                "        System.out.println(e);\n"
                "    }\n"
                "}\n")
            expected = "Immutable Employee value object with constructor validation and toString."
        return Candidate(
            family=self.NAME, language="java", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write the Java program (single file, one public class Main): {expected} "
                  f"Use interfaces/encapsulation exactly as described; the class compiles "
                  f"standalone with javac and runs with java."),
            expected_behavior=expected, code=code, verify_method="static_check",
            notes={"explain": {"purpose": expected,
                               "approach": "Interface + final fields + ctor validation.",
                               "key_points": ["single public class per file",
                                              "final fields make instances immutable",
                                              "@Override catches signature drift"],
                               "big_o_time": "O(1)", "big_o_space": "O(1)",
                               "edge_cases": ["blank name rejected", "polymorphic area dispatch"]}},
            tags=["java", kind], variant=kind, seed=rng.randrange(2**31))


class JavaCollectionsFamily(Family):
    NAME = "java_collections"
    LANGUAGE = "java"
    DOMAIN = "algorithms"
    DIFFICULTIES = ("intermediate", "advanced")
    SUPPORTS = ("explanation", "code_review", "complexity")

    def generate(self, rng: random.Random) -> Candidate:
        kind = rng.choice(["word_count", "optional_chain"])
        if kind == "word_count":
            words = [rng.choice(["api", "db", "cache", "queue", "worker"])
                     for _ in range(rng.randint(8, 20))]
            wl = ", ".join(f'"{w}"' for w in words)
            code = (
                f"import java.util.*;\nimport java.util.stream.*;\n\n"
                f"public class Main {{\n"
                f"    static Map<String, Long> countWords(List<String> words) {{\n"
                f"        return words.stream()\n"
                f"            .collect(Collectors.groupingBy(w -> w, TreeMap::new, Collectors.counting()));\n"
                f"    }}\n\n"
                f"    public static void main(String[] args) {{\n"
                f"        List<String> words = List.of({wl});\n"
                f"        countWords(words).forEach((k, v) -> System.out.println(k + \"=\" + v));\n"
                f"    }}\n"
                f"}}\n")
            from collections import Counter
            c = Counter(words)
            expected = f"TreeMap orders keys alphabetically: {dict(sorted(c.items()))}."
        else:  # optional_chain
            code = (
                "import java.util.Optional;\n\n"
                "public class Main {\n\n"
                "    static Optional<String> findUser(String id) {\n"
                "        return \"ada\".equals(id) ? Optional.of(\"ada@example.test\")\n"
                "                                  : Optional.empty();\n"
                "    }\n\n"
                "    public static void main(String[] args) {\n"
                "        String mail = findUser(\"ada\")\n"
                "            .map(String::toUpperCase)\n"
                "            .orElse(\"guest\");\n"
                "        System.out.println(mail);\n"
                "        System.out.println(findUser(\"ghost\").orElse(\"missing\"));\n"
                "    }\n"
                "}\n")
            expected = "ADA@EXAMPLE.TEST then missing; Optional chains avoid null checks."
        return Candidate(
            family=self.NAME, language="java", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Write the Java program (single public class Main): {expected} Use the "
                  f"Collections/streams/Optional APIs exactly as described; no external "
                  f"libraries; the file must compile with javac 17+."),
            expected_behavior=expected, code=code, verify_method="static_check",
            notes={"explain": {"purpose": expected,
                               "approach": "Streams collect / Optional monadic chain.",
                               "key_points": ["groupingBy with TreeMap keeps keys sorted",
                                              "counting() downstream collects frequencies",
                                              "Optional.map/orElse avoid NPEs"],
                               "big_o_time": "O(n) (plus sort for TreeMap)",
                               "big_o_space": "O(u) distinct keys",
                               "edge_cases": ["empty list", "missing keys", "null-free design"]}},
            tags=["java", "collections", kind], variant=kind, seed=rng.randrange(2**31))


class JavaProjectFamily(Family):
    NAME = "java_project_multifile"
    LANGUAGE = "java"
    DOMAIN = "engineering"
    DIFFICULTIES = ("advanced", "expert")
    SUPPORTS = ("architecture", "explanation")
    PROJECT_FAMILY = True

    def generate(self, rng: random.Random) -> Candidate:
        domain = rng.choice(["inventory", "todo", "roster"])
        items = rng.sample(["alpha", "beta", "gamma", "delta"], rng.randint(2, 4))
        main = (
            f"public class Main {{\n"
            f"    public static void main(String[] args) {{\n"
            f"        {domain.capitalize()}Service service = new {domain.capitalize()}Service();\n"
            + "".join(f"        service.add(\"{it}\", {rng.randint(1, 9)});\n" for it in items)
            + f"        System.out.println(service.snapshot());\n"
            f"    }}\n"
            f"}}\n")
        helper = (
            f"import java.util.*;\n\n"
            f"class {domain.capitalize()}Service {{\n"
            f"    private final Map<String, Integer> data = new TreeMap<>();\n\n"
            f"    void add(String key, int qty) {{\n"
            f"        data.merge(key, qty, Integer::sum);\n"
            f"    }}\n\n"
            f"    Map<String, Integer> snapshot() {{\n"
            f"        return Collections.unmodifiableMap(new TreeMap<>(data));\n"
            f"    }}\n"
            f"}}\n")
        readme = (f"# {domain}-service\n\nTwo-file Java project (default package).\n\n"
                  f"- `Main.java`: entry point\n"
                  f"- `{domain.capitalize()}Service.java`: service with merge + unmodifiable snapshot\n\n"
                  f"Build: `javac Main.java {domain.capitalize()}Service.java && java Main`\n")
        files = [FileSpec("Main.java", main),
                 FileSpec(f"{domain.capitalize()}Service.java", helper),
                 FileSpec("README.md", readme)]
        counts = {}
        for it in items:
            counts[it] = counts.get(it, 0) + 1
        return Candidate(
            family=self.NAME, language="java", domain=self.DOMAIN,
            difficulty=rng.choice(self.DIFFICULTIES),
            task=(f"Assemble the two-file Java project in README.md: {domain.capitalize()}Service "
                  f"(TreeMap storage, merge for upsert, unmodifiable snapshot) plus Main that adds "
                  f"{items} and prints the snapshot. Only Main.java is public-class; the service "
                  f"file holds a package-private class so both compile side by side."),
            expected_behavior=f"snapshot() returns sorted counts {counts} and rejects external mutation.",
            files=files, entry="Main.java", verify_method="static_check", is_project=True,
            notes={"explain": {"purpose": "Package-private service + public entry pattern.",
                               "approach": "TreeMap ordering, merge() upsert, defensive snapshot copy.",
                               "key_points": ["one public class per file",
                                              "unmodifiableMap guards internal state",
                                              "merge implements upsert atomically"],
                               "big_o_time": "O(log n) per add", "big_o_space": "O(n)",
                               "edge_cases": ["duplicate keys accumulate", "snapshot immutability"]}},
            tags=["java", "project", domain], variant=domain, seed=rng.randrange(2**31))


register(globals(), JavaOopFamily)
register(globals(), JavaCollectionsFamily)
register(globals(), JavaProjectFamily)
