import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const batchRoot = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const batch = JSON.parse(await fs.readFile(path.join(batchRoot, "batch_definition.json"), "utf8"));
const preflight = JSON.parse(await fs.readFile(path.join(batchRoot, "engineering_preflight.json"), "utf8"));
const projectRoot = path.resolve(batchRoot, "../../..");
const devRoot = path.join(projectRoot, "BENCHMARK_VOCABULARY", "DEVELOPMENT", "DEV_R8_1_POSTCONFIRMATION");
const devManifest = JSON.parse(await fs.readFile(path.join(devRoot, "development_manifest.json"), "utf8"));
const devRegistry = JSON.parse(await fs.readFile(path.join(devRoot, "registry", "term_registry.json"), "utf8"));
const devIndex = JSON.parse(await fs.readFile(path.join(devRoot, "requirement_term_index.json"), "utf8"));
const fixtureCatalog = JSON.parse(await fs.readFile(path.join(batchRoot, "rdf_fixtures", "fixture_catalog.json"), "utf8"));
const fixtureValidation = JSON.parse(await fs.readFile(path.join(batchRoot, "rdf_fixtures", "validation_report.json"), "utf8"));
const calibrationAnalysis = JSON.parse(await fs.readFile(path.join(batchRoot, "r7_calibration_analysis.json"), "utf8"));
const evaluationPath = path.join(projectRoot, "SHACL_GENERATION_PIPELINE", "outputs", "development_batch01", "evaluations", "EVAL-BATCH01-R7-ACCEPTED-SHAPES-20260813T070815332270Z", "evaluation_results.jsonl");
const evaluationRows = (await fs.readFile(evaluationPath, "utf8")).trim().split("\n").map((line) => JSON.parse(line));
const evaluationByCase = new Map(evaluationRows.map((row) => [row.case_id, row]));
const outputPath = path.join(batchRoot, "batch01_vocabulary_and_fixture_tracker.xlsx");

const colors = {
  navy: "#17324D", teal: "#0F766E", pale: "#E8F1F5", white: "#FFFFFF",
  gray: "#5B6573", line: "#CBD5E1", green: "#DCFCE7", red: "#FEE2E2", amber: "#FEF3C7",
};

function colName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

function addSheet(workbook, name, headers, rows, widths = {}) {
  const sheet = workbook.worksheets.getItem(name);
  sheet.showGridLines = false;
  const lastCol = colName(headers.length - 1);
  sheet.getRange(`A1:${lastCol}1`).format.fill = colors.navy;
  sheet.getRange("A1").values = [["NLTL Development Calibration - Batch 01"]];
  sheet.getRange("A1").format.font = { bold: true, color: colors.white, size: 16 };
  sheet.getRange(`A2:${lastCol}2`).format = { fill: colors.pale, font: { italic: true, color: colors.gray } };
  sheet.getRange("A2").values = [[`${name} | ${batch.batch_id} | vocabulary is not frozen`]];
  sheet.getRange(`A4:${lastCol}4`).values = [headers];
  sheet.getRange(`A4:${lastCol}4`).format = {
    fill: colors.teal, font: { bold: true, color: colors.white }, wrapText: true,
    verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: colors.line },
  };
  sheet.getRange(`A4:${lastCol}4`).format.rowHeight = 32;
  if (rows.length) {
    const lastRow = 4 + rows.length;
    sheet.getRange(`A5:${lastCol}${lastRow}`).values = rows;
    sheet.getRange(`A5:${lastCol}${lastRow}`).format = {
      verticalAlignment: "top", borders: { insideHorizontal: { style: "thin", color: colors.line } },
    };
    sheet.tables.add(`A4:${lastCol}${lastRow}`, true, `T_${name.replace(/[^A-Za-z0-9]/g, "")}`);
    headers.forEach((header, index) => {
      const col = colName(index);
      const range = sheet.getRange(`${col}5:${col}${lastRow}`);
      range.format.columnWidth = widths[header] ?? (/TEXT|REQUIREMENT|ISSUE|VARIANT|TERMS|NOTES/.test(header) ? 48 : 18);
      if (/TEXT|REQUIREMENT|ISSUE|VARIANT|TERMS|NOTES/.test(header)) range.format.wrapText = true;
      if (/COUNT|SEQUENCE|PAGE|MINIMUM/.test(header)) range.format.numberFormat = "#,##0";
      if (/STATUS|DECISION/.test(header)) {
        range.conditionalFormats.add("containsText", { text: "READY", format: { fill: colors.green } });
        range.conditionalFormats.add("containsText", { text: "COMPLETE", format: { fill: colors.green } });
        range.conditionalFormats.add("containsText", { text: "NEW", format: { fill: colors.amber } });
        range.conditionalFormats.add("containsText", { text: "REMODEL", format: { fill: colors.red } });
        range.conditionalFormats.add("containsText", { text: "UNIT", format: { fill: colors.amber } });
      }
    });
  }
  sheet.freezePanes.freezeRows(4);
  sheet.getRange(`A1:${lastCol}${Math.max(5, rows.length + 4)}`).format.font.name = "Aptos";
  return sheet;
}

