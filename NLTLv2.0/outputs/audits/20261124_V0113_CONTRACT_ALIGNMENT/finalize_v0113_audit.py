from pathlib import Path
import sys,json,hashlib,ast,difflib,shutil,importlib.metadata
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_V0113_CONTRACT_ALIGNMENT';B=R/'outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01';OLD=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION/information_flow_audit_20261124';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Project,write
from nltlv2.hosted_pilot import verify
import nltlv2

def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):write(A/n,x)
assert load(A/'offline_verification.json')['success']
# Configuration check, not generation/evaluation.
config=Project(R).config('configs/nltl.json');assert config['maximum_candidate_attempts']==3 and config['repair_limits']==dict(technical=1,semantic=1,total=2)
# Consolidate a COMPLETE generic software example, not an adapted historical model result.
E=A/'scripted_technical_semantic_example';history=load(E/'history.json');example=dict(label='SCRIPTED_GENERIC_SOFTWARE_EVIDENCE_ONLY_NO_WORKFLOW_CREDIT',real_model_calls=0,workflow_credit=0,source='Synthetic boolean/cardinality requirement NOVEL-RULE in temporary software-test project; not a regulation or production input',candidate_version=2,candidate_sha256=history[1]['sha256'],review_request=load(E/'request_003.json'),review_response=load(E/'response_003.json'),validated_review=history[1]['review'],representation_validation=load(E/'reviewer_proposal_validation_003.json'),semantic_findings=history[1]['findings'],repair_request=load(E/'request_004.json'),repair_integrity=load(E/'request_004_integrity.json'),repair_response=load(E/'response_004.json'),after_candidate_sha256=history[2]['sha256'],recheck_and_review=history[2],run_summary=load(E/'run.json'))
assert example['repair_request']['repair_type']=='semantic' and example['repair_request']['payload']['candidate_sha256']==example['candidate_sha256'];assert example['repair_request']['payload']['previous_candidate']==(E/'candidate_02.ttl').read_text()
save('complete_semantic_handoff_example.json',example)
# Snapshot and freeze exactly the current source/resources. Old frozen outputs untouched.
oldlock=load(B/'freeze_lock.json');names={n for n in oldlock['files'] if not n.startswith('outputs/') or '/tokenizer_' in n};names.update(str(p.relative_to(R)) for p in (R/'src/nltlv2').glob('*.py'));names.update(['configs/nltl.json'])
lock=dict(version='0.11.3',files={n:sha(R/n) for n in sorted(names)},purpose='TESTED_OFFLINE_FROZEN_IMPLEMENTATION_FOR_PREPARED_ONLY_DIAGNOSTIC',no_model_calls=True)
save('freeze_lock.json',lock);verify(R,lock)
for directory in ['src/nltlv2','prompts']:
 for p in (R/directory).glob('*'):
  if p.is_file() and p.suffix in ['.py','.txt']:
   dest=A/'tested_implementation'/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
for name in ['pyproject.toml','configs/nltl.json']:
 dest=A/'tested_implementation'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/name,dest)
try:installed=importlib.metadata.version('nltlv2-refined')
except importlib.metadata.PackageNotFoundError:installed=None
save('source_identity.json',dict(source_module=str(Path(nltlv2.__file__).resolve()),source_version=nltlv2.__version__,pyproject_sha256=sha(R/'pyproject.toml'),installed_distribution_metadata_version=installed,verification='Production verify(root,lock) passed for every module and locked resource. Prepared dispatch must use explicit current src PYTHONPATH; installed distribution metadata is recorded, not substituted.',frozen_files=len(lock['files'])))
refs={}
for p in (R/'src/nltlv2').glob('*.py'):
 for node in ast.walk(ast.parse(p.read_text())):
  if isinstance(node,(ast.FunctionDef,ast.ClassDef)):refs[str(p)+':'+node.name]=node.lineno
save('function_references.json',refs)
diffs=[]
for p in sorted((A/'before').rglob('*')):
 if p.is_file():
  relative=p.relative_to(A/'before');current=R/relative
  if sha(p)!=sha(current):diffs.extend(difflib.unified_diff(p.read_text().splitlines(True),current.read_text().splitlines(True),fromfile='before/'+str(relative),tofile='after/'+str(relative)))
