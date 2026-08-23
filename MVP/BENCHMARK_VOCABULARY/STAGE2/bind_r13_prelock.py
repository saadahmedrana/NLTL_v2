from __future__ import annotations
import hashlib, json
from pathlib import Path

MVP=Path(__file__).resolve().parents[2]; LOCK=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R13"
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=read(LOCK/"prelock_manifest.json")
    relatives=set(manifest["boundArtifacts"])
    relatives.update({"validation/r13_structured_table_reference_validation.json","validation/r13_direct_calculation_completeness.json","validation/final_lock_workbook_verification.json"})
    bound={rel:sha(LOCK/rel) for rel in sorted(relatives)}
    manifest["boundArtifacts"]=bound; write(LOCK/"prelock_manifest.json",manifest)
    binding=read(LOCK/"r13_prelock_binding.json"); binding["workbook"]="benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.xlsx"; binding["workbookSha256"]=sha(LOCK/binding["workbook"]); binding["boundMachineReadableArtifacts"]=bound; binding["boundRequirementIndex"]={"requirement_term_index.json":bound["requirement_term_index.json"]}; write(LOCK/"r13_prelock_binding.json",binding)
    print(json.dumps({"status":"PASS","boundArtifacts":len(bound),"workbookSha256":binding["workbookSha256"]},indent=2))
if __name__=="__main__": main()
