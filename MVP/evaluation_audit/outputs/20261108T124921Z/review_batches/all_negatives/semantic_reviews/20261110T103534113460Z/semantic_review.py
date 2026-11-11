#!/usr/bin/env python3
"""Review saved semantic blockers. No SHACL validation, query execution or generation.

Only the 201 frozen PAIR_VERIFIED semantic blockers are candidates. Source-
reviewed branch guards select applicability before repaired outcomes are checked.
Unsupported constructs remain unresolved. The historic aggregate reports stay
untouched; this extension emits a new delta report and common-subset counts.
"""
import argparse
import copy
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'full_audit'))
from common import audit,BASE,OUT,atomic
from prepare import types_of,ONTO
from rdflib import Graph,URIRef,Literal,BNode,RDF,XSD
from rdflib.collection import Collection
from evaluate import parameter
N,Q,S=audit.N,audit.Q,audit.S

# Source/contract applicability assertions, reviewed against the saved clause.
# This list never uses whichever branch happens to accept the repaired graph.
GUARDS={
 'I2-046':['polarClassRequirementsApplicable','polarClass'],
 'I2-066':['withinIceStrengthenedArea'],
 'IMO-014':['codeApplicable'],
 'IMO-018':['iceCapabilityMethodologyApplicable'],
 'IMO-019':['shipOperatesInLowAirTemperature'],
 'IMO-026':['iceCapabilityMethodologyApplicable'],
 'IMO-028':['shipIceStrengthened'],
 'IMO-030':['iceOperationApplicable'],
 'IMO-033':['iceAccretionLikely'],
 'IMO-034':['iceAccretionLikely'],
 'IMO-050':['installedInExposedPosition'],
 'IMO-060':['fixedWaterSystemSeparateFromMainFirePumps','independentSeaSuctionUsed'],
 'IMO-066':['shipExposedToIceAccretion'],
 'IMO-068':['shipOperatesInIceCoveredWaters','directEvacuationOntoIceApplicable'],
 'IMO-069':['addedSurvivalDeviceRequiresPower'],
 'IMO-071':['immersionSuitRequired'],
 'IMO-072':['extendedDarknessOperation'],
 'IMO-075':['survivalEquipmentRequired'],
 'IMO-083':['iceAccretionLikely'],
 'IMO-084':['requiredSensorProjectsBelowHull'],
 'IMO-087':['plannedOrActualLatitude'],
 'IMO-088':['operatesOnlyInContinuousDaylight'],
 'IMO-089':['icebreakerEscortOperation'],
 'IMO-098':['shipOperatesInLowAirTemperature'],
 'IMO-107':['polarWaterOperationApplicable'],
 'IMO-108':['shipCategory','constructionDate','aggregateOilFuelCapacity','individualOilFuelTankCapacity'],
 'IMO-113':['polarWaterOperationApplicable'],
 'IMO-121':['foodWasteDischargeOccurs'],
 'IMO-125':['polarWaterOperationApplicable'],
 'IMO26-008':['directBridgeVisibilityCompliancePossible'],
 'IMO26-013':['plannedOrActualLatitude'],
 'IMO26-017':['polarCodeChapter11Applicable'],
 'IMO26-018':['polarCodeChapter11Dash1Applicable','safetyManagementSystemImplemented'],
 'TRF-029':['directAnalysisUsed'],
 'TRF-040':['iceClass','openWaterServiceSpeed','weatherDeckBelowUpperIceBelt'],
 'TRF-050':['shellPlateButtCrossing'],
 'TRF-067':['iceClass'],
 'TRF-082':['bollardThrustKnown'],
 'TRF-083':['rotationalSpeedKnown'],
 'TRF-126':['propulsionEngineReversalRequiredForAstern'],
 'TRF-127':['airReceiverServesAdditionalPurpose'],
 'TRF-128':['iceClass','propulsionEngineReversalRequiredForAstern'],
 'TRF-129':['iceNavigationCondition','navigatingInIce'],
}
GUARDS.update({
 'IMO-014':['polarCodeApplies'], 'IMO-050':['fireSafetyComponentExposed'],
 'IMO-069':['addedLifeSavingDeviceRequiresPower'],
 'IMO-075':['personalOrGroupSurvivalEquipmentRequired'],
 'IMO-107':['shipOperatesInPolarWaters'], 'IMO-113':['shipOperatesInPolarWaters'],
 'IMO-117':['sewageDischargeUsesTreatmentPlant'], 'IMO-121':['foodWasteDischargeToSea'],
 'IMO-125':['shipOperatesInPolarWaters'],
 'IMO26-017':['polarCodeChapter11Dash1Applicable'],
 'TRF-015':['navigatingInIce'], 'TRF-036':['iceClass'],
 'TRF-126':['propulsionEngineReversedForAstern'],
 'TRF-128':['iceClass','propulsionEngineReversedForAstern'],
})
# Independently source-backed numeric semantics, not learned from shape bounds.
BOUNDS={
 ('I2-046','internalStructureCorrosionAbrasionAddition','minInclusive'):'1',
 ('IMO-033','deckIcingAllowance','hasValue'):'30',
 ('IMO-033','sideIcingAllowance','hasValue'):'7.5',
 ('IMO-087','gnssCompassOrEquivalentCount','minInclusive'):'1',
 ('IMO26-013','gnssCompassOrEquivalentCount','minInclusive'):'1',
 ('IMO-108','oilFuelTankOuterShellSeparation','minInclusive'):'0.76',
 ('IMO-121','foodWasteScreenOpening','maxInclusive'):'25',
 ('TRF-128','airReceiverChargingTime','maxInclusive'):'1',
}
BOUNDS.update({('IMO-009','landOriginIceConcentration','maxExclusive'):'1',
 ('IMO-009','totalIceConcentration','maxInclusive'):'1',
 ('IMO-089','visibilityRange','minInclusive'):'2',
 ('IMO-121','requiredScreenOpening','maxInclusive'):'25'})
