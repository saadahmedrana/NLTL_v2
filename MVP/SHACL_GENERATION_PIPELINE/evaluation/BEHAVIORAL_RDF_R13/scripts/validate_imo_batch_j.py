
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-j/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-091','IMO-092','IMO-094','IMO-095','IMO-097','IMO-098','IMO-099']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={'IMO-091':'Part I-A 10.2.1.3','IMO-092':'Part I-A 10.2.1.4','IMO-094':'Part I-A 10.3.1.2','IMO-095':'Part I-A 10.3.1.3','IMO-097':'Part I-A 10.3.2.1','IMO-098':'Part I-A 10.3.2.2','IMO-099':'Part I-A 10.3.2.3'}

def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def bg(cid,vals):
 g,ex,s=new_graph(BASE,cid)
 for t,v in vals.items(): add_value(g,s,t,v,ex)
 return g

def o091(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); return bool(s) and all(lit(g,s,t) is True for t in ['twoWayOnSceneCommunicationPresent','searchAndRescueCoordinationCommunicationPresent','aeronauticalFrequencyCapabilityPresent'])
def o092(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); return bool(s) and lit(g,s,'telemedicalAssistanceCommunicationEquipmentPresent') is True
def o094(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); tr=lit(g,s,'shipProvidesIcebreakingEscort') if s else None
 if tr is None:return False
 return True if tr is False else lit(g,s,'asternFacingSoundSignalingSystemPresent') is True and lit(g,s,'internationalCodeOfSignalsComplianceStatus') is True

def b095(cid,rcc=True,freqs=(121.5,123.1),omit_rcc=False):
 g,ex,s=new_graph(BASE,cid)
 if not omit_rcc:add_value(g,s,'rescueCoordinationCentreVoiceOrData',rcc,ex)
 for i,f in enumerate(freqs): add_value(g,s,'supportedAircraftVoiceFrequency',f,ex,name=f'freq{i+1}')
 return g
