import pathlib,json,hashlib,shutil,subprocess,os,sys
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');O=R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
m=load(O/'pilot_manifest.json');frozen=load(O/'frozen_resource_hashes.json');pre=R/'outputs/audits/20261124_FIVE_REQUIREMENT_SCOPE_READINESS';construction=load(pre/'evaluation_construction_review.json')
# Independently freeze evaluation data/bindings, outside all production requests.
evaluation_lock={}
for row in construction['rows']:
 for path in [row['file'],row['binding_file']]:evaluation_lock[path]=sha(R/path)
for path in ['evaluation/selections/regression_core.json','evaluation/independent.py','evaluation/specifications/intended_negative_cases.json',str((pre/'evaluation_construction_review.json').relative_to(R))]:evaluation_lock[path]=sha(R/path)
write(O/'evaluation_resources.lock.json',evaluation_lock)
preflight=r'''"""Offline pilot preflight only: never loads credentials or opens a provider transport."""
import pathlib,json,hashlib,socket,sys,importlib.metadata
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
manifest=load(HERE/'pilot_manifest.json')
for name,h in load(HERE/'frozen_resource_hashes.json').items():
 assert sha(ROOT/name)==h,'FROZEN_RESOURCE_CHANGED '+name
for name,h in load(HERE/'evaluation_resources.lock.json').items():
 assert sha(ROOT/name)==h,'EVALUATION_RESOURCE_CHANGED '+name
import nltlv2
assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.10.1'
assert pathlib.Path(nltlv2.__file__).is_relative_to(HERE/'runtime')
source={str(p.relative_to(ROOT/'src/nltlv2')):sha(p) for p in (ROOT/'src/nltlv2').rglob('*.py')}
installed={str(p.relative_to(HERE/'runtime/nltlv2')):sha(p) for p in (HERE/'runtime/nltlv2').rglob('*.py')}
assert source==installed
expected=load(HERE/'runtime_identity.json')['dependencies']
assert all(importlib.metadata.version(k)==v for k,v in expected.items())
from nltlv2.core import Project
from nltlv2.schema import Schema
from nltlv2.admission import load_admission
from nltlv2.requests import initial_request
from nltlv2.transport import provider_payload
project=Project(ROOT);schema=Schema(project);requests={}
for job in manifest['jobs']:
 assert not (ROOT/job['output']).exists(),'JOB_ALREADY_RESERVED_OR_RUN '+job['experiment_id']
 cfg=project.config(job['config']);admission=load_admission(project,cfg,schema,job['requirement_id']);assert admission['valid']
 ctx=schema.context(job['requirement_id']);ctx['admission']=admission['context'];ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}
 req=initial_request(project,ctx,settings);req.update(model=cfg['model'],max_output_tokens=cfg['generation_max_tokens'])
 assert req==load(ROOT/job['initial_request']),'ACTUAL_INITIAL_REQUEST_DRIFT'
 requests.setdefault(job['requirement_id'],[]).append(provider_payload(req))
assert all(v[0]==v[1] for v in requests.values())
assert len(manifest['jobs'])==10 and sum(j['max_provider_calls'] for j in manifest['jobs'])==55
assert not (ROOT/manifest['batch_output']).exists(),'BATCH_ALREADY_RESERVED_OR_RUN'
print(json.dumps(dict(status='READY_UNDISPATCHED',pipeline_version='0.10.1',approved_scopes=5,identical_actual_initial_pairs=5,max_provider_calls=55,model_calls=0,dispatch_authorized=False)))
'''
(O/'offline_preflight.py').write_text(preflight)
cmds=[]
PYTHON='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
for job in m['jobs']:
 cmd=f'"$PILOT_PYTHON" -B -m nltlv2.cli --project "$PILOT_PROJECT" run --config "{job["config"]}" --requirement "{job["requirement_id"]}" --experiment-id "{job["experiment_id"]}" --allow-model-calls > "$PILOT_BATCH/{job["experiment_id"]}.stdout.log" 2> "$PILOT_BATCH/{job["experiment_id"]}.stderr.log"'
 cmds.append(cmd)
