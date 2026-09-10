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
BASE="https://w3id.org/nltl/benchmark/i2-batch-g/"

REQS=["I2-004","I2-005","I2-041","I2-042","I2-046","I2-047","I2-066","I2-067"]
EXPECTED_MODES={
    "I2-004":"DIRECT_STATIC",
    "I2-005":"DIRECT_STATIC",
    "I2-041":"COMPLEX_READINESS",
    "I2-042":"DIRECT_CALCULATION",
    "I2-046":"DIRECT_CALCULATION",
    "I2-047":"DIRECT_CALCULATION",
    "I2-066":"DIRECT_STATIC",
    "I2-067":"DIRECT_STATIC",
}
for req in REQS:
    assert CONTRACTS[req]["status"]=="COMPLETE"
    assert CONTRACTS[req]["verificationMode"]==EXPECTED_MODES[req]
assert CONTRACTS["I2-041"].get("formulaExecutionRequired") is False

ONTOLOGY=Graph().parse(R13/"ontology"/"nltl_benchmark_vocabulary.ttl",format="turtle")
KNOWN_NLTL={str(s).split("#",1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL))}
POLAR_CLASSES={NLTL[f"polarClassPc{i}"] for i in range(1,8)}


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
        g.add((q,QUDT.unit,u))
        g.add((s,NLTL[term],q))
        return q
    if kind=="DatatypeProperty":
        dt=datatype_for(term)
        if dt is None:
            raise RuntimeError(f"Unsupported datatype for {term}")
        g.add((s,NLTL[term],Literal(value,datatype=dt)))
        return None
    if kind=="ObjectProperty":
        if not isinstance(value,URIRef):
            raise RuntimeError(f"{term} requires URIRef")
        g.add((s,NLTL[term],value))
        return value
    raise RuntimeError(f"Cannot add value for {kind} term {term}")


def one(g,s,p):
    vals=list(g.objects(s,p))
    return vals[0] if len(vals)==1 else None


def bool_value(g,s,term):
    o=one(g,s,NLTL[term])
    if o is None:
        return None
    try:
        return bool(o.toPython())
    except Exception:
        return None


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


def close(a,b,tol=1e-9):
    return a is not None and b is not None and math.isclose(a,b,rel_tol=tol,abs_tol=tol)


# ------------------------------------------------------------------
# I2-004 — UIWL displacement equals greatest represented case value
# ------------------------------------------------------------------
def build_004(cid,case_values=(10,12,11),selected=12,missing_selected=False,wrong_selected_unit=False,wrong_case_unit_index=None):
    g,ex,ship=new_graph(cid)
    for i,v in enumerate(case_values):
        case=ex[f"waterlineCase{i+1}"]
        g.add((case,RDF.type,NLTL.upperIceWaterlineCase))
        g.add((ship,NLTL.hasUpperIceWaterlineCase,case))
        add_value(g,case,"waterlineCaseDisplacement",v,ex,f"caseDisp{i+1}",wrong_unit=(wrong_case_unit_index==i))
    if not missing_selected:
        add_value(g,ship,"upperIceWaterlineDisplacement",selected,ex,"selectedDui",wrong_unit=wrong_selected_unit)
    return g


