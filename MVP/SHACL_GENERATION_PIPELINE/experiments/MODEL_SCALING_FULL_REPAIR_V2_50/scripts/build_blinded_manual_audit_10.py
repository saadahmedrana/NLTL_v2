#!/usr/bin/env python3
"""Build the blinded ten-requirement scaling audit package offline."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from rdflib import Graph


EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE = EXPERIMENT.parents[1]
REPO = PIPELINE.parents[1]
sys.path.insert(0, str(PIPELINE / "evaluation"))

from experiment_runner.core import load_benchmark  # noqa: E402


OUTPUT = EXPERIMENT / "MANUAL_AUDIT_SCALING_10"
SAMPLE = EXPERIMENT / "MANIFESTS/sample_50.json"
LUNA_REFERENCE = EXPERIMENT / "REFERENCE/LUNA/generation_subset.jsonl"
SELECTION_SEED = "NLTL-MANUAL-AUDIT-SCALING-10-20260918-v1"
BLINDING_SEED = "NLTL-MANUAL-AUDIT-BLINDING-20260918-v1"

ALLOCATION = (
    ("DIRECT_STATIC", "I2", 1),
    ("DIRECT_STATIC", "TRAFICOM", 1),
    ("DIRECT_STATIC", "IMO", 1),
    ("DIRECT_STATIC", "IMO26", 1),
    ("DIRECT_CALCULATION", "I2", 1),
    ("DIRECT_CALCULATION", "TRAFICOM", 1),
    ("DIRECT_CALCULATION", "IMO", 1),
    ("COMPLEX_READINESS", "I2", 1),
    ("COMPLEX_READINESS", "TRAFICOM", 2),
)

MODELS = {
    "luna": ("GPT-5.6 Luna", "gpt-5.6-luna-2026-07-09"),
    "sol": ("GPT-5.6 SOL", "gpt-5.6-sol-2026-07-09"),
    "gemini": ("Gemini 3.5 Flash", "gemini-3.5-flash"),
    "gpt_oss": ("gpt-oss-120b", "gpt-oss-120b"),
}
MODES = ("SELF_REPAIR_FINAL", "FIRST_GENERATION")
RUBRIC = (
    ("Q1", "Applicability and target", "Semantic fidelity", 2),
    ("Q2", "Ontology terms, ownership and paths", "Semantic fidelity", 2),
    ("Q3", "Required obligations complete", "Semantic fidelity", 2),
    ("Q4", "Constraint parameters, units and calculations", "Semantic fidelity", 2),
    ("Q5", "Logic, branches, exceptions and boundaries", "Semantic fidelity", 2),
    ("Q6", "No unsupported restrictions", "Semantic fidelity", 2),
    ("Q7", "Source traceability", "Semantic fidelity", 2),
    ("CQ1", "Analyzability and maintainability", "Implementation quality", 2),
    ("CQ2", "Internal consistency and non-redundancy", "Implementation quality", 2),
    ("CQ3", "Diagnostic usefulness", "Implementation quality", 2),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def selection_digest(record: dict[str, Any]) -> str:
    material = "|".join((SELECTION_SEED, record["verification_mode"], record["source_family"], record["requirement_id"]))
    return sha256_bytes(material.encode("utf-8"))


def select_requirements(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select using only family, mode, ID, and the recorded seed."""
    selected: list[dict[str, Any]] = []
    for mode, family, count in ALLOCATION:
        pool = [r for r in records if r["verification_mode"] == mode and r["source_family"] == family]
        ranked = sorted(pool, key=lambda r: (selection_digest(r), r["requirement_id"]))
        if len(ranked) < count:
            raise RuntimeError(f"Insufficient frozen sample records for {mode}/{family}: {len(ranked)} < {count}")
        selected.extend(ranked[:count])
    if len({r["requirement_id"] for r in selected}) != 10:
        raise RuntimeError("Selection did not produce ten unique requirements")
    return selected


def selected_list_hash(requirement_ids: list[str]) -> str:
    return sha256_bytes(("\n".join(requirement_ids) + "\n").encode("utf-8"))


