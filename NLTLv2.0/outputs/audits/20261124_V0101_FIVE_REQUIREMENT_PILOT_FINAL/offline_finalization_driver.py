import pathlib,json,hashlib,copy,shutil,socket,ast,subprocess,sys,datetime
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');O=R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL';PRE=R/'outputs/audits/20261124_FIVE_REQUIREMENT_SCOPE_READINESS';HIST=R/'outputs/experiments/20261124T113231275705Z_V0101_I2_004_DEVELOPMENT_CONTINUATION'
APPROVAL='''I approve the grouped synthetic research-scope proposal and its
experimental edition selections for I2-005, IMO-001, TRF-010 and
TRF-035. I approve TRF-035 option A: recorded ruleLength and a
separately supplied classificationSocietyRuleLength reference datum.

Record this instruction as approval provenance. Retain the stated
limits: research assumptions do not certify real-vessel eligibility,
legal governing editions or society-rule derivation.

Preserve every generated candidate, including the last rejected one,
with its findings and terminal reason. Keep acceptance criteria
identical across attempts. Do not add a lenient final attempt,
fallback acceptance or human-review arm.

Selected NLTL output remains the first internally accepted candidate.
If none is accepted, report NO_VERDICT. Evaluate rejected candidates
only as separately labelled diagnostics; never select by external score.

Finalize the five-requirement paired pilot manifest using the approved
scopes and TRF-035 mapping choice. Verify identical actual initial
requests/settings across arms, evaluation isolation and the existing
55-call maximum with early stopping.

Keep v0.10.1 implementation frozen. No further pipeline changes.
Return final readiness and exact dispatch instructions.
Do not make model calls or dispatch yet.'''
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
assert not O.exists();before={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts};O.mkdir(parents=True);write(O/'protected_before.json',before)
(O/'approval_verbatim.txt').write_text(APPROVAL+'\n')
from nltlv2.core import Project,GenerationProject
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,load_admission,definition_hash,validate_data_scope
from nltlv2.runner import Runner
from nltlv2.transport import provider_payload
from nltlv2.prompt_accounting import measure
from nltlv2.evidence import literal_identity
from rdflib import Graph
p=Project(R);schema=Schema(p);proposal=load(PRE/'approval_proposal.json');approval_ref='User instruction in the current conversation, 2026-11-24 (verbatim approval):\n'+APPROVAL
scopefiles={'I2-004':'data/admissions/i2_004_research_scope.approved.json'};scope_results={}
for item in proposal['scope_files']:
 rid=item['requirement_id'];assert sha(R/item['file'])==item['sha256'];decl=load(R/item['file']);assert definition_hash(decl)==item['scope_definition_sha256']
 decl['provenance']=dict(declarant='User in the current conversation',reference=approval_ref,basis='User-approved grouped synthetic research assumptions and experimental editions; no certification of real-vessel eligibility, governing legal editions or society-rule derivation.')
 decl['approval']=dict(status='APPROVED',approved_by='User in the current conversation',reference=approval_ref)
 for e in decl['source_editions']:e['selection_provenance']=approval_ref+'\nExperimental source selection only, not legally governing-edition determination.'
 assert definition_hash(decl)==item['scope_definition_sha256'];path=item['file'].replace('.proposed.json','.approved.json');assert not (R/path).exists();write(R/path,decl);scopefiles[rid]=path
for rid,path in scopefiles.items():
 result=validate_declaration(load(R/path),schema,rid);assert result['valid'],result;scope_results[rid]=result
