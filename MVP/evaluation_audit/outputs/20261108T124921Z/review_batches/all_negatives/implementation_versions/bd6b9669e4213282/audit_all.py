#!/usr/bin/env python3
"""Resumable all-retained-negative audit. Never invokes generation or an API."""
import argparse
import json
import sys
from datetime import datetime,timezone
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'full_audit'))
from common import audit, BASE, OUT, OLD, atomic

def checkpoint(record):
    path=OUT/'records'/f'{record["case_id"]}.json'
    if path.exists() and audit.read(path)!=record:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        atomic(OUT/'record_history'/record['case_id']/f'{stamp}.json',audit.read(path))
    atomic(path,record)

def initialize():
    OUT.mkdir(parents=True,exist_ok=True)
    env=audit.read(BASE/'environment.json')
    assert (audit.platform.python_version(),audit.rdflib.__version__,audit.pyshacl.__version__)==(env['python'],env['rdflib'],env['pyshacl']),'Use the recorded validation environment'
    assert env['options']==audit.OPTIONS and env['ontology_sha256']==audit.sha(audit.ONTOLOGY),'Validation inputs changed'
    authority=audit.read(audit.HERE/'authoritative_run.json')
    assert Path(authority['run_dir'])==BASE
    assert audit.sha(BASE/'baseline_results.json')==authority['baseline_sha256']
    for p,h in audit.read(BASE/'source_hashes.json').items():assert audit.sha(p)==h,f'Changed historical input: {p}'
    rows=audit.read(BASE/'retained_rows.json');neg={r['case_id']:r for r in rows if r['condition']=='NO_SEMANTIC' and r['expected']=='FAIL'}
    corrected_hashes={r['case_id']:r['corrected_sha256'] for r in audit.read(BASE/'fixture_corrections.json')}
    fixture_manifest={}
    for row in rows:
        if row['condition']!='NO_SEMANTIC':continue
        path=BASE/'corrected_benchmark'/row['rdf_path']
        expected=corrected_hashes.get(row['case_id'],row['rdf_sha256'])
        assert audit.sha(path)==expected,f'Corrected fixture changed: {row["case_id"]}; affected ordinary results must be revalidated before reuse'
        fixture_manifest[str(path)]=expected
    atomic(OUT/'reused_corrected_fixture_sha256.json',fixture_manifest)
    assert len(neg)==1205
    prior=audit.expected_specs(audit.HERE/'reviewed_failure_specs_batch50.json');assert len(prior)==50
    if not (OUT/'immutable_inputs.json').exists():
        immutable={str(BASE/'baseline_results.json'):audit.sha(BASE/'baseline_results.json'),str(OLD/'strict_results.json'):audit.sha(OLD/'strict_results.json'),str(OLD/'reviewed_failure_specs.json'):audit.sha(OLD/'reviewed_failure_specs.json')}
        atomic(OUT/'immutable_inputs.json',immutable)
    for p,h in audit.read(OUT/'immutable_inputs.json').items():assert audit.sha(p)==h,f'Preserved result changed: {p}'
    existing_results=audit.read(OLD/'strict_results.json')
    for cid,row in neg.items():
        p=OUT/'records'/f'{cid}.json'
        if p.exists():continue
        record=dict(case_id=cid,requirement_id=row['requirement_id'],source_clause=row['source_clause'],intended_rationale=row['source_oracle_rationale'],expected='FAIL',state='PENDING',blockers=[])
        if cid in prior:
            record.update(state='COMPLETED_PRIOR50',specification=str(OLD/'reviewed_failure_specs.json'),workflows={r['condition']:r for r in existing_results if r['case_id']==cid and r['arm']=='corrected_fixtures'})
        elif cid in audit.EXCLUSIONS:record.update(state='EXCLUDED',exclusion_reason=audit.EXCLUSIONS[cid],exclusion_evidence=str(BASE/'exclusions.csv'))
        atomic(p,record)
    atomic(OUT/'cohort.json',dict(retained_negatives=1205,prior_reviewed=50,previously_excluded=1,remaining_requested=1154,authoritative_run=str(BASE),baseline_reexecuted=False,new_llm_api_calls=0))
    return rows,neg

