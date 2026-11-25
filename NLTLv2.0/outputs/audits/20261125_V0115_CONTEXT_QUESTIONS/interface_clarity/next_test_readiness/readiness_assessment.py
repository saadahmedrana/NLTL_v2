from pathlib import Path
import json,sys,copy,hashlib,socket,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS';C=A/'interface_clarity';N=C/'next_test_readiness';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(R/'src'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,write
from nltlv2.schema import Schema
from nltlv2.admission import load_admission
from nltlv2.requests import initial_request
from nltlv2.transport import provider_payload
from nltlv2.token_budget import load_counter,preflight
from nltlv2.hosted_pilot import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
assert load(C/'verification.json')['success'] and load(C/'verification.json')['tests']==303
for n,h in load(C/'tested_source_hashes.json').items():assert sha(R/n)==h,'TESTED_SOURCE_CHANGED '+n
N.mkdir(exist_ok=False);m=load(A/'diagnostic.prepared.json');schema=Schema(Project(R));counter=load_counter(R,m['token_limits']);rows=[];inputs=set();scopefiles={};cfgbase=copy.deepcopy(m['config'])
for rid in ['I2-004','I2-005','TRF-010','TRF-035']:
 scope='data/admissions/'+rid.lower().replace('-','_')+'_research_scope.approved.json';scopefiles[rid]=scope;cfg=copy.deepcopy(cfgbase);cfg['admission_file']=scope;ad=load_admission(Project(R),cfg,schema,rid);ctx=schema.context(rid);ctx['admission']=copy.deepcopy(ad['context']);ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 for edition in ad['context']['declaration']['source_editions']:assert sha(R/edition['file'])==edition['sha256'];inputs.add(edition['file'])
 request=initial_request(Project(R),ctx,{k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']});request.update(model=cfg['model'],max_output_tokens=cfg['generation_max_tokens']);payload=provider_payload(request);payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']];payload.update(truncation='disabled',store=False);capacity=preflight(payload,m['token_limits'],counter)
 blockers=[]
 if not ad['valid']:blockers.append(ad['errors'])
 if capacity['exceeds_known_token_limit']:blockers.append('Known input/output token capacity exceeded')
 rows.append(dict(requirement_id=rid,status='READY_FOR_BOUNDED_DEVELOPMENT_DIAGNOSTIC' if not blockers else 'BLOCKED',blockers=blockers,approved_scope_file=scope,approved_scope_sha256=sha(R/scope),population_scope=ad['context']['declaration']['population_description'],source_documents=[dict(file=d['file'],sha256=sha(R/d['file'])) for d in ctx['source_documents']],source_clause=ctx['requirement']['clause'],representation_contract=ctx['contract'],quantity_encoding=ctx['quantityEncoding'],source_selection_gaps=ctx.get('unresolvedSourceContext',[]),unresolved_vocabulary_ownership=ctx['unresolvedOwnership'],capacity=capacity,initial_request_bytes=len(json.dumps(payload,ensure_ascii=False).encode()),source_selection_is_not_completeness_proof=True,missing_required_information_stays_blocking_during_review=True,prior_exposure=True,generated_outputs_or_scores_consulted_for_selection=False))
 inputs.add(scope);inputs.update(d['file'] for d in ctx['source_documents'])
