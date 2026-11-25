from pathlib import Path
import sys,json,hashlib,collections,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0113_IMO001_DIAGNOSTIC_PREFLIGHT';B=R/'outputs/experiments/20261125_V0113_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';S=R/'results/20261125_V0113_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';S.mkdir(exist_ok=False);sys.path.insert(0,str(R/'src'))
from nltlv2.hosted_pilot import verify
from nltlv2.core import Candidate,write
from nltlv2.evidence import extract_location
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
closed=load(B/'dispatch_closed.json');assert closed['dispatch_closed'] and closed['outstanding_provider_processes']==0 and closed['physical_calls']==4 and not closed['errors'];assert sha(B/'selected_outputs.json')==closed['selection_manifest_sha256'];verify(R,load(B/'freeze_lock.json'))
d=B/'IMO-001/NLTL';run=load(d/'run.json');pair=load(B/'IMO-001/pair.json');assert pair['shared_start_equal'] and pair['shared_raw_equal'] and pair['initial_request_equal'];assert run['repair_calls']==0 and run['repair_counts']=={'technical':0,'semantic':0};assert not run['operational_failure']
evaldone=load(B/'evaluation/evaluation_complete.json');assert evaldone['dispatch_closed_sha256']==sha(B/'dispatch_closed.json');assert all(sha(R/name)==h for name,h in closed['all_candidate_sha256'].items())
requests=[];trace=[]
for p in sorted((B/'provider').glob('call_*_request.json')):
 n=int(p.stem.split('_')[1]);req=load(p);payload=req['payload'];wire=json.loads(payload['input'][1]['content'][0]['text']);response=load(B/'provider'/f'call_{n:03d}_response.json');assert json.loads((B/'provider'/f'call_{n:03d}_request.body').read_text())==payload
 requests.append(dict(call=n,route=req['route'],request=str(p),exact_request_body=str(B/'provider'/f'call_{n:03d}_request.body'),request_bytes=(B/'provider'/f'call_{n:03d}_request.body').stat().st_size,request_sha256=sha(B/'provider'/f'call_{n:03d}_request.body'),response=str(B/'provider'/f'call_{n:03d}_response.json'),raw_response=str(B/'provider'/f'call_{n:03d}_response.body'),status=response['status'],returned_model=response.get('returned_model'),identity_status=response.get('identity_status'),usage=response['usage'],client_seconds=response['elapsed_seconds'],token_budget=response.get('token_budget')))
 if not req['route'].startswith('review'):continue
 local=n-1;failure=d/f'reviewer_format_failure_{local:03d}.json';errors=load(failure)['validation_errors'] if failure.exists() else [];obj=json.loads(response['text']);catalog={e['evidence_id']:e for e in wire['evidence_catalog']['entries']};cross=[]
 def walk(x,path='$'):
  if isinstance(x,dict):
   for key,quote in [('source_evidence_id','source_excerpt'),('evidence_id','evidence_excerpt')]:
    if x.get(key) is not None:cross.append(dict(path=path,field=key,asserted_id=x[key],asserted_excerpt=x.get(quote),supplied_entry=catalog.get(x[key])))
   if x.get('candidate_location'):
    c=Candidate(wire['candidate_version'],wire['full_candidate'],'');cross.append(dict(path=path,code_location=x['candidate_location'],exact_code=extract_location(x['candidate_location'],c)))
   for k,v in x.items():walk(v,path+'.'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):walk(v,path+'['+str(i)+']')
 walk(obj)
 trace.append(dict(call=n,route=req['route'],interface_and_proposal_valid=not errors,source_response=response['text'],validation_errors=errors,evidence_and_locations=cross,prior_issues=wire['prior_issues'],feedback=wire.get('format_feedback'),remaining_context=obj.get('unchecked'),request_binding={k:wire[k] for k in ['candidate_version','candidate_sha256','review_request_id']},interpretation_is_not_proven_by_valid_citations=True))