# Exact source-approved alternatives; sh:in is not accepted merely because the
# repaired value happens to be on a generated whitelist.
ENUMS={
 ('IMO-048','approvingAuthority'):['Administration','recognized organization accepted by the Administration'],
 ('IMO-048','approvalStandard'):['standard acceptable to the Organization','another standard offering an equivalent level of safety'],
 ('IMO26-005','intendedAreaSuitabilityApprovalStatus'):['https://w3id.org/nltl/vocab#evidenceStateApproved'],
}
# Manually inspected full SELECTs. Hash bindings are frozen in each review plan.
# Complex table selection, applicability-counterfactual changes, and schedule
# directionality are deliberately left outside these simple correspondences.
QUERY_REVIEWS={
'I2-004':('upperIceWaterlineDisplacement','The NOT EXISTS greater-case subquery selects a maximal linked case displacement, then compares DUI to that maximum. Both operands and the tolerance expression were inspected; the retained negative is outside that tolerance and the repair restores the exact maximum.'),
'I2-042':('flangeWidth','The joined quantities are flangeWidth and netWebThickness; the SELECT returns only when flangeWidth < 5*netWebThickness, the explicit source inequality.'),
'I2-055':('designStress','The SELECT joins designStress and permissibleStress and returns when the decimal design value exceeds the permissible value. The unrelated stored status flag is not its failure condition.'),
'IMO-004':('iceTypeClassification','Sea-ice origin, <=1 winter growth and 0.3..2.0 m qualify the case; NOT EXISTS requires firstYearIce on the same ship. Those selectors do not change in the repair.'),
'IMO-009':('landOriginIceConcentration totalIceConcentration','For bergy waters, the NOT EXISTS body requires land concentration <1 and total <=1 in the explicitly frozen tenths scale (contract comparisonModel), with canonical dimensionless quantities. The one changed concentration is the failing conjunct.'),
'IMO-038':('longitudinalDamageExtent verticalDamageExtent selectedVerticalDamagePosition','The SELECTs implement 0.045L/0.015L by the unchanged forward selector, min(0.20T,longitudinal), and vertical-position bounds 0..1.20T. The corresponding disjunct and stored numeric delta were reviewed; tolerances are recorded rather than treated as a general source equivalence.'),
'IMO-041':('hydraulicFluidFreezingOrViscosityControlPresent','Under the unchanged hydraulic actuation selector, NOT EXISTS tests the same ship-owned fluid-control assertion for true.'),
'IMO-048':('approvingAuthority approvalStandard materialApprovalStatus polarServiceTemperature','The NOT EXISTS conjunction exactly names the two authorized authority strings, two acceptable/equivalent-standard strings, approved state and Celsius PST quantity. The source contract stringValuePolicies confirms the alternatives.'),
'IMO-057':('maintainedTemperature','The SELECT traverses each recognized fire-pump type to its containing compartment and requires a decimal Celsius temperature >0. The repaired unit belongs to that same containing compartment, rather than to the ship or pump.'),
'IMO-065':('survivalSupportDuration','The joined support duration must not be shorter than maximumExpectedRescueTime. The query compares these quantities, matching the source maximum-rescue-time requirement.'),
'IMO-082':('clearViewAsternStatus','The unchanged asternViewRequiredBridgeConfiguration guard activates a NOT EXISTS check for a boolean true clearViewAsternStatus on the ship.'),
'IMO-084':('sensorIceProtectionPresent','The unchanged requiredSensorProjectsBelowHull=true activates NOT EXISTS sensorIceProtectionPresent=true on the same owner.'),
'IMO-086':('independentFromHeadingMeans','For each linked heading means, NOT EXISTS checks a different independence target that is itself in the same ship-owned inventory. A self/out-of-inventory target does not satisfy that join.'),
'IMO-087':('gnssCompassOrEquivalentCount connectedToMainPower connectedToEmergencyPower','Latitude >80 activates the disjunction: absent count>=1, absent main-power link, or absent emergency-power link. The single repaired assertion is the corresponding failing disjunct.'),
'IMO-099':('communicationDeviceAvailability','The SELECT compares communication availability with maximumExpectedRescueTime, rejecting availability < rescue duration; the canonical quantities use the common day scale.'),
'IMO-109':('cargoTankOuterShellSeparation','The source category/date/cargo-oil/non-tanker guards are unchanged. NOT EXISTS requires decimal metre separation >=0.76 on the ship; the missing or too-small source field is the failing condition.'),
'IMO-119':('approvedSewageTreatmentPlantUsed administrationDischargeApprovalStatus','Category A/B, concentration >1 in tenths, extended operation and occurring discharge activate the requirement. The inspected conjunction/disjunction rejects a missing true plant-use assertion or missing approved Administration state.'),
'IMO26-012':('independentFromHeadingMeans','The SELECT focus is a heading means: it requires a same-ship inventory edge, a different independence target and a same-ship edge for that target. The wrong/self/outside target is precisely the intended defect.'),
'IMO26-013':('gnssCompassOrEquivalentCount connectedToMainPower connectedToEmergencyPower','The latitude quantity is in degrees and >80. The SELECT tests count>=1 and both ship-owned power connections, with each failure as a separate disjunct.'),
'TRF-013':('operatingAftDraught','The SELECT joins fore/aft operating and minimum/maximum ice-class draught quantities. The repaired aft value is the only out-of-range conjunct/disjunct; fore and all limits remain unchanged.'),
'TRF-015':('operatingDraught operatingTrim loadingCalculationSeaWaterSalinity','Under navigatingInIce=true, the first SELECT compares operating draught/trim with UIWL/maximum trim. The separate salinity SELECT tests loading versus intended-route salinity in the canonical salinity unit. Only the reported query and its corresponding field are admitted.'),
'TRF-024':('deliveryDate','The UNION explicitly includes the absent valid deliveryDate branch, which prevents the source deadline calculation. The other date assertions and class selectors remain fixed.'),
'TRF-035':('ruleLength','The SELECT joins ruleLength and classificationSocietyRuleLength, then tests numeric inequality, exactly the rule-length identity in the source.'),
'TRF-045':('span frameSpanWithinIceStrengtheningZone','ordinaryFrameScantlingsUsed=true activates NOT EXISTS a positive metre span and canonical metre ice portion less than 0.15*span. Missing span or wrong ice-portion unit is the sole broken conjunct in these pairs.'),
'TRF-052':('antitrippingSupportSpacing','Without the true equivalent-direct-calculation flag, asymmetry or web angle <90 activates NOT EXISTS spacing<=1300 mm. The source-backed 1300 mm bound and unchanged trigger were inspected.'),
'TRF-056':('shipSideDeflection hasHatchCoverDesignEvidence hasHatchFittingDesignEvidence','The SELECT joins the applicable hatch to its ship and tests opening>B/2. Its OR of NOT EXISTS checks hatch-owned deflection and typed cover/fitting evidence. The field restored or moved to that hatch is the sole failed conjunct.'),
'TRF-074':('propulsionSystemDesignedForIceClass','IB/IC plus top-depth<hi activate NOT EXISTS redesign for IA, on the same ship; the omitted redesign assertion is the intended failure.'),
'TRF-084':('propellerPitchAtMcrFreeRunning','The unchanged CP and pitchValueKnown=false guard activates the missing canonical free/bollard pitch pair with bollard=0.7*free. The free-running quantity is missing, not merely numerically discrepant.'),
'TRF-127':('airReceiverCapacity','The unchanged additional-purpose=true flag activates the numeric capacity<additional-purpose-required-capacity comparison, matching the source extra-capacity obligation.'),
}
QUERY_REVIEWS.update({
 'IMO-069':('devicePowerSourceIndependentOfMainPower','addedLifeSavingDeviceRequiresPower=true activates NOT EXISTS a true devicePowerSourceIndependentOfMainPower assertion on the ship; the sole changed power independence field is the tested defect.'),
 'IMO-075':('availableSurvivalEquipmentCapacity','The unchanged equipment-required flag activates capacity < CEIL(personsOnBoard*1.10), exactly the source 110% coverage constraint for integral equipment capacity.'),
 'IMO-017':('polarCertificateValidityDates hasCertificateScheduleDateRecord','The NLTL_v2 UNION checks each Polar validity/survey/endorsement date against an equal SOLAS schedule date of the same category; the Single-shot query checks the reverse join. In F01 the validity dates differ. In F05 the NLTL_v2 survey branch has no schedule record. The other date categories remain matched.'),
 'I2-048':('requiredHullStructuralSteelGrade actualHullStructuralSteelGrade','Local Table-8 cell only: PC3, normal strength, material class One, thickness 17.5 mm selects source grade D. In this query band=3 and PC1-5 select D in the second IF after the B branch is false. F010 fails !BOUND(required); F011 fails required!=D; F012 fails actualRank<requiredRank; F013 fails the normal-strength family membership test. The table implementation outside this observed cell is not certified by this binding.'),
})
QUERY_BINDINGS_PATH=Path(__file__).with_name('semantic_query_bindings_20261110.json')
QUERY_BINDINGS=audit.read(QUERY_BINDINGS_PATH) if QUERY_BINDINGS_PATH.exists() else []

