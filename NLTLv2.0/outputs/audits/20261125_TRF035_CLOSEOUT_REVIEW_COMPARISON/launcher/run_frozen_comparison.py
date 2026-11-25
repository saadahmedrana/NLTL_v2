"""Standalone frozen reviewer comparison. No generation, repair or production edits."""
from pathlib import Path
import argparse,copy,datetime,hashlib,json,os,socket,sys,time
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
A=R/'outputs/audits/20261125_TRF035_CLOSEOUT_REVIEW_COMPARISON'
D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION'
sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Candidate,Project,write
from nltlv2.evidence import assert_review_packet,citation_error,code_location,extract_location
from nltlv2.hosted_pilot import verify
from nltlv2.review_protocol import contract_shape_errors,normalize_response,response_correction_instruction,ReviewerFormatError
from nltlv2.review_validation import validate_review
from nltlv2.requests import review_proposal_routing
from nltlv2.schema import Schema
from nltlv2.token_budget import load_counter,preflight
from nltlv2.transport import HostedResponsesTransport,provider_payload

def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def failure(code,path,expected,observed=None,category='MALFORMED_STRUCTURE'):return dict(code=code,path=path,expected=expected,observed=observed,category=category)

def coverage_errors(raw,wire,c,required):
 errors=[];items=raw.get('coverage')
 if items is None:return [failure('MISSING_COMPARISON_COVERAGE','$.coverage','B must return source-derived coverage')] if required else []
 spec=wire['expected_response_schema']['properties']['coverage'];errors+=contract_shape_errors(items,spec,'$.coverage')
 if errors:return errors
 if required and not items:errors.append(failure('EMPTY_COMPARISON_COVERAGE','$.coverage','Explain represented source conditions; an empty array is not coverage'))
 catalog=wire['evidence_catalog'];entries={e['evidence_id']:e for e in catalog['entries']}
 for i,item in enumerate(items):
  at='$.coverage['+str(i)+']'
  for j,ref in enumerate(item['evidence']):
   ref={'id':ref} if isinstance(ref,str) else ref;path=at+'.evidence['+str(j)+']';entry=entries.get(ref['id'])
   if not entry:errors.append(failure('MISSING_OR_UNSUPPLIED_EVIDENCE_ID',path,'Supplied E ID only',ref['id']));continue
   start,end=ref.get('start',0),ref.get('end',len(entry['text']));span=('start' in ref)==('end' in ref) and type(start) is int and type(end) is int and 0<=start<end<=len(entry['text'])
   if not span:errors.append(failure('INVALID_EVIDENCE_SPAN',path,'Paired valid evidence character offsets',ref))
   if entry['kind']=='RDF_FACT' and (start!=0 or end!=len(entry['text'])):errors.append(failure('RDF_FACT_REFERENCE_MUST_BE_WHOLE_FACT',path,'Whole explicit RDF fact',ref))
   if 'quote' in ref:
    problem=citation_error(catalog,ref['id'],ref['quote'],source=entry['kind']=='SOURCE')
    if problem:errors.append(failure(problem[0],path+'.quote',problem[1],ref['quote']))
    elif span and ref['quote'] not in entry['text'][start:end] and entry['kind']!='RDF_FACT':errors.append(failure('ASSERTED_QUOTE_OUTSIDE_SPAN',path+'.quote','Exact quote inside evidence span',ref['quote']))
  for j,loc in enumerate(item.get('locations',[])):
   try:extract_location(code_location(c,loc['start'],loc['end'],unit=loc.get('unit','lines')),c)
   except ValueError as e:errors.append(failure(str(e),at+'.locations['+str(j)+']','Valid current candidate location',loc))
  if item['status']=='IMPLEMENTED' and not item.get('locations'):errors.append(failure('COVERAGE_IMPLEMENTATION_NEEDS_LOCATION',at+'.locations','Cite current code claimed to implement this criterion'))
  if item['status']=='MISSING' and not raw.get('issues'):errors.append(failure('COVERAGE_DECISION_CONTRADICTION',at,'Missing implementation requires actionable issue; semantic linkage remains independent judgment'))
  if item['status']=='UNRESOLVED' and not (raw.get('questions') or any(g.get('material') for g in raw.get('gap_review',[])) or any(x.get('disposition')=='UNRESOLVED' for x in raw.get('change_review',[])) or any(x.get('disposition')=='STILL_UNRESOLVED' for x in raw.get('question_review',[]))):errors.append(failure('COVERAGE_DECISION_CONTRADICTION',at,'Unresolved source information requires question or explicit unresolved context'))
 return errors

