
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

BASE='https://w3id.org/nltl/benchmark/imo-batch-a/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-001','IMO-002','IMO-003','IMO-004','IMO-005','IMO-006','IMO-007','IMO-008','IMO-009','IMO-010','IMO-011','IMO-012','IMO-013']
MODES={r:'DIRECT_STATIC' for r in REQS}
MODES['IMO-011']='COMPLEX_READINESS'; MODES['IMO-012']='DIRECT_CALCULATION'
CLAUSES={'IMO-001':'Introduction 2.1','IMO-002':'Introduction 2.2','IMO-003':'Introduction 2.3','IMO-004':'Introduction 2.4',
'IMO-005':'Introduction 2.5','IMO-006':'Introduction 2.8','IMO-007':'Introduction 2.10','IMO-008':'Introduction 2.15',
'IMO-009':'Part I-A 1.2.1','IMO-010':'Part I-A 1.2.7','IMO-011':'Part I-A 1.2.9','IMO-012':'Part I-A 1.2.11','IMO-013':'Part I-A 1.2.12'}

def build001(cid,cond=NLTL.mediumFirstYearIceWithPossibleOldIceInclusions,cat=NLTL.polarShipCategoryA,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='designIceCondition':add_value(g,s,'designIceCondition',cond,ex)
    if omit!='shipCategory' and cat is not None:add_value(g,s,'shipCategory',cat,ex)
    return g
def oracle001(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); cond=one(g,s,'designIceCondition'); cat=one(g,s,'shipCategory')
    if cond is None:return False
    if cond==NLTL.mediumFirstYearIceWithPossibleOldIceInclusions:return cat==NLTL.polarShipCategoryA
    return True

def build002(cid,cond=NLTL.thinFirstYearIceWithPossibleOldIceInclusions,cat=NLTL.polarShipCategoryB,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='designIceCondition':add_value(g,s,'designIceCondition',cond,ex)
    if omit!='shipCategory' and cat is not None:add_value(g,s,'shipCategory',cat,ex)
    return g
def oracle002(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cond=one(g,s,'designIceCondition');cat=one(g,s,'shipCategory')
    if cond is None:return False
    if cond==NLTL.thinFirstYearIceWithPossibleOldIceInclusions:
        if cat is None:return False
        if cat==NLTL.polarShipCategoryA:return True
        return cat==NLTL.polarShipCategoryB
    return True

def build003(cid,cond=NLTL.openWaterIceCondition,cat=NLTL.polarShipCategoryC,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='designIceCondition':add_value(g,s,'designIceCondition',cond,ex)
    if omit!='shipCategory' and cat is not None:add_value(g,s,'shipCategory',cat,ex)
    return g
def oracle003(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cond=one(g,s,'designIceCondition');cat=one(g,s,'shipCategory')
    if cond is None:return False
    if cond in {NLTL.openWaterIceCondition,NLTL.iceConditionLessSevereThanCategoryAAndB}:return cat==NLTL.polarShipCategoryC
    return True

def build004(cid,origin=NLTL.seaIceOrigin,growth=1,thickness=.3,classification=NLTL.firstYearIce,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceOriginType':add_value(g,s,'iceOriginType',origin,ex)
    if omit!='winterGrowthCount':add_value(g,s,'winterGrowthCount',growth,ex)
    if omit!='iceThickness':add_value(g,s,'iceThickness',thickness,ex)
    if omit!='iceTypeClassification' and classification is not None:add_value(g,s,'iceTypeClassification',classification,ex)
    return g
def oracle004(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);origin=one(g,s,'iceOriginType');growth=lit(g,s,'winterGrowthCount');th=qnum(g,s,'iceThickness');cl=one(g,s,'iceTypeClassification')
    if origin is None or growth is None or th is None:return False
    if origin==NLTL.seaIceOrigin and growth<=1 and .3<=th<=2.0:return cl==NLTL.firstYearIce
    return True

def build005(cid,condition='ice free waters',present=False,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceCondition':add_value(g,s,'iceCondition',condition,ex)
    if omit!='totalIcePresent' and present is not None:add_value(g,s,'totalIcePresent',present,ex)
    return g
def oracle005(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);c=lit(g,s,'iceCondition');p=lit(g,s,'totalIcePresent')
    if c is None:return False
    if str(c).strip().lower()=='ice free waters':return p is False
    return True

def build006(cid,classification=NLTL.mediumFirstYearIce,thickness=.7,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceTypeClassification':add_value(g,s,'iceTypeClassification',classification,ex)
    if omit!='iceThickness':add_value(g,s,'iceThickness',thickness,ex)
    return g
def oracle006(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cl=one(g,s,'iceTypeClassification');th=qnum(g,s,'iceThickness')
    if cl is None:return False
    if cl==NLTL.mediumFirstYearIce:return th is not None and .7<=th<=1.2
    return True

def build007(cid,classification=NLTL.openWaterIceCondition,conc=.9,land=False,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceConditionClassification':add_value(g,s,'iceConditionClassification',classification,ex)
    if omit!='seaIceConcentration':add_value(g,s,'seaIceConcentration',conc,ex)
    if omit!='iceOfLandOriginPresent':add_value(g,s,'iceOfLandOriginPresent',land,ex)
    return g
def oracle007(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cl=one(g,s,'iceConditionClassification')
    if cl is None:return False
    if cl==NLTL.openWaterIceCondition:
        c=qnum(g,s,'seaIceConcentration');land=lit(g,s,'iceOfLandOriginPresent')
        return c is not None and c<1 and land is False
    return True

def build008(cid,classification=NLTL.thinFirstYearIce,thickness=.3,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceTypeClassification':add_value(g,s,'iceTypeClassification',classification,ex)
    if omit!='iceThickness':add_value(g,s,'iceThickness',thickness,ex)
    return g
def oracle008(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cl=one(g,s,'iceTypeClassification');th=qnum(g,s,'iceThickness')
    if cl is None:return False
    if cl==NLTL.thinFirstYearIce:return th is not None and .3<=th<=.7
    return True

def build009(cid,condition='bergy waters',land=.5,total=1.0,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceCondition':add_value(g,s,'iceCondition',condition,ex)
    if omit!='landOriginIceConcentration':add_value(g,s,'landOriginIceConcentration',land,ex)
    if omit!='totalIceConcentration':add_value(g,s,'totalIceConcentration',total,ex)
    return g
def oracle009(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);c=lit(g,s,'iceCondition')
    if c is None:return False
    if str(c).strip().lower()=='bergy waters':
        land=qnum(g,s,'landOriginIceConcentration');total=qnum(g,s,'totalIceConcentration')
        return land is not None and total is not None and land<1 and total<=1
    return True

def build010(cid,days=5,omit=False):
    g,ex,s=new_graph(BASE,cid)
    if not omit:add_value(g,s,'maximumExpectedRescueTime',days,ex)
    return g
def oracle010(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);d=qnum(g,s,'maximumExpectedRescueTime')
    return d is not None and d>=5

def build011(cid,years=10,approved=None,missing=None,orphan=False):
    g,ex,s=new_graph(BASE,cid)
    if missing!='dataPeriod':add_value(g,s,'dataPeriod',years,ex)
    if missing!='meanDailyLowTemperature':add_value(g,s,'meanDailyLowTemperature',-20,ex)
    obs=typed(ex,g,'obs1','dailyLowTemperatureObservation')
    if not orphan:add_value(g,s,'hasDailyLowTemperatureObservation',obs,ex)
    if missing!='dailyTemperatureObservationDate':add_value(g,obs,'dailyTemperatureObservationDate','2025-01-15',ex)
    if missing!='dailyLowTemperature':add_value(g,obs,'dailyLowTemperature',-25,ex)
    if approved is not None and missing!='administrationDatasetApprovalStatus':
        add_value(g,s,'administrationDatasetApprovalStatus',NLTL.evidenceStateApproved if approved else ex.notApproved,ex)
    return g
def oracle011(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);years=qnum(g,s,'dataPeriod');mean=qnum(g,s,'meanDailyLowTemperature')
    if years is None or mean is None:return False
    obs=list(g.objects(s,NLTL.hasDailyLowTemperatureObservation))
    if not obs:return False
    for o in obs:
        if lit(g,o,'dailyTemperatureObservationDate') is None or qnum(g,o,'dailyLowTemperature') is None:return False
    if years<10:return one(g,s,'administrationDatasetApprovalStatus')==NLTL.evidenceStateApproved
    return True

def build012(cid,mdlt=-20,pst=-30,omit=None,wrong_unit=False):
    g,ex,s=new_graph(BASE,cid)
    if omit!='lowestMdlt':add_value(g,s,'lowestMdlt',mdlt,ex,unit_override=UNIT.K if wrong_unit and omit!='lowestMdlt' else None)
    if omit!='polarServiceTemperature':add_value(g,s,'polarServiceTemperature',pst,ex)
    return g
def oracle012(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);m=qnum(g,s,'lowestMdlt');p=qnum(g,s,'polarServiceTemperature')
    return m is not None and p is not None and p<=m-10+1e-12

def build013(cid,mdlt=-10.1,flag=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='lowestMdlt':add_value(g,s,'lowestMdlt',mdlt,ex)
    if omit!='shipOperatesInLowAirTemperature':add_value(g,s,'shipOperatesInLowAirTemperature',flag,ex)
    return g
def oracle013(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);m=qnum(g,s,'lowestMdlt');f=lit(g,s,'shipOperatesInLowAirTemperature')
    return m is not None and isinstance(f,bool) and f==(m<-10)

ORACLES={'IMO-001':oracle001,'IMO-002':oracle002,'IMO-003':oracle003,'IMO-004':oracle004,'IMO-005':oracle005,'IMO-006':oracle006,'IMO-007':oracle007,'IMO-008':oracle008,'IMO-009':oracle009,'IMO-010':oracle010,'IMO-011':oracle011,'IMO-012':oracle012,'IMO-013':oracle013}
CASES=[]
def ac(req,suf,exp,rat,g):CASES.append({'requirement_id':req,'case_id':f'{req}-{suf}','expected':exp,'rationale':rat,'graph':g})

# Category definitions.
ac('IMO-001','P01','PASS','Medium first-year design condition maps to category A.',build001('IMO-001-P01'))
ac('IMO-001','P02','PASS','Different design condition does not activate category-A implication.',build001('IMO-001-P02',NLTL.openWaterIceCondition,NLTL.polarShipCategoryC))
ac('IMO-001','F01','FAIL','Medium first-year condition incorrectly categorized C.',build001('IMO-001-F01',cat=NLTL.polarShipCategoryC))
ac('IMO-001','F02','FAIL','Applicable category value missing.',build001('IMO-001-F02',cat=None))
ac('IMO-001','F03','FAIL','Design-ice-condition selector missing.',build001('IMO-001-F03',omit='designIceCondition'))

ac('IMO-002','P01','PASS','Thin first-year design condition maps non-category-A ship to category B.',build002('IMO-002-P01'))
ac('IMO-002','P02','PASS','Category A ship is outside the not-category-A branch.',build002('IMO-002-P02',cat=NLTL.polarShipCategoryA))
ac('IMO-002','P03','PASS','Different design condition does not activate category-B implication.',build002('IMO-002-P03',NLTL.openWaterIceCondition,NLTL.polarShipCategoryC))
ac('IMO-002','F01','FAIL','Thin first-year non-A ship incorrectly categorized C.',build002('IMO-002-F01',cat=NLTL.polarShipCategoryC))
ac('IMO-002','F02','FAIL','Thin first-year branch lacks category evidence.',build002('IMO-002-F02',cat=None))

ac('IMO-003','P01','PASS','Open-water design condition maps to category C.',build003('IMO-003-P01'))
ac('IMO-003','P02','PASS','Less-severe-than-A/B condition maps to category C.',build003('IMO-003-P02',NLTL.iceConditionLessSevereThanCategoryAAndB))
ac('IMO-003','P03','PASS','Different design condition does not activate category-C implication.',build003('IMO-003-P03',NLTL.mediumFirstYearIceWithPossibleOldIceInclusions,NLTL.polarShipCategoryA))
ac('IMO-003','F01','FAIL','Open-water design condition incorrectly categorized B.',build003('IMO-003-F01',cat=NLTL.polarShipCategoryB))
ac('IMO-003','F02','FAIL','Less-severe design condition lacks category.',build003('IMO-003-F02',NLTL.iceConditionLessSevereThanCategoryAAndB,None))
ac('IMO-003','F03','FAIL','Design condition selector missing.',build003('IMO-003-F03',omit='designIceCondition'))

for suf,th in [('P01',.3),('P02',1.0),('P03',2.0)]:
    ac('IMO-004',suf,'PASS','First-year-ice thickness boundary/interior with sea origin and one winter growth.',build004(f'IMO-004-{suf}',thickness=th))
ac('IMO-004','P04','PASS','Non-sea origin does not activate first-year classification implication.',build004('IMO-004-P04',origin=NLTL.iceOriginValue,classification=None))
ac('IMO-004','F01','FAIL','Qualifying first-year ice not classified as first-year ice.',build004('IMO-004-F01',classification=NLTL.mediumFirstYearIce))
ac('IMO-004','F02','FAIL','Qualifying case lacks classification evidence.',build004('IMO-004-F02',classification=None))
ac('IMO-004','F03','FAIL','Thickness required to evaluate first-year definition is missing.',build004('IMO-004-F03',omit='iceThickness'))

ac('IMO-005','P01','PASS','Ice-free waters with no ice present.',build005('IMO-005-P01'))
ac('IMO-005','P02','PASS','Different ice condition is not constrained by ice-free implication.',build005('IMO-005-P02','open water',True))
ac('IMO-005','F01','FAIL','Ice-free waters label used while ice is present.',build005('IMO-005-F01',present=True))
ac('IMO-005','F02','FAIL','Ice-free waters lacks total-ice evidence.',build005('IMO-005-F02',present=None))
ac('IMO-005','F03','FAIL','Ice-condition label missing.',build005('IMO-005-F03',omit='iceCondition'))

for suf,th in [('P01',.7),('P02',1.0),('P03',1.2)]:
    ac('IMO-006',suf,'PASS','Medium first-year-ice thickness boundary/interior.',build006(f'IMO-006-{suf}',thickness=th))
ac('IMO-006','P04','PASS','Different ice type does not activate medium-first-year range.',build006('IMO-006-P04',NLTL.thinFirstYearIce,.6))
ac('IMO-006','F01','FAIL','Medium first-year ice below 0.7 m.',build006('IMO-006-F01',thickness=.69))
ac('IMO-006','F02','FAIL','Medium first-year ice above 1.2 m.',build006('IMO-006-F02',thickness=1.21))
ac('IMO-006','F03','FAIL','Medium first-year ice thickness missing.',build006('IMO-006-F03',omit='iceThickness'))

ac('IMO-007','P01','PASS','Open water with zero sea-ice concentration and no land-origin ice.',build007('IMO-007-P01',conc=0))
ac('IMO-007','P02','PASS','Open water just below 1/10 concentration and no land-origin ice.',build007('IMO-007-P02',conc=.999))
ac('IMO-007','P03','PASS','Different ice-condition classification does not activate open-water limits.',build007('IMO-007-P03',NLTL.iceConditionLessSevereThanCategoryAAndB,1.5,True))
ac('IMO-007','F01','FAIL','Open water has sea-ice concentration at 1/10.',build007('IMO-007-F01',conc=1.0))
ac('IMO-007','F02','FAIL','Open water contains land-origin ice.',build007('IMO-007-F02',conc=.5,land=True))
ac('IMO-007','F03','FAIL','Open-water concentration missing.',build007('IMO-007-F03',omit='seaIceConcentration'))
ac('IMO-007','F04','FAIL','Open-water land-origin-ice flag missing.',build007('IMO-007-F04',omit='iceOfLandOriginPresent'))

for suf,th in [('P01',.3),('P02',.5),('P03',.7)]:
    ac('IMO-008',suf,'PASS','Thin first-year-ice thickness boundary/interior.',build008(f'IMO-008-{suf}',thickness=th))
ac('IMO-008','P04','PASS','Different ice type does not activate thin-first-year range.',build008('IMO-008-P04',NLTL.mediumFirstYearIce,1.0))
ac('IMO-008','F01','FAIL','Thin first-year ice below 0.3 m.',build008('IMO-008-F01',thickness=.29))
ac('IMO-008','F02','FAIL','Thin first-year ice above 0.7 m.',build008('IMO-008-F02',thickness=.71))
ac('IMO-008','F03','FAIL','Thin first-year ice thickness missing.',build008('IMO-008-F03',omit='iceThickness'))

ac('IMO-009','P01','PASS','Bergy waters satisfies land-origin and total concentration limits.',build009('IMO-009-P01',land=.5,total=1.0))
ac('IMO-009','P02','PASS','Bergy waters with no land-origin concentration represented and total below limit.',build009('IMO-009-P02',land=0,total=.5))
ac('IMO-009','P03','PASS','Different condition does not activate bergy-waters thresholds.',build009('IMO-009-P03','open water',2,2))
ac('IMO-009','F01','FAIL','Land-origin ice concentration reaches 1/10.',build009('IMO-009-F01',land=1,total=1))
ac('IMO-009','F02','FAIL','Total ice concentration exceeds 1/10.',build009('IMO-009-F02',land=.5,total=1.1))
ac('IMO-009','F03','FAIL','Bergy-waters land-origin concentration missing.',build009('IMO-009-F03',omit='landOriginIceConcentration'))
ac('IMO-009','F04','FAIL','Bergy-waters total concentration missing.',build009('IMO-009-F04',omit='totalIceConcentration'))

for suf,d,exp in [('P01',5,'PASS'),('P02',10,'PASS'),('F01',4.99,'FAIL')]:
    ac('IMO-010',suf,exp,'Maximum expected rescue time five-day minimum boundary.',build010(f'IMO-010-{suf}',d))
ac('IMO-010','F02','FAIL','Maximum expected rescue time missing.',build010('IMO-010-F02',omit=True))

ac('IMO-011','P01','PASS','Ten-year dated observation readiness with MDLT result.',build011('IMO-011-P01',10))
ac('IMO-011','P02','PASS','Shorter approved dataset represented with Administration approval evidence.',build011('IMO-011-P02',8,True))
ac('IMO-011','P03','PASS','Longer-than-ten-year dataset requires no short-dataset approval.',build011('IMO-011-P03',12))
ac('IMO-011','F01','FAIL','Observation date missing.',build011('IMO-011-F01',10,missing='dailyTemperatureObservationDate'))
ac('IMO-011','F02','FAIL','Daily low temperature missing.',build011('IMO-011-F02',10,missing='dailyLowTemperature'))
ac('IMO-011','F03','FAIL','MDLT result missing.',build011('IMO-011-F03',10,missing='meanDailyLowTemperature'))
ac('IMO-011','F04','FAIL','Data period missing.',build011('IMO-011-F04',10,missing='dataPeriod'))
ac('IMO-011','F05','FAIL','Short dataset lacks Administration approval evidence.',build011('IMO-011-F05',8,None))
ac('IMO-011','F06','FAIL','Short dataset has non-approved evidence state.',build011('IMO-011-F06',8,False))
ac('IMO-011','F07','FAIL','Observation exists but ship-to-observation path is missing.',build011('IMO-011-F07',10,orphan=True))

ac('IMO-012','P01','PASS','PST exactly 10 C below lowest MDLT.',build012('IMO-012-P01',-20,-30))
ac('IMO-012','P02','PASS','PST more conservative than 10 C below MDLT.',build012('IMO-012-P02',-15,-30))
ac('IMO-012','F01','FAIL','PST is not at least 10 C below MDLT.',build012('IMO-012-F01',-20,-29.9))
ac('IMO-012','F02','FAIL','Lowest MDLT missing.',build012('IMO-012-F02',omit='lowestMdlt'))
ac('IMO-012','F03','FAIL','PST missing.',build012('IMO-012-F03',omit='polarServiceTemperature'))
ac('IMO-012','F04','FAIL','Lowest MDLT encoded with wrong unit.',build012('IMO-012-F04',wrong_unit=True))

for suf,m,f,exp in [('P01',-10,False,'PASS'),('P02',-10.1,True,'PASS'),('P03',-25,True,'PASS'),('P04',0,False,'PASS'),('F01',-11,False,'FAIL'),('F02',-5,True,'FAIL')]:
    ac('IMO-013',suf,exp,'Low-air-temperature classification around -10 C boundary.',build013(f'IMO-013-{suf}',m,f))
ac('IMO-013','F03','FAIL','Low-air-temperature classification result missing.',build013('IMO-013-F03',omit='shipOperatesInLowAirTemperature'))

assert len(CASES)==83,len(CASES)
MANIFEST='imo_batch_a_manifest.jsonl';LOCK='imo_batch_a_fixture_lock.json';VALIDATOR='validate_imo_batch_a.py'
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Behavioral Benchmark Batch A',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
