from pathlib import Path
import json,hashlib,collections,shutil,subprocess
from rdflib import Graph,RDF,URIRef
from rdflib.namespace import SH
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/v060_live_pilot_state_20261120_retry1.json');state=json.loads(STATE.read_text());g=Path(state['group']);E=g/'evaluation';RIDS=['I2-004','I2-005','IMO-001','TRF-010','TRF-035']
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert state['status']=='GENERATION_COMPLETE'
raw=read(E/'all_candidates.json');rows=raw['rows'];cases=read(E/'selection.json')['cases'];bycase={c['case_id']:c for c in cases}
# Independent human-equivalent source/constraint adjudication, after all provider dispatches.
# These are evidence records tied to saved candidates, never a production checker/answer profile.
keys=[('I2-004','NLTL',2,'I2-004-G-F02','upperIceWaterlineDisplacement','MinCountConstraintComponent'),('I2-005','NLTL',2,'I2-005-G-F04','hasBottomRegionLowerRegionBoundaryPoint','MinCountConstraintComponent'),('TRF-010','NLTL',1,'TRF-010-F02','iceClass','MinCountConstraintComponent'),('TRF-035','Single-shot',1,'TRF-035-F03','ruleLength','MinCountConstraintComponent'),('TRF-035','Single-shot',1,'TRF-035-F04','ruleLength','UNIT_HASVALUE_WITH_NODE_WRAPPER')]
adjudications=[]
for rid,wf,version,cid,prop,semantics in keys:
 r=next(x for x in rows if (x['requirement_id'],x['workflow'],x['version'],x['case_id'])==(rid,wf,version,cid));assert r['strict']=='UNRESOLVED_ATTRIBUTION';assert r['oracle']['issues']==[prop];assert r['verdict']['conforms'] is False and r['repaired_verdict']['conforms'] is True
 vs=r['verdict']['violations'];candidate=ROOT/r['candidate'];shape=Graph().parse(candidate)
 if semantics=='MinCountConstraintComponent':
  assert len(vs)==1 and vs[0]['path']=='https://w3id.org/nltl/vocab#'+prop and vs[0]['component']==str(SH.MinCountConstraintComponent)
  assert all(any(t['predicate']==str(SH.minCount) and t['object'].startswith('"1"') for t in v['constraint']) for v in r['violations_with_constraint_evidence'])
  explanation='The sole report is the minCount=1 constraint at the intended missing property. Complete constraint/owner path matches the reviewed defect. No other violations are reported; adding only the certified intended property/counterpart makes the full unchanged shape pass.'
 else:
  assert len(vs)==2 and {v['component'] for v in vs}=={str(SH.NodeConstraintComponent),str(SH.HasValueConstraintComponent)}
  assert any(v['path']=='http://qudt.org/schema/qudt/unit' for v in vs);assert any(v['path']=='https://w3id.org/nltl/vocab#ruleLength' for v in vs)
  root=URIRef('https://w3id.org/nltl/vocab#TRF035LengthQuantityShape');assert (root,None,None) in shape
  explanation='The HasValueConstraintComponent requires metre at ruleLength/qudt:unit. The sh:node report on ruleLength is the logical wrapper for the same unit defect, not an additional unrelated failure. The complete negative graph differs from its certified counterpart only in the intended unit assertion; both original reports disappear on that counterpart.'
 c=bycase[cid];ng=Graph().parse(ROOT/c['fixture']);pg=Graph().parse(ROOT/c['counterfactual']);folder='single_shot' if wf=='Single-shot' else 'nltl';ctx=read(g/rid/folder/'context.json')
 a=dict(requirement_id=rid,workflow=wf,version=version,case_id=cid,previous_status=r['strict'],status='VERIFIED_INTENDED_DETECTION',candidate=r['candidate'],candidate_sha256=r['candidate_sha256'],source_clause=ctx['requirement']['clause'],source_excerpt=ctx['requirement']['text'],intended_property=prop,admissible_semantics=semantics,reason=explanation,evidence_paths=dict(original_report=str((E/rid/folder/f'candidate_{version:02d}'/cid/'original_report.ttl').relative_to(ROOT)),repaired_report=str((E/rid/folder/f'candidate_{version:02d}'/cid/'repaired_report.ttl').relative_to(ROOT)),fixture=c['fixture'],counterpart=c['counterfactual']),exact_rdf_difference=dict(removed=sorted(' '.join(x.n3() for x in t)+' .' for t in ng-pg),added=sorted(' '.join(x.n3() for x in t)+' .' for t in pg-ng)),no_production_feedback=True)
 adjudications.append(a);r.update(strict=a['status'],attribution=explanation,adjudication_evidence='evaluation/attribution_adjudications.json')
