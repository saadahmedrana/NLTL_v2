from pathlib import Path
import json,hashlib,sys,difflib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS';C=A/'interface_clarity';G=R/'outputs/experiments/20261125_V0115_CONTEXT_QUESTION_CONTINUATION_01';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Candidate,write
from nltlv2.review_validation import validate_review
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
v=load(C/'verification.json');assert v['success'] and v['tests']==303
s=load(G/'IMO-001/NLTL/review_state_001.json');c=Candidate(s['candidate_version'],s['full_candidate'],'');p=s['previous_candidate'];previous=Candidate(p['version'],p['full_code'],'') if p else None;rows=[]
for n in [1,2]:
 path=G/'provider'/f'call_{n:03d}_response.json';obj,audit,errors=validate_review(load(path),c,s['context'],previous=previous,changes=s['change_manifest'],prior_issues=s['prior_issues'],request_body=s);assert errors and obj is None;rows.append(dict(call=n,actual_response_file=str(path),actual_response_sha256=sha(path),values_unchanged=True,classification='OFFLINE_INTERFACE_DIAGNOSTIC_NOT_ACCEPTED_REVIEW_NO_WORKFLOW_CREDIT',errors=errors))
write(C/'unchanged_saved_response_diagnostics.json',rows)
protected=load(C/'protected_before.json');changed=[n for n,h in protected.items() if not (R/n).is_file() or sha(R/n)!=h];assert not changed,changed[:10]
oldlock=load(A/'freeze_lock.json');assert sha(R/'prompts/generator.txt')==oldlock['files']['prompts/generator.txt'];assert sha(R/'configs/nltl.json')==oldlock['files']['configs/nltl.json'];assert sha(R/'src/nltlv2/requests.py')==oldlock['files']['src/nltlv2/requests.py']
files=['prompts/reviewer.txt','prompts/repair.txt','src/nltlv2/review_protocol.py','src/nltlv2/review_validation.py','src/nltlv2/runner.py'];diff=[];sizes=[]
for n in files:
 before=C/'before'/n;now=R/n;diff.extend(difflib.unified_diff(before.read_text().splitlines(True),now.read_text().splitlines(True),fromfile='before/'+n,tofile='current/'+n))
 if n.startswith('prompts/'):
  sizes.append(dict(file=n,before_bytes=len(before.read_bytes()),after_bytes=len(now.read_bytes()),before_words=len(before.read_text().split()),after_words=len(now.read_text().split())))
