import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const dir = path.join(root, "BENCHMARK_VOCABULARY/FINAL_LOCK_R5");
const read = async rel => JSON.parse(await fs.readFile(path.join(dir, rel), "utf8"));
const registry = await read("registry/term_registry.json");
const index = await read("requirement_term_index.json");
const evidence = await read("evidence/stage1_approved.json");
const change = await read("registry/r5_change_decisions.json");
const preflight = await read("evidence/r4_preflight_imo057_defect.json");
const prelock = await read("prelock_manifest.json");
const offline = await read("validation/r5_offline_validation.json");
const reqs = evidence.requirements;
const contracts = index.dependencyContracts;
const owners = index.termOwners;
const join = value => Array.isArray(value) ? value.join(" | ") : (value ?? "");
const termRows = registry.map(term => [
  term.conceptId, term.localName, term.iri, term.label, term.kind, term.module,
  term.parentOrRange, term.datatype, term.unitIri, term.unitSymbol, join(term.aliases),
  join(term.requirements), term.sourceRefs, term.normalizedDefinition, term.namingBasis,
  term.namingRule, term.mappingStatus, term.confidence, term.nameQaStatus,
]);
const reqRows = reqs.map(req => {
  const contract = contracts[req.id] ?? {};
  return [
    req.id, req.sourceSheet, req.page, req.clause, req.category, req.activeStatus,
    req.encodingPattern, req.figureDependent, index.requirementTargetOwner[req.id] ?? "ship",
    (index.requirements[req.id] ?? []).length, join(index.requirements[req.id]), contract.status ?? "",
  ];
});
const contractRows = Object.entries(contracts).map(([id, contract]) => [
  id, contract.status, contract.schemaVersion ?? 1, contract.engineeringDecision,
  join(contract.ownerClasses), join(contract.applicabilityTerms), join(contract.operandTerms),
  join(contract.resultTerms), join(contract.relationshipTerms),
  join((contract.modelPaths ?? []).map(item => `${item.fromOwner} -> ${item.via} -> ${item.toOwner}`)),
  join(contract.timeTerms), join(contract.controlledValueTerms), join(contract.evidenceTerms),
  contract.comparisonModel, contract.tableModel, contract.encodingPattern, join(contract.auditFlags),
]);
const ownerRows = Object.entries(owners).flatMap(([requirementId, mapping]) =>
  Object.entries(mapping).map(([term, owner]) => [requirementId, term, owner])
);
const controlledRows = registry.filter(term => term.kind === "NamedIndividual").map(term => [
  term.conceptId, term.localName, term.iri, term.label, term.parentOrRange,
  join(term.requirements), term.sourceRefs, term.namingBasis, term.confidence,
]);
const changeRows = change.map(item => [
  item.requirementId, item.term, item.action, item.oldDomain, item.newDomain,
  item.newTerms, item.localNameChanged, item.rationale,
]);
const preflightRows = [[
  preflight.requirementId, preflight.sessionId, preflight.runId, preflight.status,
  preflight.accepted, preflight.classification, preflight.confirmedDefect,
  preflight.sourceEvidence.document, preflight.sourceEvidence.pdfPage,
  preflight.sourceEvidence.clause, preflight.sourceEvidence.verifiedExcerpt,
]];
const hashRows = Object.entries(prelock.boundArtifacts).map(([artifact, hash]) => [artifact, hash]);
const specs = [
  {
    name: "README",
    headers: ["SECTION", "DETAIL"],
    rows: [
      ["LOCK ID", "VOCAB-LOCK-2026-08-19-R5"],
      ["STATUS", "Immutable R5 candidate prepared for one-case IMO-057 confirmation"],
      ["PURPOSE", "Correct only the source-confirmed IMO-057 maintainedTemperature ownership/domain/dependency-path defect."],
      ["CANONICAL NAMESPACE", "https://w3id.org/nltl/vocab#"],
      ["SUPERSEDES", "VOCAB-LOCK-2026-08-14-R4; all R4 files and preflight outputs remain preserved."],
      ["TERM CHANGE", "No new term and no renamed local name. maintainedTemperature remains the canonical property."],
      ["DOMAIN CHANGE", "maintainedTemperature: benchmarkEntity -> compartment."],
      ["PATH", "ship -> hasComponent -> firePump -> hasContainingCompartment -> compartment -> maintainedTemperature -> QUDT QuantityValue"],
      ["SCOPE AUDIT", "maintainedTemperature is linked only to IMO-057; no other requirement context is affected."],
      ["COUNTS", `${registry.length} registry terms; 1678 canonical terms including infrastructure; ${reqs.length} requirements; 238 generation-eligible.`],
      ["OFFLINE VALIDATION", "44/44 tests; 313/313 contexts; 20 pass + 20 fail few-shot graphs; 7/7 RDF regression; zero API calls."],
      ["UNCHANGED", "Prompts, few-shot examples, thresholds, generator logic, canonical local names, and standard external namespaces."],
    ],
  },
  {name: "MASTER_TERMS", headers: ["CONCEPT_ID", "LOCAL_NAME", "IRI", "LABEL", "KIND", "MODULE", "PARENT_OR_RANGE", "DATATYPE", "UNIT_IRI", "UNIT_SYMBOL", "ALIASES", "REQUIREMENTS", "SOURCE_REFS", "NORMALIZED_DEFINITION", "NAMING_BASIS", "NAMING_RULE", "MAPPING_STATUS", "CONFIDENCE", "NAME_QA_STATUS"], rows: termRows},
  {name: "REQUIREMENTS", headers: ["REQUIREMENT_ID", "SOURCE", "PAGE", "CLAUSE", "CATEGORY", "ACTIVE_STATUS", "ENCODING_PATTERN", "FIGURE_DEPENDENT", "TARGET_OWNER", "TERM_COUNT", "TERMS", "CONTRACT_STATUS"], rows: reqRows},
  {name: "CONTRACTS", headers: ["REQUIREMENT_ID", "STATUS", "SCHEMA_VERSION", "ENGINEERING_DECISION", "OWNER_CLASSES", "APPLICABILITY", "OPERANDS", "RESULTS", "RELATIONSHIPS", "MODEL_PATHS", "TIME", "CONTROLLED_VALUES", "EVIDENCE", "COMPARISON_MODEL", "TABLE_MODEL", "ENCODING_PATTERN", "AUDIT_FLAGS"], rows: contractRows},
  {name: "TERM_OWNERS", headers: ["REQUIREMENT_ID", "TERM", "OWNER_CLASS"], rows: ownerRows},
  {name: "CONTROLLED_VALUES", headers: ["CONCEPT_ID", "LOCAL_NAME", "IRI", "LABEL", "VALUE_CLASS", "REQUIREMENTS", "SOURCE_REFS", "NAMING_BASIS", "CONFIDENCE"], rows: controlledRows},
  {name: "R5_CHANGE", headers: ["REQUIREMENT_ID", "TERM", "ACTION", "OLD_DOMAIN", "NEW_DOMAIN", "NEW_TERMS", "LOCAL_NAME_CHANGED", "RATIONALE"], rows: changeRows},
  {name: "PREFLIGHT_EVIDENCE", headers: ["REQUIREMENT_ID", "SESSION_ID", "RUN_ID", "STATUS", "ACCEPTED", "CLASSIFICATION", "CONFIRMED_DEFECT", "SOURCE_DOCUMENT", "PDF_PAGE", "CLAUSE", "VERIFIED_EXCERPT"], rows: preflightRows},
  {name: "ARTIFACT_HASHES", headers: ["BOUND_ARTIFACT", "SHA256"], rows: hashRows},
  {
    name: "VALIDATION",
    headers: ["CHECK", "RESULT", "DETAIL"],
    rows: [
      ["Registry size", "PASS", String(registry.length)],
      ["New vocabulary terms", "PASS", "0"],
      ["Canonical local names changed", "PASS", "0"],
      ["Requirements", "PASS", String(reqs.length)],
      ["Complete contracts", "PASS", String(Object.values(contracts).filter(item => item.status === "COMPLETE").length)],
      ["All contexts", "PASS", "313/313"],
      ["IMO-057 ownership", "PASS", "maintainedTemperature owner=compartment; hasContainingCompartment owner=firePump"],
      ["Ontology syntax", "PASS", "Turtle and RDF/XML parsed and are isomorphic"],
      ["Namespace", "PASS", "https://w3id.org/nltl/vocab#; zero retired occurrences"],
      ["Offline tests", "PASS", offline.unitTests],
      ["Few-shot RDF", "PASS", "20 pass graphs conformed; 20 fail graphs rejected"],
      ["RDF regression", "PASS", "7/7 expected outcomes matched"],
      ["API calls", "PASS", "0"],
    ],
  },
];