const workbook = Workbook.create();
for (const name of ["README", "REQUIREMENTS", "PREFLIGHT", "DRAFT_TERMS", "R2_INDEX_GAPS", "DEVELOPMENT_TERMS", "OWNERSHIP", "STABILIZATION", "RDF_CASES", "CALIBRATION_ANALYSIS"]) {
  workbook.worksheets.add(name);
}
const summary = workbook.worksheets.add("SUMMARY");
summary.showGridLines = false;
summary.getRange("A1:D1").format.fill = colors.navy;
summary.getRange("A1").values = [["NLTL Development Calibration - Batch 01"]];
summary.getRange("A1").format.font = { bold: true, color: colors.white, size: 16 };
summary.getRange("A2:D2").format = { fill: colors.pale, font: { italic: true, color: colors.gray } };
summary.getRange("A2").values = [["First 50 eligible requirements | engineering preflight"]];
summary.getRange("A4:B4").values = [["METRIC", "VALUE"]];
summary.getRange("A4:B4").format = { fill: colors.teal, font: { bold: true, color: colors.white } };
summary.getRange("A5:A14").values = [["Requirements"], ["Static"], ["Static Calculation"], ["Planned minimum RDF variants"], ["Unique draft terms/values"], ["Ready-after-index-check decisions"], ["R8 stabilization registry terms"], ["R8 cumulative development additions"], ["Authored RDF cases"], ["RDF fixture validation"]];
summary.getRange("B5:B14").formulas = [
  ["=COUNTA('REQUIREMENTS'!$B$5:$B$54)"],
  ["=COUNTIF('REQUIREMENTS'!$G$5:$G$54,\"Static\")"],
  ["=COUNTIF('REQUIREMENTS'!$G$5:$G$54,\"Static Calculation\")"],
  ["=SUM('REQUIREMENTS'!$L$5:$L$54)"],
  ["=COUNTA('DRAFT_TERMS'!$A$5:$A$250)"],
  ["=COUNTIF('PREFLIGHT'!$E$5:$E$54,\"READY_AFTER_INDEX_CHECK\")"],
  ["=COUNTA('DEVELOPMENT_TERMS'!$A$5:$A$1200)"],
  ["=COUNTIF('DEVELOPMENT_TERMS'!$J$5:$J$1200,\"ADD_DEVELOPMENT_TERM\")"],
  ["=COUNTA('RDF_CASES'!$A$5:$A$204)"],
  [`=${JSON.stringify(fixtureValidation.status)}`],
];
summary.getRange("A5:A14").format.font = { bold: true, color: colors.navy };
summary.getRange("B5:B13").format.numberFormat = "#,##0";
summary.getRange("A16:D20").values = [
  ["PHASE", "Vocabulary development/calibration; do not report as final benchmark accuracy.", "", ""],
  ["ORDER", "RDF expectations are created before fresh SHACL generation.", "", ""],
  ["VOCABULARY", "R2 is the source baseline; R8.1 preserves the R8 confirmation evidence and records three post-confirmation schema/index corrections without adding vocabulary terms.", "", ""],
  ["LEAKAGE", "Development fixtures become regression tests. Official evaluation will be regenerated after the final vocabulary/pipeline freeze.", "", ""],
  ["NEXT GATE", "R8 confirmation found no remaining vocabulary-name gap. R8.1 now needs only a no-API fixture/schema recheck, after which generation may scale with RDF evaluation kept separate.", "", ""],
];
summary.getRange("A16:A20").format = { fill: colors.pale, font: { bold: true, color: colors.navy } };
summary.getRange("B16:D20").format.wrapText = true;
summary.getRange("A16:D20").format.rowHeight = 38;
summary.getRange("A1:D20").format.font.name = "Aptos";
summary.getRange("A1:A20").format.columnWidth = 40;
summary.getRange("B1:B20").format.columnWidth = 82;
summary.freezePanes.freezeRows(4);

