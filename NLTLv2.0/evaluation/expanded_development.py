"""Independent evaluation ONLY: source-authored controls for finite reviewed subsets.
Never import from production. Table/branch limits are stored with the selection.
"""
from pathlib import Path
from decimal import Decimal
from datetime import date
import json
from rdflib import Graph,Literal,RDF,RDFS,XSD,URIRef
from owlrl import DeductiveClosure,RDFS_Semantics
from nltlv2.schema import N,Q,U
SUPPORTED={'I2-046','TRF-015','I2-048','TRF-001','TRF-036','TRF-050','TRF-003','TRF-018','TRF-032','TRF-128','I2-019','I2-021','I2-041','I2-066','IMO-057','IMO-078','IMO-083','IMO-086'}
TABLE=json.loads((Path(__file__).parent/'provenance/twenty_preparation/table8_transcription.json').read_text())
GROUPS={'PC1-5':{1,2,3,4,5},'PC6-7':{6,7},'PC1-3':{1,2,3},'PC4-5':{4,5}}
GRADE={'B':'steelGradeB','D':'steelGradeD','E':'steelGradeE','AH':'steelGradeAh','DH':'steelGradeDh','EH':'steelGradeEh','FH':'steelGradeFh'}
RANK={'normalStrengthSteelCategory':{'steelGradeA':0,'steelGradeB':1,'steelGradeD':2,'steelGradeE':3},'highTensileSteelCategory':{'steelGradeAh':0,'steelGradeDh':1,'steelGradeEh':2,'steelGradeFh':3}}

def representation_graph(data,ontology):
 """RDFS classes relevant to supplied assertions; retain original field values."""
 g=Graph()
 for triple in data:g.add(triple)
 # RDFS axioms relevant to the ORIGINAL data only; avoid copying unrelated ontology
 # individuals into the case population. No inferred ownership restriction is added.
 properties=set(g.predicates());classes=set(g.objects(None,RDF.type));pending=list(properties)
 while pending:
  prop=pending.pop()
  for predicate in [RDFS.domain,RDFS.range,RDFS.subPropertyOf]:
   for obj in ontology.objects(prop,predicate):
    g.add((prop,predicate,obj))
    if predicate==RDFS.subPropertyOf and obj not in properties:properties.add(obj);pending.append(obj)
    elif predicate!=RDFS.subPropertyOf:classes.add(obj)
 pending=list(classes)
 while pending:
  cls=pending.pop()
  for parent in ontology.objects(cls,RDFS.subClassOf):
   g.add((cls,RDFS.subClassOf,parent))
   if parent not in classes:classes.add(parent);pending.append(parent)
 DeductiveClosure(RDFS_Semantics).expand(g)
 # Use entailment for class membership; read field values from original assertions.
 # owlrl may materialize equal-valued literal spellings/datatype aliases; these
 # are not additional supplied observations and must not change source inputs.
 typed=list(g.triples((None,RDF.type,None)));g=Graph()
 for triple in data:g.add(triple)
 for subject,predicate,cls in typed:
  if not isinstance(subject,Literal):g.add((subject,predicate,cls))
 return g

