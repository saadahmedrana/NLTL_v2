from pathlib import Path
import sys,json,copy,hashlib,socket,collections,unittest.mock as mock
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_V0113_CONTRACT_ALIGNMENT';B=R/'outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01';OLD=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION/information_flow_audit_20261124';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION'
sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,GenerationProject,Candidate,Finding,digest,write
from nltlv2.schema import Schema
from nltlv2.runner import Runner
from nltlv2.requests import repair_request,initial_request,parse_review
from nltlv2.review_validation import validate_review
from nltlv2.review_protocol import contract_instructions,reviewer_schema,decision_contract_errors
from nltlv2.evidence import evidence_catalog,wire_catalog
from nltlv2.admission import load_admission
from nltlv2.tracking import Tracker
from nltlv2.token_budget import load_counter,preflight

def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
inputs={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):inputs[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):write(A/n,x)
def provider(request):
 return dict(model=request.get('model','gpt-oss-120b'),input=[dict(role='developer',content=[dict(type='input_text',text=request['system'])]),dict(role='user',content=[dict(type='input_text',text=request['user'])])],max_output_tokens=request.get('max_output_tokens',16000),truncation='disabled',store=False)
def nbytes(x):return len(json.dumps(x,ensure_ascii=False).encode())
manifest=load(B/'manifest.frozen.json');counter=load_counter(R,manifest['token_limits']);rows=[];sizes=[]
# Replay original response bytes with ORIGINAL evidence aliases and request binding.
# Changes to context packing would reorder E IDs; no evidence or response is rewritten.
for old in load(OLD/'all_ten_review_error_crosswalks.json'):
 req=load(Path(old['local_request']));sequence=int(Path(old['local_request']).stem.split('_')[1]);state=load(Path(old['local_request']).parent/f'review_state_{sequence if req["route"]=="review" else sequence-1:03d}.json')
 body=json.loads(req['user']);candidate=Candidate(state['candidate_version'],state['full_candidate'],'');prev=state.get('previous_candidate');previous=Candidate(prev['version'],prev['full_code'],'') if prev else None
 assert digest(candidate.code)==body['candidate_sha256'] and candidate.code==body['full_candidate'];assert state['evidence_catalog']['catalog_sha256']==body['evidence_catalog']['catalog_sha256']
 response=load(Path(old['call']['response_file']));binding={k:body[k] for k in ['candidate_version','candidate_sha256','review_request_id']}
 # Archive-binding adapter is for this offline analysis only. Production validation
 # still recomputes every catalog and binding and permits no injected catalog.
 with mock.patch('nltlv2.review_validation.evidence_catalog',return_value=state['evidence_catalog']),mock.patch('nltlv2.review_validation.review_binding',return_value=binding):
  obj,audit,errors=validate_review(response,candidate,state['context'],state['max_issues'],previous=previous,changes=state['change_manifest'],prior_issues=state['prior_issues'],request_body=state)
 olderrors=old['all_validation_errors'];finger=lambda e:e['code']
 remaining=collections.Counter(finger(e) for e in errors);removed=[]
 for e in olderrors:
  key=finger(e)
  if remaining[key]:remaining[key]-=1
  else:removed.append(e)
 rows.append(dict(requirement=old['requirement'],call=old['call']['call'],route=req['route'],response_file=old['call']['response_file'],response_file_sha256=sha(Path(old['call']['response_file'])),response_text_sha256=digest(response['text']),response_unchanged=True,decision=obj.get('decision') if obj else None,before_errors=olderrors,after_errors=errors,removed_contract_errors=removed,interface_valid=not errors,workflow_credit=0,repair_authorizing=False,outcome='REJECTED_RESPONSE' if errors else 'CONTEXT_PENDING_NOT_ACCEPTANCE_OR_REPAIR',adapter='ORIGINAL_SAVED_CATALOG_AND_BINDING_ONLY; no response metadata/value/content edits; validate current contract against original supplied evidence'))
 # Render current production review using that same full original candidate/context.
 # Size projection, not live replay and not a claim that old IDs fit a new request.
 class Captured(Exception):pass
 capture={};dest=A/'size_projections'/f'call_{old["call"]["call"]:03d}';dest.mkdir(parents=True,exist_ok=True)
 cfg=copy.deepcopy(manifest['config']);runner=Runner(Project(R),cfg,object(),dest);runner.execution_summaries[candidate.version]=state.get('execution_probe')
 def capture_dispatch(request,latest=None):capture.update(request=request);raise Captured()
 runner.dispatch=capture_dispatch
 warnings=[Finding(**{k:v for k,v in f.items() if k!='finding_key'}) for f in state['deterministic_findings']]
 try:runner.review(candidate,state['context'],previous,state['change_manifest'],Tracker(),warnings,prior_override=state['prior_issues'])
 except Captured:pass
 projected=capture['request'];wire=json.loads(projected['user'])
 if req['route']=='review_format_retry':
  feedback=copy.deepcopy(body.get('format_feedback',{}));prior_response=load(Path(old['local_request']).parent/f'response_{sequence-1:03d}.json');feedback.update(rejected_response=prior_response['text'],rejected_response_is_not_prior_state=True);wire['format_feedback']=feedback;projected=dict(projected,route='review_format_retry',user=json.dumps(wire,ensure_ascii=False))
 projected.update(model=manifest['model'],max_output_tokens=manifest['config']['review_max_tokens']);payload=provider(projected);save(str(dest.relative_to(A)/'projected_provider_payload.json'),payload)
 # Isolate dedup effect without contract/correction overhead.
 dedup=copy.deepcopy(load(Path(old['call']['request_file']))['payload']);du=json.loads(dedup['input'][1]['content'][0]['text']);du['evidence_catalog']=wire_catalog(evidence_catalog(state['context']));dedup['input'][1]['content'][0]['text']=json.dumps(du,ensure_ascii=False)
 original=load(Path(old['call']['request_file']))['payload'];sizes.append(dict(requirement=old['requirement'],call=old['call']['call'],route=req['route'],basis='SAME_SAVED_CONTEXT_AND_CODE; newly rendered contract/packing only; correction retains original rejected text once; no workflow credit',before_provider_bytes=old['call']['payload_bytes'],dedup_only_provider_bytes=nbytes(dedup),after_projected_provider_bytes=nbytes(payload),delta=nbytes(payload)-old['call']['payload_bytes'],before_text_tokens=sum(counter(p['text']) for x in original['input'] for p in x['content']),after_capacity=preflight(payload,manifest['token_limits'],counter),projected_payload=str(dest/'projected_provider_payload.json')))
