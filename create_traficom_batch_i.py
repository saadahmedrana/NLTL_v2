from pathlib import Path
import json, hashlib, math, shutil, sys
from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.namespace import XSD

def find_repo():
    cs=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    for c in cs:
        p=c/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'/'requirement_term_index.json'
        if p.exists(): return c.resolve()
    raise RuntimeError('Could not locate NLTL_v2 repository root')
REPO=find_repo(); ROOT=REPO/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'; R13=REPO/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'
INDEX=json.loads((R13/'requirement_term_index.json').read_text()); REGISTRY=json.loads((R13/'registry'/'term_registry.json').read_text()); REG={x['localName']:x for x in REGISTRY}; CONTRACTS=INDEX['dependencyContracts']
NLTL=Namespace('https://w3id.org/nltl/vocab#'); QUDT=Namespace('http://qudt.org/schema/qudt/'); UNIT=Namespace('http://qudt.org/vocab/unit/'); BASE='https://w3id.org/nltl/benchmark/traficom-batch-i/'
REQS=['TRF-108','TRF-109','TRF-111','TRF-112','TRF-113','TRF-114','TRF-116','TRF-118','TRF-120','TRF-123']
MODES={'TRF-108':'DIRECT_STATIC','TRF-109':'DIRECT_STATIC','TRF-111':'COMPLEX_READINESS','TRF-112':'COMPLEX_READINESS','TRF-113':'DIRECT_STATIC','TRF-114':'COMPLEX_READINESS','TRF-116':'COMPLEX_READINESS','TRF-118':'COMPLEX_READINESS','TRF-120':'DIRECT_STATIC','TRF-123':'COMPLEX_READINESS'}
for r in REQS:
    assert CONTRACTS[r]['status']=='COMPLETE' and CONTRACTS[r]['verificationMode']==MODES[r]
for _r in ['TRF-111','TRF-112','TRF-114','TRF-116','TRF-118','TRF-123']:
    assert CONTRACTS[_r].get('formulaExecutionRequired') is False
ONTOLOGY=Graph().parse(R13/'ontology'/'nltl_benchmark_vocabulary.ttl',format='turtle'); KNOWN={str(s).split('#',1)[1] for s in set(ONTOLOGY.subjects()) if str(s).startswith(str(NLTL)) and '#' in str(s)}
ICE={'IA Super':NLTL.iceClassIaSuper,'IA':NLTL.iceClassIa,'IB':NLTL.iceClassIb,'IC':NLTL.iceClassIc,'II':NLTL.iceClassIi,'III':NLTL.iceClassIii}

def new(cid):
    g=Graph(); ex=Namespace(BASE+cid+'/'); g.bind('ex',ex);g.bind('nltl',NLTL);g.bind('qudt',QUDT);g.bind('unit',UNIT);g.bind('xsd',XSD); ship=ex.ship; g.add((ship,RDF.type,NLTL.ship)); return g,ex,ship

def add(g,s,t,v,ex,name=None,wrong_unit=False):
    row=REG[t]; kind=row['kind']
    if kind=='QuantityProperty':
        q=ex[name or t+'Value']; g.add((q,RDF.type,QUDT.QuantityValue)); g.add((q,QUDT.numericValue,Literal(str(v),datatype=XSD.decimal))); u=URIRef(row['unitIri']);
        if wrong_unit: u=UNIT.UNITLESS if str(u)!=str(UNIT.UNITLESS) else UNIT.M
        g.add((q,QUDT.unit,u)); g.add((s,NLTL[t],q)); return q
    if kind=='DatatypeProperty':
        dt={'xsd:boolean':XSD.boolean,'xsd:string':XSD.string,'xsd:integer':XSD.integer,'xsd:decimal':XSD.decimal,'xsd:date':XSD.date}[row['datatype']]; g.add((s,NLTL[t],Literal(v,datatype=dt))); return None
    if kind=='ObjectProperty':
        g.add((s,NLTL[t],v)); return v
    raise RuntimeError(t)
def link(g,s,t,ex,n,cls):
    o=ex[n]; g.add((o,RDF.type,NLTL[cls])); add(g,s,t,o,ex); return o
def one(g,s,t):
    xs=list(g.objects(s,NLTL[t])); return xs[0] if len(xs)==1 else None
