
from pathlib import Path
import json, hashlib, math, shutil, sys
from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD

def find_repo():
    candidates=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    seen=set()
    for c in candidates:
        c=c.resolve()
        if c in seen: continue
        seen.add(c)
        if (c/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'/'requirement_term_index.json').exists():
            return c
    raise RuntimeError('Could not locate NLTL_v2 repository root')

REPO=find_repo()
ROOT=REPO/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'
R13=REPO/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'
INDEX=json.loads((R13/'requirement_term_index.json').read_text())
REGISTRY=json.loads((R13/'registry'/'term_registry.json').read_text())
REG={x['localName']:x for x in REGISTRY}
CONTRACTS=INDEX['dependencyContracts']
NLTL=Namespace('https://w3id.org/nltl/vocab#')
QUDT=Namespace('http://qudt.org/schema/qudt/')
UNIT=Namespace('http://qudt.org/vocab/unit/')
ONTOLOGY=Graph().parse(R13/'ontology'/'nltl_benchmark_vocabulary.ttl',format='turtle')
KNOWN={str(s).split('#',1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL)) and '#' in str(s)}

def new_graph(base, case_id):
    g=Graph(); ex=Namespace(base+case_id+'/')
    g.bind('ex',ex);g.bind('nltl',NLTL);g.bind('qudt',QUDT);g.bind('unit',UNIT);g.bind('xsd',XSD)
    ship=ex.ship; g.add((ship,RDF.type,NLTL.ship))
    return g,ex,ship

def add_value(g,s,term,value,ex,name=None,unit_override=None):
    row=REG.get(term)
    if row is None:
        raise RuntimeError(f'Unknown R13 registry term: {term}')
    kind=row['kind']
    if kind=='QuantityProperty':
        q=ex[name or term+'Value']
        g.add((q,RDF.type,QUDT.QuantityValue))
        g.add((q,QUDT.numericValue,Literal(str(value),datatype=XSD.decimal)))
        unit=unit_override or row.get('unitIri') or str(UNIT.UNITLESS)
        g.add((q,QUDT.unit,URIRef(str(unit))))
        g.add((s,NLTL[term],q))
        return q
    if kind=='DatatypeProperty':
        dt={'xsd:boolean':XSD.boolean,'xsd:string':XSD.string,'xsd:integer':XSD.integer,'xsd:decimal':XSD.decimal,'xsd:date':XSD.date}.get(row.get('datatype'))
        if dt is None: raise RuntimeError(f'Unsupported datatype for {term}: {row.get("datatype")}')
        g.add((s,NLTL[term],Literal(value,datatype=dt)))
        return None
    if kind=='ObjectProperty':
        g.add((s,NLTL[term],value)); return value
    raise RuntimeError(f'Cannot add value for kind {kind}: {term}')

def add_raw_object(g,s,term,obj):
    g.add((s,NLTL[term],obj)); return obj

def typed(ex,g,name,cls):
    o=ex[name]; g.add((o,RDF.type,NLTL[cls])); return o

def link(g,s,term,ex,name,cls):
    o=typed(ex,g,name,cls)
    if term in REG: add_value(g,s,term,o,ex)
    else: add_raw_object(g,s,term,o)
    return o

def one(g,s,term):
    xs=list(g.objects(s,NLTL[term]))
    return xs[0] if len(xs)==1 else None

def lit(g,s,term):
    o=one(g,s,term)
    if o is None: return None
    try: return o.toPython()
    except: return None

def qnum(g,s,term,expected_unit=None):
    q=one(g,s,term)
    if q is None: return None
    ns=list(g.objects(q,QUDT.numericValue)); us=list(g.objects(q,QUDT.unit))
    if len(ns)!=1 or len(us)!=1: return None
    unit=expected_unit or (REG.get(term) or {}).get('unitIri')
    if unit and str(us[0])!=str(unit): return None
    try: return float(ns[0])
    except: return None

def close(a,b,tol=1e-8):
    return a is not None and b is not None and math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol)

