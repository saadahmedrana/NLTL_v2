from pathlib import Path
import sys,os,json,hashlib,copy,shutil,ast,importlib.metadata
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(A/'tokenizer_runtime')]
from nltlv2.core import Project,load,write,offline_network_guard
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport,provider_payload
from nltlv2.token_budget import load_counter,preflight
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,definition_hash

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(A/'offline_tests.json')['success'];profile=load(A/'token_limits.verified.json');counter=load_counter(R,profile)
old=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json');previous=load(R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/smoke_manifest.json')
base=copy.deepcopy(previous['config']);base['pipeline_version']='0.11.1';scopes={rid:'data/admissions/'+rid.lower().replace('-','_')+'_research_scope.approved.json' for rid in ['I2-004','I2-005','IMO-001','TRF-010','TRF-035']}
input_lock=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_resources.lock.json')
for name,h in input_lock.items():assert sha(R/name)==h,name
old_resources=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/frozen_resource_hashes.json')
for name in ['schema/Schema_for_NLTL.ttl']+list(scopes.values()):assert sha(R/name)==old_resources[name],name
proofs=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json')['approved_scope_bindings'];records=[]
with offline_network_guard():
 project=Project(R);schema=Schema(project)
 for name in project.path('configs').glob('*.json'):project.config(str(name.relative_to(R)))
 write(A/'configuration_schema_checks.json',schema.audit())
 for rid in scopes:
  admission=validate_declaration(load(R/scopes[rid]),schema,rid);assert admission['valid'];requests={}
  for wf in ['Single-shot','NLTL']:
   cfg=copy.deepcopy(base);cfg['admission_file']=scopes[rid]
   if wf=='Single-shot':cfg.update(method='Single-shot',semantic_review=False,maximum_candidate_attempts=1)
   dest=A/'initial_capture'/rid/wf;dest.mkdir(parents=True)
   runner=Runner(project,cfg,ScriptedTransport([]),dest);runner.run(rid);request=load(dest/'request_001.json');requests[wf]=request
   payload=provider_payload(request);payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']];payload.update(truncation='disabled',store=False)
   count=preflight(payload,profile,counter);assert not count['exceeds_known_token_limit']
   size=load(dest/'request_001_sizes.json');size.update(requirement_id=rid,workflow=wf,actual_payload_bytes=len(json.dumps(payload,ensure_ascii=False).encode()),token_budget=count);records.append(size)
  assert requests['Single-shot']==requests['NLTL']
  for proof in [p for p in proofs if p['requirement_id']==rid]:
   binding=load(R/proof['binding_file']);assert proof['approved_scope_matches'] and proof['prior_complete_rdfs_population_proof_reused'];assert sha(R/proof['file'])==binding['input_sha256']==proof['sha256'];assert definition_hash(load(R/scopes[rid]))==binding['scope_definition_sha256']==proof['scope_definition_sha256']
write(A/'identical_initial_sizes_and_tokens.json',records)
# Locked evaluation resources never enter dispatch's source-only file list.
evfiles={str(p.relative_to(R)):sha(p) for p in (R/'evaluation').rglob('*') if p.is_file() and '__pycache__' not in p.parts};evfiles.update(input_lock)
for name in ['outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json','outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json']:evfiles[name]=sha(R/name)
write(A/'evaluation_resources.lock.json',dict(files=evfiles))
queue=load(R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/fixed_main_queue.json');queue.pop('readiness_blockers');queue['selection_basis']='Same predeclared source/schema/scope-ready shuffled queue; capacity blockers removed only because arbitrary byte guard is removed and verified supplied-text+output counts fit the published model context; no generated-performance filter';write(A/'fixed_main_queue.json',queue)
smoke=dict(label='HOSTED_GPT_OSS_SHARED_START_SMOKE',pipeline_version='0.11.1',dispatch_ready=True,destination='https://ai-api-v2.aalto.fi/v1/responses',model='gpt-oss-120b',requirements=['I2-005','IMO-001'],scope_files={rid:scopes[rid] for rid in ['I2-005','IMO-001']},config=base,token_limits=profile,max_physical_calls=19,metadata_HTTP_calls_before_freeze=1,max_total_provider_HTTP_calls_including_metadata=20,max_reserved_output_tokens=128000,max_execution_seconds=7200,request_timeout_seconds=180,start_requirement_reserve_seconds=1920,freeze_lock=str((A/'freeze_lock.json').relative_to(R)),evaluation_lock=str((A/'evaluation_resources.lock.json').relative_to(R)),authorization='User explicitly authorized one replacement I2-005/IMO-001 hosted shared-start smoke, maximum20 physical provider calls; one non-inference catalog GET was used, leaving at most19 inference calls, no regeneration or preferred-result reruns',evaluation_policy='Same unchanged-shape execution for both arms; raw behavior and scope-qualified credit separate; no scope violation suppressed; all candidates diagnostic; selection frozen before evaluation',final_review='Existing deterministic terminal handoff; no extra model call, human arm or repair',provider_internal_timings='UNAVAILABLE',packet_size_limit_bytes=None,no_silent_context_truncation=True)
write(A/'smoke_manifest.json',smoke)
production=[]
for folder in ['src/nltlv2','prompts','schema','data/requirements']:
 production.extend(p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
production.extend(R/p for p in scopes.values());production.extend([R/'pyproject.toml',A/'smoke_manifest.json'])
for folder in ['tokenizer_runtime','tokenizer_cache']:
 production.extend(p for p in (A/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for p in production:
 if p.suffix=='.py':ast.parse(p.read_text())
lock=dict(version='0.11.1',files={str(p.relative_to(R)):sha(p) for p in production},executed_source_version='0.11.1',installed_distribution_metadata=importlib.metadata.version('nltlv2-refined'),python=sys.version,tokenizer='tiktoken0.12.0 o200k_harmony; verified cache SHA256',identity_policy='Explicit frozen PYTHONPATH source plus pinned local tokenizer dependencies; module files verified by hash. Legacy installed package metadata is not represented as the executed version.')
write(A/'freeze_lock.json',lock)
for p in production:
 dest=A/'runtime'/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
write(A/'pre_dispatch.json',dict(status='OFFLINE_VERIFIED_FROZEN',version='0.11.1',tests=load(A/'offline_tests.json'),all_five_initial_pairs_identical=True,all_five_text_token_plus_output_counts_within_published_model_context=True,provider_context_limit_and_full_framing='UNKNOWN_EXPLICIT',model_inference_calls=0,metadata_provider_HTTP_calls=1,remaining_inference_call_cap=19,total_provider_HTTP_cap=20,all_46_retained_input_proofs_verified=True,source_freeze_sha256=sha(A/'freeze_lock.json'),no_byte_dispatch_guard=True,no_tracker_prompt_scope_ontology_fixture_changes=True,main_not_dispatched=True))
for name in ['hosted_replacement_discovery.py','cache_hosted_tokenizer.py','implement_hosted_replacement.py','fix_hosted_evaluation.py','add_replacement_tests.py','verify_replacement_offline.py','freeze_hosted_replacement.py']:
 p=Path('/tmp')/name
 if p.exists():shutil.copy2(p,A/name)
print(json.dumps(load(A/'pre_dispatch.json'),indent=2))
