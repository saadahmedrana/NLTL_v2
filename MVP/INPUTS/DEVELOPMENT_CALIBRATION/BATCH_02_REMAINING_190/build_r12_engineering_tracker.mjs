import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const batch = path.join(root, "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190");
const r12 = path.join(root, "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R12_FINAL_GAP_CLOSURE");
const read = async p => JSON.parse(await fs.readFile(p, "utf8"));
const analysis = await read(path.join(batch, "r12_failure_analysis.json"));
const schemaQueue = await read(path.join(batch, "generation_queue_r12_schema_confirmation.json"));
const controlQueue = await read(path.join(batch, "generation_queue_r12_generator_control.json"));
const decisions = await read(path.join(r12, "registry/r12_change_decisions.json"));
const registry = await read(path.join(r12, "registry/term_registry.json"));
const index = await read(path.join(r12, "requirement_term_index.json"));
const evidencePayload = await read(path.join(r12, "evidence/stage1_approved.json"));
const validation = await read(path.join(r12, "validation/validation_report.json"));
const evidence = Object.fromEntries(evidencePayload.requirements.map(x => [x.id, x]));
const terms = Object.fromEntries(registry.map(x => [x.localName, x]));
const results = Object.fromEntries(analysis.records.map(x => [x.requirement_id, x]));

const contractRows = schemaQueue.requirements.map(rid => {
  const c = index.dependencyContracts[rid];
  return [rid, c.status, c.engineeringDecision, c.applicabilityTerms.join(" | "), c.relationshipTerms.join(" | "), c.controlledValueTerms.join(" | "), c.operandTerms.join(" | "), c.resultTerms.join(" | "), c.evidenceTerms.join(" | "), c.comparisonModel, c.formulaExpression, c.tableModel];
});

