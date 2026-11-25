from pathlib import Path
import sys,json,hashlib,copy,collections,difflib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_IDENTIFIER_ROUTING_AND_20_10_READINESS';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Project,Candidate,write
from nltlv2.schema import Schema
from nltlv2.requests import review_proposal_routing,initial_request
from nltlv2.review_validation import validate_review
from nltlv2.admission import load_admission
from nltlv2.hosted_pilot import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text());save=lambda n,x:write(A/n,x)
verification=load(A/'verification.json');assert verification['success'] and verification['tests']==311
# Historical raw response replay is an identity check only; no workflow or semantic credit.
G=R/'outputs/experiments/20261125_V0115_TRF035_FROZEN_REVIEW_COMPARISON_01';oldstate=load(R/'outputs/experiments/20261125_V0115_V2_TRF035_INTERFACE_CLARITY_DIAGNOSTIC_01/TRF-035/NLTL/review_state_001.json');c=Candidate(oldstate['candidate_version'],oldstate['full_candidate'],'');response=load(G/'provider/call_002_response.json');obj,audit,errors=validate_review(response,c,oldstate['context'],request_body=oldstate);assert not errors;unchanged=copy.deepcopy(obj);schema=Schema(Project(R));route=review_proposal_routing(obj,schema,'TRF-035',oldstate['context'],candidate=c);assert obj==unchanged and route['route']=='VALID'
save('routing_identity_replay.json',dict(label='OFFLINE_IDENTITY_ONLY_NO_WORKFLOW_OR_SEMANTIC_CREDIT',historical_raw_response_sha256=sha(G/'provider/call_002_response.body'),historical_outcome='REVIEWER_RESPONSE_PROTOCOL_FAILURE_UNCHANGED',prospective_route=route,model_claims_changed=False,interpretation_supported_by_fix=False,production_acceptance_granted=False))
# Queue selection uses SOURCE + REPRESENTATION only. No cases, labels, generated outputs or scores enter selection.
seed='NLTL_20_GPTOSS_10_GPT55_SOURCE_SCHEMA_QUEUE_20261125_V1';rank=lambda rid:hashlib.sha256((seed+'|'+rid).encode()).hexdigest();anchors=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'];groups={};excluded=[]
for rid,rec in schema.requirements.items():
 if rid in anchors or rid=='I2-042':continue
 binding=schema.bindings.get(rid,{});root,paths=schema.allowed_paths(rid)
 if not root or not binding.get('owners') or not all(paths.get('https://w3id.org/nltl/vocab#'+prop) for prop in binding['owners']):continue
 source=schema.catalog.get(rec.get('source'))
 if not source or not (R/source['file']).is_file() or sha(R/source['file'])!=source.get('sha256'):continue
 groups.setdefault(rec['source'],[]).append(rid)
for source in groups:groups[source].sort(key=rank)
order=sorted(groups,key=lambda source:hashlib.sha256((seed+'|'+source).encode()).hexdigest());selected=anchors.copy()
while len(selected)<20:
 added=False
 for source in order:
  if groups[source]:selected.append(groups[source].pop(0));added=True
  if len(selected)==20:break
 if not added:raise ValueError('INSUFFICIENT_SOURCE_SCHEMA_CANDIDATE_POOL')
# Exact 10 overlap: anchors + first new candidate from each source, then seeded fill.
overlap=anchors.copy();seen=set(schema.requirements[rid]['source'] for rid in [])
for rid in selected[5:]:
 source=schema.requirements[rid]['source']
 if source not in seen:overlap.append(rid);seen.add(source)
for rid in sorted(selected[5:],key=rank):
 if len(overlap)>=10:break
 if rid not in overlap:overlap.append(rid)
