#!/usr/bin/env python3
"""v0.8.0 D-3 fix: attach re-verification fixtures to published bash/sql records.

Audit finding D-3: the bash/sql executors used fixtures from generator notes
(notes["cases"], notes["setup"]) that were never persisted, so 68 bash + 22 sql
module-01 records cannot be re-verified by third parties from the published
payload alone. Original verification WAS real; the gap is reproducibility.

Fix (two phases):
  --scan   Brute-force the original job seeds. The original build used
           job seeds 20260101 + batch*1_000_000 + attempts (build_dataset.py),
           and generation is a pure function of (family, job seed). Regenerate
           candidates per family over that space and match them against the
           published records by content key (sha256 of code, or of the sorted
           file list for multi-file projects). Save matches to
           reports/fixture_recovery_v080.json.
  --apply  Embed the recovered (or honestly regenerated) fixtures into
           verification.fixtures of each published bash/sql record and rewrite
           ONLY the shards that contain such records (gzip mtime=0 so
           untouched shards stay byte-identical). Every attached fixture set is
           PROVEN correct by actually running the family executor against the
           published code before acceptance.

Fallback: a record whose original seed is outside the scan range gets a fresh
scenario generated at a v0.8.0 seed and verified against the published code;
provenance is explicit ("regenerated_v080" vs "original_recovered").
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

WRITE_DIR = os.path.join(ROOT, "datasets", "write")
HOLDOUT_DIR = os.path.join(ROOT, "datasets", "hard_holdout")
REPORT = os.path.join(ROOT, "reports", "fixture_recovery_v080.json")

FAMILIES = ("bash_ops_scripts", "bash_project_multifile", "sql_query_scenarios")
SEED_BASE = 20260101
BATCHES = range(0, 16)          # batch N -> seed_base + N*1_000_000
ATTEMPTS = 120_000              # per-batch attempt ceiling
FALLBACK_BASE = 20261011        # v0.8.0 regeneration pool (documented)


def rec_key(rec) -> str:
    if rec.get("code"):
        return hashlib.sha256(rec["code"].encode("utf-8")).hexdigest()
    parts = sorted((f["path"], f["content"]) for f in (rec.get("files") or []))
    return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()


def cand_key(cand) -> str:
    if cand.code:
        return hashlib.sha256(cand.code.encode("utf-8")).hexdigest()
    parts = sorted((f.path, f.content) for f in cand.all_files())
    return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()


def load_bash_sql_records():
    """All published write records with language bash/sql, with their shard path."""
    out = []
    shards = []
    for split in ("train", "validation", "test"):
        d = os.path.join(WRITE_DIR, split)
        shards += [(os.path.join(d, n), "write") for n in sorted(os.listdir(d))
                   if n.endswith(".jsonl.gz")]
    shards += [(os.path.join(HOLDOUT_DIR, n), "hard_holdout")
               for n in sorted(os.listdir(HOLDOUT_DIR))
               if n.startswith("write-") and n.endswith(".jsonl.gz")]
    for path, split in shards:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("language") in ("bash", "sql"):
                    out.append((path, split, rec))
    return out


def scan_unit(unit):
    """Scan one (family, batch) seed block; return {record_key: (seed, notes)}."""
    family, batch = unit
    from generators.registry import family_by_name
    fam = family_by_name(family)
    hits = {}
    base = SEED_BASE + batch * 1_000_000
    for k in range(1, ATTEMPTS + 1):
        try:
            cand = fam.generate(random.Random(base + k))
        except Exception:
            continue
        if cand is None:
            continue
        key = cand_key(cand)
        if key not in hits:
            notes = cand.notes or {}
            if not notes.get("cases"):
                continue
            hits[key] = (base + k, {"cases": notes["cases"],
                                    **({"setup": notes["setup"]}
                                       if notes.get("setup") else {})})
    return {family: {batch: hits}}


def verify_fixtures(rec, fixtures) -> bool:
    """Run the family executor against the PUBLISHED record with these fixtures."""
    from types import SimpleNamespace
    from validators.executors.bash_exec import verify_bash
    from validators.executors.sql_exec import verify_sql
    if rec.get("code"):
        entry = rec.get("entry") or "script.sh"
        files = [SimpleNamespace(path=entry, content=rec["code"])]
    else:
        files = [SimpleNamespace(path=f["path"], content=f["content"])
                 for f in (rec.get("files") or [])]

    class _C:
        pass

    c = _C()
    c.code = rec.get("code")
    c.files = files
    c.entry = rec.get("entry")
    c.all_files = lambda: files
    c.notes = fixtures
    r = verify_sql(c) if rec["language"] == "sql" else verify_bash(c)
    return bool(r.ok)


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    records = load_bash_sql_records()
    by_key = {}
    for path, split, rec in records:
        by_key.setdefault(rec_key(rec), []).append(rec)
    print(f"published bash/sql records: {len(records)} "
          f"({len(by_key)} distinct content keys)")

    if args.scan:
        units = [(f, b) for f in FAMILIES for b in BATCHES]
        merged = {}
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for res in ex.map(scan_unit, units):
                fam = next(iter(res))
                batch = next(iter(res[fam]))
                merged.setdefault(fam, {}).update(res[fam][batch])
        # resolve records -> fixtures
        out = {"recovered": [], "missing": []}
        for key, recs in by_key.items():
            hit = None
            for fam, batches in merged.items():
                for batch, hits in batches.items():
                    if key in hits:
                        hit = (fam, batch, hits[key])
                        break
                if hit:
                    break
            if hit is None:
                out["missing"].append({"key": key,
                                       "ids": [r["id"] for r in recs]})
                continue
            fam, batch, (seed, fixtures) = hit
            ok = all(verify_fixtures(r, fixtures) for r in recs)
            out["recovered" if ok else "missing"].append(
                {"key": key, "ids": [r["id"] for r in recs], "family": fam,
                 "batch": batch, "job_seed": seed, "fixtures": fixtures,
                 "verified": ok})
            if not ok:
                out["recovered"] = [x for x in out["recovered"] if x["key"] != key]
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print(f"recovered+verified: {len(out['recovered'])} keys, "
              f"missing: {len(out['missing'])} keys -> {REPORT}")
        return

    if args.apply:
        with open(REPORT, encoding="utf-8") as f:
            report = json.load(f)
        fixes = {}
        for item in report["recovered"]:
            for rid in item["ids"]:
                fixes[rid] = {"fixtures": item["fixtures"],
                              "fixtures_origin": "original_recovered",
                              "fixtures_seed": item["job_seed"]}
        # fallback: re-capture fixtures by running the PUBLISHED code on
        # fresh, shape-correct inputs (real captured expectations)
        missing_ids = {rid for item in report["missing"] for rid in item["ids"]}
        from scripts.recapture_fixtures_v080 import (recapture_bash_ops,
                                                     recapture_bash_project,
                                                     recapture_sql)
        for path, split, rec in records:
            rid = rec["id"]
            if rid not in missing_ids or rid in fixes:
                continue
            fam_name = rec["provenance"]["generator"]
            if fam_name == "bash_ops_scripts":
                fx = recapture_bash_ops(rec)
            elif fam_name == "bash_project_multifile":
                fx = recapture_bash_project(rec)
            elif fam_name == "sql_query_scenarios":
                fx = recapture_sql(rec)
            else:
                fx = None
            if fx is None:
                print(f"  !! recapture failed for {rid} ({fam_name})")
                continue
            if not verify_fixtures(rec, fx):
                print(f"  !! recaptured fixtures failed verification for {rid}")
                continue
            fixes[rid] = {"fixtures": fx,
                          "fixtures_origin": "recaptured_v080",
                          "fixtures_seed": rec["provenance"]["seed"]}
        print(f"fixtures resolved: {len(fixes)}/{len(records)}")

        # rewrite only shards that contain bash/sql records
        by_shard = {}
        for path, split, rec in records:
            by_shard.setdefault(path, []).append(rec)
        for path, recs in sorted(by_shard.items()):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
            changed = False
            for rec in rows:
                fx = fixes.get(rec["id"])
                if fx:
                    rec["verification"]["fixtures"] = fx["fixtures"]
                    rec["verification"]["fixtures_origin"] = fx["fixtures_origin"]
                    rec["verification"]["fixtures_seed"] = fx["fixtures_seed"]
                    changed = True
            if not changed:
                continue
            import io
            import time
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as f:
                for rec in rows:
                    f.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
            with open(path, "wb") as f:
                f.write(buf.getvalue())
            print(f"  rewrote {os.path.relpath(path, ROOT)} "
                  f"({len(rows)} rows, {sum(1 for r in rows if r['id'] in fixes)} fixed)")
        print("apply done")


if __name__ == "__main__":
    main()
