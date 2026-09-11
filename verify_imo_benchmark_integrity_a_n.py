from pathlib import Path
import hashlib
import json
import re

EXPECTED_SOURCE = "SRC-IMO-MSC385-94"
EXPECTED_BATCH_COUNTS = {
    "a": (13, 83),
    "b": (6, 39),
    "c": (9, 41),
    "d": (7, 62),
    "e": (7, 60),
    "f": (9, 68),
    "g": (10, 82),
    "h": (4, 33),
    "i": (9, 65),
    "j": (7, 37),
    "k": (7, 75),
    "l": (7, 52),
    "m": (8, 59),
    "n": (6, 49),
}


def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    candidates += list(Path(__file__).resolve().parents)
    for c in candidates:
        root = c / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"
        r13 = c / "MVP" / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"
        if root.exists() and (r13 / "requirement_term_index.json").exists():
            return c.resolve()
    raise RuntimeError("Could not locate NLTL_v2 repository root")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


REPO = find_repo()
ROOT = REPO / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"
R13 = REPO / "MVP" / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"
index = json.loads((R13 / "requirement_term_index.json").read_text())
all_complete = {
    req for req, contract in index["dependencyContracts"].items()
    if req.startswith("IMO-") and contract.get("status") == "COMPLETE"
}

all_req = []
all_case = []
all_path = []
overall = True

print("IMO Polar Code systematic benchmark integrity A-N")
for batch in "abcdefghijklmn":
    manifest_path = ROOT / "manifests" / f"imo_batch_{batch}_manifest.jsonl"
    lock_path = ROOT / "locks" / f"imo_batch_{batch}_fixture_lock.json"
    if not manifest_path.exists() or not lock_path.exists():
        print(f"Batch {batch.upper()}: MISSING manifest/lock")
        overall = False
        continue

    rows = [json.loads(line) for line in manifest_path.read_text().splitlines() if line.strip()]
    lock = json.loads(lock_path.read_text())
    reqs = sorted({row["requirement_id"] for row in rows})

    hashes_ok = True
    naming_ok = True
    provenance_ok = True
    count_ok = True

    exp_req, exp_case = EXPECTED_BATCH_COUNTS[batch]
    if len(reqs) != exp_req or len(rows) != exp_case:
        count_ok = False
        overall = False
        print(
            f"  unexpected batch counts: got {len(reqs)} requirements/{len(rows)} cases; "
            f"expected {exp_req}/{exp_case}"
        )

    if (
        len(reqs) != lock.get("requirement_count")
        or len(rows) != lock.get("case_count")
        or sorted(lock.get("requirements", [])) != reqs
    ):
        count_ok = False
        overall = False
        print("  lock count/requirement-list mismatch")

    for rel, expected_hash in lock.get("frozen_files", {}).items():
        path = ROOT / rel
        if not path.exists() or sha256(path) != expected_hash:
            hashes_ok = False
            overall = False
            print("  hash mismatch:", rel)

    for row in rows:
        req = row.get("requirement_id", "")
        cid = row.get("case_id", "")
        rdf_path = row.get("rdf_path", "")
        if (
            not re.fullmatch(r"IMO-\d{3}", req)
            or not cid.startswith(req + "-")
            or rdf_path != f"rdf/IMO/{req}/{cid}.ttl"
        ):
            naming_ok = False
            overall = False
            print("  naming/path mismatch:", req, cid, rdf_path)

        if (
            row.get("source_id") != EXPECTED_SOURCE
            or not row.get("source_clause")
            or row.get("generated_shacl_inspected") is not False
        ):
            provenance_ok = False
            overall = False
            print("  provenance mismatch:", cid)

        if req not in all_complete:
            provenance_ok = False
            overall = False
            print("  requirement is not frozen COMPLETE:", req)

    all_req += reqs
    all_case += [row["case_id"] for row in rows]
    all_path += [row["rdf_path"] for row in rows]

    print(
        f"Batch {batch.upper()}: {len(reqs):2d} requirements / {len(rows):3d} cases / "
        f"hashes {'PASS' if hashes_ok else 'FAIL'} / "
        f"naming {'PASS' if naming_ok else 'FAIL'} / "
        f"provenance {'PASS' if provenance_ok else 'FAIL'} / "
        f"counts {'PASS' if count_ok else 'FAIL'}"
    )

req_disjoint = len(set(all_req)) == len(all_req)
case_unique = len(set(all_case)) == len(all_case)
path_unique = len(set(all_path)) == len(all_path)
covered = set(all_req)
coverage_exact = covered == all_complete
expected_total_ok = len(covered) == 109 and len(all_case) == 805

overall = (
    overall
    and req_disjoint
    and case_unique
    and path_unique
    and coverage_exact
    and expected_total_ok
)

print(f"Unique systematic IMO requirements: {len(covered)}")
print(f"Systematic IMO RDF cases: {len(all_case)}")
print(
    "R13 IMO COMPLETE coverage: "
    + (f"PASS ({len(covered)}/{len(all_complete)})" if coverage_exact else f"FAIL ({len(covered)}/{len(all_complete)})")
)
if not coverage_exact:
    missing = sorted(all_complete - covered)
    extra = sorted(covered - all_complete)
    if missing:
        print("Missing COMPLETE requirements:", ", ".join(missing))
    if extra:
        print("Unexpected requirements:", ", ".join(extra))
print("Expected final IMO totals (109 requirements / 805 cases): " + ("PASS" if expected_total_ok else "FAIL"))
print("Cross-batch requirement disjointness: " + ("PASS" if req_disjoint else "FAIL"))
print("Cross-batch case/path uniqueness: " + ("PASS" if case_unique and path_unique else "FAIL"))
print("IMO naming/provenance discipline: " + ("PASS" if overall else "FAIL"))
print("Overall IMO integrity status: " + ("PASS" if overall else "FAIL"))
raise SystemExit(0 if overall else 1)