def qnum(g,s,t):
    q=one(g,s,t)
    if q is None:return None
    ns=list(g.objects(q,QUDT.numericValue)); us=list(g.objects(q,QUDT.unit)); exp=REG[t].get('unitIri','')
    if len(ns)!=1 or len(us)!=1 or (exp and str(us[0])!=exp):return None
    try:return float(ns[0])
    except:return None
def lit(g,s,t):
    o=one(g,s,t)
    if o is None:return None
    try:return o.toPython()
    except:return None
def close(a,b): return a is not None and b is not None and math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-7)


def build108(cid,known=False,selected='two',missing=None):
    g,ex,s=new(cid);add(g,s,'stressLifeCurveKnown',known,ex);add(g,s,'stressLifeCurveType','known' if known else 'unknown',ex)
    if missing!='stressLifeCurveSelection':add(g,s,'stressLifeCurveSelection',NLTL.twoSlopeStressLifeCurve if selected=='two' else ex.otherStressLifeCurve,ex)
    if missing!='stressLifeCurveSelectionCorrespondenceEvidence':link(g,s,'stressLifeCurveSelectionCorrespondenceEvidence',ex,'evidence','evidenceArtifact')
    return g
def oracle108(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);known=lit(g,s,'stressLifeCurveKnown');sel=one(g,s,'stressLifeCurveSelection');ev=one(g,s,'stressLifeCurveSelectionCorrespondenceEvidence')
    if known is False:return sel==NLTL.twoSlopeStressLifeCurve and ev is not None
    return sel is not None and ev is not None

def build109(cid,ptype='open',cycles=5000000,bad=False,missing=None,badref=False):
    g,ex,s=new(cid);add(g,s,'propellerType',ptype,ex);add(g,s,'iceLoadCycleCount',cycles,ex);tc=link(g,s,'hasTableLookupCase',ex,'lookup','tableLookupCase');add(g,tc,'tableReference',NLTL.traficomTable6Dash10 if badref else NLTL.traficomTable6Dash14,ex)
    row={'open':[.000747,.0645,-.0565,2.22],'ducted':[.000534,.0533,-.0459,2.584]}[ptype]
    for t,v in zip(['fatigueCoefficientC1','fatigueCoefficientC2','fatigueCoefficientC3','fatigueCoefficientC4'],row):
        if t!=missing:add(g,tc,t,v+(0.001 if bad and t=='fatigueCoefficientC1' else 0),ex)
    return g
def oracle109(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);pt=lit(g,s,'propellerType');n=lit(g,s,'iceLoadCycleCount');tc=one(g,s,'hasTableLookupCase')
    if pt not in {'open','ducted'} or n is None or not (5000000<=n<=100000000) or tc is None or one(g,tc,'tableReference')!=NLTL.traficomTable6Dash14:return False
    exp={'open':[.000747,.0645,-.0565,2.22],'ducted':[.000534,.0533,-.0459,2.584]}[pt]
    got=[qnum(g,tc,t) for t in ['fatigueCoefficientC1','fatigueCoefficientC2','fatigueCoefficientC3','fatigueCoefficientC4']]
    return all(close(a,b) for a,b in zip(got,exp))

def build111(cid,typ='extreme',missing=None,bad=False):
    g,ex,s=new(cid);comp=link(g,s,'hasPropellerShaftLineComponent',ex,'component','propellerShaftLineComponent');lc=link(g,s,'hasPropulsionLoadCase',ex,'loadCase','loadCase');tv={'extreme':NLTL.extremeOperationalLoadCase,'fatigue':NLTL.fatigueLoadCase,'blade':NLTL.bladeFailureLoadCase}[typ];add(g,lc,'shaftLineLoadCaseType',tv,ex)
    vals={'extremeIceForce':500,'componentYieldSafetyFactor':1.3 if typ=='extreme' else 1.0,'fatigueSafetyFactor':1.5}
    for t,v in vals.items():
        if t!=missing:add(g,comp if t!='extremeIceForce' else lc,t,(v-0.2 if bad and t in {'componentYieldSafetyFactor','fatigueSafetyFactor'} else v),ex)
    return g
def oracle111(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);comp=one(g,s,'hasPropellerShaftLineComponent');lc=one(g,s,'hasPropulsionLoadCase')
    if comp is None or lc is None or qnum(g,lc,'extremeIceForce') is None:return False
    typ=one(g,lc,'shaftLineLoadCaseType');ys=qnum(g,comp,'componentYieldSafetyFactor');fs=qnum(g,comp,'fatigueSafetyFactor')
    if typ==NLTL.extremeOperationalLoadCase:return ys is not None and ys>=1.3
    if typ==NLTL.fatigueLoadCase:return fs is not None and fs>=1.5
    if typ==NLTL.bladeFailureLoadCase:return ys is not None and ys>=1.0
    return False