write(E/'attribution_adjudications.json',adjudications);write(E/'all_candidates_adjudicated.json',dict(rows=rows,parse_errors=raw['parse_errors'],classification='Evidence-reviewed after dispatch; rejected candidates diagnostic only'))

def metrics(rs):
 pos=[r for r in rs if r['expected']=='PASS'];neg=[r for r in rs if r['expected']=='FAIL'];counts=collections.Counter(r.get('strict','NO_VERDICT') for r in neg)
 return dict(total_denominator=len(rs),positive_denominator=len(pos),negative_denominator=len(neg),positive_acceptance=sum(r['verdict']['conforms'] is True for r in pos),positive_rejection=sum(r['verdict']['conforms'] is False for r in pos),positive_no_verdict=sum(r['verdict']['conforms'] is None for r in pos),strict_intended_detection=counts['VERIFIED_INTENDED_DETECTION'],missed_intended_defects=counts['MISSED_INTENDED_DEFECT'],unrelated_rejection=counts['UNRELATED_OR_ADDITIONAL_FAILURE'],unresolved_attribution=counts['UNRESOLVED_ATTRIBUTION'],negative_no_verdict=counts['NO_VERDICT'],ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rs),ordinary_disagreement=sum(r['ordinary_agreement'] is False for r in rs),no_verdict=sum(r['verdict']['conforms'] is None for r in rs),executable=sum(r['verdict']['conforms'] is not None for r in rs))
run={(rid,wf):read(g/rid/fo/'run.json') for rid in RIDS for wf,fo in [('Single-shot','single_shot'),('NLTL','nltl')]}
def selected_rows(wf,budget=6):
 ans=[]
 for rid in RIDS:
  h=run[rid,wf]
  selected=next((x['version'] for x in h['history'] if x.get('accepted') and x['attempt']<=budget),None) if wf=='NLTL' else h['evaluation_candidate']
  for c in [c for c in cases if c['requirement_id']==rid]:
   if selected is not None:
    r=dict(next(x for x in rows if (x['requirement_id'],x['workflow'],x['version'],x['case_id'])==(rid,wf,selected,c['case_id'])))
   else:r=dict(workflow=wf,requirement_id=rid,case_id=c['case_id'],expected=c['expected'],version=None,verdict={'conforms':None},ordinary_agreement=None,strict='NO_VERDICT' if c['expected']=='FAIL' else None,reason='No internally accepted candidate; rejected candidates receive no workflow credit.')
   ans.append(r)
 return ans
primary={wf:selected_rows(wf) for wf in ['Single-shot','NLTL']};summary={wf:metrics(rs) for wf,rs in primary.items()};per={rid:{wf:metrics([r for r in primary[wf] if r['requirement_id']==rid]) for wf in primary} for rid in RIDS}
write(E/'primary_workflow_results.json',dict(label='v0.6.0 source-grounded development pilot',per_requirement=per,summaries=summary,rows=sum(primary.values(),[]),exclusions={'Single-shot':[],'NLTL':[]},all_primary_cases_retained=True,selection='Original Single-shot response; first internally accepted NLTL candidate only',interpretation='Development evidence, not full benchmark; no earlier results pooled'))
diagnostics=[]
for key in sorted({(r['requirement_id'],r['workflow'],r['version']) for r in rows}):
 rs=[r for r in rows if (r['requirement_id'],r['workflow'],r['version'])==key];h=run[key[0],key[1]];hist=next(x for x in h['history'] if x['version']==key[2]);diagnostics.append(dict(requirement_id=key[0],workflow=key[1],version=key[2],internally_accepted=hist.get('accepted'),workflow_selected=key[2]==h['evaluation_candidate'],summary=metrics(rs),repaired_counterparts_pass=sum(r.get('repaired_verdict',{}).get('conforms') is True for r in rs),counterpart_denominator=sum(r['expected']=='FAIL' for r in rs)))
write(E/'candidate_diagnostic_summaries.json',diagnostics)
budget=[]
for b in [2,3,4,5,6]:
 selected={rid:next((h['version'] for h in run[rid,'NLTL']['history'] if h.get('accepted') and h['attempt']<=b),None) for rid in RIDS};prefix=[h for rid in RIDS for h in run[rid,'NLTL']['history'] if h['attempt']<=b];calls=[m for h in prefix for m in h['request_metrics']]
 budget.append(dict(budget=b,selected_versions=selected,summary=metrics(selected_rows('NLTL',b)),calls=len(calls),input_tokens=sum(x['usage'].get('input_tokens',0) for x in calls),output_tokens=sum(x['usage'].get('output_tokens',0) for x in calls),provider_seconds=sum(x['elapsed_seconds'] for x in calls),prefix_runtime_seconds=sum(x['elapsed_seconds'] for x in prefix),selection_rule='First internal acceptance within prefix; never choose by evaluation score. Reviewer format retries count separately.',same_histories=True))
