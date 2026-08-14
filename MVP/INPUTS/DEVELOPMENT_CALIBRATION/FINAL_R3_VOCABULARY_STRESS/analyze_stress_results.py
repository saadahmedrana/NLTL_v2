from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/vocabulary_stress_r3"
ANALYSIS = Path(__file__).resolve().parent / "analysis"


def latest_session_result() -> Path:
    candidates = list((OUTPUTS / "sessions").glob("SESSION-BATCH-*/batch_result.json"))
    if not candidates:
        raise FileNotFoundError("No completed stress-test batch_result.json was found")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_events(run_directory: Path) -> list[dict]:
    path = run_directory / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def classify(result: dict, events: list[dict]) -> tuple[str, str]:
    status = result.get("status", "")
    matcher_decisions = [e for e in events if e.get("event_type") == "matcher_decision"]
    matcher_searches = [e for e in events if e.get("event_type") == "matcher_search"]
    if status in {"BATCH_ITEM_ERROR", "PIPELINE_ERROR", "INTERRUPTED"}:
        return "TECHNICAL_ERROR_RETRY", "The run did not produce an interpretable vocabulary signal."
    if any(e.get("match_found") is True for e in matcher_decisions):
        return "EXISTING_R3_TERM_FOUND_MODEL_ERROR", "The matcher resolved the request to an existing locked term; this is not a vocabulary gap."
    if status == "TERM_RESOLUTION_UNRESOLVED" or (
        matcher_searches and not matcher_decisions and max(int(e.get("candidate_count", 0)) for e in matcher_searches) == 0
    ) or any(e.get("match_found") is False for e in matcher_decisions):
        return "SUSPECTED_GAP_MANUAL_SOURCE_REVIEW", "No existing term was resolved. This is only a candidate signal and requires source-based manual inspection."
    if status == "GENERATION_ACCEPTED":
        return "NO_GAP_SIGNAL", "The generation and semantic review raised no unresolved vocabulary signal."
    return "MODEL_LOGIC_OR_SHACL_ERROR_NO_GAP_SIGNAL", "The failure did not establish absence from R3; treat it as model/SHACL behavior unless manual evidence proves otherwise."


parser = argparse.ArgumentParser()
parser.add_argument("--session-result", type=Path)
args = parser.parse_args()
session_path = (args.session_result or latest_session_result()).resolve()
session = json.loads(session_path.read_text(encoding="utf-8"))
adjudication_path = Path(__file__).resolve().parent / "manual_adjudication_rep1.json"
adjudication = json.loads(adjudication_path.read_text(encoding="utf-8")) if adjudication_path.exists() else {"decisions": {}}
rows = []
for result in session["results"]:
    run_dir = Path(result.get("run_directory", ""))
    events = read_events(run_dir) if run_dir else []
    classification, rationale = classify(result, events)
    calls = [e for e in events if e.get("event_type") == "api_call_completed"]
    matcher = [e for e in events if e.get("event_type") == "matcher_decision"]
    searches = [e for e in events if e.get("event_type") == "matcher_search"]
    manual = adjudication.get("decisions", {}).get(result.get("requirement_id", ""), {})
    rows.append({
        "requirement_id": result.get("requirement_id", ""),
        "repetition": result.get("repetition", 1),
        "run_id": result.get("run_id", ""),
        "status": result.get("status", ""),
        "accepted": result.get("accepted", False),
        "classification": classification,
        "classification_rationale": rationale,
        "matcher_activated": bool(searches),
        "matcher_candidate_count": max([int(e.get("candidate_count", 0)) for e in searches] or [0]),
        "matcher_match_found": any(e.get("match_found") is True for e in matcher),
        "matched_local_names": " | ".join(sorted({str(e.get("canonical_local_name")) for e in matcher if e.get("match_found")})),
        "api_calls": len(calls),
        "input_tokens": sum(int(e.get("input_tokens") or 0) for e in calls),
        "output_tokens": sum(int(e.get("output_tokens") or 0) for e in calls),
        "elapsed_ms": sum(float(e.get("elapsed_ms") or 0) for e in calls),
        "final_feedback": result.get("final_feedback", result.get("error", "")),
        "run_directory": str(run_dir),
        "manual_review_status": "COMPLETE" if manual else ("PENDING" if classification == "SUSPECTED_GAP_MANUAL_SOURCE_REVIEW" else "NOT_REQUIRED"),
        "manual_source_decision": manual.get("decision", ""),
        "review_source": manual.get("source", ""),
        "review_notes": manual.get("rationale", ""),
    })

counts = Counter(row["classification"] for row in rows)
manual_counts = Counter(row["manual_source_decision"] for row in rows if row["manual_source_decision"])
pending_manual = sum(row["manual_review_status"] == "PENDING" for row in rows)
payload = {
    "status": "MANUAL_REVIEW_COMPLETE_GAPS_CONFIRMED" if manual_counts["GENUINE_SCHEMA_GAP_CONFIRMED"] else ("ANALYZED_PENDING_MANUAL_REVIEW" if pending_manual else "ANALYZED_NO_GAP_SIGNALS"),
    "scoredExperiment": False,
    "sessionId": session["session_id"],
    "candidateLockId": session["vocabulary_lock_id"],
    "requirements": session["requirements"],
    "totalItems": session["total_items"],
    "classificationCounts": dict(sorted(counts.items())),
    "manualDecisionCounts": dict(sorted(manual_counts.items())),
    "pendingManualReviews": pending_manual,
    "automaticOntologyChanges": 0,
    "records": rows,
}
ANALYSIS.mkdir(parents=True, exist_ok=True)
stem = session["session_id"]
json_path = ANALYSIS / f"{stem}_classification.json"
csv_path = ANALYSIS / f"{stem}_classification.csv"
json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
with csv_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["requirement_id"])
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps({"status": payload["status"], "sessionId": stem, "counts": payload["classificationCounts"], "json": str(json_path), "csv": str(csv_path)}, indent=2))
