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
BASE = "https://w3id.org/nltl/benchmark/traficom-batch-a/"

REQS = ['TRF-001', 'TRF-002', 'TRF-003', 'TRF-004', 'TRF-005', 'TRF-006', 'TRF-007', 'TRF-009', 'TRF-010']
EXPECTED_MODES = {'TRF-001': 'DIRECT_STATIC', 'TRF-002': 'DIRECT_STATIC', 'TRF-003': 'DIRECT_STATIC', 'TRF-004': 'DIRECT_STATIC', 'TRF-005': 'DIRECT_STATIC', 'TRF-006': 'DIRECT_STATIC', 'TRF-007': 'DIRECT_STATIC', 'TRF-009': 'DIRECT_STATIC', 'TRF-010': 'DIRECT_STATIC'}

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
# TRAFICOM BATCH A — REGULATION-EDITION APPLICABILITY
# ============================================================

def build_edition_case(cid, contract_date=None, stage_date=None, edition=None):
    g, ex, ship = new_graph(cid)
    if contract_date is not None:
        add_value(g, ship, "constructionContractDate", contract_date, ex)
    if stage_date is not None:
        add_value(g, ship, "constructionStageDate", stage_date, ex)
    if edition is not None:
        add_value(g, ship, "applicableIceClassRegulationEdition", edition, ex)
    return g


def edition_oracle(g, lower, upper, target, date_term="constructionContractDate", stage_term=None):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    d = date_value(g, ship, stage_term or date_term)
    edition = obj_value(g, ship, "applicableIceClassRegulationEdition")
    if d is None or edition is None:
        return False
    in_range = d >= lower and (upper is None or d < upper)
    return (edition == target) if in_range else (edition != target)


def oracle_001(g):
    return edition_oracle(g, date(2021, 7, 5), None, EDITION_2021)


def oracle_002(g):
    return edition_oracle(g, date(2019, 1, 1), date(2021, 7, 5), EDITION_2017)


def oracle_003(g):
    return edition_oracle(g, date(2012, 1, 1), date(2019, 1, 1), EDITION_2010)


def oracle_004(g):
    return edition_oracle(g, date(2010, 1, 1), date(2012, 1, 1), EDITION_2008)


def oracle_005(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    contract = date_value(g, ship, "constructionContractDate")
    edition = obj_value(g, ship, "applicableIceClassRegulationEdition")
    if stage is None or contract is None or edition is None:
        return False
    applicable = stage >= date(2003, 9, 1) and contract < date(2010, 1, 1)
    return (edition == EDITION_2002) if applicable else (edition != EDITION_2002)


def build_006(cid, stage_date, owner_request, base_edition, engine_edition):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "constructionStageDate", stage_date, ex)
    add_value(g, ship, "ownerRequested2008EngineOutputRequirements", owner_request, ex)
    add_value(g, ship, "applicableIceClassRegulationEdition", base_edition, ex)
    add_value(g, ship, "engineOutputRegulationEdition", engine_edition, ex)
    add_value(g, ship, "iceClass", ICE_CLASSES["IA"], ex)
    return g


