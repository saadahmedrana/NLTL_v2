from pathlib import Path
import ast,json,hashlib,difflib,sys,shutil,importlib.metadata
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0115_CONTEXT_QUESTIONS';sys.path.insert(0,str(R/'src'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(A/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
old=read(R/'outputs/audits/20261125_V0114_SEMANTIC_HANDOFF/freeze_lock.json')
lock=dict(version='0.11.5',review_contract_version=4,files={n:sha(R/n) for n in old['files']})
for p in (R/'src/nltlv2').glob('*.py'):lock['files'][str(p.relative_to(R))]=sha(p)
lock['files']['tests/test_context_question_history.py']=sha(R/'tests/test_context_question_history.py')
save('freeze_lock.json',lock)
from nltlv2.hosted_pilot import verify
import nltlv2
verify(R,lock)
save('source_identity.json',dict(imported_source=str(Path(nltlv2.__file__).resolve()),source_version=nltlv2.__version__,installed_distribution_version=importlib.metadata.version('nltlv2-refined'),frozen_files=len(lock['files']),verification='PASS',note='Explicit source path checked; installed distribution metadata is recorded without relabelling.'))
refs={};diff=[];changed=[]
for p in sorted((A/'before').rglob('*')):
 if not p.is_file():continue
 n=str(p.relative_to(A/'before'));now=R/n
 if p.read_bytes()!=now.read_bytes():
  changed.append(n);diff.extend(difflib.unified_diff(p.read_text().splitlines(True),now.read_text().splitlines(True),fromfile='before/'+n,tofile='current/'+n))
 if now.suffix=='.py':
  refs[n]={x.name:x.lineno for x in ast.walk(ast.parse(now.read_text())) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
(A/'implementation.diff').write_text(''.join(diff));save('function_references.json',refs)
protected=read(A/'protected_before.json');mismatch=[n for n,h in protected.items() if not (R/n).is_file() or sha(R/n)!=h];assert not mismatch,mismatch[:10]
replayinputs=read(A/'replay_input_hashes.json');bad=[n for n,h in replayinputs.items() if not str(A) in n and sha(Path(n))!=h];assert not bad,bad
for n,h in old['files'].items():
 if 'tracking' in n or 'retention' in n:assert sha(R/n)==h
save('preservation_verification.json',dict(preexisting_protected_files=len(protected),changed_protected_files=mismatch,replay_input_mismatches=bad,historical_result='ACCEPTED_UNCHANGED',historical_scores_reports_candidates_fixtures_scopes_ledger='SHA256_UNCHANGED',model_calls=0,evaluation_reruns=0,changed_implementation_files=changed,new_test='tests/test_context_question_history.py'))
for name in ['replay_v0115.py','verify_v0115.py','finalize_v0115.py']:shutil.copyfile('/tmp/'+name,A/name)
report='''v0.11.5 — offline context-question carry-forward correction

Patch
Only the demonstrated handoff gap is changed. Existing context_resolution helpers now retain each wholly validated material question in a per-run ledger, with a public Q ID and software-owned stable identity, immutable original missing/why text, originating candidate/version/hash, exact evidence/provenance identities, observations, disposition history and retrieval attempts. Failed/partial reviews cannot add, close or overwrite questions. The Runner writes context_questions.json and includes it in the final run result.

Follow-up reviews and relevant repair packets receive a readable prior_context_questions list: original question/reason, originating candidate, supporting evidence mapped to CURRENT E aliases, readable provenance, retrieval status and artifact references. The immutable ledger retains exact original evidence and hashes. If old evidence is absent, its original text/provenance and explicit unavailability replace any stale alias. No semantic matching, silent substantive correction or post-evaluation diagnosis is introduced.

Contract
The initial compact assessment/issues/questions contract stays unchanged. Only when open prior questions exist, one conditional question_review list is required. Each prior Q ID must appear exactly once with disposition RESOLVED, WITHDRAWN or STILL_UNRESOLVED and nonempty why. Closure additionally requires supplied SOURCE, RDF/schema or caller-scope evidence references; context-status references alone are insufficient. Unknown/stale IDs, invalid evidence, incomplete/duplicate coverage, mutated snapshots, and closing a question while asking it again are invalid. APPROVE with STILL_UNRESOLVED remains invalid. STILL_UNRESOLVED retains the original blocking question and bounded retrieval request. Explanatory truth and whether evidence answers the question remain reviewer judgments, not deterministic proofs.

Generic software-only example (not a historical IMO response):
{"assessment":"APPROVE","issues":[],"questions":[],"question_review":[{"id":"Q1","disposition":"RESOLVED","why":"The supplied representation declaration specifies the previously missing property and datatype.","evidence":["E7"]}]}
E7 must actually be supplied and valid; this illustrative assertion earns no workflow or accuracy credit.

Verification
296 software tests passed, including 14 new generic controls; zero failures/errors. Controls cover immutable original wording/provenance, alias changes and absent evidence, valid supported resolution/withdrawal, invalid/missing references or explanations, stale state/IDs, missing or duplicate dispositions, contradictory closure/reasking, retrieval attempts, repair-packet delivery, and failed-review state preservation. The complete scripted controller route exhausts the existing response-correction allowance on bare approval, retains material questions as context-pending, and delivers technically qualifying code as UNVERIFIED/HUMAN_REVIEW_REQUIRED without authorizing repair. No model inference or benchmark evaluation was run. These are software controls, not accuracy evidence.

Exact saved sequence replay (prospective diagnostics only)
Actual provider call 3: unchanged HUMAN_REVIEW_REQUIRED response validates, creating Q1. Its original SOURCE E191 is remapped to E436 after retrieval while preserving immutable evidence/provenance. The complete representative follow-up packet contains Q1's full missing/why wording, candidate 2 SHA f1e7a37af387274d7cb1481d1271249fd2b5f3ed732c7d2cc74db4b348e0840e, full candidate/current source-schema evidence, and round-1 retrieval summary (20 terms, no new source characters).
Actual provider call 4: unchanged HUMAN_REVIEW_REQUIRED response asks Q2 but lacks $.question_review for Q1; MISSING_REVIEW_FIELD. It would require bounded correction, not commit Q2 under the new controller.
Actual provider call 5: historical bare APPROVE lacks $.question_review and cannot clear either historical question. For this independent guard test only, both originally validated historical question events are reconstructed. Q2 kind/reference/section are restored from the SAME original raw response because the old normalized artifact omitted them; missing/why/evidence claims are unchanged. This is labelled historical-event/interface-only reconstruction, not acceptance of call 4 under current validation. A new controller would require correction/stop at call 4; call 5 is not claimed newly dispatched.
Both reconstructed historical questions remain STILL_UNRESOLVED. The historical ACCEPTED result/report, candidate bytes, scores and ledger remain unchanged; no scores are rewritten.

Prepared diagnostic (UNDISPATCHED)
diagnostic.prepared.json specifies one FRESH IMO-001 shared-start generation, preserved byte-for-byte as Single-shot and reused by NLTL. Start with empty issues/questions, load the existing approved scope through scope_files, and import no historical candidate/question/solution or evaluation resource into requests. No forced questions/repairs/approval or preferred-result rerun; unexercised branches must be labelled. Existing limits unchanged: one technical plus one semantic revision, three candidates, four primary reviews total/three per candidate, one shared response correction per review, two retrieval rounds, eleven physical provider HTTP calls including corrections/repair, 16,000 output tokens per request, 176,000 maximum reserved output tokens, 600-second workflow window. Final handoff/delivery policy remains separate from approval; evaluation can occur only after dispatch closure under separate authorization.

Capacity
The complete follow-up rendering has 66,975 verified supplied-text tokens + 16,000 output tokens = 82,975 lower-bound input/output capacity, within the public 131,072 context. Provider framing and any lower deployed limit remain unknown; no silent truncation or arbitrary byte ceiling is introduced.

Evidence files
complete_followup_packet.json: COMPLETE current follow-up rendering, provider payload, internal state and original evidence provenance; OFFLINE/NOT DISPATCHED.
exact_saved_sequence_replay.json: every unchanged saved review and rejecting rule.
historically_validated_question_event_ledger.json: original historical question events, no production seeding.
verification.json / offline_tests.log: all software checks.
implementation.diff / function_references.json: exact patch and function line references.
freeze_lock.json / source_identity.json: frozen tested source and honest import/distribution identity.
preservation_verification.json: protected historical/resource hash verification.

Limitations
A citation/disposition's semantic adequacy remains model judgment. Question deduplication uses kind plus whitespace-normalized exact missing text, not semantic inference. A future live run may never exercise the carry-forward branch. No new operational or accuracy claim is made.
'''
(A/'REPORT.txt').write_text(report)
save('artifact_manifest.json',{str(p.relative_to(A)):sha(p) for p in sorted(A.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(frozen_files=len(lock['files']),protected_files=len(protected),changed=changed,report=str(A/'REPORT.txt'),identity=read(A/'source_identity.json')),indent=2))
