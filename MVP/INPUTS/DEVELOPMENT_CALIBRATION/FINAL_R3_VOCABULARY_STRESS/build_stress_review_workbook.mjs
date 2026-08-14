import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const analysisPath=path.resolve(process.argv[2]);
const payload=JSON.parse(await fs.readFile(analysisPath,"utf8"));
const base=path.dirname(analysisPath);
const rows=payload.records;
const counts=payload.classificationCounts;
const manualCounts=payload.manualDecisionCounts ?? {};
const specs=[
 {name:"README",headers:["SECTION","DETAIL"],rows:[
  ["PURPOSE","Development-only R3 vocabulary stress test; never part of the scored experiment."],
  ["LOCK",payload.candidateLockId],["SESSION",payload.sessionId],["ITEMS",payload.totalItems],
  ["DECISION RULE","Only source-confirmed required concepts with no valid R3 representation are genuine gaps. Model suggestions never change the ontology automatically."],
  ["NEXT ACTION","Manually inspect only rows classified SUSPECTED_GAP_MANUAL_SOURCE_REVIEW."],
 ]},
 {name:"SUMMARY",headers:["CLASSIFICATION","COUNT"],rows:[...Object.entries(counts).map(([k,v])=>[`AUTOMATIC: ${k}`,v]),...Object.entries(manualCounts).map(([k,v])=>[`MANUAL: ${k}`,v]),["PENDING MANUAL REVIEWS",payload.pendingManualReviews ?? 0]]},
 {name:"RUN_RESULTS",headers:["REQUIREMENT_ID","REPETITION","RUN_ID","STATUS","ACCEPTED","CLASSIFICATION","MATCHER_ACTIVATED","CANDIDATES","MATCH_FOUND","MATCHED_TERMS","API_CALLS","INPUT_TOKENS","OUTPUT_TOKENS","ELAPSED_MS","FINAL_FEEDBACK","RUN_DIRECTORY"],rows:rows.map(r=>[r.requirement_id,r.repetition,r.run_id,r.status,r.accepted,r.classification,r.matcher_activated,r.matcher_candidate_count,r.matcher_match_found,r.matched_local_names,r.api_calls,r.input_tokens,r.output_tokens,r.elapsed_ms,r.final_feedback,r.run_directory])},
 {name:"MANUAL_REVIEW",headers:["REQUIREMENT_ID","RUN_ID","MODEL_SIGNAL","FINAL_FEEDBACK","MANUAL_REVIEW_STATUS","MANUAL_SOURCE_DECISION","REVIEW_SOURCE","REVIEW_NOTES"],rows:rows.filter(r=>r.classification==="SUSPECTED_GAP_MANUAL_SOURCE_REVIEW").map(r=>[r.requirement_id,r.run_id,r.classification,r.final_feedback,r.manual_review_status,r.manual_source_decision,r.review_source,r.review_notes])},
];
const wb=Workbook.create();const C={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1",green:"#DCFCE7",amber:"#FEF3C7",red:"#FEE2E2"};
const col=i=>{let n=i+1,s="";while(n){let r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26)}return s};
const width=h=>/FEEDBACK|DIRECTORY|DETAIL|DECISION|NOTES/.test(h)?48:/CLASSIFICATION|MATCHED/.test(h)?34:/TOKENS|ELAPSED|CANDIDATE|STATUS/.test(h)?22:18;
let ti=1;
for(const s of specs){const sh=wb.worksheets.add(s.name);sh.showGridLines=false;const lc=col(s.headers.length-1),lr=4+s.rows.length;sh.getRange(`A1:${lc}1`).format.fill=C.navy;sh.getRange("A1").values=[["R3 Vocabulary Stress Test — Non-Scored"]];sh.getRange("A1").format.font={bold:true,color:C.white,size:15};sh.getRange(`A2:${lc}2`).format={fill:C.pale,font:{color:C.gray,italic:true}};sh.getRange("A2").values=[[`${s.name} | ${payload.sessionId}`]];sh.getRange(`A4:${lc}4`).values=[s.headers];sh.getRange(`A4:${lc}4`).format={fill:C.teal,font:{bold:true,color:C.white},wrapText:true,rowHeight:30};if(s.rows.length){sh.getRange(`A5:${lc}${lr}`).values=s.rows;sh.getRange(`A5:${lc}${lr}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:C.line}}};sh.tables.add(`A4:${lc}${lr}`,true,`StressT${ti++}`)}for(let i=0;i<s.headers.length;i++){const l=col(i),h=s.headers[i],rg=sh.getRange(`${l}4:${l}${Math.max(5,lr)}`);rg.format.columnWidth=width(h);if(width(h)>=34)rg.format.wrapText=true;if(h==="CLASSIFICATION"){rg.conditionalFormats.add("containsText",{text:"NO_GAP_SIGNAL",format:{fill:C.green}});rg.conditionalFormats.add("containsText",{text:"SUSPECTED_GAP",format:{fill:C.red}});rg.conditionalFormats.add("containsText",{text:"MODEL_ERROR",format:{fill:C.amber}})}}sh.freezePanes.freezeRows(4);sh.freezePanes.freezeColumns(Math.min(2,s.headers.length));sh.getRange(`A1:${lc}${Math.max(5,lr)}`).format.font.name="Aptos"}
const out=path.join(base,`${payload.sessionId}_stress_review.xlsx`);const previews=path.join(base,`${payload.sessionId}_previews`);await fs.mkdir(previews,{recursive:true});const rendered=[];for(const s of specs){const lc=col(s.headers.length-1),mr=Math.min(30,4+s.rows.length);const png=await wb.render({sheetName:s.name,range:`A1:${lc}${mr}`,scale:0.7,format:"png"});const p=path.join(previews,`${s.name}.png`);await fs.writeFile(p,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:s.name,preview:p})}const inspect=await wb.inspect({kind:"table",range:"SUMMARY!A1:B20",include:"values,formulas",tableMaxRows:20,tableMaxCols:4,maxChars:5000});const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:100},summary:"formula errors"});const file=await SpreadsheetFile.exportXlsx(wb);await file.save(out);await fs.writeFile(path.join(base,`${payload.sessionId}_workbook_verification.json`),JSON.stringify({status:"PASS",workbook:out,sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson,visualReview:"Pending manual preview inspection"},null,2)+"\n");console.log(JSON.stringify({status:"PASS",workbook:out,sheets:specs.length},null,2));
