
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


BASE='https://w3id.org/nltl/benchmark/imo-batch-d/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-031','IMO-032','IMO-033','IMO-034','IMO-035','IMO-037','IMO-038']
MODES={
    'IMO-031':'DIRECT_STATIC','IMO-032':'DIRECT_STATIC','IMO-033':'DIRECT_CALCULATION',
    'IMO-034':'DIRECT_STATIC','IMO-035':'DIRECT_STATIC','IMO-037':'COMPLEX_READINESS',
    'IMO-038':'DIRECT_CALCULATION'
}
CLAUSES={
    'IMO-031':'Part I-A 3.3.1','IMO-032':'Part I-A 3.3.2.1-.3','IMO-033':'Part I-A 4.3.1.1',
    'IMO-034':'Part I-A 4.3.1.2','IMO-035':'Part I-A 4.3.1.3','IMO-037':'Part I-A 4.3.2.1',
    'IMO-038':'Part I-A 4.3.2.2'
}

APPROVED=NLTL.evidenceStateApproved
REJECTED=NLTL.evidenceStateRejected
CAT_A=NLTL.polarShipCategoryA; CAT_B=NLTL.polarShipCategoryB; CAT_C=NLTL.polarShipCategoryC
ALLOWED_AUTH={'Administration','recognized organization accepted by the Administration'}
AB_STANDARDS={'standard acceptable to the Organization','another standard offering an equivalent level of safety'}
C_STANDARD='acceptable standard adequate for operating ice type and concentration'

def ship_of(g): return next(g.subjects(RDF.type,NLTL.ship),None)
def obj(g,s,term): return one(g,s,term)
def has_obj(g,s,term,o): return (s,NLTL[term],o) in g

def case(req,cid,expected,graph,rationale):
    return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}

# IMO-031 ------------------------------------------------------
def b031(cid,authority='Administration',standard='standard acceptable to the Organization',status=APPROVED,pst=-30,omit=None):
    g,ex,s=new_graph(BASE,cid)
    vals={
        'exposedStructureMaterial':'grade-qualified exposed structural steel',
        'materialApprovalStatus':status,
        'approvingAuthority':authority,
        'approvalStandard':standard,
        'polarServiceTemperature':pst,
    }
    for t,v in vals.items():
        if omit==t: continue
        add_value(g,s,t,v,ex)
    return g

def o031(g):
    s=ship_of(g)
    return (
        isinstance(lit(g,s,'exposedStructureMaterial'),str)
        and obj(g,s,'materialApprovalStatus')==APPROVED
        and lit(g,s,'approvingAuthority') in ALLOWED_AUTH
        and lit(g,s,'approvalStandard') in AB_STANDARDS
        and qnum(g,s,'polarServiceTemperature') is not None
    )

# IMO-032 ------------------------------------------------------
def b032(cid,cat=CAT_A,strengthened=True,authority='Administration',standard='standard acceptable to the Organization',status=APPROVED,ice_type='medium first-year ice',ice_conc=0.7,omit_record=False,omit=None):
    g,ex,s=new_graph(BASE,cid)
    add_value(g,s,'shipCategory',cat,ex); add_value(g,s,'shipIceStrengthened',strengthened,ex)
    if omit_record: return g
    rec=typed(ex,g,'approvalRecord','approvalRecord'); add_value(g,s,'hasApprovalRecord',rec,ex)
    vals={'approvingAuthority':authority,'approvalStandard':standard,'scantlingApprovalStatus':status}
    if cat==CAT_C and strengthened:
        vals.update({'operatingIceType':ice_type,'operatingIceConcentration':ice_conc})
    for t,v in vals.items():
        if omit==t: continue
        add_value(g,rec,t,v,ex)
    return g

def _approval_record_ok(g,rec,cat,strengthened):
    if obj(g,rec,'scantlingApprovalStatus')!=APPROVED: return False
    if lit(g,rec,'approvingAuthority') not in ALLOWED_AUTH: return False
    std=lit(g,rec,'approvalStandard')
    if cat in (CAT_A,CAT_B): return std in AB_STANDARDS
    if cat==CAT_C and strengthened:
        return std==C_STANDARD and isinstance(lit(g,rec,'operatingIceType'),str) and bool(lit(g,rec,'operatingIceType').strip()) and qnum(g,rec,'operatingIceConcentration') is not None
    return True