# Existing repair packets, repacked with SAME context/findings/candidate, no dispatched semantic feedback.
for old in load(OLD/'actual_repair_packets_and_diffs.json'):
 d=Path(old['local_request']).parent;req=load(Path(old['local_request']));body=json.loads(req['user']);ctx=load(d/'context.json');c=Candidate(body['candidate_version'],body['previous_candidate'],'');findings=[Finding(**f) for f in load(d/f'findings_{c.version:02d}.json')];pr=repair_request(GenerationProject(R),ctx,c,findings,persistent_summary=body.get('persistent_failure_summary'));pr.update(model='gpt-oss-120b',max_output_tokens=16000);payload=provider(pr);dest=A/'size_projections'/f'call_{old["call"]["call"]:03d}';dest.mkdir(exist_ok=True);write(dest/'projected_provider_payload.json',payload);sizes.append(dict(requirement=old['requirement'],call=old['call']['call'],route=req['route'],basis='SAME_SAVED_CONTEXT_CODE_AND_EXACT_ORIGINAL_DIAGNOSTICS; packing-only offline projection',before_provider_bytes=old['call']['payload_bytes'],after_projected_provider_bytes=nbytes(payload),delta=nbytes(payload)-old['call']['payload_bytes'],after_capacity=preflight(payload,manifest['token_limits'],counter),projected_payload=str(dest/'projected_provider_payload.json')))
