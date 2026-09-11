
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-l/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-105','IMO-106','IMO-107','IMO-108','IMO-109','IMO-110','IMO-111']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={r:f'Part II-A {cl}' for r,cl in {
 'IMO-105':'1.1.1','IMO-106':'1.1.2','IMO-107':'1.1.4','IMO-108':'1.2.1','IMO-109':'1.2.2','IMO-110':'1.2.3','IMO-111':'1.2.4'}.items()}
CAT_A=NLTL.polarShipCategoryA;CAT_B=NLTL.polarShipCategoryB;CAT_C=NLTL.polarShipCategoryC
CLEAN=NLTL.cleanBallastMaterial;SEG=NLTL.segregatedBallastMaterial

def case(req,cid,expected,graph,rationale):return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid):return new_graph(BASE,cid)
def obj(g,s,t):return one(g,s,t)

def area_vals(g,s,ex,area='Arctic waters',arctic='Arctic waters'):
 add_value(g,s,'operatingArea',area,ex);add_value(g,s,'arcticWaters',arctic,ex)

def b105(cid,area='Arctic waters',arctic='Arctic waters',discharge=False,omit=None):
 g,ex,s=shipg(cid)
 if omit!='operatingArea':add_value(g,s,'operatingArea',area,ex)
 if omit!='arcticWaters':add_value(g,s,'arcticWaters',arctic,ex)
 if omit!='oilOrOilyMixtureDischargeToSea':add_value(g,s,'oilOrOilyMixtureDischargeToSea',discharge,ex)
 return g
