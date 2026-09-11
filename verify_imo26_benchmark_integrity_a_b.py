from pathlib import Path
import hashlib, json, re

EXPECTED_SOURCE="SRC-IMO26-SUPPLEMENT"
EXPECTED_BATCH_COUNTS={"a":(11,90),"b":(4,37)}

def find_repo():
    candidates=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    for c in candidates:
        root=c/"MVP"/"SHACL_GENERATION_PIPELINE"/"evaluation"/"BEHAVIORAL_RDF_R13"
        r13=c/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
        if root.exists() and (r13/"requirement_term_index.json").exists():return c.resolve()
    raise RuntimeError("Could not locate NLTL_v2 repository root")

def sha256(p):return hashlib.sha256(p.read_bytes()).hexdigest()

REPO=find_repo()
ROOT=REPO/"MVP"/"SHACL_GENERATION_PIPELINE"/"evaluation"/"BEHAVIORAL_RDF_R13"
R13=REPO/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
index=json.loads((R13/"requirement_term_index.json").read_text())
all_complete={r for r,c in index["dependencyContracts"].items() if r.startswith("IMO26-") and c.get("status")=="COMPLETE"}
all_req=[];all_case=[];all_path=[];overall=True

print("IMO 2026 Supplement systematic benchmark integrity A-B")
for batch in "ab":
    mp=ROOT/"manifests"/f"imo26_batch_{batch}_manifest.jsonl"
    lp=ROOT/"locks"/f"imo26_batch_{batch}_fixture_lock.json"
    if not mp.exists() or not lp.exists():
        print(f"Batch {batch.upper()}: MISSING manifest/lock");overall=False;continue
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]
    lock=json.loads(lp.read_text());reqs=sorted({x["requirement_id"] for x in rows})
    hashes=naming=provenance=counts=True
    er,ec=EXPECTED_BATCH_COUNTS[batch]
    if len(reqs)!=er or len(rows)!=ec:counts=False;overall=False
    if len(reqs)!=lock.get("requirement_count") or len(rows)!=lock.get("case_count") or sorted(lock.get("requirements",[]))!=reqs:
        counts=False;overall=False
    for rel,h in lock.get("frozen_files",{}).items():
        p=ROOT/rel
        if not p.exists() or sha256(p)!=h:hashes=False;overall=False;print("  hash mismatch:",rel)
    for row in rows:
        req=row.get("requirement_id","");cid=row.get("case_id","");rp=row.get("rdf_path","")
        if not re.fullmatch(r"IMO26-\d{3}",req) or not cid.startswith(req+"-") or rp!=f"rdf/IMO26/{req}/{cid}.ttl":
            naming=False;overall=False;print("  naming/path mismatch:",req,cid,rp)
        if row.get("source_id")!=EXPECTED_SOURCE or not row.get("source_clause") or row.get("verification_mode")!="DIRECT_STATIC" or row.get("generated_shacl_inspected") is not False:
            provenance=False;overall=False;print("  provenance mismatch:",cid)
        if req not in all_complete:provenance=False;overall=False;print("  requirement not frozen COMPLETE:",req)
    all_req+=reqs;all_case += [x["case_id"] for x in rows];all_path += [x["rdf_path"] for x in rows]
    print(f"Batch {batch.upper()}: {len(reqs):2d} requirements / {len(rows):3d} cases / hashes {'PASS' if hashes else 'FAIL'} / naming {'PASS' if naming else 'FAIL'} / provenance {'PASS' if provenance else 'FAIL'} / counts {'PASS' if counts else 'FAIL'}")

req_disjoint=len(all_req)==len(set(all_req))
case_unique=len(all_case)==len(set(all_case));path_unique=len(all_path)==len(set(all_path))
covered=set(all_req);coverage=covered==all_complete
totals=len(covered)==15 and len(all_case)==127
overall=overall and req_disjoint and case_unique and path_unique and coverage and totals

# Pilot 02 must remain byte-identical, especially its IMO26-007 and IMO26-011 fixtures/specs.
pilot_ok=True
pilot_path=ROOT/"locks"/"pilot_02_fixture_lock.json"
if pilot_path.exists():
    pilot=json.loads(pilot_path.read_text())
    for rel,h in pilot.get("hashes",{}).items():
        p=ROOT/rel
        if not p.exists() or sha256(p)!=h:
            pilot_ok=False;overall=False;print("Pilot 02 hash mismatch:",rel)
else:
    pilot_ok=False;overall=False;print("Pilot 02 lock missing")

# Systematic cases must not reuse Pilot 02 case IDs or paths.
pilot_manifest=ROOT/"manifests"/"pilot_02_manifest.jsonl"
pilot_sep=True
if pilot_manifest.exists():
    prow=[json.loads(x) for x in pilot_manifest.read_text().splitlines() if x.strip()]
    pcases={x["case_id"] for x in prow};ppaths={x["rdf_path"] for x in prow}
    if pcases.intersection(all_case) or ppaths.intersection(all_path):pilot_sep=False;overall=False
else:
    pilot_sep=False;overall=False

print(f"Unique systematic IMO26 requirements: {len(covered)}")
print(f"Systematic IMO26 RDF cases: {len(all_case)}")
print("R13 IMO26 COMPLETE coverage: "+(f"PASS ({len(covered)}/{len(all_complete)})" if coverage else f"FAIL ({len(covered)}/{len(all_complete)})"))
if not coverage:
    print("Missing COMPLETE requirements:",", ".join(sorted(all_complete-covered)))
    print("Unexpected requirements:",", ".join(sorted(covered-all_complete)))
print("Expected final IMO26 totals (15 requirements / 127 cases): "+("PASS" if totals else "FAIL"))
print("Cross-batch requirement disjointness: "+("PASS" if req_disjoint else "FAIL"))
print("Cross-batch case/path uniqueness: "+("PASS" if case_unique and path_unique else "FAIL"))
print("Pilot 02 frozen hashes: "+("PASS" if pilot_ok else "FAIL"))
print("Pilot 02 / systematic IMO26 physical separation: "+("PASS" if pilot_sep else "FAIL"))
print("Overall IMO26 integrity status: "+("PASS" if overall else "FAIL"))
raise SystemExit(0 if overall else 1)
