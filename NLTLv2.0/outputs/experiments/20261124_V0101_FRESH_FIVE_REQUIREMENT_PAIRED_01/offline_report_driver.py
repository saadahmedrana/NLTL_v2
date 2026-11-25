import pathlib,json,hashlib,collections,re,shutil,sys
from decimal import Decimal
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');P=R/'outputs/audits/20261124_V0101_FIVE_REQUIREMENT_PILOT_FINAL';B=R/'outputs/experiments/20261124_V0101_FRESH_FIVE_REQUIREMENT_PAIRED_01';E=B/'evaluation';M=json.loads((P/'pilot_manifest.json').read_text())
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def ref(path,text):
 data=path.read_text();start=data.index(text);return dict(file=str(path.relative_to(R)),sha256=sha(path),line=data[:start].count('\n')+1,excerpt=text)
assert load(B/'dispatch_closed.json')['dispatch_closed'];assert load(E/'evaluation_complete.json')['status']=='COMPLETE'
from rdflib import Graph,Namespace
from rdflib.namespace import SH
from nltlv2.evidence import literal_identity
Q=Namespace('http://qudt.org/schema/qudt/')
findings=[]
# Exact lexical evidence: do not normalize or edit any candidate/input.
for wf,suffix in [('Single-shot','SINGLE_SHOT'),('NLTL','NLTL')]:
 f=R/('outputs/experiments/'+M['batch_id']+'_I2_005_'+suffix+'/candidate_01.ttl');inp=R/'evaluation/fixtures/I2-005-G-P01.ttl'
 with literal_identity():g=Graph().parse(f);data=Graph().parse(inp)
 required=next(v for v in g.objects(None,SH.hasValue) if getattr(v,'datatype',None) and str(v.datatype).endswith('#decimal'));observed=next(data.objects(None,Q.numericValue))
 assert str(required)=='7' and str(observed)=='7.0' and required!=observed and Decimal(str(required))==Decimal(str(observed))
 findings.append(dict(id='I2_005_LITERAL_TERM_IDENTITY_'+suffix,workflow=wf,candidate=ref(f,'sh:hasValue "7"^^xsd:decimal'),input_file=str(inp.relative_to(R)),input_sha256=sha(inp),required_literal_n3=required.n3(),actual_literal_n3=observed.n3(),rdf_terms_identical=False,numeric_values_equal=True,source_file='data/requirements/IACS_I2_full.txt',source_clause='I2.2.5',meaning='Exact-term hasValue overconstrains the represented numeric 7-degree obligation; positive and three intended-only counterparts fail. This is source/candidate/report inspection, not a candidate modification or extra evaluation run.',report_format_note='Turtle report rendering may print decimal7 as7.0; original candidate/input bytes and these n3 lexical terms are authoritative for this distinction.'))
f=R/('outputs/experiments/'+M['batch_id']+'_I2_004_SINGLE_SHOT/candidate_01.ttl');findings.append(dict(id='I2_004_SINGLE_SHOT_MAXIMUM_LOGIC',candidate=ref(f,'FILTER NOT EXISTS {'),source_file='data/requirements/IACS_I2_full.txt',source_clause='I2.1.2.2',meaning='The violation SELECT requires both no greater case and no equal case. A selected lower-than-maximum value fails the first filter, so no violation row is returned; I2-004-G-F01 is missed. This is the actual fresh candidate, not the historical seed or a new benchmark diagnostic.'))
for wf,suffix in [('Single-shot','SINGLE_SHOT'),('NLTL','NLTL')]:
 f=R/('outputs/experiments/'+M['batch_id']+'_IMO_001_'+suffix+'/candidate_01.ttl');findings.append(dict(id='IMO_001_IMPLICATION_DIRECTION_'+suffix,workflow=wf,candidate=ref(f,'sh:or ('),source_file='data/requirements/IMO_full.txt',source_clause='Introduction2.1 with2.2/2.3 context',meaning='Candidate enforces CategoryA -> represented medium-first-year design condition but does not enforce the reviewed design-condition -> CategoryA direction. Both miss IMO-001-F01 (medium condition recorded with CategoryC). Accepted NLTL also allows absent category selector and misses IMO-001-F02; Single-shot requires category so catches F02. No unconditional all-ships-CategoryA obligation is inferred.'))
write(B/'independent_substantive_findings.json',findings)
# Compare the actual one repair without altering candidate bytes.
d=R/('outputs/experiments/'+M['batch_id']+'_TRF_035_NLTL');queries=[]
for version in [1,2]:
 with literal_identity():g=Graph().parse(d/f'candidate_{version:02d}.ttl')
 queries.append([str(q) for q in g.objects(None,SH.select)])
