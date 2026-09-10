from pathlib import Path
import json, hashlib, math, shutil, sys
from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD

def find_repo():
    cs=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    for c in cs:
        p=c/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'/'requirement_term_index.json'
        if p.exists(): return c.resolve()
    raise RuntimeError('Could not locate NLTL_v2 repository root')
REPO=find_repo(); ROOT=REPO/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'; R13=REPO/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'
INDEX=json.loads((R13/'requirement_term_index.json').read_text()); REGISTRY=json.loads((R13/'registry'/'term_registry.json').read_text()); REG={x['localName']:x for x in REGISTRY}; CONTRACTS=INDEX['dependencyContracts']
NLTL=Namespace('https://w3id.org/nltl/vocab#'); QUDT=Namespace('http://qudt.org/schema/qudt/'); UNIT=Namespace('http://qudt.org/vocab/unit/'); BASE='https://w3id.org/nltl/benchmark/traficom-batch-g/'
REQS=['TRF-069','TRF-070','TRF-074','TRF-075','TRF-076','TRF-077','TRF-078','TRF-079','TRF-080']
MODES={'TRF-069':'DIRECT_STATIC','TRF-070':'COMPLEX_READINESS','TRF-074':'DIRECT_STATIC','TRF-075':'DIRECT_STATIC','TRF-076':'DIRECT_STATIC','TRF-077':'DIRECT_STATIC','TRF-078':'DIRECT_CALCULATION','TRF-079':'DIRECT_CALCULATION','TRF-080':'DIRECT_CALCULATION'}
for r in REQS:
    assert CONTRACTS[r]['status']=='COMPLETE' and CONTRACTS[r]['verificationMode']==MODES[r]
assert CONTRACTS['TRF-070'].get('formulaExecutionRequired') is False
ONTOLOGY=Graph().parse(R13/'ontology'/'nltl_benchmark_vocabulary.ttl',format='turtle'); KNOWN={str(s).split('#',1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL)) and '#' in str(s)}
ICE={'IA Super':NLTL.iceClassIaSuper,'IA':NLTL.iceClassIa,'IB':NLTL.iceClassIb,'IC':NLTL.iceClassIc,'II':NLTL.iceClassIi,'III':NLTL.iceClassIii}

def new(cid):
    g=Graph(); ex=Namespace(BASE+cid+'/'); g.bind('ex',ex);g.bind('nltl',NLTL);g.bind('qudt',QUDT);g.bind('unit',UNIT);g.bind('xsd',XSD); ship=ex.ship; g.add((ship,RDF.type,NLTL.ship)); return g,ex,ship

def add(g,s,t,v,ex,name=None,wrong_unit=False):
    row=REG[t]; kind=row['kind']
    if kind=='QuantityProperty':
        q=ex[name or t+'Value']; g.add((q,RDF.type,QUDT.QuantityValue)); g.add((q,QUDT.numericValue,Literal(str(v),datatype=XSD.decimal))); u=URIRef(row['unitIri']);
        if wrong_unit: u=UNIT.UNITLESS if str(u)!=str(UNIT.UNITLESS) else UNIT.M
        g.add((q,QUDT.unit,u)); g.add((s,NLTL[t],q)); return q
    if kind=='DatatypeProperty':
        dt={'xsd:boolean':XSD.boolean,'xsd:string':XSD.string,'xsd:integer':XSD.integer,'xsd:decimal':XSD.decimal,'xsd:date':XSD.date}[row['datatype']]; g.add((s,NLTL[t],Literal(v,datatype=dt))); return None
    if kind=='ObjectProperty':
        g.add((s,NLTL[t],v)); return v
    raise RuntimeError(t)
def link(g,s,t,ex,n,cls):
    o=ex[n]; g.add((o,RDF.type,NLTL[cls])); add(g,s,t,o,ex); return o
def one(g,s,t):
    xs=list(g.objects(s,NLTL[t])); return xs[0] if len(xs)==1 else None
