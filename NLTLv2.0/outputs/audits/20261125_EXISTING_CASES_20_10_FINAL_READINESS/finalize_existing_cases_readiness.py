from pathlib import Path
import json,hashlib,sys,difflib,shutil,collections
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');M=R.parent/'MVP';A=R/'outputs/audits/20261125_EXISTING_CASES_20_10_FINAL_READINESS';load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();save=lambda n,x:(A/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
d=load(A/'existing_cases.discovery.json');rows=load(A/'verified_requirement_readiness.json');cases=load(A/'verified_existing_cases.evaluation_only.json')['requirements'];previous=load(R/'outputs/audits/20261125_IDENTIFIER_ROUTING_AND_20_10_READINESS/source_schema_selection.freeze.json')['GPT_OSS_20'];ready=d['ready_with_current_scopes_and_evaluator'];eligible=d['eligible_with_verified_case_subsets'];assert len(ready)==4 and len(eligible)==8
# Confirm retained ready-case bytes and counterparts are identical to their existing reviewed originals.
byid={c['case_id']:c for sub in cases.values() for c in sub};core=load(R/'evaluation/selections/regression_core.json')['cases'];copied=[]
for c in core:
 if c['requirement_id'] not in ready:continue
 old=byid[c['case_id']];assert sha(R/c['fixture'])==old['fixture_sha256']
 if c.get('counterfactual'):assert sha(R/c['counterfactual'])==old['counterpart_sha256']
 copied.append(dict(case_id=c['case_id'],requirement_id=c['requirement_id'],fixture=c['fixture'],fixture_sha256=sha(R/c['fixture']),counterpart=c.get('counterfactual'),counterpart_sha256=sha(R/c['counterfactual']) if c.get('counterfactual') else None))
save('ready_original_case_identity.json',copied)
# Record all previous proposed slots and the reason replacements cannot fill the target.
manifest_counts=collections.Counter();base=M/'SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13'
for f in (base/'manifests').glob('*.jsonl'):
 for line in f.read_text().splitlines():
  if line.strip():manifest_counts[json.loads(line)['requirement_id']]+=1
replacements=[]
for rid in previous:
 reasons=[]
 if rid=='IMO-001':reasons=['UNRESOLVED_DESIGN_INTENT_REPRESENTATION']
 elif rid not in ready:reasons=['NO_EXISTING_INDEPENDENT_SOURCE_SCHEMA_VERIFIED_POSITIVE_AND_NEGATIVE_COUNTERPART_SUBSET_IN_REVIEWED_EVIDENCE','APPROVED_SCOPE_MISSING','CURRENT_EVALUATOR_BINDINGS_NOT_READY']
 replacements.append(dict(previous_requirement=rid,original_manifest_case_rows=manifest_counts[rid],decision='RETAIN_READY' if rid in ready else 'EXCLUDE_FROM_INFERENCE_PENDING_READY_REPLACEMENT',reasons=reasons,replacement=None if reasons else rid,replacement_status='No unused launch-ready replacement available' if reasons else 'Retained unchanged'))
conditional=[r for r in rows if r['requirement_id'] in eligible and r['requirement_id'] not in ready]
freeze=dict(label='READINESS_SELECTION_FROZEN_NO_EXPERIMENT_INFERENCE',requested_requirements=20,requested_GPT55_overlap=10,fully_ready_order=['TRF-010','I2-005','TRF-035','I2-004'],fully_ready_count=4,ready_case_count=len(copied),ready_counterparts=sum(bool(c.get('counterpart')) for c in copied),complexity=dict(easy=['TRF-010'],intermediate=['I2-005','TRF-035'],difficult=['I2-004']),verified_case_subset_candidates=eligible,conditional_candidates=conditional,remaining_unique_ready_slots_short=16,ten_requirement_overlap_possible=False,final_twenty_selection=None,GPT55_ten_overlap=None,dispatch_ready=False,no_reduced_diagnostic_prepared=True,selection_basis='Existing source/schema verified cases and source/table/branch/RDF-path complexity only; no workflow performance consulted.',case_scope='Reusable verified subsets are finite development controls, not full branch certification. Partial table/exception coverage remains explicit.',accounting=dict(IMO_001='Unresolved representation retained in historical/planned accounting; not silently dropped',I2_042='Previously deferred; not reintroduced'),pipeline_snapshot=load(A/'pipeline.freeze.json')['snapshot_id'],models=dict(GPT_OSS='gpt-oss-120b',GPT55='gpt-5.5-2026-04-24'),shared_start_policy='Each model independently generates once per requirement; Single-shot preserves that exact output and NLTL starts from the same bytes. Same frozen cases/counterparts for both workflows and overlap models; evaluation after closure only.',model_context_policy='Fixtures, labels, counterparts, expected answers and independent source oracles remain outside all production requests. B coverage prompt is not adopted.')
save('selection.readiness.freeze.json',freeze);save('replacements_and_reasons.json',replacements)
conn=load(A/'connection_probe.result.json');assert conn['status']=='CONNECTION_VERIFIED' and conn['provider_calls']==1
# Record the tested current state distinctly. Production prompt hashes remain the pre-comparison baseline.
lock=load(A/'pipeline.freeze.json');sys.path.insert(0,str(R/'src'));from nltlv2.hosted_pilot import verify;verify(R,lock)
protected=load(A/'protected_before.json');changed=[n for n,h in protected.items() if sha(R/n)!=h];assert not changed,changed[:10]
newtests=load(A/'verification.json');assert newtests['success'] and newtests['tests']==313
diff=[]
for n in ['src/nltlv2/transport.py','src/nltlv2/hosted_pilot.py']:
 diff+=list(difflib.unified_diff((A/'before'/n).read_text().splitlines(True),(R/n).read_text().splitlines(True),fromfile='before/'+n,tofile='current/'+n))