const readmeSheet = addSheet(workbook, "README", ["SECTION", "DETAIL"], [
  ["PURPOSE", "Active development tracker for the first 50 generation-eligible requirements."],
  ["SELECTION", batch.selection_rule],
  ["SOURCE LOCK", batch.source_lock_id],
  ["SOURCE EVIDENCE SHA256", batch.source_files.requirement_evidence_sha256],
  ["SOURCE INDEX SHA256", batch.source_files.requirement_term_index_sha256],
  ["BOUNDARY", "Batch membership is fixed; vocabulary terms, indexes and fixtures are still under development."],
  ["DEVELOPMENT BINDING", devManifest.developmentId],
  ["DEVELOPMENT STATUS", devManifest.status],
  ["RDF FIXTURES", `${fixtureCatalog.cases} cases; ${fixtureValidation.status}; one pass, one fail and one boundary/non-applicability case per requirement.`],
  ["STABILIZATION", "R8 repairs context delivery for TRF-037 and TRF-042 and adds deterministic guards for brittle numeric equality and mutually exclusive case properties."],
  ["NO ANSWER LOGIC", "Draft vocabulary terms must represent observations, entities, relations, quantities or evidence - never a precomputed compliance answer."],
], { SECTION: 28, DETAIL: 95 });
readmeSheet.getRange("B5:B14").format.wrapText = true;
readmeSheet.getRange("A5:B14").format.rowHeight = 34;

const requirementRows = batch.requirements.map((r) => [
  r.sequence, r.requirement_id, r.source_sheet, r.page, r.clause, r.edition, r.category,
  r.encoding_pattern, r.r2_indexed_term_count, r.r2_indexed_terms.join(" | "),
  r.fixture_pattern, r.minimum_fixture_variants,
  devIndex.requirements[r.requirement_id].length, devIndex.requirements[r.requirement_id].join(" | "),
  r.normalized_requirement,
]);
addSheet(workbook, "REQUIREMENTS", [
  "SEQUENCE", "REQUIREMENT_ID", "SOURCE_SHEET", "PAGE", "CLAUSE", "EDITION", "CATEGORY",
  "ENCODING_PATTERN", "R2_INDEXED_TERM_COUNT", "R2_INDEXED_TERMS", "FIXTURE_PATTERN",
  "MINIMUM_FIXTURE_VARIANTS", "R8_DEV_INDEXED_TERM_COUNT", "R8_DEV_INDEXED_TERMS", "NORMALIZED_REQUIREMENT",
], requirementRows, { EDITION: 36, CATEGORY: 22, ENCODING_PATTERN: 30, R7_DEV_INDEXED_TERMS: 64, NORMALIZED_REQUIREMENT: 80 });

const preflightRows = preflight.requirements.map((r) => [
  r.sequence, r.requirement_id, r.page, r.clause, r.decision,
  r.existing_terms_to_link.join(" | "), r.draft_new_terms.join(" | "),
  r.existing_terms_not_currently_indexed.join(" | "), r.engineering_issue,
  r.planned_fixture_variants, r.review_status,
]);
addSheet(workbook, "PREFLIGHT", [
  "SEQUENCE", "REQUIREMENT_ID", "PAGE", "CLAUSE", "DECISION", "EXISTING_TERMS_TO_LINK",
  "DRAFT_NEW_TERMS", "EXISTING_TERMS_NOT_CURRENTLY_INDEXED", "ENGINEERING_ISSUE",
  "PLANNED_FIXTURE_VARIANTS", "REVIEW_STATUS",
], preflightRows, { DECISION: 28, ENGINEERING_ISSUE: 72, PLANNED_FIXTURE_VARIANTS: 58, REVIEW_STATUS: 32 });

const termMap = new Map();
for (const row of preflight.requirements) {
  for (const term of row.draft_new_terms) {
    if (!termMap.has(term)) termMap.set(term, []);
    termMap.get(term).push(row.requirement_id);
  }
}
const termRows = [...termMap.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([term, ids], index) => [
  term, ids.join(" | "), ids.length, "PROVISIONAL", "Initial preflight term retained for comparison with the consolidated R7 registry.",
]);
addSheet(workbook, "DRAFT_TERMS", ["DRAFT_LOCAL_NAME", "REQUIREMENT_IDS", "REQUIREMENT_COUNT", "STATUS", "NEXT_REVIEW"], termRows,
  { DRAFT_LOCAL_NAME: 46, REQUIREMENT_IDS: 42, STATUS: 18, NEXT_REVIEW: 72 });

