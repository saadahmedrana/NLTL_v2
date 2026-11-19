from pathlib import Path
import json,hashlib,collections,shutil
from rdflib import Graph,URIRef,RDF,Literal
from rdflib.namespace import SH
from rdflib.collection import Collection
from nltlv2.core import Project,load,write,offline_network_guard
from nltlv2.schema import Schema,N,Q,U
from nltlv2.evaluation import strict_status
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/i2_v040_targeted_state_20261116.json');LABEL='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def metrics(rs):
 positives=[r for r in rs if r['expected']=='PASS'];negatives=[r for r in rs if r['expected']=='FAIL'];counts=collections.Counter(r.get('strict_status') for r in negatives)
 return dict(positive_acceptance=sum(r['verdict']['conforms'] is True for r in positives),positive_denominator=len(positives),strict_intended_detection=counts['VERIFIED_INTENDED_DETECTION'],negative_denominator=len(negatives),missed_defects=counts['MISSED_INTENDED_DEFECT'],unrelated_rejections=counts['UNRELATED_OR_ADDITIONAL_FAILURE'],unresolved_attribution=counts['UNRESOLVED_ATTRIBUTION'],negative_no_verdict=counts['NO_VERDICT'],no_verdict=sum(r['verdict']['conforms'] is None for r in rs),repaired_acceptance=sum(r['repaired_verdict']['conforms'] is True for r in negatives),repaired_denominator=len(negatives),ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rs),ordinary_executable_denominator=sum(r['verdict']['conforms'] is not None for r in rs),case_denominator=len(rs))
