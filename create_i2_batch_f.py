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
        if c in seen: continue
        seen.add(c)
        if (c/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"/"requirement_term_index.json").exists(): return c
    raise RuntimeError("Could not locate NLTL_v2 repository root")

REPO=find_repo(); PIPELINE=REPO/"MVP"/"SHACL_GENERATION_PIPELINE"; ROOT=PIPELINE/"evaluation"/"BEHAVIORAL_RDF_R13"; R13=REPO/"MVP"/"BENCHMARK_VOCABULARY"/"FINAL_LOCK_R13"
INDEX=json.loads((R13/"requirement_term_index.json").read_text()); REGISTRY=json.loads((R13/"registry"/"term_registry.json").read_text()); REG={x["localName"]:x for x in REGISTRY}; CONTRACTS=INDEX["dependencyContracts"]
NLTL=Namespace("https://w3id.org/nltl/vocab#"); QUDT=Namespace("http://qudt.org/schema/qudt/"); UNIT=Namespace("http://qudt.org/vocab/unit/"); BASE="https://w3id.org/nltl/benchmark/i2-batch-f/"
REQS=["I2-021","I2-026","I2-030","I2-031","I2-032","I2-034","I2-035"]
EXPECTED_MODES={"I2-021":"DIRECT_CALCULATION","I2-026":"DIRECT_STATIC","I2-030":"COMPLEX_READINESS","I2-031":"DIRECT_STATIC","I2-032":"DIRECT_CALCULATION","I2-034":"DIRECT_STATIC","I2-035":"DIRECT_CALCULATION"}
for req in REQS:
    assert CONTRACTS[req]["status"]=="COMPLETE" and CONTRACTS[req]["verificationMode"]==EXPECTED_MODES[req]
assert CONTRACTS["I2-030"].get("formulaExecutionRequired") is False
ONTOLOGY=Graph().parse(R13/"ontology"/"nltl_benchmark_vocabulary.ttl",format="turtle")
KNOWN_NLTL={str(s).split("#",1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL))}


def new_graph(cid):
    g=Graph(); ex=Namespace(BASE+cid+"/"); g.bind("ex",ex); g.bind("nltl",NLTL); g.bind("qudt",QUDT); g.bind("unit",UNIT); g.bind("xsd",XSD); ship=ex.ship; g.add((ship,RDF.type,NLTL.ship)); return g,ex,ship

def datatype_for(term): return {"xsd:boolean":XSD.boolean,"xsd:string":XSD.string,"xsd:integer":XSD.integer,"xsd:decimal":XSD.decimal,"xsd:date":XSD.date}.get(REG[term].get("datatype",""))
def add_value(g,s,term,value,ex,name=None,unit_override=None,wrong_unit=False):
    row=REG.get(term)
    if row is None: raise RuntimeError(f"Unknown R13 term: {term}")
    if row["kind"]=="QuantityProperty":
        unit=unit_override or row.get("unitIri","")
        if not unit: raise RuntimeError(f"{term} has no frozen/context unit")
        q=ex[name or term+"Value"]; g.add((q,RDF.type,QUDT.QuantityValue)); g.add((q,QUDT.numericValue,Literal(str(value),datatype=XSD.decimal))); u=URIRef(unit)
        if wrong_unit: u=UNIT.UNITLESS if u!=UNIT.UNITLESS else UNIT.M
        g.add((q,QUDT.unit,u)); g.add((s,NLTL[term],q)); return q
    if row["kind"]=="DatatypeProperty":
        dt=datatype_for(term)
        if dt is None: raise RuntimeError(f"Unsupported datatype for {term}")
        g.add((s,NLTL[term],Literal(value,datatype=dt))); return None
    if row["kind"]=="ObjectProperty":
        if not isinstance(value,URIRef): raise RuntimeError(f"{term} requires URIRef")
        g.add((s,NLTL[term],value)); return value
    raise RuntimeError(f"Cannot add value for {row['kind']} term {term}")

def one(g,s,p):
    vals=list(g.objects(s,p)); return vals[0] if len(vals)==1 else None

def bool_value(g,s,term):
    o=one(g,s,NLTL[term])
    if o is None: return None
    try: return bool(o.toPython())
    except Exception: return None

def qty_number(g,s,term,expected_unit=None):
    expected=expected_unit or REG.get(term,{}).get("unitIri",""); vals=list(g.objects(s,NLTL[term]))
    if len(vals)!=1: return None
    q=vals[0]
    if (q,RDF.type,QUDT.QuantityValue) not in g: return None
    nums=list(g.objects(q,QUDT.numericValue)); units=list(g.objects(q,QUDT.unit))
    if len(nums)!=1 or len(units)!=1: return None
    if expected and str(units[0])!=str(expected): return None
    try: return float(nums[0])
    except Exception: return None

