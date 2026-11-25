"""One authorized v0.9.1 operational run; orchestration only, no evaluator imports."""
from pathlib import Path
import argparse,copy,hashlib,importlib.metadata,json,os,re,shutil,subprocess,sys,time,urllib.parse
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest
from nltlv2.schema import Schema,TERM_FIELDS
from nltlv2.admission import load_admission,definition_hash
from nltlv2.requests import initial_request,assert_integrity
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport,provider_payload
from nltlv2.review_protocol import response_format
import nltlv2
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent;ENV=REPO.parent/'env/NLTL_v2.env';RID='I2-004';STATE=Path('/private/tmp/v091_i2004_live_state.json');GIT='/Library/Developer/CommandLineTools/usr/bin/git'
APPROVAL='''I approve the proposed I2-004 synthetic research-scope declaration
and the two experimental edition selections exactly as presented:
UR I2 Rev.4 (December 2019), with UR I1 Rev.2 (April 2016)
as contextual scope evidence.

Record this instruction as the approval reference. This approval
does not claim real-vessel eligibility or legally governing editions.'''
REFERENCE='User instruction in the current conversation, 2026-11-23 (verbatim approval):\n'+APPROVAL
SCOPE='data/admissions/i2_004_research_scope.approved.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.run([GIT,'-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout
def isolation(request):
 text=json.dumps(request,ensure_ascii=False)
 assert 'https://w3id.org/nltl/benchmark/' not in text,'EVALUATION_NAMESPACE_REQUEST_INTEGRITY_FAILURE'
 assert not re.search(r'I2-\d{3}-[A-Z]-[PF]\d{2}',text),'EVALUATION_CASE_REQUEST_INTEGRITY_FAILURE'
 def walk(x):
  if isinstance(x,dict):
   assert not ({'case_id','admitted_nodes','expected_verdicts','counterfactual_records','behavioral_witnesses','validated_constraint_changes'}&set(x)),'EVALUATION_FIELD_REQUEST_INTEGRITY_FAILURE'
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(request)
 body=json.loads(request['user']);body=body.get('original_request',body)
 ad=body.get('context',{}).get('admission') if request['route'] in ['generation','review','review_format_retry'] else body.get('admission')
 assert ad and set(ad['declaration']['focus_set'])=={'mode','owner_class'},'COMMON_SCOPE_REQUEST_INTEGRITY_FAILURE'
 return dict(no_evaluation_namespace=True,no_case_identifiers=True,no_per_input_binding_fields=True,common_scope_only=True)