overlap=overlap[:10];assert len(set(selected))==20 and len(set(overlap))==10 and set(overlap)<=set(selected)
save('source_schema_selection.freeze.json',dict(seed=seed,selection_method='Five prior-exposed anchors retained for accounting; remaining 15 source-stratified deterministic hash order among existing explicit-owner/path candidates. Ten overlap include anchors plus source-diverse seeded entries. No evaluation/performance consulted.',GPT_OSS_20=selected,GPT_55_10=overlap,source_groups=order,requirements_held_out=False,prior_exposure='Existing development corpus; anchors known exposed. Other per-model prior exposure not fully catalogued, never claimed held out.',deferred={'I2-042':'Previously deferred; not added or substituted.'}))
# Now inspect evaluation availability separately, AFTER queue frozen. Do not load generated scores.
core=load(R/'evaluation/selections/regression_core.json')['cases'];scopebinding=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json')['evaluation']['bindings'];evalreqs={r['requirement_id'] for r in core};rows=[];sourcefiles=set()
for rid in selected:
 record=schema.requirements[rid];context=schema.context(rid);scope='data/admissions/'+rid.lower().replace('-','_')+'_research_scope.approved.json';scopeexists=(R/scope).is_file();ad=None
 if scopeexists:
  cfg=load(R/'configs/nltl.json');cfg['admission_file']=scope;ad=load_admission(Project(R),cfg,schema,rid);assert ad['valid']
 cases=[case for case in core if case['requirement_id']==rid];files_available=bool(cases) and all((R/case['fixture']).is_file() and (not case.get('counterfactual') or (R/case['counterfactual']).is_file()) for case in cases);bindingready=bool(cases) and all(case['case_id'] in scopebinding for case in cases)
 blockers=[]
 if not scopeexists:blockers.append(dict(code='APPROVED_RESEARCH_SCOPE_MISSING',required_file=scope,detail='Need explicit external population/edition assumptions and representation responsibilities; existing I2-004/five-requirement approval is not transferable.'))
 if rid=='IMO-001':blockers.append(dict(code='DESIGN_INTENT_REPRESENTATION_UNRESOLVED',detail='Designed-for-polar-waters is not established equivalent to the actual-operation Boolean; no scope strengthening or solution supplied.'))
 if not files_available:blockers.append(dict(code='UNCHANGED_BUNDLED_CASES_COUNTERPARTS_MISSING',detail='No bundled original independent cases/counterparts for this selected requirement. Historical case inventory or labels alone is insufficient.'))
 if not bindingready:blockers.append(dict(code='EVALUATION_INPUT_SCOPE_PROVENANCE_MISSING',detail='No approved construction/admission bindings for this selected requirement. Do not infer admission from labels or model behavior.'))
 root,paths=schema.allowed_paths(rid)
 sourcefiles.update(doc['file'] for doc in context['source_documents'])
 rows.append(dict(requirement_id=rid,GPT_OSS=True,GPT_55=rid in overlap,source=record['source'],clause=record['clause'],source_schema_structural_readiness='RETAINED_SOURCE_AND_EXPLICIT_PATHS_AVAILABLE_NOT_FULL_REGULATORY_CERTIFICATION',target_owner=root,declared_paths=paths,scope_status='APPROVED_UNCHANGED' if scopeexists else 'MISSING_APPROVAL',scope_file=scope if scopeexists else None,scope_sha256=sha(R/scope) if scopeexists else None,source_documents=[dict(file=doc['file'],sha256=sha(R/doc['file'])) for doc in context['source_documents']],unresolved_source_reference_count=len(context.get('unresolvedSourceContext',[])),cases=len(cases),counterparts=sum(bool(case.get('counterfactual')) for case in cases),evaluation_support='EXISTING_ORIGINAL_CASES_AND_BINDINGS' if files_available and bindingready else 'BLOCKED',status='BLOCKED' if blockers else 'READY_WITHIN_APPROVED_SYNTHETIC_SCOPE',blockers=blockers))
