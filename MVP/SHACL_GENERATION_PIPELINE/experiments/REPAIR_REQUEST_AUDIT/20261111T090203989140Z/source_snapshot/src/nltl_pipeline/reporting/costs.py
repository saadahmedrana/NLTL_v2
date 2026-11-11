from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import PIPELINE_ROOT, PipelineConfig


DEFAULT_PRICING_USD_PER_MILLION: dict[str, dict[str, float]] = {
    "gpt-5.6-sol-2026-07-09": {"input": 5.0, "output": 30.0},
    "gpt-5.6-terra-2026-07-09": {"input": 2.5, "output": 15.0},
    "gpt-5.6-luna-2026-07-09": {"input": 1.0, "output": 6.0},
    "offline-scripted": {"input": 0.0, "output": 0.0},
}
DEFAULT_PRICING_SOURCE = (
    "https://azure.microsoft.com/en-us/blog/gpt-5-6-now-available-in-microsoft-foundry/"
)


@dataclass(frozen=True, slots=True)
class CostSummary:
    calls: int
    runs: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_usd: float
    unknown_pricing_calls: int
    workbook: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed_api_calls": self.calls,
            "runs_with_recorded_calls": self.runs,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_usd, 6),
            "unknown_pricing_calls": self.unknown_pricing_calls,
            "workbook": str(self.workbook) if self.workbook else "",
        }


def pricing_config(config: PipelineConfig) -> tuple[dict[str, dict[str, float]], str, str]:
    configured = config.raw.get("cost_estimation", {})
    rates = {
        model: {"input": float(values["input"]), "output": float(values["output"])}
        for model, values in configured.get("usd_per_million_tokens", DEFAULT_PRICING_USD_PER_MILLION).items()
    }
    source = str(configured.get("source_url", DEFAULT_PRICING_SOURCE))
    basis = str(configured.get(
        "basis",
        "Indicative Microsoft Azure list-price estimate; not an Aalto invoice.",
    ))
    return rates, source, basis


def completed_api_calls(outputs_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for events_path in sorted(outputs_root.rglob("events.jsonl")):
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_type") != "api_call_completed":
                continue
            input_tokens = int(event.get("input_tokens") or 0)
            output_tokens = int(event.get("output_tokens") or 0)
            records.append({
                "timestamp_utc": str(event.get("timestamp_utc", "")),
                "session_id": str(event.get("session_id", "")),
                "run_id": str(event.get("run_id", "")),
                "requirement_id": str(event.get("requirement_id", "")),
                "role": str(event.get("role", "")),
                "model": str(event.get("model", "")),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": int(event.get("total_tokens") or input_tokens + output_tokens),
                "response_id": str(event.get("response_id", "")),
                "events_path": str(events_path.relative_to(outputs_root)),
            })
    records.sort(key=lambda item: (item["timestamp_utc"], item["run_id"], item["role"]))
    return records


def _run_metadata(outputs_root: Path) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for events_path in sorted(outputs_root.rglob("events.jsonl")):
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            run_id = str(event.get("run_id", ""))
            if not run_id:
                continue
            current = metadata.setdefault(run_id, {
                "run_id": run_id,
                "requirement_id": str(event.get("requirement_id", "")),
                "session_id": str(event.get("session_id", "")),
                "started_utc": "",
                "finished_utc": "",
                "status": "",
                "accepted": "",
                "pipeline_version": "",
                "run_path": str(events_path.parent.relative_to(outputs_root)),
            })
            if event.get("event_type") == "run_started":
                current["started_utc"] = str(event.get("timestamp_utc", ""))
                current["pipeline_version"] = str(event.get("pipeline_version", ""))
            elif event.get("event_type") == "run_finished":
                current["finished_utc"] = str(event.get("timestamp_utc", ""))
                current["status"] = str(event.get("status", ""))
                current["accepted"] = event.get("accepted", "")
    return metadata


def build_cost_payload(config: PipelineConfig, outputs_root: Path) -> tuple[dict[str, Any], CostSummary]:
    rates, source, basis = pricing_config(config)
    calls = completed_api_calls(outputs_root)
    metadata = _run_metadata(outputs_root)
    by_run: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_usd": 0.0,
        "unknown_pricing_calls": 0,
        "models": set(),
        "roles": set(),
    })
    call_rows: list[list[Any]] = []
    unknown_calls = 0
    estimated_total = 0.0
    for call in calls:
        rate = rates.get(call["model"])
        input_rate = rate["input"] if rate else None
        output_rate = rate["output"] if rate else None
        estimated = (
            call["input_tokens"] / 1_000_000 * input_rate
            + call["output_tokens"] / 1_000_000 * output_rate
        ) if rate else None
        if estimated is None:
            unknown_calls += 1
        else:
            estimated_total += estimated
        aggregate = by_run[call["run_id"]]
        aggregate["calls"] += 1
        aggregate["input_tokens"] += call["input_tokens"]
        aggregate["output_tokens"] += call["output_tokens"]
        aggregate["total_tokens"] += call["total_tokens"]
        aggregate["models"].add(call["model"])
        aggregate["roles"].add(call["role"])
        if estimated is None:
            aggregate["unknown_pricing_calls"] += 1
        else:
            aggregate["estimated_usd"] += estimated
        call_rows.append([
            call["timestamp_utc"], call["session_id"], call["run_id"], call["requirement_id"],
            call["role"], call["model"], call["input_tokens"], call["output_tokens"],
            call["total_tokens"], input_rate, output_rate, estimated, call["response_id"],
            call["events_path"],
        ])

    run_rows: list[list[Any]] = []
    cumulative = 0.0
    ordered_runs = sorted(by_run, key=lambda run_id: (
        metadata.get(run_id, {}).get("started_utc", ""), run_id,
    ))
    for run_id in ordered_runs:
        item = by_run[run_id]
        meta = metadata.get(run_id, {})
        cumulative += item["estimated_usd"]
        run_rows.append([
            meta.get("started_utc", ""), meta.get("finished_utc", ""), meta.get("session_id", ""),
            run_id, meta.get("requirement_id", ""), meta.get("pipeline_version", ""),
            meta.get("status", ""), meta.get("accepted", ""), item["calls"],
            item["input_tokens"], item["output_tokens"], item["total_tokens"],
            " | ".join(sorted(item["models"])), " | ".join(sorted(item["roles"])),
            item["estimated_usd"], cumulative, item["unknown_pricing_calls"],
            meta.get("run_path", ""),
        ])

    pricing_rows = [
        [model, values["input"], values["output"], "USD per 1M tokens", source]
        for model, values in sorted(rates.items())
    ]
    payload = {
        "title": "NLTL Pipeline API Token and Cost Ledger",
        "subtitle": "All completed API response events currently retained under SHACL_GENERATION_PIPELINE/outputs",
        "generated_from": str(outputs_root),
        "pricing_source": source,
        "pricing_basis": basis,
        "pricing_rows": pricing_rows,
        "run_rows": run_rows,
        "call_rows": call_rows,
        "summary": {
            "runs": len(by_run),
            "calls": len(calls),
            "input_tokens": sum(item["input_tokens"] for item in calls),
            "output_tokens": sum(item["output_tokens"] for item in calls),
            "total_tokens": sum(item["total_tokens"] for item in calls),
            "estimated_usd": estimated_total,
            "unknown_pricing_calls": unknown_calls,
        },
    }
    summary = CostSummary(
        calls=len(calls),
        runs=len(by_run),
        input_tokens=payload["summary"]["input_tokens"],
        output_tokens=payload["summary"]["output_tokens"],
        total_tokens=payload["summary"]["total_tokens"],
        estimated_usd=estimated_total,
        unknown_pricing_calls=unknown_calls,
    )
    return payload, summary


