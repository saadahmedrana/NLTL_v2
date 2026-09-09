#!/usr/bin/env python3
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

registry_terms |= {
    "ship",
    "plating",
    "structuralMember",
    "calculationCase",
    "obliquePlatingInterpolationCase",
    "interpolationPoint",
}

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
    print("\nDiagnostics:")

    for d in diagnostics:
        print(d)

sys.exit(0 if ok else 1)
