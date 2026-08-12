import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const stage2 = process.env.NLTL_STAGE2_DIR
  ? path.resolve(process.env.NLTL_STAGE2_DIR)
  : path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const workbookPath = process.env.NLTL_STAGE2_WORKBOOK
  ? path.resolve(process.env.NLTL_STAGE2_WORKBOOK)
  : path.join(stage2, "benchmark_vocabulary_stage2.xlsx");
const reportStem = process.env.NLTL_STAGE2_REPORT_STEM || "workbook_verification";
const evidence = JSON.parse(await fs.readFile(path.join(stage2, "evidence/stage1_approved.json"), "utf8"));
const manifest = JSON.parse(await fs.readFile(path.join(stage2, "stage2_manifest.json"), "utf8"));
const terms = JSON.parse(await fs.readFile(path.join(stage2, "registry/term_registry.json"), "utf8"));
const refinements = JSON.parse(await fs.readFile(path.join(stage2, "registry/naming_refinements.json"), "utf8"));
const retired = JSON.parse(await fs.readFile(path.join(stage2, "registry/retired_stage1_candidates.json"), "utf8"));
const external = JSON.parse(await fs.readFile(path.join(stage2, "evidence/external_uri_verification.json"), "utf8"));
const validation = JSON.parse(await fs.readFile(path.join(stage2, "validation/validation_report.json"), "utf8"));
const profileNames = ["master", "traficom", "iacs_ur_i2", "imo_polar_code", "imo_amend_2026", "direct_deterministic", "evidence_and_deferred"];
const profiles = Object.fromEntries(await Promise.all(profileNames.map(async name => [name, JSON.parse(await fs.readFile(path.join(stage2, `profiles/${name}.json`), "utf8"))])));

const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const checks = [];

function pass(check, detail) {
  checks.push({ check, status: "PASS", detail });
}

