from pathlib import Path
import json,hashlib,collections,sys
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');M=R.parent/'MVP';A=R/'outputs/audits/20261125_EXISTING_CASES_20_10_FINAL_READINESS';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text());save=lambda n,x:(A/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
# First: inventory in NLTLv2.0, including its provenance pointers; no generated scores read.
new_inventory=load(R/'evaluation/selections/case_inventory.json');new_core=load(R/'evaluation/selections/regression_core.json')['cases'];first=dict(root=str(R),indexed_cases=len(new_inventory),bundled_cases=len(new_core),bundled_requirement_ids=sorted({c['requirement_id'] for c in new_core}),meaning='fixture:null/bundled:false means not copied here, not absent from MVP/dataset.')
# Second: MVP retained manifests and saved source/schema case review; do NOT execute historical runners.
base=M/'SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13';manifestrows=[]
for f in sorted((base/'manifests').glob('*.jsonl')):
 for line in f.read_text().splitlines():
  if line.strip():manifestrows.append(dict(json.loads(line),manifest_file=str(f),manifest_sha256=sha(f)))
locks=[];badlocks=[];checked=0
for f in sorted((base/'locks').glob('*fixture_lock.json')):
 lock=load(f);issues=[]
 for relative,h in lock.get('frozen_files',{}).items():
  path=base/relative;checked+=1
  if not path.is_file() or sha(path)!=h:issues.append(relative)
 locks.append(dict(file=str(f),sha256=sha(f),requirements=lock.get('requirements'),frozen_files=len(lock.get('frozen_files',{})),mismatches=issues))
 if issues:badlocks.append(dict(lock=str(f),mismatches=issues))
reviewdir=M/'evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z';review=load(reviewdir/'reviewed_cases.json');per=load(reviewdir/'per_requirement_review.json');casegroups=collections.defaultdict(list);failures=[]
for row in review:
 if row.get('review_status') not in ['SOURCE_AND_SCHEMA_VERIFIED_POSITIVE','SOURCE_AND_SCHEMA_VERIFIED_NEGATIVE_WITH_REPAIR']:continue
 path=Path(row['fixture']);errors=[]
 if not path.is_file() or sha(path)!=row['fixture_sha256']:errors.append('REVIEWED_FIXTURE_HASH_MISMATCH')
 source=row.get('source_evidence',{});sourcepath=Path(source.get('source_path',''))
 if not sourcepath.is_file() or sha(sourcepath)!=source.get('source_sha256'):errors.append('SOURCE_PROVENANCE_HASH_MISMATCH')
 if row['expected']=='FAIL':
  rep=row.get('independent_repair_review',{});rp=Path(rep.get('path',''))
  if not rp.is_file() or sha(rp)!=rep.get('sha256'):errors.append('COUNTERPART_HASH_MISMATCH')
  if rep.get('source_oracle',{}).get('conforms') is not True or not rep.get('one_intended_property_changed'):errors.append('INTENDED_ONLY_COUNTERPART_NOT_ESTABLISHED')
 if not row.get('freeze_verified') or not row.get('gold_expectation_verified'):errors.append('REVIEW_RECEIPT_NOT_VERIFIED')
 if row.get('workflow_outcomes_used') or row.get('screened_against_generated_shapes'):errors.append('GENERATED_PERFORMANCE_USED_FOR_CASE_REVIEW')
 if errors:failures.append(dict(case_id=row['case_id'],errors=errors));continue
 casegroups[row['requirement_id']].append(dict(case_id=row['case_id'],requirement_id=row['requirement_id'],expected=row['expected'],fixture=str(path),fixture_sha256=sha(path),source_file=str(sourcepath),source_sha256=sha(sourcepath),counterpart=rep.get('path') if row['expected']=='FAIL' else None,counterpart_sha256=rep.get('sha256') if row['expected']=='FAIL' else None,original_review_status=row['review_status'],review_artifact=str(reviewdir/'reviewed_cases.json'),review_artifact_sha256=sha(reviewdir/'reviewed_cases.json'),model_context_forbidden=True,unchanged=True))