def blind_assignments(requirement_id: str) -> list[dict[str, str]]:
    identities: list[dict[str, str]] = []
    for model_key, (model_name, model_id) in MODELS.items():
        for mode in MODES:
            material = "|".join((BLINDING_SEED, requirement_id, model_key, mode))
            identities.append({
                "model_key": model_key,
                "model_name": model_name,
                "model_id": model_id,
                "evaluation_mode": mode,
                "ordering_sha256": sha256_bytes(material.encode("utf-8")),
            })
    identities.sort(key=lambda r: (r["ordering_sha256"], r["model_key"], r["evaluation_mode"]))
    for index, row in enumerate(identities, 1):
        row["opaque_id"] = f"A{index:02d}"
    return identities


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def load_candidate_manifests(selected_ids: set[str]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str], str]]:
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    manifest_hashes: dict[tuple[str, str], str] = {}
    for mode in MODES:
        for model in MODELS:
            path = EXPERIMENT / f"RDF_INPUTS/FINAL/{mode}/{model}/generated_rules.jsonl"
            if not path.is_file():
                raise RuntimeError(f"Missing preserved candidate manifest: {path}")
            manifest_hashes[(model, mode)] = sha256_file(path)
            indexed = {str(row["requirement_id"]): row for row in load_jsonl(path)}
            sample_records = json.loads(SAMPLE.read_text(encoding="utf-8"))["records"]
            frozen_ids = {str(record["requirement_id"]) for record in sample_records}
            if set(indexed) != frozen_ids:
                raise RuntimeError(f"Candidate manifest does not cover the frozen sample exactly: {path}")
            for rid in selected_ids:
                rows[(model, mode, rid)] = indexed[rid]
    return rows, manifest_hashes


def read_context_paths(selected_ids: set[str]) -> dict[str, Path]:
    """Read only the context_path locator after selection has been fixed."""
    result: dict[str, Path] = {}
    for row in load_jsonl(LUNA_REFERENCE):
        rid = str(row["requirement_id"])
        if rid in selected_ids:
            result[rid] = resolve_repo_path(str(row["context_path"]))
    if set(result) != selected_ids:
        raise RuntimeError("Could not resolve context packs for every selected requirement")
    return result


def candidate_status(row: dict[str, Any], destination: Path) -> tuple[str, str | None, str | None]:
    source_raw = row.get("generated_shacl_path")
    if row.get("generation_status") != "GENERATED" or not source_raw:
        return "MISSING", None, None
    source = resolve_repo_path(str(source_raw))
    if not source.is_file():
        return "MISSING", None, None
    data = source.read_bytes()
    digest = sha256_bytes(data)
    recorded = row.get("generated_shacl_sha256")
    if recorded and recorded != digest:
        raise RuntimeError(f"Candidate hash mismatch for {source}")
    destination.write_bytes(data)
    try:
        Graph().parse(destination, format="turtle")
    except Exception as exc:  # preserve bytes and label the structural status only
        return "UNPARSEABLE", digest, f"{type(exc).__name__}: {str(exc)[:500]}"
    return "AVAILABLE", digest, None


def safe_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "requirement": context["requirement"],
        "terms": context.get("terms", []),
        "node_patterns": context.get("node_patterns", []),
        "source_lock": context.get("source_lock", {}),
    }


def format_requirement_packet(record: dict[str, Any], req: dict[str, Any], context: dict[str, Any], cases: list[Any], slots: list[dict[str, Any]]) -> str:
    lines = [
        f"# {record['requirement_id']}", "",
        f"Family: {record['source_family']}",
        f"Complexity category: {record['verification_mode']}",
        f"Source: {req.get('source', record.get('source_id', ''))}",
        f"Edition: {req.get('edition', '')}",
        f"Section: {req.get('section', '')}",
        f"Clause: {req.get('clause', record.get('source_clause', ''))}",
        f"Page: {req.get('page', '')}", "",
        "## Exact natural-language requirement", "", str(req.get("sourceText", "")), "",
        "## Relevant ontology context", "",
        f"Full context: rdf_cases/{record['requirement_id']}/ontology_context.json", "",
    ]
    for term in context.get("terms", []):
        if isinstance(term, dict):
            label = term.get("term") or term.get("localName") or term.get("iri") or term.get("id") or "term"
            lines.append(f"- {label}: {json.dumps(term, ensure_ascii=False, sort_keys=True)}")
    lines.extend(["", "## Frozen RDF cases", ""])
    for case in cases:
        lines.append(f"- {case.case_id}: expected {case.expected_outcome}; `{case.case_id}.ttl`")
    lines.extend(["", "## Blinded artifact slots", ""])
    for slot in sorted(slots, key=lambda s: s["opaque_id"]):
        suffix = f"; candidate SHA-256 {slot['candidate_sha256']}" if slot["candidate_sha256"] else ""
        lines.append(f"- {slot['opaque_id']}: {slot['status']}{suffix}")
    lines.extend(["", "Score every slot in scoring_template.xlsx. Do not attempt to identify the system or processing stage.", ""])
    return "\n".join(lines)


def zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = Path("BATCH_01") / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


