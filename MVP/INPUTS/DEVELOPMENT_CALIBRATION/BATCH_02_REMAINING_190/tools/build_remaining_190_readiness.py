from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parent
PROJECT_ROOT = BATCH_ROOT.parents[2]
PIPELINE_ROOT = PROJECT_ROOT / "SHACL_GENERATION_PIPELINE"
DEV_CONFIG = PIPELINE_ROOT / "config/pipeline.dev-batch01.json"
BATCH01 = PROJECT_ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50/batch_definition.json"

sys.path.insert(0, str(PIPELINE_ROOT / "src"))

from nltl_pipeline.config import PipelineConfig  # noqa: E402
from nltl_pipeline.retrieval.context import NLTL, VocabularyRepository  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_paths(repository: VocabularyRepository, target: str, owner: str) -> list[str]:
    target_iri = NLTL + target
    owner_iri = NLTL + owner
    matches: list[str] = []
    for local_name, term in repository.all_terms.items():
        if term.get("kind") != "ObjectProperty":
            continue
        if str(term.get("parentOrRange") or "") != owner_iri:
            continue
        if target_iri in {str(item) for item in term.get("domains", [])}:
            matches.append(local_name)
    return sorted(matches)


def main() -> None:
    config = PipelineConfig.load(DEV_CONFIG)
    repository = VocabularyRepository(config)
    batch01 = json.loads(BATCH01.read_text(encoding="utf-8"))
    prior_ids = {item["requirement_id"] for item in batch01["requirements"]}
    eligible = [
        item for item in repository.evidence["requirements"]
        if repository.is_generation_eligible(item)
    ]
    selected = [item for item in eligible if item["id"] not in prior_ids]
    if len(eligible) != 240 or len(prior_ids) != 50 or len(selected) != 190:
        raise RuntimeError(
            f"Selection invariant failed: eligible={len(eligible)}, batch01={len(prior_ids)}, remaining={len(selected)}"
        )

    records: list[dict[str, object]] = []
    for sequence, requirement in enumerate(selected, 1):
        rid = requirement["id"]
        indexed = list(repository.requirement_index.get(rid, []))
        target = repository.requirement_target_owner.get(rid, "ship")
        owners = repository.term_owners.get(rid, {})
        missing_terms = sorted(name for name in indexed if name not in repository.all_terms)
        missing_owner_classes = sorted({target, *owners.values()} - {
            name for name, term in repository.all_terms.items() if term.get("kind") == "Class"
        })
        path_notes: list[str] = []
        owners_without_direct_path: list[str] = []
        for owner in sorted(set(owners.values()) - {target}):
            paths = direct_paths(repository, target, owner)
            if paths:
                path_notes.append(f"{target}->{owner}: {', '.join(paths)}")
            else:
                owners_without_direct_path.append(owner)

        missing_unit_terms = sorted(
            name for name in indexed
            if name in repository.all_terms
            and repository.all_terms[name].get("kind") == "QuantityProperty"
            and not repository.all_terms[name].get("unitIri")
        )
        context_error = ""
        context_term_count = 0
        try:
            context = repository.build_context_pack(rid)
            context_term_count = len(context.terms)
        except Exception as exc:  # retained in the audit instead of hiding a queue defect
            context_error = f"{type(exc).__name__}: {exc}"

        blockers: list[str] = []
        reviews: list[str] = []
        if context_error:
            blockers.append("CONTEXT_BUILD_FAILED")
        if not indexed:
            blockers.append("NO_INDEXED_TERMS")
        if missing_terms:
            blockers.append("INDEXED_TERM_MISSING")
        if missing_owner_classes:
            blockers.append("OWNER_CLASS_MISSING")
        if owners_without_direct_path:
            reviews.append("CROSS_OWNER_PATH_REVIEW")
        if missing_unit_terms:
            reviews.append("UNIT_METADATA_REVIEW")
        readiness = "BLOCKED" if blockers else ("READY_WITH_REVIEW_FLAGS" if reviews else "READY")

        records.append({
            "sequence": sequence,
            "requirement_id": rid,
            "source_sheet": requirement.get("sourceSheet", ""),
            "page": requirement.get("page", ""),
            "clause": requirement.get("clause", ""),
            "category": requirement.get("category", ""),
            "encoding_pattern": requirement.get("encodingPattern", ""),
            "target_owner": target,
            "indexed_term_count": len(indexed),
            "context_term_count": context_term_count,
            "indexed_terms": indexed,
            "required_owners": sorted(set(owners.values())),
            "direct_paths": path_notes,
            "owners_without_direct_path": owners_without_direct_path,
            "missing_unit_terms": missing_unit_terms,
            "semantic_obligation_count": len(repository.semantic_obligations.get(rid, [])),
            "exclusive_group_count": len(repository.exclusive_property_groups.get(rid, [])),
            "context_error": context_error,
            "blockers": blockers,
            "review_flags": reviews,
            "readiness": readiness,
            "normalized_requirement": requirement.get("normalizedRequirement", ""),
        })

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lock_id = str(repository.lock_info.get("lock_id", ""))
    definition = {
        "batch_id": "DEV-CAL-BATCH-02-REMAINING-190",
        "phase": "vocabulary development and generation calibration",
        "selection_rule": "All generation-eligible requirements in active evidence order excluding Batch 01's 50 IDs",
        "generated_at_utc": generated_at,
        "development_vocabulary_id": lock_id,
        "pipeline_config": str(DEV_CONFIG.relative_to(PROJECT_ROOT)),
        "pipeline_config_sha256": sha256(DEV_CONFIG),
        "active_binding": repository.lock_info,
        "counts": {
            "all_requirements": len(repository.requirements),
            "generation_eligible": len(eligible),
            "excluded_batch01": len(prior_ids),
            "selected": len(records),
            "ready": sum(row["readiness"] == "READY" for row in records),
            "ready_with_review_flags": sum(row["readiness"] == "READY_WITH_REVIEW_FLAGS" for row in records),
            "blocked": sum(row["readiness"] == "BLOCKED" for row in records),
        },
        "category_counts": dict(Counter(str(row["category"]) for row in records)),
        "source_sheet_counts": dict(Counter(str(row["source_sheet"]) for row in records)),
        "requirements": records,
    }
    queue = {
        "queue_id": "DEV-R8.1-REMAINING-190-ONE-RUN",
        "description": "One development generation run for each of the 190 eligible requirements outside Batch 01.",
        "development_vocabulary_id": lock_id,
        "repetitions": 1,
        "requirements": [row["requirement_id"] for row in records],
    }

    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    (BATCH_ROOT / "batch_definition.json").write_text(
        json.dumps(definition, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (BATCH_ROOT / "generation_queue.json").write_text(
        json.dumps(queue, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    headers = [
        "sequence", "requirement_id", "source_sheet", "page", "clause", "category",
        "encoding_pattern", "target_owner", "indexed_term_count", "context_term_count",
        "indexed_terms", "required_owners", "direct_paths", "owners_without_direct_path",
        "missing_unit_terms", "semantic_obligation_count", "exclusive_group_count",
        "context_error", "blockers", "review_flags", "readiness", "normalized_requirement",
    ]
    with (BATCH_ROOT / "readiness_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in records:
            flat = dict(row)
            for key in ("indexed_terms", "required_owners", "direct_paths", "owners_without_direct_path", "missing_unit_terms", "blockers", "review_flags"):
                flat[key] = " | ".join(str(item) for item in row[key])
            writer.writerow({key: flat[key] for key in headers})

    summary = definition["counts"]
    report = f"""# Batch 02 — Remaining 190 readiness

Generated: {generated_at}

## Scope

- Active development vocabulary: `{lock_id}`
- Generation-eligible requirements: {summary['generation_eligible']}
- Batch 01 exclusions: {summary['excluded_batch01']}
- Remaining queue: {summary['selected']}
- Ready without flags: {summary['ready']}
- Ready with review flags: {summary['ready_with_review_flags']}
- Blocked: {summary['blocked']}

`READY_WITH_REVIEW_FLAGS` is not a confirmed vocabulary gap. It means the static audit found either a cross-owner relationship without a one-hop path or a quantity without one fixed recommended unit; both can be legitimate and must be interpreted per requirement.

## Safe launch

Run from `SHACL_GENERATION_PIPELINE` and explicitly select the R8.1 development configuration:

```bash
../.venv/bin/python run_pipeline.py --config config/pipeline.dev-batch01.json generate-batch --queue ../INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190/generation_queue.json
```

The queue embeds the R8.1 development vocabulary ID. The pipeline will abort before API calls if a different vocabulary is active.
"""
    (BATCH_ROOT / "READINESS_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"batch": definition["batch_id"], **summary, "first": records[0]["requirement_id"], "last": records[-1]["requirement_id"]}, indent=2))


if __name__ == "__main__":
    main()