def qnum(g,s,t):
    q=one(g,s,t)
    if q is None:return None
    ns=list(g.objects(q,QUDT.numericValue)); us=list(g.objects(q,QUDT.unit)); exp=REG[t].get('unitIri','')
    if len(ns)!=1 or len(us)!=1 or (exp and str(us[0])!=exp):return None
    try:return float(ns[0])
    except:return None
def lit(g,s,t):
    o=one(g,s,t)
    if o is None:return None
    try:return o.toPython()
    except:return None
def close(a,b): return a is not None and b is not None and math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-7)

def build069(cid, ice='IA', ptype='open', pitch='fixed', normal=True, miss=None, bad=False):
    g,ex,s=new(cid); add(g,s,'iceClass',ICE[ice],ex); add(g,s,'propellerType',ptype,ex); add(g,s,'pitchType',pitch,ex); add(g,s,'normalOperationalConditions',normal,ex); add(g,s,'maximumIceTorque',100,ex)
    vals={'normalServiceLifePropellerIceLoadCondition':True,'fixedPitchPropellerReversalLoadIncluded':True,'stoppedPropellerDraggingOutsideLoadModel':True,'radialIceEntryOutsideLoadModel':True}
    if bad: vals['stoppedPropellerDraggingOutsideLoadModel']=False
    for t,v in vals.items():
        if t!=miss:add(g,s,t,v,ex)
    return g
def oracle069(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); ice=one(g,s,'iceClass'); pt=lit(g,s,'propellerType'); pitch=lit(g,s,'pitchType'); norm=lit(g,s,'normalOperationalConditions')
    applicable=ice in {ICE['IA Super'],ICE['IA'],ICE['IB'],ICE['IC']} and pt in {'open','ducted'} and pitch in {'controllable','fixed'} and norm is True
    if not applicable:return True
    req=['normalServiceLifePropellerIceLoadCondition','stoppedPropellerDraggingOutsideLoadModel','radialIceEntryOutsideLoadModel']
    if pitch=='fixed': req.append('fixedPitchPropellerReversalLoadIncluded')
    return all(lit(g,s,t) is True for t in req)

def build070(cid, main=True, typ='azimuthing', miss=None, wrongpath=False):
    g,ex,s=new(cid); add(g,s,'mainPropulsionThruster',main,ex); add(g,s,'thrusterType',typ,ex)
    if not main:return g
    dc=ex.designCondition; g.add((dc,RDF.type,NLTL.designCondition));
    if not wrongpath:add(g,s,'hasDesignCondition',dc,ex)
    target=s if wrongpath else dc
    vals={'propellerIceInteractionLoad':100,'thrusterBodyIceInteractionLoad':80,'localIcePressure':5.6,'designConditionLocalStrengthCapacity':120}
    for t,v in vals.items():
        if t!=miss:add(g,target,t,v,ex)
    return g
def oracle070(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); main=lit(g,s,'mainPropulsionThruster'); typ=lit(g,s,'thrusterType')
    if main is not True or typ not in {'azimuthing','fixed'}: return True
    dc=one(g,s,'hasDesignCondition');
    if dc is None:return False
    return all(qnum(g,dc,t) is not None for t in ['propellerIceInteractionLoad','thrusterBodyIceInteractionLoad','localIcePressure','designConditionLocalStrengthCapacity'])

def build074(cid,ice='IB',depth=0.8,hi=1.0,designed='IA',omit=False):
    g,ex,s=new(cid); add(g,s,'iceClass',ICE[ice],ex); add(g,s,'ballastConditionPropellerTopDepth',depth,ex); add(g,s,'requiredPropellerSubmersionDepthHi',hi,ex)
    if not omit:add(g,s,'propulsionSystemDesignedForIceClass',ICE[designed],ex)
    return g
