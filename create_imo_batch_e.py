
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


BASE='https://w3id.org/nltl/benchmark/imo-batch-e/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-040','IMO-041','IMO-043','IMO-045','IMO-047','IMO-048','IMO-049']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
    'IMO-040':'Part I-A 5.3.1','IMO-041':'Part I-A 5.3.2.1','IMO-043':'Part I-A 6.3.1.1',
    'IMO-045':'Part I-A 6.3.1.3','IMO-047':'Part I-A 6.3.2.2','IMO-048':'Part I-A 6.3.2.3',
    'IMO-049':'Part I-A 6.3.3.1-.3'
}
APPROVED=NLTL.evidenceStateApproved; REJECTED=NLTL.evidenceStateRejected
CAT_A=NLTL.polarShipCategoryA; CAT_B=NLTL.polarShipCategoryB; CAT_C=NLTL.polarShipCategoryC
ALLOWED_AUTH={'Administration','recognized organization accepted by the Administration'}
AB_STANDARDS={'standard acceptable to the Organization','another standard offering an equivalent level of safety'}
C_STANDARD='acceptable standard adequate for operating ice type and concentration'
HAZARDS=[NLTL.iceAccretionHazard,NLTL.snowAccumulationHazard,NLTL.seawaterIceIngestionHazard,
         NLTL.liquidFreezingOrViscosityIncreaseHazard,NLTL.seawaterIntakeTemperatureHazard,NLTL.snowIngestionHazard]
APPLICABLE_COMPONENT_TYPES={'propeller blade','propulsion line','steering equipment','other appendage'}

def ship_of(g): return next(g.subjects(RDF.type,NLTL.ship),None)
def obj(g,s,term): return one(g,s,term)
def case(req,cid,expected,graph,rationale): return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}

# IMO-040 ------------------------------------------------------
def _hatch(g,ex,s,name,with_means=True,wrong_owner=False):
    h=typed(ex,g,name,'relevantHatchOrDoorItem'); add_value(g,s,'hasRelevantHatchOrDoor',h,ex)
    add_value(g,h,'relevantHatchOrDoor',name,ex)
    if with_means:
        m=typed(ex,g,name+'Means','iceSnowRemovalOrPreventionMeans')
        add_value(g,s if wrong_owner else h,'hasIceOrSnowRemovalOrPreventionMeans',m,ex)
    return h

def b040(cid,likely=True,hatches=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'iceAccretionLikely',likely,ex)
    for kw in (hatches or []): _hatch(g,ex,s,**kw)
    return g

def o040(g):
    s=ship_of(g); likely=lit(g,s,'iceAccretionLikely')
    if likely is False: return True
    if likely is not True: return False
    for h in g.objects(s,NLTL.hasRelevantHatchOrDoor):
        if len(list(g.objects(h,NLTL.hasIceOrSnowRemovalOrPreventionMeans)))<1: return False
    return True