class Unsupported(Exception):pass

def local(x):return str(x).split('#')[-1]
def seq(g,h):return list(Collection(g,h))
def number(x):
 from decimal import Decimal
 return Decimal(str(x))
def graph_hash(p):return audit.sha(p)
def compact_graph(g):return sorted(audit.triples(g))

def path_nodes(g,focus,p,sg):
 if isinstance(p,URIRef):return list(g.objects(focus,p)),[(focus,p)]
 if p is None:return [focus],[]
 parts=seq(sg,p)
 if not parts:raise Unsupported('Unreviewed inverse/alternative/empty path')
 values=[focus];edges=[]
 for prop in parts:
  if not isinstance(prop,URIRef):raise Unsupported('Complex path element')
  nxt=[]
  for s in values:nxt.extend(g.objects(s,prop));edges.append((s,prop))
  values=nxt
 return values,edges

IGNORED={RDF.type,S.path,S.message,S.name,S.description,S.order,S.severity,S.deactivated,S.targetClass,S.targetSubjectsOf,S.targetObjectsOf,S.targetNode,S['class'],S.datatype,S.nodeKind,S.minCount,S.maxCount,S.hasValue,S['in'],S.minInclusive,S.maxInclusive,S.minExclusive,S.maxExclusive,S.property,S.node,S['and'],S['or'],S.xone}

def rdfs_types(g,value):
    result=types_of(g,value)
    for s,p in g.subject_predicates(value):result.update(ONTO.objects(p,audit.RDFS.range))
    for p,o in g.predicate_objects(value):result.update(ONTO.objects(p,audit.RDFS.domain))
    pending=list(result)
    while pending:
        for parent in ONTO.objects(pending.pop(),audit.RDFS.subClassOf):
            if parent not in result:result.add(parent);pending.append(parent)
    return result