def write_cost_ledger(config: PipelineConfig) -> CostSummary:
    outputs_root = (PIPELINE_ROOT / "outputs").resolve()
    destination = outputs_root / "cost_reporting"
    destination.mkdir(parents=True, exist_ok=True)
    payload, summary = build_cost_payload(config, outputs_root)
    payload_path = destination / "pipeline_cost_ledger.json"
    workbook_path = destination / "pipeline_cost_ledger.xlsx"
    payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    node = Path(str(config.raw["reporting"]["node_executable"]))
    node_modules = Path(str(config.raw["reporting"]["artifact_tool_node_modules"]))
    if not node.is_file() or not node_modules.is_dir():
        return summary
    builder = PIPELINE_ROOT / "reporting" / "build_cost_ledger.mjs"
    with tempfile.TemporaryDirectory(prefix="nltl_cost_ledger_") as temp_name:
        temp = Path(temp_name)
        os.symlink(node_modules, temp / "node_modules", target_is_directory=True)
        copied_builder = temp / "build_cost_ledger.mjs"
        shutil.copy2(builder, copied_builder)
        result = subprocess.run(
            [str(node), str(copied_builder), str(payload_path), str(workbook_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(f"Cost ledger Excel export failed: {result.stderr.strip() or result.stdout.strip()}")
    return CostSummary(
        calls=summary.calls,
        runs=summary.runs,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        total_tokens=summary.total_tokens,
        estimated_usd=summary.estimated_usd,
        unknown_pricing_calls=summary.unknown_pricing_calls,
        workbook=workbook_path,
    )


def terminal_cost_summary(summary: CostSummary) -> str:
    warning = (
        f" unknown_price_calls={summary.unknown_pricing_calls}"
        if summary.unknown_pricing_calls else ""
    )
    return (
        f"[COST] PROJECT CUMULATIVE runs={summary.runs} calls={summary.calls} "
        f"input_tokens={summary.input_tokens:,} output_tokens={summary.output_tokens:,} "
        f"total_tokens={summary.total_tokens:,} estimated_usd=${summary.estimated_usd:,.2f}"
        f"{warning} basis=Azure-list-price-estimate-not-Aalto-invoice"
    )
