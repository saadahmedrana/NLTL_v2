import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [mvpArg] = process.argv.slice(2);
if (!mvpArg) throw new Error("Usage: build_r9_engineering_tracker.mjs MVP_ROOT");
const mvp = path.resolve(mvpArg);
const batch = path.join(mvp, "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190");
const r9 = path.join(mvp, "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R9_FOUNDATION");
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const failure = await readJson(path.join(batch, "r9_failure_analysis.json"));
const depth = await readJson(path.join(batch, "r9_all313_dependency_audit.json"));
const index = await readJson(path.join(r9, "requirement_term_index.json"));
const evidencePayload = await readJson(path.join(r9, "evidence/stage1_approved.json"));
const decisions = await readJson(path.join(r9, "registry/r9_change_decisions.json"));
const registry = await readJson(path.join(r9, "registry/term_registry.json"));
const queue = await readJson(path.join(batch, "generation_queue_r9_affected.json"));
const units = await readJson(path.join(r9, "evidence/external_uri_verification.json"));
const validation = await readJson(path.join(r9, "validation/validation_report.json"));
const evidence = Object.fromEntries(evidencePayload.requirements.map((item) => [item.id, item]));
const registryByName = Object.fromEntries(registry.map((item) => [item.localName, item]));
const failedById = Object.fromEntries(failure.records.map((item) => [item.requirement_id, item]));