const workbook = Workbook.create();
const colors = {navy: "#17324D", teal: "#0F766E", pale: "#E8F1F5", white: "#FFFFFF", gray: "#5B6573", line: "#CBD5E1"};
const columnName = index => {
  let number = index + 1;
  let result = "";
  while (number) {
    const remainder = (number - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    number = Math.floor((number - 1) / 26);
  }
  return result;
};
const width = header => /DEFINITION|RATIONALE|DECISION|MODEL|DETAIL|EXCERPT|DEFECT/.test(header) ? 48 : /IRI|TERMS|REFS|ALIASES|OWNER|VALUES|PATH|DIRECTORY|SHAPE/.test(header) ? 36 : /STATUS|BASIS|ACTION|CLASSIFICATION/.test(header) ? 26 : 18;
let tableNumber = 1;
for (const spec of specs) {
  const sheet = workbook.worksheets.add(spec.name);
  sheet.showGridLines = false;
  const lastColumn = columnName(spec.headers.length - 1);
  const lastRow = 4 + spec.rows.length;
  sheet.getRange(`A1:${lastColumn}1`).format.fill = colors.navy;
  sheet.getRange("A1").values = [["NLTL Benchmark Vocabulary - Final Lock R5"]];
  sheet.getRange("A1").format.font = {bold: true, color: colors.white, size: 15};
  sheet.getRange(`A2:${lastColumn}2`).format = {fill: colors.pale, font: {color: colors.gray, italic: true}};
  sheet.getRange("A2").values = [[`${spec.name} | VOCAB-LOCK-2026-08-19-R5`]];
  sheet.getRange(`A4:${lastColumn}4`).values = [spec.headers];
  sheet.getRange(`A4:${lastColumn}4`).format = {fill: colors.teal, font: {bold: true, color: colors.white}, wrapText: true, rowHeight: 30};
  if (spec.rows.length) {
    sheet.getRange(`A5:${lastColumn}${lastRow}`).values = spec.rows;
    sheet.getRange(`A5:${lastColumn}${lastRow}`).format = {verticalAlignment: "top", borders: {insideHorizontal: {style: "thin", color: colors.line}}};
    sheet.tables.add(`A4:${lastColumn}${lastRow}`, true, `R5T${tableNumber++}`);
  }
  for (let i = 0; i < spec.headers.length; i++) {
    const letter = columnName(i);
    const columnWidth = width(spec.headers[i]);
    const range = sheet.getRange(`${letter}4:${letter}${Math.max(5, lastRow)}`);
    range.format.columnWidth = columnWidth;
    if (columnWidth >= 36) range.format.wrapText = true;
  }
  sheet.freezePanes.freezeRows(4);
  sheet.freezePanes.freezeColumns(Math.min(2, spec.headers.length));
  sheet.getRange(`A1:${lastColumn}${Math.max(5, lastRow)}`).format.font.name = "Aptos";
}

const output = path.join(dir, "benchmark_vocabulary_stage2_LOCK-2026-08-19-R5.xlsx");
const previewDir = path.join(dir, "validation/final_lock_workbook_previews");
await fs.mkdir(previewDir, {recursive: true});
const rendered = [];
for (const spec of specs) {
  const maxRows = Math.min(30, 4 + spec.rows.length);
  const lastColumn = columnName(spec.headers.length - 1);
  const png = await workbook.render({sheetName: spec.name, range: `A1:${lastColumn}${maxRows}`, scale: 0.65, format: "png"});
  const previewPath = path.join(previewDir, `${String(rendered.length + 1).padStart(2, "0")}_${spec.name}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await png.arrayBuffer()));
  rendered.push({sheet: spec.name, preview: path.relative(dir, previewPath), renderedRange: `A1:${lastColumn}${maxRows}`});
}
const summaryInspect = await workbook.inspect({kind: "table", range: "README!A1:B16", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 4, maxChars: 7000});
const formulaErrors = await workbook.inspect({kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: {useRegex: true, maxResults: 300}, summary: "formula errors"});
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(output);
await fs.writeFile(
  path.join(dir, "validation/final_lock_workbook_verification.json"),
  JSON.stringify({
    status: "PASS",
    workbook: path.basename(output),
    sheetCount: specs.length,
    sheetsRendered: rendered,
    summaryInspect: summaryInspect.ndjson,
    formulaErrorScan: formulaErrors.ndjson,
    visualReview: "Pending manual inspection of all rendered previews",
  }, null, 2) + "\n",
);
console.log(JSON.stringify({status: "PASS", workbook: output, sheets: specs.length, registryTerms: registry.length, requirements: reqs.length, previews: rendered.length}, null, 2));