def run():
 state=load(STATE);assert state['status']=='DIAGNOSTIC_FINISHED';group=Path(state['group']);out=group/'evaluation';shutil.copyfile(__file__,out/'semantic_review_and_report.py');run=load(group/'diagnostic/run.json');rows=load(out/'raw_results.json');cases=load(out/'reviewed_selection.json')['cases'];schema=Schema(Project(group/'snapshot'));reviews=[]
 with offline_network_guard():
  for r in rows:
   if r['expected']!='FAIL':continue
   status=r['strict_provisional'];meaning=None
   if status=='PENDING_SEMANTIC_REVIEW':
    assert r['version']==2 and r['repaired_verdict']['conforms'] is True
    code=(group/'diagnostic/candidate_02.ttl').read_text();shape=Graph().parse(data=code,format='turtle');fixture=Graph().parse(out/'inputs'/next(Path(c['fixture']).name for c in cases if c['case_id']==r['case_id']));ship=next(fixture.subjects(RDF.type,N.ship));d=r['violation_details'];cid=r['case_id'];source=load(group/'snapshot/data/contracts/development_preflight_profiles.json')['requirements']['I2-004']['source']
    if cid=='I2-004-G-F01':
     assert len(d)==1 and d[0]['component']==str(SH.SPARQLConstraintComponent) and d[0]['focus']==str(ship)
     owner=URIRef(d[0]['source_shape']);assert (owner,SH.targetClass,N.ship) in shape;query=str(shape.value(shape.value(owner,SH.sparql),SH.select));assert 'MAX(?caseValue)' in query and 'SELECT ?this ?focus ?resultValue' in query and 'GROUP BY ?this ?focus ?resultValue' in query and 'FILTER (?focus = $this)' in query and 'FILTER (?resultValue != ?maximumCaseValue)' in query
     meaning=dict(kind='INTENDED_SELECTED_DISPLACEMENT_NOT_MAXIMUM',constraint=query,complete_paths=['ship/upperIceWaterlineDisplacement/qudt:numericValue','ship/hasUpperIceWaterlineCase/waterlineCaseDisplacement/qudt:numericValue'],reason='The applicable ship is selected by the existing focus equality. The aggregate groups the bound focus/result and computes MAX of the linked case values; the constraint reports numeric inequality with that maximum. The sole negative report is that constraint; the intended-only numeric repair makes the full unchanged shape pass.')
    elif cid=='I2-004-G-F02':
     assert len(d)==1 and d[0]['component']==str(SH.MinCountConstraintComponent) and d[0]['path']==str(N.upperIceWaterlineDisplacement) and d[0]['focus']==str(ship);assert not list(fixture.objects(ship,N.upperIceWaterlineDisplacement));assert [str(SH.minCount),Literal(1).n3()] in d[0]['source_triples']
     meaning=dict(kind='INTENDED_MISSING_SELECTED_DISPLACEMENT',required_owner_path='ship/upperIceWaterlineDisplacement',constraint='sh:minCount 1',reason='The report is on the applicable ship and exact required result property; the fixture omits that property. Supplying only the certified selected-displacement counterpart makes the full shape pass.')
    elif cid=='I2-004-G-F03':
     wrappers=[x for x in d if x['component']==str(SH.NodeConstraintComponent)];leaves=[x for x in d if x['component']!=str(SH.NodeConstraintComponent)];assert len(wrappers)==len(leaves)==1
     parent=wrappers[0];leaf=leaves[0];assert parent['focus']==str(ship) and parent['path']==str(N.upperIceWaterlineDisplacement) and leaf['node'] in parent['details'] and leaf['focus']==parent['value'] and leaf['path']==str(Q.unit) and leaf['component']==str(SH.InConstraintComponent)
     quantity=URIRef(parent['value']);actual=list(fixture.objects(quantity,Q.unit));assert actual==[U.UNITLESS]
     quantity_shape=shape.value(next(ps for root in shape.subjects(SH.targetClass,N.ship) for ps in shape.objects(root,SH.property) if shape.value(ps,SH.path)==N.upperIceWaterlineDisplacement),SH.node)
     unit_shape=next(ps for ps in shape.objects(quantity_shape,SH.property) if shape.value(ps,SH.path)==Q.unit);members=list(Collection(shape,shape.value(unit_shape,SH['in'])));assert members==[U.KiloTON_Metric]
     meaning=dict(kind='INTENDED_WRONG_CANONICAL_UNIT',required_owner_path='ship/upperIceWaterlineDisplacement/qudt:unit',observed_unit=str(actual[0]),required_unit=str(U.KiloTON_Metric),reason='The parent node wrapper points via sh:detail to the unit-membership violation on that exact selected quantity. The only leaf rejects the intended UNITLESS mutation against the property-specific canonical kilotonne unit. The intended-only unit repair makes the full shape pass. The wrapper is the same underlying failure, not an unrelated violation.')
    else:raise AssertionError('Unreviewed negative case')
    status=strict_status(False,True,True,False,certified=True,attribution_resolved=True);reviews.append(dict(label=LABEL,candidate_version=2,candidate_sha256=r['candidate_sha256'],case_id=cid,classification=status,source=source,reasoning=meaning,violation_details=d,reports_path=r['reports_path'],certified_repair=next(c['source_review']['independent_repair_review'] for c in cases if c['case_id']==cid)))
   r['strict_status']=status
   if meaning:r['attribution']=meaning
  write(out/'semantic_adjudications.json',reviews);write(out/'independent_results.json',dict(label=LABEL,version='0.4.0',rows=rows,exclusions=[],shape_transformations=[],feedback_to_repair=False,evaluation_after_diagnostic=True))
  results={str(v):metrics([r for r in rows if r['version']==v]) for v in sorted({r['version'] for r in rows})}
  write(out/'candidate_metrics.json',dict(label=LABEL,candidates=results,accepted_diagnostic_candidate=run['accepted_version'],rejected_candidate_credit=False,not_fresh_workflow_accuracy=True))
  events=load(group/'diagnostic/call_ledger.json');assert all(e['status']=='RESPONSE' for e in events);counts=dict(collections.Counter(e['route'] for e in events));assert counts=={'targeted_repair':1,'review':1}
  usage=dict(label=LABEL,provider_calls=len(events),routes=counts,initial_generation_calls=0,repair_calls=1,review_calls=1,auxiliary_format_retries=0,input_tokens=sum(e['usage']['input_tokens'] for e in events),output_tokens=sum(e['usage']['output_tokens'] for e in events),total_tokens=sum(e['usage']['total_tokens'] for e in events),provider_request_seconds=sum(e['elapsed_seconds'] for e in events),diagnostic_seconds=load(group/'execution_completion.json')['elapsed_seconds'],external_validation_seconds=load(out/'completion.json')['elapsed_seconds'],provider_details_preserved=True);write(group/'usage_summary.json',usage)
  before=load(group/'historical_artifact_hashes_before.json');historybad=[f for f,h in before.items() if sha(ROOT/f)!=h];frozen=load(group/'snapshot_hashes.json');changed=[f for f,h in frozen.items() if sha(group/'snapshot'/f)!=h or sha(ROOT/f)!=h];assert not historybad and not changed
  sent='\n'.join(f.read_text() for f in (group/'diagnostic').glob('provider_request_*.json'));leaks=[c['case_id'] for c in cases if c['case_id'] in sent];assert not leaks and 'https://w3id.org/nltl/benchmark/i2-batch-g/' not in sent
  seed=(group/'diagnostic/candidate_01.ttl').read_text();repaired=(group/'diagnostic/candidate_02.ttl').read_text();assert sha(group/'diagnostic/candidate_01.ttl')=='d2c44f9c6243b3169e3d10d7ae32c81ed4a8342d6a4e6de9dd0e7f4a02e01184'
  expected=seed.replace('SELECT ?focus ?resultValue (MAX(?caseValue) AS ?maximumCaseValue)','SELECT ?this ?focus ?resultValue (MAX(?caseValue) AS ?maximumCaseValue)').replace('GROUP BY ?focus ?resultValue','GROUP BY ?this ?focus ?resultValue');assert expected==repaired
  history=run['history'];assert [r['status'] for r in history]==['REJECTED','ACCEPTED'];assert run['accepted_version']==2
  coverage0=load(group/'diagnostic/development_coverage_01.json');coverage1=load(group/'diagnostic/development_coverage_02.json');assert all(w['status']=='UNASSESSABLE_CANDIDATE_ERROR' for w in coverage0['witnesses']);assert all(w['status']=='OBSERVED_MATCH' for w in coverage1['witnesses']);assert len(coverage1['witnesses'])==13
  integrity=load(group/'diagnostic/request_001_integrity.json');assert integrity['previous_code_full'] and integrity['feedback_same_version'];assert results['1']['no_verdict']==6 and results['2']['strict_intended_detection']==3 and results['2']['positive_acceptance']==3 and results['2']['repaired_acceptance']==3
  verification=dict(label=LABEL,status='PASSED',historical_artifacts_verified=len(before),historical_mismatches=historybad,frozen_input_mismatches=changed,base_config_unchanged=True,seed_byte_identical=True,full_latest_seed_in_repair_request=True,external_case_ids_in_requests=leaks,external_instance_namespace_in_requests=False,generation_snapshot_has_evaluation=False,external_evaluation_after_completion=True,no_dispatch_after_first_acceptance=True,no_second_repair_or_extra_attempt=True,initial_generations=0,manual_candidate_edits=False,old_scores_changed=False)
  write(group/'verification.json',verification)
  summary=dict(label=LABEL,version='0.4.0',requirement='I2-004',seed_historical_version=5,seed_diagnostic_version=1,accepted_diagnostic_version=2,status='ACCEPTED',nested_projection_corrected=True,query_executed=True,edit='Only two model-produced line changes: add ?this to nested SELECT projection and GROUP BY.',internal=dict(seed_unassessable_witnesses=13,repaired_matched_witnesses=13,known_query_error_findings_resolved=2,underlying_query_defects=1,behavioral_counterexamples_before=None,behavioral_counterexamples_after=0,persistent=0,regressed=0,unassessable_after=0,note='The seed could not execute; 13 newly assessed matches are not 13 previously confirmed behavioral defects resolved.'),external_candidates=results,usage=usage,historical_artifacts_unchanged=len(before),limitations=['One targeted seeded development diagnostic, not fresh pipeline performance or a Single-shot comparison.','Six reviewed cases and three intended-only counterparts plus finite internal witnesses do not prove complete regulatory correctness.','No historical scores changed; seed and rejected candidates receive no workflow credit.'],five_requirement_batch_restarted=False,study_run=False)
  write(group/'SUMMARY.json',summary)
  report=f'''# TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC — I2-004, frozen v0.4.0

The first live repair was internally accepted; the diagnostic stopped immediately. Zero initial generations; no second repair, regeneration, manual edit, batch restart or study.

| Question | Result |
|---|---|
| Nested SELECT projection corrected? | Yes. The model added `?this` to the nested SELECT and GROUP BY; these are the only two changed lines. |
| Repaired query executed? | Yes, on all 13 original internal witnesses and all reviewed external cases/counterparts. |
| Internal transitions | Two corroborating findings for one query-level projection defect resolved. No persistent, regressed or unassessable findings remain. The seed's 13 behavioral checks were unassessable; the repair produces 13 assessed matches, not 13 prior behavioral defects resolved. |
| Internal acceptance | Diagnostic candidate 2 (one repair of the historical v5 seed), after deterministic checks, runtime probe and reviewer ACCEPT. No format retry. |

## Independent evaluation — after repair finished

| Diagnostic candidate | Positives accepted / 3 | Strict intended detections / 3 | Missed | Unrelated | Unresolved attribution | No-verdict cases / 6 | Repaired counterparts passing / 3 | Ordinary agreement / executable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seed (historical v5; diagnostic v1) | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 / 0 |
| Repaired, accepted v2 | 3 | 3 | 0 | 0 | 0 | 0 | 3 | 6 / 6 |

F01 reports the source-backed MAX comparison at the applicable ship. F02 reports missing selected displacement via minCount 1 on the exact owner/path. F03 reports the canonical-unit mutation through a node wrapper and its nested unit-membership detail: these describe the same intended defect. Every intended-only repair makes the full unchanged candidate pass; no unrelated leaves remain. Attribution uses constraint/query/path semantics and the counterfactual reports, not messages or blank-node spelling. See `evaluation/semantic_adjudications.json`.

## Actual calls, tokens and time

- **{usage['provider_calls']} calls:** one targeted repair and one review. **0 initial generations, 0 format retries.**
- **{usage['input_tokens']:,} input + {usage['output_tokens']:,} output = {usage['total_tokens']:,} provider-reported tokens.** Raw provider usage, including cache/reasoning details, is preserved.
- Diagnostic elapsed **{usage['diagnostic_seconds']:.2f}s**; provider request time **{usage['provider_request_seconds']:.2f}s**; separate external validation **{usage['external_validation_seconds']:.2f}s**.

## Evidence and preservation

The seed SHA-256 is `d2c44f9c6243b3169e3d10d7ae32c81ed4a8342d6a4e6de9dd0e7f4a02e01184`. Installed/source identity, bundle hashes and frozen resources were checked before dispatch. The base config remains unchanged; live authorization was a saved runtime overlay through the existing explicit opt-in. Credentials stayed external and were not copied or exposed.

Complete rendered requests, actual provider payloads/raw responses, candidate hashes, original diagnostics, diff, stable reconciliation, persistent summaries and acceptance records are in `diagnostic/`. Independent reports/oracles and semantic adjudications are in `evaluation/`. The snapshot contains no evaluation directory; the repair process denied reads of original evaluation, old outputs and old MVP. External fixture IDs/instance namespaces were absent from sent requests.

**{len(before)} historical output artifacts verified unchanged.** This demonstrates one successful live targeted repair and response path. It does not establish fresh workflow accuracy, general superiority, complete correctness or an optimal attempt budget. Historical stopped-run scores remain unchanged. Stopped after this diagnostic.
'''
  (group/'REPORT.md').write_text(report)
  hashes={str(f.relative_to(group)):sha(f) for f in group.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name!='artifact_hashes.json'};write(group/'artifact_hashes.json',hashes)
  print(json.dumps(dict(label=LABEL,status='ACCEPTED',candidate_metrics=results,usage=usage,historical_artifacts_verified=len(before),report=str(group/'REPORT.md')),indent=2))
if __name__=='__main__':run()
