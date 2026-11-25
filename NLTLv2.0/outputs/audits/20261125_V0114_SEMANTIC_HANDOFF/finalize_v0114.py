from pathlib import Path
import sys,json,hashlib,ast,copy,shutil,difflib,importlib.metadata
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_V0114_SEMANTIC_HANDOFF';B=R/'outputs/experiments/20261125_V0113_IMO001_HOSTED_DEVELOPMENT_DIAGNOSTIC_01';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Project,write
from nltlv2.hosted_pilot import verify
from nltlv2.review_protocol import reviewer_schema
import nltlv2
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):write(A/n,x)
tests=load(A/'verification.json');assert tests['success'] and tests['tests']==282
cfg=Project(R).config('configs/nltl.json');assert cfg['review_contract_version']==4 and cfg['maximum_candidate_attempts']==3
refs={}
def index(nodes,path,prefix=''):
 for n in nodes:
  if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
   key=prefix+n.name;refs[str(path)+':'+key]=n.lineno;index(n.body,path,key+'.')
for p in (R/'src/nltlv2').glob('*.py'):index(ast.parse(p.read_text()).body,p)
save('function_references.json',refs)
# Update the SAME 17 capability IDs in a current ledger, retaining immutable historical ledger.
oldledger=R/'outputs/audits/20261124_FOCUSED_SIMPLIFICATION/retention_ledger.json';ledger=copy.deepcopy(load(oldledger))
updates={
1:('KEEP',['requests.py:repair_request','requests.py:assert_integrity','runner.py:Runner.dispatch'],'Full latest code, exact original diagnostics and resolved evidence integrity reach the SAME generator; current end-to-end software route passes.'),
2:('KEEP',['checks.py:check','checks.py:runtime_probe','requests.py:repair_findings'],'Parser/Meta-SHACL/SPARQL checks unchanged. Current semantic feedback keeps the complete original response diagnostic, not a replacement summary; deterministic diagnostics remain exact.'),
7:('SIMPLIFY',['tracking.py:Tracker.observe','review_validation.py:validate_compact_review'],'Tracker module unchanged. Software derives stable IDs from normalized description and immutable evidence identity, and reconciliation from complete current assessment. Rephrased issues are not assumed equivalent; APPROVE resolution remains a model claim. Prior valid pending findings survive subsequent invalid review.'),
10:('SIMPLIFY',['review_protocol.py:reviewer_schema','review_validation.py:validate_compact_review','evidence.py:extract_location'],'One small live contract: assessment/issues/questions, conditional change/gap review. Software attaches hashes, extracts evidence/code and validates all assertions. Optional asserted quotes retain exact literal checks; no model metadata echoes.'),
11:('SIMPLIFY',['review_validation.py:validate_compact_review','change_review.py:manifest'],'One assessment per request-local change group, covering removal/replacement. Regression links an issue index; supported changes need appropriate evidence. No duplicate removal or prior-reconciliation response lists.'),
12:('KEEP',['requests.py:review_proposal_routing','requests.py:review_conflicts'],'Optional explicit multi-operand property/path/role/unit/datatype proposals reuse unchanged mapping conflict checks; unknown paths/real contradictions remain blocking.'),
13:('KEEP',['runner.py:Runner.review','runner.py:Runner.run','requests.py:review_base'],'Same immutable correction state, one shared correction per review, one technical and one semantic revision, three candidates, four primary reviews, two retrieval rounds, 11 physical calls. No forced repairs/regeneration. Valid prior context is retained on later format failure.'),
17:('REMOVE',['review_protocol.py:reviewer_schema','requests.py:compact_review','core.py:GenerationProject.path'],'Remove required model hash/ID/clause/quote echoes and duplicate reconciliation/removal fields from production responses. Legacy format is restricted to explicit offline regression controls and rejected for live transports; no legacy live fallback or answer-bearing production resource.')}
for row in ledger:
 number=row['item']
 if number in updates:
  rec,specs,evidence=updates[number];row['recommendation']=rec;row['problem_and_evidence']=evidence;row['references']=[]
  for spec in specs:
   file,fn=spec.split(':');p=R/'src/nltlv2'/file;row['references'].append(str(p)+':'+str(refs[str(p)+':'+fn])+' :: '+fn)
 else:
  new=[]
  for ref in row['references']:
   filepart,fn=ref.split(' :: ');rel=filepart.rsplit(':',1)[0];p=R/rel;key=str(p)+':'+fn
   new.append(str(p)+(':'+str(refs[key]) if key in refs else '')+' :: '+fn)
  row['references']=new
 row['verification']='OFFLINE/SCRIPTED v0.11.4: 282 software controls (21 current compact-contract controls plus 261 existing regressions). Latest actual v0.11.3 responses replayed unchanged or in labelled interface projections; zero new model calls or accuracy credit.'
 row['version']='0.11.4'