const gapRows = preflight.requirements.flatMap((r) => r.existing_terms_not_currently_indexed.map((term) => [
  r.requirement_id, term, r.decision, "ADD_TO_DEVELOPMENT_INDEX_AFTER_SEMANTIC_CONFIRMATION",
]));
addSheet(workbook, "R2_INDEX_GAPS", ["REQUIREMENT_ID", "EXISTING_TERM", "PREFLIGHT_DECISION", "ACTION"], gapRows,
  { EXISTING_TERM: 44, PREFLIGHT_DECISION: 28, ACTION: 52 });

const developmentRows = devRegistry.map((term) => [
  term.localName, term.iri, term.kind, term.parentOrRange, term.datatype ?? "", term.unitSymbol ?? "",
  (term.requirements ?? []).join(" | "), term.namingBasis ?? "", term.namingRule ?? "",
  String(term.conceptId ?? "").startsWith("VOC-DEV") ? "ADD_DEVELOPMENT_TERM" : "REUSE_R2_TERM",
]);
addSheet(workbook, "DEVELOPMENT_TERMS", [
  "LOCAL_NAME", "EXACT_IRI", "KIND", "RANGE_OR_PARENT", "DATATYPE", "UNIT", "REQUIREMENT_IDS",
  "NAMING_BASIS", "NAMING_RULE", "ACTION",
], developmentRows, { LOCAL_NAME: 46, EXACT_IRI: 62, KIND: 24, RANGE_OR_PARENT: 58, REQUIREMENT_IDS: 44, NAMING_BASIS: 72, NAMING_RULE: 72, ACTION: 28 });

const ownershipRows = Object.entries(devIndex.termOwners ?? {}).flatMap(([requirementId, owners]) =>
  Object.entries(owners).map(([localName, owner]) => [
    requirementId,
    devIndex.requirementTargetOwner?.[requirementId] ?? "",
    localName,
    owner,
    (devIndex.semanticObligations?.[requirementId] ?? []).join(" | "),
    "AUTHORITATIVE_REQUIREMENT_SCOPED",
  ])
);
addSheet(workbook, "OWNERSHIP", [
  "REQUIREMENT_ID", "TARGET_OWNER", "LOCAL_NAME", "REQUIRED_OWNER", "SEMANTIC_OBLIGATIONS", "STATUS",
], ownershipRows, { TARGET_OWNER: 34, LOCAL_NAME: 46, REQUIRED_OWNER: 34, SEMANTIC_OBLIGATIONS: 90, STATUS: 38 });

