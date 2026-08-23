from __future__ import annotations

import hashlib
import json
from pathlib import Path

from promote_r12_direct_calculation_metadata import CALCULATION_METADATA


MVP = Path(__file__).resolve().parents[2]
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R12"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    decisions_path = LOCK / "registry/r12_direct_calculation_metadata_decisions.json"
    decisions = read(decisions_path)
    decisions["calculationMetadata"] = {
        rid: {"operandTerms": operands, "resultTerms": results}
        for rid, (operands, results) in sorted(CALCULATION_METADATA.items())
    }
    decisions["specifiedMetadataRequirementCount"] = len(CALCULATION_METADATA)
    write(decisions_path, decisions)

    manifest_path = LOCK / "prelock_manifest.json"
    binding_path = LOCK / "r12_prelock_binding.json"
    manifest = read(manifest_path)
    relatives = set(manifest["boundArtifacts"])
    relatives.add("validation/r12_direct_calculation_completeness.json")
    bound = {relative: sha(LOCK / relative) for relative in sorted(relatives)}
    manifest["boundArtifacts"] = bound
    binding = read(binding_path)
    binding["boundMachineReadableArtifacts"] = bound
    binding["boundRequirementIndex"] = {"requirement_term_index.json": bound["requirement_term_index.json"]}
    write(manifest_path, manifest)
    write(binding_path, binding)
    print(json.dumps({"status": "PASS", "boundArtifacts": len(bound),
                      "metadataRequirements": len(CALCULATION_METADATA)}, indent=2))


if __name__ == "__main__":
    main()