def build112(cid,missing=None,bad=False):
    g,ex,s=new(cid);comp=link(g,s,'hasPropellerShaftLineComponent',ex,'component','propellerShaftLineComponent');lc=link(g,s,'hasPropulsionLoadCase',ex,'loadCase','loadCase');add(g,lc,'shaftLineLoadCaseType',NLTL.bladeFailureLoadCase,ex)
    vals={'bladeFailureUltimateLoad':500,'combinedAxialBendingTorsionLoad':600,'bendingYieldSafetyFactor':1.0,'torsionalYieldSafetyFactor':1.0}
    for t,v in vals.items():
        if t!=missing:add(g,lc if 'Load' in t else comp,t,(.9 if bad and 'SafetyFactor' in t else v),ex)
    return g
def oracle112(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);comp=one(g,s,'hasPropellerShaftLineComponent');lc=one(g,s,'hasPropulsionLoadCase')
    return comp is not None and lc is not None and one(g,lc,'shaftLineLoadCaseType')==NLTL.bladeFailureLoadCase and qnum(g,lc,'bladeFailureUltimateLoad') is not None and qnum(g,lc,'combinedAxialBendingTorsionLoad') is not None and (qnum(g,comp,'bendingYieldSafetyFactor') or -1)>=1 and (qnum(g,comp,'torsionalYieldSafetyFactor') or -1)>=1

def build113(cid,missing=None,bad=False):
    g,ex,s=new(cid)
    if missing!='thrusterBladeLossDesignEvidence':link(g,s,'thrusterBladeLossDesignEvidence',ex,'bladeLossEvidence','evidenceArtifact')
    if missing!='maximumComponentLoadBladeOrientationConfirmed':add(g,s,'maximumComponentLoadBladeOrientationConfirmed',not bad,ex)
    return g
def oracle113(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);return one(g,s,'thrusterBladeLossDesignEvidence') is not None and lit(g,s,'maximumComponentLoadBladeOrientationConfirmed') is True

def build114(cid,geom='hemispherical',missing=None,badref=False):
    g,ex,s=new(cid);c=link(g,s,'hasThrusterIceImpactLoadCase',ex,'impact','thrusterIceImpactLoadCase');body=ex.thrusterBody;g.add((body,RDF.type,NLTL.thrusterBody));add(g,c,'thrusterImpactCaseAppliesToBody',body,ex);add(g,c,'designIceBlockTableReference',NLTL.traficomTable6Dash16Reference if badref else NLTL.traficomTable6Dash3Reference,ex);add(g,c,'impactLoadCaseTableReference',NLTL.traficomTable6Dash16Reference,ex);add(g,c,'contactGeometryClassification',NLTL.hemisphericalContactGeometry if geom=='hemispherical' else NLTL.nonHemisphericalContactGeometry,ex)
    vals={'iceOperatingSpeed':5,'thrusterIceImpactLoad':1000,'thrusterIceImpactDemand':1000,'thrusterResistanceCapacity':1200}
    for t,v in vals.items():
        if t!=missing:add(g,c,t,v,ex)
    if missing!='thrusterIceImpactLoadedAreaEvidence':link(g,c,'thrusterIceImpactLoadedAreaEvidence',ex,'areaEvidence','evidenceArtifact')
    if geom!='hemispherical':
        if missing!='equivalentImpactSphereRadius':add(g,c,'equivalentImpactSphereRadius',.5,ex)
        if missing!='contactGeometryCorrespondenceEvidence':link(g,c,'contactGeometryCorrespondenceEvidence',ex,'geomEvidence','evidenceArtifact')
    return g
