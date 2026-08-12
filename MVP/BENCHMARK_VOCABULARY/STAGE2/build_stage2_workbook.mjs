import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const stage2 = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const evidence = JSON.parse(await fs.readFile(path.join(stage2, "evidence/stage1_approved.json"), "utf8"));
const manifest = JSON.parse(await fs.readFile(path.join(stage2, "stage2_manifest.json"), "utf8"));
const terms = JSON.parse(await fs.readFile(path.join(stage2, "registry/term_registry.json"), "utf8"));
const refinements = JSON.parse(await fs.readFile(path.join(stage2, "registry/naming_refinements.json"), "utf8"));
const retired = JSON.parse(await fs.readFile(path.join(stage2, "registry/retired_stage1_candidates.json"), "utf8"));
const external = JSON.parse(await fs.readFile(path.join(stage2, "evidence/external_uri_verification.json"), "utf8"));
const validation = JSON.parse(await fs.readFile(path.join(stage2, "validation/validation_report.json"), "utf8"));
const profileNames = ["master", "traficom", "iacs_ur_i2", "imo_polar_code", "imo_amend_2026", "direct_deterministic", "evidence_and_deferred"];
const profiles = Object.fromEntries(await Promise.all(profileNames.map(async name => [name, JSON.parse(await fs.readFile(path.join(stage2, `profiles/${name}.json`), "utf8"))])));

const outputPath = path.join(stage2, "benchmark_vocabulary_stage2.xlsx");
const qaDir = path.join(stage2, "qa_workbook");
await fs.mkdir(qaDir, { recursive: true });

const wb = Workbook.create();
const navy = "#17324D";
const blue = "#2F6690";
const pale = "#EAF2F8";
const green = "#D1E7DD";
const amber = "#FFF3CD";
const red = "#F8D7DA";

function colName(n) {
  let s = "";
  for (let x = n + 1; x > 0; x = Math.floor((x - 1) / 26)) s = String.fromCharCode(65 + ((x - 1) % 26)) + s;
  return s;
}

function writeMatrix(sheet, row, col, matrix) {
  if (!matrix.length || !matrix[0].length) return;
  sheet.getRangeByIndexes(row, col, matrix.length, matrix[0].length).values = matrix;
}

function addDataSheet(name, headers, rows, widths = {}) {
  const sheet = wb.worksheets.add(name);
  writeMatrix(sheet, 0, 0, [headers, ...rows]);
  const lastCol = colName(headers.length - 1);
  const lastRow = rows.length + 1;
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(Math.min(3, headers.length));
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 10, name: "Aptos" },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 38,
  };
  const used = sheet.getRange(`A1:${lastCol}${lastRow}`);
  used.format.font = { name: "Aptos", size: 9, color: "#172B4D" };
  used.format.verticalAlignment = "top";
  sheet.getRange(`A1:${lastCol}1`).format = {
    fill: navy,
    font: { bold: true, color: "#FFFFFF", size: 10, name: "Aptos" },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 38,
  };
  if (rows.length) {
    sheet.getRange(`A2:${lastCol}${lastRow}`).format.wrapText = true;
    sheet.getRange(`A2:${lastCol}${lastRow}`).format.borders = {
      insideHorizontal: { style: "thin", color: "#E6EAF0" },
      bottom: { style: "thin", color: "#E6EAF0" },
    };
    const table = sheet.tables.add(`A1:${lastCol}${lastRow}`, true, `${name.replace(/[^A-Za-z0-9]/g, "")}Table`);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
  for (let i = 0; i < headers.length; i++) sheet.getRange(`${colName(i)}:${colName(i)}`).format.columnWidth = widths[i] ?? 18;
  return sheet;
}