def o105(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 a=lit(g,s,'operatingArea'); ar=lit(g,s,'arcticWaters'); d=lit(g,s,'oilOrOilyMixtureDischargeToSea')
 if a is None or ar is None:return False
 if a==ar:return d is False
 return True

def b106(cid,classification=CLEAN,applicable=False,omit=None):
 g,ex,s=shipg(cid)
 if classification=='OTHER': classification=typed(ex,g,'otherMaterial','dischargedMaterialTypeValue')
 if omit!='dischargedMaterialClassification':add_value(g,s,'dischargedMaterialClassification',classification,ex)
 if omit!='polarCodeOilDischargeParagraph1Point1Point1Applicable':add_value(g,s,'polarCodeOilDischargeParagraph1Point1Point1Applicable',applicable,ex)
 return g
def o106(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 c=obj(g,s,'dischargedMaterialClassification'); a=lit(g,s,'polarCodeOilDischargeParagraph1Point1Point1Applicable')
 if c is None:return False
 if c in (CLEAN,SEG):return a is False
 return a is True

def b107(cid,polar=True,overall=True,orb=True,manual=True,plan=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipOperatesInPolarWaters':polar,'polarOperationCoverage':overall,'oilRecordBookPolarCoverage':orb,'manualPolarCoverage':manual,'pollutionEmergencyPlanPolarCoverage':plan}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o107(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 p=lit(g,s,'shipOperatesInPolarWaters')
 if p is None:return False
 if p is False:return True
 return all(lit(g,s,t) is True for t in ['polarOperationCoverage','oilRecordBookPolarCoverage','manualPolarCoverage','pollutionEmergencyPlanPolarCoverage'])

def b108(cid,cat=CAT_A,date='2017-01-01',agg=599,ind=31,sep=.76,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'constructionDate':date,'aggregateOilFuelCapacity':agg,'individualOilFuelTankCapacity':ind,'oilFuelTankOuterShellSeparation':sep}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o108(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');d=lit(g,s,'constructionDate');agg=qnum(g,s,'aggregateOilFuelCapacity');ind=qnum(g,s,'individualOilFuelTankCapacity')
 if None in (cat,d,agg,ind):return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01' or agg>=600 or ind<=30:return True
 sep=qnum(g,s,'oilFuelTankOuterShellSeparation');return sep is not None and sep>=.76

def b109(cid,cat=CAT_A,date='2017-01-01',stype='cargo ship other than tanker',carries=True,sep=.76,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'constructionDate':date,'shipType':stype,'cargoTankCarriesOil':carries,'cargoTankOuterShellSeparation':sep}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o109(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');d=lit(g,s,'constructionDate');st=lit(g,s,'shipType');car=lit(g,s,'cargoTankCarriesOil')
 if None in (cat,d,st,car):return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01' or st=='oil tanker' or car is False:return True
 sep=qnum(g,s,'cargoTankOuterShellSeparation');return sep is not None and sep>=.76

def b110(cid,cat=CAT_A,date='2017-01-01',stype='oil tanker',dwt=4999,db=True,wing=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'constructionDate':date,'shipType':stype,'deadweight':dwt,'entireCargoTankLengthDoubleBottomProtectionStatus':db,'wingTankProtectionStatus':wing}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o110(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');d=lit(g,s,'constructionDate');st=lit(g,s,'shipType');dw=qnum(g,s,'deadweight')
 if None in (cat,d,st,dw):return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01' or st!='oil tanker' or dw>=5000:return True
 return lit(g,s,'entireCargoTankLengthDoubleBottomProtectionStatus') is True and lit(g,s,'wingTankProtectionStatus') is True

def b111(cid,cat=CAT_A,date='2017-01-01',tank='oil residue tank',cap=31,sep=.76,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'constructionDate':date,'tankType':tank,'individualTankCapacity':cap,'tankOuterShellSeparation':sep}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o111(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');d=lit(g,s,'constructionDate');t=lit(g,s,'tankType');cap=qnum(g,s,'individualTankCapacity')
 if None in (cat,d,t,cap):return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01' or t not in ('oil residue tank','oily bilge water holding tank') or cap<=30:return True
 sep=qnum(g,s,'tankOuterShellSeparation');return sep is not None and sep>=.76

ORACLES={'IMO-105':o105,'IMO-106':o106,'IMO-107':o107,'IMO-108':o108,'IMO-109':o109,'IMO-110':o110,'IMO-111':o111}
CASES=[]
for cid,exp,kw,rat in [
 ('IMO-105-L-P01','PASS',{},'Arctic-water oil/oily-mixture discharge prohibited and not occurring.'),
 ('IMO-105-L-F01','FAIL',{'discharge':True},'Oil/oily-mixture discharge occurs in Arctic waters.'),
 ('IMO-105-L-P02','PASS',{'area':'Baltic Sea'},'Outside Arctic waters; clause 1.1.1 conditional prohibition not applicable.'),
 ('IMO-105-L-F02','FAIL',{'omit':'operatingArea'},'Operating-area applicability value missing.'),
 ('IMO-105-L-F03','FAIL',{'omit':'oilOrOilyMixtureDischargeToSea'},'Applicable discharge state missing.')]:CASES.append(case('IMO-105',cid,exp,b105(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-106-L-P01','PASS',{'classification':CLEAN,'applicable':False},'Clean ballast is exempt from 1.1.1 prohibition.'),
 ('IMO-106-L-P02','PASS',{'classification':SEG,'applicable':False},'Segregated ballast is exempt from 1.1.1 prohibition.'),
 ('IMO-106-L-P03','PASS',{'classification':'OTHER','applicable':True},'Non-exempt discharged material retains clause 1.1.1 applicability.'),
 ('IMO-106-L-F01','FAIL',{'classification':CLEAN,'applicable':True},'Clean ballast incorrectly marked subject to the prohibition.'),
 ('IMO-106-L-F02','FAIL',{'classification':SEG,'applicable':True},'Segregated ballast incorrectly marked subject to the prohibition.'),
 ('IMO-106-L-F03','FAIL',{'classification':'OTHER','applicable':False},'Non-exempt material incorrectly marked exempt.'),
 ('IMO-106-L-F04','FAIL',{'omit':'dischargedMaterialClassification'},'Discharged-material classification missing.')]:CASES.append(case('IMO-106',cid,exp,b106(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-107-L-P01','PASS',{},'All required MARPOL Annex I polar-operation document coverage present.'),
 ('IMO-107-L-P02','PASS',{'polar':False,'overall':False,'orb':False,'manual':False,'plan':False},'Ship does not operate in polar waters; conditional coverage not applicable.'),
 ('IMO-107-L-F01','FAIL',{'orb':False},'Oil Record Book polar coverage missing.'),
 ('IMO-107-L-F02','FAIL',{'manual':False},'Manual polar coverage missing.'),
 ('IMO-107-L-F03','FAIL',{'plan':False},'Pollution emergency plan polar coverage missing.'),
 ('IMO-107-L-F04','FAIL',{'overall':False},'Overall polar-operation coverage state not satisfied.'),
 ('IMO-107-L-F05','FAIL',{'omit':'shipOperatesInPolarWaters'},'Applicability fact missing.')]:CASES.append(case('IMO-107',cid,exp,b107(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-108-L-P01','PASS',{},'Applicable A-ship case at exact 0.76 m shell-separation boundary.'),
 ('IMO-108-L-P02','PASS',{'cat':CAT_B,'sep':1.0},'Applicable B-ship case above minimum separation.'),
 ('IMO-108-L-F01','FAIL',{'sep':.759},'Applicable oil-fuel tank separation below 0.76 m.'),
 ('IMO-108-L-P03','PASS',{'agg':600,'sep':0},'Aggregate capacity exactly 600 m3 is outside the less-than-600 trigger.'),
 ('IMO-108-L-P04','PASS',{'ind':30,'sep':0},'Individual tank exactly 30 m3 is within the small-tank exemption.'),
 ('IMO-108-L-P05','PASS',{'date':'2016-12-31','sep':0},'Pre-2017 construction is outside applicability.'),
 ('IMO-108-L-P06','PASS',{'cat':CAT_C,'sep':0},'Category C is outside the A/B structural requirement.'),
 ('IMO-108-L-F02','FAIL',{'omit':'oilFuelTankOuterShellSeparation'},'Applicable separation result missing.'),
 ('IMO-108-L-F03','FAIL',{'omit':'aggregateOilFuelCapacity'},'Applicability capacity value missing.')]:CASES.append(case('IMO-108',cid,exp,b108(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-109-L-P01','PASS',{},'Applicable non-tanker cargo tank carrying oil at exact 0.76 m boundary.'),
 ('IMO-109-L-F01','FAIL',{'sep':.75},'Applicable cargo-tank shell separation below 0.76 m.'),
 ('IMO-109-L-P02','PASS',{'stype':'oil tanker','sep':0},'Oil tanker excluded from 1.2.2.'),
 ('IMO-109-L-P03','PASS',{'carries':False,'sep':0},'Cargo tank not used to carry oil; requirement not applicable.'),
 ('IMO-109-L-P04','PASS',{'date':'2016-12-31','sep':0},'Pre-2017 construction not applicable.'),
 ('IMO-109-L-P05','PASS',{'cat':CAT_C,'sep':0},'Category C not applicable.'),
 ('IMO-109-L-F02','FAIL',{'omit':'cargoTankOuterShellSeparation'},'Applicable separation result missing.'),
 ('IMO-109-L-F03','FAIL',{'omit':'shipType'},'Ship-type applicability value missing.')]:CASES.append(case('IMO-109',cid,exp,b109(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-110-L-P01','PASS',{},'Applicable sub-5000 DWT A oil tanker has both required protection arrangements.'),
 ('IMO-110-L-P02','PASS',{'cat':CAT_B,'dwt':1000},'Applicable B oil tanker with both protection arrangements.'),
 ('IMO-110-L-F01','FAIL',{'db':False},'Double-bottom protection condition fails.'),
 ('IMO-110-L-F02','FAIL',{'wing':False},'Wing-tank protection condition fails.'),
 ('IMO-110-L-P03','PASS',{'dwt':5000,'db':False,'wing':False},'Exactly 5000 tonnes is outside the less-than-5000 trigger.'),
 ('IMO-110-L-P04','PASS',{'stype':'cargo ship other than tanker','db':False,'wing':False},'Non-oil-tanker ship not applicable.'),
 ('IMO-110-L-P05','PASS',{'date':'2016-12-31','db':False,'wing':False},'Pre-2017 construction not applicable.'),
 ('IMO-110-L-F03','FAIL',{'omit':'deadweight'},'Deadweight applicability operand missing.')]:CASES.append(case('IMO-110',cid,exp,b110(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-111-L-P01','PASS',{},'Oil-residue tank above 30 m3 at exact 0.76 m boundary.'),
 ('IMO-111-L-P02','PASS',{'tank':'oily bilge water holding tank'},'Oily-bilge holding tank above 30 m3 meets separation.'),
 ('IMO-111-L-F01','FAIL',{'sep':.759},'Applicable tank separation below 0.76 m.'),
 ('IMO-111-L-P03','PASS',{'cap':30,'sep':0},'Tank exactly 30 m3 is exempt.'),
 ('IMO-111-L-P04','PASS',{'tank':'fresh water tank','sep':0},'Other tank type is outside this clause.'),
 ('IMO-111-L-P05','PASS',{'date':'2016-12-31','sep':0},'Pre-2017 construction not applicable.'),
 ('IMO-111-L-P06','PASS',{'cat':CAT_C,'sep':0},'Category C not applicable.'),
 ('IMO-111-L-F02','FAIL',{'omit':'tankOuterShellSeparation'},'Applicable tank separation value missing.')]:CASES.append(case('IMO-111',cid,exp,b111(cid,**kw),rat))

MANIFEST='imo_batch_l_manifest.jsonl';LOCK='imo_batch_l_fixture_lock.json';VALIDATOR='validate_imo_batch_l.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch L',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
