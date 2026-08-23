from __future__ import annotations

import hashlib
import json
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    manifest_path = LOCK / "prelock_manifest.json"
    binding_path = LOCK / "r11_prelock_binding.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relatives = set(manifest["boundArtifacts"])
    relatives.add("validation/r11_direct_calculation_completeness_diagnostic.json")
    bound = {relative: sha(LOCK / relative) for relative in sorted(relatives)}
    manifest["boundArtifacts"] = bound
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["boundMachineReadableArtifacts"] = bound
    binding["boundRequirementIndex"] = {"requirement_term_index.json": bound["requirement_term_index.json"]}
    write(manifest_path, manifest)
    write(binding_path, binding)
    print(json.dumps({"status": "PASS", "boundArtifacts": len(bound)}, indent=2))


if __name__ == "__main__":
    main()
