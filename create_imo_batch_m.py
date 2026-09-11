
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



BASE='https://w3id.org/nltl/benchmark/imo-batch-m/'
SOURCE_ID='SRC-IMO-MSC385-94'
REQS=['IMO-112','IMO-113','IMO-114','IMO-115','IMO-116','IMO-117','IMO-118','IMO-119']
MODES={r:'DIRECT_STATIC' for r in REQS}
CLAUSES={r:f'Part II-A {cl}' for r,cl in {
 'IMO-112':'2.1.1','IMO-113':'2.1.2','IMO-114':'2.1.3','IMO-115':'4.2.1.1','IMO-116':'4.2.1.2','IMO-117':'4.2.1.3','IMO-118':'4.2.2','IMO-119':'4.2.3'}.items()}
CAT_A=NLTL.polarShipCategoryA;CAT_B=NLTL.polarShipCategoryB;CAT_C=NLTL.polarShipCategoryC
APPROVED=NLTL.evidenceStateApproved;REJECTED=NLTL.evidenceStateRejected

def case(req,cid,expected,graph,rationale):return {'requirement_id':req,'case_id':cid,'expected':expected,'graph':graph,'rationale':rationale}
def shipg(cid):return new_graph(BASE,cid)
def obj(g,s,t):return one(g,s,t)
def objs(g,s,t):return list(g.objects(s,NLTL[t]))

