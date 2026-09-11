
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-h/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-075','IMO-077','IMO-078','IMO-079']
MODES={'IMO-075':'DIRECT_CALCULATION','IMO-077':'DIRECT_CALCULATION','IMO-078':'DIRECT_STATIC','IMO-079':'DIRECT_CALCULATION'}
CLAUSES={'IMO-075':'Part I-A 8.3.3.3.3.2','IMO-077':'Part I-A 8.3.3.3.3.5','IMO-078':'Part I-A 8.3.3.3.3.6-.7','IMO-079':'Part I-A 8.3.3.4'}

def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}

def b075(cid,required=True,persons=10,cap=11,accessible=True,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 vals={'personalOrGroupSurvivalEquipmentRequired':required,'personsOnBoard':persons,'availableSurvivalEquipmentCapacity':cap,'storageAccessibilityStatus':accessible}
 for t,v in vals.items():
  if omit!=t:add_value(g,ship,t,v,ex)
 return g

def o075(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 req=lit(g,ship,'personalOrGroupSurvivalEquipmentRequired')
 if req is None:return False
 if req is False:return True
 p=lit(g,ship,'personsOnBoard'); c=lit(g,ship,'availableSurvivalEquipmentCapacity'); a=lit(g,ship,'storageAccessibilityStatus')
 return p is not None and c is not None and int(c)>=math.ceil(int(p)*1.10) and a is True

def b077(cid,carried=True,persons=10,extra=2,loaded=1200,craft=12,launch=1200,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 vals={'additionalEquipmentCarriedInSurvivalCraft':carried,'personsCapacityRequirement':persons,'additionalEquipmentCapacityRequirement':extra,'loadedSurvivalCraftRequirement':loaded,'survivalCraftAvailableCapacity':craft,'launchingApplianceCapacity':launch}
 for t,v in vals.items():
  if omit!=t:add_value(g,ship,t,v,ex)
 return g

def o077(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 tr=lit(g,ship,'additionalEquipmentCarriedInSurvivalCraft')
 if tr is None:return False
 if tr is False:return True
 p=lit(g,ship,'personsCapacityRequirement'); e=lit(g,ship,'additionalEquipmentCapacityRequirement'); sc=lit(g,ship,'survivalCraftAvailableCapacity')
 l=qnum(g,ship,'loadedSurvivalCraftRequirement'); lc=qnum(g,ship,'launchingApplianceCapacity')
 return None not in (p,e,sc,l,lc) and int(sc)>=int(p)+int(e) and lc>=l

def b078(cid,passengers=0,crew=0,pok=True,cok=True,omit_p=False,omit_c=False):
 g,ex,ship=new_graph(BASE,cid)
 for i in range(passengers):
  p=typed(ex,g,f'passenger{i+1}','passenger'); add_value(g,ship,'hasPassenger',p,ex)
  if not omit_p:add_value(g,p,'personalSurvivalEquipmentInstructionCompleted',pok,ex)
 for i in range(crew):
  c=typed(ex,g,f'crew{i+1}','crewMember'); add_value(g,ship,'hasCrewMemberInventory',c,ex)
  if not omit_c:add_value(g,c,'personalAndGroupSurvivalEquipmentTrainingCompleted',cok,ex)
 return g

def o078(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 for p in g.objects(ship,NLTL.hasPassenger):
  if lit(g,p,'personalSurvivalEquipmentInstructionCompleted') is not True:return False
 for c in g.objects(ship,NLTL.hasCrewMemberInventory):
  if lit(g,c,'personalAndGroupSurvivalEquipmentTrainingCompleted') is not True:return False
 return True

def b079(cid,persons=10,rescue_days=5,rations=50,omit=None,unit_override=None):
 g,ex,ship=new_graph(BASE,cid)
 if omit!='personsOnBoard':add_value(g,ship,'personsOnBoard',persons,ex)
 if omit!='maximumExpectedRescueTime':add_value(g,ship,'maximumExpectedRescueTime',rescue_days,ex)
 if omit!='availableEmergencyRationPerson':add_value(g,ship,'availableEmergencyRationPerson',rations,ex,unit_override=unit_override)
 return g

def o079(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 p=lit(g,ship,'personsOnBoard'); d=qnum(g,ship,'maximumExpectedRescueTime'); r=qnum(g,ship,'availableEmergencyRationPerson')
 return None not in (p,d,r) and r>=int(p)*d

ORACLES={'IMO-075':o075,'IMO-077':o077,'IMO-078':o078,'IMO-079':o079}
CASES=[]
# 075: trigger, exact ceil boundary, violation, missing values, accessibility
for cid,exp,kw,rat in [
 ('IMO-075-H-P01','PASS',{},'10 persons requires ceil(11.0)=11 and accessible storage.'),
 ('IMO-075-H-P02','PASS',{'persons':11,'cap':13},'11 persons requires ceil(12.1)=13.'),
 ('IMO-075-H-F01','FAIL',{'cap':10},'Capacity below 110 percent requirement.'),
 ('IMO-075-H-F02','FAIL',{'accessible':False},'Storage is not accessible.'),
 ('IMO-075-H-F03','FAIL',{'omit':'personsOnBoard'},'Missing formula operand.'),
 ('IMO-075-H-F04','FAIL',{'omit':'availableSurvivalEquipmentCapacity'},'Missing calculated capacity result.'),
 ('IMO-075-H-F05','FAIL',{'omit':'storageAccessibilityStatus'},'Missing storage status.'),
 ('IMO-075-H-P03','PASS',{'required':False,'persons':0,'cap':0,'accessible':False},'Conditional obligation not applicable.'),
 ('IMO-075-H-P04','PASS',{'persons':1,'cap':2},'Ceiling behavior at one person.')]:
 CASES.append(case('IMO-075',cid,exp,b075(cid,**kw),rat))
# 077
for cid,exp,kw,rat in [
 ('IMO-077-H-P01','PASS',{},'Exact personnel+equipment capacity and launching mass boundary.'),
 ('IMO-077-H-P02','PASS',{'craft':15,'launch':1500},'Capacity above both minima.'),
 ('IMO-077-H-F01','FAIL',{'craft':11},'Survival craft capacity below summed requirement.'),
 ('IMO-077-H-F02','FAIL',{'launch':1199},'Launching appliance capacity below loaded craft requirement.'),
 ('IMO-077-H-F03','FAIL',{'omit':'additionalEquipmentCapacityRequirement'},'Missing calculation operand.'),
 ('IMO-077-H-F04','FAIL',{'omit':'launchingApplianceCapacity'},'Missing required result.'),
 ('IMO-077-H-P03','PASS',{'carried':False,'craft':0,'launch':0},'Conditional obligation not applicable.'),
 ('IMO-077-H-F05','FAIL',{'omit':'additionalEquipmentCarriedInSurvivalCraft'},'Missing applicability fact.')]:
 CASES.append(case('IMO-077',cid,exp,b077(cid,**kw),rat))
# 078
for cid,exp,kw,rat in [
 ('IMO-078-H-P01','PASS',{'passengers':1,'crew':1},'Passenger instructed and crew trained.'),
 ('IMO-078-H-P02','PASS',{'passengers':2,'crew':2},'All linked persons satisfy universal rule.'),
 ('IMO-078-H-P03','PASS',{},'No represented passengers or crew; universal set is empty.'),
 ('IMO-078-H-F01','FAIL',{'passengers':1,'crew':1,'pok':False},'Passenger instruction incomplete.'),
 ('IMO-078-H-F02','FAIL',{'passengers':1,'crew':1,'cok':False},'Crew training incomplete.'),
 ('IMO-078-H-F03','FAIL',{'passengers':1,'omit_p':True},'Passenger instruction value missing.'),
 ('IMO-078-H-F04','FAIL',{'crew':1,'omit_c':True},'Crew training value missing.'),
 ('IMO-078-H-F05','FAIL',{'passengers':2,'crew':1,'pok':False},'Universal passenger rule fails when any linked passenger fails.')]:
 CASES.append(case('IMO-078',cid,exp,b078(cid,**kw),rat))
# 079
for cid,exp,kw,rat in [
 ('IMO-079-H-P01','PASS',{},'Exact person-day ration boundary 10x5=50.'),
 ('IMO-079-H-P02','PASS',{'persons':7,'rescue_days':6,'rations':45},'Rations above 42 person-days.'),
 ('IMO-079-H-F01','FAIL',{'rations':49},'Rations one person-day below minimum.'),
 ('IMO-079-H-F02','FAIL',{'omit':'personsOnBoard'},'Missing persons operand.'),
 ('IMO-079-H-F03','FAIL',{'omit':'maximumExpectedRescueTime'},'Missing rescue-time operand.'),
 ('IMO-079-H-F04','FAIL',{'omit':'availableEmergencyRationPerson'},'Missing ration result.'),
 ('IMO-079-H-F05','FAIL',{'unit_override':UNIT.HR},'Wrong unit on ration duration quantity.'),
 ('IMO-079-H-P03','PASS',{'persons':1,'rescue_days':5,'rations':5},'Minimum one-person five-day boundary.')]:
 CASES.append(case('IMO-079',cid,exp,b079(cid,**kw),rat))

MANIFEST='imo_batch_h_manifest.jsonl';LOCK='imo_batch_h_fixture_lock.json';VALIDATOR='validate_imo_batch_h.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:
  raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch H',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
