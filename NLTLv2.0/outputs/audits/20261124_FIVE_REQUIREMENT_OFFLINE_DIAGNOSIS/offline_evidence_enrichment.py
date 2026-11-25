import pathlib,json,hashlib,shutil
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');O=R/'outputs/audits/20261124_FIVE_REQUIREMENT_OFFLINE_DIAGNOSIS'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
from rdflib import Graph
from rdflib.namespace import SH
from nltlv2.evidence import literal_identity
rows=load(O/'strict_attribution_completed.json');cache={}
for row in rows:
 key=row['candidate']['file']
 if key not in cache:
  with literal_identity():g=Graph().parse(R/key)
  cache[key]=dict(select_queries=[str(x) for x in g.objects(None,SH.select)],literal_has_values=[x.n3() for x in g.objects(None,SH.hasValue)],candidate_sha256=sha(R/key))
 row['actual_candidate_constraints']=cache[key]
 with literal_identity():a=Graph().parse(R/row['original_fixture']['file']);b=Graph().parse(R/row['counterpart_fixture']['file'])
 row['exact_intended_only_graph_edits']=dict(removed=sorted(' '.join(v.n3() for v in t) for t in set(a)-set(b)),added=sorted(' '.join(v.n3() for v in t) for t in set(b)-set(a)))
