from pathlib import Path
import json,hashlib,ast,re,collections
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2');R=ROOT/'NLTLv2.0';M=ROOT/'MVP/SHACL_GENERATION_PIPELINE';A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';O=A/'information_flow_audit_20261124';inputs=json.loads((O/'input_hashes.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):p=Path(p);inputs[str(p)]=sha(p);return p.read_text()
def load(p):return json.loads(read(p))
def write(name,x):(O/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def packet(p):
 s=read(p);header,body=s.split('--- USER INPUT ---',1);return header,json.loads(body)
ids=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'];hist=[]
for exp,config in [('LUNA_NO_SEMANTIC_VALIDATOR','pipeline.luna-no-semantic-validator-run01.json'),('FULL_REPAIR_V2','pipeline.full-repair-v2-run01.json')]:
 cfgpath=M/'experiments'/exp/'CONFIGS'/config;cfg=load(cfgpath);matched=[]
 sessions=list((M/'experiments'/exp/'RUN_01/sessions').glob('*/batch_result.json'));batch=load(sessions[0]);batchidentity={k:v for k,v in batch.items() if k!='results'}
 for rid in ids:
  d=next((M/'experiments'/exp/'RUN_01/runs').glob('RUN-'+rid+'-*'));events=[json.loads(x) for x in read(d/'events.jsonl').splitlines() if x.strip()];gh,gen=packet(d/'artifacts/attempt_01/generator_prompt.txt');context=load(d/'artifacts/context_pack_initial.json');shots=load(d/'artifacts/few_shots_selected.json');case=dict(requirement_id=rid,run=str(d),start_event=events[0],terminal=next(e for e in reversed(events) if e['event_type']=='run_finished'),generator_packet=str(d/'artifacts/attempt_01/generator_prompt.txt'),generator_header=gh,requirement=gen['requirement'],selection=gen['selection'],usage_policy=gen['usagePolicy'],node_patterns=gen['nodePatterns'],vocabulary_terms=gen['allowedVocabulary'],few_shots=[dict(exampleId=x.get('exampleId'),inputRequirement=x.get('inputRequirement'),status=x.get('status')) for x in shots],actual_generator_keys=list(gen),actual_generator_prompt_bytes=(d/'artifacts/attempt_01/generator_prompt.txt').stat().st_size,api_calls=[e for e in events if e['event_type']=='api_call_completed'],candidate_sha256=sha(d/'artifacts/attempt_01/candidate_shape.ttl'))
  if exp=='FULL_REPAIR_V2':
   vh,v=packet(d/'artifacts/attempt_01/validator_prompt_01.txt');case.update(validator_header=vh,validator_packet=str(d/'artifacts/attempt_01/validator_prompt_01.txt'),validator_keys=list(v),validator_raw=read(d/'artifacts/attempt_01/validator_raw_01.txt'),current_issues=load(d/'artifacts/attempt_01/structured_current_issues.json'),syntax_repair_packets=[])
   for sp in (d/'artifacts/attempt_01').glob('syntax_repair_prompt_*.txt'):
    h,b=packet(sp);case['syntax_repair_packets'].append(dict(path=str(sp),header=h,keys=list(b),diagnostics=b.get('syntaxDiagnostics'),full_previous_response_present=bool(b.get('candidateResponse'))))
  matched.append(case)
 identity=dict(experiment=exp,config_file=str(cfgpath),config_sha256=sha(cfgpath),saved_batch=str(sessions[0]),batch_identity=batchidentity,model_settings=cfg['models'],limits=cfg['generation'],api_limits={k:v for k,v in cfg['api'].items() if k in ['persistent_transient_retries','validator_response_retries','contract_response_retries','max_output_tokens']},prompt_directory=cfg['paths']['prompt_directory'],matched=matched)
 hist.append(identity)
# Retained evaluation identity ties operational MVP to syntax-only, not PipelineRunner.
prov=load(ROOT/'MVP/comparison_review_2026-11-24/baseline_provenance.json');manifest=read(M/'evaluation/generated_rule_manifests/RUN_01/no_semantic_generated_rules.jsonl');mr=[json.loads(x) for x in manifest.splitlines() if x.strip()];proof=[]
for row in mr:
 if row['requirement_id'] in ids:
  p=ROOT/row['generated_shacl_path'];assert sha(p)==row['generated_shacl_sha256'];proof.append(row)
write('historical_implementation_identities.json',dict(baseline_mapping=prov['retained_result_cohort'],baseline_actual_manifest_matched_rows=proof,implementations=hist,identity_caveat='Saved events/config hashes/actual packets establish executed routes. Complete immutable historical source snapshots are not claimed for MVP/FULL_REPAIR_V2. Current source locations supplement,not replace,saved packet identity.'))
# Actual semantic repair in V2 is an unmatched requirement; do not pretend the matched five were repaired.
d=M/'experiments/FULL_REPAIR_V2/RUN_01/runs/RUN-TRF-086-20260915T134745469954Z';h,b=packet(d/'artifacts/attempt_02/semantic_repair_prompt.txt');events=[json.loads(x) for x in read(d/'events.jsonl').splitlines() if x.strip()];pre=(d/'artifacts/attempt_01/candidate_shape.ttl').read_text();assert b['previousCandidateShacl']==pre
write('full_repair_v2_actual_semantic_example.json',dict(label='UNMATCHED_REQUIREMENT_FEEDBACK_MECHANISM_ONLY_NOT_CONTROLLED_ACCURACY_COMPARISON',run=str(d),start=events[0],terminal=next(e for e in reversed(events) if e['event_type']=='run_finished'),prompt_file=str(d/'artifacts/attempt_02/semantic_repair_prompt.txt'),header=h,previous_candidate_complete=True,previous_sha256=sha(d/'artifacts/attempt_01/candidate_shape.ttl'),current_issues=load(d/'artifacts/attempt_01/structured_current_issues.json'),actual_repair_packet=b,repair_output_sha256=sha(d/'artifacts/attempt_02/candidate_shape.ttl'),after_issues=load(d/'artifacts/attempt_02/structured_current_issues.json'),metadata=load(d/'artifacts/attempt_02/attempt_metadata.json')))
# Actual syntax-only baseline repair with no semantic-loop claim.
d=next((M/'experiments/LUNA_NO_SEMANTIC_VALIDATOR/RUN_01/runs').glob('RUN-I2-009-*'));h,b=packet(d/'artifacts/attempt_01/syntax_repair_prompt_01.txt');events=[json.loads(x) for x in read(d/'events.jsonl').splitlines() if x.strip()]
write('mvp_actual_syntax_example.json',dict(run=str(d),prompt_file=str(d/'artifacts/attempt_01/syntax_repair_prompt_01.txt'),header=h,packet=b,complete_latest_raw_response=b['candidateResponse']==read(d/'artifacts/attempt_01/generator_raw.txt'),terminal=next(e for e in reversed(events) if e['event_type']=='run_finished')))
C=R/'outputs/experiments/20261124T113231275705Z_V0101_I2_004_DEVELOPMENT_CONTINUATION';d=C/'I2-004/nltl';cs=load(C/'results_summary.json');identity=load(C/'installed_source_identity.json');rows=[]
for n in range(1,5):
 req=load(d/f'request_{n:03d}.json');provider=load(d/f'provider_request_{n:03d}.json');body=provider['body'];u=body['input'][1]['content'];u=u[0]['text'] if isinstance(u,list) else u;assert u==req['user'];p=json.loads(u);response=load(d/f'response_{n:03d}.json');entries=p['evidence_catalog']['entries'];rows.append(dict(index=n,route=req['route'],provider_packet=str(d/f'provider_request_{n:03d}.json'),endpoint_origin=provider['endpoint_origin'],endpoint_path=provider['endpoint_path'],model=body['model'],max_output_tokens=body['max_output_tokens'],body_bytes=len(json.dumps(body,ensure_ascii=False).encode()),candidate_version=p['candidate_version'],candidate_sha256=p['candidate_sha256'],evidence_counts=dict(collections.Counter(e['kind'] for e in entries)),source_chars=sum(len(e['text']) for e in entries if e['kind']=='SOURCE'),previous_candidate_full=bool(p.get('previous_candidate') or p.get('full_candidate')),findings=p.get('current_findings'),response=response.get('text'),prior_issues=p.get('prior_issues'),full_provider_request=provider))
codecmp={}
for name in ['src/nltlv2/review_validation.py','src/nltlv2/requests.py','src/nltlv2/review_protocol.py','src/nltlv2/context_resolution.py','src/nltlv2/source_context.py','prompts/reviewer.txt','prompts/repair.txt']:
 p=C/'snapshot'/name;q=A/'runtime'/name
 if p.exists():codecmp[name]=dict(old_sha256=sha(p),current_sha256=sha(q),identical=sha(p)==sha(q))
write('successful_v0101_continuation_comparison.json',dict(identity_file=str(C/'installed_source_identity.json'),identity=identity,summary=cs,actual_packets=rows,snapshot_code_comparison=codecmp,diff=read(d/'diff_01_02.patch'),actual_model_review_fields_unchanged=True,controlled_comparison=False,limits='Seeded parseable historical candidate,Luna instead ofGPT-OSS,older source/schema context and accepted-only selection. Six-case original benchmark was6/6 for seed AND repair; maximum-direction improvement was demonstrated separately,not a benchmark-score increase.'))
# Line references for actual rules and historical supplement source.
refs=load(O/'function_references.json')
for p in [M/'src/nltl_pipeline/orchestration/no_semantic_validator.py',M/'src/nltl_pipeline/orchestration/runner.py',M/'src/nltl_pipeline/prompts.py',M/'src/nltl_pipeline/validation/contracts.py']:
 s=read(p)
 for node in ast.walk(ast.parse(s)):
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)):refs[str(p)+':'+node.name]=node.lineno
write('function_references.json',refs);write('input_hashes.json',inputs)
print(json.dumps(dict(historical_matched_runs=10,matched_V2_semantic_repairs=0,unmatched_actual_semantic_repairs=1,baseline_actual_syntax_examples=1,successful_continuation_calls=4,review_validator_prompt_and_packet_unchanged_since_v0101={k:v['identical'] for k,v in codecmp.items()}),indent=2))