def oracle114(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);c=one(g,s,'hasThrusterIceImpactLoadCase')
    if c is None or one(g,c,'designIceBlockTableReference')!=NLTL.traficomTable6Dash3Reference or one(g,c,'impactLoadCaseTableReference')!=NLTL.traficomTable6Dash16Reference or one(g,c,'thrusterImpactCaseAppliesToBody') is None:return False
    if any(qnum(g,c,t) is None for t in ['iceOperatingSpeed','thrusterIceImpactLoad','thrusterIceImpactDemand','thrusterResistanceCapacity']) or one(g,c,'thrusterIceImpactLoadedAreaEvidence') is None:return False
    geom=one(g,c,'contactGeometryClassification')
    if geom==NLTL.nonHemisphericalContactGeometry:return qnum(g,c,'equivalentImpactSphereRadius') is not None and one(g,c,'contactGeometryCorrespondenceEvidence') is not None
    return geom==NLTL.hemisphericalContactGeometry

def build116(cid,area=3.14159265,thick=1.0,hub=False,missing=None):
    g,ex,s=new(cid);r=min(math.sqrt(area/math.pi),thick/2) if not hub else math.sqrt(area/math.pi);vals={'nonHemisphericalImpactContactArea':area,'designIceThickness':thick,'propellerHubOrThrusterEndCapImpact':hub,'equivalentImpactSphereRadius':r}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle116(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);return all((lit(g,s,t) is not None if t=='propellerHubOrThrusterEndCapImpact' else qnum(g,s,t) is not None) for t in ['nonHemisphericalImpactContactArea','designIceThickness','propellerHubOrThrusterEndCapImpact','equivalentImpactSphereRadius'])

def build118(cid,local=False,missing=None,bad=False):
    g,ex,s=new(cid);comp=ex.component;g.add((comp,RDF.type,NLTL.shipComponent));ass=link(g,s,'hasFactoredExtremeLoadOperabilityAssessment',ex,'assessment','factoredExtremeLoadOperabilityAssessment');add(g,ass,'assessedThrusterComponent',comp,ex);add(g,s,'thrusterExtremeLoad',1000,ex);add(g,s,'yieldSafetyFactor',1.0 if local else 1.3,ex);add(g,s,'nominalVonMisesStress',200,ex);add(g,s,'localStressConcentration',1 if local else 0,ex);add(g,s,'componentMaterialYieldStrength',300,ex);add(g,ass,'assessedFactoredExtremeLoad',1300,ex);add(g,ass,'assessmentOperabilityMaintained',not bad,ex);add(g,ass,'assessmentRepairRequired',bad,ex)
    if missing:
        for ss,p,o in list(g.triples((None,NLTL[missing],None))):g.remove((ss,p,o))
    return g
def oracle118(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);ass=one(g,s,'hasFactoredExtremeLoadOperabilityAssessment')
    if ass is None:return False
    for t in ['thrusterExtremeLoad','yieldSafetyFactor','nominalVonMisesStress','localStressConcentration','componentMaterialYieldStrength']:
        if qnum(g,s,t) is None:return False
    return one(g,ass,'assessedThrusterComponent') is not None and qnum(g,ass,'assessedFactoredExtremeLoad') is not None and lit(g,ass,'assessmentOperabilityMaintained') is True and lit(g,ass,'assessmentRepairRequired') is False

def build120(cid,dirs=('longitudinal','transverse'),missing=None):
    g,ex,s=new(cid);body=ex.thrusterBody;g.add((body,RDF.type,NLTL.thrusterBody))
    for d in dirs:
        c=link(g,body,'hasNaturalFrequencyCalculationCase',ex,d+'Case','calculationCase');add(g,c,'vibrationDirection',NLTL.longitudinalDirection if d=='longitudinal' else NLTL.transverseDirection,ex)
        vals={'shipAttachmentStiffness':1000,'thrusterNaturalFrequency':20,'waterAddedMass':500}
        for t,v in vals.items():
            if t!=missing:add(g,c,t,v,ex)
    return g
def oracle120(g):
    cases=list(g.subjects(RDF.type,NLTL.calculationCase));seen=set()
    for c in cases:
        d=one(g,c,'vibrationDirection');seen.add(d)
        if any(qnum(g,c,t) is None for t in ['shipAttachmentStiffness','thrusterNaturalFrequency','waterAddedMass']):return False
    return NLTL.longitudinalDirection in seen and NLTL.transverseDirection in seen