write(O/'strict_attribution_completed.json',rows)
shared=load(O/'shared_start_design.proposed.json');shared['implementation_readiness']='Design only. Current Runner.run/CLI independently generates; launching both ordinary CLIs would NOT implement shared-start. A future small orchestrator must hand the one fresh raw/candidate artifact to existing assess_candidate/review/repair routes, or explicitly record cached initial delivery, with shared_call_id and physical versus logical accounting. No historical continuation driver, new framework or wrapper is installed now.';write(O/'shared_start_design.proposed.json',shared)
local=load(O/'triton_gpt_oss_pilot.proposed.json');local['future_read_only_checks_not_executed']=['Confirm activated account, correct Aalto username, VPN/jump route and project association.','On the documented code host: slurm partitions; module spider scicomp-llm-env; module show model-huggingface; quota.','List the exact openai/gpt-oss-120b snapshot already present in the shared HuggingFace cache; verify tokenizer/Harmony cache presence without triggering downloads.','Inspect installed vLLM/torch/CUDA versions and allowed QOS/time/CPU/RAM/GPU requests; do not infer support from model-name equality.'];write(O/'triton_gpt_oss_pilot.proposed.json',local)
summary='''OFFLINE PILOT DIAGNOSIS AND NEXT-TEST PROPOSAL

The main loss was review/context-gate coverage, not execution failure. Every NLTL NO_VERDICT candidate passed parse/structure/local runtime checks. I2-004 stopped after an invalid clause identifier and then10 unassessed context gaps; I2-005 had a real numeric-term defect but incompatible root/local proposal paths stopped repair; TRF-010 had retained clause text but unresolved reference identity, then a no-novelty retrieval stop. These are different failure types; none was infrastructure/integrity failure or confirmed engine failure.

There was only one revision: TRF-035v1->v2. It removed canonical-name checker errors on administrative constraint/prefix nodes; all10 saved input verdicts stayed identical. No measured functional repair or regression occurred. The other four NLTL candidates were never revised.19 missing selected-output case verdicts are acceptance-gate coverage loss. Independent-generation Single-shot candidates cannot serve as NLTL's initial-candidate baseline.

Source/code/report adjudication of the existing exact pairs completes strict attribution: Single-shot11/16 verified intended detections,2 misses,3 additional-failure pairs; selected NLTL5/16 verified,2 misses,9 NO_VERDICT. Every row links the saved constraint/query, original/counterpart hashes and graph edits, source clause and violation report. No execution, label or old score was rerun/rewritten. This is finite-case attribution, not proof of whole-shape correctness or real-vessel compliance. Accepted IMO-001 still implements the wrong implication direction for two negatives. Both I2-005 candidates still reject numeric7.0 through lexical hasValue7.

Alternative policy, NOT implemented: choose the highest version with declared technical checks and intact provenance, independently of external scores. Deliver ACCEPTED only with valid bound acceptance; otherwise UNVERIFIED plus all warnings, semantic findings, context uncertainty, invalid-review diagnostics and the exact stop reason. Do not turn invalid reviews into accepted issues or repair permission. Unknown technical safety produces no technical output. Keep infrastructure/resource interruption as a separate workflow outcome; an intact earlier technical artifact may be delivered UNVERIFIED, but integrity-invalid artifacts cannot be returned as trusted outputs. No final-attempt leniency.

Retrospective observation of that rule:2 ACCEPTED+3 UNVERIFIED outputs,27/30 original-case agreement rather than9 correct/2 wrong/19 NO_VERDICT under accepted-only. It adds18 correct deliveries and1 wrong delivery. This is increased delivery coverage, not increased verification; historical selections remain unchanged.

Minimal changes to consider later: explicit root/local path frames and a distinction between context questions and concrete edits; reuse the existing shared correction allowance rather than hard-conflicting on demonstrably inconsistent reviewer metadata. Supply exact required-gap IDs and resolve body-section identity by document/edition/hash/offset rather than TOC matches. Exempt only genuinely administrative SHACL resource names from regulatory identifier checks. Preserve all ledger safeguards, budgets, immutable retries and genuine contradiction/integrity stops. Do not add maritime solution profiles or hardcode the numerical answers. No change was made here.

New design label: SHARED_START_REFINEMENT_DEVELOPMENT. Generate once per requirement; seal that output as Single-shot and give its exact raw/candidate bytes to NLTL. Count the shared physical call once, retain all revisions, and evaluate only after closure. Current ordinary CLI pairs do not implement this; a small future orchestration/accounting decision is needed. Five requirements would use<=50 physical calls at current bounds. This is distinct from the completed ten-independent-generation pilot.

Bounded local-model proposal: use openai/gpt-oss-120b native MXFP4 for two predeclared requirements,I2-005 and IMO-001, one shared start each,<=20 total physical calls,<=2 repairs and<=4 candidates. Keep four primary reviews/requirement,one shared correction/review,two retrieval rounds,16000/4000 output caps. Proposed budget:one full x86 H200141GB,8 CPU,128GiB RAM,150GiB free scratch,one hour maximum subject to actual QOS. Model context is131072 input+output tokens; exact Harmony/tokenizer fit is a gate, never silent source/candidate truncation. No models, tokenizers or jobs were downloaded/launched.

Existing GPT-OSS config is a hosted Aalto API configuration with old retry behavior, not evidence of Triton access. Current Aalto docs verify code.triton host guidance, GPU Slurm requirements,H200 resources,shared cache/modules; active account/project,QOS,cache snapshot,runtime/kernel/API compatibility and exact token fit remain unverified. Local Responses/Harmony final-text/error/usage compatibility must be checked before a future adapter decision. No adapter changed.

Record queue wait,environment setup,model loading,per-request inference/RPC,review/repair,retrieval/checks,total workflow,GPU allocation and external evaluation separately. No Triton times exist yet:all are null. Hosted provider RPC latency is not pure GPU inference. Public documentation URLs and timestamped verification limits are in triton_documentation_verification.json.

Implementation,17-item ledger,source/schema/scope,tracker,fixtures,historical results and selections remain unchanged. All new analysis is isolated here; no model calls or evaluation reruns were made.
'''
(O/'SUMMARY.txt').write_text(summary)
shutil.copy2('/tmp/nltl_enrich_offline_diagnosis.py',O/'offline_evidence_enrichment.py')
before=load(O/'protected_before.json');changed=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h];assert not changed,changed
pres=load(O/'preservation_verification.json');pres['final_check']='PASS_AFTER_SOURCE_CODE_REPORT_TRACE_ENRICHMENT';write(O/'preservation_verification.json',pres)
write(O/'artifact_manifest.json',{str(f.relative_to(O)):sha(f) for f in O.rglob('*') if f.is_file() and f.name!='artifact_manifest.json'})
print(json.dumps(dict(summary=str(O/'SUMMARY.txt'),strict_pairs=len(rows),candidate_constraint_traces=len(cache),protected_existing_files=len(before),modified_existing_files=0,model_calls=0,pipeline_edits=0),indent=2))
