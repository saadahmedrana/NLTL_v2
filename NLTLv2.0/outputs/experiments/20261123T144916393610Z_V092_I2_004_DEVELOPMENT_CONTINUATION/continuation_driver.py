"""Bounded orchestration using frozen production check/review/repair; no generation/evaluator."""
from pathlib import Path
import argparse,copy,hashlib,importlib.metadata,json,os,re,shutil,subprocess,sys,time,urllib.parse
import nltlv2
from nltlv2.core import Project,GenerationProject,load,write,stamp,digest,Candidate,finding,normalize,WrapperError
from nltlv2.schema import Schema,TERM_FIELDS
from nltlv2.admission import load_admission,definition_hash
from nltlv2.evidence import assert_review_packet,probe_summary
from nltlv2.requests import repair_request,assert_integrity
from nltlv2.checks import check,runtime_probe
from nltlv2.change_review import manifest
from nltlv2.tracking import Tracker
from nltlv2.runner import Runner
from nltlv2.transport import LiveTransport,provider_payload
from nltlv2.review_protocol import response_format
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');REPO=ROOT.parent;ENV=REPO.parent/'env/NLTL_v2.env';STATE=Path('/private/tmp/v092_continuation_live_state.json');CONFIG='configs/v092_review_continuation.json';RID='I2-004';SEED='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a';GIT='/Library/Developer/CommandLineTools/usr/bin/git'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):return subprocess.run([GIT,'-C',str(REPO),*args],capture_output=True,text=True,check=True).stdout

def isolate(request):
 text=json.dumps(request,ensure_ascii=False)
 assert 'https://w3id.org/nltl/benchmark/' not in text,'EVALUATION_NAMESPACE_REQUEST_INTEGRITY_FAILURE'
 assert not re.search(r'I2-\d{3}-[A-Z]-[PF]\d{2}',text),'EVALUATION_CASE_REQUEST_INTEGRITY_FAILURE'
 forbidden={'case_id','admitted_nodes','expected_verdicts','counterfactual_records','behavioral_witnesses','validated_constraint_changes','solution_profile','sourceBackedObligations'}
 def visit(x):
  if isinstance(x,dict):
   assert not forbidden&set(x),'EVALUATION_OR_SOLUTION_FIELD_INTEGRITY_FAILURE'
   for v in x.values():visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(request)
 body=json.loads(request['user']);body=body.get('original_request',body)
 scope=body.get('context',{}).get('admission') if request['route'].startswith('review') else body.get('admission');assert scope and set(scope['declaration']['focus_set'])=={'mode','owner_class'}
 return dict(no_evaluation_namespace=True,no_evaluation_case_ids=True,no_per_input_binding_or_solution_fields=True,common_approved_scope_only=True)