def trace(sg,node,g,focus,scope=None,depth=0):
 """Finite static constraint trace for a saved logical wrapper, not a validator.

 Unsupported or inference-dependent failures return unknown, never credit.
 Every visited constraint and applicable branch is retained in the proof.
 """
 if depth>24:return dict(ok=None,failures=[],unknown=['Recursive/deep shape'])
 if sg.value(node,S.deactivated)==Literal(True):return dict(ok=True,failures=[],unknown=[],deactivated=True)
 unsupported=[str(p) for p in sg.predicates(node) if p not in IGNORED]
 if unsupported:return dict(ok=None,failures=[],unknown=sorted(set(unsupported)))
 path=sg.value(node,S.path)
 try:vals,edges=path_nodes(g,focus,path,sg)
 except Exception as e:return dict(ok=None,failures=[],unknown=[str(e)])
 if path is not None:
  for owner,prop in edges:
   if str(prop).startswith(str(N)):scope=(str(owner),str(prop))
 failures=[];unknown=[];children=[]
 def fail(kind,expected,actual=None):failures.append(dict(kind=kind,owner=str(focus),path=str(path) if isinstance(path,URIRef) else [str(x) for x in seq(sg,path)] if path else None,scope=list(scope) if scope else None,expected=expected,actual=actual))
 for pred,compare in [(S.minCount,lambda a,b:a>=b),(S.maxCount,lambda a,b:a<=b)]:
  for value in sg.objects(node,pred):
   if not compare(len(vals),int(value)):fail(local(pred),int(value),len(vals))
 for required in sg.objects(node,S.hasValue):
  if required not in vals:fail('hasValue',required.n3(),[v.n3() for v in vals])
 for head in sg.objects(node,S['in']):
  allowed=seq(sg,head)
  for value in vals:
   if value not in allowed:fail('in',[v.n3() for v in allowed],value.n3())
 for cls in sg.objects(node,S['class']):
  for value in vals:
   if cls not in rdfs_types(g,value):unknown.append('Class requires further inference or is false: '+str(cls))
 for kind in sg.objects(node,S.nodeKind):
  kinds={S.IRI:(URIRef,),S.BlankNode:(BNode,),S.Literal:(Literal,),S.BlankNodeOrIRI:(BNode,URIRef),S.IRIOrLiteral:(URIRef,Literal),S.BlankNodeOrLiteral:(BNode,Literal)}
  if kind not in kinds:unknown.append('Unknown node kind')
  else:
   for value in vals:
    if not isinstance(value,kinds[kind]):fail('nodeKind',str(kind),value.n3())
 for dt in sg.objects(node,S.datatype):
  for value in vals:
   if not isinstance(value,Literal) or (value.datatype or XSD.string)!=dt:fail('datatype',str(dt),value.n3())
 for pred,compare in [(S.minInclusive,lambda a,b:a>=b),(S.maxInclusive,lambda a,b:a<=b),(S.minExclusive,lambda a,b:a>b),(S.maxExclusive,lambda a,b:a<b)]:
  for bound in sg.objects(node,pred):
   for value in vals:
    try:valid=compare(value.toPython(),bound.toPython()) if isinstance(value,Literal) and value.datatype==XSD.date and bound.datatype==XSD.date else compare(number(value),number(bound))
    except Exception:unknown.append('Unsupported numeric/date comparator');continue
    if not valid:fail(local(pred),str(bound),str(value))
 for child in sg.objects(node,S.property):
  for value in vals:
   result=trace(sg,child,g,value,scope,depth+1);children.append(result);failures+=result['failures'];unknown+=result['unknown']
 for child in sg.objects(node,S.node):
  for value in vals:
   result=trace(sg,child,g,value,scope,depth+1);children.append(result);failures+=result['failures'];unknown+=result['unknown']
 logical=[]
 for pred in [S['and'],S['or'],S.xone]:
  for head in sg.objects(node,pred):
   for value in vals:
    branches=[trace(sg,c,g,value,scope,depth+1) for c in seq(sg,head)]
    known=all(b['ok'] is not None for b in branches);passing=sum(b['ok'] is True for b in branches)
    ok=(all(b['ok'] for b in branches) if pred==S['and'] else passing>=1 if pred==S['or'] else passing==1) if known else None
    logical.append(dict(operator=local(pred),ok=ok,branches=branches))
    if ok is False:
     if pred==S.xone and passing>1:fail('xone_multiple',1,passing)
     else:
      for branch in branches:failures+=branch['failures']
    elif ok is None:unknown.append('Unresolved nested '+local(pred))
 ok=False if failures else None if unknown else True
 return dict(ok=ok,failures=failures,unknown=unknown,logical=logical,children=children)

def intended_leaf(record,leaf,good):
 roots={tuple(x) for x in record['selected_repair']['semantic_roots']}
 scope=tuple(leaf['scope']) if leaf.get('scope') else None
 if scope not in roots:return False
 kind=leaf['kind'];prop=local(scope[1]);owner=URIRef(leaf['owner']);path=leaf['path']
 if kind=='minCount':return leaf['expected']==1
 if kind=='maxCount':return record['source_evidence']['contract'].get('cardinalityPolicies',{}).get(prop,{}).get('maxCount')==leaf['expected']
 if kind=='hasValue':
  values=list(good.objects(owner,URIRef(path))) if isinstance(path,str) else []
  if not any(x.n3()==leaf['expected'] for x in values):return False
  if path==str(Q.unit):return True # frozen canonical unit and unchanged number
  if any(isinstance(x,Literal) and x.datatype in [XSD.decimal,XSD.integer,XSD.double] for x in values):
   bound=BOUNDS.get((record['requirement_id'],prop,kind));return bound is not None and any(number(x)==number(bound) for x in values)
  return True # source-fixed boolean, approval state or explicit controlled constant
 if kind=='datatype':return True
 if kind in ['minInclusive','maxInclusive','minExclusive','maxExclusive']:
  bound=BOUNDS.get((record['requirement_id'],prop,kind))
  if record['requirement_id']=='TRF-126' and prop=='airReceiverConsecutiveStartCapacity' and kind=='minInclusive':
   flag=good.value(URIRef(scope[0]),N.propulsionEngineReversedForAstern);bound='12' if flag==Literal(True) else '6' if flag==Literal(False) else None
  if record['requirement_id']=='TRF-128' and prop=='compressorChargeTime' and kind=='maxInclusive':
   owner=URIRef(scope[0]);ice=good.value(owner,N.iceClass);flag=good.value(owner,N.propulsionEngineReversedForAstern)
   if ice is not None and flag in [Literal(True),Literal(False)]:bound='0.5' if ice==N.iceClassIaSuper and flag==Literal(True) else '1'
  if record['requirement_id']=='TRF-036' and prop=='designIceLoadHeight' and kind=='minInclusive':
   bound={N.iceClassIaSuper:'0.35',N.iceClassIa:'0.30',N.iceClassIb:'0.25',N.iceClassIc:'0.22'}.get(good.value(URIRef(scope[0]),N.iceClass))
  return bound is not None and number(bound)==number(leaf['expected'])
 if kind=='in':
  expected=ENUMS.get((record['requirement_id'],prop))
  if expected is None:return False
  allowed=[str(next(iter(audit.load_triples([f'<urn:s> <urn:p> {v} .'])))[2]) for v in leaf['expected']]
  return set(allowed)==set(expected)
 return False

def source_graph(report,shape,source):
 if list(report.predicate_objects(source)):return report
 if isinstance(source,URIRef) and list(shape.predicate_objects(source)):return shape
 return None