# IMO-041 ------------------------------------------------------
def b041(cid,act='hydraulic',control=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='openingActuationType': add_value(g,s,'openingActuationType',act,ex)
    if omit!='hydraulicFluidFreezingOrViscosityControlPresent' and act=='hydraulic': add_value(g,s,'hydraulicFluidFreezingOrViscosityControlPresent',control,ex)
    return g

def o041(g):
    s=ship_of(g); act=lit(g,s,'openingActuationType')
    if not isinstance(act,str) or not act.strip(): return False
    if act!='hydraulic': return True
    return lit(g,s,'hydraulicFluidFreezingOrViscosityControlPresent') is True

# IMO-043 ------------------------------------------------------
def _installation(g,ex,s,name,hazards=None,evidence=True,coverage=True,associated=True,wrong_evidence_path=False):
    inst=typed(ex,g,name,'machineryInstallationItem'); add_value(g,s,'hasMachineryInstallation',inst,ex); add_value(g,inst,'machineryInstallation',name,ex)
    if associated:
        eq=typed(ex,g,name+'Equipment','associatedEquipmentItem'); add_value(g,inst,'hasAssociatedEquipment',eq,ex)
    for hz in (HAZARDS if hazards is None else hazards): add_value(g,inst,'hasApplicableHazard',hz,ex)
    if evidence:
        ev=typed(ex,g,name+'Evidence','evidenceArtifact'); add_value(g,ev,'hazardProtectionCoverage',coverage,ex)
        add_value(g,s if wrong_evidence_path else inst,'hasHazardProtectionEvidence',ev,ex)
    return inst

def b043(cid,installs=None):
    g,ex,s=new_graph(BASE,cid)
    for kw in (installs or []): _installation(g,ex,s,**kw)
    return g

def o043(g):
    s=ship_of(g); installs=list(g.objects(s,NLTL.hasMachineryInstallation))
    if not installs: return True
    for inst in installs:
        if not isinstance(lit(g,inst,'machineryInstallation'),str): return False
        if len(list(g.objects(inst,NLTL.hasAssociatedEquipment)))<1: return False
        hz=set(g.objects(inst,NLTL.hasApplicableHazard))
        if not set(HAZARDS).issubset(hz): return False
        evs=list(g.objects(inst,NLTL.hasHazardProtectionEvidence))
        if not evs or not any(lit(g,e,'hazardProtectionCoverage') is True for e in evs): return False
    return True

# IMO-045 ------------------------------------------------------
def b045(cid,supply=True,ice=False,alt=None,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='machinerySeawaterSupply': add_value(g,s,'machinerySeawaterSupply',supply,ex)
    if supply:
        if omit!='iceIngestionPreventionPresent': add_value(g,s,'iceIngestionPreventionPresent',ice,ex)
        if alt is not None and omit!='alternateFunctionalityArrangementApprovalStatus': add_value(g,s,'alternateFunctionalityArrangementApprovalStatus',alt,ex)
    return g

def o045(g):
    s=ship_of(g); supply=lit(g,s,'machinerySeawaterSupply')
    if supply is False: return True
    if supply is not True: return False
    return lit(g,s,'iceIngestionPreventionPresent') is True or obj(g,s,'alternateFunctionalityArrangementApprovalStatus')==APPROVED

# IMO-047 ------------------------------------------------------
def _engine(g,ex,s,name,temp=0,min_t=-20,max_t=45,control=True,omit=None,wrong_unit=None):
    e=typed(ex,g,name,'essentialEngine'); add_value(g,s,'hasEssentialEngine',e,ex)
    vals={'combustionAirTemperatureControlPresent':control,'combustionAirTemperature':temp,
          'manufacturerMinAirTemperature':min_t,'manufacturerMaxAirTemperature':max_t}
    for t,v in vals.items():
        if omit==t: continue
        add_value(g,e,t,v,ex,name=f'{name}_{t}Value',unit_override=(UNIT.K if wrong_unit==t else None))
    return e

def b047(cid,engines=None):
    g,ex,s=new_graph(BASE,cid)
    for kw in (engines or []): _engine(g,ex,s,**kw)
    return g

def o047(g):
    s=ship_of(g)
    for e in g.objects(s,NLTL.hasEssentialEngine):
        if lit(g,e,'combustionAirTemperatureControlPresent') is not True: return False
        t=qnum(g,e,'combustionAirTemperature'); lo=qnum(g,e,'manufacturerMinAirTemperature'); hi=qnum(g,e,'manufacturerMaxAirTemperature')
        if None in (t,lo,hi) or lo>hi or t<lo-1e-9 or t>hi+1e-9: return False
    return True

# IMO-048 ------------------------------------------------------
def b048(cid,authority='Administration',standard='standard acceptable to the Organization',status=APPROVED,pst=-30,omit=None):
    g,ex,s=new_graph(BASE,cid)
    vals={'exposedMachineryOrFoundationMaterial':'exposed machinery/foundation material','materialApprovalStatus':status,
          'approvingAuthority':authority,'approvalStandard':standard,'polarServiceTemperature':pst}
    for t,v in vals.items():
        if omit==t: continue
        add_value(g,s,t,v,ex)
    return g

def o048(g):
    s=ship_of(g)
    return isinstance(lit(g,s,'exposedMachineryOrFoundationMaterial'),str) and obj(g,s,'materialApprovalStatus')==APPROVED and lit(g,s,'approvingAuthority') in ALLOWED_AUTH and lit(g,s,'approvalStandard') in AB_STANDARDS and qnum(g,s,'polarServiceTemperature') is not None

# IMO-049 ------------------------------------------------------
def _component(g,ex,s,name,ctype='propeller blade',authority='Administration',standard='standard acceptable to the Organization',status=APPROVED,ice_type='medium first-year ice',ice_conc=0.7,omit_record=False,omit=None):
    c=typed(ex,g,name,'machineryComponent'); add_raw_object(g,s,'hasComponent',c); add_value(g,c,'machineryComponentType',ctype,ex)
    if omit_record: return c
    rec=typed(ex,g,name+'Approval','approvalRecord'); add_value(g,c,'hasApprovalRecord',rec,ex)
    vals={'approvingAuthority':authority,'approvalStandard':standard,'scantlingApprovalStatus':status}
    cat=obj(g,s,'shipCategory'); strengthened=lit(g,s,'shipIceStrengthened')
    if cat==CAT_C and strengthened is True: vals.update({'operatingIceType':ice_type,'operatingIceConcentration':ice_conc})
    for t,v in vals.items():
        if omit==t: continue
        add_value(g,rec,t,v,ex)
    return c

def b049(cid,cat=CAT_A,strengthened=True,components=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'shipCategory',cat,ex); add_value(g,s,'shipIceStrengthened',strengthened,ex)
    for kw in (components or []): _component(g,ex,s,**kw)
    return g

def o049(g):
    s=ship_of(g); cat=obj(g,s,'shipCategory'); strengthened=lit(g,s,'shipIceStrengthened')
    if cat not in (CAT_A,CAT_B,CAT_C) or strengthened not in (True,False): return False
    if strengthened is False: return True
    comps=[]
    for c in g.objects(s,NLTL.hasComponent):
        ctype=lit(g,c,'machineryComponentType')
        if ctype in APPLICABLE_COMPONENT_TYPES: comps.append(c)
    if not comps: return True
    for c in comps:
        recs=list(g.objects(c,NLTL.hasApprovalRecord))
        if len(recs)!=1: return False
        rec=recs[0]
        if obj(g,rec,'scantlingApprovalStatus')!=APPROVED or lit(g,rec,'approvingAuthority') not in ALLOWED_AUTH: return False
        std=lit(g,rec,'approvalStandard')
        if cat in (CAT_A,CAT_B):
            if std not in AB_STANDARDS: return False
        elif cat==CAT_C:
            if std!=C_STANDARD or not isinstance(lit(g,rec,'operatingIceType'),str) or qnum(g,rec,'operatingIceConcentration') is None: return False
    return True

ORACLES={'IMO-040':o040,'IMO-041':o041,'IMO-043':o043,'IMO-045':o045,'IMO-047':o047,'IMO-048':o048,'IMO-049':o049}
CASES=[]
# 040
for cid,exp,g,rat in [
('IMO-040-P01','PASS',b040('IMO-040-P01',hatches=[{'name':'hatch1'}]),'Applicable hatch has linked ice/snow removal or prevention means.'),
('IMO-040-P02','PASS',b040('IMO-040-P02',hatches=[{'name':'hatch1'},{'name':'door1'}]),'Multiple relevant closures all protected.'),
('IMO-040-P03','PASS',b040('IMO-040-P03',likely=False,hatches=[{'name':'hatch1','with_means':False}]),'No ice-accretion trigger; closure protection obligation inactive.'),
('IMO-040-P04','PASS',b040('IMO-040-P04',likely=True,hatches=[]),'No represented relevant closure: universal condition is vacuously satisfied.'),
('IMO-040-F01','FAIL',b040('IMO-040-F01',hatches=[{'name':'hatch1','with_means':False}]),'Applicable hatch lacks protection means.'),
('IMO-040-F02','FAIL',b040('IMO-040-F02',hatches=[{'name':'hatch1'},{'name':'door1','with_means':False}]),'One of multiple relevant closures is unprotected.'),
('IMO-040-F03','FAIL',b040('IMO-040-F03',hatches=[{'name':'hatch1','wrong_owner':True}]),'Protection means exists but is attached to wrong owner/path.')]: CASES.append(case('IMO-040',cid,exp,g,rat))
# 041
for cid,exp,g,rat in [
('IMO-041-P01','PASS',b041('IMO-041-P01'),'Hydraulic opening has freezing/viscosity control.'),
('IMO-041-P02','PASS',b041('IMO-041-P02',act='manual'),'Non-hydraulic opening is outside the conditional trigger.'),
('IMO-041-P03','PASS',b041('IMO-041-P03',act='electric'),'Electric actuation does not activate hydraulic-fluid requirement.'),
('IMO-041-F01','FAIL',b041('IMO-041-F01',control=False),'Hydraulic opening lacks required fluid control.'),
('IMO-041-F02','FAIL',b041('IMO-041-F02',omit='hydraulicFluidFreezingOrViscosityControlPresent'),'Hydraulic control evidence value missing.'),
('IMO-041-F03','FAIL',b041('IMO-041-F03',omit='openingActuationType'),'Actuation selector missing.')]: CASES.append(case('IMO-041',cid,exp,g,rat))
# 043
five=HAZARDS[:-1]
for cid,exp,g,rat in [
('IMO-043-P01','PASS',b043('IMO-043-P01',installs=[{'name':'mainMachinery'}]),'One machinery installation has complete six-hazard protection coverage and evidence.'),
('IMO-043-P02','PASS',b043('IMO-043-P02',installs=[{'name':'mainMachinery'},{'name':'auxMachinery'}]),'Multiple installations independently satisfy complete hazard coverage.'),
('IMO-043-P03','PASS',b043('IMO-043-P03',installs=[]),'No represented machinery installation; no unsupported existence cardinality is invented.'),
('IMO-043-F01','FAIL',b043('IMO-043-F01',installs=[{'name':'mainMachinery','hazards':five}]),'One required environmental hazard is missing.'),
('IMO-043-F02','FAIL',b043('IMO-043-F02',installs=[{'name':'mainMachinery','evidence':False}]),'Hazard protection evidence missing.'),
('IMO-043-F03','FAIL',b043('IMO-043-F03',installs=[{'name':'mainMachinery','coverage':False}]),'Hazard protection evidence does not establish coverage.'),
('IMO-043-F04','FAIL',b043('IMO-043-F04',installs=[{'name':'mainMachinery','associated':False}]),'Associated equipment path omitted from represented installation.'),
('IMO-043-F05','FAIL',b043('IMO-043-F05',installs=[{'name':'mainMachinery','wrong_evidence_path':True}]),'Evidence attached to ship instead of machinery installation.'),
('IMO-043-F06','FAIL',b043('IMO-043-F06',installs=[{'name':'mainMachinery'},{'name':'auxMachinery','hazards':five}]),'Universal coverage fails when one represented installation is incomplete.')]: CASES.append(case('IMO-043',cid,exp,g,rat))
# 045
for cid,exp,g,rat in [
('IMO-045-P01','PASS',b045('IMO-045-P01',supply=True,ice=True),'Ice-ingestion-prevention route.'),
('IMO-045-P02','PASS',b045('IMO-045-P02',supply=True,ice=False,alt=APPROVED),'Approved alternate-functionality route.'),
('IMO-045-P03','PASS',b045('IMO-045-P03',supply=True,ice=True,alt=APPROVED),'Both valid routes represented.'),
('IMO-045-P04','PASS',b045('IMO-045-P04',supply=False),'No machinery seawater supply represented as applicable.'),
('IMO-045-F01','FAIL',b045('IMO-045-F01',supply=True,ice=False),'Neither allowed functionality route present.'),
('IMO-045-F02','FAIL',b045('IMO-045-F02',supply=True,ice=False,alt=REJECTED),'Alternate arrangement is not approved.'),
('IMO-045-F03','FAIL',b045('IMO-045-F03',supply=True,ice=False,omit='iceIngestionPreventionPresent'),'Required route state is absent and no approved alternate exists.'),
('IMO-045-F04','FAIL',b045('IMO-045-F04',omit='machinerySeawaterSupply'),'Applicability/supply state missing.')]: CASES.append(case('IMO-045',cid,exp,g,rat))
# 047
for cid,exp,g,rat in [
('IMO-047-P01','PASS',b047('IMO-047-P01',engines=[{'name':'engine1','temp':0,'min_t':-20,'max_t':45}]),'Controlled combustion-air temperature within manufacturer criteria.'),
('IMO-047-P02','PASS',b047('IMO-047-P02',engines=[{'name':'engine1','temp':-20,'min_t':-20,'max_t':45}]),'Lower manufacturer limit is inclusive.'),
('IMO-047-P03','PASS',b047('IMO-047-P03',engines=[{'name':'engine1','temp':45,'min_t':-20,'max_t':45}]),'Upper manufacturer limit is inclusive.'),
('IMO-047-P04','PASS',b047('IMO-047-P04',engines=[{'name':'engine1'},{'name':'engine2','temp':10,'min_t':-5,'max_t':30}]),'Multiple essential engines all compliant.'),
('IMO-047-P05','PASS',b047('IMO-047-P05',engines=[]),'No represented essential internal-combustion engine: universal condition vacuous.'),
('IMO-047-F01','FAIL',b047('IMO-047-F01',engines=[{'name':'engine1','control':False}]),'Combustion-air temperature control absent.'),
('IMO-047-F02','FAIL',b047('IMO-047-F02',engines=[{'name':'engine1','temp':-20.1,'min_t':-20,'max_t':45}]),'Air temperature below manufacturer minimum.'),
('IMO-047-F03','FAIL',b047('IMO-047-F03',engines=[{'name':'engine1','temp':45.1,'min_t':-20,'max_t':45}]),'Air temperature above manufacturer maximum.'),
('IMO-047-F04','FAIL',b047('IMO-047-F04',engines=[{'name':'engine1','omit':'manufacturerMinAirTemperature'}]),'Manufacturer criterion boundary missing.'),
('IMO-047-F05','FAIL',b047('IMO-047-F05',engines=[{'name':'engine1','wrong_unit':'combustionAirTemperature'}]),'Combustion-air temperature uses wrong unit.'),
('IMO-047-F06','FAIL',b047('IMO-047-F06',engines=[{'name':'engine1'},{'name':'engine2','temp':50,'max_t':45}]),'One of multiple essential engines violates manufacturer criteria.')]: CASES.append(case('IMO-047',cid,exp,g,rat))
# 048
for cid,exp,g,rat in [
('IMO-048-P01','PASS',b048('IMO-048-P01'),'Administration approval with Organization-acceptable standard.'),
('IMO-048-P02','PASS',b048('IMO-048-P02',authority='recognized organization accepted by the Administration',standard='another standard offering an equivalent level of safety'),'Recognized organization and equivalent-safety standard route.'),
('IMO-048-F01','FAIL',b048('IMO-048-F01',authority='manufacturer'),'Unauthorized authority.'),
('IMO-048-F02','FAIL',b048('IMO-048-F02',standard='yard procedure'),'Unapproved material standard.'),
('IMO-048-F03','FAIL',b048('IMO-048-F03',status=REJECTED),'Material approval status rejected.'),
('IMO-048-F04','FAIL',b048('IMO-048-F04',omit='polarServiceTemperature'),'PST basis missing.'),
('IMO-048-F05','FAIL',b048('IMO-048-F05',omit='exposedMachineryOrFoundationMaterial'),'Applicable exposed machinery/foundation material missing.')]: CASES.append(case('IMO-048',cid,exp,g,rat))
# 049
for cid,exp,g,rat in [
('IMO-049-P01','PASS',b049('IMO-049-P01',cat=CAT_A,components=[{'name':'propeller','ctype':'propeller blade'}]),'Category A propeller blade approval.'),
('IMO-049-P02','PASS',b049('IMO-049-P02',cat=CAT_B,components=[{'name':'steering','ctype':'steering equipment','authority':'recognized organization accepted by the Administration','standard':'another standard offering an equivalent level of safety'}]),'Category B recognized-organization/equivalent-safety route.'),
('IMO-049-P03','PASS',b049('IMO-049-P03',cat=CAT_C,strengthened=True,components=[{'name':'appendage','ctype':'other appendage','standard':C_STANDARD}]),'Ice-strengthened Category C with adequate ice-specific approval context.'),
('IMO-049-P04','PASS',b049('IMO-049-P04',cat=CAT_C,strengthened=False,components=[]),'Ship not ice strengthened: chapter-3 machinery scantling branch inactive.'),
('IMO-049-P05','PASS',b049('IMO-049-P05',cat=CAT_A,components=[{'name':'hotel','ctype':'hotel service equipment','omit_record':True}]),'Non-target machinery component type does not activate listed scantling approval branch.'),
('IMO-049-P06','PASS',b049('IMO-049-P06',cat=CAT_A,components=[{'name':'propeller','ctype':'propeller blade'},{'name':'shaft','ctype':'propulsion line'}]),'Multiple applicable components independently approved.'),
('IMO-049-F01','FAIL',b049('IMO-049-F01',cat=CAT_A,components=[{'name':'propeller','ctype':'propeller blade','omit_record':True}]),'Applicable machinery component approval record missing.'),
('IMO-049-F02','FAIL',b049('IMO-049-F02',cat=CAT_B,components=[{'name':'steering','ctype':'steering equipment','authority':'manufacturer'}]),'Unauthorized approving authority.'),
('IMO-049-F03','FAIL',b049('IMO-049-F03',cat=CAT_C,strengthened=True,components=[{'name':'appendage','ctype':'other appendage','standard':'another standard offering an equivalent level of safety'}]),'Category C branch incorrectly uses A/B equivalent-safety alternative.'),
('IMO-049-F04','FAIL',b049('IMO-049-F04',cat=CAT_C,strengthened=True,components=[{'name':'appendage','ctype':'other appendage','standard':C_STANDARD,'omit':'operatingIceType'}]),'Category C operating-ice-type context missing.'),
('IMO-049-F05','FAIL',b049('IMO-049-F05',cat=CAT_A,components=[{'name':'propeller','ctype':'propeller blade','status':REJECTED}]),'Scantling approval state is not approved.'),
('IMO-049-F06','FAIL',b049('IMO-049-F06',cat=CAT_A,components=[{'name':'propeller','ctype':'propeller blade'},{'name':'shaft','ctype':'propulsion line','authority':'manufacturer'}]),'Universal approval fails when one applicable component is invalid.')]: CASES.append(case('IMO-049',cid,exp,g,rat))

MANIFEST='imo_batch_e_manifest.jsonl'; LOCK='imo_batch_e_fixture_lock.json'; VALIDATOR='validate_imo_batch_e.py'
def run():
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                   batch_label='IMO Polar Code Behavioral Benchmark Batch E',manifest_name=MANIFEST,lock_name=LOCK,
                   validator_name=VALIDATOR,family='IMO')
def main():
    validation_mode=Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv
    if validation_mode:
        ok=validate_batch(MANIFEST,LOCK,ORACLES,True); raise SystemExit(0 if ok else 1)
    run()
if __name__=='__main__': main()
