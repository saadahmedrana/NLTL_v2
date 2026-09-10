from pathlib import Path
import json
import hashlib
import math
import shutil
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD


# ============================================================
# LOCATE REPOSITORY / LOAD FROZEN R13
# ============================================================

def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent] + list(Path(__file__).resolve().parents)
    seen = set()
    for c in candidates:
        c = c.resolve()
        if c in seen:
            continue
        seen.add(c)
        if (c / "MVP" / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13" / "requirement_term_index.json").exists():
            return c
    raise RuntimeError("Could not locate NLTL_v2 repository root")


REPO = find_repo()
PIPELINE = REPO / "MVP" / "SHACL_GENERATION_PIPELINE"
ROOT = PIPELINE / "evaluation" / "BEHAVIORAL_RDF_R13"
R13 = REPO / "MVP" / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"

INDEX = json.loads((R13 / "requirement_term_index.json").read_text())
REGISTRY = json.loads((R13 / "registry" / "term_registry.json").read_text())
REG = {x["localName"]: x for x in REGISTRY}
CONTRACTS = INDEX["dependencyContracts"]

NLTL = Namespace("https://w3id.org/nltl/vocab#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-d/"

REQS = [
    "TRF-029",
    "TRF-030",
    "TRF-031",
    "TRF-032",
    "TRF-034",
    "TRF-035",
    "TRF-036",
    "TRF-037",
]

EXPECTED_MODES = {
    "TRF-029": "DIRECT_STATIC",
    "TRF-030": "COMPLEX_READINESS",
    "TRF-031": "DIRECT_CALCULATION",
    "TRF-032": "DIRECT_STATIC",
    "TRF-034": "COMPLEX_READINESS",
    "TRF-035": "DIRECT_STATIC",
    "TRF-036": "DIRECT_STATIC",
    "TRF-037": "DIRECT_CALCULATION",
}

for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]

for req in ["TRF-030", "TRF-034"]:
    assert CONTRACTS[req].get("formulaExecutionRequired") is False

ONTOLOGY = Graph().parse(R13 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
KNOWN_NLTL = {
    str(s).split("#", 1)[1]
    for s in set(ONTOLOGY.subjects())
    if str(s).startswith(str(NLTL))
}

ICE_CLASSES = {
    "IA Super": NLTL.iceClassIaSuper,
    "IA": NLTL.iceClassIa,
    "IB": NLTL.iceClassIb,
    "IC": NLTL.iceClassIc,
    "II": NLTL.iceClassIi,
    "III": NLTL.iceClassIii,
}


# ============================================================
# RDF HELPERS
# ============================================================

def new_graph(cid):
    g = Graph()
    ex = Namespace(BASE + cid + "/")
    g.bind("ex", ex)
    g.bind("nltl", NLTL)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("xsd", XSD)
    ship = ex.ship
    g.add((ship, RDF.type, NLTL.ship))
    return g, ex, ship


def datatype_for(term):
    return {
        "xsd:boolean": XSD.boolean,
        "xsd:string": XSD.string,
        "xsd:integer": XSD.integer,
        "xsd:decimal": XSD.decimal,
        "xsd:date": XSD.date,
    }.get(REG[term].get("datatype", ""))


def add_value(g, s, term, value, ex, name=None, unit_override=None, wrong_unit=False):
    row = REG.get(term)
    if row is None:
        raise RuntimeError(f"Unknown R13 term: {term}")
    kind = row["kind"]

    if kind == "QuantityProperty":
        unit = unit_override or row.get("unitIri", "")
        if not unit:
            raise RuntimeError(f"{term} has no frozen unit; provide an explicit case-local source unit")
        q = ex[name or term + "Value"]
        g.add((q, RDF.type, QUDT.QuantityValue))
        g.add((q, QUDT.numericValue, Literal(str(value), datatype=XSD.decimal)))
        u = URIRef(unit)
        if wrong_unit:
            u = UNIT.UNITLESS if str(u) != str(UNIT.UNITLESS) else UNIT.M
        g.add((q, QUDT.unit, u))
        g.add((s, NLTL[term], q))
        return q

    if kind == "DatatypeProperty":
        dt = datatype_for(term)
        if dt is None:
            raise RuntimeError(f"Unsupported datatype for {term}")
        g.add((s, NLTL[term], Literal(value, datatype=dt)))
        return None

    if kind == "ObjectProperty":
        if not isinstance(value, URIRef):
            raise RuntimeError(f"{term} requires URIRef")
        g.add((s, NLTL[term], value))
        return value

    raise RuntimeError(f"Cannot add value for {kind} term {term}")


def add_case_local_quantity(g, s, term, value, ex, unit_uri, name=None):
    """Use when frozen R13 intentionally claims no external unit IRI.

    TRF-032's generic scantling quantities are comparable quantities, but R13's
    unitDecisionStatus explicitly declines to claim one external unit. A single
    case-local unit URI is therefore used consistently across the three values;
    the oracle checks unit identity and numeric ordering only.
    """
    row = REG.get(term)
    if row is None or row.get("kind") != "QuantityProperty":
        raise RuntimeError(f"{term} is not a frozen R13 QuantityProperty")
    q = ex[name or term + "Value"]
    g.add((q, RDF.type, QUDT.QuantityValue))
    g.add((q, QUDT.numericValue, Literal(str(value), datatype=XSD.decimal)))
    g.add((q, QUDT.unit, URIRef(unit_uri)))
    g.add((s, NLTL[term], q))
    return q


def one(g, s, p):
    vals = list(g.objects(s, p))
    return vals[0] if len(vals) == 1 else None


def bool_value(g, s, term):
    o = one(g, s, NLTL[term])
    if o is None:
        return None
    try:
        return bool(o.toPython())
    except Exception:
        return None


def string_value(g, s, term):
    o = one(g, s, NLTL[term])
    return None if o is None else str(o)


def obj_value(g, s, term):
    return one(g, s, NLTL[term])


def qty_value_unit(g, s, term, expected_unit=None):
    vals = list(g.objects(s, NLTL[term]))
    if len(vals) != 1:
        return None, None
    q = vals[0]
    if (q, RDF.type, QUDT.QuantityValue) not in g:
        return None, None
    nums = list(g.objects(q, QUDT.numericValue))
    units = list(g.objects(q, QUDT.unit))
    if len(nums) != 1 or len(units) != 1:
        return None, None
    if expected_unit and str(units[0]) != str(expected_unit):
        return None, None
    try:
        return float(nums[0]), str(units[0])
    except Exception:
        return None, None


def qty_number(g, s, term, expected_unit=None):
    expected = expected_unit or REG.get(term, {}).get("unitIri", "")
    v, _ = qty_value_unit(g, s, term, expected if expected else None)
    return v


def close(a, b, tol=1e-8):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol)


CASE_DEFS = []


def add_case(req, suffix, expected, rationale, graph):
    CASE_DEFS.append({
        "requirement_id": req,
        "case_id": f"{req}-{suffix}",
        "expected": expected,
        "rationale": rationale,
        "graph": graph,
    })


# ============================================================
# TRF-029 — APPROVED DIRECT-ANALYSIS SUBSTITUTION
# ============================================================

def build_029(cid, used=True, prescribed=False, approval=NLTL.evidenceStateApproved,
              arrangement="non-standard grillage detail", omit=None):
    g, ex, ship = new_graph(cid)
    if omit != "directAnalysisUsed":
        add_value(g, ship, "directAnalysisUsed", used, ex)
    if used:
        if omit != "prescribedProcedureApplicability" and prescribed is not None:
            add_value(g, ship, "prescribedProcedureApplicability", prescribed, ex)
        if omit != "directAnalysisApprovalStatus" and approval is not None:
            add_value(g, ship, "directAnalysisApprovalStatus", approval, ex)
        if omit != "structuralArrangement" and arrangement is not None:
            add_value(g, ship, "structuralArrangement", arrangement, ex)
    return g


def oracle_029(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    used = bool_value(g, ship, "directAnalysisUsed")
    if used is None:
        return False
    if not used:
        return True
    return (
        bool_value(g, ship, "prescribedProcedureApplicability") is False
        and obj_value(g, ship, "directAnalysisApprovalStatus") == NLTL.evidenceStateApproved
        and bool((string_value(g, ship, "structuralArrangement") or "").strip())
    )


add_case("TRF-029", "P01", "PASS", "Approved direct analysis replaces an inapplicable prescribed procedure and records the structural arrangement.", build_029("TRF-029-P01"))
add_case("TRF-029", "P02", "PASS", "Direct analysis is not used, so the substitution conditions are not activated.", build_029("TRF-029-P02", used=False))
add_case("TRF-029", "F01", "FAIL", "Direct analysis is used while the prescribed procedure is still marked applicable.", build_029("TRF-029-F01", prescribed=True))
add_case("TRF-029", "F02", "FAIL", "Direct analysis is used without an approval status.", build_029("TRF-029-F02", omit="directAnalysisApprovalStatus"))
add_case("TRF-029", "F03", "FAIL", "Direct analysis is used but approval is rejected rather than approved.", build_029("TRF-029-F03", approval=NLTL.evidenceStateRejected))
add_case("TRF-029", "F04", "FAIL", "Direct analysis is used without identifying the structural arrangement or detail.", build_029("TRF-029-F04", omit="structuralArrangement"))
add_case("TRF-029", "F05", "FAIL", "The direct-analysis applicability selector is missing.", build_029("TRF-029-F05", omit="directAnalysisUsed"))


# ============================================================
# TRF-030 — DIRECT-ANALYSIS LOAD-PATCH READINESS
# ============================================================

def build_030(cid, missing=None, wrong_owner=None, wrong_unit=None,
              load_length_determined=True, capacity=True, combined=True):
    g, ex, ship = new_graph(cid)
    case = ex.directAnalysis
    g.add((case, RDF.type, NLTL.directAnalysisCase))
    if missing != "hasDirectAnalysisCase":
        g.add((ship, NLTL.hasDirectAnalysisCase, case))

    qvals = [
        ("icePressure", 1.20),
        ("loadPatchHeight", 0.35),
        ("loadPatchLength", 0.80),
        ("iceLoadAreaFactorCa", 0.70),
        ("verticalLoadPosition", 0.00),
        ("horizontalLoadPosition", 0.00),
        ("appliedIcePressure", 2.16),
    ]
    for term, value in qvals:
        if missing == term:
            continue
        owner = ship if wrong_owner == term else case
        add_value(g, owner, term, value, ex, term, wrong_unit=(wrong_unit == term))

    if missing != "loadLengthDeterminedFromArrangement":
        add_value(g, case, "loadLengthDeterminedFromArrangement", load_length_determined, ex)
    if missing != "capacityMinimizingLoadPositionConfirmed":
        add_value(g, case, "capacityMinimizingLoadPositionConfirmed", capacity, ex)
    if missing != "combinedBendingAndShearEvaluated":
        add_value(g, case, "combinedBendingAndShearEvaluated", combined, ex)
    return g


def oracle_030(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    case = one(g, ship, NLTL.hasDirectAnalysisCase)
    if case is None or (case, RDF.type, NLTL.directAnalysisCase) not in g:
        return False
    for term in [
        "icePressure", "loadPatchHeight", "loadPatchLength", "iceLoadAreaFactorCa",
        "verticalLoadPosition", "horizontalLoadPosition", "appliedIcePressure",
    ]:
        if qty_number(g, case, term) is None:
            return False
    if bool_value(g, case, "loadLengthDeterminedFromArrangement") is None:
        return False
    if bool_value(g, case, "capacityMinimizingLoadPositionConfirmed") is not True:
        return False
    if bool_value(g, case, "combinedBendingAndShearEvaluated") is not True:
        return False
    return True


add_case("TRF-030", "P01", "PASS", "Direct-analysis case has the complete R13 load-patch/readiness interface with arrangement-derived load length.", build_030("TRF-030-P01", load_length_determined=True))
add_case("TRF-030", "P02", "PASS", "Direct-analysis case remains readiness-complete when load length is not directly determined from the arrangement.", build_030("TRF-030-P02", load_length_determined=False))
for suffix, term in [
    ("F01", "icePressure"),
    ("F02", "loadPatchHeight"),
    ("F03", "loadPatchLength"),
    ("F04", "iceLoadAreaFactorCa"),
    ("F05", "verticalLoadPosition"),
    ("F06", "horizontalLoadPosition"),
    ("F07", "appliedIcePressure"),
    ("F08", "loadLengthDeterminedFromArrangement"),
]:
    add_case("TRF-030", suffix, "FAIL", f"Direct-analysis readiness is missing required field {term}.", build_030(f"TRF-030-{suffix}", missing=term))
add_case("TRF-030", "F09", "FAIL", "Capacity-minimising load position has not been confirmed.", build_030("TRF-030-F09", capacity=False))
add_case("TRF-030", "F10", "FAIL", "Combined bending-and-shear evaluation has not been performed.", build_030("TRF-030-F10", combined=False))
add_case("TRF-030", "F11", "FAIL", "Direct-analysis case exists but is not connected through hasDirectAnalysisCase.", build_030("TRF-030-F11", missing="hasDirectAnalysisCase"))
add_case("TRF-030", "F12", "FAIL", "Applied ice pressure is attached to the ship rather than the direct-analysis case.", build_030("TRF-030-F12", wrong_owner="appliedIcePressure"))
add_case("TRF-030", "F13", "FAIL", "Ice-pressure readiness quantity uses the wrong unit.", build_030("TRF-030-F13", wrong_unit="icePressure"))


# ============================================================
# TRF-031 — DIRECT-ANALYSIS ACCEPTANCE / BEAM-THEORY SHEAR
# ============================================================

def build_031(cid, yield_point=235.0, combined_stress=200.0, beam=False,
              yield_shear=None, allowable=None, omit=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    if yield_shear is None and yield_point is not None:
        yield_shear = yield_point / math.sqrt(3.0)
    if omit != "yieldPoint" and yield_point is not None:
        add_value(g, ship, "yieldPoint", yield_point, ex, "yieldPoint", wrong_unit=(wrong_unit == "yieldPoint"))
    if omit != "combinedBendingShearStress" and combined_stress is not None:
        add_value(g, ship, "combinedBendingShearStress", combined_stress, ex, "combinedStress", wrong_unit=(wrong_unit == "combinedBendingShearStress"))
    if omit != "yieldShearStress" and yield_shear is not None:
        add_value(g, ship, "yieldShearStress", yield_shear, ex, "yieldShear", wrong_unit=(wrong_unit == "yieldShearStress"))
    if omit != "beamTheoryUsed":
        add_value(g, ship, "beamTheoryUsed", beam, ex)
    if beam and omit != "allowableShearStress" and allowable is not None:
        add_value(g, ship, "allowableShearStress", allowable, ex, "allowableShear", wrong_unit=(wrong_unit == "allowableShearStress"))
    add_value(g, ship, "vonMisesYieldCriterion", "von Mises yield criterion", ex)
    return g


def oracle_031(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    sy = qty_number(g, ship, "yieldPoint")
    combined = qty_number(g, ship, "combinedBendingShearStress")
    tau_y = qty_number(g, ship, "yieldShearStress")
    beam = bool_value(g, ship, "beamTheoryUsed")
    if sy is None or combined is None or tau_y is None or beam is None:
        return False
    if not close(tau_y, sy / math.sqrt(3.0), tol=1e-7):
        return False
    if not (combined < sy):
        return False
    if beam:
        allowable = qty_number(g, ship, "allowableShearStress")
        if allowable is None or allowable > 0.9 * tau_y + 1e-8:
            return False
    return True


sy = 235.0
_tau = sy / math.sqrt(3.0)
add_case("TRF-031", "P01", "PASS", "Von-Mises combined stress is below yield and the derived yield shear stress is correct; beam-theory branch is inactive.", build_031("TRF-031-P01", beam=False))
add_case("TRF-031", "P02", "PASS", "Beam-theory allowable shear is exactly the permitted 0.9 tau_y boundary.", build_031("TRF-031-P02", beam=True, allowable=0.9 * _tau))
add_case("TRF-031", "P03", "PASS", "Beam-theory allowable shear is below the 0.9 tau_y limit.", build_031("TRF-031-P03", beam=True, allowable=100.0))
add_case("TRF-031", "F01", "FAIL", "Combined bending/shear stress equals the yield point; the source requires it to be lower.", build_031("TRF-031-F01", combined_stress=235.0))
add_case("TRF-031", "F02", "FAIL", "Combined bending/shear stress exceeds the yield point.", build_031("TRF-031-F02", combined_stress=240.0))
add_case("TRF-031", "F03", "FAIL", "Derived yield shear stress is inconsistent with sigma_y/sqrt(3).", build_031("TRF-031-F03", yield_shear=120.0))
add_case("TRF-031", "F04", "FAIL", "Beam-theory allowable shear exceeds 0.9 tau_y.", build_031("TRF-031-F04", beam=True, allowable=0.9 * _tau + 1.0))
add_case("TRF-031", "F05", "FAIL", "Beam-theory branch is active but allowable shear stress is missing.", build_031("TRF-031-F05", beam=True, allowable=None))
add_case("TRF-031", "F06", "FAIL", "Yield point operand is missing.", build_031("TRF-031-F06", omit="yieldPoint"))
add_case("TRF-031", "F07", "FAIL", "Beam-theory selector is missing.", build_031("TRF-031-F07", omit="beamTheoryUsed"))
add_case("TRF-031", "F08", "FAIL", "Combined stress uses the wrong unit.", build_031("TRF-031-F08", wrong_unit="combinedBendingShearStress"))


# ============================================================
# TRF-032 — CLASSIFICATION-SOCIETY MINIMUM SCANTLING FLOOR
# ============================================================

def build_032(cid, regulation=10.0, society=12.0, selected=12.0,
              omit=None, mismatch_unit=False):
    g, ex, ship = new_graph(cid)
    unit_main = str(ex.scantlingUnit)
    unit_other = str(ex.otherScantlingUnit)
    if omit != "regulationRequiredScantling":
        add_case_local_quantity(g, ship, "regulationRequiredScantling", regulation, ex, unit_main, "regulationScantling")
    if omit != "classificationSocietyRequiredScantling":
        add_case_local_quantity(g, ship, "classificationSocietyRequiredScantling", society, ex, unit_main, "societyScantling")
    if omit != "selectedDesignScantling":
        add_case_local_quantity(g, ship, "selectedDesignScantling", selected, ex, unit_other if mismatch_unit else unit_main, "selectedScantling")
    return g


def oracle_032(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    reg, ur = qty_value_unit(g, ship, "regulationRequiredScantling")
    soc, us = qty_value_unit(g, ship, "classificationSocietyRequiredScantling")
    sel, ux = qty_value_unit(g, ship, "selectedDesignScantling")
    if None in (reg, soc, sel) or not ur or not us or not ux:
        return False
    if not (ur == us == ux):
        return False
    return sel + 1e-8 >= max(reg, soc)


add_case("TRF-032", "P01", "PASS", "Classification-society baseline exceeds the ice-regulation scantling, and the selected design meets the higher society minimum.", build_032("TRF-032-P01", 10.0, 12.0, 12.0))
add_case("TRF-032", "P02", "PASS", "Ice-regulation scantling exceeds the society baseline, and the selected design meets the regulation minimum.", build_032("TRF-032-P02", 12.0, 10.0, 12.0))
add_case("TRF-032", "P03", "PASS", "Equal regulation and society minima are met exactly.", build_032("TRF-032-P03", 10.0, 10.0, 10.0))
add_case("TRF-032", "P04", "PASS", "A design scantling above both applicable minima is compliant.", build_032("TRF-032-P04", 10.0, 12.0, 13.0))
add_case("TRF-032", "F01", "FAIL", "Selected scantling is below the higher classification-society minimum.", build_032("TRF-032-F01", 10.0, 12.0, 11.9))
add_case("TRF-032", "F02", "FAIL", "Selected scantling is below the higher ice-regulation minimum.", build_032("TRF-032-F02", 12.0, 10.0, 11.9))
add_case("TRF-032", "F03", "FAIL", "Selected design scantling is missing.", build_032("TRF-032-F03", omit="selectedDesignScantling"))
add_case("TRF-032", "F04", "FAIL", "Classification-society comparator is missing.", build_032("TRF-032-F04", omit="classificationSocietyRequiredScantling"))
add_case("TRF-032", "F05", "FAIL", "Comparable scantling quantities use inconsistent source units.", build_032("TRF-032-F05", mismatch_unit=True))


# ============================================================
# TRF-034 — EFFECTIVE MEMBER CROSS-SECTION READINESS
# ============================================================

def build_034(cid, normal=True, missing=None, wrong_owner=None, wrong_unit=None, evidence=True):
    g, ex, ship = new_graph(cid)
    member = ex.member
    xsec = ex.effectiveSection
    g.add((member, RDF.type, NLTL.iceStringer))
    g.add((xsec, RDF.type, NLTL.effectiveMemberCrossSection))
    if missing != "hasEffectiveMemberCrossSection":
        g.add((member, NLTL.hasEffectiveMemberCrossSection, xsec))

    if missing != "sectionModulus":
        add_value(g, member if wrong_owner == "sectionModulus" else xsec, "sectionModulus", 2500.0, ex, "sectionModulus", wrong_unit=(wrong_unit == "sectionModulus"))
    if missing != "shearArea":
        add_value(g, member if wrong_owner == "shearArea" else xsec, "shearArea", 0.02, ex, "shearArea", wrong_unit=(wrong_unit == "shearArea"))
    if missing != "memberNormalToPlating":
        add_value(g, xsec, "memberNormalToPlating", normal, ex)

    if not normal and evidence and missing != "hasClassificationSocietySectionPropertyCalculationEvidence":
        ev = ex.evidence
        g.add((ev, RDF.type, NLTL.evidenceArtifact))
        owner = member if wrong_owner == "evidence" else xsec
        g.add((owner, NLTL.hasClassificationSocietySectionPropertyCalculationEvidence, ev))
    return g


def oracle_034(g):
    members = list(g.subjects(RDF.type, NLTL.iceStringer))
    if len(members) != 1:
        return False
    member = members[0]
    xsec = one(g, member, NLTL.hasEffectiveMemberCrossSection)
    if xsec is None or (xsec, RDF.type, NLTL.effectiveMemberCrossSection) not in g:
        return False
    if qty_number(g, xsec, "sectionModulus") is None or qty_number(g, xsec, "shearArea") is None:
        return False
    normal = bool_value(g, xsec, "memberNormalToPlating")
    if normal is None:
        return False
    if not normal:
        ev = one(g, xsec, NLTL.hasClassificationSocietySectionPropertyCalculationEvidence)
        if ev is None or (ev, RDF.type, NLTL.evidenceArtifact) not in g:
            return False
    return True


add_case("TRF-034", "P01", "PASS", "Normal member has an effective cross-section with section modulus and shear area; external section-property evidence is not triggered.", build_034("TRF-034-P01", normal=True))
add_case("TRF-034", "P02", "PASS", "Non-normal member has required effective-section properties and classification-society calculation evidence.", build_034("TRF-034-P02", normal=False, evidence=True))
add_case("TRF-034", "F01", "FAIL", "Effective cross-section exists but the member-to-cross-section relationship is missing.", build_034("TRF-034-F01", missing="hasEffectiveMemberCrossSection"))
add_case("TRF-034", "F02", "FAIL", "Effective cross-section is missing section modulus.", build_034("TRF-034-F02", missing="sectionModulus"))
add_case("TRF-034", "F03", "FAIL", "Effective cross-section is missing shear area.", build_034("TRF-034-F03", missing="shearArea"))
add_case("TRF-034", "F04", "FAIL", "Member-normal-to-plating assessment is missing.", build_034("TRF-034-F04", missing="memberNormalToPlating"))
add_case("TRF-034", "F05", "FAIL", "Non-normal member lacks classification-society section-property calculation evidence.", build_034("TRF-034-F05", normal=False, evidence=False))
add_case("TRF-034", "F06", "FAIL", "Section modulus is attached to the member rather than the effective cross-section.", build_034("TRF-034-F06", wrong_owner="sectionModulus"))
add_case("TRF-034", "F07", "FAIL", "Shear area uses the wrong unit.", build_034("TRF-034-F07", wrong_unit="shearArea"))
add_case("TRF-034", "F08", "FAIL", "Required evidence for a non-normal member is attached to the wrong owner.", build_034("TRF-034-F08", normal=False, wrong_owner="evidence"))


# ============================================================
# TRF-035 — RULE LENGTH FROM CLASSIFICATION SOCIETY
# ============================================================

def build_035(cid, society_length=150.0, rule_length=150.0, omit=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "classificationSociety", "Classification Society", ex)
    if omit != "classificationSocietyRuleLength":
        add_value(g, ship, "classificationSocietyRuleLength", society_length, ex, "societyRuleLength", wrong_unit=(wrong_unit == "classificationSocietyRuleLength"))
    if omit != "ruleLength":
        add_value(g, ship, "ruleLength", rule_length, ex, "ruleLength", wrong_unit=(wrong_unit == "ruleLength"))
    return g


def oracle_035(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    a = qty_number(g, ship, "classificationSocietyRuleLength")
    b = qty_number(g, ship, "ruleLength")
    return close(a, b)


add_case("TRF-035", "P01", "PASS", "Rule length equals the classification-society rule length.", build_035("TRF-035-P01", 150.0, 150.0))
add_case("TRF-035", "P02", "PASS", "A second valid rule-length value is transferred unchanged from the classification-society value.", build_035("TRF-035-P02", 92.5, 92.5))
add_case("TRF-035", "F01", "FAIL", "Rule length differs from the classification-society rule length.", build_035("TRF-035-F01", 150.0, 149.0))
add_case("TRF-035", "F02", "FAIL", "Classification-society rule length is missing.", build_035("TRF-035-F02", omit="classificationSocietyRuleLength"))
add_case("TRF-035", "F03", "FAIL", "Rule length is missing.", build_035("TRF-035-F03", omit="ruleLength"))
add_case("TRF-035", "F04", "FAIL", "Rule length is represented using the wrong unit.", build_035("TRF-035-F04", wrong_unit="ruleLength"))


# ============================================================
# TRF-036 — TABLE 4-1 ICE THICKNESS / DESIGN LOAD HEIGHT
# ============================================================

TABLE_4_1 = {
    ICE_CLASSES["IA Super"]: (1.00, 0.35),
    ICE_CLASSES["IA"]: (0.80, 0.30),
    ICE_CLASSES["IB"]: (0.60, 0.25),
    ICE_CLASSES["IC"]: (0.40, 0.22),
}


def build_036(cid, ice_class="IA", hi=None, h=None, missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    pset = ex.designParameters
    g.add((pset, RDF.type, NLTL.iceClassDesignParameterSet))
    if missing != "hasIceClassDesignParameterSet":
        g.add((ship, NLTL.hasIceClassDesignParameterSet, pset))
    cls = ICE_CLASSES[ice_class]
    if missing != "iceClass":
        add_value(g, pset, "iceClass", cls, ex)
    if cls in TABLE_4_1:
        default_hi, default_h = TABLE_4_1[cls]
    else:
        default_hi, default_h = (0.0, 0.0)
    if hi is None:
        hi = default_hi
    if h is None:
        h = default_h
    if missing != "levelIceThickness":
        add_value(g, pset, "levelIceThickness", hi, ex, "levelIceThickness", wrong_unit=(wrong_unit == "levelIceThickness"))
    if missing != "designIceLoadHeight":
        add_value(g, pset, "designIceLoadHeight", h, ex, "designIceLoadHeight", wrong_unit=(wrong_unit == "designIceLoadHeight"))
    return g


def oracle_036(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    pset = one(g, ship, NLTL.hasIceClassDesignParameterSet)
    if pset is None or (pset, RDF.type, NLTL.iceClassDesignParameterSet) not in g:
        return False
    cls = obj_value(g, pset, "iceClass")
    if cls not in TABLE_4_1:
        return False
    hi = qty_number(g, pset, "levelIceThickness")
    h = qty_number(g, pset, "designIceLoadHeight")
    expected_hi, expected_h = TABLE_4_1[cls]
    return close(hi, expected_hi) and close(h, expected_h)


for i, cls in enumerate(["IA Super", "IA", "IB", "IC"], start=1):
    add_case("TRF-036", f"P{i:02d}", "PASS", f"Table 4-1 values for ice class {cls} are selected exactly.", build_036(f"TRF-036-P{i:02d}", cls))
add_case("TRF-036", "F01", "FAIL", "IA level-ice thickness is not the Table 4-1 value.", build_036("TRF-036-F01", "IA", hi=0.81, h=0.30))
add_case("TRF-036", "F02", "FAIL", "IB design ice-load height is not the Table 4-1 value.", build_036("TRF-036-F02", "IB", hi=0.60, h=0.26))
add_case("TRF-036", "F03", "FAIL", "Ice-class selector is missing from the parameter set.", build_036("TRF-036-F03", "IA", missing="iceClass"))
add_case("TRF-036", "F04", "FAIL", "Ship-to-design-parameter-set relation is missing.", build_036("TRF-036-F04", "IA", missing="hasIceClassDesignParameterSet"))
add_case("TRF-036", "F05", "FAIL", "Ice class II is not a valid Table 4-1 selector.", build_036("TRF-036-F05", "II", hi=0.4, h=0.22))
add_case("TRF-036", "F06", "FAIL", "Level-ice thickness uses the wrong unit.", build_036("TRF-036-F06", "IA", wrong_unit="levelIceThickness"))


# ============================================================
# TRF-037 — ICE PRESSURE p = cd * cp * ca * p0; cd MIN 1
# ============================================================

def expected_037(a, k, b, cp, ca, p0):
    cd = min(1.0, (a * k + b) / 1000.0)
    return cd, cd * cp * ca * p0


def build_037(cid, a=30.0, k=10.0, b=230.0, cp=1.0, ca=0.8, p0=5.6,
              cd=None, pressure=None, missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    expected_cd, expected_p = expected_037(a, k, b, cp, ca, p0)
    if cd is None:
        cd = expected_cd
    if pressure is None:
        pressure = expected_p
    vals = [
        ("shipSizeEngineOutputCoefficientA", a),
        ("shipSizeEngineOutputCoefficientK", k),
        ("shipSizeEngineOutputCoefficientB", b),
        ("iceClassFactorCp", cp),
        ("iceLoadAreaFactorCa", ca),
        ("nominalIcePressureP0", p0),
        ("shipSizeEngineOutputFactorCd", cd),
        ("icePressure", pressure),
    ]
    for term, value in vals:
        if missing == term:
            continue
        add_value(g, ship, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def oracle_037(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    vals = {}
    for term in [
        "shipSizeEngineOutputCoefficientA", "shipSizeEngineOutputCoefficientK",
        "shipSizeEngineOutputCoefficientB", "iceClassFactorCp", "iceLoadAreaFactorCa",
        "nominalIcePressureP0", "shipSizeEngineOutputFactorCd", "icePressure",
    ]:
        vals[term] = qty_number(g, ship, term)
        if vals[term] is None:
            return False
    exp_cd, exp_p = expected_037(
        vals["shipSizeEngineOutputCoefficientA"],
        vals["shipSizeEngineOutputCoefficientK"],
        vals["shipSizeEngineOutputCoefficientB"],
        vals["iceClassFactorCp"],
        vals["iceLoadAreaFactorCa"],
        vals["nominalIcePressureP0"],
    )
    return close(vals["shipSizeEngineOutputFactorCd"], exp_cd, tol=1e-7) and close(vals["icePressure"], exp_p, tol=1e-7)


add_case("TRF-037", "P01", "PASS", "Uncapped c_d branch and resulting design ice pressure are calculated correctly.", build_037("TRF-037-P01", a=30.0, k=10.0, b=230.0, cp=1.0, ca=0.8, p0=5.6))
add_case("TRF-037", "P02", "PASS", "A second uncapped coefficient set produces the correct c_d and pressure.", build_037("TRF-037-P02", a=6.0, k=15.0, b=518.0, cp=0.85, ca=0.6, p0=5.6))
add_case("TRF-037", "P03", "PASS", "Raw c_d above one is capped at the regulatory maximum 1.0 before pressure calculation.", build_037("TRF-037-P03", a=30.0, k=30.0, b=230.0, cp=1.0, ca=1.0, p0=5.6))
k_boundary = (1000.0 - 230.0) / 30.0
add_case("TRF-037", "P04", "PASS", "Exact c_d=1 boundary is accepted.", build_037("TRF-037-P04", a=30.0, k=k_boundary, b=230.0, cp=0.75, ca=0.5, p0=5.6))
add_case("TRF-037", "F01", "FAIL", "c_d result is inconsistent with (a*k+b)/1000.", build_037("TRF-037-F01", cd=0.60))
add_case("TRF-037", "F02", "FAIL", "Design ice pressure is inconsistent with c_d*c_p*c_a*p_0.", build_037("TRF-037-F02", pressure=3.0))
add_case("TRF-037", "F03", "FAIL", "Raw c_d above one is not capped at 1.0.", build_037("TRF-037-F03", a=30.0, k=30.0, b=230.0, cd=1.13, pressure=6.328))
for suffix, term in [
    ("F04", "shipSizeEngineOutputCoefficientA"),
    ("F05", "shipSizeEngineOutputCoefficientK"),
    ("F06", "shipSizeEngineOutputCoefficientB"),
    ("F07", "iceClassFactorCp"),
    ("F08", "iceLoadAreaFactorCa"),
    ("F09", "nominalIcePressureP0"),
    ("F10", "shipSizeEngineOutputFactorCd"),
    ("F11", "icePressure"),
]:
    add_case("TRF-037", suffix, "FAIL", f"Required TRF-037 formula field {term} is missing.", build_037(f"TRF-037-{suffix}", missing=term))
add_case("TRF-037", "F12", "FAIL", "Design ice pressure uses the wrong unit.", build_037("TRF-037-F12", wrong_unit="icePressure"))


ORACLES = {
    "TRF-029": oracle_029,
    "TRF-030": oracle_030,
    "TRF-031": oracle_031,
    "TRF-032": oracle_032,
    "TRF-034": oracle_034,
    "TRF-035": oracle_035,
    "TRF-036": oracle_036,
    "TRF-037": oracle_037,
}

assert len(CASE_DEFS) == 84, len(CASE_DEFS)


# ============================================================
# VALIDATION
# ============================================================

def graph_vocab_ok(g):
    local = set()
    for s, p, o in g:
        for node in (s, p, o):
            text = str(node)
            if text.startswith(str(NLTL)):
                local.add(text.split("#", 1)[1])
    unknown = sorted(x for x in local if x not in KNOWN_NLTL)
    return not unknown, unknown


def graph_qudt_ok(g):
    for q in g.subjects(RDF.type, QUDT.QuantityValue):
        if len(list(g.objects(q, QUDT.numericValue))) != 1:
            return False
        if len(list(g.objects(q, QUDT.unit))) != 1:
            return False
    return True


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_existing(check_hashes=True):
    manifest_path = ROOT / "manifests" / "traficom_batch_d_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_d_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch D manifest does not exist")

    rows = [json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
    syntax = vocab = qudt = agreement = 0
    diagnostics = []

    for row in rows:
        p = ROOT / row["rdf_path"]
        try:
            g = Graph().parse(p, format="turtle")
            syntax += 1
        except Exception as e:
            diagnostics.append((row["case_id"], "parse", str(e)))
            continue

        ok, unknown = graph_vocab_ok(g)
        if ok:
            vocab += 1
        else:
            diagnostics.append((row["case_id"], "vocab", unknown))

        if graph_qudt_ok(g):
            qudt += 1
        else:
            diagnostics.append((row["case_id"], "QUDT", "invalid QuantityValue"))

        actual = "PASS" if ORACLES[row["requirement_id"]](g) else "FAIL"
        if actual == row["expected"]:
            agreement += 1
        else:
            diagnostics.append((row["case_id"], "oracle", f"expected={row['expected']} actual={actual}"))

    hash_ok = True
    if check_hashes:
        if not lock_path.exists():
            hash_ok = False
            diagnostics.append(("lock", "hash", "lock file missing"))
        else:
            lock = json.loads(lock_path.read_text())
            for rel, expected_hash in lock["frozen_files"].items():
                p = ROOT / rel
                if not p.exists() or sha256(p) != expected_hash:
                    hash_ok = False
                    diagnostics.append((rel, "hash", "mismatch"))

    n = len(rows)
    print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}")
    print(f"RDF files: {n}")
    print(f"Syntactically valid: {syntax}")
    print(f"Vocabulary validation count: {vocab}")
    print(f"QUDT/unit validation count: {qudt}")
    print(f"Source-oracle agreement count: {agreement}")
    if check_hashes:
        print("Frozen hashes matched: " + ("YES" if hash_ok else "NO"))

    ok = syntax == vocab == qudt == agreement == n and (hash_ok if check_hashes else True)
    print("Overall status: " + ("PASS" if ok else "FAIL"))
    if diagnostics:
        print("\nDiagnostics:")
        for d in diagnostics:
            print(d)
    return ok


# ============================================================
# GENERATE / FREEZE
# ============================================================

def generate():
    rdf_root = ROOT / "rdf" / "TRF"
    spec_root = ROOT / "specifications" / "TRF"
    manifest_root = ROOT / "manifests"
    locks_root = ROOT / "locks"
    scripts_root = ROOT / "scripts"

    for p in [rdf_root, spec_root, manifest_root, locks_root, scripts_root]:
        p.mkdir(parents=True, exist_ok=True)

    lock_path = locks_root / "traficom_batch_d_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch D lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {
        "TRF-029": "4.1",
        "TRF-030": "4.1",
        "TRF-031": "4.1",
        "TRF-032": "4.1",
        "TRF-034": "4.1",
        "TRF-035": "4.1.1",
        "TRF-036": "4.2.1",
        "TRF-037": "4.2.2",
    }

    # Collision guard before writing anything.
    planned_paths = []
    for c in CASE_DEFS:
        req = c["requirement_id"]
        planned_paths.append(rdf_root / req / f"{c['case_id']}.ttl")
    planned_paths += [spec_root / f"{req}.json" for req in REQS]
    planned_paths.append(manifest_root / "traficom_batch_d_manifest.jsonl")
    planned_paths.append(scripts_root / "validate_traficom_batch_d.py")
    for p in planned_paths:
        if p.exists():
            raise SystemExit(f"Refusing to overwrite pre-existing benchmark artifact: {p}")

    manifest_rows = []
    for c in CASE_DEFS:
        req = c["requirement_id"]
        outdir = rdf_root / req
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{c['case_id']}.ttl"
        c["graph"].serialize(destination=p, format="turtle")
        manifest_rows.append({
            "requirement_id": req,
            "case_id": c["case_id"],
            "expected": c["expected"],
            "rdf_path": str(p.relative_to(ROOT)),
            "source_id": "SRC-TRAFICOM-2021",
            "source_clause": clauses[req],
            "verification_mode": EXPECTED_MODES[req],
            "source_oracle_rationale": c["rationale"],
            "generated_shacl_inspected": False,
        })

    manifest_path = manifest_root / "traficom_batch_d_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in manifest_rows:
            f.write(json.dumps(row) + "\n")

    for req in REQS:
        spec = {
            "requirement_id": req,
            "source_id": "SRC-TRAFICOM-2021",
            "source_clause": clauses[req],
            "source_lock_id": INDEX["sourceLockId"],
            "r13_contract": CONTRACTS[req],
            "test_cases": [
                {"case_id": x["case_id"], "expected": x["expected"], "rationale": x["rationale"]}
                for x in CASE_DEFS if x["requirement_id"] == req
            ],
            "benchmark_policy": "Source/R13-defined behavioral oracle created without inspecting generated SHACL.",
        }
        (spec_root / f"{req}.json").write_text(json.dumps(spec, indent=2) + "\n")

    print("Pre-freeze validation")
    if not validate_existing(check_hashes=False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")

    frozen = [manifest_path]
    frozen += [spec_root / f"{req}.json" for req in REQS]
    for req in REQS:
        frozen += sorted((rdf_root / req).glob("*.ttl"))

    lock = {
        "benchmark": "TRAFICOM Behavioral Benchmark Batch D",
        "source_lock_id": INDEX["sourceLockId"],
        "source_id": "SRC-TRAFICOM-2021",
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    validator_path = scripts_root / "validate_traficom_batch_d.py"
    shutil.copy2(Path(__file__).resolve(), validator_path)
    validator_path.chmod(0o755)

    (ROOT / "README_TRAFICOM_BATCH_D.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch D\n\n"
        "Requirements: 8\n"
        "Cases: 84\n\n"
        "TRF-029, TRF-030, TRF-031, TRF-032, TRF-034, TRF-035, TRF-036, TRF-037\n\n"
        "Scope: TRAFICOM 2021 sections 4.1, 4.1.1, 4.2.1 and 4.2.2.\n\n"
        "Generated SHACL was not inspected during fixture construction.\n"
        "COMPLEX_READINESS cases test frozen R13 readiness/owner/path/unit/evidence semantics and do not execute advanced engineering formulae.\n\n"
        "Validate with:\n\npython3 scripts/validate_traficom_batch_d.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(check_hashes=True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = Path(__file__).name == "validate_traficom_batch_d.py" or "--validate-only" in sys.argv
    if validation_mode:
        ok = validate_existing(check_hashes=True)
        raise SystemExit(0 if ok else 1)
    generate()


if __name__ == "__main__":
    main()