save('historical_review_replay.json',rows);save('same_context_packet_sizes.json',sorted(sizes,key=lambda r:r['call']))
# Actual new source selection from unmodified approved resources; no model or fixture access.
project=GenerationProject(R);schema=Schema(project);source_sizes=[]
for rid in manifest['requirements']:
 old=next(x for x in load(OLD/'initial_context_inventory.json') if x['requirement']==rid);cfg=copy.deepcopy(manifest['config']);cfg['admission_file']=manifest['scope_files'][rid];ctx=schema.context(rid);ctx['admission']=load_admission(project,cfg,schema,rid)['context'];ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 sourcebody=''.join(d['text'] for d in ctx['source_documents']);assert any(ctx['requirement']['text'] in d['text'] for d in ctx['source_documents']) or ' '.join(ctx['requirement']['text'].split()) in ' '.join(sourcebody.split())
 initial=initial_request(project,ctx,{k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']});initial.update(model=cfg['model'],max_output_tokens=cfg['generation_max_tokens']);payload=provider(initial);dest=A/'new_initial_packets'/rid;dest.mkdir(parents=True,exist_ok=True);write(dest/'provider_payload.json',payload);write(dest/'source_selection_manifest.json',schema.source_manifests[rid]);write(dest/'context.json',ctx)
 source_sizes.append(dict(requirement=rid,before_provider_bytes=old['provider_call']['payload_bytes'],after_provider_bytes=nbytes(payload),delta=nbytes(payload)-old['provider_call']['payload_bytes'],before_source_characters=old['source_characters'],after_source_characters=sum(len(d['text']) for d in ctx['source_documents']),before_passages=len(old['source_documents']),after_passages=len(ctx['source_documents']),primary_clause_preserved=True,schema_terms_unchanged=ctx['schema_terms']==old['all_schema_terms'],ontology_facts_unchanged=ctx['ontology_evidence']==old['all_supplied_ontology_facts'],quantity_encoding_unchanged=ctx['quantityEncoding']==old['quantity_encoding'],scope_unchanged=ctx['admission']==old['approved_scope'],capacity=preflight(payload,manifest['token_limits'],counter),packet=str(dest/'provider_payload.json')))
save('initial_context_size_changes.json',source_sizes)
# Prepared one-requirement fresh shared-start diagnostic. No seeded shapes/issues/solutions.
m=copy.deepcopy(manifest);cfg=m['config'];cfg.update(maximum_candidate_attempts=3,pipeline_version='0.11.3',repair_limits=dict(technical=1,semantic=1,total=2));cfg['continuation']['max_provider_calls']=11
m.update(pipeline_version='0.11.3',dispatch_ready=False,prepared_only=True,requirements=['IMO-001'],scope_files={'IMO-001':manifest['scope_files']['IMO-001']},max_physical_calls=11,max_total_provider_HTTP_calls_including_metadata=11,max_reserved_output_tokens=176000,max_execution_seconds=600,start_requirement_reserve_seconds=540,freeze_lock=str((A/'freeze_lock.json').relative_to(R)),diagnostic_label='FRESH_SHARED_START_SEMANTIC_REPAIR_OPPORTUNITY_NOT_PERFORMANCE_STUDY',prior_exposure={'IMO-001':'Used in v0.11.2 main and hosted smoke; selected here from audit to exercise corrected review handoff, not held out'},repair_exercise_policy='No seeded shape, prior issue or regulatory solution. Early acceptance allowed; untriggered semantic repair must be reported NOT_EXERCISED. No regeneration or preferred-result rerun.',approval_required='Prepared, undispatched. No model-call authorization supplied by this offline implementation task. Reverify freeze and obtain explicit diagnostic dispatch authorization.',initial_prior_issues=[],no_evaluation_resources_in_model_context=True)
# Evaluation lock remains the unchanged historical evaluation-resource lock; no evaluation invoked.
m['authorization']='OFFLINE_PREPARATION_ONLY_NOT_AUTHORIZED_FOR_DISPATCH'
m['readiness_criterion']='Final offline software controls pass and source/schema/scope resolve; no new live operational or accuracy claim.'
m['selection_basis']='One previously exposed source-ready requirement, chosen for an audit-informed handoff diagnostic; not held out and not selected by evaluation score.'
for key in ['planned_case_denominators','fixed_requirement_queue_seed','main_results_separate_from_smoke']:m.pop(key,None)
m['results_separate_from_all_previous_runs']=True
save('semantic_repair_diagnostic.prepared.json',m)
save('evaluation_plan.not_model_input.json',dict(label='FUTURE_INDEPENDENT_EVALUATION_ONLY_AFTER_DISPATCH_CLOSURE',requirement='IMO-001',original_cases_per_arm=5,counterparts_per_arm=3,basis='Counts from unchanged saved v0.11.2 result inventory, not a rerun',evaluation_resources_lock=manifest['evaluation_lock'],candidate_shapes_unchanged=True,equal_denominators=True,production_inputs=False))
save('replay_input_hashes.json',inputs)
print(json.dumps(dict(replayed=len(rows),original_errors=sum(len(r['before_errors']) for r in rows),remaining_errors=sum(len(r['after_errors']) for r in rows),valid_context_pending_calls=[r['call'] for r in rows if r['interface_valid']],size_projections=len(sizes),initial_sizes=source_sizes,model_calls=0,evaluation_reruns=0),indent=2))
