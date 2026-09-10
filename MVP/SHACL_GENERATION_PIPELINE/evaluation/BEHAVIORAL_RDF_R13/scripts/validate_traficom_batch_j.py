
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

BASE='https://w3id.org/nltl/benchmark/traficom-batch-j/'
SOURCE_ID='SRC-TRAFICOM-2021'
REQS=['TRF-126','TRF-127','TRF-128','TRF-129','TRF-130','TRF-131','TRF-132','TRF-133']
MODES={
'TRF-126':'DIRECT_STATIC','TRF-127':'DIRECT_STATIC','TRF-128':'DIRECT_STATIC','TRF-129':'DIRECT_STATIC',
'TRF-130':'DIRECT_CALCULATION','TRF-131':'DIRECT_STATIC','TRF-132':'DIRECT_CALCULATION','TRF-133':'DIRECT_STATIC'}
CLAUSES={'TRF-126':'7.1','TRF-127':'7.1','TRF-128':'7.1','TRF-129':'7.2','TRF-130':'7.2','TRF-131':'7.2','TRF-132':'Annex II','TRF-133':'Annex III'}
ICE={'IAS':NLTL.iceClassIaSuper,'IA':NLTL.iceClassIa,'IB':NLTL.iceClassIb,'IC':NLTL.iceClassIc}