def o032(g):
    s=ship_of(g); cat=obj(g,s,'shipCategory'); strengthened=lit(g,s,'shipIceStrengthened')
    if cat==CAT_C and strengthened is False: return True
    if cat not in (CAT_A,CAT_B,CAT_C) or strengthened is None: return False
    recs=list(g.objects(s,NLTL.hasApprovalRecord))
    if len(recs)!=1: return False
    return _approval_record_ok(g,recs[0],cat,bool(strengthened))

# IMO-033 ------------------------------------------------------
def b033(cid,likely=True,area=100.0,moment=200.0,deck=30.0,side=7.5,darea=None,dmoment=None,omit=None,wrong_unit=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'iceAccretionLikely',likely,ex)
    if not likely: return g
    darea=area*1.05 if darea is None else darea; dmoment=moment*1.10 if dmoment is None else dmoment
    vals={'deckIcingAllowance':deck,'sideIcingAllowance':side,'continuousSurfaceProjectedArea':area,
          'continuousSurfaceStaticMoment':moment,'discontinuousSurfaceProjectedArea':darea,'discontinuousSurfaceStaticMoment':dmoment}
    for t,v in vals.items():
        if omit==t: continue
        unit_override=(UNIT.GM_PER_M2 if wrong_unit==t else None)
        add_value(g,s,t,v,ex,unit_override=unit_override)
    return g

def o033(g):
    s=ship_of(g); likely=lit(g,s,'iceAccretionLikely')
    if likely is False: return True
    if likely is not True: return False
    deck=qnum(g,s,'deckIcingAllowance'); side=qnum(g,s,'sideIcingAllowance')
    a=qnum(g,s,'continuousSurfaceProjectedArea'); m=qnum(g,s,'continuousSurfaceStaticMoment')
    da=qnum(g,s,'discontinuousSurfaceProjectedArea'); dm=qnum(g,s,'discontinuousSurfaceStaticMoment')
    return close(deck,30) and close(side,7.5) and a is not None and m is not None and close(da,a*1.05) and close(dm,m*1.10)

# IMO-034 ------------------------------------------------------
def b034(cid,likely=True,min_design=True,removal=True,omit=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'iceAccretionLikely',likely,ex)
    if likely:
        if omit!='iceAccretionMinimizationDesignPresent': add_value(g,s,'iceAccretionMinimizationDesignPresent',min_design,ex)
        if omit!='requiredIceRemovalMeansPresent': add_value(g,s,'requiredIceRemovalMeansPresent',removal,ex)
        add_value(g,s,'administrationRequiredIceRemovalMeans','electrical, pneumatic, or special-tool means as required',ex)
    return g

def o034(g):
    s=ship_of(g); likely=lit(g,s,'iceAccretionLikely')
    if likely is False: return True
    return likely is True and lit(g,s,'iceAccretionMinimizationDesignPresent') is True and lit(g,s,'requiredIceRemovalMeansPresent') is True

# IMO-035 ------------------------------------------------------
def b035(cid,info=True,pwom_values='deck=30 kg/m2; side=7.5 kg/m2',stab_values='deck=30 kg/m2; side=7.5 kg/m2',omit=None,wrong_owner=False):
    g,ex,s=new_graph(BASE,cid)
    pw=typed(ex,g,'pwomRecord','documentRecord'); st=typed(ex,g,'stabilityRecord','documentRecord')
    if omit!='hasPolarWaterOperationalManualRecord': add_value(g,s,'hasPolarWaterOperationalManualRecord',pw,ex)
    if omit!='hasStabilityCalculationRecord': add_value(g,s,'hasStabilityCalculationRecord',st,ex)
    target=s if wrong_owner else pw
    if omit!='polarWaterOperationalManualIcingAllowanceInformationPresent': add_value(g,target,'polarWaterOperationalManualIcingAllowanceInformationPresent',info,ex)
    if omit!='polarWaterOperationalManualIcingAllowanceValues': add_value(g,target,'polarWaterOperationalManualIcingAllowanceValues',pwom_values,ex)
    if omit!='stabilityCalculationIcingAllowanceValues': add_value(g,st,'stabilityCalculationIcingAllowanceValues',stab_values,ex)
    return g