assert trace[0]['interface_and_proposal_valid'];assert len(trace[1]['validation_errors'])==11 and len(trace[2]['validation_errors'])==12
assert trace[2]['feedback']['validation_errors']==trace[1]['validation_errors'];assert trace[2]['feedback']['rejected_response']==trace[1]['source_response'];assert trace[1]['request_binding']==trace[2]['request_binding'];assert trace[1]['prior_issues']==trace[2]['prior_issues'];assert trace[0]['prior_issues']==[]
retrieval=load(d/'retrieval_ledger.json');assert len(retrieval)==1;ev=retrieval[0];schema_entries=[e for e in ev['entries'] if e['kind']=='schema'];assert len(schema_entries)==1;newterms=schema_entries[0]['term_iris'];newfacts=schema_entries[0]['ontology_triples']
# Existing source context, not a new evaluation or new production input.
first_wire=json.loads(load(B/'provider/call_002_request.json')['payload']['input'][1]['content'][0]['text']);source_entries=first_wire['evidence_catalog']['entries'];supplied_before=[e for e in source_entries if e['kind']=='RDF_FACT' and 'polarShipCategoryA>' in e['text']];scope=next(e for e in source_entries if e['kind']=='CALLER_DECLARATION')
summary=dict(label='FRESH_PREVIOUSLY_EXPOSED_SHARED_START_DEVELOPMENT_DIAGNOSTIC_NOT_COMPARATIVE_PERFORMANCE',run_id=B.name,source_version='0.11.3',design='FRESH_NOT_SEEDED',candidate_sha256=pair['nltl']['history'][0]['sha256'],shared_start_equal=True,shared_raw_equal=True,initial_request_equal=True,physical_calls=4,limits=dict(technical_repairs=1,semantic_repairs=1,candidates=3,physical_calls=11,primary_reviews=4,shared_corrections_per_review=1,retrieval_rounds=2),used=dict(generations=1,technical_repairs=0,semantic_repairs=0,candidates=1,primary_reviews=2,corrections=1,retrieval_rounds=1),terminal=run['status'],delivery=run['delivery'],approval=False,semantic_repair_exercised=False,context_pending=True,context_pending_basis='First current-run validated review marked mapping uncertainty material; no later validated reconciliation or evidence assessment resolves it. Do not infer resolution from the empty final delivery findings list.',first_unresolved_bottleneck='Reviewer interpretation conflated legal obligation with RDF vocabulary representation and demanded that the regulation prescribe the RDF individual. Supplied mapping facts already identify Category A. Its material unchecked claim routed to retrieval, not repair; post-retrieval review/correction failed validation.',retrieval=dict(novel=True,new_schema_terms=len(newterms),new_explicit_triples=len(newfacts),new_source_characters=0,terms=newterms,assessment='Some related ice concepts, many manual/eligibility/document terms. No new clause or necessary individual-name mapping; existing controlled Category A individual/type/label was already supplied. No validated resolution of the reported gap.'),validated_review_does_not_prove_issue_correct=True,technical_check=load(d/'technical_01.json'),usage={k:sum(q['usage'][k] for q in requests) for k in ['input_tokens','output_tokens','total_tokens']},client_phase_seconds={route:sum(q['client_seconds'] for q in requests if q['route']==route) for route in ['generation','review','review_format_retry','targeted_repair','syntax_repair']},technical_check_seconds=load(d/'technical_01.json')['check_seconds'],workflow_seconds=closed['elapsed_seconds'],evaluation_seconds=evaldone['elapsed_seconds'],provider_internal_timings='UNAVAILABLE',independent_results=evaldone['summary'],repairs_and_diffs='NOT_EXERCISED; no code revision or repair packet dispatched',no_further_model_calls=True)
write(A/'actual_request_index.json',requests);write(A/'actual_feedback_trace.json',trace);write(A/'context_relevance_assessment.json',dict(initial_category_mapping_facts=supplied_before,approved_scope=scope,retrieval_event=ev,assessment=summary['retrieval'],model_claim_is_not_established_missing_context=True));write(S/'summary.json',summary)
# Report every error separately, with exact actual evidence and code ranges in trace.
errorlines=[]
for t in trace:
 errorlines.append(f"Provider call {t['call']} / {t['route']}: {len(t['validation_errors'])} validation failures")
 for e in t['validation_errors']:errorlines.append(f"  {e['code']} at {e['path']}: expected {e['expected']}; observed {json.dumps(e.get('observed'),ensure_ascii=False)}")
