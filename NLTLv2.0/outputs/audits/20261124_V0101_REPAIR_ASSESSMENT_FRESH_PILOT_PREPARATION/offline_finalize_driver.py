import pathlib,json,hashlib,copy,socket,collections,time
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');O=R/'outputs/audits/20261124_V0101_REPAIR_ASSESSMENT_FRESH_PILOT_PREPARATION';P=O/'pilot_preparation';D=O/'external_development_diagnostic'
def load(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
from nltlv2.core import Project,GenerationProject
from nltlv2.requests import initial_request
from rdflib import Graph,Literal
from rdflib.namespace import SH
from rdflib.compare import isomorphic
from nltlv2.evidence import literal_identity
RUN=R/'outputs/experiments/20261124T113231275705Z_V0101_I2_004_DEVELOPMENT_CONTINUATION';seed=RUN/'I2-004/nltl/candidate_01.ttl';repair=RUN/'I2-004/nltl/candidate_02.ttl'
with literal_identity():a=Graph().parse(seed);b=Graph().parse(repair)
queries={label:[str(q) for q in g.objects(None,SH.select)] for label,g in [('seed',a),('repair',b)]}
for g in [a,b]:g.remove((None,SH.select,None))
assert isomorphic(a,b)
write(O/'query_and_non_query_comparison.json',dict(queries=queries,all_non_select_shape_triples_isomorphic=True,interpretation='Only SELECT strings differ semantically; blank-node identity ignored. Prefix expansion, comparison repair and whitespace changes exactly documented in original diff.'))
source=R/'data/requirements/IACS_I2_full.txt';txt=source.read_text();start=txt.index('I2.1.2.2 The ship displacement')
# Select the exact paragraph, excluding following heading or page content.
quote_end=txt.index('displacement.',txt.index('greatest',start))+len('displacement.')
prov=load(D/'mutation_provenance.json');prov.pop('quotation',None);prov.update(exact_source_quotation=txt[start:quote_end],source_character_range=[start,quote_end],source_lines=[txt[:start].count('\n')+1,txt[:quote_end].count('\n')+1]);write(D/'mutation_provenance.json',prov)
checks=[]
for rid in ['I2-004','I2-005','IMO-001','TRF-010','TRF-035']:
 request=load(P/(rid+'_initial_request_OFFLINE_ONLY.json'));ctx=json.loads(request['user'])['context'];rendered=[]
 for method in ['Single-shot','NLTL']:
  cfg=load(P/(rid+'_'+method+'_PROPOSED.json'));Project(R).config(str((P/(rid+'_'+method+'_PROPOSED.json')).relative_to(R)))
  settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}
  req=initial_request(GenerationProject(R),copy.deepcopy(ctx),settings);rendered.append(req)
 assert rendered[0]==rendered[1]==request
 checks.append(dict(requirement_id=rid,identical_initial_request=True,rendered_system_sha256=hashlib.sha256(request['system'].encode()).hexdigest(),rendered_user_sha256=hashlib.sha256(request['user'].encode()).hexdigest(),settings_equal=True,configs_valid=True))
# Confirm new external graphs, evaluation and historical candidates are denied by source-only capability.
access=[]
for path in [str((D/'above_maximum.ttl').relative_to(R)),'evaluation/fixtures/I2-004-G-P01.ttl',str(seed.relative_to(R)),str((P/'plan.json').relative_to(R))]:
 try:GenerationProject(R).path(path)
 except (ValueError,PermissionError) as e:access.append(dict(path=path,denied=True,reason=str(e)))
 else:raise AssertionError('Forbidden source path accessible: '+path)
