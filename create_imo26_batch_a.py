
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
    for p in [ROOT/'rdf'/family,ROOT/'specifications'/family/'systematic',ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:
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
        sp=ROOT/'specifications'/family/'systematic'/f'{req}.json'
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
        p=ROOT/'specifications'/family/'systematic'/f'{req}.json'; frozen[str(p.relative_to(ROOT))]=sha256(p)
    lp.write_text(json.dumps({
        'benchmark':batch_label,'source_lock_id':INDEX['sourceLockId'],'source_id':source_id,
        'requirements':reqs,'requirement_count':len(reqs),'case_count':len(cases),
        'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,
        'frozen_files':frozen
    },indent=2)+'\n')
    print('\nFrozen validation'); assert validate_batch(manifest_name,lock_name,oracles,True)




BASE='https://w3id.org/nltl/benchmark/imo26-batch-a/'
SOURCE_ID='SRC-IMO26-SUPPLEMENT'
REQS=['IMO26-001','IMO26-002','IMO26-005','IMO26-007','IMO26-008','IMO26-009','IMO26-010','IMO26-011','IMO26-012','IMO26-013','IMO26-014']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
 'IMO26-001':'MSC.538(107) Amendment 2 - Chapter 9 applicability',
 'IMO26-002':'Chapter 9-1 applicability',
 'IMO26-005':'9-1.2.2.2',
 'IMO26-007':'9-1.3.2.1.1',
 'IMO26-008':'9-1.3.2.1.2',
 'IMO26-009':'9-1.3.2.1.3',
 'IMO26-010':'9-1.3.2.1.4.1',
 'IMO26-011':'9-1.3.2.1.4.2',
 'IMO26-012':'9-1.3.2.2.1',
 'IMO26-013':'9-1.3.2.2.2',
 'IMO26-014':'9-1.3.3',
}
APPROVED=NLTL.evidenceStateApproved
REJECTED=NLTL.evidenceStateRejected
CAT_A=NLTL.polarShipCategoryA
CAT_B=NLTL.polarShipCategoryB
CAT_C=NLTL.polarShipCategoryC

def case(req,cid,expected,graph,rationale):
    return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid): return new_graph(BASE,cid)
def vals(g,s,term): return list(g.objects(s,NLTL[term]))