# Runnable command text only; not a new executor or pipeline route, and never executed here.
text=f'''EXACT DISPATCH INSTRUCTIONS — PREPARED ONLY; DO NOT EXECUTE WITHOUT SEPARATE AUTHORIZATION

Manifest: {O/'pilot_manifest.json'}
Status: scopes/mapping approved, implementation frozen, model dispatch NOT authorized.
No experiment directories exist yet. The ten audit capture directories contain only first-packet software evidence; they are not model runs or generated candidates.

A. OFFLINE PREFLIGHT (safe to run now; makes zero calls)

export PILOT_PROJECT='{R}'
export PILOT_PYTHON='{PYTHON}'
export PILOT_PREPARATION='{O}'
export PYTHONPATH="$PILOT_PREPARATION/runtime"
export PYTHONDONTWRITEBYTECODE=1
"$PILOT_PYTHON" -B "$PILOT_PREPARATION/offline_preflight.py"

This checks frozen implementation/prompts/resources/configs/approved scopes, exact actual initial packets, installed/source identity/dependencies, immutable evaluation file hashes, and absence of all ten output IDs and the batch directory. A mismatch stops preparation. The shared environment's older distribution must not be used without this explicit frozen-runtime PYTHONPATH.

B. ONLY AFTER A NEW EXPLICIT DISPATCH AUTHORIZATION

The following block is dormant instruction text, not authorization. Do not execute it during preparation. Authorization must name this manifest/hash, established destination, model, five fresh pairs and 55-call ceiling. Record that future authorization separately; do not edit the frozen manifest.

set -eu
: "${{NLTL_PILOT_DISPATCH_AUTHORIZATION:?Separate explicit authorization reference required}}"
"$PILOT_PYTHON" -B "$PILOT_PREPARATION/offline_preflight.py"
export NLTL_ENV_FILE='/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env'
export NLTL_ALLOW_MODEL_CALLS=YES
export PILOT_BATCH="$PILOT_PROJECT/{m['batch_output']}"

Before LiveTransport construction, locally verify that AALTO_RESPONSES_BASE_URL in this external file exactly equals {m['destination']} and that the key exists; never print the key. Credential contents were not loaded in this preparation. If the destination differs, stop; do not dispatch elsewhere. The existing production transport loads only this external file.

"$PILOT_PYTHON" -B -c 'import os; from dotenv import dotenv_values; e=dotenv_values(os.environ["NLTL_ENV_FILE"]); assert e.get("AALTO_RESPONSES_BASE_URL", "").rstrip("/")=="https://aalto-openai-apigw.azure-api.net/v1/openai/responses", "DESTINATION_MISMATCH"; assert e.get("AALTO_API_KEY"), "MISSING_PROVIDER_KEY"; print("Verified approved destination and external credential presence; key not displayed")'

mkdir "$PILOT_BATCH"
cp "$PILOT_PREPARATION/pilot_manifest.json" "$PILOT_BATCH/pilot_manifest.frozen.json"

Run each literal command below ONCE, in order. All use current production CLI/Runner/LiveTransport routes and no seeded continuation driver. A previously reserved job ID fails before any generation. Do not restart interrupted jobs under a fresh ID or rerun for a preferred result. If a command fails, stop and preserve/reconcile artifacts and reserved calls; do not create a replacement job.

'''+ '\n\n'.join(cmds)+'''

C. PRESERVATION AND DISPATCH CLOSURE — BEFORE INDEPENDENT EVALUATION

Preserve each job directory in full, all CLI logs, exact actual requests/responses/usage, original diagnostics, evidence and code-span validation, candidate files/hashes, runtime probes, findings, reviewer failures, diffs/change assessments, histories and terminal transitions. Do not clean up rejected or final candidate files. Count every request attempt conservatively, including a request with no saved response after timeout/interrupt; ten per NLTL, one per Single-shot and55 total remain hard ceilings. Capture-only audit packets are not provider calls.

For EVERY candidate_*.ttl, create an external candidate inventory entry containing its byte hash/version/path, its history row and findings file, and the terminal run reason. Include the last rejected candidate. If infrastructure aborts after saving code but before a findings record, retain the code/raw response, mark findings unavailable with the exact operational failure, and do not invent findings or credit that output. Keep raw malformed output as well.

Select NLTL output only from its first accepted=true history row with run status ACCEPTED and intact resources/candidate hash. It must equal accepted_version. Otherwise selected output is null/NO_VERDICT. Do not select the final rejection, highest external score or a manually reviewed fallback. Single-shot retains its sole delivered candidate; malformed output remains NO_VERDICT. Acceptance code and prompts stay identical across all attempts, including the final attempt. There is no human-review arm.

Save a selected-output manifest and an exhaustive all-candidate diagnostic inventory BEFORE reading external outcomes. Save dispatch_closed.json only when all ten jobs are terminal or explicitly closed after operational interruption, no provider process is outstanding and no additional job will be sent. Bind the receipt to the selected-manifest SHA256, each selected and diagnostic candidate SHA256, all job statuses and the conservative total call count. Even if an internal history row had accepted=true, a final integrity-failure run is not creditable.

D. INDEPENDENT EVALUATION — AFTER CLOSURE ONLY

Use the manifest's 30 unchanged original cases and16 existing counterparts, per-requirement approved scope files and46 reviewed hash-bound input bindings in evaluation_resources.lock.json. I2-042 and the external post-repair above-maximum diagnostic remain outside this inventory and denominators. Do not change labels, scopes, source editions or counterpart files.

Run a separate offline evaluation process after checking closure/manifest/candidate/resource hashes. Existing evaluation/independent.py validate_admitted_graph accepts the exact declaration/binding per requirement; validate_pair_graph and strict_status preserve uncertainty. Its generic evaluate() assumes one research_scope and37 cases and is NOT a compatible five-scope driver: do not call it as though it implements this manifest, and do not reuse an incompatible historical continuation/evaluation driver. Dispatch instructions require no evaluation import in production.

Report selected outputs separately from REJECTED_CANDIDATE_DIAGNOSTICS. Diagnostics may include every saved candidate but never alter selection. Missing accepted NLTL output remains NO_VERDICT; missing or unresolved violation attribution remains unresolved, not automatic strict credit. Preserve raw/adjudicated evidence separately, without adding a human acceptance arm or changing the production criteria. Record calls, tokens, actual request sizes and runtime from actual artifacts. No fresh performance or superiority claim is supported merely by this development pilot.

This file contains instructions only. No model call, candidate generation, live transport or independent conformance evaluation was performed during finalization.
'''
(O/'DISPATCH_INSTRUCTIONS.txt').write_text(text)
# External, score-independent inventory/selection contract; this does not alter Runner acceptance.
write(O/'candidate_preservation_and_selection_contract.json',dict(every_candidate_preserved=True,inventory_glob='candidate_*.ttl',include_last_rejected=True,required_fields=['version','path','sha256','candidate_status','findings_path_or_explicit_unavailable_reason','run_terminal_reason','operational_failure_reference'],selected_nltl='First accepted=true history row if run status ACCEPTED and all integrity checks remain valid; otherwise NO_VERDICT',external_scores_used_for_selection=False,final_attempt_leniency=False,fallback_acceptance=False,human_review_arm=False,diagnostics_label='REJECTED_CANDIDATE_DIAGNOSTICS',dispatch_closure_required_before_evaluation=True))
sizes=load(O/'actual_initial_request_sizes.json')
rows=[]
for size in sizes:
 rid=size['requirement_id'];inv=next(x for x in load(pre/'pilot_plan.proposed.json')['evaluation_inventory'] if x['requirement_id']==rid);rows.append(dict(requirement_id=rid,readiness='READY_AWAITING_DISPATCH_AUTHORIZATION',scope_approved=True,mapping_choice='A_APPROVED' if rid=='TRF-035' else None,original_cases=inv['original_cases'],counterparts=inv['counterparts'],actual_initial_bytes_per_arm=size['rendered_bytes'],paired_initial_payloads_identical=True,maximum_provider_calls_per_pair=11))