(A/'implementation.diff').write_text(''.join(diffs))
# Previously generated results, all source/schema/scope data and old audit remain immutable.
before=load(A/'protected_before.json');changed=[n for n,h in before.items() if not (R/n).is_file() or sha(R/n)!=h]
inputs=load(A/'replay_input_hashes.json');input_changed=[n for n,h in inputs.items() if not Path(n).is_file() or sha(Path(n))!=h]
legacy=load(OLD/'input_hashes.json');legacy_changed=[n for n,h in legacy.items() if not Path(n).is_file() or sha(Path(n))!=h]
assert not changed and not input_changed and not legacy_changed,(changed,input_changed,legacy_changed)
save('preservation_verification.json',dict(original_outputs_results_evaluation_schema_data_files_checked=len(before),changed=changed,original_audit_inputs_checked=len(legacy),original_audit_inputs_changed=legacy_changed,replay_inputs_checked=len(inputs),replay_inputs_changed=input_changed,model_calls=0,benchmark_evaluation_reruns=0,tracker_changes=0,retention_ledger_unchanged=True,verification='SHA256 against implementation-task entry and prior read-only audit input index; old historical source snapshots and all actual responses unchanged. Active implementation changes are intentional and separately diffed.'))
replays=load(A/'historical_review_replay.json');packet_sizes=load(A/'same_context_packet_sizes.json');initial_sizes=load(A/'initial_context_size_changes.json');tests=load(A/'offline_verification.json');m=load(A/'semantic_repair_diagnostic.prepared.json');assert m['dispatch_ready'] is False and m['requirements']==['IMO-001'];assert m['start_requirement_reserve_seconds']<m['max_execution_seconds']
assert all(not r['after_capacity']['exceeds_known_token_limit'] for r in packet_sizes)
aggregates={route:dict(before=sum(x['before_provider_bytes'] for x in packet_sizes if x['route']==route),after=sum(x['after_projected_provider_bytes'] for x in packet_sizes if x['route']==route)) for route in ['review','review_format_retry','targeted_repair']}
save('size_accounting_summary.json',dict(label='OFFLINE_SIZE_PROJECTIONS_NOT_PROVIDER_TRAFFIC',same_saved_candidate_and_context_by_route=aggregates,all_primary_clauses_preserved=all(r['primary_clause_preserved'] for r in initial_sizes),all_schema_facts_quantities_scope_unchanged=all(r['schema_terms_unchanged'] and r['ontology_facts_unchanged'] and r['quantity_encoding_unchanged'] and r['scope_unchanged'] for r in initial_sizes),maximum_projected_supplied_text_tokens=max(r['after_capacity']['supplied_text_tokens'] for r in packet_sizes),output_reservation_per_request=16000,known_model_context_tokens=131072,provider_framing_and_lower_provider_limit='UNEXPOSED; exact supplied text count under pinned public encoding, not full provider input count',silent_truncation=False))
report=f'''Implemented v0.11.3 — focused review-contract and semantic-repair opportunity correction

No model calls, benchmark evaluation reruns, tracker changes or historical edits. {tests['tests']} software controls pass, zero failures/errors, with networking blocked. All saved responses were replayed unchanged; no historical output was promoted. This is software verification, not new workflow-performance evidence.

Contract and implementation

The authoritative response contract lives in {R}/src/nltlv2/review_protocol.py: category/authority constants, claim_required fields, claim_basis(), decision_contract_errors(), reviewer_schema(), and its generated description. prompts/reviewer.txt defers state/field rules to that description instead of repeating incompatible instructions. Runtime review_validation.py::validate_review uses the same authority/decision rules. The contract is rendered ONCE in expected_response_schema.description, not duplicated in a second instruction catalog. Exact file/function lines are in function_references.json; implementation.diff records before/after source changes.

• Optional evidence-request reference may be omitted/null. A supplied reference must be a nonempty bounded string; availability/edition are checked by the resolver, not invented by the format checker. Without a reference, Resolver.resolve searches only supplied/approved catalog documents under the existing document, lookup, passage, depth and round bounds. Missing/ambiguous evidence stays explicit. This does not waive citation requirements for claims.
• UNRESOLVED_CONTEXT issues and MISSING_INFORMATION/UNRESOLVED context assessments require supplied evidence and an explanation, but no invented offending code span or regulatory quotation. A context-only issue can omit/null candidate_location; an asserted stale/invalid location still fails. Material unchecked context alone can justify UNRESOLVED. It never establishes a repairable defect, support for a change or acceptance. CONTEXT cannot mark an assessment REPAIRABLE_CODE or a change SUPPORTED/REGRESSION.
• SOURCE_BACKED_LOGIC_ERROR keeps exact primary source_clause, supplied SOURCE ID, exact whitespace-preserving quotation, supporting evidence and a current code anchor. New TECHNICAL_REPRESENTATION_ERROR issues, or change/reconciliation assessments explicitly marked claim_basis=TECHNICAL, cite supplied SCHEMA_TEXT/RDF_FACT/CALLER_DECLARATION evidence. Technical code/change claims still need current/previous locations as applicable. A technical label cannot convert a regulatory issue category into a technical one; contradictory authority fields fail. Every asserted SOURCE citation is checked even when optional.
• ACCEPT requires no issues, material uncertainty, pending evidence requests or unresolved changes, supported changes and resolved prior issues. It requires an explicit material=true/false assessment for EVERY supplied retrieval-gap ID. Other decisions may report relevant gaps. REJECT requires an actionable regulatory/technical code issue. UNRESOLVED needs explicit context uncertainty, material unchecked scope, a pending request or unresolved change. Pending UNRESOLVED changes may accompany REQUEST_EVIDENCE without an invented code defect; REGRESSION still requires a linked actionable issue.
• Correction feedback now includes the exact rejected response once, as explicitly non-authoritative material, plus every validation error. Wrong-kind errors report the failing ID rather than the quotation. Candidate, evidence, request binding and original prior issues remain immutable; the shared correction allowance is unchanged.

Retained safeguards: local immutable evidence/provenance hashes; exact RDF lexical/datatype/language identity; SOURCE kinds/quotations; candidate/version/hash and code spans; property/path/operand pairing; activation/reachability/deactivation; Meta-SHACL and actual execution; exact original diagnostics; full latest code in repairs; supported change/removal review; stable issues/regressions/repetition; bounded retrieval/calls/timeouts; paired shared-start bytes; one-call original Single-shot; generation/evaluation filesystem separation and dispatch-closure checks. Citations validate identity, not entailment. There is still no automatic proof that a natural-language interpretation is correct; technical authority is not blanket permission to remove constraints.

Replay of ALL saved main-run reviews and corrections

Requirement | Original errors → corrected-contract errors (review / correction) | Alignment effect | Remaining failure or non-accepting state
--- | --- | --- | ---
TRF-035 | 4→4 / 2→2 | No response rewrite or new permission | RDF label cited as SOURCE; wrong primary-clause strings; UNRESOLVED without context uncertainty. Target-loss assertion/missing-comment complaint is not accepted repair feedback.
IMO-001 | 4→4 / 1→0 | Optional source reference no longer rejects correction | Original issue still has wrong clause/kind and missing supporting citation. Correction is a VALID REQUEST_EVIDENCE only, not approval or repair. Asking for an already supplied definition remains unnecessary; proposed targeting remedy is not validated.
TRF-010 | 12→12 / 2→0 | Material unchecked gaps can express context-only UNRESOLVED without fake code issue | Initial ACCEPT still omits 12 required gap assessments. Correction is VALID CONTEXT-PENDING, with gap materiality unresolved; no repair permission.
I2-004 | 5→2 / 5→2 | Remove optional-reference and pending-change/decision contradictions | Original change/removal still cites RDF_FACT as SOURCE; correction still asserts a non-exact quotation. Wrong authority question is not relabelled, and no maximum-selection solution is supplied.
I2-005 | 13→13 / 5→2 | Context-only UNRESOLVED/unresolved-change no longer requires an invented code issue | ACCEPT still omits 13 gap assessments; correction still cites RDF_FACT as SOURCE for change/removal. No automatic technical reclassification.

Total: 53→41 errors (12 policy/interface errors removed); two of ten responses now validate only as pending context, zero accepted candidates and zero repair-authorizing historical reviews. historical_review_replay.json preserves both error lists, original response hashes, removed-error correspondence and zero-credit labels. Replay pins each ORIGINAL immutable evidence catalog/binding in an offline adapter because repacking changes request-local E aliases. It does not rewrite response metadata, quotes, claims, code locations or decisions. Production validation still recomputes bindings/catalogs and exposes no catalog-injection option. No historical findings enter a new production tracker.

Context changes and request sizes

source_context.py::contents_entry/scope_heading/select_document removes demonstrated TOC/reference and table-caption false positives: a table titled “Definition of loads” no longer becomes a global definitions section. Explicitly referenced tables remain included. The conservative original scope/application vocabulary, primary anchor, parents, genuine definition/application context, material explicit references and full supporting-source fallback remain. Complete omitted sections stay retrievable with document/span hashes; there is no material-context truncation or regulatory answer profile.

evidence.py::evidence_catalog removes ontology_triples from retrieval-status JSON ONLY when the exact triples already exist in supplied ontology_evidence. Unique retrieval facts and all source/schema/representation metadata remain. This avoids the demonstrated second copies without deleting ontology individuals or manufacturing facts.

Fresh generation renderings, identical settings, before→after bytes: TRF-035 162,257→146,530; IMO-001 74,648→74,648; TRF-010 147,940→132,213; I2-004 48,663→48,663; I2-005 47,553→47,553. Primary clauses, schema term/fact inventories, quantity encoding and approved scope match exactly. Each TRAFICOM selection removes 7,962 initially selected source characters; whole sections remain retrievable and uncertainty explicit. These are offline renderings, not fresh generations.

Holding SAVED candidate and context fixed, aggregate actual-before→projected-after provider bytes: primary reviews {aggregates['review']['before']:,}→{aggregates['review']['after']:,}; corrections {aggregates['review_format_retry']['before']:,}→{aggregates['review_format_retry']['after']:,}; three technical repairs {aggregates['targeted_repair']['before']:,}→{aggregates['targeted_repair']['after']:,}. Some smaller categorical packets GROW because the conditional contract and exact rejected response are explicit; do not infer that every request shrinks. Technical repair packets have no retrieval-status duplication to remove and are unchanged. same_context_packet_sizes.json contains all 13 per-call rows, dedup-only effects, complete projected packets and token counts; initial_context_size_changes.json contains all five initial packets/manifests. Correction envelopes are labelled size projections, not delivered historical feedback or workflow credit.

All projected supplied-text+16,000-output lower bounds fit the retained 131,072 model-context capacity under the pinned cached o200k_harmony counter. Maximum supplied-text count: {max(r['after_capacity']['supplied_text_tokens'] for r in packet_sizes):,}. Provider framing, deployed tokenizer revision and any lower provider limit remain unknown. No arbitrary byte dispatch guard, silent truncation or provider fallback is introduced. Reviewer/correction max_output_tokens remains 16,000 including reasoning in the prepared GPT-OSS profile; other reasoning/model parameters are unchanged.

Repair and call bounds

Runner.run hard-bounds three candidates: generation plus at most ONE technical and ONE semantic code revision, two revisions TOTAL, in either necessary order. This reserves an opportunity, not a forced call. Deterministic disqualification routes to the technical slot; validated actionable review feedback on technically qualifying code routes to the semantic slot. Failed/context-only reviews never create repair state. Repeated technical or semantic failure cannot borrow the other type's slot. Early acceptance stops immediately. If a semantic revision introduces a technical error, only a still-unused declared technical slot may be used; otherwise the error remains and latest_technical delivery applies. No regeneration or hidden extra attempt.

At most four primary reviews total, three per candidate, one SHARED response correction per review, two retrieval rounds. Worst case per shared-start pair: 1 generation + 2 code revisions + 4 reviews + 4 corrections = 11 physical calls, including the unchanged Single-shot generation shared with NLTL. Lower configured provider/candidate limits still apply. New results record repair_counts, repair_limits, per-candidate/request repair_type, route counts, effective review/provider/candidate limits, usage totals, request latency and workflow/check elapsed time. Real provider usage/raw responses remain preserved; scripted zeros are not cost measurements.

Complete packet example and verification

complete_semantic_handoff_example.json contains the FULL rendered review request, raw response, validated issue/code locations, semantic findings, FULL repair request, integrity record, repair response and recheck/review. The underlying scripted_technical_semantic_example preserves every candidate, diff, request, response and transition: malformed generation→technical repair→grounded semantic issue→semantic repair→recheck/acceptance. It uses a synthetic NOVEL-RULE boolean/cardinality source in software tests, never a regulatory solution or production input. Five logical scripted calls, zero real provider calls and ZERO workflow credit. Other controls exercise exhausted correction/repair slots, stale ranges, false citations, context-only uncertainty, technical evidence, optional reference retrieval, duplicate/unique facts, source selection and delivery after an erroneous semantic revision.

261 tests pass; networking blocked; no benchmark evaluation rerun. offline_tests.log and offline_verification.json contain results. Existing software tests were updated only for the requested two-slot policy, context/decision contradiction handling and conditional schema; no regulatory fixtures, ontology or approved scope changed. Source identity and freeze_lock.json verify all current modules/resources; tested_implementation is the preserved tested-source snapshot. preservation_verification.json checks all original outputs/results/evaluation/schema/data and the prior audit's historical inputs, including the retention ledger. implementation.diff and function_references.json make changes reviewable.

Prepared only: small GPT-OSS diagnostic

semantic_repair_diagnostic.prepared.json selects IMO-001 ONLY, with its existing approved scope and current source/schema. Prior exposure is explicit; this is not held out or a new five-requirement batch. One fresh generation, preserve that exact original as Single-shot, NLTL begins with identical bytes and empty prior issues; no saved shape, failed review, known diagnosis or repair solution is imported. Source-only initial payload is new_initial_packets/IMO-001/provider_payload.json.

Limits: 11 physical calls including generation/repairs/corrections; 176,000 reserved output tokens; 600-second configured dispatch window; 180-second request timeout; start reserve 540 seconds; the repair/review/retrieval bounds above. Same unchanged five IMO cases and three counterparts per arm are planned ONLY for independent evaluation after dispatch closure; these counts/resource references live in evaluation_plan.not_model_input.json and are not model inputs. Rejected/error candidates and unfinished outcomes stay artifacts; delivery is latest technical ACCEPTED/UNVERIFIED, or NO_VERDICT if none qualifies. Untriggered semantic repair must be reported NOT_EXERCISED. Provider-internal timings remain unavailable; client usage/latencies/check/workflow/evaluation timing stay separate.

The manifest has dispatch_ready=false, prepared_only=true and no dispatch authorization. Production hosted_pilot.verify(root,lock) passes; the existing production driver would refuse this prepared manifest before provider construction. A future explicit authorization and frozen-source verification are required. Nothing has been dispatched, and no longer experiment was prepared or launched by this change.
'''
(A/'REPORT.txt').write_text(report)
for path in ['/tmp/verify_v0113_offline.py','/tmp/replay_prepare_v0113.py','/tmp/finalize_v0113_audit.py']:
 shutil.copyfile(path,A/Path(path).name)
save('artifact_manifest.json',{str(p.relative_to(A)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(A.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json' and '__pycache__' not in p.parts})
print(json.dumps(dict(report=str(A/'REPORT.txt'),tests=tests['tests'],replayed=len(replays),errors_before=sum(len(x['before_errors']) for x in replays),errors_after=sum(len(x['after_errors']) for x in replays),source_frozen_files=len(lock['files']),preservation=load(A/'preservation_verification.json'),model_calls=0,dispatch_ready=m['dispatch_ready']),indent=2))