def b001(cid,cert=True,app=True,omit=None):
    g,ex,s=shipg(cid)
    for t,v in {'solasChapterICertified':cert,'polarCodeChapter9Applicable':app}.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o001(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    cert=lit(g,s,'solasChapterICertified');app=lit(g,s,'polarCodeChapter9Applicable')
    return cert is not None and app is not None and app is cert

def b002(cid,stype='fishing_vessel',length=24,gt=300,trade=False,app=True,omit=None):
    g,ex,s=shipg(cid)
    if omit!='shipType':add_value(g,s,'shipType',stype,ex)
    if omit!='lengthOverall':add_value(g,s,'lengthOverall',length,ex)
    if omit!='grossTonnage':add_value(g,s,'grossTonnage',gt,ex)
    if omit!='engagedInTrade':add_value(g,s,'engagedInTrade',trade,ex)
    if omit!='polarCodeChapter9Dash1Applicable':add_value(g,s,'polarCodeChapter9Dash1Applicable',app,ex)
    return g
def calc_ch9_1(g,s):
    st=lit(g,s,'shipType')
    if st is None:return None
    if st=='fishing_vessel':
        L=qnum(g,s,'lengthOverall')
        return None if L is None else L>=24
    if st=='pleasure_yacht':
        gt=qnum(g,s,'grossTonnage');tr=lit(g,s,'engagedInTrade')
        return None if gt is None or tr is None else (gt>=300 and tr is False)
    if st=='cargo_ship':
        gt=qnum(g,s,'grossTonnage')
        return None if gt is None else (gt>=300 and gt<500)
    return False
def o002(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    expected=calc_ch9_1(g,s);actual=lit(g,s,'polarCodeChapter9Dash1Applicable')
    return expected is not None and actual is not None and actual is expected

def b005(cid,systems=('heading_reference',),statuses=(APPROVED,)):
    g,ex,s=shipg(cid)
    for v in systems:add_value(g,s,'headingOrPositionSystem',v,ex)
    for st in statuses:add_value(g,s,'intendedAreaSuitabilityApprovalStatus',st,ex)
    return g
def o005(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    systems=vals(g,s,'headingOrPositionSystem');statuses=vals(g,s,'intendedAreaSuitabilityApprovalStatus')
    if not systems:return True
    return bool(statuses) and all(x==APPROVED for x in statuses)

def b007(cid,ice=True,date='2026-01-01',ind=2,echo=0,trans=0,equiv=False,omit=None):
    g,ex,s=shipg(cid)
    data={'shipIceStrengthened':ice,'constructionDate':date,'independentEchoSoundingDeviceCount':ind,
          'echoSoundingDeviceCount':echo,'independentTransducerCount':trans,
          'administrationApprovedEquivalentDepthSoundingDevicePresent':equiv}
    for t,v in data.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o007(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    ice=lit(g,s,'shipIceStrengthened');d=lit(g,s,'constructionDate')
    if ice is None or d is None:return False
    if ice is False or str(d)<'2026-01-01':return True
    a=lit(g,s,'independentEchoSoundingDeviceCount')
    e=lit(g,s,'echoSoundingDeviceCount');t=lit(g,s,'independentTransducerCount')
    eq=lit(g,s,'administrationApprovedEquivalentDepthSoundingDevicePresent')
    return (a is not None and int(a)>=2) or (e is not None and t is not None and int(e)>=1 and int(t)>=2) or eq is True

def b008(cid,solas=True,astern=True,equiv=False,omit=None):
    g,ex,s=shipg(cid)
    data={'solasRegulationV22Point1Point9Point4ComplianceStatus':solas,'clearViewAsternStatus':astern,
          'administrationApprovedEquivalentVisibilityArrangementPresent':equiv}
    for t,v in data.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o008(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    solas=lit(g,s,'solasRegulationV22Point1Point9Point4ComplianceStatus')
    astern=lit(g,s,'clearViewAsternStatus')
    equiv=lit(g,s,'administrationApprovedEquivalentVisibilityArrangementPresent')
    return (solas is True and astern is True) or equiv is True

def b009(cid,likely=True,protected=(True,),omit_selector=False,omit_value=False):
    g,ex,s=shipg(cid)
    if not omit_selector:add_value(g,s,'iceAccretionLikely',likely,ex)
    for i,v in enumerate(protected):
        a=typed(ex,g,f'antenna{i+1}','navigationOrCommunicationAntenna')
        add_value(g,s,'hasRequiredNavigationOrCommunicationAntenna',a,ex)
        if not omit_value:add_value(g,a,'antennaIceAccumulationPreventionPresent',v,ex)
    return g
def o009(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    likely=lit(g,s,'iceAccretionLikely')
    if likely is None:return False
    if likely is False:return True
    ants=list(g.objects(s,NLTL.hasRequiredNavigationOrCommunicationAntenna))
    return all(lit(g,a,'antennaIceAccumulationPreventionPresent') is True for a in ants)

def b010(cid,projects=True,protect=True,omit=None):
    g,ex,s=shipg(cid)
    for t,v in {'requiredSensorProjectsBelowHull':projects,'sensorIceProtectionPresent':protect}.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o010(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    p=lit(g,s,'requiredSensorProjectsBelowHull')
    if p is None:return False
    if p is False:return True
    return lit(g,s,'sensorIceProtectionPresent') is True

def b011(cid,cat=CAT_A,date='2026-01-01',enclosed=True,design=False,equiv=False,omit=None):
    g,ex,s=shipg(cid)
    data={'shipCategory':cat,'constructionDate':date,'bridgeWingsEnclosed':enclosed,
          'bridgeWingProtectionDesignStatus':design,
          'administrationApprovedEquivalentBridgeWingProtectionPresent':equiv}
    for t,v in data.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o011(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    cat=one(g,s,'shipCategory');d=lit(g,s,'constructionDate')
    if cat is None or d is None:return False
    if cat not in (CAT_A,CAT_B) or str(d)<'2026-01-01':return True
    return lit(g,s,'bridgeWingsEnclosed') is True or lit(g,s,'bridgeWingProtectionDesignStatus') is True or lit(g,s,'administrationApprovedEquivalentBridgeWingProtectionPresent') is True

def b012(cid,gt=500,n=2,main=True,emerg=True,indep=True,wrong_target=False,omit_gt=False):
    g,ex,s=shipg(cid)
    if not omit_gt:add_value(g,s,'grossTonnage',gt,ex)
    means=[]
    for i in range(n):
        m=typed(ex,g,f'heading{i+1}','nonMagneticHeadingMeans')
        add_value(g,s,'hasNonMagneticHeadingMeans',m,ex);means.append(m)
        if main:add_raw_object(g,m,'connectedToMainPower',ex.mainPowerSource)
        if emerg:add_raw_object(g,m,'connectedToEmergencyPower',ex.emergencyPowerSource)
    if indep and len(means)>=2:
        for i,m in enumerate(means):
            add_raw_object(g,m,'independentFromHeadingMeans',means[(i+1)%len(means)] if not wrong_target else ex.externalHeadingMeans)
    return g
def o012(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    gt=qnum(g,s,'grossTonnage')
    if gt is None:return False
    if gt<500:return True
    ms=list(g.objects(s,NLTL.hasNonMagneticHeadingMeans))
    if len(set(ms))<2:return False
    own=set(ms)
    for m in own:
        if not list(g.objects(m,NLTL.connectedToMainPower)) or not list(g.objects(m,NLTL.connectedToEmergencyPower)):return False
        if not any(o in own and o!=m for o in g.objects(m,NLTL.independentFromHeadingMeans)):return False
    return True

def b013(cid,lat=81,count=1,main=True,emerg=True,omit=None):
    g,ex,s=shipg(cid)
    if omit!='plannedOrActualLatitude':add_value(g,s,'plannedOrActualLatitude',lat,ex)
    if omit!='gnssCompassOrEquivalentCount':add_value(g,s,'gnssCompassOrEquivalentCount',count,ex)
    if omit!='connectedToMainPower' and main:add_raw_object(g,s,'connectedToMainPower',ex.mainPowerSource)
    if omit!='connectedToEmergencyPower' and emerg:add_raw_object(g,s,'connectedToEmergencyPower',ex.emergencyPowerSource)
    return g
def o013(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    lat=qnum(g,s,'plannedOrActualLatitude')
    if lat is None:return False
    if lat<=80:return True
    c=lit(g,s,'gnssCompassOrEquivalentCount')
    return c is not None and int(c)>=1 and bool(list(g.objects(s,NLTL.connectedToMainPower))) and bool(list(g.objects(s,NLTL.connectedToEmergencyPower)))

def b014(cid,day=False,count=2,omit=None):
    g,ex,s=shipg(cid)
    if omit!='operatesOnlyInContinuousDaylight':add_value(g,s,'operatesOnlyInContinuousDaylight',day,ex)
    if omit!='visualIceDetectionIlluminationMeansCount':add_value(g,s,'visualIceDetectionIlluminationMeansCount',count,ex)
    return g
def o014(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    day=lit(g,s,'operatesOnlyInContinuousDaylight')
    if day is None:return False
    if day is True:return True
    c=lit(g,s,'visualIceDetectionIlluminationMeansCount')
    return c is not None and int(c)>=2

ORACLES={'IMO26-001':o001,'IMO26-002':o002,'IMO26-005':o005,'IMO26-007':o007,'IMO26-008':o008,'IMO26-009':o009,'IMO26-010':o010,'IMO26-011':o011,'IMO26-012':o012,'IMO26-013':o013,'IMO26-014':o014}
CASES=[]
def add(req,suffix,exp,builder,kw,rat):
    cid=f'{req}-A-{suffix}'
    CASES.append(case(req,cid,exp,builder(cid,**kw),rat))

for x in [
 ('P01','PASS',{},'SOLAS chapter I certified ship has Chapter 9 applicable.'),
 ('P02','PASS',{'cert':False,'app':False},'Non-SOLAS-chapter-I-certified ship has Chapter 9 not applicable.'),
 ('F01','FAIL',{'cert':True,'app':False},'Certified ship incorrectly marks Chapter 9 not applicable.'),
 ('F02','FAIL',{'cert':False,'app':True},'Non-certified ship incorrectly marks Chapter 9 applicable.'),
 ('F03','FAIL',{'omit':'solasChapterICertified'},'SOLAS chapter I certification state missing.'),
]: add('IMO26-001',x[0],x[1],b001,x[2],x[3])

for x in [
 ('P01','PASS',{'stype':'fishing_vessel','length':24,'app':True},'Fishing vessel exactly at 24 m applicability boundary.'),
 ('P02','PASS',{'stype':'fishing_vessel','length':23.99,'app':False},'Fishing vessel below 24 m is outside Chapter 9-1.'),
 ('P03','PASS',{'stype':'pleasure_yacht','gt':300,'trade':False,'app':True},'Non-trading pleasure yacht exactly at 300 GT boundary.'),
 ('P04','PASS',{'stype':'pleasure_yacht','gt':299.9,'trade':False,'app':False},'Pleasure yacht below 300 GT is outside Chapter 9-1.'),
 ('P05','PASS',{'stype':'pleasure_yacht','gt':300,'trade':True,'app':False},'Pleasure yacht engaged in trade is outside this Chapter 9-1 branch.'),
 ('P06','PASS',{'stype':'cargo_ship','gt':300,'app':True},'Cargo ship exactly at lower 300 GT boundary.'),
 ('P07','PASS',{'stype':'cargo_ship','gt':499.9,'app':True},'Cargo ship below 500 GT upper boundary remains applicable.'),
 ('P08','PASS',{'stype':'cargo_ship','gt':500,'app':False},'Cargo ship at 500 GT is outside the <500 GT branch.'),
 ('P09','PASS',{'stype':'cargo_ship','gt':299.9,'app':False},'Cargo ship below 300 GT is outside Chapter 9-1.'),
 ('P10','PASS',{'stype':'other','app':False},'Other ship type is outside the three Chapter 9-1 alternatives.'),
 ('F01','FAIL',{'stype':'fishing_vessel','length':24,'app':False},'Applicable fishing vessel incorrectly marked non-applicable.'),
 ('F02','FAIL',{'stype':'cargo_ship','gt':500,'app':True},'500 GT cargo ship incorrectly marked applicable.'),
 ('F03','FAIL',{'omit':'shipType'},'Ship-type selector missing.'),
 ('F04','FAIL',{'stype':'fishing_vessel','omit':'lengthOverall'},'Fishing-vessel length selector missing.'),
 ('F05','FAIL',{'stype':'pleasure_yacht','omit':'engagedInTrade'},'Pleasure-yacht trade-status selector missing.'),
 ('F06','FAIL',{'stype':'cargo_ship','omit':'grossTonnage'},'Cargo-ship gross tonnage selector missing.'),
]: add('IMO26-002',x[0],x[1],b002,x[2],x[3])

for x in [
 ('P01','PASS',{},'One heading-reference system has approved intended-area suitability.'),
 ('P02','PASS',{'systems':('heading_reference','position_fixing'),'statuses':(APPROVED,APPROVED)},'Two represented systems are both approved.'),
 ('P03','PASS',{'systems':(),'statuses':()},'No represented system; universal obligation does not invent existence.'),
 ('F01','FAIL',{'statuses':(REJECTED,)},'Represented system has rejected intended-area suitability.'),
 ('F02','FAIL',{'systems':('heading_reference','position_fixing'),'statuses':(APPROVED,REJECTED)},'Mixed approved/rejected systems violate universal approval.'),
 ('F03','FAIL',{'systems':('heading_reference',),'statuses':()},'Represented system lacks suitability approval status.'),
]: add('IMO26-005',x[0],x[1],b005,x[2],x[3])

for x in [
 ('P01','PASS',{},'Applicable ice-strengthened post-2026 ship satisfies two-independent-echo-sounder route.'),
 ('P02','PASS',{'ind':0,'echo':1,'trans':2},'Applicable ship satisfies one echo sounder plus two independent transducers.'),
 ('P03','PASS',{'ind':0,'echo':0,'trans':0,'equiv':True},'Administration-approved equivalent depth-sounding device satisfies alternative route.'),
 ('P04','PASS',{'ind':2,'echo':1,'trans':2,'equiv':True},'Multiple valid routes may coexist.'),
 ('P05','PASS',{'date':'2025-12-31','ind':0},'Pre-2026 construction is outside amended obligation.'),
 ('P06','PASS',{'ice':False,'ind':0},'Non-ice-strengthened ship is outside amended obligation.'),
 ('F01','FAIL',{'ind':1,'echo':0,'trans':0,'equiv':False},'Applicable ship satisfies none of the three routes.'),
 ('F02','FAIL',{'ind':0,'echo':1,'trans':1,'equiv':False},'One echo sounder with only one transducer is insufficient.'),
 ('F03','FAIL',{'omit':'constructionDate'},'Construction-date applicability selector missing.'),
 ('F04','FAIL',{'omit':'shipIceStrengthened'},'Ice-strengthening applicability selector missing.'),
]: add('IMO26-007',x[0],x[1],b007,x[2],x[3])

for x in [
 ('P01','PASS',{},'SOLAS V/22.1.9.4 compliance and clear view astern satisfy direct route.'),
 ('P02','PASS',{'solas':False,'astern':False,'equiv':True},'Administration-approved equivalent visibility arrangement satisfies alternative route.'),
 ('P03','PASS',{'equiv':True},'Direct and equivalent routes may coexist.'),
 ('P04','PASS',{'solas':False,'astern':False,'equiv':True,'omit':'clearViewAsternStatus'},'Equivalent visibility route is independently sufficient.'),
 ('F01','FAIL',{'solas':False,'astern':False,'equiv':False},'Neither direct nor equivalent visibility route is satisfied.'),
 ('F02','FAIL',{'solas':True,'astern':False,'equiv':False},'SOLAS status alone without clear view astern is insufficient.'),
 ('F03','FAIL',{'solas':False,'astern':True,'equiv':False},'Clear view astern alone without SOLAS compliance is insufficient.'),
]: add('IMO26-008',x[0],x[1],b008,x[2],x[3])

for x in [
 ('P01','PASS',{},'One required antenna is protected against ice accumulation.'),
 ('P02','PASS',{'protected':(True,True)},'All represented required antennas are protected.'),
 ('P03','PASS',{'likely':False,'protected':(False,)},'Ice accretion not likely; conditional protection obligation not applicable.'),
 ('P04','PASS',{'protected':()},'No required antenna represented; universal obligation does not invent existence.'),
 ('F01','FAIL',{'protected':(False,)},'Required antenna lacks ice-accumulation prevention.'),
 ('F02','FAIL',{'protected':(True,False)},'Mixed protected/unprotected antenna set violates universal obligation.'),
 ('F03','FAIL',{'omit_selector':True},'Ice-accretion applicability selector missing.'),
 ('F04','FAIL',{'omit_value':True},'Required antenna protection value missing.'),
]: add('IMO26-009',x[0],x[1],b009,x[2],x[3])

for x in [
 ('P01','PASS',{},'Required below-hull projecting sensor is protected against ice.'),
 ('P02','PASS',{'projects':False,'protect':False},'No required sensor projects below hull; obligation not applicable.'),
 ('F01','FAIL',{'protect':False},'Projecting required sensor lacks ice protection.'),
 ('F02','FAIL',{'omit':'requiredSensorProjectsBelowHull'},'Below-hull projection trigger missing.'),
 ('F03','FAIL',{'omit':'sensorIceProtectionPresent'},'Required ice-protection state missing.'),
]: add('IMO26-010',x[0],x[1],b010,x[2],x[3])

for x in [
 ('P01','PASS',{},'Category A post-2026 ship satisfies enclosed bridge-wing route.'),
 ('P02','PASS',{'cat':CAT_B,'enclosed':False,'design':True},'Category B ship satisfies protective-design route.'),
 ('P03','PASS',{'enclosed':False,'design':False,'equiv':True},'Administration-approved equivalent bridge-wing protection satisfies route.'),
 ('P04','PASS',{'enclosed':True,'design':True,'equiv':True},'All three valid routes may coexist.'),
 ('P05','PASS',{'cat':CAT_C,'enclosed':False,'design':False,'equiv':False},'Category C is outside A/B obligation.'),
 ('P06','PASS',{'date':'2025-12-31','enclosed':False,'design':False,'equiv':False},'Pre-2026 construction is outside amended obligation.'),
 ('F01','FAIL',{'enclosed':False,'design':False,'equiv':False},'Applicable category A ship satisfies no bridge-wing route.'),
 ('F02','FAIL',{'cat':CAT_B,'enclosed':False,'design':False,'equiv':False},'Applicable category B ship satisfies no bridge-wing route.'),
 ('F03','FAIL',{'omit':'shipCategory'},'Ship-category applicability selector missing.'),
 ('F04','FAIL',{'omit':'constructionDate'},'Construction-date applicability selector missing.'),
]: add('IMO26-011',x[0],x[1],b011,x[2],x[3])

for x in [
 ('P01','PASS',{},'500 GT ship has two powered independent non-magnetic heading means.'),
 ('P02','PASS',{'gt':600,'n':3},'Ship above 500 GT has three valid heading means.'),
 ('P03','PASS',{'gt':499,'n':0,'main':False,'emerg':False,'indep':False},'Ship below 500 GT is outside 9-1.3.2.2.1 requirement.'),
 ('F01','FAIL',{'n':1},'Applicable ship has fewer than two heading means.'),
 ('F02','FAIL',{'main':False},'Applicable heading means lack main-power connection.'),
 ('F03','FAIL',{'emerg':False},'Applicable heading means lack emergency-power connection.'),
 ('F04','FAIL',{'indep':False},'Heading means are not independent.'),
 ('F05','FAIL',{'wrong_target':True},'Independence points outside the ship-owned heading-means inventory.'),
 ('F06','FAIL',{'omit_gt':True},'Gross-tonnage applicability selector missing.'),
]: add('IMO26-012',x[0],x[1],b012,x[2],x[3])

for x in [
 ('P01','PASS',{},'Latitude above 80 degrees with GNSS/equivalent and both power sources.'),
 ('P02','PASS',{'lat':80,'count':0,'main':False,'emerg':False},'Exactly 80 degrees is outside >80-degree trigger.'),
 ('P03','PASS',{'lat':79.9,'count':0,'main':False,'emerg':False},'Latitude below trigger is not applicable.'),
 ('F01','FAIL',{'count':0},'No GNSS compass/equivalent above 80 degrees.'),
 ('F02','FAIL',{'main':False},'Required main-power connection absent.'),
 ('F03','FAIL',{'emerg':False},'Required emergency-power connection absent.'),
 ('F04','FAIL',{'omit':'plannedOrActualLatitude'},'Latitude applicability selector missing.'),
]: add('IMO26-013',x[0],x[1],b013,x[2],x[3])

for x in [
 ('P01','PASS',{},'Non-continuous-daylight operation has exactly two illumination means.'),
 ('P02','PASS',{'count':3},'More than two illumination means is compliant.'),
 ('P03','PASS',{'day':True,'count':0},'Sole 24-hour daylight operation is exempt.'),
 ('F01','FAIL',{'count':1},'Only one illumination means where two are required.'),
 ('F02','FAIL',{'count':0},'No illumination means where two are required.'),
 ('F03','FAIL',{'omit':'operatesOnlyInContinuousDaylight'},'Continuous-daylight applicability state missing.'),
 ('F04','FAIL',{'omit':'visualIceDetectionIlluminationMeansCount'},'Required illumination-means count missing.'),
]: add('IMO26-014',x[0],x[1],b014,x[2],x[3])

MANIFEST='imo26_batch_a_manifest.jsonl'
LOCK='imo26_batch_a_fixture_lock.json'
VALIDATOR='validate_imo26_batch_a.py'
def main():
    if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:
        raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                   batch_label='IMO 2026 Supplement Batch A',manifest_name=MANIFEST,lock_name=LOCK,
                   validator_name=VALIDATOR,family='IMO26')
if __name__=='__main__':main()
