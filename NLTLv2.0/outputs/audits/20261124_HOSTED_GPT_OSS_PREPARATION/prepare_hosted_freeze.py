from pathlib import Path
import sys,json,hashlib,copy,shutil,random,importlib.metadata,ast,os
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');sys.path[:0]=[str(R/'src')]
from nltlv2.core import Project,load,write,offline_network_guard
from nltlv2.schema import Schema
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport,provider_payload
from nltlv2.admission import validate_declaration,validate_data_scope,definition_hash
from nltlv2.evidence import literal_identity
from rdflib import Graph
A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(A/'offline_tests.json')['success']
base=load(R/'configs/nltl.json');base.update(model='gpt-oss-120b',pipeline_version='0.11.0',maximum_candidate_attempts=2,review_format_retries=1,delivery_policy='latest_technical',network_enabled=True,continuation={'max_provider_calls':9})
base['context_resolution'].update(max_rounds=2,max_reviews_per_candidate=3,max_reviews_per_run=4)
scopes={rid:'data/admissions/'+rid.lower().replace('-','_')+'_research_scope.approved.json' for rid in ['I2-004','I2-005','IMO-001','TRF-010','TRF-035']}
old=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json')
proofs=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json')['approved_scope_bindings']
oldlock=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_resources.lock.json')
for name,h in oldlock.items():assert sha(R/name)==h,('RETAINED_INPUT_PROOF_STALE',name)
oldresources=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/frozen_resource_hashes.json')
for name in ['schema/Schema_for_NLTL.ttl']+list(scopes.values()):assert sha(R/name)==oldresources[name]
write(A/'redundant_inference_interrupted.json',dict(status='INTERRUPTED_REDUNDANT_OFFLINE_INFERENCE',model_calls=0,basis='Reuse existing complete RDFS population proofs only after exact input, binding, ontology and approved-scope hashes match'))
records=[];input_checks=[]
with offline_network_guard():
 for f in (R/'configs').glob('*.json'):Project(R).config(str(f.relative_to(R)))
 S=Schema(Project(R));audit=S.audit();write(A/'configuration_schema_checks.json',audit)
 for rid in scopes:
  requests={}
  for wf in ['Single-shot','NLTL']:
   cfg=copy.deepcopy(base);cfg['admission_file']=scopes[rid]
   if wf=='Single-shot':cfg.update(method=wf,semantic_review=False,maximum_candidate_attempts=1)
   dest=A/'initial_capture_final'/rid/wf;dest.mkdir(parents=True)
   # Capture production-rendered request without dispatching; exhaustion here is intentional software evidence.
   run=Runner(Project(R),cfg,ScriptedTransport([]),dest);run.run(rid);request=load(dest/'request_001.json');requests[wf]=request
   record=load(dest/'request_001_sizes.json');record.update(requirement_id=rid,workflow=wf);records.append(record)
  assert requests['NLTL']==requests['Single-shot']
  if rid in ['I2-005','IMO-001']:assert len(json.dumps(provider_payload(requests['NLTL'])).encode())<110000
  admission=validate_declaration(load(R/scopes[rid]),S,rid);assert admission['valid']
  for c in load(R/'evaluation/selections/regression_core.json')['cases']:
   if c['requirement_id']!=rid:continue
   for kind in ['fixture','counterfactual']:
    if not c.get(kind):continue
    with literal_identity():g=Graph().parse(R/c[kind])
    binding_file=old['evaluation']['bindings'][c['case_id']][kind];binding=load(R/binding_file)
    proof=next(p for p in proofs if p['file']==c[kind] and p['binding_file']==binding_file)
    assert proof['approved_scope_matches'] and proof['prior_complete_rdfs_population_proof_reused']
    assert sha(R/c[kind])==binding['input_sha256']==proof['sha256']
    assert binding['scope_definition_sha256']==proof['scope_definition_sha256']==definition_hash(load(R/scopes[rid]))
    input_checks.append(dict(requirement_id=rid,case_id=c['case_id'],kind=kind,input_sha256=sha(R/c[kind]),valid=True))
