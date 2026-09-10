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
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-c/"

REQS = ['TRF-017', 'TRF-018', 'TRF-020', 'TRF-022', 'TRF-023', 'TRF-024', 'TRF-025', 'TRF-026', 'TRF-027', 'TRF-028']
EXPECTED_MODES = {'TRF-017': 'DIRECT_STATIC', 'TRF-018': 'DIRECT_CALCULATION', 'TRF-020': 'COMPLEX_READINESS', 'TRF-022': 'COMPLEX_READINESS', 'TRF-023': 'DIRECT_STATIC', 'TRF-024': 'DIRECT_STATIC', 'TRF-025': 'COMPLEX_READINESS', 'TRF-026': 'COMPLEX_READINESS', 'TRF-027': 'DIRECT_CALCULATION', 'TRF-028': 'COMPLEX_READINESS'}

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
# TRAFICOM BATCH C — ENGINE OUTPUT / REQUIRED POWER
# ============================================================

def build_017(
    cid,
    continuous=5000.0,
    restriction=False,
    restricted=None,
    additional=None,
    total=None,
    omit=None,
):
    g, ex, ship = new_graph(cid)
    if omit != "propulsionMachineryContinuousOutput":
        add_value(g, ship, "propulsionMachineryContinuousOutput", continuous, ex, "continuous")
    if omit != "propulsionOutputRestrictionApplies":
        add_value(g, ship, "propulsionOutputRestrictionApplies", restriction, ex)
    if restricted is not None and omit != "restrictedPropulsionOutput":
        add_value(g, ship, "restrictedPropulsionOutput", restricted, ex, "restricted")
    if additional is not None and omit != "additionalPropulsionPower":
        add_value(g, ship, "additionalPropulsionPower", additional, ex, "additional")
    base = restricted if restriction else continuous
    if total is None and base is not None:
        total = base + (additional or 0.0)
    if omit != "maximumContinuousRatingPower" and total is not None:
        add_value(g, ship, "maximumContinuousRatingPower", total, ex, "total")
    return g


