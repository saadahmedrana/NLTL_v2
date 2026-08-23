from __future__ import annotations

import csv, hashlib, json, shutil
from collections import Counter
from pathlib import Path
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS, XSD

MVP=Path(__file__).resolve().parents[2]; PIPE=MVP/"SHACL_GENERATION_PIPELINE"
SOURCE=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R12"; TARGET=MVP/"BENCHMARK_VOCABULARY/FINAL_LOCK_R13"
SOURCE_LOCK_ID="VOCAB-LOCK-2026-08-21-R12"; LOCK_ID="VOCAB-LOCK-2026-08-22-R13"
CANONICAL="https://w3id.org/nltl/vocab#"; NLTL=Namespace(CANONICAL)
EXPECTED_COUNTS={"Static":191,"Static Calculation":43,"Complex":45,"Dynamic":19,"Physical Test":15}
GRADE_RANKS={"steelGradeB":("B",1,"normalStrengthSteelCategory"),"steelGradeD":("D",2,"normalStrengthSteelCategory"),"steelGradeE":("E",3,"normalStrengthSteelCategory"),"steelGradeAh":("AH",1,"highTensileSteelCategory"),"steelGradeDh":("DH",2,"highTensileSteelCategory"),"steelGradeEh":("EH",3,"highTensileSteelCategory"),"steelGradeFh":("FH",4,"highTensileSteelCategory")}
NEW_TERMS=tuple(GRADE_RANKS)+("traficomTable6Dash14",)

