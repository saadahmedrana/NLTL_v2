from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
from rdflib import Graph
from rdflib.compare import isomorphic

MVP=Path(__file__).resolve().parents[2]; LOCK=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R13"; BASE="benchmark_vocabulary_stage2_LOCK-2026-08-22-R13"; LOCK_ID="VOCAB-LOCK-2026-08-22-R13"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def main():
    workbook=LOCK/f"{BASE}.xlsx"; workbook_check=LOCK/"validation/final_lock_workbook_verification.json"; offline=LOCK/"validation/r13_offline_validation.json"; integrity=LOCK/"validation/r13_namespace_policy_and_integrity_report.json"; provenance=LOCK/"provenance/r12_immutable_source_hashes.json"
    for p in (workbook,workbook_check,offline,integrity,provenance):
        if not p.exists(): raise FileNotFoundError(p)
    if read(workbook_check).get("status")!="PASS" or not read(workbook_check).get("visualReview","").startswith("PASS"): raise RuntimeError("workbook verification incomplete")
    report=read(offline); integ=read(integrity)
    if report.get("status")!="PASS" or integ.get("status")!="PASS": raise RuntimeError("offline verification incomplete")
    ttl=Graph().parse(LOCK/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle"); rdf=Graph().parse(LOCK/"ontology/nltl_benchmark_vocabulary.rdf",format="xml")
    if not isomorphic(ttl,rdf): raise RuntimeError("ontology serializations differ")
    prelock=read(LOCK/"prelock_manifest.json"); bound={rel:sha(LOCK/rel) for rel in prelock["boundArtifacts"]}
    for rel in ("validation/r13_namespace_policy_and_integrity_report.json","validation/r13_offline_validation.json"): bound[rel]=sha(LOCK/rel)
    pipeline=MVP/"SHACL_GENERATION_PIPELINE"; prompts={x:sha(pipeline/"prompts"/x) for x in ("r11/generator.txt","r11/validator.txt","vocabulary_matcher.txt","control_v1_3/syntax_repair.txt")}; sources={x:sha(pipeline/x) for x in ("src/nltl_pipeline/retrieval/context.py","src/nltl_pipeline/retrieval/fewshot.py","src/nltl_pipeline/validation/shacl.py","src/nltl_pipeline/prompts.py","src/nltl_pipeline/orchestration/runner.py","src/nltl_pipeline/api/client.py","src/nltl_pipeline/config.py")}
    registry=read(LOCK/"registry/term_registry.json"); decisions=read(LOCK/"registry/r13_narrow_source_correction_decisions.json"); prov=read(provenance)
    lock={"lockId":LOCK_ID,"status":"LOCKED_NARROW_SOURCE_GROUNDED_CORRECTIONS_R13","lockedDate":"2026-08-22","revision":"R13","vocabularyVersion":"2.23.0-stage2-final-r13","supersedes":"VOCAB-LOCK-2026-08-21-R12","canonicalVocabularyNamespace":"https://w3id.org/nltl/vocab#","workbook":workbook.name,"workbookSha256":sha(workbook),"counts":{"requirements":313,"generationEligibleRequirements":268,"completeDependencyContracts":268,"registryTerms":len(registry),"canonicalTermsIncludingInfrastructure":1726,"categoryChanges":0,"fewShotExamples":22,"newVocabularyTerms":8,"removedVocabularyTerms":0,"modifiedVocabularyTerms":1},"categoryCounts":report["categoryCounts"],"newCanonicalTerms":decisions["newCanonicalTerms"],"affectedRequirements":decisions["affectedRequirements"],"tableReferenceCompleteness":{"contractsChecked":2,"violations":0,"blockingForFutureLocks":True},"boundMachineReadableArtifacts":bound,"boundRequirementIndex":{"requirement_term_index.json":bound["requirement_term_index.json"]},"promptSha256":prompts,"pipelineSourceSha256":sources,"r12ImmutableSource":{"fileCount":prov["fileCount"],"aggregateSha256":prov["aggregateSha256"]},"offlineVerification":report,"apiCallsDuringPromotion":0}
    lock_path=LOCK/f"{BASE}.lock.json"; sha_path=LOCK/f"{BASE}.sha256"
    if lock_path.exists() or sha_path.exists(): raise FileExistsError("Refusing to overwrite finalized R13")
    write(lock_path,lock); lines=[f"{sha(workbook)}  {workbook.name}",f"{sha(lock_path)}  {lock_path.name}"]+[f"{h}  {rel}" for rel,h in sorted(bound.items())]; sha_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    for source in (workbook,lock_path,sha_path):
        target=MVP/source.name
        if target.exists(): raise FileExistsError(target)
        shutil.copy2(source,target)
    print(json.dumps({"status":"LOCKED","lockId":LOCK_ID,"workbookSha256":lock["workbookSha256"],"lockJsonSha256":sha(lock_path),"checksumManifestSha256":sha(sha_path),"registrySha256":bound["registry/term_registry.json"],"ontologyTurtleSha256":bound["ontology/nltl_benchmark_vocabulary.ttl"],"ontologyRdfXmlSha256":bound["ontology/nltl_benchmark_vocabulary.rdf"],"requirementIndexSha256":bound["requirement_term_index.json"],"requirementEvidenceSha256":bound["evidence/stage1_approved.json"],"verificationPolicySha256":bound["evidence/verification_policy_r13.json"],"r12ImmutableAggregateSha256":prov["aggregateSha256"],"apiCalls":0},indent=2))
if __name__=="__main__": main()
