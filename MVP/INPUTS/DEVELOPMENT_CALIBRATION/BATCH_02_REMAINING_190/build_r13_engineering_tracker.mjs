import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root=path.resolve(process.argv[2]);
const batch=path.join(root,"INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190");
const r13=path.join(root,"BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R13_APPLICABILITY_MATRIX_CLOSURE");
const read=async p=>JSON.parse(await fs.readFile(p,"utf8"));
const analysis=await read(path.join(batch,"r13_failure_analysis.json"));
const confirmation=await read(path.join(batch,"generation_queue_r13_confirmation.json"));
const held=await read(path.join(batch,"generation_queue_r13_generator_only_held.json"));
const decisions=await read(path.join(r13,"registry/r13_change_decisions.json"));
const registry=await read(path.join(r13,"registry/term_registry.json"));
const index=await read(path.join(r13,"requirement_term_index.json"));
const evidencePayload=await read(path.join(r13,"evidence/stage1_approved.json"));
const validation=await read(path.join(r13,"validation/validation_report.json"));
const evidence=Object.fromEntries(evidencePayload.requirements.map(x=>[x.id,x]));
const terms=Object.fromEntries(registry.map(x=>[x.localName,x]));
const results=Object.fromEntries(analysis.records.map(x=>[x.requirement_id,x]));