def oracle074(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); ice=one(g,s,'iceClass'); d=qnum(g,s,'ballastConditionPropellerTopDepth'); hi=qnum(g,s,'requiredPropellerSubmersionDepthHi')
    if d is None or hi is None:return False
    if ice in {ICE['IB'],ICE['IC']} and d<hi:return one(g,s,'propulsionSystemDesignedForIceClass')==ICE['IA']
    return True

def build075(cid,forces='backward',omit_link=None):
    g,ex,s=new(cid); lc=link(g,s,'hasPropellerBladeLoadCase',ex,'case','propellerBladeLoadCase'); b=ex.blade; ib=ex.iceBlock; g.add((b,RDF.type,NLTL.propellerBlade));g.add((ib,RDF.type,NLTL.iceBlock))
    if omit_link!='blade':add(g,lc,'propellerBladeLoadCaseBlade',b,ex)
    if omit_link!='ice':add(g,lc,'propellerBladeLoadCaseIceBlock',ib,ex)
    if forces in {'backward','both'}:add(g,lc,'backwardBladeForce',500,ex)
    if forces in {'forward','both'}:add(g,lc,'forwardBladeForce',400,ex)
    return g
def oracle075(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); cases=list(g.objects(s,NLTL.hasPropellerBladeLoadCase))
    for c in cases:
        if one(g,c,'propellerBladeLoadCaseBlade') is None or one(g,c,'propellerBladeLoadCaseIceBlock') is None:return False
        n=sum(qnum(g,c,t) is not None for t in ['backwardBladeForce','forwardBladeForce'])
        if n!=1:return False
    return True

def build076(cid,ptype='CP',reverse=False,missing_num=None,extra5=False):
    g,ex,s=new(cid); add(g,s,'propellerType',ptype,ex); add(g,s,'propellerReversingCapability',reverse,ex)
    nums=[1,2,3,4]+([5] if (ptype=='FP' and reverse) or extra5 else [])
    for n in nums:
        if n==missing_num:continue
        lc=link(g,s,'hasPropellerBladeLoadCase',ex,f'case{n}','propellerBladeLoadCase'); add(g,lc,'propellerBladeLoadCaseNumber',n,ex)
    return g
def oracle076(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); pt=lit(g,s,'propellerType'); rev=lit(g,s,'propellerReversingCapability'); nums=[]
    for c in g.objects(s,NLTL.hasPropellerBladeLoadCase):
        n=lit(g,c,'propellerBladeLoadCaseNumber');
        if isinstance(n,int):nums.append(n)
    req={1,2,3,4};
    if pt=='FP' and rev is True:req.add(5)
    return req.issubset(set(nums))

def build077(cid,ptype='open',k=None,maxload=100,wrong_unit=False):
    g,ex,s=new(cid); add(g,s,'propellerType',ptype,ex); add(g,s,'maximumBladeIceLoad',maxload,ex)
    if k is None:k=0.75 if ptype=='open' else 1.0
    add(g,s,'loadSpectrumShapeParameter',k,ex,wrong_unit=wrong_unit); return g
def oracle077(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); pt=lit(g,s,'propellerType'); k=qnum(g,s,'loadSpectrumShapeParameter'); mx=qnum(g,s,'maximumBladeIceLoad')
    if pt=='open':return close(k,0.75) and mx is not None and mx>=0
    if pt=='ducted':return close(k,1.0) and mx is not None and mx>=0
    return True

def build078(cid,badref=False,badcalc=False,missing=None):
    g,ex,s=new(cid); c6=link(g,s,'hasTableLookupCase',ex,'table6','tableLookupCase'); c7=link(g,s,'hasTableLookupCase',ex,'table7','tableLookupCase')
    add(g,c6,'tableReference',NLTL.traficomTable6Dash7 if badref else NLTL.traficomTable6Dash6,ex); add(g,c6,'iceClass',ICE['IA Super'],ex); add(g,c6,'selectedIceClassCycleCount',9000000,ex)
    add(g,c7,'tableReference',NLTL.traficomTable6Dash7,ex); loc=ex.centrePropeller; add(g,c7,'tableLookupPropellerLocation',loc,ex); add(g,c7,'selectedPropellerLocationFactor',1,ex)
    vals={'iceLoadCycleCoefficientK2':0.8,'iceLoadCycleCoefficientK3':1.0,'propellerBladeLoadSpectrumCountFactor':1.0}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    if missing!='iceLoadCycleCount':add(g,s,'iceLoadCycleCount',7000000 if badcalc else 7200000,ex)
    return g