def prepare():
 assert not STATE.exists(),'No duplicate preparation/rerun'
 assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.9.2'
 identity={}
 for f in sorted((ROOT/'src/nltlv2').glob('*.py')):
  p=Path(nltlv2.__file__).parent/f.name;assert f.read_bytes()==p.read_bytes(),'INSTALLED_SOURCE_IDENTITY_FAILURE';identity[str(f.relative_to(ROOT))]=dict(sha256=sha(f),installed=str(p))
 project=Project(ROOT);base=project.config(CONFIG);assert base['method']=='offline' and base['pipeline_version']=='0.9.2'
 assert base['maximum_candidate_attempts']==2 and base['review_format_retries']==1 and base['context_resolution']['max_rounds']==2 and base['context_resolution']['max_reviews_per_run']==4 and response_format(base) is None and not base['fresh_regeneration']
 cont=base['continuation'];assert cont['seed_sha256']==SEED and cont['initial_generation_calls']==0 and cont['max_repair_calls']==1 and cont['prior_issue_ids']==[]
 seed=ROOT/cont['seed_file'];context_file=ROOT/cont['source_context'];assert sha(seed)==SEED
 cfg=copy.deepcopy(base);cfg.update(method='NLTL',network_enabled=True,proposal_only=False,purpose='User-authorized seeded DEVELOPMENT_CONTINUATION, not fresh comparative performance');cfg['continuation'].update(dispatch_prepared_only=False,requires_separate_model_authorization=False,authorization='Current-conversation user instruction authorizes this bounded continuation')
 schema=Schema(GenerationProject(ROOT));admission=load_admission(project,cfg,schema,RID);assert admission['valid'],admission['errors'];context=load(context_file);assert context['admission']==admission['context'];assert context['requirement']==schema.context(RID)['requirement'] and context['examples']==[]
 for key in ['termOwners','modelPaths','contract','quantityEncoding']:assert context[key]==schema.context(RID)[key]
 for doc in context['source_documents']:
  source=ROOT/doc['file'];raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==doc['sha256'];text=raw.decode('utf-8');span=doc.get('selection');assert doc['text']==(text[span['start']:span['end']] if span else text)
 for row in context['schema_terms']:
  assert row['iri'] in schema.terms
  for key in ['kind','datatype','unitIri']:
   if row.get(key):assert row[key]==schema.terms[row['iri']].get(key)
 group=project.output('experiments',stamp()+'_V092_I2_004_DEVELOPMENT_CONTINUATION');write(STATE,dict(status='PREPARING',group=str(group)))
 previous={str(f.relative_to(ROOT)):sha(f) for folder in ['outputs/experiments','evaluation/fixtures','evaluation/selections'] for f in (ROOT/folder).rglob('*') if f.is_file() and not f.is_relative_to(group)};previous['src/nltlv2/tracking.py']=sha(ROOT/'src/nltlv2/tracking.py');write(group/'preserved_hashes_before.json',previous)
 for name,args in [('git_revision.txt',['rev-parse','HEAD']),('working_tree_before.txt',['status','--porcelain=v1','--untracked-files=all']),('working_diff.patch',['diff','--binary']),('index_diff.patch',['diff','--cached','--binary'])]:(group/name).write_text(git(*args))
 write(group/'installed_source_identity.json',identity);write(group/'base_config.json',base);write(group/'resolved_config.json',cfg);write(group/'source_schema_context.json',context)
 snap=group/'snapshot';snap.mkdir()
 for folder in ['src/nltlv2','prompts']:shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 files=['pyproject.toml','requirements-lock.txt',CONFIG,base['admission_file'],'schema/Schema_for_NLTL.ttl','schema/locked_representation_context.jsonld','schema/representation_bindings.json','data/requirements/source_catalog.json']
 catalog=load(ROOT/'data/requirements/source_catalog.json');files += [v['file'] for v in catalog['sources'].values()];files += [v['provenance']['file'] for v in catalog['sources'].values() if isinstance(v.get('provenance'),dict) and v['provenance'].get('file')]
 for name in sorted(set(files)):
  dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
 record=load(ROOT/'data/requirements/requirements.json')[RID];fields={'id','source','clause','text','source_file','source_sha256','supporting_sources'};write(snap/'data/requirements/requirements.json',{RID:{k:v for k,v in record.items() if k in fields}});write(snap/'schema/term_registry.json',[{k:v for k,v in r.items() if k in TERM_FIELDS} for r in load(ROOT/'schema/term_registry.json')])
 dest=group/RID/'nltl';dest.mkdir(parents=True);(dest/'candidate_01.ttl').write_bytes(seed.read_bytes());write(dest/'candidate_01.json',dict(version=1,sha256=SEED,origin='EXACT_HISTORICAL_SEED',new_generation=False));assert sha(dest/'candidate_01.ttl')==SEED
 frozen=Schema(GenerationProject(snap));assert frozen.context(RID)['requirement']==context['requirement'];assert load_admission(Project(snap),cfg,frozen,RID)['context']==context['admission']
 hashes={str(f.relative_to(snap)):sha(f) for f in snap.rglob('*') if f.is_file()};write(group/'snapshot_hashes.json',hashes)
 original=set(files)|{'schema/term_registry.json','data/requirements/requirements.json',cont['seed_file'],cont['source_context']}|{str(f.relative_to(ROOT)) for folder in ['src/nltlv2','prompts'] for f in (ROOT/folder).glob('*') if f.is_file()};write(group/'original_input_hashes.json',{n:sha(ROOT/n) for n in sorted(original)})
 from dotenv import dotenv_values
 env=dotenv_values(ENV);url=urllib.parse.urlsplit(env['AALTO_RESPONSES_BASE_URL']);assert env.get('AALTO_API_KEY') and url.scheme=='https' and url.netloc=='aalto-openai-apigw.azure-api.net' and url.path=='/v1/openai/responses' and not any([url.username,url.password,url.query,url.fragment]);assert not ENV.is_relative_to(ROOT)
 write(group/'preflight.json',dict(version='0.9.2',label='DEVELOPMENT_CONTINUATION',seed_sha256=SEED,installed_source_identical=True,git_revision=git('rev-parse','HEAD').strip(),working_tree='Recorded, not claimed as a clean version tag',approved_scope_sha256=sha(ROOT/base['admission_file']),scope_definition_sha256=definition_hash(context['admission']['declaration']),schema_sha256=sha(ROOT/'schema/Schema_for_NLTL.ttl'),source_context_sha256=sha(context_file),prior_issue_ids=[],failed_historical_reviews_loaded=False,historical_diagnosis_or_solution_loaded=False,evaluation_loaded=False,seed_code_unmodified=True,initial_generations=0,max_repairs=1,max_candidates_including_seed=2,max_context_rounds=2,max_primary_reviews=4,max_format_retries_per_review=1,max_total_provider_calls=9,structured_output=False,capability_probes=0,examples=[],model=cfg['model'],endpoint_origin=url.scheme+'://'+url.netloc,endpoint_path=url.path,external_credential_location=str(ENV),key_present=True,secrets_logged=False,base_configuration_preserved=True,dependencies={n:importlib.metadata.version(n) for n in ['rdflib','pyshacl','owlrl','requests','python-dotenv']}))
 shutil.copyfile(__file__,group/'continuation_driver.py');write(STATE,dict(status='PREPARED',group=str(group)));print('PREPARED '+str(group),flush=True)