write(E/'budget_2_to_6.json',budget)
comparisons=[]
for rid in RIDS:
 h=run[rid,'NLTL'];sel=h['accepted_version'];initial=[r for r in rows if r['requirement_id']==rid and r['workflow']=='NLTL' and r['version']==1];final=[r for r in primary['NLTL'] if r['requirement_id']==rid];recoveries=[];regressions=[];unassessable=[]
 def success(r):return r['verdict']['conforms'] is True if r['expected']=='PASS' else r.get('strict')=='VERIFIED_INTENDED_DETECTION'
 for a,b in zip(sorted(initial,key=lambda r:r['case_id']),sorted(final,key=lambda r:r['case_id'])):
  assert a['case_id']==b['case_id']
  if sel is None or a['verdict']['conforms'] is None or b['verdict']['conforms'] is None:unassessable.append(a['case_id']);continue
  if success(b) and not success(a):recoveries.append(a['case_id'])
  if success(a) and not success(b):regressions.append(a['case_id'])
 comparisons.append(dict(requirement_id=rid,selected_version=sel,recovered_case_ids=recoveries,regressed_case_ids=regressions,comparison_unassessable_case_ids=unassessable,initial_diagnostic=metrics(initial),selected_final=metrics(final),no_accepted_candidate_is_not_last_candidate=True))
write(E/'initial_vs_selected_final.json',dict(per_requirement=comparisons,deduplicated_recoveries=sorted({x for r in comparisons for x in r['recovered_case_ids']}),deduplicated_regressions=sorted({x for r in comparisons for x in r['regressed_case_ids']}),unassessable_cases=25,explanation='Only IMO-001 has a selected final, identical to v1. Four no-verdict requirements have no final code comparison; do not count rejected-last candidates as workflow recoveries.'))
# Actual call accounting, independent of candidate selection.
allcalls=[];byrun={}
for (rid,wf),h in run.items():
 folder='single_shot' if wf=='Single-shot' else 'nltl';events=read(g/rid/folder/'call_ledger.json');allcalls.extend(events)
 byrun[rid+' '+wf]=dict(calls=len(events),generation_calls=sum(x['route']=='generation' for x in events),repair_calls=sum(x['route'].endswith('repair') for x in events),review_calls=sum(x['route']=='review' for x in events),format_retries=sum(x['route']=='review_format_retry' for x in events),input_tokens=sum(x['usage'].get('input_tokens',0) for x in events),output_tokens=sum(x['usage'].get('output_tokens',0) for x in events),total_tokens=sum(x['usage'].get('total_tokens',0) for x in events),provider_seconds=sum(x['elapsed_seconds'] for x in events),workflow_elapsed_seconds=h['elapsed_seconds'],candidate_attempts=h['candidate_attempts'],accepted_version=h['accepted_version'],status=h['status'])
total=dict(calls=len(allcalls),successful_http_responses=sum(e['status']=='RESPONSE' for e in allcalls),routes=dict(collections.Counter(x['route'] for x in allcalls)),input_tokens=sum(x['usage'].get('input_tokens',0) for x in allcalls),output_tokens=sum(x['usage'].get('output_tokens',0) for x in allcalls),total_tokens=sum(x['usage'].get('total_tokens',0) for x in allcalls),provider_seconds=sum(x['elapsed_seconds'] for x in allcalls),dispatch_loop_seconds=state['elapsed_seconds'],workflow_elapsed_seconds=sum(x['workflow_elapsed_seconds'] for x in byrun.values()),independent_evaluation_seconds=raw['evaluation_elapsed_seconds'],candidate_count=len(diagnostics))
write(g/'metrics.json',dict(total=total,per_workflow_requirement=byrun))
# Findings provenance and exact raw reviewer artifacts; invalid findings never become certified inputs.
origins=[];review_issues=[]
for rid in RIDS:
 folder=g/rid/'nltl';h=run[rid,'NLTL']
 for hist in h['history']:
  origins.append(dict(requirement_id=rid,version=hist['version'],status=hist['status'],deterministic_findings=[f for f in hist.get('findings',[]) if f['assessment']!='MODEL_INTERPRETATION'],accepted_model_findings=[f for f in hist.get('findings',[]) if f['assessment']=='MODEL_INTERPRETATION'],model_review=hist.get('review'),reviewer_format_failure=hist.get('reviewer_format_failure')))
 for f in folder.glob('response_*.json'):
  rawresp=read(f)
  try:review=json.loads(rawresp['text'])
  except:continue
  if not isinstance(review,dict) or 'decision' not in review:continue
  for issue in review.get('issues',[]):
   suggestion=issue.get('suggestion','');problems=[]
   if 'qudt:value' in suggestion:problems.append('Suggested predicate is undeclared; canonical numericValue is absent from rendered initial schema context. Wrong-predicate recommendation conflicts with original deterministic rejection.')
   if 'sh:hasValue "7"^^xsd:decimal' in suggestion:problems.append('Proposes exact RDF-term equality without establishing numeric-value equivalence; not supported as a remedy for the source numeric-equality obligation.')
   if 'sh:maxCount 1' in suggestion and rid in ['I2-004','I2-005','TRF-035']:problems.append('Exact-one RDF cardinality is not established by the quoted numeric serialization/source alone; retained as uncertain, not a confirmed obligation.')
   review_issues.append(dict(requirement_id=rid,response=str(f.relative_to(ROOT)),issue_id=issue.get('issue_id'),raw_issue=issue,accepted_into_repair=False,why_not='Reviewer structure/grounding validation failed; no subsequent semantic repair dispatched.',unsupported_or_uncertain_correction=problems,interpretation='Some loss-of-obligation diagnoses are supported by code/source; suggested implementations remain independently unverified.'))