def inspect_response(response,wire,state,c,schema,required):
 try:_,normal=normalize_response(response)
 except ReviewerFormatError as e:return dict(valid=False,errors=[e.details],review=None,projection=None,coverage=None)
 raw=normal['normalized_response'];errors=contract_shape_errors(raw,wire['expected_response_schema'])
 if errors:return dict(valid=False,errors=errors,review=None,projection=None,coverage=None)
 errors+=coverage_errors(raw,wire,c,required)
 # Explicit comparison-only projection: raw response is preserved, no claim is changed.
 projection={k:v for k,v in raw.items() if k!='coverage'}
 projected=dict(response,text=json.dumps(projection,ensure_ascii=False));obj,audit,core_errors=validate_review(projected,c,state['context'],state['max_issues'],previous=None,changes=state['change_manifest'],prior_issues=state['prior_issues'],request_body=state);errors+=core_errors
 if obj is not None and not core_errors:
  route=review_proposal_routing(obj,schema,state['context']['requirement']['id'],state['context'])
  errors+=route['correctable']+route['blocking']
 return dict(valid=not errors,errors=errors,review=obj if not errors else None,projection=projection,coverage=raw.get('coverage'),projection_label='COMPARISON_ONLY_NO_WORKFLOW_CREDIT_NO_REPAIR_AUTHORIZATION',explanatory_truth='REQUIRES_POST_CLOSURE_INDEPENDENT_INSPECTION')

def frozen_inputs():
 for n,h in load(A/'comparison.freeze.json').items():
  if sha(A/n)!=h:raise ValueError('COMPARISON_ARTIFACT_INTEGRITY_FAILURE '+n)
 m=load(A/'comparison.prepared.json');g=Path(m['source_run']);lock=load(g/'freeze_lock.json');verify(R,lock)
 if sha(g/'freeze_lock.json')!=m['source_freeze_sha256']:raise ValueError('SOURCE_FREEZE_INTEGRITY_FAILURE')
 if sha(g/'provider/call_002_request.body')!=m['source_review_request_sha256']:raise ValueError('SOURCE_REQUEST_INTEGRITY_FAILURE')
 state=load(g/'TRF-035/NLTL/review_state_001.json');c=Candidate(state['candidate_version'],state['full_candidate'],'')
 if c.sha256!=m['candidate_sha256']:raise ValueError('CANDIDATE_INTEGRITY_FAILURE')
 payloads={arm:load(A/(arm+'.request.json')) for arm in m['arm_order']}
 for arm,p in payloads.items():assert_review_packet(json.loads(p['input'][1]['content'][0]['text']),c)
 if payloads[m['arm_order'][0]]['input'][1]!=payloads[m['arm_order'][1]]['input'][1]:raise ValueError('COMPARISON_INPUT_INTEGRITY_FAILURE')
 limits=load(g/'manifest.frozen.json')['token_limits'];return m,g,lock,state,c,payloads,limits