def build126(cid,reversed_value=True,starts=12,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='propulsionEngineReversedForAstern': add_value(g,s,'propulsionEngineReversedForAstern',reversed_value,ex)
    if omit!='airReceiverConsecutiveStartCapacity': add_value(g,s,'airReceiverConsecutiveStartCapacity',starts,ex)
    return g
def oracle126(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); rev=lit(g,s,'propulsionEngineReversedForAstern'); n=lit(g,s,'airReceiverConsecutiveStartCapacity')
    if not isinstance(rev,bool) or not isinstance(n,int): return False
    return n >= (12 if rev else 6)

def build127(cid,serves=True,capacity=10,required=8,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='airReceiverServesAdditionalPurpose': add_value(g,s,'airReceiverServesAdditionalPurpose',serves,ex)
    if omit!='airReceiverCapacity': add_value(g,s,'airReceiverCapacity',capacity,ex)
    if omit!='additionalPurposeRequiredAirCapacity': add_value(g,s,'additionalPurposeRequiredAirCapacity',required,ex,unit_override=UNIT.M3)
    return g
def oracle127(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); serves=lit(g,s,'airReceiverServesAdditionalPurpose')
    if not isinstance(serves,bool): return False
    if not serves: return True
    cap=qnum(g,s,'airReceiverCapacity'); req=qnum(g,s,'additionalPurposeRequiredAirCapacity',UNIT.M3)
    return cap is not None and req is not None and cap>=req

def build128(cid,ice='IAS',rev=True,hours=.5,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceClass': add_value(g,s,'iceClass',ICE[ice],ex)
    if omit!='propulsionEngineReversalRequiredForAstern': add_value(g,s,'propulsionEngineReversalRequiredForAstern',rev,ex)
    if omit!='compressorChargeTime': add_value(g,s,'compressorChargeTime',hours,ex)
    return g
def oracle128(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); ic=one(g,s,'iceClass'); rev=lit(g,s,'propulsionEngineReversalRequiredForAstern'); t=qnum(g,s,'compressorChargeTime')
    if ic is None or not isinstance(rev,bool) or t is None: return False
    limit=.5 if ic==NLTL.iceClassIaSuper and rev else 1.0
    return t<=limit+1e-12

def build129(cid,navigating=True,secured=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='navigatingInIce': add_value(g,s,'navigatingInIce',navigating,ex)
    if omit!='iceNavigationCondition': add_value(g,s,'iceNavigationCondition','navigating in ice' if navigating else 'open water',ex)
    if secured is not None and omit!='coolingWaterSupplySecured': add_value(g,s,'coolingWaterSupplySecured',secured,ex)
    return g
def oracle129(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); nav=lit(g,s,'navigatingInIce')
    if not isinstance(nav,bool): return False
    if nav:
        return lit(g,s,'coolingWaterSupplySecured') is True
    return True

def add_chest(g,ex,s,name,power=1500,rec=2.0,area=4.0,inlet=1.0,loc=True,space=True,discharge=True,actual=2.0,alternating=None):
    c=typed(ex,g,name,'inletChest'); add_raw_object(g,s,'hasComponent',c)
    add_value(g,c,'totalRelevantEnginePower',power,ex,name=name+'Power')
    add_value(g,c,'recommendedChestVolume',rec,ex,name=name+'Recommended')
    add_value(g,c,'seaChestVolume',actual,ex,name=name+'Actual')
    add_value(g,c,'inletPipeArea',inlet,ex,name=name+'InletArea')
    add_value(g,c,'strainerOpenArea',area,ex,name=name+'StrainerArea')
    add_value(g,c,'strainerOpenAreaRatio',area/inlet,ex,name=name+'Ratio')
    add_value(g,c,'nearCentrelineAndWellAftIfPossible',loc,ex)
    add_value(g,c,'iceAccumulationSpaceAboveInlet',space,ex)
    add_value(g,c,'fullCapacityDischargePipeConnected',discharge,ex)
    if alternating is not None: add_value(g,c,'alternatingCoolingWaterIntakeAndDischarge',alternating,ex)
    return c
def build130(cid,alt=False,two=True,bad=None,omit_selector=False):
    g,ex,s=new_graph(BASE,cid)
    if not omit_selector: add_value(g,s,'coolingWaterChestVolumeAndHeightRequirementsCannotBeMet',alt,ex)
    add_value(g,s,'coolingWaterChestAlternativeArrangementUsed',alt,ex)
    kwargs=dict(power=1500,rec=2.0,area=4.0,inlet=1.0,loc=True,space=True,discharge=True,actual=2.0,alternating=True if alt else None)
    if bad=='recommended': kwargs['rec']=1.0
    if bad=='ratio': kwargs['area']=3.9
    if bad=='location': kwargs['loc']=False
    if bad=='space': kwargs['space']=False
    if bad=='discharge': kwargs['discharge']=False
    if bad!='noChest': add_chest(g,ex,s,'chest1',**kwargs)
    if alt and two and bad!='oneChest':
        kwargs2=dict(kwargs); kwargs2['actual']=1.0
        if bad=='alternating': kwargs2['alternating']=False
        add_chest(g,ex,s,'chest2',**kwargs2)
    if bad=='altFlag': 
        # replace the single true value by false
        g.remove((s,NLTL.coolingWaterChestAlternativeArrangementUsed,None)); add_value(g,s,'coolingWaterChestAlternativeArrangementUsed',False,ex)
    return g
def oracle130(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); selector=lit(g,s,'coolingWaterChestVolumeAndHeightRequirementsCannotBeMet')
    if not isinstance(selector,bool): return False
    chests=[o for o in g.objects(s,NLTL.hasComponent) if (o,RDF.type,NLTL.inletChest) in g]
    if not chests: return False
    for c in chests:
        power=qnum(g,c,'totalRelevantEnginePower'); rec=qnum(g,c,'recommendedChestVolume'); area=qnum(g,c,'strainerOpenArea'); inlet=qnum(g,c,'inletPipeArea'); ratio=qnum(g,c,'strainerOpenAreaRatio')
        if None in (power,rec,area,inlet,ratio): return False
        if not close(rec,power/750.0) or inlet<=0 or area+1e-12<4*inlet or ratio+1e-12<4: return False
        if lit(g,c,'nearCentrelineAndWellAftIfPossible') is not True: return False
        if lit(g,c,'iceAccumulationSpaceAboveInlet') is not True: return False
        if lit(g,c,'fullCapacityDischargePipeConnected') is not True: return False
    if selector:
        if lit(g,s,'coolingWaterChestAlternativeArrangementUsed') is not True or len(chests)<2:return False
        if any(lit(g,c,'alternatingCoolingWaterIntakeAndDischarge') is not True for c in chests):return False
    return True

def build131(cid,used=True,substitute=False,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if used:
        if omit!='ballastWaterCoolingArrangement':add_value(g,s,'ballastWaterCoolingArrangement','reserve ballast-water cooling',ex)
        if omit!='reserveCoolingFunction':add_value(g,s,'reserveCoolingFunction','reserve only',ex)
        if omit!='substituteArrangementStatus':add_value(g,s,'substituteArrangementStatus',substitute,ex)
    return g
def oracle131(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); arr=lit(g,s,'ballastWaterCoolingArrangement')
    if arr is None:return True
    return lit(g,s,'substituteArrangementStatus') is False

def build132(cid,ice='IB',f1=.9,f2=1.0,f3=1.1,f4=.18,disp=10000,p0=0,power=None,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceClass':add_value(g,s,'iceClass',ICE[ice],ex)
    vals={'engineOutputFormulaFactorF1':f1,'engineOutputFormulaFactorF2':f2,'engineOutputFormulaFactorF3':f3}
    for t,v in vals.items():
        if omit!=t:add_value(g,s,t,v,ex)
    if omit!='engineOutputFormulaFactorF4':add_value(g,s,'engineOutputFormulaFactorF4',f4,ex,unit_override=UNIT.UNITLESS)
    if omit!='engineOutputFormulaDisplacement':add_value(g,s,'engineOutputFormulaDisplacement',disp,ex,unit_override=UNIT.TON_Metric)
    if omit!='engineOutputFormulaBasePowerP0':add_value(g,s,'engineOutputFormulaBasePowerP0',p0,ex)
    calc=f1*f2*f3*(f4*disp+p0); required=max(calc,740.0)
    if power is None:power=required
    if omit!='maximumContinuousRatingPower':add_value(g,s,'maximumContinuousRatingPower',power,ex)
    return g
def oracle132(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); ic=one(g,s,'iceClass')
    if ic not in {NLTL.iceClassIb,NLTL.iceClassIc}: return ic is not None
    f1=qnum(g,s,'engineOutputFormulaFactorF1');f2=qnum(g,s,'engineOutputFormulaFactorF2');f3=qnum(g,s,'engineOutputFormulaFactorF3');f4=qnum(g,s,'engineOutputFormulaFactorF4',UNIT.UNITLESS)
    d=qnum(g,s,'engineOutputFormulaDisplacement',UNIT.TON_Metric);p0=qnum(g,s,'engineOutputFormulaBasePowerP0');p=qnum(g,s,'maximumContinuousRatingPower')
    if None in (f1,f2,f3,f4,d,p0,p):return False
    required=max(f1*f2*f3*(f4*d+p0),740.0)
    return p+1e-9>=required

def add_mark_common(g,ex,m,name,thickness=6,welded=True,color=NLTL.redReflectingMarkingColour,visible=True):
    add_value(g,m,'markingPlateThickness',thickness,ex,name=name+'Thickness')
    add_value(g,m,'markingWeldedToShipSide',welded,ex)
    add_value(g,m,'reflectingMarkingColour',color,ex)
    add_value(g,m,'markingPlainlyVisibleInIceConditions',visible,ex)
def build133(cid,timber=False,bad=None):
    g,ex,s=new_graph(BASE,cid); add_value(g,s,'timberLoadLineMarkApplicable',timber,ex)
    tri=typed(ex,g,'triangle','warningTriangleMarking'); add_value(g,s,'hasWarningTriangleMarking',tri,ex)
    mark=typed(ex,g,'iceMark','iceClassDraughtMarking'); add_value(g,s,'hasIceClassDraughtMarking',mark,ex)
    tth=4 if bad=='thin' else 9 if bad=='thick' else 6
    col=ex.blue if bad=='color' else NLTL.redReflectingMarkingColour
    add_mark_common(g,ex,tri,'tri',tth,bad!='weld',col,bad!='visible')
    add_mark_common(g,ex,mark,'mark',6,True,NLTL.yellowReflectingMarkingColour,True)
    add_value(g,tri,'warningTriangleSideLength',250 if bad=='side' else 300,ex)
    add_value(g,tri,'verticalOffsetAboveSummerFreshWaterLoadLine',900 if bad=='vertical' else 1000,ex)
    add_value(g,tri,'markingAtOrBelowDeckLine',bad!='deck',ex)
    add_value(g,tri,'warningTriangleUpperEdgeVerticallyAboveIceMark',bad!='upper',ex)
    add_value(g,mark,'draughtMarkAftOffset',500 if bad=='aft' else 540,ex)
    ref=NLTL.timberLoadLineVerticalReference if timber else NLTL.loadLineRingCentreReference
    if bad=='reference': ref=NLTL.loadLineRingCentreReference if timber else NLTL.timberLoadLineVerticalReference
    add_value(g,mark,'draughtMarkAftReferencePoint',ref,ex)
    add_value(g,mark,'letterDimensionsEqualLoadLineMark',bad!='letters',ex)
    if bad=='noTriangle':g.remove((s,NLTL.hasWarningTriangleMarking,tri))
    return g
def oracle133(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None); timber=lit(g,s,'timberLoadLineMarkApplicable')
    if not isinstance(timber,bool):return False
    tri=one(g,s,'hasWarningTriangleMarking');mark=one(g,s,'hasIceClassDraughtMarking')
    if tri is None or mark is None:return False
    for m in (tri,mark):
        t=qnum(g,m,'markingPlateThickness')
        if t is None or not 5<=t<=8:return False
        if lit(g,m,'markingWeldedToShipSide') is not True or lit(g,m,'markingPlainlyVisibleInIceConditions') is not True:return False
        if one(g,m,'reflectingMarkingColour') not in {NLTL.redReflectingMarkingColour,NLTL.yellowReflectingMarkingColour}:return False
    if not close(qnum(g,tri,'warningTriangleSideLength'),300):return False
    if not close(qnum(g,tri,'verticalOffsetAboveSummerFreshWaterLoadLine'),1000):return False
    if lit(g,tri,'markingAtOrBelowDeckLine') is not True or lit(g,tri,'warningTriangleUpperEdgeVerticallyAboveIceMark') is not True:return False
    if not close(qnum(g,mark,'draughtMarkAftOffset'),540) or lit(g,mark,'letterDimensionsEqualLoadLineMark') is not True:return False
    expected=NLTL.timberLoadLineVerticalReference if timber else NLTL.loadLineRingCentreReference
    return one(g,mark,'draughtMarkAftReferencePoint')==expected

ORACLES={'TRF-126':oracle126,'TRF-127':oracle127,'TRF-128':oracle128,'TRF-129':oracle129,'TRF-130':oracle130,'TRF-131':oracle131,'TRF-132':oracle132,'TRF-133':oracle133}
CASES=[]
def ac(req,suffix,expected,rationale,g):CASES.append({'requirement_id':req,'case_id':f'{req}-{suffix}','expected':expected,'rationale':rationale,'graph':g})

for suf,rev,n,exp in [('P01',True,12,'PASS'),('P02',True,15,'PASS'),('P03',False,6,'PASS'),('P04',False,10,'PASS'),('F01',True,11,'FAIL'),('F02',False,5,'FAIL')]:
    ac('TRF-126',suf,exp,'Starting-air consecutive-start threshold branch.',build126(f'TRF-126-{suf}',rev,n))
ac('TRF-126','F03','FAIL','Reversal status missing.',build126('TRF-126-F03',omit='propulsionEngineReversedForAstern'))
ac('TRF-126','F04','FAIL','Consecutive-start capacity missing.',build126('TRF-126-F04',omit='airReceiverConsecutiveStartCapacity'))

ac('TRF-127','P01','PASS','Additional-purpose receiver capacity exceeds required capacity.',build127('TRF-127-P01',True,10,8))
ac('TRF-127','P02','PASS','No additional receiver purpose; conditional obligation inactive.',build127('TRF-127-P02',False,10,8))
ac('TRF-127','F01','FAIL','Additional-purpose capacity is insufficient.',build127('TRF-127-F01',True,7,8))
for i,t in enumerate(['airReceiverServesAdditionalPurpose','airReceiverCapacity','additionalPurposeRequiredAirCapacity'],2):
    ac('TRF-127',f'F0{i}','FAIL',f'Required conditional evidence {t} missing.',build127(f'TRF-127-F0{i}',True,10,8,omit=t))

for suf,ice,rev,t,exp in [('P01','IAS',True,.5,'PASS'),('P02','IAS',True,.4,'PASS'),('P03','IA',True,1,'PASS'),('P04','IAS',False,1,'PASS'),('F01','IAS',True,.51,'FAIL'),('F02','IA',True,1.01,'FAIL')]:
    ac('TRF-128',suf,exp,'Compressor charging-time branch and boundary.',build128(f'TRF-128-{suf}',ice,rev,t))
for i,t in enumerate(['compressorChargeTime','iceClass','propulsionEngineReversalRequiredForAstern'],3):
    ac('TRF-128',f'F0{i}','FAIL',f'Required branch datum {t} missing.',build128(f'TRF-128-F0{i}',omit=t))

ac('TRF-129','P01','PASS','Cooling-water supply secured while navigating in ice.',build129('TRF-129-P01',True,True))
ac('TRF-129','P02','PASS','Not navigating in ice; obligation inactive.',build129('TRF-129-P02',False,None))
ac('TRF-129','F01','FAIL','Cooling-water supply explicitly unsecured in ice.',build129('TRF-129-F01',True,False))
ac('TRF-129','F02','FAIL','Cooling-water security evidence missing in ice.',build129('TRF-129-F02',True,None))
ac('TRF-129','F03','FAIL','Navigation selector missing.',build129('TRF-129-F03',omit='navigatingInIce'))

for suf,kwargs,exp,rat in [
('P01',{},'PASS','Canonical single inlet chest.'),
('P02',{'alt':True},'PASS','Two-chest alternating exception when volume/height requirements cannot be met.'),
('F01',{'bad':'recommended'},'FAIL','Recommended nominal chest-volume calculation inconsistent with power/750.'),
('F02',{'bad':'ratio'},'FAIL','Strainer open area below four times inlet-pipe area.'),
('F03',{'bad':'location'},'FAIL','Sea inlet location requirement not met.'),
('F04',{'bad':'space'},'FAIL','No ice-accumulation space above inlet.'),
('F05',{'bad':'discharge'},'FAIL','Full-capacity discharge pipe absent.'),
('F06',{'bad':'noChest'},'FAIL','No inlet chest represented.'),
('F07',{'alt':True,'bad':'oneChest'},'FAIL','Alternative branch has fewer than two chests.'),
('F08',{'alt':True,'bad':'altFlag'},'FAIL','Alternative branch selector true but alternative-use flag false.'),
('F09',{'alt':True,'bad':'alternating'},'FAIL','Alternative branch lacks alternating intake/discharge on one chest.'),
('F10',{'omit_selector':True},'FAIL','Mandatory exception selector evidence missing.')]:
    ac('TRF-130',suf,exp,rat,build130(f'TRF-130-{suf}',**kwargs))

ac('TRF-131','P01','PASS','No ballast-water cooling arrangement used.',build131('TRF-131-P01',False))
ac('TRF-131','P02','PASS','Ballast-water cooling represented as reserve, not substitute.',build131('TRF-131-P02',True,False))
ac('TRF-131','F01','FAIL','Ballast-water cooling incorrectly represented as substitute inlet chest.',build131('TRF-131-F01',True,True))
ac('TRF-131','F02','FAIL','Used ballast-water arrangement lacks substitute-status evidence.',build131('TRF-131-F02',True,False,omit='substituteArrangementStatus'))

# Annex II: canonical arithmetic and 740 kW floor.
g=build132('TRF-132-P01','IB');ac('TRF-132','P01','PASS','IB power equals formula-derived minimum.',g)
g=build132('TRF-132-P02','IC',f1=1.0,f2=.9,f3=1.0,f4=.11,disp=30000,p0=2100);ac('TRF-132','P02','PASS','IC power equals formula-derived minimum.',g)
g=build132('TRF-132-P03','IB',f1=.9,f2=.9,f3=1.0,f4=.01,disp=1000,p0=100,power=740);ac('TRF-132','P03','PASS','740 kW statutory floor governs.',g)
g=build132('TRF-132-P04','IA',power=100);ac('TRF-132','P04','PASS','Annex II IB/IC power constraint non-applicable to IA.',g)
basecalc=.9*1.0*1.1*(.18*10000+0)
ac('TRF-132','F01','FAIL','Power below formula-derived minimum.',build132('TRF-132-F01','IB',power=basecalc-1))
ac('TRF-132','F02','FAIL','Power below 740 kW floor.',build132('TRF-132-F02','IC',f1=.9,f2=.9,f3=1,f4=.01,disp=1000,p0=100,power=739))
ac('TRF-132','F03','FAIL','Formula factor F4 missing.',build132('TRF-132-F03','IB',omit='engineOutputFormulaFactorF4'))
ac('TRF-132','F04','FAIL','Engine power result missing.',build132('TRF-132-F04','IB',omit='maximumContinuousRatingPower'))

for suf,timber,bad,exp,rat in [
('P01',False,None,'PASS','Annex III load-line-ring reference branch.'),
('P02',True,None,'PASS','Annex III timber-load-line reference branch.'),
('F01',False,'thin','FAIL','Marking plate thinner than 5 mm.'),
('F02',False,'thick','FAIL','Marking plate thicker than 8 mm.'),
('F03',False,'color','FAIL','Non-red/yellow reflecting colour.'),
('F04',False,'weld','FAIL','Warning triangle not welded to ship side.'),
('F05',False,'visible','FAIL','Marking not plainly visible in ice.'),
('F06',False,'side','FAIL','Warning-triangle side is not 300 mm.'),
('F07',False,'vertical','FAIL','Warning triangle not 1000 mm above summer fresh-water load line.'),
('F08',False,'deck','FAIL','Warning triangle is not constrained at/below deck line.'),
('F09',False,'aft','FAIL','ICE draught mark offset is not 540 mm.'),
('F10',True,'reference','FAIL','Wrong aft reference for timber-load-line branch.'),
('F11',False,'upper','FAIL','Triangle upper edge not vertically above ICE mark.'),
('F12',False,'letters','FAIL','ICE-mark letter dimensions do not match load-line mark.'),
('F13',False,'noTriangle','FAIL','Warning-triangle relationship missing.')]:
    ac('TRF-133',suf,exp,rat,build133(f'TRF-133-{suf}',timber,bad))

assert len(CASES)==67,len(CASES)

MANIFEST='traficom_batch_j_manifest.jsonl'; LOCK='traficom_batch_j_fixture_lock.json'; VALIDATOR='validate_traficom_batch_j.py'
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='TRAFICOM Behavioral Benchmark Batch J',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='TRF')
