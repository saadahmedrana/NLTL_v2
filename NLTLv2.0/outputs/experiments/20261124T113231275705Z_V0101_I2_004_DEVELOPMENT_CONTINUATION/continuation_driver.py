"""Explicit v0.10.1 orchestration: current terminal outcomes and shared corrections; production code unchanged."""
from pathlib import Path
import argparse,base64,copy,csv,datetime,hashlib,importlib.metadata,io,json,os,re,shutil,subprocess,sys,time,tomllib,urllib.parse,zipfile
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent;ENV=REPO.parent/'env/NLTL_v2.env';STATE=Path('/private/tmp/v0101_authorized_continuation_state.json');CONFIG='outputs/audits/20261124_REVIEWER_ROUTING/prepared_continuation/continuation_config.json';RID='I2-004';SEED='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a'
TERMINAL={'RESOURCE_ATTRIBUTION_UNCERTAIN','INFRASTRUCTURE_FAILURE','REVIEWER_FORMAT_FAILURE','REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED','REQUEST_INTEGRITY_FAILURE','PROVIDER_CALL_LIMIT_EXHAUSTED','CONFLICT','UNRESOLVED_CONTEXT','CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST','STAGNATION_STOP'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def install_frozen_source(snapshot,group):
 """Create an offline pure-Python wheel from exact frozen source; install only into this run."""
 metadata=tomllib.loads((snapshot/'pyproject.toml').read_text())['project'];assert metadata['version']=='0.10.1'
 name=metadata['name'].replace('-','_');info=name+'-0.10.1.dist-info';items={str(f.relative_to(snapshot/'src')):f.read_bytes() for f in (snapshot/'src/nltlv2').glob('*.py')}
 headers=['Metadata-Version: 2.1','Name: '+metadata['name'],'Version: '+metadata['version'],'Summary: '+metadata['description'],'Requires-Python: '+metadata['requires-python']]+['Requires-Dist: '+d for d in metadata['dependencies']]
 items[info+'/METADATA']=('\n'.join(headers)+'\n\nFrozen exact production source for this authorized development continuation.\n').encode();items[info+'/WHEEL']=b'Wheel-Version: 1.0\nGenerator: exact-frozen-source-audit\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
 record=io.StringIO();writer=csv.writer(record,lineterminator='\n')
 for name,data in sorted(items.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='),len(data)])
 writer.writerow([info+'/RECORD','','']);items[info+'/RECORD']=record.getvalue().encode();wheel=group/(metadata['name'].replace('-','_')+'-0.10.1-py3-none-any.whl')
 with zipfile.ZipFile(wheel,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in items.items():z.writestr(name,data)
 runtime=group/'runtime';env=dict(os.environ,PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1');proc=subprocess.run([sys.executable,'-B','-m','pip','--disable-pip-version-check','--no-cache-dir','install','--no-deps','--no-index','--target',str(runtime),str(wheel)],env=env,capture_output=True,text=True);(group/'run_local_install_stdout.txt').write_text(proc.stdout);(group/'run_local_install_stderr.txt').write_text(proc.stderr);assert proc.returncode==0,'RUN_LOCAL_INSTALL_FAILURE';return runtime

def prepare():
 assert not STATE.exists(),'Single authorized continuation state already exists; no repeat dispatch'
 sys.path.insert(0,str(ROOT/'src'))
 from nltlv2.core import Project,GenerationProject,offline_network_guard
 from nltlv2.schema import Schema,TERM_FIELDS
 from nltlv2.admission import load_admission,definition_hash
 import nltlv2
 with offline_network_guard():
  assert nltlv2.__version__=='0.10.1';project=Project(ROOT);base=project.config(CONFIG);cont=base['continuation'];assert base['method']=='offline' and base['pipeline_version']=='0.10.1';assert cont['seed_sha256']==SEED and cont['initial_generation_calls']==0 and cont['max_repair_calls']==1 and cont['max_total_candidates_including_seed']==2 and cont['prior_issue_ids']==[]
  assert cont['max_provider_calls']==9
  assert base['maximum_candidate_attempts']==2 and base['review_format_retries']==1 and base['context_resolution']['max_rounds']==2 and base['context_resolution']['max_reviews_per_candidate']==3 and base['context_resolution']['max_reviews_per_run']==4 and not base['fresh_regeneration']
  seed=ROOT/cont['seed_file'];assert sha(seed)==SEED;context=load(ROOT/cont['source_context']);schema=Schema(GenerationProject(ROOT));ad=load_admission(project,base,schema,RID);assert ad['valid'] and context['admission']==ad['context'];current=schema.context(RID)
  for key in ['requirement','termOwners','modelPaths','contract','quantityEncoding']:assert context[key]==current[key],key
  assert context['examples']==[]
  for doc in context['source_documents']:
   raw=project.path(doc['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==doc['sha256'];text=raw.decode();span=doc.get('selection');assert doc['text']==(text[span['start']:span['end']] if span else text)
  from rdflib import Graph
  for fact in context['ontology_evidence']:
   parsed=Graph().parse(data=' '.join(fact)+' .',format='turtle')
   assert all(t in schema.graph for t in parsed),'UNSUPPLIED_ONTOLOGY_EVIDENCE'
  for row in context['schema_terms']:
   assert row['iri'] in schema.terms
   for key in ['kind','datatype','unitIri']:
    if row.get(key):assert row[key]==schema.terms[row['iri']].get(key)
  timestamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');group=project.output('experiments',timestamp+'_V0101_I2_004_DEVELOPMENT_CONTINUATION');write(STATE,dict(status='PREPARING',group=str(group)))
  before={str(f.relative_to(ROOT)):sha(f) for folder in ['outputs','schema','data','evaluation','results'] for f in (ROOT/folder).rglob('*') if f.is_file() and not f.is_relative_to(group)};before['src/nltlv2/tracking.py']=sha(ROOT/'src/nltlv2/tracking.py');write(group/'preserved_hashes_before.json',before)
  cfg=copy.deepcopy(base);cfg.update(method='NLTL',network_enabled=True,proposal_only=False,purpose='Authorized v0.10.1 seeded DEVELOPMENT_CONTINUATION; not fresh comparative performance');cfg['continuation'].update(dispatch_prepared_only=False,requires_separate_model_authorization=False,authorization='Current user authorizes exactly one bounded v0.10.1 continuation; no pipeline change, rerun or expansion')
  write(group/'base_config.json',base);write(group/'resolved_config.json',cfg);write(group/'source_schema_context.json',context)
  snapshot=group/'snapshot';snapshot.mkdir();shutil.copytree(ROOT/'src/nltlv2',snapshot/'src/nltlv2',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));shutil.copytree(ROOT/'prompts',snapshot/'prompts');shutil.copyfile(ROOT/'pyproject.toml',snapshot/'pyproject.toml');shutil.copyfile(ROOT/'requirements-lock.txt',snapshot/'requirements-lock.txt')
  files=['schema/Schema_for_NLTL.ttl','schema/representation_bindings.json','schema/locked_representation_context.jsonld','schema/runtime_lock.json','data/requirements/source_catalog.json',base['admission_file']]
  for entry in schema.catalog.values():
   files.append(entry['file']);provenance=entry.get('provenance')
   if isinstance(provenance,dict) and provenance.get('file'):files.append(provenance['file'])
  for name in set(files):dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
  raw=schema.requirements[RID];allowed={'id','source','clause','text','source_file','source_sha256','supporting_sources'};write(snapshot/'data/requirements/requirements.json',{RID:{k:v for k,v in raw.items() if k in allowed}});write(snapshot/'schema/term_registry.json',[{k:v for k,v in row.items() if k in TERM_FIELDS} for row in load(ROOT/'schema/term_registry.json')])
  frozen=Schema(GenerationProject(snapshot));assert frozen.context(RID)==current,'SNAPSHOT_CONTEXT_MISMATCH';assert load_admission(Project(snapshot),cfg,frozen,RID)['context']==ad['context']
  runtime=install_frozen_source(snapshot,group)
  identity={}
  for source in (ROOT/'src/nltlv2').glob('*.py'):
   installed=runtime/'nltlv2'/source.name;assert source.read_bytes()==installed.read_bytes()==(snapshot/'src/nltlv2'/source.name).read_bytes();identity[str(source.relative_to(ROOT))]=dict(sha256=sha(source),installed=str(installed))
  distributions=list(importlib.metadata.distributions(path=[str(runtime)]));dist=next(d for d in distributions if d.metadata['Name']=='nltlv2-refined');assert dist.version=='0.10.1';write(group/'installed_source_identity.json',identity)
  original=set(files)|{'pyproject.toml','requirements-lock.txt',CONFIG,cont['seed_file'],cont['source_context'],'schema/term_registry.json','data/requirements/requirements.json'}|{str(p.relative_to(ROOT)) for folder in ['src/nltlv2','prompts'] for p in (ROOT/folder).glob('*') if p.is_file()};write(group/'original_input_hashes.json',{n:sha(ROOT/n) for n in sorted(original)})
  write(group/'snapshot_hashes.json',{str(p.relative_to(snapshot)):sha(p) for p in snapshot.rglob('*') if p.is_file()});write(group/'runtime_hashes.json',{str(p.relative_to(runtime)):sha(p) for p in runtime.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
  dest=group/RID/'nltl';dest.mkdir(parents=True);shutil.copyfile(seed,dest/'candidate_01.ttl');write(dest/'candidate_01.json',dict(version=1,sha256=SEED,origin='EXACT_UNCHANGED_SAVED_SEED',new_generation=False))
  write(group/'orchestration_contract.json',dict(version='0.10.1',terminal_outcomes=sorted(TERMINAL),error_outcome_source='Runner.assess_candidate controller outcome, never remapped to legacy format failure',shared_correction_allowance=1,correction_transport_label='review_format_retry',overall_provider_cap=9,old_driver_not_executed=True,production_source_unchanged=True))
  write(group/'preflight.json',dict(version='0.10.1',label='DEVELOPMENT_CONTINUATION',seed_sha256=SEED,shared_environment_distribution='0.9.2; deliberately unchanged',actual_run_local_installed_distribution=dist.version,installed_source_identical=True,run_local_runtime=str(runtime),approved_scope_sha256=sha(ROOT/base['admission_file']),scope_definition_sha256=definition_hash(ad['context']['declaration']),source_context_sha256=sha(ROOT/cont['source_context']),original_input_hashes_verified=True,initial_prior_issues=[],failed_reviews_loaded=False,historical_diagnosis_or_solution_loaded=False,evaluation_data_loaded=False,source_schema_context_only=True,initial_generations=0,max_repairs=1,max_candidates_including_seed=2,max_primary_reviews=4,max_reviews_per_candidate=3,max_format_retries_per_review=1,max_context_rounds=2,max_total_provider_calls=9,early_acceptance=True,regeneration=False,provider_model=cfg['model'],credential_location=str(ENV),dependencies={n:importlib.metadata.version(n) for n in ['rdflib','pyshacl','owlrl','requests','python-dotenv']},time_context='UTC artifacts; user timezone Europe/Helsinki'))
  shutil.copyfile(__file__,group/'continuation_driver.py');write(STATE,dict(status='PREPARED',group=str(group)));print('PREPARED '+str(group),flush=True)

def run():
 state=load(STATE);assert state['status']=='PREPARED','No repeat dispatch';group=Path(state['group']);runtime=group/'runtime';snapshot=group/'snapshot';dest=group/RID/'nltl';cfg=load(group/'resolved_config.json');context=load(group/'source_schema_context.json')
 for name,h in load(group/'original_input_hashes.json').items():assert sha(ROOT/name)==h,'ORIGINAL_INPUT_INTEGRITY_FAILURE'
 sys.path.insert(0,str(runtime))
 import nltlv2
 assert Path(nltlv2.__file__).parent==runtime/'nltlv2' and nltlv2.__version__=='0.10.1'
 assert importlib.metadata.version('nltlv2-refined')=='0.10.1'
 from nltlv2.core import Project,Candidate,finding,normalize,WrapperError,digest
 from nltlv2.runner import Runner
 from nltlv2.tracking import Tracker
 from nltlv2.change_review import manifest
 from nltlv2.checks import check,runtime_probe
 from nltlv2.evidence import probe_summary,assert_review_packet
 from nltlv2.requests import repair_request,assert_integrity
 from nltlv2.transport import LiveTransport,provider_payload
 os.environ.update(NLTL_ENV_FILE=str(ENV),NLTL_ALLOW_MODEL_CALLS='YES')
 source_reads=[];gate={'enabled':False}
 def firewall(event,args):
  if not gate['enabled']:return
  if event=='import' and args and any(str(args[0]).startswith('nltlv2.'+m) for m in ['evaluation','development_checks','enumerations','constraint_changes','preflight']):raise PermissionError('FORBIDDEN_SOLUTION_IMPORT')
  if event in ['open','os.listdir','os.scandir'] and args and isinstance(args[0],(str,bytes,os.PathLike)):
   path=Path(os.fsdecode(args[0])).resolve();blocked=path.is_relative_to(REPO/'MVP') or (path.is_relative_to(ROOT) and not path.is_relative_to(group)) or any(path.is_relative_to(snapshot/p) for p in ['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']) or path.is_relative_to(group/'evaluation')
   if blocked:raise PermissionError('FORBIDDEN_EVALUATION_HISTORY_SOLUTION_ACCESS')
   if event=='open' and path.is_relative_to(snapshot/'data/requirements'):source_reads.append(str(path.relative_to(snapshot)))
 sys.addaudithook(firewall)
 class AuditedLive(LiveTransport):
  def __init__(self):super().__init__(enabled=True,project_root=ROOT);self.events=[];self.closed=False
  def dispatch(self,request,latest=None,expected_findings=None):
   route=request['route'];assert not self.closed;assert route in ['review','review_format_retry','syntax_repair','targeted_repair'],'GENERATION_OR_UNKNOWN_ROUTE_FORBIDDEN';assert len(self.events)<9
   if route=='review_format_retry':
    primaries=[e for e in self.events if e['route']=='review'];assert primaries and primaries[-1]['candidate_version']==latest.version,'CORRECTION_WITHOUT_PRIMARY_REVIEW'
    assert sum(e['route']=='review_format_retry' for e in self.events if e['index']>primaries[-1]['index'])<1,'SHARED_CORRECTION_ALLOWANCE_EXHAUSTED'
   assert sum(e['route']=='review' for e in self.events)+int(route=='review')<=4
   assert sum(e['route']=='review' and e['candidate_version']==latest.version for e in self.events)+int(route=='review')<=3
   assert sum(e['route'].endswith('repair') for e in self.events)+int(route.endswith('repair'))<=1
   for folder,manifest_file in [(snapshot,'snapshot_hashes.json'),(runtime,'runtime_hashes.json')]:
    for name,h in load(group/manifest_file).items():assert sha(folder/name)==h,'FROZEN_IMPLEMENTATION_INTEGRITY_FAILURE'
   body=json.loads(request['user']);assert body.get('protocol_version')==2
   assert latest and (dest/f'candidate_{latest.version:02d}.ttl').read_text()==latest.code
   assert body['admission_sha256']==hashlib.sha256(json.dumps(context['admission'],sort_keys=True).encode()).hexdigest()
   text=json.dumps(body,ensure_ascii=False);assert 'https://w3id.org/nltl/benchmark/' not in text;assert not re.search(r'I2-\d{3}-[A-Z]-[PF]\d{2}',text)
   forbidden={'case_id','admitted_nodes','expected_verdicts','counterfactual_records','behavioral_witnesses','validated_constraint_changes','solution_profile','sourceBackedObligations'}
   def inspect(x):
    if isinstance(x,dict):
     assert not forbidden&set(x),'SOLUTION_OR_EVALUATION_REQUEST_FAILURE'
     for value in x.values():inspect(value)
    elif isinstance(x,list):
     for value in x:inspect(value)
   inspect(body)
   caller=[json.loads(e['text']) for e in body['evidence_catalog']['entries'] if e['kind']=='CALLER_DECLARATION'];assert caller==[context['admission']]
   if route.startswith('review'):
    assert_review_packet(body,latest)
    if not self.events:assert body['prior_issues']==[]
   else:assert_integrity(request,latest,expected_findings)
   url=urllib.parse.urlsplit(self.url);assert url.scheme=='https' and url.netloc=='aalto-openai-apigw.azure-api.net' and url.path=='/v1/openai/responses' and not any([url.username,url.password,url.query,url.fragment]),'UNEXPECTED_PROVIDER_ENDPOINT'
   payload=provider_payload(request);assert 'text' not in payload,'STRUCTURED_OUTPUT_UNAUTHORIZED';index=len(self.events)+1
   write(dest/f'live_boundary_{index:03d}.json',dict(no_evaluation_or_solution_inputs=True,empty_initial_prior_state=not self.events,complete_candidate=True,scope_hash_verified=True,frozen_runtime_verified=True,protocol=2))
   write(dest/f'provider_request_{index:03d}.json',dict(endpoint_origin=url.scheme+'://'+url.netloc,endpoint_path=url.path,authentication='External secret header omitted',body=payload))
   event=dict(index=index,route=route,candidate_version=latest.version,candidate_sha256=latest.sha256,request_sha256=digest(json.dumps(payload)),status='DISPATCHING');self.events.append(event);write(dest/'call_ledger.json',self.events);print('CALL '+str(index)+' '+route,flush=True);started=time.monotonic()
   try:
    response=super().dispatch(request,latest,expected_findings);write(dest/f'provider_response_{index:03d}.json',response);provider=response.get('provider_response',{});event.update(status='RESPONSE',provider_id=provider.get('id'),provider_model=provider.get('model'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'));write(dest/'call_ledger.json',self.events);assert provider.get('model') in [None,request['model']],'PROVIDER_MODEL_MISMATCH';print('RESPONSE '+str(index)+' '+str(response.get('status')),flush=True);return response
   except Exception as error:
    resp=getattr(error,'response',None);text=resp.text if resp is not None else None;event.update(status='ERROR',error_type=type(error).__name__,diagnostic=str(error).replace(self.key,'[REDACTED]'),http_status=resp.status_code if resp is not None else None,response_body=text.replace(self.key,'[REDACTED]') if text else None,elapsed_seconds=time.monotonic()-started);write(dest/'call_ledger.json',self.events);raise RuntimeError('PROVIDER_DISPATCH_FAILURE; see redacted ledger') from None
 transport=AuditedLive();gate['enabled']=True
 denied=[]
 for path in [ROOT/'evaluation',ROOT/'tests',ROOT/'outputs/audits',ROOT/'outputs/experiments',REPO/'MVP',snapshot/'evaluation',snapshot/'data/contracts',group/'evaluation']:
  try:path.open('rb')
  except PermissionError:denied.append(str(path))
  else:raise RuntimeError('RESOURCE_BOUNDARY_FAILURE')
 write(group/'runtime_boundary_verification.json',dict(all_denied=True,denied_paths=denied,content_read=False,failed_historical_reviews_loaded=False,initial_prior_issues=[]))
 runner=Runner(Project(snapshot),cfg,transport,dest);runner.admission_context=copy.deepcopy(context['admission']);runner.input_hashes={name:h for name,h in load(group/'snapshot_hashes.json').items() if name.startswith(('data/','schema/','prompts/')) and name!='schema/runtime_lock.json'};tracker=Tracker();assert tracker.prior_semantic_issues()==[];runner.latest_findings=()
 current=Candidate(1,(dest/'candidate_01.ttl').read_text(),'');assert current.sha256==SEED;previous=None;fmt=None;history=[];operational=None;status='UNSTARTED';state['status']='RUNNING';write(STATE,state);start=time.monotonic()
 try:
  for version in [1,2]:
   attempt_start=time.monotonic();metric_start=len(runner.response_metrics);changes=manifest(previous,current) if previous else dict(status='EXACT_SEED_UNCHANGED',changes=[]);write(dest/f'change_manifest_{version:02d}.json',changes)
   if previous:(dest/f'diff_{previous.version:02d}_{version:02d}.patch').write_text(changes['diff'])
   fs=[finding(current,'RESPONSE_FORMAT_ERROR','Missing/ambiguous wrapper',current.raw,expected='<BEGIN_SHACL> ... <END_SHACL>',suggestion='Return one complete unambiguous block',diagnostic=fmt)] if fmt else check(current,runner.schema,RID,admission=runner.admission_context)
   parsed=not fmt and not any(f.category=='PARSE_ERROR' for f in fs);runtime_complete=False;runner.execution_summaries[version]=probe_summary(current,reason='Static/format blockers; no execution')
   if not any(f.blocking for f in fs):
    execution,probe=runtime_probe(current,runner.schema);fs+=execution;runtime_complete=not execution;runner.execution_summaries[version]=probe_summary(current,probe);write(dest/f'runtime_probe_{version:02d}.json',probe)
   write(dest/f'pre_review_findings_{version:02d}.json',[f.asdict() for f in fs]);context,fs,obj,error,conflicts,controller=runner.assess_candidate(current,context,previous,changes,tracker,fs,RID)
   reconciled,persistent=tracker.observe(current,fs,static_complete=parsed,review=obj,runtime_complete=runtime_complete);accepted=not any(f.blocking for f in fs) and not error and not conflicts and obj is not None and obj['decision']=='ACCEPT' and controller=='ACCEPTED'
   resource=any(f.assessment=='RESOURCE_UNCERTAIN' for f in fs);infra=any(f.assessment=='INFRASTRUCTURE_OR_UNKNOWN' for f in fs);status='ACCEPTED' if accepted else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if resource else 'INFRASTRUCTURE_FAILURE' if infra else controller if error else 'CONFLICT' if conflicts else controller if controller in TERMINAL else 'REJECTED'
   if error:assert controller in ['REQUEST_INTEGRITY_FAILURE','REVIEWER_PROPOSAL_CORRECTION_EXHAUSTED','REVIEWER_FORMAT_FAILURE'],'UNRECOGNIZED_CURRENT_REVIEW_OUTCOME'
   stagnation=tracker.stagnation_stop(cfg.get('stagnation',{})) if not accepted else None
   if stagnation and status=='REJECTED':status='STAGNATION_STOP'
   row=dict(version=version,sha256=current.sha256,origin='EXACT_UNCHANGED_SEED' if version==1 else 'ONE_MODEL_REPAIR',accepted=accepted,status=status,findings=[f.asdict() for f in fs],review=obj,reviewer_format_failure=error,conflicts=conflicts,changes=reconciled,persistent_failure_summary=persistent,structural_change_manifest=changes,elapsed_seconds=time.monotonic()-attempt_start,request_metrics=runner.response_metrics[metric_start:],regulatory_correctness_certified=False);history.append(row);write(dest/'history.json',history);write(dest/f'findings_{version:02d}.json',row['findings']);write(dest/f'reconciliation_{version:02d}.json',reconciled);runner.latest_findings=tuple(fs)
   if accepted or status in TERMINAL:break
   if version==2:status='ATTEMPT_LIMIT_EXHAUSTED';break
   runner.transition(current,'REPAIR_REQUEST_READY',latest_code_complete=True,development_continuation=True);response=runner.dispatch(repair_request(runner.p,context,current,fs,persistent_summary=persistent),current);raw=response['text'];fmt=None;normalization=None
   try:code,normalization=normalize(raw)
   except WrapperError as error:code=raw;fmt=str(error)
   previous=current;current=Candidate(2,code,raw);(dest/'candidate_02.ttl').write_text(code);write(dest/'candidate_02.json',dict(version=2,sha256=current.sha256,origin='MODEL_REPAIR',normalization=normalization))
  runner.verify_inputs()
 except Exception as error:
  diagnostic=str(error).replace(transport.key,'[REDACTED]');integrity=any(k in diagnostic for k in ['INTEGRITY','STALE','ABSENT','FEEDBACK','TRUNCATED_PREVIOUS','RENDERED_REQUEST']);status='PROVIDER_CALL_LIMIT_EXHAUSTED' if diagnostic=='PROVIDER_CALL_LIMIT_EXHAUSTED' else 'REQUEST_INTEGRITY_FAILURE' if integrity else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if isinstance(error,(TimeoutError,MemoryError,RecursionError)) or 'timeout' in type(error).__name__.lower() else 'INFRASTRUCTURE_FAILURE';operational=dict(type=type(error).__name__,diagnostic=diagnostic,status=status,no_automatic_retry=True);write(dest/'operational_failure.json',operational)
 transport.closed=True
 result=dict(version='0.10.1',run_label='DEVELOPMENT_CONTINUATION',seeded_not_fresh_workflow_performance=True,requirement_id=RID,status=status,candidate_attempts=len(list(dest.glob('candidate_*.ttl'))),seed_sha256=SEED,accepted_version=next((h['version'] for h in history if h['accepted']),None),evaluation_candidate=next((h['version'] for h in history if h['accepted']),None),initial_generations=0,current_terminal_outcomes_used=True,shared_response_correction_allowance=1,repair_calls=sum(e['route'].endswith('repair') for e in transport.events),primary_reviews=sum(e['route']=='review' for e in transport.events),format_retries=sum(e['route']=='review_format_retry' for e in transport.events),provider_calls=len(transport.events),elapsed_seconds=time.monotonic()-start,history=history,operational_failure=operational,initial_prior_issues=[],failed_historical_reviews_used=False,independent_evaluation_consulted=False,limits_preserved=True)
 write(dest/'run.json',result);write(group/'source_file_reads.json',source_reads);state.update(status='DISPATCH_CLOSED',outcome=status,accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts']);write(STATE,state);write(group/'dispatch_closed.json',dict(state,dispatch_closed=True,run_manifest_sha256=sha(dest/'run.json'),candidate_sha256={f.stem:sha(f) for f in dest.glob('candidate_*.ttl')},model_transport_closed=True));print('DISPATCH_CLOSED '+status,flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);action=parser.parse_args().action;prepare() if action=='prepare' else run()