def oracle_006(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    owner_request = bool_value(g, ship, "ownerRequested2008EngineOutputRequirements")
    base_edition = obj_value(g, ship, "applicableIceClassRegulationEdition")
    engine_edition = obj_value(g, ship, "engineOutputRegulationEdition")
    if None in (stage, owner_request, base_edition, engine_edition):
        return False
    cohort = date(1986, 11, 1) <= stage < date(2003, 9, 1)
    if not cohort:
        return base_edition != EDITION_1985
    if base_edition != EDITION_1985:
        return False
    if owner_request:
        return engine_edition == EDITION_2008
    return engine_edition != EDITION_2008


def due_date_from_delivery(delivery):
    return date(delivery.year + 20, 1, 1)


def build_legacy_twenty_year(cid, stage_date, delivery_date, assessment_date, ice_class, method=None):
    g, ex, ship = new_graph(cid)
    if stage_date is not None:
        add_value(g, ship, "constructionStageDate", stage_date, ex)
    if delivery_date is not None:
        add_value(g, ship, "deliveryDate", delivery_date, ex)
    if assessment_date is not None:
        add_value(g, ship, "assessmentDate", assessment_date, ex)
    add_value(g, ship, "iceClass", ICE_CLASSES[ice_class], ex)
    if method is not None:
        add_value(g, ship, "engineOutputComplianceMethod", method, ex)
    return g


def legacy_twenty_year_oracle(g, cohort_test):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    stage = date_value(g, ship, "constructionStageDate")
    delivery = date_value(g, ship, "deliveryDate")
    assessment = date_value(g, ship, "assessmentDate")
    ice_class = obj_value(g, ship, "iceClass")
    if stage is None or delivery is None or assessment is None or ice_class is None:
        return False
    applicable = (
        cohort_test(stage)
        and ice_class in {ICE_CLASSES["IA Super"], ICE_CLASSES["IA"]}
        and assessment >= due_date_from_delivery(delivery)
    )
    if not applicable:
        return True
    method = obj_value(g, ship, "engineOutputComplianceMethod")
    return method in {
        NLTL.traficom2017Section3Point2Point2Method,
        NLTL.traficom2017Section3Point2Point4Method,
    }


def oracle_007(g):
    return legacy_twenty_year_oracle(
        g,
        lambda stage: date(1986, 11, 1) <= stage < date(2003, 9, 1),
    )


def oracle_009(g):
    return legacy_twenty_year_oracle(
        g,
        lambda stage: stage < date(1986, 11, 1),
    )


def build_010(cid, ice_class=None):
    g, ex, ship = new_graph(cid)
    if ice_class is not None:
        value = ICE_CLASSES[ice_class] if ice_class in ICE_CLASSES else NLTL[ice_class]
        g.add((ship, NLTL.iceClass, value))
    return g


def oracle_010(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    v = one(g, ship, NLTL.iceClass)
    return v in set(ICE_CLASSES.values())


# TRF-001
add_case("TRF-001", "P01", "PASS", "Construction contract date equals the 2021 applicability cutoff and edition 2021 is selected.", build_edition_case("TRF-001-P01", "2021-07-05", edition=EDITION_2021))
add_case("TRF-001", "P02", "PASS", "Post-cutoff ship uses the 2021 edition.", build_edition_case("TRF-001-P02", "2024-01-01", edition=EDITION_2021))
add_case("TRF-001", "P03", "PASS", "Pre-cutoff ship does not claim the 2021 edition.", build_edition_case("TRF-001-P03", "2020-01-01", edition=EDITION_2017))
add_case("TRF-001", "F01", "FAIL", "Post-cutoff ship incorrectly claims the 2017 edition.", build_edition_case("TRF-001-F01", "2022-01-01", edition=EDITION_2017))
add_case("TRF-001", "F02", "FAIL", "Applicability cannot be evaluated because constructionContractDate is missing.", build_edition_case("TRF-001-F02", edition=EDITION_2021))

# TRF-002
add_case("TRF-002", "P01", "PASS", "Date inside the 2019-to-2021 range selects the 2017 edition.", build_edition_case("TRF-002-P01", "2020-06-01", edition=EDITION_2017))
add_case("TRF-002", "P02", "PASS", "Lower boundary 2019-01-01 selects the 2017 edition.", build_edition_case("TRF-002-P02", "2019-01-01", edition=EDITION_2017))
add_case("TRF-002", "P03", "PASS", "Date before the frozen R13 range does not claim the 2017 edition.", build_edition_case("TRF-002-P03", "2018-06-01", edition=EDITION_2010))
add_case("TRF-002", "P04", "PASS", "At the 2021 cutoff the 2017 edition is no longer selected.", build_edition_case("TRF-002-P04", "2021-07-05", edition=EDITION_2021))
add_case("TRF-002", "F01", "FAIL", "Inside-range ship claims the wrong edition.", build_edition_case("TRF-002-F01", "2020-06-01", edition=EDITION_2010))
add_case("TRF-002", "F02", "FAIL", "A pre-range date incorrectly claims the 2017 edition under the frozen R13 contract.", build_edition_case("TRF-002-F02", "2018-06-01", edition=EDITION_2017))
add_case("TRF-002", "F03", "FAIL", "A date at the 2021 cutoff incorrectly continues to claim the 2017 edition.", build_edition_case("TRF-002-F03", "2021-07-05", edition=EDITION_2017))

# TRF-003
add_case("TRF-003", "P01", "PASS", "Date inside the 2012-to-2019 range selects the 2010 edition.", build_edition_case("TRF-003-P01", "2015-01-01", edition=EDITION_2010))
add_case("TRF-003", "P02", "PASS", "Lower boundary 2012-01-01 selects the 2010 edition.", build_edition_case("TRF-003-P02", "2012-01-01", edition=EDITION_2010))
add_case("TRF-003", "P03", "PASS", "Pre-range date selects the earlier edition.", build_edition_case("TRF-003-P03", "2011-06-01", edition=EDITION_2008))
add_case("TRF-003", "P04", "PASS", "At 2019-01-01 the later edition is selected.", build_edition_case("TRF-003-P04", "2019-01-01", edition=EDITION_2017))
add_case("TRF-003", "F01", "FAIL", "Inside-range date claims the wrong edition.", build_edition_case("TRF-003-F01", "2015-01-01", edition=EDITION_2017))
add_case("TRF-003", "F02", "FAIL", "Pre-range date incorrectly claims the 2010 edition.", build_edition_case("TRF-003-F02", "2011-06-01", edition=EDITION_2010))
add_case("TRF-003", "F03", "FAIL", "At the upper boundary the 2010 edition is incorrectly retained.", build_edition_case("TRF-003-F03", "2019-01-01", edition=EDITION_2010))

# TRF-004
add_case("TRF-004", "P01", "PASS", "Date inside the 2010-to-2012 range selects the 2008 edition.", build_edition_case("TRF-004-P01", "2011-01-01", edition=EDITION_2008))
add_case("TRF-004", "P02", "PASS", "Lower boundary 2010-01-01 selects the 2008 edition.", build_edition_case("TRF-004-P02", "2010-01-01", edition=EDITION_2008))
add_case("TRF-004", "P03", "PASS", "Pre-range date does not claim the 2008 edition.", build_edition_case("TRF-004-P03", "2009-12-31", edition=EDITION_2002))
add_case("TRF-004", "P04", "PASS", "At 2012-01-01 the 2010 edition is selected.", build_edition_case("TRF-004-P04", "2012-01-01", edition=EDITION_2010))
add_case("TRF-004", "F01", "FAIL", "Inside-range ship claims the wrong edition.", build_edition_case("TRF-004-F01", "2011-01-01", edition=EDITION_2010))
add_case("TRF-004", "F02", "FAIL", "Pre-range date incorrectly claims the 2008 edition.", build_edition_case("TRF-004-F02", "2009-12-31", edition=EDITION_2008))
add_case("TRF-004", "F03", "FAIL", "Upper-boundary date incorrectly continues to claim the 2008 edition.", build_edition_case("TRF-004-F03", "2012-01-01", edition=EDITION_2008))

# TRF-005
add_case("TRF-005", "P01", "PASS", "Applicable construction-stage cohort and pre-2010 contract use the 2002 edition.", build_edition_case("TRF-005-P01", "2009-01-01", "2003-09-01", EDITION_2002))
add_case("TRF-005", "P02", "PASS", "Later construction stage with pre-2010 contract remains in the 2002 edition cohort.", build_edition_case("TRF-005-P02", "2008-01-01", "2005-01-01", EDITION_2002))
add_case("TRF-005", "P03", "PASS", "Earlier construction stage does not claim the 2002 edition.", build_edition_case("TRF-005-P03", "2008-01-01", "2003-08-31", EDITION_1985))
add_case("TRF-005", "P04", "PASS", "Contract at 2010-01-01 is outside the 2002-edition cohort.", build_edition_case("TRF-005-P04", "2010-01-01", "2005-01-01", EDITION_2008))
add_case("TRF-005", "F01", "FAIL", "Applicable cohort claims the wrong edition.", build_edition_case("TRF-005-F01", "2009-01-01", "2005-01-01", EDITION_2008))
add_case("TRF-005", "F02", "FAIL", "Pre-2003 construction stage incorrectly claims the 2002 edition.", build_edition_case("TRF-005-F02", "2008-01-01", "2003-08-31", EDITION_2002))
add_case("TRF-005", "F03", "FAIL", "Post-cohort contract incorrectly claims the 2002 edition.", build_edition_case("TRF-005-F03", "2010-01-01", "2005-01-01", EDITION_2002))

# TRF-006
add_case("TRF-006", "P01", "PASS", "1985-rules cohort without owner request keeps 1985 as base and engine-output edition.", build_006("TRF-006-P01", "1995-01-01", False, EDITION_1985, EDITION_1985))
add_case("TRF-006", "P02", "PASS", "1985-rules cohort with owner request keeps 1985 as base while using 2008 for engine output.", build_006("TRF-006-P02", "1995-01-01", True, EDITION_1985, EDITION_2008))
add_case("TRF-006", "P03", "PASS", "Lower construction-stage boundary belongs to the 1985 cohort.", build_006("TRF-006-P03", "1986-11-01", False, EDITION_1985, EDITION_1985))
add_case("TRF-006", "P04", "PASS", "Stage at 2003-09-01 is outside the 1985 cohort.", build_006("TRF-006-P04", "2003-09-01", False, EDITION_2002, EDITION_2002))
add_case("TRF-006", "F01", "FAIL", "Owner request is true but engine output does not use the permitted 2008 edition.", build_006("TRF-006-F01", "1995-01-01", True, EDITION_1985, EDITION_1985))
add_case("TRF-006", "F02", "FAIL", "Owner request is false but engine output incorrectly uses the 2008 edition.", build_006("TRF-006-F02", "1995-01-01", False, EDITION_1985, EDITION_2008))
add_case("TRF-006", "F03", "FAIL", "Applicable cohort does not retain the 1985 base regulation edition.", build_006("TRF-006-F03", "1995-01-01", True, EDITION_2008, EDITION_2008))
add_case("TRF-006", "F04", "FAIL", "Outside-cohort ship incorrectly claims the 1985 base edition.", build_006("TRF-006-F04", "2003-09-01", False, EDITION_1985, EDITION_1985))

# TRF-007
add_case("TRF-007", "P01", "PASS", "Applicable IA ship satisfies the 20-year obligation via 2017 section 3.2.2.", build_legacy_twenty_year("TRF-007-P01", "1995-01-01", "2000-06-01", "2020-01-01", "IA", NLTL.traficom2017Section3Point2Point2Method))
add_case("TRF-007", "P02", "PASS", "Applicable IA Super ship satisfies the obligation via 2017 section 3.2.4.", build_legacy_twenty_year("TRF-007-P02", "1995-01-01", "2000-06-01", "2025-01-01", "IA Super", NLTL.traficom2017Section3Point2Point4Method))
add_case("TRF-007", "P03", "PASS", "Assessment before the 20-year due date does not yet activate the method obligation.", build_legacy_twenty_year("TRF-007-P03", "1995-01-01", "2000-06-01", "2019-12-31", "IA", None))
add_case("TRF-007", "P04", "PASS", "Ice class IB is outside the IA/IA Super obligation.", build_legacy_twenty_year("TRF-007-P04", "1995-01-01", "2000-06-01", "2025-01-01", "IB", None))
add_case("TRF-007", "P05", "PASS", "Stage at 2003-09-01 is outside the section-1.6 legacy cohort.", build_legacy_twenty_year("TRF-007-P05", "2003-09-01", "2000-06-01", "2025-01-01", "IA", None))
add_case("TRF-007", "F01", "FAIL", "Applicable and due IA ship has no accepted 2017 compliance method.", build_legacy_twenty_year("TRF-007-F01", "1995-01-01", "2000-06-01", "2020-01-01", "IA", None))
add_case("TRF-007", "F02", "FAIL", "Applicable and due ship records an unsupported compliance method.", build_legacy_twenty_year("TRF-007-F02", "1995-01-01", "2000-06-01", "2021-01-01", "IA Super", NLTL.iceClassRegulationEdition2010))
add_case("TRF-007", "F03", "FAIL", "Missing assessment date prevents the time-dependent obligation from being evaluated.", build_legacy_twenty_year("TRF-007-F03", "1995-01-01", "2000-06-01", None, "IA", NLTL.traficom2017Section3Point2Point2Method))

# TRF-009
add_case("TRF-009", "P01", "PASS", "Pre-1986 IA ship satisfies the 20-year obligation via section 3.2.2.", build_legacy_twenty_year("TRF-009-P01", "1980-01-01", "1990-06-01", "2010-01-01", "IA", NLTL.traficom2017Section3Point2Point2Method))
add_case("TRF-009", "P02", "PASS", "Pre-1986 IA Super ship satisfies the obligation via section 3.2.4.", build_legacy_twenty_year("TRF-009-P02", "1980-01-01", "1990-06-01", "2015-01-01", "IA Super", NLTL.traficom2017Section3Point2Point4Method))
add_case("TRF-009", "P03", "PASS", "Assessment before the due date is not yet subject to the 20-year method obligation.", build_legacy_twenty_year("TRF-009-P03", "1980-01-01", "1990-06-01", "2009-12-31", "IA", None))
add_case("TRF-009", "P04", "PASS", "IB is outside the IA/IA Super legacy method obligation.", build_legacy_twenty_year("TRF-009-P04", "1980-01-01", "1990-06-01", "2015-01-01", "IB", None))
add_case("TRF-009", "P05", "PASS", "Stage at the 1986-11-01 boundary belongs to the later section-1.6 cohort and is outside TRF-009.", build_legacy_twenty_year("TRF-009-P05", "1986-11-01", "1990-06-01", "2015-01-01", "IA", None))
add_case("TRF-009", "F01", "FAIL", "Applicable and due pre-1986 IA ship has no accepted method.", build_legacy_twenty_year("TRF-009-F01", "1980-01-01", "1990-06-01", "2010-01-01", "IA", None))
add_case("TRF-009", "F02", "FAIL", "Applicable and due pre-1986 ship records an unsupported method.", build_legacy_twenty_year("TRF-009-F02", "1980-01-01", "1990-06-01", "2011-01-01", "IA Super", NLTL.iceClassRegulationEdition2010))
add_case("TRF-009", "F03", "FAIL", "Missing delivery date prevents calculation of the 20-year due date.", build_legacy_twenty_year("TRF-009-F03", "1980-01-01", None, "2015-01-01", "IA", NLTL.traficom2017Section3Point2Point2Method))

# TRF-010
for i, cls in enumerate(["IA Super", "IA", "IB", "IC", "II", "III"], start=1):
    add_case("TRF-010", f"P{i:02d}", "PASS", f"Ice class {cls} is one of the six source-permitted classes.", build_010(f"TRF-010-P{i:02d}", cls))
add_case("TRF-010", "F01", "FAIL", "An unlisted ice-class value is not permitted.", build_010("TRF-010-F01", "polarClassPc6"))
add_case("TRF-010", "F02", "FAIL", "Ice class assignment is missing.", build_010("TRF-010-F02", None))

assert len(CASE_DEFS) == 65, len(CASE_DEFS)

ORACLES = {
    "TRF-001": oracle_001,
    "TRF-002": oracle_002,
    "TRF-003": oracle_003,
    "TRF-004": oracle_004,
    "TRF-005": oracle_005,
    "TRF-006": oracle_006,
    "TRF-007": oracle_007,
    "TRF-009": oracle_009,
    "TRF-010": oracle_010
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
    manifest_path = ROOT / "manifests" / "traficom_batch_a_manifest.jsonl"
    lock_path = ROOT / "locks" / "traficom_batch_a_fixture_lock.json"

    if not manifest_path.exists():
        raise SystemExit("TRAFICOM Batch A manifest does not exist")

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

    lock_path = locks_root / "traficom_batch_a_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("TRAFICOM Batch A lock already exists. Refusing to overwrite frozen fixtures.")

    clauses = {'TRF-001': '1.1', 'TRF-002': '1.2', 'TRF-003': '1.3', 'TRF-004': '1.4', 'TRF-005': '1.5', 'TRF-006': '1.6', 'TRF-007': '1.6 (20-year IA/IA Super engine-output obligation)', 'TRF-009': '1.7 (20-year IA/IA Super engine-output obligation)', 'TRF-010': '1.8'}
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

    manifest_path = manifest_root / "traficom_batch_a_manifest.jsonl"
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
        (spec_root / f"{req}_traficom_batch_a.json").write_text(
            json.dumps(spec, indent=2) + "\n"
        )

    print("Pre-freeze validation")
    if not validate_existing(False):
        raise SystemExit("Pre-freeze validation failed. No lock written.")

    frozen = [manifest_path]
    frozen += [
        spec_root / f"{req}_traficom_batch_a.json"
        for req in REQS
    ]
    for req in REQS:
        frozen += sorted((rdf_root / req).glob("*.ttl"))

    lock = {
        "benchmark": "TRAFICOM Behavioral Benchmark Batch A",
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

    validator = scripts_root / "validate_traficom_batch_a.py"
    shutil.copy2(Path(__file__).resolve(), validator)
    validator.chmod(0o755)

    (ROOT / "README_TRAFICOM_BATCH_A.md").write_text(
        "# TRAFICOM Behavioral Benchmark Batch A\n\n"
        f"Requirements: {len(REQS)}\nCases: {len(CASE_DEFS)}\n\n"
        + "\n".join(REQS)
        + "\n\nGenerated SHACL was not inspected during fixture construction.\n"
        + "The batch is frozen with SHA-256 hashes after source-oracle validation.\n\n"
        + "Run:\n\npython3 scripts/validate_traficom_batch_a.py\n"
    )

    print("\nFrozen validation")
    if not validate_existing(True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = (
        Path(__file__).name == "validate_traficom_batch_a.py"
        or "--validate-only" in sys.argv
    )
    if validation_mode:
        raise SystemExit(0 if validate_existing(True) else 1)
    generate()


if __name__ == "__main__":
    main()
