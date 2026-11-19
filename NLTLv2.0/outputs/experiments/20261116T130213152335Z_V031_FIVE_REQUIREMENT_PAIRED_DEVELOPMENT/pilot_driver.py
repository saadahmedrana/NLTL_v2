"""Bounded v0.3.1 pilot orchestration only; frozen pipeline is never edited.
Generation imports no external evaluation modules and runs from a fixture-free snapshot.
"""
from pathlib import Path
import argparse,collections,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest
from nltlv2.schema import Schema
from nltlv2.preflight import validate_manifest,settings
from nltlv2.requests import initial_request,assert_integrity
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent
ENV=REPO.parent/'env/NLTL_v2.env';STATE=Path('/private/tmp/five_v031_pilot_state_20261116.json')
RIDS=['I2-004','I2-005','IMO-001','TRF-010','TRF-035']
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def git(*args):return subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/git','-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def prepare():
 if STATE.exists():raise RuntimeError('State already exists; no repetition')
 p=Project(ROOT);m=load(p.path('configs/five_requirement_development_pilot.json'));valid=validate_manifest(p,m,require_ready=True)
 assert m['requirements']==RIDS and importlib.metadata.version('nltlv2-refined')=='0.3.1'
 import nltlv2
 assert all(f.read_bytes()==(Path(nltlv2.__file__).parent/f.name).read_bytes() for f in (ROOT/'src/nltlv2').glob('*.py'))
 bundle=load(ROOT/'docs/bundle_manifest.json');assert all(sha(ROOT/name)==h for name,h in bundle['files'].items())
 historical={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'outputs').rglob('*') if f.is_file()}
 group=p.output('experiments',stamp()+'_V031_FIVE_REQUIREMENT_PAIRED_DEVELOPMENT')
 write(group/'historical_artifact_hashes_before.json',historical);write(STATE,dict(group=str(group),status='PREPARING',completed=[],started=[]))
 for file,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=normal']),('working_tree_diff.patch',['diff','--','NLTLv2.0']),('index_diff.patch',['diff','--cached','--','NLTLv2.0'])]: (group/file).write_text(git(*args))
 snapshot=group/'snapshot';snapshot.mkdir()
 for directory in ['src','prompts','configs','schema','data']:shutil.copytree(ROOT/directory,snapshot/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info','.DS_Store'))
 for name in ['pyproject.toml','requirements-lock.txt','README.md']:shutil.copyfile(ROOT/name,snapshot/name)
 hashes={str(f.relative_to(snapshot)):sha(f) for f in snapshot.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 shutil.copyfile(__file__,group/'pilot_driver.py');write(group/'manifest_validation.json',valid)
 configs={method:p.config(file) for method,file in [('Single-shot','configs/single_shot.json'),('NLTL','configs/nltl.json')]}
 for cfg in configs.values():cfg['network_enabled']=True # Runtime authorization overlay only, saved separately.
 assert settings(configs['Single-shot'])==settings(configs['NLTL'])
 frozen=Project(snapshot);schema=Schema(frozen);equal={}
 for rid in RIDS:
  context=schema.context(rid);requests=[initial_request(frozen,context,settings(cfg)) for cfg in configs.values()];assert requests[0]==requests[1]
  assert all(rid not in json.dumps(e) for e in context['examples'])
  equal[rid]=dict(identical=True,request_sha256=digest(json.dumps(requests[0],ensure_ascii=False)),context_sha256=digest(json.dumps(context,ensure_ascii=False)))
 assert not (snapshot/'evaluation').exists() and not (snapshot/'outputs').exists()
 firewall=GenerationProject(snapshot)
 for path in ['evaluation/fixtures/foo.ttl','outputs/old.json','results/labels.json']:
  try:firewall.path(path)
  except ValueError:pass
  else:raise RuntimeError('Resource firewall failure')
 from dotenv import dotenv_values
 env=dotenv_values(ENV);u=urllib.parse.urlsplit(env['AALTO_RESPONSES_BASE_URL']);assert env.get('AALTO_API_KEY') and u.scheme=='https' and not any([u.username,u.password,u.query,u.fragment])
 write(group/'preflight.json',dict(version='0.3.1',requirements=RIDS,deferred=['I2-042'],scope='Bounded development only; not held-out, no prior TRF-010 results pooled',model=configs['NLTL']['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,credential_location=str(ENV),key_present=True,secret_values_logged=False,schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],git_revision=git('rev-parse','HEAD').strip(),paired_requests=equal,source_authored_witnesses_enabled=True,evaluation_firewall='Fixture-free snapshot; GenerationProject resource restriction; runtime audit denies reads of original evaluation and historical outputs and old MVP. Separate evaluation process after generation closes.',limits=m['workflows'],stop_policy='Before next requirement/arm after runtime, integrity, contradictory feedback or exhausted reviewer-format problems; no transport retries.',dependencies={n:importlib.metadata.version(n) for n in ['rdflib','pyshacl','requests','python-dotenv']},model_calls_authorized_by_user=True))
 write(group/'resolved_configs.json',configs);write(STATE,dict(group=str(group),status='PREPARED',completed=[],started=[]));print('PREPARED '+str(group),flush=True)

def verify(group):
 for name,h in load(group/'snapshot_hashes.json').items():
  if sha(group/'snapshot'/name)!=h or sha(ROOT/name)!=h:raise RuntimeError('FROZEN_IMPLEMENTATION_CHANGED: '+name)

def install_audit(group):
 blocked=[ROOT/'evaluation',ROOT/'results',REPO/'MVP']
 def audit(event,args):
  if event=='import' and args and str(args[0]).startswith('nltlv2.evaluation'):raise RuntimeError('EVALUATION_IMPORT_FORBIDDEN_DURING_GENERATION')
  if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
   file=Path(os.fsdecode(args[0])).resolve()
   if any(file==x or file.is_relative_to(x) for x in blocked) or (file.is_relative_to(ROOT/'outputs') and not file.is_relative_to(group)):
    raise RuntimeError('EXTERNAL_EVALUATION_OR_HISTORY_READ_FORBIDDEN')
 sys.addaudithook(audit)

class AuditTransport(LiveTransport):
 def __init__(self,dest,method):
  super().__init__(enabled=True,project_root=ROOT);self.dest=dest;self.method=method;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route']
  if route=='fresh_regeneration':raise RuntimeError('REGENERATION_DISABLED')
  if route=='generation' and any(e['route']=='generation' for e in self.events):raise RuntimeError('INITIAL_CALL_LIMIT')
  if self.method=='Single-shot' and (route!='generation' or self.events):raise RuntimeError('SINGLE_SHOT_ONE_CALL_ONLY')
  if route.endswith('repair'):
   if sum(e['route'].endswith('repair') for e in self.events)>=5:raise RuntimeError('REPAIR_LIMIT')
   assert_integrity(request,latest,expected_findings)
  i=len(self.events)+1;u=urllib.parse.urlsplit(self.url)
  body=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  write(self.dest/f'provider_request_{i:03d}.json',dict(endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,authentication='External header; value omitted',body=body))
  event=dict(index=i,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(body)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events);print('CALL '+self.dest.parent.name+' '+self.method+' '+str(i)+' '+route,flush=True);start=time.monotonic()
  try:
   response=super().dispatch(request,latest,expected_findings);provider=response.get('provider_response',{})
   write(self.dest/f'provider_response_{i:03d}.json',response)
   event.update(status='RESPONSE',provider_model=provider.get('model'),provider_id=provider.get('id'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'))
   if provider.get('model')!=request['model']:raise RuntimeError('UNEXPECTED_PROVIDER_MODEL')
   # Reviewer truncation follows the frozen bounded format-retry policy; code truncation is a preserved output failure.
   if response.get('status') not in ['completed','incomplete',None]:raise RuntimeError('UNEXPECTED_PROVIDER_STATUS')
   write(self.dest/'call_ledger.json',self.events);return response
  except Exception as error:
   resp=getattr(error,'response',None);text=resp.text if resp is not None else None
   event.update(status='ERROR',error_type=type(error).__name__,error=str(error).replace(self.key,'[REDACTED_CREDENTIAL]'),http_status=resp.status_code if resp is not None else None,response_body=text.replace(self.key,'[REDACTED_CREDENTIAL]') if text else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events)
   raise RuntimeError('PROVIDER_OR_INTEGRITY_FAILURE; see redacted ledger') from None

def flags(result,dest):
 issues=[]
 if any(e['status']!='RESPONSE' for e in load(dest/'call_ledger.json')):issues.append('PROVIDER_FAILURE')
 for row in result.get('history',[]):
  if row.get('conflicts'):issues.append('CONTRADICTORY_FEEDBACK')
  if row.get('reviewer_format_failure'):issues.append('EXHAUSTED_REVIEWER_FORMAT_RETRIES')
  if row.get('development_coverage',{}).get('status')=='UNRESOLVED_EXECUTION':issues.append('DEVELOPMENT_EXECUTION_FAILURE')
  for finding in row.get('findings',[]):
   if finding['location'].startswith('local runtime'):issues.append('LOCAL_EXECUTION_FAILURE')
 return sorted(set(issues))

def run():
 state=load(STATE);assert state['status']=='PREPARED';group=Path(state['group']);verify(group);install_audit(group)
 os.environ['NLTL_ENV_FILE']=str(ENV);os.environ['NLTL_ALLOW_MODEL_CALLS']='YES'
 p=Project(group/'snapshot');configs=load(group/'resolved_configs.json');state['status']='RUNNING';write(STATE,state);started=time.monotonic();outcomes={};stop=[]
 for rid in RIDS:
  verify(group);state['started'].append(rid);write(STATE,state);reqdir=group/rid;reqdir.mkdir(exist_ok=False);outcomes[rid]={}
  for method,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
   dest=reqdir/folder;dest.mkdir();cfg=configs[method];write(dest/'resolved_config.json',cfg);transport=AuditTransport(dest,method);print('START '+rid+' '+method,flush=True)
   try:
    result=Runner(p,cfg,transport,dest).run(rid);stop=flags(result,dest);outcomes[rid][method]=dict(status=result['status'],accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts'],safety_flags=stop)
    print('FINISH '+rid+' '+method+' '+result['status']+' candidates='+str(result['candidate_attempts']),flush=True)
   except Exception as e:
    stop=['OPERATIONAL_OR_INTEGRITY_FAILURE'];outcomes[rid][method]=dict(status='OPERATIONAL_FAILURE',error_type=type(e).__name__,message=str(e),safety_flags=stop);write(dest/'operational_failure.json',outcomes[rid][method]);print('STOP '+rid+' '+method+' '+str(e),flush=True)
   write(group/'execution_outcomes.json',dict(version='0.3.1',status='RUNNING',requirements=outcomes,elapsed_seconds=time.monotonic()-started))
   if stop:break
  if (reqdir/'single_shot/request_001.json').exists() and (reqdir/'nltl/request_001.json').exists():
   a=load(reqdir/'single_shot/request_001.json');b=load(reqdir/'nltl/request_001.json');equal=a==b;write(reqdir/'initial_request_equality.json',dict(equal=equal,sha256=digest(json.dumps(a,ensure_ascii=False))))
   if not equal:stop.append('INITIAL_REQUEST_INTEGRITY_FAILURE')
  if stop:break
  state['completed'].append(rid);write(STATE,state)
 state['status']='STOPPED_SAFETY' if stop else 'GENERATION_COMPLETE';state['stop_flags']=stop;write(STATE,state)
 write(group/'execution_outcomes.json',dict(version='0.3.1',status=state['status'],requirements=outcomes,completed_requirements=state['completed'],not_started=[r for r in RIDS if r not in state['started']],stop_flags=stop,elapsed_seconds=time.monotonic()-started,evaluation_started=False))
 print('GENERATION_END '+state['status']+' '+str(group),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','run']);args=parser.parse_args();globals()[args.phase]()
