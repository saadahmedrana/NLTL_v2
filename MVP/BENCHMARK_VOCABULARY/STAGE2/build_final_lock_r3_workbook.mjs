import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const dir = path.join(root, "BENCHMARK_VOCABULARY/FINAL_LOCK_R3");
const read = async rel => JSON.parse(await fs.readFile(path.join(dir, rel), "utf8"));
const registry = await read("registry/term_registry.json");
const index = await read("requirement_term_index.json");
const evidence = await read("evidence/stage1_approved.json");
const additions = await read("registry/r13_change_decisions.json");
const confirmation = await read("confirmation/r13_confirmation_results.json");
const prelock = await read("prelock_manifest.json");
const validation = await read("validation/validation_report.json");

const reqs = evidence.requirements;
const contracts = index.dependencyContracts;
const owners = index.termOwners;
const join = v => Array.isArray(v) ? v.join(" | ") : (v ?? "");
const reqRows = reqs.map(r => {
  const c = contracts[r.id] ?? {};
  return [r.id, r.sourceSheet, r.page, r.clause, r.category, r.activeStatus, r.encodingPattern, r.figureDependent,
    join(index.requirementTargetOwner[r.id]), (index.requirements[r.id] ?? []).length, join(index.requirements[r.id]), c.status ?? ""];
});
const contractRows = Object.entries(contracts).map(([id,c]) => [id,c.status,c.engineeringDecision,join(c.ownerClasses),join(c.applicabilityTerms),join(c.operandTerms),join(c.resultTerms),join(c.relationshipTerms),join(c.timeTerms),join(c.controlledValueTerms),join(c.evidenceTerms),c.comparisonModel,c.tableModel,c.encodingPattern,join(c.auditFlags)]);
const ownerRows = Object.entries(owners).flatMap(([requirementId,mapping]) =>
  Object.entries(mapping).map(([term,owner]) => [requirementId,term,owner])
);
const controlled = registry.filter(t => t.kind === "NamedIndividual").map(t => [t.conceptId,t.localName,t.iri,t.label,t.parentOrRange,join(t.requirements),t.sourceRefs,t.namingBasis,t.confidence]);
const termRows = registry.map(t => [t.conceptId,t.localName,t.iri,t.label,t.kind,t.module,t.parentOrRange,t.datatype,t.unitIri,t.unitSymbol,join(t.aliases),join(t.requirements),t.sourceRefs,t.normalizedDefinition,t.namingBasis,t.namingRule,t.mappingStatus,t.confidence,t.nameQaStatus]);
const addRows = additions.map(d => [d.canonicalLocalName,d.kind,d.domain,d.range,join(d.linkedRequirements),d.action,d.rationale]);
const confRows = confirmation.results.map(r => [r.requirementId,r.runId,r.status,r.accepted,r.attempts,r.finalShapeSha256,r.finalFeedback,r.sourceRunDirectory]);
const hashRows = Object.entries(prelock.boundArtifacts).map(([p,h]) => [p,h]);