def close(a,b,tol=1e-8): return a is not None and b is not None and math.isclose(a,b,rel_tol=tol,abs_tol=tol)

# ---------------- I2-021 shell thickness ----------------
def build_021(cid,tnet=20,allowance=2,thickness_m=0.022,missing=None,wrong_unit=False):
    g,ex,ship=new_graph(cid); p=ex.plating; g.add((p,RDF.type,NLTL.plating)); g.add((ship,NLTL.hasPlating,p))
    if missing!="iceLoadRequiredNetPlateThickness": add_value(g,p,"iceLoadRequiredNetPlateThickness",tnet,ex,"tnet")
    if missing!="corrosionAbrasionAllowance": add_value(g,p,"corrosionAbrasionAllowance",allowance,ex,"allowance")
    if missing!="thickness": add_value(g,p,"thickness",thickness_m,ex,"thickness",wrong_unit=wrong_unit)
    return g

def oracle_021(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    plates=list(g.objects(ships[0],NLTL.hasPlating))
    if not plates: return False
    for p in plates:
        tnet=qty_number(g,p,"iceLoadRequiredNetPlateThickness"); ts=qty_number(g,p,"corrosionAbrasionAllowance"); t=qty_number(g,p,"thickness")
        if None in (tnet,ts,t) or not close(t,(tnet+ts)/1000.0): return False
    return True

# ---------------- I2-026 support fixity ----------------
def build_026(cid,condition="fixed",continuous=False,bracket=False,restraint=False,evidence=False,terminates=False,omit_support_link=False,omit_condition=False):
    g,ex,ship=new_graph(cid); m=ex.member; s=ex.support
    g.add((m,RDF.type,NLTL.framingMember)); g.add((m,RDF.type,NLTL.structuralMember)); g.add((s,RDF.type,NLTL.memberSupport)); g.add((ship,NLTL.hasStructuralMember,m))
    if not omit_support_link: g.add((m,NLTL.hasMemberSupport,s))
    add_value(g,m,"continuousThroughSupport",continuous,ex); add_value(g,m,"terminatesWithinIceStrengthenedArea",terminates,ex); add_value(g,s,"connectionBracketPresent",bracket,ex); add_value(g,s,"demonstratedRotationalRestraint",restraint,ex)
    if not omit_condition: g.add((s,NLTL.frameSupportCondition,NLTL.fixedFrameSupport if condition=="fixed" else NLTL.simpleFrameSupport))
    if evidence:
        ev=ex.restraintEvidence; g.add((ev,RDF.type,NLTL.evidenceArtifact)); g.add((s,NLTL.significantRotationalRestraintEvidence,ev))
    return g

def oracle_026(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    members=list(g.objects(ships[0],NLTL.hasStructuralMember))
    if len(members)!=1: return False
    m=members[0]; support=one(g,m,NLTL.hasMemberSupport)
    if support is None: return False
    condition=one(g,support,NLTL.frameSupportCondition)
    if condition not in {NLTL.fixedFrameSupport,NLTL.simpleFrameSupport}: return False
    cont=bool_value(g,m,"continuousThroughSupport"); term=bool_value(g,m,"terminatesWithinIceStrengthenedArea"); bracket=bool_value(g,support,"connectionBracketPresent"); restraint=bool_value(g,support,"demonstratedRotationalRestraint")
    if None in (cont,term,bracket,restraint): return False
    restraint_basis=restraint and one(g,support,NLTL.significantRotationalRestraintEvidence) is not None
    fixed_basis=cont or bracket or restraint_basis
    if term and condition!=NLTL.fixedFrameSupport: return False
    if condition==NLTL.fixedFrameSupport and not fixed_basis: return False
    if restraint and not restraint_basis: return False
    return True

# ---------------- I2-030 section-modulus readiness ----------------
def build_030(cid,omega=90,missing=None,omit_plating_link=False,omit_member_link=False,oblique_missing=None):
    g,ex,ship=new_graph(cid); calc=ex.calc; member=ex.member; plating=ex.plating
    g.add((calc,RDF.type,NLTL.calculationCase)); g.add((calc,RDF.type,NLTL.localFrameSectionCalculationCase)); g.add((member,RDF.type,NLTL.structuralMember)); g.add((plating,RDF.type,NLTL.plating))
    g.add((ship,NLTL.hasCalculationCase,calc)); g.add((member,NLTL.hasLocalFrameSectionCalculationCase,calc))
    if not omit_plating_link: g.add((calc,NLTL.sectionCalculationCasePlating,plating))
    if not omit_member_link: g.add((calc,NLTL.sectionCalculationCaseStructuralMember,member))
    vals=[("netLocalFrameFlangeArea",60,member,"afn"),("netAttachedShellPlateThickness",10,member,"tpn"),("frameSpacing",0.5,member,"spacing"),("webHeight",300,member,"hw"),("netWebThickness",12,member,"twn"),("localFrameFlangeCentreHeight",330,member,"hfc"),("webAngleToShellPlate",90,member,"phi"),("webToFlangeCentreDistance",20,member,"bw"),("framingAngleOmega",omega,plating,"omega"),("plasticNeutralAxisHeight",120,calc,"zna"),("netEffectivePlasticSectionModulus",500,member,"zp")]
    for term,val,owner,name in vals:
        if missing!=term: add_value(g,owner,term,val,ex,name)
    if 20<omega<70:
        lo=ex["lower"]; hi=ex["upper"]; g.add((lo,RDF.type,NLTL.interpolationPoint)); g.add((hi,RDF.type,NLTL.interpolationPoint))
        if oblique_missing!="lowerLink": g.add((calc,NLTL.interpolationLowerEndpoint,lo))
        if oblique_missing!="upperLink": g.add((calc,NLTL.interpolationUpperEndpoint,hi))
        if oblique_missing!="lowerCoordinate": add_value(g,lo,"interpolationPointCoordinate",20,ex,"loCoord")
        if oblique_missing!="upperCoordinate": add_value(g,hi,"interpolationPointCoordinate",70,ex,"hiCoord")
        if oblique_missing!="lowerResult": add_value(g,lo,"interpolationPointResult",450,ex,"loResult",unit_override=str(UNIT.CentiM3))
        if oblique_missing!="upperResult": add_value(g,hi,"interpolationPointResult",520,ex,"hiResult",unit_override=str(UNIT.CentiM3))
    return g

def oracle_030(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    ship=ships[0]; calcs=list(g.objects(ship,NLTL.hasCalculationCase))
    if len(calcs)!=1: return False
    c=calcs[0]; member=one(g,c,NLTL.sectionCalculationCaseStructuralMember); plating=one(g,c,NLTL.sectionCalculationCasePlating)
    if member is None or plating is None: return False
    if one(g,member,NLTL.hasLocalFrameSectionCalculationCase)!=c: return False
    for t in ["netLocalFrameFlangeArea","netAttachedShellPlateThickness","frameSpacing","webHeight","netWebThickness","localFrameFlangeCentreHeight","webAngleToShellPlate","webToFlangeCentreDistance","netEffectivePlasticSectionModulus"]:
        if qty_number(g,member,t) is None: return False
    omega=qty_number(g,plating,"framingAngleOmega")
    if omega is None or qty_number(g,c,"plasticNeutralAxisHeight") is None: return False
    afn=qty_number(g,member,"netLocalFrameFlangeArea"); tpn=qty_number(g,member,"netAttachedShellPlateThickness"); spacing=qty_number(g,member,"frameSpacing")
    if not (100*afn > 1000*tpn*spacing): return False
    if 20<omega<70:
        lo=one(g,c,NLTL.interpolationLowerEndpoint); hi=one(g,c,NLTL.interpolationUpperEndpoint)
        if lo is None or hi is None: return False
        if qty_number(g,lo,"interpolationPointCoordinate") is None or qty_number(g,hi,"interpolationPointCoordinate") is None: return False
        if qty_number(g,lo,"interpolationPointResult",str(UNIT.CentiM3)) is None or qty_number(g,hi,"interpolationPointResult",str(UNIT.CentiM3)) is None: return False
    return True

# ---------------- I2-031 bottom/transverse side local frames ----------------
def build_031(cid,location="bottom",demand=100,strength=100,orientation_ok=True,transverse=True,include_member=True,missing=None):
    g,ex,ship=new_graph(cid)
    if not include_member: return g
    m=ex.member; lc=ex.loadcase; g.add((m,RDF.type,NLTL.structuralMember)); g.add((m,RDF.type,NLTL.localFrame)); g.add((lc,RDF.type,NLTL.loadCase)); g.add((ship,NLTL.hasStructuralMember,m)); g.add((m,NLTL.hasStructuralMemberLoadCase,lc)); g.add((m,NLTL.frameProfileType,NLTL.flatBarSection))
    loc=NLTL.bottomStructureLocation if location=="bottom" else NLTL.sideStructureLocation; g.add((m,NLTL.structuralLocation,loc)); add_value(g,m,"transverseFrameOrientation",transverse,ex)
    if missing!="plasticStrength": add_value(g,m,"plasticStrength",strength,ex,"strength")
    if missing!="midspanPlasticCollapseLoad": add_value(g,m,"midspanPlasticCollapseLoad",strength,ex,"collapse")
    if missing!="combinedShearAndBendingDemand": add_value(g,lc,"combinedShearAndBendingDemand",demand,ex,"demand",unit_override=str(UNIT.KiloN))
    if location=="bottom":
        add_value(g,lc,"patchLoad",50,ex,"patch")
        g.add((lc,NLTL.loadPatchOrientation,NLTL.loadPatchHeightParallelToFrame if orientation_ok else ex.wrongOrientation))
        if not orientation_ok: g.add((ex.wrongOrientation,RDF.type,NLTL.loadPatchOrientationValue))
    return g

def oracle_031(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    members=list(g.objects(ships[0],NLTL.hasStructuralMember))
    if not members: return True
    for m in members:
        loc=one(g,m,NLTL.structuralLocation); transverse=bool_value(g,m,"transverseFrameOrientation")
        applicable=loc==NLTL.bottomStructureLocation or (loc==NLTL.sideStructureLocation and transverse is True)
        if not applicable: continue
        strength=qty_number(g,m,"plasticStrength"); collapse=qty_number(g,m,"midspanPlasticCollapseLoad")
        if strength is None or collapse is None or not close(strength,collapse): return False
        lcs=list(g.objects(m,NLTL.hasStructuralMemberLoadCase))
        if not lcs: return False
        for lc in lcs:
            demand=qty_number(g,lc,"combinedShearAndBendingDemand",str(UNIT.KiloN))
            if demand is None or demand>strength+1e-9: return False
            if loc==NLTL.bottomStructureLocation:
                if one(g,lc,NLTL.loadPatchOrientation)!=NLTL.loadPatchHeightParallelToFrame: return False
                if qty_number(g,lc,"patchLoad") is None: return False
    return True

# ---------------- I2-032 transverse shear-area calculation ----------------
def at_transverse(a,b,s,af,ppf,pavg,sy): return 10000.0*0.5*min(a,b)*s*(af*ppf*pavg)/(0.577*sy)
def build_032(cid,a=2.0,b=1.0,s=0.5,af=1.0,ppf=1.2,pavg=2.0,sy=235,aw_cm2=None,at_cm2=None,missing=None,wrong_unit=False):
    g,ex,ship=new_graph(cid); expected=at_transverse(a,b,s,af,ppf,pavg,sy); at_cm2=expected if at_cm2 is None else at_cm2; aw_cm2=expected if aw_cm2 is None else aw_cm2
    vals=[("frameSpan",a,"a"),("span",a,"span"),("loadPatchHeight",b,"b"),("frameSpacing",s,"s"),("hullAreaFactor",af,"af"),("selectedHullAreaFactor",af,"saf"),("peakPressureFactor",ppf,"ppf"),("averageIcePressure",pavg,"pavg"),("yieldStrength",sy,"sy"),("requiredTransverseFrameShearArea",at_cm2,"at"),("shearArea",aw_cm2/10000.0,"aw")]
    for term,val,name in vals:
        if missing!=term: add_value(g,ship,term,val,ex,name,wrong_unit=(wrong_unit and term=="requiredTransverseFrameShearArea"))
    return g

def oracle_032(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    s=ships[0]; names=["frameSpan","span","loadPatchHeight","frameSpacing","hullAreaFactor","selectedHullAreaFactor","peakPressureFactor","averageIcePressure","yieldStrength","requiredTransverseFrameShearArea","shearArea"]; v={t:qty_number(g,s,t) for t in names}
    if any(v[t] is None for t in names): return False
    if not close(v["frameSpan"],v["span"]) or not close(v["hullAreaFactor"],v["selectedHullAreaFactor"]): return False
    expected=at_transverse(v["frameSpan"],v["loadPatchHeight"],v["frameSpacing"],v["selectedHullAreaFactor"],v["peakPressureFactor"],v["averageIcePressure"],v["yieldStrength"])
    return close(v["requiredTransverseFrameShearArea"],expected) and v["shearArea"]*10000.0+1e-8>=expected

# ---------------- I2-034 longitudinal side-frame universal ----------------
def build_034(cid,demands=(80,),strength=100,include_member=True,side=True,longitudinal=True,missing=None):
    g,ex,ship=new_graph(cid)
    if not include_member: return g
    m=ex.member; g.add((m,RDF.type,NLTL.structuralMember)); g.add((m,RDF.type,NLTL.longitudinalLocalFrame)); g.add((ship,NLTL.hasStructuralMember,m)); g.add((m,NLTL.structuralLocation,NLTL.sideStructureLocation if side else NLTL.bottomStructureLocation)); add_value(g,m,"longitudinalFrameOrientation",longitudinal,ex); add_value(g,m,"sideStructureApplicability",side,ex)
    if missing!="plasticStrength": add_value(g,m,"plasticStrength",strength,ex,"strength")
    if missing!="midspanPlasticCollapseLoad": add_value(g,m,"midspanPlasticCollapseLoad",strength,ex,"collapse")
    for i,d in enumerate(demands):
        lc=ex[f"load{i+1}"]; g.add((lc,RDF.type,NLTL.loadCase)); g.add((m,NLTL.hasStructuralMemberLoadCase,lc)); add_value(g,lc,"combinedShearAndBendingDemand",d,ex,f"demand{i+1}",unit_override=str(UNIT.KiloN))
    return g

def oracle_034(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    members=list(g.objects(ships[0],NLTL.hasStructuralMember))
    if not members: return True
    for m in members:
        applicable=(one(g,m,NLTL.structuralLocation)==NLTL.sideStructureLocation and bool_value(g,m,"longitudinalFrameOrientation") is True)
        if not applicable: continue
        strength=qty_number(g,m,"plasticStrength"); collapse=qty_number(g,m,"midspanPlasticCollapseLoad")
        if strength is None or collapse is None or not close(strength,collapse): return False
        lcs=list(g.objects(m,NLTL.hasStructuralMemberLoadCase))
        if not lcs: return False
        for lc in lcs:
            d=qty_number(g,lc,"combinedShearAndBendingDemand",str(UNIT.KiloN))
            if d is None or d>strength+1e-9: return False
    return True

# ---------------- I2-035 longitudinal shear-area calculation ----------------
def al_longitudinal(a,b,s,af,ppf,pavg,sy):
    bp=b/s; b2=b*(1-0.25*bp) if bp<2 else s; k0=1-0.3/bp; b1=k0*b2; return 10000.0*(af*ppf*pavg)*0.5*b1*a/(0.577*sy)
def build_035(cid,a=2.0,b=0.75,s=0.5,af=1.0,ppf=1.0,pavg=2.0,sy=235,aw_cm2=None,al_cm2=None,missing=None):
    g,ex,ship=new_graph(cid); expected=al_longitudinal(a,b,s,af,ppf,pavg,sy); al_cm2=expected if al_cm2 is None else al_cm2; aw_cm2=expected if aw_cm2 is None else aw_cm2
    vals=[("frameSpan",a,"a"),("loadPatchHeight",b,"b"),("frameSpacing",s,"s"),("selectedHullAreaFactor",af,"af"),("peakPressureFactor",ppf,"ppf"),("averageIcePressure",pavg,"pavg"),("yieldStrength",sy,"sy"),("requiredLongitudinalFrameShearArea",al_cm2,"al"),("shearArea",aw_cm2/10000.0,"aw")]
    for term,val,name in vals:
        if missing!=term: add_value(g,ship,term,val,ex,name)
    return g

def oracle_035(g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    s=ships[0]; names=["frameSpan","loadPatchHeight","frameSpacing","selectedHullAreaFactor","peakPressureFactor","averageIcePressure","yieldStrength","requiredLongitudinalFrameShearArea","shearArea"]; v={t:qty_number(g,s,t) for t in names}
    if any(v[t] is None for t in names): return False
    if v["frameSpacing"]<=0 or v["loadPatchHeight"]<=0: return False
    expected=al_longitudinal(v["frameSpan"],v["loadPatchHeight"],v["frameSpacing"],v["selectedHullAreaFactor"],v["peakPressureFactor"],v["averageIcePressure"],v["yieldStrength"])
    return close(v["requiredLongitudinalFrameShearArea"],expected) and v["shearArea"]*10000.0+1e-8>=expected

ORACLES={"I2-021":oracle_021,"I2-026":oracle_026,"I2-030":oracle_030,"I2-031":oracle_031,"I2-032":oracle_032,"I2-034":oracle_034,"I2-035":oracle_035}
CASE_DEFS=[]
def add_case(req,suffix,expected,rationale,graph): CASE_DEFS.append({"requirement_id":req,"case_id":f"{req}-{suffix}","expected":expected,"rationale":rationale,"graph":graph})

# I2-021 — 6
add_case("I2-021","P01","PASS","Shell thickness equals tnet plus corrosion/abrasion allowance after mm-to-m conversion required by frozen R13 units.",build_021("I2-021-P01"))
add_case("I2-021","P02","PASS","Zero corrosion allowance gives thickness exactly equal to net ice-load thickness.",build_021("I2-021-P02",tnet=18,allowance=0,thickness_m=0.018))
add_case("I2-021","F01","FAIL","Reported shell thickness is below tnet+ts.",build_021("I2-021-F01",thickness_m=0.021))
add_case("I2-021","F02","FAIL","Reported shell thickness is above tnet+ts rather than equal to the required expression.",build_021("I2-021-F02",thickness_m=0.023))
add_case("I2-021","F03","FAIL","Required corrosion/abrasion allowance operand is missing.",build_021("I2-021-F03",missing="corrosionAbrasionAllowance"))
add_case("I2-021","F04","FAIL","Thickness result is encoded with the wrong unit.",build_021("I2-021-F04",wrong_unit=True))

# I2-026 — 8
add_case("I2-026","P01","PASS","Continuous-through-support framing is represented with fixed support.",build_026("I2-026-P01",condition="fixed",continuous=True))
add_case("I2-026","P02","PASS","Connection bracket provides a source-grounded basis for fixed support.",build_026("I2-026-P02",condition="fixed",bracket=True))
add_case("I2-026","P03","PASS","Without a fixity basis, simple support is conservatively assumed.",build_026("I2-026-P03",condition="simple"))
add_case("I2-026","P04","PASS","Demonstrated rotational restraint plus evidence provides a basis for fixed support.",build_026("I2-026-P04",condition="fixed",restraint=True,evidence=True))
add_case("I2-026","F01","FAIL","Fixed support is claimed without continuity, bracket, or demonstrated restraint evidence.",build_026("I2-026-F01",condition="fixed"))
add_case("I2-026","F02","FAIL","Rotational restraint is claimed but significant-restraint evidence is missing.",build_026("I2-026-F02",condition="fixed",restraint=True,evidence=False))
add_case("I2-026","F03","FAIL","Framing terminating within an ice-strengthened area is represented as simply supported.",build_026("I2-026-F03",condition="simple",terminates=True))
add_case("I2-026","F04","FAIL","Member support node is not connected through the frozen hasMemberSupport path.",build_026("I2-026-F04",condition="fixed",continuous=True,omit_support_link=True))

# I2-030 — 9
add_case("I2-030","P01","PASS","Non-oblique z_na branch has all selectors, operands, relationships and results required by frozen R13 readiness.",build_030("I2-030-P01",omega=90))
add_case("I2-030","P02","PASS","Oblique 45-degree case includes both interpolation endpoints and context-specific section-modulus values.",build_030("I2-030-P02",omega=45))
add_case("I2-030","F01","FAIL","Branch selector netLocalFrameFlangeArea is missing.",build_030("I2-030-F01",missing="netLocalFrameFlangeArea"))
add_case("I2-030","F02","FAIL","Required net attached shell-plate thickness is missing.",build_030("I2-030-F02",missing="netAttachedShellPlateThickness"))
add_case("I2-030","F03","FAIL","Required webHeight operand is missing.",build_030("I2-030-F03",missing="webHeight"))
add_case("I2-030","F04","FAIL","Required net effective plastic section modulus result is missing.",build_030("I2-030-F04",missing="netEffectivePlasticSectionModulus"))
add_case("I2-030","F05","FAIL","Calculation case is not linked to plating through sectionCalculationCasePlating.",build_030("I2-030-F05",omit_plating_link=True))
add_case("I2-030","F06","FAIL","Oblique case is missing the lower interpolation endpoint relationship.",build_030("I2-030-F06",omega=45,oblique_missing="lowerLink"))
add_case("I2-030","F07","FAIL","Oblique case is missing an interpolation-point result.",build_030("I2-030-F07",omega=45,oblique_missing="upperResult"))

# I2-031 — 7
add_case("I2-031","P01","PASS","Bottom local frame at capacity has correct patch orientation and demand equal to plastic strength.",build_031("I2-031-P01",location="bottom",demand=100,strength=100))
add_case("I2-031","P02","PASS","Transverse local frame in side structure has demand below plastic strength.",build_031("I2-031-P02",location="side",demand=80,strength=100,transverse=True))
add_case("I2-031","P03","PASS","Universal clause does not invent a local frame when none is represented.",build_031("I2-031-P03",include_member=False))
add_case("I2-031","F01","FAIL","Applicable local-frame demand exceeds plastic strength.",build_031("I2-031-F01",location="bottom",demand=101,strength=100))
add_case("I2-031","F02","FAIL","Bottom-structure patch orientation is not parallel to the frame direction.",build_031("I2-031-F02",location="bottom",orientation_ok=False))
add_case("I2-031","F03","FAIL","Plastic strength/midspan-collapse evidence is incomplete.",build_031("I2-031-F03",location="side",missing="midspanPlasticCollapseLoad"))
add_case("I2-031","F04","FAIL","Applicable load case is missing combined shear-and-bending demand.",build_031("I2-031-F04",location="side",missing="combinedShearAndBendingDemand"))

# I2-032 — 6
base_at=at_transverse(2.0,1.0,0.5,1.0,1.2,2.0,235)
add_case("I2-032","P01","PASS","Transverse-frame shear area equals required At with LL governed by load-patch height b<a.",build_032("I2-032-P01",a=2,b=1,aw_cm2=base_at))
add_case("I2-032","P02","PASS","Actual shear area exceeds required At with LL governed by frame span a<b.",build_032("I2-032-P02",a=1,b=2,aw_cm2=base_at+20))
add_case("I2-032","F01","FAIL","Actual shear area is below required At.",build_032("I2-032-F01",a=2,b=1,aw_cm2=base_at-1))
add_case("I2-032","F02","FAIL","Stored requiredTransverseFrameShearArea does not equal the source equation.",build_032("I2-032-F02",a=2,b=1,at_cm2=base_at+10,aw_cm2=base_at+20))
add_case("I2-032","F03","FAIL","Formula operand loadPatchHeight is missing.",build_032("I2-032-F03",missing="loadPatchHeight"))
add_case("I2-032","F04","FAIL","Required transverse-frame shear-area result uses the wrong unit.",build_032("I2-032-F04",wrong_unit=True))

# I2-034 — 6
add_case("I2-034","P01","PASS","Longitudinal side local frame has demand below plastic strength.",build_034("I2-034-P01",demands=(80,),strength=100))
add_case("I2-034","P02","PASS","All represented load cases for a longitudinal side local frame satisfy the universal comparison.",build_034("I2-034-P02",demands=(70,90,100),strength=100))
add_case("I2-034","P03","PASS","Universal clause does not require inventing a longitudinal frame when none is represented.",build_034("I2-034-P03",include_member=False))
add_case("I2-034","F01","FAIL","One longitudinal side-frame load case exceeds plastic strength.",build_034("I2-034-F01",demands=(80,101),strength=100))
add_case("I2-034","F02","FAIL","Plastic-strength definition is missing the midspan-collapse load.",build_034("I2-034-F02",missing="midspanPlasticCollapseLoad"))
add_case("I2-034","F03","FAIL","Applicable longitudinal side frame is missing plasticStrength.",build_034("I2-034-F03",missing="plasticStrength"))

# I2-035 — 6
base_al=al_longitudinal(2.0,0.75,0.5,1.0,1.0,2.0,235)
add_case("I2-035","P01","PASS","Longitudinal shear-area branch with b/s<2 satisfies Aw=AL.",build_035("I2-035-P01",a=2,b=0.75,s=0.5,aw_cm2=base_al))
base_al2=al_longitudinal(2.0,1.0,0.5,1.0,1.0,2.0,235)
add_case("I2-035","P02","PASS","Boundary b/s=2 uses the b2=s branch and actual shear area exceeds AL.",build_035("I2-035-P02",a=2,b=1.0,s=0.5,aw_cm2=base_al2+10))
add_case("I2-035","F01","FAIL","Actual longitudinal shear area is below required AL.",build_035("I2-035-F01",a=2,b=0.75,s=0.5,aw_cm2=base_al-1))
add_case("I2-035","F02","FAIL","Stored requiredLongitudinalFrameShearArea does not equal the source piecewise equation.",build_035("I2-035-F02",a=2,b=0.75,s=0.5,al_cm2=base_al+5,aw_cm2=base_al+10))
add_case("I2-035","F03","FAIL","Peak-pressure-factor operand is missing.",build_035("I2-035-F03",missing="peakPressureFactor"))
add_case("I2-035","F04","FAIL","Load-patch height needed by the source b/s branch is missing from the RDF case.",build_035("I2-035-F04",missing="loadPatchHeight"))

assert len(CASE_DEFS)==48,len(CASE_DEFS)

def graph_vocab_ok(g):
    local=set()
    for s,p,o in g:
        for node in (s,p,o):
            text=str(node)
            if text.startswith(str(NLTL)): local.add(text.split("#",1)[1])
    unknown=sorted(x for x in local if x not in KNOWN_NLTL); return not unknown,unknown

def graph_qudt_ok(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1: return False
    return True

def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def validate_existing(check_hashes=True):
    manifest_path=ROOT/"manifests"/"i2_batch_f_manifest.jsonl"; lock_path=ROOT/"locks"/"i2_batch_f_fixture_lock.json"
    if not manifest_path.exists(): raise SystemExit("Batch F manifest does not exist")
    rows=[json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]; syntax=vocab=qudt=agreement=0; diagnostics=[]
    for row in rows:
        p=ROOT/row["rdf_path"]
        try: g=Graph().parse(p,format="turtle"); syntax+=1
        except Exception as e: diagnostics.append((row["case_id"],"parse",str(e))); continue
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
        if not lock_path.exists(): hash_ok=False; diagnostics.append(("lock","hash","lock file missing"))
        else:
            lock=json.loads(lock_path.read_text())
            for rel,expected_hash in lock["frozen_files"].items():
                p=ROOT/rel
                if not p.exists() or sha256(p)!=expected_hash: hash_ok=False; diagnostics.append((rel,"hash","mismatch"))
    n=len(rows); print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}"); print(f"RDF files: {n}"); print(f"Syntactically valid: {syntax}"); print(f"Vocabulary validation count: {vocab}"); print(f"QUDT/unit validation count: {qudt}"); print(f"Source-oracle agreement count: {agreement}")
    if check_hashes: print("Frozen hashes matched: "+("YES" if hash_ok else "NO"))
    ok=syntax==vocab==qudt==agreement==n and (hash_ok if check_hashes else True); print("Overall status: "+("PASS" if ok else "FAIL"))
    if diagnostics:
        print("\nDiagnostics:")
        for d in diagnostics: print(d)
    return ok

def generate():
    rdf_root=ROOT/"rdf"/"I2"; spec_root=ROOT/"specifications"/"I2"; manifest_root=ROOT/"manifests"; locks_root=ROOT/"locks"; scripts_root=ROOT/"scripts"
    for p in [rdf_root,spec_root,manifest_root,locks_root,scripts_root]: p.mkdir(parents=True,exist_ok=True)
    lock_path=locks_root/"i2_batch_f_fixture_lock.json"
    if lock_path.exists(): raise SystemExit("Batch F lock already exists. Refusing to overwrite frozen fixtures.")
    clauses={"I2-021":"I2.4.1","I2-026":"I2.5.3","I2-030":"I2.5.8-I2.5.9","I2-031":"I2.6.1","I2-032":"I2.6.2","I2-034":"I2.7.1","I2-035":"I2.7.2"}
    rows=[]
    for c in CASE_DEFS:
        req=c["requirement_id"]; outdir=rdf_root/req; outdir.mkdir(parents=True,exist_ok=True); p=outdir/f"{c['case_id']}.ttl"; c["graph"].serialize(destination=p,format="turtle")
        rows.append({"requirement_id":req,"case_id":c["case_id"],"expected":c["expected"],"rdf_path":str(p.relative_to(ROOT)),"source_id":"SRC-IACS-I2-R4","source_clause":clauses[req],"verification_mode":EXPECTED_MODES[req],"sourceability_grade":"D_REGULATION_SYNTHETIC","source_oracle_rationale":c["rationale"],"generated_shacl_inspected":False})
    manifest_path=manifest_root/"i2_batch_f_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows: f.write(json.dumps(row)+"\n")
    for req in REQS:
        spec={"requirement_id":req,"source_id":"SRC-IACS-I2-R4","source_clause":clauses[req],"source_lock_id":INDEX["sourceLockId"],"r13_contract":CONTRACTS[req],"test_cases":[{"case_id":x["case_id"],"expected":x["expected"],"rationale":x["rationale"]} for x in CASE_DEFS if x["requirement_id"]==req],"sourceability_grade":"D_REGULATION_SYNTHETIC","benchmark_policy":"Source/R13-defined behavioral oracle created without inspecting generated SHACL."}
        (spec_root/f"{req}.json").write_text(json.dumps(spec,indent=2)+"\n")
    print("Pre-freeze validation")
    if not validate_existing(False): raise SystemExit("Pre-freeze validation failed. No lock written.")
    frozen=[manifest_path]+[spec_root/f"{r}.json" for r in REQS]
    for req in REQS: frozen+=sorted((rdf_root/req).glob("*.ttl"))
    lock={"benchmark":"I2 Behavioral Benchmark Batch F","source_lock_id":INDEX["sourceLockId"],"requirements":REQS,"requirement_count":len(REQS),"case_count":len(CASE_DEFS),"generated_without_inspecting_generated_shacl":True,"previous_frozen_batches_modified":False,"frozen_files":{str(p.relative_to(ROOT)):sha256(p) for p in frozen}}
    lock_path.write_text(json.dumps(lock,indent=2)+"\n"); validator=scripts_root/"validate_i2_batch_f.py"; shutil.copy2(Path(__file__).resolve(),validator); validator.chmod(0o755)
    (ROOT/"README_I2_BATCH_F.md").write_text("# I2 Behavioral Benchmark Batch F\n\nRequirements: 7\nCases: 48\n\nI2-021\nI2-026\nI2-030\nI2-031\nI2-032\nI2-034\nI2-035\n\nGenerated SHACL was not inspected during fixture construction. COMPLEX_READINESS I2-030 checks selectors, operands, paths, results and interpolation readiness without executing nonlinear section-modulus equations. I2-035 includes loadPatchHeight because the source piecewise b/s equation requires it and the term exists in frozen R13, even though the I2-035 dependency-contract operand list omits it; the contract itself is not modified.\n\nRun:\n\npython3 scripts/validate_i2_batch_f.py\n")
    print("\nFrozen validation")
    if not validate_existing(True): raise SystemExit("Post-freeze validation failed")

def main():
    validation_mode=Path(__file__).name=="validate_i2_batch_f.py" or "--validate-only" in sys.argv
    if validation_mode: raise SystemExit(0 if validate_existing(True) else 1)
    generate()
if __name__=="__main__": main()
