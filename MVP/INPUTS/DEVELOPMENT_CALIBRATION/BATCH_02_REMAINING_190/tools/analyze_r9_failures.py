from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parent
PROJECT_ROOT = BATCH_ROOT.parents[2]
RUNS_ROOT = PROJECT_ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
QUEUE_PATH = BATCH_ROOT / "generation_queue.json"
DEV_ROOT = PROJECT_ROOT / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R8_1_POSTCONFIRMATION"
EVIDENCE_PATH = DEV_ROOT / "evidence/stage1_approved.json"
INDEX_PATH = DEV_ROOT / "requirement_term_index.json"
SESSION_ID = "SESSION-BATCH-20260813T091540611845Z"


CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("MISSING_FORMULA_OPERAND", ("missing formula operand", "formula operands", "omitted operands", "absent operand", "all missing operands")),
    ("MISSING_FORMULA_RESULT", ("result property", "computed result property", "calculated result", "force-result", "reported design")),
    ("MISSING_BRANCH_SELECTOR", ("branch-selection", "branch selector", "applicability evidence", "conditional evidence", "selector")),
    ("CONTROLLED_VALUE_REQUIRED", ("controlled value", "controlled steel-grade", "regulatory ordering", "string-valued", "unrestricted provisional string")),
    ("NUMERIC_QUANTITY_REQUIRED", ("numeric quantity", "numeric property", "quantity range", "compatible units", "force quantity range", "pressure quantity")),
    ("MISSING_RELATIONSHIP_PATH", ("relationship", "inventory path", "inventory relationship", "ship-to-", "membership", "per-lifeboat", "per-antenna", "per-craft")),
    ("MISSING_CASE_OR_ASSIGNMENT_NODE", ("case-specific", "load-case", "calculation case", "assignment", "pair each", "case-owned", "per-person", "item/case")),
    ("MISSING_EVIDENCE_MODEL", ("evidence", "approval", "certificate", "document", "recorded distance", "design evidence")),
    ("INCOMPLETE_INDEX_OR_CONTEXT", ("only candidate", "only the", "supplied terms", "supplied candidate", "candidates do not", "available terms")),
    ("GENERATOR_INCOMPLETE_LOGIC", ("presence-only", "only part", "omits", "does not encode", "complete requirement", "full regulatory alternative")),
    ("GENERATOR_CONDITIONAL_LOGIC", ("accidental pass", "missing selector", "sh:or", "non-applicable branch", "conjunctively", "conditional alternatives")),
    ("GENERATOR_FORMULA_LOGIC", ("expected result", "exact equality", "tolerance", "formula-derived constraint", "linear interpolation")),
    ("GENERATOR_SPARQL_LOGIC", ("pre-bound", "grouped directly", "aggregation", "bounded sparql", "combinatorial")),
    ("GENERATOR_ALL_VALUES_LOGIC", ("all supplied", "every", "universal constraint", "all-values", "existence test", "qualifiedmincount")),
    ("OVERLOADED_OR_WRONG_TERM", ("must not be substituted", "different requirement", "different distance", "too broad", "generic thickness", "does not distinguish", "explicitly unsuitable")),
]


