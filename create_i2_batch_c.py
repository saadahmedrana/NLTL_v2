from pathlib import Path
import json
import hashlib
import shutil
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD


# ============================================================
# LOCATE REPOSITORY
# ============================================================

def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    candidates += list(Path(__file__).resolve().parents)

    for c in candidates:
        if (
            c
            / "MVP"
            / "BENCHMARK_VOCABULARY"
            / "FINAL_LOCK_R13"
            / "requirement_term_index.json"
        ).exists():
            return c

    raise RuntimeError("Could not locate NLTL_v2 repository root")


REPO = find_repo()

PIPELINE = (
    REPO
    / "MVP"
    / "SHACL_GENERATION_PIPELINE"
)

ROOT = (
    PIPELINE
    / "evaluation"
    / "BEHAVIORAL_RDF_R13"
)

R13 = (
    REPO
    / "MVP"
    / "BENCHMARK_VOCABULARY"
    / "FINAL_LOCK_R13"
)

INDEX_PATH = R13 / "requirement_term_index.json"
REGISTRY_PATH = R13 / "registry" / "term_registry.json"

INDEX = json.loads(INDEX_PATH.read_text())
REGISTRY = json.loads(REGISTRY_PATH.read_text())

REG = {x["localName"]: x for x in REGISTRY}
CONTRACTS = INDEX["dependencyContracts"]

NLTL = Namespace("https://w3id.org/nltl/vocab#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")

BASE = "https://w3id.org/nltl/benchmark/i2-batch-c/"

REQS = [
    "I2-006",
    "I2-008",
    "I2-060",
    "I2-062",
    "I2-064",
    "I2-065",
]

EXPECTED_MODES = {
    "I2-006": "DIRECT_STATIC",
    "I2-008": "COMPLEX_READINESS",
    "I2-060": "DIRECT_STATIC",
    "I2-062": "COMPLEX_READINESS",
    "I2-064": "COMPLEX_READINESS",
    "I2-065": "COMPLEX_READINESS",
}

for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert (
        CONTRACTS[req]["verificationMode"]
        == EXPECTED_MODES[req]
    )

for req in ["I2-008", "I2-062", "I2-064", "I2-065"]:
    assert CONTRACTS[req].get("formulaExecutionRequired") is False


# Infrastructure concepts that are valid members of frozen R13
# even when not represented as ordinary term_registry rows.
INFRA = {
    "ship",
    "polarClassValue",
    "bowSubregionCalculationCase",
    "structuralMember",
    "hullStructure",
    "cutout",
    "grillageSystem",
    "webFrame",
    "loadCarryingStringer",
    "calculationCase",
    "structuralMemberWeb",
    "structuralMemberFlange",
    "evidenceArtifact",
}

KNOWN_NLTL = set(REG.keys()) | INFRA


# ============================================================
# RDF HELPERS
# ============================================================

def new_graph(case_id):
    g = Graph()
    ex = Namespace(BASE + case_id + "/")

    g.bind("ex", ex)
    g.bind("nltl", NLTL)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("xsd", XSD)

    ship = ex.ship
    g.add((ship, RDF.type, NLTL.ship))

    return g, ex, ship


def datatype_for(term):
    row = REG[term]
    dt = row.get("datatype", "")

    if dt == "xsd:boolean":
        return XSD.boolean
    if dt == "xsd:string":
        return XSD.string
    if dt == "xsd:integer":
        return XSD.integer
    if dt == "xsd:decimal":
        return XSD.decimal
    if dt == "xsd:date":
        return XSD.date

    return None


def add_value(
    g,
    subject,
    term,
    value,
    ex,
    name=None,
    wrong_unit=False,
):
    if term not in REG:
        raise RuntimeError(f"Unknown R13 term: {term}")

    row = REG[term]
    kind = row["kind"]

    if kind == "QuantityProperty":
        unit = row.get("unitIri", "")

        if not unit:
            raise RuntimeError(
                f"{term} is QuantityProperty but has no frozen unit"
            )

        q = ex[name or (term + "Value")]

        g.add((q, RDF.type, QUDT.QuantityValue))
        g.add(
            (
                q,
                QUDT.numericValue,
                Literal(str(value), datatype=XSD.decimal),
            )
        )

        u = URIRef(unit)

        if wrong_unit:
            alt = UNIT.UNITLESS
            if alt == u:
                alt = UNIT.M
            u = alt

        g.add((q, QUDT.unit, u))
        g.add((subject, NLTL[term], q))
        return

    if kind == "DatatypeProperty":
        dt = datatype_for(term)

        if dt is None:
            raise RuntimeError(
                f"No supported datatype mapping for {term}"
            )

        g.add(
            (
                subject,
                NLTL[term],
                Literal(value, datatype=dt),
            )
        )
        return

    if kind == "ObjectProperty":
        if not isinstance(value, URIRef):
            raise RuntimeError(
                f"{term} requires URIRef object"
            )

        g.add((subject, NLTL[term], value))
        return

    raise RuntimeError(
        f"add_value cannot use {kind} term {term}"
    )


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