write(A/'identical_initial_request_sizes.json',records);write(A/'evaluation_only_readiness.json',input_checks)
queue=list(scopes);random.Random(20261124).shuffle(queue)
blockers={r['requirement_id']:'Initial complete packet exceeds conservative110000-byte request bound; hosted tokenizer/capacity not verified; no truncation' for r in records if r['workflow']=='NLTL' and r['rendered_bytes']>109000}
write(A/'fixed_main_queue.json',dict(readiness_blockers=blockers,seed=20261124,requirements=queue,deferred=['I2-042'],selection_basis='All five existing source/schema/approved-scope-ready requirements, shuffled before hosted model dispatch; no generated-performance filter',prior_exposure={rid:'Earlier Aalto development pilot; smoke requirements additionally exposed in upcoming smoke' if rid in ['I2-005','IMO-001'] else 'Earlier Aalto development pilot' for rid in queue},held_out=False))
# Evaluation resources are locked here and never opened by dispatch.
evpaths=[p for p in (R/'evaluation').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
evpaths+=[R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/pilot_manifest.json',R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json']
for bindings in old['evaluation']['bindings'].values():evpaths.extend(R/f for f in bindings.values())
write(A/'evaluation_resources.lock.json',dict(files={str(p.relative_to(R)):sha(p) for p in evpaths}))
manifest=dict(label='HOSTED_GPT_OSS_SHARED_START_SMOKE',pipeline_version='0.11.0',destination='https://ai-api-v2.aalto.fi/v1/responses',model='gpt-oss-120b',requirements=['I2-005','IMO-001'],scope_files={rid:scopes[rid] for rid in ['I2-005','IMO-001']},config=base,max_physical_calls=20,max_reserved_output_tokens=128000,max_execution_seconds=7200,max_request_bytes=110000,request_timeout_seconds=180,start_requirement_reserve_seconds=1920,freeze_lock=str((A/'freeze_lock.json').relative_to(R)),evaluation_lock=str((A/'evaluation_resources.lock.json').relative_to(R)),authorization='User explicitly authorizes hosted source/schema/scope/candidate/diagnostic delivery, two requirements, at most20 physical calls; no fixture/label/counterpart/history inputs',no_provider_internal_timing=True,token_limits='Per request: generation/repair16000, review/correction4000;128000 reserved output-token ceiling. Input bounded by110000 serialized UTF8 bytes/call, never silently truncated; exact provider tokens recorded when supplied.',final_review='Deterministic terminal review handoff; no additional call or repair; ACCEPTED/UNVERIFIED delivery and APPROVE/HUMAN_REVIEW_REQUIRED/REJECT remain distinct')
write(A/'smoke_manifest.json',manifest)
# Snapshot contains production inputs only. No historical output, benchmark, witness or solution file.
production=[]
for folder in ['src/nltlv2','prompts','schema','data/requirements']:
 production.extend(p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
production.extend(R/f for f in scopes.values());production.extend([R/'pyproject.toml',A/'smoke_manifest.json'])
for p in production:
 if p.suffix=='.py':ast.parse(p.read_text())
lock=dict(version='0.11.0',files={str(p.relative_to(R)):sha(p) for p in production},installed_distribution_metadata=importlib.metadata.version('nltlv2-refined'),source_version='0.11.0',identity_policy='Executed source hashes match frozen runtime and source; shared environment package metadata is legacy and is not represented as the executed source version',python=sys.version,dependencies={n:importlib.metadata.version(n) for n in ['rdflib','pyshacl','owlrl','requests','python-dotenv']},context_capacity='Hosted capacity/revision not independently pinned; request byte bound and truncation=disabled; provider rejection is terminal, never silently shortened')
write(A/'freeze_lock.json',lock)
for p in production:
 dest=A/'runtime'/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
write(A/'pre_dispatch.json',dict(status='OFFLINE_VERIFIED_FROZEN',tests=load(A/'offline_tests.json'),initial_request_equality=True,model_calls=0,smoke_requirements=manifest['requirements'],fixed_main_queue=queue,approved_scopes_verified=5,evaluation_input_bindings_verified=len(input_checks),source_freeze_sha256=sha(A/'freeze_lock.json'),implementation_version='0.11.0',previous_version_backup='original/',new_main_experiment_not_launched=True,triton_preparation='STOPPED'))
print(json.dumps(load(A/'pre_dispatch.json'),indent=2))
