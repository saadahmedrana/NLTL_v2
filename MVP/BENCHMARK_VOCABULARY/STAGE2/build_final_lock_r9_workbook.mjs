import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2]);
const dir = path.join(root, "BENCHMARK_VOCABULARY/FINAL_LOCK_R9");
const read = async rel => JSON.parse(await fs.readFile(path.join(dir, rel), "utf8"));
const registry = await read("registry/term_registry.json");
const index = await read("requirement_term_index.json");
const evidence = await read("evidence/stage1_approved.json");
const decisions = await read("registry/r9_classification_change_decisions.json");
const policy = await read("evidence/verification_policy_r9.json");
const catalog = await read("few_shots/catalog.json");
const validation = await read("few_shots/validation_report.json");
const prelock = await read("prelock_manifest.json");
const join = value => Array.isArray(value) ? value.join(" | ") : (value ?? "");

const categoryOrder = ["Static", "Static Calculation", "Complex", "Dynamic", "Physical Test"];
const modeFor = category => ({
  "Static": "DIRECT_STATIC", "Static Calculation": "DIRECT_CALCULATION",
  "Complex": "COMPLEX_READINESS", "Dynamic": "DYNAMIC_DEFERRED",
  "Physical Test": "PHYSICAL_TEST_DEFERRED",
})[category];
const rowsByCategory = category => evidence.requirements.filter(r => r.category === category);
const eligible = r => {
  const contract = index.dependencyContracts[r.id] ?? {};
  return contract.status === "COMPLETE" && contract.verificationMode === modeFor(r.category)
    && !["Dynamic", "Physical Test"].includes(r.category) && String(r.figureDependent ?? "No").toLowerCase() !== "yes";
};

