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
BASE = "https://w3id.org/nltl/benchmark/i2-batch-e/"

REQS = ["I2-014", "I2-015", "I2-017", "I2-018"]
EXPECTED_MODES = {
    "I2-014": "DIRECT_CALCULATION",
    "I2-015": "COMPLEX_READINESS",
    "I2-017": "COMPLEX_READINESS",
    "I2-018": "DIRECT_CALCULATION",
}
for req in REQS:
    assert CONTRACTS[req]["status"] == "COMPLETE"
    assert CONTRACTS[req]["verificationMode"] == EXPECTED_MODES[req]
for req in ["I2-015", "I2-017"]:
    assert CONTRACTS[req].get("formulaExecutionRequired") is False

ONTOLOGY = Graph().parse(R13 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
KNOWN_NLTL = {
    str(s).split("#", 1)[1]
    for s in set(ONTOLOGY.subjects())
    if str(s).startswith(str(NLTL))
}


def new_graph(case_id):
    g = Graph()
    ex = Namespace(BASE + case_id + "/")
    g.bind("ex", ex); g.bind("nltl", NLTL); g.bind("qudt", QUDT); g.bind("unit", UNIT); g.bind("xsd", XSD)
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


def add_value(g, subject, term, value, ex, name=None, unit_override=None, wrong_unit=False):
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
        g.add((subject, NLTL[term], q))
        return q
    if kind == "DatatypeProperty":
        dt = datatype_for(term)
        if dt is None:
            raise RuntimeError(f"Unsupported datatype for {term}")
        g.add((subject, NLTL[term], Literal(value, datatype=dt)))
        return None
    if kind == "ObjectProperty":
        if not isinstance(value, URIRef):
            raise RuntimeError(f"{term} requires URIRef")
        g.add((subject, NLTL[term], value))
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
    nums = list(g.objects(q, QUDT.numericValue)); units = list(g.objects(q, QUDT.unit))
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


# ----------------------------- I2-014 -----------------------------
def build_014(cid, count=4, missing_evidence_index=None, missing_field=None,
              selected_force=None, selected_line=None, selected_pressure=None,
              midpoint_values=None, reverse_links=False):
    g, ex, ship = new_graph(cid)
    mids = midpoint_values or [1.0, 3.0, 5.0, 7.0]
    forces = [4.0, 6.0, 5.0, 7.0]
    lines = [1.0, 1.4, 1.2, 1.3]
    pressures = [2.0, 2.5, 2.2, 2.4]
    cases = []
    for i in range(count):
        c = ex[f"subregion{i+1}"]
        cases.append(c)
        g.add((c, RDF.type, NLTL.bowSubregionCalculationCase))
        if missing_field != (i, "bowSubregionMidLengthPosition"):
            add_value(g, c, "bowSubregionMidLengthPosition", mids[i], ex, f"mid{i+1}")
        if missing_field != (i, "bowSubregionAspectRatio"):
            add_value(g, c, "bowSubregionAspectRatio", 1.5 + 0.1*i, ex, f"ar{i+1}")
        if missing_field != (i, "bowSubregionCalculatedForce"):
            add_value(g, c, "bowSubregionCalculatedForce", forces[i], ex, f"force{i+1}")
        if missing_field != (i, "bowSubregionCalculatedLineLoad"):
            add_value(g, c, "bowSubregionCalculatedLineLoad", lines[i], ex, f"line{i+1}")
        if missing_field != (i, "bowSubregionCalculatedPressure"):
            add_value(g, c, "bowSubregionCalculatedPressure", pressures[i], ex, f"pressure{i+1}")
        if missing_evidence_index != i:
            ev = ex[f"evidence{i+1}"]
            g.add((ev, RDF.type, NLTL.evidenceArtifact))
            g.add((c, NLTL.bowSubregionCalculationEvidence, ev))
    link_order = list(reversed(cases)) if reverse_links else cases
    for c in link_order:
        g.add((ship, NLTL.hasBowSubregionCalculationCase, c))
    if selected_force is None: selected_force = max(forces[:count]) if count else 0
    if selected_line is None: selected_line = max(lines[:count]) if count else 0
    if selected_pressure is None: selected_pressure = max(pressures[:count]) if count else 0
    add_value(g, ship, "selectedMaximumBowForce", selected_force, ex, "selectedForce")
    add_value(g, ship, "selectedMaximumBowLineLoad", selected_line, ex, "selectedLine")
    add_value(g, ship, "selectedMaximumBowPressure", selected_pressure, ex, "selectedPressure")
    return g


def oracle_014(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1: return False
    ship = ships[0]
    cases = list(g.objects(ship, NLTL.hasBowSubregionCalculationCase))
    if len(cases) != 4: return False
    mids = []; forces = []; lines = []; pressures = []
    for c in cases:
        if one(g, c, NLTL.bowSubregionCalculationEvidence) is None: return False
        mid = qty_number(g, c, "bowSubregionMidLengthPosition")
        ar = qty_number(g, c, "bowSubregionAspectRatio")
        f = qty_number(g, c, "bowSubregionCalculatedForce")
        q = qty_number(g, c, "bowSubregionCalculatedLineLoad")
        p = qty_number(g, c, "bowSubregionCalculatedPressure")
        if None in (mid, ar, f, q, p): return False
        mids.append(mid); forces.append(f); lines.append(q); pressures.append(p)
    mids.sort()
    d1, d2, d3 = mids[1]-mids[0], mids[2]-mids[1], mids[3]-mids[2]
    if d1 <= 0 or not (close(d1,d2) and close(d2,d3)): return False
    return (
        close(qty_number(g, ship, "selectedMaximumBowForce"), max(forces))
        and close(qty_number(g, ship, "selectedMaximumBowLineLoad"), max(lines))
        and close(qty_number(g, ship, "selectedMaximumBowPressure"), max(pressures))
    )


# ----------------------------- I2-015 -----------------------------
def build_015(cid, missing=None, wrong_relation=False, wrong_classification=False):
    g, ex, ship = new_graph(cid)
    case = ex.bowCase; lookup = ex.factorLookup
    g.add((case, RDF.type, NLTL.bowSubregionCalculationCase))
    g.add((lookup, RDF.type, NLTL.tableLookupCase))
    if not wrong_relation:
        g.add((ship, NLTL.hasBowSubregionCalculationCase, case))
    if missing != "classification":
        g.add((case, NLTL.bowFormApplicabilityClassification,
               NLTL.i231vBowFormApplicability if not wrong_classification else ex.wrongApplicability))
        if wrong_classification:
            g.add((ex.wrongApplicability, RDF.type, NLTL.bowFormApplicabilityValue))
    if missing != "lookupRelation":
        g.add((case, NLTL.hasFailureClassFactorLookupCase, lookup))
    if missing != "upperIceWaterlineLengthLUI": add_value(g, ship, "upperIceWaterlineLengthLUI", 100, ex, "lui")
    if missing != "bowSubregionMidLengthPosition": add_value(g, case, "bowSubregionMidLengthPosition", 10, ex, "x")
    if missing != "bowSubregionWaterlineAngle": add_value(g, case, "bowSubregionWaterlineAngle", 30, ex, "alpha")
    if missing != "betaIPrime": add_value(g, case, "betaIPrime", 0.5, ex, "betaPrime")
    if missing != "flexuralFailureClassFactor": add_value(g, lookup, "flexuralFailureClassFactor", 9.0, ex, "cff")
    if missing != "crushingFailureClassFactor": add_value(g, lookup, "crushingFailureClassFactor", 3.1, ex, "cfc")
    if missing != "bowShapeCoefficient": add_value(g, case, "bowShapeCoefficient", 0.6, ex, "fa")
    return g


def oracle_015(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1: return False
    ship = ships[0]
    if qty_number(g, ship, "upperIceWaterlineLengthLUI") is None: return False
    cases = list(g.objects(ship, NLTL.hasBowSubregionCalculationCase))
    if len(cases) != 1: return False
    c = cases[0]
    if one(g, c, NLTL.bowFormApplicabilityClassification) != NLTL.i231vBowFormApplicability: return False
    lookup = one(g, c, NLTL.hasFailureClassFactorLookupCase)
    if lookup is None: return False
    for term in ["bowSubregionMidLengthPosition", "bowSubregionWaterlineAngle", "betaIPrime", "bowShapeCoefficient"]:
        if qty_number(g, c, term) is None: return False
    for term in ["flexuralFailureClassFactor", "crushingFailureClassFactor"]:
        if qty_number(g, lookup, term) is None: return False
    return True


# ----------------------------- I2-017 -----------------------------
def build_017(cid, dui=20, threshold=40, missing=None, omit_link=False, wrong_unit=None):
    g, ex, ship = new_graph(cid)
    case = ex.nonBowCase
    g.add((case, RDF.type, NLTL.nonBowIceLoadCalculationCase))
    g.add((case, RDF.type, NLTL.calculationCase))
    g.add((case, RDF.type, NLTL.tableLookupCase))
    if not omit_link:
        g.add((ship, NLTL.hasNonBowIceLoadCalculationCase, case))
    if missing != "upperIceWaterlineDraughtDUI": add_value(g, ship, "upperIceWaterlineDraughtDUI", dui, ex, "dui", wrong_unit=(wrong_unit=="upperIceWaterlineDraughtDUI"))
    if missing != "displacementFactorThreshold": add_value(g, ship, "displacementFactorThreshold", threshold, ex, "threshold")
    if missing != "crushingFailureClassFactor": add_value(g, case, "crushingFailureClassFactor", 3.1, ex, "cfc")
    if missing != "loadPatchDimensionClassFactor": add_value(g, case, "loadPatchDimensionClassFactor", 1.31, ex, "cfd")
    if missing != "shipDisplacementFactor": add_value(g, case, "shipDisplacementFactor", 6.8 if dui<=threshold else 8.0, ex, "df")
    if missing != "nonBowIceForce": add_value(g, case, "nonBowIceForce", 700, ex, "force")
    if missing != "nonBowIceLineLoad": add_value(g, case, "nonBowIceLineLoad", 0.7, ex, "line")
    return g


def oracle_017(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1: return False
    ship = ships[0]
    if qty_number(g, ship, "upperIceWaterlineDraughtDUI") is None: return False
    if qty_number(g, ship, "displacementFactorThreshold") is None: return False
    cases = list(g.objects(ship, NLTL.hasNonBowIceLoadCalculationCase))
    if len(cases) != 1: return False
    c = cases[0]
    for term in ["crushingFailureClassFactor", "loadPatchDimensionClassFactor", "shipDisplacementFactor", "nonBowIceForce", "nonBowIceLineLoad"]:
        if qty_number(g, c, term) is None: return False
    return True


# ----------------------------- I2-018 -----------------------------
def build_018(cid, force_kn=1800, height=1.0, length=1.0, pavg=1.8,
              ppf=1.0, selected_ppf=1.0, missing=None, wrong_table=False):
    g, ex, ship = new_graph(cid)
    patch = ex.patch; lookup = ex.lookup; ev = ex.evidence
    g.add((patch, RDF.type, NLTL.iceLoadPatch))
    g.add((lookup, RDF.type, NLTL.peakPressureFactorLookupCase))
    g.add((lookup, RDF.type, NLTL.tableLookupCase))
    g.add((ev, RDF.type, NLTL.evidenceArtifact))
    if missing != "hasIceLoadPatch": g.add((ship, NLTL.hasIceLoadPatch, patch))
    if missing != "hasPeakPressureFactorLookupCase": g.add((ship, NLTL.hasPeakPressureFactorLookupCase, lookup))
    if missing != "hasTableLookupCase": g.add((ship, NLTL.hasTableLookupCase, lookup))
    if missing != "iceForce": add_value(g, patch, "iceForce", force_kn, ex, "force")
    if missing != "loadPatchHeight": add_value(g, patch, "loadPatchHeight", height, ex, "height")
    if missing != "loadPatchLength": add_value(g, patch, "loadPatchLength", length, ex, "length")
    if missing != "averageIcePressure": add_value(g, patch, "averageIcePressure", pavg, ex, "pavg")
    if missing != "localizedStructuralMemberCategory": g.add((lookup, NLTL.localizedStructuralMemberCategory, NLTL.bottomStructureFrameCategory))
    if missing != "selectedPeakPressureFactor": add_value(g, lookup, "selectedPeakPressureFactor", selected_ppf, ex, "selectedPpf")
    if missing != "peakPressureFactor": add_value(g, lookup, "peakPressureFactor", ppf, ex, "ppf")
    if missing != "tableReference": g.add((lookup, NLTL.tableReference, NLTL.iacsUrI2Table3 if not wrong_table else NLTL.iacsUrI2Table8))
    if missing != "lookupSelectionEvidence": g.add((lookup, NLTL.lookupSelectionEvidence, ev))
    return g


def oracle_018(g):
    ships = list(g.subjects(RDF.type, NLTL.ship))
    if len(ships) != 1: return False
    ship = ships[0]
    patch = one(g, ship, NLTL.hasIceLoadPatch)
    lookup = one(g, ship, NLTL.hasPeakPressureFactorLookupCase)
    table_lookup = one(g, ship, NLTL.hasTableLookupCase)
    if patch is None or lookup is None or table_lookup != lookup: return False
    f = qty_number(g, patch, "iceForce"); b = qty_number(g, patch, "loadPatchHeight"); w = qty_number(g, patch, "loadPatchLength"); p = qty_number(g, patch, "averageIcePressure")
    if None in (f,b,w,p) or b <= 0 or w <= 0: return False
    # Frozen R13 stores iceForce in kN; source Pavg is MPa. 1 kN/m^2 = 0.001 MPa.
    if not close(p, f / (b*w) / 1000.0): return False
    if one(g, lookup, NLTL.localizedStructuralMemberCategory) != NLTL.bottomStructureFrameCategory: return False
    if one(g, lookup, NLTL.tableReference) != NLTL.iacsUrI2Table3: return False
    if one(g, lookup, NLTL.lookupSelectionEvidence) is None: return False
    ppf = qty_number(g, lookup, "peakPressureFactor"); selected = qty_number(g, lookup, "selectedPeakPressureFactor")
    # Table 3 gives PPFs=1.0 for frames in bottom structures, which can be tested without inventing a spacing term absent from this R13 contract.
    return close(ppf, 1.0) and close(selected, 1.0)


ORACLES = {"I2-014": oracle_014, "I2-015": oracle_015, "I2-017": oracle_017, "I2-018": oracle_018}
CASE_DEFS = []
def add_case(req, suffix, expected, rationale, graph):
    CASE_DEFS.append({"requirement_id": req, "case_id": f"{req}-{suffix}", "expected": expected, "rationale": rationale, "graph": graph})

# I2-014 — 9
add_case("I2-014","P01","PASS","Exactly four equally spaced bow subregion midpoint cases carry evidence, F/Q/P/AR results, and correct selected maxima.",build_014("I2-014-P01"))
add_case("I2-014","P02","PASS","RDF link ordering is irrelevant; four complete subregions in reverse insertion order still produce the same maxima.",build_014("I2-014-P02",reverse_links=True))
add_case("I2-014","F01","FAIL","Only three bow subregion calculation cases are represented instead of four.",build_014("I2-014-F01",count=3))
add_case("I2-014","F02","FAIL","One bow subregion is missing its calculation-evidence artifact.",build_014("I2-014-F02",missing_evidence_index=2))
add_case("I2-014","F03","FAIL","One bow subregion is missing its aspect-ratio result.",build_014("I2-014-F03",missing_field=(1,"bowSubregionAspectRatio")))
add_case("I2-014","F04","FAIL","Selected maximum bow force is not the maximum of the four reported subregion forces.",build_014("I2-014-F04",selected_force=6.0))
add_case("I2-014","F05","FAIL","Selected maximum bow line load is incorrect.",build_014("I2-014-F05",selected_line=1.2))
add_case("I2-014","F06","FAIL","Selected maximum bow pressure is incorrect.",build_014("I2-014-F06",selected_pressure=2.2))
add_case("I2-014","F07","FAIL","Four midpoint positions are not equally spaced, violating equal-length subregion structure.",build_014("I2-014-F07",midpoint_values=[1.0,3.0,5.0,8.0]))

# I2-015 — 9
add_case("I2-015","P01","PASS","Applicable I2.3.1(v) bow case contains the complete frozen R13 readiness interface.",build_015("I2-015-P01"))
for suffix, term in [("F01","bowSubregionMidLengthPosition"),("F02","upperIceWaterlineLengthLUI"),("F03","bowSubregionWaterlineAngle"),("F04","betaIPrime"),("F05","flexuralFailureClassFactor"),("F06","crushingFailureClassFactor"),("F07","bowShapeCoefficient")]:
    add_case("I2-015",suffix,"FAIL",f"Required readiness term {term} is missing.",build_015(f"I2-015-{suffix}",missing=term))
add_case("I2-015","F08","FAIL","Bow subregion case is not linked from the ship via hasBowSubregionCalculationCase.",build_015("I2-015-F08",wrong_relation=True))

# I2-017 — 10
add_case("I2-017","P01","PASS","Complete non-bow readiness case with D_UI below the displacement-factor threshold.",build_017("I2-017-P01",20,40))
add_case("I2-017","P02","PASS","Complete non-bow readiness case with D_UI above the displacement-factor threshold.",build_017("I2-017-P02",60,40))
for suffix, term in [("F01","upperIceWaterlineDraughtDUI"),("F02","displacementFactorThreshold"),("F03","crushingFailureClassFactor"),("F04","loadPatchDimensionClassFactor"),("F05","shipDisplacementFactor"),("F06","nonBowIceForce"),("F07","nonBowIceLineLoad")]:
    add_case("I2-017",suffix,"FAIL",f"Required non-bow readiness term {term} is missing.",build_017(f"I2-017-{suffix}",missing=term))
add_case("I2-017","F08","FAIL","Non-bow calculation case exists but is not linked from the ship.",build_017("I2-017-F08",omit_link=True))

# I2-018 — 8
add_case("I2-018","P01","PASS","Bottom-structure frame Table-3 case has correct Pavg and constant PPFs=1.0 with frozen table reference and evidence.",build_018("I2-018-P01"))
add_case("I2-018","P02","PASS","Different load-patch dimensions preserve Pavg=F/(b*w) and the bottom-structure Table-3 PPF of 1.0.",build_018("I2-018-P02",force_kn=2400,height=1.0,length=2.0,pavg=1.2))
add_case("I2-018","F01","FAIL","Average pressure does not equal F/(b*w) after R13 kN-to-source-MPa conversion.",build_018("I2-018-F01",pavg=1.7))
add_case("I2-018","F02","FAIL","Bottom-structure Table-3 peak-pressure factor is incorrect.",build_018("I2-018-F02",ppf=1.2,selected_ppf=1.2))
add_case("I2-018","F03","FAIL","IACS UR I2 Table 3 reference is missing.",build_018("I2-018-F03",missing="tableReference"))
add_case("I2-018","F04","FAIL","Localized structural-member category selector is missing.",build_018("I2-018-F04",missing="localizedStructuralMemberCategory"))
add_case("I2-018","F05","FAIL","Table-lookup selection evidence is missing.",build_018("I2-018-F05",missing="lookupSelectionEvidence"))
add_case("I2-018","F06","FAIL","Lookup case references the wrong IACS table.",build_018("I2-018-F06",wrong_table=True))

assert len(CASE_DEFS) == 36, len(CASE_DEFS)


def graph_vocab_ok(g):
    local=set()
    for s,p,o in g:
        for node in (s,p,o):
            text=str(node)
            if text.startswith(str(NLTL)): local.add(text.split("#",1)[1])
    unknown=sorted(x for x in local if x not in KNOWN_NLTL)
    return not unknown, unknown

def graph_qudt_ok(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1: return False
    return True

def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_existing(check_hashes=True):
    manifest_path=ROOT/"manifests"/"i2_batch_e_manifest.jsonl"; lock_path=ROOT/"locks"/"i2_batch_e_fixture_lock.json"
    if not manifest_path.exists(): raise SystemExit("Batch E manifest does not exist")
    rows=[json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
    syntax=vocab=qudt=agreement=0; diagnostics=[]
    for row in rows:
        p=ROOT/row["rdf_path"]
        try: g=Graph().parse(p,format="turtle"); syntax+=1
        except Exception as e: diagnostics.append((row["case_id"],"parse",str(e))); continue
        ok,unknown=graph_vocab_ok(g)
        if ok: vocab+=1
        else: diagnostics.append((row["case_id"],"vocab",unknown))
        if graph_qudt_ok(g): qudt+=1
        else: diagnostics.append((row["case_id"],"QUDT","invalid QuantityValue"))
        actual="PASS" if ORACLES[row["requirement_id"]](g) else "FAIL"
        if actual==row["expected"]: agreement+=1
        else: diagnostics.append((row["case_id"],"oracle",f"expected={row['expected']} actual={actual}"))
    hash_ok=True
    if check_hashes:
        if not lock_path.exists(): hash_ok=False; diagnostics.append(("lock","hash","lock file missing"))
        else:
            lock=json.loads(lock_path.read_text())
            for rel,expected_hash in lock["frozen_files"].items():
                p=ROOT/rel
                if not p.exists() or sha256(p)!=expected_hash: hash_ok=False; diagnostics.append((rel,"hash","mismatch"))
    n=len(rows)
    print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}"); print(f"RDF files: {n}"); print(f"Syntactically valid: {syntax}"); print(f"Vocabulary validation count: {vocab}"); print(f"QUDT/unit validation count: {qudt}"); print(f"Source-oracle agreement count: {agreement}")
    if check_hashes: print("Frozen hashes matched: "+("YES" if hash_ok else "NO"))
    ok=syntax==vocab==qudt==agreement==n and (hash_ok if check_hashes else True)
    print("Overall status: "+("PASS" if ok else "FAIL"))
    if diagnostics:
        print("\nDiagnostics:")
        for d in diagnostics: print(d)
    return ok


def generate():
    rdf_root=ROOT/"rdf"/"I2"; spec_root=ROOT/"specifications"/"I2"; manifest_root=ROOT/"manifests"; locks_root=ROOT/"locks"; scripts_root=ROOT/"scripts"
    for p in [rdf_root,spec_root,manifest_root,locks_root,scripts_root]: p.mkdir(parents=True,exist_ok=True)
    lock_path=locks_root/"i2_batch_e_fixture_lock.json"
    if lock_path.exists(): raise SystemExit("Batch E lock already exists. Refusing to overwrite frozen fixtures.")
    clauses={"I2-014":"I2.3.2.1(ii)","I2-015":"I2.3.2.1(iii)(a)","I2-017":"I2.3.2.2(i)","I2-018":"I2.3.4(i)-(ii), Table 3"}
    rows=[]
    for c in CASE_DEFS:
        req=c["requirement_id"]; outdir=rdf_root/req; outdir.mkdir(parents=True,exist_ok=True); p=outdir/f"{c['case_id']}.ttl"; c["graph"].serialize(destination=p,format="turtle")
        rows.append({"requirement_id":req,"case_id":c["case_id"],"expected":c["expected"],"rdf_path":str(p.relative_to(ROOT)),"source_id":"SRC-IACS-I2-R4","source_clause":clauses[req],"verification_mode":EXPECTED_MODES[req],"sourceability_grade":"D_REGULATION_SYNTHETIC","source_oracle_rationale":c["rationale"],"generated_shacl_inspected":False})
    manifest_path=manifest_root/"i2_batch_e_manifest.jsonl"
    with manifest_path.open("w") as f:
        for row in rows: f.write(json.dumps(row)+"\n")
    for req in REQS:
        spec={"requirement_id":req,"source_id":"SRC-IACS-I2-R4","source_clause":clauses[req],"source_lock_id":INDEX["sourceLockId"],"r13_contract":CONTRACTS[req],"test_cases":[{"case_id":x["case_id"],"expected":x["expected"],"rationale":x["rationale"]} for x in CASE_DEFS if x["requirement_id"]==req],"sourceability_grade":"D_REGULATION_SYNTHETIC","benchmark_policy":"Source/R13-defined behavioral oracle created without inspecting generated SHACL."}
        (spec_root/f"{req}.json").write_text(json.dumps(spec,indent=2)+"\n")
    print("Pre-freeze validation")
    if not validate_existing(False): raise SystemExit("Pre-freeze validation failed. No lock written.")
    frozen=[manifest_path]+[spec_root/f"{r}.json" for r in REQS]
    for req in REQS: frozen+=sorted((rdf_root/req).glob("*.ttl"))
    lock={"benchmark":"I2 Behavioral Benchmark Batch E","source_lock_id":INDEX["sourceLockId"],"requirements":REQS,"requirement_count":len(REQS),"case_count":len(CASE_DEFS),"generated_without_inspecting_generated_shacl":True,"previous_frozen_batches_modified":False,"frozen_files":{str(p.relative_to(ROOT)):sha256(p) for p in frozen}}
    lock_path.write_text(json.dumps(lock,indent=2)+"\n")
    validator=scripts_root/"validate_i2_batch_e.py"; shutil.copy2(Path(__file__).resolve(),validator); validator.chmod(0o755)
    (ROOT/"README_I2_BATCH_E.md").write_text("# I2 Behavioral Benchmark Batch E\n\nRequirements: 4\nCases: 36\n\nI2-014\nI2-015\nI2-017\nI2-018\n\nGenerated SHACL was not inspected during fixture construction. I2-018 Table-3 cases use the bottom-structure-frame row (PPFs=1.0), which is deterministically testable using the frozen R13 contract without inventing an absent spacing selector.\n\nRun:\n\npython3 scripts/validate_i2_batch_e.py\n")
    print("\nFrozen validation")
    if not validate_existing(True): raise SystemExit("Post-freeze validation failed")

def main():
    validation_mode=Path(__file__).name=="validate_i2_batch_e.py" or "--validate-only" in sys.argv
    if validation_mode: raise SystemExit(0 if validate_existing(True) else 1)
    generate()

if __name__=="__main__": main()
