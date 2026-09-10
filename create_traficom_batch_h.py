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
NLTL=Namespace('https://w3id.org/nltl/vocab#'); QUDT=Namespace('http://qudt.org/schema/qudt/'); UNIT=Namespace('http://qudt.org/vocab/unit/'); BASE='https://w3id.org/nltl/benchmark/traficom-batch-h/'
REQS=['TRF-081','TRF-082','TRF-083','TRF-084','TRF-085','TRF-086','TRF-087','TRF-088','TRF-091','TRF-101','TRF-102','TRF-103','TRF-104']
MODES={'TRF-081':'DIRECT_CALCULATION','TRF-082':'DIRECT_STATIC','TRF-083':'DIRECT_STATIC','TRF-084':'DIRECT_CALCULATION','TRF-085':'DIRECT_STATIC','TRF-086':'DIRECT_CALCULATION','TRF-087':'DIRECT_STATIC','TRF-088':'DIRECT_STATIC','TRF-091':'DIRECT_STATIC','TRF-101':'DIRECT_CALCULATION','TRF-102':'DIRECT_CALCULATION','TRF-103':'DIRECT_STATIC','TRF-104':'DIRECT_STATIC'}
for r in REQS:
    assert CONTRACTS[r]['status']=='COMPLETE' and CONTRACTS[r]['verificationMode']==MODES[r]
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


def build081(cid,ff=100,fb=120,T=50,bad=False,missing=None):
    g,ex,s=new(cid); tf=1.1*ff;tb=1.1*fb;fw=T+2.2*tf;bw=1.5*tb;des=max(fw,bw)
    vals={'forwardBladeForce':ff,'backwardBladeForce':fb,'hydrodynamicBollardThrust':T,'forwardIceThrust':tf,'backwardIceThrust':tb,'forwardPropellerShaftDesignThrust':fw,'backwardPropellerShaftDesignThrust':bw,'propellerShaftDesignThrust':des+(10 if bad else 0)}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle081(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);ff=qnum(g,s,'forwardBladeForce');fb=qnum(g,s,'backwardBladeForce');T=qnum(g,s,'hydrodynamicBollardThrust');tf=qnum(g,s,'forwardIceThrust');tb=qnum(g,s,'backwardIceThrust');fw=qnum(g,s,'forwardPropellerShaftDesignThrust');bw=qnum(g,s,'backwardPropellerShaftDesignThrust');d=qnum(g,s,'propellerShaftDesignThrust')
    if None in [ff,fb,T,tf,tb,fw,bw,d]:return False
    return close(tf,1.1*ff) and close(tb,1.1*fb) and close(fw,T+2.2*tf) and close(bw,1.5*tb) and close(d,max(fw,bw))

def tablecase(g,ex,s,ref,operand=None,value=100,known_term=None,known=False,badref=False,missing_evidence=False):
    if known_term:add(g,s,known_term,known,ex)
    if operand:add(g,s,operand,value,ex)
    if known:return
    tc=link(g,s,'hasTableLookupCase',ex,'lookup','tableLookupCase');add(g,tc,'tableReference',NLTL.traficomTable6Dash14 if badref else NLTL[ref],ex);add(g,tc,'tableLookupApplied',True,ex)
    if not missing_evidence: link(g,tc,'lookupSelectionEvidence',ex,'lookupEvidence','evidenceArtifact')
def oracle_table(g,ref,operand=None,known_term=None):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if known_term and lit(g,s,known_term) is True:return True
    if operand and (qnum(g,s,operand) is None):return False
    cases=list(g.objects(s,NLTL.hasTableLookupCase));
    if len(cases)!=1:return False
    c=cases[0]
    return one(g,c,'tableReference')==NLTL[ref] and lit(g,c,'tableLookupApplied') is True and one(g,c,'lookupSelectionEvidence') is not None

