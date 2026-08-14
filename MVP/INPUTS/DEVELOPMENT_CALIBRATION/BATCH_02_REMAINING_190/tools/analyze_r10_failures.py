from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
MVP = BATCH.parents[2]
RUNS = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r9/runs"
R9 = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R9_FOUNDATION"
SESSION = "SESSION-BATCH-20260813T151944473992Z"


def classify(feedback: str, status: str) -> list[str]:
    text = feedback.lower()
    rules = {
        "MISSING_RELATIONSHIP_OR_PATH": ("relationship", "ship-to-", "linking", "connecting"),
        "WRONG_OWNER_OR_DOMAIN": ("-owned", "domain mismatch", "must not be moved", "scoped to"),
        "MISSING_FORMULA_OPERAND_OR_RESULT": ("operand", "formula", "result property", "quantity result"),
        "MISSING_TABLE_MODEL": ("table", "lookup", "selector"),
        "MISSING_BRANCH_OR_CONTROLLED_VALUE": ("branch", "controlled", "selector", "applicability"),
        "MISSING_EVIDENCE_MODEL": ("evidence", "approval", "record"),
        "GENERATOR_LOGIC_ONLY": ("remove sh:mincount", "presence-only", "accidental", "exact equality"),
        "CONTRACT_ROLE_ERROR": ("complete dependency contract", "declared", "wrong result"),
    }
    found = [name for name, words in rules.items() if any(word in text for word in words)]
    if status == "TERM_RESOLUTION_UNRESOLVED":
        found.append("VOCABULARY_OR_GRAPH_MODEL_GAP")
    return sorted(set(found)) or ["ENGINEERING_REVIEW"]


def main() -> None:
    evidence = {item["id"]: item for item in json.loads((R9 / "evidence/stage1_approved.json").read_text())["requirements"]}
    index = json.loads((R9 / "requirement_term_index.json").read_text())
    records = []
    calls = []
    for directory in sorted(RUNS.iterdir()):
        event_path = directory / "events.jsonl"
        if not event_path.exists():
            continue
        events = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
        if not events or events[0].get("session_id") != SESSION:
            continue
        start = next(event for event in events if event["event_type"] == "run_started")
        finish = next(event for event in reversed(events) if event["event_type"] == "run_finished")
        calls.extend(event for event in events if event["event_type"] == "api_call_completed")
        if finish.get("accepted"):
            continue
        rid = start["requirement_id"]
        req = evidence[rid]
        record = {
            "requirement_id": rid,
            "source_sheet": req.get("sourceSheet", ""),
            "page": req.get("page", ""),
            "clause": req.get("clause", ""),
            "encoding_pattern": req.get("encodingPattern", ""),
            "status": finish.get("status", ""),
            "attempts": finish.get("attempts", 0),
            "root_causes": classify(str(finish.get("final_feedback", "")), str(finish.get("status", ""))),
            "final_feedback": finish.get("final_feedback", ""),
            "normalized_requirement": req.get("normalizedRequirement", ""),
            "r9_contract": index["dependencyContracts"].get(rid, {}),
            "run_directory": str(directory.relative_to(MVP)),
            "engineering_decision": "PENDING_R10_REPAIR",
        }
        records.append(record)
    status_counts = Counter(item["status"] for item in records)
    cause_counts = Counter(cause for item in records for cause in item["root_causes"])
    role_counts = Counter(item.get("role", "") for item in calls)
    payload = {
        "analysis_id": "R10-R9-CONFIRMATION-FAILURE-RECONSTRUCTION-V1",
        "session_id": SESSION,
        "run_count": 112,
        "failure_count": len(records),
        "status_counts": dict(status_counts),
        "cause_counts": dict(cause_counts),
        "api_calls": len(calls),
        "api_role_counts": dict(role_counts),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in calls),
        "records": records,
    }
    (BATCH / "r10_failure_analysis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
    fields = ["requirement_id", "source_sheet", "page", "clause", "encoding_pattern", "status", "attempts", "root_causes", "final_feedback", "normalized_requirement", "run_directory", "engineering_decision"]
    with (BATCH / "r10_failure_analysis.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in records:
            row = {key: item[key] for key in fields}; row["root_causes"] = " | ".join(item["root_causes"]); writer.writerow(row)
    print(json.dumps({"failures": len(records), "statuses": status_counts, "causes": cause_counts, "api_calls": len(calls), "tokens": payload["total_tokens"]}, indent=2))


if __name__ == "__main__":
    main()
