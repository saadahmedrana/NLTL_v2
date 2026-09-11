
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-k/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-074','IMO-096','IMO-100','IMO-101','IMO-102','IMO-103','IMO-104']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
 'IMO-074':'Part I-A 8.3.3.3.3.1',
 'IMO-096':'Part I-A 10.3.1.4',
 'IMO-100':'Part I-A 11.2',
 'IMO-101':'Part I-A 11.3',
 'IMO-102':'Part I-A 12.3.1',
 'IMO-103':'Part I-A 12.3.2',
 'IMO-104':'Part I-A 12.3.4',
}
APPROVED=NLTL.evidenceStateApproved
REJECTED=NLTL.evidenceStateRejected
ICE_FREE=NLTL.iceFreeIceCondition; OPEN=NLTL.openWaterIceCondition; OTHER=NLTL.otherWatersIceCondition
TANKER=NLTL.tankerPolarTrainingShipType; PASSENGER=NLTL.passengerShipPolarTrainingShipType; OTHER_SHIP=NLTL.otherShipPolarTrainingType
MASTER=NLTL.masterPolarTrainingRole; CHIEF=NLTL.chiefMatePolarTrainingRole; OICNW=NLTL.officerInChargeOfNavigationalWatchPolarTrainingRole
BASIC=NLTL.basicPolarTrainingLevel; ADV=NLTL.advancedPolarTrainingLevel; NA=NLTL.polarTrainingNotApplicable

def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid): return new_graph(BASE,cid)
def obj(g,s,t): return one(g,s,t)
def objs(g,s,t): return list(g.objects(s,NLTL[t]))

# IMO-074
def b074(cid,potential=True,group=True,equiv=None,omit=None):
 g,ex,s=shipg(cid)
 if omit!='abandonmentOntoIceOrLandPotential': add_value(g,s,'abandonmentOntoIceOrLandPotential',potential,ex)
 if omit!='groupSurvivalEquipmentCarried': add_value(g,s,'groupSurvivalEquipmentCarried',group,ex)
 if equiv is not None and omit!='normalLifeSavingEquivalentFunctionalityApprovalStatus': add_value(g,s,'normalLifeSavingEquivalentFunctionalityApprovalStatus',APPROVED if equiv else REJECTED,ex)
 return g
