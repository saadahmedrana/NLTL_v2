from pathlib import Path
import hashlib
import json


def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents)
    seen = set()
    for c in candidates:
        c = c.resolve()
        if c in seen:
            continue
        seen.add(c)
        if (c / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13").exists():
            return c
    raise RuntimeError("Could not locate NLTL_v2 repository root")


REPO = find_repo()
ROOT = REPO / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"
EXPECTED_SOURCE = "SRC-TRAFICOM-2021"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


all_requirements = []
all_case_ids = []
all_rdf_paths = []
overall = True

print("TRAFICOM systematic benchmark integrity A-I")

for batch in "abcdefghi":
    manifest_path = ROOT / "manifests" / f"traficom_batch_{batch}_manifest.jsonl"
    lock_path = ROOT / "locks" / f"traficom_batch_{batch}_fixture_lock.json"

    if not manifest_path.exists() or not lock_path.exists():
        print(f"Batch {batch.upper()}: MISSING manifest/lock")
        overall = False
        continue

    rows = [json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
    lock = json.loads(lock_path.read_text())
    reqs = sorted(set(r["requirement_id"] for r in rows))

    hashes_ok = True
    naming_ok = True
    provenance_ok = True

    for rel, expected in lock.get("frozen_files", {}).items():
        p = ROOT / rel
        if not p.exists() or sha256(p) != expected:
            hashes_ok = False
            overall = False
            print(f"  hash mismatch: {rel}")

    if len(reqs) != lock.get("requirement_count"):
        overall = False
    if len(rows) != lock.get("case_count"):
        overall = False
    if sorted(lock.get("requirements", [])) != reqs:
        overall = False

    for r in rows:
        req = r.get("requirement_id", "")
        cid = r.get("case_id", "")
        rdf_path = r.get("rdf_path", "")
        expected_path = f"rdf/TRF/{req}/{cid}.ttl"

        if not req.startswith("TRF-") or not cid.startswith(req + "-") or rdf_path != expected_path:
            naming_ok = False
            overall = False
            print(f"  naming/path mismatch: {req} | {cid} | {rdf_path}")

        if r.get("source_id") != EXPECTED_SOURCE or not r.get("source_clause"):
            provenance_ok = False
            overall = False
            print(f"  provenance mismatch: {cid}")

        if r.get("generated_shacl_inspected") is not False:
            provenance_ok = False
            overall = False
            print(f"  benchmark-independence flag mismatch: {cid}")

    all_requirements.extend(reqs)
    all_case_ids.extend(r["case_id"] for r in rows)
    all_rdf_paths.extend(r["rdf_path"] for r in rows)

    print(
        f"Batch {batch.upper()}: "
        f"{len(reqs):2d} requirements / "
        f"{len(rows):3d} cases / "
        f"hashes {'PASS' if hashes_ok else 'FAIL'} / "
        f"naming {'PASS' if naming_ok else 'FAIL'} / "
        f"provenance {'PASS' if provenance_ok else 'FAIL'}"
    )

unique_reqs = len(set(all_requirements))
unique_cases = len(set(all_case_ids))
unique_paths = len(set(all_rdf_paths))

req_disjoint = unique_reqs == len(all_requirements)
case_unique = unique_cases == len(all_case_ids)
path_unique = unique_paths == len(all_rdf_paths)
if not req_disjoint:
    overall = False
    print("Requirement overlap between TRAFICOM batches: FAIL")
if not case_unique:
    overall = False
    print("Duplicate case identifiers between TRAFICOM batches: FAIL")
if not path_unique:
    overall = False
    print("Duplicate RDF paths between TRAFICOM batches: FAIL")

print(f"Unique systematic TRAFICOM requirements: {unique_reqs}")
print(f"Systematic TRAFICOM RDF cases: {len(all_case_ids)}")
print("Cross-batch requirement disjointness: " + ("PASS" if req_disjoint else "FAIL"))
print("Cross-batch case/path uniqueness: " + ("PASS" if case_unique and path_unique else "FAIL"))
print("TRAFICOM naming/provenance discipline: " + ("PASS" if overall else "FAIL"))
print("Overall TRAFICOM integrity status: " + ("PASS" if overall else "FAIL"))

raise SystemExit(0 if overall else 1)