(C/'implementation.diff').write_text(''.join(diff));write(C/'prompt_sizes.json',sizes)
write(C/'tested_source_hashes.json',{n:sha(R/n) for n in files+['tests/test_prompt_clarity.py','src/nltlv2/requests.py','prompts/generator.txt','configs/nltl.json']});write(C/'preservation_verification.json',dict(protected_files=len(protected),changed_protected_files=[],generator_prompt_unchanged=True,initial_request_builder_unchanged=True,model_settings_and_bounds_unchanged=True,scope_schema_fixtures_tracker_ledger_historical_scores_and_reports_unchanged=True,model_calls=0,evaluation_reruns=0,new_diagnostic_prepared=False,version_bump=False))
review=(R/'prompts/reviewer.txt').read_text();repair=(R/'prompts/repair.txt').read_text()
report='''

FOCUSED OFFLINE INTERFACE CLARITY UPDATE — 2026-11-25
This addendum records subsequent prompt/diagnostic work, not a new pipeline version or model run. Earlier freeze locks, prepared diagnostics and historical reports remain unchanged; their old hashes are not relabelled as the current working source. No diagnostic was prepared or dispatched by this task.

Exact changes
prompts/reviewer.txt now separates regulation (obligation), schema/mappings (RDF representation), approved scope (external assumptions), candidate (object of assessment), and execution diagnostics (technical behavior only). It supplies the requested ordered six-step procedure, then one accepted evidence-field example and one accepted code-location example. Carried-forward questions are explicitly addressed; current and prior questions are treated consistently. Conditional change/gap review and representation safeguards remain, without model-owned hash/reconciliation bookkeeping.
The authoritative schema description in review_protocol.compact_contract_instructions is shortened to response-field and decision rules. The initial three fields and conditional question_review/change_review/gap_review representations are unchanged. No additional protocol layer was added.
review_protocol.response_correction_instruction and Runner.review retain the existing feedback field and single shared allowance. Guidance is selected from actual error paths: evidence problems explain supplied E IDs versus issues[].location and exact optional quotations; location problems explain valid code ranges. The unrelated general operand-pairing instruction is removed from correction feedback. Original state, failed-review isolation and complete-response requirements remain.
contract_shape_errors now reports the actual matching reference-object field errors (such as forbidden unit), instead of collapsing them into a generic union-type message. validate_compact_review also checks safe, well-typed evidence fragments when other fields are malformed. Empty spans, unknown references and false quotations are reported together. Malformed reviews still return no accepted review, issues or dispositions. No assertion, quote or historical response is rewritten.
prompts/repair.txt explicitly identifies complete latest previous_candidate, original diagnostics, affected locations, evidence and intended correction; requires complete revised SHACL; preserves unaffected obligations. Constraint deletion merely to pass checks remains prohibited. Supported removal/replacement remains subject to evidence and preservation recheck. No generated shape was edited.

Verification
303 software tests pass (296 existing plus 7 focused controls); zero failures/errors, network blocked, model calls zero, benchmark evaluation reruns zero. The controls check exact accepted string/object evidence forms and extracted code ranges, context dispositions without locations, independent error aggregation, relevant correction wording, complete original repair delivery, prompt role/procedure alignment, and identical initial request construction. Existing shared-start integrity, bounds and rejection controls continue to pass.
Both actual saved continuation responses were replayed UNCHANGED against the clarified interface. Both remain invalid and receive no workflow credit. The first now exposes forbidden evidence unit, unknown candidate_shape ID, empty E471 span and false E471 quotation; the correction still exposes forbidden unit and unknown candidate_shape ID. No historical review became repair authorization or an accepted disposition. Full error arrays and raw-artifact hashes: interface_clarity/unchanged_saved_response_diagnostics.json.
The model's candidate_shape paraphrases are also not exact code quotations. Unknown evidence cannot be authenticated as a candidate-code citation; no automatic reinterpretation as a code location is attempted.

Research representation decision is unchanged
IMO-001 source establishes design intent. Approved external eligibility does not separately assume the polar-waters design condition true for every record. Current IMO-001 bindings do not supply that separate mapping. The operational Boolean is not established equivalent to design intent. This software update neither supplies a mapping nor amends scope; the concern remains unresolved pending supported representation input or separately approved scope change. Evaluation labels/performance were not used for this decision and no requirement-specific answer was added to production text.

Preservation
The generator prompt, initial_request/repair packet builder, model settings, shared-start input construction and call/candidate/retrieval/time limits are unchanged. All preexisting runs, scores, candidate bytes, fixtures, scopes, ontology, tracker, retention ledger and historical reports verify unchanged by SHA256. Only this existing OFFLINE patch report receives this addendum; its prior exact contents are archived under interface_clarity/before.

Final reviewer prompt
--- BEGIN reviewer.txt ---
'''+review+'''--- END reviewer.txt ---

Final generator repair prompt
--- BEGIN repair.txt ---
'''+repair+'''--- END repair.txt ---

Patch, focused controls, prompt sizes, tested-source hashes and preservation results are recorded in interface_clarity/. Software evidence is not evidence of regulatory accuracy. No live diagnostics are scheduled or authorized by this update.
'''
oldreport=C/'before/outputs/audits/20261125_V0115_CONTEXT_QUESTIONS/REPORT.txt';(A/'REPORT.txt').write_text(oldreport.read_text()+report);(C/'REPORT_ADDENDUM.txt').write_text(report)
for n in ['clarity_patch.py','clarity_tests.py','verify_prompt_clarity.py','finalize_prompt_clarity.py']:shutil.copyfile('/tmp/'+n,C/n)
write(C/'artifact_manifest.json',{str(p.relative_to(C)):sha(p) for p in C.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(tests=v['tests'],preserved_files=len(protected),replay_error_codes=[dict(call=r['call'],errors=[e['code'] for e in r['errors']]) for r in rows],prompt_sizes=sizes,report=str(A/'REPORT.txt'),model_calls=0),indent=2))