const readme = wb.worksheets.add("README");
readme.showGridLines = false;
readme.getRange("A1:H1").merge();
readme.getRange("A1").values = [["NLTL Benchmark Controlled Vocabulary - Stage 2"]];
readme.getRange("A1:H1").format = { fill: navy, font: { bold: true, color: "#FFFFFF", size: 18, name: "Aptos Display" }, rowHeight: 36 };
readme.getRange("A3:B15").values = [
  ["Status", "COMPLETE - validation passed"],
  ["Version", manifest.version],
  ["Generated", manifest.generatedDate],
  ["Stage 1 lock", manifest.stage1LockId],
  ["Locked requirements", manifest.requirements],
  ["Stage 1 candidate lineages", manifest.stage1CandidateTerms],
  ["Canonical Stage 2 terms", manifest.terms],
  ["Classes", manifest.termKinds.Class],
  ["Datatype properties", manifest.termKinds.DatatypeProperty],
  ["Object properties", manifest.termKinds.ObjectProperty],
  ["Quantity properties", manifest.termKinds.QuantityProperty],
  ["Validation checks passed", validation.checksPassed],
  ["Provisional namespace", manifest.provisionalVocabularyBase],
];
readme.getRange("A3:A15").format = { fill: pale, font: { bold: true, color: navy } };
readme.getRange("A3:B15").format.borders = { preset: "outside", style: "thin", color: "#AAB7C4" };
readme.getRange("A17:H17").merge();
readme.getRange("A17").values = [["Scope boundary"]];
readme.getRange("A17:H17").format = { fill: blue, font: { bold: true, color: "#FFFFFF", size: 12 } };
readme.getRange("A18:H23").values = [
  ["Purpose", "One controlled master vocabulary with canonical names, URIs, value structures, units, datatypes, mappings, and source/profile allow-lists.", null, null, null, null, null, null],
  ["Excluded logic", "No regulatory thresholds, formulas, applicability outcomes, expected pass/fail labels, or requirement-level cardinalities are included. The future benchmark pipeline generates requirement-specific SHACL from this controlled input contract.", null, null, null, null, null, null],
  ["Naming", "ASCII lowerCamelCase; engineering subject + characteristic + qualifier; unit-free local names; original notation retained as aliases.", null, null, null, null, null, null],
  ["Quantity pattern", "Entity -> canonical property -> QUDT QuantityValue with exactly one decimal numericValue and one unit IRI.", null, null, null, null, null, null],
  ["Profiles", "All source and activation profiles are allow-lists over the same master namespace; they are not separate schemas.", null, null, null, null, null, null],
  ["Publication", "The w3id base is provisional and ISO 19848 normative text remains unavailable; neither blocks local benchmark construction.", null, null, null, null, null, null],
];
readme.getRange("A18:A23").format.font = { bold: true, color: navy };
readme.getRange("B18:H23").merge(true);
readme.getRange("A18:H23").format = { wrapText: true, verticalAlignment: "top" };
readme.getRange("A25:H25").merge();
readme.getRange("A25").values = [["Workbook guide"]];
readme.getRange("A25:H25").format = { fill: blue, font: { bold: true, color: "#FFFFFF", size: 12 } };
const guide = [
  ["MASTER_TERMS", "One row per canonical term with lineage, role, range, unit, naming, evidence, and mapping decisions."],
  ["PROFILE_SUMMARY", "Master, source, and activation profile counts and boundaries."],
  ["PROFILE_MEMBERSHIP", "Term-level allow-list membership for every profile."],
  ["REQUIREMENT_PROFILE", "All 313 requirements linked to their Stage 2 canonical terms and profiles."],
  ["NODE_PATTERNS", "Canonical RDF/SHACL node and value patterns."],
  ["CONTROLLED_VALUES", "Regulation-defined classes/categories plus evidence/compliance lifecycle values."],
  ["NAMING_REFINEMENTS", "Stage 1 to Stage 2 name refinements and the exact semantic merge."],
  ["RETIRED_CANDIDATE", "The rejected multi-dimension generic term and requirement-specific redirects."],
  ["EXTERNAL_URI_REGISTER", "Verified QUDT and W3C namespace evidence."],
  ["VALIDATION", "All automated validation checks and details."],
  ["DECISIONS_LIMITATIONS", "Adopted engineering decisions and non-blocking publication limitations."],
  ["SOURCE_LINEAGE", "Read-only Stage 1 source inventory carried forward for provenance."],
];
writeMatrix(readme, 25, 0, guide);
readme.getRange("A26:A37").format = { fill: pale, font: { bold: true, color: navy } };
readme.getRange("A26:B37").format.wrapText = true;
readme.getRange("A:A").format.columnWidth = 34;
readme.getRange("B:B").format.columnWidth = 95;
readme.freezePanes.freezeRows(1);

