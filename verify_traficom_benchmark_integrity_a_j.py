from pathlib import Path
import hashlib, json, re

def find_repo():
    for c in [Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents):
        if (c/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13').exists(): return c.resolve()
    raise RuntimeError('Could not locate NLTL_v2 repository root')
REPO=find_repo(); ROOT=REPO/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'
EXPECTED_SOURCE='SRC-TRAFICOM-2021'
EXPECTED_COMPLETE=99
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
all_req=[];all_case=[];all_path=[];overall=True
print('TRAFICOM systematic benchmark integrity A-J')
for batch in 'abcdefghij':
    mp=ROOT/'manifests'/f'traficom_batch_{batch}_manifest.jsonl';lp=ROOT/'locks'/f'traficom_batch_{batch}_fixture_lock.json'
    if not mp.exists() or not lp.exists():
        print(f'Batch {batch.upper()}: MISSING manifest/lock');overall=False;continue
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()];lock=json.loads(lp.read_text());reqs=sorted(set(r['requirement_id'] for r in rows))
    hashes=naming=prov=True
    for rel,x in lock.get('frozen_files',{}).items():
        p=ROOT/rel
        if not p.exists() or sha(p)!=x:hashes=False;overall=False;print('  hash mismatch:',rel)
    if len(reqs)!=lock.get('requirement_count') or len(rows)!=lock.get('case_count') or sorted(lock.get('requirements',[]))!=reqs:overall=False
    for r in rows:
        req=r.get('requirement_id','');cid=r.get('case_id','');path=r.get('rdf_path','')
        if not re.fullmatch(r'TRF-\d{3}',req) or not cid.startswith(req+'-') or path!=f'rdf/TRF/{req}/{cid}.ttl':
            naming=False;overall=False;print('  naming/path mismatch:',req,cid,path)
        if r.get('source_id')!=EXPECTED_SOURCE or not r.get('source_clause') or r.get('generated_shacl_inspected') is not False:
            prov=False;overall=False;print('  provenance mismatch:',cid)
    all_req+=reqs;all_case += [r['case_id'] for r in rows];all_path += [r['rdf_path'] for r in rows]
    print(f"Batch {batch.upper()}: {len(reqs):2d} requirements / {len(rows):3d} cases / hashes {'PASS' if hashes else 'FAIL'} / naming {'PASS' if naming else 'FAIL'} / provenance {'PASS' if prov else 'FAIL'}")
req_disjoint=len(set(all_req))==len(all_req);case_unique=len(set(all_case))==len(all_case);path_unique=len(set(all_path))==len(all_path)
complete=len(set(all_req))==EXPECTED_COMPLETE
overall=overall and req_disjoint and case_unique and path_unique and complete
print(f'Unique systematic TRAFICOM requirements: {len(set(all_req))}')
print(f'Systematic TRAFICOM RDF cases: {len(all_case)}')
print('R13 TRAFICOM COMPLETE coverage: '+('PASS' if complete else 'FAIL')+f' ({len(set(all_req))}/{EXPECTED_COMPLETE})')
print('Cross-batch requirement disjointness: '+('PASS' if req_disjoint else 'FAIL'))
print('Cross-batch case/path uniqueness: '+('PASS' if case_unique and path_unique else 'FAIL'))
print('TRAFICOM naming/provenance discipline: '+('PASS' if overall else 'FAIL'))
print('Overall TRAFICOM integrity status: '+('PASS' if overall else 'FAIL'))
raise SystemExit(0 if overall else 1)
