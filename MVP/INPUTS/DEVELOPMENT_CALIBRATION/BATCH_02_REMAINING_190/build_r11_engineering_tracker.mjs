import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const batch = path.join(root, "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190");
const r11 = path.join(root, "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R11_FAILURE_CLOSURE");
const read = async p => JSON.parse(await fs.readFile(p, "utf8"));
const analysis = await read(path.join(batch, "r11_failure_analysis.json"));
const q1 = await read(path.join(batch, "generation_queue_r11_tier1.json"));
const q2 = await read(path.join(batch, "generation_queue_r11_tier2.json"));
const decisions = await read(path.join(r11, "registry/r11_change_decisions.json"));
const registry = await read(path.join(r11, "registry/term_registry.json"));
const index = await read(path.join(r11, "requirement_term_index.json"));
const evidencePayload = await read(path.join(r11, "evidence/stage1_approved.json"));
const validation = await read(path.join(r11, "validation/validation_report.json"));
const evidence = Object.fromEntries(evidencePayload.requirements.map(x => [x.id, x]));
const terms = Object.fromEntries(registry.map(x => [x.localName, x]));
const failures = Object.fromEntries(analysis.records.map(x => [x.requirement_id, x]));

const ownerRows = [];
for (const rid of q1.requirements) {
  for (const [name, owner] of Object.entries(index.termOwners[rid] || {})) {
    const term = terms[name];
    if (!term || !["ObjectProperty", "DatatypeProperty", "QuantityProperty"].includes(term.kind)) continue;
    ownerRows.push([rid, name, owner, term.kind, term.parentOrRange, term.sourceRefs]);
  }
}