def preflight_check():
 m,g,lock,state,c,payloads,limits=frozen_inputs();counter=load_counter(R,limits)
 assert (m['max_HTTP_calls_total'],m['max_primary_reviews'],m['shared_corrections_per_arm'],m['max_output_tokens_per_request'],m['max_workflow_seconds'])==(4,2,1,16000,600)
 capacities={arm:preflight(p,limits,counter) for arm,p in payloads.items()};assert not any(v['exceeds_known_token_limit'] for v in capacities.values())
 import dotenv
 cred=Path(os.environ.get('NLTL_ENV_FILE','/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env')).resolve();assert cred.is_file() and not cred.is_relative_to(R),'EXTERNAL_CREDENTIAL_CONFIGURATION_REQUIRED'
 env=dotenv.dotenv_values(cred);assert env.get('AALTO_AI_API_KEY'),'AALTO_AI_API_KEY_MISSING';assert env.get('AALTO_AI_RESPONSES_URL',m['destination']).rstrip('/')==m['destination'];del env
 return dict(status='READY_OFFLINE_NO_MODEL_CALLS',candidate_sha256=c.sha256,arms=2,capacity=capacities,external_credentials_present=True,credentials_printed=False,production_files_verified=len(lock['files']))

def classify(exc):
 message=str(exc)
 if any(k in message for k in ['INTEGRITY','STALE','ISOLAT','FORBIDDEN']):return 'PIPELINE_INTEGRITY_ROUTING_OR_MISSING_IO'
 if any(k in message for k in ['FINAL_OUTPUT_MISSING','INVALID_JSON','MODEL_CONTEXT_TOKEN_LIMIT','RENDERED','ABSENT']):return 'PIPELINE_INTEGRITY_ROUTING_OR_MISSING_IO'
 if message in ['WORKFLOW_TIME_LIMIT_EXHAUSTED','OUTPUT_TOKEN_LIMIT_EXHAUSTED','PROVIDER_CALL_LIMIT_EXHAUSTED']:return 'FROZEN_CONTROLLER_LIMIT_STOP'
 return 'TRANSPORT_INFRASTRUCTURE'