normalize=lambda q:re.sub(r'\s+',' ',q.replace('?this','$this')).strip()
assert len(queries[0])==len(queries[1])==1 and normalize(queries[0][0])==normalize(queries[1][0])
write(B/'repair_assessment.json',dict(requirement_id='TRF-035',repairs=1,cause='Two deterministic CANONICAL_IDENTIFIER_ERROR findings on minted nltl:TRF035RuleLengthEqualityConstraint and nltl:TRF035Prefixes identifiers.',change='Replaced named SPARQL constraint/prefix containers with inline blank nodes; standardized one ?this spelling to $this.',comparison_queries=queries,queries_equal_modulo_whitespace_and_equivalent_this_sigil=True,functional_calculation_change=False,rechecking='Static/runtime checks passed; review ACCEPT after one shared format correction to assess13 retrieval gaps.',selected_version=2,before_sha256=sha(d/'candidate_01.ttl'),after_sha256=sha(d/'candidate_02.ttl'),external_behavior='Both versions agree with6/6 original cases and accept4/4 counterparts; rejected version1 remains diagnostic-only.'))
metrics=load(B/'call_metrics.json');progress=load(B/'dispatch_progress.json');selected=load(E/'selected_output_results.json');diagnostics=load(E/'candidate_diagnostics.json');closure=load(B/'dispatch_closed.json');complete=load(E/'evaluation_complete.json')
usage=dict(input_tokens=sum(x['usage'].get('input_tokens',0) for x in metrics),output_tokens=sum(x['usage'].get('output_tokens',0) for x in metrics),total_tokens=sum(x['usage'].get('total_tokens',0) for x in metrics),cached_input_tokens=sum(x['usage'].get('input_tokens_details',{}).get('cached_tokens',0) for x in metrics),reasoning_output_tokens_included_in_output=sum(x['usage'].get('output_tokens_details',{}).get('reasoning_tokens',0) for x in metrics))
routes={route:dict(calls=sum(x['route']==route for x in metrics),minimum_rendered_bytes=min(x['rendered_bytes'] for x in metrics if x['route']==route),maximum_rendered_bytes=max(x['rendered_bytes'] for x in metrics if x['route']==route)) for route in sorted({x['route'] for x in metrics})}
table=[]
for rid in M['requirements']:
 single=next(x for x in diagnostics if x['workflow']=='Single-shot' and x['requirement_id']==rid);nrun=next(x for x in progress if x['workflow']=='NLTL' and x['requirement_id']==rid);nselected=next((x for x in diagnostics if x['workflow']=='NLTL' and x['requirement_id']==rid and x['selected']),None);nrejected=[x for x in diagnostics if x['workflow']=='NLTL' and x['requirement_id']==rid and not x['selected']]
 table.append(dict(requirement_id=rid,single_shot_ordinary_agreement=f"{single['ordinary_correct']}/{single['original_cases']}",nltl_terminal=nrun['status'],nltl_selected_version=nrun['accepted_version'],nltl_selected_ordinary_agreement=f"{nselected['ordinary_correct']}/{nselected['original_cases']}" if nselected else 'NO_VERDICT',nltl_rejected_diagnostics=[dict(version=x['version'],ordinary_agreement=f"{x['ordinary_correct']}/{x['original_cases']}") for x in nrejected],single_calls=1,nltl_calls=nrun['provider_calls']))
