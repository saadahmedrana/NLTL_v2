from __future__ import annotations

import argparse
import json
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate COMPLETE DIRECT_CALCULATION metadata.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    repository = VocabularyRepository(PipelineConfig.load(config_path))
    violations = []
    checked = 0
    for requirement_id, contract in sorted(repository.dependency_contracts.items()):
        if contract.get("status") != "COMPLETE" or contract.get("verificationMode") != "DIRECT_CALCULATION":
            continue
        checked += 1
        missing = [field for field in ("operandTerms", "resultTerms", "comparisonModel")
                   if not contract.get(field)]
        if missing:
            violations.append({"requirementId": requirement_id, "missingFields": missing})
    report = {
        "status": "PASS" if not violations else "FAIL",
        "lockId": repository.lock_info["lock_id"],
        "completeDirectCalculationContractsChecked": checked,
        "violationCount": len(violations),
        "violationRequirementIds": [row["requirementId"] for row in violations],
        "violations": violations,
        "rule": "COMPLETE DIRECT_CALCULATION requires non-empty operandTerms, resultTerms, and comparisonModel",
        "contractsModified": 0,
        "eligibilityModified": 0,
        "apiCalls": 0,
    }
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
