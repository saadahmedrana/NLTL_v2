"""Bounded TRF-010 development tests; no evaluation modules or fixtures in generation.
The seed adapter calls the frozen production checker, repair renderer, request
boundary, regression guard, runtime probe and reviewer. It issues no generation.
"""
from pathlib import Path
import argparse,collections,datetime,difflib,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,Candidate,normalize,WrapperError,finding,write,load,stamp,digest
from nltlv2.schema import Schema
from nltlv2.checks import check,regression,transitions,runtime_probe
from nltlv2.enumerations import coverage_findings
from nltlv2.requests import initial_request,repair_request,assert_integrity
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport

ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent
ENV=REPO.parent/'env/NLTL_v2.env';STATE=Path('/private/tmp/nltlv2_bounded_state_20261113.json');RID='TRF-010'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def git(*args):return subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/git','-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def prepare():
 if STATE.exists():raise RuntimeError('Refusing to reuse bounded-test state')
 p=Project(ROOT);c1=p.config('configs/single_shot.json');c2=p.config('configs/nltl.json')
 import nltlv2
 assert importlib.metadata.version('nltlv2-refined')=='0.2.0'
 assert all(f.read_bytes()==(Path(nltlv2.__file__).parent/f.name).read_bytes() for f in (ROOT/'src/nltlv2').glob('*.py'))
 manifest=load(ROOT/'docs/bundle_manifest.json')
 assert all(sha(ROOT/name)==expected for name,expected in manifest['files'].items())
 # Freeze all prior artifacts before creating this new study container. Hashes only, no copying outputs.
 historical={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'outputs').rglob('*') if f.is_file()}
 run_id=stamp()+'_TRF010_BOUNDED_DEVELOPMENT';group=p.output('experiments',run_id)
 write(group/'historical_artifact_hashes_before.json',historical)
 (group/'git_revision.txt').write_text(git('rev-parse','HEAD'))
 (group/'working_tree_before.txt').write_text(git('status','--porcelain=v1','--untracked-files=normal'))
 (group/'working_tree_diff_stat.txt').write_text(git('diff','--stat'));(group/'index_diff_stat.txt').write_text(git('diff','--cached','--stat'))
 snap=group/'snapshot';snap.mkdir()
 for d in ['src','prompts','configs','schema','data']:
  shutil.copytree(ROOT/d,snap/d,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
 for name in ['pyproject.toml','requirements-lock.txt']:shutil.copyfile(ROOT/name,snap/name)
 hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 shutil.copyfile(__file__,group/'bounded_live_driver.py')
 frozen=Project(snap);schema=Schema(frozen);ctx=schema.context(RID)
 assert all(RID not in json.dumps(x) and x['inputRequirement'] not in [ctx['requirement']['text'],ctx['requirement']['normalized']] for x in ctx['examples'])
 configs={'Single-shot':c1,'NLTL':c2}
 for cfg in configs.values():cfg['network_enabled']=True
 assert c1['maximum_candidate_attempts']==1 and not c1['semantic_review']
 assert c2['maximum_candidate_attempts']==6 and not c2['fresh_regeneration']
 reqs=[initial_request(frozen,ctx,{k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}) for cfg in configs.values()]
 assert reqs[0]==reqs[1]
 from dotenv import dotenv_values
 values=dotenv_values(ENV);url=values['AALTO_RESPONSES_BASE_URL'].rstrip('/');u=urllib.parse.urlsplit(url)
 assert values.get('AALTO_API_KEY') and u.scheme=='https' and not any([u.username,u.password,u.query,u.fragment])
 seed=ROOT/'outputs/experiments/20261111T123517321850Z_TRF010_LIVE_DEV/nltl/candidate_01.ttl'
 assert sha(seed)=='080007c68965287e5b8a344ba8d94c89c789a709a61a1a859d2edd46f1af0e8b'
 write(group/'preflight.json',dict(version='0.2.0',requirement=RID,git_revision=git('rev-parse','HEAD').strip(),model=c2['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,credential_location=str(ENV),key_present=True,secret_values_logged=False,schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],initial_context_sha256=digest(json.dumps(ctx,ensure_ascii=False)),initial_request_sha256=digest(json.dumps(reqs[0],ensure_ascii=False)),paired_initial_requests_identical=True,examples=[x['exampleId'] for x in ctx['examples']],target_absent_from_examples=True,historical_seed=str(seed.relative_to(ROOT)),historical_seed_sha256=sha(seed),arm_A=dict(label='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC',maximum_repair_calls=2,initial_generation_calls=0,not_fresh_performance=True),arm_B=dict(label='FRESH_PAIRED_DEVELOPMENT_PILOT',single_shot_generation_calls=1,nltl_maximum_candidate_attempts=6,fresh_regeneration=False),stop_rule='Do not start the next arm after any runtime, integrity or contradictory-feedback problem. No automatic transport retries.',dependencies={x:importlib.metadata.version(x) for x in ['rdflib','pyshacl','requests','python-dotenv']},evaluation_firewall='No evaluation imports, cases, labels or counterparts in this generation process; independent offline process only after arm completion'))
 write(group/'resolved_configs.json',configs);write(group/'corrected_initial_request.json',reqs[0])
 write(STATE,dict(group=str(group),arm_A=None,arm_B=None));print('PREPARED '+str(group),flush=True)

def verify_frozen(group):
 for name,expected in load(group/'snapshot_hashes.json').items():
  if sha(group/'snapshot'/name)!=expected or sha(ROOT/name)!=expected:raise RuntimeError('FROZEN_INPUT_OR_IMPLEMENTATION_CHANGED: '+name)

def credentials():
 os.environ['NLTL_ALLOW_MODEL_CALLS']='YES';os.environ['NLTL_ENV_FILE']=str(ENV)

class AuditTransport(LiveTransport):
 def __init__(self,dest,allowed_generation,max_repairs):
  super().__init__(enabled=True,project_root=ROOT);self.dest=dest;self.events=[];self.allowed_generation=allowed_generation;self.max_repairs=max_repairs
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route'];ngen=sum(e['route']=='generation' for e in self.events);nrepair=sum(e['route'].endswith('repair') for e in self.events)
  if route=='generation' and ngen>=self.allowed_generation:raise RuntimeError('GENERATION_CALL_LIMIT_OR_SEED_MODE_VIOLATION')
  if route.endswith('repair') and nrepair>=self.max_repairs:raise RuntimeError('REPAIR_CALL_LIMIT')
  if route=='fresh_regeneration':raise RuntimeError('FRESH_REGENERATION_DISABLED')
  if route.endswith('repair'):assert_integrity(request,latest,expected_findings)
  u=urllib.parse.urlsplit(self.url);i=len(self.events)+1
  body=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  write(self.dest/f'provider_request_{i:03d}.json',dict(endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,authentication='External header; value omitted',body=body))
  event=dict(index=i,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(body)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events)
  started=time.monotonic()
  try:
   result=super().dispatch(request,latest,expected_findings);provider=result.get('provider_response',{})
   event.update(status='RESPONSE',provider_model=provider.get('model'),provider_id=provider.get('id'),response_status=result.get('status'),finish_reason=result.get('finish_reason'),usage=result.get('usage',{}),elapsed_seconds=result.get('elapsed_seconds'))
   write(self.dest/'call_ledger.json',self.events)
   if provider.get('model')!=request['model'] or result.get('status') not in ['completed',None]:
    write(self.dest/f'unexpected_provider_response_{i:03d}.json',result);raise RuntimeError('UNEXPECTED_PROVIDER_MODEL_OR_COMPLETION_STATUS')
   return result
  except Exception as error:
   response=getattr(error,'response',None);text=response.text if response is not None else None
   if text:text=text.replace(self.key,'[REDACTED_CREDENTIAL]')
   event.update(status='ERROR',error_type=type(error).__name__,error=str(error).replace(self.key,'[REDACTED_CREDENTIAL]'),http_status=response.status_code if response is not None else None,response_body=text,elapsed_seconds=time.monotonic()-started);write(self.dest/'call_ledger.json',self.events)
   raise RuntimeError('DISPATCH_OR_INTEGRITY_FAILURE; see redacted call ledger') from None

def safety_flags(dest,rows):
 flags=[]
 if (dest/'call_ledger.json').exists() and any(x['status']!='RESPONSE' for x in load(dest/'call_ledger.json')):flags.append('PROVIDER_DISPATCH_FAILURE')
 for row in rows:
  if row.get('conflicts'):flags.append('CONTRADICTORY_REVIEWER_FEEDBACK')
  if row.get('reviewer_format_failure'):flags.append('EXHAUSTED_REVIEWER_FORMAT_RETRIES')
  for f in row.get('findings',[]):
   if f['location'].startswith('local runtime'):flags.append('LOCAL_EXECUTION_FAILURE')
   if f['location']=='repair regression guard' and 'maxCount' in f['excerpt']:
    flags.append('POTENTIAL_CARDINALITY_PRESERVATION_CONFLICT_REQUIRES_REVIEW')
 return sorted(set(flags))

def targeted():
 state=load(STATE);group=Path(state['group']);verify_frozen(group)
 if state['arm_A'] is not None:raise RuntimeError('Arm A already started; never rerun for a preferred outcome')
 arm=Project(ROOT).output('experiments',stamp()+'_TRF010_TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC');state['arm_A']=str(arm);write(STATE,state);write(group/'arm_paths.json',state)
 cfg=load(group/'resolved_configs.json')['NLTL'];p=Project(group/'snapshot');schema=Schema(p);context=schema.context(RID)
 write(arm/'context.json',context);write(arm/'resolved_config.json',cfg);write(arm/'arm_definition.json',dict(label='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC',maximum_repair_calls=2,initial_generation_calls=0,not_Single_shot_comparison=True,frozen_snapshot=str((group/'snapshot').relative_to(ROOT))))
 seed_path=ROOT/load(group/'preflight.json')['historical_seed'];seed=Candidate(1,seed_path.read_text(),load(seed_path.parent/'response_001.json')['text'])
 assert seed.sha256==load(group/'preflight.json')['historical_seed_sha256']
 (arm/'candidate_01.ttl').write_bytes(seed_path.read_bytes());(arm/'seed_raw_historical_response.txt').write_text(seed.raw)
 write(arm/'candidate_01.json',dict(version=1,sha256=seed.sha256,origin='Historical byte-identical seed; not a new generation',source=str(seed_path.relative_to(ROOT))))
 fs=check(seed,schema,RID);_,proof=coverage_findings(seed,schema,RID)
 assert any(x['status']=='MISSING_ENUMERATION' for x in proof) and fs and all(f.confirmed for f in fs)
 write(arm/'findings_01.json',[f.asdict() for f in fs]);write(arm/'enumeration_coverage_01.json',proof)
 rows=[dict(version=1,status='HISTORICAL_SEED_DEFECT_CONFIRMED',accepted=False,candidate_sha256=seed.sha256,findings=[f.asdict() for f in fs],request_metrics=[],note='No internal or external result changes the historical pilot.')];write(arm/'history.json',rows)
 credentials();transport=AuditTransport(arm,allowed_generation=0,max_repairs=2);runner=Runner(p,cfg,transport,arm);runner.latest_findings=tuple(fs);previous=seed;oldfindings=fs;started=time.monotonic();status='REPAIR_LIMIT_EXHAUSTED';failure=None
 try:
  for repair_index in [1,2]:
   # Uses the production renderer, independent findings reference and live-boundary integrity guard.
   request=repair_request(p,context,previous,oldfindings);assert request['route'] in ['targeted_repair','syntax_repair'];call_start=runner.sequence
   response=runner.dispatch(request,previous);raw=response['text'];error=None;normalization=None
   try:code,normalization=normalize(raw)
   except WrapperError as e:code=raw;error=str(e)
   current=Candidate(previous.version+1,code,raw);(arm/f'candidate_{current.version:02d}.ttl').write_text(code)
   write(arm/f'candidate_{current.version:02d}.json',dict(version=current.version,sha256=current.sha256,origin='Live targeted repair',repair_index=repair_index,normalization=normalization))
   (arm/f'diff_{previous.version:02d}_{current.version:02d}.patch').write_text(''.join(difflib.unified_diff(previous.code.splitlines(True),current.code.splitlines(True),fromfile=f'v{previous.version}',tofile=f'v{current.version}')))
   current_findings=[finding(current,'RESPONSE_FORMAT_ERROR','Missing/ambiguous response wrapper',raw,expected='<BEGIN_SHACL> and <END_SHACL>',evidence='Production wrapper contract',suggestion='Return one complete candidate block.',diagnostic=error)] if error else check(current,schema,RID)
   if not error:
    current_findings+=regression(previous,current,oldfindings)
    if not any(f.category=='PARSE_ERROR' for f in current_findings):
     _,report=coverage_findings(current,schema,RID);write(arm/f'enumeration_coverage_{current.version:02d}.json',report)
   obj=None;review_error=None;conflicts=[]
   if not current_findings:
    runtime_findings,probe=runtime_probe(current,schema);current_findings+=runtime_findings;write(arm/f'runtime_probe_{current.version:02d}.json',probe)
   if not current_findings:
    obj,semantic,review_error=runner.review(current,context);current_findings+=semantic
    if obj:conflicts=__import__('nltlv2.requests',fromlist=['review_conflicts']).review_conflicts(obj,schema,RID)
   accepted=not current_findings and not review_error and not conflicts
   status='ACCEPTED' if accepted else 'CONFLICT' if conflicts else 'REVIEWER_FORMAT_FAILURE' if review_error else 'UNRESOLVED_CONTEXT' if any(not f.confirmed for f in current_findings) else 'REJECTED'
   row=dict(version=current.version,repair_index=repair_index,status=status,accepted=accepted,candidate_sha256=current.sha256,findings=[f.asdict() for f in current_findings],changes=transitions(oldfindings,current_findings),review=obj,reviewer_format_failure=review_error,conflicts=conflicts,request_metrics=runner.response_metrics[call_start:]);rows.append(row)
   write(arm/'history.json',rows);write(arm/f'findings_{current.version:02d}.json',[f.asdict() for f in current_findings]);runner.latest_findings=tuple(current_findings)
   flags=safety_flags(arm,rows)
   if accepted or flags or any(not f.confirmed for f in current_findings):break
   previous=current;oldfindings=current_findings
  else:status='REPAIR_LIMIT_EXHAUSTED'
 except Exception as e:
  failure=dict(type=type(e).__name__,message=str(e));status='OPERATIONAL_FAILURE';write(arm/'operational_failure.json',failure)
 result=dict(label='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC',requirement_id=RID,status=status,historical_seed_sha256=seed.sha256,initial_generation_calls=0,repair_calls=sum(e['route'].endswith('repair') for e in transport.events),review_calls=sum(e['route']=='review' for e in transport.events),auxiliary_format_retries=sum(e['route']=='review_format_retry' for e in transport.events),accepted_version=next((r['version'] for r in rows if r.get('accepted')),None),elapsed_seconds=time.monotonic()-started,history=rows,not_fresh_pipeline_performance=True,not_Single_shot_comparison=True,safety_flags=safety_flags(arm,rows)+(['OPERATIONAL_OR_INTEGRITY_FAILURE'] if failure else []))
 write(arm/'run.json',result);write(group/'arm_A_completion.json',dict(path=str(arm.relative_to(ROOT)),status=status,safety_flags=result['safety_flags'],next_arm='REQUIRES_EXPLICIT_EVIDENCE_REVIEW_BEFORE_START'))
 print(json.dumps({k:v for k,v in result.items() if k!='history'},indent=2),flush=True);print('ARM_A='+str(arm),flush=True)

def fresh():
 state=load(STATE);group=Path(state['group']);verify_frozen(group)
 if not state['arm_A'] or state['arm_B']:raise RuntimeError('Arm order/repetition violation')
 gate=load(group/'arm_A_safety_gate.json')
 if gate.get('decision')!='PROCEED_TO_B' or gate.get('safety_flags'):raise RuntimeError('Arm A safety gate prevents next arm')
 arm=Project(ROOT).output('experiments',stamp()+'_TRF010_FRESH_PAIRED_DEVELOPMENT_PILOT');state['arm_B']=str(arm);write(STATE,state);write(group/'arm_paths.json',state)
 p=Project(group/'snapshot');configs=load(group/'resolved_configs.json');credentials();results={};started=time.monotonic()
 write(arm/'arm_definition.json',dict(label='FRESH_PAIRED_DEVELOPMENT_PILOT',requirement_id=RID,frozen_snapshot=str((group/'snapshot').relative_to(ROOT)),single_shot_generation_calls=1,nltl_maximum_candidate_attempts=6,reruns_for_preferred_outcome=False))
 for method,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
  dest=arm/folder;dest.mkdir();cfg=configs[method];write(dest/'resolved_config.json',cfg);transport=AuditTransport(dest,allowed_generation=1,max_repairs=0 if method=='Single-shot' else 5)
  print('START_B '+method,flush=True)
  try:
   result=Runner(p,cfg,transport,dest).run(RID);flags=safety_flags(dest,result['history']);results[method]=dict(status=result['status'],candidate_attempts=result['candidate_attempts'],accepted_version=result['accepted_version'],safety_flags=flags)
   print('FINISHED_B '+method+' '+result['status']+' candidates='+str(result['candidate_attempts']),flush=True)
  except Exception as e:
   results[method]=dict(status='OPERATIONAL_FAILURE',error_type=type(e).__name__,message=str(e),safety_flags=['OPERATIONAL_OR_INTEGRITY_FAILURE']);write(dest/'operational_failure.json',results[method]);break
  write(arm/'execution_outcomes.json',results)
  if flags:break
 write(arm/'execution_outcomes.json',dict(label='FRESH_PAIRED_DEVELOPMENT_PILOT',requirement_id=RID,methods=results,elapsed_seconds=time.monotonic()-started))
 if all((arm/x/'request_001.json').is_file() for x in ['single_shot','nltl']):
  assert load(arm/'single_shot/request_001.json')==load(arm/'nltl/request_001.json');write(arm/'initial_request_equality.json',dict(equal=True,sha256=digest(json.dumps(load(arm/'nltl/request_001.json'),ensure_ascii=False))))
 print('ARM_B='+str(arm),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','targeted','fresh']);args=parser.parse_args();{'prepare':prepare,'targeted':targeted,'fresh':fresh}[args.phase]()
