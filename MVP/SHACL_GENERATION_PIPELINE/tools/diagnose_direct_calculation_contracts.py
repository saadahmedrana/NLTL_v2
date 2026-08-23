from __future__ import annotations

import argparse
import json
from pathlib import Path

from nltl_pipeline.config import PipelineConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Report incomplete metadata in COMPLETE DIRECT_CALCULATION contracts")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    config = PipelineConfig.load(Path(args.config))
    index = json.loads(config.path("requirement_term_index").read_text(encoding="utf-8"))
    rows = []
    for rid, contract in sorted(index["dependencyContracts"].items()):
        if contract.get("status") != "COMPLETE" or contract.get("verificationMode") != "DIRECT_CALCULATION":
            continue
        missing = [field for field in ("operandTerms", "resultTerms", "comparisonModel") if not contract.get(field)]
        if missing:
            rows.append({"requirementId": rid, "missingFields": missing})
    report = {
        "status": "REPORT_ONLY",
        "lockId": index.get("sourceLockId"),
        "rule": "COMPLETE DIRECT_CALCULATION with empty operandTerms OR resultTerms OR comparisonModel",
        "diagnosticCount": len(rows),
        "requirementIds": [row["requirementId"] for row in rows],
        "findings": rows,
        "contractsModified": 0,
        "eligibilityModified": 0,
        "apiCalls": 0,
    }
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
