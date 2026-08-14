from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parent
MVP = BATCH_ROOT.parents[2]
DEV = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R8_1_POSTCONFIRMATION"


def main() -> None:
    evidence = json.loads((DEV / "evidence/stage1_approved.json").read_text(encoding="utf-8"))
    index = json.loads((DEV / "requirement_term_index.json").read_text(encoding="utf-8"))
    registry = json.loads((DEV / "registry/term_registry.json").read_text(encoding="utf-8"))
    terms = {item["localName"]: item for item in registry}
    failed = {
        item["requirement_id"]: item
        for item in json.loads((BATCH_ROOT / "r9_failure_analysis.json").read_text(encoding="utf-8"))["records"]
    }
    rows = []
    for req in evidence["requirements"]:
        rid = req["id"]
        names = list(index["requirements"].get(rid, []))
        records = [terms[name] for name in names if name in terms]
        kinds = Counter(item.get("kind", "") for item in records)
        pattern = str(req.get("encodingPattern", ""))
        lower = pattern.lower()
        flags: list[str] = []
        if "formula" in lower or "calculation" in lower or "numeric" in lower:
            if kinds["QuantityProperty"] < 2:
                flags.append("FORMULA_OR_NUMERIC_HAS_FEWER_THAN_TWO_QUANTITIES")
            if len(names) < 3:
                flags.append("FORMULA_OR_NUMERIC_CONTEXT_TOO_SHALLOW")
        if "conditional" in lower and len(names) < 2:
            flags.append("CONDITIONAL_CONTEXT_HAS_NO_EXPLICIT_OUTCOME_PAIR")
        if "table" in lower and len(names) < 3:
            flags.append("TABLE_CONTEXT_TOO_SHALLOW")
        if any(token in lower for token in ("qualified", "per-", "cross-document", "assignment")):
            if kinds["ObjectProperty"] == 0:
                flags.append("PER_ITEM_OR_QUALIFIED_CONTEXT_HAS_NO_RELATIONSHIP")
        string_terms = [item["localName"] for item in records if item.get("datatype") == "xsd:string"]
        if any(token in lower for token in ("enumeration", "classification", "lookup")) and string_terms:
            flags.append("ORDERED_OR_ENUMERATED_LOGIC_USES_STRING")
        if rid in failed:
            flags.append("OBSERVED_BATCH02_FAILURE")
        active = (
            req.get("activeStatus") == "Stage 2 candidate - direct/deterministic"
            and str(req.get("figureDependent", "No")).lower() != "yes"
        )
        rows.append({
            "requirement_id": rid,
            "source_sheet": req.get("sourceSheet", ""),
            "page": req.get("page", ""),
            "clause": req.get("clause", ""),
            "active": active,
            "encoding_pattern": pattern,
            "indexed_term_count": len(names),
            "class_count": kinds["Class"],
            "object_property_count": kinds["ObjectProperty"],
            "datatype_property_count": kinds["DatatypeProperty"],
            "quantity_property_count": kinds["QuantityProperty"],
            "string_terms": string_terms,
            "flags": sorted(set(flags)),
            "observed_status": failed.get(rid, {}).get("status", "NOT_FAILED_IN_BATCH02"),
            "normalized_requirement": req.get("normalizedRequirement", ""),
        })
    payload = {
        "audit_id": "R9-ALL313-DEPENDENCY-DEPTH-V1",
        "requirements": len(rows),
        "active_requirements": sum(bool(row["active"]) for row in rows),
        "flagged_all": sum(bool(row["flags"]) for row in rows),
        "flagged_active": sum(bool(row["active"] and row["flags"]) for row in rows),
        "flag_counts": dict(Counter(flag for row in rows for flag in row["flags"])),
        "records": rows,
    }
    (BATCH_ROOT / "r9_all313_dependency_audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    headers = list(rows[0])
    with (BATCH_ROOT / "r9_all313_dependency_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["flags"] = " | ".join(row["flags"])
            flat["string_terms"] = " | ".join(row["string_terms"])
            writer.writerow(flat)
    print(json.dumps({key: payload[key] for key in ("requirements", "active_requirements", "flagged_all", "flagged_active", "flag_counts")}, indent=2))


if __name__ == "__main__":
    main()
