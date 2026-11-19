"""Fresh-batch-only accounting and post-generation review. Never feeds repair."""
from pathlib import Path
from collections import Counter
import json,hashlib,shutil
from rdflib import Graph,Literal,URIRef,XSD
from rdflib.namespace import SH
from nltlv2.core import load,write,offline_network_guard
STATE=Path('/private/tmp/five_v040_pilot_state_20261117.json');ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
METHODS={'Single-shot':'single_shot','NLTL':'nltl'}
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def metrics(rows):
 pos=[r for r in rows if r['expected']=='PASS'];neg=[r for r in rows if r['expected']=='FAIL'];counts=Counter(r.get('strict') for r in neg);exe=[r for r in rows if r['verdict']['conforms'] is not None]
 return dict(cases=len(rows),positive_denominator=len(pos),positive_acceptance=sum(r['verdict']['conforms'] is True for r in pos),positive_rejection=sum(r['verdict']['conforms'] is False for r in pos),positive_no_verdict=sum(r['verdict']['conforms'] is None for r in pos),negative_denominator=len(neg),strict_intended_detection=counts['VERIFIED_INTENDED_DETECTION'],missed_defects=counts['MISSED_INTENDED_DEFECT'],unrelated_rejections=counts['UNRELATED_OR_ADDITIONAL_FAILURE'],unresolved_attribution=counts['UNRESOLVED_ATTRIBUTION'],negative_no_verdict=counts['NO_VERDICT'],no_verdict=sum(r['verdict']['conforms'] is None for r in rows),ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rows),ordinary_disagreement=sum(r['ordinary_agreement'] is False for r in rows),ordinary_executable_denominator=len(exe),ordinary_executable_percent=100*sum(r['ordinary_agreement'] is True for r in exe)/len(exe) if exe else None,coverage_percent=100*len(exe)/len(rows) if rows else None,repaired_acceptance=sum(r.get('repaired_verdict',{}).get('conforms') is True for r in neg))
def nov(c):return dict(requirement_id=c['requirement_id'],case_id=c['case_id'],expected=c['expected'],verdict=dict(conforms=None),ordinary_agreement=None,strict='NO_VERDICT' if c['expected']=='FAIL' else None)
def delta(before,after):
 ga=[];la=[];gs=[];ls=[];gp=[];lp=[];new_nv=[]
 for old in before:
  new=next(r for r in after if r['case_id']==old['case_id']);cid=old['case_id']
  if old['ordinary_agreement'] is not True and new['ordinary_agreement'] is True:ga.append(cid)
  if old['ordinary_agreement'] is True and new['ordinary_agreement'] is not True:la.append(cid)
  if old.get('strict')!='VERIFIED_INTENDED_DETECTION' and new.get('strict')=='VERIFIED_INTENDED_DETECTION':gs.append(cid)
  if old.get('strict')=='VERIFIED_INTENDED_DETECTION' and new.get('strict')!='VERIFIED_INTENDED_DETECTION':ls.append(cid)
  if old['expected']=='PASS':
   if old['verdict']['conforms'] is not True and new['verdict']['conforms'] is True:gp.append(cid)
   if old['verdict']['conforms'] is True and new['verdict']['conforms'] is not True:lp.append(cid)
  if old['verdict']['conforms'] is not None and new['verdict']['conforms'] is None:new_nv.append(cid)
 return dict(ordinary_gain_ids=ga,ordinary_loss_ids=la,strict_gain_ids=gs,strict_loss_ids=ls,positive_gain_ids=gp,positive_loss_ids=lp,new_no_verdict_ids=new_nv,deduplicated_gain_ids=sorted(set(ga+gs+gp)),deduplicated_loss_ids=sorted(set(la+ls+lp)))