def o035(g):
    s=ship_of(g); pws=list(g.objects(s,NLTL.hasPolarWaterOperationalManualRecord)); sts=list(g.objects(s,NLTL.hasStabilityCalculationRecord))
    if len(pws)!=1 or len(sts)!=1: return False
    pw,st=pws[0],sts[0]
    a=lit(g,pw,'polarWaterOperationalManualIcingAllowanceValues'); b=lit(g,st,'stabilityCalculationIcingAllowanceValues')
    return lit(g,pw,'polarWaterOperationalManualIcingAllowanceInformationPresent') is True and isinstance(a,str) and bool(a.strip()) and a==b

# IMO-037 ------------------------------------------------------
def _loading(g,ex,s,name,alt=False,residual=1.0,alt_status=True,evidence=True,omit=None,wrong_path=False):
    lc=typed(ex,g,name,'loadingConditionCase'); add_value(g,s,'hasLoadingConditionCase',lc,ex)
    if omit!='loadingConditionIdentifier': add_value(g,lc,'loadingConditionIdentifier',name,ex)
    if omit!='alternativeInstrumentApplicable': add_value(g,lc,'alternativeInstrumentApplicable',alt,ex)
    if omit!='residualStabilityFactorSI': add_value(g,lc,'residualStabilityFactorSI',residual,ex)
    if alt and omit!='alternativeInstrumentResidualStabilityStatus': add_value(g,lc,'alternativeInstrumentResidualStabilityStatus',alt_status,ex)
    if evidence and omit!='hasLoadingConditionResultEvidence':
        ev=typed(ex,g,name+'Evidence','evidenceArtifact')
        add_value(g,s if wrong_path else lc,'hasLoadingConditionResultEvidence',ev,ex)
    return lc

def b037(cid,cat=CAT_A,date='2017-01-01',loads=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'shipCategory',cat,ex); add_value(g,s,'constructionDate',date,ex)
    for kw in (loads or []): _loading(g,ex,s,**kw)
    return g

def o037(g):
    s=ship_of(g); cat=obj(g,s,'shipCategory'); dt=lit(g,s,'constructionDate')
    if cat not in (CAT_A,CAT_B): return True if cat is not None and dt is not None else False
    if dt is None: return False
    from datetime import date as _date
    if dt < _date(2017,1,1): return True
    lcs=list(g.objects(s,NLTL.hasLoadingConditionCase))
    if not lcs: return False
    for lc in lcs:
        if not isinstance(lit(g,lc,'loadingConditionIdentifier'),str): return False
        alt=lit(g,lc,'alternativeInstrumentApplicable')
        if alt not in (True,False): return False
        if qnum(g,lc,'residualStabilityFactorSI') is None: return False
        if len(list(g.objects(lc,NLTL.hasLoadingConditionResultEvidence)))!=1: return False
        if alt is True and lit(g,lc,'alternativeInstrumentResidualStabilityStatus') is not True: return False
    return True

# IMO-038 ------------------------------------------------------
def b038(cid,forward=True,L=100.0,T=10.0,pos=6.0,long=None,trans=760.0,vert=None,omit=None,wrong_unit=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'damageCenterForwardOfMaxBreadth',forward,ex)
    expected_long=(0.045 if forward else 0.015)*L
    long=expected_long if long is None else long
    vert=min(0.20*T,expected_long) if vert is None else vert
    vals={'upperIceWaterlineLength':L,'upperIceWaterlineDraught':T,'longitudinalDamageExtent':long,
          'transversePenetration':trans,'verticalDamageExtent':vert,'selectedVerticalDamagePosition':pos}
    for t,v in vals.items():
        if omit==t: continue
        unit_override=(UNIT.MilliM if wrong_unit==t and t!='transversePenetration' else (UNIT.M if wrong_unit==t else None))
        add_value(g,s,t,v,ex,unit_override=unit_override)
    return g

