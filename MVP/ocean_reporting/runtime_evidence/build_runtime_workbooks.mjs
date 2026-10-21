import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dataPath = "/private/tmp/nltl_runtime_evidence.json";
const runtimeOutput = "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/NLTL_Runtime_and_Iterations.xlsx";
const paperInput = "/Users/sadisfaction570/Downloads/NLTL_v2_Paper_Tables.xlsx";
const paperOutput = "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/inputs/NLTL_v2_Paper_Tables.xlsx";
const previewDir = "/private/tmp/nltl_runtime_previews";

const data = JSON.parse(await fs.readFile(dataPath, "utf8"));
await fs.mkdir(path.dirname(runtimeOutput), { recursive: true });
await fs.mkdir(path.dirname(paperOutput), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const NAVY = "#17365D";
const BLUE = "#D9EAF7";
const LIGHT = "#F3F6F8";
const GRID = "#D8E0E6";
const AMBER = "#FFF2CC";
const RED = "#FCE4D6";
const GREEN = "#E2F0D9";
const FONT = "Arial";

function colName(n) {
  let s = "";
  while (n > 0) {
    n -= 1;
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26);
  }
  return s;
}

function cleanValue(v) {
  if (v === undefined) return null;
  if (Number.isNaN(v)) return null;
  return v;
}

function matrix(rows, headers) {
  return rows.map((row) => headers.map((h) => cleanValue(row[h])));
}

function chunks(values, size = 900) {
  const out = [];
  for (let i = 0; i < values.length; i += size) out.push([i, values.slice(i, i + size)]);
  return out;
}

