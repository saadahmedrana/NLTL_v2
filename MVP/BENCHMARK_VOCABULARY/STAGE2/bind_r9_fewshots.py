from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES"
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
TARGET = LOCK / "few_shots"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith(".pyc")}


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite R9 few-shot snapshot: {TARGET}")
    validation = read(SOURCE / "validation_report.json")
    catalog = read(SOURCE / "catalog.json")
    if not validation.get("allChecksPassed") or catalog.get("exampleCount") != 22:
        raise RuntimeError("Few-shot library must have 22 fully validated examples before R9 binding")
    required = {"FS-COMPLEX-READINESS-01", "FS-COMPLEX-READINESS-02"}
    if not required.issubset({row["exampleId"] for row in catalog["examples"]}):
        raise RuntimeError("Required R9 Complex-readiness examples are absent")
    shutil.copytree(SOURCE, TARGET, ignore=ignore)

    relative_hashes = {
        str(path.relative_to(LOCK)): sha(path)
        for path in sorted(TARGET.rglob("*")) if path.is_file()
    }
    binding = read(LOCK / "r9_prelock_binding.json")
    binding["boundMachineReadableArtifacts"].update(relative_hashes)
    write(LOCK / "r9_prelock_binding.json", binding)
    prelock = read(LOCK / "prelock_manifest.json")
    prelock["boundArtifacts"].update(relative_hashes)
    prelock["fewShotLibrary"] = {
        "exampleCount": 22,
        "newExampleIds": sorted(required),
        "validationStatus": "PASS",
        "snapshotFileCount": len(relative_hashes),
    }
    write(LOCK / "prelock_manifest.json", prelock)
    print(json.dumps({
        "status": "PASS", "exampleCount": 22,
        "snapshotFileCount": len(relative_hashes),
        "target": str(TARGET),
    }, indent=2))


if __name__ == "__main__":
    main()