def o038(g):
    s=ship_of(g); forward=lit(g,s,'damageCenterForwardOfMaxBreadth')
    if forward not in (True,False): return False
    L=qnum(g,s,'upperIceWaterlineLength'); T=qnum(g,s,'upperIceWaterlineDraught')
    le=qnum(g,s,'longitudinalDamageExtent'); tp=qnum(g,s,'transversePenetration'); ve=qnum(g,s,'verticalDamageExtent'); pos=qnum(g,s,'selectedVerticalDamagePosition')
    if None in (L,T,le,tp,ve,pos): return False
    exp=(0.045 if forward else 0.015)*L
    return close(le,exp) and close(tp,760.0) and close(ve,min(0.20*T,exp)) and (-1e-9 <= pos <= 1.20*T+1e-9)

ORACLES={'IMO-031':o031,'IMO-032':o032,'IMO-033':o033,'IMO-034':o034,'IMO-035':o035,'IMO-037':o037,'IMO-038':o038}
CASES=[]
# 031
for cid,exp,g,rat in [
('IMO-031-P01','PASS',b031('IMO-031-P01'),'Administration approval, acceptable standard and PST basis.'),
('IMO-031-P02','PASS',b031('IMO-031-P02',authority='recognized organization accepted by the Administration',standard='another standard offering an equivalent level of safety'),'Recognized-organization/equivalent-safety branch.'),
('IMO-031-F01','FAIL',b031('IMO-031-F01',authority='yard self-approval'),'Unauthorized approving authority.'),
('IMO-031-F02','FAIL',b031('IMO-031-F02',standard='uncontrolled internal standard'),'Unapproved standard route.'),
('IMO-031-F03','FAIL',b031('IMO-031-F03',status=REJECTED),'Material approval status is not approved.'),
('IMO-031-F04','FAIL',b031('IMO-031-F04',omit='polarServiceTemperature'),'PST basis missing.'),
('IMO-031-F05','FAIL',b031('IMO-031-F05',omit='exposedStructureMaterial'),'Applicable exposed material identifier missing.')]: CASES.append(case('IMO-031',cid,exp,g,rat))
# 032
for cid,exp,g,rat in [
('IMO-032-P01','PASS',b032('IMO-032-P01',cat=CAT_A),'Category A approval via Administration.'),
('IMO-032-P02','PASS',b032('IMO-032-P02',cat=CAT_B,authority='recognized organization accepted by the Administration',standard='another standard offering an equivalent level of safety'),'Category B recognized-organization/equivalent-safety route.'),
('IMO-032-P03','PASS',b032('IMO-032-P03',cat=CAT_C,strengthened=True,standard=C_STANDARD),'Ice-strengthened Category C with adequate ice-specific standard.'),
('IMO-032-P04','PASS',b032('IMO-032-P04',cat=CAT_C,strengthened=False,omit_record=True),'Category C not ice strengthened: R13 branch not applicable.'),
('IMO-032-F01','FAIL',b032('IMO-032-F01',cat=CAT_A,omit_record=True),'Applicable Category A approval record missing.'),
('IMO-032-F02','FAIL',b032('IMO-032-F02',cat=CAT_B,authority='manufacturer'),'Unauthorized authority for Category B.'),
('IMO-032-F03','FAIL',b032('IMO-032-F03',cat=CAT_C,strengthened=True,standard='another standard offering an equivalent level of safety'),'Category C branch does not admit the A/B equivalent-safety alternative.'),
('IMO-032-F04','FAIL',b032('IMO-032-F04',cat=CAT_C,strengthened=True,standard=C_STANDARD,omit='operatingIceConcentration'),'Category C ice-concentration context missing.'),
('IMO-032-F05','FAIL',b032('IMO-032-F05',cat=CAT_A,status=REJECTED),'Scantling approval state is not approved.')]: CASES.append(case('IMO-032',cid,exp,g,rat))
# 033
for cid,exp,g,rat in [
('IMO-033-P01','PASS',b033('IMO-033-P01',area=100,moment=200),'Exact icing allowances and 5%/10% formula results.'),
('IMO-033-P02','PASS',b033('IMO-033-P02',area=37.25,moment=81.5),'Independent numeric formula instance.'),
('IMO-033-P03','PASS',b033('IMO-033-P03',likely=False),'Ice accretion not likely: conditional calculation inactive.'),
('IMO-033-F01','FAIL',b033('IMO-033-F01',deck=29.9),'Deck icing allowance below prescribed 30 kg/m2.'),
('IMO-033-F02','FAIL',b033('IMO-033-F02',side=7.4),'Side icing allowance differs from 7.5 kg/m2.'),
('IMO-033-F03','FAIL',b033('IMO-033-F03',darea=104.0),'Projected-area 5% increase calculated incorrectly.'),
('IMO-033-F04','FAIL',b033('IMO-033-F04',dmoment=219.0),'Static-moment 10% increase calculated incorrectly.'),
('IMO-033-F05','FAIL',b033('IMO-033-F05',omit='continuousSurfaceProjectedArea'),'Formula operand missing.'),
('IMO-033-F06','FAIL',b033('IMO-033-F06',omit='discontinuousSurfaceStaticMoment'),'Formula result missing.'),
('IMO-033-F07','FAIL',b033('IMO-033-F07',wrong_unit='deckIcingAllowance'),'Wrong QUDT unit on deck icing allowance.')]: CASES.append(case('IMO-033',cid,exp,g,rat))
# 034
for cid,exp,g,rat in [
('IMO-034-P01','PASS',b034('IMO-034-P01'),'Ice-accretion design and removal means both present.'),
('IMO-034-P02','PASS',b034('IMO-034-P02',likely=False),'No ice-accretion trigger.'),
('IMO-034-F01','FAIL',b034('IMO-034-F01',min_design=False),'Ice-accretion minimization design absent.'),
('IMO-034-F02','FAIL',b034('IMO-034-F02',removal=False),'Required ice-removal means absent.'),
('IMO-034-F03','FAIL',b034('IMO-034-F03',omit='requiredIceRemovalMeansPresent'),'Required boolean result missing.')]: CASES.append(case('IMO-034',cid,exp,g,rat))
# 035
for cid,exp,g,rat in [
('IMO-035-P01','PASS',b035('IMO-035-P01'),'PWOM carries icing information matching stability calculation.'),
('IMO-035-P02','PASS',b035('IMO-035-P02',pwom_values='30|7.5|5%|10%',stab_values='30|7.5|5%|10%'),'Second matching document-value representation.'),
('IMO-035-F01','FAIL',b035('IMO-035-F01',info=False),'PWOM icing information presence flag false.'),
('IMO-035-F02','FAIL',b035('IMO-035-F02',pwom_values='30|7.5',stab_values='30|8.0'),'PWOM values do not match stability calculation.'),
('IMO-035-F03','FAIL',b035('IMO-035-F03',omit='hasPolarWaterOperationalManualRecord'),'PWOM record path missing.'),
('IMO-035-F04','FAIL',b035('IMO-035-F04',omit='hasStabilityCalculationRecord'),'Stability-calculation record path missing.'),
('IMO-035-F05','FAIL',b035('IMO-035-F05',wrong_owner=True),'PWOM icing facts placed on wrong owner rather than linked record.')]: CASES.append(case('IMO-035',cid,exp,g,rat))
# 037 readiness -- numeric equality is intentionally not independently executed
for cid,exp,g,rat in [
('IMO-037-P01','PASS',b037('IMO-037-P01',loads=[{'name':'LC1','alt':False,'residual':1.0}]),'Applicable standard route with complete R13 readiness interface.'),
('IMO-037-P02','PASS',b037('IMO-037-P02',cat=CAT_B,loads=[{'name':'LC1','alt':True,'residual':0.84,'alt_status':True}]),'Alternative-instrument route with compliant result interface.'),
('IMO-037-P03','PASS',b037('IMO-037-P03',loads=[{'name':'LC1','alt':False,'residual':0.77}]),'Deliberately formula/value-inconsistent residual factor retained as PASS: R13 marks this COMPLEX_READINESS with formulaExecutionRequired=false.'),
('IMO-037-P04','PASS',b037('IMO-037-P04',cat=CAT_C,date='2020-01-01',loads=[]),'Category C lies outside A/B damaged-stability cohort.'),
('IMO-037-P05','PASS',b037('IMO-037-P05',cat=CAT_A,date='2016-12-31',loads=[]),'Pre-2017 construction lies outside applicability cohort.'),
('IMO-037-F01','FAIL',b037('IMO-037-F01',loads=[]),'Applicable ship has no loading-condition readiness case.'),
('IMO-037-F02','FAIL',b037('IMO-037-F02',loads=[{'name':'LC1','alt':False,'omit':'loadingConditionIdentifier'}]),'Loading-condition identifier operand missing.'),
('IMO-037-F03','FAIL',b037('IMO-037-F03',loads=[{'name':'LC1','alt':False,'omit':'residualStabilityFactorSI'}]),'Required residual-stability result interface missing.'),
('IMO-037-F04','FAIL',b037('IMO-037-F04',loads=[{'name':'LC1','alt':True,'alt_status':False}]),'Alternative instrument route represented as non-compliant.'),
('IMO-037-F05','FAIL',b037('IMO-037-F05',loads=[{'name':'LC1','alt':False,'evidence':False}]),'Required loading-condition result evidence path missing.'),
('IMO-037-F06','FAIL',b037('IMO-037-F06',loads=[{'name':'LC1','alt':False,'wrong_path':True}]),'Result evidence attached to ship instead of loadingConditionCase.'),
('IMO-037-F07','FAIL',b037('IMO-037-F07',loads=[{'name':'LC1','alt':False},{'name':'LC2','alt':True,'alt_status':False}]),'Universal readiness fails when one represented loading condition has no valid route.')]: CASES.append(case('IMO-037',cid,exp,g,rat))
# 038
for cid,exp,g,rat in [
('IMO-038-P01','PASS',b038('IMO-038-P01',forward=True,L=100,T=10,pos=0),'Forward branch and lower inclusive vertical-position boundary.'),
('IMO-038-P02','PASS',b038('IMO-038-P02',forward=True,L=100,T=10,pos=12),'Upper inclusive vertical-position boundary at 1.20 draught.'),
('IMO-038-P03','PASS',b038('IMO-038-P03',forward=False,L=100,T=10,pos=6),'Aft/non-forward 1.5% longitudinal branch.'),
('IMO-038-P04','PASS',b038('IMO-038-P04',forward=False,L=300,T=5,pos=3),'Case where 20% draught governs vertical damage extent.'),
('IMO-038-F01','FAIL',b038('IMO-038-F01',forward=True,L=100,T=10,long=4.4),'Wrong forward longitudinal damage extent.'),
('IMO-038-F02','FAIL',b038('IMO-038-F02',trans=759),'Transverse penetration must be 760 mm.'),
('IMO-038-F03','FAIL',b038('IMO-038-F03',forward=True,L=100,T=10,vert=1.9),'Vertical damage extent not equal to required minimum.'),
('IMO-038-F04','FAIL',b038('IMO-038-F04',T=10,pos=-0.01),'Selected vertical position below keel.'),
('IMO-038-F05','FAIL',b038('IMO-038-F05',T=10,pos=12.01),'Selected vertical position above 120% UIWL draught.'),
('IMO-038-F06','FAIL',b038('IMO-038-F06',omit='upperIceWaterlineLength'),'Required formula operand missing.'),
('IMO-038-F07','FAIL',b038('IMO-038-F07',omit='verticalDamageExtent'),'Required formula result missing.'),
('IMO-038-F08','FAIL',b038('IMO-038-F08',wrong_unit='longitudinalDamageExtent'),'Wrong unit on longitudinal damage extent.')]: CASES.append(case('IMO-038',cid,exp,g,rat))

MANIFEST='imo_batch_d_manifest.jsonl'; LOCK='imo_batch_d_fixture_lock.json'; VALIDATOR='validate_imo_batch_d.py'

def run():
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                   batch_label='IMO Polar Code Behavioral Benchmark Batch D',manifest_name=MANIFEST,lock_name=LOCK,
                   validator_name=VALIDATOR,family='IMO')

def main():
    validation_mode=Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv
    if validation_mode:
        ok=validate_batch(MANIFEST,LOCK,ORACLES,True); raise SystemExit(0 if ok else 1)
    run()

if __name__=='__main__': main()