def qty_valid(g, s, term):
    if term not in REG:
        return False

    expected = REG[term].get("unitIri", "")

    if not expected:
        return False

    vals = list(g.objects(s, NLTL[term]))

    if len(vals) != 1:
        return False

    q = vals[0]

    if (q, RDF.type, QUDT.QuantityValue) not in g:
        return False

    nums = list(g.objects(q, QUDT.numericValue))
    units = list(g.objects(q, QUDT.unit))

    return (
        len(nums) == 1
        and len(units) == 1
        and str(units[0]) == expected
    )


# ============================================================
# CASE BUILDERS
# ============================================================

def build_006(
    cid,
    intent,
    basis=None,
    requirement_set=None,
):
    g, ex, ship = new_graph(cid)

    add_value(
        g,
        ship,
        "asternIceOperationIntent",
        intent,
        ex,
    )

    if basis is not None:
        add_value(
            g,
            ship,
            "aftSectionDesignBasis",
            basis,
            ex,
        )

    if requirement_set is not None:
        add_value(
            g,
            ship,
            "hullAreaRequirementSet",
            requirement_set,
            ex,
        )

    return g


def build_008(
    cid,
    missing=None,
    wrong_owner=None,
    omit_case_relation=False,
):
    g, ex, ship = new_graph(cid)

    # I2-008 requires a Polar Class ship but does not require
    # a particular PC number for the Bow-area readiness case.
    pc = ex.polarClass
    g.add((pc, RDF.type, NLTL.polarClassValue))
    g.add((ship, NLTL.polarClass, pc))

    case = ex.bowCase

    g.add(
        (
            case,
            RDF.type,
            NLTL.bowSubregionCalculationCase,
        )
    )

    if not omit_case_relation:
        g.add(
            (
                ship,
                NLTL.hasBowSubregionCalculationCase,
                case,
            )
        )

    fields = [
        ("bowShapeCoefficient", 0.6),
        ("totalGlancingImpactForce", 5.0),
        ("glancingImpactLineLoad", 1000.0),
        ("glancingImpactPressure", 2.0),
    ]

    for term, value in fields:
        if term == missing:
            continue

        owner = ship if term == wrong_owner else case

        add_value(
            g,
            owner,
            term,
            value,
            ex,
            term,
        )

    return g


def build_060(
    cid,
    in_way,
    instability=None,
    stiffening=None,
    omit_cutout=False,
    wrong_owner=None,
):
    g, ex, ship = new_graph(cid)

    member = ex.member
    cutout = ex.cutout

    g.add(
        (
            member,
            RDF.type,
            NLTL.structuralMember,
        )
    )

    g.add(
        (
            ship,
            NLTL.hasStructuralMember,
            member,
        )
    )

    owner = (
        ship
        if wrong_owner == "memberInWayOfCutout"
        else member
    )

    add_value(
        g,
        owner,
        "memberInWayOfCutout",
        in_way,
        ex,
    )

    if not omit_cutout:
        g.add((cutout, RDF.type, NLTL.cutout))
        g.add((member, NLTL.hasCutout, cutout))

    if instability is not None:
        add_value(
            g,
            member,
            "memberInstability",
            instability,
            ex,
        )

    if stiffening is not None:
        add_value(
            g,
            member,
            "stiffeningNecessary",
            stiffening,
            ex,
        )

    return g


def build_062(
    cid,
    member_type,
    in_grillage,
    direct=None,
    wrong_owner=False,
):
    g, ex, ship = new_graph(cid)

    member = ex.member
    grillage = ex.grillage

    g.add(
        (
            member,
            RDF.type,
            NLTL[member_type],
        )
    )

    g.add(
        (
            member,
            RDF.type,
            NLTL.structuralMember,
        )
    )

    g.add(
        (
            ship,
            NLTL.hasStructuralMember,
            member,
        )
    )

    if in_grillage:
        g.add(
            (
                grillage,
                RDF.type,
                NLTL.grillageSystem,
            )
        )

        g.add(
            (
                member,
                NLTL.partOfGrillageSystem,
                grillage,
            )
        )

    if direct is not None:
        add_value(
            g,
            ship if wrong_owner else member,
            "directCalculationUsed",
            direct,
            ex,
        )

    return g


