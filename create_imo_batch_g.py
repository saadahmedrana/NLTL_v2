
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


BASE='https://w3id.org/nltl/benchmark/imo-batch-g/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-062','IMO-064','IMO-065','IMO-066','IMO-068','IMO-069','IMO-070','IMO-071','IMO-072','IMO-073']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
 'IMO-062':'Part I-A 8.2.1.1','IMO-064':'Part I-A 8.2.3.1','IMO-065':'Part I-A 8.2.3.3',
 'IMO-066':'Part I-A 8.3.1.1','IMO-068':'Part I-A 8.3.2.1','IMO-069':'Part I-A 8.3.2.2',
 'IMO-070':'Part I-A 8.3.3.1.1','IMO-071':'Part I-A 8.3.3.1.2','IMO-072':'Part I-A 8.3.3.2',
 'IMO-073':'Part I-A 8.3.3.3.1'
}
APPROVED=NLTL.evidenceStateApproved; REJECTED=NLTL.evidenceStateRejected
INSULATED=NLTL.insulatedImmersionSuit
PARTIAL=NLTL.partiallyEnclosedLifeboat; TOTAL=NLTL.totallyEnclosedLifeboat
PROTECTED_CATEGORIES=[
 NLTL.escapeRouteProtectedItem,NLTL.musterStationProtectedItem,NLTL.embarkationAreaProtectedItem,
 NLTL.survivalCraftProtectedItem,NLTL.launchingApplianceProtectedItem,NLTL.survivalCraftAccessProtectedItem]
ALLOWED_EQUIPMENT={NLTL.immersionSuitEquipment,NLTL.thermalProtectiveAidEquipment}

def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}

def b062(cid,routes=None):
 g,ex,ship=new_graph(BASE,cid)
 for spec in routes or []:
  r=typed(ex,g,spec.get('name','route'),'exposedEscapeRoute'); add_value(g,ship,'hasExposedEscapeRoute',r,ex)
  if not spec.get('omit_access'): add_value(g,r,'accessibleStatus',spec.get('accessible',True),ex)
  if not spec.get('omit_safe'): add_value(g,r,'safeStatus',spec.get('safe',True),ex)
  if not spec.get('omit_evidence'):
   ev=typed(ex,g,spec.get('name','route')+'Evidence','evidenceArtifact')
   owner=ship if spec.get('wrong_evidence_owner') else r
   add_value(g,owner,'hasEscapeRouteIceSnowMitigationEvidence',ev,ex)
   if not spec.get('omit_coverage'): add_value(g,ev,'iceSnowMitigationCoverage',spec.get('coverage',True),ex)
 return g