def load_session_events() -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for path in RUNS_ROOT.glob("RUN-*/events.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("session_id") == SESSION_ID:
                event["_event_file"] = str(path.relative_to(PROJECT_ROOT))
                events.append(event)
    return events


def categories(feedback: str, status: str) -> list[str]:
    lower = feedback.lower()
    result = [name for name, needles in CATEGORY_RULES if any(needle in lower for needle in needles)]
    if status == "TERM_RESOLUTION_UNRESOLVED":
        result.append("VOCABULARY_OR_MODEL_GAP")
    if status == "MAX_ATTEMPTS_REACHED":
        result.append("GENERATION_OR_CONTEXT_REPAIR")
    return sorted(set(result)) or ["MANUAL_ENGINEERING_REVIEW"]


def extract_requested_symbols(feedback: str) -> list[str]:
    tokens: set[str] = set()
    patterns = (
        r"\b[A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9.]+)+\b",
        r"\b[a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9.]+\b",
        r"\b(?:Omega|gamma|sigma|phi|Delta|DUI|FIB|PPF|CFC|DF|tnet)\b",
    )
    for pattern in patterns:
        tokens.update(re.findall(pattern, feedback))
    return sorted(tokens)


def main() -> None:
    events = load_session_events()
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))["requirements"]
    evidence_payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    requirements = {item["id"]: item for item in evidence_payload["requirements"]}
    index_payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    run_finished = {event["requirement_id"]: event for event in events if event.get("event_type") == "run_finished"}
    by_requirement: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for event in events:
        rid = str(event.get("requirement_id", ""))
        if rid:
            by_requirement[rid].append(event)

    records: list[dict[str, object]] = []
    for rid in queue:
        final = run_finished[rid]
        if final.get("accepted") is True:
            continue
        req_events = by_requirement[rid]
        iterations = [event for event in req_events if event.get("event_type") == "iteration_completed"]
        validations = [event for event in req_events if event.get("event_type") == "validation_completed"]
        matcher_calls = [event for event in req_events if event.get("event_type") == "api_call_completed" and event.get("role") == "vocabulary_matcher"]
        feedback = str(final.get("final_feedback", ""))
        req = requirements[rid]
        indexed = list(index_payload["requirements"].get(rid, []))
        ownership = dict(index_payload.get("termOwners", {}).get(rid, {}))
        record = {
            "requirement_id": rid,
            "source_sheet": req.get("sourceSheet", ""),
            "page": req.get("page", ""),
            "clause": req.get("clause", ""),
            "category": req.get("category", ""),
            "encoding_pattern": req.get("encodingPattern", ""),
            "status": final.get("status", ""),
            "attempts": final.get("attempts", 0),
            "matcher_calls": len(matcher_calls),
            "matcher_activated_iterations": sum(event.get("matcher_activated") is True for event in iterations),
            "deterministic_invalid_iterations": sum(event.get("valid") is False for event in validations),
            "indexed_term_count": len(indexed),
            "indexed_terms": indexed,
            "target_owner": index_payload.get("requirementTargetOwner", {}).get(rid, "ship"),
            "term_owners": ownership,
            "root_cause_categories": categories(feedback, str(final.get("status", ""))),
            "formula_symbols_in_feedback": extract_requested_symbols(feedback),
            "final_feedback": feedback,
            "normalized_requirement": req.get("normalizedRequirement", ""),
            "run_directory": str(Path(str(final.get("_event_file", ""))).parent),
            "engineering_decision": "PENDING_R9_ENGINEERING_REVIEW",
        }
        records.append(record)

    category_counts = Counter(category for record in records for category in record["root_cause_categories"])
    status_counts = Counter(str(record["status"]) for record in records)
    source_counts = Counter(str(record["source_sheet"]) for record in records)
    pattern_counts = Counter(str(record["encoding_pattern"]) for record in records)
    payload = {
        "analysis_id": "R9-BATCH02-FAILURE-ROOT-CAUSE-V1",
        "session_id": SESSION_ID,
        "queue_count": len(queue),
        "failure_count": len(records),
        "status_counts": dict(status_counts),
        "root_cause_counts": dict(category_counts.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "encoding_pattern_counts": dict(pattern_counts.most_common()),
        "records": records,
    }
    (BATCH_ROOT / "r9_failure_analysis.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    headers = [
        "requirement_id", "source_sheet", "page", "clause", "category", "encoding_pattern",
        "status", "attempts", "matcher_calls", "matcher_activated_iterations",
        "deterministic_invalid_iterations", "indexed_term_count", "indexed_terms",
        "target_owner", "term_owners", "root_cause_categories", "formula_symbols_in_feedback",
        "final_feedback", "normalized_requirement", "run_directory", "engineering_decision",
    ]
    with (BATCH_ROOT / "r9_failure_analysis.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for record in records:
            flat = dict(record)
            for key in ("indexed_terms", "root_cause_categories", "formula_symbols_in_feedback"):
                flat[key] = " | ".join(str(item) for item in record[key])
            flat["term_owners"] = json.dumps(record["term_owners"], sort_keys=True, ensure_ascii=True)
            writer.writerow({key: flat[key] for key in headers})

    lines = [
        "# R9 Batch 02 failure reconstruction",
        "",
        f"- Session: `{SESSION_ID}`",
        f"- Failed cases reconstructed: {len(records)}",
        f"- Term-resolution unresolved: {status_counts.get('TERM_RESOLUTION_UNRESOLVED', 0)}",
        f"- Maximum attempts reached: {status_counts.get('MAX_ATTEMPTS_REACHED', 0)}",
        "",
        "## Root-cause signals",
        "",
    ]
    for name, count in category_counts.most_common():
        lines.append(f"- {name}: {count}")
    lines.extend([
        "",
        "These are multi-label evidence signals, not yet final term-addition decisions. Each change must be checked against the regulation and the reusable engineering model.",
    ])
    (BATCH_ROOT / "R9_FAILURE_RECONSTRUCTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "failures": len(records),
        "statuses": status_counts,
        "top_root_causes": category_counts.most_common(12),
        "sources": source_counts,
    }, indent=2))


if __name__ == "__main__":
    main()