summary=dict(label='FRESH_PAIRED_FIVE_REQUIREMENT_DEVELOPMENT_EVIDENCE_NOT_HELD_OUT',offline_tests=dict(tests=214,failures=0,errors=0,initial_harness_import_error_corrected=True),dispatch=dict(status='CLOSED',calls=19,maximum_calls=55,generations=10,repairs=1,primary_reviews=5,shared_response_corrections=3,candidates=11,all_candidates_preserved=True,no_additional_calls=True,elapsed_seconds=closure['elapsed_seconds'],provider_seconds=sum(x['provider_elapsed_seconds'] for x in metrics)),usage=usage,request_size_ranges=routes,results=table,selected_summaries=selected['summaries'],independent_evaluation_seconds=complete['elapsed_seconds'],independent_oracle_label_disagreements=complete['oracle_disagreements'],strict_attribution_policy='Existing exact-query-body correspondence; unresolved wrappers/property constraints not credited as strict detections.',selection='First internal acceptance only, sealed before evaluation; three requirements NO_VERDICT. Rejected candidates diagnostic-only, never selected by external score.',unchanged_implementation=True,preserved_historical_results=True,deferred=['I2-042'])
write(B/'pilot_summary.json',summary)
lines=[]
for x in table:lines.append(f"{x['requirement_id']} | {x['single_shot_ordinary_agreement']} | {x['nltl_selected_ordinary_agreement']} | {x['nltl_terminal']} | {x['single_calls']}+{x['nltl_calls']}")
report='''FRESH FIVE-REQUIREMENT PAIRED DEVELOPMENT PILOT — COMPLETED

Authorized by user: "u can run them  now", following the exact offline/live commands and55-call ceiling. Scope, edition, source/schema, model and v0.10.1 implementation were frozen. No added requirements, study expansion, preferred-result rerun, candidate edit, lenient final attempt or human acceptance arm. I2-042 remains deferred.

OFFLINE CHECKS
Frozen preflight passed. The original user-facing test command failed nine module imports because its existing socket-class guard was installed before ssl loaded. This was an audit-harness import-order problem, not nine exercised test failures. Preloading ssl/unittest.mock before the unchanged guard corrected it:214 tests,0 failures,0 errors,0 model calls,4.001s. Both outcomes are recorded; implementation/prompts were not changed. The printed ConstraintLoadError in the successful test log is an intentional malformed-structure control, not a suite failure.

LIVE DISPATCH
All ten planned jobs executed once and closed.19/55 provider calls:10 fresh generations,5 primary reviews,3 shared response corrections,1 targeted repair. All11 candidates and full actual packets/responses, original logs/findings, code/evidence validation, changes/diffs and terminal reasons are saved. No provider process remains and no more calls will be made. Five actual initial request/provider-payload pairs matched the prepared packets exactly. Dispatch and selected/all-candidate manifests were sealed before external evaluation.

Requirement | Single-shot original-case agreement | Selected NLTL agreement | NLTL terminal | Calls Single+NLTL
'''+ '\n'.join(lines)+'''

NO_VERDICT is not a selected rejected candidate. All original denominators remain unchanged. Selected-output totals: Single-shot27 correct,3 incorrect,0 no-verdict out of30; NLTL9 correct,2 incorrect,19 NO_VERDICT out of30. NLTL had two selected outputs covering11 cases, of which9 agree. Single-shot accepted13/16 existing counterparts. NLTL accepted7 selected-output counterparts; the other9 have NO_VERDICT because no internally accepted candidate exists. These are ordinary execution/label comparisons, NOT strictly attributed detection scores or whole-requirement compliance certification. Known development cases are not held out, and this small pilot does not establish workflow superiority.

REVIEW AND STOPPING EVIDENCE
I2-004: first review returned an unresolved eligibility proposal but failed exact source-clause validation (WRONG_SOURCE_CLAUSE). Its one corrected response said ACCEPT but left10 retained retrieval gaps unassessed. REVIEWER_FORMAT_FAILURE; no repair, accepted issue or output. Candidate preserved.
I2-005: review independently raised horizontal-reference uncertainty and the "7"^^decimal RDF-term versus numeric equality issue. Its proposed shellInclinationAngle property/numeric paths omitted the ship-to-boundary-point prefix required by the supplied proposal contract; they matched no alternate declared property and remained blocking UNRESOLVED_REPRESENTATION_CONFLICT, not the narrow correctable mismatched-pair case. Terminal CONFLICT; no repair. This protocol outcome is not proof that the ontology/source itself is contradictory.
IMO-001: review validated and ACCEPTed version1 directly. Independent evaluation still found two missed negatives, showing that validated citations/review acceptance do not establish the represented interpretation's correctness.
TRF-010: review twice treated the section1.8 multiple-anchor ambiguity (contents/reference versus source section) as material and requested source evidence. Local retrieval added no novel resolution and stopped REPEATED_EVIDENCE_REQUEST. No repair or acceptance.
TRF-035: version1 had two deterministic canonical-identifier errors on named SPARQL/prefix containers. One targeted repair inlined those containers and standardized a ?this/$this spelling. The comparison query is identical modulo whitespace and equivalent variable sigil, so there is no functional calculation change. Static/runtime rechecking passed. The first ACCEPT response left13 retrieval gaps unassessed; its one shared correction assessed them and validated ACCEPT for version2. Both versions behave6/6 on originals and4/4 on counterparts, but only accepted version2 is selected.

INDEPENDENT SUBSTANTIVE FAILURES
- I2-004 Single-shot: violation query joins NOT EXISTS(greater case) AND NOT EXISTS(equal case). A lower-than-maximum selection makes the first filter false, producing no violation; I2-004-G-F01 is missed. This is the actual fresh candidate; historical seed/repair solutions were not injected. The rejected NLTL candidate happens to agree6/6 but is diagnostic-only.
- I2-005 both workflows: exact-term sh:hasValue "7"^^xsd:decimal rejects the numerically equal input "7.0"^^xsd:decimal. The original positive and three intended-only counterparts fail. Literal lexical identity is preserved in the raw candidate/input and independent_substantive_findings.json. RDFLib's Turtle report rendering can display the decimal differently; the saved raw bytes/n3 evidence establish the distinction. No candidate or fixture was normalized or patched.
- IMO-001 both workflows: enforcing CategoryA -> design condition does not enforce the reviewed design-condition -> CategoryA direction. Both accept medium-first-year design condition with CategoryC (F01). Accepted NLTL also accepts absent category with that condition (F02). Single-shot's required category catches F02. No unconditional CategoryA rule for every ship is inferred.
No new source-backed expected labels were invented: all46 unchanged source-oracle/input checks agree with retained expectations. No original score or fixture was rewritten.

REJECTED DIAGNOSTICS — NEVER SELECTED
I2-004 NLTLv1:6/6; I2-005 NLTLv1:4/5; TRF-010 NLTLv1:8/8; TRF-035 NLTLv1:6/6. These remain REJECTED_CANDIDATE_DIAGNOSTICS even where their observed behavior is better than another selected output. Final rejected candidates and their terminal reasons remain in candidate_inventory.json.

ATTRIBUTION LIMITATION
Independent evaluation executed102 candidate/input validations across11 saved candidates using existing pySHACL helpers, approved scope hashes and unchanged reviewed class-population proofs. Conservative existing exact source-authored query-body matching does not resolve most generated SHACL/property-wrapper semantics. Single-shot strict statuses:2 missed intended defects,3 unrelated/additional-failure pairs,11 unresolved attribution. Selected NLTL:2 missed intended defects,5 unresolved attribution,9 NO_VERDICT. Unresolved attribution receives no strictly verified detection credit; ordinary agreement is reported separately. No posthoc acceptance, external-score selection or lenient attribution rule was introduced.

USAGE AND RUNTIME
Provider input tokens992,083; output41,153; total1,033,236. Cached input90,133. Reasoning output21,991 is included in output, not added again. Dispatch wall307.877s; sum provider request time291.160s. Independent evaluation35.311s with4 local workers; no evaluation/model calls overlapped and evaluation made0 provider calls.
Exact system+user UTF-8 request bytes: generation44,954–156,020 (10); primary review111,723–345,231 (5); shared correction264,271–350,601 (3); targeted repair184,619 (1). Complete per-call usage, payload reconstruction and size evidence are retained. Actual provider payloads are reconstructed from the exact stored request and frozen production renderer; no claim of captured TLS/network bytes is made.

PRESERVATION
The frozen implementation, prompts, canonical schema/ontology, approved scopes, source files/catalog, all prior runs/scores, fixture/counterpart files, tracker and17-item ledger remain unchanged. Dispatch closure binds selected manifest and every saved candidate hash. All pre-existing files are checked again after evaluation. Complete external artifacts remain outside production resource access. No further calls, reruns or pipeline modifications were made.

FILES
pilot_summary.json: concise machine-readable report.
selected_outputs.json + dispatch_closed.json: score-independent selection/closure.
candidate_inventory.json: every candidate/findings/status, including final rejections.
call_metrics.json: original usage/runtime/size per request.
evaluation/selected_output_results.json: selected-output-only results and unchanged denominators.
evaluation/candidate_diagnostics.json: all candidates, clearly separated by selected status.
evaluation/all_candidate_verdicts.json and per-case report.ttl/result.json: complete execution evidence.
independent_substantive_findings.json + repair_assessment.json: exact code/source references and analytical diagnoses.
'''
(B/'REPORT.txt').write_text(report)
shutil.copy2('/tmp/nltl_evaluate_closed_five_pilot.py',B/'independent_evaluation_driver.py');shutil.copy2('/tmp/nltl_finish_five_pilot_report.py',B/'offline_report_driver.py')
before=load(B/'protected_before.json');changed=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h];assert not changed,changed
for f,h in load(P/'evaluation_resources.lock.json').items():assert sha(R/f)==h
for f,h in load(P/'frozen_resource_hashes.json').items():assert sha(R/f)==h
write(B/'final_preservation_verification.json',dict(status='PASS',protected_existing_files=len(before),modified_or_deleted=[],frozen_implementation_and_resources_unchanged=True,original_evaluation_inputs_and_scores_unchanged=True,selected_manifest_still_sealed=sha(B/'selected_outputs.json')==closure['selection_manifest_sha256'],all_candidate_hashes_intact=all(sha(R/f)==h for f,h in closure['all_candidate_sha256'].items()),model_calls=19,no_additional_dispatch=True))
# Bind report/evaluation and each sibling job's full packet tree without modifying historical manifests.
artifact_files=[f for f in B.rglob('*') if f.is_file() and f.name!='artifact_manifest.json']
for job in M['jobs']:artifact_files.extend(f for f in (R/job['output']).rglob('*') if f.is_file())
write(B/'artifact_manifest.json',{str(f.relative_to(R)):sha(f) for f in artifact_files})
print(json.dumps(dict(report=str(B/'REPORT.txt'),summary=summary,preservation=load(B/'final_preservation_verification.json')),indent=2))
