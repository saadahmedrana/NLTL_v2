#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    config = PipelineConfig.load(Path(args.config))
    vocabulary = VocabularyRepository(config)
    checked: list[str] = []
    violations: list[dict[str, str]] = []
    for requirement_id, contract in sorted(vocabulary.dependency_contracts.items()):
        model = contract.get("tableModel")
        if contract.get("status") != "COMPLETE" or not isinstance(model, dict):
            continue
        if model.get("structured") is not True or not model.get("canonicalTableReference"):
            continue
        checked.append(requirement_id)
        try:
            vocabulary.validate_dependency_contract(requirement_id)
        except Exception as exc:  # deterministic reporting boundary
            violations.append({"requirementId": requirement_id, "error": str(exc)})
    report = {
        "status": "PASS" if not violations else "FAIL",
        "contractsChecked": checked,
        "checkedCount": len(checked),
        "violationCount": len(violations),
        "violations": violations,
    }
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