def prepare():
 assert not STATE.exists(),'No duplicate run/preferred-outcome rerun'
 assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.9.1'
 identity={}
 for p in sorted((ROOT/'src/nltlv2').glob('*.py')):
  q=Path(nltlv2.__file__).parent/p.name;assert p.read_bytes()==q.read_bytes(),'INSTALLED_SOURCE_IDENTITY_FAILURE';identity[str(p.relative_to(ROOT))]=dict(sha256=sha(p),installed=str(q))
 base=load(ROOT/'configs/v091_bounded_live_check.json');p=Project(ROOT);p.config('configs/v091_bounded_live_check.json')
 assert base['maximum_candidate_attempts']==2 and base['review_format_retries']==1 and base['context_resolution']['max_rounds']==2 and base['context_resolution']['max_reviews_per_run']==4
 assert base['method']=='NLTL' and not base.get('seed_candidate') and base['fresh_regeneration'] is False and base['pipeline_version']=='0.9.1' and response_format(base) is None
 approved=load(ROOT/base['admission_file']);assert approved['approval']['status']=='PROPOSED'
 original_definition=definition_hash(approved)
 approved['approval']=dict(status='APPROVED',approved_by='User in the current conversation',reference=REFERENCE)
 approved['provenance']=dict(declarant='User in the current conversation',reference=REFERENCE,basis='User-approved synthetic research assumption; no real-vessel eligibility or legally governing editions asserted.')
 for e in approved['source_editions']:e['selection_provenance']=REFERENCE+'\nExperimental selection only; not a legal governing-edition determination.'
 assert definition_hash(approved)==original_definition
 assert not (ROOT/SCOPE).exists(),'Preserve any existing approval; do not overwrite'
 # Approval metadata is the only active input change; implementation and draft stay unchanged.
 write(ROOT/SCOPE,approved)
 cfg=dict(base,admission_file=SCOPE,network_enabled=True,proposal_only=False,purpose='Explicitly user-authorized one fresh bounded I2-004 v0.9.1 check')
 schema=Schema(GenerationProject(ROOT));admission=load_admission(p,cfg,schema,RID);assert admission['valid'],admission['errors'];context=schema.context(RID);context['admission']=admission['context'];context['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 assert context['examples']==[]
 group=p.output('experiments',stamp()+'_V091_I2_004_BOUNDED_OPERATIONAL_CHECK');write(STATE,dict(status='PREPARING',group=str(group)))
 previous={str(f.relative_to(ROOT)):sha(f) for folder in ['outputs/experiments','evaluation/fixtures','evaluation/selections'] for f in (ROOT/folder).rglob('*') if f.is_file() and not f.is_relative_to(group)}
 previous['src/nltlv2/tracking.py']=sha(ROOT/'src/nltlv2/tracking.py');write(group/'preserved_hashes_before.json',previous)
 for name,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=all']),('working_diff.patch',['diff','--binary']),('index_diff.patch',['diff','--cached','--binary'])]:(group/name).write_text(git(*args))
 (group/'approval_reference.txt').write_text(REFERENCE+'\n');write(group/'installed_source_identity.json',identity);write(group/'base_config.json',base);write(group/'resolved_config.json',cfg)
 snap=group/'snapshot';snap.mkdir()
 for folder in ['src/nltlv2','prompts']:shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 files=['pyproject.toml','requirements-lock.txt','configs/v091_bounded_live_check.json',SCOPE,'schema/Schema_for_NLTL.ttl','schema/locked_representation_context.jsonld','schema/representation_bindings.json','data/requirements/source_catalog.json']
 catalog=load(ROOT/'data/requirements/source_catalog.json')
 files += [x['file'] for x in catalog['sources'].values()]
 files += [x['provenance']['file'] for x in catalog['sources'].values() if isinstance(x.get('provenance'),dict) and x['provenance'].get('file')]
 for name in sorted(set(files)):
  dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
 selected=load(ROOT/'data/requirements/requirements.json')[RID];fields={'id','source','clause','text','source_file','source_sha256','supporting_sources'};write(snap/'data/requirements/requirements.json',{RID:{k:v for k,v in selected.items() if k in fields}})
 write(snap/'schema/term_registry.json',[{k:v for k,v in row.items() if k in TERM_FIELDS} for row in load(ROOT/'schema/term_registry.json')])
 frozen=Schema(GenerationProject(snap));fr_admission=load_admission(Project(snap),cfg,frozen,RID);assert fr_admission['valid'];ctx=frozen.context(RID);ctx['admission']=fr_admission['context'];ctx['scope']=context['scope'];assert ctx==context,'SOURCE_CONTEXT_SNAPSHOT_INTEGRITY_FAILURE'
 expected=initial_request(GenerationProject(snap),ctx,{k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']});scope_isolation=isolation(expected);write(group/'expected_initial_request.json',expected);write(group/'preflight_context.json',ctx);write(group/'preflight_source_selection_manifest.json',frozen.source_manifests[RID]);write(group/'approved_scope_validation.json',fr_admission)
 hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 originals=set(files)|{'schema/term_registry.json','data/requirements/requirements.json'}|{str(f.relative_to(ROOT)) for folder in ['src/nltlv2','prompts'] for f in (ROOT/folder).glob('*') if f.is_file()};write(group/'original_input_hashes.json',{name:sha(ROOT/name) for name in sorted(originals)})
 from dotenv import dotenv_values
 env=dotenv_values(ENV);u=urllib.parse.urlsplit(env['AALTO_RESPONSES_BASE_URL']);assert env.get('AALTO_API_KEY') and u.scheme=='https' and u.netloc=='aalto-openai-apigw.azure-api.net' and u.path=='/v1/openai/responses' and not any([u.username,u.password,u.query,u.fragment]);assert not ENV.is_relative_to(ROOT)
 write(group/'preflight.json',dict(version='0.9.1',requirement_id=RID,git_revision=git('rev-parse','HEAD').strip(),working_tree='Recorded exact changes; frozen snapshot, not claimed as a clean version tag',installed_source_identical=True,approved_scope_definition_sha256=original_definition,approved_scope_sha256=sha(ROOT/SCOPE),schema_sha256=sha(ROOT/'schema/Schema_for_NLTL.ttl'),initial_generation_calls=1,max_candidates=2,max_repairs=1,max_context_rounds=2,max_reviews=4,format_retries_per_review=1,max_total_calls=10,examples=[],structured_output=False,source_only_snapshot=True,request_isolation=scope_isolation,external_credential_location=str(ENV),key_present=True,secrets_logged=False,model=cfg['model'],endpoint_origin=u.scheme+'://'+u.netloc,endpoint_path=u.path,dependencies={x:importlib.metadata.version(x) for x in ['rdflib','pyshacl','owlrl','requests','python-dotenv']},evaluation='Not imported/read in production; only after dispatch_closed.json',base_config_preserved=True,network_opt_in='NLTL_ALLOW_MODEL_CALLS=YES + enabled=True'))
 shutil.copyfile(__file__,group/'operational_driver.py');write(STATE,dict(status='PREPARED',group=str(group)));print('PREPARED '+str(group),flush=True)

def verify_original(group):
 for name,h in load(group/'original_input_hashes.json').items():assert sha(ROOT/name)==h,'ORIGINAL_INPUT_INTEGRITY_FAILURE '+name

def firewall(group,events):
 snap=group/'snapshot';blocked=[snap/x for x in ['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']]+[group/'evaluation']
 def audit(event,args):
  if event=='import' and args and any(str(args[0]).startswith('nltlv2.'+m) for m in ['evaluation','development_checks','enumerations','constraint_changes','preflight']):raise PermissionError('FORBIDDEN_SOLUTION_IMPORT')
  if event in ['open','os.listdir','os.scandir'] and args and isinstance(args[0],(str,bytes,os.PathLike)):
   f=Path(os.fsdecode(args[0])).resolve()
   if f.is_relative_to(REPO/'MVP') or (f.is_relative_to(ROOT) and not f.is_relative_to(group)) or any(f==p or f.is_relative_to(p) for p in blocked):raise PermissionError('FORBIDDEN_EVALUATION_WITNESS_SOLUTION_HISTORY_ACCESS')
   if event=='open' and f.is_relative_to(snap/'data/requirements'):events.append(dict(event='source_file_open',path=str(f.relative_to(snap))))
 sys.addaudithook(audit)

class AuditTransport(LiveTransport):
 def __init__(self,group,dest,expected):super().__init__(enabled=True,project_root=ROOT);self.group=group;self.dest=dest;self.expected=expected;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route'];assert route in ['generation','syntax_repair','targeted_repair','review','review_format_retry'],'ROUTE_INTEGRITY_FAILURE'
  assert sum(e['route']=='generation' for e in self.events)+(route=='generation')<=1,'GENERATION_LIMIT_INTEGRITY_FAILURE'
  assert sum(e['route'].endswith('repair') for e in self.events)+route.endswith('repair')<=1,'REPAIR_LIMIT_INTEGRITY_FAILURE'
  assert sum(e['route']=='review' for e in self.events)+(route=='review')<=4,'REVIEW_LIMIT_INTEGRITY_FAILURE'
  assert sum(e['route']=='review_format_retry' for e in self.events)+(route=='review_format_retry')<=4,'FORMAT_RETRY_LIMIT_INTEGRITY_FAILURE'
  assert len(self.events)<10,'TOTAL_REQUEST_LIMIT_INTEGRITY_FAILURE'
  for name,h in load(self.group/'snapshot_hashes.json').items():assert sha(self.group/'snapshot'/name)==h,'SNAPSHOT_INTEGRITY_FAILURE'
  for name,row in load(self.group/'installed_source_identity.json').items():assert sha(row['installed'])==row['sha256'],'INSTALLED_CODE_INTEGRITY_FAILURE'
  if route=='generation':assert not self.events and all(request[k]==self.expected[k] for k in ['route','system','user']),'INITIAL_REQUEST_INTEGRITY_FAILURE'
  boundary=isolation(request)
  if latest is not None:
   assert (self.dest/f'candidate_{latest.version:02d}.ttl').read_text()==latest.code,'LATEST_CANDIDATE_INTEGRITY_FAILURE'
   if route.endswith('repair'):boundary.update(assert_integrity(request,latest,expected_findings))
   else:
    data=json.loads(request['user']);data=data.get('original_request',data);assert data['full_candidate']==latest.code and data['candidate_sha256']==latest.sha256 and data['candidate_version']==latest.version,'LATEST_REVIEW_CODE_INTEGRITY_FAILURE'
  payload=provider_payload(request);assert 'text' not in payload,'STRUCTURED_OUTPUT_MUST_REMAIN_DISABLED';index=len(self.events)+1;url=urllib.parse.urlsplit(self.url)
  write(self.dest/f'live_boundary_{index:03d}.json',boundary);write(self.dest/f'provider_request_{index:03d}.json',dict(endpoint_origin=url.scheme+'://'+url.netloc,endpoint_path=url.path,authentication='External header omitted',body=payload))
  event=dict(index=index,route=route,candidate_version=latest.version if latest else None,request_sha256=digest(json.dumps(payload)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events);print('CALL '+str(index)+' '+route,flush=True);start=time.monotonic()
  try:
   response=super().dispatch(request,latest,expected_findings);write(self.dest/f'provider_response_{index:03d}.json',response);p=response.get('provider_response',{});event.update(status='RESPONSE',provider_id=p.get('id'),provider_model=p.get('model'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'));write(self.dest/'call_ledger.json',self.events);print('RESPONSE '+str(index)+' '+str(response.get('status')),flush=True)
   assert p.get('model') in [None,request['model']],'PROVIDER_MODEL_INTEGRITY_FAILURE'
   return response
  except Exception as error:
   resp=getattr(error,'response',None);body=resp.text if resp is not None else None;event.update(status='ERROR',type=type(error).__name__,diagnostic=str(error).replace(self.key,'[REDACTED]'),http_status=resp.status_code if resp is not None else None,response_body=body.replace(self.key,'[REDACTED]') if body else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events);raise RuntimeError('PROVIDER_DISPATCH_FAILURE; see redacted ledger') from None

def run():
 state=load(STATE);assert state['status']=='PREPARED','No repeat dispatch';group=Path(state['group']);verify_original(group)
 for name,h in load(group/'snapshot_hashes.json').items():assert sha(group/'snapshot'/name)==h
 cfg=load(group/'resolved_config.json');expected=load(group/'expected_initial_request.json');os.environ.update(NLTL_ENV_FILE=str(ENV),NLTL_ALLOW_MODEL_CALLS='YES')
 # Credentials loaded from approved external location, never copied or logged.
 dest=group/RID/'nltl';dest.mkdir(parents=True);transport=AuditTransport(group,dest,expected);source_events=[];firewall(group,source_events)
 denied=[]
 for f in [ROOT/'evaluation/selections/regression_core.json',ROOT/'evaluation/specifications/admission_scope_i2_004/I2-004-G-P01.admission.json',ROOT/'tests/data/legacy_regulatory_witnesses.json',ROOT/'outputs/experiments',REPO/'MVP/evaluation_audit',group/'snapshot/data/contracts/solution_profiles.json',group/'snapshot/evaluation/labels.json']:
  try:f.open('rb')
  except PermissionError:denied.append(str(f))
  else:raise RuntimeError('BOUNDARY_INTEGRITY_FAILURE')
 write(group/'runtime_boundary_verification.json',dict(denied_paths=denied,all_denied=True,content_read=False,capability='Source-only snapshot plus process filesystem audit; no evaluation inputs loaded'))
 state['status']='RUNNING';write(STATE,state);start=time.monotonic()
 try:
  result=Runner(Project(group/'snapshot'),cfg,transport,dest).run(RID);state.update(status='DISPATCH_CLOSED',outcome=result['status'],accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts'],elapsed_seconds=time.monotonic()-start)
 except Exception as error:
  write(group/'driver_failure.json',dict(type=type(error).__name__,diagnostic=str(error).replace(transport.key,'[REDACTED]'),no_retry=True));state.update(status='DISPATCH_CLOSED',outcome='DRIVER_FAILURE',elapsed_seconds=time.monotonic()-start)
 write(group/'source_file_reads.json',source_events);write(STATE,state);write(group/'dispatch_closed.json',state);print('DISPATCH_CLOSED '+state['outcome'],flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();prepare() if args.action=='prepare' else run()
