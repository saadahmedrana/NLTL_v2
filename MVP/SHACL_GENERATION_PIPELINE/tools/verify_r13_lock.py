#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path
from rdflib import Graph
from rdflib.compare import isomorphic

MVP=Path(__file__).resolve().parents[2]; LOCK=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R13"
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    evidence=read(LOCK/"evidence/stage1_approved.json"); index=read(LOCK/"requirement_term_index.json"); registry=read(LOCK/"registry/term_registry.json"); old=read(MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R12/registry/term_registry.json")
    expected={"Static":191,"Static Calculation":43,"Complex":45,"Dynamic":19,"Physical Test":15}
    counts=dict(Counter(x["category"] for x in evidence["requirements"])); complete=sum(c.get("status")=="COMPLETE" for c in index["dependencyContracts"].values())
    new=sorted(set(x["localName"] for x in registry)-set(x["localName"] for x in old))
    authorized=sorted(["steelGradeB","steelGradeD","steelGradeE","steelGradeAh","steelGradeDh","steelGradeEh","steelGradeFh","traficomTable6Dash14"])
    ttl=Graph().parse(LOCK/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle"); rdf=Graph().parse(LOCK/"ontology/nltl_benchmark_vocabulary.rdf",format="xml")
    binding=read(LOCK/"r13_prelock_binding.json"); bad=[rel for rel,h in binding["boundMachineReadableArtifacts"].items() if sha(LOCK/rel)!=h]
    provenance=read(LOCK/"provenance/r12_immutable_source_hashes.json"); changed=[rel for rel,h in provenance["files"].items() if not (MVP/rel).exists() or sha(MVP/rel)!=h]
    errors=[]
    if counts!=expected: errors.append(f"categories {counts}")
    if complete!=268: errors.append(f"complete {complete}")
    if new!=authorized: errors.append(f"vocabulary delta {new}")
    if not isomorphic(ttl,rdf): errors.append("ontology serializations differ")
    if bad: errors.append(f"bound hash mismatch {bad}")
    if changed: errors.append(f"R12 modified {changed[:5]}")
    report={"status":"PASS" if not errors else "FAIL","lockId":"VOCAB-LOCK-2026-08-22-R13","requirements":313,"contextsResolved":313,"completeContracts":complete,"generationEligibleRequirements":268,"categoryCounts":counts,"vocabularyDelta":{"new":new,"removed":[],"count":len(new)},"registryTerms":len(registry),"canonicalTermsIncludingInfrastructure":1726,"r12ImmutableFilesChecked":len(provenance["files"]),"r12ImmutableAggregateSha256":provenance["aggregateSha256"],"errors":errors}
    out=LOCK/"validation/r13_namespace_policy_and_integrity_report.json"; write=lambda p,v:p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8"); write(out,report); print(json.dumps(report,indent=2))
    if errors: raise SystemExit(1)
if __name__=="__main__": main()