write(P/'software_checks.json',dict(identical_initial_inputs=checks,source_only_denials=access,configs=10,network_calls=0,transport_instances=0))
# Narrow schema semantics review (full graph extracts already retained).
sem=load(P/'representation_semantics_review.json')
write(P/'readiness_decisions.json',{
'I2-004':{'scope':'Existing I2.1.2.2-specific approval only; edition and synthetic eligibility explicitly assumed.','decision':'Ready for a separately authorized fresh pair, not a continuation or seeded generation.'},
'I2-005':{'scope':'Absent approval: distinct I2.2.5 boundary-point population and source-edition selection needed.','representation':'ship -> hasBottomRegionLowerRegionBoundaryPoint -> hullBoundaryPoint -> shellInclinationAngle; decimal degrees.','limitation':'Supplied point and angle support a represented boundary-angle check; they do not establish physical boundary geometry. Keep source figure/reference materiality explicit.'},
'IMO-001':{'scope':'Absent approval. Native document identifies MSC.385(94), adopted 21 November 2014; no catalog edition/authority/provenance selection support.','representation':'designIceCondition and shipCategory object properties, controlled individuals available. Definition of mediumFirstYearIceWithPossibleOldIceInclusions explicitly says at least medium first-year ice.','limitation':'A finite represented design-condition population can be proposed, but do not interpret the clause as requiring every ship to be Category A or silently certify a general severity hierarchy. Conditional definition and absent inputs require source/representation adjudication.'},
'TRF-010':{'scope':'Absent approval. Native document TRAFICOM/68863/03.04.01.00/2021 identifies 2021 edition; catalog lacks admission metadata. Section 1.1 explicitly applies section 1.8 to all ships irrespective of build year; do not inherit I2 dates.','representation':'All six canonical ice-class individuals available from ontology even if absent registry entries.','limitation':'Class-record vocabulary validation does not independently establish structure, power or capabilities described by each class. Act 1121/2005 section 3 is referenced; unresolved reference materiality must be reviewed, not automatically assumed resolved.'},
'TRF-035':{'scope':'Absent approval. Distinct construction/date/application scope for section 4.1.1 needed; no blanket section 1.8 exception. Catalog metadata missing as for TRF-010.','representation':'Both length quantities are direct ship-owned decimal metres. Ontology explicitly calls classificationSocietyRuleLength a linked requirement operand and recommended unit M, but flags development unit selected and fixture conversion required. No equivalentProperty assertion was found between the two properties in the inspected subjects.','limitation':'Compare submitted L against an independently supplied society rule-length datum only under an explicitly declared representation; do not derive society rules from its name. Classification-society identity/provenance is not proof of the value. bow/midbody/stern are individuals despite ownership-map entries: retain kind checks rather than treating them as quantity paths.'},
'I2-042':{'decision':'DEFERRED; excluded from all proposed dispatch and evaluation inventories.'}})
write(P/'freeze_inputs.json',{str(p.relative_to(R)):sha(p) for folder in ['src','configs','prompts','schema','data/requirements','data/admissions'] for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts})
# Token ceilings only; input tokens and elapsed time unknowable before fresh responses.
plan=load(P/'plan.json');plan.update(response_token_ceiling=dict(per_pair=80000,all_five_pairs=400000,derivation='Single-shot 16000 + NLTL two candidate calls * 16000 + eight primary/correction responses * 4000. Actual calls/outputs stop early; input/provider token totals are not estimated by bytes.'),dispatch_prerequisites=['Separate approved scope per requirement, approved source-edition/provenance selection and current catalog readiness.','Per-input admitted-population bindings and independent expected-behavior review for cases/counterparts outside production.','Verify installed/source identity against source tree and freeze all current resources and rendered initial inputs; present shared environment has old installed metadata unless PYTHONPATH/current frozen runtime is explicit.','Freeze prompts/configuration before first dispatch, use fresh output identifiers, empty prior issues, and production source-only capability.','Retain actual packets/responses/code hashes/diagnostics and all transitions; close both workflows before independent evaluation.'],future_request_accounting='Initial estimates are exact system+user UTF-8; provider JSON overhead excluded. Review/repair/correction/retrieval request sizes cannot be exact before fresh outputs. Preserve and measure full actual packets; bounded retrieval never silently truncates material context. No historical candidate was used to manufacture an estimate.')
write(P/'plan.json',plan)
sizes=load(P/'request_sizes.json');size_lines='\n'.join(f"{v['requirement_id']}: {v['rendered_bytes']:,} bytes per arm ({v['status']})." for v in sizes)
report=f'''OFFLINE v0.10.1 REPAIR ASSESSMENT AND FRESH FIVE-REQUIREMENT PILOT PREPARATION

Successful continuation preserved unchanged. No provider/model calls, pipeline changes, fixture edits, tracker changes, source/schema/scope changes, or historical score updates. New files exist only in this audit directory. The external diagnostic is post-repair development evidence, not held out or fresh comparative performance.

REPAIR ASSESSMENT
Inspected exact source data/requirements/IACS_I2_full.txt, clause I2.1.2.2 (lines {prov['source_lines'][0]}-{prov['source_lines'][1]}), existing approved I2-004 declaration, exact candidate_01 seed d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a, accepted candidate_02 823c65db62106f8b2c8f2fab358ee1f7b9de76fce380965915eeda6bc315164a, and original diff_01_02.patch. See exact_inspected_references.json for immutable paths/hashes and dispatch closure; query_and_non_query_comparison.json retains both complete queries.

Let u be the selected displacement and C the finite, nonempty set of supplied valid determining-case displacements. Seed violation: exists c in C, c > u. It therefore accepts u above every case. Repaired violation: (exists c > u) OR (no c = u). Acceptance becomes (all c <= u) AND (some c = u), exactly u = max(C). Tied maxima remain allowed. Numeric equality is SPARQL decimal equality, not literal lexical identity. The full-IRI rewrites remove reliance on prefix resolution without changing the represented identifiers. Non-SELECT shape triples are graph-isomorphic, so targets, nested shapes, datatype/unit/cardinality checks and source annotations were retained. This implements the represented maximum obligation under the declared research scope, conditional on complete and accurate submitted determining cases.

Assumptions and missing-input behavior (analytical inspection, except the separately executed diagnostic below):
- Linked cases must be all and only the waterlines used to determine UIWL. Open-world RDF cannot establish completeness; an omitted true maximum can still lead to acceptance. Unlinked waterlines are ignored.
- Exactly one selected displacement and one displacement per case, at least one case, decimal numericValue, quantity/case classes and canonical metric-kilotonne unit are inherited shape requirements. These are representation/data-completeness assumptions; the bare source paragraph does not independently justify every serialization cardinality. In particular, the single-waterline source branch is represented using at least one case rather than allowing an absent case list.
- Missing selected quantity, case displacement, numeric value or canonical unit is blocked by nested SHACL core constraints even when the comparison cannot bind it. Required class membership is checked after RDFS inference: absence of an explicit rdf:type alone need not fail if ontology domains/ranges entail it. No cases is blocked by minCount; with a bound selected value, the repaired no-equal branch also rejects. Multiple selected quantities/numeric values are blocked by maxCount. Invalid datatypes and unit mismatches do not silently count as valid operands: core shape constraints fail. These observations were not a new exhaustive missing-input test suite.
- No unit conversion, rounding tolerance, positive-mass rule, case-list completeness test, physical-waterline verification, real vessel eligibility/date certification or legally governing-edition certification was added. Canonical decimal/kt data and caller-admitted synthetic population remain essential. Focus is class ship with RDFS inference; input-population guards belong to the external admission/evaluation boundary.
- No regression is demonstrated: all non-query shape constraints are retained, and the new PASS control remains PASS. The accepted historical six-case/three-counterpart evaluation remains unchanged and is reused only as historical evidence, not rerun here. This small diagnostic does not establish absence of regressions on arbitrary data.

NEW EXTERNAL DEVELOPMENT DIAGNOSTIC
Base: unchanged I2-004-G-P01 positive graph. Supplied case values 10.0, 12.0, 11.0 kt; selected value changed from 12.0 to 13.0 kt. Only one numeric triple is replaced. Source-backed expectation FAIL because 13 is not the greatest case displacement, 12. Intended-only correction replaces that selected numeric value with 12.0; corrected graph is isomorphic to the original positive graph. Exact source quotation with original whitespace and character/line bounds is in external_development_diagnostic/mutation_provenance.json. New evaluation-only scope bindings hash each new input. Existing I2-004 scope is used without extension.

                           Expected  Seed       Repair
Above maximum (13 vs 12)    FAIL      PASS/miss  FAIL/detected
Intended-only (12 vs 12)    PASS      PASS       PASS

Four local pySHACL executions, independent source-authored oracle cross-check, full reports and admission results are saved under external_development_diagnostic/. The repair's violation is the maximum SELECT constraint; no unrelated nested constraint failed. Neither graph is available through GenerationProject. Original six-case benchmark, counterparts, scores and accepted run are untouched. This is deliberately uncovered-direction development evidence and must never be pooled as held-out evidence.

FRESH PAIRED PILOT — PROPOSAL ONLY, DO NOT DISPATCH
Requirements: I2-004, I2-005, IMO-001, TRF-010, TRF-035. I2-042 deferred. Overall status BLOCKED pending four distinct approvals, source catalog readiness and independent evaluation admissions. Do not silently omit blocked requirements to call a partial run the five-requirement pilot.

I2-004: source/hash, quantities/paths/units and approved I2.1.2.2 research scope available. Ready for a separately authorized fresh pair. Approval is not a general UR I2 or five-requirement scope.
I2-005: source I2.2.5, nested boundary-point angle in decimal degrees available. Needs its own population/edition approval and evaluation bindings; angle/point records do not certify physical boundary geometry. I2-004 scope is not reused.
IMO-001: source Introduction 2.1 and canonical design-condition/category individuals available; one condition's ontology definition explicitly represents 'at least medium first-year ice'. Needs separate approval, catalog document-id/edition/authority/provenance metadata and independent evaluation scope review. Category-A definition must not become unconditional Category-A membership for every ship. No general ice-severity hierarchy is established by individual names.
TRF-010: source section 1.8 and six canonical class individuals available, including individuals absent registry rows. Needs separate approval, catalog metadata and evaluation bindings. Section 1.1 makes section 1.8 apply irrespective of build year. A class-vocabulary check is narrower than proving the capabilities in class descriptions; referenced Act context materiality remains explicit.
TRF-035: source section 4.1.1, two decimal-metre quantities and direct ship paths available. Needs separate scope/edition approval, catalog metadata, independent input/value provenance and evaluation bindings. Existing quantity-unit metadata carries a development/fixture-conversion qualification. Resolve interpretation of independently supplied society rule length and L without handwritten repair solutions. Bow/midbody/stern individuals are not numeric properties despite noisy ownership entries.

Readiness details, actual retained source hashes, paths, unresolved references and full relevant ontology extracts: pilot_preparation/readiness.json, readiness_decisions.json, representation_semantics_review.json. Missing catalog metadata is an existing admission-readiness blocker; nothing was changed to bypass it. Proposed metadata/approvals are not fabricated.

Exact proposed settings: established Aalto Responses endpoint, model gpt-5.6-luna-2026-07-09, generation_max_tokens=16000, review_max_tokens=4000, bounded_json, review_max_issues=12; same source/schema/approved admission and initial generation request byte-for-byte for both arms. No examples, seeded shapes, prior issues, historical failed reviews or repair solutions. Existing config resource routes, checker/reviewer/repair/terminal behavior retained. Stagnation detection remains reporting-only as current production configuration; candidate/review/call caps and terminal outcomes bound execution. Proposed configs are inert method=offline, network_enabled=false with proposed_method recorded. They are configuration proposals, not executable authorized jobs.

Single-shot: exactly one initial generation call and no review, retries or repair.
NLTL: one fresh generation, at most one repair, at most two candidates; at most four primary reviews total, at most three per candidate; one shared response-correction allowance per primary review; at most two retrieval rounds; at most ten provider calls including all corrections and repair. Uses the existing continuation.max_provider_calls guard as a generic call budget, not seeded continuation mode. Early acceptance/terminal stopping, no regeneration or preferred-result reruns.
Maximum five-pair calls: 5 Single-shot + 50 NLTL = 55. Output-token caps: at most 80,000 per pair, 400,000 total (not a usage forecast). Retrieval retains current limits: <=3 requests/round, <=6 documents, depth<=3, <=6 passages/round, <=16,000 characters/round and <=32,000 added source characters total; <=24 schema terms/300 triples per round and <=24 reference lookups. Material unavailable context blocks; no silent truncation.

After ALL dispatches close, evaluate unchanged per-requirement cases and intended-only counterparts independently. Inventory: 30 original cases (14 positive,16 negative) plus16 counterparts. Require reviewed per-input admissions, expected-behavior/source attribution and identical evaluation sets. The four unapproved scopes are also evaluation blockers, even if existing source-authored expected labels are present. Only internally accepted NLTL outputs receive selected-output credit; otherwise NO_VERDICT. Rejected-candidate diagnostics remain separate. External above-maximum diagnostic is excluded from this original inventory and score denominators. These are known development cases; fresh generation does not turn them into held-out evidence or prove workflow superiority.

REQUEST-SIZE ESTIMATES
{size_lines}
Numbers are exact current system+user UTF-8 bytes per arm, excluding provider JSON framing. I2-004 includes its actual approved admission. Four other rows are conditional baseline sizes excluding future admission envelopes; final sizes must be re-rendered after approval. Their differing source context sizes are retained intact. Byte totals are not provider tokens. Full offline initial packets and component accounting are saved. No unseen candidate, review, repair or retry was fabricated: their later request sizes depend on actual generation, retrieval, issues and responses and must be measured at dispatch. Configured output-token ceilings do not imply an input-byte ceiling.

VERIFICATION AND FREEZE
All ten inert configs passed existing configuration checks. Each pair's independently re-rendered initial system/user/settings match exactly. GenerationProject rejects diagnostic, pilot artifact, original fixture and historical candidate paths. Socket connections disabled; no transport or provider constructed. All 10,602 pre-existing protected files are unchanged (including source, prompts, configs, schema, approved scope, original fixtures/scores, historical outputs and ledger). New external diagnostic only: four local validations, no original benchmark reruns. Full software evidence and freeze-input hashes are saved. The shared environment's old installed package must not be mistaken for current v0.10.1: future dispatch must verify and freeze an explicit current source/installed runtime identity before any call. No runtime identity was silently updated in this preparation.
'''
(O/'report.txt').write_text(report)
# Include scripts as reproducibility evidence; paths refer only to new audit output.
(O/'offline_assessment_driver.py').write_bytes(pathlib.Path('/tmp/nltl_offline_assess_prepare.py').read_bytes());(O/'offline_finalize_driver.py').write_bytes(pathlib.Path('/tmp/nltl_finish_offline_assessment.py').read_bytes())
preservation=load(O/'preservation_verification.json');changed=[k for k,h in preservation['manifest'].items() if not (R/k).is_file() or sha(R/k)!=h];assert not changed,changed
preservation['final_check']='PASS_AFTER_REPORT_AND_PREPARATION';write(O/'preservation_verification.json',preservation)
write(O/'artifact_manifest.json',{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
print(json.dumps(dict(report=str(O/'report.txt'),config_checks=len(checks)*2,identical_pairs=len(checks),denied_paths=len(access),non_query_graphs_isomorphic=True,protected=len(preservation['manifest']),new_artifacts=sum(1 for p in O.rglob('*') if p.is_file())),indent=2))
