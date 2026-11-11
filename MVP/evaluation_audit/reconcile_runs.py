"""Read-only reconciliation of completed audit runs; no evaluator is invoked."""
import json
from pathlib import Path
import audit

def reconcile():
    chosen=audit.HERE/'outputs/20261108T124921Z'
    earlier=audit.HERE/'outputs/20261108T113918056821Z'
    details=[]
    def baseline_projection(p):
        return [{k:v for k,v in r.items() if k not in {'original_report','corrected_report'}} for r in audit.read(p/'baseline_results.json')]
    def strict_projection(p):
        keys=['condition','case_id','requirement_id','arm','original_eligible','status','diagnostic_observation','fixture_oracle_negative','fixture_oracle_repaired']
        return [{**{k:r.get(k) for k in keys},**{k:r[k]['conforms'] for k in ['negative','repaired'] if k in r}} for r in audit.read(p/'strict_results.json')]
    assert baseline_projection(chosen)==baseline_projection(earlier)
    assert strict_projection(chosen)==strict_projection(earlier)
    assert audit.read(chosen/'report.json')==audit.read(earlier/'report.json')
    assert audit.read(chosen/'environment.json')==audit.read(earlier/'environment.json')
    assert audit.read(chosen/'reviewed_failure_specs.json')==audit.read(earlier/'reviewed_failure_specs.json')
    assert audit.read(chosen/'baseline_differences.json')==[]
    for p in [earlier,chosen]:
        corrected={r['case_id']:r['corrected_sha256'] for r in audit.read(p/'fixture_corrections.json')}
        rows=audit.read(p/'retained_rows.json')
        assert len(rows)==4320
        for r in rows:
            if r['condition']=='NO_SEMANTIC':assert audit.sha(p/'corrected_benchmark'/r['rdf_path'])==corrected.get(r['case_id'],r['rdf_sha256'])
        details.append(dict(run=str(p),completed=True,baseline_sha256=audit.sha(p/'baseline_results.json'),strict_sha256=audit.sha(p/'strict_results.json'),full_phase_receipts=sorted({f.name.split('_')[0] for f in (p/'phase_receipts').glob('*.json')})))
    for path,h in audit.read(chosen/'source_hashes.json').items():assert audit.sha(path)==h,f'Changed historical input: {path}'
    audit.dump(chosen/'run_reconciliation.json',dict(authoritative_run=str(chosen),reason='User-selected completed rerun; complete phase receipts; 4320 baseline records and zero differences. Earlier run has identical verdicts and strict classifications. JSON hashes differ because evidence paths refer to different directories.',compared=details,incomplete_run='20261108T124705Z',incomplete_reason='No environment, baseline, specifications, strict results or report',baseline_validation_inputs_unchanged=True,baseline_reexecuted=False))
    authority_path=audit.HERE/'authoritative_run.json'
    authority=audit.read(authority_path) if authority_path.exists() else {}
    if authority.get('run_dir')!=str(chosen):authority={}
    authority.update(run_dir=str(chosen),reconciliation=str(chosen/'run_reconciliation.json'),baseline_sha256=audit.sha(chosen/'baseline_results.json'))
    audit.dump(authority_path,authority)
    print('Authoritative completed run:',chosen)
    return chosen

if __name__=='__main__':reconcile()
