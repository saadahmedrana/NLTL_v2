from pathlib import Path
import json, re, hashlib

def find_repo():
    for c in [Path.cwd(), Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents):
        if (c/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13').exists(): return c.resolve()
    raise RuntimeError('Could not locate repo')
R=find_repo()/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'
families=[('IACS I2','i2','I2','SRC-IACS-I2-R4','abcdefghi'),('TRAFICOM','traficom','TRF','SRC-TRAFICOM-2021','abcdefghij'),('IMO','imo','IMO','SRC-IMO-MSC385-94','abcdefghij')]
all_req=[]; all_case=[]; all_path=[]; ok=True
print('Cross-regulation systematic mapping integrity through IMO Batch J')
for label,prefix,folder,source,batches in families:
    reqs=[];cases=[];paths=[]; fam=True
    for b in batches:
        mp=R/'manifests'/f'{prefix}_batch_{b}_manifest.jsonl'
        if not mp.exists(): print(label,'missing',mp.name); fam=False; ok=False; continue
        for line in mp.read_text().splitlines():
            if not line.strip(): continue
            x=json.loads(line); req=x['requirement_id']; cid=x['case_id']; path=x['rdf_path']
            if not req.startswith(folder+'-') or not cid.startswith(req+'-') or path!=f'rdf/{folder}/{req}/{cid}.ttl' or x.get('source_id')!=source: fam=False; ok=False
            reqs.append(req);cases.append(cid);paths.append(path)
    u=set(reqs); print(f'{label}: {len(u)} requirements / {len(cases)} cases / family mapping '+('PASS' if fam else 'FAIL'))
    all_req+=list(u);all_case+=cases;all_path+=paths
rq=len(all_req)==len(set(all_req)); cq=len(all_case)==len(set(all_case)); pq=len(all_path)==len(set(all_path)); ok=ok and rq and cq and pq
print('Cross-regulation requirement-ID uniqueness: '+('PASS' if rq else 'FAIL')); print('Cross-regulation case-ID uniqueness: '+('PASS' if cq else 'FAIL')); print('Cross-regulation RDF-path uniqueness: '+('PASS' if pq else 'FAIL')); print(f'I2 + TRAFICOM + IMO systematic requirements represented: {len(set(all_req))}'); print(f'I2 + TRAFICOM + IMO systematic RDF cases represented: {len(all_case)}'); print('Overall cross-regulation mapping status: '+('PASS' if ok else 'FAIL')); raise SystemExit(0 if ok else 1)