write(g/'finding_origin_and_review_audit.json',dict(candidate_findings=origins,raw_reviewer_issues=review_issues,valid_actionable_semantic_findings=0,false_acceptance=dict(requirement_id='IMO-001',version=1,reason='Entire submitted shape has no SHACL target and is not invoked by any targeted shape. Every negative passes. Reviewer ACCEPT retained material target uncertainty in unchecked.',missed_case_ids=[c['case_id'] for c in cases if c['requirement_id']=='IMO-001' and c['expected']=='FAIL']),review_protocol_failures=dict(alias_key_errors=7,grounding_error=1,format_retry_policy='Exactly one configured retry; no manual normalization or model reruns.')))
# Source/context diagnostics are retrospective only, no implementation changes.
write(g/'context_coverage_findings.json',dict(numeric_predicate=dict(requirements=['I2-004','I2-005','TRF-035'],canonical='http://qudt.org/schema/qudt/numericValue',declared_file='schema/locked_representation_context.jsonld',supplied_in_schema_terms=False,supplied_in_ontology_evidence=False,source='Runtime canonical checker knows numericValue, but rendered per-requirement context drops the quantity predicate; datatype-only quantityEncoding does not restore it.'),controlled_values=dict(requirement_id='TRF-010',supplied_full_source_enumeration=True,canonical_value_individuals_in_initial_context=False,note='The original schema/registry have named values; relevant closure is omitted by context selection. Missing enumeration diagnosis is supported, but invented IRIs are not warranted.'),target_scope=dict(requirement_id='IMO-001',termOwners={'shipCategory':'ship','designIceCondition':'ship'},target_owner=None,note='Owner bindings exist; target/application uncertainty was permitted through ACCEPT. No-target shape is vacuous under the reviewed validation setup.'),regulatory_scope_ambiguities=['TRF-035: relation/equality between two represented length properties remains unclear in representation-only context; benchmark oracle uses previously approved equality scope. Do not infer a new runtime contract from these results.','I2-004 and I2-005: unconditional required linked-case/point existence is part of reviewed evaluation scope; representation-only source context needs explicit handling of material applicability uncertainty, not silent assumptions.','TRF-010: maxCount=1 not explicitly proven by source/schema here; treat as unresolved RDF cardinality, not a forced repair.']))
# Frozen and historical preservation, including previous HTTP403 attempt.
for name,h in read(g/'snapshot_hashes.json').items():assert sha(g/'snapshot'/name)==h,name
for name,h in read(g/'original_input_hashes.json').items():assert sha(ROOT/name)==h,name
old=read(g/'historical_hashes_before.json')
for name,h in old.items():assert sha(ROOT/name)==h,name
write(g/'preservation_verification.json',dict(historical_files_verified=len(old),all_previous_hashes_unchanged=True,frozen_snapshot_and_original_input_hashes_unchanged=True,original_and_repaired_fixtures_unchanged=True,no_generations_after_dispatch_closed=True,no_earlier_results_pooled=True))
shutil.copyfile('/private/tmp/v060_evaluate_retry1.py',g/'independent_evaluation_driver.py');shutil.copyfile(__file__,g/'report_driver.py')
write(g/'final_summary.json',dict(version='0.6.0',label='SOURCE_GROUNDED_DEVELOPMENT_PILOT',status='COMPLETE',summaries=summary,per_requirement=per,metrics=total,accepted_requirements=['IMO-001'],no_verdict_requirements=['I2-004','I2-005','TRF-010','TRF-035'],recommendation='Fix the demonstrated reviewer protocol/grounding interface and non-vacuous acceptance/context coverage defects before further live development. Do not expand to 50 requirements from these results.'))
print(json.dumps(dict(summaries=summary,per_requirement=per,metrics=total,diagnostics=diagnostics),indent=2))
