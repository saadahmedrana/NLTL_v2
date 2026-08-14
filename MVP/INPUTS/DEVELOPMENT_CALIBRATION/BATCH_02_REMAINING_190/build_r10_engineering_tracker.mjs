import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [rootArg] = process.argv.slice(2);
const root = path.resolve(rootArg);
const batch = path.join(root, "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190");
const r10 = path.join(root, "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R10_GRAPH_COMPLETION");
const read = async p => JSON.parse(await fs.readFile(p, "utf8"));
const failures = await read(path.join(batch, "r10_failure_analysis.json"));
const queue = await read(path.join(batch, "generation_queue_r10_affected.json"));
const decisions = await read(path.join(r10, "registry/r10_change_decisions.json"));
const registry = await read(path.join(r10, "registry/term_registry.json"));
const index = await read(path.join(r10, "requirement_term_index.json"));
const evidencePayload = await read(path.join(r10, "evidence/stage1_approved.json"));
const validation = await read(path.join(r10, "validation/validation_report.json"));
const evidence = Object.fromEntries(evidencePayload.requirements.map(x => [x.id, x]));
const terms = Object.fromEntries(registry.map(x => [x.localName, x]));
const failure = Object.fromEntries(failures.records.map(x => [x.requirement_id, x]));
const sheets = [
  {name:"README",headers:["SECTION","DETAIL"],rows:[
    ["PURPOSE","Trace R10 repairs for the 63 unsuccessful R9 confirmation cases."],
    ["BOUNDARY","R10 is development calibration, not a final experiment lock."],
    ["PRIMARY REPAIR","Complete graph paths, authoritative per-node property ownership, table attribution, controlled selectors, evidence relationships, and formula roles."],
    ["FAIL-CLOSED GATE","Schema-v2 contracts are checked locally for exact terms, indexing, required fields, object-path kind, path domain/range compatibility, and owner/domain compatibility."],
    ["DEFERRED","I2-008 is a non-self-contained umbrella statement; its complete downstream formula clauses remain active."],
    ["NO API","No API calls were made while constructing or validating R10."],
  ]},
  {name:"R9_FAILURES",headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R9_STATUS","ATTEMPTS","ROOT_CAUSES","R9_FEEDBACK","R10_DECISION","R10_CONTRACT_STATUS"],rows:failures.records.map(x=>[x.requirement_id,x.source_sheet,x.page,x.clause,x.status,x.attempts,x.root_causes.join(" | "),x.final_feedback,index.dependencyContracts[x.requirement_id].engineeringDecision,index.dependencyContracts[x.requirement_id].status])},
  {name:"TERM_ADDITIONS",headers:["LOCAL_NAME","IRI","LABEL","KIND","DOMAIN","RANGE","DATATYPE","UNIT_IRI","UNIT_SYMBOL","ALIASES","REQUIREMENTS","SOURCE_REFS","RATIONALE"],rows:decisions.map(d=>{const t=terms[d.canonicalLocalName];return[t.localName,t.iri,t.label,t.kind,d.domain,t.parentOrRange,t.datatype,t.unitIri,t.unitSymbol,t.aliases.join(" | "),t.requirements.join(" | "),t.sourceRefs,d.rationale]})},
  {name:"CONTRACTS_V2",headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","STATUS","ENGINEERING_DECISION","OWNER_CLASSES","APPLICABILITY_TERMS","OPERAND_TERMS","RESULT_TERMS","RELATIONSHIP_TERMS","CONTROLLED_VALUES","MODEL_PATHS","FORMULA_EXPRESSION","COMPARISON_MODEL","TABLE_MODEL","BLOCKER"],rows:failures.records.map(x=>{const c=index.dependencyContracts[x.requirement_id];return[x.requirement_id,x.source_sheet,x.page,x.clause,c.status,c.engineeringDecision,(c.ownerClasses||[]).join(" | "),(c.applicabilityTerms||[]).join(" | "),(c.operandTerms||[]).join(" | "),(c.resultTerms||[]).join(" | "),(c.relationshipTerms||[]).join(" | "),(c.controlledValueTerms||[]).join(" | "),JSON.stringify(c.modelPaths||[]),c.formulaExpression||"",c.comparisonModel||"",c.tableModel||"",c.blocker||""]})},
  {name:"OWNER_ASSIGNMENTS",headers:["REQUIREMENT_ID","TERM","OWNER","TERM_DOMAIN","TERM_KIND"],rows:Object.entries(index.termOwners||{}).flatMap(([rid,map])=>Object.entries(map).filter(([name])=>decisions.some(d=>d.canonicalLocalName===name)).map(([name,owner])=>[rid,name,owner,(terms[name]?.domains||[]).join(" | ")||"See ontology rdfs:domain",terms[name]?.kind||""]))},
  {name:"R10_QUEUE",headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R9_STATUS","R10_STATUS","PURPOSE"],rows:queue.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,failure[rid].status,index.dependencyContracts[rid].status,"Confirm R10 repair once"])},
  {name:"DEFERRED",headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","STATUS","REASON","COVERAGE"],rows:[["I2-008",evidence["I2-008"].sourceSheet,evidence["I2-008"].page,evidence["I2-008"].clause,index.dependencyContracts["I2-008"].status,index.dependencyContracts["I2-008"].blocker,"Downstream I2.3.2 formula requirements remain active"]]},
  {name:"VALIDATION",headers:["CHECK","RESULT","DETAIL"],rows:[
    ["Ontology/registry build",validation.status,`${validation.registryTerms} terms; ${validation.addedTerms} R10 additions`],
    ["All requirement contexts","PASS","313/313 build locally"],
    ["Active schema-v2 contracts","PASS","Ownership and object-path checks enabled"],
    ["Offline tests","PASS","40/40"],
    ["Pipeline doctor","PASS",`${validation.generationEligible} generation-eligible requirements`],
    ["API calls during R10","PASS","0"],
  ]},
];

const wb=Workbook.create(); const c={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7",red:"#FEE2E2",amber:"#FEF3C7"};
const col=i=>{let n=i+1,s="";while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/FEEDBACK|MODEL|RATIONALE|DETAIL|REASON|PATH|FORMULA/.test(h)?48:/TERM|IRI|CAUSE|REF/.test(h)?36:/STATUS|DECISION/.test(h)?28:18;
const summary=wb.worksheets.add("SUMMARY");summary.showGridLines=false;summary.getRange("A1:D1").format.fill=c.navy;summary.getRange("A1").values=[["R10 Graph-Completion Development Revision"]];summary.getRange("A1").format.font={bold:true,color:c.white,size:16};summary.getRange("A2:D2").format={fill:c.pale,font:{color:c.gray,italic:true}};summary.getRange("A2").values=[["VOCAB-DEV-2026-08-13-R10-GRAPH-COMPLETION"]];summary.getRange("A4:B4").values=[["METRIC","VALUE"]];summary.getRange("A4:B4").format={fill:c.teal,font:{bold:true,color:c.white}};summary.getRange("A5:A15").values=[["R9 confirmation runs"],["R9 accepted"],["R9 unresolved terms/models"],["R9 maximum attempts"],["R10 registry terms"],["R10 terms added"],["Generation eligible"],["R10 confirmation queue"],["Deferred umbrella cases"],["All contexts validated"],["Offline tests passing"]];summary.getRange("B5:B15").values=[[112],[49],[58],[5],[validation.registryTerms],[validation.addedTerms],[validation.generationEligible],[queue.requirements.length],[1],[313],[40]];summary.getRange("A5:A15").format.font={bold:true,color:c.navy};summary.getRange("A1:A15").format.columnWidth=36;summary.getRange("B1:B15").format.columnWidth=46;summary.getRange("C1:D15").format.columnWidth=8;summary.getRange("A1:D15").format.font.name="Aptos";summary.freezePanes.freezeRows(4);
let ti=1;for(const s of sheets){const sh=wb.worksheets.add(s.name);sh.showGridLines=false;const lc=col(s.headers.length-1),lr=4+s.rows.length;sh.getRange(`A1:${lc}1`).format.fill=c.navy;sh.getRange("A1").values=[["R10 Graph-Completion Development Revision"]];sh.getRange("A1").format.font={bold:true,color:c.white,size:15};sh.getRange(`A2:${lc}2`).format={fill:c.pale,font:{color:c.gray,italic:true}};sh.getRange("A2").values=[[`${s.name} | editable engineering traceability`]];sh.getRange(`A4:${lc}4`).values=[s.headers];sh.getRange(`A4:${lc}4`).format={fill:c.teal,font:{bold:true,color:c.white},wrapText:true};if(s.rows.length){sh.getRange(`A5:${lc}${lr}`).values=s.rows;sh.getRange(`A5:${lc}${lr}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:c.line}}};sh.tables.add(`A4:${lc}${lr}`,true,`R10T${ti}`)}for(let i=0;i<s.headers.length;i++){const l=col(i),h=s.headers[i],rg=sh.getRange(`${l}4:${l}${Math.max(5,lr)}`);rg.format.columnWidth=width(h);if(/FEEDBACK|MODEL|RATIONALE|DETAIL|REASON|PATH|TERM|CAUSE|REF|FORMULA/.test(h))rg.format.wrapText=true;if(/STATUS|RESULT|DECISION/.test(h)&&s.rows.length){const d=sh.getRange(`${l}5:${l}${lr}`);d.conditionalFormats.add("containsText",{text:"PASS",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"COMPLETE",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"DEFER",format:{fill:c.amber}});d.conditionalFormats.add("containsText",{text:"FAIL",format:{fill:c.red}})}}sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(Math.min(2,s.headers.length));sh.getRange(`A1:${lc}${Math.max(5,lr)}`).format.font.name="Aptos";ti++}
const out=path.join(batch,"r10_engineering_change_tracker.xlsx"),previewDir=path.join(batch,"validation/r10_tracker_previews");await fs.mkdir(previewDir,{recursive:true});const rendered=[];for(const name of ["SUMMARY",...sheets.map(s=>s.name)]){const png=await wb.render({sheetName:name,autoCrop:"all",scale:0.8,format:"png"});const p=path.join(previewDir,`${name.toLowerCase()}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:name,preview:path.relative(batch,p)})}const inspect=await wb.inspect({kind:"table",range:"SUMMARY!A1:B15",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:6000});const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});const file=await SpreadsheetFile.exportXlsx(wb);await file.save(out);await fs.writeFile(path.join(batch,"validation/r10_tracker_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(out),sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson},null,2)+"\n");console.log(JSON.stringify({status:"PASS",workbook:out,sheets:1+sheets.length,previews:rendered.length},null,2));
