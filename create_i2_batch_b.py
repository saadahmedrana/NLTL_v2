from pathlib import Path
import json
import hashlib
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD

REPO = Path.cwd()

ROOT = (
    REPO
    / "MVP"
    / "SHACL_GENERATION_PIPELINE"
    / "evaluation"
    / "BEHAVIORAL_RDF_R13"
)

R13 = REPO / "MVP" / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"

INDEX_PATH = R13 / "requirement_term_index.json"
REGISTRY_PATH = R13 / "registry" / "term_registry.json"

if not INDEX_PATH.exists():
    raise SystemExit(f"Missing R13 index: {INDEX_PATH}")

if not REGISTRY_PATH.exists():
    raise SystemExit(f"Missing R13 registry: {REGISTRY_PATH}")

INDEX = json.loads(INDEX_PATH.read_text())
REGISTRY = json.loads(REGISTRY_PATH.read_text())

CONTRACTS = INDEX["dependencyContracts"]
TERM_OWNERS = INDEX.get("termOwners", {})
REG = {x["localName"]: x for x in REGISTRY}

NLTL = Namespace("https://w3id.org/nltl/vocab#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")

BASE = "https://w3id.org/nltl/benchmark/i2-batch-b/"

REQUIREMENTS = [
    "I2-022",
    "I2-023",
    "I2-024",
    "I2-040",
    "I2-043",
]

for req in REQUIREMENTS:
    c = CONTRACTS[req]

    assert c["status"] == "COMPLETE", (req, c["status"])
    assert c["verificationMode"] == "COMPLEX_READINESS", (
        req,
        c["verificationMode"],
    )
    assert c.get("formulaExecutionRequired") is False, (
        req,
        c.get("formulaExecutionRequired"),
    )


def ensure_term(term):
    if term not in REG:
        raise RuntimeError(f"R13 registry term missing: {term}")


def unit_iri(term):
    ensure_term(term)

    # R13 intentionally defines interpolationPointResult as a
    # context-dependent quantity with no single global unit.
    # In I2-024 it represents endpoint net plate thickness,
    # therefore the source-grounded contextual unit is millimetre.
    if term == "interpolationPointResult":
        return URIRef("http://qudt.org/vocab/unit/MilliM")

    u = REG[term].get("unitIri", "")

    if not u:
        raise RuntimeError(
            f"Expected quantity term {term} has no frozen or contextual unit"
        )

    return URIRef(u)


def new_graph(case_id):
    g = Graph()

    g.bind("nltl", NLTL)
    g.bind("qudt", QUDT)
    g.bind("unit", UNIT)
    g.bind("xsd", XSD)

    ex = Namespace(BASE + case_id + "/")
    g.bind("ex", ex)

    ship = ex.ship
    g.add((ship, RDF.type, NLTL.ship))

    return g, ex, ship


def add_quantity(
    g,
    subject,
    term,
    ex,
    name,
    value,
    wrong_unit=False,
):
    ensure_term(term)

    q = ex[name]

    g.add((q, RDF.type, QUDT.QuantityValue))
    g.add(
        (
            q,
            QUDT.numericValue,
            Literal(str(value), datatype=XSD.decimal),
        )
    )

    expected = unit_iri(term)

    if wrong_unit:
        wrong = UNIT.UNITLESS

        if str(expected) == str(wrong):
            wrong = UNIT.M

        g.add((q, QUDT.unit, wrong))
    else:
        g.add((q, QUDT.unit, expected))

    g.add((subject, NLTL[term], q))

    return q


def quantity_valid(g, subject, term):
    vals = list(g.objects(subject, NLTL[term]))

    if len(vals) != 1:
        return False

    q = vals[0]

    if (q, RDF.type, QUDT.QuantityValue) not in g:
        return False

    nums = list(g.objects(q, QUDT.numericValue))
    units = list(g.objects(q, QUDT.unit))

    if len(nums) != 1 or len(units) != 1:
        return False

    return units[0] == unit_iri(term)


def quantity_number(g, subject, term):
    vals = list(g.objects(subject, NLTL[term]))

    if len(vals) != 1:
        return None

    nums = list(g.objects(vals[0], QUDT.numericValue))

    if len(nums) != 1:
        return None

    try:
        return float(nums[0])
    except Exception:
        return None


# ------------------------------------------------------------------
# I2-022
# ------------------------------------------------------------------

