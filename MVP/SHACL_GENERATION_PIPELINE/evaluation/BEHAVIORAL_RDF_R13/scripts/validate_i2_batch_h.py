from pathlib import Path
import json
import hashlib
import math
import shutil
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD


def find_repo():
    candidates=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    seen=set()
    for c in candidates:
        c=c.resolve()
        if c in seen:
            continue
        seen.add(c)
        if (c/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"/"requirement_term_index.json").exists():
            return c
    raise RuntimeError("Could not locate NLTL_v2 repository root")


REPO=find_repo()
PIPELINE=REPO/"MVP"/"SHACL_GENERATION_PIPELINE"
ROOT=PIPELINE/"evaluation"/"BEHAVIORAL_RDF_R13"
R13=REPO/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
INDEX=json.loads((R13/"requirement_term_index.json").read_text())
REGISTRY=json.loads((R13/"registry"/"term_registry.json").read_text())
REG={x["localName"]:x for x in REGISTRY}
CONTRACTS=INDEX["dependencyContracts"]

NLTL=Namespace("https://w3id.org/nltl/vocab#")
QUDT=Namespace("http://qudt.org/schema/qudt/")
UNIT=Namespace("http://qudt.org/vocab/unit/")
BASE="https://w3id.org/nltl/benchmark/i2-batch-h/"

REQS=["I2-048"]
EXPECTED_MODES={"I2-048":"DIRECT_STATIC"}
assert CONTRACTS["I2-048"]["status"]=="COMPLETE"
assert CONTRACTS["I2-048"]["verificationMode"]=="DIRECT_STATIC"
assert CONTRACTS["I2-048"].get("formulaExecutionRequired") is False

TABLE=CONTRACTS["I2-048"]["tableModel"]
ROWS=TABLE["rows"]
GRADE_FAMILIES=TABLE["gradeFamilies"]
TABLE_REF=NLTL[TABLE["canonicalTableReference"]]

ONTOLOGY=Graph().parse(R13/"ontology"/"nltl_benchmark_vocabulary.ttl",format="turtle")
KNOWN_NLTL={str(s).split("#",1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL))}
POLAR_CLASSES={f"PC{i}":NLTL[f"polarClassPc{i}"] for i in range(1,8)}
URI_TO_PC={v:k for k,v in POLAR_CLASSES.items()}
GROUP_MEMBERS={
    "PC1-3":["PC1","PC2","PC3"],
    "PC1-5":["PC1","PC2","PC3","PC4","PC5"],
    "PC4-5":["PC4","PC5"],
    "PC6-7":["PC6","PC7"],
}


def new_graph(cid):
    g=Graph(); ex=Namespace(BASE+cid+"/")
    g.bind("ex",ex); g.bind("nltl",NLTL); g.bind("qudt",QUDT); g.bind("unit",UNIT); g.bind("xsd",XSD)
    ship=ex.ship; g.add((ship,RDF.type,NLTL.ship))
    return g,ex,ship


def datatype_for(term):
    return {
        "xsd:boolean":XSD.boolean,
        "xsd:string":XSD.string,
        "xsd:integer":XSD.integer,
        "xsd:decimal":XSD.decimal,
        "xsd:date":XSD.date,
    }.get(REG[term].get("datatype",""))


def add_value(g,s,term,value,ex,name=None,unit_override=None,wrong_unit=False):
    row=REG.get(term)
    if row is None:
        raise RuntimeError(f"Unknown R13 term: {term}")
    kind=row["kind"]
    if kind=="QuantityProperty":
        unit=unit_override or row.get("unitIri","")
        if not unit:
            raise RuntimeError(f"{term} has no frozen/context unit")
        q=ex[name or term+"Value"]
        g.add((q,RDF.type,QUDT.QuantityValue))
        g.add((q,QUDT.numericValue,Literal(str(value),datatype=XSD.decimal)))
        u=URIRef(unit)
        if wrong_unit:
            u=UNIT.UNITLESS if u!=UNIT.UNITLESS else UNIT.M
        g.add((q,QUDT.unit,u)); g.add((s,NLTL[term],q)); return q
    if kind=="DatatypeProperty":
        dt=datatype_for(term)
        if dt is None:
            raise RuntimeError(f"Unsupported datatype for {term}")
        g.add((s,NLTL[term],Literal(value,datatype=dt))); return None
    if kind=="ObjectProperty":
        if not isinstance(value,URIRef):
            raise RuntimeError(f"{term} requires URIRef")
        g.add((s,NLTL[term],value)); return value
    raise RuntimeError(f"Cannot add value for {kind} term {term}")