def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def write(p,v): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=True)+"\n",encoding="utf-8")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def immutable_manifest():
    roots=[SOURCE,MVP/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R12.xlsx",MVP/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R12.lock.json",MVP/"benchmark_vocabulary_stage2_LOCK-2026-08-21-R12.sha256"]; files={}
    for root in roots:
        candidates=[root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in candidates: files[str(p.relative_to(MVP))]=sha(p)
    aggregate=hashlib.sha256("\n".join(f"{h}  {n}" for n,h in sorted(files.items())).encode()).hexdigest()
    return {"sourceLockId":SOURCE_LOCK_ID,"fileCount":len(files),"aggregateSha256":aggregate,"files":files}

def new_term(local,label,parent,concept,module,requirement,evidence,definition):
    return {"aliases":[],"conceptId":concept,"confidence":"High","datatype":"","evidenceExcerpt":evidence,"haithamUri":"","iri":CANONICAL+local,"kind":"NamedIndividual","label":label,"localName":local,"mappingStatus":"No external equivalence claimed; source-grounded R13 controlled value.","module":module,"nameQaStatus":"Passed - ASCII-only lowerCamelCase and collision review","namingBasis":"Human-approved source table value and existing controlled-value class","namingRule":"N4 - ASCII lowerCamelCase controlled value preserving source notation in label.","normalizedDefinition":definition,"parentOrRange":CANONICAL+parent,"quantityKindLabel":"","requirements":[requirement],"roleDecision":"Controlled regulatory value","sourceConceptIds":[concept],"sourceRefs":requirement,"stage1LocalNames":[local],"stage2UnitEvidence":"","unitDecisionStatus":"Not a quantity property","unitIri":"","unitSymbol":""}

def table8_model():
    columns=[("I_PC1_5","steelMaterialClassOne","PC1-5"),("I_PC6_7","steelMaterialClassOne","PC6-7"),("II_PC1_5","steelMaterialClassTwo","PC1-5"),("II_PC6_7","steelMaterialClassTwo","PC6-7"),("III_PC1_3","steelMaterialClassThree","PC1-3"),("III_PC4_5","steelMaterialClassThree","PC4-5"),("III_PC6_7","steelMaterialClassThree","PC6-7")]
    rows=[
      (None,10,["B/AH","B/AH","B/AH","B/AH","E/EH","E/EH","B/AH"]),
      (10,15,["B/AH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"]),
      (15,20,["D/DH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"]),
      (20,25,["D/DH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"]),
      (25,30,["D/DH","B/AH","E/EH","D/DH","E/EH","E/EH","E/EH"]),
      (30,35,["D/DH","B/AH","E/EH","D/DH","E/EH","E/EH","E/EH"]),
      (35,40,["D/DH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","E/EH","E/EH"]),
      (40,45,["E/EH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","E/EH","E/EH"]),
      (45,50,["E/EH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","NOT_APPLICABLE/FH","E/EH"]),
    ]
    grade={"B":"steelGradeB","D":"steelGradeD","E":"steelGradeE","AH":"steelGradeAh","DH":"steelGradeDh","EH":"steelGradeEh","FH":"steelGradeFh"}
    structured=[]
    for lower,upper,values in rows:
        selections=[]
        for (_,material,pcs),pair in zip(columns,values):
            normal,high=pair.split("/")
            selections.append({"steelMaterialClass":material,"polarClassGroup":pcs,"steelStrengthCategory":"normalStrengthSteelCategory","requiredGrade":grade.get(normal),"applicable":normal!="NOT_APPLICABLE"})
            selections.append({"steelMaterialClass":material,"polarClassGroup":pcs,"steelStrengthCategory":"highTensileSteelCategory","requiredGrade":grade[high],"applicable":True})
        structured.append({"thicknessBand":{"lowerExclusiveMm":lower,"upperInclusiveMm":upper},"selections":selections})
    return {"structured":True,"canonicalTableReference":"iacsUrI2Table8","referenceProperty":"tableReference","selectors":["asBuiltPlateThickness","polarClass","steelMaterialClass","steelStrengthCategory"],"resultTerm":"requiredHullStructuralSteelGrade","thicknessUnit":"http://qudt.org/vocab/unit/MilliM","polarClassGroups":["PC1-3","PC1-5","PC4-5","PC6-7"],"gradeFamilies":{"normalStrengthSteelCategory":{"steelGradeB":1,"steelGradeD":2,"steelGradeE":3},"highTensileSteelCategory":{"steelGradeAh":1,"steelGradeDh":2,"steelGradeEh":3,"steelGradeFh":4}},"notApplicableMarker":"NOT_APPLICABLE","notApplicableIsGrade":False,"rows":structured}

def main():
    if TARGET.exists(): raise FileExistsError(f"Refusing to overwrite existing R13 directory: {TARGET}")
    provenance=immutable_manifest()
    for d in ("context","evidence","few_shots","ontology","registry"): shutil.copytree(SOURCE/d,TARGET/d)
    shutil.copy2(SOURCE/"requirement_term_index.json",TARGET/"requirement_term_index.json"); (TARGET/"provenance").mkdir(parents=True); (TARGET/"validation").mkdir(parents=True)
    evidence=read(TARGET/"evidence/stage1_approved.json"); by={r["id"]:r for r in evidence["requirements"]}; index=read(TARGET/"requirement_term_index.json"); registry=read(TARGET/"registry/term_registry.json"); old_registry={t["localName"]:t for t in registry}
    excerpt=by["I2-048"]["sourceText"]; additions=[]
    for i,(local,(label,rank,family)) in enumerate(GRADE_RANKS.items(),1): additions.append(new_term(local,label,"steelGradeValue",f"VOC-R13-{i:04d}","hull","I2-048",excerpt,f"NORMALIZED (R13): IACS UR I2 Table 8 steel grade {label}, ranked {rank} only within {family}."))
    additions.append(new_term("traficomTable6Dash14","TRAFICOM Table 6-14","tableReferenceValue","VOC-R13-0008","regulation","TRF-109",by["TRF-109"]["sourceText"],"NORMALIZED (R13): controlled reference to TRAFICOM Table 6-14, Parameters for rho determination."))
    if len(additions)!=8 or set(NEW_TERMS)&set(old_registry): raise RuntimeError("R13 new-term inventory differs from exactly eight authorized additions")
    registry.extend(additions); registry.sort(key=lambda t:t["localName"])
    assessment=next(t for t in registry if t["localName"]=="assessmentDate"); assessment["requirements"]=sorted(set(assessment.get("requirements",[]))|{"TRF-014"}); assessment["sourceRefs"]=(assessment.get("sourceRefs","")+"; TRF-014 | TRAFICOM 3.2.2").strip("; "); assessment["normalizedDefinition"]="NORMALIZED (R13 provenance extension): supplied deterministic assessment date, including TRF-014 deadline evaluation; never wall-clock time."
    graph=Graph().parse(TARGET/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle")
    for item in additions:
        iri=URIRef(item["iri"]); graph.add((iri,RDF.type,OWL.NamedIndividual)); graph.add((iri,RDF.type,URIRef(item["parentOrRange"]))); graph.add((iri,RDF.type,SKOS.Concept)); graph.add((iri,RDFS.label,Literal(item["label"],lang="en"))); graph.add((iri,SKOS.prefLabel,Literal(item["label"],lang="en"))); graph.add((iri,SKOS.definition,Literal(item["normalizedDefinition"],lang="en"))); graph.add((iri,NLTL.draftConceptId,Literal(item["conceptId"]))); graph.add((iri,NLTL.sourceRequirementId,Literal(item["requirements"][0])))
    for local,(_,rank,_) in GRADE_RANKS.items(): graph.add((NLTL[local],NLTL.steelGradeOrderRank,Literal(rank,datatype=XSD.integer)))
    graph.add((NLTL.assessmentDate,NLTL.sourceRequirementId,Literal("TRF-014")))
    graph.serialize(TARGET/"ontology/nltl_benchmark_vocabulary.ttl",format="turtle"); graph.serialize(TARGET/"ontology/nltl_benchmark_vocabulary.rdf",format="xml")
    context=read(TARGET/"context/nltl_benchmark_context.jsonld")
    for local in NEW_TERMS: context["@context"][local]="nltl:"+local
    context["@context"]=dict(sorted(context["@context"].items())); write(TARGET/"context/nltl_benchmark_context.jsonld",context)

    # I2-048: existing case, exact Table 8 matrix, family-scoped rank comparison, no lookup evidence/parallel generic case.
    rid="I2-048"; grades=list(GRADE_RANKS); terms={"ship","polarClass","hasSteelGradeRequirementCase","steelGradeRequirementCase","steelGradeRequirementCasePlating","plating","tableReference","iacsUrI2Table8","asBuiltPlateThickness","steelMaterialClass","steelMaterialClassValue","steelMaterialClassOne","steelMaterialClassTwo","steelMaterialClassThree","steelStrengthCategory","steelStrengthCategoryValue","normalStrengthSteelCategory","highTensileSteelCategory","actualHullStructuralSteelGrade","requiredHullStructuralSteelGrade","steelGradeValue","steelGradeOrderRank",*grades}
    index["requirements"][rid]=sorted(terms); index["termOwners"][rid]={"polarClass":"ship","hasSteelGradeRequirementCase":"ship","steelGradeRequirementCasePlating":"steelGradeRequirementCase","tableReference":"steelGradeRequirementCase","asBuiltPlateThickness":"steelGradeRequirementCase","steelMaterialClass":"steelGradeRequirementCase","steelStrengthCategory":"steelGradeRequirementCase","actualHullStructuralSteelGrade":"steelGradeRequirementCase","requiredHullStructuralSteelGrade":"steelGradeRequirementCase","steelGradeOrderRank":"steelGradeValue"}
    obligation="For every represented steelGradeRequirementCase, select the exact required grade from iacsUrI2Table8 using ship polarClass plus case asBuiltPlateThickness, steelMaterialClass and steelStrengthCategory. Missing selectors or an applicable selection without a required grade fail. The actual grade must have rank greater than or equal to the required grade only within the same steelStrengthCategory; NOT_APPLICABLE combinations impose no grade result."
    index["semanticObligations"][rid]=[obligation]
    c=index["dependencyContracts"][rid]; c.update(schemaVersion=2,engineeringDecision="R13_EXACT_IACS_TABLE8_EXISTING_CASE_MODEL",encodingPattern="Structured deterministic table selection plus family-scoped rank comparison",applicabilityTerms=["polarClass","asBuiltPlateThickness","steelMaterialClass","steelStrengthCategory"],operandTerms=["polarClass","asBuiltPlateThickness","steelMaterialClass","steelStrengthCategory"],resultTerms=["requiredHullStructuralSteelGrade"],comparisonTerms=["actualHullStructuralSteelGrade","requiredHullStructuralSteelGrade","steelGradeOrderRank"],controlledValueTerms=sorted(["iacsUrI2Table8","steelMaterialClassOne","steelMaterialClassTwo","steelMaterialClassThree","normalStrengthSteelCategory","highTensileSteelCategory",*grades]),directConstraintTerms=sorted(terms),relationshipTerms=["hasSteelGradeRequirementCase","steelGradeRequirementCasePlating","tableReference","polarClass","steelMaterialClass","steelStrengthCategory","actualHullStructuralSteelGrade","requiredHullStructuralSteelGrade"],evidenceTerms=[],ownerClasses=["ship","steelGradeRequirementCase","plating","steelGradeValue"],modelPaths=[{"fromOwner":"ship","via":"hasSteelGradeRequirementCase","toOwner":"steelGradeRequirementCase"},{"fromOwner":"steelGradeRequirementCase","via":"steelGradeRequirementCasePlating","toOwner":"plating"},{"fromOwner":"steelGradeRequirementCase","via":"tableReference","toOwner":"tableReferenceValue"},{"fromOwner":"steelGradeRequirementCase","via":"actualHullStructuralSteelGrade","toOwner":"steelGradeValue"},{"fromOwner":"steelGradeRequirementCase","via":"requiredHullStructuralSteelGrade","toOwner":"steelGradeValue"},{"fromOwner":"ship","via":"polarClass","toOwner":"polarClassValue"}],tableModel=table8_model(),comparisonModel=obligation,cardinalityPolicies={"tableReference":{"minCount":1,"maxCount":1,"hasValue":"iacsUrI2Table8"},"steelGradeRequirementCasePlating":{"minCount":1,"maxCount":1},"asBuiltPlateThickness":{"minCount":1,"maxCount":1},"steelMaterialClass":{"minCount":1,"maxCount":1},"steelStrengthCategory":{"minCount":1,"maxCount":1},"requiredHullStructuralSteelGrade":{"minCount":1,"maxCount":1,"whenApplicable":True},"actualHullStructuralSteelGrade":{"minCount":1,"maxCount":1}},universalScopePolicy="Validate every represented steelGradeRequirementCase; do not impose independent top-level case existence.",topLevelCaseMinCount=0,requiredModelFields=["verificationMode","comparisonModel","tableModel","operandTerms","resultTerms","relationshipTerms","modelPaths"])
    for stale in ("asBuiltThickness","materialClass","steelGrade","hasTableLookupCase","lookupSelectionEvidence"):
        for field in ("legacyIndexedTerms",):
            if isinstance(c.get(field),list): c[field]=[x for x in c[field] if x!=stale]

    # Approval strings: exact source-authorized alternatives, with distinct A/B and Category C policies.
    authority=["Administration","recognized organization accepted by the Administration"]; standard_ab=["standard acceptable to the Organization","another standard offering an equivalent level of safety"]; standard_c=["acceptable standard adequate for operating ice type and concentration"]
    for rid,subject in (("IMO-031","exposed-structure material"),("IMO-048","exposed machinery or foundation material")):
        c=index["dependencyContracts"][rid]; c["stringValuePolicies"]={"approvingAuthority":authority,"approvalStandard":standard_ab}; c["approvalBranchPolicies"]={"applicableApproval":{"approvingAuthority":authority,"approvalStandard":standard_ab,"preservePolarServiceTemperatureBasis":True}}; c["comparisonModel"]=f"Every applicable {subject} approval uses approvingAuthority equal to one of the two authorized alternatives and approvalStandard equal to an Organization-acceptable or equivalent-safety alternative, preserving the polarServiceTemperature basis."; c["engineeringDecision"]="R13_CONTROLLED_APPROVAL_STRINGS"
        index["semanticObligations"][rid]=[c["comparisonModel"]]
    for rid,component in (("IMO-032",False),("IMO-049",True)):
        c=index["dependencyContracts"][rid]; c["stringValuePolicies"]={"approvingAuthority":authority}; c["approvalBranchPolicies"]={"categoryAOrB":{"approvingAuthority":authority,"approvalStandard":standard_ab},"iceStrengthenedCategoryC":{"approvingAuthority":authority,"approvalStandard":standard_c,"requiredContext":["operatingIceType","operatingIceConcentration"],"equivalentSafetyAlternativeAllowed":False}}; subject="each applicable machinery component approvalRecord" if component else "the applicable ship approvalRecord"; c["comparisonModel"]=f"For {subject}: Category A/B uses an authorized authority and an Organization-acceptable or equivalent-safety standard; ice-strengthened Category C uses an authorized authority and an acceptable standard adequate for operatingIceType and operatingIceConcentration, without the A/B equivalent-safety alternative."; c["engineeringDecision"]="R13_BRANCH_SPECIFIC_CONTROLLED_APPROVAL_STRINGS"; index["semanticObligations"][rid]=[c["comparisonModel"]]

    # TRF-012: structural readiness only, no envelope reconstruction.
    rid="TRF-012"; c=index["dependencyContracts"][rid]; readiness="Verify structural readiness only: intended ice-operating waterlines and the externally determined lower ice waterline are represented with profile points carrying longitudinalPosition and verticalCoordinate. Do not reconstruct or prove the defining geometric calculation."
    c.update(engineeringDecision="R13_TRUE_COMPLEX_READINESS_WATERLINE_STRUCTURE",encodingPattern="Complex readiness input/result structure",comparisonModel=readiness,operandTerms=["hasIntendedIceOperatingWaterline","hasWaterlineProfilePoint","longitudinalPosition","verticalCoordinate"],resultTerms=["hasLowerIceWaterline","hasWaterlineProfilePoint","longitudinalPosition","verticalCoordinate"],ownerClasses=["ship","iceWaterline","waterlineProfilePoint"],readinessInputPaths=["ship -> hasIntendedIceOperatingWaterline -> iceWaterline -> hasWaterlineProfilePoint -> waterlineProfilePoint"],readinessResultPaths=["ship -> hasLowerIceWaterline -> iceWaterline -> hasWaterlineProfilePoint -> waterlineProfilePoint"],prohibitedOperations=["compute pointwise lower envelope","interpolate waterline segments","calculate segment crossings","reconstruct broken-line geometry","use NOW() or wall-clock state","invent geometric tolerance","prove equality to a reconstructed envelope"],formulaExecutionRequired=False); index["semanticObligations"][rid]=[readiness]

    # TRF-014: deterministic supplied assessmentDate, no wall-clock dependency.
    rid="TRF-014"; index["requirements"][rid]=sorted(set(index["requirements"][rid])|{"assessmentDate"}); index["termOwners"][rid]["assessmentDate"]="ship"; c=index["dependencyContracts"][rid]; c["applicabilityTerms"]=sorted(set(c["applicabilityTerms"])|{"assessmentDate"}); c["directConstraintTerms"]=sorted(set(c.get("directConstraintTerms",index["requirements"][rid]))|{"assessmentDate"}); c["timeTerms"]=sorted(set(c.get("timeTerms",[]))|{"assessmentDate","constructionDate","firstScheduledDryDockingDate"}); c["literalConstants"]={"regulatoryCutoffDate":{"lexicalForm":"2007-07-01","datatype":"xsd:date"}}; c["conditionalRules"]=[{"if":"constructionDate >= 2007-07-01","then":"preserve the existing source marking condition"},{"if":"constructionDate < 2007-07-01 AND complete required warning-triangle and ice-class-draught-mark evidence exists","then":"pass without requiring firstScheduledDryDockingDate"},{"if":"constructionDate < 2007-07-01 AND complete marking evidence is absent","then":"require firstScheduledDryDockingDate; when firstScheduledDryDockingDate <= assessmentDate, require the markings"}]; c["comparisonModel"]="Use supplied assessmentDate, never execution time. Preserve certificate/document and draught-direction obligations. Apply the fixed xsd:date cutoff 2007-07-01; pre-cutoff ships with complete marking evidence pass without firstScheduledDryDockingDate, otherwise require that date and enforce markings when it is on or before assessmentDate."; c["engineeringDecision"]="R13_REUSE_ASSESSMENT_DATE_NO_WALL_CLOCK"; index["semanticObligations"][rid]=[c["comparisonModel"]]

    # TRF-109: exact Table 6-14 controlled reference and exactly-one coefficient values.
    rid="TRF-109"; index["requirements"][rid]=sorted(set(index["requirements"][rid])|{"traficomTable6Dash14"}); c=index["dependencyContracts"][rid]; c["controlledValueTerms"]=sorted(set(c.get("controlledValueTerms",[]))|{"traficomTable6Dash14"}); c["directConstraintTerms"]=sorted(set(c["directConstraintTerms"])|{"traficomTable6Dash14"}); c["tableModel"]={"structured":True,"canonicalTableReference":"traficomTable6Dash14","referenceProperty":"tableReference","sourceTitle":"TRAFICOM Table 6-14 - Parameters for rho determination","selector":"propellerType","rows":{"open":{"C1":0.000747,"C2":0.0645,"C3":-0.0565,"C4":2.22},"ducted":{"C1":0.000534,"C2":0.0533,"C3":-0.0459,"C4":2.584}},"iceLoadCycleCountRange":{"minimumInclusive":5000000,"maximumInclusive":100000000},"coefficientCardinality":{"fatigueCoefficientC1":{"minCount":1,"maxCount":1},"fatigueCoefficientC2":{"minCount":1,"maxCount":1},"fatigueCoefficientC3":{"minCount":1,"maxCount":1},"fatigueCoefficientC4":{"minCount":1,"maxCount":1}},"calculateLaterRho":False}; c["comparisonModel"]="For tableReference exactly traficomTable6Dash14, select the exact open or ducted C1-C4 row; require exactly one value for each coefficient and 5000000 <= iceLoadCycleCount <= 100000000. Do not calculate later rho expressions."; c["engineeringDecision"]="R13_CANONICAL_TABLE_6_14_REFERENCE_AND_CARDINALITY"; index["semanticObligations"][rid]=[c["comparisonModel"]]

    # Final identity/count assertions and derived artifacts.
    counts=dict(Counter(r["category"] for r in evidence["requirements"]));
    if counts!=EXPECTED_COUNTS: raise RuntimeError(f"Unexpected R13 category counts: {counts}")
    if any(by[rid]["category"]!=next(x for x in read(SOURCE/"evidence/stage1_approved.json")["requirements"] if x["id"]==rid)["category"] for rid in by): raise RuntimeError("R13 category changed unexpectedly")
    index["sourceLockId"]=LOCK_ID; index["version"]="13.0"; evidence["summary"]["verificationPolicyLockId"]=LOCK_ID; evidence["summary"]["verificationPolicy"]="R13 narrow source-grounded table, approval, readiness, and date corrections"
    write(TARGET/"evidence/stage1_approved.json",evidence); write(TARGET/"requirement_term_index.json",index); write(TARGET/"registry/term_registry.json",registry)
    fields=list(read(SOURCE/"registry/term_registry.json")[0].keys())
    with (TARGET/"registry/term_registry.csv").open("w",encoding="utf-8",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore"); w.writeheader()
        for item in registry: w.writerow({k:" | ".join(v) if isinstance(v,list) else v for k,v in item.items()})
    policy=read(TARGET/"evidence/verification_policy_r12.json"); policy.update(lockId=LOCK_ID,categoryCounts=EXPECTED_COUNTS); policy["r13Corrections"]=["I2-048 exact IACS Table 8 and grade families","IMO approval controlled strings","TRF-012 structural readiness","TRF-014 assessmentDate reuse","TRF-109 canonical Table 6-14 reference"]; policy["structuredTableReferenceRule"]="A COMPLETE structured tableModel with canonicalTableReference must resolve to a tableReferenceValue and appear in controlled/scope metadata; validation blocks rather than invents."; write(TARGET/"evidence/verification_policy_r13.json",policy)
    (TARGET/"evidence/VERIFICATION_POLICY_R13.md").write_text("# R13 verification policy provenance\n\nR13 applies only the approved source-grounded table, approval, readiness, and deterministic-date corrections. Categories and API behavior are unchanged. Structured canonical table references are blocking-validated and never invented.\n",encoding="utf-8")
    decisions={"lockId":LOCK_ID,"sourceLockId":SOURCE_LOCK_ID,"newCanonicalTerms":list(NEW_TERMS),"modifiedExistingTermMetadata":["assessmentDate provenance only"],"affectedRequirements":["I2-048","IMO-031","IMO-032","IMO-048","IMO-049","TRF-012","TRF-014","TRF-109"],"categoryChanges":{},"apiCalls":0,"apiTransportChanges":0}; write(TARGET/"registry/r13_narrow_source_correction_decisions.json",decisions); write(TARGET/"provenance/r12_immutable_source_hashes.json",provenance)
    bound_rel=["context/nltl_benchmark_context.jsonld","evidence/stage1_approved.json","evidence/verification_policy_r13.json","evidence/VERIFICATION_POLICY_R13.md","ontology/nltl_benchmark_vocabulary.ttl","ontology/nltl_benchmark_vocabulary.rdf","registry/term_registry.json","registry/term_registry.csv","registry/r13_narrow_source_correction_decisions.json","requirement_term_index.json","provenance/r12_immutable_source_hashes.json","few_shots/few_shot_pairs.jsonl","few_shots/catalog.json","few_shots/validation_report.json"]
    bound={rel:sha(TARGET/rel) for rel in bound_rel}; write(TARGET/"r13_prelock_binding.json",{"lockId":LOCK_ID,"status":"PRELOCK_OFFLINE_VALIDATION_ONLY","workbook":"Pending R13 workbook","workbookSha256":"","boundMachineReadableArtifacts":bound,"boundRequirementIndex":{"requirement_term_index.json":bound["requirement_term_index.json"]}}); write(TARGET/"prelock_manifest.json",{"lockId":LOCK_ID,"sourceLockId":SOURCE_LOCK_ID,"boundArtifacts":bound,"categoryChanges":{},"categoryCounts":EXPECTED_COUNTS,"newCanonicalTerms":list(NEW_TERMS),"apiCalls":0})
    print(json.dumps({"status":"R13_PRELOCK_CREATED","lockId":LOCK_ID,"categoryCounts":counts,"newCanonicalTerms":list(NEW_TERMS),"r12ImmutableFiles":provenance["fileCount"],"apiCalls":0},indent=2))

if __name__=="__main__": main()