def b112(cid,area='Arctic waters',arctic='Arctic waters',discharge=False,omit=None):
 g,ex,s=shipg(cid)
 vals={'operatingArea':area,'arcticWaters':arctic,'noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea':discharge}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o112(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 a=lit(g,s,'operatingArea');ar=lit(g,s,'arcticWaters');d=lit(g,s,'noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea')
 if a is None or ar is None:return False
 if a==ar:return d is False
 return True

def b113(cid,polar=True,overall=True,cargo=True,manual=True,plan=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipOperatesInPolarWaters':polar,'polarOperationCoverage':overall,'cargoRecordBookPolarCoverage':cargo,'manualPolarCoverage':manual,'noxiousLiquidSubstanceEmergencyPlanPolarCoverage':plan}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o113(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 p=lit(g,s,'shipOperatesInPolarWaters')
 if p is None:return False
 if p is False:return True
 return all(lit(g,s,t) is True for t in ['polarOperationCoverage','cargoRecordBookPolarCoverage','manualPolarCoverage','noxiousLiquidSubstanceEmergencyPlanPolarCoverage'])

def b114(cid,cat=CAT_A,date='2017-01-01',requires=True,tank_type='3',approval=True,cert=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'constructionDate':date,'carriedNoxiousLiquidSubstanceRequiresType3Tank':requires,'cargoTankType':tank_type,'applicableCertificatePolarOperationEntryPresent':cert}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='administrationCarriageApprovalStatus':add_value(g,s,'administrationCarriageApprovalStatus',APPROVED if approval else REJECTED,ex)
 return g
def o114(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');d=lit(g,s,'constructionDate');req=lit(g,s,'carriedNoxiousLiquidSubstanceRequiresType3Tank');tt=lit(g,s,'cargoTankType')
 if None in (cat,d,req,tt):return False
 if cat not in (CAT_A,CAT_B) or str(d)<'2017-01-01' or req is False or str(tt)!='3':return True
 return obj(g,s,'administrationCarriageApprovalStatus')==APPROVED and lit(g,s,'applicableCertificatePolarOperationEntryPresent') is True

def b115(cid,stype='comminuted',flag=True,distance=3.01,near=2,record=1,marpol=True,omit=None):
 g,ex,s=shipg(cid);vals={'sewageDischargeType':stype,'comminutedAndDisinfected':flag,'marpolAnnexIvRegulation11Point1Point1ComplianceStatus':marpol}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='distanceToNearestIceShelfOrFastIce':add_value(g,s,'distanceToNearestIceShelfOrFastIce',distance,ex)
 if omit!='nearbyIceConcentration':add_value(g,s,'nearbyIceConcentration',near,ex)
 if omit!='distanceFromAreaWithIceConcentrationAboveOneTenth':add_value(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth',record,ex)
 return g
def o115(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 st=lit(g,s,'sewageDischargeType');flag=lit(g,s,'comminutedAndDisinfected')
 if st is None or flag is None:return False
 if st!='comminuted' or flag is False:return True
 d=qnum(g,s,'distanceToNearestIceShelfOrFastIce');near=qnum(g,s,'nearbyIceConcentration');rec=qnum(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth')
 return d is not None and d>3 and near is not None and rec is not None and lit(g,s,'marpolAnnexIvRegulation11Point1Point1ComplianceStatus') is True

def b116(cid,stype='not comminuted',flag=True,distance=12.01,near=2,record=1,marpol=True,omit=None):
 g,ex,s=shipg(cid);vals={'sewageDischargeType':stype,'notComminutedOrDisinfected':flag,'marpolAnnexIvRegulation11Point1Point1ComplianceStatus':marpol}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='distanceToNearestIceShelfOrFastIce':add_value(g,s,'distanceToNearestIceShelfOrFastIce',distance,ex)
 if omit!='nearbyIceConcentration':add_value(g,s,'nearbyIceConcentration',near,ex)
 if omit!='distanceFromAreaWithIceConcentrationAboveOneTenth':add_value(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth',record,ex)
 return g
def o116(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 st=lit(g,s,'sewageDischargeType');flag=lit(g,s,'notComminutedOrDisinfected')
 if st is None or flag is None:return False
 if st!='not comminuted' or flag is False:return True
 d=qnum(g,s,'distanceToNearestIceShelfOrFastIce');near=qnum(g,s,'nearbyIceConcentration');rec=qnum(g,s,'distanceFromAreaWithIceConcentrationAboveOneTenth')
 return d is not None and d>12 and near is not None and rec is not None and lit(g,s,'marpolAnnexIvRegulation11Point1Point1ComplianceStatus') is True

def b117(cid,uses=True,approval=True,cert=True,discharge=True,generic_cert=True,generic_discharge=True,land=1,icearea=1,omit=None,wrong_owner=False):
 g,ex,s=shipg(cid)
 if omit!='sewageDischargeUsesTreatmentPlant':add_value(g,s,'sewageDischargeUsesTreatmentPlant',uses,ex)
 if omit!='sewageTreatmentPlantApprovalStatus':add_value(g,s,'sewageTreatmentPlantApprovalStatus',APPROVED if approval else REJECTED,ex)
 if omit!='marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus':add_value(g,s,'marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus',APPROVED if cert else REJECTED,ex)
 if omit!='marpolCertificationStatus':add_value(g,s,'marpolCertificationStatus',APPROVED if generic_cert else REJECTED,ex)
 if omit!='marpolAnnexIvRegulation11Point1Point2DischargeComplianceStatus':add_value(g,s,'marpolAnnexIvRegulation11Point1Point2DischargeComplianceStatus',discharge,ex)
 if omit!='marpolDischargeStatus':add_value(g,s,'marpolDischargeStatus',generic_discharge,ex)
 rec=typed(ex,g,'distanceRecord','dischargeDistanceRecords')
 if omit!='hasDischargeDistanceRecord':add_value(g,s,'hasDischargeDistanceRecord',rec,ex)
 owner=s if wrong_owner else rec
 if omit!='distanceToNearestLandIceShelfOrFastIce':add_value(g,owner,'distanceToNearestLandIceShelfOrFastIce',land,ex)
 if omit!='distanceToAreaWithIceConcentrationGreaterThanOneTenth':add_value(g,owner,'distanceToAreaWithIceConcentrationGreaterThanOneTenth',icearea,ex)
 return g
def o117(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 uses=lit(g,s,'sewageDischargeUsesTreatmentPlant')
 if uses is None:return False
 if uses is False:return True
 if obj(g,s,'sewageTreatmentPlantApprovalStatus')!=APPROVED:return False
 if obj(g,s,'marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus')!=APPROVED:return False
 if obj(g,s,'marpolCertificationStatus')!=APPROVED:return False
 if lit(g,s,'marpolAnnexIvRegulation11Point1Point2DischargeComplianceStatus') is not True or lit(g,s,'marpolDischargeStatus') is not True:return False
 rs=objs(g,s,'hasDischargeDistanceRecord')
 return len(rs)==1 and qnum(g,rs[0],'distanceToNearestLandIceShelfOrFastIce') is not None and qnum(g,rs[0],'distanceToAreaWithIceConcentrationGreaterThanOneTenth') is not None

def b118(cid,date='2017-01-01',cat=CAT_A,passenger=False,discharge=False,compliance=False,omit=None):
 g,ex,s=shipg(cid)
 if passenger:g.add((s,RDF.type,NLTL.passengerShip))
 vals={'constructionDate':date,'shipCategory':cat,'sewageDischargeToSea':discharge,'polarCodeSewageParagraph4Point2Point1Point3ComplianceStatus':compliance}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 return g
def o118(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 d=lit(g,s,'constructionDate');cat=obj(g,s,'shipCategory')
 if d is None or cat is None:return False
 applicable=str(d)>='2017-01-01' and (cat in (CAT_A,CAT_B) or (s,RDF.type,NLTL.passengerShip) in g)
 if not applicable:return True
 dis=lit(g,s,'sewageDischargeToSea');comp=lit(g,s,'polarCodeSewageParagraph4Point2Point1Point3ComplianceStatus')
 if dis is None:return False
 return dis is False or comp is True

def b119(cid,cat=CAT_A,conc=2,extended=True,occurs=True,plant=True,cert=True,approval=True,omit=None):
 g,ex,s=shipg(cid);vals={'shipCategory':cat,'extendedPeriodOperation':extended,'sewageDischargeOccurs':occurs,'approvedSewageTreatmentPlantUsed':plant}
 for t,v in vals.items():
  if omit!=t:add_value(g,s,t,v,ex)
 if omit!='iceConcentration':add_value(g,s,'iceConcentration',conc,ex)
 if omit!='marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus':add_value(g,s,'marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus',APPROVED if cert else REJECTED,ex)
 if omit!='administrationDischargeApprovalStatus':add_value(g,s,'administrationDischargeApprovalStatus',APPROVED if approval else REJECTED,ex)
 return g
def o119(g):
 s=next(g.subjects(RDF.type,NLTL.ship),None)
 if s is None:return False
 cat=obj(g,s,'shipCategory');conc=qnum(g,s,'iceConcentration');ext=lit(g,s,'extendedPeriodOperation');occ=lit(g,s,'sewageDischargeOccurs')
 if None in (cat,conc,ext,occ):return False
 if cat not in (CAT_A,CAT_B) or conc<=1 or ext is False or occ is False:return True
 return lit(g,s,'approvedSewageTreatmentPlantUsed') is True and obj(g,s,'marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus')==APPROVED and obj(g,s,'administrationDischargeApprovalStatus')==APPROVED

ORACLES={'IMO-112':o112,'IMO-113':o113,'IMO-114':o114,'IMO-115':o115,'IMO-116':o116,'IMO-117':o117,'IMO-118':o118,'IMO-119':o119}
CASES=[]
for cid,exp,kw,rat in [
 ('IMO-112-M-P01','PASS',{},'NLS/NLS-mixture discharge does not occur in Arctic waters.'),('IMO-112-M-F01','FAIL',{'discharge':True},'NLS discharge occurs in Arctic waters.'),('IMO-112-M-P02','PASS',{'area':'Baltic Sea'},'Outside Arctic waters.'),('IMO-112-M-F02','FAIL',{'omit':'operatingArea'},'Operating-area applicability value missing.'),('IMO-112-M-F03','FAIL',{'omit':'noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea'},'Applicable discharge state missing.')]:CASES.append(case('IMO-112',cid,exp,b112(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-113-M-P01','PASS',{},'Cargo Record Book, Manual, and NLS emergency-plan polar coverage all present.'),('IMO-113-M-P02','PASS',{'polar':False,'overall':False,'cargo':False,'manual':False,'plan':False},'Not operating in polar waters.'),('IMO-113-M-F01','FAIL',{'cargo':False},'Cargo Record Book polar coverage missing.'),('IMO-113-M-F02','FAIL',{'manual':False},'Manual polar coverage missing.'),('IMO-113-M-F03','FAIL',{'plan':False},'NLS emergency-plan polar coverage missing.'),('IMO-113-M-F04','FAIL',{'overall':False},'Overall polar-operation coverage false.')]:CASES.append(case('IMO-113',cid,exp,b113(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-114-M-P01','PASS',{},'Applicable category A type-3 carriage has Administration approval and certificate entry.'),('IMO-114-M-P02','PASS',{'cat':CAT_B},'Applicable category B type-3 carriage compliant.'),('IMO-114-M-F01','FAIL',{'approval':False},'Administration carriage approval absent.'),('IMO-114-M-F02','FAIL',{'cert':False},'Polar-operation certificate entry absent.'),('IMO-114-M-P03','PASS',{'cat':CAT_C,'approval':False,'cert':False},'Category C outside this A/B trigger.'),('IMO-114-M-P04','PASS',{'date':'2016-12-31','approval':False,'cert':False},'Pre-2017 construction outside trigger.'),('IMO-114-M-P05','PASS',{'requires':False,'approval':False,'cert':False},'NLS does not require type-3 tank.'),('IMO-114-M-P06','PASS',{'tank_type':'2','approval':False,'cert':False},'Cargo tank is not type 3.'),('IMO-114-M-F03','FAIL',{'omit':'administrationCarriageApprovalStatus'},'Applicable approval evidence missing.')]:CASES.append(case('IMO-114',cid,exp,b114(cid,**kw),rat))
for req,builder,threshold in [('IMO-115',b115,3),('IMO-116',b116,12)]:
 for cid,exp,kw,rat in [
  (f'{req}-M-P01','PASS',{},f'Applicable sewage route strictly beyond {threshold} nm with MARPOL compliance and recorded ice-concentration distance.'),
  (f'{req}-M-F01','FAIL',{'distance':threshold},f'Exact {threshold} nm boundary fails strict greater-than requirement.'),
  (f'{req}-M-F02','FAIL',{'marpol':False},'MARPOL Annex IV discharge compliance fails.'),
  (f'{req}-M-F03','FAIL',{'omit':'distanceFromAreaWithIceConcentrationAboveOneTenth'},'Distinct ice-concentration-area distance record missing.'),
  (f'{req}-M-F04','FAIL',{'omit':'distanceToNearestIceShelfOrFastIce'},'Distance to ice shelf/fast ice missing.'),
  (f'{req}-M-P02','PASS',{'stype':'treatment plant','flag':False,'distance':0,'marpol':False},'Different sewage-discharge route; this conditional branch not applicable.'),
  (f'{req}-M-F05','FAIL',{'omit':'sewageDischargeType'},'Discharge-type applicability selector missing.')]:CASES.append(case(req,cid,exp,builder(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-117-M-P01','PASS',{},'Approved treatment plant, MARPOL certification/discharge compliance, and both distance records present.'),('IMO-117-M-P02','PASS',{'uses':False,'approval':False,'cert':False,'discharge':False,'generic_cert':False,'generic_discharge':False},'Treatment-plant route not used; conditional branch not applicable.'),('IMO-117-M-F01','FAIL',{'approval':False},'Treatment-plant approval status not approved.'),('IMO-117-M-F02','FAIL',{'cert':False},'Required MARPOL certification status not approved.'),('IMO-117-M-F03','FAIL',{'discharge':False},'MARPOL Annex IV 11.1.2 discharge compliance false.'),('IMO-117-M-F04','FAIL',{'omit':'hasDischargeDistanceRecord'},'Ship-to-distance-record path missing.'),('IMO-117-M-F05','FAIL',{'omit':'distanceToNearestLandIceShelfOrFastIce'},'Nearest land/ice distance record missing.'),('IMO-117-M-F06','FAIL',{'omit':'distanceToAreaWithIceConcentrationGreaterThanOneTenth'},'Ice-concentration-area distance record missing.'),('IMO-117-M-F07','FAIL',{'wrong_owner':True},'Distance quantities attached to ship instead of the linked discharge-distance record.')]:CASES.append(case('IMO-117',cid,exp,b117(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-118-M-P01','PASS',{},'Post-2017 category A ship does not discharge sewage.'),('IMO-118-M-P02','PASS',{'discharge':True,'compliance':True},'Discharge permitted through compliant 4.2.1.3 route.'),('IMO-118-M-F01','FAIL',{'discharge':True,'compliance':False},'Applicable ship discharges without compliant 4.2.1.3 route.'),('IMO-118-M-P03','PASS',{'date':'2016-12-31','discharge':True},'Pre-2017 construction outside 4.2.2 trigger.'),('IMO-118-M-P04','PASS',{'cat':CAT_C,'discharge':True},'Category C non-passenger ship outside trigger.'),('IMO-118-M-P05','PASS',{'cat':CAT_C,'passenger':True,'discharge':False},'Post-2017 passenger ship covered regardless of category and does not discharge.'),('IMO-118-M-F02','FAIL',{'cat':CAT_C,'passenger':True,'discharge':True,'compliance':False},'Passenger ship discharge without compliant 4.2.1.3 route.')]:CASES.append(case('IMO-118',cid,exp,b118(cid,**kw),rat))
for cid,exp,kw,rat in [
 ('IMO-119-M-P01','PASS',{},'Category A extended operation above 1/10 uses approved treatment plant with certification and Administration approval.'),('IMO-119-M-P02','PASS',{'cat':CAT_B,'conc':3},'Applicable category B case compliant.'),('IMO-119-M-F01','FAIL',{'plant':False},'Approved sewage treatment plant not used.'),('IMO-119-M-F02','FAIL',{'cert':False},'Required MARPOL certification absent.'),('IMO-119-M-F03','FAIL',{'approval':False},'Administration discharge approval absent.'),('IMO-119-M-P03','PASS',{'conc':1,'plant':False,'cert':False,'approval':False},'Exactly 1/10 does not satisfy exceeding-1/10 trigger.'),('IMO-119-M-P04','PASS',{'extended':False,'plant':False,'cert':False,'approval':False},'Operation not for an extended period.'),('IMO-119-M-P05','PASS',{'occurs':False,'plant':False,'cert':False,'approval':False},'No sewage discharge occurs.'),('IMO-119-M-P06','PASS',{'cat':CAT_C,'plant':False,'cert':False,'approval':False},'Category C outside A/B trigger.')]:CASES.append(case('IMO-119',cid,exp,b119(cid,**kw),rat))

MANIFEST='imo_batch_m_manifest.jsonl';LOCK='imo_batch_m_fixture_lock.json';VALIDATOR='validate_imo_batch_m.py'
def main():
 if Path(__file__).name==VALIDATOR or '--validate-only' in sys.argv:raise SystemExit(0 if validate_batch(MANIFEST,LOCK,ORACLES,True) else 1)
 generate_batch(base=BASE,reqs=REQS,modes=MODES,cases=CASES,oracles=ORACLES,clauses=CLAUSES,source_id=SOURCE_ID,batch_label='IMO Polar Code Batch M',manifest_name=MANIFEST,lock_name=LOCK,validator_name=VALIDATOR,family='IMO')
if __name__=='__main__':main()
