
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

BASE='https://w3id.org/nltl/benchmark/imo-batch-c/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-022','IMO-023','IMO-024','IMO-025','IMO-026','IMO-027','IMO-028','IMO-029','IMO-030']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={'IMO-022':'Part I-A 2.2.2','IMO-023':'Part I-A 2.2.3','IMO-024':'Part I-A 2.2.4','IMO-025':'Part I-A 2.3.1',
'IMO-026':'Part I-A 2.3.2','IMO-027':'Part I-A 2.3.3','IMO-028':'Part I-A 2.3.4','IMO-029':'Part I-A 2.3.5','IMO-030':'Part I-A 2.3.6'}

def build022(cid,manual=True,cap=True,lim=True,ref='Part I-A 1.5 operational assessment',omit=None):
    g,ex,s=new_graph(BASE,cid)
    vals={'polarWaterOperationalManualPresent':manual,'capabilitiesSectionPresent':cap,'limitationsSectionPresent':lim,'operationalAssessmentReference':ref}
    for t,v in vals.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def oracle022(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    ref=lit(g,s,'operationalAssessmentReference')
    return lit(g,s,'polarWaterOperationalManualPresent') is True and lit(g,s,'capabilitiesSectionPresent') is True and lit(g,s,'limitationsSectionPresent') is True and isinstance(ref,str) and bool(ref.strip())

def build023(cid,normal=True,avoid=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='normalOperationProcedurePresent':add_value(g,s,'normalOperationProcedurePresent',normal,ex)
    if omit!='capabilityExceedanceAvoidanceProcedurePresent':add_value(g,s,'capabilityExceedanceAvoidanceProcedurePresent',avoid,ex)
    return g
def oracle023(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    return lit(g,s,'normalOperationProcedurePresent') is True and lit(g,s,'capabilityExceedanceAvoidanceProcedurePresent') is True

def single_bool(cid,term,value=True,omit=False):
    g,ex,s=new_graph(BASE,cid)
    if not omit:add_value(g,s,term,value,ex)
    return g
def bool_oracle(term):
    return lambda g: lit(g,next(g.subjects(RDF.type,NLTL.ship),None),term) is True

def build026(cid,app=True,present=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceCapabilityMethodologyApplicable':add_value(g,s,'iceCapabilityMethodologyApplicable',app,ex)
    if present is not None and omit!='polarWaterOperationalManualIceCapabilityMethodologyPresent':add_value(g,s,'polarWaterOperationalManualIceCapabilityMethodologyPresent',present,ex)
    return g
def oracle026(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);a=lit(g,s,'iceCapabilityMethodologyApplicable')
    if not isinstance(a,bool):return False
    return True if not a else lit(g,s,'polarWaterOperationalManualIceCapabilityMethodologyPresent') is True

def build027(cid,bad=None):
    g,ex,s=new_graph(BASE,cid)
    strings={'voyageLimitAvoidance':'avoid ice/temperature limits','environmentalForecastArrangements':'receive environmental forecasts','informationLimitationMeasures':'address hydrographic meteorological navigational limitations','requiredEquipmentOperation':'operate equipment required by other Code chapters'}
    for t,v in strings.items():
        if bad==t+'Missing':continue
        add_value(g,s,t,'' if bad==t else v,ex)
    for t in ['environmentalFunctionalityMeasures','polarWaterOperationalManualRiskProcedureCoverage']:
        if bad==t+'Missing':continue
        add_value(g,s,t,False if bad==t else True,ex)
    return g
def oracle027(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    for t in ['voyageLimitAvoidance','environmentalForecastArrangements','informationLimitationMeasures','requiredEquipmentOperation']:
        v=lit(g,s,t)
        if not isinstance(v,str) or not v.strip():return False
    return lit(g,s,'environmentalFunctionalityMeasures') is True and lit(g,s,'polarWaterOperationalManualRiskProcedureCoverage') is True

def build028(cid,strengthened=True,emergency=True,entrap=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='shipIceStrengthened':add_value(g,s,'shipIceStrengthened',strengthened,ex)
    if emergency is not None and omit!='emergencyProviderContactProcedurePresent':add_value(g,s,'emergencyProviderContactProcedurePresent',emergency,ex)
    if entrap is not None and omit!='prolongedEntrapmentProcedurePresent':add_value(g,s,'prolongedEntrapmentProcedurePresent',entrap,ex)
    return g
def oracle028(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);st=lit(g,s,'shipIceStrengthened')
    if not isinstance(st,bool):return False
    if lit(g,s,'emergencyProviderContactProcedurePresent') is not True:return False
    return lit(g,s,'prolongedEntrapmentProcedurePresent') is True if st else True

def build030(cid,app=True,monitor=True,escort=True,ind='independent-operation limitations',esc='escorted-operation limitations',omit=None):
    g,ex,s=new_graph(BASE,cid)
    vals={'iceOperationApplicable':app,'iceSafetyMonitoringProcedurePresent':monitor,'escortRequirementsPresent':escort,'independentOperationLimits':ind,'escortedOperationLimits':esc}
    for t,v in vals.items():
        if omit!=t and v is not None:add_value(g,s,t,v,ex)
    return g
def oracle030(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);a=lit(g,s,'iceOperationApplicable')
    if not isinstance(a,bool):return False
    if not a:return True
    if lit(g,s,'iceSafetyMonitoringProcedurePresent') is not True or lit(g,s,'escortRequirementsPresent') is not True:return False
    for t in ['independentOperationLimits','escortedOperationLimits']:
        v=lit(g,s,t)
        if not isinstance(v,str) or not v.strip():return False
    return True

ORACLES={'IMO-022':oracle022,'IMO-023':oracle023,'IMO-024':bool_oracle('polarIncidentProcedurePresent'),'IMO-025':bool_oracle('polarWaterOperationalManualPresentOnBoard'),'IMO-026':oracle026,'IMO-027':oracle027,'IMO-028':oracle028,'IMO-029':bool_oracle('exceedanceResponseProcedurePresent'),'IMO-030':oracle030}
CASES=[]
def ac(r,s,e,rat,g):CASES.append({'requirement_id':r,'case_id':f'{r}-{s}','expected':e,'rationale':rat,'graph':g})

ac('IMO-022','P01','PASS','PWOM contains capabilities, limitations and operational-assessment reference.',build022('IMO-022-P01'))
ac('IMO-022','F01','FAIL','PWOM presence flag false.',build022('IMO-022-F01',manual=False))
ac('IMO-022','F02','FAIL','Capabilities section absent.',build022('IMO-022-F02',cap=False))
ac('IMO-022','F03','FAIL','Limitations section absent.',build022('IMO-022-F03',lim=False))
ac('IMO-022','F04','FAIL','Operational-assessment reference missing.',build022('IMO-022-F04',omit='operationalAssessmentReference'))

ac('IMO-023','P01','PASS','Normal-operation and capability-exceedance-avoidance procedures present.',build023('IMO-023-P01'))
ac('IMO-023','F01','FAIL','Normal-operation procedure absent.',build023('IMO-023-F01',normal=False))
ac('IMO-023','F02','FAIL','Capability-exceedance avoidance procedure absent.',build023('IMO-023-F02',avoid=False))
ac('IMO-023','F03','FAIL','Normal-operation procedure evidence missing.',build023('IMO-023-F03',omit='normalOperationProcedurePresent'))

ac('IMO-024','P01','PASS','Polar-water incident procedure present.',single_bool('IMO-024-P01','polarIncidentProcedurePresent',True))
ac('IMO-024','F01','FAIL','Polar-water incident procedure false.',single_bool('IMO-024-F01','polarIncidentProcedurePresent',False))
ac('IMO-024','F02','FAIL','Polar-water incident procedure missing.',single_bool('IMO-024-F02','polarIncidentProcedurePresent',omit=True))

ac('IMO-025','P01','PASS','PWOM carried on board.',single_bool('IMO-025-P01','polarWaterOperationalManualPresentOnBoard',True))
ac('IMO-025','F01','FAIL','PWOM not carried on board.',single_bool('IMO-025-F01','polarWaterOperationalManualPresentOnBoard',False))
ac('IMO-025','F02','FAIL','PWOM-on-board evidence missing.',single_bool('IMO-025-F02','polarWaterOperationalManualPresentOnBoard',omit=True))

ac('IMO-026','P01','PASS','Applicable ice-capability methodology included in PWOM.',build026('IMO-026-P01'))
ac('IMO-026','P02','PASS','Methodology not applicable; conditional section inactive.',build026('IMO-026-P02',False,None))
ac('IMO-026','F01','FAIL','Applicable methodology section absent.',build026('IMO-026-F01',True,False))
ac('IMO-026','F02','FAIL','Methodology applicability evidence missing.',build026('IMO-026-F02',omit='iceCapabilityMethodologyApplicable'))

ac('IMO-027','P01','PASS','Risk-based PWOM procedure coverage contains every frozen R13 element.',build027('IMO-027-P01'))
for i,t in enumerate(['voyageLimitAvoidance','environmentalForecastArrangements','informationLimitationMeasures','requiredEquipmentOperation','environmentalFunctionalityMeasures','polarWaterOperationalManualRiskProcedureCoverage'],1):
    ac('IMO-027',f'F0{i}','FAIL',f'PWOM risk-procedure element {t} not satisfied.',build027(f'IMO-027-F0{i}',bad=t))

ac('IMO-028','P01','PASS','Ice-strengthened ship includes emergency-provider and prolonged-entrapment procedures.',build028('IMO-028-P01',True,True,True))
ac('IMO-028','P02','PASS','Non-ice-strengthened ship includes emergency-provider procedure; entrapment branch inactive.',build028('IMO-028-P02',False,True,None))
ac('IMO-028','F01','FAIL','Emergency-provider contact procedure absent.',build028('IMO-028-F01',True,False,True))
ac('IMO-028','F02','FAIL','Ice-strengthened ship lacks prolonged-entrapment procedure.',build028('IMO-028-F02',True,True,False))
ac('IMO-028','F03','FAIL','Ice-strengthening selector missing.',build028('IMO-028-F03',omit='shipIceStrengthened'))

ac('IMO-029','P01','PASS','Exceedance-response procedure present.',single_bool('IMO-029-P01','exceedanceResponseProcedurePresent',True))
ac('IMO-029','F01','FAIL','Exceedance-response procedure false.',single_bool('IMO-029-F01','exceedanceResponseProcedurePresent',False))
ac('IMO-029','F02','FAIL','Exceedance-response procedure missing.',single_bool('IMO-029-F02','exceedanceResponseProcedurePresent',omit=True))

ac('IMO-030','P01','PASS','Applicable ice operation has monitoring, escort requirements and both operating-mode limitations.',build030('IMO-030-P01'))
ac('IMO-030','P02','PASS','Ice operation not applicable; conditional procedure requirement inactive.',build030('IMO-030-P02',False,None,None,None,None))
ac('IMO-030','F01','FAIL','Ice-operation monitoring procedure absent.',build030('IMO-030-F01',True,False,True))
ac('IMO-030','F02','FAIL','Escort/icebreaker requirements absent.',build030('IMO-030-F02',True,True,False))
ac('IMO-030','F03','FAIL','Independent-operation limitations missing.',build030('IMO-030-F03',omit='independentOperationLimits'))
ac('IMO-030','F04','FAIL','Escorted-operation limitations missing.',build030('IMO-030-F04',omit='escortedOperationLimits'))
ac('IMO-030','F05','FAIL','Ice-operation applicability selector missing.',build030('IMO-030-F05',omit='iceOperationApplicable'))

assert len(CASES)==41,len(CASES)
MANIFEST='imo_batch_c_manifest.jsonl';LOCK='imo_batch_c_fixture_lock.json';VALIDATOR='validate_imo_batch_c.py'
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Behavioral Benchmark Batch C',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