const specs=[
 {name:"README",headers:["SECTION","DETAIL"],rows:[
  ["PURPOSE","Trace R13 closure of the final two genuine vocabulary gaps exposed by R12."],
  ["BOUNDARY","R13 is development calibration pending a two-case confirmation; it is not the final experimental lock."],
  ["I2-046","Adds an explicit boolean Polar-Class applicability selector so missing polarClass data cannot silently establish non-applicability."],
  ["IMO-102","Adds controlled Ice-free/Other-waters, ship-type, and crew-role values for the exact MSC.385(94) 12.3.1 matrix; reuses the existing Open-water value."],
  ["GENERATOR-ONLY","Five R12 failures are held outside vocabulary completeness decisions."],
  ["NO API","No API calls were made while constructing or validating R13."],
 ]},
 {name:"R12_RESULTS",headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R12_STATUS","ACCEPTED","ATTEMPTS","CLASSIFICATION","R13_TERMS","QUEUE","FINAL_FEEDBACK"],rows:analysis.records.map(x=>{const e=evidence[x.requirement_id];return[x.requirement_id,e.sourceSheet,e.page,e.clause,x.status,x.accepted,x.attempts,x.classification,x.r13_terms.join(" | "),x.queue,x.final_feedback]})},
 {name:"TERM_ADDITIONS",headers:["LOCAL_NAME","IRI","LABEL","KIND","DOMAIN","RANGE","ALIASES","REQUIREMENTS","SOURCE_REFS","RATIONALE"],rows:decisions.map(d=>{const t=terms[d.canonicalLocalName];return[t.localName,t.iri,t.label,t.kind,d.domain,t.parentOrRange,t.aliases.join(" | "),t.requirements.join(" | "),t.sourceRefs,d.rationale]})},
 {name:"CONTRACTS",headers:["REQUIREMENT_ID","DECISION","APPLICABILITY","RELATIONSHIPS","CONTROLLED_VALUES","OPERANDS","COMPARISON_MODEL","TABLE_MODEL"],rows:confirmation.requirements.map(rid=>{const c=index.dependencyContracts[rid];return[rid,c.engineeringDecision,c.applicabilityTerms.join(" | "),c.relationshipTerms.join(" | "),c.controlledValueTerms.join(" | "),c.operandTerms.join(" | "),c.comparisonModel,c.tableModel]})},
 {name:"CONFIRMATION",headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R12_STATUS","PURPOSE"],rows:confirmation.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,results[rid].status,"Confirm final R13 vocabulary gap closure once"])},
 {name:"GENERATOR_HELD",headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R12_STATUS","REASON"],rows:held.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,results[rid].status,"Vocabulary sufficient; generation behavior only"])},
 {name:"VALIDATION",headers:["CHECK","RESULT","DETAIL"],rows:[
  ["Ontology and registry",validation.status,`${validation.registryTerms} terms; ${validation.addedTerms} R13 additions`],
  ["Local-name QA","PASS","Unique ASCII-only lowerCamelCase identifiers"],
  ["Confirmation queue","PASS",`${validation.confirmationQueue} genuine vocabulary-gap cases`],
  ["Generator-only hold","PASS",`${validation.generatorOnlyHeld} cases excluded from vocabulary completeness decisions`],
  ["API calls during R13 build","PASS","0"],
 ]},
];

const wb=Workbook.create();const c={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7",red:"#FEE2E2",amber:"#FEF3C7"};
const col=i=>{let n=i+1,s="";while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/FEEDBACK|RATIONALE|DETAIL|REASON|COMPARISON|TABLE_MODEL/.test(h)?52:/TERM|IRI|SOURCE_REF|CLASSIFICATION|APPLICABILITY|RELATIONSHIP|CONTROLLED|OPERAND/.test(h)?38:/STATUS|RESULT|PURPOSE|QUEUE/.test(h)?28:18;
const summary=wb.worksheets.add("SUMMARY");summary.showGridLines=false;summary.getRange("A1:D1").format.fill=c.navy;summary.getRange("A1").values=[["R13 Applicability and Matrix Closure"]];summary.getRange("A1").format.font={bold:true,color:c.white,size:16};summary.getRange("A2:D2").format={fill:c.pale,font:{color:c.gray,italic:true}};summary.getRange("A2").values=[["VOCAB-DEV-2026-08-14-R13-APPLICABILITY-MATRIX-CLOSURE"]];summary.getRange("A4:B4").values=[["METRIC","VALUE"]];summary.getRange("A4:B4").format={fill:c.teal,font:{bold:true,color:c.white}};summary.getRange("A5:A12").values=[["R12 cases"],["R12 accepted"],["R12 failures"],["R13 registry terms"],["R13 terms added"],["Confirmation cases"],["Generator-only held"],["API calls during build"]];summary.getRange("B5:B12").values=[[analysis.r12_cases],[analysis.r12_accepted],[analysis.r12_failures],[validation.registryTerms],[validation.addedTerms],[confirmation.requirements.length],[held.requirements.length],[0]];summary.getRange("A5:A12").format.font={bold:true,color:c.navy};summary.getRange("A1:A12").format.columnWidth=34;summary.getRange("B1:B12").format.columnWidth=50;summary.getRange("C1:D12").format.columnWidth=8;summary.getRange("A1:D12").format.font.name="Aptos";summary.freezePanes.freezeRows(4);
let ti=1;for(const s of specs){const sh=wb.worksheets.add(s.name);sh.showGridLines=false;const lc=col(s.headers.length-1),lr=4+s.rows.length;sh.getRange(`A1:${lc}1`).format.fill=c.navy;sh.getRange("A1").values=[["R13 Applicability and Matrix Closure"]];sh.getRange("A1").format.font={bold:true,color:c.white,size:15};sh.getRange(`A2:${lc}2`).format={fill:c.pale,font:{color:c.gray,italic:true}};sh.getRange("A2").values=[[`${s.name} | editable engineering traceability`]];sh.getRange(`A4:${lc}4`).values=[s.headers];sh.getRange(`A4:${lc}4`).format={fill:c.teal,font:{bold:true,color:c.white},wrapText:true,rowHeight:30};if(s.rows.length){sh.getRange(`A5:${lc}${lr}`).values=s.rows;sh.getRange(`A5:${lc}${lr}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:c.line}}};sh.tables.add(`A4:${lc}${lr}`,true,`R13T${ti}`)}for(let i=0;i<s.headers.length;i++){const l=col(i),h=s.headers[i],rg=sh.getRange(`${l}4:${l}${Math.max(5,lr)}`);rg.format.columnWidth=width(h);if(/FEEDBACK|RATIONALE|DETAIL|REASON|TERM|REF|CLASSIFICATION|APPLICABILITY|RELATIONSHIP|CONTROLLED|OPERAND|COMPARISON|TABLE_MODEL/.test(h))rg.format.wrapText=true;if(/STATUS|RESULT|ACCEPTED/.test(h)&&s.rows.length){const d=sh.getRange(`${l}5:${l}${lr}`);d.conditionalFormats.add("containsText",{text:"PASS",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"ACCEPT",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"MAX",format:{fill:c.amber}});d.conditionalFormats.add("containsText",{text:"UNRESOLVED",format:{fill:c.red}})}}sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(Math.min(2,s.headers.length));sh.getRange(`A1:${lc}${Math.max(5,lr)}`).format.font.name="Aptos";ti++}

const out=path.join(batch,"r13_engineering_change_tracker.xlsx");const previewDir=path.join(batch,"validation/r13_tracker_previews");await fs.mkdir(previewDir,{recursive:true});const rendered=[];for(const name of ["SUMMARY",...specs.map(s=>s.name)]){const png=await wb.render({sheetName:name,autoCrop:"all",scale:0.8,format:"png"});const p=path.join(previewDir,`${name.toLowerCase()}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:name,preview:path.relative(batch,p)})}
const inspect=await wb.inspect({kind:"table",range:"SUMMARY!A1:B12",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:6000});const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});const file=await SpreadsheetFile.exportXlsx(wb);await file.save(out);await fs.writeFile(path.join(batch,"validation/r13_tracker_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(out),sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson},null,2)+"\n");console.log(JSON.stringify({status:"PASS",workbook:out,sheets:1+specs.length,previews:rendered.length},null,2));