def oracle078(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); c6=c7=None
    for c in g.objects(s,NLTL.hasTableLookupCase):
        tr=one(g,c,'tableReference')
        if tr==NLTL.traficomTable6Dash6:c6=c
        if tr==NLTL.traficomTable6Dash7:c7=c
    if c6 is None or c7 is None:return False
    nclass=qnum(g,c6,'selectedIceClassCycleCount'); k1=qnum(g,c7,'selectedPropellerLocationFactor'); k2=qnum(g,s,'iceLoadCycleCoefficientK2'); k3=qnum(g,s,'iceLoadCycleCoefficientK3'); nn=qnum(g,s,'propellerBladeLoadSpectrumCountFactor'); ni=lit(g,s,'iceLoadCycleCount')
    return all(x is not None for x in [nclass,k1,k2,k3,nn,ni]) and int(round(k1*k2*k3*nclass*nn))==ni

def build079(cid,f=-0.5,bad=False,missing=None):
    g,ex,s=new(cid); D=4.0; H=1.0; h0=(f+1)*(D/2)+H; k=0.8-f if f<0 else 0.8-0.4*f if f<=1 else 0.6-0.2*f if f<=2.5 else 0.1
    vals={'designIceThickness':H,'propellerDiameter':D,'propellerShaftCentrelineDepth':h0,'propellerImmersionFunction':f,'iceLoadCycleCoefficientK2':k+(0.1 if bad else 0)}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle079(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); H=qnum(g,s,'designIceThickness');D=qnum(g,s,'propellerDiameter');h0=qnum(g,s,'propellerShaftCentrelineDepth');f=qnum(g,s,'propellerImmersionFunction');k=qnum(g,s,'iceLoadCycleCoefficientK2')
    if None in [H,D,h0,f,k] or D==0:return False
    f2=(h0-H)/(D/2)-1; k2=0.8-f if f<0 else 0.8-0.4*f if f<=1 else 0.6-0.2*f if f<=2.5 else 0.1
    return close(f,f2) and close(k,k2)

def build080(cid,n=1000,z=4,bad=False,missing=None):
    g,ex,s=new(cid); vals={'iceLoadCycleCount':n,'propellerBladeCount':z,'effectiveIceLoadCycleCount':n*z+(1 if bad else 0)}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle080(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); n=lit(g,s,'iceLoadCycleCount');z=lit(g,s,'propellerBladeCount');e=qnum(g,s,'effectiveIceLoadCycleCount'); return n is not None and z is not None and close(e,n*z)