def run(identifier):
 preflight_check()
 for n,h in load(A/'launcher/launcher.freeze.json')['files'].items():
  if sha(A/n)!=h:raise ValueError('LAUNCHER_FREEZE_INTEGRITY_FAILURE '+n)
 m,g,lock,state,c,payloads,limits=frozen_inputs();out=Project(R).output('experiments',identifier);write(out/'comparison.manifest.frozen.json',m);write(out/'production.freeze.json',lock);write(out/'launcher.freeze.json',load(A/'launcher/launcher.freeze.json'));results=[];t=None;started=time.monotonic();terminal=None;active_arm=None
 def progress(active=None,phase='IDLE'):
  data=dict(total_arms=2,done=len(results),in_progress=1 if active else 0,pending=2-len(results)-(1 if active else 0),active_arm=active,phase=phase,provider_calls=0 if t is None else t.calls,max_provider_calls=4,elapsed_seconds=time.monotonic()-started);write(out/'progress.json',data);print(f"done={data['done']}/2 in_progress={data['in_progress']} pending={data['pending']} calls={data['provider_calls']}/4 arm={active or '-'} phase={phase}",flush=True)
 try:
  t=HostedResponsesTransport(enabled=True,project_root=R,output=out/'provider',max_calls=4,max_seconds=600,max_output_tokens_total=64000,timeout=180,token_limits=limits,token_counter=load_counter(R,limits));schema=Schema(Project(R));progress()
  for arm in m['arm_order']:
   active_arm=arm;dest=out/arm;dest.mkdir();p=payloads[arm];wire=json.loads(p['input'][1]['content'][0]['text']);base=copy.deepcopy(wire);attempts=[];assessment=None
   for correction in range(2):
    frozen_inputs();progress(arm,'RESPONSE_CORRECTION' if correction else 'REVIEW')
    request=dict(route='review_format_retry' if correction else 'review',system=p['input'][0]['content'][0]['text'],user=json.dumps(wire,ensure_ascii=False),model=p['model'],max_output_tokens=p['max_output_tokens'])
    reconstructed=provider_payload(request);reconstructed['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in reconstructed['input']];reconstructed.update(truncation='disabled',store=False)
    if correction==0 and reconstructed!=p:raise ValueError('RENDERED_REQUEST_INTEGRITY_FAILURE')
    write(dest/f'request_{correction+1:03d}.json',request);response=t.dispatch(request,c,());write(dest/f'response_{correction+1:03d}.json',response);validated=inspect_response(response,base,state,c,schema,arm=='B_generic_coverage');write(dest/f'validation_{correction+1:03d}.json',validated);attempts.append(dict(physical_call=t.calls,correction=correction,validation_file=f'validation_{correction+1:03d}.json',valid=validated['valid'],errors=validated['errors'],usage=response.get('usage'),elapsed_seconds=response['elapsed_seconds']))
    if validated['valid']:
     assessment=validated['review']['assessment'];break
    if any(e.get('category')=='REQUEST_VERSION_BINDING' or 'INTEGRITY' in e.get('code','') or e.get('code','').startswith('STALE_') for e in validated['errors']):raise ValueError('VALIDATION_BINDING_INTEGRITY_FAILURE')
    if correction==0:
     wire=copy.deepcopy(base);wire['format_feedback']=dict(rejected_response=response['text'],validation_errors=validated['errors'],failed_review_is_not_prior_state=True,shared_response_correction_allowance=True,instruction=response_correction_instruction(validated['errors'])+' For the comparison-only coverage field, code ranges use coverage[].locations with the same current-candidate location form. Keep coverage distinct from core review fields. Do not change any substantive claim merely to bypass validation.')
   row=dict(arm=arm,status='VALID_REVIEW_NOT_CORRECTNESS_CERTIFICATION' if assessment else 'REVIEWER_RESPONSE_PROTOCOL_FAILURE',assessment=assessment,attempts=attempts,classification=['REVIEWER_RESPONSE_PROTOCOL_FAILURE'] if not assessment else ['SUBSTANTIVE_INTERPRETATION_REQUIRES_INDEPENDENT_INSPECTION'],genuine_ambiguity_status='MODEL_REPORTED_NOT_INDEPENDENTLY_ESTABLISHED' if assessment=='HUMAN_REVIEW_REQUIRED' else 'NOT_ESTABLISHED',coverage_truth='POST_CLOSURE_INSPECTION_REQUIRED',evaluation_attribution='NO_NEW_EVALUATION_OR_ATTRIBUTION_CREDIT',production_acceptance=False,repair_authorized=False);results.append(row);write(dest/'result.json',row);active_arm=None;progress()
 except Exception as e:
  terminal=dict(classification=classify(e),type=type(e).__name__,diagnostic=str(e),arm=active_arm,no_retry=True)
  if active_arm and active_arm not in {r['arm'] for r in results}:
   row=dict(arm=active_arm,status='ERROR',classification=[terminal['classification']],terminal_failure=terminal,production_acceptance=False,repair_authorized=False);results.append(row);write(out/active_arm/'result.json',row)
  write(out/'terminal_failure.json',terminal);print('STOP '+terminal['classification']+': '+str(e),flush=True)
 finally:
  if t:t.close()
  write(out/'dispatch_closed.json',dict(dispatch_closed=True,closed_utc=utc(),outstanding_provider_processes=0,physical_calls=t.calls if t else 0,elapsed_seconds=time.monotonic()-started,terminal_failure=terminal,candidate_sha256=c.sha256,results=results,not_run=[arm for arm in m['arm_order'] if arm not in {r['arm'] for r in results}],no_generation_or_repair=True,no_workflow_credit=True));progress(phase='CLOSED')
 print('CLOSED — '+str(out),flush=True)
 if terminal:raise SystemExit(2)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--run-id');p.add_argument('--allow-model-calls',action='store_true');args=p.parse_args()
 if args.preflight:
  def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE_PREFLIGHT')
  socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny;print(json.dumps(preflight_check(),indent=2))
 elif args.run_id and args.allow_model_calls:run(args.run_id)
 else:p.error('Use --preflight (offline), or --run-id ID --allow-model-calls (live).')