assert [r['item'] for r in ledger]==list(range(1,18));write(R/'docs/retention_ledger.json',ledger);save('retention_ledger.json',ledger);write(R/'docs/retention_ledger_provenance.json',dict(previous_ledger=str(oldledger.relative_to(R)),previous_sha256=sha(oldledger),current_version='0.11.4',same_capability_ids=True,historical_ledger_unchanged=True))
# Complete representative actual SOFTWARE route, never a regulatory model result.
E=A/'complete_current_handoff';h=load(E/'history.json');req=load(E/'request_003.json');assert req['repair_type']=='semantic';assert req['payload']['previous_candidate']==(E/'candidate_01.ttl').read_text();review=load(E/'review_validated_002.json')
example=dict(label='SCRIPTED_GENERIC_SOFTWARE_EVIDENCE_ONLY_ZERO_WORKFLOW_ACCURACY_CREDIT',workflow_credit=0,provider_calls=0,review_request=load(E/'request_002.json'),review_response=load(E/'response_002.json'),validated_feedback=review,immutable_evidence_map=load(E/'review_packet_002_evidence.json'),complete_revision_request=req,integrity=load(E/'request_003_integrity.json'),revision_response=load(E/'response_003.json'),recheck_review_request=load(E/'request_004.json'),recheck_review_response=load(E/'response_004.json'),candidate_diff=(E/'diff_01_02.patch').read_text(),final_run=load(E/'run.json'))
save('complete_feedback_revision_packet.json',example)
# Freeze tested source/config/resources; no changes to historical frozen copies.
oldlock=load(B/'freeze_lock.json');names={n for n in oldlock['files'] if not n.startswith('outputs/') or '/tokenizer_' in n};names.update(['configs/nltl.json']);names.update(str(p.relative_to(R)) for p in (R/'src/nltlv2').glob('*.py'));lock=dict(version='0.11.4',review_contract_version=4,files={n:sha(R/n) for n in sorted(names)},purpose='OFFLINE_TESTED_PREPARED_ONLY_SINGLE_REQUIREMENT_DIAGNOSTIC');save('freeze_lock.json',lock);verify(R,lock)
for directory in ['src/nltlv2','prompts']:
 for p in (R/directory).iterdir():
  if p.is_file() and p.suffix in ['.py','.txt']:
   dst=A/'tested_implementation'/p.relative_to(R);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
for name in ['pyproject.toml','configs/nltl.json']:
 dst=A/'tested_implementation'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/name,dst)
save('source_identity.json',dict(version=nltlv2.__version__,module=str(nltlv2.__file__),installed_distribution_metadata_version=importlib.metadata.version('nltlv2-refined'),verified_current_modules_and_resources=len(lock['files']),verification='Explicit current src import and production verify(root,lock) passed; metadata version recorded honestly, not substituted.'))
diff=[];changed_source=[]
for p in (A/'before/src').rglob('*.py'):
 relative=p.relative_to(A/'before');q=R/relative
 if sha(p)!=sha(q):changed_source.append(str(relative));diff+=list(difflib.unified_diff(p.read_text().splitlines(True),q.read_text().splitlines(True),fromfile='before/'+str(relative),tofile='after/'+str(relative)))
