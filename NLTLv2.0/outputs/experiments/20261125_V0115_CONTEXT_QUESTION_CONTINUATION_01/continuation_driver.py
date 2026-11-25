"""One authorized historical-state diagnostic; production Runner routes unchanged."""
from pathlib import Path
import os,sys,json,copy,hashlib,time,datetime,socket,shutil,argparse
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION'
G=R/'outputs/experiments/20261125_V0115_CONTEXT_QUESTION_CONTINUATION_01';RID='IMO-001'
sys.path[:0]=[str(R/'src'),str(R/'tests'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,Candidate,Finding,write,digest,normalize,finding
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.hosted_pilot import verify
from nltlv2.evidence import probe_summary,assert_review_packet
from nltlv2.context_resolution import unresolved_questions
from nltlv2.checks import check,runtime_probe
from nltlv2.change_review import manifest
from nltlv2.requests import repair_request
from nltlv2.admission import load_admission
from nltlv2.token_budget import load_counter,preflight
from nltlv2.transport import HostedResponsesTransport,provider_payload
from nltlv2.delivery import finalize
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def payload(q):
 p=provider_payload(q);p['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in p['input']];p.update(truncation='disabled',store=False);return p

def setup(cfg,transport,dest,state,ledger,event,inputs):
 r=Runner(Project(R),cfg,transport,dest);r.admission_context=copy.deepcopy(state['context']['admission']);r.context_questions=copy.deepcopy(ledger);r.input_hashes=copy.deepcopy(inputs);r.resolver.rounds=1;r.resolver.total_characters=event['total_characters'];r.resolver.events=[copy.deepcopy(event)];r.resolver.attempted_requests={digest(json.dumps(event['requests'],sort_keys=True))}
 # First saved retrieval was schema-only; there are no source traversal/cache states to reconstruct.
 assert all(e.get('kind')=='schema' for e in event['entries'])
 r.execution_summaries[state['candidate_version']]=copy.deepcopy(state['execution_probe']);return r

def prepare():
 def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
 socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
 assert not G.exists(),'Fresh output ID required; no repeat dispatch';G.mkdir(parents=True)
 frozen=load(A/'freeze_lock.json');verify(R,frozen)
 packet=load(A/'complete_followup_packet.json');s=packet['internal_state'];ledger=packet['question_provenance_ledger_before_second_historical_question'];assert len(ledger)==1
 q=next(iter(ledger.values()));assert q['id']=='Q1' and len(q['observations'])==1 and not q['dispositions'] and q['status']=='STILL_UNRESOLVED';assert len(q['retrieval_attempts'])==1
 # Independently verify the original first response/question/evidence, not later reviews.
 B=R/'outputs/experiments/20261125_V0114_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';first=load(B/'provider/call_003_response.json');rawq=json.loads(first['text'])['questions'];assert len(rawq)==1 and rawq[0]['missing']==q['missing'] and rawq[0]['why']==q['why']
 oldstate=load(B/'IMO-001/NLTL/review_state_002.json');oldcatalog={x['evidence_id']:x for x in oldstate['evidence_catalog']['entries']}
 for e in q['supporting_evidence']:
  original=oldcatalog[e['original_reference']];assert all(original[k]==e[k] for k in ['evidence_sha256','provenance_sha256']);assert digest(e['text'])==e['text_sha256'];assert e['text']==original['text'][e['start']:e['end']];assert e['origin']==original['origin']
 seed=B/'IMO-001/NLTL/candidate_02.ttl';assert sha(seed)==s['candidate_sha256']==packet['candidate_sha256']==q['originating_candidate']['sha256'];assert seed.read_text()==s['full_candidate'];assert s['candidate_version']==2
 event=load(B/'IMO-001/NLTL/retrieval_ledger.json')[0];assert event['round']==1;assert event['requests'][0]['query']==q['missing'][:2000]
 # Load only first saved state; no later question/review/approval/evaluation artifact imported.
 m=load(A/'diagnostic.prepared.json');cfg=copy.deepcopy(m['config']);cfg['admission_file']=m['scope_files'][RID];cfg['context_resolution']['max_reviews_per_run']=3;cfg['maximum_candidate_attempts']=2
 names=set(cfg['resources'].values())|{'prompts/generator.txt','prompts/reviewer.txt','prompts/repair.txt',cfg['admission_file']}|{d['file'] for d in s['context']['source_documents']}
 inputs={n:frozen['files'][n] for n in names}
 for n,h in inputs.items():assert sha(R/n)==h
 ad=load_admission(Project(R),cfg,Runner(Project(R),cfg,object(),G).schema,RID);assert ad['valid'] and ad['context']==s['context']['admission']
 rdest=G/RID/'NLTL';rdest.mkdir(parents=True);(rdest/'candidate_02.ttl').write_text(s['full_candidate']);write(rdest/'candidate_02.json',dict(version=2,sha256=s['candidate_sha256'],origin='EXACT_UNCHANGED_HISTORICAL_STATE_SEED',generated=False))
 r=setup(cfg,object(),rdest,s,ledger,event,inputs);c=Candidate(2,s['full_candidate'],s['full_candidate']);p=s['previous_candidate'];previous=Candidate(p['version'],p['full_code'],p['full_code']) if p else None
 capture={}
 class Capture(Exception):pass
 def dispatch(request,latest=None):capture['request']=dict(request,model=cfg['model'],max_output_tokens=cfg['review_max_tokens']);raise Capture()
 r.dispatch=dispatch
 warnings=[Finding(**{k:v for k,v in x.items() if k!='finding_key'}) for x in s['deterministic_findings']]
 try:r.review(c,s['context'],previous,s['change_manifest'],Tracker(),warnings,prior_override=[])
 except Capture:pass
 request=capture['request'];wire=json.loads(request['user']);assert len(wire['prior_context_questions'])==1;assert wire['prior_context_questions'][0]['missing']==q['missing'] and wire['prior_context_questions'][0]['why']==q['why'];assert not wire['prior_issues'] if 'prior_issues' in wire else True
 pld=payload(request);counter=load_counter(R,m['token_limits']);cap=preflight(pld,m['token_limits'],counter);assert not cap['exceeds_known_token_limit'];assert request['max_output_tokens']==16000
 import dotenv
 cred=Path(os.environ.get('NLTL_ENV_FILE','/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env'));env=dotenv.dotenv_values(cred);assert env.get('AALTO_AI_API_KEY');assert env.get('AALTO_AI_RESPONSES_URL',m['destination']).rstrip('/')==m['destination'];del env
 protected={str(p.relative_to(R)):sha(p) for dn in ['outputs','results','evaluation','schema','data'] for p in (R/dn).rglob('*') if p.is_file() and not p.is_relative_to(G) and '__pycache__' not in p.parts};protected['docs/retention_ledger.json']=sha(R/'docs/retention_ledger.json')
 write(G/'protected_before.json',protected);write(G/'continuation_config.json',cfg);write(G/'seed_state.json',s);write(G/'initial_question_ledger.json',ledger);write(G/'saved_first_retrieval.json',event);write(G/'source_input_hashes.json',inputs);write(G/'freeze_lock.json',frozen);write(G/'token_limits.json',m['token_limits']);write(G/'first_request.frozen.json',request);write(G/'first_provider_payload.frozen.json',pld);(G/'first_provider_payload.frozen.body').write_bytes(json.dumps(pld,ensure_ascii=False).encode());write(G/'first_capacity.json',cap)
 write(G/'origin_verification.json',dict(label='HISTORICAL_STATE_DEVELOPMENT_CONTINUATION_NOT_FRESH_WORKFLOW_PERFORMANCE',source_packet=str(A/'complete_followup_packet.json'),source_packet_sha256=sha(A/'complete_followup_packet.json'),seed_file=str(seed),seed_sha256=sha(seed),first_response_file=str(B/'provider/call_003_response.json'),first_response_sha256=sha(B/'provider/call_003_response.json'),first_question=q,first_retrieval_round=1,approved_scope_file=cfg['admission_file'],approved_scope_sha256=sha(R/cfg['admission_file']),scope_loaded=True,later_reviews_imported=False,historical_approval_imported=False,evaluation_findings_imported=False,known_solution_imported=False,initial_prior_issues=[],first_request_sha256=digest(json.dumps(request,sort_keys=True)),provider_payload_sha256=sha(G/'first_provider_payload.frozen.body')))
 # Current software controls offline, without saved question/solution supplied to model requests.
 import unittest,io
 for k in ['NLTL_TEST_OUTPUT','NLTL_ALIGNMENT_EXAMPLE','NLTL_HANDOFF_EXAMPLE']:os.environ.pop(k,None)
 os.environ['NLTL_TEST_PROJECT']=str(R);stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover(str(R/'tests')));(G/'offline_tests.log').write_text(stream.getvalue());assert tests.wasSuccessful()
 write(G/'preflight.json',dict(status='READY_FROZEN_NOT_DISPATCHED',label='CONTEXT_QUESTION_CONTINUATION',tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),network='BLOCKED',source_version='0.11.5',initial_generations=0,primary_reviews_maximum=3,shared_corrections_per_review=1,semantic_revisions_maximum=1,technical_revisions_maximum=0,total_candidate_limit=2,saved_retrieval_rounds=1,total_retrieval_rounds=2,remaining_retrieval_rounds=1,provider_http_call_cap=11,control_flow_maximum_calls=3*2+1,max_seconds=600,max_output_tokens_per_request=16000,max_reserved_output_tokens=176000,capacity=cap,no_implementation_or_prompt_changes=True))
 shutil.copyfile(__file__,G/'continuation_driver.py');verify(R,frozen)
 names=['continuation_driver.py','continuation_config.json','seed_state.json','initial_question_ledger.json','saved_first_retrieval.json','source_input_hashes.json','freeze_lock.json','token_limits.json','first_request.frozen.json','first_provider_payload.frozen.body','origin_verification.json','preflight.json']
 write(G/'continuation_freeze.json',{n:sha(G/n) for n in names});write(G/'dispatch_state.json',dict(status='PREPARED',provider_calls=0));print(json.dumps(dict(prepared=str(G),tests=tests.testsRun,seed_sha256=c.sha256,question_id=q['id'],capacity=cap,max_calls=11,control_flow_bound=7)),flush=True)

def run():
 assert load(G/'dispatch_state.json')['status']=='PREPARED','No repeat dispatch'
 for n,h in load(G/'continuation_freeze.json').items():assert sha(G/n)==h,'CONTINUATION_STATE_INTEGRITY_FAILURE'
 frozen=load(G/'freeze_lock.json');verify(R,frozen);cfg=load(G/'continuation_config.json');s=load(G/'seed_state.json');ledger=load(G/'initial_question_ledger.json');event=load(G/'saved_first_retrieval.json');inputs=load(G/'source_input_hashes.json');limits=load(G/'token_limits.json');first_request=load(G/'first_request.frozen.json');counter=load_counter(R,limits)
 dest=G/RID/'NLTL';os.environ.update(NLTL_ALLOW_MODEL_CALLS='YES',NLTL_ENV_FILE=os.environ.get('NLTL_ENV_FILE','/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env'))
 write(G/'dispatch_state.json',dict(status='DISPATCH_STARTED_NO_RERUN',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));start=time.monotonic()
 t=HostedResponsesTransport(enabled=True,project_root=R,output=G/'provider',max_calls=11,max_seconds=600,max_output_tokens_total=176000,timeout=180,token_limits=limits,token_counter=counter)
 r=setup(cfg,t,dest,s,ledger,event,inputs);tracker=Tracker();context=copy.deepcopy(s['context']);c=Candidate(2,s['full_candidate'],s['full_candidate']);p=s['previous_candidate'];previous=Candidate(p['version'],p['full_code'],p['full_code']) if p else None;changes=s['change_manifest'];history=[];repairs=0;terminal='NOT_STARTED';operational=None;phases=[]
 original_dispatch=r.dispatch
 def dispatch(request,latest=None):
  verify(R,dict(frozen,files={n:h for n,h in frozen['files'].items() if not n.startswith('tests/')}))
  for n,h in load(G/'continuation_freeze.json').items():assert sha(G/n)==h,'CONTINUATION_STATE_INTEGRITY_FAILURE'
  assert request['route'] in ['review','review_format_retry','targeted_repair','syntax_repair'];assert request['route'].endswith('repair') is False or request.get('repair_type')=='semantic';assert latest is not None
  if not r.calls:assert dict(request,model=cfg['model'],max_output_tokens=cfg['review_max_tokens'])==first_request,'FROZEN_FIRST_REQUEST_INTEGRITY_FAILURE'
  # No generation; at most 3 primaries/3 shared corrections and one semantic revision.
  assert sum(x['route']=='review' for x in r.calls)+int(request['route']=='review')<=3
  assert sum(x['route'].endswith('repair') for x in r.calls)+int(request['route'].endswith('repair'))<=1
  t0=time.monotonic()
  try:return original_dispatch(request,latest)
  finally:phases.append(dict(phase=request['route'],candidate_version=latest.version,elapsed_seconds=time.monotonic()-t0))
 r.dispatch=dispatch
 # During dispatch only production files and this continuation's artifacts are accessible.
 gate={'on':True};denied=[]
 def firewall(ev,args):
  if not gate['on']:return
  if ev=='import' and args and str(args[0]).startswith(('nltlv2.evaluation','nltlv2.development_checks')):raise PermissionError('EVALUATION_IMPORT_ISOLATED')
  if ev in ['open','os.listdir','os.scandir'] and args and isinstance(args[0],(str,bytes,os.PathLike)):
   p=Path(os.fsdecode(args[0])).resolve()
   forbidden=p.is_relative_to(R.parent/'MVP') or any(p.is_relative_to(R/x) for x in ['results','evaluation','tests','data/contracts','data/examples']) or (p.is_relative_to(R/'outputs') and not p.is_relative_to(G) and not p.is_relative_to(D/'tokenizer_cache') and not p.is_relative_to(D/'tokenizer_runtime') and str(p.relative_to(R)) not in frozen['files'])
   if forbidden:denied.append(str(p));raise PermissionError('EVALUATION_HISTORY_SOLUTION_ACCESS_FORBIDDEN')
 sys.addaudithook(firewall)
 try:
  r.transition(c,'CONTINUATION_START',initial_generations=0,saved_question_ids=['Q1'],saved_retrieval_rounds=1)
  for index in range(2):
   ts=time.monotonic();fs=check(c,r.schema,RID,admission=r.admission_context);r.execution_summaries[c.version]=probe_summary(c,reason='Blocked by static checks');runtime_complete=False
   if not any(f.blocking for f in fs):
    execution,probe=runtime_probe(c,r.schema);fs+=execution;r.execution_summaries[c.version]=probe_summary(c,probe);runtime_complete=not execution;write(dest/f'runtime_probe_{c.version:02d}.json',probe)
   tech=dict(candidate_version=c.version,candidate_sha256=c.sha256,qualifies=runtime_complete and not any(f.blocking and f.category!='UNRESOLVED_CONTEXT' for f in fs),runtime_complete=runtime_complete,findings=[f.asdict() for f in fs],check_seconds=time.monotonic()-ts);write(dest/f'technical_{c.version:02d}.json',tech);phases.append(dict(phase='technical_checks',candidate_version=c.version,elapsed_seconds=time.monotonic()-ts))
   # Seed execution summary must match the frozen request; a mismatch is integrity, never silently updated.
   if index==0:
    actual=r.execution_summaries[c.version];saved=s['execution_probe']
    for k in ['candidate_version','candidate_sha256','engine','engine_version','engine_outcome','exact_diagnostics']:assert actual[k]==saved[k],'FROZEN_EXECUTION_CONTEXT_INTEGRITY_FAILURE'
    for k in ['roots','supported','unsupported_custom_targets']:assert actual['activation'][k]==saved['activation'][k],'FROZEN_ACTIVATION_INTEGRITY_FAILURE'
    for k in ['reachable','enforcing_nodes','deactivated_reachable','orphan_constraint_nodes']:assert len(actual['activation'][k])==len(saved['activation'][k]),'FROZEN_ACTIVATION_INTEGRITY_FAILURE'
    write(dest/'seed_recheck_comparison.json',dict(actual=actual,saved=saved,equivalent_engine_diagnostics_and_activation=True,note='RDF blank-node parser labels are nondeterministic. Keep the original saved probe in the frozen continuation request; preserve current recheck separately.'))
    r.execution_summaries[c.version]=copy.deepcopy(saved)
   context,fs,obj,error,conflicts,status=r.assess_candidate(c,context,previous,changes,tracker,fs,RID)
   rec,persistent=tracker.observe(c,fs,static_complete=not any(f.category=='PARSE_ERROR' for f in fs),review=obj,runtime_complete=runtime_complete);r.latest_findings=tuple(fs)
   accepted=status=='ACCEPTED' and obj is not None and obj['decision']=='ACCEPT' and not error and not conflicts and not any(f.blocking for f in fs)
   terminal='ACCEPTED' if accepted else status
   row=dict(version=c.version,sha256=c.sha256,accepted=accepted,status=terminal,technical=tech,review=obj,reviewer_format_failure=error,conflicts=conflicts,findings=[f.asdict() for f in fs],repair_type=None if index==0 else 'semantic',structural_change_manifest=changes,changes=rec,persistent_failure_summary=persistent);history.append(row);write(dest/'history.json',history);write(dest/f'findings_{c.version:02d}.json',row['findings'])
   if accepted or error or conflicts or status!='REJECTED':break
   if index==1:terminal='SEMANTIC_REPAIR_LIMIT_EXHAUSTED' if tech['qualifies'] else 'TECHNICAL_FAILURE_NO_REPAIR_ALLOWANCE';r.transition(c,terminal);break
   if not tech['qualifies']:terminal='TECHNICAL_FAILURE_NO_REPAIR_ALLOWANCE';r.transition(c,terminal);break
   request=repair_request(r.p,context,c,fs,persistent_summary=persistent,context_questions=unresolved_questions(r.context_questions,context));request['repair_type']='semantic';r.transition(c,'REPAIR_REQUEST_READY',repair_type='semantic',full_latest_candidate=True);response=r.dispatch(request,c);repairs+=1
   if response.get('status')=='incomplete' or response.get('finish_reason') in ['length','max_tokens','max_output_tokens']:raise ValueError('SEMANTIC_REVISION_OUTPUT_INCOMPLETE_NO_EXTRA_REPAIR')
   code,norm=normalize(response['text']);previous=c;c=Candidate(c.version+1,code,response['text']);(dest/f'candidate_{c.version:02d}.ttl').write_text(code);write(dest/f'candidate_{c.version:02d}.json',dict(version=c.version,sha256=c.sha256,normalization=norm,origin='ACTUAL_SEMANTIC_REPAIR_RESPONSE'));changes=manifest(previous,c);write(dest/f'change_manifest_{c.version:02d}.json',changes);(dest/f'diff_{previous.version:02d}_{c.version:02d}.patch').write_text(changes['diff'])
 except Exception as e:
  message=str(e);terminal='REQUEST_INTEGRITY_FAILURE' if any(x in message for x in ['INTEGRITY','STALE','ISOLATED','FORBIDDEN']) else 'BOUNDED_REVISION_OUTPUT_FAILURE' if 'SEMANTIC_REVISION_OUTPUT_INCOMPLETE' in message or type(e).__name__=='WrapperError' else 'PROVIDER_CALL_LIMIT_EXHAUSTED' if message=='PROVIDER_CALL_LIMIT_EXHAUSTED' else 'WORKFLOW_TIME_LIMIT_EXHAUSTED' if message=='WORKFLOW_TIME_LIMIT_EXHAUSTED' else 'INFRASTRUCTURE_FAILURE';operational=dict(status=terminal,type=type(e).__name__,diagnostic=message,no_retry=True);write(dest/'operational_failure.json',operational)
 finally:
  t.close();gate['on']=False;write(G/'dispatch_closure.json',dict(closed=True,closed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),provider_calls=t.calls,elapsed_seconds=time.monotonic()-start,terminal=terminal,no_further_calls=True));write(G/'dispatch_state.json',dict(status='CLOSED_NO_RERUN',provider_calls=t.calls))
 # Preserve a qualifying seed even if a later ordinary review fails; current production delivery selection.
 delivery=finalize(dest,history,terminal);result=dict(version='0.11.5',label='HISTORICAL_STATE_CONTEXT_QUESTION_CONTINUATION_DEVELOPMENT_EVIDENCE_NOT_FRESH_PERFORMANCE',requirement_id=RID,status=terminal,delivery=delivery,context_questions=r.context_questions,history=history,repair_counts=dict(technical=0,semantic=repairs),provider_calls=t.calls,call_counts_by_route={route:sum(x['route']==route for x in r.calls) for route in sorted({x['route'] for x in r.calls})},usage={k:sum((m.get('usage') or {}).get(k,0) or 0 for m in r.response_metrics) for k in ['input_tokens','output_tokens','total_tokens']},phase_timings=phases,elapsed_seconds=time.monotonic()-start,operational_failure=operational,isolation=dict(active_during_dispatch=True,denied_accesses=denied,evaluation_loaded=False),initial_generations=0,seed_sha256=s['candidate_sha256'],code_changed=any(h['sha256']!=s['candidate_sha256'] for h in history),evaluation='PENDING_ONLY_IF_CHANGED_AFTER_CLOSURE_OTHERWISE_REFERENCE_EXISTING_BEHAVIOR',provider_internal_timings='UNAVAILABLE');write(dest/'run.json',result);write(G/'phase_timings.json',phases);verify(R,frozen);print(json.dumps(dict(output=str(G),status=terminal,delivery=delivery['status'],calls=t.calls,repairs=repairs,code_changed=result['code_changed'],usage=result['usage'],elapsed_seconds=result['elapsed_seconds'],operational_failure=operational)),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);args=p.parse_args();prepare() if args.mode=='prepare' else run()
