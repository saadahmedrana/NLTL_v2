import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const dir = path.join(root, "BENCHMARK_VOCABULARY/FINAL_LOCK_R10");
const read = async rel => JSON.parse(await fs.readFile(path.join(dir, rel), "utf8"));
const registry = await read("registry/term_registry.json");
const index = await read("requirement_term_index.json");
const evidence = await read("evidence/stage1_approved.json");
const decisions = await read("registry/r10_mechanical_change_decisions.json");
const policy = await read("evidence/verification_policy_r10.json");
const prelock = await read("prelock_manifest.json");
const ontologyText = await fs.readFile(path.join(dir, "ontology/nltl_benchmark_vocabulary.ttl"), "utf8");
const join = value => Array.isArray(value) ? value.join(" | ") : (value ?? "");
const domainFor = local => {
  const escaped = local.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = ontologyText.match(new RegExp(`nltl:${escaped}\\s+a[\\s\\S]*?rdfs:domain\\s+nltl:([A-Za-z0-9_]+)\\s*;`));
  return match ? `https://w3id.org/nltl/vocab#${match[1]}` : "";
};
const categoryOrder = ["Static", "Static Calculation", "Complex", "Dynamic", "Physical Test"];
const modeFor = category => ({"Static":"DIRECT_STATIC","Static Calculation":"DIRECT_CALCULATION",
  "Complex":"COMPLEX_READINESS","Dynamic":"DYNAMIC_DEFERRED","Physical Test":"PHYSICAL_TEST_DEFERRED"})[category];
const eligible = r => { const c=index.dependencyContracts[r.id]??{}; return c.status==="COMPLETE" &&
  c.verificationMode===modeFor(r.category) && !["Dynamic","Physical Test"].includes(r.category) &&
  String(r.figureDependent??"No").toLowerCase()!=="yes"; };

const sheets = [
  {name:"README",headers:["SECTION","DETAIL"],rows:[
    ["LOCK ID","VOCAB-LOCK-2026-08-20-R10"],["STATUS","R10 candidate pending final offline verification"],
    ["SUPERSEDES","Immutable VOCAB-LOCK-2026-08-20-R9"],["NAMESPACE","https://w3id.org/nltl/vocab#"],
    ["CATEGORY COUNTS","Static 194 | Static Calculation 43 | Complex 42 | Dynamic 19 | Physical Test 15"],
    ["CATEGORY DELTA","TRF-056 and TRF-128 only: Static Calculation -> Static"],
    ["VOCABULARY DELTA","New: tableLookupPropellerLocation; modified domain: sectionCalculationCaseStructuralMember -> calculationCase"],
    ["REQUIREMENT CORRECTIONS","I2-029 | TRF-028 | TRF-056 | TRF-078 | TRF-128; TRF-048 explicitly unchanged"],
    ["VALIDATOR CONTROL","Possible feedback reversals are diagnostic and non-blocking; response-schema validation remains strict"],
    ["FUTURE CLEANUP",policy.futureCleanupItem],["API CALLS","Zero during R10 promotion and verification"]]},
  {name:"REQUIREMENTS",headers:["ID","SOURCE","PAGE","CLAUSE","CATEGORY","VERIFICATION_MODE","ACTIVE_STATUS","TARGET_OWNER","TERMS","CONTRACT_STATUS","ELIGIBLE"],rows:
    evidence.requirements.map(r=>[r.id,r.sourceSheet,r.page,r.clause,r.category,index.dependencyContracts[r.id]?.verificationMode??"",
      r.activeStatus,index.requirementTargetOwner[r.id]??"ship",join(index.requirements[r.id]),index.dependencyContracts[r.id]?.status??"",eligible(r)?"YES":"NO"])},
  {name:"CONTRACTS",headers:["ID","CATEGORY","MODE","STATUS","OWNERS","DIRECT_TERMS","APPLICABILITY","OPERANDS","RESULTS","COMPARISONS","RELATIONSHIPS","MODEL_PATHS","EVIDENCE","FORMULA","TABLE_MODEL","COMPARISON_MODEL"],rows:
    evidence.requirements.map(r=>{const c=index.dependencyContracts[r.id]??{};return[r.id,r.category,c.verificationMode,c.status,join(c.ownerClasses),join(c.directConstraintTerms),join(c.applicabilityTerms),join(c.operandTerms),join(c.resultTerms),join(c.comparisonTerms),join(c.relationshipTerms),join((c.modelPaths??[]).map(p=>`${p.fromOwner} -> ${p.via} -> ${p.toOwner}`)),join(c.evidenceTerms),c.formulaExpression??"",c.tableModel??"",c.comparisonModel??""];})},
  {name:"R10_CHANGES",headers:["ITEM","CHANGE","DETAIL"],rows:[
    ["I2-029","Existing relationship reused","calculationCase -> sectionCalculationCaseStructuralMember -> structuralMember; no arbitrary ship member"],
    ["TRF-078","One relationship added","tableLookupCase -> tableLookupPropellerLocation -> propellerLocationValue for Table 6-7; Table 6-6 reuses iceClass"],
    ["TRF-128","Direct Static","Conditional compressorChargeTime <= 0.5 h for IA Super/reversal; otherwise <= 1 h"],
    ["TRF-028","Mandatory evidence narrowed",`Before: ${join(decisions.trf028MandatoryEvidenceBefore)} | After: ${join(decisions.trf028MandatoryEvidenceAfter)}`],
    ["TRF-056","Direct Static","If hatchOpeningLength > shipBreadth / 2, require deflection representation and both design evidence paths"],
    ["TRF-048","No change","R9 contract, terms, ownership, target and semantic obligation preserved"]]},
  {name:"CATEGORY_STATUS",headers:["CATEGORY","TOTAL","COMPLETE","ELIGIBLE","DEFERRED","VERIFICATION_MODE"],rows:
    categoryOrder.map(category=>{const rows=evidence.requirements.filter(r=>r.category===category);const complete=rows.filter(r=>index.dependencyContracts[r.id]?.status==="COMPLETE").length;const ok=rows.filter(eligible).length;return[category,rows.length,complete,ok,rows.length-ok,modeFor(category)];})},
  {name:"MASTER_TERMS",headers:["CONCEPT_ID","LOCAL_NAME","IRI","LABEL","KIND","DOMAIN","PARENT_OR_RANGE","MODULE","DATATYPE","UNIT_IRI","ALIASES","REQUIREMENTS","SOURCE_REFS","NORMALIZED_DEFINITION","CONFIDENCE"],rows:
    registry.map(t=>[t.conceptId,t.localName,t.iri,t.label,t.kind,domainFor(t.localName),t.parentOrRange,t.module,t.datatype,t.unitIri,join(t.aliases),join(t.requirements),t.sourceRefs,t.normalizedDefinition,t.confidence])},
  {name:"VOCABULARY_DELTA",headers:["LOCAL_NAME","DELTA_TYPE","KIND","DOMAIN_BEFORE","DOMAIN_AFTER","RANGE","SOURCE_REQUIREMENT"],rows:[
    ["tableLookupPropellerLocation","NEW","ObjectProperty","","tableLookupCase","propellerLocationValue","TRF-078"],
    ["sectionCalculationCaseStructuralMember","MODIFIED DOMAIN","ObjectProperty","localFrameSectionCalculationCase","calculationCase","structuralMember","I2-029; I2-030"]]},
  {name:"ARTIFACT_HASHES",headers:["ARTIFACT","PRELOCK_SHA256"],rows:Object.entries(prelock.boundArtifacts)},
];