const termHeaders = ["Source_Concept_IDs", "Stage1_Local_Names", "Canonical_Local_Name", "Canonical_URI", "Preferred_Label", "Kind", "Module", "Parent_or_Range", "Datatype", "Unit_Symbol", "Unit_URI", "Quantity_Kind", "Unit_Decision", "Role_Decision", "Aliases", "Requirement_IDs", "Source_Clause_Page", "Naming_Basis", "Naming_Rule", "Name_QA", "Confidence", "Haitham_URI", "Mapping_Status", "Evidence_Excerpt", "Normalized_Definition"];
const termRows = terms.map(t => [t.sourceConceptIds.join("; "), t.stage1LocalNames.join("; "), t.localName, t.iri, t.label, t.kind, t.module, t.parentOrRange, t.datatype, t.unitSymbol, t.unitIri, t.quantityKindLabel, t.unitDecisionStatus, t.roleDecision, t.aliases.join("; "), t.requirements.join("; "), t.sourceRefs, t.namingBasis, t.namingRule, t.nameQaStatus, t.confidence, t.haithamUri, t.mappingStatus, t.evidenceExcerpt, t.normalizedDefinition]);
const master = addDataSheet("MASTER_TERMS", termHeaders, termRows, {0:22,1:36,2:48,3:72,4:40,5:20,6:16,7:55,8:20,9:14,10:48,11:28,12:70,13:60,14:48,15:42,16:58,17:45,18:65,19:38,20:12,21:55,22:42,23:70,24:70});
master.getRange(`F2:F${termRows.length + 1}`).conditionalFormats.add("containsText", { text: "Quantity", format: { fill: green, font: { color: "#0F5132" } } });
master.getRange(`M2:M${termRows.length + 1}`).conditionalFormats.add("containsText", { text: "no unsupported", format: { fill: amber, font: { color: "#664D03" } } });

const profileSummaryRows = profileNames.map(name => {
  const p = profiles[name];
  return [name, p.profileId, p.title, p.requirementIds.length, p.termCount, p.activationBoundary, p.masterVocabulary, p.unitPolicy, p.containsRequirementLogic ? "Yes" : "No"];
});
addDataSheet("PROFILE_SUMMARY", ["Profile", "Profile_URI", "Title", "Requirement_Count", "Term_Count", "Activation_Boundary", "Master_Vocabulary", "Unit_Policy", "Contains_Requirement_Logic"], profileSummaryRows, {0:24,1:65,2:38,3:18,4:14,5:70,6:60,7:90,8:24});

const allowed = Object.fromEntries(profileNames.map(name => [name, new Set([...profiles[name].allowedClasses, ...profiles[name].allowedProperties])]));
const membershipRows = terms.map(t => [t.localName, t.iri, t.kind, t.module, ...profileNames.map(name => allowed[name].has(t.iri) ? "Yes" : "No")]);
addDataSheet("PROFILE_MEMBERSHIP", ["Canonical_Local_Name", "Canonical_URI", "Kind", "Module", ...profileNames], membershipRows, {0:48,1:72,2:20,3:16,4:12,5:12,6:14,7:18,8:18,9:22,10:22});

