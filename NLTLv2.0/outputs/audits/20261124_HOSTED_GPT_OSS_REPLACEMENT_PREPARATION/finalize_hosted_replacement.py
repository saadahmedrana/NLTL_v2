from pathlib import Path
import json,hashlib,shutil,sys
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';B=R/'outputs/experiments/20261124_V0111_HOSTED_GPT_OSS_SHARED_START_REPLACEMENT_SMOKE_01';sys.path[:0]=[str(A/'runtime/src'),str(A/'tokenizer_runtime')]
from nltlv2.core import load,write
from nltlv2.review_protocol import normalize_response,ReviewerFormatError
from nltlv2.requests import review_base

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Exact saved responses, unchanged metadata/text; software diagnosis only, never repair feedback.
controls=[]
for n in [3,4]:
 response=load(B/'provider'/f'call_{n:03d}_response.json')
 try:normalize_response(response);outcome='UNEXPECTED_VALID'
 except ReviewerFormatError as error:outcome=error.details
 controls.append(dict(label='OFFLINE_SAVED_RESPONSE_ROUTING_DIAGNOSTIC_NO_MODEL_CALL',call=n,response_sha256=sha(B/'provider'/f'call_{n:03d}_response.json'),status=response['status'],finish_reason=response['finish_reason'],final_output_present=response['final_output_present'],existing_review_normalizer_outcome=outcome,actual_transport_returned_to_runner=n==3,substantive_claims_unchanged=True,accepted_issues_created=False))