def build_022(
    case_id,
    omega,
    area="bowIntermediateBottomHullArea",
    complete=True,
    missing=None,
    wrong_owner=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(case_id)

    plating = ex.plating
    member = ex.member

    g.add((plating, RDF.type, NLTL.plating))
    g.add((member, RDF.type, NLTL.structuralMember))

    g.add((ship, NLTL.hasPlating, plating))
    g.add(
        (
            plating,
            NLTL.platingSupportedByStructuralMember,
            member,
        )
    )

    g.add(
        (
            plating,
            NLTL.platingHullAreaClassification,
            NLTL[area],
        )
    )

    add_quantity(
        g,
        plating,
        "framingAngleOmega",
        ex,
        "omega",
        omega,
    )

    if complete:
        fields = [
            (member, "frameSpacing", 0.6),
            (member, "selectedHullAreaFactor", 1.0),
            (member, "yieldStrength", 235.0),
            (plating, "peakPressureFactor", 1.2),
            (plating, "averageIcePressure", 1.5),
            (plating, "loadPatchHeight", 0.5),
            (
                plating,
                "iceLoadRequiredNetPlateThickness",
                0.012,
            ),
        ]

        for owner, term, value in fields:
            if term == missing:
                continue

            actual_owner = owner

            if term == wrong_owner:
                actual_owner = ship

            add_quantity(
                g,
                actual_owner,
                term,
                ex,
                term,
                value,
                wrong_unit=(term == wrong_unit),
            )

    return g


# ------------------------------------------------------------------
# I2-023
# ------------------------------------------------------------------

def build_023(
    case_id,
    omega,
    complete=True,
    missing=None,
    wrong_owner=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(case_id)

    plating = ex.plating
    member = ex.member

    g.add((plating, RDF.type, NLTL.plating))
    g.add((member, RDF.type, NLTL.structuralMember))

    g.add((ship, NLTL.hasPlating, plating))
    g.add(
        (
            plating,
            NLTL.platingSupportedByStructuralMember,
            member,
        )
    )

    add_quantity(
        g,
        plating,
        "framingAngleOmega",
        ex,
        "omega",
        omega,
    )

    if complete:
        fields = [
            (member, "frameSpacing", 0.6),
            (member, "frameSpan", 2.5),
            (member, "selectedHullAreaFactor", 1.0),
            (member, "yieldStrength", 235.0),
            (plating, "peakPressureFactor", 1.2),
            (plating, "averageIcePressure", 1.5),
            (plating, "loadPatchHeight", 0.5),
            (
                plating,
                "iceLoadRequiredNetPlateThickness",
                0.012,
            ),
        ]

        for owner, term, value in fields:
            if term == missing:
                continue

            actual_owner = owner

            if term == wrong_owner:
                actual_owner = ship

            add_quantity(
                g,
                actual_owner,
                term,
                ex,
                term,
                value,
                wrong_unit=(term == wrong_unit),
            )

    return g


# ------------------------------------------------------------------
# I2-024
# ------------------------------------------------------------------

def build_024(
    case_id,
    angle,
    complete=True,
    missing=None,
    wrong_owner=None,
    omit_upper_relation=False,
    wrong_unit=None,
):
    g, ex, ship = new_graph(case_id)

    case = ex.case
    lower = ex.lowerEndpoint
    upper = ex.upperEndpoint

    g.add(
        (
            case,
            RDF.type,
            NLTL.obliquePlatingInterpolationCase,
        )
    )

    g.add((case, RDF.type, NLTL.calculationCase))

    g.add((lower, RDF.type, NLTL.interpolationPoint))
    g.add((upper, RDF.type, NLTL.interpolationPoint))

    g.add(
        (
            ship,
            NLTL.hasObliquePlatingInterpolationCase,
            case,
        )
    )

    add_quantity(
        g,
        ship if wrong_owner == "framingAngle" else case,
        "framingAngle",
        ex,
        "framingAngle",
        angle,
    )

    # Non-applicable cases intentionally need nothing else.
    if not complete:
        return g

    g.add((case, NLTL.interpolationLowerEndpoint, lower))

    if not omit_upper_relation:
        g.add((case, NLTL.interpolationUpperEndpoint, upper))

    endpoint_data = [
        (
            lower,
            "interpolationPointCoordinate",
            "lowerCoordinate",
            20,
        ),
        (
            lower,
            "interpolationPointResult",
            "lowerResult",
            0.010,
        ),
        (
            upper,
            "interpolationPointCoordinate",
            "upperCoordinate",
            70,
        ),
        (
            upper,
            "interpolationPointResult",
            "upperResult",
            0.014,
        ),
    ]

    skipped_coordinate = False

    for owner, term, name, value in endpoint_data:
        if missing == "lowerInterpolationPointCoordinate":
            if owner == lower and term == "interpolationPointCoordinate":
                skipped_coordinate = True
                continue

        add_quantity(
            g,
            owner,
            term,
            ex,
            name,
            value,
            wrong_unit=(wrong_unit == term),
        )

    if missing != "longitudinalFramingNetPlateThickness":
        add_quantity(
            g,
            case,
            "longitudinalFramingNetPlateThickness",
            ex,
            "longitudinalThickness",
            0.010,
        )

    if missing != "transverseFramingNetPlateThickness":
        add_quantity(
            g,
            case,
            "transverseFramingNetPlateThickness",
            ex,
            "transverseThickness",
            0.014,
        )

    if missing != "interpolatedNetPlateThickness":
        add_quantity(
            g,
            case,
            "interpolatedNetPlateThickness",
            ex,
            "interpolatedThickness",
            0.012,
            wrong_unit=(
                wrong_unit == "interpolatedNetPlateThickness"
            ),
        )

    return g


# ------------------------------------------------------------------
# I2-040
# ------------------------------------------------------------------

def build_040(
    case_id,
    section,
    missing=None,
    wrong_owner=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(case_id)

    member = ex.member

    g.add((member, RDF.type, NLTL.structuralMember))
    g.add((ship, NLTL.hasStructuralMember, member))

    if section is not None:
        g.add(
            (
                member,
                NLTL.structuralSectionType,
                NLTL[section],
            )
        )

    fields = [
        ("webHeight", 0.20),
        ("netWebThickness", 0.010),
        ("yieldStrength", 235.0),
    ]

    for term, value in fields:
        if term == missing:
            continue

        owner = ship if term == wrong_owner else member

        add_quantity(
            g,
            owner,
            term,
            ex,
            term,
            value,
            wrong_unit=(term == wrong_unit),
        )

    return g


# ------------------------------------------------------------------
# I2-043
# ------------------------------------------------------------------

def build_043(
    case_id,
    missing=None,
    wrong_owner=None,
    wrong_unit=None,
):
    g, ex, ship = new_graph(case_id)

    member = ex.member

    g.add((member, RDF.type, NLTL.structuralMember))
    g.add((ship, NLTL.hasStructuralMember, member))

    fields = [
        ("netFlangeThickness", 0.012),
        ("yieldStrength", 235.0),
        ("flangeOutstand", 0.050),
    ]

    for term, value in fields:
        if term == missing:
            continue

        owner = ship if term == wrong_owner else member

        add_quantity(
            g,
            owner,
            term,
            ex,
            term,
            value,
            wrong_unit=(term == wrong_unit),
        )

    return g


# ================================================================
# FROZEN CASE PLAN
# ================================================================

CASES = []


def case(req, suffix, expected, rationale, graph):
    CASES.append(
        {
            "requirement_id": req,
            "case_id": f"{req}-{suffix}",
            "expected": expected,
            "rationale": rationale,
            "graph": graph,
        }
    )


# ---------------- I2-022 : 8 ----------------

case(
    "I2-022",
    "P01",
    "PASS",
    "Omega 90 deg; applicable transverse plating has complete readiness data.",
    build_022("I2-022-P01", 90),
)

case(
    "I2-022",
    "P02",
    "PASS",
    "Omega 70 deg boundary is applicable and complete.",
    build_022("I2-022-P02", 70, "midbodyBottomHullArea"),
)

case(
    "I2-022",
    "P03",
    "PASS",
    "Omega 45 deg is outside transverse applicability; missing readiness fields do not violate I2-022.",
    build_022(
        "I2-022-P03",
        45,
        "sternBottomHullArea",
        complete=False,
    ),
)

case(
    "I2-022",
    "F01",
    "FAIL",
    "Applicable transverse plating is missing frameSpacing.",
    build_022("I2-022-F01", 90, missing="frameSpacing"),
)

case(
    "I2-022",
    "F02",
    "FAIL",
    "Applicable transverse plating is missing the net-thickness result.",
    build_022(
        "I2-022-F02",
        90,
        missing="iceLoadRequiredNetPlateThickness",
    ),
)

case(
    "I2-022",
    "F03",
    "FAIL",
    "Applicable transverse plating is missing peakPressureFactor.",
    build_022(
        "I2-022-F03",
        90,
        missing="peakPressureFactor",
    ),
)

case(
    "I2-022",
    "F04",
    "FAIL",
    "frameSpacing exists but is attached to the wrong owner.",
    build_022(
        "I2-022-F04",
        90,
        wrong_owner="frameSpacing",
    ),
)

case(
    "I2-022",
    "F05",
    "FAIL",
    "Net-thickness result uses the wrong unit.",
    build_022(
        "I2-022-F05",
        90,
        wrong_unit="iceLoadRequiredNetPlateThickness",
    ),
)


# ---------------- I2-023 : 8 ----------------

case(
    "I2-023",
    "P01",
    "PASS",
    "Omega 0 deg longitudinal plating has complete readiness data.",
    build_023("I2-023-P01", 0),
)

case(
    "I2-023",
    "P02",
    "PASS",
    "Omega 20 deg boundary is applicable and complete.",
    build_023("I2-023-P02", 20),
)

case(
    "I2-023",
    "P03",
    "PASS",
    "Omega 45 deg is outside longitudinal applicability; readiness fields are not required by I2-023.",
    build_023("I2-023-P03", 45, complete=False),
)

case(
    "I2-023",
    "F01",
    "FAIL",
    "Applicable longitudinal plating is missing frameSpan.",
    build_023("I2-023-F01", 10, missing="frameSpan"),
)

case(
    "I2-023",
    "F02",
    "FAIL",
    "Applicable longitudinal plating is missing loadPatchHeight.",
    build_023(
        "I2-023-F02",
        10,
        missing="loadPatchHeight",
    ),
)

case(
    "I2-023",
    "F03",
    "FAIL",
    "Applicable longitudinal plating is missing the net-thickness result.",
    build_023(
        "I2-023-F03",
        10,
        missing="iceLoadRequiredNetPlateThickness",
    ),
)

case(
    "I2-023",
    "F04",
    "FAIL",
    "selectedHullAreaFactor is attached to the wrong owner.",
    build_023(
        "I2-023-F04",
        10,
        wrong_owner="selectedHullAreaFactor",
    ),
)

case(
    "I2-023",
    "F05",
    "FAIL",
    "Net-thickness result has the wrong unit.",
    build_023(
        "I2-023-F05",
        10,
        wrong_unit="iceLoadRequiredNetPlateThickness",
    ),
)


# ---------------- I2-024 : 9 ----------------

case(
    "I2-024",
    "P01",
    "PASS",
    "45 deg oblique case has complete interpolation readiness structure.",
    build_024("I2-024-P01", 45),
)

case(
    "I2-024",
    "P02",
    "PASS",
    "21 deg lies inside the oblique interval and has complete readiness data.",
    build_024("I2-024-P02", 21),
)

case(
    "I2-024",
    "P03",
    "PASS",
    "20 deg is not oblique under the strict 20 < angle < 70 condition.",
    build_024("I2-024-P03", 20, complete=False),
)

case(
    "I2-024",
    "P04",
    "PASS",
    "70 deg is not oblique under the strict 20 < angle < 70 condition.",
    build_024("I2-024-P04", 70, complete=False),
)

case(
    "I2-024",
    "F01",
    "FAIL",
    "Applicable oblique case is missing the lower interpolation-point coordinate.",
    build_024(
        "I2-024-F01",
        45,
        missing="lowerInterpolationPointCoordinate",
    ),
)

case(
    "I2-024",
    "F02",
    "FAIL",
    "Applicable oblique case is missing interpolatedNetPlateThickness.",
    build_024(
        "I2-024-F02",
        45,
        missing="interpolatedNetPlateThickness",
    ),
)

case(
    "I2-024",
    "F03",
    "FAIL",
    "framingAngle is attached to the wrong owner.",
    build_024(
        "I2-024-F03",
        45,
        wrong_owner="framingAngle",
    ),
)

case(
    "I2-024",
    "F04",
    "FAIL",
    "Applicable interpolation case is missing longitudinal-framing endpoint thickness.",
    build_024(
        "I2-024-F04",
        45,
        missing="longitudinalFramingNetPlateThickness",
    ),
)

case(
    "I2-024",
    "F05",
    "FAIL",
    "Applicable interpolation case is missing its upper-endpoint relation.",
    build_024(
        "I2-024-F05",
        45,
        omit_upper_relation=True,
    ),
)


# ---------------- I2-040 : 8 ----------------

for suffix, section in [
    ("P01", "flatBarStructuralSection"),
    ("P02", "bulbSection"),
    ("P03", "teeSection"),
    ("P04", "angleSection"),
]:
    case(
        "I2-040",
        suffix,
        "PASS",
        f"{section} contains all required web-buckling readiness quantities.",
        build_040(f"I2-040-{suffix}", section),
    )

case(
    "I2-040",
    "F01",
    "FAIL",
    "structuralSectionType is missing.",
    build_040("I2-040-F01", None),
)

case(
    "I2-040",
    "F02",
    "FAIL",
    "webHeight is missing.",
    build_040(
        "I2-040-F02",
        "teeSection",
        missing="webHeight",
    ),
)

case(
    "I2-040",
    "F03",
    "FAIL",
    "webHeight is attached to the wrong owner.",
    build_040(
        "I2-040-F03",
        "teeSection",
        wrong_owner="webHeight",
    ),
)

case(
    "I2-040",
    "F04",
    "FAIL",
    "yieldStrength uses an incorrect unit.",
    build_040(
        "I2-040-F04",
        "teeSection",
        wrong_unit="yieldStrength",
    ),
)


# ---------------- I2-043 : 6 ----------------

case(
    "I2-043",
    "P01",
    "PASS",
    "All flange-outstand readiness quantities are present on the structural member.",
    build_043("I2-043-P01"),
)

case(
    "I2-043",
    "F01",
    "FAIL",
    "netFlangeThickness is missing.",
    build_043(
        "I2-043-F01",
        missing="netFlangeThickness",
    ),
)

case(
    "I2-043",
    "F02",
    "FAIL",
    "yieldStrength is missing.",
    build_043(
        "I2-043-F02",
        missing="yieldStrength",
    ),
)

case(
    "I2-043",
    "F03",
    "FAIL",
    "flangeOutstand result is missing.",
    build_043(
        "I2-043-F03",
        missing="flangeOutstand",
    ),
)

case(
    "I2-043",
    "F04",
    "FAIL",
    "flangeOutstand is attached to the wrong owner.",
    build_043(
        "I2-043-F04",
        wrong_owner="flangeOutstand",
    ),
)

case(
    "I2-043",
    "F05",
    "FAIL",
    "flangeOutstand uses the wrong unit.",
    build_043(
        "I2-043-F05",
        wrong_unit="flangeOutstand",
    ),
)


assert len(CASES) == 39, len(CASES)


# ================================================================
# DETERMINISTIC SOURCE/R13 ORACLE
# ================================================================

def one(g, subject, predicate):
    vals = list(g.objects(subject, predicate))
    return vals[0] if len(vals) == 1 else None


def oracle_022(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]
    platings = list(g.objects(ship, NLTL.hasPlating))

    if not platings:
        return False

    for p in platings:
        omega = quantity_number(g, p, "framingAngleOmega")

        if omega is None or not quantity_valid(
            g, p, "framingAngleOmega"
        ):
            return False

        area = one(
            g,
            p,
            NLTL.platingHullAreaClassification,
        )

        applicable_area = area in {
            NLTL.bowIntermediateBottomHullArea,
            NLTL.midbodyBottomHullArea,
            NLTL.sternBottomHullArea,
        }

        applicable = omega >= 70 and applicable_area

        if not applicable:
            continue

        member = one(
            g,
            p,
            NLTL.platingSupportedByStructuralMember,
        )

        if member is None:
            return False

        member_terms = [
            "frameSpacing",
            "selectedHullAreaFactor",
            "yieldStrength",
        ]

        plating_terms = [
            "peakPressureFactor",
            "averageIcePressure",
            "loadPatchHeight",
            "iceLoadRequiredNetPlateThickness",
        ]

        if not all(
            quantity_valid(g, member, t)
            for t in member_terms
        ):
            return False

        if not all(
            quantity_valid(g, p, t)
            for t in plating_terms
        ):
            return False

    return True


def oracle_023(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]
    platings = list(g.objects(ship, NLTL.hasPlating))

    if not platings:
        return False

    for p in platings:
        omega = quantity_number(g, p, "framingAngleOmega")

        if omega is None or not quantity_valid(
            g, p, "framingAngleOmega"
        ):
            return False

        applicable = omega <= 20

        if not applicable:
            continue

        member = one(
            g,
            p,
            NLTL.platingSupportedByStructuralMember,
        )

        if member is None:
            return False

        member_terms = [
            "frameSpacing",
            "frameSpan",
            "selectedHullAreaFactor",
            "yieldStrength",
        ]

        plating_terms = [
            "peakPressureFactor",
            "averageIcePressure",
            "loadPatchHeight",
            "iceLoadRequiredNetPlateThickness",
        ]

        if not all(
            quantity_valid(g, member, t)
            for t in member_terms
        ):
            return False

        if not all(
            quantity_valid(g, p, t)
            for t in plating_terms
        ):
            return False

    return True


def oracle_024(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]

    cases = list(
        g.objects(
            ship,
            NLTL.hasObliquePlatingInterpolationCase,
        )
    )

    if not cases:
        return False

    for c in cases:
        angle = quantity_number(g, c, "framingAngle")

        # Wrong-owner framingAngle must not be silently accepted.
        if angle is None:
            return False

        if not quantity_valid(g, c, "framingAngle"):
            return False

        applicable = 20 < angle < 70

        if not applicable:
            continue

        if not quantity_valid(
            g,
            c,
            "longitudinalFramingNetPlateThickness",
        ):
            return False

        if not quantity_valid(
            g,
            c,
            "transverseFramingNetPlateThickness",
        ):
            return False

        if not quantity_valid(
            g,
            c,
            "interpolatedNetPlateThickness",
        ):
            return False

        lower = one(
            g,
            c,
            NLTL.interpolationLowerEndpoint,
        )

        upper = one(
            g,
            c,
            NLTL.interpolationUpperEndpoint,
        )

        if lower is None or upper is None:
            return False

        for endpoint in (lower, upper):
            if not quantity_valid(
                g,
                endpoint,
                "interpolationPointCoordinate",
            ):
                return False

            if not quantity_valid(
                g,
                endpoint,
                "interpolationPointResult",
            ):
                return False

    return True


def oracle_040(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]
    members = list(
        g.objects(ship, NLTL.hasStructuralMember)
    )

    if not members:
        return False

    allowed = {
        NLTL.flatBarStructuralSection,
        NLTL.bulbSection,
        NLTL.teeSection,
        NLTL.angleSection,
    }

    for m in members:
        section = one(
            g,
            m,
            NLTL.structuralSectionType,
        )

        if section not in allowed:
            return False

        for t in [
            "webHeight",
            "netWebThickness",
            "yieldStrength",
        ]:
            if not quantity_valid(g, m, t):
                return False

    return True


def oracle_043(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))

    if len(ships) != 1:
        return False

    ship = ships[0]
    members = list(
        g.objects(ship, NLTL.hasStructuralMember)
    )

    if not members:
        return False

    for m in members:
        for t in [
            "netFlangeThickness",
            "yieldStrength",
            "flangeOutstand",
        ]:
            if not quantity_valid(g, m, t):
                return False

    return True


ORACLES = {
    "I2-022": oracle_022,
    "I2-023": oracle_023,
    "I2-024": oracle_024,
    "I2-040": oracle_040,
    "I2-043": oracle_043,
}


# ================================================================
# WRITE BENCHMARK
# ================================================================

rdf_root = ROOT / "rdf" / "I2"
spec_root = ROOT / "specifications" / "I2"
manifest_root = ROOT / "manifests"
lock_root = ROOT / "locks"
scripts_root = ROOT / "scripts"

for p in [
    rdf_root,
    spec_root,
    manifest_root,
    lock_root,
    scripts_root,
]:
    p.mkdir(parents=True, exist_ok=True)


SOURCE_CLAUSES = {
    "I2-022": "I2.4.2 — transversely framed plating",
    "I2-023": "I2.4.2 — longitudinally framed plating",
    "I2-024": "I2.4.2 — obliquely framed plating",
    "I2-040": "I2.9 — local web buckling",
    "I2-043": "I2.9 — flange outstand",
}


# Do not overwrite an already-frozen Batch B accidentally.
lock_path = lock_root / "i2_batch_b_fixture_lock.json"

if lock_path.exists():
    raise SystemExit(
        "i2_batch_b_fixture_lock.json already exists. "
        "Refusing to overwrite a frozen Batch B."
    )


manifest_rows = []

for c in CASES:
    req = c["requirement_id"]
    cid = c["case_id"]

    outdir = rdf_root / req
    outdir.mkdir(parents=True, exist_ok=True)

    rdf_path = outdir / f"{cid}.ttl"

    c["graph"].serialize(
        destination=rdf_path,
        format="turtle",
    )

    manifest_rows.append(
        {
            "requirement_id": req,
            "case_id": cid,
            "expected": c["expected"],
            "rdf_path": str(
                rdf_path.relative_to(ROOT)
            ),
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": SOURCE_CLAUSES[req],
            "verification_mode": "COMPLEX_READINESS",
            "formula_execution_required": False,
            "source_oracle_rationale": c["rationale"],
        }
    )


for req in REQUIREMENTS:
    cases_for_req = [
        {
            "case_id": x["case_id"],
            "expected": x["expected"],
            "rationale": x["rationale"],
        }
        for x in CASES
        if x["requirement_id"] == req
    ]

    spec = {
        "requirement_id": req,
        "source_id": "SRC-IACS-I2-R4",
        "source_clause": SOURCE_CLAUSES[req],
        "source_lock_id": INDEX["sourceLockId"],
        "status": CONTRACTS[req]["status"],
        "verification_mode": CONTRACTS[req][
            "verificationMode"
        ],
        "formula_execution_required": CONTRACTS[req].get(
            "formulaExecutionRequired"
        ),
        "comparison_model": CONTRACTS[req][
            "comparisonModel"
        ],
        "operand_terms": CONTRACTS[req].get(
            "operandTerms", []
        ),
        "result_terms": CONTRACTS[req].get(
            "resultTerms", []
        ),
        "model_paths": CONTRACTS[req].get(
            "modelPaths", []
        ),
        "test_cases": cases_for_req,
        "benchmark_policy": (
            "Behavioral readiness oracle derived only from "
            "source requirement and frozen R13 contract. "
            "Generated SHACL was not inspected."
        ),
    }

    (
        spec_root / f"{req}.json"
    ).write_text(
        json.dumps(spec, indent=2) + "\n"
    )


manifest_path = (
    manifest_root / "i2_batch_b_manifest.jsonl"
)

with manifest_path.open("w") as f:
    for row in manifest_rows:
        f.write(json.dumps(row) + "\n")


# ================================================================
# VALIDATE BEFORE FREEZING
# ================================================================

registry_terms = set(REG.keys())

# Canonical benchmark infrastructure classes are part of the
# frozen R13 vocabulary even when they are not ordinary term_registry entries.
registry_terms |= {
    "ship",
    "plating",
    "structuralMember",
    "calculationCase",
    "obliquePlatingInterpolationCase",
    "interpolationPoint",
}

# Canonical benchmark infrastructure classes are part of the
# frozen R13 vocabulary even when they are not ordinary term_registry entries.
registry_terms |= {
    "ship",
    "plating",
    "structuralMember",
    "calculationCase",
    "obliquePlatingInterpolationCase",
    "interpolationPoint",
}

syntax_count = 0
vocab_count = 0
qudt_count = 0
oracle_count = 0

diagnostics = []


def graph_vocab_ok(g):
    local_names = set()

    for s, p, o in g:
        for node in (s, p, o):
            text = str(node)

            if text.startswith(str(NLTL)):
                local_names.add(
                    text.split("#", 1)[1]
                )

    unknown = sorted(
        x
        for x in local_names
        if x not in registry_terms
    )

    return len(unknown) == 0, unknown


def graph_qudt_ok(g):
    for q in g.subjects(
        RDF.type,
        QUDT.QuantityValue,
    ):
        nums = list(
            g.objects(q, QUDT.numericValue)
        )

        units = list(
            g.objects(q, QUDT.unit)
        )

        if len(nums) != 1:
            return False

        if len(units) != 1:
            return False

    return True


for row in manifest_rows:
    p = ROOT / row["rdf_path"]

    try:
        g = Graph().parse(p, format="turtle")
        syntax_count += 1
    except Exception as e:
        diagnostics.append(
            (
                row["case_id"],
                "TURTLE",
                str(e),
            )
        )
        continue

    ok, unknown = graph_vocab_ok(g)

    if ok:
        vocab_count += 1
    else:
        diagnostics.append(
            (
                row["case_id"],
                "VOCAB",
                unknown,
            )
        )

    if graph_qudt_ok(g):
        qudt_count += 1
    else:
        diagnostics.append(
            (
                row["case_id"],
                "QUDT",
                "bad QuantityValue structure",
            )
        )

    actual = (
        "PASS"
        if ORACLES[row["requirement_id"]](g)
        else "FAIL"
    )

    if actual == row["expected"]:
        oracle_count += 1
    else:
        diagnostics.append(
            (
                row["case_id"],
                "ORACLE",
                f"expected={row['expected']} actual={actual}",
            )
        )


N = len(manifest_rows)

print("Pre-freeze validation")
print(f"Requirements: {len(REQUIREMENTS)}")
print(f"RDF files: {N}")
print(f"Syntactically valid: {syntax_count}")
print(f"Vocabulary validation count: {vocab_count}")
print(f"QUDT/unit validation count: {qudt_count}")
print(f"Source-oracle agreement count: {oracle_count}")

if not (
    syntax_count
    == vocab_count
    == qudt_count
    == oracle_count
    == N
):
    print("Overall status: FAIL")

    for d in diagnostics:
        print(d)

    raise SystemExit(1)


# ================================================================
# FREEZE HASHES
# ================================================================

def sha256(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


frozen_files = [manifest_path]

frozen_files.extend(
    sorted(
        (spec_root / f"{r}.json")
        for r in REQUIREMENTS
    )
)

for req in REQUIREMENTS:
    frozen_files.extend(
        sorted(
            (rdf_root / req).glob("*.ttl")
        )
    )


lock = {
    "benchmark": "I2 Behavioral Benchmark Batch B",
    "source_lock_id": INDEX["sourceLockId"],
    "requirements": REQUIREMENTS,
    "requirement_count": len(REQUIREMENTS),
    "case_count": N,
    "generated_without_inspecting_generated_shacl": True,
    "pilot_fixtures_modified": False,
    "frozen_files": {
        str(p.relative_to(ROOT)): sha256(p)
        for p in frozen_files
    },
}

lock_path.write_text(
    json.dumps(lock, indent=2) + "\n"
)


# ================================================================
# WRITE STANDALONE REVALIDATOR
# ================================================================

validator = '''#!/usr/bin/env python3
from pathlib import Path
import json
import hashlib
import sys
from rdflib import Graph, Namespace, RDF

ROOT = Path(__file__).resolve().parents[1]
MVP_ROOT = ROOT.parents[2]

R13 = (
    MVP_ROOT
    / "BENCHMARK_VOCABULARY"
    / "FINAL_LOCK_R13"
)

REGISTRY = json.loads(
    (
        R13
        / "registry"
        / "term_registry.json"
    ).read_text()
)

REG = {x["localName"]: x for x in REGISTRY}

MANIFEST = (
    ROOT
    / "manifests"
    / "i2_batch_b_manifest.jsonl"
)

LOCK = (
    ROOT
    / "locks"
    / "i2_batch_b_fixture_lock.json"
)

NLTL = Namespace("https://w3id.org/nltl/vocab#")
QUDT = Namespace("http://qudt.org/schema/qudt/")


def unit_iri(term):
    from rdflib import URIRef

    # Contextual I2-024 endpoint thickness unit.
    if term == "interpolationPointResult":
        return URIRef("http://qudt.org/vocab/unit/MilliM")

    return URIRef(REG[term]["unitIri"])


def one(g, subject, predicate):
    vals = list(g.objects(subject, predicate))
    return vals[0] if len(vals) == 1 else None


def quantity_valid(g, subject, term):
    vals = list(g.objects(subject, NLTL[term]))

    if len(vals) != 1:
        return False

    q = vals[0]

    if (q, RDF.type, QUDT.QuantityValue) not in g:
        return False

    nums = list(g.objects(q, QUDT.numericValue))
    units = list(g.objects(q, QUDT.unit))

    if len(nums) != 1 or len(units) != 1:
        return False

    return units[0] == unit_iri(term)


def quantity_number(g, subject, term):
    vals = list(g.objects(subject, NLTL[term]))

    if len(vals) != 1:
        return None

    nums = list(
        g.objects(vals[0], QUDT.numericValue)
    )

    if len(nums) != 1:
        return None

    try:
        return float(nums[0])
    except Exception:
        return None


def oracle_022(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False

    ship = ships[0]
    ps = list(g.objects(ship, NLTL.hasPlating))

    if not ps:
        return False

    for p in ps:
        omega = quantity_number(
            g, p, "framingAngleOmega"
        )

        if (
            omega is None
            or not quantity_valid(
                g, p, "framingAngleOmega"
            )
        ):
            return False

        area = one(
            g,
            p,
            NLTL.platingHullAreaClassification,
        )

        applicable = (
            omega >= 70
            and area
            in {
                NLTL.bowIntermediateBottomHullArea,
                NLTL.midbodyBottomHullArea,
                NLTL.sternBottomHullArea,
            }
        )

        if not applicable:
            continue

        m = one(
            g,
            p,
            NLTL.platingSupportedByStructuralMember,
        )

        if m is None:
            return False

        if not all(
            quantity_valid(g, m, t)
            for t in [
                "frameSpacing",
                "selectedHullAreaFactor",
                "yieldStrength",
            ]
        ):
            return False

        if not all(
            quantity_valid(g, p, t)
            for t in [
                "peakPressureFactor",
                "averageIcePressure",
                "loadPatchHeight",
                "iceLoadRequiredNetPlateThickness",
            ]
        ):
            return False

    return True


def oracle_023(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False

    ship = ships[0]
    ps = list(g.objects(ship, NLTL.hasPlating))

    if not ps:
        return False

    for p in ps:
        omega = quantity_number(
            g, p, "framingAngleOmega"
        )

        if (
            omega is None
            or not quantity_valid(
                g, p, "framingAngleOmega"
            )
        ):
            return False

        if omega > 20:
            continue

        m = one(
            g,
            p,
            NLTL.platingSupportedByStructuralMember,
        )

        if m is None:
            return False

        if not all(
            quantity_valid(g, m, t)
            for t in [
                "frameSpacing",
                "frameSpan",
                "selectedHullAreaFactor",
                "yieldStrength",
            ]
        ):
            return False

        if not all(
            quantity_valid(g, p, t)
            for t in [
                "peakPressureFactor",
                "averageIcePressure",
                "loadPatchHeight",
                "iceLoadRequiredNetPlateThickness",
            ]
        ):
            return False

    return True


def oracle_024(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False

    ship = ships[0]

    cs = list(
        g.objects(
            ship,
            NLTL.hasObliquePlatingInterpolationCase,
        )
    )

    if not cs:
        return False

    for c in cs:
        angle = quantity_number(
            g, c, "framingAngle"
        )

        if (
            angle is None
            or not quantity_valid(
                g, c, "framingAngle"
            )
        ):
            return False

        if not 20 < angle < 70:
            continue

        for t in [
            "longitudinalFramingNetPlateThickness",
            "transverseFramingNetPlateThickness",
            "interpolatedNetPlateThickness",
        ]:
            if not quantity_valid(g, c, t):
                return False

        lo = one(
            g,
            c,
            NLTL.interpolationLowerEndpoint,
        )

        hi = one(
            g,
            c,
            NLTL.interpolationUpperEndpoint,
        )

        if lo is None or hi is None:
            return False

        for ep in (lo, hi):
            for t in [
                "interpolationPointCoordinate",
                "interpolationPointResult",
            ]:
                if not quantity_valid(g, ep, t):
                    return False

    return True


def oracle_040(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False

    ship = ships[0]

    ms = list(
        g.objects(
            ship,
            NLTL.hasStructuralMember,
        )
    )

    if not ms:
        return False

    allowed = {
        NLTL.flatBarStructuralSection,
        NLTL.bulbSection,
        NLTL.teeSection,
        NLTL.angleSection,
    }

    for m in ms:
        section = one(
            g,
            m,
            NLTL.structuralSectionType,
        )

        if section not in allowed:
            return False

        if not all(
            quantity_valid(g, m, t)
            for t in [
                "webHeight",
                "netWebThickness",
                "yieldStrength",
            ]
        ):
            return False

    return True


def oracle_043(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False

    ship = ships[0]

    ms = list(
        g.objects(
            ship,
            NLTL.hasStructuralMember,
        )
    )

    if not ms:
        return False

    return all(
        all(
            quantity_valid(g, m, t)
            for t in [
                "netFlangeThickness",
                "yieldStrength",
                "flangeOutstand",
            ]
        )
        for m in ms
    )


ORACLES = {
    "I2-022": oracle_022,
    "I2-023": oracle_023,
    "I2-024": oracle_024,
    "I2-040": oracle_040,
    "I2-043": oracle_043,
}


rows = [
    json.loads(x)
    for x in MANIFEST.read_text().splitlines()
    if x.strip()
]

lock = json.loads(LOCK.read_text())

registry_terms = set(REG.keys())

syntax = 0
vocab = 0
qudt = 0
agreement = 0

diagnostics = []


for row in rows:
    p = ROOT / row["rdf_path"]

    try:
        g = Graph().parse(p, format="turtle")
        syntax += 1
    except Exception as e:
        diagnostics.append(
            (row["case_id"], "parse", str(e))
        )
        continue

    local = set()

    for s, pred, o in g:
        for n in (s, pred, o):
            text = str(n)

            if text.startswith(str(NLTL)):
                local.add(
                    text.split("#", 1)[1]
                )

    unknown = sorted(
        x
        for x in local
        if x not in registry_terms
    )

    if unknown:
        diagnostics.append(
            (row["case_id"], "vocab", unknown)
        )
    else:
        vocab += 1

    qok = True

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
            qok = False

        if len(
            list(
                g.objects(
                    q,
                    QUDT.unit,
                )
            )
        ) != 1:
            qok = False

    if qok:
        qudt += 1
    else:
        diagnostics.append(
            (
                row["case_id"],
                "qudt",
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


def sha256(p):
    return hashlib.sha256(
        p.read_bytes()
    ).hexdigest()


hash_ok = True

for rel, expected_hash in lock[
    "frozen_files"
].items():
    p = ROOT / rel

    if (
        not p.exists()
        or sha256(p) != expected_hash
    ):
        hash_ok = False
        diagnostics.append(
            (rel, "hash", "mismatch")
        )


n = len(rows)

print(f"Requirements: {len(set(x['requirement_id'] for x in rows))}")
print(f"RDF files: {n}")
print(f"Syntactically valid: {syntax}")
print(f"Vocabulary validation count: {vocab}")
print(f"QUDT/unit validation count: {qudt}")
print(f"Source-oracle agreement count: {agreement}")
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
    and hash_ok
)

print(
    "Overall status: "
    + ("PASS" if ok else "FAIL")
)

if diagnostics:
    print("\\nDiagnostics:")

    for d in diagnostics:
        print(d)

sys.exit(0 if ok else 1)
'''

validator_path = (
    scripts_root / "validate_i2_batch_b.py"
)

validator_path.write_text(validator)
validator_path.chmod(0o755)


README = ROOT / "README_I2_BATCH_B.md"

README.write_text(
    """# I2 Behavioral Benchmark Batch B

Requirements: 5
RDF cases: 39

Requirements:
- I2-022
- I2-023
- I2-024
- I2-040
- I2-043

All five are frozen R13 COMPLEX_READINESS requirements with
formulaExecutionRequired=false.

The benchmark therefore checks applicability, required operands,
results, graph paths, owners and units rather than numerically
executing the advanced engineering formula.

Generated SHACL must not be inspected while constructing or
modifying this batch.

Validate with:

python3 scripts/validate_i2_batch_b.py
"""
)


print()
print("Batch B created and frozen.")
print(f"Requirements: {len(REQUIREMENTS)}")
print(f"RDF files: {N}")
print("Frozen hashes matched: YES")
print("Overall status: PASS")
print()
print(
    "Now run:"
)
print(
    "cd MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13"
)
print(
    "python3 scripts/validate_i2_batch_b.py"
)