(A/'minimal_transport.diff').write_text(''.join(diff));save('preservation_verification.json',dict(protected_files=len(protected),protected_changes=changed,ready_original_fixture_counterpart_hashes_match=True,MVP_and_locked_dataset_written=False,production_prompts_unchanged=True,coverage_prompt_not_adopted=True,metadata_or_connection_experimental_material_sent=False,connection_probe_calls=1,experiment_calls=0,evaluation_reruns=0))
# Freeze evaluation evidence independently from the model-facing source snapshot.
save('evaluation_inputs.freeze.json',dict(label='EVALUATION_ONLY_EXCLUDED_FROM_MODEL_REQUESTS',files={c['fixture']:c['fixture_sha256'] for rid in eligible for c in cases[rid]}|{c['counterpart']:c['counterpart_sha256'] for rid in eligible for c in cases[rid] if c.get('counterpart')},source_review_hashes={str(M/'evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z/reviewed_cases.json'):sha(M/'evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z/reviewed_cases.json')}))
summary='''Existing validation cases and GPT-5.5 connection — final readiness

Correction to earlier readiness claim
I checked NLTLv2.0 first, then MVP, then the locked R13 dataset. fixture:null/bundled:false in the new-folder inventory does NOT mean original cases do not exist. The earlier claim of missing cases was too broad. NLTLv2.0 indexes 1,302 reviewed entries and bundles 37 cases across six requirements. MVP retains 2,251 distinct original manifest cases across 268 requirements. Verified 36 fixture locks / 2,513 locked-file entries with ZERO mismatches. The current ontology, term registry and quantity JSON-LD hashes match the locked R13 assets.

What is actually reusable
The retained independent source/schema review documents verified positive cases and negative/intended-only-counterpart pairs for TEN requirements: I2-004, I2-005, I2-042, I2-048, IMO-001, TRF-001, TRF-010, TRF-035, TRF-036, TRF-050. All referenced verified fixture/counterpart/source hashes checked unchanged; no failed checks. The existence of many other frozen authoring cases is not the same as current source/schema/gold/counterpart readiness; no old model scores were used to promote cases.
Exclude previously deferred I2-042 and unresolved IMO-001 from inference eligibility, preserving both in accounting. EIGHT candidates have reusable verified subsets. Four of these are only conditional candidates because their research scopes are unapproved and current evaluation bindings are not integrated:
- I2-048: 137 verified positives / 14 negative-counterpart pairs; difficult table logic. Partial table coverage and pending duplicate-material repair remain explicit; do not include the unverified original cases or claim full table/footnote coverage.
- TRF-001: 3 positives / 2 pairs; intermediate application branches. Universal-provision isolation is not fully covered.
- TRF-036: 4 positives / 5 pairs; difficult table logic. Do not include the separately ambiguous class-II case or claim missing selector branches tested.
- TRF-050: 2 positives / 5 pairs; difficult exception logic. Some crossing/weld/selector branches remain unisolated.
Their original verified CASES exist and remain unchanged. They are not launch-ready requirements under current approved scopes. No restrictive new scope or expected answer was invented to declare them ready.

Exact launch-ready count: FOUR, not twenty
TRF-010 — easy designation-record constraints: 8 original cases, 2 counterparts.
I2-005 — intermediate linked point/angle representation: 5 original cases, 4 counterparts.
TRF-035 — intermediate two-quantity data roles: 6 original cases, 4 counterparts.
I2-004 — difficult nested waterline cases: 6 original cases, 3 counterparts.
TOTAL 25 original cases / 13 counterparts. Current copies exactly match reviewed originals. These four already have approved scopes, source/schema readiness and the existing independent evaluation route. Complexity derives from source/branch/path structure, never past generated performance. Known exposure and finite coverage remain explicit.

Replacements and final selection
replacements_and_reasons.json records all twenty former proposed slots: four retained ready entries, IMO-001 excluded pending its genuine mapping decision, and fifteen entries with original authoring cases but without existing independently verified reusable subsets/current approved scopes/evaluation bindings. No unused fully ready alternative can fill those sixteen slots. The four new verified-subset candidates are recorded with their remaining scope/evaluation blockers; they are not relabelled ready replacements. Selection was NOT resampled by generated score.
selection.readiness.freeze.json freezes this result: ready_count=4, final_twenty_selection=null, GPT55_ten_overlap=null, dispatch_ready=false. It does not silently substitute a four-requirement diagnostic or a smaller overlap. A ten-of-twenty experiment cannot honestly be launched from the current evidence. No more TRF-035 prompt experiments are prepared.

All remaining blockers
1. Sixteen more unique launch-ready requirements are needed to reach twenty. Original files alone do not resolve source/gold/representation/counterpart review limits. Four additional candidates have verified finite subsets but lack approved scopes and current evaluation integration; further candidates need source/schema/counterpart verification or resolution of actual blockers.
2. Explicit approval of additional research scopes is missing; the prior five approvals cannot be extended automatically. Required population/edition assumptions and representation responsibilities must be declared without importing solution profiles or witness answers. Current labels and generated performance cannot supply admission.
3. Input-construction/admission bindings and the current independent evaluator route must be verified for new requirements. Historical source-authored oracles remain evaluation-only evidence and cannot be copied into generation/review/repair. No fixtures or counterparts were edited or newly fabricated here.
4. IMO-001's design-intent mapping remains unresolved; I2-042 remains deferred. They are not counted as ready replacements or erased from historical/planned accounting.

GPT-5.5 connection checks FINISHED
Actual endpoint: https://ai-api-v2.aalto.fi/v1/responses.
Requested and RETURNED model: gpt-5.5-2026-04-24, identity MATCH, status completed, final CONNECTION_OK. Exactly ONE benign transport-only request, 25 input + 18 output = 43 tokens, 1.707s provider latency. No requirement, candidate, source/schema/scope or evaluation material was sent. No retry/fallback and no experiment inference. Full actual request/response/usage artifacts: gpt55_connection_probe/. Backend identity beyond returned provider metadata, provider-specific large-context limits and exact framing/tokenizer remain unexposed; the successful tiny probe is not a large-context or accuracy test.
The existing hosted transport now accepts an explicitly configured member of the two verified model IDs. GPT-OSS remains the default; request/returned-model checks use the configured expected model, missing returned identity stays UNKNOWN and mismatches remain terminal. hosted_pilot passes the manifest's model. Same bounded transport, final-output extraction, no silent fallback/retries/truncation; no new framework. Two mocked identity controls added. All 313 software tests pass.
New source snapshot: V0115_HOSTED_MODEL_IDENTITY_20261125_TESTED_313, in pipeline.freeze.json. It retains the narrow identifier-routing fix and baseline prompts, without B's coverage instruction. Evaluation fixture hashes are frozen SEPARATELY in evaluation_inputs.freeze.json; they are not part of model context.

Bounds and command
The requested 20 + 10 model/requirement pairs retain the existing maximum 11 calls, three distinct candidates, one shared generation, at most one technical and one semantic repair, four primary reviews, one correction/review, two retrieval rounds and 600 seconds per pair; 16,000 output tokens/request. Conditional total ceilings: 330 calls, 5.28 million reserved output tokens, 5 hours serial per-pair maximum. These are not expected runtime or spend forecasts; observed latency from easy/single examples is not representative. Actual input/provider token capacity must be checked per rendered packet with uncertainty disclosed, no arbitrary byte ceiling or truncation.
NO 20/10 LAUNCH COMMAND is supplied because fewer than twenty are genuinely ready and no exact ten overlap can be frozen. The connection blocker is resolved, but the data/scope/evaluation blockers are not. No model experiment or reduced substitute was dispatched. Once those blockers are resolved, the existing shared-start hosted runner can use separate model manifests; no new orchestration framework is needed.

Preservation
MVP and locked originals read-only, historical candidates/decisions/scores and retention ledger unchanged. Production prompts, source/schema, existing fixtures and approved scope declarations unchanged. No evaluation rerun. Exactly one transport connection probe is separately labelled; zero experimental calls.

Artifacts
existing_cases.discovery.json — search order and corpus counts.
MVP_fixture_lock_verification.json — original lock evidence.
verified_existing_cases.evaluation_only.json — exact reusable case/counterpart paths/hashes, NEVER model input.
verified_requirement_readiness.json — ten requirements with counts, partial-coverage limits and blockers.
selection.readiness.freeze.json / replacements_and_reasons.json — exact final readiness and replacement decisions.
connection_probe.result.json / gpt55_connection_probe/ — actual endpoint/model protocol evidence.
pipeline.freeze.json / verification.json / offline_tests.log — frozen tested transport and pipeline.
evaluation_inputs.freeze.json — separate evaluation-only freeze.
minimal_transport.diff / preservation_verification.json — small integration change and unchanged historical inputs.
'''
(A/'REPORT.txt').write_text(summary)
for n in ['prepare_dual_model_transport.py','verify_dual_transport.py','inspect_existing_validation_cases.py','gpt55_connection_probe.py','finalize_existing_cases_readiness.py']:shutil.copyfile('/tmp/'+n,A/n)
save('artifact_manifest.json',{str(p.relative_to(A)):sha(p) for p in A.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(report=str(A/'REPORT.txt'),ready_count=4,verified_subset_candidates=8,original_cases_discovered=2251,ready_cases=25,ready_counterparts=13,connection_verified=True,connection_calls=1,experiment_calls=0,launch_ready=False),indent=2))
