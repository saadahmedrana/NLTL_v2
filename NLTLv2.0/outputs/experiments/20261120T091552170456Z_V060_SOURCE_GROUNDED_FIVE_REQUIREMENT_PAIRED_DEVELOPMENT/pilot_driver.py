"""Orchestrate only: frozen v0.6.0 paired development pilot, no evaluator imports."""
from pathlib import Path
import argparse,hashlib,importlib,importlib.metadata,json,os,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest
from nltlv2.schema import Schema,TERM_FIELDS
from nltlv2.requests import initial_request,assert_integrity
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent;ENV=REPO.parent/'env/NLTL_v2.env'
STATE=Path('/private/tmp/v060_live_pilot_state_20261120.json');RIDS=['I2-004','I2-005','IMO-001','TRF-010','TRF-035']
GIT='/Library/Developer/CommandLineTools/usr/bin/git'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def git(*args):return subprocess.run([GIT,'-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def prepare():
 if STATE.exists():raise RuntimeError('Pilot already prepared; no repeated preparation/dispatch')
 assert importlib.metadata.version('nltlv2-refined')=='0.6.0'
 import nltlv2
 identity={}
 for f in (ROOT/'src/nltlv2').glob('*.py'):
  installed=Path(nltlv2.__file__).parent/f.name;assert f.read_bytes()==installed.read_bytes();identity[str(f.relative_to(ROOT))]=dict(sha256=sha(f),installed=str(installed))
 head=git('rev-parse','HEAD').strip();remote=git('ls-remote','origin','refs/heads/main').split()[0];assert head==remote
 assert not git('status','--porcelain=v1').strip(),'Working tree changed before freeze'
 p=Project(ROOT);configs={'Single-shot':p.config('configs/single_shot.json'),'NLTL':p.config('configs/nltl.json')}
 assert configs['Single-shot']['maximum_candidate_attempts']==1 and not configs['Single-shot']['semantic_review']
 assert configs['NLTL']['maximum_candidate_attempts']==6 and configs['NLTL']['semantic_review'] and not configs['NLTL']['fresh_regeneration']
 schema=Schema(p);contexts={rid:schema.context(rid) for rid in RIDS}
 assert all(c['examples']==[] for c in contexts.values())
 initial_settings=lambda c:{k:c[k] for k in ['model','generation_max_tokens','review_max_tokens']}
 assert initial_settings(configs['Single-shot'])==initial_settings(configs['NLTL'])
 historical={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'outputs').rglob('*') if f.is_file()}
 group=p.output('experiments',stamp()+'_V060_SOURCE_GROUNDED_FIVE_REQUIREMENT_PAIRED_DEVELOPMENT')
 write(STATE,dict(group=str(group),status='PREPARING',started=[],completed=[]))
 for name,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=all']),('working_tree_diff.patch',['diff','--binary']),('index_diff.patch',['diff','--cached','--binary'])]:(group/name).write_text(git(*args))
 write(group/'historical_hashes_before.json',historical);write(group/'installed_source_identity.json',identity)
 snap=group/'snapshot';snap.mkdir()
 for folder in ['src/nltlv2','prompts','configs']:
  shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 inputs=['pyproject.toml','requirements-lock.txt','schema/Schema_for_NLTL.ttl','schema/locked_representation_context.jsonld','schema/representation_bindings.json']
 for rid in RIDS:inputs.extend(d['file'] for d in contexts[rid]['source_documents'])
 for name in sorted(set(inputs)):
  dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
 # Drop ignored preparation fields entirely. Assert rendered requests unchanged below.
 requirements=load(ROOT/'data/requirements/requirements.json')
 safe_fields={'id','source','clause','text','source_file','source_sha256','supporting_sources'}
 projected={rid:{k:v for k,v in requirements[rid].items() if k in safe_fields} for rid in RIDS}
 write(snap/'data/requirements/requirements.json',projected)
 catalog=load(ROOT/'data/requirements/source_catalog.json');catalog['sources']={k:v for k,v in catalog['sources'].items() if k in {requirements[r]['source'] for r in RIDS}}
 write(snap/'data/requirements/source_catalog.json',catalog)
 write(snap/'schema/term_registry.json',[{k:v for k,v in r.items() if k in TERM_FIELDS} for r in load(ROOT/'schema/term_registry.json')])
 frozen=Project(snap);frozen_schema=Schema(GenerationProject(snap));equal={}
 for rid in RIDS:
  context=frozen_schema.context(rid);assert context==contexts[rid],rid
  reqs=[initial_request(GenerationProject(snap),context,initial_settings(c)) for c in configs.values()];assert reqs[0]==reqs[1]
  equal[rid]=dict(identical=True,context_sha256=digest(json.dumps(context,ensure_ascii=False)),initial_request_sha256=digest(json.dumps(reqs[0],ensure_ascii=False)),examples=[],initial_request=reqs[0])
 write(group/'paired_initial_requests.json',equal)
 for cfg in configs.values():cfg.update(network_enabled=True,run_label='V060_SOURCE_GROUNDED_DEVELOPMENT_PILOT')
 write(group/'resolved_configs.json',configs)
 hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 write(group/'original_input_hashes.json',{str(f.relative_to(ROOT)):sha(f) for f in [ROOT/x for x in sorted(set(inputs)|{'schema/term_registry.json','data/requirements/requirements.json','data/requirements/source_catalog.json'})]+list((ROOT/'prompts').glob('*.txt'))+list((ROOT/'configs').glob('*.json'))+list((ROOT/'src/nltlv2').glob('*.py'))})
 from dotenv import dotenv_values
 env=dotenv_values(ENV);u=urllib.parse.urlsplit(env['AALTO_RESPONSES_BASE_URL']);assert env.get('AALTO_API_KEY') and u.scheme=='https' and not any([u.username,u.password,u.query,u.fragment]);assert ENV.is_file() and not ENV.is_relative_to(ROOT)
 write(group/'preflight.json',dict(version='0.6.0',label='SOURCE_GROUNDED_DEVELOPMENT_PILOT',requirements=RIDS,deferred=['I2-042'],pushed_revision=head,remote_main=remote,working_tree_clean_before_snapshot=True,installed_source_identical=True,model=configs['NLTL']['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,external_credential_location=str(ENV),key_present=True,secrets_logged=False,examples=[],curated_examples_restored=False,initial_requests_identical=True,schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],source_projection='Only fields ignored by frozen Schema.context are omitted; source/context/request identity asserted against originals.',production_evaluation_access=False,production_witness_access=False,execution_probes='Frozen schema-derived empty targets; ignore compliance outcomes; no requirement-specific expected verdicts.',semantic_claims='Model interpretations, not independently verified facts',max_candidates=6,single_shot_calls=1,fresh_regeneration=False,bounded_review_format_retries=configs['NLTL']['review_format_retries'],dependencies={x:importlib.metadata.version(x) for x in ['rdflib','pyshacl','requests','python-dotenv']},no_previous_outputs_seeded=True,evaluation='Separate process after dispatch closes, 30 reviewed cases and 16 counterparts; all primary denominators retained.'))
 write(group/'execution_manifest.json',dict(requirements=RIDS,workflows={'Single-shot':dict(calls=1,review=False,repair=False),'NLTL':dict(max_candidates=6,early_acceptance=True,regeneration=False)},stop_on=['INFRASTRUCTURE_FAILURE','REQUEST_INTEGRITY_FAILURE','CONFLICT','RESOURCE_ATTRIBUTION_UNCERTAIN'],continue_after='Ordinary attempt-budget exhaustion',no_reruns=True))
 shutil.copyfile(__file__,group/'pilot_driver.py');write(STATE,dict(group=str(group),status='PREPARED',started=[],completed=[]));print('PREPARED '+str(group),flush=True)

def verify(group):
 for name,h in load(group/'snapshot_hashes.json').items():
  if sha(group/'snapshot'/name)!=h:raise RuntimeError('FROZEN_SNAPSHOT_INTEGRITY_FAILURE')
 for name,h in load(group/'original_input_hashes.json').items():
  if sha(ROOT/name)!=h:raise RuntimeError('FROZEN_SOURCE_INTEGRITY_FAILURE')

def firewall(group):
 snap=group/'snapshot';production_forbidden=['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']
 def audit(event,args):
  if event=='import' and args and any(str(args[0]).startswith('nltlv2.'+m) for m in ['evaluation','development_checks','enumerations','constraint_changes','preflight']):raise RuntimeError('FORBIDDEN_SOLUTION_IMPORT')
  if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
   f=Path(os.fsdecode(args[0])).resolve()
   if f.is_relative_to(REPO/'MVP') or (f.is_relative_to(ROOT) and not f.is_relative_to(group)):raise RuntimeError('FORBIDDEN_ORIGINAL_HISTORY_EVALUATION_READ')
   if any(f==snap/x or f.is_relative_to(snap/x) for x in production_forbidden):raise RuntimeError('FORBIDDEN_SOLUTION_EVALUATION_WITNESS_READ')
 sys.addaudithook(audit)

class AuditTransport(LiveTransport):
 def __init__(self,dest,method,expected_initial):
  super().__init__(enabled=True,project_root=ROOT);self.dest=dest;self.method=method;self.events=[];self.expected_initial=expected_initial
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route']
  if route=='generation':
   assert not self.events and all(request[k]==self.expected_initial[k] for k in ['system','user','route']),'INITIAL_REQUEST_INTEGRITY_FAILURE'
  if self.method=='Single-shot':assert route=='generation' and not self.events,'SINGLESHOT_INTEGRITY_FAILURE'
  assert route in ['generation','syntax_repair','targeted_repair','review','review_format_retry'],'ROUTE_INTEGRITY_FAILURE'
  assert sum(e['route']=='generation' for e in self.events)+(route=='generation')<=1
  assert sum(e['route'].endswith('repair') for e in self.events)+route.endswith('repair')<=5
  assert len(self.events)<18
  body=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  index=len(self.events)+1;u=urllib.parse.urlsplit(self.url)
  write(self.dest/f'provider_request_{index:03d}.json',dict(endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,body=body,authentication='External header value omitted'))
  event=dict(index=index,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(body)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events)
  print('CALL '+self.dest.parent.name+' '+self.method+' '+str(index)+' '+route,flush=True);start=time.monotonic()
  try:
   response=super().dispatch(request,latest,expected_findings);provider=response.get('provider_response',{});write(self.dest/f'provider_response_{index:03d}.json',response)
   event.update(status='RESPONSE',provider_id=provider.get('id'),provider_model=provider.get('model'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'))
   write(self.dest/'call_ledger.json',self.events)
   if provider.get('model') not in [None,request['model']]:raise RuntimeError('PROVIDER_MODEL_INTEGRITY_FAILURE')
   if response.get('status') not in ['completed','incomplete',None]:raise RuntimeError('PROVIDER_STATUS_FAILURE')
   return response
  except Exception as e:
   resp=getattr(e,'response',None);body=resp.text if resp is not None else None
   event.update(status='ERROR',error_type=type(e).__name__,error=str(e).replace(self.key,'[REDACTED]'),http_status=resp.status_code if resp is not None else None,response_body=body.replace(self.key,'[REDACTED]') if body else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events);raise RuntimeError('PROVIDER_OR_INTEGRITY_FAILURE; see redacted ledger') from None

def run():
 state=load(STATE);assert state['status']=='PREPARED','No reruns or resumes of dispatched workflows';group=Path(state['group']);verify(group)
 configs=load(group/'resolved_configs.json');expected=load(group/'paired_initial_requests.json');os.environ.update(NLTL_ENV_FILE=str(ENV),NLTL_ALLOW_MODEL_CALLS='YES')
 # Instantiate source-bound Runner after firewall installation; no evaluation imported.
 state['status']='RUNNING';write(STATE,state);start=time.monotonic();firewall(group);outcomes={};stop=[]
 # Verification of original hashes occurred before firewall; snapshot hashes checked between workflows.
 for rid in RIDS:
  state['started'].append(rid);write(STATE,state);reqdir=group/rid;reqdir.mkdir();outcomes[rid]={}
  for method,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
   for name,h in load(group/'snapshot_hashes.json').items():assert sha(group/'snapshot'/name)==h,'SNAPSHOT_INTEGRITY_FAILURE'
   dest=reqdir/folder;dest.mkdir();write(dest/'resolved_config.json',configs[method]);print('START '+rid+' '+method,flush=True)
   transport=AuditTransport(dest,method,expected[rid]['initial_request'])
   result=Runner(Project(group/'snapshot'),configs[method],transport,dest).run(rid)
   stop=[e['error_type'] for e in transport.events if e['status']!='RESPONSE']
   if result['status'] in ['INFRASTRUCTURE_FAILURE','REQUEST_INTEGRITY_FAILURE','CONFLICT','RESOURCE_ATTRIBUTION_UNCERTAIN']:stop.append(result['status'])
   if result.get('operational_failure'):stop.append('OPERATIONAL_FAILURE')
   outcomes[rid][method]=dict(status=result['status'],accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts'],stop_flags=stop)
   print('FINISH '+rid+' '+method+' '+result['status']+' candidates='+str(result['candidate_attempts']),flush=True)
   write(group/'generation_progress.json',dict(outcomes=outcomes,elapsed_seconds=time.monotonic()-start,stop=stop))
   if stop:break
  if stop:break
  state['completed'].append(rid);write(STATE,state)
 state.update(status='STOPPED' if stop else 'GENERATION_COMPLETE',outcomes=outcomes,stop_flags=stop,elapsed_seconds=time.monotonic()-start);write(STATE,state);write(group/'dispatch_closed.json',state);print('DISPATCH_CLOSED '+state['status'],flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);a=parser.parse_args();prepare() if a.action=='prepare' else run()