OR={'TRF-069':oracle069,'TRF-070':oracle070,'TRF-074':oracle074,'TRF-075':oracle075,'TRF-076':oracle076,'TRF-077':oracle077,'TRF-078':oracle078,'TRF-079':oracle079,'TRF-080':oracle080}
CASES=[]
def ac(r,suf,exp,rat,g):CASES.append({'requirement_id':r,'case_id':f'{r}-{suf}','expected':exp,'rationale':rat,'graph':g})
# 069 6
ac('TRF-069','P01','PASS','Applicable fixed-pitch normal-service scope with all source scope flags.',build069('TRF-069-P01'))
ac('TRF-069','P02','PASS','Ice class II is outside propulsion-machinery applicability.',build069('TRF-069-P02',ice='II'))
ac('TRF-069','P03','PASS','Controllable-pitch applicable route does not require FP reversal flag.',build069('TRF-069-P03',pitch='controllable',miss='fixedPitchPropellerReversalLoadIncluded'))
ac('TRF-069','F01','FAIL','Missing normal-service load-condition evidence.',build069('TRF-069-F01',miss='normalServiceLifePropellerIceLoadCondition'))
ac('TRF-069','F02','FAIL','Stopped-propeller dragging incorrectly treated as in-scope.',build069('TRF-069-F02',bad=True))
ac('TRF-069','F03','FAIL','Fixed-pitch reversal load inclusion is missing.',build069('TRF-069-F03',miss='fixedPitchPropellerReversalLoadIncluded'))
#070 6
ac('TRF-070','P01','PASS','Azimuthing main-thruster readiness complete.',build070('TRF-070-P01'))
ac('TRF-070','P02','PASS','Fixed main-thruster readiness complete.',build070('TRF-070-P02',typ='fixed'))
ac('TRF-070','P03','PASS','Non-main propulsion thruster is outside conditional rule.',build070('TRF-070-P03',main=False))
ac('TRF-070','F01','FAIL','Missing local ice pressure operand.',build070('TRF-070-F01',miss='localIcePressure'))
ac('TRF-070','F02','FAIL','Missing local-strength capacity result.',build070('TRF-070-F02',miss='designConditionLocalStrengthCapacity'))
ac('TRF-070','F03','FAIL','Design-condition quantities attached on wrong path.',build070('TRF-070-F03',wrongpath=True))
#074 7
for suf,d,hi,des,exp in [('P01',0.8,1.0,'IA','PASS'),('P02',1.0,1.0,'IB','PASS'),('P03',1.2,1.0,'IC','PASS'),('F01',0.8,1.0,'IB','FAIL'),('F02',0.8,1.0,'IC','FAIL')]:ac('TRF-074',suf,exp,'Propeller submersion trigger/boundary case.',build074('TRF-074-'+suf,depth=d,hi=hi,designed=des))
ac('TRF-074','P04','PASS','IA ship is not subject to IB/IC redesign trigger.',build074('TRF-074-P04',ice='IA',depth=.5,hi=1,designed='IA'))
ac('TRF-074','F03','FAIL','Triggered IB case lacks redesign-class assertion.',build074('TRF-074-F03',depth=.5,hi=1,omit=True))
#075 6
ac('TRF-075','P01','PASS','Backward-only blade load case.',build075('TRF-075-P01','backward'))
ac('TRF-075','P02','PASS','Forward-only blade load case.',build075('TRF-075-P02','forward'))
ac('TRF-075','P03','PASS','No load cases does not violate universal xone.',new('TRF-075-P03')[0])
ac('TRF-075','F01','FAIL','Both backward and forward force violate exactly-one.',build075('TRF-075-F01','both'))
ac('TRF-075','F02','FAIL','Neither force is present.',build075('TRF-075-F02','none'))
ac('TRF-075','F03','FAIL','Blade relationship missing.',build075('TRF-075-F03','backward','blade'))
#076 7
ac('TRF-076','P01','PASS','CP covers load cases 1-4.',build076('TRF-076-P01','CP',False))
ac('TRF-076','P02','PASS','FP non-reversing covers load cases 1-4.',build076('TRF-076-P02','FP',False))
ac('TRF-076','P03','PASS','Reversing FP covers load cases 1-5.',build076('TRF-076-P03','FP',True))
for n in [1,3,4]:ac('TRF-076',f'F0{n}','FAIL',f'Mandatory load case {n} missing.',build076(f'TRF-076-F0{n}','CP',False,missing_num=n))
ac('TRF-076','F05','FAIL','Reversing FP lacks load case 5.',build076('TRF-076-F05','FP',True,missing_num=5))
#077 6
ac('TRF-077','P01','PASS','Open propeller uses k=0.75.',build077('TRF-077-P01','open'))
ac('TRF-077','P02','PASS','Ducted propeller uses k=1.0.',build077('TRF-077-P02','ducted'))
ac('TRF-077','P03','PASS','Unrelated propeller type is outside enumerated source branches.',build077('TRF-077-P03','other',k=.5))
ac('TRF-077','F01','FAIL','Open propeller has wrong shape parameter.',build077('TRF-077-F01','open',k=1.0))
ac('TRF-077','F02','FAIL','Ducted propeller has wrong shape parameter.',build077('TRF-077-F02','ducted',k=.75))
ac('TRF-077','F03','FAIL','Shape parameter uses wrong unit.',build077('TRF-077-F03','open',wrong_unit=True))
#078 6
ac('TRF-078','P01','PASS','Canonical Table 6-6/6-7 lookups and N_ice calculation.',build078('TRF-078-P01'))
ac('TRF-078','F01','FAIL','Table 6-6 reference is wrong.',build078('TRF-078-F01',badref=True))
ac('TRF-078','F02','FAIL','N_ice result is numerically wrong.',build078('TRF-078-F02',badcalc=True))
for i,t in enumerate(['iceLoadCycleCoefficientK2','iceLoadCycleCoefficientK3','iceLoadCycleCount'],3):ac('TRF-078',f'F0{i}','FAIL',f'Missing {t}.',build078(f'TRF-078-F0{i}',missing=t))
#079 8
for i,f in enumerate([-0.5,0,1,2.5,3],1):ac('TRF-079',f'P0{i}','PASS',f'Piecewise k2 boundary/branch f={f}.',build079(f'TRF-079-P0{i}',f=f))
ac('TRF-079','F01','FAIL','Incorrect k2 result.',build079('TRF-079-F01',f=1.2,bad=True))
ac('TRF-079','F02','FAIL','Missing immersion function.',build079('TRF-079-F02',missing='propellerImmersionFunction'))
ac('TRF-079','F03','FAIL','Missing design ice thickness.',build079('TRF-079-F03',missing='designIceThickness'))
#080 5
ac('TRF-080','P01','PASS','Effective cycles multiply per-blade cycles by blade count.',build080('TRF-080-P01',1000,4))
ac('TRF-080','P02','PASS','Single blade leaves cycle count unchanged.',build080('TRF-080-P02',25,1))
ac('TRF-080','F01','FAIL','Incorrect multiplied cycle count.',build080('TRF-080-F01',1000,4,True))
ac('TRF-080','F02','FAIL','Missing propeller blade count.',build080('TRF-080-F02',missing='propellerBladeCount'))
ac('TRF-080','F03','FAIL','Missing effective cycle result.',build080('TRF-080-F03',missing='effectiveIceLoadCycleCount'))

