from pathlib import Path
import sys,json,hashlib,copy,shutil,ast,importlib.metadata
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,load,write,offline_network_guard
from nltlv2.runner import Runner
from nltlv2.transport import ScriptedTransport,provider_payload
from nltlv2.token_budget import load_counter,preflight
from nltlv2.schema import Schema
from nltlv2.admission import validate_declaration,definition_hash

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(A/'offline_tests.json')['success'];old=load(D/'smoke_manifest.json');m=copy.deepcopy(old)
m.update(pipeline_version='0.11.2',dispatch_ready=True,max_physical_calls=20,max_reserved_output_tokens=320000,metadata_HTTP_calls_before_freeze=0,max_total_provider_HTTP_calls_including_metadata=20,freeze_lock=str((A/'freeze_lock.json').relative_to(R)),evaluation_lock=str((A/'evaluation_resources.lock.json').relative_to(R)),authorization='User explicitly authorized exactly one new I2-005/IMO-001 shared-start smoke with reviewer/correction16000 tokens including reasoning, at most20 physical inference calls, no manual edits/regeneration/preferred-result rerun',review_budget_scope='Bounded development setting including reasoning; not a guarantee of sufficient output',no_reasoning_settings_change=True)
m['config'].update(pipeline_version='0.11.2',review_max_tokens=16000)
changes={k:dict(before=old['config'].get(k),after=m['config'].get(k)) for k in set(old['config'])|set(m['config']) if old['config'].get(k)!=m['config'].get(k)};assert set(changes)=={'pipeline_version','review_max_tokens'}
write(A/'authorized_config_changes.json',dict(config=changes,old_output_reservation=128000,new_output_reservation=320000,formula='2*(1 shared generation+1 repair+4 primary reviews+4 shared corrections)*16000=320000',reasoning_settings_changed=False,generation_output_tokens_unchanged=16000,call_cap=20))
profile=m['token_limits'];counter=load_counter(R,profile);scopes={rid:'data/admissions/'+rid.lower().replace('-','_')+'_research_scope.approved.json' for rid in ['I2-004','I2-005','IMO-001','TRF-010','TRF-035']};records=[]
evlock=load(D/'evaluation_resources.lock.json')
for name,h in evlock['files'].items():assert sha(R/name)==h,name
write(A/'evaluation_resources.lock.json',evlock)
proofs=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/evaluation_binding_validation.json')['approved_scope_bindings'];old_resource=load(R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL/frozen_resource_hashes.json')
for name in ['schema/Schema_for_NLTL.ttl']+list(scopes.values()):assert sha(R/name)==old_resource[name]
with offline_network_guard():
 project=Project(R);schema=Schema(project)
 for file in (R/'configs').glob('*.json'):project.config(str(file.relative_to(R)))
 write(A/'configuration_schema_checks.json',schema.audit())
 for rid in scopes:
  admission=validate_declaration(load(R/scopes[rid]),schema,rid);assert admission['valid'];requests={}
  for wf in ['Single-shot','NLTL']:
   cfg=copy.deepcopy(m['config']);cfg['admission_file']=scopes[rid]
   if wf=='Single-shot':cfg.update(method='Single-shot',semantic_review=False,maximum_candidate_attempts=1)
   dest=A/'initial_capture'/rid/wf;dest.mkdir(parents=True)
   Runner(project,cfg,ScriptedTransport([]),dest).run(rid);request=load(dest/'request_001.json');requests[wf]=request;payload=provider_payload(request);payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']];payload.update(truncation='disabled',store=False)
   budget=preflight(payload,profile,counter);assert not budget['exceeds_known_token_limit'];record=load(dest/'request_001_sizes.json');record.update(requirement_id=rid,workflow=wf,token_budget=budget,actual_payload_bytes=len(json.dumps(payload,ensure_ascii=False).encode()));records.append(record)
  assert requests['Single-shot']==requests['NLTL']
  for proof in [p for p in proofs if p['requirement_id']==rid]:
   binding=load(R/proof['binding_file']);assert sha(R/proof['file'])==binding['input_sha256']==proof['sha256'];assert definition_hash(load(R/scopes[rid]))==binding['scope_definition_sha256']==proof['scope_definition_sha256'];assert proof['approved_scope_matches']
write(A/'identical_initial_sizes_tokens.json',records)
# Recount the exact previous review/correction requests with the new output reservation, no model call.
previous=R/'outputs/experiments/20261124_V0111_HOSTED_GPT_OSS_SHARED_START_REPLACEMENT_SMOKE_01/provider';capacity=[]
for n in [3,4]:
 payload=copy.deepcopy(load(previous/f'call_{n:03d}_request.json')['payload']);payload['max_output_tokens']=16000;b=preflight(payload,profile,counter);assert not b['exceeds_known_token_limit'];capacity.append(dict(label='OFFLINE_REQUEST_RESERVATION_RECALCULATION_ONLY',saved_request=n,capacity=b,full_input_unchanged=True))
write(A/'review_capacity_recalculation.json',capacity);write(A/'smoke_manifest.json',m);write(A/'fixed_main_queue.json',load(D/'fixed_main_queue.json'))
production=[]
for folder in ['src/nltlv2','prompts','schema','data/requirements']:
 production.extend(p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
production.extend(R/name for name in scopes.values());production.extend([R/'pyproject.toml',A/'smoke_manifest.json'])
for folder in ['tokenizer_runtime','tokenizer_cache']:production.extend(p for p in (D/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for p in production:
 if p.suffix=='.py':ast.parse(p.read_text())
lock=dict(version='0.11.2',files={str(p.relative_to(R)):sha(p) for p in production},executed_source_version='0.11.2',installed_distribution_metadata=importlib.metadata.version('nltlv2-refined'),python=sys.version,identity_policy='Explicit frozen source PYTHONPATH and pinned tokenizer; source/module hashes checked before every dispatch, legacy installed metadata not misrepresented.')
write(A/'freeze_lock.json',lock)
for p in production:
 dest=A/'runtime'/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for name in ['gptoss_16k_fix.py','gptoss_16k_tests.py','verify_gptoss16k.py','freeze_gptoss16k.py']:shutil.copy2(Path('/tmp')/name,A/name)
write(A/'pre_dispatch.json',dict(status='OFFLINE_VERIFIED_FROZEN',version='0.11.2',tests=load(A/'offline_tests.json'),review_and_correction_max_output_tokens=16000,max_physical_inference_calls=20,max_reserved_output_tokens=320000,initial_request_equality=True,source_freeze_sha256=sha(A/'freeze_lock.json'),metadata_HTTP_calls=0,model_inference_calls=0,source_edits_limited_to_two_authorized_fixes_and_version_metadata=True,provider_framing_and_actual_limits_unknown=True,material_context_truncated=False))
print(json.dumps(load(A/'pre_dispatch.json'),indent=2))