def firewall(group,source_events):
 snap=group/'snapshot';blocked=[snap/x for x in ['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']]+[group/'evaluation']
 def audit(event,args):
  if event=='import' and args and any(str(args[0]).startswith('nltlv2.'+m) for m in ['evaluation','development_checks','enumerations','constraint_changes','preflight']):raise PermissionError('FORBIDDEN_SOLUTION_IMPORT')
  if event in ['open','os.listdir','os.scandir'] and args and isinstance(args[0],(str,bytes,os.PathLike)):
   p=Path(os.fsdecode(args[0])).resolve()
   if p.is_relative_to(REPO/'MVP') or (p.is_relative_to(ROOT) and not p.is_relative_to(group)) or any(p==b or p.is_relative_to(b) for b in blocked):raise PermissionError('FORBIDDEN_EVALUATION_WITNESS_SOLUTION_HISTORY_ACCESS')
   if event=='open' and p.is_relative_to(snap/'data/requirements'):source_events.append(str(p.relative_to(snap)))
 sys.addaudithook(audit)

class AuditedLive(LiveTransport):
 def __init__(self,group,dest):super().__init__(enabled=True,project_root=ROOT);self.group=group;self.dest=dest;self.events=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  route=request['route'];assert route in ['review','review_format_retry','targeted_repair','syntax_repair'],'ZERO_GENERATION_ROUTE_INTEGRITY_FAILURE'
  assert len(self.events)<9
  assert sum(e['route']=='review' for e in self.events)+(route=='review')<=4
  assert sum(e['route']=='review_format_retry' for e in self.events)+(route=='review_format_retry')<=4
  assert sum(e['route'].endswith('repair') for e in self.events)+route.endswith('repair')<=1
  for name,h in load(self.group/'snapshot_hashes.json').items():assert sha(self.group/'snapshot'/name)==h,'SNAPSHOT_INTEGRITY_FAILURE'
  for name,row in load(self.group/'installed_source_identity.json').items():assert sha(row['installed'])==row['sha256'],'INSTALLED_INTEGRITY_FAILURE'
  assert latest and (self.dest/f'candidate_{latest.version:02d}.ttl').read_text()==latest.code,'LATEST_CODE_INTEGRITY_FAILURE'
  boundary=isolate(request)
  if route.startswith('review'):
   body=json.loads(request['user']);body=body.get('original_request',body);boundary.update(assert_review_packet(body,latest))
   if not self.events:assert body['prior_issues']==[],'EMPTY_INITIAL_PRIOR_STATE_INTEGRITY_FAILURE'
  else:boundary.update(assert_integrity(request,latest,expected_findings))
  payload=provider_payload(request);assert 'text' not in payload,'STRUCTURED_OUTPUT_MUST_REMAIN_DISABLED';i=len(self.events)+1;url=urllib.parse.urlsplit(self.url);write(self.dest/f'live_boundary_{i:03d}.json',boundary);write(self.dest/f'provider_request_{i:03d}.json',dict(endpoint_origin=url.scheme+'://'+url.netloc,endpoint_path=url.path,authentication='External header omitted',body=payload))
  event=dict(index=i,route=route,candidate_version=latest.version,candidate_sha256=latest.sha256,request_sha256=digest(json.dumps(payload)),status='DISPATCHING');self.events.append(event);write(self.dest/'call_ledger.json',self.events);print('CALL '+str(i)+' '+route,flush=True);start=time.monotonic()
  try:
   response=super().dispatch(request,latest,expected_findings);write(self.dest/f'provider_response_{i:03d}.json',response);obj=response.get('provider_response',{});event.update(status='RESPONSE',provider_id=obj.get('id'),provider_model=obj.get('model'),response_status=response.get('status'),finish_reason=response.get('finish_reason'),usage=response.get('usage',{}),elapsed_seconds=response.get('elapsed_seconds'));write(self.dest/'call_ledger.json',self.events);print('RESPONSE '+str(i)+' '+str(response.get('status')),flush=True);assert obj.get('model') in [None,request['model']],'PROVIDER_MODEL_INTEGRITY_FAILURE';return response
  except Exception as error:
   resp=getattr(error,'response',None);body=resp.text if resp is not None else None;event.update(status='ERROR',error_type=type(error).__name__,diagnostic=str(error).replace(self.key,'[REDACTED]'),http_status=resp.status_code if resp is not None else None,response_body=body.replace(self.key,'[REDACTED]') if body else None,elapsed_seconds=time.monotonic()-start);write(self.dest/'call_ledger.json',self.events);raise RuntimeError('PROVIDER_DISPATCH_FAILURE; see redacted ledger') from None