LEAK_PATTERNS = (
    re.compile(rb"gpt-5\.6[- ]luna", re.I),
    re.compile(rb"gpt-5\.6[- ]sol", re.I),
    re.compile(rb"\bluna\b", re.I),
    re.compile(rb"\bgemini\b", re.I),
    re.compile(rb"gpt[-_]oss", re.I),
    re.compile(rb"self_repair_final", re.I),
    re.compile(rb"first_generation", re.I),
)


def scan_bytes_for_leaks(label: str, data: bytes) -> None:
    for pattern in LEAK_PATTERNS:
        if pattern.search(data):
            raise RuntimeError(f"Blinding leak in {label}: pattern {pattern.pattern!r}")


def verify_zip_blinding(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            scan_bytes_for_leaks(f"ZIP entry name {name}", name.encode("utf-8"))
            data = archive.read(name)
            if name.endswith((".md", ".txt", ".json", ".csv", ".ttl")):
                scan_bytes_for_leaks(name, data)
            if name.endswith(".xlsx"):
                with zipfile.ZipFile(io.BytesIO(data)) as workbook:
                    for member in workbook.namelist():
                        if member.endswith((".xml", ".rels")):
                            scan_bytes_for_leaks(f"{name}!{member}", workbook.read(member))


def verify_package(root: Path, selected: list[dict[str, Any]], slots: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [r["requirement_id"] for r in selected]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise RuntimeError("Package does not contain exactly ten unique requirements")
    if len(slots) != 80:
        raise RuntimeError(f"Package does not contain exactly 80 slots: {len(slots)}")
    per_req = Counter(slot["requirement_id"] for slot in slots)
    if set(per_req) != set(ids) or set(per_req.values()) != {8}:
        raise RuntimeError(f"Every requirement must contain eight slots: {per_req}")
    mode_counts = Counter(r["verification_mode"] for r in selected)
    family_counts = Counter(r["source_family"] for r in selected)
    if mode_counts != Counter({"DIRECT_STATIC": 4, "DIRECT_CALCULATION": 3, "COMPLEX_READINESS": 3}):
        raise RuntimeError(f"Unexpected complexity split: {mode_counts}")
    if family_counts != Counter({"TRAFICOM": 4, "I2": 3, "IMO": 2, "IMO26": 1}):
        raise RuntimeError(f"Unexpected family split: {family_counts}")
    zip_path = root / "BATCH_01.zip"
    if not zip_path.is_file():
        raise RuntimeError("Uploadable ZIP is missing")
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if any("BLINDING_KEY" in name for name in names):
            raise RuntimeError("Private blinding key leaked into ZIP")
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member: {bad}")
    verify_zip_blinding(zip_path)
    return {
        "requirements": len(ids),
        "artifact_slots": len(slots),
        "complexity_counts": dict(sorted(mode_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "zip_sha256": sha256_file(zip_path),
        "blinding_scan": "PASS",
    }


def build() -> Path:
    if OUTPUT.exists():
        raise RuntimeError(f"Refusing to replace existing package: {OUTPUT}")
    sample_raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    selected = select_requirements(sample_raw["records"])
    selected_ids = [r["requirement_id"] for r in selected]
    selected_set = set(selected_ids)
    candidate_rows, manifest_hashes = load_candidate_manifests(selected_set)
    contexts = read_context_paths(selected_set)
    benchmark = load_benchmark(REPO)
    by_requirement = benchmark.by_requirement()

    staging = Path(tempfile.mkdtemp(prefix="manual-audit-10-", dir=str(OUTPUT.parent)))
    try:
        batch = staging / "BATCH_01"
        artifacts = batch / "artifacts"
        rdf_cases = batch / "rdf_cases"
        private = staging / "PRIVATE"
        for directory in (artifacts, rdf_cases, private):
            directory.mkdir(parents=True, exist_ok=True)

        all_slots: list[dict[str, Any]] = []
        private_rows: list[dict[str, Any]] = []
        packet_sections: list[str] = []
        scoring_rows: list[dict[str, str]] = []
        integrity_entries: list[dict[str, Any]] = []

        for record in selected:
            rid = record["requirement_id"]
            context = safe_context(json.loads(contexts[rid].read_text(encoding="utf-8")))
            req = context["requirement"]
            cases = by_requirement[rid]
            if len(cases) != int(record["frozen_case_count"]):
                raise RuntimeError(f"Frozen case count mismatch for {rid}")

            context_path = rdf_cases / rid / "ontology_context.json"
            write_json(context_path, context)
            integrity_entries.append({"kind": "ontology_context", "requirement_id": rid, "path": str(context_path.relative_to(batch)), "sha256": sha256_file(context_path)})
            case_index: list[dict[str, Any]] = []
            for case in cases:
                source = benchmark.root / case.rdf_path
                destination = rdf_cases / rid / f"{case.case_id}.ttl"
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                digest = sha256_file(destination)
                if digest != case.rdf_sha256:
                    raise RuntimeError(f"RDF case hash mismatch for {case.case_id}")
                case_index.append({
                    "case_id": case.case_id,
                    "expected_label": case.expected_outcome,
                    "rdf_file": destination.name,
                    "rdf_sha256": digest,
                    "source_oracle_rationale": case.source_oracle_rationale,
                    "test_pattern": case.test_pattern,
                })
                integrity_entries.append({"kind": "rdf_case", "requirement_id": rid, "case_id": case.case_id, "path": str(destination.relative_to(batch)), "sha256": digest})
            cases_index_path = rdf_cases / rid / "cases.json"
            write_json(cases_index_path, {"requirement_id": rid, "cases": case_index})
            integrity_entries.append({"kind": "rdf_case_index", "requirement_id": rid, "path": str(cases_index_path.relative_to(batch)), "sha256": sha256_file(cases_index_path)})

            req_slots: list[dict[str, Any]] = []
            for identity in blind_assignments(rid):
                opaque = identity["opaque_id"]
                slot_dir = artifacts / rid / opaque
                slot_dir.mkdir(parents=True, exist_ok=True)
                row = candidate_rows[(identity["model_key"], identity["evaluation_mode"], rid)]
                candidate_path = slot_dir / "candidate.ttl"
                status, candidate_hash, parse_error = candidate_status(row, candidate_path)
                public_slot = {
                    "requirement_id": rid,
                    "opaque_id": opaque,
                    "status": status,
                    "candidate_file": "candidate.ttl" if candidate_hash else None,
                    "candidate_sha256": candidate_hash,
                }
                slot_meta = dict(public_slot)
                if parse_error:
                    slot_meta["parse_diagnostic"] = parse_error
                slot_meta_path = slot_dir / "slot.json"
                write_json(slot_meta_path, slot_meta)
                if candidate_hash:
                    integrity_entries.append({"kind": "candidate", **public_slot, "path": str(candidate_path.relative_to(batch)), "sha256": candidate_hash})
                integrity_entries.append({"kind": "artifact_slot", **public_slot, "path": str(slot_meta_path.relative_to(batch)), "sha256": sha256_file(slot_meta_path)})
                req_slots.append(public_slot)
                all_slots.append(public_slot)
                scoring_rows.append({
                    "requirement_id": rid,
                    "family": record["source_family"],
                    "category": record["verification_mode"],
                    "opaque_id": opaque,
                })
                private_rows.append({
                    "requirement_id": rid,
                    "opaque_id": opaque,
                    "model_key": identity["model_key"],
                    "model_name": identity["model_name"],
                    "model_id": identity["model_id"],
                    "evaluation_mode": identity["evaluation_mode"],
                    "blinding_seed": BLINDING_SEED,
                    "ordering_sha256": identity["ordering_sha256"],
                    "source_manifest_sha256": manifest_hashes[(identity["model_key"], identity["evaluation_mode"])],
                    "candidate_status": status,
                    "candidate_sha256": candidate_hash or "",
                })

            packet_text = format_requirement_packet(record, req, context, cases, req_slots)
            packet_path = artifacts / rid / "REVIEW_PACKET.md"
            packet_path.write_text(packet_text, encoding="utf-8")
            integrity_entries.append({"kind": "review_packet", "requirement_id": rid, "path": str(packet_path.relative_to(batch)), "sha256": sha256_file(packet_path)})
            packet_sections.append(packet_text)

        key_path = private / "BLINDING_KEY.csv"
        with key_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(private_rows[0]))
            writer.writeheader()
            writer.writerows(private_rows)

        batch_text = "\n\n".join([
            "BLINDED MANUAL AUDIT — BATCH 01\n\nThis packet contains ten requirements and eight opaque artifact slots per requirement. Artifact IDs are independently randomized within each requirement. No identity key is included. Score every slot with scoring_template.xlsx. AVAILABLE means preserved candidate bytes are present; UNPARSEABLE means preserved bytes are present but fail an offline Turtle parse; MISSING means no preserved candidate exists for that exact slot.\n\nRubric: Q1–Q7 score semantic fidelity from 0–2 (maximum 14); CQ1–CQ3 score implementation quality from 0–2 (maximum 6).",
            *packet_sections,
        ]) + "\n"
        batch_text_path = batch / "BATCH_01.txt"
        batch_text_path.write_text(batch_text, encoding="utf-8")

        workbook_input = staging / ".workbook_input.json"
        write_json(workbook_input, {"rows": scoring_rows, "rubric": [dict(code=c, criterion=q, dimension=d, maximum=m) for c, q, d, m in RUBRIC]})
        work_dir = staging / ".work"
        work_dir.mkdir()
        node_modules = Path(os.environ.get("CODEX_ARTIFACT_NODE_MODULES", "/Users/sadisfaction570/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"))
        node_bin = Path(os.environ.get("CODEX_ARTIFACT_NODE", "/Users/sadisfaction570/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"))
        os.symlink(node_modules, work_dir / "node_modules", target_is_directory=True)
        builder = work_dir / "build_workbook.mjs"
        shutil.copyfile(Path(__file__).with_name("build_blinded_manual_audit_workbook.mjs"), builder)
        workbook_path = batch / "scoring_template.xlsx"
        subprocess.run([str(node_bin), str(builder), str(workbook_input), str(workbook_path), str(work_dir / "previews")], check=True, cwd=work_dir)
        inspect_sidecar = workbook_path.with_suffix(workbook_path.suffix + ".inspect.ndjson")
        if inspect_sidecar.exists():
            inspect_sidecar.unlink()
        shutil.rmtree(work_dir)
        workbook_input.unlink()

        integrity_entries.extend([
            {"kind": "batch_instructions", "path": "BATCH_01.txt", "sha256": sha256_file(batch_text_path)},
            {"kind": "scoring_workbook", "path": "scoring_template.xlsx", "sha256": sha256_file(workbook_path)},
        ])
        batch_manifest = {
            "batch_id": "BATCH_01",
            "selected_requirement_list_sha256": selected_list_hash(selected_ids),
            "requirement_count": 10,
            "artifact_slot_count": 80,
            "requirements": [{
                "requirement_id": r["requirement_id"],
                "family": r["source_family"],
                "complexity_category": r["verification_mode"],
                "rdf_case_count": int(r["frozen_case_count"]),
            } for r in selected],
            "artifact_slots": all_slots,
            "integrity": sorted(integrity_entries, key=lambda e: (e["path"], e.get("opaque_id", ""))),
        }
        write_json(batch / "manifest.json", batch_manifest)

        root_readme = """# Blinded manual audit package\n\n`BATCH_01.zip` is the uploadable blinded review packet. It contains ten requirements, all 80 required artifact slots, frozen RDF fixtures, expected labels, ontology context, and the scoring workbook.\n\n`PRIVATE/BLINDING_KEY.csv` is deliberately outside the ZIP. Keep it private until scoring and adjudication are complete. No generation or RDF evaluation is performed by this packaging workflow.\n"""
        (staging / "README.md").write_text(root_readme, encoding="utf-8")
        zip_directory(batch, staging / "BATCH_01.zip")
        verification = verify_package(staging, selected, all_slots)
        selection_manifest = {
            "selection_seed": SELECTION_SEED,
            "selection_method": "Within each recorded family/category allocation stratum, sort ascending by SHA-256(seed|verification_mode|source_family|requirement_id), then take the requested count.",
            "selection_input_path": str(SAMPLE.relative_to(REPO)),
            "selection_input_sha256": sha256_file(SAMPLE),
            "allocation": [{"complexity_category": mode, "family": family, "count": count} for mode, family, count in ALLOCATION],
            "selected_requirement_ids": selected_ids,
            "selected_requirement_list_serialization": "UTF-8 requirement IDs in displayed order, one per line, with final newline",
            "selected_requirement_list_sha256": selected_list_hash(selected_ids),
            "selection_records": [{
                "requirement_id": r["requirement_id"],
                "family": r["source_family"],
                "complexity_category": r["verification_mode"],
                "selection_ordering_sha256": selection_digest(r),
            } for r in selected],
            "blinding_seed": BLINDING_SEED,
            "blinding_method": "For each requirement independently, sort the eight identities by SHA-256(seed|requirement_id|model_key|evaluation_mode), then assign A01-A08.",
            "batch_01_txt_sha256": sha256_file(batch_text_path),
            "scoring_template_xlsx_sha256": sha256_file(workbook_path),
            "blinding_key_sha256": sha256_file(key_path),
            "batch_01_zip_sha256": verification["zip_sha256"],
            "verification": verification,
        }
        write_json(staging / "selection_manifest.json", selection_manifest)
        staging.replace(OUTPUT)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return OUTPUT


def main() -> int:
    result = build()
    print(canonical_json({"package": str(result), "zip": str(result / "BATCH_01.zip")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
