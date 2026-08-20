from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
PIPE = MVP / "SHACL_GENERATION_PIPELINE"
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
CONFIG = "config/pipeline.r8-prelock-offline.json"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: list[str], env=None) -> subprocess.CompletedProcess:
    completed = subprocess.run(args, cwd=PIPE, env=env, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{completed.stdout}\n{completed.stderr}")
    return completed


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    python = sys.executable
    run([python, "tools/verify_r8_lock.py"])
    integrity = read(LOCK / "validation/r8_namespace_policy_and_integrity_report.json")
    if integrity["status"] != "PASS":
        raise RuntimeError("R8 integrity verification failed")

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    tests = run([python, "-m", "unittest", "discover", "-s", "tests", "-q"], env=env)
    text = tests.stdout + tests.stderr
    match = re.search(r"Ran\s+(\d+)\s+tests", text)
    test_count = int(match.group(1)) if match else 0
    if not test_count or "OK" not in text:
        raise RuntimeError("Offline test suite did not complete")

    doctor = json.loads(run([python, "run_pipeline.py", "--config", CONFIG, "doctor"]).stdout)
    if doctor.get("status") != "PASS" or doctor.get("environment_file_accessed") is not False:
        raise RuntimeError("R8 doctor failed or accessed environment")

    evaluations = []
    for manifest in (
        "../INPUTS/RDF_R4_GENERATED_SHAPE_CONFIRMATION/evaluation_manifest.json",
        "../INPUTS/RDF_SHIP_GRAPH_PILOT/pilot_manifest.json",
    ):
        result = json.loads(run([python, "run_pipeline.py", "--config", CONFIG,
                                 "evaluate", "--manifest", manifest]).stdout)
        if result.get("status") != "PASS":
            raise RuntimeError(f"RDF regression failed: {manifest}")
        output = Path(result["output"])
        summary = read(output / "evaluation_summary.json")
        if summary["execution_ok"] != summary["items"] or summary["expected_matches"] != summary["items"]:
            raise RuntimeError(f"RDF expectation mismatch: {manifest}")
        evaluations.append({**summary, "output": str(output.relative_to(MVP))})

    ttl = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R8 ontology serializations are not isomorphic")

    workbook = read(LOCK / "validation/final_lock_workbook_verification.json")
    if workbook.get("status") != "PASS" or not workbook.get("visualReview", "").startswith("PASS"):
        raise RuntimeError("Workbook verification is incomplete")
    provenance = read(LOCK / "provenance/r7_immutable_source_hashes.json")
    changed = [relative for relative, expected in provenance["files"].items()
               if not (MVP / relative).exists() or digest(MVP / relative) != expected]
    if changed:
        raise RuntimeError(f"R7 immutability failure: {changed[:10]}")

    report = {
        "status": "PASS",
        "lockCandidate": "VOCAB-LOCK-2026-08-20-R8",
        "apiCalls": 0,
        "environmentFileAccessed": False,
        "categoryCounts": integrity["categoryCounts"],
        "reclassifiedRequirements": integrity["reclassifiedCount"],
        "requirements": integrity["requirements"],
        "requirementContexts": {"resolved": integrity["contextsResolved"], "expected": 313},
        "completeContracts": integrity["completeContracts"],
        "generationEligibleRequirements": integrity["generationEligibleRequirements"],
        "complex": integrity["complex"],
        "ontologySyntax": "PASS - Turtle and RDF/XML parsed and are isomorphic",
        "ontologyChangedFromR7": False,
        "registryChangedFromR7": False,
        "unitTests": f"{test_count}/{test_count} PASS",
        "doctor": "PASS",
        "rdfRegression": evaluations,
        "workbookVerification": {
            "status": workbook["status"], "sheetCount": workbook["sheetCount"],
            "visualReview": workbook["visualReview"],
        },
        "r7ImmutableFilesChecked": len(provenance["files"]),
        "r7ImmutableAggregateSha256": provenance["aggregateSha256"],
    }
    output = LOCK / "validation/r8_offline_validation.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "unitTests": report["unitTests"],
        "contexts": integrity["contextsResolved"], "eligible": integrity["generationEligibleRequirements"],
        "complex": integrity["complex"],
        "rdfEvaluations": [{"id": x["evaluation_id"], "matched": f"{x['expected_matches']}/{x['items']}"} for x in evaluations],
        "r7ImmutableFiles": len(provenance["files"]), "apiCalls": 0,
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