function styleTitle(sheet, lastCol, title, note) {
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${lastCol}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: NAVY,
    font: { name: FONT, size: 16, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeight = 28;
  sheet.mergeCells(`A2:${lastCol}2`);
  sheet.getRange("A2").values = [[note]];
  sheet.getRange(`A2:${lastCol}2`).format = {
    fill: LIGHT,
    font: { name: FONT, size: 9, italic: true, color: "#44546A" },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2").format.rowHeight = 34;
}

function addDataSheet(workbook, options) {
  const { name, title, note, headers, labels, rows, tableName, widths = {} } = options;
  const sheet = workbook.worksheets.add(name);
  const lastCol = colName(headers.length);
  styleTitle(sheet, lastCol, title, note);
  sheet.getRange(`A4:${lastCol}4`).values = [labels];
  sheet.getRange(`A4:${lastCol}4`).format = {
    fill: NAVY,
    font: { name: FONT, size: 9, bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: GRID },
  };
  sheet.getRange("A4").format.rowHeight = 34;
  const values = matrix(rows, headers);
  for (const [offset, part] of chunks(values)) {
    const start = 5 + offset;
    const end = start + part.length - 1;
    sheet.getRange(`A${start}:${lastCol}${end}`).values = part;
  }
  const endRow = Math.max(4, 4 + rows.length);
  if (rows.length) {
    const table = sheet.tables.add(`A4:${lastCol}${endRow}`, true, tableName);
    table.style = "TableStyleMedium2";
    table.showFilterButton = true;
  }
  for (let i = 0; i < headers.length; i++) {
    const letter = colName(i + 1);
    sheet.getRange(`${letter}4`).format.columnWidth = widths[headers[i]] || 16;
  }
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(Math.min(2, headers.length));
  return { sheet, endRow };
}

function mean(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function median(values) {
  if (!values.length) return null;
  const v = [...values].sort((a, b) => a - b);
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function sampleSd(values) {
  if (values.length < 2) return null;
  const m = mean(values);
  return Math.sqrt(values.reduce((s, x) => s + (x - m) ** 2, 0) / (values.length - 1));
}

function stats(values) {
  const v = values.filter((x) => typeof x === "number" && Number.isFinite(x));
  return { n: v.length, mean: mean(v), sd: sampleSd(v), median: median(v), total: v.reduce((a, b) => a + b, 0), max: v.length ? Math.max(...v) : null };
}

function groupRows(rows, keyFn) {
  const map = new Map();
  for (const row of rows) {
    const key = keyFn(row);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  }
  return map;
}

const runHeaders = [
  "experiment", "publication_label", "scope", "session_id", "run_id", "requirement_id", "repetition", "scaling_sample_member",
  "pipeline_version", "model_role_configuration", "generator_model", "validator_model", "syntax_repair_model",
  "started_utc", "finished_utc", "elapsed_seconds", "api_seconds", "candidate_attempts", "terminal_candidate_iteration",
  "generator_calls", "semantic_validator_calls", "syntax_repair_calls", "vocabulary_matcher_calls", "logical_api_calls", "transport_attempts",
  "final_status", "accepted_flag", "deterministic_valid", "eligible_at_start", "output_available", "successful_output", "completed",
  "completed_unsuccessful", "final_shape_or_candidate", "source_path", "success_definition", "behavioral_cases", "behavioral_executed",
  "behavioral_correct", "behavioral_all_correct", "behavioral_source",
];
const runLabels = [
  "Original experiment", "Publication label", "Scope", "Session ID", "Run ID", "Requirement ID", "Repetition", "Scaling sample member",
  "Pipeline version", "Model-role configuration", "Generator model", "Validator model", "Syntax-repair model",
  "Started UTC", "Finished UTC", "Elapsed (s)", "Logical API time (s)", "Candidate attempts", "Terminal recorded iteration",
  "Generator calls", "Semantic-validator calls", "Syntax-repair calls", "Vocabulary-matcher calls", "Logical API calls", "Transport attempts",
  "Final status", "Accepted flag", "Deterministic valid", "Eligible at start", "Output available", "Successful output", "Completed",
  "Completed unsuccessful", "Final shape/candidate", "Source events path", "Success definition", "Behavioural cases", "Behavioural executed",
  "Behavioural correct", "All cases correct", "Behavioural source",
];

const iterationHeaders = ["experiment", "publication_label", "scope", "session_id", "run_id", "requirement_id", "repetition", "iteration", "record_source", "mode", "static_valid", "validator_accept", "matcher_activated", "decision", "generator_seconds", "validator_seconds", "stalled", "oscillation_detected", "feedback", "timestamp_utc", "source_path"];
const iterationLabels = ["Original experiment", "Publication label", "Scope", "Session ID", "Run ID", "Requirement ID", "Repetition", "Candidate iteration", "Record source", "Mode", "Static valid", "Validator accepts", "Matcher activated", "Decision", "Generator time (s)", "Validator time (s)", "Stalled", "Oscillation detected", "Feedback", "Timestamp UTC", "Source events path"];

const apiHeaders = ["experiment", "publication_label", "scope", "session_id", "run_id", "requirement_id", "repetition", "call_ordinal", "event_id", "timestamp_utc", "role", "model", "iteration", "syntax_repair_attempt", "contract_attempt", "elapsed_seconds", "transport_attempts", "input_tokens", "output_tokens", "total_tokens", "response_id", "source_path"];
const apiLabels = ["Original experiment", "Publication label", "Scope", "Session ID", "Run ID", "Requirement ID", "Repetition", "Logical call ordinal", "Event ID", "Timestamp UTC", "Role", "Model", "Candidate iteration", "Syntax-repair attempt", "Contract attempt", "Logical call elapsed (s)", "Transport attempts/retries", "Input tokens", "Output tokens", "Total tokens", "Response ID", "Source events path"];

const rdfHeaders = ["experiment", "publication_label", "scope", "stage", "model", "evaluation_run_id", "generation_run", "generation_run_id", "configuration", "requirement_id", "case_id", "expected_outcome", "actual_conforms", "behavioral_match", "execution_status", "end_to_end_success", "outcome_class", "runtime_seconds", "generation_status", "shape_parse_status", "failure_stage", "source_family", "source_path"];
const rdfLabels = ["Original experiment", "Publication label", "Scope", "Stage", "Model key", "Evaluation run ID", "Generation run", "Generation run ID", "Configuration", "Requirement ID", "Case ID", "Expected outcome", "Actual conforms", "Expected agreement", "Execution status", "End-to-end success", "Outcome class", "RDF runtime (s)", "Generation status", "Shape parse status", "Failure stage", "Source family", "Source ledger path"];

const workbook = Workbook.create();
workbook.worksheets.add("Summary");
const readme = workbook.worksheets.add("README");
readme.showGridLines = false;
readme.mergeCells("A1:H1");
readme.getRange("A1").values = [["NLTL runtime and iteration evidence"]];
readme.getRange("A1:H1").format = { fill: NAVY, font: { name: FONT, size: 17, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
readme.getRange("A1").format.rowHeight = 30;
const readmeRows = [
  ["Purpose", "Recover and organise existing execution-time, iteration, API-call and RDF-evaluation evidence. No generation, evaluation or API calls were run."],
  ["Publication mapping", "Selected formal LUNA_NO_SEMANTIC_VALIDATOR runs are labelled NLTL_v2. LUNA_CONTEXTUAL_SINGLESHOT is labelled Single-shot. Original experiment, pipeline and model identifiers remain in provenance columns."],
  ["Requirement-run time", data.metadata.metric_definitions.requirement_run_elapsed],
  ["Logical API time", data.metadata.metric_definitions.api_seconds],
  ["RDF time", data.metadata.metric_definitions.rdf_seconds],
  ["Candidate attempts", data.metadata.metric_definitions.candidate_attempts],
  ["Success: NLTL_v2 mapping", "Deterministic-valid recorded candidate exists. The historical accepted=False flag is not treated as failure because semantic acceptance was deliberately disabled."],
  ["Success: Single-shot", "Deterministic-valid extracted output exists. One candidate attempt is verified from single_shot_diagnostics_completed; there are no iteration_completed events."],
  ["Success: full repair/model scaling", "GENERATION_ACCEPTED with accepted=True and a recorded final shape."],
  ["Completed unsuccessful runs", "Preserved in overall timing and iteration summaries. Missing values remain blank and are never replaced by zero."],
  ["Transport retries", "Reported as a separate count. Transport-attempt timing rows are not added to logical api_call_completed elapsed time."],
  ["RDF denominator caveat", "Existing runtime ledgers retain 2,186 full-benchmark and 381 scaling cases. Current Paper Tables/manuscript data report 2,160 and 373; timing evidence is preserved under its recorded dataset version."],
  ["Hidden evaluation", "HIDDEN_RDF_EVALUATION contains an audit only. It stopped before evaluation because no formal independent hidden R13 benchmark was present."],
  ["Source project", data.metadata.project],
  ["Generated", String(data.metadata.created_utc).replace("T", " ").replace(/Z$/, " UTC")],
  ["Requirement runs", data.metadata.counts.requirement_runs],
  ["Candidate iteration records", data.metadata.counts.iterations],
  ["Logical API calls", data.metadata.counts.api_calls],
  ["RDF case records", data.metadata.counts.rdf_cases],
];
readme.getRange(`A3:B${2 + readmeRows.length}`).values = readmeRows;
readme.getRange(`A3:A${2 + readmeRows.length}`).format = { fill: BLUE, font: { name: FONT, size: 10, bold: true, color: NAVY }, wrapText: true, borders: { preset: "all", style: "thin", color: GRID } };
readme.getRange(`B3:B${2 + readmeRows.length}`).format = { font: { name: FONT, size: 10, color: "#1F2937" }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: GRID } };
readme.getRange("A1").format.columnWidth = 26;
readme.getRange("B1").format.columnWidth = 105;
readme.getRange(`A3:B${2 + readmeRows.length}`).format.autofitRows();
readme.freezePanes.freezeRows(2);

const indexHeaders = ["original_experiment", "publication_label", "scope", "session_id", "model_role_configuration", "benchmark_subset", "repetition", "requirement_runs", "unique_requirements", "source_root", "success_definition"];
const indexLabels = ["Original experiment", "Publication label", "Scope", "Session ID", "Model-role configuration", "Benchmark/subset", "Repetition", "Requirement runs", "Unique requirements", "Source root", "Success definition"];
addDataSheet(workbook, { name: "Experiment_Index", title: "Experiment index", note: "Formal sessions included in the evidence workbook. Smoke, connectivity and mini-test runs are listed in Audit and excluded from summaries.", headers: indexHeaders, labels: indexLabels, rows: data.experiment_index, tableName: "ExperimentIndexTable", widths: { original_experiment: 31, publication_label: 23, scope: 30, session_id: 43, model_role_configuration: 70, benchmark_subset: 45, repetition: 14, source_root: 75, success_definition: 85 } });

const runSheet = addDataSheet(workbook, { name: "Requirement_Runs", title: "Requirement runs", note: "One row per unique formal requirement-run. Run elapsed, logical API time and RDF evidence are separate. Missing evidence is blank.", headers: runHeaders, labels: runLabels, rows: data.requirement_runs, tableName: "RequirementRunsTable", widths: { experiment: 31, publication_label: 22, scope: 30, session_id: 42, run_id: 43, requirement_id: 15, repetition: 13, pipeline_version: 35, model_role_configuration: 70, started_utc: 25, finished_utc: 25, final_status: 38, final_shape_or_candidate: 35, source_path: 90, success_definition: 90, behavioral_source: 90 } });
runSheet.sheet.getRange(`P5:R${runSheet.endRow}`).format.numberFormat = "0.000";
runSheet.sheet.getRange(`S5:Y${runSheet.endRow}`).format.numberFormat = "0";
runSheet.sheet.getRange(`AK5:AM${runSheet.endRow}`).format.numberFormat = "0";

const iterSheet = addDataSheet(workbook, { name: "Iterations", title: "Candidate iterations", note: "Recorded candidate iterations. Single-shot rows are sourced from single_shot_diagnostics_completed and explicitly marked in Record source.", headers: iterationHeaders, labels: iterationLabels, rows: data.iterations, tableName: "IterationsTable", widths: { experiment: 31, publication_label: 22, scope: 28, session_id: 42, run_id: 43, requirement_id: 15, record_source: 32, mode: 22, decision: 28, feedback: 100, timestamp_utc: 25, source_path: 90 } });
iterSheet.sheet.getRange(`O5:P${iterSheet.endRow}`).format.numberFormat = "0.000";

const apiSheet = addDataSheet(workbook, { name: "API_Calls", title: "Logical completed API calls", note: "One row per api_call_completed event. elapsed_seconds already covers the logical call; transport attempts/retries are retained separately and never added again.", headers: apiHeaders, labels: apiLabels, rows: data.api_calls, tableName: "ApiCallsTable", widths: { experiment: 31, publication_label: 22, scope: 28, session_id: 42, run_id: 43, requirement_id: 15, event_id: 15, timestamp_utc: 25, role: 20, model: 31, response_id: 40, source_path: 90 } });
apiSheet.sheet.getRange(`P5:P${apiSheet.endRow}`).format.numberFormat = "0.000";

const rdfSheet = addDataSheet(workbook, { name: "RDF_Evaluation", title: "RDF evaluation timings", note: "Per-case runtime from existing evaluation ledgers. Generation timing and RDF execution timing remain separate. Dataset-version caveats are recorded in README and Audit.", headers: rdfHeaders, labels: rdfLabels, rows: data.rdf_evaluation, tableName: "RdfEvaluationTable", widths: { experiment: 31, publication_label: 23, scope: 28, stage: 23, model: 18, evaluation_run_id: 52, generation_run: 45, generation_run_id: 43, configuration: 34, requirement_id: 15, case_id: 24, outcome_class: 28, source_path: 95 } });
rdfSheet.sheet.getRange(`R5:R${rdfSheet.endRow}`).format.numberFormat = "0.000";

const auditHeaders = ["severity", "category", "experiment", "run_id", "detail"];
const auditLabels = ["Severity", "Category", "Experiment", "Run ID", "Detail"];
const auditSheet = addDataSheet(workbook, { name: "Audit", title: "Audit and caveats", note: "Missing, ambiguous, excluded or conflicting evidence. Items are retained rather than guessed or silently repaired.", headers: auditHeaders, labels: auditLabels, rows: data.audit, tableName: "AuditTable", widths: { severity: 14, category: 32, experiment: 35, run_id: 45, detail: 115 } });
if (auditSheet.endRow >= 5) {
  auditSheet.sheet.getRange(`A5:E${auditSheet.endRow}`).conditionalFormats.add("containsText", { text: "ERROR", format: { fill: RED, font: { color: "#9C0006", bold: true } } });
  auditSheet.sheet.getRange(`A5:E${auditSheet.endRow}`).conditionalFormats.add("containsText", { text: "WARNING", format: { fill: AMBER, font: { color: "#7F6000" } } });
}

// Build the formula-driven session summary after source sheets exist.
const summary = workbook.worksheets.getItem("Summary");
summary.showGridLines = false;
const sessionGroups = [...groupRows(data.requirement_runs, (r) => `${r.experiment}|${r.session_id}`).entries()];
const summaryHeaders = ["Original experiment", "Publication label", "Scope", "Session ID", "Model-role configuration", "Subset", "Repetition", "Runs", "Unique requirements", "Successful outputs", "Completed unsuccessful", "Incomplete", "Timed n", "Mean run (s)", "Sample SD (s)", "Median run (s)", "Total run (s)", "Iteration n", "Mean attempts", "Sample SD attempts", "Median attempts", "Max attempts", "Successful iteration n", "Mean attempts successful", "API n", "Mean API (s)", "Total API (s)", "Transport attempts"];
styleTitle(summary, colName(summaryHeaders.length), "Runtime and iteration summary", "Formula-driven summaries by formal experiment session. Completed unsuccessful runs remain in overall timing and iteration statistics.");
summary.getRange(`A4:${colName(summaryHeaders.length)}4`).values = [summaryHeaders];
summary.getRange(`A4:${colName(summaryHeaders.length)}4`).format = { fill: NAVY, font: { name: FONT, size: 9, bold: true, color: "#FFFFFF" }, wrapText: true, borders: { preset: "all", style: "thin", color: GRID }, verticalAlignment: "center" };
summary.getRange("A4").format.rowHeight = 42;
const runRowById = new Map(data.requirement_runs.map((r, i) => [r.run_id, i + 5]));
const indexBySession = new Map(data.experiment_index.map((r) => [`${r.original_experiment}|${r.session_id}`, r]));
for (let i = 0; i < sessionGroups.length; i++) {
  const [key, rows] = sessionGroups[i];
  const target = i + 5;
  const idx = indexBySession.get(key);
  const sourceRows = rows.map((r) => runRowById.get(r.run_id)).sort((a, b) => a - b);
  const start = sourceRows[0], end = sourceRows[sourceRows.length - 1];
  summary.getRange(`A${target}:G${target}`).values = [[idx.original_experiment, idx.publication_label, idx.scope, idx.session_id, idx.model_role_configuration, idx.benchmark_subset, idx.repetition]];
  summary.getRange(`H${target}`).formulas = [[`=COUNTA('Requirement_Runs'!$E$${start}:$E$${end})`]];
  summary.getRange(`I${target}:L${target}`).values = [[
    idx.unique_requirements, rows.filter((r) => r.successful_output).length,
    rows.filter((r) => r.completed_unsuccessful).length, rows.filter((r) => !r.completed).length,
  ]];
  summary.getRange(`M${target}:V${target}`).formulas = [[
    `=COUNT('Requirement_Runs'!$P$${start}:$P$${end})`, `=AVERAGE('Requirement_Runs'!$P$${start}:$P$${end})`, `=STDEV.S('Requirement_Runs'!$P$${start}:$P$${end})`, `=MEDIAN('Requirement_Runs'!$P$${start}:$P$${end})`, `=SUM('Requirement_Runs'!$P$${start}:$P$${end})`,
    `=COUNT('Requirement_Runs'!$R$${start}:$R$${end})`, `=AVERAGE('Requirement_Runs'!$R$${start}:$R$${end})`, `=STDEV.S('Requirement_Runs'!$R$${start}:$R$${end})`, `=MEDIAN('Requirement_Runs'!$R$${start}:$R$${end})`, `=MAX('Requirement_Runs'!$R$${start}:$R$${end})`,
  ]];
  const successfulAttempts = rows.filter((r) => r.successful_output && typeof r.candidate_attempts === "number").map((r) => r.candidate_attempts);
  summary.getRange(`W${target}:X${target}`).values = [[successfulAttempts.length, mean(successfulAttempts)]];
  summary.getRange(`Y${target}:AB${target}`).formulas = [[
    `=COUNT('Requirement_Runs'!$Q$${start}:$Q$${end})`, `=AVERAGE('Requirement_Runs'!$Q$${start}:$Q$${end})`, `=SUM('Requirement_Runs'!$Q$${start}:$Q$${end})`, `=SUM('Requirement_Runs'!$Y$${start}:$Y$${end})`,
  ]];
}
const sessionEnd = 4 + sessionGroups.length;
summary.getRange(`A4:AB${sessionEnd}`).format.borders = { preset: "all", style: "thin", color: GRID };
summary.getRange(`A5:AB${sessionEnd}`).format.font = { name: FONT, size: 9, color: "#1F2937" };
summary.getRange(`N5:Q${sessionEnd}`).format.numberFormat = "0.000";
summary.getRange(`S5:X${sessionEnd}`).format.numberFormat = "0.000";
summary.getRange(`Z5:AA${sessionEnd}`).format.numberFormat = "0.000";
const sessionTable = summary.tables.add(`A4:AB${sessionEnd}`, true, "SessionSummaryTable");
sessionTable.style = "TableStyleMedium2";
sessionTable.showFilterButton = true;

// Separate RDF runtime summary, using formulas over contiguous ledger blocks.
const rdfGroups = [...groupRows(data.rdf_evaluation, (r) => `${r.experiment}|${r.publication_label}|${r.stage}|${r.evaluation_run_id}`).entries()];
const rdfStartHeader = sessionEnd + 3;
summary.mergeCells(`A${rdfStartHeader - 1}:P${rdfStartHeader - 1}`);
summary.getRange(`A${rdfStartHeader - 1}`).values = [["Separate RDF evaluation runtime summary"]];
summary.getRange(`A${rdfStartHeader - 1}:P${rdfStartHeader - 1}`).format = { fill: BLUE, font: { name: FONT, size: 11, bold: true, color: NAVY } };
const rdfSummaryHeaders = ["Original experiment", "Publication label", "Stage", "Evaluation run ID", "Model key", "Cases", "Unique requirements", "Timed n", "Mean RDF (s)", "Sample SD (s)", "Median RDF (s)", "Max RDF (s)", "Total RDF (s)", "Executed", "Expected agreement", "Source dataset"];
summary.getRange(`A${rdfStartHeader}:P${rdfStartHeader}`).values = [rdfSummaryHeaders];
summary.getRange(`A${rdfStartHeader}:P${rdfStartHeader}`).format = { fill: NAVY, font: { name: FONT, size: 9, bold: true, color: "#FFFFFF" }, wrapText: true, borders: { preset: "all", style: "thin", color: GRID } };
const rdfRowMap = new Map(data.rdf_evaluation.map((r, i) => [`${r.evaluation_run_id}|${r.stage}|${r.case_id}|${r.publication_label}`, i + 5]));
for (let i = 0; i < rdfGroups.length; i++) {
  const [, rows] = rdfGroups[i];
  const r0 = rows[0];
  const target = rdfStartHeader + 1 + i;
  const sourceRows = rows.map((r) => rdfRowMap.get(`${r.evaluation_run_id}|${r.stage}|${r.case_id}|${r.publication_label}`)).sort((a, b) => a - b);
  const start = sourceRows[0], end = sourceRows[sourceRows.length - 1];
  summary.getRange(`A${target}:E${target}`).values = [[r0.experiment, r0.publication_label, r0.stage, r0.evaluation_run_id, r0.model]];
  summary.getRange(`F${target}:G${target}`).values = [[rows.length, new Set(rows.map((r) => r.requirement_id)).size]];
  summary.getRange(`H${target}:M${target}`).formulas = [[
    `=COUNT('RDF_Evaluation'!$R$${start}:$R$${end})`, `=AVERAGE('RDF_Evaluation'!$R$${start}:$R$${end})`, `=STDEV.S('RDF_Evaluation'!$R$${start}:$R$${end})`, `=MEDIAN('RDF_Evaluation'!$R$${start}:$R$${end})`, `=MAX('RDF_Evaluation'!$R$${start}:$R$${end})`, `=SUM('RDF_Evaluation'!$R$${start}:$R$${end})`,
  ]];
  summary.getRange(`N${target}:O${target}`).values = [[rows.filter((r) => r.execution_status === "EXECUTED").length, rows.filter((r) => r.behavioral_match === true).length]];
  summary.getRange(`P${target}`).values = [[r0.source_path]];
}
const rdfSummaryEnd = rdfStartHeader + rdfGroups.length;
summary.getRange(`A${rdfStartHeader}:P${rdfSummaryEnd}`).format.borders = { preset: "all", style: "thin", color: GRID };
summary.getRange(`A${rdfStartHeader + 1}:P${rdfSummaryEnd}`).format.font = { name: FONT, size: 9, color: "#1F2937" };
summary.getRange(`I${rdfStartHeader + 1}:M${rdfSummaryEnd}`).format.numberFormat = "0.000";
const rdfSummaryTable = summary.tables.add(`A${rdfStartHeader}:P${rdfSummaryEnd}`, true, "RdfRuntimeSummaryTable");
rdfSummaryTable.style = "TableStyleMedium2";
summary.freezePanes.freezeRows(4);
summary.freezePanes.freezeColumns(2);
for (let i = 1; i <= 28; i++) summary.getRange(`${colName(i)}1`).format.columnWidth = i <= 7 ? 22 : 15;
summary.getRange("D1").format.columnWidth = 44;
summary.getRange("E1").format.columnWidth = 65;
summary.getRange("F1").format.columnWidth = 38;
summary.getRange("P1").format.columnWidth = 90;

workbook.recalculate();
const formulaErrors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
console.log("FORMULA_ERRORS", formulaErrors.ndjson);
const summaryInspect = await workbook.inspect({ kind: "table", sheetId: "Summary", range: `A1:AB${Math.min(sessionEnd, 16)}`, include: "values,formulas", tableMaxRows: 16, tableMaxCols: 28, maxChars: 12000 });
console.log("SUMMARY_INSPECT", summaryInspect.ndjson);

const previewRanges = {
  "Summary": `A1:AB${Math.min(rdfSummaryEnd, 48)}`,
  "README": `A1:B${2 + readmeRows.length}`,
  "Experiment_Index": `A1:K${Math.min(4 + data.experiment_index.length, 32)}`,
  "Requirement_Runs": "A1:AO28",
  "Iterations": "A1:U28",
  "API_Calls": "A1:V28",
  "RDF_Evaluation": "A1:W28",
  "Audit": `A1:E${Math.min(4 + data.audit.length, 30)}`,
};
if (process.env.SKIP_PREVIEWS !== "1") {
  for (const sheetName of ["Summary", "README", "Experiment_Index", "Requirement_Runs", "Iterations", "API_Calls", "RDF_Evaluation", "Audit"]) {
    const preview = await workbook.render({ sheetName, range: previewRanges[sheetName], autoCrop: "all", scale: 0.8, format: "png" });
    await fs.writeFile(`${previewDir}/runtime_${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}

const runtimeBlob = await SpreadsheetFile.exportXlsx(workbook);
await runtimeBlob.save(runtimeOutput);

// Add a concise snapshot to a preserved copy of the current Paper Tables workbook.
const paperBlob = await FileBlob.load(paperInput);
const paperBook = await SpreadsheetFile.importXlsx(paperBlob);
const initialPaper = await paperBook.inspect({ kind: "sheet", include: "id,name", maxChars: 6000 });
console.log("PAPER_SHEETS_BEFORE", initialPaper.ndjson);
let paperSheet;
try {
  paperSheet = paperBook.worksheets.getItem("Runtime summary");
  paperSheet.getUsedRange()?.clear({ applyTo: "all" });
} catch {
  paperSheet = paperBook.worksheets.add("Runtime summary");
}
paperSheet.showGridLines = false;
paperSheet.mergeCells("A1:M1");
paperSheet.getRange("A1").values = [["Table 17: Existing runtime and candidate-attempt evidence"]];
paperSheet.getRange("A1:M1").format = { fill: NAVY, font: { name: FONT, size: 15, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
paperSheet.getRange("A1").format.rowHeight = 28;
paperSheet.mergeCells("A2:M2");
paperSheet.getRange("A2").values = [["Generation runtime uses run_started to run_finished. Logical API time is reported separately. Completed unsuccessful runs remain in overall statistics. Values are recovered from existing logs; no experiments were rerun."]];
paperSheet.getRange("A2:M2").format = { fill: LIGHT, font: { name: FONT, size: 9, italic: true, color: "#44546A" }, wrapText: true };
paperSheet.getRange("A2").format.rowHeight = 34;
const paperHeaders = ["Comparison", "Publication label", "Original experiment", "Subset/session", "Timed runs", "Unique requirements", "Successful outputs", "Mean run (s)", "Sample SD (s)", "Median run (s)", "Total run (s)", "Mean attempts", "Max attempts"];
paperSheet.getRange("A4:M4").values = [paperHeaders];
paperSheet.getRange("A4:M4").format = { fill: NAVY, font: { name: FONT, size: 9, bold: true, color: "#FFFFFF" }, wrapText: true, borders: { preset: "all", style: "thin", color: GRID } };

function paperRow(comparison, label, experiment, subset, rows) {
  const timed = stats(rows.map((r) => r.elapsed_seconds));
  const attempts = stats(rows.map((r) => r.candidate_attempts));
  return [comparison, label, experiment, subset, timed.n, new Set(rows.map((r) => r.requirement_id)).size, rows.filter((r) => r.successful_output).length, timed.mean, timed.sd, timed.median, timed.total, attempts.mean, attempts.max];
}

const paperRows = [];
const noSemantic = data.requirement_runs.filter((r) => r.experiment === "LUNA_NO_SEMANTIC_VALIDATOR");
const noSemanticRun1 = noSemantic.filter((r) => r.repetition === "RUN_01");
const singleShot = data.requirement_runs.filter((r) => r.experiment === "LUNA_CONTEXTUAL_SINGLESHOT");
paperRows.push(paperRow("Main paper", "Single-shot", "LUNA_CONTEXTUAL_SINGLESHOT", "RUN_01; full 268 requirements", singleShot));
paperRows.push(paperRow("Main paper", "NLTL_v2", "LUNA_NO_SEMANTIC_VALIDATOR", "RUN_01; full 268 requirements", noSemanticRun1));
paperRows.push(paperRow("Repetition evidence", "NLTL_v2", "LUNA_NO_SEMANTIC_VALIDATOR", "RUN_01-RUN_10; 2,680 requirement-runs", noSemantic));

const lunaSample = data.requirement_runs.filter((r) => r.experiment === "FULL_REPAIR_V2" && r.scaling_sample_member);
const modelGroups = [
  ["GPT-5.6 Luna", "gpt-5.6-luna-2026-07-09", lunaSample],
  ["GPT-5.6 Sol", "gpt-5.6-sol-2026-07-09", data.requirement_runs.filter((r) => r.experiment === "MODEL_SCALING_FULL_REPAIR_V2_50" && r.generator_model.includes("gpt-5.6-sol"))],
  ["Gemini 3.5 Flash", "gemini-3.5-flash", data.requirement_runs.filter((r) => r.experiment === "MODEL_SCALING_FULL_REPAIR_V2_50" && r.generator_model.includes("gemini-3.5-flash"))],
  ["GPT-OSS 120B", "gpt-oss-120b", data.requirement_runs.filter((r) => r.experiment === "MODEL_SCALING_FULL_REPAIR_V2_50" && r.generator_model.includes("gpt-oss-120b"))],
];
for (const [label, modelId, rows] of modelGroups) paperRows.push(paperRow("Four-model sample", label, rows[0]?.experiment || "", `${modelId}; frozen 50-requirement sample`, rows));

paperSheet.getRange(`A5:M${4 + paperRows.length}`).values = paperRows;
paperSheet.getRange(`A4:M${4 + paperRows.length}`).format.borders = { preset: "all", style: "thin", color: GRID };
paperSheet.getRange(`A5:M${4 + paperRows.length}`).format.font = { name: FONT, size: 9, color: "#1F2937" };
paperSheet.getRange(`H5:L${4 + paperRows.length}`).format.numberFormat = "0.00";
const paperTable = paperSheet.tables.add(`A4:M${4 + paperRows.length}`, true, "RuntimeSummaryTable");
paperTable.style = "TableStyleMedium2";
const paperEnd = 6 + paperRows.length;
paperSheet.getRange("A1").format.columnWidth = 20;
paperSheet.getRange("B1").format.columnWidth = 22;
paperSheet.getRange("C1").format.columnWidth = 34;
paperSheet.getRange("D1").format.columnWidth = 45;
paperSheet.getRange("E1:M1").format.columnWidth = 16;
paperSheet.freezePanes.freezeRows(4);
paperSheet.mergeCells(`A${6 + paperRows.length}:M${6 + paperRows.length}`);
paperSheet.getRange(`A${6 + paperRows.length}`).values = [["Caveat: logged RDF timing datasets retain 2,186 full-benchmark and 381 scaling cases. Current manuscript/Paper Tables behavioural denominators are 2,160 and 373; do not substitute these timing-ledger denominators for the current reported results."]];
paperSheet.getRange(`A${6 + paperRows.length}:M${6 + paperRows.length}`).format = { fill: AMBER, font: { name: FONT, size: 9, color: "#7F6000" }, wrapText: true };
paperSheet.getRange(`A${6 + paperRows.length}`).format.rowHeight = 36;
paperBook.recalculate();
const paperErrors = await paperBook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "paper workbook formula error scan" });
console.log("PAPER_FORMULA_ERRORS", paperErrors.ndjson);
const paperInspect = await paperBook.inspect({ kind: "table", sheetId: "Runtime summary", range: `A1:M${7 + paperRows.length}`, include: "values,formulas", tableMaxRows: 20, tableMaxCols: 13, maxChars: 10000 });
console.log("PAPER_RUNTIME_INSPECT", paperInspect.ndjson);
const paperPreview = await paperBook.render({ sheetName: "Runtime summary", autoCrop: "all", scale: 1.2, format: "png" });
await fs.writeFile(`${previewDir}/paper_Runtime_summary.png`, new Uint8Array(await paperPreview.arrayBuffer()));
const paperOutBlob = await SpreadsheetFile.exportXlsx(paperBook);
await paperOutBlob.save(paperOutput);

console.log(JSON.stringify({ runtimeOutput, paperOutput, previewDir, paperRows: paperRows.length, sessionSummaryRows: sessionGroups.length, rdfSummaryRows: rdfGroups.length }, null, 2));