def wrapper_proof(record,v,sg,bad,good,source_node=None,head_override=None):
 source=source_node if source_node is not None else URIRef(v['source_shape'])
 # Source blank nodes must be resolved through the saved report graph, never
 # through the parser's new blank-node labels.
 if not (source,None,None) in sg:
  candidates=[s for s in sg.subjects(RDF.type,S.NodeShape) if str(s)==v['source_shape']]
  if not candidates:return dict(resolved=False,why='Reported blank-node source is not structurally identified')
  source=candidates[0]
 pred=S.xone if v['component']=='XoneConstraintComponent' else S['or']
 heads=[head_override] if head_override is not None else list(sg.objects(source,pred))
 if not heads:return dict(resolved=False,why='Wrapper source has no logical list')
 if len(heads)>1:
  # The report can name one shape with several OR lists without identifying a
  # list by blank-node ID. Inspect every list: unchanged passing lists cannot
  # be its reported failure, and every failing list must have intended proof.
  lists=[];proved=0
  for head in heads:
   children=seq(sg,head);bs=[trace(sg,n,bad,URIRef(v['focus']))['ok'] for n in children];gs=[trace(sg,n,good,URIRef(v['focus']))['ok'] for n in children]
   passes=lambda xs:any(x is True for x in xs) if pred==S['or'] else all(x is not None for x in xs) and sum(x is True for x in xs)==1
   if passes(bs) and passes(gs):lists.append(dict(disposition='UNCHANGED_PASS',bad_branch_states=bs,repaired_branch_states=gs));continue
   proof=wrapper_proof(record,v,sg,bad,good,source,head)
   lists.append(proof)
   if not proof['resolved']:return dict(resolved=False,why='One of several logical lists remains unbound',lists=lists)
   proved+=1
  return dict(resolved=bool(proved),meaning='All source-shape logical lists inspected; unchanged passing lists omitted, every failing list corresponds to the intended defect.',lists=lists)
 focus=URIRef(v['focus']);branches=seq(sg,heads[0]);guards=set(GUARDS.get(record['requirement_id'],[]))
 guards.update(record['source_evidence']['contract'].get('applicabilityTerms',[]))
 # Changing applicability in a supplied counterfactual cannot be justified by
 # selecting a different branch here.
 roots={tuple(x) for x in record['selected_repair']['semantic_roots']}
 if record['requirement_id']=='TRF-075' and pred==S.xone:
  paths={sg.value(n,S.path) for n in branches}
  if paths!={N.backwardBladeForce,N.forwardBladeForce}:return dict(resolved=False,why='Unreviewed exclusive-force paths')
  bs=[trace(sg,n,bad,focus) for n in branches];gs=[trace(sg,n,good,focus) for n in branches]
  ok=all(x['ok'] is not None for x in bs+gs) and sum(x['ok'] is True for x in bs)==2 and sum(x['ok'] is True for x in gs)==1
  return dict(resolved=ok,meaning='Source explicitly forbids simultaneous forward/backward forces. Both canonical force branches conform in the negative; removal of only the intended extra force leaves exactly one conforming branch in the saved repaired pair.',bad_branches=bs,repaired_branches=gs,source_clause=record['source_clause'])
 if any(local(p) in guards and set(bad.objects(URIRef(s),URIRef(p)))!=set(good.objects(URIRef(s),URIRef(p))) for s,p in roots):return dict(resolved=False,why='Counterfactual changes an applicability selector')
 evidence=[];all_failures=[];active=0
 for i,branch in enumerate(branches):
  b=trace(sg,branch,bad,focus);g=trace(sg,branch,good,focus)
  # Only a direct branch guard can rule out a branch. A failed selector
  # inside one nested alternative does not make the whole branch inapplicable.
  guard_failures=[]
  for child in sg.objects(branch,S.property):
   guard_path=sg.value(child,S.path)
   if not isinstance(guard_path,URIRef) or local(guard_path) not in guards:continue
   if any(sg.value(child,p) is not None for p in [S['or'],S['and'],S.xone]):continue
   guard_trace=trace(sg,child,bad,focus)
   guard_failures.extend(f for f in guard_trace['failures'] if f.get('scope') and tuple(f['scope']) not in roots)
  inactive=bool(guard_failures)
  if inactive:
   # These selector terms must be identical in both immutable fixture graphs.
   for f in guard_failures:
    s,p=map(URIRef,f['scope'])
    if set(bad.objects(s,p))!=set(good.objects(s,p)):return dict(resolved=False,why='Inactive-branch selector changes')
  else:
   active+=1
   if b['ok'] is None or g['ok'] is None:return dict(resolved=False,why='Unsupported/inference-dependent applicable branch',branches=evidence+[dict(index=i,bad=b,repaired=g)])
   if b['ok'] is not False or g['ok'] is not True:return dict(resolved=False,why='Applicable branch does not isolate intended negative-to-repaired change',branches=evidence+[dict(index=i,bad=b,repaired=g)])
   if not b['failures'] or not all(intended_leaf(record,f,good) for f in b['failures']):return dict(resolved=False,why='Applicable branch has unbound or other-field failures',branches=evidence+[dict(index=i,bad=b,repaired=g)])
   all_failures+=b['failures']
  evidence.append(dict(index=i,applicability='INACTIVE_BY_UNCHANGED_SOURCE_SELECTOR' if inactive else 'APPLICABLE',guard_failures=guard_failures,bad=b,repaired=g))
 if not active:return dict(resolved=False,why='No independently applicable branch established',branches=evidence)
 if pred==S.xone and active!=1:return dict(resolved=False,why='Exclusive alternatives not independently disambiguated',branches=evidence)
 return dict(resolved=True,meaning='Source-applicable branch fails only on the intended field; other branches are ruled out by unchanged source selectors. Saved full repaired report conforms.',branches=evidence,intended_leaf_failures=all_failures)


