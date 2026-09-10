
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

BASE='https://w3id.org/nltl/benchmark/imo-batch-b/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-014','IMO-016','IMO-017','IMO-018','IMO-019','IMO-021']
MODES={'IMO-014':'DIRECT_STATIC','IMO-016':'DIRECT_STATIC','IMO-017':'DIRECT_STATIC','IMO-018':'DIRECT_STATIC','IMO-019':'DIRECT_CALCULATION','IMO-021':'DIRECT_STATIC'}
CLAUSES={'IMO-014':'Part I-A 1.3.1','IMO-016':'Part I-A 1.3.5','IMO-017':'Part I-A 1.3.6','IMO-018':'Part I-A 1.3.7','IMO-019':'Part I-A 1.4.2','IMO-021':'Part I-A 1.5'}

def build014(cid,applies=True,present=True,status=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='polarCodeApplies':add_value(g,s,'polarCodeApplies',applies,ex)
    if present is not None and omit!='polarShipCertificatePresent':add_value(g,s,'polarShipCertificatePresent',present,ex)
    if status is not None and omit!='polarShipCertificateStatus':add_value(g,s,'polarShipCertificateStatus',status,ex)
    return g
def oracle014(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);a=lit(g,s,'polarCodeApplies')
    if not isinstance(a,bool):return False
    if not a:return True
    return lit(g,s,'polarShipCertificatePresent') is True and lit(g,s,'polarShipCertificateStatus') is True

def build016(cid,lang='English',translation=None,model=NLTL.appendixIPolarShipCertificateModel,omit=None):
    g,ex,s=new_graph(BASE,cid)
    cert=typed(ex,g,'certificate','polarShipCertificateForm')
    if omit!='hasPolarShipCertificate':add_value(g,s,'hasPolarShipCertificate',cert,ex)
    if omit!='certificateFormModel':add_value(g,cert,'certificateFormModel',model,ex)
    if omit!='certificateLanguage':add_value(g,cert,'certificateLanguage',lang,ex)
    if translation is not None and omit!='approvedTranslationPresent':add_value(g,cert,'approvedTranslationPresent',translation,ex)
    return g
def oracle016(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);cert=one(g,s,'hasPolarShipCertificate')
    if cert is None:return False
    if one(g,cert,'certificateFormModel')!=NLTL.appendixIPolarShipCertificateModel:return False
    lang=lit(g,cert,'certificateLanguage')
    if not isinstance(lang,str) or not lang.strip():return False
    if lang.strip().lower() not in {'english','french','spanish'}:
        return lit(g,cert,'approvedTranslationPresent') is True
    return True

def add_sched_record(g,ex,sched,name,typ,date):
    rec=typed(ex,g,name,'certificateScheduleDateRecord');add_value(g,sched,'hasCertificateScheduleDateRecord',rec,ex)
    add_value(g,rec,'certificateScheduleDateType',typ,ex);add_value(g,rec,'certificateScheduleDate',date,ex)
    return rec
def build017(cid,dates=('2030-01-01','2028-06-01','2028-07-01'),bad=None):
    g,ex,s=new_graph(BASE,cid)
    cert=typed(ex,g,'certificate','polarShipCertificateForm')
    if bad!='noCert':add_value(g,s,'hasPolarShipCertificate',cert,ex)
    sched=typed(ex,g,'solasSchedule','solasCertificateSchedule')
    if bad!='noSchedule':add_value(g,s,'hasSolasCertificateSchedule',sched,ex)
    validity,survey,endorse=dates
    add_value(g,s,'polarCertificateValidityDates',validity if bad!='mismatchValidity' else '2030-01-02',ex)
    add_value(g,s,'surveyDates',survey,ex);add_value(g,s,'endorsementDates',endorse,ex)
    if bad!='noSchedule':
        add_sched_record(g,ex,sched,'validityRecord',NLTL.validityDateCategory,validity)
        if bad!='missingSurveyRecord':add_sched_record(g,ex,sched,'surveyRecord',NLTL.surveyDateCategory,survey)
        add_sched_record(g,ex,sched,'endorsementRecord',NLTL.endorsementDateCategory,endorse)
    supp=typed(ex,g,'supplement','polarCertificateSupplement')
    if bad!='noSupplement':
        add_value(g,s,'hasPolarCertificateSupplement',supp,ex);add_value(g,s,'polarCertificateSupplementPresent',True,ex)
        recs=typed(ex,g,'requiredEquipment','requiredEquipmentRecords')
        if bad!='noEquipment':add_value(g,supp,'hasRequiredEquipmentRecords',recs,ex)
    return g
def oracle017(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if one(g,s,'hasPolarShipCertificate') is None:return False
    sched=one(g,s,'hasSolasCertificateSchedule')
    if sched is None:return False
    wanted={NLTL.validityDateCategory:lit(g,s,'polarCertificateValidityDates'),
            NLTL.surveyDateCategory:lit(g,s,'surveyDates'),
            NLTL.endorsementDateCategory:lit(g,s,'endorsementDates')}
    if any(v is None for v in wanted.values()):return False
    found={}
    for rec in g.objects(sched,NLTL.hasCertificateScheduleDateRecord):
        typ=one(g,rec,'certificateScheduleDateType');date=lit(g,rec,'certificateScheduleDate')
        if typ is not None and date is not None:found[typ]=date
    if any(found.get(k)!=v for k,v in wanted.items()):return False
    supp=one(g,s,'hasPolarCertificateSupplement')
    return supp is not None and lit(g,s,'polarCertificateSupplementPresent') is True and one(g,supp,'hasRequiredEquipmentRecords') is not None

def build018(cid,app=True,ref=True,approved=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='iceCapabilityMethodologyApplicable':add_value(g,s,'iceCapabilityMethodologyApplicable',app,ex)
    if ref is not None and omit!='certificateMethodologyReferencePresent':add_value(g,s,'certificateMethodologyReferencePresent',ref,ex)
    if approved is not None and omit!='administrationAcceptanceStatus':add_value(g,s,'administrationAcceptanceStatus',approved,ex)
    return g
def oracle018(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);a=lit(g,s,'iceCapabilityMethodologyApplicable')
    if not isinstance(a,bool):return False
    if not a:return True
    return lit(g,s,'certificateMethodologyReferencePresent') is True and lit(g,s,'administrationAcceptanceStatus') is True

def build019(cid,oper=True,mdlt=-20,pst=-30,functional=True,omit=None):
    g,ex,s=new_graph(BASE,cid)
    if omit!='shipOperatesInLowAirTemperature':add_value(g,s,'shipOperatesInLowAirTemperature',oper,ex)
    if omit!='lowestMdlt':add_value(g,s,'lowestMdlt',mdlt,ex)
    if omit!='polarServiceTemperature':add_value(g,s,'polarServiceTemperature',pst,ex)
    if functional is not None and omit!='requiredSystemsFunctionalAtPst':add_value(g,s,'requiredSystemsFunctionalAtPst',functional,ex)
    return g
def oracle019(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);op=lit(g,s,'shipOperatesInLowAirTemperature')
    if not isinstance(op,bool):return False
    if not op:return True
    m=qnum(g,s,'lowestMdlt');p=qnum(g,s,'polarServiceTemperature')
    return m is not None and p is not None and p<=m-10+1e-12 and lit(g,s,'requiredSystemsFunctionalAtPst') is True

def build021(cid,bad=None):
    g,ex,s=new_graph(BASE,cid)
    fields={'operationalAssessmentPresent':True,'assessedIceOperation':True,'assessedHighLatitude':True,'assessedAbandonment':True,'assessedCodeHazards':True,'assessedAdditionalHazards':True}
    for t,v in fields.items():
        if bad==t+'Missing':continue
        add_value(g,s,t,False if bad==t else v,ex)
    if bad!='assessedLowAirTemperatureMissing':add_value(g,s,'assessedLowAirTemperature',-20,ex)
    return g
def oracle021(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if lit(g,s,'operationalAssessmentPresent') is not True:return False
    if qnum(g,s,'assessedLowAirTemperature') is None:return False
    for t in ['assessedIceOperation','assessedHighLatitude','assessedAbandonment','assessedCodeHazards','assessedAdditionalHazards']:
        if lit(g,s,t) is not True:return False
    return True

ORACLES={'IMO-014':oracle014,'IMO-016':oracle016,'IMO-017':oracle017,'IMO-018':oracle018,'IMO-019':oracle019,'IMO-021':oracle021}
CASES=[]
def ac(r,s,e,rat,g):CASES.append({'requirement_id':r,'case_id':f'{r}-{s}','expected':e,'rationale':rat,'graph':g})

ac('IMO-014','P01','PASS','Applicable ship carries valid Polar Ship Certificate.',build014('IMO-014-P01'))
ac('IMO-014','P02','PASS','Polar Code not applicable; certificate obligation inactive.',build014('IMO-014-P02',False,None,None))
ac('IMO-014','F01','FAIL','Applicable ship lacks certificate.',build014('IMO-014-F01',True,False,True))
ac('IMO-014','F02','FAIL','Applicable ship certificate is not valid.',build014('IMO-014-F02',True,True,False))
ac('IMO-014','F03','FAIL','Polar-Code applicability evidence missing.',build014('IMO-014-F03',omit='polarCodeApplies'))

for suf,lang,tr,model,exp,rat in [
('P01','English',None,NLTL.appendixIPolarShipCertificateModel,'PASS','Appendix I model certificate in English.'),
('P02','French',None,NLTL.appendixIPolarShipCertificateModel,'PASS','Appendix I model certificate in French.'),
('P03','German',True,NLTL.appendixIPolarShipCertificateModel,'PASS','Non-approved-language original includes approved-language translation.'),
('F01','German',False,NLTL.appendixIPolarShipCertificateModel,'FAIL','Non-approved-language original lacks required translation.'),
('F02','English',None,NLTL.certificateFormModelValue,'FAIL','Certificate does not use Appendix I model.')]:
    ac('IMO-016',suf,exp,rat,build016(f'IMO-016-{suf}',lang,tr,model))
ac('IMO-016','F03','FAIL','Certificate language missing.',build016('IMO-016-F03',omit='certificateLanguage'))
ac('IMO-016','F04','FAIL','Ship-to-certificate path missing.',build016('IMO-016-F04',omit='hasPolarShipCertificate'))

ac('IMO-017','P01','PASS','Polar certificate dates match SOLAS schedule and supplement records equipment.',build017('IMO-017-P01'))
ac('IMO-017','F01','FAIL','Polar validity date mismatches SOLAS schedule.',build017('IMO-017-F01',bad='mismatchValidity'))
ac('IMO-017','F02','FAIL','SOLAS schedule relationship missing.',build017('IMO-017-F02',bad='noSchedule'))
ac('IMO-017','F03','FAIL','Polar certificate supplement missing.',build017('IMO-017-F03',bad='noSupplement'))
ac('IMO-017','F04','FAIL','Required equipment records missing from supplement.',build017('IMO-017-F04',bad='noEquipment'))
ac('IMO-017','F05','FAIL','Survey-date schedule record missing.',build017('IMO-017-F05',bad='missingSurveyRecord'))
ac('IMO-017','F06','FAIL','Polar Ship Certificate relationship missing.',build017('IMO-017-F06',bad='noCert'))

ac('IMO-018','P01','PASS','Applicable ice-capability methodology is referenced and accepted.',build018('IMO-018-P01'))
ac('IMO-018','P02','PASS','Methodology not applicable; conditional reference obligation inactive.',build018('IMO-018-P02',False,None,None))
ac('IMO-018','F01','FAIL','Applicable methodology reference missing.',build018('IMO-018-F01',True,False,True))
ac('IMO-018','F02','FAIL','Administration acceptance absent.',build018('IMO-018-F02',True,True,False))
ac('IMO-018','F03','FAIL','Applicability selector missing.',build018('IMO-018-F03',omit='iceCapabilityMethodologyApplicable'))

ac('IMO-019','P01','PASS','Low-air-temperature ship has compliant PST and functional systems.',build019('IMO-019-P01'))
ac('IMO-019','P02','PASS','PST more conservative than required.',build019('IMO-019-P02',True,-20,-35,True))
ac('IMO-019','P03','PASS','Ship not operating in low air temperature; conditional requirement inactive.',build019('IMO-019-P03',False,-5,-15,None))
ac('IMO-019','F01','FAIL','PST is too warm relative to MDLT.',build019('IMO-019-F01',True,-20,-29.9,True))
ac('IMO-019','F02','FAIL','Required systems not functional at PST.',build019('IMO-019-F02',True,-20,-30,False))
ac('IMO-019','F03','FAIL','PST missing for applicable ship.',build019('IMO-019-F03',omit='polarServiceTemperature'))
ac('IMO-019','F04','FAIL','Lowest MDLT missing for applicable ship.',build019('IMO-019-F04',omit='lowestMdlt'))

ac('IMO-021','P01','PASS','Operational assessment covers all frozen R13 hazard domains.',build021('IMO-021-P01'))
for i,bad in enumerate(['operationalAssessmentPresent','assessedIceOperation','assessedHighLatitude','assessedAbandonment','assessedCodeHazards','assessedAdditionalHazards'],1):
    ac('IMO-021',f'F0{i}','FAIL',f'Operational assessment field {bad} not satisfied.',build021(f'IMO-021-F0{i}',bad=bad))
ac('IMO-021','F07','FAIL','Low-air-temperature assessment quantity missing.',build021('IMO-021-F07',bad='assessedLowAirTemperatureMissing'))

assert len(CASES)==39,len(CASES)
MANIFEST='imo_batch_b_manifest.jsonl';LOCK='imo_batch_b_fixture_lock.json';VALIDATOR='validate_imo_batch_b.py'
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Behavioral Benchmark Batch B',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
