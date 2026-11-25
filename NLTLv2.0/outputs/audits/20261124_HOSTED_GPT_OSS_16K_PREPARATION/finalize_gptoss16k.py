from pathlib import Path
import json,hashlib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';B=R/'outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_16K_SMOKE_01'
def load(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
main=load(A/'main_manifest.json');assert main['dispatch_ready'];main['prior_exposure']={rid:'Known prior development exposure; additionally used in this GPT-OSS16k smoke. Not held out.' if rid in ['I2-005','IMO-001'] else 'Known prior development exposure. Not held out.' for rid in main['requirements']};write(A/'main_manifest.json',main);mainlock=load(A/'main_freeze_lock.json');mainlock['files'][str((A/'main_manifest.json').relative_to(R))]=sha(A/'main_manifest.json');write(A/'main_freeze_lock.json',mainlock)
setup="""NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_PREP="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION"
NLTL_DEPS="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime"
"""
launch="""#!/bin/bash
set -euo pipefail
"""+setup+"""# MODEL CALLS: only execute when you choose to launch the prepared main experiment.
"$NLTL_PY" -B -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["dispatch_ready"],"MAIN_NOT_READY"; print("Launching fixed shared-start development queue; at most50 inference calls.",flush=True)' "$NLTL_PREP/main_manifest.json"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_PREP/runtime/src:$NLTL_DEPS"
export NLTL_ALLOW_MODEL_CALLS=YES
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
exec "$NLTL_PY" -B -m nltlv2.hosted_pilot --project "$NLTL_ROOT" --manifest outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION/main_manifest.json --run-id 20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01 --allow-model-calls > "$NLTL_PREP/main_dispatch.stdout.txt" 2> "$NLTL_PREP/main_dispatch.stderr.txt"
"""
(A/'launch_main.sh').write_text(launch)
evaluate="""#!/bin/bash
set -euo pipefail
"""+setup+"""# OFFLINE: separate phase; refuses missing dispatch closure or overwriting evaluation.
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_PREP/runtime/src:$NLTL_DEPS"
exec "$NLTL_PY" -B "$NLTL_ROOT/evaluation/evaluate_hosted_shared_start.py" --project "$NLTL_ROOT" --run-id 20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01
"""
(A/'evaluate_main.sh').write_text(evaluate)
verifier='''import os,sys,ssl,socket,requests,pathlib,json,hashlib,time,io,unittest
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';D=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path[:0]=[str(A/'runtime/src'),str(R/'tests'),str(D/'tokenizer_runtime')]
from nltlv2.core import Project,stamp,write
for name,h in json.loads((A/'freeze_lock.json').read_text())['files'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==h,('FROZEN_SOURCE_CHANGED',name)
O=Project(R).output('audits','OFFLINE_GPTOSS16K_'+stamp());os.environ['NLTL_TEST_PROJECT']=str(R)
def deny(*a,**kw):raise RuntimeError('NETWORK_BLOCKED_OFFLINE')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
start=time.monotonic();stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover(str(R/'tests')));(O/'offline_tests.log').write_text(stream.getvalue());summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),network='BLOCKED',model_calls=0,elapsed_seconds=time.monotonic()-start,output=str(O));write(O/'summary.json',summary);print(stream.getvalue()[-1800:]);print(json.dumps(summary));sys.exit(not result.wasSuccessful())
'''
(A/'verify_offline.py').write_text(verifier)
commands='''GPT-OSS v0.11.2 MAIN COMMANDS — PREPARED, NOT LAUNCHED BY AGENT

Path setup (repeat in another terminal when monitoring):
'''+setup+'''
OFFLINE tests — creates a new audit output, never overwrites this smoke:
PYTHONDONTWRITEBYTECODE=1 "$NLTL_PY" -B "$NLTL_PREP/verify_offline.py"
Expected:242 tests,OK,failures0/errors0/networkBLOCKED/model_calls0.

MODEL CALLS — one main-launch command, execute only when you choose:
bash "$NLTL_PREP/launch_main.sh"
Run ID:20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01. Existing output is
refused; no automatic rerun/regeneration. Credentials remain in the external
NLTL_ENV_FILE (established default path); no key/token is printed. Exact main
manifest and all complete actual packets/responses are saved under outputs/experiments.

MONITOR — read-only, in another terminal after repeating path setup:
tail -f "$NLTL_PREP/main_dispatch.stdout.txt" "$NLTL_PREP/main_dispatch.stderr.txt"
For current call count and completed requirements (repeat as needed):
cat "$NLTL_ROOT/outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01/provider/physical_calls.json"
cat "$NLTL_ROOT/outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01/progress.json"
Progress appears after the first requirement; physical_calls updates before every
HTTP request. Closure is printed at completion. Missing files before launch/first
requirement are expected, not a signal to rerun. Candidate/controller/review artifacts
are written in each requirement/arm folder during work.

INDEPENDENT EVALUATION — OFFLINE, only after the dispatch command exits:
bash "$NLTL_PREP/evaluate_main.sh"
The evaluator verifies dispatch_closed=true, zero outstanding client calls, sealed
selection/candidate hashes, frozen source and unchanged input/scope bindings before
execution. It refuses missing closure or an existing evaluation directory. It makes
no provider calls, edits no shapes and reports raw behavior separately from scope-
qualified credit. Results:the main experiment's evaluation/ folder, with selected_results.json,
all_candidate_diagnostics.json,recoveries_regressions.json,evaluation_complete.json.
Expected completion:statusCOMPLETE/model_calls0, with actual scores and NOT_RUN counts.

FIXED LIMITS
Queue seed20261124:TRF-035,IMO-001,TRF-010,I2-004,I2-005. I2-042 deferred.
All five have approved source/schema/research scope and known prior development
exposure; two additionally appeared in the16k smoke. No requirement chosen by score.
Per requirement:one shared generation,at mostone repair/two NLTL candidates,four
primary reviews total/three per candidate,one shared correction per review,two
retrieval rounds. At most50 physical calls,all outputs capped16000 including reasoning;
800000 run output-token reservations. No changed reasoning or other model parameters.
7200second execution budget;180second request timeout;start another requirement only
with at least1920seconds remaining. Stop early on acceptance/terminal outcomes;
ordinary bounded reviewer failures continue; actual infrastructure/integrity stops.
Unstarted entries remain NOT_RUN. Do not fill unused time with new generations.
Local engine checks have no hard process deadline; this is the existing budget guard,
not a guaranteed hard OS walltime. Provider-internal queue/loading/GPU times unavailable.
Published131072 model context and verified supplied-text counts are checked with the
16000 output reservation. Provider-specific context/output ceilings and framing remain
unexposed; no byte ceiling, material-context truncation or provider/model fallback.
The same30 original cases+16 counterparts per arm are evaluated only after closure.
No evaluation fixtures/labels/counterparts/diagnoses enter production requests.
'''
(A/'TERMINAL_COMMANDS.txt').write_text(commands)
report='''HOSTED GPT-OSS16K SHARED-START DEVELOPMENT SMOKE — v0.11.2 — 24 November2026

OPERATIONAL OUTCOME
Both I2-005 and IMO-001 completed under existing frozen policies. Dispatch closed
normally after4 physical inference calls,below20. Shared initial requests,raw outputs
and candidate bytes matched for each pair. No infrastructure/integrity failures,
manual edits,regeneration,preferred-result reruns or implementation changes during
inference occurred. The longer experiment is READY FOR USER LAUNCH and was NOT
launched by the agent. Readiness depends on operational completion,not accuracy.

ONLY TWO AUTHORIZED FIXES
src/nltlv2/transport.py::HostedResponsesTransport.dispatch now returns incomplete
empty-final responses to the existing truncation handler. It never extracts reasoning
as final text or accepts partial reviews. Completed missing-final responses remain
HOSTED_FINAL_OUTPUT_MISSING errors. The existing one shared correction allowance,
call caps and infrastructure/integrity stops are unchanged. No new retry loop.
New hosted configuration sets review_max_tokens16000 for primary review AND its
correction,including reasoning. Generation/repair remain16000. No reasoning effort,
temperature or other model parameter changed. Smoke reservations are now320000
(20*16000);five-requirement main reservations800000(50*16000). These are bounded
settings,not claims of sufficiency. Version metadata changed to0.11.2; no other
production logic,prompt,tracker,scope,ontology,fixture or historical result changed.

OFFLINE VERIFICATION / FREEZE
242 software tests passed with DNS/sockets blocked and0 model calls. Exact previous
truncated raw response bodies were replayed without changing substantive text or
metadata;both partial-final and empty-final incomplete responses reached
TRUNCATED_REVIEW,creating no accepted issues. Generic completed/missing-final,
completed/reasoning-only,conflicting-completed/length and partial-ACCEPT controls
passed. A scripted two-requirement batch used one correction per review at16000,
stopped each with REVIEWER_FORMAT_FAILURE and continued,without authorizing repair.
This is software evidence,not a prediction of live reviewer behavior.
All five initial pairs were captured and matched under the16k setting; supplied-text
plus reserved output counts fit the pinned published131072 context. Provider-specific
limits/full framing remain UNKNOWN;actual counts,margins and raw usage are retained.
No byte guard or silent input truncation.46 unchanged scope/input-construction proofs
were verified separately from model context. freeze_lock.json/runtime pin executed
source and tokenizer resources. Legacy installed distribution metadata0.9.2 is honestly
recorded;explicit PYTHONPATH executes hash-verified frozen0.11.2 source.

I2-005: REPAIR EXERCISED, NO QUALIFYING DELIVERY
One shared initial generation had unbound ex: prefixes;original Turtle parsing failed
at line13. Exact original diagnostic and full candidate were sent through production
syntax_repair. The one repair added only @prefix ex:<http://example.org/ex#>.
Parsing recovered;rechecking then exposed the pre-existing extra global target classes
outside the approved ship population. This is a remaining scope defect,not a newly
introduced constraint change. The existing two-candidate/one-repair bound ended with
ATTEMPT_LIMIT_EXHAUSTED,deliveryNO_VERDICT,final handoffREJECT. Both candidates,
findings,diff and terminal state are retained. No I2-005 live review occurred because
technical checks blocked it. This demonstrates syntax repair/recheck delivery,not a
successful semantic repair or accepted repaired candidate.

IMO-001: COMPLETE REAL REVIEW AND FINAL HANDOFF
One shared initial candidate passed technical/execution checks. A complete real
review response validated candidate/version/hash/request binding and the existing
response/proposal protocol. DecisionACCEPT;issues,change assessments,reconciliations,
unchecked and evidence requests were empty. Final deliveryACCEPTED/final handoff
APPROVE. No repair was triggered. The review used879 output tokens including728
reasoning tokens under the16000 ceiling. It does not demonstrate that16000 suffices
for a complex change review,or that a real16k truncation/correction path succeeds.
Live response correction,retrieval,issue-level property/path/citation proposals,
source-backed semantic repair and change/removal assessment were unexercised;
retained offline controls cover these software safeguards without pretending live proof.

INDEPENDENT EVALUATION AFTER DISPATCH CLOSURE
Same planned denominator per arm:10 original cases+7 unchanged counterparts;0NOT_RUN.
Each arm's selected results:4 correct,1 wrong,5NO_VERDICT;5/10 verdict coverage;
4/5 agreement conditional on a verdict. Strict verified detection0/7:fourI2-005
NO_VERDICT negatives and threeIMO-001 unresolved strict-attribution cases. Three
counterparts accepted out of seven planned,all3/3 on IMO-001. No external score was
used for selection,acceptance or main readiness.
I2-005 Single-shot preserved its exact malformed original,so5 raw execution verdicts
are unavailable. NLTL has no technically qualifying selected shape. Its rejected
syntax-repaired candidate was evaluated separately:raw4/5 agreement,one wrong
positive rejection,scope violations on all5,1/4 counterparts accepted. None of that
rejected diagnostic output receives delivered/admitted credit. Prefix repair restores
executable diagnostics;there was no valid original behavioral verdict for claiming
semantic recoveries/regressions. Scope compliance is separate,never hidden or waived.
IMO-001 shared/accepted candidate is identical in both arms:4/5 agreement,one wrong
valid-positive rejection(IMO-001-P02),all three negative/counterpart pairs observed
correctly but conservative strict attribution remains unresolved. Its unconditional
category/design-condition assertions overconstrain the admitted population. Internal
ACCEPTED/APPROVE is not independent semantic correctness certification. There is no
accuracy-improvement claim or superiority comparison.

TOKENS / PHASE TIMES
4 inference calls;87154 input+6089 output=93243 total tokens. No metadata/provider
probe during this smoke. Generation21.858s(two calls),syntax repair8.194s,review6.489s,
correction0s,technical checks0.540s,total client workflow39.032s. Independent evaluation
30.559s,after closure. Technical time is inside the2.490s nonrequest client remainder,
not an extra disjoint bucket. I2-005 workflow16.616s;IMO-00122.173s. All actual request
sizes,verified text counts,provider usage/status/model metadata and full response
bodies are in actual_calls_sizes_tokens.json and the established experiment folder.
Provider queue/model loading/GPU times are UNAVAILABLE,not zero estimates.

LONGER RUN — PREPARED, NOT LAUNCHED
Fixed seed20261124 queue:TRF-035,IMO-001,TRF-010,I2-004,I2-005;I2-042 deferred. All
have approved source/schema/research scope and known prior development exposure;
I2-005/IMO-001 additionally used here. No choice used generated performance. No
historical shapes,repair solutions,case IDs or evaluation labels enter production.
One fresh generation per requirement is preserved as Single-shot and shared unchanged
with NLTL;at mostone repair/two candidates,four primary reviews/three per candidate,
one shared correction per review,two retrieval rounds. Fifty-call maximum,16000
output tokens per call including reasoning,800000 run output reservations. Same30
original cases+16 counterparts per arm;evaluate separately only after dispatch closure.
Existing7200second budget,180second request timeout,start-next guard1920seconds
remaining are predeclared. Early acceptance/terminal outcomes stop;unstarted items
remainNOT_RUN,not model failures. Local checks have no hard process deadline,so the
guard is not a guaranteed hard OS walltime. No need to use two hours if queue finishes.
Two observed requirements took17–22s and only two requests each. Simple scenario
arithmetic gives~97s for five equally light workflows,~457s for50 requests at observed
mean latency,or~80min request time for the full800k output reservation at observed
aggregate output/client-latency rate. These are workload scenarios,not precise
forecasts:larger sources,full-length reviews,corrections,retrieval,checks and service
variation can dominate. Plan the five-entry queue within approximately two hours;
keep time-guardNOT_RUN outcomes if it does not fit. Do not add repeated generations
to fill unused time. External evaluation/setup/provider-internal timing is separate.

COMMANDS / PRESERVATION
TERMINAL_COMMANDS.txt contains exact offline tests,one launch command,log/progress
monitoring and separate independent evaluation command. launch_main.sh/evaluate_main.sh
are thin terminal conveniences around existing tooling,not another framework. Their
syntax/readiness/frozen-resource checks were verified offline;neither main inference
nor main evaluation was launched. Main output ID is
20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01;existing output is refused.
All prior runs/scores,successfulv0.10.1 repair,MVP,fixtures,ontology,approved scopes,
tracker and17-item retention ledger remain unchanged. Source originals and patch are
saved here;source/candidate/evaluation hashes still match after analysis. No commits,
pushes or model calls after closure. Current summary tables under results/;all raw
smoke requests/responses/candidates/logs under outputs/experiments/.
'''
(A/'REPORT.txt').write_text(report)
(R/'results/hosted_gpt_oss_16k_smoke_20261124.txt').write_text('HOSTED GPT-OSS16K SHARED-START DEVELOPMENT SMOKE — v0.11.2\nOperationally complete;4 inference calls;main prepared,NOT LAUNCHED.\n\nRequirement NLTL outcome                    Real review    Repair\nI2-005      NO_VERDICT / REJECT              Not reached    Prefix fixed;scope still fails\nIMO-001     ACCEPTED / APPROVE               Valid ACCEPT   None triggered\n\nShared-start raw/request/candidate equality:PASS both.\nSelected results per arm:4correct,1wrong,5NO_VERDICT /10 originals.\nVerdict coverage5/10;conditional agreement4/5;strict verified0/7.\nIMO-001-P02 valid-positive rejected despite internal approval.\nRejected I2-005 repair:raw4/5,scope-invalid;diagnostic only,never selected.\nCalls4;input87154/output6089/total93243tokens.\nGeneration21.858s;repair8.194s;review6.489s;checks0.540s;workflow39.032s.\nIndependent evaluation30.559s;provider-internal timing unavailable.\nMain:fixed five requirements,50calls,800koutput reservations,7200sbudget.\nExact commands:outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION/TERMINAL_COMMANDS.txt\n')
shutil.copy2('/tmp/finalize_gptoss16k.py',A/'finalize_gptoss16k.py')
write(A/'artifact_manifest.json',dict(files={str(p.relative_to(R)):sha(p) for p in A.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'},smoke_files={str(p.relative_to(R)):sha(p) for p in B.rglob('*') if p.is_file()}))
print('Ready main commands and report saved. Main experiment NOT LAUNCHED.')
