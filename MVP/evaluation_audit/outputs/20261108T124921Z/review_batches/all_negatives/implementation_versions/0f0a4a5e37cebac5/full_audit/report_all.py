"""Report all terminal case records, with common denominators and immutable history."""
import csv
import hashlib
import json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from common import audit,BASE,OUT,OLD,atomic

TERMINAL={'COMPLETED','COMPLETED_PRIOR50','BLOCKED','EXCLUDED'}
STATUSES=['STRICT_INTENDED_MATCH','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','MISSED_INTENDED_DEFECT','NO_VERDICT','UNRESOLVED_REASON']

def records():return [audit.read(p) for p in sorted((OUT/'records').glob('*.json'))]

def checks(rs):
    assert len(rs)==1205 and len({r['case_id'] for r in rs})==1205
    assert all(r['state'] in TERMINAL for r in rs),'Nonterminal cases remain; resume evaluate/prepare first'
    assert sum(r['state']=='COMPLETED_PRIOR50' for r in rs)==50
    assert {r['case_id'] for r in rs if r['state']=='EXCLUDED'}==set(audit.EXCLUSIONS)
    for p,h in audit.read(OUT/'immutable_inputs.json').items():assert audit.sha(p)==h
    for r in rs:
        assert r['state']!='BLOCKED' or r.get('blockers'),r['case_id']
        if r.get('workflows'):assert set(r['workflows'])==set(audit.WORKFLOWS)
        for w,v in r.get('workflows',{}).items():
            assert v['status'] in STATUSES
            if not v['original_eligible']:assert v['status']=='NO_VERDICT'
            if v['status']=='STRICT_INTENDED_MATCH':
                assert v['negative']['conforms'] is False and v['repaired']['conforms'] is True
                if r['state']!='COMPLETED_PRIOR50':
                    meaning=v['violation_reason_review'];assert meaning['intended'] and not meaning['unrelated'] and not meaning['unresolved']
        if r.get('selected_repair') and r.get('workflows'):
            assert r['selected_repair']['repaired_original_oracle'] is True
            assert not r['selected_repair']['repaired_schema_issues']
            assert r['independent_repaired_valid'] is True
    return dict(all_retained_negatives_terminal=True,common_reviewed_case_ids=True,identical_exclusion_ids=True,prior50_preserved=True,baseline_preserved=True,no_original_no_verdict_credited=True)

def write_csv(name,rows,fields=None):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})