def run():
 state=load(STATE);assert state['status']=='PREPARED','No repeat dispatch';G=Path(state['group'])
 for name,h in load(G/'original_input_hashes.json').items():assert sha(ROOT/name)==h,'ORIGINAL_INPUT_INTEGRITY_FAILURE'
 for name,h in load(G/'snapshot_hashes.json').items():assert sha(G/'snapshot'/name)==h
 cfg=load(G/'resolved_config.json');context=load(G/'source_schema_context.json');dest=G/RID/'nltl';os.environ.update(NLTL_ENV_FILE=str(ENV),NLTL_ALLOW_MODEL_CALLS='YES');transport=AuditedLive(G,dest);source_events=[];firewall(G,source_events)
 denied=[]
 for p in [ROOT/'evaluation',ROOT/'tests',ROOT/'outputs/experiments',REPO/'MVP/evaluation_audit',G/'snapshot/data/contracts',G/'snapshot/evaluation',G/'snapshot/data/examples']:
  try:p.open('rb')
  except PermissionError:denied.append(str(p))
  else:raise RuntimeError('BOUNDARY_INTEGRITY_FAILURE')
 write(G/'runtime_boundary_verification.json',dict(all_denied=True,denied_paths=denied,content_read=False,initial_prior_issues=[],historical_reviews_not_loaded=True))
 runner=Runner(Project(G/'snapshot'),cfg,transport,dest);runner.admission_context=copy.deepcopy(context['admission']);runner.input_hashes={n:h for n,h in load(G/'snapshot_hashes.json').items() if n.startswith(('data/','schema/','prompts/'))};runner.latest_findings=();tracker=Tracker();assert tracker.prior_semantic_issues()==[]
 current=Candidate(1,(dest/'candidate_01.ttl').read_text(),'');assert current.sha256==SEED;previous=None;fmt=None;history=[];operational=None;status='UNSTARTED';state['status']='RUNNING';write(STATE,state);start=time.monotonic()
 try:
  for version in [1,2]:
   assert current.version==version;attempt_start=time.monotonic();metric_start=len(runner.response_metrics)
   changes=manifest(previous,current) if previous else dict(status='EXACT_SEED_UNCHANGED',changes=[]);write(dest/f'change_manifest_{version:02d}.json',changes)
   if previous:(dest/f'diff_{previous.version:02d}_{version:02d}.patch').write_text(changes['diff'])
   fs=[finding(current,'RESPONSE_FORMAT_ERROR','Missing/ambiguous wrapper',current.raw,expected='<BEGIN_SHACL> ... <END_SHACL>',suggestion='Return one complete unambiguous SHACL block',diagnostic=fmt)] if fmt else check(current,runner.schema,RID,admission=runner.admission_context)
   parsed=not fmt and not any(f.category=='PARSE_ERROR' for f in fs);runtime_complete=False;runner.execution_summaries[version]=probe_summary(current,reason='Current static/format blockers; execution not run')
   if not any(f.blocking for f in fs):
    execution,probe=runtime_probe(current,runner.schema);fs+=execution;runtime_complete=not execution;runner.execution_summaries[version]=probe_summary(current,probe);write(dest/f'runtime_probe_{version:02d}.json',probe)
   write(dest/f'pre_review_findings_{version:02d}.json',[f.asdict() for f in fs]);context,fs,obj,error,conflicts,controller=runner.assess_candidate(current,context,previous,changes,tracker,fs,RID)
   reconciled,persistent=tracker.observe(current,fs,static_complete=parsed,review=obj,runtime_complete=runtime_complete);accepted=not any(f.blocking for f in fs) and not error and not conflicts and obj is not None and obj['decision']=='ACCEPT' and controller=='ACCEPTED'
   resource=any(f.assessment=='RESOURCE_UNCERTAIN' for f in fs);infra=any(f.assessment=='INFRASTRUCTURE_OR_UNKNOWN' for f in fs)
   status='ACCEPTED' if accepted else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if resource else 'INFRASTRUCTURE_FAILURE' if infra else 'REVIEWER_FORMAT_FAILURE' if error else 'CONFLICT' if conflicts else controller if controller in ['UNRESOLVED_CONTEXT','CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST'] else 'REJECTED'
   stagnation=tracker.stagnation_stop(cfg.get('stagnation',{})) if not accepted else None
   if stagnation and status=='REJECTED':status='STAGNATION_STOP'
   row=dict(version=version,sha256=current.sha256,origin='EXACT_HISTORICAL_SEED' if version==1 else 'ONE_MODEL_REPAIR',accepted=accepted,status=status,findings=[f.asdict() for f in fs],review=obj,reviewer_format_failure=error,conflicts=conflicts,changes=reconciled,persistent_failure_summary=persistent,structural_change_manifest=changes,elapsed_seconds=time.monotonic()-attempt_start,request_metrics=runner.response_metrics[metric_start:],regulatory_correctness_certified=False)
   history.append(row);write(dest/'history.json',history);write(dest/f'findings_{version:02d}.json',row['findings']);write(dest/f'reconciliation_{version:02d}.json',reconciled);runner.latest_findings=tuple(fs)
   if accepted or status in ['RESOURCE_ATTRIBUTION_UNCERTAIN','INFRASTRUCTURE_FAILURE','REVIEWER_FORMAT_FAILURE','CONFLICT','UNRESOLVED_CONTEXT','CONTEXT_LIMIT_EXHAUSTED','REPEATED_EVIDENCE_REQUEST','STAGNATION_STOP']:break
   if version==2:status='ATTEMPT_LIMIT_EXHAUSTED';break
   runner.transition(current,'REPAIR_REQUEST_READY',latest_code_complete=True,continuation=True);request=repair_request(runner.p,context,current,fs,persistent_summary=persistent);response=runner.dispatch(request,current);raw=response['text'];fmt=None;normalization=None
   try:code,normalization=normalize(raw)
   except WrapperError as e:code=raw;fmt=str(e)
   previous=current;current=Candidate(2,code,raw);(dest/'candidate_02.ttl').write_text(code);write(dest/'candidate_02.json',dict(version=2,sha256=current.sha256,origin='MODEL_REPAIR',normalization=normalization))
  runner.verify_inputs()
 except Exception as error:
  diagnostic=str(error).replace(transport.key,'[REDACTED]');integrity=any(k in diagnostic for k in ['INTEGRITY','STALE','ABSENT','FEEDBACK','TRUNCATED_PREVIOUS','RENDERED_REQUEST']);status='REQUEST_INTEGRITY_FAILURE' if integrity else 'RESOURCE_ATTRIBUTION_UNCERTAIN' if isinstance(error,(TimeoutError,MemoryError,RecursionError)) or 'timeout' in type(error).__name__.lower() else 'INFRASTRUCTURE_FAILURE';operational=dict(type=type(error).__name__,diagnostic=diagnostic,status=status,no_retry=True);write(dest/'operational_failure.json',operational)
 result=dict(version='0.9.2',run_label='DEVELOPMENT_CONTINUATION',not_fresh_comparative_performance=True,requirement_id=RID,method='NLTL_SEEDED_DEVELOPMENT_CONTINUATION',status=status,candidate_attempts=len(list(dest.glob('candidate_*.ttl'))),seed_sha256=SEED,accepted_version=next((r['version'] for r in history if r['accepted']),None),evaluation_candidate=next((r['version'] for r in history if r['accepted']),None),generation_calls=0,repair_calls=sum(x['route'].endswith('repair') for x in runner.calls),primary_reviews=sum(x['route']=='review' for x in runner.calls),auxiliary_format_retries=sum(x['route']=='review_format_retry' for x in runner.calls),provider_calls=len(transport.events),elapsed_seconds=time.monotonic()-start,history=history,operational_failure=operational,initial_prior_issues=[],failed_historical_reviews_used=False,independent_evaluation_used=False,limits_preserved=True,selection='First internal acceptance only; otherwise NO_VERDICT. Seeded continuation never fresh workflow performance.')
 write(dest/'run.json',result);write(G/'source_file_reads.json',source_events);state.update(status='DISPATCH_CLOSED',outcome=status,accepted_version=result['accepted_version'],candidate_attempts=result['candidate_attempts'],elapsed_seconds=result['elapsed_seconds']);write(STATE,state);write(G/'dispatch_closed.json',state);print('DISPATCH_CLOSED '+status,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);args=p.parse_args();prepare() if args.action=='prepare' else run()
