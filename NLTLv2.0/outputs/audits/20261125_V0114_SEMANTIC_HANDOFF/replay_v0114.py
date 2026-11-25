from pathlib import Path
import sys,json,copy,hashlib,collections,socket
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0114_SEMANTIC_HANDOFF';B=R/'outputs/experiments/20261125_V0113_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,Candidate,Finding,write
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.review_validation import validate_compact_review
from nltlv2.review_protocol import reviewer_schema
from nltlv2.token_budget import load_counter,preflight

def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
inputs={}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):inputs[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):write(A/n,x)
m=load(B/'manifest.frozen.json');counter=load_counter(R,m['token_limits']);rows=[];sizes=[]
for n in [2,3,4]:
 actual=load(B/'provider'/f'call_{n:03d}_request.json');body=json.loads(actual['payload']['input'][1]['content'][0]['text']);state=load(B/'IMO-001/NLTL'/f'review_state_{1 if n==2 else 2:03d}.json');response=load(B/'provider'/f'call_{n:03d}_response.json');old=json.loads(response['text']);c=Candidate(body['candidate_version'],body['full_candidate'],'');ctx=state['context'];prior=state['prior_issues'];changes=state['change_manifest']
 raw_errors=validate_compact_review(response,c,ctx,previous=None,changes=changes,prior_issues=prior,request_body=state)[2]
 # Mechanical interface projection: keep issue descriptions, corrections, all
 # asserted quotes, locations, proposed operands and material uncertainty intact.
 projected=dict(assessment={'ACCEPT':'APPROVE','UNRESOLVED':'HUMAN_REVIEW_REQUIRED','REQUEST_EVIDENCE':'HUMAN_REVIEW_REQUIRED','REJECT':'REJECT'}[old['decision']],issues=[],questions=[])
 for x in old['issues']:
  refs=[]
  for idkey,quotekey in [('source_evidence_id','source_excerpt'),('evidence_id','evidence_excerpt')]:
   if x.get(idkey) is not None:
    r={'id':x[idkey]}
    if x.get(quotekey) is not None:r['quote']=x[quotekey]
    refs.append(r)
  extra=[r for r in old.get('reconciliations',[]) if r.get('issue_id')==x.get('issue_id')]
  for r in extra:
   for ik,qk in [('source_evidence_id','source_excerpt'),('evidence_id','evidence_excerpt')]:
    if r.get(ik) is not None and r.get(qk) is not None:
     citation=dict(id=r[ik],quote=r[qk])
     if citation not in refs:refs.append(citation)
  description=x['reason']+'\nExpected: '+x['expected']+''.join('\nPrior-issue assessment: '+r['reason'] for r in extra)
  y=dict(description=description,evidence=refs,location={k:v for k,v in x['candidate_location'].items() if k in ['start','end','unit']},suggestion=x['suggestion'])
  if x.get('proposed_path') is not None:
   y['operands']=[dict(property=x['property'],path=x['proposed_path'],role=x.get('proposed_path_role') or 'PROPERTY',**{b:x[a] for a,b in [('proposed_unit','unit'),('proposed_datatype','datatype')] if x.get(a) is not None})]
  projected['issues'].append(y)
 for u in old.get('unchecked',[]):
  if u.get('material'):projected['questions'].append(dict(missing=u['scope'],why=u['reason'],kind='schema'))
 # Original evidence requests, if any, are not fabricated into code findings.
 for q in old.get('evidence_requests',[]):projected['questions'].append(dict(missing=q['query'],why=q['reason'],kind=q['kind'],**{k:q[k] for k in ['reference','section'] if q.get(k) is not None}))
 current,audit,errors=validate_compact_review(dict(text=json.dumps(projected)),c,ctx,previous=None,changes=changes,prior_issues=prior,request_body=state)
 fail=B/'IMO-001/NLTL'/f'reviewer_format_failure_{n-1:03d}.json';before=load(fail)['validation_errors'] if fail.exists() else []
 rows.append(dict(provider_call=n,actual_request=str(B/'provider'/f'call_{n:03d}_request.body'),actual_response=str(B/'provider'/f'call_{n:03d}_response.json'),actual_response_sha256=sha(B/'provider'/f'call_{n:03d}_response.json'),raw_unchanged_compatibility_errors=raw_errors,original_validation_errors=before,projection_label='INTERFACE_ONLY_SOFTWARE_PROJECTION_ZERO_WORKFLOW_CREDIT',projection=projected,projection_errors=errors,substantive_descriptions_preserved=all(p['description'].startswith(o['reason']) and o['expected'] in p['description'] for p,o in zip(projected['issues'],old['issues'])),suggested_corrections_unchanged=[x['suggestion'] for x in projected['issues']]==[x['suggestion'] for x in old['issues']],asserted_quotes_preserved=True,bookkeeping_removed='Candidate echoes, clause/category/claim-basis echoes and duplicate reconciliation/removal metadata, not model claim text',routing_choice_for_old_material_unchecked='schema kind added solely to project the representation-mapping question onto bounded retrieval; never a new model result',context_pending=bool(projected['questions']),repair_authorizing=False,workflow_credit=0))
 class Capture(Exception):pass
 captured={};dest=A/'size_projections'/f'call_{n:03d}';dest.mkdir(parents=True,exist_ok=True);cfg=copy.deepcopy(m['config']);cfg.update(review_contract_version=4,pipeline_version='0.11.4');runner=Runner(Project(R),cfg,object(),dest);runner.execution_summaries[c.version]=state['execution_probe']
 def capture(q,latest=None):captured['request']=q;raise Capture()
 runner.dispatch=capture
 fs=[Finding(**{k:v for k,v in f.items() if k!='finding_key'}) for f in state['deterministic_findings']]
 try:runner.review(c,ctx,None,changes,Tracker(),fs,prior_override=prior)
 except Capture:pass
 q=captured['request'];wire=json.loads(q['user'])
 if n==4:
  wire['format_feedback']=dict(rejected_response=json.dumps(rows[1]['projection']),validation_errors=rows[1]['projection_errors'],failed_review_is_not_prior_state=True,shared_response_correction_allowance=True,instruction='Return one complete corrected response, unchanged candidate/evidence/original prior state. No rejected issue authorizes repair.')
 payload=copy.deepcopy(actual['payload']);payload['input'][0]['content'][0]['text']=q['system'];payload['input'][1]['content'][0]['text']=json.dumps(wire,ensure_ascii=False)
 write(dest/'projected_provider_payload.json',payload);size=len(json.dumps(payload,ensure_ascii=False).encode());sizes.append(dict(call=n,route=actual['route'],basis='SAME_SAVED_CANDIDATE_CONTEXT_PRIOR; new interface/packing only, zero workflow credit',before_bytes=(B/'provider'/f'call_{n:03d}_request.body').stat().st_size,after_projected_bytes=size,before_schema_bytes=len(json.dumps(body['expected_response_schema']).encode()),after_schema_bytes=len(json.dumps(wire['expected_response_schema']).encode()),capacity=preflight(payload,m['token_limits'],counter),projected_packet=str(dest/'projected_provider_payload.json')))
