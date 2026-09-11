
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


BASE='https://w3id.org/nltl/benchmark/imo-batch-f/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-050','IMO-051','IMO-052','IMO-053','IMO-055','IMO-057','IMO-058','IMO-059','IMO-060']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
    'IMO-050':'Part I-A 7.2.1.1','IMO-051':'Part I-A 7.2.1.2','IMO-052':'Part I-A 7.2.1.4',
    'IMO-053':'Part I-A 7.2.1.5','IMO-055':'Part I-A 7.3.1.1','IMO-057':'Part I-A 7.3.2.1',
    'IMO-058':'Part I-A 7.3.2.2','IMO-059':'Part I-A 7.3.2.3','IMO-060':'Part I-A 7.3.2.4'
}
APPROVED=NLTL.evidenceStateApproved
REJECTED=NLTL.evidenceStateRejected
WARM=NLTL.warmStorageLocation
PUMP_TYPES={NLTL.firePump,NLTL.emergencyFirePump,NLTL.waterMistPump,NLTL.waterSprayPump}

def case(req,cid,expected,graph,rationale):
    return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}

def direct_bool(g,ship,term,val,ex): add_value(g,ship,term,val,ex)

def b050(cid, exposed=True, protected=True, omit=None):
    g,ex,ship=new_graph(BASE,cid)
    if omit!='fireSafetyComponentExposed': add_value(g,ship,'fireSafetyComponentExposed',exposed,ex)
    if omit!='iceAndSnowProtectionPresent': add_value(g,ship,'iceAndSnowProtectionPresent',protected,ex)
    return g

