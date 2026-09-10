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
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-e/"

REQS = [
    "TRF-040", "TRF-041", "TRF-042", "TRF-043", "TRF-044", "TRF-045",
    "TRF-046", "TRF-047", "TRF-048", "TRF-049", "TRF-050", "TRF-051",
    "TRF-052",
]

EXPECTED_MODES = {
    "TRF-040": "DIRECT_STATIC",
    "TRF-041": "COMPLEX_READINESS",
    "TRF-042": "DIRECT_CALCULATION",
    "TRF-043": "DIRECT_STATIC",
    "TRF-044": "DIRECT_CALCULATION",
    "TRF-045": "DIRECT_STATIC",
    "TRF-046": "DIRECT_STATIC",
    "TRF-047": "DIRECT_STATIC",
    "TRF-048": "DIRECT_CALCULATION",
    "TRF-049": "DIRECT_STATIC",
    "TRF-050": "DIRECT_STATIC",
    "TRF-051": "COMPLEX_READINESS",
    "TRF-052": "DIRECT_STATIC",
}

for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]

for req in ["TRF-041", "TRF-051"]:
    assert CONTRACTS[req].get("formulaExecutionRequired") is False

ONTOLOGY = Graph().parse(R13 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
KNOWN_NLTL = {
    str(s).split("#", 1)[1]
    for s in set(ONTOLOGY.subjects())
    if str(s).startswith(str(NLTL)) and "#" in str(s)
}

ICE_CLASSES = {
    "IA Super": NLTL.iceClassIaSuper,
    "IA": NLTL.iceClassIa,
    "IB": NLTL.iceClassIb,
    "IC": NLTL.iceClassIc,
    "II": NLTL.iceClassIi,
    "III": NLTL.iceClassIii,
}

REGIONS = {
    "bow": NLTL.bowRegion,
    "midbody": NLTL.midbodyRegion,
    "stern": NLTL.sternRegion,
}

BOUNDARY_M0 = {
    NLTL.bulkCarrierTopWingTankFrameCondition: 7.0,
    NLTL.singleDeckTankTopToMainDeckFrameCondition: 6.0,
    NLTL.multiDeckOrStringerContinuousFrameCondition: 5.7,
    NLTL.twoDeckFrameCondition: 5.0,
}


# ============================================================
# RDF HELPERS
# ============================================================

def new_graph(cid, root_class="ship"):
    g = Graph()
    ex = Namespace(BASE + cid + "/")
    g.bind("ex", ex)
    g.bind("nltl", NLTL)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("xsd", XSD)
    root = ex[root_class]
    g.add((root, RDF.type, NLTL[root_class]))
    return g, ex, root


def datatype_for(term):
    return {
        "xsd:boolean": XSD.boolean,
        "xsd:string": XSD.string,
        "xsd:integer": XSD.integer,
        "xsd:decimal": XSD.decimal,
        "xsd:date": XSD.date,
    }.get(REG[term].get("datatype", ""))


def add_value(g, s, term, value, ex, name=None, wrong_unit=False):
    row = REG.get(term)
    if row is None:
        raise RuntimeError(f"Unknown R13 term: {term}")
    kind = row["kind"]

    if kind == "QuantityProperty":
        unit = row.get("unitIri", "")
        if not unit:
            raise RuntimeError(f"{term} has no frozen unit")
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


def one(g, s, p):
    vals = list(g.objects(s, p))
    return vals[0] if len(vals) == 1 else None


def bool_value(g, s, term):
    o = one(g, s, NLTL[term])
    if o is None:
        return None
    try:
        v = o.toPython()
        return v if isinstance(v, bool) else None
    except Exception:
        return None


def int_value(g, s, term):
    o = one(g, s, NLTL[term])
    if o is None:
        return None
    try:
        return int(o.toPython())
    except Exception:
        return None


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


def qty_number(g, s, term):
    expected = REG.get(term, {}).get("unitIri", "")
    v, _ = qty_value_unit(g, s, term, expected if expected else None)
    return v


def close(a, b, tol=1e-7):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def exactly_one_subject(g, cls):
    xs = list(g.subjects(RDF.type, cls))
    return xs[0] if len(xs) == 1 else None


def typed_as(g, node, cls):
    return node is not None and (node, RDF.type, cls) in g


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
# TRF-040 — SHELL-PLATING ICE-BELT ADDITIONAL REQUIREMENTS
# ============================================================

def build_040(cid, ice="IA", speed=17.0, forefoot=None, upper=None,
              sidescuttle=False, deck_below=False, bulwark=None, freeing=None,
              omit=None):
    g, ex, ship = new_graph(cid)
    if omit != "iceClass":
        add_value(g, ship, "iceClass", ICE_CLASSES[ice], ex)
    if omit != "openWaterServiceSpeed":
        add_value(g, ship, "openWaterServiceSpeed", speed, ex)
    if forefoot is not None and omit != "forefootShellStrengtheningStatus":
        add_value(g, ship, "forefootShellStrengtheningStatus", forefoot, ex)
    if upper is not None and omit != "upperBowIceBeltStrengtheningStatus":
        add_value(g, ship, "upperBowIceBeltStrengtheningStatus", upper, ex)
    if omit != "sidescuttleInIceBelt":
        add_value(g, ship, "sidescuttleInIceBelt", sidescuttle, ex)
    if omit != "weatherDeckBelowIceBeltUpperLimit":
        add_value(g, ship, "weatherDeckBelowIceBeltUpperLimit", deck_below, ex)
    if bulwark is not None and omit != "bulwarkStrengthStatus":
        add_value(g, ship, "bulwarkStrengthStatus", bulwark, ex)
    if freeing is not None and omit != "freeingPortStrengthStatus":
        add_value(g, ship, "freeingPortStrengthStatus", freeing, ex)
    return g


def oracle_040(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None:
        return False
    ice = obj_value(g, ship, "iceClass")
    speed = qty_number(g, ship, "openWaterServiceSpeed")
    sides = bool_value(g, ship, "sidescuttleInIceBelt")
    deck = bool_value(g, ship, "weatherDeckBelowIceBeltUpperLimit")
    if ice not in ICE_CLASSES.values() or speed is None or sides is None or deck is None:
        return False
    if sides is not False:
        return False
    if ice == ICE_CLASSES["IA Super"]:
        if bool_value(g, ship, "forefootShellStrengtheningStatus") is not True:
            return False
    if ice in {ICE_CLASSES["IA Super"], ICE_CLASSES["IA"]} and speed >= 18.0:
        if bool_value(g, ship, "upperBowIceBeltStrengtheningStatus") is not True:
            return False
    if deck:
        if bool_value(g, ship, "bulwarkStrengthStatus") is not True:
            return False
        if bool_value(g, ship, "freeingPortStrengthStatus") is not True:
            return False
    return True


add_case("TRF-040", "P01", "PASS", "IA Super: forefoot strengthening is bow-equivalent and sidescuttles are excluded.",
         build_040("TRF-040-P01", ice="IA Super", speed=17.0, forefoot=True))
add_case("TRF-040", "P02", "PASS", "IA at the 18 kn trigger has upper-bow belt strengthening equivalent to the midbody requirement.",
         build_040("TRF-040-P02", ice="IA", speed=18.0, upper=True))
add_case("TRF-040", "P03", "PASS", "IB at high open-water speed does not trigger the IA/IA Super upper-bow extension.",
         build_040("TRF-040-P03", ice="IB", speed=20.0))
add_case("TRF-040", "P04", "PASS", "IA below 18 kn does not trigger the mandatory upper-bow extension.",
         build_040("TRF-040-P04", ice="IA", speed=17.9))
add_case("TRF-040", "P05", "PASS", "Weather deck below the ice-belt upper limit has compliant bulwark and freeing-port strength.",
         build_040("TRF-040-P05", ice="IC", deck_below=True, bulwark=True, freeing=True))
add_case("TRF-040", "F01", "FAIL", "A sidescuttle is situated in the ice belt.",
         build_040("TRF-040-F01", ice="IB", sidescuttle=True))
add_case("TRF-040", "F02", "FAIL", "IA Super forefoot strengthening is not provided.",
         build_040("TRF-040-F02", ice="IA Super", forefoot=False))
add_case("TRF-040", "F03", "FAIL", "IA at or above 18 kn lacks the required upper-bow belt strengthening.",
         build_040("TRF-040-F03", ice="IA", speed=18.0, upper=False))
add_case("TRF-040", "F04", "FAIL", "Weather deck is below the upper ice-belt limit but bulwark strength is non-compliant.",
         build_040("TRF-040-F04", ice="IC", deck_below=True, bulwark=False, freeing=True))
add_case("TRF-040", "F05", "FAIL", "Weather deck is below the upper ice-belt limit but freeing-port strength is non-compliant.",
         build_040("TRF-040-F05", ice="IC", deck_below=True, bulwark=True, freeing=False))


# ============================================================
# TRF-041 — SHELL-PLATING THICKNESS FORMULA READINESS
# ============================================================

def build_041(cid, orientation=NLTL.transverseFramingOrientation, missing=None, wrong_unit=None):
    g, ex, plating = new_graph(cid, "plating")
    vals = {
        "spacing": 0.6,
        "icePressure": 1.2,
        "platingPressure": 0.9,
        "yieldStrength": 235.0,
        "transversePlatingFactorF1": 0.92,
        "longitudinalPlatingFactorF2": 1.02,
        "corrosionAbrasionAddition": 2.0,
        "requiredShellPlatingThickness": 18.0,
    }
    for term, value in vals.items():
        if term != missing:
            add_value(g, plating, term, value, ex, wrong_unit=(term == wrong_unit))
    if missing != "platingFramingOrientation":
        add_value(g, plating, "platingFramingOrientation", orientation, ex)
    return g


def oracle_041(g):
    p = exactly_one_subject(g, NLTL.plating)
    if p is None:
        return False
    required_q = [
        "spacing", "icePressure", "platingPressure", "yieldStrength",
        "transversePlatingFactorF1", "longitudinalPlatingFactorF2",
        "corrosionAbrasionAddition", "requiredShellPlatingThickness",
    ]
    if any(qty_number(g, p, t) is None for t in required_q):
        return False
    orientation = obj_value(g, p, "platingFramingOrientation")
    return orientation in {NLTL.transverseFramingOrientation, NLTL.longitudinalFramingOrientation}


add_case("TRF-041", "P01", "PASS", "Complete transverse-framing formula-readiness graph with frozen R13 operands and result.", build_041("TRF-041-P01"))
add_case("TRF-041", "P02", "PASS", "Complete longitudinal-framing formula-readiness graph with frozen R13 operands and result.", build_041("TRF-041-P02", NLTL.longitudinalFramingOrientation))
for i, term in enumerate([
    "spacing", "icePressure", "platingPressure", "yieldStrength", "transversePlatingFactorF1",
    "longitudinalPlatingFactorF2", "corrosionAbrasionAddition", "platingFramingOrientation",
    "requiredShellPlatingThickness",
], 1):
    add_case("TRF-041", f"F{i:02d}", "FAIL", f"Formula-readiness term {term} is missing.", build_041(f"TRF-041-F{i:02d}", missing=term))
add_case("TRF-041", "F10", "FAIL", "Required shell-plating thickness uses the wrong unit.", build_041("TRF-041-F10", wrong_unit="requiredShellPlatingThickness"))


# ============================================================
# TRF-042 — LONGITUDINAL PLATING FACTOR f2
# ============================================================

def f2_expected(h, s):
    if s <= 0:
        return None
    r = h / s
    if r <= 0 or r > 1.8 + 1e-9:
        return None
    if r <= 1.0 + 1e-9:
        return 0.4 / r + 0.6
    return 1.4 - 0.4 * r


def build_042(cid, h=0.3, s=0.6, result=None, missing=None, wrong_unit=None):
    g, ex, p = new_graph(cid, "plating")
    if missing != "designIceLoadHeight":
        add_value(g, p, "designIceLoadHeight", h, ex, wrong_unit=(wrong_unit == "designIceLoadHeight"))
    if missing != "spacing":
        add_value(g, p, "spacing", s, ex, wrong_unit=(wrong_unit == "spacing"))
    if missing != "longitudinalPlatingFactorF2":
        if result is None:
            result = f2_expected(h, s)
        add_value(g, p, "longitudinalPlatingFactorF2", result, ex, wrong_unit=(wrong_unit == "longitudinalPlatingFactorF2"))
    return g


def oracle_042(g):
    p = exactly_one_subject(g, NLTL.plating)
    if p is None:
        return False
    h = qty_number(g, p, "designIceLoadHeight")
    s = qty_number(g, p, "spacing")
    r = qty_number(g, p, "longitudinalPlatingFactorF2")
    exp = None if h is None or s is None else f2_expected(h, s)
    return exp is not None and close(r, exp)


for suffix, h, s in [("P01", 0.3, 0.6), ("P02", 0.6, 0.6), ("P03", 0.72, 0.6), ("P04", 1.08, 0.6)]:
    add_case("TRF-042", suffix, "PASS", f"Correct f2 calculation at h/s={h/s:.3g}.", build_042(f"TRF-042-{suffix}", h=h, s=s))
add_case("TRF-042", "F01", "FAIL", "f2 numeric result is wrong.", build_042("TRF-042-F01", result=0.2))
add_case("TRF-042", "F02", "FAIL", "designIceLoadHeight is missing.", build_042("TRF-042-F02", missing="designIceLoadHeight", result=1.4))
add_case("TRF-042", "F03", "FAIL", "spacing is missing.", build_042("TRF-042-F03", missing="spacing", result=1.4))
add_case("TRF-042", "F04", "FAIL", "designIceLoadHeight has the wrong unit.", build_042("TRF-042-F04", wrong_unit="designIceLoadHeight"))


# ============================================================
# TRF-043 — FRAME-STRENGTHENING TERMINATION AT ADJACENT BOUNDARY
# ============================================================

def build_043(cid, extension=250.0, boundary_cls=NLTL.deckStructure, permitted=True, missing=None):
    g, ex, ship = new_graph(cid)
    case = ex.terminationCase
    g.add((case, RDF.type, NLTL.framingIceStrengtheningTerminationCase))
    if missing != "hasFramingIceStrengtheningTerminationCase":
        add_value(g, ship, "hasFramingIceStrengtheningTerminationCase", case, ex)
    if missing != "extensionBeyondAdjacentDeckOrTankBoundary":
        add_value(g, case, "extensionBeyondAdjacentDeckOrTankBoundary", extension, ex)
    boundary = ex.boundary
    g.add((boundary, RDF.type, boundary_cls))
    if missing != "terminationAdjacentBoundary":
        add_value(g, case, "terminationAdjacentBoundary", boundary, ex)
    if missing != "iceStrengtheningTerminationAtAdjacentBoundaryPermitted":
        add_value(g, case, "iceStrengtheningTerminationAtAdjacentBoundaryPermitted", permitted, ex)
    return g


def oracle_043(g):
    ship = exactly_one_subject(g, NLTL.ship)
    case = exactly_one_subject(g, NLTL.framingIceStrengtheningTerminationCase)
    if ship is None or case is None or obj_value(g, ship, "hasFramingIceStrengtheningTerminationCase") != case:
        return False
    ext = qty_number(g, case, "extensionBeyondAdjacentDeckOrTankBoundary")
    boundary = obj_value(g, case, "terminationAdjacentBoundary")
    permitted = bool_value(g, case, "iceStrengtheningTerminationAtAdjacentBoundaryPermitted")
    if ext is None or boundary is None or permitted is None:
        return False
    allowed = any(typed_as(g, boundary, c) for c in [NLTL.deckStructure, NLTL.tankBoundaryPlating, NLTL.tankTop])
    if not allowed:
        return False
    return permitted is (ext <= 250.0)


add_case("TRF-043", "P01", "PASS", "Exactly 250 mm extension terminates at a deck boundary and is permitted.", build_043("TRF-043-P01", 250.0, NLTL.deckStructure, True))
add_case("TRF-043", "P02", "PASS", "Sub-250 mm extension terminates at a tank-top boundary and is permitted.", build_043("TRF-043-P02", 100.0, NLTL.tankTop, True))
add_case("TRF-043", "P03", "PASS", "Sub-250 mm extension terminates at tank boundary plating and is permitted.", build_043("TRF-043-P03", 249.9, NLTL.tankBoundaryPlating, True))
add_case("TRF-043", "P04", "PASS", "Extension above 250 mm is correctly not treated as eligible for the termination permission.", build_043("TRF-043-P04", 251.0, NLTL.deckStructure, False))
add_case("TRF-043", "F01", "FAIL", "At the 250 mm boundary the permitted flag is incorrectly false.", build_043("TRF-043-F01", 250.0, NLTL.deckStructure, False))
add_case("TRF-043", "F02", "FAIL", "Extension above 250 mm is incorrectly marked permitted.", build_043("TRF-043-F02", 251.0, NLTL.deckStructure, True))
add_case("TRF-043", "F03", "FAIL", "Termination boundary is not one of the source-permitted deck/tank boundary types.", build_043("TRF-043-F03", 200.0, NLTL.supportingStructure, True))
add_case("TRF-043", "F04", "FAIL", "Extension beyond the adjacent boundary is missing.", build_043("TRF-043-F04", missing="extensionBeyondAdjacentDeckOrTankBoundary"))


# ============================================================
# TRF-044 — TRANSVERSE-FRAME SECTION MODULUS / SHEAR AREA
# ============================================================

def calc_044(p, s, h, l, m0, sy):
    mt = 7.0 * m0 / (7.0 - 5.0 * h / l)
    z = p * s * h * l / (mt * sy) * 1e6
    a = math.sqrt(3.0) * 1.2 * p * h * s / (2.0 * sy) * 1e4
    return mt, z, a


def build_044(cid, p=1.2, s=0.6, h=0.35, l=3.0,
              cond=NLTL.bulkCarrierTopWingTankFrameCondition, m0=None,
              mt=None, z=None, a=None, missing=None, wrong_unit=None):
    g, ex, frame = new_graph(cid, "transverseFrame")
    if m0 is None:
        m0 = BOUNDARY_M0[cond]
    sy = 235.0
    cmt, cz, ca = calc_044(p, s, h, l, m0, sy)
    if mt is None: mt = cmt
    if z is None: z = cz
    if a is None: a = ca
    vals = {
        "icePressure": p, "spacing": s, "designIceLoadHeight": h, "span": l,
        "frameBoundaryConditionFactorM0": m0, "yieldStrength": sy,
        "frameMomentFactorMt": mt, "sectionModulus": z, "requiredShearArea": a,
    }
    for term, value in vals.items():
        if term != missing:
            add_value(g, frame, term, value, ex, wrong_unit=(term == wrong_unit))
    if missing != "frameBoundaryConditionType":
        add_value(g, frame, "frameBoundaryConditionType", cond, ex)
    return g


def oracle_044(g):
    f = exactly_one_subject(g, NLTL.transverseFrame)
    if f is None:
        return False
    cond = obj_value(g, f, "frameBoundaryConditionType")
    if cond not in BOUNDARY_M0:
        return False
    vals = [qty_number(g, f, t) for t in ["icePressure", "spacing", "designIceLoadHeight", "span", "frameBoundaryConditionFactorM0", "yieldStrength", "frameMomentFactorMt", "sectionModulus", "requiredShearArea"]]
    if any(v is None for v in vals):
        return False
    p, s, h, l, m0, sy, mt, z, a = vals
    if not close(m0, BOUNDARY_M0[cond]):
        return False
    if l <= 0 or 7.0 - 5.0 * h / l <= 0 or sy <= 0:
        return False
    emt, ez, ea = calc_044(p, s, h, l, m0, sy)
    return close(mt, emt) and close(z, ez) and close(a, ea)


for i, cond in enumerate(BOUNDARY_M0, 1):
    add_case("TRF-044", f"P{i:02d}", "PASS", f"Correct transverse-frame calculation using source Table 4-7 m0={BOUNDARY_M0[cond]}.", build_044(f"TRF-044-P{i:02d}", cond=cond))
add_case("TRF-044", "F01", "FAIL", "m0 does not match the selected source boundary condition.", build_044("TRF-044-F01", cond=NLTL.bulkCarrierTopWingTankFrameCondition, m0=6.0))
add_case("TRF-044", "F02", "FAIL", "Calculated frame moment factor mt is wrong.", build_044("TRF-044-F02", mt=1.0))
add_case("TRF-044", "F03", "FAIL", "Calculated section modulus is wrong.", build_044("TRF-044-F03", z=1.0))
add_case("TRF-044", "F04", "FAIL", "Calculated required shear area is wrong.", build_044("TRF-044-F04", a=1.0))
add_case("TRF-044", "F05", "FAIL", "Required span operand is missing.", build_044("TRF-044-F05", missing="span"))
add_case("TRF-044", "F06", "FAIL", "Ice pressure uses the wrong unit.", build_044("TRF-044-F06", wrong_unit="icePressure"))


# ============================================================
# TRF-045 — <15% FRAME-SPAN PERMISSIVE ORDINARY SCANTLINGS RULE
# ============================================================

def build_045(cid, span=4.0, zone=0.4, ordinary=True, missing=None, wrong_unit=None):
    g, ex, frame = new_graph(cid, "frame")
    if missing != "span": add_value(g, frame, "span", span, ex, wrong_unit=(wrong_unit == "span"))
    if missing != "frameSpanWithinIceStrengtheningZone": add_value(g, frame, "frameSpanWithinIceStrengtheningZone", zone, ex, wrong_unit=(wrong_unit == "frameSpanWithinIceStrengtheningZone"))
    if missing != "ordinaryFrameScantlingsUsed": add_value(g, frame, "ordinaryFrameScantlingsUsed", ordinary, ex)
    return g


def oracle_045(g):
    f = exactly_one_subject(g, NLTL.frame)
    if f is None:
        return False
    span = qty_number(g, f, "span")
    zone = qty_number(g, f, "frameSpanWithinIceStrengtheningZone")
    ordinary = bool_value(g, f, "ordinaryFrameScantlingsUsed")
    if span is None or zone is None or ordinary is None or span <= 0 or zone < 0:
        return False
    ratio = zone / span
    if ratio < 0.15:
        return True  # source says ordinary scantlings MAY be used, not must be used
    return ordinary is False


add_case("TRF-045", "P01", "PASS", "Below 15% of span: ordinary scantlings may be used.", build_045("TRF-045-P01", 4.0, 0.596, True))
add_case("TRF-045", "P02", "PASS", "Below 15% of span: retaining ice-strengthened scantlings also remains compliant because the rule is permissive.", build_045("TRF-045-P02", 4.0, 0.596, False))
add_case("TRF-045", "P03", "PASS", "Exactly 15% is not 'less than 15%'; ordinary scantlings are therefore not invoked.", build_045("TRF-045-P03", 4.0, 0.6, False))
add_case("TRF-045", "P04", "PASS", "Above 15% ordinary scantlings are not used under this exception.", build_045("TRF-045-P04", 4.0, 0.8, False))
add_case("TRF-045", "F01", "FAIL", "Exactly 15% incorrectly uses the less-than-15% ordinary-scantlings exception.", build_045("TRF-045-F01", 4.0, 0.6, True))
add_case("TRF-045", "F02", "FAIL", "Above 15% incorrectly uses ordinary scantlings under this exception.", build_045("TRF-045-F02", 4.0, 0.8, True))
add_case("TRF-045", "F03", "FAIL", "Total frame span is missing.", build_045("TRF-045-F03", missing="span"))
add_case("TRF-045", "F04", "FAIL", "Ice-strengthened portion of span has the wrong unit.", build_045("TRF-045-F04", wrong_unit="frameSpanWithinIceStrengtheningZone"))


# ============================================================
# TRF-046 — UPPER END OF TRANSVERSE FRAMING
# ============================================================

def build_046(cid, frame_cls=NLTL.mainFrame, standard_support=NLTL.deckStructure,
              alternative=False, same=True, omit=None):
    g, ex, frame = new_graph(cid, "frame")
    g.add((frame, RDF.type, NLTL.transverseFrame))
    g.add((frame, RDF.type, frame_cls))
    part = ex.strengthenedPart
    g.add((part, RDF.type, NLTL.frameStrengthenedPart))
    if omit != "hasStrengthenedPart": add_value(g, frame, "hasStrengthenedPart", part, ex)
    upper = ex.upperEnd
    if omit != "hasUpperEnd": add_value(g, frame, "hasUpperEnd", upper, ex)

    if not alternative:
        if standard_support is not None and omit != "hasAttachedSupportingStructure":
            support = ex.support
            g.add((support, RDF.type, standard_support))
            add_value(g, frame, "hasAttachedSupportingStructure", support, ex)
    else:
        support = ex.support
        g.add((support, RDF.type, NLTL.deckStructure))
        if omit != "hasTerminationAboveSupportingStructure": add_value(g, frame, "hasTerminationAboveSupportingStructure", support, ex)
        if omit != "supportingStructureAtOrAboveIceBeltUpperLimit": add_value(g, support, "supportingStructureAtOrAboveIceBeltUpperLimit", True, ex)
        if omit != "ordinaryFrameScantlingsUsed": add_value(g, frame, "ordinaryFrameScantlingsUsed", True, ex)
        if frame_cls == NLTL.intermediateIceFrame:
            h = ex.horizontalMember
            g.add((h, RDF.type, NLTL.horizontalConnectionMember))
            main = ex.adjacentMainFrame
            g.add((main, RDF.type, NLTL.mainFrame))
            if omit != "hasHorizontalConnectionMember": add_value(g, frame, "hasHorizontalConnectionMember", h, ex)
            if omit != "connectsToAdjacentMainFrame": add_value(g, h, "connectsToAdjacentMainFrame", main, ex)
            if omit != "sameScantlingsAsMainFrame": add_value(g, h, "sameScantlingsAsMainFrame", same, ex)
    return g


def oracle_046(g):
    frames = list(g.subjects(RDF.type, NLTL.frame))
    if len(frames) != 1:
        return False
    f = frames[0]
    if (f, RDF.type, NLTL.transverseFrame) not in g:
        return False
    if obj_value(g, f, "hasStrengthenedPart") is None or obj_value(g, f, "hasUpperEnd") is None:
        return False
    support = obj_value(g, f, "hasAttachedSupportingStructure")
    if support is not None:
        return any(typed_as(g, support, c) for c in [NLTL.deckStructure, NLTL.tankBoundaryPlating, NLTL.iceStringer])
    term = obj_value(g, f, "hasTerminationAboveSupportingStructure")
    if term is None or bool_value(g, term, "supportingStructureAtOrAboveIceBeltUpperLimit") is not True:
        return False
    if bool_value(g, f, "ordinaryFrameScantlingsUsed") is not True:
        return False
    if (f, RDF.type, NLTL.intermediateIceFrame) in g:
        h = obj_value(g, f, "hasHorizontalConnectionMember")
        if h is None or not typed_as(g, h, NLTL.horizontalConnectionMember):
            return False
        if obj_value(g, h, "connectsToAdjacentMainFrame") is None:
            return False
        if bool_value(g, h, "sameScantlingsAsMainFrame") is not True:
            return False
    return True


add_case("TRF-046", "P01", "PASS", "Upper end is attached to a deck.", build_046("TRF-046-P01", standard_support=NLTL.deckStructure))
add_case("TRF-046", "P02", "PASS", "Upper end is attached to tank boundary plating.", build_046("TRF-046-P02", standard_support=NLTL.tankBoundaryPlating))
add_case("TRF-046", "P03", "PASS", "Upper end is attached to an ice stringer.", build_046("TRF-046-P03", standard_support=NLTL.iceStringer))
add_case("TRF-046", "P04", "PASS", "Intermediate-frame termination above a qualifying support uses the permitted horizontal-member route.", build_046("TRF-046-P04", frame_cls=NLTL.intermediateIceFrame, alternative=True))
add_case("TRF-046", "F01", "FAIL", "No permitted upper-end supporting structure or source exception route is present.", build_046("TRF-046-F01", standard_support=None))
add_case("TRF-046", "F02", "FAIL", "Upper end is attached only to a generic unsupported structure type.", build_046("TRF-046-F02", standard_support=NLTL.supportingStructure))
add_case("TRF-046", "F03", "FAIL", "Intermediate exception route uses a horizontal member that does not have the same scantlings as the main frame.", build_046("TRF-046-F03", frame_cls=NLTL.intermediateIceFrame, alternative=True, same=False))
add_case("TRF-046", "F04", "FAIL", "Intermediate exception route is missing its horizontal connection member.", build_046("TRF-046-F04", frame_cls=NLTL.intermediateIceFrame, alternative=True, omit="hasHorizontalConnectionMember"))


# ============================================================
# TRF-047 — LOWER END OF TRANSVERSE FRAMING
# ============================================================

def build_047(cid, frame_cls=NLTL.mainFrame, standard_support=NLTL.deckStructure,
              alternative=False, same=True, main_below=True, omit=None):
    g, ex, frame = new_graph(cid, "frame")
    g.add((frame, RDF.type, NLTL.transverseFrame))
    g.add((frame, RDF.type, frame_cls))
    part = ex.strengthenedPart
    g.add((part, RDF.type, NLTL.frameStrengthenedPart))
    if omit != "hasStrengthenedPart": add_value(g, frame, "hasStrengthenedPart", part, ex)
    lower = ex.lowerEnd
    if omit != "hasLowerEnd": add_value(g, frame, "hasLowerEnd", lower, ex)

    if not alternative:
        if standard_support is not None and omit != "hasAttachedSupportingStructure":
            support = ex.support
            g.add((support, RDF.type, standard_support))
            add_value(g, frame, "hasAttachedSupportingStructure", support, ex)
    else:
        support = ex.support
        g.add((support, RDF.type, NLTL.tankTop))
        if omit != "hasTerminationBelowSupportingStructure": add_value(g, frame, "hasTerminationBelowSupportingStructure", support, ex)
        if omit != "supportingStructureAtOrBelowIceBeltLowerLimit": add_value(g, support, "supportingStructureAtOrBelowIceBeltLowerLimit", True, ex)
        h = ex.horizontalMember
        g.add((h, RDF.type, NLTL.horizontalConnectionMember))
        main = ex.adjacentMainFrame
        g.add((main, RDF.type, NLTL.mainFrame))
        if omit != "hasHorizontalConnectionMember": add_value(g, frame, "hasHorizontalConnectionMember", h, ex)
        if omit != "connectsToAdjacentMainFrame": add_value(g, h, "connectsToAdjacentMainFrame", main, ex)
        if omit != "sameScantlingsAsMainFrame": add_value(g, h, "sameScantlingsAsMainFrame", same, ex)
        if omit != "mainFrameBelowIceBeltStrengthened": add_value(g, main, "mainFrameBelowIceBeltStrengthened", main_below, ex)
    return g


def oracle_047(g):
    frames = list(g.subjects(RDF.type, NLTL.frame))
    if len(frames) != 1:
        return False
    f = frames[0]
    if (f, RDF.type, NLTL.transverseFrame) not in g:
        return False
    if obj_value(g, f, "hasStrengthenedPart") is None or obj_value(g, f, "hasLowerEnd") is None:
        return False
    support = obj_value(g, f, "hasAttachedSupportingStructure")
    if support is not None:
        return any(typed_as(g, support, c) for c in [NLTL.deckStructure, NLTL.tankBoundaryPlating, NLTL.tankTop, NLTL.iceStringer])
    if (f, RDF.type, NLTL.intermediateIceFrame) not in g:
        return False
    term = obj_value(g, f, "hasTerminationBelowSupportingStructure")
    if term is None or bool_value(g, term, "supportingStructureAtOrBelowIceBeltLowerLimit") is not True:
        return False
    h = obj_value(g, f, "hasHorizontalConnectionMember")
    if h is None or obj_value(g, h, "connectsToAdjacentMainFrame") is None or bool_value(g, h, "sameScantlingsAsMainFrame") is not True:
        return False
    main = obj_value(g, h, "connectsToAdjacentMainFrame")
    if bool_value(g, main, "mainFrameBelowIceBeltStrengthened") is not True:
        return False
    return True


add_case("TRF-047", "P01", "PASS", "Lower end is attached to a deck.", build_047("TRF-047-P01", standard_support=NLTL.deckStructure))
add_case("TRF-047", "P02", "PASS", "Lower end is attached to a tank top.", build_047("TRF-047-P02", standard_support=NLTL.tankTop))
add_case("TRF-047", "P03", "PASS", "Lower end is attached to an ice stringer.", build_047("TRF-047-P03", standard_support=NLTL.iceStringer))
add_case("TRF-047", "P04", "PASS", "Intermediate-frame lower termination uses the permitted horizontal-member route and adjacent main frame remains ice-strengthened.", build_047("TRF-047-P04", frame_cls=NLTL.intermediateIceFrame, alternative=True))
add_case("TRF-047", "F01", "FAIL", "No permitted lower-end attachment is present.", build_047("TRF-047-F01", standard_support=None))
add_case("TRF-047", "F02", "FAIL", "Lower end is attached only to a generic unsupported structure type.", build_047("TRF-047-F02", standard_support=NLTL.supportingStructure))
add_case("TRF-047", "F03", "FAIL", "Intermediate lower-end exception has a horizontal member with non-matching scantlings.", build_047("TRF-047-F03", frame_cls=NLTL.intermediateIceFrame, alternative=True, same=False))
add_case("TRF-047", "F04", "FAIL", "Adjacent main frame below the ice belt is not ice-strengthened.", build_047("TRF-047-F04", frame_cls=NLTL.intermediateIceFrame, alternative=True, main_below=False))


# ============================================================
# TRF-048 — LONGITUDINAL-FRAME SECTION MODULUS / SHEAR AREA
# ============================================================

def calc_048(p, h, s, l, m, sy):
    f4 = 1.0 - 0.2 * h / s
    z = f4 * p * h * l * l / (4.0 * m * sy) * 1e6
    a = math.sqrt(3.0) * f4 * 2.16 * p * h * l / (2.0 * sy) * 1e4
    return f4, z, a


def build_048(cid, p=1.1, h=0.3, s=0.6, l=3.5, m=13.3, sy=235.0,
              condition=NLTL.continuousBeamWithBracketsFrameCondition, different=False,
              f4=None, z=None, a=None, actual=None, gross=None, bracket=None,
              missing=None, wrong_unit=None):
    g, ex, frame = new_graph(cid, "longitudinalFrame")
    ef4, ez, ea = calc_048(p, h, s, l, m, sy)
    if f4 is None: f4 = ef4
    if z is None: z = ez
    if a is None: a = ea
    vals = {
        "icePressure": p, "designIceLoadHeight": h, "spacing": s, "span": l,
        "frameMomentFactorM": m, "yieldStrength": sy,
        "longitudinalFrameLoadDistributionFactorF4": f4, "sectionModulus": z,
        "requiredShearArea": a,
    }
    for term, value in vals.items():
        if term != missing:
            add_value(g, frame, term, value, ex, wrong_unit=(term == wrong_unit))
    if missing != "frameBoundaryConditionType": add_value(g, frame, "frameBoundaryConditionType", condition, ex)
    if missing != "significantlyDifferentBoundaryConditions": add_value(g, frame, "significantlyDifferentBoundaryConditions", different, ex)
    if gross is not None: add_value(g, frame, "grossFrameShearArea", gross, ex)
    if bracket is not None: add_value(g, frame, "bracketArea", bracket, ex)
    if actual is not None: add_value(g, frame, "actualFrameShearArea", actual, ex)
    return g


def oracle_048(g):
    f = exactly_one_subject(g, NLTL.longitudinalFrame)
    if f is None:
        return False
    condition = obj_value(g, f, "frameBoundaryConditionType")
    different = bool_value(g, f, "significantlyDifferentBoundaryConditions")
    vals = [qty_number(g, f, t) for t in ["icePressure", "designIceLoadHeight", "spacing", "span", "frameMomentFactorM", "yieldStrength", "longitudinalFrameLoadDistributionFactorF4", "sectionModulus", "requiredShearArea"]]
    if condition is None or different is None or any(v is None for v in vals):
        return False
    p, h, s, l, m, sy, f4, z, a = vals
    if s <= 0 or l <= 0 or m <= 0 or sy <= 0:
        return False
    if condition == NLTL.continuousBeamWithBracketsFrameCondition and different is False and not close(m, 13.3):
        return False
    if different is True and m > 13.3 + 1e-7:
        return False
    ef4, ez, ea = calc_048(p, h, s, l, m, sy)
    if not (close(f4, ef4) and close(z, ez) and close(a, ea)):
        return False
    gross = qty_number(g, f, "grossFrameShearArea")
    bracket = qty_number(g, f, "bracketArea")
    actual = qty_number(g, f, "actualFrameShearArea")
    present = [gross is not None, bracket is not None, actual is not None]
    if any(present) and not all(present):
        return False
    if all(present) and not close(actual, gross - bracket):
        return False
    return True


add_case("TRF-048", "P01", "PASS", "Correct longitudinal-frame calculation for continuous beam with brackets using m=13.3.", build_048("TRF-048-P01"))
add_case("TRF-048", "P02", "PASS", "Second correct longitudinal-frame numeric case.", build_048("TRF-048-P02", p=1.4, h=0.35, s=0.7, l=4.0))
add_case("TRF-048", "P03", "PASS", "Significantly different boundary conditions use a smaller moment factor and recomputed results.", build_048("TRF-048-P03", m=12.0, different=True))
add_case("TRF-048", "P04", "PASS", "Bracket area is excluded from actual frame shear area.", build_048("TRF-048-P04", gross=30.0, bracket=4.0, actual=26.0))
add_case("TRF-048", "F01", "FAIL", "Default continuous-beam-with-brackets case uses m other than 13.3.", build_048("TRF-048-F01", m=12.0, different=False))
add_case("TRF-048", "F02", "FAIL", "Longitudinal load-distribution factor f4 is wrong.", build_048("TRF-048-F02", f4=0.1))
add_case("TRF-048", "F03", "FAIL", "Calculated section modulus is wrong.", build_048("TRF-048-F03", z=1.0))
add_case("TRF-048", "F04", "FAIL", "Calculated required shear area is wrong.", build_048("TRF-048-F04", a=1.0))
add_case("TRF-048", "F05", "FAIL", "Required span operand is missing.", build_048("TRF-048-F05", missing="span"))
add_case("TRF-048", "F06", "FAIL", "Yield strength uses the wrong unit.", build_048("TRF-048-F06", wrong_unit="yieldStrength"))
add_case("TRF-048", "F07", "FAIL", "Actual frame shear area incorrectly includes the bracket area.", build_048("TRF-048-F07", gross=30.0, bracket=4.0, actual=30.0))


# ============================================================
# TRF-049 — FRAME ATTACHMENT TO SUPPORTING STRUCTURES
# ============================================================

def build_049(cid, within=True, frame_cls=NLTL.frame, effective=True,
              longitudinal=False, transverse=False, terminates=False,
              bracket_present=False, similar=False, passes=False, side_count=2,
              bracket_thickness=12.0, web_thickness=10.0, edge=True,
              omit=None):
    g, ex, frame = new_graph(cid, "frame")
    if frame_cls != NLTL.frame:
        g.add((frame, RDF.type, frame_cls))
    if longitudinal: g.add((frame, RDF.type, NLTL.longitudinalFrame))
    if transverse: g.add((frame, RDF.type, NLTL.transverseFrame))
    if omit != "withinIceStrengthenedArea": add_value(g, frame, "withinIceStrengthenedArea", within, ex)
    if within and omit != "effectiveAttachmentConfirmed": add_value(g, frame, "effectiveAttachmentConfirmed", effective, ex)

    if longitudinal:
        wf = ex.webFrame
        bh = ex.bulkhead
        g.add((wf, RDF.type, NLTL.supportingStructure))
        g.add((bh, RDF.type, NLTL.bulkhead))
        if omit != "hasSupportingWebFrame": add_value(g, frame, "hasSupportingWebFrame", wf, ex)
        if omit != "hasSupportingBulkhead": add_value(g, frame, "hasSupportingBulkhead", bh, ex)
        bracket_present = True if omit != "hasConnectionBracket" else False

    if terminates:
        add_value(g, frame, "terminatesAtDeckOrIceStringer", True, ex)

    bracket = None
    if bracket_present:
        bracket = ex.bracket
        g.add((bracket, RDF.type, NLTL.connectionBracket))
        if omit != "hasConnectionBracket": add_value(g, frame, "hasConnectionBracket", bracket, ex)
        if omit != "bracketThickness": add_value(g, bracket, "bracketThickness", bracket_thickness, ex)
        if omit != "bracketEdgeStiffened": add_value(g, bracket, "bracketEdgeStiffened", edge, ex)
        if omit != "frameWebThickness": add_value(g, frame, "frameWebThickness", web_thickness, ex)
    if similar and omit != "similarAttachmentConstructionPresent":
        add_value(g, frame, "similarAttachmentConstructionPresent", True, ex)

    if passes:
        add_value(g, frame, "passesThroughSupportingStructure", True, ex)
        if omit != "webPlateConnectionSideCount": add_value(g, frame, "webPlateConnectionSideCount", side_count, ex)
    return g


def oracle_049(g):
    frames = list(g.subjects(RDF.type, NLTL.frame))
    if len(frames) != 1:
        return False
    f = frames[0]
    within = bool_value(g, f, "withinIceStrengthenedArea")
    if within is None:
        return False
    if not within:
        return True
    if bool_value(g, f, "effectiveAttachmentConfirmed") is not True:
        return False
    if (f, RDF.type, NLTL.longitudinalFrame) in g:
        if obj_value(g, f, "hasSupportingWebFrame") is None or obj_value(g, f, "hasSupportingBulkhead") is None:
            return False
        if obj_value(g, f, "hasConnectionBracket") is None:
            return False
    if bool_value(g, f, "terminatesAtDeckOrIceStringer") is True:
        if obj_value(g, f, "hasConnectionBracket") is None and bool_value(g, f, "similarAttachmentConstructionPresent") is not True:
            return False
    if bool_value(g, f, "passesThroughSupportingStructure") is True:
        if int_value(g, f, "webPlateConnectionSideCount") != 2:
            return False
    bracket = obj_value(g, f, "hasConnectionBracket")
    if bracket is not None:
        bt = qty_number(g, bracket, "bracketThickness")
        wt = qty_number(g, f, "frameWebThickness")
        if bt is None or wt is None or bt < wt:
            return False
        if bool_value(g, bracket, "bracketEdgeStiffened") is not True:
            return False
    return True


add_case("TRF-049", "P01", "PASS", "Frame outside the ice-strengthened area is outside the attachment obligation.", build_049("TRF-049-P01", within=False))
add_case("TRF-049", "P02", "PASS", "Generic frame within the ice-strengthened area has effective attachment confirmed.", build_049("TRF-049-P02"))
add_case("TRF-049", "P03", "PASS", "Longitudinal frame has supporting web-frame/bulkhead relationships and bracket attachment.", build_049("TRF-049-P03", longitudinal=True))
add_case("TRF-049", "P04", "PASS", "Transverse frame terminating at deck/stringer uses a bracket.", build_049("TRF-049-P04", transverse=True, terminates=True, bracket_present=True))
add_case("TRF-049", "P05", "PASS", "Transverse frame terminating at deck/stringer uses permitted similar attachment construction.", build_049("TRF-049-P05", transverse=True, terminates=True, similar=True))
add_case("TRF-049", "P06", "PASS", "Frame passing through a support connects both web-plate sides.", build_049("TRF-049-P06", passes=True, side_count=2))
add_case("TRF-049", "P07", "PASS", "Installed bracket equals the frame-web thickness and has buckling-stiffened edge.", build_049("TRF-049-P07", bracket_present=True, bracket_thickness=10.0, web_thickness=10.0, edge=True))
add_case("TRF-049", "F01", "FAIL", "Frame within ice-strengthened area lacks effective attachment confirmation.", build_049("TRF-049-F01", effective=False))
add_case("TRF-049", "F02", "FAIL", "Longitudinal-frame branch lacks its required connection bracket.", build_049("TRF-049-F02", longitudinal=True, omit="hasConnectionBracket"))
add_case("TRF-049", "F03", "FAIL", "Passing-through frame connects only one side of the web plate.", build_049("TRF-049-F03", passes=True, side_count=1))
add_case("TRF-049", "F04", "FAIL", "Installed bracket is thinner than the frame web.", build_049("TRF-049-F04", bracket_present=True, bracket_thickness=8.0, web_thickness=10.0))
add_case("TRF-049", "F05", "FAIL", "Installed bracket edge is not stiffened against buckling.", build_049("TRF-049-F05", bracket_present=True, edge=False))


# ============================================================
# TRF-050 — DOUBLE-CONTINUOUS FRAME/SHELL WELD + SCALLOPING RULE
# ============================================================

def build_050(cid, weld=NLTL.doubleContinuousWeld, scallop=False, butt=False, missing=None, wrong_owner=False):
    g, ex, frame = new_graph(cid, "frame")
    rec = ex.attachmentRecord
    g.add((rec, RDF.type, NLTL.frameAttachmentRecord))
    if missing != "frameAttachment": add_value(g, frame, "frameAttachment", rec, ex)
    if missing != "frameShellWeldType":
        add_value(g, frame if wrong_owner else rec, "frameShellWeldType", weld, ex)
    if missing != "scallopingPresent": add_value(g, rec, "scallopingPresent", scallop, ex)
    if missing != "shellPlateButtCrossing": add_value(g, rec, "shellPlateButtCrossing", butt, ex)
    return g


def oracle_050(g):
    f = exactly_one_subject(g, NLTL.frame)
    rec = exactly_one_subject(g, NLTL.frameAttachmentRecord)
    if f is None or rec is None or obj_value(g, f, "frameAttachment") != rec:
        return False
    if obj_value(g, rec, "frameShellWeldType") != NLTL.doubleContinuousWeld:
        return False
    scallop = bool_value(g, rec, "scallopingPresent")
    butt = bool_value(g, rec, "shellPlateButtCrossing")
    if scallop is None or butt is None:
        return False
    return (not scallop) or butt


add_case("TRF-050", "P01", "PASS", "Double-continuous weld with no scalloping.", build_050("TRF-050-P01"))
add_case("TRF-050", "P02", "PASS", "Scalloping is present only at a shell-plate butt crossing, the explicit exception.", build_050("TRF-050-P02", scallop=True, butt=True))
add_case("TRF-050", "F01", "FAIL", "Scalloping is present away from a shell-plate butt crossing.", build_050("TRF-050-F01", scallop=True, butt=False))
add_case("TRF-050", "F02", "FAIL", "Frame-shell weld type is not double continuous.", build_050("TRF-050-F02", weld=NLTL.evidenceStateApproved))
add_case("TRF-050", "F03", "FAIL", "Weld type is missing.", build_050("TRF-050-F03", missing="frameShellWeldType"))
add_case("TRF-050", "F04", "FAIL", "Scalloping state is missing.", build_050("TRF-050-F04", missing="scallopingPresent"))
add_case("TRF-050", "F05", "FAIL", "Weld type is attached to the wrong owner instead of the attachment record.", build_050("TRF-050-F05", wrong_owner=True))


# ============================================================
# TRF-051 — FRAME WEB-THICKNESS READINESS
# ============================================================

def build_051(cid, profile=NLTL.profileSection, in_lieu=False, missing=None, wrong_unit=None):
    g, ex, hull = new_graph(cid, "hullStructure")
    vals = {
        "adjacentFrameHeight": 500.0,
        "yieldStrength": 235.0,
        "netShellPlatingThickness": 18.0,
        "corrosionAbrasionAddition": 2.0,
        "frameWebThickness": 10.0,
    }
    for term, value in vals.items():
        if term != missing:
            add_value(g, hull, term, value, ex, wrong_unit=(term == wrong_unit))
    if missing != "frameProfileType": add_value(g, hull, "frameProfileType", profile, ex)
    if missing != "inLieuOfFrame": add_value(g, hull, "inLieuOfFrame", in_lieu, ex)
    return g


def oracle_051(g):
    h = exactly_one_subject(g, NLTL.hullStructure)
    if h is None:
        return False
    for term in ["adjacentFrameHeight", "yieldStrength", "netShellPlatingThickness", "corrosionAbrasionAddition", "frameWebThickness"]:
        if qty_number(g, h, term) is None:
            return False
    profile = obj_value(g, h, "frameProfileType")
    in_lieu = bool_value(g, h, "inLieuOfFrame")
    return profile in {NLTL.profileSection, NLTL.flatBarSection} and in_lieu is not None


add_case("TRF-051", "P01", "PASS", "Complete profile-section web-thickness readiness case.", build_051("TRF-051-P01", NLTL.profileSection, False))
add_case("TRF-051", "P02", "PASS", "Complete flat-bar web-thickness readiness case.", build_051("TRF-051-P02", NLTL.flatBarSection, False))
add_case("TRF-051", "P03", "PASS", "Complete in-lieu-of-frame plate-thickness readiness case.", build_051("TRF-051-P03", NLTL.profileSection, True))
for i, term in enumerate(["adjacentFrameHeight", "yieldStrength", "frameProfileType", "netShellPlatingThickness", "corrosionAbrasionAddition", "inLieuOfFrame", "frameWebThickness"], 1):
    add_case("TRF-051", f"F{i:02d}", "FAIL", f"Readiness term {term} is missing.", build_051(f"TRF-051-F{i:02d}", missing=term))
add_case("TRF-051", "F08", "FAIL", "Frame web thickness uses the wrong unit.", build_051("TRF-051-F08", wrong_unit="frameWebThickness"))


# ============================================================
# TRF-052 — ANTI-TRIPPING SUPPORT
# ============================================================

def build_052(cid, asym=False, angle=90.0, spacing=1300.0, span=4.0, ice="IA",
              regions=None, alternative=False, missing=None):
    g, ex, frame = new_graph(cid, "frame")
    if missing != "frameAsymmetrical": add_value(g, frame, "frameAsymmetrical", asym, ex)
    if missing != "frameWebAngleToShell": add_value(g, frame, "frameWebAngleToShell", angle, ex)
    if missing != "frameSpan": add_value(g, frame, "frameSpan", span, ex)
    if missing != "iceClass": add_value(g, frame, "iceClass", ICE_CLASSES[ice], ex)
    if missing != "equivalentSupportStatusByDirectCalculation": add_value(g, frame, "equivalentSupportStatusByDirectCalculation", alternative, ex)
    trigger = asym or angle < 90.0
    if trigger and not alternative and missing != "antitrippingSupportSpacing":
        add_value(g, frame, "antitrippingSupportSpacing", spacing, ex)
    if regions:
        for r in regions:
            add_value(g, frame, "hasAntitrippingSupportRegion", REGIONS[r], ex)
    return g


def required_regions_052(span, ice_uri):
    if span > 4.0:
        return {REGIONS["bow"], REGIONS["midbody"], REGIONS["stern"]}
    if ice_uri == ICE_CLASSES["IA Super"]:
        return {REGIONS["bow"], REGIONS["midbody"], REGIONS["stern"]}
    if ice_uri == ICE_CLASSES["IA"]:
        return {REGIONS["bow"], REGIONS["midbody"]}
    if ice_uri in {ICE_CLASSES["IB"], ICE_CLASSES["IC"]}:
        return {REGIONS["bow"]}
    return set()


def oracle_052(g):
    f = exactly_one_subject(g, NLTL.frame)
    if f is None:
        return False
    asym = bool_value(g, f, "frameAsymmetrical")
    angle = qty_number(g, f, "frameWebAngleToShell")
    span = qty_number(g, f, "frameSpan")
    ice = obj_value(g, f, "iceClass")
    alt = bool_value(g, f, "equivalentSupportStatusByDirectCalculation")
    if asym is None or angle is None or span is None or ice is None or alt is None:
        return False
    trigger = asym or angle < 90.0
    if not trigger:
        return True
    if alt:
        return True
    spacing = qty_number(g, f, "antitrippingSupportSpacing")
    if spacing is None or spacing > 1300.0:
        return False
    actual = set(g.objects(f, NLTL.hasAntitrippingSupportRegion))
    required = required_regions_052(span, ice)
    if not required:
        return False
    return required.issubset(actual)


all_regions = ["bow", "midbody", "stern"]
add_case("TRF-052", "P01", "PASS", "Asymmetrical frame with span >4 m has <=1300 mm support spacing in all regions.", build_052("TRF-052-P01", asym=True, span=5.0, ice="IC", regions=all_regions))
add_case("TRF-052", "P02", "PASS", "Web angle below 90 degrees triggers support; IA Super short frame is supported in all regions.", build_052("TRF-052-P02", angle=89.0, span=4.0, ice="IA Super", regions=all_regions))
add_case("TRF-052", "P03", "PASS", "IA short-frame scope covers bow and midbody.", build_052("TRF-052-P03", asym=True, span=4.0, ice="IA", regions=["bow", "midbody"]))
add_case("TRF-052", "P04", "PASS", "IB short-frame scope covers the bow region.", build_052("TRF-052-P04", asym=True, span=4.0, ice="IB", regions=["bow"]))
add_case("TRF-052", "P05", "PASS", "Neither asymmetry nor web angle triggers anti-tripping support; 90 degree boundary is non-triggering.", build_052("TRF-052-P05", asym=False, angle=90.0, span=4.0, ice="IA"))
add_case("TRF-052", "P06", "PASS", "Approved equivalent support demonstrated by direct calculation is accepted as the alternative route.", build_052("TRF-052-P06", asym=True, spacing=1600.0, span=5.0, ice="IA", regions=[], alternative=True))
add_case("TRF-052", "P07", "PASS", "Support spacing exactly at the 1300 mm maximum is compliant.", build_052("TRF-052-P07", asym=True, spacing=1300.0, span=4.0, ice="IB", regions=["bow"]))
add_case("TRF-052", "F01", "FAIL", "Triggered anti-tripping support spacing exceeds 1300 mm.", build_052("TRF-052-F01", asym=True, spacing=1300.1, span=4.0, ice="IB", regions=["bow"]))
add_case("TRF-052", "F02", "FAIL", "IA short frame omits required midbody anti-tripping support scope.", build_052("TRF-052-F02", asym=True, span=4.0, ice="IA", regions=["bow"]))
add_case("TRF-052", "F03", "FAIL", "IA Super short frame omits the required stern-region support scope.", build_052("TRF-052-F03", asym=True, span=4.0, ice="IA Super", regions=["bow", "midbody"]))
add_case("TRF-052", "F04", "FAIL", "Frame longer than 4 m is not supported in all regions.", build_052("TRF-052-F04", asym=True, span=4.01, ice="IC", regions=["bow"]))
add_case("TRF-052", "F05", "FAIL", "Triggered case is missing anti-tripping support spacing.", build_052("TRF-052-F05", asym=True, span=4.0, ice="IB", regions=["bow"], missing="antitrippingSupportSpacing"))


ORACLES = {
    "TRF-040": oracle_040,
    "TRF-041": oracle_041,
    "TRF-042": oracle_042,
    "TRF-043": oracle_043,
    "TRF-044": oracle_044,
    "TRF-045": oracle_045,
    "TRF-046": oracle_046,
    "TRF-047": oracle_047,
    "TRF-048": oracle_048,
    "TRF-049": oracle_049,
    "TRF-050": oracle_050,
    "TRF-051": oracle_051,
    "TRF-052": oracle_052,
}


# ============================================================
# VALIDATION
# ============================================================

def graph_vocab_ok(g):
    local = set()
    for s, p, o in g:
        for node in (s, p, o):
            text = str(node)
            if text.startswith(str(NLTL)) and "#" in text:
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
    manifest_path = ROOT / "manifests" / "traficom_batch_e_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_e_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch E manifest does not exist")
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

    lock_path = locks_root / "traficom_batch_e_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch E lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {
        "TRF-040": "4.3.1",
        "TRF-041": "4.3.2",
        "TRF-042": "4.3.2",
        "TRF-043": "4.4.1",
        "TRF-044": "4.4.2.1",
        "TRF-045": "4.4.2.1",
        "TRF-046": "4.4.2.2",
        "TRF-047": "4.4.2.3",
        "TRF-048": "4.4.3",
        "TRF-049": "4.4.4.1",
        "TRF-050": "4.4.4.2",
        "TRF-051": "4.4.4.2",
        "TRF-052": "4.4.4.2",
    }

    # Strong collision guard before writing anything.
    planned_paths = []
    for c in CASE_DEFS:
        req = c["requirement_id"]
        planned_paths.append(rdf_root / req / f"{c['case_id']}.ttl")
    planned_paths += [spec_root / f"{req}.json" for req in REQS]
    planned_paths += [
        manifest_root / "traficom_batch_e_manifest.jsonl",
        scripts_root / "validate_traficom_batch_e.py",
        ROOT / "README_TRAFICOM_BATCH_E.md",
    ]
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

    manifest_path = manifest_root / "traficom_batch_e_manifest.jsonl"
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
        "benchmark": "TRAFICOM Behavioral Benchmark Batch E",
        "source_lock_id": INDEX["sourceLockId"],
        "source_id": "SRC-TRAFICOM-2021",
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    validator_path = scripts_root / "validate_traficom_batch_e.py"
    shutil.copy2(Path(__file__).resolve(), validator_path)
    validator_path.chmod(0o755)

    counts = {req: sum(1 for x in CASE_DEFS if x["requirement_id"] == req) for req in REQS}
    (ROOT / "README_TRAFICOM_BATCH_E.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch E\n\n"
        f"Requirements: {len(REQS)}\n"
        f"Cases: {len(CASE_DEFS)}\n\n"
        + ", ".join(REQS) + "\n\n"
        "Scope: TRAFICOM 2021 sections 4.3.1 through 4.4.4.2 (shell plating and framing).\n\n"
        "Generated SHACL was not inspected during fixture construction.\n"
        "COMPLEX_READINESS cases test frozen R13 readiness/owner/unit semantics and do not execute advanced engineering formulae.\n\n"
        "Per-requirement cases: " + json.dumps(counts, sort_keys=True) + "\n\n"
        "Validate with:\n\npython3 scripts/validate_traficom_batch_e.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(check_hashes=True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = Path(__file__).name == "validate_traficom_batch_e.py" or "--validate-only" in sys.argv
    if validation_mode:
        ok = validate_existing(check_hashes=True)
        raise SystemExit(0 if ok else 1)
    generate()


if __name__ == "__main__":
    main()