def build123(cid,missing=None,bad=False):
    g,ex,s=new(cid);lc=link(g,s,'hasOccasionalForceLoadCase',ex,'loadCase','occasionalForceLoadCase');comp=link(g,lc,'occasionalForceCaseAssessedComponent',ex,'component','shipComponent');mat=link(g,comp,'hasMaterialProperties',ex,'material','materialProperties');add(g,lc,'occasionalForceComponentStress',200,ex);add(g,mat,'componentMaterialYieldStrength',300,ex);add(g,comp,'componentYieldSafetyFactor',1.2,ex);add(g,lc,'propellerBladeExcludedFromOccasionalForceScope',not bad,ex)
    if missing:
        for ss,p,o in list(g.triples((None,NLTL[missing],None))):g.remove((ss,p,o))
    return g
def oracle123(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);lc=one(g,s,'hasOccasionalForceLoadCase');
    if lc is None:return False
    comp=one(g,lc,'occasionalForceCaseAssessedComponent');mat=one(g,comp,'hasMaterialProperties') if comp else None
    return comp is not None and mat is not None and qnum(g,lc,'occasionalForceComponentStress') is not None and qnum(g,mat,'componentMaterialYieldStrength') is not None and qnum(g,comp,'componentYieldSafetyFactor') is not None and lit(g,lc,'propellerBladeExcludedFromOccasionalForceScope') is True