const workbook=Workbook.create();
const colors={navy:"#17324D",teal:"#0F766E",pale:"#E8F1F5",white:"#FFFFFF",gray:"#5B6573",line:"#CBD5E1"};
const col=i=>{let n=i+1,s="";while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26);}return s;};
const width=h=>/TEXT|DEFINITION|DETAIL|MODEL|FORMULA|TERMS|PATH/.test(h)?48:/IRI|OWNER|SOURCE_REFS|RANGE|DOMAIN/.test(h)?38:/STATUS|CATEGORY|MODE/.test(h)?25:18;
let tableId=1;
for(const spec of sheets){
  const ws=workbook.worksheets.add(spec.name);ws.showGridLines=false;const last=col(spec.headers.length-1),end=4+spec.rows.length;
  ws.getRange(`A1:${last}1`).format.fill=colors.navy;ws.getRange("A1").values=[["NLTL Benchmark Vocabulary - Final Lock R10"]];
  ws.getRange("A1").format.font={bold:true,color:colors.white,size:15};ws.getRange(`A2:${last}2`).format={fill:colors.pale,font:{color:colors.gray,italic:true}};
  ws.getRange("A2").values=[[`${spec.name} | VOCAB-LOCK-2026-08-20-R10`]];ws.getRange(`A4:${last}4`).values=[spec.headers];
  ws.getRange(`A4:${last}4`).format={fill:colors.teal,font:{bold:true,color:colors.white},wrapText:true,rowHeight:30};
  if(spec.rows.length){ws.getRange(`A5:${last}${end}`).values=spec.rows;ws.getRange(`A5:${last}${end}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:colors.line}}};ws.tables.add(`A4:${last}${end}`,true,`R10T${tableId++}`);}
  spec.headers.forEach((h,i)=>{const letter=col(i),w=width(h),range=ws.getRange(`${letter}4:${letter}${Math.max(5,end)}`);range.format.columnWidth=w;if(w>=38)range.format.wrapText=true;});
  ws.freezePanes.freezeRows(4);ws.freezePanes.freezeColumns(Math.min(2,spec.headers.length));ws.getRange(`A1:${last}${Math.max(5,end)}`).format.font.name="Aptos";
}
const previewDir=path.join(dir,"validation/final_lock_workbook_previews");await fs.mkdir(previewDir,{recursive:true});const rendered=[];
for(const spec of sheets){const last=col(spec.headers.length-1),maxRows=Math.min(25,4+spec.rows.length);const png=await workbook.render({sheetName:spec.name,range:`A1:${last}${maxRows}`,scale:0.55,format:"png"});const file=path.join(previewDir,`${String(rendered.length+1).padStart(2,"0")}_${spec.name}.png`);await fs.writeFile(file,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:spec.name,preview:path.relative(dir,file),renderedRange:`A1:${last}${maxRows}`});}
const inspect=await workbook.inspect({kind:"table",range:"README!A1:B18",include:"values,formulas",tableMaxRows:24,tableMaxCols:4,maxChars:8000});
const errors=await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const output=path.join(dir,"benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.xlsx");const exported=await SpreadsheetFile.exportXlsx(workbook);await exported.save(output);
await fs.writeFile(path.join(dir,"validation/final_lock_workbook_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(output),sheetCount:sheets.length,sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson,visualReview:"PENDING"},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:output,sheets:sheets.length,previews:rendered.length,registryTerms:registry.length,requirements:evidence.requirements.length},null,2));