def vocab(g):
    bad=[]
    for s,p,o in g:
        for n in (s,p,o):
            st=str(n)
            if st.startswith(str(NLTL)) and '#' in st and st.split('#',1)[1] not in KNOWN: bad.append(st.split('#',1)[1])
    return not bad,sorted(set(bad))
def qudt(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1:return False
    return True
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(check_hashes=True):
    mp=ROOT/'manifests'/'traficom_batch_g_manifest.jsonl'; lp=ROOT/'locks'/'traficom_batch_g_fixture_lock.json'
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]; syn=vo=qu=ag=0; diag=[]
    for r in rows:
        p=ROOT/r['rdf_path']
        try:g=Graph().parse(p,format='turtle');syn+=1
        except Exception as e:diag.append((r['case_id'],'parse',str(e)));continue
        ok,b=vocab(g);vo+=int(ok); qu+=int(qudt(g)); act='PASS' if OR[r['requirement_id']](g) else 'FAIL'; ag+=int(act==r['expected'])
        if not ok:diag.append((r['case_id'],'vocab',b))
        if act!=r['expected']:diag.append((r['case_id'],'oracle',act,r['expected']))
    h=True
    if check_hashes:
        if not lp.exists():h=False
        else:
            lock=json.loads(lp.read_text());
            for rel,x in lock['frozen_files'].items():
                p=ROOT/rel
                if not p.exists() or sha(p)!=x:h=False;diag.append((rel,'hash','mismatch'))
    n=len(rows); print(f'Requirements: {len(set(r["requirement_id"] for r in rows))}');print(f'RDF files: {n}');print(f'Syntactically valid: {syn}');print(f'Vocabulary validation count: {vo}');print(f'QUDT/unit validation count: {qu}');print(f'Source-oracle agreement count: {ag}');
    if check_hashes:print('Frozen hashes matched: '+('YES' if h else 'NO'))
    ok=(syn==vo==qu==ag==n and (h if check_hashes else True));print('Overall status: '+('PASS' if ok else 'FAIL'))
    if diag:print('Diagnostics:',*diag,sep='\n')
    return ok