write(O/'final_readiness.json',dict(status='READY_AWAITING_SEPARATE_DISPATCH_AUTHORIZATION',rows=rows,original_cases=30,counterparts=16,max_provider_calls=55,provider_calls_made=0,model_calls_made=0,generated_candidates=0,remaining_scope_or_mapping_decisions=[],remaining_authorization='Explicit dispatch authorization only',deferred=['I2-042']))
report='''FINAL FIVE-REQUIREMENT PAIRED PILOT — APPROVED SCOPES, UNDISPATCHED

User approval is preserved verbatim in approval_verbatim.txt and as actual approval provenance in four NEW .approved.json declarations. Original proposals and I2-004 approval are unchanged. Definitions/experimental editions are unchanged, so the46 evaluation input binding definition hashes still match. TRF-035 option A is recorded as approved; recorded L and separately supplied reference remain separate roles. No equality, formula, expected verdict or alias metadata was installed. Research assumptions do not certify real-vessel eligibility, governing legal editions or society-rule derivation.

'''+ '\n'.join(f"{x['requirement_id']}: READY; {x['original_cases']} original + {x['counterparts']} counterparts; actual initial {x['actual_initial_bytes_per_arm']:,} bytes per arm, identical NLTL/Single-shot; <=11 calls/pair." for x in rows)+'''

All five actual initial requests were captured through the unchanged production Runner.dispatch boundary before any provider response/transport. System/user/settings and full provider payloads match within each pair. Saved captures are clearly labelled software evidence: zero model calls/responses/generated candidates. Byte totals are system+user UTF-8, not token estimates; provider JSON sizing is separately recorded. Source/schema evidence and actual approved scope context are included, with no seeds, prior issues, historical diagnoses, repair solutions, case labels or counterpart identities.

Frozen runtime: copied installed v0.10.1 metadata/package matches all23 current source Python files byte-for-byte; actual imported module/distribution both0.10.1; locked dependency versions verified. Shared environment remains untouched. Code, prompts, canonical schema/representation, source catalog/text/PDFs, scope files, configs and initial packets have exact frozen hashes. Evaluation resources have a separate inaccessible-to-production lock.

Five actual approved production input-scope guards passed; all46 unchanged prior complete RDFS population proofs and construction hashes remain valid under the identical approved definition hashes. No conformance evaluation rerun occurred. Source-only GenerationProject denies evaluation fixtures/bindings, historical candidate and audit resources. Production capture path logs include source/schema/admission/prompt resources only; no evaluation loaded by generation. This verifies the existing application capability boundary, not an OS sandbox claim.

Single-shot exactly1 call. NLTL one fresh generation plus<=1 repair, <=2 candidates, <=4 primary reviews total and<=3 per candidate, one SHARED response correction per review, <=2 retrieval rounds, <=10 calls including repair/corrections. Five pairs<=55 calls. Fresh run-once output IDs are reserved in the manifest but no experiment directories were created. Current early acceptance/terminal conditions stop each workflow. No regeneration, manual candidate edits, preferred-result reruns, lenient last attempt, fallback acceptance or human-review arm.

Static review confirms the single unchanged acceptance expression has no attempt/budget-dependent threshold. The production Runner saves candidates before checking, findings/history/status and changes for normal terminal paths, and selects the first accepted history entry. The final exhausted candidate remains rejected, with ATTEMPT_LIMIT_EXHAUSTED as run reason. Operational failures may interrupt findings creation; the external inventory must retain such saved candidates and explicitly record findings unavailable plus the exact operational reason. No candidates may silently disappear. This preservation/selection contract changes no production code or acceptance criteria.

Only first internally accepted NLTL output with intact run integrity is selected. Otherwise NO_VERDICT. All rejected candidates, including the last, remain separate labelled diagnostics; external scores never choose an output. Selected/all-candidate manifests and hashes must be sealed with a dispatch-closure receipt BEFORE independent evaluation. Evaluation uses unchanged30 development cases and16 counterparts with approved per-requirement scopes/bindings. Generic evaluation.evaluate assumes one scope/37 cases and must not be mistaken for this five-scope plan; use its existing independent scope/validation helpers according to the manifest in a separate offline process. Unknown attribution remains unresolved, not strict success. No original score or case was changed.

Exact commands and closure/preservation/evaluation instructions: DISPATCH_INSTRUCTIONS.txt. Safe offline preflight: offline_preflight.py with the frozen runtime PYTHONPATH. Live commands are dormant instructions and require separate explicit authorization. Destination/model are the established Aalto Responses endpoint and gpt-5.6-luna-2026-07-09. Current finalization did not load credentials, construct LiveTransport, dispatch or evaluate candidates. I2-042 remains deferred. v0.10.1 implementation and the successful repair remain unchanged.
'''
(O/'final_readiness_report.txt').write_text(report)
# Include new verification/instruction artifacts in the freeze without touching existing protected files.
for f in [O/'offline_preflight.py',O/'evaluation_resources.lock.json',O/'runtime_identity.json',O/'candidate_preservation_and_selection_contract.json',O/'DISPATCH_INSTRUCTIONS.txt']:
 frozen[str(f.relative_to(R))]=sha(f)