def build_064(
    cid,
    method="linear",
    missing=None,
    buckling=True,
    wrong_owner=None,
):
    g, ex, ship = new_graph(cid)

    calc = ex.calculation
    member = ex.member
    web = ex.web
    flange = ex.flange

    g.add(
        (
            calc,
            RDF.type,
            NLTL.calculationCase,
        )
    )

    g.add(
        (
            ship,
            NLTL.hasCalculationCase,
            calc,
        )
    )

    if method is not None:
        controlled = (
            NLTL.linearCalculationMethodValue
            if method == "linear"
            else NLTL.nonlinearCalculationMethodValue
        )

        g.add(
            (
                calc,
                NLTL.calculationMethod,
                controlled,
            )
        )

    # Nonlinear case is a deliberate non-applicable case.
    if method != "linear":
        return g

    g.add(
        (
            member,
            RDF.type,
            NLTL.structuralMember,
        )
    )
    g.add((member, RDF.type, NLTL.hullStructure))

    g.add(
        (
            ship,
            NLTL.hasStructuralMember,
            member,
        )
    )

    if missing != "web":
        g.add(
            (
                web,
                RDF.type,
                NLTL.structuralMemberWeb,
            )
        )
        g.add(
            (
                member,
                NLTL.hasStructuralMemberWeb,
                web,
            )
        )

    if missing != "flange":
        g.add(
            (
                flange,
                RDF.type,
                NLTL.structuralMemberFlange,
            )
        )
        g.add(
            (
                member,
                NLTL.hasStructuralMemberFlange,
                flange,
            )
        )

    if missing != "bucklingCriteriaSatisfied":
        add_value(
            g,
            member,
            "bucklingCriteriaSatisfied",
            buckling,
            ex,
        )

    if missing != "yieldStrength":
        add_value(
            g,
            member,
            "yieldStrength",
            235.0,
            ex,
            "yieldStrength",
        )

    if missing != "nominalShearStress":
        add_value(
            g,
            ship
            if wrong_owner == "nominalShearStress"
            else web,
            "nominalShearStress",
            100.0,
            ex,
            "nominalShearStress",
        )

    if missing != "nominalFlangeVonMisesStress":
        add_value(
            g,
            ship
            if wrong_owner
            == "nominalFlangeVonMisesStress"
            else flange,
            "nominalFlangeVonMisesStress",
            200.0,
            ex,
            "nominalFlangeVonMisesStress",
        )

    return g


def build_065(
    cid,
    method="nonlinear",
    missing=None,
    assessment=True,
    wrong_owner=None,
):
    g, ex, ship = new_graph(cid)

    calc = ex.calculation

    g.add(
        (
            calc,
            RDF.type,
            NLTL.calculationCase,
        )
    )

    g.add(
        (
            ship,
            NLTL.hasCalculationCase,
            calc,
        )
    )

    controlled = (
        NLTL.nonlinearCalculationMethodValue
        if method == "nonlinear"
        else NLTL.linearCalculationMethodValue
    )

    g.add(
        (
            calc,
            NLTL.calculationMethod,
            controlled,
        )
    )

    # Linear calculation is outside I2-065 applicability.
    if method != "nonlinear":
        return g

    values = [
        ("fractureMargin", 1.2),
        ("majorBucklingMargin", 1.2),
        ("permanentLateralDeformation", 0.002),
        ("permanentOutOfPlaneDeformation", 0.002),
        ("relevantStructuralDimension", 1.0),
        ("yieldingMargin", 1.2),
    ]

    for term, value in values:
        if term == missing:
            continue

        add_value(
            g,
            calc,
            term,
            value,
            ex,
            term,
        )

    if missing != "minorPermanentDeformationAssessmentSatisfied":
        add_value(
            g,
            calc,
            "minorPermanentDeformationAssessmentSatisfied",
            assessment,
            ex,
        )

    if missing != "nonlinearAnalysisAcceptanceEvidence":
        evidence = ex.evidence

        g.add(
            (
                evidence,
                RDF.type,
                NLTL.evidenceArtifact,
            )
        )

        owner = (
            ship
            if wrong_owner
            == "nonlinearAnalysisAcceptanceEvidence"
            else calc
        )

        g.add(
            (
                owner,
                NLTL.nonlinearAnalysisAcceptanceEvidence,
                evidence,
            )
        )

    return g


# ============================================================
# ORACLES
# ============================================================