OR={'TRF-108':oracle108,'TRF-109':oracle109,'TRF-111':oracle111,'TRF-112':oracle112,'TRF-113':oracle113,'TRF-114':oracle114,'TRF-116':oracle116,'TRF-118':oracle118,'TRF-120':oracle120,'TRF-123':oracle123}
CASES=[]
def ac(r,suf,exp,rat,g):CASES.append({'requirement_id':r,'case_id':f'{r}-{suf}','expected':exp,'rationale':rat,'graph':g})
# 108
ac('TRF-108','P01','PASS','Unknown S-N curve defaults to two-slope.',build108('TRF-108-P01'));ac('TRF-108','P02','PASS','Known curve with correspondence evidence.',build108('TRF-108-P02',known=True,selected='one'));ac('TRF-108','F01','FAIL','Unknown curve does not select two-slope.',build108('TRF-108-F01',selected='one'));ac('TRF-108','F02','FAIL','Selection evidence missing.',build108('TRF-108-F02',missing='stressLifeCurveSelectionCorrespondenceEvidence'))
#109
for i,(pt,n) in enumerate([('open',5000000),('open',100000000),('ducted',5000000),('ducted',100000000)],1):ac('TRF-109',f'P0{i}','PASS','Canonical Table 6-14 selector and cycle boundary.',build109(f'TRF-109-P0{i}',pt,n))
ac('TRF-109','F01','FAIL','Wrong Table 6-14 coefficient.',build109('TRF-109-F01','open',10000000,bad=True));ac('TRF-109','F02','FAIL','Wrong table reference.',build109('TRF-109-F02','ducted',10000000,badref=True));ac('TRF-109','F03','FAIL','Cycle count below allowed range.',build109('TRF-109-F03','open',4999999));ac('TRF-109','F04','FAIL','Missing coefficient C4.',build109('TRF-109-F04','open',10000000,missing='fatigueCoefficientC4'))
#111
for i,t in enumerate(['extreme','fatigue','blade'],1):ac('TRF-111',f'P0{i}','PASS',f'Ready shaft-line {t} load case.',build111(f'TRF-111-P0{i}',t))
ac('TRF-111','F01','FAIL','Missing extreme ice force operand.',build111('TRF-111-F01','extreme',missing='extremeIceForce'));ac('TRF-111','F02','FAIL','Extreme-load yield safety factor too low.',build111('TRF-111-F02','extreme',bad=True));ac('TRF-111','F03','FAIL','Fatigue safety factor too low.',build111('TRF-111-F03','fatigue',bad=True))
#112
ac('TRF-112','P01','PASS','Blade-failure shaft-line readiness complete.',build112('TRF-112-P01'));ac('TRF-112','F01','FAIL','Missing combined load.',build112('TRF-112-F01',missing='combinedAxialBendingTorsionLoad'));ac('TRF-112','F02','FAIL','Missing bending safety factor.',build112('TRF-112-F02',missing='bendingYieldSafetyFactor'));ac('TRF-112','F03','FAIL','Yield safety factor below one.',build112('TRF-112-F03',bad=True))
#113
ac('TRF-113','P01','PASS','Blade-loss design evidence and worst orientation confirmed.',build113('TRF-113-P01'));ac('TRF-113','F01','FAIL','Design evidence missing.',build113('TRF-113-F01',missing='thrusterBladeLossDesignEvidence'));ac('TRF-113','F02','FAIL','Maximum-load orientation not confirmed.',build113('TRF-113-F02',bad=True));ac('TRF-113','F03','FAIL','Orientation confirmation missing.',build113('TRF-113-F03',missing='maximumComponentLoadBladeOrientationConfirmed'))
#114
ac('TRF-114','P01','PASS','Hemispherical impact case complete.',build114('TRF-114-P01'));ac('TRF-114','P02','PASS','Non-hemispherical case includes equivalent radius and correspondence evidence.',build114('TRF-114-P02','non'));ac('TRF-114','F01','FAIL','Wrong design-ice-block table reference.',build114('TRF-114-F01',badref=True));ac('TRF-114','F02','FAIL','Non-hemispherical radius missing.',build114('TRF-114-F02','non',missing='equivalentImpactSphereRadius'));ac('TRF-114','F03','FAIL','Loaded-area evidence missing.',build114('TRF-114-F03',missing='thrusterIceImpactLoadedAreaEvidence'))
#116
ac('TRF-116','P01','PASS','Non-hemispherical readiness has contact area, thickness and equivalent radius.',build116('TRF-116-P01'));ac('TRF-116','P02','PASS','Hub/end-cap exception context represented.',build116('TRF-116-P02',hub=True));ac('TRF-116','F01','FAIL','Equivalent radius missing.',build116('TRF-116-F01',missing='equivalentImpactSphereRadius'));ac('TRF-116','F02','FAIL','Contact area missing.',build116('TRF-116-F02',missing='nonHemisphericalImpactContactArea'))
#118
ac('TRF-118','P01','PASS','Nominal thruster-body assessment ready.',build118('TRF-118-P01'));ac('TRF-118','P02','PASS','Local stress-concentration assessment ready.',build118('TRF-118-P02',local=True));ac('TRF-118','F01','FAIL','Operability not maintained.',build118('TRF-118-F01',bad=True));ac('TRF-118','F02','FAIL','Factored load result missing.',build118('TRF-118-F02',missing='assessedFactoredExtremeLoad'));ac('TRF-118','F03','FAIL','Material yield strength missing.',build118('TRF-118-F03',missing='componentMaterialYieldStrength'))
#120
ac('TRF-120','P01','PASS','Longitudinal and transverse calculations include water added mass and attachment stiffness.',build120('TRF-120-P01'));ac('TRF-120','F01','FAIL','Transverse direction case missing.',build120('TRF-120-F01',dirs=('longitudinal',)));ac('TRF-120','F02','FAIL','Water added mass missing.',build120('TRF-120-F02',missing='waterAddedMass'));ac('TRF-120','F03','FAIL','Attachment stiffness missing.',build120('TRF-120-F03',missing='shipAttachmentStiffness'))
#123
ac('TRF-123','P01','PASS','Occasional-force component readiness with blade exclusion evidence.',build123('TRF-123-P01'));ac('TRF-123','F01','FAIL','Propeller-blade exclusion evidence false.',build123('TRF-123-F01',bad=True));ac('TRF-123','F02','FAIL','Component stress missing.',build123('TRF-123-F02',missing='occasionalForceComponentStress'));ac('TRF-123','F03','FAIL','Material path missing.',build123('TRF-123-F03',missing='hasMaterialProperties'));ac('TRF-123','F04','FAIL','Safety factor result missing.',build123('TRF-123-F04',missing='componentYieldSafetyFactor'))
def vocab(g):
    bad=[]
    for s,p,o in g:
        for n in (s,p,o):
            st=str(n)
            if st.startswith(str(NLTL)) and '#' in st and st.split('#',1)[1] not in KNOWN: bad.append(st.split('#',1)[1])
    return not bad,sorted(set(bad))