def one(g,s,p):
    vals=list(g.objects(s,p)); return vals[0] if len(vals)==1 else None


def qty_number(g,s,term,expected_unit=None):
    expected=expected_unit or REG.get(term,{}).get("unitIri","")
    vals=list(g.objects(s,NLTL[term]))
    if len(vals)!=1:
        return None
    q=vals[0]
    if (q,RDF.type,QUDT.QuantityValue) not in g:
        return None
    nums=list(g.objects(q,QUDT.numericValue)); units=list(g.objects(q,QUDT.unit))
    if len(nums)!=1 or len(units)!=1:
        return None
    if expected and str(units[0])!=str(expected):
        return None
    try:
        return float(nums[0])
    except Exception:
        return None


def local(uri):
    text=str(uri)
    return text.split("#",1)[1] if "#" in text else text.rsplit("/",1)[-1]


def group_contains(group,pc_name):
    return pc_name in GROUP_MEMBERS[group]


def lookup_row(thickness):
    matches=[]
    for row in ROWS:
        band=row["thicknessBand"]
        lo=band["lowerExclusiveMm"]; hi=band["upperInclusiveMm"]
        if (lo is None or thickness>lo) and thickness<=hi:
            matches.append(row)
    return matches[0] if len(matches)==1 else None


def table_lookup(pc_uri,thickness,mat_uri,strength_uri):
    pc_name=URI_TO_PC.get(pc_uri)
    if pc_name is None:
        return None
    row=lookup_row(thickness)
    if row is None:
        return None
    mat=local(mat_uri); strength=local(strength_uri)
    matches=[]
    for sel in row["selections"]:
        if sel["steelMaterialClass"]!=mat or sel["steelStrengthCategory"]!=strength:
            continue
        if group_contains(sel["polarClassGroup"],pc_name):
            matches.append(sel)
    if len(matches)!=1:
        return None
    return matches[0]


def grade_rank(family_uri,grade_uri):
    fam=local(family_uri); grade=local(grade_uri)
    return GRADE_FAMILIES.get(fam,{}).get(grade)


def build_048(cid,pc,thickness,material_class,strength_category,actual_grade,required_grade,table_ref=TABLE_REF,
              omit_case=False,omit_plating_link=False,missing=None,wrong_thickness_unit=False,
              duplicate_material=False,duplicate_table=False):
    g,ex,ship=new_graph(cid)
    if missing!="polarClass":
        g.add((ship,NLTL.polarClass,pc))
    if omit_case:
        return g
    case=ex.case; plating=ex.plating
    g.add((case,RDF.type,NLTL.steelGradeRequirementCase)); g.add((plating,RDF.type,NLTL.plating))
    g.add((ship,NLTL.hasSteelGradeRequirementCase,case))
    if not omit_plating_link:
        g.add((case,NLTL.steelGradeRequirementCasePlating,plating))
    if missing!="asBuiltPlateThickness":
        add_value(g,plating,"asBuiltPlateThickness",thickness,ex,"thickness",wrong_unit=wrong_thickness_unit)
    if missing!="steelMaterialClass":
        g.add((case,NLTL.steelMaterialClass,material_class))
        if duplicate_material:
            alt=NLTL.steelMaterialClassTwo if material_class!=NLTL.steelMaterialClassTwo else NLTL.steelMaterialClassOne
            g.add((case,NLTL.steelMaterialClass,alt))
    if missing!="steelStrengthCategory":
        g.add((case,NLTL.steelStrengthCategory,strength_category))
    if missing!="tableReference":
        g.add((case,NLTL.tableReference,table_ref))
        if duplicate_table:
            g.add((case,NLTL.tableReference,ex.otherTable))
    if missing!="actualHullStructuralSteelGrade" and actual_grade is not None:
        g.add((case,NLTL.actualHullStructuralSteelGrade,actual_grade))
    if missing!="requiredHullStructuralSteelGrade" and required_grade is not None:
        g.add((case,NLTL.requiredHullStructuralSteelGrade,required_grade))
    return g