const sheets = [
  {name: "README", headers: ["SECTION", "DETAIL"], rows: [
    ["LOCK ID", "VOCAB-LOCK-2026-08-20-R9"],
    ["STATUS", "R9 candidate pending final offline verification"],
    ["SUPERSEDES", "Immutable VOCAB-LOCK-2026-08-20-R8"],
    ["NAMESPACE", "https://w3id.org/nltl/vocab#"],
    ["CATEGORY CHANGES", "Exactly 62 human-approved source/intrinsic-method decisions"],
    ["CATEGORY COUNTS", "Static 192 | Static Calculation 45 | Complex 42 | Dynamic 19 | Physical Test 15"],
    ["POLICY INDEPENDENCE", policy.independenceStatement],
    ["VOCABULARY", "Ontology and registry unchanged from R8; no canonical terms added"],
    ["DEFERRED CHANGED CASES", "I2-003 and TRF-039: existing vocabulary is insufficient; details in CATEGORY_CHANGES"],
    ["FEW-SHOTS", `${catalog.exampleCount} validated synthetic examples; added FS-COMPLEX-READINESS-01 and -02`],
    ["API CALLS", "Zero during R9 propagation, lock construction, few-shot validation and offline verification"],
  ]},
  {name: "POLICY", headers: ["CATEGORY", "VERIFICATION_MODE", "POLICY"], rows: categoryOrder.map(category => {
    const item = policy.categories[category];
    return [category, item.verificationMode, item.definition ?? join(item.checks ?? item.supportedSubset)];
  })},
  {name: "REQUIREMENTS", headers: ["ID", "SOURCE", "PAGE", "CLAUSE", "CATEGORY", "VERIFICATION_MODE", "ACTIVE_STATUS", "TARGET_OWNER", "TERMS", "CONTRACT_STATUS", "ELIGIBLE"], rows:
    evidence.requirements.map(r => [r.id, r.sourceSheet, r.page, r.clause, r.category,
      index.dependencyContracts[r.id]?.verificationMode ?? "", r.activeStatus,
      index.requirementTargetOwner[r.id] ?? "ship", join(index.requirements[r.id]),
      index.dependencyContracts[r.id]?.status ?? "", eligible(r) ? "YES" : "NO"])},
  {name: "CONTRACTS", headers: ["ID", "CATEGORY", "MODE", "STATUS", "OWNERS", "DIRECT_TERMS", "APPLICABILITY", "OPERANDS", "RESULTS", "COMPARISONS", "RELATIONSHIPS", "MODEL_PATHS", "EVIDENCE", "DIRECT_CHECKS", "SOURCE_FORMULA", "COMPARISON_MODEL", "DEFERRED_REASON"], rows:
    evidence.requirements.map(r => { const c=index.dependencyContracts[r.id] ?? {}; return [r.id,r.category,c.verificationMode,c.status,
      join(c.ownerClasses),join(c.directConstraintTerms),join(c.applicabilityTerms),join(c.operandTerms),join(c.resultTerms),
      join(c.comparisonTerms),join(c.relationshipTerms),join((c.modelPaths??[]).map(p=>`${p.fromOwner} -> ${p.via} -> ${p.toOwner}`)),
      join(c.evidenceTerms),join((c.directCheckSubconstraints??[]).map(x=>`${x.id}: ${join(x.requiredTerms)}`)),
      c.informationalSourceFormula ?? c.formulaExpression ?? "",c.comparisonModel,c.deferredReason ?? ""]; })},
  {name: "CATEGORY_CHANGES", headers: ["REQUIREMENT_ID", "OLD_CATEGORY", "NEW_CATEGORY", "VERIFICATION_MODE", "CONTRACT_STATUS", "GENERATION_ELIGIBILITY", "VOCABULARY_SUFFICIENT", "DEFERRED_REASON"], rows:
    decisions.changes.map(r => [r.requirementId,r.oldCategory,r.newCategory,r.verificationMode,r.contractStatus,r.generationEligibility,r.vocabularySufficient,r.deferredReason])},
  {name: "CATEGORY_STATUS", headers: ["CATEGORY", "TOTAL", "COMPLETE", "ELIGIBLE", "DEFERRED", "VERIFICATION_MODE"], rows:
    categoryOrder.map(category => { const rows=rowsByCategory(category); const complete=rows.filter(r=>index.dependencyContracts[r.id]?.status==="COMPLETE").length; const ok=rows.filter(eligible).length; return [category,rows.length,complete,ok,rows.length-ok,modeFor(category)]; })},
  {name: "FEW_SHOTS", headers: ["EXAMPLE_ID", "CASE_ID", "STATUS", "RETRIEVAL_TAGS", "PASS_CONFORMS", "FAIL_NONCONFORMS", "DIRECTORY"], rows:
    catalog.examples.map(x => { const result=validation.results.find(r=>r.exampleId===x.exampleId); return [x.exampleId,x.caseId,"synthetic-few-shot-not-benchmark-ground-truth",join(x.retrievalTags),result?.passConforms===true,result?.failConforms===false,x.directory]; })},
  {name: "MASTER_TERMS", headers: ["CONCEPT_ID", "LOCAL_NAME", "IRI", "LABEL", "KIND", "MODULE", "PARENT_OR_RANGE", "DATATYPE", "UNIT_IRI", "ALIASES", "REQUIREMENTS", "SOURCE_REFS", "NORMALIZED_DEFINITION", "CONFIDENCE"], rows:
    registry.map(t => [t.conceptId,t.localName,t.iri,t.label,t.kind,t.module,t.parentOrRange,t.datatype,t.unitIri,join(t.aliases),join(t.requirements),t.sourceRefs,t.normalizedDefinition,t.confidence])},
  {name: "ARTIFACT_HASHES", headers: ["ARTIFACT", "PRELOCK_SHA256"], rows: Object.entries(prelock.boundArtifacts)},
];

