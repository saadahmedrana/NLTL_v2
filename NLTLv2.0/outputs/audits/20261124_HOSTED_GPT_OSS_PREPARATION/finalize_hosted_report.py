from pathlib import Path
import json,hashlib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION';B=R/'outputs/experiments/20261124_V0110_HOSTED_GPT_OSS_SHARED_START_SMOKE_01'
def load(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for p in [A/'smoke_summary.json',R/'results/hosted_gpt_oss_smoke_20261124.json']:
 x=load(p);x['label']='HOSTED_SHARED_START_DEVELOPMENT_SMOKE_NOT_COMPARATIVE_PERFORMANCE';x['fresh_generation']=True;x['queue_seed_applies_to_requirement_order_not_candidate']=True;write(p,x)
# A rerunnable offline verifier always uses a NEW audit output; it cannot overwrite frozen test evidence.
s=Path('/tmp/run_hosted_offline.py').read_text();s=s.replace("A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION'", """from nltlv2.core import Project,stamp
lock=json.loads((R/'outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/freeze_lock.json').read_text())
import hashlib
for name,h in lock['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
A=Project(R).output('audits','OFFLINE_HOSTED_CHECK_'+stamp())
print('NEW_OFFLINE_OUTPUT '+str(A),flush=True)""");(A/'offline_verification.py').write_text(s)
launch='''#!/bin/bash
set -euo pipefail
NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_AUDIT="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION"
# Offline gate: currently exits2. No provider process is constructed if blocked.
"$NLTL_PY" -B -c 'import json,sys; m=json.load(open(sys.argv[1])); print("READY" if m["dispatch_ready"] else "BLOCKED: "+m["blocker"],flush=True); sys.exit(0 if m["dispatch_ready"] else 2)' "$NLTL_AUDIT/main_manifest.blocked.json"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_AUDIT/runtime/src"
export NLTL_ALLOW_MODEL_CALLS=YES
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
exec "$NLTL_PY" -B -m nltlv2.hosted_pilot --project "$NLTL_ROOT" --manifest outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/main_manifest.blocked.json --run-id 20261124_V0110_HOSTED_GPT_OSS_SHARED_START_MAIN_01 --allow-model-calls > "$NLTL_AUDIT/main_dispatch.stdout.txt" 2> "$NLTL_AUDIT/main_dispatch.stderr.txt"
'''
(A/'launch_main.guarded.sh').write_text(launch)
commands='''HOSTED GPT-OSS v0.11.0 COMMANDS — main dispatch is BLOCKED, not launched

Set paths (no network, no credentials printed):
NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_AUDIT="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION"

OFFLINE tests (new output each time; no evaluation rerun/model calls):
PYTHONDONTWRITEBYTECODE=1 "$NLTL_PY" -B "$NLTL_AUDIT/offline_verification.py"
Success: Ran228 tests ... OK; JSON tests228/failures0/errors0/networkBLOCKED/model_calls0.
A frozen-source mismatch stops before tests; inspect that error rather than force a run.

MAIN INFERENCE launch command — WOULD make model calls only after readiness gate:
bash "$NLTL_AUDIT/launch_main.guarded.sh"
CURRENT EXPECTED OUTPUT: BLOCKED: Required hosted review stage was not exercised: ...
CURRENT EXPECTED EXIT:2; no main experiment output or provider call.
Do not edit the readiness flag to bypass the blocker. The manifest is hash-bound.
A separately verified capacity/budget correction and freeze is needed first.

MONITOR, only after an actual authorized main launch exists:
tail -f "$NLTL_AUDIT/main_dispatch.stdout.txt" "$NLTL_AUDIT/main_dispatch.stderr.txt"
cat "$NLTL_ROOT/outputs/experiments/20261124_V0110_HOSTED_GPT_OSS_SHARED_START_MAIN_01/progress.json"
cat "$NLTL_ROOT/outputs/experiments/20261124_V0110_HOSTED_GPT_OSS_SHARED_START_MAIN_01/provider/physical_calls.json"
The paired entry records progress/call artifacts during work and prints closure at end.
Missing files before launch are expected. No Triton/scheduler commands apply.

INDEPENDENT EVALUATION — OFFLINE, only AFTER dispatch closes:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$NLTL_AUDIT/runtime/src" "$NLTL_PY" -B "$NLTL_ROOT/evaluation/evaluate_hosted_shared_start.py" --project "$NLTL_ROOT" --run-id 20261124_V0110_HOSTED_GPT_OSS_SHARED_START_MAIN_01
The evaluator requires exact dispatch closure, candidate and selection hashes,
unchanged admitted cases/counterparts, and a new evaluation directory. It refuses
missing closure or overwriting an evaluation. No dependent job/server is needed.
Success: evaluation_complete.json statusCOMPLETE/model_calls0 plus printed summary.
Do not use the old hosted connectivity/generate commands as setup tests: they make calls.
No smoke relaunch command is supplied because this smoke is closed and must not rerun.
'''
(A/'TERMINAL_COMMANDS.txt').write_text(commands)
report='''HOSTED GPT-OSS SHARED-START DEVELOPMENT SMOKE — 24 November2026

Outcome: v0.11.0 was implemented, offline verified and frozen. The single authorized smoke stopped after2 physical provider calls because the first review packet exceeded the frozen client byte guard. It is NOT an end-to-end source-grounded-review success. No rerun, prompt/implementation change after freeze, main experiment or Triton activity occurred.

IMPLEMENTATION / FREEZE
src/nltlv2/transport.py::HostedResponsesTransport is an explicit Bearer Responses adapter for https://ai-api-v2.aalto.fi/v1/responses and gpt-oss-120b. Historical protocol knowledge is reused, not its client/orchestrator. One HTTP attempt per dispatch; retries0 and redirects disabled; no provider/model fallback. Typed assistant output_text is extracted; reasoning remains in complete raw response bodies. Returned model stays unknown if absent; mismatches stop. Both live responses returned gpt-oss-120b, completed, with separate reasoning and assistant output. This is honest returned metadata, not proof of pinned weights/tokenizer revision. Raw bytes, parsed objects, usage, status/incomplete details and request latency are retained. Credentials stay external; auth headers are not saved. Missing final text/refusal-only output stops rather than scraping reasoning.
src/nltlv2/runner.py::Runner.run(shared_start=...) compares identical initial requests, consumes the same fresh raw response without another provider generation, and records pre-review technical evidence. It preserves the existing acceptance, review/path/evidence validation, repair authorization, correction/retrieval limits and tracker.
src/nltlv2/delivery.py::finalize selects the highest technically qualifying version without scores. ACCEPTED still requires existing acceptance; otherwise UNVERIFIED, or NO_VERDICT if none qualifies/integrity fails. Completed technical evidence survives a subsequent provider-review failure. Findings/terminal reason remain attached. Final review/handoff is a deterministic mapping of saved validated review and technical state to APPROVE/HUMAN_REVIEW_REQUIRED/REJECT; it is not another model call or human-review arm and cannot authorize another repair.
src/nltlv2/hosted_pilot.py::run_pair/main is a small entry around the production Runner, not a new experiment framework. It makes one shared generation, records exact arm equality, applies global physical caps, freezes/seals selection and all candidates, and closes dispatch before external evaluation. Production uses source-only resource capabilities; no evaluation bindings, fixture identities, labels, counterparts, historical solutions or candidates enter requests.
Freeze: freeze_lock.json and runtime/;228 offline tests passed with DNS/sockets blocked. Generic controls exercise final extraction, missing/mismatched identity, raw artifacts, no retry/fallback, request/call bounds, actual scripted repair, immutable shared starts, failed-review/no-repair and deterministic delivery/integrity handling. Full suite includes existing parser/Meta-SHACL/path/activation/evidence/correction/repair controls. Installed distribution metadata remains older0.9.2; executed frozen source is0.11.0 and checked by exact hashes, not represented as an installed0.11 distribution.

ACTUAL SMOKE
I2-005: initial request/raw/candidate equality PASS; only1 generation. Seed d8eb8e506d48f1fb4e7155ffa233fe42af15132aea2dfcf660f3df52046e976d failed admission target-boundary checks because linked hull points and quantities had global targets. One targeted repair removed those two global targetClass declarations, retaining nested reachability, quantity/unit constraints and numeric hasValue. Repair70ac8a563f208cda80c04ad75d5fc09e3761f103582b1b9b31eefa5b62681721 passed declared technical checks/runtime probe. A nonblocking numeric RDF-term-identity warning remained.
The review request was fully built/saved but its140705-byte serialized payload exceeded110000. Exact terminal outcome: INFRASTRUCTURE_FAILURE; diagnostic REQUEST_CONTEXT_BYTE_LIMIT_EXCEEDED_NO_TRUNCATION. This was a LOCAL CONSERVATIVE BYTE GUARD, not a demonstrated provider context rejection. No model review, correction, retrieval, grounded change assessment or internal acceptance occurred. Latest qualifying repair was delivered UNVERIFIED / HUMAN_REVIEW_REQUIRED. No more repair was permitted.
IMO-001: NOT_RUN after infrastructure stop;5 original cases and3 counterparts remain planned, not model failures. Repair was exercised; review/correction/retrieval/acceptance and the second requirement were unexercised.

INDEPENDENT EVALUATION AFTER CLOSURE
Same planned denominator per arm:10 original cases+7 counterparts. Started I2-005:5+4; unstarted IMO-001:5+3 NOT_RUN.
Single-shot retains its exact original output but has5 NO_VERDICT on admitted evaluation because its extra targets violate the scope boundary; this is loss through a declared gate, not five proved semantic errors.
NLTL delivered UNVERIFIED repair:4/5 ordinary agreement,1 wrong positive rejection;0/4 strictly verified detections,1 unresolved attribution and3 unrelated/additional failures;1/4 counterparts accepted. The positive's HasValue violation and retained numeric literal confirm that repair did not resolve the generic numeric-term warning. No approved/certified-correct output. The numerical constraints did not change: target-boundary repair opens admitted evaluation coverage, which must not be reported as four established semantic recoveries. All original/repair diagnostics remain separate. Raw evaluator NO_VERDICT aggregates include NOT_RUN; smoke_summary.json separates them explicitly.

PHYSICAL ACCOUNTING / TIMES
2 HTTP200 calls,35207 input+2331 output=37538 total tokens. Generation6.018s; repair7.938s; technical checks0.597s; total paired client workflow15.577s; independent evaluation5.934s. Provider request latency includes server/network work, not exposed device inference. Queue/loading/GPU timings are UNAVAILABLE.
Packets: generation44943 rendered/47552 actual payload bytes; repair76039/82111; review128322/140705 NOT SENT. No format-retry packet was exercised or fabricated. Full actual and attempted packets are saved.
Use provider/physical_calls.json for actual physical count. Legacy Runner provider_calls/dispatch_attempts also count the locally blocked logical review attempt; summing those fields would falsely give3. Candidate2's technical/diff/delivery artifacts are complete, but history.json has no completed row2 because review dispatch failed. Both are explicit reporting limitations, not grounds to rerun.

LONGER RUN — PREPARED, BLOCKED, NOT DISPATCHED
Queue fixed BEFORE model dispatch with seed20261124: TRF-035, IMO-001, TRF-010, I2-004, I2-005. All have approved source/schema/scope; all have prior development exposure. I2-042 deferred. Initial rendered sizes:156009,70678,142511,45796,44943 bytes respectively. TRF-035/TRF-010 exceed the conservative packet bound and remain explicit NOT_RUN blockers. Neither scope nor source is truncated or expanded. Three initial-packet-ready requirements remain, but no complete reviewed workflow has been observed.
Provisional limits:30 physical calls total;10/eligible requirement (one shared generation+one repair+four primary reviews+four shared corrections),2 candidates,3 primary reviews/candidate,2 retrieval rounds; generation/repair16000 and review/correction4000 output tokens,192000 reserved output tokens total. Serialized input bound110000bytes/call,3.3MB aggregate; exact input-token ceiling is NOT verified without hosted tokenizer/capacity evidence. Execution budget7200seconds; request timeout180seconds; start another requirement only with at least1920seconds remaining. Local engine checks lack a hard timeout, so this is a time-budget guard, not a guaranteed hard deadline. No need to fill two hours if the ready queue finishes.
Only two request latencies from one interrupted requirement exist. Request-only extrapolation of ten calls is roughly60–80seconds, omitting unmeasured review/correction output length, retrieval, checks and service variation. A precise two-hour throughput forecast is unsupported. The main manifest has dispatch_ready=false and its launch script exits BLOCKED before any provider construction. Exact test/launch/monitor/evaluate commands are in TERMINAL_COMMANDS.txt.
Minimum NEXT correction proposal, not implemented: establish a justified context/token budget for full review/change evidence, then adjust only that declared capacity gate and verify complete review delivery offline. Do not disable source grounding, drop material evidence or loosen acceptance. Clarify logical/physical counters and interrupted-candidate reporting in a later tested version. Preserve this frozen smoke as failed-stage evidence; no preferred-result rerun.

PRESERVATION
MVP, historical outputs/scores, fixtures, ontology, approved scopes, tracker and17-item retention ledger unchanged. Existing source changes limited to runner/transport/version declarations; originals retained. No commits/pushes. All candidates/raw requests/responses/diagnostics/diff/transitions/technical findings/delivery/evaluation saved under the established smoke folder. New summary in results/hosted_gpt_oss_smoke_20261124.json. No claims of held-out performance, regulatory certification or superiority over Single-shot.
'''
(A/'REPORT.txt').write_text(report)
for name in ['implement_hosted.py','write_hosted_files.py','write_pilot.py','write_hosted_tests.py','write_hosted_eval.py','prepare_hosted_freeze.py','report_hosted_smoke.py','finalize_hosted_report.py']:
 p=Path('/tmp')/name
 if p.exists():shutil.copy2(p,A/name)
write(A/'artifact_manifest.json',dict(files={str(p.relative_to(R)):sha(p) for p in A.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'},smoke_artifact_files={str(p.relative_to(R)):sha(p) for p in B.rglob('*') if p.is_file()}))
print('Report, guarded commands and blocked main manifest saved. Frozen implementation unchanged.')