def build082(cid,known=False,badref=False,miss_ev=False):g,ex,s=new(cid);tablecase(g,ex,s,'traficomTable6Dash8','hydrodynamicBollardThrust',100,'bollardThrustKnown',known,badref,miss_ev);return g
def oracle082(g):return oracle_table(g,'traficomTable6Dash8','hydrodynamicBollardThrust','bollardThrustKnown')
def build083(cid,known=False,badref=False,miss_ev=False):g,ex,s=new(cid);tablecase(g,ex,s,'traficomTable6Dash9','propellerRotationalSpeedAtMaximumContinuousRatingBollard',100,'rotationalSpeedKnown',known,badref,miss_ev);return g
def oracle083(g):return oracle_table(g,'traficomTable6Dash9','propellerRotationalSpeedAtMaximumContinuousRatingBollard','rotationalSpeedKnown')

def build084(cid,ptype='CP',known=False,free=1.0,bollard=None,missing=None):
    g,ex,s=new(cid);add(g,s,'propellerType',ptype,ex);add(g,s,'pitchValueKnown',known,ex)
    if missing!='propellerPitchAtMcrFreeRunning':add(g,s,'propellerPitchAtMcrFreeRunning',free,ex)
    if bollard is None:bollard=free if known else .7*free
    if missing!='propellerPitchAtMcrBollard':add(g,s,'propellerPitchAtMcrBollard',bollard,ex)
    return g
def oracle084(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);pt=lit(g,s,'propellerType');kn=lit(g,s,'pitchValueKnown')
    if pt!='CP':return True
    b=qnum(g,s,'propellerPitchAtMcrBollard')
    if kn is True:return b is not None
    f=qnum(g,s,'propellerPitchAtMcrFreeRunning');return close(b,.7*f if f is not None else None)

def build085(cid,with_table=True,badref=False,miss_ev=False):
    g,ex,s=new(cid);add(g,s,'propellerDiameter',5,ex);add(g,s,'propellerRotationalSpeedAtMaximumContinuousRatingBollard',120,ex)
    if with_table:tablecase(g,ex,s,'traficomTable6Dash9',None,None,None,False,badref,miss_ev)
    return g