def graph_vocab_ok(g):
    unknown=set()
    for s,p,o in g:
        for n in (s,p,o):
            st=str(n)
            if st.startswith(str(NLTL)) and '#' in st:
                local=st.split('#',1)[1]
                if local not in KNOWN: unknown.add(local)
    return not unknown,sorted(unknown)

def graph_qudt_ok(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1: return False
        if len(list(g.objects(q,QUDT.unit)))!=1: return False
    return True

def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_batch(manifest_name,lock_name,oracles,check_hashes=True):
    mp=ROOT/'manifests'/manifest_name; lp=ROOT/'locks'/lock_name
    if not mp.exists(): raise SystemExit(f'Manifest missing: {mp}')
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]
    syntax=vocab=qudt=agreement=0; diagnostics=[]
    for row in rows:
        p=ROOT/row['rdf_path']
        try:
            g=Graph().parse(p,format='turtle'); syntax+=1
        except Exception as e:
            diagnostics.append((row['case_id'],'parse',str(e))); continue
        ok,unknown=graph_vocab_ok(g)
        if ok:vocab+=1
        else:diagnostics.append((row['case_id'],'vocab',unknown))
        if graph_qudt_ok(g):qudt+=1
        else:diagnostics.append((row['case_id'],'QUDT','invalid QuantityValue'))
        actual='PASS' if oracles[row['requirement_id']](g) else 'FAIL'
        if actual==row['expected']:agreement+=1
        else:diagnostics.append((row['case_id'],'oracle',f"expected={row['expected']} actual={actual}"))
    hash_ok=True
    if check_hashes:
        if not lp.exists():
            hash_ok=False; diagnostics.append(('lock','hash','lock missing'))
        else:
            lock=json.loads(lp.read_text())
            for rel,expected in lock.get('frozen_files',{}).items():
                p=ROOT/rel
                if not p.exists() or sha256(p)!=expected:
                    hash_ok=False; diagnostics.append((rel,'hash','mismatch'))
    n=len(rows)
    print(f"Requirements: {len(set(r['requirement_id'] for r in rows))}")
    print(f"RDF files: {n}")
    print(f"Syntactically valid: {syntax}")
    print(f"Vocabulary validation count: {vocab}")
    print(f"QUDT/unit validation count: {qudt}")
    print(f"Source-oracle agreement count: {agreement}")
    if check_hashes: print('Frozen hashes matched: '+('YES' if hash_ok else 'NO'))
    ok=syntax==vocab==qudt==agreement==n and (hash_ok if check_hashes else True)
    print('Overall status: '+('PASS' if ok else 'FAIL'))
    if diagnostics:
        print('\nDiagnostics:')
        for d in diagnostics: print(d)
    return ok

