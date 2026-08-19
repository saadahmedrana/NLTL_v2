import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const dir = path.join(root, "BENCHMARK_VOCABULARY/FINAL_LOCK_R6");
const read = async rel => JSON.parse(await fs.readFile(path.join(dir, rel), "utf8"));
const registry = await read("registry/term_registry.json");
const index = await read("requirement_term_index.json");
const evidence = await read("evidence/stage1_approved.json");
const audit = await read("validation/global_consistency_audit/r6_global_consistency_audit.json");
const changes = await read("registry/r6_change_decisions.json");
const prelock = await read("prelock_manifest.json");
const join = value => Array.isArray(value) ? value.join(" | ") : (value ?? "");
const reqById = Object.fromEntries(evidence.requirements.map(row => [row.id, row]));

const sheets = [
  {name: "README", headers: ["SECTION", "DETAIL"], rows: [
    ["LOCK ID", "VOCAB-LOCK-2026-08-19-R6"],
    ["STATUS", "R6 candidate pending final offline verification"],
    ["SUPERSEDES", "Immutable VOCAB-LOCK-2026-08-19-R5; R5 and its run evidence are preserved"],
    ["NAMESPACE", "https://w3id.org/nltl/vocab#"],
    ["GLOBAL AUDIT", `${audit.contractsAudited}/313 contracts; ${audit.completeContractsAudited}/238 COMPLETE contracts; ${audit.flagged} flagged; ${audit.confirmedDefective} confirmed; ${audit.falsePositives} false positives`],
    ["SCHEMA CHANGE", "IMO-017 only: certificate date category class plus validity, survey, and endorsement controlled individuals"],
    ["DEPENDENCY CHANGES", "I2-013, I2-021, I2-030, I2-031, I2-041, I2-042, I2-043, IMO-083, IMO-118, IMO26-009, TRF-127"],
    ["PIPELINE HARDENING", "Syntax-only repair budget; validator history consistency; deterministic COMPLETE relationship and explicit policy linting"],
    ["API CALLS", "Zero during audit, correction, lock construction, and offline verification"],
  ]},
  {name: "MASTER_TERMS", headers: ["CONCEPT_ID", "LOCAL_NAME", "IRI", "LABEL", "KIND", "MODULE", "PARENT_OR_RANGE", "DATATYPE", "UNIT_IRI", "ALIASES", "REQUIREMENTS", "SOURCE_REFS", "NORMALIZED_DEFINITION", "NAMING_BASIS", "CONFIDENCE"], rows: registry.map(t => [t.conceptId,t.localName,t.iri,t.label,t.kind,t.module,t.parentOrRange,t.datatype,t.unitIri,join(t.aliases),join(t.requirements),t.sourceRefs,t.normalizedDefinition,t.namingBasis,t.confidence])},
  {name: "REQUIREMENTS", headers: ["ID","SOURCE","PAGE","CLAUSE","CATEGORY","ACTIVE_STATUS","TARGET_OWNER","TERMS","CONTRACT_STATUS"], rows: evidence.requirements.map(r => [r.id,r.sourceSheet,r.page,r.clause,r.category,r.activeStatus,index.requirementTargetOwner[r.id] ?? "ship",join(index.requirements[r.id]),index.dependencyContracts[r.id]?.status ?? ""])},
  {name: "CONTRACTS", headers: ["ID","STATUS","SCHEMA_VERSION","DECISION","OWNERS","APPLICABILITY","OPERANDS","RESULTS","COMPARISONS","RELATIONSHIPS","MODEL_PATHS","CONTROLLED_VALUES","EVIDENCE","FORMULA","COMPARISON_MODEL","AUDIT_FLAGS","R6_AUDIT_DISPOSITION"], rows: Object.entries(index.dependencyContracts).map(([id,c]) => [id,c.status,c.schemaVersion ?? 1,c.engineeringDecision,join(c.ownerClasses),join(c.applicabilityTerms),join(c.operandTerms),join(c.resultTerms),join(c.comparisonTerms),join(c.relationshipTerms),join((c.modelPaths ?? []).map(p => `${p.fromOwner} -> ${p.via} -> ${p.toOwner}`)),join(c.controlledValueTerms),join(c.evidenceTerms),c.formulaExpression ?? "",c.comparisonModel,join(c.auditFlags),c.r6AuditDisposition ?? ""])},
  {name: "TERM_OWNERS", headers: ["REQUIREMENT_ID","TERM","OWNER"], rows: Object.entries(index.termOwners).flatMap(([id,map]) => Object.entries(map).map(([term,owner]) => [id,term,owner]))},
  {name: "CONTROLLED_VALUES", headers: ["CONCEPT_ID","LOCAL_NAME","IRI","LABEL","VALUE_CLASS","REQUIREMENTS","SOURCE_REFS"], rows: registry.filter(t => t.kind === "NamedIndividual").map(t => [t.conceptId,t.localName,t.iri,t.label,t.parentOrRange,join(t.requirements),t.sourceRefs])},
  {name: "GLOBAL_AUDIT", headers: ["REQUIREMENT_ID","SUSPECTED_DEFECT","SOURCE_GROUNDED","CONFIRMED_ISSUE","CLASSIFICATION","PROPOSED_CORRECTION","SOURCE","PAGE","CLAUSE","SOURCE_TEXT","NORMALIZED_REQUIREMENT"], rows: audit.records.map(r => [r.requirementId,r.suspectedDefect,r.sourceGrounded,r.confirmedIssue,r.classification,r.proposedCorrection,r.source,r.page,r.clause,r.sourceText,r.normalizedRequirement])},
  {name: "R6_CHANGES", headers: ["REQUIREMENT_ID","CLASSIFICATION","ACTION","SOURCE_PAGE","SOURCE_CLAUSE"], rows: changes.map(c => [c.requirementId,c.classification,c.action,reqById[c.requirementId].page,reqById[c.requirementId].clause])},
  {name: "ARTIFACT_HASHES", headers: ["ARTIFACT","PRELOCK_SHA256"], rows: Object.entries(prelock.boundArtifacts)},
];

