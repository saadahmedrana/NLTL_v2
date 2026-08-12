import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const data = JSON.parse(await fs.readFile("/tmp/nltl_stage1/stage1_data.json", "utf8"));
const outputPath = path.join(root, "benchmark_vocabulary_stage1_naming_audited.xlsx");
const exportDir = path.join(root, "exports_naming_audited");
const qaDir = path.join(root, "qa_naming_audited");
await fs.mkdir(exportDir, { recursive: true });
await fs.mkdir(qaDir, { recursive: true });

const wb = Workbook.create();
const navy = "#17324D";
const blue = "#2F6690";
const pale = "#EAF2F8";
const amber = "#FFF3CD";
const red = "#F8D7DA";
const green = "#D1E7DD";
const grey = "#667085";

function writeMatrix(sheet, startRow, startCol, matrix) {
  if (!matrix.length || !matrix[0].length) return;
  sheet.getRangeByIndexes(startRow, startCol, matrix.length, matrix[0].length).values = matrix;
}

function colName(n) {
  let s = "";
  for (let x = n + 1; x > 0; x = Math.floor((x - 1) / 26)) s = String.fromCharCode(65 + ((x - 1) % 26)) + s;
  return s;
}

function styleDataSheet(sheet, headers, rows, widths = {}) {
  const lastCol = colName(headers.length - 1);
  const lastRow = rows.length + 1;
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(Math.min(3, headers.length));
  const header = sheet.getRange(`A1:${lastCol}1`);
  header.format.fill = navy;
  header.format.font = { bold: true, color: "#FFFFFF", size: 10 };
  header.format.wrapText = true;
  header.format.rowHeight = 36;
  const used = sheet.getRange(`A1:${lastCol}${lastRow}`);
  used.format.font = { name: "Aptos", size: 9, color: "#172B4D" };
  used.format.verticalAlignment = "top";
  sheet.getRange(`A2:${lastCol}${lastRow}`).format.wrapText = true;
  sheet.getRange(`A2:${lastCol}${lastRow}`).format.borders = {
    insideHorizontal: { style: "thin", color: "#E6EAF0" },
    bottom: { style: "thin", color: "#E6EAF0" },
  };
  for (let i = 0; i < headers.length; i++) {
    sheet.getRange(`${colName(i)}:${colName(i)}`).format.columnWidth = widths[i] ?? 16;
  }
  if (rows.length) {
    const table = sheet.tables.add(`A1:${lastCol}${lastRow}`, true, `${sheet.name.replace(/[^A-Za-z0-9]/g, "")}Table`);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
}

function addSheet(name, headers, rows, widths = {}) {
  const sheet = wb.worksheets.add(name);
  writeMatrix(sheet, 0, 0, [headers, ...rows]);
  styleDataSheet(sheet, headers, rows, widths);
  return sheet;
}

const readme = wb.worksheets.add("README");
readme.showGridLines = false;
readme.getRange("A1:H1").merge();
readme.getRange("A1").values = [["Benchmark Vocabulary - Stage 1 Naming-Audited Engineering Evidence Base"]];
readme.getRange("A1:H1").format.fill = navy;
readme.getRange("A1:H1").format.font = { bold: true, color: "#FFFFFF", size: 18 };
readme.getRange("A1:H1").format.rowHeight = 34;
readme.getRange("A3:B12").values = [
  ["Status", "NAMING-AUDITED STAGE 1 - no blocking naming issues; no RDF/JSON-LD ontology emitted yet"],
  ["Lock", data.summary.lockId],
  ["Locked requirements", null],
  ["Shortlisted concepts", null],
  ["Direct/deterministic Stage 2 candidates", null],
  ["Complex workflow deferred", null],
  ["Dynamic/history deferred", null],
  ["Physical-test evidence only", null],
  ["Haitham ship/rules triples", `${data.summary.haithamShipTriples} / ${data.summary.haithamRulesTriples}`],
  ["Current INPUTS status", "Resolved - locked R2 workbook promoted byte-identically into INPUTS"],
];
readme.getRange("B5:B10").values = [[
  data.summary.requirementCount
], [
  data.summary.conceptCount
], [
  data.summary.activationCounts["Stage 2 candidate - direct/deterministic"]
], [
  data.summary.activationCounts["Deferred - composite/evidence workflow review"]
], [
  data.summary.activationCounts["Deferred - observation/history/simulation design required"]
], [
  data.summary.activationCounts["Evidence-only - physical result not inferred by SHACL"]
]];
readme.getRange("A3:A12").format.fill = pale;
readme.getRange("A3:A12").format.font = { bold: true, color: navy };
readme.getRange("A3:B12").format.borders = { preset: "outside", style: "thin", color: "#AAB7C4" };
readme.getRange("A14:H14").merge();
readme.getRange("A14").values = [["Scope and interpretation"]];
readme.getRange("A14:H14").format.fill = blue;
readme.getRange("A14:H14").format.font = { bold: true, color: "#FFFFFF", size: 12 };
readme.getRange("A15:H21").values = [
  ["Purpose", "A controlled, reviewable evidence base for choosing one future benchmark vocabulary. This workbook does not declare final classes, properties, units, shapes, profiles, or base URIs.", null, null, null, null, null, null],
  ["Source precedence", "RELEVANT FILES -> INPUTS -> OLD FILES fallback. Main MSC.385(94) is now current in RELEVANT FILES, and the locked R2 workbook is current in INPUTS.", null, null, null, null, null, null],
  ["Regulatory wording", "Exact evidence excerpts are copied only from the reverified locked workbook or directly inspected PDFs; normalized definitions are labeled NORMALIZED.", null, null, null, null, null, null],
  ["Canonical naming decision", "Adopted: ASCII lowerCamelCase, unit-free local names. Source notation and symbols remain aliases. Unit/quantity metadata is separate.", null, null, null, null, null, null],
  ["Activation boundary", "Accepted by user: Static and Static Calculation rows are direct/deterministic candidates. Dynamic and Complex rows are deferred; Physical Test rows track evidence only.", null, null, null, null, null, null],
  ["Node/value decision", "Adopted: entity -> canonical property -> QUDT QuantityValue or typed literal; SOSA Observation for history; provenance-bearing nodes for evidence.", null, null, null, null, null, null],
  ["Review discipline", "Broken JSON-LD is excluded. Exact external mappings are accepted only when verified; otherwise consistent benchmark terms are coined with aliases and provenance.", null, null, null, null, null, null],
];
readme.getRange("A15:A21").format.font = { bold: true, color: navy };
readme.getRange("A15:H21").format.wrapText = true;
readme.getRange("A15:H21").format.verticalAlignment = "top";
readme.getRange("B15:H21").merge(true);
readme.getRange("A23:H23").merge();
readme.getRange("A23").values = [["Sheet guide"]];
readme.getRange("A23:H23").format.fill = blue;
readme.getRange("A23:H23").format.font = { bold: true, color: "#FFFFFF", size: 12 };
readme.getRange("A24:B33").values = [
  ["SOURCE_MANIFEST", "Content-verified source inventory, hashes, roles, duplicates, and missing active companions."],
  ["TERMINOLOGY_SHORTLIST", "All reviewable concept candidates, aliases, evidence, type/unit metadata, mappings, and review fields."],
  ["NAMING_AUDIT", "One row per candidate showing naming basis, authority, rule, aliases, QA result, and paper-ready defensibility."],
  ["NAMING_POLICY", "The seven deterministic naming rules applied during the audit."],
  ["REQUIREMENT_COVERAGE", "All 313 locked requirements linked to candidate concepts and activation boundaries."],
  ["NAMESPACE_COMPATIBILITY", "Exact URI, namespace, datatype/unit, and node-model differences."],
  ["DECISIONS", "Adopted naming/model decisions and their rationale."],
  ["PUBLICATION_LIMITATIONS", "Non-blocking publication actions, source limitations, and resolved controls."],
  ["UNRESOLVED", "Blocking issue register; currently records that none remain for Stage 1 naming."],
  ["exports_naming_audited", "Machine-readable CSV copies of the core and naming-audit tables."],
];
readme.getRange("A24:A33").format.fill = pale;
readme.getRange("A24:A33").format.font = { bold: true, color: navy };
readme.getRange("A24:B33").format.wrapText = true;
readme.getRange("A:A").format.columnWidth = 36;
readme.getRange("B:B").format.columnWidth = 90;
readme.freezePanes.freezeRows(1);

const manifestHeaders = ["Source_ID","Exact_Path","Filename","Content_Role","Version_Date","Page_Count","SHA256","Status","Notes"];
const manifestRows = data.manifest.map(x => [x.sourceId,x.path,x.filename,x.role,x.versionDate,x.pageCount,x.sha256,x.status,x.notes]);
addSheet("SOURCE_MANIFEST", manifestHeaders, manifestRows, {0:12,1:64,2:42,3:32,4:30,5:12,6:68,7:28,8:60});

const termHeaders = [
  "Concept_ID","Preferred_Label","Proposed_Local_Name","Source_Labels_Aliases","Exact_Evidence_Excerpt","Normalized_Definition","Role","Draft_Domain","Draft_Range","Datatype","Unit","Unit_URI","Quantity_Kind","Cardinality","Closed_World",
  "Use_Applicability","Use_Targeting","Use_Formula","Use_Comparison","Use_Relation","Use_Time_History","Use_Document_Evidence","Use_Test_Evidence","Requirement_IDs","Source_Clause_Page","Verification_Category",
  "Haitham_URI","Haitham_Mapping_Status","Rana_Thesis_URI","Rana_Mapping_Status","AnchorMap_Mapping_Text","AnchorMap_URI","AnchorMap_Status","DNV_GMOD_Mapping","DNV_GMOD_URI","DNV_Status","QUDT_W3C_Mapping","Mapping_Status","Decision_Rationale","Confidence","Human_Review_Status","Notes",
  "Naming_Basis","Naming_Authority","Naming_Rule","Name_QA_Status","Defensibility","Origin_Evidence"
];
const yn = v => v ? "Yes" : "No";
const termRows = data.concepts.map(c => [
  c.conceptId,c.label,c.localName,c.aliases,c.exactEvidence,c.normalizedDefinition,c.role,c.domain,c.range,c.datatype,c.unit,c.unitUri,c.quantityKind,c.cardinality,c.closedWorld,
  yn(c.applicability),yn(c.targeting),yn(c.formula),yn(c.comparison),yn(c.relation),yn(c.timeHistory),yn(c.documentEvidence),yn(c.testEvidence),c.requirementIds,c.sourceRefs,c.verificationCategory,
  c.haithamUri,c.haithamMappingStatus,c.ranaUri,c.ranaMappingStatus,c.anchorMapMapping,c.anchorMapUri,c.anchorMapStatus,c.dnvGmodMapping,c.dnvGmodUri,c.dnvStatus,c.qudtW3cMapping,c.mappingStatus,c.decisionRationale,c.confidence,c.humanReview,c.notes,
  c.namingBasis,c.namingAuthority,c.namingRule,c.nameQaStatus,c.defensibility,c.originEvidence
]);
const termWidths = {0:12,1:31,2:42,3:44,4:58,5:58,6:24,7:28,8:18,9:24,10:12,11:42,12:20,13:28,14:30,23:45,24:55,25:24,26:45,27:38,28:45,29:32,30:55,31:35,32:50,33:28,34:35,35:45,36:55,37:38,38:55,39:12,40:42,41:35,42:42,43:58,44:62,45:42,46:70,47:52};
const termsSheet = addSheet("TERMINOLOGY_SHORTLIST", termHeaders, termRows, termWidths);
termsSheet.getRange(`AN2:AN${termRows.length+1}`).dataValidation = { rule: { type: "list", values: ["High","Medium","Low"] } };
termsSheet.getRange(`AO2:AO${termRows.length+1}`).dataValidation = { rule: { type: "list", values: ["Naming audit passed; final semantic scope and URI activation remain Stage 2 decisions","Rejected"] } };

const namingAuditHeaders = ["Concept_ID","Proposed_Local_Name","Preferred_Label","Naming_Basis","Naming_Authority","Naming_Rule","Origin_Evidence","Source_Labels_Aliases","Name_QA_Status","Confidence","Defensibility","Requirement_IDs"];
const namingAuditRows = data.concepts.map(c => [c.conceptId,c.localName,c.label,c.namingBasis,c.namingAuthority,c.namingRule,c.originEvidence,c.aliases,c.nameQaStatus,c.confidence,c.defensibility,c.requirementIds]);
addSheet("NAMING_AUDIT", namingAuditHeaders, namingAuditRows, {0:12,1:42,2:34,3:45,4:62,5:70,6:52,7:50,8:42,9:12,10:76,11:42});

const namingPolicyHeaders = ["Rule_ID","Rule","Application","Paper_Defense"];
const namingPolicyRows = data.namingRules.map(x => [x.ruleId,x.rule,x.application,x.paperDefense]);
addSheet("NAMING_POLICY", namingPolicyHeaders, namingPolicyRows, {0:12,1:34,2:78,3:76});

const reqHeaders = ["Requirement_ID","Source_Sheet","Source","Edition","PDF_Page","Section","Clause","Verification_Category","Exact_Source_Text","Normalized_Requirement","Canonical_Variables_From_Lock","Required_Inputs_Artifacts","Linked_Concept_IDs","Coverage_Status","SHACL_Codability","Encoding_Pattern","Activation_Status","Figure_Dependent","Source_URL"];
const reqRows = data.requirements.map(r => [r.id,r.sourceSheet,r.source,r.edition,r.page,r.section,r.clause,r.category,r.sourceText,r.normalizedRequirement,r.canonicalVariables,r.requiredInputs,r.conceptIds,r.coverageStatus,r.codability,r.encodingPattern,r.activeStatus,r.figureDependent,r.sourceUrl]);
addSheet("REQUIREMENT_COVERAGE", reqHeaders, reqRows, {0:14,1:20,2:34,3:28,4:12,5:34,6:18,7:22,8:64,9:64,10:42,11:48,12:45,13:30,14:16,15:32,16:45,17:16,18:55});

const compHeaders = ["Audit_Item","Source_A","Exact_URI_or_Pattern_A","Source_B","Exact_URI_or_Pattern_B","Match_Status","Risk","Finding"];
const compRows = data.compatibility.map(x => [x.item,x.sourceA,x.exactA,x.sourceB,x.exactB,x.status,x.risk,x.finding]);
const comp = addSheet("NAMESPACE_COMPATIBILITY", compHeaders, compRows, {0:26,1:24,2:58,3:24,4:58,5:34,6:12,7:70});
comp.getRange(`G2:G${compRows.length+1}`).conditionalFormats.add("containsText", { text: "Critical", format: { fill: red, font: { bold: true, color: "#842029" } } });
comp.getRange(`G2:G${compRows.length+1}`).conditionalFormats.add("containsText", { text: "High", format: { fill: amber, font: { bold: true, color: "#664D03" } } });

const decisionHeaders = ["Decision_ID","Status","Topic","Proposed_Decision","Rationale","User_Action"];
const decisionRows = data.decisions.map(x => [x.decisionId,x.status,x.topic,x.decision,x.rationale,x.requiresUser]);
const decisions = addSheet("DECISIONS", decisionHeaders, decisionRows, {0:14,1:14,2:28,3:70,4:62,5:20});
decisions.getRange(`B2:B${decisionRows.length+1}`).dataValidation = { rule: { type: "list", values: ["Adopted","Accepted by user","Open","Proposed","Approved","Rejected","Deferred"] } };

const limitationHeaders = ["Item_ID","Category","Status","Item","Treatment"];
const limitationRows = data.publicationLimitations.map(x => [x.itemId,x.category,x.status,x.item,x.treatment]);
addSheet("PUBLICATION_LIMITATIONS", limitationHeaders, limitationRows, {0:14,1:28,2:24,3:72,4:78});

const unresolvedHeaders = ["Issue_ID","Priority","Issue","Impact","Decision_or_Input_Needed"];
const unresolvedRows = data.unresolved.map(x => [x.issueId,x.priority,x.issue,x.impact,x.needed]);
const unresolved = addSheet("UNRESOLVED", unresolvedHeaders, unresolvedRows, {0:14,1:14,2:65,3:65,4:70});
unresolved.getRange(`B2:B${unresolvedRows.length+1}`).conditionalFormats.add("containsText", { text: "Critical", format: { fill: red, font: { bold: true, color: "#842029" } } });
unresolved.getRange(`B2:B${unresolvedRows.length+1}`).conditionalFormats.add("containsText", { text: "High", format: { fill: amber, font: { bold: true, color: "#664D03" } } });

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"','""')}"` : s;
}
async function writeCsv(filename, headers, rows) {
  const text = [headers, ...rows].map(row => row.map(csvEscape).join(",")).join("\n") + "\n";
  await fs.writeFile(path.join(exportDir, filename), text, "utf8");
}
await writeCsv("source_manifest.csv", manifestHeaders, manifestRows);
await writeCsv("terminology_shortlist.csv", termHeaders, termRows);
await writeCsv("naming_audit.csv", namingAuditHeaders, namingAuditRows);
await writeCsv("naming_policy.csv", namingPolicyHeaders, namingPolicyRows);
await writeCsv("requirement_coverage.csv", reqHeaders, reqRows);
await writeCsv("namespace_compatibility.csv", compHeaders, compRows);

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);

const checks = [];
checks.push((await wb.inspect({ kind:"table", range:"README!A1:H33", include:"values,formulas", tableMaxRows:38, tableMaxCols:8, maxChars:11000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"SOURCE_MANIFEST!A1:I16", include:"values,formulas", tableMaxRows:18, tableMaxCols:9, maxChars:9000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"TERMINOLOGY_SHORTLIST!A1:J18", include:"values,formulas", tableMaxRows:18, tableMaxCols:10, maxChars:9000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"NAMING_AUDIT!A1:L18", include:"values,formulas", tableMaxRows:18, tableMaxCols:12, maxChars:12000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"NAMING_POLICY!A1:D8", include:"values,formulas", tableMaxRows:10, tableMaxCols:4, maxChars:9000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"REQUIREMENT_COVERAGE!A1:S12", include:"values,formulas", tableMaxRows:12, tableMaxCols:19, maxChars:9000 })).ndjson);
checks.push((await wb.inspect({ kind:"table", range:"NAMESPACE_COMPATIBILITY!A1:H12", include:"values,formulas", tableMaxRows:12, tableMaxCols:8, maxChars:9000 })).ndjson);
checks.push((await wb.inspect({ kind:"match", searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options:{useRegex:true,maxResults:300}, summary:"final formula error scan", maxChars:4000 })).ndjson);
await fs.writeFile(path.join(qaDir,"workbook_inspection.ndjson"), checks.join("\n"), "utf8");

const renderSpecs = [
  ["README","A1:H33"], ["SOURCE_MANIFEST","A1:I16"],
  ["TERMINOLOGY_SHORTLIST","A1:J20"], ["TERMINOLOGY_SHORTLIST","AM1:AV20"],
  ["NAMING_AUDIT","A1:F20"], ["NAMING_AUDIT","G1:L20"], ["NAMING_POLICY","A1:D8"],
  ["REQUIREMENT_COVERAGE","A1:J18"], ["REQUIREMENT_COVERAGE","K1:S18"],
  ["NAMESPACE_COMPATIBILITY","A1:H12"], ["DECISIONS","A1:F12"], ["PUBLICATION_LIMITATIONS","A1:E4"], ["UNRESOLVED","A1:E3"],
];
for (let i=0; i<renderSpecs.length; i++) {
  const [sheetName, range] = renderSpecs[i];
  const blob = await wb.render({ sheetName, range, scale: 1.25, format:"png" });
  await fs.writeFile(path.join(qaDir, `${String(i+1).padStart(2,"0")}_${sheetName}_${range.replaceAll(":","-")}.png`), new Uint8Array(await blob.arrayBuffer()));
}
console.log(JSON.stringify({outputPath,concepts:termRows.length,requirements:reqRows.length,renders:renderSpecs.length},null,2));