save('latest_response_replay.json',rows);save('request_size_projection.json',sizes);save('replay_input_hashes.json',inputs)
prepared=copy.deepcopy(m);cfg=prepared['config'];cfg.update(pipeline_version='0.11.4',review_contract_version=4);prepared.update(pipeline_version='0.11.4',dispatch_ready=False,prepared_only=True,authorization='PREPARATION_ONLY_NO_AUTHORIZATION_OR_DISPATCH',approval_required='Await explicit authorization for this prepared diagnostic; current task is offline only.',freeze_lock=str((A/'freeze_lock.json').relative_to(R)),diagnostic_label='FRESH_SINGLE_REQUIREMENT_SHARED_START_SEMANTIC_HANDOFF_DEVELOPMENT_DIAGNOSTIC',requirements=['IMO-001'],initial_prior_issues=[],prior_exposure={'IMO-001':'Previously exposed in hosted diagnostics/main run; not held out. No previous candidate, review or solution imported.'},selection_basis='Previously approved, source/schema/scope-ready single-requirement handoff diagnostic; not a new batch and not selected by external score.',repair_exercise_policy='Fresh one-call shared generation. No forced code issue/repair; early approval or genuine context-pending is a result. No regeneration/manual edits/preferred-result rerun.',results_separate_from_all_previous_runs=True)
for k in ['planned_case_denominators','fixed_requirement_queue_seed','main_results_separate_from_smoke']:prepared.pop(k,None)
save('semantic_repair_diagnostic.prepared.json',prepared)
save('evaluation_plan.not_model_input.json',dict(requirement='IMO-001',original_cases_per_arm=5,counterparts_per_arm=3,policy='Existing independent evaluator only after verified dispatch closure, unchanged cases/shapes, separate approval/scope/delivered behavior/strict attribution; never selection by score.',evaluation_lock=m['evaluation_lock'],production_input=False))
print(json.dumps(dict(replays=[dict(call=r['provider_call'],original_errors=len(r['original_validation_errors']),projected_errors=[e['code'] for e in r['projection_errors']],raw_compatible=not r['raw_unchanged_compatibility_errors']) for r in rows],sizes=sizes,model_calls=0),indent=2))
