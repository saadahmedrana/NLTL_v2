
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-i/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-081','IMO-082','IMO-083','IMO-084','IMO-085','IMO-086','IMO-087','IMO-088','IMO-089']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={'IMO-081':'Part I-A 9.3.2.1.1','IMO-082':'Part I-A 9.3.2.1.2','IMO-083':'Part I-A 9.3.2.1.3','IMO-084':'Part I-A 9.3.2.1.4.1','IMO-085':'Part I-A 9.3.2.1.4.2','IMO-086':'Part I-A 9.3.2.2.1','IMO-087':'Part I-A 9.3.2.2.2','IMO-088':'Part I-A 9.3.3.1','IMO-089':'Part I-A 9.3.3.2'}
CAT_A=NLTL.polarShipCategoryA; CAT_B=NLTL.polarShipCategoryB; CAT_C=NLTL.polarShipCategoryC; APPROVED=NLTL.evidenceStateApproved

def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid): return new_graph(BASE,cid)

def b081(cid,date='2017-01-01',ice=True,ind=2,echo=0,trans=0,omit=None):
 g,ex,s=shipg(cid); vals={'constructionDate':date,'shipIceStrengthened':ice,'independentEchoSoundingDeviceCount':ind,'echoSoundingDeviceCount':echo,'independentTransducerCount':trans}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o081(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 d=lit(g,s,'constructionDate'); ice=lit(g,s,'shipIceStrengthened')
 if d is None or ice is None:return False
 if str(d)<'2017-01-01' or ice is False:return True
 a=lit(g,s,'independentEchoSoundingDeviceCount'); e=lit(g,s,'echoSoundingDeviceCount'); t=lit(g,s,'independentTransducerCount')
 return a is not None and e is not None and t is not None and (int(a)>=2 or (int(e)>=1 and int(t)>=2))

def b082(cid,bridge=NLTL.asternViewRequiredBridgeConfiguration,solas=True,astern=True,omit=None):
 g,ex,s=shipg(cid); vals={'bridgeConfigurationType':bridge,'solasRegulationV22Point1Point9Point4ComplianceStatus':solas,'clearViewAsternStatus':astern}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o082(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 b=one(g,s,'bridgeConfigurationType'); sol=lit(g,s,'solasRegulationV22Point1Point9Point4ComplianceStatus')
 if b is None or sol is not True:return False
 if b==NLTL.asternViewRequiredBridgeConfiguration:return lit(g,s,'clearViewAsternStatus') is True
 return True

def b083(cid,likely=True,vals=(True,),omit_selector=False,omit_value=False):
 g,ex,s=shipg(cid)
 if not omit_selector:add_value(g,s,'iceAccretionLikely',likely,ex)
 for i,v in enumerate(vals):
  a=typed(ex,g,f'antenna{i+1}','navigationOrCommunicationAntenna'); add_value(g,s,'hasRequiredNavigationOrCommunicationAntenna',a,ex)
  if not omit_value:add_value(g,a,'antennaIceAccumulationPreventionPresent',v,ex)
 return g
def o083(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 likely=lit(g,s,'iceAccretionLikely')
 if likely is None:return False
 if likely is False:return True
 ants=list(g.objects(s,NLTL.hasRequiredNavigationOrCommunicationAntenna))
 return all(lit(g,a,'antennaIceAccumulationPreventionPresent') is True for a in ants)

def b084(cid,projects=True,protect=True,omit=None):
 g,ex,s=shipg(cid)
 for t,v in {'requiredSensorProjectsBelowHull':projects,'sensorIceProtectionPresent':protect}.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o084(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); p=lit(g,s,'requiredSensorProjectsBelowHull') if s else None
 if p is None:return False
 return True if p is False else lit(g,s,'sensorIceProtectionPresent') is True

def b085(cid,cat=CAT_A,date='2017-01-01',enclosed=True,status=True,omit=None):
 g,ex,s=shipg(cid); vals={'shipCategory':cat,'constructionDate':date,'bridgeWingsEnclosed':enclosed,'bridgeWingProtectionDesignStatus':status}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o085(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=one(g,s,'shipCategory'); d=lit(g,s,'constructionDate')
 if cat is None or d is None:return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01':return True
 return lit(g,s,'bridgeWingsEnclosed') is True or lit(g,s,'bridgeWingProtectionDesignStatus') is True

def b086(cid,n=2,main=True,emerg=True,indep=True,wrong_target=False):
 g,ex,s=shipg(cid); means=[]
 for i in range(n):
  m=typed(ex,g,f'heading{i+1}','nonMagneticHeadingMeans'); add_value(g,s,'hasNonMagneticHeadingMeans',m,ex); means.append(m)
  if main:add_raw_object(g,m,'connectedToMainPower',ex.mainPowerSource)
  if emerg:add_raw_object(g,m,'connectedToEmergencyPower',ex.emergencyPowerSource)
 if indep and len(means)>=2:
  for i,m in enumerate(means): add_raw_object(g,m,'independentFromHeadingMeans', means[(i+1)%len(means)] if not wrong_target else ex.externalHeading)
 return g
def o086(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); ms=list(g.objects(s,NLTL.hasNonMagneticHeadingMeans)) if s else []
 if len(set(ms))<2:return False
 own=set(ms)
 for m in own:
  if not list(g.objects(m,NLTL.connectedToMainPower)) or not list(g.objects(m,NLTL.connectedToEmergencyPower)):return False
  if not any(o in own and o!=m for o in g.objects(m,NLTL.independentFromHeadingMeans)):return False
 return True

def b087(cid,lat=81,count=1,main=True,emerg=True,omit=None):
 g,ex,s=shipg(cid); vals={'plannedOrActualLatitude':lat,'gnssCompassOrEquivalentCount':count}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='connectedToMainPower': add_raw_object(g,s,'connectedToMainPower',ex.mainPowerSource) if main else None
 if omit!='connectedToEmergencyPower': add_raw_object(g,s,'connectedToEmergencyPower',ex.emergencyPowerSource) if emerg else None
 return g
def o087(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); lat=qnum(g,s,'plannedOrActualLatitude') if s else None
 if lat is None:return False
 if lat<=80:return True
 c=lit(g,s,'gnssCompassOrEquivalentCount')
 return c is not None and int(c)>=1 and bool(list(g.objects(s,NLTL.connectedToMainPower))) and bool(list(g.objects(s,NLTL.connectedToEmergencyPower)))

def b088(cid,day=False,count=2,arc=360,alt=APPROVED,omit=None):
 g,ex,s=shipg(cid); vals={'operatesOnlyInContinuousDaylight':day,'bridgeControlledRotatableNarrowBeamSearchlightCount':count,'searchlightCoverageArc':arc,'alternateVisualIceDetectionMeansApprovalStatus':alt}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o088(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); day=lit(g,s,'operatesOnlyInContinuousDaylight') if s else None
 if day is None:return False
 if day is True:return True
 c=lit(g,s,'bridgeControlledRotatableNarrowBeamSearchlightCount'); a=qnum(g,s,'searchlightCoverageArc'); alt=one(g,s,'alternateVisualIceDetectionMeansApprovalStatus')
 return (c is not None and a is not None and int(c)>=2 and a>=360) or alt==APPROVED

def b089(cid,escort=True,light=True,astern=True,vis=2,colreg=True,omit=None):
 g,ex,s=shipg(cid); vals={'icebreakerEscortOperation':escort,'manuallyInitiatedFlashingRedStoppedLightPresent':light,'lightVisibleFromAstern':astern,'visibilityRange':vis,'colregSternLightArcComplianceStatus':colreg}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o089(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); e=lit(g,s,'icebreakerEscortOperation') if s else None
 if e is None:return False
 if e is False:return True
 return lit(g,s,'manuallyInitiatedFlashingRedStoppedLightPresent') is True and lit(g,s,'lightVisibleFromAstern') is True and (qnum(g,s,'visibilityRange') or -1)>=2 and lit(g,s,'colregSternLightArcComplianceStatus') is True

ORACLES={'IMO-081':o081,'IMO-082':o082,'IMO-083':o083,'IMO-084':o084,'IMO-085':o085,'IMO-086':o086,'IMO-087':o087,'IMO-088':o088,'IMO-089':o089}
CASES=[]
def add(req,cid,exp,builder,kw,rat): CASES.append(case(req,cid,exp,builder(cid,**kw),rat))
# 081
for x in [('P01','PASS',{},'Two independent echo sounders at applicability boundary.'),('P02','PASS',{'ind':0,'echo':1,'trans':2},'One device with two independent transducers.'),('P03','PASS',{'date':'2016-12-31','ind':0},'Pre-2017 not applicable.'),('P04','PASS',{'ice':False,'ind':0},'Non-ice-strengthened not applicable.'),('F01','FAIL',{'ind':1,'echo':1,'trans':1},'Neither alternative sufficient.'),('F02','FAIL',{'omit':'constructionDate'},'Missing construction date.'),('F03','FAIL',{'omit':'shipIceStrengthened'},'Missing ice-strengthening selector.'),('F04','FAIL',{'ind':0,'echo':1,'trans':0},'Transducer alternative incomplete.')]: add('IMO-081','IMO-081-I-'+x[0],x[1],b081,x[2],x[3])
#082
for x in [('P01','PASS',{},'SOLAS compliant and required astern view present.'),('P02','PASS',{'bridge':NLTL.bridgeConfigurationValue,'astern':False},'Other bridge configuration needs SOLAS compliance only.'),('F01','FAIL',{'solas':False},'Mandatory SOLAS compliance fails.'),('F02','FAIL',{'astern':False},'Required astern view missing.'),('F03','FAIL',{'omit':'bridgeConfigurationType'},'Missing bridge selector.'),('F04','FAIL',{'omit':'solasRegulationV22Point1Point9Point4ComplianceStatus'},'Missing SOLAS status.'),('F05','FAIL',{'omit':'clearViewAsternStatus'},'Missing astern view on required configuration.')]: add('IMO-082','IMO-082-I-'+x[0],x[1],b082,x[2],x[3])
#083
for x in [('P01','PASS',{},'One required antenna protected.'),('P02','PASS',{'vals':(True,True)},'All required antennas protected.'),('P03','PASS',{'likely':False,'vals':(False,)},'Not applicable without likely ice accretion.'),('F01','FAIL',{'vals':(False,)},'Required antenna unprotected.'),('F02','FAIL',{'vals':(True,False)},'Universal branch fails for one antenna.'),('F03','FAIL',{'omit_selector':True},'Missing applicability selector.'),('F04','FAIL',{'omit_value':True},'Missing antenna protection value.')]: add('IMO-083','IMO-083-I-'+x[0],x[1],b083,x[2],x[3])
#084
for x in [('P01','PASS',{},'Projecting sensor protected.'),('P02','PASS',{'projects':False,'protect':False},'Not applicable when no required sensor projects below hull.'),('F01','FAIL',{'protect':False},'Projecting sensor lacks protection.'),('F02','FAIL',{'omit':'requiredSensorProjectsBelowHull'},'Missing trigger.'),('F03','FAIL',{'omit':'sensorIceProtectionPresent'},'Missing protection result.')]: add('IMO-084','IMO-084-I-'+x[0],x[1],b084,x[2],x[3])
#085
for x in [('P01','PASS',{},'Category A post-2017 with enclosed wings.'),('P02','PASS',{'enclosed':False,'status':True},'Approved protection design alternative.'),('P03','PASS',{'cat':CAT_C,'enclosed':False,'status':False},'Category C not applicable.'),('P04','PASS',{'date':'2016-12-31','enclosed':False,'status':False},'Pre-2017 not applicable.'),('F01','FAIL',{'enclosed':False,'status':False},'Neither required route.'),('F02','FAIL',{'omit':'shipCategory'},'Missing category selector.'),('F03','FAIL',{'omit':'constructionDate'},'Missing date selector.'),('F04','FAIL',{'cat':CAT_B,'enclosed':False,'status':False},'Category B applicable and noncompliant.')]: add('IMO-085','IMO-085-I-'+x[0],x[1],b085,x[2],x[3])
#086
for x in [('P01','PASS',{},'Two distinct powered independent means.'),('P02','PASS',{'n':3},'Three valid means.'),('F01','FAIL',{'n':1},'Fewer than two means.'),('F02','FAIL',{'main':False},'Main power connection missing.'),('F03','FAIL',{'emerg':False},'Emergency power connection missing.'),('F04','FAIL',{'indep':False},'Independence relation missing.'),('F05','FAIL',{'wrong_target':True},'Independence target is not another ship-owned means.')]: add('IMO-086','IMO-086-I-'+x[0],x[1],b086,x[2],x[3])
#087
for x in [('P01','PASS',{},'Latitude above 80 with powered GNSS compass.'),('P02','PASS',{'lat':80,'count':0,'main':False,'emerg':False},'Exactly 80 degrees is not above 80.'),('P03','PASS',{'lat':79.9,'count':0,'main':False,'emerg':False},'Below threshold not applicable.'),('F01','FAIL',{'count':0},'No GNSS/equivalent above 80.'),('F02','FAIL',{'main':False},'Main power missing.'),('F03','FAIL',{'emerg':False},'Emergency power missing.'),('F04','FAIL',{'omit':'plannedOrActualLatitude'},'Missing latitude selector.')]: add('IMO-087','IMO-087-I-'+x[0],x[1],b087,x[2],x[3])
#088
for x in [('P01','PASS',{},'Two bridge-controlled searchlights with 360-degree arc.'),('P02','PASS',{'count':0,'arc':0,'alt':APPROVED},'Approved alternate detection means.'),('P03','PASS',{'day':True,'count':0,'arc':0,'alt':NLTL.evidenceStateRejected},'Sole 24-hour daylight operation not applicable.'),('F01','FAIL',{'count':1,'arc':360,'alt':NLTL.evidenceStateRejected},'Insufficient searchlight count and no alternative.'),('F02','FAIL',{'count':2,'arc':359,'alt':NLTL.evidenceStateRejected},'Coverage below 360 degrees.'),('F03','FAIL',{'count':0,'arc':0,'alt':NLTL.evidenceStateRejected},'Neither route satisfied.'),('F04','FAIL',{'omit':'operatesOnlyInContinuousDaylight'},'Missing applicability fact.'),('P04','PASS',{'count':3,'arc':400,'alt':NLTL.evidenceStateRejected},'Searchlight route above minima.')]: add('IMO-088','IMO-088-I-'+x[0],x[1],b088,x[2],x[3])
#089
for x in [('P01','PASS',{},'Escort stopped-light arrangement exactly meets requirements.'),('P02','PASS',{'escort':False,'light':False,'astern':False,'vis':0,'colreg':False},'No escort operation; obligation not applicable.'),('F01','FAIL',{'light':False},'Flashing red stopped light absent.'),('F02','FAIL',{'astern':False},'Light not visible from astern.'),('F03','FAIL',{'vis':1.9},'Visibility below two nautical miles.'),('F04','FAIL',{'colreg':False},'COLREG stern-light arc status noncompliant.'),('F05','FAIL',{'omit':'visibilityRange'},'Missing visibility range.'),('F06','FAIL',{'omit':'icebreakerEscortOperation'},'Missing escort-operation selector.')]: add('IMO-089','IMO-089-I-'+x[0],x[1],b089,x[2],x[3])

MANIFEST='imo_batch_i_manifest.jsonl';LOCK='imo_batch_i_fixture_lock.json';VALIDATOR='validate_imo_batch_i.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv: raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch I',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
