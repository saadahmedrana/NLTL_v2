from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MVP = ROOT.parents[2]
DEV = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R8_1_POSTCONFIRMATION"


STOP = {
    "IF", "THEN", "AND", "OR", "IN", "NOT", "TRUE", "FALSE", "WHERE", "WITH",
    "SOLAS", "MARPOL", "PWOM", "UIWL", "LIWL", "MCR", "IMO", "IACS",
}


def normalize_identifier(value: str) -> str:
    value = value.strip("_.,;:()[]{}")
    value = re.sub(r"_+(m|mm|cm|km|nm|m3|kN|MN|MNm|kNm|MPa|rpm|deg|tenths)$", "", value, flags=re.I)
    value = re.sub(r"_+", "_", value)
    return value


def main() -> None:
    evidence = json.loads((DEV / "evidence/stage1_approved.json").read_text(encoding="utf-8"))
    registry = json.loads((DEV / "registry/term_registry.json").read_text(encoding="utf-8"))
    index = json.loads((DEV / "requirement_term_index.json").read_text(encoding="utf-8"))
    known: defaultdict[str, set[str]] = defaultdict(set)
    for term in registry:
        for label in {
            term["localName"], term.get("label", ""),
            *term.get("aliases", []), *term.get("stage1LocalNames", []),
        }:
            compact = re.sub(r"[^A-Za-z0-9]", "", str(label)).lower()
            if compact:
                known[compact].add(term["localName"])

    rows = []
    aggregate = Counter()
    for req in evidence["requirements"]:
        rid = req["id"]
        text = str(req.get("normalizedRequirement", ""))
        candidates = set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9.]+)+\b", text))
        # Include compact equation symbols only when they occur adjacent to an
        # assignment or arithmetic operator; ordinary prose abbreviations are excluded.
        candidates.update(re.findall(r"\b([A-Za-z][A-Za-z0-9]{0,8})\s*(?==|[+*/^-])", text))
        for raw in sorted(candidates):
            normalized = normalize_identifier(raw)
            if not normalized or normalized.upper() in STOP:
                continue
            compact = re.sub(r"[^A-Za-z0-9]", "", normalized).lower()
            matches = sorted(known.get(compact, set()))
            indexed_matches = sorted(set(matches) & set(index["requirements"].get(rid, [])))
            status = "INDEXED_EXACT_OR_ALIAS" if indexed_matches else ("REGISTRY_MATCH_NOT_INDEXED" if matches else "NO_EXACT_NAME_OR_ALIAS")
            rows.append({
                "requirement_id": rid,
                "source_sheet": req.get("sourceSheet", ""),
                "page": req.get("page", ""),
                "clause": req.get("clause", ""),
                "raw_identifier": raw,
                "normalized_identifier": normalized,
                "status": status,
                "registry_matches": matches,
                "indexed_matches": indexed_matches,
                "active_status": req.get("activeStatus", ""),
                "figure_dependent": req.get("figureDependent", ""),
            })
            aggregate[status] += 1

    payload = {
        "audit_id": "R9-ALL313-EXPLICIT-IDENTIFIER-RECONCILIATION-V1",
        "identifier_occurrences": len(rows),
        "status_counts": dict(aggregate),
        "records": rows,
        "limitations": [
            "The extraction is lexical and deliberately over-inclusive; NO_EXACT_NAME_OR_ALIAS is a review queue, not automatic proof that a new term is required.",
            "Hidden relational, evidence, applicability, and node-model dependencies still require engineering review even when no variable-style identifier appears in the text.",
        ],
    }
    (ROOT / "r9_all313_explicit_identifier_audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    headers = list(rows[0])
    with (ROOT / "r9_all313_explicit_identifier_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["registry_matches"] = " | ".join(row["registry_matches"])
            flat["indexed_matches"] = " | ".join(row["indexed_matches"])
            writer.writerow(flat)
    print(json.dumps({"identifier_occurrences": len(rows), "status_counts": aggregate}, indent=2))


if __name__ == "__main__":
    main()
