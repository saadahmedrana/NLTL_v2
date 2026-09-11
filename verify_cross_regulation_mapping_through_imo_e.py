from pathlib import Path
import json, re

def find_repo():
    for c in [Path.cwd(), Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents):
        if (c/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13').exists():
            return c.resolve()
    raise RuntimeError('Could not locate NLTL_v2 repository root')

ROOT=find_repo()/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'
families=[
    ('IACS I2','i2_batch_','abcdefghi','I2-','rdf/I2/','SRC-IACS-I2-R4'),
    ('TRAFICOM','traficom_batch_','abcdefghij','TRF-','rdf/TRF/','SRC-TRAFICOM-2021'),
    ('IMO','imo_batch_','abcde','IMO-','rdf/IMO/','SRC-IMO-MSC385-94'),
]
reqs=[]; cases=[]; paths=[]; overall=True
print('Cross-regulation systematic mapping integrity through IMO Batch E')
for name,prefix,batches,reqprefix,pathprefix,source in families:
    fr=fc=0; fam_ok=True
    for b in batches:
        mp=ROOT/'manifests'/f'{prefix}{b}_manifest.jsonl'
        if not mp.exists():
            print(name,b.upper(),'manifest missing'); overall=False; fam_ok=False; continue
        rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]
        for r in rows:
            req=r.get('requirement_id',''); cid=r.get('case_id',''); path=r.get('rdf_path','')
            if not req.startswith(reqprefix) or not cid.startswith(req+'-') or path!=f'{pathprefix}{req}/{cid}.ttl' or r.get('source_id')!=source:
                overall=False; fam_ok=False; print('family mismatch:',r)
        rs=set(r['requirement_id'] for r in rows)
        fr+=len(rs); fc+=len(rows); reqs.extend(rs); cases.extend(r['case_id'] for r in rows); paths.extend(r['rdf_path'] for r in rows)
    print(f"{name}: {fr} requirements / {fc} cases / family mapping {'PASS' if fam_ok else 'FAIL'}")
unique_req=len(set(reqs))==len(reqs); unique_case=len(set(cases))==len(cases); unique_path=len(set(paths))==len(paths)
overall=overall and unique_req and unique_case and unique_path
print('Cross-regulation requirement-ID uniqueness: '+('PASS' if unique_req else 'FAIL'))
print('Cross-regulation case-ID uniqueness: '+('PASS' if unique_case else 'FAIL'))
print('Cross-regulation RDF-path uniqueness: '+('PASS' if unique_path else 'FAIL'))
print(f'I2 + TRAFICOM + IMO systematic requirements represented: {len(set(reqs))}')
print(f'I2 + TRAFICOM + IMO systematic RDF cases represented: {len(cases)}')
print('Overall cross-regulation mapping status: '+('PASS' if overall else 'FAIL'))
raise SystemExit(0 if overall else 1)
