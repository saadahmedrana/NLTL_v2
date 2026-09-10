from pathlib import Path
import json
import hashlib
import math
import shutil
import sys
from datetime import date

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
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-b/"

REQS = ['TRF-011', 'TRF-012', 'TRF-013', 'TRF-014', 'TRF-015', 'TRF-016']
EXPECTED_MODES = {'TRF-011': 'DIRECT_STATIC', 'TRF-012': 'COMPLEX_READINESS', 'TRF-013': 'DIRECT_STATIC', 'TRF-014': 'DIRECT_STATIC', 'TRF-015': 'DIRECT_STATIC', 'TRF-016': 'DIRECT_CALCULATION'}

for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]

for req in REQS:
    if EXPECTED_MODES[req] == "COMPLEX_READINESS":
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

EDITION_2021 = NLTL.iceClassRegulationEdition2021
EDITION_2017 = NLTL.iceClassRegulationEdition2017
EDITION_2010 = NLTL.iceClassRegulationEdition2010
EDITION_2008 = NLTL.iceClassRegulationEdition2008
EDITION_2002 = NLTL.iceClassRegulationEdition2002
EDITION_1985 = NLTL.iceClassRuleEdition1985


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
            raise RuntimeError(f"{term} has no frozen unit; provide source-grounded unit_override")
        q = ex[name or term + "Value"]
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


def bool_value(g, s, term):
    o = one(g, s, NLTL[term])
    if o is None:
        return None
    try:
        return bool(o.toPython())
    except Exception:
        return None


def date_value(g, s, term):
    o = one(g, s, NLTL[term])
    if o is None:
        return None
    try:
        return date.fromisoformat(str(o))
    except Exception:
        return None


def obj_value(g, s, term):
    return one(g, s, NLTL[term])


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
# TRAFICOM BATCH B — ICE CLASS DRAUGHT / WATERLINES
# ============================================================

def add_profile(g, ex, owner, prefix, profile):
    for i, (x, z) in enumerate(sorted(profile.items())):
        p = ex[f"{prefix}Point{i+1}"]
        g.add((p, RDF.type, NLTL.waterlineProfilePoint))
        g.add((owner, NLTL.hasWaterlineProfilePoint, p))
        add_value(g, p, "longitudinalPosition", x, ex, f"{prefix}X{i+1}")
        add_value(g, p, "verticalCoordinate", z, ex, f"{prefix}Z{i+1}")


def profile_map(g, line):
    points = list(g.objects(line, NLTL.hasWaterlineProfilePoint))
    if not points:
        return None
    out = {}
    for p in points:
        x = qty_number(g, p, "longitudinalPosition")
        z = qty_number(g, p, "verticalCoordinate")
        if x is None or z is None or x in out:
            return None
        out[x] = z
    return out


def build_011(cid, intended_profiles, upper_profile=None, omit_upper=False, upper_wrong_owner=False):
    g, ex, ship = new_graph(cid)
    for i, profile in enumerate(intended_profiles):
        line = ex[f"intendedLine{i+1}"]
        g.add((line, RDF.type, NLTL.iceWaterline))
        g.add((ship, NLTL.hasIntendedIceOperatingWaterline, line))
        add_profile(g, ex, line, f"i{i+1}", profile)

    if not omit_upper:
        upper = ex.upperIceWaterline
        g.add((upper, RDF.type, NLTL.iceWaterline))
        g.add((ship, NLTL.hasUpperIceWaterline, upper))
        if upper_profile is not None:
            if upper_wrong_owner:
                add_profile(g, ex, ship, "upperWrong", upper_profile)
            else:
                add_profile(g, ex, upper, "upper", upper_profile)
    return g


