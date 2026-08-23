from __future__ import annotations

import hashlib, json, sys
from collections import Counter
from pathlib import Path
from rdflib import Graph
from rdflib.compare import isomorphic

MVP=Path(__file__).resolve().parents[2]; PIPE=MVP/"SHACL_GENERATION_PIPELINE"
R12=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R12"; R11=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
EXPECTED={"Static":191,"Static Calculation":43,"Complex":45,"Dynamic":19,"Physical Test":15}
EXPECTED_STATUS={"Static":(191,190,190,1),"Static Calculation":(43,41,41,2),"Complex":(45,37,37,8),"Dynamic":(19,0,0,19),"Physical Test":(15,0,0,15)}
def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    errors=[]; evidence=read(R12/"evidence/stage1_approved.json"); old=read(R11/"evidence/stage1_approved.json")
    index=read(R12/"requirement_term_index.json"); by={r["id"]:r for r in evidence["requirements"]}; before={r["id"]:r for r in old["requirements"]}
    changed={rid for rid in by if by[rid]["category"]!=before[rid]["category"]}; counts=dict(Counter(r["category"] for r in evidence["requirements"]))
    if changed!={"TRF-055"}: errors.append(f"category delta differs: {sorted(changed)}")
    if counts!=EXPECTED: errors.append(f"category counts differ: {counts}")
    invariant=("registry/term_registry.json","registry/term_registry.csv","ontology/nltl_benchmark_vocabulary.ttl","ontology/nltl_benchmark_vocabulary.rdf")
    for rel in invariant:
        if (R11/rel).read_bytes()!=(R12/rel).read_bytes(): errors.append(f"vocabulary artifact differs: {rel}")
    registry=read(R12/"registry/term_registry.json")
    if len({r["localName"] for r in registry})!=len(registry): errors.append("registry local-name collision")
    if not isomorphic(Graph().parse(R12/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle"),Graph().parse(R12/"ontology/nltl_benchmark_vocabulary.rdf",format="xml")): errors.append("ontology serializations not isomorphic")
    binding=read(R12/"r12_prelock_binding.json"); bound_checked=0
    for rel,expected in binding["boundMachineReadableArtifacts"].items():
        bound_checked+=1
        if not (R12/rel).exists() or sha(R12/rel)!=expected: errors.append(f"prelock hash mismatch: {rel}")
    provenance=read(R12/"provenance/r11_immutable_source_hashes.json")
    changed_r11=[rel for rel,expected in provenance["files"].items() if not (MVP/rel).exists() or sha(MVP/rel)!=expected]
    if changed_r11: errors.append(f"R11 immutability failure: {changed_r11[:10]}")
    sys.path.insert(0,str(PIPE/"src")); from nltl_pipeline.config import PipelineConfig; from nltl_pipeline.retrieval.context import VocabularyRepository
    repo=VocabularyRepository(PipelineConfig.load(PIPE/"config/pipeline.r12-prelock-offline.json")); resolved=0
    for rid in sorted(repo.requirements):
        try: repo.build_context_pack(rid); resolved+=1
        except Exception as exc: errors.append(f"context failure {rid}: {exc}")
    category_status={}
    for category,expected in EXPECTED_STATUS.items():
        ids={rid for rid,row in by.items() if row["category"]==category}; complete={rid for rid in ids if index["dependencyContracts"][rid].get("status")=="COMPLETE"}; eligible={rid for rid in ids if repo.is_generation_eligible(by[rid])}; actual=(len(ids),len(complete),len(eligible),len(ids-eligible))
        if actual!=expected: errors.append(f"{category} status differs: {actual}")
        category_status[category]={"total":actual[0],"complete":actual[1],"generationEligible":actual[2],"deferred":actual[3],"deferredRequirementIds":sorted(ids-eligible)}
    decisions=read(R12/"registry/r12_direct_calculation_metadata_decisions.json")
    if decisions.get("specifiedMetadataRequirementCount")!=22: errors.append("specified metadata count differs")
    for rid,expected in decisions.get("calculationMetadata",{}).items():
        c=index["dependencyContracts"][rid]
        if c.get("operandTerms")!=expected["operandTerms"]: errors.append(f"operandTerms differ: {rid}")
        if c.get("resultTerms")!=expected["resultTerms"]: errors.append(f"resultTerms differ: {rid}")
    c=index["dependencyContracts"]["TRF-055"]
    if c.get("verificationMode")!="DIRECT_STATIC" or c.get("operandTerms") or c.get("resultTerms"): errors.append("TRF-055 mode/metadata differs")
    for text in ("actualSectionModulus >= requiredSectionModulus","actualShearArea >= requiredShearArea","0.10 <= permittedReducedLineLoad < 0.15","reducedLineLoadApprovedByClassificationSociety = true"):
        if text not in c.get("comparisonModel",""): errors.append(f"TRF-055 comparison missing: {text}")
    for section in (index["requirements"]["TRF-059"],index["termOwners"]["TRF-059"],index["dependencyContracts"]["TRF-059"].get("legacyIndexedTerms",[])):
        if "sectionModulus" in section: errors.append("TRF-059 retains stale sectionModulus")
    violations=[]; calc_checked=0
    for rid,c in index["dependencyContracts"].items():
        if c.get("status")=="COMPLETE" and c.get("verificationMode")=="DIRECT_CALCULATION":
            calc_checked+=1; missing=[f for f in ("operandTerms","resultTerms","comparisonModel") if not c.get(f)]
            if missing: violations.append({"requirementId":rid,"missingFields":missing})
    if violations: errors.append(f"calculation metadata violations: {violations}")
    diagnostic=read(R12/"validation/r12_direct_calculation_completeness.json")
    if diagnostic.get("violationCount")!=0 or diagnostic.get("completeDirectCalculationContractsChecked")!=41: errors.append("stored calculation validation differs")
    r11_lock=read(R11/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.lock.json"); api="src/nltl_pipeline/api/client.py"
    if sha(PIPE/api)!=r11_lock["pipelineSourceSha256"][api]: errors.append("API client changed from R11")
    workbook=read(R12/"validation/final_lock_workbook_verification.json")
    if workbook.get("status")!="PASS" or not workbook.get("visualReview","").startswith("PASS"): errors.append("workbook verification incomplete")
    lock_path=R12/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R12.lock.json"; sum_path=R12/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R12.sha256"; checksum_entries=0
    if lock_path.exists() or sum_path.exists():
        if not lock_path.exists() or not sum_path.exists(): errors.append("final lock/checksum pair incomplete")
        else:
            for line in sum_path.read_text().splitlines():
                expected,rel=line.split("  ",1); checksum_entries+=1
                if not (R12/rel).exists() or sha(R12/rel)!=expected: errors.append(f"checksum mismatch: {rel}")
            for name in (lock_path.name,sum_path.name,read(lock_path)["workbook"]):
                if not (MVP/name).exists() or (MVP/name).read_bytes()!=(R12/name).read_bytes(): errors.append(f"root artifact mismatch: {name}")
    report={"status":"PASS" if not errors else "FAIL","lockCandidate":"VOCAB-LOCK-2026-08-21-R12","requirements":len(by),"contextsResolved":resolved,"categoryChanges":len(changed),"categoryCounts":counts,"categoryStatus":category_status,"completeContracts":sum(c.get("status")=="COMPLETE" for c in index["dependencyContracts"].values()),"generationEligibleRequirements":sum(repo.is_generation_eligible(row) for row in by.values()),"registryTerms":len(registry),"vocabularyDelta":{"new":0,"removed":0,"modified":0},"completeDirectCalculationContractsChecked":calc_checked,"directCalculationViolations":violations,"boundHashesChecked":bound_checked,"finalChecksumEntriesChecked":checksum_entries,"r11ImmutableFilesChecked":len(provenance["files"]),"r11ImmutableAggregateSha256":provenance["aggregateSha256"],"apiClientUnchanged":True,"apiCalls":0,"errors":errors}
    output=R12/"validation/r12_namespace_policy_and_integrity_report.json"
    if not lock_path.exists(): output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,indent=2)); return 0 if not errors else 1

if __name__=="__main__": raise SystemExit(main())