write(A/'saved_response_routing_diagnosis.json',controls)
first=json.loads(load(B/'I2-005/NLTL/request_002.json')['user']);retry=json.loads(load(B/'I2-005/NLTL/request_003.json')['user']);assert review_base(first)==review_base(retry)
write(A/'retry_state_verification.json',dict(status='PASS',same_candidate_sha256=first['candidate_sha256'],same_candidate_code=first['full_candidate']==retry['full_candidate'],same_evidence_prior_state_and_binding=True,one_existing_correction_used=True,accepted_issues_from_truncated_reviews=0,no_extra_budget=True))
report='''HOSTED GPT-OSS REPLACEMENT SMOKE — v0.11.1 — 24 November2026

The requested focused fixes were implemented,236 offline tests passed, and code/prompts were frozen before the one replacement dispatch. The byte blocker is gone. The full live review reached Aalto. The smoke then exposed a reviewer-output-budget/routing limitation and stopped; it did not complete operationally. No code/prompt change, extra generation, manual shape edit, preferred-result rerun or further model call followed closure. The longer experiment remains BLOCKED and undispatched.

EXACT CHANGES
src/nltlv2/transport.py::HostedResponsesTransport.dispatch removes max_request_bytes and its rejection. All request body bytes and sizes remain artifacts. No alternative byte/character ceiling exists. Existing external Bearer authentication, typed assistant-final extraction, honest returned-model metadata, complete raw responses/usage/finish status, no redirects/retries/fallback, call/time/output reservations and candidate/request integrity remain.
src/nltlv2/token_budget.py::load_counter/preflight uses pinned tiktoken0.12.0/regex2025.11.3 and hash-verified o200k_harmony data. It counts every supplied text block and reserves max_output_tokens against known token limits; it never truncates. Official pinned GPT-OSS120b config specifies131072 tokens. The hosted /v1/models catalog confirms the model but does not expose its deployed limit, output ceiling, tokenizer revision or full framing. Those stay UNKNOWN. Verified supplied-text count is not misrepresented as exact complete provider input. Provider context rejection would stop, not trigger a smaller/fallback request. The observed provider input count was74 above supplied-text count for all four smoke calls; that is evidence for these calls, not an assumed universal constant.
src/nltlv2/runner.py::Runner.run now counts physical transport attempts separately from logical dispatch attempts and preserves complete interrupted-candidate history/findings. Single-shot still makes exactly one call and performs no feedback checks/reviews; its unchanged original artifact is retained for the same external parse/execution diagnostics even if wrapper formatting fails. No shape is repaired by the evaluator.
evaluation/evaluate_hosted_shared_start.py::execute_unchanged applies identical execution to both arms, including scope-violating candidates. Raw behavior, exact scope findings and scope-qualified/admitted credit are separate. Scope violations remain blocking for admitted credit; they are not hidden behind a missing raw verdict or silently waived. Disposable exact graph copies prevent pySHACL's in-memory axiom additions from mutating cached candidates/inputs. Original files remain byte-identical. NOT_RUN is explicit and separate from model failures.
Review/path/citation validation, tracker, source/schema/scopes, technical/acceptance criteria, latest-technical delivery and final handoff are unchanged. No old framework or regulatory solution profile was copied.

OFFLINE VERIFICATION / FREEZE
236 tests passed with DNS/sockets blocked and0 model calls, including generic token boundaries/provider limit precedence, unknown framing, complete large-packet delivery, immutable candidate/retry state, physical accounting, interrupted-history preservation and symmetric unchanged-shape/scope evaluation. The previously blocked140705-byte review packet was delivered unchanged through a fake HTTP session;38194 supplied-text tokens+4000 reserved output tokens, complete saved candidate. This is interface/software evidence, not model-review success or accepted substantive claims.
All five proposed initial pairs have identical actual requests/settings. All supplied-text+output counts fit the published model context.46 unchanged input-construction/scope proofs were revalidated by hash against the retained ontology and approved declarations, separately from production context. freeze_lock.json/runtime contain the executed0.11.1 source and pinned tokenizer resources. Legacy installed distribution metadata0.9.2 is recorded honestly; execution uses verified frozen PYTHONPATH source, not an assumed installation label.

ONE ACTUAL REPLACEMENT DISPATCH
I2-005: one fresh shared generation; Single-shot raw response/candidate bytes exactly equal NLTL's start. Initial candidate5ef26fe0110b491f46279a0e2da007d5ed08115d8bb2e1dcf04c5ad61b953698 had confirmed canonical QUDT fragment-IRI errors and extra global targets outside the admitted ship population. One production targeted repair generateda686756008b640188b009169dde8e827a40cb974b18d1664c3e2de56a61cac81. It used canonical QUDT slash IRIs and removed the two extra global targets while retaining nested constraints. Technical/static/runtime recheck passed; numeric RDF-term-identity warning remained.
Primary review: HTTP200, full141339-byte packet delivered; statusincomplete/reasonmax_output_tokens after4000 output tokens,3573 reasoning tokens. Existing validation rejected it as TRUNCATED_REVIEW; no issues were accepted. One shared correction used the same candidate/evidence/binding/original prior state; its142199-byte packet also reached Aalto.
Correction: HTTP200, statusincomplete/reasonmax_output_tokens,4000 output tokens including3997 reasoning tokens, no final assistant text. The frozen transport's unconditional missing-final check raised HOSTED_FINAL_OUTPUT_MISSING before the normalizer could classify truncation. Exact controller terminal: INFRASTRUCTURE_FAILURE. This is not a context-size failure or a validated source/path finding, and no transport/HTTP failure occurred.
The latest technically qualifying repair was delivered UNVERIFIED / HUMAN_REVIEW_REQUIRED, never ACCEPTED. Both completed/interrupted candidate history rows, findings, diff, actual packets/responses, one format failure, prior-state proof and terminal reason are retained. No validated model review, grounded removal assessment, source retrieval or internal acceptance was exercised.
IMO-001: NOT_RUN after the existing infrastructure stop; no model output. Its5 original cases+3 counterparts are unstarted, not model failures. Five provider HTTP requests total:1 metadata-only GET+4 inference requests, below20 total. No persistent retry or extra response-correction allowance.

INDEPENDENT POST-CLOSURE EVALUATION
Both arms keep the same10 original+7 counterpart planned denominators: started I2-0055+4 and NOT_RUN IMO-0015+3. No selection used evaluation scores.
I2-005 Single-shot unchanged original: raw4/5 ordinary agreement,1 wrong positive rejection,0/4 strictly verified detections,0/4 counterparts accepted. Extra target classes remain explicit scope violations; admitted credit is withheld on all5 originals.
I2-005 NLTL UNVERIFIED repair: raw4/5 agreement,1 wrong positive rejection,0/4 strictly verified detections,1/4 counterparts accepted. Scope boundary passes; unresolved exact numeric-term matching still rejects the valid positive case. There is no approved/certified-correct output.
All5 original-case verdicts are unchanged between initial and repair;0 original-case behavior recoveries/regressions. Canonical vocabulary/scope repairs are real technical improvements and scope-qualified coverage changes, not evidence of four new semantic recoveries. The one counterpart improvement is observed for the combined repair; no ablation or unsupported strict attribution is claimed. Both arms now expose raw behavior and scope violations using the same function; prior smoke scores were not rewritten.

CALLS / TOKENS / PHASE TIMES
4 physical inference calls:113905 input+11069 output=124974 tokens; returned modelgpt-oss-120b throughout. One metadata-only HTTP GET is separately recorded. Generation7.566s,repair9.900s,review23.446s,correction21.730s,technical checks0.567s,client workflow64.526s,independent evaluation33.606s. Technical time is within the1.884s client nonrequest remainder, not an extra disjoint bucket. Queue/model-loading/GPU timings UNAVAILABLE.
Actual payloads:47552 generation,87773 repair,141339 review,142199 correction bytes. Every packet is complete; no byte guard or source-context truncation. Supplied text counts and actual provider counts/margins are in actual_calls_tokens_sizes.json.

REMAINING MINIMUM FIXES — PROPOSED, NOT IMPLEMENTED AFTER FREEZE
1. Return an incomplete empty-final reviewer response to the existing truncated-review validator, so it consumes only the shared correction allowance and terminates with the explicit existing exhausted-review outcome. Completed responses with no final text must remain terminal; never scrape reasoning as a review. saved_response_routing_diagnosis.json replays exact saved metadata/text offline and confirms the existing normalizer already returns TRUNCATED_REVIEW for both responses. It accepts no claims and edits no metadata.
2. Predeclare and offline-verify a GPT-OSS reviewer output/reasoning budget sufficient for a complete protocol response.4000 was demonstrably insufficient here. Do not relax evidence/path/acceptance criteria, add a retry loop or use a lenient final attempt. No new budget was tested live after this run.
The main-launch condition in the user's instruction was not met, so no ready-to-run main launch command is issued. main_manifest.blocked.json has dispatch_ready=false and the production entry rejects it before output/provider construction. Fixed queue remains TRF-035,IMO-001,TRF-010,I2-004,I2-005 with seed20261124, chosen by source/schema/approved-scope readiness before performance; all have prior development exposure; I2-042 deferred. No byte-based readiness exclusions remain. Provisional planning remains at most50 calls,320000 reserved output tokens,7200 execution seconds,180s request timeout and1920s remaining before another requirement starts. These are blocked planning parameters, not authorization or a validated completion forecast. One interrupted requirement with two truncated reviews cannot establish two-hour completed-workflow throughput. Local checks still have no hard process deadline; hosted capacity/framing is undisclosed.

PRESERVATION
All previous smoke/pilot results, MVP, historical runs/scores, fixtures, ontology, approved scopes, tracker and17-item retention ledger remain unchanged. Source originals and implementation.patch are retained here. No commits/pushes/new study/framework. All current smoke artifacts are under outputs/experiments/20261124_V0111_HOSTED_GPT_OSS_SHARED_START_REPLACEMENT_SMOKE_01; results summary/table under results/. Source freeze still matches after evaluation; no model calls after closure.

PRIMARY TOKEN REFERENCES
https://huggingface.co/openai/gpt-oss-120b/blob/988e56b6fc3c723ad30aa7f18db742f54f921567/config.json
https://github.com/openai/gpt-oss/blob/main/gpt_oss/tokenizer.py
Pinned local tokenizer packages/data hashes and the actual hosted model metadata receipt are retained here. Public model configuration is not substituted for an unexposed deployed provider setting.
'''
(A/'REPORT.txt').write_text(report)
(R/'results/hosted_gpt_oss_replacement_smoke_20261124.txt').write_text('HOSTED GPT-OSS REPLACEMENT DEVELOPMENT SMOKE — v0.11.1\nOperational completion: NO; dispatch closed; no main experiment.\n\nRequirement  Arm          Raw agreement  Scope-qualified   Delivery / approval\nI2-005       Single-shot  4/5            NO:extra targets  Exact original;no admitted credit\nI2-005       NLTL         4/5            YES               UNVERIFIED / HUMAN_REVIEW_REQUIRED\nIMO-001      Both         NOT_RUN        NOT_RUN           No output\n\nStrict verified0/4 both;counterparts accepted0/4 Single-shot,1/4 NLTL.\nOriginal-case verdict changes after repair:0 recoveries,0 regressions,5 unchanged.\n4 inference calls+1metadata GET;113905 input/11069 output tokens.\nGeneration7.566s;repair9.900s;review23.446s;correction21.730s;checks0.567s.\nWorkflow64.526s;evaluation33.606s;provider-internal timings unavailable.\nStop: incomplete4000-token reviewer correction had no final text;transport classified\nHOSTED_FINAL_OUTPUT_MISSING as infrastructure. Code remained frozen;no rerun.\nSee outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/REPORT.txt.\n')
# Rerunnable offline command writes fresh audit outputs, never overwriting this freeze's evidence.
s=Path('/tmp/verify_replacement_offline.py').read_text().split('# Interface-only replay:')[0]
s=s.replace("start=time.monotonic();suite=", """from nltlv2.core import Project,stamp
for name,h in json.loads((A/'freeze_lock.json').read_text())['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
O=Project(R).output('audits','OFFLINE_HOSTED_V0111_'+stamp());print('NEW_OFFLINE_OUTPUT '+str(O),flush=True)
start=time.monotonic();suite=""")
s=s.replace("(A/'offline_tests.log')", "(O/'offline_tests.log')").replace("(A/'offline_tests.json')", "(O/'offline_tests.json')")
(A/'routine_offline_verification.py').write_text(s)
(A/'TERMINAL_COMMANDS.txt').write_text('''OFFLINE ONLY — no provider/model calls, new audit output every run:
PYTHONDONTWRITEBYTECODE=1 '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python' -B '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/routine_offline_verification.py'
Expected:236 tests,OK,failures0/errors0/networkBLOCKED/model_calls0.

MAIN INFERENCE: NOT READY — no launch command is issued because the user's
operational-smoke condition was not met. Do not reuse the earlier version's launcher
or change dispatch_ready to bypass this failure. Main queue/manifest are prepared
but blocked; no longer experiment or additional smoke is authorized by this report.

The independent replacement-smoke evaluation already completed after verified
closure. Its output directory is immutable; the evaluator refuses to overwrite it.
Do not rerun the smoke or select another candidate by its external score.
''')
for name in ['finalize_hosted_replacement.py']:
 shutil.copy2(Path('/tmp')/name,A/name)
write(A/'artifact_manifest.json',dict(files={str(p.relative_to(R)):sha(p) for p in A.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'},smoke_files={str(p.relative_to(R)):sha(p) for p in B.rglob('*') if p.is_file()}))
print('Final report, exact saved-response routing diagnosis, result table and offline-only command saved; frozen pipeline unchanged.')