def generate_batch(*,base,reqs,modes,cases,oracles,clauses,source_id,batch_label,manifest_name,lock_name,validator_name,family):
    for r in reqs:
        assert CONTRACTS[r]['status']=='COMPLETE',r
        assert CONTRACTS[r]['verificationMode']==modes[r],(r,CONTRACTS[r]['verificationMode'],modes[r])
        if modes[r]=='COMPLEX_READINESS':
            assert CONTRACTS[r].get('formulaExecutionRequired') is False,r
    for p in [ROOT/'rdf'/family,ROOT/'specifications'/family,ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:
        p.mkdir(parents=True,exist_ok=True)
    lp=ROOT/'locks'/lock_name
    if lp.exists(): raise SystemExit(f'{batch_label} lock already exists. Refusing to overwrite frozen fixtures.')
    rows=[]
    for c in cases:
        req=c['requirement_id']; od=ROOT/'rdf'/family/req; od.mkdir(parents=True,exist_ok=True)
        p=od/f"{c['case_id']}.ttl"
        if p.exists(): raise SystemExit(f'Refusing to overwrite existing RDF fixture: {p}')
        c['graph'].serialize(destination=p,format='turtle')
        rows.append({
            'requirement_id':req,'case_id':c['case_id'],'expected':c['expected'],
            'rdf_path':str(p.relative_to(ROOT)),'source_id':source_id,'source_clause':clauses[req],
            'verification_mode':modes[req],'source_oracle_rationale':c['rationale'],
            'generated_shacl_inspected':False,
        })
    mp=ROOT/'manifests'/manifest_name
    mp.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    for req in reqs:
        sp=ROOT/'specifications'/family/f'{req}.json'
        if sp.exists(): raise SystemExit(f'Refusing to overwrite existing specification: {sp}')
        sp.write_text(json.dumps({
            'requirement_id':req,'source_id':source_id,'source_clause':clauses[req],
            'source_lock_id':INDEX['sourceLockId'],'r13_contract':CONTRACTS[req],
            'test_cases':[{'case_id':x['case_id'],'expected':x['expected'],'rationale':x['rationale']} for x in cases if x['requirement_id']==req],
            'benchmark_policy':'Source/R13-defined behavioral oracle created without inspecting generated SHACL.'
        },indent=2)+'\n')
    print('Pre-freeze validation'); assert validate_batch(manifest_name,lock_name,oracles,False)
    vp=ROOT/'scripts'/validator_name; shutil.copy2(Path(__file__).resolve(),vp); vp.chmod(0o755)
    frozen={}
    for c in cases:
        p=ROOT/'rdf'/family/c['requirement_id']/f"{c['case_id']}.ttl"
        frozen[str(p.relative_to(ROOT))]=sha256(p)
    frozen[str(mp.relative_to(ROOT))]=sha256(mp)
    for req in reqs:
        p=ROOT/'specifications'/family/f'{req}.json'; frozen[str(p.relative_to(ROOT))]=sha256(p)
    lp.write_text(json.dumps({
        'benchmark':batch_label,'source_lock_id':INDEX['sourceLockId'],'source_id':source_id,
        'requirements':reqs,'requirement_count':len(reqs),'case_count':len(cases),
        'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,
        'frozen_files':frozen
    },indent=2)+'\n')
    print('\nFrozen validation'); assert validate_batch(manifest_name,lock_name,oracles,True)



BASE='https://w3id.org/nltl/benchmark/imo-batch-n/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-120','IMO-121','IMO-122','IMO-123','IMO-124','IMO-125']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={r:f'Part II-A {cl}' for r,cl in {
 'IMO-120':'5.2.1.1','IMO-121':'5.2.1.2','IMO-122':'5.2.1.3-.4','IMO-123':'5.2.1.5','IMO-124':'5.2.2.1-.2','IMO-125':'5.2.3'}.items()}

def case(req,cid,expected,graph,rationale):return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid):return new_graph(BASE,cid)
def objs(g,s,t):return list(g.objects(s,NLTL[t]))