write(O/'frozen_resource_hashes.json',frozen)
env=dict(os.environ,PYTHONPATH=str(O/'runtime'),PYTHONDONTWRITEBYTECODE='1');check=subprocess.run([PYTHON,'-B',str(O/'offline_preflight.py')],env=env,capture_output=True,text=True);write(O/'offline_preflight_result.json',dict(returncode=check.returncode,stdout=check.stdout,stderr=check.stderr));assert check.returncode==0,check.stderr
before=load(O/'protected_before.json');changed=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h];assert not changed,changed
pres=load(O/'preservation_verification.json');pres.update(final_check='PASS_AFTER_FINAL_MANIFEST_AND_INSTRUCTIONS',modified_existing=[]);write(O/'preservation_verification.json',pres)
shutil.copy2('/tmp/nltl_write_final_dispatch_instructions.py',O/'offline_instruction_driver.py')
write(O/'artifact_manifest.json',{str(f.relative_to(O)):sha(f) for f in O.rglob('*') if f.is_file() and f.name!='artifact_manifest.json'})
print(json.dumps(dict(report=str(O/'final_readiness_report.txt'),instructions=str(O/'DISPATCH_INSTRUCTIONS.txt'),manifest_sha256=sha(O/'pilot_manifest.json'),offline_preflight=load(O/'offline_preflight_result.json'),previous_files_unchanged=len(before)),indent=2))
