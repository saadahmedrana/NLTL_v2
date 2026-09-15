#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ARCHITECTURES = ("V2_FALLBACK25", "NO_SEMANTIC", "SINGLESHOT")
ORIGINAL_WORKBOOK_SHA = "85dac48c8e505ab46b66e6b847a8c3e8be1de30cf13d74ed00bdd0a8af2446b6"
ORIGINAL_SELECTION_SHA = "d6b4af2f99bfac320254dc01d0da949353316382a8b44624f9febc666b4a5a7d"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fenced_turtle(text: str, label: str) -> str:
    match = re.search(re.escape(label) + r"\n```turtle\n(.*?)\n```", text, flags=re.DOTALL)
    if not match:
        raise AssertionError(f"Missing Turtle block after {label}")
    return match.group(1)


def main() -> None:
    audit_root = Path(__file__).resolve().parents[1]
    repo = audit_root.parents[4]
    selection = json.loads((audit_root / "audit_selection.json").read_text(encoding="utf-8"))
    assert sha256(audit_root / "originals/NLTL_Manual_Audit.xlsx") == ORIGINAL_WORKBOOK_SHA
    assert sha256(audit_root / "originals/audit_selection.json") == ORIGINAL_SELECTION_SHA
    assert len(selection["requirements"]) == len(set(selection["requirements"])) == 268
    assert len(selection["records"]) == 804
    assert Counter(row["architecture"] for row in selection["records"]) == Counter({name: 268 for name in ARCHITECTURES})
    assert all(pool == ["RUN_01"] for pool in selection["run_selection"]["eligible_run_pools"].values())

    records = {(row["architecture"], row["requirement_id"]): row for row in selection["records"]}
    case_ids = set()
    for requirement_id in selection["requirements"]:
        cases = selection["cases_per_requirement"][requirement_id]
        assert len(cases) == len(set(cases)) == 2
        case_ids.update(cases)
        for architecture in ARCHITECTURES:
            row = records[(architecture, requirement_id)]
            assert row["selected_case_ids"] == cases
            expected_digest = hashlib.sha256(
                f"{selection['seed']}|RUN|{architecture}|{requirement_id}|RUN_01".encode()
            ).hexdigest()
            assert row["run_choice_digest"] == expected_digest
    assert len(case_ids) == 536

    batch_sizes = []
    verified_shapes = verified_rdf = 0
    for batch_number in range(1, 28):
        batch = f"BATCH_{batch_number:02d}"
        text = (audit_root / f"batches/{batch}.txt").read_text(encoding="utf-8")
        metadata = json.loads((audit_root / f"batches/{batch}.json").read_text(encoding="utf-8"))
        assert metadata["batch"] == batch
        batch_sizes.append(len(metadata["requirements"]))
        for index, requirement in enumerate(metadata["requirements"]):
            requirement_id = requirement["requirement_id"]
            start_marker = f"REQUIREMENT {requirement['order']:03d}: {requirement_id}"
            start = text.index(start_marker)
            next_positions = [position for position in (text.find("\nREQUIREMENT ", start + 1),) if position >= 0]
            requirement_text = text[start:min(next_positions) if next_positions else len(text)]
            for case in requirement["selected_cases"]:
                case_start = requirement_text.index(f"CASE {case['case_id']}")
                boundaries = [
                    position for position in (
                        requirement_text.find("\nCASE ", case_start + 1),
                        requirement_text.find("\nC. ARCHITECTURE SPECIMEN:", case_start + 1),
                    ) if position >= 0
                ]
                case_text = requirement_text[case_start:min(boundaries)]
                rdf_path = repo / case["rdf_path_full"]
                assert sha256(rdf_path) == case["rdf_sha256"]
                assert fenced_turtle(case_text, "Full unmodified RDF Turtle:").rstrip("\n") == rdf_path.read_text(encoding="utf-8").rstrip("\n")
                verified_rdf += 1
            for architecture in ARCHITECTURES:
                record = records[(architecture, requirement_id)]
                arch_start = requirement_text.index(f"C. ARCHITECTURE SPECIMEN: {architecture}")
                boundaries = [
                    position for position in (
                        requirement_text.find("\nC. ARCHITECTURE SPECIMEN:", arch_start + 1),
                        requirement_text.find("\nF. MANUAL REVIEW CHECKLIST", arch_start + 1),
                    ) if position >= 0
                ]
                arch_text = requirement_text[arch_start:min(boundaries)]
                packed = fenced_turtle(arch_text, "Full unmodified selected SHACL:")
                if record.get("shape_path") and (repo / record["shape_path"]).is_file():
                    shape_path = repo / record["shape_path"]
                    assert sha256(shape_path) == record["shape_sha256"]
                    assert packed.rstrip("\n") == shape_path.read_text(encoding="utf-8").rstrip("\n")
                    verified_shapes += 1
                else:
                    assert packed.startswith("MISSING")
    assert batch_sizes == [10] * 26 + [8]
    assert verified_rdf == 536
    assert verified_shapes == 779

    manifest = json.loads((audit_root / "packet_manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = audit_root / entry["path"]
        assert path.is_file()
        assert path.stat().st_size == entry["bytes"]
        assert sha256(path) == entry["sha256"]
    assert (audit_root / "NLTL_Manual_Audit_ready.xlsx").is_file()
    assert len((audit_root / "missing_evidence.txt").read_text(encoding="utf-8").splitlines()) >= 30
    print(json.dumps({
        "requirements": 268,
        "batches": 27,
        "batch_sizes": batch_sizes,
        "architecture_slots": 804,
        "selected_case_ids": 536,
        "verified_rdf_blocks": verified_rdf,
        "verified_shacl_blocks": verified_shapes,
        "explicit_missing_shacl": 804 - verified_shapes,
        "failed_jobs_retained": sum(row["output_origin"] != "OFFICIAL_ELIGIBLE_OUTPUT" for row in selection["records"]),
        "manifest_files_verified": len(manifest["files"]),
    }, indent=2))


if __name__ == "__main__":
    main()
