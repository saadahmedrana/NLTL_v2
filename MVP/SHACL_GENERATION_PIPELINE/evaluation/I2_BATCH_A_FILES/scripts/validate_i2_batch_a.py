#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, sys
from rdflib import Graph, Namespace, RDF
from rdflib.namespace import XSD

ROOT = Path(__file__).resolve().parents[1]
MVP_ROOT = ROOT.parents[2]
R13 = MVP_ROOT / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"
INDEX = R13 / "requirement_term_index.json"
REGISTRY = R13 / "registry" / "term_registry.json"
MANIFEST = ROOT / "manifests" / "i2_batch_a_manifest.jsonl"
LOCK = ROOT / "locks" / "i2_batch_a_fixture_lock.json"
NLTL = Namespace("https://w3id.org/nltl/vocab#")
QUDT = Namespace("http://qudt.org/schema/qudt/")

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def one(g,s,p):
    vals=list(g.objects(s,p))
    return vals[0] if len(vals)==1 else None
def boolv(g,s,p):
    v=one(g,s,p)
    return None if v is None else bool(v.toPython())
def num(g,s,p):
    q=one(g,s,p)
    if q is None: return None
    v=one(g,q,QUDT.numericValue)
    return None if v is None else float(v)

def oracle(req,g):
    ships=list(g.subjects(RDF.type,NLTL.ship))
    if len(ships)!=1: return False
    ship=ships[0]
    if req=="I2-001":
        d=one(g,ship,NLTL.constructionContractDate); a=boolv(g,ship,NLTL.urI2RevisionApplicability)
        if d is None or a is None: return False
        return a == (str(d) >= "2021-01-01")
    if req=="I2-013":
        return one(g,ship,NLTL.classificationSocietyAccelerationEvidence) is not None and one(g,ship,NLTL.inertialLoadDesignConsiderationEvidence) is not None
    if req=="I2-019":
        members=list(g.objects(ship,NLTL.hasStructuralMember))
        if not members: return False
        for m in members:
            areas=list(g.objects(m,NLTL.hasSpannedHullArea))
            selected=num(g,m,NLTL.selectedHullAreaFactor)
            if not areas or selected is None: return False
            factors=[num(g,a,NLTL.hullAreaFactor) for a in areas]
            if any(x is None for x in factors) or abs(selected-max(factors))>1e-9: return False
        return True
    if req=="I2-029":
        cs=list(g.objects(ship,NLTL.hasCalculationCase))
        if not cs: return False
        for c in cs:
            if boolv(g,c,NLTL.attachedShellPlatingIncludedInSectionModulus) is not True: return False
            if boolv(g,c,NLTL.attachedShellPlatingExcludedFromShearArea) is not True: return False
            fi=boolv(g,c,NLTL.flangeMaterialIncludedInShearArea)
            if fi is None: return False
            m=one(g,c,NLTL.sectionCalculationCaseStructuralMember)
            if m is None: return False
            if fi is True and boolv(g,m,NLTL.flangeFitted) is not True: return False
        return True
    if req=="I2-037":
        members=list(g.objects(ship,NLTL.hasStructuralMember))
        applicable=[m for m in members if (m,RDF.type,NLTL.webFrame) in g or (m,RDF.type,NLTL.loadCarryingStringer) in g]
        if not applicable: return False
        if not list(g.objects(ship,NLTL.hasIceLoadPatchDesignCase)): return False
        for m in applicable:
            lcs=list(g.objects(m,NLTL.hasStructuralMemberLoadCase))
            if not lcs: return False
            if not all(boolv(g,lc,NLTL.memberCapacityMinimizationConfirmed) is True for lc in lcs): return False
        return True
    if req=="I2-061":
        cases=list(g.objects(ship,NLTL.hasCalculationCase))
        if not cases: return False
        for c in cases:
            hs=one(g,c,NLTL.calculationCaseAssessedHullStructure)
            if hs is None: return False
            applicable=((hs,RDF.type,NLTL.plating) in g or (hs,RDF.type,NLTL.structuralMember) in g)
            if applicable:
                method=one(g,c,NLTL.calculationMethod)
                if method is None or method==NLTL.directCalculationMethodValue: return False
        return True
    raise KeyError(req)

rows=[json.loads(x) for x in MANIFEST.read_text().splitlines() if x.strip()]
lock=json.loads(LOCK.read_text())
idx=json.loads(INDEX.read_text())
reg=json.loads(REGISTRY.read_text())
known={r["localName"] for r in reg}
known |= {"ship","evidenceArtifact","structuralMember","calculationCase","hullAreaValue","webFrame","loadCarryingStringer","loadCase","iceLoadPatchDesignCase","plating","hullStructure"}

syntax=vocab=qudt=agree=0
bad=[]
for row in rows:
    p=ROOT/row["rdf_path"]
    try:
        g=Graph().parse(p,format="turtle"); syntax+=1
    except Exception as e:
        bad.append((row["case_id"],"parse",str(e))); continue
    local=set()
    for s,pred,o in g:
        for u in (s,pred,o):
            if str(u).startswith(str(NLTL)):
                local.add(str(u).split("#",1)[1])
    unknown=sorted(x for x in local if x not in known)
    if unknown:
        bad.append((row["case_id"],"vocab",unknown))
    else: vocab+=1
    qok=True
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1:
            qok=False
    if qok: qudt+=1
    else: bad.append((row["case_id"],"qudt","bad QuantityValue"))
    actual="PASS" if oracle(row["requirement_id"],g) else "FAIL"
    if actual==row["expected"]: agree+=1
    else: bad.append((row["case_id"],"oracle",f"expected {row['expected']} got {actual}"))

hash_ok=True
for rel,h in lock["frozen_files"].items():
    p=ROOT/rel
    if not p.is_file() or sha(p)!=h:
        hash_ok=False; bad.append((rel,"hash","mismatch"))

print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}")
print(f"RDF files: {len(rows)}")
print(f"Syntactically valid: {syntax}")
print(f"Vocabulary validation count: {vocab}")
print(f"QUDT/unit validation count: {qudt}")
print(f"Source-oracle agreement count: {agree}")
print(f"Frozen hashes matched: {'YES' if hash_ok else 'NO'}")
status=(syntax==len(rows)==vocab==qudt==agree and hash_ok)
print(f"Overall status: {'PASS' if status else 'FAIL'}")
if bad:
    print("Diagnostics:")
    for x in bad: print(" ",x)
sys.exit(0 if status else 1)
