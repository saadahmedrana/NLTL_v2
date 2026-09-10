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
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-f/"

REQS = [
    "TRF-053", "TRF-054", "TRF-055", "TRF-056",
    "TRF-057", "TRF-058", "TRF-059", "TRF-060",
    "TRF-062", "TRF-063", "TRF-064", "TRF-066", "TRF-067",
]

EXPECTED_MODES = {
    "TRF-053": "DIRECT_CALCULATION",
    "TRF-054": "DIRECT_CALCULATION",
    "TRF-055": "DIRECT_STATIC",
    "TRF-056": "DIRECT_STATIC",
    "TRF-057": "DIRECT_CALCULATION",
    "TRF-058": "DIRECT_CALCULATION",
    "TRF-059": "DIRECT_CALCULATION",
    "TRF-060": "COMPLEX_READINESS",
    "TRF-062": "DIRECT_STATIC",
    "TRF-063": "DIRECT_STATIC",
    "TRF-064": "DIRECT_STATIC",
    "TRF-066": "DIRECT_STATIC",
    "TRF-067": "DIRECT_STATIC",
}

for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE", req
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req], req

assert CONTRACTS["TRF-060"].get("formulaExecutionRequired") is False

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

ALPHA_TABLE = {
    0.0: 1.50,
    0.2: 1.23,
    0.4: 1.16,
    0.6: 1.11,
    0.8: 1.09,
    1.0: 1.07,
    1.2: 1.06,
    1.4: 1.05,
    1.6: 1.05,
    1.8: 1.04,
    2.0: 1.04,
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


def obj_value(g, s, term):
    return one(g, s, NLTL[term])


def qty_number(g, s, term):
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
    expected = REG.get(term, {}).get("unitIri", "")
    if expected and str(units[0]) != expected:
        return None
    try:
        return float(nums[0])
    except Exception:
        return None


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
# TRF-053 — STRINGERS WITHIN ICE BELT (4.11 / 4.12)
# ============================================================

def calc_053(p, h, l, m, sy):
    line_mn_m = max(p * h, 0.15)
    z = 0.9 * 1.8 * line_mn_m * l * l / (m * sy) * 1e6
    a = math.sqrt(3) * 0.9 * 1.8 * 1.2 * line_mn_m * l / (2 * sy) * 1e4
    return line_mn_m * 1000.0, z, a


def build_053(cid, p=0.8, h=0.35, l=3.0, m=13.3, sy=235.0,
              mutate=None, missing=None, wrong_unit=None):
    g, ex, s = new_graph(cid, "iceStringer")
    expected = calc_053(p, h, l, m, sy)
    vals = {
        "icePressure": p,
        "designIceLoadHeight": h,
        "span": l,
        "frameMomentFactorM": m,
        "yieldStrength": sy,
        "designLineLoad": expected[0],
        "sectionModulus": expected[1],
        "requiredShearArea": expected[2],
    }
    if mutate == "designLineLoad": vals["designLineLoad"] *= 1.10
    if mutate == "sectionModulus": vals["sectionModulus"] *= 0.90
    if mutate == "requiredShearArea": vals["requiredShearArea"] *= 1.10
    for term, value in vals.items():
        if term != missing:
            add_value(g, s, term, value, ex, wrong_unit=(term == wrong_unit))
    return g


def oracle_053(g):
    s = exactly_one_subject(g, NLTL.iceStringer)
    if s is None: return False
    p = qty_number(g, s, "icePressure")
    h = qty_number(g, s, "designIceLoadHeight")
    l = qty_number(g, s, "span")
    m = qty_number(g, s, "frameMomentFactorM")
    sy = qty_number(g, s, "yieldStrength")
    line = qty_number(g, s, "designLineLoad")
    z = qty_number(g, s, "sectionModulus")
    a = qty_number(g, s, "requiredShearArea")
    if None in (p, h, l, m, sy, line, z, a) or m <= 0 or sy <= 0:
        return False
    e_line, e_z, e_a = calc_053(p, h, l, m, sy)
    return close(line, e_line) and close(z, e_z) and close(a, e_a)


add_case("TRF-053", "P01", "PASS", "Stringer within the ice belt satisfies formulas 4.11 and 4.12 above the 0.15 MN/m floor.", build_053("TRF-053-P01"))
add_case("TRF-053", "P02", "PASS", "The minimum design line load of 0.15 MN/m is correctly applied.", build_053("TRF-053-P02", p=0.2, h=0.35))
add_case("TRF-053", "P03", "PASS", "Exact p*h = 0.15 MN/m boundary is accepted.", build_053("TRF-053-P03", p=0.5, h=0.3))
add_case("TRF-053", "F01", "FAIL", "designLineLoad does not equal max(p*h,0.15).", build_053("TRF-053-F01", mutate="designLineLoad"))
add_case("TRF-053", "F02", "FAIL", "Section modulus is inconsistent with formula 4.11.", build_053("TRF-053-F02", mutate="sectionModulus"))
add_case("TRF-053", "F03", "FAIL", "Required shear area is inconsistent with formula 4.12.", build_053("TRF-053-F03", mutate="requiredShearArea"))
add_case("TRF-053", "F04", "FAIL", "Required span operand is missing.", build_053("TRF-053-F04", missing="span"))
add_case("TRF-053", "F05", "FAIL", "designLineLoad carries the wrong unit.", build_053("TRF-053-F05", wrong_unit="designLineLoad"))


# ============================================================
# TRF-054 — STRINGERS OUTSIDE ICE BELT (4.13 / 4.14)
# ============================================================

def calc_054(p, h, l, m, sy, hs, ls):
    line_mn_m = max(p * h, 0.15)
    factor = 1.0 - hs / ls
    z = 0.80 * 1.8 * line_mn_m * l * l / (m * sy) * factor * 1e6
    a = math.sqrt(3) * 0.80 * 1.8 * 1.2 * line_mn_m * l / (2 * sy) * factor * 1e4
    return line_mn_m * 1000.0, factor, z, a


def build_054(cid, p=0.8, h=0.35, l=3.0, m=13.3, sy=235.0, hs=0.5, ls=2.0,
              mutate=None, missing=None, wrong_unit=None):
    g, ex, s = new_graph(cid, "iceStringer")
    e = calc_054(p, h, l, m, sy, hs, ls)
    vals = {
        "icePressure": p,
        "designIceLoadHeight": h,
        "span": l,
        "frameMomentFactorM": m,
        "yieldStrength": sy,
        "distanceToIceBelt": hs,
        "stringerSpan": ls,
        "designLineLoad": e[0],
        "outsideIceBeltFactor": e[1],
        "sectionModulus": e[2],
        "requiredShearArea": e[3],
    }
    if mutate in vals: vals[mutate] *= 1.10
    for term, value in vals.items():
        if term != missing:
            add_value(g, s, term, value, ex, wrong_unit=(term == wrong_unit))
    return g


def oracle_054(g):
    s = exactly_one_subject(g, NLTL.iceStringer)
    if s is None: return False
    names = ["icePressure", "designIceLoadHeight", "span", "frameMomentFactorM", "yieldStrength", "distanceToIceBelt", "stringerSpan", "designLineLoad", "outsideIceBeltFactor", "sectionModulus", "requiredShearArea"]
    v = {t: qty_number(g, s, t) for t in names}
    if any(v[t] is None for t in names) or v["frameMomentFactorM"] <= 0 or v["yieldStrength"] <= 0 or v["stringerSpan"] <= 0:
        return False
    e = calc_054(v["icePressure"], v["designIceLoadHeight"], v["span"], v["frameMomentFactorM"], v["yieldStrength"], v["distanceToIceBelt"], v["stringerSpan"])
    return close(v["designLineLoad"], e[0]) and close(v["outsideIceBeltFactor"], e[1]) and close(v["sectionModulus"], e[2]) and close(v["requiredShearArea"], e[3])


add_case("TRF-054", "P01", "PASS", "Outside-ice-belt stringer satisfies formulas 4.13 and 4.14.", build_054("TRF-054-P01"))
add_case("TRF-054", "P02", "PASS", "Minimum line-load floor is correctly applied outside the ice belt.", build_054("TRF-054-P02", p=0.2, h=0.35))
add_case("TRF-054", "P03", "PASS", "Zero distance to the ice belt gives an outside-ice-belt factor of one.", build_054("TRF-054-P03", hs=0.0, ls=2.0))
add_case("TRF-054", "F01", "FAIL", "Outside-ice-belt factor is inconsistent with 1-hs/ls.", build_054("TRF-054-F01", mutate="outsideIceBeltFactor"))
add_case("TRF-054", "F02", "FAIL", "Section modulus is inconsistent with formula 4.13.", build_054("TRF-054-F02", mutate="sectionModulus"))
add_case("TRF-054", "F03", "FAIL", "Required shear area is inconsistent with formula 4.14.", build_054("TRF-054-F03", mutate="requiredShearArea"))
add_case("TRF-054", "F04", "FAIL", "Adjacent-stringer distance operand is missing.", build_054("TRF-054-F04", missing="stringerSpan"))
add_case("TRF-054", "F05", "FAIL", "outsideIceBeltFactor carries the wrong unit.", build_054("TRF-054-F05", wrong_unit="outsideIceBeltFactor"))


# ============================================================
# TRF-055 — NARROW DECK STRIPS / VERY-LONG-HATCH EXCEPTION
# ============================================================

def build_055(cid, abreast=True, serves=True, very_long=False,
              actual_z=1200.0, required_z=1000.0, actual_a=150.0, required_a=120.0,
              reduced=None, approved=None, missing=None):
    g, ex, s = new_graph(cid, "narrowDeckStrip")
    vals = {
        "abreastOfHatch": abreast,
        "servesAsIceStringer": serves,
        "veryLongHatchOpening": very_long,
        "actualSectionModulus": actual_z,
        "requiredSectionModulus": required_z,
        "actualShearArea": actual_a,
        "requiredShearArea": required_a,
    }
    if reduced is not None: vals["permittedReducedLineLoad"] = reduced
    if approved is not None: vals["reducedLineLoadApprovedByClassificationSociety"] = approved
    for term, value in vals.items():
        if term != missing:
            add_value(g, s, term, value, ex)
    return g


def oracle_055(g):
    s = exactly_one_subject(g, NLTL.narrowDeckStrip)
    if s is None: return False
    abreast = bool_value(g, s, "abreastOfHatch")
    serves = bool_value(g, s, "servesAsIceStringer")
    if abreast is None or serves is None: return False
    if not (abreast and serves):
        return True
    very_long = bool_value(g, s, "veryLongHatchOpening")
    if very_long is None: return False
    az = qty_number(g, s, "actualSectionModulus")
    rz = qty_number(g, s, "requiredSectionModulus")
    aa = qty_number(g, s, "actualShearArea")
    ra = qty_number(g, s, "requiredShearArea")
    if None in (az, rz, aa, ra) or az < rz or aa < ra:
        return False
    reduced = qty_number(g, s, "permittedReducedLineLoad")
    approved = bool_value(g, s, "reducedLineLoadApprovedByClassificationSociety")
    if reduced is not None or approved is not None:
        if not very_long or reduced is None or approved is not True:
            return False
        # Registry unit is kN/m: 0.10 <= p*h < 0.15 MN/m becomes 100 <= value < 150 kN/m.
        if not (100.0 <= reduced < 150.0):
            return False
    return True


add_case("TRF-055", "P01", "PASS", "Applicable narrow deck strip meets section-modulus and shear-area requirements without using the exception.", build_055("TRF-055-P01"))
add_case("TRF-055", "P02", "PASS", "Very-long-hatch exception is approved at the 0.10 MN/m lower boundary.", build_055("TRF-055-P02", very_long=True, reduced=100.0, approved=True))
add_case("TRF-055", "P03", "PASS", "Approved reduced line load below 0.15 MN/m and above the lower bound is accepted.", build_055("TRF-055-P03", very_long=True, reduced=149.0, approved=True))
add_case("TRF-055", "P04", "PASS", "A deck strip not abreast of a hatch is outside this requirement's applicability.", build_055("TRF-055-P04", abreast=False, serves=True))
add_case("TRF-055", "F01", "FAIL", "Actual section modulus is below the required section modulus.", build_055("TRF-055-F01", actual_z=999.0))
add_case("TRF-055", "F02", "FAIL", "Actual shear area is below the required shear area.", build_055("TRF-055-F02", actual_a=119.0))
add_case("TRF-055", "F03", "FAIL", "Reduced line load is below the source minimum of 0.10 MN/m.", build_055("TRF-055-F03", very_long=True, reduced=99.0, approved=True))
add_case("TRF-055", "F04", "FAIL", "Reduced line load is used without classification-society approval.", build_055("TRF-055-F04", very_long=True, reduced=120.0, approved=False))
add_case("TRF-055", "F05", "FAIL", "Applicable deck strip is missing the veryLongHatchOpening applicability state.", build_055("TRF-055-F05", missing="veryLongHatchOpening"))


# ============================================================
# TRF-056 — WEATHERDECK HATCH SIDE-DEFLECTION EVIDENCE
# ============================================================

def build_056(cid, breadth=20.0, hatch_len=12.0, deflection=0.02,
              cover=True, fitting=True, omit_relation=False, missing=None, wrong_owner=False):
    g, ex, ship = new_graph(cid)
    hatch = ex.hatch
    g.add((hatch, RDF.type, NLTL.weatherdeckHatch))
    if not omit_relation:
        add_value(g, ship, "hasWeatherdeckHatch", hatch, ex)
    if missing != "shipBreadth": add_value(g, ship, "shipBreadth", breadth, ex)
    if missing != "hatchOpeningLength": add_value(g, hatch, "hatchOpeningLength", hatch_len, ex)
    if deflection is not None and missing != "shipSideDeflection":
        add_value(g, ship if wrong_owner else hatch, "shipSideDeflection", deflection, ex)
    if cover and missing != "hasHatchCoverDesignEvidence":
        ev = ex.coverEvidence
        g.add((ev, RDF.type, NLTL.hatchCoverDesignEvidence))
        add_value(g, hatch, "hasHatchCoverDesignEvidence", ev, ex)
    if fitting and missing != "hasHatchFittingDesignEvidence":
        ev = ex.fittingEvidence
        g.add((ev, RDF.type, NLTL.hatchFittingDesignEvidence))
        add_value(g, hatch, "hasHatchFittingDesignEvidence", ev, ex)
    return g


def oracle_056(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    hatch = obj_value(g, ship, "hasWeatherdeckHatch")
    if hatch is None or not typed_as(g, hatch, NLTL.weatherdeckHatch): return False
    b = qty_number(g, ship, "shipBreadth")
    hl = qty_number(g, hatch, "hatchOpeningLength")
    if b is None or hl is None: return False
    if hl <= b / 2.0:
        return True
    if qty_number(g, hatch, "shipSideDeflection") is None:
        return False
    ce = obj_value(g, hatch, "hasHatchCoverDesignEvidence")
    fe = obj_value(g, hatch, "hasHatchFittingDesignEvidence")
    return typed_as(g, ce, NLTL.hatchCoverDesignEvidence) and typed_as(g, fe, NLTL.hatchFittingDesignEvidence)


add_case("TRF-056", "P01", "PASS", "Weatherdeck hatch longer than B/2 includes side-deflection representation and both evidence paths.", build_056("TRF-056-P01"))
add_case("TRF-056", "P02", "PASS", "Hatch opening exactly B/2 does not trigger the greater-than-B/2 obligation.", build_056("TRF-056-P02", breadth=20.0, hatch_len=10.0, deflection=None, cover=False, fitting=False))
add_case("TRF-056", "P03", "PASS", "Shorter hatch opening is non-applicable to the very-long-hatch evidence obligation.", build_056("TRF-056-P03", breadth=20.0, hatch_len=9.0, deflection=None, cover=False, fitting=False))
add_case("TRF-056", "F01", "FAIL", "Applicable long hatch is missing ship-side deflection representation.", build_056("TRF-056-F01", deflection=None))
add_case("TRF-056", "F02", "FAIL", "Applicable long hatch is missing hatch-cover design evidence.", build_056("TRF-056-F02", cover=False))
add_case("TRF-056", "F03", "FAIL", "Applicable long hatch is missing hatch-fitting design evidence.", build_056("TRF-056-F03", fitting=False))
add_case("TRF-056", "F04", "FAIL", "Side-deflection quantity is attached to the ship rather than the applicable hatch.", build_056("TRF-056-F04", wrong_owner=True))
add_case("TRF-056", "F05", "FAIL", "Weatherdeck-hatch node exists but the ship-to-hatch path is missing.", build_056("TRF-056-F05", omit_relation=True))


# ============================================================
# TRF-057 — WEB-FRAME ICE LOAD (4.15)
# ============================================================

def calc_057(p, h, spacing):
    return 1.8 * max(p * h, 0.15) * spacing * 1000.0  # kN


def build_057(cid, p=0.8, h=0.35, spacing=2.0, mutate=False, missing=None, wrong_unit=None):
    g, ex, w = new_graph(cid, "webFrame")
    vals = {
        "icePressure": p,
        "iceLoadHeight": h,
        "webFrameSpacing": spacing,
        "webFrameIceLoad": calc_057(p, h, spacing),
    }
    if mutate: vals["webFrameIceLoad"] *= 1.10
    for t, v in vals.items():
        if t != missing: add_value(g, w, t, v, ex, wrong_unit=(t == wrong_unit))
    return g


def oracle_057(g):
    w = exactly_one_subject(g, NLTL.webFrame)
    if w is None: return False
    p = qty_number(g, w, "icePressure")
    h = qty_number(g, w, "iceLoadHeight")
    s = qty_number(g, w, "webFrameSpacing")
    f = qty_number(g, w, "webFrameIceLoad")
    return None not in (p, h, s, f) and close(f, calc_057(p, h, s))


add_case("TRF-057", "P01", "PASS", "Web-frame ice load follows formula 4.15 above the line-load floor.", build_057("TRF-057-P01"))
add_case("TRF-057", "P02", "PASS", "Formula 4.15 correctly applies the 0.15 MN/m minimum line load.", build_057("TRF-057-P02", p=0.2, h=0.35))
add_case("TRF-057", "P03", "PASS", "Exact p*h = 0.15 MN/m boundary is accepted.", build_057("TRF-057-P03", p=0.5, h=0.3))
add_case("TRF-057", "F01", "FAIL", "webFrameIceLoad is inconsistent with formula 4.15.", build_057("TRF-057-F01", mutate=True))
add_case("TRF-057", "F02", "FAIL", "Required ice-pressure operand is missing.", build_057("TRF-057-F02", missing="icePressure"))
add_case("TRF-057", "F03", "FAIL", "Required web-frame spacing is missing.", build_057("TRF-057-F03", missing="webFrameSpacing"))
add_case("TRF-057", "F04", "FAIL", "webFrameIceLoad carries the wrong unit.", build_057("TRF-057-F04", wrong_unit="webFrameIceLoad"))


# ============================================================
# TRF-058 — OUTSIDE-ICE-BELT FORCE REDUCTION
# ============================================================

def build_058(cid, force=500.0, hs=0.5, ls=2.0, mutate=False, missing=None, wrong_unit=None):
    g, ex, w = new_graph(cid, "webFrame")
    adjusted = force * (1.0 - hs / ls)
    vals = {
        "iceLoadForce": force,
        "stringerOutsideIceBeltHeight": hs,
        "stringerSpan": ls,
        "adjustedIceLoadForce": adjusted,
    }
    if mutate: vals["adjustedIceLoadForce"] *= 1.10
    for t, v in vals.items():
        if t != missing: add_value(g, w, t, v, ex, wrong_unit=(t == wrong_unit))
    return g


def oracle_058(g):
    w = exactly_one_subject(g, NLTL.webFrame)
    if w is None: return False
    f = qty_number(g, w, "iceLoadForce")
    hs = qty_number(g, w, "stringerOutsideIceBeltHeight")
    ls = qty_number(g, w, "stringerSpan")
    a = qty_number(g, w, "adjustedIceLoadForce")
    return None not in (f, hs, ls, a) and ls > 0 and close(a, f * (1.0 - hs / ls))


add_case("TRF-058", "P01", "PASS", "Force is correctly reduced by 1-hs/ls for a supported stringer outside the ice belt.", build_058("TRF-058-P01"))
add_case("TRF-058", "P02", "PASS", "At hs=0 the adjustment factor is one and the force is unchanged.", build_058("TRF-058-P02", hs=0.0))
add_case("TRF-058", "F01", "FAIL", "Adjusted force does not equal F*(1-hs/ls).", build_058("TRF-058-F01", mutate=True))
add_case("TRF-058", "F02", "FAIL", "Distance from the stringer to the ice belt is missing.", build_058("TRF-058-F02", missing="stringerOutsideIceBeltHeight"))
add_case("TRF-058", "F03", "FAIL", "Adjusted ice-load result is missing.", build_058("TRF-058-F03", missing="adjustedIceLoadForce"))
add_case("TRF-058", "F04", "FAIL", "Adjusted ice-load force carries the wrong unit.", build_058("TRF-058-F04", wrong_unit="adjustedIceLoadForce"))


# ============================================================
# TRF-059 — WEB-FRAME REQUIRED SHEAR AREA / TABLE 4-8 ALPHA
# ============================================================

def calc_059(q_kn, alpha, sy):
    q_mn = q_kn / 1000.0
    return math.sqrt(3) * alpha * 1.1 * q_mn / sy * 1e4


def build_059(cid, ratio=1.0, q=500.0, sy=235.0, alpha=None,
              mutate_area=False, missing=None, wrong_unit=None):
    g, ex, w = new_graph(cid, "webFrame")
    if alpha is None:
        alpha = ALPHA_TABLE.get(ratio, 1.07)
    vals = {
        "maximumCalculatedShearForce": q,
        "webFrameShearFactorAlpha": alpha,
        "yieldStrength": sy,
        "freeFlangeToWebAreaRatio": ratio,
        "requiredShearArea": calc_059(q, alpha, sy),
    }
    if mutate_area: vals["requiredShearArea"] *= 1.10
    for t, v in vals.items():
        if t != missing: add_value(g, w, t, v, ex, wrong_unit=(t == wrong_unit))
    return g


def oracle_059(g):
    w = exactly_one_subject(g, NLTL.webFrame)
    if w is None: return False
    ratio = qty_number(g, w, "freeFlangeToWebAreaRatio")
    alpha = qty_number(g, w, "webFrameShearFactorAlpha")
    q = qty_number(g, w, "maximumCalculatedShearForce")
    sy = qty_number(g, w, "yieldStrength")
    area = qty_number(g, w, "requiredShearArea")
    if None in (ratio, alpha, q, sy, area) or sy <= 0:
        return False
    key = next((k for k in ALPHA_TABLE if close(ratio, k)), None)
    if key is None or not close(alpha, ALPHA_TABLE[key]):
        return False
    return close(area, calc_059(q, alpha, sy))


for suf, ratio in [("P01", 0.0), ("P02", 0.2), ("P03", 1.0), ("P04", 2.0)]:
    add_case("TRF-059", suf, "PASS", f"Table 4-8 alpha is selected correctly for Af/Aw={ratio} and formula 4.16 is satisfied.", build_059(f"TRF-059-{suf}", ratio=ratio))
add_case("TRF-059", "F01", "FAIL", "Alpha does not match the Table 4-8 value for the given Af/Aw ratio.", build_059("TRF-059-F01", ratio=1.0, alpha=1.23))
add_case("TRF-059", "F02", "FAIL", "Required shear area is inconsistent with formula 4.16.", build_059("TRF-059-F02", mutate_area=True))
add_case("TRF-059", "F03", "FAIL", "Af/Aw ratio is not one of the frozen Table 4-8 selector values.", build_059("TRF-059-F03", ratio=0.3, alpha=1.20))
add_case("TRF-059", "F04", "FAIL", "Af/Aw ratio operand is missing.", build_059("TRF-059-F04", missing="freeFlangeToWebAreaRatio"))
add_case("TRF-059", "F05", "FAIL", "Yield-strength operand is missing.", build_059("TRF-059-F05", missing="yieldStrength"))
add_case("TRF-059", "F06", "FAIL", "Required shear area carries the wrong unit.", build_059("TRF-059-F06", wrong_unit="requiredShearArea"))


# ============================================================
# TRF-060 — WEB-FRAME SECTION-MODULUS READINESS / TABLE 4-8
# ============================================================

def build_060(cid, missing=None, wrong_table=False, gamma_on_ship=False, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    lookup = ex.lookup
    evidence = ex.lookupEvidence
    g.add((lookup, RDF.type, NLTL.tableLookupCase))
    g.add((evidence, RDF.type, NLTL.evidenceArtifact))
    add_value(g, ship, "hasTableLookupCase", lookup, ex)
    if missing != "lookupSelectionEvidence":
        add_value(g, lookup, "lookupSelectionEvidence", evidence, ex)
    if missing != "tableReference":
        add_value(g, lookup, "tableReference", NLTL.iacsUrI2Table8 if wrong_table else NLTL.traficomTable4Dash8, ex)

    ship_vals = {
        "actualWebFrameCrossSectionalArea": 300.0,
        "requiredShearArea": 120.0,
        "sectionModulus": 1000.0,
        "shearArea": 0.020,
        "webFrameFreeFlangeArea": 100.0,
        "webFrameIceLoad": 500.0,
        "webFrameMaximumIceLoadBendingMoment": 0.500,
        "webFrameSpan": 5.0,
        "webFrameWebArea": 200.0,
        "yieldStrength": 235.0,
    }
    for t, v in ship_vals.items():
        if t != missing:
            add_value(g, ship, t, v, ex, wrong_unit=(t == wrong_unit))
    if missing != "webFrameTable4Dash8GammaFactor":
        add_value(g, ship if gamma_on_ship else lookup, "webFrameTable4Dash8GammaFactor", 0.80, ex, wrong_unit=(wrong_unit == "webFrameTable4Dash8GammaFactor"))
    return g


def oracle_060(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    lookup = obj_value(g, ship, "hasTableLookupCase")
    if lookup is None or not typed_as(g, lookup, NLTL.tableLookupCase): return False
    ev = obj_value(g, lookup, "lookupSelectionEvidence")
    if ev is None or not typed_as(g, ev, NLTL.evidenceArtifact): return False
    if obj_value(g, lookup, "tableReference") != NLTL.traficomTable4Dash8:
        return False
    for t in ["actualWebFrameCrossSectionalArea", "requiredShearArea", "sectionModulus", "shearArea", "webFrameFreeFlangeArea", "webFrameIceLoad", "webFrameMaximumIceLoadBendingMoment", "webFrameSpan", "webFrameWebArea", "yieldStrength"]:
        if qty_number(g, ship, t) is None:
            return False
    return qty_number(g, lookup, "webFrameTable4Dash8GammaFactor") is not None


add_case("TRF-060", "P01", "PASS", "Complete Table 4-8 readiness graph has all required operands, result/interface quantities and lookup-evidence path.", build_060("TRF-060-P01"))
add_case("TRF-060", "P02", "PASS", "A second complete readiness graph preserves the frozen Table 4-8 interface.", build_060("TRF-060-P02"))
add_case("TRF-060", "F01", "FAIL", "Required web-frame ice-load operand is missing.", build_060("TRF-060-F01", missing="webFrameIceLoad"))
add_case("TRF-060", "F02", "FAIL", "Required maximum bending-moment result/interface quantity is missing.", build_060("TRF-060-F02", missing="webFrameMaximumIceLoadBendingMoment"))
add_case("TRF-060", "F03", "FAIL", "Table 4-8 gamma factor is missing.", build_060("TRF-060-F03", missing="webFrameTable4Dash8GammaFactor"))
add_case("TRF-060", "F04", "FAIL", "Lookup-selection evidence path is missing.", build_060("TRF-060-F04", missing="lookupSelectionEvidence"))
add_case("TRF-060", "F05", "FAIL", "The readiness graph points to the wrong controlled table reference.", build_060("TRF-060-F05", wrong_table=True))
add_case("TRF-060", "F06", "FAIL", "Gamma factor is attached to the ship rather than the Table 4-8 lookup case.", build_060("TRF-060-F06", gamma_on_ship=True))

# Two additional path/unit failures to reach the planned eight cases.
add_case("TRF-060", "F07", "FAIL", "Table-reference relationship is missing.", build_060("TRF-060-F07", missing="tableReference"))
add_case("TRF-060", "F08", "FAIL", "A required readiness quantity carries the wrong unit.", build_060("TRF-060-F08", wrong_unit="webFrameSpan"))


# ============================================================
# TRF-062 — PROPELLER BLADE-TIP / HULL CLEARANCE
# ============================================================

def build_062(cid, minimum=0.35, clearance=0.35, missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    # Contextual stern-frame node reflects the source's 'hull (including stern frame)' wording.
    sf = ex.sternFrame
    g.add((sf, RDF.type, NLTL.sternFrame))
    if missing != "minimumClearance": add_value(g, ship, "minimumClearance", minimum, ex, wrong_unit=(wrong_unit == "minimumClearance"))
    if missing != "propellerBladeTipHullClearance": add_value(g, ship, "propellerBladeTipHullClearance", clearance, ex, wrong_unit=(wrong_unit == "propellerBladeTipHullClearance"))
    return g


def oracle_062(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    minimum = qty_number(g, ship, "minimumClearance")
    actual = qty_number(g, ship, "propellerBladeTipHullClearance")
    return minimum is not None and actual is not None and actual >= minimum


add_case("TRF-062", "P01", "PASS", "Propeller blade-tip clearance exactly equals the required minimum h0.", build_062("TRF-062-P01"))
add_case("TRF-062", "P02", "PASS", "Propeller blade-tip clearance exceeds h0.", build_062("TRF-062-P02", clearance=0.50))
add_case("TRF-062", "F01", "FAIL", "Propeller blade-tip clearance is below h0.", build_062("TRF-062-F01", clearance=0.34))
add_case("TRF-062", "F02", "FAIL", "Actual blade-tip/hull clearance is missing.", build_062("TRF-062-F02", missing="propellerBladeTipHullClearance"))
add_case("TRF-062", "F03", "FAIL", "Minimum-clearance threshold is missing.", build_062("TRF-062-F03", missing="minimumClearance"))
add_case("TRF-062", "F04", "FAIL", "Actual clearance carries the wrong unit.", build_062("TRF-062-F04", wrong_unit="propellerBladeTipHullClearance"))


# ============================================================
# TRF-063 — SIDE-PROPELLER STRENGTHENING ENVELOPE
# ============================================================

def build_063(cid, fwd=1.5, aft=1.5, boundary="tankTop", missing=None, wrong_unit=None, omit_relation=False):
    g, ex, ship = new_graph(cid)
    env = ex.envelope
    g.add((env, RDF.type, NLTL.sidePropellerStrengtheningEnvelope))
    if not omit_relation:
        add_value(g, ship, "hasSidePropellerStrengtheningEnvelope", env, ex)
    if missing != "strengtheningForwardExtent": add_value(g, env, "strengtheningForwardExtent", fwd, ex, wrong_unit=(wrong_unit == "strengtheningForwardExtent"))
    if missing != "strengtheningAftExtent": add_value(g, env, "strengtheningAftExtent", aft, ex, wrong_unit=(wrong_unit == "strengtheningAftExtent"))
    if missing != "strengtheningEnvelopeBoundary":
        b = ex.boundary
        g.add((b, RDF.type, NLTL.tankTop if boundary == "tankTop" else NLTL.sternFrame))
        add_value(g, env, "strengtheningEnvelopeBoundary", b, ex)
    return g


def oracle_063(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    env = obj_value(g, ship, "hasSidePropellerStrengtheningEnvelope")
    if env is None or not typed_as(g, env, NLTL.sidePropellerStrengtheningEnvelope): return False
    fwd = qty_number(g, env, "strengtheningForwardExtent")
    aft = qty_number(g, env, "strengtheningAftExtent")
    boundary = obj_value(g, env, "strengtheningEnvelopeBoundary")
    return fwd is not None and aft is not None and fwd >= 1.5 and aft >= 1.5 and typed_as(g, boundary, NLTL.tankTop)


add_case("TRF-063", "P01", "PASS", "Side-propeller strengthening reaches the tank top and exactly 1.5 m forward and aft.", build_063("TRF-063-P01"))
add_case("TRF-063", "P02", "PASS", "Strengthening extents greater than 1.5 m satisfy the requirement.", build_063("TRF-063-P02", fwd=2.0, aft=1.8))
add_case("TRF-063", "F01", "FAIL", "Forward strengthening extent is below 1.5 m.", build_063("TRF-063-F01", fwd=1.49))
add_case("TRF-063", "F02", "FAIL", "Aft strengthening extent is below 1.5 m.", build_063("TRF-063-F02", aft=1.49))
add_case("TRF-063", "F03", "FAIL", "Strengthening-envelope boundary is missing.", build_063("TRF-063-F03", missing="strengtheningEnvelopeBoundary"))
add_case("TRF-063", "F04", "FAIL", "Strengthening envelope terminates at the wrong hull-structure class rather than the tank top.", build_063("TRF-063-F04", boundary="sternFrame"))
add_case("TRF-063", "F05", "FAIL", "Envelope node exists but ship-to-envelope relationship is missing.", build_063("TRF-063-F05", omit_relation=True))
add_case("TRF-063", "F06", "FAIL", "Forward strengthening extent carries the wrong unit.", build_063("TRF-063-F06", wrong_unit="strengtheningForwardExtent"))


# ============================================================
# TRF-064 — SIDE-PROPELLER SHAFTING / BOSSINGS / STRUT EVIDENCE
# ============================================================

def build_064(cid, side=True, tube=True, boss_side=True, boss_tube=True, strut=False,
              strut_design=True, strut_strength=True, strut_attachment=True,
              wrong_evidence_owner=False):
    g, ex, ship = new_graph(cid)
    if side:
        shaft = ex.shafting
        g.add((shaft, RDF.type, NLTL.sidePropellerShaftingAssembly))
        add_value(g, ship, "hasSidePropellerShafting", shaft, ex)
        if boss_side:
            boss = ex.shaftBossing
            g.add((boss, RDF.type, NLTL.platedBossingStructure))
            add_value(g, shaft, "enclosedByPlatedBossing", boss, ex)
    if tube:
        st = ex.sternTube
        g.add((st, RDF.type, NLTL.sternTube))
        add_value(g, ship, "hasSternTube", st, ex)
        if boss_tube:
            boss = ex.tubeBossing
            g.add((boss, RDF.type, NLTL.platedBossingStructure))
            add_value(g, st, "enclosedByPlatedBossing", boss, ex)
    if strut:
        ds = ex.detachedStrut
        g.add((ds, RDF.type, NLTL.detachedStrutStructure))
        add_value(g, ship, "hasDetachedStrut", ds, ex)
        target = ship if wrong_evidence_owner else ds
        if strut_design:
            ev = ex.designEvidence; g.add((ev, RDF.type, NLTL.strutDesignEvidence)); add_value(g, target, "hasStrutDesignEvidence", ev, ex)
        if strut_strength:
            ev = ex.strengthEvidence; g.add((ev, RDF.type, NLTL.strutStrengthEvidence)); add_value(g, target, "hasStrutStrengthEvidence", ev, ex)
        if strut_attachment:
            ev = ex.attachmentEvidence; g.add((ev, RDF.type, NLTL.strutHullAttachmentEvidence)); add_value(g, target, "hasStrutHullAttachmentEvidence", ev, ex)
    return g


def oracle_064(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    shafts = list(g.objects(ship, NLTL.hasSidePropellerShafting))
    tubes = list(g.objects(ship, NLTL.hasSternTube))
    struts = list(g.objects(ship, NLTL.hasDetachedStrut))
    if not shafts and not tubes and not struts:
        return True
    for comp, cls in [(x, NLTL.sidePropellerShaftingAssembly) for x in shafts] + [(x, NLTL.sternTube) for x in tubes]:
        if not typed_as(g, comp, cls): return False
        boss = obj_value(g, comp, "enclosedByPlatedBossing")
        if boss is None or not typed_as(g, boss, NLTL.platedBossingStructure): return False
    for ds in struts:
        if not typed_as(g, ds, NLTL.detachedStrutStructure): return False
        de = obj_value(g, ds, "hasStrutDesignEvidence")
        se = obj_value(g, ds, "hasStrutStrengthEvidence")
        ae = obj_value(g, ds, "hasStrutHullAttachmentEvidence")
        if not typed_as(g, de, NLTL.strutDesignEvidence): return False
        if not typed_as(g, se, NLTL.strutStrengthEvidence): return False
        if not typed_as(g, ae, NLTL.strutHullAttachmentEvidence): return False
    return True


add_case("TRF-064", "P01", "PASS", "Side-propeller shafting and stern tube are each enclosed by typed plated bossings.", build_064("TRF-064-P01"))
add_case("TRF-064", "P02", "PASS", "Detached strut has design, strength and hull-attachment evidence in addition to bossed shafting/tube.", build_064("TRF-064-P02", strut=True))
add_case("TRF-064", "P03", "PASS", "Ship without side-propeller shafting, stern tube or detached strut is non-applicable.", build_064("TRF-064-P03", side=False, tube=False))
add_case("TRF-064", "F01", "FAIL", "Side-propeller shafting lacks its plated-bossing enclosure.", build_064("TRF-064-F01", boss_side=False))
add_case("TRF-064", "F02", "FAIL", "Stern tube lacks its plated-bossing enclosure.", build_064("TRF-064-F02", boss_tube=False))
add_case("TRF-064", "F03", "FAIL", "Detached strut lacks design evidence.", build_064("TRF-064-F03", strut=True, strut_design=False))
add_case("TRF-064", "F04", "FAIL", "Detached strut lacks strength evidence.", build_064("TRF-064-F04", strut=True, strut_strength=False))
add_case("TRF-064", "F05", "FAIL", "Detached strut lacks hull-attachment evidence.", build_064("TRF-064-F05", strut=True, strut_attachment=False))
add_case("TRF-064", "F06", "FAIL", "Strut evidence is attached to the ship rather than the detached-strut structure.", build_064("TRF-064-F06", strut=True, wrong_evidence_owner=True))


# ============================================================
# TRF-066 — IA / IA SUPER RUDDER ICE PROTECTION
# ============================================================

def build_066(cid, ice="IA", practicable=True, arrangement="iceKnife", extends=True, omit_arrangement=False, omit_practicable=False):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice], ex)
    if not omit_practicable:
        add_value(g, ship, "iceKnifePracticable", practicable, ex)
    if not omit_arrangement:
        arr = ex.arrangement
        if arrangement == "iceKnife":
            g.add((arr, RDF.type, NLTL.iceKnife))
            add_value(g, arr, "extendsBelowLowerIceWaterline", extends, ex)
        elif arrangement == "equivalent":
            g.add((arr, RDF.type, NLTL.equivalentRudderProtectionMeans))
        else:
            g.add((arr, RDF.type, NLTL.rudderProtectionArrangement))
        add_value(g, ship, "hasRudderProtectionArrangement", arr, ex)
    return g


def oracle_066(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    ice = obj_value(g, ship, "iceClass")
    if ice not in (NLTL.iceClassIa, NLTL.iceClassIaSuper):
        return True
    practicable = bool_value(g, ship, "iceKnifePracticable")
    if practicable is None: return False
    arr = obj_value(g, ship, "hasRudderProtectionArrangement")
    if arr is None: return False
    if typed_as(g, arr, NLTL.equivalentRudderProtectionMeans):
        return True
    if typed_as(g, arr, NLTL.iceKnife):
        return bool_value(g, arr, "extendsBelowLowerIceWaterline") is True
    return False


add_case("TRF-066", "P01", "PASS", "IA ship with practicable ice knife has a knife extending below the LIWL.", build_066("TRF-066-P01", ice="IA", practicable=True, arrangement="iceKnife", extends=True))
add_case("TRF-066", "P02", "PASS", "IA Super ship uses an equivalent rudder-protection means when the ice knife is not practicable.", build_066("TRF-066-P02", ice="IA Super", practicable=False, arrangement="equivalent"))
add_case("TRF-066", "P03", "PASS", "IB ship is outside the IA/IA Super conditional obligation.", build_066("TRF-066-P03", ice="IB", omit_arrangement=True))
add_case("TRF-066", "F01", "FAIL", "Applicable IA ship has no rudder-protection arrangement.", build_066("TRF-066-F01", ice="IA", omit_arrangement=True))
add_case("TRF-066", "F02", "FAIL", "Ice knife does not extend below the LIWL.", build_066("TRF-066-F02", ice="IA", arrangement="iceKnife", extends=False))
add_case("TRF-066", "F03", "FAIL", "Applicable ship has only a generic arrangement, not an ice knife or equivalent means.", build_066("TRF-066-F03", ice="IA", arrangement="generic"))
add_case("TRF-066", "F04", "FAIL", "Applicable ship is missing the iceKnifePracticable applicability state.", build_066("TRF-066-F04", ice="IA Super", omit_practicable=True))


# ============================================================
# TRF-067 — IA / IA SUPER RUDDER LOAD-ABSORBING ARRANGEMENT
# ============================================================

def build_067(cid, ice="IA", arrangement="loadAbsorbing", omit=False, untyped=False):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice], ex)
    if not omit:
        arr = ex.arrangement
        if not untyped:
            if arrangement == "loadAbsorbing":
                g.add((arr, RDF.type, NLTL.rudderLoadAbsorbingArrangement))
            elif arrangement == "iceKnife":
                g.add((arr, RDF.type, NLTL.iceKnife))
        add_value(g, ship, "hasRudderProtectionArrangement", arr, ex)
    return g


def oracle_067(g):
    ship = exactly_one_subject(g, NLTL.ship)
    if ship is None: return False
    ice = obj_value(g, ship, "iceClass")
    if ice not in (NLTL.iceClassIa, NLTL.iceClassIaSuper):
        return True
    arr = obj_value(g, ship, "hasRudderProtectionArrangement")
    return typed_as(g, arr, NLTL.rudderLoadAbsorbingArrangement)


add_case("TRF-067", "P01", "PASS", "IA ship has a typed rudder load-absorbing arrangement.", build_067("TRF-067-P01", ice="IA"))
add_case("TRF-067", "P02", "PASS", "IA Super ship has a typed rudder load-absorbing arrangement.", build_067("TRF-067-P02", ice="IA Super"))
add_case("TRF-067", "P03", "PASS", "IC ship is outside the IA/IA Super conditional obligation.", build_067("TRF-067-P03", ice="IC", omit=True))
add_case("TRF-067", "F01", "FAIL", "Applicable ship is missing a rudder load-absorbing arrangement.", build_067("TRF-067-F01", ice="IA", omit=True))
add_case("TRF-067", "F02", "FAIL", "An ice knife is not a substitute for the separate load-absorbing arrangement required by this clause.", build_067("TRF-067-F02", ice="IA", arrangement="iceKnife"))
add_case("TRF-067", "F03", "FAIL", "Rudder-protection relationship points to an untyped arrangement node.", build_067("TRF-067-F03", ice="IA Super", untyped=True))


ORACLES = {
    "TRF-053": oracle_053,
    "TRF-054": oracle_054,
    "TRF-055": oracle_055,
    "TRF-056": oracle_056,
    "TRF-057": oracle_057,
    "TRF-058": oracle_058,
    "TRF-059": oracle_059,
    "TRF-060": oracle_060,
    "TRF-062": oracle_062,
    "TRF-063": oracle_063,
    "TRF-064": oracle_064,
    "TRF-066": oracle_066,
    "TRF-067": oracle_067,
}

# 13 requirements, 102 frozen behavioral cases.
assert len(CASE_DEFS) == 102, len(CASE_DEFS)
assert set(x["requirement_id"] for x in CASE_DEFS) == set(REQS)


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
    manifest_path = ROOT / "manifests" / "traficom_batch_f_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_f_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch F manifest does not exist")
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

    lock_path = locks_root / "traficom_batch_f_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch F lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {
        "TRF-053": "4.5.1",
        "TRF-054": "4.5.2",
        "TRF-055": "4.5.3",
        "TRF-056": "4.5.3",
        "TRF-057": "4.6.1",
        "TRF-058": "4.6.1",
        "TRF-059": "4.6.2",
        "TRF-060": "4.6.2",
        "TRF-062": "4.8",
        "TRF-063": "4.8",
        "TRF-064": "4.8",
        "TRF-066": "5",
        "TRF-067": "5",
    }

    # Strong collision guard before writing anything.
    planned_paths = []
    for c in CASE_DEFS:
        req = c["requirement_id"]
        planned_paths.append(rdf_root / req / f"{c['case_id']}.ttl")
    planned_paths += [spec_root / f"{req}.json" for req in REQS]
    planned_paths += [
        manifest_root / "traficom_batch_f_manifest.jsonl",
        scripts_root / "validate_traficom_batch_f.py",
        ROOT / "README_TRAFICOM_BATCH_F.md",
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

    manifest_path = manifest_root / "traficom_batch_f_manifest.jsonl"
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
        "benchmark": "TRAFICOM Behavioral Benchmark Batch F",
        "source_lock_id": INDEX["sourceLockId"],
        "source_id": "SRC-TRAFICOM-2021",
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    validator_path = scripts_root / "validate_traficom_batch_f.py"
    shutil.copy2(Path(__file__).resolve(), validator_path)
    validator_path.chmod(0o755)

    counts = {req: sum(1 for x in CASE_DEFS if x["requirement_id"] == req) for req in REQS}
    (ROOT / "README_TRAFICOM_BATCH_F.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch F\n\n"
        f"Requirements: {len(REQS)}\n"
        f"Cases: {len(CASE_DEFS)}\n\n"
        + ", ".join(REQS) + "\n\n"
        "Scope: TRAFICOM 2021 sections 4.5.1-4.6.2, 4.8 and selected complete Chapter 5 rudder requirements.\n"
        "TRF-061 and TRF-065 are intentionally excluded because frozen R13 does not classify them COMPLETE.\n\n"
        "Generated SHACL was not inspected during fixture construction.\n"
        "TRF-060 is COMPLEX_READINESS with formulaExecutionRequired=false; its cases test the frozen interface/table/owner/unit contract rather than executing the advanced section-modulus calculation.\n\n"
        "Per-requirement cases: " + json.dumps(counts, sort_keys=True) + "\n\n"
        "Validate with:\n\npython3 scripts/validate_traficom_batch_f.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(check_hashes=True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = Path(__file__).name == "validate_traficom_batch_f.py" or "--validate-only" in sys.argv
    if validation_mode:
        ok = validate_existing(check_hashes=True)
        raise SystemExit(0 if ok else 1)
    generate()


if __name__ == "__main__":
    main()
