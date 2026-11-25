from pathlib import Path
import sys,json,copy,hashlib,socket
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS';B=R/'outputs/experiments/20261125_V0114_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,Candidate,Finding,write
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.context_resolution import remember_question_review,unresolved_questions,record_question_retrieval
from nltlv2.review_validation import validate_review
from nltlv2.token_budget import load_counter,preflight

def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
inputs={};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):inputs[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):write(A/n,x)
m=load(B/'manifest.frozen.json');counter=load_counter(R,m['token_limits']);retrieval=load(B/'IMO-001/NLTL/retrieval_ledger.json');ledger={};rows=[];packets=[]
for n in [3,4,5]:
 oldstate=load(B/'IMO-001/NLTL'/f'review_state_{n-1:03d}.json');response=load(B/'provider'/f'call_{n:03d}_response.json');c=Candidate(oldstate['candidate_version'],oldstate['full_candidate'],'');p=oldstate.get('previous_candidate');prev=Candidate(p['version'],p['full_code'],'') if p else None;ctx=oldstate['context'];assert c.sha256==oldstate['candidate_sha256']
 dest=A/'followup_packets'/f'call_{n:03d}';dest.mkdir(parents=True,exist_ok=True);cfg=copy.deepcopy(m['config']);cfg['pipeline_version']='0.11.5';r=Runner(Project(R),cfg,object(),dest);r.context_questions=copy.deepcopy(ledger);r.execution_summaries[c.version]=oldstate['execution_probe'];capture={}
 class Capture(Exception):pass
 def dispatch(request,latest=None):capture['request']=request;raise Capture()
 r.dispatch=dispatch
 warnings=[Finding(**{k:v for k,v in f.items() if k!='finding_key'}) for f in oldstate['deterministic_findings']]
 try:r.review(c,ctx,prev,oldstate['change_manifest'],Tracker(),warnings,prior_override=oldstate['prior_issues'])
 except Capture:pass
 request=capture['request'];state=load(dest/'review_state_001.json');wire=json.loads(request['user']);obj,audit,errors=validate_review(response,c,ctx,previous=prev,changes=oldstate['change_manifest'],prior_issues=oldstate['prior_issues'],request_body=state)
 oldrequest=load(B/'provider'/f'call_{n:03d}_request.json');payload=copy.deepcopy(oldrequest['payload']);payload['input'][0]['content'][0]['text']=request['system'];payload['input'][1]['content'][0]['text']=request['user'];write(dest/'provider_payload.not_dispatched.json',payload)
 rows.append(dict(actual_provider_call=n,classification='PROSPECTIVE_SOFTWARE_REPLAY_NO_WORKFLOW_OR_SCORE_CREDIT',actual_response_file=str(B/'provider'/f'call_{n:03d}_response.json'),actual_response_sha256=sha(B/'provider'/f'call_{n:03d}_response.json'),response_values_unchanged=True,assessment=json.loads(response['text'])['assessment'],prior_material_questions=[dict(id=q['id'],missing=q['missing'],why=q['why'],evidence=q['supporting_evidence'],attempts=q['retrieval_attempts']) for q in wire['prior_context_questions']],validation_errors=errors,current_contract_valid=not errors,current_internal_approval=False,workflow_credit=0,sequence_caveat='New controller would require correction/stop at call 4. Call 5 is separately checked against both historically validated questions, not claimed dispatched in a new workflow.'))
 packets.append(dict(call=n,request=request,provider_payload=payload,internal_state=state,candidate_sha256=c.sha256,prior_question_count=len(wire['prior_context_questions']),capacity=preflight(payload,m['token_limits'],counter)))
 if n==3:
  assert not errors;ledger=remember_question_review(ledger,obj,c,dict(original_provider_call=n,request_id=oldstate['review_request_id']),oldstate['evidence_catalog']);ledger=record_question_retrieval(ledger,retrieval[0],str(B/'IMO-001/NLTL/retrieval_ledger.json')+'#/0')
 if n==4:
  assert errors and any(e['path']=='$.question_review' for e in errors)
  # Import only the ORIGINAL validated historical event for sequence reconstruction.
  # This is not accepting this response under the corrected controller or closing Q1.
  historical=load(B/'IMO-001/NLTL/review_validated_003.json')['review'];assert 'prior_context_questions' not in historical
  for q,rawq in zip(historical['questions'],json.loads(response['text'])['questions']):
   for field in ['kind','reference','section']:q[field]=rawq.get(field)
  # Interface-only metadata restoration from the same exact raw response; claims unchanged.
  ledger=remember_question_review(ledger,historical,c,dict(original_provider_call=n,request_id=oldstate['review_request_id'],label='HISTORICAL_VALIDATED_EVENT_IMPORT_ONLY_NOT_CURRENT_ACCEPTANCE'),oldstate['evidence_catalog']);ledger=record_question_retrieval(ledger,retrieval[1],str(B/'IMO-001/NLTL/retrieval_ledger.json')+'#/1')
assert [len(r['prior_material_questions']) for r in rows]==[0,1,2];assert not rows[0]['validation_errors'] and rows[1]['validation_errors'] and rows[2]['validation_errors'];assert all(q['status']=='STILL_UNRESOLVED' for q in ledger.values());assert load(B/'IMO-001/NLTL/run.json')['status']=='ACCEPTED'
save('exact_saved_sequence_replay.json',rows);save('historically_validated_question_event_ledger.json',ledger);save('complete_followup_packet.json',dict(label='OFFLINE_COMPLETE_FOLLOWUP_RENDERING_NOT_DISPATCHED_NO_WORKFLOW_CREDIT',actual_saved_candidate_unchanged=True,originating_actual_provider_call=4,**packets[1],question_provenance_ledger_before_second_historical_question={k:v for k,v in ledger.items() if v['id']=='Q1'}))
save('packet_capacity.json',[dict(call=p['call'],prior_question_count=p['prior_question_count'],capacity=p['capacity']) for p in packets]);save('replay_input_hashes.json',inputs)
# Fresh prepared diagnostic: no old candidate, question, diagnosis or solution is seeded.
prepared=copy.deepcopy(load(R/'outputs/audits/20261125_V0114_SEMANTIC_HANDOFF/semantic_repair_diagnostic.prepared.json'));prepared.update(pipeline_version='0.11.5',dispatch_ready=False,prepared_only=True,authorization='OFFLINE_PREPARATION_ONLY_NO_MODEL_DISPATCH_AUTHORIZATION',approval_required='New explicit authorization required; this task permits offline preparation only.',freeze_lock=str((A/'freeze_lock.json').relative_to(R)),initial_context_questions=[],question_carryforward_policy='Persist actual validated material questions generated in this NEW run; require supported explicit disposition before approval. Do not seed historical questions.',exercise_policy='No forced question, semantic issue, repair or approval. Report unexercised branches NOT_EXERCISED; no preferred-result rerun.',diagnostic_label='FRESH_SINGLE_REQUIREMENT_CONTEXT_QUESTION_CARRYFORWARD_DEVELOPMENT_DIAGNOSTIC');prepared['config']['pipeline_version']='0.11.5';save('diagnostic.prepared.json',prepared)
print(json.dumps(dict(replay=[dict(call=r['actual_provider_call'],prior_question_count=len(r['prior_material_questions']),errors=[e['code'] for e in r['validation_errors']],assessment=r['assessment']) for r in rows],questions=[dict(id=q['id'],missing=q['missing'],status=q['status']) for q in ledger.values()],old_result_unchanged='ACCEPTED',model_calls=0),indent=2))
