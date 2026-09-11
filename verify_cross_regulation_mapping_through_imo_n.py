from pathlib import Path
import json

EXPECTED = {
    "IACS I2": (45, 499),
    "TRAFICOM": (99, 755),
    "IMO": (109, 805),
}
EXPECTED_TOTAL = (253, 2059)


def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    candidates += list(Path(__file__).resolve().parents)
    for c in candidates:
        root = c / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"
        if root.exists():
            return c.resolve()
    raise RuntimeError("Could not locate NLTL_v2 repository root")


ROOT = find_repo() / "MVP" / "SHACL_GENERATION_PIPELINE" / "evaluation" / "BEHAVIORAL_RDF_R13"
families = [
    ("IACS I2", "i2", "I2", "SRC-IACS-I2-R4", "abcdefghi"),
    ("TRAFICOM", "traficom", "TRF", "SRC-TRAFICOM-2021", "abcdefghij"),
    ("IMO", "imo", "IMO", "SRC-IMO-MSC385-94", "abcdefghijklmn"),
]

all_req = []
all_case = []
all_path = []
ok = True

print("Cross-regulation systematic mapping integrity through IMO Batch N")
for label, prefix, folder, source, batches in families:
    reqs = []
    cases = []
    paths = []
    family_ok = True

    for batch in batches:
        manifest_path = ROOT / "manifests" / f"{prefix}_batch_{batch}_manifest.jsonl"
        if not manifest_path.exists():
            print(label, "missing", manifest_path.name)
            family_ok = False
            ok = False
            continue

        rows = [json.loads(line) for line in manifest_path.read_text().splitlines() if line.strip()]
        for row in rows:
            req = row.get("requirement_id", "")
            cid = row.get("case_id", "")
            rdf_path = row.get("rdf_path", "")
            if (
                not req.startswith(folder + "-")
                or not cid.startswith(req + "-")
                or rdf_path != f"rdf/{folder}/{req}/{cid}.ttl"
                or row.get("source_id") != source
                or ("generated_shacl_inspected" in row and row.get("generated_shacl_inspected") is not False)
            ):
                family_ok = False
                ok = False
                print("  family mapping mismatch:", label, req, cid, rdf_path)
            reqs.append(req)
            cases.append(cid)
            paths.append(rdf_path)

    unique_reqs = set(reqs)
    expected_req, expected_cases = EXPECTED[label]
    count_ok = len(unique_reqs) == expected_req and len(cases) == expected_cases
    family_ok = family_ok and count_ok
    ok = ok and count_ok

    print(
        f"{label}: {len(unique_reqs)} requirements / {len(cases)} cases / "
        f"family mapping {'PASS' if family_ok else 'FAIL'}"
    )
    if not count_ok:
        print(f"  expected {expected_req} requirements / {expected_cases} cases")

    all_req += list(unique_reqs)
    all_case += cases
    all_path += paths

req_unique = len(all_req) == len(set(all_req))
case_unique = len(all_case) == len(set(all_case))
path_unique = len(all_path) == len(set(all_path))
total_ok = len(set(all_req)) == EXPECTED_TOTAL[0] and len(all_case) == EXPECTED_TOTAL[1]
ok = ok and req_unique and case_unique and path_unique and total_ok

print("Cross-regulation requirement-ID uniqueness: " + ("PASS" if req_unique else "FAIL"))
print("Cross-regulation case-ID uniqueness: " + ("PASS" if case_unique else "FAIL"))
print("Cross-regulation RDF-path uniqueness: " + ("PASS" if path_unique else "FAIL"))
print(f"I2 + TRAFICOM + IMO systematic requirements represented: {len(set(all_req))}")
print(f"I2 + TRAFICOM + IMO systematic RDF cases represented: {len(all_case)}")
print("Expected pre-IMO26 total (253 requirements / 2059 cases): " + ("PASS" if total_ok else "FAIL"))
print("Overall cross-regulation mapping status: " + ("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
