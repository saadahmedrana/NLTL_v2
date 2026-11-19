"""Frozen v0.5.0 TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC orchestration.
No external evaluation imports/data; production Runner and LiveTransport unchanged.
"""
from pathlib import Path
import argparse,hashlib,importlib.metadata,json,os,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport
from nltlv2.requests import assert_integrity
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent
ENV=REPO.parent/'env/NLTL_v2.env';STATE=Path('/private/tmp/imo_001_v050_targeted_state_20261119.json');LABEL='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC'
SEED='d343219b4548a6c5fe6fe524421158c7e54f9eb41aa2a170e5c5870e5ab499da'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def git(*args):return subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/git','-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def prepare():
 if STATE.exists():raise RuntimeError('State already exists; refusing another diagnostic')
 p=Project(ROOT);cfg=p.config('configs/imo_001_selector_repair_diagnostic.json');import nltlv2
 assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.5.0'
 assert all(f.read_bytes()==(Path(nltlv2.__file__).parent/f.name).read_bytes() for f in (ROOT/'src/nltlv2').glob('*.py'))
 bundle=load(ROOT/'docs/bundle_manifest.json');assert all(sha(ROOT/name)==h for name,h in bundle['files'].items())
 assert cfg['seed_candidate']['sha256']==SEED==sha(ROOT/cfg['seed_candidate']['path'])
 assert cfg['maximum_candidate_attempts']==3 and cfg['maximum_repair_calls']==2 and cfg['initial_generation_calls']==0 and not cfg['fresh_regeneration'] and not cfg['stagnation']['enabled']
 historical={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'outputs').rglob('*') if f.is_file()}
 group=p.output('experiments',stamp()+'_V050_IMO_001_'+LABEL);write(STATE,dict(group=str(group),status='PREPARING'))
 write(group/'historical_artifact_hashes_before.json',historical)
 for file,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=normal']),('working_tree_diff.patch',['diff','--','NLTLv2.0']),('index_diff.patch',['diff','--cached','--','NLTLv2.0'])]:(group/file).write_text(git(*args))
 snapshot=group/'snapshot';snapshot.mkdir()
 for directory in ['src','prompts','configs','schema','data','smoke_tests/regression_inputs']:shutil.copytree(ROOT/directory,snapshot/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info','.DS_Store'))
 for name in ['pyproject.toml','requirements-lock.txt','README.md']:shutil.copyfile(ROOT/name,snapshot/name)
 hashes={str(f.relative_to(snapshot)):sha(f) for f in snapshot.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes);shutil.copyfile(__file__,group/'diagnostic_driver.py')
 frozen=GenerationProject(snapshot);assert not (snapshot/'evaluation').exists()
 for path in ['evaluation/fixtures/foo.ttl','outputs/old_results.json','results/labels.json']:
  try:frozen.path(path)
  except ValueError:pass
  else:raise RuntimeError('Generation resource firewall failed')
 from dotenv import dotenv_values
 values=dotenv_values(ENV);url=values['AALTO_RESPONSES_BASE_URL'];u=urllib.parse.urlsplit(url)
 assert values.get('AALTO_API_KEY') and u.scheme=='https' and not any([u.username,u.password,u.query,u.fragment])
 resolved=dict(cfg,network_enabled=True,model_calls_authorized=True,prepared_only=False)
 write(group/'resolved_config.json',resolved);write(group/'preflight.json',dict(label=LABEL,version='0.5.0',requirement='IMO-001',installed_source_identical=True,seed_sha256=SEED,base_config_sha256=sha(ROOT/'configs/imo_001_selector_repair_diagnostic.json'),runtime_overlay={'network_enabled':True,'model_calls_authorized':True,'prepared_only':False},initial_generation_calls=0,maximum_repair_calls=2,review_format_retries=cfg['review_format_retries'],maximum_candidate_attempts=3,model=cfg['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,external_credential_location=str(ENV),credential_present=True,secrets_logged=False,schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],dependencies={n:importlib.metadata.version(n) for n in ['rdflib','pyshacl','requests','python-dotenv']},evaluation_firewall='No evaluation in snapshot; GenerationProject API restriction and runtime audit prohibit original evaluation, prior outputs and old MVP reads. Evaluation only in a later offline process.',no_historical_scores_changed=True))
 write(STATE,dict(group=str(group),status='PREPARED'));print('PREPARED '+str(group),flush=True)

def verify(group):
 for name,h in load(group/'snapshot_hashes.json').items():
  if sha(group/'snapshot'/name)!=h or sha(ROOT/name)!=h:raise RuntimeError('FROZEN_INPUT_CHANGED: '+name)

def firewall(group):
 blocked=[ROOT/'evaluation',ROOT/'results',REPO/'MVP']
 def audit(event,args):
  if event=='import' and args and str(args[0]).startswith('nltlv2.evaluation'):raise RuntimeError('EVALUATION_IMPORT_FORBIDDEN')
  if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
   file=Path(os.fsdecode(args[0])).resolve()
   if any(file==x or file.is_relative_to(x) for x in blocked) or (file.is_relative_to(ROOT/'outputs') and not file.is_relative_to(group)):raise RuntimeError('EVALUATION_OR_HISTORY_READ_FORBIDDEN_DURING_REPAIR')
 sys.addaudithook(audit)

class AuditTransport(LiveTransport):
 def __init__(self,dest):super().__init__(enabled=True,project_root=ROOT);self.dest=dest;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  verify(self.dest.parent)
  import nltlv2
  assert all(f.read_bytes()==(Path(nltlv2.__file__).parent/f.name).read_bytes() for f in (self.dest.parent/'snapshot/src/nltlv2').glob('*.py'))
  route=request['route']
  if route in ['generation','fresh_regeneration']:raise RuntimeError('INITIAL_GENERATION_AND_REGENERATION_FORBIDDEN')
  if route not in ['targeted_repair','syntax_repair','review','review_format_retry']:raise RuntimeError('UNEXPECTED_ROUTE')
  if route.endswith('repair'):
   if sum(e['route'].endswith('repair') for e in self.events)>=2:raise RuntimeError('REPAIR_CALL_LIMIT')
   assert_integrity(request,latest,expected_findings)
  if route=='review' and sum(e['route']=='review' for e in self.events)>=2:raise RuntimeError('REVIEW_CALL_LIMIT')
  if route=='review_format_retry' and sum(e['route']=='review_format_retry' for e in self.events)>=2:raise RuntimeError('FORMAT_RETRY_LIMIT')
  if len(self.events)>=6:raise RuntimeError('TOTAL_BOUNDED_CALL_LIMIT')
  index=len(self.events)+1;u=urllib.parse.urlsplit(self.url);body=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  write(self.dest/f'provider_request_{index:03d}.json',dict(label=LABEL,endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,authentication='External header; secret value omitted',body=body))
  event=dict(index=index,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(body)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events);print('CALL '+str(index)+' '+route,flush=True);start=time.monotonic()
  try:
   result=super().dispatch(request,latest,expected_findings);provider=result.get('provider_response',{});write(self.dest/f'provider_response_{index:03d}.json',result)
   event.update(status='RESPONSE',provider_model=provider.get('model'),provider_id=provider.get('id'),response_status=result.get('status'),finish_reason=result.get('finish_reason'),usage=result.get('usage',{}),elapsed_seconds=result.get('elapsed_seconds'))
   if provider.get('model')!=request['model']:raise RuntimeError('PROVIDER_MODEL_MISMATCH')
   if result.get('status') not in ['completed','incomplete',None]:raise RuntimeError('UNEXPECTED_PROVIDER_STATUS')
   write(self.dest/'call_ledger.json',self.events);return result
  except Exception as error:
   response=getattr(error,'response',None);text=response.text if response is not None else None
   event.update(status='ERROR',error_type=type(error).__name__,error=str(error).replace(self.key,'[REDACTED_CREDENTIAL]'),http_status=response.status_code if response is not None else None,response_body=text.replace(self.key,'[REDACTED_CREDENTIAL]') if text else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events)
   raise RuntimeError('PROVIDER_OR_INTEGRITY_FAILURE; see redacted call ledger') from None

def run():
 state=load(STATE);assert state['status']=='PREPARED';group=Path(state['group']);verify(group);firewall(group)
 os.environ['NLTL_ALLOW_MODEL_CALLS']='YES';os.environ['NLTL_ENV_FILE']=str(ENV)
 cfg=load(group/'resolved_config.json');dest=group/'diagnostic';dest.mkdir(exist_ok=False);transport=AuditTransport(dest);state['status']='RUNNING';write(STATE,state);started=time.monotonic()
 result=Runner(Project(group/'snapshot'),cfg,transport,dest).run('IMO-001');verify(group)
 assert result['generation_calls']==0 and sum(e['route'].endswith('repair') for e in transport.events)<=2 and result['candidate_attempts']<=3
 state['status']='DIAGNOSTIC_FINISHED';state['production_status']=result['status'];state['accepted_version']=result['accepted_version'];write(STATE,state)
 write(group/'execution_completion.json',dict(label=LABEL,version='0.5.0',status=result['status'],accepted_version=result['accepted_version'],seed_sha256=SEED,initial_generation_calls=0,repair_calls=sum(e['route'].endswith('repair') for e in transport.events),review_calls=sum(e['route']=='review' for e in transport.events),auxiliary_format_retries=sum(e['route']=='review_format_retry' for e in transport.events),elapsed_seconds=time.monotonic()-started,evaluation_started=False))
 print('FINISHED '+result['status']+' accepted='+str(result['accepted_version'])+' '+str(group),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','run']);args=parser.parse_args();globals()[args.phase]()
