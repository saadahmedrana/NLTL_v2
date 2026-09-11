from pathlib import Path
import hashlib, json, re

def find_repo():
    for c in [Path.cwd(), Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents):
        if (c/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13').exists(): return c.resolve()
    raise RuntimeError('Could not locate NLTL_v2 repository root')
REPO=find_repo(); ROOT=REPO/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'; R13=REPO/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'; EXPECTED_SOURCE='SRC-IMO-MSC385-94'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
index=json.loads((R13/'requirement_term_index.json').read_text()); all_complete={k for k,v in index['dependencyContracts'].items() if k.startswith('IMO-') and v.get('status')=='COMPLETE'}
all_req=[]; all_case=[]; all_path=[]; overall=True
print('IMO Polar Code systematic benchmark integrity A-J')
for batch in 'abcdefghij':
    mp=ROOT/'manifests'/f'imo_batch_{batch}_manifest.jsonl'; lp=ROOT/'locks'/f'imo_batch_{batch}_fixture_lock.json'
    if not mp.exists() or not lp.exists(): print(f'Batch {batch.upper()}: MISSING manifest/lock'); overall=False; continue
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]; lock=json.loads(lp.read_text()); reqs=sorted(set(r['requirement_id'] for r in rows)); hashes=naming=prov=True
    for rel,x in lock.get('frozen_files',{}).items():
        p=ROOT/rel
        if not p.exists() or sha(p)!=x: hashes=False; overall=False; print('  hash mismatch:',rel)
    if len(reqs)!=lock.get('requirement_count') or len(rows)!=lock.get('case_count') or sorted(lock.get('requirements',[]))!=reqs: overall=False
    for r in rows:
        req=r.get('requirement_id',''); cid=r.get('case_id',''); path=r.get('rdf_path','')
        if not re.fullmatch(r'IMO-\d{3}',req) or not cid.startswith(req+'-') or path!=f'rdf/IMO/{req}/{cid}.ttl': naming=False; overall=False; print('  naming/path mismatch:',req,cid,path)
        if r.get('source_id')!=EXPECTED_SOURCE or not r.get('source_clause') or r.get('generated_shacl_inspected') is not False: prov=False; overall=False; print('  provenance mismatch:',cid)
        if req not in all_complete: prov=False; overall=False; print('  requirement is not frozen COMPLETE:',req)
    all_req+=reqs; all_case += [r['case_id'] for r in rows]; all_path += [r['rdf_path'] for r in rows]
    print(f"Batch {batch.upper()}: {len(reqs):2d} requirements / {len(rows):3d} cases / hashes {'PASS' if hashes else 'FAIL'} / naming {'PASS' if naming else 'FAIL'} / provenance {'PASS' if prov else 'FAIL'}")
req_disjoint=len(set(all_req))==len(all_req); case_unique=len(set(all_case))==len(all_case); path_unique=len(set(all_path))==len(all_path); overall=overall and req_disjoint and case_unique and path_unique
covered=set(all_req)
print(f'Unique systematic IMO requirements: {len(covered)}'); print(f'Systematic IMO RDF cases: {len(all_case)}'); print(f'R13 IMO COMPLETE coverage: {len(covered)}/{len(all_complete)}'); print('Cross-batch requirement disjointness: '+('PASS' if req_disjoint else 'FAIL')); print('Cross-batch case/path uniqueness: '+('PASS' if case_unique and path_unique else 'FAIL')); print('IMO naming/provenance discipline: '+('PASS' if overall else 'FAIL')); print('Overall IMO integrity status: '+('PASS' if overall else 'FAIL')); raise SystemExit(0 if overall else 1)