def o050(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    exp=lit(g,ship,'fireSafetyComponentExposed') if ship else None
    if not isinstance(exp,bool): return False
    if not exp: return True
    return lit(g,ship,'iceAndSnowProtectionPresent') is True

def b051(cid, items=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in items or []:
        item=typed(ex,g,spec.get('name','control'), 'localControlItem')
        if not spec.get('wrong_owner'):
            add_value(g,ship,'hasLocalControlItem',item,ex)
        else:
            stray=typed(ex,g,'strayOwner','ship'); add_value(g,stray,'hasLocalControlItem',item,ex)
        if not spec.get('omit_protection'): add_value(g,item,'freezingSnowIceProtectionPresent',spec.get('protection',True),ex)
        if not spec.get('omit_access'): add_value(g,item,'continuouslyAccessible',spec.get('accessible',True),ex)
    return g

def o051(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None: return False
    for item in g.objects(ship,NLTL.hasLocalControlItem):
        if lit(g,item,'freezingSnowIceProtectionPresent') is not True: return False
        if lit(g,item,'continuouslyAccessible') is not True: return False
    return True

def b052(cid, items=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in items or []:
        item=typed(ex,g,spec.get('name','access'),'requiredAccessItem')
        add_value(g,ship,'hasRequiredAccessItem',item,ex)
        if not spec.get('with_means',True): continue
        means=typed(ex,g,spec.get('means_name',spec.get('name','access')+'Means'),'iceSnowRemovalOrPreventionMeans')
        owner=ship if spec.get('wrong_owner') else item
        add_value(g,owner,'hasIceOrSnowRemovalOrPreventionMeans',means,ex)
    return g

def o052(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None: return False
    for item in g.objects(ship,NLTL.hasRequiredAccessItem):
        if not list(g.objects(item,NLTL.hasIceOrSnowRemovalOrPreventionMeans)): return False
    return True

def b053(cid, media=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in media or []:
        item=typed(ex,g,spec.get('name','medium'),'extinguishingMediumItem')
        add_value(g,ship,'hasExtinguishingMedium',item,ex)
        if not spec.get('omit_status'): add_value(g,item,'intendedOperationCompatibilityStatus',spec.get('approved',True),ex)
    return g

def o053(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None: return False
    for item in g.objects(ship,NLTL.hasExtinguishingMedium):
        if lit(g,item,'intendedOperationCompatibilityStatus') is not True: return False
    return True

def b055(cid, exposed=True, vtype='isolating', protected=True, accessible=True, omit=None):
    g,ex,ship=new_graph(BASE,cid)
    vals={'valveExposed':exposed,'valveType':vtype,'iceAccretionProtectionPresent':protected,'continuouslyAccessible':accessible}
    for t,v in vals.items():
        if omit!=t: add_value(g,ship,t,v,ex)
    return g

def o055(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None: return False
    exp=lit(g,ship,'valveExposed'); vt=lit(g,ship,'valveType')
    if not isinstance(exp,bool) or vt is None: return False
    if not exp or str(vt).lower() not in {'isolating','pressure','vacuum'}: return True
    return lit(g,ship,'iceAccretionProtectionPresent') is True and lit(g,ship,'continuouslyAccessible') is True

def b057(cid, pumps=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in pumps or []:
        p=typed(ex,g,spec.get('name','pump'),spec.get('cls','firePump'))
        if not spec.get('wrong_ship_path'):
            add_raw_object(g,ship,'hasComponent',p)
        else:
            stray=typed(ex,g,'strayShip','ship'); add_raw_object(g,stray,'hasComponent',p)
        if spec.get('omit_compartment'): continue
        comp=typed(ex,g,spec.get('name','pump')+'Compartment','compartment')
        owner=ship if spec.get('wrong_compartment_path') else p
        add_value(g,owner,'hasContainingCompartment',comp,ex)
        if not spec.get('omit_temp'):
            add_value(g,comp,'maintainedTemperature',spec.get('temp',5),ex,name=spec.get('name','pump')+'MaintainedTemperatureValue',unit_override=spec.get('unit'))
    return g

def o057(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None:return False
    for p in g.objects(ship,NLTL.hasComponent):
        types=set(g.objects(p,RDF.type))
        if not (types & PUMP_TYPES): continue
        comps=list(g.objects(p,NLTL.hasContainingCompartment))
        if not comps: return False
        good=False
        for c in comps:
            t=qnum(g,c,'maintainedTemperature')
            if t is not None and t>0: good=True
        if not good: return False
    return True

def b058(cid, sections=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in sections or []:
        s=typed(ex,g,spec.get('name','section'),'exposedFireMainSectionItem')
        add_value(g,ship,'hasExposedFireMainSection',s,ex)
        if not spec.get('omit_isolation'): add_value(g,s,'isolationCapability',spec.get('isolation',True),ex)
        if not spec.get('omit_drainage'): add_value(g,s,'drainageMeansPresent',spec.get('drainage',True),ex)
    return g

def o058(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None:return False
    for s in g.objects(ship,NLTL.hasExposedFireMainSection):
        if lit(g,s,'isolationCapability') is not True or lit(g,s,'drainageMeansPresent') is not True:return False
    return True

def b059(cid, outfits=None):
    g,ex,ship=new_graph(BASE,cid)
    for spec in outfits or []:
        o=typed(ex,g,spec.get('name','outfit'),'firefighterOutfitItem')
        add_value(g,ship,'hasFirefighterOutfit',o,ex)
        if spec.get('omit_location'): continue
        loc=typed(ex,g,spec.get('name','outfit')+'Store','physicalStorageLocation')
        add_value(g,o,'hasStorageLocation',loc,ex)
        if spec.get('omit_class'): continue
        cls=WARM if spec.get('warm',True) else typed(ex,g,spec.get('name','outfit')+'ColdClass','storageTemperatureClassValue')
        add_value(g,loc,'storageTemperatureClass',cls,ex)
    return g

def o059(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None:return False
    for o in g.objects(ship,NLTL.hasFirefighterOutfit):
        locs=list(g.objects(o,NLTL.hasStorageLocation))
        if not locs:return False
        if not any(WARM in set(g.objects(loc,NLTL.storageTemperatureClass)) for loc in locs): return False
    return True

def b060(cid,separate=True,independent=True,clearing=True,omit=None):
    g,ex,ship=new_graph(BASE,cid)
    vals={'fixedWaterSystemSeparateFromMainFirePumps':separate,'independentSeaSuctionUsed':independent,'seaSuctionIceClearingCapability':clearing}
    for t,v in vals.items():
        if omit!=t:add_value(g,ship,t,v,ex)
    return g

def o060(g):
    ship=next(g.subjects(RDF.type,NLTL.ship),None)
    if ship is None:return False
    a=lit(g,ship,'fixedWaterSystemSeparateFromMainFirePumps'); b=lit(g,ship,'independentSeaSuctionUsed')
    if not isinstance(a,bool) or not isinstance(b,bool):return False
    if not (a and b):return True
    return lit(g,ship,'seaSuctionIceClearingCapability') is True

ORACLES={'IMO-050':o050,'IMO-051':o051,'IMO-052':o052,'IMO-053':o053,'IMO-055':o055,'IMO-057':o057,'IMO-058':o058,'IMO-059':o059,'IMO-060':o060}
CASES=[]
# 050
for cid,exp,g,rat in [
('IMO-050-P01','PASS',b050('IMO-050-P01'),'Exposed fire-safety component has ice/snow protection.'),
('IMO-050-P02','PASS',b050('IMO-050-P02',exposed=False,protected=False),'Non-exposed component does not activate protection obligation.'),
('IMO-050-F01','FAIL',b050('IMO-050-F01',protected=False),'Exposed fire-safety component lacks protection.'),
('IMO-050-F02','FAIL',b050('IMO-050-F02',omit='iceAndSnowProtectionPresent'),'Required protection state missing on applicable case.'),
('IMO-050-F03','FAIL',b050('IMO-050-F03',omit='fireSafetyComponentExposed'),'Applicability selector missing.'),
('IMO-050-F04','FAIL',b050('IMO-050-F04',exposed=True,protected=False),'Single semantic violation of mandatory protection.')]:CASES.append(case('IMO-050',cid,exp,g,rat))
# 051
for cid,exp,g,rat in [
('IMO-051-P01','PASS',b051('IMO-051-P01',[{'name':'control1'}]),'One local control is protected and continuously accessible.'),
('IMO-051-P02','PASS',b051('IMO-051-P02',[{'name':'control1'},{'name':'control2'}]),'Multiple represented controls all comply.'),
('IMO-051-P03','PASS',b051('IMO-051-P03',[]),'No represented local-control item; no existence cardinality invented by this requirement.'),
('IMO-051-F01','FAIL',b051('IMO-051-F01',[{'name':'control1','protection':False}]),'Protection against freezing/snow/ice absent.'),
('IMO-051-F02','FAIL',b051('IMO-051-F02',[{'name':'control1','accessible':False}]),'Control is not continuously accessible.'),
('IMO-051-F03','FAIL',b051('IMO-051-F03',[{'name':'control1','omit_access':True}]),'Accessibility state missing.'),
('IMO-051-F04','FAIL',b051('IMO-051-F04',[{'name':'control1'},{'name':'control2','protection':False}]),'Universal condition fails when one represented control is invalid.')]:CASES.append(case('IMO-051',cid,exp,g,rat))
# 052
for cid,exp,g,rat in [
('IMO-052-P01','PASS',b052('IMO-052-P01',[{'name':'access1'}]),'Required access has associated ice/snow removal or prevention means.'),
('IMO-052-P02','PASS',b052('IMO-052-P02',[{'name':'access1'},{'name':'access2'}]),'Multiple required accesses each have associated means.'),
('IMO-052-P03','PASS',b052('IMO-052-P03',[]),'No required-access item represented; universal condition is vacuous.'),
('IMO-052-F01','FAIL',b052('IMO-052-F01',[{'name':'access1','with_means':False}]),'Required access lacks associated means.'),
('IMO-052-F02','FAIL',b052('IMO-052-F02',[{'name':'access1'},{'name':'access2','with_means':False}]),'One of multiple required accesses lacks means.'),
('IMO-052-F03','FAIL',b052('IMO-052-F03',[{'name':'access1','wrong_owner':True}]),'Means exists but is connected through the wrong owner/path.'),
('IMO-052-F04','FAIL',b052('IMO-052-F04',[{'name':'access1','with_means':False}]),'Per-item relationship requirement is not satisfied.')]:CASES.append(case('IMO-052',cid,exp,g,rat))
# 053
for cid,exp,g,rat in [
('IMO-053-P01','PASS',b053('IMO-053-P01',[{'name':'waterMist'}]),'Extinguishing medium is approved for intended operation.'),
('IMO-053-P02','PASS',b053('IMO-053-P02',[{'name':'medium1'},{'name':'medium2'}]),'Multiple media all have approved compatibility.'),
('IMO-053-P03','PASS',b053('IMO-053-P03',[]),'No extinguishing medium represented; no unsupported existence cardinality added.'),
('IMO-053-F01','FAIL',b053('IMO-053-F01',[{'name':'medium1','approved':False}]),'Medium is not compatible with intended operation.'),
('IMO-053-F02','FAIL',b053('IMO-053-F02',[{'name':'medium1','omit_status':True}]),'Compatibility state missing.'),
('IMO-053-F03','FAIL',b053('IMO-053-F03',[{'name':'medium1'},{'name':'medium2','approved':False}]),'Universal condition fails for mixed valid/invalid media.')]:CASES.append(case('IMO-053',cid,exp,g,rat))
# 055
for cid,exp,g,rat in [
('IMO-055-P01','PASS',b055('IMO-055-P01',vtype='isolating'),'Exposed isolating valve protected and accessible.'),
('IMO-055-P02','PASS',b055('IMO-055-P02',vtype='pressure'),'Exposed pressure valve protected and accessible.'),
('IMO-055-P03','PASS',b055('IMO-055-P03',vtype='vacuum'),'Exposed vacuum valve protected and accessible.'),
('IMO-055-P04','PASS',b055('IMO-055-P04',exposed=False,protected=False,accessible=False),'Non-exposed valve is outside trigger.'),
('IMO-055-P05','PASS',b055('IMO-055-P05',vtype='control',protected=False,accessible=False),'Other valve type is outside enumerated trigger.'),
('IMO-055-F01','FAIL',b055('IMO-055-F01',protected=False),'Triggered valve lacks ice-accretion protection.'),
('IMO-055-F02','FAIL',b055('IMO-055-F02',accessible=False),'Triggered valve is not continuously accessible.'),
('IMO-055-F03','FAIL',b055('IMO-055-F03',omit='valveType'),'Valve-type selector missing.'),
('IMO-055-F04','FAIL',b055('IMO-055-F04',omit='valveExposed'),'Exposure selector missing.')]:CASES.append(case('IMO-055',cid,exp,g,rat))
# 057
for cid,exp,g,rat in [
('IMO-057-P01','PASS',b057('IMO-057-P01',[{'name':'fire','cls':'firePump','temp':1}]),'Fire pump compartment is above freezing.'),
('IMO-057-P02','PASS',b057('IMO-057-P02',[{'name':'emergency','cls':'emergencyFirePump','temp':5}]),'Emergency fire pump satisfies same temperature rule.'),
('IMO-057-P03','PASS',b057('IMO-057-P03',[{'name':'mist','cls':'waterMistPump','temp':10}]),'Water-mist pump satisfies temperature rule.'),
('IMO-057-P04','PASS',b057('IMO-057-P04',[{'name':'spray','cls':'waterSprayPump','temp':0.1}]),'Water-spray pump just above freezing passes.'),
('IMO-057-P05','PASS',b057('IMO-057-P05',[{'name':'fire','cls':'firePump','temp':3},{'name':'mist','cls':'waterMistPump','temp':4}]),'Multiple target pumps all located above freezing.'),
('IMO-057-P06','PASS',b057('IMO-057-P06',[]),'No target pump represented; this requirement does not create pump existence.'),
('IMO-057-F01','FAIL',b057('IMO-057-F01',[{'name':'fire','cls':'firePump','temp':0}]),'Exactly freezing is not above freezing.'),
('IMO-057-F02','FAIL',b057('IMO-057-F02',[{'name':'fire','cls':'firePump','temp':-1}]),'Pump compartment below freezing.'),
('IMO-057-F03','FAIL',b057('IMO-057-F03',[{'name':'fire','cls':'firePump','omit_temp':True}]),'Maintained temperature missing.'),
('IMO-057-F04','FAIL',b057('IMO-057-F04',[{'name':'fire','cls':'firePump','omit_compartment':True}]),'Containing-compartment path missing.'),
('IMO-057-F05','FAIL',b057('IMO-057-F05',[{'name':'fire','cls':'firePump','temp':5,'unit':UNIT.K}]),'Maintained temperature encoded in wrong frozen R13 unit.'),
('IMO-057-F06','FAIL',b057('IMO-057-F06',[{'name':'fire','cls':'firePump','temp':5},{'name':'mist','cls':'waterMistPump','temp':0}]),'One of multiple target pumps violates the requirement.')]:CASES.append(case('IMO-057',cid,exp,g,rat))
# 058
for cid,exp,g,rat in [
('IMO-058-P01','PASS',b058('IMO-058-P01',[{'name':'section1'}]),'Exposed fire-main section can be isolated and drained.'),
('IMO-058-P02','PASS',b058('IMO-058-P02',[{'name':'section1'},{'name':'section2'}]),'Multiple exposed sections all comply.'),
('IMO-058-P03','PASS',b058('IMO-058-P03',[]),'No exposed fire-main section represented; no existence requirement invented.'),
('IMO-058-F01','FAIL',b058('IMO-058-F01',[{'name':'section1','isolation':False}]),'Isolation capability absent.'),
('IMO-058-F02','FAIL',b058('IMO-058-F02',[{'name':'section1','drainage':False}]),'Drainage means absent.'),
('IMO-058-F03','FAIL',b058('IMO-058-F03',[{'name':'section1','omit_drainage':True}]),'Drainage state missing.'),
('IMO-058-F04','FAIL',b058('IMO-058-F04',[{'name':'section1'},{'name':'section2','isolation':False}]),'Universal condition fails when one exposed section is invalid.')]:CASES.append(case('IMO-058',cid,exp,g,rat))
# 059
for cid,exp,g,rat in [
('IMO-059-P01','PASS',b059('IMO-059-P01',[{'name':'outfit1'}]),'Firefighter outfit stored at warm-class location.'),
('IMO-059-P02','PASS',b059('IMO-059-P02',[{'name':'outfit1'},{'name':'outfit2'}]),'Multiple outfits each have warm storage.'),
('IMO-059-P03','PASS',b059('IMO-059-P03',[]),'No firefighter outfit represented; no existence cardinality created.'),
('IMO-059-F01','FAIL',b059('IMO-059-F01',[{'name':'outfit1','warm':False}]),'Outfit storage is not warm-class.'),
('IMO-059-F02','FAIL',b059('IMO-059-F02',[{'name':'outfit1','omit_location':True}]),'Storage-location relationship missing.'),
('IMO-059-F03','FAIL',b059('IMO-059-F03',[{'name':'outfit1','omit_class':True}]),'Storage temperature class missing.'),
('IMO-059-F04','FAIL',b059('IMO-059-F04',[{'name':'outfit1'},{'name':'outfit2','warm':False}]),'Universal storage condition fails for one invalid outfit.')]:CASES.append(case('IMO-059',cid,exp,g,rat))
# 060
for cid,exp,g,rat in [
('IMO-060-P01','PASS',b060('IMO-060-P01',True,True,True),'Separate fixed-water system with independent suction has ice-clearing capability.'),
('IMO-060-P02','PASS',b060('IMO-060-P02',False,True,False),'System not separate from main pumps: conditional obligation inactive.'),
('IMO-060-P03','PASS',b060('IMO-060-P03',True,False,False),'Independent sea suction not used: conditional obligation inactive.'),
('IMO-060-P04','PASS',b060('IMO-060-P04',False,False,False),'Both trigger conditions false.'),
('IMO-060-F01','FAIL',b060('IMO-060-F01',True,True,False),'Triggered sea suction cannot be cleared of ice.'),
('IMO-060-F02','FAIL',b060('IMO-060-F02',True,True,omit='seaSuctionIceClearingCapability'),'Triggered result state missing.'),
('IMO-060-F03','FAIL',b060('IMO-060-F03',omit='independentSeaSuctionUsed'),'Conditional selector missing.')]:CASES.append(case('IMO-060',cid,exp,g,rat))

MANIFEST='imo_batch_f_manifest.jsonl'; LOCK='imo_batch_f_fixture_lock.json'; VALIDATOR='validate_imo_batch_f.py'
def run():
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                   batch_label='IMO Polar Code Behavioral Benchmark Batch F',manifest_name=MANIFEST,lock_name=LOCK,
                   validator_name=VALIDATOR,family='IMO')
def main():
    validation_mode=Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv
    if validation_mode:
        ok=validate_batch(MANIFEST,LOCK,ORACLES,True); raise SystemExit(0 if ok else 1)
    run()
if __name__=='__main__': main()
