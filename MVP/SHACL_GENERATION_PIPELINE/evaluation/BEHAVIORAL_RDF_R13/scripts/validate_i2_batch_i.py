from pathlib import Path
import json
import hashlib
import math
import shutil
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD


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
BASE = "https://w3id.org/nltl/benchmark/i2-batch-i/"

REQS = ["I2-050", "I2-051", "I2-052", "I2-054", "I2-055"]
EXPECTED_MODES = {
    "I2-050": "COMPLEX_READINESS",
    "I2-051": "DIRECT_CALCULATION",
    "I2-052": "COMPLEX_READINESS",
    "I2-054": "COMPLEX_READINESS",
    "I2-055": "DIRECT_STATIC",
}
for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]
for req in ["I2-050", "I2-052", "I2-054"]:
    assert CONTRACTS[req].get("formulaExecutionRequired") is False

ONTOLOGY = Graph().parse(R13 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
KNOWN_NLTL = {
    str(s).split("#", 1)[1]
    for s in set(ONTOLOGY.subjects())
    if str(s).startswith(str(NLTL))
}


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
            raise RuntimeError(f"{term} has no frozen/context unit")
        q = ex[name or (term + "Value")]
        g.add((q, RDF.type, QUDT.QuantityValue))
        g.add((q, QUDT.numericValue, Literal(str(value), datatype=XSD.decimal)))
        u = URIRef(unit)
        if wrong_unit:
            u = UNIT.UNITLESS if u != UNIT.UNITLESS else UNIT.M
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


def one(g, s, p):
    vals = list(g.objects(s, p))
    return vals[0] if len(vals) == 1 else None


def qty_number(g, s, term, expected_unit=None):
    expected = expected_unit or REG.get(term, {}).get("unitIri", "")
    vals = list(g.objects(s, NLTL[term]))
    if len(vals) != 1:
        return None
    q = vals[0]
    if (q, RDF.type, QUDT.QuantityValue) not in g:
        return None
    nums = list(g.objects(q, QUDT.numericValue))
    units = list(g.objects(q, QUDT.unit))
    if len(nums) != 1 or len(units) != 1:
        return None
    if expected and str(units[0]) != str(expected):
        return None
    try:
        return float(nums[0])
    except Exception:
        return None


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


def close(a, b, tol=1e-9):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ==================================================================
# I2-050 — COMPLEX_READINESS, source formula is informational only
# ==================================================================
I2_050_OPERANDS = [
    "crushingFailureClassFactor",
    "flexuralFailureClassFactor",
    "hullFormCoefficientKh",
    "iceStrengthCoefficientKI",
    "longitudinalStrengthClassFactor",
    "stemAngle",
    "upperIceWaterlineDraughtDUI",
]
I2_050_RESULTS = [
    "designVerticalIceForceAtBow",
    "designVerticalIceForceAtBowCandidateOne",
    "designVerticalIceForceAtBowCandidateTwo",
]


def build_050(cid, missing=None, wrong_owner=None, wrong_unit=None, inconsistent=False):
    g, ex, ship = new_graph(cid)
    calc = ex.calculation
    g.add((calc, RDF.type, NLTL.calculationCase))
    vals = {
        "crushingFailureClassFactor": 4.50,
        "flexuralFailureClassFactor": 13.48,
        "hullFormCoefficientKh": 2.0,
        "iceStrengthCoefficientKI": 1.2,
        "longitudinalStrengthClassFactor": 3.15,
        "stemAngle": 45.0,
        # Follow frozen R13 interface exactly. It currently carries unit:M.
        "upperIceWaterlineDraughtDUI": 12.0,
        "designVerticalIceForceAtBow": 7.0,
        "designVerticalIceForceAtBowCandidateOne": 7.0,
        "designVerticalIceForceAtBowCandidateTwo": 16.176,
    }
    if inconsistent:
        # Deliberately not formula-consistent. R13 classifies this as readiness-only.
        vals.update({
            "designVerticalIceForceAtBow": 99.0,
            "designVerticalIceForceAtBowCandidateOne": 3.0,
            "designVerticalIceForceAtBowCandidateTwo": 4.0,
        })
    for term, value in vals.items():
        if term == missing:
            continue
        owner = calc if term == wrong_owner else ship
        add_value(g, owner, term, value, ex, term, wrong_unit=(term == wrong_unit))
    return g


def oracle_050(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    # R13 deliberately marks the source formula as informational. The oracle checks
    # the complete frozen interface (terms/owners/units) and does not recompute F_IB.
    return all(qty_number(g, ship, t) is not None for t in I2_050_OPERANDS + I2_050_RESULTS)


# ==================================================================
# I2-051 — positive vertical-shear branch, direct calculation
# ==================================================================
def positive_cf(x, lui):
    if lui <= 0 or x < 0 or x > lui:
        return None
    r = x / lui
    if r <= 0.6:
        return 0.0
    if r < 0.9:
        return (r - 0.6) / 0.3
    return 1.0


def build_051(
    cid,
    x=75.0,
    lui=100.0,
    fib=5.0,
    cf=None,
    fi_kn=None,
    missing=None,
    wrong_unit=None,
    omit_relation=False,
    direction=NLTL.positiveShearForce,
):
    g, ex, ship = new_graph(cid)
    calc = ex.calculation
    g.add((calc, RDF.type, NLTL.calculationCase))
    if not omit_relation:
        g.add((ship, NLTL.hasCalculationCase, calc))
    if missing != "upperIceWaterlineLengthLUI":
        add_value(g, ship, "upperIceWaterlineLengthLUI", lui, ex, "lui", wrong_unit=(wrong_unit == "upperIceWaterlineLengthLUI"))
    if missing != "designVerticalIceForceAtBow":
        add_value(g, ship, "designVerticalIceForceAtBow", fib, ex, "fib", wrong_unit=(wrong_unit == "designVerticalIceForceAtBow"))
    if missing != "shearForceDirection":
        g.add((calc, NLTL.shearForceDirection, direction))
    if missing != "hullGirderLongitudinalPositionFromAft":
        add_value(g, calc, "hullGirderLongitudinalPositionFromAft", x, ex, "x", wrong_unit=(wrong_unit == "hullGirderLongitudinalPositionFromAft"))
    expected_cf = positive_cf(x, lui)
    if cf is None:
        cf = expected_cf if expected_cf is not None else 0.0
    if missing != "longitudinalDistributionFactor":
        add_value(g, calc, "longitudinalDistributionFactor", cf, ex, "cf", wrong_unit=(wrong_unit == "longitudinalDistributionFactor"))
    if fi_kn is None:
        fi_kn = (cf * fib * 1000.0) if cf is not None else 0.0
    if missing != "designVerticalIceShearForce":
        add_value(g, calc, "designVerticalIceShearForce", fi_kn, ex, "fi", wrong_unit=(wrong_unit == "designVerticalIceShearForce"))
    return g


def oracle_051(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    lui = qty_number(g, ship, "upperIceWaterlineLengthLUI")
    fib = qty_number(g, ship, "designVerticalIceForceAtBow")
    if lui is None or fib is None or lui <= 0:
        return False
    cases = list(g.objects(ship, NLTL.hasCalculationCase))
    if not cases:
        return False
    for calc in cases:
        if one(g, calc, NLTL.shearForceDirection) != NLTL.positiveShearForce:
            return False
        x = qty_number(g, calc, "hullGirderLongitudinalPositionFromAft")
        cf = qty_number(g, calc, "longitudinalDistributionFactor")
        fi = qty_number(g, calc, "designVerticalIceShearForce")
        exp_cf = positive_cf(x, lui) if x is not None else None
        if exp_cf is None or cf is None or fi is None:
            return False
        if not close(cf, exp_cf):
            return False
        # F_IB is frozen as MN while F_I is frozen as kN, hence *1000.
        if not close(fi, exp_cf * fib * 1000.0):
            return False
    return True


# ==================================================================
# I2-052 — COMPLEX_READINESS for linear interpolation
# ==================================================================
def build_052(
    cid,
    x=75.0,
    lower=(60.0, 0.0),
    upper=(90.0, 1.0),
    interpolated_factor=0.5,
    interpolated_value="0.5",
    missing=None,
    wrong_unit=None,
    omit_lower_from_points=False,
    same_endpoint=False,
    extra_point=False,
):
    g, ex, ship = new_graph(cid)
    calc = ex.calculation
    lo = ex.lowerPoint
    hi = lo if same_endpoint else ex.upperPoint
    g.add((calc, RDF.type, NLTL.calculationCase))
    g.add((lo, RDF.type, NLTL.interpolationPoint))
    if hi != lo:
        g.add((hi, RDF.type, NLTL.interpolationPoint))
    g.add((ship, NLTL.hasCalculationCase, calc))

    if missing != "interpolationLowerEndpoint":
        g.add((calc, NLTL.interpolationLowerEndpoint, lo))
    if missing != "interpolationUpperEndpoint":
        g.add((calc, NLTL.interpolationUpperEndpoint, hi))
    if not omit_lower_from_points:
        g.add((calc, NLTL.hasInterpolationPoint, lo))
    if hi != lo:
        g.add((calc, NLTL.hasInterpolationPoint, hi))

    if missing != "hullGirderLongitudinalPositionFromAft":
        add_value(g, calc, "hullGirderLongitudinalPositionFromAft", x, ex, "x", wrong_unit=(wrong_unit == "hullGirderLongitudinalPositionFromAft"))
    if missing != "interpolatedLongitudinalDistributionFactor":
        add_value(g, calc, "interpolatedLongitudinalDistributionFactor", interpolated_factor, ex, "interpFactor", wrong_unit=(wrong_unit == "interpolatedLongitudinalDistributionFactor"))
    if missing != "interpolatedValue":
        add_value(g, calc, "interpolatedValue", interpolated_value, ex)

    for label, point, pair in [("lower", lo, lower), ("upper", hi, upper)]:
        # When endpoints are deliberately the same node, only write the first pair
        # so the failure is endpoint identity rather than accidental duplicate values.
        if label == "upper" and hi == lo:
            continue
        if missing != f"{label}.interpolationCoordinate":
            add_value(g, point, "interpolationCoordinate", pair[0], ex, f"{label}Coord", unit_override=str(UNIT.M), wrong_unit=(wrong_unit == f"{label}.interpolationCoordinate"))
        if missing != f"{label}.interpolationPointValue":
            add_value(g, point, "interpolationPointValue", pair[1], ex, f"{label}Value", unit_override=str(UNIT.UNITLESS), wrong_unit=(wrong_unit == f"{label}.interpolationPointValue"))

    if extra_point:
        p = ex.extraPoint
        g.add((p, RDF.type, NLTL.interpolationPoint))
        g.add((calc, NLTL.hasInterpolationPoint, p))
        add_value(g, p, "interpolationCoordinate", 100.0, ex, "extraCoord", unit_override=str(UNIT.M))
        add_value(g, p, "interpolationPointValue", 1.2, ex, "extraValue", unit_override=str(UNIT.UNITLESS))
    return g


def valid_interp_point(g, p):
    return (
        (p, RDF.type, NLTL.interpolationPoint) in g
        and qty_number(g, p, "interpolationCoordinate", str(UNIT.M)) is not None
        and qty_number(g, p, "interpolationPointValue", str(UNIT.UNITLESS)) is not None
    )


def oracle_052(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    cases = list(g.objects(ship, NLTL.hasCalculationCase))
    if not cases:
        return False
    for calc in cases:
        if qty_number(g, calc, "hullGirderLongitudinalPositionFromAft") is None:
            return False
        if qty_number(g, calc, "interpolatedLongitudinalDistributionFactor") is None:
            return False
        if string_value(g, calc, "interpolatedValue") is None:
            return False
        lo = one(g, calc, NLTL.interpolationLowerEndpoint)
        hi = one(g, calc, NLTL.interpolationUpperEndpoint)
        if lo is None or hi is None or lo == hi:
            return False
        points = set(g.objects(calc, NLTL.hasInterpolationPoint))
        if lo not in points or hi not in points:
            return False
        if not valid_interp_point(g, lo) or not valid_interp_point(g, hi):
            return False
    return True


# ==================================================================
# I2-054 — COMPLEX_READINESS for vertical ice bending moment
# ==================================================================
def build_054(
    cid,
    x=60.0,
    cm=1.0,
    mi=40.0,
    lui=100.0,
    stem=45.0,
    fib=5.0,
    missing=None,
    wrong_unit=None,
    omit_calc_link=False,
    omit_bending_link=False,
    with_interp_points=False,
):
    g, ex, ship = new_graph(cid)
    calc = ex.bendingCase
    g.add((calc, RDF.type, NLTL.calculationCase))
    g.add((calc, RDF.type, NLTL.hullGirderBendingMomentCalculationCase))
    if not omit_calc_link:
        g.add((ship, NLTL.hasCalculationCase, calc))
    if not omit_bending_link:
        g.add((ship, NLTL.hasHullGirderBendingMomentCalculationCase, calc))

    globals_ = {
        "upperIceWaterlineLengthLUI": lui,
        "stemAngle": stem,
        "designVerticalIceForceAtBow": fib,
    }
    for term, val in globals_.items():
        if term != missing:
            add_value(g, ship, term, val, ex, term, wrong_unit=(wrong_unit == term))

    cases_ = {
        "caseHullGirderLongitudinalPositionFromAft": x,
        "caseBendingMomentDistributionFactor": cm,
        "caseDesignVerticalIceBendingMoment": mi,
    }
    for term, val in cases_.items():
        if term != missing:
            add_value(g, calc, term, val, ex, term, wrong_unit=(wrong_unit == term))

    if with_interp_points:
        for i, (coord, val) in enumerate([(70.0, 1.0), (95.0, 0.3)], start=1):
            p = ex[f"interp{i}"]
            g.add((p, RDF.type, NLTL.interpolationPoint))
            g.add((calc, NLTL.hasInterpolationPoint, p))
            add_value(g, p, "interpolationCoordinate", coord, ex, f"interpCoord{i}", unit_override=str(UNIT.M))
            add_value(g, p, "interpolationPointValue", val, ex, f"interpVal{i}", unit_override=str(UNIT.UNITLESS))
    return g


def oracle_054(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    for term in ["upperIceWaterlineLengthLUI", "stemAngle", "designVerticalIceForceAtBow"]:
        if qty_number(g, ship, term) is None:
            return False
    calc_cases = set(g.objects(ship, NLTL.hasCalculationCase))
    bend_cases = set(g.objects(ship, NLTL.hasHullGirderBendingMomentCalculationCase))
    if not calc_cases or not bend_cases or calc_cases != bend_cases:
        return False
    for calc in bend_cases:
        if (calc, RDF.type, NLTL.hullGirderBendingMomentCalculationCase) not in g:
            return False
        for term in [
            "caseHullGirderLongitudinalPositionFromAft",
            "caseBendingMomentDistributionFactor",
            "caseDesignVerticalIceBendingMoment",
        ]:
            if qty_number(g, calc, term) is None:
                return False
        # Interpolation points are contextual evidence for intermediate cases. If
        # represented, require well-formed coordinate/value QuantityValues; do not
        # numerically execute interpolation or the bending-moment formula.
        for p in g.objects(calc, NLTL.hasInterpolationPoint):
            if not valid_interp_point(g, p):
                return False
    return True


# ==================================================================
# I2-055 — direct stress criterion
# ==================================================================
def build_055(cid, design=150.0, permissible=200.0, status=True, missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    if missing != "designStress":
        add_value(g, ship, "designStress", design, ex, "designStress", wrong_unit=(wrong_unit == "designStress"))
    if missing != "permissibleStress":
        add_value(g, ship, "permissibleStress", permissible, ex, "permissibleStress", wrong_unit=(wrong_unit == "permissibleStress"))
    if missing != "strengthCriterionStatus":
        add_value(g, ship, "strengthCriterionStatus", status, ex)
    return g


def oracle_055(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    design = qty_number(g, ship, "designStress")
    permissible = qty_number(g, ship, "permissibleStress")
    status = bool_value(g, ship, "strengthCriterionStatus")
    return design is not None and permissible is not None and status is True and design <= permissible + 1e-12


ORACLES = {
    "I2-050": oracle_050,
    "I2-051": oracle_051,
    "I2-052": oracle_052,
    "I2-054": oracle_054,
    "I2-055": oracle_055,
}


# ==================================================================
# CASE PLAN — collision-safe Batch-I IDs
# ==================================================================
CASE_DEFS = []


def add_case(req, suffix, expected, rationale, graph):
    case_id = f"{req}-I-{suffix}"
    CASE_DEFS.append({
        "requirement_id": req,
        "case_id": case_id,
        "expected": expected,
        "rationale": rationale,
        "graph": graph,
    })


# I2-050 — 14
add_case("I2-050", "P01", "PASS", "Complete frozen R13 readiness interface for both F_IB candidates and selected design force.", build_050("I2-050-I-P01"))
add_case("I2-050", "P02", "PASS", "R13 classifies I2-050 as COMPLEX_READINESS with formulaExecutionRequired=false; deliberately formula-inconsistent result values still provide the complete reviewable interface.", build_050("I2-050-I-P02", inconsistent=True))
for idx, term in enumerate(I2_050_OPERANDS + I2_050_RESULTS, start=1):
    add_case("I2-050", f"F{idx:02d}", "FAIL", f"Required readiness term {term} is missing.", build_050(f"I2-050-I-F{idx:02d}", missing=term))
add_case("I2-050", "F11", "FAIL", "designVerticalIceForceAtBow is attached to a calculation node instead of its frozen ship owner.", build_050("I2-050-I-F11", wrong_owner="designVerticalIceForceAtBow"))
add_case("I2-050", "F12", "FAIL", "stemAngle uses the wrong QUDT unit.", build_050("I2-050-I-F12", wrong_unit="stemAngle"))

# I2-051 — 14
for suffix, x, expected_cf in [
    ("P01", 0.0, 0.0),
    ("P02", 60.0, 0.0),
    ("P03", 75.0, 0.5),
    ("P04", 90.0, 1.0),
    ("P05", 100.0, 1.0),
]:
    add_case("I2-051", suffix, "PASS", f"Positive-shear branch at x={x:g} m uses the correct source-defined distribution factor Cf={expected_cf:g} and FI=Cf*FIB.", build_051(f"I2-051-I-{suffix}", x=x))
add_case("I2-051", "F01", "FAIL", "Interpolated positive-shear distribution factor is numerically wrong.", build_051("I2-051-I-F01", x=75.0, cf=0.4, fi_kn=2000.0))
add_case("I2-051", "F02", "FAIL", "Vertical ice shear force does not equal Cf*FIB after MN-to-kN unit conversion.", build_051("I2-051-I-F02", x=75.0, cf=0.5, fi_kn=2400.0))
add_case("I2-051", "F03", "FAIL", "Frozen positive-shear selector shearForceDirection is missing.", build_051("I2-051-I-F03", missing="shearForceDirection"))
add_case("I2-051", "F04", "FAIL", "Hull-girder longitudinal position is missing from the calculation case.", build_051("I2-051-I-F04", missing="hullGirderLongitudinalPositionFromAft"))
add_case("I2-051", "F05", "FAIL", "Global design vertical ice force at bow is missing.", build_051("I2-051-I-F05", missing="designVerticalIceForceAtBow"))
add_case("I2-051", "F06", "FAIL", "Global upper-ice-waterline length is missing.", build_051("I2-051-I-F06", missing="upperIceWaterlineLengthLUI"))
add_case("I2-051", "F07", "FAIL", "designVerticalIceShearForce is encoded with the wrong unit.", build_051("I2-051-I-F07", wrong_unit="designVerticalIceShearForce"))
add_case("I2-051", "F08", "FAIL", "Longitudinal position lies beyond the represented LUI domain.", build_051("I2-051-I-F08", x=105.0, cf=1.0, fi_kn=5000.0))
add_case("I2-051", "F09", "FAIL", "Calculation case exists but ship-to-case relationship is absent.", build_051("I2-051-I-F09", omit_relation=True))

# I2-052 — 12
add_case("I2-052", "P01", "PASS", "Complete interpolation-readiness graph contains input position, lower/upper endpoints, point coordinates/values and result fields.", build_052("I2-052-I-P01"))
add_case("I2-052", "P02", "PASS", "Readiness-only policy does not recompute interpolation; numerically inconsistent interpolated result remains structurally complete for expert/external execution.", build_052("I2-052-I-P02", interpolated_factor=0.9, interpolated_value="externally-computed"))
add_case("I2-052", "P03", "PASS", "Additional well-formed interpolation point does not invalidate the required lower/upper endpoint structure.", build_052("I2-052-I-P03", extra_point=True))
add_case("I2-052", "F01", "FAIL", "Lower interpolation endpoint relationship is missing.", build_052("I2-052-I-F01", missing="interpolationLowerEndpoint"))
add_case("I2-052", "F02", "FAIL", "Upper interpolation endpoint relationship is missing.", build_052("I2-052-I-F02", missing="interpolationUpperEndpoint"))
add_case("I2-052", "F03", "FAIL", "Lower endpoint is not included through hasInterpolationPoint.", build_052("I2-052-I-F03", omit_lower_from_points=True))
add_case("I2-052", "F04", "FAIL", "Lower endpoint lacks interpolationCoordinate.", build_052("I2-052-I-F04", missing="lower.interpolationCoordinate"))
add_case("I2-052", "F05", "FAIL", "Upper endpoint lacks interpolationPointValue.", build_052("I2-052-I-F05", missing="upper.interpolationPointValue"))
add_case("I2-052", "F06", "FAIL", "Interpolated longitudinal distribution factor result is missing.", build_052("I2-052-I-F06", missing="interpolatedLongitudinalDistributionFactor"))
add_case("I2-052", "F07", "FAIL", "Generic interpolatedValue result is missing.", build_052("I2-052-I-F07", missing="interpolatedValue"))
add_case("I2-052", "F08", "FAIL", "Lower and upper interpolation endpoints collapse to the same point.", build_052("I2-052-I-F08", same_endpoint=True))
add_case("I2-052", "F09", "FAIL", "Interpolation-point coordinate has the wrong contextual unit.", build_052("I2-052-I-F09", wrong_unit="lower.interpolationCoordinate"))

# I2-054 — 12
add_case("I2-054", "P01", "PASS", "Complete bending-moment readiness case at a source-defined plateau contains global operands, case operands and result.", build_054("I2-054-I-P01"))
add_case("I2-054", "P02", "PASS", "Intermediate bending-moment case includes well-formed interpolation-point context.", build_054("I2-054-I-P02", x=82.5, cm=0.65, mi=30.0, with_interp_points=True))
add_case("I2-054", "P03", "PASS", "R13 marks I2-054 as COMPLEX_READINESS; deliberately formula-inconsistent Cm/MI values remain a complete frozen interface rather than being numerically recomputed.", build_054("I2-054-I-P03", x=82.5, cm=0.2, mi=999.0, with_interp_points=True))
for idx, term in enumerate([
    "upperIceWaterlineLengthLUI",
    "stemAngle",
    "designVerticalIceForceAtBow",
    "caseHullGirderLongitudinalPositionFromAft",
    "caseBendingMomentDistributionFactor",
    "caseDesignVerticalIceBendingMoment",
], start=1):
    add_case("I2-054", f"F{idx:02d}", "FAIL", f"Required bending-moment readiness term {term} is missing.", build_054(f"I2-054-I-F{idx:02d}", missing=term))
add_case("I2-054", "F07", "FAIL", "Generic ship-to-calculationCase relationship is missing.", build_054("I2-054-I-F07", omit_calc_link=True))
add_case("I2-054", "F08", "FAIL", "Dedicated hasHullGirderBendingMomentCalculationCase relationship is missing.", build_054("I2-054-I-F08", omit_bending_link=True))
add_case("I2-054", "F09", "FAIL", "Bending-moment result uses the wrong QUDT unit.", build_054("I2-054-I-F09", wrong_unit="caseDesignVerticalIceBendingMoment"))

# I2-055 — 9
add_case("I2-055", "P01", "PASS", "Design stress exactly equals permissible stress and criterion status is satisfied.", build_055("I2-055-I-P01", 200.0, 200.0, True))
add_case("I2-055", "P02", "PASS", "Design stress below permissible stress satisfies the direct criterion.", build_055("I2-055-I-P02", 150.0, 200.0, True))
add_case("I2-055", "F01", "FAIL", "Design stress exceeds permissible stress even though status is incorrectly asserted true.", build_055("I2-055-I-F01", 201.0, 200.0, True))
add_case("I2-055", "F02", "FAIL", "A below-limit stress pair with strengthCriterionStatus=false is not a compliant case.", build_055("I2-055-I-F02", 150.0, 200.0, False))
add_case("I2-055", "F03", "FAIL", "An above-limit stress pair remains non-compliant when status=false.", build_055("I2-055-I-F03", 250.0, 200.0, False))
add_case("I2-055", "F04", "FAIL", "designStress is missing.", build_055("I2-055-I-F04", missing="designStress"))
add_case("I2-055", "F05", "FAIL", "permissibleStress is missing.", build_055("I2-055-I-F05", missing="permissibleStress"))
add_case("I2-055", "F06", "FAIL", "strengthCriterionStatus is missing.", build_055("I2-055-I-F06", missing="strengthCriterionStatus"))
add_case("I2-055", "F07", "FAIL", "designStress is encoded with the wrong QUDT unit.", build_055("I2-055-I-F07", wrong_unit="designStress"))

assert len(CASE_DEFS) == 61, len(CASE_DEFS)


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
    manifest_path = ROOT / "manifests" / "i2_batch_i_manifest.jsonl"
    lock_path = ROOT / "locks" / "i2_batch_i_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("Batch I manifest does not exist")
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


def generate():
    rdf_root = ROOT / "rdf" / "I2"
    spec_root = ROOT / "specifications" / "I2"
    manifest_root = ROOT / "manifests"
    locks_root = ROOT / "locks"
    scripts_root = ROOT / "scripts"
    for p in [rdf_root, spec_root, manifest_root, locks_root, scripts_root]:
        p.mkdir(parents=True, exist_ok=True)

    lock_path = locks_root / "i2_batch_i_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("Batch I lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {
        "I2-050": "I2.13.2.1",
        "I2-051": "I2.13.3.1",
        "I2-052": "I2.13.3.1 (intermediate values by linear interpolation)",
        "I2-054": "I2.13.4.1",
        "I2-055": "I2.13.5.1",
    }

    rows = []
    for c in CASE_DEFS:
        req = c["requirement_id"]
        outdir = rdf_root / req
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{c['case_id']}.ttl"
        c["graph"].serialize(destination=p, format="turtle")
        rows.append({
            "requirement_id": req,
            "case_id": c["case_id"],
            "expected": c["expected"],
            "rdf_path": str(p.relative_to(ROOT)),
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": clauses[req],
            "verification_mode": EXPECTED_MODES[req],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
            "source_oracle_rationale": c["rationale"],
            "generated_shacl_inspected": False,
        })

    manifest_path = manifest_root / "i2_batch_i_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    spec_paths = []
    for req in REQS:
        spec = {
            "requirement_id": req,
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": clauses[req],
            "source_lock_id": INDEX["sourceLockId"],
            "r13_contract": CONTRACTS[req],
            "test_cases": [
                {"case_id": x["case_id"], "expected": x["expected"], "rationale": x["rationale"]}
                for x in CASE_DEFS
                if x["requirement_id"] == req
            ],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
            "benchmark_policy": "Source/R13-defined behavioral oracle created without inspecting generated SHACL.",
        }
        p = spec_root / f"{req}_batch_i.json"
        p.write_text(json.dumps(spec, indent=2) + "\n")
        spec_paths.append(p)

    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")

    frozen = [manifest_path] + spec_paths
    for req in REQS:
        frozen += sorted((rdf_root / req).glob(f"{req}-I-*.ttl"))

    lock = {
        "benchmark": "I2 Behavioral Benchmark Batch I",
        "source_lock_id": INDEX["sourceLockId"],
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "previous_frozen_batches_modified": False,
        "readiness_formula_execution": {
            "I2-050": False,
            "I2-052": False,
            "I2-054": False,
        },
        "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    validator = scripts_root / "validate_i2_batch_i.py"
    shutil.copy2(Path(__file__).resolve(), validator)
    validator.chmod(0o755)

    (ROOT / "README_I2_BATCH_I.md").write_text(
        "# I2 Behavioral Benchmark Batch I\n\n"
        "Requirements: 5\nCases: 61\n\n"
        "I2-050, I2-051, I2-052, I2-054, I2-055\n\n"
        "Batch I closes the remaining IACS I2 longitudinal-strength group in the frozen R13 mapping. "
        "I2-050, I2-052 and I2-054 are intentionally readiness-only because R13 sets formulaExecutionRequired=false; "
        "their advanced source equations/interpolation are therefore not executed by the behavioral oracle. "
        "I2-051 executes the frozen positive-shear branch, including MN-to-kN conversion between F_IB and F_I. "
        "I2-055 checks the generic frozen designStress <= permissibleStress criterion together with satisfied status.\n\n"
        "Audit note: the frozen R13 registry currently assigns upperIceWaterlineDraughtDUI the unit metre even though "
        "the IACS source defines D_UI as displacement. This batch does not alter R13; I2-050 is readiness-only and tests "
        "the frozen interface exactly. The discrepancy should be reported separately as a vocabulary-contract limitation, not repaired from benchmark outcomes.\n\n"
        "Run:\n\npython3 scripts/validate_i2_batch_i.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = Path(__file__).name == "validate_i2_batch_i.py" or "--validate-only" in sys.argv
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__ == "__main__":
    main()