(A/'ALL_VALIDATION_FAILURES.txt').write_text('\n'.join(errorlines)+'\n')
report=f'''v0.11.3 IMO-001 hosted GPT-OSS development diagnostic — CLOSED

Fresh, not seeded. One initial generation was preserved byte-for-byte as Single-shot and supplied unchanged to NLTL, with empty prior issues. Candidate SHA256: {summary['candidate_sha256']}. Existing approved source/schema/scope and prepared settings were verified; 261 offline tests passed. Installed import used explicit frozen v0.11.3 source, not the older distribution metadata. No failed historical reviews, known repair solution or evaluation inputs entered requests. Frozen implementation/prompts remained unchanged.

Outcome and first unresolved bottleneck

No technical or semantic repair occurred. The FIRST review did pass citation, code-location and proposal validation, but its substantive claim was that the regulation must explicitly prescribe the RDF individual polarShipCategoryA. It labelled this a technical error and marked the mapping gap material. The source obligation and ontology representation are different authorities: the supplied initial evidence already contained the Category A controlled individual, its type and prefLabel (E14/E25/E192), and the approved scope explicitly did not assume every record was Category A. The valid citation establishes a supplied fact, not this interpretation. This is not demonstrated absence of a necessary source/schema mapping.

The material unchecked statement correctly prevented immediate repair/acceptance and triggered the existing bounded retrieval route. It added 24 schema terms and 291 explicit triples, zero source characters: some related medium/thin first-year-ice concepts, many manual, eligibility and document terms. It supplied no new legal clause or missing individual-name mapping and did not resolve the model's demand for a regulatory RDF identifier. Novel evidence was not necessarily relevant resolution.

After retrieval, the reviewer changed to SOURCE_BACKED_LOGIC_ERROR and suggested relaxing/removing hasValue. That response failed 11 validations; the one allowed correction failed 12. Terminal: REVIEWER_FORMAT_FAILURE; delivery UNVERIFIED / HUMAN_REVIEW_REQUIRED. Both repair slots were UNUSED. Remaining primary-review/call capacity does not authorize bypassing this terminal outcome. No repair packet or undispatched feedback is described as delivered.

Exact call path and limits

Call 1 generation; call 2 review (valid, material-context pending); local schema retrieval; call 3 review (invalid); call 4 shared correction (invalid); stop. One candidate, two primary reviews, one correction, one retrieval round, zero repairs. Ceilings: three candidates, one technical plus one semantic repair, four primary reviews, one shared correction per review, two retrieval rounds, eleven physical calls. No regeneration/manual edits/rerun/additional requirements/metadata calls.

Every validation failure is listed in {A}/ALL_VALIDATION_FAILURES.txt; {A}/actual_feedback_trace.json preserves all raw final responses, exact fields, supplied evidence, server-extracted code, validation errors and correction feedback. For call 3: two INVALID_SOURCE_QUOTATION errors (issue/reconciliation), one UNSUPPORTED_SCHEMA_EVIDENCE, seven UNKNOWN_REVIEW_FIELD errors in reconciliation, and one UNGROUNDED_ISSUE_RECONCILIATION (state UNRESOLVED is not a permitted reconciliation state; the ID itself is known). For call 4: the two quotation and seven unknown-field errors persist, schema-evidence mismatch occurs for issue AND reconciliation, and UNRESOLVED_DECISION_NEEDS_CONTEXT_ISSUE is added (decision UNRESOLVED but issue remains SOURCE_BACKED_LOGIC_ERROR, unchecked/requests empty). Total 23 reported errors across the two failed responses.

The source assertion normalizes the original “at least\\nmedium first-year ice” into “at least medium first-year ice”; the exact quotation rejection is correct. E540 is a SCHEMA_TEXT individual record, but the asserted excerpt is a serialized RDF triple; the matching RDF_FACT is E428. The runtime must not silently substitute IDs or rewrite quotations. The seven extra reconciliation fields are property, proposed_path, proposed_path_role, proposed_unit, proposed_datatype, operands and representation_disposition; null does not make unknown fields valid. Correction feedback carried all eleven errors AND the exact rejected response, with the same candidate/evidence/binding/prior state. It did not repair these remaining errors. No stale candidate/code-location failure or property/path proposal validation result was reported for the invalid responses: parsing stopped before proposal routing.

Context-pending is retained in summary.json and this assessment: the first valid material claim has no validated resolution. The original pipeline delivery/history summary has findings=[] and terminal_review_decision=null after the later invalid review. That summary omission does not erase the earlier saved review or establish resolution. Original run/delivery files remain untouched; this report flags the limitation rather than changing their status.

Technical checks and remaining code issue

The candidate passed syntax, Meta-SHACL, activation, representation/admission checks and an actual engine probe, with no technical findings. These establish technical execution only. It targets all nltl:ship and unconditionally requires BOTH Category A and the designated medium-first-year condition; source/scope do not make every admitted ship Category A. That overrestriction is a remaining substantive issue, distinct from the reviewer's demand for the legal text to name RDF IRIs. It was not validly resolved or repaired. Independent evaluation later confirms an incorrect rejection on IMO-001-P02 by these two HasValue constraints. No changes or repaired-candidate recheck occurred; review and semantic repair effectiveness remain unproved.

Independent evaluation AFTER dispatch closure

Both arms: SAME unchanged candidate, 5 cases, 4 correct / 1 wrong / 0 no-verdict; zero scope-violation cases, 4 admitted-correct. All 3 counterparts pass. All 3 negative-case attributions remain UNRESOLVED_ATTRIBUTION: paired rejection/counterpart acceptance is observed, but no verified strict-detection credit is assigned. NLTL has no internal approval; delivered behavior is not correctness certification or accepted-only credit. Selected output was fixed before evaluation; no external score influenced selection. No recovery/regression comparison exists because there is no revision. This is a previously exposed, single-requirement development diagnostic, not fresh comparative performance.

Calls, tokens, bytes and timings

Four completed responses; all returned model=gpt-oss-120b (MATCH), no truncation/infrastructure/integrity failure. Input {summary['usage']['input_tokens']:,}; output {summary['usage']['output_tokens']:,}; total {summary['usage']['total_tokens']:,} tokens, provider usage including cached input/reasoning as returned. Exact serialized request bytes by call: 74,648 / 129,056 / 245,205 / 252,351. Client request time: generation {summary['client_phase_seconds']['generation']:.2f}s; primary reviews {summary['client_phase_seconds']['review']:.2f}s; correction {summary['client_phase_seconds']['review_format_retry']:.2f}s; repairs 0. Technical checks {summary['technical_check_seconds']:.2f}s; total dispatch workflow {summary['workflow_seconds']:.2f}s; independent evaluation {summary['evaluation_seconds']:.2f}s. Local retrieval has no separate measured timer in the frozen controller; do not fabricate one. Provider queue/loading/GPU timings unavailable. All complete actual provider request/response bodies, usage, request capacities, model metadata and latencies are in {B}/provider.

Artifacts and preservation

Run: {B}
Audit/preflight/feedback trace: {A}
Independent results: {B}/evaluation/selected_results.json
Summary: {S}/summary.json
Source/prompts/configuration/approved resources verified unchanged after run. All previous runs, evaluations, scores and retention ledger remain unchanged. No implementation changes or further model calls after the bounded outcome. All remaining evidence is preserved; no model response was manually corrected or promoted.
'''
(S/'REPORT.txt').write_text(report);(A/'DIAGNOSTIC_REPORT.txt').write_text(report)
# Save client/evaluation timing rows separately for reuse without inference.
(S/'timing_and_usage.tsv').write_text('call\troute\trequest_bytes\tinput_tokens\toutput_tokens\tclient_seconds\n'+''.join(f"{q['call']}\t{q['route']}\t{q['request_bytes']}\t{q['usage']['input_tokens']}\t{q['usage']['output_tokens']}\t{q['client_seconds']}\n" for q in requests))
before=load(A/'protected_before.json');changed=[n for n,h in before.items() if not (R/n).is_file() or sha(R/n)!=h];assert not changed,changed
verify(R,load(B/'freeze_lock.json'));write(A/'preservation_verification.json',dict(original_files_checked=len(before),changed=[],frozen_source_config_resources_verified=True,approved_scope_unchanged=True,all_candidate_hashes_verified=True,selection_fixed_before_evaluation=True,evaluation_dispatch_closure_hash_matches=True,previous_results_and_retention_ledger_unchanged=True,physical_model_calls=4,additional_model_calls_after_closure=0))
shutil.copyfile('/tmp/v0113_preflight.py',A/'preflight_script.py');shutil.copyfile('/tmp/report_v0113_diagnostic.py',A/'report_script.py')
write(A/'artifact_manifest.json',{str(p.relative_to(A)):sha(p) for p in sorted(A.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(report=str(S/'REPORT.txt'),summary=str(S/'summary.json'),calls=4,usage=summary['usage'],workflow_seconds=summary['workflow_seconds'],evaluation_seconds=summary['evaluation_seconds'],scope_violation_cases=0,technical_repairs=0,semantic_repairs=0,context_pending=True,terminal=summary['terminal'],historical_files_unchanged=len(before)),indent=2))