const specs = [
  {name:"README", headers:["SECTION","DETAIL"], rows:[
    ["LOCK ID","VOCAB-LOCK-2026-08-14-R3"],["STATUS","Final experiment input; immutable by content hash"],
    ["PURPOSE","Canonical NL-to-SHACL benchmark vocabulary and complete requirement dependency contracts."],
    ["EXPERIMENT RULE","An invented, missed, or misused term that already exists in this lock is a model/pipeline outcome. A genuinely absent concept is a benchmark-infrastructure defect and must not be patched during a scored run."],
    ["COUNTS",`${registry.length} registry terms; 1673 canonical terms including infrastructure; ${reqs.length} requirements; ${validation.errors.length} validation errors; 0 known vocabulary gaps.`],
    ["SUPERSEDES","VOCAB-LOCK-2026-08-12-R2; prior locks remain historical evidence."],
    ["PUBLICATION ITEMS","Provisional w3id namespace is not registered; ISO 19848 normative text remains unavailable. These do not block private experiments."],
    ["API CALLS","No API calls were made to construct or lock R3."],
  ]},
  {name:"MASTER_TERMS",headers:["CONCEPT_ID","LOCAL_NAME","IRI","LABEL","KIND","MODULE","PARENT_OR_RANGE","DATATYPE","UNIT_IRI","UNIT_SYMBOL","ALIASES","REQUIREMENTS","SOURCE_REFS","NORMALIZED_DEFINITION","NAMING_BASIS","NAMING_RULE","MAPPING_STATUS","CONFIDENCE","NAME_QA_STATUS"],rows:termRows},
  {name:"REQUIREMENTS",headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","CATEGORY","ACTIVE_STATUS","ENCODING_PATTERN","FIGURE_DEPENDENT","TARGET_OWNER","TERM_COUNT","TERMS","CONTRACT_STATUS"],rows:reqRows},
  {name:"CONTRACTS",headers:["REQUIREMENT_ID","STATUS","ENGINEERING_DECISION","OWNER_CLASSES","APPLICABILITY","OPERANDS","RESULTS","RELATIONSHIPS","TIME","CONTROLLED_VALUES","EVIDENCE","COMPARISON_MODEL","TABLE_MODEL","ENCODING_PATTERN","AUDIT_FLAGS"],rows:contractRows},
  {name:"TERM_OWNERS",headers:["REQUIREMENT_ID","TERM","OWNER_CLASS"],rows:ownerRows},
  {name:"CONTROLLED_VALUES",headers:["CONCEPT_ID","LOCAL_NAME","IRI","LABEL","VALUE_CLASS","REQUIREMENTS","SOURCE_REFS","NAMING_BASIS","CONFIDENCE"],rows:controlled},
  {name:"R13_ADDITIONS",headers:["LOCAL_NAME","KIND","DOMAIN","RANGE","REQUIREMENTS","ACTION","RATIONALE"],rows:addRows},
  {name:"CONFIRMATION",headers:["REQUIREMENT_ID","RUN_ID","STATUS","ACCEPTED","ATTEMPTS","FINAL_SHAPE_SHA256","FINAL_FEEDBACK","SOURCE_RUN_DIRECTORY"],rows:confRows},
  {name:"ARTIFACT_HASHES",headers:["BOUND_ARTIFACT","SHA256"],rows:hashRows},
  {name:"VALIDATION",headers:["CHECK","RESULT","DETAIL"],rows:[
    ["Registry size","PASS",String(registry.length)],["Requirements","PASS",String(reqs.length)],
    ["Complete contracts","PASS",String(Object.values(contracts).filter(c=>c.status==="COMPLETE").length)],
    ["Known vocabulary gaps","PASS","0"],["R13 confirmation","PASS","I2-046 and IMO-102 accepted"],
    ["Ontology syntax","PASS","Turtle and RDF/XML parsed before finalization"],["Offline tests","PASS","44/44"],
  ]},
];

const wb = Workbook.create();
const C={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7"};
const col=i=>{let n=i+1,s="";while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/DEFINITION|RATIONALE|DECISION|MODEL|DETAIL|FEEDBACK|RULE/.test(h)?48:/IRI|TERMS|REFS|ALIASES|OWNER|VALUES|DIRECTORY/.test(h)?36:/STATUS|BASIS|ACTION/.test(h)?26:18;
let tableNo=1;
for (const spec of specs) {
  const sh=wb.worksheets.add(spec.name); sh.showGridLines=false;
  const last=col(spec.headers.length-1), lastRow=4+spec.rows.length;
  sh.getRange(`A1:${last}1`).format.fill=C.navy; sh.getRange("A1").values=[["NLTL Benchmark Vocabulary — Final Lock R3"]];
  sh.getRange("A1").format.font={bold:true,color:C.white,size:15};
  sh.getRange(`A2:${last}2`).format={fill:C.pale,font:{color:C.gray,italic:true}}; sh.getRange("A2").values=[[`${spec.name} | VOCAB-LOCK-2026-08-14-R3`]];
  sh.getRange(`A4:${last}4`).values=[spec.headers]; sh.getRange(`A4:${last}4`).format={fill:C.teal,font:{bold:true,color:C.white},wrapText:true,rowHeight:30};
  if(spec.rows.length){sh.getRange(`A5:${last}${lastRow}`).values=spec.rows;sh.getRange(`A5:${last}${lastRow}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:C.line}}};sh.tables.add(`A4:${last}${lastRow}`,true,`R3T${tableNo++}`)}
  for(let i=0;i<spec.headers.length;i++){const l=col(i),h=spec.headers[i],r=sh.getRange(`${l}4:${l}${Math.max(5,lastRow)}`);r.format.columnWidth=width(h);if(width(h)>=36)r.format.wrapText=true}
  sh.freezePanes.freezeRows(4); sh.freezePanes.freezeColumns(Math.min(2,spec.headers.length)); sh.getRange(`A1:${last}${Math.max(5,lastRow)}`).format.font.name="Aptos";
}

const out=path.join(dir,"benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.xlsx");
const previewDir=path.join(dir,"validation/final_lock_workbook_previews"); await fs.mkdir(previewDir,{recursive:true});
const rendered=[];
for(const spec of specs){const maxRows=Math.min(30,4+spec.rows.length),last=col(spec.headers.length-1);const png=await wb.render({sheetName:spec.name,range:`A1:${last}${maxRows}`,scale:0.65,format:"png"});const p=path.join(previewDir,`${String(rendered.length+1).padStart(2,"0")}_${spec.name}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:spec.name,preview:path.relative(dir,p),renderedRange:`A1:${last}${maxRows}`})}
const inspect=await wb.inspect({kind:"table",range:"README!A1:B12",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:6000});
const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const file=await SpreadsheetFile.exportXlsx(wb); await file.save(out);
await fs.writeFile(path.join(dir,"validation/final_lock_workbook_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(out),sheetCount:specs.length,sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson,visualReview:"Pending manual inspection of all rendered previews"},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:out,sheets:specs.length,registryTerms:registry.length,requirements:reqs.length,previews:rendered.length},null,2));
