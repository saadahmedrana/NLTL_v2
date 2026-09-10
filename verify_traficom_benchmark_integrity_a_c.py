from pathlib import Path
import hashlib
import json


def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents)
    for c in candidates:
        c = c.resolve()
        if (c / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13").exists():
            return c
    raise RuntimeError("Could not locate NLTL_v2 repository root")


REPO = find_repo()
ROOT = REPO / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


all_requirements = []
all_case_ids = []
all_rdf_paths = []
overall = True

print("TRAFICOM systematic benchmark integrity A-C")

for batch in "abc":
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

    all_requirements.extend(reqs)
    all_case_ids.extend(r["case_id"] for r in rows)
    all_rdf_paths.extend(r["rdf_path"] for r in rows)

    print(
        f"Batch {batch.upper()}: "
        f"{len(reqs):2d} requirements / "
        f"{len(rows):3d} cases / "
        f"hashes {'PASS' if hashes_ok else 'FAIL'}"
    )

unique_reqs = len(set(all_requirements))
unique_cases = len(set(all_case_ids))
unique_paths = len(set(all_rdf_paths))

if unique_reqs != len(all_requirements):
    overall = False
    print("Requirement overlap between TRAFICOM batches: FAIL")
if unique_cases != len(all_case_ids):
    overall = False
    print("Duplicate case identifiers between TRAFICOM batches: FAIL")
if unique_paths != len(all_rdf_paths):
    overall = False
    print("Duplicate RDF paths between TRAFICOM batches: FAIL")

print(f"Unique systematic TRAFICOM requirements: {unique_reqs}")
print(f"Systematic TRAFICOM RDF cases: {len(all_case_ids)}")
print("Cross-batch requirement disjointness: " + ("PASS" if unique_reqs == len(all_requirements) else "FAIL"))
print("Cross-batch case/path uniqueness: " + ("PASS" if unique_cases == len(all_case_ids) and unique_paths == len(all_rdf_paths) else "FAIL"))
print("Overall TRAFICOM integrity status: " + ("PASS" if overall else "FAIL"))

raise SystemExit(0 if overall else 1)
