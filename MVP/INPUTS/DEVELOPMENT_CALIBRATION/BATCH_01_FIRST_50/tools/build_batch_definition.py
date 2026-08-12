from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parent
PROJECT_ROOT = BATCH_ROOT.parents[2]
EVIDENCE = PROJECT_ROOT / "BENCHMARK_VOCABULARY/STAGE2_R2/evidence/stage1_approved.json"
INDEX = PROJECT_ROOT / "BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/R2/requirement_term_index.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eligible(row: dict[str, object]) -> bool:
    active = str(row.get("activeStatus", "")).lower()
    codability = str(row.get("codability", "")).lower()
    figure = str(row.get("figureDependent", "")).lower()
    return "direct/deterministic" in active and codability in {"high", "medium"} and figure != "yes"


def test_pattern(row: dict[str, object]) -> tuple[str, int]:
    pattern = str(row.get("encodingPattern", ""))
    if "Table" in pattern:
        return "table lookup plus constraint", 3
    if "Formula" in pattern or "Calculation" in str(row.get("category", "")):
        return "numeric/formula boundary", 3
    if "Conditional" in pattern:
        return "applicable, non-applicable, applicable failure", 3
    return "presence or controlled-value pair", 2


def main() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    index_payload = json.loads(INDEX.read_text(encoding="utf-8"))
    selected = [row for row in evidence["requirements"] if eligible(row)][:50]
    if len(selected) != 50:
        raise RuntimeError(f"Expected 50 requirements, found {len(selected)}")

    records = []
    for sequence, row in enumerate(selected, 1):
        fixture_pattern, minimum_variants = test_pattern(row)
        terms = list(index_payload["requirements"].get(row["id"], []))
        records.append({
            "sequence": sequence,
            "requirement_id": row["id"],
            "source": row.get("source", ""),
            "source_sheet": row.get("sourceSheet", ""),
            "edition": row.get("edition", ""),
            "page": row.get("page", ""),
            "clause": row.get("clause", ""),
            "category": row.get("category", ""),
            "encoding_pattern": row.get("encodingPattern", ""),
            "source_text": row.get("sourceText", ""),
            "normalized_requirement": row.get("normalizedRequirement", ""),
            "r2_indexed_terms": terms,
            "r2_indexed_term_count": len(terms),
            "fixture_pattern": fixture_pattern,
            "minimum_fixture_variants": minimum_variants,
            "dependency_review_status": "PENDING_ENGINEERING_REVIEW",
            "fixture_status": "BLOCKED_UNTIL_DEPENDENCY_REVIEW",
        })

    payload = {
        "batch_id": "DEV-CAL-BATCH-01-FIRST-50",
        "phase": "vocabulary development and calibration",
        "selection_rule": "First 50 generation-eligible requirements in locked R2 evidence order",
        "source_lock_id": "VOCAB-LOCK-2026-08-12-R2",
        "source_files": {
            "requirement_evidence": str(EVIDENCE.relative_to(PROJECT_ROOT)),
            "requirement_evidence_sha256": sha256(EVIDENCE),
            "requirement_term_index": str(INDEX.relative_to(PROJECT_ROOT)),
            "requirement_term_index_sha256": sha256(INDEX),
        },
        "requirement_count": len(records),
        "planned_minimum_fixture_variants": sum(row["minimum_fixture_variants"] for row in records),
        "category_counts": dict(Counter(str(row["category"]) for row in records)),
        "encoding_pattern_counts": dict(Counter(str(row["encoding_pattern"]) for row in records)),
        "requirements": records,
    }
    (BATCH_ROOT / "batch_definition.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    headers = [
        "sequence", "requirement_id", "source_sheet", "page", "clause", "category",
        "encoding_pattern", "r2_indexed_term_count", "r2_indexed_terms", "fixture_pattern",
        "minimum_fixture_variants", "dependency_review_status", "fixture_status",
        "normalized_requirement",
    ]
    with (BATCH_ROOT / "batch_requirements.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in records:
            export = {key: row[key] for key in headers}
            export["r2_indexed_terms"] = " | ".join(row["r2_indexed_terms"])
            writer.writerow(export)

    print(json.dumps({
        "batch_id": payload["batch_id"],
        "requirements": len(records),
        "planned_minimum_fixture_variants": payload["planned_minimum_fixture_variants"],
        "first": records[0]["requirement_id"],
        "last": records[-1]["requirement_id"],
    }, indent=2))


if __name__ == "__main__":
    main()