def oracle_011(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    intended = list(g.objects(ship, NLTL.hasIntendedIceOperatingWaterline))
    upper = one(g, ship, NLTL.hasUpperIceWaterline)
    if not intended or upper is None:
        return False

    maps = [profile_map(g, line) for line in intended]
    up = profile_map(g, upper)
    if any(m is None for m in maps) or up is None:
        return False

    xs = set().union(*(m.keys() for m in maps))
    if set(up.keys()) != xs:
        return False
    for x in xs:
        vals = [m[x] for m in maps if x in m]
        if not vals or not close(up[x], max(vals)):
            return False
    return True


def build_012(cid, missing=None, wrong_owner=False):
    g, ex, ship = new_graph(cid)
    intended = ex.intendedLine
    lower = ex.lowerIceWaterline
    g.add((intended, RDF.type, NLTL.iceWaterline))
    g.add((lower, RDF.type, NLTL.iceWaterline))

    if missing != "hasIntendedIceOperatingWaterline":
        g.add((ship, NLTL.hasIntendedIceOperatingWaterline, intended))
    if missing != "hasLowerIceWaterline":
        g.add((ship, NLTL.hasLowerIceWaterline, lower))

    ip = ex.intendedPoint
    lp = ex.lowerPoint
    g.add((ip, RDF.type, NLTL.waterlineProfilePoint))
    g.add((lp, RDF.type, NLTL.waterlineProfilePoint))

    if missing != "intendedPointPath":
        g.add(((ship if wrong_owner else intended), NLTL.hasWaterlineProfilePoint, ip))
    if missing != "lowerPointPath":
        g.add((lower, NLTL.hasWaterlineProfilePoint, lp))

    if missing != "intendedLongitudinalPosition":
        add_value(g, ip, "longitudinalPosition", 10.0, ex, "ix")
    if missing != "intendedVerticalCoordinate":
        add_value(g, ip, "verticalCoordinate", 5.0, ex, "iz")
    if missing != "lowerLongitudinalPosition":
        add_value(g, lp, "longitudinalPosition", 10.0, ex, "lx")
    if missing != "lowerVerticalCoordinate":
        add_value(g, lp, "verticalCoordinate", 3.5, ex, "lz")
    return g


def line_ready(g, line):
    return profile_map(g, line) is not None


def oracle_012(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    intended = list(g.objects(ship, NLTL.hasIntendedIceOperatingWaterline))
    lower = one(g, ship, NLTL.hasLowerIceWaterline)
    if not intended or lower is None:
        return False
    return all(line_ready(g, line) for line in intended) and line_ready(g, lower)


def build_013(
    cid,
    strengthened=True,
    ice_class="IA",
    fore=5.0,
    aft=5.0,
    min_fore=4.0,
    max_fore=6.0,
    min_aft=4.0,
    max_aft=6.0,
    omit=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "shipIceStrengthened", strengthened, ex)
    if ice_class is not None:
        add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)

    upper = ex.upperIceWaterline
    lower = ex.lowerIceWaterline
    g.add((upper, RDF.type, NLTL.iceWaterline))
    g.add((lower, RDF.type, NLTL.iceWaterline))
    if omit != "hasUpperIceWaterline":
        g.add((ship, NLTL.hasUpperIceWaterline, upper))
    if omit != "hasLowerIceWaterline":
        g.add((ship, NLTL.hasLowerIceWaterline, lower))

    vals = {
        "operatingForeDraught": fore,
        "operatingAftDraught": aft,
        "minimumIceClassDraughtFore": min_fore,
        "maximumIceClassDraughtFore": max_fore,
        "minimumIceClassDraughtAft": min_aft,
        "maximumIceClassDraughtAft": max_aft,
    }
    for term, value in vals.items():
        if omit == term:
            continue
        add_value(g, ship, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def oracle_013(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    strengthened = bool_value(g, ship, "shipIceStrengthened")
    if strengthened is None:
        return False
    if not strengthened:
        return True
    if obj_value(g, ship, "iceClass") is None:
        return False
    if one(g, ship, NLTL.hasUpperIceWaterline) is None or one(g, ship, NLTL.hasLowerIceWaterline) is None:
        return False

    vals = {t: qty_number(g, ship, t) for t in [
        "operatingForeDraught", "operatingAftDraught",
        "minimumIceClassDraughtFore", "maximumIceClassDraughtFore",
        "minimumIceClassDraughtAft", "maximumIceClassDraughtAft",
    ]}
    if any(v is None for v in vals.values()):
        return False
    return (
        vals["minimumIceClassDraughtFore"] <= vals["operatingForeDraught"] <= vals["maximumIceClassDraughtFore"]
        and vals["minimumIceClassDraughtAft"] <= vals["operatingAftDraught"] <= vals["maximumIceClassDraughtAft"]
    )


def build_014(
    cid,
    assessment="2026-01-01",
    construction="2010-01-01",
    summer=7.0,
    uiwl=6.0,
    drydock=None,
    markings=True,
    mark_draught=6.0,
    omit=None,
):
    g, ex, ship = new_graph(cid)
    if assessment is not None:
        add_value(g, ship, "assessmentDate", assessment, ex)
    if construction is not None:
        add_value(g, ship, "constructionDate", construction, ex)
    add_value(g, ship, "summerLoadLineFreshWaterDraught", summer, ex, "summer")
    add_value(g, ship, "upperIceWaterlineDraught", uiwl, ex, "uiwl")
    add_value(g, ship, "iceClass", ICE_CLASSES["IA"], ex)
    if drydock is not None:
        add_value(g, ship, "firstScheduledDryDockingDate", drydock, ex)

    cert = ex.certificate
    doc = ex.restrictionDocument
    g.add((cert, RDF.type, NLTL.classCertificate))
    g.add((doc, RDF.type, NLTL.iceDraughtRestrictionDocument))
    if omit != "hasClassCertificate":
        g.add((ship, NLTL.hasClassCertificate, cert))
    if omit != "hasIceDraughtRestrictionDocument":
        g.add((ship, NLTL.hasIceDraughtRestrictionDocument, doc))

    cert_vals = {
        "maximumIceClassDraughtFore": 6.0,
        "maximumIceClassDraughtAmidships": 6.0,
        "maximumIceClassDraughtAft": 6.0,
        "minimumIceClassDraughtFore": 4.0,
        "minimumIceClassDraughtAmidships": 4.0,
        "minimumIceClassDraughtAft": 4.0,
    }
    for term, value in cert_vals.items():
        if omit != term:
            add_value(g, cert, term, value, ex, "cert_" + term)

    if omit != "retainedOnBoard":
        add_value(g, doc, "retainedOnBoard", True, ex)
    if omit != "readilyAvailableToMaster":
        add_value(g, doc, "readilyAvailableToMaster", True, ex)

    if markings:
        if omit != "warningTrianglePresent":
            add_value(g, ship, "warningTrianglePresent", True, ex)
        if omit != "iceClassDraughtMarkPresent":
            add_value(g, ship, "iceClassDraughtMarkPresent", True, ex)
        if omit != "iceClassDraughtMarkDraughtAmidships":
            add_value(g, ship, "iceClassDraughtMarkDraughtAmidships", mark_draught, ex, "markDraught")
    return g


def markings_complete(g, ship, cert):
    if bool_value(g, ship, "warningTrianglePresent") is not True:
        return False
    if bool_value(g, ship, "iceClassDraughtMarkPresent") is not True:
        return False
    mark = qty_number(g, ship, "iceClassDraughtMarkDraughtAmidships")
    max_mid = qty_number(g, cert, "maximumIceClassDraughtAmidships")
    return mark is not None and max_mid is not None and close(mark, max_mid)


def oracle_014(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    assessment = date_value(g, ship, "assessmentDate")
    construction = date_value(g, ship, "constructionDate")
    summer = qty_number(g, ship, "summerLoadLineFreshWaterDraught")
    uiwl = qty_number(g, ship, "upperIceWaterlineDraught")
    cert = one(g, ship, NLTL.hasClassCertificate)
    doc = one(g, ship, NLTL.hasIceDraughtRestrictionDocument)
    if None in (assessment, construction, summer, uiwl, cert, doc):
        return False
    if obj_value(g, ship, "iceClass") is None:
        return False
    if (cert, RDF.type, NLTL.classCertificate) not in g or (doc, RDF.type, NLTL.iceDraughtRestrictionDocument) not in g:
        return False
    if bool_value(g, doc, "retainedOnBoard") is not True or bool_value(g, doc, "readilyAvailableToMaster") is not True:
        return False
    for term in [
        "maximumIceClassDraughtFore", "maximumIceClassDraughtAmidships", "maximumIceClassDraughtAft",
        "minimumIceClassDraughtFore", "minimumIceClassDraughtAmidships", "minimumIceClassDraughtAft",
    ]:
        if qty_number(g, cert, term) is None:
            return False

    marking_required = summer > uiwl
    if not marking_required:
        return True

    cutoff = date(2007, 7, 1)
    if construction >= cutoff:
        return markings_complete(g, ship, cert)

    if markings_complete(g, ship, cert):
        return True

    drydock = date_value(g, ship, "firstScheduledDryDockingDate")
    if drydock is None:
        return False
    if drydock > assessment:
        return True
    return False


def build_015(
    cid,
    navigating=True,
    operating_draught=5.5,
    uiwl=6.0,
    operating_trim=0.3,
    max_trim=0.5,
    route_salinity=6.0,
    loading_salinity=6.0,
    omit=None,
):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "navigatingInIce", navigating, ex)
    values = {
        "operatingDraught": operating_draught,
        "upperIceWaterlineDraught": uiwl,
        "operatingTrim": operating_trim,
        "maximumPermittedIceTrim": max_trim,
        "intendedRouteSeaWaterSalinity": route_salinity,
        "loadingCalculationSeaWaterSalinity": loading_salinity,
    }
    for term, value in values.items():
        if omit != term:
            add_value(g, ship, term, value, ex, term)
    return g


def oracle_015(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    nav = bool_value(g, ship, "navigatingInIce")
    if nav is None:
        return False
    if not nav:
        return True
    op_d = qty_number(g, ship, "operatingDraught")
    uiwl = qty_number(g, ship, "upperIceWaterlineDraught")
    trim = qty_number(g, ship, "operatingTrim")
    max_trim = qty_number(g, ship, "maximumPermittedIceTrim")
    route_s = qty_number(g, ship, "intendedRouteSeaWaterSalinity")
    load_s = qty_number(g, ship, "loadingCalculationSeaWaterSalinity")
    if None in (op_d, uiwl, trim, max_trim, route_s, load_s):
        return False
    return op_d <= uiwl and abs(trim) <= max_trim and close(route_s, load_s)


def build_016(
    cid,
    navigating=True,
    displacement=5000.0,
    hi=0.8,
    amid=4.0,
    liwl_amid=3.8,
    forward=None,
    propeller_submerged=True,
    tank_above=True,
    tank_needed=True,
    freezing=True,
    omit=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "navigatingInIce", navigating, ex)

    upper = ex["upper"]
    lower = ex["lower"]
    g.add((upper, RDF.type, NLTL.iceWaterline))
    g.add((lower, RDF.type, NLTL.iceWaterline))
    if omit != "hasUpperIceWaterline":
        g.add((ship, NLTL.hasUpperIceWaterline, upper))
    if omit != "hasLowerIceWaterline":
        g.add((ship, NLTL.hasLowerIceWaterline, lower))

    if omit != "displacementAtUpperIceWaterline":
        add_value(g, upper, "displacementAtUpperIceWaterline", displacement, ex, "dui", wrong_unit=(wrong_unit == "displacementAtUpperIceWaterline"))
    if omit != "levelIceThickness":
        add_value(g, ship, "levelIceThickness", hi, ex, "hi", wrong_unit=(wrong_unit == "levelIceThickness"))
    if omit != "draughtAmidships":
        add_value(g, ship, "draughtAmidships", amid, ex, "amid")
    if omit != "liwlDraughtAmidships":
        add_value(g, lower, "liwlDraughtAmidships", liwl_amid, ex, "liwlAmid")
    if omit != "propellerHighestPointSubmerged":
        add_value(g, ship, "propellerHighestPointSubmerged", propeller_submerged, ex)

    required = min((2.0 + 0.00025 * displacement) * hi, 4.0 * hi)
    if forward is None:
        forward = required
    if omit != "forwardDraught":
        add_value(g, ship, "forwardDraught", forward, ex, "forward")

    tank = ex.ballastTank
    g.add((tank, RDF.type, NLTL.ballastTank))
    g.add((ship, NLTL.hasBallastTank, tank))
    add_value(g, tank, "situatedAboveLowerIceWaterline", tank_above, ex)
    add_value(g, tank, "usedToReachLowerIceWaterline", tank_needed, ex)
    if omit != "freezingPreventionPresent":
        add_value(g, tank, "freezingPreventionPresent", freezing, ex)
    return g


def oracle_016(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    nav = bool_value(g, ship, "navigatingInIce")
    if nav is None:
        return False
    if not nav:
        return True

    upper = one(g, ship, NLTL.hasUpperIceWaterline)
    lower = one(g, ship, NLTL.hasLowerIceWaterline)
    if upper is None or lower is None:
        return False

    displacement = qty_number(g, upper, "displacementAtUpperIceWaterline")
    hi = qty_number(g, ship, "levelIceThickness")
    amid = qty_number(g, ship, "draughtAmidships")
    liwl_amid = qty_number(g, lower, "liwlDraughtAmidships")
    forward = qty_number(g, ship, "forwardDraught")
    if None in (displacement, hi, amid, liwl_amid, forward):
        return False
    if amid < liwl_amid:
        return False
    if bool_value(g, ship, "propellerHighestPointSubmerged") is not True:
        return False

    required = min((2.0 + 0.00025 * displacement) * hi, 4.0 * hi)
    if forward + 1e-9 < required:
        return False

    for tank in g.objects(ship, NLTL.hasBallastTank):
        above = bool_value(g, tank, "situatedAboveLowerIceWaterline")
        needed = bool_value(g, tank, "usedToReachLowerIceWaterline")
        if above is None or needed is None:
            return False
        if above and needed and bool_value(g, tank, "freezingPreventionPresent") is not True:
            return False
    return True


# TRF-011
add_case("TRF-011", "P01", "PASS", "One intended operating waterline is exactly reproduced by the UIWL envelope.", build_011("TRF-011-P01", [{0.0: 4.0, 10.0: 4.5}], {0.0: 4.0, 10.0: 4.5}))
add_case("TRF-011", "P02", "PASS", "UIWL takes the pointwise maximum of two intended ice-operating waterlines.", build_011("TRF-011-P02", [{0.0: 4.0, 10.0: 4.5}, {0.0: 4.2, 10.0: 4.3}], {0.0: 4.2, 10.0: 4.5}))
add_case("TRF-011", "P03", "PASS", "Broken-line UIWL correctly contains the pointwise envelope at three longitudinal positions.", build_011("TRF-011-P03", [{0.0: 4.0, 5.0: 4.8, 10.0: 4.4}, {0.0: 4.1, 5.0: 4.6, 10.0: 4.7}], {0.0: 4.1, 5.0: 4.8, 10.0: 4.7}))
add_case("TRF-011", "F01", "FAIL", "UIWL lies below an intended operating waterline at one position.", build_011("TRF-011-F01", [{0.0: 4.0, 10.0: 4.5}, {0.0: 4.2, 10.0: 4.3}], {0.0: 4.1, 10.0: 4.5}))
add_case("TRF-011", "F02", "FAIL", "UIWL is above rather than equal to the highest intended point, so it is not the envelope.", build_011("TRF-011-F02", [{0.0: 4.0, 10.0: 4.5}], {0.0: 4.2, 10.0: 4.5}))
add_case("TRF-011", "F03", "FAIL", "The upper ice waterline relationship is missing.", build_011("TRF-011-F03", [{0.0: 4.0}], omit_upper=True))
add_case("TRF-011", "F04", "FAIL", "UIWL profile points are attached to the wrong owner.", build_011("TRF-011-F04", [{0.0: 4.0}], {0.0: 4.0}, upper_wrong_owner=True))

# TRF-012
add_case("TRF-012", "P01", "PASS", "Intended and lower waterlines have profile-point paths with longitudinal and vertical coordinates.", build_012("TRF-012-P01"))
for suffix, missing in [
    ("F01", "hasIntendedIceOperatingWaterline"),
    ("F02", "hasLowerIceWaterline"),
    ("F03", "intendedPointPath"),
    ("F04", "lowerPointPath"),
    ("F05", "intendedLongitudinalPosition"),
    ("F06", "lowerVerticalCoordinate"),
]:
    add_case("TRF-012", suffix, "FAIL", f"Readiness input/result is incomplete: {missing} is missing.", build_012(f"TRF-012-{suffix}", missing=missing))
add_case("TRF-012", "F07", "FAIL", "Intended-waterline profile point is attached to ship rather than the waterline.", build_012("TRF-012-F07", wrong_owner=True))

# TRF-013
add_case("TRF-013", "P01", "PASS", "Ice-strengthened ship operates strictly between minimum and maximum fore/aft draughts.", build_013("TRF-013-P01"))
add_case("TRF-013", "P02", "PASS", "Lower draught boundaries are inclusive.", build_013("TRF-013-P02", fore=4.0, aft=4.0))
add_case("TRF-013", "P03", "PASS", "Upper draught boundaries are inclusive.", build_013("TRF-013-P03", fore=6.0, aft=6.0))
add_case("TRF-013", "P04", "PASS", "Non-ice-strengthened ship is outside this conditional draught obligation.", build_013("TRF-013-P04", strengthened=False, ice_class=None, omit="hasUpperIceWaterline"))
add_case("TRF-013", "F01", "FAIL", "Fore draught is below the minimum ice-class draught.", build_013("TRF-013-F01", fore=3.99))
add_case("TRF-013", "F02", "FAIL", "Aft draught exceeds the maximum ice-class draught.", build_013("TRF-013-F02", aft=6.01))
add_case("TRF-013", "F03", "FAIL", "Required maximum fore draught is missing.", build_013("TRF-013-F03", omit="maximumIceClassDraughtFore"))
add_case("TRF-013", "F04", "FAIL", "Required lower-waterline relationship is missing.", build_013("TRF-013-F04", omit="hasLowerIceWaterline"))
add_case("TRF-013", "F05", "FAIL", "Operating fore draught uses the wrong unit.", build_013("TRF-013-F05", wrong_unit="operatingForeDraught"))

# TRF-014
add_case("TRF-014", "P01", "PASS", "Pre-2007 ship with complete marking evidence passes without firstScheduledDryDockingDate.", build_014("TRF-014-P01", construction="2000-01-01", drydock=None, markings=True))
add_case("TRF-014", "P02", "PASS", "Pre-2007 ship before its future scheduled dry docking may legitimately lack the marking.", build_014("TRF-014-P02", assessment="2008-01-01", construction="2000-01-01", drydock="2009-01-01", markings=False))
add_case("TRF-014", "P03", "PASS", "Post-2007 ship with required certificate, document and markings complies.", build_014("TRF-014-P03", construction="2010-01-01", markings=True))
add_case("TRF-014", "P04", "PASS", "Construction date exactly 2007-07-01 uses the post-cutoff marking obligation.", build_014("TRF-014-P04", construction="2007-07-01", markings=True))
add_case("TRF-014", "P05", "PASS", "When summer fresh-water load line is not above UIWL, marking obligation is not triggered.", build_014("TRF-014-P05", construction="2010-01-01", summer=6.0, uiwl=6.0, markings=False))
add_case("TRF-014", "F01", "FAIL", "Draught-restriction document is not demonstrably retained on board.", build_014("TRF-014-F01", omit="retainedOnBoard"))
add_case("TRF-014", "F02", "FAIL", "Class certificate is missing one required ice-class draught value.", build_014("TRF-014-F02", omit="minimumIceClassDraughtAft"))
add_case("TRF-014", "F03", "FAIL", "Post-cutoff ship with summer load line above UIWL lacks required markings.", build_014("TRF-014-F03", construction="2010-01-01", markings=False))
add_case("TRF-014", "F04", "FAIL", "Pre-cutoff ship is past its scheduled dry docking but required markings remain absent.", build_014("TRF-014-F04", assessment="2010-01-01", construction="2000-01-01", drydock="2009-01-01", markings=False))
add_case("TRF-014", "F05", "FAIL", "Ice-class draught mark records a draught different from the certificate maximum amidships draught.", build_014("TRF-014-F05", construction="2010-01-01", markings=True, mark_draught=5.5))

# TRF-015
add_case("TRF-015", "P01", "PASS", "Navigating-in-ice case respects UIWL draught, trim limit and route salinity.", build_015("TRF-015-P01"))
add_case("TRF-015", "P02", "PASS", "Draught and trim exactly at their limits are permitted.", build_015("TRF-015-P02", operating_draught=6.0, operating_trim=0.5))
add_case("TRF-015", "P03", "PASS", "When not navigating in ice the ice-navigation loading constraint is not applicable.", build_015("TRF-015-P03", navigating=False, omit="loadingCalculationSeaWaterSalinity"))
add_case("TRF-015", "F01", "FAIL", "Operating draught exceeds UIWL.", build_015("TRF-015-F01", operating_draught=6.1))
add_case("TRF-015", "F02", "FAIL", "Operating trim exceeds the permitted ice trim.", build_015("TRF-015-F02", operating_trim=0.6))
add_case("TRF-015", "F03", "FAIL", "Loading calculation does not use intended-route salinity.", build_015("TRF-015-F03", loading_salinity=5.0))
add_case("TRF-015", "F04", "FAIL", "Intended-route salinity is missing during ice navigation.", build_015("TRF-015-F04", omit="intendedRouteSeaWaterSalinity"))
add_case("TRF-015", "F05", "FAIL", "Maximum permitted ice trim is missing.", build_015("TRF-015-F05", omit="maximumPermittedIceTrim"))

# TRF-016
add_case("TRF-016", "P01", "PASS", "Forward draught satisfies the uncapped formula branch for a 5000 t displacement.", build_016("TRF-016-P01", displacement=5000.0, hi=0.8))
add_case("TRF-016", "P02", "PASS", "Forward draught satisfies the 4hi cap branch for a 10000 t displacement.", build_016("TRF-016-P02", displacement=10000.0, hi=0.8))
add_case("TRF-016", "P03", "PASS", "Ballast tank above LIWL but not needed to reach LIWL does not require freezing prevention.", build_016("TRF-016-P03", tank_above=True, tank_needed=False, freezing=False))
add_case("TRF-016", "P04", "PASS", "Non-ice-navigation case is outside the conditional loading obligations.", build_016("TRF-016-P04", navigating=False, omit="forwardDraught"))
add_case("TRF-016", "F01", "FAIL", "Forward draught is below formula 2.1 requirement.", build_016("TRF-016-F01", displacement=5000.0, hi=0.8, forward=2.5))
add_case("TRF-016", "F02", "FAIL", "Draught amidships is below LIWL amidships.", build_016("TRF-016-F02", amid=3.7, liwl_amid=3.8))
add_case("TRF-016", "F03", "FAIL", "Highest point of propeller is not submerged.", build_016("TRF-016-F03", propeller_submerged=False))
add_case("TRF-016", "F04", "FAIL", "Required ballast tank above LIWL lacks freezing prevention.", build_016("TRF-016-F04", tank_above=True, tank_needed=True, freezing=False))
add_case("TRF-016", "F05", "FAIL", "UIWL displacement needed by formula 2.1 is missing.", build_016("TRF-016-F05", omit="displacementAtUpperIceWaterline"))
add_case("TRF-016", "F06", "FAIL", "Level ice thickness uses the wrong unit.", build_016("TRF-016-F06", wrong_unit="levelIceThickness"))

assert len(CASE_DEFS) == 52, len(CASE_DEFS)

ORACLES = {
    "TRF-011": oracle_011,
    "TRF-012": oracle_012,
    "TRF-013": oracle_013,
    "TRF-014": oracle_014,
    "TRF-015": oracle_015,
    "TRF-016": oracle_016
}


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
    manifest_path = ROOT / "manifests" / "traficom_batch_b_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_b_fixture_lock.json"

    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch B manifest does not exist")

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
            diagnostics.append((
                row["case_id"],
                "oracle",
                f"expected={row['expected']} actual={actual}",
            ))

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
    rdf_root = ROOT / "rdf" / "TRF"
    spec_root = ROOT / "specifications" / "TRF"
    manifest_root = ROOT / "manifests"
    locks_root = ROOT / "locks"
    scripts_root = ROOT / "scripts"

    for p in [rdf_root, spec_root, manifest_root, locks_root, scripts_root]:
        p.mkdir(parents=True, exist_ok=True)

    lock_path = locks_root / "traficom_batch_b_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch B lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {'TRF-011': '2.1 (UIWL envelope)', 'TRF-012': '2.1 (LIWL readiness/profile representation)', 'TRF-013': '2.2 (maximum/minimum fore and aft draught)', 'TRF-014': '2.2 (documentation, certificate and ice-draught marking obligations)', 'TRF-015': '2.2 (UIWL draught/trim and route-salinity loading limits)', 'TRF-016': '2.2 / equation (2.1) (LIWL loading, ballast freezing prevention, propeller submergence and forward draught)'}
    rows = []

    for c in CASE_DEFS:
        req = c["requirement_id"]
        outdir = rdf_root / req
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{c['case_id']}.ttl"
        if p.exists():
            raise SystemExit(f"Refusing to overwrite pre-existing fixture: {p}")
        c["graph"].serialize(destination=p, format="turtle")
        rows.append({
            "requirement_id": req,
            "case_id": c["case_id"],
            "expected": c["expected"],
            "rdf_path": str(p.relative_to(ROOT)),
            "source_id": "SRC-TRAFICOM-2021",
            "source_clause": clauses[req],
            "verification_mode": EXPECTED_MODES[req],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
            "source_oracle_rationale": c["rationale"],
            "generated_shacl_inspected": False,
        })

    manifest_path = manifest_root / "traficom_batch_b_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    for req in REQS:
        spec = {
            "requirement_id": req,
            "source_id": "SRC-TRAFICOM-2021",
            "source_clause": clauses[req],
            "source_lock_id": INDEX["sourceLockId"],
            "r13_contract": CONTRACTS[req],
            "test_cases": [
                {
                    "case_id": x["case_id"],
                    "expected": x["expected"],
                    "rationale": x["rationale"],
                }
                for x in CASE_DEFS
                if x["requirement_id"] == req
            ],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
            "benchmark_policy": "Source/R13-defined behavioral oracle created without inspecting generated SHACL.",
        }
        (spec_root / f"{req}_traficom_batch_b.json").write_text(
            json.dumps(spec, indent=2) + "\n"
        )

    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")

    frozen = [manifest_path]
    frozen += [
        spec_root / f"{req}_traficom_batch_b.json"
        for req in REQS
    ]
    for req in REQS:
        frozen += sorted((rdf_root / req).glob("*.ttl"))

    lock = {
        "benchmark": "TRAFICOM Behavioral Benchmark Batch B",
        "source_lock_id": INDEX["sourceLockId"],
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "previous_frozen_batches_modified": False,
        "frozen_files": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in frozen
        },
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")

    validator = scripts_root / "validate_traficom_batch_b.py"
    shutil.copy2(Path(__file__).resolve(), validator)
    validator.chmod(0o755)

    (ROOT / "README_TRAFICOM_BATCH_B.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch B\n\n"
        f"Requirements: {len(REQS)}\nCases: {len(CASE_DEFS)}\n\n"
        + "\n".join(REQS)
        + "\n\nGenerated SHACL was not inspected during fixture construction.\n"
        + "The batch is frozen with SHA-256 hashes after source-oracle validation.\n\n"
        + "Run:\n\npython3 scripts/validate_traficom_batch_b.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = (
        Path(__file__).name == "validate_traficom_batch_b.py"
        or "--validate-only" in sys.argv
    )
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__ == "__main__":
    main()