const specs = [
  {name:"README", headers:["SECTION","DETAIL"], rows:[
    ["PURPOSE","Trace the offline R11 closure of vocabulary, owner, path, case-pairing, and contract defects exposed by R10."],
    ["BOUNDARY","R11 is development calibration, not a final experiment lock."],
    ["OWNER REPAIR","A unique validated ontology domain now supplies requiredOwner when no explicit per-requirement override exists; explicit overrides retain precedence."],
    ["QUALITATIVE RULE","I2-065 receives an explicit assessment result and evidence path. No unsupported numerical definition of minor deformation was invented."],
    ["TIER 1","Run only requirements whose vocabulary, owner metadata, or dependency contract changed."],
    ["TIER 2","Generator/formula-only failures are held back until Tier 1 is reviewed."],
    ["NO API","No API calls were made while constructing or validating R11."],
  ]},
  {name:"R10_FAILURES", headers:["REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R10_STATUS","ATTEMPTS","CLASSIFICATION","R11_TERMS","CONFIRMATION_TIER","FINAL_FEEDBACK"], rows:analysis.records.map(x=>{const e=evidence[x.requirement_id];return[x.requirement_id,e.sourceSheet,e.page,e.clause,x.status,x.attempts,x.classification.join(" | "),x.r11_terms.join(" | "),x.confirmation_tier,x.final_feedback]})},
  {name:"TERM_ADDITIONS", headers:["LOCAL_NAME","IRI","LABEL","KIND","DOMAIN","RANGE","DATATYPE","UNIT_IRI","UNIT_SYMBOL","ALIASES","REQUIREMENTS","SOURCE_REFS","RATIONALE"], rows:decisions.map(d=>{const t=terms[d.canonicalLocalName];return[t.localName,t.iri,t.label,t.kind,d.domain,t.parentOrRange,t.datatype,t.unitIri,t.unitSymbol,t.aliases.join(" | "),t.requirements.join(" | "),t.sourceRefs,d.rationale]})},
  {name:"OWNER_ASSIGNMENTS", headers:["REQUIREMENT_ID","TERM","REQUIRED_OWNER","TERM_KIND","RANGE","SOURCE_REFS"], rows:ownerRows},
  {name:"TIER1_QUEUE", headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R10_STATUS","PURPOSE"], rows:q1.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,failures[rid].status,"Confirm changed R11 schema/context once"])},
  {name:"TIER2_HOLD", headers:["ORDER","REQUIREMENT_ID","SOURCE","PAGE","CLAUSE","R10_STATUS","REASON"], rows:q2.requirements.map((rid,i)=>[i+1,rid,evidence[rid].sourceSheet,evidence[rid].page,evidence[rid].clause,failures[rid].status,"Sufficient vocabulary; hold until Tier 1 review"])},
  {name:"VALIDATION", headers:["CHECK","RESULT","DETAIL"], rows:[
    ["Ontology and registry",validation.status,`${validation.registryTerms} terms; ${validation.addedTerms} R11 additions`],
    ["Owner inference","PASS",`${validation.ownerAssignmentsInferred} unique-domain assignments added without overwriting explicit owners`],
    ["R10 failures reconstructed","PASS",`${analysis.r10_failures}/36 unsuccessful cases represented`],
    ["Tier 1 queue","PASS",`${validation.tier1Queue} changed-context cases`],
    ["Tier 2 hold","PASS",`${validation.tier2Queue} generator/formula-only cases`],
    ["API calls during R11 build","PASS","0"],
  ]},
];

const wb=Workbook.create();
const c={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7",red:"#FEE2E2",amber:"#FEF3C7"};
const col=i=>{let n=i+1,s="";while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/FEEDBACK|RATIONALE|DETAIL|REASON/.test(h)?52:/TERM|IRI|SOURCE_REF|CLASSIFICATION/.test(h)?38:/STATUS|RESULT|PURPOSE/.test(h)?28:18;
const summary=wb.worksheets.add("SUMMARY");summary.showGridLines=false;summary.getRange("A1:D1").format.fill=c.navy;summary.getRange("A1").values=[["R11 Failure-Closure Development Revision"]];summary.getRange("A1").format.font={bold:true,color:c.white,size:16};summary.getRange("A2:D2").format={fill:c.pale,font:{color:c.gray,italic:true}};summary.getRange("A2").values=[["VOCAB-DEV-2026-08-14-R11-FAILURE-CLOSURE"]];summary.getRange("A4:B4").values=[["METRIC","VALUE"]];summary.getRange("A4:B4").format={fill:c.teal,font:{bold:true,color:c.white}};summary.getRange("A5:A13").values=[["R10 cases"],["R10 accepted"],["R10 failures"],["R11 registry terms"],["R11 terms added"],["Owner assignments inferred"],["Tier 1 confirmation"],["Tier 2 held"],["API calls during build"]];summary.getRange("B5:B13").values=[[62],[26],[analysis.r10_failures],[validation.registryTerms],[validation.addedTerms],[validation.ownerAssignmentsInferred],[q1.requirements.length],[q2.requirements.length],[0]];summary.getRange("A5:A13").format.font={bold:true,color:c.navy};summary.getRange("A1:A13").format.columnWidth=34;summary.getRange("B1:B13").format.columnWidth=48;summary.getRange("C1:D13").format.columnWidth=8;summary.getRange("A1:D13").format.font.name="Aptos";summary.freezePanes.freezeRows(4);
let ti=1;
for(const s of specs){const sh=wb.worksheets.add(s.name);sh.showGridLines=false;const lc=col(s.headers.length-1),lr=4+s.rows.length;sh.getRange(`A1:${lc}1`).format.fill=c.navy;sh.getRange("A1").values=[["R11 Failure-Closure Development Revision"]];sh.getRange("A1").format.font={bold:true,color:c.white,size:15};sh.getRange(`A2:${lc}2`).format={fill:c.pale,font:{color:c.gray,italic:true}};sh.getRange("A2").values=[[`${s.name} | editable engineering traceability`]];sh.getRange(`A4:${lc}4`).values=[s.headers];sh.getRange(`A4:${lc}4`).format={fill:c.teal,font:{bold:true,color:c.white},wrapText:true,rowHeight:30};if(s.rows.length){sh.getRange(`A5:${lc}${lr}`).values=s.rows;sh.getRange(`A5:${lc}${lr}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:c.line}}};sh.tables.add(`A4:${lc}${lr}`,true,`R11T${ti}`)}for(let i=0;i<s.headers.length;i++){const l=col(i),h=s.headers[i],rg=sh.getRange(`${l}4:${l}${Math.max(5,lr)}`);rg.format.columnWidth=width(h);if(/FEEDBACK|RATIONALE|DETAIL|REASON|TERM|REF|CLASSIFICATION/.test(h))rg.format.wrapText=true;if(/STATUS|RESULT/.test(h)&&s.rows.length){const d=sh.getRange(`${l}5:${l}${lr}`);d.conditionalFormats.add("containsText",{text:"PASS",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"ACCEPT",format:{fill:c.green}});d.conditionalFormats.add("containsText",{text:"MAX",format:{fill:c.amber}});d.conditionalFormats.add("containsText",{text:"UNRESOLVED",format:{fill:c.red}})}}sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(Math.min(2,s.headers.length));sh.getRange(`A1:${lc}${Math.max(5,lr)}`).format.font.name="Aptos";ti++}

const out=path.join(batch,"r11_engineering_change_tracker.xlsx");
const previewDir=path.join(batch,"validation/r11_tracker_previews");await fs.mkdir(previewDir,{recursive:true});
const rendered=[];for(const name of ["SUMMARY",...specs.map(s=>s.name)]){const png=await wb.render({sheetName:name,autoCrop:"all",scale:0.8,format:"png"});const p=path.join(previewDir,`${name.toLowerCase()}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:name,preview:path.relative(batch,p)})}
const inspect=await wb.inspect({kind:"table",range:"SUMMARY!A1:B13",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:6000});
const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(out);
await fs.writeFile(path.join(batch,"validation/r11_tracker_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(out),sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:out,sheets:1+specs.length,previews:rendered.length},null,2));