function assert(condition, check, detail) {
  if (!condition) throw new Error(`${check}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  pass(check, detail);
}

function norm(value) {
  return value === null || value === undefined ? "" : value;
}

function compareMatrix(sheetName, expected) {
  const actual = wb.worksheets.getItem(sheetName).getRangeByIndexes(0, 0, expected.length, expected[0].length).values;
  for (let r = 0; r < expected.length; r++) {
    for (let c = 0; c < expected[r].length; c++) {
      if (norm(actual[r][c]) !== norm(expected[r][c])) {
        throw new Error(`${sheetName} mismatch at row ${r + 1}, column ${c + 1}: actual=${JSON.stringify(actual[r][c])} expected=${JSON.stringify(expected[r][c])}`);
      }
    }
  }
  pass(`${sheetName} exact data reconciliation`, `${expected.length - 1} data rows x ${expected[0].length} columns`);
}

const expectedSheets = [
  "README", "MASTER_TERMS", "PROFILE_SUMMARY", "PROFILE_MEMBERSHIP", "REQUIREMENT_PROFILE",
  "NODE_PATTERNS", "CONTROLLED_VALUES", "NAMING_REFINEMENTS", "RETIRED_CANDIDATE",
  "EXTERNAL_URI_REGISTER", "VALIDATION", "DECISIONS_LIMITATIONS",
];
if (manifest.revision === "R2") expectedSheets.push("R2_REVISIONS");
expectedSheets.push("SOURCE_LINEAGE");
const sheetInspection = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 12000 });
const actualSheets = sheetInspection.ndjson.split("\n").filter(Boolean).map(line => JSON.parse(line)).filter(x => x.kind === "sheet").map(x => x.name);
assert(JSON.stringify(actualSheets) === JSON.stringify(expectedSheets), "sheet order and completeness", actualSheets);

const readmeSummary = [
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
const actualReadme = wb.worksheets.getItem("README").getRange("A3:B15").values;
assert(JSON.stringify(actualReadme.map(r => r.map(norm))) === JSON.stringify(readmeSummary), "README control totals", readmeSummary.map(x => `${x[0]}=${x[1]}`));
const boundaryText = norm(wb.worksheets.getItem("README").getRange("B19").values[0][0]);
assert(boundaryText.includes("pipeline generates requirement-specific SHACL"), "pipeline boundary recorded in workbook", boundaryText);

const termHeaders = ["Source_Concept_IDs", "Stage1_Local_Names", "Canonical_Local_Name", "Canonical_URI", "Preferred_Label", "Kind", "Module", "Parent_or_Range", "Datatype", "Unit_Symbol", "Unit_URI", "Quantity_Kind", "Unit_Decision", "Role_Decision", "Aliases", "Requirement_IDs", "Source_Clause_Page", "Naming_Basis", "Naming_Rule", "Name_QA", "Confidence", "Haitham_URI", "Mapping_Status", "Evidence_Excerpt", "Normalized_Definition"];
const termRows = terms.map(t => [t.sourceConceptIds.join("; "), t.stage1LocalNames.join("; "), t.localName, t.iri, t.label, t.kind, t.module, t.parentOrRange, t.datatype, t.unitSymbol, t.unitIri, t.quantityKindLabel, t.unitDecisionStatus, t.roleDecision, t.aliases.join("; "), t.requirements.join("; "), t.sourceRefs, t.namingBasis, t.namingRule, t.nameQaStatus, t.confidence, t.haithamUri, t.mappingStatus, t.evidenceExcerpt, t.normalizedDefinition]);
compareMatrix("MASTER_TERMS", [termHeaders, ...termRows]);

const profileSummaryRows = profileNames.map(name => {
  const p = profiles[name];
  return [name, p.profileId, p.title, p.requirementIds.length, p.termCount, p.activationBoundary, p.masterVocabulary, p.unitPolicy, p.containsRequirementLogic ? "Yes" : "No"];
});
compareMatrix("PROFILE_SUMMARY", [["Profile", "Profile_URI", "Title", "Requirement_Count", "Term_Count", "Activation_Boundary", "Master_Vocabulary", "Unit_Policy", "Contains_Requirement_Logic"], ...profileSummaryRows]);

const allowed = Object.fromEntries(profileNames.map(name => [name, new Set([...profiles[name].allowedClasses, ...profiles[name].allowedProperties])]));
const membershipRows = terms.map(t => [t.localName, t.iri, t.kind, t.module, ...profileNames.map(name => allowed[name].has(t.iri) ? "Yes" : "No")]);
compareMatrix("PROFILE_MEMBERSHIP", [["Canonical_Local_Name", "Canonical_URI", "Kind", "Module", ...profileNames], ...membershipRows]);

const termByConcept = new Map(terms.flatMap(t => t.sourceConceptIds.map(id => [id, t])));
const requirementSets = Object.fromEntries(profileNames.map(name => [name, new Set(profiles[name].requirementIds)]));
const requirementRows = evidence.requirements.map(r => {
  const cids = String(r.conceptIds || "").split(";").map(x => x.trim()).filter(Boolean);
  const canonicalTerms = [...new Set(cids.map(cid => termByConcept.get(cid)?.localName).filter(Boolean))].sort();
  const reqProfiles = profileNames.filter(name => requirementSets[name].has(r.id));
  return [r.id, r.sourceSheet, r.source, r.edition, r.page, r.clause, r.category, r.activeStatus, canonicalTerms.join("; "), reqProfiles.join("; "), r.coverageStatus, r.codability, r.encodingPattern, r.figureDependent, r.sourceText];
});
compareMatrix("REQUIREMENT_PROFILE", [["Requirement_ID", "Source_Sheet", "Source", "Edition", "PDF_Page", "Clause", "Verification_Category", "Activation_Status", "Canonical_Stage2_Terms", "Profiles", "Stage1_Coverage_Status", "SHACL_Codability", "Encoding_Pattern", "Figure_Dependent", "Verified_Source_Text"], ...requirementRows]);

const patternRows = [
  ["Quantity value", "Entity -> canonical quantity property -> qudt:QuantityValue", "qudt:numericValue exactly 1 xsd:decimal; qudt:unit exactly 1 IRI", "Structural QA only; the pipeline generates regulatory SHACL"],
  ["Typed scalar", "Entity -> canonical datatype property -> literal", "Explicit xsd:boolean, xsd:integer, xsd:date, xsd:dateTime, or xsd:string", "No inferred datatype"],
  ["Controlled value", "Entity -> canonical object property -> controlled value IRI", "Ice class, Polar Class, polar ship category, evidence state, compliance state", "Avoid free-text variants"],
  ["Observation/history", "Entity -> nltl:hasObservation -> sosa:Observation", "Feature of interest, observed property, result time, and simple/node result", "Use for time-indexed evidence"],
  ["Document/test evidence", "Entity -> nltl:hasEvidence -> nltl:evidenceArtifact", "dcterms:source required; lifecycle/provenance represented on the node", "Do not reduce approvals to an unqualified boolean"],
  ["Source profile", "Profile -> allow-list of master class/property URIs", "No independent namespace and containsRequirementLogic=false", "Prevents source-specific schema drift"],
];
compareMatrix("NODE_PATTERNS", [["Pattern", "Canonical_Graph_Path", "Schema_Only_Constraint", "Boundary"], ...patternRows]);

const controlledRows = [];
for (const [scheme, values] of Object.entries({
  "Finnish-Swedish ice class": [["iceClassIaSuper","IA Super"],["iceClassIa","IA"],["iceClassIb","IB"],["iceClassIc","IC"],["iceClassIi","II"],["iceClassIii","III"]],
  "IACS Polar Class": Array.from({length:7}, (_,i) => [`polarClassPc${i+1}`, `PC${i+1}`]),
  "IMO polar ship category": [["polarShipCategoryA","Category A"],["polarShipCategoryB","Category B"],["polarShipCategoryC","Category C"]],
  "Evidence lifecycle": ["Draft","Submitted","UnderReview","Approved","Rejected","Expired","Revoked"].map(x => [`evidenceState${x}`, x]),
  "Compliance state": ["Compliant","NonCompliant","NotApplicable","Unknown"].map(x => [`complianceState${x}`, x]),
})) for (const [local, label] of values) controlledRows.push([scheme, local, `${manifest.provisionalVocabularyBase}${local}`, label]);
compareMatrix("CONTROLLED_VALUES", [["Scheme", "Local_Name", "IRI", "Preferred_Label"], ...controlledRows]);

compareMatrix("NAMING_REFINEMENTS", [["Stage1_Local_Name", "Stage2_Local_Name", "Action", "Reason"], ...refinements.map(x => [x.stage1LocalName, x.stage2LocalName, x.action, x.reason])]);
const retiredRows = [];
for (const [cid, item] of Object.entries(retired)) for (const [rid, redirect] of Object.entries(item.requirementRedirects)) retiredRows.push([cid, item.stage1LocalName, item.reason, rid, redirect, `${manifest.provisionalVocabularyBase}${redirect}`]);
compareMatrix("RETIRED_CANDIDATE", [["Stage1_Concept_ID", "Stage1_Local_Name", "Retirement_Reason", "Requirement_ID", "Redirect_Canonical_Term", "Redirect_URI"], ...retiredRows]);

const externalRows = external.qudtUnits.map(x => ["QUDT unit", x.uri, x.officialResource, x.officialVocabularyIndex, x.verifiedDate, x.verificationStatus]);
for (const uri of external.w3cNamespaces) externalRows.push(["W3C namespace", uri, uri, "", manifest.generatedDate, "Stable W3C namespace used by the benchmark"]);
compareMatrix("EXTERNAL_URI_REGISTER", [["Type", "URI", "Direct_Resource", "Vocabulary_Index", "Verified_Date", "Status"], ...externalRows]);
compareMatrix("VALIDATION", [["Check", "Status", "Detail"], ...validation.checks.map(x => [x.check, x.status, typeof x.detail === "string" ? x.detail : JSON.stringify(x.detail)])]);

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
if (manifest.revision === "R2") decisionRows.push([
  "DEC-S2-R2-01",
  "Adopted",
  "IMO-057 relationship repair",
  "Retire string-valued containingCompartment; add hasContainingCompartment plus explicit compartment and pump classes",
  "The verified clause requires traversal from each named pump category to a compartment whose maintained temperature is above freezing; a string cannot support that SHACL path.",
]);
compareMatrix("DECISIONS_LIMITATIONS", [["Item_ID", "Status", "Topic", "Decision_or_Limitation", "Engineering_Rationale_or_Treatment"], ...decisionRows]);
const sourceRows = evidence.manifest.map(x => [x.sourceId, x.path, x.filename, x.role, x.versionDate, x.pageCount, x.sha256, x.status, x.notes]);
compareMatrix("SOURCE_LINEAGE", [["Source_ID", "Exact_Path", "Filename", "Content_Role", "Version_Date", "Page_Count", "SHA256", "Status", "Notes"], ...sourceRows]);
if (manifest.revision === "R2") {
  const r2Names = new Set(["compartment", "hasContainingCompartment", "emergencyFirePump", "waterMistPump", "waterSprayPump"]);
  const r2Rows = terms.filter(t => r2Names.has(t.localName)).map(t => [
    "IMO-057", t.sourceConceptIds.join("; "), t.localName, t.iri, t.kind, t.parentOrRange,
    t.aliases.join("; "), t.sourceRefs, t.evidenceExcerpt, t.normalizedDefinition,
  ]);
  compareMatrix("R2_REVISIONS", [["Requirement_ID", "Concept_ID", "Canonical_Local_Name", "Canonical_URI", "Kind", "Parent_or_Range", "Aliases", "Source_Reference", "Verified_Evidence", "Normalized_Rationale"], ...r2Rows]);
}

const formulaScan = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "independent formula error scan", maxChars: 4000 });
assert(formulaScan.ndjson.includes("matched 0 entries"), "formula error scan", "0 formula error cells");

const visualRenderFiles = [
  "01_README_A1-H37.png", "02_MASTER_TERMS_A1-M18.png", "03_MASTER_TERMS_N1-Y18.png",
  "04_PROFILE_SUMMARY_A1-I9.png", "05_PROFILE_MEMBERSHIP_A1-K18.png",
  "06_REQUIREMENT_PROFILE_A1-H16.png", "07_REQUIREMENT_PROFILE_I1-O16.png",
  "08_NODE_PATTERNS_A1-D8.png", "09_CONTROLLED_VALUES_A1-D30.png",
  manifest.revision === "R2" ? "10_NAMING_REFINEMENTS_A1-D14.png" : "10_NAMING_REFINEMENTS_A1-D13.png", "11_RETIRED_CANDIDATE_A1-F5.png",
  "12_EXTERNAL_URI_REGISTER_A1-F34.png", manifest.revision === "R2" ? "13_VALIDATION_A1-C46.png" : "13_VALIDATION_A1-C43.png",
  "14_DECISIONS_LIMITATIONS_A1-E13.png", "15_SOURCE_LINEAGE_A1-I21.png",
];
if (manifest.revision === "R2") visualRenderFiles.push("16_R2_REVISIONS_A1-J6.png");
const renderExistence = await Promise.all(visualRenderFiles.map(async x => {
  try { await fs.access(path.join(stage2, "qa_workbook", x)); return true; } catch { return false; }
}));
assert(renderExistence.every(Boolean), "all-sheet visual render coverage", `${visualRenderFiles.length} inspected renders covering all ${expectedSheets.length} sheets`);

const workbookBytes = await fs.readFile(workbookPath);
const workbookSha256 = crypto.createHash("sha256").update(workbookBytes).digest("hex");
const report = {
  status: "PASS",
  verifiedDate: manifest.generatedDate,
  workbook: path.relative(path.dirname(stage2), workbookPath),
  workbookSha256,
  sheets: expectedSheets.length,
  terms: terms.length,
  requirements: evidence.requirements.length,
  visualReview: `PASS - all ${visualRenderFiles.length} renders covering all ${expectedSheets.length} sheets were inspected for clipping, legibility, and layout defects`,
  checksPassed: checks.length,
  checks,
};
await fs.writeFile(path.join(stage2, `validation/${reportStem}.json`), JSON.stringify(report, null, 2) + "\n", "utf8");
const markdown = [
  "# Stage 2 workbook verification", "", "Status: **PASS**", "",
  `Workbook SHA-256: \`${workbookSha256}\``, "",
  `Sheets: **${expectedSheets.length}**  `, `Canonical terms: **${terms.length}**  `,
  `Requirements: **${evidence.requirements.length}**  `, `Independent checks passed: **${checks.length}**`, "",
  ...checks.map(x => `- ${x.check}: PASS - ${typeof x.detail === "string" ? x.detail : JSON.stringify(x.detail)}`), "",
];
await fs.writeFile(path.join(stage2, `validation/${reportStem.toUpperCase()}.md`), markdown.join("\n"), "utf8");
console.log(JSON.stringify(report, null, 2));