save('requirement_readiness.json',rows)
# Freeze exactly the tested pipeline; never overwrite any earlier lock.
old=load(R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/interface_clarity/next_test_readiness/current_tested_snapshot.json');names=set(old['files'])|{str(p.relative_to(R)) for p in (R/'src/nltlv2').glob('*.py')}|sourcefiles|{'tests/test_identifier_identity_routing.py'}
lock=dict(snapshot_id='V0115_IDENTIFIER_IDENTITY_ROUTING_20261125_TESTED_311',version='0.11.5',tests=311,scope_of_change='Identifier identity comparison only; production prompts/acceptance/model settings unchanged; no coverage prompt adoption.',files={n:sha(R/n) for n in sorted(names)})
save('pipeline.freeze.json',lock);verify(R,lock)
endpoint=load(A/'gpt55_endpoint_verification.json');assert endpoint['model_inference_calls']==0
transport=(R/'src/nltlv2/transport.py').read_text();assert "HOSTED_MODEL='gpt-oss-120b'" in transport and "if request['model']!=HOSTED_MODEL" in transport
ready=[r['requirement_id'] for r in rows if not r['blockers']];new=[r['requirement_id'] for r in rows if r['scope_status']=='MISSING_APPROVAL'];missing_eval=[r['requirement_id'] for r in rows if r['evaluation_support']=='BLOCKED']
plan=dict(label='BROADER_20_GPTOSS_10_OVERLAPPING_GPT55_SHARED_START_DEVELOPMENT_PLAN',dispatch_ready=False,status='BLOCKED_ALL_BLOCKERS_REPORTED_NO_LAUNCH_COMMAND',pipeline_freeze='outputs/audits/20261125_IDENTIFIER_ROUTING_AND_20_10_READINESS/pipeline.freeze.json',selection_seed=seed,models=[dict(requested_model='gpt-oss-120b',requirements=selected,count=20,established_responses_endpoint='https://ai-api-v2.aalto.fi/v1/responses'),dict(advertised_provider_model_id='gpt-5.5-2026-04-24',requirements=overlap,count=10,advertised_on='https://ai-api-v2.aalto.fi/v1/models',candidate_responses_endpoint='https://ai-api-v2.aalto.fi/v1/responses',responses_execution_verified=False,production_adapter_support=False)],design=dict(within_each_model='Generate once per requirement; preserve exact output as Single-shot and refine exact same bytes in NLTL. No shared candidate across different models.',overlap='Exactly the declared ten IDs and same independent cases/denominators across models; freeze data/scopes before dispatch.',source_prompts='Current frozen generator/reviewer/repair; NO B coverage addition or comparison-only coverage schema.',selection='Latest technically qualifying candidate under existing delivery policy; approval separate; no external-score selection.',unstarted='NOT_RUN retained in denominators/accounting; no automatic substitution or requirement-specific fixing.',evaluation='Independent only after dispatch closure for each model run; no fixtures/labels/solutions in production.'),limits=dict(per_requirement_model_pair=dict(initial_generations=1,technical_repairs=1,semantic_repairs=1,total_revisions=2,distinct_candidates=3,primary_reviews_total=4,primary_per_candidate=3,shared_corrections_per_review=1,retrieval_rounds=2,max_provider_HTTP_calls=11,output_tokens_per_request=16000,max_reserved_output_tokens=176000,workflow_seconds=600,request_timeout_seconds=180),GPT_OSS_20=dict(provider_HTTP_calls=220,output_token_reservation=3520000,workflow_ceiling_seconds=12000),GPT_55_10=dict(provider_HTTP_calls=110,output_token_reservation=1760000,workflow_ceiling_seconds=6000),overall=dict(model_requirement_pairs=30,provider_HTTP_calls=330,output_token_reservation=5280000,distinct_candidates=90,workflow_ceiling_seconds=18000),time_stopping='Existing reserve policy: do not start another requirement without sufficient remaining allocation (currently 540-second start reserve); unstarted requirements NOT_RUN. Proposed aggregate ceilings are conservative limits, not a runtime forecast.'),blockers=[dict(code='FIFTEEN_APPROVED_SCOPES_MISSING',requirements=new),dict(code='IMO001_REPRESENTATION_BLOCKER_RETAINED',requirements=['IMO-001']),dict(code='FIFTEEN_INDEPENDENT_EVALUATION_SETS_AND_PROVENANCE_MISSING',requirements=missing_eval,details='Current regression_core bundles 37 cases across only six requirements; I2-042 deferred, leaving the prior five available. Only prior five have approved evaluation bindings.'),dict(code='GPT55_PRODUCTION_TRANSPORT_NOT_SUPPORTED',details='HostedResponsesTransport hard-restricts requests to GPT-OSS; generic LiveTransport is an older endpoint/protocol path, not a verified substitute. No adapter changes beyond authorized routing fix performed.'),dict(code='GPT55_RESPONSES_IDENTITY_AND_CAPACITY_UNVERIFIED',details='Metadata GET advertised gpt-5.5-2026-04-24, but did not demonstrate Responses access/backend identity/context/output limits/tokenizer. Public OpenAI snapshot is gpt-5.5-2026-04-23; do not silently replace or equate provider aliases. No inference probe performed.'),dict(code='BROADER_EVALUATOR_NOT_IMPLEMENTED_FOR_NEW_REQUIREMENTS',details='Existing independent oracle/reference controls and scope binding route cover the bundled regression set, not the additional fifteen. Cases and independent source-backed oracle/construction review are required; no answer-bearing controls enter production.')],counts=dict(ready_source_scope_eval=ready,ready_count=len(ready),blocked_count=20-len(ready),approved_scope_missing_count=len(new),independent_eval_missing_count=len(missing_eval)),metadata_verification=endpoint,not_dispatched=True)
save('broader_experiment.blocked.json',plan)
# Prompt and protected-artifact identity proof.
protected=load(A/'protected_before.json');changed=[n for n,h in protected.items() if sha(R/n)!=h];assert not changed,changed[:10]
assert sha(R/'prompts/reviewer.txt')==old['files']['prompts/reviewer.txt'];assert sha(R/'prompts/generator.txt')==old['files']['prompts/generator.txt'];assert sha(R/'prompts/repair.txt')==old['files']['prompts/repair.txt']
diff=[]
for n in ['src/nltlv2/requests.py','src/nltlv2/runner.py']:
 diff+=list(difflib.unified_diff((A/'before'/n).read_text().splitlines(True),(R/n).read_text().splitlines(True),fromfile='before/'+n,tofile='current/'+n))
(A/'implementation.diff').write_text(''.join(diff));save('preservation_verification.json',dict(protected_files=len(protected),changed_protected_files=changed,production_prompts_unchanged=True,scope_schema_tracker_ledger_historical_candidates_decisions_scores_unchanged=True,inference_calls=0,metadata_HTTP_calls=endpoint.get('metadata_HTTP_calls',0),evaluation_reruns=0))
for n in ['fix_identifier_routing.py','test_identifier_routing_patch.py','verify_identifier_routing.py','verify_aalto_gpt55_metadata.py','prepare_20_10_readiness.py']:shutil.copyfile('/tmp/'+n,A/n)
print(json.dumps(dict(selected_20=selected,overlap_10=overlap,ready=ready,scope_missing=len(new),eval_missing=len(missing_eval),pipeline_snapshot=lock['snapshot_id'],model_inference_calls=0,metadata_HTTP_calls=1),indent=2))