def prepare_job(row):
    from prepare import prepare_case
    try:
        record=prepare_case(row);record['state']='BLOCKED' if record['blockers'] else 'PAIR_VERIFIED';return record
    except Exception as exc:
        return dict(case_id=row['case_id'],requirement_id=row['requirement_id'],source_clause=row['source_clause'],intended_rationale=row['source_oracle_rationale'],expected='FAIL',state='BLOCKED',blockers=[dict(code='PREPARATION_ERROR',detail=f'{type(exc).__name__}: {exc}',fixture=row['fixture_path'],source_context=row['requirement_context_path'])])

def prepare_all(neg,workers,retry=False):
    selected=[]
    for cid,row in neg.items():
        rec=audit.read(OUT/'records'/f'{cid}.json')
        if rec['state']=='PENDING' or (retry and rec['state'] in ['BLOCKED','PAIR_VERIFIED']):selected.append(row)
    print('Preparation queue:',len(selected),flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(prepare_job,r):r['case_id'] for r in selected}
        for i,f in enumerate(as_completed(futures),1):
            rec=f.result();checkpoint(rec)
            if i%25==0 or i==len(futures):print(f'Preparation checkpoint {i}/{len(futures)}',flush=True)

def evaluate_all(rows,workers):
    from evaluate import evaluate_case
    index={(r['condition'],r['case_id']):r for r in rows}
    queue=[]
    for p in sorted((OUT/'records').glob('*.json')):
        rec=audit.read(p)
        if rec['state']=='PAIR_VERIFIED':queue.append((rec,[index[w,rec['case_id']] for w in audit.WORKFLOWS]))
    print('Evaluation queue:',len(queue),flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(evaluate_case,*job):job[0]['case_id'] for job in queue}
        for i,f in enumerate(as_completed(futures),1):
            rec=f.result();checkpoint(rec)
            if i%10==0 or i==len(futures):print(f'Evaluation checkpoint {i}/{len(futures)}',flush=True)

def reclassify():
    """Recheck source/schema gates and reason matching, reusing execution caches."""
    from prepare import schema_issues
    from rdflib import Graph
    for path in sorted((OUT/'records').glob('*.json')):
        r=audit.read(path)
        if not r.get('selected_repair'):continue
        issues=schema_issues(Graph().parse(r['repaired_fixture']))
        if issues:
            r['superseded_workflows']=r.pop('workflows',r.get('superseded_workflows',{}));r['state']='BLOCKED'
            r['independent_repaired_valid']=False;r['selected_repair']['repaired_schema_issues']=issues
            r['blockers']=[dict(code='REPAIRED_SCHEMA_RECHECK_FAILED',detail='Independent range/domain/type/unit checking found an unresolved fixture/contract discrepancy. No shape-dependent exclusion or correction is applied.',issues=issues)]
        else:
            r['blockers']=[];r['state']='PAIR_VERIFIED';r['independent_repaired_valid']=True;r['selected_repair']['repaired_schema_issues']=[]
        checkpoint(r)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['prepare','evaluate','reclassify','report','all'],default='all');p.add_argument('--workers',type=int,default=4);p.add_argument('--retry-blocked',action='store_true');args=p.parse_args()
    rows,neg=initialize()
    if args.phase in ['prepare','all']:prepare_all(neg,args.workers,args.retry_blocked)
    if args.phase=='reclassify':reclassify()
    if args.phase in ['evaluate','reclassify','all']:evaluate_all(rows,args.workers)
    if args.phase in ['report','all']:
        from report_all import build_report
        build_report(rows,neg)
if __name__=='__main__':main()