def b120(cid,area='Arctic waters',arctic='Arctic waters',discharge=True,distance=12,near=2,record=1,omit=None):
 g,ex,s=shipg(cid);vals={'operatingArea':area,'arcticWaters':arctic,'foodWasteDischargeToSea':discharge}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='distanceToNearestLandIceShelfOrFastIce':add_value(g,s,'distanceToNearestLandIceShelfOrFastIce',distance,ex)
 if omit!='nearbyIceConcentration':add_value(g,s,'nearbyIceConcentration',near,ex)
 if omit!='distanceFromAreaWithIceConcentrationAboveOneTenth':add_value(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth',record,ex)
 return g
def o120(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 a=lit(g,s,'operatingArea');ar=lit(g,s,'arcticWaters');dis=lit(g,s,'foodWasteDischargeToSea')
 if a is None or ar is None or dis is None:return False
 if a!=ar or dis is False:return True
 d=qnum(g,s,'distanceToNearestLandIceShelfOrFastIce');near=qnum(g,s,'nearbyIceConcentration');rec=qnum(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth')
 return d is not None and d>=12 and near is not None and rec is not None

def b121(cid,discharge=True,ground=True,screen=25,contam=False,omit=None):
 g,ex,s=shipg(cid);vals={'foodWasteDischargeToSea':discharge,'foodWasteComminutedOrGround':ground,'contaminatedByOtherGarbage':contam}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='requiredScreenOpening':add_value(g,s,'requiredScreenOpening',screen,ex)
 return g
def o121(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 d=lit(g,s,'foodWasteDischargeToSea')
 if d is None:return False
 if d is False:return True
 return lit(g,s,'foodWasteComminutedOrGround') is True and qnum(g,s,'requiredScreenOpening') is not None and qnum(g,s,'requiredScreenOpening')<=25 and lit(g,s,'contaminatedByOtherGarbage') is False

def b122(cid,food=False,animal=False,omit=None):
 g,ex,s=shipg(cid)
 if omit!='foodWasteDischargeOntoIce':add_value(g,s,'foodWasteDischargeOntoIce',food,ex)
 if omit!='animalCarcassDischarge':add_value(g,s,'animalCarcassDischarge',animal,ex)
 return g
def o122(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 return s is not None and lit(g,s,'foodWasteDischargeOntoIce') is False and lit(g,s,'animalCarcassDischarge') is False

def b123(cid,residue=True,enroute=True,harmful=False,ports=True,route=True,reception=False,distance=12,near=2,record=1,omit=None,wrong_owner=False):
 g,ex,s=shipg(cid);vals={'residueNotRecoverableByCommonMethods':residue,'shipEnRoute':enroute,'harmfulSubstancePresent':harmful,'departureAndDestinationWithinArctic':ports,'routeRemainsWithinArctic':route,'adequateReceptionFacilitiesAvailable':reception,'nearbyIceConcentration':near}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 rec=typed(ex,g,'distanceRecord','dischargeDistanceRecords')
 if omit!='hasDischargeDistanceRecord':add_value(g,s,'hasDischargeDistanceRecord',rec,ex)
 owner=s if wrong_owner else rec
 if omit!='distanceToNearestLandIceShelfOrFastIce':add_value(g,owner,'distanceToNearestLandIceShelfOrFastIce',distance,ex)
 if omit!='distanceToAreaWithIceConcentrationGreaterThanOneTenth':add_value(g,owner,'distanceToAreaWithIceConcentrationGreaterThanOneTenth',record,ex)
 return g
def o123(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 checks={'residueNotRecoverableByCommonMethods':True,'shipEnRoute':True,'harmfulSubstancePresent':False,'departureAndDestinationWithinArctic':True,'routeRemainsWithinArctic':True,'adequateReceptionFacilitiesAvailable':False}
 for t,v in checks.items():
  if lit(g,s,t) is not v:return False
 if qnum(g,s,'nearbyIceConcentration') is None:return False
 rs=objs(g,s,'hasDischargeDistanceRecord')
 if len(rs)!=1:return False
 return qnum(g,rs[0],'distanceToNearestLandIceShelfOrFastIce') is not None and qnum(g,rs[0],'distanceToNearestLandIceShelfOrFastIce')>=12 and qnum(g,rs[0],'distanceToAreaWithIceConcentrationGreaterThanOneTenth') is not None

def b124(cid,area='Antarctic area',antarctic='Antarctic area',occurs=True,distance=12,near=2,record=1,onto=False,omit=None):
 g,ex,s=shipg(cid);vals={'operatingArea':area,'antarcticArea':antarctic,'marpolAnnexVRegulation6Point1DischargeOccurs':occurs,'foodWasteDischargeOntoIce':onto}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='distanceToNearestFastIce':add_value(g,s,'distanceToNearestFastIce',distance,ex)
 if omit!='nearbyIceConcentration':add_value(g,s,'nearbyIceConcentration',near,ex)
 if omit!='distanceFromAreaWithIceConcentrationAboveOneTenth':add_value(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth',record,ex)
 return g
def o124(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 a=lit(g,s,'operatingArea');ant=lit(g,s,'antarcticArea');occ=lit(g,s,'marpolAnnexVRegulation6Point1DischargeOccurs')
 if a is None or ant is None or occ is None:return False
 if a!=ant or occ is False:return True
 d=qnum(g,s,'distanceToNearestFastIce');near=qnum(g,s,'nearbyIceConcentration');rec=qnum(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth')
 return d is not None and d>=12 and near is not None and rec is not None and lit(g,s,'foodWasteDischargeOntoIce') is False

def b125(cid,polar=True,overall=True,book=True,plan=True,placard=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipOperatesInPolarWaters':polar,'polarOperationCoverage':overall,'garbageRecordBookPolarCoverage':book,'garbageManagementPlanPolarCoverage':plan,'garbagePlacardPolarCoverage':placard}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o125(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 p=lit(g,s,'shipOperatesInPolarWaters')
 if p is None:return False
 if p is False:return True
 return all(lit(g,s,t) is True for t in ['polarOperationCoverage','garbageRecordBookPolarCoverage','garbageManagementPlanPolarCoverage','garbagePlacardPolarCoverage'])

ORACLES={'IMO-120':o120,'IMO-121':o121,'IMO-122':o122,'IMO-123':o123,'IMO-124':o124,'IMO-125':o125}
CASES=[]
for cid,exp,kw,rat in [
 ('IMO-120-N-P01','PASS',{},'Arctic food-waste discharge at inclusive 12 nm boundary with distinct ice-concentration distance record.'),('IMO-120-N-P02','PASS',{'distance':20},'Distance above 12 nm minimum.'),('IMO-120-N-F01','FAIL',{'distance':11.99},'Distance below 12 nm minimum.'),('IMO-120-N-F02','FAIL',{'omit':'distanceFromAreaWithIceConcentrationAboveOneTenth'},'Ice-concentration-area distance record missing.'),('IMO-120-N-F03','FAIL',{'omit':'distanceToNearestLandIceShelfOrFastIce'},'Nearest land/ice shelf/fast ice distance missing.'),('IMO-120-N-P03','PASS',{'discharge':False,'distance':0},'No food-waste discharge to sea; conditional distance rule not applicable.'),('IMO-120-N-P04','PASS',{'area':'Baltic Sea','distance':0},'Outside Arctic waters.'),('IMO-120-N-F04','FAIL',{'omit':'operatingArea'},'Operating-area applicability selector missing.')]:CASES.append(case('IMO-120',cid,exp,b120(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-121-N-P01','PASS',{},'Food waste is comminuted/ground, screen opening exactly 25 mm, and uncontaminated.'),('IMO-121-N-P02','PASS',{'screen':10},'Screen opening smaller than maximum.'),('IMO-121-N-F01','FAIL',{'ground':False},'Food waste not comminuted or ground.'),('IMO-121-N-F02','FAIL',{'screen':25.1},'Screen opening exceeds 25 mm.'),('IMO-121-N-F03','FAIL',{'contam':True},'Food waste contaminated by another garbage type.'),('IMO-121-N-P03','PASS',{'discharge':False,'ground':False,'screen':100,'contam':True},'No food-waste discharge to sea; conditional preparation constraints not applicable.'),('IMO-121-N-F04','FAIL',{'omit':'requiredScreenOpening'},'Required screen-opening quantity missing.'),('IMO-121-N-F05','FAIL',{'omit':'foodWasteDischargeToSea'},'Discharge applicability state missing.')]:CASES.append(case('IMO-121',cid,exp,b121(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-122-N-P01','PASS',{},'Neither food waste onto ice nor animal carcass discharge occurs.'),('IMO-122-N-F01','FAIL',{'food':True},'Food waste discharged onto ice.'),('IMO-122-N-F02','FAIL',{'animal':True},'Animal carcass discharge occurs.'),('IMO-122-N-F03','FAIL',{'food':True,'animal':True},'Both prohibitions violated.'),('IMO-122-N-F04','FAIL',{'omit':'foodWasteDischargeOntoIce'},'Food-waste-on-ice state missing.'),('IMO-122-N-F05','FAIL',{'omit':'animalCarcassDischarge'},'Animal-carcass discharge state missing.')]:CASES.append(case('IMO-122',cid,exp,b122(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-123-N-P01','PASS',{},'All Arctic cargo-residue discharge conditions satisfied at inclusive 12 nm boundary with ice-concentration distance record.'),('IMO-123-N-P02','PASS',{'distance':25,'record':8},'All conditions satisfied above distance boundary.'),('IMO-123-N-F01','FAIL',{'residue':False},'Residue is recoverable by commonly available unloading methods.'),('IMO-123-N-F02','FAIL',{'enroute':False},'Ship is not en route.'),('IMO-123-N-F03','FAIL',{'harmful':True},'Harmful substance is present.'),('IMO-123-N-F04','FAIL',{'ports':False},'Departure/destination are not both within Arctic waters.'),('IMO-123-N-F05','FAIL',{'route':False},'Route transits outside Arctic waters.'),('IMO-123-N-F06','FAIL',{'reception':True},'Adequate reception facilities are available.'),('IMO-123-N-F07','FAIL',{'distance':11.99},'Distance to nearest land/ice shelf/fast ice below 12 nm.'),('IMO-123-N-F08','FAIL',{'omit':'distanceToAreaWithIceConcentrationGreaterThanOneTenth'},'Required recorded distance from >1/10 ice-concentration area missing.'),('IMO-123-N-F09','FAIL',{'omit':'hasDischargeDistanceRecord'},'Ship-to-discharge-distance-record path missing.'),('IMO-123-N-F10','FAIL',{'wrong_owner':True},'Distance values attached to ship rather than linked discharge-distance record.')]:CASES.append(case('IMO-123',cid,exp,b123(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-124-N-P01','PASS',{},'Antarctic MARPOL Annex V 6.1 discharge at inclusive 12 nm fast-ice boundary, with ice-area record and no food waste onto ice.'),('IMO-124-N-P02','PASS',{'distance':20},'Compliant Antarctic discharge above minimum distance.'),('IMO-124-N-F01','FAIL',{'distance':11.99},'Distance to nearest fast ice below 12 nm.'),('IMO-124-N-F02','FAIL',{'onto':True},'Food waste is discharged onto ice.'),('IMO-124-N-F03','FAIL',{'omit':'distanceFromAreaWithIceConcentrationAboveOneTenth'},'Ice-concentration-area distance record missing.'),('IMO-124-N-P03','PASS',{'occurs':False,'distance':0,'onto':True},'No MARPOL Annex V 6.1 discharge occurs; conditional branch not applicable.'),('IMO-124-N-P04','PASS',{'area':'Arctic waters','distance':0,'onto':True},'Outside Antarctic area.'),('IMO-124-N-F04','FAIL',{'omit':'operatingArea'},'Operating-area selector missing.')]:CASES.append(case('IMO-124',cid,exp,b124(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-125-N-P01','PASS',{},'Garbage Record Book, Garbage Management Plan, placards and overall polar-operation coverage all present.'),('IMO-125-N-P02','PASS',{'polar':False,'overall':False,'book':False,'plan':False,'placard':False},'Ship does not operate in polar waters.'),('IMO-125-N-F01','FAIL',{'book':False},'Garbage Record Book polar coverage missing.'),('IMO-125-N-F02','FAIL',{'plan':False},'Garbage Management Plan polar coverage missing.'),('IMO-125-N-F03','FAIL',{'placard':False},'Garbage placard polar coverage missing.'),('IMO-125-N-F04','FAIL',{'overall':False},'Overall polar-operation coverage false.'),('IMO-125-N-F05','FAIL',{'omit':'shipOperatesInPolarWaters'},'Polar-operation applicability state missing.')]:CASES.append(case('IMO-125',cid,exp,b125(cid,**kw),rat))

MANIFEST='imo_batch_n_manifest.jsonl';LOCK='imo_batch_n_fixture_lock.json';VALIDATOR='validate_imo_batch_n.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch N',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