const termByConcept = new Map(terms.flatMap(t => t.sourceConceptIds.map(id => [id, t])));
const reqProfileMembership = Object.fromEntries(profileNames.map(name => [name, new Set(profiles[name].requirementIds)]));
const requirementRows = evidence.requirements.map(r => {
  const cids = String(r.conceptIds || "").split(";").map(x => x.trim()).filter(Boolean);
  const canonicalTerms = [...new Set(cids.map(cid => termByConcept.get(cid)?.localName).filter(Boolean))].sort();
  const reqProfiles = profileNames.filter(name => reqProfileMembership[name].has(r.id));
  return [r.id, r.sourceSheet, r.source, r.edition, r.page, r.clause, r.category, r.activeStatus, canonicalTerms.join("; "), reqProfiles.join("; "), r.coverageStatus, r.codability, r.encodingPattern, r.figureDependent, r.sourceText];
});
addDataSheet("REQUIREMENT_PROFILE", ["Requirement_ID", "Source_Sheet", "Source", "Edition", "PDF_Page", "Clause", "Verification_Category", "Activation_Status", "Canonical_Stage2_Terms", "Profiles", "Stage1_Coverage_Status", "SHACL_Codability", "Encoding_Pattern", "Figure_Dependent", "Verified_Source_Text"], requirementRows, {0:15,1:20,2:36,3:28,4:12,5:18,6:22,7:46,8:70,9:45,10:30,11:18,12:35,13:16,14:80});

const patternRows = [
  ["Quantity value", "Entity -> canonical quantity property -> qudt:QuantityValue", "qudt:numericValue exactly 1 xsd:decimal; qudt:unit exactly 1 IRI", "Structural QA only; the pipeline generates regulatory SHACL"],
  ["Typed scalar", "Entity -> canonical datatype property -> literal", "Explicit xsd:boolean, xsd:integer, xsd:date, xsd:dateTime, or xsd:string", "No inferred datatype"],
  ["Controlled value", "Entity -> canonical object property -> controlled value IRI", "Ice class, Polar Class, polar ship category, evidence state, compliance state", "Avoid free-text variants"],
  ["Observation/history", "Entity -> nltl:hasObservation -> sosa:Observation", "Feature of interest, observed property, result time, and simple/node result", "Use for time-indexed evidence"],
  ["Document/test evidence", "Entity -> nltl:hasEvidence -> nltl:evidenceArtifact", "dcterms:source required; lifecycle/provenance represented on the node", "Do not reduce approvals to an unqualified boolean"],
  ["Source profile", "Profile -> allow-list of master class/property URIs", "No independent namespace and containsRequirementLogic=false", "Prevents source-specific schema drift"],
];
addDataSheet("NODE_PATTERNS", ["Pattern", "Canonical_Graph_Path", "Schema_Only_Constraint", "Boundary"], patternRows, {0:26,1:68,2:78,3:58});

const controlledRows = [];
for (const [scheme, values] of Object.entries({
  "Finnish-Swedish ice class": [["iceClassIaSuper","IA Super"],["iceClassIa","IA"],["iceClassIb","IB"],["iceClassIc","IC"],["iceClassIi","II"],["iceClassIii","III"]],
  "IACS Polar Class": Array.from({length:7}, (_,i) => [`polarClassPc${i+1}`, `PC${i+1}`]),
  "IMO polar ship category": [["polarShipCategoryA","Category A"],["polarShipCategoryB","Category B"],["polarShipCategoryC","Category C"]],
  "Evidence lifecycle": ["Draft","Submitted","UnderReview","Approved","Rejected","Expired","Revoked"].map(x => [`evidenceState${x}`, x]),
  "Compliance state": ["Compliant","NonCompliant","NotApplicable","Unknown"].map(x => [`complianceState${x}`, x]),
})) for (const [local, label] of values) controlledRows.push([scheme, local, `${manifest.provisionalVocabularyBase}${local}`, label]);
addDataSheet("CONTROLLED_VALUES", ["Scheme", "Local_Name", "IRI", "Preferred_Label"], controlledRows, {0:30,1:40,2:75,3:28});