def o074(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 p=lit(g,s,'abandonmentOntoIceOrLandPotential')
 if p is None:return False
 if p is False:return True
 grp=lit(g,s,'groupSurvivalEquipmentCarried')
 eq=obj(g,s,'normalLifeSavingEquivalentFunctionalityApprovalStatus')
 return grp is True or eq==APPROVED

# IMO-096
def b096(cid,voice=True,data=True,omit=None):
 g,ex,s=shipg(cid)
 if omit!='telemedicalAssistanceServiceTwoWayVoiceCapability':add_value(g,s,'telemedicalAssistanceServiceTwoWayVoiceCapability',voice,ex)
 if omit!='telemedicalAssistanceServiceTwoWayDataCapability':add_value(g,s,'telemedicalAssistanceServiceTwoWayDataCapability',data,ex)
 return g
def o096(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 return s is not None and lit(g,s,'telemedicalAssistanceServiceTwoWayVoiceCapability') is True and lit(g,s,'telemedicalAssistanceServiceTwoWayDataCapability') is True

# IMO-100
def b100(cid,plan=True,hazards=('ice',),coverage=(True,),omit_plan=False):
 g,ex,s=shipg(cid)
 if not omit_plan:add_value(g,s,'voyagePlanPresent',plan,ex)
 for h in hazards:add_value(g,s,'identifiedIntendedVoyageHazard',h,ex)
 for c in coverage:add_value(g,s,'voyagePlanHazardCoverage',c,ex)
 return g
def o100(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None or lit(g,s,'voyagePlanPresent') is not True:return False
 hs=list(g.objects(s,NLTL.identifiedIntendedVoyageHazard)); cs=[x.toPython() for x in g.objects(s,NLTL.voyagePlanHazardCoverage)]
 if not hs:return True
 return len(cs)>=1 and all(x is True for x in cs)

# IMO-101
def b101(cid,coverage=True,omit_plan=False,omit_cov=False,wrong_owner=False):
 g,ex,s=shipg(cid); p=typed(ex,g,'routePlan','polarRoutePlan')
 if not omit_plan:add_value(g,s,'hasPolarRoutePlan',p,ex)
 if not omit_cov:
  add_value(g,s if wrong_owner else p,'voyagePlanningTopicCoverage',coverage,ex)
 return g
def o101(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 ps=objs(g,s,'hasPolarRoutePlan')
 return len(ps)==1 and lit(g,ps[0],'voyagePlanningTopicCoverage') is True

# IMO-102 matrix
def matrix_level(ice,stype,role):
 if ice==ICE_FREE:return NA
 if ice==OPEN:
  return BASIC if stype in (TANKER,PASSENGER) else NA
 if ice==OTHER:
  return ADV if role in (MASTER,CHIEF) else BASIC if role==OICNW else None
 return None

def b102(cid,ice,stype,role,required=None,record_level=None,stcw=True,omit=None):
 g,ex,s=shipg(cid); c=typed(ex,g,'crew','crewMember')
 if omit!='iceConditionClassification':add_value(g,s,'iceConditionClassification',ice,ex)
 if omit!='polarTrainingShipTypeClassification':add_value(g,s,'polarTrainingShipTypeClassification',stype,ex)
 add_value(g,s,'hasCrewMemberInventory',c,ex)
 if omit!='polarTrainingCrewRoleClassification':add_value(g,c,'polarTrainingCrewRoleClassification',role,ex)
 expected=matrix_level(ice,stype,role); req=required if required is not None else expected
 if omit!='requiredTrainingLevel':add_value(g,c,'requiredTrainingLevel',req,ex)
 if req!=NA and omit!='record':
  rec=typed(ex,g,'trainingRecord','polarTrainingRecord')
  add_value(g,c,'hasCrewTrainingRecord',rec,ex);add_value(g,c,'hasPolarTrainingRecord',rec,ex)
  if omit!='trainingRecordLevel':add_value(g,rec,'trainingRecordLevel',record_level if record_level is not None else req,ex)
  if omit!='stcwQualificationValid':add_value(g,rec,'stcwQualificationValid',stcw,ex)
 return g

def o102(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 ice=obj(g,s,'iceConditionClassification'); st=obj(g,s,'polarTrainingShipTypeClassification')
 if ice is None or st is None:return False
 crews=objs(g,s,'hasCrewMemberInventory')
 if not crews:return False
 for c in crews:
  role=obj(g,c,'polarTrainingCrewRoleClassification'); req=obj(g,c,'requiredTrainingLevel')
  if role not in (MASTER,CHIEF,OICNW): return False
  exp=matrix_level(ice,st,role)
  if exp is None or req!=exp:return False
  if exp==NA:continue
  rs=objs(g,c,'hasCrewTrainingRecord'); es=objs(g,c,'hasPolarTrainingRecord')
  if len(rs)!=1 or len(es)!=1 or rs[0]!=es[0]:return False
  r=rs[0]
  if obj(g,r,'trainingRecordLevel')!=exp or lit(g,r,'stcwQualificationValid') is not True:return False
 return True

# IMO-103 alternate qualified person
def b103(cid,alt=True,ship_type='passenger ship',ice='other waters',conc=1,permission=True,stcw_conv=True,stcw_code=True,advanced=True,watch=True,rest=True,basic=True,omit=None):
 g,ex,s=shipg(cid); vals={
  'alternateQualifiedPersonUsed':alt,'shipType':ship_type,'iceCondition':ice,
  'administrationPermissionStatus':permission,'stcwConventionRegulationIi2ComplianceStatus':stcw_conv,
  'stcwCodeSectionAIi2ComplianceStatus':stcw_code,'advancedPolarTrainingStatus':advanced,
  'watchCoverageStatus':watch,'restComplianceStatus':rest,'designatedOfficerBasicTrainingStatus':basic}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='iceConcentration':add_value(g,s,'iceConcentration',conc,ex)
 return g

def o103(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 alt=lit(g,s,'alternateQualifiedPersonUsed')
 if alt is None:return False
 if alt is False:return True
 for t in ['administrationPermissionStatus','stcwConventionRegulationIi2ComplianceStatus','stcwCodeSectionAIi2ComplianceStatus','advancedPolarTrainingStatus','watchCoverageStatus','restComplianceStatus']:
  if lit(g,s,t) is not True:return False
 st=lit(g,s,'shipType'); ice=lit(g,s,'iceCondition'); conc=qnum(g,s,'iceConcentration')
 if st is None or ice is None or conc is None:return False
 need_basic=(st in ('passenger ship','tanker') and ice not in ('open waters','bergy waters')) or (st=='cargo ship other than tanker' and conc>2)
 if need_basic and lit(g,s,'designatedOfficerBasicTrainingStatus') is not True:return False
 return True

# IMO-104 familiarization graph
def b104(cid,n=1,status=True,omit=None,mismatch=False):
 g,ex,s=shipg(cid)
 for i in range(n):
  c=typed(ex,g,f'crew{i+1}','crewMember'); d=typed(ex,g,f'duty{i+1}','assignedDuty'); rec=typed(ex,g,f'record{i+1}','familiarizationRecord'); item=typed(ex,g,f'item{i+1}','polarWaterOperationalManualItem')
  add_value(g,s,'hasCrewMemberInventory',c,ex)
  if omit!='hasAssignedDuty':add_value(g,c,'hasAssignedDuty',d,ex)
  if omit!='hasFamiliarizationRecord':add_value(g,c,'hasFamiliarizationRecord',rec,ex)
  if omit!='hasRelevantPolarWaterOperationalManualItem':add_value(g,d,'hasRelevantPolarWaterOperationalManualItem',item,ex)
  rec_item=typed(ex,g,f'otherItem{i+1}','polarWaterOperationalManualItem') if mismatch else item
  if omit!='familiarizationRecordItem':add_value(g,rec,'familiarizationRecordItem',rec_item,ex)
  if omit!='polarWaterOperationalManualFamiliarizationStatus':add_value(g,rec_item,'polarWaterOperationalManualFamiliarizationStatus',status,ex)
 return g

def o104(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 crews=objs(g,s,'hasCrewMemberInventory')
 if not crews:return False
 for c in crews:
  ds=objs(g,c,'hasAssignedDuty'); rs=objs(g,c,'hasFamiliarizationRecord')
  if not ds or len(rs)!=1:return False
  relevant=set()
  for d in ds: relevant.update(objs(g,d,'hasRelevantPolarWaterOperationalManualItem'))
  if not relevant:return False
  covered=set(objs(g,rs[0],'familiarizationRecordItem'))
  if not relevant.issubset(covered):return False
  for item in relevant:
   if lit(g,item,'polarWaterOperationalManualFamiliarizationStatus') is not True:return False
 return True

ORACLES={'IMO-074':o074,'IMO-096':o096,'IMO-100':o100,'IMO-101':o101,'IMO-102':o102,'IMO-103':o103,'IMO-104':o104}
CASES=[]
# 074
for cid,exp,kw,rat in [
 ('IMO-074-K-P01','PASS',{},'Applicable: group survival equipment carried.'),
 ('IMO-074-K-P02','PASS',{'group':False,'equiv':True},'Applicable: approved equivalent functionality route.'),
 ('IMO-074-K-P03','PASS',{'group':True,'equiv':True},'Both permitted routes present.'),
 ('IMO-074-K-F01','FAIL',{'group':False,'equiv':False},'Applicable but neither permitted route is satisfied.'),
 ('IMO-074-K-P04','PASS',{'potential':False,'group':False},'Abandonment onto ice/land not identified; conditional obligation not applicable.'),
 ('IMO-074-K-F02','FAIL',{'omit':'abandonmentOntoIceOrLandPotential'},'Missing applicability fact.')]: CASES.append(case('IMO-074',cid,exp,b074(cid,**kw),rat))
# 096
for cid,exp,kw,rat in [
 ('IMO-096-K-P01','PASS',{},'TMAS supports both two-way voice and two-way data.'),
 ('IMO-096-K-F01','FAIL',{'voice':False},'Two-way voice capability absent.'),
 ('IMO-096-K-F02','FAIL',{'data':False},'Two-way data capability absent.'),
 ('IMO-096-K-F03','FAIL',{'omit':'telemedicalAssistanceServiceTwoWayVoiceCapability'},'Voice capability value missing.'),
 ('IMO-096-K-F04','FAIL',{'omit':'telemedicalAssistanceServiceTwoWayDataCapability'},'Data capability value missing.')]: CASES.append(case('IMO-096',cid,exp,b096(cid,**kw),rat))
# 100
for cid,exp,kw,rat in [
 ('IMO-100-K-P01','PASS',{},'Voyage plan present and one identified hazard covered.'),
 ('IMO-100-K-P02','PASS',{'hazards':('ice','remoteness'),'coverage':(True,True)},'Multiple intended-voyage hazards all covered.'),
 ('IMO-100-K-P03','PASS',{'hazards':(), 'coverage':()},'Voyage plan present with no separately represented hazard nodes.'),
 ('IMO-100-K-F01','FAIL',{'hazards':('ice','remoteness'),'coverage':(True,False)},'One represented hazard is not covered.'),
 ('IMO-100-K-F02','FAIL',{'plan':False},'Voyage plan absent.'),
 ('IMO-100-K-F03','FAIL',{'hazards':('ice','remoteness'),'coverage':()},'Coverage evidence missing for represented hazards.'),
 ('IMO-100-K-F04','FAIL',{'omit_plan':True},'Voyage-plan presence value missing.')]: CASES.append(case('IMO-100',cid,exp,b100(cid,**kw),rat))
# 101
for cid,exp,kw,rat in [
 ('IMO-101-K-P01','PASS',{},'Ship links to a polar route plan with complete topic coverage.'),
 ('IMO-101-K-F01','FAIL',{'coverage':False},'Route-plan topic coverage is false.'),
 ('IMO-101-K-F02','FAIL',{'omit_plan':True},'Required ship-to-route-plan path missing.'),
 ('IMO-101-K-F03','FAIL',{'omit_cov':True},'Route plan exists but coverage value is missing.'),
 ('IMO-101-K-F04','FAIL',{'wrong_owner':True},'Coverage is asserted on the ship instead of the linked route plan.')]: CASES.append(case('IMO-101',cid,exp,b101(cid,**kw),rat))
# 102 exhaustive valid matrix: 27 cells
for ice in (ICE_FREE,OPEN,OTHER):
 for st in (TANKER,PASSENGER,OTHER_SHIP):
  for role in (MASTER,CHIEF,OICNW):
   tag=f'{len([x for x in CASES if x["requirement_id"]=="IMO-102"])+1:02d}'
   CASES.append(case('IMO-102',f'IMO-102-K-P{tag}','PASS',b102(f'IMO-102-K-P{tag}',ice,st,role),'Valid controlled 12.3.1 matrix cell with matching required level and STCW record when required.'))
# targeted 102 failures
for cid,kw,rat in [
 ('IMO-102-K-F01',{'ice':OTHER,'stype':TANKER,'role':MASTER,'required':BASIC},'Wrong required level: master in other waters requires Advanced.'),
 ('IMO-102-K-F02',{'ice':OPEN,'stype':PASSENGER,'role':OICNW,'record_level':ADV},'Training record level does not match required Basic level.'),
 ('IMO-102-K-F03',{'ice':OTHER,'stype':OTHER_SHIP,'role':CHIEF,'stcw':False},'Matching Advanced record exists but STCW qualification is invalid.'),
 ('IMO-102-K-F04',{'ice':OTHER,'stype':TANKER,'role':OICNW,'omit':'record'},'Required training record evidence missing.'),
 ('IMO-102-K-F05',{'ice':ICE_FREE,'stype':TANKER,'role':MASTER,'required':BASIC},'Ice-free matrix cell must be Not Applicable.'),
 ('IMO-102-K-F06',{'ice':OPEN,'stype':TANKER,'role':MASTER,'omit':'polarTrainingCrewRoleClassification'},'Crew-role selector missing.'),
 ('IMO-102-K-F07',{'ice':OTHER,'stype':PASSENGER,'role':MASTER,'omit':'requiredTrainingLevel'},'Required training-level selector/result missing.')]: CASES.append(case('IMO-102',cid,'FAIL',b102(cid,**kw),rat))
# 103
for cid,exp,kw,rat in [
 ('IMO-103-K-P01','PASS',{'alt':False},'Alternate qualified person not used; 12.3.2 conditional route not applicable.'),
 ('IMO-103-K-P02','PASS',{'ship_type':'passenger ship','ice':'open waters','basic':False},'Passenger ship in open waters: alternate-person core conditions satisfied; extra basic condition not triggered.'),
 ('IMO-103-K-P03','PASS',{'ship_type':'passenger ship','ice':'other waters','basic':True},'Passenger ship outside open/bergy waters with designated-officer basic training.'),
 ('IMO-103-K-F01','FAIL',{'ship_type':'passenger ship','ice':'other waters','basic':False},'Passenger ship outside open/bergy waters lacks designated-officer basic training.'),
 ('IMO-103-K-P04','PASS',{'ship_type':'cargo ship other than tanker','ice':'other waters','conc':2,'basic':False},'Cargo ship exactly at 2/10 does not trigger the greater-than-2/10 condition.'),
 ('IMO-103-K-P05','PASS',{'ship_type':'cargo ship other than tanker','ice':'other waters','conc':3,'basic':True},'Cargo ship above 2/10 with required designated-officer basic training.'),
 ('IMO-103-K-F02','FAIL',{'ship_type':'cargo ship other than tanker','ice':'other waters','conc':3,'basic':False},'Cargo ship above 2/10 lacks required basic training.'),
 ('IMO-103-K-F03','FAIL',{'permission':False},'Administration permission condition fails.'),
 ('IMO-103-K-F04','FAIL',{'advanced':False},'Alternate person lacks required advanced polar training.'),
 ('IMO-103-K-F05','FAIL',{'watch':False},'Insufficient trained-person watch coverage.'),
 ('IMO-103-K-F06','FAIL',{'rest':False},'Administration minimum-hours-of-rest condition fails.')]: CASES.append(case('IMO-103',cid,exp,b103(cid,**kw),rat))
# 104
for cid,exp,kw,rat in [
 ('IMO-104-K-P01','PASS',{},'One crew member has duty-linked PWOM item and completed familiarization record.'),
 ('IMO-104-K-P02','PASS',{'n':2},'Every represented crew member has completed familiarization for relevant assigned-duty items.'),
 ('IMO-104-K-F01','FAIL',{'status':False},'Familiarization status is not completed.'),
 ('IMO-104-K-F02','FAIL',{'omit':'hasFamiliarizationRecord'},'Crew familiarization record missing.'),
 ('IMO-104-K-F03','FAIL',{'omit':'hasAssignedDuty'},'Assigned-duty relation missing.'),
 ('IMO-104-K-F04','FAIL',{'omit':'familiarizationRecordItem'},'Familiarization record does not identify the relevant PWOM item.'),
 ('IMO-104-K-F05','FAIL',{'mismatch':True},'Record covers a different PWOM item than the one relevant to the assigned duty.')]: CASES.append(case('IMO-104',cid,exp,b104(cid,**kw),rat))

MANIFEST='imo_batch_k_manifest.jsonl';LOCK='imo_batch_k_fixture_lock.json';VALIDATOR='validate_imo_batch_k.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:
  raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch K',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