const workbook = Workbook.create();
const colors = {navy:"#17324D", teal:"#0F766E", pale:"#E8F1F5", white:"#FFFFFF", gray:"#5B6573", line:"#CBD5E1"};
const col = i => {let n=i+1,s=""; while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26);}return s;};
const width = h => /TEXT|DEFINITION|RATIONALE|ACTION|MODEL|DETAIL|CORRECTION|DEFECT/.test(h)?48:/IRI|TERMS|REFS|PATH|OWNERS/.test(h)?36:/STATUS|CLASSIFICATION|DECISION/.test(h)?26:18;
let tableId=1;
for (const spec of sheets) {
  const ws=workbook.worksheets.add(spec.name); ws.showGridLines=false;
  const last=col(spec.headers.length-1), end=4+spec.rows.length;
  ws.getRange(`A1:${last}1`).format.fill=colors.navy;
  ws.getRange("A1").values=[["NLTL Benchmark Vocabulary - Final Lock R6"]];
  ws.getRange("A1").format.font={bold:true,color:colors.white,size:15};
  ws.getRange(`A2:${last}2`).format={fill:colors.pale,font:{color:colors.gray,italic:true}};
  ws.getRange("A2").values=[[`${spec.name} | VOCAB-LOCK-2026-08-19-R6`]];
  ws.getRange(`A4:${last}4`).values=[spec.headers];
  ws.getRange(`A4:${last}4`).format={fill:colors.teal,font:{bold:true,color:colors.white},wrapText:true,rowHeight:30};
  if(spec.rows.length){ws.getRange(`A5:${last}${end}`).values=spec.rows;ws.getRange(`A5:${last}${end}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:colors.line}}};ws.tables.add(`A4:${last}${end}`,true,`R6T${tableId++}`);}
  spec.headers.forEach((h,i)=>{const letter=col(i),w=width(h),range=ws.getRange(`${letter}4:${letter}${Math.max(5,end)}`);range.format.columnWidth=w;if(w>=36)range.format.wrapText=true;});
  ws.freezePanes.freezeRows(4); ws.freezePanes.freezeColumns(Math.min(2,spec.headers.length));
  ws.getRange(`A1:${last}${Math.max(5,end)}`).format.font.name="Aptos";
}

const previewDir=path.join(dir,"validation/final_lock_workbook_previews"); await fs.mkdir(previewDir,{recursive:true});
const rendered=[];
for(const spec of sheets){const last=col(spec.headers.length-1), maxRows=Math.min(25,4+spec.rows.length);const png=await workbook.render({sheetName:spec.name,range:`A1:${last}${maxRows}`,scale:0.55,format:"png"});const file=path.join(previewDir,`${String(rendered.length+1).padStart(2,"0")}_${spec.name}.png`);await fs.writeFile(file,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:spec.name,preview:path.relative(dir,file),renderedRange:`A1:${last}${maxRows}`});}
const inspect=await workbook.inspect({kind:"table",range:"README!A1:B14",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:7000});
const errors=await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const output=path.join(dir,"benchmark_vocabulary_stage2_LOCK-2026-08-19-R6.xlsx");
const exported=await SpreadsheetFile.exportXlsx(workbook); await exported.save(output);
await fs.writeFile(path.join(dir,"validation/final_lock_workbook_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(output),sheetCount:sheets.length,sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson,visualReview:"PENDING"},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:output,sheets:sheets.length,previews:rendered.length,registryTerms:registry.length,requirements:evidence.requirements.length},null,2));
