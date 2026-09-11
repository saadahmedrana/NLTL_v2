
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
    for p in [ROOT/'rdf'/family,ROOT/'specifications'/family/'systematic',ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:
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
        sp=ROOT/'specifications'/family/'systematic'/f'{req}.json'
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
        p=ROOT/'specifications'/family/'systematic'/f'{req}.json'; frozen[str(p.relative_to(ROOT))]=sha256(p)
    lp.write_text(json.dumps({
        'benchmark':batch_label,'source_lock_id':INDEX['sourceLockId'],'source_id':source_id,
        'requirements':reqs,'requirement_count':len(reqs),'case_count':len(cases),
        'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,
        'frozen_files':frozen
    },indent=2)+'\n')
    print('\nFrozen validation'); assert validate_batch(manifest_name,lock_name,oracles,True)




BASE='https://w3id.org/nltl/benchmark/imo26-batch-b/'
SOURCE_ID='SRC-IMO26-SUPPLEMENT'
REQS=['IMO26-015','IMO26-016','IMO26-017','IMO26-018']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={
 'IMO26-015':'MSC.538(107) Amendment 5 - Chapter 11 applicability',
 'IMO26-016':'Chapter 11-1 applicability',
 'IMO26-017':'11-1.2',
 'IMO26-018':'11-1.3.1-11-1.3.9',
}

def case(req,cid,expected,graph,rationale):
    return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid): return new_graph(BASE,cid)
def vals(g,s,term): return list(g.objects(s,NLTL[term]))

