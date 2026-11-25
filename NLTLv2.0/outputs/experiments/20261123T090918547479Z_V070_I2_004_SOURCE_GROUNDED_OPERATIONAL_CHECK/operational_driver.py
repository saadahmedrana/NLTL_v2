"""Orchestration only: one fresh frozen v0.7.0 NLTL operational check, no evaluator imports."""
from pathlib import Path
import argparse,hashlib,importlib,importlib.metadata,json,os,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest,Candidate
from nltlv2.schema import Schema,TERM_FIELDS
from nltlv2.requests import initial_request,assert_integrity
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport,provider_payload
from nltlv2.review_protocol import response_format
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent;ENV=REPO.parent/'env/NLTL_v2.env';RID='I2-004';STATE=Path('/private/tmp/v070_i2004_operational_state.json');GIT='/Library/Developer/CommandLineTools/usr/bin/git'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def git(*args):return subprocess.run([GIT,'-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def prepare():
 assert not STATE.exists(),'No duplicate preparation or preferred-outcome rerun'
 assert importlib.metadata.version('nltlv2-refined')=='0.7.0'
 import nltlv2
 identity={}
 for f in (ROOT/'src/nltlv2').glob('*.py'):
  installed=Path(nltlv2.__file__).parent/f.name;assert f.read_bytes()==installed.read_bytes();identity[str(f.relative_to(ROOT))]=dict(sha256=sha(f),installed=str(installed))
 p=Project(ROOT);cfg=p.config('configs/v070_bounded_live_check.json')
 assert cfg['method']=='NLTL' and cfg['maximum_candidate_attempts']==2 and cfg['review_format_retries']==1 and cfg['pipeline_version']=='0.7.0'
 assert not cfg.get('seed_candidate') and cfg['fresh_regeneration'] is False and response_format(cfg) is None and cfg['review_output_mode']=='bounded_json' and cfg['provider_capabilities']['responses_text_json_schema'] is False
 schema=Schema(GenerationProject(ROOT));context=schema.context(RID);assert context['examples']==[]
 previous={str(f.relative_to(ROOT)):sha(f) for f in (ROOT/'outputs').rglob('*') if f.is_file()}
 group=p.output('experiments',stamp()+'_V070_I2_004_SOURCE_GROUNDED_OPERATIONAL_CHECK');write(STATE,dict(group=str(group),status='PREPARING'))
 for name,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=all']),('working_tree_diff.patch',['diff','--binary']),('index_diff.patch',['diff','--cached','--binary'])]:(group/name).write_text(git(*args))
 write(group/'historical_hashes_before.json',previous);write(group/'installed_source_identity.json',identity)
 snap=group/'snapshot';snap.mkdir()
 for folder in ['src/nltlv2','prompts','configs']:shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 inputs=['pyproject.toml','requirements-lock.txt','schema/Schema_for_NLTL.ttl','schema/locked_representation_context.jsonld','schema/representation_bindings.json']+list({d['file'] for d in context['source_documents']})
 for name in inputs:
  dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
 requirements=load(ROOT/'data/requirements/requirements.json');fields={'id','source','clause','text','source_file','source_sha256','supporting_sources'};write(snap/'data/requirements/requirements.json',{RID:{k:v for k,v in requirements[RID].items() if k in fields}})
 catalog=load(ROOT/'data/requirements/source_catalog.json');catalog['sources']={k:v for k,v in catalog['sources'].items() if k==requirements[RID]['source']};write(snap/'data/requirements/source_catalog.json',catalog)
 write(snap/'schema/term_registry.json',[{k:v for k,v in r.items() if k in TERM_FIELDS} for r in load(ROOT/'schema/term_registry.json')])
 frozen=Schema(GenerationProject(snap));assert frozen.context(RID)==context,'Snapshot projection must not alter rendered context'
 settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']};expected=initial_request(GenerationProject(snap),context,settings);write(group/'expected_initial_request.json',expected);write(group/'preflight_context.json',context);write(group/'preflight_source_selection_manifest.json',frozen.source_manifests[RID])
 runtime=dict(cfg,network_enabled=True,proposal_only=False,run_label='V070_SOURCE_GROUNDED_BOUNDED_OPERATIONAL_CHECK');write(group/'base_config.json',cfg);write(group/'resolved_config.json',runtime)
 hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 originals=set(inputs)|{'schema/term_registry.json','data/requirements/requirements.json','data/requirements/source_catalog.json','configs/v070_bounded_live_check.json'}|{str(f.relative_to(ROOT)) for folder in ['src/nltlv2','prompts'] for f in (ROOT/folder).glob('*') if f.is_file()}
 write(group/'original_input_hashes.json',{name:sha(ROOT/name) for name in sorted(originals)})
 from dotenv import dotenv_values
 env=dotenv_values(ENV);u=urllib.parse.urlsplit(env['AALTO_RESPONSES_BASE_URL']);assert env.get('AALTO_API_KEY') and u.scheme=='https' and not any([u.username,u.password,u.query,u.fragment]) and not ENV.is_relative_to(ROOT)
 # Pre-dispatch dry-run checks integrity guards, not model-generated compliance behavior.
 from nltlv2.core import finding
 from nltlv2.requests import repair_request
 c=Candidate(1,'<urn:software-integrity-control> <urn:p> <urn:o> .\n','RAW_WRAPPER_NOT_A_SUBSTITUTE');f=finding(c,'PARSE_ERROR','synthetic integrity diagnostic',suggestion='Software-only dry run')
 packet=repair_request(GenerationProject(snap),context,c,[f]);ok=assert_integrity(packet,c,[f]);bad=json.loads(json.dumps(packet));bad['payload']['previous_candidate']=c.code[:-3];bad['user']=json.dumps(bad['payload'])
 try:assert_integrity(bad,c,[f])
 except ValueError:rejected=True
 else:raise AssertionError('Truncated current-code dry run did not reject')
 write(group/'pre_dispatch_integrity_check.json',dict(full_code=ok,truncated_code_rejected=rejected,not_a_generation_or_compliance_witness=True))
 write(group/'preflight.json',dict(version='0.7.0',requirement=RID,label='SOURCE_GROUNDED_OPERATIONAL_CHECK',git_revision=git('rev-parse','HEAD').strip(),git_state='Recorded exact modified/untracked tree; frozen version is identified by snapshot and installed/source hashes, not claimed as a clean committed v0.7 tag',installed_source_identical=True,config_path='configs/v070_bounded_live_check.json',base_config_sha256=sha(ROOT/'configs/v070_bounded_live_check.json'),max_candidates=2,initial_generations=1,max_repairs=1,review_format_retries=1,structured_output=False,capability_probes=0,fresh_regeneration=False,seed=False,examples=[],external_credential_location=str(ENV),key_present=True,secrets_logged=False,model=cfg['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,dependencies={x:importlib.metadata.version(x) for x in ['rdflib','pyshacl','requests','python-dotenv']},schema_sha256=hashes['schema/Schema_for_NLTL.ttl'],production_boundary='Source-only snapshot + GenerationProject capability + filesystem audit denying original project/history, evaluation, tests, witnesses, solutions and provenance; separately tested at runtime.',scope='One operational check, no Single-shot comparison, no batch/study. Evaluate only after dispatch closes.'))
 shutil.copyfile(__file__,group/'operational_driver.py');write(STATE,dict(group=str(group),status='PREPARED'));print('PREPARED '+str(group),flush=True)

def verify(group):
 for name,h in load(group/'snapshot_hashes.json').items():assert sha(group/'snapshot'/name)==h,'SNAPSHOT_INTEGRITY_FAILURE '+name
 for name,h in load(group/'original_input_hashes.json').items():assert sha(ROOT/name)==h,'ORIGINAL_INPUT_INTEGRITY_FAILURE '+name

def firewall(group,events):
 snap=group/'snapshot';blocked=[snap/p for p in ['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']]
 def audit(event,args):
  if event=='import' and args and any(str(args[0]).startswith('nltlv2.'+m) for m in ['evaluation','development_checks','enumerations','constraint_changes','preflight']):raise RuntimeError('FORBIDDEN_SOLUTION_IMPORT')
  if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
   f=Path(os.fsdecode(args[0])).resolve()
   if f.is_relative_to(REPO/'MVP') or (f.is_relative_to(ROOT) and not f.is_relative_to(group)) or any(f==p or f.is_relative_to(p) for p in blocked):raise PermissionError('FORBIDDEN_EVALUATION_WITNESS_SOLUTION_HISTORY_ACCESS')
   if f.is_relative_to(snap/'data/requirements'):events.append(dict(event='source_file_open',path=str(f.relative_to(snap))))
 sys.addaudithook(audit)

class AuditTransport(LiveTransport):
 def __init__(self,group,dest,expected):super().__init__(enabled=True,project_root=ROOT);self.group=group;self.dest=dest;self.expected=expected;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route'];assert route in ['generation','syntax_repair','targeted_repair','review','review_format_retry'],'ROUTE_INTEGRITY_FAILURE'
  assert sum(e['route']=='generation' for e in self.events)+(route=='generation')<=1,'GENERATION_LIMIT_INTEGRITY_FAILURE'
  assert sum(e['route'].endswith('repair') for e in self.events)+route.endswith('repair')<=1,'REPAIR_LIMIT_INTEGRITY_FAILURE'
  assert sum(e['route']=='review' for e in self.events)+(route=='review')<=2
  assert sum(e['route']=='review_format_retry' for e in self.events)+(route=='review_format_retry')<=2
  assert len(self.events)<6,'REQUEST_LIMIT_INTEGRITY_FAILURE'
  for name,h in load(self.group/'snapshot_hashes.json').items():assert sha(self.group/'snapshot'/name)==h,'SNAPSHOT_INTEGRITY_FAILURE'
  for name,meta in load(self.group/'installed_source_identity.json').items():assert sha(meta['installed'])==meta['sha256'],'INSTALLED_CODE_INTEGRITY_FAILURE'
  if route=='generation':assert not self.events and all(request[k]==self.expected[k] for k in ['route','system','user']),'INITIAL_CONTEXT_INTEGRITY_FAILURE'
  if route.endswith('repair'):
   assert latest is not None and expected_findings is not None
   code=(self.dest/f'candidate_{latest.version:02d}.ttl').read_text();assert code==latest.code and digest(code)==latest.sha256,'LATEST_CODE_INTEGRITY_FAILURE';check=assert_integrity(request,latest,expected_findings)
   write(self.dest/f'live_repair_boundary_{len(self.events)+1:03d}.json',dict(check,previous_artifact=str((self.dest/f'candidate_{latest.version:02d}.ttl').relative_to(self.group)),full_extracted_code_supplied=True,raw_response_not_used_as_substitute=True))
  body=provider_payload(request);assert 'text' not in body,'STRUCTURED_OUTPUT_MUST_REMAIN_DISABLED';index=len(self.events)+1;u=urllib.parse.urlsplit(self.url)
  write(self.dest/f'provider_request_{index:03d}.json',dict(endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,authentication='External header omitted',body=body))
  e=dict(index=index,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(body)),status='DISPATCHING');self.events.append(e);write(self.dest/'call_ledger.json',self.events);print('CALL '+str(index)+' '+route,flush=True);start=time.monotonic()
  try:
   response=super().dispatch(request,latest,expected_findings);write(self.dest/f'provider_response_{index:03d}.json',response);p=response.get('provider_response',{});e.update(status='RESPONSE',provider_id=p.get('id'),provider_model=p.get('model'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'));write(self.dest/'call_ledger.json',self.events)
   assert p.get('model') in [None,request['model']],'PROVIDER_MODEL_INTEGRITY_FAILURE'
   assert response.get('status') in ['completed','incomplete',None],'PROVIDER_STATUS_FAILURE'
   return response
  except Exception as error:
   resp=getattr(error,'response',None);text=resp.text if resp is not None else None;e.update(status='ERROR',error_type=type(error).__name__,error=str(error).replace(self.key,'[REDACTED]'),http_status=resp.status_code if resp is not None else None,response_body=text.replace(self.key,'[REDACTED]') if text else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events);raise RuntimeError('PROVIDER_DISPATCH_FAILURE; see redacted ledger') from None

def run():
 state=load(STATE);assert state['status']=='PREPARED','No repeat dispatch';group=Path(state['group']);verify(group);cfg=load(group/'resolved_config.json');expected=load(group/'expected_initial_request.json');os.environ.update(NLTL_ENV_FILE=str(ENV),NLTL_ALLOW_MODEL_CALLS='YES')
 source_events=[];firewall(group,source_events)
 # Verify denials before model dispatch, using read attempts with no content returned.
 denied=[]
 for path in [ROOT/'evaluation/selections/regression_core.json',ROOT/'tests/data/legacy_regulatory_witnesses.json',ROOT/'schema/provenance/requirement_term_index_R13_original.json',ROOT/'outputs/experiments',group/'snapshot/data/contracts/solution_profiles.json',group/'snapshot/evaluation/labels.json']:
  try:path.open('rb')
  except PermissionError:denied.append(str(path))
  else:raise RuntimeError('BOUNDARY_INTEGRITY_FAILURE')
 write(group/'runtime_boundary_verification.json',dict(denied=denied,all_blocked=True,content_read=False))
 dest=group/RID/'nltl';dest.mkdir(parents=True);transport=AuditTransport(group,dest,expected);state['status']='RUNNING';write(STATE,state);start=time.monotonic()
 try:
  result=Runner(Project(group/'snapshot'),cfg,transport,dest).run(RID);state.update(status='DISPATCH_CLOSED',outcome=result['status'],accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts'],elapsed_seconds=time.monotonic()-start)
 except Exception as error:
  write(group/'driver_failure.json',dict(type=type(error).__name__,diagnostic=str(error).replace(transport.key,'[REDACTED]'),no_retry=True));state.update(status='DISPATCH_CLOSED',outcome='DRIVER_FAILURE',elapsed_seconds=time.monotonic()-start)
 write(group/'source_retrievals.json',dict(source_file_open_events=source_events,initial_selection_manifest='I2-004/nltl/source_selection_manifest.json',expanded_span_retrievals=[],note='Frozen Runner has no autonomous evidence-fetch tool route; no additional source-span retrieval was requested or injected. All selected exact fragments/hashes are preserved.'))
 write(STATE,state);write(group/'dispatch_closed.json',state);print('DISPATCH_CLOSED '+state['outcome'],flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);args=p.parse_args();prepare() if args.action=='prepare' else run()