def o062(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 for r in g.objects(ship,NLTL.hasExposedEscapeRoute):
  if lit(g,r,'accessibleStatus') is not True or lit(g,r,'safeStatus') is not True:return False
  evs=list(g.objects(r,NLTL.hasEscapeRouteIceSnowMitigationEvidence))
  if not evs:return False
  if not any(lit(g,e,'iceSnowMitigationCoverage') is True for e in evs):return False
 return True

def b064(cid,persons=10,assigned=True,voyage='polar voyage',cold='anticipated cold',wind='anticipated wind',immersion=True,status=APPROVED,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 vals={'personOnBoard':persons,'assignedThermalProtection':assigned,'intendedVoyage':voyage,'anticipatedCold':cold,'anticipatedWind':wind,'immersionPotential':immersion,'thermalProtectionApprovalStatus':status}
 for t,v in vals.items():
  if omit!=t:add_value(g,ship,t,v,ex)
 return g

def o064(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 p=lit(g,ship,'personOnBoard')
 if not isinstance(p,int) or p<1:return False
 if lit(g,ship,'assignedThermalProtection') is not True:return False
 for t in ['intendedVoyage','anticipatedCold','anticipatedWind']:
  v=lit(g,ship,t)
  if not isinstance(v,str) or not v.strip():return False
 if not isinstance(lit(g,ship,'immersionPotential'),bool):return False
 return one(g,ship,'thermalProtectionApprovalStatus')==APPROVED

def b065(cid,max_days=5,support_days=5,env='water, ice or land',hab=True,weather=True,space=True,sust=True,access=True,comm=True,omit=None,wrong_unit=None):
 g,ex,ship=new_graph(BASE,cid)
 vals={'abandonmentEnvironment':env,'habitableEnvironmentPresent':hab,'weatherProtectionPresent':weather,'accommodationSpacePresent':space,'sustenanceMeansPresent':sust,'safeAccessExitPresent':access,'rescueCommunicationPresent':comm}
 for t,v in vals.items():
  if omit!=t:add_value(g,ship,t,v,ex)
 if omit!='maximumExpectedRescueTime': add_value(g,ship,'maximumExpectedRescueTime',max_days,ex,unit_override=UNIT.HR if wrong_unit=='maximumExpectedRescueTime' else None)
 if omit!='survivalSupportDuration': add_value(g,ship,'survivalSupportDuration',support_days,ex,unit_override=UNIT.HR if wrong_unit=='survivalSupportDuration' else None)
 return g

def o065(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 env=lit(g,ship,'abandonmentEnvironment')
 if not isinstance(env,str) or not env.strip():return False
 mx=qnum(g,ship,'maximumExpectedRescueTime'); sd=qnum(g,ship,'survivalSupportDuration')
 if mx is None or sd is None or sd<mx:return False
 for t in ['habitableEnvironmentPresent','weatherProtectionPresent','accommodationSpacePresent','sustenanceMeansPresent','safeAccessExitPresent','rescueCommunicationPresent']:
  if lit(g,ship,t) is not True:return False
 return True

def b066(cid,exposed=True,categories=None,missing_means_index=None,wrong_owner_index=None,omit_selector=False):
 g,ex,ship=new_graph(BASE,cid)
 if not omit_selector:add_value(g,ship,'shipExposedToIceAccretion',exposed,ex)
 cats=PROTECTED_CATEGORIES if categories is None else categories
 for i,cat in enumerate(cats):
  item=typed(ex,g,f'protectedItem{i+1}','protectedItem'); add_value(g,ship,'hasProtectedItem',item,ex)
  add_value(g,item,'protectedItemCategory',cat,ex)
  if i==missing_means_index:continue
  means=typed(ex,g,f'iceSnowMeans{i+1}','iceSnowRemovalOrPreventionMeans')
  owner=ship if i==wrong_owner_index else item
  add_value(g,owner,'hasIceSnowRemovalOrPreventionMeans',means,ex)
 return g

def o066(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 exposed=lit(g,ship,'shipExposedToIceAccretion')
 if not isinstance(exposed,bool):return False
 if not exposed:return True
 seen=set()
 for item in g.objects(ship,NLTL.hasProtectedItem):
  cats=list(g.objects(item,NLTL.protectedItemCategory))
  if len(cats)!=1 or cats[0] not in PROTECTED_CATEGORIES:return False
  seen.add(cats[0])
  if not list(g.objects(item,NLTL.hasIceSnowRemovalOrPreventionMeans)):return False
 return seen==set(PROTECTED_CATEGORIES)

def b068(cid,ice=True,direct=False,safe=True,status=APPROVED,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 vals={'shipOperatesInIceCoveredWaters':ice,'directEvacuationOntoIceApplicable':direct,'safeEvacuationMeansPresent':safe,'survivalEquipmentDeploymentApprovalStatus':status}
 for t,v in vals.items():
  if omit!=t:add_value(g,ship,t,v,ex)
 return g

def o068(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 ice=lit(g,ship,'shipOperatesInIceCoveredWaters'); direct=lit(g,ship,'directEvacuationOntoIceApplicable')
 if not isinstance(ice,bool) or not isinstance(direct,bool):return False
 if not (ice or direct):return True
 return lit(g,ship,'safeEvacuationMeansPresent') is True and one(g,ship,'survivalEquipmentDeploymentApprovalStatus')==APPROVED

def b069(cid,requires=True,independent=True,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 if omit!='addedLifeSavingDeviceRequiresPower':add_value(g,ship,'addedLifeSavingDeviceRequiresPower',requires,ex)
 if omit!='devicePowerSourceIndependentOfMainPower':add_value(g,ship,'devicePowerSourceIndependentOfMainPower',independent,ex)
 return g

def o069(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 req=lit(g,ship,'addedLifeSavingDeviceRequiresPower')
 if not isinstance(req,bool):return False
 if not req:return True
 return lit(g,ship,'devicePowerSourceIndependentOfMainPower') is True

def b070(cid,passenger=True,people=None):
 g,ex,ship=new_graph(BASE,cid)
 if passenger:g.add((ship,RDF.type,NLTL.passengerShip))
 for spec in people or []:
  p=typed(ex,g,spec.get('name','person'),'personOnBoardMember'); add_value(g,ship,'hasPersonOnBoardMember',p,ex)
  for j,eqspec in enumerate(spec.get('equipment',[{'kind':'suit','compatible':True}])):
   a=typed(ex,g,f"{spec.get('name','person')}Assignment{j+1}",'personalSurvivalEquipmentAssignment')
   if not eqspec.get('wrong_assignment_owner'):add_value(g,p,'hasPersonalSurvivalEquipmentAssignment',a,ex)
   else:add_value(g,ship,'hasPersonalSurvivalEquipmentAssignment',a,ex)
   if eqspec.get('omit_equipment'):continue
   cls='immersionSuitEquipment' if eqspec.get('kind','suit')=='suit' else ('thermalProtectiveAidEquipment' if eqspec.get('kind')=='thermal' else 'personalSurvivalEquipment')
   e=typed(ex,g,f"{spec.get('name','person')}Equipment{j+1}",cls); add_value(g,a,'assignedPersonalSurvivalEquipment',e,ex)
   if not eqspec.get('omit_compatibility'):add_value(g,e,'sizeCompatibilityStatus',eqspec.get('compatible',True),ex)
 return g

def o070(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 if (ship,RDF.type,NLTL.passengerShip) not in g:return True
 for p in g.objects(ship,NLTL.hasPersonOnBoardMember):
  good=False
  for a in g.objects(p,NLTL.hasPersonalSurvivalEquipmentAssignment):
   for e in g.objects(a,NLTL.assignedPersonalSurvivalEquipment):
    if set(g.objects(e,RDF.type)) & ALLOWED_EQUIPMENT and lit(g,e,'sizeCompatibilityStatus') is True: good=True
  if not good:return False
 return True

def b071(cid,required=True,itype=INSULATED,omit=None):
 g,ex,ship=new_graph(BASE,cid)
 if omit!='immersionSuitRequired':add_value(g,ship,'immersionSuitRequired',required,ex)
 if omit!='immersionSuitTypeClassification':
  val=itype if itype is not None else typed(ex,g,'uninsulatedSuitType','immersionSuitTypeValue')
  add_value(g,ship,'immersionSuitTypeClassification',val,ex)
 return g

def o071(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 req=lit(g,ship,'immersionSuitRequired')
 if not isinstance(req,bool):return False
 if not req:return True
 return one(g,ship,'immersionSuitTypeClassification')==INSULATED

def b072(cid,dark=True,boats=None,omit_selector=False):
 g,ex,ship=new_graph(BASE,cid)
 if not omit_selector:add_value(g,ship,'extendedDarknessOperation',dark,ex)
 for spec in boats or []:
  b=typed(ex,g,spec.get('name','boat'),'lifeboat'); add_value(g,ship,'hasLifeboat',b,ex)
  if spec.get('omit_searchlight'):continue
  s=typed(ex,g,spec.get('name','boat')+'Searchlight','searchlight')
  owner=ship if spec.get('wrong_owner') else b
  add_value(g,owner,'hasAssignedSearchlight',s,ex)
  if not spec.get('omit_status'):add_value(g,s,'searchlightContinuousUseSuitabilityStatus',spec.get('suitable',True),ex)
 return g

def o072(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 dark=lit(g,ship,'extendedDarknessOperation')
 if not isinstance(dark,bool):return False
 if not dark:return True
 for b in g.objects(ship,NLTL.hasLifeboat):
  sl=list(g.objects(b,NLTL.hasAssignedSearchlight))
  if not sl:return False
  if not any(lit(g,s,'searchlightContinuousUseSuitabilityStatus') is True for s in sl):return False
 return True

def b073(cid,boats=None):
 g,ex,ship=new_graph(BASE,cid)
 for spec in boats or []:
  b=typed(ex,g,spec.get('name','boat'),'lifeboat'); add_value(g,ship,'hasLifeboat',b,ex)
  if spec.get('omit_type'):continue
  typ=PARTIAL if spec.get('type','partial')=='partial' else (TOTAL if spec.get('type')=='total' else typed(ex,g,spec.get('name','boat')+'OpenType','lifeboatTypeValue'))
  add_value(g,b,'lifeboatTypeClassification',typ,ex)
 return g

def o073(g):
 ship=next(g.subjects(RDF.type,NLTL.ship),None)
 if ship is None:return False
 for b in g.objects(ship,NLTL.hasLifeboat):
  typ=one(g,b,'lifeboatTypeClassification')
  if typ not in {PARTIAL,TOTAL}:return False
 return True

ORACLES={'IMO-062':o062,'IMO-064':o064,'IMO-065':o065,'IMO-066':o066,'IMO-068':o068,'IMO-069':o069,'IMO-070':o070,'IMO-071':o071,'IMO-072':o072,'IMO-073':o073}
CASES=[]
# 062
for cid,exp,g,rat in [
('IMO-062-P01','PASS',b062('IMO-062-P01',[{'name':'route1'}]),'Exposed escape route accessible, safe and supported by mitigation evidence.'),
('IMO-062-P02','PASS',b062('IMO-062-P02',[{'name':'route1'},{'name':'route2'}]),'Multiple exposed escape routes all satisfy evidence/status requirements.'),
('IMO-062-P03','PASS',b062('IMO-062-P03',[]),'No exposed escape route represented; no route existence cardinality invented.'),
('IMO-062-F01','FAIL',b062('IMO-062-F01',[{'name':'route1','accessible':False}]),'Route is not accessible.'),
('IMO-062-F02','FAIL',b062('IMO-062-F02',[{'name':'route1','safe':False}]),'Route is not safe.'),
('IMO-062-F03','FAIL',b062('IMO-062-F03',[{'name':'route1','omit_evidence':True}]),'Ice/snow mitigation evidence relationship missing.'),
('IMO-062-F04','FAIL',b062('IMO-062-F04',[{'name':'route1','coverage':False}]),'Mitigation evidence does not establish coverage.'),
('IMO-062-F05','FAIL',b062('IMO-062-F05',[{'name':'route1','wrong_evidence_owner':True}]),'Evidence exists but on wrong owner/path.'),
('IMO-062-F06','FAIL',b062('IMO-062-F06',[{'name':'route1'},{'name':'route2','safe':False}]),'Universal route condition fails when one represented route is unsafe.')]:CASES.append(case('IMO-062',cid,exp,g,rat))
# 064
for cid,exp,g,rat in [
('IMO-064-P01','PASS',b064('IMO-064-P01'),'Thermal protection and approved adequacy context represented for persons on board.'),
('IMO-064-P02','PASS',b064('IMO-064-P02',persons=1,immersion=False),'Single person with non-applicable immersion still has complete cold/wind/voyage adequacy context.'),
('IMO-064-F01','FAIL',b064('IMO-064-F01',assigned=False),'Thermal protection not assigned.'),
('IMO-064-F02','FAIL',b064('IMO-064-F02',status=REJECTED),'Thermal-protection adequacy approval rejected.'),
('IMO-064-F03','FAIL',b064('IMO-064-F03',omit='intendedVoyage'),'Intended-voyage context missing.'),
('IMO-064-F04','FAIL',b064('IMO-064-F04',omit='anticipatedCold'),'Anticipated-cold context missing.'),
('IMO-064-F05','FAIL',b064('IMO-064-F05',omit='anticipatedWind'),'Anticipated-wind context missing.'),
('IMO-064-F06','FAIL',b064('IMO-064-F06',omit='thermalProtectionApprovalStatus'),'Adequacy approval status missing.')]:CASES.append(case('IMO-064',cid,exp,g,rat))
# 065
for cid,exp,g,rat in [
('IMO-065-P01','PASS',b065('IMO-065-P01',5,5),'Support duration exactly equals maximum expected rescue time.'),
('IMO-065-P02','PASS',b065('IMO-065-P02',5,7),'Support duration exceeds required rescue time.'),
('IMO-065-P03','PASS',b065('IMO-065-P03',7,7,env='ice'),'Alternative assessed abandonment environment with complete functions.'),
('IMO-065-F01','FAIL',b065('IMO-065-F01',5,4.9),'Support duration shorter than maximum expected rescue time.'),
('IMO-065-F02','FAIL',b065('IMO-065-F02',hab=False),'Habitable environment missing.'),
('IMO-065-F03','FAIL',b065('IMO-065-F03',weather=False),'Cold/wind/sun protection missing.'),
('IMO-065-F04','FAIL',b065('IMO-065-F04',space=False),'Accommodation space missing.'),
('IMO-065-F05','FAIL',b065('IMO-065-F05',sust=False),'Sustenance means missing.'),
('IMO-065-F06','FAIL',b065('IMO-065-F06',access=False),'Safe access/exit means missing.'),
('IMO-065-F07','FAIL',b065('IMO-065-F07',comm=False),'Rescue communication means missing.'),
('IMO-065-F08','FAIL',b065('IMO-065-F08',omit='survivalSupportDuration'),'Support-duration quantity missing.'),
('IMO-065-F09','FAIL',b065('IMO-065-F09',wrong_unit='survivalSupportDuration'),'Support duration uses wrong frozen R13 unit.')]:CASES.append(case('IMO-065',cid,exp,g,rat))
# 066
missing_cats=PROTECTED_CATEGORIES[:-1]
for cid,exp,g,rat in [
('IMO-066-P01','PASS',b066('IMO-066-P01'),'All six protected-item categories have associated removal/prevention means.'),
('IMO-066-P02','PASS',b066('IMO-066-P02',exposed=False,categories=[]),'Ship not exposed to ice accretion: requirement inactive.'),
('IMO-066-F01','FAIL',b066('IMO-066-F01',categories=missing_cats),'One mandatory protected-item category is absent.'),
('IMO-066-F02','FAIL',b066('IMO-066-F02',missing_means_index=0),'Escape-route protected item lacks associated means.'),
('IMO-066-F03','FAIL',b066('IMO-066-F03',missing_means_index=1),'Muster-station protected item lacks associated means.'),
('IMO-066-F04','FAIL',b066('IMO-066-F04',missing_means_index=2),'Embarkation-area protected item lacks associated means.'),
('IMO-066-F05','FAIL',b066('IMO-066-F05',missing_means_index=3),'Survival-craft protected item lacks associated means.'),
('IMO-066-F06','FAIL',b066('IMO-066-F06',missing_means_index=4),'Launching-appliance protected item lacks associated means.'),
('IMO-066-F07','FAIL',b066('IMO-066-F07',missing_means_index=5),'Survival-craft-access protected item lacks associated means.'),
('IMO-066-F08','FAIL',b066('IMO-066-F08',omit_selector=True),'Ice-accretion applicability selector missing.')]:CASES.append(case('IMO-066',cid,exp,g,rat))
# 068
for cid,exp,g,rat in [
('IMO-068-P01','PASS',b068('IMO-068-P01',True,False,True,APPROVED),'Ice-covered-water route with safe evacuation and approved deployment.'),
('IMO-068-P02','PASS',b068('IMO-068-P02',False,True,True,APPROVED),'Direct evacuation onto ice independently activates obligation.'),
('IMO-068-P03','PASS',b068('IMO-068-P03',True,True,True,APPROVED),'Both applicability routes simultaneously satisfied.'),
('IMO-068-P04','PASS',b068('IMO-068-P04',False,False,False,REJECTED),'Neither applicability route active.'),
('IMO-068-F01','FAIL',b068('IMO-068-F01',True,False,False,APPROVED),'Safe evacuation means missing on applicable operation.'),
('IMO-068-F02','FAIL',b068('IMO-068-F02',True,False,True,REJECTED),'Survival-equipment deployment approval rejected.'),
('IMO-068-F03','FAIL',b068('IMO-068-F03',False,True,True,APPROVED,omit='safeEvacuationMeansPresent'),'Safe-evacuation result missing.'),
('IMO-068-F04','FAIL',b068('IMO-068-F04',omit='shipOperatesInIceCoveredWaters'),'Applicability selector missing.')]:CASES.append(case('IMO-068',cid,exp,g,rat))
# 069
for cid,exp,g,rat in [
('IMO-069-P01','PASS',b069('IMO-069-P01',True,True),'Added powered life-saving device has independent power.'),
('IMO-069-P02','PASS',b069('IMO-069-P02',False,False),'Device does not require power; independence obligation inactive.'),
('IMO-069-F01','FAIL',b069('IMO-069-F01',True,False),'Added powered device relies on main power.'),
('IMO-069-F02','FAIL',b069('IMO-069-F02',True,omit='devicePowerSourceIndependentOfMainPower'),'Independence state missing on applicable case.'),
('IMO-069-F03','FAIL',b069('IMO-069-F03',omit='addedLifeSavingDeviceRequiresPower'),'Power-requirement selector missing.')]:CASES.append(case('IMO-069',cid,exp,g,rat))
# 070
for cid,exp,g,rat in [
('IMO-070-P01','PASS',b070('IMO-070-P01',True,[{'name':'person1','equipment':[{'kind':'suit'}]}]),'Passenger has properly sized immersion suit.'),
('IMO-070-P02','PASS',b070('IMO-070-P02',True,[{'name':'person1','equipment':[{'kind':'thermal'}]}]),'Thermal protective aid is an independent permitted route.'),
('IMO-070-P03','PASS',b070('IMO-070-P03',True,[{'name':'person1','equipment':[{'kind':'suit'},{'kind':'thermal'}]}]),'Both valid equipment routes may be present.'),
('IMO-070-P04','PASS',b070('IMO-070-P04',True,[{'name':'person1'},{'name':'person2','equipment':[{'kind':'thermal'}]}]),'Multiple persons each have a compatible permitted assignment.'),
('IMO-070-P05','PASS',b070('IMO-070-P05',False,[{'name':'person1','equipment':[{'kind':'other','compatible':False}]}]),'Non-passenger ship is outside conditional requirement.'),
('IMO-070-F01','FAIL',b070('IMO-070-F01',True,[{'name':'person1','equipment':[]}]),'Passenger has no permitted equipment assignment.'),
('IMO-070-F02','FAIL',b070('IMO-070-F02',True,[{'name':'person1','equipment':[{'kind':'suit','compatible':False}]}]),'Assigned suit is not size compatible.'),
('IMO-070-F03','FAIL',b070('IMO-070-F03',True,[{'name':'person1','equipment':[{'kind':'other','compatible':True}]}]),'Assigned equipment is not an immersion suit or thermal protective aid.'),
('IMO-070-F04','FAIL',b070('IMO-070-F04',True,[{'name':'person1'},{'name':'person2','equipment':[{'kind':'thermal','compatible':False}]}]),'One of multiple passengers has no valid compatible route.')]:CASES.append(case('IMO-070',cid,exp,g,rat))
# 071
for cid,exp,g,rat in [
('IMO-071-P01','PASS',b071('IMO-071-P01',True,INSULATED),'Required immersion suit is insulated.'),
('IMO-071-P02','PASS',b071('IMO-071-P02',False,None),'Immersion suit not required; insulation classification obligation inactive.'),
('IMO-071-F01','FAIL',b071('IMO-071-F01',True,None),'Required immersion suit has non-insulated controlled type.'),
('IMO-071-F02','FAIL',b071('IMO-071-F02',True,INSULATED,omit='immersionSuitTypeClassification'),'Required type classification missing.'),
('IMO-071-F03','FAIL',b071('IMO-071-F03',omit='immersionSuitRequired'),'Requirement selector missing.'),
('IMO-071-F04','FAIL',b071('IMO-071-F04',True,None),'Controlled type differs from insulatedImmersionSuit.')]:CASES.append(case('IMO-071',cid,exp,g,rat))
# 072
for cid,exp,g,rat in [
('IMO-072-P01','PASS',b072('IMO-072-P01',True,[{'name':'boat1'}]),'Lifeboat in extended darkness has suitable continuous-use searchlight.'),
('IMO-072-P02','PASS',b072('IMO-072-P02',True,[{'name':'boat1'},{'name':'boat2'}]),'Multiple lifeboats each have suitable searchlights.'),
('IMO-072-P03','PASS',b072('IMO-072-P03',False,[{'name':'boat1','omit_searchlight':True}]),'Extended-darkness trigger false.'),
('IMO-072-F01','FAIL',b072('IMO-072-F01',True,[{'name':'boat1','omit_searchlight':True}]),'Lifeboat lacks assigned searchlight.'),
('IMO-072-F02','FAIL',b072('IMO-072-F02',True,[{'name':'boat1','suitable':False}]),'Assigned searchlight unsuitable for continuous use.'),
('IMO-072-F03','FAIL',b072('IMO-072-F03',True,[{'name':'boat1','omit_status':True}]),'Searchlight suitability status missing.'),
('IMO-072-F04','FAIL',b072('IMO-072-F04',True,[{'name':'boat1','wrong_owner':True}]),'Searchlight linked through wrong owner/path.'),
('IMO-072-F05','FAIL',b072('IMO-072-F05',True,[{'name':'boat1'},{'name':'boat2','suitable':False}]),'Universal lifeboat condition fails when one searchlight is unsuitable.')]:CASES.append(case('IMO-072',cid,exp,g,rat))
# 073
for cid,exp,g,rat in [
('IMO-073-P01','PASS',b073('IMO-073-P01',[{'name':'boat1','type':'partial'}]),'Partially enclosed lifeboat is permitted.'),
('IMO-073-P02','PASS',b073('IMO-073-P02',[{'name':'boat1','type':'total'}]),'Totally enclosed lifeboat is permitted.'),
('IMO-073-P03','PASS',b073('IMO-073-P03',[{'name':'boat1','type':'partial'},{'name':'boat2','type':'total'}]),'Multiple lifeboats with allowed types.'),
('IMO-073-P04','PASS',b073('IMO-073-P04',[]),'No represented lifeboat; no lifeboat existence cardinality invented by this clause.'),
('IMO-073-F01','FAIL',b073('IMO-073-F01',[{'name':'boat1','type':'open'}]),'Unapproved open lifeboat type.'),
('IMO-073-F02','FAIL',b073('IMO-073-F02',[{'name':'boat1','omit_type':True}]),'Lifeboat type classification missing.'),
('IMO-073-F03','FAIL',b073('IMO-073-F03',[{'name':'boat1','type':'partial'},{'name':'boat2','type':'open'}]),'Universal type constraint fails for mixed valid/invalid lifeboats.')]:CASES.append(case('IMO-073',cid,exp,g,rat))

MANIFEST='imo_batch_g_manifest.jsonl'; LOCK='imo_batch_g_fixture_lock.json'; VALIDATOR='validate_imo_batch_g.py'
def run():
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                batch_label='IMO Polar Code Behavioral Benchmark Batch G',manifest_name=MANIFEST,lock_name=LOCK,
                validator_name=VALIDATOR,family='IMO')
def main():
 validation_mode=Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv
 if validation_mode:
  ok=validate_batch(MANIFEST,LOCK,ORACLES,True); raise SystemExit(0 if ok else 1)
 run()
if __name__=='__main__':main()