def oracle_004(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    ship=ships[0]
    cases=list(g.objects(ship,NLTL.hasUpperIceWaterlineCase))
    if not cases:
        return False
    vals=[]
    for c in cases:
        v=qty_number(g,c,"waterlineCaseDisplacement")
        if v is None:
            return False
        vals.append(v)
    selected=qty_number(g,ship,"upperIceWaterlineDisplacement")
    return selected is not None and close(selected,max(vals))


# ------------------------------------------------------------------
# I2-005 — bottom/lower-region boundary shell inclination = 7 degrees
# ------------------------------------------------------------------
def build_005(cid,angle=7.0,missing_point=False,missing_angle=False,wrong_unit=False):
    g,ex,ship=new_graph(cid)
    if missing_point:
        return g
    p=ex.boundaryPoint
    g.add((p,RDF.type,NLTL.hullBoundaryPoint))
    g.add((ship,NLTL.hasBottomRegionLowerRegionBoundaryPoint,p))
    if not missing_angle:
        add_value(g,p,"shellInclinationAngle",angle,ex,"inclination",wrong_unit=wrong_unit)
    return g


def oracle_005(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    pts=list(g.objects(ships[0],NLTL.hasBottomRegionLowerRegionBoundaryPoint))
    if len(pts)!=1:
        return False
    angle=qty_number(g,pts[0],"shellInclinationAngle")
    return close(angle,7.0)


# ------------------------------------------------------------------
# I2-041 — readiness only under frozen R13 (do not execute sqrt rule)
# ------------------------------------------------------------------
def build_041(cid,tpn=10,sy=235,twn=3.5,include_member=True,missing=None,wrong_owner=None,wrong_unit=None):
    g,ex,ship=new_graph(cid)
    if not include_member:
        return g
    m=ex.member
    g.add((m,RDF.type,NLTL.structuralMember)); g.add((ship,NLTL.hasStructuralMember,m))
    vals=[("netAttachedShellPlateThickness",tpn),("yieldStrength",sy),("netWebThickness",twn)]
    for term,val in vals:
        if missing==term:
            continue
        owner=ship if wrong_owner==term else m
        add_value(g,owner,term,val,ex,term,wrong_unit=(wrong_unit==term))
    return g


def oracle_041(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    members=list(g.objects(ships[0],NLTL.hasStructuralMember))
    # Universal/readiness semantics: do not invent a structural member.
    for m in members:
        for term in ["netAttachedShellPlateThickness","yieldStrength","netWebThickness"]:
            if qty_number(g,m,term) is None:
                return False
    return True


# ------------------------------------------------------------------
# I2-042 — flange width >= 5 * net web thickness
# ------------------------------------------------------------------
def build_042(cid,twn=10,bf=50,include_member=True,missing=None,wrong_unit=None):
    g,ex,ship=new_graph(cid)
    if not include_member:
        return g
    m=ex.member
    g.add((m,RDF.type,NLTL.structuralMember)); g.add((ship,NLTL.hasStructuralMember,m))
    if missing!="netWebThickness":
        add_value(g,m,"netWebThickness",twn,ex,"twn",wrong_unit=(wrong_unit=="netWebThickness"))
    if missing!="flangeWidth":
        add_value(g,m,"flangeWidth",bf,ex,"bf",wrong_unit=(wrong_unit=="flangeWidth"))
    return g


def oracle_042(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    for m in g.objects(ships[0],NLTL.hasStructuralMember):
        twn=qty_number(g,m,"netWebThickness"); bf=qty_number(g,m,"flangeWidth")
        if twn is None or bf is None or bf+1e-9 < 5.0*twn:
            return False
    return True


# ------------------------------------------------------------------
# I2-046 — explicit applicability + >=1.0 mm internal addition
# ------------------------------------------------------------------
def build_046(cid,applicable=True,pc=NLTL.polarClassPc3,additions=(1.0,),missing_applicability=False,duplicate_applicability=False,missing_pc=False,missing_addition_index=None,wrong_unit_index=None):
    g,ex,ship=new_graph(cid)
    if not missing_applicability:
        add_value(g,ship,"polarClassRequirementsApplicable",applicable,ex)
    if duplicate_applicability:
        g.add((ship,NLTL.polarClassRequirementsApplicable,Literal(not applicable,datatype=XSD.boolean)))
    if applicable and not missing_pc:
        g.add((ship,NLTL.polarClass,pc))
    for i,val in enumerate(additions):
        st=ex[f"internalStructure{i+1}"]
        g.add((st,RDF.type,NLTL.internalIceStrengthenedStructure))
        g.add((ship,NLTL.hasInternalIceStrengthenedStructure,st))
        if missing_addition_index==i:
            continue
        add_value(g,st,"internalStructureCorrosionAbrasionAddition",val,ex,f"addition{i+1}",wrong_unit=(wrong_unit_index==i))
    return g


def oracle_046(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    ship=ships[0]
    app=bool_value(g,ship,"polarClassRequirementsApplicable")
    if app is None:
        return False
    if app is False:
        return True
    pc=one(g,ship,NLTL.polarClass)
    if pc not in POLAR_CLASSES:
        return False
    # R13 explicitly says universal rule does not require structure existence.
    for st in g.objects(ship,NLTL.hasInternalIceStrengthenedStructure):
        addition=qty_number(g,st,"internalStructureCorrosionAbrasionAddition")
        if addition is None or addition < 1.0-1e-9:
            return False
    return True


# ------------------------------------------------------------------
# I2-047 — renewal iff gauged thickness < net thickness + 0.5 mm
# Frozen R13 stores both thickness quantities in metres.
# ------------------------------------------------------------------
def build_047(cid,gauged=0.0104,net=0.0100,renewal=True,missing=None,wrong_unit=None):
    g,ex,ship=new_graph(cid)
    if missing!="gaugedThickness":
        add_value(g,ship,"gaugedThickness",gauged,ex,"gauged",wrong_unit=(wrong_unit=="gaugedThickness"))
    if missing!="netThickness":
        add_value(g,ship,"netThickness",net,ex,"net",wrong_unit=(wrong_unit=="netThickness"))
    if missing!="steelRenewalRequired":
        add_value(g,ship,"steelRenewalRequired",renewal,ex)
    return g


def oracle_047(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    ship=ships[0]
    gauged=qty_number(g,ship,"gaugedThickness"); net=qty_number(g,ship,"netThickness"); renewal=bool_value(g,ship,"steelRenewalRequired")
    if gauged is None or net is None or renewal is None:
        return False
    required=gauged < net+0.0005-1e-12
    return renewal is required


# ------------------------------------------------------------------
# I2-066 — every in-scope weld must be double continuous
# ------------------------------------------------------------------
def build_066(cid,welds=((True,"double"),),missing_scope_index=None,missing_type_index=None):
    g,ex,ship=new_graph(cid)
    for i,(inside,wtype) in enumerate(welds):
        w=ex[f"weld{i+1}"]
        g.add((w,RDF.type,NLTL.weld)); g.add((ship,NLTL.hasWeld,w))
        if missing_scope_index!=i:
            add_value(g,w,"withinIceStrengthenedArea",inside,ex)
        if missing_type_index==i:
            continue
        if wtype=="double":
            g.add((w,NLTL.weldType,NLTL.doubleContinuousWeld))
        elif wtype is not None:
            g.add((w,NLTL.weldType,ex[f"{wtype}WeldType"]))
    return g


def oracle_066(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    for w in g.objects(ships[0],NLTL.hasWeld):
        inside=bool_value(g,w,"withinIceStrengthenedArea")
        if inside is None:
            return False
        if inside and one(g,w,NLTL.weldType)!=NLTL.doubleContinuousWeld:
            return False
    return True


# ------------------------------------------------------------------
# I2-067 — continuity of strength at every represented connection
# ------------------------------------------------------------------
def build_067(cid,statuses=(True,),missing_status_index=None):
    g,ex,ship=new_graph(cid)
    for i,status in enumerate(statuses):
        c=ex[f"connection{i+1}"]
        g.add((c,RDF.type,NLTL.benchmarkEntity)); g.add((ship,NLTL.structuralConnection,c))
        if missing_status_index!=i:
            add_value(g,c,"strengthContinuityStatus",status,ex)
    return g


def oracle_067(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1:
        return False
    for c in g.objects(ships[0],NLTL.structuralConnection):
        if bool_value(g,c,"strengthContinuityStatus") is not True:
            return False
    return True


ORACLES={
    "I2-004":oracle_004,
    "I2-005":oracle_005,
    "I2-041":oracle_041,
    "I2-042":oracle_042,
    "I2-046":oracle_046,
    "I2-047":oracle_047,
    "I2-066":oracle_066,
    "I2-067":oracle_067,
}

CASE_DEFS=[]
def add_case(req,suffix,expected,rationale,graph):
    CASE_DEFS.append({"requirement_id":req,"case_id":f"{req}-G-{suffix}","expected":expected,"rationale":rationale,"graph":graph})

# I2-004 — 6
add_case("I2-004","P01","PASS","Selected UIWL displacement equals the greatest of three represented waterline-case displacements.",build_004("I2-004-P01",(10,12,11),12))
add_case("I2-004","P02","PASS","Maximum selection is invariant to graph/case ordering.",build_004("I2-004-P02",(12,9,10),12))
add_case("I2-004","P03","PASS","A single represented UIWL case is itself the maximum.",build_004("I2-004-P03",(8,),8))
add_case("I2-004","F01","FAIL","upperIceWaterlineDisplacement is present but is not the greatest represented case displacement.",build_004("I2-004-F01",(10,12,11),11))
add_case("I2-004","F02","FAIL","The selected UIWL displacement is missing.",build_004("I2-004-F02",(10,12),12,missing_selected=True))
add_case("I2-004","F03","FAIL","The selected UIWL displacement uses the wrong unit instead of frozen kt.",build_004("I2-004-F03",(10,12),12,wrong_selected_unit=True))

# I2-005 — 5
add_case("I2-005","P01","PASS","Bottom/lower-region boundary point has shell inclination exactly 7 degrees from horizontal.",build_005("I2-005-P01",7.0))
add_case("I2-005","F01","FAIL","Boundary shell inclination is below the exact 7-degree requirement.",build_005("I2-005-F01",6.9))
add_case("I2-005","F02","FAIL","Boundary shell inclination is above the exact 7-degree requirement.",build_005("I2-005-F02",7.1))
add_case("I2-005","F03","FAIL","Boundary angle is encoded with a non-degree unit.",build_005("I2-005-F03",7.0,wrong_unit=True))
add_case("I2-005","F04","FAIL","Required bottom/lower-region boundary point is absent.",build_005("I2-005-F04",missing_point=True))

# I2-041 — 7; readiness, not nonlinear formula execution
add_case("I2-041","P01","PASS","Structural-member readiness includes tpn, yield strength and twn with correct owners and units.",build_041("I2-041-P01",10,235,3.5))
add_case("I2-041","P02","PASS","R13 classifies I2-041 as COMPLEX_READINESS; a numerically low twn remains a complete interface case rather than executing the square-root inequality.",build_041("I2-041-P02",10,355,1.0))
add_case("I2-041","P03","PASS","Universal readiness clause does not invent a structural member when none is represented.",build_041("I2-041-P03",include_member=False))
add_case("I2-041","F01","FAIL","netAttachedShellPlateThickness readiness operand is missing.",build_041("I2-041-F01",missing="netAttachedShellPlateThickness"))
add_case("I2-041","F02","FAIL","yieldStrength readiness operand is missing.",build_041("I2-041-F02",missing="yieldStrength"))
add_case("I2-041","F03","FAIL","netWebThickness readiness result is missing.",build_041("I2-041-F03",missing="netWebThickness"))
add_case("I2-041","F04","FAIL","netWebThickness is attached to ship instead of the linked structural member.",build_041("I2-041-F04",wrong_owner="netWebThickness"))

# I2-042 — 7
add_case("I2-042","P01","PASS","Flange width equals the exact boundary 5*twn.",build_042("I2-042-P01",10,50))
add_case("I2-042","P02","PASS","Flange width above 5*twn satisfies the minimum-width rule.",build_042("I2-042-P02",10,55))
add_case("I2-042","P03","PASS","Universal clause does not impose a structural-member existence requirement.",build_042("I2-042-P03",include_member=False))
add_case("I2-042","F01","FAIL","Flange width is below 5*twn.",build_042("I2-042-F01",10,49.9))
add_case("I2-042","F02","FAIL","Required flangeWidth result is missing.",build_042("I2-042-F02",missing="flangeWidth"))
add_case("I2-042","F03","FAIL","Required netWebThickness operand is missing.",build_042("I2-042-F03",missing="netWebThickness"))
add_case("I2-042","F04","FAIL","flangeWidth is encoded with the wrong unit.",build_042("I2-042-F04",wrong_unit="flangeWidth"))

# I2-046 — 10
add_case("I2-046","P01","PASS","Applicable Polar-Class context has one internal structure at the exact 1.0 mm corrosion/abrasion-addition boundary.",build_046("I2-046-P01",True,NLTL.polarClassPc3,(1.0,)))
add_case("I2-046","P02","PASS","Applicable context may exceed the 1.0 mm minimum.",build_046("I2-046-P02",True,NLTL.polarClassPc6,(1.5,)))
add_case("I2-046","P03","PASS","Explicit false applicability makes the I2.11.3 obligation non-applicable even if a represented structure has a smaller value.",build_046("I2-046-P03",False,additions=(0.5,)))
add_case("I2-046","P04","PASS","R13 explicitly treats the linked structures universally and does not require inventing an internal-structure instance.",build_046("I2-046-P04",True,NLTL.polarClassPc4,()))
add_case("I2-046","F01","FAIL","Applicable internal structure has corrosion/abrasion addition below 1.0 mm.",build_046("I2-046-F01",True,NLTL.polarClassPc3,(0.99,)))
add_case("I2-046","F02","FAIL","Applicable linked structure is missing its corrosion/abrasion-addition QuantityValue.",build_046("I2-046-F02",True,NLTL.polarClassPc3,(1.0,),missing_addition_index=0))
add_case("I2-046","F03","FAIL","Applicable internal-structure addition uses the wrong unit.",build_046("I2-046-F03",True,NLTL.polarClassPc3,(1.0,),wrong_unit_index=0))
add_case("I2-046","F04","FAIL","Explicit applicability selector is missing; R13 requires exactly one boolean.",build_046("I2-046-F04",True,NLTL.polarClassPc3,(1.0,),missing_applicability=True))
add_case("I2-046","F05","FAIL","Applicable branch lacks required Polar Class evidence.",build_046("I2-046-F05",True,NLTL.polarClassPc3,(1.0,),missing_pc=True))
add_case("I2-046","F06","FAIL","Applicability selector has conflicting duplicate boolean values rather than exactly one value.",build_046("I2-046-F06",True,NLTL.polarClassPc3,(1.0,),duplicate_applicability=True))

# I2-047 — 8
add_case("I2-047","P01","PASS","Gauged thickness below tnet+0.5 mm correctly requires renewal.",build_047("I2-047-P01",0.0104,0.0100,True))
add_case("I2-047","P02","PASS","At exactly tnet+0.5 mm the strict-less-than renewal trigger is not active.",build_047("I2-047-P02",0.0105,0.0100,False))
add_case("I2-047","P03","PASS","Above tnet+0.5 mm renewal is not required.",build_047("I2-047-P03",0.0106,0.0100,False))
add_case("I2-047","F01","FAIL","Below-threshold case incorrectly records renewalRequired=false.",build_047("I2-047-F01",0.0104,0.0100,False))
add_case("I2-047","F02","FAIL","Above-threshold case incorrectly records renewalRequired=true.",build_047("I2-047-F02",0.0106,0.0100,True))
add_case("I2-047","F03","FAIL","gaugedThickness operand is missing.",build_047("I2-047-F03",missing="gaugedThickness"))
add_case("I2-047","F04","FAIL","steelRenewalRequired result is missing.",build_047("I2-047-F04",missing="steelRenewalRequired"))
add_case("I2-047","F05","FAIL","gaugedThickness is encoded with the wrong unit.",build_047("I2-047-F05",wrong_unit="gaugedThickness"))

# I2-066 — 7
add_case("I2-066","P01","PASS","Weld within ice-strengthened area is explicitly double continuous.",build_066("I2-066-P01",((True,"double"),)))
add_case("I2-066","P02","PASS","Out-of-scope weld is not over-constrained to the double-continuous type.",build_066("I2-066-P02",((False,"other"),)))
add_case("I2-066","P03","PASS","Universal weld rule does not create a weld where none is represented.",build_066("I2-066-P03",()))
add_case("I2-066","F01","FAIL","In-scope weld has a non-double-continuous weld type.",build_066("I2-066-F01",((True,"other"),)))
add_case("I2-066","F02","FAIL","In-scope weld is missing weldType.",build_066("I2-066-F02",((True,"double"),),missing_type_index=0))
add_case("I2-066","F03","FAIL","withinIceStrengthenedArea selector is missing; frozen R13 treats missing evidence as violation.",build_066("I2-066-F03",((True,"double"),),missing_scope_index=0))
add_case("I2-066","F04","FAIL","A mixed set contains one in-scope weld with the wrong type.",build_066("I2-066-F04",((True,"double"),(True,"other"),(False,"other"))))

# I2-067 — 6
add_case("I2-067","P01","PASS","One represented structural connection has continuity of strength confirmed.",build_067("I2-067-P01",(True,)))
add_case("I2-067","P02","PASS","All represented structural connections confirm continuity of strength.",build_067("I2-067-P02",(True,True,True)))
add_case("I2-067","P03","PASS","Universal continuity clause does not impose a connection-existence requirement.",build_067("I2-067-P03",()))
add_case("I2-067","F01","FAIL","A represented structural connection explicitly lacks continuity of strength.",build_067("I2-067-F01",(False,)))
add_case("I2-067","F02","FAIL","Mixed connections include one non-continuous connection.",build_067("I2-067-F02",(True,False,True)))
add_case("I2-067","F03","FAIL","Represented structural connection is missing strengthContinuityStatus.",build_067("I2-067-F03",(True,),missing_status_index=0))

assert len(CASE_DEFS)==56,len(CASE_DEFS)


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
    manifest_path=ROOT/"manifests"/"i2_batch_g_manifest.jsonl"
    lock_path=ROOT/"locks"/"i2_batch_g_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("Batch G manifest does not exist")
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
        actual="PASS" if ORACLES[row["requirement_id"]](g) else "FAIL"
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
    print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}")
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
    lock_path=locks_root/"i2_batch_g_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("Batch G lock already exists. Refusing to overwrite frozen fixtures.")
    clauses={
        "I2-004":"I2.1.2.2",
        "I2-005":"I2.2.5",
        "I2-041":"I2.9.3",
        "I2-042":"I2.9.4(i)",
        "I2-046":"I2.11.3",
        "I2-047":"I2.11.4",
        "I2-066":"I2.18.1",
        "I2-067":"I2.18.2",
    }
    rows=[]
    for c in CASE_DEFS:
        req=c["requirement_id"]; outdir=rdf_root/req; outdir.mkdir(parents=True,exist_ok=True)
        p=outdir/f"{c['case_id']}.ttl"; c["graph"].serialize(destination=p,format="turtle")
        rows.append({
            "requirement_id":req,
            "case_id":c["case_id"],
            "expected":c["expected"],
            "rdf_path":str(p.relative_to(ROOT)),
            "source_id":"SRC-IACS-I2-R4",
            "source_clause":clauses[req],
            "verification_mode":EXPECTED_MODES[req],
            "sourceability_grade":"D_REGULATION_SYNTHETIC",
            "source_oracle_rationale":c["rationale"],
            "generated_shacl_inspected":False,
        })
    manifest_path=manifest_root/"i2_batch_g_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row)+"\n")
    for req in REQS:
        spec={
            "requirement_id":req,
            "source_id":"SRC-IACS-I2-R4",
            "source_clause":clauses[req],
            "source_lock_id":INDEX["sourceLockId"],
            "r13_contract":CONTRACTS[req],
            "test_cases":[{"case_id":x["case_id"],"expected":x["expected"],"rationale":x["rationale"]} for x in CASE_DEFS if x["requirement_id"]==req],
            "sourceability_grade":"D_REGULATION_SYNTHETIC",
            "benchmark_policy":"Source/R13-defined behavioral oracle created without inspecting generated SHACL.",
        }
        (spec_root/f"{req}_batch_g.json").write_text(json.dumps(spec,indent=2)+"\n")
    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")
    frozen=[manifest_path]+[spec_root/f"{r}_batch_g.json" for r in REQS]
    for req in REQS:
        frozen+=sorted((rdf_root/req).glob("*.ttl"))
    lock={
        "benchmark":"I2 Behavioral Benchmark Batch G",
        "source_lock_id":INDEX["sourceLockId"],
        "requirements":REQS,
        "requirement_count":len(REQS),
        "case_count":len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl":True,
        "previous_frozen_batches_modified":False,
        "frozen_files":{str(p.relative_to(ROOT)):sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock,indent=2)+"\n")
    validator=scripts_root/"validate_i2_batch_g.py"; shutil.copy2(Path(__file__).resolve(),validator); validator.chmod(0o755)
    (ROOT/"README_I2_BATCH_G.md").write_text(
        "# I2 Behavioral Benchmark Batch G\n\n"
        "Requirements: 8\nCases: 56\n\n"
        "I2-004\nI2-005\nI2-041\nI2-042\nI2-046\nI2-047\nI2-066\nI2-067\n\n"
        "Generated SHACL was not inspected during fixture construction. I2-041 is evaluated as frozen R13 COMPLEX_READINESS: the benchmark checks required owners, paths, quantities and units but does not execute the source square-root inequality.\n\n"
        "Run:\n\npython3 scripts/validate_i2_batch_g.py\n"
    )
    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode=Path(__file__).name=="validate_i2_batch_g.py" or "--validate-only" in sys.argv
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__=="__main__":
    main()
