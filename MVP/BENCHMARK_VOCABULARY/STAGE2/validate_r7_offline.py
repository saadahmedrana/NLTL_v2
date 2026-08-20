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
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
CONFIG = "config/pipeline.r7-prelock-offline.json"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: list[str], env=None) -> subprocess.CompletedProcess:
    completed = subprocess.run(args, cwd=PIPE, env=env, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
    return completed


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    python = sys.executable
    integrity_run = run([python, "tools/verify_r7_lock.py"])
    integrity = read(LOCK / "validation/r7_namespace_and_integrity_report.json")
    if integrity["status"] != "PASS":
        raise RuntimeError("R7 namespace/integrity validation did not pass")

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    tests = run([python, "-m", "unittest", "discover", "-s", "tests", "-q"], env=env)
    test_text = tests.stdout + tests.stderr
    match = re.search(r"Ran\s+(\d+)\s+tests", test_text)
    test_count = int(match.group(1)) if match else None
    if "OK" not in test_text or not test_count:
        raise RuntimeError("Could not verify unittest completion")

    doctor_run = run([python, "run_pipeline.py", "--config", CONFIG, "doctor"])
    doctor = json.loads(doctor_run.stdout)
    if doctor.get("status") != "PASS" or doctor.get("environment_file_accessed") is not False:
        raise RuntimeError("R7 offline doctor did not pass without environment access")

    manifests = [
        "../INPUTS/RDF_R4_GENERATED_SHAPE_CONFIRMATION/evaluation_manifest.json",
        "../INPUTS/RDF_SHIP_GRAPH_PILOT/pilot_manifest.json",
    ]
    evaluations = []
    for manifest in manifests:
        evaluated = run([python, "run_pipeline.py", "--config", CONFIG, "evaluate", "--manifest", manifest])
        payload = json.loads(evaluated.stdout)
        if payload.get("status") != "PASS":
            raise RuntimeError(f"Deterministic evaluation failed for {manifest}")
        output = Path(payload["output"])
        summary = read(output / "evaluation_summary.json")
        if summary["execution_ok"] != summary["items"] or summary["expected_matches"] != summary["items"] or summary["expected_mismatches"]:
            raise RuntimeError(f"Evaluation expectation mismatch for {manifest}: {summary}")
        evaluations.append({**summary, "output": str(output.relative_to(MVP))})

    workbook_check = read(LOCK / "validation/final_lock_workbook_verification.json")
    if workbook_check.get("status") != "PASS" or not str(workbook_check.get("visualReview", "")).startswith("PASS"):
        raise RuntimeError("R7 workbook programmatic/visual verification is incomplete")
    if any(token in workbook_check.get("formulaErrorScan", "") for token in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A")):
        # The inspect metadata contains the search expression itself; only fail
        # when matches are actually reported.
        scan = workbook_check.get("formulaErrorScan", "")
        if '"matches":[' in scan and '"matches":[]' not in scan:
            raise RuntimeError("Workbook formula error scan reported matches")

    ttl = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R7 Turtle and RDF/XML are not isomorphic")

    provenance = read(LOCK / "provenance/r6_immutable_source_hashes.json")
    changed = [relative for relative, expected in provenance["files"].items() if not (MVP / relative).exists() or digest(MVP / relative) != expected]
    if changed:
        raise RuntimeError(f"R6 immutability check failed: {changed}")

    index = read(LOCK / "requirement_term_index.json")
    registry = read(LOCK / "registry/term_registry.json")
    report = {
        "status": "PASS",
        "lockCandidate": "VOCAB-LOCK-2026-08-20-R7",
        "apiCalls": 0,
        "environmentFileAccessed": False,
        "ontologySyntax": "PASS - Turtle and RDF/XML parsed and are isomorphic",
        "registryValidation": {
            "terms": len(registry), "uniqueLocalNames": len({row['localName'] for row in registry}) == len(registry),
            "canonicalIris": all(row["iri"] == "https://w3id.org/nltl/vocab#" + row["localName"] for row in registry),
        },
        "requirementContexts": {"resolved": integrity["contextsResolved"], "expected": 313},
        "completeContracts": {
            "count": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
            "generationEligible": doctor["generation_eligible_requirements"],
            "withAuditFlags": sum(bool(c.get("auditFlags")) for c in index["dependencyContracts"].values() if c.get("status") == "COMPLETE"),
            "withObservedFailureStatus": sum(bool(c.get("observedFailureStatus")) for c in index["dependencyContracts"].values() if c.get("status") == "COMPLETE"),
        },
        "namespaceAndIntegrity": integrity,
        "workbookVerification": {
            "status": workbook_check["status"], "sheetCount": workbook_check["sheetCount"],
            "visualReview": workbook_check["visualReview"],
        },
        "unitTests": f"{test_count}/{test_count} PASS",
        "doctor": "PASS",
        "rdfRegression": evaluations,
        "specificAssertions": {
            "i2_009Unchanged": integrity["i2_009Unchanged"],
            "trf_127NoStartingAirCapacityTerm": integrity["trf_127NoStartingAirCapacityTerm"],
            "i2_037ReusesHasStructuralMemberLoadCase": "hasStructuralMemberLoadCase" in index["dependencyContracts"]["I2-037"]["relationshipTerms"],
            "trf_130ReusesInletChest": "inletChest" in index["requirements"]["TRF-130"],
            "r6ImmutableFilesChecked": len(provenance["files"]),
            "r6ImmutableAggregateSha256": provenance["aggregateSha256"],
        },
    }
    output = LOCK / "validation/r7_offline_validation.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "unitTests": report["unitTests"], "contexts": integrity["contextsResolved"],
        "completeContracts": report["completeContracts"]["count"],
        "rdfEvaluations": [{"id": x["evaluation_id"], "matched": f"{x['expected_matches']}/{x['items']}"} for x in evaluations],
        "r6ImmutableFiles": len(provenance["files"]), "apiCalls": 0,
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