for rel in ['prompts/reviewer.txt','configs/nltl.json','pyproject.toml']:
 p=A/'before'/rel;q=R/rel
 if sha(p)!=sha(q):diff+=list(difflib.unified_diff(p.read_text().splitlines(True),q.read_text().splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
(A/'implementation.diff').write_text(''.join(diff));save('changed_source_files.json',changed_source)
# Critical retained modules are byte-identical, not replaced with another framework.
unchanged=['tracking.py','checks.py','schema.py','admission.py','activation.py','sparql_analysis.py','sparql_extensions.py','context_resolution.py','source_context.py','transport.py','hosted_pilot.py','core.py','evidence.py']
assert all(sha(R/'src/nltlv2'/n)==sha(A/'before/src/nltlv2'/n) for n in unchanged)
protected=load(A/'protected_before.json');bad=[n for n,h in protected.items() if not (R/n).is_file() or sha(R/n)!=h];assert not bad,bad
inputs=load(A/'replay_input_hashes.json');assert all(sha(Path(n))==h for n,h in inputs.items())
save('preservation_verification.json',dict(original_outputs_results_evaluation_schema_scope_data_files_checked=len(protected),changed=[],replay_inputs_unchanged=True,unchanged_retained_modules=unchanged,tracker_unchanged=True,historical_retention_ledger_unchanged=True,current_same_17_item_ledger='docs/retention_ledger.json',model_calls=0,benchmark_evaluation_reruns=0,all_historical_candidates_scores_preserved=True))
rows=load(A/'latest_response_replay.json');sizes=load(A/'request_size_projection.json');m=load(A/'semantic_repair_diagnostic.prepared.json');assert m['requirements']==['IMO-001'] and not m['dispatch_ready'];assert m['config']['review_contract_version']==4 and m['config']['repair_limits']==dict(technical=1,semantic=1,total=2)
small_example={'assessment':'REJECT','issues':[{'description':'A property path conflicts with the supplied representation.','evidence':['E7'],'location':{'start':12,'end':14},'suggestion':'Use the declared property path and preserve the value/unit constraints.'}],'questions':[]}
save('small_response_example.json',dict(label='GENERIC_INTERFACE_EXAMPLE_NOT_A_REGULATORY_SOLUTION',response=small_example));save('response_schema.initial.json',reviewer_schema())
report=f'''v0.11.4 — focused semantic-feedback handoff simplification (OFFLINE ONLY)

Pipeline remains generator → validation/review feedback → SAME generator revises SHACL → recheck. No agents, new orchestration framework, model calls, benchmark evaluation reruns, tracker edits or new batch. Historical runs/scores/fixtures/scopes and the old retention ledger are preserved. Current 17-item ledger: {R}/docs/retention_ledger.json, derived from the immutable previous ledger with the same item IDs and updated references/evidence/dependencies.

Production response contract

Initial review has only three required fields: assessment (APPROVE | HUMAN_REVIEW_REQUIRED | REJECT), issues[], questions[]. One authoritative schema/description is reviewer_schema() in src/nltlv2/review_protocol.py; contract_shape_errors validates that emitted subset. validate_compact_review resolves evidence/code and builds the server-owned internal findings. prompts/reviewer.txt defers to this schema. Exact file/function/line references are in function_references.json; implementation.diff is reviewable.

A code issue contains description, evidence references, location and actionable suggestion. Location uses start/end, default one-based inclusive lines (characters optional). References are E IDs, optionally text spans; SOURCE/SCHEMA text is extracted exactly, and RDF facts remain whole atomic facts. quote is OPTIONAL, never required; if asserted it must still match the supplied text/terms exactly. Software attaches current candidate/version/hash, exact code, evidence/provenance hashes and the represented clause. It does not invent or correct a model's interpretation.

A context question contains missing, why and retrieval kind (source/schema), optionally evidence and source reference/section. No offending-code location or fabricated defect. Existing bounded Resolver route receives the actual missing-information question as its query. A regulation establishes obligations; declared schema establishes RDF identifiers/paths/units/datatypes; approved scope establishes an external population assumption. A regulation need not literally contain an RDF IRI. A mapping establishes neither a regulatory formula nor a compliance answer. Genuine missing/contradictory mappings stay unresolved. These roles are explicit in the generic prompt and contract; no per-regulation answer was added.

Small generic example (not a regulatory answer):
{json.dumps(small_example,indent=2)}

Only when supplied, change_review is required: one item per short C ID with disposition, reason and evidence; REGRESSION links its zero-based issue index. One item covers removal/replacement, with no duplicate removal list, prior-code quotes or repeated issue description. Previous/current code remains complete in the request. gap_review uses short G IDs; APPROVE must explicitly assess every supplied gap nonmaterial. Material gaps require questions. Optional operand proposals retain explicit property/path/role/unit/datatype checks and genuine conflicts remain blocking.

APPROVE requires no issues/questions, all changes supported and all gaps explicitly nonmaterial. REJECT requires an actionable code issue; material questions still block repair. HUMAN_REVIEW_REQUIRED must describe a question or unresolved change/gap. Unknown fields/references, invalid spans, unsupported citation assertions, partial responses and inconsistent assessments fail; no silent relabelling, quote correction or partial-review acceptance.

Software owns stable issue IDs and prior reconciliation. IDs use normalized description plus immutable evidence identity, not request-local E aliases or model metadata. Complete current APPROVE asserts no prior issue remains (still only a model claim); disappearance during REJECT/HUMAN review is unassessable, not resolution. Paraphrased issues are not assumed semantically equivalent. Tracker itself is byte-identical, retaining regression/repetition/oscillation reporting. Valid earlier questions/findings now survive a later invalid response and stay context-pending in delivery; the v0.11.3 empty-final-findings loss is covered by a new control.

Compatibility is explicit: the previous format/parser remains only for offline regression controls, with a labelled offline contract setting. Live transports reject that setting. There is ONE production contract, v4, no legacy live fallback. Old response strings are not automatically accepted as v4 or rewritten into successful model outcomes.

Actual latest-response replay

Inputs: {B}/provider actual requests/responses and candidate, not templates. All three raw old responses are incompatible with the new response shape and are retained unchanged. latest_response_replay.json records their original hashes and exact compatibility errors, plus strict interface-only projections with ZERO workflow/accuracy credit. Projections preserve descriptions, expected claims, suggestions, asserted quotations, material questions, locations and proposals; software-owned echoes and duplicate reconciliation metadata are removed. Prior-assessment prose is retained in the description, not silently discarded.

• Call 2: projected interface validates, but remains CONTEXT-PENDING and cannot authorize repair. Its claim that regulation must prescribe the RDF individual is not proved by citation validity; the mapping was already supplied. New explicit role instructions address this misunderstanding, without claiming a new model success.
• Call 3: original 11 failures become 3 projection failures: INVALID_SOURCE_QUOTATION, UNSUPPORTED_SCHEMA_EVIDENCE and consequently UNSUPPORTED_CODE_ASSERTION (no usable support survives). The line-break-normalized legal quotation and RDF triple asserted against a SCHEMA_TEXT record remain invalid. Reconciliation-field/state bureaucracy disappears; assertions do not get repaired.
• Call 4: original 12 failures become 4 projection failures: the same three plus DECISION_ISSUE_CONTRADICTION. HUMAN_REVIEW_REQUIRED with only a code issue and no actual context question/unresolved item is still inconsistent. Proposed local/prefixed paths are preserved; failures stop before proposal routing, so no path is silently corrected or accepted.

These are offline interface projections, not counterfactual live workflow results. None authorizes a historical repair or promotes a candidate. Literal errors remain justified because the old model DID assert those quotes; future v4 responses need only cite references and let software extract text. Natural-language entailment, missing-obligation detection and correction quality are NOT proved by software identity checks.

Feedback → same-generator revision

Current compact feedback is normalized into the existing candidate-bound Finding format only after full validation. The existing targeted_repair route uses the SAME configured generator model, full latest SHACL, original exact diagnostics (including the complete new compact-review response), exact affected code and correction guidance. Resolved evidence references carry text/provenance hashes and spans into the supplied catalog, where the exact source text appears once; integrity checks re-extract and verify it. Full resolved text is also preserved in validated-feedback artifacts. No failed review becomes prior state or revision permission.

Complete representative artifact: {A}/complete_feedback_revision_packet.json. It contains the full review request/response, server-resolved evidence/locations, immutable evidence map, full revision request and integrity record, revision response/diff and recheck/review. The underlying complete_current_handoff folder preserves every candidate/request/response. This uses a synthetic boolean/cardinality software source, NOT a regulatory compliance witness or production input: one scripted semantic revision, then recheck/approval, four logical scripted dispatches, zero provider calls and zero workflow-accuracy credit.

Bounds and delivery

Unchanged ceilings: generation once; at most one technical plus one semantic code revision, three candidates total, four primary reviews total (three per candidate), one SHARED response correction per review, two retrieval rounds and 11 physical calls including generation/revisions/corrections. No regeneration, forced repair or hidden extra slot. Early approval stops. Genuine missing context stays pending. A semantic revision's technical failure uses only a still-unused declared technical slot; otherwise preserve the failure and apply latest-technically-qualifying delivery. Delivery ACCEPTED/UNVERIFIED/NO_VERDICT remains separate from reviewer approval; context-pending leads to HUMAN_REVIEW_REQUIRED. Usage, timings, original diagnostics, all candidates/diffs and transitions remain recorded.

Verification, sizes and preservation

282 tests pass: 21 new current-contract controls plus 261 existing regressions (including explicitly offline legacy-format controls). Networking blocked; zero model calls and zero benchmark evaluation reruns. Controls cover complete same-generator revision, original diagnostics/evidence delivery, immutable retry, no partial acceptance, context-only questions, retained pending state, false quotes/RDF lexical identity, invalid locations/unknown IDs, whole RDF facts, change/gap review, path/operand roles, both repair slots, exhausted limits, early approval and no hidden extra repair. This is SOFTWARE evidence, not model accuracy.

Actual-before → offline-projected request bytes, same candidate/context: call 2 {sizes[0]['before_bytes']:,}→{sizes[0]['after_projected_bytes']:,}; call 3 {sizes[1]['before_bytes']:,}→{sizes[1]['after_projected_bytes']:,}; correction {sizes[2]['before_bytes']:,}→{sizes[2]['after_projected_bytes']:,}. Initial response schema {sizes[0]['before_schema_bytes']:,}→{sizes[0]['after_schema_bytes']:,} bytes. Material source/schema context and latest code are retained. These are projections, not actual provider traffic. Cached pinned tokenizer counts plus 16,000 output fit the retained 131,072 known model capacity; provider framing/deployed tokenizer/lower service limits remain unexposed. No arbitrary byte blocker, truncation, model fallback or reasoning-setting change.

Checks/schema/admission/activation/SPARQL/quantity/ontology/retrieval/source-selection/transport/shared-start driver/evaluator boundaries remain unchanged, as does tracker.py. preservation_verification.json verifies historical files, approved scopes and replay inputs; source_identity.json and freeze_lock.json identify the tested current implementation. Before-source snapshots and the historical 17-item ledger remain immutable.

Prepared, UNDISTPATCHED diagnostic

semantic_repair_diagnostic.prepared.json: IMO-001 only, previously exposed and explicitly not held out. FRESH shared-start generation; original preserved as one-call Single-shot, NLTL starts from identical bytes and empty prior issues. Existing approved source/schema/scope only; no old candidate, review, diagnosis, repair solution or evaluation fixture/label in production inputs. Existing evaluator may run only after closure on the same five cases/three counterparts, with approval/scope/delivered behavior/strict attribution separate. No new batch or experiment study.

GPT-OSS hosted endpoint/model unchanged; review/correction and generation/revision max_output_tokens 16,000 including reasoning. Maximum 11 calls, 176,000 reserved output tokens, configured 600-second window, 180-second request timeout and 540-second start reserve. Source/config/resources frozen. dispatch_ready=false and prepared_only=true: the existing driver refuses dispatch before provider construction. No model calls are authorized or performed by this task. Early approval or context-pending is a legitimate outcome; unexercised semantic repair must be reported NOT_EXERCISED, never forced or rerun for a preferred result.
'''
(A/'REPORT.txt').write_text(report)
for path in ['/tmp/verify_v0114.py','/tmp/replay_v0114.py','/tmp/finalize_v0114.py']:
 shutil.copyfile(path,A/Path(path).name)
save('artifact_manifest.json',{str(p.relative_to(A)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(A.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts})
print(json.dumps(dict(report=str(A/'REPORT.txt'),tests=tests['tests'],production_contract=4,projection_failures=[len(r['projection_errors']) for r in rows],packet_bytes=[(s['before_bytes'],s['after_projected_bytes']) for s in sizes],protected_historical_files=len(protected),ledger_items=len(ledger),source_frozen_files=len(lock['files']),dispatch_ready=m['dispatch_ready'],model_calls=0),indent=2))