def query_proof(record,v):
 req=record['requirement_id'];entry=QUERY_REVIEWS.get(req)
 if entry is None:return dict(resolved=False,why='Query needs a separate reviewed algebra/table/applicability correspondence')
 props,note=entry;roots={local(p) for s,p in record['selected_repair']['semantic_roots']}
 if not roots<=set(props.split()):return dict(resolved=False,why='Changed field is outside the reviewed query scope')
 query=v.get('query');digest=v.get('query_sha256')
 if not query or hashlib.sha256(query.encode()).hexdigest()!=digest:return dict(resolved=False,why='No exact saved query text/hash')
 bindings=[b for b in QUERY_BINDINGS if b['requirement_id']==req and b['workflow']==record.get('_workflow') and b['query_sha256']==digest]
 if len(bindings)!=1:return dict(resolved=False,why='Query bytes are outside the individually reviewed immutable bindings')
 if not any(p in query for p in roots):return dict(resolved=False,why='Query does not explicitly traverse intended field')
 if req=='I2-048':
  graph=Graph().parse(record['negative_fixture']);ship=next(graph.subjects(RDF.type,N.ship));case=next(graph.subjects(RDF.type,N.steelGradeRequirementCase));q=graph.value(case,N.asBuiltPlateThickness)
  if not (graph.value(ship,N.polarClass)==N.polarClassPc3 and graph.value(case,N.steelMaterialClass)==N.steelMaterialClassOne and graph.value(case,N.steelStrengthCategory)==N.normalStrengthSteelCategory and graph.value(q,Q.numericValue).toPython()==17.5):return dict(resolved=False,why='Table query binding is restricted to the manually reviewed source cell')
 # These SELECT correspondences are individually bound to complete query bytes,
 # source clauses, fixture deltas and already saved counterfactual reports.
 return dict(resolved=True,meaning=note,query_sha256=digest,query=query,source_clause=record['source_clause'],source_text=record['source_evidence']['frozen_requirement_text'],representation_contract=record['source_evidence']['contract'],intended_properties=sorted(roots),exact_repair=record['selected_repair'])

def wrong_owner_additional_failure(record,v,bad,good):
 if record['requirement_id']!='TRF-050' or v['path']!=str(N.shellPlateButtCrossing):return None
 focus=URIRef(v['focus']);owner_class=record['source_evidence']['term_owners'].get('shellPlateButtCrossing')
 if owner_class!='frameAttachmentRecord' or (focus,RDF.type,N.frame) not in bad:return None
 owners=list(bad.subjects(RDF.type,N.frameAttachmentRecord))
 evidence=[dict(owner=str(s),types=[str(t) for t in bad.objects(s,RDF.type)],bad_values=[o.n3() for o in bad.objects(s,N.shellPlateButtCrossing)],repaired_values=[o.n3() for o in good.objects(s,N.shellPlateButtCrossing)]) for s in owners]
 if not owners or not all(e['bad_values'] and e['bad_values']==e['repaired_values'] for e in evidence):return None
 if list(bad.objects(focus,N.shellPlateButtCrossing)) or list(good.objects(focus,N.shellPlateButtCrossing)):return None
 return dict(resolved=True,verdict='UNRELATED',meaning='Additional missing shellPlateButtCrossing is reported on the frame, whereas source/contract places it on the attachment record and that assertion is already present and unchanged. Intended repair moves frameShellWeldType only. Removing the incorrectly targeted frame after repair does not turn this extra assertion failure into intended-defect evidence.',canonical_owner=owner_class,reported_focus=str(focus),asserted_focus_types=[str(t) for t in bad.objects(focus,RDF.type)],canonical_owner_evidence=evidence)


def inspect_case(record):
 bad=Graph().parse(record['negative_fixture']);good=Graph().parse(record['repaired_fixture']);proofs={};changes={}
 for w,old in record['workflows'].items():
  if old['status']!='UNRESOLVED_REASON':continue
  assert old['original_eligible'] and old['negative']['conforms'] is False and old['repaired']['conforms'] is True
  assert graph_hash(record['negative_fixture'])==record['negative_fixture_sha256'] and graph_hash(record['repaired_fixture'])==record['repaired_fixture_sha256']
  folder=OUT/'cases'/record['case_id']/w;shape=Graph().parse(folder/'evaluated_shape.ttl');report=Graph().parse(old['negative']['report_path'])
  assert audit.sha(folder/'evaluated_shape.ttl')==old['shape_sha256']
  assert set(report.objects(None,S.conforms))=={Literal(False)}
  assert set(Graph().parse(old['repaired']['report_path']).objects(None,S.conforms))=={Literal(True)}
  reviews=[]
  for v in old['violation_reason_review']['unresolved']:
   additional=wrong_owner_additional_failure(record,v,bad,good)
   if additional is not None:p=additional
   elif record['requirement_id'] in ['IMO-072','IMO-073'] and not record['selected_repair']['added_triples']:
    p=dict(resolved=False,why='Supplied counterfactual removes the lifeboat population rather than supplying the missing lifeboat assertion. Preserve as unresolved; no fixture or original result is changed.',removed_triples=record['selected_repair']['removed_triples'])
   elif v['component']=='SPARQLConstraintComponent':p=query_proof(dict(record,_workflow=w),v)
   elif v['component'] in ['OrConstraintComponent','XoneConstraintComponent']:
    # Recover report instances by component, focus and path. For anonymous
    # sources, require *every* structurally eligible report instance to prove
    # the correspondence; no historic blank-node label or message is matched.
    from evaluate import path_value
    candidates=[]
    for result in report.subjects(RDF.type,S.ValidationResult):
     if report.value(result,S.sourceConstraintComponent)!=S[v['component']] or str(report.value(result,S.focusNode))!=v['focus']:continue
     if path_value(report,report.value(result,S.resultPath))!=v['path']:continue
     src=report.value(result,S.sourceShape)
     if isinstance(src,URIRef) and str(src)!=v['source_shape']:continue
     candidates.append(src)
    ps=[]
    for src in set(candidates):
     sg=source_graph(report,shape,src)
     ps.append(wrapper_proof(record,dict(v,source_shape=str(src)),sg,bad,good,src) if sg is not None else dict(resolved=False,why='Logical source subgraph unavailable'))
    p=ps[0] if len(ps)==1 else dict(resolved=bool(ps) and all(x['resolved'] for x in ps),meaning='Every component/focus/path-compatible report source reviewed, without message or blank-node-ID pairing.',candidate_proofs=ps)
   elif v['component']=='InConstraintComponent':
    root=next((r for r in record['selected_repair']['semantic_roots'] if r[0]==v['focus'] and r[1]==v['path']),None)
    leaf=dict(kind='in',owner=v['focus'],path=v['path'],scope=root,expected=v.get('enumeration',[]))
    ok=bool(root and leaf['expected'] and intended_leaf(record,leaf,good));p=dict(resolved=ok,meaning='Exact source/contract enumeration alternatives match this intended field.',leaf=leaf)
   else:p=dict(resolved=False,why='No reviewed direct-constraint correspondence in this continuation')
   reviews.append(dict(component=v['component'],source_shape=v['source_shape'],focus=v['focus'],proof=p))
  unrelated=any(x['proof'].get('verdict')=='UNRELATED' for x in reviews)
  accepted=unrelated or bool(reviews) and all(x['proof']['resolved'] for x in reviews) and not old['violation_reason_review']['unrelated']
  proofs[w]=dict(resolved=accepted,constraints=reviews,original_status=old['status'],negative_report=old['negative']['report_path'],repaired_report=old['repaired']['report_path'],saved_negative_conforms=False,saved_repaired_conforms=True)
  if accepted:changes[w]='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE' if unrelated else 'STRICT_INTENDED_MATCH'
 return dict(case_id=record['case_id'],requirement_id=record['requirement_id'],source_clause=record['source_clause'],intended_rationale=record['intended_rationale'],source_evidence=record['source_evidence'],workflows=proofs,proposed_changes=changes,fully_resolved=all(v['status']!='UNRESOLVED_REASON' or w in changes for w,v in record['workflows'].items()))


