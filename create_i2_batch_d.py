from pathlib import Path
import json
import hashlib
import math
import shutil
import sys

from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD


def find_repo():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    candidates += list(Path(__file__).resolve().parents)
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
BASE = "https://w3id.org/nltl/benchmark/i2-batch-d/"

REQS = ["I2-009", "I2-010", "I2-011"]
EXPECTED_MODES = {
    "I2-009": "DIRECT_STATIC",
    "I2-010": "DIRECT_STATIC",
    "I2-011": "DIRECT_CALCULATION",
}
for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]

# Use the frozen ontology itself as the vocabulary allow-list. This is stricter
# and less brittle than maintaining a hand-written infrastructure-term list.
ONTOLOGY = Graph().parse(R13 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
KNOWN_NLTL = set()
for s in set(ONTOLOGY.subjects()):
    text = str(s)
    if text.startswith(str(NLTL)):
        KNOWN_NLTL.add(text.split("#", 1)[1])


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
    dt = REG[term].get("datatype", "")
    return {
        "xsd:boolean": XSD.boolean,
        "xsd:string": XSD.string,
        "xsd:integer": XSD.integer,
        "xsd:decimal": XSD.decimal,
        "xsd:date": XSD.date,
    }.get(dt)


def add_value(g, subject, term, value, ex, name=None, unit_override=None, wrong_unit=False):
    if term not in REG:
        raise RuntimeError(f"Unknown R13 term: {term}")
    row = REG[term]
    kind = row["kind"]
    if kind == "QuantityProperty":
        unit = unit_override or row.get("unitIri", "")
        if not unit:
            raise RuntimeError(f"{term} is QuantityProperty but has no frozen/context unit")
        q = ex[name or (term + "Value")]
        g.add((q, RDF.type, QUDT.QuantityValue))
        g.add((q, QUDT.numericValue, Literal(str(value), datatype=XSD.decimal)))
        u = URIRef(unit)
        if wrong_unit:
            alt = UNIT.UNITLESS if u != UNIT.UNITLESS else UNIT.M
            u = alt
        g.add((q, QUDT.unit, u))
        g.add((subject, NLTL[term], q))
        return q
    if kind == "DatatypeProperty":
        dt = datatype_for(term)
        if dt is None:
            raise RuntimeError(f"No supported datatype mapping for {term}")
        g.add((subject, NLTL[term], Literal(value, datatype=dt)))
        return None
    if kind == "ObjectProperty":
        if not isinstance(value, URIRef):
            raise RuntimeError(f"{term} requires URIRef object")
        g.add((subject, NLTL[term], value))
        return value
    raise RuntimeError(f"add_value cannot use {kind} term {term}")


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


def qty_number(g, s, term, expected_unit=None):
    if term not in REG:
        return None
    expected = expected_unit or REG[term].get("unitIri", "")
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
    if expected and str(units[0]) != expected:
        return None
    try:
        return float(nums[0])
    except Exception:
        return None


def close(a, b, tol=1e-9):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ----------------------------- I2-009 -----------------------------
def build_009_nonbow(cid, ar=3.6, height=1.0, length=3.6, pressure=1.2,
                     area=NLTL.otherIceStrengthenedArea, omit_assignment=False,
                     omit_area_link=False):
    g, ex, ship = new_graph(cid)
    assignment = ex.assignment
    g.add((assignment, RDF.type, NLTL.hullAreaAssignment))
    if not omit_assignment:
        g.add((ship, NLTL.hasHullAreaAssignment, assignment))
    if not omit_area_link:
        g.add((assignment, NLTL.assignedHullArea, area))
    add_value(g, ship, "loadPatchAspectRatio", ar, ex, "ar")
    add_value(g, ship, "nonBowLoadPatchHeight", height, ex, "height")
    add_value(g, ship, "nonBowLoadPatchLength", length, ex, "length")
    add_value(g, ship, "averageIcePressure", pressure, ex, "pressure")
    return g


def build_009_bow(cid, gamma, beta, applicable=None):
    g, ex, ship = new_graph(cid)
    add_value(g, ship, "buttockAngle", gamma, ex, "gamma")
    add_value(g, ship, "normalFrameAngle", beta, ex, "beta")
    if applicable is not None:
        add_value(g, ship, "bowFormApplicability", applicable, ex)
    return g


def oracle_009(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    assignments = list(g.objects(ship, NLTL.hasHullAreaAssignment))
    if assignments:
        if len(assignments) != 1:
            return False
        a = assignments[0]
        if one(g, a, NLTL.assignedHullArea) != NLTL.otherIceStrengthenedArea:
            return False
        ar = qty_number(g, ship, "loadPatchAspectRatio")
        h = qty_number(g, ship, "nonBowLoadPatchHeight")
        w = qty_number(g, ship, "nonBowLoadPatchLength")
        p = qty_number(g, ship, "averageIcePressure")
        return (
            close(ar, 3.6)
            and h is not None and h > 0
            and w is not None and w > 0
            and close(w / h, 3.6)
            and p is not None
        )
    gamma = qty_number(g, ship, "buttockAngle")
    beta = qty_number(g, ship, "normalFrameAngle")
    declared = bool_value(g, ship, "bowFormApplicability")
    if gamma is None or beta is None or declared is None:
        return False
    expected = (gamma > 0.0 and gamma < 80.0 and beta > 10.0)
    return declared is expected


# ----------------------------- I2-010 -----------------------------
def build_010(cid, pc=None, vertical=None, angle=None, method=None, status=None):
    g, ex, ship = new_graph(cid)
    if pc is not None:
        g.add((ship, NLTL.polarClass, NLTL[pc]))
    if vertical is not None:
        add_value(g, ship, "verticalSidedBowForm", vertical, ex)
    if status is not None:
        add_value(g, ship, "bowVerticalSideStatus", status, ex)
    if angle is not None:
        add_value(g, ship, "normalFrameAngle", angle, ex, "beta")
    if method is not None:
        add_value(g, ship, "bowDesignForceMethod", method, ex)
    return g


def oracle_010(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    pc = one(g, ship, NLTL.polarClass)
    if pc is None:
        return False
    vertical = bool_value(g, ship, "verticalSidedBowForm")
    status = bool_value(g, ship, "bowVerticalSideStatus")
    angle = qty_number(g, ship, "normalFrameAngle")
    method = string_value(g, ship, "bowDesignForceMethod")
    if vertical is None:
        return False
    if status is not None and status is not vertical:
        return False
    pc67 = pc in {NLTL.polarClassPc6, NLTL.polarClassPc7}
    if pc67 and vertical and angle is None:
        return False
    applicable = pc67 and vertical and angle is not None and 0.0 <= angle <= 10.0
    if applicable:
        return status is True and method == "I2.3.2.1(iv)"
    return method != "I2.3.2.1(iv)"


# ----------------------------- I2-011 -----------------------------
def build_011(cid, pc=None, bulbous=None, force_iii=None, force_iv=None,
              fa=None, ar=None, design_kn=None, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    if pc is not None:
        g.add((ship, NLTL.polarClass, NLTL[pc]))
    if bulbous is not None:
        add_value(g, ship, "bulbousBowPresent", bulbous, ex)
    vals = [
        ("bowDesignForceMethodI2Point3Point2Point1PartIii", force_iii, "fiii"),
        ("bowDesignForceMethodI2Point3Point2Point1PartIv", force_iv, "fiv"),
        ("shapeCoefficient", fa, "fa"),
        ("loadPatchAspectRatio", ar, "ar"),
        ("bowDesignForce", design_kn, "design"),
    ]
    for term, value, name in vals:
        if value is not None:
            add_value(g, ship, term, value, ex, name, wrong_unit=(wrong_unit == term))
    return g


def oracle_011(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1:
        return False
    ship = ships[0]
    pc = one(g, ship, NLTL.polarClass)
    bulbous = bool_value(g, ship, "bulbousBowPresent")
    if pc is None or bulbous is None:
        return False
    applicable = pc in {NLTL.polarClassPc6, NLTL.polarClassPc7} and bulbous
    if not applicable:
        return True
    fiii = qty_number(g, ship, "bowDesignForceMethodI2Point3Point2Point1PartIii")
    fiv = qty_number(g, ship, "bowDesignForceMethodI2Point3Point2Point1PartIv")
    fa = qty_number(g, ship, "shapeCoefficient")
    ar = qty_number(g, ship, "loadPatchAspectRatio")
    design = qty_number(g, ship, "bowDesignForce")
    if None in (fiii, fiv, fa, ar, design):
        return False
    if not close(fa, 0.6) or not close(ar, 1.3):
        return False
    expected_kn = max(fiii, fiv) * 1000.0  # source candidates are MN; result term is kN in frozen R13
    return close(design, expected_kn)


ORACLES = {"I2-009": oracle_009, "I2-010": oracle_010, "I2-011": oracle_011}
CASE_DEFS = []

def add_case(req, suffix, expected, rationale, graph):
    CASE_DEFS.append({"requirement_id": req, "case_id": f"{req}-{suffix}", "expected": expected,
                      "rationale": rationale, "graph": graph})

# I2-009 — 11 cases
add_case("I2-009", "P01", "PASS", "Other ice-strengthened area uses the fixed non-bow aspect ratio AR=3.6 with consistent dimensions.", build_009_nonbow("I2-009-P01"))
add_case("I2-009", "P02", "PASS", "Bow form satisfies 0<buttockAngle<80 and normalFrameAngle>10, and applicability is declared true.", build_009_bow("I2-009-P02", 30, 20, True))
add_case("I2-009", "P03", "PASS", "Bow-form applicability holds immediately inside both strict boundaries.", build_009_bow("I2-009-P03", 0.1, 10.1, True))
add_case("I2-009", "P04", "PASS", "At buttockAngle=80 the I2.3.1(v) bow branch is non-applicable and is declared false.", build_009_bow("I2-009-P04", 80, 20, False))
add_case("I2-009", "F01", "FAIL", "Other ice-strengthened area uses AR other than the fixed value 3.6.", build_009_nonbow("I2-009-F01", ar=3.5, length=3.5))
add_case("I2-009", "F02", "FAIL", "Other-area assignment node is not linked from the ship.", build_009_nonbow("I2-009-F02", omit_assignment=True))
add_case("I2-009", "F03", "FAIL", "Hull-area assignment targets the Bow region instead of the frozen other-ice-strengthened-area value.", build_009_nonbow("I2-009-F03", area=NLTL.bowRegion))
add_case("I2-009", "F04", "FAIL", "buttockAngle=0 is outside the strict positive range but applicability is declared true.", build_009_bow("I2-009-F04", 0, 20, True))
add_case("I2-009", "F05", "FAIL", "buttockAngle=80 is outside the strict upper bound but applicability is declared true.", build_009_bow("I2-009-F05", 80, 20, True))
add_case("I2-009", "F06", "FAIL", "normalFrameAngle=10 does not satisfy the strict >10 requirement but applicability is declared true.", build_009_bow("I2-009-F06", 30, 10, True))
add_case("I2-009", "F07", "FAIL", "Angles satisfy the source branch but bowFormApplicability is declared false.", build_009_bow("I2-009-F07", 30, 20, False))

# I2-010 — 11 cases
add_case("I2-010", "P01", "PASS", "PC6 vertical-sided bow at lower boundary beta'=0 uses method I2.3.2.1(iv).", build_010("I2-010-P01", "polarClassPc6", True, 0, "I2.3.2.1(iv)", True))
add_case("I2-010", "P02", "PASS", "PC7 vertical-sided bow at inclusive upper boundary beta'=10 uses method I2.3.2.1(iv).", build_010("I2-010-P02", "polarClassPc7", True, 10, "I2.3.2.1(iv)", True))
add_case("I2-010", "P03", "PASS", "PC6 vertical-sided bow inside the 0-10 degree interval uses method (iv).", build_010("I2-010-P03", "polarClassPc6", True, 5, "I2.3.2.1(iv)", True))
add_case("I2-010", "P04", "PASS", "PC5 is outside the PC6/PC7 applicability branch when method (iv) is not asserted.", build_010("I2-010-P04", "polarClassPc5", True, 5, None, True))
add_case("I2-010", "P05", "PASS", "PC6 ship without a vertical-sided bow is outside this specific source branch.", build_010("I2-010-P05", "polarClassPc6", False, 5, None, False))
add_case("I2-010", "F01", "FAIL", "Method (iv) is incorrectly asserted for PC5.", build_010("I2-010-F01", "polarClassPc5", True, 5, "I2.3.2.1(iv)", True))
add_case("I2-010", "F02", "FAIL", "Method (iv) is asserted for beta'=11, outside the inclusive 0-10 range.", build_010("I2-010-F02", "polarClassPc6", True, 11, "I2.3.2.1(iv)", True))
add_case("I2-010", "F03", "FAIL", "Applicable PC6 vertical-sided bow is missing the required method selection.", build_010("I2-010-F03", "polarClassPc6", True, 5, None, True))
add_case("I2-010", "F04", "FAIL", "Applicable PC7 vertical-sided bow selects method (iii) instead of method (iv).", build_010("I2-010-F04", "polarClassPc7", True, 5, "I2.3.2.1(iii)", True))
add_case("I2-010", "F05", "FAIL", "Vertical-sided-bow status contradicts the verticalSidedBowForm selector.", build_010("I2-010-F05", "polarClassPc6", True, 5, "I2.3.2.1(iv)", False))
add_case("I2-010", "F06", "FAIL", "Polar Class selector is missing.", build_010("I2-010-F06", None, True, 5, "I2.3.2.1(iv)", True))

# I2-011 — 10 cases
add_case("I2-011", "P01", "PASS", "PC6 bulbous bow: method-(iv) candidate governs and final design force equals the greater candidate.", build_011("I2-011-P01", "polarClassPc6", True, 4.0, 5.0, 0.6, 1.3, 5000))
add_case("I2-011", "P02", "PASS", "PC7 bulbous bow: method-(iii) floor governs and final design force respects the floor.", build_011("I2-011-P02", "polarClassPc7", True, 5.0, 4.0, 0.6, 1.3, 5000))
add_case("I2-011", "P03", "PASS", "Non-PC6/PC7 bulbous bow is outside the source applicability branch.", build_011("I2-011-P03", "polarClassPc5", True))
add_case("I2-011", "P04", "PASS", "PC6 without a bulbous bow is outside the source applicability branch.", build_011("I2-011-P04", "polarClassPc6", False))
add_case("I2-011", "F01", "FAIL", "Applicable bulbous-bow case uses shape coefficient other than the mandated 0.6 floor assumption.", build_011("I2-011-F01", "polarClassPc6", True, 4.0, 5.0, 0.5, 1.3, 5000))
add_case("I2-011", "F02", "FAIL", "Applicable bulbous-bow case uses load-patch aspect ratio other than 1.3 for the method-(iii) floor.", build_011("I2-011-F02", "polarClassPc6", True, 4.0, 5.0, 0.6, 1.2, 5000))
add_case("I2-011", "F03", "FAIL", "Final design force is below the method-(iii) floor.", build_011("I2-011-F03", "polarClassPc7", True, 5.0, 4.0, 0.6, 1.3, 4000))
add_case("I2-011", "F04", "FAIL", "Method-(iv) candidate governs but final design force does not equal the governing value.", build_011("I2-011-F04", "polarClassPc6", True, 4.0, 5.0, 0.6, 1.3, 4500))
add_case("I2-011", "F05", "FAIL", "Applicable case is missing the method-(iii) comparison-force operand.", build_011("I2-011-F05", "polarClassPc6", True, None, 5.0, 0.6, 1.3, 5000))
add_case("I2-011", "F06", "FAIL", "Method-(iv) force has the wrong unit.", build_011("I2-011-F06", "polarClassPc6", True, 4.0, 5.0, 0.6, 1.3, 5000, wrong_unit="bowDesignForceMethodI2Point3Point2Point1PartIv"))

assert len(CASE_DEFS) == 32, len(CASE_DEFS)


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
    manifest_path = ROOT / "manifests" / "i2_batch_d_manifest.jsonl"
    lock_path = ROOT / "locks" / "i2_batch_d_fixture_lock.json"
    if not manifest_path.exists():
        raise SystemExit("Batch D manifest does not exist")
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
    lock_path = locks_root / "i2_batch_d_fixture_lock.json"
    if lock_path.exists():
        raise SystemExit("Batch D lock already exists. Refusing to overwrite frozen fixtures.")
    clauses = {"I2-009": "I2.3.1(iv)-(v)", "I2-010": "I2.3.1(vi)", "I2-011": "I2.3.1(vii)"}
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
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": clauses[req],
            "verification_mode": EXPECTED_MODES[req],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
            "source_oracle_rationale": c["rationale"],
            "generated_shacl_inspected": False,
        })
    manifest_path = manifest_root / "i2_batch_d_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in manifest_rows:
            f.write(json.dumps(row) + "\n")
    for req in REQS:
        spec = {
            "requirement_id": req,
            "source_id": "SRC-IACS-I2-R4",
            "source_clause": clauses[req],
            "source_lock_id": INDEX["sourceLockId"],
            "r13_contract": CONTRACTS[req],
            "test_cases": [{"case_id": x["case_id"], "expected": x["expected"], "rationale": x["rationale"]}
                           for x in CASE_DEFS if x["requirement_id"] == req],
            "sourceability_grade": "D_REGULATION_SYNTHETIC",
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
        "benchmark": "I2 Behavioral Benchmark Batch D",
        "source_lock_id": INDEX["sourceLockId"],
        "requirements": REQS,
        "requirement_count": len(REQS),
        "case_count": len(CASE_DEFS),
        "generated_without_inspecting_generated_shacl": True,
        "previous_frozen_batches_modified": False,
        "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    validator_path = scripts_root / "validate_i2_batch_d.py"
    shutil.copy2(Path(__file__).resolve(), validator_path)
    validator_path.chmod(0o755)
    (ROOT / "README_I2_BATCH_D.md").write_text(
        "# I2 Behavioral Benchmark Batch D\n\n"
        "Requirements: 3\nCases: 32\n\nI2-009\nI2-010\nI2-011\n\n"
        "This batch resolves the previously postponed PC6/PC7 bow-form applicability group using the frozen R13 controlled individuals polarClassPc6 and polarClassPc7.\n\n"
        "Generated SHACL was not inspected during fixture construction.\n\n"
        "Run:\n\npython3 scripts/validate_i2_batch_d.py\n"
    )
    print("\nFrozen validation")
    if not validate_existing(check_hashes=True):
        raise SystemExit("Post-freeze validation failed")


def main():
    validation_mode = Path(__file__).name == "validate_i2_batch_d.py" or "--validate-only" in sys.argv
    if validation_mode:
        raise SystemExit(0 if validate_existing(check_hashes=True) else 1)
    generate()


if __name__ == "__main__":
    main()