def b015(cid,cert=True,app=True,omit=None):
    g,ex,s=shipg(cid)
    for t,v in {'solasChapterICertified':cert,'polarCodeChapter11Applicable':app}.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o015(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    cert=lit(g,s,'solasChapterICertified');app=lit(g,s,'polarCodeChapter11Applicable')
    return cert is not None and app is not None and app is cert

def b016(cid,polar=True,stype='fishing_vessel',length=24,gt=300,trade=False,app=True,omit=None):
    g,ex,s=shipg(cid)
    data={'shipOperatesInPolarWaters':polar,'shipType':stype,'lengthOverall':length,'grossTonnage':gt,
          'engagedInTrade':trade,'polarCodeChapter11Dash1Applicable':app}
    for t,v in data.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def calc_ch11_1(g,s):
    polar=lit(g,s,'shipOperatesInPolarWaters')
    if polar is None:return None
    if polar is False:return False
    st=lit(g,s,'shipType')
    if st is None:return None
    if st=='fishing_vessel':
        L=qnum(g,s,'lengthOverall')
        return None if L is None else L>=24
    if st=='pleasure_yacht':
        gt=qnum(g,s,'grossTonnage');tr=lit(g,s,'engagedInTrade')
        return None if gt is None or tr is None else (gt>=300 and tr is False)
    if st=='cargo_ship':
        gt=qnum(g,s,'grossTonnage')
        return None if gt is None else (gt>=300 and gt<500)
    return False
def o016(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    expected=calc_ch11_1(g,s);actual=lit(g,s,'polarCodeChapter11Dash1Applicable')
    return expected is not None and actual is not None and actual is expected

def b017(cid,app=True,plan=True,hazards=('ice','remoteness'),coverage=(True,True),omit=None):
    g,ex,s=shipg(cid)
    if omit!='polarCodeChapter11Dash1Applicable':add_value(g,s,'polarCodeChapter11Dash1Applicable',app,ex)
    if omit!='voyagePlanPresent':add_value(g,s,'voyagePlanPresent',plan,ex)
    if omit!='intendedVoyageHazard':
        for h in hazards:add_value(g,s,'intendedVoyageHazard',h,ex)
    if omit!='voyagePlanCoverage':
        for c in coverage:add_value(g,s,'voyagePlanCoverage',c,ex)
    return g
def o017(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    app=lit(g,s,'polarCodeChapter11Dash1Applicable')
    if app is None:return False
    if app is False:return True
    if lit(g,s,'voyagePlanPresent') is not True:return False
    hazards=vals(g,s,'intendedVoyageHazard');cov=vals(g,s,'voyagePlanCoverage')
    if not hazards:return True
    return bool(cov) and all(x.toPython() is True for x in cov)

def b018(cid,app=True,sms=True,coverage=True,procedure=True,omit=None):
    g,ex,s=shipg(cid)
    data={'polarCodeChapter11Dash1Applicable':app,'safetyManagementSystemImplemented':sms,
          'voyagePlanningTopicCoverage':coverage,'documentedPolarOperationProcedurePresent':procedure}
    for t,v in data.items():
        if omit!=t:add_value(g,s,t,v,ex)
    return g
def o018(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if s is None:return False
    app=lit(g,s,'polarCodeChapter11Dash1Applicable')
    if app is None:return False
    if app is False:return True
    sms=lit(g,s,'safetyManagementSystemImplemented')
    coverage=lit(g,s,'voyagePlanningTopicCoverage')
    if sms is None or coverage is None:return False
    if coverage is not True:return False
    if sms is False and lit(g,s,'documentedPolarOperationProcedurePresent') is not True:return False
    return True

ORACLES={'IMO26-015':o015,'IMO26-016':o016,'IMO26-017':o017,'IMO26-018':o018}
CASES=[]
def add(req,suffix,exp,builder,kw,rat):
    cid=f'{req}-B-{suffix}'
    CASES.append(case(req,cid,exp,builder(cid,**kw),rat))

for x in [
 ('P01','PASS',{},'SOLAS chapter I certified ship has Chapter 11 applicable.'),
 ('P02','PASS',{'cert':False,'app':False},'Non-SOLAS-chapter-I-certified ship has Chapter 11 not applicable.'),
 ('F01','FAIL',{'cert':True,'app':False},'Certified ship incorrectly marks Chapter 11 not applicable.'),
 ('F02','FAIL',{'cert':False,'app':True},'Non-certified ship incorrectly marks Chapter 11 applicable.'),
 ('F03','FAIL',{'omit':'polarCodeChapter11Applicable'},'Chapter 11 applicability result missing.'),
]: add('IMO26-015',x[0],x[1],b015,x[2],x[3])

for x in [
 ('P01','PASS',{'stype':'fishing_vessel','length':24,'app':True},'Polar-water fishing vessel exactly at 24 m boundary is applicable.'),
 ('P02','PASS',{'stype':'fishing_vessel','length':23.99,'app':False},'Polar-water fishing vessel below 24 m is outside Chapter 11-1.'),
 ('P03','PASS',{'stype':'pleasure_yacht','gt':300,'trade':False,'app':True},'Polar-water non-trading pleasure yacht exactly at 300 GT boundary.'),
 ('P04','PASS',{'stype':'pleasure_yacht','gt':299.9,'trade':False,'app':False},'Pleasure yacht below 300 GT is outside Chapter 11-1.'),
 ('P05','PASS',{'stype':'pleasure_yacht','gt':300,'trade':True,'app':False},'Pleasure yacht engaged in trade is outside this Chapter 11-1 branch.'),
 ('P06','PASS',{'stype':'cargo_ship','gt':300,'app':True},'Polar-water cargo ship exactly at 300 GT lower boundary.'),
 ('P07','PASS',{'stype':'cargo_ship','gt':499.9,'app':True},'Polar-water cargo ship below 500 GT upper boundary.'),
 ('P08','PASS',{'stype':'cargo_ship','gt':500,'app':False},'Cargo ship at 500 GT is outside the <500 GT branch.'),
 ('P09','PASS',{'polar':False,'stype':'fishing_vessel','length':30,'app':False},'Ship not operating in polar waters is outside Chapter 11-1.'),
 ('P10','PASS',{'stype':'other','app':False},'Other ship type is outside the three Chapter 11-1 alternatives.'),
 ('F01','FAIL',{'stype':'fishing_vessel','length':24,'app':False},'Applicable polar-water fishing vessel marked non-applicable.'),
 ('F02','FAIL',{'polar':False,'stype':'fishing_vessel','length':30,'app':True},'Non-polar-water ship incorrectly marked Chapter 11-1 applicable.'),
 ('F03','FAIL',{'omit':'shipOperatesInPolarWaters'},'Polar-water operation applicability selector missing.'),
 ('F04','FAIL',{'omit':'shipType'},'Ship-type selector missing.'),
 ('F05','FAIL',{'stype':'cargo_ship','omit':'grossTonnage'},'Cargo-ship gross tonnage selector missing.'),
]: add('IMO26-016',x[0],x[1],b016,x[2],x[3])

for x in [
 ('P01','PASS',{},'Applicable ship has voyage plan and all represented intended-voyage hazards are covered.'),
 ('P02','PASS',{'hazards':('ice',),'coverage':(True,)},'Single represented hazard is covered by voyage plan.'),
 ('P03','PASS',{'hazards':(),'coverage':()},'Applicable voyage plan present with no separately represented hazard instances.'),
 ('P04','PASS',{'app':False,'plan':False,'hazards':('ice',),'coverage':(False,)},'Chapter 11-1 not applicable; conditional voyage-plan obligation not triggered.'),
 ('F01','FAIL',{'plan':False},'Applicable ship lacks voyage plan.'),
 ('F02','FAIL',{'coverage':(True,False)},'One represented intended-voyage hazard lacks coverage.'),
 ('F03','FAIL',{'omit':'voyagePlanCoverage'},'Represented hazards lack voyage-plan coverage values.'),
 ('F04','FAIL',{'omit':'polarCodeChapter11Dash1Applicable'},'Chapter 11-1 applicability state missing.'),
]: add('IMO26-017',x[0],x[1],b017,x[2],x[3])

for x in [
 ('P01','PASS',{},'Applicable ship with SMS covers all nine route-planning topics.'),
 ('P02','PASS',{'sms':False,'procedure':True},'Without SMS, all topics are covered and documented polar-operation procedure is present.'),
 ('P03','PASS',{'app':False,'sms':False,'coverage':False,'procedure':False},'Chapter 11-1 not applicable; route-planning obligation not triggered.'),
 ('F01','FAIL',{'coverage':False},'Applicable route-planning record does not cover all nine topics.'),
 ('F02','FAIL',{'sms':False,'procedure':False},'No SMS and no documented polar-operation procedure.'),
 ('F03','FAIL',{'sms':False,'omit':'documentedPolarOperationProcedurePresent'},'Required documented procedure missing when no SMS is implemented.'),
 ('F04','FAIL',{'omit':'safetyManagementSystemImplemented'},'SMS implementation state missing.'),
 ('F05','FAIL',{'omit':'voyagePlanningTopicCoverage'},'Nine-topic voyage-planning coverage state missing.'),
 ('F06','FAIL',{'omit':'polarCodeChapter11Dash1Applicable'},'Chapter 11-1 applicability state missing.'),
]: add('IMO26-018',x[0],x[1],b018,x[2],x[3])

MANIFEST='imo26_batch_b_manifest.jsonl'
LOCK='imo26_batch_b_fixture_lock.json'
VALIDATOR='validate_imo26_batch_b.py'
def main():
    if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:
        raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
    generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,
                   batch_label='IMO 2026 Supplement Batch B',manifest_name=MANIFEST,lock_name=LOCK,
                   validator_name=VALIDATOR,family='IMO26')
if __name__=='__main__':main()