def oracle(data,rid,ontology):
 if rid not in SUPPORTED:return dict(conforms=None,issues=[],unresolved=['NO_SOURCE_ORACLE'])
 g=representation_graph(data,ontology)
 issues=[];unresolved=[];witness=[]
 def fail(p,reason):issues.append(p);witness.append(dict(property=p,reason=reason))
 def one(owner,prop,required=True):
  vals=list(g.objects(owner,N[prop]))
  if not vals:
   if required:fail(prop,'MISSING_REPRESENTED_VALUE')
   return None
  if len(vals)!=1:unresolved.append('MULTIVALUED_'+prop);return None
  return vals[0]
 def quantity(owner,prop,unit=None):
  node=one(owner,prop)
  if node is None:return None
  ns=list(g.objects(node,Q.numericValue));us=list(g.objects(node,Q.unit))
  if len(ns)!=1 or not isinstance(ns[0],Literal) or ns[0].datatype!=XSD.decimal or len(us)!=1 or unit is not None and us!=[unit]:fail(prop,'CANONICAL_DECIMAL_OR_UNIT_INVALID');return None
  try:value=Decimal(str(ns[0]))
  except Exception:fail(prop,'NONNUMERIC');return None
  if not value.is_finite():fail(prop,'NONFINITE');return None
  return value,us[0]
 def value(owner,prop,unit):
  x=quantity(owner,prop,unit);return x[0] if x else None
 def boolean(owner,prop):
  x=one(owner,prop)
  if x is not None and (not isinstance(x,Literal) or x.datatype!=XSD.boolean):fail(prop,'BOOLEAN_REQUIRED');return None
  return None if x is None else bool(x.toPython())
 ships=list(g.subjects(RDF.type,N.ship));ship=ships[0] if len(ships)==1 else None
 if rid!='TRF-050' and ship is None:return dict(conforms=None,issues=[],unresolved=['SHIP_IDENTITY_NOT_UNIQUE'])
 if rid=='TRF-003':
  dt=one(ship,'constructionContractDate')
  if dt is not None:
   if not isinstance(dt,Literal) or dt.datatype!=XSD.date:fail('constructionContractDate','DATE_REQUIRED')
   elif date(2012,1,1)<=date.fromisoformat(str(dt))<date(2019,1,1) and one(ship,'applicableIceClassRegulationEdition')!=N.iceClassRegulationEdition2010:fail('applicableIceClassRegulationEdition','SOURCE_DATE_INTERVAL_EDITION')
 elif rid=='TRF-001':
  dt=one(ship,'constructionContractDate')
  provisions=set(g.objects(ship,N.applicableIceClassRegulatoryProvision))
  if not {N.iceClassSection1Point8Provision2021,N.iceClassDraughtChapter2Provision2021}<=provisions:fail('applicableIceClassRegulatoryProvision','MISSING_UNIVERSAL_SOURCE_PROVISION')
  if dt is not None:
   if not isinstance(dt,Literal) or dt.datatype!=XSD.date:fail('constructionContractDate','DATE_REQUIRED')
   elif date.fromisoformat(str(dt))>=date(2021,7,5) and one(ship,'applicableIceClassRegulationEdition')!=N.iceClassRegulationEdition2021:fail('applicableIceClassRegulationEdition','SOURCE_DATE_INTERVAL_EDITION')
 elif rid=='TRF-015':
  navigating=boolean(ship,'navigatingInIce')
  if navigating is False:unresolved.append('OFF_ICE_SECOND_CLAUSE_APPLICABILITY_NOT_ESTABLISHED')
  elif navigating is True:
   actual=value(ship,'operatingDraught',U.M);limit=value(ship,'upperIceWaterlineDraught',U.M);trim=value(ship,'operatingTrim',U.M);allowed=value(ship,'maximumPermittedIceTrim',U.M)
   route=quantity(ship,'intendedRouteSeaWaterSalinity',N.gramPerKilogramSalinityUnit);loading=quantity(ship,'loadingCalculationSeaWaterSalinity',N.gramPerKilogramSalinityUnit)
   if actual is not None and limit is not None and actual>limit:fail('operatingDraught','ABOVE_SOURCE_UIWL')
   if trim is not None and allowed is not None:
    if trim<0 or allowed<0:unresolved.append('SIGNED_TRIM_REPRESENTATION_NOT_ESTABLISHED')
    elif trim>allowed:fail('operatingTrim','ABOVE_SUPPLIED_ICE_TRIM_LIMIT')
   if route and loading and route!=loading:unresolved.append('TAKEN_INTO_ACCOUNT_NOT_PROOF_OF_EXACT_SCALAR_EQUALITY')
 elif rid=='TRF-018':
  cls=one(ship,'iceClass');actual=value(ship,'maximumContinuousRatingPower',U.KiloW);calc=value(ship,'calculatedRequiredPower',U.KiloW)
  floors={N.iceClassIaSuper:Decimal(2800),N.iceClassIa:Decimal(1000),N.iceClassIb:Decimal(1000),N.iceClassIc:Decimal(1000)}
  known=set(floors)|{N.iceClassIi,N.iceClassIii}
  if cls is not None and cls not in known:unresolved.append('UNRECOGNIZED_CLASS')
  if actual is not None and calc is not None and cls in known and actual<max(calc,floors.get(cls,Decimal(0))):fail('maximumContinuousRatingPower','BELOW_SOURCE_MINIMA')
 elif rid=='TRF-032':
  a=quantity(ship,'regulationRequiredScantling');b=quantity(ship,'classificationSocietyRequiredScantling');c=quantity(ship,'selectedDesignScantling')
  if a and b and c:
   if len({a[1],b[1],c[1]})!=1:fail('selectedDesignScantling','INCOMPARABLE_INPUT_UNITS')
   elif c[0]<max(a[0],b[0]):fail('selectedDesignScantling','BELOW_APPLICABLE_MINIMUM')
   elif c[0]>max(a[0],b[0]):unresolved.append('ABOVE_REFERENCE_SELECTION_ROLE_NOT_RESOLVED_BY_MAPPING')
 elif rid=='TRF-128':
  cls=one(ship,'iceClass');reverse=boolean(ship,'propulsionEngineReversalRequiredForAstern');hours=value(ship,'compressorChargeTime',U.HR)
  if cls is not None and reverse is not None and hours is not None and hours>(Decimal('.5') if cls==N.iceClassIaSuper and reverse else Decimal(1)):fail('compressorChargeTime','ABOVE_SOURCE_CHARGING_LIMIT')
 elif rid=='TRF-036':
  cls=one(ship,'iceClass');params=one(ship,'hasIceClassDesignParameterSet');table={N.iceClassIaSuper:(Decimal('1.0'),Decimal('.35')),N.iceClassIa:(Decimal('.8'),Decimal('.30')),N.iceClassIb:(Decimal('.6'),Decimal('.25')),N.iceClassIc:(Decimal('.4'),Decimal('.22'))}
  if cls is not None and cls not in table:unresolved.append('NON_TABLE_CLASS_SOURCE_EXPECTATION_UNESTABLISHED')
  if params is not None:
   hi=value(params,'levelIceThickness',U.M);h=value(params,'designIceLoadHeight',U.M)
   if cls in table:
    if hi is not None and hi!=table[cls][0]:fail('levelIceThickness','SOURCE_TABLE4_1')
    if h is not None and h!=table[cls][1]:fail('designIceLoadHeight','SOURCE_TABLE4_1')
 elif rid=='TRF-050':
  frames=set(g.subjects(RDF.type,N.frame))
  if not frames:unresolved.append('FRAME_INVENTORY_UNESTABLISHED')
  for frame in frames:
   record=one(frame,'frameAttachment')
   if record is None:continue
   weld=one(record,'frameShellWeldType');crossing=boolean(record,'shellPlateButtCrossing');scallop=boolean(record,'scallopingPresent')
   if weld is not None and weld!=N.doubleContinuousWeld:fail('frameShellWeldType','SOURCE_WELD_TYPE')
   if crossing is False and scallop is True:fail('scallopingPresent','OUTSIDE_SOURCE_EXCEPTION')
 elif rid=='I2-019':
  for member in g.objects(ship,N.hasStructuralMember):
   areas=list(g.objects(member,N.hasSpannedHullArea))
   if len(areas)<2:continue
   vals=[value(area,'hullAreaFactor',U.UNITLESS) for area in areas];actual=value(member,'selectedHullAreaFactor',U.UNITLESS)
   if vals and None not in vals and actual is not None and actual!=max(vals):fail('selectedHullAreaFactor','SOURCE_LARGEST_FACTOR')
 elif rid=='I2-021':
  for plate in g.objects(ship,N.hasPlating):
   actual=value(plate,'thickness',U.M);net=value(plate,'iceLoadRequiredNetPlateThickness',U.MilliM);allow=value(plate,'corrosionAbrasionAllowance',U.MilliM)
   if None not in [actual,net,allow] and actual*1000<net+allow:fail('thickness','BELOW_NET_PLUS_ALLOWANCE')
 elif rid=='I2-041':
  for member in g.objects(ship,N.hasStructuralMember):
   web=value(member,'netWebThickness',U.MilliM);plate=value(member,'netAttachedShellPlateThickness',U.MilliM);stress=value(member,'yieldStrength',U.MegaPA)
   if stress is not None and stress<0:unresolved.append('NEGATIVE_STRESS_INPUT')
   elif None not in [web,plate,stress] and web<Decimal('.35')*plate*(stress/235).sqrt():fail('netWebThickness','BELOW_SOURCE_ADDITIONAL_MINIMUM')
 elif rid=='I2-046':
  # Declared synthetic Polar-Class population; the legacy applicability flag is
  # not an independent source obligation and is not a substitute for admission.
  for structure in g.objects(ship,N.hasInternalIceStrengthenedStructure):
   addition=value(structure,'internalStructureCorrosionAbrasionAddition',U.MilliM)
   if addition is not None and addition<Decimal('1.0'):fail('internalStructureCorrosionAbrasionAddition','BELOW_SOURCE_INTERNAL_ADDITION')
 elif rid=='I2-066':
  for weld in g.objects(ship,N.hasWeld):
   inside=boolean(weld,'withinIceStrengthenedArea')
   if inside is True and one(weld,'weldType')!=N.doubleContinuousWeld:fail('weldType','SOURCE_IN_SCOPE_WELD_TYPE')
 elif rid=='IMO-057':
  for pump in g.objects(ship,N.hasComponent):
   if not set(g.objects(pump,RDF.type))&{N.firePump,N.emergencyFirePump,N.waterMistPump,N.waterSprayPump}:continue
   compartment=one(pump,'hasContainingCompartment')
   if compartment is not None:
    temp=value(compartment,'maintainedTemperature',U.DEG_C)
    if temp is not None and temp<=0:fail('maintainedTemperature','NOT_ABOVE_FREEZING')
 elif rid=='IMO-078':
  for passenger in g.objects(ship,N.hasPassenger):
   if boolean(passenger,'personalSurvivalEquipmentInstructionCompleted') is False:fail('personalSurvivalEquipmentInstructionCompleted','SOURCE_INSTRUCTION_INCOMPLETE')
  for crew in g.objects(ship,N.hasCrewMemberInventory):
   if boolean(crew,'personalAndGroupSurvivalEquipmentTrainingCompleted') is False:fail('personalAndGroupSurvivalEquipmentTrainingCompleted','SOURCE_TRAINING_INCOMPLETE')
 elif rid=='IMO-083':
  likely=boolean(ship,'iceAccretionLikely')
  if likely is True:
   for antenna in g.objects(ship,N.hasRequiredNavigationOrCommunicationAntenna):
    if boolean(antenna,'antennaIceAccumulationPreventionPresent') is False:fail('antennaIceAccumulationPreventionPresent','SOURCE_REQUIRED_PROTECTION_ABSENT')
 elif rid=='IMO-086':
  means=set(g.objects(ship,N.hasNonMagneticHeadingMeans));pairs=[(a,b) for a in means for b in means if a!=b and (b in set(g.objects(a,N.independentFromHeadingMeans)) or a in set(g.objects(b,N.independentFromHeadingMeans)))]
  if len(means)<2:fail('hasNonMagneticHeadingMeans','FEWER_THAN_TWO')
  elif not pairs:fail('independentFromHeadingMeans','NO_INDEPENDENT_LINKED_PAIR')
  else:
   incomplete=[]
   for a,b in pairs:
    missing={prop for device in [a,b] for prop in ['connectedToMainPower','connectedToEmergencyPower'] if not list(g.objects(device,N[prop]))}
    if not missing:break
    incomplete.append(missing)
   else:
    for prop in set.union(*incomplete):fail(prop,'REQUIRED_POWER_CONNECTION_MISSING')
 elif rid=='I2-048':
  cases=list(g.objects(ship,N.hasSteelGradeRequirementCase));pc=one(ship,'polarClass') if cases else None
  try:pcnum=int(str(pc).split('polarClassPc')[-1])
  except Exception:pcnum=None
  if pc is not None and pcnum is None:unresolved.append('UNRECOGNIZED_POLAR_CLASS')
  for case in cases:
   one(case,'steelGradeRequirementCasePlating');thickness=value(case,'asBuiltPlateThickness',U.MilliM);material=one(case,'steelMaterialClass');family=one(case,'steelStrengthCategory');refs=list(g.objects(case,N.tableReference));actual=one(case,'actualHullStructuralSteelGrade');required=list(g.objects(case,N.requiredHullStructuralSteelGrade))
   if not refs or any(ref!=N.iacsUrI2Table8 for ref in refs):fail('tableReference','SOURCE_TABLE8_REFERENCE')
   if thickness is None or material is None or family is None or pcnum is None:continue
   row=next((i for i,upper in enumerate(TABLE['upper_inclusive_mm']) if thickness<=Decimal(str(upper))),None);cols=[i for i,col in enumerate(TABLE['columns']) if material==N[col['steelMaterialClass']] and family==N[col['steelStrengthCategory']] and pcnum in GROUPS[col['polarClassGroup']]]
   if row is None or len(cols)!=1:unresolved.append('SOURCE_TABLE_CELL_UNESTABLISHED');continue
   grade=TABLE['grades'][row][cols[0]]
   if grade=='NA':
    if required:fail('requiredHullStructuralSteelGrade','NA_IS_NOT_GRADE')
   else:
    expected=N[GRADE[grade]]
    if required!=[expected]:fail('requiredHullStructuralSteelGrade','SOURCE_TABLE8_CELL')
    ranks=RANK.get(str(family).split('#')[-1],{});aname=str(actual).split('#')[-1]
    if actual is not None and (aname not in ranks or ranks[aname]<ranks[GRADE[grade]]):fail('actualHullStructuralSteelGrade','BELOW_SOURCE_GRADE_OR_INCOMPARABLE_FAMILY')
 return dict(conforms=None if unresolved else not issues,issues=sorted(set(issues)),unresolved=unresolved,witness=witness,scope='Finite source-reviewed development subset; not full branch certification')