def oracle_048(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    ship=ships[0]
    cases=list(g.objects(ship,NLTL.hasSteelGradeRequirementCase))
    # Frozen R13 explicitly has topLevelCaseMinCount=0.
    if not cases:
        return True
    pcs=list(g.objects(ship,NLTL.polarClass))
    if len(pcs)!=1 or pcs[0] not in URI_TO_PC:
        return False
    pc=pcs[0]
    for c in cases:
        plating_vals=list(g.objects(c,NLTL.steelGradeRequirementCasePlating))
        if len(plating_vals)!=1:
            return False
        plating=plating_vals[0]
        thickness=qty_number(g,plating,"asBuiltPlateThickness")
        if thickness is None:
            return False
        mats=list(g.objects(c,NLTL.steelMaterialClass)); fams=list(g.objects(c,NLTL.steelStrengthCategory)); refs=list(g.objects(c,NLTL.tableReference)); acts=list(g.objects(c,NLTL.actualHullStructuralSteelGrade)); reqs=list(g.objects(c,NLTL.requiredHullStructuralSteelGrade))
        if len(mats)!=1 or len(fams)!=1 or len(refs)!=1 or len(acts)!=1:
            return False
        if refs[0]!=TABLE_REF:
            return False
        sel=table_lookup(pc,thickness,mats[0],fams[0])
        if sel is None:
            return False
        expected_req=sel.get("requiredGrade") if sel.get("applicable") else None
        if expected_req is None:
            if len(reqs)!=0:
                return False
            # Actual grade still has exact cardinality under R13, but no minimum-grade comparison is imposed.
            continue
        if len(reqs)!=1 or reqs[0]!=NLTL[expected_req]:
            return False
        rr=grade_rank(fams[0],reqs[0]); ar=grade_rank(fams[0],acts[0])
        if rr is None or ar is None or ar<rr:
            return False
    return True


ORACLES={"I2-048":oracle_048}
CASE_DEFS=[]
def add_case(suffix,expected,rationale,graph):
    CASE_DEFS.append({"requirement_id":"I2-048","case_id":f"I2-048-H-{suffix}","expected":expected,"rationale":rationale,"graph":graph})

# ------------------------------------------------------------------
# 126 source-table cells: one PASS fixture for every R13 Table-8 cell.
# Representative concrete PC values rotate within each source group so PC1..PC7
# are all exercised while preserving the exact 126 table-cell coverage target.
# ------------------------------------------------------------------
cell_counter=0
for row_i,row in enumerate(ROWS):
    band=row["thicknessBand"]; lo=band["lowerExclusiveMm"]; hi=band["upperInclusiveMm"]
    thickness=(hi/2.0) if lo is None else (lo+hi)/2.0
    for sel_i,sel in enumerate(row["selections"]):
        cell_counter+=1
        members=GROUP_MEMBERS[sel["polarClassGroup"]]
        pc_name=members[(row_i+sel_i)%len(members)]
        pc=POLAR_CLASSES[pc_name]
        mat=NLTL[sel["steelMaterialClass"]]; fam=NLTL[sel["steelStrengthCategory"]]
        req=NLTL[sel["requiredGrade"]] if sel.get("applicable") else None
        if req is not None:
            actual=req
            rationale=(f"Exact IACS Table 8 cell {cell_counter}/126: t={thickness} mm, {pc_name}, "
                       f"{sel['steelMaterialClass']}, {sel['steelStrengthCategory']} selects {sel['requiredGrade']} and actual grade equals the requirement.")
        else:
            # R13 cardinality keeps an actual grade while NOT_APPLICABLE imposes no required-grade result.
            fam_grades=GRADE_FAMILIES[sel["steelStrengthCategory"]]
            actual=NLTL[min(fam_grades,key=fam_grades.get)]
            rationale=(f"Exact IACS Table 8 NOT_APPLICABLE cell {cell_counter}/126: t={thickness} mm, {pc_name}, "
                       f"{sel['steelMaterialClass']}, {sel['steelStrengthCategory']} has no required grade result.")
        add_case(f"T{cell_counter:03d}","PASS",rationale,build_048(f"I2-048-H-T{cell_counter:03d}",pc,thickness,mat,fam,actual,req))

assert cell_counter==126,cell_counter

# Eight lower-exclusive band checks (10+, 15+, ..., 45+) using a stable applicable selector.
for j,row in enumerate(ROWS[1:],start=1):
    lo=row["thicknessBand"]["lowerExclusiveMm"]
    thickness=lo+0.0001
    sel=next(x for x in row["selections"] if x.get("applicable") and x["steelMaterialClass"]=="steelMaterialClassOne" and x["steelStrengthCategory"]=="normalStrengthSteelCategory")
    pc_name=GROUP_MEMBERS[sel["polarClassGroup"]][0]; pc=POLAR_CLASSES[pc_name]
    req=NLTL[sel["requiredGrade"]]
    add_case(f"B{j:02d}","PASS",f"Thickness {thickness} mm is just above the lower-exclusive boundary {lo} mm and selects the next Table-8 band.",build_048(f"I2-048-H-B{j:02d}",pc,thickness,NLTL.steelMaterialClassOne,NLTL.normalStrengthSteelCategory,req,req))

# No represented case is valid because topLevelCaseMinCount=0.
g,ex,ship=new_graph("I2-048-H-PZERO")
add_case("PZERO","PASS","Frozen R13 validates every represented steel-grade case but does not impose top-level case existence.",g)

# Same-family higher grades are accepted.
add_case("PH01","PASS","A higher normal-strength grade in the same family satisfies a required grade D.",build_048("I2-048-H-PH01",POLAR_CLASSES["PC3"],17.5,NLTL.steelMaterialClassOne,NLTL.normalStrengthSteelCategory,NLTL.steelGradeE,NLTL.steelGradeD))
add_case("PH02","PASS","A higher high-tensile grade in the same family satisfies a required grade DH.",build_048("I2-048-H-PH02",POLAR_CLASSES["PC3"],17.5,NLTL.steelMaterialClassOne,NLTL.highTensileSteelCategory,NLTL.steelGradeEh,NLTL.steelGradeDh))

# Targeted failures exercise selectors, cardinality, table identity and grade-family/rank semantics.
base_pc=POLAR_CLASSES["PC3"]
base_t=17.5
base_mat=NLTL.steelMaterialClassOne
base_fam=NLTL.normalStrengthSteelCategory
base_req=NLTL.steelGradeD
add_case("F001","FAIL","Ship Polar Class selector is missing.",build_048("I2-048-H-F001",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="polarClass"))
add_case("F002","FAIL","steelGradeRequirementCase is not linked to its plating owner.",build_048("I2-048-H-F002",base_pc,base_t,base_mat,base_fam,base_req,base_req,omit_plating_link=True))
add_case("F003","FAIL","asBuiltPlateThickness selector is missing.",build_048("I2-048-H-F003",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="asBuiltPlateThickness"))
add_case("F004","FAIL","asBuiltPlateThickness uses the wrong unit rather than millimetres.",build_048("I2-048-H-F004",base_pc,base_t,base_mat,base_fam,base_req,base_req,wrong_thickness_unit=True))
add_case("F005","FAIL","steelMaterialClass selector is missing.",build_048("I2-048-H-F005",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="steelMaterialClass"))
add_case("F006","FAIL","steelMaterialClass violates frozen exact-cardinality by carrying two values.",build_048("I2-048-H-F006",base_pc,base_t,base_mat,base_fam,base_req,base_req,duplicate_material=True))
add_case("F007","FAIL","steelStrengthCategory selector is missing.",build_048("I2-048-H-F007",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="steelStrengthCategory"))
add_case("F008","FAIL","tableReference is not the canonical iacsUrI2Table8 individual.",build_048("I2-048-H-F008",base_pc,base_t,base_mat,base_fam,base_req,base_req,table_ref=Namespace(BASE+"I2-048-H-F008/").wrongTable))
add_case("F009","FAIL","Actual hull structural steel grade is missing despite frozen minCount=1.",build_048("I2-048-H-F009",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="actualHullStructuralSteelGrade"))
add_case("F010","FAIL","Applicable Table-8 cell lacks the exact required grade result.",build_048("I2-048-H-F010",base_pc,base_t,base_mat,base_fam,base_req,base_req,missing="requiredHullStructuralSteelGrade"))
add_case("F011","FAIL","Stored required grade does not equal the source Table-8 selection.",build_048("I2-048-H-F011",base_pc,base_t,base_mat,base_fam,NLTL.steelGradeE,NLTL.steelGradeE))
add_case("F012","FAIL","Actual grade B is below required grade D within the normal-strength family.",build_048("I2-048-H-F012",base_pc,base_t,base_mat,base_fam,NLTL.steelGradeB,base_req))
add_case("F013","FAIL","Actual high-tensile grade is not rank-comparable with a normal-strength required grade.",build_048("I2-048-H-F013",base_pc,base_t,base_mat,base_fam,NLTL.steelGradeDh,base_req))
# Known N/A cell: class III, PC1-3, normal strength, 35<t<=40.
add_case("F014","FAIL","NOT_APPLICABLE Table-8 combination incorrectly carries a required grade result.",build_048("I2-048-H-F014",POLAR_CLASSES["PC2"],37.5,NLTL.steelMaterialClassThree,NLTL.normalStrengthSteelCategory,NLTL.steelGradeB,NLTL.steelGradeE))
add_case("F015","FAIL","tableReference violates exact-cardinality by carrying two values.",build_048("I2-048-H-F015",base_pc,base_t,base_mat,base_fam,base_req,base_req,duplicate_table=True))

assert len(CASE_DEFS)==152,len(CASE_DEFS)


def graph_vocab_ok(g):
    local=set()
    for s,p,o in g:
        for node in (s,p,o):
            text=str(node)
            if text.startswith(str(NLTL)):
                local.add(text.split("#",1)[1])
    unknown=sorted(x for x in local if x not in KNOWN_NLTL)
    return not unknown,unknown


def graph_qudt_ok(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1:
            return False
    return True


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_existing(check_hashes=True):
    manifest_path=ROOT/"manifests"/"i2_batch_h_manifest.jsonl"
    lock_path=ROOT/"locks"/"i2_batch_h_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("Batch H manifest does not exist")
    rows=[json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
    syntax=vocab=qudt=agreement=0; diagnostics=[]
    for row in rows:
        p=ROOT/row["rdf_path"]
        try:
            g=Graph().parse(p,format="turtle"); syntax+=1
        except Exception as e:
            diagnostics.append((row["case_id"],"parse",str(e))); continue
        ok,unknown=graph_vocab_ok(g)
        if ok: vocab+=1
        else: diagnostics.append((row["case_id"],"vocab",unknown))
        if graph_qudt_ok(g): qudt+=1
        else: diagnostics.append((row["case_id"],"QUDT","invalid QuantityValue"))
        actual="PASS" if oracle_048(g) else "FAIL"
        if actual==row["expected"]: agreement+=1
        else: diagnostics.append((row["case_id"],"oracle",f"expected={row['expected']} actual={actual}"))
    hash_ok=True
    if check_hashes:
        if not lock_path.exists():
            hash_ok=False; diagnostics.append(("lock","hash","lock file missing"))
        else:
            lock=json.loads(lock_path.read_text())
            for rel,expected_hash in lock["frozen_files"].items():
                p=ROOT/rel
                if not p.exists() or sha256(p)!=expected_hash:
                    hash_ok=False; diagnostics.append((rel,"hash","mismatch"))
    n=len(rows)
    print("Requirements: 1")
    print(f"RDF files: {n}")
    print(f"Syntactically valid: {syntax}")
    print(f"Vocabulary validation count: {vocab}")
    print(f"QUDT/unit validation count: {qudt}")
    print(f"Source-oracle agreement count: {agreement}")
    if check_hashes:
        print("Frozen hashes matched: "+("YES" if hash_ok else "NO"))
    ok=syntax==vocab==qudt==agreement==n and (hash_ok if check_hashes else True)
    print("Overall status: "+("PASS" if ok else "FAIL"))
    if diagnostics:
        print("\nDiagnostics:")
        for d in diagnostics:
            print(d)
    return ok


def generate():
    rdf_root=ROOT/"rdf"/"I2"; spec_root=ROOT/"specifications"/"I2"; manifest_root=ROOT/"manifests"; locks_root=ROOT/"locks"; scripts_root=ROOT/"scripts"
    for p in [rdf_root,spec_root,manifest_root,locks_root,scripts_root]:
        p.mkdir(parents=True,exist_ok=True)
    lock_path=locks_root/"i2_batch_h_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("Batch H lock already exists. Refusing to overwrite frozen fixtures.")
    req="I2-048"; outdir=rdf_root/req; outdir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for c in CASE_DEFS:
        p=outdir/f"{c['case_id']}.ttl"; c["graph"].serialize(destination=p,format="turtle")
        rows.append({
            "requirement_id":req,
            "case_id":c["case_id"],
            "expected":c["expected"],
            "rdf_path":str(p.relative_to(ROOT)),
            "source_id":"SRC-IACS-I2-R4",
            "source_clause":"I2.12.1 / I2.12.4 Table 8",
            "verification_mode":"DIRECT_STATIC",
            "sourceability_grade":"D_REGULATION_SYNTHETIC",
            "source_oracle_rationale":c["rationale"],
            "generated_shacl_inspected":False,
        })
    manifest_path=manifest_root/"i2_batch_h_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row)+"\n")
    spec={
        "requirement_id":req,
        "source_id":"SRC-IACS-I2-R4",
        "source_clause":"I2.12.1 / I2.12.4 Table 8",
        "source_lock_id":INDEX["sourceLockId"],
        "r13_contract":CONTRACTS[req],
        "test_cases":[{"case_id":x["case_id"],"expected":x["expected"],"rationale":x["rationale"]} for x in CASE_DEFS],
        "sourceability_grade":"D_REGULATION_SYNTHETIC",
        "benchmark_policy":"Source/R13-defined behavioral oracle created without inspecting generated SHACL. Batch H mechanically covers all 126 frozen Table-8 selector cells and adds boundary/cardinality/rank controls.",
    }
    spec_path=spec_root/"I2-048_batch_h.json"; spec_path.write_text(json.dumps(spec,indent=2)+"\n")
    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")
    frozen=[manifest_path,spec_path]+sorted(outdir.glob("I2-048-H-*.ttl"))
    lock={
        "benchmark":"I2 Behavioral Benchmark Batch H",
        "source_lock_id":INDEX["sourceLockId"],
        "requirements":REQS,
        "requirement_count":1,
        "case_count":len(CASE_DEFS),
        "table8_cells_covered":126,
        "generated_without_inspecting_generated_shacl":True,
        "previous_frozen_batches_modified":False,
        "frozen_files":{str(p.relative_to(ROOT)):sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock,indent=2)+"\n")
    validator=scripts_root/"validate_i2_batch_h.py"; shutil.copy2(Path(__file__).resolve(),validator); validator.chmod(0o755)
    (ROOT/"README_I2_BATCH_H.md").write_text(
        "# I2 Behavioral Benchmark Batch H\n\n"
        "Requirement: I2-048\nCases: 152\n\n"
        "Dedicated exhaustive IACS Table 8 benchmark. It contains one source-grounded PASS fixture for every one of the 126 frozen R13 Table-8 selector cells, eight lower-exclusive thickness-boundary checks, same-family higher-grade controls, a zero-case universal-scope control, and targeted selector/cardinality/table/rank failures. Existing Pilot-02 I2-048 files are not modified; Batch-H case IDs and specification filename are batch-specific.\n\n"
        "Run:\n\npython3 scripts/validate_i2_batch_h.py\n"
    )
    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode=Path(__file__).name=="validate_i2_batch_h.py" or "--validate-only" in sys.argv
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__=="__main__":
    main()