const stabilizationRows = [
  ["TRF-037", "CONTEXT_INDEX_GAP", "hasDirectAnalysisCase existed in R7 but was absent from the scoped context; iceLoadAreaFactorCa ownership also needed the directAnalysisCase path.", "RESOLVED", "Index hasDirectAnalysisCase and directAnalysisCase; mark ca owner; generic owner-path expansion supplies canonical object-property paths."],
  ["TRF-042", "CONTEXT_INDEX_GAP", "plating existed in R7 and was the authoritative target owner, but the class was not in the scoped context.", "RESOLVED", "Index the existing plating class and always include the authoritative target-owner class."],
  ["TRF-022 | TRF-027", "NUMERIC_SERIALIZATION", "Numeric sh:hasValue on qudt:numericValue rejected equivalent decimal lexical forms.", "RESOLVED_GENERAL_GUARD", "Static validator rejects numeric sh:hasValue; prompts require equal numeric bounds for constants and tolerance for derived results."],
  ["TRF-030", "NODE_MODEL_OVERCONSTRAINT", "A case shape could require both vertical and horizontal position properties although cases represent alternative axes.", "RESOLVED_GENERAL_GUARD", "Verified exclusivePropertyGroups metadata plus deterministic conjunctive-shape rejection."],
  ["TRF-025", "TOLERANCE_SCALE", "Generated C2 tolerance was based on the reported value rather than the expected formula result.", "RESOLVED_GENERAL_GUIDANCE", "Generator and validator now require derived tolerances to scale from the expected result."],
  ["TRF-011", "GENERATOR_SYNTAX", "Final repair contained a stray token and invalid Turtle.", "ALREADY_BLOCKED_AND_GUIDANCE_STRENGTHENED", "Existing parser gate prevents acceptance; generator now performs an explicit pre-return syntax self-check."],
  ["ALL", "STATUS_CLASSIFICATION", "Matcher exhaustion was previously labeled VOCABULARY_GAP even when a canonical term might exist outside retrieval candidates.", "RESOLVED", "Runtime status is TERM_RESOLUTION_UNRESOLVED; a true vocabulary gap requires registry/index audit evidence."],
  ["TRF-025", "UNIT_METADATA_GAP", "C1 and C2 are formula outputs whose units were left unspecified, causing the generated shape and canonical fixtures to disagree.", "RESOLVED_R8_1", "Assign unit:N to C1 and C2 from the verified dimensions of every additive formula term."],
  ["TRF-030", "OVER_STRONG_EXCLUSIVITY", "The semantic validator correctly noted that the clause does not prohibit a case from recording both coordinates.", "RESOLVED_R8_1", "Remove the R8 exclusivePropertyGroups declaration; retain the requirement for several vertical and horizontal cases."],
  ["TRF-022", "UNSUPPORTED_APPLICABILITY", "The R8 shape inherited a construction-date branch although clause 3.2.2 contains no date condition, allowing the deliberate failure to pass.", "RESOLVED_R8_1", "Remove constructionStageDate from the TRF-022 scoped requirement index."],
];
const stabilizationSheet = addSheet(workbook, "STABILIZATION", [
  "REQUIREMENT_ID", "FAILURE_CLASS", "R7_EVIDENCE", "R8_STATUS", "ENGINEERING_RESOLUTION",
], stabilizationRows, { REQUIREMENT_ID: 28, FAILURE_CLASS: 34, R7_EVIDENCE: 82, R8_STATUS: 38, ENGINEERING_RESOLUTION: 90 });
stabilizationSheet.getRange("C5:E14").format.wrapText = true;
stabilizationSheet.getRange("A5:E14").format.rowHeight = 54;

const rdfRows = fixtureCatalog.caseRecords.map((item) => [
  item.caseId, item.requirementId, item.caseKind, item.expectedConforms, item.sourcePage, item.sourceClause,
  item.scenarioBasis, item.rdfFile, item.rdfSha256, item.tripleCount, item.developmentVocabularyId,
  item.calibrationOnly ? "YES" : "NO",
  evaluationByCase.has(item.caseId)
    ? (evaluationByCase.get(item.caseId).expected_match ? "EXPECTED_MATCH" : "EXPECTED_MISMATCH")
    : "NOT_IN_R7_ACCEPTED_SET",
]);
addSheet(workbook, "RDF_CASES", [
  "CASE_ID", "REQUIREMENT_ID", "CASE_KIND", "EXPECTED_CONFORMS", "SOURCE_PAGE", "SOURCE_CLAUSE",
  "SCENARIO_BASIS", "RDF_FILE", "RDF_SHA256", "TRIPLE_COUNT", "DEVELOPMENT_VOCABULARY_ID",
  "CALIBRATION_ONLY", "EXECUTION_STATUS",
], rdfRows, { CASE_ID: 34, CASE_KIND: 18, SCENARIO_BASIS: 68, RDF_FILE: 72, RDF_SHA256: 68, DEVELOPMENT_VOCABULARY_ID: 38, EXECUTION_STATUS: 22 });

const analysisRows = calibrationAnalysis.rows.map((item) => [
  item.requirement_id, item.run_id, item.generation_status, item.semantic_attempts,
  item.accepted ? "TRUE" : "FALSE", item.api_calls, item.evaluated_cases,
  item.expected_matches, item.classification, item.final_feedback,
]);
addSheet(workbook, "CALIBRATION_ANALYSIS", [
  "REQUIREMENT_ID", "R7_RUN_ID", "R7_GENERATION_STATUS", "R7_SEMANTIC_ATTEMPTS", "R7_ACCEPTED",
  "R7_API_CALLS", "R7_EVALUATED_CASES", "R7_EXPECTED_MATCHES",
  "CLASSIFICATION", "FINAL_FEEDBACK",
], analysisRows, {
  R7_RUN_ID: 48, R7_GENERATION_STATUS: 28, CLASSIFICATION: 34,
  FINAL_FEEDBACK: 90,
});

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, sheets: 11, requirements: requirementRows.length, draftTerms: termRows.length, developmentTerms: developmentRows.length, ownershipRows: ownershipRows.length, stabilizationRows: stabilizationRows.length, rdfCases: rdfRows.length, analysisRows: analysisRows.length, indexGaps: gapRows.length }));