def oracle085(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if qnum(g,s,'propellerRotationalSpeedAtMaximumContinuousRatingBollard') is None or qnum(g,s,'propellerDiameter') is None:return False
    cases=list(g.objects(s,NLTL.hasTableLookupCase))
    if not cases:return True
    c=cases[0];return one(g,c,'tableReference')==NLTL.traficomTable6Dash9 and one(g,c,'lookupSelectionEvidence') is not None

def build086(cid,**kw):return build084(cid,**kw)
def oracle086(g):return oracle084(g)

def build087(cid,ratio=0.4,missing=False):
    g,ex,s=new(cid)
    if not missing:add(g,s,'inertiaRatioIeIt',ratio,ex)
    return g
def oracle087(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);r=qnum(g,s,'inertiaRatioIeIt');return r is not None and 0<=r<=1

def build088(cid,known=False,badref=False,miss_ev=False):g,ex,s=new(cid);tablecase(g,ex,s,'traficomTable6Dash10','maximumEngineTorque',200,'maximumEngineTorqueKnown',known,badref,miss_ev);return g
def oracle088(g):return oracle_table(g,'traficomTable6Dash10','maximumEngineTorque','maximumEngineTorqueKnown')

def build091(cid,purpose='strength',missing=None):
    g,ex,s=new(cid);case=link(g,s,'hasIceMillingSequenceCase',ex,'milling','iceMillingSequenceCase');lc=link(g,case,'hasPropulsionLoadCase',ex,'loadCase','loadCase');add(g,case,'propellerIceMillingLoadSequence','half-sine blade impact sequence',ex)
    if missing!='loadCasePurpose':add(g,lc,'loadCasePurpose',NLTL.propulsionLineStrengthEvaluationPurpose if purpose=='strength' else NLTL.stallingAnalysisPurposeValue,ex)
    if missing!='propulsionLineStrengthEvaluation':add(g,case,'propulsionLineStrengthEvaluation','required',ex)
    if missing!='stallingAnalysisPurpose':add(g,case,'stallingAnalysisPurpose','not intended',ex)
    return g
def oracle091(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);c=one(g,s,'hasIceMillingSequenceCase');
    if c is None:return False
    lc=one(g,c,'hasPropulsionLoadCase');
    return lc is not None and one(g,lc,'loadCasePurpose')==NLTL.propulsionLineStrengthEvaluationPurpose and lit(g,c,'propulsionLineStrengthEvaluation') is not None and lit(g,c,'stallingAnalysisPurpose') is not None

def build101(cid,route='formula',bad=False,missing=None):
    g,ex,s=new(cid)
    if route=='analysis':
        a=link(g,s,'approvedNonlinearBladeStressAnalysis',ex,'analysis','evidenceArtifact');add(g,s,'bladeFailureLoadWeakestDirectionConfirmed',True,ex);add(g,s,'bladeFailureUltimateLoad',500,ex);return g
    c=.5;t=.08;sy=300;su=600;D=4;r=.3;sig=.6*sy+.4*su;F=300*c*t*t*sig/(.8*D-2*r);tip=.5
    vals={'bladeChordLengthAtWeakestSection':c,'bladeMaximumThicknessAtWeakestSection':t,'bladeMinimumYieldStrength':sy,'bladeUltimateTensileStrength':su,'bladeReferenceStrength1':sig,'propellerDiameter':D,'bladeCylindricalRootRadius':r,'bladeFailureLoadApplicationRadiusRatio':.8,'bladeTipOffset':tip,'bladeFailureUltimateLoad':F+(10 if bad else 0)}
    for x,v in vals.items():
        if x!=missing:add(g,s,x,v,ex)
    if missing!='bladeFailureLoadWeakestDirectionConfirmed':add(g,s,'bladeFailureLoadWeakestDirectionConfirmed',True,ex)
    return g
def oracle101(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if one(g,s,'approvedNonlinearBladeStressAnalysis') is not None:return qnum(g,s,'bladeFailureUltimateLoad') is not None and lit(g,s,'bladeFailureLoadWeakestDirectionConfirmed') is True
    names=['bladeChordLengthAtWeakestSection','bladeMaximumThicknessAtWeakestSection','bladeMinimumYieldStrength','bladeUltimateTensileStrength','bladeReferenceStrength1','propellerDiameter','bladeCylindricalRootRadius','bladeFailureLoadApplicationRadiusRatio','bladeTipOffset','bladeFailureUltimateLoad'];v={t:qnum(g,s,t) for t in names}
    if any(x is None for x in v.values()) or lit(g,s,'bladeFailureLoadWeakestDirectionConfirmed') is not True:return False
    sig=.6*v['bladeMinimumYieldStrength']+.4*v['bladeUltimateTensileStrength'];den=.8*v['propellerDiameter']-2*v['bladeCylindricalRootRadius'];
    if den<=0:return False
    F=300*v['bladeChordLengthAtWeakestSection']*v['bladeMaximumThicknessAtWeakestSection']**2*sig/den
    return close(v['bladeReferenceStrength1'],sig) and close(v['bladeFailureLoadApplicationRadiusRatio'],.8) and close(v['bladeFailureUltimateLoad'],F)

def build102(cid,route='formula',bad=False,missing=None):
    g,ex,s=new(cid)
    if route=='analysis':link(g,s,'approvedSpindleTorqueStressAnalysis',ex,'analysis','evidenceArtifact');add(g,s,'maximumSpindleTorque',120,ex);return g
    ear=.45;Z=4;le=.3;te=.25;F=500;fac=max(.3,.7*(1-((4*ear)/Z)**3));Q=max(le,.8*te)*fac*F
    vals={'bladeExpandedAreaRatio':ear,'propellerBladeCount':Z,'leadingEdgeChordPortionAtZeroPointEightRadius':le,'trailingEdgeChordPortionAtZeroPointEightRadius':te,'extremeIceForce':F,'bladeFailureSpindleTorqueFactor':fac,'bladeFailureSpindleTorque':Q+(10 if bad else 0),'maximumSpindleTorque':Q+(10 if bad else 0)}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle102(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    if one(g,s,'approvedSpindleTorqueStressAnalysis') is not None:return qnum(g,s,'maximumSpindleTorque') is not None
    ear=qnum(g,s,'bladeExpandedAreaRatio');Z=lit(g,s,'propellerBladeCount');le=qnum(g,s,'leadingEdgeChordPortionAtZeroPointEightRadius');te=qnum(g,s,'trailingEdgeChordPortionAtZeroPointEightRadius');F=qnum(g,s,'extremeIceForce');fac=qnum(g,s,'bladeFailureSpindleTorqueFactor');Q=qnum(g,s,'bladeFailureSpindleTorque');mx=qnum(g,s,'maximumSpindleTorque')
    if None in [ear,Z,le,te,F,fac,Q,mx]:return False
    f=max(.3,.7*(1-((4*ear)/Z)**3));q=max(le,.8*te)*f*F;return close(fac,f) and close(Q,q) and close(mx,q)

def build103(cid,factor=.3,missing=None):
    g,ex,s=new(cid);vals={'bladeFailureSpindleTorqueFactor':factor,'leadingEdgeChordPortionAtZeroPointEightRadius':.3,'trailingEdgeChordPortionAtZeroPointEightRadius':.25,'maximumSpindleTorque':100}
    for t,v in vals.items():
        if t!=missing:add(g,s,t,v,ex)
    return g
def oracle103(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None);f=qnum(g,s,'bladeFailureSpindleTorqueFactor');return f is not None and f>=.3 and qnum(g,s,'leadingEdgeChordPortionAtZeroPointEightRadius') is not None and qnum(g,s,'trailingEdgeChordPortionAtZeroPointEightRadius') is not None and qnum(g,s,'maximumSpindleTorque') is not None

def build104(cid,n=1,bad=False,missing=False):
    g,ex,s=new(cid);add(g,s,'pyramidStrengthPrinciple','blade loss shall not significantly damage other shaft-line components',ex)
    for i in range(n):
        c=link(g,s,'hasPropellerShaftLineComponent',ex,f'component{i}','propellerShaftLineComponent');
        if not missing:add(g,c,'significantDamageFromBladeLoss',bad and i==0,ex);add(g,c,'shaftLineComponentDamage',bad and i==0,ex)
    return g
def oracle104(g):
    s=next(g.subjects(RDF.type,NLTL.ship),None)
    for c in g.objects(s,NLTL.hasPropellerShaftLineComponent):
        if lit(g,c,'significantDamageFromBladeLoss') is not False:return False
    return True

OR={'TRF-081':oracle081,'TRF-082':oracle082,'TRF-083':oracle083,'TRF-084':oracle084,'TRF-085':oracle085,'TRF-086':oracle086,'TRF-087':oracle087,'TRF-088':oracle088,'TRF-091':oracle091,'TRF-101':oracle101,'TRF-102':oracle102,'TRF-103':oracle103,'TRF-104':oracle104}
CASES=[]
def ac(r,suf,exp,rat,g):CASES.append({'requirement_id':r,'case_id':f'{r}-{suf}','expected':exp,'rationale':rat,'graph':g})
# 081
ac('TRF-081','P01','PASS','Forward branch governs.',build081('TRF-081-P01',ff=150,fb=80,T=100));ac('TRF-081','P02','PASS','Backward branch can govern.',build081('TRF-081-P02',ff=40,fb=180,T=20));ac('TRF-081','F01','FAIL','Wrong design thrust max.',build081('TRF-081-F01',bad=True));
for i,t in enumerate(['forwardIceThrust','backwardPropellerShaftDesignThrust','hydrodynamicBollardThrust'],2):ac('TRF-081',f'F0{i}','FAIL',f'Missing {t}.',build081(f'TRF-081-F0{i}',missing=t))
# tables 082/083/088
for r,builder in [('TRF-082',build082),('TRF-083',build083),('TRF-088',build088)]:
    ac(r,'P01','PASS','Known direct value branch.',builder(r+'-P01',known=True));ac(r,'P02','PASS','Unknown value uses canonical table lookup.',builder(r+'-P02'));ac(r,'F01','FAIL','Wrong table reference.',builder(r+'-F01',badref=True));ac(r,'F02','FAIL','Missing lookup selection evidence.',builder(r+'-F02',miss_ev=True))
#084/086
for r,builder in [('TRF-084',build084),('TRF-086',build086)]:
    ac(r,'P01','PASS','Unknown CP pitch uses 0.7 free-running pitch.',builder(r+'-P01',known=False,free=1.2));ac(r,'P02','PASS','Known CP bollard pitch accepted.',builder(r+'-P02',known=True,free=1.2,bollard=1.0));ac(r,'P03','PASS','Non-CP branch not applicable.',builder(r+'-P03',ptype='FP',known=False,bollard=.2));ac(r,'F01','FAIL','Incorrect 0.7 calculation.',builder(r+'-F01',known=False,free=1.0,bollard=.8));ac(r,'F02','FAIL','Missing free-running pitch.',builder(r+'-F02',known=False,missing='propellerPitchAtMcrFreeRunning'))
#085
ac('TRF-085','P01','PASS','Known/available bollard speed present.',build085('TRF-085-P01',with_table=False));ac('TRF-085','P02','PASS','Canonical Table 6-9 lookup also represented.',build085('TRF-085-P02'));ac('TRF-085','F01','FAIL','Wrong lookup table.',build085('TRF-085-F01',badref=True));ac('TRF-085','F02','FAIL','Missing lookup evidence.',build085('TRF-085-F02',miss_ev=True))
#087
ac('TRF-087','P01','PASS','Valid inertia ratio supporting reduction to examined-component speed.',build087('TRF-087-P01',.4));ac('TRF-087','P02','PASS','Boundary inertia ratio one.',build087('TRF-087-P02',1));ac('TRF-087','F01','FAIL','Missing reduction ratio.',build087('TRF-087-F01',missing=True));ac('TRF-087','F02','FAIL','Invalid inertia ratio.',build087('TRF-087-F02',1.2))
#091
ac('TRF-091','P01','PASS','Milling sequence used for shaft-line strength evaluation.',build091('TRF-091-P01'));ac('TRF-091','F01','FAIL','Milling sequence misused for stalling analysis.',build091('TRF-091-F01',purpose='stalling'));ac('TRF-091','F02','FAIL','Load-case purpose missing.',build091('TRF-091-F02',missing='loadCasePurpose'));ac('TRF-091','F03','FAIL','Strength-evaluation statement missing.',build091('TRF-091-F03',missing='propulsionLineStrengthEvaluation'))
#101
ac('TRF-101','P01','PASS','Explicit formula route.',build101('TRF-101-P01'));ac('TRF-101','P02','PASS','Approved nonlinear analysis route.',build101('TRF-101-P02',route='analysis'));ac('TRF-101','F01','FAIL','Formula result wrong.',build101('TRF-101-F01',bad=True));ac('TRF-101','F02','FAIL','Missing reference strength.',build101('TRF-101-F02',missing='bladeReferenceStrength1'));ac('TRF-101','F03','FAIL','Missing weakest-direction confirmation.',build101('TRF-101-F03',missing='bladeFailureLoadWeakestDirectionConfirmed'))
#102
ac('TRF-102','P01','PASS','Formula route including 0.3 floor.',build102('TRF-102-P01'));ac('TRF-102','P02','PASS','Approved stress-analysis route.',build102('TRF-102-P02',route='analysis'));ac('TRF-102','F01','FAIL','Wrong spindle torque.',build102('TRF-102-F01',bad=True));ac('TRF-102','F02','FAIL','Missing expanded area ratio.',build102('TRF-102-F02',missing='bladeExpandedAreaRatio'));ac('TRF-102','F03','FAIL','Missing maximum spindle torque.',build102('TRF-102-F03',missing='maximumSpindleTorque'))
#103
ac('TRF-103','P01','PASS','Cspex at floor 0.3.',build103('TRF-103-P01',.3));ac('TRF-103','P02','PASS','Cspex above floor.',build103('TRF-103-P02',.5));ac('TRF-103','F01','FAIL','Cspex below mandatory floor.',build103('TRF-103-F01',.29));ac('TRF-103','F02','FAIL','Missing leading-edge chord portion.',build103('TRF-103-F02',missing='leadingEdgeChordPortionAtZeroPointEightRadius'))
#104
ac('TRF-104','P01','PASS','One shaft-line component protected by pyramid principle.',build104('TRF-104-P01',1));ac('TRF-104','P02','PASS','Multiple components protected.',build104('TRF-104-P02',3));ac('TRF-104','P03','PASS','Zero components does not create existence obligation.',build104('TRF-104-P03',0));ac('TRF-104','F01','FAIL','Blade loss causes significant component damage.',build104('TRF-104-F01',2,bad=True));ac('TRF-104','F02','FAIL','Component damage assessment missing.',build104('TRF-104-F02',1,missing=True))
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
    mp=ROOT/'manifests'/'traficom_batch_h_manifest.jsonl'; lp=ROOT/'locks'/'traficom_batch_h_fixture_lock.json'
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
CLAUSES={'TRF-081':'6.5.2.1-6.5.2.2','TRF-082':'6.5.2.2','TRF-083':'6.5.3.1','TRF-084':'6.5.3.1','TRF-085':'6.5.3.2','TRF-086':'6.5.3.2','TRF-087':'6.5.3.3','TRF-088':'6.5.3.3','TRF-091':'6.5.3.4','TRF-101':'6.5.4.1','TRF-102':'6.5.4.2','TRF-103':'6.5.4.2','TRF-104':'6.6.1'}
def generate():
    for p in [ROOT/'rdf'/'TRF',ROOT/'specifications'/'TRF',ROOT/'manifests',ROOT/'locks',ROOT/'scripts']:p.mkdir(parents=True,exist_ok=True)
    lp=ROOT/'locks'/'traficom_batch_h_fixture_lock.json'
    if lp.exists():raise SystemExit('Batch G lock already exists. Refusing to overwrite frozen fixtures.')
    rows=[]
    for c in CASES:
        r=c['requirement_id']; od=ROOT/'rdf'/'TRF'/r;od.mkdir(parents=True,exist_ok=True); p=od/f"{c['case_id']}.ttl"
        if p.exists():raise SystemExit(f'Refusing to overwrite existing RDF fixture: {p}')
        c['graph'].serialize(destination=p,format='turtle'); rows.append({'requirement_id':r,'case_id':c['case_id'],'expected':c['expected'],'rdf_path':str(p.relative_to(ROOT)),'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'verification_mode':MODES[r],'source_oracle_rationale':c['rationale'],'generated_shacl_inspected':False})
    mp=ROOT/'manifests'/'traficom_batch_h_manifest.jsonl';mp.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    for r in REQS:(ROOT/'specifications'/'TRF'/f'{r}.json').write_text(json.dumps({'requirement_id':r,'source_id':'SRC-TRAFICOM-2021','source_clause':CLAUSES[r],'source_lock_id':INDEX['sourceLockId'],'r13_contract':CONTRACTS[r],'test_cases':[{'case_id':x['case_id'],'expected':x['expected'],'rationale':x['rationale']} for x in CASES if x['requirement_id']==r],'benchmark_policy':'Source/R13-defined behavioral oracle created without inspecting generated SHACL.'},indent=2)+'\n')
    print('Pre-freeze validation'); assert validate(False)
    vp=ROOT/'scripts'/'validate_traficom_batch_h.py';shutil.copy2(Path(__file__).resolve(),vp);vp.chmod(0o755)
    frozen={}
    for c in CASES:frozen[str((ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl").relative_to(ROOT))]=sha(ROOT/'rdf'/'TRF'/c['requirement_id']/f"{c['case_id']}.ttl")
    frozen[str(mp.relative_to(ROOT))]=sha(mp)
    for r in REQS:
        p=ROOT/'specifications'/'TRF'/f'{r}.json';frozen[str(p.relative_to(ROOT))]=sha(p)
    lp.write_text(json.dumps({'benchmark':'TRAFICOM Behavioral Benchmark Batch H','source_lock_id':INDEX['sourceLockId'],'source_id':'SRC-TRAFICOM-2021','requirements':REQS,'requirement_count':len(REQS),'case_count':len(CASES),'generated_without_inspecting_generated_shacl':True,'previous_frozen_batches_modified':False,'frozen_files':frozen},indent=2)+'\n')
    print('\nFrozen validation'); assert validate(True)
if __name__=='__main__':
    if Path(__file__).name.startswith('validate_'):sys.exit(0 if validate(True) else 1)
    generate()