def oracle_017(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    continuous = qty_number(g, ship, "propulsionMachineryContinuousOutput")
    restricted_flag = bool_value(g, ship, "propulsionOutputRestrictionApplies")
    total = qty_number(g, ship, "maximumContinuousRatingPower")
    if continuous is None or restricted_flag is None or total is None:
        return False
    if restricted_flag:
        base = qty_number(g, ship, "restrictedPropulsionOutput")
        if base is None:
            return False
    else:
        base = continuous
    additional_vals = list(g.objects(ship, NLTL.additionalPropulsionPower))
    if len(additional_vals) > 1:
        return False
    additional = 0.0
    if additional_vals:
        additional = qty_number(g, ship, "additionalPropulsionPower")
        if additional is None:
            return False
    return close(total, base + additional)


def build_018(cid, ice_class="IA", calculated=1200.0, mcr=1200.0, omit=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    if ice_class is not None:
        add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    if omit != "calculatedRequiredPower":
        add_value(g, ship, "calculatedRequiredPower", calculated, ex, "required", wrong_unit=(wrong_unit == "calculatedRequiredPower"))
    if omit != "maximumContinuousRatingPower":
        add_value(g, ship, "maximumContinuousRatingPower", mcr, ex, "mcr", wrong_unit=(wrong_unit == "maximumContinuousRatingPower"))
    return g


def oracle_018(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    cls = obj_value(g, ship, "iceClass")
    if cls is None:
        return False
    thresholds = {
        ICE_CLASSES["IA Super"]: 2800.0,
        ICE_CLASSES["IA"]: 1000.0,
        ICE_CLASSES["IB"]: 1000.0,
        ICE_CLASSES["IC"]: 1000.0,
    }
    if cls not in thresholds:
        return True
    calc = qty_number(g, ship, "calculatedRequiredPower")
    mcr = qty_number(g, ship, "maximumContinuousRatingPower")
    if calc is None or mcr is None:
        return False
    return mcr + 1e-9 >= max(calc, thresholds[cls])


def build_020(
    cid,
    stage="2021-01-01",
    ice_class="IA Super",
    missing=None,
    wrong_owner=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "constructionStageDate", stage, ex)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)

    upper = ex["upper"]
    lower = ex["lower"]
    g.add((upper, RDF.type, NLTL.iceWaterline))
    g.add((lower, RDF.type, NLTL.iceWaterline))
    if missing != "hasUpperIceWaterline":
        g.add((ship, NLTL.hasUpperIceWaterline, upper))
    if missing != "hasLowerIceWaterline":
        g.add((ship, NLTL.hasLowerIceWaterline, lower))

    ship_terms = [
        ("engineOutputCoefficientKe", 2.03, None),
        ("propellerDiameter", 5.0, None),
        ("propellerCount", 1, None),
    ]
    for term, value, unit in ship_terms:
        if missing == term:
            continue
        owner = upper if wrong_owner == term else ship
        add_value(g, owner, term, value, ex, term, unit_override=unit, wrong_unit=(wrong_unit == term))

    if missing != "propellerPitchControlType":
        add_value(g, ship, "propellerPitchControlType", NLTL.controllablePitch, ex)
    if missing != "propulsionSystemType":
        add_value(g, ship, "propulsionSystemType", NLTL.conventionalPropulsionSystem, ex)

    for term, value in [
        ("upperIceWaterlineBreadth", 25.0),
        ("upperIceWaterlineLength", 150.0),
    ]:
        if missing != term:
            owner = ship if wrong_owner == term else upper
            add_value(g, owner, term, value, ex, term, wrong_unit=(wrong_unit == term))

    rch_vals = [
        ("brashIceChannelResistanceAtLowerIceWaterline", lower, 110000.0),
        ("brashIceChannelResistanceAtUpperIceWaterline", upper, 125000.0),
    ]
    for term, owner_default, value in rch_vals:
        if missing == term:
            continue
        owner = ship if wrong_owner == term else owner_default
        add_value(g, owner, term, value, ex, term, unit_override=str(UNIT.N), wrong_unit=(wrong_unit == term))

    results = [
        ("minimumRequiredPowerAtLowerIceWaterline", lower, 6200.0),
        ("minimumRequiredPowerAtUpperIceWaterline", upper, 7400.0),
    ]
    for term, owner_default, value in results:
        if missing == term:
            continue
        owner = ship if wrong_owner == term else owner_default
        add_value(g, owner, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def oracle_020(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    cls = obj_value(g, ship, "iceClass")
    if stage is None or cls is None:
        return False
    applicable = stage >= date(2003, 9, 1) and cls in {
        ICE_CLASSES["IA Super"], ICE_CLASSES["IA"], ICE_CLASSES["IB"], ICE_CLASSES["IC"]
    }
    if not applicable:
        return True

    upper = one(g, ship, NLTL.hasUpperIceWaterline)
    lower = one(g, ship, NLTL.hasLowerIceWaterline)
    if upper is None or lower is None:
        return False

    if qty_number(g, ship, "engineOutputCoefficientKe") is None:
        return False
    if qty_number(g, ship, "propellerDiameter") is None:
        return False
    count = one(g, ship, NLTL.propellerCount)
    if count is None:
        return False
    try:
        if int(count.toPython()) not in {1, 2, 3}:
            return False
    except Exception:
        return False

    pitch = obj_value(g, ship, "propellerPitchControlType")
    system = obj_value(g, ship, "propulsionSystemType")
    if pitch not in {NLTL.controllablePitch, NLTL.fixedPitch}:
        return False
    if system not in {NLTL.conventionalPropulsionSystem, NLTL.electricPropulsionMachinery, NLTL.hydraulicPropulsionMachinery}:
        return False

    if qty_number(g, upper, "upperIceWaterlineBreadth") is None or qty_number(g, upper, "upperIceWaterlineLength") is None:
        return False
    if qty_number(g, lower, "brashIceChannelResistanceAtLowerIceWaterline", str(UNIT.N)) is None:
        return False
    if qty_number(g, upper, "brashIceChannelResistanceAtUpperIceWaterline", str(UNIT.N)) is None:
        return False
    if qty_number(g, lower, "minimumRequiredPowerAtLowerIceWaterline") is None:
        return False
    if qty_number(g, upper, "minimumRequiredPowerAtUpperIceWaterline") is None:
        return False
    return True


def build_022(cid, missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    alpha = 24.0
    phi2 = 30.0
    L = 150.0
    T = 9.0
    B = 25.0
    raw = ((L * T) / (B ** 2)) ** 3
    psi = math.degrees(math.atan(math.tan(math.radians(phi2)) / math.sin(math.radians(alpha))))
    clamp = min(max(raw, 5.0), 20.0)

    vals = {
        "bowRakeAtQuarterBreadth": phi2,
        "waterlineAngleAtQuarterBreadth": alpha,
        "shipLength": L,
        "iceClassDraught": T,
        "shipBreadth": B,
        "coefficientC3": 845.0,
        "coefficientC4": 42.0,
        "coefficientC5": 825.0,
        "coefficientF1": 23.0,
        "coefficientF2": 45.8,
        "coefficientF3": 14.7,
        "coefficientF4": 29.0,
        "coefficientG1": 1530.0,
        "coefficientG2": 170.0,
        "coefficientG3": 400.0,
        "flareAngle": psi,
        "clampedHullGeometryTerm": clamp,
    }
    for term, value in vals.items():
        if missing != term:
            add_value(g, ship, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def oracle_022(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    required = [
        "bowRakeAtQuarterBreadth", "waterlineAngleAtQuarterBreadth",
        "shipLength", "iceClassDraught", "shipBreadth",
        "coefficientC3", "coefficientC4", "coefficientC5",
        "coefficientF1", "coefficientF2", "coefficientF3", "coefficientF4",
        "coefficientG1", "coefficientG2", "coefficientG3",
        "flareAngle", "clampedHullGeometryTerm",
    ]
    return all(qty_number(g, ship, t) is not None for t in required)


def build_023(cid, ice_class="IB", edition=EDITION_1985, required=900.0, mcr=900.0, omit=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    add_value(g, ship, "applicableIceClassRegulationEdition", edition, ex)
    if omit != "requiredPowerUnder1985Rules":
        add_value(g, ship, "requiredPowerUnder1985Rules", required, ex, "legacyRequired", wrong_unit=(wrong_unit == "requiredPowerUnder1985Rules"))
    if omit != "maximumContinuousRatingPower":
        add_value(g, ship, "maximumContinuousRatingPower", mcr, ex, "mcr", wrong_unit=(wrong_unit == "maximumContinuousRatingPower"))
    return g


def oracle_023(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    cls = obj_value(g, ship, "iceClass")
    edition = obj_value(g, ship, "applicableIceClassRegulationEdition")
    if cls is None or edition is None:
        return False
    applicable = edition == EDITION_1985 and cls in {ICE_CLASSES["IB"], ICE_CLASSES["IC"]}
    if not applicable:
        return True
    required = qty_number(g, ship, "requiredPowerUnder1985Rules")
    mcr = qty_number(g, ship, "maximumContinuousRatingPower")
    if required is None or mcr is None:
        return False
    return mcr + 1e-9 >= max(required, 740.0)


def build_024(cid, stage="1995-01-01", delivery="2000-06-01", assessment="2020-01-01", ice_class="IA", method=None):
    g, ex, ship = new_graph(cid)
    if stage is not None:
        add_value(g, ship, "constructionStageDate", stage, ex)
    if delivery is not None:
        add_value(g, ship, "deliveryDate", delivery, ex)
    if assessment is not None:
        add_value(g, ship, "assessmentDate", assessment, ex)
    if ice_class is not None:
        add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    if method is not None:
        add_value(g, ship, "engineOutputComplianceMethod", method, ex)
    return g


def oracle_024(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    delivery = date_value(g, ship, "deliveryDate")
    assessment = date_value(g, ship, "assessmentDate")
    cls = obj_value(g, ship, "iceClass")
    if None in (stage, delivery, assessment, cls):
        return False
    applicable = (
        stage < date(2003, 9, 1)
        and cls in {ICE_CLASSES["IA Super"], ICE_CLASSES["IA"]}
        and assessment >= date(delivery.year + 20, 1, 1)
    )
    if not applicable:
        return True
    method = obj_value(g, ship, "engineOutputComplianceMethod")
    return method in {
        NLTL.traficom2017Section3Point2Point2Method,
        NLTL.traficom2017Section3Point2Point4Method,
    }


def c1c2_values(bulb, B=25.0, L=150.0, T=9.0):
    f1, f2, f3, f4 = 10.3, 45.8, 2.94, 5.8
    g1, g2, g3 = 1530.0, 170.0, 400.0
    if bulb:
        c1 = f1 * (B * L) / (2 * T / B + 1) + 2.89 * (f2 * B + f3 * L + f4 * B * L)
        c2 = 6.67 * (g1 + g2 * B) + g3 * (1 + 1.2 * T / B) * (B ** 2) / math.sqrt(L)
    else:
        c1 = f1 * (B * L) / (2 * T / B + 1) + 1.84 * (f2 * B + f3 * L + f4 * B * L)
        c2 = 3.52 * (g1 + g2 * B) + g3 * (1 + 1.2 * T / B) * (B ** 2) / math.sqrt(L)
    return c1, c2


def build_025_026(cid, bulb, requirement, ice_class="IA Super", missing=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    add_value(g, ship, "bulbousBowPresent", bulb, ex)
    B, L, T = 25.0, 150.0, 9.0
    c1, c2 = c1c2_values(bulb, B, L, T)
    vals = {
        "coefficientF1": 10.3,
        "coefficientF2": 45.8,
        "coefficientF3": 2.94,
        "coefficientF4": 5.8,
        "coefficientG1": 1530.0,
        "coefficientG2": 170.0,
        "coefficientG3": 400.0,
        "shipBreadth": B,
        "shipLength": L,
        "iceClassDraught": T,
        "brashIceResistanceCoefficientC1": c1,
        "brashIceResistanceCoefficientC2": c2,
    }
    for term, value in vals.items():
        if missing != term:
            add_value(g, ship, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def readiness_025_026(g, expected_bulb):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    cls = obj_value(g, ship, "iceClass")
    bulb = bool_value(g, ship, "bulbousBowPresent")
    if cls is None or bulb is None:
        return False
    applicable = cls == ICE_CLASSES["IA Super"] and bulb is expected_bulb
    if not applicable:
        return True
    required = [
        "coefficientF1", "coefficientF2", "coefficientF3", "coefficientF4",
        "coefficientG1", "coefficientG2", "coefficientG3",
        "shipBreadth", "shipLength", "iceClassDraught",
        "brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2",
    ]
    return all(qty_number(g, ship, t) is not None for t in required)


def oracle_025(g):
    return readiness_025_026(g, False)


def oracle_026(g):
    return readiness_025_026(g, True)


def raw_geometry_term(L, T, B):
    return ((L * T) / (B ** 2)) ** 3


def build_027(cid, raw_target=10.0, result=None, stage="1995-01-01", ice_class="IA", omit=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "constructionStageDate", stage, ex)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    B, T = 25.0, 9.0
    L = (raw_target ** (1.0 / 3.0)) * (B ** 2) / T
    if result is None:
        result = min(max(raw_target, 5.0), 20.0)
    vals = {"shipLength": L, "iceClassDraught": T, "shipBreadth": B, "clampedHullGeometryTerm": result}
    for term, value in vals.items():
        if omit != term:
            add_value(g, ship, term, value, ex, term, wrong_unit=(wrong_unit == term))
    return g


def oracle_027(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    cls = obj_value(g, ship, "iceClass")
    if stage is None or cls is None:
        return False
    applicable = stage < date(2003, 9, 1) and cls in {ICE_CLASSES["IA Super"], ICE_CLASSES["IA"]}
    if not applicable:
        return True
    L = qty_number(g, ship, "shipLength")
    T = qty_number(g, ship, "iceClassDraught")
    B = qty_number(g, ship, "shipBreadth")
    result = qty_number(g, ship, "clampedHullGeometryTerm")
    if None in (L, T, B, result) or B == 0:
        return False
    raw = raw_geometry_term(L, T, B)
    expected = min(max(raw, 5.0), 20.0)
    return close(result, expected, tol=1e-7)


def build_028(cid, route="calculation", result_kind="ke", approval=True, revocation=NLTL.evidenceStateApproved, omit=None, wrong_unit=False):
    g, ex, ship = new_graph(cid)
    if route == "calculation" and omit != "evidence":
        ev = ex.calculationEvidence
        g.add((ev, RDF.type, NLTL.alternativeCalculationEvidence))
    elif route == "model" and omit != "evidence":
        ev = ex.modelEvidence
        g.add((ev, RDF.type, NLTL.modelTestEvidence))

    if omit != "approvalStatus":
        add_value(g, ship, "approvalStatus", approval, ex)
    if omit != "approvalRevocationStatus":
        add_value(g, ship, "approvalRevocationStatus", revocation, ex)

    if omit != "result":
        if result_kind == "ke":
            add_value(g, ship, "engineOutputCoefficientKe", 1.95, ex, "ke", wrong_unit=wrong_unit)
        else:
            add_value(g, ship, "brashIceChannelResistanceRch", 120000.0, ex, "rch", unit_override=str(UNIT.N), wrong_unit=wrong_unit)
    return g


def oracle_028(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    if bool_value(g, ship, "approvalStatus") is not True:
        return False
    rev = obj_value(g, ship, "approvalRevocationStatus")
    if rev is None or rev == NLTL.evidenceStateRevoked:
        return False
    evidence_present = (
        any(True for _ in g.subjects(RDF.type, NLTL.alternativeCalculationEvidence))
        or any(True for _ in g.subjects(RDF.type, NLTL.modelTestEvidence))
    )
    if not evidence_present:
        return False
    ke = qty_number(g, ship, "engineOutputCoefficientKe")
    rch = qty_number(g, ship, "brashIceChannelResistanceRch", str(UNIT.N))
    return ke is not None or rch is not None


# TRF-017
add_case("TRF-017", "P01", "PASS", "Unrestricted propulsion output equals continuously deliverable propulsion machinery output.", build_017("TRF-017-P01", continuous=5000, restriction=False, total=5000))
add_case("TRF-017", "P02", "PASS", "Restricted-output branch uses the technically/regulatorily restricted output.", build_017("TRF-017-P02", continuous=5000, restriction=True, restricted=4200, total=4200))
add_case("TRF-017", "P03", "PASS", "Additional propulsion source is included in total engine output.", build_017("TRF-017-P03", continuous=5000, restriction=False, additional=800, total=5800))
add_case("TRF-017", "P04", "PASS", "Restricted main propulsion plus additional propulsion power are both included.", build_017("TRF-017-P04", continuous=5000, restriction=True, restricted=4200, additional=800, total=5000))
add_case("TRF-017", "F01", "FAIL", "Total omits available additional propulsion power.", build_017("TRF-017-F01", continuous=5000, restriction=False, additional=800, total=5000))
add_case("TRF-017", "F02", "FAIL", "Restricted-output branch incorrectly uses unrestricted continuous output.", build_017("TRF-017-F02", continuous=5000, restriction=True, restricted=4200, total=5000))
add_case("TRF-017", "F03", "FAIL", "Restricted output value is missing while a restriction applies.", build_017("TRF-017-F03", continuous=5000, restriction=True, restricted=None, total=5000))

# TRF-018
add_case("TRF-018", "P01", "PASS", "IA calculated requirement above 1000 kW is met exactly.", build_018("TRF-018-P01", "IA", 1200, 1200))
add_case("TRF-018", "P02", "PASS", "IA uses the 1000 kW floor when calculated requirement is lower.", build_018("TRF-018-P02", "IA", 900, 1000))
add_case("TRF-018", "P03", "PASS", "IA Super uses the 2800 kW floor when calculated requirement is lower.", build_018("TRF-018-P03", "IA Super", 2000, 2800))
add_case("TRF-018", "P04", "PASS", "IB calculated requirement above floor is met.", build_018("TRF-018-P04", "IB", 3478, 3478))
add_case("TRF-018", "P05", "PASS", "IC calculated requirement above floor is met.", build_018("TRF-018-P05", "IC", 2253, 2253))
add_case("TRF-018", "P06", "PASS", "Ice class II is outside section 3.2 engine-output minima.", build_018("TRF-018-P06", "II", 500, 500))
add_case("TRF-018", "F01", "FAIL", "IA MCR is below 1000 kW floor.", build_018("TRF-018-F01", "IA", 900, 999))
add_case("TRF-018", "F02", "FAIL", "IA Super MCR is below 2800 kW floor.", build_018("TRF-018-F02", "IA Super", 2000, 2799))
add_case("TRF-018", "F03", "FAIL", "IB MCR is below calculated required power.", build_018("TRF-018-F03", "IB", 3478, 3477))
add_case("TRF-018", "F04", "FAIL", "Calculated required power is missing for an applicable ice class.", build_018("TRF-018-F04", "IC", 2253, 2253, omit="calculatedRequiredPower"))
add_case("TRF-018", "F05", "FAIL", "MCR power uses the wrong unit.", build_018("TRF-018-F05", "IA", 1200, 1200, wrong_unit="maximumContinuousRatingPower"))

# TRF-020
add_case("TRF-020", "P01", "PASS", "Applicable new IA Super ship has complete UIWL/LIWL power-calculation readiness interface.", build_020("TRF-020-P01"))
add_case("TRF-020", "P02", "PASS", "Applicable new IA ship has complete readiness interface.", build_020("TRF-020-P02", ice_class="IA"))
add_case("TRF-020", "P03", "PASS", "Pre-2003 construction-stage ship is outside the new-ship formula branch.", build_020("TRF-020-P03", stage="2003-08-31", missing="engineOutputCoefficientKe"))
add_case("TRF-020", "P04", "PASS", "Ice class II is outside the section 3.2.2 new-ship branch.", build_020("TRF-020-P04", ice_class="II", missing="engineOutputCoefficientKe"))
for suffix, missing in [
    ("F01", "engineOutputCoefficientKe"),
    ("F02", "brashIceChannelResistanceAtLowerIceWaterline"),
    ("F03", "propellerDiameter"),
    ("F04", "propellerCount"),
    ("F05", "upperIceWaterlineBreadth"),
    ("F06", "minimumRequiredPowerAtLowerIceWaterline"),
    ("F07", "hasUpperIceWaterline"),
]:
    add_case("TRF-020", suffix, "FAIL", f"Applicable readiness graph is missing {missing}.", build_020(f"TRF-020-{suffix}", missing=missing))
add_case("TRF-020", "F08", "FAIL", "UIWL brash-ice resistance is attached to ship instead of UIWL.", build_020("TRF-020-F08", wrong_owner="brashIceChannelResistanceAtUpperIceWaterline"))
add_case("TRF-020", "F09", "FAIL", "Minimum UIWL power result uses the wrong unit.", build_020("TRF-020-F09", wrong_unit="minimumRequiredPowerAtUpperIceWaterline"))

# TRF-022
add_case("TRF-022", "P01", "PASS", "Complete Table-3-2 / geometry readiness interface is present with source-grounded units.", build_022("TRF-022-P01"))
for i, missing in enumerate([
    "bowRakeAtQuarterBreadth", "waterlineAngleAtQuarterBreadth", "shipLength",
    "iceClassDraught", "shipBreadth", "coefficientC3", "coefficientF1",
    "coefficientG3", "flareAngle", "clampedHullGeometryTerm",
], start=1):
    add_case("TRF-022", f"F{i:02d}", "FAIL", f"Required readiness quantity {missing} is missing.", build_022(f"TRF-022-F{i:02d}", missing=missing))
add_case("TRF-022", "F11", "FAIL", "Flare angle uses an invalid unit.", build_022("TRF-022-F11", wrong_unit="flareAngle"))

# TRF-023
add_case("TRF-023", "P01", "PASS", "Applicable 1985-rules IB ship meets its formula-derived required power.", build_023("TRF-023-P01", "IB", EDITION_1985, 900, 900))
add_case("TRF-023", "P02", "PASS", "Applicable IC ship meets the Annex-II 740 kW minimum floor.", build_023("TRF-023-P02", "IC", EDITION_1985, 700, 740))
add_case("TRF-023", "P03", "PASS", "IA ship is outside the IB/IC legacy requirement.", build_023("TRF-023-P03", "IA", EDITION_1985, 900, 500))
add_case("TRF-023", "P04", "PASS", "Non-1985 regulation edition is outside this legacy requirement.", build_023("TRF-023-P04", "IB", EDITION_2002, 900, 500))
add_case("TRF-023", "F01", "FAIL", "Applicable IB ship is below formula-derived required power.", build_023("TRF-023-F01", "IB", EDITION_1985, 900, 899))
add_case("TRF-023", "F02", "FAIL", "Applicable IC ship is below the 740 kW floor.", build_023("TRF-023-F02", "IC", EDITION_1985, 700, 739))
add_case("TRF-023", "F03", "FAIL", "Legacy required power is missing for an applicable ship.", build_023("TRF-023-F03", "IB", EDITION_1985, 900, 900, omit="requiredPowerUnder1985Rules"))
add_case("TRF-023", "F04", "FAIL", "MCR power uses the wrong unit.", build_023("TRF-023-F04", "IB", EDITION_1985, 900, 900, wrong_unit="maximumContinuousRatingPower"))

# TRF-024
add_case("TRF-024", "P01", "PASS", "Applicable IA ship at the 20-year due date uses 2017 section 3.2.2.", build_024("TRF-024-P01", method=NLTL.traficom2017Section3Point2Point2Method))
add_case("TRF-024", "P02", "PASS", "Applicable IA Super ship uses the permitted 2017 section 3.2.4 route.", build_024("TRF-024-P02", ice_class="IA Super", assessment="2025-01-01", method=NLTL.traficom2017Section3Point2Point4Method))
add_case("TRF-024", "P03", "PASS", "Assessment before the 20-year due date does not activate the requirement.", build_024("TRF-024-P03", assessment="2019-12-31", method=None))
add_case("TRF-024", "P04", "PASS", "Post-2003 construction-stage ship is outside the existing-ship branch.", build_024("TRF-024-P04", stage="2003-09-01", method=None))
add_case("TRF-024", "P05", "PASS", "IB ship is outside the IA/IA Super branch.", build_024("TRF-024-P05", ice_class="IB", method=None))
add_case("TRF-024", "F01", "FAIL", "Applicable due IA ship has no accepted 2017 method.", build_024("TRF-024-F01", method=None))
add_case("TRF-024", "F02", "FAIL", "Applicable due ship records an unsupported compliance method.", build_024("TRF-024-F02", method=NLTL.iceClassRegulationEdition2010))
add_case("TRF-024", "F03", "FAIL", "Missing delivery date prevents determination of the 20-year deadline.", build_024("TRF-024-F03", delivery=None, method=NLTL.traficom2017Section3Point2Point2Method))

# TRF-025
add_case("TRF-025", "P01", "PASS", "IA Super ship without bulb has complete C1/C2 readiness interface.", build_025_026("TRF-025-P01", False, "TRF-025"))
add_case("TRF-025", "P02", "PASS", "Bulbous IA Super ship is outside TRF-025 no-bulb branch.", build_025_026("TRF-025-P02", True, "TRF-025", missing="coefficientF1"))
add_case("TRF-025", "P03", "PASS", "IA ship is outside IA Super C1/C2 branch.", build_025_026("TRF-025-P03", False, "TRF-025", ice_class="IA", missing="coefficientF1"))
for i, missing in enumerate(["coefficientF1", "coefficientG3", "shipBreadth", "iceClassDraught", "brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2"], start=1):
    add_case("TRF-025", f"F{i:02d}", "FAIL", f"Applicable no-bulb readiness graph is missing {missing}.", build_025_026(f"TRF-025-F{i:02d}", False, "TRF-025", missing=missing))

# TRF-026
add_case("TRF-026", "P01", "PASS", "IA Super bulbous-bow ship has complete C1/C2 readiness interface.", build_025_026("TRF-026-P01", True, "TRF-026"))
add_case("TRF-026", "P02", "PASS", "Non-bulbous IA Super ship is outside TRF-026 bulb branch.", build_025_026("TRF-026-P02", False, "TRF-026", missing="coefficientF1"))
add_case("TRF-026", "P03", "PASS", "IA ship is outside IA Super bulb C1/C2 branch.", build_025_026("TRF-026-P03", True, "TRF-026", ice_class="IA", missing="coefficientF1"))
for i, missing in enumerate(["coefficientF2", "coefficientG1", "shipLength", "iceClassDraught", "brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2"], start=1):
    add_case("TRF-026", f"F{i:02d}", "FAIL", f"Applicable bulbous-bow readiness graph is missing {missing}.", build_025_026(f"TRF-026-F{i:02d}", True, "TRF-026", missing=missing))

# TRF-027
for suffix, raw in [("P01", 3.0), ("P02", 5.0), ("P03", 10.0), ("P04", 20.0), ("P05", 30.0)]:
    add_case("TRF-027", suffix, "PASS", f"Clamped hull-geometry term correctly handles raw value {raw}.", build_027(f"TRF-027-{suffix}", raw_target=raw))
add_case("TRF-027", "P06", "PASS", "Modern construction stage is outside the existing-ship alternative-coefficient branch.", build_027("TRF-027-P06", raw_target=10.0, stage="2003-09-01", omit="clampedHullGeometryTerm"))
add_case("TRF-027", "P07", "PASS", "IB is outside the IA/IA Super alternative-coefficient branch.", build_027("TRF-027-P07", raw_target=10.0, ice_class="IB", omit="clampedHullGeometryTerm"))
add_case("TRF-027", "F01", "FAIL", "Raw value below five is not clamped to five.", build_027("TRF-027-F01", raw_target=3.0, result=3.0))
add_case("TRF-027", "F02", "FAIL", "Clamped result is missing for an applicable ship.", build_027("TRF-027-F02", raw_target=10.0, omit="clampedHullGeometryTerm"))
add_case("TRF-027", "F03", "FAIL", "Clamped dimensionless result uses the wrong unit.", build_027("TRF-027-F03", raw_target=10.0, wrong_unit="clampedHullGeometryTerm"))

# TRF-028
add_case("TRF-028", "P01", "PASS", "Approved precise-calculation route provides Ke result and alternative-calculation evidence.", build_028("TRF-028-P01", route="calculation", result_kind="ke"))
add_case("TRF-028", "P02", "PASS", "Approved model-test route provides RCH result and model-test evidence.", build_028("TRF-028-P02", route="model", result_kind="rch"))
add_case("TRF-028", "F01", "FAIL", "Approved alternative route has no Ke or RCH result.", build_028("TRF-028-F01", omit="result"))
add_case("TRF-028", "F02", "FAIL", "Alternative result is present but supporting calculation/model-test evidence is missing.", build_028("TRF-028-F02", omit="evidence"))
add_case("TRF-028", "F03", "FAIL", "Alternative route has not been approved.", build_028("TRF-028-F03", approval=False))
add_case("TRF-028", "F04", "FAIL", "Approval has been revoked based on the evidence lifecycle state.", build_028("TRF-028-F04", revocation=NLTL.evidenceStateRevoked))
add_case("TRF-028", "F05", "FAIL", "Approval revocation status is missing.", build_028("TRF-028-F05", omit="approvalRevocationStatus"))
add_case("TRF-028", "F06", "FAIL", "Alternative RCH result uses the wrong unit.", build_028("TRF-028-F06", route="model", result_kind="rch", wrong_unit=True))

assert len(CASE_DEFS) == 95, len(CASE_DEFS)

ORACLES = {
    "TRF-017": oracle_017,
    "TRF-018": oracle_018,
    "TRF-020": oracle_020,
    "TRF-022": oracle_022,
    "TRF-023": oracle_023,
    "TRF-024": oracle_024,
    "TRF-025": oracle_025,
    "TRF-026": oracle_026,
    "TRF-027": oracle_027,
    "TRF-028": oracle_028
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
    manifest_path = ROOT / "manifests" / "traficom_batch_c_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_c_fixture_lock.json"

    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch C manifest does not exist")

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

    lock_path = locks_root / "traficom_batch_c_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch C lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {'TRF-017': '3.1', 'TRF-018': '3.2', 'TRF-020': '3.2.2 / equation (3.1) / Table 3-1', 'TRF-022': '3.2.2 / Table 3-2 / geometry and clamp terms', 'TRF-023': '3.2.3 / Annex II', 'TRF-024': '3.2.4 (20-year retained-class obligation)', 'TRF-025': '3.2.4 (IA Super, no bulb alternative C1/C2)', 'TRF-026': '3.2.4 (IA Super, bulbous-bow alternative C1/C2)', 'TRF-027': '3.2.4 / Table 3-3 / clamped geometry term', 'TRF-028': '3.2.5'}
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

    manifest_path = manifest_root / "traficom_batch_c_manifest.jsonl"
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
        (spec_root / f"{req}_traficom_batch_c.json").write_text(
            json.dumps(spec, indent=2) + "\n"
        )

    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")

    frozen = [manifest_path]
    frozen += [
        spec_root / f"{req}_traficom_batch_c.json"
        for req in REQS
    ]
    for req in REQS:
        frozen += sorted((rdf_root / req).glob("*.ttl"))

    lock = {
        "benchmark": "TRAFICOM Behavioral Benchmark Batch C",
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

    validator = scripts_root / "validate_traficom_batch_c.py"
    shutil.copy2(Path(__file__).resolve(), validator)
    validator.chmod(0o755)

    (ROOT / "README_TRAFICOM_BATCH_C.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch C\n\n"
        f"Requirements: {len(REQS)}\nCases: {len(CASE_DEFS)}\n\n"
        + "\n".join(REQS)
        + "\n\nGenerated SHACL was not inspected during fixture construction.\n"
        + "The batch is frozen with SHA-256 hashes after source-oracle validation.\n\n"
        + "Run:\n\npython3 scripts/validate_traficom_batch_c.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = (
        Path(__file__).name == "validate_traficom_batch_c.py"
        or "--validate-only" in sys.argv
    )
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__ == "__main__":
    main()