addDataSheet("NAMING_REFINEMENTS", ["Stage1_Local_Name", "Stage2_Local_Name", "Action", "Reason"], refinements.map(x => [x.stage1LocalName, x.stage2LocalName, x.action, x.reason]), {0:50,1:62,2:34,3:90});

const retiredRows = [];
for (const [cid, item] of Object.entries(retired)) for (const [rid, redirect] of Object.entries(item.requirementRedirects)) retiredRows.push([cid, item.stage1LocalName, item.reason, rid, redirect, `${manifest.provisionalVocabularyBase}${redirect}`]);
addDataSheet("RETIRED_CANDIDATE", ["Stage1_Concept_ID", "Stage1_Local_Name", "Retirement_Reason", "Requirement_ID", "Redirect_Canonical_Term", "Redirect_URI"], retiredRows, {0:20,1:34,2:95,3:16,4:62,5:80});

const externalRows = external.qudtUnits.map(x => ["QUDT unit", x.uri, x.officialResource, x.officialVocabularyIndex, x.verifiedDate, x.verificationStatus]);
for (const uri of external.w3cNamespaces) externalRows.push(["W3C namespace", uri, uri, "", manifest.generatedDate, "Stable W3C namespace used by the benchmark"]);
addDataSheet("EXTERNAL_URI_REGISTER", ["Type", "URI", "Direct_Resource", "Vocabulary_Index", "Verified_Date", "Status"], externalRows, {0:22,1:62,2:72,3:72,4:16,5:70});

addDataSheet("VALIDATION", ["Check", "Status", "Detail"], validation.checks.map(x => [x.check, x.status, typeof x.detail === "string" ? x.detail : JSON.stringify(x.detail)]), {0:55,1:14,2:100});

const decisionRows = [
  ["DEC-S2-01", "Adopted", "Master namespace", manifest.provisionalVocabularyBase, "One internally modular vocabulary; source profiles are allow-lists."],
  ["DEC-S2-02", "Adopted", "Naming", "ASCII lowerCamelCase and unit-free identifiers", "Original notation remains alias/provenance."],
  ["DEC-S2-03", "Adopted", "Quantity model", "QUDT QuantityValue", "One numeric value and one unit IRI per quantity node."],
  ["DEC-S2-04", "Adopted", "Time/history", "SOSA Observation", "Separates time-indexed observations from static design facts."],
  ["DEC-S2-05", "Adopted", "Evidence", "Provenance-bearing artifact nodes", "Supports documents, tests, certificates, approvals, validity, and lifecycle."],
  ["DEC-S2-06", "Adopted", "Legacy compatibility", "SKOS exactMatch only for 22 verified Haitham URIs", "No unsafe OWL equivalence across different node models."],
  ["DEC-S2-07", "Adopted", "Generic fallback", "Retire tableFallbackValue", "It mixed thrust, rotational speed, and torque."],
  ["DEC-S2-08", "Adopted", "Viscosity", "Case-declared kind/unit must match across min/observation/max", "The source does not distinguish dynamic from kinematic viscosity."],
  ["DEC-S2-09", "Adopted", "Pipeline boundary", "This workbook is the controlled input contract; the future pipeline generates requirement-specific SHACL", "The vocabulary fixes names, URIs, types, units, and node patterns without embedding regulatory answer logic."],
  ["LIM-S2-01", "Non-blocking", "Publication namespace", "w3id redirect not registered", "Register or replace before public release."],
  ["LIM-S2-02", "Non-blocking", "ISO 19848", "Normative text unavailable", "No ISO-specific definition or identifier is claimed."],
];
addDataSheet("DECISIONS_LIMITATIONS", ["Item_ID", "Status", "Topic", "Decision_or_Limitation", "Engineering_Rationale_or_Treatment"], decisionRows, {0:16,1:18,2:30,3:72,4:90});