def oracle_006(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    intent = bool_value(
        g,
        ship,
        "asternIceOperationIntent",
    )

    if intent is None:
        return False

    if not intent:
        return True

    return (
        string_value(
            g,
            ship,
            "aftSectionDesignBasis",
        )
        == "Bow and Bow Intermediate"
        and string_value(
            g,
            ship,
            "hullAreaRequirementSet",
        )
        == "Bow and Bow Intermediate hull area requirements"
    )


def oracle_008(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    if one(g, ship, NLTL.polarClass) is None:
        return False

    cases = list(
        g.objects(
            ship,
            NLTL.hasBowSubregionCalculationCase,
        )
    )

    if not cases:
        return False

    required = [
        "bowShapeCoefficient",
        "totalGlancingImpactForce",
        "glancingImpactLineLoad",
        "glancingImpactPressure",
    ]

    for c in cases:
        if not all(
            qty_valid(g, c, t)
            for t in required
        ):
            return False

    return True


def oracle_060(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    members = list(
        g.objects(
            ship,
            NLTL.hasStructuralMember,
        )
    )

    if not members:
        return False

    for m in members:
        in_way = bool_value(
            g,
            m,
            "memberInWayOfCutout",
        )

        # Explicit status is required by this frozen oracle.
        if in_way is None:
            return False

        if not in_way:
            continue

        if one(g, m, NLTL.hasCutout) is None:
            return False

        instability = bool_value(
            g,
            m,
            "memberInstability",
        )

        stiffening = bool_value(
            g,
            m,
            "stiffeningNecessary",
        )

        if instability is not False:
            return False

        if stiffening is None:
            return False

    return True


def oracle_062(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    members = list(
        g.objects(
            ship,
            NLTL.hasStructuralMember,
        )
    )

    if not members:
        return False

    for m in members:
        relevant_type = (
            (m, RDF.type, NLTL.webFrame) in g
            or
            (m, RDF.type, NLTL.loadCarryingStringer) in g
        )

        if not relevant_type:
            continue

        in_grillage = (
            one(
                g,
                m,
                NLTL.partOfGrillageSystem,
            )
            is not None
        )

        if not in_grillage:
            continue

        if bool_value(
            g,
            m,
            "directCalculationUsed",
        ) is not True:
            return False

    return True


def oracle_064(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    cases = list(
        g.objects(
            ship,
            NLTL.hasCalculationCase,
        )
    )

    if not cases:
        return False

    for calc in cases:
        method = one(
            g,
            calc,
            NLTL.calculationMethod,
        )

        # R13 selector policy says missing method is violation.
        if method is None:
            return False

        if method != NLTL.linearCalculationMethodValue:
            continue

        members = list(
            g.objects(
                ship,
                NLTL.hasStructuralMember,
            )
        )

        if not members:
            return False

        for m in members:
            if bool_value(
                g,
                m,
                "bucklingCriteriaSatisfied",
            ) is not True:
                return False

            if not qty_valid(
                g,
                m,
                "yieldStrength",
            ):
                return False

            web = one(
                g,
                m,
                NLTL.hasStructuralMemberWeb,
            )

            flange = one(
                g,
                m,
                NLTL.hasStructuralMemberFlange,
            )

            if web is None or flange is None:
                return False

            if not qty_valid(
                g,
                web,
                "nominalShearStress",
            ):
                return False

            if not qty_valid(
                g,
                flange,
                "nominalFlangeVonMisesStress",
            ):
                return False

    return True


def oracle_065(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    cases = list(
        g.objects(
            ship,
            NLTL.hasCalculationCase,
        )
    )

    if not cases:
        return False

    for calc in cases:
        method = one(
            g,
            calc,
            NLTL.calculationMethod,
        )

        if method is None:
            return False

        if method != NLTL.nonlinearCalculationMethodValue:
            continue

        for term in [
            "fractureMargin",
            "majorBucklingMargin",
            "permanentLateralDeformation",
            "permanentOutOfPlaneDeformation",
            "relevantStructuralDimension",
            "yieldingMargin",
        ]:
            if not qty_valid(
                g,
                calc,
                term,
            ):
                return False

        if bool_value(
            g,
            calc,
            "minorPermanentDeformationAssessmentSatisfied",
        ) is not True:
            return False

        if one(
            g,
            calc,
            NLTL.nonlinearAnalysisAcceptanceEvidence,
        ) is None:
            return False

    return True


ORACLES = {
    "I2-006": oracle_006,
    "I2-008": oracle_008,
    "I2-060": oracle_060,
    "I2-062": oracle_062,
    "I2-064": oracle_064,
    "I2-065": oracle_065,
}


# ============================================================
# CASE PLAN — 42 CASES
# ============================================================

CASE_DEFS = []


def add_case(req, suffix, expected, rationale, graph):
    CASE_DEFS.append(
        {
            "requirement_id": req,
            "case_id": f"{req}-{suffix}",
            "expected": expected,
            "rationale": rationale,
            "graph": graph,
        }
    )


# I2-006 — 5

add_case(
    "I2-006",
    "P01",
    "PASS",
    "Astern ice operation is intended and aft-section design uses Bow and Bow Intermediate requirements.",
    build_006(
        "I2-006-P01",
        True,
        "Bow and Bow Intermediate",
        "Bow and Bow Intermediate hull area requirements",
    ),
)

add_case(
    "I2-006",
    "P02",
    "PASS",
    "Astern ice operation is not intended; conditional obligation does not apply.",
    build_006(
        "I2-006-P02",
        False,
    ),
)

add_case(
    "I2-006",
    "F01",
    "FAIL",
    "Astern operation is intended but aftSectionDesignBasis is incorrect.",
    build_006(
        "I2-006-F01",
        True,
        "Stern",
        "Bow and Bow Intermediate hull area requirements",
    ),
)

add_case(
    "I2-006",
    "F02",
    "FAIL",
    "Astern operation is intended but hullAreaRequirementSet is missing.",
    build_006(
        "I2-006-F02",
        True,
        "Bow and Bow Intermediate",
        None,
    ),
)

add_case(
    "I2-006",
    "F03",
    "FAIL",
    "Astern operation is intended but aftSectionDesignBasis is missing.",
    build_006(
        "I2-006-F03",
        True,
        None,
        "Bow and Bow Intermediate hull area requirements",
    ),
)


# I2-008 — 7

add_case(
    "I2-008",
    "P01",
    "PASS",
    "Polar Class ship has a complete bow-subregion readiness case.",
    build_008("I2-008-P01"),
)

for suffix, term in [
    ("F01", "bowShapeCoefficient"),
    ("F02", "totalGlancingImpactForce"),
    ("F03", "glancingImpactLineLoad"),
    ("F04", "glancingImpactPressure"),
]:
    add_case(
        "I2-008",
        suffix,
        "FAIL",
        f"Required bow-subregion readiness quantity {term} is missing.",
        build_008(
            f"I2-008-{suffix}",
            missing=term,
        ),
    )

add_case(
    "I2-008",
    "F05",
    "FAIL",
    "glancingImpactPressure is present on the wrong owner.",
    build_008(
        "I2-008-F05",
        wrong_owner="glancingImpactPressure",
    ),
)

add_case(
    "I2-008",
    "F06",
    "FAIL",
    "Bow calculation node exists but ship-to-case relationship is missing.",
    build_008(
        "I2-008-F06",
        omit_case_relation=True,
    ),
)


# I2-060 — 6

add_case(
    "I2-060",
    "P01",
    "PASS",
    "Member in way of cut-out is stable and stiffening is explicitly assessed as unnecessary.",
    build_060(
        "I2-060-P01",
        True,
        False,
        False,
    ),
)

add_case(
    "I2-060",
    "P02",
    "PASS",
    "Member is explicitly not in way of a cut-out; cut-out constraint is non-applicable.",
    build_060(
        "I2-060-P02",
        False,
        None,
        None,
        omit_cutout=True,
    ),
)

add_case(
    "I2-060",
    "F01",
    "FAIL",
    "Member in way of cut-out is explicitly unstable.",
    build_060(
        "I2-060-F01",
        True,
        True,
        True,
    ),
)

add_case(
    "I2-060",
    "F02",
    "FAIL",
    "Applicable member lacks memberInstability assessment.",
    build_060(
        "I2-060-F02",
        True,
        None,
        False,
    ),
)

add_case(
    "I2-060",
    "F03",
    "FAIL",
    "Applicable member lacks stiffeningNecessary assessment.",
    build_060(
        "I2-060-F03",
        True,
        False,
        None,
    ),
)

add_case(
    "I2-060",
    "F04",
    "FAIL",
    "memberInWayOfCutout is attached to the wrong owner.",
    build_060(
        "I2-060-F04",
        True,
        False,
        False,
        wrong_owner="memberInWayOfCutout",
    ),
)


# I2-062 — 6

add_case(
    "I2-062",
    "P01",
    "PASS",
    "Web frame in grillage system records direct calculation used.",
    build_062(
        "I2-062-P01",
        "webFrame",
        True,
        True,
    ),
)

add_case(
    "I2-062",
    "P02",
    "PASS",
    "Load-carrying stringer in grillage system records direct calculation used.",
    build_062(
        "I2-062-P02",
        "loadCarryingStringer",
        True,
        True,
    ),
)

add_case(
    "I2-062",
    "P03",
    "PASS",
    "Web frame not represented as part of a grillage system is outside this conditional obligation.",
    build_062(
        "I2-062-P03",
        "webFrame",
        False,
        None,
    ),
)

add_case(
    "I2-062",
    "F01",
    "FAIL",
    "Web frame in grillage explicitly records directCalculationUsed=false.",
    build_062(
        "I2-062-F01",
        "webFrame",
        True,
        False,
    ),
)

add_case(
    "I2-062",
    "F02",
    "FAIL",
    "Load-carrying stringer in grillage lacks directCalculationUsed result.",
    build_062(
        "I2-062-F02",
        "loadCarryingStringer",
        True,
        None,
    ),
)

add_case(
    "I2-062",
    "F03",
    "FAIL",
    "Direct-calculation result is attached to ship rather than applicable grillage member.",
    build_062(
        "I2-062-F03",
        "webFrame",
        True,
        True,
        wrong_owner=True,
    ),
)


# I2-064 — 9

add_case(
    "I2-064",
    "P01",
    "PASS",
    "Linear calculation has complete web/flange/buckling/stress readiness evidence.",
    build_064("I2-064-P01"),
)

add_case(
    "I2-064",
    "P02",
    "PASS",
    "Nonlinear calculation does not activate the I2-064 linear-analysis readiness branch.",
    build_064(
        "I2-064-P02",
        method="nonlinear",
    ),
)

add_case(
    "I2-064",
    "F01",
    "FAIL",
    "calculationMethod selector is missing.",
    build_064(
        "I2-064-F01",
        method=None,
    ),
)

add_case(
    "I2-064",
    "F02",
    "FAIL",
    "Linear case is missing structural-member web relationship.",
    build_064(
        "I2-064-F02",
        missing="web",
    ),
)

add_case(
    "I2-064",
    "F03",
    "FAIL",
    "Linear case is missing structural-member flange relationship.",
    build_064(
        "I2-064-F03",
        missing="flange",
    ),
)

add_case(
    "I2-064",
    "F04",
    "FAIL",
    "Linear case is missing nominal shear stress.",
    build_064(
        "I2-064-F04",
        missing="nominalShearStress",
    ),
)

add_case(
    "I2-064",
    "F05",
    "FAIL",
    "Linear case is missing nominal flange von Mises stress.",
    build_064(
        "I2-064-F05",
        missing="nominalFlangeVonMisesStress",
    ),
)

add_case(
    "I2-064",
    "F06",
    "FAIL",
    "Buckling-criteria assessment is explicitly false.",
    build_064(
        "I2-064-F06",
        buckling=False,
    ),
)

add_case(
    "I2-064",
    "F07",
    "FAIL",
    "Linear readiness case is missing yieldStrength.",
    build_064(
        "I2-064-F07",
        missing="yieldStrength",
    ),
)


# I2-065 — 9

add_case(
    "I2-065",
    "P01",
    "PASS",
    "Nonlinear calculation has complete margins, deformation quantities, explicit assessment and evidence.",
    build_065("I2-065-P01"),
)

add_case(
    "I2-065",
    "P02",
    "PASS",
    "Linear calculation does not activate I2-065 nonlinear readiness requirements.",
    build_065(
        "I2-065-P02",
        method="linear",
    ),
)

add_case(
    "I2-065",
    "F01",
    "FAIL",
    "Nonlinear case is missing acceptance evidence.",
    build_065(
        "I2-065-F01",
        missing="nonlinearAnalysisAcceptanceEvidence",
    ),
)

add_case(
    "I2-065",
    "F02",
    "FAIL",
    "Minor permanent-deformation assessment is explicitly false.",
    build_065(
        "I2-065-F02",
        assessment=False,
    ),
)

add_case(
    "I2-065",
    "F03",
    "FAIL",
    "Permanent lateral deformation quantity is missing.",
    build_065(
        "I2-065-F03",
        missing="permanentLateralDeformation",
    ),
)

add_case(
    "I2-065",
    "F04",
    "FAIL",
    "Permanent out-of-plane deformation quantity is missing.",
    build_065(
        "I2-065-F04",
        missing="permanentOutOfPlaneDeformation",
    ),
)

add_case(
    "I2-065",
    "F05",
    "FAIL",
    "Relevant structural dimension is missing.",
    build_065(
        "I2-065-F05",
        missing="relevantStructuralDimension",
    ),
)

add_case(
    "I2-065",
    "F06",
    "FAIL",
    "Fracture margin is missing.",
    build_065(
        "I2-065-F06",
        missing="fractureMargin",
    ),
)

add_case(
    "I2-065",
    "F07",
    "FAIL",
    "Nonlinear acceptance evidence is attached to wrong owner.",
    build_065(
        "I2-065-F07",
        wrong_owner="nonlinearAnalysisAcceptanceEvidence",
    ),
)


assert len(CASE_DEFS) == 42, len(CASE_DEFS)


# ============================================================
# VALIDATION
# ============================================================

def graph_vocab_ok(g):
    local = set()

    for s, p, o in g:
        for node in (s, p, o):
            text = str(node)

            if text.startswith(str(NLTL)):
                local.add(
                    text.split("#", 1)[1]
                )

    unknown = sorted(
        x
        for x in local
        if x not in KNOWN_NLTL
    )

    return not unknown, unknown


def graph_qudt_ok(g):
    for q in g.subjects(
        RDF.type,
        QUDT.QuantityValue,
    ):
        if len(
            list(
                g.objects(
                    q,
                    QUDT.numericValue,
                )
            )
        ) != 1:
            return False

        if len(
            list(
                g.objects(
                    q,
                    QUDT.unit,
                )
            )
        ) != 1:
            return False

    return True


def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def validate_existing(check_hashes=True):
    manifest_path = (
        ROOT
        / "manifests"
        / "i2_batch_c_manifest.jsonl"
    )

    lock_path = (
        ROOT
        / "locks"
        / "i2_batch_c_fixture_lock.json"
    )

    if not manifest_path.exists():
        raise SystemExit(
            "Batch C manifest does not exist"
        )

    rows = [
        json.loads(x)
        for x in manifest_path.read_text().splitlines()
        if x.strip()
    ]

    syntax = 0
    vocab = 0
    qudt = 0
    agreement = 0

    diagnostics = []

    for row in rows:
        p = ROOT / row["rdf_path"]

        try:
            g = Graph().parse(
                p,
                format="turtle",
            )
            syntax += 1
        except Exception as e:
            diagnostics.append(
                (
                    row["case_id"],
                    "parse",
                    str(e),
                )
            )
            continue

        ok, unknown = graph_vocab_ok(g)

        if ok:
            vocab += 1
        else:
            diagnostics.append(
                (
                    row["case_id"],
                    "vocab",
                    unknown,
                )
            )

        if graph_qudt_ok(g):
            qudt += 1
        else:
            diagnostics.append(
                (
                    row["case_id"],
                    "QUDT",
                    "invalid QuantityValue",
                )
            )

        actual = (
            "PASS"
            if ORACLES[
                row["requirement_id"]
            ](g)
            else "FAIL"
        )

        if actual == row["expected"]:
            agreement += 1
        else:
            diagnostics.append(
                (
                    row["case_id"],
                    "oracle",
                    f"expected={row['expected']} actual={actual}",
                )
            )

    hash_ok = True

    if check_hashes:
        if not lock_path.exists():
            hash_ok = False
            diagnostics.append(
                (
                    "lock",
                    "hash",
                    "lock file missing",
                )
            )
        else:
            lock = json.loads(
                lock_path.read_text()
            )

            for rel, expected_hash in lock[
                "frozen_files"
            ].items():
                p = ROOT / rel

                if (
                    not p.exists()
                    or sha256(p)
                    != expected_hash
                ):
                    hash_ok = False
                    diagnostics.append(
                        (
                            rel,
                            "hash",
                            "mismatch",
                        )
                    )

    n = len(rows)

    print(
        f"Requirements: "
        f"{len(set(r['requirement_id'] for r in rows))}"
    )
    print(f"RDF files: {n}")
    print(f"Syntactically valid: {syntax}")
    print(
        f"Vocabulary validation count: {vocab}"
    )
    print(
        f"QUDT/unit validation count: {qudt}"
    )
    print(
        f"Source-oracle agreement count: {agreement}"
    )

    if check_hashes:
        print(
            "Frozen hashes matched: "
            + ("YES" if hash_ok else "NO")
        )

    ok = (
        syntax
        == vocab
        == qudt
        == agreement
        == n
        and (
            hash_ok
            if check_hashes
            else True
        )
    )

    print(
        "Overall status: "
        + ("PASS" if ok else "FAIL")
    )

    if diagnostics:
        print("\nDiagnostics:")
        for d in diagnostics:
            print(d)

    return ok


# ============================================================
# GENERATION / FREEZE
# ============================================================

def generate():
    rdf_root = ROOT / "rdf" / "I2"
    spec_root = ROOT / "specifications" / "I2"
    manifest_root = ROOT / "manifests"
    locks_root = ROOT / "locks"
    scripts_root = ROOT / "scripts"

    for p in [
        rdf_root,
        spec_root,
        manifest_root,
        locks_root,
        scripts_root,
    ]:
        p.mkdir(
            parents=True,
            exist_ok=True,
        )

    lock_path = (
        locks_root
        / "i2_batch_c_fixture_lock.json"
    )

    if lock_path.exists():
        raise SystemExit(
            "Batch C lock already exists. "
            "Refusing to overwrite frozen fixtures."
        )

    clauses = {
        "I2-006": "I2.2.6",
        "I2-008": "I2.3.1(iii)",
        "I2-060": "I2.16.2",
        "I2-062": "I2.17.2",
        "I2-064": "I2.17.5",
        "I2-065": "I2.17.6",
    }

    manifest_rows = []

    for c in CASE_DEFS:
        req = c["requirement_id"]

        outdir = rdf_root / req
        outdir.mkdir(
            parents=True,
            exist_ok=True,
        )

        p = (
            outdir
            / f"{c['case_id']}.ttl"
        )

        c["graph"].serialize(
            destination=p,
            format="turtle",
        )

        manifest_rows.append(
            {
                "requirement_id": req,
                "case_id": c["case_id"],
                "expected": c["expected"],
                "rdf_path": str(
                    p.relative_to(ROOT)
                ),
                "source_id": "SRC-IACS-I2-R4",
                "source_clause": clauses[req],
                "verification_mode": (
                    EXPECTED_MODES[req]
                ),
                "source_oracle_rationale": (
                    c["rationale"]
                ),
                "generated_shacl_inspected": False,
            }
        )

    manifest_path = (
        manifest_root
        / "i2_batch_c_manifest.jsonl"
    )

    with manifest_path.open("w") as f:
        for row in manifest_rows:
            f.write(
                json.dumps(row) + "\n"
            )

    for req in REQS:
        spec = {
            "requirement_id": req,
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": clauses[req],
            "source_lock_id": INDEX[
                "sourceLockId"
            ],
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
            "benchmark_policy": (
                "Source/R13-defined behavioral "
                "oracle created without inspecting "
                "generated SHACL."
            ),
        }

        (
            spec_root
            / f"{req}.json"
        ).write_text(
            json.dumps(
                spec,
                indent=2,
            )
            + "\n"
        )

    print("Pre-freeze validation")

    if not validate_existing(
        check_hashes=False
    ):
        raise SystemExit(
            "Pre-freeze validation failed. "
            "No lock written."
        )

    frozen = [manifest_path]

    frozen += [
        spec_root / f"{req}.json"
        for req in REQS
    ]

    for req in REQS:
        frozen += sorted(
            (
                rdf_root
                / req
            ).glob("*.ttl")
        )

    lock = {
        "benchmark": (
            "I2 Behavioral Benchmark Batch C"
        ),
        "source_lock_id": INDEX[
            "sourceLockId"
        ],
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "pilot_fixtures_modified": False,
        "frozen_files": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in frozen
        },
    }

    lock_path.write_text(
        json.dumps(
            lock,
            indent=2,
        )
        + "\n"
    )

    # The standalone validator IS this same program.
    # This prevents generator/validator logic drifting apart.
    validator_path = (
        scripts_root
        / "validate_i2_batch_c.py"
    )

    shutil.copy2(
        Path(__file__).resolve(),
        validator_path,
    )

    validator_path.chmod(0o755)

    (
        ROOT
        / "README_I2_BATCH_C.md"
    ).write_text(
        """# I2 Behavioral Benchmark Batch C

Requirements: 6
Cases: 42

I2-006
I2-008
I2-060
I2-062
I2-064
I2-065

Generated SHACL was not inspected during fixture construction.

The creator and standalone validator share the same source code,
preventing validator-policy drift.

Run:

python3 scripts/validate_i2_batch_c.py
"""
    )

    print("\nFrozen validation")

    if not validate_existing(
        check_hashes=True
    ):
        raise SystemExit(
            "Post-freeze validation failed"
        )


def main():
    # Copied validator script automatically revalidates only.
    validation_mode = (
        Path(__file__).name
        == "validate_i2_batch_c.py"
        or "--validate-only" in sys.argv
    )

    if validation_mode:
        ok = validate_existing(
            check_hashes=True
        )
        raise SystemExit(
            0 if ok else 1
        )

    generate()


if __name__ == "__main__":
    main()