CLAUSES={'TRF-069':'6.1','TRF-070':'6.1','TRF-074':'6.5','TRF-075':'6.5.1','TRF-076':'6.5.1.3','TRF-077':'6.5.1.8','TRF-078':'6.5.1.9','TRF-079':'6.5.1.9','TRF-080':'6.5.1.9'}
def generate():
    for p in [ROOT/'rdf'/'TRF',ROOT/'specifications'/'TRF',ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:p.mkdir(parents=True,exist_ok=True)
    lp=ROOT/'locks'/'traficom_batch_g_fixture_lock.json'
    if lp.exists():raise SystemExit('Batch G lock already exists. Refusing to overwrite frozen fixtures.')
    rows=[]
    for c in CASES:
        r=c['requirement_id']; od=ROOT/'rdf'/'TRF'/r;od.mkdir(parents=True,exist_ok=True); p=od/f"{c['case_id']}.ttl"
        if p.exists():raise SystemExit(f'Refusing to overwrite existing RDF fixture: {p}')
        c['graph'].serialize(destination=p,format='turtle'); rows.append({'requirement_id':r,'case_id':c['case_id'],'expected':c['expected'],'rdf_path':str(p.relative_to(ROOT)),'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'verification_mode':MODES[r],'source_oracle_rationale':c['rationale'],'generated_shacl_inspected':False})
    mp=ROOT/'manifests'/'traficom_batch_g_manifest.jsonl';mp.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    for r in REQS:(ROOT/'specifications'/'TRF'/f'{r}.json').write_text(json.dumps({'requirement_id':r,'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'source_lock_id':INDEX['sourceLockId'],'r13_contract':CONTRACTS[r],'test_cases':[{'case_id':x['case_id'],'expected':x['expected'],'rationale':x['rationale']} for x in CASES if x['requirement_id']==r],'benchmark_policy':'Source/R13-defined behavioral oracle created without inspecting generated SHACL.'},indent=2)+'\n')
    print('Pre-freeze validation'); assert validate(False)
    vp=ROOT/'scripts'/'validate_traficom_batch_g.py';shutil.copy2(Path(__file__).resolve(),vp);vp.chmod(0o755)
    frozen={}
    for c in CASES:frozen[str((ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl").relative_to(ROOT))]=sha(ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl")
    frozen[str(mp.relative_to(ROOT))]=sha(mp)
    for r in REQS:
        p=ROOT/'specifications'/'TRF'/f'{r}.json';frozen[str(p.relative_to(ROOT))]=sha(p)
    lp.write_text(json.dumps({'benchmark':'TRAFICOM Behavioral Benchmark Batch G','source_lock_id':INDEX['sourceLockId'],'source_id':'SRC-TRAFICOM-2021','requirements':REQS,'requirement_count':len(REQS),'case_count':len(CASES),'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,'frozen_files':frozen},indent=2)+'\n')
    print('\nFrozen validation'); assert validate(True)
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate(True) else 1)
    generate()
