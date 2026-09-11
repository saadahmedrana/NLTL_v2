from pathlib import Path
import hashlib,json,re

EXPECTED={
 "IACS I2":("i2","I2","SRC-IACS-I2-R4","abcdefghi",45,499),
 "TRAFICOM":("traficom","TRF","SRC-TRAFICOM-2021","abcdefghij",99,755),
 "IMO":("imo","IMO","SRC-IMO-MSC385-94","abcdefghijklmn",109,805),
 "IMO26":("imo26","IMO26","SRC-IMO26-SUPPLEMENT","ab",15,127),
}
EXPECTED_TOTAL=(268,2186)

def find_repo():
    candidates=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    for c in candidates:
        root=c/"MVP"/"SHACL_GENERATION_PIPELINE"/"evaluation"/"BEHAVIORAL_RDF_R13"
        r13=c/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
        if root.exists() and (r13/"requirement_term_index.json").exists():return c.resolve()
    raise RuntimeError("Could not locate NLTL_v2 repository root")
def sha256(p):return hashlib.sha256(p.read_bytes()).hexdigest()

REPO=find_repo();ROOT=REPO/"MVP"/"SHACL_GENERATION_PIPELINE"/"evaluation"/"BEHAVIORAL_RDF_R13"
R13=REPO/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
index=json.loads((R13/"requirement_term_index.json").read_text())
expected_complete={r for r,c in index["dependencyContracts"].items() if c.get("status")=="COMPLETE" and (r.startswith("I2-") or r.startswith("TRF-") or r.startswith("IMO-") or r.startswith("IMO26-"))}

all_req=[];all_case=[];all_path=[];ok=True
print("FINAL systematic benchmark integrity - all source families")
for label,(prefix,folder,source,batches,exp_req,exp_case) in EXPECTED.items():
    reqs=[];cases=[];paths=[];family_ok=True
    for b in batches:
        mp=ROOT/"manifests"/f"{prefix}_batch_{b}_manifest.jsonl"
        lp=ROOT/"locks"/f"{prefix}_batch_{b}_fixture_lock.json"
        if not mp.exists() or not lp.exists():
            print(label,"missing",mp.name if not mp.exists() else lp.name);family_ok=False;ok=False;continue
        rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]
        lock=json.loads(lp.read_text())
        for rel,h in lock.get("frozen_files",{}).items():
            p=ROOT/rel
            if not p.exists() or sha256(p)!=h:
                family_ok=False;ok=False;print("  hash mismatch:",label,rel)
        for row in rows:
            req=row.get("requirement_id","");cid=row.get("case_id","");rp=row.get("rdf_path","")
            if not req.startswith(folder+"-") or not cid.startswith(req+"-") or rp!=f"rdf/{folder}/{req}/{cid}.ttl" or row.get("source_id")!=source or ("generated_shacl_inspected" in row and row.get("generated_shacl_inspected") is not False):
                family_ok=False;ok=False;print("  family mapping mismatch:",label,req,cid,rp)
            reqs.append(req);cases.append(cid);paths.append(rp)
    u=set(reqs)
    count_ok=len(u)==exp_req and len(cases)==exp_case
    if not count_ok:family_ok=False;ok=False
    print(f"{label}: {len(u)} requirements / {len(cases)} cases / frozen mapping {'PASS' if family_ok else 'FAIL'}")
    if not count_ok:print(f"  expected {exp_req} requirements / {exp_case} cases")
    all_req+=list(u);all_case+=cases;all_path+=paths

req_unique=len(all_req)==len(set(all_req));case_unique=len(all_case)==len(set(all_case));path_unique=len(all_path)==len(set(all_path))
coverage=set(all_req)==expected_complete
totals=len(set(all_req))==EXPECTED_TOTAL[0] and len(all_case)==EXPECTED_TOTAL[1]

pilot_ok=True
pilot_lock=ROOT/"locks"/"pilot_02_fixture_lock.json"
if not pilot_lock.exists():pilot_ok=False
else:
    p=json.loads(pilot_lock.read_text())
    for rel,h in p.get("hashes",{}).items():
        f=ROOT/rel
        if not f.exists() or sha256(f)!=h:pilot_ok=False;print("Pilot 02 hash mismatch:",rel)
ok=ok and req_unique and case_unique and path_unique and coverage and totals and pilot_ok

print("Cross-regulation requirement-ID uniqueness: "+("PASS" if req_unique else "FAIL"))
print("Cross-regulation case-ID uniqueness: "+("PASS" if case_unique else "FAIL"))
print("Cross-regulation RDF-path uniqueness: "+("PASS" if path_unique else "FAIL"))
print("R13 COMPLETE systematic coverage: "+(f"PASS ({len(set(all_req))}/{len(expected_complete)})" if coverage else f"FAIL ({len(set(all_req))}/{len(expected_complete)})"))
if not coverage:
    print("Missing COMPLETE requirements:",", ".join(sorted(expected_complete-set(all_req))))
    print("Unexpected requirements:",", ".join(sorted(set(all_req)-expected_complete)))
print(f"Systematic requirements represented: {len(set(all_req))}")
print(f"Systematic RDF cases represented: {len(all_case)}")
print("Expected final total (268 requirements / 2186 cases): "+("PASS" if totals else "FAIL"))
print("Pilot 02 frozen hashes: "+("PASS" if pilot_ok else "FAIL"))
print("OVERALL FINAL BENCHMARK INTEGRITY: "+("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