def run():
 state=load(STATE);assert state['status']=='GENERATION_COMPLETE';group=Path(state['group']);out=group/'evaluation';shutil.copyfile(__file__,out/'report_driver.py');cases=load(out/'reviewed_selection.json')['cases'];rows=load(out/'adjudicated_candidate_results.json');manifest=load(group/'execution_manifest.json');rids=manifest['requirements'];assert len(cases)==30
 with offline_network_guard():
  index=load(out/'candidate_index.json');candidate_metrics=[]
  for c in index:
   subset=[r for r in rows if (r['requirement_id'],r['method'],r['version'])==(c['requirement_id'],c['method'],c['version'])];candidate_metrics.append(dict(c,metrics=metrics(subset)))
  write(out/'candidate_metrics.json',candidate_metrics)
  ledger=[];selection={};runs={};events={};usage={};per_req={}
  for rid in rids:
   selection[rid]={};per_req[rid]={};usage[rid]={}
   for method,folder in METHODS.items():
    dest=group/rid/folder;run=load(dest/'run.json');runs[(rid,method)]=run;ev=load(dest/'call_ledger.json');events[(rid,method)]=ev
    assert all(e['status']=='RESPONSE' for e in ev)
    version=run['evaluation_candidate'] if method=='Single-shot' else run['accepted_version'];selection[rid][method]=dict(status=run['status'],selected_version=version,candidate_attempts=run['candidate_attempts'])
    selected=[dict(r,diagnostic_only=False,selection='ORIGINAL_SINGLE_SHOT' if method=='Single-shot' else 'FIRST_INTERNAL_ACCEPTANCE') for r in rows if r['requirement_id']==rid and r['method']==method and r['version']==version]
    if not selected:selected=[dict(nov(c),method=method,diagnostic_only=False,selection='NO_ACCEPTED_CANDIDATE') for c in cases if c['requirement_id']==rid]
    ledger.extend(selected);per_req[rid][method]=dict(selection[rid][method],metrics=metrics(selected))
    usage[rid][method]=dict(calls=len(ev),routes=dict(Counter(e['route'] for e in ev)),tokens={k:sum(e['usage'].get(k,0) for e in ev) for k in ['input_tokens','output_tokens','total_tokens']},provider_seconds=sum(e['elapsed_seconds'] for e in ev),workflow_seconds=run['elapsed_seconds'],auxiliary_format_retries=run['auxiliary_format_retries'])
  write(out/'workflow_case_ledger.json',ledger);write(out/'per_requirement_results.json',per_req)
  aggregate={method:metrics([r for r in ledger if r['method']==method]) for method in METHODS}
  common_ids=[c['case_id'] for c in cases if all(next(r for r in ledger if r['case_id']==c['case_id'] and r['method']==method)['verdict']['conforms'] is not None for method in METHODS)]
  common={method:metrics([r for r in ledger if r['method']==method and r['case_id'] in common_ids]) for method in METHODS}
  # Initial -> accepted selection and initial -> last generated diagnostic are different analyses.
  initial=[];selected_nl=[];last_nl=[];deltas={};all_transition_gain=set();all_transition_loss=set()
  for rid in rids:
   nl=[r for r in rows if r['method']=='NLTL' and r['requirement_id']==rid];first=[r for r in nl if r['version']==1];last=max(r['version'] for r in nl);final=[r for r in nl if r['version']==last];selected=[r for r in ledger if r['method']=='NLTL' and r['requirement_id']==rid];initial.extend(first);selected_nl.extend(selected);last_nl.extend(final)
   transitions=[]
   for v in range(2,last+1):
    d=delta([r for r in nl if r['version']==v-1],[r for r in nl if r['version']==v]);all_transition_gain.update(d['deduplicated_gain_ids']);all_transition_loss.update(d['deduplicated_loss_ids']);transitions.append(dict(from_version=v-1,to_version=v,diagnostic_only=True,**d))
   deltas[rid]=dict(initial_to_selected=delta(first,selected),initial_to_last_diagnostic=delta(first,final),last_version=last,selected_version=selection[rid]['NLTL']['selected_version'],stepwise=transitions)
  recoveries=dict(per_requirement=deltas,initial_to_selected=delta(initial,selected_nl),initial_to_last_diagnostic=delta(initial,last_nl),deduplicated_any_transition_gain_ids=sorted(all_transition_gain),deduplicated_any_transition_loss_ids=sorted(all_transition_loss),note='A case can appear in both gain/loss sets when repairs oscillate. Counts are unique case IDs, not sum of repeated transitions. NO_VERDICT losses denote lost coverage, not a proven new logical rejection. Last/rejected diagnostics receive no workflow credit.')
  write(out/'recoveries_regressions.json',recoveries)
  # Prefix results use the first acceptance; no candidate is selected using external scores.
  budgets=[]
  for budget in range(2,7):
   prefix_rows=[];sel={};prefix_events=[];prefix_seconds=0
   for rid in rids:
    run=runs[(rid,'NLTL')];accepted=next((h['version'] for h in run['history'] if h['version']<=budget and h['accepted']),None);sel[rid]=accepted
    chosen=[r for r in rows if r['requirement_id']==rid and r['method']=='NLTL' and r['version']==accepted];prefix_rows.extend(chosen or [nov(c) for c in cases if c['requirement_id']==rid])
    for e in events[(rid,'NLTL')]:
     candidate=1 if e['route']=='generation' else e['candidate_version']+1 if e['route'].endswith('repair') else e['candidate_version']
     if candidate<=budget:prefix_events.append(e)
    prefix_seconds+=sum(h['candidate_response_seconds']+sum(m['elapsed_seconds'] for m in h['request_metrics'] if m['route'].startswith('review')) for h in run['history'] if h['version']<=budget)
   single_events=[e for rid in rids for e in events[(rid,'Single-shot')]];paired_events=single_events+prefix_events
   budgets.append(dict(budget=budget,selected_versions=sel,NLTL=metrics(prefix_rows),Single_shot=aggregate['Single-shot'],NLTL_calls=len(prefix_events),paired_calls=len(paired_events),NLTL_tokens={k:sum(e['usage'].get(k,0) for e in prefix_events) for k in ['input_tokens','output_tokens','total_tokens']},paired_tokens={k:sum(e['usage'].get(k,0) for e in paired_events) for k in ['input_tokens','output_tokens','total_tokens']},observed_NLTL_provider_seconds=prefix_seconds,note='Same saved histories; first internal acceptance only. Prefix prompts/settings are unchanged; external scores do not choose candidates. Runtime here is observed included provider time, not a separately executed budget run.'))
  write(out/'budget_prefixes.json',budgets)
  totals={}
  for method in METHODS:
   ev=[e for rid in rids for e in events[(rid,method)]];totals[method]=dict(calls=len(ev),routes=dict(Counter(e['route'] for e in ev)),tokens={k:sum(e['usage'].get(k,0) for e in ev) for k in ['input_tokens','output_tokens','total_tokens']},provider_seconds=sum(e['elapsed_seconds'] for e in ev),workflow_seconds=sum(runs[(rid,method)]['elapsed_seconds'] for rid in rids),auxiliary_format_retries=sum(runs[(rid,method)]['auxiliary_format_retries'] for rid in rids))
  ev=[e for a in events.values() for e in a];usage_summary=dict(per_requirement=usage,by_method=totals,total=dict(calls=len(ev),routes=dict(Counter(e['route'] for e in ev)),tokens={k:sum(e['usage'].get(k,0) for e in ev) for k in ['input_tokens','output_tokens','total_tokens']},provider_seconds=sum(e['elapsed_seconds'] for e in ev),generation_batch_seconds=load(group/'execution_outcomes.json')['elapsed_seconds'],external_validation_seconds=load(out/'validation_completion.json')['elapsed_seconds'],auxiliary_format_retries=0));write(group/'usage_summary.json',usage_summary)
  # Evidence-backed findings discovered in this batch; no fixes or relabels.
  a=Literal('7',datatype=XSD.decimal);b=Literal('7.0',datatype=XSD.decimal);assert a!=b and bool(a.eq(b))
  false_acceptance=[]
  for rid in rids:
   if selection[rid]['NLTL']['selected_version'] is None:continue
   rs=[r for r in ledger if r['requirement_id']==rid and r['method']=='NLTL'];bad=[r for r in rs if (r['expected']=='PASS' and r['verdict']['conforms'] is False) or (r['expected']=='FAIL' and r['strict']!='VERIFIED_INTENDED_DETECTION')]
   if bad:false_acceptance.append(dict(requirement_id=rid,version=selection[rid]['NLTL']['selected_version'],affected_case_ids=[r['case_id'] for r in bad],positive_failures=[r['case_id'] for r in bad if r['expected']=='PASS']))
  assert false_acceptance==[dict(requirement_id='I2-005',version=2,affected_case_ids=['I2-005-G-P01','I2-005-G-F02','I2-005-G-F03','I2-005-G-F04'],positive_failures=['I2-005-G-P01'])]
  lexical=[]
  q=URIRef('http://qudt.org/schema/qudt/numericValue')
  for file in sorted((out/'inputs').glob('I2-005*')):lexical.append(dict(file=file.name,values=[v.n3() for v in Graph().parse(file).objects(None,q)]))
  literal_issue=dict(requirement_id='I2-005',cause='Generated term-equality constraint used for numeric value equality; source-authored witness lexical coverage gap',source_clause='I2.2.5',source_expectation='Inclination is numerically 7 degrees; approved xsd:decimal encoding does not mandate a unique lexical spelling.',term1=a.n3(),term2=b.n3(),RDF_term_equal=False,numeric_value_equal=True,shacl='sh:hasValue "7"^^xsd:decimal',affected_methods=['Single-shot','NLTL'],false_internal_acceptance=false_acceptance,fixture_spelling_evidence=lexical,confirmed_fixture_defect=False,shape_repairs_applied=False)
  imo=[]
  for h in runs[('IMO-001','NLTL')]['history']:
   coverage=load(group/f"IMO-001/nltl/development_coverage_{h['version']:02d}.json");imo.append(dict(version=h['version'],behavior=coverage['status'],failed_witness_ids=[w['witness_id'] for w in coverage['witnesses'] if w['status']=='CONFIRMED_COUNTEREXAMPLE'],findings=[dict(category=f['category'],message=f['message'],excerpt=f['excerpt'],diagnostic=f['diagnostic']) for f in h['findings'] if f['blocking']],external_metrics=next(c['metrics'] for c in candidate_metrics if c['requirement_id']=='IMO-001' and c['method']=='NLTL' and c['version']==h['version']),accepted=h['accepted']))
  blocker=dict(requirement_id='IMO-001',cause='Overbroad obligation-preservation guard cannot discharge deletion of source-unsupported selector closure',source_expectation='Known nonapplicable design conditions remain valid; the Category A obligation is conditional. The explicit selector is required, but is not a one-value closed vocabulary.',original_excess_constraint='sh:path designIceCondition ; sh:in (mediumFirstYearIceWithPossibleOldIceInclusions)',finding_assessment='The deletion is factually detected, but preserving this generated selector closure as a regulatory obligation is unsupported. Even candidates remove it, pass all configured witnesses and all five external cases, but are rejected by the guard. No automatic conflict status was raised.',timeline=imo,unsupported_preservation_blocker_versions=[2,4,6],source_unchanged=True,guard_disabled=False,rejected_candidate_credit=False)
  write(out/'demonstrated_defects.json',dict(literal_comparison=literal_issue,regression_authorization=blocker))
  feedback=[]
  for rid in rids:
   run=runs[(rid,'NLTL')];steps=[]
   for h in run['history']:
    steps.append(dict(version=h['version'],status=h['status'],accepted=h['accepted'],findings=Counter(f['category'] for f in h['findings']),review=h['review'],scope=h['development_coverage'].get('unchecked'),behavior=h['development_coverage']['status']))
   feedback.append(dict(requirement_id=rid,attempts=run['candidate_attempts'],accepted_version=run['accepted_version'],steps=steps,repair_assessment='Corrected nonexistent qudt:DEG to canonical unit:DEG without numeric scale change; relevant internal findings resolved, but external lexical-equality defect remains.' if rid=='I2-005' else 'Five repairs oscillated between removing unsupported closure (valid behavior, preservation blocker) and restoring it (nonapplicable branch failures); no accepted output.' if rid=='IMO-001' else 'Accepted fresh initial candidate; no repair exercised.'))
  write(out/'feedback_review.json',dict(requirements=feedback,unsupported_preservation_findings=blocker['unsupported_preservation_blocker_versions'],unresolved_static_warnings='I2-004 initial standalone prefix-context warning retained at acceptance; actual execution passed reviewed cases. It is not a confirmed code defect.',false_internal_acceptances=false_acceptance))
  summary=dict(version='0.4.0',label='FRESH_PAIRED_DEVELOPMENT_PILOT',status='GENERATION_COMPLETE',requirements=rids,deferred=['I2-042'],scope='30 reviewed development cases: 14P/16N and 16 repaired counterparts; not held-out representative benchmark',selection=selection,per_requirement=per_req,aggregate=aggregate,common_executable_case_ids=common_ids,common_executable_case_count=len(common_ids),common_executable_negative_denominator=sum(c['expected']=='FAIL' for c in cases if c['case_id'] in common_ids),common_subset_secondary_only=common,accepted_requirements=4,NLTL_attempts={rid:runs[(rid,'NLTL')]['candidate_attempts'] for rid in rids},recoveries_regressions=recoveries,budgets=budgets,usage=usage_summary,false_internal_acceptances=false_acceptance,exclusions=[],shape_transformations=[],previous_pilots_or_seeded_diagnostics_pooled=False,recommendation='Fix the demonstrated source-backed regression-authorization and numeric-literal witness/operand gaps before further live expansion. Do not proceed to the 50-requirement study or infer superiority/optimal budget from these five development requirements.')
  write(group/'SUMMARY.json',summary)
  # Invariants keep reported success independent from external selection.
  assert len(ledger)==60 and len(rows)==90 and len(candidate_metrics)==16
  assert aggregate['Single-shot']['strict_intended_detection']==12 and aggregate['NLTL']['strict_intended_detection']==10
  assert aggregate['Single-shot']['ordinary_agreement']==27 and aggregate['NLTL']['ordinary_agreement']==24
  assert aggregate['NLTL']['no_verdict']==5 and per_req['IMO-001']['NLTL']['selected_version'] is None
  assert usage_summary['total']['calls']==20 and usage_summary['total']['tokens']['total_tokens']==186380
  report=['# Fresh v0.4.0 paired development pilot','','Only this fresh batch is included. All five requirements completed; I2-042 deferred. No seeded shapes or diagnostic solutions were supplied. No implementation/configuration changes, reruns, exclusions or shape transformations.','','## Selected workflow results','','P = positives accepted; S = strict intended detections; M = missed defects; U = unrelated/additional rejection; A = unresolved attribution; NV = no-verdict cases (positive + negative). P and S have separate denominators.','','| Requirement | Workflow | P | S | M | U | A | NV | Ordinary agreement / executable | NLTL acceptance |','|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
  for rid in rids:
   for method in METHODS:
    x=per_req[rid][method];m=x['metrics'];report.append(f"| {rid} | {method} | {m['positive_acceptance']}/{m['positive_denominator']} | {m['strict_intended_detection']}/{m['negative_denominator']} | {m['missed_defects']} | {m['unrelated_rejections']} | {m['unresolved_attribution']} | {m['no_verdict']} | {m['ordinary_agreement']}/{m['ordinary_executable_denominator']} | {x['selected_version'] if method=='NLTL' and x['selected_version'] else 'exhausted at 6' if method=='NLTL' else 'original'} |")
  for method in METHODS:
   m=aggregate[method];report.append(f"| TOTAL | {method} | {m['positive_acceptance']}/14 | {m['strict_intended_detection']}/16 | {m['missed_defects']} | {m['unrelated_rejections']} | {m['unresolved_attribution']} | {m['no_verdict']} | {m['ordinary_agreement']}/{m['ordinary_executable_denominator']} | |")
  report+=['','All 30 case IDs and 16 negative IDs remain in both workflow denominators. NLTL has one executable positive rejection and five NO_VERDICT cases (IMO-001: 2P/3N), not six ordinary disagreements. Single-shot has three ordinary disagreements. Ordinary executable agreement is 90% Single-shot and 96% NLTL, with coverage 100% and 83.33% respectively; these conditional percentages must not hide the missing NLTL outcomes. Correct/executable/retained counts are 27/30/30 and 24/25/30.','','The secondary common executable subset has 25 cases (12P/13N): Single-shot ordinary 23/25, strict 9/13; NLTL ordinary 24/25, strict 10/13. This subset omits the five valid IMO cases ONLY for a labelled coverage comparison; they remain in the primary results. No claim of superiority follows.','','## What repairs did','','- I2-004, TRF-010 and TRF-035 accepted candidate 1. I2-004 Single-shot misses the below-maximum defect because two NOT EXISTS filters are conjunctive; NLTL initially produced the correct disjunctive condition. This difference did not result from repair.','- I2-005 accepted candidate 2 after correcting `qudt:DEG` (wrong namespace) to canonical `unit:DEG` and adding query prefixes. Values/threshold were preserved. This is a safe identifier correction, not numeric conversion.','- I2-005 is nevertheless a false internal acceptance: both workflows use `sh:hasValue "7"^^xsd:decimal`. The reviewed positive and three valid repairs contain `"7.0"^^xsd:decimal`; their numeric value is 7 but RDF terms differ. Source and approved serialization require numeric equality and decimal datatype, not one lexical spelling. The internal positive witnesses use the matching `"7"` spelling. Keep all these valid tests. F01 alone receives strict credit because its certified repair uses the matching spelling and the full shape passes.','- IMO-001 exhausted six candidates. Initial/odd candidates wrongly close the selector to only the applicable medium-ice value. Even candidates remove that unsupported closure and pass all internal witnesses and all five external cases, but the preservation guard blocks the deleted `sh:in`. Later feedback restores the bad restriction, producing oscillation. Three unsupported preservation blockers occur at v2/v4/v6. No conflict status was raised; no operational failure occurred. These rejected candidates are diagnostic, never promoted to workflow success.','','Negative attribution inspected the actual property paths, source queries and nested details, with the intended-only repaired reports. The I2-005 lexical failures are unrelated/additional failures where valid repairs still reject. Other wrappers describe the same underlying intended missing/unit/value defects; no message-text or blank-node-ID matching was used. See `evaluation/semantic_adjudications.json` and `demonstrated_defects.json`.','','## Recoveries and regressions','','Initial → selected NLTL outputs: **one unique strict recovery**, I2-005-G-F01; no positive or ordinary recovery. Four previously correct IMO outcomes lose credit/coverage because no candidate was accepted (P01 and F01–F03); all five IMO outcomes become NO_VERDICT. These are coverage losses, not newly measured logical rejections.','','Initial → last generated diagnostics (unaccepted IMO v6 kept separate): two unique recoveries, I2-005-G-F01 strict and IMO-001-P02 positive/ordinary; no final logical regression. Across all repair transitions, IMO-001-P02 repeatedly recovers/regresses; count it once in each relevant union, not once per oscillation. No rejected IMO recovery contributes to selected-workflow scores.','','## Budgets 2–6','','Same saved histories, first acceptance within each prefix; no external-score selection and no new calls. All budgets select I2-004 v1, I2-005 v2, TRF-010 v1, TRF-035 v1; IMO has no acceptance. Performance is identical across budgets: NLTL P=11/14, strict=10/16, unrelated=3, no verdict=5. Higher budgets spend more on the unresolved preservation loop, not better selected outputs. This does not establish an optimal general budget.','','| Budget | Paired calls (Single-shot + NLTL) | NLTL calls | Paired provider tokens |','|---|---:|---:|---:|']
  for b in budgets:report.append(f"| {b['budget']} | {b['paired_calls']} | {b['NLTL_calls']} | {b['paired_tokens']['total_tokens']:,} |")
  report+=['','## Calls and runtime','','| Workflow | Calls | Initial generations | Repairs | Reviews | Format retries | Input tokens | Output tokens | Total tokens | Workflow seconds |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
  for method in METHODS:
   u=totals[method];rr=u['routes'];report.append(f"| {method} | {u['calls']} | {rr.get('generation',0)} | {rr.get('targeted_repair',0)+rr.get('syntax_repair',0)} | {rr.get('review',0)} | {rr.get('review_format_retry',0)} | {u['tokens']['input_tokens']:,} | {u['tokens']['output_tokens']:,} | {u['tokens']['total_tokens']:,} | {u['workflow_seconds']:.2f} |")
  t=usage_summary['total'];report += [f"\nTotal: {t['calls']} successful calls, {t['tokens']['total_tokens']:,} tokens ({t['tokens']['input_tokens']:,} input / {t['tokens']['output_tokens']:,} output). Generation batch {t['generation_batch_seconds']:.2f}s; included provider time {t['provider_seconds']:.2f}s; separate independent validation {t['external_validation_seconds']:.2f}s. Raw provider cache/reasoning usage preserved. No auxiliary retries.",'','## Recommendation','','Fix the demonstrated deterministic numeric-literal coverage/operand gap and the preservation guard’s authorization of source-backed excess-constraint removal before another live expansion. Do not disable the guard broadly, normalize fixtures to satisfy code, or drop valid cases. Keep earlier pilots and seeded diagnostics separate. These five development requirements cannot establish general superiority or an optimal iteration budget. The 50-requirement study remains pending review.']
  (group/'REPORT.md').write_text('\n'.join(report)+'\n')
  print(json.dumps(dict(aggregate=aggregate,calls=t['calls'],tokens=t['tokens'],report=str(group/'REPORT.md')),indent=2))
if __name__=='__main__':run()