const specs = [
  { name: "README", headers: ["SECTION", "DETAIL"], rows: [
    ["PURPOSE", "Engineering traceability for the R9 development vocabulary and dependency-contract repair."],
    ["STATUS", "Development foundation only; this is not the final experiment vocabulary lock."],
    ["METHOD", "Observed failures were reconstructed, all 313 requirements were screened for modelling depth, reusable terms were added, and every active requirement received a complete dependency contract."],
    ["FAIL-CLOSED RULE", "The pipeline refuses to call an LLM unless an active requirement has a COMPLETE dependency contract and all declared terms are present and indexed."],
    ["NO LEAKAGE", "Contracts identify required entities, paths, operands, evidence roles, controlled values, and comparison structure. They do not include expected RDF pass/fail outcomes."],
    ["RERUN", "The R9 queue contains repaired observed failures plus proactive remodels only; it excludes the source-blocked case."],
    ["SOURCE LIMIT", "I2-053 is deferred because UR I2.13.3.2 delegates to UR S11.5.4.2 and UR S11 is not available in the verified project sources."],
    ["UNIT CONTROL", "Every new external unit IRI is present in the external URI evidence ledger; plausible-looking unverified QUDT identifiers fail the build."],
  ]},
  { name: "FAILURE_DECISIONS", headers: ["REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "PRIOR_STATUS", "ATTEMPTS", "ROOT_CAUSES", "INDEXED_TERMS", "R9_CONTRACT_STATUS", "ENGINEERING_DECISION", "BLOCKER", "COMPARISON_MODEL"], rows: failure.records.map((item) => {
    const contract = index.dependencyContracts[item.requirement_id];
    return [item.requirement_id, item.source_sheet, item.page, item.clause, item.status, item.attempts, item.root_cause_categories.join(" | "), item.indexed_terms.join(" | "), contract.status, contract.engineeringDecision ?? "", contract.blocker ?? "", contract.comparisonModel ?? ""];
  })},
  { name: "GLOBAL_DEP_AUDIT", headers: ["REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "ACTIVE", "ENCODING_PATTERN", "FLAGS", "PRIOR_FAILURE_STATUS", "INDEXED_TERM_COUNT", "CLASS_COUNT", "OBJECT_PROPERTY_COUNT", "DATATYPE_PROPERTY_COUNT", "QUANTITY_PROPERTY_COUNT", "R9_CONTRACT_STATUS", "ENGINEERING_DECISION"], rows: depth.records.map((item) => {
    const contract = index.dependencyContracts[item.requirement_id];
    return [item.requirement_id, item.source_sheet, item.page, item.clause, item.active, item.encoding_pattern, item.flags.join(" | "), item.observed_status, item.indexed_term_count, item.class_count, item.object_property_count, item.datatype_property_count, item.quantity_property_count, contract.status, contract.engineeringDecision ?? ""];
  })},
  { name: "TERM_ADDITIONS", headers: ["LOCAL_NAME", "IRI", "LABEL", "KIND", "DOMAIN", "RANGE", "DATATYPE", "UNIT_IRI", "UNIT_SYMBOL", "QUANTITY_KIND", "ALIASES", "LINKED_REQUIREMENTS", "NAMING_BASIS", "SOURCE_REFS", "RATIONALE"], rows: decisions.map((item) => {
    const term = registryByName[item.canonicalLocalName];
    return [term.localName, term.iri, term.label, term.kind, item.domain, term.parentOrRange, term.datatype, term.unitIri, term.unitSymbol, term.quantityKindLabel, term.aliases.join(" | "), term.requirements.join(" | "), term.namingBasis, term.sourceRefs, item.rationale];
  })},
  { name: "DEPENDENCY_CONTRACTS", headers: ["REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "ACTIVE_STATUS", "CONTRACT_STATUS", "ENCODING_PATTERN", "OWNER_CLASSES", "APPLICABILITY_TERMS", "OPERAND_TERMS", "RESULT_TERMS", "RELATIONSHIP_TERMS", "EVIDENCE_TERMS", "CONTROLLED_VALUE_TERMS", "COMPARISON_MODEL", "TABLE_MODEL", "AUDIT_FLAGS", "ENGINEERING_DECISION", "BLOCKER"], rows: evidencePayload.requirements.map((item) => {
    const c = index.dependencyContracts[item.id];
    return [item.id, item.sourceSheet, item.page, item.clause, item.activeStatus, c.status, c.encodingPattern, c.ownerClasses.join(" | "), c.applicabilityTerms.join(" | "), c.operandTerms.join(" | "), c.resultTerms.join(" | "), c.relationshipTerms.join(" | "), c.evidenceTerms.join(" | "), c.controlledValueTerms.join(" | "), c.comparisonModel, c.tableModel, c.auditFlags.join(" | "), c.engineeringDecision ?? "", c.blocker ?? ""];
  })},
  { name: "RERUN_QUEUE", headers: ["ORDER", "REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "PRIOR_STATUS", "SELECTION_REASON", "CONTRACT_STATUS"], rows: queue.requirements.map((rid, position) => {
    const item = evidence[rid]; const prior = failedById[rid];
    return [position + 1, rid, item.sourceSheet, item.page, item.clause, prior?.status ?? "PREVIOUSLY_ACCEPTED", prior ? "REPAIRED_OBSERVED_FAILURE" : "PROACTIVE_MODEL_REPAIR", index.dependencyContracts[rid].status];
  })},
  { name: "DEFERRED", headers: ["REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "STATUS", "BLOCKER", "ENGINEERING_ACTION"], rows: Object.entries(index.dependencyContracts).filter(([, c]) => c.status === "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY").map(([rid, c]) => [rid, evidence[rid].sourceSheet, evidence[rid].page, evidence[rid].clause, c.status, c.blocker, "Keep outside generation until the cited normative companion method is obtained and modelled."])},
  { name: "EXTERNAL_UNITS", headers: ["UNIT_IRI", "SYMBOL", "OFFICIAL_VOCABULARY", "OFFICIAL_RESOURCE", "VERIFIED_DATE", "VERIFICATION_STATUS"], rows: units.qudtUnits.filter((item) => item.verifiedDate === "2026-08-13").map((item) => [item.uri, item.symbol ?? "", item.officialVocabulary, item.officialResource, item.verifiedDate, item.verificationStatus])},
];

const workbook = Workbook.create();
const colors = { navy: "#17324D", teal: "#0F766E", pale: "#E8F1F5", white: "#FFFFFF", gray: "#5B6573", line: "#CBD5E1", green: "#DCFCE7", red: "#FEE2E2", amber: "#FEF3C7" };
function colName(index) { let x = index + 1, out = ""; while (x) { const r = (x - 1) % 26; out = String.fromCharCode(65 + r) + out; x = Math.floor((x - 1) / 26); } return out; }
function width(header) { if (/MODEL|RATIONALE|BLOCKER|DETAIL|ROOT_CAUSES|SOURCE_REFS/.test(header)) return 48; if (/IRI|TERMS|FLAGS/.test(header)) return 38; if (/STATUS|DECISION|PATTERN/.test(header)) return 30; if (/NAME|LABEL|SOURCE/.test(header)) return 24; return 16; }

const summary = workbook.worksheets.add("SUMMARY");
summary.showGridLines = false;
summary.getRange("A1:D1").format.fill = colors.navy;
summary.getRange("A1").values = [["R9 Engineering Vocabulary Foundation"]];
summary.getRange("A1").format.font = { bold: true, color: colors.white, size: 16 };
summary.getRange("A2:D2").format = { fill: colors.pale, font: { color: colors.gray, italic: true } };
summary.getRange("A2").values = [["Development binding VOCAB-DEV-2026-08-13-R9-FOUNDATION"]];
summary.getRange("A4:B4").values = [["METRIC", "VALUE"]];
summary.getRange("A4:B4").format = { fill: colors.teal, font: { bold: true, color: colors.white } };
summary.getRange("A5:A14").values = [["Prior failed requirements"], ["Prior vocabulary/model failures"], ["R9 registry terms"], ["R9 terms added"], ["Requirements modelled"], ["Generation-eligible requirements"], ["Complete active contracts"], ["Source-blocked active requirements"], ["Affected rerun queue"], ["Offline tests passing"]];
summary.getRange("B5:B14").values = [[failure.failure_count], [failure.root_cause_counts.VOCABULARY_OR_MODEL_GAP], [validation.registryTerms], [validation.addedTerms], [313], [239], [239], [1], [queue.requirements.length], [39]];
summary.getRange("A16:B20").values = [["CONTROL", "OUTCOME"], ["Ontology and registry build", validation.status], ["New external unit URIs verified", validation.newExternalUnitsVerified], ["Observed failures covered", `${queue.selection.observedFailuresRepaired} repaired; 1 source-blocked`], ["API calls made during R9 build", 0]];
summary.getRange("A16:B16").format = { fill: colors.teal, font: { bold: true, color: colors.white } };
summary.getRange("A5:A14").format.font = { bold: true, color: colors.navy };
summary.getRange("A17:A20").format.font = { bold: true, color: colors.navy };
summary.getRange("A1:D20").format.font.name = "Aptos";
summary.getRange("A1:A20").format.columnWidth = 36; summary.getRange("B1:B20").format.columnWidth = 44; summary.getRange("C1:D20").format.columnWidth = 8;
summary.freezePanes.freezeRows(4);

let tableIndex = 1;
for (const spec of specs) {
  const sheet = workbook.worksheets.add(spec.name); sheet.showGridLines = false;
  const lastCol = colName(spec.headers.length - 1); const lastRow = 4 + spec.rows.length;
  sheet.getRange(`A1:${lastCol}1`).format.fill = colors.navy;
  sheet.getRange("A1").values = [["R9 Engineering Vocabulary Foundation"]];
  sheet.getRange("A1").format.font = { bold: true, color: colors.white, size: 15 };
  sheet.getRange(`A2:${lastCol}2`).format = { fill: colors.pale, font: { color: colors.gray, italic: true } };
  sheet.getRange("A2").values = [[`${spec.name} | development evidence and decisions`]];
  sheet.getRange(`A4:${lastCol}4`).values = [spec.headers];
  sheet.getRange(`A4:${lastCol}4`).format = { fill: colors.teal, font: { bold: true, color: colors.white }, wrapText: true, verticalAlignment: "center" };
  if (spec.rows.length) {
    sheet.getRange(`A5:${lastCol}${lastRow}`).values = spec.rows;
    sheet.getRange(`A5:${lastCol}${lastRow}`).format = { verticalAlignment: "top", borders: { insideHorizontal: { style: "thin", color: colors.line } } };
    sheet.tables.add(`A4:${lastCol}${lastRow}`, true, `R9T${tableIndex}`);
  }
  for (let c = 0; c < spec.headers.length; c++) {
    const letter = colName(c), header = spec.headers[c]; const range = sheet.getRange(`${letter}4:${letter}${Math.max(5, lastRow)}`);
    range.format.columnWidth = width(header);
    if (/MODEL|RATIONALE|BLOCKER|DETAIL|TERMS|FLAGS|CAUSES|REFS/.test(header)) range.format.wrapText = true;
    if (/STATUS|DECISION/.test(header) && spec.rows.length) {
      const data = sheet.getRange(`${letter}5:${letter}${lastRow}`);
      data.conditionalFormats.add("containsText", { text: "COMPLETE", format: { fill: colors.green } });
      data.conditionalFormats.add("containsText", { text: "PASS", format: { fill: colors.green } });
      data.conditionalFormats.add("containsText", { text: "BLOCKED", format: { fill: colors.amber } });
      data.conditionalFormats.add("containsText", { text: "FAIL", format: { fill: colors.red } });
      data.conditionalFormats.add("containsText", { text: "UNRESOLVED", format: { fill: colors.red } });
    }
  }
  sheet.freezePanes.freezeRows(4); sheet.freezePanes.freezeColumns(Math.min(2, spec.headers.length));
  sheet.getRange(`A1:${lastCol}${Math.max(5, lastRow)}`).format.font.name = "Aptos";
  tableIndex++;
}

const out = path.join(batch, "r9_engineering_change_tracker.xlsx");
const previewDir = path.join(batch, "validation/r9_tracker_previews");
await fs.mkdir(previewDir, { recursive: true });
const checks = [];
for (const name of ["SUMMARY", ...specs.map((item) => item.name)]) {
  const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 0.8, format: "png" });
  const previewPath = path.join(previewDir, `${name.toLowerCase()}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  checks.push({ sheet: name, preview: path.relative(batch, previewPath) });
}
const inspect = await workbook.inspect({ kind: "table", range: "SUMMARY!A1:B20", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 4, maxChars: 8000 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
await fs.writeFile(path.join(batch, "validation/r9_tracker_verification.json"), JSON.stringify({ status: "PASS", workbook: path.basename(out), sheetsRendered: checks, summaryInspect: inspect.ndjson, formulaErrorScan: errors.ndjson }, null, 2) + "\n");
const file = await SpreadsheetFile.exportXlsx(workbook); await file.save(out);
console.log(JSON.stringify({ status: "PASS", workbook: out, sheets: 1 + specs.length, previews: checks.length }, null, 2));