def o095(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None or lit(g,s,'rescueCoordinationCentreVoiceOrData') is not True:return False
 vals=[]
 for q in g.objects(s,NLTL.supportedAircraftVoiceFrequency):
  ns=list(g.objects(q,QUDT.numericValue)); us=list(g.objects(q,QUDT.unit))
  if len(ns)!=1 or len(us)!=1 or str(us[0])!=R13_UNIT_MHZ:return False
  vals.append(float(ns[0]))
 return any(close(x,121.5) for x in vals) and any(close(x,123.1) for x in vals)
R13_UNIT_MHZ=str(UNIT.MegaHZ)

def b097(cid,low=True,n=1,missing=None):
 g,ex,s=new_graph(BASE,cid); add_value(g,s,'shipOperatesInLowAirTemperature',low,ex)
 for i in range(n):
  c=typed(ex,g,f'craft{i+1}','survivalCraft'); add_raw_object(g,s,'hasSurvivalCraft',c); add_raw_object(g,s,'hasRequiredRescueBoatOrLifeboat',c)
  if missing!='distress': add_raw_object(g,c,'survivalCraftHasShipToShoreDistressAlertDevice',typed(ex,g,f'distress{i+1}','shipToShoreDistressAlertDevice'))
  if missing!='location': add_raw_object(g,c,'survivalCraftHasLocationSignalDevice',typed(ex,g,f'location{i+1}','locationSignalDevice'))
  if missing!='onscene': add_raw_object(g,c,'survivalCraftHasOnSceneCommunicationDevice',typed(ex,g,f'onscene{i+1}','onSceneCommunicationDevice'))
 return g
def o097(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); low=lit(g,s,'shipOperatesInLowAirTemperature') if s else None
 if low is None:return False
 if low is False:return True
 cs=list(g.objects(s,NLTL.hasRequiredRescueBoatOrLifeboat))
 if not cs:return False
 for c in cs:
  if not list(g.objects(c,NLTL.survivalCraftHasShipToShoreDistressAlertDevice)) or not list(g.objects(c,NLTL.survivalCraftHasLocationSignalDevice)) or not list(g.objects(c,NLTL.survivalCraftHasOnSceneCommunicationDevice)):return False
 return True

def b098(cid,low=True,n=1,missing=None):
 g,ex,s=new_graph(BASE,cid); add_value(g,s,'shipOperatesInLowAirTemperature',low,ex)
 for i in range(n):
  c=typed(ex,g,f'other{i+1}','otherSurvivalCraft'); add_raw_object(g,s,'hasOtherSurvivalCraft',c)
  if missing!='location': add_raw_object(g,c,'hasLocationSignalDevice',typed(ex,g,f'location{i+1}','locationSignalDevice'))
  if missing!='onscene': add_raw_object(g,c,'hasOnSceneCommunicationDevice',typed(ex,g,f'onscene{i+1}','onSceneCommunicationDevice'))
 return g
def o098(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None); low=lit(g,s,'shipOperatesInLowAirTemperature') if s else None
 if low is None:return False
 if low is False:return True
 for c in g.objects(s,NLTL.hasOtherSurvivalCraft):
  if not list(g.objects(c,NLTL.hasLocationSignalDevice)) or not list(g.objects(c,NLTL.hasOnSceneCommunicationDevice)):return False
 return True

def b099(cid,proc=True,active=True,rescue=5,avail=5,omit=None):
 g,ex,s=new_graph(BASE,cid); vals={'batteryLifeManagementProcedurePresent':proc,'procedureImplementationStatus':active,'maximumExpectedRescueTime':rescue,'communicationDeviceAvailability':avail}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o099(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 return lit(g,s,'batteryLifeManagementProcedurePresent') is True and lit(g,s,'procedureImplementationStatus') is True and qnum(g,s,'maximumExpectedRescueTime') is not None and qnum(g,s,'communicationDeviceAvailability') is not None and qnum(g,s,'communicationDeviceAvailability')>=qnum(g,s,'maximumExpectedRescueTime')

ORACLES={'IMO-091':o091,'IMO-092':o092,'IMO-094':o094,'IMO-095':o095,'IMO-097':o097,'IMO-098':o098,'IMO-099':o099}
CASES=[]
def add(req,cid,exp,g,rat):CASES.append(case(req,cid,exp,g,rat))
# 091
base091={'twoWayOnSceneCommunicationPresent':True,'searchAndRescueCoordinationCommunicationPresent':True,'aeronauticalFrequencyCapabilityPresent':True}
add('IMO-091','IMO-091-J-P01','PASS',bg('IMO-091-J-P01',base091),'All required SAR/on-scene capabilities present.')
for i,t in enumerate(base091,1):
 v=base091.copy();v[t]=False;add('IMO-091',f'IMO-091-J-F0{i}','FAIL',bg(f'IMO-091-J-F0{i}',v),f'{t} false.')
# 092
add('IMO-092','IMO-092-J-P01','PASS',bg('IMO-092-J-P01',{'telemedicalAssistanceCommunicationEquipmentPresent':True}),'Telemedical communication equipment present.')
add('IMO-092','IMO-092-J-F01','FAIL',bg('IMO-092-J-F01',{'telemedicalAssistanceCommunicationEquipmentPresent':False}),'Telemedical equipment absent.')
g,ex,s=new_graph(BASE,'IMO-092-J-F02');add('IMO-092','IMO-092-J-F02','FAIL',g,'Required presence value missing.')
#094
for cid,exp,vals,rat in [('P01','PASS',{'shipProvidesIcebreakingEscort':True,'asternFacingSoundSignalingSystemPresent':True,'internationalCodeOfSignalsComplianceStatus':True},'Escort ship has astern signaling and code compliance.'),('P02','PASS',{'shipProvidesIcebreakingEscort':False,'asternFacingSoundSignalingSystemPresent':False,'internationalCodeOfSignalsComplianceStatus':False},'Non-escort ship not applicable.'),('F01','FAIL',{'shipProvidesIcebreakingEscort':True,'asternFacingSoundSignalingSystemPresent':False,'internationalCodeOfSignalsComplianceStatus':True},'Sound signaling absent.'),('F02','FAIL',{'shipProvidesIcebreakingEscort':True,'asternFacingSoundSignalingSystemPresent':True,'internationalCodeOfSignalsComplianceStatus':False},'International Code of Signals status fails.')]: add('IMO-094','IMO-094-J-'+cid,exp,bg('IMO-094-J-'+cid,vals),rat)
#095
for cid,exp,kw,rat in [('P01','PASS',{},'Both mandated aircraft frequencies and RCC communication present.'),('P02','PASS',{'freqs':(123.1,121.5,130.0)},'Required frequencies can coexist with extras.'),('F01','FAIL',{'freqs':(121.5,)},'123.1 MHz missing.'),('F02','FAIL',{'freqs':(123.1,)},'121.5 MHz missing.'),('F03','FAIL',{'rcc':False},'RCC voice/data capability absent.'),('F04','FAIL',{'omit_rcc':True},'RCC capability value missing.')]: add('IMO-095','IMO-095-J-'+cid,exp,b095('IMO-095-J-'+cid,**kw),rat)
#097
for cid,exp,kw,rat in [('P01','PASS',{},'Released craft has all three communication device types.'),('P02','PASS',{'n':2},'Every represented required craft has all device types.'),('P03','PASS',{'low':False,'n':0},'Low-air-temperature condition false.'),('F01','FAIL',{'missing':'distress'},'Distress-alert device missing.'),('F02','FAIL',{'missing':'location'},'Location device missing.'),('F03','FAIL',{'missing':'onscene'},'On-scene device missing.'),('F04','FAIL',{'n':0},'Applicable ship has no represented required rescue boat/lifeboat.')]: add('IMO-097','IMO-097-J-'+cid,exp,b097('IMO-097-J-'+cid,**kw),rat)
#098
for cid,exp,kw,rat in [('P01','PASS',{},'Other survival craft has both required device types.'),('P02','PASS',{'n':2},'All other survival craft compliant.'),('P03','PASS',{'low':False,'n':1,'missing':'location'},'Condition not applicable outside low air temperature.'),('F01','FAIL',{'missing':'location'},'Location signal device missing.'),('F02','FAIL',{'missing':'onscene'},'On-scene communication device missing.'),('F03','FAIL',{'n':2,'missing':'location'},'Universal craft rule fails when required devices omitted.')]: add('IMO-098','IMO-098-J-'+cid,exp,b098('IMO-098-J-'+cid,**kw),rat)
#099
for cid,exp,kw,rat in [('P01','PASS',{},'Availability exactly equals maximum rescue time.'),('P02','PASS',{'avail':7},'Device availability exceeds rescue time.'),('F01','FAIL',{'proc':False},'Battery-life management procedure absent.'),('F02','FAIL',{'active':False},'Procedure not implemented.'),('F03','FAIL',{'avail':4.9},'Communication availability shorter than rescue time.'),('F04','FAIL',{'omit':'communicationDeviceAvailability'},'Availability duration missing.'),('F05','FAIL',{'omit':'maximumExpectedRescueTime'},'Rescue-time duration missing.')]: add('IMO-099','IMO-099-J-'+cid,exp,b099('IMO-099-J-'+cid,**kw),rat)

MANIFEST='imo_batch_j_manifest.jsonl';LOCK='imo_batch_j_fixture_lock.json';VALIDATOR='validate_imo_batch_j.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv: raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch J',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