def all_records():return [audit.read(p) for p in sorted((OUT/'records').glob('*.json'))]
def export_csv(path,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with path.open('w',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=fields);wr.writeheader()
  for r in rows:wr.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def protected(rs):
 paths=[BASE/'baseline_results.json',BASE/'review_batches/batch50/strict_results.json',BASE/'review_batches/batch50/reviewed_failure_specs.json']
 paths += [p for p in OUT.glob('*') if p.is_file()]
 paths += list((OUT/'cases').rglob('*'))
 paths += [OUT/'records'/f'{r["case_id"]}.json' for r in rs if r['state']!='BLOCKED' or not r.get('workflows')]
 return {str(p):audit.sha(p) for p in paths if p.is_file()}

def inspect(review):
 rs=all_records();target=[r for r in rs if r['state']=='BLOCKED' and r.get('workflows')]
 assert len(target)==201,'Use a fresh explicit target inventory after this continuation has been applied'
 assert sum(r['state']=='BLOCKED' and not r.get('workflows') for r in rs)==529
 review.mkdir(parents=True,exist_ok=False)
 atomic(review/'protected_before.json',protected(rs));atomic(review/'initial_records.json',target)
 code=Path(__file__);(review/'semantic_review.py').write_bytes(code.read_bytes())
 (review/QUERY_BINDINGS_PATH.name).write_bytes(QUERY_BINDINGS_PATH.read_bytes())
 dependencies=[code,QUERY_BINDINGS_PATH,audit.HERE/'full_audit/common.py',audit.HERE/'full_audit/prepare.py',audit.HERE/'full_audit/evaluate.py',audit.HERE/'audit.py',audit.ONTOLOGY]
 atomic(review/'implementation_inputs.json',{str(p):audit.sha(p) for p in dependencies})
 for i,r in enumerate(target,1):
  result=inspect_case(r);atomic(review/'cases'/f'{r["case_id"]}.json',result)
  if i%25==0:print(f'Semantic evidence checkpoint {i}/201',flush=True)
 results=[audit.read(p) for p in sorted((review/'cases').glob('*.json'))]
 inputs=list((review/'cases').glob('*.json'))+[review/'initial_records.json',review/'semantic_review.py',review/QUERY_BINDINGS_PATH.name,review/'protected_before.json',review/'implementation_inputs.json']
 atomic(review/'review_manifest.json',{str(p):audit.sha(p) for p in inputs})
 counts=dict(target_cases=201,fully_resolvable=sum(r['fully_resolved'] for r in results),workflow_constraints_resolved=sum(len(r['proposed_changes']) for r in results),source_repair_blockers_untouched=529,new_validations=0,new_query_executions=0)
 atomic(review/'preview.json',counts);print(json.dumps(counts,indent=2))

def apply(review):
 initial=audit.read(review/'initial_records.json');results={p.stem:audit.read(p) for p in (review/'cases').glob('*.json')};assert len(results)==201
 for path,sha in audit.read(review/'review_manifest.json').items():assert audit.sha(path)==sha,'Inspected evidence changed'
 for path,sha in audit.read(review/'implementation_inputs.json').items():assert audit.sha(path)==sha,'Inspection implementation/input changed'
 for path,sha in audit.read(review/'protected_before.json').items():assert audit.sha(path)==sha,f'Protected artifact changed: {path}'
 original={r['case_id']:r for r in initial};updates=[]
 for cid,r in original.items():
  path=OUT/'records'/f'{cid}.json';current=audit.read(path)
  result=results[cid]
  if not result['proposed_changes']:
   assert current==r,'Unresolved target record changed since inspection';continue
  new=copy.deepcopy(r)
  for w,status in result['proposed_changes'].items():
   v=new['workflows'][w];assert v['status']=='UNRESOLVED_REASON'
   v.update(status=status,semantic_review=str(review/'cases'/f'{cid}.json'),likely_cause=dict(primary='CONTEXT_SCHEMA_MISMATCH' if status=='MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE' else 'NONE_IDENTIFIED',detail='Source/contract-bound query or applicable-branch meaning established from immutable saved paired evidence; see the reviewed owner proof for additional failures.'))
   v.pop('blocker',None)
   meaning=v['violation_reason_review'];prior_unresolved=copy.deepcopy(meaning['unresolved'])
   meaning['prior_unresolved_constraints']=prior_unresolved;meaning['semantic_review']=v['semantic_review']
   if status=='STRICT_INTENDED_MATCH':
    meaning['intended']+=prior_unresolved;meaning['unresolved']=[]
   else:
    additional=[d for d in prior_unresolved if d['component']=='MinCountConstraintComponent' and d['path']==str(N.shellPlateButtCrossing)]
    meaning['unrelated']+=additional;meaning['unresolved']=[d for d in prior_unresolved if d not in additional]
  remaining=[dict(workflow=w,**v['blocker']) for w,v in new['workflows'].items() if v.get('blocker')]
  new['blockers']=remaining;new['state']='BLOCKED' if remaining else 'COMPLETED';new['semantic_review']=str(review/'cases'/f'{cid}.json')
  assert current in [r,new],'Target record changed outside this semantic review'
  if current!=new:
   atomic(review/'before'/f'{cid}.json',r);atomic(path,new)
  updates.append(dict(case_id=cid,requirement_id=r['requirement_id'],new_state=new['state'],changed_workflows=result['proposed_changes']))
 for path,sha in audit.read(review/'protected_before.json').items():assert audit.sha(path)==sha,f'Protected artifact changed: {path}'
 rs=all_records();complete=[r for r in rs if r['state'] in ['COMPLETED','COMPLETED_PRIOR50']];rows=[]
 for w,label in audit.WORKFLOWS.items():
  counts=Counter(r['workflows'][w]['status'] for r in complete)
  for status in ['STRICT_INTENDED_MATCH','MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE','MISSED_INTENDED_DEFECT','NO_VERDICT']:
   rows.append(dict(workflow=label,status=status,count=counts[status],denominator=len(complete),percentage=100*counts[status]/len(complete)))
  assert sum(counts.values())==len(complete) and not counts['UNRESOLVED_REASON']
 after=dict(resolved_cases=len(complete)-474,resolved_workflow_blockers=sum(len(u['changed_workflows']) for u in updates),fully_classified_cases=len(complete),fully_classified_requirements=len({r['requirement_id'] for r in complete}),remaining_semantic_cases=sum(r['state']=='BLOCKED' and bool(r.get('workflows')) for r in rs),source_repair_blockers=529,excluded=sum(r['state']=='EXCLUDED' for r in rs),strict_summary=rows,validation_executions=0,query_executions=0,completed_cases_reexecuted=0,unchanged_reports_rebuilt=0,protected_artifact_hashes_unchanged=True)
 atomic(review/'updates.json',updates);atomic(review/'summary.json',after);atomic(review/'common_fully_classified_case_ids.json',[r['case_id'] for r in complete]);export_csv(review/'strict_summary.csv',rows)
 export_csv(review/'case_changes.csv',updates)
 remaining=[]
 for cid,result in results.items():
  pending={w:[c['proof'].get('why',c['proof'].get('meaning','Unresolved enumeration')) for c in v['constraints'] if not c['proof']['resolved']] for w,v in result['workflows'].items() if not v['resolved']}
  if pending:remaining.append(dict(case_id=cid,requirement_id=result['requirement_id'],pending_workflows=pending,evidence=str(review/'cases'/f'{cid}.json')))
 assert len(remaining)==after['remaining_semantic_cases'];export_csv(review/'remaining_semantic_cases.csv',remaining)
 lines=['# Saved-evidence semantics continuation','',f"Resolved **{after['resolved_cases']} of 201 case blockers** ({after['resolved_workflow_blockers']} workflow blockers). **{after['remaining_semantic_cases']}** cases remain semantically unresolved. The **529** source/repair blockers and prior single exclusion are untouched.",'',f"Common fully classified subset: **{len(complete)} negatives across {after['fully_classified_requirements']} requirements** for both workflows. Historical no-verdicts remain uncredited. These are subset results, not full-benchmark strict accuracy.",'','| Workflow | Strict match | Unrelated/additional | Missed | No verdict |','|---|---:|---:|---:|---:|']
 for w,label in audit.WORKFLOWS.items():
  vals=[r for r in rows if r['workflow']==label];lines.append('| '+label+' | '+' | '.join(f"{r['count']} ({r['percentage']:.1f}%)" for r in vals)+' |')
 lines+=['','No SHACL validation or SPARQL query execution was run. Existing completed records, both fixture files, shapes, validation reports, full ordinary metrics and historical reports are hash-checked and unchanged. Only formerly unresolved workflow statuses are updated. Source guards choose branches before counterfactual acceptance is checked. Unsupported/inference-dependent constructs, unbound alternatives, complex tables and applicability-repair concerns remain unresolved.','', 'Examples: both I2-042 queries explicitly test flangeWidth < 5*netWebThickness; conditional IMO-018/030 branches fail only on the intended obligation under fixed selectors; the local I2-048 PC3/17.5-mm/material-One/normal-strength Table-8 cell was traced to D and the exact missing/wrong-grade/rank/family disjunct. TRF-050-F05 receives unrelated/additional-failure classification in both workflows because shellPlateButtCrossing is wrongly required on the frame even though it is already supplied on the attachment record. One confirmed unrelated report is enough to deny strict credit; other unresolved leaves remain visible.','', 'The unresolved inventory is `remaining_semantic_cases.csv`. In particular, IMO-072-F01 and IMO-073-F02 supplied counterfactuals remove the lifeboat instead of providing its missing assertion. Applicability-changing counterfactuals and complex unbound branch/query combinations also remain unresolved. These concerns are preserved in the 201-case semantic-review arm; none is silently added to or removed from the separate 529 source/repair blockers.','', 'Every one of the 201 cases has an evidence record in `cases/`, including the complete inspected SELECT or branch/leaf trace where resolved. `before/` preserves each changed parent record; `updates.json` contains the delta. The frozen inspected implementation and exact SELECT bindings are saved here. No message text or historic blank-node ID is a matching criterion.']
 (review/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(after,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['inspect','apply'],required=True);p.add_argument('--review-dir',type=Path);args=p.parse_args()
 review=args.review_dir or OUT/'semantic_reviews'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 if args.phase=='inspect':inspect(review)
 else:
  assert args.review_dir,'Apply requires the exact inspected review directory';apply(review)
 print('Review directory:',review)