write(N/'four_requirement_readiness.json',rows)
# A DISTINCT current snapshot, not an edited/reused earlier v0.11.5 lock.
names=set(load(A/'freeze_lock.json')['files']);names.update(str(p.relative_to(R)) for p in (R/'src/nltlv2').glob('*.py'));names.update(['tests/test_prompt_clarity.py']);names.update(inputs)
lock=dict(snapshot_id='V0115_INTERFACE_CLARITY_20261125_TESTED_303',version='0.11.5',label='CURRENT_TESTED_SOURCE_PROMPTS_AND_READINESS_RESOURCES_NOT_EARLIER_V0115_FREEZE',tests=303,files={n:sha(R/n) for n in sorted(names)})
write(N/'current_tested_snapshot.json',lock);verify(R,lock)
recommended='TRF-035';assert next(r for r in rows if r['requirement_id']==recommended)['status'].startswith('READY')
manifest=copy.deepcopy(m);manifest.update(label='HOSTED_GPT_OSS_SHARED_START_DEVELOPMENT',requirements=[recommended],scope_files={recommended:scopefiles[recommended]},freeze_lock=str((N/'current_tested_snapshot.json').relative_to(R)),dispatch_ready=True,prepared_only=True,authorization='OFFLINE_READINESS_ONLY. No model calls authorized by this artifact; launch requires explicit user execution/authorization.',approval_required='No dispatch in current task.',initial_context_questions=[],initial_prior_issues=[],diagnostic_label='FRESH_TRF035_SHARED_START_SEMANTIC_HANDOFF_DIAGNOSTIC',prior_exposure={recommended:'Previously included in the five-requirement development set; not held out. Selection is source/schema/scope based; no saved candidate, review, repair solution or performance imported.'},question_carryforward_policy='Only questions validated during the new diagnostic; never import historical questions or solutions.',exercise_policy='No forced issue/repair/approval; early stopping. Unexercised semantic repair is NOT_EXERCISED. No regeneration/manual edits/preferred-result rerun.',selection_basis='TRF-035 has an approved distinction between a recorded quantity and separately supplied society reference, explicit direct owner mappings, and canonical quantity encoding. This isolates handoff/citation/operand roles without the unresolved IMO design-intent equivalence.',planned_set_accounting=dict(historical_five_requirement_set=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'],current_readiness_assessed=['I2-004','I2-005','TRF-010','TRF-035'],recommended_next_single_requirement=recommended,not_selected_this_diagnostic=['I2-004','I2-005','TRF-010'],blocked_not_dropped={'IMO-001':'Unresolved polar-waters design-intent representation; remains in historical/planned-set accounting. No rerun authorized.'},deferred=['I2-042']))
# No candidates/solutions/reviewer findings/diagnostic-specific instructions in config or production prompts.
write(N/'TRF035.shared_start.manifest.json',manifest)
command='''# MODEL CALLS: run only when you choose to authorize/launch this diagnostic.
NLTL_PROJECT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_ALLOW_MODEL_CALLS=YES \\
NLTL_ENV_FILE='/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env' \\
PYTHONPATH="$NLTL_PROJECT/src:$NLTL_PROJECT/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime" \\
'/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python' -m nltlv2.hosted_pilot \\
  --project "$NLTL_PROJECT" \\
  --manifest 'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/interface_clarity/next_test_readiness/TRF035.shared_start.manifest.json' \\
  --run-id '20261125_V0115_TRF035_INTERFACE_CLARITY_DIAGNOSTIC_01' \\
  --allow-model-calls
'''
(N/'launch_command.txt').write_text(command)
notes={'I2-004':'Ready within approved synthetic scope: retained I2.1.2.2, ship-to-waterline-case owner traversal, both displacement quantities in KiloTON_Metric. Physical population/eligibility certification is outside scope. Broad related vocabulary is not additional approved obligations. Prior exposure; do not import previous diagnosis/solution.', 'I2-005':'Ready within approved boundary-record scope: retained I2.2.5, ship-to-hullBoundaryPoint link, angle quantity in DEG with declared numeric encoding. Hull-surface reconstruction and physical completeness of points are explicitly outside scope; represented boundary condition is not assumed true.', 'TRF-010':'Ready for designation-record validation: retained section 1.8 supplies six classes, ship-owned iceClass and ontology individuals. Approved scope excludes reconstructing propulsion/structure/navigation capability. This is not real-vessel class certification.', 'TRF-035':'Ready under approved option A: retained section 4.1.1 L definition, direct ship ownership of ruleLength and classificationSocietyRuleLength; metre/decimal quantities. The society reference is separately supplied and its authenticity assumed externally, not derived from classificationSociety text. No value relationship is pre-assumed by scope. Other hull-region vocabulary is context, not an extra obligation.'}
for row in rows:row['assessment_reason']=notes[row['requirement_id']]
write(N/'four_requirement_readiness.json',rows)
summary='''NEXT-TEST READINESS — offline source/schema/scope assessment only

Current patch identifier: V0115_INTERFACE_CLARITY_20261125_TESTED_303.
current_tested_snapshot.json records CURRENT hashes of all production source modules, prompts, configuration and retained readiness resources. It is distinct from the earlier v0.11.5 context-question and continuation freezes; those are preserved unchanged. Current source/prompt hashes match the 303-test clarity verification snapshot. No source/prompt/configuration implementation was edited in this task.

'''+ '\n\n'.join(rid+': '+notes[rid] for rid in notes)+'''

All four approved declarations loaded successfully through the existing admission mechanism; source-edition document hashes match retained sources. Current actual initial request token counts plus 16,000 output tokens fit the public model capacity. These checks establish bounded diagnostic readiness, not source-context completeness or future semantic approval. Secondary source gaps/unknown ownership remain explicit in four_requirement_readiness.json and must be reviewed/retrieved under existing bounds. Exact source/owner mappings, units and declared research limits determine readiness; generated performance was not used.

Recommendation: ONE fresh TRF-035 shared-start semantic-handoff diagnostic. Its explicitly approved recorded/reference data roles, two direct quantity operands and common units provide a focused way to exercise evidence-versus-code citations and feedback delivery while avoiding IMO-001's unresolved design-intent mapping. No issue or repair is guaranteed or forced; a valid early approval is a legitimate outcome. No previous candidate, repair solution, historical review or evaluation resource is a production input. All four alternatives are previously exposed, not held out; this is not a ranking by model performance.

Existing bounds unchanged: one initial generation shared byte-for-byte with Single-shot and NLTL; at most one technical plus one semantic revision; three distinct candidates including the shared initial; four primary reviews total, at most three per candidate; one shared response correction per primary review; two retrieval rounds; eleven total provider HTTP calls including generation/revisions/corrections; 600-second workflow window; 180-second request timeout; 16,000 output tokens including reasoning per request; maximum 176,000 reserved output tokens; start reserve 540 seconds. Early stopping, no regeneration/manual repairs/preferred-result rerun. Current latest-technical delivery and final handoff policies are unchanged; external evaluation only after dispatch closure.

IMO-001 remains BLOCKED for another diagnostic by unresolved design-intent representation. It is retained in the historical five-requirement set and planned-set inventory, not excluded from any old denominator or score. I2-042 remains deferred. Selecting one next diagnostic does not drop the other three ready requirements or alter the planned set.

TRF035.shared_start.manifest.json uses the NEW current_tested_snapshot.json with the existing hosted_pilot CLI. dispatch_ready denotes offline readiness; prepared_only/authorization explicitly record that this task authorizes no calls. The CLI's explicit --allow-model-calls and live opt-in are required for a future user launch. This command has NOT been run. No new driver/framework or production implementation was added.

Exact launch command (MAKES MODEL CALLS):
'''+command
(N/'REPORT.txt').write_text(summary)
# Verify no implementation, scope, tracker or historical artifact change from the completed clarity state.
for n,h in load(C/'tested_source_hashes.json').items():assert sha(R/n)==h
for n,h in load(C/'protected_before.json').items():assert sha(R/n)==h
write(N/'preservation_verification.json',dict(current_tested_source_matches=True,old_protected_files_unchanged=True,model_calls=0,evaluation_reruns=0,production_changes=0,old_freeze_locks_unchanged=True))
shutil.copyfile(__file__,N/'readiness_assessment.py');write(N/'artifact_manifest.json',{str(p.relative_to(N)):sha(p) for p in N.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(snapshot=lock['snapshot_id'],snapshot_sha256=sha(N/'current_tested_snapshot.json'),recommendation=recommended,rows=[dict(id=x['requirement_id'],ready=x['status'],tokens=x['capacity']['input_plus_output_lower_bound'],source_gaps=len(x['source_selection_gaps'])) for x in rows],report=str(N/'REPORT.txt'),model_calls=0),indent=2))