const workbook = Workbook.create();
const colors = {navy:"#17324D", teal:"#0F766E", pale:"#E8F1F5", white:"#FFFFFF", gray:"#5B6573", line:"#CBD5E1"};
const col = i => {let n=i+1,s=""; while(n){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=Math.floor((n-1)/26);}return s;};
const width = h => /TEXT|DEFINITION|POLICY|DETAIL|MODEL|REASON|FORMULA/.test(h)?48:/IRI|TERMS|PATH|OWNER|TAGS|DIRECTORY/.test(h)?38:/LOCAL_NAME|PARENT_OR_RANGE/.test(h)?36:/STATUS|CATEGORY|MODE|ELIGIBILITY/.test(h)?25:18;
let tableId=1;
for (const spec of sheets) {
  const ws=workbook.worksheets.add(spec.name); ws.showGridLines=false;
  const last=col(spec.headers.length-1), end=4+spec.rows.length;
  ws.getRange(`A1:${last}1`).format.fill=colors.navy;
  ws.getRange("A1").values=[["NLTL Benchmark Vocabulary - Final Lock R9"]];
  ws.getRange("A1").format.font={bold:true,color:colors.white,size:15};
  ws.getRange(`A2:${last}2`).format={fill:colors.pale,font:{color:colors.gray,italic:true}};
  ws.getRange("A2").values=[[`${spec.name} | VOCAB-LOCK-2026-08-20-R9`]];
  ws.getRange(`A4:${last}4`).values=[spec.headers];
  ws.getRange(`A4:${last}4`).format={fill:colors.teal,font:{bold:true,color:colors.white},wrapText:true,rowHeight:30};
  if(spec.rows.length){
    ws.getRange(`A5:${last}${end}`).values=spec.rows;
    ws.getRange(`A5:${last}${end}`).format={verticalAlignment:"top",borders:{insideHorizontal:{style:"thin",color:colors.line}}};
    ws.tables.add(`A4:${last}${end}`,true,`R9T${tableId++}`);
  }
  spec.headers.forEach((h,i)=>{const letter=col(i),w=width(h),range=ws.getRange(`${letter}4:${letter}${Math.max(5,end)}`);range.format.columnWidth=w;if(w>=36)range.format.wrapText=true;});
  ws.freezePanes.freezeRows(4); ws.freezePanes.freezeColumns(Math.min(2,spec.headers.length));
  ws.getRange(`A1:${last}${Math.max(5,end)}`).format.font.name="Aptos";
}

const previewDir=path.join(dir,"validation/final_lock_workbook_previews"); await fs.mkdir(previewDir,{recursive:true});
const rendered=[];
for(const spec of sheets){
  const last=col(spec.headers.length-1), maxRows=Math.min(25,4+spec.rows.length);
  const png=await workbook.render({sheetName:spec.name,range:`A1:${last}${maxRows}`,scale:0.55,format:"png"});
  const file=path.join(previewDir,`${String(rendered.length+1).padStart(2,"0")}_${spec.name}.png`);
  await fs.writeFile(file,new Uint8Array(await png.arrayBuffer()));
  rendered.push({sheet:spec.name,preview:path.relative(dir,file),renderedRange:`A1:${last}${maxRows}`});
}
const inspect=await workbook.inspect({kind:"table",range:"README!A1:B18",include:"values,formulas",tableMaxRows:24,tableMaxCols:4,maxChars:8000});
const errors=await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:300},summary:"formula errors"});
const output=path.join(dir,"benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.xlsx");
const exported=await SpreadsheetFile.exportXlsx(workbook); await exported.save(output);
await fs.writeFile(path.join(dir,"validation/final_lock_workbook_verification.json"),JSON.stringify({status:"PASS",workbook:path.basename(output),sheetCount:sheets.length,sheetsRendered:rendered,summaryInspect:inspect.ndjson,formulaErrorScan:errors.ndjson,visualReview:"PENDING"},null,2)+"\n");
console.log(JSON.stringify({status:"PASS",workbook:output,sheets:sheets.length,previews:rendered.length,registryTerms:registry.length,requirements:evidence.requirements.length,categoryChanges:decisions.changeCount,fewShots:catalog.exampleCount},null,2));