def qudt(g):
    for q in g.subjects(RDF.type,QUDT.QuantityValue):
        if len(list(g.objects(q,QUDT.numericValue)))!=1 or len(list(g.objects(q,QUDT.unit)))!=1:return False
    return True
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(check_hashes=True):
    mp=ROOT/'manifests'/'traficom_batch_i_manifest.jsonl'; lp=ROOT/'locks'/'traficom_batch_i_fixture_lock.json'
    rows=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()]; syn=vo=qu=ag=0; diag=[]
    for r in rows:
        p=ROOT/r['rdf_path']
        try:g=Graph().parse(p,format='turtle');syn+=1
        except Exception as e:diag.append((r['case_id'],'parse',str(e)));continue
        ok,b=vocab(g);vo+=int(ok); qu+=int(qudt(g)); act='PASS' if OR[r['requirement_id']](g) else 'FAIL'; ag+=int(act==r['expected'])
        if not ok:diag.append((r['case_id'],'vocab',b))
        if act!=r['expected']:diag.append((r['case_id'],'oracle',act,r['expected']))
    h=True
    if check_hashes:
        if not lp.exists():h=False
        else:
            lock=json.loads(lp.read_text());
            for rel,x in lock['frozen_files'].items():
                p=ROOT/rel
                if not p.exists() or sha(p)!=x:h=False;diag.append((rel,'hash','mismatch'))
    n=len(rows); print(f'Requirements: {len(set(r["requirement_id"] for r in rows))}');print(f'RDF files: {n}');print(f'Syntactically valid: {syn}');print(f'Vocabulary validation count: {vo}');print(f'QUDT/unit validation count: {qu}');print(f'Source-oracle agreement count: {ag}');
    if check_hashes:print('Frozen hashes matched: '+('YES' if h else 'NO'))
    ok=(syn==vo==qu==ag==n and (h if check_hashes else True));print('Overall status: '+('PASS' if ok else 'FAIL'))
    if diag:print('Diagnostics:',*diag,sep='\n')
    return ok
CLAUSES={'TRF-108':'6.6.2.3','TRF-109':'6.6.2.3','TRF-111':'6.6.4','TRF-112':'6.6.4.1','TRF-113':'6.6.5.1','TRF-114':'6.6.5.2','TRF-116':'6.6.5.2','TRF-118':'6.6.5.4','TRF-120':'6.6.5.5','TRF-123':'6.7.3'}
def generate():
    for p in [ROOT/'rdf'/'TRF',ROOT/'specifications'/'TRF',ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:p.mkdir(parents=True,exist_ok=True)
    lp=ROOT/'locks'/'traficom_batch_i_fixture_lock.json'
    if lp.exists():raise SystemExit('Batch G lock already exists. Refusing to overwrite frozen fixtures.')
    rows=[]
    for c in CASES:
        r=c['requirement_id']; od=ROOT/'rdf'/'TRF'/r;od.mkdir(parents=True,exist_ok=True); p=od/f"{c['case_id']}.ttl"
        if p.exists():raise SystemExit(f'Refusing to overwrite existing RDF fixture: {p}')
        c['graph'].serialize(destination=p,format='turtle'); rows.append({'requirement_id':r,'case_id':c['case_id'],'expected':c['expected'],'rdf_path':str(p.relative_to(ROOT)),'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'verification_mode':MODES[r],'source_oracle_rationale':c['rationale'],'generated_shacl_inspected':False})
    mp=ROOT/'manifests'/'traficom_batch_i_manifest.jsonl';mp.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    for r in REQS:(ROOT/'specifications'/'TRF'/f'{r}.json').write_text(json.dumps({'requirement_id':r,'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'source_lock_id':INDEX['sourceLockId'],'r13_contract':CONTRACTS[r],'test_cases':[{'case_id':x['case_id'],'expected':x['expected'],'rationale':x['rationale']} for x in CASES if x['requirement_id']==r],'benchmark_policy':'Source/R13-defined behavioral oracle created without inspecting generated SHACL.'},indent=2)+'\n')
    print('Pre-freeze validation'); assert validate(False)
    vp=ROOT/'scripts'/'validate_traficom_batch_i.py';shutil.copy2(Path(__file__).resolve(),vp);vp.chmod(0o755)
    frozen={}
    for c in CASES:frozen[str((ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl").relative_to(ROOT))]=sha(ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl")
    frozen[str(mp.relative_to(ROOT))]=sha(mp)
    for r in REQS:
        p=ROOT/'specifications'/'TRF'/f'{r}.json';frozen[str(p.relative_to(ROOT))]=sha(p)
    lp.write_text(json.dumps({'benchmark':'TRAFICOM Behavioral Benchmark Batch I','source_lock_id':INDEX['sourceLockId'],'source_id':'SRC-TRAFICOM-2021','requirements':REQS,'requirement_count':len(REQS),'case_count':len(CASES),'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,'frozen_files':frozen},indent=2)+'\n')
    print('\nFrozen validation'); assert validate(True)
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate(True) else 1)
    generate()
