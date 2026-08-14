from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LOCK_ID = "VOCAB-LOCK-2026-08-14-R3"
EVIDENCE = ROOT / "BENCHMARK_VOCABULARY/FINAL_LOCK_R3/evidence/stage1_approved.json"
INDEX = ROOT / "BENCHMARK_VOCABULARY/FINAL_LOCK_R3/requirement_term_index.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
index = json.loads(INDEX.read_text(encoding="utf-8"))
eligible = [
    item["id"] for item in evidence["requirements"]
    if item.get("activeStatus") == "Stage 2 candidate - direct/deterministic"
    and str(item.get("figureDependent", "No")).lower() != "yes"
]
incomplete = [rid for rid in eligible if index["dependencyContracts"].get(rid, {}).get("status") != "COMPLETE"]
if len(eligible) != 238 or incomplete:
    raise RuntimeError(f"Expected 238 eligible requirements and complete contracts; got {len(eligible)}, incomplete={incomplete}")

common = {
    "development_vocabulary_id": LOCK_ID,
    "purpose": "NON_SCORED_R3_VOCABULARY_STRESS_TEST",
    "requirements": eligible,
}
write_json(HERE / "generation_queue_r3_stress_rep1.json", {**common, "repetitions": 1, "independentSweep": 1})
write_json(HERE / "generation_queue_r3_stress_rep2.json", {**common, "repetitions": 1, "independentSweep": 2})
write_json(HERE / "stress_test_manifest.json", {
    "status": "READY",
    "scoredExperiment": False,
    "candidateLockId": LOCK_ID,
    "requirements": len(eligible),
    "plannedIndependentSweeps": 2,
    "models": {"generator": "gpt-5.6-luna-2026-07-09", "validator": "gpt-5.6-terra-2026-07-09", "vocabularyMatcher": "gpt-5.6-luna-2026-07-09"},
    "maximumSemanticAttempts": 1,
    "evidenceSha256": sha256(EVIDENCE),
    "requirementIndexSha256": sha256(INDEX),
    "classificationPolicy": {
        "existingTermMissedInventedOrMisused": "GENERATOR_ERROR_IGNORE_FOR_VOCABULARY",
        "unrequiredModelSuggestion": "GENERATOR_ERROR_IGNORE_FOR_VOCABULARY",
        "sourceConfirmedMissingRepresentation": "SUSPECTED_GENUINE_GAP_MANUAL_REVIEW",
        "automaticOntologyExpansion": False,
    },
})
print(json.dumps({"status": "READY", "eligibleRequirements": len(eligible), "queues": 2}, indent=2))