write(O/'approved_scope_validation.json',scope_results)
mapping=load(PRE/'trf_035_mapping_decision.proposed.json');write(O/'trf_035_mapping_approval.json',dict(status='APPROVED_OPTION_A',approved_choice=mapping['options'][0],approval_reference=approval_ref,source_proposal_sha256=sha(PRE/'trf_035_mapping_decision.proposed.json'),representation_files_unchanged=True,no_equality_formula_or_expected_verdict_installed=True))
# Freeze a byte-identical installed v0.10.1 runtime copy; do not modify the shared environment.
runtime=O/'runtime';shutil.copytree(HIST/'runtime',runtime,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
sourcefiles={str(f.relative_to(R/'src/nltlv2')):sha(f) for f in (R/'src/nltlv2').rglob('*.py')};installed={str(f.relative_to(runtime/'nltlv2')):sha(f) for f in (runtime/'nltlv2').rglob('*.py')};assert installed==sourcefiles
identity_code='import nltlv2,importlib.metadata,json;print(json.dumps(dict(module_version=nltlv2.__version__,distribution_version=importlib.metadata.version("nltlv2-refined"),module_file=nltlv2.__file__,dependencies={n:importlib.metadata.version(n) for n in ["rdflib","pyshacl","owlrl","requests","python-dotenv"]})))'
import os
env=dict(os.environ,PYTHONPATH=str(runtime),PYTHONDONTWRITEBYTECODE='1');identity=json.loads(subprocess.run([sys.executable,'-B','-c',identity_code],env=env,capture_output=True,text=True,check=True).stdout);assert identity['distribution_version']==identity['module_version']=='0.10.1';assert pathlib.Path(identity['module_file']).is_relative_to(runtime)
identity.update(installed_source_identical=True,python_files=len(sourcefiles),python_executable=sys.executable,shared_environment_unchanged=True);write(O/'runtime_identity.json',identity)
# Existing input bindings retain their scope-definition hashes despite new approval provenance.
construction=load(PRE/'evaluation_construction_review.json');prior_resource_hashes=load(PRE/'pilot_resource_hashes.proposed.json');assert all(sha(R/k)==v for k,v in prior_resource_hashes.items()),'Preparation resources changed'
binding_checks=[];guard_checks=[];bindings={}
for row in construction['rows']:
 rid=row['requirement_id'];binding=load(R/row['binding_file']);decl=scope_results[rid]['context']['declaration'];assert sha(R/row['file'])==binding['input_sha256']==row['input_sha256'];assert binding['scope_id']==decl['admission_id'];assert binding['scope_definition_sha256']==definition_hash(decl);assert row['rdfs_population_equals_declared'] and binding['admitted_nodes']==row['declared_population_nodes']
 bindings.setdefault(row['case_id'],{})[row['kind']]=row['binding_file'];binding_checks.append(dict(requirement_id=rid,file=row['file'],sha256=row['input_sha256'],scope_definition_sha256=binding['scope_definition_sha256'],binding_file=row['binding_file'],approved_scope_matches=True,prior_complete_rdfs_population_proof_reused=True))
for rid in scopefiles:
 row=next(x for x in construction['rows'] if x['requirement_id']==rid)
 with literal_identity():g=Graph().parse(R/row['file'])
 verdict=validate_data_scope(g,schema.graph,scope_results[rid]['context'],load(R/row['binding_file']),row['input_sha256']);assert verdict['valid'],verdict;guard_checks.append(dict(requirement_id=rid,file=row['file'],actual_production_scope_guard=verdict))
write(O/'evaluation_binding_validation.json',dict(inputs=46,approved_scope_bindings=binding_checks,actual_production_guard_checks=guard_checks,coverage_basis='All 46 prior exact-file/ontology RDFS population proofs remain unchanged; five actual approved guard executions verify transition from proposed to approved. No conformance evaluation or expected labels used.',conformance_runs=0))
# Capture the actual production initial-dispatch boundary, without responses or providers.
class Captured(BaseException):pass
class CaptureOnly:
 is_live=False
 def dispatch(self,request,latest=None,expected_findings=None):
  assert request['route']=='generation' and latest is None and not expected_findings
  self.request=copy.deepcopy(request);self.payload=provider_payload(request);raise Captured()
source_path_events=[];original_path=GenerationProject.path
def tracked_path(self,relative):
 value=original_path(self,relative);source_path_events.append(str(relative));return value
GenerationProject.path=tracked_path
rids=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'];jobs=[];sizes=[];BATCH='20261124_V0101_FRESH_FIVE_REQUIREMENT_PAIRED_01';batch_root='outputs/experiments/'+BATCH
for rid in rids:
 requests=[];payloads=[]
 for method in ['Single-shot','NLTL']:
  cfg=load(PRE/'pilot_configs'/(rid+'_'+method+'_PROPOSED.json'));cfg.update(method=method,network_enabled=True,admission_file=scopefiles[rid]);cfg.pop('proposed_method',None);cfg.pop('proposal_only',None)
  cpath=O/'configs'/(rid+'_'+method+'.json');write(cpath,cfg);p.config(str(cpath.relative_to(R)));assert load_admission(p,cfg,schema,rid)['valid']
  out=O/'actual_initial_capture'/rid/method;out.mkdir(parents=True);t=CaptureOnly();runner=Runner(p,cfg,t,out)
  try:runner.run(rid)
  except Captured:pass
  else:raise AssertionError('Capture boundary not reached')
  assert not list(out.glob('candidate_*.ttl'));req=load(out/'request_001.json');assert req==t.request;requests.append(req);payloads.append(t.payload)
  write(out/'capture_receipt.json',dict(label='OFFLINE_PRODUCTION_DISPATCH_BOUNDARY_CAPTURE_NO_PROVIDER',provider_calls=0,model_calls=0,candidates=0,response_supplied=False,source_only_path_events=list(dict.fromkeys(source_path_events))))
  experiment_id=BATCH+'_'+rid.replace('-','_')+'_'+('SINGLE_SHOT' if method=='Single-shot' else 'NLTL');assert not (R/'outputs/experiments'/experiment_id).exists()
  cap=1 if method=='Single-shot' else 10;assert cfg['continuation']['max_provider_calls']==cap
  jobs.append(dict(requirement_id=rid,workflow=method,config=str(cpath.relative_to(R)),config_sha256=sha(cpath),experiment_id=experiment_id,output='outputs/experiments/'+experiment_id,max_provider_calls=cap,execute_at_most_once=True,initial_request=str((out/'request_001.json').relative_to(R))))
 assert requests[0]==requests[1] and payloads[0]==payloads[1]
 for row in construction['rows']:assert row['case_id'] not in requests[0]['system']+requests[0]['user']
 row=measure(requests[0]);row.update(requirement_id=rid,actual_runner_initial_requests_identical=True,actual_provider_payloads_identical=True,provider_payload_default_json_bytes=len(json.dumps(payloads[0],allow_nan=False).encode()),system_sha256=hashlib.sha256(requests[0]['system'].encode()).hexdigest(),user_sha256=hashlib.sha256(requests[0]['user'].encode()).hexdigest(),capture_only=True);sizes.append(row)
GenerationProject.path=original_path
write(O/'actual_initial_request_sizes.json',sizes)
assert sum(x['max_provider_calls'] for x in jobs)==55
# Verify frozen acceptance/selection code, with no attempt-dependent acceptance threshold.
tree=ast.parse((R/'src/nltlv2/runner.py').read_text());assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='accepted' for t in n.targets)];assert len(assignments)==1
names={n.id for n in ast.walk(assignments[0].value) if isinstance(n,ast.Name)};assert not names & {'attempt','maximum','external_score'}
code=(R/'src/nltlv2/runner.py').read_text();assert "next((h['version'] for h in history if h['accepted']),None)" in code
write(O/'acceptance_preservation_review.json',dict(acceptance_expression=ast.unparse(assignments[0].value),line=assignments[0].lineno,identical_expression_all_attempts=True,attempt_or_budget_dependent_threshold=False,first_accepted_selection=True,nltl_fallback=False,every_response_and_candidate_saved_before_checking=True,per_candidate_findings_and_status_in_history=True,final_rejected_candidate_retained=True,terminal_run_reason_in_run_json=True,exception_path='Candidate files and raw packets remain preserved if checking aborts; inventory must explicitly record unavailable findings and operational failure instead of inventing findings.',runtime_source_sha256=sha(R/'src/nltlv2/runner.py')))
isolation=[]
for path in ['evaluation/fixtures/TRF-035-P01.ttl','evaluation/selections/regression_core.json',str((PRE/'evaluation_construction_review.json').relative_to(R)),str((HIST/'I2-004/nltl/candidate_02.ttl').relative_to(R)),str((PRE/'evaluation_only_bindings').relative_to(R))]:
 try:GenerationProject(R).path(path)
 except (ValueError,PermissionError) as e:isolation.append(dict(path=path,denied=True,reason=str(e)))
 else:raise AssertionError('Forbidden resource accessible')