def build_report(rows,neg):
    rs=records();verified_checks=checks(rs);states=Counter(r['state'] for r in rs)
    with (OLD/'failure_causes.csv').open() as f:
        old_causes={(r['condition'],r['case_id']):r for r in csv.DictReader(f) if r['arm']=='corrected_fixtures'}
    paired=[r for r in rs if r.get('workflows')];completed=[r for r in paired if r['state'] in ['COMPLETED','COMPLETED_PRIOR50']]
    strict_rows=[];summary=[];causes=[];blockers=[];examples={};attempts=[];specs=[]
    for r in rs:
        for b in r.get('blockers',[]):blockers.append(dict(b,case_id=r['case_id'],requirement_id=r['requirement_id'],source_clause=r.get('source_clause'),rationale=r.get('intended_rationale'),record=str(OUT/'records'/f'{r["case_id"]}.json')))
        for i,a in enumerate(r.get('candidate_attempts',[])):attempts.append(dict(case_id=r['case_id'],candidate=i,**a))
        if r.get('selected_repair') and r.get('workflows'):specs.append({k:v for k,v in r.items() if k!='workflows'})
        for w,v in r.get('workflows',{}).items():
            flat=dict(condition=w,workflow=v['workflow'],case_id=r['case_id'],requirement_id=r['requirement_id'],case_state=r['state'],status=v['status'],original_eligible=v['original_eligible'],negative_conforms=(v.get('negative') or {}).get('conforms'),repaired_conforms=(v.get('repaired') or {}).get('conforms'),negative_report=(v.get('negative') or {}).get('report_path'),repaired_report=(v.get('repaired') or {}).get('report_path'),likely_cause=v.get('likely_cause'),record=str(OUT/'records'/f'{r["case_id"]}.json'))
            strict_rows.append(flat)
            examples.setdefault(v['status'],[])
            if len(examples[v['status']])<4:examples[v['status']].append(flat)
            cause=v.get('likely_cause') or old_causes.get((w,r['case_id']))
            if cause:flat['likely_cause']=cause
            if cause and v['status'] not in ['STRICT_INTENDED_MATCH','NO_VERDICT']:causes.append(dict(cause,case_id=r['case_id'],requirement_id=r['requirement_id'],workflow=v['workflow'],status=v['status']))
    for scope,subset in [('all_source_verified_pairs_including_semantic_blockers',paired),('fully_classified_common_subset',completed)]:
        ids=[r['case_id'] for r in subset]
        for w in audit.WORKFLOWS:
            count=Counter(r['workflows'][w]['status'] for r in subset)
            for status in STATUSES:summary.append(dict(scope=scope,workflow=audit.WORKFLOWS[w],status=status,count=count[status],denominator=len(subset),percentage=100*count[status]/len(subset) if subset else None,requirements=len({r['requirement_id'] for r in subset})))
        atomic(OUT/f'{scope}_case_ids.json',ids)
    write_csv('strict_results.csv',strict_rows);atomic(OUT/'strict_results.json',strict_rows)
    write_csv('strict_summary.csv',summary);write_csv('unresolved_blockers.csv',blockers);write_csv('repair_candidate_review.csv',attempts);write_csv('strict_mismatch_causes.csv',causes)
    atomic(OUT/'reviewed_failure_specs_additional.json',specs)
    atomic(OUT/'reviewed_failure_specs_index.json',dict(preserved_prior50=str(OLD/'reviewed_failure_specs.json'),additional=str(OUT/'reviewed_failure_specs_additional.json'),note='PAIR_VERIFIED specifications have independent source/schema repair evidence; semantic blockers remain UNRESOLVED and receive no strict credit.'))
    # Ordinary cohort is kept in full, including every valid blocked case. No
    # fixture inputs changed beyond the authoritative baseline corrections.
    ordinary=[]
    for prefix in ['original','corrected_before_exclusions','corrected_after_exclusions']:
        for suffix in ['figure6.csv','ordinary_verdicts.csv','per_requirement.csv']:
            p=BASE/f'{prefix}_{suffix}'
            if p.exists():
                (OUT/p.name).write_bytes(p.read_bytes());ordinary.append(dict(path=str(p),sha256=audit.sha(p),copied_to=str(OUT/p.name)))
    atomic(OUT/'ordinary_reuse_receipt.json',dict(reason='No additional fixture corrections were applied; all original/corrected ordinary results and Figure 6 denominators are reused byte-for-byte.',inputs=ordinary,baseline_reexecuted=False,positive_revalidation_required=False))
    atomic(OUT/'fixture_corrections_additional.json',[])
    for name in ['fixture_corrections.csv','fixture_corrections.json','exclusions.csv','exclusions_by_requirement.csv']:
        p=BASE/name
        if p.exists():(OUT/name).write_bytes(p.read_bytes())
    diagnostic=dict(new_transformations=[],new_diagnostic_validations=0,preserved_prior50=str(OLD/'diagnostic_results.csv'),preserved_baseline=str(BASE/'diagnostic_shape_repair_results.csv'),note='Diagnostic shape transformations remain separate and contribute no unchanged-shape credit.')
    atomic(OUT/'diagnostic_results.json',diagnostic)
    # Full original ledger, augmented without dropping positives, no-verdicts,
    # valid failures, blocked cases, or historical metadata.
    byid={r['case_id']:r for r in rs};ledger=[]
    with (BASE/'full_case_ledger.csv').open() as f:
        for row in csv.DictReader(f):
            r=byid.get(row['case_id']);row['all_negative_audit_state']=r['state'] if r else 'POSITIVE_NOT_IN_STRICT_AUDIT'
            row['prior_review_status']=row.get('review_status','')
            if r:row['review_status']='REVIEWED' if r['state'] in ['COMPLETED','COMPLETED_PRIOR50'] else 'BLOCKED' if r['state']=='BLOCKED' else 'INVALID_TEST_EXCLUDED'
            row['all_negative_audit_record']=str(OUT/'records'/f'{r["case_id"]}.json') if r else ''
            row['all_negative_audit_status']=(r or {}).get('workflows',{}).get(row['condition'],{}).get('status','UNRESOLVED_REASON' if r and r['state']=='BLOCKED' else 'INVALID_TEST_EXCLUDED' if r else '')
            row['all_negative_audit_blockers']=r.get('blockers',[]) if r else []
            ledger.append(row)
    assert len(ledger)==4320
    write_csv('full_case_ledger.csv',ledger)
    counts=dict(retained_negatives=1205,preserved_prior50=50,remaining_requested=1154,additional_fully_classified=states['COMPLETED'],fully_classified_total=len(completed),blocked=states['BLOCKED'],excluded=states['EXCLUDED'],source_verified_pairs=len(paired),source_verified_pairs_with_semantic_blockers=sum(r['state']=='BLOCKED' for r in paired),source_or_repair_blocked=sum(r['state']=='BLOCKED' and not r.get('workflows') for r in rs),distinct_requirements_all=len({r['requirement_id'] for r in rs}),distinct_requirements_fully_classified=len({r['requirement_id'] for r in completed}),distinct_requirements_source_verified_pairs=len({r['requirement_id'] for r in paired}))
    fault_groups=[]
    for (w,cause),n in Counter((r['workflow'],r['primary']) for r in causes).items():fault_groups.append(dict(workflow=w,cause=cause,count=n,requirements=sorted({r['requirement_id'] for r in causes if r['workflow']==w and r['primary']==cause})))
    prior=Counter((r['condition'],r['status']) for r in audit.read(OLD/'strict_results.json') if r['arm']=='corrected_fixtures')
    changes=[dict(workflow=audit.WORKFLOWS[w],status=s,previous50=prior[w,s],current_paired=sum(r['workflows'][w]['status']==s for r in paired),added=sum(r['workflows'][w]['status']==s for r in paired)-prior[w,s]) for w in audit.WORKFLOWS for s in STATUSES]
    write_csv('previous50_comparison.csv',changes);write_csv('fault_causes_by_requirement.csv',fault_groups)
    req_rows=[]
    for req in sorted({r['requirement_id'] for r in rs}):
        group=[r for r in rs if r['requirement_id']==req]
        req_rows.append(dict(requirement_id=req,negative_cases=len(group),states=dict(Counter(r['state'] for r in group)),blocker_codes=dict(Counter(b['code'] for r in group for b in r.get('blockers',[])))))
    write_csv('requirements_coverage.csv',req_rows)
    report=dict(counts=counts,states=dict(states),strict_summary=summary,blocker_codes=dict(Counter(b['code'] for b in blockers)),fault_causes=fault_groups,examples=examples,changes_from_previous50=changes,checks=verified_checks,ordinary_changed=False,new_corrections=0,new_exclusions=0,new_llm_api_calls=0,new_shape_generations=0,baseline_reexecuted=False,limitations=['Source-authored fixture oracles are independent of generated SHACL; their scope is the represented requirement plus canonical schema, not complete ship certification.','No strict accuracy estimate is made for the full benchmark. Unresolved cases are explicitly listed and valid tests stay in ordinary denominators.','Likely fault origins are left UNRESOLVED where reports do not distinguish context, generator and runtime causes.'])
    atomic(OUT/'report.json',report)
    lines=['# All retained negative tests: intended-failure audit','',f'Authoritative baseline: `{BASE.name}`. The original 50 specifications and results are unchanged. No new generation/API calls, baseline rerun, fixture corrections or exclusions.','',f"All **1,154 additional cases** have terminal records. Across the 1,205 retained negatives: **{len(completed)} fully classified**, **{states['BLOCKED']} blocked**, **{states['EXCLUDED']} excluded**. {counts['distinct_requirements_all']} distinct requirements were examined; fully classified cases cover {counts['distinct_requirements_fully_classified']} requirements.",'',f"There are **{len(paired)} source/schema-verified pairs** across {counts['distinct_requirements_source_verified_pairs']} requirements. {counts['source_verified_pairs_with_semantic_blockers']} of these still have an unresolved violation-semantics or execution blocker. The remaining {counts['source_or_repair_blocked']} blocked cases lack a verified source/repair pair.",'','## Unchanged generated shapes','',f'Common denominator: **{len(paired)} source-verified negative cases per workflow**, including original no-verdicts and unresolved semantic reviews. Unresolved receives no strict credit. These are reviewed-subset results, not full-benchmark strict accuracy.','', '| Workflow | Strict match | Unrelated/additional failure | Missed defect | No verdict | Unresolved |','|---|---:|---:|---:|---:|---:|']
    for w in audit.WORKFLOWS:
        cs=Counter(r['workflows'][w]['status'] for r in paired);lines.append('| '+audit.WORKFLOWS[w]+' | '+' | '.join(f'{cs[s]} ({cs[s]/len(paired):.1%})' for s in STATUSES)+' |')
    lines+=['',f'The fully classified common subset contains {len(completed)} cases for both workflows. Its separate counts and denominators are in `strict_summary.csv`; cases with a semantic blocker in either workflow remain visible above, including the other workflow’s completed result.','', '## Ordinary Figure 6','', 'Unchanged: no new fixture input was established that warrants a correction. After the existing identical TRF-002-F02 exclusion, each workflow retains **2,159 cases / 268 requirements**, including **955 expected PASS / 1,204 expected FAIL**. NLTL_v2 ordinary agreement is **1,634/2,159** (requirement mean **76.6965%**); Single-shot is **1,429/2,159** (requirement mean **68.8808%**). Ordinary results include all valid blocked tests. Original/corrected Figure 6 files are copied unchanged, with expected-class denominators.','', '## Causes and examples','']
    lines += [
        '- **Intended match:** NLTL_v2 I2-048-H-F003 lacks case-owned asBuiltPlateThickness. Adding only the source-builder thickness selector (17.5 mm) gives an independently valid fixture and full-shape PASS; the missing-field violation matches.',
        '- **Owner mismatch:** NLTL_v2 I2-023-F04 repairs only the misplaced selectedHullAreaFactor. The valid repair still fails because the shape requires yieldStrength on ship; the canonical fixture carries it on the structural member.',
        '- **Unit/runtime problem:** Single-shot TRF-080-F01 repairs only the incorrect multiplied cycle count. The valid counterfactual still rejects because the shape expects http://qudt.org/schema/qudt/UNITLESS while the contract uses http://qudt.org/vocab/unit/UNITLESS.',
        '- **Generated defect:** the preserved Single-shot I2-004-G-F02 audit shows an inverted displacement query rejecting the valid restored 12 kt maximum; NLTL_v2 IMO26-014-A-F01 accepts insufficient illumination through its daylight=false OR branch.',
        '- **Fixture/oracle defect:** the historical TRF-001 universal-provision omission remains corrected in the versioned benchmark. No new ambiguous source/schema discrepancy was silently repaired or excluded. IMO-097 rescue-boat versus ontology lifeboat range remains blocked.',
        '- **Unresolved meaning:** NLTL_v2 I2-004-G-F01 rejects the negative and accepts its repair, but the query’s maximum-displacement/tolerance semantics lack a new admissible-semantics review. Verdict change alone receives no strict credit.',
        '- **No verdict:** Single-shot IMO26-009 retains its historical malformed-Turtle no-verdict outcome; offline diagnostics never restore eligibility.',
        '',
    ]
    for group in fault_groups:lines.append(f"- {group['workflow']}: {group['cause']}: {group['count']} mismatch/unresolved records across {len(group['requirements'])} requirements; examples: {', '.join(group['requirements'][:8])}. Full requirement lists are in `fault_causes_by_requirement.csv`.")
    for status,items in examples.items():
        e=items[0];lines.append(f"- {status}: `{e['case_id']}` / {e['workflow']}; full evidence in `records/{e['case_id']}.json`.")
    lines+=['','The previous 50-case counts (NLTL_v2: 32 strict / 13 unrelated / 5 missed; Single-shot: 31 strict / 2 unrelated / 3 missed / 14 no verdict) are preserved. Exact additions by status are in `previous50_comparison.csv`.','', '## Remaining blockers','']
    for code,n in report['blocker_codes'].items():lines.append(f'- {code}: {n} blocker entries. Entries can overlap within a case.')
    lines+=['','Every blocked case has its own source clause, intended rationale, evidence path and failed gate in `records/` and `unresolved_blockers.csv`. Examples include omitted parent applicability (IMO26-010/011), omitted source acceptance criteria (I2-065), unresolved welded-profile scope (I2-043), source equation/table reconciliation, multi-field/default replay discrepancies and logical/SPARQL semantics not yet established. Missing authority or applicability assertions are not invented.','', '## Artifacts and resume','', '`full_case_ledger.csv` covers all 4,320 workflow/case rows. `reviewed_failure_specs_additional.json` contains independently verified pairs and exact RDF deltas; prior50 are referenced separately. `cases/` saves each pair, unchanged shape bytes and reports. Historical no-verdict cases have no new offline validation/credit. `diagnostic_results.json` references the preserved diagnostic arm, with no new transformations.','', '```bash','.venv/bin/python evaluation_audit/audit_all.py --phase report','.venv/bin/python evaluation_audit/audit_all.py --phase all --workers 6','# Only after adding concrete source/repair evidence for blocked cases:','.venv/bin/python evaluation_audit/audit_all.py --phase all --retry-blocked --workers 6','.venv/bin/python -m unittest discover -s evaluation_audit -v','```','', 'Each finished case is checkpointed atomically. Repaired validations are cached by graph, shape and environment hashes; unchanged negative reports are reused from the authoritative baseline. Report generation refuses pending cases and checks preserved input hashes. Retrying blockers archives the previous record.']
    (OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    atomic(OUT/'checks.json',verified_checks)
    codepaths=list((audit.HERE/'full_audit').glob('*.py'))+[audit.HERE/'audit.py',audit.HERE/'audit_all.py',audit.HERE/'test_all_negatives.py',audit.HERE/'full_audit/source_reviews.json',audit.HERE/'requirements-lock.txt',audit.HERE/'README.md']
    codehashes={str(p):audit.sha(p) for p in codepaths}
    version=hashlib.sha256(json.dumps(codehashes,sort_keys=True).encode()).hexdigest()[:16]
    snapshot=OUT/'implementation_versions'/version
    for path in codepaths:
        target=snapshot/path.relative_to(audit.HERE);target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes(path.read_bytes())
        assert audit.sha(target)==codehashes[str(path)]
    atomic(OUT/'execution_provenance.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),code_and_manual_review_sha256=codehashes,implementation_snapshot=str(snapshot),preserved_inputs=audit.read(OUT/'immutable_inputs.json'),baseline_reexecuted=False,new_llm_api_calls=0,new_shape_generations=0,validation_options=audit.read(BASE/'environment.json')))
    print(json.dumps(counts,indent=2),flush=True)