# Third: locked dataset identity, verifying the retained R13 machine-readable assets actually used.
locked=M/'BENCHMARK_VOCABULARY/FINAL_LOCK_R13';lockfile=locked/'benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json';lk=load(lockfile);bound=lk['boundMachineReadableArtifacts'];keyfiles=['ontology/nltl_benchmark_vocabulary.ttl','registry/term_registry.json','context/nltl_benchmark_context.jsonld'];lockedproof=[]
for name in keyfiles:
 p=locked/name;assert sha(p)==bound[name];lockedproof.append(dict(file=str(p),sha256=sha(p),lock_file=str(lockfile)))
assert sha(R/'schema/Schema_for_NLTL.ttl')==bound['ontology/nltl_benchmark_vocabulary.ttl'];assert sha(R/'schema/term_registry.json')==bound['registry/term_registry.json'];assert sha(R/'schema/locked_representation_context.jsonld')==bound['context/nltl_benchmark_context.jsonld']
byreq={x['requirement_id']:x for x in per};ready=[];summaries=[]
complexity={'TRF-010':'EASY','TRF-001':'INTERMEDIATE','I2-005':'INTERMEDIATE','TRF-035':'INTERMEDIATE','TRF-036':'DIFFICULT','TRF-050':'DIFFICULT','I2-004':'DIFFICULT','I2-048':'DIFFICULT','IMO-001':'INTERMEDIATE','I2-042':'INTERMEDIATE'}
for rid,cases in sorted(casegroups.items()):
 pos=[x for x in cases if x['expected']=='PASS'];neg=[x for x in cases if x['expected']=='FAIL']
 if not pos or not neg:continue
 p=byreq[rid];scope=R/'data/admissions'/f'{rid.lower().replace("-","_")}_research_scope.approved.json';blocked=[]
 if rid=='I2-042':blocked.append('PREVIOUSLY_DEFERRED')
 if rid=='IMO-001':blocked.append('UNRESOLVED_DESIGN_INTENT_REPRESENTATION')
 if not scope.is_file():blocked.append('APPROVED_RESEARCH_SCOPE_MISSING')
 # Existing evaluation route covers only the six copied core requirements.
 if rid not in {x['requirement_id'] for x in new_core}:blocked.append('CURRENT_EVALUATOR_SCOPE_BINDINGS_NOT_INTEGRATED')
 if not blocked:ready.append(rid)
 summaries.append(dict(requirement_id=rid,verified_positive_cases=len(pos),verified_negative_counterpart_pairs=len(neg),total_original_cases=len(cases),all_cases_in_requirement_verified=not p['positive_not_certified'] and not p['negative_gold_not_certified'],branch_review=p['branch_review_status'],coverage_limits=p['coverage_gaps'],complexity=complexity.get(rid,'NOT_CLASSIFIED'),complexity_basis='Source/table/branch and explicit RDF traversal structure, not generated model performance.',scope_approved=scope.is_file(),blockers=blocked,end_to_end_ready=not blocked))
source_reviewed=[x['requirement_id'] for x in summaries];eligible=[x['requirement_id'] for x in summaries if x['requirement_id'] not in ['IMO-001','I2-042']]
save('existing_cases.discovery.json',dict(search_order=[str(R),str(M),str(locked)],NLTLv2_first=first,MVP=dict(manifest_rows=len(manifestrows),distinct_cases=len({x['case_id'] for x in manifestrows}),manifest_requirements=len({x['requirement_id'] for x in manifestrows}),locks_verified=len(locks),lock_entries_checked=checked,lock_mismatches=badlocks,case_hash_or_provenance_failures=failures),locked_dataset=lockedproof,current_schema_identical_to_locked_R13=True,source_schema_verified_requirements=source_reviewed,eligible_with_verified_case_subsets=eligible,ready_with_current_scopes_and_evaluator=ready,important_correction='Prior claim that fifteen selected requirements lacked cases was too broad: original cases exist in MVP; most lack independently verified/source-compatible subsets, approved scopes or current evaluation integration.'))
save('MVP_fixture_lock_verification.json',locks);save('verified_existing_cases.evaluation_only.json',dict(label='EVALUATION_ONLY_NEVER_MODEL_INPUT',requirements=casegroups));save('verified_requirement_readiness.json',summaries)
print(json.dumps(dict(original_manifest_cases=len({x['case_id'] for x in manifestrows}),source_schema_verified_with_pairs=source_reviewed,eligible_verified_subsets=eligible,end_to_end_ready=ready,lock_mismatches=len(badlocks),case_failures=failures,summary=summaries),indent=2))