const sourceRows = evidence.manifest.map(x => [x.sourceId, x.path, x.filename, x.role, x.versionDate, x.pageCount, x.sha256, x.status, x.notes]);
addDataSheet("SOURCE_LINEAGE", ["Source_ID", "Exact_Path", "Filename", "Content_Role", "Version_Date", "Page_Count", "SHA256", "Status", "Notes"], sourceRows, {0:12,1:70,2:48,3:36,4:32,5:12,6:68,7:30,8:70});

const inspections = [];
for (const [sheetName, range] of [["README","A1:H37"],["MASTER_TERMS","A1:M16"],["MASTER_TERMS","N1:Y16"],["PROFILE_SUMMARY","A1:I9"],["PROFILE_MEMBERSHIP","A1:K16"],["REQUIREMENT_PROFILE","A1:O12"],["NODE_PATTERNS","A1:D8"],["CONTROLLED_VALUES","A1:D30"],["NAMING_REFINEMENTS","A1:D13"],["RETIRED_CANDIDATE","A1:F5"],["EXTERNAL_URI_REGISTER","A1:F34"],["VALIDATION","A1:C43"],["DECISIONS_LIMITATIONS","A1:E13"],["SOURCE_LINEAGE","A1:I21"]]) {
  inspections.push((await wb.inspect({ kind: "table", range: `${sheetName}!${range}`, include: "values,formulas", tableMaxRows: 40, tableMaxCols: 25, maxChars: 12000 })).ndjson);
}
inspections.push((await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan", maxChars: 4000 })).ndjson);
await fs.writeFile(path.join(qaDir, "workbook_inspection.ndjson"), inspections.join("\n"), "utf8");

const renderSpecs = [["README","A1:H37"],["MASTER_TERMS","A1:M18"],["MASTER_TERMS","N1:Y18"],["PROFILE_SUMMARY","A1:I9"],["PROFILE_MEMBERSHIP","A1:K18"],["REQUIREMENT_PROFILE","A1:H16"],["REQUIREMENT_PROFILE","I1:O16"],["NODE_PATTERNS","A1:D8"],["CONTROLLED_VALUES","A1:D30"],["NAMING_REFINEMENTS","A1:D13"],["RETIRED_CANDIDATE","A1:F5"],["EXTERNAL_URI_REGISTER","A1:F34"],["VALIDATION","A1:C43"],["DECISIONS_LIMITATIONS","A1:E13"],["SOURCE_LINEAGE","A1:I21"]];
for (let i = 0; i < renderSpecs.length; i++) {
  const [sheetName, range] = renderSpecs[i];
  const blob = await wb.render({ sheetName, range, scale: 1.15, format: "png" });
  await fs.writeFile(path.join(qaDir, `${String(i + 1).padStart(2, "0")}_${sheetName}_${range.replaceAll(":", "-")}.png`), new Uint8Array(await blob.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const postExport = [];
postExport.push((await saved.inspect({ kind: "sheet", include: "id,name", maxChars: 8000 })).ndjson);
postExport.push((await saved.inspect({ kind: "table", range: "README!A1:B15", include: "values,formulas", tableMaxRows: 15, tableMaxCols: 2, maxChars: 5000 })).ndjson);
postExport.push((await saved.inspect({ kind: "table", range: "MASTER_TERMS!A1:M12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 13, maxChars: 8000 })).ndjson);
postExport.push((await saved.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "post-export formula error scan", maxChars: 4000 })).ndjson);
await fs.writeFile(path.join(qaDir, "post_export_inspection.ndjson"), postExport.join("\n"), "utf8");
console.log(JSON.stringify({ outputPath, sheets: 13, terms: terms.length, requirements: requirementRows.length, renders: renderSpecs.length }, null, 2));