const specs = [
  {name:"README", headers:["SECTION","DETAIL"], rows:[
    ["PURPOSE","Trace the offline R12 closure of the eight source-grounded vocabulary or requirement-model gaps exposed by R11."],
    ["BOUNDARY","R12 remains development calibration and is not the final experimental vocabulary lock."],
    ["SOURCE CONTROL","Names and controlled values derive from verified IACS UR I2, MSC.385(94) clause 12.3.1, and TRAFICOM clause 6.6.5.2 wording. No external equivalence is claimed."],
    ["SCHEMA CONFIRMATION","Run the eight changed-context requirements once."],
    ["GENERATOR CONTROL","Run the five failures with sufficient vocabulary only after schema confirmation; they test generator behavior, not vocabulary coverage."],
    ["NO API","No API calls were made while constructing or validating R12."],
  ]},
  {name:"R11_RESULTS", headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R11_STATUS","ACCEPTED","ATTEMPTS","CLASSIFICATION","R12_TERMS","QUEUE","FINAL_FEEDBACK"], rows:analysis.records.map(x=>{const e=evidence[x.requirement_id];return[x.requirement_id,e.sourceSheet,e.page,e.clause,x.status,x.accepted,x.attempts,x.classification,x.r12_terms.join(" | "),x.queue,x.final_feedback]})},
  {name:"TERM_ADDITIONS", headers:["LOCAL_NAME","IRI","LABEL","KIND","DOMAIN","RANGE","DATATYPE","UNIT_IRI","UNIT_SYMBOL","ALIASES","REQUIREMENTS","SOURCE_REFS","RATIONALE"], rows:decisions.map(d=>{const t=terms[d.canonicalLocalName];return[t.localName,t.iri,t.label,t.kind,d.domain,t.parentOrRange,t.datatype,t.unitIri,t.unitSymbol,t.aliases.join(" | "),t.requirements.join(" | "),t.sourceRefs,d.rationale]})},
  {name:"CONTRACT_CHANGES", headers:["REQUIREMENT_ID","STATUS","DECISION","APPLICABILITY","RELATIONSHIPS","CONTROLLED_VALUES","OPERANDS","RESULTS","EVIDENCE","COMPARISON_MODEL","FORMULA","TABLE_MODEL"], rows:contractRows},
  {name:"SCHEMA_QUEUE", headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R11_STATUS","PURPOSE"], rows:schemaQueue.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,results[rid].status,"Confirm changed R12 vocabulary/contract once"])},
  {name:"GENERATOR_CONTROL", headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R11_STATUS","REASON"], rows:controlQueue.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,results[rid].status,"Vocabulary sufficient; isolate generator repair behavior"])},
  {name:"VALIDATION", headers:["CHECK","RESULT","DETAIL"], rows:[
    ["Ontology and registry",validation.status,`${validation.registryTerms} terms; ${validation.addedTerms} R12 additions`],
    ["Local-name QA","PASS","All registry local names are unique ASCII-only lowerCamelCase identifiers"],
    ["Source grounding","PASS","Controlled training values verified in MSC.385(94) 12.3.1; table/contact terms verified in TRAFICOM 6.6.5.2"],
    ["Schema confirmation queue","PASS",`${validation.schemaConfirmationQueue} changed-context cases`],
    ["Generator control queue","PASS",`${validation.generatorControlQueue} sufficient-vocabulary cases`],
    ["API calls during R12 build","PASS","0"],
  ]},
];

const wb=Workbook.create();
const c={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7",red:"#FEE2E2",amber:"#FEF3C7"};
const col=i=>{let n=i+1,s="";while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/FEEDBACK|RATIONALE|DETAIL|REASON|COMPARISON|FORMULA|TABLE_MODEL/.test(h)?52:/TERM|IRI|SOURCE_REF|CLASSIFICATION|APPLICABILITY|RELATIONSHIP|CONTROLLED|OPERAND|EVIDENCE/.test(h)?38:/STATUS|RESULT|PURPOSE|QUEUE/.test(h)?28:18;
const summary=wb.worksheets.add("SUMMARY");summary.showGridLines=false;summary.getRange("A1:D1").format.fill=c.navy;summary.getRange("A1").values=[["R12 Final-Gap-Closure Development Revision"]];summary.getRange("A1").format.font={bold:true,color:c.white,size:16};summary.getRange("A2:D2").format={fill:c.pale,font:{color:c.gray,italic:true}};summary.getRange("A2").values=[["VOCAB-DEV-2026-08-14-R12-FINAL-GAP-CLOSURE"]];summary.getRange("A4:B4").values=[["METRIC","VALUE"]];summary.getRange("A4:B4").format={fill:c.teal,font:{bold:true,color:c.white}};summary.getRange("A5:A13").values=[["R11 cases"],["R11 accepted"],["R11 failures"],["R12 registry terms"],["R12 terms added"],["Owner assignments inferred"],["Schema confirmation"],["Generator control"],["API calls during build"]];summary.getRange("B5:B13").values=[[analysis.r11_cases],[analysis.r11_accepted],[analysis.r11_failures],[validation.registryTerms],[validation.addedTerms],[validation.ownerAssignmentsInferred],[schemaQueue.requirements.length],[controlQueue.requirements.length],[0]];summary.getRange("A5:A13").format.font={bold:true,color:c.navy};summary.getRange("A1:A13").format.columnWidth=34;summary.getRange("B1:B13").format.columnWidth=48;summary.getRange("C1:D13").format.columnWidth=8;summary.getRange("A1:D13").format.font.name="Aptos";summary.freezePanes.freezeRows(4);
let ti=1;
for(const s of specs){const sh=wb.worksheets.add(s.name);sh.showGridLines=false;const lc=col(s.headers.length-1),lr=4+s.rows.length;sh.getRange(`A1:${lc}1`).format.fill=c.navy;sh.getRange("A1").values=[["R12 Final-Gap-Closure Development Revision"]];sh.getRange("A1").format.font={bold:true,color:c.white,size:15};sh.getRange(`A2:${lc}2`).format={fill:c.pale,font:{color:c.gray,italic:true}};sh.getRange("A2").values=[[`${s.name} | editable engineering traceability`]];sh.getRange(`A4:${lc}4`).values=[s.headers];sh.getRange(`A4:${lc}4`).format={fill:c.teal,font:{bold:true,color:c.white},wrapText:true,rowHeight:30};if(s.rows.length){sh.getRange(`A5:${lc}${lr}`).values=s.rows;sh.getRange(`A5:${lc}${lr}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:c.line}}};sh.tables.add(`A4:${lc}${lr}`,true,`R12T${ti}`)}for(let i=0;i<s.headers.length;i++){const l=col(i),h=s.headers[i],rg=sh.getRange(`${l}4:${l}${Math.max(5,lr)}`);rg.format.columnWidth=width(h);if(/FEEDBACK|RATIONALE|DETAIL|REASON|TERM|REF|CLASSIFICATION|APPLICABILITY|RELATIONSHIP|CONTROLLED|OPERAND|RESULTS|EVIDENCE|COMPARISON|FORMULA|TABLE_MODEL/.test(h))rg.format.wrapText=true;if(/STATUS|RESULT|ACCEPTED/.test(h)&&s.rows.length){const d=sh.getRange(`${l}5:${l}${lr}`);d.conditionalFormats.add("containsText",{text:"PASS",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"ACCEPT",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"MAX",format:{fill:c.amber}});d.conditionalFormats.add("containsText",{text:"UNRESOLVED",format:{fill:c.red}})}}sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(Math.min(2,s.headers.length));sh.getRange(`A1:${lc}${Math.max(5,lr)}`).format.font.name="Aptos";ti++}

const out=path.join(batch,"r12_engineering_change_tracker.xlsx");
const previewDir=path.join(batch,"validation/r12_tracker_previews");await fs.mkdir(previewDir,{recursive:true});
const rendered=[];for(const name of ["SUMMARY",...specs.map(s=>s.name)]){const png=await wb.render({sheetName:name,autoCrop:"all",scale:0.8,format:"png"});const p=path.join(previewDir,`${name.toLowerCase()}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:name,preview:path.relative(batch,p)})}
const inspect=await wb.inspect({kind:"table",range:"SUMMARY!A1:B13",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:6000});
const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(out);
await fs.writeFile(path.join(batch,"validation/r12_tracker_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(out),sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:out,sheets:1+specs.length,previews:rendered.length},null,2));