assert all(not x.startswith(('evaluation/','outputs/','tests/','docs/')) for x in source_path_events)
write(O/'evaluation_isolation_verification.json',dict(status='PASS',denials=isolation,actual_initial_source_paths=sorted(set(source_path_events)),source_capture_loaded_evaluation=False,fixture_identifiers_in_requests=False,source_only_capability=True,os_security_sandbox_claimed=False))
limits=load(PRE/'pilot_plan.proposed.json')['per_requirement'];manifest=dict(format_version=1,label='FRESH_PAIRED_FIVE_REQUIREMENT_DEVELOPMENT_PILOT',pipeline_version='0.10.1',status='READY_AWAITING_SEPARATE_DISPATCH_AUTHORIZATION',dispatch_authorized=False,dispatch_started=False,batch_id=BATCH,batch_output=batch_root,requirements=rids,deferred=['I2-042'],destination='https://aalto-openai-apigw.azure-api.net/v1/openai/responses',model='gpt-5.6-luna-2026-07-09',runtime=str(runtime.relative_to(R)),jobs=jobs,max_provider_calls=55,per_requirement=limits,initial_generations_per_requirement_per_arm=1,seeded_shapes=False,prior_issues=[],regeneration=False,acceptance=dict(policy='Same frozen checks and review criteria for every attempt; first internally accepted NLTL candidate only.',lenient_final_attempt=False,fallback_acceptance=False,human_review_arm=False,external_score_selection=False,no_accepted_candidate='NO_VERDICT',run_integrity_failure='NO_VERDICT even if an earlier history row had accepted=true'),preservation=dict(all_generated_candidates=True,last_rejected_candidate=True,all_requests_responses=True,all_diagnostics_findings=True,all_terminal_reasons=True,all_diffs_and_change_assessments=True,operational_failure_inventory='Preserve orphan candidate files and record findings unavailable with operational reason; never silently omit them.'),scope_files=scopefiles,scope_definition_sha256={rid:scope_results[rid]['context']['scope_definition_sha256'] for rid in rids},trf_035_mapping='APPROVED_OPTION_A',evaluation=dict(model_access=False,only_after_all_dispatches_close=True,original_cases=30,counterparts=16,bindings=bindings,scope_by_requirement=scopefiles,selected_nltl='FIRST_INTERNAL_ACCEPTANCE_OR_NO_VERDICT',rejected_candidates='SEPARATELY_LABELLED_REJECTED_CANDIDATE_DIAGNOSTICS_NEVER_SELECTED_BY_SCORE',external_above_maximum_diagnostic_excluded=True,held_out=False,driver_policy='Existing independent.validate_admitted_graph per requirement with that approved scope and exact binding; generic evaluate() assumes one scope/37 cases and is not this five-requirement manifest. Do not reuse an incompatible historical driver.'),actual_initial_sizes_file=str((O/'actual_initial_request_sizes.json').relative_to(R)),calls_formula='5 * (1 Single-shot + 2 NLTL candidate calls + 4 primary reviews + 4 shared corrections) = 55; caps are maxima, early acceptance/terminal outcomes stop each workflow.',run_once=True,no_automatic_retry_of_jobs=True)
assert not (R/batch_root).exists();write(O/'pilot_manifest.json',manifest)
# Freeze resources, approved declarations, all preparation configs and installed runtime.
freeze={str(f.relative_to(R)):sha(f) for folder in ['src','prompts','schema','data/requirements','data/admissions'] for f in (R/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
for folder in [O/'runtime',O/'configs',O/'actual_initial_capture']:
 for f in folder.rglob('*'):
  if f.is_file():freeze[str(f.relative_to(R))]=sha(f)
freeze[str((O/'pilot_manifest.json').relative_to(R))]=sha(O/'pilot_manifest.json');write(O/'frozen_resource_hashes.json',freeze)
write(O/'preservation_verification.json',dict(status='PASS',existing_files_checked=len(before),modified_existing=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h],new_approved_scopes=4,model_calls=0,provider_calls=0,candidates_generated=0,live_transport_constructed=False,conformance_evaluation_reruns=0,implementation_frozen=True))
assert load(O/'preservation_verification.json')['modified_existing']==[]
shutil.copy2('/tmp/nltl_finalize_approved_pilot.py',O/'offline_finalization_driver.py')
print(json.dumps(dict(output=str(O),scopes_valid=5,guard_checks=5,matching_actual_initial_requests=5,sizes=[dict(requirement_id=x['requirement_id'],bytes=x['rendered_bytes']) for x in sizes],max_provider_calls=55,old_files_unchanged=len(before),runtime=identity),indent=2),flush=True)
